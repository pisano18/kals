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
        a = out.setdefault((tb, pb), {"n": 0, "lost": 0, "contracts": 0.0,
                                      "cents": 0.0, "closes": set(),
                                      "lost_closes": set()})
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
    for a in out.values():
        a["loss_rate"] = (100.0 * a["lost"] / a["n"]) if a["n"] else None
        a["per_contract"] = (a["cents"] / a["n"]) if a["n"] else None
        # RULE 4: closes are the independent observations, trades are not.
        a["n_closes"] = len(a["closes"])
        a["n_lost_closes"] = len(a["lost_closes"])
        a["close_loss_rate"] = ((100.0 * a["n_lost_closes"] / a["n_closes"])
                                if a["n_closes"] else None)
    return out


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


def walk(files, settled, series=SERIES, on_progress=None):
    rows, bad = [], 0
    needle = '"' + series + "-"
    for i, f in enumerate(files):
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if needle not in line:
                        continue
                    try:
                        m = json.loads(line).get("msg") or {}
                    except ValueError:
                        continue
                    r = scan(m, settled, series=series)
                    if r:
                        rows.append(r)
        except Exception:                                      # noqa: BLE001
            # a torn hour is SKIPPED, never silently treated as an empty one
            bad += 1
        if on_progress and not i % 25:
            on_progress(i, len(files), len(rows))
    return rows, bad


def report(cs, say=print, min_n=30):
    lines = []
    w = lines.append
    w("  OIL (%s) -- EVERY TAKER NEAR A CLOSE, BY PRICE AND CLOCK" % SERIES)
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
    print("oilband selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--series", default=SERIES)
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--rebuild", action="store_true",
                    help="re-walk the tape instead of using the cached trades")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    # THE WALK IS THE EXPENSIVE PART, so it is paid for once. The first run of
    # this file was piped through `tail`, which threw away the header and the
    # two most important rows before they were ever written, and re-reading
    # 221 tape hours to get them back is ten minutes for nothing.
    cache = os.path.join(RESULTS, "oilband_%s.json" % a.series)
    if not a.rebuild and os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            rows = [tuple(r) for r in json.load(fh)["rows"]]
        print("  %d trades from cache (%s)" % (len(rows),
                                               os.path.basename(cache)))
        report(cells(rows), min_n=a.min_n)
        return 0
    settled = load_settlements()
    print("  settlements on file: %d" % len(settled), flush=True)
    files = sorted(glob.glob(os.path.join(a.data, "trade", "*.jsonl.gz")))
    print("  walking %d tape hours for %s..." % (len(files), a.series),
          flush=True)
    rows, bad = walk(files, settled, series=a.series,
                     on_progress=lambda i, n, r: print(
                         "    %d/%d hours, %d trades" % (i, n, r), flush=True))
    if not rows:
        print("oilband: loaded nothing -- no %s trade joined a settlement."
              % a.series)
        return 0
    print("  %d trades, %d unreadable hours skipped" % (len(rows), bad),
          flush=True)
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"series": a.series, "rows": rows, "bad_hours": bad}, fh)
    report(cells(rows), min_n=a.min_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
