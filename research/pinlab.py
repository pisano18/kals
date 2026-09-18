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

# match: a substring of the arm's command line, used to find its paper log and
#        to tell whether it is running right now.
EXPERIMENTS = [
    # ---------------------------------------------------------------- RUNNING
    {
        "name": "Lower confidence (5 arms: 0.99 / 0.985 / 0.98 / 0.975 / 0.97)",
        "status": RUNNING, "match": "--pin ", "since": "2026-09-18",
        "what": "Five paper bots identical to the live one except they need less "
                "certainty before buying. The live bot demands 99.5%.",
        "why": "Our cheap fills (under 95c) fell from 28 a day to 7. The question "
               "is whether those trades are still there but now sit just under our "
               "confidence bar, or whether they are genuinely gone.",
        "good": "A looser arm makes MORE money per day without its loss rate "
                "rising past break-even. Then the bar is too strict and we lower it.",
        "bad": "Looser arms take more trades and lose more than the extra trades "
               "pay for. Then 99.5% is right and the missing fills are a supply "
               "problem, not a gate problem -- which is what the pickoff tracker "
               "already suggests.",
        "watch": "Dollars per day, not win rate. At 96c a 3% loss rate is "
                 "break-even, so an arm can win 97 times in 100 and make nothing.",
    },
    {
        "name": "Hedge on the market price, not the model (A47)",
        "status": RUNNING, "match": "--hedge-price", "since": "2026-09-17",
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
        "name": "The 45-second early leg (A46 + A49)",
        "status": RUNNING, "match": "--early-tau", "since": "2026-09-17",
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
        "name": "Coin Race (KXCRYPTOLEAD15M), paper",
        "status": RUNNING, "match": "pinracearm.py", "since": "2026-09-15",
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


def _paper_logs():
    return sorted(glob.glob(os.path.join(RESULTS, "pinrun-paper-*.jsonl")))


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
            v = float(r.get("pnl_c") or 0) / 100.0
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
            if '"settled"' not in line and '"order"' not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            if k == "order":
                contracts += float(r.get("filled") or 0)
            elif k == "settled":
                t = r.get("t") or ""
                try:
                    ts = calendar.timegm(_t.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
                except (TypeError, ValueError):
                    continue
                pts.append((ts, float(r.get("pnl_c") or 0) / 100.0))
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
    return {"live": lcurve, "arm": acurve,
            "live_net": lcurve[-1][1], "arm_net": acurve[-1][1],
            "diff": acurve[-1][1] - lcurve[-1][1], "from": t0,
            "scale": scale}


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
        for p in (logs if logs is not None else _paper_logs()):
            r = _first_record(p)
            if r is None:
                continue
            blob = json.dumps(r)
            key = m.strip().lstrip("-").split()[0] if m.startswith("--") else None
            if key and key.replace("-", "_") in blob:
                best = p
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
    s = summarise_log(p)
    ck(s["settled"] == 2 and s["won"] == 1 and s["lost"] == 1
       and abs(s["net"] + 6.50) < 1e-9,
       "a paper log summarises to settled, won, lost and NET DOLLARS -- the net "
       "is what matters, and here one loss swamps one win (-$6.50 on 1-1)")
    ck(summarise_log(os.path.join(td, "nope.jsonl")) is None,
       "NULL: a missing log summarises to nothing rather than zeros that read "
       "as a real result")
    lp = live_progress(cmdlines=["python pinrun.py --pin 0.97 --size 20"], logs=[p])
    ck(lp["--pin "]["running"] is True, "a matching command line marks it running")
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
    ck(whatif([], 0, lp_, lc) is None and whatif(ap_, 0.0, lp_, lc) is None,
       "NULL: no arm data, or no contracts to scale by, produces NO comparison "
       "rather than a divide-by-zero or a fake zero")
    print("pinlab selftest: OK (%d entries: %s)"
          % (len(EXPERIMENTS), ", ".join("%s %d" % (k, v) for k, v in sorted(counts().items()))))


if __name__ == "__main__":
    selftest()
