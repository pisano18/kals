#!/usr/bin/env python3
r"""server_sync.py -- bring this laptop's results\ up to date from the trading server.

Since 2026-10-27 00:20 ET every live bot and the phone link run on the Ohio
server (AWS EC2, see C:\kals\server.json). The desktop app (pindesk.py) and the
Pin Deck (pindeck.py) read results\ on the machine they run on, and on the
laptop that folder stopped at 00:20 ET. This script copies over what changed
on the server, so both show the server's numbers without being changed
themselves.

ONE RUN IS TWO ROUND TRIPS:
  1. ssh   this file sends the server a small Python program on stdin (the
           SERVER SIDE block below) carrying the laptop's list of files: name,
           size, time and a fingerprint. The server works out what changed,
           packs it into one .tgz under C:\Users\<user>\sync\ (PowerShell
           mangles raw bytes on an ssh pipe, so nothing binary comes back on
           it), and prints one line naming the file. It also packs a snapshot
           of what only the server can see: is the pin bot's process alive,
           its stand-down flag, the watchdog and phone heartbeats, open bets,
           the python processes running, and the Bots tab's numbers
           (botstats.all_bots, read there).
  2. scp   the .tgz comes back and is unpacked here.

WHAT IS COPIED
  *.jsonl *.log *.out *.err   append-only logs. Only the bytes after the end of
          the laptop's copy, and only if the laptop's last 4 KB match the
          server's at the same place. If they do not (the server copy is
          shorter, or the two differ), the server's file is copied whole and
          the laptop's old copy is MOVED, never deleted, to
          results\_laptop_before_sync\. Copies end on a whole line.
  anything else   copied whole when its size or time differs and its content
          does too (same content, only the time differs: just the time).
NEVER TOUCHED ON THE LAPTOP
  *.stop *.pid *.heartbeat *.lock *.reset pinphone.update laptop_handover.*
          the laptop's own stand-down flags and process files; and what the
          laptop writes for itself (pindesk.log, pindeck.html, this script's
          files).
  A log this laptop has written since the move (00:20 ET) or since this
  script last wrote it is held: a paper test still running here owns it.
  Nothing on the laptop is ever deleted. Nothing on the server is written
  except the .tgz in the sync folder (the previous one is removed).

    python research\server_sync.py               # one sync, one line of summary
    python research\server_sync.py --dry-run     # what would come over; nothing written
    python research\server_sync.py --selftest

The desktop app runs it at open and every 2 minutes while it is open. A
one-line summary of every run goes to results\server_sync.log.
"""
import calendar
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

_HERE_FILE = os.path.abspath(globals().get("__file__") or sys.argv[0] or ".")
HERE = os.path.dirname(_HERE_FILE)
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
KALS = r"C:\kals"
CONFIG = os.path.join(KALS, "server.json")
STATE = os.path.join(KALS, "server_sync_state.json")
LOCK = os.path.join(KALS, "server_sync.lock")
LOG_NAME = "server_sync.log"
STATUS_NAME = "server_status.json"
BOTS_NAME = "server_bots.json"
BACKUP_DIR = "_laptop_before_sync"
# The laptop stopped writing its bots' logs at 00:19:08 ET on 10-27 (the
# handover); anything it wrote after this was written by something still
# running HERE, and that log is the laptop's own.
CUTOVER = calendar.timegm((2026, 10, 27, 4, 20, 0))
EVERY_S = 120
CREATE_NO_WINDOW = 0x08000000
SSH_TIMEOUT_S = 300
SCP_TIMEOUT_S = 900


# ===========================================================================
# ---- SERVER SIDE BEGIN ----
# Everything from here to SERVER SIDE END is ALSO sent to the server and run
# there by `python -`. It imports only the standard library (and, inside
# try, the server's own pinflat / pindesk / botstats) and uses nothing
# defined outside this block.
# ===========================================================================
import base64 as _b64          # noqa: E402
import fnmatch as _fnm         # noqa: E402
import glob as _glob           # noqa: E402
import hashlib as _hl          # noqa: E402
import io as _io               # noqa: E402
import json as _json           # noqa: E402
import os as _os               # noqa: E402
import shutil as _shutil       # noqa: E402
import subprocess as _sp       # noqa: E402
import sys as _sys             # noqa: E402
import tarfile as _tar         # noqa: E402
import time as _time           # noqa: E402
import zlib as _zlib           # noqa: E402

PROTO = 1
APPEND_EXT = (".jsonl", ".log", ".out", ".err")
TAIL = 4096                    # bytes fingerprinted at the end of a log
FULL_HASH_MAX = 8 << 20        # other files: hashed whole up to this size
WHOLE_MAX = 64 << 20           # a non-log file bigger than this is not copied
RUN_MAX = 400 << 20            # raw bytes per run; the rest comes on the next run
QUIET_S = 120                  # a log with no newline at its end is sent anyway once this quiet
NEVER = ("*.stop", "*.pid", "*.heartbeat", "*.lock", "*.reset", "*.tmp", "*.sync-tmp",
         "pinphone.update", "laptop_handover.*",
         # what the laptop writes for itself
         "server_sync*", "server_status.json", "server_bots.json",
         "pindesk.log", "pindesk.err", "pindeck.html")
READY = "SYNC-READY"
PLANNED = "SYNC-PLAN"


def is_never(name):
    """Names the sync never sends, never writes and never moves."""
    n = str(name).lower()
    return any(_fnm.fnmatch(n, g) for g in NEVER)


def is_append(name):
    return str(name).lower().endswith(APPEND_EXT)


def safe_name(name):
    """A plain file name in results\\ -- no folder, no '..', nothing hidden."""
    n = str(name or "")
    return (bool(n) and n == _os.path.basename(n) and "/" not in n and "\\" not in n
            and ":" not in n and n not in (".", "..") and not n.startswith("."))


def _sha(*parts):
    h = _hl.sha1()
    for p in parts:
        h.update(p)
    return h.hexdigest()[:20]


def tail_print(path, end):
    """Fingerprint of the TAIL bytes that end at byte `end` (None if the file is shorter)."""
    start = max(0, int(end) - TAIL)
    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            b = fh.read(int(end) - start)
    except OSError:
        return None
    if len(b) != int(end) - start:
        return None
    return _sha(b, b"|%d" % int(end))


def whole_print(path, size):
    """Fingerprint of a whole (non-log) file: all of it up to 8 MB, else its first and last MB."""
    try:
        with open(path, "rb") as fh:
            if size <= FULL_HASH_MAX:
                b = fh.read(size + 1)
                return _sha(b, b"|%d" % len(b))
            a = fh.read(1 << 20)
            fh.seek(max(0, size - (1 << 20)))
            z = fh.read(1 << 20)
            return _sha(a, z, b"|%d" % size)
    except OSError:
        return None


def plan(results, laptop, hold=()):
    """What the laptop needs, as a list of entries, and the files left out (name, why).

    `laptop` = {name: [size, mtime, fingerprint]} as the laptop sent it. An
    entry is {op: append|whole|touch, name, offset, upto, mtime, why}.
    """
    hold = set(hold or ())
    out, left = [], []
    try:
        scan = sorted(_os.scandir(results), key=lambda e: e.name)
    except OSError as e:
        return [], [("results", "cannot list %s: %s" % (results, e))]
    for e in scan:
        try:
            if not e.is_file():
                continue
            st = e.stat()
        except OSError:
            continue
        name = e.name
        if is_never(name) or not safe_name(name):
            continue
        if name in hold:
            left.append((name, "the laptop writes this log itself"))
            continue
        size, mtime, path = st.st_size, st.st_mtime, e.path
        lap = laptop.get(name)
        base = {"name": name, "mtime": mtime, "upto": size}
        if is_append(name):
            if lap:
                lsize, lmt, lpr = int(lap[0]), float(lap[1]), lap[2]
                if size == lsize and abs(mtime - lmt) < 1:
                    continue
                if size >= lsize and lpr and tail_print(path, lsize) == lpr:
                    if size == lsize:
                        out.append(dict(base, op="touch", offset=lsize, why="same"))
                    else:
                        out.append(dict(base, op="append", offset=lsize, why="grew"))
                    continue
                why = "shorter on the server" if size < lsize else "the two copies differ"
            else:
                why = "new"
            out.append(dict(base, op="whole", offset=0, why=why))
        else:
            if lap:
                lsize, lmt, lpr = int(lap[0]), float(lap[1]), lap[2]
                if size == lsize and abs(mtime - lmt) < 1:
                    continue
                if size == lsize and lpr and whole_print(path, size) == lpr:
                    out.append(dict(base, op="touch", offset=size, why="same"))
                    continue
            if size > WHOLE_MAX:
                left.append((name, "%.0f MB, too big for a whole copy" % (size / 1e6)))
                continue
            out.append(dict(base, op="whole", offset=0, why="new" if not lap else "changed"))
    return out, left


def _read_range(path, start, end):
    with open(path, "rb") as fh:
        fh.seek(start)
        return fh.read(max(0, end - start))


def _piece(ent, results, now):
    """The bytes for one entry, ending on a whole line for a log. None = nothing to send yet."""
    path = _os.path.join(results, ent["name"])
    if ent["op"] == "touch":
        return b""
    data = _read_range(path, ent["offset"], ent["upto"])
    if is_append(ent["name"]):
        cut = data.rfind(b"\n")
        if cut < 0:
            if now - ent["mtime"] < QUIET_S or not data:
                return None
        else:
            data = data[:cut + 1]
    elif ent["name"].lower().endswith(".json") and data:
        for _ in range(2):                         # a cache caught mid-write: read it once more
            try:
                _json.loads(data.decode("utf-8-sig"))
                break
            except ValueError:
                _time.sleep(0.3)
                try:
                    data = _read_range(path, 0, _os.path.getsize(path))
                    ent["upto"] = len(data)
                    ent["mtime"] = _os.path.getmtime(path)
                except OSError:
                    return None
        else:
            return None
    return data


def build(results, req, out_path, now=None, facts=None):
    """Plan, read and pack. Writes the .tgz at out_path; returns the summary dict."""
    now = _time.time() if now is None else now
    entries, left = plan(results, req.get("files") or {}, req.get("hold") or ())
    budget = int(req.get("budget") or RUN_MAX)
    # small first: every small change comes through even when one big log is catching up
    entries.sort(key=lambda x: (x["upto"] - x["offset"]) if x["op"] != "touch" else -1)
    sent, deferred, used = [], [], 0
    blobs = []
    for ent in entries:
        try:
            data = _piece(ent, results, now)
        except OSError as e:
            left.append((ent["name"], "could not read: %s" % e))
            continue
        if data is None:
            continue
        if ent["op"] != "touch" and used and used + len(data) > budget:
            deferred.append(ent["name"])
            continue
        if ent["op"] != "touch" and not data and ent["op"] == "append":
            continue
        ent["len"] = len(data)
        ent["size"] = (ent["offset"] + len(data)) if ent["op"] == "append" else (
            len(data) if ent["op"] == "whole" else ent["offset"])
        if ent["op"] != "touch":
            ent["member"] = "d/%05d" % len(blobs)
            blobs.append((ent["member"], data))
            used += len(data)
        sent.append(ent)
    summary = {"proto": PROTO, "at": now, "entries": sent, "left": left[:200], "n_left": len(left),
               "deferred": deferred, "raw": used}
    if not req.get("dry"):
        meta = dict(summary, facts=facts if facts is not None else {})
        tmp = out_path + ".part"
        with _tar.open(tmp, "w:gz", compresslevel=6) as tf:
            for name, data in [("plan.json", _json.dumps(meta, default=str).encode("utf-8"))] + blobs:
                ti = _tar.TarInfo(name)
                ti.size = len(data)
                ti.mtime = int(now)
                tf.addfile(ti, _io.BytesIO(data))
        _os.replace(tmp, out_path)
    return summary


def _below_normal():
    """Never compete with the bots for the CPU: this process and its children run below normal."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)
    except Exception:                                              # noqa: BLE001
        pass


def server_facts(repo, results, now=None):
    """What only the server can see: the pin bot's process, its flag, heartbeats, open bets, processes."""
    now = _time.time() if now is None else now
    f = {"at": now, "errors": []}
    research = _os.path.join(repo, "research")
    if research not in _sys.path:
        _sys.path.insert(0, research)

    def age(p):
        try:
            return max(0.0, now - _os.path.getmtime(p))
        except OSError:
            return None
    try:
        import socket
        f["host"] = socket.gethostname()
    except Exception:                                              # noqa: BLE001
        pass
    pidfile = _os.path.join(results, "pinrun-live.pid")
    try:
        import pinflat
        pid = pinflat.live_pid(pidfile)
        f["pid"], f["alive"] = pid, bool(pid) and bool(pinflat.pid_alive(pid))
    except Exception as e:                                         # noqa: BLE001
        f["errors"].append("process: %s" % e)
        pinflat = None
    try:
        with open(_os.path.join(results, "pinrun-live.stop"), encoding="utf-8") as fh:
            f["flag"] = fh.read().strip() or "(no reason)"
    except OSError:
        f["flag"] = None
    f["watchdog_s"] = age(_os.path.join(results, "watch_bot.heartbeat"))
    f["phone_s"] = age(_os.path.join(results, "pinphone.heartbeat"))
    lives = _glob.glob(_os.path.join(results, "pinrun-live-*.jsonl"))
    newest = max(lives, key=_os.path.getmtime) if lives else None
    ages = [a for a in (age(newest) if newest else None, age(_os.path.join(results, "pinrun-live.out")))
            if a is not None]
    f["quiet_s"] = min(ages) if ages else None
    if pinflat is not None:
        try:
            st, d = pinflat.check(results=results, pidfile=pidfile)
            f["flat"], f["open"] = st, d.get("open") or {}
        except Exception as e:                                     # noqa: BLE001
            f["flat"], f["open"] = "UNKNOWN", {}
            f["flat_err"] = str(e)[:120]
    try:
        import pindesk as _pd
        if f.get("alive") and newest:
            f["blind"] = _pd.blind_of(_pd.tail_rows(newest), now)
        f["ram_gb"] = _pd._ram_free_gb()
    except Exception as e:                                         # noqa: BLE001
        f["errors"].append("pindesk: %s" % str(e)[:120])
    try:
        f["disk_gb"] = _shutil.disk_usage(_os.path.splitdrive(results)[0] + "\\").free / 1e9
    except Exception:                                              # noqa: BLE001
        f["disk_gb"] = None
    try:
        f["stops"] = sorted(n for n in _os.listdir(results) if n.lower().endswith(".stop"))
    except OSError:
        f["stops"] = None
    try:
        r = _sp.run(["powershell.exe", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                     "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"],
                    capture_output=True, text=True, timeout=30, creationflags=0x08000000)
        procs = []
        for line in (r.stdout or "").splitlines():
            pid, _t, cl = line.partition("\t")
            if cl.strip() and pid.strip().isdigit():
                procs.append([int(pid.strip()), cl.strip()])
        f["procs"] = procs
    except Exception as e:                                         # noqa: BLE001
        f["procs"] = None
        f["errors"].append("process list: %s" % str(e)[:120])
    return f


def server_bots(repo):
    """The Bots tab's numbers, read on the server (botstats.all_bots: the same call the app made)."""
    research = _os.path.join(repo, "research")
    if research not in _sys.path:
        _sys.path.insert(0, research)
    t = _time.time()
    try:
        import botstats
        a = botstats.all_bots()
        return {"at": t, "secs": round(_time.time() - t, 2), "all": a}
    except Exception as e:                                         # noqa: BLE001
        return {"at": t, "secs": round(_time.time() - t, 2), "error": "%s: %s" % (type(e).__name__, str(e)[:200])}


def server_main(payload):
    """Run on the server. Packs what the laptop needs and prints one READY line naming the .tgz."""
    t0 = _time.time()
    req = _json.loads(_zlib.decompress(_b64.b64decode(payload)).decode("utf-8"))
    _below_normal()
    results, repo, out_dir = req["results"], req["repo"], req["out_dir"]
    if req.get("dry"):
        s = build(results, req, None)
        n = {"append": 0, "whole": 0, "touch": 0}
        for e in s["entries"]:
            n[e["op"]] += 1
        print("%s %s" % (PLANNED, _json.dumps({"n": n, "raw": s["raw"], "deferred": len(s["deferred"]),
                                                "n_left": s["n_left"], "left": s["left"][:40],
                                                "big": sorted(((e["len"], e["op"], e["name"], e["why"])
                                                               for e in s["entries"]), reverse=True)[:40],
                                                "secs": round(_time.time() - t0, 2)})))
        return 0
    _os.makedirs(out_dir, exist_ok=True)
    for old in _glob.glob(_os.path.join(out_dir, "delta-*.tgz*")):
        try:
            _os.remove(old)
        except OSError:
            pass
    facts = {}
    if req.get("facts", True):
        try:
            facts = server_facts(repo, results)
        except Exception as e:                                     # noqa: BLE001
            facts = {"at": _time.time(), "errors": ["facts: %s" % e]}
    if req.get("bots", True):
        facts["bots"] = server_bots(repo)
    stamp = _time.strftime("%Y%m%dT%H%M%SZ", _time.gmtime())
    out = _os.path.join(out_dir, "delta-%s.tgz" % stamp)
    s = build(results, req, out, facts=facts)
    small = {"n": len(s["entries"]), "raw": s["raw"], "deferred": len(s["deferred"]),
             "secs": round(_time.time() - t0, 2)}
    print("%s %s %d %s" % (READY, out, _os.path.getsize(out), _json.dumps(small)))
    _sys.stdout.flush()
    return 0
# ---- SERVER SIDE END ----


# ===========================================================================
# LAPTOP SIDE
# ===========================================================================
class SyncError(RuntimeError):
    pass


def load_config(path=None):
    """C:\\kals\\server.json as a dict, None when absent. Raises SyncError when present but unreadable."""
    p = path or CONFIG
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8-sig") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        raise SyncError("%s cannot be read: %s" % (p, e))
    if not isinstance(d, dict) or not d.get("host") or not d.get("user") or not d.get("key"):
        raise SyncError("%s needs host, user and key" % p)
    d.setdefault("python", r"C:\Python314\python.exe")
    d.setdefault("repo", r"C:\kals-repo")
    return d


def _exe(name):
    """Windows' own OpenSSH when it is there (the desktop shortcut's PATH may put another first)."""
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", name + ".exe")
    return p if os.path.exists(p) else name


def ssh_base(cfg):
    """ssh argv up to and including user@host. BatchMode: it never stops to ask anything."""
    return [_exe("ssh"), "-i", cfg["key"], "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=8",
            "%s@%s" % (cfg["user"], cfg["host"])]


def remote_dir(cfg):
    return cfg.get("sync_dir") or ("C:\\Users\\%s\\sync" % cfg["user"])


def scp_cmd(cfg, remote, local):
    return [_exe("scp"), "-i", cfg["key"], "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-q",
            "%s@%s:%s" % (cfg["user"], cfg["host"], remote.replace("\\", "/")), local]


def server_program(payload):
    """The SERVER SIDE block of this file plus the one call that runs it."""
    with open(_HERE_FILE, encoding="utf-8") as fh:
        src = fh.read()
    a = src.index("# ---- SERVER SIDE BEGIN ----")
    b = src.index("# ---- SERVER SIDE END ----")
    return src[a:b] + "\n_sys.exit(server_main(%r))\n" % payload


def load_state(path=None):
    try:
        with open(path or STATE, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state, path=None):
    p = path or STATE
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, separators=(",", ":"))
    os.replace(tmp, p)


def expected_after(meta_entries, sent):
    """{name: [size, mtime]} each file will have once its entry is applied (the journal)."""
    out = {}
    for e in meta_entries:
        n = e.get("name")
        if e.get("op") == "touch":
            out[n] = [int((sent.get(n) or [0])[0]), float(e["mtime"])]
        elif e.get("op") in ("append", "whole"):
            out[n] = [int(e.get("size") or 0), float(e["mtime"])]
    return out


def recover_journal(state, results, path):
    """A sync that died half way (the app closed mid-unpack): adopt every file the journal says
    it was writing that now has exactly the size and time it was going to have. Without this,
    those files would look written by the laptop and be held for good."""
    try:
        with open(path, encoding="utf-8") as fh:
            pend = json.load(fh)
    except (OSError, ValueError):
        return 0
    n = 0
    for name, (sz, mt) in (pend or {}).items():
        try:
            st = os.stat(os.path.join(results, name))
        except OSError:
            continue
        if st.st_size == int(sz) and abs(st.st_mtime - float(mt)) <= 1:
            state[name] = [int(sz), float(mt)]
            n += 1
    try:
        os.remove(path)
    except OSError:
        pass
    return n


def laptop_owned(name, size, mtime, state, cutover=CUTOVER):
    """Is this log being written HERE? Then the laptop's copy is its own and is never replaced."""
    if not is_append(name):
        return False
    s = state.get(name)
    if s is not None:
        if s[0] == "held":                 # a laptop process had it open when the sync tried it
            return True
        return int(s[0]) != int(size) or abs(float(s[1]) - float(mtime)) > 1
    return float(mtime) > cutover


def manifest(results, state, cutover=CUTOVER):
    """({name: [size, mtime, fingerprint]}, [names held because the laptop writes them])."""
    files, hold = {}, []
    for e in os.scandir(results):
        try:
            if not e.is_file():
                continue
            st = e.stat()
        except OSError:
            continue
        name = e.name
        if is_never(name):
            continue
        if laptop_owned(name, st.st_size, st.st_mtime, state, cutover):
            hold.append(name)
            continue
        fp = tail_print(e.path, st.st_size) if is_append(name) else whole_print(e.path, st.st_size)
        files[name] = [st.st_size, st.st_mtime, fp]
    return files, sorted(hold)


def _replace(src, dst, tries=10):
    for k in range(tries):
        try:
            os.replace(src, dst)
            return True
        except PermissionError:
            time.sleep(0.2 * (k + 1))
    return False


def _write_json(path, obj):
    tmp = path + ".sync-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, default=str)
    if not _replace(tmp, path):
        try:
            os.remove(tmp)
        except OSError:
            pass


def apply_package(pkg, results, state, sent, now=None, journal=None):
    """Unpack one .tgz into results\\. Returns the counts. Never deletes; never writes a NEVER name.

    `journal`: a file written BEFORE anything is applied, naming the size and time every file will
    have, so a run killed half way can be told from a laptop process (recover_journal)."""
    now = time.time() if now is None else now
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))
    r = {"append": 0, "whole": 0, "touch": 0, "skipped": [], "replaced": [], "moved": [], "bytes": 0,
         "held_now": []}
    with tarfile.open(pkg, "r:gz") as tf:
        meta = json.loads(tf.extractfile("plan.json").read().decode("utf-8"))
        if journal:
            with open(journal, "w", encoding="utf-8") as fh:
                json.dump(expected_after(meta.get("entries") or [], sent), fh)
        for ent in meta.get("entries") or []:
            name = ent.get("name")
            if not safe_name(name) or is_never(name):
                r["skipped"].append((name, "not a name the sync may write"))
                continue
            path = os.path.join(results, name)
            try:
                cur = os.stat(path)
            except OSError:
                cur = None
            want = sent.get(name)
            # the laptop's copy must still be the one the server planned against
            if want is None:
                if cur is not None:
                    r["skipped"].append((name, "appeared on the laptop during the sync"))
                    continue
            elif cur is None or cur.st_size != int(want[0]) or abs(cur.st_mtime - float(want[1])) > 1:
                r["skipped"].append((name, "changed on the laptop during the sync"))
                continue
            mt = float(ent["mtime"])
            op = ent.get("op")
            try:
                if op == "touch":
                    os.utime(path, (mt, mt))
                    state[name] = [cur.st_size, mt]
                    r["touch"] += 1
                    continue
                data = tf.extractfile(ent["member"]).read()
                if len(data) != int(ent["len"]):
                    r["skipped"].append((name, "damaged in transit"))
                    continue
                if op == "append":
                    with open(path, "r+b") as fh:
                        fh.seek(0, 2)
                        if fh.tell() != int(ent["offset"]):
                            r["skipped"].append((name, "the laptop copy is not where the server thought"))
                            continue
                        fh.write(data)
                    os.utime(path, (mt, mt))
                    state[name] = [int(ent["offset"]) + len(data), mt]
                    r["append"] += 1
                elif op == "whole":
                    tmp = path + ".sync-tmp"
                    with open(tmp, "wb") as fh:
                        fh.write(data)
                    os.utime(tmp, (mt, mt))
                    if cur is not None and is_append(name) and cur.st_size > 0 and name not in state:
                        # the laptop's copy has bytes the server's lacks: keep them, moved aside
                        # (a copy this sync wrote itself is only the server's old bytes: no need)
                        bdir = os.path.join(results, BACKUP_DIR)
                        os.makedirs(bdir, exist_ok=True)
                        bpath = os.path.join(bdir, "%s.%s" % (name, stamp))
                        if not _replace(path, bpath, tries=3):
                            # a process HERE has it open, so it is writing it: the laptop's from now on
                            os.remove(tmp)
                            state[name] = ["held", now]
                            r["held_now"].append(name)
                            continue
                        r["moved"].append(name)
                    if not _replace(tmp, path):
                        os.remove(tmp)
                        r["skipped"].append((name, "in use on the laptop"))
                        continue
                    state[name] = [len(data), mt]
                    r["whole"] += 1
                    if cur is not None:
                        r["replaced"].append(name)
                else:
                    r["skipped"].append((name, "unknown op %r" % op))
                    continue
                r["bytes"] += len(data)
            except OSError as e:
                r["skipped"].append((name, "could not write: %s" % e))
        facts = meta.get("facts") or {}
    bots = facts.pop("bots", None) if isinstance(facts, dict) else None
    if facts:
        _write_json(os.path.join(results, STATUS_NAME), facts)
    if bots:
        _write_json(os.path.join(results, BOTS_NAME), bots)
    r["deferred"] = len(meta.get("deferred") or [])
    r["n_left"] = meta.get("n_left", 0)
    return r


def _run(cmd, timeout, inp=None):
    try:
        p = subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        raise SyncError("%s gave no answer in %d s" % (cmd[0], timeout))
    except OSError as e:
        raise SyncError("could not run %s: %s" % (cmd[0], e))
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _short(err):
    e = " ".join(str(err).split())
    low = e.lower()
    if "timed out" in low or "could not resolve" in low or "no route" in low or "unreachable" in low \
            or "connection refused" in low or "connection reset" in low or "closed by remote" in low:
        return "could not reach the server (%s)" % e[:90]
    if "permission denied" in low:
        return "the server refused the key (%s)" % e[:90]
    return e[:160]


def _pid_alive(pid):
    """Does this process exist? (pinflat.pid_alive's rule: YES when it cannot tell.)"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x00100000, False, pid)
        if h:
            k.CloseHandle(h)
            return True
        return k.GetLastError() == 5
    except Exception:                                              # noqa: BLE001
        return True


def _lock(path):
    """One sync at a time on this laptop. Returns a release function, or None if one is running.
    A lock left by a sync whose process is gone (the app closed mid-sync) is taken over."""
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("%d %d" % (os.getpid(), time.time())).encode())
            os.close(fd)

            def release():
                try:
                    os.remove(path)
                except OSError:
                    pass
            return release
        except FileExistsError:
            try:
                with open(path, encoding="utf-8") as fh:
                    owner = (fh.read().split() or ["0"])[0]
                if (owner.isdigit() and int(owner) != os.getpid() and not _pid_alive(owner)) \
                        or time.time() - os.path.getmtime(path) > 900:     # a sync that died holding it
                    os.remove(path)
                    continue
            except OSError:
                continue
            return None
    return None


def _log_line(results, text, now=None):
    now = time.time() if now is None else now
    try:
        sys.path.insert(0, HERE)
        from downtime import et_offset
        stamp = time.strftime("%Y-%m-%d %H:%M:%S ET", time.gmtime(now + et_offset(now)))
    except Exception:                                              # noqa: BLE001
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    try:
        with open(os.path.join(results, LOG_NAME), "a", encoding="utf-8") as fh:
            fh.write("%s  %s\n" % (stamp, text))
    except OSError:
        pass


def _mb(n):
    return "%.2f MB" % (n / 1e6)


def sync_once(cfg=None, results=None, state_path=None, lock_path=None, dry_run=False, log=True):
    """One sync. Returns a summary dict; never raises. `ok` False means nothing on the laptop changed."""
    t0 = time.time()
    results = results or RESULTS
    out = {"ok": False, "at": t0, "err": None, "append": 0, "whole": 0, "touch": 0, "bytes": 0,
           "wire": 0, "replaced": [], "held": 0, "deferred": 0, "secs": 0.0}
    release = None
    tmpdir = None
    try:
        cfg = cfg or load_config()
        if not cfg:
            raise SyncError("no %s: this computer is not set up to read a server" % CONFIG)
        release = _lock(lock_path or LOCK)
        if release is None:
            out["err"] = "another sync is already running"
            out["busy"] = True
            return out
        state = load_state(state_path)
        jpath = (state_path or STATE) + ".pending"
        if recover_journal(state, results, jpath):
            save_state(state, state_path)
        files, hold = manifest(results, state)
        out["held"] = len(hold)
        req = {"results": cfg["repo"].rstrip("\\") + "\\results", "repo": cfg["repo"],
               "out_dir": remote_dir(cfg), "files": files, "hold": hold, "dry": bool(dry_run)}
        import base64
        import zlib
        payload = base64.b64encode(zlib.compress(json.dumps(req, separators=(",", ":")).encode("utf-8"), 6)).decode()
        prog = server_program(payload).encode("utf-8")
        cmd = ssh_base(cfg) + ["& '%s' -" % cfg["python"]]
        code, so, se = _run(cmd, SSH_TIMEOUT_S, prog)
        lines = [l for l in so.splitlines() if l.startswith((READY, PLANNED))]
        if code != 0 or not lines:
            raise SyncError(_short(se.strip() or so.strip() or "ssh exit %d" % code))
        head = lines[-1]
        if dry_run:
            out["plan"] = json.loads(head.split(" ", 1)[1])
            out["ok"] = True
            return out
        _tag, rpath, nbytes, small = head.split(" ", 3)
        out["wire"] = int(nbytes)
        out["server_secs"] = json.loads(small).get("secs")
        tmpdir = tempfile.mkdtemp(prefix="kals_sync_")
        local = os.path.join(tmpdir, os.path.basename(rpath.replace("\\", "/")))
        code, so, se = _run(scp_cmd(cfg, rpath, local), SCP_TIMEOUT_S)
        if code != 0 or not os.path.exists(local) or os.path.getsize(local) != int(nbytes):
            raise SyncError("the download failed: " + _short(se.strip() or "scp exit %d" % code))
        r = apply_package(local, results, state, files, journal=jpath)
        save_state(state, state_path)
        try:
            os.remove(jpath)
        except OSError:
            pass
        out["held"] += len(r["held_now"])
        out.update(ok=True, append=r["append"], whole=r["whole"], touch=r["touch"], bytes=r["bytes"],
                   replaced=r["replaced"], moved=r["moved"], skipped=r["skipped"], deferred=r["deferred"],
                   n_left=r["n_left"])
    except SyncError as e:
        out["err"] = str(e)
    except Exception as e:                                         # noqa: BLE001
        out["err"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
        if release:
            release()
        out["secs"] = round(time.time() - t0, 1)
        if log and not out.get("busy") and not dry_run:
            _log_line(results, summary_line(out), t0)
    return out


def summary_line(s):
    if not s.get("ok"):
        return "FAILED after %.1f s: %s" % (s.get("secs") or 0, s.get("err"))
    n = s["append"] + s["whole"]
    txt = "ok  %d file%s updated (%d added to, %d copied whole, %d time only), %s of data, %s over the wire, %.1f s" % (
        n, "" if n == 1 else "s", s["append"], s["whole"], s["touch"], _mb(s["bytes"]), _mb(s["wire"]), s["secs"])
    if s.get("server_secs") is not None:
        txt += " (server %.1f s)" % s["server_secs"]
    if s.get("held"):
        txt += "; %d log%s written on this laptop left alone" % (s["held"], "" if s["held"] == 1 else "s")
    if s.get("moved"):
        txt += "; laptop copies kept in results\\%s: %s" % (BACKUP_DIR, ", ".join(s["moved"][:6]))
    if s.get("deferred"):
        txt += "; %d more next run" % s["deferred"]
    if s.get("skipped"):
        txt += "; skipped %s" % ", ".join("%s (%s)" % (n_, w) for n_, w in s["skipped"][:4])
    return txt


class Syncer:
    """The desktop app's background sync: once now, then every EVERY_S, never on the interface thread."""

    def __init__(self, cfg=None, every=EVERY_S, on_done=None):
        self.cfg, self.every, self.on_done = cfg, every, on_done
        self.last = None                # the last summary
        self.last_ok = None             # time of the last good sync
        self.running = False
        self._wake = threading.Event()
        self._stop = False

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        return self

    def now(self):
        """Sync as soon as possible (the Refresh button, a button press on the server)."""
        self._wake.set()

    def _loop(self):
        while not self._stop:
            self.running = True
            try:
                s = sync_once(self.cfg)
            except Exception as e:                                 # noqa: BLE001
                s = {"ok": False, "err": str(e), "at": time.time()}
            self.running = False
            if not s.get("busy"):
                self.last = s
                if s.get("ok"):
                    self.last_ok = s.get("at")
            if self.on_done:
                try:
                    self.on_done(s)
                except Exception:                                  # noqa: BLE001
                    pass
            # another sync (a second window, or one run by hand) held the lock: try again soon
            self._wake.wait(15 if s.get("busy") else self.every)
            self._wake.clear()


# ===========================================================================
# self-test: planted files in temp folders, no network
# ===========================================================================
def selftest():
    def ck(cond, msg):
        if not cond:
            raise SystemExit("server_sync selftest: FAILED -- " + msg)

    def put(d, name, data, mtime=None):
        p = os.path.join(d, name)
        with open(p, "wb") as fh:
            fh.write(data)
        if mtime is not None:
            os.utime(p, (mtime, mtime))
        return p

    def get(d, name):
        with open(os.path.join(d, name), "rb") as fh:
            return fh.read()

    base = tempfile.mkdtemp(prefix="server_sync_test_")
    try:
        srv, lap, outd = (os.path.join(base, x) for x in ("server", "laptop", "out"))
        for d in (srv, lap, outd):
            os.makedirs(d)
        old = CUTOVER - 3600
        new = CUTOVER + 3600
        prefix = b"".join(b'{"n": %d, "pad": "%s"}\n' % (i, b"x" * 40) for i in range(300))
        # 1. a log that grew on the server, with a half-written last line
        put(lap, "pinrun-live-a.jsonl", prefix, old)
        put(srv, "pinrun-live-a.jsonl", prefix + b'{"n": 300}\n{"n": 301}\n{"n": 3', new)
        # 2. a log the two machines both wrote after the copy (they differ)
        put(lap, "ladder-live.jsonl", prefix + b'{"laptop": 1}\n', old)
        put(srv, "ladder-live.jsonl", prefix + b'{"server": 1}\n{"server": 2}\n', new)
        # 3. a log that is shorter on the server (rewritten there)
        put(lap, "watch_bot.log", b"line\n" * 500, old)
        put(srv, "watch_bot.log", b"fresh\n" * 3, new)
        # 4. a json cache that changed, and one with the same bytes and another time
        put(lap, "kalshi_ledger.json", b'{"v": 1}', old)
        put(srv, "kalshi_ledger.json", b'{"v": 2, "rows": [1, 2, 3]}', new)
        put(lap, "DOWNTIME.json", b'{"same": true}', old)
        put(srv, "DOWNTIME.json", b'{"same": true}', new)
        # 5. the laptop's own files: never copied, never touched
        for n_, data in (("pinrun-live.stop", b"laptop handover"), ("pinrun-live.pid", b"111"),
                         ("watch_bot.heartbeat", b"laptop"), ("pinphone.update", b"laptop"),
                         ("laptop_handover.log", b"laptop log\n"), ("pindesk.log", b"laptop desk\n")):
            put(lap, n_, data, old)
        for n_, data in (("pinrun-live.stop", b"SERVER flag"), ("pinrun-live.pid", b"999"),
                         ("watch_bot.heartbeat", b"server"), ("pinphone.update", b"server"),
                         ("laptop_handover.log", b"server log\n"), ("pindesk.log", b"server desk\n"),
                         ("fxtake-live.stop", b"server stop"), ("pinrun-hwm.reset", b"server")):
            put(srv, n_, data, new)
        # 6. a log a paper test on the LAPTOP is still writing: held, never replaced
        put(lap, "fc-fast-paper.jsonl", b'{"laptop": "own"}\n', new)
        put(srv, "fc-fast-paper.jsonl", b'{"server": "other"}\n' * 5, new)
        # 7. a laptop-only file, and a server-only new file
        put(lap, "only-on-laptop.jsonl", b'{"keep": 1}\n', old)
        put(srv, "pinrun-live-new.jsonl", b'{"n": 1}\n{"n": 2}\n', new)
        # 8. unchanged on both
        put(lap, "same.jsonl", prefix, old)
        put(srv, "same.jsonl", prefix, old)

        # 9. a log a laptop process holds open (Windows will not move it): held from then on
        put(lap, "rain-paper-stdout.log", b"laptop line\n", old)
        put(srv, "rain-paper-stdout.log", b"server line\n" * 2, new)
        state = {}

        def one_run(now):
            files, hold = manifest(lap, state)
            ck("pinrun-live.stop" not in files and "pinrun-live.pid" not in files
               and "watch_bot.heartbeat" not in files and "pinphone.update" not in files
               and "laptop_handover.log" not in files and "pindesk.log" not in files,
               "the laptop's flags, pids, heartbeats and own files are never even listed")
            req = {"files": files, "hold": hold}
            pkg = os.path.join(outd, "delta-%d.tgz" % now)
            s = build(srv, req, pkg, now=now, facts={"at": now, "alive": True, "bots": {"at": now, "all": {}}})
            return s, apply_package(pkg, lap, state, files, now=now), hold

        busy = open(os.path.join(lap, "rain-paper-stdout.log"), "ab")
        try:
            s1, r1, hold1 = one_run(new + 60)
        finally:
            busy.close()
        if os.name == "nt":
            ck(r1["held_now"] == ["rain-paper-stdout.log"] and get(lap, "rain-paper-stdout.log") == b"laptop line\n"
               and not os.path.exists(os.path.join(lap, "rain-paper-stdout.log.sync-tmp")),
               "a log open in a laptop process is left as it is: %r" % r1["held_now"])
            ck("rain-paper-stdout.log" in manifest(lap, state)[1], "and held on every later run")
        ck(hold1 == ["fc-fast-paper.jsonl"], "a log the laptop writes itself is held: %r" % hold1)
        ck(get(lap, "fc-fast-paper.jsonl") == b'{"laptop": "own"}\n', "the held log is untouched")
        names = {e["name"] for e in s1["entries"]}
        ck(not names & {"pinrun-live.stop", "pinrun-live.pid", "watch_bot.heartbeat", "pinphone.update",
                        "laptop_handover.log", "pindesk.log", "fxtake-live.stop", "pinrun-hwm.reset"},
           "no *.stop / *.pid / *.heartbeat / *.reset / pinphone.update / laptop_handover.* / pindesk.log "
           "leaves the server: %r" % sorted(names))
        for n_, data in (("pinrun-live.stop", b"laptop handover"), ("pinrun-live.pid", b"111"),
                         ("watch_bot.heartbeat", b"laptop"), ("pinphone.update", b"laptop"),
                         ("laptop_handover.log", b"laptop log\n"), ("pindesk.log", b"laptop desk\n")):
            ck(get(lap, n_) == data, "%s on the laptop is exactly as it was" % n_)
        ck(not os.path.exists(os.path.join(lap, "fxtake-live.stop")), "a server stop file is never copied")
        ck(not os.path.exists(os.path.join(lap, "pinrun-hwm.reset")), "a server one-shot flag is never copied")
        # the delta: appended, cut at the last whole line
        ck(get(lap, "pinrun-live-a.jsonl") == prefix + b'{"n": 300}\n{"n": 301}\n',
           "a grown log gets only its new bytes, ending on a whole line")
        ent = next(e for e in s1["entries"] if e["name"] == "pinrun-live-a.jsonl")
        ck(ent["op"] == "append" and ent["offset"] == len(prefix), "it was sent as a delta from the laptop's end")
        # diverged and shorter: whole copies, the laptop's copy moved aside, not deleted
        ck(get(lap, "ladder-live.jsonl") == prefix + b'{"server": 1}\n{"server": 2}\n',
           "a log that differs is copied whole")
        ck(get(lap, "watch_bot.log") == b"fresh\n" * 3, "a log shorter on the server is copied whole")
        bdir = os.path.join(lap, BACKUP_DIR)
        kept = sorted(os.listdir(bdir))
        ck(len(kept) == 2 and any(k.startswith("ladder-live.jsonl.") for k in kept)
           and any(k.startswith("watch_bot.log.") for k in kept), "both laptop copies kept: %r" % kept)
        ck(any(get(bdir, k) == b"line\n" * 500 for k in kept), "the kept copy has the laptop's bytes")
        ck(set(r1["moved"]) == {"ladder-live.jsonl", "watch_bot.log"}, "moved: %r" % r1["moved"])
        ck(get(lap, "kalshi_ledger.json") == b'{"v": 2, "rows": [1, 2, 3]}', "a changed cache is copied whole")
        ck(abs(os.path.getmtime(os.path.join(lap, "DOWNTIME.json")) - new) < 2
           and get(lap, "DOWNTIME.json") == b'{"same": true}', "same bytes, other time: only the time moves")
        ck(get(lap, "only-on-laptop.jsonl") == b'{"keep": 1}\n', "a laptop-only file is kept")
        ck(get(lap, "pinrun-live-new.jsonl") == b'{"n": 1}\n{"n": 2}\n', "a new server file arrives")
        ck(get(lap, "same.jsonl") == prefix and "same.jsonl" not in names, "an unchanged file is not sent")
        ck(os.path.exists(os.path.join(lap, STATUS_NAME)) and os.path.exists(os.path.join(lap, BOTS_NAME)),
           "the server's status and Bots numbers are written beside the logs")
        ck("pinrun-live-a.jsonl" not in r1["replaced"] and "ladder-live.jsonl" in r1["replaced"],
           "a replaced log is reported, so the app re-reads it from the start")

        # second run, nothing new on the server: idempotent (the half line is still being written)
        s2, r2, _h = one_run(new + 90)
        ck(r2["append"] == 0 and r2["whole"] == 0 and r2["bytes"] == 0,
           "a second run with nothing new moves nothing: %r" % (s2["entries"],))
        ck(len(os.listdir(bdir)) == 2, "and keeps nothing more aside")

        # the half line is finished on the server; the next run completes it
        with open(os.path.join(srv, "pinrun-live-a.jsonl"), "ab") as fh:
            fh.write(b'02}\n')
        os.utime(os.path.join(srv, "pinrun-live-a.jsonl"), (new + 200, new + 200))
        s3, r3, _h = one_run(new + 240)
        ck(get(lap, "pinrun-live-a.jsonl") == prefix + b'{"n": 300}\n{"n": 301}\n{"n": 302}\n'
           and r3["append"] == 1, "the next run appends the rest of the line")
        # a run killed after unpacking but before saving its state: the journal adopts the files
        with open(os.path.join(srv, "pinrun-live-a.jsonl"), "ab") as fh:
            fh.write(b'{"n": 303}\n')
        os.utime(os.path.join(srv, "pinrun-live-a.jsonl"), (new + 300, new + 300))
        before = json.loads(json.dumps(state))
        files, hold = manifest(lap, state)
        pkg = os.path.join(outd, "delta-killed.tgz")
        build(srv, {"files": files, "hold": hold}, pkg, now=new + 330, facts={})
        jp = os.path.join(base, "state.json.pending")
        apply_package(pkg, lap, json.loads(json.dumps(state)), files, now=new + 330, journal=jp)
        ck("pinrun-live-a.jsonl" in manifest(lap, before)[1], "without the journal the file would look laptop-written")
        ck(recover_journal(before, lap, jp) >= 1 and "pinrun-live-a.jsonl" not in manifest(lap, before)[1]
           and not os.path.exists(jp), "the journal of a killed run adopts what it wrote")
        state.clear()
        state.update(before)
        # a laptop process writes a log the sync wrote: from then on it is the laptop's
        with open(os.path.join(lap, "pinrun-live-new.jsonl"), "ab") as fh:
            fh.write(b'{"laptop wrote": 1}\n')
        files, hold = manifest(lap, state)
        ck("pinrun-live-new.jsonl" in hold, "a synced log the laptop then writes is held")

        # the program sent to the server compiles and holds no laptop-only name
        prog = server_program("eA==")
        compile(prog, "<server>", "exec")
        ck("def server_main" in prog and "def apply_package" not in prog and "LAPTOP SIDE" not in prog,
           "the server is sent only the SERVER SIDE block")
        # commands: ssh and scp, key and BatchMode, nothing else
        cfg = {"host": "18.216.240.218", "user": "Administrator", "key": r"C:\k\id", "python": r"C:\Python314\python.exe",
               "repo": r"C:\kals-repo"}
        sb = ssh_base(cfg)
        ck(os.path.basename(sb[0]).lower() in ("ssh", "ssh.exe") and sb[-1] == "Administrator@18.216.240.218"
           and "BatchMode=yes" in sb
           and sb[sb.index("-i") + 1] == r"C:\k\id", "ssh argv: %r" % sb)
        sc = scp_cmd(cfg, r"C:\Users\Administrator\sync\delta-x.tgz", r"C:\t\d.tgz")
        ck(os.path.basename(sc[0]).lower() in ("scp", "scp.exe") and sc[-2] == "Administrator@18.216.240.218:C:/Users/Administrator/sync/delta-x.tgz",
           "scp argv: %r" % sc)
        # config
        cp = put(base, "server.json", json.dumps(cfg).encode())
        ck(load_config(cp)["host"] == "18.216.240.218", "config reads")
        ck(load_config(os.path.join(base, "nope.json")) is None, "no config = None")
        put(base, "bad.json", b"{not json")
        try:
            load_config(os.path.join(base, "bad.json"))
            ck(False, "a broken config must not read as 'no server'")
        except SyncError:
            pass
        # lock
        lp = os.path.join(base, "x.lock")
        rel = _lock(lp)
        ck(rel is not None and _lock(lp) is None, "one sync at a time")
        rel()
        rel2 = _lock(lp)
        ck(rel2 is not None, "the lock is released")
        rel2()
        with open(lp, "w") as fh:                 # left by a process that no longer exists
            fh.write("4000000000 %d" % time.time())
        rel3 = _lock(lp)
        ck(rel3 is not None, "a lock whose owner is gone is taken over")
        rel3()
        ck(safe_name("a.jsonl") and not safe_name("..\\a") and not safe_name("d/a") and not safe_name("C:a"),
           "file names are plain names only")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print("server_sync selftest: OK")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        selftest()
        return 0
    dry = "--dry-run" in argv
    s = sync_once(dry_run=dry)
    if dry:
        if not s.get("ok"):
            print("dry run FAILED: %s" % s.get("err"))
            return 1
        print(json.dumps(s["plan"], indent=1))
        return 0
    print(summary_line(s))
    return 0 if s.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
