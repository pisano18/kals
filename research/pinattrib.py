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
    "confidence", "no_offer", "depth_floor", "edge_floor", "dump_guard",
    "improve_by", "rebuy_band", "price_ceiling", "ev_floor",
]

WHAT = {
    "close_budget": "the close has already bought its contract budget",
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
    "dump_guard": "priced far below fair -- someone else knew something",
    "improve_by": "a second buy that was not cheaper than the first",
    "rebuy_band": "a same-coin re-buy outside the 0.5-1c band",
    "price_ceiling": "priced above the 98c ceiling",
    "ev_floor": "expected value negative at that price",
}


# --------------------------------------------------------------- loading
def load_log(paths):
    """(refusals, bought, settled_by_market) from pinrun's own jsonl logs."""
    refusals, bought, settled = [], set(), {}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    m = json.loads(ln)
                except ValueError:
                    continue
                k = m.get("kind")
                if k == "refused":
                    refusals.append(m)
                elif k == "order":
                    # an order SENT on this market; the close is in the ticker
                    bought.add(m.get("ticker"))
                elif k == "settled":
                    settled.setdefault(m.get("ticker"), []).append(m)
    return refusals, bought, settled


def load_outcomes(markets_json):
    """{ticker: "yes"/"no"} from the settlement pull."""
    out = {}
    if not os.path.exists(markets_json):
        return out
    with open(markets_json, encoding="utf-8") as fh:
        d = json.load(fh)
    for _ser, rows in (d or {}).items():
        for r in rows or []:
            res = r.get("result")
            if res in ("yes", "no"):
                out[r["ticker"]] = res
    return out


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
                                "money": 0.0, "scored": 0, "unscorable": 0})
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


def report(rows, say=print, order=GATE_ORDER):
    lines = []
    w = lines.append
    w("  EVERY GATE IN THE BOT, IN THE ORDER IT IS ASKED")
    w("")
    w("  A gate only gets asked if every gate above it said yes, so a quiet")
    w("  row near the bottom may just mean the rows above got there first.")
    w("")
    w("  gate            | stopped | closes | only  | really  | of those blocked      | $ if we had")
    w("                  |  it     |        | moved | blocked | would WIN / would LOSE|  been filled")
    w("  ----------------|---------|--------|-------|---------|-----------------------|-------------")
    seen = []
    for g in order + sorted(x for x in rows if x not in order):
        if g in seen:
            continue
        seen.append(g)
        a = rows.get(g)
        if a is None:
            w("  %-16s|       0 |      0 |     0 |       0 |        -              |      -"
              % g)
            continue
        scored = "%5d / %-5d" % (a["won"], a["lost"]) if a["scored"] else \
                 "   -   (no price)"
        money = ("%+11.2f" % a["money"]) if a["scored"] else "      -"
        w("  %-16s| %7d | %6d | %5d | %7d | %-21s | %s"
          % (g, a["n"], len(a["closes"]), a["delayed"], a["blocked"],
             scored, money))
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
    refusals, bought, _settled = load_log(paths)
    outcomes = load_outcomes(a.markets)
    print("  %d logs, %d gate refusals, %d markets ordered, %d settlements"
          % (len(paths), len(refusals), len(bought), len(outcomes)))
    if not refusals:
        print("pinattrib: loaded nothing -- no gate refusal is on record yet. "
              "AMENDMENT 25 instrumentation only starts recording from the "
              "next bot restart.")
        return 0
    rows = attribute(refusals, bought, outcomes)
    txt = report(rows)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_attrib -- what each gate in the bot actually did"
                 + nl + nl)
        fh.write("```" + nl + txt + nl + "```" + nl)
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
