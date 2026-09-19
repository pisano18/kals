"""pinlab.py -- the drawing board: every experiment, what it means, where it got to.

WHY THIS EXISTS. The operator, 2026-09-18: *"Can we get a tab that's like a
planning thing, drawing board, think tank... show all paper runs or anything
similar and explain what it does, the implication, good vs bad outcomes, why
it's good or bad... a history of paper runs that are aborted or finished and
show whether they got implemented or not and what data came from that."*

The knowledge was scattered across PREREG files, VERSIONS.md, HANDOFF.md and a
dozen results/*.md, none of which he can read from the app. This file is the
single catalogue, and `pindesk`'s Lab tab renders it.

**The rule for writing an entry: an experiment that was KILLED is as valuable
as one that shipped, and the reason it died is the part worth keeping.** Half
the entries below are things that looked good and were not. A drawing board
that only records the wins teaches nothing.

`live_progress()` attaches what each running arm has actually done, read from
its own paper log, so the catalogue is never a stale description of something
that stopped days ago.
"""
import collections
import glob
import json
import os
import re
import time
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

RESULTS = os.path.join(os.path.dirname(HERE), "results")

RUNNING, SHIPPED, KILLED, PAUSED, IDEA = "RUNNING", "SHIPPED", "KILLED", "PAUSED", "IDEA"

# `select` values: an entry names the start-record fields that distinguish its
# arm from every other arm, because the start record holds the WHOLE
# configuration and a flag's mere presence there means nothing.
SET = "<set>"          # the field is present and not null (the flag was passed)
UNSET = "<unset>"      # the field is absent or null (the flag was NOT passed)

# match: a substring of the arm's command line, used to find its paper log and
#        to tell whether it is running right now.
EXPERIMENTS = [
    # ---------------------------------------------------------------- RUNNING
    {
        "name": "Hedge on the market price, not the model (A47)",
        "status": SHIPPED, "match": "--hedge-price", "since": "2026-09-17",
        "select": {"hedge_price": SET, "band_mults": lambda v: not v},
        "outcome": "LIVE at 0.60 from 2026-09-18 (v-bands), on the live record "
                   "rather than this arm: every real loss was hedged with our "
                   "side already under 60c (4 of 4 pass -- BTC and HYPE on "
                   "09-14 at 43-58c, DOGE and BNB later), and every false "
                   "alarm was bought with our side at 73c or more (5 of 5 "
                   "blocked, -$41.72 saved). The paper arm never produced a "
                   "hedge of its own to score; the operator's 'this version "
                   "better still hedge when I lose' is answered by those four.",
        "legacy_logs": ["pinrun-paper-20260917T163428Z.jsonl",
                        "pinrun-paper-20260918T041353Z.jsonl"],
        "what": "Insurance fires only when OUR side's market price has also fallen "
                "below 50c, instead of firing on the model's belief alone.",
        "why": "The wobble study, 1,717 markets: a favourite that dips but stops "
               "above 50c recovered 48 times out of 48. One that crosses below 50c "
               "really flipped 76% of the time. The model panics at moves the "
               "market shrugs off.",
        "good": "It skips the wasted hedges and keeps the needed ones. Each wasted "
                "hedge costs a real premium.",
        "bad": "It waits too long and misses insurance we needed, which is the "
               "expensive direction. A hedge that arrives late is worse than none.",
        "watch": "Alarms it SKIPPED that went on to lose. Three of those and the "
                 "idea is dead.",
    },
    {
        "name": "Buy bigger in the last seconds (A48)",
        "status": RUNNING, "match": "--late-mult", "since": "2026-09-17",
        # late_mult SHIPS AT 1.0, so `SET` would match every log ever written.
        "select": {"late_mult": lambda v: v is not None and float(v) > 1.0, 
                   "band_mults": lambda v: not v, "hedge_price": lambda v: v is None},
        "legacy_logs": ["pinrun-paper-20260917T212112Z.jsonl"],
        "what": "Lets one order exceed the normal size when there are under 10 "
                "seconds left. Operator's idea.",
        "why": "Our own fills earn 5.35c a contract inside 5 seconds against 1.90c "
               "at 16-30 seconds -- 2.8x -- and that window is only 6% of our "
               "volume. The book is not the limit either: the median depth at our "
               "own price is 433 contracts against a size of 95.",
        "good": "The best-paying window gets more of our money. This is the "
                "largest upside on the board.",
        "bad": "Bigger size in the last seconds is also bigger size when a book "
               "collapses mid-flight, which is exactly how the Bitcoin trade cost "
               "$27.87.",
        "watch": "Money per contract in the late window, and the worst single "
                 "close.",
    },
    {
        "name": "Insurance only when the other side is a normal bet (A51)",
        "status": RUNNING, "match": "--hedge-normal", "since": "2026-09-18",
        "select": {"hedge_normal": True, 
                   "band_mults": lambda v: not v, "hedge_price": lambda v: v is None},
        "what": "Only buys insurance when the OTHER side would pass the same "
                "tests a normal bet passes: our model 99.5% sure of it, and "
                "its price at or under 98c.",
        "why": "Operator's idea: 'buy enough there just like a normal bet to "
               "offset it or even profit.' Today insurance fires on the model's "
               "panic alone at any price under a dollar, and the record is bad "
               "-- 12 insured quarter-hours, 11 ended negative, and five of "
               "them bought the other side at 10-18c, meaning the market still "
               "liked our side and we paid for nothing.",
        "good": "It fires rarely and the quarter-hours it skips end up costing "
                "less than the premiums we save. Firing rarely IS the point.",
        "bad": "It waits so long that real insurance is missed. By the time the "
               "model is 99.5% sure the other side wins, that side is usually "
               "expensive, and a contract bought at 97c returns 3c -- so the "
               "offset will be partial at best. This may turn out to be an "
               "argument for not taking the bet at all rather than rescuing it.",
        "watch": "Quarter-hours where insurance was HELD OFF and the bet then "
                 "lost, against the premiums saved on the ones that recovered.",
    },
    {
        "name": "45 seconds at FULL size, but only when the market agrees (A50)",
        "status": RUNNING, "match": "--early-max-edge", "since": "2026-09-18",
        # A51 ALSO CARRIES `--early-max-edge`, because it is built on top of
        # this one. Selecting on that flag alone matched both logs and took
        # the newer, so A50 displayed A51's markets -- the same
        # arm-reads-another-arm's-log bug this `select` mechanism was added to
        # kill, re-introduced the moment a second arm inherited the flag.
        # Whenever an arm is layered on another, the older one must exclude it.
        "select": {"early_max_edge": SET, "hedge_normal": lambda v: not v,
                   # A52 inherits this flag as well; same trap, third time
                   "hedge_jump": lambda v: v is None,
                   # the 99c arm carries the cap too; A50 proper is at 98c.
                   # A start record without the field predates it and means
                   # the default, which is 98c.
                   "price_ceiling": lambda v: v is None or abs(float(v) - 0.98) < 1e-9,
                   "band_mults": lambda v: not v, "hedge_price": lambda v: v is None},
        "what": "Buys a WHOLE bet at 31-45 seconds out, not a third -- but only "
                "when our model and the market price are within 3 cents of each "
                "other.",
        "why": "Operator: 'we need to figure out how to be able to buy it at "
               "full price 45 seconds out.' Size is a blunt protection; it "
               "costs us on every good trade to survive the bad ones. Out at "
               "45 seconds only a quarter of the settlement average is locked, "
               "so when the market disagrees with us by a lot the MARKET is "
               "usually right -- the reverse of inside 30 seconds, where that "
               "same disagreement is the entire edge. The one loss in the "
               "current 45-second arm was exactly this: bought at 93c while "
               "the model said 99.9%, and it cost more than the other "
               "seventeen trades made.",
        "good": "It makes more per early bet than the uncapped arm AND refuses "
                "at least 5 of its trades. Then full size at 45 seconds is "
                "defensible and the third goes away.",
        "bad": "It refuses trades that went on to win while still losing money. "
               "That is the expensive direction and it kills the idea.",
        "watch": "Early markets that the cap refused, and what they did next. "
                 "Bars are in results/PREREG_a50_early_edge_cap.md and are not "
                 "moved after the fact.",
    },
    {
        "name": "The 45-second early leg (A46 + A49)",
        "status": RUNNING, "match": "--early-tau", "since": "2026-09-17",
        "select": {"early_tau_max": 45, "pin": 0.995, "early_max_edge": UNSET,
                   # the staged arm (a third, then topped up) shares every
                   # other setting; a FULL early bet is early_frac 1.0
                   "early_frac": 1.0,
                   "band_mults": lambda v: not v, "hedge_price": lambda v: v is None},
        "what": "Buys between 31 and 45 seconds out at FULL size since 2026-09-18 "
                "~17:0xZ (a third before that), only if the price is at least "
                "90c and the model is within 3c of the market.",
        "why": "The cheap offers get taken a median of 41 seconds before the close "
               "while our window starts at 30. This is the only lever aimed at "
               "that.",
        "good": "More trades from the window where the buying actually happens.",
        "bad": "Less of the settlement average is locked that far out, so the "
               "model leans harder on a volatility guess. It went live at FULL "
               "size for one day and one bad fill took back most of what thirty "
               "good ones made.",
        "watch": "Losses on closes that carried an early leg. Revert at 3 in 40, "
                 "or 2 in the first 15.",
    },
    {
        "name": "Commodities, paper (all five, every window)",
        "status": RUNNING, "match": "cmdarm.py", "since": "2026-09-17",
        # cmdarm's start record has no `mode`; `size_dollars` is cmdlive's.
        "select": {"series": SET, "dry": UNSET},
        "what": "Gold, oil, silver, copper and natural gas on their own best "
                "windows, plus one window deliberately chosen to LOSE as a control.",
        "why": "Commodities settle on the close of a one-minute candle, not a "
               "60-second average, so their safe zones are at BOTH ends of the "
               "quarter hour with a dangerous middle. Opposite shape to crypto.",
        "good": "A second product. The crypto pool halved on 09-13 and more venues "
                "is the only answer to that.",
        "bad": "If the deliberate loser makes money, the whole method is misreading "
               "the world and nothing else it says can be trusted.",
        "watch": "The anti-silver control above all else.",
    },
    {
        "name": "Commodities, LIVE (oil, last 15 seconds, $10)",
        "status": PAUSED, "match": "cmdlive.py", "since": "2026-09-17",
        "until": "STOOD DOWN 2026-09-18 17:31:52Z, by its own brake at "
                 "-$27.28 and then by the operator: 'Oil is sucking bad. "
                 "Ruined gains 2 days in a row now. Turn it off, figure out "
                 "a strategy for it, then paper trade it.' It lost $59.46 on "
                 "09-17 and $27.28 on 09-18 -- $86.74 against crypto's $115.68 "
                 "and $67.40 those days, which is the whole of 'we are only up "
                 "$22'. results/cmdlive.stop is present; boot_all.ps1 has it "
                 "behind `if ($false ...)`. It does NOT restart on a reboot.",
        "select": {"size_dollars": SET},
        "what": "Real money on ONE cell: oil at 95-99c inside the final 15 seconds.",
        "why": "Paper cannot answer whether an offer would reach US -- on crypto "
               "the tape and our fills differed 31x in loss rate. Only real fills "
               "can.",
        "good": "It fills and holds its loss rate. Then the window widens.",
        "bad": "Losses at a rate the tape did not predict, which would mean "
               "commodity offers are adversely selected the way crypto's are.",
        "watch": "Stops itself at $25 down or 4 losses. First day: 29 won, 3 lost, "
                 "-$56.83, and two thirds of that was one defect (betting the same "
                 "market twice through different windows), now fixed.",
    },
    {
        "name": "Score several entry-time warnings and refuse on a vote (measured, dead)",
        "status": KILLED, "since": "2026-09-18",
        "what": "The operator's idea after a single sigma stress refused 88% of "
                "wins: treat each warning as one box, refuse only when several "
                "are ticked. Boxes tried: cushion under 3 sd at entry, sigma "
                "under 0.7x the coin's median (a calm patch), edge over 3c.",
        "why": "Every loss in both windows is a 10-18 sigma single-second jump "
               "with sigma understated 2-3x at entry, and the losers sit inside "
               "the winners' confidence range. If any entry-time signal saw the "
               "jump coming, a vote would catch it without a single veto's cost.",
        "outcome": "NOTHING AT ENTRY SEES IT. 920 live+paper markets, 19 misses. "
                   "31-45 s pooled: one flag catches 4/4 misses but refuses 121 "
                   "of 161 wins (75%); two flags catch 1/4 and refuse 22%; three "
                   "catch 0/4. Singly, every entry-time feature -- cushion, edge, "
                   "price, relative sigma, book age, index age -- needs a "
                   "threshold that refuses 45-98% of wins to catch every miss, "
                   "and the misses are barely enriched in any feature's worst "
                   "fifth (live 3-30 s: 4 of 11 misses vs 91 of 463 wins on "
                   "cushion). The HINDSIGHT features -- realized/sigma ratio and "
                   "biggest one-second move -- put 100% of misses in the worst "
                   "fifth every time, which proves the losses ARE jumps and "
                   "proves they are invisible beforehand. And the calm-patch "
                   "story is contradicted here: all four 45 s misses had sigma "
                   "1.2-1.8x ABOVE their coin's median, not below.",
        "attribution": "None shipped. The defence against a jump is after "
                       "entry, not before: the hedge (+$46.55 net across every "
                       "alarm) and, if anything, a faster post-entry reaction to "
                       "the jump itself (A47 waits for the market price to "
                       "agree). Study: results/sigcheck.py, results/sigcheck_out.json.",
    },
    {
        "name": "Sell the winner early at 99.9c instead of holding (measured, dead)",
        "status": KILLED, "since": "2026-09-18",
        "what": "Operator's question: once a position is worth ~99.9c, post a "
                "resting ask and take the money rather than carrying it to "
                "settlement.",
        "why": "It would convert a small tail risk into certainty, and the bot "
               "has never sold anything -- every position runs to settlement.",
        "outcome": "THE ARITHMETIC IS REAL BUT TOO THIN TO BUILD FOR. Measured "
                   "on 36 tape hours: a side that traded at 99c+ inside a "
                   "minute of the close still flipped 3 times in 1,080 "
                   "(0.28%), so HOLDING is worth 99.72c. Selling at 99.9c is "
                   "worth 99.9c, a gain of 0.18c a contract. Liquidity is not "
                   "the obstacle -- 62% of near-close winning-side volume "
                   "(1.95M contracts in 24 hours) trades at 99.8c or better, "
                   "and as a MAKER we would pay no fee. At 77 contracts that "
                   "is 14c a market, and at today's ~12 signals a day, under "
                   "$2 a day.",
        "attribution": "Not built. It needs the first sell path this bot has "
                       "ever had -- new order state, cancel-before-settlement, "
                       "and a bug there sells a winner at a bad price. That "
                       "risk is larger than $2 a day. The usual second reason "
                       "to exit early (free the capital) does not apply: we "
                       "are limited by SUPPLY, about 12 signals a day, not by "
                       "capital or open-position count.",
    },
    {
        "name": "Refuse a market where the model reverses itself (measured, dead)",
        "status": KILLED, "since": "2026-09-18",
        "what": "The idea: if the model wants one side early in a quarter-hour "
                "and the other side seconds later, it has contradicted itself, "
                "so refuse the market.",
        "why": "It came out of the 09-18 oil loss, where the bot bought NO at "
               "9 seconds out and YES at 2 seconds out and lost $9.41.",
        "outcome": "NO RELATIONSHIP, and the phenomenon is nearly absent. Live "
                   "crypto: ZERO reversals in 558 settled markets -- the "
                   "settlement average is mostly locked by the time we look, "
                   "so a late reverse is close to impossible by construction. "
                   "Commodities can reverse, because only the final print of a "
                   "one-minute candle matters, but paper found 4 reversals in "
                   "311 markets and NONE of them lost (+$6.47), while live oil "
                   "had 2 in 45 and split one-one.",
        "attribution": "Nothing. Six reversal markets in total across every "
                       "source, no measurable edge, and refusing them would "
                       "have changed almost nothing. Do not resurrect this "
                       "without a much larger commodity sample.",
    },
    {
        "name": "Coin Race (KXCRYPTOLEAD15M), paper",
        "status": RUNNING, "match": "pinracearm.py", "since": "2026-09-15",
        "select": {"table": SET},
        "what": "Which coin leads over a quarter hour. Five legs per race and four "
                "of them lose, so the NO side of a trailer is a much flatter bet "
                "than the leader's YES.",
        "why": "A whole series we do not trade at all, and volume is the binding "
               "constraint.",
        "good": "A second crypto product with no new venue needed.",
        "bad": "An early version took up to 17 legs on one race and lost $1,682 "
               "in paper. Uncapped legs on one event is not diversification.",
        "watch": "Money per race, never legs won. One arm went 8 of 9 legs and "
                 "still lost.",
    },
    # ---------------------------------------------------------------- SHIPPED
    {
        "name": "Hedge threshold 0.80 -> 0.60",
        "status": SHIPPED, "since": "2026-09-16", "match": None,
        "what": "Insurance fires when belief in our side drops under 60%, not 80%.",
        "why": "Hedges at high belief were firing on noise.",
        "outcome": "GOOD, and measurable. Of 14 live hedges, the 5 wasted ones "
                   "at belief 0.64-0.89 could not happen under the new gate. Under "
                   "0.60 exactly 7 would have fired and 6 of those were needed.",
        "attribution": "Hedging is +$14.30 across its whole life (6 needed paying "
                       "+$56.01, 6 wasted costing -$41.72). The change removes most "
                       "of the wasted side.",
    },
    {
        "name": "One position per MARKET (commodities)",
        "status": SHIPPED, "since": "2026-09-17", "match": None,
        "what": "The first window to fill claims a market; later windows on the "
                "same market are refused whichever side they want.",
        "why": "Windows are not independent opportunities. They are different "
               "moments looking at the same yes-or-no question.",
        "outcome": "Found by losing. One oil market was bought NO at 180 seconds "
                   "AND NO again at 60 seconds through a different window, then YES "
                   "at 23 seconds. One adverse event became two losses, -$58.84.",
        "attribution": "Would have halved that day's commodity loss. $67.72 of "
                       "unintended extra stake went on across 7 of 22 markets.",
    },
    {
        "name": "The books come from Kalshi, not our logs",
        "status": SHIPPED, "since": "2026-09-18", "match": None,
        "what": "pinledger reads /portfolio/settlements; the app and the phone bot "
                "read that. Our logs still explain WHY we traded.",
        "why": "Our logs write one line per LEG, so a hedged market looked like two "
               "trades and one of them like a pure loss.",
        "outcome": "The phone bot had texted a -$3.93 LOSS on a DOGE market Kalshi "
                   "settled at +$4.36. Day totals were crypto-only, double-counted, "
                   "and missed every position open when a process was killed.",
        "attribution": "No money either way -- it changes what we SEE, which had "
                       "been wrong by tens of dollars a day in both directions.",
    },
    # ----------------------------------------------------------------- KILLED
    {
        "name": "Resting a bid instead of crossing the spread",
        "status": KILLED, "since": "2026-09-12", "match": None,
        "what": "Post an offer and wait instead of taking what is there.",
        "why": "Makers pay no fee, and a third of all opportunities die because "
               "nobody is selling the winning side.",
        "outcome": "KILLED, and the mechanism should stop this ever being "
                   "re-proposed: a bid resting one tick under the ask was filled on "
                   "29% of markets that WON and on 100% of the 17 that LOST. "
                   "Whoever reaches down to your resting bid already knows. It did "
                   "not even get a better price (94.16c against the taker's 94.05c).",
        "attribution": "Resting lost to taking in 113 of 114 comparisons across "
                       "9 days and 793 closes.",
    },
    {
        "name": "A minimum distance-from-the-line gate",
        "status": KILLED, "since": "2026-09-18", "match": None,
        "what": "Refuse trades where the price sits too few standard deviations "
                "from the strike, however confident the model is.",
        "why": "6 of our 13 all-time losses sat under 3 sd, including the $27.87 "
               "Bitcoin loss at 2.70 sd. The model maps that distance through a "
               "normal curve while the index has a tail 44x fatter.",
        "outcome": "KILLED BY THE MONEY. Every threshold loses: a 3 sd floor skips "
                   "144 settled markets to avoid 5 losers, and those 144 markets "
                   "MADE $86.85. Thin-cushion trades lose more often AND are still "
                   "profitable.",
        "attribution": "-$5.80 at 2.0 sd, -$86.85 at 3.0, -$105.31 at 4.0. The "
                       "lesson: counting losses is not counting money.",
    },
    {
        "name": "Raise the 98c price ceiling",
        "status": KILLED, "since": "2026-09-17", "match": None,
        "what": "Buy the near-certainties priced above 98c that we currently refuse.",
        "why": "431 refusals, and 311 of the markets behind them settled our way "
               "with ZERO losses.",
        "outcome": "Not worth it. It would roughly DOUBLE the number of trades and "
                   "add about $10 a day, because at 99c a win pays one cent. A "
                   "dormant gate also takes over at 98.7c, so a straight change "
                   "delivers a third of what it looks like.",
        "attribution": "+$1.94/day reachable immediately. Against a run earning "
                       "$70-115 a day, it is noise with a risk attached.",
    },
    {
        "name": "The dump guard is costing us winners",
        "status": KILLED, "since": "2026-09-17", "match": None,
        "what": "The gate that refuses any offer more than 15c under fair value -- "
                "an unnamed price floor at 84.5c.",
        "why": "It had flagged 17 markets, and 10 of them went on to win.",
        "outcome": "THE CLAIM WAS WRONG. A refusal marks a MOMENT, not a market's "
                   "fate: the bot kept looking and BOUGHT 10 of those 17 seconds "
                   "later when the discount narrowed. Their wins are already in our "
                   "P&L. Of the 4 it truly blocked, it MADE us about $12.",
        "attribution": "No change deployed. The guard stays at 0.15.",
    },
    # ------------------------------------------------------------------ IDEAS
    {
        "name": "Price cap 98c -> 99c (7-day arm)",
        "status": RUNNING, "match": "--price-ceiling", "since": "2026-09-18",
        "select": {"price_ceiling": lambda v: v is not None and float(v) > 0.985, 
                   "band_mults": lambda v: not v, "hedge_price": lambda v: v is None},
        "what": "Buys asks up to 99c instead of stopping at 98c. Everything "
                "else identical to the live bot. Running SEVEN days, not the "
                "usual 40 closes, on the operator's word: 'This one will "
                "probably run for some time longer than the others to really "
                "be sure.'",
        "why": "The 98c cap has blocked 461 markets and turned away 379 "
               "would-be winners and ZERO losers (+$122.80 if every one had "
               "filled). When the band was allowed live it was 82 markets, 1 "
               "loss, +$51.07 including the loss.",
        "good": "It earns more per day than the live bot without its loss rate "
                "passing 1 in 70, which is break-even at 98-99c.",
        "bad": "A loss at 98.5c takes about 65 wins to earn back where one at "
               "98c takes 53, so a single extra loss erases weeks of the gain. "
               "The live margin is 0.2 points on ONE loss -- its upper bound is "
               "near 5%, which is why this needs a week and not a day.",
        "watch": "Loss rate in the 98-99c band alone, not the arm's total. The "
                 "cheaper trades it also takes will swamp the signal otherwise.",
    },
    {
        "name": "AMENDMENT 15 -- the belief-collapse hedge, built and NOT yet deployed (09-12 00:11 ET)",
        "status": RUNNING, "match": "pinvin_0912a.py", "since": "2026-09-18",
        # code_sha is the hash of that vintage file itself and cannot collide
        # with any other arm -- the settings alone would match dozens of logs.
        "select": {"code_sha": "438725fabfde"},
        "what": "The bot exactly as commit `7b6e7d7` posted it, 09-12 00:11 ET, running as a "
                "paper arm on today's markets. The oldest version in the window. Hedge trigger 0.90, no bank brake, no auto-size, no jump gate, no both-sides guard, no close contract budget, one bet per market. Nine amendments behind today.",
        "why": "Operator, 2026-09-18: 'Run any version posted on the 12th "
               "12am through 13th end of day and run them and put them in "
               "the lab.' The 13th was our best day ($114.77) and the 12th "
               "the day before it; every version since has been an "
               "improvement on paper and the account has not moved with "
               "them. These five run on their OWN shipped defaults -- no "
               "flags -- so each is the version as posted, not the version "
               "as we would configure it now.",
        "good": "It beats today's bot on the same markets. Then something "
                "between 09-12 00:11 ET and now is costing us, and the diff is a short "
                "list: this file against the current one.",
        "bad": "It trails today's bot. Then the amendments since were right "
               "and the fall in daily money is the market, which is what "
               "the fixed-size paper arms already say (they saw the same "
               "1.5c price rise the live bot did).",
        "watch": "Money per settled market against the live bot and against "
                 "the other vintages -- the ladder between them is where any "
                 "single bad change would show.",
    },
    {
        "name": "AMENDMENT 16 -- SIZE follows the bank automatically (09-12 19:13 ET)",
        "status": RUNNING, "match": "pinvin_0912b.py", "since": "2026-09-18",
        # code_sha is the hash of that vintage file itself and cannot collide
        # with any other arm -- the settings alone would match dozens of logs.
        "select": {"code_sha": "20b28c8fa0a4"},
        "what": "The bot exactly as commit `c0f8e33` posted it, 09-12 19:13 ET, running as a "
                "paper arm on today's markets. The first version that sized itself off the balance. Hedge trigger down to 0.80 after the backtest rebuild; still no bank brake, no jump gate, no close budget.",
        "why": "Operator, 2026-09-18: 'Run any version posted on the 12th "
               "12am through 13th end of day and run them and put them in "
               "the lab.' The 13th was our best day ($114.77) and the 12th "
               "the day before it; every version since has been an "
               "improvement on paper and the account has not moved with "
               "them. These five run on their OWN shipped defaults -- no "
               "flags -- so each is the version as posted, not the version "
               "as we would configure it now.",
        "good": "It beats today's bot on the same markets. Then something "
                "between 09-12 19:13 ET and now is costing us, and the diff is a short "
                "list: this file against the current one.",
        "bad": "It trails today's bot. Then the amendments since were right "
               "and the fall in daily money is the market, which is what "
               "the fixed-size paper arms already say (they saw the same "
               "1.5c price rise the live bot did).",
        "watch": "Money per settled market against the live bot and against "
                 "the other vintages -- the ladder between them is where any "
                 "single bad change would show.",
    },
    {
        "name": "AMENDMENT 17 -- a close is capped on CONTRACTS, coins unlimited (09-12 21:49 ET)",
        "status": RUNNING, "match": "pinvin_0913a.py", "since": "2026-09-18",
        # code_sha is the hash of that vintage file itself and cannot collide
        # with any other arm -- the settings alone would match dozens of logs.
        "select": {"code_sha": "4b3abeba0cbc"},
        "what": "The bot exactly as commit `3f393ea` posted it, 09-12 21:49 ET, running as a "
                "paper arm on today's markets. The close budget arrives: a close may spend MAX_PER_CLOSE x SIZE contracts across any number of coins. This is the shape the bot still has today.",
        "why": "Operator, 2026-09-18: 'Run any version posted on the 12th "
               "12am through 13th end of day and run them and put them in "
               "the lab.' The 13th was our best day ($114.77) and the 12th "
               "the day before it; every version since has been an "
               "improvement on paper and the account has not moved with "
               "them. These five run on their OWN shipped defaults -- no "
               "flags -- so each is the version as posted, not the version "
               "as we would configure it now.",
        "good": "It beats today's bot on the same markets. Then something "
                "between 09-12 21:49 ET and now is costing us, and the diff is a short "
                "list: this file against the current one.",
        "bad": "It trails today's bot. Then the amendments since were right "
               "and the fall in daily money is the market, which is what "
               "the fixed-size paper arms already say (they saw the same "
               "1.5c price rise the live bot did).",
        "watch": "Money per settled market against the live bot and against "
                 "the other vintages -- the ladder between them is where any "
                 "single bad change would show.",
    },
    {
        "name": "v-a21 -- the confidence gate 0.995 -> 0.990 (09-13 09:52 ET)",
        "status": RUNNING, "match": "pinvin_0913b.py", "since": "2026-09-18",
        # code_sha is the hash of that vintage file itself and cannot collide
        # with any other arm -- the settings alone would match dozens of logs.
        "select": {"code_sha": "1472f4e77e63"},
        "what": "The bot exactly as commit `a8973c1` posted it, 09-13 09:52 ET, running as a "
                "paper arm on today's markets. The loosest confidence gate the bot has ever run live, reverted the same day. Also carries the volatility ruler and the down-only ruler (A20/A20b), both since reverted for cutting signals 63%.",
        "why": "Operator, 2026-09-18: 'Run any version posted on the 12th "
               "12am through 13th end of day and run them and put them in "
               "the lab.' The 13th was our best day ($114.77) and the 12th "
               "the day before it; every version since has been an "
               "improvement on paper and the account has not moved with "
               "them. These five run on their OWN shipped defaults -- no "
               "flags -- so each is the version as posted, not the version "
               "as we would configure it now.",
        "good": "It beats today's bot on the same markets. Then something "
                "between 09-13 09:52 ET and now is costing us, and the diff is a short "
                "list: this file against the current one.",
        "bad": "It trails today's bot. Then the amendments since were right "
               "and the fall in daily money is the market, which is what "
               "the fixed-size paper arms already say (they saw the same "
               "1.5c price rise the live bot did).",
        "watch": "Money per settled market against the live bot and against "
                 "the other vintages -- the ladder between them is where any "
                 "single bad change would show.",
    },
    {
        "name": "AMENDMENTS 28 and 29 -- spend the budget we already allow ourselves (09-13 18:33 ET)",
        "status": RUNNING, "match": "pinvin_0913c.py", "since": "2026-09-18",
        # code_sha is the hash of that vintage file itself and cannot collide
        # with any other arm -- the settings alone would match dozens of logs.
        "select": {"code_sha": "100ca4058a18"},
        "what": "The bot exactly as commit `6ee8409` posted it, 09-13 18:33 ET, running as a "
                "paper arm on today's markets. Late on the best day. Two bets per MARKET, the depth floor lowered, best-first scan order, per-gate refusal records. Within hours of the 09-13 23:51 version that pinrun913.py already runs.",
        "why": "Operator, 2026-09-18: 'Run any version posted on the 12th "
               "12am through 13th end of day and run them and put them in "
               "the lab.' The 13th was our best day ($114.77) and the 12th "
               "the day before it; every version since has been an "
               "improvement on paper and the account has not moved with "
               "them. These five run on their OWN shipped defaults -- no "
               "flags -- so each is the version as posted, not the version "
               "as we would configure it now.",
        "good": "It beats today's bot on the same markets. Then something "
                "between 09-13 18:33 ET and now is costing us, and the diff is a short "
                "list: this file against the current one.",
        "bad": "It trails today's bot. Then the amendments since were right "
               "and the fall in daily money is the market, which is what "
               "the fixed-size paper arms already say (they saw the same "
               "1.5c price rise the live bot did).",
        "watch": "Money per settled market against the live bot and against "
                 "the other vintages -- the ladder between them is where any "
                 "single bad change would show.",
    },
    {
        "name": "The 2026-09-13 bot, re-run beside today's",
        "status": RUNNING, "match": "pinrun913.py", "since": "2026-09-18",
        # code_sha is the hash of pinrun913.py itself and cannot collide with
        # any other arm. Selecting on max_per_market=1 would also match nine
        # historical logs from before the flag changed.
        "select": {"code_sha": "1e57c5cf45bb"},
        "what": "The bot exactly as it ran on 09-13, when it made $114.78 and "
                "took 21 cheap fills, running as a paper arm next to today's "
                "live bot on the same markets at the same instant.",
        "why": "Operator: 'Are you absolutely certain it isn't our bot "
               "filtering them out... Do we still have that version from way "
               "back then?' Our cheap (<95c) fills fell from 21-22 a day to "
               "2-8 while the tape's cheap supply stayed flat, and my check "
               "that we were not refusing them was blind: the confidence gate "
               "fires BEFORE a price is read, so a cheap offer refused there "
               "carries no price and the query counted zero. Three gates exist "
               "now that did not on 09-13 (both_sides, jump_against, "
               "against_thin), all added 09-14.",
        "good": "It takes cheap fills today's bot refuses. Then we are "
                "filtering them out and the gate is findable -- which it "
                "ALREADY DID within 15 minutes, catching A50 refusing a 94.8c "
                "fill at tau 25 that the old bot bought and won.",
        "bad": "It sees the same empty book we do. Then we are arriving after "
               "the offers and the answer is speed or a second venue, not a "
               "setting.",
        "watch": "Cheap (<95c) fills per day, side by side. Saturday is the "
                 "biggest cheap-supply day of the week (2x a weekday), so the "
                 "first Saturday is the sharpest test.",
    },
    {
        "name": "Hedge on the JUMP, not on the belief (A52)",
        "status": RUNNING, "match": "--hedge-jump", "since": "2026-09-18",
        "select": {"hedge_jump": SET, 
                   "band_mults": lambda v: not v, "hedge_price": lambda v: v is None},
        "what": "Buy insurance the instant the index makes a one-second move of "
                "N sigma against us AFTER entry, instead of waiting for the "
                "model's belief to fall through 60%. It is a reaction, not a "
                "refusal: no trade is turned away.",
        "why": "Every loss we have is a post-entry jump of 10-18 sigma that "
               "nothing at entry sees coming (the entry-time vote, killed the "
               "same day, proved that). The current hedge fires on belief, "
               "which is DOWNSTREAM of the jump, by which time the other side "
               "costs 50-70c. A trigger on the jump itself fires while the "
               "market still likes our side, when the other side is 10-20c -- "
               "so a needed hedge pays 80-90c a contract instead of 30-50c, and "
               "a wasted one costs a few dollars, not twenty.",
        "good": "Measured on 920 markets (results/sigcheck_out.json), a firing "
                "upper bound: live 3-30 s at 5 sigma catches 11 of 11 losses "
                "and fires on 9% of winners; at 8 sigma, 7 of 11 and 4%; at 10 "
                "sigma, 5 of 11 and 2%. Live 31-45 s at 8 sigma catches its one "
                "loss and fires on 5% of winners.",
        "bad": "These records hold the biggest move, not WHEN it came relative "
               "to the price collapse. If the jump and the collapse are the "
               "same second, the hedge fills at 60c anyway and this buys "
               "nothing over the belief trigger. The smallest jump among the 19 "
               "misses is 4.3 sigma and the largest among winners is 62.6, so "
               "no threshold is clean; the money is in the fill price, which "
               "only a paper arm can measure.",
        "watch": "For each alarm: the index-jump time, the hedge fill time, and "
                 "the fill price, against what the belief trigger would have "
                 "paid on the same market.",
    },
    # ---- AMENDMENT 53 arms (2026-09-18). All share the v-bands live
    # baseline; each changes one thing; the last changes everything. The
    # selectors name EVERY distinguishing field, because the layered-arm trap
    # has now been sprung three times.
    {
        "name": "v-bands baseline, in paper (the control for the band arms)",
        "status": RUNNING, "match": "arm-b-control", "since": "2026-09-18",
        "select": {"skip_bands": lambda v: v == [], "band_mults": lambda v: v == [[0.9, 0.94, 1.5]],
                   "early_min_price": 0.9, "early_max_edge": 3.0},
        "what": "Exactly the live flag set after v-bands: hedge only when the "
                "market agrees (0.60), 1.5x at 90-94c that switches itself "
                "off after one boosted loss, the 45 s leg at 90c+ with the 3c "
                "edge cap. (The 94-96c skip was withdrawn before it ran.)",
        "why": "Every other band arm is read against this one on the same "
               "markets at the same instant. Its start record is also the "
               "proof that the live startup path comes up with the new flags.",
        "good": "It tracks the live bot's fills. Then the control is honest.",
        "bad": "It diverges from live. Then paper fills are not our fills "
               "here and none of the arms can be read.",
        "watch": "Fills per day and the `band_boost` records: was/now/cap/"
                 "avail/room say which rail bound each boost.",
    },
    {
        "name": "The 45 s leg opened to the bands that earn (no edge cap, 80c floor)",
        "status": RUNNING, "match": "arm-b-early-open", "since": "2026-09-18",
        "select": {"early_min_price": 0.8, "early_max_edge": UNSET,
                   "band_mults": lambda v: v == [[0.9, 0.94, 1.5]], "skip_bands": lambda v: v == []},
        "what": "The 31-45 s leg may buy from 80c up, with A50's 3c edge cap "
                "off. Today it refuses anything under 90c and anything with "
                "more than 3c of edge -- which is every trade in the 80-94c "
                "band, the one that returns 8-14%.",
        "why": "Operator: 'We need to see if we can buy 45s at better bands "
               "that are currently blocked.' A50 exists because on the tape "
               "6c+ edges at 31-45 s lost 3 of 11; that was a tape count, "
               "never a live one, and A50 shipped broken for ten hours, so "
               "nothing live has ever measured it.",
        "good": "Early fills under 94c settle like the late ones (0-1 losses "
                "in the first 30). Then a graduated live step follows.",
        "bad": "Two or more losses in the first 20 early sub-94c closes. Paper "
               "understates our loss rate (rule 5), so a bad paper result is "
               "final.",
        "watch": "Early-leg fills under 94c: count, price, and settled result, "
                 "against the control's late fills on the same markets.",
    },
    {
        "name": "The 45 s leg with the edge cap off, floor kept at 90c",
        "status": RUNNING, "match": "arm-b-early-nocap", "since": "2026-09-18",
        "select": {"early_min_price": 0.9, "early_max_edge": UNSET,
                   "band_mults": lambda v: v == [[0.9, 0.94, 1.5]], "skip_bands": lambda v: v == []},
        "what": "Same as the control but A50's 3c cap is off: the early leg "
                "may take a 90-94c ask with 6-10c of edge.",
        "why": "Separates the two blocks. If this arm matches early-open, the "
               "floor is not what is costing us; if it lags, the 80-90c band "
               "at 45 s is where the money was.",
        "good": "More early fills at 90-94c, settling clean.",
        "bad": "Losses appear that the control does not have.",
        "watch": "Early fills at 90-94c vs the control's, same markets.",
    },
    {
        "name": "Skip 94-96c (withdrawn from live; tested here instead)",
        "status": RUNNING, "match": "arm-b-skip9496", "since": "2026-09-18",
        "select": {"skip_bands": lambda v: v == [[0.94, 0.96]], "band_mults": lambda v: v == [[0.9, 0.94, 1.5]],
                   "early_max_edge": 3.0},
        "what": "The control with one change: any ask at 94.0-95.9c is refused.",
        "why": "It was staged for live on the whole-history figure (+0.8%, 83 "
               "closes) and withdrawn when the operator asked whether that was "
               "coincidence: on the modern bot the band is 38 closes, 1 loss, "
               "+2.25%. So it is tested, not deployed.",
        "good": "The arm matches the control on money while taking fewer "
                "trades. Then the band was dead weight after all.",
        "bad": "It trails the control by about the band's +2.3% a day. Then "
               "the skip is dead and the band stays.",
        "watch": "Money per day against the control; the `price_band` "
                 "refusals scored as if filled.",
    },
    {
        "name": "Skip 94-97.5c",
        "status": RUNNING, "match": "arm-b-skip975", "since": "2026-09-18",
        "select": {"skip_bands": lambda v: v == [[0.94, 0.975]], "band_mults": lambda v: v == [[0.9, 0.94, 1.5]],
                   "early_max_edge": 3.0},
        "what": "The refused band widens to take in 96-97.5c as well.",
        "why": "Operator: 'omitting 94-96 and 94-97.5'. 96-97.5c returned "
               "+1.2% on 130 closes with a 2.3% loss rate against a 3% "
               "break-even -- thin, but positive, unlike 94-96c.",
        "good": "Nothing: this arm can only lose volume. It is here to price "
                "that volume: what the wider skip gives up per day.",
        "bad": "It gives up more than the band's +1.2% is worth in slots "
               "freed. Then 94-96c stays the skip.",
        "watch": "Money per day against the control, and the `price_band` "
                 "refusals scored as if filled.",
    },
    {
        "name": "2x at 90-94c (the next sizing step, run ahead in paper)",
        "status": RUNNING, "match": "arm-b-mult2", "since": "2026-09-18",
        "select": {"band_mults": lambda v: v == [[0.9, 0.94, 2.0]], "skip_bands": lambda v: v == []},
        "what": "Inside 90-94c one order may reach 2 x SIZE instead of 1.5x.",
        "why": "The live step is 1.5x with a bar (v-bands). This arm shows how "
               "often the book holds 2x, and which rail binds, so the step to "
               "2x is sized before it is taken.",
        "good": "Most boosts reach 2x and the binding rail is the book, not "
                "the drawdown headroom.",
        "bad": "The headroom binds most of the time. Then the bank, not the "
               "flag, is the limit and 2x changes nothing.",
        "watch": "`band_boost` records: now/cap/avail/room.",
    },
    {
        "name": "Go harder: 2x across 80-94c, skip 94-97.5c",
        "status": RUNNING, "match": "arm-b-harder", "since": "2026-09-18",
        "select": {"band_mults": lambda v: v == [[0.8, 0.9, 2.0], [0.9, 0.94, 2.0]], "early_max_edge": 3.0},
        "what": "Two boosted bands (80-90c and 90-94c, both 2x) and the wider "
                "skip, with the 45 s leg as live.",
        "why": "Operator: 'just going harder by either more money, doubling "
               "down, or buying earlier.' 80-90c returned +13.6% on 29 closes "
               "with ONE loss -- its upper bound sits at its 15% break-even, "
               "which is why it is NOT in the live step.",
        "good": "The 80-90c band keeps its record at 2x in paper. Then it is "
                "a candidate for a live 1.5x.",
        "bad": "A second loss in 80-90c. Then the band stays at 1x live "
               "whatever the average says.",
        "watch": "80-90c closes and losses; boosts per day; the drawdown "
                 "headroom hitting its floor.",
    },
    {
        "name": "Everything at once: early open + go harder",
        "status": RUNNING, "match": "arm-b-all", "since": "2026-09-18",
        "select": {"band_mults": lambda v: v == [[0.8, 0.9, 2.0], [0.9, 0.94, 2.0]], "early_max_edge": UNSET,
                   "early_min_price": 0.8},
        "what": "The early leg opened to 80c+ with no cap, 2x across 80-94c, "
                "94-97.5c skipped.",
        "why": "The interactions: an early 85c fill at 2x is the largest, "
               "earliest, least-locked bet any arm makes. If this arm wins "
               "and the single-change arms do not, the win is an interaction "
               "and needs its own test before anything goes live.",
        "good": "Beats every single-change arm on the same closes.",
        "bad": "Its worst close. One 2x early loss at 85c is about $130 at "
               "today's size.",
        "watch": "Worst close, and the early 2x fills specifically.",
    },
    # ---- THE 60-SECOND LADDER (2026-09-18). Operator: "Do we have an arm
    # for testing buying early in increments up to 60 seconds?" We did not --
    # the old arm-early60 ended on 09-17 and the band rewrite dropped it.
    # All three carry the v-bands live baseline and differ only in the early
    # leg, so the selectors name early_tau_max 60 plus what separates them.
    {
        "name": "A third at 46-60 s, topped up inside 30 s (the increments)",
        "status": RUNNING, "match": "arm-e60-third", "since": "2026-09-18",
        "select": {"early_tau_max": 60, "early_frac": 0.333,
                   "early_min_price": 0.9, "early_max_edge": 3.0},
        "what": "Buys a THIRD of a bet as soon as a market qualifies between "
                "46 and 60 seconds out, then completes it to a full bet once "
                "inside 30 seconds -- two bites, at two different levels of "
                "certainty.",
        "why": "Settlement is the mean of sixty one-second prints, so at 60 s "
               "NONE of them is recorded, at 45 s a quarter is, at 30 s a "
               "half. A third early is a foot in the door at the moment the "
               "price is best and our model is weakest; the top-up commits "
               "the rest when three times as much of the answer is on disk. "
               "The 45 s version of exactly this shipped and is live.",
        "good": "It gets a materially better average price than the control "
                "with no more losses in the first 40 early closes.",
        "bad": "Losses the control does not have, or top-ups that never come "
               "because the price has run away by 30 s -- then the early "
               "third is just a smaller bet at a worse moment.",
        "watch": "How often the top-up actually fills (a `topup` leg in the "
                 "signal records), and the price of the early third against "
                 "the control's single fill on the same market.",
    },
    {
        "name": "When an early bet flips, buy DOUBLE the other side (A54)",
        "status": RUNNING, "match": "arm-e60-flip2", "since": "2026-09-18",
        "select": {"flip_mult": lambda v: v is not None and float(v) > 1.0,
                   "early_tau_max": 60, "early_frac": 0.333},
        "what": "Identical to the 'third at 46-60 s' arm in every setting "
                "except one: when a bet opened out at 46-60 s turns against "
                "us INSIDE 30 seconds, it buys twice the position on the "
                "other side instead of an equal hedge, so the position ends "
                "up net long the side the later look prefers.",
        "why": "Operator: 'Make sure the paper arms from 30-60 seconds buy "
               "more of the other side if at 30 seconds or less it flips.' "
               "The reasoning is the settlement window: a bet placed at 60 s "
               "is made with NONE of the sixty prints recorded, and by 30 s "
               "HALF are. The later look is strictly better informed, so its "
               "disagreement is information rather than noise.",
        "good": "It beats its control (arm-e60-third) on money AND on the "
                "worst single close. That means the 30-second read really "
                "does overturn the 60-second one often enough to bet on.",
        "bad": "It loses more than its control. Doubling is NOT a hedge -- "
               "1 YES at 97c against 2 NO at 60c loses 17c if NO lands and "
               "117c if YES lands, where an equal hedge loses 57c either "
               "way. It needs the flip to be right about 7 times in 10 just "
               "to break even against hedging.",
        "watch": "Every flip: the entry price and second, the flip price and "
                 "second, and which side actually settled. The pair's net "
                 "against what an equal hedge would have locked.",
    },
    {
        "name": "The whole bet at 46-60 s (control for the increments)",
        "status": RUNNING, "match": "arm-e60-full", "since": "2026-09-18",
        "select": {"early_tau_max": 60, "early_frac": 1.0,
                   "early_min_price": 0.9, "early_max_edge": 3.0},
        "what": "Same 46-60 s window, but the whole bet goes in at once.",
        "why": "Separates 'earlier is better' from 'staging is better'. If "
               "this matches the thirds arm, staging earns nothing and the "
               "simpler rule wins; if it loses more, the staging is what "
               "makes 60 s survivable.",
        "good": "It matches the thirds arm on money with fewer moving parts.",
        "bad": "It carries the losses the thirds arm avoids. At 60 s nothing "
               "of the settlement average is locked, so this is the most "
               "exposed bet any arm makes.",
        "watch": "Losing closes, and the worst single close, against the "
                 "thirds arm on the same markets.",
    },
    {
        "name": "60 s increments into the bands that earn (no edge cap, 80c floor)",
        "status": RUNNING, "match": "arm-e60-open", "since": "2026-09-18",
        "select": {"early_tau_max": 60, "early_frac": 0.333,
                   "early_min_price": 0.8, "early_max_edge": UNSET},
        "what": "A third at 46-60 s, with the 90c floor lowered to 80c and "
                "A50's 3c edge cap off.",
        "why": "The 80-94c band returns 8-14% and the early leg is forbidden "
               "from all of it. This asks whether that ban is right at 60 s, "
               "where it is least likely to be -- the further out, the more "
               "a cheap ask is the market's honest opinion rather than a "
               "mistake, so this is the arm most likely to fail.",
        "good": "Early fills under 94c that settle like the late ones.",
        "bad": "Two or more losses in the first 20 early sub-94c closes. "
               "Paper understates our own loss rate, so a bad paper result "
               "here is final and the band stays shut out that far.",
        "watch": "Early fills under 94c: count, price, settled result.",
    },
    {
        "name": "Crypto.com prediction markets (FIX API)",
        "status": IDEA, "since": "2026-09-17", "match": None,
        "what": "A second venue. They run 5- and 15-minute crypto markets on more "
                "coins than Kalshi.",
        "why": "THE most valuable thread open. The cheap-offer pool on Kalshi "
               "halved on 09-13 and our share never moved -- when the pool itself "
               "dries up, the answer is another product, not a better bot.",
        "good": "A whole second supply of the same trade.",
        "bad": "Predictions are FIX-only there (REST and WebSocket say 'coming "
               "soon'), and FIX is a heavyweight session protocol our stack does "
               "not speak. And we do not yet know their settlement rule, which "
               "decides whether ANY of our modelling transfers.",
        "where": "Support gave an address: fixapi@crypto.com. A draft asking the "
                 "six questions that decide it is at results/cryptocom_fixapi_email.md. "
                 "Question 1 is whether short-duration crypto contracts exist at "
                 "all; question 2 is whether settlement is an average or a single "
                 "print.",
    },
    {
        "name": "Polymarket",
        "status": IDEA, "since": "2026-09-17", "match": None,
        "what": "Another prediction venue.",
        "why": "Same reason: more supply.",
        "bad": "Their crypto predictions are not offered to US users, so the main "
               "exchange is out of reach.",
        "where": "Parked unless the access question changes.",
    },
    {
        "name": "Buy the NEW side when a favourite crosses below 50c",
        "status": IDEA, "since": "2026-09-17", "match": None,
        "what": "Not a hedge -- a fresh bet on the side that is taking over.",
        "why": "When the favourite falls under 50c inside the last 30 seconds it "
               "goes on to lose 76% of the time across 158 markets. Buying the "
               "other side at ~50c is worth about +11c a contract on paper, the "
               "biggest per-contract number found.",
        "bad": "Also the most suspect. The person selling you the new side at 50c "
               "may be the one who knows why it moved -- exactly the population "
               "trap that makes tape numbers lie.",
        "where": "Not built. Needs its own arm, not a flag on the existing bot.",
    },
    {
        "name": "Size taper on thin cushions",
        "status": IDEA, "since": "2026-09-18", "match": None,
        "what": "Take the trades that sit close to the line, but SMALLER.",
        "why": "Refusing them loses money (see the killed gate above), but they do "
               "earn less: about 60c a market against $1.04 for the rest.",
        "good": "Keeps the profit, cuts the size of the worst days.",
        "bad": "Any size rule is another thing that can be wrong in the direction "
               "of trading less.",
        "where": "Proposed, not built.",
    },
    {
        "name": "Gemini prediction markets",
        "status": KILLED, "since": "2026-09-16", "match": None,
        "what": "A venue we built support for.",
        "why": "More supply.",
        "outcome": "Almost zero volume. Built and shelved.",
        "attribution": "No money either way.",
    },
]

# THE FIVE CONFIDENCE ARMS, one entry each rather than one entry for the set.
# They are the comparison the operator asked for -- "start a paper arm at .99,
# .985, .98, .975, .97" -- and a single lumped row could only ever show one of
# their logs, which is exactly the bug that made every arm report the same five
# markets. Generated in a loop because only the number differs.
for _pin, _pct in ((0.99, "99.0%"), (0.985, "98.5%"), (0.98, "98.0%"),
                   (0.975, "97.5%"), (0.97, "97.0%")):
    EXPERIMENTS.insert(0, {
        "name": "Lower confidence to %s" % _pct,
        "status": KILLED, "match": "--pin %s" % _pin, "since": "2026-09-18",
        "select": {"pin": _pin},
        "outcome": "STOPPED 2026-09-18 ~16:30Z after 12-13 settled markets each, "
                   "to free memory for a settlement refresh. Every one of the "
                   "five was BEHIND the live bot on the what-if, scaled to our "
                   "contracts: 97.0%% -25%%, 97.5%% -36%%, 98.0%% -20%%, "
                   "98.5%% -32%%, 99.0%% -31%%, with 54-68%% less swing. Small "
                   "samples, but all five pointed the same way.",
        "attribution": "None shipped. The bar stays at 99.5%%: lowering it took "
                       "more trades and made less money per contract, which is "
                       "the supply story (offers are scarce), not the gate "
                       "story (the gate is too strict).",
        "what": "A paper bot identical to the live one except it buys once it is "
                "%s sure instead of 99.5%% sure." % _pct,
        "why": "Our cheap fills (under 95c) fell from 28 a day to 7. The question "
               "is whether those trades are still there but now sit just under our "
               "confidence bar, or whether they are genuinely gone.",
        "good": "It makes MORE money per day than the live bot without its loss "
                "rate rising past break-even. Then the bar is too strict.",
        "bad": "It takes more trades and loses more than the extra trades pay for. "
               "Then 99.5% is right and the missing fills are a supply problem, "
               "not a gate problem -- which is what the pickoff tracker suggests.",
        "watch": "Dollars per day, not win rate. At 96c a 3% loss rate is "
                 "break-even, so an arm can win 97 times in 100 and make nothing.",
    })
del _pin, _pct


def _paper_logs():
    """Every arm's log, not just the crypto ones.

    This globbed `pinrun-paper-*` alone, so the commodity arms and the Coin
    Race arm -- which write their own prefixes -- showed the operator a blank
    where three running experiments should be. An arm that is invisible in the
    Lab is an arm nobody checks.
    """
    out = []
    for pat in ("pinrun-paper-*.jsonl", "cmdarm-*.jsonl", "cmdlive-*.jsonl",
                "pinracearm-*.jsonl"):
        out += glob.glob(os.path.join(RESULTS, pat))
    return sorted(out)


def _sel_ok(got, want):
    """One `select` clause against one start-record field.

    `want` is a value, SET/UNSET, or a callable -- a callable is the right
    answer whenever the arm's setting has a non-null DEFAULT (late_mult ships
    at 1.0, so SET would match every log ever written and put another arm's
    money under this one's name).
    """
    if callable(want):
        try:
            return bool(want(got))
        except Exception:                                          # noqa: BLE001
            return False
    if want is SET or want == SET:
        return got is not None
    if want is UNSET or want == UNSET:
        return got is None
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return abs(float(got) - float(want)) < 1e-9
    return got == want


def _first_record(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    return json.loads(line)
                except ValueError:
                    return None
    except OSError:
        return None
    return None


# A paper arm writes a record every close (15 minutes) and usually far more
# often. Twenty-five minutes is comfortably past one close and well short of
# two, so a live arm is never called dead and a dead one is not called live
# for long.
FRESH_S = 25 * 60

_NOPOS = object()


def _settled_pnl(r):
    """Dollars from one settled record, or _NOPOS if we held nothing.

    THREE ARMS, THREE SPELLINGS. `pinrun` writes `pnl_c` in CENTS; the Coin
    Race arm writes `pnl` in DOLLARS and emits a settled record for EVERY race
    whether or not it traded. Reading only `pnl_c` scored the race arm at
    exactly $0.00 across 214 "settled" markets, of which it had actually
    traded 34 -- a flat zero that reads as a real, harmless result.
    """
    if r.get("pnl_c") is not None:
        return float(r["pnl_c"]) / 100.0
    if r.get("pnl") is not None:
        # a race record with no position is not a market we were in
        if r.get("positions") is not None and not r.get("positions"):
            return _NOPOS
        return float(r["pnl"])
    return _NOPOS


def _log_span(path):
    """(first_epoch, last_epoch) of a log's timestamped records; None when
    the log is readable but carries no timestamps; False when it cannot be
    read at all. The two are different answers and join_logs treats them
    differently -- one is kept, the other dropped."""
    import calendar
    import time as _t
    lo = hi = None
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return False
    with fh:
        for line in fh:
            i = line.find('"t": "')
            if i < 0:
                continue
            t = line[i + 6:i + 25]
            try:
                ts = calendar.timegm(_t.strptime(t, "%Y-%m-%dT%H:%M:%S"))
            except (TypeError, ValueError):
                continue
            lo = ts if lo is None else min(lo, ts)
            hi = ts if hi is None else max(hi, ts)
    return None if lo is None else (lo, hi)


def join_logs(paths):
    """The logs that together ARE one arm, oldest first, overlaps refused.

    THE OPERATOR, 2026-09-18: "i see some charts cut off because we stopped".
    An arm that is stopped and started again writes a NEW log, and the Lab
    showed only the newest one -- so a restart did not cut the chart, it
    threw the earlier hours away. This returns every matching log in time
    order so the chart is the arm's whole life with a gap where it was down.

    TWO LOGS THAT OVERLAP IN TIME ARE NOT ONE ARM. They are two processes on
    the same settings at once (a stale duplicate, or a relaunch that failed
    to kill the old one), and summing them double-counts every market. When
    a later log starts before an earlier one ends, the earlier one is dropped
    and the caller is told, rather than the money being quietly doubled.

    Returns (kept_paths, dropped_paths).
    """
    spans, unplaced = [], []
    for p in paths:
        sp = _log_span(p)
        if sp is False:
            continue                      # unreadable: not a log at all
        if sp is None:
            # NO TIMESTAMPS (a log that never got past its start record, or a
            # hand-made one): it cannot be ordered or overlap-checked, so it
            # is KEPT, last, by name -- dropping it would make an arm with one
            # such log vanish from the Lab, which is what the first version
            # of this did to every confidence arm in the self-test
            unplaced.append(p)
            continue
        spans.append((sp[0], sp[1], p))
    spans.sort()
    kept, dropped = [], []
    for lo, hi, p in spans:
        if kept and lo <= kept[-1][1]:
            # overlap: the log that ENDS LATER is the arm -- it is the one
            # still running, or the one that ran longest. A relaunch that
            # died in a minute must not displace the arm it duplicated. The
            # loser is dropped whole rather than sliced, because a sliced log
            # would hide that two processes ran at once.
            if hi > kept[-1][1]:
                dropped.append(kept[-1][2])
                kept[-1] = (lo, hi, p)
            else:
                dropped.append(p)
            continue
        kept.append((lo, hi, p))
    return [p for _, _, p in kept] + sorted(unplaced), dropped


def summarise_log(path):
    """{settled, won, lost, net} for one paper log, or a LIST of logs joined
    in time order (join_logs). Cheap: reads settled lines."""
    if isinstance(path, (list, tuple)):
        parts = [summarise_log(p) for p in path]
        parts = [x for x in parts if x]
        if not parts:
            return None
        return {"settled": sum(x["settled"] for x in parts),
                "won": sum(x["won"] for x in parts),
                "lost": sum(x["lost"] for x in parts),
                "net": sum(x["net"] for x in parts),
                "logs": len(parts)}
    n = won = lost = 0
    net = 0.0
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            if '"settled"' not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("kind") != "settled":
                continue
            v = _settled_pnl(r)
            if v is _NOPOS:
                continue
            n += 1
            net += v
            if v < 0:
                lost += 1
            else:
                won += 1
    return {"settled": n, "won": won, "lost": lost, "net": net}


def arm_series(path):
    """[(epoch, pnl)] and total contracts for one paper arm, oldest first.
    `path` may be a list of logs (join_logs), read in order and merged."""
    import calendar
    import time as _t
    if isinstance(path, (list, tuple)):
        pts, contracts = [], 0.0
        for p in path:
            a, b = arm_series(p)
            pts.extend(a)
            contracts += b
        pts.sort()
        return pts, contracts
    pts, contracts = [], 0.0
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return [], 0.0
    with fh:
        for line in fh:
            if ('"settled"' not in line and '"order"' not in line
                    and '"signal"' not in line):
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            if k == "order":
                contracts += float(r.get("filled") or 0)
            elif k == "signal" and not r.get("live"):
                # A PAPER ARM WRITES NO ORDER RECORDS -- there is no wire call
                # to record. Its contracts live on the signal as `take_n`, and
                # counting only `order` rows gave every arm zero contracts, so
                # the scaling divided by zero and every what-if came back
                # empty. Live rows are excluded here because the live path DOES
                # write orders and would double-count.
                contracts += float(r.get("take_n") or 0)
            elif k == "settled":
                v = _settled_pnl(r)
                if v is _NOPOS:
                    continue
                t = r.get("t") or ""
                try:
                    ts = calendar.timegm(_t.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
                except (TypeError, ValueError):
                    continue
                pts.append((ts, v))
    pts.sort()
    return pts, contracts


def whatif(arm_pts, arm_contracts, live_pts, live_contracts):
    """Two cumulative curves over the SAME window, plus an honest headline.

    THE SIZE PROBLEM, and why this is not a raw comparison. A paper arm trades
    a fixed 20 contracts; the live bot sizes itself from the bank and has been
    at 95-99. Laying those two P&L curves side by side would say nothing about
    the STRATEGY and everything about the stake. So the arm is scaled to the
    live bot's actual contract volume: what it earned PER CONTRACT, applied to
    the contracts we really traded.

    Returns {'live': [(t, cum)], 'arm': [(t, cum)], 'live_net', 'arm_net',
    'diff', 'from'} or None when there is not enough to compare.
    """
    if not arm_pts or not live_pts or arm_contracts <= 0 or live_contracts <= 0:
        return None
    t0 = arm_pts[0][0]
    live = [(t, v) for t, v in live_pts if t >= t0]
    if not live:
        return None
    scale = live_contracts / arm_contracts
    cum, lcurve = 0.0, []
    for t, v in live:
        cum += v
        lcurve.append((t, cum))
    cum, acurve = 0.0, []
    for t, v in arm_pts:
        cum += v * scale
        acurve.append((t, cum))
    # VOLATILITY, so "better" is not judged on the total alone. A strategy that
    # earns the same with half the swing is a better strategy, and one that
    # earns slightly more by risking far more is usually not. Measured as the
    # standard deviation of per-market P&L, scaled the same way.
    def _sd(vals):
        if len(vals) < 2:
            return 0.0
        mu = sum(vals) / len(vals)
        return (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5

    live_vals = [v for _, v in live]
    arm_vals = [v * scale for _, v in arm_pts]
    lsd, asd = _sd(live_vals), _sd(arm_vals)
    lworst = min(live_vals) if live_vals else 0.0
    aworst = min(arm_vals) if arm_vals else 0.0
    return {"live": lcurve, "arm": acurve,
            "live_net": lcurve[-1][1], "arm_net": acurve[-1][1],
            "diff": acurve[-1][1] - lcurve[-1][1], "from": t0,
            "scale": scale,
            "pct": (100.0 * (acurve[-1][1] - lcurve[-1][1]) / abs(lcurve[-1][1]))
                   if abs(lcurve[-1][1]) > 1e-9 else None,
            "live_sd": lsd, "arm_sd": asd,
            "sd_pct": (100.0 * (asd - lsd) / lsd) if lsd > 1e-9 else None,
            "live_worst": lworst, "arm_worst": aworst,
            "n_live": len(live_vals), "n_arm": len(arm_vals)}


def live_progress(cmdlines=None, logs=None):
    """{match: {'running': bool, 'settled', 'won', 'lost', 'net'}}.

    `cmdlines` is the list of command lines currently running; pass it in so
    this is testable without touching the process table.
    """
    out = {}
    cmdlines = cmdlines or []
    for e in EXPERIMENTS:
        m = e.get("match")
        if not m:
            continue
        running = any(m in (c or "") for c in cmdlines)
        best = None
        # A LOG THAT IS STILL BEING WRITTEN IS A RUNNING ARM, and that test is
        # applied below once the arm's log is known. TWO reasons it is needed.
        #
        # 1. An arm whose `match` is a NAME ("arm-b-control") has that name
        #    nowhere in its command line -- it is only the redirect filename,
        #    which Win32_Process does not report. Every one of the eleven
        #    named arms therefore read "NOT RUNNING" in the app while alive.
        # 2. Windows returns CommandLine EMPTY for a process a caller cannot
        #    open. That has already broken restart_bot.ps1 once, badly enough
        #    to start a second live bot, and the fix there was the same:
        #    believe the file, not the process list.
        # HOW AN ARM IS MATCHED TO ITS LOG, and why the first version was
        # silently wrong. It looked for the flag NAME anywhere in the start
        # record -- but the start record is the WHOLE configuration, so every
        # log carries `pin` and `early_tau_max` whether or not the arm changed
        # them. Every experiment therefore matched every log and took the
        # newest, so five confidence arms and the 45-second arm all reported
        # the same five markets, and the what-if compared an arm against
        # itself. An entry now names the field VALUES that distinguish it
        # (`select`), and an entry with no `select` gets no log at all --
        # blank is honest, a stranger's numbers under your name is not.
        sel = e.get("select")
        pool = logs if logs is not None else _paper_logs()
        matched = []
        # AN ARM'S LOGS START NO EARLIER THAN THE ARM. A `select` names the
        # settings, and settings recur: `pin 0.99` was a paper run on 09-13
        # under different code, and joining that on to an arm declared on
        # 09-18 stitched two experiments into one chart. The filename carries
        # the start stamp, so a log from before `since` is not this arm's.
        since = str(e.get("since") or "").replace("-", "")[:8]
        if sel:
            for p in pool:
                stamp = re.search(r"(\d{8})T\d{6}Z", os.path.basename(p))
                if since and stamp and stamp.group(1) < since:
                    continue
                r = _first_record(p)
                if r is None or r.get("kind") != "start":
                    continue
                if all(_sel_ok(r.get(k), want) for k, want in sel.items()):
                    matched.append(p)
        dropped = []
        if len(matched) == 1:
            best = matched[0]
        elif matched:
            kept, dropped = join_logs(matched)
            # ONE log stays a plain path so every caller that reads `log`
            # as a filename keeps working; two or more become the joined list
            best = kept[-1] if len(kept) == 1 else kept
        if best is None and e.get("legacy_logs"):
            # RUNS THAT PREDATE THE START-RECORD FIX. A47 and A48 were launched
            # on 2026-09-17, before `hedge_price` and `late_mult` were written
            # into the start record, so their logs cannot say what they are
            # testing and no `select` can find them. These names were matched
            # by hand, from process creation time against log filename, and are
            # here so three days of arm history stays visible instead of being
            # thrown away by a restart. Runs started after the fix identify
            # themselves and never reach this branch.
            known = {os.path.basename(p): p for p in pool}
            for nm in e["legacy_logs"]:
                if nm in known:
                    best = known[nm]
        if not running and best:
            # ...the freshness test. A paper arm writes at least a `watch`
            # record every close, so a log untouched for FRESH_S is a dead
            # arm however its command line reads.
            newest = best[-1] if isinstance(best, (list, tuple)) else best
            try:
                running = (time.time() - os.path.getmtime(newest)) < FRESH_S
            except OSError:
                pass
        info = {"running": running}
        if best:
            s = summarise_log(best)
            if s:
                info.update(s)
                if isinstance(best, (list, tuple)):
                    info["log"] = os.path.basename(best[-1])
                    info["logs"] = [os.path.basename(p) for p in best]
                else:
                    info["log"] = os.path.basename(best)
            if dropped:
                # said out loud, never summed: two processes ran at once
                info["overlap_dropped"] = [os.path.basename(p) for p in dropped]
        out[m] = info
    return out


def counts():
    c = collections.Counter(e["status"] for e in EXPERIMENTS)
    return c


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinlab selftest: FAILED -- " + msg)

    ck(EXPERIMENTS, "the catalogue is not empty")
    for e in EXPERIMENTS:
        ck(e.get("name") and e.get("status") and e.get("what") and e.get("why"),
           "every entry has a name, a status, what it does and why: %r" % e.get("name"))
        ck(e["status"] in (RUNNING, SHIPPED, KILLED, PAUSED, IDEA),
           "%r has a known status" % e["name"])
        if e["status"] in (RUNNING, IDEA):
            ck(e.get("good") or e.get("bad") or e.get("where"),
               "a RUNNING or IDEA entry says what good and bad look like: %r" % e["name"])
        if e["status"] in (SHIPPED, KILLED):
            ck(e.get("outcome"),
               "a SHIPPED or KILLED entry says what actually happened: %r" % e["name"])
    c = counts()
    ck(c[KILLED] >= 3,
       "the board keeps its DEAD ideas -- %d of them. A drawing board that "
       "only records the wins teaches nothing, and half of what was learned "
       "this week came from things that did not work" % c[KILLED])
    ck(c[RUNNING] >= 1 and c[IDEA] >= 1, "and it has live work and future work")

    import tempfile
    td = tempfile.mkdtemp()
    p = os.path.join(td, "pinrun-paper-x.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "pin": 0.97, "hedge_price": None}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl_c": 250.0}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl_c": -900.0}) + "\n")
    ap2, ac2 = arm_series(p)
    ck(ac2 == 0.0, "no signals in this fixture yet, so no contracts")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "signal", "live": False, "take_n": 20.0}) + "\n")
        fh.write(json.dumps({"kind": "signal", "live": True, "take_n": 99.0}) + "\n")
    ap3, ac3 = arm_series(p)
    ck(ac3 == 20.0,
       "a PAPER arm's contracts come from its signals (it writes no order "
       "records at all), and a live row is not counted -- reading only orders "
       "gave every arm zero contracts and silently emptied every what-if")
    s = summarise_log(p)
    ck(s["settled"] == 2 and s["won"] == 1 and s["lost"] == 1
       and abs(s["net"] + 6.50) < 1e-9,
       "a paper log summarises to settled, won, lost and NET DOLLARS -- the net "
       "is what matters, and here one loss swamps one win (-$6.50 on 1-1)")
    # THE COIN RACE ARM SPELLS ITS MONEY DIFFERENTLY, and gets a settled
    # record for every race whether it traded or not.
    rp = os.path.join(td, "pinracearm-x.jsonl")
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "table": "race_gaptable.json"}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl": 0, "positions": 0}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl": 3.25, "positions": 2}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl": -1.25, "positions": 1}) + "\n")
    rs = summarise_log(rp)
    ck(rs["settled"] == 2 and abs(rs["net"] - 2.00) < 1e-9,
       "a race log counts only races it HELD, and reads `pnl` as DOLLARS -- "
       "reading `pnl_c` scored 214 races at a flat $0.00, which looks like a "
       "harmless result rather than a unit bug")
    ck(rs["won"] == 1 and rs["lost"] == 1, "...and splits them into won and lost")
    ck(summarise_log(os.path.join(td, "nope.jsonl")) is None,
       "NULL: a missing log summarises to nothing rather than zeros that read "
       "as a real result")
    # TWO ARMS THAT DIFFER ONLY IN CONFIDENCE MUST NOT SHARE A LOG. The first
    # matcher looked for the flag NAME in the start record, but the start
    # record holds the whole configuration, so every arm matched every log and
    # took the newest -- five arms all reported the same five markets and the
    # what-if compared an arm against itself.
    q97 = os.path.join(td, "pinrun-paper-a97.jsonl")
    q98 = os.path.join(td, "pinrun-paper-a98.jsonl")
    for path, pinv, pnl in ((q97, 0.97, 300.0), (q98, 0.98, -400.0)):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "start", "pin": pinv,
                                 "early_tau_max": 30, "hedge_price": None}) + "\n")
            fh.write(json.dumps({"kind": "settled", "pnl_c": pnl}) + "\n")
    lp2 = live_progress(cmdlines=[], logs=[q97, q98])
    ck(lp2["--pin 0.97"].get("log") == "pinrun-paper-a97.jsonl"
       and lp2["--pin 0.98"].get("log") == "pinrun-paper-a98.jsonl",
       "each confidence arm finds ITS OWN log, by the value of `pin` and not by "
       "the flag's name appearing somewhere in the configuration")
    ck(abs(lp2["--pin 0.97"]["net"] - 3.0) < 1e-9
       and abs(lp2["--pin 0.98"]["net"] + 4.0) < 1e-9,
       "...so their money is reported separately (+$3.00 against -$4.00), which "
       "is the whole point of running five of them")
    # A SETTING WITH A NON-NULL DEFAULT NEEDS A CALLABLE, NOT `SET`.
    ck(_sel_ok(1.0, SET) is True and _sel_ok(1.0, lambda v: v > 1.0) is False,
       "`SET` is true of a setting sitting at its shipped default (late_mult "
       "1.0), so an arm testing a RAISED value must select on the value -- "
       "otherwise it matches every log there has ever been")
    ck(_sel_ok(None, lambda v: v > 1.0) is False,
       "...and a callable that would raise on a missing field refuses rather "
       "than matching")
    # AN ARM LAYERED ON ANOTHER MUST NOT STEAL ITS LOG. A51 sets
    # --early-max-edge as well as --hedge-normal, so selecting on the shared
    # flag alone matched both and the older arm displayed the newer's markets.
    base = os.path.join(td, "pinrun-paper-b1.jsonl")
    layer = os.path.join(td, "pinrun-paper-b2.jsonl")
    for path, extra, pnl in ((base, {}, 500.0),
                             (layer, {"hedge_normal": True}, -700.0)):
        with open(path, "w", encoding="utf-8") as fh:
            rec = {"kind": "start", "pin": 0.995, "early_max_edge": 3.0}
            rec.update(extra)
            fh.write(json.dumps(rec) + "\n")
            fh.write(json.dumps({"kind": "settled", "pnl_c": pnl}) + "\n")
    layer2 = os.path.join(td, "pinrun-paper-b3.jsonl")
    with open(layer2, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "pin": 0.995, "early_max_edge": 3.0,
                             "hedge_jump": 8.0}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl_c": 900.0}) + "\n")
    lp3 = live_progress(cmdlines=[], logs=[base, layer, layer2])
    ck(lp3["--hedge-jump"].get("log") == "pinrun-paper-b3.jsonl",
       "a THIRD arm layered on the same flag finds its own log")
    ck(lp3["--early-max-edge"].get("log") == "pinrun-paper-b1.jsonl",
       "...and the base arm still does not claim it -- the trap has now been "
       "sprung twice, so every layered arm must be excluded by name")
    ck(lp3["--early-max-edge"].get("log") == "pinrun-paper-b1.jsonl",
       "the base arm keeps its OWN log when a later arm inherits its flag -- "
       "selecting on the shared flag alone showed the older arm the newer "
       "arm's markets, which is exactly the bug `select` was added to kill")
    ck(lp3["--hedge-normal"].get("log") == "pinrun-paper-b2.jsonl",
       "...and the layered arm finds its own")
    ck(abs(lp3["--early-max-edge"]["net"] - 5.0) < 1e-9
       and abs(lp3["--hedge-normal"]["net"] + 7.0) < 1e-9,
       "...so a winning arm and a losing one are never shown the same money")
    ck(lp2["--hedge-price"].get("log") is None,
       "NULL: an arm whose distinguishing flag is not set in ANY log gets no "
       "log at all -- blank is honest; another arm's numbers under its name is "
       "the bug this replaced")
    lp = live_progress(cmdlines=["python pinrun.py --pin 0.97 --size 20"], logs=[p])
    ck(lp["--pin 0.97"]["running"] is True, "a matching command line marks it running")
    ck(lp["--hedge-price"]["running"] is False, "and a missing one does not")
    # A LOG STILL BEING WRITTEN IS A RUNNING ARM, whatever the process list says.
    ck(live_progress(cmdlines=[], logs=[p])["--pin 0.97"]["running"] is True,
       "an arm whose log was just written is RUNNING even with an EMPTY "
       "process list -- eleven arms are matched by a NAME that appears "
       "nowhere in their command line, and Windows also hides CommandLine "
       "from a caller that cannot open the process")
    _old = os.path.join(td, "pinrun-paper-stale.jsonl")
    with open(_old, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "pin": 0.97}) + chr(10))
        fh.write(json.dumps({"kind": "settled", "pnl_c": 100.0}) + chr(10))
    os.utime(_old, (time.time() - FRESH_S - 60, time.time() - FRESH_S - 60))
    ck(live_progress(cmdlines=[], logs=[_old])["--pin 0.97"]["running"] is False,
       "...and a log untouched for longer than one close is a DEAD arm, so "
       "the freshness rule cannot report a stopped arm as running")
    ck(live_progress(cmdlines=[], logs=[])["cmdarm.py"]["running"] is False,
       "NULL: nothing running, nothing claimed")

    # AN ARM IS EVERY LOG THAT MATCHES IT, IN ORDER -- A RESTART IS A GAP,
    # NOT A RESET. And two logs that overlap are two processes, never summed.
    ja = os.path.join(td, "pinrun-paper-j1.jsonl")
    jb = os.path.join(td, "pinrun-paper-j2.jsonl")
    jc = os.path.join(td, "pinrun-paper-j3.jsonl")
    for path, t0, t1, pnl in ((ja, "2026-09-18T10:00:00Z", "2026-09-18T11:00:00Z", 100.0),
                              (jb, "2026-09-18T12:00:00Z", "2026-09-18T13:00:00Z", -50.0),
                              (jc, "2026-09-18T12:30:00Z", "2026-09-18T14:00:00Z", 700.0)):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "start", "pin": 0.975, "t": t0}) + "\n")
            fh.write(json.dumps({"kind": "signal", "take_n": 20.0, "t": t0}) + "\n")
            fh.write(json.dumps({"kind": "settled", "pnl_c": pnl, "t": t1}) + "\n")
    kept, dropped = join_logs([jb, ja])
    ck(kept == [ja, jb] and dropped == [],
       "two logs that do not overlap are ONE arm, oldest first, whichever "
       "order they were handed over in")
    sm = summarise_log(kept)
    ck(sm["settled"] == 2 and abs(sm["net"] - 0.5) < 1e-9 and sm["logs"] == 2,
       "...and their money is summed ($1.00 then -$0.50), so a restarted arm "
       "keeps its history with a gap instead of starting from zero")
    pts, ctr = arm_series(kept)
    ck([v for _, v in pts] == [1.0, -0.5] and abs(ctr - 40.0) < 1e-9,
       "...the series runs oldest first across the join, and contracts add")
    kept2, dropped2 = join_logs([ja, jb, jc])
    ck(kept2 == [ja, jc] and dropped2 == [jb],
       "a log that starts BEFORE the previous one ended is a second process "
       "on the same settings: the one that ends first is dropped whole and "
       "named, and the $7.00 is never added to the $-0.50 it overlapped")
    jd = os.path.join(td, "pinrun-paper-j4.jsonl")
    with open(jd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "pin": 0.975, "t": "2026-09-18T12:40:00Z"}) + chr(10))
        fh.write(json.dumps({"kind": "end", "t": "2026-09-18T12:41:00Z"}) + chr(10))
    kept3, dropped3 = join_logs([jb, jd])
    ck(kept3 == [jb] and dropped3 == [jd],
       "a relaunch that started inside a running arm and DIED a minute later "
       "does not displace it -- the arm is the log that ends later, not the "
       "one that started later; the first rule got this backwards and would "
       "have shown a dead 0-trade log in place of a live one")
    lpj = live_progress(cmdlines=[], logs=[ja, jb])
    ck(lpj["--pin 0.975"].get("logs") == ["pinrun-paper-j1.jsonl", "pinrun-paper-j2.jsonl"]
       and abs(lpj["--pin 0.975"]["net"] - 0.5) < 1e-9,
       "the Lab reports the joined arm and lists every log it stands on")
    lpo = live_progress(cmdlines=[], logs=[ja, jb, jc])
    ck(lpo["--pin 0.975"].get("overlap_dropped") == ["pinrun-paper-j2.jsonl"],
       "...and when logs overlap it says which one it refused to count")
    jold = os.path.join(td, "pinrun-paper-20260913T010000Z.jsonl")
    with open(jold, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "pin": 0.975, "t": "2026-09-13T01:00:00Z"}) + "\n")
        fh.write(json.dumps({"kind": "settled", "pnl_c": 9999.0, "t": "2026-09-13T02:00:00Z"}) + "\n")
    lps = live_progress(cmdlines=[], logs=[jold, ja, jb])
    ck(abs(lps["--pin 0.975"]["net"] - 0.5) < 1e-9,
       "a log stamped BEFORE the arm's `since` date is not the arm's, however "
       "well its settings match -- the $99.99 from 09-13 stays out of an arm "
       "declared on 09-18")
    ck(join_logs([]) == ([], []) and join_logs([os.path.join(td, "nope.jsonl")]) == ([], []),
       "NULL: no logs, or an unreadable one, join to nothing")
    jn = os.path.join(td, "pinrun-paper-j0.jsonl")
    with open(jn, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "start", "pin": 0.975}) + "\n")
    ck(join_logs([jn, ja]) == ([ja, jn], []),
       "NULL: a log with no timestamps is KEPT, last, and never counted as an "
       "overlap -- dropping it made every confidence arm disappear")

    # WHAT IF THE ARM HAD BEEN LIVE
    ap_, ac = [(100, 1.0), (200, -3.0), (300, 2.0)], 60.0
    lp_, lc = [(50, 5.0), (150, 2.0), (250, -1.0)], 600.0
    w = whatif(ap_, ac, lp_, lc)
    ck(w is not None, "two arms with data produce a comparison")
    ck(w["live"][0][0] >= 100,
       "the live curve starts when the ARM started, not before -- comparing a "
       "full history against a two-day arm would flatter whichever ran longer")
    ck(abs(w["scale"] - 10.0) < 1e-9,
       "the arm is scaled to the live bot's contract volume (10x here): a paper "
       "arm trades 20 contracts while the live bot trades 95, so a raw "
       "comparison would measure the STAKE and not the strategy")
    ck(abs(w["arm_net"] - 0.0) < 1e-9 and abs(w["live_net"] - 1.0) < 1e-9,
       "arm nets (1-3+2)x10 = 0; live nets 2-1 = 1 over the same window")
    ck(abs(w["diff"] + 1.0) < 1e-9, "so the arm would have been $1 WORSE")
    ck(w["pct"] is not None and abs(w["pct"] + 100.0) < 1e-6,
       "and that is expressed as a PERCENTAGE of what we actually made, which "
       "is the number that survives a change of stake")
    ck(w["arm_sd"] > w["live_sd"],
       "volatility is reported too: this arm swings harder per market, and a "
       "strategy that earns the same with a bigger swing is not an improvement")
    ck(w["arm_worst"] <= w["live_worst"],
       "so is the worst single market, which is what actually hurts on a bad day")
    ck(whatif([(100, 1.0)], 10.0, [(100, 1.0)], 10.0)["sd_pct"] is None,
       "NULL: one market either side gives no volatility comparison rather than "
       "a made-up zero")
    ck(whatif([], 0, lp_, lc) is None and whatif(ap_, 0.0, lp_, lc) is None,
       "NULL: no arm data, or no contracts to scale by, produces NO comparison "
       "rather than a divide-by-zero or a fake zero")
    print("pinlab selftest: OK (%d entries: %s)"
          % (len(EXPERIMENTS), ", ".join("%s %d" % (k, v) for k, v in sorted(counts().items()))))


if __name__ == "__main__":
    selftest()
