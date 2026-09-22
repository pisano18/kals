#!/usr/bin/env python3
# VERSION: 2026-09-13-at1
"""pinattrib.py -- what did each individual gate in the bot actually DO?

THE OPERATOR, 2026-09-13: "Is it actually possible to implement that for every
single function and method of the bot? It would be so powerful to look at each
individual implementation and function and algorithm and decision of the bot
and see how it alone affected what happens. Things like how often it came into
play, how close to correct it ended up being, if it actually led to a decision
or over shadowed by something else, how much extra money it actually earned us
compared to without or how much it's lost us."

IT IS POSSIBLE FOR THE REFUSALS, WHICH IS MOST OF THE BOT. Nineteen decision
points now record, once per market per close, that they stopped a trade and
what was on the table at the time (AMENDMENT 25 in pinrun.py). Every one of
those has an outcome we can look up afterwards, because the market settles
whether we bought it or not.

THE FOUR COLUMNS, AND WHAT EACH IS WORTH.

  CAME INTO PLAY -- how many (close, market) pairs this gate stopped. Exact.

  BINDING, NOT OVERSHADOWED -- the loop stops at the FIRST gate that objects,
  so a recorded refusal is by construction the one that actually decided. That
  is a real answer to "did it lead to a decision", but it is answered in the
  ORDER THE GATES RUN. A gate late in the chain looks quiet partly because
  earlier gates got there first, and this file prints the order so that is
  visible rather than hidden.

  DELAYED vs BLOCKED -- the distinction that makes the rest mean anything. A
  gate that refuses a market at 30 seconds out, after which the bot buys that
  same market at 20 seconds, PREVENTED NOTHING; it moved the entry. Refusals
  are split into `delayed` (we bought that market in that close anyway) and
  `blocked` (we never did). Only `blocked` is scored.

  WOULD-BE MONEY -- for each blocked refusal, what the trade would have paid
  if it had been filled at the price that was showing, at the size the bot was
  running, net of the exchange's fee, using the market's real settlement.

WHAT THIS CANNOT TELL YOU, AND IT IS NOT A TECHNICALITY.

  **A price showing is not a fill.** We would have been racing for it. Live
  fill rate is ~70%, and CLAUDE.md rule 5 records the population gap between
  "an offer was sitting there" and "someone actively sold it to us" at 31x.
  So the money column is an UPPER BOUND on what a gate cost, and, for gates
  that refuse bad trades, an upper bound on what it saved. It is labelled
  `if filled` everywhere and must never be quoted as P&L.

  **The columns do not add up to the bot's P&L, and they never will.** Gates
  interact through one shared contract budget: refusing a trade frees budget
  that a later trade spends. Turning two gates off is not the sum of turning
  each off. Anyone wanting the true marginal value of a gate has to re-run the
  close with it disabled -- that is a what-if run, not arithmetic on this
  table.

  **A gate that never fires is not useless.** `price_ceiling` refusing nothing
  means nothing got that expensive, which is the ceiling working upstream of
  itself. Zero rows is reported as zero rows, never as "no effect".
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinrun                                                  # noqa: E402

# The order the trade loop actually asks them, which is the only way to read
# the "came into play" column honestly.
GATE_ORDER = [
    "close_budget", "max_per_close", "max_per_market", "both_sides",
    "market_attempts", "attempts_cap", "book_suspect", "book_stale",
    "index_stale", "no_sigma",
    "confidence", "no_offer", "depth_floor", "edge_floor", "against_thin",
    "jump_against", "dump_guard",
    "improve_by", "rebuy_band", "price_ceiling", "ev_floor",
    # R4 (2026-09-22): this one sits AFTER the signals counter, which is why
    # it was invisible for so long -- it is the only refusal that used to
    # happen with no record at all. It is NOT the same gate as
    # "close_budget" above: that one refuses on close_budget_for (base PLUS
    # one bet for a new coin or inside the last seconds), this one on the
    # BASE alone, so a row here means the third bet was granted and priced
    # and then dropped. Its `budget_left` reads > 0 while the base is spent.
    "close_budget_base",
    "early_once", "staged_none", "early_cheap", "early_dear", "early_wide",
    "price_band",
    # NOT hedge_wait_normal, and not any other insurance decision. They are
    # written with rec(), so their `kind` is their own name and NOT "refused"
    # -- load_log() collects only refusals, so a row for one could never hold
    # a number. Listing it here printed a permanent, authoritative-looking
    # zero for a test that is in fact PAPER-ONLY, and the operator caught it:
    # "I don't see an insurance test in the table."
    #
    # A name in this list that is not a real `_gate()` call is a promise the
    # table cannot keep. The self-test now checks that in BOTH directions; it
    # only ever checked that every real gate is listed, never that every
    # listed name is real.
]

WHAT = {
    "close_budget": "the close has already bought its contract budget",
    "close_budget_base": ("the close had spent its BASE budget (two bets), so "
                          "the third bet -- which the budget gate above had "
                          "already allowed, and which the bank brake and the "
                          "worst-close rail had already been sized for -- was "
                          "dropped. Until 2026-09-22 this happened with no "
                          "record at all: one run counted 102 signals against "
                          "5 orders and nothing said where the other 97 went"),
    "max_per_close": "the close has already had its allowed number of fills",
    "max_per_market": "we already own this market in this close",
    "both_sides": "we hold the other side of this market already",
    "market_attempts": "already tried this market enough times this close",
    "attempts_cap": "too many orders already sent on this close",
    "book_suspect": "the order book looked wrong",
    "book_stale": "the order book was too old to trust",
    "index_stale": "the price index was too old to trust",
    "no_sigma": "not enough index history to measure how jumpy it is",
    "confidence": "the model was not sure enough",
    "no_offer": "the model was sure but nobody was selling that side",
    "depth_floor": "too few contracts on offer to be worth taking",
    "edge_floor": "the profit on offer was too thin",
    "against_thin": ("thin profit AND the live price was already past the "
                     "strike against us"),
    "jump_against": ("the index just made a big one-second move against us "
                     "-- jumps keep going more often than the model thinks"),
    "dump_guard": "priced far below fair -- someone else knew something",
    "improve_by": "a second buy that was not cheaper than the first",
    "rebuy_band": "a same-coin re-buy outside the 0.5-1c band",
    "price_ceiling": "priced above the 98c ceiling",
    "early_once": "A46: this market already holds an early leg (31-45 s); only one per market",
    "staged_none": "A46: the staged leg came to nothing (market already at full size, or under the minimum)",
    "hedge_wait_normal": "A51: insurance held off because the OTHER side was not yet a bet we would make on its own -- our model was not PIN sure of it, or it cost more than the price ceiling. The old rule fired on the model alone and 11 of 12 insured closes still ended negative, five of them paying 10-18c while the market still liked our side",
    "price_band": "A53: the ask sat inside a skipped price band (--skip-band). Live record for 94-96c, 83 closes: +$25 on $2,970, a loss rate level with its break-even; the band held a position slot and earned nothing measurable",
    "early_wide": "A50: the 31-45 s early leg found our model MORE than the cap above the market price. Late, that disagreement is the whole edge (6c or more made 1.44 $/bet inside 30 s); early, three quarters of the settlement window has not happened yet and the same band lost 3.01 $/bet, so out there a big edge means our volatility guess is wrong rather than the market",
    "early_dear": "A78: the 31-45 s early leg wanted an ask ABOVE the 97.5c ceiling. That leg earns 1.14c a contract against 5.63c at 6-10 s, and above 97.5c it is risking 98c to make 1.8c fifteen seconds before the information the strategy rests on arrives -- the shape of the KXBTC15M-26SEP191600-00 fill that cost $107.95",
    "early_cheap": "A49: the 31-45 s early leg wanted an ask under the 90c floor. Out that far less of the settlement average is locked, so a cheap ask is the market disagreeing with us where the model is weakest",
    "ev_floor": "expected value negative at that price",
}


# --------------------------------------------------------------- loading
def load_log(paths):
    """(refusals, bought, settled, starts, refusals_per_file).

    `starts` and the per-file count exist so the report can say WHICH BOT it
    is describing. Pooling ninety-two restarts without checking their settings
    silently mixes several different bots into one table.
    """
    refusals, bought, settled = [], set(), {}
    starts, per_file, hedges = {}, {}, []
    for p in paths:
        nm = os.path.basename(p)
        n = 0
        with open(p, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    m = json.loads(ln)
                except ValueError:
                    continue
                k = m.get("kind")
                if k == "refused":
                    refusals.append(m)
                    n += 1
                elif k == "order":
                    # an order SENT on this market; the close is in the ticker
                    bought.add(m.get("ticker"))
                elif k == "settled":
                    settled.setdefault(m.get("ticker"), []).append(m)
                elif k == "start" and nm not in starts:
                    starts[nm] = m
                elif isinstance(k, str) and k.startswith("hedge"):
                    # kept SEPARATELY from refusals: insurance decisions carry
                    # their own kind, which is exactly why the gate table
                    # could never see them
                    hedges.append(m)
        per_file[nm] = n
    return refusals, bought, settled, starts, per_file, hedges


def load_outcomes(markets_json):
    """{ticker: "yes"/"no"} from EVERY settlement directory, newest winning.

    2026-09-18: this read ONE file, `C:\\kals\\fulltape\\markets.json`, last
    refreshed on 09-12. A refusal can only be scored if its market's
    settlement is on file, so EVERY gate's money column read
    "- (no price)" -- the one column that answers "does this gate prevent
    losses or only trim volume" was blank for all twenty-seven of them, and
    the report said nothing was wrong. The fresh settlements were sitting in
    `fulltape_recent` the whole time.

    This is the SECOND tool to fail this exact way; `pinpickoff` silently
    stopped at 09-12 for the same reason and four rebuilds were spent blaming
    the tape. `outcome_coverage()` below exists so the third one cannot.
    """
    out = {}
    paths = [markets_json]
    base = os.path.dirname(markets_json)
    paths += sorted(glob.glob(os.path.join(base + "_*", "markets.json")))
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for _ser, rows in (d or {}).items():
            for r in rows or []:
                res = _result_word(r.get("result"))
                if res and r.get("ticker"):
                    out[r["ticker"]] = res
    return out


def _result_word(res):
    """'yes'/'no' from a settlement's `result`, whichever way it is written.

    THE REFRESHED PULL WRITES A NUMBER, THE OLD ONE WROTE A WORD. `fulltape`
    holds `"result": "yes"`; `fulltape_recent` holds `"result": 1.0`. Testing
    `res in ("yes", "no")` silently dropped every single fresh settlement, so
    even after the directory glob was fixed the coverage was 0 of 6,442 and
    every gate's money column stayed blank.

    NOT a magnitude guess (hard rule 5): 1.0 and 0.0 are the only numbers this
    field takes, and anything else returns None rather than being rounded into
    an outcome.
    """
    if isinstance(res, str):
        r = res.strip().lower()
        return r if r in ("yes", "no") else None
    if isinstance(res, bool):
        return "yes" if res else "no"
    if isinstance(res, (int, float)):
        if float(res) == 1.0:
            return "yes"
        if float(res) == 0.0:
            return "no"
    return None


def outcome_coverage(refusals, outcomes):
    """(matched, total, newest ticker with no settlement) over BLOCKED rows.

    A REPORT THAT HAS RUN OUT OF DATA MUST SAY SO. Low coverage is the only
    thing that distinguishes "these gates turned nothing away" from "we cannot
    see what they turned away", and those are opposite findings.
    """
    have = miss = 0
    worst = None
    for r in refusals:
        tk = r.get("ticker")
        if not tk:
            continue
        if outcomes.get(tk):
            have += 1
        else:
            miss += 1
            if worst is None or (r.get("t") or "") > (worst[1] or ""):
                worst = (tk, r.get("t"))
    return have, have + miss, worst


# --------------------------------------------------------------- scoring
def would_be(r, outcome):
    """Dollars this refused trade would have made IF WE HAD BEEN FILLED.

    None when the record does not carry a price and a side -- the early gates
    fire before any of that exists, and inventing it would be the whole point
    of this file thrown away.
    """
    price = r.get("price")
    want = r.get("want")
    if price is None or want not in ("yes", "no") or outcome not in ("yes",
                                                                    "no"):
        return None
    n = min(float(r.get("size_now") or 0.0), float(r.get("size") or 0.0))
    if n <= 0:
        return None
    price = float(price)
    fee = pinrun.billed_fee(price, n)
    if want == outcome:
        return n * (1.0 - price) - fee
    return -n * price - fee


def attribute(refusals, bought, outcomes):
    """One row per gate."""
    rows = {}
    for r in refusals:
        g = r.get("gate")
        if not g:
            continue
        a = rows.setdefault(g, {"n": 0, "closes": set(), "delayed": 0,
                                "blocked": 0, "won": 0, "lost": 0,
                                "money": 0.0, "scored": 0, "unscorable": 0,
                                "no_price": 0, "no_side": 0, "no_size": 0,
                                "unsettled": 0})
        a["n"] += 1
        a["closes"].add(r.get("close_s"))
        tk = r.get("ticker")
        if tk in bought:
            # WE BOUGHT THIS MARKET IN THIS CLOSE ANYWAY. The gate moved the
            # entry; it did not prevent the trade, and scoring it as prevented
            # would credit or blame it for a trade that happened.
            a["delayed"] += 1
            continue
        a["blocked"] += 1
        # WHY a refusal cannot be scored, split out. The operator, 2026-09-18:
        # *"How can something block more than it would of won but not lost
        # anything."* Because `blocked` counted every refusal while
        # `won`/`lost` counted only the SCORABLE ones, and the difference --
        # 196 markets on one row -- was printed nowhere. A table whose columns
        # do not add up is a table nobody should believe, and he was right not
        # to. The three reasons are different things and only one of them is
        # a real limit:
        #   no_price  the gate fired before a price existed. Nothing was ever
        #             on the table, so there is nothing to value. Permanent.
        #   no_size   a price and a side were recorded but not the size. That
        #             is a LOGGING GAP, not a limit, and it silently threw
        #             away 545 of depth_floor's refusals.
        #   unsettled the market has not settled yet, or the pull has not
        #             caught up. Temporary; it resolves itself.
        if r.get("price") is None:
            a["no_price"] += 1
            continue
        if r.get("want") not in ("yes", "no"):
            a["no_side"] += 1
            continue
        if min(float(r.get("size_now") or 0.0), float(r.get("size") or 0.0)) <= 0:
            a["no_size"] += 1
            continue
        if not outcomes.get(tk):
            a["unsettled"] += 1
            continue
        pl = would_be(r, outcomes.get(tk))
        if pl is None:
            a["unscorable"] += 1
            continue
        a["scored"] += 1
        a["money"] += pl
        if pl > 0:
            a["won"] += 1
        else:
            a["lost"] += 1
    return rows


# WHICH GATES CAN BE SWITCHED OFF, and the start-record field that says so.
# The operator, 2026-09-18: *"Wait those are the gates that are currently
# running for us? Live on the real bot?"* -- a fair question the table could
# not answer, because a gate that is OFF and a gate that simply never fired
# both printed 0. Those are opposite facts. Anything not named here is always
# on and cannot be disabled by a flag.
SWITCHES = {
    "jump_against": ("jump_gate", lambda v: bool(v)),
    "dump_guard": ("dump_enabled", lambda v: bool(v)),
    "early_wide": ("early_max_edge", lambda v: v is not None),
    "price_band": ("skip_bands", lambda v: bool(v)),
    "hedge_wait_normal": ("hedge_normal", lambda v: bool(v)),
    "early_cheap": ("early_tau_max", lambda v: bool(v) and float(v) > 30),
    "early_once": ("early_tau_max", lambda v: bool(v) and float(v) > 30),
    "staged_none": ("early_tau_max", lambda v: bool(v) and float(v) > 30),
    "book_suspect": ("sweep_enabled", lambda v: bool(v)),
}

# The settings that decide what the gates DO. A log written under different
# values describes a different bot, so `config_currency` counts how much of
# the table is on today's settings rather than pooling ten days silently.
CONFIG_KEYS = ("pin", "edge_floor", "ev_floor", "price_ceiling", "jump_gate",
               "dump_enabled", "dump_discount", "max_per_close",
               "max_per_market", "min_level", "improve_by")


def gate_on(gate, start):
    """True / False / None (unknown) for whether a gate is switched on."""
    if not start:
        return None
    sw = SWITCHES.get(gate)
    if sw is None:
        return True
    field, test = sw
    if field not in start:
        return None
    try:
        return bool(test(start.get(field)))
    except Exception:                                          # noqa: BLE001
        return None


def config_currency(starts, refusals_by_file):
    """(logs on today's settings, refusals on them, total, earliest day).

    `starts` is {basename: start record}, newest last.
    """
    if not starts:
        return 0, 0, 0, None
    names = sorted(starts)
    cur = tuple(starts[names[-1]].get(k) for k in CONFIG_KEYS)
    same = nsame = ntot = 0
    first = None
    for nm in names:
        n = refusals_by_file.get(nm, 0)
        ntot += n
        if tuple(starts[nm].get(k) for k in CONFIG_KEYS) == cur:
            same += 1
            nsame += n
            if first is None:
                first = nm
    return same, nsame, ntot, first


def hedge_attrib(records, outcomes):
    """What every insurance ALARM was actually worth.

    THE GAP THIS FILLS. The gate table cannot see insurance at all -- those
    decisions are written under their own names, not as refusals -- so the
    single most expensive discretionary act the bot performs had no
    attribution of any kind. The operator caught the hole: *"I don't see an
    insurance test in the table."*

    The population is the ALARM, not the purchase. Asking "did the hedges we
    bought pay?" only ever looks at hedges we bought, which cannot say whether
    buying was the right call. Every alarm is one decision, and it has exactly
    two honest outcomes:

      our side went on to LOSE   -- insurance was genuinely needed
      our side went on to WIN    -- any premium paid was thrown away

    Money follows from the binary. A hedge contract costs `price` and pays a
    dollar iff our original side loses, so:

      needed: + n * (1 - price)      the hedge pays out
      wasted: - n * price            the hedge expires worthless

    Fees are NOT netted here: the hedge's fee is billed on the hedge leg and
    is already inside the close's own P&L, and subtracting it again would
    double-count it against the gate table's convention.
    """
    alarms, bought, noask = {}, {}, set()
    for r in records:
        k = r.get("kind")
        tk = r.get("ticker")
        if not tk:
            continue
        if k == "hedge_alarm":
            alarms.setdefault(tk, r)
        elif k == "hedge":
            b = bought.setdefault(tk, [0.0, 0.0])
            n = float(r.get("n") or 0)
            b[0] += n
            b[1] += n * float(r.get("price") or 0)
        elif k == "hedge_no_ask":
            noask.add(tk)
    out = {"needed": 0, "wasted": 0, "unresolved": 0, "uninsured": 0,
           "paid_out": 0.0, "thrown_away": 0.0, "no_ask": 0, "rows": [],
           # A52: the same tallies split by WHICH reason fired the alarm.
           # "belief" is the shipped trigger; "jump" is the post-entry jump
           # trigger. An alarm with no `trigger` field predates A52 and is
           # counted under "belief", which is what fired it.
           "by_trigger": {}}
    for tk, a in sorted(alarms.items()):
        want = a.get("want")
        res = outcomes.get(tk)
        n, cost = bought.get(tk, [0.0, 0.0])
        px = (cost / n) if n else None
        trig = a.get("trigger") or "belief"
        bt = out["by_trigger"].setdefault(trig, {"alarms": 0, "needed": 0,
                                                 "wasted": 0, "paid_out": 0.0,
                                                 "thrown_away": 0.0,
                                                 "prices": []})
        bt["alarms"] += 1
        if px:
            bt["prices"].append(px)
        row = {"ticker": tk, "want": want, "result": res, "n": n,
               "price": px, "no_ask": tk in noask, "trigger": trig,
               "jump_sd": a.get("jump_sd")}
        if res not in ("yes", "no") or want not in ("yes", "no"):
            row["verdict"] = "not settled on file"
            out["unresolved"] += 1
        elif res == want:
            row["verdict"] = ("our side won -- premium thrown away" if n
                              else "our side won -- nothing paid, correct")
            row["money"] = -cost
            out["thrown_away"] += cost
            bt["thrown_away"] += cost
            if n:
                out["wasted"] += 1
                bt["wasted"] += 1
        else:
            row["verdict"] = ("our side lost -- insurance paid" if n
                              else "our side lost -- UNINSURED")
            row["money"] = n * 1.0 - cost
            out["paid_out"] += n - cost
            out["needed"] += 1
            bt["needed"] += 1
            bt["paid_out"] += n - cost
            if not n:
                out["uninsured"] += 1
        if tk in noask:
            out["no_ask"] += 1
        out["rows"].append(row)
    out["alarms"] = len(alarms)
    out["net"] = out["paid_out"] - out["thrown_away"]
    return out


def hedge_report(h, say=print):
    lines = []
    w = lines.append
    w("  INSURANCE -- EVERY ALARM, AND WHETHER IT WAS WORTH ANYTHING")
    w("")
    w("  The gate table above cannot see any of this: insurance decisions are")
    w("  not recorded as refusals. This is the population the gate table")
    w("  misses, and it is counted by ALARM, not by purchase -- asking only")
    w("  whether the hedges we bought paid cannot say whether buying was the")
    w("  right call in the first place.")
    w("")
    if not h["alarms"]:
        w("  No insurance alarm on record yet.")
        txt = "\n".join(lines)
        if say:
            say(txt)
        return txt
    judged = h["needed"] + h["wasted"] + (h["rows"] and 0)
    w("  %d alarms on real money." % h["alarms"])
    w("    %d times our bet went on to LOSE  -- insurance was needed"
      % h["needed"])
    w("    %d times our bet went on to WIN   -- the premium was thrown away"
      % h["wasted"])
    if h["uninsured"]:
        w("    (%d of the needed ones we never managed to insure at all)"
          % h["uninsured"])
    if h["unresolved"]:
        w("    %d have not settled on file yet" % h["unresolved"])
    if h["no_ask"]:
        w("    %d found nobody selling the other side" % h["no_ask"])
    w("")
    w("  WHAT IT WAS WORTH")
    w("    paid out when needed      %+9.2f" % h["paid_out"])
    w("    thrown away when not      %+9.2f" % -h["thrown_away"])
    w("    ------------------------------------")
    w("    insurance, all in         %+9.2f" % h["net"])
    w("")
    if len(h.get("by_trigger") or {}) > 1:
        w("  BY WHICH REASON FIRED (A52 -- the jump trigger against the belief trigger,")
        w("  on the SAME arm; this is the comparison PREREG_a52_jump_hedge.md scores)")
        w("    %-8s %7s %7s %7s %10s %10s %12s" % ("trigger", "alarms", "needed",
                                                     "wasted", "paid out", "thrown", "median paid"))
        for trig, bt in sorted(h["by_trigger"].items()):
            ps = sorted(bt["prices"])
            med = ("%.3f" % ps[len(ps) // 2]) if ps else "  -  "
            w("    %-8s %7d %7d %7d %+10.2f %+10.2f %12s" % (
                trig, bt["alarms"], bt["needed"], bt["wasted"],
                bt["paid_out"], -bt["thrown_away"], med))
        w("    The thesis is that 'jump' pays a LOWER median price and is needed at")
        w("    least as often. Cheaper and mostly right, or it is buying noise.")
        w("")
    w("  A POSITIVE total does not make the rule right and a negative one does")
    w("  not make it wrong: this counts only markets where the alarm fired, and")
    w("  the alarm is the thing being judged. What matters is the HIT RATE --")
    w("  how often an alarm was followed by a real loss. Two paper tests are")
    w("  aimed at exactly that: A47 waits for the market price to agree, A51")
    w("  waits until the other side is a bet we would make on its own.")
    w("")
    w("  every alarm")
    for r in h["rows"]:
        w("    %-30s ours %-3s -> %-4s  %5.0f @ %s  %s"
          % (r["ticker"][:30], r["want"] or "?", r["result"] or "?",
             r["n"], ("%.3f" % r["price"]) if r["price"] else "  -  ",
             r["verdict"]))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def report(rows, say=print, order=GATE_ORDER, start=None, currency=None):
    lines = []
    w = lines.append
    w("  EVERY GATE IN THE BOT, IN THE ORDER IT IS ASKED")
    w("")
    w("  A gate only gets asked if every gate above it said yes, so a quiet")
    w("  row near the bottom may just mean the rows above got there first.")
    w("")
    w("  EVERY ROW ADDS UP:  fired = moved + blocked, and")
    w("                      blocked = won + lost + the three 'cannot say' columns.")
    w("")
    if currency:
        _same, _nsame, _ntot, _first = currency
        w("  HOW MUCH OF THIS IS TODAY'S BOT: %d of %d refusals (%.0f%%) come"
          % (_nsame, _ntot, (100.0 * _nsame / _ntot) if _ntot else 0))
        w("  from runs with exactly the settings that are live now, starting")
        w("  %s. The rest ran under older settings and describe"
          % (_first or "?"))
        w("  a bot that no longer exists.")
        w("")
    w("  gate            | on? |  fired | moved |blocked |  won | lost |no price|no size|unsettled| $ if filled")
    w("  ----------------|-----|--------|-------|--------|------|------|--------|-------|---------|------------")
    seen = []
    for g in order + sorted(x for x in rows if x not in order):
        if g in seen:
            continue
        seen.append(g)
        _on = gate_on(g, start)
        _onw = {True: " on", False: "OFF", None: "  ?"}[_on]
        a = rows.get(g)
        if a is None:
            w("  %-16s| %s |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -"
              % (g, _onw))
            continue
        nop = a["no_price"] + a["no_side"] + a["unscorable"]
        money = ("%+11.2f" % a["money"]) if a["scored"] else "      -"
        # `delayed`, NOT len(closes). The first version of this row printed the
        # close count under the "moved" heading, so fired != moved + blocked
        # on every line -- the exact arithmetic failure this rewrite existed to
        # remove. The self-test now reads the RENDERED table back and checks
        # the identity, because checking it on the data would have passed.
        w("  %-16s| %s | %6d | %5d | %6d | %4s | %4s | %6d | %5d | %7d |%s"
          % (g, _onw, a["n"], a["delayed"], a["blocked"],
             a["won"] if a["scored"] else "-",
             a["lost"] if a["scored"] else "-",
             nop, a["no_size"], a["unsettled"], money))
    w("")
    w("  WHAT THIS TABLE DOES NOT COVER: the INSURANCE decisions. Whether to")
    w("  buy the other side when a bet turns, and at what price, is decided")
    w("  somewhere else in the bot and is not recorded as a refusal, so no row")
    w("  here can ever describe it. Read those from the hedge list instead")
    w("  (`/hedges` on the phone, or the Now tab). As of 2026-09-18 that is 12")
    w("  insured quarter-hours of which 11 still ended negative.")
    w("")
    w("  'on?' IS THE LIVE BOT RIGHT NOW, read from its own newest start")
    w("  record -- not from this file's defaults. A gate marked OFF is not")
    w("  running for real money, so its zero means 'switched off', not 'never")
    w("  needed'. Those are opposite facts and they used to print the same.")
    w("")
    w("  WHY A BLOCKED MARKET MAY HAVE NO WIN/LOSE")
    w("    no price   the gate fired BEFORE any price existed -- nothing was")
    w("               ever on the table, so there is nothing to value. This")
    w("               will never be scorable and that is correct.")
    w("    no size    a price and a side were recorded but not the size. That")
    w("               is a LOGGING GAP in the bot, not a limit, and it is")
    w("               being closed gate by gate.")
    w("    unsettled  the market has not settled yet, or the settlement pull")
    w("               has not caught up. It resolves itself.")
    w("")
    w("  WHY 'would lose' IS SO OFTEN ZERO, and why that is not a broken column.")
    w("  Every gate below `confidence` is only ever asked about a market the")
    w("  model is ALREADY at least 99.5% sure of. That is the population, not")
    w("  a sample of it. Those markets win almost every time whether we buy")
    w("  them or not, so a gate that turns them away turns away winners -- by")
    w("  construction. The outcomes behind this column were checked against")
    w("  Kalshi's own settlement record on 503 shared markets and agreed on")
    w("  503 of 503, with the underlying results running a balanced 50/50.")
    w("  A gate stopping winners is therefore the EXPECTED reading; what makes")
    w("  a gate worth keeping is the size of the loss it prevents when it is")
    w("  right, which is why one -$37.85 row can outweigh a thousand small")
    w("  forgone wins.")
    w("")
    w("  `$ if we had been filled` is an UPPER BOUND, not profit and loss. A")
    w("  price showing is not a fill -- we would have been racing for it, and")
    w("  the live fill rate is about 7 in 10. A POSITIVE number means the gate")
    w("  turned away trades that would have won; a NEGATIVE number means it")
    w("  turned away trades that would have lost, which is it doing its job.")
    w("")
    w("  These figures DO NOT add up to the bot's profit and never will: the")
    w("  gates share one contract budget, so refusing one trade frees money a")
    w("  later trade spends. Only a re-run with a gate switched off gives its")
    w("  true worth.")
    w("")
    w("  WHAT EACH ONE IS")
    for g in seen:
        if g in WHAT:
            w("    %-16s %s" % (g, WHAT[g]))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


# --------------------------------------------------------------- selftest
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # ---- the money arithmetic, against hand-checked numbers --------------
    r = {"price": 0.90, "want": "yes", "size": 100.0, "size_now": 10.0}
    got = would_be(r, "yes")
    hand = 10.0 * 0.10 - pinrun.billed_fee(0.90, 10.0)
    ck(abs(got - hand) < 1e-12,
       "a winning 90c buy of 10 pays 10c each less the fee: $%+.4f" % got)
    ck(abs(would_be(r, "no") - (-10.0 * 0.90
                                - pinrun.billed_fee(0.90, 10.0))) < 1e-12,
       "and a losing one costs the whole 90c each plus the fee")
    ck(would_be(dict(r, size=4.0), "yes") == would_be(dict(r, size_now=4.0),
                                                      "yes"),
       "the contracts counted are the SMALLER of what was offered and what "
       "the bot was sized for -- taking the larger would inflate every gate "
       "that fired on a thin book")
    # SETTLEMENTS COME FROM EVERY fulltape DIRECTORY, NEWEST WINNING. Reading
    # only the base file left every gate's money column blank for six days
    # while the report claimed nothing was wrong.
    import tempfile as _tf
    _td = _tf.mkdtemp()
    _base = os.path.join(_td, "fulltape")
    _recent = os.path.join(_td, "fulltape_recent")
    os.makedirs(_base)
    os.makedirs(_recent)
    with open(os.path.join(_base, "markets.json"), "w", encoding="utf-8") as fh:
        json.dump({"KXBTC15M": [{"ticker": "OLD-1", "result": "yes"},
                                {"ticker": "BOTH-1", "result": "no"}]}, fh)
    with open(os.path.join(_recent, "markets.json"), "w", encoding="utf-8") as fh:
        json.dump({"KXBTC15M": [{"ticker": "NEW-1", "result": "no"},
                                {"ticker": "BOTH-1", "result": "yes"}]}, fh)
    _o = load_outcomes(os.path.join(_base, "markets.json"))
    ck(_o.get("OLD-1") == "yes" and _o.get("NEW-1") == "no",
       "settlements are read from the base directory AND every fulltape_* "
       "beside it -- reading only the base is what blanked the money column "
       "for every one of the bot's gates")
    ck(_o.get("BOTH-1") == "yes",
       "...and where they disagree the LATER directory wins, because that is "
       "the refreshed pull")
    # THE FRESH PULL WRITES A NUMBER, THE OLD ONE WROTE A WORD.
    ck(_result_word(1.0) == "yes" and _result_word(0.0) == "no",
       "a settlement whose result is the NUMBER 1.0 or 0.0 is read -- testing "
       "only for the words dropped every fresh settlement and left coverage "
       "at 0 of 6,442 even after the directory glob was fixed")
    ck(_result_word("Yes") == "yes" and _result_word("no") == "no",
       "...and the old word form still reads, in any case")
    ck(_result_word(0.5) is None and _result_word("void") is None
       and _result_word(None) is None,
       "NULL: anything that is not plainly one or zero is NOT an outcome, "
       "rather than being rounded into one (hard rule 5)")
    with open(os.path.join(_recent, "markets.json"), "w", encoding="utf-8") as fh:
        json.dump({"KXBTC15M": [{"ticker": "NUM-1", "result": 1.0},
                                {"ticker": "NUM-0", "result": 0.0}]}, fh)
    _o2 = load_outcomes(os.path.join(_base, "markets.json"))
    ck(_o2.get("NUM-1") == "yes" and _o2.get("NUM-0") == "no",
       "and a real numeric settlement file loads end to end")
    _h, _t, _w = outcome_coverage(
        [{"ticker": "OLD-1", "t": "2026-09-10T00:00:00Z"},
         {"ticker": "GONE-1", "t": "2026-09-17T00:00:00Z"},
         {"ticker": "GONE-2", "t": "2026-09-12T00:00:00Z"}], _o)
    ck(_h == 1 and _t == 3,
       "coverage counts how many refused markets we can actually score")
    ck(_w and _w[0] == "GONE-1",
       "...and names the NEWEST one we cannot, which is the one that says how "
       "stale the settlement pull is")
    ck(outcome_coverage([], _o) == (0, 0, None),
       "NULL: no refusals is (0, 0, None), not a fabricated 100% coverage")
    # EVERY ROW MUST ADD UP. The operator: "How can something block more than
    # it would of won but not lost anything." It could because `blocked`
    # counted every refusal while won/lost counted only the scorable ones, and
    # the 196-market difference was printed nowhere.
    _refs = [
        # scorable, and wins
        {"gate": "g", "ticker": "T-WIN", "close_s": 1, "want": "yes",
         "price": 0.9, "size": 10.0, "size_now": 10.0},
        # scorable, and loses
        {"gate": "g", "ticker": "T-LOSE", "close_s": 1, "want": "no",
         "price": 0.9, "size": 10.0, "size_now": 10.0},
        # fired before a price existed
        {"gate": "g", "ticker": "T-NOPX", "close_s": 1},
        # price and side, but the size was never logged
        {"gate": "g", "ticker": "T-NOSZ", "close_s": 1, "want": "yes",
         "price": 0.9, "size_now": 10.0},
        # everything logged, but the market has not settled
        {"gate": "g", "ticker": "T-UNSET", "close_s": 1, "want": "yes",
         "price": 0.9, "size": 10.0, "size_now": 10.0},
        # we refused it and then bought it anyway
        {"gate": "g", "ticker": "T-MOVED", "close_s": 1, "want": "yes",
         "price": 0.9, "size": 10.0, "size_now": 10.0},
    ]
    _out = {"T-WIN": "yes", "T-LOSE": "yes", "T-NOSZ": "yes", "T-MOVED": "yes"}
    _rows = attribute(_refs, {"T-MOVED"}, _out)
    _a = _rows["g"]
    ck(_a["n"] == 6 and _a["delayed"] == 1 and _a["blocked"] == 5,
       "fired = moved + blocked, exactly")
    ck(_a["won"] == 1 and _a["lost"] == 1,
       "one blocked market would have won and one would have lost")
    ck(_a["no_price"] == 1 and _a["no_size"] == 1 and _a["unsettled"] == 1,
       "and the three markets that cannot be judged are split by WHY, because "
       "'no price was ever showing' and 'we forgot to log the size' are "
       "different problems and only the second is fixable")
    ck(_a["blocked"] == _a["won"] + _a["lost"] + _a["no_price"]
       + _a["no_side"] + _a["no_size"] + _a["unsettled"] + _a["unscorable"],
       "BLOCKED ADDS UP to won + lost + every reason we cannot say -- a table "
       "whose columns do not reconcile is a table nobody should believe")
    _txt = report(_rows, say=None)
    ck("EVERY ROW ADDS UP" in _txt and "no size" in _txt,
       "...and the report states the identity and shows the columns that make "
       "it true, rather than hiding the remainder")
    # READ THE RENDERED TABLE BACK AND CHECK THE ARITHMETIC ON THE PAGE.
    # Checking `rows` would have passed while the printed row put the CLOSE
    # COUNT under the "moved" heading, so fired != moved + blocked on every
    # line. The number a person reads is the number that has to reconcile.
    _bad = []
    for _line in _txt.splitlines():
        if not _line.startswith("  g  ") and not _line.strip().startswith("g |"):
            if "|" not in _line or _line.strip().startswith("gate"):
                continue
        _cells = [c.strip() for c in _line.split("|")]
        if len(_cells) < 9 or not _cells[1].isdigit():
            continue
        _fired, _moved, _blocked = (int(_cells[1]), int(_cells[2]),
                                    int(_cells[3]))
        if _fired != _moved + _blocked:
            _bad.append((_cells[0], _fired, _moved, _blocked))
    ck(not _bad,
       "in the RENDERED table every row satisfies fired = moved + blocked: %r"
       % (_bad[:3],))
    # IS THIS GATE ACTUALLY RUNNING FOR REAL MONEY? A gate that is switched
    # OFF and a gate that never fired both printed 0. Opposite facts.
    _live = {"jump_gate": True, "dump_enabled": True, "early_max_edge": 3.0,
             "hedge_normal": None, "early_tau_max": 45, "sweep_enabled": True}
    ck(gate_on("jump_against", _live) is True
       and gate_on("early_wide", _live) is True,
       "a gate whose flag is set reads as ON")
    ck(gate_on("hedge_wait_normal", _live) is False,
       "A51's gate reads OFF, because the live bot does not pass "
       "--hedge-normal -- its zero means 'not running', not 'never needed'")
    ck(gate_on("confidence", _live) is True,
       "a gate with no switch at all is always on")
    ck(gate_on("jump_against", {}) is None
       and gate_on("anything", None) is None,
       "NULL: with no start record on file the answer is '?' rather than a "
       "confident claim that everything is running")
    ck(gate_on("early_cheap", {"early_tau_max": 30}) is False,
       "the early-leg gates read OFF when the early window is closed, which "
       "is what `early_tau_max == TAU_MAX` means")
    # A REAL gate switched off, not the phantom row. This used to assert on
    # `hedge_wait_normal`, which was never a gate at all -- so the check
    # passed on the strength of the very bug it should have caught.
    _off = dict(_live, jump_gate=False)
    _txt2 = report(_rows, say=None, start=_off)
    ck(" on |" in _txt2 and "OFF |" in _txt2 and "on? |" in _txt2,
       "and the table carries an on/off column read from the LIVE bot's own "
       "start record, not from this file's defaults")

    # WHICH BOT IS THIS TABLE DESCRIBING? Pooling restarts with different
    # settings silently mixes several different bots into one row.
    _starts = {"a.jsonl": {"pin": 0.99}, "b.jsonl": {"pin": 0.995},
               "c.jsonl": {"pin": 0.995}}
    _same, _nsame, _ntot, _first = config_currency(
        _starts, {"a.jsonl": 100, "b.jsonl": 30, "c.jsonl": 70})
    ck(_same == 2 and _nsame == 100 and _ntot == 200,
       "currency counts only the runs whose settings match the NEWEST one, so "
       "a table pooling ten days says how much of itself is today's bot")
    ck(_first == "b.jsonl",
       "...and names the first run that matches, which is how far back the "
       "current configuration actually goes")
    ck(config_currency({}, {}) == (0, 0, 0, None),
       "NULL: no start records is zeros and no date, not a claim of 100%")
    ck("would lose" in _txt and "99.5" in _txt,
       "the report explains WHY 'would lose' is so often zero -- these gates "
       "only ever see markets the model is already sure of")
    # INSURANCE, which the gate table structurally cannot see.
    _hrec = [
        # alarm, our side went on to LOSE, we insured 10 at 50c -> pays $10
        {"kind": "hedge_alarm", "ticker": "H-NEED", "want": "yes"},
        {"kind": "hedge", "ticker": "H-NEED", "n": 10.0, "price": 0.50},
        # alarm, our side went on to WIN, we insured 10 at 20c -> $2 wasted
        {"kind": "hedge_alarm", "ticker": "H-WASTE", "want": "yes"},
        {"kind": "hedge", "ticker": "H-WASTE", "n": 10.0, "price": 0.20},
        # alarm, our side lost, nobody was selling the other side
        {"kind": "hedge_alarm", "ticker": "H-NOASK", "want": "yes"},
        {"kind": "hedge_no_ask", "ticker": "H-NOASK"},
        # alarm on a market that has not settled
        {"kind": "hedge_alarm", "ticker": "H-OPEN", "want": "yes"},
    ]
    _hout = {"H-NEED": "no", "H-WASTE": "yes", "H-NOASK": "no"}
    _h = hedge_attrib(_hrec, _hout)
    ck(_h["alarms"] == 4, "the population is the ALARM, not the purchase -- "
       "asking only whether the hedges we BOUGHT paid cannot say whether "
       "buying was the right call")
    ck(_h["needed"] == 2 and _h["wasted"] == 1 and _h["unresolved"] == 1,
       "each alarm resolves to needed, wasted, or not-yet-settled")
    ck(_h["uninsured"] == 1 and _h["no_ask"] == 1,
       "an alarm we could not act on is counted as needed AND as uninsured, "
       "because the loss happened whether or not anyone would sell to us")
    ck(abs(_h["paid_out"] - 5.0) < 1e-9,
       "a hedge bought at 50c that pays a dollar earns 50c a contract: $5.00 "
       "on ten")
    ck(abs(_h["thrown_away"] - 2.0) < 1e-9,
       "a hedge bought at 20c on a bet that WON is worth nothing: $2.00 gone")
    ck(abs(_h["net"] - 3.0) < 1e-9, "and the two net to $3.00")
    # A52: alarms split by which trigger fired, so the jump arm's bars read
    # straight off the report.
    _hrec2 = _hrec + [
        {"kind": "hedge_alarm", "ticker": "H-JUMP", "want": "yes",
         "trigger": "jump", "jump_sd": 9.1},
        {"kind": "hedge", "ticker": "H-JUMP", "n": 10.0, "price": 0.15},
    ]
    _h2 = hedge_attrib(_hrec2, dict(_hout, **{"H-JUMP": "no"}))
    ck(set(_h2["by_trigger"]) == {"belief", "jump"},
       "alarms are split by trigger, and an alarm with no trigger field -- one "
       "written before A52 -- is counted as 'belief', which is what fired it")
    ck(_h2["by_trigger"]["jump"]["needed"] == 1
       and abs(_h2["by_trigger"]["jump"]["paid_out"] - 8.5) < 1e-9,
       "a jump-fired hedge bought at 15c on a bet that LOST pays 85c a "
       "contract -- the whole thesis is that it fires while the other side is "
       "still cheap")
    ck(_h2["by_trigger"]["belief"]["needed"] == 2
       and _h2["needed"] == 3,
       "...and the totals still add up across triggers")
    _ht2 = hedge_report(_h2, say=None)
    ck("BY WHICH REASON FIRED" in _ht2 and "median paid" in _ht2,
       "the report shows the per-trigger block when two triggers exist")
    ck("BY WHICH REASON FIRED" not in hedge_report(_h, say=None),
       "NULL: with one trigger only there is nothing to compare and the block "
       "is omitted rather than printing a one-row table")
    ck(hedge_attrib([], {})["alarms"] == 0
       and "No insurance alarm on record" in hedge_report(
           hedge_attrib([], {}), say=None),
       "NULL: no alarms says so, rather than printing a $0.00 that reads as "
       "insurance having been free")
    _ht = hedge_report(_h, say=None)
    ck("HIT RATE" in _ht and "A47" in _ht and "A51" in _ht,
       "the report says the hit rate is the thing being judged, and names the "
       "two tests aimed at it -- a positive total does not make the rule right")
    ck(would_be({"price": None, "want": "yes"}, "yes") is None,
       "a refusal with no price is NOT scored -- the early gates fire before "
       "a price exists and inventing one is the whole point thrown away")
    ck(would_be(r, None) is None,
       "and a market with no settlement on file is not scored either")

    # ---- delayed vs blocked, which is the heart of it --------------------
    refs = [
        # refused at 30s, then bought -- the gate MOVED the trade, not stopped
        {"kind": "refused", "gate": "edge_floor", "ticker": "A",
         "close_s": 900, "price": 0.97, "want": "yes", "size": 100.0,
         "size_now": 10.0},
        # refused and never bought, and it would have LOST
        {"kind": "refused", "gate": "dump_guard", "ticker": "B",
         "close_s": 900, "price": 0.80, "want": "yes", "size": 100.0,
         "size_now": 10.0},
        # refused and never bought, and it would have WON
        {"kind": "refused", "gate": "dump_guard", "ticker": "C",
         "close_s": 1800, "price": 0.80, "want": "yes", "size": 100.0,
         "size_now": 10.0},
    ]
    rows = attribute(refs, bought={"A"},
                     outcomes={"A": "yes", "B": "no", "C": "yes"})
    ck(rows["edge_floor"]["delayed"] == 1
       and rows["edge_floor"]["blocked"] == 0,
       "a market we refused and then BOUGHT is counted as delayed, never as "
       "blocked -- scoring it would credit the gate for a trade that happened")
    ck(rows["edge_floor"]["scored"] == 0,
       "and a delayed refusal contributes no money either way")
    ck(rows["dump_guard"]["blocked"] == 2
       and rows["dump_guard"]["closes"] == {900, 1800},
       "two genuinely blocked markets across two closes")
    ck(rows["dump_guard"]["won"] == 1 and rows["dump_guard"]["lost"] == 1,
       "one would have won and one would have lost")
    _hand = (-10.0 * 0.80 - pinrun.billed_fee(0.80, 10.0)) \
        + (10.0 * 0.20 - pinrun.billed_fee(0.80, 10.0))
    ck(abs(rows["dump_guard"]["money"] - _hand) < 1e-12,
       "and the money is the two added: $%+.4f" % rows["dump_guard"]["money"])

    # ---- a gate that saved money must read NEGATIVE ----------------------
    saver = [{"kind": "refused", "gate": "dump_guard", "ticker": "B",
              "close_s": 900 * i, "price": 0.95, "want": "yes",
              "size": 100.0, "size_now": 10.0} for i in range(1, 11)]
    for i, x in enumerate(saver):
        x["ticker"] = "L%d" % i
    rows2 = attribute(saver, bought=set(),
                      outcomes=dict(("L%d" % i, "no") for i in range(10)))
    ck(rows2["dump_guard"]["money"] < 0,
       "a gate that turned away ten losers reads NEGATIVE ($%+.2f), which is "
       "it doing its job -- if the sign were flipped every guard in the bot "
       "would look like it was costing money"
       % rows2["dump_guard"]["money"])

    # ---- the report must not hide a gate that never fired ----------------
    txt = report({"dump_guard": rows2["dump_guard"]}, say=None)
    ck("price_ceiling" in txt,
       "a gate with no refusals still gets a row -- 'it never fired' and 'we "
       "never looked' must not look the same")
    ck("UPPER BOUND" in txt and "DO NOT add up" in txt,
       "and both caveats travel with the table rather than living in a "
       "docstring nobody opens")

    # ---- the gate list must match pinrun's, or a gate is invisible -------
    src = open(os.path.join(HERE, "pinrun.py"), encoding="utf-8").read()
    live = set()
    for ln in src.split(chr(10)):
        t = ln.strip()
        if t.startswith('_gate("'):
            live.add(t.split('"')[1])
    ck(live, "pinrun.py has instrumented gates to read")
    ck(live <= set(GATE_ORDER),
       "every gate pinrun records appears in GATE_ORDER, so none is dropped "
       "from the report (%s)" % sorted(live - set(GATE_ORDER)))
    ck(set(GATE_ORDER) <= set(WHAT),
       "and every one has a plain-English description (%s)"
       % sorted(set(GATE_ORDER) - set(WHAT)))
    # THE OTHER DIRECTION, which was never checked. A name in GATE_ORDER that
    # is not a real `_gate()` call prints a permanent zero row that looks
    # measured and cannot ever be. `hedge_wait_normal` sat there doing exactly
    # that -- an authoritative zero for a test that is paper-only.
    ck(set(GATE_ORDER) <= live,
       "every name in GATE_ORDER is a REAL _gate() call in pinrun, so the "
       "table cannot show a row that could never hold a number (%s)"
       % sorted(set(GATE_ORDER) - live))
    print("pinattrib selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--logs", default=os.path.join(REPO, "results"),
                    help="directory of pinrun-*.jsonl logs")
    ap.add_argument("--glob", default="pinrun-live-*.jsonl",
                    help="which logs: the default is LIVE only, because a "
                         "paper run's refusals are a different bot")
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "RESULTS_attrib.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_ATTRIB_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    paths = sorted(glob.glob(os.path.join(a.logs, a.glob)))
    if not paths:
        print("pinattrib: loaded nothing -- no log matched %s" % a.glob)
        return 0
    refusals, bought, _settled, starts, per_file, hedges = load_log(paths)
    outcomes = load_outcomes(a.markets)
    print("  %d logs, %d gate refusals, %d markets ordered, %d settlements"
          % (len(paths), len(refusals), len(bought), len(outcomes)))
    _have, _tot, _worst = outcome_coverage(refusals, outcomes)
    _cov = (100.0 * _have / _tot) if _tot else 0.0
    print("  settlement coverage: %d of %d refused markets (%.0f%%)"
          % (_have, _tot, _cov))
    if _cov < 80.0:
        print("  *** COVERAGE IS LOW. The money column below is blank or "
              "partial because settlements are MISSING, not because the gates "
              "turned nothing away. Those are opposite findings. Newest "
              "unsettled: %s (%s). Refresh with kalshi_fulltape.py. ***"
              % (_worst or ("?", "?")))
    if not refusals:
        print("pinattrib: loaded nothing -- no gate refusal is on record yet. "
              "AMENDMENT 25 instrumentation only starts recording from the "
              "next bot restart.")
        return 0
    rows = attribute(refusals, bought, outcomes)
    newest = starts[sorted(starts)[-1]] if starts else None
    txt = report(rows, start=newest,
                 currency=config_currency(starts, per_file))
    txt += chr(10) + chr(10) + hedge_report(hedge_attrib(hedges, outcomes),
                                            say=print)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_attrib -- what each gate in the bot actually did"
                 + nl + nl)
        fh.write("```" + nl + txt + nl + "```" + nl)
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
