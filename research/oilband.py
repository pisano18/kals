"""oilband.py -- where the money in oil actually is, by price and by clock.

WHY THIS EXISTS. The operator, 2026-09-18: *"I want you to do whatever it takes
with oil to get it working right. I know there's something in oil we just
haven't gotten it right."*

What we had before this file was a contradiction nobody had resolved:

  paper, every window   86 markets, ZERO losses, +1.7% to +3.7%
  live, 2-15 s only     17 markets, ONE loss,    -4.4%

and the live window is the one paper has almost no data on -- 1 market of 86.
Meanwhile paper's best-evidenced oil cell (71 markets at 121-180 s) is not
traded live at all. So the live rule was never the rule the evidence supported.

**WHAT THIS MEASURES, AND WHAT IT IS NOT ALLOWED TO CLAIM.** It walks the trade
tape and asks, of every TAKER who bought into a WTI market near its close: what
did they pay, how long was left, and did their side win? That is a large, clean
sample of what the MARKET did.

It is NOT our loss rate and must never be quoted as one (AMENDMENT 2026-09-10,
rule 5). The tape's population is "an offer was sitting there"; ours is
"someone actively sold it to US", and only the second is adversely selected. On
crypto those two differed by 31x. So:

  USE THIS FOR: the SHAPE -- which price and clock cells are better than which
                other cells, measured on thousands of trades instead of 17.
  NEVER FOR:    the level of our own loss rate, or what a rule "would have
                cost us".

WHY OIL IS NOT CRYPTO, which is the whole reason a separate study is needed.
A crypto contract settles on the MEAN of 60 one-second prints, so a late move
is diluted by 59 prints that already happened. A commodity settles on the CLOSE
of a one-minute candle -- a single number. Nothing is diluted. The last second
counts exactly as much as the first, which is why the crypto intuition that
"later is safer" cannot be assumed here and has to be measured.

CRYPTO, SAME STUDY, ONE PASS (2026-09-18). The crypto bot's 3-30 s window is
drying up and the operator needs the same table for 31-45 s and later, on the
nine crypto series. Nine series in one pass over 557 tape hours is ~25 million
near-close trades, which does not fit in memory as rows (~4.6 GB) and must not
be dumped as a raw-row JSON. So a multi-series walk folds every trade into a
PER-CLOSE, PER-CELL aggregate as it goes -- `accumulate()` -- and the cache
holds that instead of rows. `cells_from_agg()` reproduces `cells()` exactly
(the self-test checks it on the planted grid) at the bands in this file; a
different banding needs a re-walk. Old row caches still load.

POOLING ACROSS SERIES keys the close by its EPOCH, not by (series, close): all
the 15-minute crypto series settle on the same quarter hour and at rho ~0.8 are
worth ~1.22 observations per close, not nine (hard rule 4). A pooled cell's
`closes` is therefore the number of quarter-hours, and a quarter-hour counts as
lost if ANY series in that cell lost it.
"""
import argparse
import collections
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DATA = r"C:\kals\kalshi_data"
SETTLE = r"C:\kals\fulltape\markets.json"

SERIES = "KXWTI15M"
CRYPTO = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M")
TAU_MAX = 240            # look this far back from each close
FEE_RATE = 0.07          # takers pay 0.07 * p * (1 - p) per contract

TAU_BANDS = ((0, 15), (16, 30), (31, 45), (46, 60), (61, 90), (91, 120),
             (121, 180), (181, 240))
PX_BANDS = ((0.85, 0.90), (0.90, 0.93), (0.93, 0.95), (0.95, 0.97),
            (0.97, 0.98), (0.98, 0.99), (0.99, 1.00))


def fee(p, n=1.0):
    return FEE_RATE * p * (1.0 - p) * n


def band_of(v, bands):
    for lo, hi in bands:
        if lo <= v <= hi:
            return (lo, hi)
    return None


def scan(msg, settled, series=SERIES, tau_max=TAU_MAX):
    """One tape trade -> (tau, paid, won) for the TAKER, or None.

    Every taker, not only the ones who happened to be right -- measuring only
    the winners is how a study invents an edge that is not there.
    """
    import pinflat
    tk = msg.get("market_ticker")
    if not tk or not tk.startswith(series + "-"):
        return None
    won_yes = settled.get(tk)
    if won_yes is None:
        return None
    close = pinflat.close_epoch(tk)
    if close is None:
        return None
    try:
        ts = int(msg["ts"])
        yes_px = float(msg["yes_price_dollars"])
        n = float(msg.get("count_fp") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    tau = close - ts
    if not (0 <= tau <= tau_max):
        return None
    side = msg.get("taker_side")
    if side not in ("yes", "no"):
        return None
    # A YES ask at p IS a NO ask at 1-p. Decide the unit once, from the field
    # name, never from the magnitude (hard rule 5).
    paid = yes_px if side == "yes" else 1.0 - yes_px
    if not (0.0 < paid < 1.0):
        return None
    won = (side == "yes" and won_yes) or (side == "no" and not won_yes)
    # THE CLOSE COMES BACK TOO, because hard rule 4 is not optional: hundreds
    # of trades share one settlement outcome, so a cell of 1,671 TRADES may be
    # 40 independent observations. Counting trades as evidence is how this
    # project has invented an edge before.
    return tau, paid, bool(won), n, close


def _finish(out):
    for a in out.values():
        a["loss_rate"] = (100.0 * a["lost"] / a["n"]) if a["n"] else None
        a["per_contract"] = (a["cents"] / a["n"]) if a["n"] else None
        # RULE 4: closes are the independent observations, trades are not.
        a["n_closes"] = len(a["closes"])
        a["n_lost_closes"] = len(a["lost_closes"])
        a["close_loss_rate"] = ((100.0 * a["n_lost_closes"] / a["n_closes"])
                                if a["n_closes"] else None)
    return out


def _cell():
    return {"n": 0, "lost": 0, "contracts": 0.0, "cents": 0.0,
            "closes": set(), "lost_closes": set()}


def cells(rows, tau_bands=TAU_BANDS, px_bands=PX_BANDS):
    """{(tau_band, px_band): stats} -- trades, losses, cents per contract."""
    out = {}
    for row in rows:
        tau, paid, won, n = row[0], row[1], row[2], row[3]
        close = row[4] if len(row) > 4 else None
        tb = band_of(tau, tau_bands)
        pb = band_of(paid, px_bands)
        if tb is None or pb is None:
            continue
        a = out.setdefault((tb, pb), _cell())
        a["n"] += 1
        a["contracts"] += n
        if close is not None:
            a["closes"].add(close)
        if won:
            a["cents"] += 100.0 * ((1.0 - paid) - fee(paid))
        else:
            a["lost"] += 1
            a["cents"] += 100.0 * (-paid - fee(paid))
            if close is not None:
                a["lost_closes"].add(close)
    return _finish(out)


def accumulate(agg, row, tau_bands=TAU_BANDS, px_bands=PX_BANDS):
    """Fold one (tau, paid, won, n, close) row into a per-close cell table.

    agg is {(close, tau_band, px_band): [trades, lost, contracts, cents]}.
    It holds exactly what `cells()` needs, per close, so a nine-series walk of
    ~25M trades fits in a few tens of MB instead of ~4.6 GB of row tuples.
    """
    tau, paid, won, n = row[0], row[1], row[2], row[3]
    close = row[4] if len(row) > 4 else None
    tb = band_of(tau, tau_bands)
    pb = band_of(paid, px_bands)
    if tb is None or pb is None:
        return False
    a = agg.setdefault((close, tb, pb), [0, 0, 0.0, 0.0])
    a[0] += 1
    a[2] += n
    if won:
        a[3] += 100.0 * ((1.0 - paid) - fee(paid))
    else:
        a[1] += 1
        a[3] += 100.0 * (-paid - fee(paid))
    return True


def cells_from_agg(agg):
    """The same {(tau_band, px_band): stats} as `cells()`, from an aggregate.

    Several series' aggregates can be merged first (`merge_aggs`); because the
    key is the close EPOCH, a quarter-hour that nine series all traded is ONE
    close in the pooled table, and it is a lost close if any of them lost.
    """
    out = {}
    for (close, tb, pb), (n, lost, contracts, cents) in agg.items():
        a = out.setdefault((tb, pb), _cell())
        a["n"] += n
        a["lost"] += lost
        a["contracts"] += contracts
        a["cents"] += cents
        if close is not None:
            a["closes"].add(close)
            if lost:
                a["lost_closes"].add(close)
    return _finish(out)


def merge_aggs(aggs):
    out = {}
    for agg in aggs:
        for k, v in agg.items():
            a = out.setdefault(k, [0, 0, 0.0, 0.0])
            for i in range(4):
                a[i] += v[i]
    return out


def agg_to_list(agg):
    return [[c, tb[0], tb[1], pb[0], pb[1], v[0], v[1], v[2], v[3]]
            for (c, tb, pb), v in agg.items()]


def agg_from_list(lst):
    return {(r[0], (r[1], r[2]), (r[3], r[4])): [r[5], r[6], r[7], r[8]]
            for r in lst}


def break_even(paid):
    """The loss rate at which buying at `paid` stops making money.

    win = (1 - paid) - fee, loss = paid + fee, so the edge is zero at
    L = win / (win + loss). Stated per cell so a cell is never called "good"
    on its win rate alone -- at 99c a 1-in-100 loss rate is break-even.
    """
    w = (1.0 - paid) - fee(paid)
    l = paid + fee(paid)
    if w <= 0:
        return 0.0
    return 100.0 * w / (w + l)


def load_settlements(path=SETTLE):
    """{ticker: True/False for YES} from every fulltape directory."""
    import pinattrib
    return {k: (v == "yes") for k, v in
            pinattrib.load_outcomes(path).items()}


def _load_checkpoint(path, wanted):
    """Resume state written by `_save_checkpoint`, or None if absent or for a
    different set of series (a checkpoint for the wrong series is worse than
    none: it would be silently summed into a table that names other series)."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    if tuple(d.get("series") or ()) != tuple(wanted):
        return None
    aggs = {s: agg_from_list(d["aggs"][s]) for s in wanted}
    seen = {s: {"trades": d["seen"][s]["trades"],
                "closes": set(d["seen"][s]["closes"])} for s in wanted}
    return aggs, seen, int(d.get("bad", 0)), set(d.get("done") or ())


def _save_checkpoint(path, wanted, aggs, seen, bad, done):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"series": list(wanted), "bad": bad, "done": sorted(done),
                   "aggs": {s: agg_to_list(aggs[s]) for s in wanted},
                   "seen": {s: {"trades": seen[s]["trades"],
                                "closes": sorted(seen[s]["closes"])}
                            for s in wanted}}, fh)
    os.replace(tmp, path)


def walk_many(files, settled, series_list, on_progress=None, rows_out=None,
              checkpoint=None, every=25):
    """ONE pass over the tape for several series at once.

    Returns ({series: agg}, {series: {"trades", "closes"}}, bad_hours). If
    `rows_out` is a dict, the raw rows are also appended per series into it
    (only sane for a thin series such as oil). A torn hour keeps whatever it
    yielded before the tear and is counted in `bad`, never treated as empty.

    `checkpoint` is a path: the state is written there after every `every`
    hours and a later call with the same path and series resumes after the
    last hour it finished, never re-counting one. The first nine-series walk
    was killed at hour 250 of 557 by a low-memory guard with nothing saved.
    """
    wanted = tuple(series_list)
    needles = tuple('"' + s + "-" for s in wanted)
    state = _load_checkpoint(checkpoint, wanted)
    if state:
        aggs, seen, bad, done = state
    else:
        aggs = {s: {} for s in wanted}
        seen = {s: {"trades": 0, "closes": set()} for s in wanted}
        bad, done = 0, set()
    n_rows = 0
    for i, f in enumerate(files):
        if os.path.basename(f) in done:
            continue
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    for nd in needles:
                        if nd in line:
                            break
                    else:
                        continue
                    try:
                        m = json.loads(line).get("msg") or {}
                    except ValueError:
                        continue
                    ser = str(m.get("market_ticker") or "").partition("-")[0]
                    if ser not in aggs:
                        continue
                    r = scan(m, settled, series=ser)
                    if not r:
                        continue
                    n_rows += 1
                    seen[ser]["trades"] += 1
                    seen[ser]["closes"].add(r[4])
                    accumulate(aggs[ser], r)
                    if rows_out is not None:
                        rows_out.setdefault(ser, []).append(r)
        except Exception:                                      # noqa: BLE001
            # a torn hour is SKIPPED, never silently treated as an empty one
            bad += 1
        done.add(os.path.basename(f))
        if checkpoint and not len(done) % every:
            _save_checkpoint(checkpoint, wanted, aggs, seen, bad, done)
        if on_progress and not i % 25:
            on_progress(i, len(files), n_rows)
    for s in seen:
        seen[s]["closes"] = len(seen[s]["closes"])
    return aggs, seen, bad


def walk(files, settled, series=SERIES, on_progress=None):
    """Single-series walk returning raw rows -- the original oil path."""
    rows_out = {}
    _aggs, _seen, bad = walk_many(files, settled, [series],
                                  on_progress=on_progress, rows_out=rows_out)
    return rows_out.get(series, []), bad


def report(cs, say=print, min_n=30, label=None):
    lines = []
    w = lines.append
    w("  %s -- EVERY TAKER NEAR A CLOSE, BY PRICE AND CLOCK"
      % (label or "OIL (%s)" % SERIES))
    w("")
    w("  TAPE POPULATION. This is what the MARKET did, never our loss rate")
    w("  (rule 5): an offer sitting there is not an offer sold to us, and on")
    w("  crypto those two differed by 31x. Read the SHAPE, not the level.")
    w("")
    w("  'break-even' is the loss rate at which that price stops paying, so a")
    w("  cell is never called good on its win rate alone.")
    w("")
    w("  RULE 4: `closes` is the evidence, `trades` is not -- hundreds of")
    w("  trades share one settlement, so a cell of 1,600 trades can be 40")
    w("  independent observations. Cells are filtered on CLOSES.")
    w("")
    w("  %-10s %-12s %7s %7s %6s %8s %10s %10s"
      % ("seconds", "price", "closes", "trades", "lost", "closes lost",
         "break-even", "c/contract"))
    best = []
    for (tb, pb), a in sorted(cs.items()):
        if a["n_closes"] < min_n:
            continue
        be = break_even((pb[0] + pb[1]) / 2.0)
        # JUDGED ON CLOSES, not trades: the close-level loss rate is the one
        # that has to clear break-even, because a close is the observation.
        clr = a["close_loss_rate"]
        good = a["per_contract"] > 0 and clr is not None and clr < be
        flag = "  <-- pays" if good else ""
        w("  %-10s %-12s %7d %7d %6d %10.2f%% %9.2f%% %+9.3f%s"
          % ("%d-%d" % tb, "%.2f-%.2f" % pb, a["n_closes"], a["n"],
             a["n_lost_closes"], clr if clr is not None else -1.0,
             be, a["per_contract"], flag))
        if good:
            best.append(((tb, pb), a))
    w("")
    if best:
        best.sort(key=lambda x: -x[1]["per_contract"])
        w("  BEST CELLS BY MONEY PER CONTRACT")
        for (tb, pb), a in best[:6]:
            w("    %d-%d s at %.2f-%.2f : %+.3f c/contract, %d of %d CLOSES "
              "lost (%.2f%%), %d contracts changed hands"
              % (tb[0], tb[1], pb[0], pb[1], a["per_contract"],
                 a["n_lost_closes"], a["n_closes"], a["close_loss_rate"],
                 a["contracts"]))
    else:
        w("  NO CELL CLEARS ITS OWN BREAK-EVEN at n >= %d." % min_n)
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def cache_path(series):
    return os.path.join(RESULTS, "oilband_%s.json" % series)


def load_cache(path):
    """-> ("rows", rows) for the original row cache, ("agg", agg) for the
    per-close cache, plus the stored metadata."""
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    if "agg" in d:
        return "agg", agg_from_list(d["agg"]), d
    return "rows", [tuple(r) for r in d["rows"]], d


def _write_gz(path, lines):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("oilband selftest: FAILED -- " + msg)

    ck(abs(fee(0.95) - 0.07 * 0.95 * 0.05) < 1e-12,
       "the taker fee is 0.07 * p * (1-p) per contract")
    # BREAK-EVEN: the number that stops a 99% win rate looking like a win.
    ck(abs(break_even(0.99) - 100.0 * ((0.01 - fee(0.99))
                                       / ((0.01 - fee(0.99)) + 0.99 + fee(0.99)))) < 1e-9,
       "break-even at 99c is under 1 in 100 -- buying a near-certainty pays a")
    ck(break_even(0.99) < 1.0 and break_even(0.90) > 8.0,
       "...cent, so it must almost never lose, while 90c can afford to lose "
       "roughly one time in eleven")
    ck(break_even(0.99) < break_even(0.95) < break_even(0.90),
       "the cheaper the price the more losses it can carry")

    # SCAN: a planted winner and a planted loser, both counted.
    s = {"KXWTI15M-26SEP181015-15": True}
    close = __import__("pinflat").close_epoch("KXWTI15M-26SEP181015-15")
    m = {"market_ticker": "KXWTI15M-26SEP181015-15", "ts": close - 10,
         "yes_price_dollars": 0.96, "taker_side": "yes", "count_fp": 5}
    got = scan(m, s)
    ck(got and got[0] == 10 and abs(got[1] - 0.96) < 1e-9 and got[2] is True,
       "a taker who bought YES at 96c ten seconds out, on a market YES won, "
       "is recorded as a winner at 96c")
    m2 = dict(m, taker_side="no")
    got2 = scan(m2, s)
    ck(got2 and abs(got2[1] - 0.04) < 1e-9 and got2[2] is False,
       "the SAME print read from the NO side is a 4c buy that LOST -- the unit "
       "comes from the side, never from the magnitude (hard rule 5)")
    ck(scan(dict(m, ts=close + 5), s) is None,
       "NULL: a print after the close is not a trade into that close")
    ck(scan(dict(m, market_ticker="KXGOLD15M-26SEP181015-15"), s) is None,
       "NULL: another commodity is not oil")
    ck(scan(m, {}) is None,
       "NULL: a market with no settlement on file is skipped, not guessed")

    # CELLS: a planted grid where the answer is known, with the trades spread
    # over a KNOWN number of closes so rule 4 can be checked.
    rows = ([(10, 0.96, True, 1.0, 1000 + i % 50) for i in range(99)]
            + [(10, 0.96, False, 1.0, 1000)]
            + [(100, 0.96, False, 1.0, 2000 + i % 50) for i in range(50)]
            + [(100, 0.96, True, 1.0, 2000 + i % 50) for i in range(50)])
    cs = cells(rows)
    late = cs[((0, 15), (0.95, 0.97))]
    far = cs[((91, 120), (0.95, 0.97))]
    ck(late["n"] == 100 and late["lost"] == 1 and abs(late["loss_rate"] - 1.0) < 1e-9,
       "a cell counts its trades and its losses")
    ck(late["n_closes"] == 50 and late["n_lost_closes"] == 1,
       "RULE 4: a hundred trades over fifty closes is FIFTY observations, and "
       "the cell says so -- counting trades as evidence is how this project "
       "has invented an edge before")
    ck(abs(late["close_loss_rate"] - 2.0) < 1e-9,
       "...so the loss rate that matters is 1 close in 50 (2%), not 1 trade "
       "in 100 (1%) -- clustering makes it look twice as safe as it is")
    ck(late["per_contract"] > 0 and far["per_contract"] < 0,
       "1 loss in 100 at 96c pays; 50 in 100 does not, and the sign says so")
    ck(cells([(10, 0.96, True, 1.0)])[((0, 15), (0.95, 0.97))]["n_closes"] == 0,
       "NULL: a row with no close contributes no observation, rather than "
       "being counted as one")
    txt = report(cs, say=None, min_n=10)
    ck("<-- pays" in txt, "a cell that beats its own break-even is flagged")
    ck("RULE 4" in txt and "closes" in txt,
       "and the table says on its face that closes are the evidence")
    ck("rule 5" in txt and "31x" in txt,
       "and the report carries the warning that this is the TAPE, not our own "
       "loss rate, where the reader will see it")
    ck("NO CELL CLEARS" in report({}, say=None),
       "NULL: nothing measured says so rather than printing an empty table "
       "that reads as 'no edge anywhere'")

    # THE PER-CLOSE AGGREGATE must give the SAME table as the rows do, cell
    # by cell, or the crypto tables are a different study wearing oil's name.
    agg = {}
    for r in rows + [(10, 0.5, True, 1.0, 1000)]:
        accumulate(agg, r)
    ca = cells_from_agg(agg)
    keys = ("n", "lost", "contracts", "cents", "n_closes", "n_lost_closes",
            "per_contract", "close_loss_rate")
    same = (set(ca) == set(cs) and all(
        abs(ca[k][f] - cs[k][f]) < 1e-9 for k in cs for f in keys))
    ck(same, "the per-close aggregate reproduces cells() exactly on the "
             "planted grid -- every count, every cent, every close")
    ck(agg_from_list(json.loads(json.dumps(agg_to_list(agg)))) == agg,
       "...and it survives the round trip through the JSON cache unchanged")
    ck(not accumulate({}, (10, 0.5, True, 1.0, 1000)),
       "NULL: a 50c trade lands in no price band and is not folded in")
    ck(cells_from_agg(merge_aggs([agg, agg]))[((0, 15), (0.95, 0.97))]["n_closes"] == 50,
       "RULE 4 when POOLING: two series on the same fifty quarter-hours are "
       "fifty closes, not a hundred")

    # TWO SERIES IN ONE PASS stay separate: a tiny tape with a BTC winner and
    # an ETH loser at the same close, plus a GOLD print nobody asked for.
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp()
    try:
        c_btc, c_eth, c_gld = ("KXBTC15M-26SEP181015-15",
                               "KXETH15M-26SEP181015-15",
                               "KXGOLD15M-26SEP181015-15")
        settled = {c_btc: True, c_eth: False, c_gld: True}
        base = {"ts": close - 40, "yes_price_dollars": 0.96,
                "taker_side": "yes", "count_fp": 2}
        good = os.path.join(tmp, "a.jsonl.gz")
        _write_gz(good, [{"msg": dict(base, market_ticker=c_btc)},
                         {"msg": dict(base, market_ticker=c_eth)},
                         {"msg": dict(base, market_ticker=c_gld)},
                         {"msg": dict(base, market_ticker=c_btc, ts=close - 5)}])
        torn = os.path.join(tmp, "b.jsonl.gz")
        _write_gz(torn, [{"msg": dict(base, market_ticker=c_eth)}] * 200)
        with open(torn, "rb") as fh:
            blob = fh.read()
        with open(torn, "wb") as fh:
            fh.write(blob[: len(blob) // 2])
        aggs, seen, bad = walk_many([good, torn], settled,
                                    ["KXBTC15M", "KXETH15M"])
        cb = cells_from_agg(aggs["KXBTC15M"])
        ce = cells_from_agg(aggs["KXETH15M"])
        ck(set(aggs) == {"KXBTC15M", "KXETH15M"},
           "one pass collects exactly the series asked for -- GOLD, on the "
           "same tape, is not picked up")
        ck(cb[((31, 45), (0.95, 0.97))]["n"] == 1
           and cb[((31, 45), (0.95, 0.97))]["lost"] == 0
           and cb[((0, 15), (0.95, 0.97))]["n"] == 1,
           "the BTC winner lands in BTC's table, in the right clock cells")
        ck(ce[((31, 45), (0.95, 0.97))]["lost"] == 1
           and ((0, 15), (0.95, 0.97)) not in ce,
           "the ETH loser lands in ETH's table and does not leak into BTC's")
        ck(seen["KXBTC15M"]["trades"] == 2 and seen["KXBTC15M"]["closes"] == 1
           and seen["KXETH15M"]["closes"] == 1,
           "each series counts its own trades and its own closes")
        ck(bad == 1 and ce[((31, 45), (0.95, 0.97))]["n"] >= 1,
           "a torn hour is COUNTED as torn, the good hour's rows survive it, "
           "and the walk does not abort")
        pooled = cells_from_agg(merge_aggs(aggs.values()))
        p = pooled[((31, 45), (0.95, 0.97))]
        ck(p["n_closes"] == 1 and p["n_lost_closes"] == 1,
           "POOLED: BTC won and ETH lost the same quarter-hour, which is ONE "
           "close, and a LOST one (rule 4)")
        rows1, bad1 = walk([good], settled, series="KXBTC15M")
        ck(len(rows1) == 2 and all(r[4] == close for r in rows1) and bad1 == 0,
           "the single-series walk still returns raw rows for that series only")
        # RESUME: a walk that dies after the first hour must pick up at the
        # second, and must not count the first hour twice.
        ckp = os.path.join(tmp, "ckpt.json")
        a1, _s1, b1 = walk_many([good], settled, ["KXBTC15M", "KXETH15M"],
                                checkpoint=ckp, every=1)
        ck(os.path.exists(ckp) and b1 == 0,
           "the state is checkpointed after each `every` hours")
        a2, s2, b2 = walk_many([good, torn], settled, ["KXBTC15M", "KXETH15M"],
                               checkpoint=ckp, every=1)
        ck(a2 == aggs and b2 == bad and s2["KXBTC15M"]["trades"] == 2,
           "resumed from the checkpoint, the finished hour is skipped and the "
           "totals equal a single uninterrupted walk -- nothing counted twice")
        ck(_load_checkpoint(ckp, ["KXBTC15M"]) is None,
           "NULL: a checkpoint for a different series set is ignored, not "
           "summed into the wrong table")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("oilband selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--series", nargs="+", default=[SERIES],
                    help="one or more series; several are walked in ONE pass")
    ap.add_argument("--all-crypto", action="store_true",
                    help="the nine crypto series: " + " ".join(CRYPTO))
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--rebuild", action="store_true",
                    help="re-walk the tape instead of using the cached trades")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    series = list(CRYPTO) if a.all_crypto else list(a.series)
    # THE WALK IS THE EXPENSIVE PART, so it is paid for once. The first run of
    # this file was piped through `tail`, which threw away the header and the
    # two most important rows before they were ever written, and re-reading
    # 221 tape hours to get them back is ten minutes for nothing.
    tables = {}          # series -> cells
    aggs = {}            # series -> per-close aggregate (for pooling)
    todo = []
    for s in series:
        c = cache_path(s)
        if a.rebuild or not os.path.exists(c):
            todo.append(s)
            continue
        kind, data, meta = load_cache(c)
        if kind == "rows":
            print("  %s: %d trades from cache (%s)"
                  % (s, len(data), os.path.basename(c)))
            tables[s] = cells(data)
            agg = {}
            for r in data:
                accumulate(agg, r)
            aggs[s] = agg
        else:
            print("  %s: %d trades over %d closes from cache (%s), %d torn "
                  "hours at walk time"
                  % (s, meta.get("trades", 0), meta.get("closes", 0),
                     os.path.basename(c), meta.get("bad_hours", 0)))
            tables[s] = cells_from_agg(data)
            aggs[s] = data
    if todo:
        settled = load_settlements()
        print("  settlements on file: %d" % len(settled), flush=True)
        files = sorted(glob.glob(os.path.join(a.data, "trade", "*.jsonl.gz")))
        print("  walking %d tape hours for %s..." % (len(files), " ".join(todo)),
              flush=True)
        ckp = os.path.join(RESULTS, "oilband_checkpoint.json")
        if os.path.exists(ckp):
            print("  resuming from %s" % os.path.basename(ckp), flush=True)
        got, seen, bad = walk_many(
            files, settled, todo, checkpoint=ckp,
            on_progress=lambda i, n, r: print(
                "    %d/%d hours, %d trades" % (i, n, r), flush=True))
        print("  %d unreadable hours skipped" % bad, flush=True)
        for s in todo:
            if not seen[s]["trades"]:
                print("oilband: loaded nothing -- no %s trade joined a "
                      "settlement." % s)
                continue
            print("  %s: %d trades over %d closes" % (s, seen[s]["trades"],
                                                      seen[s]["closes"]))
            with open(cache_path(s), "w", encoding="utf-8") as fh:
                json.dump({"series": s, "format": "byclose",
                           "bad_hours": bad, "hours": len(files),
                           "trades": seen[s]["trades"],
                           "closes": seen[s]["closes"],
                           "tau_bands": TAU_BANDS, "px_bands": PX_BANDS,
                           "agg": agg_to_list(got[s])}, fh)
            tables[s] = cells_from_agg(got[s])
            aggs[s] = got[s]
        if os.path.exists(ckp):
            os.remove(ckp)          # the caches now hold everything it held
    if not tables:
        print("oilband: loaded nothing -- no trade joined a settlement.")
        return 0
    for s in series:
        if s not in tables:
            continue
        print()
        report(tables[s], min_n=a.min_n,
               label=None if s == SERIES and len(series) == 1
               else "%s" % s)
    if len(tables) > 1:
        print()
        report(cells_from_agg(merge_aggs(aggs.values())), min_n=a.min_n,
               label="POOLED %d SERIES (%s) -- a quarter-hour is ONE close"
               % (len(tables), " ".join(s for s in series if s in tables)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
