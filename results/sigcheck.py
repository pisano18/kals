"""Did sigma-at-entry understate what the coin then did?  (read-only, streaming)

For every pin signal, realized = sd of one-second DOLLAR price differences from
the signal's second to the last settlement print (close-1), in the SAME units
as pinrun's `_sig_over` (demeaned, n-1).  ratio = realized / sigma_logged.
Never imports replay.py; never loads a whole hour into memory.
"""
import calendar, collections, glob, gzip, json, math, os, statistics, sys
from statistics import NormalDist

ND = NormalDist()
RESULTS = r"C:\kals-repo\results"
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sigcheck_out.json")
SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI", "KXBNB15M": "BNBUSD_RTI",
    "KXBCH15M": "BCHUSD_RTI", "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}
N_AVG = 60
ET_OFF_SEP = -4 * 3600      # EDT; every signal here is 2026-09-08..09-18
_MON = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}


def close_epoch(ticker):
    import re
    m = re.match(r"^[A-Z0-9]+-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?:-|$)", ticker)
    if not m:
        return None
    yy, mon, dd, hh, mm = m.groups()
    naive = calendar.timegm((2000 + int(yy), _MON[mon], int(dd), int(hh), int(mm), 0))
    return naive - ET_OFF_SEP


def iso_epoch(s):
    return calendar.timegm((int(s[0:4]), int(s[5:7]), int(s[8:10]),
                            int(s[11:13]), int(s[14:16]), int(s[17:19])))


def vf(r):
    """var_factor(r, [1.0]) for r <= 60: sum_{k=1..r} k^2 / 60^2."""
    return (r * (r + 1) * (2 * r + 1) / 6.0) / (N_AVG ** 2)


def eff_strike(strike, digits):
    if digits is None:
        return float(strike)
    return float(strike) - 0.5 * (10.0 ** (-int(digits)))


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def bucket(tau):
    if 31 <= tau <= 45:
        return "31-45"
    if 3 <= tau <= 30:
        return "3-30"
    return None


# ------------------------------------------------------------ 1. signals
files = sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))
               + glob.glob(os.path.join(RESULTS, "pinrun-paper-*.jsonl")))
signals = []                                  # dicts
settled = collections.defaultdict(list)       # (file, ticker) -> [rec]
settled_any = collections.defaultdict(list)   # (group, ticker) -> [rec]
ruler_of = {}
edge_floor_of = {}
pin_of = {}
for f in files:
    grp = "live" if os.path.basename(f).startswith("pinrun-live") else "paper"
    pending = collections.defaultdict(collections.deque)   # ticker -> signals awaiting order
    with open(f, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            if k == "start":
                ruler_of[f] = r.get("sigma_ruler", "live")
                edge_floor_of[f] = r.get("edge_floor")
                pin_of[f] = r.get("pin")
            elif k == "signal":
                s = dict(r)
                s["_file"] = f
                s["_grp"] = grp
                s["_filled"] = None
                signals.append(s)
                if grp == "live":
                    pending[r["ticker"]].append(s)
            elif k == "order" and grp == "live":
                q = pending.get(r.get("ticker"))
                if q:
                    s = q.popleft()
                    s["_filled"] = r.get("filled")
                    s["_order_status"] = r.get("status")
            elif k == "settled":
                settled[(f, r.get("ticker"))].append(r)
                settled_any[(grp, r.get("ticker"))].append(r)

# ------------------------------------------------------------ 2. units
# one unit per (group, ticker, bucket): the EARLIEST signal in that bucket
# (max tau); live additionally requires that signal's own order to have filled.
units = {}
dropped = collections.Counter()
for s in signals:
    b = bucket(int(s["tau"]))
    if b is None:
        dropped[(s["_grp"], "tau_out_of_range")] += 1
        continue
    if s["_grp"] == "live":
        if s["_filled"] is None:
            dropped[("live", "no_order_record")] += 1
            continue
        if s["_filled"] <= 0:
            dropped[("live", "unfilled")] += 1
            continue
    ser = s["ticker"].split("-")[0]
    iid = SERIES_TO_INDEX.get(ser)
    if iid is None:
        dropped[(s["_grp"], "unknown_series:" + ser)] += 1
        continue
    key = (s["_grp"], s["ticker"], b)
    cur = units.get(key)
    if cur is None or (s["tau"], -iso_epoch(s["t"])) > (cur["tau"], -iso_epoch(cur["t"])):
        units[key] = s
    units[key]["_n_signals"] = (cur["_n_signals"] + 1) if cur else 1

# outcome join.  A file can hold several `settled` records for one ticker:
# ONE PER FILL LOT (NEAR-26SEP082045 has three, costs 0.962/0.956/0.73
# matching three fills) and, when a hedge fired, lots on the other side too.
# So the market's money is the plain sum.  Two outcome labels are kept:
#   _wrong : the model's side lost (want != result)  -- what sigma can explain
#   _lost  : net pnl over every lot < 0               -- the operator's money
# They differ when the model's leg won and the hedge leg cost more.
def _net(recs):
    legs = collections.defaultdict(float)
    for r in recs:
        legs[r.get("want")] += (r.get("pnl_c") or 0)
    return sum(legs.values()), dict(legs)

no_outcome = collections.Counter()
for key, s in list(units.items()):
    recs = settled.get((s["_file"], s["ticker"])) or []
    src = "same_file"
    if not recs:
        recs = settled_any.get((s["_grp"], s["ticker"])) or []
        src = "other_file"
    if not recs:
        no_outcome[s["_grp"]] += 1
        del units[key]
        continue
    net, last = _net(recs)
    s["_result"] = recs[-1].get("result")
    s["_pnl_c"] = net
    s["_pnl_legs"] = last
    s["_lost"] = net < 0
    s["_wrong"] = s["_result"] != s["want"]
    s["_outcome_src"] = src

# close time and window.  The record's `t` can lag the loop's now_s by 1-2 s
# (16 of 919 units), so the ticker's close is the anchor and t_s = close-tau.
close_mismatch = 0
for key, s in units.items():
    close_s = close_epoch(s["ticker"])
    t_s = close_s - int(s["tau"])
    if iso_epoch(s["t"]) + int(s["tau"]) != close_s:
        close_mismatch += 1
    s["_t_s"] = t_s
    s["_close_s"] = close_s
    s["_iid"] = SERIES_TO_INDEX[s["ticker"].split("-")[0]]

# ------------------------------------------------------------ 3. tape
need = collections.defaultdict(set)           # iid -> secs needed
hours = collections.defaultdict(set)          # hour_name -> iids
for s in units.values():
    lo, hi = s["_close_s"] - N_AVG, s["_close_s"] - 1
    need[s["_iid"]].update(range(lo, hi + 1))
    for sec in (lo, hi, hi + 2):
        hours[sec // 3600 * 3600].add(s["_iid"])

prints = {}                                   # (iid, sec) -> value (last seen)
dups = 0
torn = []
missing = []
import time as _time
t0 = _time.time()
for hsec in sorted(hours):
    import datetime as _dt
    name = _dt.datetime.fromtimestamp(hsec, _dt.timezone.utc).strftime("%Y%m%dT%H") + ".jsonl.gz"
    path = os.path.join(IDXDIR, name)
    if not os.path.exists(path):
        missing.append(name)
        continue
    ids = tuple(hours[hsec])
    tags = tuple('"' + i + '"' for i in ids)
    try:
        fh = gzip.open(path, "rt", encoding="utf-8", errors="replace")
    except OSError:
        torn.append(name)
        continue
    try:
        with fh:
            for line in fh:
                if not any(t in line for t in tags):
                    continue
                try:
                    m = json.loads(line).get("msg") or {}
                except ValueError:
                    continue
                iid = m.get("index_id")
                if iid not in ids:
                    continue
                try:
                    d = json.loads(m.get("data") or "{}")
                    sec = int(d["time"]) // 1000
                    v = float(d["value"])
                except (KeyError, TypeError, ValueError):
                    continue
                if sec in need[iid]:
                    if (iid, sec) in prints:
                        dups += 1
                    prints[(iid, sec)] = v
    except Exception as e:                                          # noqa: BLE001
        torn.append(name + " (" + type(e).__name__ + ")")
print(f"tape pass: {len(hours)} hours in {_time.time()-t0:.0f}s, prints kept {len(prints)}, "
      f"dup secs {dups}, missing files {len(missing)}, torn {len(torn)}", file=sys.stderr)

# ------------------------------------------------------------ 4. per-unit measures
for s in units.values():
    iid, t_s, close_s = s["_iid"], s["_t_s"], s["_close_s"]
    sg = float(s["sigma"])
    secs = [x for x in range(t_s, close_s) if (iid, x) in prints]
    diffs = [prints[(iid, secs[i])] - prints[(iid, secs[i - 1])]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    s["_n_after"] = len(secs)
    s["_n_diffs"] = len(diffs)
    if len(diffs) >= 2 and sg > 0:
        mu = sum(diffs) / len(diffs)
        s["_realized"] = math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))
        s["_ratio"] = s["_realized"] / sg
        s["_maxmove_sd"] = max(abs(x) for x in diffs) / sg
    else:
        s["_realized"] = s["_ratio"] = s["_maxmove_sd"] = None
    # the settlement outcome from the tape, for a sanity check against result
    win = [prints.get((iid, x)) for x in range(close_s - N_AVG, close_s)]
    have = [v for v in win if v is not None]
    s["_n_window"] = len(have)
    K = eff_strike(s["strike"], s.get("digits"))
    s["_settle_z"] = None
    if len(have) == N_AVG:
        m60 = sum(have) / N_AVG
        s["_tape_result"] = "yes" if m60 >= K else "no"
        # where settlement actually landed, in the model's own sd units at
        # entry (negative = on the losing side of the strike)
        sd0 = sg * math.sqrt(vf(int(s["tau"])))
        if sd0 > 0:
            zz = (m60 - K) / sd0
            s["_settle_z"] = zz if s["want"] == "yes" else -zz
    else:
        s["_tape_result"] = None
    # recompute the model's z from the tape; try both conventions for whether
    # the print AT the signal second was already held (r = tau or tau-1)
    best = None
    for r in (int(s["tau"]), int(s["tau"]) - 1):
        n_lock = N_AVG - r
        lock = [prints.get((iid, x)) for x in range(close_s - N_AVG, close_s - N_AVG + n_lock)]
        got = [v for v in lock if v is not None]
        if n_lock > 0 and len(got) < 0.95 * n_lock:
            continue
        if len(got) < n_lock:                      # interior gap: nearest print
            filled = []
            for i, v in enumerate(lock):
                if v is None:
                    cands = [(abs(j - i), lock[j]) for j in range(len(lock)) if lock[j] is not None]
                    v = min(cands)[1]
                filled.append(v)
            got = filled
        mu = (sum(got) + r * float(s["spot"])) / N_AVG
        sd = sg * math.sqrt(vf(r)) if r > 0 else 0.0
        if sd <= 0:
            continue
        z_yes = (mu - K) / sd
        z = z_yes if s["want"] == "yes" else -z_yes
        # the logged `fair` is ALWAYS P(YES) (pinrun line 6484:
        # _conf = f if want == "yes" else 1 - f), so compare on the YES side
        fr = ND.cdf(z_yes)
        err = abs(fr - float(s["fair"]))
        if best is None or err < best[0]:
            best = (err, r, z, ND.cdf(z))
    if best:
        s["_z_re"], s["_fair_re"], s["_fair_err"], s["_r_used"] = best[2], best[3], best[0], best[1]
    else:
        s["_z_re"] = s["_fair_re"] = s["_fair_err"] = s["_r_used"] = None

# ------------------------------------------------------------ 5. tables
def cell(us):
    rs = [u["_ratio"] for u in us if u["_ratio"] is not None]
    n = len(us)
    closes = len({u["_close_s"] for u in us})
    out = dict(n_markets=n, n_closes=closes, n_with_ratio=len(rs),
               n_netloss=sum(1 for u in us if u["_lost"]),
               median_ndiffs=(statistics.median([u["_n_diffs"] for u in us]) if us else None))
    if rs:
        out.update(median=pct(rs, .5), p75=pct(rs, .75), p90=pct(rs, .9),
                   n_gt15=sum(1 for x in rs if x > 1.5), n_gt20=sum(1 for x in rs if x > 2.0),
                   median_maxmove_sd=statistics.median([u["_maxmove_sd"] for u in us if u["_maxmove_sd"] is not None]))
    return out


tables = {}
for grp in ("live", "paper"):
    for b in ("31-45", "3-30", "16-30"):
        for outcome in ("WRONG", "RIGHT"):
            us = [u for (g, tk, bb), u in units.items()
                  if g == grp and (bb == b if b != "16-30" else (bb == "3-30" and 16 <= u["tau"] <= 30))
                  and (u["_wrong"] == (outcome == "WRONG"))]
            tables[(grp, b, outcome)] = cell(us)

# alignment / sanity
align = collections.Counter()
for u in units.values():
    if u["_fair_err"] is None:
        align["no_recompute"] += 1
    elif u["_fair_err"] < 1e-3:
        align["fair_within_0.001"] += 1
    elif u["_fair_err"] < 1e-2:
        align["fair_within_0.01"] += 1
    else:
        align["fair_off_more"] += 1
    if u["_tape_result"] is None:
        align["tape_window_incomplete"] += 1
    elif u["_tape_result"] == u["_result"]:
        align["tape_result_agrees"] += 1
    else:
        align["tape_result_DISAGREES"] += 1
    align["lost_ne_wrong"] += int(u["_lost"] != u["_wrong"])
    if u["_grp"] == "live" and ruler_of.get(u["_file"], "live") != "live":
        align["live_units_nonlive_ruler"] += 1
    if u["_grp"] == "paper" and ruler_of.get(u["_file"], "live") != "live":
        align["paper_units_nonlive_ruler"] += 1

# stress rule at PIN=0.995 with z recomputed from the tape; also the edge floor
stress = {}
for grp in ("live", "paper"):
    for k in (1.5, 2.0):
        for outcome in ("WRONG", "RIGHT"):
            us = [u for (g, tk, bb), u in units.items() if g == grp and bb == "31-45"
                  and (u["_wrong"] == (outcome == "WRONG"))]
            n_ok = n_refuse_pin = n_refuse_edge = n_na = 0
            for u in us:
                z = u["_z_re"]
                if z is None:
                    n_na += 1
                    continue
                fr = ND.cdf(z / k)
                p = float(u["price"])
                fee = 0.07 * p * (1 - p)
                ef = edge_floor_of.get(u["_file"])
                ef = float(ef) if ef is not None else 0.0
                if fr < 0.995:
                    n_refuse_pin += 1
                elif fr - p - fee < ef:
                    n_refuse_edge += 1
                else:
                    n_ok += 1
            stress[(grp, k, outcome)] = dict(n=len(us), still_ok=n_ok, refused_pin=n_refuse_pin,
                                              refused_edge=n_refuse_edge, no_z=n_na)

losers = []
for (g, tk, bb), u in sorted(units.items(), key=lambda kv: (kv[0][0], kv[1]["t"])):
    if bb == "31-45" and (u["_wrong"] or u["_lost"]):
        losers.append(dict(group=g, ticker=tk, t=u["t"], tau=u["tau"], want=u["want"], price=u["price"],
                           fair=u["fair"], sigma=u["sigma"], realized=u["_realized"], ratio=u["_ratio"],
                           maxmove_sd=u["_maxmove_sd"], n_diffs=u["_n_diffs"], result=u["_result"],
                           pnl_c=u["_pnl_c"], pnl_legs=u.get("_pnl_legs"), settle_z=u["_settle_z"],
                           z_re=u["_z_re"], fair_re=u["_fair_re"], r_used=u["_r_used"],
                           filled=u.get("_filled"), n_signals=u["_n_signals"], ruler=ruler_of.get(u["_file"], "live"),
                           file=os.path.basename(u["_file"])))

report = dict(
    n_signal_lines=len(signals), dropped=dict((f"{a}:{b}", c) for (a, b), c in dropped.items()),
    no_outcome=dict(no_outcome), close_mismatch=close_mismatch,
    tape=dict(hours=len(hours), prints=len(prints), dup_secs=dups, missing=missing, torn=torn),
    align=dict(align),
    edge_floors=sorted({v for v in edge_floor_of.values() if v is not None}),
    pins_31_45={grp: sorted({pin_of.get(u["_file"]) for (g, tk, bb), u in units.items() if g == grp and bb == "31-45"}) for grp in ("live", "paper")},
    tables={f"{g}|{b}|{o}": v for (g, b, o), v in tables.items()},
    stress={f"{g}|x{k}|{o}": v for (g, k, o), v in stress.items()},
    losers_31_45=losers,
    units=[{k: v for k, v in u.items() if k not in ("ladder",)} for u in units.values()],
)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1, default=str)

# ------------------------------------------------------------ 6. print
def fmt(x, d=2):
    return "-" if x is None else f"{x:.{d}f}"

print("signal lines:", len(signals), "| dropped:", report["dropped"], "| no outcome:", report["no_outcome"],
      "| close mismatch:", close_mismatch)
print("tape:", report["tape"]["hours"], "hours; missing", len(missing), missing, "; torn", len(torn), torn, "; dup secs", dups)
print("alignment:", report["align"])
print("edge floors seen:", report["edge_floors"], "| pins on 31-45 units:", report["pins_31_45"])
print()
hdr = f"{'group':6} {'tau':6} {'side':5} {'n_mkts':>6} {'n_close':>7} {'net$<0':>6} {'n_rat':>5} {'med_nd':>6} {'median':>7} {'p75':>7} {'p90':>7} {'>1.5':>6} {'>2.0':>6} {'medmax_sd':>9}"
print(hdr)
for (g, b, o), c in tables.items():
    n = c["n_with_ratio"]
    f15 = f"{c.get('n_gt15',0)}/{n}" if n else "-"
    f20 = f"{c.get('n_gt20',0)}/{n}" if n else "-"
    print(f"{g:6} {b:6} {o:5} {c['n_markets']:>6} {c['n_closes']:>7} {c['n_netloss']:>6} {n:>5} {fmt(c['median_ndiffs'],0):>6} "
          f"{fmt(c.get('median')):>7} {fmt(c.get('p75')):>7} {fmt(c.get('p90')):>7} {f15:>6} {f20:>6} {fmt(c.get('median_maxmove_sd')):>9}")
print()
print("stress at PIN=0.995 (z recomputed from tape), 31-45 units:")
for (g, k, o), c in stress.items():
    print(f"  {g:6} x{k:<4} {o:5} n={c['n']:>3} still_ok={c['still_ok']:>3} refused_pin={c['refused_pin']:>3} refused_edge={c['refused_edge']:>3} no_z={c['no_z']}")
print()
print("LOSERS at 31-45 s (wrong side OR net pnl<0; 'res' != 'want' means the model missed):")
print(f"{'grp':5} {'ticker':28} {'t(UTC)':20} {'tau':>3} {'want':4} {'price':>5} {'fair':>7} {'sigma':>9} {'realized':>9} {'ratio':>6} {'maxmv_sd':>8} {'nd':>3} {'res':>3} {'pnl_c':>7} {'z_re':>5} {'fair_re':>7} {'settle_z':>8} {'fill':>6} ruler legs")
for l in losers:
    print(f"{l['group']:5} {l['ticker']:28} {l['t']:20} {l['tau']:>3} {l['want']:4} {l['price']:>5} {l['fair']:>7} {l['sigma']:>9} "
          f"{fmt(l['realized'],6):>9} {fmt(l['ratio']):>6} {fmt(l['maxmove_sd']):>8} {l['n_diffs']:>3} {l['result']:>3} {fmt(l['pnl_c'],1):>7} "
          f"{fmt(l['z_re']):>5} {fmt(l['fair_re'],5):>7} {fmt(l['settle_z']):>8} {fmt(l['filled'],1):>6} {l['ruler']} {l['pnl_legs']}")
print()
print("live 3-30 WRONG SIDE (for comparison):")
for (g, tk, bb), u in sorted(units.items(), key=lambda kv: kv[1]["t"]):
    if g == "live" and bb == "3-30" and u["_wrong"]:
        print(f"  {tk:28} {u['t']:20} tau {u['tau']:>2} {u['want']:3} price {u['price']:<5} sigma {u['sigma']:<9} ratio {fmt(u['_ratio']):>5} maxmv {fmt(u['_maxmove_sd']):>6} settle_z {fmt(u['_settle_z']):>6} pnl {fmt(u['_pnl_c'],0):>6} legs {u.get('_pnl_legs')}")
print()
print("units where LOST (net pnl<0) != WRONG SIDE (want != result):")
for (g, tk, bb), u in sorted(units.items(), key=lambda kv: kv[1]["t"]):
    if u["_lost"] != u["_wrong"]:
        print(f"  {g:5} {tk:28} {u['t']:20} tau {u['tau']:>2} {u['want']:3} result {u['_result']} net {fmt(u['_pnl_c'],1)} legs {u.get('_pnl_legs')} ratio {fmt(u['_ratio'])}")
