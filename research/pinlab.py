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
        "status": RUNNING, "match": "--hedge-price", "since": "2026-09-17",
        "select": {"hedge_price": SET},
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
        "select": {"late_mult": lambda v: v is not None and float(v) > 1.0},
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
        "select": {"hedge_normal": True},
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
        "select": {"early_max_edge": SET, "hedge_normal": lambda v: not v},
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
        "select": {"early_tau_max": 45, "pin": 0.995, "early_max_edge": UNSET},
        "what": "Buys a THIRD of a bet between 31 and 45 seconds out, and only if "
                "the price is at least 90c. Also live at that size.",
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
        "status": RUNNING, "match": "cmdlive.py", "since": "2026-09-17",
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
        "status": RUNNING, "match": "--pin %s" % _pin, "since": "2026-09-18",
        "select": {"pin": _pin},
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


def summarise_log(path):
    """{settled, won, lost, net} for one paper log. Cheap: reads settled lines."""
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
    """[(epoch, pnl)] and total contracts for one paper arm, oldest first."""
    import calendar
    import time as _t
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
        if sel:
            for p in pool:
                r = _first_record(p)
                if r is None or r.get("kind") != "start":
                    continue
                if all(_sel_ok(r.get(k), want) for k, want in sel.items()):
                    best = p
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
        info = {"running": running}
        if best:
            s = summarise_log(best)
            if s:
                info.update(s)
                info["log"] = os.path.basename(best)
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
    lp3 = live_progress(cmdlines=[], logs=[base, layer])
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
    ck(live_progress(cmdlines=[], logs=[])["cmdarm.py"]["running"] is False,
       "NULL: nothing running, nothing claimed")

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
