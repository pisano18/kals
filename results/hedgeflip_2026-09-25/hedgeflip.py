#!/usr/bin/env python3
"""hedgeflip.py -- "cash out AND still hedge": would it have made money?

THE OPERATOR, 2026-09-25: "What about when hedging -- if we're certain it's
going down we cash out where it's at and still hedge to save a little more?"

WHAT THAT TRADE IS. On Kalshi, selling our YES at the bid and buying NO at the
ask are the same trade (YES bid = 1 - NO ask, one book, one fee formula). The
live hedge already buys the other side for the whole position, which leaves a
locked $1 a pair. "Cash out AND hedge" therefore buys the other side TWICE: the
result is a full position on the OTHER side -- a bet that the move continues.
So every variant here is one number k = contracts of the other side bought at
the alarm, as a multiple of the position:

    k = 0      no hedge
    k = 0.5    half hedge
    k = 1      the live hedge (locks the pair)
    k = 1 + x  hedge plus an extra opposite leg of x times the position (the
               flip; x = 1 is "cash out and hedge")

The money of the extra leg is simply (other side won ? 1 : 0) - price - fee,
per contract. It pays exactly when buying the other side at the alarm is
cheaper than its real chance of winning. That is the whole question.

SOURCES, in the order CLAUDE.md ranks them. Money: Kalshi's ledger
(results/kalshi_ledger.json, pinledger.pnl). Prices at the alarm: OUR OWN
hedge fills and the book our bot logged (hedge / hedge_quote records). The
model's belief at the alarm: the bot's own logged `belief`. For the
per-second rule sweep (population B), the per-second picture from
results/cf_2026-09-24/cf_dataset.jsonl.gz (belief rebuilt from the index with
pinrun's maths; the other side's ask from the ticker tape) is used ONLY where
the bot logged nothing for that second -- and the tape is known to be stale at
crash seconds (see the price-source check this script prints).

Nothing here is replayed through pinsim and no loss rate is quoted from the
tape. Every dollar figure below is a HYPOTHESIS about what a different rule
would have made on the markets we actually held.

    python hedgeflip.py --selftest
    python hedgeflip.py            # self-test first, then the real record
"""
import calendar
import collections
import glob
import gzip
import json
import math
import os
import random
import sys
import time

REPO = r"C:\kals-repo"
RES = os.path.join(REPO, "results")
sys.path.insert(0, os.path.join(REPO, "research"))

LEDGER = os.path.join(RES, "kalshi_ledger.json")
XFERS = os.path.join(RES, "kalshi_transfers.json")
CF = os.path.join(RES, "cf_2026-09-24", "cf_dataset.jsonl.gz")
LOG_GLOB = os.path.join(RES, "pinrun-live-*.jsonl")
SINCE_ET = "2026-09-13"
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
     "NOV", "DEC"])}
XS = (0.25, 0.5, 1.0)
SLIPS = (0.0, 0.05)
FULL_COVER = 0.95        # an extra leg is only priced where the hedge itself filled


def fee(p, n):
    """Kalshi taker fee, the formula (Kalshi bills it to $0.0001)."""
    if n <= 0 or p is None:
        return 0.0
    return 0.07 * float(p) * (1.0 - float(p)) * float(n)


def fnum(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def close_of_ticker(tk):
    """UTC epoch of the close encoded (in ET) in a 15-minute ticker."""
    stamp = tk.split("-")[1]
    yy, mon, dd = int(stamp[0:2]), MONTHS[stamp[2:5]], int(stamp[5:7])
    hh = int(stamp[7:9])
    mm = int(stamp[9:11]) if len(stamp) >= 11 and stamp[9:11].isdigit() else 0
    et = calendar.timegm((2000 + yy, mon, dd, hh, mm, 0))
    off = 4 * 3600 if 3 <= mon <= 10 else 5 * 3600   # EDT through Oct (close enough here)
    return et + off


def et_day(tk):
    stamp = tk.split("-")[1]
    return "%04d-%02d-%02d" % (2000 + int(stamp[0:2]), MONTHS[stamp[2:5]], int(stamp[5:7]))


def et_label(tk):
    stamp = tk.split("-")[1]
    h, m = int(stamp[7:9]), (stamp[9:11] if len(stamp) >= 11 else "00")
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return "%s/%s %d:%s %s" % (MONTHS[stamp[2:5]], stamp[5:7], h12, m, ap)


def coin(tk):
    return tk.split("-")[0][2:].replace("15M", "")


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
KEEP = ("hedge_alarm", "hedge", "hedge_quote", "hedge_panic", "hedge_prop",
        "hedge_wait_price", "hedge_gave_up", "hedge_no_ask")


def parse_lines(lines, logs=None):
    """{ticker: {'alarms':[], 'hedges':[], 'quotes':{tau: rec}, 'other':[]}}"""
    logs = logs if logs is not None else {}
    for line in lines:
        if '"kind": "hedge' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        k = r.get("kind")
        if k not in KEEP:
            continue
        tk = r.get("ticker")
        if not tk:
            continue
        d = logs.setdefault(tk, {"alarms": [], "hedges": [], "quotes": {}, "other": []})
        if k == "hedge_alarm":
            d["alarms"].append(r)
        elif k == "hedge":
            oid = r.get("order_id")
            if oid and any(h.get("order_id") == oid for h in d["hedges"]):
                continue
            d["hedges"].append(r)
        elif k == "hedge_quote":
            tau = r.get("tau")
            if tau is not None and int(tau) not in d["quotes"]:
                d["quotes"][int(tau)] = r
        else:
            d["other"].append(r)
    return logs


def load_logs():
    logs = {}
    for p in sorted(glob.glob(LOG_GLOB)):
        with open(p, encoding="utf-8", errors="replace") as fh:
            parse_lines(fh, logs)
    return logs


def load_ledger():
    import pinledger as L
    rows = L.load_cache(L.LEDGER)
    by = {}
    for s in rows.values():
        tk = s.get("ticker")
        if tk:
            by.setdefault(tk, []).append(s)
    return rows, by, L


# ---------------------------------------------------------------------------
# population A -- the markets we actually hedged
# ---------------------------------------------------------------------------
def market_row(tk, lg, led_rows, pnl_fn):
    """One hedged market, money from the ledger, prices from our fills."""
    if not lg["alarms"] and not lg["hedges"]:
        return None
    fills = [h for h in lg["hedges"] if fnum(h.get("n")) > 0]
    if not fills:
        return None
    want = (lg["alarms"][0].get("want") if lg["alarms"] else None)
    if want is None:
        want = "yes" if fills[0].get("side") == "no" else "no"
    other = "no" if want == "yes" else "yes"
    s = led_rows[0] if led_rows else None
    if s is None:
        return None
    if len(led_rows) > 1:
        # one settlement per market for 15-minute series; merge if not
        pass
    yc, nc = fnum(s.get("yes_count_fp")), fnum(s.get("no_count_fp"))
    yd, nd = fnum(s.get("yes_total_cost_dollars")), fnum(s.get("no_total_cost_dollars"))
    res = str(s.get("market_result") or "").lower()
    n_our, c_our = (yc, yd) if want == "yes" else (nc, nd)
    n_h, c_h = (nc, nd) if want == "yes" else (yc, yd)
    fills.sort(key=lambda h: (h.get("t", ""), -int(h.get("tau") or 0)))
    fl = [(int(h.get("tau") or 0), fnum(h.get("n")), fnum(h.get("price")),
           h.get("ask"), h.get("ask_size"), h.get("t")) for h in fills]
    log_n = sum(f[1] for f in fl)
    reconciled = abs(log_n - n_h) <= 0.5
    if not reconciled and n_h > 0:
        # the ledger is the authority: one synthetic fill at the ledger's average
        fl = [(fl[0][0], n_h, c_h / n_h, fl[0][3], fl[0][4], fl[0][5])]
    fee_h = sum(fee(f[2], f[1]) for f in fl)
    fee_all = fnum(s.get("fee_cost"))
    fee_our = fee_all - fee_h
    o_our = 1.0 if res == want else 0.0
    o_oth = 1.0 if res == other else 0.0
    actual = pnl_fn(s)
    nohedge = n_our * o_our - c_our - fee_our
    hedge_leg = n_h * o_oth - c_h - fee_h
    al = lg["alarms"][0] if lg["alarms"] else None
    act = fills[0]
    first_try = sorted(lg["hedges"], key=lambda h: h.get("t", ""))[0]
    return dict(
        tk=tk, close_s=close_of_ticker(tk), day=et_day(tk), want=want, other=other,
        result=res, o_oth=o_oth, n_our=n_our, c_our=c_our, n_h=n_h, c_h=c_h,
        fee_h=fee_h, fee_our=fee_our, actual=actual, nohedge=nohedge,
        hedge_leg=hedge_leg, fills=fl, reconciled=reconciled, log_n=log_n,
        cov=(n_h / n_our) if n_our else 0.0,
        alarm_tau=int(al["tau"]) if al else None,
        alarm_b=fnum(al.get("belief")) if al else None,
        alarm_thr=al.get("threshold") if al else None,
        try_tau=int(first_try.get("tau") or 0), try_ask=first_try.get("ask"),
        try_b=fnum(first_try.get("belief")),
        act_tau=int(act.get("tau") or 0), act_b=fnum(act.get("belief")),
        q_first=fl[0][2], q_worst=max(f[2] for f in fl),
        q_avg=(c_h / n_h) if n_h else None,
        settled_time=s.get("settled_time"))


def variant(m, k, slip=0.0):
    """Dollars on the market if we had held k x position of the other side.

    The first contracts come from our real hedge fills in time order; any
    beyond what the hedge bought are priced at the WORST price the hedge paid
    plus `slip` -- and only where the hedge itself covered the position (a
    hedge that could not fill is evidence there was no book for more).
    Returns (dollars, extra_contracts_priced, extra_refused)."""
    target = k * m["n_our"]
    got = 0.0
    leg = 0.0
    for tau, n, p, _a, _s, _t in m["fills"]:
        if got >= target - 1e-9:
            break
        take = min(n, target - got)
        leg += take * m["o_oth"] - take * p - fee(p, take)
        got += take
    extra = max(0.0, target - got)
    refused = 0.0
    if extra > 1e-9:
        if m["cov"] >= FULL_COVER:
            p = min(0.99, m["q_worst"] + slip)
            leg += extra * m["o_oth"] - extra * p - fee(p, extra)
        else:
            refused = extra
            extra = 0.0
    return m["nohedge"] + leg, extra, refused


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def poisson_binomial_ge(ps, k):
    """P(sum of independent Bernoulli(ps) >= k), exact."""
    dist = [1.0]
    for p in ps:
        nd = [0.0] * (len(dist) + 1)
        for i, v in enumerate(dist):
            nd[i] += v * (1 - p)
            nd[i + 1] += v * p
        dist = nd
    return sum(dist[k:]) if k < len(dist) else 0.0


def boot_ci(by_close, B=20000, seed=11):
    """95% CI of the SUM over closes, resampling closes."""
    vals = list(by_close.values())
    if not vals:
        return (0.0, 0.0)
    rnd = random.Random(seed)
    n = len(vals)
    sums = sorted(sum(vals[rnd.randrange(n)] for _ in range(n)) for _ in range(B))
    return sums[int(0.025 * B)], sums[int(0.975 * B) - 1]


def mde_dollars(ns, qs):
    """Smallest true edge (dollars, whole sample) a two-sided 5% test finds
    80% of the time, if the other side's price were exactly fair:
    2.8 x sd of the extra leg's money under that null."""
    var = sum((n ** 2) * q * (1 - q) for n, q in zip(ns, qs))
    return 2.8 * math.sqrt(var)


def mde_cents(ns, qs):
    tot = sum(ns)
    if tot <= 0:
        return float("nan")
    return 100.0 * mde_dollars(ns, qs) / tot


# ---------------------------------------------------------------------------
# population B -- every held position whose belief crossed a trigger
# ---------------------------------------------------------------------------
def build_popb(logs, led_by, cf_rows, since_et=SINCE_ET):
    """Per-second picture for every position we held since `since_et`.

    belief: the bot's own hedge_quote belief where logged, else the index
            rebuild (cf_dataset conf).
    price:  the bot's own hedge_quote ask, else our hedge record's ask at that
            second, else the ticker tape (cf_dataset opp). The source of the
            price at the fire second is kept so the report can say it."""
    out = []
    seen = set()
    for m in cf_rows:
        tk = m["tk"]
        if et_day(tk) < since_et or m.get("result") not in ("yes", "no"):
            continue
        if not m.get("our_n") or m.get("tau_entry") is None:
            continue
        seen.add(tk)
        conf = list(m["conf"])
        csrc = ["idx" if c is not None else None for c in conf]
        opp = list(m["opp"])
        osz = list(m["osz"])
        psrc = ["tape" if q is not None else None for q in opp]
        out.append(dict(tk=tk, close_s=m["close_s"], want=m["want"],
                        result=m["result"], te=int(m["tau_entry"]),
                        n=m["our_n"], cost=m["our_cost"], conf=conf, csrc=csrc,
                        opp=opp, osz=osz, psrc=psrc))
    # markets after the tape rebuild ends: the bot's own per-second log only
    for tk, lg in logs.items():
        if tk in seen or not lg["quotes"] or et_day(tk) < since_et:
            continue
        rows = led_by.get(tk)
        if not rows:
            continue
        s = rows[0]
        res = str(s.get("market_result") or "").lower()
        if res not in ("yes", "no"):
            continue
        q0 = next(iter(lg["quotes"].values()))
        want = "yes" if q0.get("side") == "no" else "no"
        n = fnum(s.get("yes_count_fp") if want == "yes" else s.get("no_count_fp"))
        cost = fnum(s.get("yes_total_cost_dollars") if want == "yes" else s.get("no_total_cost_dollars"))
        if n <= 0:
            continue
        conf = [None] * 46
        csrc = [None] * 46
        opp = [None] * 46
        osz = [None] * 46
        psrc = [None] * 46
        te = max(lg["quotes"]) + 1
        out.append(dict(tk=tk, close_s=close_of_ticker(tk), want=want, result=res,
                        te=min(te, 45), n=n, cost=cost, conf=conf, csrc=csrc,
                        opp=opp, osz=osz, psrc=psrc))
    # overlay the bot's own numbers
    for m in out:
        lg = logs.get(m["tk"])
        if not lg:
            continue
        for tau, q in lg["quotes"].items():
            if 0 <= tau <= 45:
                if q.get("belief") is not None:
                    m["conf"][tau] = float(q["belief"])
                    m["csrc"][tau] = "bot"
                if q.get("ask") is not None and 0 < float(q["ask"]) < 1:
                    m["opp"][tau] = float(q["ask"])
                    m["osz"][tau] = fnum(q.get("size"))
                    m["psrc"][tau] = "bot"
        for h in sorted(lg["hedges"], key=lambda h: h.get("t", "")):
            tau = int(h.get("tau") or -1)
            if 0 <= tau <= 45 and h.get("ask") is not None and m["psrc"][tau] != "bot":
                m["opp"][tau] = float(h["ask"])
                m["osz"][tau] = fnum(h.get("ask_size"))
                m["psrc"][tau] = "bot"
            if 0 <= tau <= 45 and h.get("belief") is not None and m["csrc"][tau] != "bot":
                m["conf"][tau] = float(h["belief"])
                m["csrc"][tau] = "bot"
        for a in lg["alarms"]:
            tau = int(a.get("tau") or -1)
            if 0 <= tau <= 45 and a.get("belief") is not None and m["csrc"][tau] != "bot":
                m["conf"][tau] = float(a["belief"])
                m["csrc"][tau] = "bot"
    return out


def unhedged(m):
    win = 1.0 if m["result"] == m["want"] else 0.0
    n = m["n"]
    p = m["cost"] / n if n else 0.0
    return n * (win - p) - fee(p, n)


def fire_tau(m, trig, delay=0):
    """First held second the belief is under `trig` for delay+1 printed seconds."""
    run = 0
    for tau in range(min(m["te"] - 1, 45), -1, -1):
        c = m["conf"][tau]
        if c is None:
            continue
        if c < trig:
            run += 1
            if run > delay:
                return tau
        else:
            run = 0
    return None


def sim_leg(m, tau0, k, retry_s=30):
    """Buy k x position of the other side from second tau0 on, at the logged
    price, up to the size offered each second. Returns (dollars, bought, src)."""
    target = k * m["n"]
    win_oth = 1.0 if m["result"] != m["want"] else 0.0
    bought = 0.0
    leg = 0.0
    src = None
    for tau in range(tau0, max(-1, tau0 - retry_s), -1):
        q = m["opp"][tau]
        qs = m["osz"][tau] or 0.0
        if q is None or q >= 0.99 or qs < 1:
            continue
        take = min(max(0.0, target - bought), qs)
        if take <= 0:
            break
        if src is None:
            src = m["psrc"][tau]
        leg += take * (win_oth - q) - fee(q, take)
        bought += take
        if bought >= target - 1e-9:
            break
    return leg, bought, src


def rule_money(m, trig, k, delay=0):
    base = unhedged(m)
    t = fire_tau(m, trig, delay)
    if t is None:
        return base, None, 0.0, None
    leg, bought, src = sim_leg(m, t, k)
    return base + leg, t, bought, src


# ---------------------------------------------------------------------------
# bank curve, loss cap
# ---------------------------------------------------------------------------
def bank_curve(led_rows, pnl_fn, deltas, xfers):
    """Max drawdown ($, %) from the running high since SINCE_ET, with per-
    market deltas added at their settlement time."""
    ev = []
    for s in led_rows.values():
        t = s.get("settled_time") or ""
        try:
            ts = calendar.timegm(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue
        ev.append((ts, "pnl", pnl_fn(s) + deltas.get(s.get("ticker"), 0.0)))
    for d in xfers.get("deposits", []):
        if d.get("status") == "applied":
            ev.append((int(d["finalized_ts"]), "dep",
                       (d["amount_cents"] - d.get("fee_cents", 0)) / 100.0))
    for w in xfers.get("withdrawals", []):
        ev.append((int(w.get("finalized_ts") or w.get("created_ts")), "dep",
                   -w["amount_cents"] / 100.0))
    ev.sort()
    t0 = calendar.timegm((2026, 9, 13, 4, 0, 0))
    pnl = 0.0
    dep = 0.0
    hwm = None
    worst_d = 0.0
    worst_p = 0.0
    when = None
    # Drawdown is measured on TRADING money only (a deposit is not a recovery
    # and must not hide or create a drawdown); the % is against the bank at the
    # running high (deposits so far + the trading high).
    for ts, kind, v in ev:
        if kind == "dep":
            dep += v
        else:
            pnl += v
        if ts < t0:
            continue
        hwm = pnl if hwm is None else max(hwm, pnl)
        dd = hwm - pnl
        bank_hi = dep + hwm
        if dd > worst_d:
            worst_d = dd
            when = ts
        if bank_hi > 0 and dd / bank_hi > worst_p:
            worst_p = dd / bank_hi
    return worst_d, worst_p, when


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------
def selftest():
    ok = True

    def check(cond, msg):
        nonlocal ok
        if not cond:
            print("  FAIL:", msg)
            ok = False

    # (1) variant arithmetic on a hand-built market
    base = dict(n_our=10.0, c_our=9.5, fee_our=fee(0.95, 10), o_oth=1.0,
                fills=[(20, 6.0, 0.55, 0.55, 100, "a"), (19, 4.0, 0.60, 0.60, 100, "b")],
                cov=1.0, q_worst=0.60)
    base["nohedge"] = 0.0 - 9.5 - fee(0.95, 10)
    v0, _, _ = variant(base, 0.0)
    check(abs(v0 - base["nohedge"]) < 1e-12, "k=0 must be the unhedged money")
    v1, _, _ = variant(base, 1.0)
    leg1 = 6 * 0.45 - fee(0.55, 6) + 4 * 0.40 - fee(0.60, 4)
    check(abs(v1 - (base["nohedge"] + leg1)) < 1e-12, "k=1 must be the actual hedge")
    vh, _, _ = variant(base, 0.5)
    check(abs(vh - (base["nohedge"] + 5 * 0.45 - fee(0.55, 5))) < 1e-12,
          "k=0.5 takes the FIRST fills in time order")
    v2, ex, rf = variant(base, 2.0, slip=0.05)
    check(abs(v2 - (v1 + 10 * (1 - 0.65) - fee(0.65, 10))) < 1e-12 and ex == 10 and rf == 0,
          "flip x=1 adds 10 at worst+slip")
    fa = dict(base, o_oth=0.0)
    fa["nohedge"] = 10 - 9.5 - fee(0.95, 10)
    v2f, _, _ = variant(fa, 2.0)
    v1f, _, _ = variant(fa, 1.0)
    check(abs((v2f - v1f) - (-10 * 0.60 - fee(0.60, 10))) < 1e-12,
          "a false alarm loses the extra leg's whole price")
    thin = dict(base, cov=0.1, fills=[(20, 1.0, 0.55, 0.55, 1, "a")])
    _, ex, rf = variant(thin, 2.0)
    check(ex == 0 and abs(rf - 19.0) < 1e-9, "no extra leg where the hedge could not fill")

    # (2) poisson-binomial vs brute force
    rnd = random.Random(3)
    ps = [rnd.uniform(0.1, 0.9) for _ in range(8)]
    for k in range(9):
        brute = 0.0
        for mask in range(256):
            pr = 1.0
            c = 0
            for i in range(8):
                if mask >> i & 1:
                    pr *= ps[i]
                    c += 1
                else:
                    pr *= 1 - ps[i]
            if c >= k:
                brute += pr
        check(abs(brute - poisson_binomial_ge(ps, k)) < 1e-12, "poisson-binomial k=%d" % k)

    # (3) planted worlds: fair price -> flip ~ -fee; 15c cheap -> flip ~ +15c - fee
    for planted, lo, hi in ((0.0, -0.05, 0.02), (0.15, 0.10, 0.17)):
        rnd = random.Random(5)
        tot = 0.0
        ntot = 0.0
        wins = 0
        qs = []
        for _ in range(4000):
            q = rnd.uniform(0.5, 0.85)
            won = rnd.random() < min(0.99, q + planted)
            n = rnd.choice((10.0, 50.0, 100.0))
            m = dict(n_our=n, nohedge=0.0, o_oth=1.0 if won else 0.0,
                     fills=[(10, n, q, q, 999, "a")], cov=1.0, q_worst=q)
            tot += variant(m, 2.0)[0] - variant(m, 1.0)[0]
            ntot += n
            wins += won
            qs.append(q)
        per = tot / ntot
        check(lo < per < hi, "planted edge %.2f read %.3f/contract" % (planted, per))
        pv = poisson_binomial_ge(qs, wins)
        if planted == 0.0:
            check(pv > 0.01, "fair world must not look significant (p=%.3g)" % pv)
        else:
            check(pv < 1e-6, "cheap world must look significant (p=%.3g)" % pv)

    # (4) rule engine on a synthetic per-second market
    conf = [None] * 46
    for t in range(46):
        conf[t] = 0.999 if t > 20 else 0.3
    opp = [0.02 if t > 20 else 0.62 for t in range(46)]
    m = dict(tk="KXBTC15M-26SEP131230-30", close_s=0, want="yes", result="no",
             te=30, n=10.0, cost=9.6, conf=conf, csrc=["idx"] * 46, opp=opp,
             osz=[500.0] * 46, psrc=["tape"] * 46)
    check(fire_tau(m, 0.40) == 20, "fires at the first second under 0.40")
    mm, t, b, src = rule_money(m, 0.40, 2.0)
    want_v = unhedged(m) + 20 * (1 - 0.62) - fee(0.62, 20)
    check(t == 20 and abs(mm - want_v) < 1e-12 and b == 20, "flip x=1 buys 2x at the fire second")
    conf2 = list(conf)
    conf2[19] = 0.9
    conf2[18] = 0.9
    m2 = dict(m, conf=conf2)
    check(fire_tau(m2, 0.40, delay=2) == 15, "a 2 s delay needs 3 printed seconds under")
    check(fire_tau(dict(m, te=15), 0.40) == 14, "never fires before the entry")
    # (5) parser + ticker clock
    lines = ['{"ticker": "KXBTC15M-26SEP131230-30", "want": "yes", "entry": 0.9, "n": 5.0,'
             ' "belief": 0.3, "tau": 20, "threshold": 0.4, "t": "2026-09-13T16:29:40Z", "kind": "hedge_alarm"}',
             '{"ticker": "KXBTC15M-26SEP131230-30", "side": "no", "price": 0.6, "n": 5.0, "ask": 0.6,'
             ' "ask_size": 50, "tau": 20, "belief": 0.3, "order_id": "x", "t": "2026-09-13T16:29:40Z", "kind": "hedge"}',
             '{"ticker": "KXBTC15M-26SEP131230-30", "side": "no", "price": 0.6, "n": 5.0, "ask": 0.6,'
             ' "ask_size": 50, "tau": 20, "belief": 0.3, "order_id": "x", "t": "2026-09-13T16:29:40Z", "kind": "hedge"}',
             '{"ticker": "KXBTC15M-26SEP131230-30", "side": "no", "ask": 0.5, "size": 9, "tau": 21,'
             ' "belief": 0.7, "t": "2026-09-13T16:29:39Z", "kind": "hedge_quote"}']
    lg = parse_lines(lines)
    d = lg.get("KXBTC15M-26SEP131230-30")
    check(d and len(d["alarms"]) == 1 and len(d["hedges"]) == 1 and 21 in d["quotes"],
          "parser keeps one copy of a duplicated order")
    check(close_of_ticker("KXBTC15M-26SEP131230-30") == calendar.timegm((2026, 9, 13, 16, 30, 0)),
          "ticker ET -> UTC")
    # (6) drawdown: a planted $50 dip after a $100 high is found; a deposit
    # in the middle neither hides nor creates one
    t = calendar.timegm((2026, 9, 14, 0, 0, 0))
    rows = {"a": dict(ticker="A", settled_time="2026-09-14T00:00:00Z", v=100.0),
            "b": dict(ticker="B", settled_time="2026-09-14T01:00:00Z", v=-50.0),
            "c": dict(ticker="C", settled_time="2026-09-14T03:00:00Z", v=20.0)}
    xf = {"deposits": [dict(status="applied", finalized_ts=t - 86400, amount_cents=40000, fee_cents=0),
                       dict(status="applied", finalized_ts=t + 7200, amount_cents=100000, fee_cents=0)],
          "withdrawals": []}
    wd, wp, _ = bank_curve(rows, lambda s: s["v"], {}, xf)
    check(abs(wd - 50.0) < 1e-9 and abs(wp - 50.0 / 500.0) < 1e-9, "planted $50 dip on a $500 high (got %.2f, %.3f)" % (wd, wp))
    wd2, _, _ = bank_curve(rows, lambda s: s["v"], {"B": 50.0}, xf)
    check(abs(wd2) < 1e-9, "removing the dip removes the drawdown")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def fmt(v):
    return "%+.2f" % v


def main():
    logs = load_logs()
    led_rows, led_by, L = load_ledger()
    xfers = json.load(open(XFERS, encoding="utf-8"))
    cf_rows = [json.loads(l) for l in gzip.open(CF, "rt", encoding="utf-8")]
    print("live-log tickers with hedge records: %d; ledger settlements: %d; tape rebuild markets: %d"
          % (len(logs), len(led_rows), len(cf_rows)))

    # ---------------- population A ----------------
    A = []
    for tk, lg in logs.items():
        if et_day(tk) < SINCE_ET:
            continue
        m = market_row(tk, lg, led_by.get(tk, []), L.pnl)
        if m:
            A.append(m)
    A.sort(key=lambda m: m["close_s"])
    print("\n=== A. EVERY MARKET WE ACTUALLY HEDGED since ET %s: %d markets, %d closes ===" % (
        SINCE_ET, len(A), len({m["close_s"] for m in A})))
    bad = [m["tk"] for m in A if not m["reconciled"]]
    print("hedge fills in our log vs Kalshi's hedge-side count: %d of %d agree%s" % (
        len(A) - len(bad), len(A), ("; ledger average used for " + ", ".join(bad)) if bad else ""))
    hdr = ("market (ET close)", "want", "res", "b@alarm", "thr", "tau", "N", "hedged",
           "q_first", "q_avg", "q_worst", "actual", "no hedge", "hedge leg")
    print("%-22s %-4s %-3s %7s %5s %4s %6s %6s %7s %6s %7s %8s %8s %9s" % hdr)
    for m in A:
        print("%-22s %-4s %-3s %7.3f %5s %4s %6.1f %6.1f %7.3f %6.3f %7.3f %8s %8s %9s" % (
            coin(m["tk"]) + " " + et_label(m["tk"]), m["want"], m["result"], m["alarm_b"] or -1,
            m["alarm_thr"], m["alarm_tau"], m["n_our"], m["n_h"], m["q_first"], m["q_avg"],
            m["q_worst"], fmt(m["actual"]), fmt(m["nohedge"]), fmt(m["hedge_leg"])))
    tot_act = sum(m["actual"] for m in A)
    tot_nh = sum(m["nohedge"] for m in A)
    saves = [m for m in A if m["o_oth"] == 1.0]
    falses = [m for m in A if m["o_oth"] == 0.0]
    print("TOTAL actual %s | no hedge %s | hedging made %s  (saves %d: %s; false alarms %d: %s)" % (
        fmt(tot_act), fmt(tot_nh), fmt(tot_act - tot_nh), len(saves),
        fmt(sum(m["hedge_leg"] for m in saves)), len(falses), fmt(sum(m["hedge_leg"] for m in falses))))

    def variant_table(sub, label):
        print("\n--- variants, %s: %d markets, %d closes ---" % (label, len(sub), len({m['close_s'] for m in sub})))
        rows = [("no hedge (k=0)", 0.0, 0.0), ("half hedge (k=0.5)", 0.5, 0.0),
                ("live hedge (k=1)", 1.0, 0.0)]
        for x in XS:
            for sl in SLIPS:
                rows.append(("hedge + extra %.2fx @worst+%dc" % (x, round(100 * sl)), 1.0 + x, sl))
        base = {}
        out = {}
        for name, k, sl in rows:
            per = {}
            refused = 0.0
            for m in sub:
                v, ex, rf = variant(m, k, sl)
                per[m["tk"]] = v
                refused += rf
            bc = collections.defaultdict(float)
            for m in sub:
                bc[m["close_s"]] += per[m["tk"]]
            if name.startswith("live"):
                base = per
            out[name] = (per, bc, refused)
        live = out["live hedge (k=1)"][0]
        print("%-34s %9s %9s %24s %8s %7s" % ("variant", "total $", "vs live", "95% CI of vs-live (closes)", "worst mkt", "unfilled"))
        for name, _, _ in rows:
            per, bc, refused = out[name]
            dv = collections.defaultdict(float)
            for m in sub:
                dv[m["close_s"]] += per[m["tk"]] - live[m["tk"]]
            lo, hi = boot_ci(dv)
            print("%-34s %9s %9s        [%+8.2f, %+8.2f] %8s %7.0f" % (
                name, fmt(sum(per.values())), fmt(sum(per.values()) - sum(live.values())), lo, hi,
                fmt(min(per.values())), refused))
        return out

    outA = variant_table(A, "all hedged markets")
    A40 = [m for m in A if (m["try_b"] if m["try_b"] else m["alarm_b"]) < 0.40]
    outA40 = variant_table(A40, "hedges fired with belief UNDER 0.40 (the rule running today)")
    Ahi = [m for m in A if m not in A40]
    variant_table(Ahi, "hedges fired at belief 0.40 or above (old 0.60-0.90 triggers)")

    # extra-leg money per market, x = 1, worst price
    print("\n--- the extra leg alone (x=1, at the worst price the hedge paid), per market ---")
    for m in A:
        v2, ex, rf = variant(m, 2.0)
        v1, _, _ = variant(m, 1.0)
        print("  %-22s b=%.3f  %s  extra %5.1f @ %.3f -> %s%s" % (
            coin(m["tk"]) + " " + et_label(m["tk"]), m["try_b"], "REVERSED (our side won)" if m["o_oth"] == 0 else "continued          ",
            ex, m["q_worst"], fmt(v2 - v1), "  (hedge could not fill; no extra priced)" if rf else ""))

    # ---------------- Q3: model vs market vs outcome at the alarm ----------------
    print("\n=== Q3. AT THE HEDGE: model's chance for the other side vs its price vs what happened ===")
    for label, sub in (("all hedged", A), ("belief under 0.40", A40)):
        pm = [1.0 - m["try_b"] for m in sub]
        pq = [m["q_first"] for m in sub]
        k = int(sum(m["o_oth"] for m in sub))
        n = len(sub)
        print("  %-18s n=%2d  model says other side wins %.1f times (avg %.2f); price says %.1f (avg %.2f);"
              " it won %d  | P(>= %d wins | price fair)=%.3f  P(>= %d | model right)=%.3f" % (
                  label, n, sum(pm), sum(pm) / n, sum(pq), sum(pq) / n, k, k,
                  poisson_binomial_ge(pq, k), k, poisson_binomial_ge(pm, k)))
        cheaper = sum(1 for a, b in zip(pm, pq) if b < a)
        print("  %-18s price below the model's chance in %d of %d markets; avg gap (model - price) %+.1fc" % (
            "", cheaper, n, 100 * sum(a - b for a, b in zip(pm, pq)) / n))
    ns = [m["n_our"] for m in A40 if m["cov"] >= FULL_COVER]
    qs = [m["q_worst"] for m in A40 if m["cov"] >= FULL_COVER]
    print("  smallest edge the under-0.40 set could detect (x=1): $%.0f total, %.0fc a contract over %d markets"
          % (mde_dollars(ns, qs), mde_cents(ns, qs), len(ns)))

    # ---------------- Q4: risk ----------------
    print("\n=== Q4. RISK: worst day, the $200 day cap, the 20% drawdown brake ===")
    day_tot = collections.defaultdict(float)
    for s in led_rows.values():
        tk = s.get("ticker") or ""
        try:
            d = et_day(tk)
        except (IndexError, KeyError, ValueError):
            continue
        if d >= SINCE_ET:
            day_tot[d] += L.pnl(s)
    for scope, S in (("applied to all 16 real hedges", A),
                     ("applied only to the hedges under 0.40 (today's trigger)", A40)):
        print("  -- %s --" % scope)
        for name, k, sl in (("live hedge", 1.0, 0.0), ("no hedge", 0.0, 0.0), ("half", 0.5, 0.0),
                            ("x=0.25", 1.25, 0.0), ("x=0.5", 1.5, 0.0), ("x=1", 2.0, 0.0),
                            ("x=1 +5c", 2.0, 0.05)):
            deltas = {}
            for m in S:
                deltas[m["tk"]] = variant(m, k, sl)[0] - m["actual"]
            dd = dict(day_tot)
            for m in S:
                dd[m["day"]] = dd.get(m["day"], 0.0) + deltas[m["tk"]]
            worst = min(dd.items(), key=lambda kv: kv[1])
            cap = [d for d, v in dd.items() if v <= -200]
            wd, wp, when = bank_curve(led_rows, L.pnl, deltas, xfers)
            print("  %-11s worst ET day %s %s | days at/below -$200: %d %s | max drawdown $%.2f (%.1f%% of the bank at its high), bottom %s ET"
                  % (name, worst[0], fmt(worst[1]), len(cap), cap, wd, 100 * wp,
                     time.strftime("%m-%d %H:%M", time.gmtime(when - 4 * 3600)) if when else "-"))

    # ---------------- population B ----------------
    B = build_popb(logs, led_by, cf_rows)
    print("\n=== B. EVERY POSITION WE HELD since ET %s, per-second rule sweep: %d markets ===" % (SINCE_ET, len(B)))
    print("  belief source: bot-logged seconds %d, index-rebuild seconds %d; price source: bot %d, tape %d" % (
        sum(1 for m in B for s in m["csrc"] if s == "bot"), sum(1 for m in B for s in m["csrc"] if s == "idx"),
        sum(1 for m in B for s in m["psrc"] if s == "bot"), sum(1 for m in B for s in m["psrc"] if s == "tape")))
    base_tot = sum(unhedged(m) for m in B)
    print("  no hedge at all: %s" % fmt(base_tot))
    rules = [(0.40, 1.0, 0), (0.40, 0.5, 0), (0.40, 1.25, 0), (0.40, 1.5, 0), (0.40, 2.0, 0),
             (0.40, 1.0, 1), (0.40, 1.0, 2), (0.40, 1.0, 3), (0.60, 1.0, 0), (0.50, 1.0, 0),
             (0.30, 1.0, 0), (0.25, 1.0, 0), (0.20, 2.0, 0), (0.10, 2.0, 0)]
    ref = {m["tk"]: rule_money(m, 0.40, 1.0, 0)[0] for m in B}
    for trig, k, dl in rules:
        per = {}
        fired = []
        srcs = collections.Counter()
        for m in B:
            v, t, b, src = rule_money(m, trig, k, dl)
            per[m["tk"]] = v
            if t is not None:
                fired.append((m, t, b))
                srcs[src] += 1
        dv = collections.defaultdict(float)
        for m in B:
            dv[m["close_s"]] += per[m["tk"]] - ref[m["tk"]]
        dv = {c: v for c, v in dv.items() if abs(v) > 1e-9}
        lo, hi = boot_ci(dv) if dv else (0.0, 0.0)
        rev = sum(1 for m, t, b in fired if m["result"] == m["want"])
        print("  belief<%.2f k=%.2f delay %ds: fired %2d (reversed %d) price src %s | total %s | vs 0.40 hedge %s [%+.2f, %+.2f]"
              % (trig, k, dl, len(fired), rev, dict(srcs), fmt(sum(per.values())),
                 fmt(sum(per.values()) - sum(ref.values())), lo, hi))
    print("\n  the 0.40 crossings (who they were), and the x=1 extra leg priced there:")
    ex_by_src = collections.defaultdict(float)
    bs = []
    wins_back = 0
    for m in B:
        t = fire_tau(m, 0.40)
        if t is None:
            continue
        prev = next((m["conf"][u] for u in range(t + 1, min(m["te"], 46)) if m["conf"][u] is not None), None)
        v2 = rule_money(m, 0.40, 2.0)
        v1 = rule_money(m, 0.40, 1.0)
        src = v2[3] or "-"
        ex_by_src[src] += v2[0] - v1[0]
        bs.append(m["conf"][t])
        wins_back += int(m["result"] == m["want"])
        print("    %-22s want %-3s res %-3s tau %2d belief %.3f (prev %s) other-side ask %s [%s] N %6.1f  extra leg %s [%s]" % (
            coin(m["tk"]) + " " + et_label(m["tk"]), m["want"], m["result"], t, m["conf"][t],
            "%.3f" % prev if prev is not None else "-", m["opp"][t], m["psrc"][t], m["n"],
            fmt(v2[0] - v1[0]), src))
    print("  x=1 extra leg by price source: %s" % {k: round(v, 2) for k, v in ex_by_src.items()})
    print("  came back %d of %d; the model's own belief said %.2f; P(this few | model right) = %.3f" % (
        wins_back, len(bs), sum(bs), 1.0 - poisson_binomial_ge(bs, wins_back + 1)))

    # ---------------- price-source check ----------------
    print("\n=== PRICE SOURCE CHECK: tape vs the ask our bot logged at the same second ===")
    cfd = {m["tk"]: m for m in cf_rows}
    for label, kind in (("hedge seconds (fast)", "hedges"), ("quiet held seconds", "quotes")):
        tot = ex = w2 = 0
        for tk, lg in logs.items():
            m = cfd.get(tk)
            if not m:
                continue
            recs = lg[kind] if kind == "hedges" else list(lg[kind].values())
            for r in recs:
                tau = r.get("tau")
                a = r.get("ask")
                if tau is None or a is None or not (0 <= int(tau) <= 45):
                    continue
                q = m["opp"][int(tau)]
                if q is None:
                    continue
                tot += 1
                ex += abs(float(a) - q) < 0.0051
                w2 += abs(float(a) - q) <= 0.0201
        print("  %-22s %4d seconds: tape equals our ask %d (%.0f%%), within 2c %d (%.0f%%)" % (
            label, tot, ex, 100.0 * ex / max(tot, 1), w2, 100.0 * w2 / max(tot, 1)))


if __name__ == "__main__":
    if not selftest():
        sys.exit(1)
    if "--selftest" in sys.argv:
        sys.exit(0)
    main()
