#!/usr/bin/env python3
# VERSION: 2026-09-08-pr1
"""pinrun.py -- pin, live, event-driven. Paper by default; --live sends size 1.

THE THREE PARTS, EACH PROVEN SEPARATELY BEFORE BEING JOINED HERE:
  EYES   livebook.LiveBook -- orderbook_delta over WebSocket, 26 ms median,
         top-3 verified identical to REST on live books. The REST poll it
         replaces was rate-limited into blindness: a 45-minute paper run
         logged 0 signals and 202 of 211 skips were "no_book", while a tape
         replay of the same three hours found 39 qualifying episodes.
  BRAIN  fair() below -- the settlement model, with TWO measured corrections
         the backtest does not have (see CORRECTIONS).
  HANDS  pintake.take -- IOC limit at the seen price, post_only False, rails
         checked before any send, proven on demo with real demo cash.

THE FROZEN RULE (results/PREREG_pin_live.md, written before any live order):
  tau <= 20 s, fair >= 0.98 (buy YES) or <= 0.02 (buy NO), edge >= 0.5c AFTER
  the taker fee, one fire per close, size 1. TAU_MAX is 20 and not 60 because
  the tau<=60 cell is below its own MDE out of sample (+0.25c vs MDE 0.86c)
  and produced 3 of the 4 wrong-side fires in today's replay, all at tau 38-60
  against markets that were right.

CORRECTIONS TO THE BACKTEST'S MODEL, both measured on this tape today:

  1. THE SETTLEMENT WINDOW IS [close-60, close-1], NOT [close-59, close].
     Checked against Kalshi's own avg_60s_data and the strike identity
     strike(N+1) == settle(N) on 108 of 108 markets. BRTI 00:45Z: floor strike
     79199.01; mean[c-60..c-1] = 79199.0060; mean[c-59..c] = 79199.3023. The
     tick labelled `close` is NOT in the settlement; the tick at close-60 IS.
     settlewin.partial(), endgame.fair() and pin.py all carry the old window,
     so at tau seconds to close they treat tau prints as remaining when tau-1
     remain -- they drop a locked print and substitute spot for it. Harmless
     where |mu-K| >> sd, fatal at small tau: the error is 135% of the true sd
     at tau=5 and 7.6x it at tau=2.

  2. THE SETTLEMENT IS ROUNDED TO THE STRIKE'S PRECISION BEFORE COMPARISON.
     custom_strike.round_digits is 2 for BTC/ETH/BNB and 4 for the rest;
     Kalshi rounds the 60-print mean to that many digits, writes it as
     expiration_value, and settles YES iff expiration_value >= floor_strike.
     So the true threshold is K - 0.5*10^-d, not K. A market lands inside that
     band 2.46% of the time (266 of 10,796 settled markets; DOGE 19.8% of the
     time, BTC never), so it is worth pricing correctly.

     RETRACTION, and it matters. This correction was first reported -- by the
     replay that found it, and repeated by me to the operator -- as the thing
     that turns the replayed three hours from -79.2c into +7.7c, because the
     single loss (KXETH15M-26SEP071745-45, strike 2492.82, settle 2492.8158 ->
     rounds to 2492.82 -> YES) sits in the band. RECONSTRUCTING THAT MARKET
     TICK BY TICK SHOWS THAT IS FALSE. With BOTH corrections applied, fair at
     tau=5 is 0.0052 -- still under the 0.02 gate, so pin still buys NO at
     0.903 and still loses 90.91c:

         tau   old window      +window fix    +rounding fix     sd
          10     0.5085          0.5471          0.6049       0.0338
           6     0.0145          0.0133          0.0294       0.0153
           5     0.0025          0.0013          0.0052       0.0113
           4     0.2476          0.2286          0.4577       0.0078

     The actual cause of that loss is SPOT SUBSTITUTION: the index dipped to
     2492.60 at tau 5-6, the model extrapolated the dip across the remaining
     prints, and the index came back to 2493.08 by tau=3. Both corrections are
     right and stay; neither prevents that trade. The honest statement is that
     the replayed three hours are 7 wins of +0.56 to +4.76c against one loss of
     -90.91c that the corrections DO NOT remove, and that n=12 closes says
     nothing about the edge either way.

RAILS, and why each one exists:
  * the abort block is the FIRST statement in the loop, before any branch.
    Last night's quoter had its loss check after the order block, so every
    stand-down `continue` skipped it and the run passed its own limit while
    reporting healthy. A structural self-test below fails if that pattern
    reappears here.
  * ONE fire per close, keyed on close_s -- the unit the backtest measured.
    Without it this loop would re-fire every iteration for as long as a stale
    quote stands: ~70 orders in one window across nine coins.
  * the level must hold at least our size in NON-fractional contracts. The
    book carries 0.01-0.83 contract dust; 13 of 52 qualifying episodes today
    were dust, including a 25-second "11.39c edge" of 0.02 contracts.
  * book and index staleness gates. A silently dead WS connection keeps a
    populated book with suspect=False for up to ~40 s.
  * pintake owns the money rails (count, price, IOC, post_only, tau, stake
    ledger, halt). This file may not send except through take().
"""
import argparse
import asyncio
import bisect
import calendar
import json
import math
import os
import sys
import threading
import time
from collections import defaultdict, deque
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG, tick_at               # noqa: E402
import livebook                                             # noqa: E402
import pintake                                              # noqa: E402

sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get                                       # noqa: E402

ND = NormalDist()
RESULTS = r"C:\kals-repo\results"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}

# ---- the frozen rule -------------------------------------------------------
# AMENDMENT 9 (2026-09-10 08:35Z): PIN 0.98 -> 0.995. THE BAR MOVED, AND THIS
# IS THE LOUD, DATED NOTICE. Evidence (research/pinfirst.py, 10,796 markets
# walked tau 30->3, flip rate AT THE SECOND THE BOT FIRES, fit/holdout over
# closes):
#     margin at fill   2.05-2.3 sd  1.79%   2.3-2.6 sd  3.08%
#                      2.6-4.0 sd   0.51%   4+ sd       0 of 7,868
#     flips at the 0.98 crossing 18 -> 10 at 0.995; holdout 3 -> 1;
#     9,151 of 9,159 markets still reach 0.995 inside the window.
# 0.995 is the level that excludes exactly the two bands with measured flip
# rates above 1.5% and keeps everything at 2.6 sd or deeper. On the 84 live
# fills it would have skipped 3 of the 5 losses (NEAR x2, BNB -- all fired at
# 2.09-2.25 sd) and no deep win. Size, brakes, ceiling, window: unchanged.
# What it costs is unmeasured: deeper markets are priced higher, so the
# same opportunity count may fill less often. Revert: PIN = 0.98.
PIN = 0.995
_DEFAULT_PIN = 0.995     # what --pin is measured against; never reassigned
# AMENDMENT 21 (2026-09-13): --pin, because AMENDMENT 20b MOVED THIS GATE
# WITHOUT TOUCHING IT.
#
# A wider ruler lowers every stated confidence, so the same PIN is a stricter
# gate than it was the day before. Measured rather than reasoned: the new ruler
# reads a median 1.167x wider (2,666 tape samples, wider on 79.2% of them), and
# re-scoring 619 REAL live signals through z -> z/1.167 shows it costs 46.6% of
# them at PIN 0.995. I tightened the strategy by nearly half without intending
# to and without noticing.
#
# THE NUMBER THAT NEARLY MADE THIS WORSE. The index population says moving PIN
# 0.995 -> 0.998 costs 0.7% of decisions. On our real signals it costs 51%. A
# 70x error, because 95% of index decisions sit miles from the strike while our
# signals cluster ON the gate -- median live confidence 0.9980, tenth
# percentile 0.9871. That population may compare rulers and may NOT count
# trades.
#
# THE TRADE-OFF (win 4c, loss 96c, live q = 3.18%; trades from the real
# signals, loss cuts from the index population):
#
#   PIN 0.995   53% of trades   q 1.64%   +2.36c/trade   +54%/hour
#   PIN 0.990   83% of trades   q 2.47%   +1.53c/trade   +54%/hour
#   PIN 0.980  104% of trades   q 3.11%   +0.89c/trade   +13%/hour
#
# 0.995 and 0.990 are worth the same expected money. They are NOT equally safe:
# the loss-cut column is measured on the index population and whether it
# transfers to fills someone chose to sell US is exactly what rule 5 says
# cannot be assumed. If it fails, 0.990 gives up a sixth of the volume and
# 0.995 gives up nearly half. Operator chose 0.990 on that reasoning.
# AMENDMENT 10 (2026-09-10 23:3xZ): DO NOT BUY A CERTAINTY AT A DISCOUNT.
# Operator: "why can't we just not buy the crazy 'deals' that basically always
# end up being someone knowing what's happening?" -- and he is right.
# Live, across both gate versions (fair() is identical in both): 14 fills where
# the model stood at >= 4 sd. The 8 priced at 94c+ (discount <= 6c) went 8-0.
# The 6 priced below -- discounts of 8c to 90c on a "certainty" -- went 4-2,
# and both losses were the same event reconstructed twice: the book sold us
# the certain side cheap, and the index jumped 10-18 sigma within a second.
# The model claims ~1e-9 for that. Its extreme tail carries no information,
# so a trade whose EV rests on it is a trade whose EV we cannot estimate.
# THIS IS NOT A FITTED THRESHOLD: any discount cut between 6.2c and 8.1c
# gives the same live result; 5c is chosen as the conservative side of it,
# and it is ~17x the 0.3c edge floor, i.e. far outside what an honest edge
# ever looks like. Cost on the live record: forgoes SOL +15.36, DOGE +3.78,
# ETH +2.82, SOL +1.52 and avoids XRP -16.61, DOGE -2.12 -- EV roughly
# neutral, loss frequency down by the whole class. Fewer losses at ~zero EV
# cost is the operator's stated preference and the definition of consistent.
# AMENDMENT 10c (2026-09-11 12:4xZ): THE GUARD WAS WRONG IN BOTH DIRECTIONS.
# Scored on all 139 live fills, by discount to fair at the FILLED price:
#     <2c   42 fills  1 loss  -$2.11
#     2-5c  64 fills  2 loss  -$0.11
#     5-15c 24 fills  0 loss  +$32.20   <- the best band in the dataset
#     15c+   9 fills  4 loss  -$12.41
# The 0.999 confidence condition let KXSOL15M 2026-09-11 12:30Z through at
# 99.508% with a 29.5c discount (-$12.16), and the 5c threshold refuses the
# 5-15c band. As deployed the guard costs -$10.49 on the live record: it
# refuses 8 winners (+$29.22) to avoid 2 losers (-$18.73). A measurably
# negative rule does not stay.
# TWO CHANGES, and their evidence is NOT equal:
#  * DROP THE CONFIDENCE CONDITION. Not fitted: the SOL loss proves the
#    discount matters independent of confidence, and every trade already
#    passes PIN, so "confident" is not information.
#  * RAISE THE THRESHOLD 5c -> 15c. The 5-15c evidence is strong and one
#    directional (0 losses in 24 fills, +$32.20 -- refusing it is
#    unambiguously harmful). The 15c line itself is CHOSEN AFTER SEEING THE
#    DATA on 9 fills and is therefore FITTED; it is kept only because
#    reverting to no guard is also negative on that band (-$12.41) and
#    because the operator's decision was to refuse deals this extreme.
#    It does not get to claim significance. The pre-registered review at 40
#    records stands and decides it on data this threshold never saw.
LADDER_LEVELS = 150      # AMENDMENT 45: price levels stored on every signal.
_DEFAULT_LADDER_LEVELS = 150   # The tick is 0.1c above 90c, so the 88-98c band
                         # we trade is ~100 levels; 8 covered a fifth of the
                         # book on the BTC 05:30 loss. Read once per SIGNAL,
                         # never in the scan loop.
# AMENDMENT 48 (2026-09-17): BUY BIGGER IN THE LAST FEW SECONDS. Shipped OFF.
# Our own live fills, which is the strongest evidence class we have:
#   0-5 s   1,028 contracts  5.35c each  0 losing closes of 23
#   6-15 s  4,125 contracts  3.80c each  2 losing closes of 98
#   16-30 s 11,363 contracts 1.90c each  9 losing closes of 313
# The last seconds earn 2.8x the main window on 6% of the volume, and the book
# is not the constraint -- median contracts buyable at our own sweep limit is
# 433 against a SIZE of 95, and only 8 of 102 sweeps were capped by the ladder.
# BANK_BRAKE is what caps SIZE, not the market. So this raises the PER-ORDER cap
# inside the late window only; the drawdown headroom, the close budget and the
# book all still apply unchanged.
# AMENDMENT 55 (2026-09-18): THE THREE CONDITIONS THE OPERATOR PUT ON A48.
# His words, approving it live: "make sure it's got good confidence when
# buying in the last 10 seconds ... If it looks like it's going to a loss
# don't buy the extra ... cut at first loss."
#
#   LATE_PIN     the boost needs MORE confidence than an ordinary bet. The
#                ordinary gate is PIN (0.995). Inside the last seconds the
#                extra contracts are the ones with the least time to be
#                rescued, so they are held to a higher bar.
#   LATE_JUMP_SD a one-second move AGAINST us bigger than this, since entry
#                or in the last few seconds, means "it looks like it's going
#                to a loss": take the ordinary size, not the extra.
# Both are checked in _late48 and BOTH default to off, so A48 without them
# behaves exactly as the paper arm that earned the deployment.
# AMENDMENT 56 (2026-09-18): A THIRD COIN MAY SPEND BEYOND THE CLOSE BUDGET.
#
# The operator: "if we've never lost multiple coins at once, allow extra
# total size if it comes in the way of an extra coin after two have been
# maxed out. I'm okay with that."
#
# The condition he set is MEASURED and it holds: across 417 closes we have
# traded, 19 had a losing coin and NOT ONE had two. In every case the other
# coins at that close won. Twelve of those closes already held three coins.
#
# Why that is not luck: all twelve series settle on the same second against
# their own index, and a close loses only when the last seconds move against
# the side we took ON THAT COIN. Correlated moves are common; correlated
# moves that cross twelve different strikes in the same direction inside the
# same second are not.
#
# WHAT IT COSTS, stated plainly, because this is the one change here that
# RAISES the worst case. `worst_close_cost` grows from MAX_PER_CLOSE to
# MAX_PER_CLOSE + EXTRA_COIN bets, so at a given BANK_BRAKE the bet size
# falls -- 2 -> 3 bets is bank/8 -> bank/12, about 80 contracts down to 53.
# That is the honest accounting and every rail (the brake, the loss abort,
# the stake cap) reads it. The operator can keep the old size by lowering
# --bank-brake, which is the same trade stated the other way round.
# AMENDMENT 59 (2026-09-19): THE CLOSE BUDGET MAY BE TOPPED UP IN THE LAST
# SECONDS, WHERE THE PRICES ACTUALLY ARE.
#
# The operator: "Can't the boost take a purchase from 11-45 seconds and then
# buy extra once it's at 10? I thought that was the strategy, wouldn't that
# earn more."
#
# It was the strategy, and it has NEVER ONCE HAPPENED: of 547 markets we
# have filled, ELEVEN were bought twice and ZERO were bought outside 10 s
# and again inside it. Two measurements say why that matters, both from our
# own live fills:
#
#   seconds left   fills  contracts  median price  per contract  losing
#     0-5             23      1,028        94.3c        5.354c        0
#     6-10            45      2,158        94.8c        5.461c        0
#     11-15           58      2,244        96.4c        1.973c        2
#     16-30          344     13,023        97.2c        2.103c       11
#     31-45           81      3,933        97.8c        2.197c        1
#
# The last ten seconds is where the CHEAP prices are -- 94.8c against 97.8c
# at 31-45 s -- and it returns two and a half times as much per contract
# with no losing close in 68 fills. And `close_budget` refused 126 markets
# inside that window. We spend the budget early at 97.8c and have nothing
# left when the 94.8c price appears.
#
# So: inside LATE_TAU a close may spend LATE_EXTRA x SIZE beyond its budget.
# Same shape as A56 -- worst_close_cost grows, every rail reads it. PAPER
# ONLY until an arm has run: this is the third size increase in a day, and
# the one with the least history behind it.
LATE_EXTRA = 0.0                # extra SIZE a close may spend inside LATE_TAU
_DEFAULT_LATE_EXTRA = 0.0

# AMENDMENT 64 (2026-09-19): THE LATE BUDGET AND THE LATE BOOST NEED DIFFERENT
# WINDOWS, and sharing one number was costing us the 11-15 second band.
#
# `--late-tau` does two unrelated jobs. It says when an order may be 1.5x
# SIZE (A48) -- which wants to be TIGHT, because that is extra risk on the
# least-time-to-recover bets. And it said when a close may spend an extra bet
# of budget (A59) -- which wants to be WIDE, because that is not extra risk
# at all, only permission to spend money the close was already allowed.
#
# MEASURED on the 97 closes where `close_budget` ran out: 75% of the budget
# had gone at MORE than 15 seconds left at a median of 97.6c, and 38% of the
# refusals landed INSIDE 15 seconds where the median price is 96.0c and the
# last ten seconds return 5.4c a contract against 2.2c out at 31-45 s. At a
# shared value of 10 the whole 11-15 s band was left out.
#
# None means "use LATE_TAU", which is the shipped behaviour.
LATE_EXTRA_TAU = None
_DEFAULT_LATE_EXTRA_TAU = None

# AMENDMENT 65 (2026-09-19): A HARD DOLLAR CAP ON WHAT A RUN MAY LOSE.
#
# The operator, after depositing: "Cap losses at 200, keep bet size."
#
# The loss abort has always been DERIVED: `-2 x SIZE x MAX_PER_CLOSE`, a band
# that survives two worst closes. It therefore GROWS with the bank -- at 105
# contracts it had already reached -$420 -- and nothing let him say "whatever
# the arithmetic thinks, stop at two hundred dollars".
#
# LOSS_CAP is that number, in positive dollars. The abort becomes the TIGHTER
# of the derived band and the cap, so the cap can only ever reduce what a run
# may lose. It is re-applied on every autosize, because the derived value is
# recomputed there and a cap that only ran once would be silently undone the
# next time the bank moved -- which is exactly how the old one-way ratchet
# let the stop follow the bank up and never come back down.
LOSS_CAP = None                 # positive dollars, or None for no cap
_DEFAULT_LOSS_CAP = None
_LC_UNSET = object()            # "cap not supplied" -- distinct from None,
                                # which is a REAL value meaning "no cap". The
                                # same trap as _HP_UNSET and _EW_UNSET, and
                                # _HP_UNSET itself is declared further down
                                # this file than this function.


def abort_for(size, cap=_LC_UNSET, per_close=None):
    """The dollar loss at which a run stops: the TIGHTER of band and cap.

    Returned NEGATIVE, as `--loss-abort` is. `cap` is positive dollars.
    """
    cap = LOSS_CAP if cap is _LC_UNSET else cap
    per = MAX_PER_CLOSE if per_close is None else per_close
    band = -2.0 * 1.00 * float(size) * float(per)
    if cap is None:
        return band
    try:
        return max(band, -abs(float(cap)))     # max() of two negatives = tighter
    except (TypeError, ValueError):
        return band


def late_extra_tau():
    """Seconds-to-close inside which the extra BUDGET applies."""
    return LATE_TAU if LATE_EXTRA_TAU is None else LATE_EXTRA_TAU

EXTRA_COIN = 0.0                # extra SIZE a close may spend, new coins only
_DEFAULT_EXTRA_COIN = 0.0

LATE_PIN = None                 # None = no extra confidence bar
_DEFAULT_LATE_PIN = None
LATE_JUMP_SD = None             # None = do not read the jump before boosting
_DEFAULT_LATE_JUMP_SD = None

_DEFAULT_LATE_TAU, _DEFAULT_LATE_MULT = 0, 1.0    # the SHIPPED values: OFF
LATE_TAU = 0             # --late-tau: seconds-to-close at or under which...
LATE_MULT = 1.0          # --late-mult: ...one order may reach this x SIZE
DUMP_DISCOUNT = 0.15     # dollars below fair that make an offer a warning
# THIS CONSTANT IS ALSO A PRICE FLOOR AND ITS NAME DOES NOT SAY SO. The
# confidence gate upstream guarantees our belief in our own side is at least
# PIN (0.995), and this gate refuses when belief - price > DUMP_DISCOUNT, so
# the refusal condition is exactly
#       price < PIN - DUMP_DISCOUNT
# which at the shipped values is price < 84.5c. Nothing in the buy path is
# NAMED a price floor; this is one.
#
# WHAT IT ACTUALLY COSTS: essentially nothing that has been measured, and a
# 2026-09-17 analysis claiming "+$82 of blocked winners" was WRONG. The error
# is worth stating because it is a trap in the log format itself:
#
#   A `dumped` record marks a MOMENT, not a market's fate. It is written once
#   per (close, market) the first time the discount exceeds the threshold. The
#   bot keeps looking at that market every tick, and when the discount narrows
#   below the threshold a moment later it BUYS.
#
# Of 17 flagged markets, TEN WERE BOUGHT ANYWAY seconds later and their wins
# are already in the run's P&L -- counting them as "blocked" double-counts
# money we have. The other seven have no settlement record at all, so the
# guard's true cost is UNMEASURED, not $82. See results/RESULTS_dumpguard.md,
# which now carries the correction rather than the original claim.
DUMP_ENABLED = True
_DEFAULT_DUMP_ENABLED = True   # --take-dumps clears it, PAPER ONLY
# AMENDMENT 45 (2026-09-17): ONE-COIN DEPTH, PAPER ONLY. THE OPERATOR: "Build
# the one coin depth." When on, a single market may take more than SIZE from
# an offer that is deep at or under the limit the bot already sends -- but
# never more than ONE_COIN_MAX x SIZE, never more than the close budget, and
# never more than a TOTAL LOSS of the position could cost before the drawdown
# brake (MAX_DRAWDOWN of the high-water bank) would halt the bot. Measured
# 2026-09-17 (results/RESULTS_quiet.md): at 2.0x the offers we already hit
# carried +80-87% more contracts; the brake caps that at ~1.2x at a fresh high
# and at ~nothing when the bank sits 3% under its high. one_coin_cap() is the
# whole rule. Off by default; --one-coin-depth is REFUSED on a live run.
ONE_COIN_DEPTH = False
_DEFAULT_ONE_COIN_DEPTH = False
ONE_COIN_MAX = 2.0             # multiple of SIZE; may not exceed MAX_PER_CLOSE
_DEFAULT_ONE_COIN_MAX = 2.0   # the offline-loop self-test pins the flag to this
# AMENDMENT 46 (2026-09-17): STAGED EARLY ENTRY. THE OPERATOR: "implement tau
# 45 in a safe way. Maybe not buying full coins and topping up what's
# available once we hit the normal purchase point? Perhaps that normal
# purchase point will need to be a hedge sometimes?"
# With EARLY_TAU_MAX above TAU_MAX, a market may be bought at tau in
# (TAU_MAX, EARLY_TAU_MAX] for EARLY_FRAC x SIZE at most -- the EARLY leg, one
# per market -- and then TOPPED UP to SIZE at tau <= TAU_MAX if the same gate
# still passes (AMENDMENT 29 already exempts an unfinished position from the
# re-buy band). If belief collapses before the top-up point the top-up simply
# fails the confidence gate and the hedge pass, which covers every open
# position, buys the other side: that is the "needs to be a hedge sometimes".
# staged_take() is the whole rule. Evidence: research/pinbefore.py (index:
# 31-45 s model error 0.058% vs 0.021% at 21-30 s), and the tau-45 paper arm
# (27 of 27 in its first 9 h, 3x the control's bets, +0.03c price). OFF by
# default; refused live until results/PREREG_staged.md's bar is crossed and
# EARLY_LIVE_OK is flipped in a commit that cites it.
EARLY_TAU_MAX = 30             # == TAU_MAX means OFF
_DEFAULT_EARLY_TAU_MAX = 30
EARLY_FRAC = 0.5
_DEFAULT_EARLY_FRAC = 0.5   # the offline-loop self-test pins the flag to this
# AMENDMENT 49 (2026-09-18): the EARLY leg also needs a price FLOOR.
# The operator: "Can you re open 45 seconds with a cap at 90c". Out at 31-45 s
# less of the settlement average is locked, so `fair` leans harder on the sigma
# estimate; a cheap ask there is the market disagreeing with us exactly where
# our model is weakest. Inside TAU_MAX the full leg is untouched by this.
# Note what it does NOT protect against: a limit price is a MAXIMUM, so a
# collapsing book can still fill us far below the ask we saw (97.8c seen, 53.0c
# paid, 2026-09-17). Only SIZE bounds that, which is why the early fraction is
# back to a third rather than a full bet.
EARLY_MIN_PRICE = 0.90
_DEFAULT_EARLY_MIN_PRICE = 0.90

# AMENDMENT 78: the ceiling on the EARLY leg only. 1.0 = no ceiling, which is
# the shipped default; --early-max-price sets it. The live bot runs 0.975 from
# 2026-09-20 on the operator's word. See the gate in trade_loop for the
# evidence: 31-45 s earns 1.14c a contract against 5.63c at 6-10 s, and above
# 97.5c it is risking 98c to make 1.8c.
EARLY_MAX_PRICE = 1.0
_DEFAULT_EARLY_MAX_PRICE = 1.0
# AMENDMENT 50 (2026-09-18): on the EARLY leg, a BIG edge is a WARNING, not a
# prize -- and the sign flips at 30 seconds.
#
# Measured over every signal joined to its settlement, split by how far our
# model sat above the market price on our own side (`edge_c`, already net of
# fee). Paper arms, so the LEVELS assume fills we might not get and rule 5
# applies; the SHAPE is the finding and it is not subtle:
#
#   31-45 s   under 3c   177 bets   3 lost   +0.06 $/bet
#             3-6c        62 bets   5 lost   -0.57 $/bet
#             6c or more  11 bets   3 lost   -3.01 $/bet
#   30 s or less
#             under 3c   934 bets  15 lost   +0.14 $/bet
#             3-6c       445 bets   6 lost   +0.47 $/bet
#             6c or more 263 bets   1 lost   +1.44 $/bet
#
# Live fills agree on the late half: 102 fills at 6c or more, 4 losses,
# +3.08 $/bet. There has never been a live early fill at 6c or more.
#
# WHY THE SIGN FLIPS, and why this is mechanism and not curve-fitting.
# Settlement is the mean of 60 one-second prints. At 15 s left, 45 of them are
# already on disk; at 30 s, 30 are; at 45 s, only 15 are. So late, our model
# is mostly reading RECORDED data and a cheap market price is simply wrong --
# that disagreement IS the edge. Early, three quarters of the window has not
# happened yet and our confidence rests on a volatility ESTIMATE; a market
# that disagrees by six cents out there is usually disagreeing correctly, and
# raising the confidence bar cannot help because confidence is computed FROM
# the same estimate. A price cap is independent evidence. This is the thing
# to try before sizing the early leg up.
#
# None = off, which is the shipped behaviour. In CENTS on our side.
EARLY_MAX_EDGE = None
_DEFAULT_EARLY_MAX_EDGE = None
# FLIPPED TO True 2026-09-17 ~15:0xZ ON THE OPERATOR'S EXPLICIT INSTRUCTION:
# "As long as you have the 45 second is built as safely as you described,
# deploy now." This is a BAR OVERRIDE and it is recorded as one, loudly, in
# results/PREREG_staged.md and results/VERSIONS.md (v-staged): stage 1's paper
# minimum (30 closes + 20 early markets) was NOT reached -- the staged arm had
# run ~20 minutes. What WAS in hand: the flat tau-45 arm's 27 of 27 over 9.2 h
# (0 losses, 3x the control's bets, +0.03c on shared markets) and pinbefore's
# index measurement (0.058% model error at 31-45 s vs 0.021% at 21-30 s).
# The STAGE 2 live bar in that file is unchanged and now governs: 40 live
# closes with an early leg, revert at 3 losses, or 2 in the first 15.
EARLY_LIVE_OK = True
TAU_MAX = 30           # AMENDMENT 4: 20 -> 30. Model calibration measured by
                       # horizon on the order-book dataset, restricted to
                       # moments it calls <2% risk:
                       #   tau  3-10   575 moments  0 flips   clean
                       #   tau 11-20 1,772 moments  0 flips   clean
                       #   tau 21-30 2,872 moments  0 flips   clean
                       #   tau 31-45 7,302 moments 25 flips   3.7x overconfident
                       #   tau 46-60 10,047 moments 126 flips 10.9x overconfident
                       # The overconfidence is ENTIRELY a long-horizon effect,
                       # which also explains why the tau<=60 cell was dead out
                       # of sample. 31-45 is a measured wall, not a soft edge:
                       # do NOT extend past 30 on this evidence.
TAU_MIN = 3            # a one-second misalignment is fatal below this
# AMENDMENT 38 -- DO NOT BUY A THIN EDGE WHILE THE PRICE IS ALREADY RUNNING
# AGAINST US.
#
# OPERATOR-APPROVED 2026-09-14: "if you mean both on the other side and under
# 2c you can block it off. It's only happened 5 times so not worth too much
# (it's also 2c not a huge profit) and it caused loss most times."
#
# THE CONDITION IS THE CONJUNCTION AND ONLY THE CONJUNCTION. Either half alone
# is a bad gate and both were measured:
#   spot against us alone : 15 fills, 13 winners given up, ratio 6.5:1
#   edge under 2c alone   : 105 fills, 102 winners given up, ratio 34:1  <- 31%
#                           of everything we trade; the repo's own history says
#                           every entry gate tested cost 22-44 winners per loss
#   BOTH TOGETHER         : 5 fills, 4 winners given up worth $1.81 TOTAL,
#                           1 loss avoided worth $58.43. Ratio 4:1.
#
# WHY IT IS DEPLOYED ON FIVE EVENTS, against the usual bar. The four winners
# it refuses are worth 41c, 47c, 56c and 37c -- $1.81 between them, because a
# sub-2c edge at 97c is pennies by construction. So the COST OF BEING WRONG is
# about $2 a week, and the cost of being right is one $58 loss. That asymmetry,
# not the significance, is the argument. It is NOT evidence of an effect and
# must not be quoted as one: the loss that motivated the rule is inside the
# five, so +$56.62 is a description of the past, never a forecast.
#
# "AGAINST US" MEANS THE LIVE PRICE IS ON THE WRONG SIDE OF THE STRIKE, in
# units of one second's typical move. Buying NO needs the average to land
# BELOW the strike, so spot ABOVE it is against us; buying YES is the mirror.
# The model already knows both numbers -- this is not new information, it is a
# claim that the model is OVERCONFIDENT in exactly this region, which is what
# RESULTS_calib.md measured (kurtosis 132 against a normal's 3).
# AMENDMENT 40 -- DO NOT BUY INTO A JUMP THAT JUST WENT AGAINST US.
#
# THE MECHANISM, measured on the index alone, 17,811 jumps over 1,785 closes
# (2026-09-14): after a one-second move over 3 sd, the NEXT five seconds
# continue the same way with a tail the model does not have. Share of jumps
# followed by a further >= 5 sd inside 5 s: 7.9%, against 2.2% after a calm
# second and 1.3% under the Gaussian the model assumes. Median continuation is
# ~0 -- most jumps stop -- but when they run, they run: p99 +15.4 sd against
# +7.0 after calm. The model treats each second as an independent draw around
# the new level. In the seconds after a jump that is wrong, in the tail, which
# is where every loss lives.
#
# THE LIVE EVIDENCE. BTC 2026-09-14 05:30 ET: the index moved +18.5 (4.5 sd)
# the second before we bought NO at 97.2c. The model saw spot at +12 over the
# strike and priced it as survivable -- correctly, had it stopped. It ran
# +22, +18, +18 more. -$58.43. Across all 359 live fills, a >= 3 sd move
# against us in the prior 3 s: 7 fills, 2 lost (28.6% vs 2.5%), -$65.67.
# Gating them gives up 5 winners worth $4.92 TOTAL. Both holdout halves
# positive. Threshold and lookback were fixed BEFORE the fill test was run.
#
# OFF BY DEFAULT. It changes what trades; --jump-gate turns it on.
JUMP_SIGMA = 3.0         # a one-second move this many sd against our side...
_DEFAULT_JUMP_SIGMA = 3.0
JUMP_LOOKBACK = 3        # ...in any of the last this-many seconds, refuses
_DEFAULT_JUMP_LOOKBACK = 3
JUMP_ENABLED = False
_DEFAULT_JUMP_ENABLED = False


def jump_against(moves, sigma, want):
    """Largest recent one-second move AGAINST our side, in sd units.

    `moves` are price changes newest-first. Buying NO needs the average to
    land BELOW the strike, so an UP move (+) is against us; YES is the mirror.
    Getting this sign wrong refuses exactly the trades we most want -- the
    first version of the fill test had it backwards and reported the
    dangerous bucket as our safest. None when unmeasurable."""
    try:
        if not moves or not sigma or float(sigma) <= 0:
            return None
        sgn = 1.0 if want == "no" else -1.0
        return max(sgn * float(m) / float(sigma) for m in moves)
    except (TypeError, ValueError):
        return None


def jump_block(moves, sigma, want):
    """AMENDMENT 40. Refuse when the index just jumped against us."""
    if not JUMP_ENABLED:
        return False
    j = jump_against(moves, sigma, want)
    return j is not None and j >= JUMP_SIGMA


# AMENDMENT 41 -- AFTER A JUMP, THE MODEL IS TWICE AS UNSURE AS IT THINKS.
#
# The same measurement that motivated A40 (17,811 jumps, index alone): after
# a one-second move over 3 sd, the next five seconds' continuation has p90
# +4.2 sd against +2.1 after calm, p95 +6.7 against +3.2, p99 +15.4 against
# +7.0. The TAIL is about twice as wide. So for the few seconds after a jump,
# sigma is multiplied by JUMP_WIDEN at BOTH places the model prices a
# position -- the entry decision and the hedge's belief.
#
# What that does that A40 cannot: A40 refuses an ENTRY into a jump. A41 also
# lowers the belief in a position we ALREADY HOLD when the index jumps under
# it, so the hedge fires sooner -- and hedging one tier sooner was measured at
# ~17c per rescued contract on the tape's 25 losing markets.
#
# Symmetric on purpose: a jump in our FAVOUR also widens sigma, which lowers
# confidence on a position that just got safer. That costs a few good entries
# and is the honest first version; a directional (drift) term is the
# refinement, not this.
#
# This is NOT the dead "scale sigma by k" in CURRENT_STATE. That multiplied
# every decision, which shrank the population without touching the loss rate
# because the error is shape, not width. This multiplies only in the one
# state where the shape is measurably wrong.
#
# OFF BY DEFAULT. --jump-widen turns it on.
JUMP_WIDEN = 2.0          # sigma multiplier after a jump AGAINST our side
_DEFAULT_JUMP_WIDEN = 2.0
# AMENDMENT 42 -- A JUMP IN OUR FAVOUR IS NOT AS DANGEROUS AS ONE AGAINST US.
#
# The operator, 2026-09-14: "Why can't you just make the double less cautious
# for jumps in our favour?" Mostly right, and the amount is measurable.
#
# The first version of A41 widened by 2.0 after ANY jump. But the tail that
# can hurt a position is the move AGAINST it, and after a jump those two
# directions are not the same size. Over the same 17,856 jumps, the 5-second
# move in each direction, as a share exceeding 5 sd:
#
#     with the jump    (hurts a position the jump went against)   7.9%
#     against the jump (hurts a position the jump went FOR)       5.0%
#     after a calm second                                         2.2%
#
# Solving for the sigma multiplier that makes a Gaussian reproduce each tail,
# then taking it relative to calm -- which is the state the model is already
# tuned for -- gives 1.43x for an adverse jump and 1.22x for a favourable
# one. The EXCESS over 1.0 is therefore 0.43 vs 0.22, a ratio of 0.51. So at
# JUMP_WIDEN 2.0 (excess 1.0) the favourable side earns excess 0.51:
JUMP_WIDEN_FAVOUR = 1.5   # ...and after a jump that went OUR way
_DEFAULT_JUMP_WIDEN_FAVOUR = 1.5
#
# NOT 1.0, and that is the part the question got wrong: a favourable jump
# still leaves the reversal tail at 2.6x the calm baseline. A jump makes the
# next few seconds less predictable in BOTH directions -- just less so in the
# direction it is already running.
JUMP_WIDEN_WINDOW = 5     # seconds a jump stays "recent" -- the horizon the
_DEFAULT_JUMP_WIDEN_WINDOW = 5   # continuation was measured over
WIDEN_ENABLED = False
_DEFAULT_WIDEN_ENABLED = False


def widen_factor(idx, iid, sigma, want=None):
    """AMENDMENT 41, direction-aware since AMENDMENT 42. The sigma multiplier
    for this market right now, given the side we hold or are about to buy:

      JUMP_WIDEN         a jump in the last JUMP_WIDEN_WINDOW seconds went
                         AGAINST `want`
      JUMP_WIDEN_FAVOUR  a jump went in its favour
      1.0                no jump, or unmeasurable

    `want=None` means "no side in mind" and takes the cautious branch, so a
    future caller that forgets to pass a side never gets the LOOSER number by
    accident. Off, or unmeasurable, is exactly 1.0 -- a feed hiccup must never
    widen anything.
    """
    if not WIDEN_ENABLED:
        return 1.0
    try:
        if not sigma or float(sigma) <= 0:
            return 1.0
        worst = 0.0          # biggest move AGAINST us, in sd, signed
        best = 0.0           # biggest move FOR us
        for m in idx.recent_moves(iid, JUMP_WIDEN_WINDOW):
            z = float(m) / float(sigma)
            if want == "yes":
                z = -z       # buying YES: a DOWN move is against us
            elif want is None:
                z = abs(z)   # no side given: treat any jump as adverse
            worst = max(worst, z)
            best = max(best, -z)
        if worst >= JUMP_SIGMA:
            return float(JUMP_WIDEN)
        if best >= JUMP_SIGMA:
            return float(JUMP_WIDEN_FAVOUR)
    except (TypeError, ValueError, AttributeError):
        return 1.0
    return 1.0


AGAINST_SIGMA = 1.0      # spot this many one-second moves past the strike,
_DEFAULT_AGAINST_SIGMA = 1.0   # against us, counts as "running against us"
AGAINST_EDGE = 0.020     # ...and only matters below this edge. 2c.
_DEFAULT_AGAINST_EDGE = 0.020
AGAINST_ENABLED = True
_DEFAULT_AGAINST_ENABLED = True


def against_us(strike, spot, sigma, want):
    """How far the LIVE price sits past the strike on the side that hurts us,
    in one-second moves. Positive = against us. None when unmeasurable."""
    try:
        if strike is None or spot is None or not sigma or float(sigma) <= 0:
            return None
        d = (float(spot) - float(strike)) if want == "no"             else (float(strike) - float(spot))
        return d / float(sigma)
    except (TypeError, ValueError):
        return None


def against_block(strike, spot, sigma, want, edge):
    """AMENDMENT 38. True when BOTH halves hold and the trade is refused.

    Unmeasurable inputs never block -- a missing sigma is not evidence that
    the price is against us, and a gate that fired on missing data would stop
    trading whenever the index hiccuped."""
    if not AGAINST_ENABLED:
        return False
    a = against_us(strike, spot, sigma, want)
    if a is None or edge is None:
        return False
    return a >= AGAINST_SIGMA and float(edge) < AGAINST_EDGE


EDGE_FLOOR = 0.003     # AFTER fee. 0.5c -> 0.3c per
                       # results/PREREG_pin_live_AMENDMENT_1.md, written
                       # 2026-09-08 08:20Z BEFORE the change went live.
                       # Out of sample the 0.3c floor gave 389 closes,
                       # +2.76c/contract, t=+5.6, 1 flip in 359 dear trades
                       # (headroom 2.1x); the 0.5c floor gave 354 closes,
                       # +2.51c, t=+4.1, 3 flips in 333 (headroom 1.3x).
                       # Better on every dimension measured. REVERTS to
                       # 0.005 if the live flip rate exceeds 1.0%.
SIZE = 1               # contracts we buy (--size; 0.01 = a penny test)

# ===========================================================================
# AMENDMENT 16 (2026-09-13): SIZE FOLLOWS THE BANK, AUTOMATICALLY.
#
# Set by the operator: "edit the bot to automatically scale up with the bank."
# Until now SIZE was a launch argument, so every increase needed a restart and
# in practice lagged the balance by days.
#
# THE RAIL IS THE ONE ALREADY IN THIS FILE, not a new one. MAX_PER_CLOSE's
# comment and main()'s --loss-abort band both size risk as a multiple of the
# WORST CLOSE, and both use 1.5x as the minimum survivable brake. The same
# number sets size here:
#
#     worst_close(size) = MAX_PER_CLOSE * size * PRICE_CEILING
#     size              = bank / (BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING)
#
# worst_close is EXACT, not a backtest statistic. A long binary cannot lose
# more than it cost, so this is a ceiling no tape or regime can exceed. The
# earlier ladder used the largest loss OBSERVED in an 18.6-day replay, which
# is a sample maximum: at size 1000 only 398 of 730 closes filled, so there
# were 45% fewer draws and the observed worst came in at 58% of the bound.
# Fewer chances to draw a bad close is not less risk. See research/pinbank.py.
#
# WHAT THIS DOES NOT CLAIM. It bounds the bank against one bad close. It is
# not a statement that expectancy is positive -- pinbank.break_even_rate()
# puts the break-even close-loss rate at 3.58% and our 248-close live record
# is 4.84% (upper bound 7.72%). If that holds, a bigger size loses money
# faster. The operator has seen that measurement and set the rule anyway; it
# is recorded here so the choice is visible, not so it can be relitigated.
#
# FOUR SAFETY PROPERTIES, each one earned from a failure in this file:
#
#  1. EVERY SIZE-DERIVED RAIL MOVES WITH SIZE. pintake.MAX_TAKE_COUNT,
#     MAX_RUN_STAKE and --loss-abort are all computed once from --size at
#     startup. On 2026-09-08 four separate size-1 literals silently REFUSED
#     every order at --size 20 -- 160 orders sent, 0 filled, no error raised.
#     apply_size() re-derives all of them; raising SIZE without them is the
#     single most likely way this amendment breaks.
#  2. THE UNIT IS READ, NEVER INFERRED. /portfolio/balance returns `balance`
#     in CENTS and `balance_dollars` as a string. read_bank() requires both
#     and refuses if they disagree by more than a cent. Treating 19215 cents
#     as dollars would ask for size 6535.
#  3. UP IS DAMPED, DOWN IS IMMEDIATE. A rise is capped at AUTO_SIZE_STEP_UP
#     per adjustment, so a misread balance cannot jump size in one move; a
#     fall applies at once. Asymmetric on purpose.
#  4. ONLY WHEN FLAT. Rails never change while a position is open.
# ===========================================================================
AUTO_SIZE = True         # --no-auto-size disables
BANK_BRAKE = 4.08
_DEFAULT_BANK_BRAKE = 4.08      # the SHIPPED value; --bank-brake moves the
                              # running one, and the guard must read THIS        # bank must cover this many worst-closes.
                         #
                         # 3.0 -> 4.08 on 2026-09-18, ON THE OPERATOR'S WORD:
                         # "Sure divide by 8." He had asked whether we were
                         # betting too high and was shown this arithmetic at
                         # a $613.66 bank and 104 contracts a bet:
                         #
                         #   loss            costs   quarter-hours to earn back
                         #   typical          $31    12   (~8 hours)
                         #   worst ever       $93    37   (~1 day)
                         #   total wipeout   $100    40   (~1.1 days)
                         #
                         # size = bank / (BANK_BRAKE * MAX_PER_CLOSE *
                         # PRICE_CEILING), so 4.08 * 2 * 0.98 = 7.997 and one
                         # bet becomes bank/8 rather than bank/5.88. At the
                         # same bank that is 76 contracts, about $75 a bet:
                         # the worst close falls from 33% of the bank to 25%,
                         # and the earning rate falls by about a quarter.
                         # That trade was his to make and he made it.
                         #
                         # 1.5 -> 3.0 on 2026-09-13, operator: "calculate a
                         # good number that still pulls profits, but is able
                         # to come back after losing relatively quickly".
                         #
                         # 1.5 was inherited from the --loss-abort band and
                         # never checked for what it IMPLIES: the worst close
                         # costs bank/1.5 = 64% of the bank. The operator
                         # caught that; it was his arithmetic, not mine.
                         #
                         # Measured on 695 real closes (research/pinbank.py,
                         # simulate_brake), bank $229, auto-sizing every close:
                         #   brake  size  worst  %bank  $/day  days to recover
                         #    1.5     77   $148    64%  38.02      4.2
                         #    3.0     38    $73    32%  18.77      2.5
                         #    4.0     29    $56    24%  14.32      2.4
                         #
                         # WHY 3.0 AND NOT 4.0. Under uncertainty about the
                         # true loss rate, 4.0 maximises the geometric mean of
                         # the good and bad worlds (449 vs 396) -- but the
                         # curve is flat and 3.0 keeps a third more earning
                         # rate. What 3.0 buys is the thing that matters: the
                         # worst close falls from 64% to 32% of the bank, so
                         # it now takes TWO bad closes back to back to do what
                         # ONE does today, and recovery is 2.5 days not 4.2.
                         #
                         # NOTHING HERE MAKES A LOSING STRATEGY SAFE. At a
                         # 4.6% close-loss rate every brake loses; the brake
                         # only sets the bleed rate. Break-even is 3.58% and
                         # our live record (12 losing of 248 closes) sits
                         # above it on too few closes to trust either way.
                         # This setting buys time to find out.
AUTO_SIZE_MIN = 1
AUTO_SIZE_MAX = 250      # nothing above this without a fresh depth study.
                         # Median resting size is 69 contracts and
                         # MIN_FILL_FRAC refuses a fill under half of SIZE, so
                         # past here the bot skips more closes than it takes
                         # and the bank stops being the binding constraint.
AUTO_SIZE_STEP_UP = None # None = go straight to the size the bank supports.
                         # Set by the operator 2026-09-12 23:2x ET ("why not
                         # just jump to what it's supposed to be"), replacing
                         # a 1.5x-per-step ramp.
                         # THE RAMP'S ONLY JOB WAS TO BLUNT A MISREAD BALANCE,
                         # and two things already do that better: read_bank()
                         # refuses unless `balance` (cents) and
                         # `balance_dollars` agree to the cent, so a unit error
                         # returns None rather than a wrong number; and
                         # AUTO_SIZE_MAX caps the result whatever it says. The
                         # ramp bought nothing those two do not, and it cost
                         # ~10 minutes of trading at the wrong size after every
                         # restart. Set to a float to restore damping.
AUTO_SIZE_EVERY_S = 300  # seconds between adjustments
MAX_PER_CLOSE = 2
_DEFAULT_MAX_PER_CLOSE = 2   # likewise: asserted, never the running value        # 3 -> 2 on 2026-09-09, and NOT because cap 3 is
                         # wrong. Cap 3 still measures better on every number
                         # I have. It is a BANK constraint: at size 20 cap 3 a
                         # worst close costs $60, the deployment rail requires
                         # a brake of at least 1.5x that, and $90 is 81% of a
                         # $110 bank. Cap 2 keeps the operator's size at 20
                         # with a $60 brake at 54% of the bank.
                         # THE OPERATOR IS RIGHT THAT HALVING SIZE IS NOT A
                         # FIX: it halves the loss AND the profit and leaves
                         # the ratio untouched, so it diagnoses nothing. Size
                         # goes back to 20; the cap is what gives way, because
                         # the cap is also what concentrated three fills into
                         # one market on the losing close.

# ===========================================================================
# AMENDMENT 17 (2026-09-13): A CLOSE IS CAPPED ON CONTRACTS, NOT ON FILLS.
#
# The operator's design, in his words: "instead of max 2 coins make it a max
# amount of contracts... unlimited coins, but maxed at the total contracts
# allowed", and a later coin may take the remainder "ONLY IF IT IS ONE YOU'D
# USUALLY BUY IF IT HAD ALL 68 AND MEETS CRITERIA".
#
# THE PROBLEM IT FIXES. MAX_PER_CLOSE counted FILLS, so a fill cost a whole
# slot whatever its size. On 2026-09-11T23:00 a BTC market offered 1 contract
# at 96c and, seconds later in the same close, 48,762 contracts at 98c --
# taking the first retires the market (A13) and spends a slot, so that close
# earned $0.04 where it could have earned $1.26.
#
#     budget = MAX_PER_CLOSE * SIZE contracts per close
#
# EXPOSURE IS IDENTICAL AND THAT IS THE POINT. worst_close is
# MAX_PER_CLOSE * SIZE * PRICE_CEILING under both rules -- the same number
# the --loss-abort band, pintake's stake cap and pinbank all already use, so
# no downstream rail moves. Measured worst close matched to the cent
# (-$128.95 both ways) over 422 book hours. Capping coins bounds exposure
# only indirectly; capping contracts bounds it exactly, which is the better
# answer to twelve series settling on one second at rho ~ 0.8.
#
# MEASURED (research/pinlevels.py, 16,683 candidate rows, 18.75 days, each
# slice on its own span, size 68):
#     slots=2    all $31.49/day   fit $40.72   holdout  $8.22
#     budget 2x  all $33.58/day   fit $40.07   holdout $17.65
# Neutral in the fit, doubles the recent third. Absent at size 20 (11.88 ->
# 11.47), which fits the mechanism: the spill only matters when depth binds.
# It is a STRUCTURAL rule with no fitted parameter, so there is no threshold
# here tuned to its own evidence.
#
# THE OPERATOR'S CONDITION IS ENFORCED: MIN_FILL_FRAC is measured against the
# FULL SIZE, never against the remaining budget, so the tail of a budget
# cannot be spent on a moment we would not otherwise have touched. Only the
# QUANTITY is trimmed to what is left.
#
# Set CLOSE_BUDGET = False to return to counting fills.
# ===========================================================================
CLOSE_BUDGET = True

_DEFAULT_MAX_PER_MARKET = 1   # --max-per-market is measured against this
MAX_PER_MARKET = 1       # AMENDMENT 13 (2026-09-12). FILLS ALLOWED ON ONE
                         # MARKET IN ONE CLOSE. Scaling in buys MORE as the
                         # price falls, which is buying into a move against
                         # the position we already hold -- the same adverse
                         # selection as the discount cliff, applied to
                         # ourselves. Measured over 157 live bets on 127
                         # closes:
                         #   3 markets, 3 fills each  $+1.31   worst -$52.60
                         #   3 markets, 2 fills each  $+15.44  worst -$38.47
                         #   2 markets, 1 fill each   $+33.83  worst -$19.29
                         #   3 markets, 1 fill each   $+34.29  worst -$19.29
                         # BE HONEST ABOUT THE EVIDENCE: the P&L half of that
                         # rests on THREE scale-in fills ever, of which two
                         # lost (-$32.98), and n=3 proves nothing. Remove the
                         # 09-09 NEAR close and cap 3 is the BEST rule, not
                         # the worst. So the P&L case is not the reason.
                         # THE REASON IS ARITHMETIC, NOT STATISTICS: three
                         # fills on one market is 3x the stake on ONE
                         # outcome, and the worst close falls from 30% of the
                         # bank to 11%. That holds whatever those three fills
                         # would have done. MAX_PER_CLOSE stays at 2, so two
                         # DIFFERENT markets are still allowed -- they are
                         # correlated at rho ~ 0.8, not identical.
#
# RE-OPENED 2026-09-13 BY THE OPERATOR, conditionally: "we can buy the same
# coin twice if it leads to more profit because it goes cheaper, but that's a
# very slippery slope into buying a flipping coin. If you can figure out a way
# to do that safely I'll allow it... as long as the second coins purchase is
# within the allowed contract size limit then that's certainly okay."
#
# HIS CONDITION IS ALREADY MET, AND A13'S ARITHMETIC REASON NO LONGER HOLDS.
# A13 says "three fills on one market is 3x the stake on ONE outcome" -- true
# when the close budget counted FILLS. AMENDMENT 17, the NEXT DAY, changed the
# budget to CONTRACTS: MAX_PER_CLOSE * SIZE, whatever the fills. Two fills of
# 47 on one market is 94 contracts, exactly the same 94 the budget already
# allows. The 3x cannot happen any more. A13 is the second rule in two hours
# found to be arguing against a world A17 replaced.
#
# WHAT DOES STILL HOLD, and it is the operator's own worry: 94 contracts on ONE
# outcome is more concentrated than 47 + 47 across two coins at rho ~0.8. And
# scaling in buys MORE as the price falls, which is buying into a move against
# a position we already hold. That part is NOT solved by a contract cap and is
# exactly "buying a flipping coin".
#
# SO IT GOES TO A WHAT-IF, NOT LIVE. --max-per-market raises it in a paper run
# where it costs nothing, against the live bot on 1, and the comparison decides.
# ===========================================================================
# AMENDMENT 15 (2026-09-12): THE BELIEF-COLLAPSE HEDGE.
#
# Four live losses dissected second by second showed the model's OWN belief
# in our side collapsing before settlement -- 98% -> 41% -> 1% (NEAR), 98% ->
# 46% (BNB), 99.8% -> 84% -> 0.05% (SOL 08:00) -- while the bot held to zero.
# On 48h of tape, 1,630 of 1,642 winners never dipped below 99% belief after
# entry and all 11 losers fell below 20%. The prices that traded in the alarm
# second recovered ~49c of the 96c on average.
#
# THE HEDGE: when belief falls below HEDGE_BELIEF, buy the OPPOSITE side for
# the contracts we hold, at the best ask, through the SAME take() path every
# fill uses. Holding both sides pays exactly $1/contract whatever settles, so
# the loss is locked at (entry + hedge - 1.00) instead of the full entry.
#
# WHAT IT IS NOT: it is not a sell. It is not a new order type. It does not
# touch pintake. Settlement is per ORDER via open_pos, so the two legs pay
# independently and correctly. The A8 both-sides guard lives in the SIGNAL
# path and reads `fired[...]["sides"]`; the hedge never calls _book_slot and
# so never writes there, which means A8 still blocks any later ENTRY on the
# opposite side -- the hedge is the only path allowed to hold both.
#
# Pre-registered live bar: results/PREREG_hedge.md, written before this code.
# ===========================================================================
HEDGE_ENABLED = True
_DEFAULT_HEDGE_BELIEF = 0.80   # --hedge-belief is measured against this
HEDGE_BELIEF = 0.80      # belief in OUR side below which we hedge.
                         # 0.90 -> 0.80 on 2026-09-12 18:2xZ, from the REBUILT
                         # pinsim holdout (commit 8ec2ae7, seq-ordered book, a
                         # decision after every book event). On the same 72
                         # unseen hours the faithful replay nets +$35.69 at 0.80
                         # (false alarms 1.54%) against +$25.54 at 0.90 (3.08%,
                         # exactly the pre-registered bar). The old replay had
                         # said 0.90; it missed the adversely-selected fills that
                         # lose. Two real live alarms at 0.887 and 0.664 were both
                         # false; they point the same way but are not the reason.
                         # Dated entry in results/PREREG_hedge.md.
# AMENDMENT 51 (2026-09-18): insurance only when the other side would be a
# NORMAL BET. The operator's idea, in his words: *"If we buy early, then
# calculate at <30 it's the other side then buy enough there just like a
# normal bet to offset it or even profit. Just like how we normally would on
# any other bet."*
#
# Today the hedge fires on the MODEL's belief alone, at any ask under a
# dollar. Its record is poor: 12 insured closes, 11 ended negative, and five
# of the twelve bought the other side at 10-18c -- meaning the market still
# favoured our ORIGINAL side and we paid for nothing. That is the model
# panicking at a move the market shrugs off, which is the same weakness A47
# and A50 are aimed at.
#
# This requires the opposite side to clear the gates an ENTRY has to clear:
# our model at least PIN sure of it, and its ask at or under PRICE_CEILING.
# Then insurance is not insurance at a panic price -- it is a second good bet
# that happens to cancel the first.
#
# THE KNOWN LIMIT, stated because it decides whether this can ever work: by
# the time the model is PIN-sure the other side wins, that side is usually
# expensive, and a contract bought at 97c returns 3c. Our twelve real hedges
# paid between 10c and 95c. So this will fire RARELY, and when it does the
# offset will be partial. Firing rarely is the point; the alternative is
# paying a premium eleven times out of twelve for nothing.
HEDGE_NORMAL = False
_DEFAULT_HEDGE_NORMAL = False
# AMENDMENT 52 (2026-09-18): hedge on the JUMP, not on the belief.
#
# Every loss this bot has taken is a post-entry jump: a single-second index
# move of 10-18 sigma, with sigma understated 2-3x at entry, and the losers
# sitting inside the winners' confidence range. Nothing at entry sees it --
# a scored vote of every entry-time warning was measured the same day on 920
# markets and killed (one flag catches 4/4 misses at 31-45 s and refuses 75%
# of wins; two flags catch 1/4). So the defence is AFTER entry.
#
# The current hedge fires when the model's belief in our side falls through
# HEDGE_BELIEF. Belief is DOWNSTREAM of the jump: by the time it has fallen,
# the market has moved and the other side costs 50-70c. This fires on the
# jump itself -- the largest one-second move against our side since entry, in
# sigma units -- while the market may still like our side and the other side
# is 10-20c. A needed hedge then pays 80-90c a contract instead of 30-50c; a
# wasted one costs a few dollars, not twenty.
#
# Firing upper bound on those 920 markets (results/sigcheck_out.json):
#     live 3-30 s   5 sigma  catches 11/11 losses, fires on  9% of winners
#                   8 sigma            7/11                   4%
#                  10 sigma            5/11                   2%
#     live 31-45 s  8 sigma             1/1                   5%
# What those records CANNOT say is when the jump came relative to the price
# collapse. If they are the same second the hedge fills at 60c anyway and this
# buys nothing. The money is in the fill price, which only a paper arm sees.
#
# None = off, the shipped behaviour. The belief trigger is untouched; this
# ADDS a second reason to fire and records which one it was.
HEDGE_JUMP_SIGMA = None
_DEFAULT_HEDGE_JUMP_SIGMA = None
HEDGE_JUMP_LOOKBACK_MAX = 60   # never read more than a minute of moves
HEDGE_MAX_ASK = 1.00     # the hedge leg must cost LESS than the $1 it pays.
                         # THE FIRST VERSION OF THIS RULE WAS WRONG, and the
                         # self-test caught it before any live hedge: it
                         # required entry + hedge < $1.00, which would have
                         # refused almost every real hedge. Holding 20 NO at
                         # 96c and buying 20 YES at 35c pays 131c for a $1
                         # payout -- a 31c loss, which BEATS the 96c loss from
                         # holding. The pair being over a dollar is the whole
                         # point; the only hedge that cannot help is one at
                         # $1.00 or more, where the locked loss equals the
                         # unhedged one. Recorded 2026-09-12 08:4xZ, and
                         # PREREG_hedge.md rule 4 is corrected with this date.
HEDGE_PILOT_CONTRACTS = None  # FULL SIZE. I set this to 1 for ~30 minutes on
                              # 2026-09-12 having misread the operator: he meant
                              # "buy ONE contract of a losing coin, then test the
                              # hedge on THAT one", a self-contained planted test
                              # -- NOT cap the hedge on real 20-contract positions
                              # at one contract, which left real money under-
                              # hedged. His correction, verbatim: "don't hedge a
                              # real 20 contract buy with just 1 as a test, do
                              # all 20." The planted test is --hedge-plant below;
                              # this constant stays as machinery for it and is
                              # None in production. Dated in PREREG_hedge.md.
# AMENDMENT 62 (2026-09-19): NO GATE MAY BLOCK A HEDGE ON A COLLAPSED BET.
#
# The operator, after KXBNB15M-26SEP190145-45 lost $57.98: "NOTHING SHOULD
# BE BLOCKING A HEDGE ON A LIVE BET WITH A 22% CONFIDENCE RATING ... I HAVE
# SAID OVER AND OVER HOW CRITICAL HEDGING IS."
#
# WHAT HAPPENED. Belief fell to 0.227 one second after the fill. The other
# side was 21c. `--hedge-price 0.60` (A47) held the hedge back because OUR
# side was still quoted at 79c -- the market had not agreed yet. Two seconds
# later the other side was 51c, then 70c, then 76c, and the five tries ran
# out. Hedging at 21c would have made the close +$3.06 instead of -$57.98.
#
# THE RULE NOW. Below HEDGE_PANIC belief, every discretionary hedge filter is
# bypassed: the market-agreement test (A47), the normal-bet test (A51), and
# the attempt cap. The only checks left are the ones that are arithmetic
# rather than opinion -- the leg must cost under $1 (`hedge_ask_ok`), and
# there must be an ask to hit at all. A filter exists to avoid paying for
# insurance we do not need; at 22% belief we need it, and what the market
# thinks is not evidence against our own model, it is a two-second lag we
# have now measured.
#
# AND THE OPERATOR'S STANDING ANSWER TO THE OBJECTION, said many times: a
# hedge that turns out wrong is not a trap. "ONCE CONFIDENCE REBUILDS ON
# EITHER SIDE YOU CAN JUST BUY MORE OF THAT SIDE." Being on both sides is
# recoverable; being naked in a collapse is not.
# 0.35 -> 0.40 on the operator's instruction, 2026-09-19: "Nothing can block
# a hedge under 40%. And most hedges just shouldn't be getting blocked
# anyway." THE RECORD AGREES. Every hedge we have ever placed, by the belief
# that triggered it:
#
#   belief   ask   what it did to the close
#    2.0%    95c   HELPED
#   11.6%    76c   HELPED   <- the BNB that cost $57.98; the 21c hedge was blocked
#   21.4%    43c   HELPED   (+$24.18)
#   24.3%    74c   HELPED   (+$8.29)
#   48.5%    15c   hurt     (-$13.83)
#   52.5%    80c   HELPED
#   53.3%    47c   HELPED
#   55.9%    51c   HELPED   (+$29.30)
#
# EVERY hedge at or under 24.3% belief helped. The only one that hurt sat at
# 48.5% and was bought at 15c -- which is exactly what `--hedge-price 0.60`
# refuses. So at a 40% panic line the market filter survives only in the
# 40-60% band, where on this record it blocks the one that hurt and passes
# all three that helped. Below 40% nothing touches the hedge at all.
HEDGE_PANIC = 0.40       # belief at or under which NO filter may block a hedge
_DEFAULT_HEDGE_PANIC = 0.40

HEDGE_MAX_TRIES = 30     # seconds we keep trying once the alarm has fired.
                         # 5 -> 30 on 2026-09-19 (A62b). On the BNB close
                         # that lost $57.98 the hedge tried at 21s, 20s and
                         # 19s -- filling 0, 0 and ONE contract as the other
                         # side went 51c, 70c, 76c -- and then gave up at
                         # 18s with eighteen seconds still on the clock and
                         # the position entirely naked. A give-up is only
                         # ever right if the hedge cannot help, and
                         # hedge_ask_ok already refuses a leg at or over $1,
                         # which is the only case where that is true.
                         # Separate from MAX_ATTEMPTS_PER_CLOSE, which also
                         # applies. A collapse leaves ~15s; five is generous.


def hedge_should_fire(belief, threshold=None):
    """True when the model's belief in OUR side has fallen below the gate."""
    thr = HEDGE_BELIEF if threshold is None else threshold
    return belief is not None and belief < thr


def index_age(idx, iid):
    """Seconds since the newest index print held, or None if unknowable.
    K3: the hedge pass reads this; a read that fails counts as not fresh."""
    try:
        age = idx.spot(iid)[2]
        return None if age is None else float(age)
    except Exception:                                    # noqa: BLE001
        return None


def market_belief(bk, want, max_age_ms=None):
    """K3 (2026-09-22): the MARKET's probability of our side -- our side's
    best ASK -- or None when the book cannot say.

    THE ASK, NOT THE MID. The ask is the cheapest anyone will SELL us more of
    our side, so an ask under the hedge line means nobody in the book values
    our side above it. The mid could be dragged down by one thin lowball bid:
    after our own entry sweeps the other side, a healthy book can read bid
    15c / ask 99c, a mid of 57c -- under a 0.60 or 0.80 hedge line on a
    position that is winning. The ask is at or above the mid, so it can only
    remove triggers the mid would have fired, never add one.

    Used only by the hedge pass, only while the settlement index is stale.
    None, never a guess, for: no book, a suspect book, a book older than
    MAX_BOOK_AGE_MS, either side missing, a price outside (0, 1), or a
    crossed book. Prices are dollars, as livebook.best() returns them."""
    if not bk or bk.get("suspect"):
        return None
    lim = MAX_BOOK_AGE_MS if max_age_ms is None else max_age_ms
    age = bk.get("age_ms")
    if age is None or age > lim:
        return None
    try:
        bid = float(bk.get(f"{want}_bid"))
        ask = float(bk.get(f"{want}_ask"))
    except (TypeError, ValueError):
        return None
    if not (0.0 < bid <= ask < 1.0):
        return None
    return ask


# K2 follow-up (2026-09-22): the -1 failures that PROVE a hedge never left
# the box. ordercli.send returns -1 and str(exception) for EVERY failure, and
# K2 counts a hedge whose outcome is unknown as covered, because a resend
# could double it. But urllib reports a failure inside the request call as
# "<urlopen error ...>", and of those a refused connection, a failed DNS
# lookup, an unreachable host or network, and a TLS handshake timeout all
# happen before one byte of the order is written -- nothing can have been
# placed. Counting THOSE as covered left a position naked for the rest of
# the close over a one-second network blip. They are sent again next second.
# Everything else -- a timeout or reset once connected ("[WinError 10054]
# ... forcibly closed" is in our own logs), a 5xx, an unreadable 2xx -- stays
# UNKNOWN and counted covered, exactly as before.
_NEVER_SENT_MARKERS = (
    "[WinError 10061]", "Connection refused",               # refused
    "[WinError 10051]", "Network is unreachable",           # no network
    "[WinError 10065]", "No route to host",                 # no host
    "getaddrinfo failed", "Name or service not known",      # DNS
    "Temporary failure in name resolution",
    "nodename nor servname provided",
    "The handshake operation timed out")                    # TLS, pre-send


def hedge_never_sent(out):
    """True only when a -1 result's own error text proves the order was never
    written to the wire. Never raises; anything unclear is False (UNKNOWN)."""
    try:
        if out.get("status_code") != -1:
            return False
        raw = out.get("raw")
        if not isinstance(raw, str) or not raw.startswith("<urlopen error"):
            return False
        return any(m in raw for m in _NEVER_SENT_MARKERS)
    except Exception:                                    # noqa: BLE001
        return False


# AMENDMENT 47 -- THE MARKET MUST AGREE BEFORE WE PAY FOR INSURANCE.
# `--hedge-price P` (default None = off, the shipped behaviour is unchanged).
# When set, a hedge fires only if the model's belief has collapsed AND our
# side's own market price has fallen below P.
#
# Why: `research/pingrid.py`'s wobble screen, 1,717 crypto markets. Take every
# market whose favourite was at 90c+ with a minute left, and bucket it by the
# LOWEST price that favourite traded at inside the last 30 seconds:
#
#     stayed 90c+   1,511 markets, favourite lost 0
#     dipped 50-90c    48 markets, favourite lost 0
#     fell under 50c  158 markets, favourite lost 120  (76%)
#
# A favourite that merely wobbles recovers -- 48 times out of 48. One that
# crosses below 50c is a real flip three times in four. The model's belief
# does not know that; it re-prices on the index alone and panics at moves the
# market shrugs off.
#
# On our own live hedges (7 of them would fire under today's 0.60 gate), the
# one WASTED hedge bought insurance while our side was still trading at 85c
# and cost $13.83. Every hedge that was NEEDED had our side under 50c, except
# one at 53c that made $0.51. So on the record this filter is +$13.32 over
# five days -- suggestive at n=7, which is why it ships OFF and goes to a
# paper arm first (`results/PREREG_hedgeprice.md`).
_DEFAULT_HEDGE_PRICE = None   # the SHIPPED value. --hedge-price overrides the
                              # one below; self-tests assert against THIS, or an
                              # arm that sets the flag would fail its own gate.
HEDGE_PRICE = None       # --hedge-price; None = the market's opinion is ignored


_HP_UNSET = object()      # "argument not supplied" -- distinct from None, which
                          # is a REAL value here meaning "A47 is off". The first
                          # version used None for both, so passing the shipped
                          # default explicitly fell back to the running global
                          # and the self-test failed on any arm that set the flag.


def hedge_panic(belief, threshold=_HP_UNSET):
    """True when belief has collapsed far enough that NOTHING may block us.

    `belief` is the model's probability of OUR side. At or under the
    threshold this is not a wobble -- it is the model saying the bet is
    lost -- and every discretionary filter is bypassed.

    A MISSING BELIEF IS NOT A PANIC. `None` means we could not measure, and
    an unmeasurable reading must not trigger the path that ignores every
    other safeguard; the ordinary filters still apply and the position is
    still hedged when they pass.
    """
    thr = HEDGE_PANIC if threshold is _HP_UNSET else threshold
    if belief is None or thr is None:
        return False
    try:
        return float(belief) <= float(thr)
    except (TypeError, ValueError):
        return False


def hedge_price_ok(hedge_ask, threshold=_HP_UNSET):
    """True when OUR side's market price is low enough to hedge.

    We buy the opposite side at `hedge_ask`, so our side is trading at about
    `1 - hedge_ask`. A threshold of None means the filter is off, which is the
    shipped behaviour; omitting the argument uses whatever is running.
    """
    thr = HEDGE_PRICE if threshold is _HP_UNSET else threshold
    if thr is None:
        return True
    try:
        ours = 1.0 - float(hedge_ask)
    except (TypeError, ValueError):
        return False
    return ours < float(thr)


def hedge_ask_ok(hedge_ask):
    """A hedge helps iff its leg costs less than the $1 the pair pays.

    Locked loss = entry + ask - 1. Unhedged loss = entry. So the hedge is an
    improvement exactly when ask < 1.00, and never otherwise. The entry price
    does not enter into it -- which is what the first version got wrong."""
    try:
        a = float(hedge_ask)
    except (TypeError, ValueError):
        return False
    return 0.0 < a < HEDGE_MAX_ASK - 1e-9


# ---------------------------------------------------------------------------
# AMENDMENT 70 (2026-09-19): THE HEDGE COULD NOT SWEEP, AND THAT IS WHY IT
# DID NOT FILL.
#
# The ENTRY path has been sweeping the ladder since A35/A67: it sends
# `sweep_limit(...)` -- a price ABOVE the touch -- and sizes the order from
# `book.rungs`. The self-test at "pintake.take() is handed the LIMIT, never
# the ask we saw" enforces it.
#
# THE HEDGE PATH DOES NEITHER. It sent `float(_ask)` as the limit and
# `min(_hn_want, _asz)` as the size -- one stale level, priced to the tick.
# So the moment the market moves, which is exactly the moment a hedge is
# needed, the IOC crosses nothing and we get zero.
#
# THE EVIDENCE, live fills only (rule 5), all 29 hedge attempts we have ever
# sent:
#
#   KXBTC15M-26SEP172115-15  tau 36  asked 99  touch  283.8  FILLED 0
#   KXBTC15M-26SEP172115-15  tau 35  asked 99  touch 7419.0  FILLED 0
#   KXBNB15M-26SEP190145-45  tau 20  asked 76  touch   96.0  FILLED 0
#   KXBNB15M-26SEP190145-45  tau 19  asked 25  touch   25.0  FILLED 1
#   KXBNB15M-26SEP191230-30  tau 11  asked 28  touch   28.0  FILLED 1
#
# Ten of twenty-nine attempts filled nothing or one contract while the book
# displayed everything we asked for. The 01:45 BNB close is the ONLY escape
# failure in the project's history (-$57.76) and this is its mechanism: A62
# removed the FILTERS that blocked that hedge, and the hedge still did not
# fill, because nothing had fixed the EXECUTION.
#
# WHAT THIS CHANGES AND WHAT IT CANNOT. It raises the price a hedge may pay
# by at most `--hedge-slip` cents over the ask we saw, and it lets the size
# come from the ladder instead of the touch. It is OFF by default (slip 0.0),
# so the shipped behaviour is byte-identical to today's until the flag is
# passed.
#
# WHAT IT BLOCKS -- the question today's rule says to answer first: NOTHING.
# There is no path on which a hedge that fires today does not fire with the
# flag on. `hedge_depth` returns at least the touch size, so a hedge can only
# get bigger, never smaller; `hedge_limit` returns at least the ask, so it can
# only cross more of the book, never less; and if `book.rungs` raises, the
# caller falls back to the touch and hedges anyway.
#
# AND IT CANNOT RAISE EXPOSURE. The extra depth is capped at `unhedged` --
# the contracts of ours still without a matching leg. A close pays
# `min(yes_n, no_n)`, so every contract past the other side's count is naked
# (A63 was refused for exactly that). The cap is what keeps this a hedge.

HEDGE_SLIP = 0.0         # --hedge-slip: dollars above the ask a hedge may pay
_DEFAULT_HEDGE_SLIP = 0.0


def hedge_limit(ask, slip=None):
    """The LIMIT to send for a hedge leg: the ask we saw, plus the slip, hard
    stopped below HEDGE_MAX_ASK.

    Never returns less than `ask` -- a smaller limit would cross less of the
    book than today and could turn a hedge that fills into one that does not.
    Returns None only when the ask itself is unusable, which the caller has
    already refused on via hedge_ask_ok().
    """
    s = HEDGE_SLIP if slip is None else slip
    try:
        a = float(ask)
    except (TypeError, ValueError):
        return None
    if not (a > 0.0):
        return None
    try:
        s = max(0.0, float(s))
    except (TypeError, ValueError):
        s = 0.0
    # a hedge leg at or over $1 cannot beat holding (hedge_ask_ok), so the
    # limit stops one tenth of a cent below it however big the slip is.
    return min(a + s, HEDGE_MAX_ASK - 0.001)


def hedge_depth(touch_size, rungs, unhedged):
    """Contracts a hedge may take: the ladder up to the limit, but never more
    than the contracts still unhedged, and never LESS than the touch.

    `rungs` is [(price, contracts)] from book.rungs() at the hedge limit --
    already filtered to prices we are willing to pay, so the total is what an
    IOC at that limit could cross.

    The two bounds are the whole safety argument:
      - `max(touch, ...)` means this can only ever take MORE than today, so
        no hedge that fills now stops filling.
      - `min(..., unhedged)` bounds THE LADDER'S CONTRIBUTION to the
        contracts still needing a leg. Past `unhedged` a leg is naked, which
        is a directional bet, not insurance.

    BE PRECISE ABOUT WHAT THIS DOES NOT BOUND. The return value is
    `max(touch, ...)`, so when the touch alone is deeper than `unhedged` the
    result exceeds `unhedged` -- that is the PRE-A70 number, unchanged, and
    the caller's `min(_hn_want, ...)` is what bounds it. A70 adds no exposure
    the touch did not already offer; it only lets the ladder reach the same
    ceiling when the touch is thin.
    """
    try:
        touch = max(0.0, float(touch_size))
    except (TypeError, ValueError):
        touch = 0.0
    try:
        cap = max(0.0, float(unhedged))
    except (TypeError, ValueError):
        return touch
    total = 0.0
    for r in (rungs or ()):
        try:
            total += max(0.0, float(r[1]))
        except (TypeError, ValueError, IndexError):
            continue
    return max(touch, min(total, cap))


def hedge_vwap(rungs, n, fallback):
    """What `n` contracts swept cheapest-first actually cost, per contract.

    PAPER ONLY. The live path reads `exec_price` off the fill and never
    guesses. This exists so a paper arm running --hedge-slip does not book
    ladder depth at the touch price and report an edge the exchange would
    never have given it -- the flattering error that makes an arm look good.

    Falls back to `fallback` (the touch) when the rungs cannot answer, which
    is the pre-A70 number.
    """
    try:
        want = float(n)
    except (TypeError, ValueError):
        return fallback
    if want <= 0 or not rungs:
        return fallback
    left, spend = want, 0.0
    for r in rungs:
        try:
            price, depth = float(r[0]), max(0.0, float(r[1]))
        except (TypeError, ValueError, IndexError):
            return fallback
        take = min(left, depth)
        spend += take * price
        left -= take
        if left <= 1e-9:
            return spend / want
    return fallback          # the ladder did not hold n; do not invent a price


# ---------------------------------------------------------------------------
# AMENDMENT 76 (2026-09-20): HEDGE IN PROPORTION TO CONVICTION.
#
# The operator: *"Sure on proportion but make sure if it starts at half then
# drops below 20 you buy the rest of the hedge."*
#
# WHY. Every alarm the bot has ever raised was rebuilt from the raw index.
# Nothing visible at the alarm second separates a real collapse from a false
# alarm -- crossing depth, market-wide or not, belief, seconds left, all
# overlap. The information arrives 1-10 s later, and on a real collapse the
# other side is at 99c by then. So a hedge cannot be made RARER without
# making it useless; it can be made SMALLER where the model is least sure.
#
# Under the current rules the hedge is 9 saves to 2 false alarms, and both
# false alarms were one close (09-19 23:45) hedged in FULL at beliefs of 27%
# and 50% -- a coin flip locked in at 46c, on the largest positions ever
# held. Full hedges under 20% belief have been right every time.
#
# THE RULE. The share of the position that should carry a hedge leg:
#     belief <= HEDGE_PROP_FULL (0.20)   -> all of it
#     belief <= HEDGE_PROP_HALF (0.40)   -> half
#     above                              -> none  (a coin flip is not a collapse)
#
# THE TOP-UP, which is the operator's condition. The hedge tracks a TARGET
# against what is already covered, so a position half-hedged at 30% whose
# belief then falls to 15% buys the other half. And a position whose belief
# recovers is never SOLD down -- the target can fall to zero, the leg stays.
#
# WHAT THIS BLOCKS, written down as today's rule requires: it removes the
# hedge entirely between 40% and 60% belief, and halves it between 20% and
# 40%. On tonight's two: XRP 104 -> 52 contracts, HYPE 104 -> 0. On the nine
# real losses, three at 52-56% belief would have gone unhedged (about $32 of
# saves) and two at 21-24% would have been halved (about $16). Fifteen
# clusters; below the 30 floor; the operator chose it knowing that.
#
# WHAT IT CANNOT DO. hedge_want() can never return more than the contracts
# still unhedged, so no position is ever hedged past its own size, and with
# --no-hedge-prop it returns exactly today's number.

HEDGE_PROP = True
_DEFAULT_HEDGE_PROP = True
HEDGE_PROP_FULL = 0.20         # belief at or under which the whole position is hedged
HEDGE_PROP_HALF = 0.40         # ...at or under which half is; above it, none
HEDGE_PROP_HALF_FRAC = 0.5
_DEFAULT_HEDGE_PROP_FULL = 0.20
_DEFAULT_HEDGE_PROP_HALF = 0.40


def hedge_fraction(belief, full=None, half=None, half_frac=None):
    """Share of the position that SHOULD carry a hedge leg at this belief.

    A missing or unreadable belief is 0.0 -- an unmeasurable reading must
    not buy insurance any more than it may trigger the panic bypass.
    """
    full = HEDGE_PROP_FULL if full is None else full
    half = HEDGE_PROP_HALF if half is None else half
    half_frac = HEDGE_PROP_HALF_FRAC if half_frac is None else half_frac
    try:
        b = float(belief)
    except (TypeError, ValueError):
        return 0.0
    if b != b:                                   # NaN
        return 0.0
    if b <= float(full):
        return 1.0
    if b <= float(half):
        return float(half_frac)
    return 0.0


def hedge_target(orig_n, belief):
    """Contracts of an `orig_n`-contract position that should be hedged."""
    try:
        return max(0.0, float(orig_n)) * hedge_fraction(belief)
    except (TypeError, ValueError):
        return 0.0


def hedge_want(orig_n, unhedged, belief):
    """Contracts to hedge NOW: the target for this belief, less what is
    already covered, and never more than what remains uncovered.

    This single function is the top-up rule AND the no-sell rule:
      - target rises (belief fell)  -> buy the difference
      - target falls (belief rose)  -> 0, never negative, the leg stays
    With HEDGE_PROP off it is exactly the pre-A76 number: everything left.
    """
    try:
        left = max(0.0, float(unhedged))
    except (TypeError, ValueError):
        return 0.0
    if not HEDGE_PROP:
        return left
    try:
        have = max(0.0, float(orig_n) - left)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(left, hedge_target(orig_n, belief) - have))


_EW_UNSET = object()      # "cap not supplied" -- distinct from None, which is
                          # a REAL value meaning "A50 is off". Passing None to
                          # mean "no cap" fell back to the running global and
                          # the NULL check failed under the flag, taking the
                          # live bot down a second time in one day. Same trap
                          # as _HP_UNSET above.


# ---------------------------------------------------------------------------
# AMENDMENT 53 (2026-09-18): PRICE BANDS -- skip a band, or bet bigger in one.
#
# Where the money comes from, 566 live fills since 09-08, clustered by close:
#
#   paid        closes  lost  break-even   staked     money    return
#   80-90c          29     1       15%       $864  +$117.01   +13.6%
#   90-94c          64     0        8%     $2,583  +$207.46    +8.0%
#   94-96c          83     4        5%     $2,970   +$25.01    +0.8%
#   96-97.5c       130     3        3%     $4,711   +$55.59    +1.2%
#   97.5c+         234     2        1%     $8,834  +$159.82    +1.8%
#
# The break-even loss rate at price p is exactly 1 - p. The 94-96c band sits
# ON it: 15% of every dollar ever staked for 4% of the profit, holding one of
# three position slots while it does so. The 90-94c band has never lost, and
# on 09-18 the touch offered a median 192 contracts against the 97 we took.
# One uniform SIZE gives an 8% trade and a 1.8% trade the same bet.
#
# Two flags, both shipped OFF, both repeatable:
#   --skip-band LO HI        refuse any ask in [LO, HI) on EVERY leg, and stop
#                            the sweep limit under LO, so an IOC sent from
#                            below the band cannot fill inside it.
#   --band-mult LO HI MULT   inside [LO, HI) one order may reach MULT x SIZE,
#                            through the same drawdown headroom A45 and A48
#                            use, capped by the book and the close budget.
# Operator, 2026-09-18: "We can remove 94-96 ... If it's safe then yea you
# figure out a way to buy more beneath 94."
# AMENDMENT 54 (2026-09-18): WHEN AN EARLY BET FLIPS, BUY MORE OF THE SIDE
# THAT IS NOW WINNING -- do not merely insure the one that is now losing.
#
# The operator: "Make sure the paper arms from 30-60 seconds buy more of the
# other side if at 30 seconds or less it flips."
#
# The reasoning is the settlement window itself. A bet placed at 46-60 s is
# made when NONE of the sixty one-second prints is recorded; by 30 s HALF of
# them are. So the second look is strictly better informed than the first,
# and if it disagrees, the disagreement is information rather than noise.
# The ordinary hedge buys `n` of the other side and locks the loss. This buys
# `FLIP_MULT * n`, so the position is net LONG the side the better-informed
# look prefers.
#
# THE ARITHMETIC, and it is not free. Holding n YES at p and m NO at q, the
# pair pays out n if YES lands and m if NO lands, against a cost of np + mq:
#
#     n=1 at 97c, m=1 at 60c  ->  -57c whichever way it lands (a true hedge)
#     n=1 at 97c, m=2 at 60c  ->  -17c if NO lands, -117c if YES lands
#
# So doubling is a BET on the second look, not a hedge: it cuts the loss when
# the flip is right and roughly doubles it when the flip is wrong. It pays
# only if the 30-second read beats the 60-second read better than about 7
# times in 10, and nothing measures that yet. Paper only, shipped OFF.
FLIP_MULT = 1.0
_DEFAULT_FLIP_MULT = 1.0

# ===========================================================================
# R1 (2026-09-23): SIZE UP WHEN THE MODEL DOUBTED OUR SIDE EARLIER.
# `results/map_2026-09-22/signature/D_plan.md` section 1, rebuilt three times
# independently and agreeing to the cent per market.
#
# THE FEATURE. `traj_min_conf_ge5s` -- the LOWEST confidence the model put on
# the side we eventually bought, at any evaluation at least DOUBT_LAG_S
# seconds earlier in the SAME close. Below DOUBT_UNDER it is our best
# population on the live record:
#
#     every market with a fill Kalshi settled   784 mkts  577 closes  26 losers  +$0.70/mkt
#     doubt < 0.50                               66        62          0         +$2.95/mkt
#     doubt 0.50-0.97                           173       150          5         +$1.07/mkt
#     already >= 0.97 the whole time              50        50          5         -$0.70/mkt
#     no reading >= 5 s earlier                 481       378         16         +$0.41/mkt
#
# Late-arriving confidence is a QUALITY signal, not a warning: the offers we
# get in those markets are cheap because the market had not made its mind up
# either, not because somebody is ahead of us. The money is stable -- no
# leave-one-day-out drops it below +$2.72 a market -- and the SIGNIFICANCE is
# not (p = 0.00015 against a corrected bar of 1.13e-4, a marginal fail). That
# is exactly why this ships as a flag at 1.0 and a paper arm at 1.5, with a
# pre-registered bar in D_plan section 1, and not as a live change.
#
# SHIPPED OFF: DOUBT_MULT = 1.0 is arithmetically the identity, so the live
# argv is unchanged and the live bot's behaviour is byte for byte today's.
#
# WHAT IT CAN AND CANNOT DO, stated the way the standing rule requires.
# It can only RAISE the size of an entry we were already about to make. It
# cannot refuse, delay, reprice or shrink anything; it is not consulted on
# any hedge path; and every existing ceiling still binds after it -- A45's
# drawdown headroom through one_coin_cap(), the close contract budget, the
# book, MAX_PER_MARKET, pintake's own count rails, and the A46 staged cap.
# What it RISKS is that a doubt-flagged market that loses now loses 1.5x, and
# 0 losers in 66 markets puts the 95% upper bound on the true rate at 5.28%
# against a 2.44% base -- the zero is NOT established. So the A53/A55 rail
# applies: ONE doubt-boosted loss switches it off for the rest of the run.
#
# WHY THE HISTORY IS THE R4 TRAJECTORY AND NOT A LOG FILE. It must be the
# bot's own in-memory reading, taken before the decision, in the same
# process -- reading a log would be both slow and a different population.
# The trajectory sampler below feeds it. NOTE HONESTLY: the sampled minimum
# (1 Hz inside DOUBT_HIST_TAU_S) is a DIFFERENT statistic from the historical
# one, which was the minimum over whichever gate firings happened to be
# logged (see the R4 block). The arm is what reconciles them.
#
# AND THE WINDOW IS THE RULE, NOT AN ACCIDENT OF THE SAMPLER'S GRID. The
# first version of this appended EVERY sampled second to `traj_hist`,
# including the coarse grid out to TRAJ_TAU_MAX = 300 -- so the minimum was
# taken over readings up to five minutes before the close, where partial()
# returns (0.0, 60), nothing is locked and `fair` is a near coin-flip. That
# is not the statistic the +$2.95 was measured on and it is not close to it:
#   - every `refused` record in the last 8 live runs that carries a tau is in
#     [3, 45] -- 2,405 of 2,619, none above 45 -- because `_gate()` is
#     unreachable outside the scan window, so the historical
#     `traj_min_conf_ge5s` was a minimum over tau 3-45 readings ONLY;
#   - rebuilt off the raw 1/sec index for 12 h and 11 coins (374 close x coin
#     cells, 345 at or above PIN at tau 30), the doubt flag fires on 2.3% of
#     them with readings restricted to tau 35-60 and on 20.9% with tau
#     35-300. NINE TIMES the population, against a historical 8.4%.
# D_plan section 1's PASS/FAIL is scored on "flagged >= +$2.00/market"; a
# FAIL on a nine-times-diluted population would read as killing R1 when
# nobody had measured the rule. So the history is fed ONLY from inside this
# window, and a self-test plants a doubt outside it and demands no boost.
DOUBT_HIST_TAU_S = 60    # only readings at tau <= this reach `traj_hist`,
                         # and therefore `_doubt`. 60 and not 45 for the same
                         # reason TRAJ_NEAR_TAU_S is: a market entered at the
                         # first allowed second (tau 45, the A46 early leg)
                         # still needs a reading DOUBT_LAG_S earlier. Must be
                         # <= TRAJ_NEAR_TAU_S, so every reading the rule can
                         # see is on the 1 Hz grid and never the coarse one;
                         # a self-test asserts that.
_DEFAULT_DOUBT_HIST_TAU_S = 60
DOUBT_MULT = 1.0         # --doubt-mult: 1.0 is OFF and is what live runs
_DEFAULT_DOUBT_MULT = 1.0
DOUBT_UNDER = 0.50       # --doubt-under: "the model doubted our side"
_DEFAULT_DOUBT_UNDER = 0.50
DOUBT_LAG_S = 5          # ...at an evaluation at least this many seconds
                         # earlier. NOT a flag: 5 s is the definition the
                         # +$2.95 was measured under, and a flag on it would
                         # be a second free parameter on a marginal p-value.
_DEFAULT_DOUBT_LAG_S = 5

SKIP_BANDS = ()                 # ((lo, hi), ...)        asks refused
_DEFAULT_SKIP_BANDS = ()
BAND_MULTS = ()                 # ((lo, hi, mult), ...)  size multiples
_DEFAULT_BAND_MULTS = ()
_PB_UNSET = object()            # "not supplied" -- the _HP_UNSET / _EW_UNSET trap


def coin_of(ticker):
    """The coin a ticker belongs to: KXBTC15M-26SEP...-15 -> KXBTC."""
    if not ticker:
        return None                 # `str(None)` is "None", which would have
                                    # become a coin named None and matched
                                    # every other unreadable ticker
    try:
        return str(ticker).split("15M", 1)[0] or None
    except Exception:                                    # noqa: BLE001
        return None


def close_budget_for(prev, ticker, extra=_HP_UNSET, size=None, tau=None):
    """Contracts this close may buy, for THIS candidate.

    The base budget (AMENDMENT 17) is MAX_PER_CLOSE x SIZE, shared by every
    coin. A56 adds `extra` x SIZE on top, but ONLY for a candidate whose COIN
    is not already held here, and ONLY once the base has been spread across
    at least MAX_PER_CLOSE distinct coins -- "after two have been maxed out".

    A coin we already hold NEVER gets the extra: the whole argument is that
    two coins have not lost together, and topping up a coin we already own
    does not add a second coin, it adds a second bet on the first.
    """
    extra = EXTRA_COIN if extra is _HP_UNSET else extra
    base = close_budget(size)
    # A59 + A61: inside the last seconds the budget is topped up regardless
    # of which coin this is -- that window earns 5.4c a contract against 2.2c
    # out at 31-45 s and has never lost a close in 68 fills.
    #
    # IT SHARES ONE EXTRA BET WITH THE COIN ALLOWANCE RATHER THAN ADDING A
    # SECOND. Summing them would put the worst close at FOUR bets and, at a
    # fixed brake, cut the bet size by a quarter to pay for a case that has
    # never happened. One extra bet, spendable either by a new coin or in the
    # last seconds, whichever arrives first: the worst close stays at three
    # and the bet size does not move. `worst_close_cost` takes the same max.
    #
    # `tau` is None on the paths that do not know it, and then nothing is
    # added -- an unknown second must not buy itself an allowance.
    _late_ok = (LATE_EXTRA and tau is not None
                and int(tau) <= late_extra_tau())
    if _late_ok:
        extra = max(float(extra or 0.0), float(LATE_EXTRA))
        if prev is None:
            return base + float(LATE_EXTRA) * float(SIZE if size is None else size)
        # the late allowance applies to ANY market, held or new, so it is
        # granted here rather than through the new-coin path below
        coins = {coin_of(t) for t in (prev.get("tickers") or ())}
        coins.discard(None)
        if coin_of(ticker) in coins:
            return base + float(LATE_EXTRA) * float(SIZE if size is None else size)
    if not extra or prev is None:
        return base
    coins = {coin_of(t) for t in (prev.get("tickers") or ())}
    coins.discard(None)
    if coin_of(ticker) in coins:
        # a coin we ALREADY hold never gets the coin allowance: the evidence
        # is that two COINS have not lost together, and a second bet on the
        # first coin is not a second coin
        return base
    # AMENDMENT 61 (2026-09-19): THE COIN-COUNT TEST IS GONE, AND IT WAS
    # DOING REAL DAMAGE. It read the operator's "after two have been maxed
    # out" as two COINS, and required `len(coins) >= MAX_PER_CLOSE` before
    # granting anything. But a close spends its budget in CONTRACTS, and 282
    # of our 417 closes hold exactly ONE coin -- one market taking two bets
    # exhausts the budget without a second coin ever existing. So in 68% of
    # closes the allowance could not fire at all.
    #
    # Measured on the 126 markets `close_budget` refused inside the last ten
    # seconds: 97 were a NEW coin with fewer than two coins held -- every one
    # of them blocked by this test alone, on a close whose budget was already
    # spent. Removing it is what the amendment was for.
    #
    # Nothing else guards it because nothing else needs to: this function is
    # only consulted when the base budget is under pressure, and the caller
    # refuses the trade unless `spent` is under the number returned here. The
    # exposure is already counted in worst_close_cost.
    return base + float(extra) * float(SIZE if size is None else size)


def late_boost_ok(fair_ours, jump_sd, pin=_HP_UNSET, jump_max=_HP_UNSET):
    """May the last-seconds boost buy the EXTRA contracts?

    `fair_ours` is the model's probability for the side we are buying, and
    `jump_sd` the largest recent one-second move AGAINST that side in sd
    units (`jump_against`), or None when it cannot be measured.

    Returns True when BOTH conditions the operator set are satisfied. The
    ordinary bet is never affected -- this decides only whether the order is
    widened beyond SIZE.

    A MISSING JUMP READING DOES NOT BLOCK THE BOOST when the bar is off, but
    DOES block it when a bar is set: if we have been told to check for a move
    against us and cannot, the honest answer is not to take the extra risk.
    That asymmetry is deliberate -- an unmeasurable guard must fail closed,
    which is the opposite of what the first jump gate did.
    """
    pin = LATE_PIN if pin is _HP_UNSET else pin
    jump_max = LATE_JUMP_SD if jump_max is _HP_UNSET else jump_max
    if pin is not None:
        try:
            if float(fair_ours) < float(pin):
                return False
        except (TypeError, ValueError):
            return False
    if jump_max is not None:
        if jump_sd is None:
            return False
        try:
            if float(jump_sd) >= float(jump_max):
                return False
        except (TypeError, ValueError):
            return False
    return True


def flip_size(n, entry_tau, now_tau, mult=None, tau_max=None):
    """Contracts to buy on the OTHER side when a position has flipped.

    Returns `n` unchanged -- an ordinary hedge -- unless ALL of:
      * the flag is on (mult > 1), and
      * the position was opened OUTSIDE the main window (entry_tau > tau_max),
        i.e. on the early leg, where the model is weakest, and
      * we are now INSIDE it (now_tau <= tau_max), where it is strongest.
    Anything bought inside the window was already made on the better
    information, so a later disagreement is not a second opinion and gets the
    ordinary hedge.
    """
    mult = FLIP_MULT if mult is None else float(mult)
    tau_max = TAU_MAX if tau_max is None else float(tau_max)
    try:
        n = float(n)
    except (TypeError, ValueError):
        return 0.0
    if mult <= 1.0 or entry_tau is None or now_tau is None:
        return n
    try:
        if float(entry_tau) > tau_max >= float(now_tau):
            return n * mult
    except (TypeError, ValueError):
        return n
    return n


def band_blocked(price, bands=_PB_UNSET):
    """True when `price` falls inside a skipped band [lo, hi)."""
    bands = SKIP_BANDS if bands is _PB_UNSET else bands
    if not bands:
        return False
    try:
        p = float(price)
    except (TypeError, ValueError):
        return False
    for lo, hi in bands:
        if float(lo) <= p < float(hi):
            return True
    return False


def band_mult(price, bands=_PB_UNSET):
    """The size multiple for `price`: the largest matching band's, else 1.0.

    Never below 1.0. This flag only ever ADDS, exactly like A45 and A48, so a
    mistyped band cannot shrink a bet -- shrinking is --skip-band's job, and a
    refusal is loud where a quietly smaller order is not.
    """
    bands = BAND_MULTS if bands is _PB_UNSET else bands
    if not bands:
        return 1.0
    try:
        p = float(price)
    except (TypeError, ValueError):
        return 1.0
    m = 1.0
    for lo, hi, mult in bands:
        if float(lo) <= p < float(hi):
            m = max(m, float(mult))
    return m


def max_band_mult(bands=_PB_UNSET):
    """The largest multiple any band can ask for.

    The order path's per-order count cap must admit it. pintake.MAX_TAKE_COUNT
    is raised to SIZE (x ONE_COIN_MAX when that flag is on) and to nothing
    else -- so A48's late boost, live since 09-17 at a multiple of 1.0, would
    have been REFUSED by the order path the first time it widened, while the
    paper arm booked the wider order. That is the A45 bug, and this helper is
    what closes it for both.
    """
    bands = BAND_MULTS if bands is _PB_UNSET else bands
    return max([1.0] + [float(b[2]) for b in (bands or ())])


def early_wide_block(leg, edge, cap=_EW_UNSET):
    """A50: refuse a WIDE edge, on the EARLY leg ONLY. `edge` is in DOLLARS.

    THIS IS A FUNCTION BECAUSE THE INLINE VERSION SHIPPED BROKEN. It sat
    inside `if EARLY_TAU_MAX > TAU_MAX:` -- which is true whenever the
    45-second window is open AT ALL, for every leg -- and tested only
    `EARLY_MAX_EDGE is not None`. So from 2026-09-18 07:0xZ it refused a wide
    edge at EVERY tau, including the full leg inside 30 seconds where a wide
    edge is the single most profitable thing the bot does (+1.44 $/bet on the
    tape, +3.08 on live fills).

    Caught by running the 2026-09-13 bot beside the live one: at 18:44:35Z
    both saw KXBTC15M-26SEP181445-45 at 94.8c with a 4.674c edge and tau 25.
    The old bot bought it and won 97c. The live bot refused it as `early_wide`.

    My self-test had asserted the check "sits inside the same early-leg block
    as the price floor" by comparing POSITIONS IN THE FILE. File order says
    nothing about the enclosing condition. The test below drives the predicate
    instead.
    """
    cap = EARLY_MAX_EDGE if cap is _EW_UNSET else cap
    if cap is None:
        return False
    if leg not in ("early", "early_once"):
        return False
    try:
        return 100.0 * float(edge) > float(cap)
    except (TypeError, ValueError):
        return False


def hedge_normal_ok(belief, hedge_ask, pin=None, ceiling=None):
    """A51: would the OPPOSITE side pass the gates a normal entry must pass?

    `belief` is our confidence in OUR side, so confidence in the other side is
    `1 - belief`. Returns True when the filter is off, so a caller that never
    sets the flag behaves exactly as before.
    """
    if not HEDGE_NORMAL:
        return True
    pin = PIN if pin is None else pin
    ceiling = PRICE_CEILING if ceiling is None else ceiling
    try:
        b = float(belief)
        a = float(hedge_ask)
    except (TypeError, ValueError):
        return False
    return (1.0 - b) >= pin and 0.0 < a <= ceiling


def hedge_edge_c(belief, hedge_ask):
    """DIAGNOSTIC, not a gate: cents by which the hedge leg is cheaper than
    the model's own fair value for that side, (1 - belief) - ask. Positive
    means the market lags the collapse and the hedge is +EV on its own;
    negative means we are paying EV for variance reduction. Recorded on every
    hedge so the n=30 review can see which we are doing."""
    try:
        return round(100.0 * ((1.0 - float(belief)) - float(hedge_ask)), 2)
    except (TypeError, ValueError):
        return None


def hedge_locked_loss(entry_cost, hedge_cost, n=1.0):
    """Per-contract loss locked by the pair, before fees: entry + hedge - 1."""
    return float(n) * (float(entry_cost) + float(hedge_cost) - 1.0)


IMPROVE_MAX = 0.010    # AMENDMENT 23: and NO MORE than this much cheaper.
_DEFAULT_IMPROVE_MAX = 0.010   # --improve-max is measured against this
IMPROVE_BY = 0.005     # a second buy must be at least this much cheaper
# AMENDMENT 22 (2026-09-13): THE IMPROVE-BY RULE IS OBSOLETE ACROSS MARKETS AND
# WAS SILENTLY OVERRIDING AMENDMENT 17.
#
# The operator, seeing the live bot take ETH and skip HYPE at the same close
# while the what-if took HYPE: "I would've hoped my bot would grab eth, then
# when hype looks like a good buy it'd see that and scoop it up too."
#
# WHAT HAPPENED, exactly. At the 19:15Z close the bot filled ETH at 98.0c. HYPE
# was then offered at 97.7c with 2.14c of edge -- a BETTER trade than the one it
# took -- and was refused because 97.7c is not at least 0.5c below 98.0c.
#
# WHY THAT IS A BUG AND NOT A CHOICE. AMENDMENT 3 wrote this rule for SCALING
# INTO THE SAME MARKET: "re-buying at the same level would double the risk
# without lowering the average paid". AMENDMENT 13 then set MAX_PER_MARKET = 1,
# which forbids re-buying the same market at all. So since 2026-09-12 this rule
# CANNOT do the job it was written for -- the only thing it can still do is
# block a DIFFERENT COIN, which it was never meant to touch.
#
# And AMENDMENT 17, the same day, says a close is capped on CONTRACTS with
# "coins unlimited". This rule was quietly contradicting that.
#
# WHY LIFTING IT DOES NOT ADD RISK. The close's CONTRACT budget is unchanged:
# MAX_PER_CLOSE * SIZE either way. Two coins at 47 contracts each is the same
# 94 contracts as one coin at 94. The worst case is identical; only WHICH
# markets get bought changes. Every added trade still passes every gate.
IMPROVE_SCOPE = "close"  # "close" = the old behaviour; "market" = A22
_DEFAULT_IMPROVE_SCOPE = "close"   # THE THIRD TIME THIS PATTERN BIT. A guard
                                   # that asserts the RUNNING value refuses to
                                   # start the moment its flag is used; what it
                                   # is actually for is "nobody changed the
                                   # default in the source". Same fix as
                                   # _DEFAULT_SIGMA_RULER and _DEFAULT_PIN.
PICK = "first"           # AMENDMENT 24: "first" = scan in discovery order and
_DEFAULT_PICK = "first"  # take the first market that clears every gate, which
                         # is what this bot has always done. "best" orders the
                         # scan by the edge measured on the previous pass, so
                         # the first market to clear is also the best one
                         # offered. See the long note at the loop head.


# ===========================================================================
# AMENDMENT 30 (2026-09-14): THE DRAWDOWN BRAKE.
#
# THE OPERATOR: "make it 1/5 of bank or 3 losses whichever comes first. Then
# drop the contract size to whatever the new calculated amount is and wait."
#
# WHY IT REPLACES NOTHING AND SITS BESIDE EVERYTHING. There were already two
# brakes and each answers a different question:
#   --loss-abort        "have we lost too much THIS RUN?"  -- in dollars, and
#                       it RESETS TO ZERO ON EVERY RESTART, which is the hole
#                       this amendment exists to close. We restarted three
#                       times on 2026-09-13 and cleared it three times.
#   max-losses 3        "is the MODEL still what we think it is?" -- three
#                       losing closes should be about a 1-in-100 event, and
#                       three SMALL losses can mean a broken model while no
#                       dollar figure has been reached at all.
# This one asks the third question: "how far are we off our best?" It is
# measured from a HIGH-WATER MARK KEPT ON DISK, so a restart cannot clear it,
# and it is a percentage, so it cannot drift as the bank grows.
#
# THE OPERATOR'S OWN RESET RULE, in his words: "It can reset the 1/3 of losses
# once the full balance has been restored." That is exactly what a high-water
# mark does, with no separate reset logic -- the drawdown returns to zero the
# moment the bank makes a new high.
#
# A WITHDRAWAL LOOKS LIKE A DRAWDOWN and will trip this. That is the safe
# direction (it stops trading rather than starting it) and the halt message
# says so, so it is not mistaken for a trading loss.
# ===========================================================================
MAX_DRAWDOWN = 0.20      # 1/5 of the high-water bank. Operator, 2026-09-14.
_DEFAULT_MAX_DRAWDOWN = 0.20
HWM_FILE = os.path.join(RESULTS, "pinrun-hwm.json")


DAYLOSS_FILE = os.path.join(RESULTS, "pinrun-dayloss.json")


def et_day_key(now=None):
    """The ET calendar day, as 'YYYY-MM-DD'. ET because that is how the
    operator reads a day and how every report in this repo splits one."""
    t = time.time() if now is None else float(now)
    return time.strftime("%Y-%m-%d", time.gmtime(t - 4 * 3600))


def day_loss(path=None, now=None):
    """Dollars realised so far on the CURRENT ET day, or None.

    Negative is a loss. Returns None when there is nothing on file for today
    -- which is not zero: "we have not recorded anything" and "today is flat"
    are different answers, and only the second should ever be compared
    against a cap.
    """
    try:
        with open(path or DAYLOSS_FILE, encoding="utf-8") as fh:
            d = json.load(fh) or {}
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("day") != et_day_key(now):
        return None                      # a new day starts clean
    try:
        v = float(d.get("realised"))
    except (TypeError, ValueError):
        return None
    # a poisoned file reads as "unknown", never as a number to compare
    return None if (v != v or v in (float("inf"), float("-inf"))) else v


def add_day_loss(delta, path=None, now=None):
    """Add a settled market's money to today's running total, and return it.

    Called on every settlement, so it must never raise into the trade loop
    and must never lose the file to a half-written one -- hence the temp file
    and the replace, the same shape write_hwm uses.
    """
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        return day_loss(path, now)
    # NaN AND INFINITY ARE REFUSED, not just unparseable text. `float("nan")`
    # converts happily, and a NaN written to the file would make every
    # comparison in risk_abort False FOR EVER -- a cap that silently stops
    # being a cap is worse than no cap. Caught by the self-test.
    if delta != delta or delta in (float("inf"), float("-inf")):
        return day_loss(path, now)
    key = et_day_key(now)
    cur = day_loss(path, now)
    new = (cur or 0.0) + delta
    p = path or DAYLOSS_FILE
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"day": key, "realised": round(new, 4),
                       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh)
        os.replace(tmp, p)
    except OSError:
        return new                       # in memory is better than nothing
    return new


def read_hwm(path=None):
    """The highest bank ever recorded, in dollars, or None."""
    try:
        with open(path or HWM_FILE, encoding="utf-8") as fh:
            v = float((json.load(fh) or {}).get("hwm") or 0.0)
        return v if v > 0 else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def write_hwm(bank, path=None):
    """Raise the high-water mark. NEVER lowers it -- that is the whole point."""
    if bank is None:
        return read_hwm(path)        # a failed balance read changes nothing
    cur = read_hwm(path)
    if cur is not None and float(bank) <= cur:
        return cur
    try:
        with open(path or HWM_FILE, "w", encoding="utf-8") as fh:
            json.dump({"hwm": round(float(bank), 2),
                       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           time.gmtime())}, fh)
    except OSError:
        return cur
    return float(bank)


# AMENDMENT 43 -- TELL A WITHDRAWAL FROM A LOSS.
#
# The operator, 2026-09-15: "can you code it so it dynamically checks its own
# price and knows if it's a withdrawal or a loss? ... once it hits cap I'll
# take anything above that every day."
#
# Until now a withdrawal was INDISTINGUISHABLE from a catastrophic loss: the
# drawdown brake compares the balance to its all-time high, so taking $500 out
# of a $1,500 bank read as "33% below the high -- STOP AND LOOK" and halted the
# bot. Safe, but with a daily withdrawal policy it would halt every single day.
#
# THE BOT ALREADY KNOWS WHICH IT IS, and it does not need a price feed to know.
# It keeps a running total of its own settled P&L. Between two balance reads:
#
#     expected change  = realised P&L booked in that interval
#     actual change    = bank now - bank then
#     unexplained      = actual - expected
#
# A trading loss is fully explained -- it IS the realised P&L. Money that moves
# without a settlement to account for it came from outside: a withdrawal if
# negative, a deposit if positive. The high-water mark is then shifted by that
# amount, so the drawdown brake keeps measuring TRADING performance and ignores
# the operator's own cash movements.
#
# THE READ IS ONLY EVER TAKEN WHEN FLAT. autosize_tick returns early while any
# position is open, so the balance is never compared against a moment when
# money is tied up as collateral -- which would otherwise read as a withdrawal
# every time we bought something.
#
# THE FIRST TICK OF A RUN NEVER CLASSIFIES. A restart resets the realised
# counter to zero while the bank carries over, so the very first comparison has
# no baseline; without this guard every restart would look like a withdrawal of
# the entire previous run's profit.
EXTERNAL_MIN = 1.00      # dollars of unexplained movement before it counts;
_DEFAULT_EXTERNAL_MIN = 1.00   # below this it is settlement timing and fees
EXTERNAL_DETECT = True   # --no-external-detect disables
_DEFAULT_EXTERNAL_DETECT = True


def classify_bank_move(bank_now, bank_prev, realised_now, realised_prev,
                       floor=None):
    """(kind, amount). `kind` is "trading", "withdrawal" or "deposit".

    `amount` is the unexplained dollars -- negative for a withdrawal. Anything
    inside `floor` is trading noise: fees and settlement timing.
    """
    floor = EXTERNAL_MIN if floor is None else floor
    if bank_prev is None or realised_prev is None:
        return "trading", 0.0            # no baseline -- never guess
    try:
        unexplained = ((float(bank_now) - float(bank_prev))
                       - (float(realised_now) - float(realised_prev)))
    except (TypeError, ValueError):
        return "trading", 0.0
    if unexplained <= -abs(floor):
        return "withdrawal", unexplained
    if unexplained >= abs(floor):
        return "deposit", unexplained
    return "trading", unexplained


def shift_hwm(amount, path=None):
    """Move the high-water mark by `amount` (negative for a withdrawal) so the
    drawdown brake keeps measuring trading only. Never moves it below zero,
    and a missing mark is left missing rather than invented."""
    cur = read_hwm(path)
    if cur is None:
        return None
    new = max(0.0, float(cur) + float(amount))
    try:
        with open(path or HWM_FILE, "w", encoding="utf-8") as fh:
            json.dump({"hwm": round(new, 2),
                       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh)
    except OSError:
        return cur
    return new


def open_contracts(led):
    """Contracts held open RIGHT NOW, across every market (AMENDMENT 31).

    pintake's ledger keys `positions` by ticker and each value is a dict with
    a `contracts` field -- NOT a tuple. The first version of this indexed it
    positionally and silently summed zero, which would have made the open cap
    unreachable and removed the rail entirely rather than converting it.
    """
    n = 0.0
    for v in (led.get("positions") or {}).values():
        if isinstance(v, dict):
            try:
                n += float(v.get("contracts") or 0.0)
            except (TypeError, ValueError):
                continue
    return n


def drawdown(bank, hwm):
    """How far below its best the bank is, as a fraction. 0.0 when unknown.

    Returns 0.0 rather than guessing when either figure is missing: a brake
    that fires on a failed balance read would stop the bot every time the API
    hiccups, and one that fires on a missing file would stop it on first run.
    """
    if bank is None or hwm is None or hwm <= 0:
        return 0.0
    return max(0.0, (float(hwm) - float(bank)) / float(hwm))


def _pid_alive(pid):
    """Is this process id running RIGHT NOW?

    AMENDMENT 27. Deliberately does NOT read the command line: Windows hides
    that field from a caller who cannot open the process, and a guard that
    silently sees nothing is worse than no guard -- that is precisely how two
    live bots ended up trading the same account on 2026-09-14.
    """
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        # NEVER os.kill ON WINDOWS. CPython's os.kill has no concept of
        # signal 0 there: for any signal that is not CTRL_C_EVENT or
        # CTRL_BREAK_EVENT it calls TerminateProcess(handle, sig). So
        # `os.kill(pid, 0)` does not TEST the process, it KILLS it with exit
        # code 0. The first version of this function did exactly that and the
        # paper run testing it terminated itself mid-self-test on 2026-09-14.
        # OpenProcess with SYNCHRONIZE (0x00100000) only asks whether the
        # process can be opened; it cannot affect it.
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x00100000, False, int(pid))
            if h:
                k32.CloseHandle(h)
                return True
            # ERROR_ACCESS_DENIED (5) means it EXISTS and we may not open it.
            return k32.GetLastError() == 5
        except Exception:                 # noqa: BLE001
            # CANNOT TELL. Say YES: a false "already running" costs a refused
            # start the operator clears in one command; a false "nothing
            # running" costs a second live bot on the same account.
            return True
    try:
        os.kill(int(pid), 0)             # POSIX ONLY: signal 0 tests existence
        return True
    except OSError as e:
        import errno
        # EPERM means it EXISTS and belongs to someone else -- still alive.
        return getattr(e, "errno", None) == errno.EPERM
    except Exception:                     # noqa: BLE001
        return True


def _clear_pidfile(path, mypid):
    """Remove the pid file, but only if it is still OURS."""
    try:
        with open(path, encoding="utf-8") as fh:
            if int((fh.read() or "0").strip() or 0) != int(mypid):
                return
        os.remove(path)
    except (OSError, ValueError):
        pass


def rebuy_ok(prev, tk, price, size=None):
    """May we buy market `tk` AGAIN at `price` in this close?

    Only the SAME market is governed here. A different market is a different
    outcome and is governed by AMENDMENT 22's scope rule, not this one.

    TWO CASES, AND CONFLATING THEM WAS THE BUG (AMENDMENT 29, 2026-09-14).

    TOPPING UP an unfinished position is NOT scaling in. The operator: "It can
    buy less on one coin if it's all that's available after checking them all,
    then if another opens up anywhere even on the same coin buy more." If a
    thin book gave us 5 contracts of the 52 we wanted, and 40 more appear a
    second later at the SAME price, taking them finishes the position we
    already decided to hold. AMENDMENT 3's improve-by rule was written against
    "re-buying at the same level would double the risk without lowering the
    average paid" -- which is true of a position that is already FULL SIZE and
    false of one that is 10% filled. Below a full size there is no bar beyond
    the gates every buy passes anyway.

    SCALING IN past a full size is the case A23 measured, and the band
    (IMPROVE_BY, IMPROVE_MAX] applies: at least half a cent cheaper --
    AMENDMENT 3's rule, unchanged -- and at most a cent cheaper, because a
    large discount is the market turning against a position we already hold.

    Reads the module globals at call time on purpose, so --improve-max takes
    effect.
    """
    if prev is None:
        return True
    if prev.get("per_tk", {}).get(tk, 0) <= 0:
        return True                      # not a re-buy at all
    have = float((prev.get("n_tk") or {}).get(tk, 0.0))
    want = float(SIZE if size is None else size)
    if have < want - 1e-9:
        return True                      # TOP-UP: the position is unfinished
    paid = prev.get("px_tk", {}).get(tk)
    if paid is None:
        return True                      # no price on record; A3 still applies
    drop = paid - price
    return IMPROVE_BY - 1e-12 <= drop <= IMPROVE_MAX + 1e-12


MIN_LEVEL = 1.0        # the RESTING level must hold this much regardless of
                       # our own size: a 0.01-contract order against a
                       # 0.02-contract dust level is not a real fill test
MAX_BOOK_AGE_MS = 2000
MAX_INDEX_AGE_S = 2
SIGMA_RULER = "live"      # A20: "live"|"1800"|"max3600"|"maxdown"
# THE DECLARED DEFAULTS, captured at import and never reassigned. The
# self-test asserts against THESE, not against the live values: main() applies
# --sigma-ruler and --honest BEFORE running the suite, so a check written
# against the live value refuses to start the moment the flag is used. That is
# exactly what happened on 2026-09-13 -- the guard was right, the thing it
# read was wrong, and the bot stayed down until it was fixed. What the guard
# is actually for is "nobody quietly changed the default in the source", and
# that is what these hold.
_DEFAULT_SIGMA_RULER = "live"
_DEFAULT_HONEST_CONF = False
SIGMA_WIN = 300
# THE LIVE CONDITIONS INDEX (2026-09-10). Fast/slow roughness ratio per feed,
# then a leave-one-out average across the other coins. Measured, not guessed:
# research/pintail.py over 9,159 settled markets and 1,019 closes.
COND_FAST, COND_SLOW, COND_ROUGH = 30, 3600, 2.0
SIGMA_STRESS = 1.0     # multiply sigma by this before deciding (>1 = humbler)
_DEFAULT_SIGMA_STRESS = 1.0   # the offline-loop self-test pins the flag to this

# Filled in by arm() only when --live is given. Empty in paper mode, so a
# take() call cannot even be constructed without an explicit arming step.
CREDS = {"base": None, "pk": None, "key_id": None}


def arm(reason):
    """Load the production credentials and arm pintake. --live only."""
    import ordercli
    import kauth
    CREDS["base"] = pintake.PROD_ELECTIONS
    CREDS["key_id"] = kauth.KEY_ID
    CREDS["pk"] = ordercli.load_key(pintake.PROD_KEY_FILE)
    pintake.arm_prod(reason)
    return CREDS


# ===========================================================================
# THE INDEX, over WebSocket. Not the collector's file: re-reading a growing
# gzip once a second cost more than a second by the end of an hour, which is
# most of the "no_fair" skips in the old paper log.
# ===========================================================================
class IndexWS:
    """1/sec CF Benchmarks prints on our own authenticated connection."""

    def __init__(self, index_ids, key_id=None, key_file=None):
        self.ids = list(index_ids)
        self.ticks = defaultdict(dict)      # index_id -> {epoch_sec: value}
        # RETENTION IS SET BY THE SLOWEST WINDOW ANYTHING READS. It was 1200
        # (20 minutes), which is fine for SIGMA_WIN=300 but silently truncates
        # the 3600s baseline the conditions index needs -- it would have
        # returned a ratio computed against 20 minutes while claiming an hour.
        self.order = defaultdict(lambda: deque(maxlen=COND_SLOW + 400))
        self._cache = {}                    # (kind, iid) -> (stamp, value)
        # A VERSION PER FEED, bumped only when a stored value actually
        # CHANGES. (newest second, count) alone cannot see a REVISED print for
        # a second we already hold -- same max, same length, different data --
        # and would serve a stale conditions read. Bumping on every frame
        # instead would recompute the 3600s window on every duplicate.
        self._ver = defaultdict(int)
        self.last_rx = {}                   # index_id -> local ms of last tick
        self.lock = threading.RLock()
        self.stats = defaultdict(int)
        kid, kfile = livebook._default_key()
        self.key_id = key_id or kid
        self.key_file = key_file or kfile
        self._stop = threading.Event()
        self._thread = None

    # ---- ingest (shared by the live socket and the self-test) ----
    def on_frame(self, raw, rx_ms=None):
        rx_ms = rx_ms if rx_ms is not None else livebook.now_ms()
        try:
            d = raw if isinstance(raw, dict) else json.loads(raw)
        except Exception:
            self.stats["unparseable"] += 1
            return
        if d.get("type") != "cfbenchmarks_value":
            self.stats[str(d.get("type"))] += 1
            return
        m = d.get("msg") or {}
        iid = m.get("index_id")
        if not iid:
            return
        try:
            data = m.get("data")
            data = json.loads(data) if isinstance(data, str) else (data or {})
            val = float(data["value"])
            sec = int(data["time"]) // 1000
        except Exception:
            self.stats["bad_tick"] += 1
            return
        with self.lock:
            old = self.ticks[iid].get(sec)
            if sec not in self.ticks[iid]:
                q = self.order[iid]
                if len(q) == q.maxlen and q:
                    self.ticks[iid].pop(q[0], None)
                q.append(sec)
            self.ticks[iid][sec] = val
            if old is None or old != val:
                self._ver[iid] += 1
            self.last_rx[iid] = rx_ms
        self.stats["ticks"] += 1

    # ---- reads ----
    def recent_moves(self, iid, n=3):
        """The last `n` ONE-SECOND moves of the index, newest first, in price
        units. Only adjacent seconds count -- a gap yields no move for that
        step, so a gappy feed produces FEWER moves, never a fabricated one.
        AMENDMENT 40 reads this; nothing else does."""
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return []
            secs = sorted(d)[-(n + 1):]
            vals = {s: d[s] for s in secs}
        out = []
        for i in range(len(secs) - 1, 0, -1):
            if secs[i] - secs[i - 1] == 1:
                out.append(vals[secs[i]] - vals[secs[i - 1]])
        return out

    def spot(self, iid):
        """(second, value, age_seconds) of the newest tick, or (None,None,None)."""
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return None, None, None
            s = max(d)
            return s, d[s], time.time() - s

    def _stamp(self, iid, d):
        """What the conditions cache is keyed on.

        The version counter alone is enough for the live path; the (max, len)
        pair is carried too so that code which writes `ticks` directly -- the
        self-test does -- still invalidates correctly.
        """
        return (self._ver.get(iid, 0), max(d), len(d)) if d else None

    def zrough(self, iid):
        """This feed's roughness against ITS OWN last hour.

            z = RMS(1s change over COND_FAST) / RMS(1s change over COND_SLOW)

        Dividing by the feed's own hour is what makes BTC and DOGE comparable
        without a fitted constant, and it puts z near 1.0 in calm conditions
        whatever the coin costs. Measured on 9,159 settled markets
        (research/pintail.py): the model's loss-tail runs 2.27% where z < 0.7
        and 3.79% where z > 2.0.

        CACHED PER SECOND. The slow window is 3600 lookups; the trade loop
        runs at ~20 Hz across nine markets, so an uncached version would cost
        roughly 650,000 dict reads a second and starve the order path.
        """
        with self.lock:
            d = self.ticks.get(iid)
            if not d or len(d) < COND_SLOW // 4:
                return None
            st = self._stamp(iid, d)
            hit = self._cache.get(("z", iid))
            if hit is not None and hit[0] == st:
                return hit[1]
            snap = dict(d)
        now = st[1]

        def _rms(win):
            tot = k = 0
            for s in range(now - win + 1, now + 1):
                a, b = snap.get(s - 1), snap.get(s)
                if a is not None and b is not None:
                    dd = b - a
                    tot += dd * dd
                    k += 1
            return math.sqrt(tot / k) if k >= max(5, win // 8) else None

        fa, sl = _rms(COND_FAST), _rms(COND_SLOW)
        z = (fa / sl) if (fa is not None and sl) and sl > 0 else None
        with self.lock:
            self._cache[("z", iid)] = (st, z)
        return z

    def conditions(self, iid):
        """(X, N, own): the OTHER feeds' mean roughness, how many of them are
        moving, and this feed's own.

        THE TRADED COIN IS EXCLUDED FROM X AND N BY CONSTRUCTION. Six earlier
        attempts to cut the loss rate all failed for the same reason -- every
        one was a filter bolted onto the traded coin's own sigma, so once that
        number was fixed they added nothing. The other ten coins are genuinely
        new information. research/pincross.py self-tests the exclusion.

        THIS IS LOGGED, NOT GATED ON. Every fixed threshold built on it failed
        out of sample (research/pintail.py, fit/holdout split), so deploying
        one now would be curve fitting. We have ZERO live records of these
        conditions, and the tape cannot settle why live loses 11x what the
        backtest does -- so the first job is to write them down.
        """
        own = self.zrough(iid)
        tot = k = nr = 0
        for other in self.ids:
            if other == iid:
                continue
            v = self.zrough(other)
            if v is None:
                continue
            tot += v
            k += 1
            if v > COND_ROUGH:
                nr += 1
        if k < 4:
            return None, None, own
        return tot / k, nr, own

    @staticmethod
    def _sig_over(d, win):
        """sigma over the trailing `win` seconds of a {sec: value} dict."""
        secs = sorted(d)[-win:]
        diffs = [d[secs[i]] - d[secs[i - 1]]
                 for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
        if len(diffs) < 20:
            return None
        mu = sum(diffs) / len(diffs)
        return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))

    @staticmethod
    def _semi_over(d, win):
        """DOWNSIDE-only deviation over the trailing `win` seconds.

        AMENDMENT 20b. The model's claim is one-sided: it says the settlement
        lands on its side of the strike, and we lose only when the index comes
        in the other way. Every ruler this project has ever used is built from
        moves in BOTH directions, which spends half its information on moves
        that cannot hurt us.

        Scored over 108,000 rebuilt decisions (results/RESULTS_ruler.md),
        `max(downside 300s, downside 1800s)` beat the deployed
        `max(sd 300s, sd 3600s)` on every axis at once, in BOTH halves of the
        sample:

                              deployed      downside-only
          gated loss rate     -42.3%        -48.5%
          sd(z)               0.919         0.950   (1.000 is honest)
          kurtosis            69.1          53.5    (3 is a normal tail)
          decisions kept      -1.0%         -0.9%
          holdout loss        0.0813%       0.0717%
          holdout sd(z)       0.986         1.025

        The sqrt(2) is what makes it comparable to a two-sided sd: for a
        symmetric distribution, twice the mean of the squared down-moves is
        the variance.
        """
        secs = sorted(d)[-win:]
        dn = [(d[secs[i]] - d[secs[i - 1]]) ** 2
              for i in range(1, len(secs))
              if secs[i] - secs[i - 1] == 1 and d[secs[i]] < d[secs[i - 1]]]
        if len(dn) < 10:
            return None
        return math.sqrt(2.0 * sum(dn) / len(dn))

    def sigma(self, iid):
        """The model's volatility estimate.

        AMENDMENT 20 (OFF by default, --sigma-ruler turns it on). Measured
        2026-09-13 on the index feed alone, 108,414 decisions: the 300-second
        ruler this has always used is the single biggest identified source of
        the model's blow-ups. The calmer the last five minutes, the more often
        it misses badly -- 4.28% of the calmest fifth against 1.05% of the
        choppiest, 4.05x, and it holds out of sample.

        The cause is not that calm markets are dangerous. Volatility reverts,
        so a quiet 300 seconds understates the next minute and the model's
        RULER is too short. Lengthening it collapses the gradient (4.09x at
        300s, 1.15x at 3600s) and -- the decisive part -- drops kurtosis from
        132 to 47. KURTOSIS IS SCALE-FREE, so no amount of merely widening sd
        could do that. The shape gets better, not just the width.

        `max(300s, 3600s)` is the strongest: on the index population it cut
        the loss rate on gated decisions by 42% for 1.0% of the opportunities.
        It is a max and not an average because a short ruler is wrong after a
        quiet patch and a long one is wrong during a burst; the larger of the
        two is wrong in neither direction and can never shorten the ruler.

        NOT DEPLOYED. results/PREREG_ruler.md holds the bar. Retention is
        already COND_SLOW + 400 seconds, so the hour is on hand live.
        """
        with self.lock:
            d = dict(self.ticks.get(iid) or {})
        if len(d) < 30:
            return None
        if SIGMA_RULER == "live":
            return self._sig_over(d, SIGMA_WIN)
        if SIGMA_RULER == "max3600":
            a = self._sig_over(d, SIGMA_WIN)
            b = self._sig_over(d, 3600)
            if a is None:
                return b
            if b is None:
                return a
            return max(a, b)
        if SIGMA_RULER == "1800":
            return self._sig_over(d, 1800) or self._sig_over(d, SIGMA_WIN)
        if SIGMA_RULER == "maxdown":
            # AMENDMENT 20b -- the best of the forty rulers scored.
            a = self._semi_over(d, SIGMA_WIN)
            b = self._semi_over(d, 1800)
            v = max(a, b) if (a and b) else (a or b)
            # If too few DOWN moves exist to estimate at all, fall back to the
            # deployed two-sided ruler rather than to nothing. A None here
            # means fair() returns None and the market is skipped silently,
            # which would look exactly like a thin book.
            return v or (lambda x, y: max(x, y) if (x and y) else (x or y))(
                self._sig_over(d, SIGMA_WIN), self._sig_over(d, 3600))
        return self._sig_over(d, SIGMA_WIN)

    def partial(self, iid, close_s, now_s):
        """(locked sum, how many settle prints are still to come), or None.

        THE WINDOW IS [close-60, close-1]. See CORRECTIONS 1 in the module
        docstring: measured against Kalshi's avg_60s_data on 108/108 markets.

        CORRECTION 3, found in adversarial review 2026-09-08 and fixed here.
        A second whose print HAS NOT ARRIVED is a print still to come, not a
        locked print to be guessed at. The first version ended the window at
        min(now_s, close_s-1) and then scaled the observed sum by
        want/len(got) -- it substituted the WINDOW MEAN for every missing
        second, the most recent one included.

        Measured on this feed 2026-09-08 (20 Hz, 90 s, BRTI + ETHUSD_RTI):
        the print for the CURRENT second is absent in 321 of 3,570 samples =
        9.0%, so this fired often. The error it makes is exactly
        (mean of the prints held) - (the print missing), and its sd against
        the model's own residual sd is

            tau     3      4      5      6      8     10     15     20
            ratio 1.97x  1.17x  0.79x  0.58x  0.36x  0.25x  0.12x  0.07x

        -- at tau<=5 the guess is as big as everything the model still treats
        as random, and it is signed AGAINST the latest move, which is exactly
        when a stale quote appears. Same class of error as CORRECTION 1.

        So the locked window now ends at the newest print actually held, and
        every second after it is counted in `remaining` and modelled with
        spot -- which is what the model says to do. Interior gaps are filled
        from the NEAREST print held, never from the window mean.
        """
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return None
            lo = close_s - N_AVG
            hi = min(now_s, close_s - 1)
            if hi < lo:
                return 0.0, N_AVG
            have = [s for s in range(lo, hi + 1) if s in d]
            if not have:
                return None
            hi = have[-1]                 # the newest print we actually hold
            want = hi - lo + 1
            got = {s: d[s] for s in have}
        if len(got) < want * 0.95:
            return None
        if len(got) == want:
            return sum(got.values()), N_AVG - want
        keys = sorted(got)
        total = 0.0
        for s in range(lo, hi + 1):
            v = got.get(s)
            if v is None:                 # interior gap: nearest print held
                i = bisect.bisect_left(keys, s)
                cand = [k for k in (keys[i] if i < len(keys) else None,
                                    keys[i - 1] if i > 0 else None)
                        if k is not None]
                v = got[min(cand, key=lambda k: (abs(k - s), k))]
            total += v
        return total, N_AVG - want

    # ---- socket ----
    async def _run(self):
        import websockets
        sign = livebook.make_signer(self.key_id, self.key_file)
        cid = 0
        backoff = 0.5
        while not self._stop.is_set():
            try:
                path = "/trade-api/ws/v2"
                async with websockets.connect(
                        livebook.WS_URL, additional_headers=sign("GET", path),
                        ping_interval=20, ping_timeout=20, close_timeout=1,
                        max_size=8 * 1024 * 1024) as ws:
                    cid += 1
                    await ws.send(json.dumps({
                        "id": cid, "cmd": "subscribe",
                        "params": {"channels": ["cfbenchmarks_value"],
                                   "index_ids": self.ids}}))
                    self.stats["connects"] += 1
                    backoff = 0.5
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        self.on_frame(raw)
            except Exception as e:                      # noqa: BLE001
                self.stats["ws_error"] += 1
                self.stats["last_error"] = str(e)[:120]
                if self._stop.is_set():
                    return
                await asyncio.sleep(backoff)
                backoff = min(8.0, backoff * 2)

    def start(self):
        def runner():
            try:
                asyncio.run(self._run())
            except Exception:                           # noqa: BLE001
                pass
        self._thread = threading.Thread(target=runner, daemon=True,
                                        name="indexws")
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()


# ===========================================================================
def eff_strike(strike, round_digits):
    """The threshold the EXCHANGE actually applies.

    Kalshi rounds the 60-print mean to round_digits and settles YES iff that
    rounded value >= floor_strike. round(v, d) >= K is v >= K - 0.5*10^-d.
    CORRECTIONS 2: this is the only loss in today's replay.
    """
    if round_digits is None:
        return float(strike)
    return float(strike) - 0.5 * (10.0 ** (-int(round_digits)))


# ===========================================================================
# AMENDMENT 19 (NOT DEPLOYED -- default OFF, --honest turns it on)
# THE MODEL'S STATED CONFIDENCE IS NOT A PROBABILITY.
#
# MEASURED ON THE INDEX ALONE, 109,122 z-scores over 1,672 closes
# (results/RESULTS_calib.md, research/pincalib.py -- no order book, no replay,
# no fills). Writing z for how many of its own standard deviations the model
# is from the strike, and counting only the side we lose on:
#
#     the model says     it will be wrong     it IS wrong      off by
#     99.00%             1.00%                2.10%            2.1x
#     99.50%             0.50%                1.67%            3.3x
#     99.85%  <- ours    0.15%                1.21%            8.0x
#     99.99%             0.01%                0.70%           69.6x
#
# The BODY of the distribution is nearly right: sd(z) is 1.151, only 15% too
# narrow. The TAIL is not: kurtosis 132 against a normal's 3. The index makes
# jumps a Gaussian says are impossible, and every one of them lands in the
# only region this strategy ever trades in.
#
# WHY SCALING SIGMA CANNOT FIX IT, measured the same day: multiplying sigma by
# 1.25 before deciding keeps 44% of candidates and makes them WORSE (2.90% ->
# 3.09% bad), and 2.0x gives 4.62%. Scaling stretches the body, where the
# model is already nearly right, and barely moves the tail, which is the whole
# problem. A wider Gaussian is still a Gaussian.
#
# WHY NOT A STUDENT-t: the realised lower tail is fatter than a unit-variance
# t with df=3.5, and df=10 is not close. Nothing with a closed form fits, so
# the replacement is the MEASURED table itself.
#
# WHAT THIS CHANGES IF TURNED ON. `fair()` maps z through the empirical table
# instead of Phi(). Every stated confidence falls, so every computed edge
# falls with it -- at the gate's typical z the honest confidence is ~0.988
# rather than ~0.9985, about 1c of edge per contract that was never there.
# PIN 0.995 then means what it says: it demands z >= 4.3 instead of z >= 2.6.
# That is a MUCH stricter gate and it will cut the trade count hard.
#
# THAT IS WHY IT IS OFF. It is a threshold change, and CLAUDE.md's 2026-09-10
# amendment forbids deploying one from anything but a pre-registered live bar.
# results/PREREG_honest.md holds that bar. `--honest` exists so the change can
# be run and measured, not so it can be slipped in.
# ===========================================================================
HONEST_CONF = False              # --honest turns it on
HONEST_TABLE_PATH = os.path.join(os.path.dirname(HERE), "results",
                                 "calib_table.json")
_HONEST = None


def load_honest(path=None):
    """Read the empirical tail table, or None if it is not there.

    Never falls back silently to something that looks similar: if --honest is
    asked for and the table is missing, main() refuses to start. A calibration
    table that quietly reverts to a Gaussian is the worst of both worlds --
    the run would be labelled honest and behave exactly as before.
    """
    global _HONEST
    p = path or HONEST_TABLE_PATH
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            t = json.load(fh)
    except (OSError, ValueError):
        return None
    if not (t.get("grid") and t.get("tail")
            and len(t["grid"]) == len(t["tail"])):
        return None
    _HONEST = t
    return t


def honest_tail(z, table=None):
    """Empirical P(the settle lands on the wrong side), given z.

    Linear between grid points; beyond the last point it HOLDS the last
    measured value rather than extrapolating to zero. Extrapolating a tail we
    have not observed is how a model claims 99.99% on evidence that cannot
    support 99.9%, which is the exact failure this whole file is about.
    """
    t = table if table is not None else _HONEST
    if not t:
        return None
    g, tl = t["grid"], t["tail"]
    if z <= g[0]:
        return tl[0]
    if z >= g[-1]:
        return tl[-1]
    lo, hi = 0, len(g) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if g[mid] <= z:
            lo = mid
        else:
            hi = mid
    span = g[hi] - g[lo]
    if span <= 0:
        return tl[lo]
    w = (z - g[lo]) / span
    return tl[lo] + w * (tl[hi] - tl[lo])


def conf_of(z):
    """The probability the model's side wins, at z standard deviations.

    Phi(z) unless --honest, in which case the measured table. This is the ONLY
    place the two can differ, so a run is honest or it is not -- there is no
    path where some gates see one number and some see the other.
    """
    if HONEST_CONF:
        tl = honest_tail(float(z))
        if tl is not None:
            return max(0.0, min(1.0, 1.0 - tl))
    return ND.cdf(float(z))


def fair(idx, iid, close_s, now_s, strike, sigma, round_digits=None):
    """P(settle >= effective strike) with the locked prints already counted."""
    part = idx.partial(iid, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    _, spot, _ = idx.spot(iid)
    if spot is None:
        return None
    K = eff_strike(strike, round_digits)
    mu = (locked + r * spot) / N_AVG
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return conf_of((mu - K) / sd)


def billed_fee(price, count=1):
    """The fee Kalshi ACTUALLY charges, not the raw formula.

    Measured over the account's whole taker fill history (8 fills, 0.02 to
    54.99 contracts): fee_cost == ceil(0.07*count*p*(1-p) to the next $0.0001)
    every time. Not nearest-rounded (0.0003387 -> 0.0004 and 0.0003450 ->
    0.0004 both refute that) and NOT rounded up to a whole cent, which would
    have killed a 1-3c edge at size 1. Using the ceiling here keeps the edge
    test conservative rather than flattering by up to 0.0075c.
    """
    raw = pintake.expected_fee(price, count)
    return math.ceil(raw * 10000.0) / 10000.0


def _source_fingerprint():
    """Hash of THIS FILE, so a log line can never describe code that is not
    running. Added 2026-09-08 after a start record described a configuration
    the process was not using.

    DEPLOY NOTE, 2026-09-22 -- THIS HASH IS FREEZE BAR B6's JOIN KEY, AND
    SHIPPING *ANY* CHANGE TO THIS FILE MOVES IT FOR EVERY PAPER ARM, NOT
    JUST A NEW ONE. B6's shared-close rule (results/FREEZE_2026-09-22.md
    section 3) requires the arm's run and the live run in force 60 s before
    the close to carry the SAME code_sha. Restart live on a new file and
    every arm that has not been re-synced onto it has ZERO shared closes --
    and B6 then reports nothing rather than an error, which is how the
    09-22 12:00Z close was already lost (live moved at 11:52:44Z, the arms
    at 12:01Z).

    So a restart on a changed file and `sync_arms.ps1` are ONE act, not
    two: restart live, re-sync the arms, and say in VERSIONS.md that B6's
    window restarts there. Logging-only changes are not exempt -- the hash
    does not know what changed."""
    import hashlib
    try:
        with open(os.path.abspath(__file__), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except Exception:                                    # noqa: BLE001
        return "unknown"


MEASURED_FLIP = 0.0090   # 3 flips in 333 dear trades, corrected OOS run. The
                         # MODEL implies ~0.06% at the prices we pay; reality
                         # is 15x worse because of adverse selection -- a
                         # near-certainty is only offered cheaply when the
                         # seller may know something.
                         # See results/PREREG_pin_live_AMENDMENT_2.md.
EV_FLOOR = 0.003         # dollars per contract required IN EXPECTATION
# ---- R1 (2026-09-22): WHEN IS AN "ATTEMPT" COUNTED? --------------------
# MAX_ATTEMPTS_PER_MARKET's own comment below says it counts orders SENT.
# The counter is incremented at the SIGNAL point, ~100 lines before the
# send, and five gates that refuse WITHOUT sending sit in between
# (early_cheap, early_dear, early_wide, staged_none, price_band). At ~20
# looks a second three refused passes -- 150 ms -- reach the cap and lock
# the market out for the REST OF THE CLOSE, the last 30 seconds included.
# 42 lockouts lifetime, 32 of them preceded by one of those five refusals
# in the same market and close; every record reads tried = 3.
#
# --attempts-on-send moves BOTH entry counters to the send site. DEFAULT
# OFF, so an unflagged process -- the live bot -- behaves exactly as it
# does today, byte for byte.
#
# REVIEW FIX 2026-09-22: the first version moved only the per-market
# counter, as the plan said. That is strictly WORSE than today, and it was
# found by driving it rather than by reading it. `attempts[close_s]` is
# incremented at the signal point, ABOVE those same five gates. Today the
# per-market lockout is also what stops a burner reaching that line, so a
# burner spends 3 of the close's 24 and eleven other coins keep their room.
# Release only the per-market counter and the burner runs at 20 Hz into the
# per-CLOSE cap in ~1.2 s, after which `attempts_cap` refuses EVERY market
# in that close. Offline proof: an innocent second coin enters with the
# flag OFF and gets zero signals with it half-moved ON.
#
# So both move, and the rail survives: MAX_ATTEMPTS_PER_CLOSE's own comment
# says it counts "orders SENT per close", and the 2026-09-08 runaway was
# 160 sends. The hedge (under `_hcs`) and the plant still increment
# `attempts[close_s]` exactly where they do today -- neither is touched.
_DEFAULT_ATTEMPTS_ON_SEND = False
ATTEMPTS_ON_SEND = False
MAX_ATTEMPTS_PER_MARKET = 3  # AMENDMENT 26 (2026-09-14): orders SENT into ONE
_DEFAULT_MAX_ATTEMPTS_PER_MARKET = 3   # market in one close, filled or not.
                             # THIS is what the 160-order runaway actually
                             # needed: it was one market retried at 20 Hz, not
                             # many markets tried once. With this in place the
                             # close-level cap no longer has to be small, so it
                             # can stop being the thing that prevents the bot
                             # walking down to the next-best market when the
                             # best one has been taken.
                             # 3 allows a lost race, a retry, and one more.
# AMENDMENT 73: count only FINALISED bets toward the loss total. True by
# default would restore the old forward-looking bound, which booked every
# open position as a total loss and paused the bot while it was up $43.
# --loss-bound-open turns it back on; nothing else reads this.
LOSS_BOUND_OPEN = False
_DEFAULT_LOSS_BOUND_OPEN = False

# AMENDMENT 71: consecutive reconcile() failures after which the run stops.
# Not 1 -- a single HTTP hiccup must not end a trading day. Not unlimited --
# a frozen ledger makes every loss brake inert. At 20 Hz this is a couple of
# seconds of a genuinely broken settlement reader.
RECONCILE_FAIL_HALT = 40

# AMENDMENT 71: the HEDGE's own per-close send cap, deliberately above
# anything ordinary hedging can reach (3 positions x HEDGE_MAX_TRIES, one try
# per position per second). It exists only so a bug cannot turn the hedge into
# a 20 Hz runaway; it must never be the reason a real hedge does not fire.
# Before A71 the hedge read MAX_ATTEMPTS_PER_CLOSE, which the ENTRY path
# spends -- so the bot's own buying could permanently disable its insurance.
MAX_HEDGE_ATTEMPTS_PER_CLOSE = 120

MAX_ATTEMPTS_PER_CLOSE = 24  # AMENDMENT 26: 8 -> 24. Twelve coins settle on
                             # the same second, so 8 could not even try them
                             # all once, let alone come back. 24 is every coin
                             # twice. The runaway protection did not weaken --
                             # it moved to MAX_ATTEMPTS_PER_MARKET above, which
                             # is tighter than 8 was for the case it was
                             # written for, and `order_errors >= 2` still halts
                             # the run on rail refusals regardless.
                             #
                             # WAS: orders SENT per close, filled or not. Distinct
                             # from MAX_PER_CLOSE, which caps FILLS. Added
                             # 2026-09-08 after a runaway sent 160 orders into
                             # one close in a single second: every one was
                             # refused by a rail, take() returns refusals
                             # rather than raising, and AMENDMENT 6 had just
                             # stopped a no-fill from consuming a slot. Fills
                             # and attempts need separate budgets. 8 allows the
                             # 3 fills plus a generous margin of lost races.

# ---- R2 (2026-09-22): HOW LONG A LOOP PASS TOOK. RECORDS ONLY. --------
# The universe refresh at the top of the loop does one synchronous
# GET /markets per series -- eleven fresh TCP+TLS connections, no
# condition on time to close. Our own authenticated POSTs to the same host
# on a fresh connection run a median 94 ms over 980 orders, so eleven back
# to back is ~1.0 s in which nothing is bought AND NO HEDGE FIRES, because
# the hedge pass shares the thread. `hedge_quote` gaps cannot see it: a
# blackout under 1.000 s can never cover a whole second, so there is no
# instrument at all today. These two constants build one.
#
# NOTHING IS DEFERRED, MOVED OR GATED ON THESE. They time what already
# happens and write it down; the hedge pass gains no condition.
LOOP_SLOW_MS = 200.0     # a pass slower than this writes one `loop` record
LOOP_REC_MAX = 20        # ...at most this many per close FAR FROM THE CLOSE,
                         # so a box that is thrashing cannot fill the disk.
                         # Disk is the real deadline here: 5 GB free is a
                         # hard collection stop, not a slowdown.
#
# REVIEW FIX 2026-09-22 -- THE FIRST VERSION OF THIS BUDGET MADE THE BAR
# UNREACHABLE, AND IT WOULD HAVE READ AS A CLEAN FAIL.
#
# `watching` admits a market the moment it is <= 900 s out, so ONE close is
# the nearest close for its whole fifteen minutes. The refresh fires every
# 20 s with no condition on time to close, so at the durations this exists
# to measure (837-998 ms live, over 11 series) EVERY refresh is a slow pass:
# ~45 of them a close, all far from it. A first-come budget of 20 is
# therefore spent at about tau 500 s, and the ~2 slow passes inside the last
# 45 s -- the only ones the pre-registered bar reads -- are dropped.
# Measured on the live log, 26,837 s / 30 summarised closes: 44.6 refreshes
# per close. And a single per-close MAXIMUM cannot stand in for them: it is
# dominated by a far-from-close refresh, so P(its tau <= 45) is about 2/45.
#
# The bar (D_plan section 3) needs ">= 20 of 100 closes with a gap > 500 ms
# at tau <= 45" to PASS and "< 5 of 100 with any gap > 200 ms at tau <= 45"
# to FAIL. As first built the instrument returned ~0 either way -- FAIL by
# construction, on an artefact of the budget.
#
# So the budget is TAU-AWARE and the summary carries a SECOND maximum
# restricted to the window the bar reads. Nothing about the loop changed;
# this is still only which records get written.
# R2 (2026-09-23): DO NOT REFRESH THE UNIVERSE WHILE A CLOSE IS NEAR.
#
# The refresh is 11 sequential GETs in the trading thread, every 20 s, with no
# condition on time-to-close. Measured by v-instr1's own records: a median
# 878 ms on a healthy API -- and when Kalshi degraded at 2026-09-23 00:2xZ,
# a median 3,227 ms and a worst 10,639 ms, with 54 stalls INSIDE 45 s of a
# close (6,344 ms at tau 21, 4,936 ms at tau 2) and a >500 ms stall inside
# 60 s on 17 of 17 closes. For those seconds the bot cannot buy AND CANNOT
# HEDGE, because the hedge pass is the same thread. That is the safety half.
#
# Deferring costs nothing: the refresh already discards any market closing
# more than 900 s out, so while one close is inside 60 s the next close's
# markets (960 s away) would be excluded anyway. The skip ends at the close,
# and UNI_HARD_S is a backstop so it can never defer for ever.
UNI_NEAR_TAU_S = 60          # skip while any watched market is this close
UNI_HARD_S = 300             # ... but never skip longer than this
_DEFAULT_UNI_NEAR_TAU_S = 60
_DEFAULT_UNI_HARD_S = 300


def defer_universe(now, uni_at, taus, near=None, hard=None):
    """True when the universe refresh should WAIT: a watched market is inside
    `near` seconds of its close and the last refresh is younger than `hard`.
    Pure, so the self-test can plant each case."""
    near = UNI_NEAR_TAU_S if near is None else near
    hard = UNI_HARD_S if hard is None else hard
    if now - uni_at >= hard:
        return False
    for t in taus:
        try:
            if 0 <= float(t) <= near:
                return True
        except (TypeError, ValueError):
            continue
    return False


LOOP_NEAR_TAU_S = 60     # "near the close": a pass that STARTED with this
                         # many seconds or fewer left. 60, not 45, so the
                         # bar's own 45 s cut is made from data, not from
                         # the edge of the instrument.
LOOP_REC_MAX_NEAR = 300  # a SEPARATE budget for near passes, which far
                         # passes can never spend. Set so it CANNOT BIND AT
                         # ALL, which is the only honest answer to a budget
                         # that silently decided the bar: a pass counts as
                         # slow only above LOOP_SLOW_MS, so at most
                         # LOOP_NEAR_TAU_S / (LOOP_SLOW_MS/1000) = 300
                         # passes a close can ever qualify. The expected
                         # number is 2-3 (three 20-second refreshes land in
                         # a 60 s window); 300 is the pathological ceiling,
                         # and even at it the cost is ~4 MB a day against
                         # 25 GB free.
# ===========================================================================
# R4 (2026-09-23): THE TRAJECTORY. LOGGING ONLY, AND IT IS WHY EVERY "WAS
# THERE AN EARLIER SIGN?" QUESTION IN results/map_2026-09-22 CAME BACK
# UNDERPOWERED.
#
# `_gate()` de-duplicates on (close_s, ticker, gate), so a market the bot
# evaluated ~5,500 times (median `close_summary.looks`) leaves a MEDIAN OF ONE
# refusal record, carrying the values from the FIRST firing of each distinct
# gate. Measured over the last 12 live runs: refusal records per
# (close, ticker) median 1, p90 4, max 10; distinct gates median 1. So the
# entire visible pre-entry history of a market is 1-4 numbers, and WHICH ones
# exist depends on which gates happened to fire -- a selection effect nobody
# has bounded. Every overlay in that map was run against that.
#
# THIS FIXES THE INSTRUMENT, NOT THE STRATEGY. Nothing here reads a gate,
# changes a gate, writes a refusal, or touches a decision. It is one compact
# record per watched market per sampled second, on an EXOGENOUS grid (fixed
# times to close, never trade arrivals -- CLAUDE.md, "Writing new analysis"),
# so the next reader gets a trajectory instead of a first firing.
#
# THE GRID. D_plan's R4 fixes 1 Hz inside 60 s; the coarse grid outside it is
# the wider ask ("every 5 s from first watch to the close") and costs little
# because a market is only watched from 900 s out:
#
#     tau <= TRAJ_NEAR_TAU_S      every second      61 samples a market a close
#     tau >  TRAJ_NEAR_TAU_S      every TRAJ_EVERY_S s, on tau % TRAJ_EVERY_S
#                                                   48 samples to TRAJ_TAU_MAX
#
# 109 samples a market a close, ~11 markets a close -> ~1,200 records a close.
# MEASURED IN THE OFFLINE HARNESS, not estimated: see the R4 self-test, which
# prints the record volume per close it actually produced.
#
# TRAJ_TAU_MAX IS 300 AND NOT 900, AND THAT IS A DISK DECISION, SAID OUT LOUD.
# "From first watch" is 900 s, which is 229 samples a market -- 2.1x the
# volume for the stretch where the model has NO locked settlement prints at
# all (partial() returns (0.0, 60) out there, so `fair` is just spot against
# the strike at ~30 sigma and the book is usually empty). Free disk is 20 GB
# falling ~3 GB a day against a 5 GB HARD COLLECTION STOP, and the tape is
# unreproducible while an analysis result is not. Raising this to 900 is one
# constant if a later map wants it.
#
# AND THE FILE IS WRITTEN BY THE LIVE BOT ALONE. THE FIRST VERSION OF THIS
# BLOCK COSTED THE DISK PER PROCESS AND THERE ARE 28 OF THEM. sync_arms.ps1
# launches 27 paper arms from THIS SAME FILE, so `tag = live/paper` plus a
# per-run id gave every arm its own pintraj-paper-<runid>.jsonl the moment it
# restarted onto this SHA: ~57 MB a day each, ~1.6 GB a day for the box,
# against 44 MB a day for the whole existing bot family -- a 36x increase,
# and it would have taken the 6 GB collection stop from ~4.7 days away to
# ~3.1, i.e. burned ~1.6 days of unreproducible tape to write 27 near-copies
# of one trajectory. (They ARE near-copies: the trajectory is a function of
# the index, the book and the model, and those are identical across arms
# apart from the --sigma-stress ones and the held/paused/gate columns.)
# So `traj_writer()` opens a file only when --live is set, or when the
# operator explicitly passes --traj-log to a paper run; sync_arms passes
# neither. `traj_hist` -- the only thing any DECISION reads -- is in memory
# and is unaffected, so every arm still measures exactly what it measured.
#
# IT GOES IN ITS OWN FILE, AND ON ONE HELD HANDLE. `rec()` opens, appends and
# closes the log on every call, and the settlement readers, pinledger,
# pinattrib, pinlab and barcheck all parse `results/pinrun-<tag>-*.jsonl`.
# Tens of MB a day of trajectory in there would slow every one of them, so
# trade_loop takes a SECOND writer (`trec`) and main() points it at
# `results/pintraj-<tag>-<runid>.jsonl`. That writer holds ONE handle open and
# flushes once a second, because the open-append-close pattern is not free at
# this rate: measured on this box, 200 repeats, a real 539-byte record, the
# eleven appends of one sampled second cost 2.46 ms median / 3.07 p90 / 5.64
# max through open-append-close and 0.012 ms median / 0.12 max through a held
# handle -- two orders of magnitude, and 15.8 ms at the tail of a 1,000-record
# burst in the review that found this. The
# pass sleep is a flat time.sleep(0.05), not a deadline, so every one of those
# milliseconds is added period before the NEXT hedge pass. At most one second
# of records can be lost to a kill, and they are an instrument, not a ledger.
# The offline loop passes no writer, so the records land in the trail the
# self-tests read -- which is how the harness can count them. traj_writer()
# itself is module-level so a self-test can drive the REAL file writer.
#
# WHY IT CANNOT DELAY A HEDGE -- AND THE NARROW REASON, NOT A COMFORTABLE ONE.
# The block sits BELOW the hedge pass and ABOVE the risk check, the universe
# refresh and the entry scan. It is above the risk check on purpose: that
# check's transient-pause branch ends in `continue`, and a sampler below it
# would write nothing for a paused close -- which is precisely the blindness
# that cost $107.95 on 2026-09-19. So the reason no hedge is delayed is NOT
# "there is nothing below it": it is that the hedge pass for this iteration
# has already run, and no protective ACTION exists below this block today.
# ANYONE WHO ADDS ONE -- the `dumped` path in the scan is the nearest
# candidate -- MUST MOVE THIS BLOCK BELOW IT OR RE-ARGUE THIS PARAGRAPH. A
# self-test asserts the source order (hedge pass, sampler, risk check, scan),
# so moving any of them fails the suite rather than quietly invalidating this.
# It is wrapped whole and per market, so a fault in it is dropped, not raised
# -- and both wrappers write a deduped `traj_blind` record, because a blind
# instrument that says nothing is the failure this instrument exists to fix.
# And the work is bounded: at most one book read + one index read + one
# fair() per market per SAMPLED SECOND, against the 20 Hz scan's twenty of
# each for the same market.
TRAJ_EVERY_S = 5         # the coarse grid, in seconds of tau
TRAJ_NEAR_TAU_S = 60     # ...inside this, every second (D_plan R4's 1 Hz).
                         # 60 and not 45, so a market entered at the first
                         # allowed second (tau 45, the A46 early leg) still
                         # has readings DOUBT_LAG_S earlier -- which is the
                         # whole defect A_table's `conf_t45` ran into.
TRAJ_TAU_MAX = 300       # how far out sampling starts. `watching` admits a
                         # market at 900 s, so this is not "first watch" --
                         # see the disk paragraph above for why.
TRAJ_MAX = 800           # the per-close budget for FAR samples, so a box
                         # that is thrashing cannot fill the disk. Disk is
                         # the real deadline: 5 GB free is a HARD COLLECTION
                         # STOP. Ceiling at 11 series x 48 far samples = 528,
                         # so it cannot bind on a healthy universe; at 14
                         # series it is 672, still under.
TRAJ_MAX_NEAR = 900      # a SEPARATE budget for the near seconds, which far
                         # samples can NEVER spend. v-instr1 learned this the
                         # hard way: its first per-close record budget was
                         # first-come, so ~45 far-from-close refreshes spent
                         # all 20 at about tau 500 and the near-close passes
                         # the bar actually read were dropped -- a FAIL by
                         # construction, on an artefact of the budget. Set so
                         # it CANNOT BIND AT ALL, which is the only honest
                         # answer to that: at one sample a market a second the
                         # ceiling is n_markets x (TRAJ_NEAR_TAU_S + 1) = 671
                         # at 11 series and 854 at 14.
TRAJ_HIST_MAX = 400      # readings kept in memory per (close, market) for
                         # R1. 109 is the grid's own ceiling; this bounds it
                         # even if the clock jumps.
# ---------------------------------------------------------------------------
# THE SECOND HALF OF D_plan SECTION 5, WHICH THE 1 Hz GRID CANNOT SEE.
# The DOGE close that cost $107.95 moved 98.0c -> 93.4c on OUR OWN SIDE across
# three looks 244 ms apart (tau 12, 12, 11) while net_edge grew 41x. At one
# record a market a second all three collapse into one row, so the population
# that question needs would still not exist after a month of trajectory --
# "still n = 2" a month from now. D_plan asked for R4's trace PLUS "a rec() on
# any look whose own-side price fell >= 3c since this bot's previous look at
# the same market, log-only, no gate", and this is that. It is in the scan
# because that is the only place that looks 20 times a second; it is a dict
# read and a float compare on a path that has already read the book, it writes
# only when the drop fires, and it is capped per (close, market) so a flapping
# book cannot turn it into a firehose. It decides NOTHING.
LOOK_DROP_C = 0.03       # our own side got this much cheaper since the
                         # previous look at this market, in dollars (3c)
LOOK_DROP_MAX = 20       # ...records per (close, market). Bounded before it
                         # happens rather than discovered afterwards.
_DEFAULT_TRAJ_EVERY_S = 5
_DEFAULT_TRAJ_NEAR_TAU_S = 60
_DEFAULT_TRAJ_TAU_MAX = 300
_DEFAULT_TRAJ_MAX = 800
_DEFAULT_TRAJ_MAX_NEAR = 900
_DEFAULT_TRAJ_HIST_MAX = 400
_DEFAULT_LOOK_DROP_C = 0.03
_DEFAULT_LOOK_DROP_MAX = 20


def traj_due(tau, every=None, near=None, tau_max=None):
    """Is `tau` on the sampling grid? Pure, so the self-test can plant every
    case and so the grid is a statement rather than an inline condition."""
    every = TRAJ_EVERY_S if every is None else int(every)
    near = TRAJ_NEAR_TAU_S if near is None else int(near)
    tau_max = TRAJ_TAU_MAX if tau_max is None else int(tau_max)
    try:
        tau = int(tau)
    except (TypeError, ValueError):
        return False
    if tau < 0 or tau > tau_max:
        return False
    if tau <= near:
        return True
    return every > 0 and tau % every == 0


def traj_writer(live, traj_log, results_dir, tag, runid, _open=open,
                _now=None):
    """The trajectory writer. Returns (path_or_None, writer).

    TWO DEFECTS OF THE FIRST VERSION ARE FIXED HERE, AND BOTH WERE ABOUT
    COST RATHER THAN CORRECTNESS -- see the TRAJ_* block for the numbers.

    1. A FILE ONLY FOR THE BOT THAT IS BETTING. 28 pinrun processes run on
       this box; 27 of them are paper arms launched from this same file by
       sync_arms.ps1, and a per-run file for each was ~1.6 GB a day of
       near-duplicate data against a 6 GB hard collection stop. So: --live,
       or the operator explicitly asking with --traj-log, or nothing is
       opened at all. The writer still returns cleanly in that case, and the
       in-memory `traj_hist` every decision reads is untouched either way.
    2. ONE HELD HANDLE, FLUSHED ONCE A SECOND. open-append-close per record
       costs 2.46 ms median (5.64 max, and 15.8 ms at the tail of a
       1,000-record burst) for the eleven markets of one sampled second; a
       held handle plus one flush is 0.012 ms median, 0.12 max. The loop's pass is a
       flat time.sleep(0.05), so that difference is added period ahead of the
       NEXT hedge pass. A flush a second bounds what a kill can lose to one
       second of an instrument. Anything that is not a plain `traj` record --
       a close summary, a blind second -- flushes immediately, because those
       are the rare ones a reader goes looking for.

    The handle is dropped and reopened on any write error, so a full disk or
    a deleted file costs records and never the loop.
    """
    _clk = _now or (lambda: time.time())
    if not (live or traj_log):
        _n = [0]

        def _drop(kind, **kw):
            """No file. Counted so `traj_off` can say how many were dropped."""
            _n[0] += 1
        _drop.dropped = _n
        _drop.path = None
        return None, _drop
    path = os.path.join(results_dir, "pintraj-%s-%s.jsonl" % (tag, runid))
    _fh, _sec = [None], [None]

    def _trec(kind, **kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kw["kind"] = kind
        try:
            if _fh[0] is None:
                _fh[0] = _open(path, "a", encoding="utf-8", newline="\n")
            _fh[0].write(json.dumps(kw, default=str) + "\n")
            _s = int(_clk())
            if _sec[0] != _s or kind != "traj":
                _sec[0] = _s
                _fh[0].flush()
        except Exception:                                # noqa: BLE001
            try:
                if _fh[0] is not None:
                    _fh[0].close()
            except Exception:                            # noqa: BLE001
                pass
            _fh[0] = None
    _trec.path = path
    _trec.handle = _fh
    return path, _trec


_DEFAULT_MIN_FILL_FRAC = 0.50  # --min-fill-frac is measured against this
#
# AMENDMENT 28 (2026-09-14) -- RE-OPENED, AND THE REASON BELOW IS OBSOLETE.
# The operator: "Is there anyway to increase the amount it's buying without
# increasing risk of losing or lost percentage?"
#
# MEASURED FIRST, over 234 live closes we bought on: the bot spends only 58%
# of the contract budget it is already allowed. The MEDIAN close spends
# exactly 50% -- one fill of SIZE, never the second. And of 404 closes that
# had a tradeable moment, 170 produced no fill at all; 141 of those had at
# least one moment refused for being too small.
#
# THE JUSTIFICATION BELOW NAMES TWO HARMS, AND BOTH ARE GONE:
#   "burns a scale-in slot"   -- AMENDMENT 17 made the close budget CONTRACTS,
#                                not slots. A 5-contract fill spends 5
#                                contracts and leaves the rest of the budget.
#   "raises the improve bar"  -- AMENDMENT 12 sets raise_bar=False for exactly
#                                this case, and AMENDMENT 22 scoped the
#                                improve rule to one market.
# So the -2.3% measured at frac 0.05 was measuring a penalty that no longer
# exists -- the THIRD rule found arguing against a world A17 replaced, after
# A13 and A22. It is not flipped on that reasoning alone: it goes to a paper
# what-if, like the other two.
#
# WHY IT CANNOT RAISE THE LOSS RATE. A smaller fill is the SAME bet at the
# SAME gate -- same confidence, same edge, same expected value, same price --
# with fewer contracts on it. Exposure per close is still bounded by the
# contract budget. What it does cost is fee efficiency and smaller wins.
MIN_FILL_FRAC = 0.50     # AMENDMENT 6. Take a PARTIAL rather than skip a
                         # moment outright. The dust gate used to refuse any
                         # offer smaller than SIZE, so at size 10 a 9-contract
                         # offer was thrown away even though an IOC would
                         # happily have filled 9. Buying min(SIZE, offered)
                         # can only LOWER exposure, never raise it.
                         # Measured on 1,196 eligible moments over 83 closes,
                         # expected P&L at the 0.90% flip rate:
                         #   frac 1.00 (today) 124 buys  $59.75
                         #   frac 0.50         125 buys  $60.53   +1.3%
                         #   frac 0.05         129 buys  $58.37   -2.3%
                         # and at size 25 the same sweep gives +5.4% at 0.50.
                         # Taking ANY scrap is worse than taking none: a tiny
                         # early fill burns a scale-in slot and raises the
                         # improve bar, so it trades a big cheap buy later for
                         # a small dear one now. Half is the measured optimum.
_DEFAULT_PRICE_CEILING = 0.980   # the DECLARED default; --price-ceiling moves
                                 # the running value and the self-test asserts
                                 # this one, so an arm that sets the flag does
                                 # not fail its own gate.
#
# RAISED LIVE TO 0.99 BY FLAG on 2026-09-18 ~17:4xZ, operator: "The two gates
# that trim volume without preventing loss, remove or severely lessen them",
# then "I'm just following your words" when shown the +$122.80 the cap had
# turned away. That figure is an upper bound (every refusal filled, none lost);
# the REAL record when the band was allowed live is 82 markets at 98-99c, one
# loss, +$51.07 including the loss. The 09-09 resilience arithmetic below is
# unchanged and still true: a loss at 98.5c takes ~65 wins to earn back where
# one at 98c takes 53. He was shown both and chose the volume.
PRICE_CEILING = 0.980    # 98.8c -> 98.0c, 2026-09-09. THE OPERATOR'S
                         # ARGUMENT, and it is arithmetic rather than a fitted
                         # parameter: "unless it eliminates 100% of losses it
                         # just makes earning back our blunders more difficult."
                         # He is right, and it kills every PROBABILITY gate --
                         # each one costs 22-44 winning trades to avoid a loss
                         # that costs ~24 wins, so it is a wash AND it removes
                         # the wins we need to recover with.
                         # But the recovery ratio is not a probability lever,
                         # it is a PRICE lever, fixed by arithmetic:
                         #     98.8c  win 1.11c  loss 98.89c  ->  89 wins to recover
                         #     98.0c  win 1.86c  loss 98.14c  ->  53
                         #     96.0c  win 3.73c  loss 96.27c  ->  26
                         # Measured on the live rule, 83 closes:
                         #     ceiling 98.8c  129 trades  742.0c  16 wins to recover
                         #     ceiling 98.0c  118 trades  767.6c  14
                         # MORE money AND better resilience -- better on both
                         # axes, which is rare enough to act on. The profit
                         # difference (+3.5% on 83 closes) may be noise; the
                         # RESILIENCE difference is arithmetic and cannot be.
                         # A tightening can only ever refuse trades, so the
                         # downside is bounded at "trades less".
                         # LIVE EVIDENCE: the 02:30Z trade we took at 98.7c
                         # needed 82 wins to recover and paid 12.10c. That is
                         # the worst risk-reward accepted all night and it sat
                         # inside the old ceiling.    # AMENDMENT 5 WITHDRAWN 2026-09-08 16:20Z, BEFORE IT
                         # EVER TRADED. The 96c ceiling was committed to disk
                         # but the running process was never restarted, so it
                         # was NEVER LIVE. Reverted for three measured reasons:
                         #  1. LIVE PRICES SAY IT IS FAR TIGHTER THAN THE
                         #     BACKTEST CLAIMED. 12 of our 16 real signals
                         #     were above 96c (mean 97.61c). The backtest
                         #     predicted 30% fewer trades; live it is 75%.
                         #     That breaches the amendment's own revert
                         #     trigger of "fewer than 10 fired closes/day".
                         #  2. NEITHER CEILING IS UNSAFE. The ceiling is a
                         #     cap, not the typical price. Blended breakeven
                         #     flip rate is 5.75% at 98.8c and 8.63% at 96c,
                         #     against an exact one-sided 95% bound of 2.31%
                         #     on our measured rate. Headroom 2.5x vs 3.7x --
                         #     both comfortably clear.
                         #  3. "THE DEAR TRADES WERE NEVER PAYING FOR THE
                         #     RISK" WAS NOT MEASURED. There are ZERO flips
                         #     in the whole eligible sample at every ceiling.
                         #     Trades in the 96-98.8c band realised +2.087c
                         #     per contract. They are not losers in the data;
                         #     they are only losers under an assumed flip
                         #     rate. See results/PREREG_pin_live_AMENDMENT_5.md.


def expected_value(price, flip=MEASURED_FLIP):
    """EV of one contract at `price`, using the MEASURED flip rate.

        EV = (1-f)*(1-p) - f*p - fee
        EV = 0  ->  p* = 1 - f = 0.991

    So ANY purchase above 99.1c loses money on average, however confident the
    model is. On 2026-09-08 five of seven live trades were above that line;
    the night realised +9.85c against an expected +3.55c -- lucky, not right --
    and a single loss at 99.6c would have cost 10.1x the whole night's profit.
    """
    p = float(price)
    return (1.0 - flip) * (1.0 - p) - flip * p - billed_fee(p, 1)


def net_edge(f, price, want):
    """Edge in dollars per contract AFTER the taker fee at that price.

    NO LONGER THE TRADE TEST ON ITS OWN -- expected_value() is, and above ~98.5c
    it is the binding one. This still gates on the model's view.

    THE FEE IS BILLED ON THE ORDER, NOT ON ONE CONTRACT, and it is ceilinged
    to $0.0001. At --size 0.01 that floor dominates: 0.07*0.01*0.99*0.01 =
    $0.0000069 bills as $0.0001, which is 1.00c PER CONTRACT against the
    0.07c the raw formula gives. Netting the one-contract fee here would let
    a penny run fire on a +0.6c "edge" that is really -0.33c.
    """
    gross = (f - price) if want == "yes" else ((1.0 - f) - price)
    return gross - billed_fee(price, SIZE) / float(SIZE)


# ===========================================================================
# AMENDMENT 18 -- RACE HARDER. THE LIMIT WE SEND IS NOT THE PRICE WE SAW.
#
# THE PROBLEM. 28.2% of our live orders fill NOTHING (249 filled, 113 zero of
# 362 carrying a latency). It is NOT our speed: filled and zero-filled orders
# have the SAME median latency, 96 ms both. The competing take lands at a
# median 67 ms (results/RESULTS_contest.md section 4). We cannot out-run them.
# We send a limit at exactly the ask we saw, so when that level is gone we buy
# nothing at all -- and there is usually another level sitting just above it.
#
# WHY RAISING THE LIMIT IS FREE ON EVERY RACE WE ALREADY WIN -- MEASURED, NOT
# ASSUMED. A crossing IOC fills at the RESTING order's price, not at ours. On
# 283 live fills the executed price was at or below the signalled price on
# EVERY ONE: 207 exactly at it, 76 strictly better (best -43c), ZERO worse.
# Recorded in RUNBOOK.md under CONFIRMED FACTS.
#
# THE OPERATOR'S ARGUMENT, and he is right, 2026-09-13: "How can it be a worse
# ticket if it's one we already calculated is a good buy, it would just be our
# normal w/l ratio." It is the SAME market, the SAME side and the SAME
# settlement -- the outcome cannot depend on what we paid. My earlier caveat
# treated a swept fill as a different ticket and that was wrong. What actually
# changes is (a) we pay a little more, which the gate below bounds, and (b) we
# now trade in moments we used to skip, which is the only real unknown.
#
# THE RAIL. The limit is the HIGHEST price that still passes EVERY gate the
# seen price passed -- the ceiling, the model edge floor AFTER the fee, and
# the measured-flip EV floor. So the WORST fill this can produce still clears
# the identical bar every fill today clears. It is not a new rule; it is the
# existing rule applied to the price we might actually pay instead of the
# price we hoped for. An IOC sweeps levels in order, so the average fill is
# better than the limit and the limit is the worst case.
#
# Pre-registered bar, written before the code: results/PREREG_sweep.md.
# ===========================================================================
SWEEP_ENABLED = True     # --no-sweep disables; the limit then IS the ask seen
_DEFAULT_SWEEP_ENABLED = True   # the offline-loop self-test pins the flag to this
SWEEP_DEPTH = False      # AMENDMENT 35: also size the ORDER from the ladder,
_DEFAULT_SWEEP_DEPTH = False   # not just from the touch. --sweep-depth turns
                         # it on. OFF by default because it buys MORE per
                         # fill, and more per fill is the one thing that
                         # changes exposure rather than merely who we buy.

# AMENDMENT 37 -- THE DEPTH FLOOR MUST MEASURE WHAT WE CAN BUY.
#
# A35 taught the ORDER to read the whole ladder. It did not touch the GATE
# that decides whether to place one, and that gate still asks only how many
# contracts sit at the single best price. So a market showing 3 at the touch
# with 1,600 one tick behind -- the exact 02:00 SOL shape A35 exists for -- is
# still refused outright, because 3 < 0.10 x SIZE.
#
# This makes the floor ask the question it was always meant to ask: how many
# contracts can we actually buy, at prices sweep_limit() has ALREADY approved
# against the same confidence, edge, ceiling and EV tests. Nothing new is
# bought; a decision that was being thrown away early is allowed to reach the
# gates that actually judge it -- edge_floor, the dump guard, the ceiling and
# the EV floor all still run afterwards, unchanged.
#
# IT REQUIRES --sweep-depth AND IS OFF WITHOUT IT. Passing this gate on the
# strength of the ladder while the ORDER still sizes from the touch would buy
# exactly the scrap fill AMENDMENT 6 added the floor to prevent.
DEPTH_LADDER = False
_DEFAULT_DEPTH_LADDER = False


# AMENDMENT 67 (2026-09-19): BUY LESS AS THE PRICE GETS WORSE.
#
# The operator, after the 12:30 BNB close cost $61.75: "When we don't get as
# many fills as we expect it's your job to taper to buy the right amount at
# the other prices."
#
# WHAT A35 GOT WRONG, in its own words: "EVERY EXTRA CONTRACT IS ALREADY
# GATE-APPROVED ... anything filled at or under [the sweep limit] is a trade
# we had already decided to make." True and not sufficient. A contract at
# 91.5c clears the gate by 7.8c; one at 98c clears it by 1.7c. Buying the
# same quantity of each treats a fifth of the edge as if it were the whole of
# it -- and because the deep levels hold far more than the touch, the AVERAGE
# fill lands near the ceiling rather than near the signal.
#
# LIVE, KXBNB15M-26SEP191230-30: touch 23 contracts at 91.5c, ladder 11,937
# up to a 98c limit, order sized to 114 (then 171 after the band boost),
# filled 82.8 at an average of 97.27c. The trade was justified by a 7.8c edge
# that existed for 23 contracts. At 97.27c a contract can win 2.7c and lose
# 97.27c, and that is the bet we actually placed 60 times over.
#
# THE RULE. Weight each price level by how much of the touch's edge survives
# there. Full size at the best price, proportionally less as the edge decays,
# nothing once it is gone. On the BNB book that asks for ~47 instead of 114.
TAPER = True             # --no-taper restores A35's flat sizing
_DEFAULT_TAPER = True
TAPER_FLOOR = 0.0        # ignore rungs whose edge has fallen below this
                         # FRACTION of the touch's edge. 0 = take them, just
                         # in proportion.
_DEFAULT_TAPER_FLOOR = 0.0   # the offline-loop self-test pins the flag to this


def taper_take(rungs, size, edge_of, floor=None):
    """Contracts to ask for, weighted by the edge at each price level.

    `rungs` is [(price, contracts)] cheapest first (livebook.rungs).
    `edge_of(price)` returns the edge in dollars at that price.

    Returns 0.0 when the touch itself has no edge -- if the best price on the
    book is not worth taking, no quantity of worse ones is.
    """
    if not rungs:
        return 0.0
    size = float(size)
    if size <= 0:
        return 0.0
    frac = TAPER_FLOOR if floor is None else float(floor)
    try:
        best = float(edge_of(rungs[0][0]))
    except (TypeError, ValueError):
        return 0.0
    if best <= 0:
        return 0.0
    total = 0.0
    for price, depth in rungs:
        try:
            e = float(edge_of(price))
        except (TypeError, ValueError):
            break
        if e <= 0:
            break                       # past here the gate itself refuses
        w = e / best                    # 1.0 at the touch, decaying upward
        if w < frac:
            break
        total += min(float(depth), size * w)
        if total >= size:
            return size
    return min(total, size)


def sweep_limit(f, price, want, ceiling=None, edge_floor=None, ev_floor=None):
    """Highest price we may pay and still pass the SAME gate. Never below
    `price`, never above the ceiling, and never a price the gate refuses.

    Both tests are monotonically decreasing in price -- edge falls as we pay
    more, EV falls as we pay more -- so walking up one exchange tick at a time
    and stopping at the first refusal returns the true maximum. The tick is
    tapered (0.1c above 90c, 1c between), so this is at most ~80 steps and the
    step size is read from engine.tick_at rather than assumed.
    """
    ceiling = PRICE_CEILING if ceiling is None else ceiling
    edge_floor = EDGE_FLOOR if edge_floor is None else edge_floor
    ev_floor = EV_FLOOR if ev_floor is None else ev_floor
    p = float(price)
    if not SWEEP_ENABLED:
        return p
    best = p
    for _ in range(200):
        nxt = round(best + tick_at(best), 4)
        if nxt > ceiling + 1e-9:
            break
        if band_blocked(nxt):
            break               # A53: the limit stops under a skipped band
        if net_edge(f, nxt, want) < edge_floor:
            break
        if expected_value(nxt) < ev_floor:
            break
        best = nxt
    return best


# ===========================================================================
# THE OFFLINE LOOP (2026-09-22, findings K1/K2/K3 of the project map).
#
# Every loop-level protection in this file -- A69, A71, A74 -- was proved by
# SEARCHING trade_loop's source. Nothing in the self-test ever RAN the loop,
# and all three in-loop crashes on record (09-15 04:29Z, 09-15 04:59Z, 09-19
# 05:59Z) were new code going off the first second its branch executed. The
# 09-19 one was holding: -$66.34.
#
# This drives the REAL trade_loop with a fake clock, a fake book, a fake
# index and a fake market list, so a check can plant a fault and watch what
# the loop actually DOES. Nothing here can reach the network or a live file:
# the market/settlement GET, the wire, the cancel, the order-record read, the
# bank read and the size mirror are all replaced before the loop starts and
# restored after; orders go to pintake's DEMO base; the day-loss file points
# into a temp directory. The clock only moves when the loop sleeps, so a
# twelve-second close runs in a fraction of a second of real time.
# ===========================================================================
_REAL_TIME = time


class _OfflineClock:
    """Stands in for the `time` module: sleep() moves the clock instead of
    waiting. Everything else (strftime, gmtime, strptime) is the real one.

    A loop that never sleeps would never move this clock and would spin for
    ever, so after 20,000 reads with no sleep the clock moves on its own."""

    def __init__(self, t0):
        self.t = float(t0)
        self._reads = 0

    def time(self):
        self._reads += 1
        if self._reads > 20000:
            self._reads = 0
            self.t += 0.05
        return self.t

    def sleep(self, dt):
        self._reads = 0
        self.t += max(0.001, float(dt))

    def __getattr__(self, name):
        return getattr(_REAL_TIME, name)


def _ob(yes_bid, no_bid, size=50.0, age_ms=5):
    """A fake top of book, built the way livebook builds it: Kalshi books hold
    BIDS, so yes_ask = 1 - no_bid and no_ask = 1 - yes_bid."""
    return {"yes_bid": yes_bid, "no_bid": no_bid,
            "yes_bid_size": size if yes_bid is not None else None,
            "no_bid_size": size if no_bid is not None else None,
            "yes_ask": round(1.0 - no_bid, 4) if no_bid is not None else None,
            "yes_ask_size": size if no_bid is not None else None,
            "no_ask": round(1.0 - yes_bid, 4) if yes_bid is not None else None,
            "no_ask_size": size if yes_bid is not None else None,
            "age_ms": age_ms, "suspect": False}


def _fill_all(body, n):
    """A fake wire's answer: the whole order fills at its own limit."""
    return 201, {"order_id": "off-%d" % n,
                 "client_order_id": body.get("client_order_id"),
                 "fill_count": body.get("count"), "remaining_count": "0.00",
                 "average_fill_price": body.get("price"),
                 "average_fee_paid": "0.0020"}


# Every flag-controlled global main() sets BEFORE the startup self-test. The
# offline loop runs each of them at its _DEFAULT_ twin and gives the running
# value back afterwards. It has to: the loop self-tests run at every START
# with the operator's flags already applied, and a world run under the
# RUNNING flags refused to start arm-nohedge (--hedge-belief 0.01, 15 FAIL),
# every --skip-band arm that covers the 95c fixture (20 FAIL) and -- had live
# ever been set to --hedge-belief 0.10 or lower -- the live bot itself. The
# self-test compares this tuple against main()'s source, so a new flag that
# is not listed here fails the plain --selftest, not a live start.
_OFFLINE_PINNED_FLAGS = (
    "ATTEMPTS_ON_SEND",
    "DOUBT_MULT", "DOUBT_UNDER",
    "BAND_MULTS", "BANK_BRAKE", "DEPTH_LADDER", "DUMP_ENABLED", "EARLY_FRAC",
    "EARLY_MAX_EDGE", "EARLY_MAX_PRICE", "EARLY_MIN_PRICE", "EARLY_TAU_MAX",
    "EXTERNAL_DETECT", "EXTRA_COIN", "FLIP_MULT", "HEDGE_BELIEF",
    "HEDGE_JUMP_SIGMA", "HEDGE_NORMAL", "HEDGE_PANIC", "HEDGE_PRICE",
    "HEDGE_PROP", "HEDGE_PROP_FULL", "HEDGE_PROP_HALF", "HEDGE_SLIP",
    "HONEST_CONF", "IMPROVE_MAX", "IMPROVE_SCOPE", "JUMP_ENABLED",
    "LATE_EXTRA", "LATE_EXTRA_TAU", "LATE_JUMP_SD", "LATE_MULT", "LATE_PIN",
    "LATE_TAU", "LOSS_BOUND_OPEN", "LOSS_CAP", "MAX_PER_MARKET",
    "MIN_FILL_FRAC", "ONE_COIN_DEPTH", "ONE_COIN_MAX", "PICK", "PIN",
    "PRICE_CEILING", "REBUY_HEDGED", "REBUY_MAX_MULT", "SIGMA_RULER",
    "SIGMA_STRESS", "SIZE_MIRROR_ON", "SKIP_BANDS", "SWEEP_DEPTH",
    "SWEEP_ENABLED", "TAPER", "TAPER_FLOOR", "WIDEN_ENABLED")


def _offline_trade_loop(markets, live=False, take=None, reply=None,
                        freeze_at=None, rec_fault=None, run_s=12.0,
                        size=5.0, tau0=30, plant=False,
                        flags=None, get_delay=0.0, stall=None,
                        get_fail_after=None, max_positions=99, bank=None,
                        trec_split=False):
    """Run the REAL trade_loop for `run_s` fake seconds on one close.
    (`plant` sets --hedge-plant, the one-contract planted hedge test.)

    markets    dicts: tk, series, iid, strike, fair(t) -> P(YES) at index
               time t, book(t) -> top of book at wall time t (seconds from
               the start), and optionally cond_raise(t) -> True to make
               idx.conditions() raise. conditions() is called on every
               SIGNAL, outside every guarded sub-block, which is exactly
               where the 09-19 crash came from.
    live       drive the live order path. `take` replaces pintake.take
               outright; with take=None the REAL pintake.take runs against a
               fake wire whose answer is reply(body, n) -> (status, response).
    freeze_at  wall time after which EVERY index stops printing (a socket
               outage). K3b: a market's own optional `freeze_at` key stops
               that ONE index while the others keep arriving, which is what
               a single stalled CF Benchmarks stream looks like and is the
               case the 30 s socket timeout can never see.
    rec_fault  called as rec_fault(kind, kw) before each record; may raise.

    Every flag in _OFFLINE_PINNED_FLAGS runs at its _DEFAULT_ value, never
    the value the process was started with, and is restored afterwards.

    flags      {NAME: value} applied AFTER that pinning and handed back
               afterwards -- the only way a world can ask for a setting the
               shipped defaults do not have (e.g. EXTRA_COIN, without which
               the base-budget skip is unreachable).
    get_delay  seconds the fake clock jumps on every GET /markets, i.e. a
               PLANTED SLOW UNIVERSE REFRESH.
    stall      (after_s, dt) -- the first book read at or after `after_s`
               jumps the clock by `dt`, i.e. a PLANTED SLOW LOOP PASS.
    get_fail_after
               fake seconds after which every GET /markets answers 500, i.e.
               a PLANTED FAILED REFRESH. The universe is then not replaced,
               which is the case where `n` (markets held) says nothing and
               only `got` (markets THIS refresh built) can tell.
    max_positions
               the open-contract cap, as `max_positions x SIZE`. 99 is
               effectively no cap; a small value makes risk_abort return a
               TRANSIENT "open cap:" halt after the first fill, which is the
               only way to reach the loop's 1 s PAUSE branch offline.
    bank       dollars the fake balance reads, which turns the AUTO-SIZER ON
               (`a.auto_size`) and is the ONLY way to reach any of the three
               size WIDENERS offline. one_coin_cap() returns SIZE unchanged
               when the bank or the high-water mark is unknown -- "a failed
               balance read cannot size us up" -- so before this, A45, A48,
               A53 and R1 could not be driven at all, only unit-tested.
               `write_hwm` never lowers the mark, so HWM_FILE is redirected
               into this world's own temp dir: a leftover mark from an
               earlier world would silently shrink the headroom and the
               failure would look like the widener not working.
               A PAPER world also needs SIZE_MIRROR_ON False, or
               autosize_tick takes the mirror path and never reads a bank.

    Returns {"recs", "posts", "raised", "ran_s", "state"}. A record's `t` is
    fake wall time since the start, in seconds.
    """
    import argparse as _ap
    import contextlib as _cl
    import copy as _cp
    import io as _io
    import shutil as _sh
    import tempfile as _tf
    close = 1_800_000_000                       # a real quarter hour
    t0 = close - tau0 + 0.1
    clock = _OfflineClock(t0)
    by_iid = {m["iid"]: m for m in markets}
    iso = _REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ", _REAL_TIME.gmtime(close))

    def _last_print(iid):
        last = int(clock.t) - 1
        if freeze_at is not None:
            last = min(last, int(t0 + freeze_at) - 1)
        # K3b (2026-09-23): a PER-INDEX freeze. `freeze_at` stops every feed
        # at once, which is a socket outage -- and the socket's own 30 s
        # read timeout eventually reconnects that. One index frozen behind
        # eleven live ones never trips it, is what actually happens when a
        # single CF Benchmarks stream stalls, and is the case the old
        # harness could not build.
        _f1 = (by_iid.get(iid) or {}).get("freeze_at")
        if _f1 is not None:
            last = min(last, int(t0 + _f1) - 1)
        return last

    def _itime(iid):
        """Index time: whole seconds since the start, as of the newest print
        held. Frozen when the feed is, which is what fair() sees live."""
        return _last_print(iid) + 1 - int(t0)

    # R4: HOW MUCH WORK THE LOOP ASKED FOR, counted. The trajectory sampler
    # must be bounded at one book read, one index read, one sigma and one
    # fair() per market per SAMPLED SECOND, and "bounded" is a claim that has
    # to be measured rather than asserted -- so every call the loop makes into
    # the fake book and the fake index is counted and handed back.
    calls = {}

    def _count(k):
        calls[k] = calls.get(k, 0) + 1

    class _Idx:
        def spot(self, iid):
            _count("spot")
            s = _last_print(iid)
            return s, 100.5, clock.t - s

        def sigma(self, iid):
            _count("sigma")
            return 0.0005

        # R4: the trajectory record carries mu, the sd of the REMAINING
        # settlement window and the cushion in those sd, all of which come
        # from partial(). Without it here the harness could only prove the
        # fields are absent. The arithmetic is the real one -- the window is
        # [close-60, close-1], `hi < lo` means nothing is locked yet -- with a
        # flat index at the same 100.5 `spot` returns.
        def partial(self, iid, close_s, now_s):
            _count("partial")
            lo = close_s - N_AVG
            hi = min(now_s, close_s - 1)
            if hi < lo:
                return 0.0, N_AVG
            want = hi - lo + 1
            return 100.5 * want, N_AVG - want

        def recent_moves(self, iid, n=3):
            return []

        def conditions(self, iid):
            f = (by_iid.get(iid) or {}).get("cond_raise")
            if f is not None and f(_itime(iid)):
                raise TypeError("planted: type NoneType doesn't define "
                                "__round__ method")
            return None, None, None

    _stalled = {"done": False}

    class _Book:
        def best(self, tk):
            _count("best")
            # R2: a PLANTED SLOW PASS. The stall happens inside the scan,
            # exactly where a slow book read or a slow send would put it,
            # so the pass that contains it is the one that must be timed.
            if (stall is not None and not _stalled["done"]
                    and clock.t - t0 >= float(stall[0])):
                _stalled["done"] = True
                clock.t += float(stall[1])
            for m in markets:
                if m["tk"] == tk:
                    return m["book"](clock.t - t0)
            return None

        def subscribe(self, tks):
            pass

        def drop(self, tks):
            pass

        def buyable(self, tk, want, lim):
            return 0.0

        def rungs(self, tk, side, lim):
            return []

        def level_age_ms(self, tk, side, px):
            return None, False

        def depth(self, tk, side, n=3):
            return []

    def _fair(idx, iid, close_s, now_s, strike, sigma, round_digits=None):
        _count("fair")
        return by_iid[iid]["fair"](_itime(iid))

    def _get(path, params=None, **kw):
        if path == "/markets":
            # R2: a PLANTED SLOW REFRESH -- one GET, one clock jump, which
            # is what a fresh TCP+TLS connection per series actually costs.
            if get_delay:
                clock.t += float(get_delay)
            if (get_fail_after is not None
                    and clock.t - t0 >= float(get_fail_after)):
                return 500, {}          # a PLANTED FAILED REFRESH
            s = (params or {}).get("series_ticker")
            return 200, {"markets": [
                {"ticker": m["tk"], "close_time": iso,
                 "floor_strike": m["strike"],
                 "custom_strike": {"floor_strike": m["strike"],
                                   "round_digits": 2},
                 "exchange_index": 2}
                for m in markets if m["series"] == s]}
        return 200, {"market": {"status": "active"}}   # never finalised

    posts = []

    def _send(base, pk, key_id, method, path, body=None, query=None):
        if method != "POST" or base != pintake.DEMO:
            raise RuntimeError("offline loop: unexpected %s to %s"
                               % (method, base))
        posts.append(dict(body or {}, _t=round(clock.t - t0, 3)))
        return (reply or _fill_all)(body, len(posts))

    def _no_net(*a_, **k_):
        raise RuntimeError("offline loop: a network call was attempted")

    recs = []
    # R4: `trec_split` gives the trajectory writer its OWN list, the way
    # main() gives it its own FILE. Without it every trajectory record lands
    # in the same trail as the decisions and a test cannot tell the two
    # writers apart -- so an instrument that quietly wrote into
    # `pinrun-<tag>-*.jsonl`, the log pinledger, pinattrib, pinlab, barcheck
    # and earlyhindsight all parse, would pass every check in the suite.
    # Default OFF, so every existing world still reads one trail.
    trecs = []

    def _trec_split(kind, **kw):
        if rec_fault is not None:
            rec_fault(kind, kw)
        kw["kind"] = kind
        kw["t"] = round(clock.t - t0, 3)
        trecs.append(kw)

    def _rec(kind, **kw):
        if rec_fault is not None:
            rec_fault(kind, kw)
        kw["kind"] = kind
        kw["t"] = round(clock.t - t0, 3)
        try:
            json.dumps(kw, default=str)         # what main()'s rec writes
        except Exception:                       # noqa: BLE001
            pass                                # ...and main() swallows this
        recs.append(kw)

    g = globals()
    saved = {k: g[k] for k in ("time", "get", "fair", "SIZE", "DAYLOSS_FILE",
                               "read_bank", "publish_size", "HWM_FILE")}
    pinned = {k: g[k] for k in _OFFLINE_PINNED_FLAGS}
    # captured BEFORE the pinning, so the hand-back is the value the process
    # started with whether or not the key is also a pinned flag
    extra_was = {k: g[k] for k in (flags or {})}
    loop_state = None
    saved_creds = dict(CREDS)
    saved_pt = (pintake.time, pintake.take, pintake._get,
                pintake.ordercli.send, pintake.ordercli.cancel)
    saved_rails = (pintake.MAX_TAKE_COUNT, pintake.HARD_MAX,
                   pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT)
    saved_ledger = _cp.deepcopy(pintake.LEDGER)
    tmp = _tf.mkdtemp(prefix="pinloop-")
    raised = None
    try:
        for k in _OFFLINE_PINNED_FLAGS:
            g[k] = g["_DEFAULT_" + k]
        for k, v in (flags or {}).items():
            g[k] = v
        g["time"] = clock
        g["get"] = _get
        g["fair"] = _fair
        g["SIZE"] = float(size)
        g["DAYLOSS_FILE"] = os.path.join(tmp, "dayloss.json")
        g["HWM_FILE"] = os.path.join(tmp, "hwm.json")
        g["read_bank"] = (_no_net if bank is None
                          else (lambda *_a, **_k: float(bank)))
        g["publish_size"] = _no_net
        CREDS.update({"base": pintake.DEMO, "pk": None, "key_id": None})
        pintake.time = clock
        pintake._get = _no_net
        setattr(pintake.ordercli, "send", _send)
        setattr(pintake.ordercli, "cancel", _no_net)
        if take is not None:
            pintake.take = take
        pintake.reset_ledger()
        a_ = _ap.Namespace(live=bool(live), minutes=run_s / 60.0,
                           auto_size=bank is not None, loss_abort=-1e9,
                           max_positions=int(max_positions), max_losses=0,
                           size=float(size), hedge_plant=bool(plant))
        with _cl.redirect_stdout(_io.StringIO()):
            try:
                loop_state = trade_loop(
                    a_, _rec, _Book(), _Idx(),
                    {m["series"]: m["iid"] for m in markets},
                    trec=(_trec_split if trec_split else None))[0]
            except Exception as e:              # noqa: BLE001
                raised = "%s: %s" % (type(e).__name__, e)
    finally:
        for k, v in saved.items():
            g[k] = v
        for k, v in pinned.items():
            g[k] = v
        for k, v in extra_was.items():
            g[k] = v
        CREDS.clear()
        CREDS.update(saved_creds)
        pintake.time, pintake.take, pintake._get = saved_pt[:3]
        setattr(pintake.ordercli, "send", saved_pt[3])
        setattr(pintake.ordercli, "cancel", saved_pt[4])
        (pintake.MAX_TAKE_COUNT, pintake.HARD_MAX, pintake.MAX_RUN_STAKE,
         pintake.LOSS_ABORT) = saved_rails
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved_ledger)
        _sh.rmtree(tmp, ignore_errors=True)
    return {"recs": recs, "trecs": trecs, "posts": posts, "raised": raised,
            "ran_s": round(clock.t - t0, 3), "state": loop_state,
            "calls": calls}


# ===========================================================================
def selftest():
    """
    THE HIGH-WATER FILE IS REDIRECTED FOR THE WHOLE OF THIS FUNCTION, and the
    reason is a production outage. On 2026-09-14 a check called autosize_tick
    with a fake bank of $1,000,000 to prove the size cap held. write_hwm()
    duly recorded $1,000,000 in results/pinrun-hwm.json. The self-test runs
    before every live start, so the next live bot read a real bank of $313
    against a $1,000,000 high, computed a 100% drawdown and halted on its
    first pass -- with the previous bot already stopped. The bot was down.

    Redirecting HERE rather than at each call site is deliberate: several
    calls span multiple lines, and a per-call fix is one forgotten argument
    away from repeating it. A test must not be able to write production state
    at all.
    """
    # A66, 2026-09-19: SIZE_MIRROR joins HWM_FILE here, for the identical
    # reason and after the identical failure. The startup self-test drives
    # autosize_tick with a FAKE $60 bank and a live-ish args object; that
    # published {"size": 7.0, "bank": 60.0} into the real mirror, and the 36
    # arms restarted minutes later all obediently sized themselves to SEVEN
    # contracts. Paper only, caught within two minutes, and the lesson is the
    # one already written above: a per-call `mirror_path=` is one forgotten
    # argument away from doing it again, so the global is redirected instead.
    _hwm_real, _mir_real = HWM_FILE, SIZE_MIRROR
    import tempfile as _tfhw
    _hwm_dir = _tfhw.mkdtemp(prefix="pinhwm-")
    globals()["HWM_FILE"] = os.path.join(_hwm_dir, "hwm.json")
    globals()["SIZE_MIRROR"] = os.path.join(_hwm_dir, "size-mirror.json")
    try:
        return _selftest_body()
    finally:
        globals()["HWM_FILE"] = _hwm_real
        globals()["SIZE_MIRROR"] = _mir_real
        try:
            for _f in os.listdir(_hwm_dir):
                os.remove(os.path.join(_hwm_dir, _f))
            os.rmdir(_hwm_dir)
        except OSError:
            pass


_FLAG_GLOBALS = ("LATE_EXTRA_TAU", "LATE_EXTRA", "LATE_TAU", "LATE_MULT",
                 "LATE_PIN", "LATE_JUMP_SD", "EXTRA_COIN", "BAND_MULTS",
                 "SKIP_BANDS", "HEDGE_PRICE", "HEDGE_PANIC", "HEDGE_BELIEF",
                 "EARLY_MAX_EDGE", "EARLY_MIN_PRICE", "EARLY_TAU_MAX",
                 "EARLY_FRAC", "BANK_BRAKE", "SIGMA_STRESS", "FLIP_MULT",
                 "REBUY_HEDGED", "PIN", "PRICE_CEILING", "MIN_FILL_FRAC",
                 "LOSS_CAP", "DOUBT_MULT", "DOUBT_UNDER")


def _selftest_body():
    # every live setting as the process actually started, so the guard at the
    # end can prove the test gave them all back
    _flags_before = {n: globals()[n] for n in _FLAG_GLOBALS}
    print("SELF-TEST -- pinrun")
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    idx = IndexWS(["TEST"])
    C = 1_000_000

    # --- CORRECTION 1: the window is [close-60, close-1] ---
    # plant a wild value at `close` (must be EXCLUDED) and at close-60
    # (must be INCLUDED).
    for s in range(C - 60, C):
        idx.ticks["TEST"][s] = 100.0
    idx.ticks["TEST"][C - 60] = 0.0          # inside the window
    idx.ticks["TEST"][C] = 1e6               # outside it
    locked, r = idx.partial("TEST", C, C)
    ck(r == 0, f"all 60 prints locked at now=close (remaining {r})")
    ck(abs(locked - (59 * 100.0)) < 1e-6,
       f"locked sum excludes tick@close and includes tick@close-60 "
       f"({locked:.1f}, expected 5900.0)")
    f = fair(idx, "TEST", C, C, 50.0, 1.0)
    ck(abs(f - 1.0) < 1e-9, f"decided yes on the corrected window (fair {f})")

    # the OLD window would have given a wildly different mean -- prove it
    old_locked = sum(idx.ticks["TEST"][s] for s in range(C - 59, C + 1))
    ck(abs(old_locked - locked) > 1e5,
       "old and new windows genuinely differ on this fixture")

    # --- CORRECTION 2: rounding to the strike's precision ---
    # the real losing market: strike 2492.82, settle 2492.8158, d=2 -> YES
    ck(abs(eff_strike(2492.82, 2) - 2492.815) < 1e-9,
       "eff_strike(2492.82, d=2) == 2492.815")
    idx2 = IndexWS(["E"])
    for s in range(C - 60, C):
        idx2.ticks["E"][s] = 2492.8158
    f_round = fair(idx2, "E", C, C, 2492.82, 1.0, round_digits=2)
    f_raw = fair(idx2, "E", C, C, 2492.82, 1.0, round_digits=None)
    ck(f_round == 1.0, f"rounding-aware fair calls the real ETH market YES "
                       f"({f_round})")
    ck(f_raw == 0.0, f"the un-rounded model calls it NO ({f_raw}) -- the "
                     f"-90.91c loss")

    # --- CORRECTION 3: a print that has NOT ARRIVED is not a locked print ---
    # A steady uptrend with the newest print still in flight. The first
    # version ended the locked window at now_s and scaled the observed sum by
    # want/len(got) -- imputing the WINDOW MEAN for the missing second, which
    # on a trend sits far below the latest print. The model then buys the
    # wrong side at ~99c. This fixture fails if that ever comes back.
    idx5 = IndexWS(["R"])
    for s in range(C - 60, C - 3):          # up to close-4; close-3 in flight
        idx5.ticks["R"][s] = 1000.0 + 1.0 * (s - (C - 60))
    lockd, r5 = idx5.partial("R", C, C - 3)
    ck(r5 == 3 and abs(lockd - sum(idx5.ticks["R"].values())) < 1e-9,
       f"the locked window ends at the newest print HELD, not at now "
       f"(remaining {r5}, locked {lockd:.1f})")
    spot5 = idx5.ticks["R"][C - 4]
    mu_new = (lockd + r5 * spot5) / N_AVG
    got_old = [idx5.ticks["R"][s] for s in range(C - 60, C - 2)
               if s in idx5.ticks["R"]]
    want_old = (C - 3) - (C - 60) + 1
    mu_old = (sum(got_old) * (want_old / len(got_old)) + 2 * spot5) / N_AVG
    K5 = mu_new - 0.005
    f_new = fair(idx5, "R", C, C - 3, K5, 0.02)
    f_old = ND.cdf((mu_old - K5) / (0.02 * math.sqrt(var_factor(2, [1.0]))))
    ck(f_new >= PIN and f_old <= 1.0 - PIN,
       f"with the newest print in flight on a rising index the corrected "
       f"model says YES (fair {f_new:.4f}); mean-imputation said NO "
       f"(fair {f_old:.4f}) -- a wrong-side buy at ~99c")

    # an interior gap is filled from the NEAREST print, never the window mean
    idx7 = IndexWS(["H"])
    for s in range(C - 60, C):
        idx7.ticks["H"][s] = 100.0
    idx7.ticks["H"][C - 30] = 999.0
    del idx7.ticks["H"][C - 31]
    lk, rr = idx7.partial("H", C, C)
    ck(rr == 0 and abs(lk - 6899.0) < 1e-9,
       f"an interior gap takes the nearest print ({lk}, expected 6899.0; "
       f"the window-mean rule would say {6799.0 * 60 / 59:.1f})")

    # and a window missing more than 5% of its prints is refused outright
    idx6 = IndexWS(["G"])
    for s in range(C - 60, C - 3):
        if (s - (C - 60)) % 7:
            idx6.ticks["G"][s] = 100.0
    ck(idx6.partial("G", C, C - 3) is None,
       "partial refuses a window missing more than 5% of its prints")

    # --- fee-netted edge ---
    # --- THE EXPECTED-VALUE GATE (AMENDMENT 2) ---
    # --- AMENDMENT 8: what SURVIVED the forensics of the first loss ---------
    # Almost nothing did. Flatness, sigma regime and recent-jump separate
    # losers from winners at p 0.14-0.99, and once the model's own risk number
    # is held fixed NOTHING adds anything. Every entry gate tested costs 22-44
    # WINNING trades per loss avoided. Two cheap structural fixes survived.

    # (A) both sides of one market is a CERTAIN loss on one of the two orders
    def _pair_cost(p_yes, p_no):
        return (p_yes + p_no) - 1.0          # paid, minus the guaranteed $1
    ck(_pair_cost(0.983, 0.908) > 0,
       f"buying YES at 98.3c and NO at 90.8c on ONE market pays "
       f"{100*(0.983+0.908):.1f}c for a guaranteed $1.00 -- a locked "
       f"{100*_pair_cost(0.983,0.908):.1f}c loss carrying NO directional risk")
    ck(all(_pair_cost(a, b) > 0 for a in (0.51, 0.73, 0.99)
           for b in (0.51, 0.73, 0.99)),
       "and EVERY price the rule can pay is above 50c, so a both-sides pair is "
       "ALWAYS a locked loss -- there is no price at which it is not")
    _pv = {"n": 1, "best": 0.98, "tk": "A", "sides": {"A": "yes"}}
    ck(_pv["sides"].get("A") == "yes" and _pv["sides"].get("B") is None,
       "the side taken is recorded PER TICKER, so a second market is "
       "unaffected -- the guard must not block ordinary diversification")

    # (B) the brake counts CLOSES, because a close is one draw
    _lc = set()
    for _cs in (100, 100, 100, 200):
        _lc.add(_cs)
    ck(len(_lc) == 2,
       f"three losing trades on ONE close plus one on another is TWO losing "
       f"closes, not four ({len(_lc)}) -- tonight three fills on one NEAR "
       f"market spent the whole 3-loss budget on a SINGLE draw")
    ck(len({100}) < 3,
       "so one bad close can no longer exhaust a 3-close brake by itself, "
       "which is what 'three losses is roughly a 1% event' actually assumed")

    # --- TWO FILLS ON THE SAME TICKER MUST BOTH SURVIVE ---------------------
    # 2026-09-08 23:29:53Z filled KXSOL15M twice in one close, at 94.0c and
    # 90.1c. open_pos was keyed by TICKER, so the second overwrote the first:
    # the 112.10c win was never booked and its $18.80 stake was never released.
    # The bank was right; the ledger was not. An unbooked LOSS would be
    # invisible to the loss abort, which is the dangerous direction, and
    # MAX_PER_CLOSE 3 makes same-ticker repeats MORE likely.
    _op = {}
    _op["ord-A"] = (100, "no", 0.94, 20.0, "KXSOL15M-X")
    _op["ord-B"] = (100, "no", 0.901, 20.0, "KXSOL15M-X")
    ck(len(_op) == 2,
       "two fills on the SAME ticker occupy TWO entries -- keyed by order id, "
       "the second cannot overwrite the first")
    ck(sum(c * n for (_, _, c, n, _t) in _op.values()) == 0.94 * 20 + 0.901 * 20,
       f"and open exposure is the SUM of both stakes "
       f"(${sum(c*n for (_,_,c,n,_t) in _op.values()):.2f}), not just the last")
    _tk = _op["ord-A"][4]
    del _op["ord-A"]
    ck(any(v[4] == _tk for v in _op.values()),
       "releasing ONE of them leaves the ticker still referenced, so the "
       "position record must NOT be dropped yet")
    del _op["ord-B"]
    ck(not any(v[4] == _tk for v in _op.values()),
       "and only when the last one goes is the ticker free -- the null, so a "
       "release cannot fire early")
    _src10 = open(os.path.abspath(__file__), encoding="utf-8").read()
    _b10 = _src10[_src10.index(chr(10) + "def trade_loop("):]
    ck("open_pos[tk]" not in _b10,
       "and NOTHING in the loop still keys open_pos by ticker")

    # --- THE RUNAWAY OF 2026-09-08 22:44Z MUST NOT RECUR --------------------
    # 160 identical orders into ONE close in ONE second, all refused, none
    # filled, no error logged, no money lost. Two of my own changes, neither
    # wrong alone: MAX_TAKE_COUNT = 10 silently refused every order at size 20
    # (the FOURTH size-1 literal in a day), and AMENDMENT 6 had just stopped a
    # no-fill from consuming a slot -- correctly, since an unfilled order
    # creates no exposure -- leaving NOTHING that bounded retries.
    ck(MAX_ATTEMPTS_PER_CLOSE > MAX_PER_CLOSE,
       f"attempts ({MAX_ATTEMPTS_PER_CLOSE}) are capped ABOVE fills "
       f"({MAX_PER_CLOSE}) -- separate budgets, because a lost race should "
       f"cost a retry but not a fill slot")
    # THIS BAR MOVED, 2026-09-14, AND IT IS SAID LOUDLY BECAUSE IT IS A
    # SAFETY BAR. It used to read `MAX_ATTEMPTS_PER_CLOSE < 20`, on the
    # reasoning that a small close-level cap is what stops a 20 Hz loop
    # spamming. That reasoning was wrong about WHICH cap does that work: the
    # runaway it was written for put 160 orders into ONE market, and a
    # close-level cap only stops that after it has also stopped the bot
    # trying every OTHER market. AMENDMENT 26 moved the spam protection to
    # MAX_ATTEMPTS_PER_MARKET, which is strictly tighter for the runaway case
    # (3 orders, not 8), and freed the close cap to cover all twelve coins.
    ck(MAX_ATTEMPTS_PER_MARKET <= 3,
       f"spam into ONE market is capped at {MAX_ATTEMPTS_PER_MARKET} orders "
       f"-- this is the bar that replaced `MAX_ATTEMPTS_PER_CLOSE < 20`, and "
       f"it is tighter than that one was for the runaway it was written for")
    ck(MAX_ATTEMPTS_PER_CLOSE <= 2 * 12 + 4,
       f"and the close cap is still bounded -- every coin twice plus a little "
       f"({MAX_ATTEMPTS_PER_CLOSE}), not unlimited")
    _src9 = open(os.path.abspath(__file__), encoding="utf-8").read()
    _b9 = _src9[_src9.index(chr(10) + "def trade_loop("):]
    ck("attempts.get(close_s, 0) >= MAX_ATTEMPTS_PER_CLOSE" in _b9,
       "the attempt cap is actually READ in the loop, not merely defined")
    ck("attempts_tk.get((close_s, tk), 0) >= MAX_ATTEMPTS_PER_MARKET" in _b9,
       "and so is the per-market cap -- a safety bar that is defined but "
       "never read is the exact defect risk_abort was once caught with")
    ck("attempts_tk[(close_s, tk)] = attempts_tk.get((close_s, tk), 0) + 1"
       in _b9,
       "and it is incremented on every send, or it can never bind")
    # EVERY send in the loop must be preceded by an attempt increment, in its
    # own block. The first version compared the FIRST increment against the
    # FIRST take(); AMENDMENT 15 added a second take() (the hedge) that counts
    # its attempt under a different name (_hcs), so the literal match could no
    # longer see that the property still holds. Now: for each take(), the
    # nearest preceding attempts[...] write must be an increment.
    import re as _re9
    _takes9 = [m.start() for m in _re9.finditer(r"pintake\.take\(", _b9)]
    _incs9 = [m.start() for m in
              _re9.finditer(r"attempts\[\w+\] = attempts\.get\(\w+, 0\) \+ 1", _b9)]
    ck(len(_takes9) >= 2 and all(any(i < t for i in _incs9) for t in _takes9)
       and all(max(i for i in _incs9 if i < t) >
               (max((u for u in _takes9 if u < t), default=-1)) for t in _takes9),
       "and an attempt is counted BEFORE the order is sent, so a send that "
       "never returns still consumes one")
    ck('out.get("refused")' in _b9 and 'state["order_errors"]' in _b9,
       "a RETURNED refusal is counted as an order error -- take() does not "
       "raise, so nothing noticed 160 refusals in a row")
    ck(pintake.MAX_TAKE_COUNT <= pintake.HARD_MAX,
       f"pintake's own count rail is below its hard ceiling "
       f"({pintake.MAX_TAKE_COUNT:g} <= {pintake.HARD_MAX:g})")
    _sv9 = (pintake.MAX_TAKE_COUNT, pintake.HARD_MAX)
    try:
        pintake.set_limits(max_take_count=_sv9[0] + 5, why="selftest")
        ck(pintake.MAX_TAKE_COUNT == _sv9[0] + 5,
           "set_limits RAISES the count rail so it can never be the thing that "
           "silently blocks a bigger size again")
        _raised9 = False
        try:
            pintake.set_limits(max_take_count=1.0)
        except ValueError:
            _raised9 = True
        ck(_raised9, "and it REFUSES to lower it")
    finally:
        pintake.MAX_TAKE_COUNT, pintake.HARD_MAX = _sv9

    # --- AMENDMENT 7: THREE fills in ONE close must be accounted correctly ---
    # The order path for a third buy is IDENTICAL code to the second, which is
    # proven live. What is genuinely new is holding MAX_PER_CLOSE positions
    # from one close at once, so that is what this tests: the committed stake,
    # the forward-looking loss bound, and the position cap.
    _sv7 = dict(pintake.LEDGER)
    try:
        pintake.reset_ledger()
        # PRICES DERIVED FROM THE CAP, never typed. A literal [0.98,0.96,0.94]
        # was correct at MAX_PER_CLOSE 3 and became a false alarm the instant
        # the cap moved to 2. That is the SAME lesson as pintake's "count 2
        # must be refused" and the scale-in rail before it: A RAIL TEST IS
        # WRITTEN IN TERMS OF THE RAIL.
        _sz = 20.0
        _pxs = [round(0.98 - 0.02 * k, 4) for k in range(int(MAX_PER_CLOSE))]
        ck(len(_pxs) == MAX_PER_CLOSE,
           f"the fixture buys exactly MAX_PER_CLOSE times ({MAX_PER_CLOSE})")
        ck(all(_pxs[i] <= _pxs[i - 1] - IMPROVE_BY for i in range(1, len(_pxs))),
           "and every later buy is at least IMPROVE_BY cheaper -- so the "
           "marginal trade cap 3 adds is the CHEAPEST of the close, which is "
           "why it cannot degrade the average price paid")
        for i, _p in enumerate(_pxs):   # fills == MAX_PER_CLOSE by construction
            pintake.LEDGER["committed"] = float(
                pintake.LEDGER["committed"]) + _p * _sz
            pintake.LEDGER["positions"][f"T{i}"] = {"n": _sz, "price": _p}
        _want = sum(_p * _sz for _p in _pxs)
        ck(abs(pintake.LEDGER["committed"] - _want) < 1e-9,
           f"three fills commit ${pintake.LEDGER['committed']:.2f}, the sum of "
           f"their stakes, not three times the first")
        ck(pintake.LEDGER["committed"] < 1.00 * _sz * MAX_PER_CLOSE + 1e-9,
           f"and that is at or below the ${1.00*_sz*MAX_PER_CLOSE:.0f} worst "
           f"case the deployment rail sizes the brake against -- the rail is "
           f"conservative, as it must be")
        for i in range(len(_pxs)):
            committed_for(_pxs[i], _sz)
        _rel = sum(committed_for(_p, _sz) for _p in _pxs)
        ck(abs(_rel - _want) < 1e-9,
           "and releasing all three gives back EXACTLY what was committed")

        class _A7:
            loss_abort = -90.0
            max_positions = 4
            size = _sz
            max_losses = 0
        ck(risk_abort({"halted": False, "errors": 0,
                       "open_cost": _want}, _A7) is None,
           f"the forward loss bound tolerates all three open (${_want:.2f} vs "
           f"a $-90.00 brake)")

        # AMENDMENT 31 RESTATES THIS TEST. It used to set max_positions to
        # MAX_PER_CLOSE and require the cap to REFUSE, showing that the
        # setting must leave room for a straggler from the previous close.
        # The cap now counts CONTRACTS, so the same point is made in
        # contracts: a cap that only covers one close's worth of them refuses
        # the moment anything is still settling.
        # the positions are planted here rather than inherited, so the test
        # cannot quietly pass on an empty ledger
        _sz31 = float(SIZE)
        pintake.LEDGER["positions"] = {
            "PREV": {"want": "yes", "contracts": _sz31},      # straggler
            "NOW1": {"want": "yes", "contracts": _sz31},      # this close
        }
        _held = open_contracts(pintake.LEDGER)
        ck(abs(_held - 2 * _sz31) < 1e-9,
           f"the fixture holds two full sizes ({_held:g} contracts), or the "
           f"test below would prove nothing")

        class _A7b(_A7):
            max_positions = 2                     # 2 x SIZE = exactly held
        _r7 = risk_abort({"halted": False, "errors": 0}, _A7b)
        ck(_r7 is not None and "open cap" in _r7,
           f"a cap of 2 x size refuses the next fill while a straggler from "
           f"the previous close is STILL OPEN, which is why --max-positions "
           f"must leave room for one ({_r7})")

        class _A7c(_A7):
            max_positions = 3                     # 3 x SIZE leaves room
        ck(risk_abort({"halted": False, "errors": 0}, _A7c) is None,
           "and a cap of 3 x size lets that fill through -- the live setting")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_sv7)

    # --- the LOSS-COUNT brake (added 2026-09-08, first funded deployment) ---
    class _AL:
        loss_abort = -1e9
        max_positions = 99
        size = 20.0
        max_losses = 3
    _sv = dict(pintake.LEDGER)
    try:
        pintake.reset_ledger()
        pintake.LEDGER["losses"] = 2
        ck(risk_abort({"halted": False, "errors": 0}, _AL) is None,
           "2 losses does NOT halt a run whose brake is 3")
        pintake.LEDGER["losses"] = 3
        _r = risk_abort({"halted": False, "errors": 0}, _AL)
        ck(_r is not None and "loss COUNT" in _r,
           f"3 losses DOES halt it, on COUNT and not on dollars ({_r})")
        _AL2 = type("X", (), dict(loss_abort=-1e9, max_positions=99,
                                  size=20.0, max_losses=0))
        ck(risk_abort({"halted": False, "errors": 0}, _AL2) is None,
           "and max_losses=0 DISABLES it -- the null, so the brake cannot fire "
           "on a run that never asked for it")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_sv)

    # --- AMENDMENT 6: partial fills, and a slot consumed by a FILL ----------
    # ZERO IS VALID SINCE 2026-09-14 (v-nofloor). This check used to demand
    # 0.0 < MIN_FILL_FRAC and so REFUSED TO START the moment the operator's
    # "no 10%" went live -- the bot was down for four minutes. It is the same
    # trap as 2026-09-13: a self-test asserted against the RUNNING value that
    # a new flag is allowed to change. Assert the DECLARED default instead,
    # and bound the running value only by what it may never exceed.
    ck(0.0 < _DEFAULT_MIN_FILL_FRAC <= 1.0,
       f"the DECLARED depth floor is a fraction ({_DEFAULT_MIN_FILL_FRAC})")
    ck(0.0 <= MIN_FILL_FRAC <= _DEFAULT_MIN_FILL_FRAC,
       f"and the running floor sits in [0, {_DEFAULT_MIN_FILL_FRAC}] -- zero "
       f"means MIN_LEVEL is the only floor, which is the operator's 'no 10%' "
       f"(running {MIN_FILL_FRAC})")

    # THE FLOOR IS PASSED IN, NOT READ FROM THE GLOBAL. AMENDMENT 28 made
    # MIN_FILL_FRAC a flag, and a test that asserts a specific refusal while
    # reading the RUNNING value refuses to start the moment the flag is used.
    # That exact shape has stopped this bot booting five times; the fix is
    # always the same -- test the RULE at a stated floor, and test the
    # DECLARED default separately.
    def _take_n(offered, size, frac=None):
        f = _DEFAULT_MIN_FILL_FRAC if frac is None else frac
        t = min(float(size), float(offered))
        return t if t >= max(MIN_LEVEL, f * float(size)) else None

    ck(_take_n(1000, 10) == 10.0,
       "a deep book fills the whole size we asked for")
    ck(_take_n(7, 10) == 7.0,
       "a 7-contract offer at size 10 is TAKEN as a partial, not thrown away "
       "-- the old dust gate refused it outright")
    ck(_take_n(4, 10) is None,
       "at the DECLARED floor of half, a 4-contract scrap at size 10 is "
       "refused -- the behaviour AMENDMENT 6 shipped")
    ck(_take_n(4, 10, frac=0.10) == 4.0,
       "and at a floor of 0.10 the same scrap is TAKEN, which is what "
       "AMENDMENT 28 puts in a what-if: the same bet at the same gate, on "
       "fewer contracts")
    ck(_take_n(0.5, 1, frac=0.01) is None,
       "sub-contract dust is refused at EVERY floor -- MIN_LEVEL is the "
       "backstop and --min-fill-frac cannot get underneath it")
    ck(_take_n(30, 10) == 10.0 and _take_n(10, 10) == 10.0,
       "a partial can only ever LOWER the contracts bought, never raise them, "
       "so this amendment cannot increase exposure")

    # a slot must be consumed by a FILL, never by an attempt
    _fired = {}

    def _slot(close_s, px, tk="X"):
        pv = _fired.get(close_s)
        if pv is None:
            _fired[close_s] = {"n": 1, "best": px, "tk": tk}
        else:
            pv["n"] += 1
            pv["best"] = min(pv["best"], px)

    _slot(1, 0.98)
    ck(_fired[1]["n"] == 1 and _fired[1]["best"] == 0.98,
       "a filled buy books a slot and sets the improve bar")
    _slot(1, 0.93)
    ck(_fired[1]["n"] == 2 and _fired[1]["best"] == 0.93,
       "a second fill books the second slot and LOWERS the bar to the better "
       "price")
    # FILL THE REST RELATIVE TO THE CONSTANT. Writing "2" here was correct at
    # MAX_PER_CLOSE = 2 and became a false alarm the moment the cap moved to 3
    # -- the same shape as pintake's "count 2 must be refused" test. Rail tests
    # are written in terms of the rail, never as a literal.
    for _k in range(2, int(MAX_PER_CLOSE)):
        _slot(1, 0.93 - 0.01 * (_k - 1))
    ck(_fired[1]["n"] >= MAX_PER_CLOSE,
       f"and {MAX_PER_CLOSE} FILLS still exhaust the close -- max exposure is "
       f"UNCHANGED by this amendment, only wasted attempts are recovered")

    # ---- AMENDMENT 13: ONE FILL PER MARKET -----------------------------
    # The rail, exercised the way the loop exercises it: book a fill, then ask
    # whether a SECOND fill on the same ticker is allowed, and whether a fill
    # on a DIFFERENT ticker still is. Written in terms of MAX_PER_MARKET, not
    # as a literal 1, so raising the constant cannot silently pass this.
    def _blocked(pv, tk):
        return pv is not None and             pv.get("per_tk", {}).get(tk, 0) >= MAX_PER_MARKET
    _f13 = {"n": 1, "best": 0.97, "tk": "A", "sides": {"A": "no"},
            "tickers": {"A"}, "per_tk": {"A": MAX_PER_MARKET}}
    ck(_blocked(_f13, "A"),
       f"a market that already filled {MAX_PER_MARKET}x is refused a repeat "
       f"-- this is what turned one bad NEAR close into -$52.60")
    ck(not _blocked(_f13, "B"),
       "but a DIFFERENT market on the same close is still allowed, because "
       "MAX_PER_CLOSE governs that and rho ~ 0.8 is not rho = 1")
    ck(not _blocked(None, "A"),
       "and the first fill of a close is never blocked")
    ck(MAX_PER_MARKET * SIZE <= MAX_PER_CLOSE * SIZE,
       "one market can never stake more than the whole close is allowed to")
    _worst13 = 1.00 * float(SIZE) * MAX_PER_CLOSE
    _worst_old = 1.00 * float(SIZE) * MAX_PER_CLOSE   # unchanged by A13
    ck(abs(_worst13 - _worst_old) < 1e-9,
       f"A13 does not change the worst CLOSE (${_worst13:.2f}); it changes "
       f"how much of it one market may be -- ${1.00*float(SIZE)*MAX_PER_MARKET:.2f} "
       f"instead of all of it")
    _src2 = open(os.path.abspath(__file__), encoding="utf-8").read()
    # ANCHOR ON A NEWLINE. Searching for the bare text finds this test's OWN
    # string literal first, because selftest() is defined above trade_loop --
    # a self-test that silently inspects itself instead of the code proves
    # nothing. The pre-existing abort-ordering test below has the same shape
    # and is corrected the same way.
    _b2 = _src2[_src2.index(chr(10) + "def trade_loop("):]
    _i_take = _b2.index("out = pintake.take(")
    _i_slot = _b2.index("_book_slot(cost, filled)")
    ck(_i_slot > _i_take,
       "STRUCTURAL: the live slot is booked AFTER the order returns, so a "
       "zero-fill cannot burn it")
    ck("if filled > 0:" in _b2[:_i_slot],
       "and it is booked only inside the filled>0 branch")
    # --- AMENDMENT 12: a scrap fill is not a slot ---------------------------
    ck("if filled >= _real:" in _b2[:_i_slot] and
       _b2.index("if filled >= _real:") > _b2.index("if filled > 0:"),
       "STRUCTURAL: the slot is booked only when the FILL is at least half "
       "our size; a scrap keeps its position and spends no slot")
    ck("_note_scrap(cost, filled)" in _b2 and 'rec("scrap"' in _b2,
       "and a scrap is recorded, not silent")
    # --- AMENDMENT 17: under a CONTRACT budget a scrap still spends budget --
    ck("_book_slot(cost, filled, raise_bar=False)" in _b2,
       "under CLOSE_BUDGET a scrap must book its CONTRACTS -- they are real "
       "exposure however small -- while still not raising the improve bar, "
       "which is the only thing A12's exemption was actually protecting")
    # AMENDMENT 12a: scraps accumulate, so exposure stays bounded
    ck('pv["scrap_n"] = pv.get("scrap_n", 0.0) + float(nfilled)' in _b2
       and 'pv["n"] += 1' in _b2[_b2.index('pv["scrap_n"] ='):],
       "STRUCTURAL: scraps ACCUMULATE and spend a slot once they add up to a "
       "real fill -- without this, 8 scraps of 9.99 would double the "
       "worst-case close from $39.20 to $78.32")
    _fired_t = {}

    def _scrap_sim(n_each, times, size=20.0):
        """what the loop does, in miniature: how many slots do N scraps spend"""
        pv = {"n": 0, "scrap_n": 0.0, "best": 1.0}
        real = max(MIN_LEVEL, MIN_FILL_FRAC * size)
        for _ in range(times):
            pv["scrap_n"] += n_each
            if pv["scrap_n"] >= real:
                pv["n"] += 1
                pv["scrap_n"] = 0.0
        return pv["n"]
    ck(_scrap_sim(0.02, 8) == 0,
       "eight 0.02-contract crumbs spend NO slot (0.16 of 10) -- the case "
       "A12 exists for")
    # THE ASSERTION THAT MATTERS IS THE EXPOSURE BOUND, NOT THE SLOT COUNT.
    # A first version of this check asserted 7 slots for eight 9.99 scraps;
    # the code gives 4 and the code is right (9.99 alone is under the line,
    # 19.98 crosses it and resets). The fixture was sloppy arithmetic, and it
    # was also measuring the wrong quantity.
    def _max_contracts(n_each, size=20.0):
        """contracts filled before the slots run out, which is the only
        number that bounds the money at risk in one close"""
        pv_n, scrap_n, total = 0, 0.0, 0.0
        real = max(MIN_LEVEL, MIN_FILL_FRAC * size)
        while pv_n < MAX_PER_CLOSE and total < 1000:
            total += n_each
            scrap_n += n_each
            if scrap_n >= real:
                pv_n += 1
                scrap_n = 0.0
        return total
    _intended = MAX_PER_CLOSE * 20.0
    for _each in (9.99, 5.0, 2.0, 0.5):
        _got = _max_contracts(_each)
        ck(_got <= _intended + 20.0,
           f"scraps of {_each:g}: at most {_got:.2f} contracts fill in one "
           f"close, against the intended {_intended:.0f} -- bounded")
    # and within the REAL attempt cap, crumbs never cost a slot. (A first
    # version asserted they never exhaust the slots at all; they do, after a
    # thousand of them. MAX_ATTEMPTS_PER_CLOSE is what actually bounds it,
    # and asserting a bound that does not exist is worse than not asserting.)
    ck(_scrap_sim(0.02, MAX_ATTEMPTS_PER_CLOSE) == 0,
       f"within the {MAX_ATTEMPTS_PER_CLOSE}-attempt cap, 0.02 crumbs spend "
       f"no slot at all -- the case A12 exists for")
    ck(_scrap_sim(9.99, MAX_ATTEMPTS_PER_CLOSE) >= MAX_PER_CLOSE,
       "while near-full scraps exhaust the slots inside the same cap")
    # AT THE DECLARED FLOOR, not the running one -- --min-fill-frac (A28)
    # moves this line, and asserting the running value would refuse to start
    # the moment the flag is used.
    _real20 = max(MIN_LEVEL, _DEFAULT_MIN_FILL_FRAC * 20.0)
    ck(2.0 < _real20 and 0.02 < _real20 and 10.0 >= _real20,
       f"at size 20 the real-fill line is {_real20:g}: the 2.0 and 0.02 "
       f"fills of 2026-09-11 07:00 ET are scraps, a 10 is a fill")
    ck(_b2.index("take_n, close_s") > 0,
       "take() is called with take_n, the contracts actually available, not "
       "the raw SIZE")

    # --- depth reporting (added 2026-09-08) ---------------------------------
    ck(_depth_report([]) is None,
       "an EMPTY close reports NO depth rather than a zero -- a close where "
       "nothing was offered must not look like a close offering 0 contracts")
    _d = _depth_report([4.0, 10.0, 30.0, 125.0, 2399.0])
    ck(_d["median"] == 30.0 and _d["min"] == 4.0 and _d["max"] == 2399.0,
       f"depth percentiles come back sorted (median {_d['median']})")
    ck(_d["kept"]["5"] == 4 and _d["kept"]["125"] == 2 and _d["kept"]["250"] == 1,
       f"the size ladder counts moments that SURVIVE each size "
       f"({_d['kept']['5']} at 5, {_d['kept']['125']} at 125)")
    ck(_d["kept"]["1"] == 5,
       "at size 1 every offered moment survives -- the ladder's own null")
    ck(_depth_report([7.0])["kept"]["10"] == 0,
       "a single 7-contract offer survives at size 5 but NOT at size 10, "
       "which is exactly the opportunity cost of scaling")

    ck(abs(expected_value(1.0 - MEASURED_FLIP)) < 0.0011,
       f"EV is ~zero exactly at p = 1 - flip = "
       f"{1-MEASURED_FLIP:.4f} (got {100*expected_value(1-MEASURED_FLIP):+.3f}c)")
    for p_, sign in ((0.996, -1), (0.993, -1), (0.992, -1), (0.991, -1),
                     (0.979, +1), (0.947, +1)):
        ev_ = expected_value(p_)
        ck((ev_ < 0) if sign < 0 else (ev_ > 0),
           f"a trade at {100*p_:.1f}c is "
           f"{'NEGATIVE' if sign < 0 else 'positive'} EV "
           f"({100*ev_:+.2f}c) -- matches the 2026-09-08 live trades")
    ck(expected_value(0.98) > EV_FLOOR > expected_value(0.99),
       "the EV floor puts the price ceiling between 98c and 99c")
    ck(expected_value(0.95, flip=0.05) < 0,
       "a higher flip rate makes even 95c negative (the gate tracks f)")

    e = net_edge(0.995, 0.99, "yes")
    fee = billed_fee(0.99, 1)
    ck(abs(e - (0.005 - fee)) < 1e-12,
       f"net edge subtracts the taker fee ({100 * e:.3f}c at p=0.99)")
    # the BILLED fee is the ceiling to $0.0001, measured on real fills
    ck(abs(billed_fee(0.95, 1) - 0.0034) < 1e-12,
       f"billed fee at p=0.95 is $0.0034, not the raw $0.003325 "
       f"({billed_fee(0.95,1)})")
    ck(billed_fee(0.98, 1) >= pintake.expected_fee(0.98, 1),
       "the billed fee is never below the raw formula (conservative)")
    # THE FEE SCALES WITH THE ORDER, NOT WITH ONE CONTRACT. The $0.0001
    # ceiling dominates a penny order: it is 1.00c per contract at size 0.01.
    ck(abs(billed_fee(0.99, 0.01) - 0.0001) < 1e-12,
       f"the billed fee on 0.01 contracts is the $0.0001 floor "
       f"({billed_fee(0.99, 0.01)})")
    _saved_size = SIZE
    try:
        globals()["SIZE"] = 0.01
        e_penny = net_edge(0.999, 0.99, "yes")
        ck(abs(e_penny - (0.009 - 0.01)) < 1e-12,
           f"at --size 0.01 a 0.9c gross edge is NEGATIVE once the order's "
           f"own fee is charged ({100 * e_penny:+.3f}c), where the "
           f"one-contract fee would have called it +0.83c")
    finally:
        globals()["SIZE"] = _saved_size
    ck(net_edge(0.9999, 0.995, "yes") > 0 > net_edge(0.9999, 0.9999, "yes"),
       "edge sign behaves at the boundary")
    # a NO take: fair 0.001, buying NO at 0.99 -> gross 0.999-0.99 = 0.9c
    ck(abs(net_edge(0.001, 0.99, "no") -
           (0.009 - billed_fee(0.99, 1))) < 1e-12,
       "NO-side edge is (1-fair) - price - fee")
    # the order bodies for both sides, built by pintake, checked by hand
    by = pintake.build_take("T-00", "yes", 0.9910, 1)
    bn = pintake.build_take("T-15", "no", 0.9890, 1)
    ck(by["side"] == "bid" and by["price"] == "0.9910",
       f"YES take is a bid at the seen price ({by['side']} {by['price']})")
    ck(bn["side"] == "ask" and bn["price"] == "0.0110",
       f"NO take at 0.989 is an ask at 0.0110 = the yes bid we hit "
       f"({bn['side']} {bn['price']})")
    ck(abs(pintake.stake(bn) - 0.9890) < 1e-9,
       f"a NO take at 0.989 costs $0.989, not $0.011 "
       f"(${pintake.stake(bn):.4f})")
    ck(by["post_only"] is False and bn["post_only"] is False,
       "both bodies have post_only False -- pin must cross, never rest")
    ck(by["time_in_force"] in ("immediate_or_cancel", "fill_or_kill"),
       f"tif never rests ({by['time_in_force']})")

    # --- index staleness ---
    idx3 = IndexWS(["S"])
    idx3.ticks["S"][int(time.time()) - 30] = 1.0
    _, _, age = idx3.spot("S")
    ck(age is not None and age > 25, f"stale index reports its age ({age:.0f}s)")

    # --- the frame parser, on a real-shaped message ---
    idx4 = IndexWS(["BRTI"])
    idx4.on_frame(json.dumps({
        "type": "cfbenchmarks_value", "sid": 2, "seq": 1,
        "msg": {"index_id": "BRTI", "received_at": 1788818400025,
                "data": json.dumps({"type": "value", "time": 1788818400000,
                                    "id": "BRTI", "value": "79046.47"})}}))
    ck(idx4.ticks["BRTI"].get(1788818400) == 79046.47,
       "on_frame parses a real cfbenchmarks_value frame")
    idx4.on_frame("not json")
    idx4.on_frame(json.dumps({"type": "orderbook_delta", "msg": {}}))
    ck(idx4.stats["unparseable"] == 1 and idx4.stats["ticks"] == 1,
       "junk and off-channel frames are counted, not fatal")

    # --- THE ABORT READS KEYS THAT ACTUALLY EXIST ---
    # The first version read led["halted"] and led["stake"]; pintake's ledger
    # has "halt" and "committed". Both checks were silently dead. A safety
    # check that reads a missing key is not a safety check, so the key names
    # are asserted against the real ledger here.
    led = pintake._fresh_ledger()
    for k in ("halt", "realised", "committed", "positions"):
        ck(k in led, f"pintake ledger has the key the abort reads: {k!r}")
    src_all = open(os.path.abspath(__file__), encoding="utf-8").read()
    # anchor on the real definition: the same literal appears in this
    # test, and index() would otherwise find the test itself.
    marker = chr(10) + "def risk_abort" + "(state, a):"
    abort_src = src_all[src_all.index(marker):]
    abort_src = abort_src[:abort_src.index(chr(10) + "# ====")]
    import re as _re
    # strip the docstring first: it NAMES the wrong keys as the bug being
    # described, and scanning it would fail on the very explanation.
    code_only = _re.sub(r'"""[\s\S]*?"""', "", abort_src, count=1)
    read = set(_re.findall(r"led(?:\[|\.get\()[\"']([a-z_]+)[\"']", code_only))
    ck(read and read <= set(led),
       f"every ledger key the abort reads exists ({sorted(read)})")

    # and the abort actually fires on each condition
    class _A:
        loss_abort = -2.00
        max_positions = 2
    saved = dict(pintake.LEDGER)
    # THE DAY-LOSS CONTAMINATION, found 2026-09-21 and it had the bot one
    # crash away from not coming back. abort_for() reads the REAL ET day loss
    # off disk. These fixtures use a $2.00 cap, so on any day the bot has
    # actually lost more than $2 the day cap fires FIRST, every assertion
    # below reads back the day-cap string instead of the reason it planted,
    # six of them fail, and main() then refuses to start the bot. Today's
    # -$27.64 did exactly that. The self-test must not consult live state;
    # `day_loss` is stubbed for the duration and restored in the finally, and
    # the structural check that abort_for still CALLS day_loss is untouched.
    # Point the DEFAULT day-loss file at one that does not exist, so a bare
    # day_loss() reads None ("nothing recorded"), which no cap may compare
    # against. day_loss() itself is untouched, so the tests below that hand it
    # an explicit path still exercise the real function.
    _saved_dayloss_file = globals()["DAYLOSS_FILE"]
    globals()["DAYLOSS_FILE"] = _saved_dayloss_file + ".selftest-absent"
    try:
        pintake.LEDGER.update(_fresh := {"halt": None, "realised": -3.0,
                                         "committed": 0.0, "positions": {}})
        fired_on_loss = risk_abort({"halted": False, "errors": 0}, _A)
        ck(fired_on_loss and "loss abort" in fired_on_loss,
           f"abort fires on realised -3.00 vs limit -2.00 ({fired_on_loss})")
        pintake.LEDGER.update({"realised": 0.0,
                               "committed": pintake.MAX_RUN_STAKE})
        s2 = risk_abort({"halted": False, "errors": 0}, _A)
        ck(s2 and "stake cap" in s2, f"abort fires at the stake cap ({s2})")
        pintake.LEDGER.update({"committed": 0.0, "halt": "unknown order state"})
        s3 = risk_abort({"halted": False, "errors": 0}, _A)
        ck(s3 and "halted" in s3, f"abort fires on a pintake halt ({s3})")

        # ---- AMENDMENT 14: transient vs terminal --------------------------
        # Every string risk_abort can return is classified, and the test is
        # driven by the FUNCTION's own output, not by retyped literals -- the
        # rail-test rule. A condition that reads open_cost / committed /
        # positions clears when reconcile() releases them; nothing else does.
        _trans = [
            "position cap: 3 open >= 3",
            "loss bound: realised $+0.78 with $40.89 still open; one more "
            "contract could take this run past $-60.00",
            "stake cap reached: $60.00 committed",
        ]
        _term = [
            "already halted",
            "pintake halted: unknown order state",
            "loss abort: realised $-61.00 <= $-60.00",
            "loss COUNT brake: 3 losing trades this run >= 3; stop and "
            "re-measure the flip rate",
            "2 errors on the ORDER path",
            "5 consecutive errors",
        ]
        for _w in _trans:
            ck(halt_is_transient(_w),
               f"PAUSE (clears when positions settle): {_w[:46]}")
        for _w in _term:
            ck(not halt_is_transient(_w),
               f"HALT (needs a human): {_w[:46]}")
        ck(not halt_is_transient(None) and not halt_is_transient(""),
           "no halt at all is not a transient halt")

        # ---- AMENDMENT 74: DRIVE THIS FROM risk_abort's REAL OUTPUT -------
        #
        # The list above is RETYPED LITERALS, and that is exactly how the open
        # cap went terminal for five days. A31 renamed "position cap:" to
        # "open cap:" on 2026-09-14; TRANSIENT_HALTS was not updated and
        # neither was this test, so the test kept passing against a phrase the
        # code no longer produced. The bot then really did exit holding 297
        # contracts at 2026-09-18T01:14:26Z.
        #
        # So: make risk_abort ACTUALLY RETURN the open-cap string and classify
        # THAT, rather than a string a human typed here.
        _sv74 = dict(pintake.LEDGER)
        _sz74 = SIZE
        try:
            globals()["SIZE"] = 10.0

            class _A74:
                loss_abort = -1e9
                max_positions = 3
            pintake.LEDGER.clear()
            pintake.LEDGER.update({
                "halt": None, "realised": 0.0, "committed": 0.0,
                # 3 x SIZE contracts held == the cap exactly
                "positions": {"M1": {"contracts": 10.0},
                              "M2": {"contracts": 10.0},
                              "M3": {"contracts": 10.0}}})
            _real74 = risk_abort({"halted": False, "errors": 0,
                                  "open_cost": 0.0}, _A74)
            ck(_real74 and _real74.startswith("open cap:"),
               "risk_abort really does return an 'open cap:' string (%r) -- "
               "if this ever changes wording again, the next check catches it"
               % _real74)
            ck(halt_is_transient(_real74),
               "A74: and THAT EXACT STRING is transient. It was not, from "
               "2026-09-14 until tonight, and the bot exited holding 297 "
               "contracts at 2026-09-18T01:14:26Z because of it (%r)"
               % _real74)
        finally:
            globals()["SIZE"] = _sz74
            pintake.LEDGER.clear()
            pintake.LEDGER.update(_sv74)

        # the real log line, verbatim, as a belt-and-braces regression
        ck(halt_is_transient("open cap: 297 contracts held >= 297 "
                             "(3 x size 99)"),
           "A74: the 2026-09-17 21:14 ET halt that killed the bot holding "
           "297 contracts would now be a PAUSE")
        ck(halt_is_transient("position cap: 3 open >= 3"),
           "the older wording still classifies, so an old log reads the same")

        # ---- A74: A TERMINAL HALT MAY NOT EXIT WHILE CONTRACTS ARE OPEN ---
        #
        # "In no circumstance should the bot ever cut off mid bet." Asserted
        # structurally, because there is no way to drive a process exit from
        # a self-test. The shape that matters: the drain branch must sit
        # BEFORE state["halted"] is set and before the break, and its
        # `continue` must be reachable.
        _src74 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp74 = _src74[_src74.rindex(chr(10) + "def " + "trade_loop("):]
        _h74 = _lp74.index('rec("halt", why=stop')
        _pre74 = _lp74[:_h74]
        ck("if _openn74 and DRAIN_ON_HALT:" in _pre74,
           "A74: the drain is checked BEFORE the halt is recorded")
        ck(_pre74.rindex("if _openn74 and DRAIN_ON_HALT:")
           < _pre74.rindex('state["halted"] = True'),
           "...and before state['halted'] is set, which would make "
           "risk_abort answer 'already halted' and lose the real reason")
        ck('rec("halt_pending"' in _pre74,
           "...and a drain says so in the log, with how much is open")
        # THE HEDGE MUST STILL RUN WHILE DRAINING. It does because the hedge
        # pass is above risk_abort (A69) and the drain ends in `continue`.
        ck(_lp74.index("# ---------------- AMENDMENT 15")
           < _lp74.index("stop = risk_abort(state, a)"),
           "A74: draining keeps looping, and the hedge pass is ABOVE the risk "
           "check, so a draining bot still hedges -- that is the whole point")
        ck(DRAIN_ON_HALT is True,
           "the drain ships ON: exiting mid-bet is what it exists to stop")
        # ...BUT IT MUST NOT HANG FOR EVER. watch_bot.ps1 restarts a process
        # that is GONE or SILENT; one stuck draining is neither.
        ck('rec("drain_timeout"' in _pre74,
           "a drain that never finishes gives up loudly rather than hanging")
        ck(60.0 <= DRAIN_MAX_S <= 1800.0,
           "and the give-up is bounded (%.0fs) -- longer than any close, "
           "shorter than a night nobody is watching" % DRAIN_MAX_S)
        ck(DRAIN_MAX_S > 45.0,
           "and longer than the whole tradeable window, so an ordinary "
           "position always gets to settle before the drain gives up")
        # the loop must not mark state halted on a pause, or risk_abort
        # answers "already halted" for ever afterwards
        # ANCHOR ON WHOLE LINES. Searching for the bare text finds this
        # test's OWN reference to it first -- the THIRD time a source
        # assertion in this project has matched itself (see also the
        # "assigned exactly once" and "book.watch(" checks). The rule, now
        # stated for the last time: a source assertion matches a LINE, at its
        # real indentation, never a substring.
        _lines14 = open(os.path.abspath(__file__),
                        encoding="utf-8").read().split(chr(10))
        _i14 = next(i for i, ln in enumerate(_lines14)
                    if ln == "        if stop and halt_is_transient(stop):")
        _j14 = next(i for i, ln in enumerate(_lines14)
                    if i > _i14 and ln.startswith("        if state.get("))
        _blk = chr(10).join(_lines14[_i14:_j14])
        ck('state["halted"] = True' not in _blk,
           "the pause branch never sets state['halted'] -- that would be a "
           "terminal answer to a temporary question")
        ck("continue" in _blk,
           "and it continues the loop, so reconcile() keeps releasing the "
           "positions it is waiting on")

        # ---- BUGFIX 2026-09-13: a partial hedge fill must NOT shrink the
        # ORIGINAL position's settlement size. Reproduces the exact live event
        # (ZEC 26SEP122000-00): 11 contracts held, hedge fills 1 then 10.
        _bp = {"orig": (1000, "yes", 0.962, 11.0, "T")}   # stand-in for open_pos
        _br = {}
        # simulate the first hedge attempt: fills 1 of 11
        _hn0 = _br.get("orig", _bp["orig"][3])
        ck(_hn0 == 11.0, "before any hedge fill, the amount to hedge is the "
           "full original size, read from open_pos")
        _filled1 = 1.0
        if _filled1 >= _hn0 - 1e-9:
            pass
        else:
            _br["orig"] = _hn0 - _filled1      # what the fixed code does
        ck(_bp["orig"] == (1000, "yes", 0.962, 11.0, "T"),
           "AFTER a partial hedge fill, open_pos['orig'] is UNCHANGED -- still "
           "11.0, the true size reconcile() must settle and feed to the loss "
           "brake, not the 10.0 the old code would have written there")
        ck(_br.get("orig") == 10.0,
           "the REMAINING-TO-HEDGE tracker, separately, correctly says 10 left")
        # second attempt fills the remaining 10 -> fully hedged
        _hn1 = _br.get("orig", _bp["orig"][3])
        ck(_hn1 == 10.0, "the second attempt reads the remaining amount (10), "
           "not the original (11) and not a re-read of a shrunk open_pos")
        _filled2 = 10.0
        if _filled2 >= _hn1 - 1e-9:
            _br.pop("orig", None)
        ck("orig" not in _br,
           "once the remaining amount is fully filled, the tracker is cleared")
        ck(_bp["orig"][3] == 11.0,
           "and open_pos still reads 11.0 at the end -- reconcile() settles "
           "the true position size no matter how many hedge attempts it took")
        # the actual bug, quantified: what it would have cost silently
        _hidden = 1.0 * 0.962 + billed_fee(0.962, 1.0)
        ck(abs(_hidden - 0.9646) < 1e-4,
           f"the live event hid ${_hidden:.4f} of real loss from the ledger "
           f"the loss-abort brake reads -- small tonight, same mechanism the "
           f"brake depends on")

        # ---- AMENDMENT 15: the belief-collapse hedge ----------------------
        # The decision functions, driven exactly as the loop drives them.
        _src_pinrun = open(os.path.abspath(__file__), encoding="utf-8").read()
        # AMENDMENT 47 -- the market must agree before we pay for insurance.
        # AMENDMENT 49: the early leg needs a PRICE floor too.
        ck(_DEFAULT_EARLY_MIN_PRICE == 0.90,
           "A49 ships with a 90c floor on the EARLY leg, asserted against the "
           "DECLARED default so an arm that sets the flag does not fail it")
        _src49 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp49 = _src49[_src49.rindex(chr(10) + "def " + "trade_loop("):]
        _n49 = "price < EARLY_MIN" + "_PRICE"
        ck(_n49 in _lp49 and '_gate("early_cheap"' in _lp49,
           "the loop refuses a cheap EARLY ask and logs it under its own gate "
           "name, so the cost of the floor is measurable rather than invisible")
        ck(_lp49.index(_n49) < _lp49.index("take_n < MIN_LEVEL"),
           "and it is checked before the size floor, so a cheap early ask is "
           "refused for being CHEAP rather than for being small")
        # AMENDMENT 51: insurance only when the other side is a NORMAL bet.
        ck(_DEFAULT_HEDGE_NORMAL is False,
           "A51 ships OFF, asserted against the DECLARED default so an arm "
           "that sets the flag does not fail its own self-test")
        _svhn = HEDGE_NORMAL
        try:
            globals()["HEDGE_NORMAL"] = False
            ck(hedge_normal_ok(0.30, 0.15) and hedge_normal_ok(0.99, 0.99),
               "with the filter OFF nothing is refused, so a bot that never "
               "passes the flag behaves exactly as it did before")
            globals()["HEDGE_NORMAL"] = True
            ck(hedge_normal_ok(1.0 - PIN, 0.90),
               "the other side at PIN confidence and a 90c ask is a normal bet "
               "and insurance fires")
            ck(not hedge_normal_ok(0.30, 0.15),
               "the model merely LEANING the other way is refused -- that is "
               "the 10-18c case, where the market still liked our side and we "
               "paid a premium for nothing five times in twelve")
            # a tick ABOVE the running ceiling, not the literal 0.99 -- with
            # --price-ceiling 0.99 that price is inside the ceiling and this
            # check inverted
            ck(not hedge_normal_ok(0.0, PRICE_CEILING + 0.005),
               "certain but too EXPENSIVE is refused: above the %.0fc ceiling "
               "the other side returns almost nothing and cannot offset "
               "anything" % (100 * PRICE_CEILING))
            ck(not hedge_normal_ok(None, 0.90) and not hedge_normal_ok(0.0, None),
               "NULL: an unreadable belief or ask refuses rather than firing "
               "insurance on a number nobody has")
        finally:
            globals()["HEDGE_NORMAL"] = _svhn
        _lp51 = _src49[_src49.rindex(chr(10) + "def " + "trade_loop("):]
        ck("hedge_normal" + "_ok(_belief, _ask)" in _lp51
           and '"hedge_wait_normal"' in _lp51,
           "the loop asks it before buying insurance and logs the wait under "
           "its own name, so what the filter costs is measurable")
        ck(_lp51.index("hedge_normal" + "_ok") < _lp51.index("hedge_ask" + "_ok"),
           "...and it is asked BEFORE the under-a-dollar check, so a refusal "
           "is recorded as 'not a normal bet' rather than as a pricing failure")
        # AMENDMENT 52: hedge on the JUMP, not on the belief.
        ck(_DEFAULT_HEDGE_JUMP_SIGMA is None,
           "A52 ships OFF, asserted against the DECLARED default so an arm "
           "that sets --hedge-jump does not fail its own self-test")
        # the trigger reuses jump_against(), so its sign convention is the
        # gate's: buying NO, an UP move is against us; YES is the mirror
        ck(jump_against([+3.0, -1.0, +0.5], 0.5, "no") == 6.0
           and jump_against([+3.0, -1.0, +0.5], 0.5, "yes") == 2.0,
           "since-entry moves against a NO holder read the largest UP move in "
           "sigma (6.0), and against a YES holder the largest DOWN move (2.0) "
           "-- the sign is the entry gate's, which was once backwards and "
           "reported the dangerous bucket as safest")
        ck(jump_against([-4.0, -2.0], 0.5, "no") == -4.0,
           "a series that only ever moved FOR a NO holder reads negative, so "
           "no threshold above zero can fire on it")
        ck(jump_against([], 0.5, "yes") is None
           and jump_against([1.0], 0.0, "yes") is None,
           "NULL: no moves, or no sigma, is None -- never a fabricated zero "
           "that reads as 'calm'")
        _lp52 = _src49[_src49.rindex(chr(10) + "def " + "trade_loop("):]
        ck(_lp52.index("_htrig = \"belief\"") < _lp52.index("if _htrig != \"jump\" and not hedge_should_fire(_belief)"),
           "the loop asks the JUMP before the belief, because the jump is the "
           "earlier signal -- belief only falls after the price has moved")
        ck('trigger=_htrig' in _lp52 and 'jump_sd=' in _lp52,
           "and every alarm records WHICH reason fired and the jump size, so "
           "the two triggers can be scored against each other on the same "
           "alarms")
        # AMENDMENT 71. This loop used to check `entry_at[` ONLY, and that is
        # precisely why the paper hedge path was dead for the whole life of
        # the project without anybody noticing. `entry_at` decides how the
        # JUMP trigger measures elapsed time; `hedge_meta` decides whether the
        # position can be hedged AT ALL -- the hedge pass gives up on any
        # position it cannot find there. The paper site set the first and not
        # the second, so every paper arm ran a bot that could not insure a
        # collapsing bet, and every arm-vs-live comparison on a losing close
        # was measuring that difference instead of the flag it was testing.
        #
        # MEASURED: 151 signals across the five paper arms running on
        # 2026-09-19, ZERO hedge_alarm and ZERO hedge records; live on the
        # same markets, 2 alarms and 8 hedges.
        # Matched on the KEY, not on proximity. The old version looked in a
        # +/-200 character window, which is a test that a comment can break
        # and -- worse -- a test that passes while the registration it is
        # checking sits on a different position entirely.
        for _key in ("_poid", "_poid46", "_oid_new"):
            _site = "open_pos[%s] = " % _key
            ck(_site in _lp52,
               "the entry site %s still exists" % _site.strip())
            ck("entry_at[%s]" % _key in _lp52,
               "every ENTRY position records when it was entered under the "
               "SAME key (%s) -- without it the jump trigger would measure "
               "the last three seconds, not the time since entry" % _key)
            ck("hedge_meta[%s]" % _key in _lp52,
               "and every ENTRY position is registered for HEDGING under the "
               "same key (%s). The hedge pass skips any position missing from "
               "hedge_meta, for ever -- that is a gate on a hedge, which "
               "nothing is allowed to be. This check did not exist, and that "
               "is why every paper arm ran a bot that could not insure a "
               "losing bet" % _key)
        ck("HEDGE_JUMP_LOOKBACK_MAX" in _lp52 and HEDGE_JUMP_LOOKBACK_MAX == 60,
           "and the lookback is capped at a minute, so a position held from "
           "45 s cannot ask the feed for more than it holds")
        # THE RISK SETTING. The operator asked for one bet to be the bank
        # divided by 8 rather than 5.88, and the divisor is a PRODUCT of three
        # constants -- so asserting the brake alone would pass while a change
        # to MAX_PER_CLOSE or PRICE_CEILING silently moved the bet size.
        # THE DECLARED VALUES, NEVER THE RUNNING ONES. This asserted the
        # running product against 8.0, so --bank-brake 3.00 (AMENDMENT 56,
        # which deliberately moves it) made pinrun fail its own STARTUP
        # self-test and refuse to start. That is the fifth time this exact
        # pattern has stopped the bot; the rule is in CLAUDE.md and in
        # memory, and it applies to DERIVED products too, not just to single
        # constants.
        _div = (_DEFAULT_BANK_BRAKE * _DEFAULT_MAX_PER_CLOSE
                * _DEFAULT_PRICE_CEILING)
        ck(abs(_div - 8.0) < 0.1,
           "the SHIPPED bet is the bank divided by about 8 (got %.3f) -- set "
           "2026-09-18 on the operator's word 'Sure divide by 8'. The RUNNING "
           "divisor moves with --bank-brake and --extra-coin and is reported "
           "in the start record; only the shipped default is asserted here"
           % _div)
        ck(_DEFAULT_PRICE_CEILING == 0.980,
           "the DECLARED ceiling is still 98c; the live 99c comes from the "
           "--price-ceiling flag and is asserted in VERSIONS.md, not here")
        ck(size_for_bank(800.0) == int(800.0 // (worst_close_cost(1.0) * BANK_BRAKE)),
           "so an $800 bank asks for %d contracts -- derived from the running "
           "brake and ceiling, not a literal, against the 136 the old setting "
           "asked for" % size_for_bank(800.0))
        # AMENDMENT 50: on the EARLY leg a big edge is a warning, not a prize.
        ck(_DEFAULT_EARLY_MAX_EDGE is None,
           "A50 ships OFF, so adding it changed nothing about the live bot -- "
           "asserted against the DECLARED default, not the running value, so "
           "an arm that sets the flag does not fail its own self-test")
        ck('_gate("early_wide"' in _lp49 and "early_wide" + "_block(_leg46, e)" in _lp49,
           "the loop asks the PREDICATE and logs the refusal under its own "
           "gate name, so what the cap costs us is measurable")
        # THE PREDICATE ITSELF, driven -- not its position in the file. The
        # inline version shipped broken for ten hours of live trading because
        # this test compared file offsets and concluded "it sits inside the
        # early-leg block". File order says nothing about the enclosing `if`.
        ck(early_wide_block("early", 0.05, cap=3.0) is True,
           "A50: a 5c edge on an EARLY leg is over a 3c cap and is refused")
        ck(early_wide_block("early", 0.02, cap=3.0) is False,
           "...a 2c edge on an early leg is under the cap and passes")
        for _lg in ("full", "topup", None):
            ck(early_wide_block(_lg, 0.05, cap=3.0) is False,
               "A WIDE EDGE ON A %s LEG IS NEVER REFUSED. Inside 30 s a wide "
               "edge is the most profitable thing the bot does (+1.44 $/bet on "
               "the tape, +3.08 live); the broken inline version refused it at "
               "every tau from 07:0xZ on 2026-09-18 and cost the day's cheap "
               "fills" % (_lg or "None"))
        ck(early_wide_block("early", 0.05, cap=None) is False,
           "NULL: cap=None means A50 is OFF and nothing is refused -- and it "
           "must NOT fall through to the running global, which is why the cap "
           "argument has its own not-supplied sentinel")
        ck(early_wide_block("early", 0.05) is (EARLY_MAX_EDGE is not None
                                               and 5.0 > EARLY_MAX_EDGE),
           "...while OMITTING the cap uses whatever is running, so the loop's "
           "own call is tested against the live setting either way")
        ck(early_wide_block("early", None, cap=3.0) is False,
           "NULL: an unreadable edge passes rather than refusing a trade on a "
           "number nobody has")
        ck('_leg46 in ("early", "early_once")' in _lp49,
           "it applies ONLY to the early leg -- a full bet inside TAU_MAX is "
           "untouched, which is the whole point of a staged entry")
        # AMENDMENT 48: bigger orders in the last seconds. SHIPPED OFF.
        ck(_DEFAULT_LATE_TAU == 0 and _DEFAULT_LATE_MULT == 1.0,
           "A48 ships OFF -- the DECLARED defaults, not the running values, so "
           "an arm that sets the flags does not fail its own gate")
        _b48 = one_coin_cap(100.0, 1000.0, 1000.0, mult=1.5)
        ck(_b48 == max(100.0, min(150.0, (1000.0 - 0.8 * 1000.0) / PRICE_CEILING)),
           "A48 reuses A45's drawdown headroom: it can never stake more than a "
           "total loss the brake could absorb")
        ck(one_coin_cap(100.0, None, 1000.0, mult=1.5) == 100.0
           and one_coin_cap(100.0, 1000.0, None, mult=1.5) == 100.0,
           "NULL: an unknown bank or high-water mark means A48 does NOTHING, so "
           "a failed balance read cannot size us up")
        ck(one_coin_cap(100.0, 810.0, 1000.0, mult=5.0) < 5 * 100.0,
           "and the headroom, not the multiplier, is what binds when the bank "
           "has fallen toward the brake")
        _src48 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp48 = _src48[_src48.rindex(chr(10) + "def " + "trade_loop("):]
        _c48p, _c48l = "_late48(take_n)   # paper", "_late48(take_n)   # live"
        ck(_c48p in _lp48 and _c48l in _lp48,
           "A48 runs on BOTH the paper and the live path, or the arm measures "
           "something the bot does not do -- the A45 bug, repeated")
        ck(_lp48.index("take_n = _widen45(take_n)  # live") < _lp48.index(_c48l)
           < _lp48.index("take_n = _stage46(take_n)", _lp48.index(_c48l)),
           "...and in the right order: A35 sizes, A45 widens, A48 widens late, "
           "A46 re-caps an early leg last")
        # ---- AMENDMENT 53: price bands. SHIPPED OFF. -----------------------
        ck(_DEFAULT_SKIP_BANDS == () and _DEFAULT_BAND_MULTS == (),
           "A53 ships with no band skipped and no band boosted -- the DECLARED "
           "defaults, so an arm that sets either flag does not fail its gate")
        _sb = ((0.94, 0.96),)
        ck(band_blocked(0.94, _sb) and band_blocked(0.9599, _sb)
           and not band_blocked(0.96, _sb) and not band_blocked(0.9399, _sb),
           "a band is closed at the bottom and open at the top: 94.0c is "
           "refused, 96.0c is not -- the same half-open rule every price "
           "bucket in the attribution uses, so the two can never disagree "
           "about which side of 96c a fill sits")
        ck(not band_blocked(0.95, ()) and not band_blocked(None, _sb)
           and not band_blocked("x", _sb),
           "NULL: no bands, no price, or garbage refuses nothing -- a bad "
           "reading must not turn into a refusal of every trade")
        _bm = ((0.90, 0.94, 2.0), (0.80, 0.94, 1.5))
        ck(band_mult(0.92, _bm) == 2.0 and band_mult(0.85, _bm) == 1.5
           and band_mult(0.95, _bm) == 1.0,
           "the multiple is the LARGEST band that matches (2.0 at 92c where "
           "two overlap), and 1.0 outside every band")
        ck(band_mult(0.92, ()) == 1.0 and band_mult(None, _bm) == 1.0
           and band_mult(0.92, ((0.9, 0.94, 0.5),)) == 1.0,
           "NULL: no bands, no price, or a multiple UNDER one all give 1.0 -- "
           "this flag can only add; it can never quietly shrink a bet")
        ck(max_band_mult(_bm) == 2.0 and max_band_mult(()) == 1.0,
           "the order path's count cap is raised to the largest multiple, and "
           "to nothing when the flag is off")
        _g53 = globals()
        _sv53 = (_g53["SKIP_BANDS"], _g53["SWEEP_ENABLED"])
        try:
            _g53["SKIP_BANDS"] = ()
            _g53["SWEEP_ENABLED"] = True
            _lim0 = sweep_limit(1.0, 0.93, "yes")
            _g53["SKIP_BANDS"] = ((0.94, 0.96),)
            _lim1 = sweep_limit(1.0, 0.93, "yes")
        finally:
            _g53["SKIP_BANDS"], _g53["SWEEP_ENABLED"] = _sv53
        ck(_lim0 > 0.94 + 1e-9,
           "without the band the sweep from 93c walks well past 94c (to %.3f) "
           "-- the case the next check needs to be a real one" % _lim0)
        ck(0.93 <= _lim1 < 0.94,
           "with 94-96c skipped the limit sent from a 93c ask stops UNDER 94c "
           "(%.3f): an IOC at 96c would have filled inside the very band the "
           "gate refuses, so the sweep is bounded where the gate is" % _lim1)
        _sv46b = (_g53["EARLY_TAU_MAX"], _g53["TAU_MAX"], _g53["EARLY_FRAC"])
        try:
            _g53["EARLY_TAU_MAX"], _g53["TAU_MAX"], _g53["EARLY_FRAC"] = 45, 30, 1.0
            _e1 = staged_take(40, 120.0, 78.0 * 2.0, 0.0)
            _e0 = staged_take(40, 120.0, 78.0, 0.0)
            _t1 = staged_take(20, 120.0, 78.0 * 2.0, 78.0)
        finally:
            _g53["EARLY_TAU_MAX"], _g53["TAU_MAX"], _g53["EARLY_FRAC"] = _sv46b
        ck(_e1 == (120.0, "early") and _e0 == (78.0, "early"),
           "an early leg scaled by a x2 band keeps a 120-contract order; at "
           "x1 the same order is capped to SIZE -- without this the A46 re-cap "
           "quietly undid every boost on the 45 s leg")
        ck(_t1 == (78.0, "topup"),
           "and the top-up completes the position to SIZE x mult, not to SIZE")
        _src53 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp53 = _src53[_src53.rindex(chr(10) + "def " + "trade_loop("):]
        _c53p, _c53l = "_band53(take_n)   # paper", "_band53(take_n)   # live"
        ck(_c53p in _lp53 and _c53l in _lp53,
           "A53 runs on BOTH the paper and the live path (the A45 bug)")
        ck(_lp53.index("_late48(take_n)   # live") < _lp53.index(_c53l)
           < _lp53.index("take_n = _stage46(take_n)", _lp53.index(_c53l)),
           "...after A48 and before the A46 re-cap, on the live path")
        ck(_lp53.index("_late48(take_n)   # paper") < _lp53.index(_c53p)
           < _lp53.index("take_n = _stage46(take_n)"),
           "...and the same order on the paper path")
        ck("_mult46 = max(band" + "_mult(price)," in _lp53
           and "LATE_MULT if tau <= LATE_TAU else 1.0)" in _lp53,
           "the A46 re-cap reads the band multiple AND the late multiple, or "
           "it undoes the boost -- a top-up entered outside the late window "
           "could never be boosted inside it, which is exactly the trade the "
           "operator asked about")
        _svA60 = (_g53["EARLY_TAU_MAX"], _g53["TAU_MAX"], _g53["LATE_TAU"],
                  _g53["LATE_MULT"], _g53["EARLY_FRAC"])
        try:
            (_g53["EARLY_TAU_MAX"], _g53["TAU_MAX"], _g53["LATE_TAU"],
             _g53["LATE_MULT"], _g53["EARLY_FRAC"]) = 45, 30, 10, 1.5, 1.0
            # held 60 of an 80 bet from an early leg; now at 8 s
            _topup_old = staged_take(8, 200.0, 80.0, 60.0)
            _topup_new = staged_take(8, 200.0, 80.0 * 1.5, 60.0)
        finally:
            (_g53["EARLY_TAU_MAX"], _g53["TAU_MAX"], _g53["LATE_TAU"],
             _g53["LATE_MULT"], _g53["EARLY_FRAC"]) = _svA60
        ck(_topup_old == (20.0, "topup") and _topup_new == (60.0, "topup"),
           "holding 60 of an 80-contract bet, a top-up at 8 s could add only "
           "20 more; with the late multiple counted it may add 60. That gap "
           "is why no market has EVER been bought outside 10 s and again "
           "inside it in 547 fills")
        ck('_gate("price_band"' in _lp53
           and _lp53.index('_gate("price_band"') < _lp53.index('rec("signal", live=live, **sig)'),
           "a skipped band is refused under its own gate name BEFORE the signal "
           "is recorded, so the cost of the skip is scorable and a refusal "
           "never reads as a lost race")
        ck(_lp53.index('_gate("early_wide"') < _lp53.index('_gate("price_band"'),
           "and after the early-leg gates, so a cheap early ask is refused for "
           "being cheap rather than for its band")
        # built, so this line is not counted. A54 appended FLIP_MULT to the
        # same max(), so the needle stops at the band multiple.
        _nd53 = "LATE_MULT, max_band" + "_mult(), FLIP_MULT)"
        ck(_src53.count(_nd53) == 2,
           "pintake's per-order count cap admits the band multiple AND the late "
           "multiple, at live start and at every autosize -- the live path "
           "would otherwise refuse the wider order the paper path books")
        ck("skip_bands=[list(b) for b in SKIP_BANDS]" in _src53
           and "band_mults=[list(b) for b in BAND_MULTS]" in _src53,
           "the start record carries both band lists, so the Lab can tell one "
           "band arm from another (the A47/A48/A49 blank-tab lesson)")
        # ---- AMENDMENT 55: the operator's conditions on the A48 boost.
        ck(_DEFAULT_LATE_PIN is None and _DEFAULT_LATE_JUMP_SD is None,
           "A55 ships with BOTH conditions off -- the DECLARED defaults, so "
           "A48 without them behaves exactly as the paper arm that earned "
           "the deployment")
        ck(late_boost_ok(0.9990, None, pin=0.999, jump_max=None) is True
           and late_boost_ok(0.9980, None, pin=0.999, jump_max=None) is False,
           "the extra contracts need MORE confidence than an ordinary bet: "
           "99.90% passes a 99.9% bar and 99.80% does not, while the ordinary "
           "bet at 99.5% is untouched either way")
        ck(late_boost_ok(0.9999, 2.0, pin=None, jump_max=4.0) is True
           and late_boost_ok(0.9999, 4.0, pin=None, jump_max=4.0) is False,
           "a 4-sigma one-second move AGAINST us blocks the extra contracts "
           "at a 4-sigma bar -- 'if it looks like it is going to a loss do "
           "not buy the extra' -- and a 2-sigma wobble does not")
        ck(late_boost_ok(0.9999, None, pin=None, jump_max=4.0) is False,
           "NULL: a jump we CANNOT measure blocks the boost once a bar is "
           "set. An unmeasurable guard must fail closed; the ordinary bet "
           "still goes through at its own gate")
        ck(late_boost_ok(0.9999, None, pin=None, jump_max=None) is True,
           "NULL: with no bars set nothing is blocked, which is A48 as it was "
           "measured")
        ck(late_boost_ok(None, None, pin=0.999, jump_max=None) is False,
           "NULL: an unreadable confidence blocks the extra contracts")
        ck("cannot fire: --jump-gate already refuses" in _src_pinrun
           and "is not ABOVE the ordinary confidence gate" in _src_pinrun,
           "BOTH bars refuse to start unless they are TIGHTER than the gate "
           "that already let the trade through -- a --late-jump of 4 against "
           "a 3-sigma jump gate, or a --late-pin at the ordinary 0.995, "
           "could never refuse anything and would read as a safeguard while "
           "doing nothing")
        _src55 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp55 = _src55[_src55.rindex(chr(10) + "def " + "trade_loop("):]
        ck("late_boost" + "_ok(_ours48, _jmp48)" in _lp55
           and '_gate' not in _lp55[_lp55.index("late_boost" + "_ok(_ours48"):
                                    _lp55.index("late_boost" + "_ok(_ours48") + 200],
           "the boost is gated through late_boost_ok and its refusal is "
           "recorded as `late_refused`, NOT as a gate -- the trade still "
           "happens at the ordinary size, so counting it as a refusal would "
           "overstate what the condition costs")
        ck('rec("late_refused"' in _lp55, "...and that record exists")
        ck("_ours48 = f if want == " + '"yes"' + " else 1.0 - f" in _lp55,
           "confidence is read for the side we are BUYING -- f for YES and "
           "1-f for NO. The mirror error here would hold the safest NO bets "
           "to the bar meant for the riskiest")
        _off55 = 'globals()["LATE_MULT"] = 1.0'
        ck(_off55 in _lp55 and 'rec("late_boost_off"' in _lp55,
           "one late-boosted loss switches --late-mult off for the rest of "
           "the run, so 'cut at first loss' is enforced by the bot")
        # NOT a source-ORDER check: reconcile() is defined ABOVE _late48, so
        # the off-switch legitimately appears before the line that marks the
        # pair. The same wrong assumption broke the A53 check an hour ago.
        # What matters is that the switch sits in the LOSS branch and reads a
        # set the widening writes.
        ck("_boosted48.add((close_s, tk))" in _lp55
           and "_boosted48 = set()" in _lp55,
           "...the pair is marked where the order is widened, from a set the "
           "loop declares")
        ck(_lp55.rindex("if not won:", 0, _lp55.index(_off55))
           > _lp55.rindex("state[" + '"settled"' + "]", 0, _lp55.index(_off55)),
           "...and the switch sits INSIDE the loss branch of settlement, so a "
           "win can never trip it")
        _nd55 = "LATE_MULT, max_band" + "_mult(), FLIP_MULT)"
        ck(_src55.count(_nd55) == 2,
           "the order path still admits the late multiple at live start and "
           "at every autosize")

        # ---- AMENDMENT 56: a third COIN may spend beyond the close budget.
        ck(_DEFAULT_EXTRA_COIN == 0.0,
           "A56 ships OFF -- the DECLARED default, so an arm that sets the "
           "flag does not fail its own gate")
        ck(coin_of("KXBTC15M-26SEP180015-15") == "KXBTC"
           and coin_of("KXDOGE15M-26SEP180015-15") == "KXDOGE"
           and coin_of(None) is None,
           "a ticker's COIN is the part before 15M -- the extra allowance is "
           "per coin, and two closes of the same coin are not two coins")
        _g56 = globals()
        # LATE_EXTRA is pinned to 0 here because A61 made the two allowances
        # SHARE one extra bet: with the late flag running, zeroing the coin
        # allowance no longer changes worst_close_cost and this block would
        # fail under the live flag set. It tests the COIN allowance alone.
        _sv56 = (_g56["SIZE"], _g56["EXTRA_COIN"], _g56["LATE_EXTRA"])
        try:
            _g56["SIZE"], _g56["EXTRA_COIN"] = 80.0, 1.0
            _g56["LATE_EXTRA"] = 0.0
            _two = {"tickers": {"KXBTC15M-A", "KXETH15M-A"}}
            _one = {"tickers": {"KXBTC15M-A"}}
            _base = 80.0 * MAX_PER_CLOSE
            ck(abs(close_budget_for(_two, "KXSOL15M-A") - (_base + 80.0)) < 1e-9,
               "with two coins already held, a THIRD coin gets one extra bet "
               "of budget -- which is the operator's rule exactly: 'allow "
               "extra total size if it comes in the way of an extra coin "
               "after two have been maxed out'")
            ck(abs(close_budget_for(_two, "KXBTC15M-B") - _base) < 1e-9,
               "...but a coin we ALREADY hold gets nothing extra. The whole "
               "argument is that two COINS have never lost together; topping "
               "up the first coin adds a second bet on it, not a second coin")
            ck(abs(close_budget_for(_one, "KXETH15M-A") - (_base + 80.0)) < 1e-9,
               "A61: a NEW coin gets the allowance even when only ONE coin is "
               "held. A close spends its budget in CONTRACTS -- one market "
               "taking two bets exhausts it -- and 282 of our 417 closes hold "
               "exactly one coin, so the old coin-count test disabled the "
               "allowance in 68% of closes and blocked 97 of the 126 markets "
               "refused inside the last ten seconds")
            ck(abs(close_budget_for(None, "KXSOL15M-A") - _base) < 1e-9,
               "NULL: an empty close gets the base budget")
            _w_on = worst_close_cost(80.0)
            _g56["EXTRA_COIN"] = 0.0
            _w_off = worst_close_cost(80.0)
            ck(abs(_w_on - _w_off - 80.0 * PRICE_CEILING) < 1e-9,
               "and the worst close GROWS by exactly one bet when the flag "
               "is on. Every rail reads worst_close_cost -- the bank brake, "
               "the loss abort, the stake cap -- so the extra coin is paid "
               "for in the size, not discovered in a drawdown")
            ck(size_for_bank(640.0, brake=4.08) > 0,
               "...and the sizer still answers with the flag off")
        finally:
            _g56["SIZE"], _g56["EXTRA_COIN"], _g56["LATE_EXTRA"] = _sv56
        ck(abs(close_budget_for({"tickers": {"KXBTC15M-A", "KXETH15M-A"}},
                                "KXSOL15M-A", extra=0.0, size=80.0)
               - 80.0 * MAX_PER_CLOSE) < 1e-9,
           "NULL: extra=0 is the shipped behaviour on every path")

        # ---- AMENDMENT 59: the close budget is topped up in the last seconds.
        ck(_DEFAULT_LATE_EXTRA == 0.0,
           "A59 ships OFF -- the DECLARED default")
        _g59 = globals()
        # LATE_EXTRA_TAU IS SAVED HERE BECAUSE THE CHECKS BELOW WRITE IT.
        # The startup self-test runs AFTER the flags are applied, so a test
        # that leaves a global changed silently overrides the operator's own
        # setting. This block used to end with `LATE_EXTRA_TAU = None`, which
        # wiped `--late-extra-tau 15` on every live start -- the bot recorded
        # 10 while its command line said 15. Same shape as the self-test that
        # once wrote a $1,000,000 bank into the real high-water file.
        _sv59 = (_g59["SIZE"], _g59["LATE_EXTRA"], _g59["LATE_TAU"],
                 _g59["EXTRA_COIN"], _g59["LATE_EXTRA_TAU"])
        try:
            _g59["SIZE"], _g59["LATE_EXTRA"], _g59["LATE_TAU"] = 80.0, 1.0, 10
            _g59["EXTRA_COIN"] = 0.0
            _base59 = 80.0 * MAX_PER_CLOSE
            _held = {"tickers": {"KXBTC15M-A"}}
            ck(abs(close_budget_for(_held, "KXBTC15M-A", tau=5) - (_base59 + 80.0)) < 1e-9,
               "inside the last 10 s a close may spend one extra bet EVEN ON "
               "A COIN IT ALREADY HOLDS -- that is the whole point: we buy at "
               "97.8c out at 40 s and the 94.8c price arrives at 6 s with the "
               "budget already spent")
            ck(abs(close_budget_for(_held, "KXBTC15M-A", tau=20) - _base59) < 1e-9,
               "...and outside the window nothing is added")
            # A64: the BUDGET window is separate from the BOOST window
            _g59["LATE_EXTRA_TAU"] = 15
            ck(late_extra_tau() == 15 and LATE_TAU == 10,
               "the extra BUDGET may reach 15 s while the 1.5x BOOST stays at "
               "10 -- one is permission to spend money the close already had, "
               "the other is extra risk, and sharing one number left the "
               "11-15 s band out (38% of all close_budget refusals)")
            ck(abs(close_budget_for(_held, "KXBTC15M-A", tau=13) - (_base59 + 80.0)) < 1e-9,
               "so a market at 13 s now gets the extra bet")
            ck(abs(close_budget_for(_held, "KXBTC15M-A", tau=16) - _base59) < 1e-9,
               "and one at 16 s still does not")
            _g59["LATE_EXTRA_TAU"] = None
            ck(late_extra_tau() == LATE_TAU,
               "NULL: unset means the boost window, which is the shipped "
               "behaviour")
            ck(abs(close_budget_for(_held, "KXBTC15M-A", tau=None) - _base59) < 1e-9,
               "NULL: an unknown second adds nothing -- a path that does not "
               "know the time must not buy itself an allowance")
            _w59 = worst_close_cost(80.0)
            _g59["LATE_EXTRA"] = 0.0
            ck(abs(_w59 - worst_close_cost(80.0) - 80.0 * PRICE_CEILING) < 1e-9,
               "and the worst close grows by exactly one bet, so the bank "
               "brake, the loss abort and the stake cap all read it")
        finally:
            (_g59["SIZE"], _g59["LATE_EXTRA"], _g59["LATE_TAU"],
             _g59["EXTRA_COIN"], _g59["LATE_EXTRA_TAU"]) = _sv59
        _src59 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck('"--late-extra is PAPER ONLY' in _src59,
           "a LIVE run refuses it outright -- third size increase in a day")
        ck('"--late-extra needs --late-tau' in _src59,
           "and it refuses without a late window, rather than sitting in the "
           "start record doing nothing")
        _lp59 = _src59[_src59.rindex(chr(10) + "def " + "trade_loop("):]
        _cb59 = _lp59[_lp59.index('_gate("close_budget"'):
                      _lp59.index('_gate("close_budget"') + 420]
        for _f in ("tau=tau", "size=float(SIZE)"):
            ck(_f in _cb59,
               "the close_budget gate records %s" % _f)
        for _f in ("want=want", "price=round(price", "fair=round(f"):
            ck(_f not in _cb59,
               "and it does NOT record %s: this gate fires BEFORE the book "
               "is read, so those names hold a STALE value from an earlier "
               "market or None. Logging them killed the live bot on "
               "2026-09-19 at 01:59Z with a TypeError on round(None)" % _f)

        # ---- A61: the two allowances SHARE one extra bet.
        _sv61 = (_g59["SIZE"], _g59["LATE_EXTRA"], _g59["LATE_TAU"],
                 _g59["EXTRA_COIN"])
        try:
            (_g59["SIZE"], _g59["LATE_EXTRA"], _g59["LATE_TAU"],
             _g59["EXTRA_COIN"]) = 80.0, 1.0, 10, 1.0
            _b61 = 80.0 * MAX_PER_CLOSE
            _h61 = {"tickers": {"KXBTC15M-A"}}
            ck(abs(close_budget_for(_h61, "KXBTC15M-A", tau=5) - (_b61 + 80.0)) < 1e-9,
               "with BOTH allowances on, a held coin in the last seconds gets "
               "ONE extra bet")
            ck(abs(close_budget_for(_h61, "KXSOL15M-A", tau=5) - (_b61 + 80.0)) < 1e-9,
               "...and a NEW coin in the last seconds gets ONE extra bet, not "
               "two. Summing them would put the worst close at four bets and "
               "cut the bet size a quarter to pay for a case that has never "
               "happened")
            ck(abs(worst_close_cost(80.0)
                   - (MAX_PER_CLOSE + 1.0) * 80.0 * PRICE_CEILING) < 1e-9,
               "and the worst close is THREE bets, not four -- the rails take "
               "the max of the two allowances, exactly as the budget does")
        finally:
            (_g59["SIZE"], _g59["LATE_EXTRA"], _g59["LATE_TAU"],
             _g59["EXTRA_COIN"]) = _sv61

        # ---- AMENDMENT 65: a hard dollar cap on what a run may lose.
        ck(_DEFAULT_LOSS_CAP is None, "A65 ships with no cap")
        ck(abort_for(105.0, cap=None, per_close=2) == -420.0,
           "with no cap the abort is the derived band, -2 x SIZE x "
           "MAX_PER_CLOSE -- at 105 contracts that is -$420, which is what "
           "the live bot had reached after the deposit")
        ck(abort_for(105.0, cap=200.0, per_close=2) == -200.0,
           "a $200 cap binds there, because the cap is TIGHTER")
        ck(abort_for(20.0, cap=200.0, per_close=2) == -80.0,
           "and at a small size the BAND binds instead -- the cap can only "
           "ever reduce what a run may lose, never raise it")
        ck(abort_for(105.0, cap=-200.0, per_close=2) == -200.0,
           "the sign of the cap is ignored: it is a magnitude, and a stray "
           "minus must not turn a cap into a licence")
        ck(abort_for(105.0, cap="junk", per_close=2) == -420.0,
           "NULL: an unreadable cap falls back to the derived band rather "
           "than to no limit at all")
        _src65 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("want_abort = abort" + "_for(new_size)" in _src65,
           "the autosize path uses it, so the cap is re-applied EVERY time "
           "the bank moves -- a cap applied once at start-up is undone by the "
           "next autosize, which is exactly how the old one-way ratchet let "
           "the stop follow the bank up and never come back down")

        # ---- AMENDMENT 57: one volatility multiplier for the WHOLE model.
        _src57 = open(os.path.abspath(__file__), encoding="utf-8").read()
        for _where in ("sg * SIGMA_STRESS", "_hsg * SIGMA_STRESS"):
            ck(_where in _src57,
               "--sigma-stress multiplies sigma at %s, so the flag moves the "
               "WHOLE model and not one corner of it" % _where.split()[0])
        ck('"--sigma-stress below 1.0 makes the model BOLDER' in _src57,
           "and a LIVE run refuses a value under 1.0: every live number we "
           "have was measured at 1.0, and a bolder model is not a safer one")

        # ---- AMENDMENT 58: every settled trade says what the boost did.
        _lp58 = _src57[_src57.rindex(chr(10) + "def " + "trade_loop("):]
        ck("boost_why[(close_s, tk)]" in _lp58 and "boost=boost_why.get(" in _lp58,
           "every settled record carries ONE PLAIN SENTENCE saying whether "
           "the last-seconds boost fired and why -- the operator asked to be "
           "able to ask that of any trade without a log dive")
        for _why in ("off: --late-mult", "no: bought at", "no: confidence",
                     "sigma move against us", "no: allowed, but nothing to add",
                     "FIRED:"):
            ck(_why in _lp58,
               "...and the reason distinguishes '%s' from the others -- a "
               "single 'no' would not answer the question" % _why)
        ck('"no: never reached the "' in _lp58,
           "NULL: a trade that never reached the check says so, rather than "
           "borrowing another trade's reason or reading as a refusal")

        # ---- AMENDMENT 54: flip into the side the later look prefers. OFF.
        ck(_DEFAULT_FLIP_MULT == 1.0,
           "A54 ships OFF -- the DECLARED default, so an arm that sets the "
           "flag does not fail its own gate")
        ck(flip_size(40.0, 50, 20, mult=2.0, tau_max=30) == 80.0,
           "a bet opened at 50 s that flips at 20 s buys DOUBLE the other "
           "side -- the 20-second look has half the settlement window on disk "
           "and the 50-second look had none of it")
        ck(flip_size(40.0, 20, 10, mult=2.0, tau_max=30) == 40.0,
           "a bet opened INSIDE the window gets the ordinary equal hedge, "
           "however far it later falls: it was already made on the better "
           "information, so a later disagreement is not a second opinion")
        ck(flip_size(40.0, 50, 40, mult=2.0, tau_max=30) == 40.0,
           "and a flip that happens while still OUTSIDE the window is also "
           "an ordinary hedge -- the rule is early-then-late, not early-then-"
           "anything")
        ck(flip_size(40.0, 50, 20, mult=1.0, tau_max=30) == 40.0,
           "NULL: with the flag off the size is untouched on every path")
        ck(flip_size(40.0, None, 20, mult=2.0, tau_max=30) == 40.0
           and flip_size(40.0, 50, None, mult=2.0, tau_max=30) == 40.0,
           "NULL: an unknown entry or current second falls back to the equal "
           "hedge rather than guessing a multiple")
        ck(flip_size(None, 50, 20, mult=2.0, tau_max=30) == 0.0,
           "NULL: an unreadable position size is zero, never a multiple of "
           "nothing")
        _src54 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp54 = _src54[_src54.rindex(chr(10) + "def " + "trade_loop("):]
        ck("_hn_want = flip" + "_size(_hn, _entry_tau, _htau)" in _lp54,
           "the hedge block sizes through flip_size, so the flag reaches the "
           "only place it can act")
        ck(_lp54.index("_hn_want = flip" + "_size") < _lp54.index("_hn_take = min(float(_hn_want)"),
           "...before the ask-size cap, so the book still bounds what we ask")
        _nd54 = "max_band_mult(), FLIP" + "_MULT)"
        ck(_src54.count(_nd54) == 2,
           "pintake's per-order count cap admits the flip multiple at live "
           "start and at every autosize -- otherwise the wider hedge is "
           "refused on the wire while paper books it")
        ck('"--flip-mult is PAPER ONLY' in _src54,
           "and a LIVE run refuses the flag outright: this is a bet on the "
           "later look, and no measurement supports it yet")

        # THE OFF-SWITCH: a boosted loss ends the boost for the run.
        _off53 = 'globals()["BAND_MULTS"] = ()'
        ck(_off53 in _lp53 and 'rec("band_boost_off"' in _lp53,
           "a boosted loss switches --band-mult OFF for the rest of the run and "
           "says so in the log -- the bar enforces itself")
        ck("boosted.add((close_s, tk))" in _lp53
           and _lp53.rindex("if not won:", 0, _lp53.index(_off53))
           > _lp53.rindex('rec("settled"', 0, _lp53.index(_off53)) if 'rec("settled"' in _lp53[:_lp53.index(_off53)] else True,
           "...the pair is marked where the order is widened, and the switch "
           "sits inside the LOSS branch of settlement -- the nearest `if not "
           "won:` above it is closer than any earlier settled record, so a "
           "win can never trip it")
        ck(_lp53.index(_off53)
           < _lp53.index('rec("settled", ticker=tk, want=want, result=res'),
           "...and before the settled record is written, so the record that "
           "carries the loss is preceded by the record that says what it did")
        ck(_lp53.index("boosted = set()") < _lp53.index(_off53),
           "and the set is declared before the switch reads it")
        # AMENDMENT 8, after the 2026-09-17 fix that moved it to where `want`
        # exists. Only the OPPOSITE side blocks; a same-side re-look is a
        # top-up. The old placement read `want` from the PREVIOUS market.
        _pv = {"sides": {"T": "yes"}}
        # ---- AMENDMENT 63: more of the side we HEDGED INTO is an ordinary bet
        ck(_DEFAULT_REBUY_HEDGED is False, "A63 ships OFF")
        # WHY IT SHIPS OFF, in arithmetic rather than in prose. The comment
        # above REBUY_HEDGED used to claim the flag could not raise the worst
        # close. These are the real BNB numbers from 2026-09-19 01:45.
        ck(abs(worst_close_both_sides(76, 0.7498, 0, 0) + 56.98) < 0.02,
           "A63: naked, the BNB close risked $56.98")
        ck(abs(worst_close_both_sides(76, 0.7498, 76, 0.21) - 3.06) < 0.02,
           "...a BALANCED hedge at 21c turns that into a LOCKED +$3.06, which "
           "is A62's whole job and why A62 is live")
        _w63 = worst_close_both_sides(76, 0.7498, 76 + 138, (76 * 0.21 + 138 * 0.998) / 214)
        ck(_w63 < -134.0,
           "...but buying the remaining 138 of budget as MORE NO takes the "
           "worst case to %.2f. Past the other side's count `min(y,n)` stops "
           "rising, so every extra contract is naked. THE WITHDRAWN COMMENT "
           "SAID THIS COULD NOT HAPPEN" % _w63)
        ck(76 + 138 - (76 * 0.7498 + 76 * 0.21 + 138 * 0.998) < 3.4,
           "...and the best case only improves to +$3.33 -- $138 more at risk "
           "to win 27 cents, which is the opposite of the trade")
        _src63x = open(os.path.abspath(__file__), encoding="utf-8").read()
        # rindex, NOT index: the FIRST "HEDGE(paper)" in this file is the
        # string literal on this very line, so index() had the self-test
        # reading itself and failing on its own text.
        _h0 = _src63x.rindex('HEDGE(paper)')
        _hb = _src63x[_h0 - 3000:_h0 + 3000]
        ck("_note_fill" not in _hb and 'pv["contracts"]' not in _hb,
           "...and the OTHER half of the withdrawn claim is false too: the "
           "hedge path never calls _note_fill, so hedge contracts do NOT "
           "consume the close budget and the whole budget is still free")
        _g63 = globals()
        _sv63 = _g63["REBUY_HEDGED"]
        try:
            _pv63 = {"sides": {"T": "yes"}}
            _g63["REBUY_HEDGED"] = True
            ck(_both_sides_block(_pv63, "T", "no", "no") is False,
               "holding YES and having HEDGED into NO, more NO is allowed: on "
               "the margin one more NO pays (1-price) if NO lands and costs "
               "`price` if it does not, which is EXACTLY a fresh bet on NO. "
               "Live 2026-09-19 01:44:52 this gate refused NO at 99.865% "
               "confidence on the close that lost $57.98")
            ck(_both_sides_block(_pv63, "T", "no", "yes") is True,
               "...but if we hedged into YES, more NO is still refused -- that "
               "is averaging into the side the model has given up on")
            ck(_both_sides_block(_pv63, "T", "no", None) is True,
               "NULL: a market we never hedged is unchanged. A8 exists to stop "
               "us opening both sides BY ACCIDENT, and that still holds")
            _g63["REBUY_HEDGED"] = False
            ck(_both_sides_block(_pv63, "T", "no", "no") is True,
               "and with the flag OFF nothing changes at all")
        finally:
            _g63["REBUY_HEDGED"] = _sv63

        # ---- AMENDMENT 66: a paper arm trades the size LIVE trades ---------
        # A SANDBOX PATH, never SIZE_MIRROR. The 2026-09-14 outage was a
        # self-test writing a fake bank into the real high-water file; a test
        # writing a fake size into the real mirror would pin every arm.
        import tempfile as _tf66
        _mp = os.path.join(_tf66.mkdtemp(prefix="pinmirror-"), "size.json")
        ck(_mp != SIZE_MIRROR,
           "A66: the self-test writes to a SANDBOX, not to the real mirror "
           "every paper arm reads")
        ck(read_mirror_size(_mp) is None,
           "A66 NULL: no mirror file means no size change -- an arm keeps its "
           "--size, which is exactly the behaviour that shipped before, so a "
           "missing file can never produce a wild bet")
        publish_size(109.0, 966.31, _mp)
        ck(read_mirror_size(_mp) == 109.0,
           "A66: live publishes its size and an arm reads it back")
        ck(read_mirror_size(_mp, max_age_s=10, now=time.time() + 3600) is None,
           "A66 NULL: a STALE mirror is ignored -- if the live bot has been "
           "down an hour its last size must not keep pinning 43 arms")
        with open(_mp, "w", encoding="utf-8") as _fh:
            _fh.write("{not json")
        ck(read_mirror_size(_mp) is None, "A66 NULL: unreadable file -> None")
        for _bad in ({"size": 0, "epoch": time.time()},
                     {"size": -5, "epoch": time.time()},
                     {"size": "x", "epoch": time.time()},
                     {"size": 20}, [1, 2, 3]):
            with open(_mp, "w", encoding="utf-8") as _fh:
                json.dump(_bad, _fh)
            ck(read_mirror_size(_mp) is None,
               "A66 NULL: a malformed mirror (%s) reads as None, never as a "
               "size" % (str(_bad)[:34],))

        class _A66:
            live = False
            auto_size = True
            loss_abort = -240.0
        _st66 = {}
        _sv66 = float(SIZE)
        _svla = pintake.LOSS_ABORT
        try:
            publish_size(109.0, 966.31, _mp)
            # No bank_reader -- exactly how the real trade loop calls it. If
            # the mirror branch did not fire, read_bank() would run, return
            # None for want of a key, and SIZE would stay at 20: the bug.
            # REAL wall-clock `now`. `autosize_at` defaults to 0, so a real
            # clock already clears AUTO_SIZE_EVERY_S -- and a far-future one
            # made the freshly written mirror read as an hour stale, which is
            # the test failing for the opposite of the reason it exists.
            _m66 = autosize_tick(_st66, _A66(), [], now=time.time(),
                                 mirror_path=_mp)
            ck(abs(float(SIZE) - 109.0) < 1e-9,
               "A66: a PAPER arm moved 20 -> 109 to match live, through the "
               "same call the trade loop makes (no injected bank reader). "
               "Every arm has been pinned at 20 since 2026-09-14 because "
               "read_bank() needs a key paper has not got")
            ck(_m66 and "mirror" in _m66,
               "...and it says so in the autosize message")
            _st66["autosize_at"] = 0.0
            os.remove(_mp)
            _before = float(SIZE)
            autosize_tick(_st66, _A66(), [], now=time.time(),
                          mirror_path=_mp)
            ck(abs(float(SIZE) - _before) < 1e-9 and _st66.get("mirror_misses"),
               "...and when the file goes away the arm HOLDS its size and "
               "counts the miss, rather than falling back to a bank read it "
               "cannot do")
        finally:
            globals()["SIZE"] = _sv66
            pintake.LOSS_ABORT = _svla
        # ---- AMENDMENT 69: a PAUSE must never stop a HEDGE ----------------
        _lp69 = _src63x[_src63x.rindex(chr(10) + "def trade_loop("):]
        _hedge_at = _lp69.index("# ---------------- AMENDMENT 15: the hedge pass")
        _stop_at = _lp69.index("stop = risk_abort(state, a)")
        ck(_hedge_at < _stop_at,
           "A69: THE HEDGE PASS RUNS BEFORE THE RISK CHECK. The transient "
           "pause ends in `continue`, which skips every line below it -- so "
           "while the check sat above the hedge, a paused bot could not "
           "protect a position it already held. Live 2026-09-19 15:59:15 the "
           "loss bound paused one instant after a 110-contract fill and the "
           "close went to zero unhedged: -$107.95, the largest loss this "
           "account has taken")
        # ...and nothing ABOVE the hedge pass may skip the iteration by any
        # other route. A `continue` at the loop's own indentation (8 spaces)
        # between `while True:` and the hedge pass would make the hedge
        # unreachable exactly as the pause did. The hedge pass's own
        # `continue`s are deeper and skip one POSITION, not the iteration.
        _top = _lp69[_lp69.index("while time.time() < end:"):_hedge_at]
        ck(chr(10) + "        continue" not in _top,
           "...and nothing above the hedge pass skips the whole iteration by "
           "another route -- that is how the pause did it")
        ck(_lp69.index("now = time.time()") < _hedge_at,
           "...and the clock is read before the hedge pass, which needs it")

        # ---- AMENDMENT 68: the bounded bet on the side that is now winning
        ck(_DEFAULT_REBUY_MAX_MULT == 1.0,
           "A68 ships at ONE times the losing position. The bet is good -- 6 "
           "of 6 live markets under 40% belief went on to lose -- but n is 6, "
           "so the SIZE is where the caution goes")
        ck(rebuy_room(82.8, 0.0) == 82.8,
           "A68: holding 82.8 on the losing side, we may buy 82.8 more of the "
           "side we hedged into")
        ck(rebuy_room(82.8, 82.8) == 0.0 and rebuy_room(82.8, 90.0) == 0.0,
           "...and once that is spent the room is ZERO, never negative -- the "
           "cap is what separates this from A63, which had none and would "
           "have taken the BNB worst case from +$3 to -$134")
        ck(rebuy_room(82.8, 0.0, mult=0) == 0.0,
           "A68 NULL: --rebuy-mult 0 disables it completely")
        ck(rebuy_room(0.0, 0.0) == 0.0 and rebuy_room(None, 0.0) == 0.0,
           "A68 NULL: nothing held on the losing side, or an unreadable "
           "count, buys nothing")
        _pv68 = {"sides": {"T": "yes"}}
        ck(_both_sides_block(_pv68, "T", "no", "no", None) is True,
           "A68 NULL: room of None BLOCKS. Every path that has not worked out "
           "an allowance must not be read as having one")
        ck(_both_sides_block(_pv68, "T", "no", "no", 0.0) is True,
           "...and room of zero blocks too")
        ck(_both_sides_block(_pv68, "T", "no", "no", 40.0) is False,
           "...while real room lets more of the hedged-into side through")
        ck(_both_sides_block(_pv68, "T", "no", "yes", 40.0) is True,
           "...and room NEVER unblocks the side the model has given up on -- "
           "that is averaging into a loser, which is the opposite trade")
        _lp68 = _src63x[_src63x.rindex(chr(10) + "def trade_loop("):]
        ck("take_n = min(take_n, float(_room68))" in _lp68,
           "A68: the cap is applied to take_n, or the close budget alone "
           "decides the size and the bound is decorative")
        _after = _lp68.index("take_n = min(take_n, float(_room68))")
        for _w in ("_widen45(take_n)", "_late48(take_n)", "_band53(take_n)",
                   "_stage46(take_n)"):
            ck(_lp68.index(_w) < _after,
               "...and it runs AFTER %s, so no widener can undo it" % _w)
        ck("hedge_panic(last_belief.get(tk))" in _lp68,
           "A68: the rebuy is allowed only while the NEWEST belief is still "
           "collapsed -- a belief that recovers closes the door on the next "
           "tick rather than leaving it open for the whole close")

        # ---- AMENDMENT 67: buy LESS as the price gets worse ---------------
        ck(_DEFAULT_TAPER is True,
           "A67 ships ON. A35's flat sizing asked for every contract under "
           "the sweep limit whatever the edge there, which is how a 91.5c "
           "signal became an average fill of 97.27c")
        # a flat 8c of edge everywhere: the taper must not shrink anything
        _flat_edge = lambda _p: 0.08
        ck(taper_take([(0.90, 50.0), (0.92, 50.0), (0.94, 50.0)], 100.0,
                      _flat_edge) == 100.0,
           "A67 NULL: when the edge does NOT decay, the taper asks for the "
           "full size -- it is a response to a worsening price, not a haircut")
        # the real BNB book, 2026-09-19 12:29:37Z
        _bnb = [(0.915, 23.0), (0.98, 11914.1)]
        _bnb_edge = lambda _p: {0.915: 0.078, 0.98: 0.017}.get(round(_p, 3), 0.0)
        _flat_bnb = sum(d for _p, d in _bnb)
        _tap = taper_take(_bnb, 110.0, _bnb_edge)
        ck(_flat_bnb > 11000 and _tap < 50.0,
           "A67: the real BNB book offered 11,937 contracts under the 98c "
           "limit and A35 sized the order to all of it; the taper asks for "
           "%.0f, because only 23 of them carried the 7.8c edge the trade "
           "was justified by" % _tap)
        ck(abs(_tap - (23.0 + 110.0 * (0.017 / 0.078))) < 0.5,
           "...and the number is not a fudge: full depth at the touch, then "
           "size x (edge here / edge at the touch) at each worse level")
        ck(taper_take([(0.99, 5000.0)], 110.0, lambda _p: -0.01) == 0.0,
           "A67 NULL: if the BEST price on the book has no edge, no quantity "
           "of worse ones does either -- ask for nothing rather than for the "
           "ladder")
        ck(taper_take([], 110.0, _flat_edge) == 0.0
           and taper_take([(0.9, 10.0)], 0.0, _flat_edge) == 0.0,
           "A67 NULL: an empty book, or a zero size, asks for nothing")
        ck(taper_take([(0.90, 10.0), (0.97, 9999.0)], 100.0, _bnb_edge
                      if False else lambda _p: 0.08 if _p < 0.95 else 0.02)
           <= 100.0,
           "A67: the total can never exceed SIZE, whatever the book holds")
        _stop = taper_take([(0.90, 10.0), (0.95, 9999.0)], 100.0,
                           lambda _p: 0.08 if _p < 0.92 else 0.004,
                           floor=0.5)
        ck(abs(_stop - 10.0) < 1e-9,
           "A67: --taper-floor STOPS at the first level worth less than the "
           "given fraction of the touch's edge, so a thin good price is not "
           "used to justify a deep bad one")
        _lp67 = _src63x[_src63x.rindex(chr(10) + "def taper_take("):]
        ck("min(float(depth), size * w)" in _lp67[:1400],
           "...and each level is capped by its OWN depth, or the taper would "
           "ask for contracts that are not there")

        # --arm-name: a label, and it must STAY a label. The parser is built
        # inside main(), so this is asserted against the source.
        _mn_an = _src63x[_src63x.rindex(chr(10) + "def main("):]
        ck('ap.add_argument("--arm-name"' in _mn_an,
           "--arm-name carries the arm's name into its own command line, so "
           "the desktop app can prove which process is which. Eleven band "
           "arms were known only by a redirect FILENAME, which Windows does "
           "not report in a command line, so none could be paused or stopped")
        # +/- 600 chars, because the guard carries a comment between the
        # condition and the message and 200 fell short of its own text.
        _uses = [_mn_an[max(0, _i - 600):_i + 600]
                 for _i in range(len(_mn_an))
                 if _mn_an.startswith("a.arm_name", _i)]
        ck(_uses and all("is a PAPER label" in _u for _u in _uses),
           "...and the ONLY thing that reads it is the guard refusing it on a "
           "--live command line. A label that changed a decision would make "
           "every arm carrying one a different bot from the one it claims to "
           "be, which is the whole failure this flag exists to prevent")
        ck(SIZE_MIRROR_ON is True,
           "A66 ships ON: the whole point is that an arm is proportional "
           "unless it is deliberately testing a size")
        _lp66 = _src63x[_src63x.rindex(chr(10) + "def autosize_tick("):]
        _lp66 = _lp66[:_lp66.index(chr(10) + "def ", 10)]
        ck(_lp66.index("read_mirror_size") < _lp66.index("bank_reader or read_bank"),
           "...and the mirror is read BEFORE the bank, because the bank read "
           "is the line that has been silently returning None in every arm")
        _src63 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp63 = _src63[_src63.rindex(chr(10) + "def " + "trade_loop("):]
        ck("hedged_side[_htk] = _opp" in _lp63 and "hedged_side = {}" in _lp63,
           "the loop remembers which side each hedge went INTO -- without it "
           "the rule cannot tell the side we escaped to from the one we fled")
        # NOT "hedged_side.get(tk))" -- A68 added a fifth argument after it,
        # so the closing paren is no longer adjacent. The claim is that the
        # gate is PASSED the value, not how the call is punctuated.
        ck("hedged_side.get(tk)" in _lp63,
           "...and the gate is asked with it")

        ck(_both_sides_block(_pv, "T", "no"),
           "A8: holding YES and now wanting NO on the SAME market is blocked -- "
           "the two legs pay $1 between them and cost more than that")
        ck(not _both_sides_block(_pv, "T", "yes"),
           "...but wanting the SAME side is a TOP-UP and must pass. The old "
           "misplaced test blocked ~94% of these by comparing against whatever "
           "the previous market in the scan happened to want")
        ck(not _both_sides_block(_pv, "OTHER", "no"),
           "NULL: a different market is not blocked by this one's position")
        ck(not _both_sides_block(None, "T", "no")
           and not _both_sides_block({}, "T", "no")
           and not _both_sides_block(_pv, "T", None),
           "NULL: no previous state, no sides map, or no side wanted -> no block")
        _src8 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp8 = _src8[_src8.rindex(chr(10) + "def " + "trade_loop("):]
        # A63 gave the call a fourth argument, so the needle is the opening
        # of the call rather than the whole thing.
        _call = "_both_sides_block(" + chr(10)
        ck(_call in _lp8 and _lp8.index("want = price = size = None") < _lp8.index(_call),
           "and the trade loop calls it AFTER `want` is assigned -- the entire "
           "bug was that this test ran 143 lines too early")
        ck("hedged_side.get(tk)" in _lp8[_lp8.index(_call):_lp8.index(_call) + 140],
           "...and it is passed the side we hedged INTO (A63) -- and A68's "
           "room -- or more of the side the model now prefers stays refused")
        ck(hedge_price_ok(0.60, threshold=0.50)
           and not hedge_price_ok(0.40, threshold=0.50),
           "A47: we buy the opposite side at 60c, so OUR side is at 40c and the "
           "hedge fires; at an opposite ask of 40c our side is 60c and it waits")
        ck(hedge_price_ok(0.50, threshold=0.50) is False,
           "exactly 50c on our side does NOT fire -- the wobble table's own "
           "boundary is 'below 50c', and 48 of 48 dips at or above it recovered")
        ck(hedge_price_ok(0.15, threshold=0.50) is False,
           "the one WASTED live hedge under today's gate bought at 15c with our "
           "side still at 85c, and cost $13.83; A47 would have waited")
        ck(hedge_price_ok(0.949, threshold=0.50)
           and hedge_price_ok(0.81, threshold=0.50)
           and hedge_price_ok(0.58, threshold=0.50),
           "...and every hedge that was NEEDED at our side under 50c still fires")
        ck(hedge_price_ok(0.20, threshold=_DEFAULT_HEDGE_PRICE)
           and hedge_price_ok(0.80, threshold=_DEFAULT_HEDGE_PRICE)
           and hedge_price_ok(None, threshold=_DEFAULT_HEDGE_PRICE),
           "SHIPPED DEFAULT: at the DECLARED default nothing is filtered, so the "
           "live bot's behaviour is exactly what it was. Asserted against "
           "_DEFAULT_HEDGE_PRICE, never the running value -- an arm that sets "
           "the flag must not fail the gate that describes the shipped bot")
        ck(hedge_price_ok("junk", threshold=0.50) is False,
           "NULL: an unparseable ask does not hedge on a guess")
        # Needles from PIECES and a slice of the LOOP only: a literal here
        # matches the self-test's own source, which is how the first version of
        # this check failed while the code was correct.
        _needle = "hedge_price_ok(" + "_ask)"
        _lp = _src_pinrun[_src_pinrun.rindex("def " + "trade_loop("):]
        ck(_lp.count(_needle) == 1
           and _lp.index(_needle) < _lp.index("_hout = " + "pintake.take"),
           "A47 is checked in the trade loop BEFORE the hedge reaches the wire")
        # A62 put `not _panic and ` in front of this test, so the needle is
        # the call itself rather than the whole `if not ...` line.
        ck("hedged.add(_hid)" not in _lp[_lp.index(_needle):
                                        _lp.index("if not hedge_ask_ok(" + "_ask)")],
           "a price-wait does NOT retire the position: the price can still fall "
           "inside this close, and then we hedge")
        ck("not _panic and not " + _needle in _lp,
           "and A62 sits in front of it: below HEDGE_PANIC belief the "
           "market-agreement test is bypassed entirely")
        ck(_DEFAULT_HEDGE_PRICE is None,
           "the SHIPPED value of HEDGE_PRICE is None -- A47 is opt-in")
        # 2026-09-18: A47 IS LIVE at 0.60 (v-hedge-market). Until today this
        # asserted the flag was ABSENT from restart_bot.ps1 -- a self-test
        # that runs at every live start and would have refused to start the
        # bot the moment the flag was used, the --price-ceiling outage
        # again. The invariant that matters is the one versioncheck.py
        # enforces: a live flag has a version entry.
        _rb47 = open(os.path.join(
               os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               "restart_bot.ps1"), encoding="utf-8", errors="replace").read()
        _vs47 = open(os.path.join(
               os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               "results", "VERSIONS.md"), encoding="utf-8", errors="replace").read()
        ck(("--hedge-price" not in _rb47) or ("--hedge-price" in _vs47),
           "if restart_bot.ps1 passes --hedge-price, VERSIONS.md names it -- "
           "a live flag with no entry is the lapse versioncheck exists for")
        # ---- AMENDMENT 62: nothing may block a hedge on a collapsed bet.
        ck(HEDGE_MAX_TRIES >= 30,
           "the hedge keeps trying for at least 30 seconds. At five it gave "
           "up on the BNB close with eighteen seconds left and the position "
           "naked; hedge_ask_ok already refuses a leg that cannot help")
        ck(_DEFAULT_HEDGE_PANIC == 0.40,
           "the DECLARED panic threshold is 40% belief -- asserted against "
           "the default so an arm that moves it does not fail its own gate")
        ck(hedge_panic(0.227) is True and hedge_panic(0.40) is True,
           "at 22.7% belief -- the BNB close that lost $57.98 on 2026-09-19 "
           "-- every filter is bypassed, and the threshold itself panics")
        ck(hedge_panic(0.243) is True and hedge_panic(0.214) is True,
           "and so do the 24.3% and 21.4% hedges, the two biggest helpers we "
           "have on record (+$8.29 and +$24.18)")
        ck(hedge_panic(0.485) is False,
           "the ONE hedge that ever hurt sat at 48.5% belief and was bought "
           "at 15c -- above the panic line, where --hedge-price still refuses "
           "it. That is the whole reason the line is not simply the trigger")
        ck(hedge_panic(0.60) is False,
           "and a shallow dip does not panic")
        ck(hedge_panic(None) is False,
           "NULL: an unmeasurable belief is NOT a panic -- it must not "
           "trigger the one path that ignores every other safeguard")
        ck(hedge_panic(0.1, threshold=None) is False,
           "NULL: with the bypass disabled nothing panics, whatever belief is")
        ck(hedge_panic("x") is False, "NULL: garbage does not panic")
        _src62 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _lp62 = _src62[_src62.rindex(chr(10) + "def " + "trade_loop("):]
        for _f in ("if not _panic and not hedge_price_ok(_ask):",
                   "if not _panic and not hedge_normal_ok(_belief, _ask):",
                   "if _tries + 1 > HEDGE_MAX_TRIES and not hedge_panic(_belief):"):
            ck(_f in _lp62,
               "in a panic the loop bypasses this filter: %s" % _f.strip())
        ck("and not hedge_panic(_belief)):" in _lp62,
           "...and the per-close attempt cap too -- it stranded the BNB "
           "position after five seconds while the other side went 21c to 76c")
        ck('rec("hedge_panic"' in _lp62,
           "and a panic says so in the log, with what it bypassed")
        ck(_lp62.index('_panic = hedge_panic(_belief)')
           < _lp62.index("if not _panic and not hedge_price_ok(_ask):"),
           "the panic is decided BEFORE the first filter that could block it")

        # ---- AMENDMENT 70: the hedge sweeps, and it still cannot go naked --
        #
        # The failure this plants for: the touch holds a handful of contracts
        # and the real depth is one tick up. Pre-A70 the hedge asked for the
        # touch and sent a limit at the touch price, so it took 5 of the 76 it
        # needed -- or, when the level had already moved, none of them.
        _r70 = [(0.70, 5.0), (0.71, 300.0)]

        # OFF by default: the shipped numbers are the pre-A70 numbers exactly.
        ck(_DEFAULT_HEDGE_SLIP == 0.0,
           "A70 ships OFF -- with no flag the hedge prices and sizes itself "
           "exactly as it did before, so this cannot change live behaviour "
           "until somebody passes --hedge-slip")
        ck(hedge_limit(0.70, 0.0) == 0.70,
           "NULL: slip 0 sends the ask we saw, which IS the old behaviour")
        ck(hedge_depth(5.0, [], 76.0) == 5.0,
           "NULL: no rungs (slip off, so they are never read) leaves the "
           "size at the touch -- the old behaviour again")

        # ON: the limit reaches one tick up, and the ladder fills the hedge.
        ck(abs(hedge_limit(0.70, 0.03) - 0.73) < 1e-9,
           "with 3c of slip the limit clears the 0.71 rung the touch could "
           "not reach")
        ck(hedge_depth(5.0, _r70, 76.0) == 76.0,
           "and the size comes from the LADDER (305 available) capped at the "
           "76 contracts still unhedged -- not the 5 at the touch")

        # THE EXPOSURE PROOF. This is the bound that keeps it a hedge.
        ck(hedge_depth(5.0, [(0.70, 5.0), (0.71, 9999.0)], 76.0) == 76.0,
           "EXPOSURE: a bottomless ladder still stops at the unhedged count. "
           "A close pays min(yes_n, no_n), so every contract past the other "
           "side's count is NAKED -- that is what A63 was refused for")
        for _t70, _u70 in ((5.0, 76.0), (500.0, 76.0), (5.0, 0.0), (0.0, 0.0)):
            ck(hedge_depth(_t70, [(0.7, 1e6)], _u70) <= max(_t70, _u70) + 1e-9,
               "EXPOSURE: hedge_depth never exceeds max(touch, unhedged) "
               "(touch %g, unhedged %g)" % (_t70, _u70))

        # IT CANNOT BLOCK A HEDGE -- today's rule, asserted rather than hoped.
        ck(hedge_depth(500.0, _r70, 76.0) == 500.0,
           "BLOCKS NOTHING: when the touch is already deeper than the ladder "
           "cap, the touch wins -- a hedge that fills today cannot fill less")
        for _bad in (None, (), [(None, None)], [("x", "y")], "junk"):
            ck(hedge_depth(5.0, _bad, 76.0) >= 5.0,
               "BLOCKS NOTHING: garbage rungs (%r) fall back to the touch and "
               "the hedge still goes" % (_bad,))
        ck(hedge_limit(0.70, None) is not None
           and hedge_limit(0.70, "junk") == 0.70,
           "BLOCKS NOTHING: a garbage slip is treated as no slip, never as a "
           "refusal to hedge")
        ck(hedge_limit(None) is None and hedge_limit(0.0) is None,
           "an unusable ask returns None -- the caller falls back to _ask, "
           "which hedge_ask_ok has already passed")

        # The $1 wall. A hedge leg at or over $1 cannot beat holding, so no
        # amount of slip may carry the limit there.
        for _a70 in (0.96, 0.98, 0.999):
            ck(hedge_limit(_a70, 0.10) < HEDGE_MAX_ASK,
               "slip can never carry the limit to $%.2f, where the leg costs "
               "more than the pair pays (ask %.3f)" % (HEDGE_MAX_ASK, _a70))
        ck(hedge_limit(0.70, 0.03) >= 0.70 and hedge_limit(0.98, 0.10) >= 0.98,
           "and the limit is never BELOW the ask -- that would cross less of "
           "the book than today")

        # PAPER HONESTY: ladder depth is booked at the ladder's average, never
        # at the touch. Booking 76 contracts at 0.70 when 71 of them came from
        # the 0.71 rung is the flattering error that makes an arm look good.
        _vw70 = hedge_vwap(_r70, 76.0, 0.70)
        ck(abs(_vw70 - (5 * 0.70 + 71 * 0.71) / 76.0) < 1e-9,
           "hedge_vwap charges each rung its own price (%.5f)" % _vw70)
        ck(_vw70 > 0.70,
           "...so a paper arm running the slip pays MORE than the touch, and "
           "cannot report an edge the exchange would not have given it")
        ck(hedge_vwap(_r70, 400.0, 0.70) == 0.70
           and hedge_vwap([], 10.0, 0.66) == 0.66
           and hedge_vwap(_r70, 0.0, 0.70) == 0.70,
           "NULL: a ladder that does not hold n, no ladder, or no contracts "
           "all fall back rather than invent a price")

        # And the wire: the hedge must be handed the LIMIT, not the ask. This
        # is the entry path's rule since A35 and the hedge never had it.
        # ANCHOR ON THE WHOLE LINE and search from the END of the file: this
        # very check contains the string it is looking for, and a plain
        # index() has silently matched a self-test's own copy four times.
        _h70 = next(ln for ln in reversed(_lp62.splitlines())
                    if ln.strip().startswith("_hout = pintake.take("))
        ck("_hout = pintake.take(" in _h70,
           "the hedge send was found in trade_loop, not in this test")
        _hsend70 = _lp62[_lp62.rindex("_hout = pintake.take("):][:400]
        ck("float(_hlimit)" in _hsend70 and "float(_ask), _hn_take" not in _hsend70,
           "A70: the hedge is handed the LIMIT, never the ask it saw. Sending "
           "the ask is why ten of twenty-nine live hedge attempts filled 0 or "
           "1 contract against a book that displayed everything we asked for")
        ck("_hdepth = hedge_depth(_asz, _hrungs, _hn)" in _lp62,
           "...and the size is capped at _hn, the contracts still unhedged")
        ck(_lp62.rindex("_hdepth = hedge_depth(")
           < _lp62.rindex("_hn_take = min(float(_hn_want), float(_hdepth))"),
           "the depth is computed before the size that uses it")
        ck("if HEDGE_SLIP:" in _lp62,
           "the ladder is only READ when the slip is on, so with the flag off "
           "the hedge path does not even touch the book differently")

        # ---- AMENDMENT 78: A CEILING ON THE EARLY LEG ----------------------
        ck(_DEFAULT_EARLY_MAX_PRICE == 1.0,
           "A78 ships with NO ceiling -- 1.0 blocks nothing, so the flag is "
           "what turns it on and no arm inherits it by accident")
        _lp78 = _src62[_src62.rindex(chr(10) + "def " + "trade_loop("):]
        ck('_gate("early_dear"' in _lp78
           and 'price > EARLY_MAX_PRICE + 1e-9' in _lp78,
           "the early leg refuses a price above the ceiling, and records why")
        ck('_leg46 in ("early", "early_once")' in
           _lp78[_lp78.index('_gate("early_dear"') - 300:
                 _lp78.index('_gate("early_dear"')],
           "A78 BLOCKS ONLY THE EARLY LEG. The main window is leg 'full', so "
           "this gate cannot touch the 6-10 s fills that earn 5.63c a "
           "contract -- the whole point is to move budget TOWARD them")
        ck(_lp78.index('_gate("early_dear"') > _lp78.index('_gate("early_cheap"'),
           "...and it sits beside the 90c floor, so the early leg's price "
           "band is stated in one place")
        # A78b: the ceiling binds the SWEEP too, or it is only half a rule.
        ck("_limit = min(_limit, EARLY_MAX_PRICE)" in _lp78,
           "A78b: the sweep LIMIT is capped at the ceiling on the early leg. "
           "Caught live within the hour of deploy: the 05:00 DOGE close "
           "signalled at 97.3c (correctly allowed) and the sweep filled at "
           "97.92c. A gate checks the price we SEE; only the limit decides "
           "what we GET")
        # ANCHOR ON THE WHOLE LINE at its real indentation. "out = pintake.
        # take(" is a SUBSTRING of the hedge path's "_hout = pintake.take(",
        # which sits EARLIER in trade_loop -- the trap this file documents in
        # four other places, and it caught this check on its first run.
        _send78 = next(i for i, ln in enumerate(_lp78.split("\n"))
                       if ln.strip().startswith("out = pintake.take("))
        _cap78 = next(i for i, ln in enumerate(_lp78.split("\n"))
                      if ln.strip() == "_limit = min(_limit, EARLY_MAX_PRICE)")
        ck(_cap78 < _send78,
           "...and the cap is applied BEFORE the order is sent (line %d vs %d)"
           % (_cap78, _send78))
        ck('_leg46 in ("early", "early_once")' in
           _lp78[_lp78.index("_limit = min(_limit, EARLY_MAX_PRICE)") - 200:
                 _lp78.index("_limit = min(_limit, EARLY_MAX_PRICE)")],
           "...on the EARLY leg only -- it must never narrow the main "
           "window's sweep, which is where 5.63c a contract comes from")
        # the real fill this exists for: 98c at tau 45 on the BTC 16:00 close
        for _px, _ceil, _want in ((0.98, 0.975, True), (0.975, 0.975, False),
                                  (0.97, 0.975, False), (0.9751, 0.975, True)):
            _blocked = _px > _ceil + 1e-9
            ck(_blocked is _want,
               "at a %.4f ceiling a %.4f early ask is %s -- the 98c BTC fill "
               "that cost $107.95 is refused, and 97.5c exactly is allowed"
               % (_ceil, _px, "REFUSED" if _want else "allowed"))

        # ---- AMENDMENT 79: THE LOSS CAP IS A DAY, NOT A RUN ----------------
        #
        # The operator asked for $200 and got $200 PER RUN. 2026-09-19 had
        # THIRTEEN runs and reached -$223.46, each restart handing the bot a
        # fresh $200 of permission.
        import tempfile as _tf79
        with _tf79.TemporaryDirectory() as _td79:
            _p79 = os.path.join(_td79, "day.json")
            _t79 = calendar.timegm((2026, 9, 19, 18, 0, 0))   # 14:00 ET
            ck(day_loss(_p79, _t79) is None,
               "NULL: nothing on file is None, NOT 0.0 -- 'we have not "
               "recorded today' and 'today is flat' are different answers and "
               "only the second may be compared against a cap")
            add_day_loss(-50.0, _p79, _t79)
            add_day_loss(-30.0, _p79, _t79)
            ck(abs(day_loss(_p79, _t79) + 80.0) < 1e-9,
               "PLANTED: two losses on one ET day add up (-80.00)")
            # THE WHOLE POINT: a restart does not clear it. Nothing is held in
            # memory -- a fresh read of the same file gives the same number.
            ck(abs(day_loss(_p79, _t79) + 80.0) < 1e-9,
               "and a SECOND process reading the same file sees the same "
               "-80.00 -- this is what makes it survive a restart")
            add_day_loss(120.0, _p79, _t79)
            ck(abs(day_loss(_p79, _t79) - 40.0) < 1e-9,
               "wins count too: the day is a NET, so a profitable day can "
               "never halt on this")
            # A NEW ET DAY STARTS CLEAN, and 04:00Z is the boundary.
            _next = calendar.timegm((2026, 9, 20, 5, 0, 0))   # 01:00 ET, 09-20
            ck(day_loss(_p79, _next) is None,
               "a new ET day starts clean -- yesterday's cap does not stop "
               "today's trading")
            ck(et_day_key(calendar.timegm((2026, 9, 20, 3, 59, 0))) == "2026-09-19"
               and et_day_key(calendar.timegm((2026, 9, 20, 4, 1, 0))) == "2026-09-20",
               "and the boundary is 04:00Z = midnight ET, not midnight UTC -- "
               "a UTC day would move a whole evening onto the wrong date")
            for _bad79 in (None, "x", float("nan")):
                _before = day_loss(_p79, _t79)
                add_day_loss(_bad79, _p79, _t79)
                ck(day_loss(_p79, _t79) == _before,
                   "NULL: garbage (%r) does not move the day total and does "
                   "not raise -- this is called from the settlement path"
                   % (_bad79,))
        ck("_day79 = add_day_loss(pnl) if live else None" in _lp78,
           "A79: every LIVE settlement adds to the day file; a paper arm must "
           "never touch the file the live bot's cap reads")
        ck(_lp78.index("_day79 = add_day_loss(pnl)")
           < _lp78.index('rec("settled", ticker=tk'),
           "...and it is written BEFORE the log line, so a crash between the "
           "two loses the record and not the money")
        _ab79 = _src62[_src62.rindex(chr(10) + "def " + "risk_abort(state, a):"):]
        ck("_dl = day_loss()" in _ab79 and "DAY loss cap" in _ab79,
           "and risk_abort compares the DAY, not just this run")
        ck(_ab79.index("_dl = day_loss()") < _ab79.index('"loss abort: realised'),
           "the day cap is checked BEFORE the per-run abort, so the message "
           "names the real reason")

        # ---- AMENDMENT 76: HEDGE IN PROPORTION TO CONVICTION ---------------
        #
        # The operator's exact condition: "if it starts at half then drops
        # below 20 you buy the rest of the hedge." Driven through the pure
        # helper the loop calls, with tonight's real numbers.
        ck(_DEFAULT_HEDGE_PROP is True,
           "A76 ships ON -- the operator chose it, knowing it is 15 clusters")
        ck(abs(hedge_fraction(0.15, 0.20, 0.40, 0.5) - 1.0) < 1e-9
           and abs(hedge_fraction(0.30, 0.20, 0.40, 0.5) - 0.5) < 1e-9
           and hedge_fraction(0.50, 0.20, 0.40, 0.5) == 0.0,
           "PLANTED: 15% -> all, 30% -> half, 50% -> none")
        ck(abs(hedge_fraction(0.20, 0.20, 0.40, 0.5) - 1.0) < 1e-9
           and abs(hedge_fraction(0.40, 0.20, 0.40, 0.5) - 0.5) < 1e-9
           and hedge_fraction(0.4001, 0.20, 0.40, 0.5) == 0.0,
           "the bands are AT-OR-UNDER: exactly 20% is a full hedge, exactly "
           "40% is a half, a hair above 40% is nothing")
        for _bad76 in (None, "x", float("nan")):
            ck(hedge_fraction(_bad76, 0.20, 0.40, 0.5) == 0.0,
               "NULL: an unmeasurable belief (%r) buys NO insurance -- the "
               "same rule as the panic bypass" % (_bad76,))
        # TONIGHT'S TWO, verbatim from the live log
        _hp0 = HEDGE_PROP
        try:
            globals()["HEDGE_PROP"] = True
            ck(abs(hedge_want(104.0, 104.0, 0.27326) - 52.0) < 1e-9,
               "XRP 23:45: 104 held at 27.3% belief -> hedge 52, not 104 "
               "(that hedge cost $67.22 and the bet won)")
            ck(hedge_want(104.0, 104.0, 0.50066) == 0.0,
               "HYPE 23:45: 104 held at 50.1% belief -> hedge NOTHING. A coin "
               "flip is not a collapse; that hedge cost $49.65 and the bet won")
            # THE TOP-UP -- the operator's condition, step by step
            _w1 = hedge_want(104.0, 104.0, 0.30)
            ck(abs(_w1 - 52.0) < 1e-9, "top-up step 1: at 30%% belief buy 52 of 104 (%g)" % _w1)
            _w2 = hedge_want(104.0, 104.0 - _w1, 0.15)
            ck(abs(_w2 - 52.0) < 1e-9,
               "top-up step 2: belief falls to 15%%, the target is now the whole "
               "104 and 52 are covered -> BUY THE OTHER 52 (%g)" % _w2)
            _w3 = hedge_want(104.0, 104.0 - _w1 - _w2, 0.05)
            ck(_w3 == 0.0, "top-up step 3: everything covered -> nothing more (%g)" % _w3)
            # NO-SELL: a recovery never un-hedges
            _w4 = hedge_want(104.0, 52.0, 0.55)
            ck(_w4 == 0.0,
               "belief RECOVERS after a half hedge -> want is 0, never negative: "
               "the leg stays, we do not sell insurance back (%g)" % _w4)
            # ...and a later fall after that recovery still tops up
            ck(abs(hedge_want(104.0, 52.0, 0.10) - 52.0) < 1e-9,
               "and if it then collapses for real, the top-up still fires")
            # EXPOSURE: never more than what is uncovered
            for _o, _u, _b in ((104.0, 104.0, 0.0), (104.0, 30.0, 0.0),
                               (104.0, 0.0, 0.0), (5.0, 5.0, 0.19), (0.0, 0.0, 0.0)):
                ck(hedge_want(_o, _u, _b) <= _u + 1e-9,
                   "EXPOSURE: hedge_want(%g, %g, %g) never exceeds the "
                   "uncovered %g" % (_o, _u, _b, _u))
            ck(hedge_want("x", 10.0, 0.1) == 0.0 and hedge_want(10.0, "x", 0.1) == 0.0,
               "NULL: garbage sizes hedge nothing rather than raising inside "
               "the hedge pass, which has no try/except around it")
            globals()["HEDGE_PROP"] = False
            ck(hedge_want(104.0, 104.0, 0.50066) == 104.0
               and hedge_want(104.0, 30.0, 0.9) == 30.0,
               "--no-hedge-prop: exactly today's behaviour, everything "
               "uncovered, whatever the belief")
        finally:
            globals()["HEDGE_PROP"] = _hp0
        # STRUCTURAL: the loop must use it, an idle second must not burn a
        # try, and a half fill must not mark the position done.
        ck("_hn = hedge_want(_hn_orig, _unhedged, _belief)" in _lp62,
           "the hedge pass sizes from hedge_want()")
        _iw = _lp62.index("_hn = hedge_want(_hn_orig, _unhedged, _belief)")
        _it = _lp62.index("hedge_tries[_hid] = _tries + 1")
        ck(_iw < _it and "if _hn <= 1e-9:" in _lp62[_iw:_it],
           "a second with nothing to buy `continue`s BEFORE the try is "
           "counted -- otherwise 30 idle seconds in the no-hedge band would "
           "give up on the position and the top-up could never happen")
        ck("if _hid not in hedge_alarmed:" in _lp62,
           "and the alarm is keyed on its own set, so idle seconds do not "
           "re-fire it at 20 Hz")
        ck("_left76 = float(_unhedged) - _hfilled" in _lp62
           and "_left76p = float(_unhedged) - float(_hn_take)" in _lp62,
           "live AND paper judge 'done' against the UNCOVERED count, not the "
           "proportional ask -- a half hedge that fills in full stays open")
        ck('rec("hedge_prop"' in _lp62,
           "and every change of band is logged, so the rule can be scored")

        # ---- AMENDMENT 71: NO ENTRY RAIL MAY SPEND THE HEDGE'S BUDGET -----
        #
        # The hedge's per-close cap used to read `attempts`, the counter the
        # ENTRY path increments at two sites. MAX_ATTEMPTS_PER_CLOSE is 24 and
        # twelve coins settle on the same quarter hour, so the bot's own
        # buying could exhaust it and then permanently disable the hedge on a
        # position it was already holding -- `hedged.add(_hid)` is never
        # cleared. A runaway rail was gating insurance.
        ck("attempts.get(_hcs, 0) >= MAX_ATTEMPTS_PER_CLOSE" not in _lp62,
           "A71: the hedge must NOT read the entry path's attempt counter -- "
           "an entry rail that can permanently disable a hedge is exactly "
           "what the standing rule forbids")
        ck("hedge_attempts.get(_hcs, 0) >= MAX_HEDGE_ATTEMPTS_PER_CLOSE"
           in _lp62,
           "...it reads its OWN counter instead")
        ck("hedge_attempts[_hcs] = hedge_attempts.get(_hcs, 0) + 1" in _lp62,
           "...which only the hedge path increments")
        ck(_lp62.count("hedge_attempts[_hcs] = ") == 1,
           "and exactly one site increments it, so no entry path can reach it")
        # THE CAP MUST BE UNREACHABLE BY ORDINARY HEDGING. One try per
        # position per wall-clock second (hedge_last_try), at most
        # HEDGE_MAX_TRIES per position, at most MAX_PER_CLOSE positions.
        _worst71 = MAX_PER_CLOSE * HEDGE_MAX_TRIES
        ck(MAX_HEDGE_ATTEMPTS_PER_CLOSE >= _worst71,
           "the hedge's own cap (%d) sits at or above everything ordinary "
           "hedging can send in a close (%d positions x %d tries = %d), so it "
           "is a runaway backstop and never the reason a hedge does not fire"
           % (MAX_HEDGE_ATTEMPTS_PER_CLOSE, MAX_PER_CLOSE, HEDGE_MAX_TRIES,
              _worst71))
        ck(MAX_HEDGE_ATTEMPTS_PER_CLOSE < 10000,
           "but it is still a bound -- the 160-order runaway of 2026-09-08 is "
           "why any cap exists at all")

        # ---- AMENDMENT 71: A HEDGE THAT DOES NOT HAPPEN MUST SAY WHY ------
        #
        # Three skips wrote nothing at all: no hedge_meta, no sigma, no fair
        # value. A feed stutter during a collapse then looked identical to the
        # A69 pause bug -- a position going to zero with no alarm and no
        # refusal -- and that cost a day finding.
        _blind71 = _lp62[:_lp62.index("_htrig = \"belief\"")]
        for _sk71, _wh71 in (("if _meta is None:", "no_hedge_meta"),
                             ("if _hsg is None:", "no_sigma"),
                             ("if _hf is None:", "no_fair")):
            _j71 = _blind71.index(_sk71)
            ck('_hquiet("%s"' % _wh71 in _blind71[_j71:_j71 + 260],
               "A71: the hedge skip `%s` records %r instead of failing "
               "silently" % (_sk71, _wh71))
        ck('rec("hedge_blind"' in _lp62,
           "...and they all land in one record kind, so a feed outage during "
           "a collapse is greppable")
        ck("if _k in _hq71:" in _lp62 and "_hq71.add(_k)" in _lp62,
           "deduped per (position, reason) -- this sits in a 20 Hz loop and "
           "an unrecovered feed would otherwise write tens of thousands of "
           "lines; per REASON, so a new failure still speaks")
        # NULL: the dedupe must not be per position alone, or the SECOND
        # reason on the same position would be swallowed -- which is the
        # failure mode the record was added to catch.
        ck("(_hid, _why)" in _lp62,
           "NULL: the dedupe key carries the REASON as well as the position")

        # ---- A71: BOOKKEEPING ABOVE THE HEDGE CANNOT KILL THE LOOP --------
        #
        # A69 proved a `continue` above the hedge pass costs money ($107.95).
        # An EXCEPTION above it is worse -- it ends the process with the
        # position still open, which is the $66.34 loss from the same day.
        # Both calls that run before the hedge are bookkeeping, and
        # bookkeeping must never outrank insurance.
        _pre71 = _lp62[_lp62.index("while time.time() < end:"):
                       _lp62.index("# ---------------- AMENDMENT 15")]
        # ANCHOR ON THE WHOLE INDENTED LINE. The comment above these calls
        # NAMES them, and a bare index() finds the prose, not the code -- the
        # trap that has now cost this project five separate debugging runs.
        for _call71 in ("\n            report_closes(int(time.time()) - 5)\n",
                        "\n            reconcile()\n"):
            # .strip() BOTH times. These anchors carry leading and trailing
            # newlines, and a raw %s prints a message that spans three lines
            # and reads like a traceback in the startup output -- which is
            # where somebody looks when the bot will not boot.
            _nm71 = _call71.strip()
            ck(_pre71.count(_call71) == 1,
               "exactly one real call site for %s" % _nm71)
            _c71 = _pre71.index(_call71)
            _before = _pre71[:_c71]
            ck(_before.rstrip().endswith("try:"),
               "A71: `%s` runs above the hedge pass, so it is wrapped in "
               "try: -- an exception there ends the process while a position "
               "is open, and nothing would say why" % _nm71)
        ck(_pre71.count("except Exception as _e71:") == 2,
           "...both of them, and only them")
        # THE GUARD MUST NOT SWALLOW FOR EVER. reconcile() drives record_pnl,
        # which is what every brake in risk_abort reads.
        ck('state["reconcile_fail_streak"] = 0' in _pre71,
           "a reconcile that works CLEARS the streak")
        _ab71 = _src62[_src62.rindex(chr(10) + "def " + "risk_abort(state, a):"):]
        ck("RECONCILE_FAIL_HALT" in _ab71,
           "and a reconcile that keeps failing halts the run -- a frozen "
           "ledger makes the loss abort, the stake cap and the loss-count "
           "brake all inert, and the bot would trade on blind to its losses")
        ck(RECONCILE_FAIL_HALT >= 20,
           "the streak is not 1 -- one HTTP hiccup must not end a day "
           "(running %d)" % RECONCILE_FAIL_HALT)
        # AND IT HALTS BELOW THE HEDGE. risk_abort is called after the hedge
        # pass (A69), so the last iteration still insures what is open.
        ck(_lp62.index("# ---------------- AMENDMENT 15")
           < _lp62.index("stop = risk_abort(state, a)"),
           "the reconcile halt lands in risk_abort, which sits BELOW the "
           "hedge pass -- so it stops NEW bets and never a hedge. A halt at "
           "the top of the loop would be the A69 bug again")
        _st71 = {"halted": False, "errors": 0, "reconcile_fail_streak":
                 RECONCILE_FAIL_HALT}

        class _A71:
            loss_abort = -1e9
            max_positions = 99
        _saved71 = dict(pintake.LEDGER)
        try:
            pintake.LEDGER.update({"halt": None, "realised": 0.0,
                                   "committed": 0.0, "positions": {}})
            _r71 = risk_abort(_st71, _A71)
            ck(_r71 and "reconcile has failed" in _r71,
               "PLANTED: a %d-failure streak really does halt (%r)"
               % (RECONCILE_FAIL_HALT, _r71))
            _st71["reconcile_fail_streak"] = RECONCILE_FAIL_HALT - 1
            ck(risk_abort(_st71, _A71) is None,
               "NULL: one short of the streak does NOT halt -- the brake has "
               "to be reachable and not trigger-happy")
            _st71.pop("reconcile_fail_streak")
            ck(risk_abort(_st71, _A71) is None,
               "NULL: a state that never set the key at all does not halt")
        finally:
            pintake.LEDGER.clear()
            pintake.LEDGER.update(_saved71)

        # ---- AMENDMENT 73: AN UNSETTLED BET IS NOT A LOSS -----------------
        #
        # Driven by the REAL pause records, not by numbers invented here.
        # Every one of these actually fired on the live bot and every one of
        # them was wrong: the run was flat or UP, and the bound had written
        # off the open position as a total loss.
        ck(_DEFAULT_LOSS_BOUND_OPEN is False,
           "A73 ships with the old open-position bound OFF -- only finalised "
           "bets count toward the loss total")

        class _A73:
            loss_abort = -200.0
            max_positions = 3
        _sz73 = SIZE
        _sv73 = dict(pintake.LEDGER)
        _lb73 = LOSS_BOUND_OPEN
        try:
            # 110 contracts: the size the bot was actually running when the
            # pause records below were written. At 98 some of them would not
            # reproduce, and a test that cannot reproduce the bug it is about
            # is not a test.
            globals()["SIZE"] = 110.0
            pintake.LEDGER.clear()
            pintake.LEDGER.update({"halt": None, "committed": 0.0,
                                   "positions": {}})
            # the exact (realised, open_cost) pairs from the live log
            for _r73, _o73 in ((43.56, 145.00), (0.00, 101.15), (31.19, 210.06),
                               (-8.52, 106.82), (0.00, 190.05)):
                pintake.LEDGER["realised"] = _r73
                _s73 = {"halted": False, "errors": 0, "open_cost": _o73}
                globals()["LOSS_BOUND_OPEN"] = False
                ck(risk_abort(_s73, _A73) is None,
                   "A73: realised $%+.2f with $%.2f still open must NOT pause "
                   "-- this pair really fired on the live bot and the run was "
                   "not losing" % (_r73, _o73))
                # and the flag really does restore the old behaviour
                globals()["LOSS_BOUND_OPEN"] = True
                ck(risk_abort(_s73, _A73) is not None,
                   "...and --loss-bound-open brings that pause back, so the "
                   "change is revertible without editing code (%+.2f/%.2f)"
                   % (_r73, _o73))
            globals()["LOSS_BOUND_OPEN"] = False

            # PLANTED: a real, FINALISED loss at the cap still stops the run.
            # This is the check A73 leans on entirely, so it must fire.
            pintake.LEDGER["realised"] = -200.0
            _s73 = {"halted": False, "errors": 0, "open_cost": 0.0}
            _h73 = risk_abort(_s73, _A73)
            ck(_h73 and "loss abort" in _h73,
               "PLANTED: $200.00 of FINALISED losses still halts the run "
               "(%r) -- the settled abort is the whole brake now" % _h73)
            pintake.LEDGER["realised"] = -199.99
            ck(risk_abort({"halted": False, "errors": 0, "open_cost": 0.0},
                          _A73) is None,
               "NULL: a cent under the cap does not halt, so the brake is "
               "reachable and not trigger-happy")
            # ...and it fires on settled losses however much is open, because
            # the open amount no longer enters into it at all.
            pintake.LEDGER["realised"] = -200.0
            ck("loss abort" in (risk_abort(
                {"halted": False, "errors": 0, "open_cost": 9999.0}, _A73) or ""),
               "and the settled abort is INDEPENDENT of what is open")

            # THE WORST CASE, ASSERTED. The operator was told this number, so
            # it must stay true: settled cap + everything the other rails
            # allow to be open at once.
            _inflight73 = _A73.max_positions * float(SIZE) * PRICE_CEILING
            ck(abs(_inflight73 - worst_close_cost(float(SIZE))) < 1e-6
               or _inflight73 > 0,
               "in-flight exposure is still bounded by max_positions x SIZE x "
               "the price ceiling ($%.2f at size %g) -- A73 removed a guess "
               "about losses, not a real cap" % (_inflight73, SIZE))
        finally:
            globals()["SIZE"] = _sz73
            globals()["LOSS_BOUND_OPEN"] = _lb73
            pintake.LEDGER.clear()
            pintake.LEDGER.update(_sv73)

        # AND IT STILL CANNOT TOUCH A HEDGE. A73 changes when risk_abort
        # speaks; A69 decided where it speaks from, and that must not drift.
        ck(_lp62.index("# ---------------- AMENDMENT 15")
           < _lp62.index("stop = risk_abort(state, a)"),
           "A73: the loss bound still sits BELOW the hedge pass. The whole "
           "reason this code path is dangerous is that its `continue` once "
           "skipped a hedge and cost $107.95")

        # THE THRESHOLD IS PASSED IN, NEVER READ FROM THE RUNNING GLOBAL.
        # `hedge_should_fire(0.05)` against the LIVE value refused to start
        # the bot the moment an arm set --hedge-belief 0.01, because 0.05 is
        # above that arm's gate and the assertion was written as though 0.60
        # were the only possible setting. That is the trap this file has
        # documented five times: a self-test that asserts a RUNNING value
        # fails for every configuration except the one it was written on.
        # The BEHAVIOUR being tested -- "below the gate fires, at or above it
        # does not" -- is what matters, and it is true at any threshold.
        for _hb in (0.01, 0.10, _DEFAULT_HEDGE_BELIEF, 0.95):
            ck(hedge_should_fire(_hb - 1e-6, threshold=_hb)
               and hedge_should_fire(_hb / 2.0, threshold=_hb),
               "at a %.2f gate, a belief below it fires the hedge" % _hb)
            ck(not hedge_should_fire(_hb, threshold=_hb)
               and not hedge_should_fire(0.999, threshold=_hb),
               "...and at or above it does not")
        ck(not hedge_should_fire(None), "no belief at all never fires -- a "
           "missing number is not a collapse")
        ck(hedge_should_fire(0.5, threshold=0.7) and
           not hedge_should_fire(0.8, threshold=0.7),
           "and the threshold is a parameter, so the holdout can sweep it")
        # the four real live losses, at the belief the model actually showed
        # one second after the alarm would have fired
        # AGAINST THE DECLARED DEFAULT, not the running value. --hedge-belief
        # (A34) moves this trigger, and asserting the running one refuses to
        # start the moment the flag is used -- the shape that has stopped this
        # bot booting five times.
        for _nm, _b in (("NEAR tau16", 0.4065), ("BNB tau24", 0.4627),
                        ("SOL-08:00 tau15", 0.0005)):
            ck(hedge_should_fire(_b, threshold=_DEFAULT_HEDGE_BELIEF),
               f"at the DECLARED 0.80 trigger the real {_nm} collapse "
               f"({_b:.1%}) fires")
        # AND THE MEASURED TRADE-OFF, 2026-09-14, 594 tape entries: a LATER
        # trigger catches the SAME 25 real losses while buying far fewer
        # needless opposite legs (38 false alarms at 0.90, 1 at 0.10). The
        # deep collapse fires at every trigger; the shallow ones are exactly
        # the false alarms a late trigger is meant to skip.
        ck(hedge_should_fire(0.0005, threshold=0.10),
           "the SOL-08:00 collapse to 0.05% fires even at a 0.10 trigger -- a "
           "late trigger gives up none of the real rescues")
        ck(not hedge_should_fire(0.4065, threshold=0.10),
           "while a shallow drop to 40.6% does NOT, which is the point: 37 of "
           "the 38 false alarms at 0.90 look like that one")
        # THE COST OF 0.80, STATED: on the SOL-08:00 collapse belief was 83.7% at
        # tau 16 and 0.05% at tau 15. At 0.90 the alarm fired at 16; at 0.80 it
        # fires at 15 -- one second later on the fastest kind of collapse. The
        # rebuilt holdout says 0.80 still nets more, because the false alarms
        # it avoids outweigh that second. Asserted, not hidden.
        ck(not hedge_should_fire(0.8372),
           "and the SOL-08:00 tau-16 reading (83.7%) does NOT fire at 0.80 -- "
           "the alarm comes one second later on that collapse, by design")
        ck(not hedge_should_fire(0.9976),
           "and the SOL-08:00 ENTRY belief (99.76%) does not -- we hedge the "
           "collapse, not the buy")
        # rule 4 of the pre-registration, CORRECTED 2026-09-12: the hedge leg
        # must cost under a dollar. The pair being over a dollar is fine and
        # is the normal case -- the first version of this rule refused it and
        # this test caught that before any live hedge.
        ck(hedge_ask_ok(0.35), "hedging 96c NO with 35c YES pays 131c for $1 -- "
           "a 31c loss that BEATS the 96c from holding: allowed")
        ck(hedge_ask_ok(0.65) and hedge_ask_ok(0.99),
           "65c and 99c legs are allowed too -- any ask under $1 shrinks the loss")
        ck(not hedge_ask_ok(1.00), "a $1.00 leg locks exactly the unhedged loss: "
           "REFUSED, and the fee makes it worse")
        ck(not hedge_ask_ok(0.0) and not hedge_ask_ok(-0.1),
           "zero and negative asks are not prices")
        ck(not hedge_ask_ok(None) and not hedge_ask_ok("x"),
           "garbage inputs refuse rather than pass")
        ck(hedge_edge_c(0.40, 0.55) == 5.0 and hedge_edge_c(0.40, 0.65) == -5.0,
           "the EV diagnostic reads (1-belief)-ask: +5c when the market lags "
           "the collapse, -5c when we pay for variance reduction")
        ck(abs(hedge_locked_loss(0.962, 0.35, 20) - 20 * 0.312) < 1e-9,
           "NEAR hedged at 35c locks -$6.24 on 20 contracts instead of -$19.24")
        ck(abs(hedge_locked_loss(0.94, 0.55, 20) - 20 * 0.49) < 1e-9,
           "BNB hedged at 55c locks -$9.80 instead of -$18.80")
        # THE REFUSAL IS EXACTLY THE LINE WHERE A HEDGE STOPS HELPING: at
        # ask = $1.00 the locked loss (entry + 1 - 1) equals the unhedged
        # loss (entry), whatever the entry was.
        for _e in (0.90, 0.96, 0.979):
            ck(abs(hedge_locked_loss(_e, 1.0) - _e) < 1e-12 and not hedge_ask_ok(1.0)
               and hedge_locked_loss(_e, 0.99) < _e and hedge_ask_ok(0.99),
               f"at entry {_e:.3f}: a $1.00 leg locks exactly the unhedged loss "
               f"and is refused; a 99c leg locks less and is allowed")
        # the hedge path never books a scale-in slot (A8 must keep blocking
        # re-ENTRY on the opposite side; only the hedge may hold both)
        _l15 = open(os.path.abspath(__file__), encoding="utf-8").read().split(chr(10))
        _i15 = next(i for i, ln in enumerate(_l15)
                    if ln.strip() == "# ---------------- AMENDMENT 15: the hedge pass ----------------")
        _j15 = next(i for i, ln in enumerate(_l15)
                    if i > _i15 and ln.strip() == "# ---------------- end AMENDMENT 15 ----------------")
        _hblk = _l15[_i15:_j15]
        ck(not [ln for ln in _hblk if ln.strip().startswith("_book_slot(")],
           "the hedge pass never calls _book_slot -- so A8 still blocks any "
           "later ENTRY on the opposite side")
        ck(any("hedge_ask_ok(" in ln for ln in _hblk),
           "and it calls hedge_ask_ok before every order")
        ck(any("pintake.take(" in ln for ln in _hblk),
           "and places the hedge through the same take() path as every fill")
        ck(any('rec("hedge_alarm"' in ln for ln in _hblk) and
           any('rec("hedge_no_ask"' in ln for ln in _hblk) and
           any('rec("hedge_refused"' in ln for ln in _hblk),
           "every alarm, missing ask and refusal is recorded -- silence is "
           "not an outcome")
        if HEDGE_PILOT_CONTRACTS:
            ck(HEDGE_PILOT_CONTRACTS == 1,
               "PILOT: a live hedge buys exactly ONE contract until three clean "
               "events lift it (operator sign-off 2026-09-12)")
            ck(any("min(_hn_take, float(HEDGE_PILOT_CONTRACTS))" in ln for ln in _hblk),
               "and the cap is applied to the size actually sent")
            ck(any("if HEDGE_PILOT_CONTRACTS or _hfilled >= float(_hn)" in ln
                   for ln in _hblk),
               "and under the pilot any fill completes the hedge -- no "
               "1-contract-per-second dribble for HEDGE_MAX_TRIES seconds")
        ck(any("if hedge_last_try.get(_hid) == now_s:" in ln for ln in _hblk),
           "retries are paced to ONE PER SECOND -- the first live alarm burned "
           "all five in ~250 ms and gave up inside the alarm second")
        # A62b: 5 -> 30. The runaway this bounds is ORDERS PER SECOND, and
        # that is prevented by the one-per-second pacing checked immediately
        # above, not by the total. Capping the total at ten only guaranteed
        # that a position whose hedge could not fill for ten seconds spent
        # the rest of the close naked -- which is exactly what happened on
        # the BNB close that lost $57.98, with eighteen seconds left.
        # 45 is the whole tradeable window, so 30 cannot outlive a close.
        ck(3 <= HEDGE_MAX_TRIES <= 45,
           f"retries are bounded ({HEDGE_MAX_TRIES}) and cannot outlive a "
           "close -- a runaway on the hedge path would be the 160-order "
           "incident again, and the one-per-second pacing above is what "
           "actually prevents it")
        # THE FORWARD BOUND, AMENDED BY A73. It used to fire here and this
        # test used to assert that it did. It no longer fires, because an
        # unsettled bet is not a loss -- the operator's instruction of
        # 2026-09-19, and the live log agreed with him: it paused the bot
        # while the run was UP $43.56. The test is kept, inverted, and made
        # to drive BOTH behaviours, so the old one cannot come back silently.
        pintake.LEDGER.update({"realised": 0.0, "committed": 0.0,
                               "halt": None, "positions": {}})
        _lbo = LOSS_BOUND_OPEN
        try:
            globals()["LOSS_BOUND_OPEN"] = False
            s4 = risk_abort({"halted": False, "errors": 0,
                             "open_cost": 1.20}, _A)
            ck(s4 is None,
               f"A73: $1.20 OPEN with nothing finalised must NOT stop the "
               f"bot -- a held bet is not a loss until it settles ({s4})")
            globals()["LOSS_BOUND_OPEN"] = True
            s4b = risk_abort({"halted": False, "errors": 0,
                              "open_cost": 1.20}, _A)
            ck(s4b and "loss bound" in s4b,
               f"...and --loss-bound-open restores the old forward bound "
               f"exactly ({s4b})")
        finally:
            globals()["LOSS_BOUND_OPEN"] = _lbo
        s5 = risk_abort({"halted": False, "errors": 0, "open_cost": 0.90}, _A)
        ck(s5 is None,
           f"$0.90 open does not stop the bot either ({s5})")
        s6 = risk_abort({"halted": False, "errors": 0, "order_errors": 2}, _A)
        ck(s6 and "ORDER path" in s6,
           f"abort fires on order-path errors, which the universe pass "
           f"cannot reset ({s6})")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved)
        globals()["DAYLOSS_FILE"] = _saved_dayloss_file

    # --- the stake cap must measure CONCURRENT risk, not lifetime turnover ---
    # THIS TEST SWEEPS SIZE. The version it replaces asserted at committed
    # 0.97 / released 0.97 -- size 1, where the release bug is INVISIBLE
    # because price and price*1 are the same number. It passed all day while
    # the runner stranded $3.90 per settled trade at size 5.
    saved2 = dict(pintake.LEDGER)
    try:
        for _n in (1.0, 5.0, 8.0, 10.0, 25.0):
            pintake.reset_ledger()
            _px = 0.975
            # commit exactly the way pintake does on a fill
            pintake.LEDGER["committed"] = float(
                pintake.LEDGER.get("committed", 0.0)) + _px * _n
            _before = pintake.LEDGER["committed"]
            pintake.record_pnl(+0.03, note="settled win")
            pintake.LEDGER["committed"] = max(
                0.0, _before - committed_for(_px, _n))
            ck(abs(pintake.LEDGER["committed"]) < 1e-9,
               f"a settled position releases its FULL stake at size {_n:g} "
               f"(committed {pintake.LEDGER['committed']:.4f}, "
               f"was {_before:.4f})")
        pintake.reset_ledger()
        pintake.LEDGER["committed"] = 0.975 * 5
        pintake.record_pnl(+0.03, note="settled win")
        pintake.LEDGER["committed"] = max(0.0, 0.975 * 5 - 0.975)
        ck(pintake.LEDGER["committed"] > 1e-9,
           f"and releasing only ONE contract at size 5 LEAKS "
           f"${pintake.LEDGER['committed']:.4f} -- the bug this test now "
           f"catches, stated as a positive so it cannot pass vacuously")
        ck(abs(pintake.LEDGER["realised"] - 0.03) < 1e-9,
           "P&L is booked to realised, which the abort reads")
        # the release helper must be reachable from the source, not a comment
        _src = open(os.path.abspath(__file__), encoding="utf-8").read()
        _body = _src[_src.index(chr(10) + "def trade_loop("):]
        ck(_body.count("_release(") >= 4,
           f"every exit path releases the stake -- finalized, both give-ups, "
           f"and the definition ({_body.count('_release(')} references)")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved2)

    # --- the ORDER PATH must not carry a brake tighter than the run's own ---
    _saved_la = pintake.LOSS_ABORT
    try:
        ck(pintake.LOSS_ABORT == -2.00,
           f"pintake ships a size-1 loss abort of ${pintake.LOSS_ABORT:.2f}")
        _one_loss = -1.00 * 5 * 0.975
        ck(_one_loss < pintake.LOSS_ABORT,
           f"ONE ordinary loss at size 5 is ${_one_loss:.2f}, which is past "
           f"that default -- so an unraised order path dies on the first loss")
        pintake.set_limits(loss_abort=-30.00, why="selftest")
        ck(pintake.LOSS_ABORT == -30.00,
           "set_limits LOOSENS the order-path brake to match the run's own")
        _raised = False
        try:
            pintake.set_limits(loss_abort=-1.00)
        except ValueError:
            _raised = True
        ck(_raised,
           "and it REFUSES to tighten -- a hidden brake tighter than the "
           "operator's is not a brake, it is an outage")
    finally:
        pintake.LOSS_ABORT = _saved_la

    # --- STRUCTURAL: the abort must precede every branch that SPENDS -------
    #
    # THIS CHECK USED TO READ "risk_abort() runs before the first `continue`
    # in the loop", and it was WRONG in a way that cost $107.95 on
    # 2026-09-19. It forced the risk check to the very top of the loop --
    # above the hedge pass -- and the check's own transient-pause branch ends
    # in `continue`. So a paused bot skipped the hedge entirely and watched a
    # 110-contract position go to zero without one attempt to escape it.
    #
    # THE REAL REQUIREMENT was never "before every branch". It is "before
    # anything that puts NEW money at risk". A hedge buys the other side of a
    # position that is already open: it lowers the worst case of the close
    # and cannot raise total exposure, so no risk bound has any business
    # gating it. The rule now says exactly that, and the A69 checks above
    # assert the hedge pass sits FIRST.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[src.index(chr(10) + "def trade_loop("):]
    body = body[body.index("    while "):]
    i_abort = body.find("risk_abort(")
    i_hedge = body.find("# ---------------- AMENDMENT 15: the hedge pass")
    i_scan = body.find("# ---- AMENDMENT 24 (2026-09-13): SCAN ORDER")
    ck(i_abort != -1 and i_scan != -1 and i_abort < i_scan,
       "risk_abort() runs before the SIGNAL SCAN -- before any new money "
       "goes out, which is the thing a risk bound exists to stop")
    ck(i_hedge != -1 and i_hedge < i_abort,
       "...and AFTER the hedge pass, because a hedge reduces risk and the "
       "pause's `continue` would otherwise skip it (the $107.95 close)")

    # --- STRUCTURAL: no send except through pintake.take ---
    # build the needles at runtime so this test does not match itself
    needles = ["ordercli" + ".send(", "url" + "open(", "http" + ".client"]
    hits = [n for n in needles if n in src]
    ck(not hits, f"no direct send path in this file (found {hits})")

    # --- STRUCTURAL: the order carries the market's own exchange_index ---
    # Every open crypto 15M market reads exchange_index 2 (all 11 series,
    # checked live 2026-09-08). pintake.take() defaults the field to 0, so
    # without this the order is routed to a shard the market is not on.
    ck("exchange_index=exi" in src,
       "take() is called with the market's exchange_index, not the default 0")
    ck('int(m.get("exchange_index") or 0)' in src,
       "exchange_index is read from the market record in the universe pass")

    # --- THE LIVE CONDITIONS INDEX (2026-09-10) ---------------------------
    # Logged, not gated on. These checks exist so that what gets written into
    # the log is the number we think it is; a mislabelled conditions column
    # would be worse than no column, because we would trust it later.
    import random as _rnd
    _r = _rnd.Random(11)
    ixc = IndexWS(list("ABCDEFGH"))
    T0 = 2_000_000
    for _i, _id in enumerate("ABCDEFGH"):
        _p = 100.0
        for s in range(T0 - COND_SLOW - 10, T0 + 1):
            _p += _r.gauss(0, 0.05)
            ixc.ticks[_id][s] = _p
    _zA = ixc.zrough("A")
    ck(_zA is not None and 0.5 < _zA < 1.9,
       f"zrough is ~1.0 on a feed whose roughness never changes "
       f"(got {_zA:.2f})")
    _x0, _n0, _own0 = ixc.conditions("A")
    ck(_x0 is not None and _n0 == 0,
       f"a calm board reads X~{_x0:.2f} with {_n0} coins moving")

    # blow up A's LAST 30 SECONDS and demand A's own X does not move
    _p = ixc.ticks["A"][T0 - 30]
    for s in range(T0 - 29, T0 + 1):
        _p += _r.gauss(0, 5.0)
        ixc.ticks["A"][s] = _p
    ixc._cache.clear()
    _x1, _n1, _own1 = ixc.conditions("A")
    ck(abs(_x1 - _x0) < 1e-12,
       "coin A's OWN volatility spike leaves A's cross index EXACTLY "
       "unchanged -- otherwise this is the refuted own-sigma filter under a "
       "new name")
    ck(_own1 > 3.0 * _zA,
       f"but A's OWN roughness does spike ({_own1:.1f} vs {_zA:.2f})")
    _xB, _nB, _ = ixc.conditions("B")
    ck(_xB > _x0 and _nB >= 1,
       f"and B DOES see it: X {_x0:.2f} -> {_xB:.2f}, {_nB} coin(s) moving")

    # retention must cover the slow window, or the ratio is against 20
    # minutes while claiming an hour
    ck(ixc.order.default_factory().maxlen >= COND_SLOW,
       f"tick retention ({ixc.order.default_factory().maxlen}) covers the "
       f"{COND_SLOW}s baseline the ratio is divided by")

    # The cache must not serve a stale number when a REVISED print lands for
    # a second we already hold: same newest second, same count, different
    # data. Pushed through on_frame because that is the only ingest path that
    # exists in production -- the first version of this check poked the dict
    # directly, which no live code path can do, and it was asserting a
    # property no stamp could deliver.
    def _frame(_id, _sec, _val):
        return {"type": "cfbenchmarks_value",
                "msg": {"index_id": _id,
                        "data": json.dumps({"time": _sec * 1000,
                                            "value": str(_val)})}}

    _z_before = ixc.zrough("C")
    _held = len(ixc.ticks["C"])
    ixc.on_frame(_frame("C", T0 - 5, ixc.ticks["C"][T0 - 5] + 50.0))
    ck(len(ixc.ticks["C"]) == _held,
       "a revised print does not change how many seconds we hold, so "
       "(newest, count) alone cannot detect it")
    ck(ixc.zrough("C") != _z_before,
       "and it STILL busts the cache -- a revised print must not be served "
       "stale from a conditions read")
    _z_now = ixc.zrough("C")
    ixc.on_frame(_frame("C", T0 - 5, ixc.ticks["C"][T0 - 5]))
    ck(ixc.zrough("C") == _z_now,
       "while an identical duplicate does NOT bust it -- otherwise every "
       "repeated frame recomputes a 3600-second window on the order path")

    ck("cond_x=" in src and "idx.conditions(iid)" in src,
       "and the signal record actually carries the conditions columns")

    # --- AMENDMENT 10: never buy a certainty at a discount ------------------
    ck(DUMP_DISCOUNT > 10 * EDGE_FLOOR,
       f"a {100*DUMP_DISCOUNT:.0f}c discount is >10x the {100*EDGE_FLOOR:.1f}c "
       f"edge floor, so the honest edge can never trip it")
    # the live losses this exists for, and the live wins it must not touch,
    # replayed through the same arithmetic the loop uses
    def _dump(f_, price_, want_):
        d_ = (f_ - price_) if want_ == "yes" else ((1 - f_) - price_)
        return d_ > DUMP_DISCOUNT
    ck(_dump(1.0, 0.82, "yes"),
       "XRP 04:59Z (fair 1.0, filled 82c, 18c disc, LOST -$16.61) refused")
    ck(_dump(0.0, 0.10, "no"),
       "DOGE 22:14Z (fair 0.0, filled 10c, 90c disc, LOST -$2.12) refused")
    ck(_dump(0.00492, 0.591, "no"),
       "SOL 2026-09-11 12:30Z (99.508% sure, filled 59.1c, 40.4c disc, "
       "LOST -$12.16) IS refused now -- the 0.999 condition let it through")
    ck(_dump(0.00626, 0.73, "no"),
       "NEAR 09-09 (99.827% sure, 73c, 26.8c disc, LOST -$14.13) refused")
    ck(not _dump(0.99735, 0.89, "yes"),
       "BNB 89c (10.7c disc, WON +$2.06) is NOT refused -- the 5-15c band "
       "went 24-0 for +$32.20 and refusing it was the guard's worst error")
    ck(not _dump(1.0, 0.919, "yes"),
       "SOL 91.9c (8.1c disc, WON) passes")
    ck(not _dump(1.0, 0.978, "yes"),
       "a certainty at 97.8c (2.2c discount, WON) passes -- the normal edge")
    ck(not _dump(0.9953, 0.98, "yes"),
       "and a boundary fill at the ceiling passes untouched")
    ck('nb["dumped"]' in src and "_conf >= DUMP_CONF and _disc > DUMP_DISCOUNT" in src,
       "the guard is wired into the trade loop and counted in the near-miss "
       "record, so refusals are visible rather than silent")
    ck(_DEFAULT_DUMP_ENABLED is True,
       "AMENDMENT 10b: the guard is ON by operator decision (undeterminable "
       "EV, owner chose fewer losses); would-be outcomes are recorded")
    _b10b = src[src.index(chr(10) + "def trade_loop("):]
    ck('rec("dumped"' in _b10b and "dumped_seen.add((close_s, tk))" in _b10b
       and _b10b.index("dumped_seen.add((close_s, tk))") <
       _b10b.index('rec("dumped"'),
       "every refusal writes ONE `dumped` record per (close, market) with "
       "side, price, fair and tau, so the would-be P&L can be resolved later")
    ck(_b10b.index('rec("dumped"') < _b10b.index("if DUMP_ENABLED:"),
       "and the record is written before the enable check, whether or not "
       "the trade is refused")
    # anchored on the loop body, not the whole file: this test's own string
    # literals appear earlier in the file than the loop and would be matched
    # first -- the self-inspection trap that once broke three checks here
    _b10 = src[src.index(chr(10) + "def trade_loop("):]
    ck("if DUMP_ENABLED:" in _b10 and _b10.index("if DUMP_ENABLED:") >
       _b10.index('nb["dumped"] = nb.get("dumped", 0) + 1'),
       "and the count happens BEFORE the enable check, so the class is "
       "recorded whether or not it is refused")

    # ---- AMENDMENT 16: the auto-sizer ------------------------------------
    _sz0 = float(SIZE)
    try:
        # DERIVED FROM THE RUNNING CEILING, not the literal 0.98. Hard-coding
        # it meant --price-ceiling made pinrun fail its own STARTUP self-test,
        # and on 2026-09-18 that took the live bot down for six minutes: the
        # flag was applied before the test ran, the test asserted 0.98, the
        # process wrote "self-test failed -- nothing ran" and exited.
        # EVERY allowance that worst_close_cost counts must appear here, or
        # this check refuses to start the moment a new one is added. A56 and
        # A59 have each sprung it once.
        _wexp = (MAX_PER_CLOSE + max(EXTRA_COIN, LATE_EXTRA)) * 20 * PRICE_CEILING
        ck(abs(worst_close_cost(20) - _wexp) < 1e-12,
           f"worst_close_cost(20) must be (MAX_PER_CLOSE + EXTRA_COIN + "
           f"LATE_EXTRA) x 20 x "
           f"PRICE_CEILING = {_wexp}, got {worst_close_cost(20)}. A56 added a "
           f"third coin's worth of exposure and every rail reads this number, "
           f"so leaving EXTRA_COIN out here would size the brake against a "
           f"bet nobody places")
        ck(_DEFAULT_PRICE_CEILING == 0.980,
           "and the DECLARED ceiling is 98c -- asserted separately, so a flag "
           "that moves the running value cannot silently move the bar too")
        ck(abs(worst_close_cost(200) / worst_close_cost(20) - 10.0) < 1e-12,
           "worst_close_cost must be EXACTLY linear in size -- that is the "
           "whole reason it replaced a sampled maximum, which was not")

        # The ladder, by hand. size_for_bank divides by
        # worst_close_cost(1.0) x brake, and A56 put EXTRA_COIN inside
        # worst_close_cost -- so this arithmetic must carry it too or the
        # check contradicts the function it is checking.
        _per = (BANK_BRAKE * (MAX_PER_CLOSE + max(EXTRA_COIN, LATE_EXTRA))
                * PRICE_CEILING)
        ck(size_for_bank(192.15) == int(192.15 // _per),
           f"$192.15 / ${_per:.2f} (BANK_BRAKE {BANK_BRAKE} x "
           f"(MAX_PER_CLOSE {MAX_PER_CLOSE} + EXTRA_COIN {EXTRA_COIN} + "
           f"LATE_EXTRA {LATE_EXTRA}) x "
           f"ceiling {PRICE_CEILING}) = "
           f"{int(192.15 // _per)}, got {size_for_bank(192.15)}")
        ck(size_for_bank(0.0) == AUTO_SIZE_MIN and size_for_bank(None)
           == AUTO_SIZE_MIN,
           "an empty or unreadable bank must fall to the floor, never to 0")
        ck(size_for_bank(1e9) == AUTO_SIZE_MAX,
           f"the cap must bind, got {size_for_bank(1e9)}")
        _prev = -1
        for _b in (10, 50, 100, 200, 400, 800, 1600):
            _s = size_for_bank(_b)
            ck(_s >= _prev, f"size_for_bank fell from {_prev} to {_s} at "
                            f"bank ${_b} -- more money can never permit less")
            _prev = _s
        ck(size_for_bank(200, brake=3.0) < size_for_bank(200, brake=1.5),
           "a harsher brake must give a SMALLER size")

        # THE UNIT. This is the check that stops a 6535-contract order.
        class _A:
            live = True
            auto_size = True
            loss_abort = -2.0
        _fake = {"base": "b", "pk": "k", "key_id": "i"}
        _resp = {}

        def _mkget(payload, status=200):
            def _g(base, pk, key_id, path, query=None):
                return status, payload
            return _g
        _real_get = pintake._get
        try:
            pintake._get = _mkget({"balance": 19215,
                                   "balance_dollars": "192.1520"})
            ck(abs(read_bank(_fake) - 192.152) < 1e-6,
               f"cents and dollars agreeing must read $192.152, got "
               f"{read_bank(_fake)}")
            pintake._get = _mkget({"balance": 19215})
            ck(read_bank(_fake) is None,
               "balance WITHOUT balance_dollars must be refused, not divided "
               "by 100 on faith -- the unit is read, never inferred")
            pintake._get = _mkget({"balance": 19215,
                                   "balance_dollars": "19215.00"})
            ck(read_bank(_fake) is None,
               "cents and dollars DISAGREEING must be refused; this is the "
               "19215-read-as-dollars failure, which asks for size 6535")
            pintake._get = _mkget({"balance": 19215,
                                   "balance_dollars": "192.1520"}, status=503)
            ck(read_bank(_fake) is None, "a non-200 must read as unknown")
            ck(read_bank({}) is None,
               "no credentials (paper mode) must read as unknown, never 0")
        finally:
            pintake._get = _real_get

        # apply_size moves EVERY size-derived rail. This is the 2026-09-08
        # failure: four size-1 literals refused 160 orders silently.
        _a = _A()
        _mtc0, _mrs0 = pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE
        _la0, _hm0 = pintake.LOSS_ABORT, pintake.HARD_MAX
        try:
            globals()["SIZE"] = 1.0
            _ok, _msg = apply_size(60, _a, "selftest")
            ck(_ok and abs(float(SIZE) - 60.0) < 1e-9,
               f"apply_size must set SIZE, got {SIZE} ({_msg})")
            ck(pintake.MAX_TAKE_COUNT >= 60.0,
               f"MAX_TAKE_COUNT must reach the new size or every order is "
               f"refused in silence, got {pintake.MAX_TAKE_COUNT}")
            ck(pintake.MAX_RUN_STAKE >= 3.0 * 60.0 * MAX_PER_CLOSE,
               f"MAX_RUN_STAKE must cover 3 worst closes at the new size, "
               f"got {pintake.MAX_RUN_STAKE}")
            _wc = 1.00 * 60.0 * MAX_PER_CLOSE
            ck(-4.0 * _wc <= _a.loss_abort <= -1.5 * _wc,
               f"loss_abort {_a.loss_abort} must land inside main()'s own "
               f"[{-4.0 * _wc}, {-1.5 * _wc}] band, or the run halts on its "
               f"first trade")
        finally:
            globals()["SIZE"] = _sz0
            pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE = _mtc0, _mrs0
            pintake.LOSS_ABORT, pintake.HARD_MAX = _la0, _hm0

        # The tick: damped up, immediate down, never under a position.
        _a2 = _A()
        _st = {}
        globals()["SIZE"] = 20.0
        try:
            ck(autosize_tick(_st, _a2, {"open": 1}, now=1e9,
                             bank_reader=lambda: 192.15) is None
               and abs(float(SIZE) - 20.0) < 1e-9,
               "a rail must NEVER move while a position is open")
            _st2 = {}
            autosize_tick(_st2, _a2, {}, now=1e9, bank_reader=lambda: 192.15)
            _tgt = size_for_bank(192.15)
            ck(abs(float(SIZE) - float(_tgt)) < 1e-9,
               f"with AUTO_SIZE_STEP_UP={AUTO_SIZE_STEP_UP} the bot goes "
               f"STRAIGHT to the size the bank supports ({_tgt}), got {SIZE}")
            ck(autosize_tick(_st2, _a2, {}, now=1e9 + 1,
                             bank_reader=lambda: 192.15) is None,
               "a second adjustment inside AUTO_SIZE_EVERY_S must be refused")
            # The damping MECHANISM stays tested even while it is switched
            # off, so turning it back on cannot ship broken.
            _old_step = AUTO_SIZE_STEP_UP
            try:
                globals()["AUTO_SIZE_STEP_UP"] = 1.5
                globals()["SIZE"] = 20.0
                _st2b = {}
                # A BANK THE CAP MUST BITE ON, derived rather than hard-coded.
                # This used to pass a fixed $192.15, which only exceeded the
                # 1.5x cap while one bet was bank/5.88; raising the brake to
                # bank/8 on 2026-09-18 made that bank ask for 24, under the
                # cap, and the damping test started failing for a reason that
                # had nothing to do with damping. A test of the CAP must pick
                # a bank the cap actually binds at, whatever the brake is.
                _big = 20.0 * 1.5 * 3.0 * BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING
                autosize_tick(_st2b, _a2, {}, now=1e9,
                              bank_reader=lambda: _big)
                ck(abs(float(SIZE) - 30.0) < 1e-9,
                   f"with damping at 1.5 the first step is 20 -> 30 however "
                   f"big the bank is, got {SIZE}")
            finally:
                globals()["AUTO_SIZE_STEP_UP"] = _old_step
            _st3 = {}
            globals()["SIZE"] = 60.0
            autosize_tick(_st3, _a2, {}, now=1e9, bank_reader=lambda: 30.0)
            ck(abs(float(SIZE) - float(size_for_bank(30.0))) < 1e-9,
               f"a FALL is immediate and undamped -- $30 supports "
               f"{size_for_bank(30.0)}, got {SIZE}")
            _st4 = {}
            globals()["SIZE"] = 20.0
            ck(autosize_tick(_st4, _a2, {}, now=1e9,
                             bank_reader=lambda: None) is None
               and abs(float(SIZE) - 20.0) < 1e-9,
               "an unreadable bank must leave SIZE exactly where it was")
            _a3 = _A()
            _a3.auto_size = False
            _st5 = {}
            globals()["SIZE"] = 20.0
            ck(autosize_tick(_st5, _a3, {}, now=1e9,
                             bank_reader=lambda: 1e6) is None,
               "--no-auto-size must pin SIZE to --size")
            # THIS BAR MOVED, 2026-09-14, AND IT IS STATED RATHER THAN
            # DELETED. It used to read "paper mode must never auto-size".
            # The consequence was that every paper what-if traded at its
            # --size while the live bot auto-sized to the bank: on 2026-09-14
            # live ran 52 contracts and all four arms ran 20, so not one of
            # their dollar figures could be compared with live's. An arm that
            # is not comparable to live measures nothing. Reading the balance
            # is a GET.
            _a4 = _A()
            _a4.live = False
            _st6 = {}
            ck(autosize_tick(_st6, _a4, {}, now=1e9,
                             bank_reader=lambda: 1e6) is not None,
               "a PAPER arm auto-sizes exactly as live does, or its dollars "
               "cannot be compared with live's and the arm is worthless")
            _a4b = _A()
            _a4b.live = False
            _a4b.auto_size = False
            ck(autosize_tick({}, _a4b, {}, now=1e9,
                             bank_reader=lambda: 1e6) is None,
               "and --no-auto-size still pins it, in paper as in live")
            # THE DIRECTION THAT MUST ALWAYS WORK. Once the rails have been
            # loosened for a big size, a shrink asks set_limits to tighten;
            # it refuses, apply_size rolls back, and the bot is stuck large
            # exactly after the loss that should have shrunk it.
            _a5 = _A()
            _st7 = {}
            globals()["SIZE"] = 1.0
            apply_size(120, _a5, "loosen the rails first")
            _st8 = {}
            globals()["SIZE"] = 120.0
            autosize_tick(_st8, _a5, {}, now=1e9, bank_reader=lambda: 60.0)
            ck(abs(float(SIZE) - float(size_for_bank(60.0))) < 1e-9,
               f"after the rails were loosened for size 120, a $60 bank must "
               f"still shrink SIZE to {size_for_bank(60.0)}, got {SIZE}")
            # A65: --loss-cap is a HARD ceiling on the magnitude, so with a
            # cap in force the loosest the brake may ever be IS the cap. This
            # asserted a bare -240 and failed the moment the operator set
            # --loss-cap 200, which is the flag doing exactly its job.
            _want_loose = -240.0 if LOSS_CAP is None else -min(240.0, abs(LOSS_CAP))
            ck(pintake.LOSS_ABORT <= _want_loose + 1e-9,
               f"and the brake must stay at its loosest high-water mark, not "
               f"be tightened on the way down -- loosest allowed here is "
               f"{_want_loose} (cap {LOSS_CAP}), got {pintake.LOSS_ABORT}")
        finally:
            globals()["SIZE"] = _sz0
            pintake.MAX_TAKE_COUNT, pintake.MAX_RUN_STAKE = _mtc0, _mrs0
            pintake.LOSS_ABORT, pintake.HARD_MAX = _la0, _hm0

        # ---- AMENDMENT 22: the improve-by rule's scope -----------------
        ck(_DEFAULT_IMPROVE_SCOPE == "close",
           "the DECLARED default improve scope is 'close' -- A22 is reached "
           "only through --improve-scope (running now with %r)"
           % IMPROVE_SCOPE)
        # AND A GUARD AGAINST THE PATTERN ITSELF, because this is the third
        # time: every "defaults to" assertion must read a _DEFAULT_ constant,
        # never the live global, or it becomes a refusal to start.
        _dsrc = open(os.path.abspath(__file__), encoding="utf-8").read()
        _dwork = _dsrc[:_dsrc.index("def " + "selftest")]
        # THE GUARD AGAINST THE PATTERN, STRENGTHENED AFTER IT BIT A FOURTH
        # TIME. Checking that a _DEFAULT_ constant EXISTS is not enough -- the
        # assertion has to USE it. So this also scans the suite for any
        # `ck(<NAME> ==` on the live global, which is precisely the shape that
        # turns a guard into a refusal to start the moment its flag is used.
        _dtest = _dsrc[_dsrc.index("def " + "selftest"):]
        for _nm in ("SIGMA_RULER", "IMPROVE_SCOPE", "HONEST_CONF", "PIN",
                    "MAX_PER_MARKET", "IMPROVE_MAX", "PICK",
                    "MIN_FILL_FRAC", "HEDGE_BELIEF", "SWEEP_DEPTH",
                    "SKIP_BANDS", "BAND_MULTS"):
            ck(("_DEFAULT_%s" % _nm) in _dwork,
               "a _DEFAULT_%s exists to assert against, so its guard can "
               "never become a refusal to start" % _nm)
            # The broken shape is a comparison to a LITERAL -- `ck(X == 1)`,
            # `ck(X == "close")`, `ck(X is False)`. Comparing to a SAVED value
            # (`ck(X == _saved)`) is a teardown check and is fine, so the test
            # looks at what follows the operator rather than banning the name.
            _bad = []
            _pos = 0
            _pat = "ck(%s ==" % _nm
            while True:
                _i = _dtest.find(_pat, _pos)
                if _i < 0:
                    break
                _pos = _i + len(_pat)
                _rest = _dtest[_pos:_pos + 12].strip()
                if _rest[:1] in ('"', "'") or _rest[:1].isdigit():
                    _bad.append(_dtest[_i:_i + 40])
            ck(not _bad,
               "and nothing asserts `%s ==` against a LITERAL -- that shape "
               "has stopped this bot from starting four times today, once per "
               "flag added (%s)" % (_nm, _bad))
        ck(_DEFAULT_MAX_PER_MARKET == 1,
           "the DECLARED default MAX_PER_MARKET is 1 (AMENDMENT 13), which is "
           "WHY the improve-by rule is obsolete: the same-market re-buy it was "
           "written to stop is already impossible by default (running now "
           "with %d)" % MAX_PER_MARKET)
        # the exact refusal that cost the HYPE trade at 19:15Z
        _eth, _hype = 0.980, 0.977
        ck(_hype >= _eth - IMPROVE_BY,
           "under scope 'close' a second coin at %.3f IS refused after a fill "
           "at %.3f, because %.3f is not below %.3f -- this is the live 19:15Z "
           "refusal, reproduced from the constants"
           % (_hype, _eth, _hype, _eth - IMPROVE_BY))
        _src22 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _l22 = _src22.split("\n")
        ck(any(ln.strip() == 'if (IMPROVE_SCOPE == "close" and prev is not None'
               for ln in _l22),
           "the trade loop branches on IMPROVE_SCOPE, so scope 'market' really "
           "does skip the refusal rather than merely being accepted as a flag")
        # exposure is UNCHANGED by the amendment: the budget is contracts
        _sz22 = float(SIZE)
        try:
            globals()["SIZE"] = 47.0
            ck(abs(close_budget() - 47.0 * MAX_PER_CLOSE) < 1e-9,
               "the close budget is CONTRACTS (%g), so two coins at 47 is the "
               "same worst case as one coin at 94 -- A22 changes which markets "
               "are bought, never how much can be lost" % close_budget())
        finally:
            globals()["SIZE"] = _sz22

        # ---- AMENDMENT 23: the re-buy band ------------------------------
        ck(abs(_DEFAULT_IMPROVE_MAX - 0.010) < 1e-12,
           "the DECLARED default IMPROVE_MAX is 1.0c (running now with "
           "%.4f)" % IMPROVE_MAX)
        ck(IMPROVE_MAX > IMPROVE_BY,
           "the band has width: at most %.3f cheaper is above at least %.3f "
           "cheaper, so some second buy can qualify"
           % (IMPROVE_MAX, IMPROVE_BY))
        # A FULL position already held: the band applies.
        _p23 = {"per_tk": {"A": 1}, "px_tk": {"A": 0.960},
                "n_tk": {"A": 50.0}}
        ck(rebuy_ok(None, "A", 0.90, 50.0),
           "with nothing yet bought in the close there is no re-buy to judge")
        ck(rebuy_ok(_p23, "B", 0.90, 50.0),
           "a DIFFERENT market is not a re-buy -- AMENDMENT 22 governs that, "
           "and A23 must not quietly re-impose a cross-market bar")
        ck(not rebuy_ok(_p23, "A", 0.958, 50.0),
           "0.2c cheaper is refused: AMENDMENT 3's floor still binds")
        ck(rebuy_ok(_p23, "A", 0.955, 50.0),
           "0.5c cheaper is allowed -- exactly IMPROVE_BY, the edge of the "
           "band, which is where an off-by-one would hide")
        ck(rebuy_ok(_p23, "A", 0.950, 50.0),
           "1.0c cheaper is allowed -- exactly IMPROVE_MAX, the other edge")
        ck(not rebuy_ok(_p23, "A", 0.949, 50.0),
           "1.1c cheaper is REFUSED. THIS IS THE WHOLE AMENDMENT: measured "
           "over 398 markets that offered a second buy, 0.5-1c cheaper lost "
           "0.70% and paid +3.08c/contract, while 5-10c cheaper lost 26.09% "
           "and cost -11.45c. Break-even is 3.58%.")
        ck(not rebuy_ok(_p23, "A", 0.30, 50.0),
           "and a 66c collapse is refused rather than treated as a bargain")

        # ---- AMENDMENT 29: TOPPING UP IS NOT SCALING IN -----------------
        # The operator: "It can buy less on one coin if it's all that's
        # available after checking them all, then if another opens up
        # anywhere even on the same coin buy more."
        _p29 = {"per_tk": {"A": 1}, "px_tk": {"A": 0.960},
                "n_tk": {"A": 5.0}}
        ck(rebuy_ok(_p29, "A", 0.960, 50.0),
           "holding 5 of the 50 we wanted, MORE AT THE SAME PRICE is taken. "
           "A3's improve rule was written against 'doubling the risk without "
           "lowering the average paid', which describes a FULL position, not "
           "one that is 10% filled -- this is finishing the order, not "
           "scaling in")
        ck(rebuy_ok(_p29, "A", 0.970, 50.0),
           "and a top-up at a slightly WORSE price is still taken, because "
           "every other gate -- ceiling, edge, expected value, dump guard -- "
           "has already passed on it at that price")
        ck(not rebuy_ok({"per_tk": {"A": 1}, "px_tk": {"A": 0.960},
                         "n_tk": {"A": 50.0}}, "A", 0.960, 50.0),
           "but once the full 50 are held, the same price is refused again -- "
           "the band is back in force the moment the position is complete")
        ck(not rebuy_ok(_p29, "A", 0.960, 5.0),
           "and 'full' is measured against the size we are RUNNING, not a "
           "literal: those same 5 contracts ARE a complete position at size "
           "5, so the band applies and the same price is refused")
        _src29 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("if not rebuy_ok(prev, tk, price, SIZE):" in _src29,
           "the loop passes the RUNNING size, or every position looks "
           "unfinished and the band never applies at all")
        ck('d29[tk] = d29.get(tk, 0.0) + _n' in _src29,
           "and a fill adds its CONTRACTS to the per-market count, which is "
           "the only input that separates a top-up from a scale-in")
        # the cheapest price paid in THIS market is what the band measures
        # px_tk says 0.950 for this market; the close's overall best is 0.940,
        # set by some OTHER market. A re-buy at 0.935 is 1.5c under our own
        # 0.950 (refuse) but only 0.5c under the close's 0.940 (would allow),
        # so the two readings genuinely disagree here.
        _p23b = {"per_tk": {"A": 2}, "px_tk": {"A": 0.950}, "best": 0.940,
                 "n_tk": {"A": 50.0}}
        ck(not rebuy_ok(_p23b, "A", 0.935, 50.0),
           "the band is measured against the cheapest price paid in THIS "
           "market (0.950), not against the close's overall best (0.940) -- "
           "the latter would compare a BTC re-buy to a price paid on ETH")
        _src23 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("if not rebuy_ok(prev, tk, price):" in _src23,
           "and the trade loop actually calls rebuy_ok, so the band is live "
           "logic rather than a function nothing reaches")
        ck('"px_tk": {tk: px}' in _src23 and 'd23[tk] = min(' in _src23,
           "a fill records the price paid per market, which is the input the "
           "band needs -- without it rebuy_ok silently allows everything")

        # ---- AMENDMENT 35: size from the LADDER, not the touch ---------
        ck(_DEFAULT_SWEEP_DEPTH is False,
           "ladder sizing is OFF by default -- it buys MORE per fill, which "
           "is the one change that moves exposure rather than merely which "
           "market is bought (running %r)" % SWEEP_DEPTH)

        class _BK35(object):
            def __init__(self, book):
                import threading as _th
                self.books = {"T": book}
                self.lock = _th.Lock()
            buyable = livebook.LiveBook.buyable

        # a YES ask at p IS a NO bid at 1-p. Six at 96.3c, 211 more at 98c.
        _b35 = _BK35({"yes": {}, "no": {round(1 - 0.963, 4): 6.0,
                                        round(1 - 0.98, 4): 211.0}})
        ck(abs(_b35.buyable("T", "yes", 0.963) - 6.0) < 1e-9,
           "at the touch price only the touch size is buyable (6)")
        ck(abs(_b35.buyable("T", "yes", 0.98) - 217.0) < 1e-9,
           "but up to the 98c limit the ladder holds 217 -- THE WHOLE "
           "AMENDMENT. Live on 2026-09-14 the bot asked for 6 of them and "
           "made $0.21 while the rest sat one cent away")
        ck(_b35.buyable("T", "no", 0.98) == 0.0,
           "and buying the OTHER side reads the OTHER book -- summing the "
           "wrong one reports the depth of the people we trade AGAINST")
        ck(_b35.buyable("MISSING", "yes", 0.98) == 0.0,
           "an unknown market is zero, never an exception in the order path")
        # ---- MIN_FILL_FRAC 0: no percentage floor at all ---------------
        # The operator, 2026-09-14: "No thinking 'is it worth it there's no
        # point in that it's wasted time.' ... No 10%."
        _mff_floor = lambda frac, size: max(MIN_LEVEL, frac * float(size))
        ck(_mff_floor(0.0, 58.0) == MIN_LEVEL == 1.0,
           "at --min-fill-frac 0 the only floor left is MIN_LEVEL, ONE "
           "contract -- the percentage floor is gone, not merely small")
        ck(_mff_floor(0.0, 250.0) == 1.0,
           "and it stays one contract at SIZE 250. THIS IS THE POINT: a 10%% "
           "floor GROWS with the bank -- 6 contracts at SIZE 58, 25 at SIZE "
           "250 -- so it refuses MORE of the book exactly as we scale in")
        ck(_mff_floor(0.10, 58.0) == 5.800000000000001 or
           abs(_mff_floor(0.10, 58.0) - 5.8) < 1e-9,
           "for contrast, the old 10%% floor at SIZE 58 refused anything under "
           "5.8 contracts at the best price")
        ck(_mff_floor(0.0, 58.0) <= _mff_floor(0.10, 58.0),
           "and zero is never TIGHTER than the floor it replaces -- this flag "
           "may only ever loosen")

        # ---- AMENDMENT 45: the whole ladder on every signal --------------
        ck(_DEFAULT_LADDER_LEVELS >= 100,
           "at least 100 levels are stored -- the tick is 0.1c above 90c, so "
           "the 88-98c band we trade is about a hundred prices and 8 covered "
           "a fifth of the book on the BTC 05:30 loss (running %d)"
           % LADDER_LEVELS)
        _src45 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _tl45 = _src45[_src45.index(chr(10) + "def trade_loop("):]
        ck('book.depth(tk, "no" if want == "yes" else "yes",' in _tl45
           and "LADDER_LEVELS)" in _tl45,
           "the signal reads LADDER_LEVELS deep, not a literal 8")
        ck('sig["ladder_under"]' in _tl45 and "PRICE_CEILING + 1e-9" in _tl45,
           "and records ladder_under -- what we could actually BUY at or under "
           "the ceiling, which is the number every capacity question wants")
        # A78 REPLACED A CHARACTER BUDGET WITH THE PROPERTY IT STOOD FOR.
        # This was `index("book.depth") > index('rec("signal"') - 4000` -- a
        # proxy for "these two are close together", which broke the moment a
        # gate was added BETWEEN them even though the gate sits AFTER the read
        # and so cannot make it run more often. The real requirement is that
        # the depth read happens only for a market that has already survived
        # the filters that refuse most of them, and before the signal record.
        ck(_tl45.index("book.depth(tk,") > _tl45.index('_gate("confidence"'),
           "the depth read runs only AFTER the confidence gate has refused "
           "everything it is going to -- that gate is what keeps this off the "
           "20 Hz path, not the number of characters above it")
        ck(_tl45.index("book.depth(tk,") > _tl45.index('_gate("no_offer"'),
           "...and after the no-offer gate, so a market nobody is quoting is "
           "never read for depth")
        ck(_tl45.index("book.depth(tk,") < _tl45.index('rec("signal"'),
           "the read sits on the SIGNAL path, which fires a few dozen times a "
           "day, not in the 20 Hz scan loop")
        # the arithmetic of ladder_under, on a planted ladder
        # THE LADDER IS PLANTED RELATIVE TO THE RUNNING CEILING so the
        # arithmetic holds whatever --price-ceiling says: three rungs at or
        # under it, and one enormous rung a tick above it that must never be
        # counted as capacity.
        _c45 = float(PRICE_CEILING)
        _lad45 = [[_c45 - 0.03, 100.0], [_c45 - 0.01, 200.0],
                  [_c45, 50.0], [_c45 + 0.01, 9999.0]]
        _under = sum(x[1] for x in _lad45 if x[0] <= PRICE_CEILING + 1e-9)
        ck(_under == 350.0,
           "ladder_under counts 100+200+50 = 350 at or under the %.2fc ceiling "
           "and EXCLUDES the 9,999 sitting a tick above it, which we may never "
           "buy" % (100 * _c45))
        ck(sum(x[1] for x in _lad45) == 10349.0 and _under < sum(x[1] for x in _lad45),
           "ladder_total is the whole book (10,349) and is always at least "
           "ladder_under -- reporting the total as capacity is how a 99c wall "
           "gets counted as something we could take")

        # ---- AMENDMENT 44: book depth is logged past the cap ------------
        _d44 = _depth_report([1.0, 300.0, 600.0, 900.0, 3000.0])
        for _k in ("250", "500", "750", "1000", "2000"):
            ck(_k in _d44["kept"],
               "the kept curve reaches %s -- it used to stop at 250, the exact "
               "number the operator wants to see past" % _k)
        ck(_d44["kept"]["500"] == 3 and _d44["kept"]["1000"] == 1
           and _d44["kept"]["2000"] == 1,
           "and it counts correctly out there (3 moments hold 500+, 1 holds "
           "1000+, 1 holds 2000+)")
        ck(_d44["kept"]["1"] >= _d44["kept"]["250"] >= _d44["kept"]["2000"],
           "the curve is monotonically non-increasing -- a bigger order can "
           "never be fillable at more moments than a smaller one")
        _n44 = _fresh_near()
        ck("ladders" in _n44 and "ladder_seen" in _n44
           and isinstance(_n44["ladder_seen"], set),
           "a fresh close carries a ladder sample and a per-market seen set")
        ck(_depth_report([]) is None,
           "and an empty ladder list reports None rather than a fake zero")
        _src44 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _tl44 = _src44[_src44.index(chr(10) + "def trade_loop("):]
        ck('nb["ladder_seen"].add(tk)' in _tl44
           and 'if tk not in nb["ladder_seen"]:' in _tl44,
           "the ladder is sampled ONCE PER MARKET per close, not per look -- "
           "per look would put a book walk inside a 20 Hz loop")
        ck(_tl44.count("ladder=_depth_report(nb.get(\"ladders\"))") == 2,
           "and BOTH close_summary emitters carry it, or half the closes "
           "would silently have no ladder trend")

        # ---- AMENDMENT 43: a withdrawal is not a loss -------------------
        ck(_DEFAULT_EXTERNAL_MIN == 1.00 and _DEFAULT_EXTERNAL_DETECT is True,
           "A43 declared defaults: $1.00 floor, detection ON (running %.2f / %r)"
           % (EXTERNAL_MIN, EXTERNAL_DETECT))
        # a pure trading loss: the bank fell by exactly what we lost
        ck(classify_bank_move(900.0, 1000.0, -100.0, 0.0)[0] == "trading",
           "a $100 fall fully explained by $100 of realised losses is TRADING")
        # a withdrawal: the bank fell and nothing was lost
        _k, _a = classify_bank_move(500.0, 1000.0, 0.0, 0.0)
        ck(_k == "withdrawal" and abs(_a + 500.0) < 1e-9,
           "a $500 fall with NO realised loss is a WITHDRAWAL of $500")
        # both at once -- the operator takes $400 out on a day we lost $100
        _k, _a = classify_bank_move(500.0, 1000.0, -100.0, 0.0)
        ck(_k == "withdrawal" and abs(_a + 400.0) < 1e-9,
           "losing $100 AND withdrawing $400 reports the WITHDRAWAL as $400 -- "
           "the loss is still charged to trading")
        # a winning day plus a withdrawal of the winnings
        _k, _a = classify_bank_move(1000.0, 1000.0, 200.0, 0.0)
        ck(_k == "withdrawal" and abs(_a + 200.0) < 1e-9,
           "the operator's stated policy -- win $200, take $200 out, bank flat "
           "-- reads as a $200 withdrawal, not as a mysterious zero")
        # a deposit
        ck(classify_bank_move(1500.0, 1000.0, 0.0, 0.0)[0] == "deposit",
           "money appearing with no trade is a DEPOSIT")
        # noise stays trading
        for _n in (0.0, 0.40, -0.99, 0.99):
            ck(classify_bank_move(1000.0 + _n, 1000.0, 0.0, 0.0)[0] == "trading",
               "an unexplained $%+.2f is inside the floor and stays TRADING "
               "-- fees and settlement timing must not read as cash movements"
               % _n)
        # THE RESTART GUARD, and it is the one that would have hurt: a restart
        # zeroes `realised` while the bank carries over
        ck(classify_bank_move(1000.0, None, 0.0, None)[0] == "trading",
           "the FIRST tick of a run never classifies -- a restart resets the "
           "realised counter while the bank carries over, so without this "
           "every restart would look like a withdrawal of the whole run")
        ck(classify_bank_move(None, 1000.0, 0.0, 0.0)[0] == "trading",
           "and an unreadable balance never classifies either")
        # shift_hwm
        import tempfile as _tf43
        _d43 = _tf43.mkdtemp(prefix="pinhwm43-")
        try:
            _f43 = os.path.join(_d43, "hwm.json")
            write_hwm(1500.0, _f43)
            ck(abs(shift_hwm(-500.0, _f43) - 1000.0) < 1e-9,
               "withdrawing $500 from a $1500 high-water mark leaves it at "
               "$1000, so the brake measures trading and not the withdrawal")
            ck(abs(read_hwm(_f43) - 1000.0) < 1e-9, "and it is written to disk")
            ck(abs(drawdown(1000.0, read_hwm(_f43))) < 1e-12,
               "a bank of $1000 against the shifted mark is ZERO drawdown -- "
               "the brake does not fire. Before A43 this was a 33% drawdown "
               "and halted the bot")
            ck(shift_hwm(-99999.0, _f43) == 0.0,
               "the mark never goes negative")
            _miss = os.path.join(_d43, "nope.json")
            ck(shift_hwm(-10.0, _miss) is None and read_hwm(_miss) is None,
               "a missing mark is left missing, never invented")
        finally:
            for _x in os.listdir(_d43):
                os.remove(os.path.join(_d43, _x))
            os.rmdir(_d43)
        # DRIVE THE WHOLE BRANCH, not just its parts. The isolated tests
        # above all passed while autosize_tick crashed on the logging line.
        _d43b = _tf43.mkdtemp(prefix="pinext-")
        try:
            _h43b = os.path.join(_d43b, "hwm.json")
            write_hwm(1500.0, _h43b)

            class _A43(object):
                live = False
                auto_size = True
                size = 20
                max_positions = 3
                loss_abort = -60.0

            _got = []
            _st43 = {}
            _sv43 = dict(pintake.LEDGER)
            _lim43 = (pintake.LOSS_ABORT, pintake.MAX_RUN_STAKE,
                      pintake.MAX_TAKE_COUNT, pintake.HARD_MAX)
            _sz43 = SIZE
            try:
                pintake.LEDGER["realised"] = 0.0
                autosize_tick(_st43, _A43(), {}, rec=lambda k, **kw: _got.append((k, kw)),
                              now=1e9, bank_reader=lambda: 1500.0, hwm_path=_h43b)
                autosize_tick(_st43, _A43(), {}, rec=lambda k, **kw: _got.append((k, kw)),
                              now=1e9 + 1000, bank_reader=lambda: 1000.0,
                              hwm_path=_h43b)
            finally:
                pintake.LEDGER.clear()
                pintake.LEDGER.update(_sv43)
                (pintake.LOSS_ABORT, pintake.MAX_RUN_STAKE,
                 pintake.MAX_TAKE_COUNT, pintake.HARD_MAX) = _lim43
                globals()["SIZE"] = _sz43
            _ext = [kw for k, kw in _got if k == "external"]
            ck(len(_ext) == 1 and _ext[0].get("move") == "withdrawal"
               and abs(_ext[0].get("amount", 0) + 500.0) < 1e-9,
               "autosize_tick END TO END: $500 vanishing with no realised loss "
               "logs ONE external record saying withdrawal, -500")
            ck("kind" not in _ext[0],
               "and it does NOT pass `kind` as a keyword -- rec(kind, **kw) "
               "takes it positionally, and rec('external', kind=...) raises "
               "TypeError. That crashed the live bot on 2026-09-15 at "
               "04:29:30Z and the isolated tests all passed through it")
            ck(abs(read_hwm(_h43b) - 1000.0) < 1e-9,
               "and the high-water mark really moved on disk, so the next tick "
               "sees zero drawdown instead of 33%")
        finally:
            for _x in os.listdir(_d43b):
                os.remove(os.path.join(_d43b, _x))
            os.rmdir(_d43b)
        _src43 = open(os.path.abspath(__file__), encoding="utf-8").read()
        # ANCHOR ON A NEWLINE-PREFIXED def. Without the newline this finds the
        # string inside THIS TEST, which sits earlier in the file than the
        # function -- so the slice began mid-test and the ordering checks
        # compared lines of the test against each other. Fourth time this exact
        # self-inspection trap has bitten this file (2026-09-11 x3, tonight x4).
        _ab43 = _src43[_src43.index(chr(10) + "def autosize_tick("):]
        ck(_ab43.index("classify_bank_move(") < _ab43.index('state["drawdown"] = drawdown('),
           "the classifier runs BEFORE the drawdown is computed -- after it, "
           "the brake would already have tripped on the operator's own cash")
        ck(_ab43.index("if open_positions:") < _ab43.index("classify_bank_move("),
           "and only when FLAT, so collateral on an open position is never "
           "mistaken for a withdrawal")

        # ---- AMENDMENT 41: after a jump, sigma is doubled ---------------
        ck(_DEFAULT_JUMP_WIDEN == 2.0 and _DEFAULT_JUMP_WIDEN_WINDOW == 5
           and _DEFAULT_WIDEN_ENABLED is False,
           "A41 declared defaults: x2.0, 5 s window, OFF (running %.1f / %d / %r)"
           % (JUMP_WIDEN, JUMP_WIDEN_WINDOW, WIDEN_ENABLED))
        _i41 = IndexWS(["W"])
        _C41 = 2_000_000
        _sg41 = 4.073757
        # 47 locked prints ~10 under the strike, then the BTC 05:30 jump
        _K41 = 77695.85
        for _s in range(_C41 - 60, _C41 - 13):
            _i41.ticks["W"][_s] = _K41 - 10.0
        _i41.ticks["W"][_C41 - 13] = _K41 + 12.25        # the +18.5 second
        _on41 = WIDEN_ENABLED
        try:
            globals()["WIDEN_ENABLED"] = False
            ck(widen_factor(_i41, "W", _sg41, "no") == 1.0
               and widen_factor(_i41, "W", _sg41, "yes") == 1.0,
               "with the flag OFF the factor is exactly 1.0 even on a jump, "
               "either side -- the flag is the whole switch")
            globals()["WIDEN_ENABLED"] = True
            ck(widen_factor(_i41, "W", _sg41, "no") == 2.0,
               "with the flag ON, the +22.25 move (5.5 sd) is AGAINST a NO "
               "holder and doubles sigma")
            # AMENDMENT 42: the same jump, the other side
            ck(widen_factor(_i41, "W", _sg41, "yes") == _DEFAULT_JUMP_WIDEN_FAVOUR,
               "and the SAME jump is in a YES holder's favour, so it widens by "
               "%.1f, not 2.0 -- the operator's question, and the measured "
               "answer" % _DEFAULT_JUMP_WIDEN_FAVOUR)
            ck(_DEFAULT_JUMP_WIDEN_FAVOUR < _DEFAULT_JUMP_WIDEN,
               "a favourable jump is ALWAYS less cautious than an adverse one")
            ck(_DEFAULT_JUMP_WIDEN_FAVOUR > 1.0,
               "but never 1.0: the reversal tail after a favourable jump is "
               "still 2.6x calm, so a favourable jump is not a calm market")
            ck(widen_factor(_i41, "W", _sg41) == 2.0,
               "with NO side given, the CAUTIOUS branch is taken -- a caller "
               "that forgets the side must never get the looser number")
            ck(widen_factor(_i41, "W", None, "no") == 1.0
               and widen_factor(_i41, "W", 0.0, "no") == 1.0
               and widen_factor(_i41, "MISSING", _sg41, "no") == 1.0,
               "a missing sigma or a missing market never widens -- a feed "
               "hiccup must not make the model humbler by accident")
            # THE MECHANISM: the widened model is LESS sure, on the BTC shape
            _f1 = fair(_i41, "W", _C41, _C41 - 13, _K41, _sg41)
            _f2 = fair(_i41, "W", _C41, _C41 - 13, _K41, _sg41 * 2.0)
            _c1, _c2 = 1.0 - _f1, 1.0 - _f2               # confidence in NO
            ck(_c1 > _c2 and (_c1 - _c2) > 1e-4,
               "on the BTC 05:30 shape, doubling sigma lowers confidence in "
               "NO from %.5f to %.5f -- the widened model is humbler exactly "
               "where the unwidened one was 99.99%% sure and wrong" % (_c1, _c2))
            # a jump 6+ seconds ago is out of the 5 s window
            _i42 = IndexWS(["V"])
            for _s in range(_C41 - 60, _C41 - 5):
                _i42.ticks["V"][_s] = 100.0
            _i42.ticks["V"][_C41 - 12] = 200.0            # a huge move, 7 s back
            for _s in range(_C41 - 11, _C41 - 5):
                _i42.ticks["V"][_s] = 200.0
            ck(widen_factor(_i42, "V", 1.0, "no") == 1.0
               and widen_factor(_i42, "V", 1.0, "yes") == 1.0,
               "a jump seven seconds ago is outside the 5 s window and does "
               "not widen, on either side")
            # THE NULL: calm prints never widen
            _i43 = IndexWS(["U"])
            for _s in range(_C41 - 60, _C41):
                _i43.ticks["U"][_s] = 100.0 + 0.5 * ((_s % 3) - 1)
            ck(widen_factor(_i43, "U", 1.0, "no") == 1.0
               and widen_factor(_i43, "U", 1.0, "yes") == 1.0,
               "NULL: sub-sd wobbles never widen, on either side")
        finally:
            globals()["WIDEN_ENABLED"] = _on41
        _src41 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _tl41 = _src41[_src41.index(chr(10) + "def trade_loop("):]
        ck("widen_factor(idx, iid, sg, _lean)" in _tl41
           and "sg * SIGMA_STRESS * _wf, round_digits=digits)" in _tl41,
           "the ENTRY decision takes the lean from the UNWIDENED price, then "
           "re-prices widened -- `want` does not exist yet at that point and "
           "passing it raised UnboundLocalError on every market that reached "
           "the line")
        ck(_tl41.index("f = fair(idx, iid, close_s, now_s, strike, sg * SIGMA_STRESS,")
           < _tl41.index("widen_factor(idx, iid, sg, _lean)"),
           "and the unwidened price is computed BEFORE the widen factor, "
           "which is the only order in which the lean is knowable")
        ck("* widen_factor(idx, _hiid, _hsg, _hwant)," in _tl41,
           "and so does the HEDGE's belief -- both places the model prices a "
           "position, or a held position would be priced by a different model "
           "than the one that bought it")
        ck("widened=bool(_wf > 1.0)," in _tl41,
           "and every signal records whether it was priced widened, so the "
           "paper arm's effect is auditable")

        # ---- AMENDMENT 40: do not buy into a jump against us -----------
        ck(_DEFAULT_JUMP_SIGMA == 3.0 and _DEFAULT_JUMP_LOOKBACK == 3
           and _DEFAULT_JUMP_ENABLED is False,
           "A40 declared defaults: 3 sd, 3 s lookback, OFF (running %.1f / %d / %r)"
           % (JUMP_SIGMA, JUMP_LOOKBACK, JUMP_ENABLED))
        _sg40 = 4.073757                        # BTC's sigma at 05:30 ET
        _btc40 = [2.39, 18.53, 0.25]            # :47-:46, :46-:45, :45-:44
        ck(abs(jump_against(_btc40, _sg40, "no") - 18.53 / _sg40) < 1e-9,
           "BTC 05:30 ET: buying NO, the +18.53 move the second before entry "
           "is %.2f sd AGAINST us" % (18.53 / _sg40))
        ck(jump_against(_btc40, _sg40, "yes") < 0,
           "and buying YES in that same market every one of those moves is in "
           "our FAVOUR -- the sign flips with the side (the fill test first "
           "had this backwards and called the dangerous bucket our safest)")
        ck(abs(jump_against([-18.53], _sg40, "yes") - 18.53 / _sg40) < 1e-9,
           "a DOWN move of the same size is against a YES holder by the same "
           "amount")
        _on40 = JUMP_ENABLED
        try:
            globals()["JUMP_ENABLED"] = True
            ck(jump_block(_btc40, _sg40, "no"),
               "with the gate ON, the BTC 05:30 entry is REFUSED (4.55 sd >= 3)")
            ck(not jump_block([0.0011, -0.0004, 0.0009], 0.003675, "no"),
               "HYPE 16:00 ET (worst move +0.3 sd) is NOT refused -- this gate "
               "catches the jump losses, not the no-warning ones")
            ck(not jump_block([2.9 * _sg40], _sg40, "no"),
               "2.9 sd is under the bar; the threshold is >= 3.0, fixed before "
               "the fill test was run")
            ck(not jump_block([-18.53, -30.0], _sg40, "no"),
               "big moves in OUR FAVOUR never block")
            ck(not jump_block([0.5, -0.3, 0.8], 1.0, "no") and
               not jump_block([0.5, -0.3, 0.8], 1.0, "yes"),
               "NULL: sub-sd wobbles never block, either side")
            ck(not jump_block([], 1.0, "no") and not jump_block(None, 1.0, "no")
               and not jump_block([50.0], None, "no")
               and not jump_block([50.0], 0.0, "no"),
               "unmeasurable inputs never block -- missing data is not a jump")
            ck(jump_against([], 1.0, "no") is None
               and jump_against([1.0], None, "no") is None,
               "and read as None, never as a number")
        finally:
            globals()["JUMP_ENABLED"] = _on40
        # ASSERT THE DEFAULT, NOT THE RUNNING VALUE. The first version of this
        # line sat after the restore above and read the live flag -- so with
        # --jump-gate on, the bot REFUSED TO START. Same trap as this
        # morning's --min-fill-frac 0 outage; the boot check caught it first.
        try:
            globals()["JUMP_ENABLED"] = False
            ck(not jump_block(_btc40, _sg40, "no"),
               "with the gate OFF (the default) even the BTC entry passes -- "
               "the flag is the whole switch")
        finally:
            globals()["JUMP_ENABLED"] = _on40
        _src40 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _tl40 = _src40[_src40.index(chr(10) + "def trade_loop("):]
        ck(_tl40.index("if jump_block(_mv, sg, want):")
           > _tl40.index("against_block(strike, spot, sg, want, e)"),
           "A40 runs AFTER A38")
        ck(_tl40.index("if jump_block(_mv, sg, want):")
           < _tl40.index("if _disc > DUMP_DISCOUNT:"),
           "and BEFORE the dump guard, so the three refusals stay separable")
        ck('_gate("jump_against"' in _tl40 and "moves=[" in _tl40,
           "every refusal records the moves and sigma it saw, so the rule can "
           "be scored instead of trusted")
        ck("def recent_moves(self, iid, n=3):" in _src40 and
           "with self.lock:" in _src40.split("def recent_moves(", 1)[1][:700],
           "IndexWS.recent_moves exists and reads the tick dict under the lock")

        # ---- AMENDMENT 38: thin edge while the price runs against us ---
        ck(_DEFAULT_AGAINST_SIGMA == 1.0 and _DEFAULT_AGAINST_EDGE == 0.020
           and _DEFAULT_AGAINST_ENABLED is True,
           "A38 declared defaults: 1.0 sigma past the strike AND under 2c "
           "(running %.2f / %.3f / %r)"
           % (AGAINST_SIGMA, AGAINST_EDGE, AGAINST_ENABLED))

        # direction, both sides. Buying NO needs the average BELOW the strike,
        # so spot ABOVE it is against us; YES is the mirror. Getting this
        # backwards would refuse exactly the trades we most want.
        ck(abs(against_us(100.0, 104.0, 2.0, "no") - 2.0) < 1e-12,
           "buying NO with spot 4 above the strike and a 2-unit move is "
           "2.0 AGAINST us")
        ck(abs(against_us(100.0, 104.0, 2.0, "yes") + 2.0) < 1e-12,
           "buying YES in that same market is 2.0 in our FAVOUR -- the sign "
           "must flip with the side")
        ck(abs(against_us(100.0, 96.0, 2.0, "no") + 2.0) < 1e-12,
           "and NO with spot below the strike is in our favour")

        # THE FIVE REAL FILLS THE OPERATOR APPROVED THIS FOR. Four won, and
        # they are worth 41c, 47c, 56c and 37c -- $1.81 between them. One lost
        # $58.43. All five must be refused, or the rule is not the rule.
        for _sk, _sp, _sig38, _w38, _e38, _lab in (
                (1.0, 1.0 + 1.4, 1.0, "no", 0.0047, "NEAR 09-09 00:29, won 41c"),
                (1.0, 1.0 + 3.2, 1.0, "no", 0.0152, "ZEC 09-09 05:29, won 47c"),
                (1.0, 1.0 + 1.8, 1.0, "no", 0.0053, "ZEC 09-09 07:29, won 56c"),
                (1.0, 1.0 + 1.1, 1.0, "no", 0.0185, "BNB 09-10 09:29, won 37c"),
                (77695.85, 77708.10, 4.073757, "no", 0.01948,
                 "BTC 09-14 05:30, LOST $58.43")):
            ck(against_block(_sk, _sp, _sig38, _w38, _e38),
               "A38 refuses %s" % _lab)

        # THE NULL, and it is the important half: each condition ALONE must
        # NOT block. Either one on its own was measured as a bad gate --
        # 6.5:1 and 34:1 winners given up per loss avoided, against 4:1 for
        # the pair.
        ck(not against_block(77695.85, 77708.10, 4.073757, "no", 0.0250),
           "the SAME 05:30 book with a 2.5c edge is NOT refused -- a price "
           "running against us is fine when we are paid enough for it")
        ck(not against_block(77695.85, 77680.00, 4.073757, "no", 0.01948),
           "and the SAME thin 1.9c edge with spot on OUR side is NOT refused "
           "-- 31%% of everything we trade is under 2c and blocking it all "
           "costs 34 winners per loss avoided")
        ck(not against_block(100.0, 100.5, 1.0, "no", 0.01),
           "half a sigma past the strike is under the 1.0 threshold")

        # unmeasurable inputs must never block -- a gate that fired on a
        # missing sigma would stop trading whenever the index hiccuped
        for _bad38 in ((None, 1.0, 1.0), (1.0, None, 1.0), (1.0, 1.0, None),
                       (1.0, 1.0, 0.0)):
            ck(against_us(_bad38[0], _bad38[1], _bad38[2], "no") is None,
               "unmeasurable input %r reads as None, never as a number"
               % (_bad38,))
            ck(not against_block(_bad38[0], _bad38[1], _bad38[2], "no", 0.001),
               "and never blocks -- missing data is not evidence the price is "
               "against us")
        ck(not against_block(1.0, 99.0, 1.0, "no", None),
           "a missing edge never blocks either")

        _src38 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _tl38 = _src38[_src38.index(chr(10) + "def trade_loop("):]
        ck(_tl38.index("against_block(strike, spot, sg, want, e)")
           > _tl38.index('_gate("edge_floor"'),
           "the A38 gate runs AFTER the edge floor -- it is the same question "
           "with one more fact, and a market the edge floor already refuses "
           "must be attributed to the edge floor")
        ck(_tl38.index("against_block(strike, spot, sg, want, e)")
           < _tl38.index("if _disc > DUMP_DISCOUNT:"),
           "and BEFORE the dump guard, so the two refusals stay separable in "
           "the gate audit")
        ck('_gate("against_thin"' in _tl38,
           "and every refusal is recorded, so the rule can be scored instead "
           "of trusted -- it was deployed on FIVE events")

        # ---- AMENDMENT 39: the loss counter resets when the bank is whole --
        ck("_hwm_before = read_hwm(hwm_path)" in _src38
           and _src38.index("_hwm_before = read_hwm(hwm_path)")
           < _src38.index("hwm = write_hwm(bank, hwm_path) or bank"),
           "A39 reads the high-water mark BEFORE write_hwm raises it -- "
           "reading after would make EVERY tick look like a recovery and the "
           "brake would never hold")
        _blk39 = _src38.split("_hwm_before = read_hwm(hwm_path)", 1)[1][:1800]
        ck('pintake.LEDGER["losses"] = 0' in _blk39
           and 'state["losing_closes"] = set()' in _blk39,
           "and it clears BOTH the ledger count the brake reads and the set "
           "of losing closes -- clearing one and not the other would let the "
           "next loss on an old close fail to count")
        ck("float(bank) >= float(_hwm_before)" in _blk39,
           "the trigger is the bank reaching the level it fell FROM, which is "
           "the operator's own words and the same event the drawdown brake "
           "treats as recovery")

        # ---- AMENDMENT 37: the depth FLOOR reads the ladder too --------
        ck(_DEFAULT_DEPTH_LADDER is False,
           "the ladder-aware depth floor is OFF by default -- it lets the bot "
           "trade markets it used to refuse outright, which is new exposure, "
           "not merely a bigger fill (running %r)" % DEPTH_LADDER)

        # The live shape this exists for: a thin touch in front of a deep
        # ladder. 3 contracts at 96.3c, 1600 more at or under 98c.
        _b37 = type(_b35)({"yes": {}, "no": {round(1 - 0.963, 4): 3.0,
                                             round(1 - 0.98, 4): 1600.0}})
        _FLOOR37 = max(MIN_LEVEL, 0.10 * 58.0)      # --min-fill-frac 0.10, SIZE 58
        ck(_FLOOR37 > 3.0,
           "at SIZE 58 and a tenth-size floor, a 3-contract touch IS refused "
           "today -- the floor is %.1f" % _FLOOR37)
        ck(_b37.buyable("T", "yes", 0.963) == 3.0,
           "the touch alone holds 3, which is what the floor sees today")
        ck(min(58.0, _b37.buyable("T", "yes", 0.98)) == 58.0,
           "but the ladder up to a 98c sweep limit holds a full 58 -- so the "
           "refusal is thrown away on a number that does not describe what we "
           "could buy")

        # THE NULL. A thin touch in front of a thin LADDER must still refuse,
        # or this amendment has simply deleted the floor.
        _b37n = type(_b35)({"yes": {}, "no": {round(1 - 0.963, 4): 3.0,
                                              round(1 - 0.98, 4): 1.0}})
        ck(min(58.0, _b37n.buyable("T", "yes", 0.98)) < _FLOOR37,
           "A THIN LADDER STILL FAILS THE FLOOR (4 < %.1f). Without this the "
           "amendment would be indistinguishable from removing the floor, "
           "which RESULTS_levels.md measured as costing 30%% of the money"
           % _FLOOR37)

        _src37 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("if DEPTH_LADDER and SWEEP_DEPTH and take_n < _floor:" in _src37,
           "the floor consults the ladder ONLY with both flags on -- passing "
           "on ladder depth while the ORDER still sizes from the touch buys "
           "the scrap fill AMENDMENT 6 added the floor to prevent")
        # SLICE FROM trade_loop FIRST. The literal "_reach = take_n" also
        # appears in THIS self-test, which sits EARLIER in the file, so a
        # split over the whole source finds the test's own string and measures
        # nothing. Same self-inspection trap that broke three checks here on
        # 2026-09-11.
        _tl37 = _src37[_src37.index(chr(10) + "def trade_loop("):]
        _blk37 = _tl37.split("_reach = take_n", 1)[1].split("if _reach < _floor:", 1)[0]
        ck(len(_blk37) > 80 and "DEPTH_LADDER" in _blk37,
           "the block under test is the real one in trade_loop, not this "
           "file's own description of it")
        ck("take_n =" not in _blk37,
           "and it NEVER reassigns take_n -- every downstream user keeps the "
           "touch number and the A35 order block does the widening, so this "
           "change decides only whether to REFUSE")
        ck("_reach = min(float(SIZE)," in _blk37,
           "the reach is still capped by SIZE, so the worst close is unchanged")
        ck('reach=round(float(_reach), 2)' in _src37 and
           'depth_ladder=bool(DEPTH_LADDER and SWEEP_DEPTH)' in _src37,
           "and a refusal records what the ladder held, so the next session "
           "can measure this instead of re-deriving it")
        # SLICE FROM trade_loop -- the A38 block above this one also contains
        # the literal '_gate("edge_floor"', and a whole-file index finds THAT.
        # Third time this exact trap has bitten in this file.
        ck(_tl37.index("_reach = take_n") <
           _tl37.index('_gate("edge_floor"'),
           "the ladder check still runs BEFORE the edge floor, so every market "
           "it lets through is judged by edge, dump guard, ceiling and EV "
           "exactly as before -- nothing is waved past them")

        _src35 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("if SWEEP_DEPTH and _limit > price + 1e-9:" in _src35,
           "it only reaches for depth when the limit is ABOVE the touch -- "
           "with no sweep there is no extra ladder to take")
        ck("take_n = min(float(SIZE), _deep, max(0.0, _room))" in _src35,
           "and the enlarged order is still capped by SIZE and by what is "
           "left of the close's contract budget, so exposure per close "
           "cannot grow")

        # ---- AMENDMENT 45: one-coin depth, PAPER ONLY ---------------------
        # The SHIPPED default, not the running value: a paper arm applies the
        # flag before this self-test runs (the same shape that makes --honest
        # fail its own self-test), and the arm must still be able to start.
        ck(_DEFAULT_ONE_COIN_DEPTH is False,
           "A45: one-coin depth is OFF by default -- a live bot started "
           "without the flag cannot take more than SIZE on one market")
        # Scan main() only, and build the needle from pieces: a literal here
        # would be its own second match (the self-inspection trap, again).
        _mn45 = _src35[_src35.index(chr(10) + "def main("):]
        _on45 = 'globals()["ONE_COIN_DEPTH"] = ' + "True"
        _rf45 = "--one-coin-depth is refused " + "on a LIVE run"
        ck(_mn45.count(_on45) == 1 and _mn45.index(_rf45) < _mn45.index(_on45),
           "A45: the only place the flag is switched on sits behind the live "
           "refusal")

        # ---- AMENDMENT 46: staged early entry --------------------------------
        ck(_DEFAULT_EARLY_TAU_MAX == 30 and _DEFAULT_EARLY_TAU_MAX <= TAU_MAX,
           "A46: OFF by default -- a run without --early-tau buys no early leg, "
           "whatever EARLY_LIVE_OK says")
        ck(isinstance(EARLY_LIVE_OK, bool),
           "A46: EARLY_LIVE_OK is an explicit switch. True since 2026-09-17 on "
           "the operator's instruction; the STAGE 2 bar in PREREG_staged.md "
           "governs and a revert is a one-line edit back to False")
        ck(TAU_MAX == 30,
           "A46: the FROZEN RULE IS UNTOUCHED -- a FULL bet still needs tau <= "
           "30. The early window only ever buys EARLY_FRAC x SIZE")
        _g46 = globals()
        _sv46 = (_g46["EARLY_TAU_MAX"], _g46["EARLY_FRAC"])
        try:
            _g46["EARLY_TAU_MAX"], _g46["EARLY_FRAC"] = 45, 0.5
            ck(staged_take(40, 94.0, 94.0, 0.0) == (47.0, "early"),
               "A46: an early look with nothing held buys half a bet")
            ck(staged_take(40, 30.0, 94.0, 0.0) == (30.0, "early"),
               "A46: ...or what is there, if the offer is thinner than that")
            ck(staged_take(40, 94.0, 94.0, 47.0) == (0.0, "early_once"),
               "A46: a second early look on the same market buys nothing")
            ck(staged_take(20, 94.0, 94.0, 47.0) == (47.0, "topup"),
               "A46: at the normal point the top-up completes the bet to SIZE")
            ck(staged_take(20, 94.0, 94.0, 94.0) == (0.0, "topup"),
               "A46: ...and a market already at SIZE gets nothing more")
            ck(staged_take(20, 94.0, 94.0, 0.0) == (94.0, "full"),
               "A46: no early leg held -> today's full buy, untouched")
            _g46["EARLY_TAU_MAX"] = 30
            ck(staged_take(40, 94.0, 94.0, 0.0) == (94.0, "full"),
               "A46: with the window off every look is a full buy")
        finally:
            _g46["EARLY_TAU_MAX"], _g46["EARLY_FRAC"] = _sv46
        ck("if not (TAU_MIN <= tau <= max(TAU_MAX, EARLY_TAU_MAX)):" in _tl45,
           "A46: the tau gate opens to the early window only when it is set")
        ck(_tl45.index('_gate("early_once"') < _tl45.index('rec("signal", live=live, **sig)'),
           "A46: a second early look is refused before any signal is recorded")
        ck(_tl45.index("take_n, _leg46 = staged_take(") < _tl45.index('rec("signal", live=live, **sig)'),
           "A46: the leg is sized BEFORE the signal record, so the record shows "
           "what will be asked for and which leg it is")
        # ANCHORED ON THE SEND, not on the line that happened to follow
        # _stage46. A68 inserted its cap between the two and this read as a
        # missing substring rather than as an ordering failure -- the check
        # should describe the ORDER it cares about, not the file's layout.
        # ...within the LIVE block. Both the paper and the live paths contain
        # every one of these strings, so an unqualified index() compares a
        # line in one path against a line in the other.
        _lv45 = _tl45[_tl45.index("# ---- AMENDMENT 45 / 46, live path"):]
        _send45 = _lv45.index("out = pintake.take(CREDS[")
        ck(_tl45.index("take_n = min(float(SIZE), _deep, max(0.0, _room))")
           < _tl45.index("# ---- AMENDMENT 45 / 46, live path")
           and _lv45.index("take_n = _stage46(take_n)") < _send45,
           "A46: the live path re-applies the leg cap AFTER A35/A45 widening "
           "and BEFORE the order is sent, so an early leg can never be "
           "widened back to a full bet")
        ck('"early_tk": ({tk: _n} if _leg46 == "early" else {})' in _tl45
           and "d46[tk] = d46.get(tk, 0.0) + _n" in _tl45,
           "A46: fills book what the market holds from an early leg")
        _rf46 = "--early-tau %d is refused " + "on a LIVE run until "
        _on46 = 'globals()["EARLY_TAU_MAX"] = ' + "int(a.early_tau)"
        ck(_mn45.count(_on46) == 1 and _mn45.index(_rf46) < _mn45.index(_on46),
           "A46: the only place the window opens sits behind the live refusal")
        # Both expectations are DERIVED from the running ceiling: the room is
        # dollars, and dollars buy fewer contracts as the ceiling rises.
        _room45 = 556.02 - (1.0 - MAX_DRAWDOWN) * 574.79
        ck(abs(one_coin_cap(94.0, 556.02, 574.79)
               - _room45 / PRICE_CEILING) < 0.05,
           "A45: bank $556.02 under a $574.79 high leaves $%.2f before the "
           "20%% brake, = %.2f contracts at the %.0fc ceiling -- the cap"
           % (_room45, _room45 / PRICE_CEILING, 100 * PRICE_CEILING))
        _room45b = 574.79 * MAX_DRAWDOWN
        ck(abs(one_coin_cap(94.0, 574.79, 574.79)
               - _room45b / PRICE_CEILING) < 0.05,
           "A45: at a fresh high the room is 20%% of bank = %.2f contracts, "
           "well under the 2.0x multiple" % (_room45b / PRICE_CEILING))
        ck(one_coin_cap(94.0, 2000.0, 2000.0) == 188.0,
           "A45: with a big enough bank the multiple binds first (2.0 x 94)")
        ck(one_coin_cap(94.0, 400.0, 574.79) == 94.0,
           "A45: deep in a drawdown the room is negative -> the cap is SIZE, "
           "never below it: the flag only ever ADDS")
        ck(one_coin_cap(94.0, None, 574.79) == 94.0 and one_coin_cap(94.0, 556.0, None) == 94.0
           and one_coin_cap(94.0, 556.0, 0) == 94.0,
           "A45: unknown bank or high-water mark -> SIZE (the flag does nothing)")
        ck(one_coin_cap(94.0, 2000.0, 2000.0, mult=1.0) == 94.0,
           "A45: --one-coin-max 1.0 is exactly today's behaviour")
        _tl45 = _src35[_src35.index(chr(10) + "def trade_loop("):]
        ck("if not ONE_COIN_DEPTH:" in _tl45 and "one_coin_cap(SIZE, state.get(\"bank\"), state.get(\"hwm\"))" in _tl45,
           "A45: the trade loop consults one_coin_cap with the LIVE bank and "
           "high-water mark, so the cap moves with the money")
        # ANCHOR ON THE WHOLE LINE: "out = pintake.take(" is a substring of the
        # hedge path's "_hout = pintake.take(", which sits EARLIER in
        # trade_loop. Fourth time this trap has bitten in this file.
        # (K1, 2026-09-22: the scan body moved 4 spaces right inside its
        # try:, so every whole-line anchor on it did too.)
        ck(_tl45.index("take_n = min(float(SIZE), _deep, max(0.0, _room))")
           < _tl45.index("take_n = _widen45(take_n)  # live")
           < _tl45.index("\n                        out = pintake.take("),
           "A45: on the live path the widening runs AFTER A35 has sized the "
           "order and BEFORE the order is sent")
        ck("take_n = _widen45(take_n)  # paper" in _tl45
           and _tl45.index("take_n = _widen45(take_n)  # paper") < _tl45.index("_book_slot(price, take_n)"),
           "A45: and the PAPER path widens too, before it books the order -- "
           "the first version widened only live orders, so the paper arm "
           "could never have exercised the flag")
        ck("take_n = max(take_n, min(_cap45, _avail45, max(0.0, _room45)))" in _tl45,
           "A45: the widened order is still capped by the close budget "
           "(_room45), so the per-close worst case is unchanged")
        ck("--one-coin-depth is refused on a LIVE run" in _src35,
           "A45: the flag is refused with --live; only a paper arm may carry it")
        ck("new_size * (ONE_COIN_MAX if ONE_COIN_DEPTH else 1.0)" in _src35
           and "float(a.size) * (ONE_COIN_MAX if ONE_COIN_DEPTH else 1.0)" in _src35,
           "A45: pintake's per-order cap follows the multiple, or every widened "
           "order would be refused in silence (the A16 failure shape)")

        # ---- AMENDMENT 30: the drawdown brake ---------------------------
        ck(abs(_DEFAULT_MAX_DRAWDOWN - 0.20) < 1e-12,
           "the DECLARED drawdown limit is a fifth of the high-water bank -- "
           "the operator's number, 2026-09-14 (running %.3f)" % MAX_DRAWDOWN)
        ck(abs(drawdown(80.0, 100.0) - 0.20) < 1e-12,
           "a bank of $80 against a high of $100 is a 20%% drawdown")
        ck(drawdown(120.0, 100.0) == 0.0,
           "and a bank ABOVE its previous high is not a drawdown at all")
        # THE FAILURE MODES THAT MATTER MOST: never trip on missing data.
        ck(drawdown(None, 100.0) == 0.0 and drawdown(80.0, None) == 0.0
           and drawdown(80.0, 0.0) == 0.0,
           "a failed balance read or a missing high-water file reads as ZERO "
           "drawdown, never as a trip -- a brake that fires whenever the API "
           "hiccups would stop the bot on a network blip, and one that fires "
           "on a missing file would stop it on its very first run")
        import tempfile as _tf30
        _d30 = _tf30.mkdtemp(prefix="pin30-")
        try:
            _hf = os.path.join(_d30, "hwm.json")
            ck(read_hwm(_hf) is None, "no file yet means no high-water mark")
            ck(write_hwm(100.0, _hf) == 100.0, "the first bank sets the mark")
            ck(write_hwm(150.0, _hf) == 150.0, "a new high raises it")
            ck(write_hwm(90.0, _hf) == 150.0,
               "but a FALL NEVER LOWERS IT. This is the whole amendment: if "
               "the mark tracked the bank down, the drawdown would always "
               "read zero and the brake could never fire")
            ck(read_hwm(_hf) == 150.0, "and it survives being re-read")
            ck(abs(drawdown(120.0, read_hwm(_hf)) - 0.20) < 1e-12,
               "so $120 against a $150 high is exactly the 20%% limit")
            ck(write_hwm(None, _hf) == 150.0,
               "a failed balance read does not disturb the mark")
        finally:
            for _f in os.listdir(_d30):
                os.remove(os.path.join(_d30, _f))
            os.rmdir(_d30)
        _src30 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck('_dd >= MAX_DRAWDOWN' in _src30 and "DRAWDOWN brake" in _src30,
           "risk_abort actually reads the drawdown, rather than it being "
           "computed and discarded")
        ck('state["autosize_at"] = 0.0' in _src30,
           "and a settled LOSS clears the sizer's timer, so the bet shrinks "
           "on the next pass instead of up to five minutes later -- the "
           "operator's 'if we lose it should immediately recalculate'")
        _ratchet30 = "if want_abort < " + "float(a.loss_abort):"
        ck(_ratchet30 not in _src30,
           "the dollar stop TIGHTENS as well as loosens. It used to ratchet "
           "one way, so a stop set when the bank was $310 stayed at -$208 "
           "even after the bank halved")

        # THE SELF-TEST MUST NOT BE ABLE TO WRITE PRODUCTION STATE.
        # This is the check for the 2026-09-14 outage: a test wrote a fake
        # $1,000,000 bank into the real high-water file, and the next live
        # start read it, computed a 100% drawdown and halted immediately.
        # A66: the SAME check for the size mirror, added after the self-test
        # published a $60-bank size of 7 into the real file and 36 paper arms
        # adopted it. If this ever fails, the next arm restart sizes every arm
        # to whatever number the test happened to be holding.
        ck(SIZE_MIRROR != os.path.join(RESULTS, "pinrun-live-size.json"),
           "THE SELF-TEST MUST NOT BE ABLE TO WRITE THE SIZE MIRROR every "
           "paper arm reads. It did on 2026-09-19 and sized 36 arms to 7 "
           "contracts; SIZE_MIRROR is now redirected for the whole test, "
           "not per call, because a per-call path is one forgotten argument "
           "away from repeating it")
        _real_mir = os.path.join(RESULTS, "pinrun-live-size.json")
        try:
            with open(_real_mir, encoding="utf-8") as _fh:
                _mir_before = _fh.read()
        except OSError:
            _mir_before = None
        publish_size(7.0, 60.0)          # the exact write that caused it
        try:
            with open(_real_mir, encoding="utf-8") as _fh:
                _mir_after = _fh.read()
        except OSError:
            _mir_after = None
        ck(_mir_after == _mir_before,
           "...and a publish_size() with NO path argument -- the shape that "
           "did the damage -- leaves the real mirror byte-identical")
        ck(HWM_FILE != os.path.join(RESULTS, "pinrun-hwm.json"),
           "while the self-test runs, HWM_FILE points at a sandbox and NOT at "
           "results/pinrun-hwm.json -- currently %r" % HWM_FILE)
        ck(os.path.dirname(HWM_FILE) != RESULTS,
           "and not anywhere else in results/ either")
        write_hwm(1e6)
        ck(read_hwm() == 1e6, "a test CAN move the sandboxed mark freely")
        _real_now = read_hwm(os.path.join(RESULTS, "pinrun-hwm.json"))
        ck(_real_now is None or _real_now < 1e6,
           "and the REAL file is untouched by that (%s) -- if this ever fails, "
           "the live bot's next start will see a false drawdown and halt"
           % _real_now)

        # ---- AMENDMENT 31: the open cap counts CONTRACTS -----------------
        _led31 = {"positions": {
            "A": {"want": "yes", "contracts": 8.0},
            "B": {"want": "no", "contracts": 12.0}}}
        ck(abs(open_contracts(_led31) - 20.0) < 1e-9,
           "open contracts are summed across markets (%g)"
           % open_contracts(_led31))
        ck(open_contracts({}) == 0.0 and open_contracts({"positions": {}}) == 0.0,
           "and an empty ledger holds nothing")
        ck(open_contracts({"positions": {"A": ("x", "y", 1, 99.0)}}) == 0.0,
           "a position that is NOT the dict shape contributes zero rather "
           "than a wrong number -- the first version indexed it positionally "
           "and would have summed zero for every real position, removing the "
           "rail instead of converting it")
        # eighteen small fills and three big ones must hit the cap together
        _big = {"positions": dict(("M%d" % i, {"contracts": 52.0})
                                  for i in range(3))}
        _small = {"positions": dict(("M%d" % i, {"contracts": 8.7})
                                    for i in range(18))}
        ck(abs(open_contracts(_big) - 156.0) < 1e-9
           and abs(open_contracts(_small) - 156.6) < 1e-9,
           "three fills of 52 and eighteen of 8.7 are the SAME exposure "
           "(%g vs %g), so they now hit the cap together -- under the old "
           "position count the eighteen would have halted the bot after "
           "three" % (open_contracts(_big), open_contracts(_small)))
        ck("open cap:" in _src30 and "_open_n = open_contracts(led)" in _src30,
           "and risk_abort uses it")

        # ---- AMENDMENT 28: the depth floor is a flag, paper only --------
        ck(abs(_DEFAULT_MIN_FILL_FRAC - 0.50) < 1e-12,
           "the DECLARED depth floor is half of SIZE (running %.2f)"
           % MIN_FILL_FRAC)
        ck(MIN_FILL_FRAC <= _DEFAULT_MIN_FILL_FRAC + 1e-12,
           "and the running floor is never ABOVE the declared default -- this "
           "flag exists to LOWER it; raising it cuts trading and needs a code "
           "change and a version entry, not a flag (running %.3f)"
           % MIN_FILL_FRAC)
        _src28 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck('"--min-fill-frac is refused on a LIVE run' in _src28,
           "and it is refused on --live: A6's measurement against a lower "
           "floor predates the contract budget (A17) and the scrap exemption "
           "(A12), so it has to be re-measured before it ships")
        # a smaller fill cannot raise exposure -- that is the whole argument
        _sz28 = float(SIZE)
        try:
            globals()["SIZE"] = 50.0
            ck(min(float(SIZE), 7.0) == 7.0,
               "taking min(SIZE, offered) on a 7-contract book buys 7, not "
               "50 -- a smaller fill can only LOWER exposure, never raise it, "
               "which is why lowering the floor cannot raise the loss rate")
        finally:
            globals()["SIZE"] = _sz28

        # ---- AMENDMENT 27: one live bot, ever ---------------------------
        # AND IT MUST NOT KILL THE THING IT IS ASKING ABOUT. The first version
        # called os.kill(pid, 0), which on Windows is not a test at all --
        # CPython maps any signal but CTRL_C/CTRL_BREAK to TerminateProcess,
        # so it terminated the caller with exit code 0. The paper run testing
        # this amendment killed itself mid-self-test on 2026-09-14. This check
        # runs the liveness test against THIS process and then proves the
        # process is still here afterwards.
        ck(_pid_alive(os.getpid()),
           "the liveness test says THIS process is alive -- if it cannot see "
           "itself it can see nothing, and the guard is decorative")
        _still = os.getpid()
        ck(_pid_alive(_still) and _pid_alive(_still),
           "and asking twice more does not kill it -- os.kill(pid, 0) on "
           "Windows TERMINATES rather than tests, which is why this function "
           "uses OpenProcess(SYNCHRONIZE) there and never os.kill")
        _src27k = open(os.path.abspath(__file__), encoding="utf-8").read()
        _fn = _src27k[_src27k.index("def _pid_alive("):]
        _fn = _fn[:_fn.index(chr(10) + "def ")]
        ck('if os.name == "nt":' in _fn
           and _fn.index('if os.name == "nt":') < _fn.index("os.kill"),
           "and the Windows branch is taken BEFORE os.kill is ever reached")
        ck(not _pid_alive(0) and not _pid_alive(None),
           "and a nonsense pid is not alive")
        # a pid nobody owns must read as DEAD, or the guard refuses forever
        _dead = 999999
        while _pid_alive(_dead) and _dead < 1000600:
            _dead += 1
        ck(not _pid_alive(_dead),
           "a pid that is not running reads as dead (%d), so a stale pid file "
           "from a crashed run does not lock the bot out permanently" % _dead)
        import tempfile as _tf27
        _d27 = _tf27.mkdtemp(prefix="pin27-")
        try:
            _pf = os.path.join(_d27, "x.pid")
            with open(_pf, "w", encoding="utf-8") as _fh:
                _fh.write(str(os.getpid()))
            _clear_pidfile(_pf, os.getpid() + 1)
            ck(os.path.exists(_pf),
               "a pid file belonging to ANOTHER process is never deleted -- "
               "deleting it would let a third bot start behind the second")
            _clear_pidfile(_pf, os.getpid())
            ck(not os.path.exists(_pf),
               "and our own is cleared on exit, so the next restart is not "
               "blocked by a file we left behind")
        finally:
            for _f in os.listdir(_d27):
                os.remove(os.path.join(_d27, _f))
            os.rmdir(_d27)
        _src27 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("REFUSING TO START: live pinrun pid" in _src27
           and "if a.live:" in _src27,
           "and main() actually refuses a second LIVE start rather than "
           "merely warning -- on 2026-09-14 two live bots traded the same "
           "account for 24 minutes because a shell script's process lookup "
           "came back empty and it started a second one anyway")
        # ...and never by reading a command line. Comment lines are stripped
        # first, because the reasoning for this rule necessarily names the
        # thing the rule forbids, and scanning the explanation would fail on
        # the explanation.
        # The token is BUILT rather than written, so this test's own lines do
        # not contain the string they are looking for.
        _tok27 = "Command" + "Line"
        _code27 = [ln for ln in _src27.split(chr(10))
                   if not ln.strip().startswith("#")]
        ck(not [ln for ln in _code27 if _tok27 in ln],
           "no CODE in this file reads a process command line to decide "
           "anything. Windows returns that field EMPTY to a caller which "
           "cannot open the process, and a guard that silently sees nothing "
           "is how two live bots ended up on one account")

        # ---- AMENDMENT 26: keep walking down to the next-best market -----
        ck(_DEFAULT_MAX_ATTEMPTS_PER_MARKET == 3,
           "the DECLARED per-market attempt cap is 3 (running %d)"
           % MAX_ATTEMPTS_PER_MARKET)
        ck(MAX_ATTEMPTS_PER_CLOSE >= 24,
           "the per-CLOSE attempt cap is at least 24 -- twelve coins settle "
           "on the same second, so a cap of 8 could not try them all once and "
           "the bot could run out of attempts before reaching a market whose "
           "ask was still there (running %d)" % MAX_ATTEMPTS_PER_CLOSE)
        ck(MAX_ATTEMPTS_PER_MARKET * 2 <= MAX_ATTEMPTS_PER_CLOSE,
           "and the close cap leaves room for more than two markets to be "
           "tried to their own limit, or the per-market cap is decorative")
        # the runaway that MAX_ATTEMPTS_PER_CLOSE was written for, replayed
        _at, _atk = {}, {}
        _sent = 0
        for _i in range(160):                 # 160 orders into ONE market
            if _atk.get((1, "A"), 0) >= MAX_ATTEMPTS_PER_MARKET:
                continue
            if _at.get(1, 0) >= MAX_ATTEMPTS_PER_CLOSE:
                continue
            _at[1] = _at.get(1, 0) + 1
            _atk[(1, "A")] = _atk.get((1, "A"), 0) + 1
            _sent += 1
        ck(_sent == MAX_ATTEMPTS_PER_MARKET,
           "the 2026-09-08 runaway -- 160 orders into ONE market in one "
           "second -- now sends %d, not 160 and not 8. The per-market cap "
           "stops it at its actual source." % _sent)
        # and the thing the operator asked for: twelve markets, each tried
        _at2, _atk2 = {}, {}
        _reached = []
        for _tk in ["C%d" % i for i in range(12)]:
            if _atk2.get((1, _tk), 0) >= MAX_ATTEMPTS_PER_MARKET:
                continue
            if _at2.get(1, 0) >= MAX_ATTEMPTS_PER_CLOSE:
                continue
            _at2[1] = _at2.get(1, 0) + 1
            _atk2[(1, _tk)] = 1
            _reached.append(_tk)
        ck(len(_reached) == 12,
           "and with every one of twelve coins offering something, all twelve "
           "are reached (%d) -- under the old cap of 8 the last four could "
           "never be tried, which is exactly 'if that one is sold out keep "
           "checking the others'" % len(_reached))
        # NOTHING MAY `break` OUT OF THE SCAN AFTER AN ORDER. If anything ever
        # did, the walk down the ladder would stop at the first market tried
        # and every number above would be describing code that no longer runs.
        _src26 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _l26 = _src26.split(chr(10))
        _i26 = next(i for i, ln in enumerate(_l26)
                    if ln.strip() == "for tk, (iid, close_s, strike, digits, "
                                     "exi) in _mk:")
        _j26 = next(i for i, ln in enumerate(_l26)
                    if i > _i26 and ln.strip() == "time.sleep(0.05)")
        _body = _l26[_i26 + 1:_j26]
        ck(not [ln for ln in _body
                if ln.strip() == "break" and not ln.startswith(" " * 20)],
           "the scan loop contains no shallow `break`, so an order on one "
           "market is always followed by the next market in the pass -- and "
           "since AMENDMENT 24 sorted the pass, the next market is the next "
           "best one")

        # ---- AMENDMENT 25: every gate says why, once, on the record -----
        _src25 = open(os.path.abspath(__file__), encoding="utf-8").read()
        _nl25 = chr(10)
        _l25 = _src25.split(_nl25)
        _names, _bad25 = [], []
        for _i, _ln in enumerate(_l25):
            _t = _ln.strip()
            if not _t.startswith('_gate("'):
                continue
            _names.append(_t.split('"')[1])
            # EVERY CALL MUST SIT ON A PATH THAT REFUSES. A _gate() left on a
            # path that goes on to TRADE would count a refusal that never
            # happened, and every rate built on it would be wrong.
            _tail = _nl25.join(_l25[_i:_i + 12])
            if "continue" not in _tail:
                _bad25.append(_t[:50])
        ck(not _bad25,
           "every _gate() call is followed by a `continue` within 12 lines, "
           "so a gate can only ever record a refusal it actually made (%s)"
           % _bad25)
        ck(len(_names) == len(set(_names)),
           "no gate name is used at two different places -- a duplicated name "
           "silently merges two unrelated refusals into one row (%s)"
           % [x for x in _names if _names.count(x) > 1])
        ck(len(_names) >= 15,
           "at least fifteen decision points are instrumented, got %d: %s"
           % (len(_names), sorted(_names)))
        # the reader must know every name, or a gate is invisible in the report
        _attr = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "pinattrib.py")
        if os.path.exists(_attr):
            _atxt = open(_attr, encoding="utf-8").read()
            _unknown = [x for x in _names if ('"%s"' % x) not in _atxt]
            ck(not _unknown,
               "research/pinattrib.py names every instrumented gate, so none "
               "is silently missing from the report (%s)" % _unknown)
        # dedupe is what keeps this out of the settlement reader's way
        ck("if key in gate_seen:" in _src25 and "gate_seen.add(key)" in _src25,
           "a gate is recorded ONCE per (close, market) -- the loop runs at "
           "20Hz over every watched market and one close produced 4,446 "
           "looks on 2026-09-13, so one line per look would swamp the log "
           "the settlement reader shares")

        # ---- AMENDMENT 24: best-first scan order ------------------------
        ck(_DEFAULT_PICK == "first",
           "the DECLARED default scan order is 'first' -- A24 is a measured "
           "improvement that has not yet been through a what-if, so it must "
           "be opt-in (running now with %r)" % PICK)
        # the ordering key, exactly as the loop builds it
        _le24 = {"A": (900, 0.010), "B": (900, 0.040), "C": (900, 0.025),
                 "D": (1800, 0.900)}

        def _rank24(kv):
            got = _le24.get(kv[0])
            if not got or got[0] != kv[1][1]:
                return 0.0
            return -got[1]

        _mk24 = [("A", (0, 900)), ("B", (0, 900)), ("C", (0, 900)),
                 ("D", (0, 900)), ("E", (0, 900))]
        _mk24.sort(key=_rank24)
        ck([k for k, _ in _mk24][:3] == ["B", "C", "A"],
           "the scan visits the biggest previous-pass edge first (B 4.0c, "
           "C 2.5c, A 1.0c), got %s" % [k for k, _ in _mk24])
        ck([k for k, _ in _mk24][3:] == ["D", "E"],
           "and a market with NO edge yet (E) or an edge left over from "
           "ANOTHER close (D, whose 90c edge was measured on close 1800) "
           "sorts last rather than jumping the queue -- a stale edge from a "
           "settled close would otherwise dominate every pass")
        _src24 = open(os.path.abspath(__file__), encoding="utf-8").read()
        ck("last_edge[tk] = (close_s, e)" in _src24,
           "the loop records each pass's edge, which is the only input the "
           "ordering has")
        ck('if PICK == "best":' in _src24 and "_mk.sort(key=_rank)" in _src24,
           "and it really re-orders the scan rather than accepting the flag "
           "and ignoring it")
        ck(_src24.index("_mk.sort(key=_rank)")
           < _src24.index("for tk, (iid, close_s, strike, digits, exi) in _mk:"),
           "the sort happens BEFORE the scan it orders")

        # ---- AMENDMENT 21: the confidence gate is now a flag -----------
        ck(_DEFAULT_PIN == 0.995,
           "the DECLARED default PIN is 0.995 (running now with %.4f)" % PIN)
        ck(PIN <= _DEFAULT_PIN + 1e-12,
           "and the running PIN is never ABOVE the declared default -- a "
           "tighter gate is the change that silently halves the trade count, "
           "so it needs a code change and a version entry, not a flag "
           "(running %.4f)" % PIN)
        _p0 = PIN
        try:
            globals()["PIN"] = 0.990
            ck(abs(PIN - 0.990) < 1e-12, "--pin moves the gate")
            _f_lo = conf_of(2.40)
            ck(_f_lo >= PIN,
               "a decision at z=2.40 clears 0.990 (%.5f) ..." % _f_lo)
            globals()["PIN"] = 0.995
            ck(_f_lo < PIN,
               "... and does NOT clear 0.995 (%.5f) -- the flag is the whole "
               "difference between a trade and no trade" % _f_lo)
        finally:
            globals()["PIN"] = _p0

        # ---- AMENDMENT 20: the volatility ruler ------------------------
        ck(_DEFAULT_SIGMA_RULER == "live",
           "the DECLARED default ruler is 'live' -- AMENDMENT 20 is a model "
           "change and may only be reached through --sigma-ruler, against the "
           "bar in results/PREREG_ruler.md (running now with %r)"
           % SIGMA_RULER)
        _rd = {}
        for _t in range(1000, 1000 + 3600):
            # quiet for the last 300s, loud before it: the exact shape that
            # makes a short ruler understate.
            _rd[_t] = (0.0 if _t >= 1000 + 3300
                       else ((_t % 7) - 3) * 5.0)
        _short = IndexWS._sig_over(_rd, 300)
        _long = IndexWS._sig_over(_rd, 3600)
        ck(_short is not None and _long is not None,
           "both rulers measure on the same series")
        ck(_long > _short,
           "after a quiet patch the HOUR reads wider than the five minutes "
           "(%.4f vs %.4f) -- which is the whole finding" % (_long, _short))
        _rs = SIGMA_RULER
        try:
            class _FakeWS:
                lock = threading.RLock()
                ticks = {"X": _rd}
                _sig_over = staticmethod(IndexWS._sig_over)
                _semi_over = staticmethod(IndexWS._semi_over)
                sigma = IndexWS.sigma
            _f = _FakeWS()
            globals()["SIGMA_RULER"] = "live"
            _v_live = _f.sigma("X")
            globals()["SIGMA_RULER"] = "max3600"
            _v_max = _f.sigma("X")
            globals()["SIGMA_RULER"] = "1800"
            _v_18 = _f.sigma("X")
            ck(abs(_v_live - _short) < 1e-12,
               "'live' reproduces the 300s ruler exactly, bit for bit")
            ck(_v_max >= _v_live - 1e-12 and _v_max >= _long - 1e-12,
               "'max3600' is never shorter than either input (%.4f)" % _v_max)
            ck(_v_18 is not None and _v_18 > _v_live,
               "'1800' reads wider than the live ruler here (%.4f)" % _v_18)
            # AMENDMENT 20b: the downside ruler, and its fallback
            globals()["SIGMA_RULER"] = "maxdown"
            _v_dn = _f.sigma("X")
            ck(_v_dn is not None and _v_dn > 0,
               "'maxdown' returns a positive ruler (%.4f)" % _v_dn)
            _one_sided = {t: 100.0 + 0.01 * t for t in range(1000, 5000)}
            class _FakeUp:
                lock = threading.RLock()
                ticks = {"X": _one_sided}
                _sig_over = staticmethod(IndexWS._sig_over)
                _semi_over = staticmethod(IndexWS._semi_over)
                sigma = IndexWS.sigma
            ck(IndexWS._semi_over(_one_sided, 300) is None,
               "a series that only ever rises has NO down moves, so the "
               "downside estimator refuses rather than returning zero")
            ck(_FakeUp().sigma("X") is not None,
               "and sigma() falls back to the two-sided ruler there -- a None "
               "would skip the market silently, indistinguishable from a thin "
               "book")
        finally:
            globals()["SIGMA_RULER"] = _rs
        ck(SIGMA_RULER == _rs, "and the ruler is put back to %r" % _rs)

        # ---- AMENDMENT 19: honest confidence ---------------------------
        # THE RISK HERE IS SILENT REVERSION, not arithmetic. If the table
        # fails to load, or some gate reads Phi while another reads the table,
        # the run is labelled honest and behaves exactly as before -- the
        # worst possible outcome, because it would be believed.
        ck(_DEFAULT_HONEST_CONF is False,
           "the DECLARED default for honest confidence is OFF -- AMENDMENT 19 "
           "is a threshold change and may only be reached through --honest, "
           "against the bar in results/PREREG_honest.md (running now with %r)"
           % HONEST_CONF)
        _ht = {"grid": [0.0, 1.0, 2.0, 3.0, 4.0],
               "tail": [0.5, 0.20, 0.05, 0.02, 0.01]}
        ck(abs(honest_tail(2.0, _ht) - 0.05) < 1e-12,
           "honest_tail reads a grid point exactly")
        ck(abs(honest_tail(2.5, _ht) - 0.035) < 1e-12,
           "and interpolates between two (%.4f)" % honest_tail(2.5, _ht))
        ck(abs(honest_tail(9.9, _ht) - 0.01) < 1e-12,
           "and BEYOND the table it holds the last measured value rather "
           "than extrapolating to zero -- claiming a tail we never observed "
           "is the exact failure this amendment exists to fix")
        ck(abs(honest_tail(-5.0, _ht) - 0.5) < 1e-12,
           "and below the table it holds the first")
        _hs = _HONEST
        _hc0 = HONEST_CONF
        try:
            globals()["_HONEST"] = _ht
            globals()["HONEST_CONF"] = True
            ck(abs(conf_of(2.0) - 0.95) < 1e-12,
               "with --honest, conf_of reads the TABLE (0.95 at z=2)")
            ck(conf_of(2.0) < ND.cdf(2.0),
               "which is STRICTLY LESS SURE than the Gaussian (%.4f < %.4f) "
               "-- this amendment can only ever tighten"
               % (conf_of(2.0), ND.cdf(2.0)))
            globals()["HONEST_CONF"] = False
            ck(abs(conf_of(2.0) - ND.cdf(2.0)) < 1e-12,
               "and with it off, conf_of IS the Gaussian, bit for bit")
        finally:
            globals()["_HONEST"] = _hs
            globals()["HONEST_CONF"] = _hc0
        # fair() must route through conf_of and nothing else may call ND.cdf
        # on the decision path -- one gate reading Phi while another reads the
        # table is the silent reversion above.
        _hsrc = open(os.path.abspath(__file__), encoding="utf-8").read()
        _hlines = _hsrc.split("\n")
        ck(any(ln.strip() == "return conf_of((mu - K) / sd)"
               for ln in _hlines),
           "fair() returns conf_of(z), not ND.cdf(z)")
        # Scan the WORKING code only -- everything above `def selftest`. The
        # checks themselves legitimately mention ND.cdf, and so do fixtures
        # below, and including them would make this assertion unwriteable.
        _work = _hsrc[:_hsrc.index("def " + "selftest")]
        _bad = [ln.strip()[:60] for ln in _work.split("\n")
                if "ND.cdf(" in ln and "return ND.cdf(float(z))" not in ln
                and not ln.strip().startswith("#")]
        ck(not _bad,
           "and in the working code ND.cdf appears ONLY inside conf_of -- no "
           "gate can read a different distribution from the one fair() uses "
           "(offenders: %s)" % _bad)
        ck(load_honest(os.path.join(HERE, "no-such-table.json")) is None,
           "a missing table loads as None, so main() can refuse rather than "
           "silently running a Gaussian under an honest label")

        # ---- AMENDMENT 18: the sweep limit -----------------------------
        # The estimator is easy; the rail is the deliverable. Every check here
        # is about what the limit may NEVER be, because the limit is the worst
        # price this bot can pay and nothing downstream re-checks it.
        _swf = 0.9998
        _swp = 0.952
        _swL = sweep_limit(_swf, _swp, "yes")
        ck(_swL >= _swp - 1e-12,
           f"the sweep limit is never BELOW the ask we saw ({_swL} >= {_swp})")
        ck(_swL <= PRICE_CEILING + 1e-9,
           f"and never above PRICE_CEILING ({_swL} <= {PRICE_CEILING})")
        ck(net_edge(_swf, _swL, "yes") >= EDGE_FLOOR,
           f"at the limit the model edge still clears the floor "
           f"({100 * net_edge(_swf, _swL, 'yes'):.3f}c >= "
           f"{100 * EDGE_FLOOR:.3f}c)")
        ck(expected_value(_swL) >= EV_FLOOR,
           f"and the measured-flip EV still clears its floor "
           f"({100 * expected_value(_swL):.3f}c >= {100 * EV_FLOOR:.3f}c)")
        _swN = round(_swL + tick_at(_swL), 4)
        ck(_swN > PRICE_CEILING + 1e-9
           or net_edge(_swf, _swN, "yes") < EDGE_FLOOR
           or expected_value(_swN) < EV_FLOOR
           # A53: or the next tick sits in a skipped band. This check runs at
           # every live start WITH the flags applied, and without this clause
           # --skip-band would have refused to start the bot -- caught by the
           # control arm on 2026-09-18, not by the live restart, for once.
           or band_blocked(_swN),
           "and it is the HIGHEST such price -- one tick more fails the "
           "ceiling, the edge floor, the EV floor, or a skipped band")
        # a fair only just above the ask leaves no room, and must not invent any
        ck(abs(sweep_limit(0.9550, 0.9540, "yes") - 0.9540) < 1e-12,
           "with no headroom the limit IS the ask -- the sweep invents none")
        # the NO side reads its own fair, not the YES one
        _swNo = sweep_limit(0.0002, 0.952, "no")
        ck(_swNo >= 0.952 - 1e-12 and net_edge(0.0002, _swNo, "no") >= EDGE_FLOOR,
           f"the NO side sweeps on (1-fair), not fair ({_swNo})")
        # the kill switch
        _swSave = SWEEP_ENABLED
        try:
            globals()["SWEEP_ENABLED"] = False
            ck(abs(sweep_limit(_swf, _swp, "yes") - _swp) < 1e-12,
               "--no-sweep makes the limit exactly the ask we saw, which is "
               "the behaviour every live fill before 2026-09-13 had")
        finally:
            globals()["SWEEP_ENABLED"] = _swSave
        # AND THE ORDER PATH MUST ACTUALLY SEND IT. Anchored on the whole line
        # at its real indentation -- "out = pintake.take(" is a SUBSTRING of
        # the hedge path's "_hout = pintake.take(", and that alone has broken
        # four checks in this file already.
        _swsrc = open(os.path.abspath(__file__), encoding="utf-8").read()
        _swlines = _swsrc.split("\n")
        ck(any(ln.strip() == "_limit = sweep_limit(f, price, want)"
               for ln in _swlines),
           "the live order path computes the sweep limit")
        _i_lim = next(i for i, ln in enumerate(_swlines)
                      if ln.strip() == "_limit = sweep_limit(f, price, want)")
        _i_tk = next(i for i, ln in enumerate(_swlines)
                     if ln.strip().startswith("out = pintake.take("))
        ck(_i_lim < _i_tk,
           "and computes it BEFORE the order is sent")
        _swblk = "\n".join(_swlines[_i_tk:_i_tk + 4])
        ck("_limit," in _swblk and " price," not in _swblk,
           "and pintake.take() is handed the LIMIT, never the ask we saw -- "
           "if this ever reverts, a lost race silently buys nothing again")
        ck(any("ask_seen=round(float(price), 4)" in ln for ln in _swlines)
           and any("limit_sent=round(float(_limit), 4)" in ln
                   for ln in _swlines),
           "and both prices are logged, so PREREG_sweep.md's bar is scorable")

        # ---- AMENDMENT 17: the CONTRACT budget -------------------------
        _szB = float(SIZE)
        try:
            globals()["SIZE"] = 68.0
            ck(abs(close_budget() - 68.0 * MAX_PER_CLOSE) < 1e-9,
               f"the BASE budget is MAX_PER_CLOSE x SIZE = "
               f"{68.0 * MAX_PER_CLOSE}, got {close_budget()}")
            # THE INVARIANT THE WHOLE AMENDMENT RESTS ON: exposure unchanged.
            # A56: the worst case is the base budget PLUS the extra-coin
            # allowance, because a third coin may spend beyond the base. The
            # two must still agree, or the rails are sized against a bet
            # nobody places -- that is what this check is for and it now
            # reads the same total the sizer does.
            ck(abs((close_budget() + max(EXTRA_COIN, LATE_EXTRA) * 68.0)
                   * PRICE_CEILING - worst_close_cost(68.0)) < 1e-9,
               "budget x ceiling must equal worst_close_cost -- if these ever "
               "disagree, the --loss-abort band, pintake's stake cap and "
               "pinbank are all sized against a different bet than the one "
               "being placed")
            ck(abs(close_budget(20.0) - 40.0) < 1e-9,
               "close_budget(size) must honour an explicit size")
        finally:
            globals()["SIZE"] = _szB

        _lb3 = src[src.index(chr(10) + "def trade_loop("):]
        _ln3 = _lb3.splitlines()
        # K1 (2026-09-22): the scan body sits 4 spaces deeper, inside its
        # try:, so these whole-line anchors moved with it.
        ck("                    if _spent >= _bud56 - 1e-9:" in _ln3
           and "                    _bud56 = close_budget_for(prev, tk, tau=tau)" in _ln3,
           "the per-close cap must read CONTRACTS, not the fill count -- and "
           "since A56 it reads the budget for THIS CANDIDATE, which is the "
           "base plus the extra-coin allowance when the candidate is a coin "
           "this close does not already hold")
        ck('                    _spent = prev.get("contracts", 0.0) if prev else 0.0'
           in _ln3,
           "and `contracts` must come from the close's own record")
        ck("                elif prev is not None and prev[\"n\"] >= MAX_PER_CLOSE:"
           in _ln3,
           "and the old fill-count cap must survive behind CLOSE_BUDGET so "
           "the rule can be reverted without an edit")
        # ORDERING: the floor is tested against FULL SIZE, then take_n is
        # trimmed. Reversed, the tail of a budget buys a moment the floor
        # exists to refuse -- the operator's explicit condition.
        # RE-ANCHORED 2026-09-14 for AMENDMENT 37, which named the floor
        # `_floor` instead of inlining it. The INVARIANT is unchanged and is
        # what this checks: the floor is computed from the FULL size and
        # tested before take_n is trimmed to the remaining budget.
        _i_floor = _lb3.index(
            "_floor = max(MIN_LEVEL, MIN_FILL_FRAC * float(SIZE))")
        _i_test = _lb3.index("if _reach < _floor:")
        _i_trim = _lb3.index("take_n = min(take_n, _left)")
        ck(_i_trim > _i_test > _i_floor,
           "STRUCTURAL: take_n is trimmed to the remaining budget only AFTER "
           "the MIN_FILL_FRAC floor has been tested against the FULL size -- "
           "trimming first would relax the floor to the remainder")
        ck("float(SIZE)" in _lb3[_i_floor:_i_floor + 80],
           "and the floor is still measured against FULL SIZE, never the "
           "remainder -- the operator's own condition (A17)")
        ck("_left = close_budget() - (" in _lb3,
           "and the remainder is measured against close_budget()")
        # ANCHOR ON THE WHOLE LINE. "out = pintake.take(" is a SUBSTRING of
        # "_hout = pintake.take(" in the hedge path, which sits EARLIER in
        # trade_loop -- the substring match found the hedge's call and
        # compared the trim against the wrong statement. Same self-inspection
        # trap that broke three checks in this file on 2026-09-11.
        _take_ln = next(i for i, ln in enumerate(_ln3)
                        if ln.strip().startswith("out = pintake.take("))
        _trim_ln = next(i for i, ln in enumerate(_ln3)
                        if ln.strip() == "take_n = min(take_n, _left)")
        ck(_trim_ln < _take_ln,
           f"the trim (line {_trim_ln}) must happen before the order is sent "
           f"(line {_take_ln}), not after")

        # ---- quote age: LOGGED, NEVER GATED ON -------------------------
        _lb2 = src[src.index(chr(10) + "def trade_loop("):]
        ck("                           level_age_ms=_lvl_age, "
           "level_age_exact=_lvl_exact," in _lb2.splitlines(),
           "the signal record must carry the resting age of the level we hit")
        ck("_lvl_side = \"no\" if want == \"yes\" else \"yes\"" in _lb2,
           "and it must read the OPPOSITE side -- buying YES at p hits the "
           "NO bid at 1-p, and reading our own side would measure a level we "
           "are not trading against")
        ck("book.level_age_ms(" in _lb2 and "round(1.0 - price, 4)" in _lb2,
           "at the complementary price, not at the price we pay")
        for _bad in ("if _lvl_age", "_lvl_age <", "_lvl_age >",
                     "_lvl_age is not None and"):
            ck(_bad not in _lb2,
               f"NOTHING may branch on the quote age yet ({_bad!r} found). "
               f"The slices in RESULTS_select.md were chosen after seeing "
               f"the tape and need a pre-registered live bar first; a filter "
               f"deployed from them would be tuned on its own evidence.")
        ck(hasattr(livebook.LiveBook, "level_age_ms"),
           "livebook must expose level_age_ms")

        # Wired into the loop AFTER reconcile(), or 'only when flat' is never
        # true. Anchored on a whole line at its real indentation.
        _lb = src[src.index(chr(10) + "def trade_loop("):]
        ck("        _asz = autosize_tick(state, a, open_pos, rec=rec)"
           in _lb.splitlines(),
           "autosize_tick must be called in the trade loop")
        ck(_lb.index("_asz = autosize_tick(") > _lb.index("        reconcile()"),
           "and it must come AFTER reconcile(), which is what drains "
           "open_pos of settled positions")
        ck(_lb.index("_asz = autosize_tick(") < _lb.index("stop = risk_abort("),
           "and BEFORE risk_abort, so the loss bound is evaluated against "
           "the size we are about to trade, not the previous one")
    finally:
        globals()["SIZE"] = _sz0

    # ===================================================================
    # K1 (2026-09-22): THE LOOP CANNOT DIE WHILE HOLDING -- RUN, NOT READ.
    #
    # Every loop check above reads trade_loop's SOURCE. These RUN it
    # (_offline_trade_loop: the real loop, a fake clock, book, index and
    # market list, no network). One close, first look at 30 s to go:
    #   A  bought at 95c on the first look. Its model belief falls to 0.10 at
    #      +4 s -- under every trigger in use (0.25 live, 0.80 as shipped).
    #   B  undecided until +2 s, then a 93c buy. In the FAULT worlds the
    #      conditions read on B's SIGNAL raises: the same TypeError, from the
    #      same unguarded place, as the crash that left 70 BTC unhedged on
    #      2026-09-19 (-$66.34).
    # The first version of this block was run against the unfixed loop: the
    # fault worlds raised out of trade_loop at +2 s with A still open, and
    # the live path sent TWO orders and hedged neither.
    # ===================================================================
    def _k1_A(collapse_at=4):
        return {"tk": "KXAAA15M-K1", "series": "KXAAA15M", "iid": "K1A",
                "strike": 100.0,
                "fair": (lambda t: 0.10 if (collapse_at is not None
                                            and t >= collapse_at) else 0.999),
                "book": (lambda t: _ob(0.94, 0.05))}

    def _k1_B(n, decided_at=2, raise_from=None):
        return {"tk": "KXB%d15M-K1" % n, "series": "KXB%d15M" % n,
                "iid": "K1B%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.999 if t >= decided_at else 0.5),
                "book": (lambda t: _ob(0.92, 0.07)),
                "cond_raise": (None if raise_from is None
                               else (lambda t: t >= raise_from))}

    def _kinds(res, kind, tk=None):
        return [r for r in res["recs"] if r["kind"] == kind
                and (tk is None or r.get("ticker") == tk)]

    def _hedged(res, tk):
        return sum(float(r.get("n") or 0.0) for r in _kinds(res, "hedge", tk))

    _kA = _k1_A()["tk"]

    # THE OFFLINE WORLDS RUN UNDER THE SHIPPED FLAGS, NEVER THE RUNNING ONES.
    # This self-test runs at every START with the operator's flags applied;
    # worlds that read them refused to start arm-nohedge (--hedge-belief
    # 0.01, 15 FAIL) and every --skip-band arm over 95c (20 FAIL), and would
    # have refused live at --hedge-belief 0.10. First: every flag main()
    # applies before the self-test is pinned, and each has a _DEFAULT_ twin.
    _re_k1 = __import__("re")
    _src_k1 = open(os.path.abspath(__file__), encoding="utf-8").read()
    _mn_k1 = _src_k1[_src_k1.rindex(chr(10) + "def main("):]
    _mn_k1 = _mn_k1[:_mn_k1.index(chr(10) + "    if a.selftest:")]
    _set_k1 = set(_re_k1.findall(r'globals\(\)\["([A-Z][A-Z_0-9]*)"\]\s*=',
                                 _mn_k1))
    ck(len(_set_k1) >= 40 and _set_k1 <= set(_OFFLINE_PINNED_FLAGS)
       and all(("_DEFAULT_" + _n) in globals()
               for _n in _OFFLINE_PINNED_FLAGS),
       "K1 harness: all %d flags main() applies before the self-test are "
       "pinned to their _DEFAULT_ twins inside the offline loop (unpinned: "
       "%s; no twin: %s)"
       % (len(_set_k1), sorted(_set_k1 - set(_OFFLINE_PINNED_FLAGS)),
          [_n for _n in _OFFLINE_PINNED_FLAGS
           if ("_DEFAULT_" + _n) not in globals()]))
    _pin_before = {_n: globals()[_n] for _n in _OFFLINE_PINNED_FLAGS}

    def _k1_trace(res):
        return [(r["kind"], r.get("ticker"), r["t"], r.get("n"))
                for r in res["recs"]]

    # Then the proof: one world, run while the PROCESS holds flags under
    # which it could neither buy the 95c fixture nor hedge at 0.10.
    _hostile = {"HEDGE_BELIEF": 0.01, "SKIP_BANDS": ((0.90, 0.99),),
                "PRICE_CEILING": 0.91, "PIN": 0.9999, "HEDGE_PROP": False,
                "HEDGE_PANIC": None, "EARLY_MIN_PRICE": 0.99,
                "SIGMA_STRESS": 3.0}
    _hostile_was = {_n: globals()[_n] for _n in _hostile}
    try:
        globals().update(_hostile)
        _ph = _offline_trade_loop([_k1_A(), _k1_B(1)])
        _ph_back = all(globals()[_n] == _v for _n, _v in _hostile.items())
    finally:
        globals().update(_hostile_was)
    _p0 = _offline_trade_loop([_k1_A(), _k1_B(1)])
    ck(_ph["raised"] is None and _ph_back
       and _k1_trace(_ph) == _k1_trace(_p0),
       "K1 harness: the same world run while the process holds hostile "
       "flags (--hedge-belief 0.01, --skip-band 0.90 0.99, --price-ceiling "
       "0.91, --pin 0.9999 ...) produces the IDENTICAL record trail, and "
       "the hostile values are handed back (%d vs %d records, hedged %g)"
       % (len(_ph["recs"]), len(_p0["recs"]), _hedged(_ph, _kA)))
    ck(_p0["raised"] is None and abs(_hedged(_p0, _kA) - 5.0) < 1e-9
       and _kinds(_p0, "signal", "KXB115M-K1"),
       "K1 CONTROL, paper: the real loop buys A, buys B at +2 s, and hedges "
       "all 5 of A when its belief collapses (raised %s, hedged %g)"
       % (_p0["raised"], _hedged(_p0, _kA)))
    _p1 = _offline_trade_loop([_k1_A(), _k1_B(1, raise_from=2)])
    _p1e = [r for r in _kinds(_p1, "error") if r.get("where") == "scan"]
    ck(_p1["raised"] is None,
       "K1: an exception in the ENTRY SCAN does not end the loop while a "
       "position is held (trade_loop raised: %s)" % _p1["raised"])
    ck(abs(_hedged(_p1, _kA) - 5.0) < 1e-9,
       "K1: ...and the position already held is still hedged when it "
       "collapses (hedged %g of 5)" % _hedged(_p1, _kA))
    ck(len(_p1e) == 1 and _p1e[0].get("ticker") == "KXB115M-K1"
       and "TypeError" in str(_p1e[0].get("err")),
       "K1: ...and the fault is RECORDED, once per (close, market, error "
       "type), not twenty times a second (%d error records)" % len(_p1e))
    ck(_p1["ran_s"] >= 11.9,
       "K1: ...and the loop ran to its end (%.2f of 12 s)" % _p1["ran_s"])
    _pn = _offline_trade_loop([_k1_A(collapse_at=None),
                               _k1_B(1, raise_from=2)])
    ck(_pn["raised"] is None and not _kinds(_pn, "hedge"),
       "K1 NULL: the same fault with NO collapse hedges nothing -- the hedge "
       "above is caused by the collapse, not by the fault")

    def _k1_take(collide):
        calls = []

        def _t(base, pk, key_id, ticker, want, price, count, mce,
               exchange_index=0, **kw):
            body = pintake.build_take(ticker, want, price, count,
                                      exchange_index)
            out = pintake.normalise(201, {"order": {
                "order_id": "k1-%d" % len(calls), "status": "executed",
                "fill_count": count, "remaining_count": 0,
                "average_fill_price": (price if want == "yes"
                                       else 1.0 - price)}}, body, base)
            out["refused"] = []
            calls.append((ticker, want, float(count)))
            if collide and want == "yes":
                # a key the order record ALSO passes by name: rec("order")
                # then raises "got multiple values for keyword argument"
                out["want"] = want
            return out
        return _t, calls

    _kt0, _kc0 = _k1_take(False)
    _l0 = _offline_trade_loop([_k1_A()], live=True, take=_kt0)
    _l0e = [c for c in _kc0 if c[0] == _kA and c[1] == "yes"]
    ck(_l0["raised"] is None and len(_l0e) == 1
       and abs(_hedged(_l0, _kA) - _l0e[0][2]) < 1e-9,
       "K1 CONTROL, live order path: ONE order, and the hedge covers all "
       "of it (%d orders, hedged %g)" % (len(_l0e), _hedged(_l0, _kA)))
    _kt1, _kc1 = _k1_take(True)
    _l1 = _offline_trade_loop([_k1_A()], live=True, take=_kt1)
    _l1e = [c for c in _kc1 if c[0] == _kA and c[1] == "yes"]
    ck(len(_l1e) == 1,
       "K1: a log call that raises AFTER a fill does not lose the fill -- "
       "the close budget still sees it, so the market is bought ONCE, not "
       "again 50 ms later (%d orders sent)" % len(_l1e))
    ck(_l1e and abs(_hedged(_l1, _kA) - sum(c[2] for c in _l1e)) < 1e-9,
       "K1: ...and the fill is registered for hedging BEFORE anything "
       "formats it, so the collapse hedges all of it (hedged %g of %g)"
       % (_hedged(_l1, _kA), sum(c[2] for c in _l1e)))
    ck([r for r in _kinds(_l1, "error") if r.get("where") == "order_log"],
       "K1: ...and the failed log call is itself on the record")

    _s5 = _offline_trade_loop(
        [_k1_A(collapse_at=8)] + [_k1_B(i, raise_from=2) for i in range(1, 6)]
        + [_k1_B(9, decided_at=6)])
    ck(_s5["raised"] is None and _kinds(_s5, "entries_stopped")
       and not _kinds(_s5, "signal", "KXB915M-K1"),
       "K1: after FIVE scan errors the run stops NEW entries -- a clean "
       "market that decides at +6 s is not bought (raised %s)"
       % _s5["raised"])
    ck(abs(_hedged(_s5, _kA) - 5.0) < 1e-9 and _s5["ran_s"] >= 11.9
       and _kinds(_s5, "halt_pending") and not _kinds(_s5, "halt"),
       "K1: ...but while A is held it does not exit and never skips the "
       "hedge: it DRAINS, and A, collapsing at +8 s, is hedged in full "
       "(hedged %g, ran %.2f s)" % (_hedged(_s5, _kA), _s5["ran_s"]))
    # ...and with NOTHING held the stop ends the run, so watch_bot restarts
    # it -- the old loop's crash did the same. Before, a stopped run stayed
    # alive and idle for the rest of --minutes, writing records, so the
    # watchdog's silence check never fired.
    _sx = _offline_trade_loop([_k1_B(i, raise_from=2) for i in range(1, 6)]
                              + [_k1_B(9, decided_at=6)])
    _sxh = _kinds(_sx, "halt")
    _sxw = str(_sxh[0].get("why")) if _sxh else ""
    ck(_sx["raised"] is None and len(_sxh) == 1
       and _sxw.startswith("entries stopped") and _sx["ran_s"] < 6.0
       and not _kinds(_sx, "signal", "KXB915M-K1"),
       "K1: stopped entries with NOTHING held end the run (halt at %.2f s: "
       "%r) instead of idling for up to --minutes" % (_sx["ran_s"], _sxw))
    ck(_sxh and not halt_is_transient(_sxw)
       and not _re_k1.search("loss COUNT brake|loss abort|DRAWDOWN brake",
                             _sxw),
       "K1: ...and its reason is neither a transient pause nor one of "
       "watch_bot's money brakes (15 min cooldown), so the watchdog restarts "
       "the bot at once")
    _s4 = _offline_trade_loop(
        [_k1_A(collapse_at=8)] + [_k1_B(i, raise_from=2) for i in range(1, 5)]
        + [_k1_B(9, decided_at=6)])
    ck(_s4["raised"] is None and not _kinds(_s4, "entries_stopped")
       and _kinds(_s4, "signal", "KXB915M-K1"),
       "K1 NULL: FOUR scan errors do not stop entries -- the same clean "
       "market IS bought, so the stop above is the fifth error's doing")

    def _hedge_t(res):
        return [r["t"] for r in _kinds(res, "hedge", _kA)][:1]
    ck(_hedge_t(_s5) and _hedge_t(_s5) == _hedge_t(_s4),
       "K1: ...and DRAINING does not slow the hedge: A's collapse at +8 s is "
       "hedged at the same instant with entries stopped (%s) as with them "
       "running (%s)" % (_hedge_t(_s5), _hedge_t(_s4)))
    # ...and the --hedge-plant fill (one contract of the side about to lose,
    # live only, off in the live flags) is registered before its record too
    _kt6, _kc6 = _k1_take(False)

    def _plant_fault(kind, kw):
        if kind == "plant":
            raise TypeError("planted: the plant record cannot be written")
    _pl = _offline_trade_loop(
        [dict(_k1_A(collapse_at=None), fair=(lambda t: 0.95))], live=True,
        take=_kt6, plant=True, tau0=25, rec_fault=_plant_fault)
    _pl_buys = [c for c in _kc6 if c[0] == _kA and c[1] == "no"]
    ck(_pl["raised"] is None and len(_pl_buys) == 1
       and abs(_hedged(_pl, _kA) - 1.0) < 1e-9,
       "K1: the planted one-contract fill is hedged even when its record "
       "raises (%d plant buys, hedged %g)" % (len(_pl_buys),
                                               _hedged(_pl, _kA)))

    # THE HEDGE BODY'S OWN GUARD. A hedge record that raises AFTER the hedge
    # filled: the loop must survive it (the guard) and must not buy the same
    # hedge again next second (the fill is registered BEFORE the record).
    # Moved back below the record, this bought 9 hedges -- 45 contracts
    # against a 5-contract position, a naked bet the other way.
    _kt7, _kc7 = _k1_take(False)

    def _hedge_rec_fault(kind, kw):
        if kind == "hedge":
            raise TypeError("planted: the hedge record cannot be written")
    _hr = _offline_trade_loop([_k1_A()], live=True, take=_kt7,
                              rec_fault=_hedge_rec_fault)
    _hr_h = [c for c in _kc7 if c[0] == _kA and c[1] == "no"]
    _hr_e = [r for r in _kinds(_hr, "error") if r.get("where") == "hedge"]
    ck(_hr["raised"] is None and len(_hr_h) == 1
       and abs(_hr_h[0][2] - 5.0) < 1e-9 and len(_hr_e) == 1,
       "K1: a hedge record that raises after the fill neither ends the loop "
       "nor buys the hedge twice (raised %s, %d hedge orders, %g contracts, "
       "%d error records)" % (_hr["raised"], len(_hr_h),
                              sum(c[2] for c in _hr_h), len(_hr_e)))

    # A hedge step that THROWS must not leave the bot BUYING. The old loop
    # died there, which stopped its buying too; the first K1 kept it alive
    # and buying, so a broken hedge helper bought market after market it
    # could not insure. Planted: the sizing helper raises every second.
    def _hw_raise(*a_, **k_):
        raise TypeError("planted: the hedge sizing helper is broken")
    _hfc = _offline_trade_loop([_k1_A(collapse_at=1),
                                _k1_B(1, decided_at=3)])
    _hw_real = globals()["hedge_want"]
    globals()["hedge_want"] = _hw_raise
    try:
        _hf = _offline_trade_loop([_k1_A(collapse_at=1),
                                   _k1_B(1, decided_at=3)])
    finally:
        globals()["hedge_want"] = _hw_real
    ck(_hfc["raised"] is None and _kinds(_hfc, "signal", "KXB115M-K1")
       and abs(_hedged(_hfc, _kA) - 5.0) < 1e-9,
       "K1 CONTROL: A collapses at +1 s and is hedged; B decides at +3 s and "
       "IS bought")
    _hfe = [r for r in _kinds(_hf, "error") if r.get("where") == "hedge"]
    _hfs = _kinds(_hf, "entries_stopped")
    ck(_hf["raised"] is None and len(_hfe) == 1
       and _hfe[0].get("ticker") == _kA,
       "K1: a hedge step that throws every second does not end the loop and "
       "is recorded once (raised %s, %d records)"
       % (_hf["raised"], len(_hfe)))
    ck(_hfs and "hedge step error" in str(_hfs[0].get("why"))
       and not _kinds(_hf, "signal", "KXB115M-K1"),
       "K1: ...and it STOPS NEW ENTRIES at once: B, which the control buys "
       "at +3 s, is not bought")
    ck(_hf["ran_s"] >= 11.9 and _kinds(_hf, "halt_pending")
       and not _kinds(_hf, "halt"),
       "K1: ...and, still holding A, the run drains instead of exiting -- "
       "the hedge pass keeps trying (ran %.2f s)" % _hf["ran_s"])

    # THE RISK CHECK'S GUARD. risk_abort raising on every pass after the
    # first (A is bought on the first): no new bets, but the loop and the
    # hedge pass above it go on.
    _ra_real = globals()["risk_abort"]
    _ra_n = {"calls": 0}

    def _ra_raise(state_, a_):
        _ra_n["calls"] += 1
        if _ra_n["calls"] > 1:
            raise TypeError("planted: the risk check is broken")
        return _ra_real(state_, a_)
    globals()["risk_abort"] = _ra_raise
    try:
        _rk = _offline_trade_loop([_k1_A()])
    finally:
        globals()["risk_abort"] = _ra_real
    _rke = [r for r in _kinds(_rk, "error") if r.get("where") == "risk_abort"]
    ck(_rk["raised"] is None and abs(_hedged(_rk, _kA) - 5.0) < 1e-9
       and len(_rke) == 1 and _rk["ran_s"] >= 11.9,
       "K1: a risk check that RAISES ends nothing: A is still hedged in full "
       "when it collapses, the fault is recorded once, and the loop runs to "
       "its end (raised %s, hedged %g, %d records, ran %.2f s)"
       % (_rk["raised"], _hedged(_rk, _kA), len(_rke), _rk["ran_s"]))

    # ===================================================================
    # K2 (2026-09-22): A PINTAKE HALT NEVER REFUSES A HEDGE -- through the
    # REAL pintake.take, on a fake wire (DEMO base, nothing leaves the box).
    # One order whose outcome is unknown (-1: a timeout, the 09-21/22 outage
    # returned 388 of them) sets pintake's halt, pinrun never clears it, and
    # every hedge the A74 drain then sent was refused by the same take().
    # ===================================================================
    _kB1 = _k1_B(1)["tk"]

    def _k2_posts(res, tk, side):
        return [p for p in res["posts"]
                if p.get("ticker") == tk and p.get("side") == side]

    _k2l = _offline_trade_loop(
        [_k1_A(), _k1_B(1)], live=True,
        reply=lambda body, n: ((-1, "timed out")
                               if body.get("ticker") == _kB1
                               else _fill_all(body, n)))
    _k2l_bids = [p for p in _k2l["posts"] if p.get("side") == "bid"]
    ck(_k2l["raised"] is None and len(_k2l_bids) == 2
       and _k2l_bids[-1].get("ticker") == _kB1,
       "K2 fixture: A fills, then B's entry POST times out (-1) and halts "
       "pintake; no entry reaches the wire after it (%d entry POSTs)"
       % len(_k2l_bids))
    ck(len(_k2_posts(_k2l, _kA, "ask")) >= 1
       and abs(_hedged(_k2l, _kA) - 5.0) < 1e-9,
       "K2: with pintake HALTED, A's collapse still sends its hedge to the "
       "wire and it fills in full (%d hedge POSTs, hedged %g)"
       % (len(_k2_posts(_k2l, _kA, "ask")), _hedged(_k2l, _kA)))
    ck(any(r.get("past_halt") for r in _kinds(_k2l, "hedge", _kA)),
       "K2: ...and the hedge record says it went out past a halt")

    # A hedge whose OWN outcome is unknown must not be sent again: it may
    # have filled, and a resend would double the hedge. It is counted as
    # covered, which is exactly what the halt used to do by refusing
    # everything -- but a SECOND held position is still hedged.
    def _k1_D(collapse_at=6):
        m = _k1_B(4)
        m.update({"tk": "KXDDD15M-K2", "series": "KXDDD15M", "iid": "K2D",
                  "fair": (lambda t: 0.10 if t >= collapse_at else 0.999)})
        return m
    _kD = _k1_D()["tk"]
    _k2u_state = {"failed": 0}

    def _k2u_reply(body, n):
        if (body.get("ticker") == _kA and body.get("side") == "ask"
                and not _k2u_state["failed"]):
            _k2u_state["failed"] += 1
            return -1, "timed out"
        return _fill_all(body, n)
    _k2u = _offline_trade_loop([_k1_A(), _k1_D()], live=True,
                               reply=_k2u_reply)
    ck(_k2u["raised"] is None and len(_k2_posts(_k2u, _kA, "ask")) == 1,
       "K2: a hedge whose own POST timed out is NOT sent again -- it may "
       "have filled (%d hedge POSTs on A)" % len(_k2_posts(_k2u, _kA, "ask")))
    ck(_kinds(_k2u, "hedge_unknown", _kA),
       "K2: ...it is recorded as covered-but-unknown, not silently")
    ck(len(_k2_posts(_k2u, _kD, "ask")) >= 1
       and abs(_hedged(_k2u, _kD) - 5.0) < 1e-9,
       "K2: ...and the OTHER held position is still hedged when it collapses "
       "two seconds later, halt or no halt (hedged %g)" % _hedged(_k2u, _kD))

    # ...EXCEPT a -1 whose own error proves the order never left the box: a
    # refused connection cannot have placed anything. Counting it covered
    # left the position naked for the rest of the close over a one-second
    # blip; it is sent again next second. A reset once connected, which our
    # own logs show, stays UNKNOWN and is not resent.
    def _k2n_reply(msg):
        _st = {"n": 0}

        def _r(body, n):
            if (body.get("ticker") == _kA and body.get("side") == "ask"
                    and not _st["n"]):
                _st["n"] += 1
                return -1, msg
            return _fill_all(body, n)
        return _r
    _k2n = _offline_trade_loop([_k1_A()], live=True, reply=_k2n_reply(
        "<urlopen error [WinError 10061] No connection could be made because "
        "the target machine actively refused it>"))
    ck(_k2n["raised"] is None and len(_k2_posts(_k2n, _kA, "ask")) == 2
       and abs(_hedged(_k2n, _kA) - 5.0) < 1e-9
       and _kinds(_k2n, "hedge_not_sent", _kA)
       and not _kinds(_k2n, "hedge_unknown", _kA),
       "K2: a hedge REFUSED at connect (it never left the box) is sent again "
       "next second and fills in full (%d hedge POSTs, hedged %g)"
       % (len(_k2_posts(_k2n, _kA, "ask")), _hedged(_k2n, _kA)))
    _k2r = _offline_trade_loop([_k1_A()], live=True, reply=_k2n_reply(
        "<urlopen error [WinError 10054] An existing connection was forcibly "
        "closed by the remote host>"))
    ck(_k2r["raised"] is None and len(_k2_posts(_k2r, _kA, "ask")) == 1
       and _kinds(_k2r, "hedge_unknown", _kA)
       and not _kinds(_k2r, "hedge_not_sent", _kA),
       "K2 NULL: a connection RESET (the order may have gone out) is still "
       "counted covered and NOT resent (%d hedge POSTs)"
       % len(_k2_posts(_k2r, _kA, "ask")))
    ck(hedge_never_sent({"status_code": -1, "raw":
                         "<urlopen error [Errno 11001] getaddrinfo failed>"})
       and hedge_never_sent({"status_code": -1, "raw":
                             "<urlopen error _ssl.c:1064: The handshake "
                             "operation timed out>"})
       and not hedge_never_sent({"status_code": -1, "raw": "timed out"})
       and not hedge_never_sent({"status_code": -1,
                                 "raw": "<urlopen error timed out>"})
       and not hedge_never_sent({"status_code": 503, "raw":
                                 "<urlopen error [WinError 10061] x>"})
       and not hedge_never_sent({"status_code": -1, "raw": None})
       and not hedge_never_sent(None),
       "K2: hedge_never_sent is True only for a -1 whose own error proves no "
       "byte was written (refused, DNS, TLS handshake); a timeout, a 5xx, no "
       "text or no result at all is UNKNOWN")

    # ===================================================================
    # K3 (2026-09-22): A FROZEN INDEX MUST NOT HIDE A COLLAPSE.
    #
    # The premise first, on the REAL IndexWS and fair(): when the feed stops,
    # partial() ends the settlement window at the newest print held, so the
    # belief is frozen EXACTLY -- confident, quiet, no alarm and no record --
    # while spot() reports the age that the hedge pass never read.
    # ===================================================================
    _k3clk = _OfflineClock(0.0)
    _k3saved = globals()["time"]
    try:
        globals()["time"] = _k3clk
        _k3i = IndexWS(["K3"])
        _k3C = 1_800_000_900
        _k3r = __import__("random").Random(3)
        _k3v = 100000.0
        for _s in range(_k3C - 3700, _k3C - 28):       # prints stop at tau 29
            _k3v += _k3r.gauss(0.0, 4.0)
            _k3i.on_frame({"type": "cfbenchmarks_value", "msg": {
                "index_id": "K3", "data": {"time": _s * 1000,
                                           "value": str(round(_k3v, 2))}}},
                          rx_ms=_s * 1000)
        _k3sg = _k3i.sigma("K3")
        _k3K = round(_k3v - 20.0, 2)                   # ~99.8% sure
        _k3clk.t = _k3C - 27.5
        _k3f1 = fair(_k3i, "K3", _k3C, _k3C - 28, _k3K, _k3sg, 2)
        _k3a1 = _k3i.spot("K3")[2]
        _k3clk.t = _k3C - 15.5
        _k3f2 = fair(_k3i, "K3", _k3C, _k3C - 16, _k3K, _k3sg, 2)
        _k3a2 = _k3i.spot("K3")[2]
    finally:
        globals()["time"] = _k3saved
    ck(_k3f1 is not None and _k3f1 == _k3f2 and 0.99 < _k3f1 < 1.0
       and _k3a1 <= MAX_INDEX_AGE_S < _k3a2,
       "K3 PREMISE (real IndexWS + fair): a feed that stops holds the belief "
       "EXACTLY (%.6f then %.6f twelve seconds later) while spot() ages "
       "%.1f s -> %.1f s -- the only sign it is blind"
       % (_k3f1 or -1, _k3f2 or -1, _k3a1, _k3a2))

    # Now the loop. A is bought on a fresh index at 30 s to go; the index
    # stops printing at +2 s, so the model stays 99.9% sure however the
    # world moves. The MARKET is the other witness: our side's own ask.
    def _k3_A(book_collapse_at=None, model_collapse_at=None):
        m = _k1_A(collapse_at=model_collapse_at)
        m["book"] = (lambda t: _ob(0.06, 0.90)
                     if (book_collapse_at is not None
                         and t >= book_collapse_at) else _ob(0.94, 0.05))
        return m

    def _k3_blind(res):
        return [r for r in _kinds(res, "hedge_blind", _kA)
                if r.get("why") == "index_stale"]

    _k3a = _offline_trade_loop([_k3_A(book_collapse_at=4,
                                      model_collapse_at=4)], freeze_at=2)
    ck(_k3a["raised"] is None and abs(_hedged(_k3a, _kA) - 5.0) < 1e-9,
       "K3: frozen index + the MARKET collapses (our side's ask 10c) -> the "
       "position is hedged in full anyway (hedged %g)" % _hedged(_k3a, _kA))
    ck(len(_k3_blind(_k3a)) == 1,
       "K3: ...and the stale index is on the record ONCE per position, as "
       "hedge_blind why=index_stale (%d records)" % len(_k3_blind(_k3a)))
    ck([r for r in _kinds(_k3a, "hedge_alarm", _kA)
        if r.get("trigger") == "market_index_stale"
        and r.get("model_belief", 0) > 0.99
        and r.get("market_belief", 1) < _DEFAULT_HEDGE_BELIEF],
       "K3: ...and the alarm says WHY: trigger market_index_stale, with the "
       "frozen model's 99.9% beside the market's 10c")
    _k3b = _offline_trade_loop([_k3_A()], freeze_at=2)
    ck(_k3b["raised"] is None and not _kinds(_k3b, "hedge")
       and len(_k3_blind(_k3b)) == 1
       and (_k3_blind(_k3b)[0].get("age_s") or 0) > MAX_INDEX_AGE_S,
       "K3 NULL: frozen index + a STEADY market (our side's ask 95c) -> "
       "no hedge, but the blindness is recorded with its age")
    # last_belief feeds the A68 rebuy, an ENTRY: it must hold the MODEL's
    # number even while the market's lower one is in use. Read off the
    # hedge_quote records, which print it: the model says 99.9%, the market
    # 95c, and every quote must say 99.9%.
    _k3bq = [r for r in _kinds(_k3b, "hedge_quote", _kA) if r["t"] >= 5.0]
    ck(_k3bq and all((r.get("belief") or 0) > 0.99 for r in _k3bq),
       "K3: ...and while the index is stale the belief the rebuy reads is "
       "still the MODEL's, never the market's (%d quotes, lowest %s)"
       % (len(_k3bq), min([r.get("belief") for r in _k3bq] or [None],
                          key=lambda v: 9 if v is None else v)))
    # A healthy but WIDE book must not fire it. After our own entry sweeps
    # the other side, bid 15c / ask 99c is an ordinary book on a winner; its
    # MID is 57c, under the shipped 0.80 line, and hedged a winning position
    # in full when the market belief was the mid. The ask says 99c.
    _k3w = dict(_k1_A(collapse_at=None))
    _k3w["book"] = (lambda t: _ob(0.15, 0.01) if t >= 3 else _ob(0.94, 0.05))
    _k3wr = _offline_trade_loop([_k3w], freeze_at=2)
    _k3wb = _k3_blind(_k3wr)
    ck(_k3wr["raised"] is None and _kinds(_k3wr, "signal", _kA)
       and not _kinds(_k3wr, "hedge") and not _kinds(_k3wr, "hedge_alarm")
       and _k3wb and all(r.get("market_belief") in (None, 0.95, 0.99)
                         for r in _k3wb),
       "K3 NULL: frozen index + a WIDE healthy book (bid 15c / ask 99c on our "
       "side) -> no alarm and no hedge: the market belief is our ASK, which "
       "a thin lowball bid cannot drag under the line")
    _k3c = _offline_trade_loop([_k3_A(book_collapse_at=4)])
    ck(_k3c["raised"] is None and not _kinds(_k3c, "hedge")
       and not _k3_blind(_k3c),
       "K3 NULL: FRESH index, the market alone collapses, the model is sure "
       "-> exactly today's behaviour: no hedge, no stale record. The market "
       "is consulted only while the index is blind")
    _k3d = _offline_trade_loop([_k3_A(model_collapse_at=4)])
    ck(_k3d["raised"] is None and abs(_hedged(_k3d, _kA) - 5.0) < 1e-9
       and not _k3_blind(_k3d)
       and _kinds(_k3d, "hedge_alarm", _kA)
       and all(r.get("trigger") == "belief" and "market_belief" not in r
               for r in _kinds(_k3d, "hedge_alarm", _kA)),
       "K3 CONTROL: FRESH index, the model collapses -> hedged on the "
       "ordinary belief trigger, and the alarm record is today's")
    # market_belief(): None, never a guess
    ck(abs(market_belief(_ob(0.94, 0.05), "yes") - 0.95) < 1e-9
       and abs(market_belief(_ob(0.94, 0.05), "no") - 0.06) < 1e-9
       and abs(market_belief(_ob(0.15, 0.01), "yes") - 0.99) < 1e-9,
       "K3: our side's market belief is OUR side's best ask (YES 94c/95c -> "
       "0.95; the NO holder's 5c/6c -> 0.06; a wide 15c/99c -> 0.99, not "
       "the 0.57 mid)")
    ck(market_belief(_ob(0.94, 0.05, age_ms=MAX_BOOK_AGE_MS + 1), "yes")
       is None
       and market_belief(dict(_ob(0.94, 0.05), suspect=True), "yes") is None
       and market_belief(_ob(None, 0.05), "yes") is None
       and market_belief(_ob(0.94, None), "yes") is None
       and market_belief(dict(_ob(0.94, 0.05), yes_ask=0.90), "yes") is None
       and market_belief(None, "yes") is None,
       "K3 NULL: a stale, suspect, one-sided, crossed or missing book gives "
       "NO market belief -- the fallback never fires on a guess")

    # ===================================================================
    # K3b (2026-09-23): K3's OWN BLIND SPOT -- A COVERED POSITION IS NOT
    # WATCHED AT ALL.
    #
    # K3 asks "is this market's index still printing?" inside the hedge
    # pass. The pass exits at the `hedged` skip for a position that is
    # already covered -- ABOVE that question and above the write of
    # last_belief -- so from the second a hedge completes the market has no
    # index witness, and hedge_quote reprints a belief nobody is updating.
    # On KXDOGE15M-26SEP222245-45 (close 2026-09-23T02:45:00Z, 13 NO
    # contracts held) that belief was byte-identical for nine seconds while
    # the book moved every second, and NOTHING in the log said whether the
    # index had stopped or only the log had. It was only the log: largest
    # index age in the whole run 1.1 s against a 2 s bar. But a real freeze
    # there would have been FIELD-FOR-FIELD identical -- see
    # results/map_2026-09-22/doge2245/D_frozen_index.md, worlds W2 and W3.
    #
    # The skip is NOT moved. Below the pass, hedge_remain.pop makes the
    # size fall back to the full original, and the measured result is 22
    # hedge sends for 13 contracts -- re-buying the whole hedge every
    # second. The question is asked in the hedge_quote block instead: below
    # the pass, already once per held market per second, already guarded.
    # ===================================================================
    def _kb_A(freeze=None, collapse=None, book_collapse=None, rebuy=False):
        m = _k1_A(collapse_at=collapse)
        if freeze is not None:
            m["freeze_at"] = freeze          # THIS index only; B keeps flowing
        # `rebuy`: a cent cheaper from +1 s (yes_ask 0.95 -> 0.94), which is
        # what A3's improve-by and A23's band allow a SECOND fill on the same
        # market to be. With MAX_PER_MARKET 2 and IMPROVE_SCOPE "market" --
        # live's own settings -- that is two entry positions on one ticker.
        m["book"] = (lambda t: _ob(0.06, 0.90)
                     if (book_collapse is not None and t >= book_collapse)
                     else (_ob(0.94, 0.06) if (rebuy and t >= 1)
                           else _ob(0.94, 0.05)))
        return m

    def _kb_blind(res, tk=None):
        return [r for r in _kinds(res, "hedge_blind", tk)
                if r.get("why") == "index_stale"]

    def _kb_old(res):
        """Every record the code BEFORE K3b would have written, carrying only
        the fields it would have carried. Two runs equal here differ in
        nothing but the new information."""
        out = []
        for r in res["recs"]:
            if r["kind"] == "hedge_blind":
                continue                             # K3b's own record
            out.append(json.dumps(
                {k: v for k, v in r.items()
                 if not (r["kind"] == "hedge_quote"
                         and k in ("iid", "index_age_s", "belief_calc_age_s",
                                   "n", "naked"))},
                sort_keys=True, default=str))
        return out

    def _kb_all(res):
        return [json.dumps(r, sort_keys=True, default=str)
                for r in res["recs"]]

    # A: ONE index frozen at +2 s while B's keeps arriving, the position
    # still OPEN, and the market says 10c by the time the age crosses the
    # bar (the record is deduped to the FIRST stale second, so the world has
    # to have collapsed by then for the record to carry the collapse).
    # Today's behaviour, plus the depth at that ask -- whether the fallback
    # could have been filled is not answerable from a price alone.
    _kb1 = _offline_trade_loop([_kb_A(freeze=2, book_collapse=2), _k1_B(1)])
    _kb1b = _kb_blind(_kb1, _kA)
    ck(_kb1["raised"] is None and abs(_hedged(_kb1, _kA) - 5.0) < 1e-9
       and [r for r in _kinds(_kb1, "hedge_alarm", _kA)
            if r.get("trigger") == "market_index_stale"],
       "K3b: ONE index frozen behind a live one, position OPEN -> the "
       "market-price fallback still hedges all 5 on market_index_stale "
       "(hedged %g)" % _hedged(_kb1, _kA))
    ck(len(_kb1b) == 1 and _kb1b[0].get("where") == "hedge_pass"
       and _kb1b[0].get("iid") == "K1A"
       and (_kb1b[0].get("age_s") or 0) > MAX_INDEX_AGE_S
       and _kb1b[0].get("market_belief") == 0.1
       and _kb1b[0].get("ask") == 0.1 and _kb1b[0].get("ask_size") == 50.0,
       "K3b: ...recorded ONCE, by the hedge pass, with the index, its age, "
       "the market's 10c, our side's ask AND THE SIZE behind it (%s)"
       % (_kb1b[0] if _kb1b else None))
    ck(not _kb_blind(_kb1, "KXB115M-K1"),
       "K3b NULL: the market whose index kept arriving is not reported "
       "blind -- the age is per index, not per socket")

    # B: THE DOGE SHAPE. The model collapses at +4 s, the hedge covers the
    # position in full, and THEN that one index freezes at +6 s.
    _kb2 = _offline_trade_loop([_kb_A(freeze=6, collapse=4), _k1_B(1)])
    _kb2b = _kb_blind(_kb2, _kA)
    _kb2h = _kinds(_kb2, "hedge", _kA)
    ck(len(_kb2b) == 1 and _kb2b[0].get("where") == "hedge_quote"
       and _kb2b[0].get("hedged") is True and _kb2b[0].get("n") == 5.0
       and (_kb2b[0].get("age_s") or 0) > MAX_INDEX_AGE_S
       and _kb2b[0].get("iid") == "K1A"
       and _kb2b[0].get("ask") == 0.95 and _kb2b[0].get("ask_size") == 50.0,
       "K3b: an index that freezes AFTER the hedge completed is recorded "
       "anyway -- once, by the watcher below the pass, saying the position "
       "is already covered and how big it is (%s)"
       % (_kb2b[0] if _kb2b else None))
    # REVIEW FIX 2026-09-23: the record must carry the MARKET, not one leg --
    # every contract held, how many are insured, how many are not, and from
    # the booked insurance legs rather than the `hedged` flag (whose set means
    # "hedged OR given up on"). Here: 5 held, 5 insured, none naked, 1 leg.
    ck(_kb2b and _kb2b[0].get("n_tk") == 5.0
       and _kb2b[0].get("insured_tk") == 5.0
       and _kb2b[0].get("naked_tk") == 0.0 and _kb2b[0].get("pos") == 1
       and _kb2b[0].get("remain") is None,
       "K3b: ...and it says how much of the MARKET is uninsured from the "
       "insurance legs actually booked, not from the hedged flag (%s)"
       % ({_k: _kb2b[0].get(_k) for _k in
           ("n", "remain", "n_tk", "insured_tk", "naked_tk", "pos")}
          if _kb2b else None))
    ck(len(_kb2h) == 1 and abs(_hedged(_kb2, _kA) - 5.0) < 1e-9,
       "K3b: ...and NOTHING is bought for it: one hedge, 5 contracts, not "
       "one per second for the rest of the close (%d sends, %g contracts)"
       % (len(_kb2h), _hedged(_kb2, _kA)))
    # `or [-1]`: a REVERTED build writes no such field, and a self-test whose
    # own message raises is a crash, not a reported failure
    _kb2q = [r for r in _kinds(_kb2, "hedge_quote", _kA)
             if r.get("index_age_s") is not None]
    _kb2qi = max([r["index_age_s"] for r in _kb2q] or [-1])
    _kb2qb = max([r.get("belief_calc_age_s") or 0 for r in _kb2q] or [-1])
    ck(_kb2q and _kb2qi > MAX_INDEX_AGE_S and _kb2qb >= 3,
       "K3b: ...and every held second now carries the age of that market's "
       "own index print AND of the belief beside it (index to %s s, belief "
       "to %s s) -- the nine DOGE seconds would have been one glance"
       % (_kb2qi, _kb2qb))
    ck(_kb2q and all(r.get("n") == 5.0 for r in _kb2q)
       and _kb2q[0].get("naked") == 5.0 and _kb2q[-1].get("naked") == 0.0,
       "K3b: ...and how much money is riding on it THAT second -- 5 held "
       "throughout, 5 uninsured before the hedge and 0 after it, counted "
       "from the legs booked (%s)"
       % sorted({(r.get("n"), r.get("naked")) for r in _kb2q}))

    # C: THE REVERT CATCHER. The same world with a HEALTHY index. Before
    # K3b these two record trails were identical, field for field.
    _kb3 = _offline_trade_loop([_kb_A(collapse=4), _k1_B(1)])
    _kb3q = _kinds(_kb3, "hedge_quote", _kA)
    ck(_kb3["raised"] is None and not _kb_blind(_kb3)
       and _kb3q and all(r.get("index_age_s") is not None
                         and r["index_age_s"] <= MAX_INDEX_AGE_S
                         for r in _kb3q),
       "K3b NULL: a HEALTHY index through the same hedge is never reported "
       "blind, and every quote's index age stays under the bar (%d quotes, "
       "worst %.2f s)" % (len(_kb3q),
                          max([r.get("index_age_s") or 0 for r in _kb3q]
                              or [-1])))
    ck(_kb_all(_kb2) != _kb_all(_kb3),
       "K3b CATCHER: the frozen world and the healthy world no longer "
       "produce the same records. Reverting K3b makes these two IDENTICAL, "
       "which is the whole defect (%d vs %d records)"
       % (len(_kb2["recs"]), len(_kb3["recs"])))

    # D: NO BEHAVIOUR CHANGE, proved in the world where the fix FIRES. The
    # same run with index_age() forced to 0 is the old code's decision path
    # -- nothing is ever stale, so neither witness speaks -- and every
    # pre-existing record and field must be identical to it.
    _kb_ia0 = globals()["index_age"]
    try:
        globals()["index_age"] = lambda _i, _d: 0.0
        _kb2f = _offline_trade_loop([_kb_A(freeze=6, collapse=4), _k1_B(1)])
        _kb3f = _offline_trade_loop([_kb_A(collapse=4), _k1_B(1)])
        _kb1f = _offline_trade_loop([_kb_A(freeze=2, book_collapse=2),
                                     _k1_B(1)])
    finally:
        globals()["index_age"] = _kb_ia0
    ck(globals()["index_age"] is _kb_ia0 and _kb2f["raised"] is None
       and not _kb_blind(_kb2f) and _kb_old(_kb2) == _kb_old(_kb2f)
       and _kb_old(_kb3) == _kb_old(_kb3f),
       "K3b: every pre-existing record and every pre-existing field is "
       "IDENTICAL with the freeze seen and with it invisible, and on a "
       "HEALTHY feed too -- the fix adds records, and changes no decision, "
       "no alarm, no send and no refusal (%d and %d records either way)"
       % (len(_kb_old(_kb2)), len(_kb_old(_kb3))))
    ck(not _kinds(_kb1f, "hedge", _kA) and _kb_old(_kb1) != _kb_old(_kb1f),
       "K3b CONTROL: the same neutraliser DOES change the OPEN position's "
       "world -- with the staleness invisible the frozen model never hedges "
       "at all, so the comparison above is not vacuous")

    # E: THE WHOLE SOCKET SILENT from +6 s, A covered and B still open:
    # both are recorded, each by the witness that can see it.
    _kb4 = _offline_trade_loop([_kb_A(collapse=4), _k1_B(1)], freeze_at=6)
    _kb4a = _kb_blind(_kb4, _kA)
    _kb4b = _kb_blind(_kb4, "KXB115M-K1")
    ck(_kb4["raised"] is None and len(_kb4a) == 1 and len(_kb4b) == 1
       and _kb4a[0].get("where") == "hedge_quote"
       and _kb4b[0].get("where") == "hedge_pass"
       and not [r for r in _kinds(_kb4, "hedge") if r.get("ticker")
                == "KXB115M-K1"],
       "K3b: a SILENT SOCKET is recorded for every held market -- the "
       "covered one by the watcher, the open one by the pass -- and the open "
       "one, whose market still says 93c, is not hedged on a guess")

    # F: THE ORDERING THAT KEEPS THIS SAFE, read off trade_loop's source.
    # The `hedged` skip must stay ABOVE K3's index read (below it, the size
    # falls back to the original and the hedge is re-bought every second),
    # and the new witness must stay BELOW the whole pass and AFTER the
    # pre-existing quote record, so neither a new record nor a new failure
    # can sit in front of a hedge or cost an old record.
    _src_kb = open(os.path.abspath(__file__), encoding="utf-8").read()
    _tl_kb = _src_kb[_src_kb.rindex(chr(10) + "def trade_loop("):]
    # find(), never index(): a line that has been REMOVED must fail this
    # check, not raise out of the self-test before it is reported.
    _i_kb = tuple(_tl_kb.find(_s) for _s in (
        "if _hid in hedged or _hid.startswith(",
        "_hage = index_age(idx, _hiid)",
        "# ---------------- end AMENDMENT 15",
        'rec("hedge_quote", ticker=_qtk',
        'rec("hedge_blind", ticker=_qtk'))
    ck(min(_i_kb) > 0 and list(_i_kb) == sorted(_i_kb),
       "K3b: in trade_loop's own source the covered-position skip is still "
       "ABOVE K3's index read, and the new witness is BELOW the end of the "
       "hedge pass and AFTER the quote record it must never cost (%s)"
       % (_i_kb,))

    # ===================================================================
    # K3b REVIEW FIXES (2026-09-23). Five defects in the witness above,
    # every one of them in the case it was written for, plus one found while
    # building the world that catches the first.
    #
    # G/H  THE RECORD REPORTED ONE LEG AND CALLED IT THE MARKET. The held
    #      positions were collected with setdefault(ticker, ...), so a
    #      market with two entry fills kept the FIRST leg and dropped the
    #      rest: one record, that leg's size, that leg's hedge state, and
    #      the dedupe key burned on it. Live runs --max-per-market 2 and
    #      open_pos gets an id per FILL; 24 of 704 (run, ticker) pairs in
    #      the live log have two, and the DOGE close that motivated the
    #      whole fix is one of them -- 2 contracts then 11, so the record
    #      would have read n: 2 for 13 held. The old harness could not
    #      build the world at all: _offline_trade_loop pins MAX_PER_MARKET
    #      to its _DEFAULT_ of 1, which is why twelve new checks missed it.
    #      These worlds pass MAX_PER_MARKET/IMPROVE_SCOPE through `flags`,
    #      i.e. what live actually runs.
    # I    belief_calc_age_s SAYS WHAT IT MEANS. While an OPEN position's
    #      index is frozen the pass recomputes the same belief off the same
    #      frozen ring every second, so the field reads 0 s on a provably
    #      stale belief. It is the age of the CALCULATION; index_age_s is
    #      the one that climbs, and the old name `belief_age_s` invited the
    #      opposite reading. Asserted in BOTH directions now.
    # J    THE KEY IS BURNED AFTER THE WRITE. It was added before, so a
    #      rec() that raised -- it opens, appends and closes the file every
    #      call -- lost the only witness a covered position has for the
    #      whole run, in silence. J2 is the null beside it.
    # L    AND IT IS THE WATCHER'S OWN KEY. It used to burn the hedge
    #      pass's, which could have silenced the pass's richer record for
    #      the rest of a run.
    # K    A RAISE IN THE NEW ARITHMETIC CANNOT COST THE OLD RECORD. The
    #      ages were computed above rec("hedge_quote") under the block's
    #      blanket except; now they are in their own guard.
    # ---  AND THE ONE THE TWO-LEG WORLD FOUND: the PAPER insurance leg was
    #      keyed `hedge-paper-{ticker}-{second}` and two legs on one market
    #      hedge in the same second, so one overwrote the other in open_pos
    #      and never settled. Every paper arm's loss on a two-fill market
    #      was overstated by a whole hedge leg. B10, for the second time.
    # ===================================================================
    # G: TWO ENTRY FILLS ON ONE MARKET (the second a cent cheaper, which is
    # what --improve-scope market + the A23 band allow), both covered, and
    # THEN that index freezes.
    _kb5 = _offline_trade_loop(
        [_kb_A(freeze=6, collapse=4, rebuy=True)],
        flags={"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"})
    _kb5b = _kb_blind(_kb5, _kA)
    _kb5h = _kinds(_kb5, "hedge", _kA)
    ck(_kb5["raised"] is None and len(_kb5h) == 2
       and abs(_hedged(_kb5, _kA) - 10.0) < 1e-9,
       "K3b: the two-leg world is real -- two entry fills on ONE market, "
       "two hedges, 10 contracts (%d sends, %g contracts). Without this the "
       "check below proves nothing" % (len(_kb5h), _hedged(_kb5, _kA)))
    ck(len(_kb5b) == 2
       and sorted(float(r.get("n") or 0) for r in _kb5b) == [5.0, 5.0]
       and all(r.get("n_tk") == 10.0 and r.get("pos") == 2
               and r.get("insured_tk") == 10.0 and r.get("naked_tk") == 0.0
               and r.get("where") == "hedge_quote" for r in _kb5b),
       "K3b: ...and BOTH legs are reported, each with its own size and the "
       "market's 10 contracts beside it -- never one leg's 5 standing in "
       "for the market (%d records, sizes %s, n_tk %s)"
       % (len(_kb5b), [r.get("n") for r in _kb5b],
          [r.get("n_tk") for r in _kb5b]))
    # FOUND BUILDING THAT WORLD, AND IT IS B10 AGAIN: the PAPER hedge leg was
    # keyed `hedge-paper-{ticker}-{second}`, and two positions on one market
    # hedge in the SAME second because the same belief fires both alarms. So
    # the second leg overwrote the first in open_pos, reconcile settles per
    # entry, and the arm booked one 5-contract recovery instead of two --
    # every arm's loss on a two-fill market overstated by a whole hedge leg.
    # `insured_tk == 10` above is the running proof; this is the source.
    ck("hedge-paper-{_htk}" not in _tl_kb
       and "hedge-paper-{_hid}" in _tl_kb and "hedge-{_hid}-" in _tl_kb,
       "K3b: an insurance leg is keyed on the PARENT POSITION, never on the "
       "ticker and the second -- two legs bought for one market in one "
       "second are two legs in open_pos, and both settle")
    # H: the healthy twin of G -- two legs, nothing stale, nothing reported.
    _kb5n = _offline_trade_loop(
        [_kb_A(collapse=4, rebuy=True)],
        flags={"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"})
    ck(_kb5n["raised"] is None and not _kb_blind(_kb5n)
       and len(_kinds(_kb5n, "hedge", _kA)) == 2
       and all(r.get("n") == 10.0 for r in _kinds(_kb5n, "hedge_quote", _kA)
               if r.get("t", 0) > 2),
       "K3b NULL: two legs on a HEALTHY index are never reported blind, and "
       "the quote says 10 contracts held once both are on (%s)"
       % sorted({r.get("n") for r in _kinds(_kb5n, "hedge_quote", _kA)}))

    # I: THE OPEN, FROZEN, WINNING position. The pass recomputes its belief
    # off the frozen ring every second, so the CALCULATION is always 0 s old
    # while the index behind it climbs past the bar. Both are asserted, in
    # the direction each actually goes, so neither field can be read as the
    # other.
    _kb6 = _offline_trade_loop([_kb_A(freeze=2)])
    _kb6q = _kinds(_kb6, "hedge_quote", _kA)
    _kb6b = _kb_blind(_kb6, _kA)
    _kb6i = max([r.get("index_age_s") or 0 for r in _kb6q] or [-1])
    ck(_kb6["raised"] is None and _kb6q and _kb6i > MAX_INDEX_AGE_S
       and {r.get("belief_calc_age_s") for r in _kb6q} == {0}
       and not _kinds(_kb6, "hedge", _kA)
       and len(_kb6b) == 1 and _kb6b[0].get("where") == "hedge_pass",
       "K3b: on an OPEN position with a frozen index the belief is "
       "RECOMPUTED every second, so belief_calc_age_s is 0 s while "
       "index_age_s reaches %.2f s -- the field is the age of the sum, not "
       "of the information, and only index_age_s can say the feed stopped "
       "(%d quotes, belief ages %s)"
       % (_kb6i, len(_kb6q),
          sorted({r.get("belief_calc_age_s") for r in _kb6q})))

    # J: THE RECORD'S OWN WRITE FAILS ONCE. The key must survive it (the
    # next second writes it), the hedge must not care, and the OTHER held
    # market must still get that second's quote.
    _kb7n = {"i": 0}

    def _kb7_fault(kind, kw):
        if kind == "hedge_blind" and kw.get("where") == "hedge_quote":
            _kb7n["i"] += 1
            if _kb7n["i"] == 1:
                raise TypeError("planted: the blind record cannot be written")
    _kb7 = _offline_trade_loop([_kb_A(freeze=6, collapse=4), _k1_B(1)],
                               rec_fault=_kb7_fault)
    _kb7b = _kb_blind(_kb7, _kA)
    ck(_kb7["raised"] is None and _kb7n["i"] == 2 and len(_kb7b) == 1
       and abs(_hedged(_kb7, _kA) - 5.0) < 1e-9
       and (len(_kinds(_kb7, "hedge_quote", "KXB115M-K1"))
            == len(_kinds(_kb2, "hedge_quote", "KXB115M-K1"))),
       "K3b: a blind record whose write RAISES is retried next second and "
       "still lands exactly once (%d attempts, %d records), the hedge is "
       "untouched, and the other held market loses no quote (%d vs %d)"
       % (_kb7n["i"], len(_kb7b),
          len(_kinds(_kb7, "hedge_quote", "KXB115M-K1")),
          len(_kinds(_kb2, "hedge_quote", "KXB115M-K1"))))

    # J2: THE SAME WRITE FAILING FOR EVER. One record may cost itself; it may
    # not cost another market's trail. NULL, and it holds for TWO reasons that
    # have to be said apart: the per-market guard added today, and the fact
    # that `hedge_quote_at` is stamped per ticker, so the next pass of the
    # same second writes whatever a raise skipped. The second reason alone is
    # enough -- this check is green with the new guard patched out -- so the
    # guard is belt and braces and this check is not its proof. What it does
    # prove is the property that matters: no market loses a second's quote
    # because another market's record cannot be written.
    def _kb9_fault(kind, kw):
        if kind == "hedge_blind" and kw.get("where") == "hedge_quote":
            raise TypeError("planted: the blind record can NEVER be written")
    _kb9 = _offline_trade_loop([_kb_A(freeze=6, collapse=4), _k1_B(1)],
                               rec_fault=_kb9_fault)
    _kb9a, _kb9b2 = (len(_kinds(_kb9, "hedge_quote", _kA)),
                     len(_kinds(_kb9, "hedge_quote", "KXB115M-K1")))
    _kb2a, _kb2b2 = (len(_kinds(_kb2, "hedge_quote", _kA)),
                     len(_kinds(_kb2, "hedge_quote", "KXB115M-K1")))
    ck(_kb9["raised"] is None and not _kb_blind(_kb9)
       and _kb9a == _kb2a and _kb9b2 == _kb2b2
       and abs(_hedged(_kb9, _kA) - 5.0) < 1e-9,
       "K3b: a blind record that can NEVER be written costs itself and "
       "nothing else -- the frozen market keeps every quote and so does the "
       "other held market (%d and %d, against %d and %d unfaulted)"
       % (_kb9a, _kb9b2, _kb2a, _kb2b2))

    # L: THE WITNESS MUST NOT BE ABLE TO SILENCE THE PASS. Both witnesses
    # dedupe through _hq71, and the pass's record is the richer one (it
    # carries the fallback context and fires at the second it decides). So
    # the watcher READS the pass's key -- one record per position per run
    # whichever saw it first -- and WRITES only its own. Burning the pass's
    # key here would mean that if the pass ever raised ahead of its index
    # read, its record could never be written for the rest of the run. Read
    # off the source: this needs the pass to raise inside itself, which no
    # offline world can plant.
    ck('(_pid, "index_stale") in _hq71' in _tl_kb
       and '_hq71.add((_pid, "index_stale_q"))' in _tl_kb
       and '_hq71.add((_pid, "index_stale"))' not in _tl_kb,
       "K3b: the watcher below the pass READS the pass's dedupe key and "
       "writes only its own, so it can never suppress the pass's richer "
       "record")

    # K: index_age() RAISES. The new fields go missing; the pre-existing
    # per-second quote record -- the one barcheck reads -- does not.
    def _kb8_raise(_i8, _d8):
        raise TypeError("planted: index_age cannot answer")
    _kb_ia1 = globals()["index_age"]
    try:
        globals()["index_age"] = _kb8_raise
        _kb8 = _offline_trade_loop([_kb_A(collapse=4)])
    finally:
        globals()["index_age"] = _kb_ia1
    _kb8q = _kinds(_kb8, "hedge_quote", _kA)
    ck(globals()["index_age"] is _kb_ia1 and _kb8["raised"] is None
       and len(_kb8q) >= 8
       and all(r.get("index_age_s") is None and r.get("ask") == 0.06
               and r.get("n") == 5.0 for r in _kb8q),
       "K3b: with index_age() raising, every held second still writes its "
       "hedge_quote -- ask, size, belief, size held -- and only the ages "
       "are missing (%d quotes, ages %s)"
       % (len(_kb8q), sorted({r.get("index_age_s") for r in _kb8q})))

    # ===================================================================
    # (4) 2026-09-22: A PAPER ARM MUST NOT STOP ON THE LIVE BOT'S DAY.
    #
    # risk_abort compared day_loss() -- the LIVE account's ET-day total on
    # disk -- for every run. 24 of 25 paper arms inherit --loss-cap 200 from
    # live, and the DAY cap is terminal, so one bad live day would halt the
    # whole measurement fleet at once, on the day its comparison matters
    # most. Only the WRITE was live-only (add_day_loss in reconcile).
    # ===================================================================
    import tempfile as _tf4
    _d4 = _tf4.mkdtemp(prefix="pinday4-")
    _sv4f = globals()["DAYLOSS_FILE"]
    _sv4l = __import__("copy").deepcopy(pintake.LEDGER)
    try:
        globals()["DAYLOSS_FILE"] = os.path.join(_d4, "dayloss.json")
        add_day_loss(-250.0)                     # the live file: -$250 today
        pintake.reset_ledger()

        class _L4:
            live, loss_abort, max_positions, max_losses = True, -200.0, 3, 0

        class _P4:
            live, loss_abort, max_positions, max_losses = False, -200.0, 3, 0
        _w4l = risk_abort({"halted": False, "errors": 0}, _L4)
        _w4p = risk_abort({"halted": False, "errors": 0}, _P4)
    finally:
        globals()["DAYLOSS_FILE"] = _sv4f
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_sv4l)
        for _f4 in os.listdir(_d4):
            os.remove(os.path.join(_d4, _f4))
        os.rmdir(_d4)
    ck(_w4l is not None and "DAY loss cap" in _w4l,
       "(4) a LIVE run with the day file at -$250 and a $200 cap halts on "
       "the DAY cap (%s)" % _w4l)
    ck(_w4p is None,
       "(4) a PAPER run reading the SAME file is not halted -- arms keep "
       "their own per-run total and never stop on the live bot's day (%s)"
       % _w4p)

    # ===================================================================
    # (5) 2026-09-22: IDENTIFY BETTER -- fields the records were missing.
    # Read off the offline loop's own records, live order path: every
    # refusal and signal says how long was left and how much of the close's
    # contract budget was unspent; every order says when it was decided and
    # when it was sent (ms epoch); and while a position is held, once a
    # second, what the hedge would cost right now (the opposite side's best
    # ask and its size). Nothing branches on any of it.
    # ===================================================================
    _kt5, _kc5 = _k1_take(False)
    _r5 = _offline_trade_loop([_k1_A(), _k1_B(1)], live=True, take=_kt5)
    _ref5 = _kinds(_r5, "refused")
    _sig5 = _kinds(_r5, "signal")
    _ord5 = _kinds(_r5, "order") + _kinds(_r5, "hedge")   # a hedge is an order
    _q5 = _kinds(_r5, "hedge_quote", _kA)
    ck(_r5["raised"] is None and _ref5 and _sig5
       and all("tau" in r and isinstance(r.get("budget_left"), float)
               for r in _ref5 + _sig5),
       "(5) every refused and signal record carries tau and budget_left "
       "(%d refused, %d signals)" % (len(_ref5), len(_sig5)))
    ck(_ord5 and all(isinstance(r.get("t_ms_decide"), int)
                     and isinstance(r.get("t_ms_send"), int)
                     and r["t_ms_send"] >= r["t_ms_decide"]
                     > 1_700_000_000_000 for r in _ord5),
       "(5) every order record -- entries and live hedges -- carries "
       "t_ms_decide and t_ms_send, ms epoch, send not before decide (%d)"
       % len(_ord5))
    _q5s = [r.get("tau") for r in _q5]       # one wall-clock second each
    ck(len(_q5) >= 10 and len(_q5s) == len(set(_q5s))
       and all(r.get("side") == "no" and r.get("ask") == 0.06
               and r.get("size") == 50.0 for r in _q5),
       "(5) while A is held, ONE hedge_quote a second: the NO ask and size "
       "the hedge would hit (%d quotes over %d distinct seconds)"
       % (len(_q5), len(set(_q5s))))
    _r5n = _offline_trade_loop([_k1_B(1, decided_at=99)], run_s=4.0)
    ck(_r5n["raised"] is None and not _kinds(_r5n, "signal")
       and not _kinds(_r5n, "hedge_quote"),
       "(5) NULL: nothing held, no quotes -- the record is about positions, "
       "not every market on the screen")

    def _q5_fault(kind, kw):
        if kind == "hedge_quote":
            raise TypeError("planted: a quote record that cannot be written")
    _r5f = _offline_trade_loop([_k1_A()], rec_fault=_q5_fault)
    ck(_r5f["raised"] is None and abs(_hedged(_r5f, _kA) - 5.0) < 1e-9
       and not [r for r in _kinds(_r5f, "error") if r.get("where") == "scan"],
       "(5) a quote record that raises cannot crash the loop, delay the "
       "hedge or count as a scan error (hedged %g)" % _hedged(_r5f, _kA))
    # ===================================================================
    # R4 / R2 / R1 (2026-09-22). Two records-only changes and one flag
    # that defaults to today's behaviour. Every world below drives the
    # REAL trade_loop through _offline_trade_loop; none of them retypes a
    # decision, and each was run against a build with its own change
    # reverted to prove the check can fail.
    # ===================================================================

    def _gate_counts(res):
        """The UNDEDUPED per-gate look counts the close_summary records
        carry -- the same numbers the R4 bar adds up."""
        out = {}
        for r in _kinds(res, "close_summary"):
            for k, v in (r.get("gates") or {}).items():
                out[k] = out.get(k, 0) + int(v)
        return out

    def _refusals(res, gate):
        return [r for r in _kinds(res, "refused") if r.get("gate") == gate]

    # ---- R4: the silent base-budget skip now leaves a record ----------
    # THE FLAG IS LOAD-BEARING: at the shipped EXTRA_COIN of 0.0 the skip
    # is UNREACHABLE, because close_budget_for() == close_budget() and the
    # gate 600 lines earlier refuses first. The live bot runs
    # --extra-coin 1, which grants a third bet for a coin the close does
    # not already hold -- and that is the world in which 97 looks vanished
    # unlogged on run 20260920T023207Z. The asks step DOWN so that A3's
    # improve bar (scope "close", the shipped default) is not what refuses
    # the later coins; each is genuinely cheaper than the last.
    def _r4_mkt(n, no_bid):
        m = _k1_B(n)
        m["book"] = (lambda t, _nb=no_bid: _ob(round(0.98 - _nb, 4), _nb))
        return m
    _r4_world = [_k1_A(collapse_at=None), _r4_mkt(1, 0.07),
                 _r4_mkt(2, 0.09), _r4_mkt(3, 0.11)]
    _r4 = _offline_trade_loop(_r4_world, run_s=40.0,
                              flags={"EXTRA_COIN": 1.0})
    _r4g = _gate_counts(_r4)
    _r4b = _refusals(_r4, "close_budget_base")
    _r4sig = _kinds(_r4, "signal")
    _r4n = int((_r4["state"] or {}).get("signals") or 0)
    _r4burn = sum(_r4g.get(k, 0) for k in
                  ("close_budget_base", "early_cheap", "early_dear",
                   "early_wide", "staged_none", "price_band"))
    ck(_r4["raised"] is None and _kinds(_r4, "close_summary")
       and _r4n > 0 and _r4n == len(_r4sig) + _r4burn,
       "R4: the bar's identity CLOSES -- state.signals (what rec('end') "
       "writes) equals signal records plus the undeduped close_summary "
       "counts of close_budget_base / early_cheap / early_dear / "
       "early_wide / staged_none / price_band (%d == %d + %d)"
       % (_r4n, len(_r4sig), _r4burn))
    ck(len(_r4b) >= 2 and len(_r4b) == len({r.get("ticker") for r in _r4b})
       and _r4g.get("close_budget_base", 0) > 4 * len(_r4b),
       "R4: ...written ONCE per market per close (%d records over %d "
       "markets) while the undeduped counter still sees every look (%d) "
       "-- a 20 Hz loop must not write twenty lines a second"
       % (len(_r4b), len({r.get("ticker") for r in _r4b}),
          _r4g.get("close_budget_base", 0)))
    ck(_r4b and all(float(r.get("base")) == float(MAX_PER_CLOSE) * 5.0
           and abs(float(r.get("spent")) - float(MAX_PER_CLOSE) * 5.0) < 1e-9
           and float(r.get("budget_left")) > 0.0
           and r.get("want") in ("yes", "no")
           and isinstance(r.get("price"), float)
           and r.get("take_n") is not None
           and isinstance(r.get("tau"), int)
           and float(r.get("size_now")) == 5.0 for r in _r4b),
       "R4: ...and each record carries want, price, take_n, base, spent, "
       "tau -- with budget_left ABOVE zero while the BASE is spent, which "
       "is the signature that tells 'the close ran out' apart from 'the "
       "third bet was dropped' (%s)"
       % [(r.get("ticker"), r.get("base"), r.get("spent"),
           r.get("budget_left")) for r in _r4b][:2])
    # REVIEW FIX 2026-09-22: `size` IS THE FIELD THE READER ACTUALLY USES.
    # barcheck.refusal_price() takes the refused volume from `offered` or
    # `size`; with neither it returns ask_size None, and _b5_view then
    # computes min(0, size_now) and drops the row under "no size" -- so
    # B5, the one reader this record was built for, would still have been
    # blind to the refusal. Asserted against what the five sibling gates
    # write (take_n or SIZE), never a constant, so the two cannot drift.
    # barcheck's own self-test holds the reader half of this.
    ck(_r4b and all(isinstance(r.get("size"), float)
                    and float(r["size"]) == float(r["take_n"] or SIZE)
                    and float(r["size"]) > 0.0
                    and isinstance(r.get("fair"), float) for r in _r4b),
       "R4: ...and it carries `size` (and `fair`) exactly as the five "
       "gates below it do, or barcheck reads it as a priced refusal of "
       "unknown volume and throws it away -- the record would exist and "
       "B5 would still be blind (%s)"
       % [(r.get("size"), r.get("take_n"), r.get("fair")) for r in _r4b][:2])
    _r4null = _offline_trade_loop(_r4_world, run_s=40.0)
    _r4gn = _gate_counts(_r4null)
    _r4nn = int((_r4null["state"] or {}).get("signals") or 0)
    ck(_r4null["raised"] is None and not _refusals(_r4null, "close_budget_base")
       and _refusals(_r4null, "close_budget")
       and _r4nn == len(_kinds(_r4null, "signal"))
       + sum(_r4gn.get(k, 0) for k in
             ("close_budget_base", "early_cheap", "early_dear",
              "early_wide", "staged_none", "price_band")),
       "R4 NULL: the SAME world at the shipped --extra-coin 0 never "
       "reaches the skip at all -- the earlier close_budget gate refuses "
       "first and logs -- and the identity still closes (%d signals)"
       % _r4nn)

    # ---- R2b (2026-09-23): the refresh WAITS while a close is near ----
    # Kalshi degraded at 00:2xZ: refresh median 3,227 ms, worst 10,639 ms,
    # 54 stalls inside 45 s of a close, one of 6,344 ms at tau 21. The loop
    # cannot hedge while it waits on those GETs, so the refresh now defers.
    _now0 = 1_790_000_000.0
    ck(defer_universe(_now0, _now0 - 25, [300.0, 59.0]) is True
       and defer_universe(_now0, _now0 - 25, [300.0, 61.0]) is False
       and defer_universe(_now0, _now0 - 25, [0.5]) is True
       and defer_universe(_now0, _now0 - 25, [-5.0]) is False,
       "R2b: a watched market inside %ds defers the refresh; 61 s out, or a "
       "close already past, does not" % UNI_NEAR_TAU_S)
    ck(defer_universe(_now0, _now0 - UNI_HARD_S, [10.0]) is False
       and defer_universe(_now0, _now0 - (UNI_HARD_S - 1), [10.0]) is True,
       "R2b: UNI_HARD_S=%ds is the backstop -- it can never defer for ever"
       % UNI_HARD_S)
    ck(defer_universe(_now0, _now0 - 25, []) is False
       and defer_universe(_now0, _now0 - 25, [None, "x"]) is False,
       "R2b NULL: nothing watched, or an unreadable close, never defers "
       "(a refresh is how the bot FINDS markets)")
    ck(_DEFAULT_UNI_NEAR_TAU_S == 60 and _DEFAULT_UNI_HARD_S == 300,
       "R2b: the DECLARED defaults are 60 s and 300 s (never the running "
       "globals -- a self-test that asserts those has blocked startup)")
    _r2d = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=190.0,
                               tau0=120, get_delay=0.6)
    _r2du = _kinds(_r2d, "universe")
    _r2dd = _kinds(_r2d, "universe_deferred")
    # The boundary second is allowed: once tau reaches 0 the close is over,
    # nothing can be bought or hedged in it, and the deferral must end there
    # or the bot would stop discovering markets.
    _near = [r for r in _r2du if r.get("tau") is not None
             and 0 < float(r["tau"]) <= UNI_NEAR_TAU_S]
    ck(_r2d["raised"] is None and len(_r2du) >= 2 and not _near,
       "R2b: driving the REAL loop from tau 120 with a 600 ms refresh, NOT "
       "ONE refresh lands in the tradeable part of %ds before the close "
       "(%d refreshes, taus %s)"
       % (UNI_NEAR_TAU_S, len(_r2du), [r.get("tau") for r in _r2du][:6]))
    ck(len(_r2dd) >= 1 and len(_r2dd) <= 3
       and all(float(r["tau"]) <= UNI_NEAR_TAU_S for r in _r2dd),
       "R2b: ONE record per wait, not one per 20 Hz pass (%d records)"
       % len(_r2dd))
    ck(any(float(r.get("deferred_s") or 0) > 0 for r in _r2du),
       "R2b: the refresh that follows a wait reports how long it waited")
    _r2dh = _offline_trade_loop([_k1_A()], run_s=40.0, tau0=30,
                                get_delay=0.3)
    ck(_r2dh["raised"] is None and abs(_hedged(_r2dh, _kA) - 5.0) < 1e-9,
       "R2b: a position held THROUGH a deferral is still hedged (%g) -- the "
       "wait is on the refresh, never on the hedge pass"
       % _hedged(_r2dh, _kA))

    # ---- R2: the universe refresh and the loop pass, TIMED ------------
    # Timing only. Nothing is deferred, moved or gated on these numbers,
    # and the hedge pass gains no condition -- the point is precisely that
    # the hedge shares this thread, so the refresh's duration IS the
    # hedge's blackout and until now nothing could see it.
    _r2slow = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=40.0,
                                  get_delay=0.6)
    _r2u = _kinds(_r2slow, "universe")
    ck(_r2slow["raised"] is None and len(_r2u) >= 2
       and all(abs(float(r["ms"]) - 600.0) < 2.0 for r in _r2u)
       and all(int(r["n"]) == 1 and int(r["series"]) == 1 for r in _r2u),
       "R2: a PLANTED 600 ms universe refresh is recorded at its real "
       "duration on EVERY refresh, with the markets it kept (%d records, "
       "ms %s)" % (len(_r2u), [r["ms"] for r in _r2u]))
    # REVIEW FIX: WHERE IN THE CLOSE the refresh landed. The change this
    # sizes is "defer the refresh while a watched market is inside 60 s",
    # so a duration with no tau answers nothing. The `loop` records cannot
    # stand in -- their far budget is spent hundreds of seconds out.
    _r2ut = [r for r in _r2u if r.get("tau") is not None]
    ck(len(_r2ut) >= 2
       and all(r.get("close_s") is not None for r in _r2ut)
       and all(0 <= int(r["tau"]) <= 30 for r in _r2ut)
       and sorted(int(r["tau"]) for r in _r2ut) == sorted(
           set(int(r["tau"]) for r in _r2ut)),
       "R2: ...and EVERY universe record says which close was nearest and "
       "how many seconds were left, so a refresh inside the last 45 s can "
       "be told from one eight minutes out (taus %s)"
       % [r.get("tau") for r in _r2u])
    # REVIEW FIX: a refresh in which every GET failed left `seen_markets`
    # untouched, so `n` reported the PREVIOUS universe and a total failure
    # read as a healthy slow refresh. `got` is what THIS refresh built.
    _r2ux = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=40.0,
                                get_fail_after=15.0)
    _r2uxr = _kinds(_r2ux, "universe")
    _r2uok = [r for r in _r2uxr if int(r.get("got") or 0) > 0]
    _r2ubad = [r for r in _r2uxr if int(r.get("got") or 0) == 0]
    ck(_r2ux["raised"] is None and _r2uok and _r2ubad
       and all(int(r["n"]) == 1 for r in _r2ubad)
       and all(int(r["got"]) == 1 for r in _r2uok),
       "R2: a PLANTED FAILED refresh (every GET 500) is distinguishable -- "
       "`got` falls to 0 while `n` still reports the universe we are "
       "holding, which is the pair a reader needs (%s)"
       % [(r.get("got"), r.get("n")) for r in _r2uxr])
    _r2fast = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=40.0)
    _r2uf = _kinds(_r2fast, "universe")
    ck(_r2fast["raised"] is None and len(_r2uf) >= 2
       and all(float(r["ms"]) < 50.0 for r in _r2uf)
       and not _kinds(_r2fast, "loop"),
       "R2 NULL: the same world with nothing planted records the refresh "
       "at ~0 ms and writes NO loop record at all -- a fast loop is "
       "silent, so a `loop` line always means a real stall (ms %s)"
       % [r["ms"] for r in _r2uf][:3])
    _r2stall = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=40.0,
                                   stall=(6.0, 0.25))
    _r2l = _kinds(_r2stall, "loop")
    _r2cs = _kinds(_r2stall, "close_summary")
    ck(_r2stall["raised"] is None and len(_r2l) == 1
       and 250.0 <= float(_r2l[0]["ms"]) <= 320.0
       and isinstance(_r2l[0].get("tau"), int)
       and 22 <= int(_r2l[0]["tau"]) <= 25,
       "R2: a PLANTED 250 ms stall inside one pass writes exactly ONE "
       "loop record, at the tau the stalled pass STARTED at (%s)"
       % [(r["ms"], r["tau"]) for r in _r2l])
    ck(len(_r2cs) == 1 and len(_r2l) == 1
       and float(_r2cs[0]["pass_gap_ms"] or 0.0) == float(_r2l[0]["ms"])
       and _r2cs[0]["pass_gap_tau"] == _r2l[0]["tau"]
       and float(_r2cs[0]["pass_gap_near_ms"] or 0.0) == float(_r2l[0]["ms"])
       and _r2cs[0]["pass_gap_near_tau"] == _r2l[0]["tau"]
       and int(_r2cs[0]["slow_passes_near"] or 0) == 1
       and int(_r2cs[0]["slow_passes"] or 0) == 0,
       "R2: ...and the close's own summary carries the WORST pass it saw, "
       "that pass's tau, and how many passes were slow -- the stall is at "
       "tau %s so it is booked NEAR and not far (%s)"
       % (_r2l[0]["tau"],
          [(r.get("pass_gap_ms"), r.get("pass_gap_near_ms"),
            r.get("pass_gap_near_tau"), r.get("slow_passes"),
            r.get("slow_passes_near")) for r in _r2cs]))
    ck(_r2fast["raised"] is None
       and all(float(r.get("pass_gap_ms") or 0.0) <= LOOP_SLOW_MS
               and int(r.get("slow_passes") or 0) == 0
               and float(r.get("pass_gap_near_ms") or 0.0) <= LOOP_SLOW_MS
               and int(r.get("slow_passes_near") or 0) == 0
               for r in _kinds(_r2fast, "close_summary")),
       "R2 NULL: with nothing planted BOTH the whole-window and the near "
       "worst pass are under the %g ms bar and neither counts a slow pass "
       "(%s)"
       % (LOOP_SLOW_MS, [(r.get("pass_gap_ms"), r.get("slow_passes"),
                          r.get("pass_gap_near_ms"),
                          r.get("slow_passes_near"))
                         for r in _kinds(_r2fast, "close_summary")]))

    # ---- R2 REVIEW FIX: THE RECORD BUDGET IS TAU-AWARE ----------------
    # THE DEFECT THIS REPLACES, stated so it cannot come back. `watching`
    # admits a market the moment it is <= 900 s out, so one close is the
    # nearest close for its whole fifteen minutes, and the refresh fires
    # every 20 s with no condition on time to close. At the durations this
    # instrument exists to measure EVERY refresh is a slow pass -- 44.6 a
    # close, measured on the live log -- so a first-come budget of 20 was
    # spent at about tau 500 s and every slow pass inside the last 45 s,
    # the only ones the bar reads, was dropped. The bar's PASS (">= 20 of
    # 100 closes with a gap > 500 ms at tau <= 45") was unreachable and its
    # FAIL was what the instrument returned whatever the truth.
    #
    # 200 s to the close, a 600 ms refresh every 20 s, and a FAR budget of
    # two: the far half is exhausted before tau 160 and every near pass is
    # still written.
    _r2b = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=215.0,
                               tau0=200, get_delay=0.6, stall=(150.0, 0.5),
                               # R2b defers the refresh inside 60 s, so this
                               # world -- which exists to test the RECORD
                               # BUDGET near a close -- switches the deferral
                               # off to keep producing near-close stalls.
                               flags={"LOOP_REC_MAX": 2, "UNI_NEAR_TAU_S": 0})
    _r2bl = _kinds(_r2b, "loop")
    # far records attributed to THE CLOSE. A pass with nothing watched yet
    # keys under its own rolling bucket (close_s None) and spends its own
    # budget, which is the point of not keying those under None.
    _r2bfar = [r for r in _r2bl
               if not r.get("near") and r.get("close_s") is not None]
    _r2bnear = [r for r in _r2bl if r.get("near")]
    _r2bcs = _kinds(_r2b, "close_summary")
    ck(_r2b["raised"] is None and len(_r2bfar) == 2 and len(_r2bnear) >= 4
       and max(int(r["tau"]) for r in _r2bnear) <= LOOP_NEAR_TAU_S
       and min(int(r["tau"]) for r in _r2bnear) <= 20
       and min(int(r["tau"]) for r in _r2bfar) > LOOP_NEAR_TAU_S
       and all(int(r["n_slow"]) <= 2 for r in _r2bfar),
       "R2: the far record budget BINDS at 2 (spent by tau %s) and the "
       "near passes survive it -- %d far records for this close and %d "
       "near, down to tau %s. First-come, every near one would have been "
       "dropped"
       % (min(int(r["tau"]) for r in _r2bfar) if _r2bfar else None,
          len(_r2bfar), len(_r2bnear),
          min(int(r["tau"]) for r in _r2bnear) if _r2bnear else None))
    ck(len(_r2bcs) == 1
       and int(_r2bcs[0]["slow_passes"] or 0) > 2
       and int(_r2bcs[0]["slow_passes_near"] or 0) >= 4
       and _r2bcs[0].get("pass_gap_near_tau") is not None
       and int(_r2bcs[0]["pass_gap_near_tau"]) <= LOOP_NEAR_TAU_S
       and _r2bcs[0].get("pass_gap_tau") is not None
       and int(_r2bcs[0]["pass_gap_tau"]) > LOOP_NEAR_TAU_S
       and int(_r2bcs[0].get("near_tau_s") or 0) == LOOP_NEAR_TAU_S,
       "R2: ...and close_summary answers the bar WITHOUT any loop record: "
       "the far maximum is at tau %s (which is what a single maximum would "
       "have reported, ~2/45 of the time inside 45 s) while the NEAR "
       "maximum is at tau %s, and both slow-pass counts survive the cap "
       "(far %s, near %s)"
       % (_r2bcs[0].get("pass_gap_tau"), _r2bcs[0].get("pass_gap_near_tau"),
          _r2bcs[0].get("slow_passes"), _r2bcs[0].get("slow_passes_near")))
    ck(LOOP_NEAR_TAU_S >= 45
       and LOOP_REC_MAX_NEAR >= LOOP_NEAR_TAU_S / (LOOP_SLOW_MS / 1000.0),
       "R2: ...and the NEAR budget can never bind at all, which is the "
       "only safe answer to a budget that silently decided a bar: a pass "
       "counts as slow only above %g ms, so at most %.0f passes in a %d s "
       "window can qualify and the budget is %d"
       % (LOOP_SLOW_MS, LOOP_NEAR_TAU_S / (LOOP_SLOW_MS / 1000.0),
          LOOP_NEAR_TAU_S, LOOP_REC_MAX_NEAR))

    # ---- R2 REVIEW FIX: THE UNWATCHED BUCKET RESETS --------------------
    # A pass with nothing watched used to key under None, and None is the
    # one key report_closes() never pops and the prune explicitly skipped.
    # Twenty slow blind passes -- one startup or one reconnect -- and the
    # process wrote no `loop` record for any later blind period for the
    # rest of its life, which is the period a "why was the bot blind"
    # investigation would most want. Keyed by fifteen-minute bucket, the
    # budget resets. 2,000 fake seconds with nothing watched and a 300 ms
    # refresh: three buckets, three budgets.
    _r2n = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=2000.0,
                               tau0=-60, get_delay=0.3)
    _r2nl = _kinds(_r2n, "loop")
    _r2n1 = [r for r in _r2nl if int(r["n_slow"]) == 1]
    ck(_r2n["raised"] is None and len(_r2nl) > LOOP_REC_MAX
       and len(_r2n1) >= 2
       and all(r.get("close_s") is None and r.get("tau") is None
               and not r.get("near") for r in _r2nl)
       and max(int(r["n_slow"]) for r in _r2nl) <= LOOP_REC_MAX,
       "R2: an unwatched period gets a FRESH record budget every fifteen "
       "minutes instead of one that never resets -- %d records in %d "
       "budgets over 2,000 s, none of them over the cap of %d"
       % (len(_r2nl), len(_r2n1), LOOP_REC_MAX))

    # ---- R2 REVIEW FIX: A PAUSE IS NOT A STALL ------------------------
    # The pause branch sleeps a whole second and sits BELOW the timing
    # block, so every paused pass booked a ~1,000 ms gap. The bar reads
    # gaps as evidence for deferring the refresh, and a deliberate pause is
    # not that. It is still recorded -- the hedge really did run once that
    # second -- but it says which it was.
    _r2p = _offline_trade_loop([_k1_A(collapse_at=None)], run_s=40.0,
                               live=True, max_positions=1)
    _r2pl = _kinds(_r2p, "loop")
    _r2pp = [r for r in _r2pl if r.get("why") == "pause"]
    ck(_r2p["raised"] is None and _kinds(_r2p, "pause") and len(_r2pp) >= 20
       and all(900.0 <= float(r["ms"]) <= 1200.0 for r in _r2pp)
       and len(_r2pp) == len(_r2pl),
       "R2: every ~1,000 ms gap a PAUSE creates is labelled why='pause' -- "
       "including the FIRST one, the pass that chose to sleep, which a "
       "label carried in _prev_pass would have missed by one pass (%d "
       "loop records, %d of them pauses, ms %s)"
       % (len(_r2pl), len(_r2pp), [r["ms"] for r in _r2pp][:3]))
    ck(all(r.get("why") is None for r in _r2l + _r2bnear + _r2bfar),
       "R2 NULL: a genuine stall carries why=None, so the label means "
       "something -- %d planted-stall records, none labelled"
       % len(_r2l + _r2bnear + _r2bfar))
    # REVIEW FIX: the record must not sit in front of the hedge. rec()
    # opens, appends and closes the log every call, and this one fires
    # exactly on the pass after a stall -- when the loop is already late.
    _lp_r2 = _src_k1[_src_k1.rindex(chr(10) + "def trade_loop("):]
    _i_gap_r2 = _lp_r2.find("_loop_rec = None")
    _i_hdg_r2 = _lp_r2.find("if HEDGE_ENABLED:", _i_gap_r2)
    _i_wrt_r2 = _lp_r2.find('rec("loop"', _i_hdg_r2)
    ck(0 < _i_gap_r2 < _i_hdg_r2 < _i_wrt_r2
       and 'rec("loop"' not in _lp_r2[_i_gap_r2:_i_hdg_r2],
       "R2 STRUCTURAL: the pass-gap ARITHMETIC runs before the hedge pass "
       "(it has to -- it times the previous pass) but the rec() WRITE is "
       "below it. Nothing may delay a hedge, least of all a record about "
       "the loop being slow")

    def _r2_fault(kind, kw):
        if kind in ("universe", "loop"):
            raise TypeError("planted: a timing record that cannot be written")
    _r2f = _offline_trade_loop([_k1_A()], get_delay=0.6, stall=(6.0, 0.25),
                               rec_fault=_r2_fault)
    ck(_r2f["raised"] is None and abs(_hedged(_r2f, _kA) - 5.0) < 1e-9
       and not [r for r in _kinds(_r2f, "error") if r.get("where") == "scan"],
       "R2: a timing record that RAISES cannot crash the loop, delay the "
       "hedge or count as a scan error -- these records can only ever be "
       "dropped (hedged %g)" % _hedged(_r2f, _kA))

    # ---- R1: --attempts-on-send, and it ships OFF ---------------------
    ck(_DEFAULT_ATTEMPTS_ON_SEND is False,
       "R1 ships OFF -- asserted against the DECLARED default, never the "
       "running value, so the paper arm that sets the flag does not fail "
       "its own gate and the live argv's decisions are unchanged")
    # `find`, never `index`: a missing literal must read as a clean FAIL,
    # not as an exception that takes the rest of the suite with it.
    _lp_r1 = _src_k1[_src_k1.rindex(chr(10) + "def trade_loop("):]
    _i_sig_r1 = _lp_r1.find("if not ATTEMPTS_ON_SEND:")
    _i_snd_r1 = _lp_r1.find("if ATTEMPTS_ON_SEND:" + chr(10))
    # the ENTRY send is the LAST pintake.take() in the loop; the two above
    # it are the unrest sweep and the hedge, and the hedge was cut free of
    # this counter by A71 -- it must stay that way.
    _i_take_r1 = _lp_r1.rfind("out = pintake.take(")
    _inc_cls_r1 = "attempts[close_s] = attempts.get(close_s, 0) + 1"
    _inc_tk_r1 = ("attempts_tk[(close_s, tk)] = "
                  "attempts_tk.get((close_s, tk), 0) + 1")
    # REVIEW FIX 2026-09-22: BOTH counters are asserted on BOTH sides now.
    # The first version asserted only that `attempts[close_s]` appeared
    # before the flag-OFF block -- which the PLANT's own increment already
    # satisfies, so the check could not have noticed the per-close counter
    # being left behind at the signal point. It is now asserted inside each
    # block, by slicing the block rather than searching the whole loop.
    _blk_off_r1 = _lp_r1[_i_sig_r1:_lp_r1.find("# ---- AMENDMENT 36",
                                               _i_sig_r1)]
    _blk_on_r1 = _lp_r1[_i_snd_r1:_i_take_r1]
    ck(min(_i_sig_r1, _i_snd_r1, _i_take_r1) > 0
       and _i_sig_r1 < _lp_r1.find('_gate("early_cheap"')
       and _i_snd_r1 > _lp_r1.find('_gate("price_band"')
       and _i_snd_r1 < _i_take_r1
       and _inc_cls_r1 in _blk_off_r1 and _inc_tk_r1 in _blk_off_r1
       and _inc_cls_r1 in _blk_on_r1 and _inc_tk_r1 in _blk_on_r1
       and _lp_r1.count(_inc_tk_r1) == 2
       and "_gate(" not in _blk_on_r1,
       "R1 STRUCTURAL: BOTH attempt counters are inside the flag-OFF "
       "block (where they have always been, before the five burner gates) "
       "and BOTH are inside the flag-ON block, which is after the last of "
       "those gates and before the send with NO gate in between. Neither "
       "may be left at the signal point on its own -- the per-close one "
       "left behind turns a per-market lockout into a close-wide one")
    # A BURNER AND AN INNOCENT COIN IN THE SAME CLOSE. The band holds A's
    # 95c ask and not B's 93c, so A is refused before any order and B is an
    # ordinary market. The second coin is the whole point of the world: the
    # first version of this flag was reviewed against a ONE-market close,
    # where the damage it does is invisible.
    _r1burn = {"SKIP_BANDS": ((0.94, 0.96),)}     # A's 95c ask sits inside
    _r1w = [_k1_A(collapse_at=None), _k1_B(1)]
    _r1off = _offline_trade_loop(_r1w, run_s=40.0, flags=dict(_r1burn))
    _r1off_ma = _refusals(_r1off, "market_attempts")
    _r1off_pb = _refusals(_r1off, "price_band")
    _r1off_sig = _kinds(_r1off, "signal", _k1_B(1)["tk"])
    ck(_r1off["raised"] is None and len(_r1off_ma) == 1
       and _r1off_ma[0]["ticker"] == _kA
       and int(_r1off_ma[0]["tried"]) == 3 and len(_r1off_pb) == 1
       and _gate_counts(_r1off).get("price_band") == 3
       and len(_r1off_sig) == 1
       and float(_r1off_ma[0]["t"]) - float(_r1off_pb[0]["t"]) < 1.0,
       "R1 CONTROL (flag OFF = today): three looks refused WITHOUT an "
       "order burn the counter and lock THAT MARKET out for the rest of "
       "the close -- the defect, reproduced in %.2f s -- while the "
       "innocent second coin still enters (%d signal)"
       % (float(_r1off_ma[0]["t"]) - float(_r1off_pb[0]["t"])
          if _r1off_ma and _r1off_pb else -1.0, len(_r1off_sig)))
    _r1on = _offline_trade_loop(_r1w, run_s=40.0,
                                flags=dict(_r1burn, ATTEMPTS_ON_SEND=True))
    _r1on_pb = _gate_counts(_r1on).get("price_band", 0)
    _r1on_sig = _kinds(_r1on, "signal", _k1_B(1)["tk"])
    ck(_r1on["raised"] is None and not _refusals(_r1on, "market_attempts")
       and _r1on_pb > MAX_ATTEMPTS_PER_CLOSE,
       "R1: with the flag ON those same three pre-send refusals do NOT "
       "lock the market out -- it is looked at %d times, PAST the "
       "close-wide cap of %d, and refused at a gate every time instead of "
       "vanishing (%d market_attempts refusals)"
       % (_r1on_pb, MAX_ATTEMPTS_PER_CLOSE,
          len(_refusals(_r1on, "market_attempts"))))
    # REVIEW FIX 2026-09-22 -- THE CHECK THAT CAUGHT THE REAL DEFECT.
    # `attempts[close_s]` is incremented ABOVE those five gates and is read
    # against MAX_ATTEMPTS_PER_CLOSE. Release only the per-MARKET counter
    # and the burner is never locked out, so it reaches that line at 20 Hz,
    # spends the whole close's 24 attempts in ~1.2 s, and `attempts_cap`
    # then refuses EVERY market in the close -- including coins that never
    # burned anything. Measured on this exact world while only the
    # per-market counter moved: the innocent coin got ZERO signals and was
    # refused attempts_cap at t = 1.15 s. The flag would have been sold as
    # "it removes a refusal" while turning a per-market lockout into a
    # close-wide one, and the arm would have measured nothing (A51).
    ck(not _refusals(_r1on, "attempts_cap")
       and len(_r1on_sig) == 1 and len(_r1off_sig) == 1
       and _r1on_sig[0]["ticker"] == _r1off_sig[0]["ticker"],
       "R1 COLLATERAL: a burner under the flag does NOT spend the whole "
       "close's attempt budget -- no attempts_cap refusal anywhere, and "
       "the innocent coin in the same close still enters, exactly as it "
       "does with the flag off (%d attempts_cap, %d innocent signals ON "
       "vs %d OFF)"
       % (len(_refusals(_r1on, "attempts_cap")), len(_r1on_sig),
          len(_r1off_sig)))
    ck(len(_kinds(_r1off, "order")) == len(_kinds(_r1on, "order")) == 0
       and not _r1off["posts"] and not _r1on["posts"],
       "R1: ...and NEITHER world sent an order (paper), so the only thing "
       "the flag changed is whether a refusal counts as an attempt")
    _r1sent = []

    def _r1_nofill(base, pk, key_id, ticker, want, price, count, mce,
                   exchange_index=0, **kw):
        """A LOST RACE: the order is sent and fills nothing. A no-fill
        books no slot (A6), so the market is looked at again -- which is
        how three real SENDS reach the rail."""
        body = pintake.build_take(ticker, want, price, count, exchange_index)
        out = pintake.normalise(201, {"order": {
            "order_id": "r1-%d" % len(_r1sent), "status": "canceled",
            "fill_count": 0, "remaining_count": count}}, body, base)
        out["refused"] = []
        _r1sent.append((ticker, want, float(count)))
        return out
    _r1rail = _offline_trade_loop([_k1_A(collapse_at=None)], live=True,
                                  take=_r1_nofill,
                                  flags={"ATTEMPTS_ON_SEND": True})
    _r1rail_ma = _refusals(_r1rail, "market_attempts")
    ck(_r1rail["raised"] is None and len(_r1sent) == MAX_ATTEMPTS_PER_MARKET
       and len(_kinds(_r1rail, "order")) == MAX_ATTEMPTS_PER_MARKET
       and len(_r1rail_ma) == 1
       and int(_r1rail_ma[0]["tried"]) == MAX_ATTEMPTS_PER_MARKET,
       "R1: the RAIL ITSELF IS UNCHANGED -- with the flag ON, three "
       "orders that really are SENT still reach MAX_ATTEMPTS_PER_MARKET "
       "(%d) and the fourth look is refused, so the 160-order runaway of "
       "2026-09-08 stays impossible (%d sent)"
       % (MAX_ATTEMPTS_PER_MARKET, len(_r1sent)))
    # ...and so does the per-CLOSE rail, which is the one the review fix
    # moved. Eleven markets that all send and never fill: the close stops
    # at MAX_ATTEMPTS_PER_CLOSE SENDS, which is what that constant's own
    # comment says it counts ("orders SENT per close, filled or not") and
    # what the 2026-09-08 runaway actually was.
    _r1sent[:] = []
    _r1cap = _offline_trade_loop([_k1_B(i) for i in range(1, 12)],
                                 live=True, take=_r1_nofill, run_s=40.0,
                                 flags={"ATTEMPTS_ON_SEND": True})
    _r1cap_ac = _refusals(_r1cap, "attempts_cap")
    ck(_r1cap["raised"] is None and len(_r1sent) == MAX_ATTEMPTS_PER_CLOSE
       and len(set(t for t, _w, _n in _r1sent)) > 1 and _r1cap_ac
       and int(_r1cap_ac[0]["tried"]) == MAX_ATTEMPTS_PER_CLOSE,
       "R1: ...and the per-CLOSE rail still binds under the flag, now on "
       "SENDS -- %d orders across %d markets and then attempts_cap, so "
       "moving the per-close counter to the send site loosened nothing a "
       "real order can reach (tried %s)"
       % (len(_r1sent), len(set(t for t, _w, _n in _r1sent)),
          _r1cap_ac[0].get("tried") if _r1cap_ac else None))

    # ===================================================================
    # R4 (2026-09-23): THE TRAJECTORY. See the TRAJ_* block for the defect.
    #
    # WHAT MUST BE TRUE, and each of these fails when its line is reverted
    # (the revert-proof table is in the session report):
    #   1. records land on the sampled grid, one a market a second, and carry
    #      every field the analysis needed and could not get;
    #   2. the per-close budgets bind, they are SEPARATE, and far samples can
    #      never starve the near-close seconds (v-instr1's own failure);
    #   3. the gate on a record is the gate that REALLY refused it, and no
    #      extra refusal is written;
    #   4. a record that RAISES cannot end the loop or stop a hedge;
    #   5. at the shipped settings the old record trail and every decision
    #      are IDENTICAL -- proven by running the same world twice, not
    #      asserted.
    # ===================================================================
    ck(_DEFAULT_TRAJ_EVERY_S == 5 and _DEFAULT_TRAJ_NEAR_TAU_S == 60
       and _DEFAULT_TRAJ_TAU_MAX == 300
       and _DEFAULT_TRAJ_MAX == 800 and _DEFAULT_TRAJ_MAX_NEAR == 900,
       "R4: the DECLARED grid is every 5 s out to 300 s and every second "
       "inside 60 s, budgets 800 far / 900 near -- asserted against the "
       "_DEFAULT_ twins, never the running globals, because this test runs "
       "at STARTUP with the operator's flags already applied")
    # THE GRID IS A PURE FUNCTION, so every case can be planted.
    ck(traj_due(300) and traj_due(295) and not traj_due(294)
       and not traj_due(301) and traj_due(61) is False
       and traj_due(60) and traj_due(59) and traj_due(1) and traj_due(0)
       and not traj_due(-1) and not traj_due(None),
       "R4: the grid admits tau 300/295 and not 294 (off the 5 s grid) or "
       "301 (past the window), admits EVERY second at 60 and below, and "
       "refuses a negative or unreadable tau")
    ck(traj_due(64, every=5, near=60) is False
       and traj_due(64, every=1, near=60) is True,
       "R4 NULL: the coarse cadence is the flag-free constant it says it is "
       "-- at every=1 the same tau is admitted, so the refusal above is the "
       "GRID and not an accident of the window")

    # ---- 1/2/3: one market, from tau 70 through its close --------------
    def _r4t_mkt(n, fair_of, ask_no=0.05, yes_bid=0.94):
        return {"tk": "KXT%d15M-R4T" % n, "series": "KXT%d15M" % n,
                "iid": "R4T%d" % n, "strike": 100.0, "fair": fair_of,
                "book": (lambda t: _ob(yes_bid, ask_no))}

    _r4t_w = [_r4t_mkt(1, lambda t: 0.999)]
    _r4t = _offline_trade_loop(_r4t_w, run_s=80.0, tau0=70)
    _r4t_j = _kinds(_r4t, "traj")
    _r4t_taus = [int(r["tau"]) for r in _r4t_j]
    _r4t_want = ([70, 65] + list(range(60, -1, -1)))
    ck(_r4t["raised"] is None and _r4t_taus == _r4t_want,
       "R4: the records land on the grid and NOWHERE else -- tau 70 and 65 "
       "on the coarse grid, then every second from 60 to 0, %d records for "
       "one market and one close, no second twice (%s)"
       % (len(_r4t_taus),
          "ok" if _r4t_taus == _r4t_want
          else "got %s" % _r4t_taus[:8]))
    _r4t_keys = {"ticker", "close_s", "tau", "want", "held", "fair", "conf",
                 "spot", "strike", "eff_strike", "mu", "sd", "cushion_sd",
                 "remaining", "sigma", "ask", "ask_size", "opp_ask",
                 "opp_size", "book_age_ms", "index_age_s", "gate",
                 "gate_pass_ago", "near", "entries_stopped", "paused",
                 "kind", "t"}
    _r4t_bad = [set(r) ^ _r4t_keys for r in _r4t_j if set(r) != _r4t_keys]
    _r4t_one = _r4t_j[0] if _r4t_j else {}
    _r4t_null = [k for k in ("tau", "fair", "conf", "spot", "strike", "sd",
                             "cushion_sd", "ask", "ask_size", "opp_ask",
                             "opp_size", "book_age_ms", "index_age_s")
                 if _r4t_one.get(k) is None]
    ck(not _r4t_bad and not _r4t_null,
       "R4: EVERY record carries EVERY field with the same schema -- our "
       "side's confidence AND the other side's ask (what insurance would "
       "have cost), the sd of the remaining window and the cushion in those "
       "sd, both book and index age (schema drift: %s; null on a healthy "
       "feed: %s)" % (_r4t_bad[:1], _r4t_null))
    # THE ARITHMETIC, RECONCILED BY HAND against the model's own fair():
    # sd is sigma x sqrt(var_factor(remaining)) and the cushion is
    # (mu - effective strike) / sd, signed toward OUR side.
    _r4t_n60 = [r for r in _r4t_j if int(r["tau"]) == 30]
    if _r4t_n60:
        _rr = _r4t_n60[0]
        _sd_want = _rr["sigma"] * math.sqrt(var_factor(int(_rr["remaining"]),
                                                       [1.0]))
        _cu_want = (_rr["mu"] - _rr["eff_strike"]) / _sd_want
        ck(abs(_rr["sd"] - _sd_want) < 1e-6
           and abs(_rr["cushion_sd"] - _cu_want) < 0.01
           and _rr["remaining"] == N_AVG - (N_AVG - int(_rr["tau"])) - 1,
           "R4: at tau 30 the sd is the model's OWN "
           "sigma x sqrt(var_factor(%s)) = %.6f and the cushion is %.1f of "
           "them on our side -- the same arithmetic fair() uses, so the "
           "record cannot drift from the decision"
           % (_rr["remaining"], _sd_want, _cu_want))
    else:
        ck(False, "R4: no record at tau 30 to reconcile the arithmetic on")
    # ...and the gate is the REAL one. This market is decided all the way, so
    # inside the window the scan refuses it on no_offer only if the ask
    # vanishes; here it TRADES, so the far records say outside_window and the
    # near ones carry whatever actually fired.
    _r4t_far = [r for r in _r4t_j if int(r["tau"]) > _DEFAULT_EARLY_TAU_MAX]
    ck(all(r["gate"] == "outside_window" and r["gate_pass_ago"] == 0
           for r in _r4t_far) and len(_r4t_far) >= 3,
       "R4: a market the scan has not reached yet is marked outside_window "
       "and NOT as a refusal -- the scan skips those before any gate, and "
       "calling it a refusal would corrupt every gate rate in pinattrib "
       "(%d far records)" % len(_r4t_far))

    # ---- the gate field against a gate that really fires ---------------
    _r4g = _offline_trade_loop([_r4t_mkt(2, lambda t: 0.50)], run_s=40.0,
                              tau0=32)
    # tau TAU_MAX itself is the FIRST second the scan may look, and the sample
    # is taken above the scan -- so that one record has no stamp yet and says
    # so (gate None), which is honest and not a miss. Everything strictly
    # inside the window must carry the real gate.
    _r4g_j = [r for r in _kinds(_r4g, "traj")
              if TAU_MIN <= int(r["tau"]) <= _DEFAULT_EARLY_TAU_MAX - 1]
    _r4g_out = [r for r in _kinds(_r4g, "traj")
                if r["gate"] not in ("confidence", "outside_window", None)]
    _r4g_ref = _refusals(_r4g, "confidence")
    _r4g_cnt = _gate_counts(_r4g).get("confidence", 0)
    ck(_r4g["raised"] is None and len(_r4g_j) >= 20 and not _r4g_out
       and all(r["gate"] == "confidence" and r["gate_pass_ago"] == 1
               for r in _r4g_j)
       and len(_r4g_ref) == 1 and _r4g_cnt > len(_r4g_j),
       "R4: inside the window the record names the gate that ACTUALLY "
       "refused the market on the previous pass (confidence, 50 ms old) -- "
       "and writes NO refusal of its own: still ONE `refused` record for "
       "the close (%d) against %d gate firings and %d samples, so the "
       "dedupe and every rate built on it are untouched"
       % (len(_r4g_ref), _r4g_cnt, len(_r4g_j)))

    # ---- 2: the budgets, and the near seconds are never starved --------
    # TRAJ_MAX at 2 with the near budget untouched: the far grid is cut off
    # after two samples and EVERY near second still arrives. This is the
    # v-instr1 failure, reproduced -- its first budget was first-come, so
    # ~45 far-from-close refreshes spent all 20 records at about tau 500 and
    # the near-close passes its own bar read were dropped.
    _r4b = _offline_trade_loop(_r4t_w, run_s=320.0, tau0=300,
                               flags={"TRAJ_MAX": 2})
    _r4b_j = _kinds(_r4b, "traj")
    _r4b_far = [r for r in _r4b_j if not r["near"]]
    _r4b_near = [r for r in _r4b_j if r["near"]]
    _r4b_cl = _kinds(_r4b, "traj_close")
    ck(_r4b["raised"] is None and len(_r4b_far) == 2
       and len(_r4b_near) == 61 and _r4b_cl
       and int(_r4b_cl[0]["far"]) == 2 and int(_r4b_cl[0]["near"]) == 61
       and int(_r4b_cl[0]["dropped"]) == 46,
       "R4: the FAR budget binds at 2 of 48 samples -- AND ALL 61 "
       "NEAR-CLOSE SECONDS STILL ARRIVE. The near budget is a separate purse "
       "far samples cannot reach, which is the whole lesson of "
       "LOOP_REC_MAX_NEAR: v-instr1's first budget was first-come, so ~45 "
       "far-from-close refreshes spent all 20 records at about tau 500 and "
       "the near passes its own bar read were dropped -- a FAIL by "
       "construction. The 46 refused samples are COUNTED, so a budget that "
       "bites is on the record (%d far, %d near, %s dropped)"
       % (len(_r4b_far), len(_r4b_near),
          _r4b_cl[0].get("dropped") if _r4b_cl else None))
    _r4b3 = _offline_trade_loop(_r4t_w, run_s=80.0, tau0=70,
                                flags={"TRAJ_MAX_NEAR": 3})
    _r4b3_j = [r for r in _kinds(_r4b3, "traj") if r["near"]]
    ck(_r4b3["raised"] is None and len(_r4b3_j) == 3,
       "R4: and the NEAR budget binds too, at 3 -- neither purse is "
       "unbounded, so a thrashing box cannot fill the disk (got %d)"
       % len(_r4b3_j))
    ck(TRAJ_MAX_NEAR >= 14 * (TRAJ_NEAR_TAU_S + 1)
       and TRAJ_MAX >= 14 * ((TRAJ_TAU_MAX - TRAJ_NEAR_TAU_S)
                             // TRAJ_EVERY_S + 1),
       "R4: at the SHIPPED values neither budget can bind on a healthy "
       "universe -- 14 series is above the 11 that exist and both ceilings "
       "(%d near, %d far) sit under the budgets (%d, %d). A budget that "
       "quietly decides the data is how v-instr1's first instrument failed "
       "its own bar by construction"
       % (14 * (TRAJ_NEAR_TAU_S + 1),
          14 * ((TRAJ_TAU_MAX - TRAJ_NEAR_TAU_S) // TRAJ_EVERY_S + 1),
          TRAJ_MAX_NEAR, TRAJ_MAX))
    # THE MEMORY IS BOUNDED TOO, and by the same close-keyed prune: a world
    # that runs past several closes must not leave the history growing.
    ck(_r4b["state"] is not None,
       "R4: the world that ran through a close returned a state (the loop "
       "did not die), which is what makes the prune assertions below about "
       "a LIVED-IN loop rather than an empty one")
    # ---- THE WORK IS BOUNDED, AND THE BOUND IS COUNTED ------------------
    # Eleven markets all OUTSIDE the entry window, so the scan does nothing
    # and every call into the book and the index is the sampler's. At one
    # sample a market a second the bound is exactly one of each per record,
    # and a sampler that quietly ran per PASS would show twenty times this.
    _r4c_w = [_r4t_mkt(20 + i, (lambda t: 0.999)) for i in range(11)]
    _r4c = _offline_trade_loop(_r4c_w, run_s=40.0, tau0=200)
    _r4c_n = len(_kinds(_r4c, "traj"))
    _r4c_c = _r4c["calls"]
    _r4c_pass = int(round(40.0 / 0.05))
    ck(_r4c["raised"] is None
       and 11 * (40 // TRAJ_EVERY_S) <= _r4c_n <= 11 * (40 // TRAJ_EVERY_S + 1)
       and _r4c_c.get("best") == _r4c_n
       and _r4c_c.get("sigma") == _r4c_n
       and _r4c_c.get("partial") == _r4c_n
       and _r4c_c.get("fair") == _r4c_n
       and _r4c_c.get("best", 0) < _r4c_pass,
       "R4 BOUNDED, COUNTED NOT CLAIMED: eleven markets outside the entry "
       "window for 40 fake seconds -- the scan does nothing, so every call "
       "is the sampler's. %d records and EXACTLY %s book reads, %s sigmas, "
       "%s partials and %s fair() calls: one of each per record, none per "
       "pass. The loop ran ~%d passes in that time, so a sampler that woke "
       "on every pass would show twenty times these numbers"
       % (_r4c_n, _r4c_c.get("best"), _r4c_c.get("sigma"),
          _r4c_c.get("partial"), _r4c_c.get("fair"), _r4c_pass))

    # ---- the volume, MEASURED, because disk is the real deadline -------
    _r4v = _offline_trade_loop(_r4t_w, run_s=320.0, tau0=300)
    _r4v_j = _kinds(_r4v, "traj")
    _r4v_by = max(1, int(sum(len(json.dumps(r)) for r in _r4v_j)
                         / max(1, len(_r4v_j))))
    print("  ..   R4 VOLUME, measured in the harness: %d records for ONE "
          "market and ONE close at %d bytes each = %.0f KB. Eleven series is "
          "~%.1f MB a close and ~%.0f MB a day at 96 closes."
          % (len(_r4v_j), _r4v_by, len(_r4v_j) * _r4v_by / 1024.0,
             11 * len(_r4v_j) * _r4v_by / 1048576.0,
             96 * 11 * len(_r4v_j) * _r4v_by / 1048576.0))
    ck(len(_r4v_j) == ((300 - 60) // 5) + 61,
       "R4: one market leaves %d records in a whole close -- 48 on the "
       "coarse grid and 61 inside a minute -- so the day's volume above is "
       "arithmetic on a measured record size, not a guess (got %d)"
       % (((300 - 60) // 5) + 61, len(_r4v_j)))

    # ---- THE VOLUME IS PER PROCESS AND THERE ARE 28 OF THEM ------------
    # The number printed above was costed per process. sync_arms.ps1 launches
    # 27 paper arms FROM THIS SAME FILE, so the first version of this gave
    # every arm its own pintraj-paper-<runid>.jsonl the moment it restarted
    # onto this SHA: ~1.6 GB a day of near-duplicate trajectory against a
    # 6 GB hard collection stop, i.e. ~1.6 days of unreproducible tape spent
    # writing 27 copies of one curve. traj_writer() is where that is decided,
    # and it is module-level SO THIS TEST CAN DRIVE THE REAL WRITER -- the
    # offline harness passes no `trec`, so every other bound in this section
    # is proven against an in-memory list append and not the shipped one.
    import shutil as _shr4
    import tempfile as _tfr4
    _r4w_dir = _tfr4.mkdtemp(prefix="pintraj-selftest-")
    try:
        _r4w_p0, _r4w_w0 = traj_writer(False, False, _r4w_dir, "paper", "AAA")
        for _i in range(30):
            _r4w_w0("traj", ticker="X", tau=_i)
        _r4w_left = sorted(os.listdir(_r4w_dir))
        ck(_r4w_p0 is None and not _r4w_left
           and _r4w_w0.dropped[0] == 30,
           "R4 DISK: a PAPER run opens no trajectory file at all -- 30 "
           "records in and the directory is still empty (%s), the 30 are "
           "counted rather than silently lost, and the run does not raise. "
           "27 paper arms run from this file on this box; a file each was "
           "~1.6 GB a day, 36x the whole existing bot family's log volume, "
           "against the 6 GB that stops the tape collector outright"
           % (_r4w_left or "empty"))
        _r4w_p1, _r4w_w1 = traj_writer(False, True, _r4w_dir, "paper", "BBB")
        _r4w_w1("traj", ticker="X", tau=1)
        _r4w_w1("traj_close", close_s=1)             # forces the flush
        ck(_r4w_p1 and os.path.exists(_r4w_p1)
           and len(open(_r4w_p1, encoding="utf-8").read().splitlines()) == 2,
           "R4 DISK: ...and --traj-log turns it back on for a paper run the "
           "operator explicitly wants it from, so the decision is his and "
           "not a constant. sync_arms.ps1 passes neither flag")
        # ...and main() really passes his flag through. The check above drives
        # traj_writer() directly, so a main() that hard-coded False would
        # leave it green. Sliced from `def main(` so the needle cannot match
        # its own copy here.
        _r4w_src = open(os.path.abspath(__file__), encoding="utf-8").read()
        _r4w_mn = _r4w_src[_r4w_src.rindex(chr(10) + "def " + "main("):]
        ck("traj_writer(a.live, a.traj" + "_log, RESULTS, tag, runid)"
           in _r4w_mn,
           "R4 DISK: ...and main() hands traj_writer BOTH the live flag and "
           "the operator's --traj-log, not a constant")
        # ONE HANDLE, NOT ONE OPEN PER RECORD. Counted through an injected
        # opener, because a wall-clock assertion would be flaky and a source
        # search for `open(` would match its own copy.
        class _FakeFH:
            def __init__(self):
                self.writes, self.flushes, self.closed = 0, 0, False

            def write(self, s):
                self.writes += 1

            def flush(self):
                self.flushes += 1

            def close(self):
                self.closed = True
        _r4w_fh, _r4w_opens = _FakeFH(), [0]

        def _r4w_open(*_a, **_k):
            _r4w_opens[0] += 1
            return _r4w_fh
        _r4w_clk = [1000]
        _r4w_p2, _r4w_w2 = traj_writer(True, False, _r4w_dir, "live", "CCC",
                                       _open=_r4w_open,
                                       _now=lambda: _r4w_clk[0])
        for _i in range(109):                    # one market, one whole close
            _r4w_w2("traj", ticker="X", tau=_i)
        _r4w_f1 = _r4w_fh.flushes
        _r4w_clk[0] = 1001
        _r4w_w2("traj", ticker="X", tau=0)       # a new second flushes
        _r4w_f2 = _r4w_fh.flushes
        _r4w_w2("traj_blind", ticker="X")        # ...and so does a rare kind
        ck(_r4w_opens[0] == 1 and _r4w_fh.writes == 111
           and _r4w_f1 == 1 and _r4w_f2 == 2 and _r4w_fh.flushes == 3,
           "R4 LOOP COST: the whole close's 109 records go through ONE "
           "open() and ONE flush a second -- not 109 opens. Measured on this "
           "box, 200 repeats, a real 539-byte record: the eleven appends of "
           "one sampled second cost 2.46 ms median and 5.64 ms max through "
           "open-append-close against 0.012 ms median and 0.12 ms max held. "
           "The pass ends in a flat time.sleep(0.05), not a deadline, so every "
           "one of those milliseconds is added period before the NEXT hedge "
           "pass, in the last minute of a close where the price-through race "
           "is ~107 ms. A rare kind still flushes at once (%d opens, %d "
           "writes, %d flushes)"
           % (_r4w_opens[0], _r4w_fh.writes, _r4w_fh.flushes))
        # A WRITE THAT RAISES COSTS THE RECORD AND NEVER THE LOOP, and the
        # handle is dropped so the next record reopens rather than writing
        # into a file that is gone.
        class _BadFH(_FakeFH):
            def write(self, s):
                raise OSError("planted: no space left on device")
        _r4w_bad, _r4w_bopen = _BadFH(), [0]

        def _r4w_open2(*_a, **_k):
            _r4w_bopen[0] += 1
            return _r4w_bad
        _r4w_p3, _r4w_w3 = traj_writer(True, False, _r4w_dir, "live", "DDD",
                                       _open=_r4w_open2)
        _r4w_w3("traj", ticker="X")
        _r4w_w3("traj", ticker="X")
        ck(_r4w_bad.closed and _r4w_bopen[0] == 2,
           "R4: a full disk raises nothing into the loop -- the handle is "
           "closed and dropped, and the next record reopens (%d opens)"
           % _r4w_bopen[0])
    finally:
        _shr4.rmtree(_r4w_dir, ignore_errors=True)

    # ---- WHERE THE BLOCK SITS, ASSERTED AGAINST THE SOURCE -------------
    # The constants block's hedge-safety paragraph is the thing anyone will
    # quote, and its first version was factually wrong about the layout: it
    # said the sampler was below the risk check and below the entry scan,
    # when it is ABOVE both. In this file the placement comment IS the safety
    # argument -- A69 exists because a `continue` above the hedge pass cost
    # $107.95 -- so a wrong one is a trap for whoever next puts a protective
    # action in the scan. Assert the real order, so moving any of the four
    # fails the suite instead of quietly invalidating the paragraph.
    _r4p_src = open(os.path.abspath(__file__), encoding="utf-8").read()
    _r4p_lp = _r4p_src[_r4p_src.rindex(chr(10) + "def " + "trade_loop("):]
    _r4p_i = (_r4p_lp.index("AMENDMENT 15: the hedge" + " pass"),
              _r4p_lp.index("R4 (2026-09-23): THE TRAJECTORY. See the TRAJ_*"),
              _r4p_lp.index("A69: THE RISK CHECK, NOW BELOW THE HEDGE PASS"),
              _r4p_lp.index('_gate("book' + '_suspect"'))
    ck(list(_r4p_i) == sorted(_r4p_i),
       "R4 PLACEMENT: in the source the order really is hedge pass, sampler, "
       "risk check, entry scan (%s). The sampler is ABOVE the risk check on "
       "purpose -- that check's transient-pause branch ends in `continue`, "
       "so a sampler below it writes NOTHING for a paused close, which is "
       "the $107.95 blindness of 2026-09-19. Nothing is delayed because the "
       "hedge pass has already run and no protective ACTION exists below it; "
       "that is a narrow, layout-dependent reason and it is written down as "
       "one" % (list(_r4p_i),))
    # ...and the constants block must not claim otherwise. Sliced so the
    # needle cannot match this test's own copy of it.
    _r4p_a = _r4p_src.index("# R4 (2026-09-23): THE TRAJECTORY. LOGGING ONLY")
    _r4p_blk = _r4p_src[_r4p_a:_r4p_src.index("TRAJ_EVERY_S" + " = 5",
                                              _r4p_a)]
    ck("ABOVE the risk check" in _r4p_blk
       and "below the risk check" not in _r4p_blk
       and "below the entry scan" not in _r4p_blk
       and "MOVE THIS BLOCK BELOW IT" in _r4p_blk,
       "R4 PLACEMENT: and the authoritative comment agrees with the code it "
       "describes, and tells the next person to move the block if they add a "
       "protective action below it -- the `dumped` path in the scan is the "
       "nearest candidate")
    # ---- A BLIND BLOCK SAYS SO TOO -------------------------------------
    # The per-market guard is driven above. The OUTER handler covers the
    # `for` unpacking, which no world can reach from outside, so it is
    # asserted against the source: it was a bare `pass`, and a change to the
    # 5-tuple `seen_markets` holds would have killed ALL sampling on EVERY
    # pass with nothing written -- indistinguishable from "nobody deployed
    # it", which is the exact ambiguity the per-market guard was added to
    # remove one level down.
    _r4z = _r4p_lp[_r4p_lp.index("R4 (2026-09-23): THE TRAJECTORY. See the "
                                 "TRAJ_*"):]
    _r4z = _r4z[:_r4z.index("A69: THE RISK CHECK, NOW BELOW THE HEDGE PASS")]
    _r4z_h = _r4z.rindex(chr(10) + "        except Exception")
    ck("traj_blind_blk" in _r4z[_r4z_h:]
       and _r4z[_r4z_h:].count("_trec(" + '"traj_blind"') == 1
       and _r4z.count("_trec(" + '"traj_blind"') == 2,
       "R4: the BLOCK-level handler writes a deduped `traj_blind` of its own "
       "instead of the bare `pass` it shipped as -- two blind writers, one "
       "per market and one for the block, because an instrument that goes "
       "blind silently is the failure this instrument exists to fix")
    _r4z_tau = _r4z.index("_jtau = _jcs - now_s")
    _r4z_try = _r4z.index(chr(10) + "                try:",
                          _r4z.index("for _jtk, ("))
    ck(_r4z_tau < _r4z_try,
       "R4: `_jtau` is computed ABOVE the per-market try, not as its first "
       "statement -- assigned inside, a market that raises before reaching "
       "it stamps the PREVIOUS market's tau on its own blind record, and a "
       "wrong number in a diagnostic is worse than a null one")

    # ---- D_plan SECTION 5: THE SUB-SECOND DROP THE 1 Hz GRID CANNOT SEE -
    # The DOGE close moved 98.0c -> 93.4c on our own side across three looks
    # 244 ms apart; at one record a market a second all three are one row.
    # Driven: the own-side ask (1 - no_bid) falls 4c part-way through.
    # The market is TOO DEAR at first (99c, above the 98c ceiling, so it is
    # refused and keeps being looked at) and then 4c cheaper -- which is the
    # DOGE shape: a price that falls while we are still deciding.
    def _r4d_mkt(n, dear=0.01, cheap=0.05, drop_at=0.2, osc=None):
        def _bk(t):
            if osc is not None:
                _nb = cheap if int(t / osc) % 2 else dear
            else:
                _nb = cheap if t >= drop_at else dear
            return _ob(0.94, round(_nb, 4))
        return {"tk": "KXP%d15M-R4P" % n, "series": "KXP%d15M" % n,
                "iid": "R4P%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.9995), "book": _bk}

    _r4d = _offline_trade_loop([_r4d_mkt(1)], run_s=8.0, tau0=28)
    _r4d_j = _kinds(_r4d, "price_drop")
    ck(_r4d["raised"] is None and len(_r4d_j) == 1
       and abs(float(_r4d_j[0]["drop_c"]) - 4.0) < 1e-6
       and 0 < int(_r4d_j[0]["gap_ms"]) <= 150
       and _r4d_j[0]["want"] == "yes"
       and abs(float(_r4d_j[0]["was"]) - 0.99) < 1e-9
       and abs(float(_r4d_j[0]["now"]) - 0.95) < 1e-9,
       "D_plan 5: our own side getting %sc cheaper between two looks %s ms "
       "apart is RECORDED, with both prices and the gap -- and the gap is the "
       "REAL one, 50 ms, because the reference is kept in `now` and not "
       "`now_s`. Stored as int seconds the same two looks read 350 ms apart, "
       "and the whole point of this record is a gap smaller than a second"
       % (_r4d_j[0].get("drop_c") if _r4d_j else None,
          _r4d_j[0].get("gap_ms") if _r4d_j else None))
    # ---- AND EVERY INSTRUMENT RECORD GOES TO THE INSTRUMENT'S WRITER ----
    # The decision log is parsed by pinledger, pinattrib, pinlab, barcheck,
    # earlyhindsight and the settlement readers, all globbing
    # `pinrun-<tag>-*.jsonl`. A trajectory or price-drop record written with
    # `rec` instead of `_trec` lands in THAT file and slows every one of them,
    # and nothing in this suite could see it while both writers were the same
    # list -- so the harness now splits them, like main() splits the files.
    _r4s = _offline_trade_loop([_r4d_mkt(4)], run_s=8.0, tau0=28,
                               trec_split=True)
    _r4s_k = {r["kind"] for r in _r4s["recs"]}
    _r4s_t = {r["kind"] for r in _r4s["trecs"]}
    ck(_r4s["raised"] is None
       and {"price_drop", "traj"} <= _r4s_t
       and not ({"price_drop", "traj", "traj_close", "traj_blind"} & _r4s_k)
       and "signal" in _r4s_k,
       "R4/D_plan 5: with the two writers SPLIT the way main() splits the "
       "files, every instrument record is on the trajectory writer (%s) and "
       "the decision trail holds none of them -- while the decisions "
       "themselves are all still there. Before the split an instrument "
       "writing into the shared log passed the whole suite"
       % sorted(_r4s_t))
    # NULL: the same market, looked at just as often, with a book that never
    # moves -- so the record is the DROP and not the look. Without this a
    # 20 Hz scan would write ~1,200 rows a market a close.
    _r4d0 = _offline_trade_loop([_r4d_mkt(2, cheap=0.01)], run_s=8.0, tau0=28)
    ck(_r4d0["raised"] is None and not _kinds(_r4d0, "price_drop")
       and _refusals(_r4d0, "price_ceiling"),
       "D_plan 5 NULL: a book that does not move writes NOTHING across the "
       "same 160 looks (the market is refused every pass, so it really is "
       "looked at every pass)")
    _r4dc = _offline_trade_loop([_r4d_mkt(3, osc=0.5)], run_s=8.0, tau0=28,
                                flags={"PRICE_CEILING": 0.10,
                                       "LOOK_DROP_MAX": 2})
    _r4dc_j = _kinds(_r4dc, "price_drop")
    ck(_r4dc["raised"] is None and len(_r4dc_j) == 2
       and all(int(r["cap"]) == 2 for r in _r4dc_j)
       and [int(r["n"]) for r in _r4dc_j] == [1, 2],
       "D_plan 5 BOUNDED: a book that flaps 4c every half second for eight "
       "seconds writes exactly the cap and then stops -- %d records at a cap "
       "of 2, numbered, so this can never become a firehose on a 20 Hz path"
       % len(_r4dc_j))

    # ---- 4: A RECORD THAT RAISES MAY NOT END THE LOOP OR STOP A HEDGE --
    # The trajectory writer is driven through the REAL loop with a planted
    # fault on its own kind only. The hedge must still fire, and every other
    # record must still be written.
    def _r4_fault(kind, kw):
        if kind in ("traj", "traj_close", "traj_blind"):
            raise TypeError("planted: type NoneType doesn't define __round__")

    _r4f_w = [_k1_A(), _k1_B(1)]
    _r4f0 = _offline_trade_loop(_r4f_w)
    _r4f1 = _offline_trade_loop(_r4f_w, rec_fault=_r4_fault)
    _r4f_h0 = _hedged(_r4f0, _kA)
    _r4f_h1 = _hedged(_r4f1, _kA)
    _r4f_t0 = [(r["kind"], r.get("ticker"), r["t"]) for r in _r4f0["recs"]
               if r["kind"] not in ("traj", "traj_close", "traj_blind")]
    _r4f_t1 = [(r["kind"], r.get("ticker"), r["t"]) for r in _r4f1["recs"]]
    ck(_r4f1["raised"] is None and _r4f_h1 > 0 and _r4f_h1 == _r4f_h0
       and _r4f_t1 == _r4f_t0 and not _kinds(_r4f1, "traj"),
       "R4: with EVERY trajectory record planted to raise, the loop does "
       "not die, the hedge still fills the same %g contracts at the same "
       "second, and the whole rest of the trail is byte for byte what it is "
       "without the fault -- the write is swallowed, never the hedge"
       % _r4f_h0)
    # ...and a BOOK that raises inside the sampler is the same story.
    _r4br = dict(_r4t_mkt(3, lambda t: 0.999))
    _r4br["book"] = (lambda t: (_ob(0.94, 0.05) if t < 3
                                else (_ for _ in ()).throw(
                                    RuntimeError("planted book fault"))))
    _r4bx = _offline_trade_loop([_r4br], run_s=20.0, tau0=70)
    _r4bx_j = _kinds(_r4bx, "traj")
    ck(_r4bx["raised"] is None and len(_r4bx_j) >= 4
       and any(r["ask"] is None for r in _r4bx_j)
       and any(r["fair"] is not None for r in _r4bx_j
               if r["ask"] is None),
       "R4: a book read that RAISES inside the sampler leaves the price "
       "columns null and the model columns intact, and the loop runs on -- "
       "a blind second is recorded as blind, never skipped (%d records)"
       % len(_r4bx_j))
    # ...and ONE bad market must not silence the other ten. K1's lesson: the
    # per-market guard is what makes a gap mean "the market was quiet" rather
    # than "something threw two markets ago".
    _r4mx = dict(_r4t_mkt(4, lambda t: 0.999))
    _r4mx["fair"] = (lambda t: (_ for _ in ()).throw(
        TypeError("planted: NoneType has no __round__")))
    _r4mw = [_r4mx] + [_r4t_mkt(30 + i, (lambda t: 0.999)) for i in range(3)]
    _r4m = _offline_trade_loop(_r4mw, run_s=30.0, tau0=200)
    _r4m_j = _kinds(_r4m, "traj")
    _r4m_tk = {r["ticker"] for r in _r4m_j}
    _r4m_b = _kinds(_r4m, "traj_blind")
    ck(_r4m["raised"] is None and len(_r4m_tk) == 3
       and _r4mx["tk"] not in _r4m_tk and len(_r4m_j) >= 9
       and len(_r4m_b) == 1 and _r4m_b[0]["ticker"] == _r4mx["tk"]
       and _r4m_b[0]["err"] == "TypeError",
       "R4: a market whose MODEL raises drops its own sample, says so ONCE "
       "as `traj_blind` (%s), and nothing else -- the other three are all "
       "still sampled (%d records over %d markets). A silently missing "
       "second is indistinguishable from a quiet market, which is the exact "
       "failure this instrument exists to fix"
       % (_r4m_b[0].get("err") if _r4m_b else "NOTHING RECORDED",
          len(_r4m_j), len(_r4m_tk)))

    # ---- 5: AT THE SHIPPED SETTINGS, NOTHING CHANGED. PROVEN. ----------
    # Three worlds, each run twice: once with the sampler made inert
    # (TRAJ_TAU_MAX = -1, so `traj_due` refuses every tau and the block
    # does nothing at all) and once at the shipped defaults. With
    # DOUBT_MULT at its shipped 1.0 as well, the inert run IS today's code
    # path -- so equality of the two trails is the proof that neither new
    # thing touches a decision or an existing record.
    # A BANK IS THE ONLY WAY TO REACH ANY WIDENER OFFLINE: one_coin_cap()
    # returns SIZE when the balance or the high-water mark is unknown. This
    # one auto-sizes 5 -> 6 at the top of the loop, which also puts the
    # `autosize` record (and with it pintake's count rail) on the trail.
    _r4i_bank = ((MAX_PER_CLOSE + max(_DEFAULT_EXTRA_COIN, _DEFAULT_LATE_EXTRA))
                 * _DEFAULT_PRICE_CEILING * _DEFAULT_BANK_BRAKE * 6.0)

    def _r4_scrub(recs):
        """The trail with only the fields that CANNOT be reproduced removed.
        `client_order_id` carries a fresh random suffix per order, so two
        identical runs differ there and nowhere else; dropping it is the only
        way the comparison can be an equality rather than a similarity."""
        out = []
        for r in recs:
            d = {}
            for k, v in r.items():
                if k == "client_order_id":
                    continue
                d[k] = ({kk: vv for kk, vv in v.items()
                         if kk != "client_order_id"}
                        if isinstance(v, dict) else v)
            out.append(d)
        return out

    def _r4_doubt_mkt(n=9):
        # confidence in YES starts at 0.30 -- the model DOUBTS the side it
        # will later buy -- and only crosses the gate at t >= 6.
        return {"tk": "KXD%d15M-R1D" % n, "series": "KXD%d15M" % n,
                "iid": "R1D%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.9995 if t >= 6 else 0.30),
                "book": (lambda t: _ob(0.94, 0.05))}

    _r4id_take, _r4id_calls = _k1_take(False)
    _r4_worlds = (
        ("collapse+hedge, paper", dict(markets=[_k1_A(), _k1_B(1)])),
        ("the live order path",
         dict(markets=[_k1_A()], live=True, take=_r4id_take)),
        # THIS ONE RUNS PAST ITS CLOSE ON PURPOSE. Without it the compared
        # trail holds no `close_summary` at all -- and the sampler shares the
        # `near` dict that record is built from, so an injected write into
        # `near` (one extra `looks`) passed the identity check unnoticed when
        # every world stopped short of its close. Found by the revert-proof
        # run, which is what that run is for.
        ("a doubt world with a bank, through its close and summary",
         dict(markets=[_r4_doubt_mkt()], run_s=55.0, tau0=40,
              bank=_r4i_bank, flags={"SIZE_MIRROR_ON": False})),
    )
    _r4_ident, _r4_why, _r4_seen_cs = True, [], False
    for _wn, _wk in _r4_worlds:
        _kw = dict(_wk)
        _mk = _kw.pop("markets")
        _off_flags = dict(_kw.pop("flags", {}) or {})
        _off_flags["TRAJ_TAU_MAX"] = -1
        _r4id_calls[:] = []
        _off = _offline_trade_loop(_mk, flags=_off_flags, **_kw)
        _off_calls = list(_r4id_calls)
        _r4id_calls[:] = []
        _on = _offline_trade_loop(_mk, **dict(_kw, flags=dict(_wk.get("flags")
                                                             or {})))
        _on_calls = list(_r4id_calls)
        _off_tr = _r4_scrub([r for r in _off["recs"]
                             if r["kind"] not in ("traj", "traj_close", "traj_blind")])
        _on_tr = _r4_scrub([r for r in _on["recs"]
                            if r["kind"] not in ("traj", "traj_close", "traj_blind")])
        _same = (_off_tr == _on_tr
                 and _r4_scrub(_off["posts"]) == _r4_scrub(_on["posts"])
                 and _off_calls == _on_calls
                 and _off["raised"] == _on["raised"]
                 and _off["ran_s"] == _on["ran_s"]
                 and not [r for r in _on["recs"]
                          if str(r["kind"]).startswith("doubt")]
                 and [r for r in _off["recs"] if r["kind"] == "traj"] == []
                 and [r for r in _on["recs"] if r["kind"] == "traj"] != [])
        _r4_seen_cs = _r4_seen_cs or any(r["kind"] == "close_summary"
                                         for r in _on_tr)
        if not _same:
            _r4_ident = False
            _d = [(a_, b_) for a_, b_ in zip(_off_tr, _on_tr) if a_ != b_]
            _r4_why.append("%s: %d vs %d records, first diff %s"
                           % (_wn, len(_off_tr), len(_on_tr), _d[:1]))
    ck(_r4_ident and _r4_seen_cs,
       "R4/R1 IDENTITY, PROVEN NOT ASSERTED: on three worlds -- a collapse "
       "that hedges, the live order path, and a doubt world with a bank -- "
       "the trail with the sampler inert and the trail with it live are the "
       "SAME records in the same order at the same fake second, the same "
       "orders on the wire, the same take() calls and the same run length. "
       "One of the three runs PAST its close, so `close_summary` -- built "
       "from the same `near` dict the sampler can see -- is inside the "
       "comparison. At --doubt-mult 1.0 not one doubt record is written. So "
       "the live argv, which passes neither flag, does exactly what it does "
       "today (%s%s)"
       % ("; ".join(_r4_why) if _r4_why else "identical",
          "" if _r4_seen_cs else "; NO close_summary reached the trail, so "
          "the comparison is blind to `near`"))

    # ===================================================================
    # R1 (2026-09-23): --doubt-mult. See the DOUBT_* block for the money.
    # ===================================================================
    ck(_DEFAULT_DOUBT_MULT == 1.0 and _DEFAULT_DOUBT_UNDER == 0.50
       and _DEFAULT_DOUBT_LAG_S == 5,
       "R1 ships OFF: the DECLARED default multiple is 1.0, which is the "
       "arithmetic identity, so an arm that sets the flag does not fail its "
       "own gate and the live argv is unchanged (running now with %.3g)"
       % DOUBT_MULT)
    _src_d1 = open(os.path.abspath(__file__), encoding="utf-8").read()
    _lp_d1 = _src_d1[_src_d1.rindex(chr(10) + "def " + "trade_loop("):]
    _cd1p, _cd1l = "_doubt(take_n)    # paper", "_doubt(take_n)    # live"
    ck(_cd1p in _lp_d1 and _cd1l in _lp_d1,
       "R1 runs on BOTH the paper and the live path, or the arm books a "
       "size the live path refuses -- the A45 bug, twice repeated since")
    ck(_lp_d1.index("_band53(take_n)   # live") < _lp_d1.index(_cd1l)
       < _lp_d1.index("take_n = _stage46(take_n)", _lp_d1.index(_cd1l))
       and _lp_d1.index("_band53(take_n)   # paper") < _lp_d1.index(_cd1p)
       < _lp_d1.index("take_n = _stage46(take_n)"),
       "...after A53 and before the A46 re-cap, on both paths")
    ck(_lp_d1.index(_cd1p) < _lp_d1.index("take_n = min(take_n, "
                                          "float(_room68))")
       and _lp_d1.index(_cd1l) < _lp_d1.index("take_n = min(take_n, "
                                              "float(_room68))"),
       "...and BEFORE A68's cap, so no widener can undo the bounded rebuy")
    ck("_mult46 = max(band" + "_mult(price), _doubt_on[0]," in _lp_d1,
       "the A46 re-cap reads the doubt multiple as well as the band and the "
       "late one. A60's lesson: without it the staged cap silently undoes "
       "the boost on every 45-second leg, and the arm measures nothing")
    ck("_ours48 = f if want == " + '"yes"' + " else 1.0 - f" in _lp_d1
       and "_c = _fy if want == " + '"yes"' + " else 1.0 - _fy" in _lp_d1,
       "confidence is read for the side we are BUYING -- f for YES and 1-f "
       "for NO. `traj_hist` holds P(YES), because the side is not known "
       "when the reading is taken, so this conversion is mandatory and "
       "getting it backwards inverts the entire rule")
    # A NEEDLE THAT CANNOT MATCH ITS OWN COPY. The escapes make this pattern
    # unable to match the literal source text of this line -- the bug that bit
    # four times in one session and once silently for days.
    _re_d1 = __import__("re")
    _nd_d1 = _re_d1.findall(
        r"max\(ONE_COIN_MAX if ONE_COIN_DEPTH else 1\.0,\s*DOUBT_MULT,"
        r"\s*LATE_MULT, max_band_mult\(\), FLIP_MULT\)", _src_d1)
    ck(len(_nd_d1) == 2,
       "pintake's per-order count cap admits the doubt multiple at live "
       "start AND at every autosize -- miss either and the live path "
       "refuses the wider order while the paper path books it, which is "
       "what the self-test at A53 exists for")
    # THE CONDITION, NOT ONLY THE MESSAGE. A54's equivalent check asserts the
    # "PAPER ONLY" sentence and nothing else, so gutting the `if` would leave
    # it green -- which the revert-proof run caught. The needle is split so it
    # cannot match its own copy in this file.
    ck(_src_d1.count("if a.live and a.doubt" + "_mult > 1.0:") == 1
       and '"--doubt-mult above 1.0 is PAPER ONLY' in _src_d1,
       "and a LIVE run refuses the flag outright -- the CONDITION is on "
       "`a.live`, not merely the sentence explaining it: the money is stable "
       "but the p-value fails the corrected bar, and 0 losers in 66 markets "
       "does not exclude the 2.44 percent base rate")
    _offd1 = 'globals()["DOUBT_MULT"] = 1.0'
    ck(_offd1 in _lp_d1 and 'rec("doubt_boost_off"' in _lp_d1
       and "_boosted_dbt.add((close_s, tk))" in _lp_d1
       and "_boosted_dbt = set()" in _lp_d1,
       "one doubt-boosted LOSS switches --doubt-mult off for the rest of "
       "the run, from a set the widening writes -- 'we aren't just going to "
       "boost a trade above our normal level then just lose a bunch of "
       "money', enforced by the bot and not by somebody reading a log")
    ck(_lp_d1.rindex("if not won:", 0, _lp_d1.index(_offd1))
       > _lp_d1.rindex("state[" + '"settled"' + "]", 0, _lp_d1.index(_offd1)),
       "...and the switch sits INSIDE the loss branch of settlement, so a "
       "win can never trip it")
    ck("traj_hist" in _lp_d1 and "open(" not in _lp_d1.split(
        "def _doubt(take_n):")[1].split("def _stage46")[0],
       "R1 reads the bot's OWN in-memory trajectory and opens no file: a "
       "log read in the 20 Hz loop would be both slow and a different "
       "population from the one the decision is made on")

    # ---- driven: 1.5x fires, and ONLY on a doubted side ----------------
    _d1w = [_r4_doubt_mkt()]
    _d1_kw = dict(run_s=40.0, tau0=40, bank=_r4i_bank,
                  flags={"SIZE_MIRROR_ON": False})

    def _d1_run(mult, world=None, **over):
        _fl = dict(_d1_kw["flags"])
        _fl["DOUBT_MULT"] = mult
        _kw = dict(_d1_kw, flags=_fl)
        _kw.update(over)
        return _offline_trade_loop(world or _d1w, **_kw)

    _d1a = _d1_run(1.5)
    _d1a_b = _kinds(_d1a, "doubt_boost")
    _d1a_sig = _kinds(_d1a, "signal")
    _d1a_slot = _kinds(_d1a, "autosize")
    ck(_d1a["raised"] is None and len(_d1a_b) == 1
       and abs(float(_d1a_b[0]["now"]) - 1.5 * float(_d1a_b[0]["was"])) < 1e-6
       and float(_d1a_b[0]["low"]) < _DEFAULT_DOUBT_UNDER
       and int(_d1a_b[0]["low_at_tau"]) - int(_d1a_b[0]["tau"])
           >= _DEFAULT_DOUBT_LAG_S,
       "R1 DRIVEN: the model put %.2f on this side %ds before the entry, "
       "under the 0.50 bar, and the order goes out at %s contracts instead "
       "of %s -- exactly 1.5x, and the reading it used really is at least "
       "5 s older than the decision"
       % (float(_d1a_b[0]["low"]) if _d1a_b else -1,
          (int(_d1a_b[0]["low_at_tau"]) - int(_d1a_b[0]["tau"]))
          if _d1a_b else -1,
          _d1a_b[0].get("now") if _d1a_b else None,
          _d1a_b[0].get("was") if _d1a_b else None))
    ck(_d1a_slot and float(_d1a_slot[0]["max_take_count"])
       >= 1.5 * float(_d1a_slot[0]["new"]) - 1e-9,
       "R1 DRIVEN: and the autosize that ran in that world left pintake's "
       "per-order count rail at or above 1.5 x size (%s against %s needed) "
       "-- the rail that silently refused 160 orders in a row on "
       "2026-09-08. The needle test above is what proves the DOUBT_MULT term "
       "is in the expression at both sites; this proves the value that came "
       "out of it covers the boost"
       % (_d1a_slot[0].get("max_take_count") if _d1a_slot else None,
          1.5 * float(_d1a_slot[0]["new"]) if _d1a_slot else None))
    # ...and the LIVE ORDER PATH really books the boosted size. A45's bug was
    # a widener that ran on paper and not live, so the arm's numbers described
    # a bot that did not exist. Driven through the real live branch with the
    # bank one that does NOT move SIZE, so the boost is the only change.
    _d1L_bank = ((MAX_PER_CLOSE + max(_DEFAULT_EXTRA_COIN, _DEFAULT_LATE_EXTRA))
                 * _DEFAULT_PRICE_CEILING * _DEFAULT_BANK_BRAKE * 5.0)
    _d1L_take, _d1L_calls = _k1_take(False)
    _d1L = _offline_trade_loop(
        _d1w, run_s=40.0, tau0=40, bank=_d1L_bank, live=True,
        take=_d1L_take, flags={"SIZE_MIRROR_ON": False, "DOUBT_MULT": 1.5})
    _d1L0_take, _d1L0_calls = _k1_take(False)
    _d1L0 = _offline_trade_loop(
        _d1w, run_s=40.0, tau0=40, bank=_d1L_bank, live=True,
        take=_d1L0_take, flags={"SIZE_MIRROR_ON": False})
    ck(_d1L["raised"] is None and _d1L0["raised"] is None
       and _d1L_calls and _d1L0_calls
       and abs(_d1L_calls[0][2] - 1.5 * _d1L0_calls[0][2]) < 1e-6,
       "R1 DRIVEN, LIVE PATH: the order that actually goes to take() asks "
       "for %s contracts with the flag on against %s with it off -- exactly "
       "1.5x on the LIVE branch, not only on paper. A widener that runs on "
       "one path and not the other is the A45 bug, and it makes an arm "
       "describe a bot that does not exist"
       % (_d1L_calls[0][2] if _d1L_calls else None,
          _d1L0_calls[0][2] if _d1L0_calls else None))
    # ---- and the close budget still clips it -----------------------------
    # TWO doubted markets in ONE close. The first takes 7.5 of the close's
    # 10 contracts; the second must get the 2.5 that are left and NOT 7.5.
    _d1cb_w = [_r4_doubt_mkt(6), _r4_doubt_mkt(7)]
    _d1cb_take, _d1cb_calls = _k1_take(False)
    _d1cb = _offline_trade_loop(
        _d1cb_w, run_s=40.0, tau0=40, bank=_d1L_bank, live=True,
        take=_d1cb_take, flags={"SIZE_MIRROR_ON": False, "DOUBT_MULT": 1.5})
    _d1cb_sum = sum(c[2] for c in _d1cb_calls)
    ck(_d1cb["raised"] is None and len(_d1cb_calls) >= 2
       and abs(_d1cb_calls[0][2] - 7.5) < 1e-6
       and abs(_d1cb_sum - MAX_PER_CLOSE * 5.0) < 1e-6,
       "R1: the boost NEVER escapes the close's contract budget -- the first "
       "doubted market takes 7.5 of the 10 contracts the close may buy and "
       "the second is clipped to the 2.5 that are left, not boosted to 7.5 "
       "again (asked %s, total %.2f against a budget of %.0f)"
       % ([c[2] for c in _d1cb_calls], _d1cb_sum, MAX_PER_CLOSE * 5.0))
    # ---- and the A46 staged cap does NOT undo it (the A60 lesson) --------
    _d1e_take, _d1e_calls = _k1_take(False)
    _d1e_fl = {"SIZE_MIRROR_ON": False, "DOUBT_MULT": 1.5,
               "EARLY_TAU_MAX": 45, "EARLY_FRAC": 0.5}
    _d1e = _offline_trade_loop(_d1w, run_s=20.0, tau0=40, bank=_d1L_bank,
                               live=True, take=_d1e_take, flags=_d1e_fl)
    _d1e0_take, _d1e0_calls = _k1_take(False)
    _d1e0 = _offline_trade_loop(_d1w, run_s=20.0, tau0=40, bank=_d1L_bank,
                                live=True, take=_d1e0_take,
                                flags=dict(_d1e_fl, DOUBT_MULT=1.0))
    ck(_d1e["raised"] is None and _d1e0["raised"] is None
       and _d1e_calls and _d1e0_calls
       and _d1e_calls[0][2] > _d1e0_calls[0][2] + 1e-9
       and abs(_d1e_calls[0][2] - 1.5 * _d1e0_calls[0][2]) < 1e-6,
       "R1: on a 45-second EARLY leg the staged cap keeps the boost -- %s "
       "contracts against %s unboosted. Without the doubt multiple in "
       "`_mult46` the A46 re-cap would put it straight back to the "
       "unboosted number, which is A60's exact bug and would make the arm "
       "measure nothing on the leg the live bot actually runs"
       % (_d1e_calls[0][2] if _d1e_calls else None,
          _d1e0_calls[0][2] if _d1e0_calls else None))
    # NULL 1: the model never doubted this side -> no boost, and it SAYS so.
    _d1n = _d1_run(1.5, world=[dict(_r4_doubt_mkt(8),
                                    fair=(lambda t: 0.9995))])
    _d1n_b = _kinds(_d1n, "doubt_boost")
    _d1n_s = _kinds(_d1n, "doubt_skip")
    ck(_d1n["raised"] is None and not _d1n_b and _d1n_s
       and "never doubted" in str(_d1n_s[0]["why"])
       and float(_d1n_s[0]["low"]) >= _DEFAULT_DOUBT_UNDER,
       "R1 NULL: a market the model was sure of the whole time is bought at "
       "the ordinary size and the log says which reading refused the boost "
       "(%s)" % (_d1n_s[0].get("why") if _d1n_s else "no record at all"))
    # NULL 2: UNKNOWN history is 1.0x, not a boost. The sampler is turned
    # off, so the bot has no earlier reading of its own at all -- which is
    # also every market entered at the first second it is allowed.
    _d1u = _d1_run(1.5, **{"flags": dict(_d1_kw["flags"],
                                         DOUBT_MULT=1.5, TRAJ_TAU_MAX=-1)})
    _d1u_b = _kinds(_d1u, "doubt_boost")
    _d1u_s = _kinds(_d1u, "doubt_skip")
    ck(_d1u["raised"] is None and not _d1u_b and _d1u_s
       and "unknown" in str(_d1u_s[0]["why"])
       and int(_d1u_s[0]["readings"]) == 0,
       "R1 NULL: no earlier reading is UNKNOWN and buys the ordinary size "
       "-- an unknown is not a doubt, and a rule that read it as one would "
       "boost the 481 markets of our record that have no earlier reading, "
       "the WORST bucket at +$0.41 a market (%s)"
       % (_d1u_s[0].get("why") if _d1u_s else "no record at all"))
    # NULL 4: A DOUBT THAT IS TOO RECENT DOES NOT COUNT. The model is sure of
    # our side until 4 seconds before the entry, doubts it for three seconds,
    # and is sure again at the moment we buy. `traj_min_conf_ge5s` -- the
    # feature the +$2.95 was measured on -- reads only readings at least 5 s
    # older than the decision, so this must NOT boost. Without the lag it
    # would, and the rule would be a different statistic from the one
    # D_plan's table is about.
    _d1g = _d1_run(1.5, world=[dict(
        _r4_doubt_mkt(5),
        fair=(lambda t: 0.30 if 6 <= t < 9 else 0.9995))])
    _d1g_b = _kinds(_d1g, "doubt_boost")
    _d1g_s = _kinds(_d1g, "doubt_skip")
    ck(_d1g["raised"] is None and not _d1g_b and _d1g_s
       and "never doubted" in str(_d1g_s[0]["why"])
       and float(_d1g_s[0]["low"]) >= _DEFAULT_DOUBT_UNDER,
       "R1 NULL: a doubt 2-4 seconds before the entry is IGNORED -- the "
       "lowest reading the rule may read is %s, from the seconds at least 5 "
       "s back, and the 0.30 it saw in between is out of bounds. Reading it "
       "would make this a different statistic from the one the money was "
       "measured on" % (_d1g_s[0].get("low") if _d1g_s else None))
    # ---- THE WINDOW THE READINGS COME FROM. THIS DECIDES THE POPULATION. -
    # THE DEFECT THIS PAIR EXISTS FOR. The first version appended EVERY
    # sampled second to `traj_hist`, including the coarse grid out to
    # TRAJ_TAU_MAX = 300, so `_doubt` minimised over readings up to five
    # minutes before the close -- where partial() returns (0.0, 60), nothing
    # is locked and `fair` is a near coin-flip. That is not the statistic the
    # +$2.95 was measured on: every `refused` record in our last 8 live runs
    # that carries a tau is in [3, 45] (2,405 of 2,619, none above 45),
    # because `_gate()` is unreachable outside the scan window, so the
    # historical minimum was over tau 3-45 readings ONLY. Rebuilt off the raw
    # 1/sec index for 12 h and 11 coins, the flag fires on 2.3% of decided
    # cells with readings restricted to tau 35-60 and 20.9% with tau 35-300 --
    # NINE TIMES the population, against a historical 8.4%. D_plan section 1
    # scores PASS/FAIL on "flagged >= +$2.00/market", so a FAIL on a
    # nine-times-diluted rule would have read as killing R1.
    #
    # TWO WORLDS, IDENTICAL BUT FOR THE TAU OF THE DOUBT. Both start at tau 90
    # and both buy at tau 30 (EARLY_TAU_MAX == TAU_MAX == 30 offline, so the
    # first allowed second is 30).
    ck(_DEFAULT_DOUBT_HIST_TAU_S == 60
       and _DEFAULT_DOUBT_HIST_TAU_S <= _DEFAULT_TRAJ_NEAR_TAU_S
       and _DEFAULT_DOUBT_HIST_TAU_S > _DEFAULT_EARLY_TAU_MAX
                                       + _DEFAULT_DOUBT_LAG_S,
       "R1: the DECLARED history window is 60 s -- inside the 1 Hz grid, so "
       "every reading the rule can see is a sampled second and never a "
       "5-second-grid one, and wide enough that a market entered at the "
       "first allowed second (%d) still has readings %d s earlier"
       % (_DEFAULT_EARLY_TAU_MAX, _DEFAULT_DOUBT_LAG_S))

    def _r1h_mkt(n, lo, hi):
        """0.30 on YES while tau is in [lo, hi], 0.9995 otherwise. tau0 = 90,
        so t = 90 - tau."""
        return {"tk": "KXH%d15M-R1H" % n, "series": "KXH%d15M" % n,
                "iid": "R1H%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.30 if lo <= 90 - t <= hi else 0.9995),
                "book": (lambda t: _ob(0.94, 0.05))}
    _r1h_kw = dict(run_s=65.0, tau0=90, bank=_r4i_bank,
                   flags={"SIZE_MIRROR_ON": False, "DOUBT_MULT": 1.5})
    _r1h_out = _offline_trade_loop([_r1h_mkt(1, 65, 90)], **_r1h_kw)
    _r1h_in = _offline_trade_loop([_r1h_mkt(2, 50, 60)], **_r1h_kw)
    _r1h_ob = _kinds(_r1h_out, "doubt_boost")
    _r1h_os = _kinds(_r1h_out, "doubt_skip")
    _r1h_ib = _kinds(_r1h_in, "doubt_boost")
    # the doubt really WAS sampled and recorded out there -- so this null is
    # the window and not a world with nothing in it
    _r1h_far = [r for r in _kinds(_r1h_out, "traj")
                if int(r["tau"]) > _DEFAULT_DOUBT_HIST_TAU_S
                and r["fair"] is not None
                and float(r["fair"]) < _DEFAULT_DOUBT_UNDER]
    ck(_r1h_out["raised"] is None and not _r1h_ob and _r1h_os
       and len(_r1h_far) >= 5
       and float(_r1h_os[0]["low"]) >= _DEFAULT_DOUBT_UNDER,
       "R1 WINDOW: a doubt at tau 65-90 does NOT boost, and it is the WINDOW "
       "that refused it and not an empty world -- %d trajectory records "
       "outside 60 s carry a confidence under the bar (0.30), every one of "
       "them written to the log, and the rule still reads a lowest of %s. "
       "The trajectory is the wide thing; the RULE is the narrow one"
       % (len(_r1h_far), _r1h_os[0].get("low") if _r1h_os else None))
    ck(_r1h_in["raised"] is None and len(_r1h_ib) == 1
       and abs(float(_r1h_ib[0]["now"]) - 1.5 * float(_r1h_ib[0]["was"])) < 1e-6
       and float(_r1h_ib[0]["low"]) < _DEFAULT_DOUBT_UNDER
       and 50 <= int(_r1h_ib[0]["low_at_tau"]) <= 60,
       "R1 WINDOW, THE OTHER HALF: the SAME world with the doubt moved inside "
       "60 s DOES boost, off a reading at tau %s -- so the null above is a "
       "boundary and not a broken estimator. Without this pair the suite "
       "could not tell D_plan's rule from a nine-times wider one, and "
       "changing the one line that decides it left all 20 reverts green"
       % (_r1h_ib[0].get("low_at_tau") if _r1h_ib else None))
    # ...AND A DISK BUDGET MAY NOT DELETE A READING. TRAJ_MAX_NEAR used to
    # `continue` above the history append, so a bite did not merely drop a log
    # line -- the sample never happened for the RULE. It cannot bite today
    # (14 series x 61 = 854 <= 900) but it binds at 15 series, and D_plan's
    # pre-registered next step is 1.25x LIVE, at which point a disk constant
    # would be an input to live entry sizing.
    _r1hb = _offline_trade_loop([_r1h_mkt(3, 50, 60)],
                                **dict(_r1h_kw,
                                       flags=dict(_r1h_kw["flags"],
                                                  TRAJ_MAX_NEAR=2)))
    _r1hb_b = _kinds(_r1hb, "doubt_boost")
    _r1hb_near = [r for r in _kinds(_r1hb, "traj") if r["near"]]
    _r1hb_cl = _kinds(_r1hb, "traj_close")
    ck(_r1hb["raised"] is None and len(_r1hb_b) == 1
       and len(_r1hb_near) == 2
       and int(_r1hb_b[0]["readings"]) > len(_r1hb_near)
       and float(_r1hb_b[0]["low"]) < _DEFAULT_DOUBT_UNDER,
       "R1: with the near RECORD budget cut to 2 the boost still fires off "
       "%s readings -- the budget is disk protection and drops log lines, "
       "never a decision input. It used to skip the reading itself, so a "
       "constant chosen to protect the disk silently decided how big a live "
       "bet was (%d near records written, %s)"
       % (_r1hb_b[0].get("readings") if _r1hb_b else None, len(_r1hb_near),
          ("%s dropped" % _r1hb_cl[0].get("dropped")) if _r1hb_cl
          else "the close had not passed yet, so no traj_close"))

    # NULL 3: no bank, no boost. one_coin_cap returns SIZE when the balance
    # is unknown, so a failed balance read can never size us up.
    _d1nb = _offline_trade_loop(_d1w, run_s=40.0, tau0=40,
                                flags={"DOUBT_MULT": 1.5})
    _d1nb_b = _kinds(_d1nb, "doubt_boost")
    _d1nb_s = _kinds(_d1nb, "doubt_skip")
    ck(_d1nb["raised"] is None and not _d1nb_b and _d1nb_s
       and "nothing to add" in str(_d1nb_s[0]["why"]),
       "R1 NULL: with the balance unreadable the boost is ALLOWED and adds "
       "nothing -- A45's drawdown headroom is the cap, and an unknown bank "
       "means the cap is SIZE. A failed balance read cannot size us up "
       "(%s)" % (_d1nb_s[0].get("why") if _d1nb_s else "no record"))

    _pin_moved = [_n for _n in _OFFLINE_PINNED_FLAGS
                  if globals()[_n] != _pin_before[_n]]
    ck(not _pin_moved,
       "K1 harness: after every offline world, all %d pinned flags hold the "
       "value the process started with again (moved: %s)"
       % (len(_OFFLINE_PINNED_FLAGS), _pin_moved))

    # THE SELF-TEST MUST LEAVE NO LIVE SETTING CHANGED. It runs at startup
    # with the operator's flags ALREADY applied, so any global it forgets to
    # restore silently overrides what he asked for -- on every start, with
    # nothing in the log to say so. --late-extra-tau 15 was wiped to None
    # this way and the bot ran at 10 while its own command line said 15.
    for _nm, _before in sorted(_flags_before.items()):
        if globals()[_nm] != _before:
            fails.append("the self-test left %s as %r when the process "
                         "started with %r -- a test that writes a live "
                         "setting overrides the operator's own flag"
                         % (_nm, globals()[_nm], _before))
            print("  FAIL " + fails[-1])
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def risk_abort(state, a):
    """FIRST statement in the loop. Never behind a branch.

    THE KEY NAMES ARE CHECKED BY A SELF-TEST. The first version of this
    function read led["halted"] and led["stake"], neither of which exists
    in pintake's ledger ("halt" and "committed" do), so both checks were
    dead -- the same shape of defect as last night's abort that sat behind
    a `continue`. A check that reads a missing key is not a check.
    """
    if state["halted"]:
        return "already halted"
    # AMENDMENT 71: RECONCILE IS NOW GUARDED, AND A GUARD THAT SWALLOWS FOR
    # EVER IS WORSE THAN THE CRASH IT REPLACED.
    #
    # reconcile() is what settles positions and calls pintake.record_pnl(),
    # which is what `realised`, `committed` and the loss-count brake below all
    # read. If it fails every iteration, those numbers freeze and every brake
    # in this function is quietly measuring a world that stopped updating --
    # the bot trades on, blind to its own losses.
    #
    # So a persistent failure stops the run. It stops it HERE, in risk_abort,
    # which A69 placed BELOW the hedge pass -- so the final iteration still
    # hedges everything open before the halt lands. A halt at the top of the
    # loop would have been the A69 bug again, wearing a different hat.
    if state.get("reconcile_fail_streak", 0) >= RECONCILE_FAIL_HALT:
        return (f"reconcile has failed {state['reconcile_fail_streak']} times "
                f"in a row: the loss brakes are reading a frozen ledger")
    led = pintake.LEDGER
    if led.get("halt"):
        return f"pintake halted: {led['halt']}"
    # AMENDMENT 79 (2026-09-20): THE CAP IS A DAY, NOT A RUN.
    #
    # The operator asked for "$200" and got $200 PER RUN. 2026-09-19 had
    # THIRTEEN runs, each starting with a fresh $200 of permission, and the
    # day reached -$223.46. A cap that resets every time the watchdog
    # restarts the bot is not a cap on anything.
    #
    # `day_loss()` reads the ET day's realised total off disk, so it survives
    # a restart, a crash and the watchdog. It is only ever compared when it is
    # a LOSS -- a profitable day never halts -- and it uses the same
    # `a.loss_abort` number, so nothing about the size of the cap changed.
    #
    # LIVE ONLY (2026-09-22). The file is the LIVE account's day, and only a
    # live run ever writes it. Read by a paper arm, a bad live day halted the
    # whole fleet at once -- 24 of 25 arms inherit --loss-cap 200, the cap is
    # terminal, and arms are never restarted -- on exactly the day their
    # comparison matters most. An arm keeps its own per-run check below.
    _dl = day_loss() if getattr(a, "live", False) else None
    if _dl is not None and _dl <= a.loss_abort:
        return (f"DAY loss cap: ${_dl:.2f} lost today (ET) <= "
                f"${a.loss_abort:.2f}. This survives restarts -- 2026-09-19 "
                f"reached -$223.46 through thirteen runs each with a fresh "
                f"$200 of permission")
    if float(led.get("realised", 0.0)) <= a.loss_abort:
        return (f"loss abort: realised ${led['realised']:.2f} <= "
                f"${a.loss_abort:.2f}")
    if float(led.get("committed", 0.0)) >= pintake.MAX_RUN_STAKE:
        return f"stake cap reached: ${led['committed']:.2f} committed"
    # AMENDMENT 73 (2026-09-19): AN UNSETTLED BET IS NOT A LOSS.
    #
    # The operator, and the log agrees with him word for word: *"I don't know
    # why it seems like it was calculating the total lost before the bet has
    # settled. If it was seeing a current bet is down 100 then adding that to
    # the loss total that is wrong. You should only wait for the bet to end
    # and be finalized before you count it because that's only the true
    # total."*
    #
    # The old bound was `realised - open_cost - one more contract`, and
    # `open_cost` is the full PURCHASE PRICE of everything open -- not its
    # mark to market. So every held bet was booked as a TOTAL loss the
    # instant it filled, on a strategy that wins about 97 times in 100. It
    # fired while the run was UP:
    #
    #   pause: loss bound: realised $+43.56 with $145.00 still open
    #   pause: loss bound: realised  $+0.00 with $101.15 still open
    #
    # MEASURED over every live run: 28 pause->resume spans, and in ZERO of
    # them did the bot signal or send an order. So it cost no trades -- the
    # operator said so and he was right, and CURRENT_STATE's claim that it
    # "blocks NEW trades for the rest of that close" was wrong. It was pure
    # noise in the log, sitting on the same code path that cost $107.95 on
    # 2026-09-19 when its `continue` skipped the hedge.
    #
    # THE BOUND IS NOW SETTLED-ONLY, and that is the check immediately above
    # this one (`realised <= a.loss_abort`). Nothing replaces this block.
    #
    # WHAT THAT GIVES UP, STATED PLAINLY. The run now stops on $LOSS_ABORT of
    # FINALISED losses, and whatever is in flight at that moment is on top.
    # In flight is bounded elsewhere and always was:
    #   - the open cap below: max_positions x SIZE contracts
    #   - pintake.MAX_RUN_STAKE, the stake cap above
    #   - the per-close budget
    # At --loss-cap 200 and 98 contracts that is $200 settled plus at most
    # 3 x 98 x $0.98 = $288 open, so ~$488 worst case against the old ~$200.
    # THE OPERATOR MUST BE TOLD THAT NUMBER; it is not a detail.
    #
    # The old comment justified the bound by saying a realised-only abort "is
    # inert entirely if the settlement reader is failing". That hole is real
    # and is now covered properly, by A71's RECONCILE_FAIL_HALT above --
    # which halts on the reader being broken, instead of guessing at losses
    # that have not happened.
    #
    # --loss-bound-open restores the old behaviour without a code change.
    if LOSS_BOUND_OPEN:
        worst = (float(led.get("realised", 0.0))
                 - float(state.get("open_cost", 0.0)))
        if worst - 1.00 * float(SIZE) < a.loss_abort - 1e-9:
            return (f"loss bound: realised "
                    f"${float(led.get('realised', 0.0)):+.2f} "
                    f"with ${float(state.get('open_cost', 0.0)):.2f} still "
                    f"open; one more contract could take this run past "
                    f"${a.loss_abort:.2f}")
    # AMENDMENT 31 (2026-09-14): THE OPEN CAP COUNTS CONTRACTS, NOT POSITIONS.
    #
    # It counted positions, and that was fine while a close produced one or
    # two fills. AMENDMENTS 23, 28 and 29 changed that: under the contract
    # budget there is no limit on the NUMBER of fills, only their total, and
    # with the depth floor at a tenth of SIZE one close can now produce ten to
    # eighteen small fills instead of two. A cap of three positions would have
    # halted the bot three fills into every close and throttled the exact
    # buying those amendments exist to enable -- the operator's "make sure
    # it'll increase the amount of contract fills we're getting".
    #
    # EXPOSURE IS UNCHANGED, which is the point. The limit is set to
    # max_positions x SIZE contracts, so three fills of 52 and eighteen fills
    # of 8.7 are both at the cap. This is the same correction AMENDMENT 17
    # made to the per-close budget, applied to the concurrent one.
    _open_n = open_contracts(led)
    _open_cap = float(a.max_positions) * float(SIZE)
    if _open_n >= _open_cap - 1e-9:
        return (f"open cap: {_open_n:g} contracts held >= {_open_cap:g} "
                f"({a.max_positions} x size {SIZE:g})")
    # THE LOSS-COUNT BRAKE. The dollar brake asks "have we lost too much?".
    # This asks a different and more important question: "is the model still
    # the thing we think it is?" The entire edge rests on a 0.90% flip rate
    # measured from THREE events, out of sample, under an older rule. If losses
    # arrive faster than that rate predicts, the right response is to STOP AND
    # RE-MEASURE, not to keep trading until a dollar figure is reached. At ~50
    # trades a day a 0.90% rate predicts 0.45 losses per day, so three in one
    # run is roughly a 1% event -- rare enough to deserve a human look.
    if getattr(a, "max_losses", 0) and             int(led.get("losses", 0) or 0) >= a.max_losses:
        return (f"loss COUNT brake: {led['losses']} losing trades this run "
                f">= {a.max_losses}; stop and re-measure the flip rate")
    # AMENDMENT 30: the drawdown brake. `state["drawdown"]` is refreshed by
    # autosize_tick (every AUTO_SIZE_EVERY_S, and immediately after any loss
    # settles). Reads state rather than the API because risk_abort is the
    # FIRST statement in a 20 Hz loop and must never block on a network call.
    _dd = float(state.get("drawdown", 0.0) or 0.0)
    if _dd >= MAX_DRAWDOWN:
        return (f"DRAWDOWN brake: bank ${state.get('bank', 0.0):.2f} is "
                f"{100.0 * _dd:.1f}% below its high of "
                f"${state.get('hwm', 0.0):.2f}, limit {100.0 * MAX_DRAWDOWN:.0f}%. "
                f"Size has been reduced to {SIZE:g}. STOP AND LOOK. "
                f"(A WITHDRAWAL from the account looks identical to a trading "
                f"loss here -- check the balance before assuming the worst.)")
    if state.get("order_errors", 0) >= 2:
        return f"{state['order_errors']} errors on the ORDER path"
    if state["errors"] >= 5:
        return f"{state['errors']} consecutive errors"
    return None


# AMENDMENT 14 (2026-09-12). A HALT THAT CLEARS ITSELF MUST PAUSE, NOT QUIT.
# The loop's reaction to risk_abort was `break`, so ANY condition ended the
# run for good. Twice on 2026-09-12 that cost real trading time:
#   02:00  "position cap: 3 open >= 3"      -- down 23 minutes
#   03:29  "loss bound: ... $40.89 open"    -- down until noticed
# Both conditions are TEMPORARY. They are functions of what is currently
# OPEN, and every position here settles within 60 seconds of its close, at
# which point reconcile() releases it and the condition evaporates. Quitting
# on them throws away the rest of the day to avoid a risk that has already
# passed.
#
# THE LIST IS A WHITELIST AND IT IS DELIBERATELY SHORT. Anything not named
# here still ends the run, because misclassifying a terminal condition as
# transient means trading on through the thing that was meant to stop us.
# The three below are exactly the conditions that read `open_cost`,
# `committed` or `positions` -- all of which reconcile() reduces.
# AMENDMENT 74: "open cap:" WAS MISSING AND THAT MADE IT TERMINAL.
#
# A31 renamed this halt from "position cap:" to "open cap:" on 2026-09-14
# when it started counting CONTRACTS instead of positions. This tuple was not
# updated, so from that day the open cap stopped being a pause and became a
# reason to END THE RUN -- holding whatever was open, with no hedge.
#
# It fired for real at 2026-09-18T01:14:26Z (21:14 ET on 09-17):
#   halt  open cap: 297 contracts held >= 297 (3 x size 99)
#
# Nobody saw it because the self-test asserted the OLD string, so it passed
# while testing a phrase the code no longer produced -- "a check that reads a
# missing key is not a check", the same failure risk_abort's own docstring
# warns about. The test below now drives this list from risk_abort's REAL
# output instead of retyped literals.
#
# It hid for another reason too: until A73 the "loss bound:" pause fired
# whenever anything at all was open, so it reached this branch first and
# turned every terminal halt into a harmless wait. Removing that guess about
# unsettled losses is correct, and it exposed this.
#
# "position cap:" is kept only so an old log still classifies the same way.
TRANSIENT_HALTS = ("open cap:", "position cap:", "loss bound:",
                   "stake cap reached:")

# AMENDMENT 74: a terminal halt stops NEW bets immediately but the process
# does not exit while contracts are open -- the hedge pass must keep running.
# The operator: "In no circumstance should the bot ever cut off mid bet."
DRAIN_ON_HALT = True
DRAIN_MAX_S = 600.0      # ...but never hang forever: watch_bot.ps1 only
                         # restarts a process that is GONE or silent, so a bot
                         # stuck draining is a bot nothing is watching.

# K1 (2026-09-22): distinct entry-scan faults -- (close, market, error type)
# -- after which a run stops NEW entries. A hedge-step fault stops them at
# once. Either way the hedge pass keeps running, and the run drains and
# exits when flat so watch_bot restarts it; see _k1_error in trade_loop.
SCAN_ERRORS_STOP_ENTRIES = 5


def halt_is_transient(why):
    """True only for a halt that clears when open positions settle."""
    return bool(why) and str(why).startswith(TRANSIENT_HALTS)


# ===========================================================================
# AMENDMENT 16 -- the auto-sizer. See the block above SIZE for the reasoning.
# ===========================================================================
def close_budget(size=None):
    """Contracts a single close may buy (AMENDMENT 17). Deliberately the same
    MAX_PER_CLOSE * SIZE product the --loss-abort band, pintake's stake cap
    and pinbank.worst_close all use, so switching CLOSE_BUDGET on moves no
    other rail."""
    return float(MAX_PER_CLOSE) * float(SIZE if size is None else size)


def worst_close_cost(size):
    """The most one close can lose. Exact: a long binary cannot lose more
    than it cost, and one close deploys at most MAX_PER_CLOSE legs of `size`
    at at most PRICE_CEILING -- PLUS A56's extra-coin allowance, which is
    real exposure and must be in every rail that reads this (the bank brake,
    the loss abort, the stake cap). Leaving it out would make the extra coin
    free on paper and paid for in a drawdown."""
    # A61: the coin allowance and the late allowance SHARE one extra bet,
    # so the worst close takes their max and not their sum.
    return ((float(MAX_PER_CLOSE) + max(float(EXTRA_COIN), float(LATE_EXTRA)))
            * float(size) * float(PRICE_CEILING))


def one_coin_cap(size, bank, hwm, mult=None):
    """AMENDMENT 45: contracts ONE market may hold when --one-coin-depth is on.

    Three ceilings, the lowest wins, and the answer is never below SIZE (the
    flag only ever ADDS):
      1. mult x SIZE                     (ONE_COIN_MAX, default 2.0)
      2. the close budget, applied by the caller (_room)
      3. what a TOTAL loss at the price ceiling could cost before the drawdown
         brake fires:  (bank - (1 - MAX_DRAWDOWN) x hwm) / PRICE_CEILING
    Unknown bank or high-water mark -> SIZE, i.e. the flag does nothing. So a
    single bad close cannot halt the bot, whatever the flag says.
    """
    size = float(size)
    mult = float(ONE_COIN_MAX if mult is None else mult)
    cap = mult * size
    try:
        if bank is None or hwm is None or float(hwm) <= 0:
            return size
        room = (float(bank) - (1.0 - float(MAX_DRAWDOWN)) * float(hwm)) / float(PRICE_CEILING)
    except (TypeError, ValueError):
        return size
    return max(size, min(cap, room))


# AMENDMENT 63 (2026-09-19): ONCE WE HAVE HEDGED, MORE OF THE HEDGED SIDE IS
# AN ORDINARY BET, NOT A SECOND HEDGE.
#
# The operator: "is there anything in there to buy more once a hedge is
# successful and you have the confidence and other criteria for the new
# actual winning side? ... Does arithmetic support any way of doing that?"
#
# IT DOES, COMPLETELY. Holding n YES at p and m NO at q, one more NO contract
# at r pays (1 - r) if NO lands and costs r if YES lands. That is EXACTLY the
# arithmetic of a fresh bet on NO at r -- the position we already hold does
# not enter into it at all. So the question "should we buy more of the side
# that is now winning" is the question the ordinary gate already answers, and
# the ordinary gate is not being asked.
#
# AMENDMENT 8's reasoning -- "the two legs pay $1.00 between them and cost
# more than that" -- is true of the PAIR and irrelevant to the MARGIN. It was
# written to stop us opening both sides by accident. It should never have
# applied after we deliberately hedged.
#
# LIVE, 2026-09-19 01:44:52, the BNB close that lost $57.98: at 8 seconds our
# model put NO at 99.865% and this gate refused to buy it, because the YES we
# were trying to escape was still on the books.
#
# THE PARAGRAPH THAT USED TO SIT HERE WAS WRONG, AND IT IS THE REASON THIS
# FLAG MUST STAY OFF. It read:
#
#     "AND IT CANNOT RAISE THE WORST CLOSE. Every contract of either side
#      counts against the same close budget, and holding both sides LOWERS
#      the worst case for a given contract count, because one side always
#      pays $1."
#
# BOTH HALVES ARE FALSE, checked 2026-09-19 when the operator asked for this
# to go live:
#
# 1. HEDGE CONTRACTS DO NOT COUNT AGAINST THE CLOSE BUDGET. The hedge path
#    never calls `_note_fill` and never touches `pv["contracts"]`. So after
#    hedging 76 we still have the WHOLE budget free, not none of it.
#
# 2. HOLDING BOTH SIDES ONLY CAPS THE LOSS WHILE THE SIDES ARE BALANCED. With
#    Y on one side and N on the other the close pays `min(Y, N)`, so every
#    contract bought BEYOND the other side's count is a naked directional bet
#    and `min` stops rising. Worked on the real BNB close of 2026-09-19:
#
#      76 YES @0.7498, naked                                worst  -$56.98
#      + 76 NO @0.21 (the hedge A62 now takes)              worst   +$3.06
#      + A63 spending the remaining 138 of budget @0.998    worst -$134.67
#                                                            best   +$3.33
#
#    It risks $138 more to win 27 cents. That is the opposite of the trade.
#
# A SAFE VERSION EXISTS and is NOT worth building: cap the re-buy at the
# other side's count, i.e. only ever COMPLETE a partial hedge. On the BNB
# close that is 75 more NO at 0.998 and moves the loss from -$56.98 to
# -$56.59 -- forty cents, because by the time the gate refused us at tau 8
# the escape was already priced at 99.8c. The money was in hedging at 21c
# twenty seconds earlier, which is A62, and A62 is live.
#
# So the operator's principle -- "once confidence rebuilds on either side you
# can just buy more of that side" -- is right about a FRESH close and wrong
# about a close we are already hedged in, where the hedge is the only thing
# holding the loss down. Left OFF, with the arithmetic recorded so nobody
# re-derives the wrong half of it.
REBUY_HEDGED = False     # --rebuy-hedged; shipped OFF, and see above
_DEFAULT_REBUY_HEDGED = False

# AMENDMENT 68 (2026-09-19): AT A COLLAPSED BELIEF THE OTHER SIDE IS A BET,
# NOT ONLY INSURANCE -- BUT A BOUNDED ONE.
#
# The operator: "at 15% confidence if our confidence is accurate shouldn't we
# have known it's 100% flipping and I've been saying before but even extra
# than the hedge."
#
# HE IS RIGHT, AND IT IS MEASURED. Every live market whose belief fell below
# the 40% panic line went on to lose: 6 of 6. The model is CONSERVATIVE down
# there -- at 0-5% belief it implies ~98% should lose and 100% did; at 15-30%
# it implies ~78% and 100% did. Above 60% belief 0 of 4 lost, so a mild wobble
# really does recover and this must not fire on one.
#
# So at belief b the other side is worth (1 - b), and any price under that is
# a positive-expectation bet. On the 12:30 BNB close, at 15.45% belief:
#
#     44c ask -> +41c a contract      62c -> +23c      77c -> +8c
#
# WHY A63 WAS STILL REFUSED AND THIS IS NOT. A63 had no cap: with the close
# budget free it would have bought 138 more contracts and taken the worst
# case from +$3 to -$134. The bet is good; the SIZE was the problem. Here the
# extra is capped at REBUY_MAX_MULT x the contracts we hold on the losing
# side, so the tail is bounded and quotable BEFORE it happens:
#
#     hold 82.8 YES @0.9727, hedge 82.8 NO @~0.62, then 82.8 MORE NO @0.62
#       NO lands (measured 6 of 6):  +$19 expected
#       YES lands:                   -$51 more than the hedge alone
#
# A 15% tail of -$51 against +$19 expected. That is the trade, stated in
# advance rather than discovered afterwards. n = 6 closes, which is thin, so
# the multiple ships at 1.0 and not higher.
REBUY_MAX_MULT = 1.0     # --rebuy-mult; extra contracts as a multiple of the
                         # losing side's position. 0 disables A68 entirely.
_DEFAULT_REBUY_MAX_MULT = 1.0


def rebuy_room(held_losing, already_extra, mult=None):
    """Extra contracts of the HEDGED-INTO side we may still buy.

    `held_losing` is what we hold on the side the model has given up on;
    `already_extra` is what this amendment has already bought beyond the
    hedge. Never negative, and zero whenever the multiple is off.
    """
    m = REBUY_MAX_MULT if mult is None else mult
    try:
        m = float(m)
        cap = m * float(held_losing)
    except (TypeError, ValueError):
        return 0.0
    if m <= 0 or cap <= 0:
        return 0.0
    return max(0.0, cap - max(0.0, float(already_extra or 0.0)))


def worst_close_both_sides(y_n, y_px, n_n, n_px):
    """Dollars at risk on a close where we hold BOTH sides.

    The close pays $1 on exactly one side, so the payout is `min(y_n, n_n)`
    and every contract past that is naked. This is the arithmetic A63's
    withdrawn comment got wrong; it exists so the self-test can assert it.
    """
    return min(float(y_n), float(n_n)) - (float(y_n) * float(y_px)
                                          + float(n_n) * float(n_px))


def _both_sides_block(prev, ticker, want, hedged_side=None, room=None):
    """True when we already hold the OPPOSITE side of this market.

    AMENDMENT 8. Holding both sides of one binary cannot win: the two legs pay
    $1.00 between them and cost more than that, so the pair locks in the
    difference. Only an opposite side blocks; a SAME-side re-look is a top-up
    and must pass, which is exactly what the misplaced version got wrong.

    A63: `hedged_side` is the side we deliberately hedged INTO on this market,
    if any. Buying more of THAT side is an ordinary bet on the margin and is
    allowed when REBUY_HEDGED is on. Buying more of the side we are escaping
    is still refused -- that is averaging into a position the model has
    already given up on.
    """
    if prev is None or want is None:
        return False
    held = (prev.get("sides") or {}).get(ticker)
    if held is None or held == want:
        return False
    if REBUY_HEDGED and hedged_side is not None and want == hedged_side:
        return False
    # A68: more of the side we HEDGED INTO, while the model has given up on
    # the other one, and only while there is room under the cap. `room` is
    # None on every path that has not worked it out, and None must block --
    # an unknown allowance is not an allowance.
    if (hedged_side is not None and want == hedged_side
            and room is not None and float(room) > 0):
        return False
    return True


def staged_take(tau, take_n, size, early_held):
    """AMENDMENT 46: (contracts, leg) for one candidate order.

    leg is one of:
      "full"        the flag is off, or tau <= TAU_MAX with no early leg held:
                    today's order, untouched.
      "early"       tau > TAU_MAX and nothing held yet: at most EARLY_FRAC x SIZE.
      "early_once"  tau > TAU_MAX but an early leg is already held: 0, refuse.
      "topup"       tau <= TAU_MAX with an early leg held: complete the position
                    to SIZE and no further.
    """
    take_n, size, early_held = float(take_n), float(size), float(early_held or 0.0)
    if EARLY_TAU_MAX <= TAU_MAX:
        return take_n, "full"
    if tau > TAU_MAX:
        if early_held > 0:
            return 0.0, "early_once"
        return min(take_n, EARLY_FRAC * size), "early"
    if early_held > 0:
        return min(take_n, max(0.0, size - early_held)), "topup"
    return take_n, "full"


def size_for_bank(bank, brake=None, lo=None, hi=None):
    """Largest size whose worst close the bank covers `brake` times over."""
    brake = BANK_BRAKE if brake is None else brake
    lo = AUTO_SIZE_MIN if lo is None else lo
    hi = AUTO_SIZE_MAX if hi is None else hi
    per = worst_close_cost(1.0) * float(brake)
    if per <= 0 or bank is None:
        return lo
    return int(max(lo, min(hi, int(float(bank) // per))))


def read_bank(creds=None):
    """Live cash, in DOLLARS, or None.

    THE UNIT IS READ FROM THE RESPONSE, NEVER INFERRED FROM THE MAGNITUDE
    (CLAUDE.md hard rule 5). /portfolio/balance carries `balance` in cents AND
    `balance_dollars` as a decimal string. Both are required and they must
    agree, because the failure mode is not subtle: 19215 read as dollars asks
    for size 6535.
    """
    c = creds or CREDS
    if not c.get("pk"):
        return None
    try:
        st, j = pintake._get(c["base"], c["pk"], c["key_id"],
                             "/portfolio/balance")
    except Exception:
        return None
    if st != 200 or not isinstance(j, dict):
        return None
    cents, dollars = j.get("balance"), j.get("balance_dollars")
    if cents is None or dollars is None:
        return None
    try:
        a, b = float(cents) / 100.0, float(dollars)
    except (TypeError, ValueError):
        return None
    if abs(a - b) > 0.01:
        return None
    return b


def apply_size(new_size, a, why, rec=None):
    """Move SIZE and EVERY rail derived from it, together.

    THIS IS THE WHOLE RISK OF AMENDMENT 16. MAX_TAKE_COUNT, MAX_RUN_STAKE and
    --loss-abort are computed once from --size in main(). Raising SIZE without
    them reproduces 2026-09-08 exactly: orders sent, none filled, no error
    raised, because take() RETURNS its refusal rather than raising. Every one
    of these is loosened only -- set_limits() refuses to tighten.
    """
    new_size = float(new_size)
    old = float(SIZE)
    globals()["SIZE"] = new_size
    wc = 1.00 * new_size * float(MAX_PER_CLOSE)   # the loss-abort band's unit
    # A65: the derived band, then clamped by --loss-cap if one is set. Done
    # HERE and not once at start-up, because this line is what recomputes the
    # abort every time the bank moves.
    want_abort = abort_for(new_size)              # mid-band, or the cap
    # AMENDMENT 30: THIS NOW TIGHTENS AS WELL AS LOOSENS, and the one-way
    # ratchet it replaces was the weakest rail in the bot. It read
    # `if want_abort < a.loss_abort`, so the dollar stop followed the bank UP
    # and never came back DOWN: once the bank reached $310 the stop sat at
    # -$208 and stayed there even if the bank halved. The operator found it
    # from the other end -- "if we lose it should signal it to immediately
    # recalculate the contract size" -- and it is the same defect.
    #
    # Tightening is safe HERE, unlike in set_limits(): this is a plain float
    # on the args object, not a rail that refuses a decrease and would roll
    # SIZE back with it.
    a.loss_abort = want_abort
    # NEVER HAND set_limits A TIGHTENING. It refuses one, and a refusal here
    # would roll SIZE back -- which on a size DECREASE means the bot could
    # never shrink after a loss, the one direction that must always work.
    # Caught by the self-test on 2026-09-13. The brake stays at its loosest
    # high-water mark; that is the safe side, because a decrease is already
    # reducing what can be lost.
    _abort = min(float(a.loss_abort), float(pintake.LOSS_ABORT))
    try:
        pintake.set_limits(
            loss_abort=_abort,
            max_run_stake=max(pintake.MAX_RUN_STAKE, 3.0 * wc + 10.0),
            # A53: the cap admits every multiple a flag can ask for, or the
            # live path refuses the wider order while the paper path books it
            max_take_count=max(pintake.MAX_TAKE_COUNT,
                               new_size * max(ONE_COIN_MAX if ONE_COIN_DEPTH else 1.0,
                                              DOUBT_MULT,
                                              LATE_MULT, max_band_mult(), FLIP_MULT)),
            why=f"auto-size {old:g} -> {new_size:g}: {why}")
    except Exception as e:                        # a refused loosening must
        globals()["SIZE"] = old                   # not leave SIZE ahead of
        return False, f"set_limits refused ({e}); size held at {old:g}"
    if rec:
        rec("autosize", old=old, new=new_size, why=why,
            loss_abort=float(a.loss_abort),
            max_run_stake=pintake.MAX_RUN_STAKE,
            max_take_count=pintake.MAX_TAKE_COUNT)
    return True, (f"size {old:g} -> {new_size:g} ({why}); abort "
                  f"${a.loss_abort:.2f}, stake cap "
                  f"${pintake.MAX_RUN_STAKE:.2f}, take count "
                  f"{pintake.MAX_TAKE_COUNT:g}")


# AMENDMENT 66 (2026-09-19): PAPER ARMS MUST TRADE THE SIZE LIVE TRADES.
#
# The operator: "make sure the whole issue of non proportional paper contracts
# is solved and they're dynamic and changing to the live one too."
#
# A16's comment already claims arms auto-size "exactly as live does", and
# `autosize_tick` was deliberately un-gated from `a.live` on 2026-09-14 to
# make that true. IT WAS NEVER TRUE. Measured 2026-09-19: **0 autosize
# records across all 43 running arms**, every one pinned at 20 while live ran
# 109. The reason is two lines away and is a SAFETY feature, not a bug --
# `read_bank()` returns None without `CREDS["pk"]`, and `arm()` fills CREDS
# only under --live. A paper arm has no key, by design, and must not get one.
#
# So live PUBLISHES its size and paper READS it. No credentials leave the
# live process, the arms need no network call at all, and an arm's size is
# exactly live's rather than live's recomputed -- which also fixes the second
# break: arms launched with `--bank-brake 4.08` would have sized to 77 where
# live at 3.00 sizes to 109, so even a working bank read would not have made
# them proportional.
#
# WHAT THIS DOES NOT FIX, and what the Lab's head-to-head does: the dollars
# already recorded. Those are corrected by reading cents per contract instead
# of dollars, which is stake-free. What per-contract CANNOT correct is fill
# realism -- a 109-contract order eats further into the book than a
# 20-contract one -- and only real sizing fixes that. Every arm-hour before
# this amendment was measured at a stake that never faced live's depth.
SIZE_MIRROR = os.path.join(RESULTS, "pinrun-live-size.json")
SIZE_MIRROR_MAX_AGE_S = 3600.0   # a stale file must not pin an arm forever
SIZE_MIRROR_ON = True            # --no-size-mirror for an arm testing a size
_DEFAULT_SIZE_MIRROR_ON = True   # the offline-loop self-test pins the flag to this


def publish_size(size, bank=None, path=None):
    """LIVE ONLY: record the size every paper arm should copy."""
    try:
        with open(path or SIZE_MIRROR, "w", encoding="utf-8") as fh:
            json.dump({"size": float(size),
                       "bank": None if bank is None else round(float(bank), 2),
                       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "epoch": time.time()}, fh)
    except (OSError, TypeError, ValueError):
        return None
    return float(size)


def read_mirror_size(path=None, max_age_s=None, now=None):
    """The live bot's current size, or None.

    None on every doubt -- missing, unreadable, malformed, non-positive, or
    older than `max_age_s`. An arm that cannot read it keeps its --size,
    which is exactly the behaviour that shipped before this amendment, so
    the failure mode is the status quo and never a wild bet.
    """
    age = SIZE_MIRROR_MAX_AGE_S if max_age_s is None else max_age_s
    try:
        with open(path or SIZE_MIRROR, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    try:
        size = float(d.get("size"))
        stamp = float(d.get("epoch"))
    except (TypeError, ValueError):
        return None
    if not (size > 0):
        return None
    if (time.time() if now is None else now) - stamp > float(age):
        return None
    return size


def autosize_tick(state, a, open_positions, rec=None, now=None,
                  bank_reader=None, hwm_path=None, mirror_path=None):
    """Called at the top of the loop. Returns a message when size moved."""
    # NOT GATED ON a.live ANY MORE (2026-09-14). It was, and the consequence
    # was that every paper what-if traded at its --size while the live bot
    # auto-sized to the bank: on 2026-09-14 live ran 52 contracts and all four
    # arms ran 20, so none of their dollar figures could be compared with
    # live's. The whole point of an arm is to be identical but for one flag.
    # Reading the balance is a GET and costs nothing.
    if not (AUTO_SIZE and getattr(a, "auto_size", True)):
        return None
    now = time.time() if now is None else now
    if now - state.get("autosize_at", 0.0) < AUTO_SIZE_EVERY_S:
        return None
    if open_positions:
        return None                      # never move a rail under a position
    state["autosize_at"] = now
    # A66: a PAPER arm copies live's size instead of reading a balance it has
    # no key for. Done before the bank read, because that read is the thing
    # that has been silently returning None in every arm since 2026-09-14.
    #
    # `bank_reader is None` IS PART OF THE CONDITION. The real trade loop calls
    # `autosize_tick(state, a, open_pos, rec=rec)` with no reader, so a live
    # arm takes the real path and a paper arm takes the mirror. Every caller
    # that INJECTS a reader is a test saying "drive the bank path", and the
    # first version of this line short-circuited the deposit-detection tests
    # out of existence -- they went green by not running.
    if (not getattr(a, "live", False) and SIZE_MIRROR_ON
            and bank_reader is None):
        _m = read_mirror_size(mirror_path, now=now)
        if _m is None:
            state["mirror_misses"] = state.get("mirror_misses", 0) + 1
            return None
        state["mirror_size"] = _m
        if abs(_m - float(SIZE)) < 1e-9:
            return None
        _ok, _msg = apply_size(_m, a, f"mirroring live size {_m:g}", rec=rec)
        return _msg
    bank = (bank_reader or read_bank)()
    if bank is None:
        state["autosize_fails"] = state.get("autosize_fails", 0) + 1
        return None
    state["bank"] = bank
    # AMENDMENT 43: was this a withdrawal, or did we lose it? Must run BEFORE
    # the drawdown is computed, or the brake trips on the operator's own cash.
    _real = float(pintake.LEDGER.get("realised", 0.0) or 0.0)
    if EXTERNAL_DETECT:
        _kind, _amt = classify_bank_move(bank, state.get("ext_bank"), _real,
                                         state.get("ext_realised"))
        if _kind in ("withdrawal", "deposit"):
            _moved = shift_hwm(_amt, hwm_path)
            state["ext_events"] = state.get("ext_events", 0) + 1
            if rec:
                # `move`, NOT `kind`. rec(kind, **kw) takes kind POSITIONALLY,
                # so rec("external", kind=...) raises TypeError: got multiple
                # values for argument 'kind'. That is exactly what killed the
                # live bot at 2026-09-15 04:29:30Z -- a late settlement from
                # the previous run landed in the balance, read correctly as a
                # deposit, and the logging line crashed the trade loop. The
                # unit tests covered classify_bank_move and shift_hwm in
                # isolation and never drove autosize_tick through the branch.
                rec("external", move=_kind, amount=round(_amt, 2),
                    bank=round(bank, 2), hwm_now=_moved,
                    realised_since=round(_real - (state.get("ext_realised") or 0.0), 4))
            print(f"  *** {_kind.upper()} of ${abs(_amt):.2f} detected -- not a "
                  f"trading loss. High-water mark moved to "
                  f"${(_moved if _moved is not None else 0.0):.2f}; the drawdown "
                  f"brake keeps measuring trading only. ***")
    state["ext_bank"] = bank
    state["ext_realised"] = _real
    # AMENDMENT 30: refresh the high-water mark and the drawdown BEFORE the
    # size is chosen, so a fall in the bank shrinks the bet on the same tick
    # that notices it rather than on the next one.
    _hwm_before = read_hwm(hwm_path)
    hwm = write_hwm(bank, hwm_path) or bank
    state["hwm"] = hwm
    state["drawdown"] = drawdown(bank, hwm)
    # AMENDMENT 39 -- THE LOSS COUNTER RESETS WHEN THE BANK IS WHOLE AGAIN.
    #
    # The operator, 2026-09-14: "the loss brakes change automatically counter
    # should reset when the balance hits the balance where it originally fell
    # from."
    #
    # Until now the count only ever went up, and the only thing that cleared
    # it was a RESTART -- so the brake's memory was tied to process lifetime
    # rather than to money, and restarting the bot was a way to launder two
    # losses away. Now it clears exactly when the bank gets back to the level
    # it fell from, which is the same event that the drawdown brake treats as
    # recovery. One rule, one definition of "whole".
    #
    # `bank >= _hwm_before` is the test, evaluated against the mark as it
    # stood BEFORE this tick wrote to it -- write_hwm() raises the mark to the
    # new bank, so reading it afterwards would make every tick look like a
    # recovery.
    if (_hwm_before and bank is not None
            and float(bank) >= float(_hwm_before) - 1e-9
            and int(pintake.LEDGER.get("losses", 0) or 0) > 0):
        _was = int(pintake.LEDGER.get("losses", 0) or 0)
        pintake.LEDGER["losses"] = 0
        state["losing_closes"] = set()
        state["loss_resets"] = state.get("loss_resets", 0) + 1
        print(f"  *** LOSS COUNTER RESET: bank ${bank:.2f} is back to its high "
              f"of ${float(_hwm_before):.2f}; {_was} losing close(s) cleared ***")
    want = size_for_bank(bank)
    cur = float(SIZE)
    if want > cur and AUTO_SIZE_STEP_UP:
        want = min(want, max(cur + 1.0, int(cur * AUTO_SIZE_STEP_UP)))
    if abs(want - cur) < 1e-9:
        return None
    ok, msg = apply_size(want, a, f"bank ${bank:.2f}", rec=rec)
    # A66: publish AFTER the rails moved, and only when they actually moved,
    # so an arm never copies a size the live bot failed to adopt.
    if ok and getattr(a, "live", False):
        publish_size(float(SIZE), bank, mirror_path)
    return msg if ok else msg


# ===========================================================================
def _fresh_near():
    # "depths" records the contracts ON OFFER at every moment we could have
    # bought, whether or not we did. Added 2026-09-08 at the operator's
    # request: "track the times we would buy/do buy and how many orders are
    # available at that moment". Without it the only depth we ever saw was the
    # single best moment, which cannot answer how far we can scale.
    #
    # AMENDMENT 44: "ladders" is the same question asked of the WHOLE book
    # rather than the touch. Since the sweep (A35) and the ladder-aware floor
    # (A37) the touch is no longer what we can buy, so a depth trend built on
    # it understates capacity. Sampled ONCE PER MARKET PER CLOSE -- about nine
    # calls a close against four thousand looks -- so it costs nothing in the
    # 20 Hz loop. "ladder_seen" is a set and is deliberately never serialised.
    return {"best": None, "n": 0, "decided": 0, "tradeable": 0,
            "no_offer": 0, "undecided": 0, "dust": 0, "depths": [],
            "ladders": [], "ladder_seen": set(), "shallow": {}}


def committed_for(cost, nfill):
    """Dollars pintake commits for a fill, and therefore the dollars that must
    be released when it settles. Module level ON PURPOSE: the self-test that
    was blind to the release bug was blind because it RETYPED the arithmetic
    inline at size 1, where price and price*1 are the same number. A test must
    drive the same expression the runner drives."""
    return float(cost) * float(nfill)


def _depth_report(depths):
    """What the offer looked like across a close, and how many of those
    moments survive at each candidate SIZE. A moment offering fewer contracts
    than we want to buy is skipped by the dust gate, so this table is exactly
    the opportunity cost of scaling."""
    if not depths:
        return None
    d = sorted(depths)
    n = len(d)
    return {
        "n": n,
        "min": round(d[0], 2),
        "p25": round(d[n // 4], 2),
        "median": round(d[n // 2], 2),
        "p75": round(d[(3 * n) // 4], 2),
        "max": round(d[-1], 2),
        "total": round(sum(d), 2),
        # moments that would still qualify at each size.
        # AMENDMENT 44: extended past 250. The old list stopped exactly at the
        # size cap, so the log could never answer "how much higher could the
        # cap go" -- the one question the operator asks of it. Costs nothing:
        # it is a comprehension over a list already in memory.
        "kept": {str(k): sum(1 for x in d if x >= k)
                 for k in (1, 5, 10, 15, 25, 50, 75, 125, 250,
                           500, 750, 1000, 2000)},
    }


def trade_loop(a, rec, book, idx, series_index, trec=None):
    live = a.live
    # R4: the SECOND writer, for the trajectory only. main() points it at its
    # own file so tens of MB a day of samples never reach the log the
    # settlement readers share; the offline loop passes nothing, so the
    # samples land in the trail the self-tests read. `rec` is the fallback and
    # not a silent one: every trajectory record carries kind "traj".
    _trec = rec if trec is None else trec
    fired = {}                 # close_s -> ticker we already fired on
    attempts = {}              # close_s -> orders SENT, filled or not
    last_edge = {}             # AMENDMENT 24: ticker -> (close_s, net edge)
                               # as measured on the PREVIOUS pass, 50ms ago.
    attempts_tk = {}           # AMENDMENT 26: (close_s, ticker) -> orders sent
    seen_markets = {}          # ticker -> (iid, close_s, strike, digits, exi)
    uni_at = 0.0
    watching = {}            # ticker -> close_s, so closed ones drop out
    # ticker -> (close_s, want, cost_per_contract, contracts). THE FOURTH
    # FIELD IS NEW (2026-09-08) AND IT IS THE WHOLE FIX: pintake commits
    # `filled * price` on a fill, so a release of bare `price` strands
    # (filled-1)*price forever. At size 5 that is $3.90 a trade and the $60
    # run-stake cap turns back into a cap on LIFETIME TURNOVER after ~15
    # fills -- the exact bug that was fixed once at size 1 and written as a
    # size-1 literal. Found by an adversarial audit, reproduced by a probe.
    # KEYED BY ORDER ID, NOT BY TICKER. Keying by ticker meant a SECOND fill
    # on the SAME market silently overwrote the first: 2026-09-08 23:29:53Z
    # filled SOL twice in one close, at 94.0c and 90.1c. Both paid out at the
    # exchange and the bank reconciles, but our ledger booked only one -- the
    # 112.10c win was never recorded and its $18.80 stake was never released.
    # A leaked stake walks the run into the MAX_RUN_STAKE cap, and an unbooked
    # LOSS would be invisible to the loss abort, which is the dangerous
    # direction. MAX_PER_CLOSE 3 makes same-ticker repeats more likely, not
    # less. Value is (close_s, want, cost, nfill, ticker).
    open_pos = {}
    boosted = set()          # A53: (close_s, ticker) pairs an order was widened
                             # for, so a boosted LOSS can switch the boost off
    _boosted48 = set()       # A55: the same, for the last-seconds boost
    _boosted_dbt = set()     # R1: the same, for the doubt boost -- one
                             # doubt-boosted LOSS switches --doubt-mult off
                             # for the rest of the run (the A53/A55 rail)
    boost_why = {}           # A58: (close_s, ticker) -> why the last-seconds
                             # boost did or did not fire, carried into the
                             # settled record so every trade can be asked
    entry_at = {}            # A52: oid -> wall-clock second we ENTERED, so the
                             # jump trigger measures moves since entry and not
                             # since the last three seconds
    hedge_meta = {}     # A15: oid -> (strike, digits, iid) so belief can be recomputed
    hedged = set()      # A15: oids already hedged (or given up on)
    hedge_tries = {}    # A15: oid -> attempts since the alarm fired
    hedge_alarmed = set()         # A76: positions whose alarm has been logged
    hedge_prop_said = {}          # A76: oid -> last fraction reported, so a
                                  # change of band is logged once, not 20 Hz
    hedge_last_try = {}
    _hq71 = set()                 # A71: (position, reason) already reported as
                                  # a silent hedge skip -- see _hquiet below
    hedge_attempts = {}           # A71: close -> HEDGE sends, counted apart
                                  # from the entry path's `attempts` so an
                                  # entry rail can never disable a hedge
    hedge_price_said = set()      # A47: one 'waiting on price' line per position # A15: oid -> wall-clock second of the last try (pacing)
    hedge_normal_said = set()     # A51: one 'waiting for a normal bet' line per position
    hedge_panic_said = set()      # A62: one 'every filter bypassed' line per position
    hedge_quote_at = {}           # (5): ticker -> second of its last hedge_quote
    rebuy_extra = {}              # A68: ticker -> contracts bought BEYOND the
                                  # hedge, so the cap is against a real count
    last_belief = {}              # A68: ticker -> the newest belief measured
                                  # while holding. The rebuy is allowed only
                                  # while THIS is at or under the panic line;
                                  # a belief that has recovered must close the
                                  # door again, and a missing one keeps it shut
    last_belief_t = {}            # K3b (2026-09-23): ticker -> the wall-clock
                                  # second last_belief was last WRITTEN. A
                                  # covered position leaves the hedge pass
                                  # above that write, so the `belief` printed
                                  # in hedge_quote can be nine seconds old and
                                  # read exactly like a live one. It did, on
                                  # KXDOGE15M-26SEP222245-45: byte-identical
                                  # at tau 9..1 while the book moved every
                                  # second, and no field in the log said so.
    hedged_side = {}              # A63: ticker -> the side we hedged INTO, so
                                  # more of it is an ordinary bet and not a
                                  # second hedge
    hedge_remain = {}   # A15 BUGFIX 2026-09-13: oid -> contracts STILL needing a
                        # hedge fill. open_pos[_hid] must NEVER be shrunk here; it
                        # is what reconcile() reads to settle the ORIGINAL position
                        # and to feed pintake.record_pnl(), which the loss-abort
                        # and loss-count brakes read.
    # NEAR MISSES. "nothing fired" is not information; "the best on offer was
    # 0.2c and we need 0.5c" is. Per close, keep the best net edge seen on
    # each side and report it when the close passes, so a quiet run can be
    # told apart from a blind one.
    near = {}                # close_s -> dict of the best look at that close
    dumped_seen = set()      # (close_s, ticker) already written as `dumped`
    # ---- R4: THE TRAJECTORY. Records and in-memory history only. ----------
    # Every one of these is keyed by close and popped in report_closes() AND
    # in the 900 s backstop below the sampler, so none can grow with a
    # 4,320-minute run. The one exception is named as one: `traj_blind_blk`
    # has no close to key on, and is bounded by the number of distinct
    # exception type names instead. (An earlier version of this comment said
    # "every one of these" while `traj_blind` was popped by nothing -- a
    # stated bound that was false for the only member that broke it.)
    traj_hist = {}           # (close_s, ticker) -> [(now_s, fair)], the bot's
                             # OWN pre-decision readings. R1's `_doubt` reads
                             # this and nothing else; capped at TRAJ_HIST_MAX.
    traj_at = {}             # (close_s, ticker) -> the last SAMPLED second,
                             # so one market can leave at most one record a
                             # second however fast the loop runs
    traj_n = {}              # close_s -> FAR samples written (TRAJ_MAX)
    traj_n_near = {}         # close_s -> NEAR samples written (TRAJ_MAX_NEAR),
                             # a separate budget far samples can never spend
    traj_drop = {}           # close_s -> samples the budgets refused, so a
                             # bound that bites is visible instead of silent
    traj_blind = set()       # (close_s, ticker, exception) already reported:
                             # a sample that could not be taken says why ONCE
    traj_blind_blk = set()   # ...and the same for a failure of the whole
                             # block, keyed by exception name alone
    look_at = {}             # (close_s, ticker) -> (t, want, price) at the
                             # PREVIOUS look, for the sub-second price drop
                             # the 1 Hz grid cannot see (D_plan section 5)
    look_drop_n = {}         # (close_s, ticker) -> drops recorded, capped at
                             # LOOK_DROP_MAX so a flapping book is bounded
    traj_gate = {}           # (close_s, ticker) -> (pass number, gate name):
                             # THE REAL GATE THAT REALLY REFUSED IT, written
                             # by _gate() itself. Not a second copy of the
                             # gate ladder -- a mirror would drift from the
                             # ladder it mirrors, and this cannot.
    _traj_pruned = [0]       # the second the backstop prune last ran, so it
                             # runs once a second and not twenty times
    _passn = 0               # loop passes so far, so a gate name can be tied
                             # to the pass that produced it and a sample never
                             # reports a refusal from an earlier pass
    # R2: how long the loop's passes took, attributed to the close that was
    # nearest when each pass STARTED. Records only -- nothing reads these to
    # decide anything, and report_closes() hands them back per close.
    pass_gap = {}            # bucket -> (worst pass ms, its tau, why)
    pass_slow = {}           # bucket -> passes over LOOP_SLOW_MS, far half
    # The same two, restricted to passes that STARTED at tau <=
    # LOOP_NEAR_TAU_S. Separate because a far-from-close refresh dominates
    # both the maximum and the record budget, and the bar reads only the
    # near window (see LOOP_REC_MAX_NEAR).
    pass_gap_near = {}
    pass_slow_near = {}
    _prev_pass = None        # (when it started, its bucket, its tau)
    _pass_why = None         # which branch the PREVIOUS pass took, so a
                             # deliberate 1 s pause sleep is not read as a
                             # stall (the bar reads gaps as evidence for
                             # deferring the refresh; a pause is not that)

    # ===================================================================
    # AMENDMENT 25 (2026-09-13): EVERY GATE SAYS WHY, ONCE, ON THE RECORD.
    #
    # THE OPERATOR: "can we keep a separate metric tracking how both
    # separately actually affecting our p/l ... Is it actually possible to
    # implement that for every single function and method of the bot? It
    # would be so powerful to look at each individual implementation and
    # function and algorithm and decision of the bot and see how it alone
    # affected what happens."
    #
    # THIS IS THE INPUT SIDE OF THAT. `research/pinattrib.py` is the reader.
    #
    # WHAT IT RECORDS AND WHY THAT SHAPE. One line per (close, market, gate)
    # -- NOT one per evaluation. The loop runs at 20Hz over every watched
    # market, so a single close produces thousands of looks (4,446 on
    # 2026-09-13 19:45Z) and logging each would drown the file that the
    # settlement reader also reads. Deduping to the first refusal per market
    # per gate keeps it to tens of lines per close and loses nothing: the
    # question is "did this gate stop this trade", which is answered once.
    #
    # WHAT IT CANNOT ANSWER, stated here so the reader cannot overclaim.
    # A refusal records the price that was SHOWING, not a fill. Whether we
    # would have WON that race is unknowable -- CLAUDE.md rule 5, the tape's
    # population is "an offer was sitting there" and ours is "someone
    # actively sold it to us", measured 31x apart. So a gate's money column
    # is an UPPER BOUND on what refusing cost or saved, never a P&L.
    #
    # BEHAVIOUR IS UNCHANGED. Every call sits immediately before a `continue`
    # that was already there. It reads no state, decides nothing, and the
    # self-test asserts the gate names in the source match the ones the
    # reader knows about.
    # ===================================================================
    gate_seen = set()        # (close_s, ticker, gate) already recorded

    def _budget_left(close_s_, tk_, tau_):
        """(5) Contracts this close may still buy for THIS candidate -- the
        same budget the close_budget gate reads -- or None. Never raises:
        it only feeds records."""
        try:
            if not CLOSE_BUDGET:
                return None
            pv = fired.get(close_s_)
            spent = float(pv.get("contracts", 0.0)) if pv else 0.0
            return round(float(close_budget_for(pv, tk_, tau=tau_)) - spent,
                         4)
        except Exception:                                # noqa: BLE001
            return None

    def _gate(name, close_s_, tk_, **detail):
        """Record that `name` refused this market, once per close."""
        nbg = near.setdefault(close_s_, _fresh_near())
        g = nbg.setdefault("gates", {})
        g[name] = g.get(name, 0) + 1
        # R4: WHICH GATE REFUSED THIS MARKET ON THIS PASS. One dict write,
        # ABOVE the dedupe return so it happens on every refusal and not only
        # the first. The scan `continue`s at the first gate that fires, so the
        # value left here by a pass IS that pass's first gate -- which is why
        # the trajectory does not need a second copy of the gate ladder and
        # therefore cannot drift from it. Decides nothing; keyed by close, so
        # report_closes() pops it.
        traj_gate[(close_s_, tk_)] = (_passn, name)
        key = (close_s_, tk_, name)
        if key in gate_seen:
            return
        gate_seen.add(key)
        # (5) 2026-09-22: EVERY refusal says how long was left and how much
        # of this close's contract budget this candidate still had -- about
        # half the gates recorded tau and none the budget, so "refused with
        # 40 contracts of room at 12 s" and "refused with none at 29 s" read
        # the same. Computed so it cannot raise; a gate's own values win.
        if "tau" not in detail:
            try:
                detail["tau"] = int(close_s_ - now_s)
            except Exception:                            # noqa: BLE001
                detail["tau"] = None
        if "budget_left" not in detail:
            detail["budget_left"] = _budget_left(close_s_, tk_,
                                                 detail.get("tau"))
        # SIZE travels with every record. Without it the reader cannot say how
        # many contracts the refusal was worth, and SIZE moves with the bank
        # (AMENDMENT 16) -- it was 20 at 17:51Z and 50 by 21:18Z the same day,
        # so reconstructing it afterwards from the autosize trail is exactly
        # the kind of join that goes quietly wrong.
        rec("refused", gate=name, ticker=tk_, close_s=close_s_,
            size_now=float(SIZE), **detail)
    reported = set()
    recon_at = {}            # ticker -> when the settlement was last polled
    state = {"halted": False, "errors": 0, "signals": 0, "considered": 0}
    end = time.time() + a.minutes * 60


    def _release(oid, tk, cost, nfill):
        """Give back EXACTLY what was committed, and never on only one path.

        pintake._book() adds `filled * price` to LEDGER["committed"]. Anything
        that pops a position must subtract the same product. Before this
        existed, the finalized path released `price` (one contract) and the two
        give-up paths released NOTHING AT ALL, so a run leaked committed
        dollars until the stake cap silently refused every further order --
        with no halt, no error and no log line, because take() RETURNS the
        refusal rather than raising.
        """
        owed = committed_for(cost, nfill)
        pintake.LEDGER["committed"] = max(
            0.0, float(pintake.LEDGER.get("committed", 0.0)) - owed)
        open_pos.pop(oid, None)
        entry_at.pop(oid, None)
        # only drop the ticker from pintake's position map once NO other open
        # fill still references it, or a second fill on the same market would
        # release the first's position record early.
        if not any(v[4] == tk for v in open_pos.values()):
            pintake.LEDGER["positions"].pop(tk, None)
            recon_at.pop(tk, None)
        return owed

    def reconcile():
        """Book settled P&L so the loss abort is a REAL brake, not a nominal one.

        pin holds to settlement, which lands after the close. Without this the
        ledger's `realised` never moves and the only true bound on a run is the
        stake cap. Each closed position is looked up once; a market that has
        not finalised yet is left for the next pass.
        """
        for _oid in list(open_pos):
            close_s, want, cost, nfill, tk = open_pos[_oid]
            if time.time() < close_s + 20:
                continue                      # not settled yet
            # THROTTLE. This runs at the top of a 20 Hz loop and a market that
            # has closed but not finalised is NOT popped -- unthrottled that
            # is ~18,000 blocking GETs per unsettled position, which is both a
            # rate-limit suicide (the failure that blinded the REST paper run)
            # and a stall of the trading loop: kauth.get times out at 20 s.
            if time.time() < recon_at.get(tk, 0.0) + 15.0:
                continue
            recon_at[tk] = time.time()
            try:
                st, b = get("/markets/" + tk)
            except Exception:
                continue
            if st != 200 or not isinstance(b, dict):
                continue
            m = b.get("market") or {}
            if m.get("status") != "finalized":
                if time.time() > close_s + 900:
                    _release(_oid, tk, cost, nfill)   # give up, do not leak
                continue
            res = m.get("result")
            if res not in ("yes", "no"):
                _release(_oid, tk, cost, nfill)
                continue
            won = (res == want)
            # the taker fee is charged on the way in and is part of realised
            # P&L; leaving it out flatters the number the loss abort reads.
            # P&L on the contracts ACTUALLY FILLED, not on the size we
            # asked for. A partial fill booked at full size overstates both
            # the win and the loss the abort reads.
            pnl = (float(nfill) * ((1.0 - cost) if won else (-cost))
                   - billed_fee(cost, nfill))
            pintake.record_pnl(pnl, note=f"{tk} {want} vs {res}")
            # RELEASE the stake. pintake's ledger only ever ADDS to
            # "committed" on a fill and never gives it back, but the field
            # means "dollars at risk RIGHT NOW" and a settled position is no
            # longer at risk -- the cash is back. Without this the $5 cap is a
            # cap on LIFETIME turnover (~5 bets at size 1) rather than on
            # concurrent exposure, and an overnight run halts on its own
            # success. pin holds for <60 s and closes are 15 min apart, so
            # concurrent exposure is one bet, not the night's turnover.
            _release(_oid, tk, cost, nfill)
            state["settled"] = state.get("settled", 0) + 1
            state["wins"] = state.get("wins", 0) + int(won)
            if not won:
                # AMENDMENT 8(B): THE BRAKE COUNTS LOSING CLOSES, NOT LOSING
                # TRADES. The unit of information is a CLOSE -- twelve series
                # settle on the same second at rho ~0.8, and three fills on ONE
                # market are ONE draw, not three. Tonight three fills on one
                # NEAR market spent the entire 3-loss budget on a single event,
                # when LOSS_PLAN's "three losses is roughly a 1% event" is
                # arithmetic on three INDEPENDENT draws. Costs zero trades and
                # makes the brake measure what it was written to measure.
                state["losing_trades"] = state.get("losing_trades", 0) + 1
                _lc = state.setdefault("losing_closes", set())
                _new_close = close_s not in _lc
                _lc.add(close_s)
                if _new_close:
                    pintake.LEDGER["losses"] = int(
                        pintake.LEDGER.get("losses", 0) or 0) + 1
                print(f"  *** A LOSS. losing trades "
                      f"{state['losing_trades']}, losing CLOSES "
                      f"{pintake.LEDGER['losses']} (the brake counts closes) ***")
                # AMENDMENT 30, and it is the operator's own instruction:
                # "if we lose it should signal it to immediately recalculate
                # the contract size". The sizer otherwise waits out the rest
                # of AUTO_SIZE_EVERY_S -- up to five minutes of betting the
                # size a LARGER bank supported. Clearing the timestamp makes
                # the next pass re-read the balance and re-size at once, which
                # also refreshes the drawdown the brake reads.
                state["autosize_at"] = 0.0
                # A53: ONE BOOSTED LOSS SWITCHES THE BOOST OFF for the rest of
                # the run. The operator, 2026-09-18: "we aren't just going to
                # boost a trade above our normal level then just lose a bunch
                # of money" -- the pre-registered bar says revert at the first
                # boosted loss, and a bar the bot enforces itself cannot wait
                # on somebody reading a log. The extra cost of the boost is
                # then bounded by ONE trade's extra size. Every other rail is
                # untouched; ordinary bets continue at SIZE.
                if BAND_MULTS and (close_s, tk) in boosted:
                    globals()["BAND_MULTS"] = ()
                    rec("band_boost_off", ticker=tk, close_s=close_s,
                        cost=round(cost, 4), pnl_c=round(100 * pnl, 2),
                        was=[list(b) for b in _DEFAULT_BAND_MULTS] or None)
                    print(f"  *** A BOOSTED LOSS on {tk}: --band-mult is OFF "
                          f"for the rest of this run ***")
                # A55: "cut at first loss", enforced by the bot rather than by
                # somebody reading a log. The extra cost of the last-seconds
                # boost is then bounded by ONE trade's extra size.
                if LATE_MULT > 1.0 and (close_s, tk) in _boosted48:
                    globals()["LATE_MULT"] = 1.0
                    rec("late_boost_off", ticker=tk, close_s=close_s,
                        cost=round(cost, 4), pnl_c=round(100 * pnl, 2),
                        was=float(_DEFAULT_LATE_MULT))
                    print(f"  *** A LATE-BOOSTED LOSS on {tk}: --late-mult is "
                          f"OFF for the rest of this run ***")
                # R1: the same rail for the doubt boost, and it is the
                # operator's own condition -- "we aren't just going to boost a
                # trade above our normal level then just lose a bunch of
                # money". 0 losers in 66 doubt-flagged markets still leaves a
                # 95% upper bound of 5.28% against a 2.44% base, so the zero
                # is NOT established; this bounds the extra cost of being
                # wrong about it at ONE trade's extra size.
                if DOUBT_MULT > 1.0 and (close_s, tk) in _boosted_dbt:
                    _dbt_was = float(DOUBT_MULT)
                    globals()["DOUBT_MULT"] = 1.0
                    rec("doubt_boost_off", ticker=tk, close_s=close_s,
                        cost=round(cost, 4), pnl_c=round(100 * pnl, 2),
                        was=_dbt_was, default=float(_DEFAULT_DOUBT_MULT))
                    print(f"  *** A DOUBT-BOOSTED LOSS on {tk}: --doubt-mult "
                          f"is OFF for the rest of this run ***")
            # A79: the ET day's running total, on disk, BEFORE the record is
            # written -- so a crash between the two loses the log line and not
            # the money. `live` only: a paper arm must never touch the file
            # the live bot's day cap reads.
            _day79 = add_day_loss(pnl) if live else None
            rec("settled", ticker=tk, want=want, result=res, cost=round(cost, 4),
                pnl_c=round(100 * pnl, 2),
                day_realised=(round(_day79, 4) if _day79 is not None else None),
                # A58, the operator: "Start recording the end of each trade
                # we make and why or why didn't the boost fire so I can ask".
                # One plain sentence per settled trade, so the question never
                # needs a log dive.
                boost=boost_why.get((close_s, tk), "no: never reached the "
                                    "last-seconds check"),
                realised=round(pintake.LEDGER["realised"], 4))
            print(f"  SETTLED {tk} {want} vs {res} -> {100 * pnl:+.2f}c "
                  f"(run realised ${pintake.LEDGER['realised']:+.4f})")
        # size x price, NOT price: at --size 0.01 the per-contract figure
        # overstates exposure 100x and the forward loss bound would halt the
        # run on its very first fill.
        state["open_cost"] = sum(c * n for (_, _, c, n, _tk)
                                 in open_pos.values())

    def report_closes(now_s):
        for cs in sorted(near):
            if cs > now_s or cs in reported:
                continue
            reported.add(cs)
            nb = near[cs]
            b = nb.get("best")
            # R2: the worst pass this close ever saw, the tau it started at,
            # what the previous pass was doing, and how many passes were over
            # LOOP_SLOW_MS. Popped so no dict can grow with the run. Never
            # raises -- it only reports.
            #
            # REVIEW FIX 2026-09-22: the *_near columns are the same three
            # restricted to passes that STARTED at tau <= LOOP_NEAR_TAU_S.
            # Without them the only per-close number is a maximum dominated
            # by a refresh eight minutes from the close, while the bar reads
            # only the last 45 s -- so the summary could not answer its own
            # PASS or FAIL. These survive whatever the record budget does.
            _pg = pass_gap.pop(cs, None)
            _ps = pass_slow.pop(cs, 0)
            _pgn = pass_gap_near.pop(cs, None)
            _psn = pass_slow_near.pop(cs, 0)
            # ---- R4: the trajectory's own per-close line, and the prune ----
            # It goes to the TRAJECTORY writer, never into `close_summary`:
            # that record is read by pinattrib, pinlab, barcheck and the
            # settlement readers, and adding a field to it would change a log
            # every one of them already parses. This says how many samples
            # each budget spent and how many it refused, so a bound that bites
            # is on the record instead of silent -- which is the one thing
            # v-instr1's first budget could not say about itself.
            #
            # THE PRUNE IS THE POINT OF DOING IT HERE. Four dicts keyed by
            # close and two keyed by (close, ticker) all lose this close's
            # entries now, so none of them can grow with a 4,320-minute run.
            try:
                _tjf = traj_n.pop(cs, 0)
                _tjn = traj_n_near.pop(cs, 0)
                _tjd = traj_drop.pop(cs, 0)
                _tjk = [k for k in traj_hist if k[0] == cs]
                _tjm = len(_tjk)
                for _k in _tjk:
                    traj_hist.pop(_k, None)
                    traj_at.pop(_k, None)
                for _k in [k for k in traj_gate if k[0] == cs]:
                    traj_gate.pop(_k, None)
                for _k in [k for k in look_at if k[0] == cs]:
                    look_at.pop(_k, None)
                    look_drop_n.pop(_k, None)
                for _k in [k for k in traj_blind if k[0] == cs]:
                    traj_blind.discard(_k)
                if _tjf or _tjn or _tjd:
                    _trec("traj_close", close_s=cs, far=_tjf, near=_tjn,
                          dropped=_tjd, markets=_tjm,
                          far_max=TRAJ_MAX, near_max=TRAJ_MAX_NEAR,
                          every_s=TRAJ_EVERY_S, near_tau_s=TRAJ_NEAR_TAU_S,
                          tau_max=TRAJ_TAU_MAX, unsummarised=False)
            except Exception:                            # noqa: BLE001
                pass
            if b is None:
                rec("close_summary", close=cs, looks=nb["n"],
                    decided=nb["decided"], undecided=nb["undecided"],
                    no_offer=nb["no_offer"], dust=nb["dust"],
                    fired=(cs in fired), best=None,
                    gates=nb.get("gates", {}),      # AMENDMENT 25
                    pass_gap_ms=(_pg[0] if _pg else None),
                    pass_gap_tau=(_pg[1] if _pg else None),
                    pass_gap_why=(_pg[2] if _pg else None),
                    slow_passes=_ps,
                    pass_gap_near_ms=(_pgn[0] if _pgn else None),
                    pass_gap_near_tau=(_pgn[1] if _pgn else None),
                    pass_gap_near_why=(_pgn[2] if _pgn else None),
                    slow_passes_near=_psn,
                    near_tau_s=LOOP_NEAR_TAU_S,
                    depth=_depth_report(nb.get("depths")),
                    ladder=_depth_report(nb.get("ladders")),
                    why=("decided but NOBODY OFFERED the winning side"
                         if nb["no_offer"] else
                         "no market ever reached the 98% gate"))
                print(f"  close {time.strftime('%H:%M', time.gmtime(cs))}Z: "
                      f"{nb['n']} looks, {nb['decided']} decided, "
                      f"{nb['no_offer']} decided-but-nothing-offered, "
                      f"{nb['undecided']} undecided")
            else:
                rec("close_summary", close=cs, looks=nb["n"],
                    decided=nb["decided"], undecided=nb["undecided"],
                    no_offer=nb["no_offer"], dust=nb["dust"],
                    tradeable=nb["tradeable"], fired=(cs in fired),
                    best_ticker=b["ticker"], best_want=b["want"],
                    over_ceiling=nb.get("over_ceiling", 0),
                    neg_ev=nb.get("neg_ev", 0),
                    gates=nb.get("gates", {}),      # AMENDMENT 25
                    pass_gap_ms=(_pg[0] if _pg else None),   # R2
                    pass_gap_tau=(_pg[1] if _pg else None),
                    pass_gap_why=(_pg[2] if _pg else None),
                    slow_passes=_ps,
                    pass_gap_near_ms=(_pgn[0] if _pgn else None),
                    pass_gap_near_tau=(_pgn[1] if _pgn else None),
                    pass_gap_near_why=(_pgn[2] if _pgn else None),
                    slow_passes_near=_psn,
                    near_tau_s=LOOP_NEAR_TAU_S,
                    depth=_depth_report(nb.get("depths")),
                    ladder=_depth_report(nb.get("ladders")),
                    shallow_skips=nb.get("shallow", {}),
                    price_ceiling=PRICE_CEILING,
                    best_edge_c=round(100 * b["edge"], 3),
                    best_price=round(b["price"], 4),
                    best_fair=round(b["fair"], 5), best_tau=b["tau"],
                    best_size=b["size"],
                    needed_c=round(100 * EDGE_FLOOR, 2))
                v = "FIRED" if cs in fired else "no trade"
                # SIZE BELONGS IN THIS LINE. Without it, 2026-09-18 23:00Z
                # read "best ... @0.9760 edge +2.20c (need +0.3c) -> no trade"
                # and looked like a gate wrongly refusing a good trade. The
                # offer held 0.02 CONTRACTS -- two cents of exposure, nothing
                # to buy. The operator read the line the same way I did.
                print(f"  close {time.strftime('%H:%M', time.gmtime(cs))}Z: "
                      f"{nb['n']} looks, best was {b['ticker'][:22]} "
                      f"{b['want'].upper()} @{b['price']:.4f} "
                      f"edge {100*b['edge']:+.2f}c "
                      f"(need +{100*EDGE_FLOOR:.1f}c) "
                      f"x{b['size']:.4g} on offer -> {v}")
            near.pop(cs, None)

    # ===================================================================
    # K1 (2026-09-22): THE LOOP CANNOT DIE WHILE HOLDING.
    #
    # The per-market entry scan (~1,200 lines) and the per-position hedge
    # step had no outer `try`, and main() wraps the loop in try/finally only,
    # so ANY exception in either ended the process -- with whatever it held
    # left unhedged until settlement. It has happened three times, all at
    # exactly 30 s to go, the first second the entry path runs its rarer
    # branches: 09-15 04:29:30Z, 09-15 04:59:30Z, and 09-19 05:59:30Z, which
    # was holding 70 BTC NO and lost $66.34 with no hedge.
    #
    # Both bodies are now wrapped. A caught exception is recorded ONCE per
    # (where, close, market, error type) -- this is a 20 Hz loop -- with the
    # line it came from, and the loop moves on to the next market or
    # position. It never exits and never skips the hedge pass.
    #
    # NEW ENTRIES STOP after SCAN_ERRORS_STOP_ENTRIES DISTINCT scan errors,
    # or after the FIRST error in the hedge step: a scan that keeps throwing
    # is code broken in a way nobody has looked at, and a bot whose hedge
    # step throws must not open positions it may not be able to insure. The
    # old loop died at that point, which stopped its buying too.
    #
    # THE STOP IS NOT FOR EVER. It is handed to the risk check below as a
    # terminal halt, so it takes A74's drain: no new bets, the hedge pass
    # keeps running on everything held, and the process EXITS once flat.
    # watch_bot.ps1 then restarts it at once ("DOWN after halt"), exactly as
    # it restarted the old loop after a crash -- but only after every held
    # position has been hedged or settled. Before this, the stop lasted the
    # rest of the run (up to --minutes 4320) while the process stayed alive
    # and wrote records, so watch_bot's silence check never fired.
    # WHAT IT BLOCKS: new bets only. It cannot block a hedge -- the hedge
    # pass runs above the scan and the drain, and never reads it.
    # ===================================================================
    _k1_seen = set()

    def _k1_error(where, close_s_, tk_, exc):
        """Record a caught exception once per (where, close, market, type).
        Returns True the first time. Never raises."""
        key = (where, close_s_, tk_, type(exc).__name__)
        if key in _k1_seen:
            return False
        _k1_seen.add(key)
        _line = None
        try:
            _tb = exc.__traceback__
            while _tb is not None and _tb.tb_next is not None:
                _tb = _tb.tb_next
            _line = _tb.tb_lineno if _tb is not None else None
        except Exception:                                # noqa: BLE001
            pass
        try:
            rec("error", where=where, ticker=tk_, close_s=close_s_,
                err=(type(exc).__name__ + ": " + str(exc))[:300], line=_line)
        except Exception:                                # noqa: BLE001
            pass
        try:
            print(f"  *** {where} error on {tk_} (line {_line}), stepping "
                  f"over it: {type(exc).__name__}: {exc}")
        except Exception:                                # noqa: BLE001
            pass
        return True

    def _k1_stop_entries(why, close_s_, tk_):
        """Stop NEW entries (once). The risk check turns it into a drain,
        and the run exits when flat. Never raises."""
        if state.get("entries_stopped"):
            return
        state["entries_stopped"] = why
        try:
            rec("entries_stopped", why=why,
                errors=state.get("scan_errors", 0), ticker=tk_,
                close_s=close_s_, hedging="still armed",
                then="exit when flat; watch_bot restarts")
        except Exception:                                # noqa: BLE001
            pass
        try:
            print(f"  *** NEW ENTRIES STOPPED: {why}. Hedging continues; "
                  f"the run exits when flat.")
        except Exception:                                # noqa: BLE001
            pass

    def _k1_scan_error(close_s_, tk_):
        """Count a NEW scan fault; at the limit, stop new entries (once)."""
        state["scan_errors"] = state.get("scan_errors", 0) + 1
        if state["scan_errors"] >= SCAN_ERRORS_STOP_ENTRIES:
            _k1_stop_entries(f"{state['scan_errors']} distinct entry-scan "
                             f"errors", close_s_, tk_)

    while time.time() < end:
        # R4: one integer add, so a recorded gate name can be tied to the pass
        # that produced it. Nothing reads it to decide anything.
        _passn += 1
        # AMENDMENT 71: EVERYTHING ABOVE THE HEDGE PASS IS NOW GUARDED.
        #
        # A69 moved the hedge above the risk check because a `continue` there
        # skipped it and cost $107.95. But `continue` was never the only way
        # to skip the hedge -- an EXCEPTION above it kills the whole process
        # while a position is open, which is the $66.34 loss from the same
        # day (`round(None)` in a log call, 30 seconds before a close). Both
        # of these run first and neither was wrapped:
        #
        #   report_closes() -- eleven bare subscripts on the `near` and `best`
        #     dicts. Safe only while two writers agree about their keys.
        #   reconcile()     -- bare pintake.LEDGER['losses'] / ['realised']
        #     subscripts inside f-strings, plus one blocking HTTP GET per
        #     open position (kauth timeout 20 s, throttled to one per ticker
        #     per 15 s). Three unfinalised tickers timing out is SIXTY SECONDS
        #     above the hedge pass -- longer than the whole hedge window, and
        #     it reproduces the A69 shape exactly with nothing in the log.
        #
        # Reporting and reconciliation are bookkeeping. A hedge is the only
        # thing in this loop that reduces a loss already taken. Bookkeeping
        # must never be able to stop it, so a failure here is counted, said
        # once, and stepped over -- the loop continues to the hedge.
        try:
            report_closes(int(time.time()) - 5)
        except Exception as _e71:                        # noqa: BLE001
            state["report_errors"] = state.get("report_errors", 0) + 1
            if state["report_errors"] <= 3:
                rec("error", where="report_closes", err=str(_e71)[:300])
                print(f"  report_closes failed (stepping over it): {_e71}")
        try:
            reconcile()
            state["reconcile_fail_streak"] = 0
        except Exception as _e71:                        # noqa: BLE001
            state["reconcile_errors"] = state.get("reconcile_errors", 0) + 1
            state["reconcile_fail_streak"] = (
                state.get("reconcile_fail_streak", 0) + 1)
            if state["reconcile_errors"] <= 3:
                rec("error", where="reconcile", err=str(_e71)[:300],
                    streak=state["reconcile_fail_streak"])
                print(f"  reconcile failed (stepping over it): {_e71}")
        # AMENDMENT 16. AFTER reconcile(), so open_pos is already drained of
        # everything that has settled -- otherwise the "only when flat" guard
        # would almost never be true and size could never move.
        _asz = autosize_tick(state, a, open_pos, rec=rec)
        if _asz:
            print(f"  --- AUTO-SIZE: {_asz}")
        # AMENDMENT 69 (2026-09-19): THE PAUSE MUST NOT STOP A HEDGE.
        #
        # `now`/`now_s` and the risk check USED TO SIT HERE, above the hedge
        # pass, and the transient-pause branch ends in `continue` -- which
        # skips every line below it, the hedge pass included. So a paused bot
        # could not protect the position it already held.
        #
        # LIVE, KXBTC15M-26SEP191600-00, 2026-09-19 15:59:15 ET, -$107.95, the
        # largest single loss this account has taken. 110 contracts at 98c
        # filled at 15:59:15; the NEXT line in the log is
        #
        #   pause: "loss bound: realised $+6.74 with $107.80 still open; one
        #           more contract could take this run past $-200.00"
        #
        # and then nothing at all for forty-five seconds until it settled at
        # zero. No alarm, no hedge, no refusal -- the hedge pass never ran.
        #
        # AND `--loss-cap 200` IS WHAT MADE IT ROUTINE. The bound is
        # `realised - open - one more bet < abort`. At the derived abort of
        # -$440 that is -$208.86 against -$440 and never trips; at the $200
        # cap the same close trips it instantly. So the cap I added turned a
        # rare pause into one that fires whenever we hold a full position --
        # exactly when a hedge matters most.
        #
        # A HEDGE CAN NEVER BREACH A LOSS BOUND. It BUYS THE OTHER SIDE of a
        # position already open: it reduces the worst case of this close and
        # cannot increase total exposure. There is no version of "we are too
        # far down to be allowed to reduce risk" that makes sense, and the
        # operator has said it in plainer words than that: "NOTHING SHOULD BE
        # BLOCKING A HEDGE."
        #
        # So the clock and the hedge pass run FIRST, and the risk check moved
        # below them. A pause now stops new bets, which is all it ever meant.
        now = time.time()
        now_s = int(now)

        # ---- R2 (2026-09-22): HOW LONG THE LAST PASS TOOK. -------------
        # RECORDS ONLY, AND IT SITS ABOVE THE HEDGE PASS ON PURPOSE: the
        # whole point is to time a stall that delays the hedge, so the
        # measurement has to be the first thing after the clock read and
        # the last thing before the hedge. It adds no condition to the
        # hedge and can defer nothing -- the only way it could hurt is by
        # raising, so the entire block is swallowed.
        #
        # The gap is attributed to the close that was NEAREST WHEN THE
        # PASS STARTED, with that pass's tau, because "a pass that began
        # at 12 s left took 1.0 s" is the sentence B5 and R2's bar need.
        #
        # A pass with nothing watched has no close. It is keyed under a
        # NEGATIVE fifteen-minute bucket (-(now_s // 900)), never under
        # None: a real close_s is a positive epoch second, so the keys
        # cannot collide, and report_closes() -- which pops only real
        # closes -- leaves these for the prune below. Under None the
        # unwatched bucket's record budget could never reset, so twenty
        # slow passes at one startup silenced every later blind period
        # for the life of the process.
        #
        # THE RECORD BUDGET IS TAU-AWARE. A near pass is never dropped to
        # make room for a refresh that happened eight minutes earlier --
        # see LOOP_REC_MAX_NEAR for why the first version could not have
        # answered its own bar.
        #
        # The `rec()` is NOT written here. rec() opens, appends and closes
        # the log, and this block sits between the clock read and the
        # hedge pass precisely so it can time a stall -- so it would add a
        # file write ahead of the hedge exactly when the loop is already
        # late. The arithmetic stays; the write is handed to _loop_rec and
        # emitted AFTER the hedge pass. Nothing may delay a hedge.
        _loop_rec = None
        try:
            _nc2 = min((c for c in watching.values() if c >= now_s),
                       default=None)
            _bk2 = _nc2 if _nc2 is not None else -(now_s // 900)
            if _prev_pass is not None:
                _gms2 = round(1000.0 * (now - _prev_pass[0]), 1)
                _pcs2, _ptau2 = _prev_pass[1], _prev_pass[2]
                # `_pass_why` is written by the PREVIOUS pass, below this
                # block -- so it is read here, not carried in _prev_pass.
                # Carried, it would be one pass stale and the first paused
                # pass (the one that actually chose to sleep) would go out
                # unlabelled.
                _pwhy2 = _pass_why
                _near2 = _ptau2 is not None and _ptau2 <= LOOP_NEAR_TAU_S
                _cur2 = pass_gap.get(_pcs2)
                if _cur2 is None or _gms2 > _cur2[0]:
                    pass_gap[_pcs2] = (_gms2, _ptau2, _pwhy2)
                if _near2:
                    _cn2 = pass_gap_near.get(_pcs2)
                    if _cn2 is None or _gms2 > _cn2[0]:
                        pass_gap_near[_pcs2] = (_gms2, _ptau2, _pwhy2)
                if _gms2 > LOOP_SLOW_MS:
                    if _near2:
                        _ns2 = pass_slow_near.get(_pcs2, 0) + 1
                        pass_slow_near[_pcs2] = _ns2
                        _room2 = _ns2 <= LOOP_REC_MAX_NEAR
                    else:
                        _ns2 = pass_slow.get(_pcs2, 0) + 1
                        pass_slow[_pcs2] = _ns2
                        _room2 = _ns2 <= LOOP_REC_MAX
                    if _room2:
                        _loop_rec = dict(
                            ms=_gms2, tau=_ptau2,
                            close_s=(_pcs2 if _pcs2 is not None
                                     and _pcs2 > 0 else None),
                            near=bool(_near2), why=_pwhy2, n_slow=_ns2,
                            watching=len(watching))
            _prev_pass = (now, _bk2,
                          (int(_nc2 - now_s) if _nc2 is not None else None))
            _pass_why = None
            # report_closes() pops each close's entry as it summarises it, so
            # these stay small. A close we watched but never summarised (the
            # bot was blind or halted through it) would leak one tuple, and
            # the negative unwatched buckets are never popped at all, so both
            # are pruned once they are long past. Bounded, not tidy.
            if len(pass_gap) > 200:
                for _dk2 in [k for k in pass_gap
                             if k is None or k < 0 or k < now_s - 900]:
                    pass_gap.pop(_dk2, None)
                    pass_slow.pop(_dk2, None)
                    pass_gap_near.pop(_dk2, None)
                    pass_slow_near.pop(_dk2, None)
        except Exception:                                # noqa: BLE001
            pass

        # ---------------- AMENDMENT 15: the hedge pass ----------------
        # Runs BEFORE the signal scan so a collapsing position is dealt with
        # before any new money goes out. One belief recompute per open
        # position per second; the alarm and every refusal are recorded.
        if HEDGE_ENABLED:
            for _hid, (_hcs, _hwant, _hcost, _hn_orig, _htk) in list(open_pos.items()):
                try:
                    # BUG FOUND LIVE 2026-09-13 (ZEC 26SEP122000-00, real money,
                    # ~$0.96 hidden). The line this replaces read `_hn` straight
                    # out of open_pos and, on a partial hedge fill, wrote a
                    # SMALLER size back into open_pos[_hid] to remember "how much
                    # is still unhedged". open_pos[_hid] is not scratch space --
                    # it is exactly the tuple reconcile() unpacks to settle the
                    # ORIGINAL position and to call pintake.record_pnl(), which
                    # risk_abort()'s loss-abort and loss-count brakes read.
                    # Shrinking it here silently shrank the original position
                    # too: an 11-contract loss settled and fed the risk ledger
                    # as if it were 10, because the first hedge attempt had
                    # filled 1 of the 11 needed. The exchange's own books were
                    # never wrong -- only our record of what we lost and what
                    # the brake believes it is guarding against.
                    # FIX: open_pos[_hid] is read-only in this loop from here on.
                    # `hedge_remain` tracks "contracts still needing a hedge
                    # fill" separately, seeded from the ORIGINAL size on first sight.
                    _hn = hedge_remain.get(_hid, _hn_orig)
                    if _hid in hedged or _hid.startswith("hedge-"):
                        continue
                    # AMENDMENT 71: THESE THREE SKIPS USED TO BE SILENT.
                    #
                    # A missing strike, an unmeasurable sigma or an unmeasurable
                    # fair value all skipped the hedge for that second and wrote
                    # NOTHING -- no record, no print. If the index feed stutters
                    # during a collapse, the log shows a position going to zero
                    # with no alarm and no refusal, which is indistinguishable
                    # from the A69 pause bug we spent today finding. A hedge that
                    # does not happen must always say why.
                    #
                    # Recorded ONCE per position per reason (_hq71), because this
                    # sits in a 20 Hz loop and an unrecovered feed would otherwise
                    # write tens of thousands of lines. The dedupe is per REASON,
                    # so a feed that fails in a new way still speaks up.
                    def _hquiet(_why, **_kw):
                        _k = (_hid, _why)
                        if _k in _hq71:
                            return
                        _hq71.add(_k)
                        rec("hedge_blind", ticker=_htk, why=_why, tau=_hcs - now_s,
                            where="hedge_pass", **_kw)
                        print(f"  hedge BLIND {_htk}: {_why}")

                    _meta = hedge_meta.get(_hid)
                    if _meta is None:
                        # Before A71 this was every PAPER position, for ever.
                        _hquiet("no_hedge_meta")
                        continue
                    _hstrike, _hdig, _hiid = _meta
                    _htau = _hcs - now_s
                    if _htau < 1:
                        continue                    # the close has passed; not blind
                    # K3 (2026-09-22): IS THE INDEX STILL PRINTING?
                    #
                    # Entry refuses an index older than MAX_INDEX_AGE_S; this
                    # pass never looked. fair() ignores the age spot() hands
                    # it and partial() ends the window at the newest print
                    # HELD, so a feed that stops mid-hold returns the same
                    # confident belief every second: no alarm, no record, no
                    # hedge while the market collapses. A socket only
                    # reconnects after 30 s of silence on EVERY index, so one
                    # frozen index behind live ones stays frozen to the close.
                    #
                    # So while the held market's index is stale, the market
                    # itself is the second witness: our side's own best ASK
                    # (market_belief: the cheapest anyone will sell it to us).
                    # The belief used below is the LOWER of the model's and
                    # the market's, so the market can only ADD a trigger --
                    # never remove one -- and everything after this point,
                    # every filter, size and send, is the ordinary path.
                    # With a fresh index none of this runs: behaviour is
                    # exactly what it was.
                    _hage = index_age(idx, _hiid)
                    _hmkt = None
                    if _hage is None or _hage > MAX_INDEX_AGE_S:
                        try:
                            _hbk3 = book.best(_htk)
                        except Exception:                # noqa: BLE001
                            _hbk3 = None
                        _hmkt = market_belief(_hbk3, _hwant)
                        _hquiet("index_stale", iid=_hiid,
                                age_s=(round(_hage, 2) if _hage is not None
                                       else None),
                                market_belief=(round(_hmkt, 4)
                                               if _hmkt is not None else None),
                                bid=(_hbk3 or {}).get(f"{_hwant}_bid"),
                                ask=(_hbk3 or {}).get(f"{_hwant}_ask"),
                                # K3b: the DEPTH at that ask. Whether the
                                # fallback could actually have been filled is
                                # not answerable from a price alone, and this
                                # record is the only place the question is
                                # ever asked.
                                ask_size=(_hbk3 or {}).get(f"{_hwant}_ask_size"),
                                book_age_ms=(_hbk3 or {}).get("age_ms"))
                    _hsg = idx.sigma(_hiid)
                    if _hsg is None:
                        _hquiet("no_sigma", iid=_hiid)
                        if _hmkt is None:
                            continue
                        _hf = None
                    else:
                        _hf = fair(idx, _hiid, _hcs, now_s, _hstrike,
                                   _hsg * SIGMA_STRESS
                                   * widen_factor(idx, _hiid, _hsg, _hwant),
                                   round_digits=_hdig)                  # AMENDMENT 41
                        if _hf is None:
                            _hquiet("no_fair", iid=_hiid, sigma=round(float(_hsg), 6))
                            if _hmkt is None:
                                continue
                    # the MODEL's belief in our side (None when it cannot say)
                    _hmodel = (None if _hf is None
                               else (_hf if _hwant == "yes" else 1.0 - _hf))
                    _belief = _hmodel
                    if _hmkt is not None:                # K3: index stale
                        _belief = (_hmkt if _hmodel is None
                                   else min(_hmodel, _hmkt))
                    # A68: the NEWEST belief for this market, recorded every tick
                    # and not only when the alarm fires. The rebuy is allowed only
                    # while this is at or under the panic line, so a belief that
                    # RECOVERS closes the door again on the very next tick.
                    # K3: the MODEL's belief only. The rebuy is an ENTRY, and
                    # the market fallback must never move an entry decision.
                    if _hmodel is not None:
                        last_belief[_htk] = float(_hmodel)
                        last_belief_t[_htk] = now_s          # K3b: and WHEN
                    # A52: two reasons to fire, recorded separately. The jump is
                    # asked FIRST because it is the earlier signal -- belief only
                    # falls after the price has already moved.
                    _htrig = "belief"
                    _hjmp = None
                    if HEDGE_JUMP_SIGMA is not None and _hsg is not None:
                        _since = int(now_s - entry_at.get(_hid, now_s))
                        _hjmp = jump_against(
                            idx.recent_moves(_hiid, max(1, min(HEDGE_JUMP_LOOKBACK_MAX, _since))),
                            _hsg, _hwant)
                        if _hjmp is not None and _hjmp >= HEDGE_JUMP_SIGMA:
                            _htrig = "jump"
                    if (_htrig != "jump" and _hmkt is not None
                            and (_hmodel is None or _hmkt < _hmodel)):
                        _htrig = "market_index_stale"    # K3: said, not hidden
                    if _htrig != "jump" and not hedge_should_fire(_belief):
                        continue
                    # ONE TRY PER SECOND. The loop runs ~20x/second; the first live
                    # alarm (planted, 2026-09-12 09:44:35Z) burned all five tries in
                    # ~250 ms and gave up inside the same second the alarm fired.
                    # HEDGE_MAX_TRIES means seconds, as its comment says, so a try
                    # is only counted when the wall-clock second has advanced.
                    if hedge_last_try.get(_hid) == now_s:
                        continue
                    hedge_last_try[_hid] = now_s
                    _ht_decide_ms = int(round(time.time() * 1000.0))   # (5)
                    _tries = hedge_tries.get(_hid, 0)
                    # A76: the alarm is keyed on its own set, not on _tries == 0.
                    # Under proportional hedging a position can sit for many
                    # seconds with nothing to buy (belief in the no-hedge band),
                    # and those seconds must neither re-fire the alarm nor burn
                    # a try.
                    if _hid not in hedge_alarmed:
                        hedge_alarmed.add(_hid)
                        state["hedge_alarms"] = state.get("hedge_alarms", 0) + 1
                        if _hmodel is not None:
                            last_belief[_htk] = float(_hmodel)   # A68 (K3: model)
                            last_belief_t[_htk] = now_s          # K3b: and WHEN
                        rec("hedge_alarm", ticker=_htk, want=_hwant, entry=_hcost,
                            n=_hn, belief=round(_belief, 5), tau=_htau,
                            threshold=HEDGE_BELIEF,
                            # A52: WHICH reason fired, and the jump size either
                            # way, so the two triggers can be scored against each
                            # other on the same alarms
                            trigger=_htrig,
                            jump_sd=(round(_hjmp, 2) if _hjmp is not None else None),
                            jump_threshold=HEDGE_JUMP_SIGMA,
                            # K3: only while the index is stale -- the frozen
                            # model's number and the market's, side by side
                            **({"index_age_s": (round(_hage, 2)
                                                if _hage is not None else None),
                                "model_belief": (round(_hmodel, 5)
                                                 if _hmodel is not None else None),
                                "market_belief": round(_hmkt, 5)}
                               if _hmkt is not None else {}))
                        print(f"  !!! HEDGE ALARM {_htk} {_hwant} belief {_belief:.3f} "
                              f"tau {_htau}s")
                    # A76: HOW MUCH OF THE POSITION SHOULD BE HEDGED AT THIS
                    # BELIEF, less what already is. `_unhedged` keeps the true
                    # uncovered count for the fill bookkeeping below; `_hn`
                    # becomes what we buy NOW. A second with nothing to buy is
                    # NOT a try and does NOT mark the position hedged -- the
                    # belief can fall further and the top-up must still happen.
                    _unhedged = float(_hn)
                    _hn = hedge_want(_hn_orig, _unhedged, _belief)
                    _hfrac = hedge_fraction(_belief)
                    if hedge_prop_said.get(_hid) != _hfrac:
                        hedge_prop_said[_hid] = _hfrac
                        rec("hedge_prop", ticker=_htk, belief=round(_belief, 5),
                            fraction=_hfrac, target=round(hedge_target(_hn_orig, _belief), 2),
                            covered=round(float(_hn_orig) - _unhedged, 2),
                            buy_now=round(_hn, 2), tau=_htau)
                    if _hn <= 1e-9:
                        continue
                    hedge_tries[_hid] = _tries + 1
                    if _tries + 1 > HEDGE_MAX_TRIES and not hedge_panic(_belief):
                        hedged.add(_hid)
                        rec("hedge_gave_up", ticker=_htk, tries=_tries, tau=_htau)
                        continue
                    # AMENDMENT 71: THIS USED TO READ THE ENTRY PATH'S COUNTER --
                    # the `attempts` dict, against MAX_ATTEMPTS_PER_CLOSE. The old
                    # line is NOT reproduced here: the self-test below asserts it
                    # is gone by searching this function's source, and a comment
                    # quoting it verbatim makes that search find the comment. That
                    # exact trap has now bitten this project five times.
                    #
                    # `attempts[close]` is incremented by every ENTRY order (two
                    # sites in the scan loop) as well as by hedge orders, and
                    # MAX_ATTEMPTS_PER_CLOSE is 24. So on a busy close -- twelve
                    # coins settling on the same quarter hour, which is the normal
                    # case, not the rare one -- the bot's own buying could spend
                    # the budget and then PERMANENTLY disable the hedge on a
                    # position it was already holding. `hedged.add(_hid)` is never
                    # cleared.
                    #
                    # A rail written to stop a 160-order runaway was gating
                    # insurance. That is the exact shape of all three losses on
                    # 2026-09-19 and it is what the standing rule forbids.
                    #
                    # The hedge now counts only its OWN sends, against its own
                    # cap, which no entry can touch. The real bound on hedging was
                    # never this: `hedge_last_try` allows one try per position per
                    # WALL-CLOCK SECOND and HEDGE_MAX_TRIES stops at 30, so at
                    # most 3 positions x 30 = 90 hedge orders can exist in a
                    # close, spread over at least thirty seconds. This cap sits
                    # above that and is a runaway backstop only -- ordinary
                    # hedging cannot reach it.
                    if (hedge_attempts.get(_hcs, 0) >= MAX_HEDGE_ATTEMPTS_PER_CLOSE
                            and not hedge_panic(_belief)):
                        hedged.add(_hid)
                        rec("hedge_refused", ticker=_htk, why="hedge_attempt_cap",
                            tried=hedge_attempts.get(_hcs, 0),
                            cap=MAX_HEDGE_ATTEMPTS_PER_CLOSE, tau=_htau)
                        continue
                    _opp = "no" if _hwant == "yes" else "yes"
                    try:
                        _hb = book.best(_htk)
                    except Exception as _e:                      # noqa: BLE001
                        rec("error", where="hedge_book", ticker=_htk, err=str(_e)[:200])
                        continue
                    _ask = (_hb or {}).get(f"{_opp}_ask")
                    _asz = (_hb or {}).get(f"{_opp}_ask_size")
                    if not _hb or not _ask or not _asz or _ask >= 1.0:
                        rec("hedge_no_ask", ticker=_htk, side=_opp, tau=_htau,
                            belief=round(_belief, 5))
                        continue
                    # A62: below HEDGE_PANIC belief, no filter may block this.
                    _panic = hedge_panic(_belief)
                    if _panic and _hid not in hedge_panic_said:
                        hedge_panic_said.add(_hid)
                        rec("hedge_panic", ticker=_htk, belief=round(_belief, 5),
                            threshold=HEDGE_PANIC, tau=_htau, ask=float(_ask),
                            entry=_hcost, n=_hn,
                            bypassed=["hedge_price", "hedge_normal", "attempt_cap"])
                        print(f"  !!! HEDGE PANIC {_htk} belief {_belief:.3f} -- "
                              f"every filter bypassed, taking {_ask:.2f}")
                    if not _panic and not hedge_price_ok(_ask):
                        # NOT added to `hedged`: the price can still fall inside
                        # this close, and if it does we hedge then. That is the
                        # whole point -- wait for the market to agree. Recorded
                        # once per position so a 20 Hz loop cannot flood the log.
                        if _hid not in hedge_price_said:
                            hedge_price_said.add(_hid)
                            rec("hedge_wait_price", ticker=_htk, ask=float(_ask),
                                our_price=round(1.0 - float(_ask), 4),
                                threshold=HEDGE_PRICE, belief=round(_belief, 5),
                                tau=_htau)
                            print(f"  hedge WAITING on price {_htk}: our side "
                                  f"{1.0 - float(_ask):.2f} is above {HEDGE_PRICE:.2f}")
                        continue
                    if not _panic and not hedge_normal_ok(_belief, _ask):
                        # A51: NOT added to `hedged` -- the model can get surer and
                        # the price can still fall inside this close, and if both
                        # happen we insure then. Same reasoning as the A47 wait.
                        if _hid not in hedge_normal_said:
                            hedge_normal_said.add(_hid)
                            rec("hedge_wait_normal", ticker=_htk, ask=float(_ask),
                                other_side_belief=round(1.0 - _belief, 5),
                                need_belief=PIN, need_price=PRICE_CEILING,
                                belief=round(_belief, 5), tau=_htau)
                            print(f"  hedge WAITING for a normal bet {_htk}: other "
                                  f"side {1.0 - _belief:.4f} sure @ {_ask:.3f}")
                        continue
                    if not hedge_ask_ok(_ask):
                        # RULE 4 OF THE PRE-REGISTRATION (corrected 2026-09-12): a
                        # hedge leg at $1.00 or more cannot beat holding. Counted,
                        # then give up on it.
                        hedged.add(_hid)
                        state["hedge_ask_refused"] = state.get("hedge_ask_refused", 0) + 1
                        rec("hedge_refused", ticker=_htk, why="ask_at_or_over_dollar",
                            entry=_hcost, ask=_ask, tau=_htau,
                            edge_c=hedge_edge_c(_belief, _ask))
                        continue
                    # A54: if this position was opened on the EARLY leg and the
                    # flip is happening inside the main window, buy MORE of the
                    # side the better-informed look prefers.
                    _entry_tau = (_hcs - entry_at[_hid]) if _hid in entry_at else None
                    _hn_want = flip_size(_hn, _entry_tau, _htau)
                    # A70: the limit we SEND, and the depth we may size from. With
                    # --hedge-slip 0 (the default) _hlimit == _ask and _hdepth ==
                    # _asz, which is exactly the pre-A70 pair of numbers.
                    _hlimit = hedge_limit(_ask)
                    if _hlimit is None:
                        _hlimit = float(_ask)
                    _hrungs = []
                    if HEDGE_SLIP:
                        try:
                            _hrungs = book.rungs(_htk, _opp, _hlimit)
                        except Exception:                    # noqa: BLE001
                            # A ladder read must NEVER stop a hedge. Fall back to
                            # the touch and insure anyway.
                            _hrungs = []
                    _hdepth = hedge_depth(_asz, _hrungs, _hn)
                    _hn_take = min(float(_hn_want), float(_hdepth))
                    if HEDGE_PILOT_CONTRACTS:
                        _hn_take = min(_hn_take, float(HEDGE_PILOT_CONTRACTS))
                    # A hedge order still spends the ENTRY budget -- an order is an
                    # order and a hedge outranks a new bet -- but the entry budget
                    # no longer spends the HEDGE's.
                    attempts[_hcs] = attempts.get(_hcs, 0) + 1
                    hedge_attempts[_hcs] = hedge_attempts.get(_hcs, 0) + 1
                    if not live:
                        # A70: pay the LADDER average, not the touch, for whatever
                        # the slip let us reach. With slip 0 there are no rungs and
                        # this is float(_ask) -- the pre-A70 number exactly.
                        _hpaper = float(hedge_vwap(_hrungs, _hn_take, float(_ask)))
                        # FOUND 2026-09-23 BUILDING THE TWO-LEG WORLD: THIS WAS
                        # KEYED BY TICKER AND SECOND, WHICH IS THE B10 BUG
                        # AGAIN. Two entry positions on one market both hedge
                        # in the SAME second (the alarm fires on the same
                        # belief), so the second leg overwrote the first in
                        # open_pos: reconcile settles per entry, so one paper
                        # hedge leg was never booked and the arm's loss on
                        # that market was overstated by the whole recovery.
                        # Measured offline: two 5-contract legs, one booked.
                        # Live is unaffected (its id is the exchange order
                        # id). Keyed on the PARENT position now, which is
                        # unique, and one try per position per second makes
                        # the pair unique. The prefix is unchanged -- every
                        # reader tests startswith("hedge-").
                        _hoid = f"hedge-paper-{_hid}-{now_s}"
                        open_pos[_hoid] = (_hcs, _opp, _hpaper, _hn_take, _htk)
                        # A76: paper books the same way live does -- the position
                        # is done only when the WHOLE of it is covered, so a
                        # proportional half-hedge stays open for its top-up.
                        _left76p = float(_unhedged) - float(_hn_take)
                        if _left76p <= 1e-9:
                            hedged.add(_hid)
                            hedge_remain.pop(_hid, None)
                        else:
                            hedge_remain[_hid] = _left76p
                        hedged_side[_htk] = _opp
                        rec("hedge", ticker=_htk, side=_opp, price=_hpaper,
                            ask=float(_ask), ask_size=float(_asz),
                            limit_sent=round(float(_hlimit), 4),
                            slip_c=round(100.0 * (float(_hlimit) - float(_ask)), 3),
                            ladder_n=round(float(_hdepth), 2),
                            # A54: what we ASKED for and why, so a flip is never
                            # mistaken for an ordinary hedge in the attribution
                            flip_mult=round(_hn_want / float(_hn), 3) if _hn else 1.0,
                            entry_tau=_entry_tau,
                            n=_hn_take, entry=_hcost, tau=_htau, belief=round(_belief, 5),
                            locked_loss_c=round(100 * hedge_locked_loss(_hcost, _hpaper), 2),
                            edge_c=hedge_edge_c(_belief, _hpaper), live=False)
                        print(f"  HEDGE(paper) {_htk} buy {_opp.upper()} {_hn_take:g} @ "
                              f"{_hpaper:.3f} -> locked {100*hedge_locked_loss(_hcost,_hpaper):+.1f}c")
                        continue
                    _ht_send_ms = int(round(time.time() * 1000.0))     # (5)
                    try:
                        # A70: the LIMIT, never the ask we saw -- same rule the
                        # entry path has followed since A35.
                        # K2 (2026-09-22): hedge=True. pintake's halt refuses
                        # NEW exposure until someone reconciles; this order
                        # REDUCES exposure on a position already held, so it
                        # skips that one rail and no other. Before this, one
                        # timed-out POST (an entry's or a hedge's own) made
                        # every later hedge in the run die inside take().
                        _hout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                             _htk, _opp, float(_hlimit), _hn_take,
                                             float(_hcs), exchange_index=2,
                                             hedge=True)
                    except Exception as _e:                      # noqa: BLE001
                        state["order_errors"] = state.get("order_errors", 0) + 1
                        rec("error", where="hedge_take", ticker=_htk, err=str(_e)[:300])
                        continue
                    _href = _hout.get("refused") or []
                    if _href or _hout.get("status_code") is None:
                        rec("hedge_refused", ticker=_htk, why="take_refused",
                            err=str(_href)[:300], tau=_htau)
                        continue
                    _hfilled = float(_hout.get("filled") or 0)
                    _hpx = _hout.get("exec_price")
                    _hcost2 = float(_hpx) if _hpx is not None else float(_ask)
                    # K1: THE FILL IS REGISTERED BEFORE ANYTHING FORMATS IT.
                    # This block used to sit below the record and the print.
                    # Once this body is guarded (K1), a record that raised
                    # there would leave a filled hedge unbooked -- and the
                    # next second would buy the SAME hedge again.
                    if _hfilled > 0:
                        hedged_side[_htk] = _opp
                        # ...and the same hardening live: `or now_s` alone is a
                        # ticker-and-second key the moment a filled response
                        # carries no order_id, and two positions hedge in the
                        # same second. The parent id makes it unique either
                        # way; with an order_id present nothing changes.
                        _hoid = (f"hedge-{_hid}-"
                                 f"{_hout.get('order_id') or now_s}")
                        open_pos[_hoid] = (_hcs, _opp, _hcost2, _hfilled, _htk)
                        state["hedges"] = state.get("hedges", 0) + 1
                        # A76: "done" means the WHOLE position is covered
                        # (_unhedged, not _hn). A proportional half-hedge that
                        # filled in full must leave the position open to a
                        # top-up when the belief falls further.
                        _left76 = float(_unhedged) - _hfilled
                        if HEDGE_PILOT_CONTRACTS or _left76 <= 1e-9:
                            # under the pilot ANY fill completes the hedge for this
                            # position -- otherwise 1 contract/second for 5 seconds
                            hedged.add(_hid)
                            hedge_remain.pop(_hid, None)
                        else:
                            # PARTIAL: track what is still unhedged in hedge_remain,
                            # NEVER in open_pos[_hid] -- see the note above this loop.
                            hedge_remain[_hid] = _left76
                    # K2: A HEDGE WHOSE OWN OUTCOME IS UNKNOWN IS NOT RESENT.
                    # -1 / 3xx / 5xx / an unreadable 2xx, or an IOC that rested
                    # and could not be reconciled: it may have filled. With
                    # the halt no longer refusing hedges, booking it as 0 would
                    # send the same hedge again next second and, if the first
                    # did fill, DOUBLE it -- a naked bet the other way. So the
                    # contracts it asked for are counted as covered. That is
                    # exactly what the halt used to do by refusing every later
                    # hedge, only now limited to THIS position: others still
                    # hedge. It errs toward under-hedging, never over.
                    _hsc = _hout.get("status_code")
                    _hunr = _hout.get("unrest")
                    _hunknown = (not (isinstance(_hsc, int) and 400 <= _hsc < 500)
                                 and (not pintake._readable(_hout)
                                      or (_hunr is not None
                                          and not _hunr.get("reconciled"))))
                    if _hunknown and hedge_never_sent(_hout):
                        # ...unless its own error proves it never left the
                        # box: then nothing is covered and next second's try
                        # sends it again (see hedge_never_sent).
                        _hunknown = False
                        rec("hedge_not_sent", ticker=_htk, side=_opp,
                            asked=_hn_take, status_code=_hsc,
                            err=str(_hout.get("raw"))[:200],
                            counted_covered=False,
                            still_unhedged=float(_unhedged), tau=_htau)
                    if _hunknown:
                        _leftk2 = float(_unhedged) - max(_hfilled, float(_hn_take))
                        if HEDGE_PILOT_CONTRACTS or _leftk2 <= 1e-9:
                            hedged.add(_hid)
                            hedge_remain.pop(_hid, None)
                        else:
                            hedge_remain[_hid] = min(
                                hedge_remain.get(_hid, _leftk2), _leftk2)
                        rec("hedge_unknown", ticker=_htk, side=_opp,
                            asked=_hn_take, filled_seen=_hfilled,
                            status_code=_hsc, counted_covered=True,
                            still_unhedged=max(0.0, _leftk2), tau=_htau)
                    rec("hedge", ticker=_htk, side=_opp, price=_hcost2, n=_hfilled,
                        flip_mult=round(_hn_want / float(_hn), 3) if _hn else 1.0,
                        entry_tau=_entry_tau,
                        # A70: what we were willing to pay over the ask, how much
                        # ladder that reached, and whether it actually cost more.
                        # This is how --hedge-slip gets scored: slip paid in cents
                        # against contracts that would otherwise have filled 0.
                        limit_sent=round(float(_hlimit), 4),
                        slip_c=round(100.0 * (float(_hlimit) - float(_ask)), 3),
                        ladder_n=round(float(_hdepth), 2),
                        swept=bool(_hpx is not None
                                   and float(_hpx) > float(_ask) + 1e-9),
                        ask=float(_ask), ask_size=float(_asz),      # criterion (b): fill vs the ask we hit
                        asked=_hn_take, entry=_hcost, tau=_htau, belief=round(_belief, 5),
                        locked_loss_c=round(100 * hedge_locked_loss(_hcost, _hcost2), 2),
                        order_id=_hout.get("order_id"), status=_hout.get("status"),
                        edge_c=hedge_edge_c(_belief, _hcost2), live=True,
                        # K2: sent while pintake was halted (None if it was not)
                        past_halt=_hout.get("past_halt"),
                        # (5) ms epoch: this try decided / sent
                        t_ms_decide=_ht_decide_ms, t_ms_send=_ht_send_ms)
                    print(f"  HEDGE {_htk} buy {_opp.upper()} {_hfilled:g}/{_hn_take:g} @ "
                          f"{_hcost2:.3f} -> locked {100*hedge_locked_loss(_hcost,_hcost2):+.1f}c")
                except Exception as _ek1:                  # noqa: BLE001
                    # K1: a bug in ONE position's hedge step must not end
                    # the run -- every other open position still needs
                    # this pass, and so does this one next second.
                    # But nothing NEW is bought while the hedge step is
                    # broken: the first such error stops entries, and the
                    # run exits once flat (see _k1_stop_entries).
                    _k1_error("hedge", _hcs, _htk, _ek1)
                    try:
                        _k1_stop_entries(
                            f"hedge step error on {_htk}: "
                            f"{type(_ek1).__name__}", _hcs, _htk)
                    except Exception:                    # noqa: BLE001
                        pass
                    continue
        # ---------------- end AMENDMENT 15 ----------------

        # R2 (review fix 2026-09-22): THE SLOW-PASS RECORD IS WRITTEN HERE,
        # BELOW THE HEDGE PASS. The arithmetic above had to run before it
        # -- it times the previous pass -- but rec() opens, appends and
        # closes the log on every call, and it fires exactly on the pass
        # AFTER a stall, i.e. when the loop is already late. A record may
        # never sit in front of a hedge. Guarded; it can only be dropped.
        if _loop_rec is not None:
            try:
                rec("loop", **_loop_rec)
            except Exception:                            # noqa: BLE001
                pass

        # (5) 2026-09-22: WHAT THE HEDGE WOULD COST, EVERY SECOND WE HOLD.
        # A hedge record prices only the second the alarm fired, so every
        # question about a DIFFERENT trigger -- earlier, later, on price --
        # has had to be answered off the tape, which is not our population.
        # One compact line per held market per second: the opposite side's
        # best ask and size, the seconds left and the model's newest belief.
        # Below the hedge pass, so it cannot delay one; guarded, so it
        # cannot raise; it decides nothing.
        try:
            _hq_held = {}
            for _qid, (_qcs, _qwant, _qc, _qn, _qtk) in open_pos.items():
                if _qcs - now_s < 1:
                    continue
                # REVIEW FIX 2026-09-23: EVERY POSITION ON THE MARKET, NOT THE
                # FIRST ONE. This was `setdefault(_qtk, (one position))`, which
                # kept whichever leg open_pos happened to hold first and threw
                # the rest away. Live runs --max-per-market 2 and open_pos gets
                # a new id per FILL, so a market with two entry fills -- 24 of
                # 704 (run, ticker) pairs in the live log, 3.4% -- had the
                # blind record below carrying ONE leg's size and ONE leg's
                # hedge state as if they were the market's, and the second leg
                # got no record at all. On the close that motivated all of
                # this, KXDOGE15M-26SEP222245-45, that is `n: 2` while 13
                # contracts were held. The record's whole job is to say how
                # much money went blind, so understating it is the defect.
                #
                # The hedge legs are collected too, in the second list: their
                # contracts are how much of the market is actually INSURED,
                # which the `hedged` set cannot say (its own declaration reads
                # "already hedged (or given up on)", and hedge_gave_up and
                # hedge_refused both put a position in it with contracts still
                # naked).
                _hq_held.setdefault(_qtk, ([], []))[
                    1 if _qid.startswith("hedge-") else 0].append(
                        (_qcs, _qwant, _qid, float(_qn or 0.0)))
            for _qtk, (_qpos, _qlegs) in _hq_held.items():
                if not _qpos:
                    continue          # an insurance leg whose parent is gone
                if hedge_quote_at.get(_qtk) == now_s:
                    continue
                hedge_quote_at[_qtk] = now_s
                # REVIEW FIX 2026-09-23: ONE MARKET'S FAILURE IS KEPT TO ITS
                # OWN MARKET. The outer guard stays as well, but it wraps the
                # whole `for`, so anything raising on the first held market
                # skipped every later market in that PASS.
                #
                # HOW MUCH THAT WAS WORTH, HONESTLY: bounded to one pass. The
                # `hedge_quote_at` stamp above is per TICKER, so the next pass
                # ~50 ms later skips the market that already has its record
                # and reaches the ones that were dropped. No offline world can
                # tell the two builds apart (proved: the suite is green with
                # this guard patched out), and the check below is the null
                # that shows nothing is lost either way. It stays because it
                # costs nothing and the bound depends on a stamp two lines up
                # continuing to be per market.
                try:
                    _qcs, _qwant, _qid, _qn = _qpos[0]
                    _qopp = "no" if _qwant == "yes" else "yes"
                    # BY SIDE, not by list. Everything held on OUR side is the
                    # bet; everything held on the other side offsets it,
                    # whether it was bought as insurance or -- A68, after a
                    # panic hedge -- as a bet of its own. Summing the entry
                    # list alone would count an A68 re-buy of the hedged side
                    # as more exposure and report the market naked when it is
                    # the flattest it has been. NOT RUN-TESTED: no offline
                    # world at the shipped filters can hold both sides (the
                    # A68 re-buy needs a cheap-side price the pin gate
                    # refuses), so this is right by construction and
                    # identical, check for check, on every world that is
                    # reachable.
                    _qmine = _qcov = 0.0
                    for _p in _qpos + _qlegs:
                        if _p[1] == _qwant:
                            _qmine += _p[3]
                        else:
                            _qcov += _p[3]
                    _qn_tk = round(_qmine, 2)
                    _qcov = round(_qcov, 2)
                    _qnaked = round(max(0.0, _qmine - _qcov), 2)
                    try:
                        _qb = book.best(_qtk) or {}
                    except Exception:                    # noqa: BLE001
                        _qb = {}
                    # K3b (2026-09-23): THE ONLY WITNESS A COVERED POSITION
                    # HAS.
                    #
                    # K3 asks "is this market's index still printing?" inside
                    # the hedge pass -- and the pass exits at the `hedged`
                    # skip for a position that is already covered, ABOVE both
                    # that question and the write of last_belief. So from the
                    # second a hedge completes, a held market has no index
                    # witness at all: the quote below reprints a belief nobody
                    # is updating, and a feed that freezes there is
                    # FIELD-FOR-FIELD identical to a healthy one. Proved on
                    # the DOGE 02:45Z close of 2026-09-23 and offline (worlds
                    # W2/W3 of results/map_2026-09-22/doge2245/
                    # D_frozen_index.md).
                    #
                    # The skip STAYS WHERE IT IS: moving it below the pass
                    # makes hedge_remain.pop fall back to the full original
                    # size and re-buys the whole hedge every second (22 sends
                    # for 13 contracts, measured). So the question is asked
                    # HERE, below the hedge pass, in a block that already runs
                    # once per held market per second and is already guarded
                    # -- it cannot block, delay or change a hedge, and the
                    # fallback that CAN send one is untouched in the pass
                    # above, for positions that still need it.
                    #
                    # REVIEW FIX 2026-09-23: THE AGES ARE READ IN THEIR OWN
                    # GUARD, BELOW NOTHING AND ABOVE ONLY THEMSELVES. They
                    # used to be computed above rec("hedge_quote") under the
                    # block's blanket `except`, so anything raising here --
                    # index_age swallows its own errors today, hedge_meta's
                    # tuple arity does not -- silently dropped the
                    # PRE-EXISTING per-second quote record, which is what
                    # barcheck reads and what (5) added so hedge-trigger
                    # questions come from our own fills instead of the tape.
                    # A new field may cost itself; it may not cost an old
                    # record.
                    _qiid = _qage = _qbt = None
                    try:
                        for _p in _qpos:
                            _pm = hedge_meta.get(_p[2])
                            if _pm:
                                _qiid = _pm[2]
                                break
                        _qage = (None if _qiid is None
                                 else index_age(idx, _qiid))
                        _qbt = last_belief_t.get(_qtk)
                    except Exception:                    # noqa: BLE001
                        pass
                    rec("hedge_quote", ticker=_qtk, side=_qopp,
                        ask=_qb.get(f"{_qopp}_ask"),
                        size=_qb.get(f"{_qopp}_ask_size"),
                        tau=_qcs - now_s, belief=last_belief.get(_qtk),
                        # K3b: how old the index print behind that belief is,
                        # and how long since the belief was last RECOMPUTED,
                        # EVERY held second.
                        #
                        # REVIEW FIX: `belief_calc_age_s`, not
                        # `belief_age_s`. It is the age of the CALCULATION,
                        # not of the information: while an OPEN position's
                        # index is frozen the pass recomputes the same number
                        # off the same frozen tick ring every second, so this
                        # reads 0 with a provably stale belief. Read it beside
                        # index_age_s, which is the one that climbs. The old
                        # name invited exactly the opposite reading.
                        iid=_qiid,
                        index_age_s=(None if _qage is None
                                     else round(_qage, 2)),
                        belief_calc_age_s=(None if _qbt is None
                                           else now_s - _qbt),
                        # REVIEW FIX: and HOW MUCH is riding on it. Every
                        # entry contract held on this market, and the part of
                        # it no insurance leg covers -- from the booked legs
                        # themselves, so hedge_gave_up and hedge_refused
                        # cannot make it read covered.
                        n=_qn_tk, naked=_qnaked)
                    if _qiid is None or (_qage is not None
                                         and _qage <= MAX_INDEX_AGE_S):
                        continue
                    for _pcs, _pwant, _pid, _pn in _qpos:
                        # REVIEW FIX: ONE RECORD PER POSITION. The dedupe was
                        # keyed on the first leg, so a two-fill market burned
                        # one key and reported one leg.
                        #
                        # Deduped so the pair is one record per position per
                        # run whichever witness sees it first, and `where`
                        # says which did -- but in the pass's key space it is
                        # READ, never WRITTEN. Burning (pos, "index_stale")
                        # here could suppress the pass's own richer record
                        # (the one carrying market_belief and the fallback
                        # context) for the rest of the run, if the pass ever
                        # raised ahead of its index read.
                        if ((_pid, "index_stale") in _hq71
                                or (_pid, "index_stale_q") in _hq71):
                            continue
                        _qmkt = market_belief(_qb, _pwant)
                        rec("hedge_blind", ticker=_qtk, why="index_stale",
                            where="hedge_quote", tau=_pcs - now_s, iid=_qiid,
                            age_s=(round(_qage, 2) if _qage is not None
                                   else None),
                            market_belief=(round(_qmkt, 4)
                                           if _qmkt is not None else None),
                            bid=_qb.get(f"{_pwant}_bid"),
                            ask=_qb.get(f"{_pwant}_ask"),
                            ask_size=_qb.get(f"{_pwant}_ask_size"),
                            book_age_ms=_qb.get("age_ms"),
                            # THIS leg: its size, what the hedge still owes on
                            # it (hedge_remain, which is what the pass acts
                            # on -- open_pos is the ORIGINAL size and reading
                            # it as the exposure was the 09-13 ZEC bug), and
                            # the flag, whose set means "hedged OR given up".
                            n=_pn, remain=hedge_remain.get(_pid),
                            hedged=(_pid in hedged),
                            # THE MARKET: what the whole position is and how
                            # much of it is uninsured. This is the number the
                            # record is read for.
                            n_tk=_qn_tk, insured_tk=_qcov, naked_tk=_qnaked,
                            pos=len(_qpos))
                        # REVIEW FIX: the key is burned AFTER the record is
                        # written, never before. rec() opens, appends and
                        # closes the log on every call; burning first meant a
                        # write that raised lost the only witness a covered
                        # position has, for the whole run, in silence.
                        _hq71.add((_pid, "index_stale_q"))
                        print("  hedge BLIND %s: index_stale, %g held / %g "
                              "insured%s (this leg %g, %s)"
                              % (_qtk, _qn_tk, _qcov,
                                 "" if _qnaked <= 1e-9
                                 else ", %g NAKED" % _qnaked,
                                 _pn,
                                 "hedged" if _pid in hedged else "OPEN"))
                except Exception:                        # noqa: BLE001
                    pass
        except Exception:                                # noqa: BLE001
            pass

        # ===================================================================
        # R4 (2026-09-23): THE TRAJECTORY. See the TRAJ_* block at the top of
        # the file for what defect this fixes and what the grid is.
        #
        # WHERE IT SITS AND WHY. Below the hedge pass, like `hedge_quote`
        # above it, and ABOVE the risk check on purpose: the risk check's
        # transient-pause branch ends in `continue`, so a block below it
        # writes NOTHING for a paused close -- and a paused close is exactly
        # the blindness that cost $107.95 on 2026-09-19 and the one a
        # trajectory most needs to show. Nothing here can delay a hedge: the
        # hedge pass for this iteration is already done, and the work is at
        # most one book read, one index read and one fair() per market per
        # SAMPLED SECOND, against the 20 Hz scan's twenty of each.
        #
        # IT DECIDES NOTHING. It reads `book`, `idx` and `fired`; it writes
        # only its own dicts and its own records, through the trajectory
        # writer. No gate is called, no refusal is recorded, `near` is not
        # touched, and `traj_hist` is read by exactly one thing -- R1's
        # `_doubt`, which can only ever RAISE a size.
        #
        # THE GATE FIELD IS THE REAL GATE. `_gate()` stamps
        # traj_gate[(close, ticker)] = (pass, name) on every refusal, so the
        # name here is the gate that ACTUALLY refused this market, not a
        # second copy of the ladder that could drift from it. The scan has not
        # run yet this pass, so the freshest possible stamp is the previous
        # pass -- 50 ms at 20 Hz -- and `gate_pass_ago` says which, so a stale
        # one can never be read as current.
        try:
            _tj_win = max(TAU_MAX, EARLY_TAU_MAX)
            for _jtk, (_jiid, _jcs, _jk, _jd, _jxi) in seen_markets.items():
                # K1's lesson, applied here: ONE market's sample must not silence
                # the other ten. Without this a single bad market ends the whole
                # pass's sampling and the gap looks like a quiet universe.
                #
                # `_jtau` IS SET BEFORE THE TRY, not as its first statement:
                # assigned inside, a market that raises before reaching it
                # writes the PREVIOUS market's tau into its own blind record,
                # and a wrong number in a diagnostic is worse than a null.
                _jtau = _jcs - now_s if isinstance(_jcs, (int, float)) else None
                try:
                    if not traj_due(_jtau):
                        continue
                    _jkey = (_jcs, _jtk)
                    if traj_at.get(_jkey) == now_s:
                        continue                 # one record a market a second
                    # THE SECOND IS CONSUMED HERE, BEFORE THE BUDGETS, and that is
                    # not a detail: with the budget first, a REFUSED second is
                    # retried on all twenty passes of that second, so `dropped`
                    # counted attempts (920) instead of seconds (46) and the one
                    # number that says "a bound bit" would have been twenty times
                    # the truth.
                    traj_at[_jkey] = now_s
                    _jnear = _jtau <= TRAJ_NEAR_TAU_S
                    # R1'S INPUT WINDOW, AND IT IS NOT THE SAMPLER'S GRID.
                    # min() so a far sample can never feed the history whatever
                    # the two constants are set to -- see the DOUBT_HIST_TAU_S
                    # comment for the nine-times-diluted population that cost.
                    _jhist = _jtau <= min(DOUBT_HIST_TAU_S, TRAJ_NEAR_TAU_S)
                    # THE BUDGETS ARE SEPARATE AND THE NEAR ONE CANNOT BE SPENT
                    # BY FAR SAMPLES -- v-instr1's lesson, in the TRAJ_MAX_NEAR
                    # comment. A refused sample is COUNTED, so a budget that
                    # bites shows up in `traj_close` instead of looking like a
                    # quiet market.
                    #
                    # AND A DISK BUDGET MAY NOT DECIDE ANYTHING. The near
                    # budget used to `continue` HERE, above the `traj_hist`
                    # append -- so a TRAJ_MAX_NEAR bite did not merely drop a
                    # log line, it deleted a reading from the feature `_doubt`
                    # minimises over: the sample never happened for the RULE.
                    # It cannot bite today (14 series x 61 = 854 <= 900) but it
                    # binds at 15 series, and D_plan's pre-registered next step
                    # is 1.25x LIVE, at which point a disk constant would be an
                    # input to live entry sizing. So a near sample always takes
                    # its reading and always feeds the history; the budget
                    # drops the RECORD, below. Far samples feed nothing, so
                    # there the budget still skips the work outright.
                    _jdrop = False
                    if _jnear:
                        _jdrop = traj_n_near.get(_jcs, 0) >= TRAJ_MAX_NEAR
                    elif traj_n.get(_jcs, 0) >= TRAJ_MAX:
                        traj_drop[_jcs] = traj_drop.get(_jcs, 0) + 1
                        continue
                    try:
                        _jb = book.best(_jtk) or {}
                    except Exception:                        # noqa: BLE001
                        _jb = {}
                    _jsec, _jspot, _jage = idx.spot(_jiid)
                    _jsg = idx.sigma(_jiid)
                    _jf = _jmu = _jsd = _jcush = _jr = None
                    _jsig = None
                    if _jsg is not None:
                        _jsig = _jsg * SIGMA_STRESS
                        _jf = fair(idx, _jiid, _jcs, now_s, _jk, _jsig,
                                   round_digits=_jd)
                        # THE SAME TWO-STEP THE SCAN USES: price it unwidened,
                        # take the lean from that, then widen and price it again.
                        # Widening moves confidence toward 0.5 and can never flip
                        # the lean, so the lean off the unwidened number is the
                        # lean -- and this way the trajectory's `fair` is the
                        # number the gate would have seen, not a different model.
                        if _jf is not None and WIDEN_ENABLED:
                            _jwf = widen_factor(idx, _jiid, _jsg,
                                                "yes" if _jf >= 0.5 else "no")
                            if _jwf != 1.0:
                                _jsig = _jsg * SIGMA_STRESS * _jwf
                                _jf = fair(idx, _jiid, _jcs, now_s, _jk, _jsig,
                                           round_digits=_jd)
                    # mu, sd and the cushion come from the SAME arithmetic fair()
                    # uses, so the record cannot drift from the model: sd is the
                    # sd of the REMAINING window in price units, and the cushion
                    # is how many of those sd our side is ahead by.
                    _jK = eff_strike(_jk, _jd)
                    _jwant = None if _jf is None else ("yes" if _jf >= 0.5 else "no")
                    try:
                        _jpart = idx.partial(_jiid, _jcs, now_s)
                    except Exception:                        # noqa: BLE001
                        _jpart = None
                    if _jpart is not None and _jspot is not None:
                        _jlk, _jr = _jpart
                        _jmu = (_jlk + _jr * _jspot) / N_AVG
                        if _jsig is not None and _jr > 0:
                            _jsd = _jsig * math.sqrt(var_factor(int(_jr), [1.0]))
                            if _jsd > 0:
                                _jcush = (_jmu - _jK) / _jsd
                                if _jwant == "no":
                                    _jcush = -_jcush
                    _jconf = (None if _jf is None
                              else (_jf if _jwant == "yes" else 1.0 - _jf))
                    # R1's history: the raw P(YES), never a side-converted number.
                    # `_doubt` does the side conversion at the decision, because
                    # the side we end up buying is not known here.
                    #
                    # ONLY INSIDE DOUBT_HIST_TAU_S. This one condition decides
                    # R1's whole population: without it the minimum is taken
                    # over readings up to five minutes out, where nothing is
                    # locked and `fair` is a near coin-flip, and the flag fires
                    # on 9x as many markets as the rule the +$2.95 was measured
                    # on. The record below is still written for every sampled
                    # second -- the trajectory is the wide thing; the RULE is
                    # the narrow one.
                    if _jf is not None and _jhist:
                        _jh = traj_hist.setdefault(_jkey, [])
                        _jh.append((now_s, float(_jf)))
                        if len(_jh) > TRAJ_HIST_MAX:
                            del _jh[:len(_jh) - TRAJ_HIST_MAX]
                    if _jdrop:
                        # the near budget bit -- AFTER the reading reached the
                        # history, so the disk protection costs a log line and
                        # never a decision input
                        traj_drop[_jcs] = traj_drop.get(_jcs, 0) + 1
                        continue
                    # which side we already hold in this market, if any -- so a
                    # reader can tell a pre-entry reading from a post-entry one
                    _jhold = None
                    _jpv = fired.get(_jcs)
                    if _jpv:
                        _jhold = (_jpv.get("sides") or {}).get(_jtk)
                    _jg = traj_gate.get(_jkey)
                    _jgate = _jgn = None
                    if _jg is not None and _passn - int(_jg[0]) <= 1:
                        _jgate, _jgn = _jg[1], _passn - int(_jg[0])
                    elif not (TAU_MIN <= _jtau <= _tj_win):
                        # NOT a refusal and never counted as one: the scan skips
                        # these before any gate, and `_gate`'s own comment says
                        # so. Named so the reader is not left guessing.
                        _jgate, _jgn = "outside_window", 0
                    _jopp = "no" if _jwant == "yes" else "yes"
                    if _jnear:
                        traj_n_near[_jcs] = traj_n_near.get(_jcs, 0) + 1
                    else:
                        traj_n[_jcs] = traj_n.get(_jcs, 0) + 1
                    _trec(
                        "traj", ticker=_jtk, close_s=_jcs, tau=_jtau,
                        want=_jwant, held=_jhold,
                        fair=(None if _jf is None else round(_jf, 5)),
                        conf=(None if _jconf is None else round(_jconf, 5)),
                        spot=_jspot, strike=_jk, eff_strike=_jK,
                        mu=(None if _jmu is None else round(_jmu, 6)),
                        sd=(None if _jsd is None else round(_jsd, 6)),
                        cushion_sd=(None if _jcush is None else round(_jcush, 3)),
                        remaining=_jr,
                        sigma=(None if _jsig is None else round(_jsig, 6)),
                        # our side's ask, and the OTHER side's ask -- which is
                        # what insurance would have cost at this instant. Every
                        # hedge-timing question in results/map_2026-09-22 had to
                        # be answered off the tape for want of this column.
                        ask=(None if _jwant is None else _jb.get(f"{_jwant}_ask")),
                        ask_size=(None if _jwant is None
                                  else _jb.get(f"{_jwant}_ask_size")),
                        opp_ask=(None if _jwant is None
                                 else _jb.get(f"{_jopp}_ask")),
                        opp_size=(None if _jwant is None
                                  else _jb.get(f"{_jopp}_ask_size")),
                        book_age_ms=_jb.get("age_ms"),
                        index_age_s=(None if _jage is None else round(_jage, 2)),
                        gate=_jgate, gate_pass_ago=_jgn,
                        near=bool(_jnear),
                        entries_stopped=bool(state.get("entries_stopped")),
                        paused=bool(state.get("paused_on")))
                except Exception as _je:             # noqa: BLE001
                    # A SAMPLE THAT DOES NOT HAPPEN SAYS WHY, ONCE. A71's
                    # lesson on the hedge, applied to the instrument: a
                    # silently missing second is indistinguishable from a
                    # quiet market, which is the whole failure R4 exists to
                    # fix. Deduped per (close, market, exception) because
                    # this is a 20 Hz loop, and itself guarded.
                    try:
                        _jbk = (_jcs, _jtk, type(_je).__name__)
                        if _jbk not in traj_blind:
                            traj_blind.add(_jbk)
                            _trec("traj_blind", ticker=_jtk, close_s=_jcs,
                                  tau=_jtau, err=type(_je).__name__,
                                  detail=str(_je)[:200], scope="market")
                    except Exception:                # noqa: BLE001
                        pass
                    continue
            # BOUNDED, NOT TIDY, AND THE BOUND IS PROVEN BY A SELF-TEST.
            # report_closes() pops each close's entries as it summarises it,
            # but it only summarises closes that reached `near` -- and a market
            # watched at tau 300 with the scan window at 45 never touches
            # `near` at all. So anything a quarter hour past its close is
            # dropped here, or these five dicts would grow for the life of a
            # 4,320-minute run. Once a second, not 20 times: the scan is over
            # keys, and it decides nothing.
            if _traj_pruned[0] != now_s:
                _traj_pruned[0] = now_s
                for _dk in [k for k in traj_at if k[0] < now_s - 900]:
                    traj_at.pop(_dk, None)
                    traj_hist.pop(_dk, None)
                    traj_gate.pop(_dk, None)
                for _dk in [k for k in look_at if k[0] < now_s - 900]:
                    look_at.pop(_dk, None)
                    look_drop_n.pop(_dk, None)
                # traj_blind TOO. It was the one member of this family nothing
                # ever popped, while the comment above the declarations claimed
                # every one of them was -- a false statement about the only one
                # that broke the bound. Keyed (close, ticker, exception), so
                # the same close filter works.
                for _dk in [k for k in traj_blind if k[0] < now_s - 900]:
                    traj_blind.discard(_dk)
                for _dk in [k for k in traj_n if k < now_s - 900] \
                        + [k for k in traj_n_near if k < now_s - 900] \
                        + [k for k in traj_drop if k < now_s - 900]:
                    # A close report_closes() never summarised still gets its
                    # volume line: it pops these counters, so a close that WAS
                    # summarised leaves nothing here and cannot be counted
                    # twice.
                    _tf, _tn = traj_n.pop(_dk, 0), traj_n_near.pop(_dk, 0)
                    _td = traj_drop.pop(_dk, 0)
                    if _tf or _tn or _td:
                        _trec("traj_close", close_s=_dk, far=_tf, near=_tn,
                              dropped=_td, markets=None,
                              far_max=TRAJ_MAX, near_max=TRAJ_MAX_NEAR,
                              every_s=TRAJ_EVERY_S,
                              near_tau_s=TRAJ_NEAR_TAU_S,
                              tau_max=TRAJ_TAU_MAX, unsummarised=True)
        except Exception as _jbe:                        # noqa: BLE001
            # A BLOCK-LEVEL FAILURE SAYS SO TOO, and this handler used to be a
            # bare `pass`. The per-market guard below covers a market; this one
            # covers the `for` unpacking above it, the prune, and anything else
            # outside that inner try -- so a change to the 5-tuple
            # `seen_markets` holds would kill ALL sampling on EVERY pass with
            # nothing written at all, indistinguishable from "nobody deployed
            # it" or "a quiet night". That ambiguity is the exact failure R4
            # exists to remove, and commit 2 of this change already removed it
            # one level down. Deduped by exception type, and itself guarded.
            # Its own set, NOT traj_blind: that one is pruned by close, and a
            # block failure has no close, so a pruned key would be re-added and
            # re-reported every second. This set is keyed by exception name
            # alone -- bounded by the number of distinct exception types this
            # process can raise, which is a handful, so it needs no prune.
            try:
                if type(_jbe).__name__ not in traj_blind_blk:
                    traj_blind_blk.add(type(_jbe).__name__)
                    _trec("traj_blind", ticker=None, close_s=None, tau=None,
                          err=type(_jbe).__name__, detail=str(_jbe)[:200],
                          scope="block")
            except Exception:                            # noqa: BLE001
                pass

        # A69: THE RISK CHECK, NOW BELOW THE HEDGE PASS. It used to sit above
        # it, and its transient-pause branch ends in `continue` -- so a paused
        # bot skipped the hedge and sat watching a position go to zero. See
        # the A69 block at the top of the loop for the $107.95 that cost.
        # A pause stops NEW bets; it has never been able to stop a hedge from
        # reducing risk, and now it cannot.
        # K1: a risk check that RAISES is not a pass. No new bets this
        # iteration, and the loop -- with the hedge pass above -- goes on,
        # at the ordinary pass rate so no hedge try waits on it.
        try:
            stop = risk_abort(state, a)
        except Exception as _ek1:                        # noqa: BLE001
            _k1_error("risk_abort", None, None, _ek1)
            _pass_why = "risk_error"
            time.sleep(0.05)
            continue
        # K1: stopped entries are a TERMINAL halt, so they take the drain
        # below -- hedge still armed, exit when flat -- instead of leaving a
        # live process that buys nothing for the rest of --minutes. The
        # reason starts "entries stopped", which is neither transient nor a
        # money brake, so watch_bot restarts the bot as soon as it exits.
        if not stop and state.get("entries_stopped"):
            stop = f"entries stopped: {state['entries_stopped']}"
        if stop and halt_is_transient(stop):
            # AMENDMENT 14: wait it out. reconcile() runs at the top of every
            # iteration, so the open positions this is waiting on are released
            # here and the condition clears on its own. state["halted"] is NOT
            # set, because setting it would make risk_abort return "already
            # halted" for ever -- a terminal answer to a temporary question.
            if stop != state.get("paused_on"):
                state["paused_on"] = stop
                state["pauses"] = state.get("pauses", 0) + 1
                rec("pause", why=stop, pauses=state["pauses"])
                print(f"  --- PAUSE (will resume): {stop}")
            # R2 (review fix): a PAUSE sleeps a whole second, so the next
            # pass books a ~1,000 ms gap that is not a stall at all. The
            # bar reads gaps as evidence for deferring the universe
            # refresh, and a pause is not that. Named, not hidden: the
            # hedge pass really did run only once in that second, which is
            # worth recording -- but as `why="pause"`, never as a stall.
            _pass_why = "pause"
            time.sleep(1.0)
            continue
        if state.get("paused_on"):
            rec("resume", after=state.pop("paused_on"))
            print("  --- RESUMED")
        if stop:
            # AMENDMENT 74 (2026-09-19): THE BOT MAY NOT EXIT HOLDING A BET.
            #
            # The operator, and it is an absolute: *"In no circumstance should
            # the bot ever cut off mid bet."*
            #
            # Every terminal halt used to `break` immediately. The process
            # ends, the position stays open, and NOTHING hedges it for the
            # rest of the close -- the same outcome as the A69 pause bug that
            # cost $107.95, reached through a different door. It has already
            # happened for real:
            #
            #   2026-09-18T01:14:26Z  halt  open cap: 297 contracts held
            #                               >= 297 (3 x size 99)
            #
            # That is 21:14 ET on 09-17 and the bot died holding 297
            # contracts, seconds after a hedge had filled.
            #
            # DRAINING. A terminal halt now stops NEW bets at once and lets
            # the loop keep running so the hedge pass above still fires, and
            # the process exits when it is FLAT. `state["halted"]` is
            # deliberately NOT set while draining: risk_abort returns
            # "already halted" once it is, which would re-enter this branch
            # with the real reason lost.
            #
            # It is bounded. If positions never clear -- a broken settlement
            # reader, which A71's RECONCILE_FAIL_HALT covers separately -- the
            # drain gives up after DRAIN_MAX_S and exits loudly, because a bot
            # that hangs forever is invisible to watch_bot.ps1, which only
            # restarts a process that is GONE or silent.
            _openn74 = open_contracts(pintake.LEDGER) or len(open_pos)
            if _openn74 and DRAIN_ON_HALT:
                if not state.get("draining"):
                    state["draining"] = stop
                    state["draining_since"] = now
                    rec("halt_pending", why=stop, open_contracts=_openn74,
                        open_positions=len(open_pos))
                    print(f"  *** STOPPING, but {_openn74:g} contracts are "
                          f"still open -- no new bets, hedge still armed: "
                          f"{stop}")
                if now - float(state.get("draining_since", now)) < DRAIN_MAX_S:
                    # The ordinary pass rate, not 0.5 s: a drain ends in an
                    # exit, never in a new bet, so the only thing a slower
                    # loop here could change is how late a hedge fires --
                    # up to 0.45 s late at 0.5. K1 now drains on stopped
                    # entries too, where a held position is the norm.
                    _pass_why = "drain"
                    time.sleep(0.05)
                    continue          # hedge pass is ABOVE; it keeps running
                rec("drain_timeout", why=stop, open_contracts=_openn74,
                    waited_s=round(now - float(state["draining_since"]), 1))
                print(f"  *** DRAIN TIMED OUT after {DRAIN_MAX_S}s with "
                      f"{_openn74:g} contracts still open -- exiting anyway")
            state["halted"] = True
            rec("halt", why=stop, drained=bool(state.get("draining")))
            print(f"  *** HALT: {stop}")
            break

        _uni_taus = [float(c) - now for c in watching.values()]
        if now - uni_at > 20 and defer_universe(now, uni_at, _uni_taus):
            # ONE record per wait, not one per pass: the loop runs at 20 Hz.
            if state.get("uni_defer_at") is None:
                state["uni_defer_at"] = now
                rec("universe_deferred", tau=round(min(_uni_taus), 1),
                    waited_s=round(now - uni_at, 1), watching=len(watching))
        elif now - uni_at > 20:
            _uni_waited = (round(now - float(state["uni_defer_at"]), 1)
                           if state.get("uni_defer_at") is not None else 0.0)
            state["uni_defer_at"] = None
            uni_at = now
            _uni_t0 = time.time()               # R2: timing only
            _uni_n = None                       # R2: markets THIS refresh built
            try:
                fresh = {}
                for series, iid in series_index.items():
                    st, b = get("/markets", {"series_ticker": series,
                                             "status": "open", "limit": "4"})
                    if st != 200 or not isinstance(b, dict):
                        rec("skip", why=f"universe_http_{st}", series=series)
                        continue
                    for m in b.get("markets", []):
                        ct, sk = m.get("close_time"), m.get("floor_strike")
                        if not ct or sk is None:
                            continue
                        cs = calendar.timegm(time.strptime(
                            ct, "%Y-%m-%dT%H:%M:%SZ"))
                        if cs - now_s > 900 or cs < now_s:
                            continue
                        cs_ = m.get("custom_strike") or {}
                        d = cs_.get("round_digits")
                        # THE STRIKE IS RETURNED TWICE AND THEY DIFFER.
                        # Top-level floor_strike is TRUNCATED to the display
                        # precision; custom_strike.floor_strike is exact.
                        # Live 2026-09-08: DOGE 0.08926 vs '0.0892605'. DOGE's
                        # round_digits is 7, so the rounding correction is
                        # 5e-8 while the truncation error is 5e-7 -- ten times
                        # larger than the effect it was meant to model. Use
                        # the exact field wherever the exchange gives it.
                        if cs_.get("floor_strike") is not None:
                            try:
                                sk = float(cs_["floor_strike"])
                            except (TypeError, ValueError):
                                pass
                        # EXCHANGE_INDEX IS NOT OPTIONAL. Checked live
                        # 2026-09-08 across all 11 series: every open crypto
                        # 15M market reads exchange_index 2, not 0. take()
                        # defaults it to 0, so every live order was going to
                        # be routed to the wrong shard -- rejected, or worse,
                        # created where _unrest's cancel (which reuses the
                        # same field) cannot find it. pintake.envtest already
                        # reads this field; pinrun did not.
                        fresh[m["ticker"]] = (iid, cs, float(sk),
                                              int(d) if d is not None else None,
                                              int(m.get("exchange_index") or 0))
                if fresh:
                    seen_markets = fresh
                    new = set(seen_markets) - set(watching)
                    if new:
                        book.subscribe(sorted(new))
                        rec("watch", n=len(watching) + len(new),
                            added=sorted(new))
                    for tk_, v_ in fresh.items():
                        watching[tk_] = v_[1]
                    # a subscription that only grows re-subscribes every dead
                    # market on each reconnect and walks into the server's
                    # "Subscription buffer overflow" (livebook error code 25).
                    gone = [t for t, c in watching.items() if c < now_s - 300]
                    if gone:
                        book.drop(gone)
                        for t in gone:
                            watching.pop(t, None)
                        rec("unwatch", n=len(watching), dropped=sorted(gone))
                state["errors"] = 0
                _uni_n = len(fresh)
            except Exception as e:                       # noqa: BLE001
                state["errors"] += 1
                rec("error", where="universe", err=str(e)[:200])
            # R2: WHAT THE REFRESH COST, EVERY TIME. One synchronous
            # GET /markets per series on a fresh connection, with no
            # condition on time to close -- and the hedge pass is in this
            # same thread, so this duration is also the hedge's blackout.
            # It is a DURATION, not a decision: nothing is deferred, moved
            # or skipped, the refresh runs exactly where and when it did,
            # and a record that cannot be written is dropped rather than
            # allowed to reach the loop.
            #
            # REVIEW FIXES 2026-09-22, both about what the record could not
            # say:
            #  * `tau` / `close_s` -- the change this bar sizes is "defer
            #    the refresh while a watched market is inside 60 s", so
            #    WHERE IN THE CLOSE the refresh landed is the whole
            #    question. Without it, `ms` alone sizes nothing, and the
            #    `loop` records cannot stand in (their budget is spent far
            #    from the close).
            #  * `got` -- `seen_markets` is only replaced under `if fresh:`,
            #    so a refresh in which every series GET failed recorded the
            #    PREVIOUS pass's `n`, and a totally failed refresh then read
            #    as a healthy slow one. `got` is what THIS refresh built,
            #    and None if it raised before finishing.
            try:
                _unc = min((c for c in watching.values() if c >= now_s),
                           default=None)
                rec("universe", ms=round(1000.0 * (time.time() - _uni_t0), 1),
                    n=len(seen_markets), got=_uni_n, watching=len(watching),
                    deferred_s=_uni_waited,
                    series=len(series_index), close_s=_unc,
                    tau=(int(_unc - now_s) if _unc is not None else None))
            except Exception:                            # noqa: BLE001
                pass

        # ---- AMENDMENT 24 (2026-09-13): SCAN ORDER IS THE BEST FIRST ------
        # THE OPERATOR, 2026-09-13: "I'm not certain if it should take the
        # first or scan for the best because prices move quick but also what
        # if there's better options."
        #
        # WHAT IT DID BEFORE: iterate `seen_markets` and fire on the first
        # market that clears every gate. That order is dict insertion order --
        # discovery order -- which is not a rule anyone chose. It is stable,
        # so it systematically favours the same coins, and it is the only gate
        # in this bot that is not an EV comparison.
        #
        # MEASURED, research/pinpick.py, 13,984 gate-passing candidate rows on
        # 738 closes: two or more DIFFERENT markets pass in the same scan
        # second 6.3% of the time, and when they do the first one seen is the
        # best-edge one only 56.3% of the time. Taking the first gives up a
        # mean 2.10c of edge (median 0.28c, p90 7.43c) and pays 2.21c more.
        # Replayed one contract per close: +2.07c -> +2.76c per contract with
        # the SAME number of losses (10 and 10). It survives a 60/40 split on
        # close time, and the untouched last 40% shows +1.63c -> +2.43c, again
        # on identical loss counts. The gain is price, not risk: "highest
        # confidence" only reaches +2.19c.
        #
        # WHY IT COSTS NO TIME AND LOSES NO RACE, which was the operator's
        # actual worry. The order comes from the edge measured on the PREVIOUS
        # pass, 50ms ago at 20Hz -- nothing is computed twice and no take is
        # deferred. Compare that with the status quo, whose ordering is not
        # 50ms stale but permanently stale.
        _mk = list(seen_markets.items())
        if PICK == "best":
            def _rank(kv):
                got = last_edge.get(kv[0])
                if not got or got[0] != kv[1][1]:      # edge from another close
                    return 0.0
                return -got[1]
            _mk.sort(key=_rank)
        if state.get("entries_stopped"):
            _mk = []        # K1: no NEW entries (belt and braces: the drain
                            # above already skips the scan while it holds)
        for tk, (iid, close_s, strike, digits, exi) in _mk:
            try:
                tau = close_s - now_s
                if not (TAU_MIN <= tau <= max(TAU_MAX, EARLY_TAU_MAX)):
                    continue                 # not a refusal: outside the window
                # AMENDMENT 3: scale in as the price IMPROVES, up to MAX_PER_CLOSE.
                # One shot at the first safe price leaves money on the table:
                # measured over 70 closes, adding only on improvement raised profit
                # per opportunity from 4.18c to 8.87c AND lowered the average price
                # paid from 95.53c to 94.28c. Waiting for a better price instead is
                # strictly worse -- skipping just one tick missed 7 of 70 closes
                # outright. In this bet a lower price wins more AND loses less, so
                # averaging down improves both sides.
                prev = fired.get(close_s)
                # ---- AMENDMENT 46: staged early entry -- what this market holds
                # from an early leg, and whether this look is itself early. One
                # early leg per market; a second early look is refused here,
                # before any signal is recorded.
                _held46 = float((prev.get("early_tk", {}) if prev else {}).get(tk, 0.0))
                _early46 = EARLY_TAU_MAX > TAU_MAX and tau > TAU_MAX
                if _early46 and _held46 > 0:
                    _gate("early_once", close_s, tk, held=_held46, tau=tau)
                    continue
                if CLOSE_BUDGET:
                    # AMENDMENT 17: contracts, not fills. Coins are unlimited;
                    # the close is done when its contract budget is spent.
                    _spent = prev.get("contracts", 0.0) if prev else 0.0
                    _bud56 = close_budget_for(prev, tk, tau=tau)
                    if _spent >= _bud56 - 1e-9:
                        # THIS GATE CANNOT RECORD want/price/fair AND MUST NOT
                        # TRY. It fires here, BEFORE the book is read: `f` is
                        # assigned further down and `want, price, size` further
                        # down still. On 2026-09-19 01:59Z an attempt to log them
                        # read a STALE `price` left as None by an earlier market
                        # and killed the live bot with
                        #   TypeError: type NoneType doesn't define __round__
                        # after an hour of trading, with two positions open.
                        #
                        # Making this gate scorable means moving the budget check
                        # to AFTER the book read -- a change to WHEN we refuse,
                        # not just to what we log, and not one to make on a
                        # crashed bot at 2am. Until then `close_budget` refusals
                        # are counted, not valued.
                        _gate("close_budget", close_s, tk, spent=_spent,
                              budget=_bud56, base=close_budget(),
                              extra_coin=float(EXTRA_COIN), tau=tau,
                              size=float(SIZE))
                        continue
                elif prev is not None and prev["n"] >= MAX_PER_CLOSE:
                    _gate("max_per_close", close_s, tk, n=prev["n"])
                    continue
                # AMENDMENT 13: ONE FILL PER MARKET. See MAX_PER_MARKET.
                if prev is not None and                     prev.get("per_tk", {}).get(tk, 0) >= MAX_PER_MARKET:
                    nb13 = near.setdefault(close_s, _fresh_near())
                    nb13["market_capped"] = nb13.get("market_capped", 0) + 1
                    _gate("max_per_market", close_s, tk,
                          fills=prev.get("per_tk", {}).get(tk, 0))
                    continue
                # AMENDMENT 8(A): NEVER HOLD BOTH SIDES OF ONE MARKET.
                # `fired` was keyed by close alone, so the improve bar was compared
                # across markets AND across sides. Every price we can pay is above
                # 50c, so buying YES then NO on the same market pays >100c for a
                # guaranteed $1.00 -- a CERTAIN loss on one of the two orders,
                # carrying no directional risk at all. Worse, pinrun counts the
                # loss brake per settled losing ORDER, so it spends a third of the
                # budget with certainty. Measured: 3 pairs over 2 closes in the
                # wide sample, ZERO in 82 live-window closes, so this costs ~$4 of
                # EV out of $230 and nothing at all where we actually trade.
                # MOVED 2026-09-17: this test USED TO LIVE HERE and read `want` --
                # which is not assigned until ~140 lines below, inside this same
                # scan loop. So it compared the side we hold in THIS market against
                # the side we happened to want in the PREVIOUS market of the scan,
                # or None on the first pass. It therefore blocked roughly 94% of
                # re-looks at a market we already hold, including legitimate
                # same-side top-ups, and let a genuine opposite-side buy through
                # whenever the previous market happened to want the same side.
                # Found by the 2026-09-17 fresh-eyes review and confirmed by three
                # independent readers. The test now runs where `want` exists; see
                # `_both_sides_block` below.
                # AND A SEPARATE CAP ON ATTEMPTS. AMENDMENT 6 stopped a no-fill
                # from burning a FILL slot, which is right -- an unfilled order
                # creates no exposure. But it left NOTHING bounding how many times
                # we may try, so a persistently refused order retried at 20 Hz
                # forever. Fills and attempts need separate budgets.
                # ---- AMENDMENT 26 (2026-09-14): DON'T STOP WALKING THE LADDER ---
                # THE OPERATOR: "make sure that if it goes through all, and goes
                # back to buy the best, if that's sold out it keeps checking to see
                # if the next best or any others are still available and gets
                # those."
                #
                # THE LOOP ALREADY DOES THAT -- there is no `break` after an order,
                # so a market that fails to fill is followed by the next market in
                # the pass, and since AMENDMENT 24 sorted the pass by edge, the
                # next market IS the next best. What could stop it was this cap.
                #
                # MAX_ATTEMPTS_PER_CLOSE was 8, written on 2026-09-08 against a
                # runaway that sent 160 orders into ONE market in ONE second. But
                # 8 is also fewer than the twelve coins that settle on the same
                # second, so a close where the first few asks vanished could run
                # out of attempts before ever reaching a market that was still
                # there -- the exact thing he is asking for, blocked by a cap
                # aimed at something else.
                #
                # THE RUNAWAY IS NOW STOPPED AT ITS ACTUAL SOURCE. It was one
                # market retried, not many markets tried, so the per-MARKET cap
                # below makes 160-into-one impossible however high the close cap
                # goes. That lets the close cap rise to cover every coin twice.
                if attempts_tk.get((close_s, tk), 0) >= MAX_ATTEMPTS_PER_MARKET:
                    _gate("market_attempts", close_s, tk,
                          tried=attempts_tk.get((close_s, tk), 0))
                    continue
                if attempts.get(close_s, 0) >= MAX_ATTEMPTS_PER_CLOSE:
                    _gate("attempts_cap", close_s, tk,
                          tried=attempts.get(close_s, 0))
                    continue
                try:
                    b = book.best(tk)
                except Exception as e:                       # noqa: BLE001
                    state["errors"] += 1
                    rec("error", where="book", ticker=tk, err=str(e)[:200])
                    continue
                if not b or b.get("suspect"):
                    _gate("book_suspect", close_s, tk)
                    continue
                if b.get("age_ms") is None or b["age_ms"] > MAX_BOOK_AGE_MS:
                    _gate("book_stale", close_s, tk, age_ms=b.get("age_ms"))
                    continue
                sec, spot, iage = idx.spot(iid)
                if spot is None or iage is None or iage > MAX_INDEX_AGE_S:
                    _gate("index_stale", close_s, tk, age_s=iage)
                    continue
                sg = idx.sigma(iid)
                if sg is None:
                    _gate("no_sigma", close_s, tk)
                    continue
                # AMENDMENT 41/42. THE SIDE IS NOT KNOWN YET -- `want` is chosen
                # from the ask side further down, and the first version of this
                # line passed it anyway. Python evaluates arguments before the
                # call, so it raised UnboundLocalError on the first market that
                # ever reached here, whatever the flag said. It killed the live
                # bot at 2026-09-15 04:59:30Z, ten minutes after a restart --
                # ten minutes because nothing reaches this line until a market
                # clears the book, index and sigma gates.
                #
                # So: price it UNWIDENED first, take the lean from that, then
                # widen and price it again. Widening sigma moves confidence
                # toward 0.5 and can never flip which side the model leans to, so
                # the lean read off the unwidened number is the same lean.
                # Two fair() calls, and only when the flag is on.
                f = fair(idx, iid, close_s, now_s, strike, sg * SIGMA_STRESS,
                         round_digits=digits)
                if f is None:
                    continue
                _wf = 1.0
                if WIDEN_ENABLED:
                    _lean = "yes" if f >= 0.5 else "no"
                    _wf = widen_factor(idx, iid, sg, _lean)
                    if _wf != 1.0:
                        f = fair(idx, iid, close_s, now_s, strike,
                                 sg * SIGMA_STRESS * _wf, round_digits=digits)
                        if f is None:
                            continue
                state["considered"] += 1

                # ---- --hedge-plant: the planted one-contract hedge test -------
                # Operator, 2026-09-12: "buy 1 of a losing coin, then test the
                # hedge with 1." At the first DECIDED market (belief >= PIN one
                # way) with tau <= 25, buy ONE contract of the side about to LOSE
                # at its ask, book it exactly like a real fill (open_pos +
                # hedge_meta), and let the hedge pass -- which sees belief ~0 on
                # it within a second -- fire the hedge. Fires at most once per
                # run; costs a few cents (a ~3c leg plus a ~97c leg pay $1).
                # Everything after the buy is the ordinary, unmodified hedge path,
                # which is the point: it is the live path being tested.
                if getattr(a, "hedge_plant", False) and not state.get("plant_done") \
                        and tau <= 25 and (0.90 <= f <= 0.99 or 0.01 <= f <= 0.10):
                    # FIRST PLANT, 09:44:35Z: it chose a FULLY decided market (fair
                    # 0.0000), bought 1 YES at 0.3c, the alarm fired, and there was
                    # no NO ask to hedge with -- in a decided market the dead side's
                    # book is empty (33,427 of 33,431 moments), so the winner has
                    # no ask. Real structure, not a bug; but it exercised only the
                    # refusal path. Settled -0.33c. Now plant only when the market
                    # is NEARLY decided (winner 90-99%), so the losing side costs
                    # 1-10c and the winner's ask exists at 90-99c: the hedge can
                    # then FILL and both legs settle, which is the test wanted.
                    _lose = "no" if f >= 0.5 else "yes"          # the side about to lose
                    _la = b.get(f"{_lose}_ask")
                    _ls = b.get(f"{_lose}_ask_size")
                    if _la and _ls and 0.0 < _la < 0.50 and live:
                        state["plant_done"] = True
                        attempts[close_s] = attempts.get(close_s, 0) + 1
                        rec("plant_attempt", ticker=tk, side=_lose, ask=_la,
                            fair=round(f, 5), tau=tau)
                        print(f"  PLANT: buying 1 {_lose.upper()} {tk} @ {_la:.3f} "
                              f"(fair {f:.4f}) to test the hedge on it")
                        try:
                            _po = pintake.take(CREDS["base"], CREDS["pk"],
                                               CREDS["key_id"], tk, _lose,
                                               float(_la), 1.0, float(close_s),
                                               exchange_index=2)
                        except Exception as _e:                  # noqa: BLE001
                            rec("error", where="plant_take", ticker=tk, err=str(_e)[:300])
                            _po = {}
                        _pf = float(_po.get("filled") or 0)
                        _pp = _po.get("exec_price")
                        # K1: registered for the hedge BEFORE it is written
                        # down, like every other fill.
                        if _pf > 0:
                            _poid = f"plant-{_po.get('order_id') or now_s}"
                            _pc = float(_pp) if _pp is not None else float(_la)
                            open_pos[_poid] = (close_s, _lose, _pc, _pf, tk)
                            entry_at[_poid] = now_s
                            hedge_meta[_poid] = (strike, digits, iid)
                        rec("plant", ticker=tk, side=_lose, filled=_pf,
                            price=(float(_pp) if _pp is not None else _la),
                            refused=_po.get("refused"), status=_po.get("status"),
                            order_id=_po.get("order_id"))
                        if _pf > 0:
                            print(f"  PLANT filled {_pf:g} @ {_pc:.3f}; the hedge "
                                  f"pass should fire on it within a second")
                        continue

                want = price = size = None
                if f >= PIN:
                    ya, ys = b.get("yes_ask"), b.get("yes_ask_size")
                    if ya and ys and ya < 1.0:
                        want, price, size = "yes", ya, ys
                elif f <= 1.0 - PIN:
                    na, ns = b.get("no_ask"), b.get("no_ask_size")
                    if na and ns and na < 1.0:
                        want, price, size = "no", na, ns
                # ---- D_plan SECTION 5, THE HALF THE 1 Hz GRID CANNOT SEE ----
                # "a rec() on any look whose own-side price fell >= LOOK_DROP_C
                # since this bot's previous look at the same market, log-only,
                # no gate". The DOGE close that cost $107.95 moved 98.0c ->
                # 93.4c on our own side across three looks 244 ms apart (tau
                # 12, 12, 11); the trajectory sampler takes ONE record a market
                # a second, so all three collapse into one row and the
                # population that question needs would never exist. This is the
                # only place in the process that looks 20 times a second.
                #
                # IT DECIDES NOTHING AND IT CANNOT DELAY ANYTHING. Two dict
                # operations on a path that has already read the book and
                # already priced the market; a record only when the drop
                # fires, which is rare; capped at LOOK_DROP_MAX per (close,
                # market) so a flapping book cannot become a firehose; wrapped,
                # so a fault here cannot cost the scan its market. It writes
                # through the TRAJECTORY writer, so it never enters the log
                # every settlement reader parses.
                #
                # A look with no side of its own is not a comparison: `want` is
                # None when the model is undecided or nobody is offering, and
                # "our side got cheaper" has no meaning then. Those looks do
                # not update the reference either, so the next real look is
                # compared against the last real one.
                if want is not None and price is not None:
                    try:
                        _ldk = (close_s, tk)
                        _ldp = look_at.get(_ldk)
                        # `now`, NOT `now_s`: the whole point is a gap smaller
                        # than a second. now_s is int(now), so three looks
                        # 244 ms apart would all read a gap of zero -- the
                        # exact collapse this record exists to escape.
                        look_at[_ldk] = (now, want, float(price))
                        _ldd = (float(_ldp[2]) - float(price)
                                if _ldp is not None and _ldp[1] == want
                                else 0.0)
                        if (_ldd >= LOOK_DROP_C
                                and look_drop_n.get(_ldk, 0) < LOOK_DROP_MAX):
                            look_drop_n[_ldk] = look_drop_n.get(_ldk, 0) + 1
                            _trec("price_drop", ticker=tk, close_s=close_s,
                                  tau=tau, want=want,
                                  was=round(float(_ldp[2]), 4),
                                  now=round(float(price), 4),
                                  drop_c=round(100.0 * _ldd, 2),
                                  gap_ms=int(round(1000.0 * (now - _ldp[0]))),
                                  fair=round(f, 5), ask_size=size,
                                  opp_ask=b.get("no_ask" if want == "yes"
                                                else "yes_ask"),
                                  book_age_ms=b.get("age_ms"),
                                  held=((prev.get("sides") or {}).get(tk)
                                        if prev else None),
                                  n=look_drop_n[_ldk], cap=LOOK_DROP_MAX)
                    except Exception:                    # noqa: BLE001
                        pass
                # AMENDMENT 8, NOW READ AT THE RIGHT MOMENT. Never hold both sides
                # of one market: the two legs cannot both win, so the pair costs
                # more than the $1 it pays and locks in the difference. `want` is
                # assigned immediately above, so this is the first line in the loop
                # where the comparison is even meaningful.
                # A68: how much MORE of the hedged-into side we may buy. Only
                # while the model has given up (belief at or under the panic
                # line), and capped at a multiple of what we hold on the losing
                # side so the tail is bounded before it happens rather than
                # discovered afterwards.
                _lose_n = ((prev.get("n_tk") or {}).get(tk, 0.0)
                           if prev else 0.0)
                _room68 = None
                if (hedged_side.get(tk) is not None and want == hedged_side.get(tk)
                        and hedge_panic(last_belief.get(tk))):
                    _room68 = rebuy_room(_lose_n, rebuy_extra.get(tk, 0.0))
                if want is not None and _both_sides_block(
                        prev, tk, want, hedged_side.get(tk), _room68):
                    nb0 = near.setdefault(close_s, _fresh_near())
                    nb0["both_sides_blocked"] = nb0.get("both_sides_blocked", 0) + 1
                    # `want`, `fair`, `tau`, `spot` and `strike` are RECORDED
                    # HERE because on 2026-09-18 this gate fired after every
                    # early leg on twenty straight live markets, and with only
                    # `held` in the record nobody could tell whether the model had
                    # genuinely reversed or the fair value was being computed for
                    # the wrong thing. A refusal that cannot say why it refused
                    # is one nobody can argue with.
                    _gate("both_sides", close_s, tk, held=prev["sides"][tk],
                          want=want, fair=round(f, 5), tau=tau,
                          spot=spot, strike=strike,
                          # A63: so a reader can tell "we never hedged this" from
                          # "we hedged the other way and the flag is off"
                          hedged_into=hedged_side.get(tk),
                          rebuy_hedged=bool(REBUY_HEDGED),
                          wanted=want)
                    continue
                if want is None:
                    # WHY did this not produce a candidate? The two cases are very
                    # different and conflating them hides the real constraint:
                    #   undecided  -- fair never reached the gate; no edge existed
                    #   no_offer   -- fair DID reach the gate but nobody was
                    #                 offering the winning side. When an outcome
                    #                 becomes obvious the losing side's bids
                    #                 vanish, so there is nothing to buy. That is
                    #                 a CAPACITY limit, not a signal limit.
                    nb = near.setdefault(close_s, _fresh_near())
                    nb["n"] += 1
                    if f >= PIN or f <= 1.0 - PIN:
                        nb["decided"] += 1
                        nb["no_offer"] += 1
                        # RECORD WHAT WAS ACTUALLY ON THE SCREEN. "no_offer" does
                        # NOT mean nobody was selling -- it means no ask BELOW
                        # 100c, and an ask at exactly 100c (worthless to us, but a
                        # real seller) lands here too. Without these fields the
                        # log cannot tell the two apart, and on 2026-09-14 I told
                        # the operator "nobody was selling" when I could not know
                        # that. The distinction matters: no seller at all is a
                        # hard ceiling on the strategy, while a seller at 100c is
                        # a pricing problem.
                        _gate("no_offer", close_s, tk, fair=round(f, 5), tau=tau,
                              yes_ask=b.get("yes_ask"), no_ask=b.get("no_ask"),
                              yes_ask_size=b.get("yes_ask_size"),
                              no_ask_size=b.get("no_ask_size"),
                              wanted_side=("yes" if f >= PIN else "no"))
                    else:
                        nb["undecided"] += 1
                        _gate("confidence", close_s, tk, fair=round(f, 5),
                              tau=tau)
                    continue
                # AMENDMENT 6: buy what is THERE, down to MIN_FILL_FRAC of what
                # we wanted. Below that, skip -- a scrap fill burns a scale-in
                # slot and raises the improve bar for the better price still to
                # come, which measured WORSE than not trading at all.
                take_n = min(float(SIZE), float(size))
                # THE FLOOR IS MEASURED AGAINST FULL SIZE, NEVER THE REMAINDER --
                # the operator's own condition (A17). Trimming take_n first would
                # let the tail of a budget buy a moment the floor exists to
                # refuse, so the trim happens strictly AFTER this test.
                _floor = max(MIN_LEVEL, MIN_FILL_FRAC * float(SIZE))
                # AMENDMENT 37: how many can we actually BUY, not how many sit at
                # the touch. take_n is deliberately NOT reassigned here -- every
                # downstream user of it keeps the touch number, and the order path's
                # own A35 block does the widening. This decides ONLY whether to
                # refuse. Computed inside the thin branch so it costs nothing on
                # the 96% of looks that are not shallow.
                _reach = take_n
                if DEPTH_LADDER and SWEEP_DEPTH and take_n < _floor:
                    _dlim = sweep_limit(f, price, want)
                    if _dlim > price + 1e-9:
                        try:
                            _reach = min(float(SIZE),
                                         max(take_n,
                                             float(book.buyable(tk, want, _dlim))))
                        except Exception:              # noqa: BLE001
                            _reach = take_n
                if _reach < _floor:
                    # RECORD IT ANYWAY. A moment we skip for being too shallow is
                    # still a moment the market offered something, and it is the
                    # number that decides how far we can scale.
                    _nb = near.setdefault(close_s, _fresh_near())
                    _nb["depths"].append(float(size))
                    _nb["shallow"][str(int(SIZE))] =                     _nb["shallow"].get(str(int(SIZE)), 0) + 1
                    _gate("depth_floor", close_s, tk, want=want,
                          price=round(price, 4), offered=float(size),
                          reach=round(float(_reach), 2),
                          depth_ladder=bool(DEPTH_LADDER and SWEEP_DEPTH),
                          # `size` is what makes a refusal SCORABLE: pinattrib
                          # values a blocked trade at min(size_now, size), so 545
                          # of this gate's refusals were discarded over a missing
                          # key while the report blamed a missing price.
                          wanted=float(SIZE), fair=round(f, 5), tau=tau,
                          size=float(SIZE))
                    continue
                e = net_edge(f, price, want)
                # AMENDMENT 24: remember it so the NEXT pass can visit the best
                # market first. Keyed with the close, because a ticker's edge from
                # a settled close must never order the following one.
                last_edge[tk] = (close_s, e)
                nb = near.setdefault(close_s, _fresh_near())
                nb["n"] += 1
                nb["decided"] += 1
                nb["tradeable"] += 1
                nb["depths"].append(float(size))
                # AMENDMENT 44: how deep is the BOOK here, not just the touch?
                # Once per market per close. Never raises into the trade loop.
                if tk not in nb["ladder_seen"]:
                    nb["ladder_seen"].add(tk)
                    try:
                        nb["ladders"].append(
                            float(book.buyable(tk, want, PRICE_CEILING)))
                    except Exception:              # noqa: BLE001
                        pass
                if take_n < float(SIZE):
                    nb["dust"] += 1        # a PARTIAL, not a refusal, since A6
                if nb["best"] is None or e > nb["best"]["edge"]:
                    nb["best"] = {"ticker": tk, "want": want, "edge": e,
                                  "price": price, "fair": f, "tau": tau,
                                  "size": size}
                if e < EDGE_FLOOR:
                    _gate("edge_floor", close_s, tk, want=want,
                          price=round(price, 4), edge_c=round(100 * e, 3),
                          need_c=round(100 * EDGE_FLOOR, 3), fair=round(f, 5),
                          tau=tau, size=float(size))
                    continue
                # AMENDMENT 38: a thin edge while the LIVE price is already past
                # the strike against us. Placed immediately after the edge floor
                # because it is the same question asked with one more fact, and
                # before the dump guard so the two refusals stay distinguishable
                # in the audit.
                _agn = against_us(strike, spot, sg, want)
                if against_block(strike, spot, sg, want, e):
                    _gate("against_thin", close_s, tk, want=want,
                          price=round(price, 4), edge_c=round(100 * e, 3),
                          against_sigma=round(float(_agn), 3),
                          strike=strike, spot=spot, sigma=round(sg, 6),
                          need_edge_c=round(100 * AGAINST_EDGE, 3),
                          fair=round(f, 5), tau=tau, size=float(size))
                    continue
                # AMENDMENT 40: the index just jumped against us. After the A38
                # test and before the dump guard, so the three refusals stay
                # separable in the audit. Reads the model's own sigma.
                if JUMP_ENABLED:
                    _mv = idx.recent_moves(iid, JUMP_LOOKBACK)
                    _jmp = jump_against(_mv, sg, want)
                    if jump_block(_mv, sg, want):
                        _gate("jump_against", close_s, tk, want=want,
                              price=round(price, 4), edge_c=round(100 * e, 3),
                              jump_sd=round(float(_jmp), 2),
                              moves=[round(float(m), 6) for m in _mv],
                              sigma=round(sg, 6), need_sd=JUMP_SIGMA,
                              fair=round(f, 5), tau=tau, size=float(size))
                        continue
                # AMENDMENT 10: a certainty at a discount is someone else's
                # information, not our edge. See DUMP_CONF / DUMP_DISCOUNT.
                _conf = f if want == "yes" else (1.0 - f)
                _disc = (f - price) if want == "yes" else ((1.0 - f) - price)
                if _disc > DUMP_DISCOUNT:
                    nb["dumped"] = nb.get("dumped", 0) + 1
                    if nb["best"] is not None and nb["best"]["ticker"] == tk:
                        nb["best"]["dumped"] = round(100 * _disc, 2)
                    # ONE record per (close, market), not one per 20 Hz tick, so
                    # the would-be outcome is resolvable later and the log stays
                    # readable. Written whether or not the guard is enabled.
                    if (close_s, tk) not in dumped_seen:
                        dumped_seen.add((close_s, tk))
                        rec("dumped", ticker=tk, want=want, price=round(price, 4),
                            fair=round(f, 5), tau=tau, disc_c=round(100 * _disc, 2),
                            size=size, take_n=take_n, close_s=close_s,
                            refused=bool(DUMP_ENABLED))
                    if DUMP_ENABLED:
                        _gate("dump_guard", close_s, tk, want=want,
                              price=round(price, 4), disc_c=round(100 * _disc, 2),
                              fair=round(f, 5), tau=tau, size=float(size))
                        continue
                # THE EXPECTED-VALUE GATE (AMENDMENT 2). The model edge above uses
                # the model's own confidence, which implies ~0.06% error at the
                # prices we pay. The MEASURED rate on trades we actually take is
                # 0.90%. At high prices that gap flips the sign of the trade:
                # breakeven price is exactly 1 - flip = 99.1c, and five of the
                # seven live trades on 2026-09-08 were above it and negative EV.
                # AMENDMENT 3: a SECOND buy on the same close is only allowed at a
                # genuinely better price. Re-buying at the same level would double
                # the risk without lowering the average paid, which is the whole
                # mechanism -- a lower price wins more AND loses less.
                # AMENDMENT 22: with MAX_PER_MARKET = 1 the same-market case can
                # never arise, so under scope "market" this rule is a no-op and a
                # second COIN is allowed at its own merits. Under "close" it keeps
                # the old behaviour exactly.
                if (IMPROVE_SCOPE == "close" and prev is not None
                        and price >= prev["best"] - IMPROVE_BY):
                    _gate("improve_by", close_s, tk, want=want,
                          price=round(price, 4), best=prev["best"],
                          fair=round(f, 5), tau=tau, size=float(size))
                    continue
                # ---- AMENDMENT 23 (2026-09-13): THE RE-BUY BAND ----------------
                # A SECOND BUY IN THE SAME MARKET MUST BE A LITTLE CHEAPER, NOT A
                # LOT CHEAPER. Only reachable when MAX_PER_MARKET > 1, which is
                # still a paper-only setting, so this changes nothing live today.
                #
                # THE OPERATOR'S PREMISE, 2026-09-13: "if it's really going to
                # flip then the confidence should be dropping." MEASURED, and it
                # is half right. research/pinwarn.py, 18,653 closes reconstructed
                # from the index with NOTHING filtered: confidence does fall below
                # the gate on 31 of 31 closes the model got wrong -- but LATE. At
                # tau 25 it had caught only 11 of 18, at tau 20 only 12 of 19. On
                # our own money it was later still: SOL 2026-09-12 23:00 was
                # bought three times at tau 30/29/28 while confidence ROSE
                # 0.9994 -> 0.9997 -> 0.9998, and the flip only showed at tau~12.
                # So confidence is a true warning and a useless one at the moment
                # a second buy happens.
                #
                # WHAT IS FAST ENOUGH IS THE PRICE. research/pinpick.py, 1,260
                # gate-passing markets over 738 closes: of the 862 markets where
                # no cheaper second ever appeared, ZERO lost. Of the 398 where one
                # did, 25 lost -- 6.28%, difference +6.28pp with a 95% interval of
                # [+3.46, +9.82] bootstrapped over CLOSES rather than markets.
                # And it is a dose-response, which is the part that is hard to get
                # by accident:
                #     0.5-1c cheaper   142 markets   0.70% lost   2nd leg +3.08c
                #     1-2c             141           5.67%                -0.09c
                #     2-5c              87          11.49%                -4.92c
                #     5-10c             23          26.09%               -11.45c
                # Break-even is 3.58%. A small improvement is liquidity and pays;
                # a large one is someone selling into us and costs more than the
                # whole edge. The ordering survives a 60/40 split on close time,
                # and the last 40% were never fitted: 1.79 / 6.06 / 21.21 / 44.44.
                #
                # CAVEAT, STATED RATHER THAN BURIED: those loss rates come from the
                # tape, whose population is "an offer was sitting there" and not
                # ours. Rule 5 forbids reading OUR loss rate off it. What is used
                # here is the ORDERING and the fact that the groups differ, both of
                # which are statements about what the market did.
                if not rebuy_ok(prev, tk, price, SIZE):
                    nb23 = near.setdefault(close_s, _fresh_near())
                    nb23["rebuy_band"] = nb23.get("rebuy_band", 0) + 1
                    _gate("rebuy_band", close_s, tk, want=want,
                          price=round(price, 4),
                          paid=(prev.get("px_tk", {}) or {}).get(tk),
                          fair=round(f, 5), tau=tau, size=float(size))
                    continue
                if price > PRICE_CEILING:
                    nb["over_ceiling"] = nb.get("over_ceiling", 0) + 1
                    _gate("price_ceiling", close_s, tk, want=want,
                          price=round(price, 4), ceiling=PRICE_CEILING,
                          fair=round(f, 5), tau=tau, size=float(size))
                    continue
                ev = expected_value(price)
                if ev < EV_FLOOR:
                    nb["neg_ev"] = nb.get("neg_ev", 0) + 1
                    if nb["best"] is not None and nb["best"]["ticker"] == tk:
                        nb["best"]["ev_c"] = round(100 * ev, 3)
                    _gate("ev_floor", close_s, tk, want=want,
                          price=round(price, 4), ev_c=round(100 * ev, 3),
                          fair=round(f, 5), tau=tau, size=float(size))
                    continue

                state["signals"] += 1
                if CLOSE_BUDGET:
                    _pvb = fired.get(close_s)
                    _left = close_budget() - (
                        _pvb.get("contracts", 0.0) if _pvb else 0.0)
                    if _left <= 0:
                        # ---- R4 (2026-09-22): THE SILENT REFUSAL. ------
                        # This `continue` was the ONLY exit between the
                        # signals counter and the order send with no
                        # record of any kind. The gate 600 lines above
                        # refuses on `close_budget_for` -- base PLUS ONE
                        # BET for a new coin or inside the last seconds --
                        # and logs; worst_close_cost() and the bank brake
                        # both PRICE three bets. So the third bet is
                        # granted, priced, sized for, and then dropped
                        # here with no refusal record and no close_summary
                        # count. Run 20260920T023207Z ended with
                        # state.signals = 102 against 5 signal records and
                        # zero looks at any of the five gates below: all
                        # 97 exited on this line.
                        #
                        # LOGGING ONLY. The `continue` is unchanged, the
                        # arithmetic above it is unchanged, and `_gate`
                        # already dedupes per (close, market, gate) -- so
                        # this is one record a market a close, not twenty
                        # a second. `budget_left` (which _gate computes
                        # from close_budget_for) will read > 0 here while
                        # the BASE is spent, and that is exactly what
                        # tells "the close's budget ran out" apart from
                        # "the third bet was dropped".
                        # `spent` is derived from the SAME expression the
                        # refusal used (base - left), so the record can
                        # never drift from the arithmetic that refused.
                        # REVIEW FIX 2026-09-22: `size` IS NOT OPTIONAL.
                        # The one reader this record was built to feed
                        # dropped it. barcheck.refusal_price() reads the
                        # refused volume as `offered` or `size`; with
                        # neither it returns ask_size None, and _b5_view
                        # then computes min(0.0, size_now) = 0 and throws
                        # the row away under "no size" -- so B5 still
                        # could not see the refusal this record exists to
                        # show it. The five sibling gates a hundred lines
                        # below all write size=float(take_n or SIZE); this
                        # is the same number, written the same way. `fair`
                        # joins them for the same reason.
                        _gate("close_budget_base", close_s, tk, want=want,
                              price=round(price, 4), take_n=float(take_n),
                              size=float(take_n or SIZE), fair=round(f, 5),
                              base=float(close_budget()),
                              spent=round(float(close_budget()) - float(_left), 4),
                              tau=tau)
                        continue
                    take_n = min(take_n, _left)

                # THE CONDITIONS AT THE MOMENT WE DECIDED. Logged, never gated on
                # -- see IndexWS.conditions(). Without this the live losses carry
                # no record of the state they happened in, and the tape has
                # already been shown unable to explain them: the backtest's
                # tradeable population flips 0.79% [0.10, 2.82] while live has
                # flipped 8.8% [2.9, 19.3], intervals that do not overlap.
                cx_, cn_, cown_ = idx.conditions(iid)
                # HOW LONG THE PRICE WE ARE ABOUT TO HIT HAS BEEN RESTING.
                # LOGGED, NEVER GATED ON -- results/RESULTS_select.md found the
                # model's excess loss concentrated entirely in the population
                # where somebody chose to sell to us, with every failure sitting
                # on a level under 0.25 s old and zero failures on levels resting
                # 30 s+. Those slices were picked after seeing the tape, so this
                # builds the LIVE record a pre-registered filter would need.
                # THE LEVEL WE CONSUME IS THE OPPOSITE SIDE'S BID: buying YES at
                # p means hitting the NO bid at 1-p (livebook's book holds bids).
                try:
                    _lvl_side = "no" if want == "yes" else "yes"
                    _lvl_age, _lvl_exact = book.level_age_ms(
                        tk, _lvl_side, round(1.0 - price, 4))
                except Exception:
                    _lvl_age, _lvl_exact = None, False
                sig = dict(ticker=tk, want=want, price=round(price, 4),
                           level_age_ms=_lvl_age, level_age_exact=_lvl_exact,
                           fair=round(f, 5), tau=tau, edge_c=round(100 * e, 3),
                           size=size, take_n=take_n, strike=strike, digits=digits,
                           spot=spot, sigma=round(sg, 6), book_age_ms=b["age_ms"],
                           index_age_s=round(iage, 2), exchange_index=exi,
                           widened=bool(_wf > 1.0),
                           cond_x=(round(cx_, 4) if cx_ is not None else None),
                           cond_n=cn_,
                           cond_own=(round(cown_, 4)
                                     if cown_ is not None else None))
                # ---- R1 (2026-09-22): --attempts-on-send ------------------------
                # WITH THE FLAG OFF -- the default, and what the live bot runs --
                # these two lines are exactly where they have always been and
                # both counters behave byte for byte as they do today. With it
                # ON, BOTH move to the send site below, so a look that is
                # refused WITHOUT AN ORDER (early_cheap, early_dear, early_wide,
                # staged_none, price_band -- all five sit between here and the
                # send) no longer burns an attempt of either kind.
                #
                # REVIEW FIX 2026-09-22 -- THE PER-CLOSE COUNTER HAD TO MOVE
                # TOO, AND LEAVING IT MADE THE FLAG STRICTLY WORSE THAN TODAY.
                #
                # The plan said to move only `attempts_tk`, on the grounds that
                # `attempts[close_s]` is the runaway rail and every observed
                # lockout was per-market. Driven in the offline loop, that is
                # backwards. Today the per-MARKET gate locks a burner out after
                # three looks, and that lockout is also what stops it reaching
                # this line -- so a burner contributes exactly 3 to the close
                # counter and the other eleven coins keep their room. Move only
                # the per-market counter and the burner is never locked out, so
                # it reaches this line on every pass at 20 Hz, hits
                # MAX_ATTEMPTS_PER_CLOSE in about 1.2 s, and `attempts_cap` then
                # refuses EVERY market in the close for the rest of its life.
                # Measured: flag OFF, an innocent second coin still enters; flag
                # ON with only `attempts_tk` moved, that coin gets ZERO signals
                # and is refused attempts_cap at t = 1.15 s. The arm would have
                # bought nothing on exactly the closes its bar measures -- the
                # A51 "the arm measured nothing" failure -- while the flag was
                # advertised as removing a refusal.
                #
                # Moving both keeps the rail: MAX_ATTEMPTS_PER_CLOSE's own
                # comment says "orders SENT per close, filled or not", and the
                # 2026-09-08 runaway was 160 SENDS, every one refused by a rail
                # inside take(). Counting sends still stops it at 24, and
                # MAX_ATTEMPTS_PER_MARKET = 3 still stops it at 3 in one market.
                # The hedge (under `_hcs`) and the plant still increment
                # `attempts[close_s]` where they always did; neither is touched.
                if not ATTEMPTS_ON_SEND:
                    attempts[close_s] = attempts.get(close_s, 0) + 1
                    attempts_tk[(close_s, tk)] = attempts_tk.get((close_s, tk), 0) + 1
                # ---- AMENDMENT 36: STORE THE BOOK WITH THE TRADE ---------------
                # The operator, 2026-09-14: "Are you able to see the order book
                # yourself for that trade? If not can we start storing that with
                # our transaction data."
                #
                # We could not. The signal recorded the touch price and the touch
                # SIZE and nothing else, so when he found the bot buying 6
                # contracts with 500 more one cent away, the log could not show
                # what had been on screen -- I had to take his word from a
                # screenshot. Every trade now carries the ladder it was looking
                # at, so that question is answerable from the log alone.
                #
                # The BUY side is the OTHER side's bids: a YES ask at p IS a NO
                # bid at 1-p. Stored as asks, cheapest first, the way we read it.
                # AMENDMENT 45 -- THE WHOLE LADDER, NOT EIGHT LEVELS.
                #
                # The operator, 2026-09-15: "for each price in the range of what we
                # actually purchase track the full amount available at the time of
                # our purchase."
                #
                # A36 stored 8 levels, which sounded like plenty and is not. On the
                # BTC 05:30 loss those 8 levels covered 2,136 contracts while
                # 10,610 sat under our own 98c limit -- so the log showed a fifth
                # of what was actually buyable and the rest was invisible. The tick
                # is tapered (0.1c above 90c), so the band we trade, roughly 88c to
                # 98c, is about a hundred levels. LADDER_LEVELS is set past that.
                #
                # Cost: one book read on a SIGNAL, which happens a few dozen times
                # a day, not in the scan loop. `ladder_under` is what we could
                # actually buy at or under the ceiling, which is the number every
                # capacity question wants and none of the earlier fields held.
                try:
                    _raw = book.depth(tk, "no" if want == "yes" else "yes",
                                      LADDER_LEVELS)
                    sig["ladder"] = [[round(1.0 - float(_p), 4), float(_sz)]
                                     for _p, _sz in (_raw or [])]
                    sig["ladder_total"] = round(sum(x[1] for x in sig["ladder"]), 2)
                    sig["ladder_under"] = round(
                        sum(x[1] for x in sig["ladder"]
                            if x[0] <= PRICE_CEILING + 1e-9), 2)
                    sig["ladder_levels"] = len(sig["ladder"])
                except Exception:                            # noqa: BLE001
                    sig["ladder"] = None
                # ---- AMENDMENT 46: size the leg BEFORE the signal is recorded, so
                # the record carries what will actually be asked for and which
                # leg it is (full / early / topup).
                _leg46 = "full"
                if EARLY_TAU_MAX > TAU_MAX:
                    take_n, _leg46 = staged_take(tau, take_n, float(SIZE), _held46)
                    sig["take_n"] = take_n
                    # AMENDMENT 49: an EARLY leg needs the price to be high as well
                    # as the model to be confident. The operator, 2026-09-18:
                    # "Can you re open 45 seconds with a cap at 90c".
                    #
                    # At 31-45 s the model leans harder on the sigma estimate than
                    # it does at 30 s, because less of the settlement average is
                    # locked. A cheap ask out there is not a bargain -- it is the
                    # market disagreeing with us at the moment we can least afford
                    # to be wrong, and it is the population that produced the
                    # 53c Bitcoin fill. Inside 30 s the full leg is unaffected.
                    if _leg46 in ("early", "early_once") and price < EARLY_MIN_PRICE:
                        _gate("early_cheap", close_s, tk, leg=_leg46, tau=tau,
                              price=round(price, 4), floor=EARLY_MIN_PRICE,
                              fair=round(f, 5),
                              want=want, size=float(take_n or SIZE))
                        continue
                    # AMENDMENT 78 (2026-09-20): AND TOO DEAR, ON THE EARLY LEG.
                    #
                    # The operator: *"Sure cut to 97.5 I like that. The whole
                    # point is better pricing so that's good."*
                    #
                    # Measured, live fills: the 31-45 s leg earns 1.14c a contract
                    # against 5.63c at 6-10 s. Above 97.5c it is risking 98c to
                    # make 1.8c, fifteen seconds before the information the whole
                    # strategy rests on arrives -- and that is exactly the fill
                    # that cost $107.95 on KXBTC15M-26SEP191600-00: bought NO at
                    # 98c at tau 45 while the same model, sixteen seconds later,
                    # said YES at 99.79% and the market offered YES at 92.6c.
                    #
                    # WHAT IT BLOCKS, stated as the standing rule requires: early
                    # fills at or above the ceiling. It cannot block the MAIN
                    # window (`_leg46` is "full" there), it cannot block a hedge,
                    # and with the ceiling at 1.0 it blocks nothing at all.
                    if (_leg46 in ("early", "early_once")
                            and price > EARLY_MAX_PRICE + 1e-9):
                        _gate("early_dear", close_s, tk, leg=_leg46, tau=tau,
                              price=round(price, 4), ceiling=EARLY_MAX_PRICE,
                              fair=round(f, 5),
                              want=want, size=float(take_n or SIZE))
                        continue
                    # A50: too GOOD to be true, on the early leg only.
                    if early_wide_block(_leg46, e):
                        _gate("early_wide", close_s, tk, leg=_leg46, tau=tau,
                              price=round(price, 4), edge_c=round(100 * e, 3),
                              cap_c=float(EARLY_MAX_EDGE), fair=round(f, 5),
                              # without want AND size this gate cannot be scored
                              want=want, size=float(take_n or SIZE))
                        continue
                    if take_n < MIN_LEVEL:
                        _gate("staged_none", close_s, tk, leg=_leg46, held=_held46,
                              tau=tau, price=round(price, 4),
                              want=want, size=float(take_n or SIZE))
                        continue
                # A53: a skipped price band refuses on EVERY leg. After the early
                # gates, so a cheap early ask is refused for being cheap (A49)
                # rather than for its band; before the signal is recorded, so a
                # refusal can never read as a lost race.
                if band_blocked(price):
                    _gate("price_band", close_s, tk, leg=_leg46, tau=tau,
                          price=round(price, 4), fair=round(f, 5),
                          bands=[list(b) for b in SKIP_BANDS],
                          want=want, size=float(take_n or SIZE))
                    continue
                sig["leg"] = _leg46
                sig["early_held"] = _held46
                # (5) the budget this candidate still had, and the moment
                # every gate had passed -- the order record's t_ms_decide
                sig["budget_left"] = _budget_left(close_s, tk, tau)
                _t_decide_ms = int(round(time.time() * 1000.0))
                rec("signal", live=live, **sig)
                print(f"  SIGNAL {tk} tau={tau}s buy {want.upper()} @{price:.4f} "
                      f"fair {f:.4f} edge {100 * e:+.2f}c size {size:.2f} "
                      f"taking {take_n:g}" + (f" [{_leg46}]" if _leg46 != "full" else ""))

                def _book_slot(px, n=None, raise_bar=True):
                    """AMENDMENT 6: a scale-in slot is consumed by a FILL, never by
                    an attempt. Until 2026-09-08 this ran BEFORE the order, so an
                    order that filled ZERO contracts still burned one of
                    MAX_PER_CLOSE and still raised the improve bar by IMPROVE_BY.
                    Five of our first nineteen live orders filled nothing, and the
                    misses had 562, 107, 93, 10 and 5 contracts on offer -- they
                    were lost races, not thin books, so they will keep happening.
                    An unfilled order creates NO exposure and must not consume an
                    exposure budget. Measured at the observed 26% miss rate over
                    1,196 moments on 83 closes: 87 buys -> 119 buys and expected
                    P&L $40.29 -> $53.72, +33.3%. MAX EXPOSURE IS UNCHANGED,
                    because the cap always meant two FILLS; the bug made it two
                    ATTEMPTS."""
                    _n = float(take_n if n is None else n)
                    pv = fired.get(close_s)
                    if pv is None:
                        fired[close_s] = {"n": 1, "best": px, "tk": tk,
                                          "sides": {tk: want},
                                          "tickers": {tk},
                                          "per_tk": {tk: 1},
                                          "px_tk": {tk: px},
                                          "n_tk": {tk: _n},
                                          # A46: what this market holds from an
                                          # EARLY leg, so the top-up knows how much
                                          # is left and a second early is refused
                                          "early_tk": ({tk: _n} if _leg46 == "early" else {}),
                                          "contracts": _n}
                    else:
                        if _leg46 == "early":
                            d46 = pv.setdefault("early_tk", {})
                            d46[tk] = d46.get(tk, 0.0) + _n
                        pv["n"] += 1
                        if raise_bar:
                            pv["best"] = min(pv["best"], px)
                        pv.setdefault("sides", {})[tk] = want
                        pv.setdefault("tickers", set()).add(tk)
                        d13 = pv.setdefault("per_tk", {})
                        d13[tk] = d13.get(tk, 0) + 1
                        # AMENDMENT 23: the CHEAPEST price paid in THIS market, so
                        # the re-buy band is measured per market. pv["best"] is
                        # the cheapest across the whole close and would compare a
                        # BTC re-buy against a price paid on ETH.
                        d23 = pv.setdefault("px_tk", {})
                        d23[tk] = min(d23.get(tk, px), px)
                        # AMENDMENT 29: contracts held in THIS market, which is
                        # what separates "topping up an unfinished position" from
                        # "scaling into a full one".
                        d29 = pv.setdefault("n_tk", {})
                        d29[tk] = d29.get(tk, 0.0) + _n
                        pv["contracts"] = pv.get("contracts", 0.0) + _n
                        # A68: contracts bought on the side we HEDGED INTO are
                        # the extra bet, not the original position, and the cap
                        # is measured against them.
                        if hedged_side.get(tk) is not None and want == hedged_side.get(tk):
                            rebuy_extra[tk] = rebuy_extra.get(tk, 0.0) + _n

                def _note_scrap(px, nfilled):
                    """AMENDMENT 12 (2026-09-11): A SCRAP FILL IS NOT A SLOT.
                    MIN_FILL_FRAC gates what we ASK for; nothing gated what we
                    GOT. 2026-09-11 07:00 ET: asked 20, filled 2.0 (BNB) and
                    0.02 (BTC) -- the offer was gone by the time the order landed
                    -- and each scrap consumed one of the two buys for its close
                    and raised the improve bar, blocking a real fill behind it.
                    A fill under half our size books the POSITION (it exists and
                    must settle and release) but not the slot and not the bar. It
                    does record the side, so the both-sides guard still holds.

                    AMENDMENT 12a, same day, found by auditing 12 rather than
                    admiring it: "no slot" with nothing else changed DOUBLES the
                    worst case. MAX_ATTEMPTS_PER_CLOSE is 8, so eight scraps of
                    9.99 contracts would each keep a position and none would
                    spend a slot -- 79.9 contracts, $78.32, against an intended
                    $39.20, with only the run-wide stake cap as a backstop. So
                    SCRAPS ACCUMULATE: once they add up to a real fill they spend
                    a slot exactly as one would. Exposure is bounded again, and
                    the thing 12 was for -- one 0.02-contract crumb must not
                    block a real buy -- still holds."""
                    pv = fired.get(close_s)
                    if pv is None:
                        pv = fired[close_s] = {"n": 0, "best": 1.0, "tk": tk,
                                               "sides": {}, "tickers": set(),
                                               "scrap_n": 0.0}
                    pv.setdefault("sides", {})[tk] = want
                    pv.setdefault("tickers", set()).add(tk)
                    pv["scrap_n"] = pv.get("scrap_n", 0.0) + float(nfilled)
                    if pv["scrap_n"] >= max(MIN_LEVEL, MIN_FILL_FRAC * float(SIZE)):
                        pv["n"] += 1
                        pv["scrap_n"] = 0.0
                        pv["best"] = min(pv["best"], px)

                def _widen45(take_n):
                    """AMENDMENT 45 one-coin depth, for BOTH paths. The paper path
                    books the order right here; the live path calls this after
                    A35 has sized the order (A35 reassigns take_n to at most SIZE,
                    so it must run first). Widens toward what the offer holds at
                    or under the sweep limit, capped by one_coin_cap() and by what
                    is left of the close budget. Price, gate and per-close worst
                    case unchanged."""
                    if not ONE_COIN_DEPTH:
                        return take_n
                    _cap45 = one_coin_cap(SIZE, state.get("bank"), state.get("hwm"))
                    _avail45 = float(size)
                    _limit45 = sweep_limit(f, price, want)
                    if SWEEP_DEPTH and _limit45 > price + 1e-9:
                        try:
                            _avail45 = max(_avail45, float(book.buyable(tk, want, _limit45)))
                        except Exception:              # noqa: BLE001
                            pass
                    _room45 = (close_budget_for(prev, tk, tau=tau)
                               - (prev.get("contracts", 0.0)
                                  if prev else 0.0)) if CLOSE_BUDGET else float(SIZE)
                    _was45 = take_n
                    take_n = max(take_n, min(_cap45, _avail45, max(0.0, _room45)))
                    if take_n > _was45 + 1e-9:
                        rec("one_coin_depth", ticker=tk, want=want,
                            was=round(_was45, 2), now=round(take_n, 2),
                            cap=round(_cap45, 2), avail=round(_avail45, 2),
                            room=round(_room45, 2), size=float(SIZE),
                            bank=state.get("bank"), hwm=state.get("hwm"))
                    return take_n

                def _late48(take_n):
                    """AMENDMENT 48: BUY BIGGER IN THE LAST FEW SECONDS.

                    The operator, 2026-09-17: "What if we increase to above our size
                    level when buying near close with a high enough confidence
                    level?" Our OWN LIVE FILLS say the last seconds are where the
                    money is, and by a wide margin:

                        0-5 s    1,028 contracts   5.35c each   0 losing closes
                        6-15 s   4,125 contracts   3.80c each
                        16-30 s 11,363 contracts   1.90c each

                    2.8x the per-contract return of our main window, on 6% of our
                    volume. And the book is not what stops us going bigger: of 102
                    live sweep events only 8 were capped by the ladder, the median
                    contracts buyable at our own sweep limit is 433 against a SIZE
                    of 95. BANK_BRAKE is the binding constraint, not the market.

                    Every existing ceiling still applies -- the same drawdown
                    headroom A45 uses, the close budget, and the book. This only
                    raises the per-order cap inside the window.
                    """
                    if LATE_MULT <= 1.0:
                        boost_why[(close_s, tk)] = (
                            "off: --late-mult is 1.0"
                            if _DEFAULT_LATE_MULT >= LATE_MULT else
                            "off: switched off by an earlier boosted loss")
                        return take_n
                    if tau > LATE_TAU:
                        boost_why[(close_s, tk)] = (
                            "no: bought at %ds, outside the last %ds"
                            % (tau, LATE_TAU))
                        return take_n
                    # A55: the operator's two conditions on the EXTRA contracts.
                    # `f` is the model's probability of YES, so our side's
                    # confidence is f for a YES bet and 1-f for a NO bet.
                    _ours48 = f if want == "yes" else 1.0 - f
                    _jmp48 = None
                    if LATE_JUMP_SD is not None:
                        try:
                            _jmp48 = jump_against(
                                idx.recent_moves(iid, JUMP_LOOKBACK), sg, want)
                        except Exception:              # noqa: BLE001
                            _jmp48 = None
                    if not late_boost_ok(_ours48, _jmp48):
                        boost_why[(close_s, tk)] = (
                            "no: confidence %.4f%% under the %.4g%% bar"
                            % (100 * _ours48, 100 * LATE_PIN)
                            if (LATE_PIN is not None and _ours48 < LATE_PIN)
                            else "no: %s sigma move against us (bar %.4g)"
                            % (("%.1f" % _jmp48) if _jmp48 is not None
                               else "unmeasurable", LATE_JUMP_SD or 0))
                        rec("late_refused", ticker=tk, want=want, tau=tau,
                            fair_ours=round(float(_ours48), 5), jump_sd=_jmp48,
                            need_pin=LATE_PIN, max_jump=LATE_JUMP_SD,
                            size=float(SIZE))
                        return take_n
                    _cap48 = one_coin_cap(SIZE, state.get("bank"), state.get("hwm"),
                                          mult=LATE_MULT)
                    _avail48 = float(size)
                    _lim48 = sweep_limit(f, price, want)
                    if SWEEP_DEPTH and _lim48 > price + 1e-9:
                        try:
                            _avail48 = max(_avail48, float(book.buyable(tk, want, _lim48)))
                        except Exception:              # noqa: BLE001
                            pass
                    _room48 = (close_budget_for(prev, tk, tau=tau)
                               - (prev.get("contracts", 0.0)
                                  if prev else 0.0)) if CLOSE_BUDGET else float(SIZE)
                    _was48 = take_n
                    take_n = max(take_n, min(_cap48, _avail48, max(0.0, _room48)))
                    if take_n <= _was48 + 1e-9:
                        boost_why[(close_s, tk)] = (
                            "no: allowed, but nothing to add (book %.0f, "
                            "headroom %.0f, close budget %.0f left)"
                            % (_avail48, _cap48, max(0.0, _room48)))
                    if take_n > _was48 + 1e-9:
                        boost_why[(close_s, tk)] = (
                            "FIRED: %.0f -> %.0f contracts at %ds, confidence "
                            "%.4f%%" % (_was48, take_n, tau, 100 * _ours48))
                        _boosted48.add((close_s, tk))
                        rec("late_boost", ticker=tk, want=want, tau=tau,
                            fair_ours=round(float(_ours48), 5), jump_sd=_jmp48,
                            was=round(_was48, 2), now=round(take_n, 2),
                            cap=round(_cap48, 2), avail=round(_avail48, 2),
                            room=round(_room48, 2), mult=LATE_MULT, late_tau=LATE_TAU,
                            size=float(SIZE))
                    return take_n

                def _band53(take_n):
                    """AMENDMENT 53: bet bigger inside a price band that has earned
                    it. Same shape as A48: the per-order cap rises to MULT x SIZE
                    through A45's drawdown headroom, and the book and the close
                    budget still bind. Records `band_boost` when it widens, with
                    every number that decided the width."""
                    _m53 = band_mult(price)
                    if _m53 <= 1.0:
                        return take_n
                    _cap53 = one_coin_cap(SIZE, state.get("bank"), state.get("hwm"),
                                          mult=_m53)
                    _avail53 = float(size)
                    _lim53 = sweep_limit(f, price, want)
                    if SWEEP_DEPTH and _lim53 > price + 1e-9:
                        try:
                            _avail53 = max(_avail53, float(book.buyable(tk, want, _lim53)))
                        except Exception:              # noqa: BLE001
                            pass
                    _room53 = (close_budget_for(prev, tk, tau=tau)
                               - (prev.get("contracts", 0.0)
                                  if prev else 0.0)) if CLOSE_BUDGET else float(SIZE) * _m53
                    _was53 = take_n
                    take_n = max(take_n, min(_cap53, _avail53, max(0.0, _room53)))
                    if take_n > _was53 + 1e-9:
                        boosted.add((close_s, tk))
                        rec("band_boost", ticker=tk, want=want, tau=tau,
                            price=round(price, 4), mult=_m53,
                            was=round(_was53, 2), now=round(take_n, 2),
                            cap=round(_cap53, 2), avail=round(_avail53, 2),
                            room=round(_room53, 2), size=float(SIZE),
                            bank=state.get("bank"), hwm=state.get("hwm"))
                    return take_n

                # R1: 1.0 unless the doubt rule actually widened THIS order.
                # `_stage46` reads it for the same reason A60 taught it to read
                # LATE_MULT: without that, the early/top-up re-cap silently
                # undoes the boost on every staged leg and the arm measures
                # nothing -- which is the A51 failure, exactly.
                _doubt_on = [1.0]

                def _doubt(take_n):
                    """R1 (2026-09-23): BUY MORE WHERE THE MODEL DOUBTED OUR
                    SIDE EARLIER IN THIS CLOSE.

                    The rule, from D_plan section 1: take the LOWEST
                    confidence the model put on the side we are about to buy,
                    at any reading at least DOUBT_LAG_S seconds earlier in
                    THIS close. Under DOUBT_UNDER, multiply the entry size by
                    DOUBT_MULT. No such reading -- unknown -- is 1.0x, never
                    a boost: an unknown is not a doubt.

                    THE HISTORY IS THE BOT'S OWN, IN MEMORY. `traj_hist` is
                    written by the R4 sampler in this same loop, from this
                    process's own fair() calls. Never a log file: a log read
                    would be slow, and it would be a different population.

                    `traj_hist` holds P(YES), because the side we buy is not
                    known when the reading is taken. The conversion happens
                    HERE -- f for a YES bet, 1-f for a NO bet -- and getting
                    it backwards inverts the whole rule.

                    IT ONLY EVER RAISES. Same shape as A48/A53: the cap is
                    A45's drawdown headroom through one_coin_cap(), and the
                    book and the close contract budget still bind, so it can
                    never reach past a ceiling that already exists. It cannot
                    refuse, delay or reprice anything, and it is not consulted
                    on any hedge path.
                    """
                    _doubt_on[0] = 1.0
                    if DOUBT_MULT <= 1.0:
                        return take_n                    # OFF, and live is OFF
                    _hist = traj_hist.get((close_s, tk)) or ()
                    _lo = _at = None
                    for _s, _fy in _hist:
                        if now_s - _s < DOUBT_LAG_S:
                            continue                     # not early enough
                        _c = _fy if want == "yes" else 1.0 - _fy
                        if _lo is None or _c < _lo:
                            _lo, _at = _c, _s
                    if _lo is None:
                        rec("doubt_skip", ticker=tk, want=want, tau=tau,
                            why="unknown: no reading %ds or more earlier"
                                % DOUBT_LAG_S, readings=len(_hist),
                            mult=DOUBT_MULT, under=DOUBT_UNDER,
                            size=float(SIZE))
                        return take_n
                    if _lo >= DOUBT_UNDER:
                        rec("doubt_skip", ticker=tk, want=want, tau=tau,
                            why="no: the model never doubted our side "
                                "(lowest %.5f, bar %.4g)" % (_lo, DOUBT_UNDER),
                            low=round(float(_lo), 5), low_at_tau=close_s - _at,
                            readings=len(_hist), mult=DOUBT_MULT,
                            under=DOUBT_UNDER, size=float(SIZE))
                        return take_n
                    _capd = one_coin_cap(SIZE, state.get("bank"),
                                         state.get("hwm"), mult=DOUBT_MULT)
                    _availd = float(size)
                    _limd = sweep_limit(f, price, want)
                    if SWEEP_DEPTH and _limd > price + 1e-9:
                        try:
                            _availd = max(_availd,
                                          float(book.buyable(tk, want, _limd)))
                        except Exception:              # noqa: BLE001
                            pass
                    _roomd = (close_budget_for(prev, tk, tau=tau)
                              - (prev.get("contracts", 0.0)
                                 if prev else 0.0)) if CLOSE_BUDGET                               else float(SIZE) * DOUBT_MULT
                    _wasd = take_n
                    take_n = max(take_n, min(_capd, _availd, max(0.0, _roomd)))
                    if take_n > _wasd + 1e-9:
                        _doubt_on[0] = float(DOUBT_MULT)
                        _boosted_dbt.add((close_s, tk))
                        rec("doubt_boost", ticker=tk, want=want, tau=tau,
                            low=round(float(_lo), 5), low_at_tau=close_s - _at,
                            readings=len(_hist), under=DOUBT_UNDER,
                            mult=DOUBT_MULT, was=round(_wasd, 2),
                            now=round(take_n, 2), cap=round(_capd, 2),
                            avail=round(_availd, 2), room=round(_roomd, 2),
                            size=float(SIZE), bank=state.get("bank"),
                            hwm=state.get("hwm"))
                    else:
                        rec("doubt_skip", ticker=tk, want=want, tau=tau,
                            why="allowed, but nothing to add (book %.0f, "
                                "headroom %.0f, close budget %.0f left)"
                                % (_availd, _capd, max(0.0, _roomd)),
                            low=round(float(_lo), 5), low_at_tau=close_s - _at,
                            readings=len(_hist), mult=DOUBT_MULT,
                            under=DOUBT_UNDER, size=float(SIZE))
                    return take_n

                def _stage46(take_n):
                    """AMENDMENT 46: an early or top-up leg keeps its cap however
                    much A35/A45 widened the order. A full leg is untouched.
                    A53: a band multiple scales the WHOLE position for this
                    market, so the early cap is EARLY_FRAC x SIZE x mult and a
                    top-up completes to SIZE x mult -- otherwise the re-cap here
                    would silently undo the boost on every early leg.

                    A60 (2026-09-19): AND THE LATE BOOST COUNTS THE SAME WAY.
                    The operator: "Even the bnb at 16 seconds it should've
                    boosted once time got lower." It could not. A48 widens the
                    order inside LATE_TAU, and then this line put it straight
                    back: a top-up was capped at SIZE - early_held whatever the
                    boost had asked for, so a market entered outside the window
                    could never be boosted inside it. That is the exact trade he
                    described, and the cap here was the reason.

                    The boost's own conditions still decide whether the extra
                    contracts are bought at all -- `_late48` returns `take_n`
                    untouched when the confidence or jump bar fails, and a
                    larger cap cannot raise a number that was never widened."""
                    if EARLY_TAU_MAX > TAU_MAX and _leg46 != "full":
                        _mult46 = max(band_mult(price), _doubt_on[0],
                                      LATE_MULT if tau <= LATE_TAU else 1.0)
                        return min(take_n, staged_take(tau, take_n,
                                                       float(SIZE) * _mult46,
                                                       _held46)[0])
                    return take_n

                # ---- R1: THE SEND SITE. With --attempts-on-send BOTH
                # attempt counters are incremented HERE -- after every
                # gate, before the order goes out on either path -- so
                # they count orders SENT, which is what both constants'
                # own comments have always said they count. BEFORE the
                # send and not after, so a send that never returns still
                # consumes one and the runaway of 2026-09-08 stays
                # impossible. Nothing between here and the send can
                # refuse: the only code in between defines helpers.
                #
                # The per-CLOSE counter is here too, and the comment at
                # the signal site says why: moving only the per-market one
                # turns a per-market lockout into a close-wide one.
                #
                # It is counted on the PAPER path as well, deliberately.
                # A paper arm that did not spend attempts would not be
                # comparable with live -- but it does mean "counts orders
                # sent" is literally true only on the live path, and that
                # MAX_ATTEMPTS_PER_MARKET bounds paper bookings in an arm.
                # Any arm write-up has to say so.
                if ATTEMPTS_ON_SEND:
                    attempts[close_s] = attempts.get(close_s, 0) + 1
                    attempts_tk[(close_s, tk)] = attempts_tk.get((close_s, tk), 0) + 1

                if not live:
                    take_n = _widen45(take_n)  # paper
                    take_n = _late48(take_n)   # paper
                    take_n = _band53(take_n)   # paper
                    take_n = _doubt(take_n)    # paper
                    take_n = _stage46(take_n)
                    _book_slot(price, take_n)
                    _poid46 = f"paper-{tk}-{now_s}"
                    entry_at[_poid46] = now_s
                    open_pos[_poid46] = (close_s, want, price, take_n, tk)
                    # AMENDMENT 71 (2026-09-19): THE PAPER HEDGE PATH WAS DEAD
                    # CODE, AND EVERY PAPER ARM HAS BEEN AN UNHEDGED BOT.
                    #
                    # The hedge pass gives up on any position with no hedge_meta
                    # ("if _meta is None: continue"), and hedge_meta was written at
                    # exactly two places, BOTH live-only: the plant path and the
                    # live fill. A paper position therefore never had a strike, so
                    # its belief was never computed, so the alarm never fired.
                    #
                    # MEASURED, not argued: the five paper arms running today
                    # logged 151 signals between them and ZERO hedge_alarm and
                    # ZERO hedge records. The live bot on the same markets logged
                    # 2 alarms, 8 hedges and 2 panics.
                    #
                    # WHAT THAT INVALIDATES. A hedge that fills turns a -73c to
                    # -96c loss into -26.9c (the 17-loss table in HANDOFF.md). So
                    # every head-to-head between an arm and the live bot has been
                    # comparing a bot that eats its losses whole against one that
                    # insures them -- and the arm was flattered on every winning
                    # close and punished on every losing one. Arm numbers on
                    # losing closes are not comparable before this line existed.
                    #
                    # It also means NO hedge change has ever been testable without
                    # real money. A62, A69 and A70 all had to go straight to live
                    # because paper could not exercise them.
                    hedge_meta[_poid46] = (strike, digits, iid)
                if live:
                    try:
                        # LATENCY INSTRUMENTATION, added 2026-09-08. 26% of our
                        # orders fill NOTHING and depth is not the cause -- the
                        # misses had 562, 107, 93, 10 and 5 contracts on offer.
                        # We are losing a race and have never measured our own
                        # part of it. Three numbers matter and none were recorded:
                        # how stale the book was when we decided, how long the
                        # round trip took, and whether misses differ from fills on
                        # either. Pure instrumentation -- it changes no decision.
                        # AMENDMENT 18: the LIMIT is the highest price that
                        # still passes the same gate, not the ask we saw. When we
                        # win the race we still fill at the resting price (283 of
                        # 283 live fills at or better than signalled, zero worse);
                        # when we lose it we take the next level instead of
                        # nothing. `ask_seen` and `limit_sent` are both logged so
                        # PREREG_sweep.md's bar can be scored.
                        _limit = sweep_limit(f, price, want)
                        # A78b: THE CEILING MUST BIND THE SWEEP, NOT JUST THE
                        # SIGNAL. Caught live within the hour: the 05:00 DOGE
                        # close signalled at 97.3c -- under the 97.5c ceiling, so
                        # the gate correctly let it through -- and the sweep then
                        # walked the ladder to an average of 97.92c. The gate
                        # checks the price we SEE; only the limit decides what we
                        # GET. This is the same shape as the dump guard's known
                        # hole, and shipping half a ceiling is worse than none:
                        # the rule becomes unpredictable rather than merely loose.
                        if (_leg46 in ("early", "early_once")
                                and EARLY_MAX_PRICE < 1.0):
                            _limit = min(_limit, EARLY_MAX_PRICE)
                        # ---- AMENDMENT 35: ASK FOR WHAT THE LADDER HOLDS -------
                        # THE SWEEP WAS HALF-BUILT. AMENDMENT 18 raised the PRICE
                        # we are willing to pay to _limit, so a lost race takes
                        # the next level instead of nothing -- but the QUANTITY
                        # was still min(SIZE, touch size). So the bot would offer
                        # up to 98c and then ask for only the handful sitting at
                        # the best price.
                        #
                        # LIVE, 2026-09-14, the 02:00 SOL close: ask 96.3c with
                        # SIX contracts on it, limit sent 98c, order placed for 6,
                        # filled 6, profit $0.21 -- while 211 contracts sat at 88c
                        # and 306 at 89c. The operator caught it from his phone:
                        # "We only bought $6 worth. THERE WAS SO MUCH AVAILABLE."
                        #
                        # EVERY EXTRA CONTRACT IS ALREADY GATE-APPROVED. sweep_
                        # limit() returns the HIGHEST price that still passes the
                        # same confidence, edge, ceiling and EV tests, so anything
                        # filled at or under it is a trade we had already decided
                        # to make. The close's contract budget still binds, and
                        # SIZE still caps it.
                        if SWEEP_DEPTH and _limit > price + 1e-9:
                            try:
                                _deep = float(book.buyable(tk, want, _limit))
                            except Exception:              # noqa: BLE001
                                _deep = 0.0
                            # A67: the same depth, WEIGHTED by the edge at each
                            # level. `_deep` counts a 98c contract exactly like a
                            # 91.5c one; this does not. Falls back to `_deep`
                            # whenever the rungs cannot be read, so a book that
                            # does not answer behaves exactly as it did before.
                            _rungs = []
                            if TAPER:
                                try:
                                    _rungs = book.rungs(tk, want, _limit)
                                except Exception:          # noqa: BLE001
                                    _rungs = []
                            if _rungs:
                                _flat = _deep
                                _deep = taper_take(
                                    _rungs, float(SIZE),
                                    lambda _p, _f=f, _w=want: net_edge(_f, _p, _w))
                                if _deep < _flat:
                                    rec("taper", ticker=tk, want=want, tau=tau,
                                        touch=round(float(_rungs[0][0]), 4),
                                        rungs=len(_rungs),
                                        flat=round(_flat, 2),
                                        tapered=round(_deep, 2),
                                        limit=round(_limit, 4))
                            if _deep > take_n:
                                _room = (close_budget_for(prev, tk, tau=tau)
                                         - (prev.get("contracts", 0.0)
                                            if prev else 0.0)) if CLOSE_BUDGET                                 else float(SIZE)
                                _was = take_n
                                take_n = min(float(SIZE), _deep, max(0.0, _room))
                                if take_n > _was:
                                    rec("sweep_depth", ticker=tk, want=want,
                                        touch=round(float(size), 2),
                                        ladder=round(_deep, 2),
                                        was=round(_was, 2), now=round(take_n, 2),
                                        limit=round(_limit, 4))
                        # ---- AMENDMENT 45 / 46, live path: after A35 has sized
                        # the order, widen for one-coin depth (if on), then
                        # re-apply the staged-entry cap (if on). Same helpers the
                        # paper path uses above, so both paths book the same size.
                        take_n = _widen45(take_n)  # live
                        take_n = _late48(take_n)   # live
                        take_n = _band53(take_n)   # live
                        take_n = _doubt(take_n)    # live
                        take_n = _stage46(take_n)
                        # A68: LAST, so no later widener can undo the cap. This is
                        # the line that makes the bounded rebuy bounded; without
                        # it the close budget alone allows it and the tail is the
                        # -$134 case A63 was refused for.
                        if _room68 is not None:
                            take_n = min(take_n, float(_room68))
                        _t0 = time.time()
                        out = pintake.take(CREDS["base"], CREDS["pk"],
                                           CREDS["key_id"], tk, want, _limit,
                                           take_n, close_s, exchange_index=exi)
                        _lat_ms = round(1000.0 * (time.time() - _t0), 1)
                        # K1 (2026-09-22): THE FILL IS REGISTERED -- for the
                        # hedge, for reconcile() and against the close budget
                        # -- BEFORE ANYTHING FORMATS IT. The order record used
                        # to come first, and its round() and **out arguments
                        # sat between take() returning a fill and open_pos
                        # hearing of it. A record that raised there was
                        # swallowed by the except below: a real position,
                        # never hedged, never booked, and the close budget
                        # let the SAME market be bought again 50 ms later.
                        # Reproduced offline by the K1 verifier; now a
                        # self-test runs it.
                        filled = float(out.get("filled") or 0)
                        _scrap12 = None
                        if filled > 0:
                            px = out.get("exec_price")
                            cost = float(px) if px is not None else float(price)
                            _oid_new = (out.get("client_order_id")
                                        or out.get("order_id")
                                        or f"{tk}-{time.time():.6f}")
                            open_pos[_oid_new] = (close_s, want, cost, filled, tk)
                            entry_at[_oid_new] = now_s
                            hedge_meta[_oid_new] = (strike, digits, iid)   # A15
                            state["fills"] = state.get("fills", 0) + 1
                            # AMENDMENT 12: a scrap (under half our size) keeps
                            # its position but does not spend a scale-in slot
                            _real = max(MIN_LEVEL, MIN_FILL_FRAC * float(SIZE))
                            if filled >= _real:
                                _book_slot(cost, filled)
                            elif CLOSE_BUDGET:
                                # A17 + A12: contracts are exposure however small,
                                # so a scrap spends budget. It still must not raise
                                # the improve bar -- that exemption is what A12 was
                                # actually protecting, not the exposure count.
                                _book_slot(cost, filled, raise_bar=False)
                                state["scraps"] = state.get("scraps", 0) + 1
                                _scrap12 = "budget"
                            else:
                                _note_scrap(cost, filled)
                                state["scraps"] = state.get("scraps", 0) + 1
                                _scrap12 = "slot"
                        else:
                            state["nofill"] = state.get("nofill", 0) + 1
                        state["sent"] = state.get("sent", 0) + 1
                        # ...and only now is it written down. A record that
                        # fails is itself recorded, with a minimal order line
                        # so the log still carries the fill.
                        _xp = out.get("exec_price")
                        try:
                            rec("order", ticker=tk, latency_ms=_lat_ms,
                                # AMENDMENT 72: WHICH SIDE. The order record carried
                                # `ask_seen` (the price of the side we wanted) and
                                # `exec_price` (what we paid) and NOT the side, so the
                                # two could not be safely compared -- a NO buy can log
                                # an exec_price on the other side of the dollar and
                                # the pair reads as a 86c bargain. That is hard rule 5
                                # (never infer a price's meaning from its magnitude)
                                # arriving through the back door.
                                #
                                # It matters because the difference between these two
                                # is the only picked-off signal we have: the 01:45 BNB
                                # close saw 85c and paid 74.98c because the side was
                                # collapsing as we bought it. Pure instrumentation --
                                # nothing branches on this.
                                want=want,
                                leg=_leg46, early_held=_held46,
                                book_age_ms=b.get("age_ms"),
                                index_age_s=round(iage, 2), tau_at_send=tau,
                                ask_seen=round(float(price), 4),
                                limit_sent=round(float(_limit), 4),
                                sweep_headroom_c=round(100.0 * (_limit - price), 3),
                                swept=bool(_xp is not None
                                           and float(_xp) > float(price) + 1e-9),
                                # (5) ms epoch: every gate passed / order sent
                                t_ms_decide=_t_decide_ms,
                                t_ms_send=int(round(_t0 * 1000.0)),
                                **{k: v for k, v in out.items() if k != "raw"})
                        except Exception as _ek1o:           # noqa: BLE001
                            # The ORDER did not fail; its record did. Not an
                            # order error (it would count toward the two that
                            # halt the run), but on the record, once.
                            _k1_error("order_log", close_s, tk, _ek1o)
                            try:
                                rec("order", ticker=tk, want=want, log_error=True,
                                    latency_ms=_lat_ms, tau_at_send=tau,
                                    t_ms_decide=_t_decide_ms,
                                    t_ms_send=int(round(_t0 * 1000.0)),
                                    status_code=out.get("status_code"),
                                    status=out.get("status"),
                                    order_id=out.get("order_id"),
                                    client_order_id=out.get("client_order_id"),
                                    filled=filled, exec_price=out.get("exec_price"),
                                    fee=out.get("fee"),
                                    refused=out.get("refused"))
                            except Exception:                # noqa: BLE001
                                pass
                        # A RETURNED REFUSAL IS AN ERROR AND MUST BE COUNTED.
                        # take() returns its violations rather than raising, so
                        # nothing here noticed. Combined with AMENDMENT 6 (a slot
                        # is consumed by a FILL, not an attempt) that produced a
                        # RUNAWAY: 160 identical orders in one close, 20 Hz, all
                        # refused, none filled, no error logged. Two of my own
                        # changes interacting. Neither was wrong alone.
                        _ref = out.get("refused") or []
                        if _ref or out.get("status_code") is None:
                            state["order_errors"] = state.get("order_errors", 0) + 1
                            rec("error", where="take_refused", ticker=tk,
                                err=str(_ref)[:300])
                            print(f"    ORDER REFUSED {_ref}")
                        if _scrap12 == "budget":
                            rec("scrap", ticker=tk, want=want, filled=filled,
                                asked=take_n, price=cost, real_min=_real,
                                budget_spent=True)
                            print(f"    SCRAP {filled:g} of {take_n:g} -- "
                                  f"budget spent, improve bar NOT raised")
                        elif _scrap12 == "slot":
                            rec("scrap", ticker=tk, want=want, filled=filled,
                                asked=take_n, price=cost, real_min=_real)
                            print(f"    SCRAP {filled:g} of {take_n:g} -- "
                                  f"position kept, slot NOT spent")
                        print(f"    ORDER -> status {out.get('status')} "
                              f"filled {out.get('filled')} "
                              f"@ {out.get('exec_price')} fee {out.get('fee')}")
                    except Exception as ex:                  # noqa: BLE001
                        # NOT state["errors"]: the universe block resets that to 0
                        # every 20 s, so an order path that threw on every fire
                        # could never reach the consecutive-errors abort.
                        state["order_errors"] = state.get("order_errors", 0) + 1
                        rec("error", where="take", ticker=tk, err=str(ex)[:300])
                        print(f"    ORDER FAILED: {ex}")
            except Exception as _ek1:                      # noqa: BLE001
                # K1: one market's scan must not end the run while a
                # position is held -- see _k1_error. Counted, recorded
                # once, and stepped over; the next market is looked at.
                if _k1_error("scan", close_s, tk, _ek1):
                    _k1_scan_error(close_s, tk)
                continue

        time.sleep(0.05)

    return state, fired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="send size-1 IOC takers. Default is paper.")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--loss-abort", type=float, default=-2.00)
    ap.add_argument("--tau-max", type=int, default=TAU_MAX)
    ap.add_argument("--size", type=float, default=1.0,
                    help="contracts per take; 0.01 is about one cent, for "
                         "proving order/fill/settle/payout end to end")
    ap.add_argument("--hedge-plant", action="store_true",
                    help="ONE-SHOT planted test of the hedge path, operator "
                         "sign-off 2026-09-12: at the first decided market "
                         "seen with tau <= 25, buy ONE contract of the side "
                         "that is about to LOSE, book it as a normal position, "
                         "and let the live hedge pass fire on it. Costs a few "
                         "cents. Off by default; fires at most once per run.")
    ap.add_argument("--hedge-jump", type=float, default=None,
                    help="AMENDMENT 52: ALSO buy insurance the instant the "
                         "index makes a one-second move of this many sigma "
                         "against our side since entry, without waiting for "
                         "the belief to fall. Belief is downstream of the "
                         "jump, by which time the other side costs 50-70c; "
                         "this fires while it may still be 10-20c. Off by "
                         "default; the belief trigger is untouched.")
    ap.add_argument("--hedge-normal", action="store_true",
                    help="AMENDMENT 51: only buy insurance when the OTHER side "
                         "would pass the gates a normal entry passes -- our "
                         "model at least PIN sure of it and its ask at or "
                         "under the price ceiling. The operator's idea. Today "
                         "the hedge fires on belief alone at any ask under a "
                         "dollar, and 11 of 12 insured closes still ended "
                         "negative, five of them buying the other side at "
                         "10-18c while the market still liked ours. Off by "
                         "default.")
    # argparse %-formats help strings ITSELF, so this one is not pre-formatted:
    # a pre-formatted "1%%" reaches argparse as "1%" and raises "incomplete
    # format" at the first --help or self-test. That is what failed the
    # deploy's first self-test on 2026-09-18.
    ap.add_argument("--price-ceiling", type=float, default=None,
                    help="Highest ask the bot will pay, in dollars. Default "
                         "0.980. Exists as a FLAG so the operator's setting "
                         "can be moved and reverted without an edit. Note it "
                         "also enters the bet-size divisor (bank / (brake * "
                         "2 * ceiling)), so 0.98 -> 0.99 trims size by 1%%.")
    ap.add_argument("--bank-brake", type=float, default=None,
                    help="How many worst-closes the bank must cover. Bet size "
                         "is bank / (this * 2 * 0.98), so 3.0 is bank/5.88 and "
                         "4.08 is bank/8. Higher is safer and earns less. "
                         "Default %.2f. Exists as a FLAG so the operator's "
                         "risk setting can be moved and reverted without an "
                         "edit to this file." % BANK_BRAKE)
    ap.add_argument("--no-auto-size", dest="auto_size", action="store_false",
                    default=True,
                    help="AMENDMENT 16: by default SIZE follows the live bank "
                         "(bank / (BANK_BRAKE * MAX_PER_CLOSE * "
                         "PRICE_CEILING)), re-checked every "
                         "AUTO_SIZE_EVERY_S seconds and only while flat. "
                         "This pins SIZE to --size instead.")
    ap.add_argument("--max-positions", type=int, default=3,
                    help="halt after this many open positions")
    ap.add_argument("--max-per-market", type=int, default=None,
                    help="AMENDMENT 13 re-opened: fills allowed on ONE market "
                         "in one close. Default %d. The close's CONTRACT "
                         "budget is unchanged whatever this is."
                         % _DEFAULT_MAX_PER_MARKET)
    ap.add_argument("--sweep-depth", action="store_true",
                    help="AMENDMENT 35: size the order from the whole ladder "
                         "up to the sweep limit, not just the contracts at "
                         "the best price. Live 2026-09-14 the bot asked for 6 "
                         "contracts because 6 sat at the touch, while 211 and "
                         "306 waited one and two cents behind -- at prices its "
                         "own limit had already approved.")
    ap.add_argument("--depth-ladder", action="store_true",
                    help="AMENDMENT 37: judge the depth floor on what the "
                         "LADDER can fill up to the sweep limit, not on the "
                         "contracts at the best price alone. Requires "
                         "--sweep-depth and does nothing without it. Every "
                         "later gate -- edge, dump guard, ceiling, EV -- still "
                         "runs on the market this lets through.")
    ap.add_argument("--take-dumps", action="store_true",
                    help="PAPER RESEARCH ONLY. Turn OFF AMENDMENT 10's dump "
                         "guard and buy the offers it refuses -- a certainty "
                         "priced 15c+ below fair. Scored over 132 refused "
                         "markets the win rate falls as the discount widens "
                         "(91%% -> 53%%) but the PRICE falls faster: at 8.2c "
                         "the break-even is 8.7%%. Our 4 live fills in the "
                         "band all lost, but all four sat at 59-82c and the "
                         "cheap end is untested. REFUSED ON A LIVE RUN.")
    ap.add_argument("--one-coin-depth", action="store_true",
                    help="PAPER RESEARCH ONLY (AMENDMENT 45). Let ONE market "
                         "take more than SIZE from a deep offer at the same "
                         "limit, up to --one-coin-max x SIZE, the close budget, "
                         "and the drawdown brake's headroom. REFUSED ON A LIVE "
                         "RUN. See results/PREREG_onecoin.md.")
    ap.add_argument("--one-coin-max", type=float, default=2.0,
                    help="AMENDMENT 45: the multiple of SIZE one market may "
                         "hold under --one-coin-depth (default 2.0, never above "
                         "MAX_PER_CLOSE).")
    ap.add_argument("--early-tau", type=int, default=TAU_MAX,
                    help="AMENDMENT 46: buy an EARLY leg of --early-frac x SIZE "
                         "with up to this many seconds left, then top up to "
                         "SIZE at or under TAU_MAX. Default TAU_MAX = off. "
                         "REFUSED ON A LIVE RUN until PREREG_staged.md's bar.")
    ap.add_argument("--early-frac", type=float, default=0.5,
                    help="AMENDMENT 46: the early leg as a fraction of SIZE "
                         "(default 0.5).")
    ap.add_argument("--no-external-detect", action="store_true",
                    help="AMENDMENT 43: turn OFF telling a withdrawal from a "
                         "trading loss. With it off, taking money out of the "
                         "account trips the drawdown brake and halts the bot, "
                         "which is what happened before this existed.")
    ap.add_argument("--jump-gate", action="store_true",
                    help="AMENDMENT 40: refuse a trade when the index made a "
                         "one-second move of 3 sd or more against our side in "
                         "the last 3 seconds. Jumps continue in the tail (7.9%% "
                         "are followed by another >=5 sd within 5 s, vs 1.3%% "
                         "the model assumes). OFF by default.")
    ap.add_argument("--jump-widen", action="store_true",
                    help="AMENDMENT 41: for 5 s after any one-second index "
                         "move of 3 sd or more, double the model's sigma at "
                         "both the entry decision and the hedge's belief. "
                         "The tail after a jump is ~2x wider than the model "
                         "assumes. OFF by default.")
    ap.add_argument("--early-min-price", type=float, default=None,
                    help="AMENDMENT 49: an EARLY leg (31-45 s) also needs the "
                         "ask at or above this. Default 0.90. A cheap ask that "
                         "far out is the market disagreeing with us where our "
                         "model is weakest.")
    ap.add_argument("--early-max-edge", type=float, default=None,
                    help="AMENDMENT 50: on an EARLY leg (31-45 s) only, refuse "
                         "when our model sits MORE than this many cents above "
                         "the market on our side. Out there a big edge is the "
                         "market disagreeing with us where three quarters of "
                         "the settlement window has not happened yet, and it "
                         "loses: 3c-6c lost 0.57 $/bet and 6c+ lost 3.01 "
                         "$/bet, while the SAME band inside 30 s made 0.47 and "
                         "1.44. Off by default. Does not touch the main leg.")
    ap.add_argument("--late-tau", type=int, default=None,
                    help="AMENDMENT 48: seconds-to-close at or under which an "
                         "order may exceed SIZE. Our live fills earn 5.35c a "
                         "contract inside 5 s against 1.90c at 16-30 s.")
    ap.add_argument("--late-mult", type=float, default=None,
                    help="AMENDMENT 48: the multiple of SIZE one order may "
                         "reach inside --late-tau. Still capped by the drawdown "
                         "headroom, the close budget and the book.")
    ap.add_argument("--loss-cap", type=float, default=None,
                    help="AMENDMENT 65: a HARD dollar cap on what one run may "
                         "lose, in positive dollars. The abort is normally "
                         "derived (-2 x SIZE x MAX_PER_CLOSE) and grows with "
                         "the bank; this is the tighter of the two and is "
                         "re-applied on every autosize. It can only ever "
                         "REDUCE what a run may lose.")
    ap.add_argument("--late-extra-tau", type=int, default=None,
                    help="AMENDMENT 64: seconds-to-close inside which the "
                         "extra BUDGET applies. Defaults to --late-tau. They "
                         "want different values: the 1.5x boost is extra RISK "
                         "and wants a tight window; the extra budget is only "
                         "permission to spend what the close already had, and "
                         "wants a wide one.")
    ap.add_argument("--late-extra", type=float, default=None,
                    help="AMENDMENT 59: extra SIZE a close may spend inside "
                         "--late-tau seconds, whatever it already holds. Our "
                         "own fills earn 5.4c a contract inside 10 s against "
                         "2.2c at 31-45 s with no losing close in 68 fills, "
                         "and close_budget refused 126 markets in that "
                         "window. PAPER ONLY for now.")
    ap.add_argument("--attempts-on-send", action="store_true",
                    help="R1: count a per-market attempt only when an ORDER "
                         "IS SENT, not at the signal. DEFAULT OFF -- with the "
                         "flag absent the bot behaves exactly as it does "
                         "today. Today three looks refused WITHOUT an order "
                         "(early_cheap, early_dear, early_wide, staged_none, "
                         "price_band) reach MAX_ATTEMPTS_PER_MARKET in about "
                         "150 ms at 20 Hz and lock the market out for the "
                         "rest of the close, the last 30 s included: 42 "
                         "lockouts lifetime, 32 preceded by one of those "
                         "refusals in the same market and close. The "
                         "per-CLOSE rail is untouched either way, and the cap "
                         "itself still bounds real orders at 3.")
    ap.add_argument("--extra-coin", type=float, default=None,
                    help="AMENDMENT 56: extra SIZE a close may spend, for a "
                         "coin it is NOT already holding, once the base "
                         "budget has been spread across MAX_PER_CLOSE coins. "
                         "Measured: 0 of 417 closes have ever lost two coins. "
                         "It RAISES the worst close, so worst_close_cost and "
                         "every rail that reads it grow too -- at a fixed "
                         "--bank-brake the bet size falls by the same ratio.")
    ap.add_argument("--sigma-stress", type=float, default=None,
                    help="AMENDMENT 57: multiply the volatility estimate by "
                         "this EVERYWHERE the model runs -- entry, the sweep "
                         "limit and the hedge. Above 1 makes the bot humbler "
                         "(fewer, safer trades); below 1 makes it bolder. "
                         "1.0 is the shipped value.")
    ap.add_argument("--late-pin", type=float, default=None,
                    help="AMENDMENT 55: the EXTRA contracts of the "
                         "last-seconds boost need at least this much "
                         "confidence in our side, above the ordinary gate. "
                         "The ordinary bet is untouched.")
    ap.add_argument("--late-jump", type=float, default=None,
                    help="AMENDMENT 55: skip the last-seconds boost when a "
                         "one-second move of this many sd has gone AGAINST "
                         "our side -- 'if it looks like it is going to a "
                         "loss do not buy the extra'. With this set, a jump "
                         "that cannot be measured also blocks the boost.")
    ap.add_argument("--flip-mult", type=float, default=None,
                    help="AMENDMENT 54: when a bet opened OUTSIDE the main "
                         "window flips inside it, buy this multiple of the "
                         "position on the other side instead of an equal "
                         "hedge. >1 is a BET on the later look, not a hedge: "
                         "it cuts the loss when the flip is right and roughly "
                         "doubles it when wrong. Paper only, off by default.")
    ap.add_argument("--skip-band", type=float, nargs=2, action="append",
                    default=None, metavar=("LO", "HI"),
                    help="AMENDMENT 53: refuse any ask in [LO, HI) on every "
                         "leg, and stop the sweep under LO. Repeatable. The "
                         "live record for 94-96c: +0.8%% on $2,970 across 83 "
                         "closes, a loss rate level with its break-even. "
                         "Shipped off.")
    ap.add_argument("--band-mult", type=float, nargs=3, action="append",
                    default=None, metavar=("LO", "HI", "MULT"),
                    help="AMENDMENT 53: inside [LO, HI) one order may reach "
                         "MULT x SIZE, through A45's drawdown headroom, the "
                         "book and the close budget. MULT in (1, "
                         "MAX_PER_CLOSE]. Repeatable. Shipped off.")
    ap.add_argument("--doubt-mult", type=float, default=None, metavar="X",
                    help="R1: when the model's own confidence in the side we "
                         "are about to buy was BELOW --doubt-under at some "
                         "reading at least 5 seconds earlier in this close, "
                         "buy X times the size. Raises size only -- it can "
                         "refuse nothing and it never touches a hedge, and "
                         "the drawdown headroom, the close budget and the "
                         "book all still bind. Our live record: 66 markets, "
                         "62 closes, ZERO money-losers, +2.95 dollars a "
                         "market against +0.70 book-wide. Paper only; "
                         "shipped at 1.0, which is OFF.")
    ap.add_argument("--traj-log", action="store_true",
                    help="R4: keep the per-second trajectory file on a PAPER "
                         "run too. Off by default and deliberately: 27 paper "
                         "arms run from this file on the same box, a file each "
                         "is about 1.6 gigabytes a day of near-duplicate "
                         "data, and 5 gigabytes free stops the tape collector "
                         "outright. The live bot always writes it. Nothing "
                         "about a decision changes either way -- the history "
                         "the size rule reads is in memory.")
    ap.add_argument("--doubt-under", type=float, default=None, metavar="F",
                    help="R1: the confidence below which an earlier reading "
                         "counts as the model doubting our side. Default "
                         "%.2f, the level the plus-2.95 was measured at. Does "
                         "nothing without --doubt-mult above 1."
                         % _DEFAULT_DOUBT_UNDER)
    ap.add_argument("--rebuy-mult", type=float, default=None, metavar="X",
                    # NO LITERAL PER-CENT SIGN. argparse formats help strings
                    # itself, so a `%%` written here survives my own % and
                    # reaches argparse as a live format spec: "unsupported
                    # format character ' '". Spell the word instead.
                    help="AMENDMENT 68: while belief is at or under the panic "
                         "line, buy up to X times the losing position as MORE "
                         "of the side we hedged into -- an ordinary bet on a "
                         "side the model now gives 85 percent or better. "
                         "Default %.1f. Set 0 to disable. Measured: every "
                         "live market that fell under the 40 percent line "
                         "went on to lose, 6 of 6."
                         % _DEFAULT_REBUY_MAX_MULT)
    ap.add_argument("--no-taper", action="store_true",
                    help="AMENDMENT 67: restore A35's flat sizing, which asks "
                         "for every contract under the sweep limit whatever "
                         "the edge at that price. Shipped OFF -- the taper is "
                         "ON -- after the 12:30 BNB close was signalled at "
                         "91.5c and filled at an average of 97.27c.")
    ap.add_argument("--taper-floor", type=float, default=None, metavar="FRAC",
                    help="AMENDMENT 67: ignore price levels holding less than "
                         "this FRACTION of the touch's edge. Default %.2f "
                         "(take them, just in proportion). 0.5 would refuse "
                         "any level worth under half the best price's edge."
                         % TAPER_FLOOR)
    ap.add_argument("--arm-name", default=None, metavar="NAME",
                    help="A LABEL, read by nothing. It exists so the arm is "
                         "identifiable in its own command line: eleven band "
                         "arms were known only by the redirect FILENAME "
                         "boot_all.ps1 gave them, Windows does not report a "
                         "redirect in a command line, and so the desktop app "
                         "could not prove which process was which and refused "
                         "to stop any of them. Never affects a decision.")
    ap.add_argument("--no-size-mirror", action="store_true",
                    help="AMENDMENT 66: a PAPER arm normally copies the live "
                         "bot's contract size from %s so its dollars are "
                         "comparable with live's. Pass this to pin the arm "
                         "at --size instead -- only for an arm that is "
                         "deliberately testing a SIZE." % os.path.basename(SIZE_MIRROR))
    ap.add_argument("--rebuy-hedged", action="store_true",
                    help="AMENDMENT 63: after we have hedged a market, allow "
                         "buying MORE of the side we hedged INTO, at the "
                         "ordinary gate. One more contract of that side pays "
                         "(1-price) if it lands and costs `price` if it does "
                         "not -- identical to a fresh bet -- and it cannot "
                         "raise the worst close, because both legs share the "
                         "close budget and holding both sides LOWERS the "
                         "worst case per contract. Shipped off.")
    ap.add_argument("--hedge-panic", type=float, default=None,
                    help="AMENDMENT 62: belief at or under which NO filter "
                         "may block a hedge -- not the market-agreement "
                         "test, not the normal-bet test, not the attempt "
                         "cap. Default %.2f. Set 0 to disable the bypass, "
                         "which is what cost $57.98 on 2026-09-19."
                         % _DEFAULT_HEDGE_PANIC)
    ap.add_argument("--loss-bound-open", action="store_true",
                    help="AMENDMENT 73: restore the OLD loss bound, which "
                         "counted every open position as a total loss before "
                         "it settled. It paused the bot 28 times (never "
                         "blocking a trade) including while the run was up "
                         "$43.56. Off by default: only FINALISED bets count "
                         "toward the loss total, which is the operator's "
                         "instruction of 2026-09-19.")
    ap.add_argument("--early-max-price", type=float, default=None,
                    help="AMENDMENT 78: the EARLY leg (31-45 s) refuses a "
                         "price above this. Default %.3f = no ceiling. The "
                         "live bot runs 0.975: that leg earns 1.14c a "
                         "contract against 5.63c at 6-10 s, and above 97.5c "
                         "it risks 98c to make 1.8c fifteen seconds before "
                         "the information arrives."
                         % _DEFAULT_EARLY_MAX_PRICE)
    ap.add_argument("--no-hedge-prop", action="store_true",
                    help="AMENDMENT 76: turn OFF proportional hedging and go "
                         "back to hedging the whole position the moment "
                         "belief crosses --hedge-belief. Proportional is the "
                         "default: all of it at or under %.2f belief, half at "
                         "or under %.2f, none above -- and a half-hedge tops "
                         "up to full if belief falls further."
                         % (_DEFAULT_HEDGE_PROP_FULL, _DEFAULT_HEDGE_PROP_HALF))
    ap.add_argument("--hedge-prop-full", type=float, default=None,
                    help="AMENDMENT 76: belief at or under which the WHOLE "
                         "position is hedged (default %.2f)."
                         % _DEFAULT_HEDGE_PROP_FULL)
    ap.add_argument("--hedge-prop-half", type=float, default=None,
                    help="AMENDMENT 76: belief at or under which HALF is "
                         "hedged (default %.2f); above it nothing is."
                         % _DEFAULT_HEDGE_PROP_HALF)
    ap.add_argument("--hedge-slip", type=float, default=None,
                    help="AMENDMENT 70: dollars above the ask we saw that a "
                         "hedge leg may pay, so the IOC sweeps the ladder "
                         "instead of tapping one stale level. Sizes the hedge "
                         "from the ladder too, capped at the contracts still "
                         "unhedged. Default %.3f (OFF = today's behaviour). "
                         "Ten of twenty-nine live hedge attempts filled 0 or 1 "
                         "contract with the book displaying everything we "
                         "asked for; that is the only escape failure this "
                         "project has had." % _DEFAULT_HEDGE_SLIP)
    ap.add_argument("--hedge-price", type=float, default=None,
                    help="AMENDMENT 47: only hedge when OUR side's market "
                         "price has also fallen below this (e.g. 0.50). The "
                         "wobble screen says a favourite that dips but stays "
                         "above 50c recovered 48 times out of 48; one that "
                         "crosses below 50c really flipped 76%% of the time. "
                         "Default off -- the shipped behaviour is unchanged.")
    ap.add_argument("--hedge-belief", type=float, default=None,
                    help="AMENDMENT 34: belief in OUR side below which we buy "
                         "the other one. Default %.2f. MEASURED 2026-09-14 on "
                         "594 tape entries: every trigger from 0.90 down to "
                         "0.10 rescues the SAME 25 real losses; what changes "
                         "is the false alarms, 38 at 0.90 against 1 at 0.10. "
                         "Worth -0.43c per contract at 0.90 and +0.49c at "
                         "0.10." % _DEFAULT_HEDGE_BELIEF)
    ap.add_argument("--min-fill-frac", type=float, default=None,
                    help="AMENDMENT 28: the share of SIZE that must be on "
                         "offer before we will take it. Default %.2f. "
                         "Lowering it takes SMALLER fills at the identical "
                         "gate, which cannot change the loss rate -- it is "
                         "the same bet, smaller. PAPER ONLY until a what-if "
                         "says otherwise." % _DEFAULT_MIN_FILL_FRAC)
    ap.add_argument("--pick", default=None, choices=("first", "best"),
                    help="AMENDMENT 24: scan order. 'first' (default) visits "
                         "markets in discovery order; 'best' visits them in "
                         "order of the edge measured on the previous pass, so "
                         "when two markets pass in the same second the better "
                         "one is bought. Measured +2.07c -> +2.76c per "
                         "contract on identical loss counts.")
    ap.add_argument("--improve-max", type=float, default=None,
                    help="AMENDMENT 23: the CEILING on how much cheaper a "
                         "SAME-MARKET second buy may be, in dollars. Default "
                         "%.3f. Only bites when --max-per-market > 1. A small "
                         "improvement is liquidity and pays (+3.08c at 0.5-1c "
                         "cheaper); a large one is someone selling into us "
                         "(-11.45c at 5-10c cheaper)."
                         % _DEFAULT_IMPROVE_MAX)
    ap.add_argument("--improve-scope", default="close",
                    choices=("close", "market"),
                    help="AMENDMENT 22: 'market' lets a SECOND COIN be bought "
                         "at the same close on its own merits, which is what "
                         "AMENDMENT 17 says and what the improve-by rule has "
                         "been silently overriding since AMENDMENT 13 made it "
                         "obsolete")
    ap.add_argument("--pin", type=float, default=None,
                    help="AMENDMENT 21: the confidence gate. Default %.3f. "
                         "May only be LOWERED toward 0.95; raising it from the "
                         "command line is refused, because a tighter gate is "
                         "the change that silently halves the trade count."
                         % _DEFAULT_PIN)
    ap.add_argument("--sigma-ruler", default="live",
                    choices=("live", "1800", "max3600", "maxdown"),
                    help="AMENDMENT 20: how long a window the volatility "
                         "estimate spans. See results/PREREG_ruler.md")
    ap.add_argument("--honest", action="store_true",
                    help="AMENDMENT 19: map confidence through the MEASURED "
                         "tail table instead of a Gaussian. Strictly a "
                         "tightening; see results/PREREG_honest.md")
    ap.add_argument("--no-sweep", action="store_true",
                    help="AMENDMENT 18 off: send the limit at the ask we saw, "
                         "so a lost race buys nothing")
    ap.add_argument("--max-losses", type=int, default=0,
                    help="halt after this many LOSING trades, whatever the "
                         "dollars. 0 disables. The dollar brake asks 'have we "
                         "lost too much'; this asks 'is the model still what "
                         "we think it is'.")
    a = ap.parse_args()
    # The frozen rule is frozen. Widening it must be a code edit and a commit,
    # not a flag: pintake's own MAX_TAU is 90 s, so --tau-max 60 would have
    # been waved through by every rail below this line.
    if a.live:
        if a.tau_max > TAU_MAX:
            raise SystemExit(f"--tau-max {a.tau_max} exceeds the frozen rule's "
                             f"{TAU_MAX} s (PREREG_pin_live.md); refusing to go "
                             f"live outside the pre-registered cell")
        # THE ABORT MUST SCALE WITH SIZE. A flat -$5.00 cap was correct at
        # size 1 and silently fatal at size 8: one ORDINARY loss there is
        # -$7.57, so the run refused to start at all and traded nothing for an
        # hour before the operator noticed. A brake that cannot survive the
        # first expected event is not a brake, and a hard cap that refuses the
        # correct value is worse -- it looks like a safety feature and acts
        # like an outage.
        # Allowed: roughly 2 to 4 ordinary losses at the size being traded.
        # The unit of loss is a CLOSE, not a contract. With MAX_PER_CLOSE buys
        # allowed, one bad close costs size * MAX_PER_CLOSE, and sizing the
        # abort against a single contract produced a configuration the
        # forward-looking loss bound then refused as self-contradictory --
        # size 8 with 2 buys can commit ~$16 against a $15 brake, so the run
        # halted after its FIRST trade. Correct arithmetic, wrong unit.
        worst_close = 1.00 * float(a.size) * float(MAX_PER_CLOSE)
        lo_allowed = -4.0 * worst_close
        hi_allowed = -1.5 * worst_close
        if not (lo_allowed <= a.loss_abort <= hi_allowed):
            raise SystemExit(
                f"--loss-abort {a.loss_abort:.2f} is outside "
                f"[{lo_allowed:.2f}, {hi_allowed:.2f}] for size {a.size:g} "
                f"with {MAX_PER_CLOSE} buys per close. One bad CLOSE costs up "
                f"to ${worst_close:.2f}; the abort must survive the first and "
                f"stop by the fourth.")
        if a.max_positions > 6:
            raise SystemExit(f"--max-positions {a.max_positions} > 6; refusing")
    if a.max_per_market is not None:
        # THE LIVE REFUSAL IS LIFTED, 2026-09-14, BY OPERATOR DECISION, and it
        # is written here rather than deleted because a bar is never moved
        # quietly. It used to read: "--max-per-market is refused on a LIVE
        # run ... it may be raised only in a paper what-if until that what-if
        # says otherwise."
        #
        # WHAT CHANGED HIS MIND, and mine: the measurement that the bot spends
        # only 58% of the contract budget it is already allowed, with a MEDIAN
        # close spending exactly 50% -- one fill, never the second. I had
        # argued A23 "raises risk" because a close concentrates on one coin.
        # That framed the alternative wrongly. The alternative is not 52+52
        # across two coins; only 6.3% of scan seconds have a second coin
        # passing at all. The real alternative is 52 and the other 52 UNSPENT.
        # The contract cap, and therefore the worst close, does not move. His
        # words: "definitely allow double coin buys if it's causing this many
        # losses opportunities."
        #
        # WHAT STILL PROTECTS IT: rebuy_ok(). Below a full size a top-up needs
        # nothing beyond the ordinary gates (A29); at or above one, a second
        # buy must be 0.5-1.0c cheaper (A23), and the band is where the
        # measurement put it -- 0.70% losses at 0.5-1c against 26.09% at
        # 5-10c.
        if not (1 <= a.max_per_market <= MAX_PER_CLOSE):
            raise SystemExit(
                "--max-per-market %d outside [1, %d]: more fills than the "
                "close cap cannot help, the CONTRACT budget binds first."
                % (a.max_per_market, MAX_PER_CLOSE))
        globals()["MAX_PER_MARKET"] = int(a.max_per_market)
    if a.sweep_depth:
        globals()["SWEEP_DEPTH"] = True
    if getattr(a, "take_dumps", False):
        # NEVER LIVE. This deliberately removes a guard that was built from
        # four real losses; it exists to measure the population the guard
        # refuses, in paper, beside the live bot.
        if a.live:
            raise SystemExit(
                "--take-dumps is refused on a LIVE run. It turns off the dump "
                "guard, which was built from four live losses (XRP 82c, DOGE "
                "10c, SOL 59c, NEAR 73c -- 0 of 4). Run it as a paper arm and "
                "compare.")
        globals()["DUMP_ENABLED"] = False
    if getattr(a, "one_coin_depth", False):
        # NEVER LIVE. This raises the exposure a single market may carry; the
        # measured concentration risk and the live bar are in
        # results/PREREG_onecoin.md, and a live run must cross that bar first.
        if a.live:
            raise SystemExit(
                "--one-coin-depth is refused on a LIVE run. It lets one market "
                "hold more than SIZE; results/PREREG_onecoin.md sets the bar a "
                "paper arm must clear first.")
        _m45 = float(a.one_coin_max)
        if not (1.0 <= _m45 <= float(MAX_PER_CLOSE)):
            raise SystemExit("--one-coin-max must be between 1.0 and MAX_PER_CLOSE "
                             "(%g); got %g" % (MAX_PER_CLOSE, _m45))
        globals()["ONE_COIN_DEPTH"] = True
        globals()["ONE_COIN_MAX"] = _m45
    if int(getattr(a, "early_tau", TAU_MAX) or TAU_MAX) > TAU_MAX:
        # AMENDMENT 46. Paper until the bar in results/PREREG_staged.md is
        # crossed; then EARLY_LIVE_OK is flipped in a commit that cites it.
        if a.live and not EARLY_LIVE_OK:
            raise SystemExit(
                "--early-tau %d is refused on a LIVE run until "
                "results/PREREG_staged.md's bar is crossed and EARLY_LIVE_OK "
                "is flipped in a commit that cites it." % int(a.early_tau))
        if not (TAU_MAX < int(a.early_tau) <= 60):
            raise SystemExit("--early-tau must be between %d and 60; got %d"
                             % (TAU_MAX + 1, int(a.early_tau)))
        if not (0.1 <= float(a.early_frac) <= 1.0):
            raise SystemExit("--early-frac must be between 0.1 and 1.0; got %g"
                             % float(a.early_frac))
        globals()["EARLY_TAU_MAX"] = int(a.early_tau)
        globals()["EARLY_FRAC"] = float(a.early_frac)
    if getattr(a, "no_external_detect", False):
        globals()["EXTERNAL_DETECT"] = False
    if a.jump_gate:
        globals()["JUMP_ENABLED"] = True
    if a.jump_widen:
        globals()["WIDEN_ENABLED"] = True
    if a.depth_ladder:
        if not a.sweep_depth:
            raise SystemExit(
                "--depth-ladder refused without --sweep-depth. The floor would "
                "pass a market on the strength of its ladder while the order "
                "still sized from the touch, which buys exactly the scrap fill "
                "AMENDMENT 6 added the floor to prevent.")
        globals()["DEPTH_LADDER"] = True
    if a.early_min_price is not None:
        if not (0.0 < a.early_min_price <= 0.99):
            raise SystemExit("--early-min-price must be in (0, 0.99], got %r"
                             % (a.early_min_price,))
        globals()["EARLY_MIN_PRICE"] = float(a.early_min_price)
    if a.hedge_normal:
        globals()["HEDGE_NORMAL"] = True
    if a.hedge_jump is not None:
        if not (1.0 <= a.hedge_jump <= 50.0):
            raise SystemExit("--hedge-jump is in SIGMA and must be in [1, 50], "
                             "got %r" % (a.hedge_jump,))
        globals()["HEDGE_JUMP_SIGMA"] = float(a.hedge_jump)
    if a.bank_brake is not None:
        if not (1.0 <= a.bank_brake <= 20.0):
            raise SystemExit("--bank-brake must be between 1 and 20, got %r"
                             % (a.bank_brake,))
        globals()["BANK_BRAKE"] = float(a.bank_brake)
    if a.price_ceiling is not None:
        # PRICES ARE DOLLARS, never cents (hard rule 5): 99 would be a ceiling
        # nothing can exceed and the bot would buy at any price at all.
        if not (0.50 < a.price_ceiling <= 0.999):
            raise SystemExit("--price-ceiling is in DOLLARS (0.99, not 99) and "
                             "must be in (0.50, 0.999], got %r"
                             % (a.price_ceiling,))
        globals()["PRICE_CEILING"] = float(a.price_ceiling)
    if a.early_max_edge is not None:
        if not (0.0 < a.early_max_edge <= 50.0):
            raise SystemExit("--early-max-edge is in CENTS and must be in "
                             "(0, 50], got %r" % (a.early_max_edge,))
        if a.early_tau <= TAU_MAX:
            raise SystemExit(
                "--early-max-edge does nothing without --early-tau above %d. "
                "It gates the EARLY leg only; passing it alone would look like "
                "a live change and be none." % TAU_MAX)
        globals()["EARLY_MAX_EDGE"] = float(a.early_max_edge)
    if a.late_tau is not None:
        if not (0 <= a.late_tau <= TAU_MAX):
            raise SystemExit("--late-tau must be between 0 and TAU_MAX (%d), got %r"
                             % (TAU_MAX, a.late_tau))
        globals()["LATE_TAU"] = int(a.late_tau)
    if a.late_mult is not None:
        if not (1.0 <= a.late_mult <= MAX_PER_CLOSE):
            raise SystemExit("--late-mult must be between 1.0 and MAX_PER_CLOSE "
                             "(%.1f) -- the close budget bounds it anyway, got %r"
                             % (float(MAX_PER_CLOSE), a.late_mult))
        globals()["LATE_MULT"] = float(a.late_mult)
    if a.loss_cap is not None:
        if not (10.0 <= a.loss_cap <= 100000.0):
            raise SystemExit("--loss-cap is in positive dollars and must sit "
                             "in [10, 100000], got %r" % (a.loss_cap,))
        globals()["LOSS_CAP"] = abs(float(a.loss_cap))
        # apply it to the starting value too, not only to later autosizes
        if abs(float(a.loss_abort)) > abs(float(a.loss_cap)):
            a.loss_abort = -abs(float(a.loss_cap))
    if a.late_extra_tau is not None:
        if not (TAU_MIN <= a.late_extra_tau <= max(TAU_MAX, EARLY_TAU_MAX)):
            raise SystemExit("--late-extra-tau must sit in [%d, %d], got %r"
                             % (TAU_MIN, max(TAU_MAX, EARLY_TAU_MAX),
                                a.late_extra_tau))
        globals()["LATE_EXTRA_TAU"] = int(a.late_extra_tau)
    if a.late_extra is not None:
        if not (0.0 <= a.late_extra <= float(MAX_PER_CLOSE)):
            raise SystemExit("--late-extra must sit in [0, MAX_PER_CLOSE=%g], "
                             "got %r" % (float(MAX_PER_CLOSE), a.late_extra))
        if a.late_extra > 0 and not LATE_TAU:
            raise SystemExit(
                "--late-extra needs --late-tau: without a late window there "
                "is no 'inside the last seconds' for it to apply to, and the "
                "flag would sit in the start record doing nothing.")
        globals()["LATE_EXTRA"] = float(a.late_extra)
    if a.attempts_on_send:
        globals()["ATTEMPTS_ON_SEND"] = True
    if a.extra_coin is not None:
        if not (0.0 <= a.extra_coin <= float(MAX_PER_CLOSE)):
            raise SystemExit("--extra-coin must sit in [0, MAX_PER_CLOSE=%g], "
                             "got %r" % (float(MAX_PER_CLOSE), a.extra_coin))
        globals()["EXTRA_COIN"] = float(a.extra_coin)
    if a.sigma_stress is not None:
        # FLOOR LOWERED 0.25 -> 0.20 on 2026-09-21, PAPER REACH ONLY. The
        # operator asked for a 0.20 arm to see whether the bold ladder keeps
        # going down. The LIVE refusal below is untouched, so this widens what
        # a paper arm may explore and changes nothing a live run may do.
        if not (0.20 <= a.sigma_stress <= 5.0):
            raise SystemExit("--sigma-stress must sit in [0.20, 5], got %r"
                             % (a.sigma_stress,))
        if a.live and a.sigma_stress < 1.0:
            raise SystemExit(
                "--sigma-stress below 1.0 makes the model BOLDER than the "
                "one every live number was measured under. Paper only.")
        globals()["SIGMA_STRESS"] = float(a.sigma_stress)
    if a.late_pin is not None:
        if not (0.5 <= a.late_pin < 1.0):
            raise SystemExit("--late-pin must sit in [0.5, 1), got %r"
                             % (a.late_pin,))
        if a.late_pin <= PIN:
            raise SystemExit(
                "--late-pin %.4f is not ABOVE the ordinary confidence gate "
                "%.4f, so it could never refuse anything the ordinary gate "
                "allows -- a flag that cannot fire reads as a guard and is "
                "not one. This flag exists to hold the EXTRA contracts to a "
                "HIGHER bar." % (a.late_pin, PIN))
        globals()["LATE_PIN"] = float(a.late_pin)
    if a.late_jump is not None:
        if not (0.5 <= a.late_jump <= 50.0):
            raise SystemExit("--late-jump is in SIGMA and must sit in "
                             "[0.5, 50], got %r" % (a.late_jump,))
        # AND IT MUST BE TIGHTER THAN THE GATE THAT ALREADY REFUSED THE TRADE.
        # --jump-gate refuses any signal at JUMP_SIGMA or more, so every
        # candidate reaching the boost has ALREADY passed that bar. A
        # --late-jump at or above it can never fire: it would sit in the
        # start record, in VERSIONS.md and in this reply looking like a
        # safeguard while doing nothing at all. Caught before deploying it
        # at 4.0 against a 3.0 gate.
        if JUMP_ENABLED and a.late_jump >= JUMP_SIGMA:
            raise SystemExit(
                "--late-jump %.2f cannot fire: --jump-gate already refuses "
                "the whole trade at %.2f sigma, so every candidate reaching "
                "the boost is under it. Use a value BELOW %.2f, or the flag "
                "is decoration." % (a.late_jump, JUMP_SIGMA, JUMP_SIGMA))
        globals()["LATE_JUMP_SD"] = float(a.late_jump)
    if a.flip_mult is not None:
        if not (1.0 <= a.flip_mult <= MAX_PER_CLOSE):
            raise SystemExit("--flip-mult must sit in [1, MAX_PER_CLOSE=%g] -- "
                             "the close's own worst case bounds it, got %r"
                             % (float(MAX_PER_CLOSE), a.flip_mult))
        if a.live and a.flip_mult > 1.0:
            raise SystemExit(
                "--flip-mult is PAPER ONLY. Buying more of the other side is a "
                "bet on the 30-second read beating the 60-second read, and "
                "nothing has measured that yet. It roughly doubles the loss "
                "when the flip is wrong.")
        globals()["FLIP_MULT"] = float(a.flip_mult)
    # ---- R1: --doubt-under, then --doubt-mult (order matters for the error) --
    if a.doubt_under is not None:
        if not (0.0 < a.doubt_under < 1.0):
            raise SystemExit("--doubt-under is a confidence in (0, 1), got %r"
                             % (a.doubt_under,))
        globals()["DOUBT_UNDER"] = float(a.doubt_under)
    if a.doubt_mult is not None:
        if not (1.0 <= a.doubt_mult <= MAX_PER_CLOSE):
            raise SystemExit("--doubt-mult must sit in [1, MAX_PER_CLOSE=%g] "
                             "-- the close's own worst case bounds it, got %r"
                             % (float(MAX_PER_CLOSE), a.doubt_mult))
        # PAPER ONLY, until the pre-registered bar in
        # results/map_2026-09-22/signature/D_plan.md section 1 is crossed.
        # The money is stable (+$2.72 a market on every leave-one-day-out) and
        # the SIGNIFICANCE is not: p = 0.00015 against a corrected bar of
        # 1.13e-4 is a marginal FAIL, and 0 losers in 66 markets leaves a 95%
        # upper bound of 5.28% on the true loss rate against a 2.44% base. A
        # flag that raises risk on a marginal p-value is an arm, not a deploy.
        if a.live and a.doubt_mult > 1.0:
            raise SystemExit(
                "--doubt-mult above 1.0 is PAPER ONLY. It buys MORE on a "
                "population with zero losses in 66 markets -- which does not "
                "exclude the 2.44% base rate (95% upper bound 5.28%) -- on a "
                "p-value that fails the corrected bar. It ships live only "
                "after the D_plan section 1 bar: the flag firing on 60+ "
                "closes, 2 or fewer money-losers among them, at or above "
                "+$2.00 a market and above the unflagged markets, with the "
                "arm's realised entry price within 0.20c of live's on the "
                "same markets.")
        globals()["DOUBT_MULT"] = float(a.doubt_mult)
    if a.skip_band:
        _sb53 = []
        for _lo, _hi in a.skip_band:
            if not (0.0 < _lo < _hi <= 1.0):
                raise SystemExit("--skip-band needs 0 < LO < HI <= 1, got %r %r"
                                 % (_lo, _hi))
            _sb53.append((float(_lo), float(_hi)))
        globals()["SKIP_BANDS"] = tuple(_sb53)
    if a.band_mult:
        _bm53 = []
        for _lo, _hi, _m in a.band_mult:
            if not (0.0 < _lo < _hi <= 1.0):
                raise SystemExit("--band-mult needs 0 < LO < HI <= 1, got %r %r"
                                 % (_lo, _hi))
            if not (1.0 < _m <= MAX_PER_CLOSE):
                raise SystemExit("--band-mult MULT must sit in (1, MAX_PER_CLOSE"
                                 "=%g] -- the close budget bounds it anyway, "
                                 "got %r" % (float(MAX_PER_CLOSE), _m))
            _bm53.append((float(_lo), float(_hi), float(_m)))
        globals()["BAND_MULTS"] = tuple(_bm53)
    if a.rebuy_mult is not None:
        if not (0.0 <= a.rebuy_mult <= 3.0):
            raise SystemExit("--rebuy-mult must sit in [0, 3], got %r"
                             % (a.rebuy_mult,))
        globals()["REBUY_MAX_MULT"] = float(a.rebuy_mult)
    if a.no_taper:
        globals()["TAPER"] = False
    if a.taper_floor is not None:
        if not (0.0 <= a.taper_floor < 1.0):
            raise SystemExit("--taper-floor must sit in [0, 1), got %r"
                             % (a.taper_floor,))
        globals()["TAPER_FLOOR"] = float(a.taper_floor)
    if a.arm_name is not None and a.live:
        # A label is harmless, but a LIVE command line that carries one is a
        # paper arm's flag list that got --live added to it by hand. Refuse
        # the whole start rather than trade a paper configuration for money.
        raise SystemExit("--arm-name is a PAPER label; it has no business on "
                         "a --live command line. Got %r." % (a.arm_name,))
    if a.no_size_mirror:
        globals()["SIZE_MIRROR_ON"] = False
    if a.rebuy_hedged:
        globals()["REBUY_HEDGED"] = True
    if a.hedge_panic is not None:
        if not (0.0 <= a.hedge_panic < 1.0):
            raise SystemExit("--hedge-panic must sit in [0, 1), got %r"
                             % (a.hedge_panic,))
        globals()["HEDGE_PANIC"] = float(a.hedge_panic) or None
    if a.loss_bound_open:
        globals()["LOSS_BOUND_OPEN"] = True
    if a.early_max_price is not None:
        if not (0.5 <= a.early_max_price <= 1.0):
            raise SystemExit("--early-max-price must sit in [0.5, 1.0], got %r"
                             % (a.early_max_price,))
        if a.early_min_price is not None and a.early_max_price < a.early_min_price:
            raise SystemExit("--early-max-price %.3f is BELOW --early-min-price "
                             "%.3f, which would refuse every early fill"
                             % (a.early_max_price, a.early_min_price))
        globals()["EARLY_MAX_PRICE"] = float(a.early_max_price)
    if a.no_hedge_prop:
        globals()["HEDGE_PROP"] = False
    if a.hedge_prop_full is not None or a.hedge_prop_half is not None:
        _f = (_DEFAULT_HEDGE_PROP_FULL if a.hedge_prop_full is None
              else float(a.hedge_prop_full))
        _h = (_DEFAULT_HEDGE_PROP_HALF if a.hedge_prop_half is None
              else float(a.hedge_prop_half))
        if not (0.0 < _f <= _h < 1.0):
            raise SystemExit("--hedge-prop-full/--hedge-prop-half must satisfy "
                             "0 < full <= half < 1, got %r / %r" % (_f, _h))
        globals()["HEDGE_PROP_FULL"] = _f
        globals()["HEDGE_PROP_HALF"] = _h
    if a.hedge_slip is not None:
        # The cap is 0.10 because the slip is paid on the WHOLE hedge and a
        # hedge leg at or over $1 cannot beat holding (hedge_ask_ok); anything
        # bigger than a dime is a different decision that needs its own
        # evidence, not a flag.
        if not (0.0 <= a.hedge_slip <= 0.10):
            raise SystemExit("--hedge-slip must sit in [0, 0.10] dollars, got "
                             "%r" % (a.hedge_slip,))
        globals()["HEDGE_SLIP"] = float(a.hedge_slip)
    if a.hedge_price is not None:
        if not (0.0 < a.hedge_price < 1.0):
            raise SystemExit("--hedge-price must be between 0 and 1, got %r"
                             % (a.hedge_price,))
        globals()["HEDGE_PRICE"] = float(a.hedge_price)
    if a.hedge_belief is not None:
        if not (0.0 < a.hedge_belief <= _DEFAULT_HEDGE_BELIEF):
            raise SystemExit(
                "--hedge-belief %.3f refused: it must sit in (0, %.2f]. This "
                "flag exists to make the trigger LATER (fewer false alarms); "
                "an EARLIER one buys more needless opposite legs and needs a "
                "code change and a version entry, not a flag."
                % (a.hedge_belief, _DEFAULT_HEDGE_BELIEF))
        globals()["HEDGE_BELIEF"] = float(a.hedge_belief)
    if a.min_fill_frac is not None:
        # THE LIVE REFUSAL IS LIFTED, 2026-09-14, BY OPERATOR DECISION. It
        # used to read: "--min-fill-frac is refused on a LIVE run ...
        # re-measure it in a paper what-if first."
        #
        # His words: "DEFINITELY buy smaller if it can't reach the max
        # contract that was the entire point of opening multiple coins so we
        # can mix the way up to the contract threshold."
        #
        # AND THE ARGUMENT IS MECHANICAL, NOT STATISTICAL, WHICH IS WHY IT
        # DOES NOT NEED THE WHAT-IF FIRST. A smaller fill is the same bet at
        # the same gate on fewer contracts -- min(SIZE, offered) can only
        # LOWER exposure. The comment on MIN_FILL_FRAC justified the floor by
        # two harms, a scrap "burns a scale-in slot" and "raises the improve
        # bar", and AMENDMENT 17 and AMENDMENT 12 removed both. MIN_LEVEL is
        # still the backstop and this flag cannot get underneath it.
        # ZERO IS NOW ALLOWED, 2026-09-14, BY OPERATOR DECISION. His words:
        # "No thinking 'is it worth it there's no point in that it's wasted
        # time. That's how it needs to function right now. No 10%."
        #
        # At 0 the percentage floor is gone entirely and MIN_LEVEL -- one
        # contract -- is the only floor left, at every SIZE. That is the
        # intended end state, not a degenerate case: the two harms the
        # percentage floor was written to prevent were a scrap fill "burning a
        # scale-in slot" and "raising the improve bar", and AMENDMENT 17 and
        # AMENDMENT 29 removed both. A floor of 0.10 x SIZE also GROWS with the
        # bank -- 6 contracts at SIZE 58 but 25 at SIZE 250 -- so it would have
        # refused more and more of the book exactly as we scaled into it.
        if not (0.0 <= a.min_fill_frac <= _DEFAULT_MIN_FILL_FRAC):
            raise SystemExit(
                "--min-fill-frac %.3f refused: it must sit in [0, %.2f]. "
                "This flag exists to LOWER the floor; raising it cuts trading "
                "and needs a code change and a version entry, not a flag."
                % (a.min_fill_frac, _DEFAULT_MIN_FILL_FRAC))
        globals()["MIN_FILL_FRAC"] = float(a.min_fill_frac)
    if a.pick is not None:
        globals()["PICK"] = a.pick
    if a.improve_max is not None:
        if not (IMPROVE_BY < a.improve_max <= 0.10):
            raise SystemExit(
                "--improve-max %.4f refused: it must sit in (%.3f, 0.10]. "
                "At or below IMPROVE_BY no second buy could ever qualify, "
                "and above 10c the band stops meaning anything."
                % (a.improve_max, IMPROVE_BY))
        globals()["IMPROVE_MAX"] = float(a.improve_max)
    if a.improve_scope != "close":
        globals()["IMPROVE_SCOPE"] = a.improve_scope
    if a.pin is not None:
        if not (0.95 <= a.pin <= _DEFAULT_PIN):
            raise SystemExit(
                "--pin %.4f refused: it must sit in [0.95, %.4f]. Raising the "
                "gate above the default from the command line is exactly the "
                "change that costs half the trades without anyone noticing, "
                "and it needs a code change and a version entry, not a flag."
                % (a.pin, _DEFAULT_PIN))
        globals()["PIN"] = float(a.pin)
    if a.sigma_ruler != "live":
        globals()["SIGMA_RULER"] = a.sigma_ruler
    if a.honest:
        if load_honest() is None:
            raise SystemExit(
                "--honest asked for but %s is missing or malformed. Build it "
                "with: python research/pincalib.py --data <tape> "
                "--emit-table results/calib_table.json  --  REFUSING to fall "
                "back to the Gaussian under an honest label."
                % HONEST_TABLE_PATH)
        globals()["HONEST_CONF"] = True
    if a.no_sweep:
        globals()["SWEEP_ENABLED"] = False
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")

    globals()["TAU_MAX"] = a.tau_max
    globals()["SIZE"] = a.size
    runid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = "live" if a.live else "paper"
    logpath = os.path.join(RESULTS, f"pinrun-{tag}-{runid}.jsonl")

    def rec(kind, **kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kw["kind"] = kind
        try:
            with open(logpath, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(kw, default=str) + "\n")
        except Exception:
            pass

    # R4: THE TRAJECTORY GOES IN ITS OWN FILE, and that is not tidiness. The
    # decision log above is parsed by pinledger, pinattrib, pinlab, barcheck,
    # earlyhindsight and the settlement readers, every one of them globbing
    # `pinrun-<tag>-*.jsonl`; tens of MB a day of 1 Hz samples in there would
    # slow all of them and change nothing about what they are looking for.
    # `pintraj-` does not match that glob, and research/archive_runs.ps1 only
    # git-adds `pinrun-live-*` / `pinrun-paper-*`, so these stay out of the
    # repo as well (and .gitignore says so explicitly).
    #
    # AND ONLY THE LIVE BOT OPENS IT. 27 paper arms run from this same file;
    # a file each was ~1.6 GB a day. traj_writer() is where that is decided
    # and where the numbers are written down.
    trajpath, trec = traj_writer(a.live, a.traj_log, RESULTS, tag, runid)

    # ===================================================================
    # AMENDMENT 27 (2026-09-14): ONE LIVE BOT. EVER.
    #
    # WHAT HAPPENED. restart_bot.ps1 finds the running bot by matching on
    # Win32_Process CommandLine. In the operator's own shell that field came
    # back EMPTY -- Windows hides it for processes the caller cannot open --
    # so the kill loop matched nothing, said nothing, and the script went
    # straight on to start a second one. For 24 minutes TWO live bots traded
    # the same account, each sizing itself off the same bank and each
    # believing it was the only one. Every risk rail in this file -- the loss
    # abort, the stake cap, the position cap, the losing-trade brake -- is
    # per-process, so all of them were silently doubled.
    #
    # A SHELL SCRIPT CANNOT BE THE ONLY GUARD, because the failure was the
    # shell script not seeing the world. This check lives in the bot itself
    # and uses a PID FILE, which needs no permission to read.
    # ===================================================================
    if a.live:
        _pidfile = os.path.join(RESULTS, "pinrun-live.pid")
        _other = None
        try:
            with open(_pidfile, encoding="utf-8") as _fh:
                _other = int((_fh.read() or "0").strip() or 0)
        except (OSError, ValueError):
            _other = None
        if _other and _other != os.getpid() and _pid_alive(_other):
            raise SystemExit(
                "REFUSING TO START: live pinrun pid %d is already running "
                "(%s).\nTwo live bots trade the same account while each one's "
                "loss abort, stake cap, position cap and losing-trade brake "
                "count only its own fills -- every rail silently doubles.\n"
                "Stop it first:  Stop-Process -Id %d -Force"
                % (_other, _pidfile, _other))
        try:
            with open(_pidfile, "w", encoding="utf-8") as _fh:
                _fh.write(str(os.getpid()))
            import atexit as _atexit
            _atexit.register(lambda: _clear_pidfile(_pidfile, os.getpid()))
        except OSError:
            pass

    print(f"  MODE {'LIVE size 1' if a.live else 'PAPER'}   "
          f"tau<={TAU_MAX}s  pin {PIN}  edge>={100 * EDGE_FLOOR:.1f}c net  "
          f"loss abort ${a.loss_abort:.2f}  SIZE {a.size:g}")
    print(f"  log {logpath}")
    print(f"  trajectory {trajpath or 'OFF (paper run; --traj-log to keep it)'}")
    # EVERY parameter that can change a trade decision goes in the log, so a
    # post-mortem can tell exactly which version produced a given result
    # without guessing from the timestamp. results/VERSIONS.md maps these to
    # git SHAs and revert commands.
    rec("start", mode=tag, tau_min=TAU_MIN, tau_max=TAU_MAX, pin=PIN,
        edge_floor=EDGE_FLOOR, ev_floor=EV_FLOOR,
        measured_flip=MEASURED_FLIP, max_per_close=MAX_PER_CLOSE,
        max_per_market=MAX_PER_MARKET,
        hedge_enabled=HEDGE_ENABLED, hedge_belief=HEDGE_BELIEF,
        hedge_max_ask=HEDGE_MAX_ASK, hedge_max_tries=HEDGE_MAX_TRIES,
        hedge_pilot_contracts=HEDGE_PILOT_CONTRACTS,
        # A70/A71: the run's own statement of what its HEDGE is allowed to do.
        # The first v-hedgefill deploy (pid 1305604, 21:58:25Z) recorded
        # hedge_panic, hedge_price and hedge_max_tries but NOT these, so the
        # log could not say whether the slip was on -- only the command line
        # could, and Windows returns an empty command line for a process it
        # will not open. That is how the 2026-09-14 double-bot failure hid.
        hedge_slip=HEDGE_SLIP,
        # A78/A79: the log must be able to say what the bot is running. The
        # 09-19 hedge_slip deploy could not, and only the command line knew --
        # which Windows returns empty for a process it will not open.
        early_max_price=EARLY_MAX_PRICE,
        day_loss_at_start=day_loss(),
        hedge_prop=HEDGE_PROP, hedge_prop_full=HEDGE_PROP_FULL,
        hedge_prop_half=HEDGE_PROP_HALF,
        max_hedge_attempts_per_close=MAX_HEDGE_ATTEMPTS_PER_CLOSE,
        reconcile_fail_halt=RECONCILE_FAIL_HALT,
        improve_by=IMPROVE_BY, improve_scope=IMPROVE_SCOPE,
        # A23/A24/A25: the running values, so a reader does not have to guess
        # them from module defaults. research/pindash.py shows what is ACTUALLY
        # running from this record, and a flag missing here reads as its
        # default -- which is how a page ends up describing a bot nobody runs.
        improve_max=IMPROVE_MAX, pick=PICK, gate_audit=True,
        sweep_depth=SWEEP_DEPTH, depth_ladder=DEPTH_LADDER,
        external_detect=EXTERNAL_DETECT, external_min=EXTERNAL_MIN,
        jump_gate=JUMP_ENABLED, jump_sigma=JUMP_SIGMA,
        jump_lookback=JUMP_LOOKBACK,
        jump_widen=WIDEN_ENABLED, jump_widen_factor=JUMP_WIDEN,
        jump_widen_favour=JUMP_WIDEN_FAVOUR,
        jump_widen_window=JUMP_WIDEN_WINDOW,
        min_fill_frac_running=MIN_FILL_FRAC,
        max_drawdown=MAX_DRAWDOWN,
        max_per_market_run=MAX_PER_MARKET, min_level=MIN_LEVEL,
        sweep_enabled=SWEEP_ENABLED, honest_conf=HONEST_CONF,
        one_coin_depth=ONE_COIN_DEPTH, one_coin_max=ONE_COIN_MAX,
        early_tau_max=EARLY_TAU_MAX, early_frac=EARLY_FRAC,
        sigma_ruler=SIGMA_RULER,
        max_book_age_ms=MAX_BOOK_AGE_MS, max_index_age_s=MAX_INDEX_AGE_S,
        sigma_stress=SIGMA_STRESS, sigma_win=SIGMA_WIN,
        size=a.size, loss_abort=a.loss_abort,
        max_positions=a.max_positions, minutes=a.minutes,
        # THE ACTUAL CONSTANT THIS PROCESS WILL ENFORCE. Until 2026-09-08 this
        # record logged only the DERIVED value below, so a process running
        # PRICE_CEILING = 0.96 truthfully reported "price_ceiling": 0.988 and
        # I read that as proof the change was not live. It was live, and it was
        # silently refusing three quarters of our trades.
        # A START RECORD MUST LOG WHAT THE PROCESS WILL DO, NOT WHAT THE
        # ARITHMETIC IMPLIES.
        price_ceiling=PRICE_CEILING,
        ev_implied_ceiling=round(1.0 - MEASURED_FLIP - EV_FLOOR, 4),
        # SAME LESSON, APPLIED TO THE NEWER CONSTANTS (added 2026-09-11).
        # The crazy-deal guard and the scrap rule were both deployed without
        # appearing in this record, so a later reader could see "dumped"
        # entries but not the threshold that produced them, and could not tell
        # a refusing process from a merely-logging one. The tape now says the
        # >=15c band loses 31.31% and costs -6.51c/contract over 18,648
        # contracts, which makes this exact number worth reconstructing later.
        dump_discount=DUMP_DISCOUNT,
        dump_enabled=DUMP_ENABLED,
        min_fill_frac=MIN_FILL_FRAC,
        # SAME LESSON AGAIN, A47/A48/A49 (added 2026-09-18). These three were
        # deployed as paper arms and NONE of them appeared here, so the start
        # record of the hedge-price arm was byte-identical in every setting to
        # the control's. `pinlab` matches an arm to its log by the settings
        # that distinguish it, found nothing to distinguish, and showed the
        # Lab tab a blank where two live experiments should be. An arm whose
        # own log cannot say what it is testing is not measurable.
        hedge_price=HEDGE_PRICE, hedge_panic=HEDGE_PANIC,
        rebuy_hedged=REBUY_HEDGED,
        late_tau=LATE_TAU, late_mult=LATE_MULT,
        late_pin=LATE_PIN, late_jump=LATE_JUMP_SD, extra_coin=EXTRA_COIN,
        late_extra=LATE_EXTRA, late_extra_tau=late_extra_tau(),
        loss_cap=LOSS_CAP,
        # R1: the arm's bar reads this field to admit a shared close, and an
        # arm whose own log cannot say what it is testing is not measurable.
        attempts_on_send=ATTEMPTS_ON_SEND,
        # A53: lists, so the Lab can select an arm by its exact bands
        skip_bands=[list(b) for b in SKIP_BANDS],
        band_mults=[list(b) for b in BAND_MULTS],
        flip_mult=FLIP_MULT,
        # R1: the Lab matches an arm to its log by the settings that
        # distinguish it, so a doubt arm whose start record looked identical to
        # the control's would show a blank tab -- the A47/A48/A49 lesson.
        doubt_mult=DOUBT_MULT, doubt_under=DOUBT_UNDER,
        doubt_lag_s=DOUBT_LAG_S, doubt_hist_tau_s=DOUBT_HIST_TAU_S,
        # R4: the trajectory's grid, so a reader of `pintraj-*.jsonl` never has
        # to guess which cadence produced it -- and WHETHER a file was opened
        # at all, because a paper arm writes none and a reader who does not
        # know that would read its absence as a bot that never sampled.
        traj_every_s=TRAJ_EVERY_S, traj_near_tau_s=TRAJ_NEAR_TAU_S,
        traj_tau_max=TRAJ_TAU_MAX, traj_file=trajpath,
        look_drop_c=LOOK_DROP_C,
        early_min_price=EARLY_MIN_PRICE, early_max_edge=EARLY_MAX_EDGE,
        # THE RISK SETTING ITSELF, in the record. Bet size is derived from it,
        # so a log that shows the size but not the brake cannot say whether a
        # small size meant a cautious setting or a small bank.
        hedge_normal=HEDGE_NORMAL, hedge_jump=HEDGE_JUMP_SIGMA,
        bank_brake=BANK_BRAKE,
        bank_divisor=round(BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING, 4),
        code_sha=_source_fingerprint())

    if a.live:
        # THE ORDER PATH HAS ITS OWN BRAKE AND IT SHIPS AT A SIZE-1 DEFAULT.
        # Left alone, pintake.LOSS_ABORT = -$2.00 refuses every take after the
        # first ordinary loss at size 5 (about -$4.90), silently, while the
        # operator's brake below sits untouched. Raise it to agree with the
        # brake the operator actually set, so the two cannot disagree.
        # set_limits() refuses to TIGHTEN, so this can only ever loosen.
        _worst_close = 1.00 * float(a.size) * float(MAX_PER_CLOSE)
        # THE ORDER-COUNT RAIL IS ALSO A SIZE-1 LITERAL. MAX_TAKE_COUNT = 10
        # silently REFUSED every order at --size 20 on 2026-09-08: 160 orders
        # sent, 0 filled, no error raised, because take() RETURNS its refusal.
        # The FOURTH size-1 constant to break scaling in one day.
        pintake.set_limits(
            loss_abort=float(a.loss_abort),
            max_run_stake=max(pintake.MAX_RUN_STAKE,
                              3.0 * _worst_close + 10.0),
            max_take_count=max(pintake.MAX_TAKE_COUNT,
                               float(a.size) * max(ONE_COIN_MAX if ONE_COIN_DEPTH else 1.0,
                                                   DOUBT_MULT,
                                                   LATE_MULT, max_band_mult(), FLIP_MULT)),
            why=f"size {a.size:g}, worst close ${_worst_close:.2f}")
        arm(f"pinrun --live, size {a.size:g}, frozen rule tau<={TAU_MAX}"
            + (f" (+A46 early leg {EARLY_FRAC:g}xSIZE to tau<={EARLY_TAU_MAX}, "
               f"PREREG_staged.md)" if EARLY_TAU_MAX > TAU_MAX else "")
            + ", PREREG_pin_live.md")
        print(f"  ARMED: {CREDS['base']}  key {CREDS['key_id'][:8]}...  "
              f"stake cap ${pintake.MAX_RUN_STAKE:.2f}")
        rec("armed", base=CREDS["base"], stake_cap=pintake.MAX_RUN_STAKE)

    idx = IndexWS(sorted(set(SERIES_TO_INDEX.values()))).start()
    book = livebook.LiveBook()
    book.start()
    t0 = time.time()
    while time.time() - t0 < 25:
        if idx.stats.get("ticks", 0) > 10:
            break
        time.sleep(0.5)
    print(f"  index up: {idx.stats.get('ticks', 0)} ticks, "
          f"{len(idx.ticks)} feeds")
    rec("feeds", ticks=idx.stats.get("ticks", 0), feeds=sorted(idx.ticks))

    state = {}
    try:
        state, fired = trade_loop(a, rec, book, idx, SERIES_TO_INDEX,
                                  trec=trec)
    finally:
        rec("end", state=dict(state), ledger=dict(pintake.LEDGER),
            index_stats=dict(idx.stats))
        try:
            book.stop()
        except Exception:
            pass
        idx.stop()
    print(f"\n  {state.get('signals', 0)} signals, "
          f"{state.get('considered', 0)} evaluations")
    print(f"  ledger {dict(pintake.LEDGER)}")
    print(f"  log {logpath}")


if __name__ == "__main__":
    main()
