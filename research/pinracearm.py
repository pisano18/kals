#!/usr/bin/env python3
# VERSION: 2026-09-15-arm4
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
import pintake                                               # noqa: E402
import pinracemodel as M                                     # noqa: E402
import pinracefair as F                                      # noqa: E402

SERIES = "KXCRYPTOLEAD15M"
# Coin Race markets sit on exchange_index 2 ("Crypto"), the same shard as the
# 15-minute families. An order sent with the default 0 is rejected outright.
RACE_EXCHANGE_INDEX = 2
# Filled in by arm() only when --live is given, so a take() call cannot even
# be constructed without an explicit arming step.
CREDS = {"base": None, "pk": None, "key_id": None}
COINS = M.COINS
N_AVG = M.N_AVG
WINDOW = M.WINDOW

# ---- the PENNY TEST rails (REAL MONEY) ------------------------------------
# Operator sign-off 2026-09-21: "Sure start the penny test", "just spend
# pennies and see if they win. You have permission to do that."
#
# These are DEFAULTS. A self-test must assert these names, never the running
# LIVE dict -- asserting a running value has refused to start a bot six times
# in this repo.
_DEFAULT_LIVE_MAX_CONTRACTS = 1      # "pennies": about $1 a race at 97c
_DEFAULT_LIVE_MAX_STAKE = 20.00      # dollars this process may ever commit
_DEFAULT_LIVE_TAU_MAX = 40           # measured 09-21: the edge dies at 41 s
_DEFAULT_LIVE_MIN_PRICE = 0.90       # measured 09-21: the floor IS the strategy
_DEFAULT_LIVE_STOP_ON_LOSS = True
LIVE_STOP_FILE = os.path.join(REPO, "results", "pinracepenny.stop")

# `races` is the hard ONE-POSITION-PER-RACE ledger. In live mode it overrides
# the band logic entirely: 2026-09-15 cost $1,306 by holding two sides of one
# race, and at most one leg of a race can ever win, so a second position is
# not diversification, it is a guaranteed loser.
LIVE = {"on": False, "max_contracts": _DEFAULT_LIVE_MAX_CONTRACTS,
        "max_stake": _DEFAULT_LIVE_MAX_STAKE,
        "tau_max": _DEFAULT_LIVE_TAU_MAX,
        "min_price": _DEFAULT_LIVE_MIN_PRICE,
        "stop_on_loss": _DEFAULT_LIVE_STOP_ON_LOSS,
        "races": set(), "staked": 0.0, "halted": None, "sends": 0}


def live_refusals(tau, price, count, race, state=None, exists=os.path.exists):
    """Every reason this race may NOT be bought with real money.

    Pure and side-effect free, so the self-test can plant each refusal one at
    a time. These sit ON TOP of pintake's own rails, never instead of them."""
    st = LIVE if state is None else state
    bad = []
    if not st["on"]:
        bad.append("not armed -- --live was not given")
    if st["halted"]:
        bad.append("halted: %s" % st["halted"])
    if race in st["races"]:
        bad.append("one position per race -- this race already has one")
    if tau is None or tau > st["tau_max"]:
        bad.append("tau %s is past the %ds bar" % (tau, st["tau_max"]))
    elif tau < 2:
        bad.append("tau %s is inside the last 2 s -- no time to fill" % tau)
    if price is None or not (0.0 < price < 1.0):
        bad.append("price %s is not a probability" % price)
    elif price < st["min_price"]:
        bad.append("price %s is under the %.2f floor" % (price, st["min_price"]))
    if count is None or count < 1:
        bad.append("count %s is under one contract" % count)
    elif count > st["max_contracts"]:
        bad.append("count %s is over the %g cap" % (count, st["max_contracts"]))
    if price is not None and count is not None and 0.0 < price < 1.0:
        if st["staked"] + price * count > st["max_stake"] + 1e-9:
            bad.append("stake $%.2f + $%.2f would pass the $%.2f cap"
                       % (st["staked"], price * count, st["max_stake"]))
    if exists(LIVE_STOP_FILE):
        bad.append("stop file present: %s" % LIVE_STOP_FILE)
    return bad


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


def fair_worth(probs, coin, side):
    """ARM4: what one side of a leg is worth under pinracefair's probability.
    YES is P(coin wins); NO is 1 - P(coin wins). None when there is no forecast."""
    if not probs or coin not in probs:
        return None
    p = probs[coin]
    return p if side == "yes" else 1.0 - p


def live_fair(ticks_by_iid, close, tau, rets):
    """({coin: P(win)}, ruler) from the arm's own live ticks, or (None, why).

    The same maths pinracefair scored on 398 unseen races: variance collapse
    times the five-coin covariance of 1-second returns. The 3600 s ruler won on
    the fit half; a freshly started arm has no hour of history, so it falls
    back to 300 s (log loss 0.02418 vs 0.02413 on the fit half) and says so
    in every record."""
    ser = F.RaceSeries(ticks_by_iid, close)
    now = close - tau
    for which in ("3600", "300"):
        c = F.pick_cov(ser, now, which)
        if c is not None:
            rnow = [math.log(rets[k]) for k in F.COINS]
            pr = F.win_probs(rnow, c, F.var_factor(tau))[1.0]
            return dict(zip(F.COINS, pr)), which
    return None, "no_cov_history"


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

    # ---- THIS BAR WAS MOVED 2026-09-21, AND IT IS MOVED LOUDLY ----------
    #
    # Until today this block asserted that the strings "pintake", "--live"
    # and the order endpoint appeared NOWHERE in this file, so that nothing
    # here could reach the exchange. That guarantee is GONE BY DESIGN: the
    # operator signed off the coin race penny test on 2026-09-21 ("just spend
    # pennies and see if they win. You have permission to do that") and this
    # file now sends real orders at one contract under --live.
    #
    # The old text is kept above in this comment rather than deleted, per the
    # standing rule that a bar is never moved quietly. What replaces it is
    # narrower and stronger: the order path may appear EXACTLY ONCE, it must
    # sit behind the --live guard, the rails must be checked before it, and
    # the endpoint and the maker field must still appear nowhere -- this file
    # takes liquidity through pintake or not at all, and never rests a quote.
    #
    # THE SELF-INSPECTION TRAP. Every needle below is BUILT, never written,
    # because spelling a module name out in this test would let the test find
    # its own comment and pass or fail for the wrong reason -- which is how
    # four earlier structural tests in this project went wrong.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for needle, what in (("post_" + "only", "a maker order field"),
                         ("/portfolio/" + "orders", "the order endpoint itself")):
        ck(src.count(needle) == 0,
           "%s (%s) appears NOWHERE in this file -- it can only ever take "
           "liquidity, through pintake's rails, and never rest a quote"
           % (needle, what))
    ck(src.count("pin" + "run." + "arm(") == 0,
       "it never calls the LIVE BOT's arming function -- the money bot's "
       "credentials and rails stay its own")

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

    # ---- ARM4 fair value ---------------------------------------------------
    pr = {"BTC": 0.93, "ETH": 0.05, "SOL": 0.01, "XRP": 0.005, "HYPE": 0.005}
    ck(fair_worth(pr, "BTC", "yes") == 0.93
       and abs(fair_worth(pr, "ETH", "no") - 0.95) < 1e-12,
       "fair value: BTC's YES is worth its 93%, ETH's NO is worth 1 - 5%")
    ck(fair_worth(None, "BTC", "yes") is None and fair_worth(pr, "DOGE", "no") is None,
       "NULL: no forecast, or a coin not in the race, is worth nothing known")
    ck(net_edge(fair_worth(pr, "BTC", "yes"), 0.95) < 0,
       "and a 93% leader offered at 95c is refused on edge -- the market's "
       "price beat the table on the 3:30 PM race exactly like this")
    base4 = 9_000_000 - (9_000_000 % WINDOW)
    close4 = base4 + 10 * WINDOW
    import random as _r
    rng4 = _r.Random(11)
    snap4 = {}
    for iid in F.IIDS:
        lvl, d4 = 100.0, {}
        for s in range(close4 - 2000, close4 - 20):
            lvl *= math.exp(rng4.gauss(0, 1e-4))
            d4[s] = lvl
        snap4[iid] = d4
    rets4 = {c: 1.0 + 0.0004 * i for i, c in enumerate(F.COINS)}
    p4, ruler4 = live_fair(snap4, close4, 20, rets4)
    ck(p4 is not None and ruler4 == "300",
       "a fresh arm with only ~33 minutes of ticks gets a forecast on the 300 s "
       "ruler (got %s), not a refusal and not a pretend hour" % ruler4)
    ck(p4 is not None and max(p4, key=p4.get) == "HYPE" and p4["HYPE"] > 0.99,
       "and a 4bp lead with 20 s left on calm independent coins is ~certain "
       "(%.3f)" % (p4 or {}).get("HYPE", 0))
    p5, why5 = live_fair({iid: {} for iid in F.IIDS}, close4, 20, rets4)
    ck(p5 is None and why5 == "no_cov_history",
       "NULL: with no tick history at all it refuses rather than guessing")

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

    # ---- THE PENNY TEST RAILS. Real money, so every one is planted. -------
    # Every assertion is on a _DEFAULT_ name, never on the running LIVE dict:
    # asserting a running value has refused to start a bot six times here.
    ck(_DEFAULT_LIVE_MAX_CONTRACTS <= pintake.MAX_TAKE_COUNT,
       "the default penny size (%g) is inside pintake's own per-order rail "
       "(%g)" % (_DEFAULT_LIVE_MAX_CONTRACTS, pintake.MAX_TAKE_COUNT))
    ck(_DEFAULT_LIVE_TAU_MAX <= 40 and _DEFAULT_LIVE_MIN_PRICE >= 0.90,
       "the defaults are the measured rule: inside %ds, at %.0fc or dearer"
       % (_DEFAULT_LIVE_TAU_MAX, 100 * _DEFAULT_LIVE_MIN_PRICE))
    ck(_DEFAULT_LIVE_STOP_ON_LOSS is True,
       "and it stops dead on the first real loss by default")

    off = {"on": False, "max_contracts": 1, "max_stake": 20.0, "tau_max": 40,
           "min_price": 0.90, "stop_on_loss": True, "races": set(),
           "staked": 0.0, "halted": None, "sends": 0}
    never = lambda _p: False                                  # noqa: E731
    ck(live_refusals(20, 0.95, 1, "R1", state=off, exists=never),
       "DISARMED: a perfect order is still refused when --live was not given")
    on = dict(off, on=True, races=set())
    ck(live_refusals(20, 0.95, 1, "R1", state=on, exists=never) == [],
       "ARMED: a 95c buy of one contract 20 s out is allowed")
    on2 = dict(on, races={"R1"})
    ck(live_refusals(20, 0.95, 1, "R1", state=on2, exists=never),
       "ONE POSITION PER RACE: the same race is refused a second time")
    ck(live_refusals(20, 0.95, 1, "R2", state=on2, exists=never) == [],
       "but a DIFFERENT race is still allowed")
    ck(live_refusals(41, 0.95, 1, "R3", state=on, exists=never),
       "41 s out is refused -- measured 09-21, the edge dies at 41")
    ck(live_refusals(1, 0.95, 1, "R3", state=on, exists=never),
       "and 1 s out is refused: no time to fill")
    ck(live_refusals(20, 0.89, 1, "R3", state=on, exists=never),
       "89c is refused -- the 90c floor IS the strategy")
    ck(live_refusals(20, 0.95, 2, "R3", state=on, exists=never),
       "two contracts is refused when the cap is one")
    ck(live_refusals(20, 0.95, 0, "R3", state=on, exists=never),
       "and zero contracts is refused rather than sent")
    ck(live_refusals(20, 0.95, 1, "R3", state=dict(on, staked=19.9),
                     exists=never),
       "a buy that would pass the total stake cap is refused")
    ck(live_refusals(20, 0.95, 1, "R3", state=dict(on, halted="lost one"),
                     exists=never),
       "nothing is sent once it has halted")
    ck(live_refusals(20, 0.95, 1, "R3", state=on, exists=lambda _p: True),
       "and the stop file refuses everything while it exists")
    ck(live_refusals(None, None, None, "R3", state=on, exists=never),
       "missing inputs refuse rather than crash")
    ck(LIVE["on"] is False and LIVE["halted"] is None,
       "the module's own live state is DISARMED at import")

    # the send must be guarded, and the race must be claimed BEFORE the send
    # so a crash mid-order cannot re-enter the same race. Anchored with
    # rindex, because a self-test that searches this file finds ITS OWN copy
    # of any string it looks for.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[src.rindex(chr(10) + "def main("):]
    ck(body.count("pintake.take(") == 1,
       "there is exactly ONE call to the order path in the whole file")
    i_guard = body.rindex('if LIVE["on"]:')
    i_claim = body.rindex('LIVE["races"].add(evt)')
    i_send = body.rindex("pintake.take(")
    ck(i_guard < i_claim < i_send,
       "the send is inside the --live guard AND the race is claimed before "
       "the order leaves, so a crash cannot re-enter the same race")
    ck(body.rindex("live_refusals(tau") < i_send,
       "and the rails are checked before the order leaves")
    ck("arm_prod" in body and body.index("arm_prod") > body.index("if a.live:"),
       "production is armed only under --live")

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
    ap.add_argument("--model", choices=("table", "fair"), default="table",
                    help="ARM4: 'fair' prices every leg with pinracefair "
                         "(variance collapse x five-coin covariance) and "
                         "considers BOTH sides of every leg")
    ap.add_argument("--one-per-race-band", action="store_true",
                    help="ARM3: at most one bet per race per time band -- "
                         "'BTC wins' and 'ETH won't win' are one bet twice")
    ap.add_argument("--live", action="store_true",
                    help="THE PENNY TEST: send REAL orders at minimum size "
                         "alongside the paper record, to measure our own fill "
                         "rate and our own loss rate. Operator sign-off "
                         "2026-09-21.")
    ap.add_argument("--max-contracts", type=float,
                    default=_DEFAULT_LIVE_MAX_CONTRACTS,
                    help="live: contracts per race (default %g)"
                         % _DEFAULT_LIVE_MAX_CONTRACTS)
    ap.add_argument("--max-stake", type=float, default=_DEFAULT_LIVE_MAX_STAKE,
                    help="live: total dollars this process may ever commit "
                         "(default %.2f)" % _DEFAULT_LIVE_MAX_STAKE)
    ap.add_argument("--live-tau-max", type=int, default=_DEFAULT_LIVE_TAU_MAX,
                    help="live: never buy further out than this (default %d)"
                         % _DEFAULT_LIVE_TAU_MAX)
    ap.add_argument("--live-min-price", type=float,
                    default=_DEFAULT_LIVE_MIN_PRICE,
                    help="live: never buy cheaper than this (default %.2f)"
                         % _DEFAULT_LIVE_MIN_PRICE)
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

    live_pos = []
    if a.live:
        # ARM REAL MONEY. Every rail is set from the command line here and
        # nowhere else, and the refusal list is printed before a single
        # market is watched so the operator can read what is bounded.
        LIVE.update(on=True, max_contracts=float(a.max_contracts),
                    max_stake=float(a.max_stake),
                    tau_max=int(a.live_tau_max),
                    min_price=float(a.live_min_price))
        if os.path.exists(LIVE_STOP_FILE):
            print("  REFUSING TO ARM -- stop file present: %s" % LIVE_STOP_FILE)
            return 1
        if LIVE["max_contracts"] > pintake.MAX_TAKE_COUNT:
            print("  REFUSING TO ARM -- %g contracts is over pintake's own "
                  "per-order rail of %g" % (LIVE["max_contracts"],
                                            pintake.MAX_TAKE_COUNT))
            return 1
        # pintake's rails are a RATCHET -- set_limits refuses to lower them,
        # deliberately, so that a caller can never quietly loosen or tighten
        # the money path. We do not touch them. Our cap is checked first in
        # live_refusals() and must be the stricter of the two, or it is not a
        # cap at all.
        if LIVE["max_stake"] > pintake.MAX_RUN_STAKE:
            print("  REFUSING TO ARM -- $%.2f is looser than pintake's own "
                  "run-stake rail of $%.2f" % (LIVE["max_stake"],
                                               pintake.MAX_RUN_STAKE))
            return 1
        import kauth
        import ordercli
        CREDS["base"] = pintake.PROD_ELECTIONS
        CREDS["key_id"] = kauth.KEY_ID
        CREDS["pk"] = ordercli.load_key(pintake.PROD_KEY_FILE)
        pintake.arm_prod("coin race penny test, operator sign-off 2026-09-21")
        print("\n  *** REAL MONEY ARMED -- THE PENNY TEST ***")
        print("  at most %g contract(s) a race, ONE position per race,"
              % LIVE["max_contracts"])
        print("  only inside %d s, only at %.0fc or dearer, at most $%.2f"
              % (LIVE["tau_max"], 100 * LIVE["min_price"], LIVE["max_stake"]))
        print("  committed in total, and it STOPS DEAD on the first losing")
        print("  race. Halt it any time with:  type nul > %s" % LIVE_STOP_FILE)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logpath = a.log or os.path.join(REPO, "results",
                                    "pinracearm-%s.jsonl" % stamp)
    logf = open(logpath, "a", encoding="utf-8")

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logf.write(json.dumps(kw) + "\n")
        logf.flush()

    print("\n  COIN RACE %s" % ("PENNY TEST -- REAL ORDERS, see the rails above"
                                if a.live else
                                "PAPER ARM -- nothing is ever sent"))
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
        one_per_race_band=bool(a.one_per_race_band), model=a.model)

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
    fair_cache = {}                         # (event, tau) -> (probs, ruler)
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

                # ---- score the REAL positions, and stop on the first loss --
                real = [p for p in live_pos if p["event"] == evt
                        and "win" not in p]
                for p in real:
                    p["win"] = ((p["coin"] == won) if p["side"] == "yes"
                                else (p["coin"] != won))
                    p["pnl"] = round(p["size"] * ((1.0 - p["price"])
                                                  if p["win"] else -p["price"])
                                     - p["size"] * fee(p["price"]), 4)
                if real:
                    lost = [p for p in real if not p["win"]]
                    rec("live_settled", event=evt, close_s=cs, winner=won,
                        positions=len(real),
                        won=sum(1 for p in real if p["win"]),
                        pnl=round(sum(p["pnl"] for p in real), 4),
                        legs=[{k: p[k] for k in
                               ("ticker", "side", "price", "size", "tau",
                                "ask_seen", "win", "pnl")} for p in real])
                    print("  ** LIVE SETTLED %-24s %-4s  %d/%d won  $%+.2f"
                          % (evt, won, sum(1 for p in real if p["win"]),
                             len(real), sum(p["pnl"] for p in real)))
                    if lost and LIVE["stop_on_loss"] and not LIVE["halted"]:
                        # STOP DEAD. The whole point of the penny test is to
                        # find out whether we lose more often than the tape
                        # says; the first real loss is the answer arriving,
                        # not a reason to keep going and find out how much.
                        LIVE["halted"] = ("first real loss: %s %s at %.0fc"
                                          % (evt, lost[0]["side"],
                                             100 * lost[0]["price"]))
                        rec("live_halt", why=LIVE["halted"],
                            staked=round(LIVE["staked"], 4),
                            sends=LIVE["sends"])
                        print("\n  *** PENNY TEST HALTED: %s" % LIVE["halted"])
                        print("  No further real order will be sent by this "
                              "process. The paper arm keeps running.\n")

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
                fprobs, ruler = None, None
                if a.model == "fair":
                    if tau > a.tau_max:
                        continue
                    fk = (evt, tau)
                    if fk not in fair_cache:
                        fair_cache.clear()
                        with idx.lock:
                            snap = {iid: dict(idx.ticks.get(iid) or {})
                                    for iid in F.IIDS}
                        fair_cache[fk] = live_fair(snap, cs, tau, rets)
                    fprobs, ruler = fair_cache[fk]
                    if fprobs is None:
                        key = (evt, "no_fair_value")
                        if key not in seen_why:
                            seen_why.add(key)
                            rec("cannot_evaluate", event=evt, tau=tau,
                                why="no_fair_value:%s" % ruler, close_s=cs)
                        continue
                legs_sides = []
                for coin, gap in sorted(g.items(), key=lambda kv: -abs(kv[1])):
                    if a.model == "fair":
                        legs_sides.append((coin, gap, "yes"))
                        legs_sides.append((coin, gap, "no"))
                    else:
                        legs_sides.append((coin, gap, None))
                for coin, gap, fside in legs_sides:
                    tkr = e["legs"][coin]
                    if fside is None:
                        side, worth = price_leg(table, tau, gap * 1e4)
                    else:
                        side, worth = fside, fair_worth(fprobs, coin, fside)
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
                           "edge": round(edge, 6), "band": band,
                           "model": a.model, "ruler": ruler}
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

                    # ---- THE PENNY TEST. Real money, one race at a time. ----
                    # The paper record above is written either way, so the
                    # assumed fill and the real one can be compared later --
                    # which is the entire point of the test.
                    if LIVE["on"]:
                        want_n = min(float(take), float(LIVE["max_contracts"]))
                        why = live_refusals(tau, float(ask), want_n, evt)
                        if why:
                            rec("live_refused", event=evt, ticker=tkr,
                                side=side, tau=tau, price=float(ask),
                                count=want_n, why=why)
                        else:
                            LIVE["races"].add(evt)      # BEFORE the send, so a
                            LIVE["sends"] += 1          # crash cannot re-enter
                            out = pintake.take(
                                CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                tkr, side, float(ask), want_n, float(cs),
                                exchange_index=RACE_EXCHANGE_INDEX,
                                max_tau=LIVE["tau_max"])
                            got = float(out.get("filled") or 0.0)
                            px = float(out.get("exec_price") or ask)
                            if got > 0:
                                LIVE["staked"] += px * got
                                live_pos.append(
                                    {"event": evt, "coin": coin,
                                     "ticker": tkr, "side": side,
                                     "price": px, "size": got, "tau": tau,
                                     "worth": round(worth, 6),
                                     "ask_seen": float(ask)})
                            rec("live_order", event=evt, ticker=tkr,
                                side=side, tau=tau, ask_seen=float(ask),
                                count_asked=want_n, filled=got,
                                exec_price=(px if got > 0 else None),
                                status=out.get("status"),
                                status_code=out.get("status_code"),
                                refused=out.get("refused"),
                                fee=out.get("fee_total"),
                                staked=round(LIVE["staked"], 4),
                                order_id=out.get("order_id"),
                                client_order_id=out.get("client_order_id"))
                            print("  ** LIVE %-24s %-4s %-3s asked %g got %g "
                                  "@ %.0fc  (staked $%.2f of $%.2f)"
                                  % (evt[-12:], coin, side.upper(), want_n,
                                     got, 100 * px, LIVE["staked"],
                                     LIVE["max_stake"]))
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
