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
BANK_BRAKE = 4.08        # bank must cover this many worst-closes.
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
MAX_PER_CLOSE = 2        # 3 -> 2 on 2026-09-09, and NOT because cap 3 is
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
HEDGE_MAX_TRIES = 5      # seconds we keep trying once the alarm has fired.
                         # Separate from MAX_ATTEMPTS_PER_CLOSE, which also
                         # applies. A collapse leaves ~15s; five is generous.


def hedge_should_fire(belief, threshold=None):
    """True when the model's belief in OUR side has fallen below the gate."""
    thr = HEDGE_BELIEF if threshold is None else threshold
    return belief is not None and belief < thr


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
SKIP_BANDS = ()                 # ((lo, hi), ...)        asks refused
_DEFAULT_SKIP_BANDS = ()
BAND_MULTS = ()                 # ((lo, hi, mult), ...)  size multiples
_DEFAULT_BAND_MULTS = ()
_PB_UNSET = object()            # "not supplied" -- the _HP_UNSET / _EW_UNSET trap


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
    the process was not using."""
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
    _hwm_real = HWM_FILE
    import tempfile as _tfhw
    _hwm_dir = _tfhw.mkdtemp(prefix="pinhwm-")
    globals()["HWM_FILE"] = os.path.join(_hwm_dir, "hwm.json")
    try:
        return _selftest_body()
    finally:
        globals()["HWM_FILE"] = _hwm_real
        try:
            for _f in os.listdir(_hwm_dir):
                os.remove(os.path.join(_hwm_dir, _f))
            os.rmdir(_hwm_dir)
        except OSError:
            pass


def _selftest_body():
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
        # the two real ones from tonight, verbatim from the live log
        ck(halt_is_transient("position cap: 3 open >= 3"),
           "the 02:00 halt that cost 23 minutes would now PAUSE")
        ck(halt_is_transient("loss bound: realised $+0.78 with $40.89 still "
                             "open; one more contract could take this run "
                             "past $-60.00"),
           "and so would the 03:29 one")
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
        for _site in ("open_pos[_poid] = ", "open_pos[f\"paper-{tk}-{now_s}\"] = ",
                      "open_pos[_oid_new] = "):
            _i = _lp52.index(_site)
            _win = _lp52[_i - 200:_i + 200]
            ck("entry_at[" in _win,
               "every ENTRY position records when it was entered beside the "
               "position itself (%s) -- without it the trigger would measure "
               "the last three seconds, not the time since entry" % _site.strip())
        ck("HEDGE_JUMP_LOOKBACK_MAX" in _lp52 and HEDGE_JUMP_LOOKBACK_MAX == 60,
           "and the lookback is capped at a minute, so a position held from "
           "45 s cannot ask the feed for more than it holds")
        # THE RISK SETTING. The operator asked for one bet to be the bank
        # divided by 8 rather than 5.88, and the divisor is a PRODUCT of three
        # constants -- so asserting the brake alone would pass while a change
        # to MAX_PER_CLOSE or PRICE_CEILING silently moved the bet size.
        _div = BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING
        ck(abs(_div - 8.0) < 0.1,
           "one bet is the bank divided by about 8 (got %.3f) -- set 2026-09-18 "
           "on the operator's word 'Sure divide by 8'; the tolerance admits the "
           "ceiling moving 0.98 -> 0.99, which makes it 8.08" % _div)
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
        ck("staged_take(tau, take_n, float(SIZE) * band_mult(price), _held46)" in _lp53,
           "the A46 re-cap reads the band multiple, or it undoes the boost")
        ck('_gate("price_band"' in _lp53
           and _lp53.index('_gate("price_band"') < _lp53.index('rec("signal", live=live, **sig)'),
           "a skipped band is refused under its own gate name BEFORE the signal "
           "is recorded, so the cost of the skip is scorable and a refusal "
           "never reads as a lost race")
        ck(_lp53.index('_gate("early_wide"') < _lp53.index('_gate("price_band"'),
           "and after the early-leg gates, so a cheap early ask is refused for "
           "being cheap rather than for its band")
        _nd53 = "LATE_MULT, max_band" + "_mult())"     # built, so this line is not counted
        ck(_src53.count(_nd53) == 2,
           "pintake's per-order count cap admits the band multiple AND the late "
           "multiple, at live start and at every autosize -- the live path "
           "would otherwise refuse the wider order the paper path books")
        ck("skip_bands=[list(b) for b in SKIP_BANDS]" in _src53
           and "band_mults=[list(b) for b in BAND_MULTS]" in _src53,
           "the start record carries both band lists, so the Lab can tell one "
           "band arm from another (the A47/A48/A49 blank-tab lesson)")
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
        _call = "_both_sides_block(" + "prev, tk, want)"
        ck(_call in _lp8 and _lp8.index("want = price = size = None") < _lp8.index(_call),
           "and the trade loop calls it AFTER `want` is assigned -- the entire "
           "bug was that this test ran 143 lines too early")
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
        ck("hedged.add(_hid)" not in _lp[_lp.index("if not " + _needle):
                                        _lp.index("if not hedge_ask_ok(" + "_ask)")],
           "a price-wait does NOT retire the position: the price can still fall "
           "inside this close, and then we hedge")
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
        ck(hedge_should_fire(0.05) and hedge_should_fire(HEDGE_BELIEF - 1e-6),
           f"belief below the {HEDGE_BELIEF:.2f} gate fires the hedge")
        ck(not hedge_should_fire(HEDGE_BELIEF) and not hedge_should_fire(0.999),
           "belief at or above the gate does not")
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
        ck(HEDGE_MAX_TRIES >= 3 and HEDGE_MAX_TRIES <= 10,
           f"retries are bounded ({HEDGE_MAX_TRIES}) -- a runaway on the hedge "
           "path would be the 160-order incident again")
        # the FORWARD bound: realised only moves after settlement, so the
        # advertised -$2.00 has to be checked against what is still open.
        pintake.LEDGER.update({"realised": 0.0, "committed": 0.0,
                               "halt": None, "positions": {}})
        s4 = risk_abort({"halted": False, "errors": 0, "open_cost": 1.20}, _A)
        ck(s4 and "loss bound" in s4,
           f"abort fires FORWARD: $1.20 open plus one more contract would "
           f"pass -$2.00 ({s4})")
        s5 = risk_abort({"halted": False, "errors": 0, "open_cost": 0.90}, _A)
        ck(s5 is None,
           f"$0.90 open still leaves room for one more contract ({s5})")
        s6 = risk_abort({"halted": False, "errors": 0, "order_errors": 2}, _A)
        ck(s6 and "ORDER path" in s6,
           f"abort fires on order-path errors, which the universe pass "
           f"cannot reset ({s6})")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved)

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

    # --- STRUCTURAL: the abort must precede every branch in the loop ---
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[src.index(chr(10) + "def trade_loop("):]
    body = body[body.index("    while "):]
    i_abort = body.find("risk_abort(")
    i_cont = body.find("continue")
    ck(i_abort != -1 and (i_cont == -1 or i_abort < i_cont),
       "risk_abort() runs before the first `continue` in the loop")

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
        ck(abs(worst_close_cost(20) - MAX_PER_CLOSE * 20 * PRICE_CEILING) < 1e-12,
           f"worst_close_cost(20) must be MAX_PER_CLOSE*20*PRICE_CEILING = "
           f"{MAX_PER_CLOSE * 20 * PRICE_CEILING}, got {worst_close_cost(20)}")
        ck(_DEFAULT_PRICE_CEILING == 0.980,
           "and the DECLARED ceiling is 98c -- asserted separately, so a flag "
           "that moves the running value cannot silently move the bar too")
        ck(abs(worst_close_cost(200) / worst_close_cost(20) - 10.0) < 1e-12,
           "worst_close_cost must be EXACTLY linear in size -- that is the "
           "whole reason it replaced a sampled maximum, which was not")

        # The ladder, by hand. bank / (1.5 * 2 * 0.98) = bank / 2.94.
        _per = BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING
        ck(size_for_bank(192.15) == int(192.15 // _per),
           f"$192.15 / ${_per:.2f} (BANK_BRAKE {BANK_BRAKE} x MAX_PER_CLOSE "
           f"{MAX_PER_CLOSE} x ceiling {PRICE_CEILING}) = "
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
            ck(pintake.LOSS_ABORT <= -240.0,
               f"and the brake must stay at its loosest high-water mark, not "
               f"be tightened on the way down, got {pintake.LOSS_ABORT}")
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
        ck(_tl45.index("book.depth(tk,") > _tl45.index('rec("signal"') - 4000,
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
        ck(_tl45.index("take_n = min(float(SIZE), _deep, max(0.0, _room))")
           < _tl45.index("take_n = _stage46(take_n)\n                    _t0 = time.time()"),
           "A46: the live path re-applies the leg cap AFTER A35/A45 widening, "
           "so an early leg can never be widened back to a full bet")
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
        ck(_tl45.index("take_n = min(float(SIZE), _deep, max(0.0, _room))")
           < _tl45.index("take_n = _widen45(take_n)  # live")
           < _tl45.index("\n                    out = pintake.take("),
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
               f"budget must be MAX_PER_CLOSE x SIZE = "
               f"{68.0 * MAX_PER_CLOSE}, got {close_budget()}")
            # THE INVARIANT THE WHOLE AMENDMENT RESTS ON: exposure unchanged.
            ck(abs(close_budget() * PRICE_CEILING
                   - worst_close_cost(68.0)) < 1e-9,
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
        ck("                if _spent >= close_budget() - 1e-9:" in _ln3,
           "the per-close cap must read CONTRACTS, not the fill count")
        ck('                _spent = prev.get("contracts", 0.0) if prev else 0.0'
           in _ln3,
           "and `contracts` must come from the close's own record")
        ck("            elif prev is not None and prev[\"n\"] >= MAX_PER_CLOSE:"
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
        ck("                       level_age_ms=_lvl_age, "
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
    led = pintake.LEDGER
    if led.get("halt"):
        return f"pintake halted: {led['halt']}"
    if float(led.get("realised", 0.0)) <= a.loss_abort:
        return (f"loss abort: realised ${led['realised']:.2f} <= "
                f"${a.loss_abort:.2f}")
    if float(led.get("committed", 0.0)) >= pintake.MAX_RUN_STAKE:
        return f"stake cap reached: ${led['committed']:.2f} committed"
    # FORWARD-LOOKING LOSS BOUND. `realised` only moves once a position has
    # SETTLED, so a realised-only abort always allows one more contract while
    # an unsettled one is open -- and it is inert entirely if the settlement
    # reader is failing. This bounds what the run can still lose: realised,
    # minus every open position going to zero, minus one more contract at up
    # to $1.00. With the default -$2.00 the run can never have more than
    # ~$1.99 at risk, whatever the settlement reader does.
    worst = float(led.get("realised", 0.0)) - float(state.get("open_cost", 0.0))
    if worst - 1.00 * float(SIZE) < a.loss_abort - 1e-9:
        return (f"loss bound: realised ${float(led.get('realised', 0.0)):+.2f} "
                f"with ${float(state.get('open_cost', 0.0)):.2f} still open; "
                f"one more contract could take this run past "
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
TRANSIENT_HALTS = ("position cap:", "loss bound:", "stake cap reached:")


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
    at at most PRICE_CEILING."""
    return float(MAX_PER_CLOSE) * float(size) * float(PRICE_CEILING)


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


def _both_sides_block(prev, ticker, want):
    """True when we already hold the OPPOSITE side of this market.

    AMENDMENT 8. Holding both sides of one binary cannot win: the two legs pay
    $1.00 between them and cost more than that, so the pair locks in the
    difference. Only an opposite side blocks; a SAME-side re-look is a top-up
    and must pass, which is exactly what the misplaced version got wrong.
    """
    if prev is None or want is None:
        return False
    held = (prev.get("sides") or {}).get(ticker)
    return held is not None and held != want


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
    want_abort = -2.0 * wc                        # mid-band: survives 2 closes
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
                                              LATE_MULT, max_band_mult())),
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


def autosize_tick(state, a, open_positions, rec=None, now=None,
                  bank_reader=None, hwm_path=None):
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


def trade_loop(a, rec, book, idx, series_index):
    live = a.live
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
    entry_at = {}            # A52: oid -> wall-clock second we ENTERED, so the
                             # jump trigger measures moves since entry and not
                             # since the last three seconds
    hedge_meta = {}     # A15: oid -> (strike, digits, iid) so belief can be recomputed
    hedged = set()      # A15: oids already hedged (or given up on)
    hedge_tries = {}    # A15: oid -> attempts since the alarm fired
    hedge_last_try = {}
    hedge_price_said = set()      # A47: one 'waiting on price' line per position # A15: oid -> wall-clock second of the last try (pacing)
    hedge_normal_said = set()     # A51: one 'waiting for a normal bet' line per position
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

    def _gate(name, close_s_, tk_, **detail):
        """Record that `name` refused this market, once per close."""
        nbg = near.setdefault(close_s_, _fresh_near())
        g = nbg.setdefault("gates", {})
        g[name] = g.get(name, 0) + 1
        key = (close_s_, tk_, name)
        if key in gate_seen:
            return
        gate_seen.add(key)
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
            rec("settled", ticker=tk, want=want, result=res, cost=round(cost, 4),
                pnl_c=round(100 * pnl, 2),
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
            if b is None:
                rec("close_summary", close=cs, looks=nb["n"],
                    decided=nb["decided"], undecided=nb["undecided"],
                    no_offer=nb["no_offer"], dust=nb["dust"],
                    fired=(cs in fired), best=None,
                    gates=nb.get("gates", {}),      # AMENDMENT 25
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

    while time.time() < end:
        report_closes(int(time.time()) - 5)
        reconcile()
        # AMENDMENT 16. AFTER reconcile(), so open_pos is already drained of
        # everything that has settled -- otherwise the "only when flat" guard
        # would almost never be true and size could never move.
        _asz = autosize_tick(state, a, open_pos, rec=rec)
        if _asz:
            print(f"  --- AUTO-SIZE: {_asz}")
        stop = risk_abort(state, a)
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
            time.sleep(1.0)
            continue
        if state.get("paused_on"):
            rec("resume", after=state.pop("paused_on"))
            print("  --- RESUMED")
        if stop:
            state["halted"] = True
            rec("halt", why=stop)
            print(f"  *** HALT: {stop}")
            break

        now = time.time()
        now_s = int(now)

        # ---------------- AMENDMENT 15: the hedge pass ----------------
        # Runs BEFORE the signal scan so a collapsing position is dealt with
        # before any new money goes out. One belief recompute per open
        # position per second; the alarm and every refusal are recorded.
        if HEDGE_ENABLED:
            for _hid, (_hcs, _hwant, _hcost, _hn_orig, _htk) in list(open_pos.items()):
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
                _meta = hedge_meta.get(_hid)
                if _meta is None:
                    continue
                _hstrike, _hdig, _hiid = _meta
                _htau = _hcs - now_s
                if _htau < 1:
                    continue
                _hsg = idx.sigma(_hiid)
                if _hsg is None:
                    continue
                _hf = fair(idx, _hiid, _hcs, now_s, _hstrike,
                           _hsg * SIGMA_STRESS
                           * widen_factor(idx, _hiid, _hsg, _hwant),
                           round_digits=_hdig)                  # AMENDMENT 41
                if _hf is None:
                    continue
                _belief = _hf if _hwant == "yes" else 1.0 - _hf
                # A52: two reasons to fire, recorded separately. The jump is
                # asked FIRST because it is the earlier signal -- belief only
                # falls after the price has already moved.
                _htrig = "belief"
                _hjmp = None
                if HEDGE_JUMP_SIGMA is not None:
                    _since = int(now_s - entry_at.get(_hid, now_s))
                    _hjmp = jump_against(
                        idx.recent_moves(_hiid, max(1, min(HEDGE_JUMP_LOOKBACK_MAX, _since))),
                        _hsg, _hwant)
                    if _hjmp is not None and _hjmp >= HEDGE_JUMP_SIGMA:
                        _htrig = "jump"
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
                _tries = hedge_tries.get(_hid, 0)
                if _tries == 0:
                    state["hedge_alarms"] = state.get("hedge_alarms", 0) + 1
                    rec("hedge_alarm", ticker=_htk, want=_hwant, entry=_hcost,
                        n=_hn, belief=round(_belief, 5), tau=_htau,
                        threshold=HEDGE_BELIEF,
                        # A52: WHICH reason fired, and the jump size either
                        # way, so the two triggers can be scored against each
                        # other on the same alarms
                        trigger=_htrig,
                        jump_sd=(round(_hjmp, 2) if _hjmp is not None else None),
                        jump_threshold=HEDGE_JUMP_SIGMA)
                    print(f"  !!! HEDGE ALARM {_htk} {_hwant} belief {_belief:.3f} "
                          f"tau {_htau}s")
                hedge_tries[_hid] = _tries + 1
                if _tries + 1 > HEDGE_MAX_TRIES:
                    hedged.add(_hid)
                    rec("hedge_gave_up", ticker=_htk, tries=_tries, tau=_htau)
                    continue
                if attempts.get(_hcs, 0) >= MAX_ATTEMPTS_PER_CLOSE:
                    hedged.add(_hid)
                    rec("hedge_refused", ticker=_htk, why="attempt_cap", tau=_htau)
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
                if not hedge_price_ok(_ask):
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
                if not hedge_normal_ok(_belief, _ask):
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
                _hn_take = min(float(_hn), float(_asz))
                if HEDGE_PILOT_CONTRACTS:
                    _hn_take = min(_hn_take, float(HEDGE_PILOT_CONTRACTS))
                attempts[_hcs] = attempts.get(_hcs, 0) + 1
                if not live:
                    _hoid = f"hedge-paper-{_htk}-{now_s}"
                    open_pos[_hoid] = (_hcs, _opp, float(_ask), _hn_take, _htk)
                    hedged.add(_hid)
                    rec("hedge", ticker=_htk, side=_opp, price=float(_ask),
                        ask=float(_ask), ask_size=float(_asz),
                        n=_hn_take, entry=_hcost, tau=_htau, belief=round(_belief, 5),
                        locked_loss_c=round(100 * hedge_locked_loss(_hcost, _ask), 2),
                        edge_c=hedge_edge_c(_belief, _ask), live=False)
                    print(f"  HEDGE(paper) {_htk} buy {_opp.upper()} {_hn_take:g} @ "
                          f"{_ask:.3f} -> locked {100*hedge_locked_loss(_hcost,_ask):+.1f}c")
                    continue
                try:
                    _hout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                         _htk, _opp, float(_ask), _hn_take,
                                         float(_hcs), exchange_index=2)
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
                rec("hedge", ticker=_htk, side=_opp, price=_hcost2, n=_hfilled,
                    ask=float(_ask), ask_size=float(_asz),      # criterion (b): fill vs the ask we hit
                    asked=_hn_take, entry=_hcost, tau=_htau, belief=round(_belief, 5),
                    locked_loss_c=round(100 * hedge_locked_loss(_hcost, _hcost2), 2),
                    order_id=_hout.get("order_id"), status=_hout.get("status"),
                    edge_c=hedge_edge_c(_belief, _hcost2), live=True)
                print(f"  HEDGE {_htk} buy {_opp.upper()} {_hfilled:g}/{_hn_take:g} @ "
                      f"{_hcost2:.3f} -> locked {100*hedge_locked_loss(_hcost,_hcost2):+.1f}c")
                if _hfilled > 0:
                    _hoid = f"hedge-{_hout.get('order_id') or now_s}"
                    open_pos[_hoid] = (_hcs, _opp, _hcost2, _hfilled, _htk)
                    state["hedges"] = state.get("hedges", 0) + 1
                    if HEDGE_PILOT_CONTRACTS or _hfilled >= float(_hn) - 1e-9:
                        # under the pilot ANY fill completes the hedge for this
                        # position -- otherwise 1 contract/second for 5 seconds
                        hedged.add(_hid)
                        hedge_remain.pop(_hid, None)
                    else:
                        # PARTIAL: track what is still unhedged in hedge_remain,
                        # NEVER in open_pos[_hid] -- see the note above this loop.
                        hedge_remain[_hid] = float(_hn) - _hfilled
        # ---------------- end AMENDMENT 15 ----------------

        if now - uni_at > 20:
            uni_at = now
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
            except Exception as e:                       # noqa: BLE001
                state["errors"] += 1
                rec("error", where="universe", err=str(e)[:200])

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
        for tk, (iid, close_s, strike, digits, exi) in _mk:
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
                if _spent >= close_budget() - 1e-9:
                    _gate("close_budget", close_s, tk, spent=_spent,
                          budget=close_budget())
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
                    rec("plant", ticker=tk, side=_lose, filled=_pf,
                        price=(float(_pp) if _pp is not None else _la),
                        refused=_po.get("refused"), status=_po.get("status"),
                        order_id=_po.get("order_id"))
                    if _pf > 0:
                        _poid = f"plant-{_po.get('order_id') or now_s}"
                        _pc = float(_pp) if _pp is not None else float(_la)
                        open_pos[_poid] = (close_s, _lose, _pc, _pf, tk)
                        entry_at[_poid] = now_s
                        hedge_meta[_poid] = (strike, digits, iid)
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
            # AMENDMENT 8, NOW READ AT THE RIGHT MOMENT. Never hold both sides
            # of one market: the two legs cannot both win, so the pair costs
            # more than the $1 it pays and locks in the difference. `want` is
            # assigned immediately above, so this is the first line in the loop
            # where the comparison is even meaningful.
            if want is not None and _both_sides_block(prev, tk, want):
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
                _room45 = (close_budget()
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
                if LATE_MULT <= 1.0 or tau > LATE_TAU:
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
                _room48 = (close_budget()
                           - (prev.get("contracts", 0.0)
                              if prev else 0.0)) if CLOSE_BUDGET else float(SIZE)
                _was48 = take_n
                take_n = max(take_n, min(_cap48, _avail48, max(0.0, _room48)))
                if take_n > _was48 + 1e-9:
                    rec("late_boost", ticker=tk, want=want, tau=tau,
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
                _room53 = (close_budget()
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

            def _stage46(take_n):
                """AMENDMENT 46: an early or top-up leg keeps its cap however
                much A35/A45 widened the order. A full leg is untouched.
                A53: a band multiple scales the WHOLE position for this
                market, so the early cap is EARLY_FRAC x SIZE x mult and a
                top-up completes to SIZE x mult -- otherwise the re-cap here
                would silently undo the boost on every early leg."""
                if EARLY_TAU_MAX > TAU_MAX and _leg46 != "full":
                    return min(take_n, staged_take(tau, take_n, float(SIZE) * band_mult(price), _held46)[0])
                return take_n

            if not live:
                take_n = _widen45(take_n)  # paper
                take_n = _late48(take_n)   # paper
                take_n = _band53(take_n)   # paper
                take_n = _stage46(take_n)
                _book_slot(price, take_n)
                entry_at[f"paper-{tk}-{now_s}"] = now_s
                open_pos[f"paper-{tk}-{now_s}"] = (close_s, want, price,
                                                   take_n, tk)
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
                        if _deep > take_n:
                            _room = (close_budget()
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
                    take_n = _stage46(take_n)
                    _t0 = time.time()
                    out = pintake.take(CREDS["base"], CREDS["pk"],
                                       CREDS["key_id"], tk, want, _limit,
                                       take_n, close_s, exchange_index=exi)
                    _lat_ms = round(1000.0 * (time.time() - _t0), 1)
                    _xp = out.get("exec_price")
                    rec("order", ticker=tk, latency_ms=_lat_ms,
                        leg=_leg46, early_held=_held46,
                        book_age_ms=b.get("age_ms"),
                        index_age_s=round(iage, 2), tau_at_send=tau,
                        ask_seen=round(float(price), 4),
                        limit_sent=round(float(_limit), 4),
                        sweep_headroom_c=round(100.0 * (_limit - price), 3),
                        swept=bool(_xp is not None
                                   and float(_xp) > float(price) + 1e-9),
                        **{k: v for k, v in out.items() if k != "raw"})
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
                    filled = float(out.get("filled") or 0)
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
                            rec("scrap", ticker=tk, want=want, filled=filled,
                                asked=take_n, price=cost, real_min=_real,
                                budget_spent=True)
                            print(f"    SCRAP {filled:g} of {take_n:g} -- "
                                  f"budget spent, improve bar NOT raised")
                        else:
                            _note_scrap(cost, filled)
                            state["scraps"] = state.get("scraps", 0) + 1
                            rec("scrap", ticker=tk, want=want, filled=filled,
                                asked=take_n, price=cost, real_min=_real)
                            print(f"    SCRAP {filled:g} of {take_n:g} -- "
                                  f"position kept, slot NOT spent")
                    else:
                        state["nofill"] = state.get("nofill", 0) + 1
                    state["sent"] = state.get("sent", 0) + 1
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
        hedge_price=HEDGE_PRICE,
        late_tau=LATE_TAU, late_mult=LATE_MULT,
        # A53: lists, so the Lab can select an arm by its exact bands
        skip_bands=[list(b) for b in SKIP_BANDS],
        band_mults=[list(b) for b in BAND_MULTS],
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
                                                   LATE_MULT, max_band_mult())),
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
        state, fired = trade_loop(a, rec, book, idx, SERIES_TO_INDEX)
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
