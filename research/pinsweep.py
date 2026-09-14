#!/usr/bin/env python3
# VERSION: 2026-09-14-sw1
"""pinsweep.py -- try every combination of the bot's dials against the tape.

THE OPERATOR, 2026-09-14: "mess around with all the variables and timings and
amounts to figure out how to make it work best ... Try different variations of
like how confident you are and how much it drops before you buy hedge, and any
other things you can imagine ... Just post the results live as they happen."

THE TRAP THIS FILE EXISTS TO AVOID, and it caught me an hour before writing it.

Asked "how cheap did the WINNING side ever get in the last minute", the tape
answers: 24.4% of markets touched 90c or better, 11.2% touched 50c or better.
That looks like an enormous untapped edge. It is not. The winning side is
cheap at a given second precisely BECAUSE the market -- and our model with it
-- believed it was going to LOSE at that second. Selecting on the outcome and
then admiring the price is outcome leakage in its purest form: those 50c
quotes are markets that flipped, and nothing visible at the time said to buy.

So a price is only an opportunity if THE MODEL WAS ALREADY CONFIDENT AT THAT
SAME SECOND. This file joins the three things that must agree:

    the INDEX      -> what the model believed, second by second
    the TICKER     -> what either side actually cost, second by second
    the SETTLEMENT -> who won

and only counts a moment where belief and price coincide. Everything else in
here is arithmetic on top of that join.

WHAT IT MAY AND MAY NOT CONCLUDE. CLAUDE.md rule 5: the tape's population is
"an offer was sitting there", ours is "someone actively sold it to us", and
they differ 31x. So the win rate printed here is THE TAPE'S, never ours, and
every ranking is a list of HYPOTHESES TO PAPER-TEST rather than a result. The
operator's own standing rule is blunter: the backtest is not evidence. What a
sweep is genuinely good for is finding which dials matter at all, and which
are dead ends not worth a paper arm.
"""
import argparse
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gzsalvage                                               # noqa: E402
import pincalib                                               # noqa: E402
from engine import var_factor, N_AVG                          # noqa: E402

WINDOW = 60
FEE = 0.07


def fee_per(p):
    return FEE * p * (1.0 - p)


# ------------------------------------------------------------------ join
def load_markets(path, series_ok):
    out = {}
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    for ser, rows in (d or {}).items():
        if ser not in series_ok:
            continue
        for r in rows or []:
            if r.get("result") in ("yes", "no") and r.get("close") \
                    and r.get("strike") is not None:
                out[r["ticker"]] = {"ser": ser, "close": int(float(r["close"])),
                                    "strike": float(r["strike"]),
                                    "result": r["result"]}
    return out


def prices(tick_dir, markets, limit=None, say=print):
    """{(ticker, tau): (yes_ask, no_ask)} -- what each side cost, per second.

    THE SIDE CONVERSION IS THE TRAP. Buying NO at q is selling YES at 1-q, so
    the NO ask is 1 - yes_BID. Using 1 - yes_ask prices the losing side inside
    the spread and invents an edge.
    """
    out = {}
    files = sorted(glob.glob(os.path.join(tick_dir, "*.jsonl.gz")))
    if limit:
        files = files[-limit:]
    for i, p in enumerate(files):
        for line in gzsalvage.iter_lines(p):
            if "15M-" not in line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            msg = m.get("msg") or {}
            mk = markets.get(msg.get("market_ticker"))
            if not mk:
                continue
            try:
                tau = mk["close"] - int(float(msg.get("ts")))
            except (TypeError, ValueError):
                continue
            if not (0 < tau <= WINDOW):
                continue

            def g(k):
                try:
                    return float(msg.get(k))
                except (TypeError, ValueError):
                    return None
            ya, yb = g("yes_ask_dollars"), g("yes_bid_dollars")
            na = None if yb is None else 1.0 - yb
            key = (msg["market_ticker"], tau)
            prev = out.get(key)
            ya = ya if (ya and 0 < ya < 1) else None
            na = na if (na and 0 < na < 1) else None
            if prev:
                ya = min(x for x in (ya, prev[0]) if x) if (ya or prev[0]) else None
                na = min(x for x in (na, prev[1]) if x) if (na or prev[1]) else None
            out[key] = (ya, na)
        if say and (i + 1) % 50 == 0:
            say("    prices: %d/%d files" % (i + 1, len(files)))
    return out


def beliefs(index, markets, say=print):
    """{(ticker, tau): P(settle >= strike)} from the index alone."""
    import replay
    out = {}
    by_ser = defaultdict(list)
    for tk, mk in markets.items():
        by_ser[mk["ser"]].append((tk, mk))
    for ser, items in sorted(by_ser.items()):
        iid = replay.SERIES_TO_INDEX.get(ser)
        if not iid:
            continue
        ser_idx = index(iid)
        if not ser_idx:
            continue
        for tk, mk in items:
            c, K = mk["close"], mk["strike"]
            for tau in range(1, WINDOW):
                now = c - tau
                spot = ser_idx.get(now - 1)
                if spot is None:
                    continue
                locked = 0.0
                ok = True
                for s in range(c - WINDOW, c - tau):
                    v = ser_idx.get(s)
                    if v is None:
                        ok = False
                        break
                    locked += v
                if not ok:
                    continue
                sg = pincalib.sigma_at(ser_idx, now - 1)
                if not sg:
                    continue
                sd = sg * math.sqrt(var_factor(int(tau), [1.0]))
                if sd <= 0:
                    continue
                mu = (locked + tau * spot) / float(N_AVG)
                out[(tk, tau)] = pincalib.norm_cdf((mu - K) / sd)
        ser_idx.clear()
        if say:
            say("    beliefs: %s done (%d rows)" % (ser, len(out)))
    return out


# ------------------------------------------------------------------ sweep
def opportunities(markets, px, bel, pin, tau_max, ceiling, edge_floor):
    """One record per market: the FIRST second, walking down from tau_max,
    where the model was confident AND that side was buyable.

    Walking DOWN from tau_max is the live bot's own behaviour -- it takes the
    first moment that qualifies, it does not wait for the best.
    """
    out = []
    for tk, mk in markets.items():
        for tau in range(min(tau_max, WINDOW - 1), 0, -1):
            b = bel.get((tk, tau))
            if b is None:
                continue
            p = px.get((tk, tau))
            if not p:
                continue
            if b >= pin:
                side, price, conf = "yes", p[0], b
            elif b <= 1.0 - pin:
                side, price, conf = "no", p[1], 1.0 - b
            else:
                continue
            if price is None or price > ceiling:
                continue
            edge = conf - price - fee_per(price)
            if edge < edge_floor:
                continue
            out.append({"tk": tk, "tau": tau, "side": side, "price": price,
                        "conf": conf, "edge": edge,
                        "won": (side == mk["result"])})
            break
    return out


def score(ops):
    if not ops:
        return None
    n = len(ops)
    w = sum(1 for o in ops if o["won"])
    pl = sum((1.0 - o["price"] - fee_per(o["price"])) if o["won"]
             else (-o["price"] - fee_per(o["price"])) for o in ops)
    pr = sorted(o["price"] for o in ops)
    closes = len(set(o["tk"].split("-")[1] for o in ops))
    return {"n": n, "closes": closes, "wins": w, "losses": n - w,
            "loss_rate": 100.0 * (n - w) / n,
            "cents": 100.0 * pl / n, "total": pl,
            "med_price": 100 * pr[len(pr) // 2],
            "p25": 100 * pr[len(pr) // 4]}


HDR = ("  gate   tau  ceil  edge |  buys closes | loss%  | med px |  c/buy  |"
       "    total")


def line(pin, tau_max, ceiling, edge_floor, s):
    if not s:
        return ("  %.3f %4d %5.0fc %4.1fc |     0      0 |   --   |   --   |"
                "   --    |     --" % (pin, tau_max, 100 * ceiling,
                                       100 * edge_floor))
    return ("  %.3f %4d %5.0fc %4.1fc | %5d %6d | %5.2f%% | %5.1fc | %+6.2fc |"
            " %+8.2f" % (pin, tau_max, 100 * ceiling, 100 * edge_floor,
                         s["n"], s["closes"], s["loss_rate"], s["med_price"],
                         s["cents"], s["total"]))


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    mk = {"A-26SEP140000-0": {"ser": "KXBTC15M", "close": 1000,
                              "strike": 1.0, "result": "yes"},
          "B-26SEP140000-0": {"ser": "KXBTC15M", "close": 1000,
                              "strike": 1.0, "result": "no"}}
    # A: model sure of YES from 40s out, YES on offer at 90c
    # B: model sure of YES too -- but NO actually won (a model error)
    bel = {}
    px = {}
    for tau in range(1, 60):
        bel[("A-26SEP140000-0", tau)] = 0.999
        bel[("B-26SEP140000-0", tau)] = 0.999
        px[("A-26SEP140000-0", tau)] = (0.90, 0.10)
        px[("B-26SEP140000-0", tau)] = (0.90, 0.10)
    ops = opportunities(mk, px, bel, 0.995, 40, 0.98, 0.003)
    ck(len(ops) == 2, "both markets produce exactly ONE buy each, not one per "
                      "second -- the bot takes a position, it does not "
                      "re-enter every tick")
    ck(all(o["tau"] == 40 for o in ops),
       "and it enters at the EARLIEST second allowed (40), walking down, "
       "which is what the live loop does")
    s = score(ops)
    ck(s["n"] == 2 and s["wins"] == 1 and abs(s["loss_rate"] - 50.0) < 1e-9,
       "one won and one lost -- a model error is scored as a loss")
    _hand = (1 - 0.90 - fee_per(0.90)) + (-0.90 - fee_per(0.90))
    ck(abs(s["total"] - _hand) < 1e-12,
       "and the P&L is the two added with the fee on both: %+.4f" % s["total"])

    # THE GATES MUST ACTUALLY BITE
    ck(opportunities(mk, px, bel, 0.9999, 40, 0.98, 0.003) == [],
       "a gate above the model's confidence refuses everything")
    ck(opportunities(mk, px, bel, 0.995, 40, 0.85, 0.003) == [],
       "a ceiling under the price refuses everything")
    ck(opportunities(mk, px, bel, 0.995, 40, 0.98, 0.50) == [],
       "and an edge floor above the edge refuses everything")

    # THE SIDE MUST BE RIGHT. Model sure of NO -> it must buy the NO ask
    bel2 = dict((k, 0.001) for k in bel)
    ops2 = opportunities(mk, px, bel2, 0.995, 40, 0.98, 0.003)
    ck(ops2 and all(o["side"] == "no" for o in ops2),
       "when the model is sure of NO it buys NO")
    ck(all(abs(o["price"] - 0.10) < 1e-9 for o in ops2),
       "at the NO price (10c), not the YES price (90c) -- getting this "
       "backwards is how a sweep invents an edge out of the spread")
    ck(sum(1 for o in ops2 if o["won"]) == 1,
       "and B, which settled NO, is the WINNER on that side")

    # OUTCOME LEAKAGE: a cheap winning side the model did NOT believe in must
    # NOT be counted. This is the whole reason the file exists.
    bel3 = dict(bel)
    for tau in range(1, 60):
        bel3[("A-26SEP140000-0", tau)] = 0.50      # model has no opinion
    ops3 = opportunities(mk, px, bel3, 0.995, 40, 0.98, 0.003)
    ck(all(o["tk"] != "A-26SEP140000-0" for o in ops3),
       "a market whose winning side was CHEAP but which the model had no "
       "opinion on is NOT an opportunity. 24.4%% of markets touch 90c on the "
       "winning side, and most of that is markets that flipped -- counting "
       "them would manufacture an enormous edge from hindsight alone")
    print("pinsweep selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ticks", default="C:/kals/kalshi_data/ticker")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--files", type=int, default=120)
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "SWEEP_LIVE.txt"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SWEEP_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    import replay
    import pinwarn
    series_ok = set(replay.SERIES_TO_INDEX)
    mk = load_markets(a.markets, series_ok)
    print("  %d settled markets" % len(mk))
    px = prices(a.ticks, mk, limit=(a.files or None))
    print("  %d (market, second) quotes" % len(px))
    keep = set(t for t, _ in px)
    mk = dict((k, v) for k, v in mk.items() if k in keep)
    print("  %d markets have quotes; loading the index for those" % len(mk))
    cache = {}

    def index(iid):
        if iid not in cache:
            cache.clear()
            cache[iid] = pinwarn.load_one_index(a.data, iid)
        return cache[iid]
    bel = beliefs(index, mk)
    print("  %d (market, second) beliefs" % len(bel))

    PINS = (0.98, 0.99, 0.995, 0.999)
    TAUS = (30, 40, 50, 55)
    CEILS = (0.90, 0.95, 0.97, 0.98)
    EDGES = (0.003, 0.01, 0.03)
    rows = []
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("SWEEP -- live, appended as each combination finishes" + nl)
        fh.write("started %s ET%s%s" % (time.strftime("%I:%M:%S %p"), nl, nl))
        fh.write(HDR + nl)
    print(HDR)
    for pin in PINS:
        for tm in TAUS:
            for ce in CEILS:
                for ef in EDGES:
                    s = score(opportunities(mk, px, bel, pin, tm, ce, ef))
                    ln = line(pin, tm, ce, ef, s)
                    print(ln, flush=True)
                    with open(a.out, "a", encoding="utf-8") as fh:
                        fh.write(ln + nl)
                    if s:
                        rows.append((pin, tm, ce, ef, s))
    rows.sort(key=lambda r: -r[4]["total"])
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write(nl + "BEST BY TOTAL (tape population -- hypotheses, not "
                 "results)" + nl + HDR + nl)
        for r in rows[:15]:
            fh.write(line(r[0], r[1], r[2], r[3], r[4]) + nl)
    print(nl + "  top 5 by total:")
    for r in rows[:5]:
        print(line(r[0], r[1], r[2], r[3], r[4]))
    print("  full table streaming to %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
