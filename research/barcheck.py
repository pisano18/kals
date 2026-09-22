"""barcheck.py -- the 2026-09-22 FREEZE's pre-registered bars, checked against
Kalshi's ledger and our own logs.

WHAT IT MEASURES. Every bar in results/FREEZE_bars.json (written before any
post-freeze outcome was read; the prose is results/FREEZE_2026-09-22.md):

  B1  the 45 s leg at a third (live) vs full vs off, from earlyhindsight.py's
      per-close counterfactual (freeze_rows(), code pinned by sha256), fed
      barcheck's own ledger snapshot and reconciled to it; INVALID if the
      scorer's ledger-vs-logs check fails on a sample close; a FULL pass must
      also pass on FULL-lo (every market resting on unlogged depth at its
      worst reading and 0);
  B2  the fresh-offer rule (map C5) out of sample, on 45 s-leg fills;
  B3  the post-fill collapse (map C6) as a HEDGE trigger, priced from the
      per-second hedge_quote log;
  B4  the 0.25 hedge trigger against PREREG_hedge.md's restored bar, plus its
      four n=30 safety rules;
  B5  why the <=30 s window's volume fell 65% (tau/budget_left on refusals)
      -- a diagnostic, answering only where the low bound (refusals whose
      book was read) and the high bound (plus every refusal made before the
      book was read, at our size) agree;
  B6  paper arms vs live on shared closes -- report only.

For each: units so far, the statistic, PASS / FAIL / COLLECTING (or PENDING
when a log field or the scorer does not exist yet, INVALID when a data check
fails, REPORT for the report-only rows), and how many units are still needed.
Writes results/FREEZE_status.md next to this script; --brief prints <= 8 plain
lines for a phone.

MULTIPLE LOOKS. A decision bar is computed ONCE, on a fixed sample: the first N
units (closes / events / alarms) in time order after its window opens. Before N
it is COLLECTING and its running numbers decide nothing; after N the verdict is
fixed and later data is shown as report only -- so re-running this every hour
cannot fish for a PASS. If a setting a bar measures changes on the live bot
(a later live `start` record differs on the bar's `config_keys`), the bar's
window restarts at that change; samples are never pooled across settings.
Across bars, only B1-B3 are discovery tests; their null false-PASS rates at
the registered n sum under the 0.10 budget (FREEZE_bars.json `multiple_looks`).
Post-registration changes are listed, dated, in FREEZE_bars.json `amendments`.

RULES IT KEEPS. Money is Kalshi's ledger (pinledger.pnl, one row per market,
hedged markets included); the logs' `realised` is never summed. n is closes.
Nothing here is a backtest -- B3/B4 price hedges from OUR OWN logged quotes.
Read-only: it writes one status file and no bytecode.
"""
import argparse
import calendar
import collections
import glob
import hashlib
import importlib
import json
import math
import os
import random
import re
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinledger                                                  # noqa: E402
from pinflat import close_epoch                                   # noqa: E402
from downtime import et_offset                                    # noqa: E402

REPO_RESULTS = os.path.join(os.path.dirname(HERE), "results")
# The live logs and the ledger are READ from the live results folder, even
# when this runs from a worktree: a worktree's results/ holds git-tracked
# snapshots of the live logs, and a run there without --data once scored
# stale copies. The status file is still written next to this script.
LIVE_RESULTS = r"C:\kals-repo\results"
DATA_DEFAULT = LIVE_RESULTS if os.path.isdir(LIVE_RESULTS) else REPO_RESULTS
BARS_PATH = os.path.join(REPO_RESULTS, "FREEZE_bars.json")
STATUS_PATH = os.path.join(REPO_RESULTS, "FREEZE_status.md")
# The pin bot's up/down 15-minute series (pinrun.SERIES_TO_INDEX; the same list
# as earlyhindsight.PIN_SERIES). The Coin Race (KXCRYPTOLEAD15M) and the
# commodity bots (KXWTI15M, KXGOLD15M, KXNATGAS15M, KXCOPPER15M -- ALSO 15M)
# share the ledger and are NOT this strategy.
PIN_SERIES = frozenset([
    "KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M",
    "KXBCH15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M", "KXADA15M"])
PIN_SHAPE = re.compile(r"^KX[A-Z0-9]+15M-\d{2}[A-Z]{3}\d{6}-\d{2}$")
LOG_RX = re.compile(r"pinrun-paper-\d{8}T\d{6}Z\.jsonl")
SIG_PAIR_S = 3          # an order is paired with its ticker's signal <= 3 s before it


def series_of(tk):
    return str(tk or "").split("-")[0]


def is_pin(tk):
    """A pin-bot market: one of PIN_SERIES, in the up/down ticker shape."""
    return series_of(tk) in PIN_SERIES and bool(PIN_SHAPE.match(tk))


# ------------------------------------------------------------------ basics
def ep(s):
    """'2026-09-22T11:42:12Z' (fractions allowed) -> UTC epoch, or None."""
    try:
        return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def iso(e):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e))


def et(epoch, date=True):
    """Presentation only: the operator reads Eastern ('9/22 07:42 ET').
    Everything stored stays UTC."""
    if epoch is None:
        return "?"
    tm = time.gmtime(epoch + et_offset(epoch))
    hm = "%02d:%02d ET" % (tm.tm_hour, tm.tm_min)
    return ("%d/%d %s" % (tm.tm_mon, tm.tm_mday, hm)) if date else hm


def fnum(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def usd(x):
    return "-" if x is None else ("%s$%.2f" % ("-" if x < 0 else "+", abs(x)))


def pct(x):
    return "-" if x is None else "%.0f%%" % (100.0 * x)


def taker_fee(k, p):
    """Kalshi taker fee on one order: 0.07*k*p*(1-p), rounded UP to the cent."""
    if k <= 0:
        return 0.0
    return math.ceil(0.07 * k * p * (1.0 - p) * 100.0 - 1e-9) / 100.0


def leg_pnl(k, price, side, result):
    """Dollars from buying k of `side` at `price` on a market that settled
    `result`, fee included. The bought side pays $1 a contract if it won."""
    won = (side == result)
    return k * ((1.0 - price) if won else -price) - taker_fee(k, price)


def fisher_greater(a, n1, b, n2):
    """One-sided exact test: P(group 1 holds >= a of the a+b losing units),
    given the margins. Small = group 1 loses more often than group 2."""
    if n1 <= 0 or n2 <= 0:
        return None

    def lc(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    K, N = a + b, n1 + n2
    p = 0.0
    for x in range(a, min(K, n1) + 1):
        if K - x > n2:
            continue
        p += math.exp(lc(n1, x) + lc(n2, K - x) - lc(N, K))
    return min(1.0, p)


def boot_p(xs, draws, seed):
    """Share of unit-resamples (with replacement) whose SUM is > 0."""
    if not xs:
        return None
    rng = random.Random(seed)
    n, hit = len(xs), 0
    for _ in range(draws):
        if sum(rng.choices(xs, k=n)) > 0:
            hit += 1
    return hit / float(draws)


def top_share(ds):
    """Largest single contribution as a share of the (positive) total."""
    tot = sum(ds)
    if tot <= 0:
        return None
    return max(ds) / tot


def read_jsonl(path):
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                yield r


# ------------------------------------------------------------------ loading
def ledger_view(rows):
    """{ticker: {pnl, result, close, yes_n, no_n}} for pin markets only."""
    out = {}
    for s in rows.values():
        tk = str(s.get("ticker") or "")
        if not is_pin(tk):
            continue
        v = out.setdefault(tk, {"pnl": 0.0, "result": None, "close": close_epoch(tk),
                                "yes_n": 0.0, "no_n": 0.0})
        v["pnl"] += pinledger.pnl(s)
        rs = str(s.get("market_result") or "").strip().lower()
        if rs in ("yes", "no"):
            v["result"] = rs
        v["yes_n"] += pinledger.money(s, "yes_count_fp")
        v["no_n"] += pinledger.money(s, "no_count_fp")
    return out


def empty_live():
    return {"armed": set(), "fills": [], "alarms": [], "hedges": [], "quotes": {},
            "refused": [], "starts": [], "budget_from": None, "quote_from": None,
            "files": 0}


def load_live(data_dir, since_s):
    """Our live logs, from `since_s` on. Only what the bars read is kept.
    Every `start` record is kept whatever its date (the config trail)."""
    W = empty_live()
    quotes = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(data_dir, "pinrun-live-*.jsonl"))):
        try:
            if os.path.getmtime(f) < since_s - 3600:
                continue                     # finished before the window opened
        except OSError:
            continue
        W["files"] += 1
        sigs = {}
        for r in read_jsonl(f):
            k = r.get("kind")
            t = ep(r.get("t"))
            if k == "start":
                W["starts"].append(r)
                continue
            if k == "signal":
                sigs[r.get("ticker")] = (t, r)
            if t is None or t < since_s:
                continue
            tk = r.get("ticker")
            if k == "close_summary":
                c = fnum(r.get("close"))
                if c is not None:
                    W["armed"].add(int(c))
            elif k == "order":
                n = fnum(r.get("filled")) or 0.0
                if n <= 0:
                    continue
                st, sg = sigs.get(tk, (None, None))
                if sg is None or st is None or not (t - SIG_PAIR_S <= st <= t):
                    sg = {}
                W["fills"].append({
                    "ticker": tk, "close": close_epoch(tk), "t": t,
                    "leg": r.get("leg") or sg.get("leg") or "full",
                    "want": r.get("want") or sg.get("want"), "n": n,
                    "exec": fnum(r.get("exec_price")),
                    "ask_seen": fnum(r.get("ask_seen", sg.get("price"))),
                    "tau": fnum(r.get("tau_at_send", sg.get("tau"))),
                    "age_ms": fnum(sg.get("level_age_ms"))})
            elif k == "hedge_alarm":
                W["alarms"].append({"ticker": tk, "t": t, "want": r.get("want"),
                                    "belief": fnum(r.get("belief")), "n": fnum(r.get("n"))})
            elif k == "hedge":
                n = fnum(r.get("n")) or 0.0
                if n > 0 and r.get("live", True) is not False:
                    W["hedges"].append({"ticker": tk, "t": t, "side": r.get("side"),
                                        "price": fnum(r.get("price")), "n": n})
            elif k == "hedge_quote":
                quotes[tk].append({"t": t, "ask": fnum(r.get("ask")), "size": fnum(r.get("size")),
                                   "belief": fnum(r.get("belief")), "side": r.get("side")})
                if W["quote_from"] is None or t < W["quote_from"]:
                    W["quote_from"] = t
            elif k == "refused" and "budget_left" in r:
                if W["budget_from"] is None or t < W["budget_from"]:
                    W["budget_from"] = t
                W["refused"].append(dict(refusal_price(r), **{
                    "close": int(fnum(r.get("close_s")) or close_epoch(tk) or 0), "ticker": tk,
                    "t": t, "gate": r.get("gate"), "tau": fnum(r.get("tau")),
                    "budget_left": fnum(r.get("budget_left")),
                    "size_now": fnum(r.get("size_now"))}))
    for q in quotes.values():
        q.sort(key=lambda x: x["t"])
    W["quotes"] = dict(quotes)
    W["fills"].sort(key=lambda f: f["t"])
    W["starts"].sort(key=lambda s: ep(s.get("t")) or 0)
    return W


def refusal_price(r):
    """{priced, ask, ask_size} from one `refused` record, in the shape each gate
    writes it. no_offer writes wanted_side + <side>_ask (null = our side not
    offered at all); the book gates (edge_floor, depth_floor, price_ceiling,
    ev_floor, rebuy_band, ...) write want + price + size (depth_floor also
    `offered`, the depth actually there); the gates that refuse BEFORE the book
    is read (close_budget, max_per_market, book_stale, ...) write no price."""
    side = r.get("wanted_side") or r.get("want")
    if side and ("%s_ask" % side) in r:
        return {"priced": True, "ask": fnum(r.get("%s_ask" % side)),
                "ask_size": fnum(r.get("%s_ask_size" % side))}
    if "price" in r:
        return {"priced": True, "ask": fnum(r.get("price")),
                "ask_size": fnum(r.get("offered", r.get("size")))}
    return {"priced": False, "ask": None, "ask_size": None}


def late_per_close(data_dir, lo, hi):
    """Baseline for B5 by THIS file's own definition: contracts bought at
    <= 30 s (not the 45 s leg) per watched close, closes lo..hi. Pre-freeze
    logs only; they no longer change, so this is fixed."""
    late, armed = 0.0, set()
    for f in sorted(glob.glob(os.path.join(data_dir, "pinrun-live-*.jsonl"))):
        try:
            if os.path.getmtime(f) < lo - 3600:
                continue
        except OSError:
            continue
        for r in read_jsonl(f):
            k = r.get("kind")
            if k == "close_summary":
                c = fnum(r.get("close"))
                if c is not None and lo + 60 <= c <= hi:
                    armed.add(int(c))
            elif k == "order" and (fnum(r.get("filled")) or 0) > 0:
                c = close_epoch(r.get("ticker"))
                tau = fnum(r.get("tau_at_send"))
                if c is not None and lo + 60 <= c <= hi and (r.get("leg") or "full") != "early" \
                        and (tau is None or tau <= 30):
                    late += fnum(r.get("filled"))
    return (late / len(armed)) if armed else None, len(armed)


def arm_names(data_dir, since_s):
    """{paper log basename: arm name}, read from the arms' own stdout files
    (each prints 'log C:\\...\\pinrun-paper-<ts>.jsonl' at start; a restart
    rewrites the file, so older logs are named by their setting instead)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(data_dir, "arm-*.out"))):
        try:
            if os.path.getmtime(f) < since_s - 86400:
                continue
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        name = os.path.basename(f)[:-4]
        with fh:
            for line in fh:
                for m in LOG_RX.findall(line):
                    out[m] = name
    return out


def in_force(starts, t):
    """The live start record in force at epoch t (the last one at/before t)."""
    cur = None
    for s in starts:
        st = ep(s.get("t"))
        if st is not None and st <= t:
            cur = s
    return cur


def signature(start, live_starts, ignore):
    """What a paper arm changes relative to the live bot in force when it
    started: sorted 'key=value' strings."""
    lv = in_force(live_starts, ep(start.get("t")) or 0) or (live_starts[0] if live_starts else {})
    keys = (set(start) | set(lv)) - set(ignore)
    return tuple(sorted("%s=%s" % (k, start.get(k)) for k in keys if start.get(k) != lv.get(k)))


def load_arms(data_dir, since_s, live_starts, rules):
    """{arm label: {early, runs: [{code, start, armed, pnl{tk}, n{tk}}], sig}}."""
    names = arm_names(data_dir, since_s)
    logs = []
    for f in sorted(glob.glob(os.path.join(data_dir, "pinrun-paper-*.jsonl"))):
        try:
            if os.path.getmtime(f) < since_s:
                continue
        except OSError:
            continue
        first = next(read_jsonl(f), None)
        if not first or first.get("kind") != "start":
            continue
        sig = signature(first, live_starts, rules["ignore_keys"])
        logs.append((f, first, sig, names.get(os.path.basename(f))))
    sig_name = {sig: nm for _f, _s, sig, nm in logs if nm}
    arms = {}
    for f, first, sig, nm in logs:
        label = nm or sig_name.get(sig) or ("sig:" + ",".join(sig) if sig else "sig:same-as-live")
        a = arms.setdefault(label, {"early": False, "runs": [], "sig": sig})
        a["early"] = a["early"] or any(s.split("=")[0] in rules["early_keys"] for s in sig)
        run = {"log": os.path.basename(f), "code": first.get("code_sha"),
               "start": ep(first.get("t")), "armed": set(), "pnl": {}, "n": {}}
        seen = set()
        for r in read_jsonl(f):
            k = r.get("kind")
            if k == "close_summary":
                c = fnum(r.get("close"))
                if c is not None:
                    run["armed"].add(int(c))
            elif k == "signal" and r.get("live") is False:
                tk = r.get("ticker")
                run["n"][tk] = run["n"].get(tk, 0.0) + (fnum(r.get("take_n", r.get("size"))) or 0.0)
            elif k == "settled":
                key = json.dumps(r, sort_keys=True)      # exact duplicates only
                if key in seen:
                    continue
                seen.add(key)
                tk = r.get("ticker")
                run["pnl"][tk] = run["pnl"].get(tk, 0.0) + (fnum(r.get("pnl_c")) or 0.0) / 100.0
        a["runs"].append(run)
    return arms


def _import_scorer(name, extra_dir):
    if extra_dir and extra_dir not in sys.path:
        sys.path.insert(0, extra_dir)
    return importlib.import_module(name)


def file_sha256(path):
    """sha256 of a source file with CRLF read as LF (earlyhindsight.code_sha256's
    rule), so a Windows checkout and git's blob hash the same. None if unreadable."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()
    except (OSError, TypeError):
        return None


def scorer_rows(mod, sc, since_s, now_s, data_dir, ledger_rows=None):
    """B1's rows from the scorer's registered entry point (FREEZE_bars.json
    `scorer.function`, earlyhindsight.freeze_rows): {rows, diag, stats, ...}.
    `ledger_rows` = the raw settlements barcheck itself read, so the scorer's
    LIVE and barcheck's ledger are one snapshot (pinledgerd rewrites the file
    every few minutes)."""
    fn = sc.get("function", "freeze_rows")
    f = getattr(mod, fn, None)
    if not callable(f):
        raise AttributeError("earlyhindsight has no %s()" % fn)
    out = f(since_s=since_s, data_dir=data_dir, now_s=now_s, ledger_rows=ledger_rows)
    if not isinstance(out, dict) or "rows" not in out:
        raise TypeError("%s() did not return {rows, ...}" % fn)
    return out, "earlyhindsight.%s" % fn


def load_scorer(bar, since_s, now_s, data_dir, extra_dir=None, ledger_rows=None):
    """(result dict, source, code sha256) or (None, why, None). Never raises.
    The hash is computed HERE from the module's file, not taken from the
    module's own report."""
    sc = bar.get("scorer", {})
    try:
        mod = _import_scorer(sc.get("module", "earlyhindsight"), extra_dir)
    except Exception as e:                                   # noqa: BLE001
        return None, "research/earlyhindsight.py not importable (%s)" % type(e).__name__, None
    code = file_sha256(getattr(mod, "__file__", None))
    try:
        out, src = scorer_rows(mod, sc, since_s, now_s, data_dir, ledger_rows)
        return out, src, code
    except Exception as e:                                   # noqa: BLE001
        return None, "earlyhindsight failed: %s: %s" % (type(e).__name__, e), code


def load_world(bars, data_dir, now=None, hindsight_dir=None):
    """Everything the bars read, from disk. Read-only. A missing file is an
    empty world, never an exception."""
    bmap = {b["id"]: b for b in bars["bars"]}
    since = min(ep(b["window_start_utc"]) for b in bars["bars"])
    W = load_live(data_dir, since)
    W["now"] = now if now is not None else int(time.time())
    rows = pinledger.load_cache(os.path.join(data_dir, "kalshi_ledger.json"))
    W["ledger_raw"] = rows
    W["ledger"] = ledger_view(rows)
    W["ledger_rows"] = len(rows)
    try:
        with open(os.path.join(data_dir, "kalshi_ledger.json"), encoding="utf-8") as fh:
            W["ledger_written"] = ep(json.load(fh).get("written"))
    except (OSError, ValueError, AttributeError):
        W["ledger_written"] = None
    b6 = bmap.get("B6")
    W["arms"] = load_arms(data_dir, ep(b6["window_start_utc"]), W["starts"], b6["rules"]) if b6 else {}
    b1 = bmap.get("B1")
    if b1:
        W["hind_rows"], W["hind_src"], W["hind_code"] = load_scorer(
            b1, ep(b1["window_start_utc"]), W["now"], data_dir, hindsight_dir,
            ledger_rows=W.get("ledger_raw"))
    else:
        W["hind_rows"], W["hind_src"], W["hind_code"] = None, "no B1", None
    b5 = bmap.get("B5")
    W["b5_base"] = {}
    if b5:
        for nm, (lo, hi) in b5["rules"].get("own_baselines", {}).items():
            W["b5_base"][nm] = late_per_close(data_dir, ep(lo), ep(hi))
    return W


# ------------------------------------------------------------ shared views
def closes_all(W, start):
    """(every close >= start+60 in time order, the unsettled ones). A close
    counts once the bot watched it (close_summary) or Kalshi settled a pin
    market at it; it is unsettled while any market we filled in it has no
    ledger result yet."""
    lo = start + 60
    traded = collections.defaultdict(set)
    for f in W["fills"]:
        if f["close"] is not None and f["close"] >= lo:
            traded[f["close"]].add(f["ticker"])
    led = {v["close"] for v in W["ledger"].values() if v["close"] is not None and v["close"] >= lo}
    every = sorted({c for c in W["armed"] if c >= lo} | led | set(traded))
    uns = {c for c in every
           if any(tk not in W["ledger"] or W["ledger"][tk]["result"] is None for tk in traded.get(c, ()))}
    return every, uns


def closes_since(W, start):
    """(settled closes, unsettled closes) -- the freeze clock."""
    every, uns = closes_all(W, start)
    return [c for c in every if c not in uns], sorted(uns)


def first_n(W, start, n):
    """The decision sample: the first n closes after `start`, in time order.
    (sample, settled_so_far, ready) -- ready once n exist and all are settled."""
    every, uns = closes_all(W, start)
    sample = every[:n]
    settled = [c for c in sample if c not in uns]
    return sample, settled, len(sample) >= n and len(settled) == len(sample)


def ledger_by_close(W):
    out = collections.defaultdict(float)
    for v in W["ledger"].values():
        if v["close"] is not None:
            out[v["close"]] += v["pnl"]
    return out


def effective_start(bar, W):
    """(start, note). The bar's window restarts at the latest live start
    record whose `config_keys` differ from the config in force when the
    window opened. Code changes (bug fixes) do not restart a bar."""
    s0 = ep(bar["window_start_utc"])
    keys = bar.get("config_keys") or []
    ref = in_force(W["starts"], s0)
    if not keys or ref is None:
        return s0, None
    start, note = s0, None
    for s in W["starts"]:
        st = ep(s.get("t"))
        if st is None or st <= s0:
            continue
        diff = [k for k in keys if s.get(k) != ref.get(k)]
        if diff:
            start = st
            note = "restarted %s: %s" % (et(st), ", ".join("%s %s->%s" % (k, ref.get(k), s.get(k))
                                                          for k in diff))
            ref = s
    return start, note


def res(status, bid, n, need, line, detail, stat=None):
    return {"id": bid, "status": status, "n": n, "need": need, "line": line,
            "detail": detail, "stat": stat or {}}


# ------------------------------------------------------------------ bars
def eval_freeze(cfg, W):
    start = ep(cfg["start_utc"])
    closes, uns = closes_since(W, start)
    lbc = ledger_by_close(W)
    money = [lbc.get(c, 0.0) for c in closes]
    lost = sum(1 for m in money if m < -1e-9)
    n = len(closes)
    need = max(0, cfg["length_closes"] - n)
    line = ("Freeze: %d of %d closes since %s. Kalshi says %s, %d losing close%s%s."
            % (n, cfg["length_closes"], et(start), usd(sum(money)), lost, "" if lost == 1 else "s",
               (", %d waiting to settle" % len(uns)) if uns else ""))
    det = ["closes counted %d, waiting to settle %d, still needed %d" % (n, len(uns), need),
           "money (Kalshi ledger, pin markets): %s over %d closes, %d losing" % (usd(sum(money)), n, lost),
           "ledger last written %s; live logs read %d" % (et(W.get("ledger_written")), W.get("files", 0))]
    return res("REPORT", "FREEZE", n, need, line, det, {"money": sum(money), "lost": lost})


def _rows(raw):
    """Normalise the scorer's output to {close: {live, full, off, full_lo,
    tickers, mismatch, not_in_ledger, flagged}}. Accepts {rows: [...]}, flat
    rows (live/full/off) and earlyhindsight's nested `pol`."""
    if isinstance(raw, tuple) and raw:
        raw = raw[0]
    if isinstance(raw, dict) and "rows" in raw:
        raw = raw["rows"]
    items = []
    if isinstance(raw, dict):
        for c, v in raw.items():
            if isinstance(v, dict):
                items.append(dict(v, close=v.get("close", c)))
    elif isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
    out = {}
    for x in items:
        c = fnum(x.get("close", x.get("close_s")))
        if c is None:
            continue
        flat = {str(k).lower(): v for k, v in x.items() if not isinstance(v, dict)}
        for k, v in (x.get("pol") or {}).items():
            flat[str(k).lower()] = v
        for k, v in (x.get("lo") or {}).items():
            flat["%s_lo" % str(k).lower()] = v
        out[int(c)] = {"live": fnum(flat.get("live", flat.get("third"))),
                       "full": fnum(flat.get("full")), "off": fnum(flat.get("off")),
                       "full_lo": fnum(flat.get("full_lo")),
                       "tickers": x.get("tickers"),
                       "mismatch": int(fnum(flat.get("mismatch")) or 0),
                       "not_in_ledger": int(fnum(flat.get("not_in_ledger")) or 0),
                       "flagged": int(fnum(flat.get("flagged")) or 0)}
    return out


def _b1_policy(ds, pr, r, ready):
    """(stat, passes) for one column of per-close differences."""
    mean = sum(ds) / len(ds) if ds else 0.0
    bp = boot_p(ds, r["boot_draws"], r["seed"]) if ds else None
    sh = top_share(ds)
    ok = (ready and mean >= pr["min_gain_per_close"] and bp is not None
          and bp >= r["min_boot_p"] and sh is not None and sh <= r["max_single_close_share"])
    return {"mean": mean, "total": sum(ds), "boot_p": bp, "top_share": sh}, ok


def eval_b1(bar, W):
    r = bar["rules"]
    start, note = effective_start(bar, W)
    N = r["min_closes"]
    sample, settled, ready = first_n(W, start, N)
    n = len(settled)
    need = max(0, N - len(sample))
    pre = ([note] if note else [])
    if W.get("hind_rows") is None:
        return res("PENDING", "B1", n, need,
                   "B1 early-bet size (third/full/off): PENDING, %d of %d closes; the scorer "
                   "is not in yet." % (n, N),
                   pre + ["scorer: %s" % W.get("hind_src")])
    rows = _rows(W["hind_rows"])
    lbc = ledger_by_close(W)
    early_closes = {f["close"] for f in W["fills"] if f["leg"] == "early"}
    s_live = l_live = 0.0
    missing = mism = nil = flagged = 0
    for c in settled:
        row = rows.get(c)
        if row is None or row["live"] is None:
            if c in early_closes:
                missing += 1
            continue
        s_live += row["live"]
        mism += row["mismatch"]
        nil += row["not_in_ledger"]
        flagged += row["flagged"]
        tks = row.get("tickers")
        if isinstance(tks, list):
            l_live += sum(W["ledger"][tk]["pnl"] for tk in tks if tk in W["ledger"])
        else:
            l_live += lbc.get(c, 0.0)
    tol = max(r["reconcile_tol_abs"], r["reconcile_tol_frac"] * abs(l_live))
    reg = (bar.get("scorer") or {}).get("code_sha256")
    code = W.get("hind_code")
    code_ok = None if reg is None and code is None else (reg is not None and code == reg)
    bad, short = [], []
    if abs(s_live - l_live) > tol:
        bad.append("its live column %s is not Kalshi's %s" % (usd(s_live), usd(l_live)))
        short.append("its money is not Kalshi's")
    if missing:
        bad.append("%d closes with a 45 s-leg fill have no scorer row" % missing)
        short.append("closes missing")
    if mism or nil:
        # the scorer's own ledger-vs-logs check: a close whose ledger entry-side
        # count differs from the logged fills (the check that caught the 09-22
        # side bug) or whose log fills have no ledger row cannot be scored
        bad.append("%d market(s) whose ledger count differs from the logged fills, %d log "
                   "fill(s) with no ledger row" % (mism, nil))
        short.append("its ledger count differs from the logged fills")
    if code_ok is False:
        bad.append("the scorer's code (%s) is not the registered one (%s): an edit after "
                   "registration needs a dated amendment in FREEZE_bars.json"
                   % ((code or "?")[:12], (reg or "none")[:12]))
        short.append("its code is not the registered one")
    det = pre + ["scorer: %s, code %s (registered %s); its live column %s vs Kalshi %s on the "
                 "same closes; mismatched markets %d, log fills with no ledger row %d, closes "
                 "with a 45 s-leg fill but no scorer row %d -> %s"
                 % (W.get("hind_src"), (code or "?")[:12], (reg or "none")[:12], usd(s_live),
                    usd(l_live), mism, nil, missing, "; ".join(bad) if bad else "reconciled")]
    live_tot = sum(lbc.get(c, 0.0) for c in settled)
    stat, passing = {}, []
    cols = {"full": "full", "off": "off", "full_lo": "full_lo"}
    ds_by = {}
    for p in cols:
        ds = []
        for c in settled:
            row = rows.get(c)
            if row is None or row.get(p) is None or row["live"] is None:
                ds.append(0.0)
            else:
                ds.append(row[p] - row["live"])
        ds_by[p] = ds
    lo_st, lo_ok = _b1_policy(ds_by["full_lo"], r["policies"]["full"], r, ready)
    for p, pr in r["policies"].items():
        st_, ok = _b1_policy(ds_by[p], pr, r, ready)
        stat[p] = st_
        det.append("%s minus the third: %s/close (%s total), resampled P(ahead) %s, biggest close %s "
                   "of it; bar >= %s/close with P >= %.3f"
                   % (p, usd(st_["mean"]), usd(st_["total"]),
                      "-" if st_["boot_p"] is None else "%.3f" % st_["boot_p"],
                      pct(st_["top_share"]), usd(pr["min_gain_per_close"]), r["min_boot_p"]))
        ok_lo = (p != "full" or lo_ok)
        if ok and ok_lo:
            passing.append((st_["mean"], p))
    stat["full_lo"] = lo_st
    det.append("full on its conservative bound (FULL-lo: %d market(s) resting on something the "
               "logs never held, each at its worst reading and 0): %s/close (%s total), resampled "
               "P %s, biggest close %s -- a FULL pass needs this to pass too"
               % (flagged, usd(lo_st["mean"]), usd(lo_st["total"]),
                  "-" if lo_st["boot_p"] is None else "%.3f" % lo_st["boot_p"],
                  pct(lo_st["top_share"])))
    rank = sorted([("third", live_tot)] + [(p, live_tot + stat[p]["total"])
                                            for p in ("full", "full_lo", "off")],
                  key=lambda x: -x[1])
    so_far = ", ".join("%s %s" % (p, usd(v)) for p, v in rank)
    det.append("hindsight money on these %d closes (Kalshi + the scorer's change): %s" % (n, so_far))
    if bad:
        st, what = "INVALID", "Scorer check failed: " + "; ".join(short)
    elif not ready:
        st, what = "COLLECTING", "Waiting" + (" (settling)" if len(sample) >= N else "")
    elif passing:
        st, what = "PASS", "switch to %s -- your call" % max(passing)[1]
    else:
        st, what = "FAIL", "keep the third"
    line = "B1 early-bet size (third/full/off): %s, %d of %d closes. %s." % (st, n, N, what)
    return res(st, "B1", n, need, line, det, stat)


def _entries_after(W, start):
    lo = start + 60
    return [f for f in W["fills"] if f["t"] >= start and f["close"] is not None and f["close"] >= lo]


def eval_b2(bar, W):
    r = bar["rules"]
    start, note = effective_start(bar, W)
    mk = {}
    for f in _entries_after(W, start):
        m = mk.setdefault(f["ticker"], {"close": f["close"], "want": f["want"], "ages": [],
                                        "early_n": 0.0, "all_n": 0.0})
        m["all_n"] += f["n"]
        if f["leg"] == "early":
            m["ages"].append(f["age_ms"])
            m["early_n"] += f["n"]
    skipped = collections.Counter()
    per_close = collections.OrderedDict()       # close -> {g: {"lost", "usd"}}
    unsettled_before = False
    for tk, m in sorted(mk.items(), key=lambda kv: kv[1]["close"]):
        if not m["ages"]:
            continue
        lv = W["ledger"].get(tk)
        if lv is None or lv["result"] is None:
            skipped["unsettled"] += 1
            per_close.setdefault(m["close"], {})["_unsettled"] = True
            continue
        if any(a is None for a in m["ages"]):
            skipped["no_age"] += 1
            continue
        fresh = [a < r["fresh_ms"] for a in m["ages"]]
        g = "fresh" if all(fresh) else ("old" if not any(fresh) else None)
        if g is None:
            skipped["mixed"] += 1
            continue
        c = per_close.setdefault(m["close"], {}).setdefault(g, {"lost": False, "usd": 0.0})
        c["lost"] = c["lost"] or (lv["result"] != m["want"])
        c["usd"] += lv["pnl"] * (m["early_n"] / m["all_n"] if m["all_n"] else 1.0)
    # the decision sample: closes in time order until both groups reach n
    fc, oc, ready = [], [], False
    for c, gs in sorted(per_close.items()):
        if gs.get("_unsettled"):
            unsettled_before = True
            break
        if "fresh" in gs:
            fc.append(gs["fresh"])
        if "old" in gs:
            oc.append(gs["old"])
        if len(fc) >= r["min_fresh_closes"] and len(oc) >= r["min_old_closes"]:
            ready = True
            break
    a, n1 = sum(v["lost"] for v in fc), len(fc)
    b, n2 = sum(v["lost"] for v in oc), len(oc)
    p = fisher_greater(a, n1, b, n2)
    value = [-v["usd"] for v in fc]          # what refusing the fresh entries would have kept
    bp = boot_p(value, r["boot_draws"], r["seed"]) if value else None
    need = max(0, r["min_fresh_closes"] - n1) + max(0, r["min_old_closes"] - n2)
    det = ([note] if note else []) + [
        "45 s-leg markets after the freeze: fresh (<%d ms) %d closes, %d lost; older %d closes, %d lost"
        % (r["fresh_ms"], n1, a, n2, b),
        "one-sided exact test p = %s (bar <= %.3f)" % ("-" if p is None else "%.4f" % p, r["alpha"]),
        "refusing the fresh 45 s entries would have kept %s (Kalshi, the leg's share), resampled "
        "P(>0) %s (bar %.2f)" % (usd(sum(value)), "-" if bp is None else "%.2f" % bp, r["min_boot_p"]),
        "not classed: %s%s" % (", ".join("%s %d" % kv for kv in sorted(skipped.items())) or "none",
                               "; stopped at an unsettled close" if unsettled_before else "")]
    passed = (ready and n1 and n2 and a / float(n1) > b / float(n2) and p is not None
              and p <= r["alpha"] and sum(value) > 0 and bp is not None and bp >= r["min_boot_p"])
    st = "PASS" if passed else ("FAIL" if ready else "COLLECTING")
    line = ("B2 fresh-offer rule: %s. Fresh offers lost %d of %d closes, older %d of %d "
            "(needs %d each)." % (st, a, n1, b, n2, r["min_fresh_closes"]))
    return res(st, "B2", n1 + n2, need, line, det,
               {"fresh": [a, n1], "old": [b, n2], "p": p, "value": sum(value), "boot_p": bp})


def walk_hedge(quotes, t0, n_held, tries_s, belief_below=None):
    """Buy the opposite side from our OWN logged quotes, as the live hedge
    would: from the first quote at/after t0 (and, for a trigger, the first
    whose belief is under it), one try a second for tries_s seconds, taking
    min(what is left, quoted size) at the quoted ask while the ask is < $1.
    Returns ([(k, price)], the second it fired or None)."""
    fire = None
    for q in quotes:
        if q["t"] < t0:
            continue
        if belief_below is None or (q["belief"] is not None and q["belief"] < belief_below):
            fire = q["t"]
            break
    if fire is None:
        return [], None
    left, buys = n_held, []
    for q in quotes:
        if q["t"] < fire:
            continue
        if q["t"] > fire + tries_s or left <= 1e-9:
            break
        ask, size = q["ask"], q["size"]
        if ask is None or ask >= 1.0 or not size or size <= 0:
            continue
        k = min(left, size)
        buys.append((k, ask))
        left -= k
    return buys, fire


def eval_b3(bar, W):
    r = bar["rules"]
    start, note = effective_start(bar, W)
    qf = W.get("quote_from")
    if qf is not None:
        start = max(start, qf)
    ents = _entries_after(W, start)
    per_close = collections.defaultdict(lambda: {"flag": False, "flag_lost": False, "lost": False,
                                                 "settled": True, "V": 0.0, "priced": False})
    flagged_mk = {}
    for f in ents:
        lv = W["ledger"].get(f["ticker"])
        pc = per_close[f["close"]]
        if lv is None or lv["result"] is None:
            pc["settled"] = False
            continue
        lost = lv["result"] != f["want"]
        pc["lost"] = pc["lost"] or lost
        if f["exec"] is not None and f["ask_seen"] is not None and \
                f["exec"] <= f["ask_seen"] - r["below_ask_c"] / 100.0 + 1e-9:
            pc["flag"] = True
            pc["flag_lost"] = pc["flag_lost"] or lost
            flagged_mk.setdefault(f["ticker"], f)
    unpriced = 0
    for tk, f in flagged_mk.items():
        pc = per_close[f["close"]]
        if not pc["settled"]:
            continue
        lv = W["ledger"][tk]
        held = sum(x["n"] for x in ents if x["ticker"] == tk and x["t"] <= f["t"])
        opp = "no" if f["want"] == "yes" else "yes"
        buys, fire = walk_hedge(W.get("quotes", {}).get(tk, []), f["t"], held, r["max_quote_wait_s"])
        if fire is None or fire > f["t"] + r["max_quote_wait_s"] or not buys:
            unpriced += 1
            continue
        mine = sum(leg_pnl(k, p, opp, lv["result"]) for k, p in buys)
        # subtract ONLY the real hedge contracts that covered the insured
        # contracts: each later hedge counts in proportion (held at the flagged
        # fill / position held when it fired) -- a top-up bought after the fill
        # was never insured -- and in total no more than the insurance bought.
        # The belief hedge still runs on whatever the insurance did not cover,
        # so that part is identical in both worlds and cancels.
        left = sum(k for k, _p in buys)
        actual = 0.0
        for h in sorted((h for h in W["hedges"] if h["ticker"] == tk and h["t"] >= f["t"]
                         and h["price"] is not None), key=lambda h: h["t"]):
            pos = sum(x["n"] for x in ents if x["ticker"] == tk and x["t"] <= h["t"])
            share = min(1.0, held / pos) if pos > 0 else 1.0
            k = min(h["n"] * share, left)
            if k <= 1e-9:
                continue
            actual += leg_pnl(k, h["price"], h["side"], lv["result"])
            left -= k
        pc["V"] += mine - actual
        pc["priced"] = True
    # the decision sample: settled closes in time order until n priced flagged closes
    fl, un, ready = [], [], False
    for c in sorted(per_close):
        v = per_close[c]
        if not v["settled"]:
            break
        (fl if v["flag"] else un).append(v)
        if sum(1 for x in fl if x["priced"]) >= r["min_flagged_closes"]:
            ready = True
            break
    a, n1 = sum(v["flag_lost"] for v in fl), len(fl)
    b, n2 = sum(v["lost"] for v in un), len(un)
    p = fisher_greater(a, n1, b, n2)
    Vs = [v["V"] for v in fl if v["priced"]]
    bp = boot_p(Vs, r["boot_draws"], r["seed"]) if Vs else None
    sh = top_share(Vs) if Vs else None
    k = len(Vs)
    need = max(0, r["min_flagged_closes"] - k)
    det = ([note] if note else []) + [
        "fills >= %.0fc under the ask seen: %d closes, %d lost; other closes %d, %d lost; p = %s "
        "(bar <= %.3f)" % (r["below_ask_c"], n1, a, n2, b, "-" if p is None else "%.4f" % p, r["alpha"]),
        "insuring those at once (priced from our own quotes) minus the hedges that actually ran: %s "
        "over %d closes, resampled P(>0) %s, biggest close %s of it; %d flagged markets had no usable "
        "quote" % (usd(sum(Vs)), k, "-" if bp is None else "%.2f" % bp, pct(sh), unpriced)]
    if qf is None:
        st = "PENDING"
        line = ("B3 fast-drop insurance: PENDING until the per-second insurance price log is live. "
                "%d flagged closes so far." % n1)
    else:
        passed = (ready and n1 and n2 and a / float(n1) > b / float(n2) and p is not None
                  and p <= r["alpha"] and sum(Vs) > 0 and bp is not None and bp >= r["min_boot_p"]
                  and sh is not None and sh <= r["max_single_close_share"])
        st = "PASS" if passed else ("FAIL" if ready else "COLLECTING")
        line = ("B3 fast-drop insurance: %s. %d of %d flagged closes priced (%d lost)."
                % (st, k, r["min_flagged_closes"], a))
    return res(st, "B3", k, need, line, det,
               {"flag": [a, n1], "other": [b, n2], "p": p, "value": sum(Vs), "boot_p": bp})


def eval_b4(bar, W):
    r, s = bar["rules"], bar["rules"]["safety"]
    start, note = effective_start(bar, W)
    ents = [f for f in W["fills"] if f["t"] >= start]
    held_all = sorted({f["ticker"] for f in ents if f["ticker"] in W["ledger"]
                       and W["ledger"][f["ticker"]]["result"]})
    # ---- (a) PREREG's four rules, on the FIRST n real alarms (its own wording)
    seen, al = set(), []
    for x in sorted(W["alarms"], key=lambda x: x["t"]):
        if x["t"] >= start and x["ticker"] not in seen:
            seen.add(x["ticker"])
            al.append(x)
    al = al[:s["n_alarms"]]
    al_set = [x for x in al if x["ticker"] in W["ledger"] and W["ledger"][x["ticker"]]["result"]]
    a_end = al[-1]["t"] if len(al) >= s["n_alarms"] else None
    held = [tk for tk in held_all if a_end is None
            or min(f["t"] for f in ents if f["ticker"] == tk) <= a_end]
    fa = caught = filled = 0
    rec_num = rec_den = 0.0
    for x in al_set:
        lv = W["ledger"][x["ticker"]]
        hs = [h for h in W["hedges"] if h["ticker"] == x["ticker"] and h["t"] >= x["t"]]
        if hs:
            filled += 1
        if lv["result"] == x["want"]:
            fa += 1
        else:
            caught += 1
            for h in hs:
                if h["price"] is not None:
                    rec_num += h["n"] * (100.0 - 100.0 * h["price"])
                    rec_den += h["n"]
    bad = [h for h in W["hedges"] if h["t"] >= start and h["price"] is not None
           and h["price"] >= s["max_hedge_price"]]
    na = len(al_set)
    fa_rate = fa / float(len(held)) if held else None
    rec = rec_num / rec_den if rec_den else None
    fill = filled / float(na) if na else None
    if bad:
        sst = "FAIL"
    elif na < s["n_alarms"] or len(al_set) < len(al):
        sst = "COLLECTING"
    else:
        sst = "PASS" if (fa_rate is not None and fa_rate <= s["max_false_alarm_rate"]
                         and rec is not None and rec >= s["min_recovery_c"]
                         and fill is not None and fill >= s["min_fill_rate"]) else "FAIL"
    det = ([note] if note else []) + [
        "safety (PREREG's n=30 rules): %s -- %d settled alarms of %d: %d caught, %d false of %d "
        "positions held (%s, bar <= %.0f%%); money back on caught ones %s c/contract (bar >= %.0f); "
        "hedge filled on %s of alarms (bar >= %.0f%%); hedges at >= $1.00: %d"
        % (sst, na, s["n_alarms"], caught, fa, len(held),
           "-" if fa_rate is None else "%.1f%%" % (100 * fa_rate), 100 * s["max_false_alarm_rate"],
           "-" if rec is None else "%.1f" % rec, s["min_recovery_c"], pct(fill),
           100 * s["min_fill_rate"], len(bad))]
    # ---- (b) the move bar, restored: 0.25 must beat 0.30 and 0.60 on the first 10 events
    qf = W.get("quote_from")
    thr = [r["live_threshold"]] + list(r["alternatives"])
    tot, ev, per_ev, shown = {}, 0, [], []
    if qf is None:
        mst = "PENDING"
        det.append("move bar: PENDING until the per-second insurance price log (with belief) is live")
    else:
        lo = max(start, qf)
        by_tk = collections.defaultdict(list)
        for f in ents:
            if f["t"] >= lo:
                by_tk[f["ticker"]].append(f)
        cands = []
        for tk, fs in by_tk.items():
            qs = W.get("quotes", {}).get(tk, [])
            first = min(f["t"] for f in fs)
            dip = next((q["t"] for q in qs if q["t"] >= first and q["belief"] is not None
                        and q["belief"] < r["event_belief"]), None)
            if dip is not None:
                cands.append((dip, tk, fs, qs))
        # an EVENT is a CLOSE (CLAUDE.md rule 4): every dipping market of one
        # close -- e.g. XRP + HYPE at 09-19 23:45 ET -- is one event, summed
        by_close = collections.OrderedDict()
        for dip, tk, fs, qs in sorted(cands, key=lambda x: x[0]):
            key = fs[0]["close"]
            by_close.setdefault(key, []).append((dip, tk, fs, qs))
        blocked = False
        for key in list(by_close)[:r["min_events"]]:
            vals = {th: 0.0 for th in thr}
            for dip, tk, fs, qs in by_close[key]:
                lv = W["ledger"].get(tk)
                if lv is None or lv["result"] is None:
                    blocked = True
                    break
                first = min(f["t"] for f in fs)
                opp = "no" if fs[0]["want"] == "yes" else "yes"
                for th in thr:
                    _b, fire = walk_hedge(qs, first, 0.0, r["hedge_tries_s"], belief_below=th)
                    if fire is None:
                        continue
                    n_held = sum(f["n"] for f in fs if f["t"] <= fire)
                    buys, _ = walk_hedge(qs, first, n_held, r["hedge_tries_s"], belief_below=th)
                    vals[th] += sum(leg_pnl(k, p, opp, lv["result"]) for k, p in buys)
            if blocked:
                break
            per_ev.append(vals)
        ev = len(per_ev)
        tot = {th: sum(v[th] for v in per_ev) for th in thr}
        ok_all, lines = True, []
        for alt in r["alternatives"]:
            ds = [v[r["live_threshold"]] - v[alt] for v in per_ev]
            sh = top_share(ds)
            ok = sum(ds) > 1e-9 and sh is not None and sh <= r["max_single_event_share"]
            ok_all = ok_all and ok
            # the other direction, under the SAME guard: is the alternative
            # itself shown ahead of 0.25? Only that is evidence for a change.
            back = [-x for x in ds]
            bsh = top_share(back)
            if sum(back) > 1e-9 and bsh is not None and bsh <= r["max_single_event_share"]:
                shown.append(alt)
            lines.append("0.25 minus %.2f: %s (biggest event %s of it)" % (alt, usd(sum(ds)), pct(sh)))
        if ev < r["min_events"]:
            mst = "COLLECTING"
        else:
            mst = "PASS" if ok_all else "FAIL"
        det.append("move bar: %s -- %d of %d closes with a dip below %.0f%% (%d more waiting to "
                   "settle); insurance money per trigger: %s; %s"
                   % (mst, ev, r["min_events"], 100 * r["event_belief"], int(blocked),
                      ", ".join("%.2f %s" % (th, usd(tot[th])) for th in thr), "; ".join(lines)))
    st = "FAIL" if "FAIL" in (sst, mst) else mst
    leader = ""
    if mst == "FAIL" and tot:
        if shown:
            best = max(shown, key=lambda th: tot[th])
            leader = " Leader %.2f, shown ahead of 0.25 under the same guard." % best
        else:
            leader = (" Nothing shown ahead of 0.25 either -- weak evidence (see the bar's mde); "
                      "no change proposed on the move bar alone.")
    line = ("B4 hedge at 25%%: %s. %d of %d test dips; real alarms %d of %d (%d caught, %d false); "
            "safety %s.%s" % (st, ev, r["min_events"], na, s["n_alarms"], caught, fa,
                              "FAIL" if sst == "FAIL" else "ok", leader))
    return res(st, "B4", ev, max(0, r["min_events"] - ev), line, det,
               {"safety": sst, "move": mst, "events": ev, "totals": tot, "alarms": na,
                "false": fa, "caught": caught, "shown_ahead": shown})


def _b5_view(r, W, closes):
    """Per-close <=30 s volume and refused volume, as TWO bounds.

    LOW  = refusals where the book was read (priced): min(offered, our size)
           with our side at 90-98c -- measured.
    HIGH = LOW + every refusal from a gate that fires BEFORE the book is read
           (capacity gates, and stale-data gates) at our full size -- an upper
           bound; its true volume is anywhere from 0 to our size.
    max_per_market is dropped: it fires only after the market already has its
    buys (the 09-22 09:00 ET BTC refusal held 79 = SIZE), so its contracts
    were never missing.
    Returns (bought/close, low/close, high/close, low by cause, high by cause,
    the filter's own tally of what it read and dropped)."""
    cs = set(closes)
    late = sum(f["n"] for f in W["fills"]
               if f["close"] in cs and f["leg"] != "early" and (f["tau"] is None or f["tau"] <= r["tau_max"]))
    lo_cls = collections.Counter()
    hi_cls = collections.Counter()
    drop = collections.Counter()              # the filter's own null: what it throws away
    cap = set(r.get("unpriced_gates", []))
    stale = set(r.get("stale_gates", []))
    for x in W["refused"]:
        if x["close"] not in cs:
            continue
        drop["read"] += 1
        if x["gate"] in r.get("dropped_gates", []):
            drop["%s (the market already held its buys)" % x["gate"]] += 1
            continue
        if x["tau"] is None or not (r["tau_min"] <= x["tau"] <= r["tau_max"]):
            drop["not 3-30 s left"] += 1
            continue
        used_up = x["budget_left"] is not None and x["budget_left"] <= 0
        if x.get("priced", True):
            if x["ask"] is None or not (r["price_lo"] <= x["ask"] <= r["price_hi"]):
                drop["our side not offered at 90-98c"] += 1
                continue
            k = min(x["ask_size"] or 0.0, x["size_now"] or 0.0)
            lo_k = k
            name = "budget used up" if used_up else x["gate"]
            drop["kept, priced"] += 1
        elif x["gate"] in cap or x["gate"] in stale:
            k = x["size_now"] or 0.0              # the HIGH bound: our whole size
            lo_k = 0.0                          # the book was never read
            name = "%s (unpriced)" % x["gate"]
            drop["kept, unpriced (%s)" % ("stale data" if x["gate"] in stale else "capacity")] += 1
        else:
            drop["no price, not a capacity or stale-data gate"] += 1
            continue
        if k <= 0:
            drop["no size"] += 1
            continue
        drop["kept"] += 1
        if lo_k:
            lo_cls[name] += lo_k
        hi_cls[name] += k
    n = len(closes)
    if not n:
        return 0.0, 0.0, 0.0, lo_cls, hi_cls, drop
    return (late / n, sum(lo_cls.values()) / n, sum(hi_cls.values()) / n, lo_cls, hi_cls, drop)


def _b5_cause(r, per_close, lo_pc, hi_pc, lo_cls, hi_cls, ref):
    """An answer only where BOTH bounds agree (amended 2026-09-22 after review).
    (a) bought >= 80% of the reference;
    (b) even the HIGH bound of refused volume is < 50% of the gap -> the
        offers were not there;
    (c) the LOW bound alone covers >= 80% of the gap AND one PRICED gate holds
        >= 50% of the HIGH bound's volume -> that gate. A gate that refuses
        before reading the book can never be named: its volume is unknown."""
    gap = ref - per_close
    if per_close >= r["recovered_frac"] * ref:
        return "buying came back once the 45 s leg shrank (it was using the budget)"
    if gap > 0 and hi_pc < r["not_ours_frac"] * gap:
        return "not our gates: the offers at our price were not there when we looked"
    hi_tot = float(sum(hi_cls.values()))
    priced_by = lo_cls
    if gap > 0 and hi_tot and lo_pc >= r["coverage"] * gap:
        name, v = hi_cls.most_common(1)[0]
        if name in priced_by and v / hi_tot >= r["top_share"]:
            return "gate '%s' (%.0f%% of refused volume on both bounds)" % (name, 100 * v / hi_tot)
    return None


def eval_b5(bar, W):
    r = bar["rules"]
    start, note = effective_start(bar, W)
    base_own = {nm: v for nm, v in (W.get("b5_base") or {}).items()}
    own_b = (base_own.get("era_b") or (None, 0))[0]
    ref = max(r["era_b_per_close"], own_b or 0.0)
    bf = W.get("budget_from")
    every, uns = closes_all(W, start)
    allset = [c for c in every if c not in uns]
    pc_all = _b5_view(r, W, allset)[0]
    base_line = ("reference before the fall: %.1f contracts a close (map 11, 2,654/day) and %s by "
                 "this file's own count on era B; the higher (%.1f) is used; post-fix %s"
                 % (r["era_b_per_close"], "-" if own_b is None else "%.1f" % own_b, ref,
                    "-" if not base_own.get("post_fix") or base_own["post_fix"][0] is None
                    else "%.1f" % base_own["post_fix"][0]))
    if bf is None:
        line = ("B5 why fewer late buys: PENDING until refusals log seconds-left and budget. "
                "Buying ~%.0f a day vs ~%.0f before." % (pc_all * r["closes_per_day"],
                                                        ref * r["closes_per_day"]))
        return res("PENDING", "B5", 0, r["min_closes"], line,
                   ([note] if note else []) + [base_line], {"per_close": pc_all})
    start = max(start, bf)
    stage, cause, used = None, None, []
    for N in (r["min_closes"], r["final_closes"]):
        sample, settled, ready = first_n(W, start, N)
        used = settled
        if not ready:
            break
        per_close, lo_pc, hi_pc, lo_cls, hi_cls, _d = _b5_view(r, W, settled)
        cause = _b5_cause(r, per_close, lo_pc, hi_pc, lo_cls, hi_cls, ref)
        stage = N
        if cause:
            break
    per_close, lo_pc, hi_pc, lo_cls, hi_cls, drop = _b5_view(r, W, used)
    n = len(used)
    tot = float(sum(hi_cls.values()))
    shares = [(g, v / tot) for g, v in hi_cls.most_common(3)] if tot else []
    det = ([note] if note else []) + [
        base_line,
        "<=30 s contracts bought: %.1f a close over %d closes (~%.0f a day); gap to the reference "
        "%.1f a close" % (per_close, n, per_close * r["closes_per_day"], ref - per_close),
        "refused with %d-%d s left: %.1f to %.1f contracts a close (LOW: book read, our side offered "
        "at %.0f-%.0fc, what was offered capped at our size; HIGH adds every refusal the book was "
        "never read for -- capacity and stale-data gates -- at our full size; first refusal per "
        "market and gate only, so both undercount repeats)"
        % (r["tau_min"], r["tau_max"], lo_pc, hi_pc, 100 * r["price_lo"], 100 * r["price_hi"]),
        "top causes on the HIGH bound: " + (", ".join("%s %.0f%%" % (g, 100 * sh) for g, sh in shares)
                                           or "none"),
        "refusal records read %d, kept %d; dropped: %s" % (
            drop["read"], drop["kept"],
            ", ".join("%s %d" % (k, v) for k, v in sorted(drop.items())
                      if k != "read" and not k.startswith("kept")) or "none")]
    if cause:
        st, target = "PASS", stage
    elif stage == r["final_closes"]:
        st, target = "FAIL", stage
    else:
        st = "COLLECTING"
        target = r["min_closes"] if stage is None else r["final_closes"]
    need = 0 if st != "COLLECTING" else max(0, target - n)
    line = ("B5 why fewer late buys: %s, %d of %d closes. Buying ~%.0f a day vs ~%.0f before%s."
            % (st, n, target, per_close * r["closes_per_day"], ref * r["closes_per_day"],
               ("; answer: " + cause) if cause else ""))
    return res(st, "B5", n, need, line, det, {"per_close": per_close, "refused_lo": lo_pc,
                                              "refused_hi": hi_pc, "shares": shares,
                                              "cause": cause})


def eval_b6(bar, W):
    """Arms vs live on SHARED closes: both watched it, it is after the arm's
    window, and the arm's code was the live bot's code at that close."""
    r = bar["rules"]
    w0, w1 = ep(bar["window_start_utc"]), ep(bar["early_window_start_utc"])
    lbc = ledger_by_close(W)
    live_mk = collections.defaultdict(set)
    live_n = collections.defaultdict(float)
    for tk, v in W["ledger"].items():
        if v["close"] is not None:
            live_mk[v["close"]].add(tk)
            live_n[v["close"]] += max(v["yes_n"], v["no_n"])
    det, most = [], 0
    for label in sorted(W.get("arms", {})):
        a = W["arms"][label]
        lo = (w1 if a["early"] else w0) + 60
        shared, arm_mk, arm_usd, arm_n = set(), collections.defaultdict(set), 0.0, 0.0
        skipped_code = 0
        for run in a["runs"]:
            for c in run["armed"]:
                if c < lo or c not in W["armed"] or (run["start"] or 0) > c - 60:
                    continue
                lv = in_force(W["starts"], c - 60)
                if lv is None or lv.get("code_sha") != run["code"]:
                    skipped_code += 1
                    continue
                shared.add(c)
            for tk, v in run["pnl"].items():
                c = close_epoch(tk)
                if c in shared and tk not in arm_mk[c]:
                    arm_mk[c].add(tk)
                    arm_usd += v
                    arm_n += run["n"].get(tk, 0.0)
        shared = sorted(shared)
        most = max(most, len(shared))
        live_usd = sum(lbc.get(c, 0.0) for c in shared)
        ln = sum(live_n.get(c, 0.0) for c in shared)
        both = sum(len(arm_mk[c] & live_mk[c]) for c in shared)
        arm_only = sum(len(arm_mk[c] - live_mk[c]) for c in shared)
        live_only = sum(len(live_mk[c] - arm_mk[c]) for c in shared)
        if len(shared) < r["min_shared_closes"]:
            det.append("%s: %d shared closes (comparison shown from %d); %d closes dropped as "
                       "different code" % (label, len(shared), r["min_shared_closes"], skipped_code))
            continue
        det.append("%s: %d shared closes; arm (paper) %s = %s c/contract, live (Kalshi) %s = %s "
                   "c/contract; markets both %d, arm only %d, live only %d%s"
                   % (label, len(shared), usd(arm_usd),
                      "-" if not arm_n else "%.2f" % (100 * arm_usd / arm_n), usd(live_usd),
                      "-" if not ln else "%.2f" % (100 * live_usd / ln), both, arm_only, live_only,
                      "" if (arm_only or live_only) else " -- its setting has NOT changed a single trade"))
    na = len(W.get("arms", {}))
    line = ("B6 practice bots vs live: report only. %d arms; most shared closes %d (shown from %d)."
            % (na, most, r["min_shared_closes"]))
    return res("REPORT", "B6", most, max(0, r["min_shared_closes"] - most), line, det, {"arms": na})


EVALS = (("B1", eval_b1), ("B2", eval_b2), ("B3", eval_b3), ("B4", eval_b4),
         ("B5", eval_b5), ("B6", eval_b6))


def evaluate(bars, W):
    out = [eval_freeze(bars["freeze"], W)]
    bmap = {b["id"]: b for b in bars["bars"]}
    for bid, fn in EVALS:
        if bid in bmap:
            out.append(fn(bmap[bid], W))
    return out


def brief(results):
    """<= 8 plain lines for a phone."""
    return [x["line"] for x in results][:8]


def status_md(results, bars, W, data_dir):
    ml = bars.get("multiple_looks", {})
    L = ["# FREEZE status -- %s" % et(W["now"]), "",
         "Generated by `python research/barcheck.py` from `%s` (read-only). Bars: "
         "`results/FREEZE_bars.json`; prose `results/FREEZE_2026-09-22.md`. %s Before its n a "
         "bar's numbers decide nothing."
         % (data_dir, ml.get("summary", "")), "",
         "| bar | status | units so far | still needed |", "|---|---|---|---|"]
    for x in results:
        L.append("| %s | %s | %d | %d |" % (x["id"], x["status"], x["n"], x["need"]))
    L.append("")
    for x in results:
        L += ["## %s -- %s" % (x["id"], x["status"]), "", x["line"], ""]
        L += ["- " + d for d in x["detail"]]
        L.append("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ selftest
def _bars_or_die(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def selftest(bars_path=BARS_PATH):
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok  " + msg)

    print("SELF-TEST -- barcheck (planted PASS, FAIL/null, not-enough, missing-file, empty-day)")
    bars = _bars_or_die(bars_path)
    bm = {b["id"]: b for b in bars["bars"]}
    ck(set(bm) == {"B1", "B2", "B3", "B4", "B5", "B6"}
       and all(k in b for b in bars["bars"] for k in
               ("question", "data", "statistic", "rules", "window_start_utc", "on_pass",
                "on_fail", "on_collecting", "blocks", "mde")),
       "FREEZE_bars.json holds B1-B6, each with question, data, statistic, rules, window, actions, "
       "what it blocks and an MDE")
    ml = bars.get("multiple_looks", {})
    fam = ml.get("null_false_pass", {})
    ck(set(fam) == {"B1-full", "B1-off", "B2", "B3"} and sum(fam.values()) <= ml.get("budget", 0) + 1e-9,
       "multiple looks: the discovery family is B1 x2, B2, B3 and its null false-PASS rates sum "
       "under the budget (%.3f <= %.2f)" % (sum(fam.values()), ml.get("budget", 0)))
    ck(all("never a hedge" in b["blocks"].lower() or b["blocks"].lower().startswith("nothing")
           for b in bars["bars"]), "every bar says it blocks nothing, or never a hedge")
    REG = (bm["B1"].get("scorer") or {}).get("code_sha256")
    ck(isinstance(REG, str) and len(REG) == 64 and bm["B1"]["scorer"].get("function") == "freeze_rows",
       "B1 pins its scorer: earlyhindsight.freeze_rows, code sha256 %s..." % str(REG)[:12])
    ck(all(a.get("utc") and a.get("what") and a.get("seen_before") for a in bars.get("amendments", [])),
       "every amendment after registration is dated and says what post-freeze data was seen first")
    T0 = ep(bars["freeze"]["start_utc"])
    C0 = (T0 // 900 + 1) * 900                     # first quarter hour after T0
    ck(C0 - T0 >= 60, "the first counted close is at least 60 s after the freeze began")
    ck(et(ep("2026-09-22T11:42:12Z")) == "9/22 07:42 ET" and et(ep("2026-12-01T17:00:00Z")) == "12/1 12:00 ET",
       "Eastern for the operator: EDT in September, EST in December")
    ck(is_pin("KXBTC15M-26SEP220900-00") and not is_pin("KXWTI15M-26SEP220900-00")
       and not is_pin("KXGOLD15M-26SEP220900-00") and not is_pin("KXCRYPTOLEAD15M-26SEP220730-XRP"),
       "pin markets are the pin bot's series only: not the commodity 15M bots, not the Coin Race")
    s_in = {"t": iso(T0)}
    ck(in_force([{"t": iso(T0 - 60), "v": 1}, dict(s_in, v=2)], T0)["v"] == 2
       and in_force([s_in], T0 - 1) is None,
       "the start record in force at t includes one written AT t, and none before it")

    def world():
        W = empty_live()
        W.update({"ledger": {}, "ledger_raw": {}, "arms": {}, "hind_rows": None,
                  "hind_src": "planted", "hind_code": REG,
                  "now": T0 + 30 * 86400, "ledger_written": T0, "b5_base": {}})
        return W

    def mkt(W, tk, close, want, result, pnl, n_=50.0):
        W["ledger"][tk] = {"pnl": pnl, "result": result, "close": close,
                           "yes_n": n_ if want == "yes" else 0.0, "no_n": n_ if want == "no" else 0.0}

    def fill(W, tk, close, t, leg, want, n_=50.0, ex=0.96, ask=0.96, age=400.0, tau=None):
        W["fills"].append({"ticker": tk, "close": close, "t": t, "leg": leg, "want": want, "n": n_,
                           "exec": ex, "ask_seen": ask, "tau": tau if tau is not None else
                           (38 if leg == "early" else 12), "age_ms": age})

    # ---------------- helpers are right before anything leans on them
    ck(abs(fisher_greater(6, 73, 0, 101) - 0.0048) < 0.002,
       "exact test reproduces map C5's 6/73 vs 0/101 closes, p ~0.005")
    ck(fisher_greater(2, 50, 2, 50) > 0.5, "and gives p > 0.5 for an even split (null)")
    ck(abs(taker_fee(55, 0.57) - 0.95) < 1e-9, "taker fee 0.07*55*0.57*0.43 = $0.9435 rounds UP to $0.95")
    ck(abs(leg_pnl(55, 0.57, "no", "no") - (55 * 0.43 - 0.95)) < 1e-9
       and abs(leg_pnl(55, 0.57, "no", "yes") - (-55 * 0.57 - 0.95)) < 1e-9,
       "a bought leg pays $1 a contract only if its side won, fee always paid")
    ck(boot_p([1.0] * 50, 500, 1) == 1.0 and boot_p([-1.0] * 50, 500, 1) == 0.0
       and 0.3 < boot_p([1.0, -1.0] * 50, 2000, 1) < 0.7,
       "resampling gives 1 / 0 / ~0.5 for all-up, all-down and balanced worlds")

    # ---------------- FREEZE clock: ledger money, unsettled held back, pre-freeze ignored
    W = world()
    for i in range(5):
        W["armed"].add(C0 + 900 * i)
    W["armed"].add(C0 - 900)                                  # before the freeze
    mkt(W, "A1", C0, "yes", "yes", 2.0)
    mkt(W, "A2", C0 + 900, "yes", "no", -30.0)
    mkt(W, "A0", C0 - 900, "yes", "no", -99.0)                # pre-freeze loss
    fill(W, "A1", C0, T0 + 200, "full", "yes")
    fill(W, "A9", C0 + 1800, T0 + 2000, "full", "yes")        # no ledger row yet
    fz = eval_freeze(bars["freeze"], W)
    ck(fz["n"] == 4 and abs(fz["stat"]["money"] + 28.0) < 1e-9 and fz["stat"]["lost"] == 1,
       "freeze clock: 4 settled closes, -$28 from the ledger, 1 losing; the pre-freeze -$99 and "
       "the unsettled close are not counted (%s)" % fz["line"])

    # ---------------- empty day: nothing after the freeze -> every bar waits, nothing crashes
    W = world()
    W["quote_from"], W["budget_from"] = T0 + 600, T0 + 600
    rs = evaluate(bars, W)
    ck(all(x["status"] in ("COLLECTING", "PENDING", "REPORT") and x["n"] == 0 for x in rs),
       "empty day: 0 units everywhere, every bar COLLECTING / PENDING / REPORT, no PASS or FAIL (%s)"
       % ", ".join("%s %s" % (x["id"], x["status"]) for x in rs))

    # ---------------- B1
    b1 = bm["B1"]
    N1 = b1["rules"]["min_closes"]

    def b1_world(nc, pattern, nested=False, lo_of=None):
        W = world()
        rows = []
        for i in range(nc):
            c = C0 + 900 * i
            W["armed"].add(c)
            live, full, off = pattern(i)
            full_lo = full if lo_of is None else lo_of(i, live, full)
            mkt(W, "B1-%d" % i, c, "yes", "yes" if live >= 0 else "no", live)
            fill(W, "B1-%d" % i, c, c - 40, "early", "yes")
            rows.append({"close": c, "live": live, "pol": {"FULL": full, "OFF": off},
                         "lo": {"FULL": full_lo}} if nested
                        else {"close": c, "live": live, "full": full, "off": off,
                              "full_lo": full_lo, "mismatch": 0, "not_in_ledger": 0})
        W["hind_rows"] = {"rows": rows}
        return W

    def early_bleeds(i):                      # a third-size leg losing $10 on every 10th close
        if i % 10 == 0:
            return (-10.0, -30.0, 0.0)
        if i % 10 < 4:
            return (0.2, 0.6, 0.0)
        return (0.0, 0.0, 0.0)

    def early_pays(i):                        # a third-size leg earning $1 on 4 closes in 10
        return (1.0, 3.0, 0.0) if i % 10 < 4 else (0.0, 0.0, 0.0)
    rng = random.Random(7)

    def null_noise(i):
        d = rng.uniform(-0.5, 0.5)
        return (1.0, 1.0 + d, 1.0 - d / 2.0)
    x = eval_b1(b1, b1_world(N1 + 20, early_bleeds))
    ck(x["status"] == "PASS" and "off" in x["line"],
       "B1 PASS world: a third-size leg that bleeds -> switch to OFF (%s)" % x["line"])
    x = eval_b1(b1, b1_world(N1 + 20, early_bleeds, nested=True))
    ck(x["status"] == "PASS" and "off" in x["line"],
       "B1 reads earlyhindsight's own row shape too (live + pol{FULL, OFF} + lo{FULL})")
    x = eval_b1(b1, b1_world(N1 + 20, early_pays))
    ck(x["status"] == "PASS" and "full" in x["line"],
       "B1 PASS world: a leg that pays 4 closes in 10 -> switch to FULL (%s)" % x["line"])
    x = eval_b1(b1, b1_world(N1 + 20, early_pays, lo_of=lambda i, live, full: live))
    ck(x["status"] == "FAIL" and x["stat"]["full"]["boot_p"] == 1.0,
       "B1: the same FULL gain resting entirely on unlogged depth (FULL-lo == the third) cannot "
       "pass -- FULL must also pass on FULL-lo (%s)" % x["line"])
    x = eval_b1(b1, b1_world(N1 + 20, null_noise))
    ck(x["status"] == "FAIL", "B1 null world: noise around zero -> FAIL, keep the third (%s)" % x["line"])
    x = eval_b1(b1, b1_world(100, early_bleeds))
    ck(x["status"] == "COLLECTING" and x["need"] == N1 - 100,
       "B1 not-enough world: the same strong effect at 100 closes decides nothing (need %d more)" % (N1 - 100))

    def one_close(i):                         # every close a hair ahead, one close enormous
        return (0.0, 0.0, 200.0) if i == 5 else (0.0, 0.0, 0.02)
    x = eval_b1(b1, b1_world(N1 + 20, one_close))
    ck(x["status"] == "FAIL" and x["stat"]["off"]["boot_p"] == 1.0 and x["stat"]["off"]["mean"] > 0.25,
       "B1: a lead that is ONE close cannot pass, even at resampled P 1.00 (single-close guard)")

    def noisy(i):                             # mean +$0.30 a close above the $0.25 floor, sd $5
        return (0.0, 0.0, 5.3 if i % 2 == 0 else -4.7)
    x = eval_b1(b1, b1_world(N1 + 20, noisy))
    ck(x["status"] == "FAIL" and x["stat"]["off"]["mean"] >= 0.25 and x["stat"]["off"]["boot_p"] < 0.975,
       "B1: a mean over the floor that is mostly noise (resampled P %.2f < 0.975) does not pass"
       % x["stat"]["off"]["boot_p"])
    W = b1_world(N1 + 20, early_bleeds)
    for r_ in W["hind_rows"]["rows"]:
        r_["live"] += 5.0                                     # scorer disagrees with Kalshi
    ck(eval_b1(b1, W)["status"] == "INVALID", "B1: a scorer whose live column does not match the ledger "
       "is INVALID")
    W = b1_world(N1 + 20, early_bleeds)
    W["hind_rows"]["rows"] = W["hind_rows"]["rows"][:50] + W["hind_rows"]["rows"][60:]
    ck(eval_b1(b1, W)["status"] == "INVALID", "B1: closes with a 45 s fill but no scorer row -> INVALID")
    W = b1_world(N1 + 20, early_bleeds)
    W["hind_rows"]["rows"][7]["mismatch"] = 1
    x = eval_b1(b1, W)
    ck(x["status"] == "INVALID" and "differs from the logged fills" in x["line"],
       "B1: ONE sample close where the scorer's ledger count differs from the logged fills (the "
       "check that caught the 09-22 side bug; LIVE stays exact) -> INVALID, though every live "
       "column reconciles (%s)" % x["line"])
    W = b1_world(N1 + 20, early_bleeds)
    W["hind_rows"]["rows"][9]["not_in_ledger"] = 2
    ck(eval_b1(b1, W)["status"] == "INVALID", "B1: log fills with no ledger row on a sample close -> INVALID")
    W = b1_world(N1 + 20, early_bleeds)
    W["hind_code"] = "0" * 64
    x = eval_b1(b1, W)
    ck(x["status"] == "INVALID" and "not the registered one" in x["line"],
       "B1: a scorer edited after registration (code hash differs) -> INVALID until the edit is "
       "registered as a dated amendment")
    W = b1_world(N1 + 20, early_bleeds)
    W["hind_rows"], W["hind_src"] = None, "not importable"
    ck(eval_b1(b1, W)["status"] == "PENDING", "B1 without the scorer is PENDING, never a guess")

    # fixed sample: a null first 300 closes followed by 300 bleeding closes stays FAIL
    def late_bleed(i):
        return null_noise(i) if i < N1 else early_bleeds(i)
    x = eval_b1(b1, b1_world(2 * N1, late_bleed))
    ck(x["status"] == "FAIL" and x["n"] == N1,
       "B1 decides ONCE on its first %d closes: later closes cannot turn a FAIL into a PASS" % N1)
    # a setting change restarts the window
    W = b1_world(N1 + 20, early_bleeds)
    W["starts"] = [{"t": iso(T0 - 30), "early_frac": 0.333, "code_sha": "a"},
                   {"t": iso(C0 + 900 * 99 + 30), "early_frac": 1.0, "code_sha": "a"},
                   {"t": iso(C0 + 900 * 150 + 30), "early_frac": 1.0, "code_sha": "b"}]
    x = eval_b1(b1, W)
    ck(x["status"] == "COLLECTING" and x["n"] == N1 + 20 - 100 and "early_frac 0.333->1.0" in x["detail"][0],
       "B1: early_frac changing mid-freeze restarts the window at the change; a code-only change "
       "does not (%d closes after it)" % x["n"])

    # ---------------- B1 scorer entry point (planted module)
    class FakeEH(object):
        got = {}

        @staticmethod
        def freeze_rows(since_s, data_dir, now_s=None, ledger_rows=None):
            FakeEH.got = {"since": since_s, "snap": ledger_rows}
            return {"rows": [{"close": C0, "live": 1.0, "full": 2.0, "off": 0.5, "full_lo": 1.5,
                              "mismatch": 0, "not_in_ledger": 0, "flagged": 1}], "diag": {}}
    out, src = scorer_rows(FakeEH, {"function": "freeze_rows"}, T0, T0 + 86400, "/nowhere",
                           ledger_rows={"k": 1})
    ck(src == "earlyhindsight.freeze_rows" and FakeEH.got["snap"] == {"k": 1}
       and _rows(out)[C0] == {"live": 1.0, "full": 2.0, "off": 0.5, "full_lo": 1.5, "tickers": None,
                              "mismatch": 0, "not_in_ledger": 0, "flagged": 1},
       "B1 calls earlyhindsight.freeze_rows with barcheck's OWN ledger snapshot and reads its "
       "full / off / full_lo / mismatch / not_in_ledger columns")

    # ---------------- B2
    b2 = bm["B2"]
    NF = b2["rules"]["min_fresh_closes"]

    def b2_world(nf, lf, no, lo, pre=0, loss=-60.0):
        W = world()
        i = 0
        for g, nn, ll, age in (("f", nf, lf, 60.0), ("o", no, lo, 400.0)):
            for j in range(nn):
                c = C0 + 900 * i
                i += 1
                W["armed"].add(c)
                lost = j < ll
                tk = "B2%s-%d" % (g, j)
                mkt(W, tk, c, "yes", "no" if lost else "yes", loss if lost else 1.7)
                fill(W, tk, c, c - 40, "early", "yes", age=age)
        for j in range(pre):                                  # pre-freeze fresh losers
            c = C0 - 900 * (j + 1)
            tk = "B2p-%d" % j
            mkt(W, tk, c, "yes", "no", -60.0)
            fill(W, tk, c, c - 40, "early", "yes", age=60.0)
        return W
    x = eval_b2(b2, b2_world(NF + 10, 9, NF + 10, 0))
    ck(x["status"] == "PASS", "B2 PASS world: fresh 9/%d lost vs older 0/%d, fresh net negative (%s)"
       % (NF, NF, x["line"]))
    W = b2_world(NF + 10, 9, NF + 10, 0)
    cu = C0 + 900 * 5 + 450                                   # an unsettled fresh close, early on
    fill(W, "B2u", cu, cu - 40, "early", "yes", age=60.0)
    x = eval_b2(b2, W)
    ck(x["status"] == "COLLECTING" and "stopped at an unsettled close" in x["detail"][-1],
       "B2 stops at the first UNSETTLED close: the same PASS world with one unsettled close early "
       "on waits for it, rather than skipping ahead to later closes (%s)" % x["line"])
    x = eval_b2(b2, b2_world(NF + 10, 2, NF + 10, 2, pre=100))
    ck(x["status"] == "FAIL",
       "B2 null world: 2 vs 2 losses -> FAIL, and 100 planted pre-freeze fresh losers are ignored")
    x = eval_b2(b2, b2_world(NF + 10, 3, NF + 10, 2, loss=-200.0))
    ck(x["status"] == "FAIL" and x["stat"]["value"] > 0,
       "B2: fresh losses that were merely BIG (3 v 2 closes, refusing would have kept %s) do not pass "
       "without the loss-rate test" % usd(x["stat"]["value"]))
    x = eval_b2(b2, b2_world(30, 6, 30, 0))
    ck(x["status"] == "COLLECTING", "B2 not-enough world: 6/30 vs 0/30 decides nothing yet")
    W = b2_world(NF + 10, 2, NF + 10, 2)
    for j in range(NF + 10):                                  # a second, later batch of fresh losers
        c = C0 + 900 * (3 * NF + j)
        tk = "B2late-%d" % j
        mkt(W, tk, c, "yes", "no", -60.0)
        fill(W, tk, c, c - 40, "early", "yes", age=60.0)
    x = eval_b2(b2, W)
    ck(x["status"] == "FAIL" and x["stat"]["fresh"][1] == NF + 10,
       "B2 decides on the closes up to the point both groups reach %d; later losers do not count" % NF)

    # ---------------- B3
    b3 = bm["B3"]
    NB3 = b3["rules"]["min_flagged_closes"]
    C3 = (ep(b3["window_start_utc"]) // 900 + 1) * 900       # B3 opens with the quote log

    def b3_world(nflag, lflag, nother, lother, quotes=True, ask=0.08):
        """Flagged closes spread evenly among the others, as they arrive live."""
        W = world()
        tot = nflag + nother
        stride = tot // nflag
        flags = {k * stride for k in range(nflag)}
        fi = oi = 0
        for j in range(tot):
            c = C3 + 900 * j
            W["armed"].add(c)
            flag = j in flags
            if flag:
                lost = fi < lflag
                fi += 1
            else:
                lost = oi % max(1, nother // max(1, lother)) == 0 and oi // max(1, nother // max(1, lother)) < lother
                oi += 1
            tk = "B3-%d" % j
            t = c - 20
            mkt(W, tk, c, "yes", "no" if lost else "yes", -48.0 if lost else 2.0)
            fill(W, tk, c, t, "full", "yes", ex=0.93 if flag else 0.96, ask=0.96)
            if flag and quotes:
                W["quotes"][tk] = [{"t": t + k, "ask": ask, "size": 500.0, "belief": 0.9,
                                    "side": "no"} for k in range(5)]
        if quotes:
            W["quote_from"] = T0 + 30
        return W
    x = eval_b3(b3, b3_world(NB3 + 4, 8, 300, 6))
    ck(x["status"] == "PASS", "B3 PASS world: flagged fills lose 8/%d, 8c insurance -> insuring pays (%s)"
       % (NB3, x["line"]))
    x = eval_b3(b3, b3_world(NB3 + 4, 1, 300, 6))
    ck(x["status"] == "FAIL" and x["stat"]["value"] < 0,
       "B3 null world: flagged fills lose like the rest -> insurance costs money -> FAIL")
    x = eval_b3(b3, b3_world(NB3 + 4, 8, 300, 6, ask=0.70))
    ck(x["status"] == "FAIL" and x["stat"]["p"] < 0.01 and x["stat"]["value"] < 0,
       "B3: flagged fills really do lose more, but at 70c insurance it costs money -> FAIL")
    x = eval_b3(b3, b3_world(10, 5, 300, 6))
    ck(x["status"] == "COLLECTING", "B3 not-enough world: 10 priced flagged closes decides nothing")
    x = eval_b3(b3, b3_world(NB3 + 4, 8, 300, 6, quotes=False))
    ck(x["status"] == "PENDING" and x["stat"]["flag"] == [8, NB3 + 4],
       "B3 with no quote log is PENDING but still counts the flagged closes")
    # matched hedge: 50 flagged + a 50 top-up AFTER the fill; the belief hedge then
    # hedged all 100 at 60c. Insuring the 50 at 8c replaces only HALF of that hedge.
    W = world()
    W["quote_from"] = T0 + 30
    c = C3
    W["armed"].add(c)
    mkt(W, "M3", c, "yes", "no", -40.0, n_=100.0)
    fill(W, "M3", c, c - 30, "full", "yes", n_=50.0, ex=0.93, ask=0.96)
    fill(W, "M3", c, c - 25, "full", "yes", n_=50.0, ex=0.96, ask=0.96)
    W["hedges"].append({"ticker": "M3", "t": c - 20, "side": "no", "price": 0.60, "n": 100.0})
    W["quotes"]["M3"] = [{"t": c - 30 + k, "ask": 0.08, "size": 500.0, "belief": 0.9, "side": "no"}
                         for k in range(5)]
    x = eval_b3(b3, W)
    want_v = leg_pnl(50.0, 0.08, "no", "no") - leg_pnl(50.0, 0.60, "no", "no")
    ck(abs(x["stat"]["value"] - want_v) < 1e-9,
       "B3 subtracts only the real hedge contracts that covered the INSURED 50 (half of the 100 "
       "hedged), not the top-up's: %s (got %s)" % (usd(want_v), usd(x["stat"]["value"])))

    # ---------------- B4
    b4 = bm["B4"]
    s4 = ep(b4["window_start_utc"])

    def ev_quotes(t, path):
        """path = [(belief, ask)] one per second from t."""
        return [{"t": t + k, "belief": b, "ask": a, "size": 500.0, "side": "no"}
                for k, (b, a) in enumerate(path)]
    A = [(0.9, 0.05), (0.45, 0.40), (0.45, 0.40), (0.9, 0.05), (0.95, 0.03)]     # dip, recovers, won
    B = [(0.9, 0.05), (0.5, 0.40), (0.27, 0.65), (0.8, 0.10), (0.95, 0.03)]     # deeper dip, won
    C = [(0.9, 0.05), (0.5, 0.45), (0.28, 0.70), (0.2, 0.78), (0.05, 0.95)]     # collapse, lost

    def b4_world(kinds, per_close=1):
        W = world()
        W["quote_from"] = s4 + 60
        for j, kd in enumerate(kinds):
            c = C0 + 900 * (j // per_close)
            W["armed"].add(c)
            tk = "B4-%d" % j
            lost = kd is C
            mkt(W, tk, c, "yes", "no" if lost else "yes", -40.0 if lost else 2.0)
            fill(W, tk, c, c - 20, "full", "yes")
            W["quotes"][tk] = ev_quotes(c - 20, kd)
        return W
    x = eval_b4(b4, b4_world([A] * 6 + [B] * 4 + [C] * 2))
    ck(x["stat"]["move"] == "PASS" and x["status"] == "PASS",
       "B4 PASS world: shallow dips that recover -> 0.25 beats 0.30 and 0.60 (%s)" % x["line"])
    x = eval_b4(b4, b4_world([A] * 2 + [C] * 10))
    ck(x["stat"]["move"] == "FAIL" and "Leader 0.60" in x["line"],
       "B4 FAIL world: real collapses dominate -> 0.60 is shown ahead under the same guard (%s)"
       % x["line"])
    x = eval_b4(b4, b4_world([A] * 5 + [C] * 1 + [A] * 4))
    ck(x["stat"]["move"] == "FAIL" and "no change proposed" in x["line"],
       "B4: 0.25 trails 0.30 only through ONE collapse -> FAIL, but 0.30's lead fails the same "
       "single-event guard: weak evidence, no change proposed (%s)" % x["line"])
    x = eval_b4(b4, b4_world([A] * 3 + [C] * 2))
    ck(x["stat"]["move"] == "COLLECTING", "B4 not-enough world: 5 events decide nothing")
    x = eval_b4(b4, b4_world([A] * 12 + [B] * 8, per_close=2))
    ck(x["stat"]["events"] == 10 and x["stat"]["move"] == "PASS",
       "B4 counts EVENTS BY CLOSE: 20 dipping markets in 10 closes are 10 events, not 20")
    x = eval_b4(b4, b4_world([A] * 6 + [B] * 4 + [C] * 30))
    ck(x["stat"]["move"] == "PASS" and x["stat"]["events"] == 10,
       "B4 move bar decides on its FIRST 10 dips; 30 later collapses do not reopen it")
    W = b4_world([A] * 6)
    W["quote_from"] = None
    ck(eval_b4(b4, W)["stat"]["move"] == "PENDING", "B4 move bar is PENDING without the quote log")
    # safety rules, on real alarms
    W = world()
    for j in range(200):
        c = C0 + 900 * j
        tk = "S-%d" % j
        lost = j < 29
        mkt(W, tk, c, "yes", "no" if lost else "yes", -20.0 if lost else 2.0)
        fill(W, tk, c, c - 20, "full", "yes")
        if j < 30:                                    # 29 caught + 1 false alarm
            W["alarms"].append({"ticker": tk, "t": c - 15, "want": "yes", "belief": 0.2, "n": 50.0})
            W["hedges"].append({"ticker": tk, "t": c - 15, "side": "no", "price": 0.6, "n": 50.0})
    ck(eval_b4(b4, W)["stat"]["safety"] == "FAIL",
       "B4 safety: 1 false alarm in the 30 positions held up to the 30th alarm is 3.3% > 3% -> FAIL; "
       "the 170 positions after it cannot dilute the rate")
    W = world()
    for j in range(200):
        c = C0 + 900 * j
        tk = "S-%d" % j
        lost = j < 29
        mkt(W, tk, c, "yes", "no" if lost else "yes", -20.0 if lost else 2.0)
        fill(W, tk, c, c - 20, "full", "yes")
        if j < 29 or j == 150:
            W["alarms"].append({"ticker": tk, "t": c - 15, "want": "yes", "belief": 0.2, "n": 50.0})
            W["hedges"].append({"ticker": tk, "t": c - 15, "side": "no", "price": 0.6, "n": 50.0})
    x = eval_b4(b4, W)
    ck(x["stat"]["safety"] == "PASS", "B4 safety PASS world: 1 false alarm in 151 held, 40c back, all filled")
    W["hedges"].append({"ticker": "S-40", "t": C0, "side": "no", "price": 1.0, "n": 5.0})
    x = eval_b4(b4, W)
    ck(x["stat"]["safety"] == "FAIL" and x["status"] == "FAIL",
       "B4 safety: ONE hedge at $1.00 fails at any n (it can only add to a loss)")
    W = world()
    for j in range(100):
        c = C0 + 900 * j
        tk = "S-%d" % j
        mkt(W, tk, c, "yes", "yes" if j < 10 else "no", 1.0)
        fill(W, tk, c, c - 20, "full", "yes")
        if j < 30:
            W["alarms"].append({"ticker": tk, "t": c - 15, "want": "yes", "belief": 0.2, "n": 50.0})
            W["hedges"].append({"ticker": tk, "t": c - 15, "side": "no", "price": 0.6, "n": 50.0})
    ck(eval_b4(b4, W)["stat"]["safety"] == "FAIL", "B4 safety FAIL world: 10 false alarms in 30 held")

    # ---------------- B5
    b5 = bm["B5"]
    r5 = b5["rules"]
    C5 = (ep(b5["window_start_utc"]) // 900 + 1) * 900       # B5 opens with the budget field
    ref5 = r5["era_b_per_close"]

    def b5_world(nc, gates, late_n=10.0, field=True, unpriced=()):
        W = world()
        W["budget_from"] = T0 + 30 if field else None
        W["b5_base"] = {"era_b": (ref5 - 2.0, 600), "post_fix": (9.7, 200)}
        for i in range(nc):
            c = C5 + 900 * i
            W["armed"].add(c)
            tk = "B5-%d" % i
            mkt(W, tk, c, "yes", "yes", 0.3)
            fill(W, tk, c, c - 10, "full", "yes", n_=late_n, tau=10)
            for g, k in gates:
                W["refused"].append({"close": c, "ticker": tk + g, "t": c - 12, "gate": g, "tau": 12.0,
                                     "budget_left": 30.0, "priced": True,
                                     "ask": 0.95, "ask_size": k, "size_now": 80.0})
            for g, k in unpriced:
                W["refused"].append({"close": c, "ticker": tk + g, "t": c - 12, "gate": g, "tau": 12.0,
                                     "budget_left": 0.0 if g == "close_budget" else 30.0,
                                     "priced": False, "ask": None, "ask_size": None, "size_now": k})
        return W
    W = b5_world(120, [("edge_floor", 14.0), ("jump_gate", 3.0)])
    W["refused"].append({"close": C5, "ticker": "far", "t": C5 - 40, "gate": "edge_floor", "tau": 40.0,
                         "budget_left": 30.0, "ask": 0.95, "ask_size": 500.0, "size_now": 80.0})
    W["refused"].append({"close": C5, "ticker": "dear", "t": C5 - 10, "gate": "edge_floor", "tau": 10.0,
                         "budget_left": 30.0, "ask": 0.99, "ask_size": 500.0, "size_now": 80.0})
    W["refused"].append({"close": C5, "ticker": "B5-0", "t": C5 - 23, "gate": "max_per_market",
                         "tau": 23.0, "budget_left": 79.0, "priced": False, "ask": None,
                         "ask_size": None, "size_now": 79.0})
    x = eval_b5(b5, W)
    ck(any("read 203, kept 200; dropped: max_per_market (the market already held its buys) 1, "
           "not 3-30 s left 1, our side not offered at 90-98c 1" in d for d in x["detail"]),
       "B5's filter prints its own null: 203 refusals read on its 100 closes; the 45 s one, the "
       "99c one and the max_per_market one (that market already held SIZE) dropped")
    ck(x["status"] == "PASS" and "edge_floor" in x["line"],
       "B5 PASS world: one PRICED gate refuses 80%% of the volume and covers the gap -> named (%s)"
       % x["line"])
    # the refusal shapes pinrun really writes (2026-09-22 live log): a reader that only knew
    # no_offer's wanted_side/<side>_ask kept 0 of 134 real refusals
    shapes = [({"gate": "no_offer", "wanted_side": "no", "yes_ask": 0.001, "no_ask": None,
                "yes_ask_size": 1034.6, "no_ask_size": None}, (0.0, 0.0)),
              ({"gate": "no_offer", "wanted_side": "no", "no_ask": 0.95, "no_ask_size": 30.0}, (30.0, 30.0)),
              ({"gate": "price_ceiling", "want": "no", "price": 0.991, "size": 7.17}, (0.0, 0.0)),
              ({"gate": "edge_floor", "want": "no", "price": 0.95, "size": 124.0}, (78.0, 78.0)),
              ({"gate": "depth_floor", "want": "no", "price": 0.96, "offered": 0.02, "wanted": 78.0,
                "size": 78.0}, (0.02, 0.02)),
              ({"gate": "close_budget", "spent": 156.0, "budget": 156.0, "size": 78.0}, (0.0, 78.0)),
              # R4 (2026-09-22): the base-budget skip. It refuses AFTER the book is read, so
              # it is a PRICED gate and must carry `size` -- the first version wrote only
              # `take_n`, which refusal_price() does not read, so every such row landed in
              # _b5_view's "no size" bucket and B5 still could not see the refusal the record
              # was added to show it. (78, 78), not (0, 0).
              ({"gate": "close_budget_base", "want": "no", "price": 0.95, "size": 78.0,
                "take_n": 78.0, "base": 156.0, "spent": 156.0, "fair": 0.999}, (78.0, 78.0)),
              # ...and the same record WITHOUT `size` is the defect: dropped, both bounds 0.
              ({"gate": "close_budget_base", "want": "no", "price": 0.95,
                "take_n": 78.0, "base": 156.0, "spent": 156.0}, (0.0, 0.0)),
              ({"gate": "book_stale", "age_ms": 2029}, (0.0, 78.0)),
              ({"gate": "max_per_market", "fills": 2}, (0.0, 0.0)),
              ({"gate": "confidence", "fair": 0.02}, (0.0, 0.0))]
    got = []
    for rec_, (want_lo, want_hi) in shapes:
        rp = refusal_price(dict(rec_, tau=12, budget_left=40.0, size_now=78.0))
        Wx = world()
        Wx["armed"].add(C5)
        Wx["refused"].append(dict(rp, close=C5, ticker="S", t=C5 - 12, gate=rec_["gate"], tau=12.0,
                                  budget_left=40.0, size_now=78.0))
        _pc, rlo, rhi, _l, _h, _d = _b5_view(r5, Wx, [C5])
        got.append(abs(rlo - want_lo) < 1e-9 and abs(rhi - want_hi) < 1e-9)
    ck(all(got), "B5 reads every refusal shape pinrun writes, as (low, high): no_offer not offered "
       "(0, 0) / offered 30 (30, 30); price_ceiling at 99.1c dropped; edge_floor 124 offered -> "
       "our 78; depth_floor 0.02; close_budget and book_stale refused before the book was read -> "
       "(0, 78); close_budget_base WITH size (78, 78) and the same record without it dropped, "
       "which is why pinrun must write it; max_per_market and confidence dropped (%s)" % got)
    x = eval_b5(b5, b5_world(320, [("edge_floor", 4.5), ("jump_gate", 4.5), ("depth_floor", 4.5),
                                   ("rebuy_band", 4.5)]))
    ck(x["status"] == "FAIL", "B5 FAIL world: four causes at 25% each, 300 closes -> no single answer")
    x = eval_b5(b5, b5_world(50, [("edge_floor", 40.0)]))
    ck(x["status"] == "COLLECTING", "B5 not-enough world: 50 closes decides nothing")
    x = eval_b5(b5, b5_world(120, [("edge_floor", 40.0)], field=False))
    ck(x["status"] == "PENDING", "B5 without the budget field is PENDING")
    x = eval_b5(b5, b5_world(120, [], late_n=ref5 * 0.85))
    ck(x["status"] == "PASS" and "came back" in x["line"],
       "B5: buying back at 85% of the higher reference -> 'the leg was using the budget'")
    x = eval_b5(b5, b5_world(120, [("edge_floor", 1.0)]))
    ck(x["status"] == "PASS" and "not our gates" in x["line"],
       "B5: refusals far below the gap on BOTH bounds -> 'the offers were not there'")
    x = eval_b5(b5, b5_world(120, [("edge_floor", 1.0)], unpriced=[("book_stale", 80.0)]))
    ck(x["status"] == "COLLECTING" and "not our gates" not in x["line"] and "book_stale" not in x["line"],
       "B5: few PRICED refusals but many stale-book refusals (volume unknown, up to our size) -> "
       "no answer: 'the offers were not there' needs the HIGH bound under half the gap, and a "
       "stale-data gate is never named (%s)" % x["line"])
    x = eval_b5(b5, b5_world(120, [("edge_floor", 16.0)], unpriced=[("close_budget", 80.0)]))
    ck(x["status"] == "COLLECTING" and "close_budget" not in x["line"],
       "B5: an UNPRICED capacity gate holding most of the high bound is never named -- its volume "
       "is unknown (%s)" % x["line"])
    x = eval_b5(b5, b5_world(120, [("edge_floor", 10.0)], unpriced=[("close_budget", 8.0)]))
    ck(x["status"] == "COLLECTING" and "edge_floor" not in x["line"],
       "B5: a priced gate that dominates but whose measured volume does not cover 80%% of the gap "
       "on its own is not named (the unpriced 8 cannot make up the coverage) (%s)" % x["line"])
    W = b5_world(120, [], late_n=ref5 * 0.85)
    W["b5_base"] = {"era_b": (ref5 * 1.2, 600)}
    ck("came back" not in eval_b5(b5, W)["line"],
       "B5 uses the HIGHER of the two references: 85% of map 11's is not 'came back' when this "
       "file's own era-B count is 20% higher")

    # ---------------- B6
    b6 = bm["B6"]
    W = world()
    w6 = ep(b6["window_start_utc"])
    W["starts"] = [{"t": iso(w6 - 3600), "code_sha": "old"}, {"t": iso(T0 + 600), "code_sha": "new"}]
    runs_x = [{"log": "a", "code": "old", "start": w6, "armed": set(), "pnl": {}, "n": {}},
              {"log": "b", "code": "new", "start": T0 + 1100, "armed": set(), "pnl": {}, "n": {}}]
    runs_e = [{"log": "c", "code": "new", "start": T0 + 1100, "armed": set(), "pnl": {}, "n": {}}]
    for i in range(-40, 80):
        c = C0 + 900 * i
        if c < w6 + 60:
            continue
        W["armed"].add(c)
        if c <= T0 + 1100:
            runs_x[0]["armed"].add(c)             # old code, still running after live moved
        if c > T0 + 600:
            runs_x[1]["armed"].add(c)
            runs_e[0]["armed"].add(c)
    W["arms"] = {"arm-x": {"early": False, "runs": runs_x, "sig": ()},
                 "arm-early-x": {"early": True, "runs": runs_e, "sig": ()}}
    x = eval_b6(b6, W)
    nx = len([c for c in W["armed"] if c >= w6 + 60 and c <= T0 + 600]) + \
        len([c for c in runs_x[1]["armed"] if c - 60 >= T0 + 1100])
    mism = len([c for c in runs_x[0]["armed"] if c - 60 >= T0 + 600])
    ck(mism >= 1 and x["status"] == "REPORT" and any(d.startswith("arm-x: %d shared" % nx) for d in x["detail"]),
       "B6: a close counts only when arm and live ran the same code (%d shared for arm-x; %d close(s) "
       "dropped where live had moved to new code and the arm had not)" % (nx, mism))
    ck(any("NOT changed a single trade" in d for d in x["detail"]),
       "B6 null: an arm that traded exactly what live traded is flagged as measuring nothing")

    # ---------------- files on disk -> the same world; then a missing-file world
    import copy
    import tempfile
    tmp = tempfile.mkdtemp(prefix="barcheck-")
    try:
        c1 = C0
        S_MIN = min(ep(b_["window_start_utc"]) for b_ in bars["bars"])   # load_live's since
        tk = "KXBTC15M-%s" % time.strftime("%y%b%d%H%M", time.gmtime(c1 + et_offset(c1))).upper() + "-00"
        ck(close_epoch(tk) == c1, "ticker clock is Eastern: %s closes at %s" % (tk, et(c1)))
        live = [{"kind": "start", "mode": "live", "pin": 0.995, "early_frac": 0.333,
                 "code_sha": "abc", "t": iso(T0 - 20)},
                {"kind": "order", "ticker": tk, "want": "no", "leg": "full", "filled": 7.0,
                 "exec_price": 0.96, "ask_seen": 0.96, "tau_at_send": 20, "t": iso(S_MIN - 100)},
                {"kind": "signal", "ticker": tk, "want": "no", "price": 0.97, "level_age_ms": 80,
                 "t": iso(c1 - 41)},
                {"kind": "order", "ticker": tk, "want": "no", "leg": "early", "filled": 30.0,
                 "exec_price": 0.97, "ask_seen": 0.97, "tau_at_send": 40, "t": iso(c1 - 40)},
                {"kind": "signal", "ticker": tk, "want": "no", "price": 0.97, "level_age_ms": 5,
                 "t": iso(c1 - 21)},
                {"kind": "order", "ticker": tk, "want": "no", "leg": "full", "filled": 10.0,
                 "exec_price": 0.96, "ask_seen": 0.96, "tau_at_send": 20, "t": iso(c1 - 20)},
                {"kind": "order", "ticker": tk, "want": "no", "leg": "full", "filled": 5.0,
                 "exec_price": 0.96, "ask_seen": 0.96, "tau_at_send": 8, "t": iso(c1 - 8)},
                {"kind": "hedge_quote", "ticker": tk, "side": "yes", "ask": 0.04, "size": 99.0,
                 "tau": 39, "belief": 0.97, "t": iso(c1 - 39)},
                {"kind": "refused", "gate": "edge_floor", "ticker": tk, "close_s": c1, "tau": 12,
                 "budget_left": 20.0, "wanted_side": "no", "no_ask": 0.95, "no_ask_size": 10.0,
                 "size_now": 80.0, "t": iso(c1 - 12)},
                {"kind": "close_summary", "close": c1, "t": iso(c1 + 5)}]
        with open(os.path.join(tmp, "pinrun-live-X.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in live) + "\nnot json\n")
        wti = "KXWTI15M-%s" % tk.split("-", 1)[1]
        sett = {"%s|x" % tk: {"ticker": tk, "market_result": "no", "no_count_fp": "40.00",
                              "no_total_cost_dollars": "38.700000", "yes_count_fp": "10.00",
                              "yes_total_cost_dollars": "0.500000", "fee_cost": "0.050000",
                              "revenue": 0, "settled_time": iso(c1 + 20)},
                "KXCRYPTOLEAD15M-X-XRP|y": {"ticker": "KXCRYPTOLEAD15M-26SEP220730-XRP",
                                            "market_result": "yes", "yes_count_fp": "1.00",
                                            "yes_total_cost_dollars": "0.5", "fee_cost": "0"},
                "%s|z" % wti: {"ticker": wti, "market_result": "yes", "yes_count_fp": "9.00",
                               "yes_total_cost_dollars": "8.1", "fee_cost": "0"}}
        with open(os.path.join(tmp, "kalshi_ledger.json"), "w", encoding="utf-8") as fh:
            json.dump({"settlements": sett, "written": iso(c1 + 30)}, fh)
        pl = "pinrun-paper-%s.jsonl" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(T0 - 10))
        paper = [{"kind": "start", "mode": "paper", "pin": 0.97, "early_frac": 0.333, "code_sha": "abc",
                  "t": iso(T0 - 10)},
                 {"kind": "signal", "live": False, "ticker": tk, "take_n": 20.0, "t": iso(c1 - 20)},
                 {"kind": "settled", "ticker": tk, "pnl_c": 55.0, "t": iso(c1 + 20)},
                 {"kind": "settled", "ticker": tk, "pnl_c": 55.0, "t": iso(c1 + 20)},
                 {"kind": "close_summary", "close": c1, "t": iso(c1 + 5)}]
        with open(os.path.join(tmp, pl), "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in paper) + "\n")
        with open(os.path.join(tmp, "arm-pinx.out"), "w", encoding="utf-8") as fh:
            fh.write("  log C:\\x\\%s\n" % pl)
        # a planted scorer module on disk: B1 must import it, hash its FILE, and
        # hand it barcheck's own ledger snapshot
        fake_mod = "eh_fake_selftest_%d" % os.getpid()
        with open(os.path.join(tmp, fake_mod + ".py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("SEEN = {}\n"
                     "def freeze_rows(since_s, data_dir, now_s=None, ledger_rows=None):\n"
                     "    SEEN['snap'] = ledger_rows\n"
                     "    return {'rows': [{'close': %d, 'live': 0.75, 'full': 0.75, 'off': 0.75,\n"
                     "                      'full_lo': 0.75, 'tickers': ['%s']}], 'diag': {}}\n"
                     % (c1, tk))
        bars_x = copy.deepcopy(bars)
        for b_ in bars_x["bars"]:
            if b_["id"] == "B1":
                b_["scorer"]["module"] = fake_mod
        Wd = load_world(bars_x, tmp, now=T0 + 86400, hindsight_dir=tmp)
        fl = Wd["fills"]
        ck(len(fl) == 3 and fl[0]["age_ms"] == 80 and fl[0]["leg"] == "early" and fl[1]["age_ms"] == 5
           and fl[2]["age_ms"] is None
           and Wd["armed"] == {c1} and len(Wd["quotes"].get(tk, [])) == 1
           and Wd["budget_from"] is not None and len(Wd["refused"]) == 1,
           "loader: each order paired with ITS signal (80 ms, 5 ms; none within 3 s -> no age), close, "
           "quote, refusal; an order written before the earliest bar window is not read")
        ck(set(Wd["ledger"]) == {tk} and abs(Wd["ledger"][tk]["pnl"] - (40 - 38.7 - 0.5 - 0.05)) < 1e-9,
           "ledger: pin market only (not the Coin Race row, not the KXWTI15M commodity row); a "
           "HEDGED market pays $40 though Kalshi's revenue field says 0 (P&L = payout - both sides - fee)")
        fmod = sys.modules.get(fake_mod)
        ck(Wd["hind_rows"] is not None and fmod is not None and fmod.SEEN.get("snap") == sett
           and Wd["hind_code"] == file_sha256(os.path.join(tmp, fake_mod + ".py"))
           and len(Wd["hind_code"] or "") == 64,
           "B1's scorer is imported from disk, handed the SAME ledger snapshot barcheck read, and "
           "its code hash is computed from its file by barcheck")
        x = eval_b1(bm["B1"], Wd)
        ck(x["status"] == "INVALID" and "not the registered one" in x["line"],
           "B1: that planted scorer is not the registered code -> INVALID (%s)" % x["line"][:80])
        runs = Wd["arms"].get("arm-pinx", {}).get("runs", [])
        ck(len(runs) == 1 and abs(runs[0]["pnl"][tk] - 0.55) < 1e-9 and runs[0]["code"] == "abc"
           and Wd["arms"]["arm-pinx"]["sig"] == ("pin=0.97",),
           "paper arm named from its .out file, its setting read as pin=0.97, its code read, an exact "
           "duplicate settled line counted once")
        rs = evaluate(bars, Wd)
        ck(len(brief(rs)) <= 8 and all(len(x) < 200 for x in brief(rs)),
           "--brief is <= 8 lines, each short enough for a phone")
        ck(status_md(rs, bars, Wd, tmp).count("## ") == 7, "status file has the freeze plus six bars")
        # the B5 baseline counts <=30 s buys OUTSIDE the 45 s leg, per watched close
        lp = [{"kind": "close_summary", "close": c1, "t": iso(c1 + 5)},
              {"kind": "order", "ticker": tk, "leg": "early", "filled": 50.0, "tau_at_send": 30,
               "t": iso(c1 - 30)},
              {"kind": "order", "ticker": tk, "leg": "full", "filled": 20.0, "tau_at_send": 10,
               "t": iso(c1 - 10)}]
        with open(os.path.join(tmp, "pinrun-live-Y.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in lp) + "\n")
        os.remove(os.path.join(tmp, "pinrun-live-X.jsonl"))
        pc_, na_ = late_per_close(tmp, c1 - 3600, c1 + 60)
        ck(na_ == 1 and abs(pc_ - 20.0) < 1e-9,
           "B5's own baseline: a 45 s-leg order sent at 30 s left is not a <=30 s buy (20 a close, "
           "not 70)")
        # missing files: no ledger, no logs, no arms -> zeros and waiting, never a crash
        for f in glob.glob(os.path.join(tmp, "*")):
            os.remove(f)
        Wm = load_world(bars, tmp, now=T0 + 86400)
        rm = evaluate(bars, Wm)
        ck(Wm["ledger"] == {} and not Wm["fills"] and all(x["n"] == 0 for x in rm)
           and all(x["status"] in ("COLLECTING", "PENDING", "REPORT") for x in rm),
           "missing files: an empty folder reads as 0 closes, every bar waiting (%s)"
           % ", ".join("%s %s" % (x["id"], x["status"]) for x in rm))
        Wn = load_world(bars, os.path.join(tmp, "does-not-exist"), now=T0 + 86400)
        ck(all(x["n"] == 0 for x in evaluate(bars, Wn)), "a folder that does not exist is also just empty")
    finally:
        sys.modules.pop("eh_fake_selftest_%d" % os.getpid(), None)
        if tmp in sys.path:
            sys.path.remove(tmp)
        for f in glob.glob(os.path.join(tmp, "*")):
            if os.path.isdir(f):
                import shutil
                shutil.rmtree(f, ignore_errors=True)
            else:
                os.remove(f)
        os.rmdir(tmp)
    print("barcheck self-test: %d checks passed" % n[0])
    return 0


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--brief", action="store_true", help="<= 8 plain lines")
    ap.add_argument("--data", default=DATA_DEFAULT,
                    help="where the live/paper logs, arm .out files and kalshi_ledger.json are "
                         "(default: the LIVE results folder, even from a worktree)")
    ap.add_argument("--bars", default=BARS_PATH)
    ap.add_argument("--status", default=STATUS_PATH, help="status file to write ('-' = none)")
    ap.add_argument("--hindsight-dir", default=None,
                    help="extra folder to import earlyhindsight.py from (default: next to this file)")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.bars)
    if os.environ.get("KALS_SELFTESTED") != "1":
        import contextlib
        import io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                selftest(a.bars)
        except SystemExit:
            print(buf.getvalue())
            print("barcheck: self-test FAILED -- no real data read")
            return 1
        if not a.brief:
            print(buf.getvalue().splitlines()[-1])
    bars = _bars_or_die(a.bars)
    W = load_world(bars, a.data, hindsight_dir=a.hindsight_dir)
    results = evaluate(bars, W)
    if a.status != "-":
        tmp = a.status + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(status_md(results, bars, W, a.data))
        os.replace(tmp, a.status)
    if a.brief:
        print("\n".join(brief(results)))
    else:
        print(status_md(results, bars, W, a.data))
        if a.status != "-":
            print("wrote %s" % a.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
