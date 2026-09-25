#!/usr/bin/env python3
"""crashidx.py -- after the model's belief in a side CRASHES from pin level to
under 0.40, how often does that side come back and win?  INDEX TAPE ONLY.

WHY. "Cash out and still hedge" (hedgeflip.py) is a bet that the move
continues. It makes money exactly when, at the alarm, the side we hold comes
back LESS often than the price of the other side implies. Our own record has
~10-15 alarms under 0.40 -- far too few to see a 10c edge. The settlement index
has every coin and every close, so it can measure the one thing the flip
depends on that is not a price: the real come-back rate after a crash, against
the model's own belief at the crash.

WHAT IT IS AND IS NOT. Source (1) in CLAUDE.md's order: the raw
cfbenchmarks_value tape, through pinrun's OWN fair() on a socket-less
IndexWS stub (the same stub results/MODEL_CALIBRATION_2026-09-25.md used, which
reproduced the live bot's logged fair on 747 of 874 fills). No order book, no
replay, no fills. **Nothing here is OUR loss rate** (rule 5): this population
is "every side that was at pin level", not "a side someone sold to us". It
says what the index did after a crash, not what we would have been filled at.

EVENT. For every coin index with a live market, every quarter-hour close with
all 60 settlement prints: for each side, `elig` = the first second in the
last 45 (tau 45..3) at which P(side) >= HI (0.995 = the live pin gate); the
event is the first LATER second (tau >= 1) at which P(side) < LO (0.40 = the
live hedge trigger). Outcome: did that side win anyway ("came back")?

    python crashidx.py --selftest
    python crashidx.py              # self-test, then the tape (~5-10 min)
    python crashidx.py --analyse    # tables from the saved rows only
"""
import calendar
import gzip
import collections
import glob
import json
import math
import os
import random
import re
import sys
import threading
import time
import zlib

sys.path.insert(0, r"C:\kals-repo\research")
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinrun                                            # noqa: E402
import gzsalvage                                         # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(OUT, "crashidx_rows.jsonl.gz")
TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
START = calendar.timegm((2026, 9, 1, 0, 0, 0))
HI, LO = 0.995, 0.40
EXTRA_LO = (0.60, 0.50, 0.30, 0.25, 0.20)     # first crossing of these too
SPAN = 700
DIGITS = {"BRTI": 2, "ETHUSD_RTI": 2, "BNBUSD_RTI": 2, "SOLUSD_RTI": 4,
          "XRPUSD_RTI": 4, "HYPEUSD_RTI": 4, "NEARUSD_RTI": 4,
          "ZECUSD_RTI": 4, "DOGEUSD_RTI": 7}
LINE_RE = re.compile(r'"index_id":"([A-Za-z0-9_]+)".*?\\"time\\":(\d+).*?'
                     r'\\"value\\":\\"([-0-9.eE]+)\\"')
SALVAGE = {}


class Stub(pinrun.IndexWS):
    """pinrun.IndexWS with no socket: only the dict its read methods use."""

    def __init__(self):                                 # noqa: D401
        self.ticks = {}
        self.lock = threading.RLock()
        self._cache = {}
        self._ver = collections.defaultdict(int)
        self.stats = collections.defaultdict(int)


STUB = Stub()


def settle_of(series, c):
    vals = []
    for s in range(c - 60, c):
        v = series.get(s)
        if v is None:
            return None
        vals.append(v)
    return sum(vals) / 60.0


def p_yes(iid, series, c, tau, strike, digits):
    """pinrun.fair at second c - tau, holding prints up to and including it."""
    now = c - tau
    d = {s: series[s] for s in range(now - SPAN, now + 1) if s in series}
    if len(d) < 30 or now not in d:
        return None, None
    STUB.ticks = {iid: d}
    sg = STUB.sigma(iid)
    if sg is None or sg <= 0:
        return None, None
    return pinrun.fair(STUB, iid, c, now, strike, sg, round_digits=digits), sg


def events_for_close(iid, series, c, strike, digits, hi=HI, lo=LO):
    """Crash events for one (index, close). Returns a list of dicts."""
    settle = settle_of(series, c)
    if settle is None:
        return []
    yes_won = (round(settle, digits) >= strike) if digits is not None else (settle >= strike)
    path = {}
    sig = {}
    for tau in range(45, 0, -1):
        f, sg = p_yes(iid, series, c, tau, strike, digits)
        if f is not None:
            path[tau] = f
            sig[tau] = sg
    out = []
    for side in ("yes", "no"):
        ps = {t: (f if side == "yes" else 1.0 - f) for t, f in path.items()}
        elig = next((t for t in range(45, 2, -1) if ps.get(t) is not None and ps[t] >= hi), None)
        if elig is None:
            continue
        won = yes_won if side == "yes" else (not yes_won)
        first = {}
        for thr in (lo,) + tuple(EXTRA_LO):
            first[thr] = next((t for t in range(elig - 1, 0, -1)
                               if ps.get(t) is not None and ps[t] < thr), None)
        t = first[lo]
        if t is None:
            out.append(dict(iid=iid, close=c, side=side, elig=elig, crash=None, won=int(won),
                            first={str(k): v for k, v in first.items()}))
            continue
        prev = next((ps[u] for u in range(t + 1, elig + 1) if ps.get(u) is not None), None)
        now = c - t
        mv = None
        if now in series and now - 1 in series and sig.get(t):
            mv = (series[now] - series[now - 1]) / sig[t]
            if side == "no":
                mv = -mv
        after = [round(ps[u], 5) if ps.get(u) is not None else None for u in range(t, 0, -1)]
        out.append(dict(iid=iid, close=c, side=side, elig=elig, crash=t, b=round(ps[t], 5),
                        prev=round(prev, 5) if prev is not None else None,
                        move_sd=round(mv, 3) if mv is not None else None,
                        after=after, won=int(won),
                        first={str(k): v for k, v in first.items()}))
    return out


def parse(line):
    m = LINE_RE.search(line)
    if m:
        return m.group(1), int(m.group(2)) // 1000, float(m.group(3))
    try:
        d = json.loads(line)
        if d.get("type") != "cfbenchmarks_value":
            return None
        mm = d.get("msg") or {}
        data = mm.get("data")
        data = json.loads(data) if isinstance(data, str) else (data or {})
        return mm.get("index_id"), int(data["time"]) // 1000, float(data["value"])
    except Exception:
        return None


def run():
    now_hour = time.strftime("%Y%m%dT%H", time.gmtime())
    files = sorted(f for f in glob.glob(os.path.join(TAPE, "*.jsonl.gz"))
                   if "20260901T00" <= os.path.basename(f)[:11] < now_hour)
    series = collections.defaultdict(dict)
    settles = {}
    done = set()
    stats = collections.Counter()
    t0 = time.time()
    with gzip.open(ROWS, "wt", encoding="utf-8") as out:
        for fi, path in enumerate(files):
            H = calendar.timegm(time.strptime(os.path.basename(path)[:11], "%Y%m%dT%H"))
            try:
                for line in gzsalvage.iter_lines(path, SALVAGE):
                    p = parse(line)
                    if p is None:
                        stats["unparsed"] += 1
                        continue
                    iid, sec, val = p
                    if iid in DIGITS:
                        series[iid][sec] = val
            except (EOFError, zlib.error, OSError):
                stats["torn_files"] += 1
            for iid in series:
                dd = series[iid]
                for s in [s for s in dd if s < H - 7400]:
                    del dd[s]
            for c in range(H - 3600, H + 1, 900):
                if c in done or c < START + 900:
                    continue
                done.add(c)
                for iid, ser in series.items():
                    st = settle_of(ser, c)
                    if st is None:
                        stats["no_settle"] += 1
                        continue
                    settles[(iid, c)] = st
                    prev = settles.get((iid, c - 900))
                    if prev is None:
                        stats["no_prev"] += 1
                        continue
                    dg = DIGITS[iid]
                    strike = round(prev, dg)
                    stats["closes"] += 1
                    for e in events_for_close(iid, ser, c, strike, dg):
                        stats["elig_sides"] += 1
                        if e.get("crash") is not None:
                            stats["crashes"] += 1
                        out.write(json.dumps(e) + "\n")
            if fi % 48 == 0:
                print("  %s closes=%d elig=%d crashes=%d %.0fs" % (
                    os.path.basename(path), stats["closes"], stats["elig_sides"],
                    stats["crashes"], time.time() - t0), flush=True)
    print("stats", dict(stats), "salvage", SALVAGE, "files", len(files),
          files[0][-20:], files[-1][-20:], flush=True)


# ---------------------------------------------------------------------------
def pb_le(ps, k):
    """P(sum Bernoulli(ps) <= k)."""
    dist = [1.0]
    for p in ps:
        nd = [0.0] * (len(dist) + 1)
        for i, v in enumerate(dist):
            nd[i] += v * (1 - p)
            nd[i + 1] += v * p
        dist = nd
    return sum(dist[:k + 1])


def cluster_ci(evs, B=4000, seed=1):
    """95% CI for came-back rate, resampling closes."""
    byc = collections.defaultdict(list)
    for e in evs:
        byc[e["close"]].append(e["won"])
    keys = list(byc)
    if not keys:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    rates = []
    for _ in range(B):
        w = n = 0
        for _k in range(len(keys)):
            v = byc[keys[rnd.randrange(len(keys))]]
            w += sum(v)
            n += len(v)
        rates.append(w / n if n else 0.0)
    rates.sort()
    return rates[int(0.025 * B)], rates[int(0.975 * B) - 1]


def table(evs, label):
    n = len(evs)
    if n == 0:
        print("  %-40s n=0" % label)
        return
    k = sum(e["won"] for e in evs)
    imp = sum(e["b"] for e in evs)
    lo, hi = cluster_ci(evs)
    closes = len({e["close"] for e in evs})
    p_low = pb_le([e["b"] for e in evs], k)
    p_high = 1.0 - pb_le([e["b"] for e in evs], k - 1) if k > 0 else 1.0
    print("  %-40s n=%4d closes=%4d | came back %3d = %5.1f%% [%4.1f, %4.1f] | model said %5.1f = %5.1f%% | "
          "ratio %.2f | P(this few)=%.3f P(this many)=%.3f" % (
              label, n, closes, k, 100.0 * k / n, 100 * lo, 100 * hi, imp, 100.0 * imp / n,
              k / imp if imp else float("nan"), p_low, p_high))


def analyse(rows=None):
    if rows is None:
        rows = [json.loads(l) for l in gzip.open(ROWS, "rt", encoding="utf-8")]
    elig = rows
    cr = [e for e in rows if e.get("crash") is not None]
    print("\nsides that reached P>=%.3f in the last 45 s: %d over %d closes; crashed under %.2f later: %d (%.2f%%)" % (
        HI, len(elig), len({e["close"] for e in elig}), LO, len(cr), 100.0 * len(cr) / max(1, len(elig))))
    print("\n=== did the side come back after the crash? (won = came back = a FALSE ALARM for a hedge) ===")
    table(cr, "all crashes under 0.40")
    for a, b in ((0.0, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 0.40)):
        table([e for e in cr if a <= e["b"] < b], "belief at crash %.2f-%.2f" % (a, b))
    for a, b in ((1, 10), (11, 20), (21, 30), (31, 44)):
        table([e for e in cr if a <= e["crash"] <= b], "seconds left %d-%d" % (a, b))
    table([e for e in cr if e.get("prev") is not None and e["prev"] >= 0.90], "one-print JUMP (prev >= 0.90)")
    table([e for e in cr if e.get("prev") is not None and e["prev"] < 0.90], "slide (prev < 0.90)")
    table([e for e in cr if e.get("move_sd") is not None and e["move_sd"] <= -4], "crash print moved >= 4 sd against")
    table([e for e in cr if e.get("move_sd") is not None and e["move_sd"] > -4], "crash print moved < 4 sd against")
    table([e for e in cr if e["b"] < 0.20 and e.get("prev") is not None and e["prev"] >= 0.90],
          "JUMP straight to under 0.20")
    # still under after d more printed seconds (the delay rule)
    for d in (1, 2, 3):
        sub = []
        for e in cr:
            a = [x for x in e["after"][1:d + 1]]
            if len(a) == d and all(x is not None and x < LO for x in a):
                sub.append(dict(e, b=e["after"][d]))
        table(sub, "still under 0.40 %d s later (belief then)" % d)
    per_coin = collections.defaultdict(list)
    for e in cr:
        per_coin[e["iid"]].append(e)
    print("\n  by coin:")
    for iid in sorted(per_coin):
        table(per_coin[iid], iid)
    # other thresholds: false-alarm rate of a trigger at X
    print("\n=== a trigger at X: how often the side it fired on came back ===")
    for thr in ("0.6", "0.5", "0.4", "0.3", "0.25", "0.2"):
        fired = [e for e in elig if e["first"].get(thr) is not None]
        k = sum(e["won"] for e in fired)
        closes = len({e["close"] for e in fired})
        lo, hi = cluster_ci(fired) if fired else (float("nan"), float("nan"))
        print("  trigger %-5s fired on %4d sides (%4d closes), came back %3d = %5.1f%% [%4.1f, %4.1f]" % (
            thr, len(fired), closes, k, 100.0 * k / max(1, len(fired)), 100 * lo, 100 * hi))
    # breakeven: what the other side must cost for a flip to pay
    if cr:
        k = sum(e["won"] for e in cr)
        rate = k / len(cr)
        print("\n  flip break-even: the other side pays if it costs less than %.3f (1 - came-back rate) minus the fee" % (1 - rate))


# ---------------------------------------------------------------------------
def selftest():
    ok = True
    rnd = random.Random(17)

    def world(momentum, n_closes, hi):
        """Random-walk index; momentum>0 plants CONTINUATION after a big move."""
        rows = []
        for k in range(n_closes):
            c = 900 * (k + 20)
            sg = 1.0
            v = 1000.0
            ser = {}
            carry = 0.0
            for s in range(c - 800, c):
                step = rnd.gauss(0, sg) + carry
                if momentum and abs(step) > 2.5 * sg:
                    carry = math.copysign(momentum * sg, step)
                else:
                    carry *= 0.9
                v += step
                ser[s] = v
            K = round(ser[c - 46] + rnd.gauss(0, 3.0), 2)
            rows.extend(events_for_close("X", ser, c, K, 2, hi=hi, lo=LO))
        return [e for e in rows if e.get("crash") is not None]

    cr = world(0.0, 1500, 0.90)
    k = sum(e["won"] for e in cr)
    imp = sum(e["b"] for e in cr)
    print("  gaussian world: %d crashes, came back %d, model said %.1f (ratio %.2f)" % (
        len(cr), k, imp, k / imp if imp else float("nan")))
    if not (len(cr) >= 40 and 0.6 < k / imp < 1.6):
        print("  FAIL: a calibrated world must read calibrated")
        ok = False
    cm = world(3.0, 1500, 0.90)
    k2 = sum(e["won"] for e in cm)
    imp2 = sum(e["b"] for e in cm)
    print("  momentum world: %d crashes, came back %d, model said %.1f (ratio %.2f)" % (
        len(cm), k2, imp2, k2 / imp2 if imp2 else float("nan")))
    if not (len(cm) >= 40 and k2 / imp2 < 0.6):
        print("  FAIL: planted continuation not detected")
        ok = False
    # outcome/side bookkeeping on a hand world: YES pinned, then crashes, settles NO
    c = 900 * 50
    ser = {s: 1000.0 + 0.01 * ((s * 7919) % 13 - 6) for s in range(c - 800, c - 30)}
    for s in range(c - 30, c):
        ser[s] = 980.0 + 0.01 * ((s * 7919) % 13 - 6)
    ev = events_for_close("X", ser, c, 995.0, 2)
    y = [e for e in ev if e["side"] == "yes"]
    if not (y and y[0]["crash"] is not None and y[0]["won"] == 0 and 28 <= y[0]["crash"] <= 31):
        print("  FAIL: hand world", y[:1])
        ok = False
    if abs(pb_le([0.5, 0.5], 0) - 0.25) > 1e-12 or abs(pb_le([0.2, 0.5, 0.9], 3) - 1.0) > 1e-12:
        print("  FAIL: poisson-binomial")
        ok = False
    ln = ('{"type":"cfbenchmarks_value","msg":{"index_id":"BRTI","data":"{\\"type\\":'
          '\\"value\\",\\"time\\":1788220800000,\\"id\\":\\"BRTI\\",\\"value\\":'
          '\\"691.360\\"}"}}')
    if parse(ln) != ("BRTI", 1788220800, 691.36):
        print("  FAIL parser", parse(ln))
        ok = False
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    if "--analyse" in sys.argv:
        analyse()
        sys.exit(0)
    if not selftest():
        sys.exit(1)
    if "--selftest" in sys.argv:
        sys.exit(0)
    run()
    analyse()
