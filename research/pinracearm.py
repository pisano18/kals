#!/usr/bin/env python3
# VERSION: 2026-09-24-tie1
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
                     and marks every paper position won, lost, or TIED (a
                     two-way tie pays 50c to both coins; the index's 3-decimal
                     rule names one). REAL legs are scored from Kalshi's own
                     result on results/kalshi_ledger.json first, and wait for
                     it: the index cannot tell a tie from a win inside 0.75 bp
                     (see settle_race). No chance of scoring the wrong race.
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
import fnmatch
import inspect
import io
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
import pinledger                                             # noqa: E402
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
_DEFAULT_LIVE_MAX_CONTRACTS = 1      # "pennies": about $1 a leg at 97c
_DEFAULT_LIVE_MAX_STAKE = 20.00      # dollars this process may ever commit
_DEFAULT_LIVE_TAU_MAX = 60           # the EARLIEST we may look (see CONFIRM)
_DEFAULT_LIVE_CONFIRM = 5            # seconds the same leg must keep qualifying
_DEFAULT_LIVE_CLOCK_TAU = 20         # fire anyway once the clock runs down
_DEFAULT_LIVE_MIN_PRICE = 0.90       # 80c on the tape; REAL fills said 90c, see below
_DEFAULT_LIVE_MAX_LEGS = 5           # one YES plus a NO on every other coin
_DEFAULT_LIVE_STOP_ON_LOSS = True
_DEFAULT_LIVE_MAX_DROP = 0.02        # fresh ask this far under the one seen = refused
# THE RACE-LEVEL z FLOOR (2026-09-22). OFF by default, so the running live
# argv decides exactly what it decides today. See z_refusal() for the rule and
# race_zscores() for the number.
_DEFAULT_MIN_Z = 0.0                 # 0 = off. 3.0 is the arm's value.
_DEFAULT_MIN_Z_TAU = 30              # the floor applies only PAST this tau
# v-race-snowball (2026-10-11). The operator: "I don't want to cap any growth. I want these to grow
# unchecked and snowball into bigger and bigger days ... Every account should be automatically increasing
# bets with their bank." OFF by default, so the running live argv (--max-contracts 20 --max-stake 40)
# sizes exactly as it does today. See bank_sizes() / bank_tick() for the rule.
_DEFAULT_CONTRACTS_PER_BANK = 0.0    # 0 = off: contracts a leg stay --max-contracts
_DEFAULT_STAKE_PER_BANK = 0.0        # 0 = off: the open-stake cap stays --max-stake
_DEFAULT_BANK_REREAD_S = 300         # the bank is re-read at most this often, and only between races
LIVE_STOP_FILE = os.path.join(REPO, "results", "pinracepenny.stop")

# pinday.RACE_PAT -- the glob the operator's DAY TOTAL reads. `load_race()`
# turns every `live_settled` leg's `pnl` under this pattern into real money.
# --paper-live writes `live_settled` records too (that is how its races get
# scored), so a paper log NAMED like a money log would put invented dollars
# into the money report. pinday also skips records flagged `paper` now, but
# this rail does not depend on that other file staying fixed: a name the glob
# cannot pick up is a rail, a field somebody has to keep reading is a promise.
PINDAY_RACE_PAT = "pinrace*-live*.jsonl"

# 2026-09-22: THE FLOOR GOES BACK TO 90c, AND EVERY SEND RE-READS THE BOOK.
#
# Real fills, 2026-09-21, one contract each, 15 races:
#
#     filled at 94-98c    24 legs    24 won
#     filled at 85-86c     2 legs     0 won    -$0.86, -$0.87
#
# The tape table below rated sub-90c legs at 1.0-1.4% losing. Our own fills
# lost both. It is the pin gate's tape-vs-live gap again (tape 0.11%, live
# 3.4%): the tape's population is "an offer was there", ours is "someone
# sold it to us". The operator: "2 losses in 15 is not too few, something is
# wrong with it." Both losses were near-tied races (gap 3.7 and 5.6 bp) at
# tau 40-41, where the market was right and the model was not.
#
# CORRECTED THE SAME NIGHT (map investigator 08, from the tape to the
# millisecond): the first loss was NOT a stale book. Our price list matched
# the exchange's book 0.16 s before the send; the 93c was a ~150 ms spike
# (the prior 10 s ranged 66-90c), and a faster maker moved its quote between
# our send and our fill -- we were picked off. The REST re-read below cannot
# stop that: on its first live order (09-22 06:29Z) it read 97c, passed, and
# the fill came at 91c. It stays as a cheap guard against a genuinely stale
# book and it LOGS `fresh_ask`, but the protection is WHEN we bet: every race
# loss since 09-21, real and paper, came 40-60 s out, and 0 of 88 paper races
# with a 90c+ bet inside 30 s lost. Hence --live-tau-max 30 (v-race30).

# WHY MORE THAN ONE LEG, WHEN 2026-09-15 COST $1,306 BY HOLDING TWO.
#
# The 09-15 arm held positions that CONTRADICTED each other -- YES and NO on
# the same ticker, and two YES legs in one race. At most one leg of a race can
# win, so those are not diversification, they are a guaranteed loser, and at
# 90c+ a contradictory pair costs more than the dollar it can ever pay.
#
# "BTC wins" and "XRP does not win" do not contradict. They are both true
# whenever BTC wins, and the second is true whenever ETH, SOL or HYPE wins
# too. So the rule is CONSISTENCY, not a count of one:
#
#     at most ONE yes leg, NO legs only on OTHER coins, never a coin twice.
#
# THE ORDER OF PREFERENCE is the operator's, 2026-09-21: "if you have a
# confident yes, then get that then try to get your cheapest nos on every
# single other coin you can. If you have a confident no but not a confident
# yes, then get all the confident nos you can get."
#
# Measured on 25 days of resting book, tau <= 40, cap 100, forecast staled two
# seconds, taking the YES first and then the cheapest NOs on other coins:
#
#     floor    $/day    losing legs     c/contract
#      75c     41.58        2.1%          +2.16c
#      80c     45.11        1.4%          +2.47c     <- the peak, both columns
#      85c     37.14        1.0%          +2.16c
#      90c     26.06        0.5%          +1.71c
#
# WHY 80c AND NOT LOWER. Run the same rule against a FRESH forecast instead of
# one staled two seconds and the difference is how much of the edge is
# split-second timing we will not have in time:
#
#     75c   $101.32 -> $41.58   loses 59%
#     80c    $74.85 -> $45.11   loses 40%
#     85c    $58.67 -> $37.14   loses 37%
#     90c    $33.34 -> $26.06   loses 22%
#
# 80c gives up no more of itself than 85c does and pays a fifth more. At 75c
# the contamination jumps to 59% and the losing-leg rate doubles. So 80c is
# the lowest floor the measurement actually supports.
#
# HOW MANY LEGS. Going from one leg to two is the whole gain ($28.95 ->
# $36.50 a day at 85c); legs three, four and five add $0.64 between them,
# because most races simply do not offer a third leg above the floor. The cap
# is 5 so nothing is left on the table, not because 5 is expected.
#
# ----------------------------------------------------------------------
# THE 09-21 LOSS, and why tau_max went 40 -> 20.
#
# The penny test's first loss: KXCRYPTOLEAD15M-26SEP210930, bought SOL NO at
# tau 40, SOL won, -$0.86 on one contract. Rebuilt from the index, HYPE and
# SOL ran neck and neck the whole way and the lead FLIPPED at tau ~32:
#
#     tau 60  HYPE 64%   tau 40  HYPE 95%  <- we fired here
#     tau 50  HYPE 72%   tau 35  HYPE 71%
#     tau 45  HYPE 78%   tau 30  SOL  64%  <- flipped
#                        tau 20  SOL 100%
#
# The 95% at tau 40 is an outlier against every neighbouring second, which
# all read 64-78%. We fired into a one-second spike in the model's own
# confidence. Four families of fix were measured on 25 days and NONE pays for
# itself -- each cuts good trades at least as fast as bad ones:
#
#     require the belief to have held N s earlier   bad rate flat, -$20-37/day
#     use the median of the last N reads            bad rate WORSE, -$21-32/day
#     refuse a belief that swung > X in 10 s        -1 bad race, -$0.52/day
#     refuse a belief spiking above its own median  -1 bad race, -$3.33/day
#
# What DOES work is not a gate at all -- it is WHEN we fire. Same rule, same
# floor, same legs, only the earliest second allowed:
#
#     tau <= 40   710 races   14 losing   1.97%   +4.21c   $52.20/day
#     tau <= 30   528 races   11 losing   2.08%   +2.36c   $21.42/day
#     tau <= 20   386 races    3 losing   0.78%   +5.24c   $31.20/day   <- this
#     tau <= 15   319 races    1 losing   0.31%   +5.44c   $21.65/day
#
# Waiting for tau 20 cuts losing races 4.5x, IMPROVES cents per contract, and
# keeps 60% of the money. In the race above, tau 20 read SOL 100% -- by then
# it was simply right. The operator's standing preference is variance
# reduction over expected value at the margin, and this is that trade twice
# over: fewer losses AND more per contract.
#
# THE EDGE BAR STAYS AT ZERO. Raising it makes the loss rate WORSE, not
# better (0c 1.97%, 1c 2.26%, 2c 5.36%, 3c 6.10%) -- the same cheap-leg cliff
# this product shows everywhere. A bigger apparent bargain is a warning.
#
# ----------------------------------------------------------------------
# CONFIRM-OR-CLOCK, the operator's idea, 2026-09-21: "once a confidence peaks
# you either watch for an additional amount of time to see if it's a quick
# spike or if it's really ascending, or you look at the time... and whichever
# comes first you use for your decision."
#
# It beats both of the fixed rules it replaces. Arm when a basket first
# qualifies; fire when the SAME anchor leg still qualifies `confirm` seconds
# later, or the moment tau reaches `clock_tau`, whichever comes first.
#
#     rule                      races  losing   rate    c/ct    $/day
#     tau <= 40 (the old one)     710      14   1.97%  +4.21c   52.20
#     tau <= 20 (the safe one)    386       3   0.78%  +5.24c   31.20
#     confirm 5s, clock 20        773       3   0.39%  +5.16c   48.28   <- this
#
# MORE races than either, the same three losses as the cautious rule spread
# over twice the races, and nearly all of the bold rule's money. The spike
# that cost us on 09-21 could not have fired: it held 95% for one second.
#
# 560 of the 773 fire on confirmation and 213 on the clock, so both halves
# earn their place. Swept: confirm 3s 0.59% / 4s 0.49% / 5s 0.39% / 6s 0.42%
# / 8s 0.47% / 10s 0.53%; clock floor 15 $34.38 / 20 $48.28 / 25 $44.51 (and
# 0.76% losing) / 30 $32.42 (1.34%). Both interior optima, neither on a
# boundary. Only 2 of 26 days end negative.
_DEFAULT_LIVE_STOP_ON_LOSS = True

# `races` maps event -> [(coin, side), ...] already held, so consistency can
# be checked against what is actually on the book, not against a count.
LIVE = {"on": False, "paper": False,
        "max_contracts": _DEFAULT_LIVE_MAX_CONTRACTS,
        "max_stake": _DEFAULT_LIVE_MAX_STAKE,
        "tau_max": _DEFAULT_LIVE_TAU_MAX,
        "min_price": _DEFAULT_LIVE_MIN_PRICE,
        "max_legs": _DEFAULT_LIVE_MAX_LEGS,
        "confirm": _DEFAULT_LIVE_CONFIRM,
        "clock_tau": _DEFAULT_LIVE_CLOCK_TAU,
        "stop_on_loss": _DEFAULT_LIVE_STOP_ON_LOSS,
        "max_drop": _DEFAULT_LIVE_MAX_DROP, "rolling": False,
        "max_losses": 1, "day_losses": 0, "loss_day": None, "halted_day": None,
        "races": {}, "armed": {}, "staked": 0.0, "halted": None, "sends": 0,
        # v-race-snowball: bank-scaled sizing, OFF unless --contracts-per-bank / --stake-per-bank > 0
        "contracts_per_bank": _DEFAULT_CONTRACTS_PER_BANK,
        "stake_per_bank": _DEFAULT_STAKE_PER_BANK,
        "bank_reread_s": _DEFAULT_BANK_REREAD_S,
        "fixed_contracts": _DEFAULT_LIVE_MAX_CONTRACTS, "fixed_stake": _DEFAULT_LIVE_MAX_STAKE,
        "bank": None, "bank_at": None}

# v-race40 (2026-09-30, operator: "increase the coin race size don't stop on one loss"): with --live-max-losses N > 1
# the live bot stops for the rest of the ET DAY after N losing races and trades again the next ET day. N = 1 (the
# default) is the old stop-dead-on-the-first-loss rule, which never expires. Size above pintake's shipped rails is
# allowed up to these ceilings of our own, raised through pintake.set_limits (printed, never silent).
RACE_MAX_CONTRACTS_CEILING = 100.0
RACE_MAX_STAKE_CEILING = 300.0

# --paper-live's own stake book. The rolling-stake release gives committed
# dollars back to a ledger; in paper mode it gives them back to THIS one, so
# pintake's ledger is never written to by a process that never sends.
PAPER_LEDGER = {"committed": 0.0}


def release_settled(state, ledger, legs):
    """ROLLING STAKE (--live-rolling-stake): give back what settled legs
    committed, in BOTH our cap (state["staked"]) and pintake's run cap
    (ledger["committed"]), the same `price * size` each fill added -- the
    release pinrun has done since its own leak (committed_for). Without it
    the $20 cap counts every bet the process has EVER placed: on 09-22 the
    penny test stopped itself at 11:59 ET after ~20 one-contract bets with
    nothing open. With it, the cap bounds what is OPEN at any moment, and the
    stop-on-first-loss rail still bounds the total. Returns dollars released."""
    amt = sum(float(p["price"]) * float(p["size"]) for p in legs)
    state["staked"] = max(0.0, float(state["staked"]) - amt)
    ledger["committed"] = max(0.0, float(ledger.get("committed", 0.0)) - amt)
    return amt


def book_ask(resp, side):
    """Best ask for buying `side`, from a REST /markets/{t}/orderbook body.

    Kalshi's REST book lists BIDS only, in dollars, ascending:
    {"orderbook_fp": {"yes_dollars": [["0.0700","2.00"],["0.1000","120.00"]],
                      "no_dollars":  [["0.7600","475.00"],["0.8000","120.00"]]}}
    A NO ask is 1 - the best YES bid, and a YES ask is 1 - the best NO bid.
    Checked against /markets on 2026-09-22: that body is yes ask 0.20, no ask
    0.90, exactly what the market quoted. None when nothing is offered."""
    if not isinstance(resp, dict):
        return None
    ob = resp.get("orderbook_fp")
    if not isinstance(ob, dict):
        return None
    other = ob.get("no_dollars" if side == "yes" else "yes_dollars") or []
    bids = []
    for lvl in other:
        try:
            px, sz = float(lvl[0]), float(lvl[1])
        except (TypeError, ValueError, IndexError):
            continue
        if sz > 0 and 0.0 < px < 1.0:
            bids.append(px)
    return round(1.0 - max(bids), 4) if bids else None


def fresh_refusal(fresh, seen, state=None):
    """None if the fresh REST ask agrees with the one we decided on, else why
    the send is refused. A buy fills at anything at or under its limit, so a
    price that collapsed under us would be BOUGHT -- this is the only place
    that can see it."""
    st = LIVE if state is None else state
    if fresh is None:
        return "fresh book unreadable or empty -- refused rather than guess"
    if fresh < st["min_price"] - 1e-9:
        return ("fresh ask %.0fc is under the %.0fc floor (saw %.0fc)"
                % (100 * fresh, 100 * st["min_price"], 100 * seen))
    if fresh < seen - st["max_drop"] - 1e-9:
        return ("fresh ask %.0fc is %.0fc under the %.0fc we decided on -- "
                "the market moved against us"
                % (100 * fresh, 100 * (seen - fresh), 100 * seen))
    return None


def arm_leg(armed, race, coin, side, tau):
    """Note that (coin, side) is qualifying in `race` at `tau`, and return the
    tau it FIRST qualified at.

    Arming is per leg, not per race: a race whose anchor flips from HYPE to
    SOL has not been holding a signal for five seconds, it has had two
    signals, and the clock must start again. That flip is exactly what cost
    the 09-21 race."""
    seen = armed.setdefault(race, {})
    if (coin, side) not in seen:
        seen[(coin, side)] = tau
    return seen[(coin, side)]


def disarm(armed, race, coin, side):
    """Forget that (coin, side) was ever qualifying in `race`, and hand back
    the tau it had been holding since. Its confirmation clock starts again
    from the next second it qualifies.

    ONE CALLER: the z refusal. `arm_leg` records the tau a leg FIRST qualified
    at and never clears it, so without this a leg that drops under the floor
    for a second and comes back still fires on its ORIGINAL clock. On the tape
    that single line is 1 loss in 554 early races against 0 in 366 -- the same
    lesson as the 09-21 spike: a confidence that holds for one second is not a
    signal. It is confined to the z gate on purpose; making every gate disarm
    would change how the other live rails behave, which is not what was
    measured.

    It fires on EVERY second the floor refuses, including seconds where some
    earlier rail (`above_ceiling`, `no_book`, `thin_edge`) answered first --
    `zmin` is race-level and index-only, so those rails say nothing about it.
    Serving the floor only on the seconds that reached the edge test would
    let a leg keep its original clock through the seconds its race was under
    the floor, and A_find F4 says a 99c ask during the qualifying seconds is
    the common case in this band. That is still ONE gate doing the
    disarming."""
    return armed.get(race, {}).pop((coin, side), None)


def confirm_refusal(first_tau, tau, state=None):
    """None if this leg may fire now, else why not.

    Fire when the leg has kept qualifying for `confirm` seconds, OR when the
    clock has run down to `clock_tau` -- whichever comes first."""
    st = LIVE if state is None else state
    if tau is None or first_tau is None:
        return "no arming record"
    if first_tau - tau >= st["confirm"]:
        return None
    if tau <= st["clock_tau"]:
        return None
    return ("held %ds of the %ds confirmation and the clock is still at %ds"
            % (first_tau - tau, st["confirm"], tau))


def inconsistent(held, coin, side):
    """Why (coin, side) must not be added to `held`, or None if it is safe.

    `held` is [(coin, side), ...] already on the book for ONE race. The only
    safe basket is: at most one YES leg, NO legs on other coins, never the
    same coin twice. Everything else can contradict itself, and a
    contradiction at 85c+ loses money before the race is even run."""
    for c, s in held:
        if c == coin:
            return ("already holding %s on %s -- a coin twice is a bet "
                    "against itself" % (s.upper(), coin))
    if side == "yes":
        for c, s in held:
            if s == "yes":
                return ("already holding YES on %s -- only one coin can win, "
                        "so a second YES is a guaranteed loser" % c)
    return None


def paper_log_refusal(logpath, paper):
    """Why --paper-live must not write to `logpath`, or None if it may.

    NULL: it says nothing about a --live log (that one is SUPPOSED to match),
    nothing about a missing path, and nothing about a paper name the day
    total cannot see."""
    if not paper or not logpath:
        return None
    if not fnmatch.fnmatch(os.path.basename(logpath), PINDAY_RACE_PAT):
        return None
    return ("--paper-live may not write to %r: pinday's day total globs %r "
            "and reads every `live_settled` leg's pnl as REAL money. Name it "
            "something the money report cannot pick up -- e.g. "
            "results/pinracearm-z3.jsonl."
            % (os.path.basename(logpath), PINDAY_RACE_PAT))

def live_refusals(tau, price, count, race, coin=None, side=None, state=None,
                  exists=os.path.exists):
    """Every reason this leg may NOT be bought with real money.

    Pure and side-effect free, so the self-test can plant each refusal one at
    a time. These sit ON TOP of pintake's own rails, never instead of them."""
    st = LIVE if state is None else state
    bad = []
    if not st["on"]:
        bad.append("not armed -- --live was not given")
    if halt_active(st):
        bad.append("halted: %s" % st["halted"])
    held = st["races"].get(race, [])
    if len(held) >= st["max_legs"]:
        bad.append("race already has %d legs, the cap" % len(held))
    if coin is not None and side is not None:
        why = inconsistent(held, coin, side)
        if why:
            bad.append(why)
    elif held:
        bad.append("cannot check consistency without a coin and side")
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


# ---- v-race-snowball: size the live path from the bank (2026-10-11) -------
# --contracts-per-bank X  -> contracts a leg = max(1, floor(bank * X))
# --stake-per-bank Y      -> the open-stake cap = bank * Y (floored to the cent)
# With X = 20/1050 and Y = 40/1050 a $1,050 bank gives today's 20 a leg and $40, and both then follow the
# bank up AND down. Both default to 0 = off, which leaves --max-contracts / --max-stake fixed exactly as
# before. Nothing else moves: the 2-losses-a-day stop, the tie-is-a-loss rule, the price floor, the
# confirmation, the leg cap and the per-race consistency rule read the same state they always did.
#
# THE BANK is the MAIN account's cash in POOL 2 (Crypto & Commodities, where coin race orders spend
# from), read the way pinrun.read_bank reads its bank: `balance` (cents) and `balance_dollars` are BOTH
# required and must agree to the cent, so the unit is read, never inferred (hard rule 5). The query MUST
# name the subaccount. Read live 2026-10-11 08:28Z, GET /portfolio/balance answered:
#     no query                          $1,069.74  (the main account, every pool)
#     exchange_index=2                  $1,297.30  (pool 2 of EVERY subaccount -- the trap)
#     subaccount=0, exchange_index=2    $1,068.25  <- this
#     subaccount=0, exchange_index=0        $1.49
# Dropping `subaccount` would size the race on the side bots' money too, about 21% too big that day.
#
# WHEN: at most every _DEFAULT_BANK_REREAD_S, and only BETWEEN races -- no real leg waiting on its
# result, no open race within RACE_BANK_QUIET_S of its close, and on the quarter-hour clock only from
# RACE_BANK_AFTER_CLOSE_S after a close to RACE_BANK_QUIET_S before the next (4:00..10:00 into each
# quarter hour) -- so a size never changes mid-race and a slow read cannot stall the seconds that trade.
# A failed read changes nothing: the last good size (or the argv's fixed one, before the first read) is
# held, and the failure is logged.
#
# The bank is CASH, so an open bet anywhere in the main account makes it read low by that bet's stake.
# MEASURED in the first paper run, 2026-10-11: a read at 09:00:00Z, the exact close, said $953.93 and
# cut the size to 18 a leg -- pinrun had bought 91 NEAR + 29 XRP at 08:59:31-41Z for the same close --
# and at 09:03:57Z the same read said $1,073.99. Every 15-minute series and the race close on the
# quarter hour and settle within minutes, hence the clock window. What is still open outside it (an
# hourly bet, say) still reads low: the error is toward a SMALLER race bet, never a bigger one.
RACE_BANK_QUERY = (("subaccount", 0), ("exchange_index", RACE_EXCHANGE_INDEX))
RACE_BANK_QUIET_S = 300          # no read while any open race is this close to its close
RACE_BANK_AFTER_CLOSE_S = 240    # ...nor this soon after a quarter-hour close (the bets on it settle)
RACE_BANK_RAIL_HEADROOM = 1.25   # pintake's rails are raised this far past a new size, so a growing
                                 # bank does not re-raise them (and print) on every read


def per_bank(text):
    """argparse type for --contracts-per-bank / --stake-per-bank: a decimal ("0.01904762") or a
    ratio ("20/1050", read as 20 per $1,050 of bank). Negative, non-finite or a zero denominator
    is refused at the command line, before anything is armed."""
    s = str(text).strip()
    try:
        if "/" in s:
            num, den = s.split("/", 1)
            v = float(num) / float(den)
        else:
            v = float(s)
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(
            "%r is not a number or a ratio like 20/1050" % (text,))
    if not math.isfinite(v) or v < 0:
        raise argparse.ArgumentTypeError("%r must be a finite number >= 0" % (text,))
    return v


def read_race_bank(getter):
    """(dollars, None) or (None, why): the main account's pool-2 cash. `getter(path, query)` returns
    (status, body) -- pintake._get with the live credentials under --live, kauth.get (GET-only by
    construction) under --paper-live, a planted function in the self-test. Never raises."""
    try:
        st, j = getter("/portfolio/balance", dict(RACE_BANK_QUERY))
    except Exception as e:                                   # noqa: BLE001
        return None, "balance read raised %s: %s" % (type(e).__name__, str(e)[:120])
    if st != 200 or not isinstance(j, dict):
        return None, "balance read failed (HTTP %s)" % (st,)
    cents, dollars = j.get("balance"), j.get("balance_dollars")
    if cents is None or dollars is None:
        return None, "balance body lacks `balance` or `balance_dollars` -- the unit cannot be read"
    try:
        a_, b_ = float(cents) / 100.0, float(dollars)
    except (TypeError, ValueError):
        return None, "balance unreadable (%r / %r)" % (cents, dollars)
    if not (math.isfinite(a_) and math.isfinite(b_)) or b_ < 0:
        return None, "balance is not a finite non-negative number (%r)" % (dollars,)
    if abs(a_ - b_) > 0.01 + 1e-9:
        return None, ("cents and dollars disagree ($%.2f vs $%.4f) -- the unit is not what it seems"
                      % (a_, b_))
    return b_, None


def bank_sizes(bank, cpb, spb, contracts, stake):
    """(contracts a leg, open-stake cap) for `bank` dollars. A rate of 0 leaves that number at the
    fixed argv value it is handed. Contracts never go under one; the 1e-9 keeps 1050 * (20/1050)
    from flooring to 19 on float error."""
    c = float(contracts)
    s = float(stake)
    if cpb > 0:
        c = float(max(1, int(math.floor(float(bank) * float(cpb) + 1e-9))))
    if spb > 0:
        s = math.floor(float(bank) * float(spb) * 100.0 + 1e-9) / 100.0
    return c, s


def between_races(live_pos, events, now):
    """True when a size may change: no real (or paper-live) leg is still waiting on its result, the
    quarter-hour clock is between RACE_BANK_AFTER_CLOSE_S after a close and RACE_BANK_QUIET_S before the
    next (the bets every 15-minute bot placed on the last close have settled, and none is placed yet on
    the next), and no open race is within RACE_BANK_QUIET_S of its close (arming, the confirmation and
    every send happen inside that window, and a stalled read there would cost seconds that trade)."""
    if any("win" not in p for p in (live_pos or [])):
        return False
    into = float(now) % 900.0
    if into < RACE_BANK_AFTER_CLOSE_S or into >= 900.0 - RACE_BANK_QUIET_S:
        return False
    for e in (events or {}).values():
        try:
            left = float(e["close"]) - float(now)
        except (KeyError, TypeError, ValueError):
            return False
        if 0 <= left <= RACE_BANK_QUIET_S:
            return False
    return True


def raise_pintake_rails(contracts, stake):
    """Loosen pintake's per-order count and run-stake rails so a bigger bank-scaled size is not
    refused at the order stage (2026-09-08: 160 orders sent, 0 filled, no error raised, because a rail
    tied to size did not move with it). One-way, as pintake insists: a smaller size needs nothing,
    because this file's own cap is checked first and is then the stricter one. None, or why not."""
    try:
        if pintake.MAX_TAKE_COUNT < contracts:
            pintake.set_limits(max_take_count=math.ceil(contracts * RACE_BANK_RAIL_HEADROOM),
                               why="--contracts-per-bank (v-race-snowball)")
        if pintake.MAX_RUN_STAKE < stake:
            pintake.set_limits(max_run_stake=round(stake * RACE_BANK_RAIL_HEADROOM, 2),
                               why="--stake-per-bank (v-race-snowball)")
    except ValueError as e:
        return "pintake refused: %s" % e
    if (contracts > pintake.MAX_TAKE_COUNT or contracts > pintake.HARD_MAX
            or stake > pintake.MAX_RUN_STAKE + 1e-9):
        return ("still over pintake's rails (count %g vs %g / HARD_MAX %g, stake $%.2f vs $%.2f)"
                % (contracts, pintake.MAX_TAKE_COUNT, pintake.HARD_MAX, stake, pintake.MAX_RUN_STAKE))
    return None


def bank_tick(state, getter, now, live_pos, events, rec=None, rails=raise_pintake_rails):
    """One look at the bank. Returns what happened: "off" (both rates 0 -- nothing read, nothing
    changed), "wait" (read less than bank_reread_s ago), "mid_race", "failed" (read failed, size held),
    "refused" (pintake would not admit the new size, size held), "resized" or "same".

    Touches ONLY state's max_contracts, max_stake, bank and bank_at -- never staked, halted, day_losses,
    max_losses or stop_on_loss, so the loss rails are exactly what they were."""
    cpb = float(state.get("contracts_per_bank") or 0.0)
    spb = float(state.get("stake_per_bank") or 0.0)
    if cpb <= 0 and spb <= 0:
        return "off"
    last = state.get("bank_at")
    if last is not None and now - float(last) < float(state.get("bank_reread_s") or _DEFAULT_BANK_REREAD_S):
        return "wait"
    if not between_races(live_pos, events, now):
        return "mid_race"
    state["bank_at"] = float(now)
    was_c, was_s = float(state["max_contracts"]), float(state["max_stake"])
    bank, why = read_race_bank(getter)
    if bank is None:
        if rec:
            rec("bank_read_failed", why=why, held_contracts=was_c, held_stake=was_s)
        return "failed"
    c, s = bank_sizes(bank, cpb, spb, state["fixed_contracts"], state["fixed_stake"])
    bad = rails(c, s) if rails else None
    if bad:
        if rec:
            rec("bank_resize_refused", why=bad, bank=round(bank, 4), contracts=c, stake=s,
                held_contracts=was_c, held_stake=was_s)
        return "refused"
    state["bank"] = bank
    state["max_contracts"], state["max_stake"] = c, s
    changed = (c, s) != (was_c, was_s)
    if rec:
        rec("bank_size", bank=round(bank, 4), contracts=c, stake=s, was_contracts=was_c,
            was_stake=was_s, changed=changed, contracts_per_bank=cpb, stake_per_bank=spb)
    return "resized" if changed else "same"


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


def _finite(x):
    """True only for a real, finite number. None, NaN and +-inf are not."""
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def race_zscores(rnow, cov, k, coins=None):
    """(zmin, {coin: z}) -- how far clear the leader is of EVERY other coin,
    measured in the sd of that PAIR's spread over the seconds still to run.

        z_j  = (r[L] - r[j]) / sqrt(k * (C[L][L] + C[j][j] - 2*C[L][j]))
        zmin = min over j != L,   L = argmax(r)

    THIS IS THE LIVE MODEL'S OWN NUMBER, asked a different question. It is the
    same covariance `win_probs` is handed one line later, the same variance
    collapse `var_factor` gives it, and the same projected returns -- no new
    model and no second ruler. It is computed ANALYTICALLY and is never read
    off `win_probs`: that is 1,000 random draws and cannot resolve a tenth of
    a percent, which is the whole region this number exists for.

    RACE-LEVEL. One number for the race, not one per leg: it is the same
    statement whichever leg we are pricing, which is the point (see
    z_refusal).

    NULL DISCIPLINE, the rule `worth` already follows: a denominator that is
    zero, negative or not finite makes zmin None, and None FAILS the floor. It
    is never a number, so it can never clear one. The per-coin dict still
    carries whatever pairs WERE computable, for the log."""
    names = list(F.COINS) if coins is None else list(coins)
    n = len(rnow) if rnow is not None else 0
    if n < 2 or len(names) != n or cov is None or len(cov) != n:
        return None, {}
    if not all(_finite(v) for v in rnow):
        return None, {c: None for c in names}
    if not _finite(k) or float(k) <= 0.0:
        # tau 0 (or worse) leaves nothing to come: every lead is infinitely
        # clear, which is exactly the sort of number that must never pass a
        # floor. None, not infinity.
        return None, {c: None for c in names}
    lead = max(range(n), key=lambda i: rnow[i])
    zs = {names[lead]: None}
    bad = False
    for j in range(n):
        if j == lead:
            continue
        try:
            var = float(k) * (float(cov[lead][lead]) + float(cov[j][j])
                              - 2.0 * float(cov[lead][j]))
        except (TypeError, ValueError, IndexError):
            zs[names[j]] = None
            bad = True
            continue
        if not _finite(var) or var <= 0.0:
            zs[names[j]] = None
            bad = True
            continue
        z = (rnow[lead] - rnow[j]) / math.sqrt(var)
        if not _finite(z):
            zs[names[j]] = None
            bad = True
            continue
        zs[names[j]] = z
    vals = [v for v in zs.values() if v is not None]
    return (None if (bad or not vals) else min(vals)), zs


def z_refusal(zmin, tau, min_z, min_z_tau):
    """None if the race-level z floor allows this leg, else the refusal label.

    RACE-LEVEL AND SIDE-INDEPENDENT, deliberately: the same number blocks the
    leader's YES and a trailing coin's NO. The paper loss 26SEP211830 was a NO
    leg whose OWN confidence was 98.6%, inside a three-way tie whose race zmin
    was 0.09. A leg-level confidence gate does not stop that. A race-level one
    does.

    IT APPLIES ONLY PAST `min_z_tau`. Inside 30 s the settlement variance has
    collapsed, so a fifth of a basis point reads as "3.6 sd": three of the six
    inside-30 losers on the tape survive a z >= 3 floor on leads of 0.19, 1.48
    and 4.64 bp, while the floor throws away 10 of our own 15 inside-30 races
    to remove losses we have never had. z is the wrong ruler at small tau.

    `min_z` of 0 is OFF -- the default, and what the live penny test runs, so
    its decisions are byte-for-byte what they are today."""
    if min_z is None or not (min_z > 0):
        return None
    if tau is None:
        return "zmin_under_floor"       # cannot tell which side of the band
    if tau <= min_z_tau:
        return None
    if zmin is None or not (zmin >= min_z):     # None and NaN both FAIL
        return "zmin_under_floor"
    return None


def live_fair(ticks_by_iid, close, tau, rets):
    """({coin: P(win)}, ruler, zmin, {coin: z}) from the arm's own live ticks,
    or (None, why, None, {}).

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
            k = F.var_factor(tau)
            pr = F.win_probs(rnow, c, k)[1.0]
            zmin, zs = race_zscores(rnow, c, k)
            return dict(zip(F.COINS, pr)), which, zmin, zs
    return None, "no_cov_history", None, {}


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


# ---- SCORING: ties, Kalshi's own result, and the retry book ----------------
#
# THE 2026-09-23 BUG. `winner_from` was a bare argmax of the five returns
# with no notion of a tie. KXCRYPTOLEAD15M-26SEP230715 (07:15 ET) closed with
# XRP 0.09 bp ahead of HYPE on our index; Kalshi called it a TIE and settled
# BOTH markets at 50c a contract (`market_result: scalar`, `value: 50`). We
# held XRP YES at 97c and HYPE NO at 98c: a real loss of -$0.9535 on the
# ledger, booked here as +$0.0465 -- two wins. The stop-on-first-loss rail
# never fired and the rolling stake was released as if won. The paper arms
# booked the same race +$7.50 where the truth at their size was about -$118.
# A_measure (results/map_2026-09-22/race_ties): 22 ties in 2,927 races, every
# one two-way, every one under 0.58 bp at the close, none determined inside
# 5.6 minutes, and NO arithmetic on the index reproduces which photo finishes
# Kalshi calls ties. So a REAL leg is scored from Kalshi's own result first,
# and never from the index inside the tie zone.
LEDGER_WAIT_S = 15 * 60   # a real leg waits this long for Kalshi's own row
TIE_SUSPECT_BP = 0.75     # under this top-two gap the index cannot call it:
                          # 13 of 13 ties inside, 0 of 2,363 races outside
LEDGER_POLL_S = 10        # re-read the ledger file at most this often


def race_returns(ticks_by_coin, close_s):
    """Every coin's settlement return (closing TWAP over opening TWAP) from
    our own index, or {} if ANY coin is missing a print in either window --
    never a partial race. This is the arithmetic `pinracemodel` validated at
    761 of 761 against Kalshi's own settled winner."""
    rets = {}
    for coin, ticks in ticks_by_coin.items():
        den = open_twap(ticks, close_s - WINDOW)
        num = [ticks[s] for s in range(close_s - N_AVG, close_s) if s in ticks]
        if not den or len(num) < N_AVG:
            return {}
        rets[coin] = (sum(num) / float(N_AVG)) / den
    return rets if len(rets) >= 2 else {}


def pct_move(ret):
    """A settlement return as the % change Kalshi publishes (1.0015 -> 0.15)."""
    return (ret - 1.0) * 100.0


def winner_from(scores, tie_bp=None):
    """(winner, is_tie, gap_bp) of a finished race, from its returns.

    winner  the coin with the largest return -- the INDEX leader -- or None
            when there is nothing to rank. On a tie it is STILL the argmax,
            so a caller must read is_tie; leaders_of() is the safe form.
    is_tie  True when the top two coins' % moves are equal after rounding to
            3 decimals -- the precision Kalshi publishes, 0.001% = 0.1 bp --
            or when the gap is under `tie_bp`, if one is given.
    gap_bp  the top-two gap in basis points of return; None when unscorable.
    """
    if not scores or len(scores) < 2:
        return None, False, None
    order = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    (top, r1), (_, r2) = order[0], order[1]
    gap_bp = (r1 - r2) * 1e4
    tie = round(pct_move(r1), 3) == round(pct_move(r2), 3)
    if tie_bp is not None and gap_bp < tie_bp:
        tie = True
    return top, tie, gap_bp


def leaders_of(scores):
    """The coins that share the lead: [winner] on an ordinary race, every
    coin whose 3-decimal % move equals the leader's on a tie, [] when the
    race cannot be scored."""
    won, tie, _ = winner_from(scores)
    if won is None:
        return []
    if not tie:
        return [won]
    top = round(pct_move(scores[won]), 3)
    return sorted(c for c, r in scores.items() if round(pct_move(r), 3) == top)


def leg_value(side, coin, leaders):
    """Dollars a contract collects at settlement: $1 to YES on the sole
    winner, 1/k to YES on each of k tied leaders (Kalshi's `value: 50` on a
    two-way tie), nothing to YES on any other coin; a NO collects the rest."""
    v = (1.0 / len(leaders)) if coin in leaders else 0.0
    return v if side == "yes" else 1.0 - v


def score_legs(legs, leaders=None, values=None):
    """Mark every scorable leg in place with value / win / tie / pnl and
    return the ones marked.

    `values` -- {ticker: what YES collected, 0..1} from Kalshi's own ledger
    -- outrank `leaders`, the index's view: a leg whose ticker has a ledger
    value is scored from it, every other leg from `leaders`. A leg with
    neither is left untouched (no "win" key), never guessed.

    pnl is size x (value - price) less the fee. With value 1 or 0 that is the
    identical arithmetic to the old win/lose branches (1 - price on a win,
    -price on a loss); 0.5 in between is the whole change. A leg that
    collected less than the full dollar did NOT win, and one that collected a
    fraction is a TIE -- a tie is a loss, and the halt rail reads `win`."""
    out = []
    for p in legs:
        v = None
        if values and p.get("ticker") in values:
            vy = float(values[p["ticker"]])
            v = vy if p["side"] == "yes" else 1.0 - vy
        elif leaders:
            v = leg_value(p["side"], p["coin"], leaders)
        if v is None:
            continue
        p["value"] = round(v, 6)
        p["tie"] = 0.0 < v < 1.0
        p["win"] = v >= 1.0 - 1e-9
        p["pnl"] = round(p["size"] * (v - p["price"])
                         - p["size"] * fee(p["price"]), 4)
        out.append(p)
    return out


def ledger_value(row):
    """What YES collected on one settled ledger row, 0..1, or None if the
    row cannot say. `value` is cents and Kalshi sets it on every row (100 on
    yes, 0 on no, 50 on a tie -- checked across 960 settlements, pinledger);
    market_result yes/no is the fallback. A `scalar` without a usable value,
    a void, or junk is None: unknown, never guessed."""
    val = row.get("value")
    if val is not None:
        try:
            v = float(val) / 100.0
        except (TypeError, ValueError):
            v = None
        if v is not None and 0.0 <= v <= 1.0:
            return v
    res = str(row.get("market_result") or "").strip().lower()
    if res == "yes":
        return 1.0
    if res == "no":
        return 0.0
    return None


def ledger_values(rows, tickers):
    """{ticker: YES value} for every ticker in `tickers` that Kalshi has
    settled in the ledger cache (pinledger's rows, keyed ticker|settled_time).
    A ticker with no usable row is ABSENT, never defaulted; the latest
    settlement wins if a ticker somehow has two."""
    want = set(tickers)
    best = {}
    for row in (rows or {}).values():
        if not isinstance(row, dict) or row.get("ticker") not in want:
            continue
        v = ledger_value(row)
        if v is None:
            continue
        tk, at = row["ticker"], str(row.get("settled_time") or "")
        if tk not in best or at >= best[tk][1]:
            best[tk] = (v, at)
    return {k: v for k, (v, _) in best.items()}


def settle_race(evt, cs, now, rets, real, pending, ledger_rows, paper=False):
    """HOW a closed race is scored -- or why it must wait. Touches only
    `pending` (the once-per-race log book) and returns a verdict dict with
    "status" scored | pending | unscored, plus winner / tie / gap_bp /
    leaders / values / source / waited, and "log" (a record kind to write
    once) when something is worth saying.

    RULES, in order:
      * no real legs: the index scores the paper legs now, tie by the
        3-decimal rule; an index hole is `unscored`, exactly as before.
      * real legs: Kalshi's own result from the ledger scores them the moment
        EVERY real ticker has a row (median determination 39 s; pinledgerd
        refreshes every 60 s). Until then the race is PENDING -- not scored,
        not dropped, stake HELD.
      * past LEDGER_WAIT_S with rows still missing: a race whose index gap
        is at least TIE_SUSPECT_BP is scored from the index (`index_fallback`).
        Under the bar, or with no index at all, it is a TIE SUSPECT: logged
        once as `unscored_tie_suspect`, kept pending with its stake held, and
        re-checked against the ledger for as long as the process runs. A tie
        has never been determined inside 5.6 minutes and the index cannot
        tell one from a win, so a real leg is never scored from it there.
      * --paper-live (paper=True) commits no money: same ledger-first path,
        but a tie suspect the index CAN rank is scored from it at the
        deadline, flagged tie_suspect, rather than held -- so a paper arm's
        rolling cap cannot silt up on races nobody will ever settle for it.
    """
    won, tie, gap_bp = winner_from(rets)
    leaders = leaders_of(rets)
    base = {"winner": won, "tie": tie, "gap_bp": gap_bp, "leaders": leaders,
            "values": {}, "waited": max(0.0, now - (cs + SCORE_DELAY)),
            "log": None}
    if not real:
        if not leaders:
            return dict(base, status="unscored",
                        why="index incomplete at close+%ds" % SCORE_DELAY)
        return dict(base, status="scored", source="index")
    ent = pending.setdefault(evt, {"logged": set()})

    def once(kind):
        if kind in ent["logged"]:
            return None
        ent["logged"].add(kind)
        return kind

    tickers = [p["ticker"] for p in real]
    vals = ledger_values(ledger_rows, tickers)
    base["values"] = vals
    if all(t in vals for t in tickers):
        coin_of = {p["ticker"]: p["coin"] for p in real}
        tied = sorted({coin_of[t] for t, x in vals.items() if 0.0 < x < 1.0})
        won_k = sorted({coin_of[t] for t, x in vals.items() if x >= 1.0})
        if tied:
            # Kalshi tied it. Every tie on record is two-way and names the
            # index's top two (8 of 8, A_measure), so when we held only one
            # tied coin the other is the index's runner-up.
            if len(tied) < 2 and rets:
                top2 = [c for c, _ in sorted(rets.items(),
                                             key=lambda kv: -kv[1])[:2]]
                tied = sorted(set(tied) | set(top2))
            return dict(base, status="scored", source="ledger", tie=True,
                        winner=None, leaders=tied)
        if won_k:
            return dict(base, status="scored", source="ledger", tie=False,
                        winner=won_k[0], leaders=won_k[:1])
        # every real ticker lost (NOs on trailers, say): Kalshi has named no
        # winner to us, so the index's view stands for the paper legs
        return dict(base, status="scored", source="ledger")
    if base["waited"] < LEDGER_WAIT_S:
        return dict(base, status="pending", log=once("awaiting_ledger"),
                    why="awaiting Kalshi's result: %d of %d rows on the ledger"
                        % (len(vals), len(tickers)))
    suspect = (not leaders) or gap_bp is None or gap_bp < TIE_SUSPECT_BP
    if suspect and (not paper or not leaders):
        if leaders:
            why = ("index gap %.3f bp is under the %.2f bp tie bar and Kalshi's "
                   "result is not on the ledger after %d min: a tie suspect -- "
                   "stake held, still waiting for the row"
                   % (gap_bp, TIE_SUSPECT_BP, LEDGER_WAIT_S // 60))
            kind = "unscored_tie_suspect"
        else:
            why = ("index incomplete and no Kalshi row after %d min -- stake "
                   "held, still waiting for the row" % (LEDGER_WAIT_S // 60))
            kind = "race_pending"
        return dict(base, status="pending", why=why, log=once(kind))
    return dict(base, status="scored", source="index_fallback",
                tie_suspect=bool(suspect),
                log=once("index_fallback"),
                why="no Kalshi row after %d min; index gap %.3f bp -- scored "
                    "from the index" % (LEDGER_WAIT_S // 60, gap_bp))


def _et_day(t):
    """ET calendar day (EDT, UTC-4 -- the repo's Nov-1 clock item applies here too)."""
    return time.strftime("%Y-%m-%d", time.gmtime(float(t) - 4 * 3600))


def halt_active(st, now=None):
    """The halt that is in force at `now`. A DAILY loss-limit halt (halted_day set) expires when the ET day turns;
    the first-loss stop (halted_day None) never does."""
    h = st.get("halted")
    if h and st.get("halted_day") and st["halted_day"] != _et_day(time.time() if now is None else now):
        return None
    return h


# v-race-daystate (2026-10-03, IDEA_LEDGER F29): THE DAY'S LOSS COUNT SURVIVES A RESTART.
# Until today `day_losses`, `loss_day`, `halted` and `halted_day` lived only in LIVE, in memory, so a
# keep-alive restart forgot the day's losses and the 2-losses-a-day stop (v-race40) could be beaten by a
# restart. Now every change is written to DAYSTATE_FILE and a --live start reads it back: a record from
# TODAY (ET) is restored -- count and halt -- so a halted day stays halted through a restart; a record from
# another day is ignored (the daily limit resets at the ET day turn, as before); a corrupt or unreadable
# file is ignored and said so in the log. Paper arms and the self-test never write results/: the writer
# runs only when `state["daystate_path"]` is set, and main sets it under --live only.
DAYSTATE_FILE = os.path.join(REPO, "results", "pinracepenny-daystate.json")
DAYSTATE_KEYS = ("loss_day", "day_losses", "halted", "halted_day")


def save_daystate(state, path=None, now=None):
    """Write the daily loss counter and halt to `path` (tmp + replace). No path (none in `state` either)
    = nothing written, so a planted dict in the self-test and a paper arm never touch results/. `day` is
    the ET day the record belongs to. Returns the path written, or None."""
    path = path or state.get("daystate_path")
    if not path:
        return None
    now = time.time() if now is None else now
    d = {k: state.get(k) for k in DAYSTATE_KEYS}
    d["day"] = state.get("loss_day") or state.get("halted_day") or _et_day(now)
    d["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, path)
    except OSError:
        return None
    return path


def restore_daystate(state, path=None, now=None):
    """Read the file at a live start. (what, detail): "restored" -- the record is from TODAY (ET) and its
    count and halt are now in `state`; "stale" -- another day, ignored; "corrupt" / "missing" -- ignored,
    with the reason. Never raises; never restores a halt whose day is not today."""
    path = path or DAYSTATE_FILE
    now = time.time() if now is None else now
    if not os.path.exists(path):
        return "missing", None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            raise ValueError("not a JSON object")
        day = str(d.get("day") or "")
        losses = int(d.get("day_losses") or 0)
        halted, halted_day = d.get("halted"), d.get("halted_day")
        if halted is not None and not isinstance(halted, str):
            raise ValueError("halted is not text")
        if losses < 0:
            raise ValueError("negative loss count")
    except (OSError, ValueError, TypeError) as e:
        return "corrupt", "%s: %s" % (type(e).__name__, str(e)[:120])
    today = _et_day(now)
    if day != today:
        return "stale", {"day": day, "today": today, "day_losses": losses, "halted": halted}
    state["loss_day"], state["day_losses"] = day, losses
    if halted and (halted_day == today or halted_day is None):
        state["halted"], state["halted_day"] = halted, halted_day
    return "restored", {"day": day, "day_losses": losses, "halted": halted, "halted_day": halted_day}


def loss_halt(evt, lost):
    """The stop-on-first-loss message for the first losing real leg. A TIE is
    named as a tie, with the dollars it cost: money was lost, so the rail
    fires, and the operator reads WHY it fired. None when nothing lost."""
    if not lost:
        return None
    p = lost[0]
    if p.get("tie"):
        return ("first real loss: TIE -- %s settled at %.0fc a contract on "
                "both tied coins; %s %s at %.0fc lost $%.2f"
                % (evt, 100 * float(p.get("value", 0.5)), p.get("coin"),
                   p["side"], 100 * p["price"], -p["pnl"]))
    return "first real loss: %s %s at %.0fc" % (evt, p["side"], 100 * p["price"])


def settle_pass(evt, cs, now, rets, fills, live_pos, pending, ledger_rows,
                rec, state, stake_book):
    """One closed race, one pass of the scorer. Scores the paper legs in
    `fills` and the real legs in `live_pos` for `evt`, releases the rolling
    stake ONLY on a scored result, writes the records through `rec`, and
    halts `state` on the first real loss -- a tie included. Returns True
    when the race is DONE (scored, or given up) and False when it must be
    looked at again: a False race stays in `known`, out of `scored`, its
    stake held. `state` is the LIVE dict in main and a planted one in the
    self-test."""
    mine = [p for p in fills if p["event"] == evt and "win" not in p]
    real = [p for p in live_pos if p["event"] == evt and "win" not in p]
    v = settle_race(evt, cs, now, rets, real, pending, ledger_rows,
                    paper=bool(state.get("paper")))
    gap = None if v.get("gap_bp") is None else round(v["gap_bp"], 4)
    if v.get("log"):
        rec(v["log"], event=evt, close_s=cs, why=v.get("why"), gap_bp=gap,
            waited=round(v.get("waited", 0.0)),
            tickers=[p["ticker"] for p in real],
            ledger_rows=len(v.get("values") or {}),
            staked_open=round(float(state.get("staked", 0.0)), 4))
    if v["status"] == "pending":
        return False                # NOT scored, NOT dropped, stake HELD
    pending.pop(evt, None)
    if v["status"] == "unscored":
        rec("unscored", event=evt, close_s=cs, why=v["why"])
        return True
    won, leaders, is_tie = v["winner"], v["leaders"], bool(v["tie"])
    done = score_legs(mine, leaders)
    if mine and not done:
        rec("unscored", event=evt, close_s=cs, positions=len(mine),
            why="paper legs: index incomplete, and Kalshi's rows cover only "
                "the real legs")
    rec("settled", event=evt, close_s=cs, winner=won, tie=is_tie,
        tied=(leaders if is_tie else None), gap_bp=gap, source=v["source"],
        returns={k: round(x, 8) for k, x in rets.items()},
        positions=len(done),
        won=sum(1 for p in done if p["win"]),
        ties=sum(1 for p in done if p.get("tie")),
        pnl=round(sum(p["pnl"] for p in done), 4))
    if done:
        print("  SETTLED %-28s %-4s  %d/%d won  $%+.2f%s"
              % (evt, won or ("TIE" if is_tie else "?"),
                 sum(1 for p in done if p["win"]),
                 len(done), sum(p["pnl"] for p in done),
                 "  (TIE: %s paid %.0fc)" % ("/".join(leaders),
                                             100.0 / len(leaders))
                 if is_tie else ""))

    # ---- the REAL positions, and stop on the first loss ----------------
    real = score_legs(real, leaders, v.get("values"))
    if real:
        lost = [p for p in real if not p["win"]]
        ties = [p for p in real if p.get("tie")]
        # --paper-live releases into ITS OWN book. A process that never
        # sends must never write to pintake's ledger.
        released = (release_settled(state, stake_book, real)
                    if state.get("rolling") else 0.0)
        for p in ties:
            # A TIE IS A LOSS, logged by name with the dollars it cost.
            rec("tie", event=evt, close_s=cs, ticker=p["ticker"],
                coin=p.get("coin"), side=p["side"], price=p["price"],
                size=p["size"], value=p["value"], pnl=p["pnl"],
                paper=state.get("paper"), source=v["source"])
        rec("live_settled", event=evt, close_s=cs, winner=won, tie=is_tie,
            tied=(leaders if is_tie else None), gap_bp=gap,
            source=v["source"], waited=round(v.get("waited", 0.0)),
            tie_suspect=bool(v.get("tie_suspect")),
            paper=state.get("paper"),
            released=round(released, 4),
            staked_open=round(float(state.get("staked", 0.0)), 4),
            positions=len(real),
            won=sum(1 for p in real if p["win"]),
            ties=len(ties),
            pnl=round(sum(p["pnl"] for p in real), 4),
            legs=[{k: p.get(k) for k in
                   ("ticker", "side", "price", "size", "tau",
                    "ask_seen", "zmin", "win", "pnl", "tie", "value")}
                  for p in real])
        print("  ** %s SETTLED %-24s %-4s  %d/%d won  $%+.2f%s"
              % ("PAPR" if state.get("paper") else "LIVE", evt,
                 won or ("TIE" if is_tie else "?"),
                 sum(1 for p in real if p["win"]),
                 len(real), sum(p["pnl"] for p in real),
                 "  TIE -- %d leg(s) paid 50c" % len(ties) if ties else ""))
        if state.get("halted") and not halt_active(state, cs):
            state["halted"] = state["halted_day"] = None          # a new ET day: the daily limit resets
            save_daystate(state, now=cs)                          # v-race-daystate: every change to disk
        if (lost and state.get("stop_on_loss") and not state.get("halted")
                and int(state.get("max_losses") or 1) > 1):
            _d = _et_day(cs)
            if state.get("loss_day") != _d:
                state["loss_day"], state["day_losses"] = _d, 0
            state["day_losses"] = int(state.get("day_losses") or 0) + 1
            rec("live_loss", day=_d, losses_today=state["day_losses"],
                limit=int(state["max_losses"]), why=loss_halt(evt, lost))
            if state["day_losses"] >= int(state["max_losses"]):
                state["halted"] = "%d losing races on %s ET, the daily limit -- %s" % (
                    state["day_losses"], _d, loss_halt(evt, lost))
                state["halted_day"] = _d
                rec("live_halt", why=state["halted"],
                    staked=round(float(state.get("staked", 0.0)), 4),
                    sends=state.get("sends"))
                print("\n  *** LIVE RACE STOPPED FOR THE DAY: %s\n" % state["halted"])
            save_daystate(state, now=cs)                          # the count, halted or not
        elif lost and state.get("stop_on_loss") and not state.get("halted"):
            # STOP DEAD. The whole point of the penny test is to find out
            # whether we lose more often than the tape says; the first real
            # loss is the answer arriving, not a reason to keep going and
            # find out how much. A tie lost money, so a tie is a loss.
            state["halted"] = loss_halt(evt, lost)
            rec("live_halt", why=state["halted"],
                staked=round(float(state.get("staked", 0.0)), 4),
                sends=state.get("sends"))
            save_daystate(state, now=cs)
            print("\n  *** PENNY TEST HALTED: %s" % state["halted"])
            print("  No further real order will be sent by this "
                  "process. The paper arm keeps running.\n")
    return True


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
    p4, ruler4, z4, zs4 = live_fair(snap4, close4, 20, rets4)
    ck(p4 is not None and ruler4 == "300",
       "a fresh arm with only ~33 minutes of ticks gets a forecast on the 300 s "
       "ruler (got %s), not a refusal and not a pretend hour" % ruler4)
    ck(p4 is not None and max(p4, key=p4.get) == "HYPE" and p4["HYPE"] > 0.99,
       "and a 4bp lead with 20 s left on calm independent coins is ~certain "
       "(%.3f)" % (p4 or {}).get("HYPE", 0))
    ck(z4 is not None and z4 > 3.0 and zs4.get("HYPE") is None
       and sorted(k for k, v in zs4.items() if v is not None)
       == sorted(c for c in F.COINS if c != "HYPE"),
       "and the SAME call returns the race's zmin (%.2f) with one z per "
       "challenger and None for the leader itself" % (z4 or 0))
    ck(z4 is not None and abs(z4 - min(v for v in zs4.values()
                                       if v is not None)) < 1e-12,
       "zmin is the SMALLEST of those, never the mean and never the leader's")
    p5, why5, z5, zs5 = live_fair({iid: {} for iid in F.IIDS}, close4, 20, rets4)
    ck(p5 is None and why5 == "no_cov_history" and z5 is None and zs5 == {},
       "NULL: with no tick history at all it refuses rather than guessing, and "
       "the z it cannot compute comes back None -- never a number")

    # ---- zmin, against arithmetic done by hand -------------------------
    # TWO COINS. sd(spread) = sqrt(k * (s1^2 + s2^2 - 2*rho*s1*s2)).
    _s1, _s2, _rho, _k = 1e-4, 2e-4, 0.5, 400.0
    _cov2 = [[_s1 * _s1, _rho * _s1 * _s2], [_rho * _s1 * _s2, _s2 * _s2]]
    _sd2 = math.sqrt(_k * (_s1 * _s1 + _s2 * _s2 - 2 * _rho * _s1 * _s2))
    _lead = 2.5 * _sd2
    _z2, _zz2 = race_zscores([_lead, 0.0], _cov2, _k, coins=["A", "B"])
    ck(abs(_z2 - 2.5) < 1e-12 and _zz2 == {"A": None, "B": _z2},
       "HAND-COMPUTED, 2 coins: a lead of 2.5 spread-sd reads back as exactly "
       "2.5 (got %.12f), and the leader has no z against itself" % _z2)
    _z2b, _ = race_zscores([0.0, _lead], _cov2, _k, coins=["A", "B"])
    ck(abs(_z2b - _lead / math.sqrt(_k * (_s2 * _s2 + _s1 * _s1
                                          - 2 * _rho * _s1 * _s2))) < 1e-12,
       "and it finds the leader wherever it sits, not at index 0")
    # THREE COINS, one close challenger and one far one: zmin is the CLOSE one.
    _c3 = [[1e-8, 0.0, 0.0], [0.0, 1e-8, 0.0], [0.0, 0.0, 4e-8]]
    _k3 = 100.0
    _sdAB = math.sqrt(_k3 * (1e-8 + 1e-8 - 0.0))
    _sdAC = math.sqrt(_k3 * (1e-8 + 4e-8 - 0.0))
    _r3 = [3.0 * _sdAB, 0.0, 3.0 * _sdAB - 6.0 * _sdAC]
    _z3, _zz3 = race_zscores(_r3, _c3, _k3, coins=["A", "B", "C"])
    ck(abs(_zz3["B"] - 3.0) < 1e-12 and abs(_zz3["C"] - 6.0) < 1e-12
       and abs(_z3 - 3.0) < 1e-12,
       "HAND-COMPUTED, 3 coins: B is 3.0 sd back and C is 6.0 sd back, so the "
       "race is 3.0 sd clear -- the NEAREST challenger sets it (got %.12f)"
       % _z3)
    # THE COLLAPSE. The same lead and the same covariance read 9.03x bigger at
    # tau 10 than at tau 45, because var_factor(45)/var_factor(10) = 81.546.
    _zA, _ = race_zscores([1e-5, 0.0], _cov2, F.var_factor(45), coins=["A", "B"])
    _zB, _ = race_zscores([1e-5, 0.0], _cov2, F.var_factor(10), coins=["A", "B"])
    _ratio = math.sqrt(F.var_factor(45) / F.var_factor(10))
    ck(abs(_zB / _zA - _ratio) < 1e-9 and abs(_ratio - 9.0303) < 1e-3,
       "THE COLLAPSE: the identical lead reads %.2f sd at tau 10 and %.2f at "
       "tau 45 -- %.4fx, exactly sqrt(var_factor(45)/var_factor(10)). This is "
       "why the floor must not apply at small tau" % (_zB, _zA, _zB / _zA))

    # NULL: every degenerate denominator FAILS, none of them passes.
    _same = [[1e-8, 1e-8], [1e-8, 1e-8]]            # identical coins: var 0
    _zn, _zzn = race_zscores([1e-7, 0.0], _same, 100.0, coins=["A", "B"])
    ck(_zn is None and _zzn == {"A": None, "B": None},
       "NULL: two coins that move IDENTICALLY have a ZERO spread sd, so the "
       "lead is not 'infinitely clear' -- it is unknown, and unknown is None")
    _neg = [[1e-8, 3e-8], [3e-8, 1e-8]]             # not PSD: var < 0
    ck(race_zscores([1e-7, 0.0], _neg, 100.0, coins=["A", "B"])[0] is None,
       "NULL: a NEGATIVE variance (a covariance that is not positive "
       "semi-definite) is refused, never square-rooted")
    ck(race_zscores([1e-7, 0.0], _cov2, 0.0, coins=["A", "B"])[0] is None
       and race_zscores([1e-7, 0.0], _cov2, F.var_factor(0),
                        coins=["A", "B"])[0] is None
       and race_zscores([1e-7, 0.0], _cov2, -5.0, coins=["A", "B"])[0] is None,
       "NULL: nothing left to come (tau 0, k = 0) and a negative k are both "
       "None -- not a division, not an infinity")
    _inf = float("inf")
    _nan = _inf - _inf
    ck(race_zscores([1e-7, 0.0], [[_nan, 0.0], [0.0, 1e-8]], 100.0,
                    coins=["A", "B"])[0] is None
       and race_zscores([1e-7, 0.0], [[_inf, 0.0], [0.0, 1e-8]], 100.0,
                        coins=["A", "B"])[0] is None
       and race_zscores([_nan, 0.0], _cov2, _k, coins=["A", "B"])[0] is None,
       "NULL: a non-finite covariance, variance or projected return is None")
    ck(race_zscores(None, _cov2, _k)[0] is None
       and race_zscores([1e-7], _cov2, _k, coins=["A"])[0] is None
       and race_zscores([1e-7, 0.0], None, _k, coins=["A", "B"])[0] is None,
       "NULL: no returns, one coin, or no covariance at all is None")
    # a PARTLY computable race is still None overall, but logs what it had
    _part = [[1e-8, 0.0, 0.0], [0.0, 1e-8, 0.0], [0.0, 0.0, _nan]]
    _zp, _zzp = race_zscores([2e-6, 0.0, -1e-6], _part, 100.0,
                             coins=["A", "B", "C"])
    ck(_zp is None and _zzp["B"] is not None and _zzp["C"] is None,
       "NULL: one unreadable pair makes the RACE unknown even though the "
       "other pair computed -- the log keeps the pair it had")

    # ---- the floor itself ----------------------------------------------
    ck(_DEFAULT_MIN_Z == 0.0,
       "the z floor is OFF by default, so the live penny test's argv decides "
       "exactly what it decides today")
    ck(_DEFAULT_MIN_Z_TAU == 30,
       "and when it is switched on it starts past 30 s, where B_verify "
       "measured it (inside 30 s, z is the wrong ruler)")
    ck(z_refusal(3.5, 45, 3.0, 30) is None,
       "at 45 s a race 3.5 sd clear passes a 3-sd floor")
    ck(z_refusal(2.5, 45, 3.0, 30) == "zmin_under_floor",
       "at 45 s a race only 2.5 sd clear is refused")
    ck(z_refusal(3.0, 45, 3.0, 30) is None,
       "the floor is INCLUSIVE: exactly 3.0 passes")
    ck(z_refusal(2.5, 25, 3.0, 30) is None and z_refusal(0.09, 2, 3.0, 30) is None,
       "and NOTHING inside 30 s is touched: the same 2.5-sd race passes at 25 s")
    ck(z_refusal(2.5, 30, 3.0, 30) is None,
       "tau 30 itself is inside -- the bar is 'past min-z-tau', not 'at' it")
    ck(z_refusal(2.5, 31, 3.0, 30) == "zmin_under_floor",
       "and 31 s is the first second it bites")
    ck(z_refusal(None, 60, 3.0, 30) == "zmin_under_floor"
       and z_refusal(_nan, 60, 3.0, 30) == "zmin_under_floor"
       and z_refusal(0.0, 60, 3.0, 30) == "zmin_under_floor"
       and z_refusal(-4.0, 60, 3.0, 30) == "zmin_under_floor",
       "NULL: an unknown, NaN, zero or NEGATIVE lead all FAIL the floor -- "
       "never a number, so never able to clear one")
    ck(z_refusal(None, None, 3.0, 30) == "zmin_under_floor",
       "and a race with no tau at all is refused rather than assumed early")
    _off = [z_refusal(z, t, 0.0, 30)
            for t in range(TAU_LO, TAU_HI + 1)
            for z in (None, _nan, -9.0, 0.0, 0.09, 2.5, 3.0, 99.0)]
    ck(all(r is None for r in _off) and len(_off) == 8 * (TAU_HI - TAU_LO + 1),
       "THE OFF SWITCH IS THE REVERT: with --min-z 0 (the live default) all "
       "%d combinations of tau and zmin are allowed, including the ones the "
       "floor exists to block" % len(_off))
    ck(all(z_refusal(z, t, None, 30) is None
           for t in (2, 30, 31, 60, 150) for z in (None, 0.0, 99.0)),
       "and a missing --min-z is off too, never a floor of None")

    # RACE-LEVEL, NOT LEG-LEVEL: the 26SEP211830 shape, built and measured
    # rather than asserted. Three coins in a near-tie, two far behind. The
    # trailing coin's own NO is worth ~99%, so every leg-level test in this
    # file passes it; the race is 0.09 sd clear, and the race-level floor
    # refuses all ten of its legs.
    _tk = F.var_factor(60)
    _tcov = [[(1e-9 if i == j else 0.0) for j in range(5)] for i in range(5)]
    _tsd = math.sqrt(_tk * 2e-9)                # sd of any pair's spread
    #       BTC       ETH             SOL             XRP        HYPE
    _tr = [0.09 * _tsd, 0.0, -0.02 * _tsd, -2.0 * _tsd, -14.0 * _tsd]
    _tz, _tzs = race_zscores(_tr, _tcov, _tk, coins=F.COINS)
    ck(abs(_tz - 0.09) < 1e-9 and abs(_tzs["HYPE"] - 14.09) < 1e-9,
       "the race is %.2f sd clear -- the NEAREST challenger, not the 14.09 sd "
       "gap to a coin that is out of it" % _tz)
    _tp = dict(zip(F.COINS, F.win_probs(_tr, _tcov, _tk)[1.0]))
    _no_worth = fair_worth(_tp, "XRP", "no")
    ck(_no_worth > 0.98 and net_edge(_no_worth, 0.98) > -0.005,
       "and the trailing coin's NO is worth %.4f -- a leg-level confidence "
       "gate lets that straight through at 98c" % _no_worth)
    ck(all(z_refusal(_tz, 60, 3.0, 30) == "zmin_under_floor"
           for _c in F.COINS for _s in ("yes", "no")),
       "but the RACE-LEVEL floor refuses ALL TEN legs of it -- the leader's "
       "YES and every trailer's NO alike. That is the 26SEP211830 loss, and "
       "a leg-level gate cannot see it.")
    ck(tuple(inspect.signature(z_refusal).parameters)
       == ("zmin", "tau", "min_z", "min_z_tau"),
       "the floor is never told which coin or which side, so it cannot "
       "quietly become a leg-level gate")
    ck(z_refusal(_tz, 25, 3.0, 30) is None,
       "and the same race inside 30 s is still taken -- the arm can only ADD "
       "to what runs live today, never subtract")

    # THE RE-ARM. A z refusal restarts the leg's confirmation clock, so a
    # confidence that dips under the floor and comes back has to serve the
    # five seconds again. That single line is 1 loss in 554 vs 0 in 366.
    cs4 = {"confirm": _DEFAULT_LIVE_CONFIRM, "clock_tau": 5}
    _am = {}
    for _t in (50, 49, 48, 47):
        _ft = arm_leg(_am, "R", "BTC", "yes", _t)
    ck(_ft == 50 and confirm_refusal(_ft, 47, cs4) is not None,
       "a leg qualifying since tau 50 has served 3 of its 5 seconds at 47")
    ck(confirm_refusal(arm_leg(_am, "R", "BTC", "yes", 45), 45, cs4) is None,
       "WITHOUT the re-arm it would fire the moment it came back at 45, on a "
       "clock that started before the refusal -- the bug the re-arm closes")
    _am = {}
    for _t in (50, 49, 48, 47):
        arm_leg(_am, "R", "BTC", "yes", _t)
    ck(disarm(_am, "R", "BTC", "yes") == 50
       and ("BTC", "yes") not in _am.get("R", {}),
       "a z refusal at 46 DISARMS the leg: its 50 s arming record is handed "
       "back and gone")
    ck(arm_leg(_am, "R", "BTC", "yes", 45) == 45,
       "so when it qualifies again at 45 the clock starts AT 45, not at 50")
    ck(disarm(_am, "R", "SOL", "no") is None and disarm({}, "R", "B", "yes") is None
       and disarm(_am, "NOSUCH", "BTC", "yes") is None,
       "NULL: disarming a leg, a race or a book that was never armed is a "
       "no-op that returns nothing, never a crash")
    ck(confirm_refusal(45, 45, cs4) is not None
       and confirm_refusal(45, 41, cs4) is not None,
       "it cannot fire at 45, and it still cannot at 41 -- 4 of 5 seconds")
    ck(confirm_refusal(45, 40, cs4) is None,
       "it fires at 40, a full five seconds after it came back")
    ck(arm_leg(_am, "R", "SOL", "no", 44) == 44,
       "and disarming one leg left every OTHER leg's clock alone")

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
    rets = race_returns(t, 10_000)
    won, _tie, _gap = winner_from(rets)
    ck(won == "SOL" and _tie is False and leaders_of(rets) == ["SOL"],
       "the scorer picks the coin with the biggest return out of five, and a "
       "1% lead is no tie")
    ck(len(rets) == 5 and all(r > 1.0 for r in rets.values()),
       "and every coin rose, which changed nothing -- a common move cannot "
       "decide a race")
    hole = {c: dict(d) for c, d in t.items()}
    hole["BTC"].pop(10_000 - 30)
    ck(race_returns(hole, 10_000) == {}
       and winner_from(race_returns(hole, 10_000)) == (None, False, None)
       and leaders_of({}) == [],
       "NULL: one missing print in one coin refuses to score the race at all, "
       "rather than scoring it on four legs")

    # ---- TIES (2026-09-24). Kalshi settles a photo finish at 50c to BOTH ---
    # coins' markets. Until today nothing here knew that a race could end
    # without a winner, and the real 09-23 tie (-$0.9535 on the ledger) was
    # booked +$0.0465 -- two wins -- so the first-loss rail never fired.
    # (a) the rule: equal after rounding each % move to 3 decimals
    _sc = {"BTC": 1.0015, "ETH": 1.0015, "SOL": 1.0001, "XRP": 0.999,
           "HYPE": 0.998}
    _w, _t, _g = winner_from(_sc)
    ck(_t is True and abs(_g) < 1e-12 and leaders_of(_sc) == ["BTC", "ETH"]
       and _w == "BTC",
       "(a) two coins at exactly +0.150% are a TIE: is_tie, gap 0 bp, both "
       "named as leaders (the argmax is still returned, so a caller that "
       "ignores is_tie is wrong by construction -- leaders_of is the safe form)")
    _sc2 = dict(_sc, ETH=1.00149)
    _w2, _t2, _g2 = winner_from(_sc2)
    ck(_w2 == "BTC" and _t2 is False and abs(_g2 - 0.1) < 1e-6
       and leaders_of(_sc2) == ["BTC"],
       "(a) +0.150%% against +0.149%% -- a 0.001%% gap, 0.1 bp -- is NOT a "
       "tie (gap %.4f bp)" % _g2)
    _sc3 = dict(_sc, BTC=1.001504, ETH=1.001496)
    ck(winner_from(_sc3)[1] is True and leaders_of(_sc3) == ["BTC", "ETH"],
       "(a) and +0.1504% vs +0.1496% IS one: equal after rounding, not "
       "identical -- the rule is Kalshi's 3 decimals, not an exact draw")
    ck(winner_from(_sc2, tie_bp=0.75) == ("BTC", True, _g2),
       "(a) under a 0.75 bp bar the 0.1 bp race reads as a tie SUSPECT -- "
       "that bar is the deadline rule for real legs, never the scorer's")
    ck(abs(leg_value("yes", "BTC", ["BTC", "ETH", "SOL"]) - 1.0 / 3) < 1e-12
       and abs(leg_value("no", "BTC", ["BTC", "ETH", "SOL"]) - 2.0 / 3) < 1e-12,
       "(a) a three-way tie pays a third: the arithmetic is 1/k, not a "
       "hard-coded 50c (no three-way tie has ever happened; A_measure)")

    # (b) a REAL YES at 97c on a tied race: 50c back on 97c plus the fee
    _yes = [{"event": "E", "coin": "BTC", "ticker": "E-BTC", "side": "yes",
             "price": 0.97, "size": 1.0}]
    score_legs(_yes, ["BTC", "ETH"])
    ck(_yes[0]["tie"] is True and _yes[0]["win"] is False
       and abs(_yes[0]["pnl"] + 0.4721) < 1e-9 and _yes[0]["value"] == 0.5,
       "(b) a YES at 97c on a tied coin books -$0.4721 a contract (50c back, "
       "97c paid, 0.21c fee) -- the ledger's exact number for the XRP leg -- "
       "is a TIE and is NOT a win")
    _hm = loss_halt("E", [p for p in _yes if not p["win"]])
    ck(_hm is not None and "TIE" in _hm and "$0.47" in _hm and "50c" in _hm,
       "(b) and the stop-on-first-loss rail FIRES on it, naming the tie and "
       "the dollars: %r" % _hm)
    # (c) a NO at 98c on the OTHER tied coin loses too; a NO on a coin that
    # did not tie still collects the full dollar
    _no = [{"event": "E", "coin": "ETH", "ticker": "E-ETH", "side": "no",
            "price": 0.98, "size": 1.0},
           {"event": "E", "coin": "SOL", "ticker": "E-SOL", "side": "no",
            "price": 0.98, "size": 1.0}]
    score_legs(_no, ["BTC", "ETH"])
    ck(_no[0]["tie"] is True and not _no[0]["win"]
       and abs(_no[0]["pnl"] + 0.4814) < 1e-9,
       "(c) a NO at 98c on the other tied coin books -$0.4814 (the ledger's "
       "HYPE number): in a tie BOTH tied coins' markets pay 50c, so the "
       "leader's YES and the rival's NO lose TOGETHER -- not a hedge")
    ck(_no[1]["win"] is True and not _no[1]["tie"]
       and abs(_no[1]["pnl"] - 0.0186) < 1e-9,
       "(c) while a NO on a coin that did not tie collects its full dollar, "
       "+$0.0186 -- the tie touches only the tied coins")

    # (d) THE 09-23 RACE, replayed from planted numbers. On our index XRP
    # beat HYPE by 0.09 bp: -0.1497% vs -0.1506%, which Kalshi's 3 decimals
    # print as -0.150 vs -0.151 -- NOT a tie by the index. Kalshi tied it.
    _evt = "KXCRYPTOLEAD15M-26SEP230715"
    _cs = 1790162100
    _r923 = {"XRP": 0.998503, "HYPE": 0.998494, "ETH": 0.998207,
             "BTC": 0.998103, "SOL": 0.997127}
    _w9, _t9, _g9 = winner_from(_r923)
    ck(_w9 == "XRP" and _t9 is False and abs(_g9 - 0.09) < 1e-6
       and round(pct_move(_r923["XRP"]), 3) == -0.15
       and round(pct_move(_r923["HYPE"]), 3) == -0.151,
       "(d) the index alone calls 09-23 for XRP by %.3f bp (-0.150 vs "
       "-0.151 at 3 decimals): no arithmetic on the index reproduces the "
       "tie, which is WHY a real leg is scored from Kalshi's row" % _g9)
    # the two ledger rows, copied verbatim from the API (as pinledger's own
    # self-test carries them)
    _rows = {"KXCRYPTOLEAD15M-26SEP230715-XRP|2026-09-23T13:55:38.204233Z": {
                 "ticker": "KXCRYPTOLEAD15M-26SEP230715-XRP",
                 "market_result": "scalar", "value": 50, "revenue": 50,
                 "yes_count_fp": "1.00", "yes_total_cost_dollars": "0.970000",
                 "no_count_fp": "0.00", "fee_cost": "0.002100",
                 "settled_time": "2026-09-23T13:55:38.204233Z"},
             "KXCRYPTOLEAD15M-26SEP230715-HYPE|2026-09-23T13:55:38.204233Z": {
                 "ticker": "KXCRYPTOLEAD15M-26SEP230715-HYPE",
                 "market_result": "scalar", "value": 50, "revenue": 50,
                 "no_count_fp": "1.00", "no_total_cost_dollars": "0.980000",
                 "yes_count_fp": "0.00", "fee_cost": "0.001400",
                 "settled_time": "2026-09-23T13:55:38.204233Z"}}
    ck(ledger_values(_rows, ["KXCRYPTOLEAD15M-26SEP230715-XRP",
                             "KXCRYPTOLEAD15M-26SEP230715-HYPE", "nope"])
       == {"KXCRYPTOLEAD15M-26SEP230715-XRP": 0.5,
           "KXCRYPTOLEAD15M-26SEP230715-HYPE": 0.5},
       "(d) the ledger reads `scalar, value 50` as 50c to YES on both "
       "tickers, and a ticker with no row is ABSENT, not defaulted")
    ck(ledger_value({"market_result": "yes", "value": 100}) == 1.0
       and ledger_value({"market_result": "no", "value": 0}) == 0.0
       and ledger_value({"market_result": "yes"}) == 1.0
       and ledger_value({"market_result": "scalar"}) is None
       and ledger_value({"market_result": "scalar", "value": "junk"}) is None
       and ledger_value({"market_result": "void", "value": 140}) is None,
       "NULL: yes/no rows read 1/0 with or without `value`; a scalar with no "
       "usable value, a void, or junk is UNKNOWN -- never a guessed payout")

    def _real923():
        return [{"event": _evt, "coin": "XRP",
                 "ticker": "KXCRYPTOLEAD15M-26SEP230715-XRP", "side": "yes",
                 "price": 0.97, "size": 1.0, "tau": 2, "ask_seen": 0.97,
                 "zmin": None},
                {"event": _evt, "coin": "HYPE",
                 "ticker": "KXCRYPTOLEAD15M-26SEP230715-HYPE", "side": "no",
                 "price": 0.98, "size": 1.0, "tau": 2, "ask_seen": 0.98,
                 "zmin": None}]

    def _drive(recs):
        def _rec(kind, **kw):
            recs.append(dict(kw, kind=kind))
        return _rec

    import contextlib as _cl

    def _sp(*args, **kw):
        # settle_pass, quietly: the records are what is asserted, and its
        # console lines (a "PENNY TEST HALTED" banner among them) must not
        # appear in a startup log where a banner has to mean a halt
        with _cl.redirect_stdout(io.StringIO()):
            return settle_pass(*args, **kw)

    _recs, _st9, _bk9, _pd9 = [], {"paper": False, "rolling": True,
                                   "staked": 1.95, "stop_on_loss": True,
                                   "halted": None, "sends": 2}, \
        {"committed": 1.95}, {}
    _lp9 = _real923()
    _done = _sp(_evt, _cs, _cs + SCORE_DELAY, _r923, [], _lp9, _pd9,
                        _rows, _drive(_recs), _st9, _bk9)
    _ls = [r for r in _recs if r["kind"] == "live_settled"]
    ck(_done is True and len(_ls) == 1 and _ls[0]["source"] == "ledger"
       and _ls[0]["tie"] is True and _ls[0]["tied"] == ["HYPE", "XRP"]
       and _ls[0]["winner"] is None and abs(_ls[0]["pnl"] + 0.9535) < 1e-9
       and _ls[0]["won"] == 0 and _ls[0]["ties"] == 2,
       "(d) REPLAYED: with Kalshi's rows on the ledger the race is scored "
       "from them as a TIE -- $%+.4f, the ledger's own -$0.9535, where the "
       "old scorer booked +$0.0465 and two wins" % _ls[0]["pnl"])
    ck(abs(_lp9[0]["pnl"] + 0.4721) < 1e-9 and abs(_lp9[1]["pnl"] + 0.4814) < 1e-9
       and not _lp9[0]["win"] and not _lp9[1]["win"],
       "(d) leg by leg: XRP YES -$0.4721, HYPE NO -$0.4814, neither a win")
    ck(sum(1 for r in _recs if r["kind"] == "tie") == 2
       and all(abs(r["pnl"]) > 0.47 for r in _recs if r["kind"] == "tie"),
       "(d) each tied leg is logged as `tie` with its dollar loss")
    ck(_st9["halted"] is not None and "TIE" in _st9["halted"]
       and any(r["kind"] == "live_halt" for r in _recs),
       "(d) and the penny test HALTS on it: %r" % _st9["halted"])
    ck(abs(_st9["staked"]) < 1e-9 and abs(_bk9["committed"]) < 1e-9
       and abs(_ls[0]["released"] - 1.95) < 1e-9,
       "(d) the rolling stake is released on the scored result, once, in "
       "both books ($1.95)")

    # (d, continued) THE SAME RACE WITH NO LEDGER ROW YET: pending, held,
    # tie-suspect at the deadline, scored the moment the rows land
    _recs, _st9, _bk9, _pd9 = [], {"paper": False, "rolling": True,
                                   "staked": 1.95, "stop_on_loss": True,
                                   "halted": None, "sends": 2}, \
        {"committed": 1.95}, {}
    _lp9 = _real923()
    _d1 = _sp(_evt, _cs, _cs + SCORE_DELAY, _r923, [], _lp9, _pd9,
                      {}, _drive(_recs), _st9, _bk9)
    ck(_d1 is False and "win" not in _lp9[0] and _st9["staked"] == 1.95
       and _bk9["committed"] == 1.95 and _st9["halted"] is None
       and [r["kind"] for r in _recs] == ["awaiting_ledger"],
       "(d) with NO row on the ledger yet the race is PENDING at close+75s: "
       "not scored from the index, stake held, one `awaiting_ledger` record")
    _d2 = _sp(_evt, _cs, _cs + SCORE_DELAY + 300, _r923, [], _lp9,
                      _pd9, {}, _drive(_recs), _st9, _bk9)
    ck(_d2 is False and len(_recs) == 1,
       "(d) five minutes later, still nothing: still pending, nothing new "
       "logged (a tie's median determination is 67 min)")
    _d3 = _sp(_evt, _cs, _cs + SCORE_DELAY + LEDGER_WAIT_S, _r923, [],
                      _lp9, _pd9, {}, _drive(_recs), _st9, _bk9)
    ck(_d3 is False and "win" not in _lp9[0] and _st9["staked"] == 1.95
       and [r["kind"] for r in _recs] == ["awaiting_ledger",
                                          "unscored_tie_suspect"]
       and abs(_recs[1]["gap_bp"] - 0.09) < 1e-6,
       "(d) at the %d-minute deadline a 0.09 bp gap is a TIE SUSPECT (bar "
       "%.2f bp): `unscored_tie_suspect`, NOT scored from the index, stake "
       "still held" % (LEDGER_WAIT_S // 60, TIE_SUSPECT_BP))
    _d4 = _sp(_evt, _cs, _cs + SCORE_DELAY + LEDGER_WAIT_S + 600,
                      _r923, [], _lp9, _pd9, {}, _drive(_recs), _st9, _bk9)
    ck(_d4 is False and len(_recs) == 2,
       "(d) and it keeps waiting without repeating itself")
    _d5 = _sp(_evt, _cs, _cs + SCORE_DELAY + 3 * 3600, _r923, [],
                      _lp9, _pd9, _rows, _drive(_recs), _st9, _bk9)
    _ls = [r for r in _recs if r["kind"] == "live_settled"]
    ck(_d5 is True and len(_ls) == 1 and _ls[0]["tie"] is True
       and abs(_ls[0]["pnl"] + 0.9535) < 1e-9 and abs(_st9["staked"]) < 1e-9
       and abs(_bk9["committed"]) < 1e-9 and "TIE" in (_st9["halted"] or ""),
       "(d) three hours on, Kalshi's rows land: scored as the tie it was, "
       "stake released exactly once, rail fired")
    # the OLD behaviour, as a proof the trap is closed: the index winner on
    # this race would have paid both legs
    _old = _real923()
    score_legs(_old, leaders_of(_r923))
    ck(abs(sum(p["pnl"] for p in _old) - 0.0465) < 1e-9,
       "(d) NULL: scored from the index alone the same two legs come to "
       "+$0.0465 -- exactly the wrong number the log holds -- so the ledger "
       "path is what changed the answer, not the arithmetic")

    # the deadline for a --paper-live arm: no money held, so a tie suspect the
    # index can rank is scored from it and FLAGGED, not held for ever
    _recs, _stp, _bkp, _pdp = [], {"paper": True, "rolling": True,
                                   "staked": 1.95, "stop_on_loss": False,
                                   "halted": None, "sends": 0}, \
        {"committed": 1.95}, {}
    _lpp = _real923()
    _e1 = _sp(_evt, _cs, _cs + SCORE_DELAY, _r923, [], _lpp, _pdp, {},
                      _drive(_recs), _stp, _bkp)
    _e2 = _sp(_evt, _cs, _cs + SCORE_DELAY + LEDGER_WAIT_S, _r923, [],
                      _lpp, _pdp, {}, _drive(_recs), _stp, _bkp)
    _ls = [r for r in _recs if r["kind"] == "live_settled"]
    ck(_e1 is False and _e2 is True and len(_ls) == 1
       and _ls[0]["source"] == "index_fallback" and _ls[0]["tie_suspect"] is True
       and _ls[0]["paper"] is True and abs(_stp["staked"]) < 1e-9
       and _stp["halted"] is None,
       "(d) a --paper-live arm waits the same %d min, then scores the suspect "
       "from the index FLAGGED tie_suspect and releases its paper stake -- "
       "it never halts, and its cap cannot silt up" % (LEDGER_WAIT_S // 60))

    # (e) AN UNSCORABLE RACE (index hole) with a real leg: kept pending, scored
    # when the row appears, stake released exactly once. Until today this was
    # dropped on the first pass -- KXCRYPTOLEAD15M-26SEP220400's XRP YES at
    # 98c is in the penny log as `unscored` and was never scored.
    _ev5 = "KXCRYPTOLEAD15M-26SEP220400"
    _cs5 = 1790056800
    _recs, _st5, _bk5, _pd5 = [], {"paper": False, "rolling": True,
                                   "staked": 0.98, "stop_on_loss": True,
                                   "halted": None, "sends": 1}, \
        {"committed": 0.98}, {}
    _lp5 = [{"event": _ev5, "coin": "XRP", "ticker": _ev5 + "-XRP",
             "side": "yes", "price": 0.98, "size": 1.0, "tau": 3,
             "ask_seen": 0.98, "zmin": None}]
    _f1 = _sp(_ev5, _cs5, _cs5 + SCORE_DELAY, {}, [], _lp5, _pd5, {},
                      _drive(_recs), _st5, _bk5)
    ck(_f1 is False and "win" not in _lp5[0] and _st5["staked"] == 0.98
       and [r["kind"] for r in _recs] == ["awaiting_ledger"],
       "(e) an index hole with a real leg is PENDING, not `unscored`: the leg "
       "keeps its place and the stake is held")
    _f2 = _sp(_ev5, _cs5, _cs5 + SCORE_DELAY + LEDGER_WAIT_S, {}, [],
                      _lp5, _pd5, {}, _drive(_recs), _st5, _bk5)
    ck(_f2 is False and _st5["staked"] == 0.98
       and [r["kind"] for r in _recs] == ["awaiting_ledger", "race_pending"],
       "(e) with no index and no row at the deadline it says so once and "
       "keeps waiting -- there is nothing to fall back on")
    _row5 = {_ev5 + "-XRP|2026-09-22T08:15:38Z": {
        "ticker": _ev5 + "-XRP", "market_result": "yes", "value": 100,
        "yes_count_fp": "1.00", "settled_time": "2026-09-22T08:15:38Z"}}
    _f3 = _sp(_ev5, _cs5, _cs5 + SCORE_DELAY + LEDGER_WAIT_S + 60, {},
                      [], _lp5, _pd5, _row5, _drive(_recs), _st5, _bk5)
    _ls = [r for r in _recs if r["kind"] == "live_settled"]
    ck(_f3 is True and _lp5[0]["win"] is True and not _lp5[0]["tie"]
       and abs(_lp5[0]["pnl"] - 0.0186) < 1e-9 and len(_ls) == 1
       and _ls[0]["source"] == "ledger" and _ls[0]["winner"] == "XRP"
       and abs(_ls[0]["released"] - 0.98) < 1e-9
       and abs(_st5["staked"]) < 1e-9 and abs(_bk5["committed"]) < 1e-9
       and _st5["halted"] is None,
       "(e) the row lands (yes, 100): scored from the ledger as a win of "
       "+$0.0186, ONE live_settled, the $0.98 stake released exactly once "
       "from both books, no halt")
    _recs = []
    ck(_sp("X", 100, 100 + SCORE_DELAY, {}, [], [], {}, {},
                   _drive(_recs), {"paper": False}, {}) is True
       and [r["kind"] for r in _recs] == ["unscored"],
       "NULL: a race with NO real legs and no index is `unscored` on the "
       "first pass, exactly as before -- the retry book is for money only")

    # (f) NULL: an ordinary win and an ordinary loss book to the cent as
    # before, through the same function and through settle_pass
    _fl = [{"event": "E", "coin": "SOL", "ticker": "E-SOL", "side": "yes",
            "price": 0.97, "size": 1.0},
           {"event": "E", "coin": "BTC", "ticker": "E-BTC", "side": "no",
            "price": 0.98, "size": 1.0},
           {"event": "E", "coin": "BTC", "ticker": "E-BTC", "side": "yes",
            "price": 0.97, "size": 3.0},
           {"event": "E", "coin": "SOL", "ticker": "E-SOL", "side": "no",
            "price": 0.98, "size": 2.0}]
    score_legs(_fl, ["SOL"])

    def _old_pnl(p, win):
        return round(p["size"] * ((1.0 - p["price"]) if win else -p["price"])
                     - p["size"] * fee(p["price"]), 4)
    ck([p["win"] for p in _fl] == [True, True, False, False]
       and all(not p["tie"] for p in _fl)
       and [p["pnl"] for p in _fl] == [_old_pnl(_fl[0], True),
                                       _old_pnl(_fl[1], True),
                                       _old_pnl(_fl[2], False),
                                       _old_pnl(_fl[3], False)]
       and [p["pnl"] for p in _fl] == [0.0279, 0.0186, -2.9163, -1.9628],
       "(f) NULL: an ordinary win (+$0.0279 / +$0.0186) and an ordinary loss "
       "(-$2.9163 / -$1.9628) are booked to the cent as the old branches "
       "did -- the tie changed nothing about a race with a winner")
    _recs, _stf, _bkf = [], {"paper": False, "rolling": True, "staked": 0.97,
                             "stop_on_loss": True, "halted": None, "sends": 1}, \
        {"committed": 0.97}
    _pf = [{"event": "E", "coin": "SOL", "ticker": "E-SOL", "side": "yes",
            "price": 0.95, "size": 10, "tau": 5}]
    _lf = [{"event": "E", "coin": "BTC", "ticker": "E-BTC", "side": "yes",
            "price": 0.97, "size": 1.0, "tau": 3, "ask_seen": 0.97,
            "zmin": None}]
    _rowf = {"E-BTC|t": {"ticker": "E-BTC", "market_result": "no", "value": 0,
                         "settled_time": "t"}}
    ck(_sp("E", 10_000, 10_000 + SCORE_DELAY, rets, _pf, _lf, {},
                   _rowf, _drive(_recs), _stf, _bkf) is True
       and [r["kind"] for r in _recs] == ["settled", "live_settled", "live_halt"]
       and _recs[0]["winner"] == "SOL" and _recs[0]["tie"] is False
       and _recs[0]["won"] == 1 and abs(_recs[0]["pnl"] - 10 * (0.05 - fee(0.95))) < 1e-9
       and _recs[1]["won"] == 0 and _recs[1]["ties"] == 0
       and abs(_recs[1]["pnl"] + 0.9721) < 1e-9
       and _stf["halted"] == "first real loss: E yes at 97c"
       and abs(_stf["staked"]) < 1e-9,
       "(f) NULL, end to end: an ordinary race scores the paper leg from the "
       "index (+$%.4f), the real leg from Kalshi's row as the plain loss it "
       "was (-$0.9721), releases the stake and halts with the OLD message, "
       "word for word" % _recs[0]["pnl"])

    # the wiring: main() drops a race only when settle_pass says so, and reads
    # Kalshi's rows from the file pinledgerd keeps
    _mw = inspect.getsource(main)
    _i_sp = _mw.find("if not settle_pass(")
    _i_sa = _mw.find("scored.add(evt)")
    ck(0 <= _i_sp < _i_sa and _i_sp < _mw.find("continue", _i_sp) < _i_sa
       and _mw.count("scored.add(evt)") == 1
       and _mw.find("known.pop(evt, None)") > _i_sa,
       "main() adds a race to `scored` and pops it from `known` only AFTER "
       "settle_pass returns True -- a pending race is looked at again, "
       "which is the whole fix for the dropped real legs")
    ck("pinledger.load_cache(pinledger.LEDGER)" in _mw
       and "now - ledger_at >= LEDGER_POLL_S" in _mw,
       "and Kalshi's rows come from pinledger's cache (results/"
       "kalshi_ledger.json), re-read at most every %ds" % LEDGER_POLL_S)

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
    ck(_DEFAULT_LIVE_TAU_MAX <= 60 and _DEFAULT_LIVE_CLOCK_TAU <= 20 and
       _DEFAULT_LIVE_CONFIRM >= 3 and _DEFAULT_LIVE_MIN_PRICE >= 0.90,
       "the defaults are the measured rule: inside %ds, at %.0fc or dearer"
       % (_DEFAULT_LIVE_TAU_MAX, 100 * _DEFAULT_LIVE_MIN_PRICE))
    ck(_DEFAULT_LIVE_STOP_ON_LOSS is True,
       "and it stops dead on the first real loss by default")

    # ROLLING STAKE: settled legs give back exactly what they committed, in
    # our cap AND pintake's, and never below zero.
    _st = {"staked": 19.36}
    _lg = {"committed": 19.36}
    _rel = release_settled(_st, _lg, [{"price": 0.98, "size": 1.0},
                                      {"price": 0.97, "size": 1.0}])
    ck(abs(_rel - 1.95) < 1e-9 and abs(_st["staked"] - 17.41) < 1e-9
       and abs(_lg["committed"] - 17.41) < 1e-9,
       "ROLLING: two settled 1-contract legs at 98c and 97c release $1.95 "
       "from BOTH caps (19.36 -> %.2f / %.2f)" % (_st["staked"], _lg["committed"]))
    _st = {"staked": 0.50}
    _lg = {"committed": 0.20}
    release_settled(_st, _lg, [{"price": 0.98, "size": 1.0}])
    ck(_st["staked"] == 0.0 and _lg["committed"] == 0.0,
       "NULL: releasing more than is held floors at zero, never negative")
    ck(LIVE["rolling"] is False,
       "rolling is OFF unless --live-rolling-stake is given (the approved "
       "rail is lifetime stake)")
    _msrc = inspect.getsource(main)
    _ssrc = inspect.getsource(settle_pass)
    _i_rel = _ssrc.find("release_settled(state, stake_book, real)")
    ck(_i_rel > 0 and _ssrc.find('state.get("rolling")', _i_rel, _i_rel + 160) > 0
       and _ssrc.count("release_settled(") == 1
       and _i_rel > _ssrc.find('if v["status"] == "pending":')
       and _i_rel > _ssrc.find("return False"),
       "settle_pass releases stake only when rolling is on, at the real-leg "
       "settlement, and only AFTER the pending exit -- a race still waiting "
       "on Kalshi's row releases nothing")
    ck('stake_book = PAPER_LEDGER if LIVE["paper"] else pintake.LEDGER' in _msrc,
       "and in --paper-live it releases into its OWN book -- a process that "
       "never sends never writes to pintake's ledger")
    _pl = dict(PAPER_LEDGER)
    _lc = float(pintake.LEDGER.get("committed", 0.0))
    _pst = {"staked": 5.0}
    PAPER_LEDGER["committed"] = 3.0
    release_settled(_pst, PAPER_LEDGER, [{"price": 0.97, "size": 1.0}])
    ck(abs(PAPER_LEDGER["committed"] - 2.03) < 1e-9
       and float(pintake.LEDGER.get("committed", 0.0)) == _lc,
       "PROVEN BY RUNNING IT: releasing a paper leg moves the paper book "
       "(3.00 -> %.2f) and leaves pintake's ledger at %.2f, untouched"
       % (PAPER_LEDGER["committed"], _lc))
    PAPER_LEDGER.clear()
    PAPER_LEDGER.update(_pl)

    # THE FRESH LOOK. A REST book copied verbatim off the wire 2026-09-22,
    # when /markets quoted that market at yes ask 0.20, no ask 0.90.
    wire = {"orderbook_fp": {"no_dollars": [["0.7600", "475.00"],
                                            ["0.8000", "120.00"]],
                             "yes_dollars": [["0.0700", "2.00"],
                                             ["0.1000", "120.00"]]}}
    ck(book_ask(wire, "no") == 0.90 and book_ask(wire, "yes") == 0.20,
       "the wire book reads back as the asks /markets quoted: NO 0.90 is "
       "1 - the best YES bid, YES 0.20 is 1 - the best NO bid (got %s, %s)"
       % (book_ask(wire, "no"), book_ask(wire, "yes")))
    ck(book_ask({"orderbook_fp": {"no_dollars": [], "yes_dollars": []}},
                "no") is None and book_ask("timed out", "yes") is None
       and book_ask({"orderbook_fp": {"yes_dollars": [["0.1000", "0.00"]]}},
                    "no") is None,
       "NULL: an empty side, an error body and a zero-size level all read as "
       "NOTHING OFFERED, never as a price")
    fst = {"min_price": _DEFAULT_LIVE_MIN_PRICE,
           "max_drop": _DEFAULT_LIVE_MAX_DROP}
    ck(fresh_refusal(0.85, 0.93, fst) is not None,
       "THE 09-21 SOL LOSS IS REFUSED: seen 93c, the book was really 85c")
    ck(fresh_refusal(0.86, 0.86, fst) is not None,
       "THE 09-21 XRP LOSS IS REFUSED: 86c is under the 90c floor")
    ck(fresh_refusal(0.98, 0.98, fst) is None
       and fresh_refusal(0.97, 0.98, fst) is None
       and fresh_refusal(0.99, 0.98, fst) is None,
       "NULL: an unchanged book, a 1c improvement and a dearer book all "
       "pass -- the 24 real 94-98c fills of 09-21 would all still be sent")
    ck(fresh_refusal(0.93, 0.96, fst) is not None,
       "a 3c drop above the floor is refused too: the price fell under us")
    ck(fresh_refusal(None, 0.97, fst) is not None,
       "a failed or empty read REFUSES -- it never falls back to the old ask")
    try:
        msrc = inspect.getsource(main)
        i_fr, i_tk = msrc.find("fresh_refusal("), msrc.find("do_order(")
        ck(0 <= i_fr < i_tk,
           "main() checks the fresh book BEFORE it can reach the order path")
        ck(msrc.count("do_order(") == 1
           and 'do_order(LIVE["paper"], CREDS,' in msrc,
           "and it reaches that path exactly once, handing it the paper flag "
           "as the first thing it is told")
        ck(msrc.find('if not why and not LIVE["paper"]:') > 0,
           "the REST last look is skipped in --paper-live (fresh_ask stays "
           "null) -- it has refused 0 of 54 real sends, so the population is "
           "unchanged and a paper arm sends no authenticated request")
    except (OSError, TypeError) as e:
        ck(False, "could not read main()'s source to prove the order: %s" % e)

    # the consistency rule, on its own
    ck(inconsistent([], "BTC", "yes") is None,
       "an empty book takes any leg")
    ck(inconsistent([("BTC", "yes")], "XRP", "no") is None,
       "'BTC wins' and 'XRP does not win' AGREE -- both true when BTC wins, "
       "and the second is also true when ETH, SOL or HYPE wins")
    ck(inconsistent([("BTC", "yes"), ("XRP", "no")], "SOL", "no") is None,
       "and a third NO on another coin still agrees")
    ck(inconsistent([("BTC", "yes")], "ETH", "yes"),
       "TWO YES LEGS ARE REFUSED -- only one coin can win, so the second is "
       "a guaranteed loser. This is what 2026-09-15 did.")
    ck(inconsistent([("BTC", "yes")], "BTC", "no"),
       "YES and NO on the SAME coin are refused -- the exact $1,306 mistake")
    ck(inconsistent([("BTC", "no")], "BTC", "yes"),
       "and refused in the other order too")
    ck(inconsistent([("BTC", "no")], "BTC", "no"),
       "and the same coin twice on the same side is refused")
    ck(inconsistent([("XRP", "no"), ("SOL", "no")], "BTC", "yes") is None,
       "one YES may still be added on top of NOs on other coins")

    off = {"on": False, "max_contracts": 1, "max_stake": 20.0, "tau_max": 20,
           "min_price": 0.90, "max_legs": 2, "stop_on_loss": True,
           "races": {}, "staked": 0.0, "halted": None, "sends": 0}
    never = lambda _p: False                                  # noqa: E731
    ck(live_refusals(20, 0.95, 1, "R1", coin="BTC", side="yes", state=off,
                     exists=never),
       "DISARMED: a perfect order is still refused when --live was not given")
    on = dict(off, on=True, races={})
    ck(live_refusals(20, 0.95, 1, "R1", coin="BTC", side="yes", state=on,
                     exists=never) == [],
       "ARMED: a 95c buy of one contract 20 s out is allowed")
    on2 = dict(on, races={"R1": [("BTC", "yes")]})
    ck(live_refusals(20, 0.95, 1, "R1", coin="XRP", side="no", state=on2,
                     exists=never) == [],
       "a SECOND leg that agrees with the first is allowed in the same race")
    ck(live_refusals(20, 0.95, 1, "R1", coin="ETH", side="yes", state=on2,
                     exists=never),
       "but a second leg that contradicts it is refused")
    on3 = dict(on, races={"R1": [("BTC", "yes"), ("XRP", "no")]})
    ck(live_refusals(20, 0.95, 1, "R1", coin="SOL", side="no", state=on3,
                     exists=never),
       "and a THIRD agreeing leg is refused by the leg cap of 2")
    ck(live_refusals(20, 0.95, 1, "R2", coin="BTC", side="yes", state=on3,
                     exists=never) == [],
       "while a DIFFERENT race is still allowed")
    ck(live_refusals(20, 0.95, 1, "R1", state=on2, exists=never),
       "a leg with no coin named is refused once the race holds anything -- "
       "consistency cannot be checked blind")
    # ---- CONFIRM-OR-CLOCK ----------------------------------------------
    cs = {"confirm": 5, "clock_tau": 20}
    ck(confirm_refusal(45, 45, cs) is not None,
       "a leg seen for the first time at tau 45 does NOT fire immediately")
    ck(confirm_refusal(45, 41, cs) is not None,
       "nor after 4 of its 5 seconds")
    ck(confirm_refusal(45, 40, cs) is None,
       "and it fires once it has held the full 5 seconds")
    ck(confirm_refusal(25, 20, cs) is None,
       "the clock alone fires it at tau 20 even with 5s exactly served")
    ck(confirm_refusal(22, 19, cs) is None,
       "and inside tau 20 the clock fires it however briefly it has held")
    ck(confirm_refusal(None, 30, cs) and confirm_refusal(30, None, cs),
       "a missing arming record refuses rather than fires")
    am = {}
    ck(arm_leg(am, "R", "BTC", "yes", 50) == 50,
       "the first sighting records its own tau")
    ck(arm_leg(am, "R", "BTC", "yes", 47) == 50,
       "and a later sighting of the SAME leg keeps the first tau")
    ck(arm_leg(am, "R", "SOL", "no", 47) == 47,
       "while a DIFFERENT leg in the same race starts its own clock -- an "
       "anchor that flips has not been holding a signal, it has had two")
    ck(confirm_refusal(arm_leg(am, "R", "SOL", "no", 44), 44, cs) is not None,
       "so the flipped anchor cannot inherit the old leg's served time, which "
       "is exactly the 09-21 loss")

    ck(live_refusals(21, 0.95, 1, "R3", coin="BTC", side="yes", state=on, exists=never),
       "21 s out is refused -- the 09-21 loss fired at 40 into a one-second confidence spike; tau<=20 cuts losing races 4.5x")
    ck(live_refusals(1, 0.95, 1, "R3", coin="BTC", side="yes", state=on, exists=never),
       "and 1 s out is refused: no time to fill")
    ck(live_refusals(20, 0.79, 1, "R3", coin="BTC", side="yes", state=on, exists=never),
       "79c is refused -- below 80c the edge is timing we will not have")
    ck(live_refusals(20, 0.95, 2, "R3", coin="BTC", side="yes", state=on, exists=never),
       "two contracts is refused when the cap is one")
    ck(live_refusals(20, 0.95, 0, "R3", coin="BTC", side="yes", state=on, exists=never),
       "and zero contracts is refused rather than sent")
    ck(live_refusals(20, 0.95, 1, "R3", coin="BTC", side="yes",
                     state=dict(on, staked=19.9), exists=never),
       "a buy that would pass the total stake cap is refused")
    ck(live_refusals(20, 0.95, 1, "R3", coin="BTC", side="yes",
                     state=dict(on, halted="lost one"), exists=never),
       "nothing is sent once it has halted")
    ck(live_refusals(20, 0.95, 1, "R3", coin="BTC", side="yes", state=on, exists=lambda _p: True),
       "and the stop file refuses everything while it exists")
    ck(live_refusals(None, None, None, "R3", coin="BTC", side="yes", state=on, exists=never),
       "missing inputs refuse rather than crash")
    ck(LIVE["on"] is False and LIVE["halted"] is None,
       "the module's own live state is DISARMED at import")

    # the send must be guarded, and the race must be claimed BEFORE the send
    # so a crash mid-order cannot re-enter the same race. Anchored with
    # rindex, because a self-test that searches this file finds ITS OWN copy
    # of any string it looks for.
    #
    # THE ANCHOR IS THE CALL TO do_order, NOT THE ORDER PATH ITSELF. The one
    # order call now lives inside do_order, and while do_order sat BELOW
    # main() the old rindex of it resolved to the last two lines of the FILE
    # -- past every line of main, so `i_guard < i_claim < i_send` and the
    # rails check could not fail for any arrangement of main(). Proven by
    # running it: with the race claimed AFTER the send this file passed and
    # the pre-do_order version failed. do_order is therefore defined ABOVE
    # main, the slice below is asserted not to reach it, and the literal is
    # SPLIT below so this comment and that assertion cannot count themselves.
    _TAKE = "pintake" + ".take("            # split: see the comment above
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    ck(src.count(_TAKE) == 1,
       "there is exactly ONE call to the order path in the whole file")
    i_main = src.rindex(chr(10) + "def main(")
    ck(src.rindex(chr(10) + "def do_order(") < src.rindex(_TAKE) < i_main,
       "the only send sits inside do_order, and do_order is defined ABOVE "
       "main -- so the main-body slice below cannot anchor on it by accident")
    body = src[i_main:]
    ck(_TAKE not in body,
       "main() itself never names the order path; it goes through do_order")
    ck(body.count("do_order(") == 1,
       "and main reaches do_order exactly once, so rindex below IS the call")
    i_guard = body.rindex('if LIVE["on"]:')
    i_claim = body.rindex('LIVE["races"].setdefault(')
    i_send = body.rindex("do_order(")
    ck(i_guard < i_claim < i_send,
       "the send is inside the --live guard AND the race is claimed before "
       "the order leaves, so a crash cannot re-enter the same race")
    ck(body.rindex("live_refusals(tau") < i_send,
       "and the rails are checked before the order leaves")

    # ---- --paper-live CANNOT REACH THE ORDER PATH ----------------------
    # Read the ONE function that can send, then RUN it both ways with the
    # order path replaced by something that explodes. The source half alone
    # has been wrong before; the run is what makes it a proof.
    dsrc = inspect.getsource(do_order)
    ck(dsrc.count("pintake" + ".take(") == 1,
       "do_order is the only function that names the order path, once")
    _i_if, _i_ret = dsrc.find("if paper:"), dsrc.find("return {")
    ck(0 <= _i_if < _i_ret < dsrc.find("pintake" + ".take("),
       "and the paper arm RETURNS before the file ever mentions it "
       "(if/return/take at %d/%d/%d)"
       % (_i_if, _i_ret, dsrc.find("pintake" + ".take(")))

    class _Boom(Exception):
        pass

    def _explode(*_a, **_kw):
        raise _Boom("the order path was reached")

    _real_take = pintake.take

    def _paper(*ar):
        """do_order in paper mode; {} if it reached the exploding order path."""
        try:
            return do_order(True, *ar)
        except _Boom:
            return {}

    try:
        pintake.take = _explode
        _po = _paper({"base": None, "pk": None, "key_id": None},
                     "KXCRYPTOLEAD15M-X-BTC", "yes", 0.97, 1.0,
                     time.time() + 40, 5.0, 30)
        ck(_po.get("filled") == 1.0 and _po.get("exec_price") == 0.97
           and _po.get("paper") is True and _po.get("status") == "paper_live",
           "PROVEN BY RUNNING IT: with the order path replaced by a function "
           "that raises, --paper-live asks for 1 of the 5 offered and books "
           "1 at the 97c it saw, WITHOUT reaching it (got %s)" % (_po or _po,))
        _po2 = _paper({"base": None, "pk": None, "key_id": None},
                      "T", "no", 0.95, 4.0, time.time() + 40, 2.0, 30)
        ck(_po2.get("filled") == 2.0,
           "would_fill is min(what we asked, what was offered): 2 of the 4 "
           "asked for, because the book showed 2")
        _po3 = _paper({}, "T", "no", 0.95, 1.0, time.time() + 40, 0.0, 30)
        ck(_po3.get("filled") == 0.0,
           "NULL: an empty book fills nothing, never a negative size")
        _raised = False
        try:
            do_order(False, {"base": None, "pk": None, "key_id": None},
                     "KXCRYPTOLEAD15M-X-BTC", "yes", 0.97, 1.0,
                     time.time() + 40, 5.0, 30)
        except _Boom:
            _raised = True
        ck(_raised,
           "and the SAME call with paper=False DOES reach it and explodes -- "
           "so the paper proof above is not vacuous")
        _seen = {}

        def _record(*ar, **kw):
            _seen["args"], _seen["kw"] = ar, kw
            return {"filled": 0.0}
        pintake.take = _record
        do_order(False, {"base": "B", "pk": "PK", "key_id": "KID"},
                 "TKR", "no", 0.96, 1.0, 1234.0, 9.0, 30)
        ck(_seen["args"] == ("B", "PK", "KID", "TKR", "no", 0.96, 1.0, 1234.0)
           and _seen["kw"] == {"exchange_index": RACE_EXCHANGE_INDEX,
                               "max_tau": 30},
           "and the live arm forwards exactly what it was given, in order -- "
           "base, key, ticker, SIDE, price, count, close -- so moving the "
           "call into a function cannot have silently reordered the money "
           "path (got %s)" % (_seen["args"],))
    finally:
        pintake.take = _real_take

    # --live and --paper-live are the same switch twice
    _ap = build_parser()
    _err = io.StringIO()
    _old_err, _code = sys.stderr, None
    try:
        sys.stderr = _err
        try:
            _ap.parse_args(["--live", "--paper-live"])
        except SystemExit as e:
            _code = e.code
    finally:
        sys.stderr = _old_err
    ck(_code not in (None, 0),
       "--live and --paper-live TOGETHER exit non-zero (%s) before anything "
       "is armed -- they are one switch in two positions" % (_code,))
    ck(_ap.parse_args(["--paper-live"]).paper_live is True
       and _ap.parse_args(["--paper-live"]).live is False
       and _ap.parse_args([]).paper_live is False
       and _ap.parse_args([]).live is False,
       "each alone parses, and NEITHER is on by default")
    ck(_ap.parse_args([]).min_z == _DEFAULT_MIN_Z
       and _ap.parse_args([]).min_z_tau == _DEFAULT_MIN_Z_TAU
       and _ap.parse_args(["--min-z", "3", "--min-z-tau", "30"]).min_z == 3.0,
       "and --min-z defaults to %g (off), --min-z-tau to %d"
       % (_DEFAULT_MIN_Z, _DEFAULT_MIN_Z_TAU))

    # v-race40: the DAILY loss limit
    _t0 = calendar.timegm((2026, 9, 30, 14, 0, 0))            # 10:00 ET
    _sd = {"halted": None, "halted_day": None}
    ck(halt_active(_sd, _t0) is None, "v-race40: nothing halted -> no halt")
    _sd = {"halted": "2 losing races", "halted_day": _et_day(_t0)}
    ck(halt_active(_sd, _t0) == "2 losing races" and halt_active(_sd, _t0 + 86400) is None,
       "v-race40: a daily-limit halt holds for the rest of that ET day and expires the next ET day")
    _sd = {"halted": "first real loss", "halted_day": None}
    ck(halt_active(_sd, _t0 + 5 * 86400) == "first real loss",
       "v-race40: the first-loss stop (--live-max-losses 1, the default) never expires")
    _on40 = dict(on, halted="3 losing races", halted_day=_et_day(time.time() - 86400))
    ck(not any("halted" in x for x in live_refusals(20, 0.95, 1, "R9", coin="BTC", side="yes", state=_on40,
                                                     exists=never)),
       "v-race40: yesterday's daily-limit halt does not refuse today's order")
    _on41 = dict(on, halted="3 losing races", halted_day=_et_day(time.time()))
    ck(any("halted" in x for x in live_refusals(20, 0.95, 1, "R9", coin="BTC", side="yes", state=_on41,
                                                 exists=never)),
       "v-race40: today's daily-limit halt refuses")
    def _fx(ev):
        return ([{"event": ev, "coin": "SOL", "ticker": ev + "-SOL", "side": "yes", "price": 0.95, "size": 10, "tau": 5}],
                [{"event": ev, "coin": "BTC", "ticker": ev + "-BTC", "side": "yes", "price": 0.97, "size": 1.0, "tau": 3,
                  "ask_seen": 0.97, "zmin": None}],
                {ev + "-BTC|t": {"ticker": ev + "-BTC", "market_result": "no", "value": 0, "settled_time": "t"}})
    _recs2, _st2 = [], {"paper": False, "rolling": True, "staked": 0.97, "stop_on_loss": True,
                        "halted": None, "sends": 1, "max_losses": 2}
    _p1, _l1, _r1 = _fx("G40")
    _sp("G40", 10_000, 10_000 + SCORE_DELAY, rets, _p1, _l1, {}, _r1, _drive(_recs2), _st2, {"committed": 0.97})
    ck(_st2["halted"] is None and _st2.get("day_losses") == 1
       and [r["kind"] for r in _recs2] == ["settled", "live_settled", "live_loss"],
       "v-race40 end to end: with a limit of 2, the first losing race is logged (live_loss) and does NOT halt (%s)"
       % [r["kind"] for r in _recs2])
    _recs3 = []
    _st2["staked"] = 0.97
    _p2, _l2, _r2 = _fx("H40")
    _sp("H40", 10_000, 10_000 + SCORE_DELAY, rets, _p2, _l2, {}, _r2, _drive(_recs3), _st2, {"committed": 0.97})
    ck(bool(_st2["halted"]) and "daily limit" in (_st2["halted"] or "") and _st2["halted_day"] == _et_day(10_000)
       and [r["kind"] for r in _recs3][-1:] == ["live_halt"],
       "v-race40 end to end: the second losing race the same ET day stops live orders for the rest of that day (%s)"
       % [r["kind"] for r in _recs3])
    ck(_ap.parse_args([]).live_max_losses == 1 and _ap.parse_args(["--live-max-losses", "3"]).live_max_losses == 3,
       "v-race40: --live-max-losses defaults to 1 (the old rule) and parses")
    ck('max_losses=max(1, int(a.live_max_losses))' in body and 'pintake.set_limits(max_run_stake=LIVE["max_stake"]' in body
       and body.find("RACE_MAX_CONTRACTS_CEILING") < body.find('pintake.set_limits(max_run_stake=LIVE["max_stake"]'),
       "v-race40: the setting reaches LIVE, and the stake rail is raised only after this file's own ceiling check")

    # v-race-daystate: the day's losses survive a restart
    import tempfile as _tfd
    _ddir = _tfd.mkdtemp(prefix="racedaystate-")
    try:
        _pth = os.path.join(_ddir, "daystate.json")
        _nowd = time.time()
        _today = _et_day(_nowd)

        def _fresh():
            return dict(on, races={}, max_losses=2, day_losses=0, loss_day=None,
                        halted=None, halted_day=None)

        def _refused(st):
            return any("halted" in x for x in live_refusals(20, 0.95, 1, "R9", coin="BTC", side="yes",
                                                             state=st, exists=never))
        # (a) PLANTED: today's file with 2 losses and the daily halt
        with open(_pth, "w", encoding="utf-8") as fh:
            json.dump({"day": _today, "loss_day": _today, "day_losses": 2,
                       "halted": "2 losing races on %s ET, the daily limit -- planted" % _today,
                       "halted_day": _today}, fh)
        _stR = _fresh()
        _k, _d = restore_daystate(_stR, _pth, _nowd)
        ck(_k == "restored" and _stR["day_losses"] == 2 and _stR["halted_day"] == _today and _refused(_stR),
           "v-race-daystate: a state file from TODAY with 2 losses and the halt is restored at start, and "
           "arming refuses every order for the rest of the day (%s)" % _k)
        ck(halt_active(_stR, _nowd + 86400) is None,
           "v-race-daystate: ...and the restored halt still expires when the ET day turns")
        # (b) today's file with ONE loss, no halt: the count comes back, orders still allowed
        with open(_pth, "w", encoding="utf-8") as fh:
            json.dump({"day": _today, "loss_day": _today, "day_losses": 1, "halted": None, "halted_day": None}, fh)
        _stO = _fresh()
        ck(restore_daystate(_stO, _pth, _nowd)[0] == "restored" and _stO["day_losses"] == 1
           and _stO["loss_day"] == _today and not _refused(_stO),
           "v-race-daystate: one loss today comes back as a count of 1 and nothing is refused -- the NEXT loss halts")
        # (c) YESTERDAY's file -> ignored
        _yday = _et_day(_nowd - 86400)
        with open(_pth, "w", encoding="utf-8") as fh:
            json.dump({"day": _yday, "loss_day": _yday, "day_losses": 2,
                       "halted": "2 losing races on %s ET, the daily limit -- planted" % _yday,
                       "halted_day": _yday}, fh)
        _stY = _fresh()
        _k, _d = restore_daystate(_stY, _pth, _nowd)
        ck(_k == "stale" and _stY["day_losses"] == 0 and _stY["halted"] is None and not _refused(_stY),
           "v-race-daystate: yesterday's file is ignored -- no losses carried, nothing refused (%s)" % _k)
        # (d) a CORRUPT file -> ignored, with the reason
        with open(_pth, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        _stC = _fresh()
        _k, _d = restore_daystate(_stC, _pth, _nowd)
        ck(_k == "corrupt" and _d and _stC["halted"] is None and _stC["day_losses"] == 0 and not _refused(_stC),
           "v-race-daystate: a corrupt file is ignored and says why (%s)" % _d)
        with open(_pth, "w", encoding="utf-8") as fh:
            json.dump({"day": _today, "day_losses": 2, "halted": ["list"], "halted_day": _today}, fh)
        _stC2 = _fresh()
        ck(restore_daystate(_stC2, _pth, _nowd)[0] == "corrupt" and _stC2["halted"] is None,
           "v-race-daystate: a file with the right day but a junk halt is corrupt, not restored")
        os.remove(_pth)
        ck(restore_daystate(_fresh(), _pth, _nowd) == ("missing", None),
           "v-race-daystate: no file is `missing`, not an error")
        # (e) END TO END through settle_pass: the first loss writes the file, the second writes the halt,
        # and a restart on the same (planted) ET day picks the halt back up
        _stE = {"paper": False, "rolling": True, "staked": 0.97, "stop_on_loss": True,
                "halted": None, "sends": 1, "max_losses": 2, "daystate_path": _pth}
        _pE, _lE, _rE = _fx("D41")
        _sp("D41", 10_000, 10_000 + SCORE_DELAY, rets, _pE, _lE, {}, _rE, _drive([]), _stE, {"committed": 0.97})
        with open(_pth, encoding="utf-8") as fh:
            _disk = json.load(fh)
        ck(_disk["day_losses"] == 1 and _disk["day"] == _et_day(10_000) and not _disk["halted"],
           "v-race-daystate end to end: the first losing race writes {day, day_losses 1, no halt} to disk")
        _stE["staked"] = 0.97
        _pE2, _lE2, _rE2 = _fx("E41")
        _sp("E41", 10_000, 10_000 + SCORE_DELAY, rets, _pE2, _lE2, {}, _rE2, _drive([]), _stE, {"committed": 0.97})
        with open(_pth, encoding="utf-8") as fh:
            _disk = json.load(fh)
        ck(_disk["day_losses"] == 2 and "daily limit" in (_disk["halted"] or "")
           and _disk["halted_day"] == _et_day(10_000),
           "v-race-daystate end to end: the second writes the halt and its day")
        _stF = _fresh()
        # (the planted day is 1969-12-31 ET, so the halt is checked at THAT clock; the real-clock refusal
        # is case (a) above)
        ck(restore_daystate(_stF, _pth, 10_000)[0] == "restored" and bool(halt_active(_stF, 10_000))
           and _stF["day_losses"] == 2,
           "v-race-daystate end to end: a restart the same ET day reads the halt and the count back")
        ck(restore_daystate(_fresh(), _pth, 10_000 + 86400)[0] == "stale",
           "v-race-daystate end to end: ...and the next ET day it is stale, so the day starts clean")
        # (f) NULL: a planted state with NO daystate_path writes nothing -- the self-test and every paper
        # arm leave results/ alone
        _stN = {"paper": False, "rolling": True, "staked": 0.97, "stop_on_loss": True,
                "halted": None, "sends": 1, "max_losses": 2}
        _pN, _lN, _rN = _fx("F41")
        _sp("F41", 10_000, 10_000 + SCORE_DELAY, rets, _pN, _lN, {}, _rN, _drive([]), _stN, {"committed": 0.97})
        ck(save_daystate(_stN) is None and not os.path.exists(DAYSTATE_FILE + ".tmp"),
           "NULL: without a daystate_path nothing is written")
        # (g) the wiring: main sets the path and restores under --live only, after `rec` exists; every
        # change in settle_pass saves
        _i_dsp = body.find('LIVE["daystate_path"] = DAYSTATE_FILE')
        ck(_i_dsp > 0 and "restore_daystate(LIVE)" in body
           and 0 < _i_dsp - body.rfind("if a.live:", 0, _i_dsp) < 400
           and body.find("def rec(kind, **kw):") < body.find("restore_daystate(LIVE)")
           and body.find("restore_daystate(LIVE)") < body.find("pinrun.IndexWS("),
           "v-race-daystate wiring: main sets daystate_path and restores under --live, after rec() exists and "
           "before the loop starts")
        _settle_src = inspect.getsource(settle_pass)
        ck(_settle_src.count("save_daystate(state") == 3
           and _settle_src.find('state["halted"] = state["halted_day"] = None') < _settle_src.find("save_daystate(state")
           and _settle_src.rfind("save_daystate(state") > _settle_src.find('state["halted"] = loss_halt(evt, lost)'),
           "v-race-daystate wiring: settle_pass saves after the day reset, after the counted loss and after the "
           "first-loss halt (%d saves)" % _settle_src.count("save_daystate(state"))
    finally:
        for _x in os.listdir(_ddir):
            os.remove(os.path.join(_ddir, _x))
        os.rmdir(_ddir)

    # PRODUCTION IS ARMED ONLY IN THE --live ARM, never in --paper-live
    _i_al = body.find("if a.live:" + chr(10))
    _i_pl = body.find("elif a.paper_live:")
    ck(0 <= _i_al < body.find("arm_prod") < _i_pl
       and _i_al < body.find('CREDS["base"] = ') < _i_pl,
       "arm_prod and the credentials sit INSIDE the --live arm and before the "
       "--paper-live one, so a paper run loads no key and arms no production")
    ck(0 <= body.find("if a.live or a.paper_live:") < _i_al,
       "while the RAILS are set for both, from one block, so the paper arm "
       "runs the same rule and not a looser one")
    ck('stop_on_loss=(False if a.paper_live' in body,
       "and --paper-live forces stop_on_loss FALSE: the live test stops dead "
       "on its first loss on purpose, and an arm that halts can never reach "
       "the races its bar needs")
    ck('stop_on_loss=bool(LIVE["stop_on_loss"])' in body
       and 'min_z=float(a.min_z), min_z_tau=int(a.min_z_tau)' in body,
       "the start record says so, and carries the floor it is running, so a "
       "window can be checked instead of assumed")

    # A FLOOR THAT CAN ONLY REFUSE IS NOT A FLOOR
    ck('if a.min_z > 0 and a.model != "fair":' in body
       and body.find('if a.min_z > 0 and a.model != "fair":')
       < body.find("if not selftest():"),
       "--min-z outside --model fair is REFUSED at startup, before anything "
       "runs: no other model builds zmin, an unknown fails the floor, and "
       "the combination would have refused every leg past --min-z-tau for a "
       "week while logging like a threshold that never passed")

    # PAPER DOLLARS MUST NOT REACH THE MONEY REPORT
    # --paper-live writes `live_settled` records with a real-looking per-leg
    # `pnl`; pinday.load_race globs pinday.RACE_PAT and reads every one of
    # them as money. So the NAME is a rail, checked here, and pinday skips
    # `paper` records as the second one.
    ck(PINDAY_RACE_PAT == "pinrace*-live*.jsonl",
       "the pattern this rail guards is the one pinday actually globs "
       "(pinday.RACE_PAT) -- if that moves, this check is what notices")
    ck(paper_log_refusal("results/pinracearm-paper-live.jsonl", True)
       and paper_log_refusal(r"C:\x\results\pinracearm-z3-live.jsonl", True)
       and paper_log_refusal("pinracepenny-live.jsonl", True),
       "THE TWO NAMES A PAPER ARM WOULD NATURALLY BE GIVEN ARE REFUSED: "
       "`pinracearm-paper-live.jsonl` and `pinracearm-z3-live.jsonl` both "
       "match the day total's glob, and would have put invented dollars into "
       "the operator's real-money report with nothing failing")
    ck(paper_log_refusal("results/pinracearm-z3.jsonl", True) is None
       and paper_log_refusal("results/pinracearm-20260922T000000Z.jsonl",
                             True) is None,
       "NULL: the recommended name and the default name are both allowed -- "
       "neither matches the glob, so the rail is not just refusing everything")
    ck(paper_log_refusal("results/pinracepenny-live.jsonl", False) is None
       and paper_log_refusal(None, True) is None,
       "NULL: it says nothing about a --live log, which is SUPPOSED to be "
       "read as money, and nothing about a path that was never given")
    _i_lw = body.find("_logwhy = paper_log_refusal(logpath")
    ck(0 <= _i_lw < body.find('logf = open(logpath'),
       "and main checks the name BEFORE it opens the file, so a refused arm "
       "does not leave a half-written log behind")

    # THE RE-ARM IS CONFINED TO THE z GATE -- and SERVED ON EVERY SECOND
    _i_pop = body.find('disarm(LIVE["armed"], evt, coin, side)')
    _i_zb = body.find("zbad = z_refusal(zmin, tau, a.min_z, a.min_z_tau)")
    ck(body.count('disarm(LIVE["armed"], evt, coin, side)') == 1
       and body.count("zbad = z_refusal(zmin, tau, a.min_z, a.min_z_tau)") == 1
       and 0 <= _i_zb < _i_pop < body.find('bad = "no_book"'),
       "the floor is evaluated -- and the clock restarted -- BEFORE the book "
       "and price chain, so a race that drops under it while the ask happens "
       "to be 99c still loses its clock (A_find F4: that is the common ask "
       "in this band, so serving the floor only after `above_ceiling` would "
       "let a leg fire on a ten-second-old clock)")
    _i_z = body.find("bad = zbad")
    ck(body.count("bad = zbad") == 1
       and 0 <= body.find('bad = "thin_edge"') < _i_z,
       "and the REASON it reports still sits in the same refusal chain as "
       "thin_edge, after the edge test -- one place, not two")
    # POSITION IS NOT REACHABILITY. `elif False:` leaves every ordering check
    # above green while the gate never runs, so read the branch itself: the z
    # floor must be the `else` of the edge test, with nothing between them.
    _ml = inspect.getsource(main).split(chr(10))
    _izl = [i for i, x in enumerate(_ml) if x.strip() == "bad = zbad"]
    _prev = ([x.strip() for x in _ml[max(0, _izl[0] - 9):_izl[0]]
              if x.strip() and not x.strip().startswith("#")] if _izl else [])
    ck(len(_izl) == 1 and _prev[-1:] == ["else:"]
       and 'bad = "thin_edge"' in _prev,
       "and it is the `else` of the edge test itself -- not an `elif False:` "
       "or any other branch that can never be taken (the line above it is %r)"
       % (_prev[-1:] or None))
    # ...and the disarm must not have been quietly put back inside `if bad:`,
    # which position alone cannot tell. Read the tree: the only `disarm` call
    # in main() is guarded by `if zbad:` and by nothing else.
    import ast as _ast
    import textwrap as _tw

    def _guards(node, chain, out):
        """Every `if` a disarm() call sits under, innermost last."""
        if (isinstance(node, _ast.Call)
                and getattr(node.func, "id", None) == "disarm"):
            out.append(tuple(chain))
        if isinstance(node, _ast.If):
            t = _ast.unparse(node.test)
            _guards(node.test, chain, out)
            for s in node.body:
                _guards(s, chain + [t], out)
            for s in node.orelse:
                _guards(s, chain + ["not (%s)" % t], out)
            return
        for ch in _ast.iter_child_nodes(node):
            _guards(ch, chain, out)
    _names = []
    _guards(_ast.parse(_tw.dedent(inspect.getsource(main))), [], _names)
    ck(_names == [("zbad",)],
       "the ONE disarm in main() is guarded by `if zbad:` and by nothing "
       "else -- not nested inside `if bad:`, which is what confined it to "
       "the seconds no earlier rail had already answered (guards: %r)"
       % (_names,))
    ck(0 <= _i_z < body.rfind("if not paper_done:") < i_guard,
       "and that chain's `continue` is before BOTH the paper fill and the "
       "live block, so a refused race buys nothing on either side -- one "
       "race-level gate, not a live-only one")
    ck(body.count("zmin=(None if zmin is None") == 7
       and body.count("z=zj") == 7
       and body.count('"zmin": (None if zmin is None') == 2,
       "zmin and the four pairwise z's are written on every race record that "
       "already existed -- all four no_trade reasons, the live refusal, the "
       "paper order and the real order, plus the paper fill and the settled "
       "leg through their position dicts -- so the threshold can be re-chosen "
       "from the arm's own decisions instead of another rebuild of the tape")
    ck('"ask_seen", "zmin", "win", "pnl", "tie", "value"'
       in inspect.getsource(settle_pass),
       "and it survives to the settlement record, where a loss -- or a tie, "
       "with what the contract collected -- is scored")

    # THE 2026-09-21 15:0xZ BUG. The paper arm fills a leg once per time band
    # and used to `continue` past everything below on later seconds. The live
    # confirmation has to be SERVED second by second, so that gave every leg
    # exactly one look -- its first -- which the confirmation refuses by
    # construction, and no live order could ever fire. Both halves are
    # asserted: the band gate must exempt live, and the live block must sit
    # OUTSIDE the paper-only branch, which is what indentation says.
    ck(body.count('if paper_done and not LIVE["on"]:') == 1,
       "the once-per-band gate EXEMPTS the live path")
    ck(body.count('if not LIVE["on"]:' + chr(10)) >= 1
       and 'buyable=have, held=taken[(evt, tkr, side)],' in body,
       "and so does the book-already-ours gate, which the paper fill trips "
       "from the second second onward")
    ck('want_n = min(float(have or asz or 0),' in body,
       "the live size comes from what is OFFERED, never from the paper arm's "
       "notional take -- that is zero once the paper fill has booked the offer")
    lines = body.split(chr(10))
    ip = next(i for i, x in enumerate(lines) if x.strip() == "if not paper_done:")
    il = next(i for i, x in enumerate(lines) if x.strip() == 'if LIVE["on"]:')
    ck(il > ip, "the live block comes after the paper-only branch")
    ck(len(lines[il]) - len(lines[il].lstrip())
       == len(lines[ip]) - len(lines[ip].lstrip()),
       "and sits at the SAME indentation, so it is NOT nested inside it -- "
       "the live path runs every second the leg qualifies")
    ck("arm_prod" in body and body.index("arm_prod") > body.index("if a.live:"),
       "production is armed only under --live")

    # ---- v-race-snowball (2026-10-11): sizes follow the bank ---------------
    # Every assertion is on a _DEFAULT_ name or a planted state, never on the running LIVE dict.
    ck(_DEFAULT_CONTRACTS_PER_BANK == 0.0 and _DEFAULT_STAKE_PER_BANK == 0.0,
       "snowball: bank sizing is OFF by default (both rates 0)")
    ck(_DEFAULT_BANK_REREAD_S == 300, "snowball: the bank is re-read at most every 300 s")
    _apS = build_parser()
    _liveargv = ["--live", "--max-contracts", "20", "--max-stake", "40", "--live-max-losses", "2",
                 "--live-rolling-stake", "--live-tau-max", "30", "--live-min-price", "0.90",
                 "--live-max-legs", "5", "--live-confirm", "5", "--live-clock-tau", "20",
                 "--minutes", "10080", "--log", "C:/kals-repo/results/pinracepenny-live.jsonl",
                 "--model", "fair", "--tau-max", "60", "--min-price", "0.80", "--min-edge", "0.00"]
    _la = _apS.parse_args(_liveargv)
    ck(_la.contracts_per_bank == _DEFAULT_CONTRACTS_PER_BANK
       and _la.stake_per_bank == _DEFAULT_STAKE_PER_BANK
       and _la.max_contracts == 20.0 and _la.max_stake == 40.0,
       "snowball: TODAY'S LIVE ARGV parses with both rates off -- 20 a leg and $40 stay fixed")
    _ls = _apS.parse_args(_liveargv + ["--contracts-per-bank", "20/1050", "--stake-per-bank", "40/1050"])
    ck(_ls.contracts_per_bank == 20 / 1050.0 and _ls.stake_per_bank == 40 / 1050.0
       and _apS.parse_args(["--contracts-per-bank", "0.5"]).contracts_per_bank == 0.5,
       "snowball: --contracts-per-bank 20/1050 and --stake-per-bank 40/1050 parse as exact ratios, "
       "and a plain decimal parses too")
    _errS = io.StringIO()
    _old_errS = sys.stderr
    _codesS = []
    try:
        sys.stderr = _errS
        for _bad in ("-1", "1/0", "abc", "nan", "inf", "20/-1050"):
            try:
                _apS.parse_args(["--stake-per-bank", _bad])
                _codesS.append(0)
            except SystemExit as e:
                _codesS.append(e.code)
    finally:
        sys.stderr = _old_errS
    ck(all(c not in (None, 0) for c in _codesS),
       "snowball: a negative, zero-denominator, junk, NaN or infinite rate is refused at the command "
       "line (exit codes %s)" % _codesS)
    _X, _Y = 20 / 1050.0, 40 / 1050.0
    ck(bank_sizes(1050.0, _X, _Y, 20, 40) == (20.0, 40.0),
       "snowball: a $1,050 bank at 20/1050 and 40/1050 is today's 20 a leg and $40 open")
    ck(bank_sizes(1068.251, _X, _Y, 20, 40) == (20.0, 40.69),
       "snowball: today's real pool-2 bank ($1,068.25, read 10-11) is 20 a leg and $40.69")
    ck(bank_sizes(2100.0, _X, _Y, 20, 40) == (40.0, 80.0)
       and bank_sizes(10500.0, _X, _Y, 20, 40) == (200.0, 400.0),
       "snowball: the bank doubles -> 40 a leg and $80; x10 -> 200 a leg and $400 -- NO CEILING, the "
       "old 100-contract / $300 startup ceilings do not bind a bank-sized run")
    ck(bank_sizes(525.0, _X, _Y, 20, 40) == (10.0, 20.0)
       and bank_sizes(30.0, _X, _Y, 20, 40) == (1.0, 1.14)
       and bank_sizes(0.0, _X, _Y, 20, 40) == (1.0, 0.0),
       "snowball: it shrinks with the bank too, and never under one contract")
    ck(all(bank_sizes(52.5 * k, _X, _Y, 20, 40) == (float(k), 2.0 * k) for k in range(1, 401))
       and bank_sizes(100.0, 0.29, 0.29, 1, 1) == (29.0, 29.0),
       "snowball: float error never floors a whole number down (0.29 x 100 is 28.999... in floating "
       "point and still sizes 29 / $29.00)")
    ck(bank_sizes(5000.0, 0.0, 0.0, 20, 40) == (20.0, 40.0)
       and bank_sizes(5000.0, _X, 0.0, 20, 40) == (95.0, 40.0)
       and bank_sizes(5000.0, 0.0, _Y, 20, 40) == (20.0, 190.47),
       "NULL: a rate of 0 leaves that number at the argv's fixed value, whatever the bank")

    # THE BANK READ. Wire bodies copied from GET /portfolio/balance, 2026-10-11 08:28Z, answered by
    # the query actually sent -- so dropping `subaccount` reads every subaccount's pool 2 and FAILS.
    _wireS = {(): {"balance": 106974, "balance_dollars": "1069.7410"},
              (("exchange_index", 2),): {"balance": 129730, "balance_dollars": "1297.3012"},
              (("exchange_index", 2), ("subaccount", 0)): {"balance": 106825,
                                                            "balance_dollars": "1068.2510"},
              (("exchange_index", 0), ("subaccount", 0)): {"balance": 149, "balance_dollars": "1.4900"}}
    _askedS = []

    def _balS(path, q):
        _askedS.append((path, dict(q or {})))
        return 200, _wireS[tuple(sorted((q or {}).items()))]
    ck(read_race_bank(_balS) == (1068.251, None)
       and _askedS == [("/portfolio/balance", {"subaccount": 0, "exchange_index": 2})],
       "snowball: the bank is the MAIN account's pool-2 cash ($1,068.25), asked for by subaccount 0 "
       "AND pool 2 -- not every subaccount's pool 2 ($1,297.30) and not every pool ($1,069.74)")
    ck(read_race_bank(lambda p, q: (200, {"balance": 106825, "balance_dollars": "106825"}))[0] is None
       and read_race_bank(lambda p, q: (200, {"balance": 106825}))[0] is None
       and read_race_bank(lambda p, q: (200, {"balance_dollars": "1068.25"}))[0] is None,
       "snowball: cents read as dollars, or a body missing either unit, is REFUSED -- never a size")

    def _raiseS(*_a):
        raise OSError("timed out")
    ck(read_race_bank(lambda p, q: (500, {}))[0] is None
       and read_race_bank(lambda p, q: (200, "<html>"))[0] is None
       and read_race_bank(_raiseS)[0] is None
       and read_race_bank(lambda p, q: (200, {"balance": -100, "balance_dollars": "-1.00"}))[0] is None
       and read_race_bank(lambda p, q: (200, {"balance": "x", "balance_dollars": "y"}))[0] is None,
       "NULL: a 500, a text body, a raising getter, a negative or a junk balance all read as UNKNOWN")

    _Q = 900.0 * 2000                        # a quarter-hour close, on the exchange's grid
    _B = _Q + 300.0                          # 5:00 into the quarter hour: inside the read window
    ck(between_races([], {}, _B) is True
       and between_races([{"event": "E"}], {}, _B) is False
       and between_races([{"event": "E", "win": True}], {}, _B) is True
       and between_races([], {"E": {"close": _B + 200.0}}, _B) is False
       and between_races([], {"E": {"close": _B + RACE_BANK_QUIET_S + 1}}, _B) is True,
       "snowball: between races = no leg waiting on its result AND no open race within %d s of its "
       "close" % RACE_BANK_QUIET_S)
    ck(between_races([], {}, _Q) is False and between_races([], {}, _Q + 100.0) is False
       and between_races([], {}, _Q + RACE_BANK_AFTER_CLOSE_S - 1) is False
       and between_races([], {}, _Q + RACE_BANK_AFTER_CLOSE_S) is True
       and between_races([], {}, _Q + 900.0 - RACE_BANK_QUIET_S - 1) is True
       and between_races([], {}, _Q + 900.0 - RACE_BANK_QUIET_S) is False
       and between_races([], {}, _Q + 899.0) is False,
       "snowball: and on the quarter-hour clock only %d s after a close to %d s before the next -- the "
       "09:00:00Z paper read sat AT the close, saw $953.93 with the main bot's $115 of 09:00 bets "
       "still open, and cut 20 a leg to 18 ($1,073.99 four minutes later)"
       % (RACE_BANK_AFTER_CLOSE_S, RACE_BANK_QUIET_S))

    # bank_tick end to end, on a planted clock, bank and rails
    _bankv = [2100.0]
    _callsS = []

    def _getS(path, q):
        _callsS.append(q)
        if _bankv[0] is None:
            return 500, {}
        return 200, {"balance": int(round(_bankv[0] * 100)), "balance_dollars": "%.4f" % _bankv[0]}
    _railsS = []

    def _railok(c, s):
        _railsS.append((c, s))
        return None
    _offS = {"max_contracts": 20.0, "max_stake": 40.0, "fixed_contracts": 20.0, "fixed_stake": 40.0,
             "contracts_per_bank": _DEFAULT_CONTRACTS_PER_BANK,
             "stake_per_bank": _DEFAULT_STAKE_PER_BANK, "bank_reread_s": _DEFAULT_BANK_REREAD_S,
             "bank": None, "bank_at": None}
    ck(bank_tick(_offS, _getS, _Q + 250.0, [], {}, None, _railok) == "off" and not _callsS
       and (_offS["max_contracts"], _offS["max_stake"]) == (20.0, 40.0),
       "NULL: OFF reads nothing and changes nothing -- the running argv's behaviour")
    _bsS = dict(_offS, contracts_per_bank=_X, stake_per_bank=_Y, paper=False, rolling=True,
                staked=0.0, stop_on_loss=True, halted=None, halted_day=None, max_losses=2,
                day_losses=0, loss_day=None, sends=0)
    _rS = []
    ck(bank_tick(_bsS, _getS, _Q + 250.0, [], {}, _drive(_rS), _railok) == "resized"
       and (_bsS["max_contracts"], _bsS["max_stake"]) == (40.0, 80.0) and len(_callsS) == 1
       and _railsS == [(40.0, 80.0)] and [r["kind"] for r in _rS] == ["bank_size"],
       "snowball: the first read at a $2,100 bank resizes to 40 a leg / $80, raising pintake's rails "
       "first, and logs it")
    ck(bank_tick(_bsS, _getS, _Q + 549.0, [], {}, None, _railok) == "wait" and len(_callsS) == 1,
       "snowball: 299 s later it does not read again")
    ck(bank_tick(_bsS, _getS, _Q + 550.0, [{"event": "E"}], {}, None, _railok) == "mid_race"
       and bank_tick(_bsS, _getS, _Q + 550.0, [], {"E": {"close": _Q + 650.0}}, None,
                     _railok) == "mid_race"
       and len(_callsS) == 1,
       "snowball: at 300 s it still waits while a leg is open or a race is about to close")
    _bankv[0] = 1050.0
    ck(bank_tick(_bsS, _getS, _Q + 550.0, [], {"E": {"close": _Q + 900.0}}, None, _railok) == "resized"
       and (_bsS["max_contracts"], _bsS["max_stake"]) == (20.0, 40.0),
       "snowball: between races the bank fell to $1,050 and the size came straight back DOWN to 20 / $40")
    ck(bank_tick(_bsS, _getS, _Q + 850.0, [], {}, None, _railok) == "mid_race"
       and bank_tick(_bsS, _getS, _Q + 900.0, [], {}, None, _railok) == "mid_race"
       and bank_tick(_bsS, _getS, _Q + 1000.0, [], {}, None, _railok) == "mid_race"
       and len(_callsS) == 2,
       "snowball: with nothing open and nothing listed, the CLOCK alone still refuses 50 s before a "
       "close, at the close and 100 s after it")
    _bankv[0] = None
    _rF = []
    ck(bank_tick(_bsS, _getS, _Q + 1150.0, [], {}, _drive(_rF), _railok) == "failed"
       and (_bsS["max_contracts"], _bsS["max_stake"]) == (20.0, 40.0)
       and [r["kind"] for r in _rF] == ["bank_read_failed"],
       "snowball: a failed read holds the last good size and logs why")
    _bankv[0] = 2100.0
    _rR = []
    ck(bank_tick(_bsS, _getS, _Q + 1450.0, [], {}, _drive(_rR), lambda c, s: "planted refusal") == "refused"
       and (_bsS["max_contracts"], _bsS["max_stake"]) == (20.0, 40.0)
       and [r["kind"] for r in _rR] == ["bank_resize_refused"],
       "snowball: if pintake will not admit the new size, the old size is held -- a size the order "
       "path refuses is never set")
    ck(bank_tick(_bsS, _getS, _Q + 2050.0, [], {}, None, _railok) == "resized"
       and _bsS["max_contracts"] == 40.0,
       "snowball: and the next good read applies it")
    # the new size is what the live rails read
    _onS = dict(on, max_contracts=_bsS["max_contracts"], max_stake=_bsS["max_stake"])
    ck(live_refusals(20, 0.95, 40, "RS", coin="BTC", side="yes", state=_onS, exists=never) == []
       and live_refusals(20, 0.95, 40, "RS", coin="BTC", side="yes",
                         state=dict(on, max_contracts=20.0, max_stake=40.0), exists=never),
       "snowball: a 40-contract leg passes the live rails at the bank-sized cap and is refused at 20")
    # the 2-losses-a-day stop and the tie-is-a-loss rule, with bank sizing on
    _pT, _lT, _rT = _fx("SNOWT")
    _lT[0]["size"] = 40.0
    _rT = {"SNOWT-BTC|t": {"ticker": "SNOWT-BTC", "market_result": "scalar", "value": 50,
                           "settled_time": "t"}}
    _bsS["staked"] = 0.97 * 40
    _recT = []
    _sp("SNOWT", 10_000, 10_000 + SCORE_DELAY, rets, _pT, _lT, {}, _rT, _drive(_recT), _bsS,
        {"committed": 0.97 * 40})
    ck(_bsS["day_losses"] == 1 and _bsS["halted"] is None
       and [r["kind"] for r in _recT][-3:] == ["tie", "live_settled", "live_loss"],
       "snowball: a 40-contract TIE is still a loss -- counted 1 of 2, no halt yet (%s)"
       % [r["kind"] for r in _recT])
    ck(bank_tick(_bsS, _getS, _Q + 2350.0, [], {}, None, _railok) == "same"
       and _bsS["day_losses"] == 1 and _bsS["halted"] is None and _bsS["max_losses"] == 2
       and _bsS["stop_on_loss"] is True,
       "snowball: a bank read touches no loss rail -- the count, the limit and the stop are as they were")
    _pL, _lL, _rL = _fx("SNOWL")
    _lL[0]["size"] = 40.0
    _bsS["staked"] = 0.97 * 40
    _sp("SNOWL", 10_000, 10_000 + SCORE_DELAY, rets, _pL, _lL, {}, _rL, _drive([]), _bsS,
        {"committed": 0.97 * 40})
    ck(bool(_bsS["halted"]) and "daily limit" in _bsS["halted"],
       "snowball: and the second losing race the same ET day still stops it for the day")
    # pintake's rails really move, one way only (its globals are restored afterwards)
    _savedS = (pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE, pintake.HARD_MAX)
    try:
        pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE, pintake.HARD_MAX = 20.0, 40.0, 25.0
        with _cl.redirect_stdout(io.StringIO()):
            _r1 = raise_pintake_rails(40.0, 80.0)
            _hi = (pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE, pintake.HARD_MAX)
            _r2 = raise_pintake_rails(10.0, 20.0)
        ck(_r1 is None and _hi[0] >= 40.0 and _hi[2] >= 40.0 and _hi[1] >= 80.0,
           "snowball: a 40 / $80 size raises pintake's per-order count, its HARD_MAX and its run-stake "
           "rail to admit it (now %g / %g / $%.2f)" % (_hi[0], _hi[2], _hi[1]))
        ck(_r2 is None and (pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE, pintake.HARD_MAX) == _hi,
           "snowball: a smaller size asks pintake for nothing and lowers nothing -- this file's own "
           "cap, checked first, is the stricter one")
    finally:
        pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE, pintake.HARD_MAX = _savedS
    # the wiring in main()
    _mS = inspect.getsource(main)
    ck(_mS.count("bank_tick(") == 1
       and _mS.find("events = discover()") < _mS.find("bank_tick(LIVE, bank_getter, now, live_pos, events, rec)")
       < _mS.find("# ---- SCORE"),
       "snowball wiring: main calls bank_tick once a loop pass, after discovery and before scoring "
       "and pricing, on the LIVE dict the rails read")
    ck(0 <= _mS.find("if _bank_flags and not (a.live or a.paper_live):") < _mS.find("if not selftest():"),
       "snowball wiring: the bank flags without --live or --paper-live are REFUSED at startup")
    ck(_mS.find("LIVE.update(on=True") < _mS.find("LIVE.update(contracts_per_bank=float(a.contracts_per_bank)")
       < _mS.find("REFUSING TO ARM -- stop file present"),
       "snowball wiring: the rates reach LIVE from the command line inside the arming block")
    ck("pintake._get(CREDS[\"base\"], CREDS[\"pk\"]" in _mS and "bank_getter = kauth.get" in _mS
       and _mS.find("bank_getter = None") < _mS.find("bank_getter = kauth.get"),
       "snowball wiring: --live reads the bank with the live key like pinrun; --paper-live through "
       "kauth, which can only GET; off = no getter, so nothing is read")

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


def build_parser():
    """The command line, built where a self-test can reach it -- so that
    "--live and --paper-live together are refused" is a test, not a claim."""
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
    mx = ap.add_mutually_exclusive_group()
    mx.add_argument("--live", action="store_true",
                    help="THE PENNY TEST: send REAL orders at minimum size "
                         "alongside the paper record, to measure our own fill "
                         "rate and our own loss rate. Operator sign-off "
                         "2026-09-21.")
    mx.add_argument("--paper-live", action="store_true",
                    help="run the ENTIRE live decision path -- arming, the "
                         "confirmation, the per-race consistency rule and "
                         "every --live-* rail -- and send NOTHING. Writes "
                         "`live_paper` records with the fill it would have "
                         "got at the ask it saw, scores them through "
                         "live_settled, never halts on a loss, and never "
                         "touches the order path. Refused with --live.")
    ap.add_argument("--max-contracts", type=float,
                    default=_DEFAULT_LIVE_MAX_CONTRACTS,
                    help="live: contracts per race (default %g)"
                         % _DEFAULT_LIVE_MAX_CONTRACTS)
    ap.add_argument("--live-max-losses", type=int, default=1,
                    help="live: stop for the rest of the ET day after this many losing races; 1 (default) = stop "
                         "for good on the first loss, the penny-test rule")
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
    ap.add_argument("--live-confirm", type=int, default=_DEFAULT_LIVE_CONFIRM,
                    help="live: seconds the same leg must keep qualifying "
                         "before it fires (default %d)" % _DEFAULT_LIVE_CONFIRM)
    ap.add_argument("--live-clock-tau", type=int,
                    default=_DEFAULT_LIVE_CLOCK_TAU,
                    help="live: fire anyway once the clock reaches this, "
                         "confirmed or not (default %d)"
                         % _DEFAULT_LIVE_CLOCK_TAU)
    ap.add_argument("--live-rolling-stake", action="store_true",
                    help="live: --max-stake bounds what is OPEN, not every "
                         "bet ever placed -- settled legs give their stake back "
                         "(the first-loss halt still bounds the total)")
    ap.add_argument("--live-max-legs", type=int, default=_DEFAULT_LIVE_MAX_LEGS,
                    help="live: AGREEING legs per race -- one YES at most, "
                         "NOs on other coins, never a coin twice (default %d)"
                         % _DEFAULT_LIVE_MAX_LEGS)
    ap.add_argument("--min-z", type=float, default=_DEFAULT_MIN_Z,
                    help="RACE-LEVEL floor: refuse EVERY leg of a race whose "
                         "leader is under this many standard deviations clear "
                         "of every other coin. NEEDS --model fair, which is "
                         "the only model that builds the number; under any "
                         "other model it is unknown and an unknown FAILS the "
                         "floor, so a non-zero value there refuses every leg "
                         "past --min-z-tau. 0 = off (default %.1f)"
                         % _DEFAULT_MIN_Z)
    ap.add_argument("--min-z-tau", type=int, default=_DEFAULT_MIN_Z_TAU,
                    help="--min-z applies only PAST this many seconds out; at "
                         "or inside it nothing changes (default %d)"
                         % _DEFAULT_MIN_Z_TAU)
    # v-race-snowball (2026-10-11): OFF by default -- the running argv is unaffected
    ap.add_argument("--contracts-per-bank", type=per_bank,
                    default=_DEFAULT_CONTRACTS_PER_BANK,
                    help="live/paper-live: contracts a leg = max(1, floor(bank x THIS)), bank = the "
                         "main account's pool-2 cash, re-read at most every %d s and only between "
                         "races. A decimal or a ratio: 20/1050 is 20 a leg at a $1,050 bank. "
                         "0 = off, --max-contracts stays fixed (default %g)"
                         % (_DEFAULT_BANK_REREAD_S, _DEFAULT_CONTRACTS_PER_BANK))
    ap.add_argument("--stake-per-bank", type=per_bank,
                    default=_DEFAULT_STAKE_PER_BANK,
                    help="live/paper-live: the open-stake cap = bank x THIS (40/1050 is $40 at a "
                         "$1,050 bank). 0 = off, --max-stake stays fixed (default %g)"
                         % _DEFAULT_STAKE_PER_BANK)
    return ap


def do_order(paper, creds, ticker, side, ask, count, close_s, supply, tau_max):
    """THE ONLY PLACE AN ORDER CAN LEAVE THIS FILE.

    `paper` is --paper-live. It returns the fill we WOULD have got -- the
    smaller of what we asked for and what the book was offering, at the ask we
    saw -- and never touches the order path. Two things prove that and both
    are in the self-test: this function's own source (the return is above the
    call, and the call appears exactly once), and a run with `pintake.take`
    replaced by something that raises, where the paper arm returns normally
    and the live arm raises. The second half is what makes the first
    non-vacuous.

    It is one function rather than two branches inline so that the proof can
    be a RUN and not only a reading. `creds` is untouched in paper mode -- in
    --paper-live it is never even loaded, so a bug that reached the wire would
    find base=None and be refused by pintake anyway."""
    if paper:
        return {"paper": True, "status": "paper_live", "status_code": None,
                "filled": max(0.0, min(float(count), float(supply))),
                "exec_price": float(ask), "refused": None, "fee_total": None,
                "order_id": None, "client_order_id": None}
    return pintake.take(creds["base"], creds["pk"], creds["key_id"],
                        ticker, side, float(ask), count, float(close_s),
                        exchange_index=RACE_EXCHANGE_INDEX, max_tau=tau_max)


def main():
    a = build_parser().parse_args()
    if a.live and a.paper_live:
        # argparse refuses this before we get here; this is the belt to that
        # pair of braces, for a caller that builds the namespace itself.
        print("  REFUSED -- --live and --paper-live are the same switch in "
              "two positions; give exactly one")
        return 2
    if a.min_z > 0 and a.model != "fair":
        # `zmin` is built in live_fair(), which only --model fair calls. Under
        # any other model it is None, and None FAILS the floor by design -- so
        # this combination would refuse EVERY leg past --min-z-tau while
        # reading, in the log, like a threshold that simply never passed. Say
        # it at startup instead of discovering it from an empty week.
        print("  REFUSED -- --min-z %.2f needs --model fair. %r never builds "
              "the number, and an unknown fails the floor, so every leg past "
              "%ds would be refused `zmin_under_floor` with zmin null."
              % (a.min_z, a.model, a.min_z_tau))
        return 2
    _bank_flags = a.contracts_per_bank > 0 or a.stake_per_bank > 0
    if _bank_flags and not (a.live or a.paper_live):
        # v-race-snowball: the bank sizes the LIVE decision path only. A plain paper arm sizes from
        # --size and would silently ignore it -- say so instead of running a week that tests nothing.
        print("  REFUSED -- --contracts-per-bank / --stake-per-bank size the live decision path; "
              "give --live or --paper-live")
        return 2
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
    if a.live or a.paper_live:
        # ARM THE LIVE DECISION PATH. Every rail is set from the command line
        # here and nowhere else, and the refusal list is printed before a
        # single market is watched so the operator can read what is bounded.
        # --paper-live takes this identical path and sends nothing.
        LIVE.update(on=True, paper=bool(a.paper_live),
                    max_losses=max(1, int(a.live_max_losses)),
                    max_contracts=float(a.max_contracts),
                    max_stake=float(a.max_stake),
                    tau_max=int(a.live_tau_max),
                    min_price=float(a.live_min_price),
                    max_legs=max(1, int(a.live_max_legs)),
                    confirm=max(0, int(a.live_confirm)),
                    clock_tau=max(1, int(a.live_clock_tau)),
                    rolling=bool(a.live_rolling_stake),
                    # PAPER-LIVE NEVER HALTS. The live test stops dead on its
                    # first loss on purpose -- the first real loss is the
                    # answer arriving. An arm that halts can never reach the
                    # 125 early races its bar needs, and it is risking
                    # nothing by carrying on.
                    stop_on_loss=(False if a.paper_live
                                  else _DEFAULT_LIVE_STOP_ON_LOSS))
        # v-race-snowball: the argv's fixed sizes are what trades until the first good bank read,
        # and what a rate of 0 keeps for good. The bank tick in the loop is the only thing that moves them.
        LIVE.update(contracts_per_bank=float(a.contracts_per_bank),
                    stake_per_bank=float(a.stake_per_bank),
                    bank_reread_s=_DEFAULT_BANK_REREAD_S,
                    fixed_contracts=LIVE["max_contracts"], fixed_stake=LIVE["max_stake"],
                    bank=None, bank_at=None)
        if os.path.exists(LIVE_STOP_FILE):
            print("  REFUSING TO ARM -- stop file present: %s" % LIVE_STOP_FILE)
            return 1
        # v-race20 (2026-09-28): pintake's per-take rail ships at 10 for this
        # process; a larger --max-contracts up to pintake.HARD_MAX (25) RAISES
        # it through pintake's own one-way ratchet (printed, never silent).
        # Above HARD_MAX the refusal below still fires.
        if (LIVE["max_contracts"] > RACE_MAX_CONTRACTS_CEILING
                or LIVE["max_stake"] > RACE_MAX_STAKE_CEILING):
            print("  REFUSING TO ARM -- over this file's own ceilings (%g contracts, $%.2f)"
                  % (RACE_MAX_CONTRACTS_CEILING, RACE_MAX_STAKE_CEILING))
            return 1
        if pintake.MAX_TAKE_COUNT < LIVE["max_contracts"]:
            # v-race40: pintake.set_limits raises HARD_MAX too when asked past it, and prints both
            pintake.set_limits(max_take_count=LIVE["max_contracts"],
                               why="--max-contracts (v-race20 / v-race40)")
        if pintake.MAX_RUN_STAKE < LIVE["max_stake"]:
            pintake.set_limits(max_run_stake=LIVE["max_stake"],
                               why="--max-stake (v-race40, operator 2026-09-30)")
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
    if a.live:
        import kauth
        import ordercli
        CREDS["base"] = pintake.PROD_ELECTIONS
        CREDS["key_id"] = kauth.KEY_ID
        CREDS["pk"] = ordercli.load_key(pintake.PROD_KEY_FILE)
        pintake.arm_prod("coin race penny test, operator sign-off 2026-09-21")
        print("\n  *** REAL MONEY ARMED -- THE PENNY TEST ***")
        print("  at most %g contract(s) a leg and %d AGREEING legs a race"
              % (LIVE["max_contracts"], LIVE["max_legs"]))
        print("  (one YES at most, NOs only on other coins, never a coin twice),")
        print("  only inside %d s, only at %.0fc or dearer, at most $%.2f"
              % (LIVE["tau_max"], 100 * LIVE["min_price"], LIVE["max_stake"]))
        print("  and a leg must keep qualifying for %d s before it fires, or"
              % LIVE["confirm"])
        print("  the clock must have run down to %d s -- whichever comes first,"
              % LIVE["clock_tau"])
        print("  %s, and it STOPS DEAD on the first losing"
              % ("OPEN at any moment (rolling: settled bets give their stake "
                 "back)" if LIVE["rolling"] else "committed in total"))
        print("  race. Halt it any time with:  type nul > %s" % LIVE_STOP_FILE)
    elif a.paper_live:
        print("\n  *** PAPER-LIVE -- THE LIVE DECISION PATH, NOTHING SENT ***")
        print("  No credentials are loaded, production is never armed, and the")
        print("  order path is never reached. Every other rail is the live one:")
        print("  at most %g contract(s) a leg and %d AGREEING legs a race,"
              % (LIVE["max_contracts"], LIVE["max_legs"]))
        print("  only inside %d s, only at %.0fc or dearer, at most $%.2f %s,"
              % (LIVE["tau_max"], 100 * LIVE["min_price"], LIVE["max_stake"],
                 "open at any moment" if LIVE["rolling"] else "in total"))
        print("  %d s of confirmation or the clock at %d s, whichever first."
              % (LIVE["confirm"], LIVE["clock_tau"]))
        print("  It does NOT stop on a loss (stop_on_loss=%s) -- an arm that"
              % LIVE["stop_on_loss"])
        print("  halts can never reach the races its bar needs, and it risks")
        print("  nothing. The REST last look is skipped (fresh_ask is null).")
        print("  ITS FILL RATE IS NOT EVIDENCE: `would_fill` is the smaller")
        print("  of what we asked for and what the book was OFFERING, and the")
        print("  size we ask for is built from that same number -- so it is")
        print("  always 100%. Whether the offer would have been OURS is the")
        print("  one thing no paper arm can test, and both real race losses")
        print("  filled at prices a once-a-second tape never showed.")
        print("  It is also stood down by %s, the MONEY test's switch."
              % os.path.basename(LIVE_STOP_FILE))
    # v-race-snowball: who reads the bank. --live reads it the way pinrun does (pintake's signed GET,
    # the live key); --paper-live through kauth, which can only GET. None = bank sizing off.
    bank_getter = None
    if _bank_flags:
        if a.live:
            bank_getter = (lambda _p, _q: pintake._get(CREDS["base"], CREDS["pk"],
                                                       CREDS["key_id"], _p, _q))
        else:
            import kauth
            bank_getter = kauth.get
        print("  BANK-SIZED: contracts a leg = %s, open-stake cap = %s;"
              % ("max(1, floor(bank x %.8g))" % LIVE["contracts_per_bank"]
                 if LIVE["contracts_per_bank"] > 0 else "fixed %g" % LIVE["max_contracts"],
                 "bank x %.8g" % LIVE["stake_per_bank"]
                 if LIVE["stake_per_bank"] > 0 else "fixed $%.2f" % LIVE["max_stake"]))
        print("  bank = the main account's pool-2 cash, re-read at most every %d s and only"
              % LIVE["bank_reread_s"])
        print("  between races (%d:%02d to %d:%02d into each quarter hour). Until the first good"
              % (RACE_BANK_AFTER_CLOSE_S // 60, RACE_BANK_AFTER_CLOSE_S % 60,
                 (900 - RACE_BANK_QUIET_S) // 60, (900 - RACE_BANK_QUIET_S) % 60))
        print("  read: %g a leg, $%.2f." % (LIVE["max_contracts"], LIVE["max_stake"]))

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logpath = a.log or os.path.join(REPO, "results",
                                    "pinracearm-%s.jsonl" % stamp)
    _logwhy = paper_log_refusal(logpath, LIVE["paper"])
    if _logwhy:
        print("  REFUSED -- %s" % _logwhy)
        return 2
    logf = open(logpath, "a", encoding="utf-8")

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logf.write(json.dumps(kw) + "\n")
        logf.flush()

    print("\n  COIN RACE %s" % ("PENNY TEST -- REAL ORDERS, see the rails above"
                                if a.live else
                                "PAPER-LIVE -- the live rule, nothing sent"
                                if a.paper_live else
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
        table_size=tstat.st_size, version="2026-09-24-tie1",
        tau_max=a.tau_max, min_gap_bp=a.min_gap_bp, min_price=a.min_price,
        one_per_race_band=bool(a.one_per_race_band), model=a.model,
        # THE ARM'S OWN IDENTITY, so a window can be checked rather than
        # assumed: the bar in C_plan section 4 runs only while the argv is
        # byte-identical, and its first validity gate reads min_z here.
        min_z=float(a.min_z), min_z_tau=int(a.min_z_tau),
        live=bool(a.live), paper_live=bool(a.paper_live),
        stop_on_loss=bool(LIVE["stop_on_loss"]),
        argv=list(sys.argv[1:]),
        live_rails=({k: LIVE[k] for k in
                     ("max_contracts", "max_stake", "tau_max", "min_price",
                      "max_legs", "confirm", "clock_tau", "rolling",
                      "stop_on_loss", "paper")} if LIVE["on"] else None),
        bank_sizing=({"contracts_per_bank": LIVE["contracts_per_bank"],
                      "stake_per_bank": LIVE["stake_per_bank"],
                      "reread_s": LIVE["bank_reread_s"],
                      "query": dict(RACE_BANK_QUERY)} if bank_getter else None))
    if a.live:
        # v-race-daystate: today's losses and halt come back from disk, so a
        # restart cannot launder the daily limit. --live ONLY: a paper arm
        # never writes or reads the file.
        LIVE["daystate_path"] = DAYSTATE_FILE
        _dk, _dd = restore_daystate(LIVE)
        rec("daystate_restored" if _dk == "restored" else "daystate_ignored",
            what=_dk, detail=_dd, path=DAYSTATE_FILE,
            day_losses=LIVE.get("day_losses"), halted=LIVE.get("halted"))
        if _dk == "restored":
            print("  day state restored from %s: %d losing race(s) today%s"
                  % (os.path.basename(DAYSTATE_FILE), int(LIVE.get("day_losses") or 0),
                     " -- STILL STOPPED FOR THE DAY: %s" % LIVE["halted"]
                     if halt_active(LIVE) else ""))
        elif _dk != "missing":
            print("  day state file %s %s -- ignored (%s)"
                  % (os.path.basename(DAYSTATE_FILE), _dk, _dd))

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
    pending = {}                            # event -> once-logged kinds
    ledger_rows = {}                        # Kalshi's settlements, cached
    ledger_at = 0.0
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

            # ---- v-race-snowball: re-size from the bank, between races only ----
            if bank_getter is not None:
                _was = (LIVE["max_contracts"], LIVE["max_stake"])
                _bt = bank_tick(LIVE, bank_getter, now, live_pos, events, rec)
                if _bt in ("resized", "failed", "refused"):
                    print("  BANK %s: $%s -> %g a leg, $%.2f open cap (was %g / $%.2f)"
                          % (_bt, "?" if LIVE["bank"] is None else "%.2f" % LIVE["bank"],
                             LIVE["max_contracts"], LIVE["max_stake"], _was[0], _was[1]))

            # ---- SCORE anything that has closed and settled ------------
            # A race leaves `known` and enters `scored` ONLY when settle_pass
            # says it is done. A race with real legs and no Kalshi row yet is
            # PENDING: looked at again next pass, its stake held. Until
            # 2026-09-24 an unscorable race was added to `scored` and popped
            # from `known` BEFORE the unscored check, so its real legs were
            # never scored and the rolling stake never released.
            for evt, e in sorted(known.items()):
                cs = int(e["close"])
                if evt in scored or now < cs + SCORE_DELAY:
                    continue
                with idx.lock:
                    tb = {c: dict(idx.ticks.get(iid) or {})
                          for c, iid in COINS.items()}
                rets = race_returns(tb, cs)
                if (any(p["event"] == evt and "win" not in p for p in live_pos)
                        and now - ledger_at >= LEDGER_POLL_S):
                    # KALSHI'S OWN RESULT, from the file pinledgerd refreshes
                    # every 60 s -- read here at most every LEDGER_POLL_S, and
                    # only while a race with real legs is waiting on it.
                    ledger_rows = pinledger.load_cache(pinledger.LEDGER)
                    ledger_at = now
                # --paper-live releases into ITS OWN book. A process that
                # never sends must never write to pintake's ledger.
                stake_book = PAPER_LEDGER if LIVE["paper"] else pintake.LEDGER
                if not settle_pass(evt, cs, now, rets, fills, live_pos,
                                   pending, ledger_rows, rec, LIVE, stake_book):
                    continue                     # pending: NOT scored, NOT dropped
                scored.add(evt)
                known.pop(evt, None)

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
                # THE RACE-LEVEL z, computed once per (race, second) with the
                # probabilities and cached with them. None outside --model
                # fair, and None FAILS the floor (z_refusal).
                zmin, zj = None, None
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
                    fprobs, ruler, zmin, zj = fair_cache[fk]
                    zj = ({k: (None if v is None else round(v, 4))
                           for k, v in (zj or {}).items()} or None)
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
                    if band is None:
                        continue
                    # THE RACE-LEVEL FLOOR IS SERVED ON EVERY SECOND, not
                    # only on the seconds that survive the book-and-price
                    # chain below. `zmin` is built from the INDEX alone -- it
                    # does not depend on the ask, the edge or the side -- and
                    # A_find F4 measured that a 99c ask during the qualifying
                    # seconds is the COMMON case in this band (in 4 of 5, the
                    # market never offered the leader at 90-98c while it
                    # qualified). Evaluating the floor only where
                    # `above_ceiling`, `no_book` or `thin_edge` did not fire
                    # first would leave a leg armed on its ORIGINAL clock
                    # through seconds its race was under the floor, so it
                    # would fire on a stale one -- the exact thing the re-arm
                    # exists to stop. So the floor is COMPUTED here, for the
                    # re-arm, and REPORTED below as the `else` of the edge
                    # test, which is where C_plan 2e puts the refusal reason.
                    # `--min-z 0` makes z_refusal return None at every tau, so
                    # the live penny argv decides exactly what it does today.
                    zbad = z_refusal(zmin, tau, a.min_z, a.min_z_tau)
                    if zbad:
                        disarm(LIVE["armed"], evt, coin, side)
                    # ONE PAPER FILL PER LEG PER BAND -- but the LIVE path must
                    # still be looked at every second. CONFIRM-OR-CLOCK needs a
                    # leg re-examined second after second to serve its
                    # confirmation; gating the whole branch on done_band gave
                    # each leg exactly ONE look per band, always its first,
                    # which the confirmation refuses by construction. That is
                    # why no live order fired between 2026-09-21 14:25Z and
                    # 15:0xZ: the rule was right and the loop never asked it
                    # twice.
                    paper_done = ((evt, tkr, side, band) in done_band
                                  or (a.one_per_race_band
                                      and (evt, band) in race_band_done))
                    if paper_done and not LIVE["on"]:
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
                                    gap_bp=round(gap * 1e4, 4),
                                    zmin=(None if zmin is None
                                          else round(zmin, 4)), z=zj)
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
                                gap_bp=round(gap * 1e4, 4),
                                zmin=(None if zmin is None
                                      else round(zmin, 4)), z=zj)
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
                        else:
                            # THE RACE-LEVEL z FLOOR, last in the chain and in
                            # the same chain as thin_edge, exactly where
                            # C_plan 2e puts it. Off at --min-z 0, and silent
                            # at or inside --min-z-tau. The re-arm that goes
                            # with it already happened above, because it must
                            # also happen on the seconds an earlier rail
                            # answered first.
                            bad = zbad
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
                                      else round(edge, 6)),
                                zmin=(None if zmin is None
                                      else round(zmin, 4)), z=zj)
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
                                buyable=have, held=taken[(evt, tkr, side)],
                                zmin=(None if zmin is None
                                      else round(zmin, 4)), z=zj)
                        # THE SECOND STARVATION, 2026-09-21. The paper fill
                        # books the WHOLE offer into `taken`, so from the next
                        # second on take_size returns 0 and this used to
                        # `continue` -- starving the live path exactly the way
                        # the band gate did. The penny test buys ONE contract;
                        # what the paper arm notionally consumed is none of its
                        # business. Its own size comes from `have` below.
                        if not LIVE["on"]:
                            continue
                        paper_done = True
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
                           "model": a.model, "ruler": ruler,
                           "zmin": (None if zmin is None else round(zmin, 4)),
                           "z": zj}
                    if not paper_done:
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
                              % (evt[-12:], coin, side.upper(), take,
                                 100 * ask, tau, gap * 1e4, worth,
                                 100 * pos["edge"]))

                    # ---- THE PENNY TEST. Real money, one race at a time. ----
                    # Reached EVERY second the leg qualifies, not only the
                    # first of its band, because the confirmation has to be
                    # served second by second.
                    if LIVE["on"]:
                        # sized from what is OFFERED, never from the paper
                        # arm's notional `take` -- which is zero once the
                        # paper fill has booked the whole offer
                        want_n = min(float(have or asz or 0),
                                     float(LIVE["max_contracts"]))
                        first_tau = arm_leg(LIVE["armed"], evt, coin, side,
                                            tau)
                        why = live_refusals(tau, float(ask), want_n, evt,
                                            coin=coin, side=side)
                        cw = confirm_refusal(first_tau, tau)
                        if cw:
                            why = list(why) + [cw]
                        fresh = None
                        if not why and not LIVE["paper"]:
                            # LAST LOOK, over REST, after every other rail
                            # has passed -- so it costs a request only when
                            # we were about to send.
                            #
                            # SKIPPED IN --paper-live, and `fresh_ask` stays
                            # null. Measured 2026-09-22 across 54 real sends
                            # and all 3,548 `live_refused` records: the fresh
                            # read has refused ZERO sends, so skipping it does
                            # not change the population -- and an arm that
                            # cannot send has no business making an
                            # authenticated request per would-send.
                            fst, fob = pintake._get(
                                CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                "/markets/%s/orderbook" % tkr)
                            fresh = book_ask(fob, side) if fst == 200 else None
                            fw = fresh_refusal(fresh, float(ask))
                            if fw:
                                why = [fw + " (http %s)" % fst]
                        if why:
                            rec("live_refused", event=evt, ticker=tkr,
                                side=side, tau=tau, price=float(ask),
                                count=want_n, why=why, fresh_ask=fresh,
                                paper=LIVE["paper"],
                                zmin=(None if zmin is None
                                      else round(zmin, 4)), z=zj)
                        else:
                            # claimed BEFORE the send, so a crash cannot
                            # re-enter and break the consistency rule
                            LIVE["races"].setdefault(evt, []).append(
                                (coin, side))
                            LIVE["sends"] += 1
                            # the SAME quantity want_n was sized from, so the
                            # paper fill is min(want_n, what was offered) and
                            # never 0 on a book the live path would have sent
                            # into
                            supply = float(have or asz or 0)
                            out = do_order(LIVE["paper"], CREDS, tkr, side,
                                           float(ask), want_n, float(cs),
                                           supply, LIVE["tau_max"])
                            got = float(out.get("filled") or 0.0)
                            px = float(out.get("exec_price") or ask)
                            if got > 0:
                                LIVE["staked"] += px * got
                                live_pos.append(
                                    {"event": evt, "coin": coin,
                                     "ticker": tkr, "side": side,
                                     "price": px, "size": got, "tau": tau,
                                     "worth": round(worth, 6),
                                     "zmin": (None if zmin is None
                                              else round(zmin, 4)),
                                     "ask_seen": float(ask)})
                            if LIVE["paper"]:
                                # A WOULD-BE ORDER. Its own record kind, so no
                                # reader can ever count it as a real send, and
                                # `would_fill` rather than `filled` for the
                                # same reason. It still appends to live_pos,
                                # so live_settled scores it exactly as today.
                                rec("live_paper", event=evt, ticker=tkr,
                                    side=side, tau=tau, ask_seen=float(ask),
                                    fresh_ask=fresh, count_asked=want_n,
                                    would_fill=got, price=px,
                                    ask_size=float(asz or 0),
                                    buyable=supply, status="paper_live",
                                    staked=round(LIVE["staked"], 4),
                                    worth=round(worth, 6),
                                    gap_bp=round(gap * 1e4, 4),
                                    edge=round(edge, 6), ruler=ruler,
                                    zmin=(None if zmin is None
                                          else round(zmin, 4)), z=zj)
                                print("  ** PAPR %-24s %-4s %-3s would fill %g"
                                      " @ %.0fc  (staked $%.2f of $%.2f)"
                                      % (evt[-12:], coin, side.upper(), got,
                                         100 * px, LIVE["staked"],
                                         LIVE["max_stake"]))
                            else:
                                rec("live_order", event=evt, ticker=tkr,
                                    side=side, tau=tau, ask_seen=float(ask),
                                    fresh_ask=fresh,
                                    count_asked=want_n, filled=got,
                                    exec_price=(px if got > 0 else None),
                                    status=out.get("status"),
                                    status_code=out.get("status_code"),
                                    refused=out.get("refused"),
                                    fee=out.get("fee_total"),
                                    staked=round(LIVE["staked"], 4),
                                    order_id=out.get("order_id"),
                                    client_order_id=out.get("client_order_id"),
                                    zmin=(None if zmin is None
                                          else round(zmin, 4)), z=zj)
                                print("  ** LIVE %-24s %-4s %-3s asked %g got "
                                      "%g @ %.0fc  (staked $%.2f of $%.2f)"
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
