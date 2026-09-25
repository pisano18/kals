"""moneyproj.py -- a 60-day money projection built ONLY from our own record.

WHAT IT ANSWERS. The operator asked (2026-09-25): "the most realistic
progression chart possible of what should be expected with money -- bet size,
made per day, loss potential, bank size -- going up to 2 months".

WHAT IT IS. A resample of our PAST, not a promise. Every input is ours:

  * money per market: Kalshi's ledger (results/kalshi_ledger.json, via
    pinledger.pnl -- payout minus both sides' cost minus fees, a hedged market
    netted to one row). Crypto 15-minute book only (the pin bot).
  * the bet size in force at each market: the live logs' `autosize` records.
  * the order-book depth under our 98c ceiling: the live bot's own `signal`
    records (`ladder`, main leg `full`), i.e. what was on offer at the moment
    it decided to buy.

HOW. A market's dollars are made "per unit of size" through the depth curve,
then replayed at each simulated path's own size:

    winning market:  dollars' = dollars * W(S') / W(S_then)
    losing market:   dollars' = dollars * S'   / S_then      (see LOSSES)

W(S) = mean over the measured ladders of the profit on the first min(S, depth)
contracts under 98c, each paying (1 - price - fee). As the size grows it eats
dearer levels (less profit per contract) and then runs out of book (no more
contracts) -- so this ONE curve carries both the capacity limit and the edge
decay, and both are read from the book we actually faced.

LOSSES scale with the WHOLE size (linear). Reason: a losing market is the one
where someone sells us all we ask for; the partial fills that cap our wins do
not cap our losses. The report prints the measured fill fraction on winners vs
losers so this can be checked, and it is the cautious choice either way.

The rules the bot applies are simulated, not a constant bet:
  size = floor(bank / 11.76), 1..250          (pinrun.size_for_bank; 11.76 =
        (MAX_PER_CLOSE 2 + 1 extra bet) x 0.98 x --bank-brake 4.00)
  re-sized before every close (the bot re-sizes every 5 min while flat)
  -$200 per ET day loss cap, fixed dollars (--loss-cap 200)
  20% drawdown halt -> rest of that day + the next day off, then START
        re-bases the high mark (v-hwm-reset; the pause is an assumption)
  Everything inside a close (early leg, late boost, extra coin, hedges, the
  loss-count brake's pauses) is IN the record already, per unit of size.

Whole ET days are resampled, so a bad day's losses stay together.

Run:  python research/moneyproj.py            (self-test first, then real data)
      python research/moneyproj.py --selftest
"""
import argparse
import bisect
import calendar
import glob
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

PER_SIZE = (2 + 1) * 0.98 * 4.00        # 11.76 dollars of bank per contract of size
SIZE_MAX = 250                          # pinrun AUTO_SIZE_MAX
CEILING = 0.98                          # pinrun PRICE_CEILING
DAY_CAP = 200.0                         # --loss-cap 200, dollars per ET day
DRAWDOWN = 0.20                         # pinrun MAX_DRAWDOWN
CRYPTO = frozenset(["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
                    "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
                    "KXNEAR15M", "KXTON15M"])
_MON = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL",
                                     "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def fee(p):
    return 0.07 * p * (1.0 - p)


def size_for_bank(bank):
    if bank is None or bank <= 0:
        return 1
    return int(max(1, min(SIZE_MAX, int(bank // PER_SIZE))))


# --------------------------------------------------------------- the depth curve
def depth_curve(ladders, smax=SIZE_MAX, halve=False):
    """W[S] for S = 0..smax: mean winning profit (dollars) of the first
    min(S, depth) contracts under the ceiling, cheapest first."""
    W = [0.0] * (smax + 1)
    if not ladders:
        return None
    for lad in ladders:
        lv = sorted((float(p), float(q) * (0.5 if halve else 1.0))
                    for p, q in lad if float(p) <= CEILING + 1e-9 and float(q) > 0)
        cum, got, i, left = 0.0, 0.0, 0, (lv[0][1] if lv else 0.0)
        for S in range(1, smax + 1):
            need = 1.0
            while need > 1e-12 and i < len(lv):
                take = min(need, left)
                p = lv[i][0]
                cum += take * (1.0 - p - fee(p))
                need -= take
                left -= take
                if left <= 1e-12:
                    i += 1
                    left = lv[i][1] if i < len(lv) else 0.0
            W[S] += cum
    n = float(len(ladders))
    return [w / n for w in W]


def obtainable(ladders, S):
    if not ladders:
        return 0.0
    return sum(min(S, sum(float(q) for p, q in lad if float(p) <= CEILING + 1e-9))
               for lad in ladders) / len(ladders)


# --------------------------------------------------------------- loading our record
def et_offset(epoch):
    try:
        from downtime import et_offset as eo
        return eo(float(epoch))
    except Exception:
        return -4 * 3600.0


def close_of_ticker(tk):
    """('YYYY-MM-DD' ET day, 'HHMM' ET, UTC epoch of the close) from the ticker."""
    try:
        s = tk.split("-")[1]
        yy, mon, dd, hh, mm = int(s[0:2]), _MON[s[2:5].upper()], int(s[5:7]), int(s[7:9]), int(s[9:11])
    except (IndexError, KeyError, ValueError, AttributeError):
        return None
    naive = calendar.timegm((2000 + yy, mon, dd, hh, mm, 0))
    epoch = naive - et_offset(naive)          # ET wall clock -> UTC epoch
    return "%04d-%02d-%02d" % (2000 + yy, mon, dd), "%02d%02d" % (hh, mm), epoch


def _ep(t):
    try:
        return calendar.timegm(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def scan_logs(pattern):
    """(size_timeline [(epoch, size)], ladders {ticker: ladder}) from live logs."""
    sizes, ladders = [], {}
    for f in sorted(glob.glob(pattern)):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"autosize"' in line:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    e = _ep(r.get("t"))
                    if r.get("kind") == "autosize" and e and r.get("new"):
                        sizes.append((e, float(r["new"])))
                elif '"signal"' in line and '"full"' in line:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if (r.get("kind") == "signal" and r.get("live") and r.get("leg") == "full"
                            and r.get("ticker") and isinstance(r.get("ladder"), list)
                            and r["ticker"] not in ladders):
                        ladders[r["ticker"]] = [(float(p), float(q)) for p, q in r["ladder"]]
    sizes.sort()
    return sizes, ladders


def size_at(timeline, epoch):
    i = bisect.bisect_right(timeline, (epoch, float("inf"))) - 1
    return timeline[i][1] if i >= 0 else None


def load_record(ledger_path, timeline, first_day, last_day):
    """{day: {'closes': [[(dollars, size_then, contracts, ticker), ...], ...]}}"""
    import pinledger
    with open(ledger_path, encoding="utf-8") as fh:
        rows = json.load(fh)["settlements"]
    mk = {}
    for s in rows.values():
        tk = s.get("ticker") or ""
        if tk.split("-")[0] not in CRYPTO:
            continue
        c = close_of_ticker(tk)
        if not c or not (first_day <= c[0] <= last_day):
            continue
        m = mk.setdefault(tk, {"d": 0.0, "n": 0.0, "c": c})
        m["d"] += pinledger.pnl(s)
        m["n"] = max(m["n"], pinledger.money(s, "yes_count_fp"), pinledger.money(s, "no_count_fp"))
    days, nosize = {}, 0
    for tk, m in mk.items():
        day, hhmm, ep = m["c"]
        S = size_at(timeline, ep - 60)
        if not S:
            nosize += 1
            continue
        days.setdefault(day, {}).setdefault(hhmm, []).append((m["d"], S, m["n"], tk))
    out = {}
    for day in sorted(days):
        out[day] = [days[day][k] for k in sorted(days[day])]
    return out, nosize


def compile_pool(record, W, loss_linear=True, L=None):
    """Each day -> list of closes (Aw, Al): pnl at size S' = Aw*W[S'] + Al*L(S')."""
    pool = []
    for day in sorted(record):
        closes = []
        for mkts in record[day]:
            aw = al = 0.0
            for d, S, n, tk in mkts:
                Si = int(round(S))
                if d >= 0:
                    aw += d / W[Si] if W[Si] > 0 else 0.0
                else:
                    al += d / (Si if loss_linear else L[Si])
            closes.append((aw, al))
        pool.append((day, closes))
    return pool


# --------------------------------------------------------------- the simulator
def simulate(pool, W, bank0, hwm0, ndays=60, paths=5000, seed=1, loss_linear=True, L=None,
             disaster=None, withdraw=None, halt_pause=1, weekday_of=None, pool_weekend=None,
             keep=True):
    """Resample whole days. Returns per-day series (lists over paths).

    disaster = (prob per close, unit loss per contract of size) planted on top.
    withdraw = X: every 7th day's end, anything above X is taken out.
    weekday_of(d) -> True if sim day d is a weekend; pool_weekend[i] same for pool.
    """
    rng = random.Random(seed)
    Lf = (lambda S: S) if loss_linear else (lambda S: L[S])
    Ltab = [Lf(S) for S in range(SIZE_MAX + 1)]
    idx_all = list(range(len(pool)))
    idx_we = [i for i in idx_all if pool_weekend and pool_weekend[i]]
    idx_wd = [i for i in idx_all if pool_weekend and not pool_weekend[i]]
    bank_d = [[0.0] * paths for _ in range(ndays + 1)]
    pnl_d = [[0.0] * paths for _ in range(ndays)]
    size_d = [[0] * paths for _ in range(ndays)]
    halted_by = [0] * (ndays + 1)          # paths that have hit the halt by end of day d
    first_halt = [None] * paths
    withdrawn = [0.0] * paths
    minrel = [1.0] * paths                 # worst bank / high mark seen
    capped_days = 0
    for p in range(paths):
        bank, hwm, off_until = bank0, hwm0, -1
        bank_d[0][p] = bank
        for d in range(ndays):
            if weekday_of is not None and idx_we and idx_wd:
                src = idx_we if weekday_of(d) else idx_wd
                closes = pool[src[rng.randrange(len(src))]][1]
            else:
                closes = pool[rng.randrange(len(pool))][1]
            size_d[d][p] = size_for_bank(bank)
            day = 0.0
            if d > off_until:
                for aw, al in closes:
                    S = size_for_bank(bank)
                    x = aw * W[S] + al * Ltab[S]
                    if disaster and rng.random() < disaster[0]:
                        x -= disaster[1] * S
                    bank += x
                    day += x
                    if bank > hwm:
                        hwm = bank
                    r = bank / hwm if hwm > 0 else 1.0
                    if r < minrel[p]:
                        minrel[p] = r
                    if r <= 1.0 - DRAWDOWN:
                        if first_halt[p] is None:
                            first_halt[p] = d
                        off_until = d + halt_pause
                        hwm = bank                     # START re-bases the mark
                        break
                    if day <= -DAY_CAP:
                        capped_days += 1
                        break
            pnl_d[d][p] = day
            if withdraw is not None and (d + 1) % 7 == 0 and bank > withdraw:
                withdrawn[p] += bank - withdraw
                bank = withdraw
                hwm = bank
            bank_d[d + 1][p] = bank
    for p in range(paths):
        if first_halt[p] is not None:
            for d in range(first_halt[p] + 1, ndays + 1):
                halted_by[d] += 1
    return {"bank": bank_d, "pnl": pnl_d, "size": size_d, "halted_by": halted_by,
            "first_halt": first_halt, "withdrawn": withdrawn, "minrel": minrel,
            "capped_days": capped_days, "paths": paths}


def pct(xs, q):
    s = sorted(xs)
    if not s:
        return None
    k = (len(s) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarise(res, bank0):
    n = res["paths"]
    ndays = len(res["pnl"])
    out = []
    for d in range(ndays):
        b = res["bank"][d + 1]
        pl = res["pnl"][d]
        out.append({
            "day": d + 1,
            "bank": {k: pct(b, q) for k, q in (("p05", .05), ("p10", .10), ("p25", .25), ("p50", .5),
                                              ("p75", .75), ("p90", .90), ("p95", .95))},
            "size_p50": pct(res["size"][d], .5),
            "pnl": {"p05": pct(pl, .05), "p50": pct(pl, .5), "p95": pct(pl, .95),
                    "mean": sum(pl) / n},
            "halted_by": res["halted_by"][d + 1] / float(n),
        })
    final = [res["bank"][ndays][p] + res["withdrawn"][p] for p in range(n)]
    return {
        "days": out,
        "halt_prob": sum(1 for x in res["first_halt"] if x is not None) / float(n),
        "below_start": sum(1 for x in final if x < bank0) / float(n),
        "final_total": {k: pct(final, q) for k, q in (("p05", .05), ("p10", .10), ("p50", .5),
                                                     ("p90", .90), ("p95", .95))},
        "withdrawn_p50": pct(res["withdrawn"], .5),
        "dd15_prob": sum(1 for r in res["minrel"] if r <= 0.85) / float(n),
        "capped_day_rate": res["capped_days"] / float(n * ndays),
    }


# --------------------------------------------------------------- self-test
def selftest():
    ok = [True]

    def ck(c, msg):
        print(("  ok   " if c else "  FAIL ") + msg)
        if not c:
            ok[0] = False

    # 1. the depth curve, planted ladder: 100 contracts at 96c, 50 at 97c, junk at 99c
    lad = [[(0.96, 100.0), (0.97, 50.0), (0.99, 500.0)]]
    W = depth_curve(lad)
    e96, e97 = 1 - .96 - fee(.96), 1 - .97 - fee(.97)
    ck(abs(W[10] - 10 * e96) < 1e-9, "depth curve: 10 contracts all at 96c -> 10 x %.5f" % e96)
    ck(abs(W[120] - (100 * e96 + 20 * e97)) < 1e-9, "depth curve: the 101st contract costs 97c (edge decays)")
    ck(abs(W[250] - (100 * e96 + 50 * e97)) < 1e-9, "depth curve: past 150 the book is empty; the 99c level is never bought")
    ck(abs(depth_curve(lad, halve=True)[250] - (50 * e96 + 25 * e97)) < 1e-9, "supply halved: half of every level")
    ck(size_for_bank(1044.69) == 88 and size_for_bank(1012.04) == 86 and size_for_bank(10 ** 6) == 250
       and size_for_bank(5) == 1, "size rule reproduces the live 88 at $1,044.69 and 86 at $1,012.04; cap 250; floor 1")

    # 2. planted world, capacity binds: every day = 10 closes, each a win of exactly
    #    W(S_then). Above the capacity (S >= 150) each close pays W[150] exactly, so
    #    60 days add 600 x W[150] -- analytic, no randomness.
    rec = {"2026-01-%02d" % (i + 1): [[(W[50], 50.0, 50.0, "x")]] * 10 for i in range(3)}
    pool = compile_pool(rec, W)
    b0 = 150 * PER_SIZE + 1000.0
    r = simulate(pool, W, b0, b0, ndays=60, paths=3, seed=3)
    want = b0 + 600 * W[150]
    ck(all(abs(r["bank"][60][p] - want) < 1e-6 for p in range(3)),
       "capacity world: bank after 60 days = start + 600 x W(150) = %.2f exactly (more bank buys nothing)" % want)

    # 3. below capacity the first close is hand-checkable: bank $588 -> size 50 -> +W(50)
    r = simulate(pool, W, 588.0, 588.0, ndays=1, paths=1, seed=1)
    S = size_for_bank(588.0)
    ck(S == 50, "bank $588 -> size 50")
    exp1, bank = 0.0, 588.0
    for _ in range(10):
        s = size_for_bank(bank)
        bank += W[s]
        exp1 += W[s]
    ck(abs(r["pnl"][0][0] - exp1) < 1e-9, "day 1 by hand: ten closes re-sized before each = %.4f" % exp1)

    # 4. NULL world: nothing planted -> nothing found
    rec0 = {"2026-01-01": [[(0.0, 50.0, 50.0, "x")]] * 10}
    r = simulate(compile_pool(rec0, W), W, 1000.0, 1000.0, ndays=60, paths=200, seed=5)
    s0 = summarise(r, 1000.0)
    ck(all(abs(x - 1000.0) < 1e-9 for x in r["bank"][60]) and s0["halt_prob"] == 0.0,
       "NULL: a world with no edge and no loss stays at $1,000 on every path and never halts")

    # 5. losses scale linearly and the -$200 day cap stops the day
    #    day = 3 closes each losing 50c per contract of size (-$25 at size 50), then a win.
    #    At a $10,000 bank the size is 250, so each loss is -$125: after two the day
    #    is at -$250 <= -$200 and the third loss and the win are never taken.
    recL = {"2026-01-01": [[(-25.0, 50.0, 50.0, "x")]] * 3 + [[(W[50], 50.0, 50.0, "y")]]}
    r = simulate(compile_pool(recL, W), W, 10000.0, 10000.0, ndays=1, paths=1, seed=1)
    ck(abs(r["pnl"][0][0] - (-250.0)) < 1e-6,
       "losses scale with the WHOLE size (-$25 at 50 -> -$125 at 250) and the day stops at the "
       "first close past -$200: -$250 exactly (got %.2f)" % r["pnl"][0][0])

    # 6. the 20% halt: one close losing 25% of the bank halts on day 1, pauses day 2
    recH = {"2026-01-01": [[(-0.25 * PER_SIZE * 50, 50.0, 50.0, "x")]] + [[(W[50], 50.0, 50.0, "y")]]}
    r = simulate(compile_pool(recH, W), W, 1000.0, 1000.0, ndays=3, paths=1, seed=1)
    ck(r["first_halt"][0] == 0 and r["pnl"][1][0] == 0.0 and r["pnl"][2][0] != 0.0,
       "a 25%-of-bank close halts day 1, day 2 is off, trading resumes day 3")

    # 7. resampling is unbiased: two days above capacity (+10 x W150 and -$30 flat
    #    per unit) -> mean day-1 P&L = average of the two, within 4 standard errors
    recR = {"2026-01-01": [[(W[50], 50.0, 50.0, "a")]] * 10,
            "2026-01-02": [[(-0.3 * 50, 50.0, 50.0, "b")]]}
    b = 200 * PER_SIZE + 1
    r = simulate(compile_pool(recR, W), W, b, b, ndays=1, paths=4000, seed=9)
    m = sum(r["pnl"][0]) / 4000.0
    exp = 0.5 * (10 * W[150]) + 0.5 * (-0.3 * 200)
    se = abs(10 * W[150] + 0.3 * 200) / 2 / math.sqrt(4000)
    ck(abs(m - exp) < 4 * se, "resampling: mean day-1 %.2f vs planted %.2f (4 SE = %.2f)" % (m, exp, 4 * se))

    # 8. withdrawals: above capacity, keep $2,000: every 7th day the excess leaves
    r = simulate(pool, W, 2000.0, 2000.0, ndays=14, paths=1, seed=1, withdraw=2000.0)
    ck(abs(r["bank"][7][0] - 2000.0) < 1e-9 and r["withdrawn"][0] > 0,
       "withdraw-above-$2,000: bank back to $2,000 on day 7, the rest counted as taken home")

    # 9. disaster planted with prob 1 on every close: -2 per contract of size, linear
    rd = simulate(compile_pool(rec0, W), W, 1000.0, 1000.0, ndays=1, paths=1, seed=1, disaster=(1.0, 0.01))
    ck(abs(rd["pnl"][0][0] - (-0.01 * 85 - 0.01 * size_for_bank(1000 - 0.85) * 9)) < 0.2 and rd["pnl"][0][0] < 0,
       "planted disaster fires on every close at 1c per contract of size: %.2f" % rd["pnl"][0][0])
    rn = simulate(compile_pool(rec0, W), W, 1000.0, 1000.0, ndays=5, paths=50, seed=1, disaster=(0.0, 5.0))
    ck(all(x == 1000.0 for x in rn["bank"][5]), "NULL: a disaster with zero chance never fires")

    print("moneyproj selftest: %s" % ("OK" if ok[0] else "FAILED"))
    return ok[0]


# --------------------------------------------------------------- real data
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--paths", type=int, default=5000)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--first", default="2026-09-13")
    ap.add_argument("--last", default="2026-09-24")
    ap.add_argument("--bank", type=float, required=False)
    ap.add_argument("--hwm", type=float, required=False)
    ap.add_argument("--start-day", default="2026-09-26", help="ET date of simulated day 1")
    ap.add_argument("--ladders-since", default="2026-09-18")
    ap.add_argument("--out-json", default=os.path.join(RESULTS, "projection_2026-09-25.json"))
    ap.add_argument("--dump", default=None, help="write the compiled inputs here (scratch)")
    a = ap.parse_args()
    if not selftest():
        sys.exit(1)
    if a.selftest:
        return
    t0 = time.time()
    timeline, ladders = scan_logs(os.path.join(RESULTS, "pinrun-live-*.jsonl"))
    rec, nosize = load_record(os.path.join(RESULTS, "kalshi_ledger.json"), timeline, a.first, a.last)
    if not rec:
        print("loaded nothing -- no ledger markets in %s..%s" % (a.first, a.last))
        sys.exit(2)
    # ladders from the recent window only (supply changed 09-16..22)
    since_ep = calendar.timegm(time.strptime(a.ladders_since, "%Y-%m-%d"))
    lad_all = {}
    for tk, lad in ladders.items():
        c = close_of_ticker(tk)
        if c and c[2] >= since_ep and tk.split("-")[0] in CRYPTO:
            lad_all[tk] = lad
    # outcome of each laddered market from the ledger
    outcome = {}
    for day in rec:
        for mk in rec[day]:
            for d, S, n, tk in mk:
                outcome[tk] = (d, S, n)
    lads = list(lad_all.values())
    lads_win = [lad_all[t] for t in lad_all if t in outcome and outcome[t][0] >= 0]
    lads_loss = [lad_all[t] for t in lad_all if t in outcome and outcome[t][0] < 0]
    W = depth_curve(lads)
    Wh = depth_curve(lads, halve=True)
    Lloss = depth_curve(lads_loss) if len(lads_loss) >= 5 else None
    fills_w = sorted(n / S for day in rec for mk in rec[day] for d, S, n, tk in mk if d >= 0 and S)
    fills_l = sorted(n / S for day in rec for mk in rec[day] for d, S, n, tk in mk if d < 0 and S)
    json.dump({"W": W, "Wh": Wh, "n_ladders": len(lads), "n_loss_ladders": len(lads_loss),
               "fills_w": fills_w, "fills_l": fills_l,
               "record": rec}, open(a.dump, "w")) if a.dump else None
    print("inputs: %d ET days, %d markets, %d closes; %d markets had no size (dropped); "
          "%d ladders (%d on losing markets); loaded in %.1fs" % (
              len(rec), sum(len(m) for d in rec for m in rec[d]), sum(len(rec[d]) for d in rec),
              nosize, len(lads), len(lads_loss), time.time() - t0))
    print("fill fraction (contracts / size): winners median %.2f (n=%d), losers median %.2f (n=%d)" % (
        pct(fills_w, .5) or 0, len(fills_w), pct(fills_l, .5) or 0, len(fills_l)))
    for S in (20, 50, 88, 127, 150, 212, 250):
        print("  S=%3d  W=%.3f  W/S=%.4f  obtainable=%.1f  halved W=%.3f" % (
            S, W[S], W[S] / S, obtainable(lads, S), Wh[S]))
    if a.dump:
        print("dumped inputs to", a.dump)
    bank0 = a.bank
    hwm0 = a.hwm if a.hwm else bank0
    if bank0 is None:
        print("no --bank given; stopping after the inputs")
        return

    full_pool = compile_pool(rec, W)
    last7 = {d: rec[d] for d in rec if d >= "2026-09-18"}
    l7_pool = compile_pool(last7, W)
    nobug = {d: rec[d] for d in last7 if d != "2026-09-19"}
    nb_pool = compile_pool(nobug, W)
    n_closes = sum(len(rec[d]) for d in rec)
    worst_unit = min(sum(m[0] / m[1] for m in mk) for d in rec for mk in rec[d])
    disaster = (1.0 / n_closes, 2.0 * abs(worst_unit))
    start = calendar.timegm(time.strptime(a.start_day, "%Y-%m-%d"))

    def date_of(d):
        return time.strftime("%a %m-%d", time.gmtime(start + 86400 * d))

    def is_weekend(d):
        return time.gmtime(start + 86400 * d).tm_wday >= 5

    def pool_we(pool):
        return [time.strptime(day, "%Y-%m-%d").tm_wday >= 5 for day, _ in pool]

    # hand check of day 1 at today's size, no intra-day re-size
    S0 = size_for_bank(bank0)
    hand = {}
    for name, pool in (("last7", l7_pool), ("full", full_pool)):
        tots = [sum(aw * W[S0] + al * S0 for aw, al in closes) for _, closes in pool]
        hand[name] = {"per_day": dict(zip([d for d, _ in pool], tots)), "mean": sum(tots) / len(tots)}

    runs = [
        ("last7", "Last 7 days (09-18..09-24) -- HEADLINE", dict(pool=l7_pool)),
        ("full", "Full record (09-13..09-24)", dict(pool=full_pool)),
        ("supply_half", "Last 7 days, cheap offers halve again", dict(pool=l7_pool, W=Wh)),
        ("disaster", "Last 7 days + planted disaster (2x worst close, 1 in %d closes)" % n_closes,
         dict(pool=l7_pool, disaster=disaster)),
        ("full_weekday", "Full record, weekends drawn only from weekends",
         dict(pool=full_pool, weekday_of=is_weekend, pool_weekend=pool_we(full_pool))),
        ("no_bugday", "Last 7 days without the 09-19 bug day", dict(pool=nb_pool)),
        ("keep1000", "Headline, withdraw weekly above $1,000", dict(pool=l7_pool, withdraw=1000.0)),
        ("keep1500", "Headline, withdraw weekly above $1,500", dict(pool=l7_pool, withdraw=1500.0)),
        ("keep2500", "Headline, withdraw weekly above $2,500", dict(pool=l7_pool, withdraw=2500.0)),
        ("full_keep1500", "Full record, withdraw weekly above $1,500", dict(pool=full_pool, withdraw=1500.0)),
    ]
    out = {"written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "bank0": bank0, "hwm0": hwm0, "size0": S0, "start_day_et": a.start_day,
           "paths": a.paths, "days": a.days,
           "inputs": {"record_days": sorted(rec), "markets": sum(len(m) for d in rec for m in rec[d]),
                      "closes": n_closes, "ladders": len(lads), "loss_ladders": len(lads_loss),
                      "W": {str(S): W[S] for S in (1, 20, 50, 88, 100, 127, 150, 200, 212, 250)},
                      "W_halved": {str(S): Wh[S] for S in (1, 20, 50, 88, 100, 127, 150, 200, 212, 250)},
                      "obtainable": {str(S): obtainable(lads, S) for S in (20, 50, 88, 127, 150, 212, 250)},
                      "fill_frac_winners_median": pct(fills_w, .5), "fill_frac_losers_median": pct(fills_l, .5),
                      "worst_close_per_size": worst_unit, "disaster": disaster,
                      "day_totals": {d: sum(m[0] for mk in rec[d] for m in mk) for d in rec},
                      "day_sizes": {d: sum(m[1] for mk in rec[d] for m in mk) / max(1, sum(len(mk) for mk in rec[d])) for d in rec},
                      "rules": {"per_size": PER_SIZE, "size_max": SIZE_MAX, "day_cap": DAY_CAP,
                                "drawdown": DRAWDOWN, "halt_pause_days": 1, "loss_scaling": "linear"}},
           "hand_day1": hand, "scenarios": {}}
    for key, label, kw in runs:
        t1 = time.time()
        pool = kw.pop("pool")
        Wk = kw.pop("W", W)
        res = simulate(pool, Wk, bank0, hwm0, ndays=a.days, paths=a.paths, seed=20260925, **kw)
        sm = summarise(res, bank0)
        sm["label"] = label
        for dd in sm["days"]:
            dd["date"] = date_of(dd["day"] - 1)
        out["scenarios"][key] = sm
        d = sm["days"]
        print("%-14s %5.1fs  day7 %7.0f  day14 %7.0f  day30 %7.0f  day60 %7.0f [p10 %7.0f p90 %7.0f]  "
              "halt %.2f  below-start %.2f  mean$/day d1 %.1f d60 %.1f" % (
                  key, time.time() - t1, d[6]["bank"]["p50"], d[13]["bank"]["p50"], d[29]["bank"]["p50"],
                  d[-1]["bank"]["p50"], d[-1]["bank"]["p10"], d[-1]["bank"]["p90"], sm["halt_prob"],
                  sm["below_start"], d[0]["pnl"]["mean"], d[-1]["pnl"]["mean"]))
        sys.stdout.flush()
    with open(a.out_json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", a.out_json)
    print("hand day-1 at size %d: last7 mean %.2f, full mean %.2f; sim day-1 mean last7 %.2f, full %.2f" % (
        S0, hand["last7"]["mean"], hand["full"]["mean"],
        out["scenarios"]["last7"]["days"][0]["pnl"]["mean"], out["scenarios"]["full"]["days"][0]["pnl"]["mean"]))


if __name__ == "__main__":
    main()
