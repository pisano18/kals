#!/usr/bin/env python3
"""racemaker.py -- what the OTHER side of every Coin Race trade earned.

THE QUESTION. Every strategy this project has tried on the Coin Race buys:
name the leader, pay the ask, hope. `racebook.py` has just shown why that is
hard -- in the last minute the five YES asks sum to a median $1.16 when the
basket is worth exactly $1.00, while the five bids sum to $1.00. The spread on
this product is almost entirely on the ASK side. Whoever is resting those
offers is being paid the whole of it.

So: stop asking what a taker earns and measure what the MAKER earns. For every
trade on the tape, the maker's position is the mirror of the taker's, and the
outcome is settled, so the maker's profit is arithmetic:

    taker bought YES at p  ->  maker is short YES  ->  maker earns  p - 1{won}
    taker bought NO  at 1-p ->  maker is long  YES ->  maker earns  1{won} - p

and MAKERS PAY NO FEE on this series (fee_type quadratic, multiplier 1,
checked against /series 2026-09-11), so that is the whole of it.

This is a census, not a strategy. It says how much money crosses to the
passive side of this book per day and which parts of it are profitable -- the
size of the prize before any question of whether we could win the queue.

WHAT IT IS NOT. It is not our fill rate and it is not our loss rate. We would
be one maker among several, we would be at the back of a queue we did not
join early, and the standing rule is absolute: a loss rate about US comes from
our own fills and from nothing else. Every number here is what the MARKET did.

THE WINNER COMES FROM THE INDEX, not from a settlement file -- the index
reproduces Kalshi's own `result` 761 of 761 (pinracemodel), it is the
preferred source under the standing order index > tape > our fills > replay,
and it is current to the last hour the collector wrote. The agreement with
the settlement file is printed, and a disagreement is a stop.

    python research/racemaker.py --selftest
    python research/racemaker.py --hours 72
    python research/racemaker.py --gate          # add the model gate (slow)
"""
import argparse
import collections
import glob
import gzip
import json
import math
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

import racebook                                                # noqa: E402

COINS = racebook.COINS
SERIES = racebook.SERIES
WINDOW = racebook.WINDOW
DATA = racebook.DATA
BANDS = ((1, 15), (16, 30), (31, 60), (61, 180), (181, 900))


# ------------------------------------------------------------- the maths
def maker_pnl(taker_side, yes_price, won):
    """Dollars the MAKER earned on one contract of this trade.

    The maker is always the mirror of the taker. No fee: makers pay none on
    this series. `won` is whether this leg settled YES."""
    if taker_side == "yes":
        return yes_price - (1.0 if won else 0.0)
    if taker_side == "no":
        return (1.0 if won else 0.0) - yes_price
    return None


# --------------------------------------------------------------- the tape
def _trade_fields(line):
    """(rx_ms, ts_ms, stamp, coin, yes_price, count, taker_side) or None."""
    tick = racebook._grab(line, "market_ticker")
    if not tick or not tick.startswith(SERIES + "-"):
        return None
    stamp, _, coin = tick[len(SERIES) + 1:].rpartition("-")
    if coin not in COINS or not stamp:
        return None
    side = racebook._grab(line, "taker_side")
    if side not in ("yes", "no"):
        return None
    try:
        yp = float(racebook._grab(line, "yes_price_dollars"))
        cnt = float(racebook._grab(line, "count_fp"))
        ts_ms = int(racebook._grab(line, "ts_ms"))
        rx_ms = int(racebook._grab(line, "_rx_ms"))
    except (TypeError, ValueError):
        return None
    if not (0.0 < yp < 1.0) or cnt <= 0:
        return None
    return (rx_ms, ts_ms, stamp, coin, yp, cnt, side)


def read_trades(files, stats=None):
    out = []
    for fp in files:
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if "CRYPTOLEAD" not in line or '"trade"' not in line:
                        continue
                    if stats is not None:
                        stats[0] += 1
                    r = _trade_fields(line)
                    if r is not None:
                        out.append(r)
                        if stats is not None:
                            stats[1] += 1
        except (EOFError, zlib.error, OSError):
            pass
    return out


# ------------------------------------------------------- winners, from index
def winners_from_index(idx, closes, M):
    """{close: winning coin} recomputed from the 1/sec settlement index."""
    out = {}
    for c in closes:
        rets = M.returns_at(idx, c, 0)
        if len(rets) < len(COINS):
            continue
        out[c] = max(rets, key=rets.get)
    return out


# ------------------------------------------------------------- reporting
def summarise(rows, label, out=None):
    """rows: [(pnl_per_contract, count, yes_price, taker_side, won)]"""
    if not rows:
        return None
    contracts = sum(r[1] for r in rows)
    dollars = sum(r[0] * r[1] for r in rows)
    notional = sum(r[2] * r[1] for r in rows)
    line = ("  %-26s %7d trades %10.0f contracts  $%9.2f  %+6.2fc/contract"
            % (label, len(rows), contracts, dollars,
               100.0 * dollars / contracts if contracts else 0.0))
    print(line)
    if out is not None:
        out.append((label, len(rows), contracts, dollars, notional))
    return dollars


# -------------------------------------------------------------- self-test
def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # --- the mirror -------------------------------------------------------
    ck(abs(maker_pnl("yes", 0.04, False) - 0.04) < 1e-12,
       "a taker buys a 4c leg that loses: the maker keeps the whole 4c")
    ck(abs(maker_pnl("yes", 0.04, True) - (-0.96)) < 1e-12,
       "and if that 4c leg WINS the maker is down 96c -- 24 sales to make it back")
    ck(abs(maker_pnl("no", 0.96, True) - 0.04) < 1e-12,
       "a taker buys the 4c NO side (96c yes) on a winner: maker keeps 4c")
    ck(abs(maker_pnl("no", 0.96, False) - (-0.96)) < 1e-12,
       "and loses 96c when it does not win")
    ck(maker_pnl("both", 0.5, True) is None, "an unknown taker side is refused")
    for p in (0.01, 0.37, 0.99):
        for w in (True, False):
            ck(abs(maker_pnl("yes", p, w) + maker_pnl("no", p, w)) < 1e-12,
               "maker P&L is exactly antisymmetric in the taker's side at %.2f/%s"
               % (p, w))
            break
        break
    # the census must sum to zero against the taker
    tot = 0.0
    for p, side, won in ((0.9, "yes", True), (0.9, "yes", False),
                         (0.1, "no", True), (0.55, "no", False)):
        taker = (1.0 if won else 0.0) - p if side == "yes" else p - (1.0 if won else 0.0)
        tot += maker_pnl(side, p, won) + taker
    ck(abs(tot) < 1e-12,
       "ZERO SUM: maker and taker P&L cancel on every trade, before fees")

    # --- the parser -------------------------------------------------------
    real = ('{"type":"trade","sid":5,"seq":674041,"msg":{"trade_id":"0723cb08",'
            '"market_ticker":"KXCRYPTOLEAD15M-26SEP210115-HYPE",'
            '"yes_price_dollars":"0.1400","no_price_dollars":"0.8600",'
            '"count_fp":"82.12","taker_side":"no","taker_outcome_side":"no",'
            '"taker_book_side":"ask","is_block_trade":false,"ts":1789966900,'
            '"ts_ms":1789966900609},"_rx_ms":1789966900631}')
    r = _trade_fields(real)
    ck(r == (1789966900631, 1789966900609, "26SEP210115", "HYPE", 0.14, 82.12, "no"),
       "A TRADE LINE COPIED OFF THE TAPE parses to its true values, fractional "
       "size and all")
    ck(_trade_fields(real.replace("CRYPTOLEAD15M", "BTC15M")) is None,
       "an up/down trade is skipped")
    ck(_trade_fields(real.replace('"count_fp":"82.12"', '"count_fp":"0.00"')) is None,
       "a zero-size print is refused rather than counted as a trade")

    # --- end to end on a planted tape -------------------------------------
    stamp = "26SEP210100"
    close = racebook.close_of(stamp)
    tmp = os.path.join(REPO, "flow_cache", "_racemaker_selftest")
    os.makedirs(tmp, exist_ok=True)
    fp = os.path.join(tmp, "20260921T05.jsonl.gz")

    def tl(sec, coin, yp, cnt, side):
        return ('{"type":"trade","msg":{"market_ticker":"%s-%s-%s",'
                '"yes_price_dollars":"%.4f","count_fp":"%.2f","taker_side":"%s",'
                '"ts_ms":%d},"_rx_ms":%d}\n'
                % (SERIES, stamp, coin, yp, cnt, side, sec * 1000, sec * 1000))
    try:
        with gzip.open(fp, "wt") as fh:
            # ten takers buy a dead leg at 5c; one buys the winner at 90c
            for k in range(10):
                fh.write(tl(close - 30 + k, "XRP", 0.05, 10, "yes"))
            fh.write(tl(close - 20, "BTC", 0.90, 10, "yes"))
            fh.write('{"type":"trade","msg":{"market_ticker":"KXBTC15M-X-T1",'
                     '"yes_price_dollars":"0.5","count_fp":"1","taker_side":"yes",'
                     '"ts_ms":1,"_rx_ms":1}}\n')
        tr = read_trades([fp])
        ck(len(tr) == 11, "11 race trades read out of a file holding 12 (%d)" % len(tr))
        won = {close: "BTC"}
        rows = []
        for _rx, ts_ms, st, coin, yp, cnt, side in tr:
            c = racebook.close_of(st)
            rows.append((maker_pnl(side, yp, coin == won[c]), cnt, yp, side,
                         coin == won[c]))
        total = sum(r[0] * r[1] for r in rows)
        # 100 contracts of a dead 5c leg = +$5.00 ; 10 of the 90c winner = -$1.00
        ck(abs(total - (5.00 - 1.00)) < 1e-9,
           "PLANTED: maker sells 100 dead contracts at 5c (+$5.00) and 10 winning "
           "ones at 90c (-$1.00) -> %+.2f" % total)
        ck(abs(sum(r[0] * r[1] for r in rows if r[4]) + 1.00) < 1e-9,
           "and the whole loss is on the one leg that won")
        # NULL: if the SAME flow lands on a leg that wins, the maker is crushed
        rows2 = [(maker_pnl(r[3], r[2], True), r[1], r[2], r[3], True) for r in rows]
        ck(sum(r[0] * r[1] for r in rows2) < -90,
           "NULL CHECK: had the 5c leg won, the same flow loses $%.2f -- the "
           "estimator is not blind to the tail"
           % -sum(r[0] * r[1] for r in rows2))
    finally:
        try:
            os.remove(fp)
            os.rmdir(tmp)
        except OSError:
            pass

    if not racebook.selftest():
        ck(False, "racebook (the shared parser) self-test")
    print("racemaker selftest:", "OK" if ok else "FAILED")
    return ok


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--hours", type=int, default=0)
    ap.add_argument("--gate", action="store_true",
                    help="also report the subset our own model would have quoted")
    ap.add_argument("--ruler", default="3600",
                    help="covariance window pinracefair chose on its fit half")
    ap.add_argument("--kappa", type=float, default=1.0,
                    help="fat-tail factor pinracefair chose on its fit half")
    ap.add_argument("--lag", type=int, default=0,
                    help="stale the forecast by N seconds -- the look-ahead control")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if not selftest():
        return 1
    if a.selftest:
        return 0

    files = sorted(glob.glob(os.path.join(a.data, "trade", "*.jsonl.gz")))
    if a.hours:
        files = files[-a.hours:]
    if not files:
        print("loaded nothing -- no trade files under %s" % a.data)
        return 0
    print("\nreading %d hourly trade files (%s .. %s)"
          % (len(files), os.path.basename(files[0]), os.path.basename(files[-1])))
    stats = [0, 0]
    trades = read_trades(files, stats=stats)
    print("  %d candidate race lines, %d parsed (%.1f%%)"
          % (stats[0], stats[1], 100.0 * stats[1] / stats[0] if stats[0] else 0.0))
    if stats[0] and stats[1] < 0.95 * stats[0]:
        print("REFUSING TO REPORT -- the trade wire format no longer matches "
              "the parser.")
        return 1
    if not trades:
        print("loaded nothing -- no CRYPTOLEAD trades on disk")
        return 0

    import idxload
    import pinracemodel as M
    closes = {}
    for _rx, _ts, stamp, _coin, _yp, _c, _s in trades:
        c = racebook.close_of(stamp)
        if c is not None:
            closes[stamp] = c
    print("  %d trades across %d races" % (len(trades), len(closes)))

    idx = idxload.load(sorted(set(M.COINS.values())), verbose=False)
    if not idx or idx.get("BRTI") is None:
        print("loaded nothing -- no index on disk")
        return 0
    won = winners_from_index(idx, sorted(set(closes.values())), M)
    print("  %d of %d races have a winner recomputable from the index"
          % (len(won), len(closes)))
    if len(won) < 30:
        print("loaded nothing -- too few races with index coverage")
        return 0

    # the index must agree with Kalshi's own settlement where we have it
    tpath = os.path.join(REPO, "results", "race_truth.json")
    if os.path.exists(tpath):
        truth = json.load(open(tpath, encoding="utf-8"))
        agree = tot = 0
        for stamp, legs in truth.items():
            c = racebook.close_of(stamp)
            if c not in won:
                continue
            w = [k for k, v in legs.items() if v == "yes"]
            if len(w) != 1:
                continue
            tot += 1
            agree += (w[0] == won[c])
        print("  index vs Kalshi's own settled result: %d of %d agree" % (agree, tot))
        if tot >= 30 and agree < tot:
            print("STOPPING -- the index and the settlement file disagree on %d "
                  "races. Nothing below can be trusted until that is explained."
                  % (tot - agree))
            return 1

    # ------------------------------------------------------------------
    rows = []
    for _rx, ts_ms, stamp, coin, yp, cnt, side in trades:
        c = closes.get(stamp)
        if c is None or c not in won:
            continue
        tau = c - ts_ms // 1000
        if tau < 0 or tau > WINDOW:
            continue
        w = (coin == won[c])
        rows.append((maker_pnl(side, yp, w), cnt, yp, side, w, tau, coin, c))
    if not rows:
        print("loaded nothing -- no trades inside a race window")
        return 0
    span = (max(r[7] for r in rows) - min(r[7] for r in rows)) / 86400.0
    span = max(span, 1e-9)
    nraces = len({r[7] for r in rows})

    print("\n## WHAT THE PASSIVE SIDE OF THIS BOOK EARNED")
    print("%.1f days, %d races with trades. Makers pay no fee, so this is net."
          % (span, nraces))
    print("  %-26s %7s %8s %10s   %s"
          % ("", "trades", "", "contracts", "dollars     per contract"))
    tot = summarise([(r[0], r[1], r[2], r[3], r[4]) for r in rows], "EVERY trade")
    print("     = $%.2f per day, $%.2f per race" % (tot / span, tot / nraces))

    print("\n## BY TIME TO CLOSE -- where in the window the money is")
    for lo, hi in BANDS:
        sel = [(r[0], r[1], r[2], r[3], r[4]) for r in rows if lo <= r[5] <= hi]
        summarise(sel, "tau %d-%ds" % (lo, hi))

    print("\n## BY WHAT THE TAKER DID  (the maker is the mirror)")
    for side, lab in (("yes", "taker BOUGHT yes  (maker sold)"),
                      ("no", "taker BOUGHT no   (maker bought yes)")):
        sel = [(r[0], r[1], r[2], r[3], r[4]) for r in rows if r[3] == side]
        summarise(sel, lab)

    print("\n## SELLING YES, BY THE PRICE THE MAKER SOLD AT   (tau <= 60s)")
    print("This is the lottery-ticket business: someone pays a few cents for a")
    print("leg that is already beaten. Sold at Xc, it is worth 0 unless it wins.")
    print("  %-26s %7s %10s %12s %8s" % ("price sold", "trades", "contracts",
                                         "dollars", "won"))
    buckets = ((0.005, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.25),
               (0.25, 0.50), (0.50, 0.75), (0.75, 0.90), (0.90, 1.0))
    for lo, hi in buckets:
        sel = [r for r in rows if r[3] == "yes" and r[5] <= 60 and lo <= r[2] < hi]
        if not sel:
            continue
        cts = sum(r[1] for r in sel)
        d = sum(r[0] * r[1] for r in sel)
        wc = sum(r[1] for r in sel if r[4])
        print("  %-26s %7d %10.0f %12.2f %7.0f (%.2f%%)"
              % ("%.0f-%.0fc" % (100 * lo, 100 * hi), len(sel), cts, d, wc,
                 100.0 * wc / cts if cts else 0))
    print("  A sale at Xc breaks even if the leg wins X%% of the time. Compare")
    print("  the last column to the price bucket: that is the whole trade.")

    print("\n## BUYING YES, BY THE PRICE THE MAKER PAID   (tau <= 60s)")
    print("  %-26s %7s %10s %12s %8s" % ("price paid", "trades", "contracts",
                                         "dollars", "won"))
    for lo, hi in buckets:
        sel = [r for r in rows if r[3] == "no" and r[5] <= 60 and lo <= r[2] < hi]
        if not sel:
            continue
        cts = sum(r[1] for r in sel)
        d = sum(r[0] * r[1] for r in sel)
        wc = sum(r[1] for r in sel if r[4])
        print("  %-26s %7d %10.0f %12.2f %7.0f (%.2f%%)"
              % ("%.0f-%.0fc" % (100 * lo, 100 * hi), len(sel), cts, d, wc,
                 100.0 * wc / cts if cts else 0))

    print("\n## THE TRADE WE ACTUALLY DO, ON SEVEN DAYS OF TAPE")
    print("The live race arm crosses the spread to BUY the leader's YES inside")
    print("tau 30 at 90c or better. Here is what every taker who did that got,")
    print("with no model gate at all -- the floor our forecast has to beat.")
    print("Taker gross is the mirror of the maker; the taker also pays")
    print("0.07*p*(1-p), which is charged here and never left out.")
    print("  %-14s %-10s %8s %10s %8s %9s %9s %9s"
          % ("tau", "price", "trades", "contracts", "won", "gross", "fee", "NET"))
    for tlo, thi in ((1, 15), (16, 30), (31, 60), (1, 30), (1, 60)):
        for plo, phi in ((0.85, 0.90), (0.90, 0.93), (0.93, 0.95), (0.95, 0.97),
                         (0.97, 0.99), (0.90, 0.98)):
            sel = [r for r in rows if r[3] == "yes" and tlo <= r[5] <= thi
                   and plo <= r[2] < phi]
            if not sel:
                continue
            cts = sum(r[1] for r in sel)
            gross = -sum(r[0] * r[1] for r in sel)     # taker = -maker
            fees = sum(racebook.order_fee(r[1], r[2]) for r in sel)
            wc = sum(r[1] for r in sel if r[4])
            print("  %-14s %-10s %8d %10.0f %7.1f%% %+8.2fc %8.2fc %+8.2fc"
                  % ("%d-%ds" % (tlo, thi), "%.0f-%.0fc" % (100 * plo, 100 * phi),
                     len(sel), cts, 100.0 * wc / cts if cts else 0,
                     100 * gross / cts if cts else 0,
                     100 * fees / cts if cts else 0,
                     100 * (gross - fees) / cts if cts else 0))
        print("  %s" % ("-" * 84))

    print("\n## PER DAY -- is it steady or is it one day?")
    import datetime as dt
    per = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for r in rows:
        d = dt.datetime.utcfromtimestamp(r[7]).strftime("%Y-%m-%d")
        per[d][0] += r[0] * r[1]
        per[d][1] += r[1]
        per[d][2] += 1
    print("  %-12s %10s %12s %12s" % ("UTC day", "trades", "contracts", "maker $"))
    for d in sorted(per):
        v = per[d]
        print("  %-12s %10d %12.0f %12.2f" % (d, v[2], v[1], v[0]))

    print("\nEVERY FIGURE IS WHAT THE MARKET DID. It is the size of the prize,")
    print("not our fill rate and not our loss rate. We would be one maker in a")
    print("queue, and only our own fills can say what we would actually get.")

    if a.gate:
        return gated(rows, idx, M, ruler=a.ruler, kappa=a.kappa, lag=a.lag)
    return 0


def gated(rows, idx, M, ruler="3600", kappa=1.0, tau_hi=60, lag=0):
    """DOES OUR FORECAST SEPARATE THE GOOD TAKES FROM THE BAD ONES?

    The census above says the average taker who bought a leg at 90-98c inside
    tau 30 LOST money. That population is not ours -- it includes everyone who
    paid 94c for a leg our model would have priced at 60c. This is the test
    that matters: take the same trades, ask the forecast what it thought at
    that second, and see whether the gate keeps the winners and drops the
    losers.

    Scored as a TAKER, because that is what we are. Fees charged.

    Every trade is scored against the forecast as of its OWN second -- no
    look-ahead, the bug that turned 89.4% into 98.9% the first time this
    product was measured.

    `lag` STALES THE FORECAST BY THAT MANY SECONDS, and it is the control that
    matters. A trade stamped inside second S is matched to a forecast built
    from prints through second S; if that second's index print actually
    reaches us after the trade, the gate has seen a fraction of a second of
    the future -- and in a race half of which is decided by under 7 basis
    points, a fraction of a second is enough to manufacture a perfect record.
    Run at lag 1 and 2 and the separation must survive, or it was never
    there."""
    import datetime as dt
    import pinracefair as F
    print("\n## DOES THE FORECAST SEPARATE THE GOOD TAKES FROM THE BAD?")
    print("Same trades as above, scored as a taker with fees, split by what our")
    print("model believed at that second. Ruler %s, fat-tail %.2f, forecast "
          "staled by %d s." % (ruler, kappa, lag))
    cache, ser_cache = {}, {}

    def fair(c, tau):
        k = (c, tau)
        if k not in cache:
            if c not in ser_cache:
                ser_cache.clear()
                ser_cache[c] = F.RaceSeries(idx, c)
            pr, _ = F.fair_at(idx, ser_cache[c], c, tau, ruler, (kappa,))
            cache[k] = pr[kappa] if pr else None
        return cache[k]

    sel = sorted([r for r in rows if 1 <= r[5] <= tau_hi and r[3] == "yes"],
                 key=lambda r: (r[7], -r[5]))
    print("  %d taker YES buys inside tau %d to score" % (len(sel), tau_hi))
    scored = []
    for k, (pnl, cnt, yp, side, wonleg, tau, coin, c) in enumerate(sel):
        p = fair(c, max(tau + lag, 1))
        if p is None or coin not in p:
            continue
        scored.append((p[coin], yp, cnt, wonleg, tau, c))
        if (k + 1) % 5000 == 0:
            print("    ... %d/%d" % (k + 1, len(sel)), flush=True)
    if not scored:
        print("  nothing scorable -- no index coverage on these races")
        return 0

    def report(rowset, label):
        """Clustered by CLOSE, per hard rule 4: hundreds of trades share one
        settlement, so `races` and `bad races` are the honest counts and
        `trades` is shown only to say how concentrated the flow is."""
        if not rowset:
            print("  %-34s %8s" % (label, "none"))
            return
        cts = sum(r[2] for r in rowset)
        gross = sum(r[2] * ((1.0 if r[3] else 0.0) - r[1]) for r in rowset)
        fees = sum(racebook.order_fee(r[2], r[1]) for r in rowset)
        wc = sum(r[2] for r in rowset if r[3])
        races = {r[5] for r in rowset}
        bad = {r[5] for r in rowset if not r[3]}
        print("  %-34s %6d %5d %5d %8.0f %6.1f%% %+8.2fc %+9.2f"
              % (label, len(rowset), len(races), len(bad), cts,
                 100.0 * wc / cts if cts else 0,
                 100 * (gross - fees) / cts if cts else 0, gross - fees))

    print("\n  %-34s %6s %5s %5s %8s %7s %9s %10s"
          % ("population", "trades", "races", "bad", "contr", "won", "NET c/ct",
             "NET $"))
    for tlo, thi, plo in ((1, 30, 0.90), (1, 60, 0.90), (1, 30, 0.0)):
        base = [r for r in scored if tlo <= r[4] <= thi and r[1] >= plo]
        head = "tau<=%d, price>=%.0fc" % (thi, 100 * plo)
        report(base, head + "  ALL takers")
        for edge in (0.0, 0.01, 0.02, 0.04):
            g = [r for r in base
                 if r[0] - r[1] - racebook.order_fee(1, r[1]) >= edge]
            report(g, head + "  model edge >= %.0fc" % (100 * edge))
        anti = [r for r in base if r[0] - r[1] < 0]
        report(anti, head + "  model says OVERPAID")
        print("  %s" % ("-" * 84))

    print("\n  BY DAY, the rule the live arm runs (tau<=30, price>=90c, edge>=2c)")
    per = collections.defaultdict(lambda: [0.0, 0.0, 0, 0.0])
    for belief, yp, cnt, wonleg, tau, c in scored:
        if not (1 <= tau <= 30 and yp >= 0.90):
            continue
        if belief - yp - racebook.order_fee(1, yp) < 0.02:
            continue
        d = dt.datetime.utcfromtimestamp(c).strftime("%Y-%m-%d")
        v = per[d]
        v[0] += cnt * ((1.0 if wonleg else 0.0) - yp) - racebook.order_fee(cnt, yp)
        v[1] += cnt
        v[2] += 1
        v[3] += (cnt if wonleg else 0)
    print("  %-12s %8s %10s %9s %10s" % ("UTC day", "trades", "contracts", "won",
                                         "NET $"))
    for d in sorted(per):
        v = per[d]
        print("  %-12s %8d %10.0f %8.1f%% %+9.2f"
              % (d, v[2], v[1], 100.0 * v[3] / v[1] if v[1] else 0, v[0]))
    print("\n  These are OTHER PEOPLE'S fills at prices that existed. They are")
    print("  what the rule would have been worth on the trades that happened,")
    print("  not our fill rate and not our loss rate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
