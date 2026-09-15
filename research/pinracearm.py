#!/usr/bin/env python3
# VERSION: 2026-09-15-arm3
"""pinracearm.py -- THE COIN RACE PAPER ARM. Nothing is ever sent.

THE OPERATOR, 2026-09-15: "you can absolutely start on a coin race paper arm.
Just make sure it's completely accurate."

WHAT IS NEW HERE, AND WHY THE OLD RACE WORK MISSED IT

`pinlead` / `pinleadprice` / `pinracetest` all asked one question: is anyone
selling us THE LEADER. `pinracetest` ran seven races live and sent zero orders
-- one candidate, refused for a thin margin, and it was the one race the model
got wrong. One shot per race, at tau 20 exactly, capped at 95c.

But a race has FIVE legs and FOUR OF THEM LOSE. The leader's YES is one
contract; the four trailers' NOs are four more, and a coin fifteen basis
points behind with eight seconds left is a far flatter bet than the leader is.
So this arm prices EVERY LEG, on the side we would actually want, for the
whole approach to the close instead of a single second.

It also behaves differently on a loss, and that is the part worth measuring.
When the leader is overtaken, the leader's YES loses -- but of our four NOs,
THREE STILL WIN, because only one trailer can take the lead. The NO side's
losses are structurally a quarter the size of the YES side's. That is not an
opinion; it is what "exactly one leg wins" means, and this arm records it.

THE FORECAST is `pinracemodel`, which reproduces Kalshi's own settled winner
on 761 of 761 races from the index tape alone, and reads every cell of its
table as a 95% UPPER bound rather than a point estimate -- so a cell of "0
wins in 120 races" is priced at 2.5% risk, not zero.

WHAT MAKES IT ACCURATE, item by item, because that was the instruction:

  NO LOOK-AHEAD      the forecast at second t uses only index prints at or
                     before t, exactly as the live bot does.
  OUT OF SAMPLE      the table is fitted on races that CLOSED BEFORE this
                     process started. Its fingerprint and race count go in the
                     log so that can be checked later, not asserted now.
  SUPPLY IS REAL     size is capped by what the book actually shows at or under
                     our limit, via LiveBook.buyable, and the whole ladder is
                     recorded next to every fill.
  FEES ARE REAL      0.07*p*(1-p), rounded up to the cent-hundredth, the same
                     function the live bot reconciled against the account.
  SELF-SCORING       at close+75s it recomputes the winner from our own index
                     and marks every paper position won or lost. No settlement
                     pull, no waiting, no chance of scoring the wrong race.
  SILENCE IS LOGGED  every reason we did NOT buy is recorded once per leg per
                     reason. `pinracetest` learned this the hard way: a race
                     that logged nothing was indistinguishable from a race with
                     no edge.

WHAT IT STILL CANNOT TELL US, stated here rather than in a footnote:

  * WHETHER WE WIN THE FILL. Every price here is an offer we saw, not an offer
    we got. This is the project's oldest open risk and no paper arm can close
    it. Fills are labelled `assumed` in the log and the report says so.
  * ADVERSE SELECTION. On the up/down markets the counterparty is 26x more
    often right when they actively sell to us (RESULTS_select). If the same
    holds here, the realised loss rate will be worse than the table's, and
    only real fills will show it.

    python research/pinracearm.py --selftest
    python research/pinracearm.py --minutes 600
"""
import argparse
import calendar
import collections
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import livebook                                              # noqa: E402
import pinrun                                                # noqa: E402
import pinracemodel as M                                     # noqa: E402

SERIES = "KXCRYPTOLEAD15M"
COINS = M.COINS
N_AVG = M.N_AVG
WINDOW = M.WINDOW

# ---- the rails ------------------------------------------------------------
SIZE = 250                # contracts we would ask for per fill
# ONE FILL PER LEG PER SIDE PER TIME BAND, and no per-race cap.
#
# arm1 capped at 2 fills a leg and 4 a race. On its first live race (11:45 ET,
# 2026-09-15) all four went at tau 126-150 -- ETH NO at 66c twice against the
# SAME 1,081 resting contracts, then BTC YES at 74c and 58c -- and the race was
# then closed to the last 30 seconds, which is the only band the tape
# (pinraceno) says is safe. The caps made the arm measure the known trap and
# nothing else. A paper arm has no bank to protect, so each band is its own
# measurement instead.
BANDS = ((61, 151), (30, 61), (15, 30), (2, 15))   # [lo, hi) seconds out
PRICE_CEILING = 0.98      # never pay 99c, the same ceiling the live bot uses
MIN_EDGE = 0.02           # 2c net of fee. RESULTS_coinrace measured the live
                          # bands at +2.5c to +4.8c a contract, so this sits at
                          # the bottom of what has ever been seen rather than
                          # at whatever the table happens to allow.
TAU_LO, TAU_HI = 2, 150   # the whole approach, not one second
SUBSCRIBE_LEAD = 120      # seconds of warm-up before the window
MAX_INDEX_AGE_S = 5
MAX_BOOK_AGE_MS = 300000  # a quiet race book is UNCHANGED, not stale --
                          # pinracetest lost three races to a 15s gate
SCORE_DELAY = 75          # seconds after the close before we score it


def fee(p, n=1.0):
    """Taker fee, rounded UP to the cent-hundredth, as the exchange bills it."""
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def open_twap(ticks, open_s):
    """Mean of the 60 prints over [open-60, open). None if ANY is missing.

    Never a partial mean. The denominator is the half of the settlement rule
    that is already fixed; guessing at it would put every return on this race
    quietly wrong in the same direction."""
    v = [ticks[s] for s in range(open_s - N_AVG, open_s) if s in ticks]
    if len(v) < N_AVG:
        return None
    return sum(v) / float(N_AVG)


def close_mu(ticks, close_s, now_s, spot):
    """Forecast of the closing 60-second mean: the prints already locked, plus
    the newest print carried forward for the seconds still to come.

    NO LOOK-AHEAD: `hi` is min(now-1, close-1), so a second that has not
    happened yet can never enter the sum."""
    lo = close_s - N_AVG
    hi = min(now_s - 1, close_s - 1)
    got = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
    n = len(got)
    if n > N_AVG or spot is None:
        return None
    return (sum(got) + (N_AVG - n) * float(spot)) / float(N_AVG)


def price_leg(table, tau, gap_bp):
    """(side, worth) for one leg -- which side we would buy and what it is
    worth, as a probability, on the pessimistic read of the table.

    A coin AHEAD of the field is a YES, and the number that matters is its
    chance of being overtaken, bounded above. A coin BEHIND is a NO, and the
    number that matters is its chance of still winning, also bounded above.
    Both bounds push the same way: they make the contract worth LESS.

    `worth` is None when the table has nothing for this gap and tau, and None
    means STAND ASIDE at any price. An earlier version returned 0.5 there, on
    the reasoning that a coin flip licenses nothing -- true at 95c, false at
    21c, where "worth 50c" reads as a 29c edge. Measured on 77 tape legs
    2026-09-15: the no-data cases were the BULK of what a 2c edge floor let
    through, and they were the cheap ones."""
    if gap_bp > 0:
        p = M.p_lose(table, tau, gap_bp)
        return "yes", (None if p is None else 1.0 - p)
    p = M.p_win(table, tau, gap_bp)
    return "no", (None if p is None else 1.0 - p)


def gate_arm3(tau, gap_bp, price, tau_max, min_gap_bp, min_price):
    """ARM3: the one form of this idea the evidence supports. None = allowed.

    arm2 lost on paper (73 bets, 44 won, -$1,560 at 250 a bet, 12 races,
    2026-09-15). No wiring bug: every bet was the right coin and side. The
    losses were PHOTO FINISHES -- every late-window loss had a lead under
    1.4bp, where the market priced 65-78c and the table claimed ~89c -- and
    cheap bets bought while the race was still open. So:

      tau_max    only the last seconds: RESULTS_coinrace found the market
                 efficient before tau 30 and the edge only inside it
      min_gap_bp only a CLEAR lead or a clear deficit: at tau <= 25 no lead of
                 4bp+ was overturned in 795 races, and the tape's 93c+ winners
                 (pinraceno) all had gaps past 4bp
      min_price  never the cheap end: a cheap price on a "clear" lead means the
                 market knows something (RESULTS_coinrace discount cliff)
    """
    if tau > tau_max:
        return "outside_tau_max"
    if abs(gap_bp) < min_gap_bp:
        return "small_gap"
    if price is not None and price < min_price - 1e-9:
        return "below_min_price"
    return None


def band_of(tau):
    """The time band a moment belongs to, as a label, or None outside them."""
    for lo, hi in BANDS:
        if lo <= tau < hi:
            return "%d-%d" % (lo, hi)
    return None


def take_size(size, buyable, already):
    """Contracts a new fill may take from a book we have already bought from.

    THE BOOK DEPLETES. Inside one race, two looks at a leg are largely the SAME
    resting orders. arm1 took 250 of ETH's 1,081 NO contracts at 66c and then,
    a quarter-second later, took the same 250 again. So what we already hold
    on this leg and side comes off what the book shows -- the rule pinreal
    uses, and pessimistic when the book has genuinely refilled."""
    left = (buyable or 0.0) - already
    if left <= 0:
        return 0
    return int(min(size, left))


def net_edge(worth, price):
    """Cents of edge per contract after the taker fee, as a fraction.

    None worth is None edge -- never a number, so it can never clear a floor."""
    if worth is None:
        return None
    return worth - price - fee(price)


def winner_from(ticks_by_coin, close_s):
    """The winner of a finished race, recomputed from our own index.

    This is the function `pinracemodel` validated at 761 of 761 against
    Kalshi's own settled `result`, which is why this arm does not need a
    settlement pull to score itself."""
    rets = {}
    for coin, ticks in ticks_by_coin.items():
        den = open_twap(ticks, close_s - WINDOW)
        num = [ticks[s] for s in range(close_s - N_AVG, close_s) if s in ticks]
        if not den or len(num) < N_AVG:
            return None, {}
        rets[coin] = (sum(num) / float(N_AVG)) / den
    if len(rets) < 2:
        return None, {}
    return max(rets.items(), key=lambda kv: kv[1])[0], rets


def selftest():
    print("SELF-TEST -- pinracearm")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # ---- THIS FILE MUST NEVER BE ABLE TO SEND AN ORDER -----------------
    # THE SELF-INSPECTION TRAP. Every needle below is BUILT, never written,
    # because spelling a module name out in this test would let the test find
    # its own comment, and
    # the check would fail on itself -- which is exactly how four earlier
    # structural tests in this project passed or failed for the wrong reason.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    needles = [("pin" + "take", "the module that can actually send an order"),
               ("pinrun." + "arm(", "the call that disarms the live bot's guard"),
               ("--" + "live", "a flag that could be passed by accident"),
               ("post_" + "only", "a maker order field"),
               ("/portfolio/" + "orders", "the order endpoint itself")]
    for needle, what in needles:
        ck(src.count(needle) == 0,
           "%s (%s) appears NOWHERE in this file -- nothing here can reach "
           "the exchange with an order" % (needle, what))

    # ---- the rails -----------------------------------------------------
    ck(PRICE_CEILING <= 0.98,
       "the price ceiling is at most 98c -- 99c leaves a cent of upside "
       "against a whole dollar of downside")
    ck(MIN_EDGE >= 0.02,
       "the edge floor is at least 2c, the bottom of the +2.5c..+4.8c bands "
       "RESULTS_coinrace actually measured, not whatever the table allows")
    ck(band_of(150) == "61-151" and band_of(61) == "61-151"
       and band_of(60) == "30-61" and band_of(29) == "15-30"
       and band_of(2) == "2-15" and band_of(1) is None and band_of(151) is None,
       "every tau from 2 to 150 lands in exactly one band, and nothing outside")
    ck(len({band_of(t) for t in range(TAU_LO, TAU_HI + 1)}) == len(BANDS),
       "and all four bands are reachable from the scanned range")
    ck(take_size(250, 1081, 0) == 250,
       "the first look at ETH's 1,081 NO contracts takes 250")
    ck(take_size(250, 1081, 250) == 250 and take_size(250, 1081, 1000) == 81,
       "a later look takes only what the book holds BEYOND what we already "
       "bought -- 81 once 1,000 are ours, not another 250")
    ck(take_size(250, 1081, 1081) == 0 and take_size(250, 900, 1081) == 0,
       "and nothing at all once we hold the whole book, or the book shrank "
       "below what we hold -- the arm1 double-count, closed")
    ck(take_size(250, None, 0) == 0, "NULL: an unreadable book takes nothing")
    ck(TAU_LO >= 1, "we never price a race after it has closed")

    # ---- scoring reads the races that OUTLIVE their close --------------
    body = src[src.index(chr(10) + "def main("):]
    sc = body[body.index("# ---- SCORE"):body.index("# ---- PRICE")]
    ck("known.items()" in sc and "events.items()" not in sc,
       "the scorer walks `known`, not `events` -- `events` is what Kalshi "
       "calls OPEN, a race stops being open at its close, and arm1 therefore "
       "never scored a single race")
    ck("known.update(events)" in body,
       "and every discovered race is added to `known` before it can drop out")

    # ---- ARM3 gate -------------------------------------------------------
    ck(gate_arm3(29, 1.26, 0.78, 30, 4.0, 0.90) == "small_gap",
       "the 3:30 PM race bet -- BTC ahead by 1.26bp at 29 s, bought at 78c, "
       "lost when ETH passed -- is refused for its tiny lead")
    ck(gate_arm3(90, -10.1, 0.95, 30, 4.0, 0.90) == "outside_tau_max",
       "the 4:15 PM race bet -- HYPE 10bp behind with 90 s left, 95c, lost "
       "when HYPE came back -- is refused for being too early")
    ck(gate_arm3(27, 4.27, 0.87, 30, 4.0, 0.90) == "below_min_price",
       "a clear lead offered at only 87c is refused -- a cheap price on a "
       "'clear' lead means the market knows something")
    ck(gate_arm3(12, -8.0, 0.95, 30, 4.0, 0.90) is None,
       "a coin 8bp behind with 12 s left, its NO at 95c, is allowed")
    ck(gate_arm3(12, 8.0, None, 30, 4.0, 0.90) is None,
       "and the pre-book check (no price yet) passes a clear late lead")
    ck(gate_arm3(150, 0.1, 0.30, TAU_HI, 0.0, 0.0) is None,
       "with the defaults every arm2 bet is still allowed, so old logs stay "
       "reproducible")

    # ---- the fee -------------------------------------------------------
    ck(abs(fee(0.95) - 0.0034) < 1e-9,
       "95c costs 0.34c to take (0.07*0.95*0.05, rounded up) -- the same "
       "function the live bot reconciled against the account")
    ck(fee(0.97) < fee(0.90),
       "and the fee SHRINKS toward the ends, which is why the expensive legs "
       "are cheaper to trade than they look")
    ck(fee(0.5) > fee(0.95), "it is largest at a coin flip")

    # ---- NO LOOK-AHEAD, the single most important test here ------------
    ticks = {s: 100.0 for s in range(1000, 1200)}
    ticks.update({s: 999.0 for s in range(1150, 1200)})     # the FUTURE
    close_s = 1160
    mu = close_mu(ticks, close_s, 1130, 100.0)
    ck(mu == 100.0,
       "at second 1130 the forecast is 100.0 and NOT pulled toward the 999s "
       "sitting at seconds 1150-1159 -- a future print can never enter the sum")
    mu2 = close_mu(ticks, close_s, 1155, 999.0)
    ck(mu2 is not None and 100.0 < mu2 < 999.0,
       "and once those seconds ARRIVE they count: the forecast moves to %.1f"
       % (mu2 or 0))
    lo = close_s - N_AVG
    ck(close_mu({s: 1.0 for s in range(lo, lo + 60)}, close_s, close_s, 1.0) == 1.0,
       "a fully locked window forecasts itself exactly")
    ck(close_mu({}, close_s, close_s - 30, None) is None,
       "NULL: no spot and no prints forecasts nothing, never a zero")

    # ---- the open window, which is a blind spot not an absence ---------
    full = {s: 5.0 for s in range(0, 100)}
    ck(open_twap(full, 60) == 5.0, "a complete opening minute averages")
    short = {s: 5.0 for s in range(0, 100) if s != 30}
    ck(open_twap(short, 60) is None,
       "and ONE missing print refuses the whole race rather than averaging 59 "
       "-- the denominator is half the settlement rule")

    # ---- which side, and what it is worth ------------------------------
    tbl = {"12": {str(M.bucket(-15.0)): {"n": 200, "won": 0},
                  str(M.bucket(15.0)): {"n": 200, "won": 200}}}
    side, worth = price_leg(tbl, 12, -15.0)
    ck(side == "no" and worth is not None and 0.98 < worth < 1.0,
       "a coin 15bp BEHIND is a NO worth %.4f -- not 1.0, because 0 wins in "
       "200 races bounds at %.2f%%, not at zero" % (worth, 100 * (1 - worth)))
    side2, worth2 = price_leg(tbl, 12, 15.0)
    ck(side2 == "yes" and 0.98 < worth2 < 1.0,
       "a coin 15bp AHEAD is a YES worth %.4f, bounded the same way" % worth2)
    ck(price_leg({}, 12, 15.0)[1] is None and price_leg({}, 12, -15.0)[1] is None,
       "NULL: with no table at all a leg is worth NOTHING KNOWN, and None is "
       "not a number that can clear an edge floor")
    ck(net_edge(None, 0.21) is None and not (net_edge(None, 0.21) or 0) >= MIN_EDGE,
       "so a 21c longshot the table has never seen produces no edge at all -- "
       "the case that was worth 50c, and therefore a 29c edge, before this")
    ck(net_edge(None, 0.97) is None,
       "and the same at 97c, where the old 0.5 happened to refuse by accident")

    # ---- the edge arithmetic -------------------------------------------
    ck(abs(net_edge(0.99, 0.95) - (0.04 - fee(0.95))) < 1e-9,
       "something worth 99c bought at 95c earns 4c less the 0.34c fee")
    ck(net_edge(0.975, 0.97) < MIN_EDGE,
       "a half-cent of gross edge does NOT clear the 2c floor")
    ck(net_edge(0.99, 0.99) < 0,
       "and paying exactly what it is worth LOSES the fee -- the fee is never "
       "forgotten by being small")
    ck(net_edge(0.5, 0.03) > 0 and net_edge(0.02, 0.03) < 0,
       "the arithmetic has no side preference: it is the same subtraction for "
       "a 3c longshot that is worth 50c and one that is worth 2c")

    # ---- SCORING, and the property the whole file is built to measure --
    t = {}
    for coin, base in (("BTC", 100.0), ("ETH", 100.0), ("SOL", 100.0),
                       ("XRP", 100.0), ("HYPE", 100.0)):
        d = {}
        cs = 10_000
        for s in range(cs - WINDOW - N_AVG, cs):
            d[s] = base
        for s in range(cs - N_AVG, cs):
            d[s] = base * (1.02 if coin == "SOL" else 1.01)
        t[coin] = d
    won, rets = winner_from(t, 10_000)
    ck(won == "SOL",
       "the scorer picks the coin with the biggest return out of five")
    ck(len(rets) == 5 and all(r > 1.0 for r in rets.values()),
       "and every coin rose, which changed nothing -- a common move cannot "
       "decide a race")
    hole = {c: dict(d) for c, d in t.items()}
    hole["BTC"].pop(10_000 - 30)
    ck(winner_from(hole, 10_000)[0] is None,
       "NULL: one missing print in one coin refuses to score the race at all, "
       "rather than scoring it on four legs")

    # THE STRUCTURAL CLAIM: when the leader is overtaken, three of four NOs
    # still win. This is arithmetic, not a measurement, and it is why the NO
    # side is worth building.
    legs = ["BTC", "ETH", "SOL", "XRP", "HYPE"]
    led, actual = "BTC", "ETH"
    no_legs = [c for c in legs if c != led]
    ck(sum(1 for c in no_legs if c != actual) == 3,
       "if we hold NO on all four trailers and the leader IS overtaken, three "
       "of the four still win -- only the coin that took the lead pays out")
    ck(sum(1 for c in no_legs if c != led) == 4,
       "and if the leader HOLDS, all four NOs win -- so the NO side's bad "
       "case is 3-of-4 where the YES side's is 0-of-1, a quarter the damage")

    # ---- the table this arm depends on must itself pass ----------------
    ck(M.upper95(0, 120) > 0.02,
       "the forecast module reads a 0-of-120 cell as %.1f%% risk, not zero -- "
       "if that ever becomes 0 this arm sizes as though it cannot lose"
       % (100 * M.upper95(0, 120)))
    ck(M.p_lose({}, 10, 50.0) is None and M.p_win({}, 10, 50.0) is None,
       "and an empty table stands aside both ways rather than guessing")
    print("SELF-TEST", "PASSED" if not f else "FAILED (%d)" % len(f))
    return not f


def discover():
    """Open Coin Race events -> {event: {"close": epoch, "legs": {coin: tk}}}."""
    sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    from kauth import get
    st, b = get("/markets", {"series_ticker": SERIES, "status": "open",
                             "limit": "200"})
    if st != 200 or not isinstance(b, dict):
        return {}
    out = {}
    for m in b.get("markets", []):
        tk = m.get("ticker") or ""
        evt, _, leg = tk.rpartition("-")
        coin = (m.get("custom_strike") or {}).get("Cryptocurrency") or leg
        if coin not in COINS:
            continue
        try:
            cs = calendar.timegm(time.strptime(m["close_time"],
                                               "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:                                    # noqa: BLE001
            continue
        e = out.setdefault(evt, {"close": float(cs), "legs": {}})
        e["legs"][coin] = tk
    return {k: v for k, v in out.items() if len(v["legs"]) == 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=float, default=600.0)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--min-edge", type=float, default=MIN_EDGE)
    ap.add_argument("--log", default=None)
    ap.add_argument("--tau-max", type=int, default=TAU_HI,
                    help="ARM3: price nothing further out than this")
    ap.add_argument("--min-gap-bp", type=float, default=0.0,
                    help="ARM3: only leads/deficits at least this wide")
    ap.add_argument("--min-price", type=float, default=0.0,
                    help="ARM3: never buy cheaper than this")
    ap.add_argument("--one-per-race-band", action="store_true",
                    help="ARM3: at most one bet per race per time band -- "
                         "'BTC wins' and 'ETH won't win' are one bet twice")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    if not os.path.exists(M.TABLE):
        print("  no forecast table at %s -- run research/pinracemodel.py first"
              % M.TABLE)
        return 1
    table = json.load(open(M.TABLE, encoding="utf-8"))
    tstat = os.stat(M.TABLE)
    cells = sum(len(v) for v in table.values())

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logpath = a.log or os.path.join(REPO, "results",
                                    "pinracearm-%s.jsonl" % stamp)
    logf = open(logpath, "a", encoding="utf-8")

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logf.write(json.dumps(kw) + "\n")
        logf.flush()

    print("\n  COIN RACE PAPER ARM -- nothing is ever sent")
    print("  size %d, <= %.0fc, edge floor %.1fc, tau %d-%d, one fill per "
          "leg per band %s" % (a.size, 100 * PRICE_CEILING, 100 * a.min_edge,
                                TAU_LO, TAU_HI, [band_of(lo) for lo, _ in BANDS]))
    print("  forecast: %s, %d cells, built %s"
          % (os.path.basename(M.TABLE), cells,
             time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(tstat.st_mtime))))
    print("  log: %s\n" % os.path.abspath(logpath))
    rec("start", size=a.size, min_edge=a.min_edge, ceiling=PRICE_CEILING,
        tau=[TAU_LO, TAU_HI], bands=[list(b) for b in BANDS],
        table=os.path.basename(M.TABLE),
        table_cells=cells, table_mtime=int(tstat.st_mtime),
        table_size=tstat.st_size, version="2026-09-15-arm3",
        tau_max=a.tau_max, min_gap_bp=a.min_gap_bp, min_price=a.min_price,
        one_per_race_band=bool(a.one_per_race_band))

    idx = pinrun.IndexWS(sorted(set(COINS.values()))).start()
    book = livebook.LiveBook()
    book.start()
    t0 = time.time()
    while time.time() - t0 < 25 and idx.stats.get("ticks", 0) < 10:
        time.sleep(0.5)
    print("  index up: %d ticks, %d feeds"
          % (idx.stats.get("ticks", 0), len(idx.ticks)))

    events = {}
    # EVERY RACE EVER SEEN, kept until it is scored. `events` is only what
    # discover() calls OPEN, and a race stops being open at its close -- so
    # arm1, which scored from `events`, dropped each race from view 75 seconds
    # before it was due to be scored and never recorded a single result. Found
    # on its first race, 11:45 ET 2026-09-15, which never settled.
    known = {}
    watched = set()
    seen_why = set()
    fills = []                                   # every paper position
    done_band = set()                       # (event, ticker, side, band)
    race_band_done = set()                  # (event, band) -- ARM3
    taken = collections.defaultdict(float)  # (event, ticker, side) -> held
    scored = set()
    last_disc = 0.0
    try:
        while time.time() - t0 < a.minutes * 60:
            now = time.time()
            if now - last_disc > 60:
                last_disc = now
                try:
                    events = discover()
                    known.update(events)
                except Exception as e:                        # noqa: BLE001
                    rec("error", where="discover", err=str(e)[:200])

            # ---- SCORE anything that has closed and settled ------------
            for evt, e in sorted(known.items()):
                cs = int(e["close"])
                if evt in scored or now < cs + SCORE_DELAY:
                    continue
                with idx.lock:
                    tb = {c: dict(idx.ticks.get(iid) or {})
                          for c, iid in COINS.items()}
                won, rets = winner_from(tb, cs)
                scored.add(evt)
                known.pop(evt, None)
                if won is None:
                    rec("unscored", event=evt, close_s=cs,
                        why="index incomplete at close+%ds" % SCORE_DELAY)
                    continue
                mine = [p for p in fills if p["event"] == evt and "win" not in p]
                for p in mine:
                    p["win"] = ((p["coin"] == won) if p["side"] == "yes"
                                else (p["coin"] != won))
                    p["pnl"] = round(p["size"] * ((1.0 - p["price"])
                                                  if p["win"] else -p["price"])
                                     - p["size"] * fee(p["price"]), 4)
                rec("settled", event=evt, close_s=cs, winner=won,
                    returns={k: round(v, 8) for k, v in rets.items()},
                    positions=len(mine),
                    won=sum(1 for p in mine if p["win"]),
                    pnl=round(sum(p["pnl"] for p in mine), 4))
                if mine:
                    print("  SETTLED %-28s %-4s  %d/%d won  $%+.2f"
                          % (evt, won, sum(1 for p in mine if p["win"]),
                             len(mine), sum(p["pnl"] for p in mine)))

            # ---- PRICE the open races ----------------------------------
            for evt, e in sorted(events.items()):
                cs = int(e["close"])
                tau = cs - int(now)
                if not (TAU_LO <= tau <= TAU_HI + SUBSCRIBE_LEAD):
                    continue
                fresh = [t for t in e["legs"].values() if t not in watched]
                if fresh:
                    watched.update(fresh)
                    try:
                        book.subscribe(fresh)
                        rec("subscribe", event=evt, tickers=fresh, tau=tau)
                    except Exception as ex:                   # noqa: BLE001
                        rec("error", where="subscribe", err=str(ex)[:200])
                if not (TAU_LO <= tau <= TAU_HI):
                    continue

                rets = {}
                why = None
                for coin, iid in COINS.items():
                    with idx.lock:
                        ticks = dict(idx.ticks.get(iid) or {})
                    sec, spot, iage = idx.spot(iid)
                    if spot is None or iage is None or iage > MAX_INDEX_AGE_S:
                        why = "stale_index:%s" % coin
                        break
                    o = open_twap(ticks, cs - WINDOW)
                    if not o:
                        # NOT an absence of edge: the opening minute is
                        # [close-960, close-900), so a process that started
                        # after it can never evaluate this race at all.
                        why = "no_open_window:%s" % coin
                        break
                    mu = close_mu(ticks, cs, int(now), spot)
                    if mu is None:
                        why = "no_close_forecast:%s" % coin
                        break
                    rets[coin] = mu / o
                if why or len(rets) != 5:
                    key = (evt, why or "incomplete")
                    if key not in seen_why:
                        seen_why.add(key)
                        rec("cannot_evaluate", event=evt, tau=tau,
                            why=why or "incomplete", have=sorted(rets),
                            close_s=cs)
                    continue

                g = M.gaps(rets)
                for coin, gap in sorted(g.items(), key=lambda kv: -abs(kv[1])):
                    tkr = e["legs"][coin]
                    side, worth = price_leg(table, tau, gap * 1e4)
                    band = band_of(tau)
                    if band is None or (evt, tkr, side, band) in done_band:
                        continue
                    if a.one_per_race_band and (evt, band) in race_band_done:
                        continue
                    g3 = gate_arm3(tau, gap * 1e4, None, a.tau_max,
                                   a.min_gap_bp, a.min_price)
                    if g3:
                        if g3 != "outside_tau_max":
                            key = (evt, coin, g3)
                            if key not in seen_why:
                                seen_why.add(key)
                                rec("no_trade", event=evt, coin=coin,
                                    ticker=tkr, tau=tau, side=side, why=g3,
                                    gap_bp=round(gap * 1e4, 4))
                        continue
                    b = book.best(tkr)
                    bad = None
                    if not b:
                        bad = "no_book"
                    elif b.get("suspect"):
                        bad = "book_suspect"
                    elif b.get("age_ms") is None:
                        bad = "book_no_age"
                    elif b["age_ms"] > MAX_BOOK_AGE_MS:
                        bad = "book_stale"
                    if bad:
                        key = (evt, coin, bad)
                        if key not in seen_why:
                            seen_why.add(key)
                            rec("no_trade", event=evt, coin=coin, ticker=tkr,
                                tau=tau, side=side, why=bad,
                                gap_bp=round(gap * 1e4, 4))
                        continue
                    ask = b.get("yes_ask") if side == "yes" else b.get("no_ask")
                    asz = (b.get("yes_ask_size") if side == "yes"
                           else b.get("no_ask_size"))
                    edge = None
                    if worth is None:
                        # The table has never seen a gap like this at this tau.
                        # STAND ASIDE at any price -- this is not the same as
                        # a 50/50, and treating it as one is what made cheap
                        # legs look like free money.
                        bad = "no_model"
                    elif not ask or not asz:
                        bad = "no_offer"
                    elif ask > PRICE_CEILING + 1e-9:
                        bad = "above_ceiling"
                    elif gate_arm3(tau, gap * 1e4, float(ask), a.tau_max,
                                   a.min_gap_bp, a.min_price):
                        bad = "below_min_price"
                    else:
                        edge = net_edge(worth, float(ask))
                        if edge < a.min_edge:
                            bad = "thin_edge"
                    if bad:
                        key = (evt, coin, bad)
                        if key not in seen_why:
                            seen_why.add(key)
                            rec("no_trade", event=evt, coin=coin, ticker=tkr,
                                tau=tau, side=side, why=bad,
                                gap_bp=round(gap * 1e4, 4),
                                worth=(None if worth is None
                                       else round(worth, 6)),
                                ask=(float(ask) if ask else None),
                                ask_size=(float(asz) if asz else None),
                                edge=(None if edge is None
                                      else round(edge, 6)))
                        continue
                    # SUPPLY, not arithmetic, caps the size. buyable() walks
                    # the ladder to our limit; the touch alone once cost the
                    # live bot four fifths of an available book (A35).
                    try:
                        have = book.buyable(tkr, side, PRICE_CEILING)
                    except Exception:                        # noqa: BLE001
                        have = float(asz)
                    take = take_size(a.size, have, taken[(evt, tkr, side)])
                    if take <= 0:
                        key = (evt, coin, "book_already_ours")
                        if key not in seen_why:
                            seen_why.add(key)
                            rec("no_trade", event=evt, coin=coin, ticker=tkr,
                                tau=tau, side=side, why="book_already_ours",
                                buyable=have, held=taken[(evt, tkr, side)])
                        continue
                    try:
                        lad = book.depth(tkr, "no" if side == "yes" else "yes", 60)
                        ladder = [[round(1.0 - float(p), 4), float(s)]
                                  for p, s in (lad or [])]
                    except Exception:                        # noqa: BLE001
                        ladder = None
                    pos = {"event": evt, "coin": coin, "ticker": tkr,
                           "side": side, "price": float(ask), "size": take,
                           "tau": tau, "worth": round(worth, 6),
                           "gap_bp": round(gap * 1e4, 4),
                           "edge": round(edge, 6), "band": band}
                    fills.append(pos)
                    done_band.add((evt, tkr, side, band))
                    race_band_done.add((evt, band))
                    taken[(evt, tkr, side)] += take
                    rec("fill", assumed=True, ask_size=float(asz),
                        buyable=float(have or 0), ladder=ladder,
                        returns={k: round(v, 8) for k, v in rets.items()},
                        **pos)
                    print("  PAPER  %-30s %-4s %-3s %d @ %.0fc  tau %2d  "
                          "gap %+7.2fbp  worth %.4f  edge %+.2fc"
                          % (evt[-12:], coin, side.upper(), take, 100 * ask,
                             tau, gap * 1e4, worth, 100 * pos["edge"]))
            time.sleep(0.25)
    finally:
        done = [p for p in fills if "win" in p]
        rec("end", fills=len(fills), settled=len(done),
            won=sum(1 for p in done if p["win"]),
            pnl=round(sum(p["pnl"] for p in done), 4))
        try:
            book.stop()
        except Exception:                                    # noqa: BLE001
            pass
        idx.stop()
        logf.close()
    done = [p for p in fills if "win" in p]
    print("\n  %d paper positions, %d settled, %d won, $%+.2f"
          % (len(fills), len(done), sum(1 for p in done if p["win"]),
             sum(p["pnl"] for p in done)))
    print("  Every price above was an offer we SAW, not one we got. Winning "
          "the fill is assumed and no paper arm can test it.")
    print("  log %s" % os.path.abspath(logpath))
    return 0


if __name__ == "__main__":
    sys.exit(main())
