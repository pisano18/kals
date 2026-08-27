#!/usr/bin/env python3
# VERSION: 2026-08-25-ev1
"""
everything.py -- one command. Does every job in RUN_WHEN_HOME.md, in the right
order, and leaves one file to send back.

    python research\\everything.py

That is the whole invocation. No arguments, no placeholders, no paths to fill
in. It finds the repo, finds the data, works out how much of it there is, and
runs the lot.

WHAT IT DOES, IN ORDER

  0  preflight     Where is everything, how much data exists, is the recorder
                   alive, is there disk left, are the dependencies present.
  1  collection    Adds the two comparison series to the recorder's config.
                   This is FIRST because it is the only step where waiting
                   costs something permanent: an hour not recorded is gone.
  2  api           Four read-only public API calls: the fee schedule for
                   Financials and Crypto, and the real contract terms for
                   KXCRYPTOCOMP15M / KXCRYPTOLEAD15M.
  3  fulltape      Refreshes the settled-market outcomes several stages need.
  4  go            every self-test, then 13 analysis stages. The long one.
  5  power         What this much data could have detected at all. Runs AFTER
                   go, because go's chain stage writes the cache power sizes
                   itself from -- but it is printed FIRST in the report,
                   because it is what makes every other number readable.
  6  report        One markdown file and one zip.

RULES IT OBEYS

  - It NEVER places, amends or cancels an order. There is no order code in this
    repository and this file adds none.
  - It never writes, moves or deletes anything under kalshi_data/ or
    feed_data/. A recorder is writing there and that data cannot be rebuilt.
  - It never kills the recorder. It edits the watchdog's config and tells you
    how to restart it, at a moment you choose.
  - Every step is isolated. One failure does not stop the others, and the
    report says plainly what did not run.
  - The report is written after EVERY step, so an interrupted run still
    leaves something worth sending.

IF IT DIES
    Run it again. Add --skip go to leave out the long stage, or --only api to
    run a single step.
"""

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Windows writes files in the ANSI code page unless told otherwise, and this
# repo's reports contain em-dashes. A run that dies with UnicodeEncodeError at
# the last line, after forty minutes of work, is the worst failure available
# here, so nothing below opens a file without saying utf-8 and nothing reads a
# subprocess without saying utf-8.
# --------------------------------------------------------------------------
ENC = "utf-8"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
API = "https://api.elections.kalshi.com/trade-api/v2"

CRYPTO_15M = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
              "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
              "KXNEAR15M", "KXTON15M"]
COMPARISON = ["KXCRYPTOLEAD15M", "KXCRYPTOCOMP15M"]

T0 = time.time()
LOG = []


def say(msg="", also_report=True):
    el = time.time() - T0
    line = f"[{int(el)//60:>3}m{int(el)%60:02d}s] {msg}" if msg else ""
    print(line, flush=True)
    if also_report and msg:
        LOG.append(msg)


def rule(title):
    print("\n" + "=" * 78, flush=True)
    print(f"  {title}", flush=True)
    print("=" * 78, flush=True)


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:,.1f} {u}"
        n /= 1024.0
    return f"{n:,.1f} PB"


# ==========================================================================
# finding things
# ==========================================================================
def find_data_root(explicit):
    """Where the recorder is writing. Checked, not assumed."""
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("KALS_DATA"):
        cands.append(os.environ["KALS_DATA"])
    cands += [
        os.path.join(os.path.dirname(REPO), "kals"),   # C:\kals next to the repo
        "C:\\kals",
        REPO,
        os.getcwd(),
    ]
    seen = []
    for c in cands:
        if not c or c in seen:
            continue
        seen.append(c)
        if os.path.isdir(os.path.join(c, "kalshi_data")):
            return c, seen
    return None, seen


def channel_hours(data_dir):
    """channel -> hourly file count. The recorder writes one file per hour per
    channel, so the count IS the hours recorded -- and it counts only hours
    actually recorded, which is the number that matters."""
    out = {}
    if not os.path.isdir(data_dir):
        return out
    for ch in sorted(os.listdir(data_dir)):
        d = os.path.join(data_dir, ch)
        if os.path.isdir(d):
            n = len(glob.glob(os.path.join(d, "*.jsonl.gz")))
            if n:
                out[ch] = n
    return out


def newest_mtime(root):
    best = 0.0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            try:
                m = os.path.getmtime(os.path.join(dirpath, f))
            except OSError:
                continue
            if m > best:
                best = m
    return best


def dir_bytes(root):
    tot = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return tot


# ==========================================================================
# running things
# ==========================================================================
def run(cmd, cwd, timeout, label):
    """A child process, with its output forced to utf-8 in both directions."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable] + cmd, cwd=cwd, timeout=timeout,
                           capture_output=True, text=True, encoding=ENC,
                           errors="replace", env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(ENC, "replace")
        return 124, out + f"\n*** {label} TIMED OUT after {timeout}s ***", \
            time.time() - t0
    except Exception as e:
        return 1, f"*** {label}: {type(e).__name__}: {e} ***", time.time() - t0


def run_stream(cmd, cwd, timeout, label, prefix="    | "):
    """Like run(), but prints the child's output as it arrives.

    go.py's self-tests take fifteen minutes and its stages can take longer.
    Capturing that silently means staring at a dead terminal with no way to
    tell work from a hang, which is how a long unattended run gets killed at
    minute twelve. go.py already summarises its own children to one line each,
    so streaming it is exactly the right granularity.
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # -u as well: a child's stdout is BLOCK buffered when it is a pipe rather
    # than a console, so without this the "streaming" progress arrives all at
    # once when the child exits -- which is exactly the dead-terminal problem
    # streaming was added to solve.
    env["PYTHONUNBUFFERED"] = "1"
    t0, buf = time.time(), []
    try:
        p = subprocess.Popen([sys.executable, "-u"] + cmd, cwd=cwd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding=ENC, errors="replace", env=env,
                             bufsize=1)
    except Exception as e:
        return 1, f"*** {label}: {type(e).__name__}: {e} ***", 0.0

    # A child that goes SILENT forever would never trip a per-line deadline,
    # so the kill has to come from a timer rather than from the read loop.
    killed = {"by_timeout": False}

    def _kill():
        killed["by_timeout"] = True
        # Popen.kill() is TerminateProcess on Windows and does NOT take the
        # process tree with it: go.py would die and leave the stage it was
        # running orphaned, still holding files open and still writing.
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                               capture_output=True)
            else:
                p.kill()
        except Exception:
            pass
        try:
            p.kill()
        except Exception:
            pass

    timer = threading.Timer(timeout, _kill)
    timer.daemon = True
    timer.start()
    try:
        for line in p.stdout:
            line = line.rstrip("\n")
            buf.append(line)
            if line.strip():
                print(prefix + line[:150], flush=True)
    except KeyboardInterrupt:
        _kill()
        raise
    finally:
        timer.cancel()
        try:
            p.stdout.close()
        except Exception:
            pass
    rc = p.wait()
    if killed["by_timeout"]:
        buf.append(f"*** {label} TIMED OUT after {timeout}s ***")
        rc = 124
    return rc, "\n".join(buf), time.time() - t0


def get_json(url, timeout=30, tries=4):
    """Read-only GET against the PUBLIC Kalshi endpoints. No key, no POST.

    Every other REST fetcher in this repo `break`s out of its loop on a
    non-200 and returns what it has, so a rate-limit blip yields a short
    result that looks exactly like a complete one. This RAISES instead, and
    retries 429/5xx with backoff. A live collector is already spending the
    same ~20 reads/sec budget round the clock, so the backoff is not
    theoretical.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "kals-research/1.0 (read-only)",
        "Accept": "application/json",
    })
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            return json.loads(raw.decode(ENC, "replace")), raw
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode(ENC, "replace")[:200]
            except Exception:
                pass
            last = f"HTTP {e.code} {body}"
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(last)            # 4xx is terminal
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < tries - 1:
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(last or "unknown error")


# ==========================================================================
# the steps
# ==========================================================================
def step_preflight(ctx):
    rule("0  PREFLIGHT")
    say(f"python {platform.python_version()} on {platform.system()} "
        f"{platform.release()}")
    say(f"repo   {REPO}")
    say(f"data   {ctx['data_root'] or '*** NOT FOUND ***'}")
    if not ctx["data_root"]:
        say("Looked in: " + ", ".join(ctx["searched"]))
        say("Pass it explicitly:  python research\\everything.py "
            "--data C:\\kals")
        return False

    kd = os.path.join(ctx["data_root"], "kalshi_data")
    fd = os.path.join(ctx["data_root"], "feed_data")
    ch = channel_hours(kd)
    ctx["channels"] = ch
    if ch:
        say("recorded hours per channel:")
        for k, v in sorted(ch.items(), key=lambda x: -x[1]):
            say(f"    {k:<24} {v:>6,} hourly files")
    else:
        say("*** no hourly files under kalshi_data -- is the recorder running?")

    idx = ch.get("cfbenchmarks_value", 0)
    if idx:
        say(f"cfbenchmarks_value: {idx:,} hours. This is the feed every "
            f"model-based stage depends on.")
    else:
        say("*** cfbenchmarks_value is EMPTY. Most of go.py will have nothing "
            "to run on. See RUNBOOK 'API traps' -- that channel needs the "
            "param `index_ids`, and a {'type':'subscribed'} reply is NOT "
            "success.")

    for name, path in (("kalshi_data", kd), ("feed_data", fd)):
        if os.path.isdir(path):
            age = time.time() - newest_mtime(path)
            state = ("recorder LOOKS ALIVE" if age < 600
                     else f"newest file is {age/3600:.1f}h old -- "
                          "recorder may be STOPPED")
            say(f"{name:<12} {human(dir_bytes(path)):>10}   {state}")

    # Projected peak memory, per channel, from what is actually on disk.
    # A crash an hour into a run is almost always this: the loaders used to
    # materialise a whole channel as Python dicts, and decoded dicts run many
    # times their compressed size. Measured after streaming them: about 220
    # bytes of peak RSS per ticker message against 1,330 before.
    B_PER_MSG, COMPRESSED_B_PER_MSG = 220.0, 26.0
    heavy = []
    for ch in ("ticker", "orderbook_delta", "orderbook_snapshot"):
        d = os.path.join(kd, ch)
        if not os.path.isdir(d):
            continue
        gb = dir_bytes(d) / 1024 ** 3
        est = gb * 1024 ** 3 / COMPRESSED_B_PER_MSG * B_PER_MSG / 1024 ** 3
        heavy.append((ch, gb, est))
    if heavy:
        say("heaviest channels, and what a stage needs in RAM to read one:")
        for ch, gb, est in heavy:
            say(f"    {ch:<24}{human(gb * 1024**3):>10} on disk"
                f"   ~{est:.1f} GB peak")
        worst = max(e for _, _, e in heavy)
        if worst > 3.0:
            say(f"*** the largest is ~{worst:.1f} GB in RAM. Stages run one at "
                f"a time, so that is the peak -- but if this machine has less "
                f"than about {worst*2:.0f} GB free, expect a stage to die or "
                f"the box to swap itself to death. Re-run with --skip go and "
                f"tell me rather than assuming the data is bad.")

    try:
        free = shutil.disk_usage(ctx["data_root"]).free
        days = free / (4.57 * 1024 ** 3)
        say(f"disk free   {human(free)}  (~{days:.1f} days at the measured "
            f"4.57 GB/day; the watchdog halts below 5 GB)")
        if free < 8 * 1024 ** 3:
            say("*** LOW DISK. feed_data is irreplaceable -- exchange sockets "
                "have no backfill. Prune kalshi_data first; Kalshi's REST "
                "history can rebuild most of it.")
    except OSError:
        pass

    try:
        import requests                                   # noqa: F401
        say("requests    installed (chain + fulltape stages need it)")
    except ImportError:
        say("requests    MISSING -- the chain and fulltape stages need it")
        if ctx["install"]:
            say("installing it now ...")
            rc, out, _ = run(["-m", "pip", "install", "requests"], REPO, 600,
                             "pip")
            say("pip " + ("ok" if rc == 0 else f"FAILED (exit {rc})"))
            if rc:
                LOG.append("```\n" + out[-1500:] + "\n```")
        else:
            say(f"install it with:  {sys.executable} -m pip install requests")
    return True


COLLECTORS = ("kalshi_collector.py", "crypto_feeds.py")


def _sha(path):
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def step_sync(ctx):
    """Is the code the watchdog actually launches the code in this repo?

    run_all.ps1 does `Set-Location C:\kals` and starts `python
    kalshi_collector.py`, so it runs the copies sitting NEXT TO THE DATA --
    not the repo at C:\kals-repo. A `git pull` updates the repo and changes
    nothing about what is recording. Every collector fix this project has
    made could have been sitting unused, and nothing in the run would have
    said so.
    """
    rule("0c  COLLECTOR CODE -- is the running copy the repo's copy?")
    root = ctx.get("data_root")
    if not root or os.path.abspath(root) == os.path.abspath(REPO):
        say("data and repo are the same directory; nothing can drift.")
        return True

    drift = []
    for name in COLLECTORS:
        live, mine = os.path.join(root, name), os.path.join(REPO, name)
        if not os.path.exists(mine):
            say(f"{name:<24} not in this repo -- skipped")
            continue
        if not os.path.exists(live):
            say(f"{name:<24} *** MISSING from {root} ***")
            drift.append((name, live, mine, "missing"))
            continue
        a, b = _sha(live), _sha(mine)
        if a == b:
            say(f"{name:<24} identical to the repo")
        else:
            say(f"{name:<24} *** DIFFERENT from the repo ***")
            drift.append((name, live, mine, "stale"))

    if not drift:
        say("The watchdog is running this repo's code.")
        return True

    say("")
    say("The watchdog launches the copies under " + root + ", so these fixes")
    say("are NOT running. They take effect only after the file is replaced")
    say("AND the collector process restarts.")
    if not ctx.get("sync"):
        say("")
        say("Re-run with --sync-collectors to copy them (each is backed up")
        say("to .bak first, and is copied only if its own self-test passes),")
        say("or copy by hand:")
        for name, live, mine, _why in drift:
            say(f'    copy /Y "{mine}" "{live}"')
        return True

    for name, live, mine, _why in drift:
        # Never overwrite the code that produces unrecoverable data with code
        # that has not proved it runs. A gate is cheap; a collector that dies
        # on import at 03:00 is not.
        #
        # Not every collector has a --selftest, and "no self-test" must not
        # mean "never sync" -- that would quietly pin the file forever. Where
        # there is one, run it; where there is not, at least prove the file
        # compiles, and say which gate was used rather than implying the
        # stronger one.
        try:
            has_st = "--selftest" in open(mine, encoding=ENC,
                                          errors="replace").read()
        except OSError:
            has_st = False
        if has_st:
            gate, cmd = "self-test", [mine, "--selftest"]
        else:
            gate, cmd = "compile check", ["-m", "py_compile", mine]
        rc, out, _dt = run(cmd, REPO, 600, f"{name} {gate}")
        if rc != 0:
            say(f"{name}: {gate} FAILED (exit {rc}) -- NOT copied")
            tail = (out or "").strip().splitlines()
            if tail:
                say("    " + tail[-1][:120])
            continue
        say(f"{name}: {gate} passed")
        if os.path.exists(live):
            bak = live + ".bak"
            if not os.path.exists(bak):
                shutil.copy2(live, bak)
                say(f"{name}: backed up to {bak}")
        shutil.copy2(mine, live)
        ok = _sha(live) == _sha(mine)
        say(f"{name}: copied, hashes {'match' if ok else '*** STILL DIFFER ***'}")
        if not ok:
            return False
    say("")
    say("Copied. The RUNNING processes still hold the old code -- restart the")
    say("watchdog when you are at the machine for this to take effect.")
    return True


def step_collection(ctx):
    rule("1  COLLECTION -- the only step where waiting costs something")
    say("KXCRYPTOLEAD15M and KXCRYPTOCOMP15M price RELATIVE performance, so "
        "their price depends on the correlation between two coins. Inverting "
        "it gives implied correlation, and realized correlation is measurable "
        "from feeds we already record. Right now we record neither.")

    ps = os.path.join(ctx["data_root"], "run_all.ps1")
    if not os.path.exists(ps):
        ps = os.path.join(REPO, "run_all.ps1")
    if not os.path.exists(ps):
        say("*** run_all.ps1 not found; add --series by hand:")
        say("    " + " ".join(CRYPTO_15M + COMPARISON))
        return True

    # newline="" on BOTH sides: text mode would otherwise translate their
    # CRLF line endings to LF and rewrite every line of the file, turning a
    # one-line change into a whole-file diff
    src = open(ps, encoding=ENC, errors="replace", newline="").read()
    if all(s in src for s in COMPARISON):
        say(f"{ps}: already subscribes to both comparison series. Nothing to "
            f"do.")
        return True
    if "kalshi_collector.py" not in src:
        say(f"*** {ps} does not look like the watchdog; not touching it.")
        return True

    bak = ps + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(ps, bak)
        say(f"backed up  {bak}")

    series = " ".join(CRYPTO_15M + COMPARISON)
    out, patched = [], False
    for line in src.splitlines(True):
        if "kalshi_collector.py" in line and "--series" not in line \
                and not patched:
            # append inside the existing quoted argument string
            i = line.rfind('"')
            if i > 0:
                line = line[:i] + f" --series {series}" + line[i:]
                patched = True
        out.append(line)
    if not patched:
        say("*** could not find the collector's argument string to patch. "
            "Add this by hand:")
        say(f"    --series {series}")
        return True

    # tmp + replace: a truncating open() here means a Ctrl+C at the wrong
    # instant leaves the watchdog empty, and the .bak is the only thing
    # standing between that and no recording at all.
    with open(ps + ".tmp", "w", encoding=ENC, newline="") as fh:
        fh.write("".join(out))
    os.replace(ps + ".tmp", ps)

    # Verify rather than announce. The patch inserts before the last quote on
    # the first line mentioning the collector; if that line were ever a
    # comment, or the quoting differed, the message would be a lie.
    check = open(ps, encoding=ENC, errors="replace", newline="").read()
    good = [ln for ln in check.splitlines()
            if "kalshi_collector.py" in ln and "--series" in ln
            and not ln.lstrip().startswith("#")
            and all(t in ln for t in COMPARISON)]
    if not good:
        say(f"*** the patch did not take. {bak} is intact -- restore it and "
            f"add this by hand:")
        say(f"    --series {series}")
        return False
    say(f"patched    {ps}  (+2 series; original kept as .bak; verified)")
    say("")
    say("THIS DOES NOT TAKE EFFECT UNTIL THE WATCHDOG RESTARTS. I have not "
        "killed it -- stopping your recorder unattended is not a risk worth "
        "taking. When you are ready, in the watchdog window: Ctrl+C, then")
    say(f"    powershell -ExecutionPolicy Bypass -File {ps}")
    say("Disk cost is small: two more series against twelve.")
    return True


def step_api(ctx):
    rule("2  API -- read-only, public, no key, no order")
    outdir = ctx["outdir"]
    probes = [
        ("series_fin.json", f"{API}/series?category=Financials",
         "fee multiplier for S&P / Nasdaq. PLAN says 0.035 against crypto's "
         "0.07. If those series have gained a short cadence, the cost bar "
         "halves and the set of edges that clears it roughly doubles. "
         "NOTE: /series?category= is coded in this repo but has never been "
         "observed returning data, so an empty result here may be the "
         "endpoint, not the answer."),
        ("series_crypto.json", f"{API}/series?category=Crypto",
         "the crypto fee multiplier, to compare against."),
        ("comp.json",
         f"{API}/markets?series_ticker=KXCRYPTOCOMP15M&status=settled&limit=2",
         "the REAL contract terms. I will not write the correlation model "
         "against my reconstruction of them."),
        ("lead.json",
         f"{API}/markets?series_ticker=KXCRYPTOLEAD15M&status=settled&limit=2",
         "same, for the lead series."),
    ]
    got = 0
    for name, url, why in probes:
        try:
            js, raw = get_json(url)
        except (RuntimeError, ValueError, OSError) as e:
            say(f"{name:<20} FAILED  {e}")
            continue
        with open(os.path.join(outdir, name), "wb") as f:
            f.write(raw)
        say(f"{name:<20} {human(len(raw)):>10}   {why}")
        ctx["api"][name] = js
        got += 1

    # ---- what the fee data actually says
    for tag in ("series_fin.json", "series_crypto.json"):
        js = ctx["api"].get(tag)
        if not js:
            continue
        rows = js.get("series") or []
        say("")
        say(f"{tag}: {len(rows)} series")
        if not rows:
            say("    EMPTY. /series?category= has never been seen returning "
                "data from this repo -- treat this as 'endpoint unconfirmed', "
                "not 'no such series'. Raw response is in the zip.")
            continue
        short = []
        for s in rows:
            tk = str(s.get("ticker", ""))
            fm = s.get("fee_multiplier")
            if any(k in tk.upper() for k in ("15M", "30M", "1H", "HOURLY")):
                short.append((tk, fm, s.get("title", "")[:48]))
        mults = sorted({s.get("fee_multiplier") for s in rows
                        if s.get("fee_multiplier") is not None})
        say(f"    fee multipliers present: {mults}")
        if short:
            say(f"    SHORT-CADENCE SERIES ({len(short)}):")
            for tk, fm, ti in short[:40]:
                say(f"      {tk:<24} fee_multiplier={fm}   {ti}")
        else:
            say("    no series with 15M/30M/1H in the ticker")

    # ---- the contract terms, which decide whether the correlation model is
    #      even writable
    for tag in ("comp.json", "lead.json"):
        js = ctx["api"].get(tag)
        if not js:
            continue
        mk = (js.get("markets") or [])
        say("")
        say(f"{tag}: {len(mk)} settled market(s)")
        for m in mk[:2]:
            for k in ("ticker", "event_ticker", "floor_strike", "cap_strike",
                      "expiration_value", "result", "open_time", "close_time"):
                if k in m:
                    say(f"      {k:<18} {m[k]}")
            rp = m.get("rules_primary")
            if rp:
                say("      rules_primary:")
                for chunk in [rp[i:i + 90] for i in range(0, len(rp), 90)]:
                    say(f"        {chunk}")
            say("      --")

    if got < len(probes):
        say("")
        say(f"*** {len(probes)-got} of {len(probes)} probes failed. These are "
            "public read-only endpoints, so a failure here is network or "
            "proxy, not permissions. Re-run with --only api once it is back.")
    return got > 0


def step_fulltape(ctx):
    rule("3  FULLTAPE -- refresh the settled-market outcomes")
    say("Several stages map tickers to strike and result through "
        "fulltape/markets.json. If it is stale, anything recorded since the "
        "last refresh has no outcome attached and is silently dropped.")
    ft = os.path.join(REPO, "kalshi_fulltape.py")
    if not os.path.exists(ft):
        ft = os.path.join(ctx["data_root"], "kalshi_fulltape.py")
    if not os.path.exists(ft):
        say("*** kalshi_fulltape.py not found; skipping")
        return True
    # --series explicitly: kalshi_fulltape.py defaults to THREE series
    # (BTC, ETH, SOL), so markets.json would carry outcomes for a quarter of
    # what the collector records and the other nine series would be silently
    # dropped by every stage that matches on outcome.
    say(f"pulling outcomes for all {len(CRYPTO_15M)} recorded series "
        f"(its own default is 3 of them, which would silently drop the rest)")
    rc, out, dt = run_stream([ft, "--data", ctx["kalshi_data"],
                              "--out", ctx["fulltape"], "--markets", "400",
                              "--series"] + CRYPTO_15M,
                             REPO, 7200, "fulltape")
    say(f"exit {rc} in {dt:.0f}s")
    ctx["raw"]["fulltape"] = out
    mj = os.path.join(ctx["fulltape"], "markets.json")
    if os.path.exists(mj):
        try:
            n = sum(len(v) for v in json.load(
                open(mj, encoding=ENC)).values())
            say(f"markets.json now holds {n:,} settled markets")
        except Exception as e:
            say(f"markets.json unreadable: {type(e).__name__}: {e}")
    return rc == 0


def step_go(ctx):
    rule("4  GO -- every self-test, then 13 stages. The long one.")
    say("A self-test failure stops the run before any real data is touched. "
        "That is deliberate: every large edge this project has produced so "
        "far was a measurement bug.")
    say("Streaming below: one line per self-test, then one per stage, so you "
        "can always tell work from a hang.")
    rc, out, dt = run_stream([os.path.join("research", "go.py"),
                              "--data", ctx["kalshi_data"],
                              "--out", ctx["fulltape"],
                              "--feeds", ctx["feed_data"]],
                             REPO, 36000, "go.py")
    say(f"exit {rc} in {dt/60:.1f} min")
    ctx["raw"]["go"] = out
    ctx["go_ok"] = (rc == 0)
    res = os.path.join(REPO, "RESULTS.md")
    if os.path.exists(res):
        say(f"wrote {res} ({human(os.path.getsize(res))})")
    return rc == 0


def step_power(ctx):
    rule("5  POWER -- what this much data could have detected at all")
    say("Runs after go, because go's chain stage writes the cache this sizes "
        "itself from. It is printed FIRST in the report, because a t of 1.4 "
        "means either 'no edge' or 'an edge we cannot see', and this is the "
        "only thing that tells those apart.")
    env_ok = ctx.get("go_ok")
    if env_ok:
        os.environ["KALS_SELFTESTED"] = "1"
        say("go.py's self-tests passed, so power.py will not repeat them "
            "(saves about seven minutes).")
    rc, out, dt = run_stream([os.path.join("research", "power.py"),
                              "--data", ctx["kalshi_data"],
                              "--cache", os.path.join(REPO,
                                                      "chain_cache.json")],
                             REPO, 3600, "power.py")
    os.environ.pop("KALS_SELFTESTED", None)
    say(f"exit {rc} in {dt/60:.1f} min")
    ctx["raw"]["power"] = out
    return rc == 0


def step_disk(ctx):
    """A fast, read-only disk census.

    Free space on this machine swung 71.5 -> 36.5 -> 44.7 GB in five hours
    while the recorded data grew ~100 MB/h, and the watchdog halts the
    collector below 5 GB. Whatever is taking that space is a threat to the
    recording, so the run should carry the evidence rather than leave it to be
    reconstructed later. The fast pass takes seconds; --deep is manual.
    """
    rule("0b  DISK")
    rc, out, dt = run_stream([os.path.join("research", "whatate.py"),
                              "--data", ctx.get("kalshi_data", ""),
                              "--feeds", ctx.get("feed_data", ""),
                              "--fulltape", ctx.get("fulltape", "")],
                             REPO, 900, "whatate.py")
    ctx["raw"]["disk"] = out
    say(f"exit {rc} in {dt:.0f}s")
    # Never fail the run on this. It is a diagnostic, and a machine that
    # refuses to enumerate one of these folders must not cost us a stage.
    return True


# ==========================================================================
# the report
# ==========================================================================
def write_report(ctx, status):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    p = []
    p.append(f"# kals — full run\n\n`{stamp}`  ·  "
             f"elapsed {int(time.time()-T0)//60} min\n")
    p.append("Produced by `research/everything.py`. Nothing here placed, "
             "amended or cancelled an order, and nothing under `kalshi_data/` "
             "or `feed_data/` was written to.\n")

    p.append("\n## Step status\n")
    p.append("| step | result |")
    p.append("|---|---|")
    for name, ok in status:
        p.append(f"| {name} | {'ok' if ok else '**FAILED / skipped**'} |")

    if ctx["raw"].get("power"):
        p.append("\n---\n\n## Detectability — read this before anything else\n")
        p.append("```\n" + ctx["raw"]["power"][-40000:] + "\n```\n")

    p.append("\n---\n\n## Run log\n")
    p.append("```\n" + "\n".join(LOG) + "\n```\n")

    for key, title in (("disk", "disk census"),
                       ("salvage", "gzip salvage survey"),
                       ("go", "go.py — self-tests and stages"),
                       ("fulltape", "kalshi_fulltape.py")):
        if ctx["raw"].get(key):
            p.append(f"\n---\n\n## {title}\n")
            p.append("```\n" + ctx["raw"][key][-120000:] + "\n```\n")

    p.append("\n---\n\n## How to read this\n\n"
             "- Any stage whose measured effect is smaller than its minimum "
             "detectable effect produced **no information** — positive or "
             "negative. It is not 'no edge found'.\n"
             "- `n` is a count of markets or close-time clusters, never "
             "trades.\n"
             "- One run emits several hundred t-statistics. The corrected bar "
             "is printed in the detectability section and it is a long way "
             "above 3.\n"
             "- Every large edge this project has produced so far was a "
             "measurement bug. Treat anything eye-catching as a bug until it "
             "survives its own null.\n")

    out = os.path.join(REPO, "REPORT.md")
    open(out, "w", encoding=ENC, newline="\n").write("\n".join(p))
    return out


def bundle(ctx, report):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    z = os.path.join(REPO, f"kals-report-{stamp}.zip")
    members = [report,
               os.path.join(REPO, "RESULTS.md"),
               os.path.join(REPO, "schema.json"),
               os.path.join(REPO, "chain_cache.json")]
    members += [os.path.join(ctx["outdir"], n) for n in
                ("series_fin.json", "series_crypto.json",
                 "comp.json", "lead.json")]
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in members:
            if os.path.exists(m):
                # chain_cache can be large and is not needed to read the
                # report; include it only if it is small enough to mail
                if m.endswith("chain_cache.json") and \
                        os.path.getsize(m) > 20 * 1024 ** 2:
                    continue
                zf.write(m, os.path.basename(m))
    return z


# ==========================================================================
def main():
    ap = argparse.ArgumentParser(
        description="Run everything. No arguments needed.")
    ap.add_argument("--data", default=None,
                    help="folder CONTAINING kalshi_data/ (default: found "
                         "automatically)")
    ap.add_argument("--only", action="append", default=None,
                    choices=["preflight", "collection", "api", "fulltape",
                             "go", "power", "disk", "sync"],
                    help="run only these steps (repeatable)")
    ap.add_argument("--skip", action="append", default=[],
                    choices=["collection", "api", "fulltape", "go", "power", "disk",
                             "sync"],
                    help="skip these steps (repeatable)")
    ap.add_argument("--sync-collectors", dest="sync", action="store_true",
                    help="replace the collector scripts next to the data with "
                         "this repo's, after each passes its own self-test. "
                         "Takes effect when the collector next restarts.")
    ap.add_argument("--no-install", dest="install", action="store_false",
                    help="do not pip install a missing dependency")
    a = ap.parse_args()

    # Our own stdout is the last unprotected encoder in the chain. The
    # children are forced to utf-8, but this process re-prints their output
    # and (in everything.py) Kalshi's rules_primary text verbatim -- external
    # legalese full of curly quotes and en-dashes. Redirect this to a file in
    # PowerShell and sys.stdout becomes cp1252, which cannot encode them.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("=" * 78, flush=True)
    print("  kals — everything", flush=True)
    print("  Nothing here places an order. Nothing here writes to "
          "kalshi_data/ or feed_data/.", flush=True)
    print("  Expect 30-60 minutes. Progress prints as it goes.", flush=True)
    print("=" * 78, flush=True)

    root, searched = find_data_root(a.data)
    ctx = {
        "data_root": root, "searched": searched, "install": a.install,
        "sync": a.sync,
        "api": {}, "raw": {}, "channels": {}, "go_ok": False,
        "outdir": REPO,
    }
    if root:
        ctx["kalshi_data"] = os.path.join(root, "kalshi_data")
        ctx["feed_data"] = os.path.join(root, "feed_data")
        ctx["fulltape"] = os.path.join(root, "fulltape")

    steps = [("preflight", step_preflight), ("disk", step_disk),
             ("sync", step_sync), ("collection", step_collection),
             ("api", step_api), ("fulltape", step_fulltape),
             ("go", step_go), ("power", step_power)]

    if root is None and (a.only and set(a.only) - {"preflight", "disk"}):
        print("\n  No kalshi_data/ found, so there is nothing for those steps "
              "to run on.", flush=True)
        print("  Looked in: " + ", ".join(searched), flush=True)
        print("  Pass it:   python research\\everything.py --data C:\\kals",
              flush=True)
        raise SystemExit(2)

    status = []
    for name, fn in steps:
        if a.only and name not in a.only:
            continue
        if name in a.skip:
            say(f"SKIPPED {name} (--skip)")
            status.append((name, False))
            continue
        try:
            ok = fn(ctx)
        except KeyboardInterrupt:
            say("*** interrupted. Writing what exists.")
            status.append((name, False))
            break
        except Exception as e:
            import traceback
            say(f"*** {name} raised {type(e).__name__}: {e}")
            LOG.append("```\n" + traceback.format_exc()[-3000:] + "\n```")
            ok = False
        status.append((name, bool(ok)))
        # written after EVERY step: an interrupted run still leaves something
        write_report(ctx, status)
        if name == "preflight" and not ok:
            say("*** cannot continue without the data directory.")
            break

    report = write_report(ctx, status)
    z = bundle(ctx, report)

    rule("DONE")
    for name, ok in status:
        print(f"    {name:<12} {'ok' if ok else 'FAILED / skipped'}",
              flush=True)
    print(flush=True)
    print(f"    SEND ME THIS ONE FILE:  {z}", flush=True)
    print(f"    (readable version:      {report})", flush=True)
    print(flush=True)


if __name__ == "__main__":
    main()
