"""Price candidate rules on the record, market by market, against Kalshi's real
result. ANALYSIS, NOT THE CERTIFIED BACKTEST: the decision is re-implemented
here from the per-second belief (index tape, pinrun's maths) and the ticker
tape's best ask. Loss rates come only from markets WE held; a top-up leg in a
market we held is priced at the tape's ask and paid by Kalshi's real result,
with the caveat that live fills at the ask succeed ~70% of the time, so top-up
gains are an upper bound (a 70% haircut is printed beside them).

Rules:
  entry ladders  cumulative size cap by seconds-left, top-up to the cap while
                 the entry gates still pass (conf >= PIN, ask <= ceiling,
                 edge >= floor, spike gate, edge cap on the early window)
  hedge triggers belief threshold / drop, proportional vs full, priced at the
                 other side's ask at that second, retried up to 30 s
"""
import json, os, sys, math, collections, time
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun

SP = r"C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad"
D = [json.loads(l) for l in open(os.path.join(SP, "cf_dataset.jsonl"), encoding="utf-8")]
PIN = 0.995; CEIL = 0.98; EDGE_FLOOR = 0.003; TAU_MIN = 3
SPIKE_MIN = 0.90; CAP_C = 10.0

def fee(p, n):
    return pinrun.billed_fee(p, n) if n > 0 else 0.0

def etday(cs):
    return time.strftime("%m-%d", time.gmtime(cs - 4 * 3600))

def band(t):
    t = t if t is not None else 99
    return "<=10" if t <= 10 else ("11-20" if t <= 20 else ("21-30" if t <= 30 else "31-45"))

def cur_frac(tau):
    """What the live bot allows today, cumulative: 1/3 at 31-45 s, full at <=30."""
    return 1.0 / 3.0 if tau > 30 else 1.0

def entry_ok(m, tau, early_cap_only_above=20):
    """Would the entry gates pass at second `tau`? (belief, ask, edge, spike, cap)"""
    c = m["conf"][tau]; a = m["ask"][tau]; sz = m["asz"][tau]
    if c is None or a is None or not sz or sz < 1:
        return None
    if c < PIN or a > CEIL:
        return None
    edge = c - a - fee(a, 1)
    if edge < EDGE_FLOOR:
        return None
    prev = m["conf"][tau + 1] if tau + 1 <= 45 else None
    if tau > 5 and prev is not None and prev < SPIKE_MIN:
        return None
    if tau > early_cap_only_above and 100.0 * (c - a) > CAP_C:
        return None
    return a, sz

def ladder_pnl(m, caps, haircut=1.0, topup=True):
    """caps: list of (tau_ceiling, cumulative fraction of full size), e.g.
    [(45, 1/3), (30, 0.5), (20, 1.0)] means <=45 s: 1/3, <=30 s: 1/2, <=20 s: full.
    Returns (pnl, n_first, n_topup) with the hedge scaled to the new size."""
    n_full = m["our_n"]
    if not n_full or m["result"] not in ("yes", "no") or m["tau_entry"] is None:
        return m["pnl"], m["our_n"], 0.0
    te = int(m["tau_entry"]); pe = float(m["price_entry"] or (m["our_cost"] / n_full))
    def cap_at(t):
        f = 0.0
        for tc, fr in caps:
            if t <= tc:
                f = max(f, fr)
        return f
    # the leg we actually took, rescaled to the new cap at that second
    f_new = cap_at(te); f_cur = cur_frac(te)
    n1 = n_full * (f_new / f_cur) if f_cur > 0 else 0.0
    n1 = min(n1, n_full * f_new)
    legs = [(n1, pe)] if n1 > 0 else []
    held = n1
    # top-ups at later seconds while unfinished and the gates pass
    if topup:
        for tau in range(min(te - 1, 45), TAU_MIN - 1, -1):
            want_n = n_full * cap_at(tau)
            if held >= want_n - 1e-9:
                continue
            ok = entry_ok(m, tau)
            if not ok:
                continue
            a, sz = ok
            take = min(want_n - held, sz) * haircut
            if take <= 0:
                continue
            legs.append((take, a)); held += take
    win = 1.0 if m["result"] == m["want"] else 0.0
    pnl = 0.0
    for n, p in legs:
        pnl += n * (win - p) - fee(p, n)
    # the hedge we actually bought, scaled to the new position
    if m["opp_n"] and n_full:
        h = held / n_full
        q = m["opp_cost"] / m["opp_n"]
        hn = m["opp_n"] * h
        pnl += hn * ((1.0 - win) - q) - fee(q, hn)
    return pnl, n1, held - n1

def unhedged_pnl(m):
    win = 1.0 if m["result"] == m["want"] else 0.0
    n = m["our_n"]; p = m["our_cost"] / n if n else 0.0
    return n * (win - p) - fee(p, n) if n else 0.0

def hedge_pnl(m, trigger, prop=True, drop=None, retry_s=30, min_belief_change=None):
    """Simulated hedge on the ACTUAL position: fire at the first second after
    entry where belief < trigger (or has dropped by `drop` from its running
    max); buy the other side at opp[tau] (retrying while it is None/>=0.99);
    size half at belief <= 0.40 / all at <= 0.20 when prop, else all."""
    n = m["our_n"]
    if not n or m["result"] not in ("yes", "no") or m["tau_entry"] is None:
        return unhedged_pnl(m), False
    te = int(m["tau_entry"]); win = 1.0 if m["result"] == m["want"] else 0.0
    base = unhedged_pnl(m)
    peak = m["conf"][te] if m["conf"][te] is not None else 1.0
    fired_at = None
    for tau in range(min(te - 1, 45), -1, -1):
        c = m["conf"][tau]
        if c is None:
            continue
        peak = max(peak, c)
        if c < trigger or (drop is not None and peak - c >= drop):
            fired_at = tau; break
    if fired_at is None:
        return base, False
    bought = 0.0; hp = 0.0
    for tau in range(fired_at, max(-1, fired_at - retry_s), -1):
        c = m["conf"][tau]; q = m["opp"][tau]; qs = m["osz"][tau] or 0.0
        if c is None or q is None or q >= 0.99 or qs < 1:
            continue
        if prop:
            target = n if c <= 0.20 else (0.5 * n if c <= 0.40 else 0.0)
        else:
            target = n
        take = min(max(0.0, target - bought), qs)
        if take <= 0:
            continue
        hp += take * ((1.0 - win) - q) - fee(q, take); bought += take
        if bought >= n - 1e-9:
            break
    return base + hp, bought > 0

def summ(label, vals, mk=None):
    n = len(vals); l = [v for v in vals if v < 0]; w = [v for v in vals if v >= 0]
    print("  %-46s %4d mkts | losers %2d %+9.2f | winners %+9.2f | NET %+9.2f | worst %+8.2f" % (
        label, n, len(l), sum(l), sum(w), sum(vals), min(vals) if vals else 0))

good = [m for m in D if m["conf_src"] and m["result"] in ("yes", "no") and m["our_n"]]
print("markets with a per-second picture:", len(good), "of", len(D),
      " (belief from index: %d, from the bot's log: %d)" % (sum(1 for m in good if m["conf_src"] == "index"), sum(1 for m in good if m["conf_src"] == "traj")))
print("  ask coverage: markets with an ask at 20 s: %d, at 10 s: %d" % (sum(1 for m in good if m["ask"][20] is not None), sum(1 for m in good if m["ask"][10] is not None)))
# sanity: rebuilt unhedged + actual hedge vs Kalshi's pnl
diffs = []
for m in good:
    win = 1.0 if m["result"] == m["want"] else 0.0
    q = (m["opp_cost"] / m["opp_n"]) if m["opp_n"] else 0.0
    rebuilt = unhedged_pnl(m) + (m["opp_n"] * ((1.0 - win) - q) - fee(q, m["opp_n"]) if m["opp_n"] else 0.0)
    diffs.append(abs(rebuilt - m["pnl"]))
print("  rebuilt pnl matches Kalshi's within 5c on %d of %d (max gap %.2f)" % (sum(1 for d in diffs if d < 0.05), len(diffs), max(diffs)))

print("\n=== ENTRY LADDERS (size cap by seconds-left; top-up to the cap at later seconds while the gates pass) ===")
LADDERS = [
    ("AS IS  (1/3 at 31-45 s, full at <=30 s), no sim", None),
    ("current caps, re-simulated (should ~match)", [(45, 1 / 3), (30, 1.0)]),
    ("A: 1/3 at 31-45, 1/2 at 21-30, full <=20", [(45, 1 / 3), (30, 0.5), (20, 1.0)]),
    ("B: none at 31-45, 1/2 at 21-30, full <=20", [(30, 0.5), (20, 1.0)]),
    ("C: no entries before 20 s", [(20, 1.0)]),
    ("D: 1/3 at 31-45, 1/3 at 21-30, full <=20", [(45, 1 / 3), (30, 1 / 3), (20, 1.0)]),
    ("E: 1/3 at 31-45, 1/2 at 21-30, full <=15", [(45, 1 / 3), (30, 0.5), (15, 1.0)]),
    ("F: 1/2 at 21-45, full <=20", [(45, 0.5), (20, 1.0)]),
]
for label, caps in LADDERS:
    if caps is None:
        summ(label, [m["pnl"] for m in good]); continue
    full = [ladder_pnl(m, caps)[0] for m in good]
    hair = [ladder_pnl(m, caps, haircut=0.7)[0] for m in good]
    notop = [ladder_pnl(m, caps, topup=False)[0] for m in good]
    summ(label, full)
    summ("     ...top-ups filled 70% of the time", hair)
    summ("     ...no top-ups at all", notop)

print("\n=== LADDER A BY WEEK ===")
capsA = [(45, 1 / 3), (30, 0.5), (20, 1.0)]
for lo, hi in (("09-08", "09-15"), ("09-16", "09-23")):
    g = [m for m in good if lo <= etday(m["close_s"]) <= hi]
    summ("%s..%s as is" % (lo, hi), [m["pnl"] for m in g])
    summ("%s..%s ladder A" % (lo, hi), [ladder_pnl(m, capsA)[0] for m in g])
    summ("%s..%s ladder C (>=20 s only)" % (lo, hi), [ladder_pnl(m, [(20, 1.0)])[0] for m in g])

print("\n=== WHERE THE LADDER-A DOLLARS COME FROM (markets first entered at 21-45 s) ===")
early = [m for m in good if m["tau_entry"] is not None and m["tau_entry"] > 20]
tu = [ladder_pnl(m, capsA) for m in early]
print("  early-entered markets: %d; got a top-up at <=20 s: %d; top-up contracts total %.0f" % (
    len(early), sum(1 for t in tu if t[2] > 0), sum(t[2] for t in tu)))
los = [m for m in early if m["pnl"] < 0]
print("  the %d early-entered LOSERS under ladder A:" % len(los))
for m in sorted(los, key=lambda m: m["pnl"]):
    p, n1, n2 = ladder_pnl(m, capsA)
    print("    %s ET %-5s %-3s %2ss  actual %+8.2f -> %+8.2f  (first leg %.0f, top-up %.0f contracts; belief at 20 s %s)" % (
        time.strftime("%m-%d %I:%M%p", time.gmtime(m["close_s"] - 4 * 3600)), m["tk"].split("-")[0][2:-3], m["want"], m["tau_entry"], m["pnl"], p, n1, n2, m["conf"][20]))

print("\n=== HEDGE TRIGGERS on the actual positions (replacing the hedges we actually bought) ===")
summ("no hedge at all", [unhedged_pnl(m) for m in good])
summ("as is (Kalshi's number, actual hedges)", [m["pnl"] for m in good])
for trig in (0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
    for prop in (True, False):
        r = [hedge_pnl(m, trig, prop=prop) for m in good]
        summ("belief < %.2f, %s  (fired %d)" % (trig, "half@.40/all@.20" if prop else "all at once", sum(1 for x in r if x[1])), [x[0] for x in r])
for drop in (0.10, 0.20, 0.30, 0.50):
    r = [hedge_pnl(m, 0.40, prop=False, drop=drop) for m in good]
    summ("belief fell %.2f from its peak OR < 0.40, all  (fired %d)" % (drop, sum(1 for x in r if x[1])), [x[0] for x in r])
