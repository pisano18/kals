"""timeedge.py -- WHEN does the live bot make its money? Hour-of-week map.

WHAT IT MEASURES. From our OWN money (Kalshi's ledger, `results/kalshi_ledger.json`,
one row per settled market, both sides netted) and our own live logs
(`results/pinrun-live-*.jsonl`: close_summary supply records, entry orders,
halts and pauses), per ET time cell:

  closes watched, closes traded, markets traded, dollars made, dollars staked,
  cents made per dollar staked (the size-free number), losing markets,
  dollars lost, supply (share of looks that found an offer on the side we
  wanted; share of watched closes where we fired) and fill rate (entry orders
  that got at least one contract).

Cells: ET hour of the trading moment (close minus 30 s -- a 16:00 close is
traded at 15:59, so it belongs to the 3 PM hour), day of week, weekend vs
weekday, US stock-market session, and scheduled-event windows.

WHY. To size up when the edge is big and down when it is not -- IF a time
difference is real. Every earlier "good number" here was a measurement bug or
a population change, so the rule below was written BEFORE the numbers were
read and is enforced in code:

  ACT       |z| >= the multiple-looks (Bonferroni) threshold over every cell
            tested, AND the cell's difference from the rest has the same sign
            in the first half of the ET days and in the second half, with
            |z| >= 1 in each half, AND >= 30 closes traded in the cell.
  CANDIDATE |z| >= 1.96, same sign in both halves, >= 30 closes. Reported,
            NOT proposed.

z compares the cell's cents-per-dollar with the rest of the week's, using a
ratio estimator whose error is clustered BY CLOSE (hard rule 4: every market
settling on one quarter hour is one observation).

A second, honest money number: choose cells on the FIRST half of days
(|z| >= 1.96), halve size in the bad ones and 1.5x in the good ones, and
apply that to the SECOND half, which the choice never saw; and the reverse.

Money source: the ledger only. Tape and replay are never used (CLAUDE.md
amendment 2026-09-10).

    python research/timeedge.py --selftest
    python research/timeedge.py [--since 2026-09-13] [--out FILE]
"""
import argparse
import calendar
import datetime as dt
import glob
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

RESULTS = os.path.join(os.path.dirname(HERE), "results")
LEDGER = os.path.join(RESULTS, "kalshi_ledger.json")
LIVE_GLOB = os.path.join(RESULTS, "pinrun-live-*.jsonl")
CRYPTO = frozenset(["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
                    "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
                    "KXNEAR15M", "KXTON15M"])
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MIN_CLOSES = 30          # CLAUDE.md: floor cluster counts at 30 before claiming anything
TRADE_LEAD_S = 30        # the trading moment is ~30 s before the close
# Scheduled US releases inside the window (checked 2026-09-25, federalreserve.gov
# and the BLS calendar): FOMC statement Wed 2026-09-16 14:00 ET, press conference
# 14:30 ET. August CPI came out 09-11 and the jobs report 09-04 -- both BEFORE the
# window, so neither can be tested here. Weekly jobless claims: Thursdays 08:30 ET.
FOMC_DAY = "2026-09-16"


_EPOCH0 = dt.datetime(1970, 1, 1)


def _utc(epoch):
    """Naive UTC datetime (utcfromtimestamp is deprecated on 3.12+)."""
    return _EPOCH0 + dt.timedelta(seconds=float(epoch))


def et_offset(epoch):
    """UTC-4 from the 2nd Sunday of March to the 1st Sunday of November, else UTC-5.
    Same rule as downtime.et_offset (copied so the self-test has no data dependency)."""
    t = _utc(epoch)
    y = t.year
    mar = dt.datetime(y, 3, 8)
    s = mar + dt.timedelta(days=(6 - mar.weekday()) % 7, hours=7)
    nov = dt.datetime(y, 11, 1)
    e = nov + dt.timedelta(days=(6 - nov.weekday()) % 7, hours=6)
    return -4 * 3600 if s <= t < e else -5 * 3600


def close_epoch_of(ticker):
    """UTC epoch of a market's close, from the ET clock in its ticker, or None.
    KXBTC15M-26SEP170000-00 -> 2026-09-17 00:00 ET; KXBTCD-26SEP2423 -> 23:00 ET."""
    try:
        st = str(ticker).split("-")[1]
        yy, mon, dd = int(st[0:2]), MONTHS[st[2:5].upper()], int(st[5:7])
        hh = int(st[7:9])
        mm = int(st[9:11]) if len(st) >= 11 else 0
    except (IndexError, KeyError, ValueError):
        return None
    local = calendar.timegm((2000 + yy, mon, dd, hh, mm, 0))
    guess = local + 4 * 3600
    return local - et_offset(guess)


def et_local(epoch):
    return _utc(epoch + et_offset(epoch))


def et_str(epoch):
    d = et_local(epoch)
    return "%s %s %d:%02d %s ET" % (DOW[d.weekday()], d.strftime("%m-%d"),
                                    (d.hour % 12) or 12, d.minute,
                                    "AM" if d.hour < 12 else "PM")


def hour_label(h):
    a = "%d %s" % ((h % 12) or 12, "AM" if h < 12 else "PM")
    b = "%d %s" % (((h + 1) % 12) or 12, "AM" if (h + 1) % 24 < 12 else "PM")
    return "%s-%s" % (a, b)


# ---------------------------------------------------------------- cells
def cells_of(close_s):
    """{family: cell label} for a close. The trading moment is close - 30 s."""
    tm = et_local(close_s - TRADE_LEAD_S)
    cl = et_local(close_s)
    wd = tm.weekday()
    weekend = wd >= 5
    mins = tm.hour * 60 + tm.minute
    out = {
        "hour": "%02d %s" % (tm.hour, hour_label(tm.hour)),
        "dow": "%d %s" % (wd, DOW[wd]),
        "weekend": "weekend" if weekend else "weekday",
    }
    if weekend:
        out["session"] = "c weekend"
    elif 9 * 60 + 30 <= mins < 16 * 60:
        out["session"] = "a US stocks open (weekday 9:30 AM-4 PM)"
    else:
        out["session"] = "b weekday, stocks closed"
    ch, cm = cl.hour, cl.minute
    cwd = cl.weekday()
    ev = []
    if cwd < 5 and (ch, cm) in ((8, 30), (8, 45), (9, 0)):
        ev.append("8:30 AM US data window (weekday closes 8:30-9:00)")
    if cwd == 3 and (ch, cm) in ((8, 30), (8, 45), (9, 0)):
        ev.append("Thursday jobless claims (8:30-9:00)")
    if cwd < 5 and (ch, cm) in ((9, 30), (9, 45), (10, 0)):
        ev.append("US stock open (weekday closes 9:30-10:00)")
    if cwd < 5 and (ch, cm) in ((15, 45), (16, 0), (16, 15)):
        ev.append("4 PM stock close (weekday closes 3:45-4:15)")
    if cl.strftime("%Y-%m-%d") == FOMC_DAY and 14 <= ch < 15 or (
            cl.strftime("%Y-%m-%d") == FOMC_DAY and (ch, cm) == (15, 0)):
        ev.append("Fed decision 09-16 (closes 2:00-3:00 PM)")
    if cwd in (6, 0, 1, 2, 3) and (ch, cm) in ((20, 0), (20, 15), (21, 30), (21, 45)):
        ev.append("Asia open (Sun-Thu 8:00, 8:15, 9:30, 9:45 PM)")
    if tm.hour in (19, 20, 21):
        ev.append("7-10 PM ET (slow-order window)")
    out["event"] = ev
    return out


# ---------------------------------------------------------------- data
def ledger_markets(path=LEDGER, since="2026-09-13"):
    """[{ticker, close, pnl, cost, hedged}] for 15-min crypto markets whose close
    falls on or after `since` (ET day). Money = pinledger.pnl (Kalshi's own)."""
    import pinledger
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh).get("settlements", {})
    by = {}
    skipped = 0
    for s in rows.values():
        tk = s.get("ticker") or ""
        if tk.split("-")[0].upper() not in CRYPTO:
            continue
        c = close_epoch_of(tk)
        if c is None:
            skipped += 1
            continue
        if et_local(c - TRADE_LEAD_S).strftime("%Y-%m-%d") < since:
            continue
        m = by.setdefault(tk, {"ticker": tk, "close": c, "pnl": 0.0, "cost": 0.0,
                               "hedged": False})
        m["pnl"] += pinledger.pnl(s)
        yc = pinledger.money(s, "yes_total_cost_dollars")
        nc = pinledger.money(s, "no_total_cost_dollars")
        m["cost"] += yc + nc + pinledger.money(s, "fee_cost")
        m["hedged"] = m["hedged"] or (pinledger.money(s, "yes_count_fp") > 0
                                      and pinledger.money(s, "no_count_fp") > 0)
    return list(by.values()), skipped


def live_records(pattern=LIVE_GLOB, since_file="20260912"):
    """(close_summaries {close: rec}, orders [rec], halts [rec]) from live logs,
    de-duplicated (the logs overlap across restarts)."""
    cs, orders, halts = {}, {}, {}
    for f in sorted(glob.glob(pattern)):
        if os.path.basename(f)[12:20] < since_file:
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"kind"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                k = r.get("kind")
                if k == "close_summary":
                    c = r.get("close")
                    if isinstance(c, (int, float)):
                        old = cs.get(int(c))
                        if old is None or (r.get("looks") or 0) > (old.get("looks") or 0):
                            cs[int(c)] = r
                elif k == "order":
                    oid = r.get("order_id") or r.get("client_order_id") or (r.get("t"), r.get("ticker"))
                    orders[oid] = r
                elif k in ("halt", "pause") or (k == "refused" and "loss" in str(r.get("gate"))):
                    why = str(r.get("why") or r.get("gate") or "")
                    halts[(r.get("t"), why[:60])] = r
    return cs, list(orders.values()), list(halts.values())


# ---------------------------------------------------------------- stats
def ratio_stats(closes):
    """closes: [(pnl, cost)] per close -> cents made per dollar staked."""
    P = sum(p for p, _ in closes)
    C = sum(c for _, c in closes)
    if C <= 0:
        return None
    return 100.0 * P / C


def compare(cell, rest):
    """(diff, z) of cell minus rest, in cents per dollar, clustered by close.

    The variance is the NULL (pooled) one: every close's residual around the
    common rate, scaled by its stake squared. The first version used each
    side's own residuals, and a cell that happened to hold no loss got a
    standard error of ~0 -- 15 of 20 null worlds then 'found' a time edge.
    Losses are rare and large, so only a pooled variance sees them."""
    if len(cell) < 2 or len(rest) < 2:
        return None, None
    Pa = sum(p for p, _ in cell); Ca = sum(c for _, c in cell); Qa = sum(c * c for _, c in cell)
    Pb = sum(p for p, _ in rest); Cb = sum(c for _, c in rest); Qb = sum(c * c for _, c in rest)
    if Ca <= 0 or Cb <= 0:
        return None, None
    R0 = (Pa + Pb) / (Ca + Cb)
    s2 = (sum((p - R0 * c) ** 2 for p, c in cell) + sum((p - R0 * c) ** 2 for p, c in rest)) / (Qa + Qb)
    d = 100.0 * (Pa / Ca - Pb / Cb)
    se = 100.0 * math.sqrt(s2 * (Qa / Ca ** 2 + Qb / Cb ** 2))
    if se <= 0:
        return d, None
    return d, d / se


def perm_threshold(vals, members, n_perm=300, seed=1):
    """95th percentile of the LARGEST |z| over all tested cells when the
    closes' (pnl, cost) are shuffled across time -- the multiple-looks bar
    that respects the fat loss tail. vals: [(p, c)]; members: [[idx]]."""
    rnd = random.Random(seed)
    P = sum(p for p, _ in vals); C = sum(c for _, c in vals)
    R0 = P / C
    s2 = sum((p - R0 * c) ** 2 for p, c in vals) / sum(c * c for _, c in vals)
    Q = sum(c * c for _, c in vals)
    order = list(range(len(vals)))
    mx = []
    for _ in range(n_perm):
        rnd.shuffle(order)
        pv = [vals[i] for i in order]
        best = 0.0
        for idx in members:
            Pa = Ca = Qa = 0.0
            for i in idx:
                p, c = pv[i]
                Pa += p; Ca += c; Qa += c * c
            Cb = C - Ca
            if Ca <= 0 or Cb <= 0:
                continue
            se = math.sqrt(s2 * (Qa / Ca ** 2 + (Q - Qa) / Cb ** 2))
            if se > 0:
                best = max(best, abs((Pa / Ca - (P - Pa) / Cb) / se))
        mx.append(best)
    mx.sort()
    return mx[int(0.95 * len(mx))]


def z_threshold(k, alpha=0.05):
    return statistics.NormalDist().inv_cdf(1 - alpha / (2 * max(1, k)))


def analyse(markets, split_day=None, n_perm=300):
    """markets: [{close, pnl, cost}] -> dict with per-close aggregates, per-cell
    tables, the multiple-looks threshold and the ACT/CANDIDATE verdicts."""
    closes = {}
    for m in markets:
        c = closes.setdefault(m["close"], {"pnl": 0.0, "cost": 0.0, "n": 0, "lost_n": 0,
                                           "lost_d": 0.0, "worst": 0.0})
        c["pnl"] += m["pnl"]
        c["cost"] += m["cost"]
        c["n"] += 1
        if m["pnl"] < 0:
            c["lost_n"] += 1
            c["lost_d"] += m["pnl"]
            c["worst"] = min(c["worst"], m["pnl"])
    days = sorted({et_local(k - TRADE_LEAD_S).strftime("%Y-%m-%d") for k in closes})
    if split_day is None:
        split_day = days[len(days) // 2] if days else ""
    cells = {}
    for k in closes:
        cf = cells_of(k)
        for fam, lab in cf.items():
            labs = lab if isinstance(lab, list) else [lab]
            for l in labs:
                cells.setdefault((fam, l), set()).add(k)
    allk = set(closes)

    def pc(keys):
        return [(closes[k]["pnl"], closes[k]["cost"]) for k in keys]

    def half(keys, first):
        return [k for k in keys
                if (et_local(k - TRADE_LEAD_S).strftime("%Y-%m-%d") < split_day) == first]

    table = []
    for (fam, lab), keys in sorted(cells.items()):
        rest = allk - keys
        R = ratio_stats(pc(keys))
        d, z = compare(pc(keys), pc(rest))
        se = abs(d / z) if (z not in (None, 0) and d is not None) else None
        d1, z1 = compare(pc(half(keys, True)), pc(half(rest, True)))
        d2, z2 = compare(pc(half(keys, False)), pc(half(rest, False)))
        table.append({
            "family": fam, "cell": lab, "closes": len(keys),
            "markets": sum(closes[k]["n"] for k in keys),
            "pnl": sum(closes[k]["pnl"] for k in keys),
            "cost": sum(closes[k]["cost"] for k in keys),
            "cpd": R, "se": se, "diff": d, "z": z,
            "d1": d1, "z1": z1, "d2": d2, "z2": z2,
            "lost_n": sum(closes[k]["lost_n"] for k in keys),
            "lost_closes": sum(1 for k in keys if closes[k]["lost_n"]),
            "lost_d": sum(closes[k]["lost_d"] for k in keys),
            "worst": min([closes[k]["worst"] for k in keys] or [0.0]),
            "keys": keys,
        })
    # Weekend/weekday is ONE comparison (each is the other's complement).
    tested = [r for r in table if r["closes"] >= MIN_CLOSES and r["z"] is not None
              and not (r["family"] == "weekend" and r["cell"] == "weekday")]
    K = len(tested)
    zb = z_threshold(K)
    order = sorted(closes)
    pos = {k: i for i, k in enumerate(order)}
    zp = perm_threshold([(closes[k]["pnl"], closes[k]["cost"]) for k in order],
                        [[pos[k] for k in r["keys"]] for r in tested], n_perm=n_perm) if tested else zb
    zt = max(zb, zp)
    for r in table:
        r["verdict"] = ""
        if r["closes"] < MIN_CLOSES or r["z"] is None:
            r["verdict"] = "too few" if r["closes"] < MIN_CLOSES else ""
            continue
        same = (r["d1"] is not None and r["d2"] is not None and r["z1"] is not None
                and r["z2"] is not None and (r["d1"] > 0) == (r["d2"] > 0) == (r["diff"] > 0))
        if abs(r["z"]) >= zt and same and abs(r["z1"]) >= 1 and abs(r["z2"]) >= 1:
            r["verdict"] = "ACT"
        elif abs(r["z"]) >= 1.96 and same:
            r["verdict"] = "candidate"
        elif abs(r["z"]) >= 1.96 and (r["d1"] is None or r["d2"] is None):
            r["verdict"] = "only one half has data"
        elif abs(r["z"]) >= 1.96:
            r["verdict"] = "flips between halves"
    return {"closes": closes, "table": table, "K": K, "zt": zt, "zb": zb, "zp": zp,
            "days": days, "split_day": split_day}


def holdout_schedule(markets, res):
    """Choose cells on one half (|z| >= 1.96 there, >= 15 closes in that half),
    0.5x size in bad cells / 1.5x in good cells, apply to the OTHER half.
    Returns [(train, test, delta_dollars, cells_used)]. Only the hour and
    session families (disjoint cells) are used so no close is scaled twice."""
    closes = res["closes"]
    split = res["split_day"]

    def first(k):
        return et_local(k - TRADE_LEAD_S).strftime("%Y-%m-%d") < split
    out = []
    for train_first in (True, False):
        train = {k for k in closes if first(k) == train_first}
        test = set(closes) - train
        mult = {}
        used = []
        for fam in ("hour",):
            labs = {}
            for k in closes:
                labs.setdefault(cells_of(k)[fam], set()).add(k)
            for lab, keys in labs.items():
                tk = keys & train
                rest = train - tk
                if len(tk) < 15:
                    continue
                d, z = compare([(closes[k]["pnl"], closes[k]["cost"]) for k in tk],
                               [(closes[k]["pnl"], closes[k]["cost"]) for k in rest])
                if z is None or abs(z) < 1.96:
                    continue
                m = 0.5 if d < 0 else 1.5
                used.append((lab, m, round(z, 2)))
                for k in keys & test:
                    mult[k] = m
        delta = sum((mult.get(k, 1.0) - 1.0) * closes[k]["pnl"] for k in test)
        out.append(("first half" if train_first else "second half",
                    "second half" if train_first else "first half", delta, used))
    return out


# ---------------------------------------------------------------- report
def fmt(x, nd=2, plus=True):
    if x is None:
        return "-"
    return ("%+.*f" if plus else "%.*f") % (nd, x)


def supply_fill(keys, cs, orders_by_close):
    w = [cs[k] for k in keys if k in cs]
    looks = sum((r.get("decided") or r.get("looks") or 0) for r in w)
    no_off = sum((r.get("no_offer") or 0) for r in w)
    fired = sum(1 for r in w if r.get("fired"))
    od = [o for k in keys for o in orders_by_close.get(k, [])]
    sent = len(od)
    got = sum(1 for o in od if (o.get("filled") or 0) > 0)
    lat = sorted(o.get("latency_ms") for o in od if isinstance(o.get("latency_ms"), (int, float)))
    return {
        "watched": len(w),
        "offer_share": (100.0 * (looks - no_off) / looks) if looks else None,
        "fired_share": (100.0 * fired / len(w)) if w else None,
        "sent": sent, "filled": got,
        "fill_pct": (100.0 * got / sent) if sent else None,
        "lat_med": lat[len(lat) // 2] if lat else None,
        "asked": sum(float((o.get("body") or {}).get("count") or 0) for o in od),
        "got_n": sum(float(o.get("filled") or 0) for o in od),
        "edge_med": (lambda e: e[len(e) // 2] if e else None)(sorted(
            r["best_edge_c"] for r in w if isinstance(r.get("best_edge_c"), (int, float)))),
    }


def report(since="2026-09-13", out=print):
    markets, skipped = ledger_markets(since=since)
    cs, orders, halts = live_records()
    cs = {k: v for k, v in cs.items()
          if et_local(k - TRADE_LEAD_S).strftime("%Y-%m-%d") >= since}
    obc = {}
    for o in orders:
        c = close_epoch_of(o.get("ticker") or "")
        if c is None or o.get("status_code") not in (200, 201):
            continue
        if et_local(c - TRADE_LEAD_S).strftime("%Y-%m-%d") < since:
            continue
        obc.setdefault(c, []).append(o)
    res = analyse(markets)
    closes = res["closes"]
    tot_p = sum(c["pnl"] for c in closes.values())
    tot_c = sum(c["cost"] for c in closes.values())
    out("# timeedge raw output (ledger money, ET cells)")
    out("markets %d, closes traded %d, ET days %s..%s (%d), split at %s; ledger rows skipped %d"
        % (len(markets), len(closes), res["days"][0], res["days"][-1], len(res["days"]),
           res["split_day"], skipped))
    out("total $%.2f on $%.2f staked = %.3f c per $; losing markets %d, losing closes %d"
        % (tot_p, tot_c, 100 * tot_p / tot_c,
           sum(c["lost_n"] for c in closes.values()),
           sum(1 for c in closes.values() if c["lost_n"])))
    out("close_summaries (closes watched) %d; entry orders %d" % (len(cs), sum(len(v) for v in obc.values())))
    out("multiple looks: %d cells tested (>= %d closes each) -> |z| must reach %.2f "
        "(Bonferroni %.2f; shuffled-time 95th pct of the largest |z| %.2f)"
        % (res["K"], MIN_CLOSES, res["zt"], res["zb"], res["zp"]))
    # MDE for a median-size hour cell
    hrs = [r for r in res["table"] if r["family"] == "hour" and r["se"]]
    if hrs:
        mse = sorted(r["se"] for r in hrs)[len(hrs) // 2]
        out("smallest difference a typical hour cell could show at that bar (80%% power): ~%.2f c per $"
            % ((res["zt"] + 0.84) * mse))
    for fam in ("dow", "session", "weekend"):
        fs = [r for r in res["table"] if r["family"] == fam and r["se"]]
        if fs:
            m = sorted(r["se"] for r in fs)[len(fs) // 2]
            out("  same for a typical %s cell: ~%.2f c per $" % (fam, (res["zt"] + 0.84) * m))
    allw = set(cs) | set(closes)
    for fam in ("hour", "dow", "weekend", "session", "event"):
        out("")
        out("## %s" % fam)
        out("| cell | watched | traded | mkts | $ made | $ staked | c/$ | vs rest | z | half1 | half2 | lost mkts | $ lost | worst | offer% | fired% | orders | filled% | ms | best edge c | verdict |")
        out("|" + "---|" * 21)
        for r in [x for x in res["table"] if x["family"] == fam]:
            keys_w = {k for k in allw if (lambda cf: (cf[fam] if not isinstance(cf[fam], list) else None) == r["cell"]
                      or (isinstance(cf[fam], list) and r["cell"] in cf[fam]))(cells_of(k))}
            sf = supply_fill(keys_w, cs, obc)
            out("| %s | %d | %d | %d | %s | %.0f | %s | %s | %s | %s | %s | %d | %s | %s | %s | %s | %d | %s | %s | %s | %s |" % (
                r["cell"], sf["watched"], r["closes"], r["markets"], fmt(r["pnl"]), r["cost"],
                fmt(r["cpd"], 3), fmt(r["diff"], 3), fmt(r["z"]), fmt(r["d1"], 3), fmt(r["d2"], 3),
                r["lost_n"], fmt(r["lost_d"]), fmt(r["worst"]), fmt(sf["offer_share"], 1, False),
                fmt(sf["fired_share"], 1, False), sf["sent"], fmt(sf["fill_pct"], 1, False),
                fmt(sf["lat_med"], 0, False), fmt(sf["edge_med"], 1, False), r["verdict"]))
    out("")
    out("## supply and fills by ET hour, first half of days vs second half")
    split = res["split_day"]
    hs = {}
    for k in allw:
        h = et_local(k - TRADE_LEAD_S).hour
        f = et_local(k - TRADE_LEAD_S).strftime("%Y-%m-%d") < split
        hs.setdefault((h, f), set()).add(k)
    a1, a2, f1, f2 = [], [], [], []
    out("| hour | offer% h1 | offer% h2 | fired% h1 | fired% h2 | fill% h1 | fill% h2 |")
    out("|---|---|---|---|---|---|---|")
    for h in range(24):
        s1 = supply_fill(hs.get((h, True), set()), cs, obc)
        s2 = supply_fill(hs.get((h, False), set()), cs, obc)
        out("| %s | %s | %s | %s | %s | %s | %s |" % (hour_label(h), fmt(s1["offer_share"], 1, False),
            fmt(s2["offer_share"], 1, False), fmt(s1["fired_share"], 1, False), fmt(s2["fired_share"], 1, False),
            fmt(s1["fill_pct"], 1, False), fmt(s2["fill_pct"], 1, False)))
        if s1["offer_share"] is not None and s2["offer_share"] is not None:
            a1.append(s1["offer_share"]); a2.append(s2["offer_share"])
        if s1["fired_share"] is not None and s2["fired_share"] is not None:
            f1.append(s1["fired_share"]); f2.append(s2["fired_share"])
    out("rank agreement of the hourly pattern between halves: offer share %.2f, fired share %.2f "
        "(1 = same order both halves, 0 = unrelated)" % (spearman(a1, a2), spearman(f1, f2)))
    # 7-10 PM ET fills vs the rest (latency audit claim)
    ev = [o for k, os_ in obc.items() for o in os_ if et_local(k - TRADE_LEAD_S).hour in (19, 20, 21)]
    ot = [o for k, os_ in obc.items() for o in os_ if et_local(k - TRADE_LEAD_S).hour not in (19, 20, 21)]
    def fr(os_):
        n = len(os_); g = sum(1 for o in os_ if (o.get("filled") or 0) > 0)
        asked = sum(float((o.get("body") or {}).get("count") or 0) for o in os_)
        got = sum(float(o.get("filled") or 0) for o in os_)
        return n, g, asked, got
    n1, g1, as1, go1 = fr(ev)
    n2, g2, as2, go2 = fr(ot)
    pp = (g1 + g2) / float(n1 + n2) if n1 + n2 else 0
    zf = ((g1 / float(n1) - g2 / float(n2)) / math.sqrt(pp * (1 - pp) * (1.0 / n1 + 1.0 / n2))) if n1 and n2 and 0 < pp < 1 else None
    out("")
    out("7-10 PM ET entry orders: %d sent, %d got a fill (%.1f%%); contracts %.0f of %.0f asked (%.1f%%)"
        % (n1, g1, 100.0 * g1 / max(1, n1), go1, as1, 100.0 * go1 / max(1, as1)))
    out("all other hours:        %d sent, %d got a fill (%.1f%%); contracts %.0f of %.0f asked (%.1f%%); z = %s"
        % (n2, g2, 100.0 * g2 / max(1, n2), go2, as2, 100.0 * go2 / max(1, as2), fmt(zf)))
    out("")
    out("## holdout: choose hour cells on one half (|z|>=1.96), 0.5x/1.5x, apply to the other")
    for tr, te, delta, used in holdout_schedule(markets, res):
        out("train %s -> test %s: %+.2f dollars; cells %s" % (tr, te, delta, used))
    acts = [r for r in res["table"] if r["verdict"] == "ACT"]
    out("")
    out("## ACT cells: %d" % len(acts))
    for r in acts:
        m = 0.5 if r["diff"] < 0 else 1.5
        delta = sum((m - 1.0) * closes[k]["pnl"] for k in r["keys"])
        out("%s / %s: %sx size -> %+.2f dollars on the record (in-sample)" % (r["family"], r["cell"], m, delta))
    out("")
    out("## halts and pauses since %s (ET)" % since)
    seen = set()
    for h in sorted(halts, key=lambda x: x.get("t") or ""):
        t = h.get("t") or ""
        try:
            e = calendar.timegm(time_parse(t))
        except ValueError:
            continue
        if et_local(e).strftime("%Y-%m-%d") < since:
            continue
        why = str(h.get("why") or h.get("gate") or "")
        key = why[:40]
        tag = "%s | %s | %s" % (h.get("kind"), et_str(e), why[:110])
        if (key, et_local(e).strftime("%m-%d %H")) in seen:
            continue
        seen.add((key, et_local(e).strftime("%m-%d %H")))
        out(tag)
    # the per-day money, to see which days dominate
    out("")
    out("## ET day money (ledger, 15-min crypto)")
    byday = {}
    for k, c in closes.items():
        d = et_local(k - TRADE_LEAD_S).strftime("%Y-%m-%d %a")
        b = byday.setdefault(d, [0.0, 0.0, 0, 0])
        b[0] += c["pnl"]; b[1] += c["cost"]; b[2] += 1; b[3] += c["lost_n"]
    for d in sorted(byday):
        b = byday[d]
        out("%s  $%+8.2f  staked $%9.2f  %.3f c/$  closes %3d  lost mkts %d" % (d, b[0], b[1], 100 * b[0] / b[1], b[2], b[3]))
    # biggest losing closes in ET
    out("")
    out("## the 15 worst closes (ET)")
    for k in sorted(closes, key=lambda k: closes[k]["pnl"])[:15]:
        c = closes[k]
        out("%s  $%+.2f  (%d markets, %d lost)" % (et_str(k), c["pnl"], c["n"], c["lost_n"]))
    return res


def spearman(a, b):
    if len(a) < 3:
        return float("nan")
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(o):
            r[i] = float(pos)
        return r
    ra, rb = rk(a), rk(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def time_parse(t):
    import time
    return time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- self-test
def _world(seed, planted_hour=None, days=14, bad_p=0.15):
    """Synthetic ledger: `days` ET days from 2026-09-13, 96 closes a day,
    closes traded (80%) with 1-4 markets each. Win: +2.3% of cost. Loss (1 in 100):
    -35% to -100% of cost. If planted_hour is set, closes traded in that ET hour
    lose with probability bad_p instead."""
    rnd = random.Random(seed)
    base = close_epoch_of("KXBTC15M-26SEP130015-15")
    ms = []
    for i in range(days * 96):
        c = base + i * 900
        if rnd.random() > 0.8:
            continue
        hr = et_local(c - TRADE_LEAD_S).hour
        p_loss = bad_p if (planted_hour is not None and hr == planted_hour) else 0.01
        for j in range(rnd.randint(1, 4)):
            cost = rnd.uniform(40, 100)
            if rnd.random() < p_loss:
                pnl = -cost * rnd.uniform(0.35, 1.0)
            else:
                pnl = cost * 0.023
            ms.append({"ticker": "T%d-%d" % (i, j), "close": c, "pnl": pnl, "cost": cost})
    return ms


def selftest():
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)
        print(("ok   " if cond else "FAIL ") + msg)

    # 1. clocks
    ck(close_epoch_of("KXBTC15M-26SEP170000-00") == calendar.timegm((2026, 9, 17, 4, 0, 0)),
       "ticker 26SEP170000 -> 2026-09-17 04:00Z (midnight EDT)")
    ck(close_epoch_of("KXBTC15M-26NOV100000-00") == calendar.timegm((2026, 11, 10, 5, 0, 0)),
       "November ticker uses EST (UTC-5)")
    ck(close_epoch_of("KXBTCD-26SEP2423-T84399.99") == calendar.timegm((2026, 9, 25, 3, 0, 0)),
       "hourly ticker 26SEP2423 -> 23:00 ET")
    c16 = close_epoch_of("KXETH15M-26SEP221600-00")
    ck(cells_of(c16)["hour"].startswith("15 "), "a 4:00 PM close is traded in the 3 PM hour")
    ck("4 PM stock close (weekday closes 3:45-4:15)" in cells_of(c16)["event"],
       "Tue 4:00 PM close is in the stock-close window")
    ck(cells_of(close_epoch_of("KXETH15M-26SEP191600-00"))["session"] == "c weekend",
       "Saturday 09-19 is weekend")
    ck("Fed decision 09-16 (closes 2:00-3:00 PM)" in cells_of(close_epoch_of("KXBTC15M-26SEP161415-15"))["event"],
       "09-16 2:15 PM close is in the Fed window")

    # 2. clustering: 12 markets on one close count as ONE close
    one = [{"close": c16, "pnl": 1.0, "cost": 50.0} for _ in range(12)]
    r = analyse(one)
    ck(len(r["closes"]) == 1 and r["closes"][c16]["n"] == 12, "12 markets on one close -> n = 1 close")

    # 3. ratio estimator: known mean
    R = ratio_stats([(2.0, 100.0)] * 50 + [(-50.0, 100.0)])
    ck(abs(R - 100 * (100 - 50) / 5100) < 1e-9, "cents per dollar = sum pnl / sum cost")

    # 4. planted: hour 3 ET loses 15 times in 100 -> must be ACT, negative, in both halves
    res = analyse(_world(7, planted_hour=3))
    h3 = [x for x in res["table"] if x["family"] == "hour" and x["cell"].startswith("03 ")][0]
    ck(h3["verdict"] == "ACT" and h3["diff"] < 0,
       "planted bad hour found: verdict %s z %.2f (bar %.2f)" % (h3["verdict"], h3["z"], res["zt"]))
    others = [x for x in res["table"] if x["family"] == "hour" and x["verdict"] == "ACT"
              and not x["cell"].startswith("03 ")]
    ck(len(others) == 0, "no other hour flagged in the planted world (%d)" % len(others))
    ho = holdout_schedule(_world(7, planted_hour=3), res)
    ck(all(d > 0 for _, _, d, _ in ho), "holdout schedule SAVES money when an hour is truly bad: %s"
       % [round(d, 2) for _, _, d, _ in ho])

    # 5. null worlds: nothing planted -> ACT must (almost) never fire
    false_act = 0
    for s in range(20):
        rr = analyse(_world(100 + s), n_perm=150)
        if any(x["verdict"] == "ACT" for x in rr["table"]):
            false_act += 1
    ck(false_act <= 2, "null worlds with any ACT cell: %d of 20 (allowed <= 2)" % false_act)
    # 6. spearman sanity
    ck(abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-9 and
       abs(spearman([1, 2, 3, 4], [40, 30, 20, 10]) + 1) < 1e-9, "rank agreement +1 / -1")
    # 7. POWER, informational: a realistic effect (5 losses in 100 in one hour vs 1 in 100)
    rm = analyse(_world(9, planted_hour=3, bad_p=0.05), n_perm=100)
    h3m = [x for x in rm["table"] if x["family"] == "hour" and x["cell"].startswith("03 ")][0]
    print("info moderate planted hour (5 in 100 losses): z %.2f vs bar %.2f, verdict '%s'"
          % (h3m["z"], rm["zt"], h3m["verdict"]))
    print("self-test %s" % ("FAILED (%d)" % len(fails) if fails else "passed"))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--since", default="2026-09-13")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        print("self-test failed; refusing to read real data")
        sys.exit(1)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)
    report(a.since, out=say)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
