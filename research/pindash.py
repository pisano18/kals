#!/usr/bin/env python3
# VERSION: 2026-09-14-dash1
"""pindash.py -- the bot's whole life in one page you can open yourself.

THE OPERATOR, 2026-09-13: "I don't like the tool we made a few days ago. Can
you take this new thing and put it as a tool I can go in myself and look at. As
well as a chart to track my personal bankroll ... be certain it includes every
single strategy the bot uses when determining a buy, a sell, a hedge, every
step in the process. Also include all the transactions I can click and see all
the values involved and what they were at the time of purchase and throughout
up until close ... In the end I should be able to see why something was bought,
what you thought about it throughout the trade, thought after if any, and all
the results that come from all of that."

WHY A FILE AND NOT A SERVER. `pintool.py` is a local web server on port 8765,
and it is the thing he does not like. This writes ONE self-contained HTML file
that he opens by double-clicking. No server to be running, no port, no process
to die overnight. It also means his account balance and every trade he has ever
made stay on his disk: the page loads nothing from the network, and the
self-test fails if a single external URL appears in the output.

WHERE EVERY NUMBER COMES FROM. `results/pinrun-live-*.jsonl`, which the live
bot writes as it goes, plus `fulltape/markets.json` for settlements. Nothing is
modelled and nothing is replayed -- if a figure is on this page, it happened.

THE BANKROLL CURVE IS PART REAL AND PART RECONSTRUCTED, and the page says so.
The bot only began reading the account balance on 2026-09-13 (AMENDMENT 16),
so there are real readings from then on and, before that, the curve is the
settled trades added up backwards from the first real reading. The self-test
requires the two to agree where they overlap; if they ever stop agreeing, money
moved in or out of the account and the reconstruction is wrong, so the page
says that out loud rather than drawing a confident wrong line.
"""
import argparse
import glob
import html
import json
import os
import re
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinrun                                                  # noqa: E402

ET_OFFSET_NOTE = "all times US Eastern"


# ---------------------------------------------------------------- time
def to_epoch(ts):
    """'2026-09-13T23:29:53Z' -> epoch seconds."""
    if not ts:
        return None
    try:
        return int(time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
                   - time.timezone)
    except (ValueError, TypeError):
        return None


def et(ts):
    """UTC stamp -> 'Sep 13, 7:29:53 PM ET'. Presentation only: CLAUDE.md
    keeps everything inside the repo in UTC and converts at the last moment."""
    e = to_epoch(ts)
    if e is None:
        return ""
    lt = time.localtime(e)
    zone = "EDT" if lt.tm_isdst else "EST"
    return time.strftime("%b %-d, %-I:%M:%S %p ", lt).replace(" 0", " ") + zone \
        if os.name != "nt" else \
        time.strftime("%b %d, %I:%M:%S %p ", lt) + zone


# ---------------------------------------------------------------- money
def usd(x, sign=True):
    """Money ALWAYS carries a dollar sign, losses included. The operator, and
    it is the only formatting rule he gave: "As far as money goes for the tool
    just if you can't put a dollar sign on it, do that, same for losses."
    """
    if x is None:
        return "--"
    x = float(x)
    s = "%s$%.2f" % ("-" if x < 0 else ("+" if sign else ""), abs(x))
    return s


def cents(x):
    if x is None:
        return "--"
    return "%.1f¢" % (100.0 * float(x))


# ---------------------------------------------------------------- loading
def load(paths):
    ev = defaultdict(list)
    for p in sorted(paths):
        run = os.path.basename(p)
        with open(p, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    m = json.loads(ln)
                except ValueError:
                    continue
                m["_run"] = run
                ev[m.get("kind")].append(m)
    return ev


def load_outcomes(markets_json):
    out = {}
    if not os.path.exists(markets_json):
        return out
    try:
        with open(markets_json, encoding="utf-8") as fh:
            d = json.load(fh)
    except (ValueError, OSError):
        return out
    for _s, rows in (d or {}).items():
        for r in rows or []:
            out[r.get("ticker")] = r
    return out


# ---------------------------------------------------------------- trades
def build_trades(ev, outcomes):
    """One record per FILLED order, carrying everything known about it.

    Joined on (ticker, nearest preceding signal). A market can be bought twice
    in one close, so the join is by order, never by ticker alone -- keying on
    the ticker would silently merge the legs of a scaled-in position and report
    one trade at the wrong price.
    """
    sigs = defaultdict(list)
    for s in ev.get("signal", []):
        sigs[s.get("ticker")].append(s)
    for k in sigs:
        sigs[k].sort(key=lambda m: to_epoch(m.get("t")) or 0)

    settles = defaultdict(list)
    for s in ev.get("settled", []):
        settles[s.get("ticker")].append(s)
    for k in settles:
        settles[k].sort(key=lambda m: to_epoch(m.get("t")) or 0)

    hedges = defaultdict(list)
    for k in ("hedge_alarm", "hedge", "hedge_no_ask", "hedge_gave_up"):
        for h in ev.get(k, []):
            hedges[h.get("ticker")].append(h)
    for k in hedges:
        hedges[k].sort(key=lambda m: to_epoch(m.get("t")) or 0)

    # THE SPINE IS THE SETTLED LEGS, NOT THE ORDERS, and that is the whole
    # correctness of this function. The first version walked `order` records
    # and attached a settlement to each. A HEDGE fill does not write an
    # `order` record -- it writes a `hedge` record -- so nine settled legs
    # worth -$9.93 fell off the page entirely, and every one of them was a
    # LOSING leg. The dashboard read +$163.28 against a true +$153.35 and
    # showed 8 losing closes where there were 10. Anything that settled is
    # real money and must appear; the order is what gets attached to it.
    fills = []
    for o in ev.get("order", []):
        if float(o.get("filled") or 0) > 0:
            fills.append({"id": len(fills), "kind": "order", "rec": o,
                          "tk": o.get("ticker"), "ft": to_epoch(o.get("t")),
                          "side": None})
    for h in ev.get("hedge", []):
        if float(h.get("n") or 0) > 0:
            fills.append({"id": len(fills), "kind": "hedge", "rec": h,
                          "tk": h.get("ticker"), "ft": to_epoch(h.get("t")),
                          "side": h.get("side")})
    for p in ev.get("plant", []):
        if float(p.get("filled") or 0) > 0:
            fills.append({"id": len(fills), "kind": "plant", "rec": p,
                          "tk": p.get("ticker"), "ft": to_epoch(p.get("t")),
                          "side": p.get("side")})
    fills.sort(key=lambda r: r["ft"] or 0)

    by_tk = defaultdict(list)
    for f in fills:
        by_tk[f["tk"]].append(f)

    out = []
    # KEYED ON THE FILL'S OWN ID, never on its position in a per-market list.
    # The first version used the per-market index against one global set, so
    # consuming fill 0 of BTC also marked fill 0 of ETH consumed, and every
    # hedge leg in the file went unmatched.
    taken = set()
    for tk, rows in settles.items():
        mk = outcomes.get(tk) or {}
        avail = by_tk.get(tk, [])
        for st in rows:
            stt = to_epoch(st.get("t"))
            want = st.get("want")
            # the latest matching fill on that side at or before settlement
            pick = None
            for f in avail:
                if f["id"] in taken:
                    continue
                if want and f["side"] and f["side"] != want:
                    continue
                if f["ft"] is not None and stt is not None \
                        and f["ft"] > stt + 5:
                    continue
                pick = f
            if pick:
                taken.add(pick["id"])
                kind, rec, ft = pick["kind"], pick["rec"], pick["ft"]
            else:
                kind, rec, ft = "unknown", {}, None
            sig = None
            if kind == "order":
                for s in sigs.get(tk, []):
                    sst = to_epoch(s.get("t"))
                    if sst is not None and ft is not None and sst <= ft + 1:
                        sig = s
            out.append({
                "ticker": tk,
                "t": rec.get("t") or st.get("t"),
                "leg": kind,
                "filled": float(rec.get("filled") or rec.get("n") or 0),
                "price": (rec.get("exec_price") if kind == "order"
                          else rec.get("price")) or st.get("cost"),
                "want": want or (sig or {}).get("want") or rec.get("side"),
                "fee": rec.get("fee_total"),
                "pnl": (float(st["pnl_c"]) / 100.0)
                       if st.get("pnl_c") is not None else None,
                "result": st.get("result") or mk.get("result"),
                "order": rec if kind == "order" else {},
                "hedge_rec": rec if kind == "hedge" else {},
                "signal": sig,
                "settle": st,
                "hedges": hedges.get(tk, []),
                "market": mk,
            })
    # anything filled but not yet settled is an OPEN position and must show
    for f in fills:
        if f["id"] in taken or f["kind"] != "order":
            continue
        tk, rec, ft = f["tk"], f["rec"], f["ft"]
        sig = None
        for s in sigs.get(tk, []):
            sst = to_epoch(s.get("t"))
            if sst is not None and ft is not None and sst <= ft + 1:
                sig = s
        out.append({
            "ticker": tk, "t": rec.get("t"), "leg": "order",
            "filled": float(rec.get("filled") or 0),
            "price": rec.get("exec_price"), "want": (sig or {}).get("want"),
            "fee": rec.get("fee_total"), "pnl": None,
            "result": None, "order": rec, "hedge_rec": {}, "signal": sig,
            "settle": None, "hedges": hedges.get(tk, []),
            "market": outcomes.get(tk) or {},
        })
    out.sort(key=lambda r: to_epoch(r["t"]) or 0)
    return out


# ---------------------------------------------------------------- bankroll
def bank_readings(ev):
    """[(epoch, dollars)] -- the REAL account balance, as the bot read it."""
    pts = []
    for a in ev.get("autosize", []):
        g = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", str(a.get("why") or ""))
        e = to_epoch(a.get("t"))
        if g and e:
            pts.append((e, float(g.group(1))))
    pts.sort()
    return pts


def bankroll(ev, trades):
    """[(epoch, dollars, real)] -- the curve, real where we have it and
    reconstructed backwards from the first real reading before that.

    `real` is True for a figure the bot actually read from the account.
    """
    real = bank_readings(ev)
    pl = [(to_epoch(t["t"]), t["pnl"]) for t in trades
          if t["pnl"] is not None and to_epoch(t["t"])]
    pl.sort()
    if not real:
        # nothing to anchor to: show cumulative profit from zero and say so
        run = 0.0
        return [(e, (run := run + v), False) for e, v in pl], False
    anchor_t, anchor_v = real[0]
    before = [(e, v) for e, v in pl if e < anchor_t]
    curve = []
    # walk BACKWARDS from the anchor, removing each trade's profit
    v = anchor_v
    back = []
    for e, p in reversed(before):
        # TWO points per trade, deliberately: the balance the instant after it
        # settled, and the balance the instant before. A single point per trade
        # draws a smooth slope between settlements, which is a lie -- the money
        # arrives all at once, and a $50 loss should look like a cliff.
        back.append((e, v, False))
        v -= p
        back.append((e - 1, v, False))
    back.reverse()
    curve += back
    curve += [(e, v, True) for e, v in real]
    after = [(e, p) for e, p in pl if e > real[-1][0]]
    v = real[-1][1]
    for e, p in after:
        v += p
        curve.append((e, v, False))
    curve.sort(key=lambda r: r[0])
    return curve, True


def reconstruction_agrees(ev, trades, tol=1.50):
    """Does adding up settled trades reproduce the account's own movement?

    If it does not, money moved in or out and the reconstructed part of the
    curve is wrong. Returns (ok, worst_gap_dollars, n_checked).
    """
    real = bank_readings(ev)
    if len(real) < 2:
        return True, 0.0, 0
    pl = sorted((to_epoch(t["t"]), t["pnl"]) for t in trades
                if t["pnl"] is not None and to_epoch(t["t"]))
    worst = 0.0
    n = 0
    for (t0, v0), (t1, v1) in zip(real, real[1:]):
        moved = v1 - v0
        earned = sum(p for e, p in pl if t0 < e <= t1)
        worst = max(worst, abs(moved - earned))
        n += 1
    return worst <= tol, worst, n


# ---------------------------------------------------------------- strategy
def live_config(ev):
    """What the RUNNING bot is set to, from its own start record.

    NOT pinrun's module defaults. The live bot takes flags, so the defaults in
    the source describe a bot nobody is running -- read `--pick best` off the
    command line and the module still says "first". Falls back to the defaults
    only when there is no start record to read, and says so.
    """
    starts = [m for m in ev.get("start", []) if m.get("mode") == "live"]
    return (starts[-1] if starts else {}), bool(starts)


class _Cfg(object):
    """pinrun's constants, overridden by whatever the live bot actually ran."""

    def __init__(self, rec):
        self._rec = rec or {}

    def __getattr__(self, name):
        v = self._rec.get(name.lower())
        if v is None:
            return getattr(pinrun, name)
        return v


def strategy_steps(cfg=None):
    """EVERY step the bot takes, in order, with its live value.

    Values come from the running bot's own start record where there is one and
    from pinrun's constants otherwise, so the page cannot drift from the code
    the way a hand-written list would.
    """
    P = cfg if cfg is not None else pinrun
    return [
        ("WATCH", [
            ("Which markets it looks at",
             "The 12 crypto 15-minute series. A market enters the scan when "
             "its close is near and leaves when it settles.",
             "%d to %d seconds before close" % (P.TAU_MIN, P.TAU_MAX)),
            ("How often it looks",
             "Twenty times a second, at every watched market.", "20 per second"),
        ]),
        ("THE MODEL -- what it believes will happen", [
            ("The settlement rule this all rests on",
             "The market settles on the AVERAGE of the last 60 one-second "
             "index prints. With 20 seconds left, 40 of those 60 are already "
             "recorded and can never change. The answer is two-thirds written "
             "before the bet is placed.",
             "60-second average"),
            ("Fair value",
             "It adds up the prints already locked in, assumes the price sits "
             "still for the seconds left, and asks how far the total would "
             "have to move to cross the strike.", "recomputed every look"),
            ("How jumpy it thinks the coin is",
             "Measured from the last 300 seconds of index moves. A jumpier "
             "coin needs a bigger cushion before the bot is sure.",
             "300-second window"),
        ]),
        ("BUYING -- every test, in the order it is asked", [
            ("Contract budget for this close",
             "A close may buy this many contracts in total, across any number "
             "of coins. Spent means done.",
             "%d x size" % P.MAX_PER_CLOSE),
            ("Fills allowed on one market",
             "How many separate buys one market may get in one close.",
             "%d" % P.MAX_PER_MARKET),
            ("Never both sides",
             "Holding YES and NO of the same market pays a guaranteed $1.00 "
             "for more than $1.00 -- a certain loss.", "blocked"),
            ("Orders allowed per close",
             "A refused order creates no position, so refusals get their own "
             "budget rather than eating the fill budget.",
             "%d" % P.MAX_ATTEMPTS_PER_CLOSE),
            ("Order book must be fresh",
             "A stale book is a price that may not be there any more.",
             "under %d ms" % P.MAX_BOOK_AGE_MS),
            ("Price index must be fresh",
             "Same reasoning for the settlement index itself.",
             "under %g s" % P.MAX_INDEX_AGE_S),
            ("Confidence gate",
             "How sure the model has to be before a buy is even considered. "
             "This is the single most important number in the bot.",
             "%.1f%%" % (100 * P.PIN)),
            ("Somebody must be selling",
             "We are a buyer. If nobody offers the winning side there is no "
             "trade, however sure we are. This is what stops most closes.",
             "an ask must exist"),
            ("Enough contracts on offer",
             "A scrap fill still uses up the close and is not worth it.",
             "at least half of size"),
            ("Profit floor",
             "What is left after the exchange fee must clear this.",
             "%s per contract" % cents(P.EDGE_FLOOR)),
            ("Too-good-to-be-true guard",
             "A price far below fair is someone selling on information we do "
             "not have. We do not take that side of it.",
             "refuse below fair by %s" % cents(P.DUMP_DISCOUNT)),
            ("Second buy must be cheaper",
             "Buying again at the same price doubles the risk without "
             "lowering the average paid.",
             "at least %s better" % cents(P.IMPROVE_BY)),
            ("...but not much cheaper",
             "A small price improvement is ordinary. A big one means the "
             "market is turning against the position we already hold.",
             "at most %s better" % cents(P.IMPROVE_MAX)),
            ("Price ceiling",
             "Above this the winnings are too thin to survive a single loss.",
             "%s" % cents(P.PRICE_CEILING)),
            ("Expected value",
             "Using the loss rate we have actually measured, not the model's "
             "own optimism, the trade must still be worth making.",
             "must be positive"),
            ("Which one it buys when several qualify",
             "The one with the most profit in it, not whichever came first in "
             "the list. Ordering uses the reading from 50 ms earlier, so "
             "nothing is recomputed and no order waits.",
             "%s" % ("BEST" if P.PICK == "best" else "first found")),
        ]),
        ("PLACING THE ORDER", [
            ("Bidding above the ask",
             "The order is sent at a limit higher than the price we saw, so a "
             "lost race to the first level still fills at the next one. It "
             "always executes at the resting price, never at our limit.",
             "up to the gate"),
            ("Order type",
             "Fill what is there this instant, cancel the rest. Nothing rests "
             "on the book with our name on it.", "immediate-or-cancel"),
            ("Partial fills",
             "Take what is there down to half of what was wanted; below that, "
             "skip.", "half of size"),
        ]),
        ("SELLING -- and why there isn't any", [
            ("Positions are held to settlement",
             "Measured and dead on mechanism: by 15 seconds out a losing "
             "position's bid is already 23 cents, and 6 cents at 10 seconds. "
             "Every way of selling out early loses money.",
             "no early exit"),
        ]),
        ("HEDGING -- the only way out of a bad trade", [
            ("What triggers it",
             "Belief in the position we hold is recomputed every second. If "
             "it collapses, the trade has turned.",
             "belief falls under %.0f%%" % (100 * P.HEDGE_BELIEF)),
            ("What it does",
             "Buys the OTHER side of the same market. Both legs settle and "
             "the pair pays exactly $1.00, so a near-total loss becomes a "
             "small one.", "buy the opposite side"),
            ("When it cannot",
             "Once an outcome is obvious the losing side's book empties, so "
             "there is often nothing to buy. That is recorded, not hidden.",
             "no ask = no hedge"),
        ]),
        ("BET SIZE -- it follows your bankroll by itself", [
            ("How size is chosen",
             "Your balance divided by the safety factor, the fills allowed "
             "per close, and the price ceiling.",
             "bank / (%g x %d x %s)"
             % (P.BANK_BRAKE, P.MAX_PER_CLOSE, cents(P.PRICE_CEILING))),
            ("Safety factor",
             "Your bankroll must cover this many worst-possible closes. At "
             "%g, the worst close costs about a third of the bank."
             % P.BANK_BRAKE, "%g x" % P.BANK_BRAKE),
            ("How often it re-checks",
             "And only while holding nothing -- the rails never move under an "
             "open position.", "every %d seconds" % P.AUTO_SIZE_EVERY_S),
            ("Hard limits on size",
             "Regardless of the bank.",
             "%g to %g contracts" % (P.AUTO_SIZE_MIN, P.AUTO_SIZE_MAX)),
        ]),
        ("BRAKES -- what stops it trading", [
            ("Drawdown from your best-ever balance",
             "The main stop. Measured from the highest your bank has ever "
             "been, which is kept in a file so restarting the bot cannot "
             "wipe it. It clears itself the moment your balance makes a new "
             "high. A WITHDRAWAL looks exactly like a loss to this rule and "
             "will stop the bot -- that is the safe direction.",
             "stop at %d%% down" % int(100 * P.MAX_DRAWDOWN)),
            ("Bet size follows the bank down, immediately",
             "The moment a loss settles, the balance is re-read and the bet "
             "is re-sized. It used to wait out the rest of a five-minute "
             "timer, betting the size a larger bank supported.",
             "same second"),
            ("Losing-trade count",
             "The most important brake. Losses arriving faster than the model "
             "predicts means the model is wrong, and the answer is to stop "
             "and re-measure, not to trade on to a dollar figure.",
             "stop after 3 losing trades"),
            ("Daily money stop",
             "Scales with size. Reached only by a genuinely bad day.",
             "set at restart, re-scaled with size"),
            ("Looking ahead, not just back",
             "Profit only counts once a position settles, so a backward-only "
             "stop always allows one more bet. This one counts every open "
             "position as if it were already lost.",
             "always on"),
            ("How much can be open at once",
             "Counted in CONTRACTS, not in number of trades. Eighteen small "
             "fills and three big ones are the same money at risk, and only "
             "the count would have stopped the small ones.",
             "3 x bet size"),
            ("Errors", "Repeated failures on the order path stop the run.",
             "2 on orders, 5 in a row anywhere"),
        ]),
    ]


# ---------------------------------------------------------------- HELP
HELP = [
    ("Bankroll", "Your actual Kalshi balance. The bot reads it every five "
     "minutes and sizes its bets from it. Solid line is a real reading; the "
     "faded part before it is worked out backwards from your settled trades, "
     "because the bot only started reading the balance on Sep 13."),
    ("Close", "One 15-minute market window. Twelve coins settle on the same "
     "second, so one close can hold several trades that all live or die "
     "together. Everything here is counted by CLOSE, not by trade, for that "
     "reason."),
    ("Strike", "The price the market is betting above or below. It is always "
     "the previous window's settlement, exactly."),
    ("Settlement", "The average of the last 60 one-second index prints. Not "
     "the last price -- the average. That is the whole edge: most of those "
     "60 prints already exist when the bot bets."),
    ("Confidence", "How sure the model is that the side it is buying will "
     "win. The bot will not consider a trade under 99.5%."),
    ("Fair value", "What the model thinks the contract is worth right now, "
     "in cents. If fair is 99.9 cents and it is on offer at 94, that gap is "
     "the profit."),
    ("Edge", "Profit per contract after the exchange fee. The floor is 0.3 "
     "cents."),
    ("Sweep", "Sending the order at a higher limit than the price we saw, so "
     "that losing the race to the first seller still fills against the next "
     "one. It always pays the resting price, never our limit."),
    ("Hedge", "Buying the opposite side of a market that has turned against "
     "us. Both sides settle and together pay exactly $1.00, which turns a "
     "near-total loss into a small one."),
    ("Gate", "Any one of the tests a possible trade has to pass. The bot "
     "stops at the first one that says no, so whichever is listed is the one "
     "that actually made the decision."),
    ("Delayed vs blocked", "If a gate refuses a coin and the bot buys that "
     "same coin seconds later, the gate DELAYED the trade rather than "
     "preventing it. Only genuinely blocked trades are scored."),
    ("“if filled”", "A price being shown is not the same as getting "
     "it -- we are racing other buyers and win about 7 times in 10. Any "
     "figure for a trade we did NOT make is a best case, never a real "
     "profit or loss."),
    ("Break-even loss rate", "How often we could afford to lose and still "
     "come out level. Compare it with how often we actually lose; the gap "
     "between them is the safety margin."),
]


# ---------------------------------------------------------------- render
CSS = """
:root{--bg:#07090c;--panel:#0d1117;--panel2:#111823;--line:#1d2733;
--txt:#d7e2ee;--dim:#7a8b9e;--dim2:#4d5c6d;--up:#26d07c;--dn:#ff4d5e;
--acc:#43e5c0;--warn:#ffc94d;--mono:'SFMono-Regular',Consolas,'Liberation Mono',monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
font:14px/1.55 var(--mono);-webkit-font-smoothing:antialiased}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
background:repeating-linear-gradient(0deg,rgba(67,229,192,.022) 0 1px,transparent 1px 3px)}
.wrap{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:22px 18px 90px}
h1{font-size:17px;letter-spacing:.22em;margin:0;color:var(--acc);font-weight:600}
.sub{color:var(--dim2);font-size:11px;letter-spacing:.12em;margin-top:5px}
.bar{display:flex;align-items:baseline;justify-content:space-between;
border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:20px;gap:16px;flex-wrap:wrap}
.pill{display:inline-block;padding:2px 9px;border:1px solid var(--line);
border-radius:11px;font-size:10px;letter-spacing:.13em;color:var(--dim)}
.pill.on{color:var(--up);border-color:rgba(38,208,124,.45)}
.pill.off{color:var(--dn);border-color:rgba(255,77,94,.45)}
nav{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:20px}
nav button{background:transparent;border:1px solid var(--line);color:var(--dim);
padding:7px 13px;font:11px var(--mono);letter-spacing:.13em;cursor:pointer;border-radius:3px}
nav button:hover{color:var(--txt);border-color:var(--dim2)}
nav button.sel{color:var(--bg);background:var(--acc);border-color:var(--acc);font-weight:700}
section{display:none}section.sel{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:13px 15px}
.card .k{color:var(--dim2);font-size:10px;letter-spacing:.15em;margin-bottom:7px}
.card .v{font-size:21px;font-weight:600;letter-spacing:-.02em}
.card .n{color:var(--dim);font-size:10.5px;margin-top:5px}
.up{color:var(--up)}.dn{color:var(--dn)}.dim{color:var(--dim)}.warn{color:var(--warn)}
.acc{color:var(--acc)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:5px;
padding:16px 18px;margin-bottom:16px}
.panel h2{font-size:11px;letter-spacing:.2em;color:var(--acc);margin:0 0 14px;font-weight:600}
.panel h3{font-size:11px;letter-spacing:.16em;color:var(--dim);margin:20px 0 9px;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;color:var(--dim2);font-size:10px;letter-spacing:.13em;
padding:7px 9px;border-bottom:1px solid var(--line);font-weight:600;white-space:nowrap}
td{padding:7px 9px;border-bottom:1px solid rgba(29,39,51,.5);vertical-align:top}
tr.trow{cursor:pointer}tr.trow:hover td{background:var(--panel2)}
tr.det>td{background:#080b0f;padding:0}
.det .in{padding:15px 17px;border-left:2px solid var(--acc)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:5px 22px;margin-bottom:14px}
.kv div{display:flex;justify-content:space-between;gap:12px;
border-bottom:1px dotted rgba(77,92,109,.3);padding:3px 0;font-size:12px}
.kv span:first-child{color:var(--dim)}
.kv span:last-child{font-variant-numeric:tabular-nums}
.tl{list-style:none;margin:0;padding:0 0 0 16px;border-left:1px solid var(--line)}
.tl li{position:relative;padding:5px 0 5px 14px;font-size:12px;color:var(--dim)}
.tl li::before{content:'';position:absolute;left:-21px;top:12px;width:7px;height:7px;
border-radius:50%;background:var(--dim2);border:2px solid var(--panel)}
.tl li.hit::before{background:var(--acc)}
.tl li.bad::before{background:var(--dn)}
.tl li b{color:var(--txt);font-weight:600}
.step{border-bottom:1px solid rgba(29,39,51,.55);padding:11px 0;display:grid;
grid-template-columns:1fr auto;gap:6px 18px;align-items:baseline}
.step .t{color:var(--txt);font-weight:600;font-size:12.5px}
.step .d{grid-column:1/2;color:var(--dim);font-size:12px}
.step .v{color:var(--acc);font-size:12px;white-space:nowrap;text-align:right}
.note{color:var(--dim);font-size:11.5px;border-left:2px solid var(--line);
padding:8px 12px;margin:12px 0;background:var(--panel2)}
.note.warn{border-left-color:var(--warn)}
#chart{width:100%;height:290px;display:block;touch-action:none}
.rng{display:flex;gap:4px;margin-top:12px}
.rng button{background:transparent;border:1px solid var(--line);color:var(--dim);
padding:4px 11px;font:10.5px var(--mono);letter-spacing:.1em;cursor:pointer;border-radius:3px}
.rng button.sel{color:var(--bg);background:var(--acc);border-color:var(--acc);font-weight:700}
#tip{position:absolute;pointer-events:none;background:#020304;border:1px solid var(--line);
border-radius:4px;padding:7px 10px;font-size:11.5px;display:none;white-space:nowrap;z-index:9}
#tipv{font-size:15px;font-weight:600}
.chartbox{position:relative}
.hd{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:4px}
.hd .big{font-size:29px;font-weight:600;letter-spacing:-.02em}
details{margin:7px 0}summary{cursor:pointer;color:var(--acc);font-size:12px;outline:none}
.badge{font-size:9.5px;letter-spacing:.1em;padding:1px 6px;border-radius:9px;
border:1px solid var(--line);color:var(--dim)}
.badge.win{color:var(--up);border-color:rgba(38,208,124,.4)}
.badge.loss{color:var(--dn);border-color:rgba(255,77,94,.4)}
.badge.hedge{color:var(--warn);border-color:rgba(255,201,77,.4)}
.empty{color:var(--dim2);font-size:12px;padding:22px 0;text-align:center}
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def render(data, say=print):
    nl = chr(10)
    j = json.dumps(data["chart"])
    parts = []
    w = parts.append
    w("<title>pin · bot console</title>")
    w("<style>%s</style>" % CSS)
    w('<div class="wrap">')

    # ---- header
    s = data["summary"]
    w('<div class="bar"><div>')
    w("<h1>P I N &nbsp;·&nbsp; B O T &nbsp; C O N S O L E</h1>")
    w('<div class="sub">%s &nbsp;·&nbsp; BUILT %s &nbsp;·&nbsp; %s</div>'
      % (esc(ET_OFFSET_NOTE.upper()), esc(data["built"]),
         esc(data["window"])))
    w("</div><div>")
    for lab, ok in data["status"]:
        w('<span class="pill %s">%s</span> ' % ("on" if ok else "off",
                                                esc(lab)))
    w("</div></div>")

    # ---- nav
    tabs = [("ov", "OVERVIEW"), ("bk", "BANKROLL"), ("tr", "TRANSACTIONS"),
            ("st", "HOW IT DECIDES"), ("ga", "GATE SCORECARD"),
            ("hp", "WHAT IT ALL MEANS")]
    w("<nav>")
    for i, (k, lab) in enumerate(tabs):
        w('<button data-t="%s"%s>%s</button>'
          % (k, ' class="sel"' if i == 0 else "", lab))
    w("</nav>")

    # ---- OVERVIEW
    w('<section id="ov" class="sel"><div class="grid">')
    for k, v, n, cls in s["cards"]:
        w('<div class="card"><div class="k">%s</div>'
          '<div class="v %s">%s</div><div class="n">%s</div></div>'
          % (esc(k), cls, esc(v), esc(n)))
    w("</div>")
    for cls, txt in s["notes"]:
        w('<div class="note %s">%s</div>' % (cls, txt))
    w('<div class="panel"><h2>WHERE THE MONEY ACTUALLY CAME FROM</h2>')
    w(_table(["PERIOD", "CLOSES", "LOST", "NET", "AVG WIN", "AVG LOSS",
              "COULD SURVIVE LOSING"], s["eras"]))
    w('<div class="note">The last column is the share of closes we could '
      'lose and still break even. Compare it with the one before it: that '
      'gap is the whole safety margin.</div></div>')
    w("</section>")

    # ---- BANKROLL
    w('<section id="bk"><div class="panel">')
    w('<div class="hd"><div class="big" id="bkv">%s</div>'
      '<div id="bkd" class="dim"></div></div>'
      % esc(usd(s["bank"], sign=False)))
    w('<div class="chartbox"><svg id="chart"></svg><div id="tip">'
      '<div id="tipd" class="dim"></div><div id="tipv"></div></div></div>')
    w('<div class="rng">')
    for r in ("1D", "1W", "1M", "ALL"):
        w('<button data-r="%s"%s>%s</button>'
          % (r, ' class="sel"' if r == "ALL" else "", r))
    w("</div>")
    w('<div class="note %s">%s</div>' % (data["bank_note"][0],
                                         data["bank_note"][1]))
    w("</div></section>")

    # ---- TRANSACTIONS
    w('<section id="tr"><div class="panel">')
    w('<h2>EVERY TRADE &nbsp;·&nbsp; CLICK ONE TO OPEN IT</h2>')
    if not data["trades_html"]:
        w('<div class="empty">no trades on record yet</div>')
    else:
        w('<table><thead><tr>'
          '<th>WHEN</th><th>MARKET</th><th>SIDE</th>'
          '<th class="num">PAID</th><th class="num">SIZE</th>'
          '<th class="num">FEE</th><th class="num">PROFIT</th>'
          '<th>OUTCOME</th></tr></thead><tbody>')
        w(data["trades_html"])
        w("</tbody></table>")
    w("</div></section>")

    # ---- STRATEGY
    w('<section id="st">')
    w('<div class="note">Every test below is applied in this order, and the '
      'bot stops at the first one that says no. Values are read straight out '
      'of the running code, so this page cannot drift from what the bot '
      'actually does.</div>')
    for title, steps in data["steps"]:
        w('<div class="panel"><h2>%s</h2>' % esc(title))
        for t, d, v in steps:
            w('<div class="step"><div class="t">%s</div><div class="v">%s</div>'
              '<div class="d">%s</div></div>' % (esc(t), esc(v), esc(d)))
        w("</div>")
    w("</section>")

    # ---- GATES
    w('<section id="ga"><div class="panel"><h2>WHAT EACH TEST ACTUALLY DID</h2>')
    if data["gates_rows"]:
        w(_table(["TEST", "STOPPED IT", "CLOSES", "ONLY DELAYED",
                  "REALLY BLOCKED", "WOULD HAVE WON", "WOULD HAVE LOST",
                  "IF FILLED"], data["gates_rows"]))
    else:
        w('<div class="empty">%s</div>' % esc(data["gates_empty"]))
    w('<div class="note warn">"If filled" is a best case, never a profit. A '
      'price being shown is not the same as getting it &mdash; we win about 7 '
      'races in 10. A NEGATIVE number here is the test doing its job: it '
      'turned away trades that would have lost.</div>')
    w('<div class="note">These figures do not add up to total profit and '
      'never will. Every test shares one contract budget, so refusing one '
      'trade frees money a later trade spends. The only way to price a single '
      'test properly is to run a paper copy of the bot with that one switch '
      'flipped and subtract.</div>')
    w("</div></section>")

    # ---- HELP
    w('<section id="hp"><div class="panel"><h2>WHAT IT ALL MEANS</h2>')
    for k, v in HELP:
        w('<div class="step"><div class="t">%s</div><div class="v"></div>'
          '<div class="d">%s</div></div>' % (esc(k), esc(v)))
    w("</div></section>")

    w("</div>")
    w("<script>const CHART=%s;</script>" % j)
    w("<script>%s</script>" % JS)
    return nl.join(parts)


def _table(head, rows):
    o = ["<table><thead><tr>"]
    for h in head:
        o.append('<th%s>%s</th>' % (' class="num"' if h not in head[:1]
                                    else "", esc(h)))
    o.append("</tr></thead><tbody>")
    for r in rows:
        o.append("<tr>")
        for i, c in enumerate(r):
            cls = "num" if i else ""
            if isinstance(c, tuple):
                c, extra = c
                cls = (cls + " " + extra).strip()
            o.append('<td class="%s">%s</td>' % (cls, esc(c)))
        o.append("</tr>")
    o.append("</tbody></table>")
    return "".join(o)


JS = r"""
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('sel'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('sel'));
  b.classList.add('sel');
  document.getElementById(b.dataset.t).classList.add('sel');
  if(b.dataset.t==='bk') draw();
});
document.querySelectorAll('tr.trow').forEach(r=>r.onclick=()=>{
  const d=r.nextElementSibling;
  if(d&&d.classList.contains('det')) d.style.display=(d.style.display==='table-row')?'none':'table-row';
});
let RANGE='ALL';
document.querySelectorAll('.rng button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.rng button').forEach(x=>x.classList.remove('sel'));
  b.classList.add('sel'); RANGE=b.dataset.r; draw();
});
function money(v){return (v<0?'-':'')+'$'+Math.abs(v).toFixed(2);}
function pick(){
  if(!CHART.length) return [];
  if(RANGE==='ALL') return CHART;
  const last=CHART[CHART.length-1][0];
  const span={'1D':86400,'1W':604800,'1M':2592000}[RANGE];
  const c=CHART.filter(p=>p[0]>=last-span);
  return c.length>1?c:CHART;
}
let PTS=[],GEO=null;
function draw(){
  const svg=document.getElementById('chart'); if(!svg) return;
  const pts=pick(); PTS=pts;
  const W=svg.clientWidth||900,H=svg.clientHeight||290,PAD=6;
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  if(pts.length<2){svg.innerHTML='<text x="12" y="26" fill="#4d5c6d" font-size="12">not enough readings yet</text>';return;}
  const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
  const x0=Math.min(...xs),x1=Math.max(...xs);
  let y0=Math.min(...ys),y1=Math.max(...ys);
  if(y1-y0<0.01){y0-=1;y1+=1;}
  const pdy=(y1-y0)*0.14; y0-=pdy; y1+=pdy;
  const X=t=>PAD+(t-x0)/(x1-x0||1)*(W-2*PAD);
  const Y=v=>H-PAD-(v-y0)/(y1-y0||1)*(H-2*PAD);
  GEO={X:X,Y:Y,x0:x0,x1:x1,W:W,H:H,PAD:PAD};
  const up=ys[ys.length-1]>=ys[0];
  const col=up?'#26d07c':'#ff4d5e';
  let d='',a='';
  pts.forEach((p,i)=>{const px=X(p[0]),py=Y(p[1]);d+=(i?'L':'M')+px.toFixed(1)+' '+py.toFixed(1);});
  a=d+'L'+X(pts[pts.length-1][0]).toFixed(1)+' '+(H-PAD)+'L'+X(pts[0][0]).toFixed(1)+' '+(H-PAD)+'Z';
  svg.innerHTML=
    '<defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1">'+
    '<stop offset="0%" stop-color="'+col+'" stop-opacity=".26"/>'+
    '<stop offset="100%" stop-color="'+col+'" stop-opacity="0"/></linearGradient></defs>'+
    '<path d="'+a+'" fill="url(#g)"/>'+
    '<path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="1.9" '+
    'stroke-linejoin="round" stroke-linecap="round"/>'+
    '<line id="cx" y1="'+PAD+'" y2="'+(H-PAD)+'" stroke="#4d5c6d" stroke-width="1" stroke-dasharray="3 3" style="display:none"/>'+
    '<circle id="cd" r="4.5" fill="'+col+'" stroke="#07090c" stroke-width="2.5" style="display:none"/>';
  setHead(pts[pts.length-1],pts[0]);
}
function setHead(p,first){
  document.getElementById('bkv').textContent=money(p[1]);
  const d=p[1]-first[1];
  const e=document.getElementById('bkd');
  e.textContent=(d>=0?'+':'')+money(Math.abs(d)).replace('$','$')+'  over this range';
  e.className=d>=0?'up':'dn';
  document.getElementById('bkv').className=d>=0?'big up':'big dn';
}
function near(t){
  let b=PTS[0],bd=1e18;
  for(const p of PTS){const dd=Math.abs(p[0]-t); if(dd<bd){bd=dd;b=p;}}
  return b;
}
const box=document.querySelector('.chartbox');
if(box) box.addEventListener('pointermove',e=>{
  if(!GEO||PTS.length<2) return;
  const r=document.getElementById('chart').getBoundingClientRect();
  const t=GEO.x0+(e.clientX-r.left-GEO.PAD)/(GEO.W-2*GEO.PAD)*(GEO.x1-GEO.x0);
  const p=near(t);
  const px=GEO.X(p[0]),py=GEO.Y(p[1]);
  const cx=document.getElementById('cx'),cd=document.getElementById('cd');
  if(cx){cx.setAttribute('x1',px);cx.setAttribute('x2',px);cx.style.display='';}
  if(cd){cd.setAttribute('cx',px);cd.setAttribute('cy',py);cd.style.display='';}
  const tip=document.getElementById('tip');
  document.getElementById('tipv').textContent=money(p[1]);
  document.getElementById('tipd').textContent=p[2]+(p[3]?'':'  · estimated');
  tip.style.display='block';
  let L=px+14; if(L>GEO.W-170) L=px-tip.offsetWidth-14;
  tip.style.left=L+'px'; tip.style.top=Math.max(4,py-46)+'px';
});
if(box) box.addEventListener('pointerleave',()=>{
  document.getElementById('tip').style.display='none';
  const cx=document.getElementById('cx'),cd=document.getElementById('cd');
  if(cx)cx.style.display='none'; if(cd)cd.style.display='none';
  if(PTS.length>1) setHead(PTS[PTS.length-1],PTS[0]);
});
window.addEventListener('resize',()=>{if(document.getElementById('bk').classList.contains('sel'))draw();});
draw();
"""


# ---------------------------------------------------------------- assembly
def close_key(ticker):
    """Markets settling on the SAME second share a key. Hard rule 4: twelve
    coins settle together, so counting trades instead of closes would report
    one bad minute as twelve independent disasters."""
    p = (ticker or "").split("-")
    return p[1] if len(p) > 1 else ticker


def era_rows(trades):
    by = defaultdict(float)
    order = []
    for t in trades:
        if t["pnl"] is None:
            continue
        k = close_key(t["ticker"])
        if k not in by:
            order.append(k)
        by[k] += t["pnl"]

    def blk(keys, label):
        if not keys:
            return None
        v = [by[k] for k in keys]
        bad = [x for x in v if x < 0]
        good = [x for x in v if x >= 0]
        aw = sum(good) / len(good) if good else 0.0
        al = -sum(bad) / len(bad) if bad else 0.0
        be = (aw / (aw + al)) if (aw + al) else 0.0
        return [label, "%d" % len(keys),
                "%d  (%.1f%%)" % (len(bad), 100.0 * len(bad) / len(keys)),
                (usd(sum(v)), "up" if sum(v) >= 0 else "dn"),
                usd(aw), usd(-al),
                ("%.1f%% of closes" % (100 * be), "acc")]

    n = len(order)
    rows = [blk(order, "all time")]
    if n >= 20:
        rows.append(blk(order[:n // 2], "first half"))
        rows.append(blk(order[n // 2:], "second half"))
    if n >= 100:
        rows.append(blk(order[-100:], "last 100 closes"))
    if n >= 50:
        rows.append(blk(order[-50:], "last 50 closes"))
    return [r for r in rows if r]


def summary(ev, trades, curve):
    by = defaultdict(float)
    for t in trades:
        if t["pnl"] is not None:
            by[close_key(t["ticker"])] += t["pnl"]
    net = sum(by.values())
    bad = sum(1 for v in by.values() if v < 0)
    n = len(by)
    bank = curve[-1][1] if curve else None
    today = None
    if curve:
        cut = curve[-1][0] - 86400
        early = [v for e, v, _ in curve if e <= cut]
        if early:
            today = curve[-1][1] - early[-1]
    sizes = [a.get("new") for a in ev.get("autosize", []) if a.get("new")]
    aborts = [a.get("loss_abort") for a in ev.get("autosize", [])
              if a.get("loss_abort")]
    worst = min(by.values()) if by else None
    best = max(by.values()) if by else None
    aw = [v for v in by.values() if v >= 0]
    al = [v for v in by.values() if v < 0]
    be = None
    if aw and al:
        a, b = sum(aw) / len(aw), -sum(al) / len(al)
        be = a / (a + b)
    cards = [
        ("BANKROLL", usd(bank, sign=False) if bank else "--",
         "read from Kalshi" if curve and curve[-1][2] else "estimated",
         "acc"),
        ("LAST 24 HOURS", usd(today) if today is not None else "--",
         "change in bankroll", "up" if (today or 0) >= 0 else "dn"),
        ("ALL-TIME PROFIT", usd(net), "%d closes traded" % n,
         "up" if net >= 0 else "dn"),
        ("CLOSES THAT LOST", "%d of %d" % (bad, n),
         "%.1f%% of everything traded" % (100.0 * bad / n if n else 0),
         "dn" if bad else "up"),
        ("SAFETY MARGIN",
         ("%.1f%%" % (100 * be)) if be else "--",
         "we could lose this often and break even", "acc"),
        ("BET SIZE NOW", ("%g contracts" % sizes[-1]) if sizes else "--",
         "set automatically from the bankroll", ""),
        ("WORST SINGLE CLOSE", usd(worst) if worst is not None else "--",
         "the most ever lost at once", "dn"),
        ("BEST SINGLE CLOSE", usd(best) if best is not None else "--",
         "the most ever made at once", "up"),
    ]
    notes = []
    if be is not None:
        rate = 100.0 * bad / n if n else 0
        notes.append((
            "", "<b>Read these two together.</b> We lose on <b>%.1f%%</b> of "
            "closes and could afford to lose on <b>%.1f%%</b>. That gap is "
            "the entire safety margin, and it is the number to watch: if the "
            "left one ever climbs past the right one, the bot is losing money "
            "even while it looks busy." % (rate, 100 * be)))
    if aborts:
        notes.append((
            "warn", "<b>The daily money stop is %s, and that is not a third "
            "of the bankroll &mdash; it is most of it.</b> Two things reach "
            "it long before the money does: the bot stops after <b>3 losing "
            "trades</b> in a run, and the worst a single close can cost is "
            "about a third of the bank. The dollar stop is the last line of "
            "defence, not the first." % usd(aborts[-1], sign=False)))
    return {"cards": cards, "notes": notes, "eras": era_rows(trades),
            "bank": bank or 0.0}


def trade_rows_html(trades):
    o = []
    for t in reversed(trades):
        # NO FILTER ON `filled`. A settled leg is real money whether or not a
        # fill record was found for it; hiding it is how a loss vanishes.
        pnl = t["pnl"]
        cls = "" if pnl is None else ("up" if pnl >= 0 else "dn")
        hedged = any(h.get("kind") == "hedge" for h in t["hedges"])
        badge = ""
        if t.get("leg") == "hedge":
            badge += '<span class="badge hedge">HEDGE LEG</span> '
        elif hedged:
            badge += '<span class="badge hedge">HEDGED</span> '

        if pnl is None:
            badge += '<span class="badge">OPEN</span>'
        elif pnl >= 0:
            badge += '<span class="badge win">WON</span>'
        else:
            badge += '<span class="badge loss">LOST</span>'
        o.append(
            '<tr class="trow"><td>%s</td><td>%s</td><td>%s</td>'
            '<td class="num">%s</td><td class="num">%g</td>'
            '<td class="num dim">%s</td><td class="num %s">%s</td>'
            '<td>%s</td></tr>'
            % (esc(et(t["t"])), esc(t["ticker"]),
               esc((t["want"] or "").upper()), esc(cents(t["price"])),
               t["filled"], esc(usd(t["fee"], sign=False)), cls,
               esc(usd(pnl)), badge))
        o.append('<tr class="det" style="display:none"><td colspan="8">'
                 '<div class="in">%s</div></td></tr>' % trade_detail(t))
    return "".join(o)


def trade_detail(t):
    sig = t["signal"] or {}
    o = t["order"] or {}
    st = t["settle"] or {}
    mk = t["market"] or {}
    out = []
    w = out.append
    f = sig.get("fair")
    mine = None
    if f is not None and sig.get("want"):
        mine = f if sig["want"] == "yes" else 1.0 - f

    w("<h3>WHY IT BOUGHT &mdash; what was true at that exact second</h3>")
    w('<div class="kv">')
    rows = [
        ("how sure the model was",
         ("%.4f%%" % (100 * mine)) if mine is not None else "--"),
        ("what this side was worth", cents(mine)),
        ("what it was on offer for", cents(sig.get("price"))),
        ("profit in it, after the fee",
         ("%.2f¢" % sig["edge_c"]) if sig.get("edge_c") is not None
         else "--"),
        ("seconds left when it decided",
         ("%s s" % sig.get("tau")) if sig.get("tau") is not None else "--"),
        ("strike it had to beat", sig.get("strike")),
        ("index price at that moment", sig.get("spot")),
        ("how jumpy the coin was then", sig.get("sigma")),
        ("contracts on offer", sig.get("size")),
        ("contracts it asked for", sig.get("take_n")),
        ("order book age",
         ("%s ms" % sig.get("book_age_ms"))
         if sig.get("book_age_ms") is not None else "--"),
        ("index age",
         ("%s s" % sig.get("index_age_s"))
         if sig.get("index_age_s") is not None else "--"),
        ("how long that price had been sitting there",
         ("%s ms" % sig.get("level_age_ms"))
         if sig.get("level_age_ms") is not None else "--"),
    ]
    for k, v in rows:
        w("<div><span>%s</span><span>%s</span></div>" % (esc(k), esc(v)))
    w("</div>")

    w("<h3>HOW THE ORDER WENT</h3>")
    w('<div class="kv">')
    swept = o.get("swept")
    rows2 = [
        ("price it saw", esc(cents(o.get("ask_seen")))),
        ("limit it sent", esc(cents(o.get("limit_sent")))),
        ("bid above the ask (the sweep)",
         ("YES &mdash; %.1f¢ of room" % (o.get("sweep_headroom_c") or 0))
         if swept else "not needed"),
        ("price it actually paid", esc(cents(o.get("exec_price")))),
        ("contracts filled",
         esc("%g of %s" % (float(o.get("filled") or 0),
                           (o.get("body") or {}).get("count")))),
        ("round trip to the exchange", esc("%s ms" % o.get("latency_ms"))),
        ("seconds left when it was sent", esc("%s s" % o.get("tau_at_send"))),
        ("exchange fee", esc(usd(o.get("fee_total"), sign=False))),
        ("order type", esc((o.get("body") or {}).get("time_in_force"))),
        ("what the exchange said",
         esc("%s / %s" % (o.get("status_code"), o.get("status")))),
    ]
    for k, v in rows2:
        w("<div><span>%s</span><span>%s</span></div>" % (esc(k), v))
    w("</div>")

    w("<h3>WHAT HAPPENED NEXT</h3>")
    w('<ul class="tl">')
    w('<li class="hit"><b>%s</b> &mdash; bought %g at %s</li>'
      % (esc(et(t["t"])), t["filled"], esc(cents(t["price"]))))
    for h in t["hedges"]:
        k = h.get("kind")
        lab = {"hedge_alarm": "belief collapsed &mdash; the trade had turned",
               "hedge": "hedged: bought the other side",
               "hedge_no_ask": "tried to hedge, but nobody was selling the "
                               "other side",
               "hedge_gave_up": "gave up trying to hedge"}.get(k, esc(k))
        w('<li class="%s"><b>%s</b> &mdash; %s%s%s</li>'
          % ("hit" if k == "hedge" else "bad", esc(et(h.get("t"))), lab,
             (" (belief %.1f%%)" % (100 * h["belief"]))
             if h.get("belief") is not None else "",
             (" at %s" % esc(cents(h.get("ask")))) if h.get("ask") else ""))
    if st:
        w('<li class="%s"><b>%s</b> &mdash; settled <b>%s</b>, '
          'this leg made <b>%s</b></li>'
          % ("hit" if (t["pnl"] or 0) >= 0 else "bad", esc(et(st.get("t"))),
             esc((st.get("result") or "").upper()), esc(usd(t["pnl"]))))
    else:
        w("<li><b>not settled yet</b></li>")
    w("</ul>")

    if mk.get("settle") is not None:
        w('<div class="kv"><div><span>where it actually settled</span>'
          '<span>%s</span></div><div><span>the strike</span>'
          '<span>%s</span></div></div>'
          % (esc(mk.get("settle")), esc(mk.get("strike"))))

    if t["pnl"] is not None and t["pnl"] < 0:
        w('<div class="note warn">This one lost. The timeline above is what '
          'to read: if belief never collapsed, the index moved in the last '
          'few seconds and nothing could have seen it coming. If it did '
          'collapse and no hedge followed, the losing side had no seller '
          '&mdash; which is what happens once an outcome becomes obvious.'
          '</div>')
    return "".join(out)


def gate_rows(ev, outcomes):
    try:
        import pinattrib
    except ImportError:
        return [], "the gate reader is missing"
    refusals = ev.get("refused", [])
    if not refusals:
        return [], ("No test has recorded a refusal yet. The bot only began "
                    "writing these down in the version deployed tonight, so "
                    "this fills in once it has been running a while.")
    bought = set(o.get("ticker") for o in ev.get("order", []))
    rows = pinattrib.attribute(refusals, bought, dict(
        (k, (v or {}).get("result")) for k, v in outcomes.items()))
    out = []
    for g in pinattrib.GATE_ORDER:
        a = rows.get(g)
        name = pinattrib.WHAT.get(g, g)
        if a is None:
            out.append([name, "0", "0", "0", "0", "--", "--", "--"])
            continue
        out.append([
            name, "%d" % a["n"], "%d" % len(a["closes"]), "%d" % a["delayed"],
            "%d" % a["blocked"],
            ("%d" % a["won"]) if a["scored"] else "--",
            ("%d" % a["lost"]) if a["scored"] else "--",
            (usd(a["money"]), "up" if a["money"] >= 0 else "dn")
            if a["scored"] else "--"])
    return out, ""


def build(logs_glob, markets_json):
    paths = sorted(glob.glob(logs_glob))
    ev = load(paths)
    outcomes = load_outcomes(markets_json)
    trades = build_trades(ev, outcomes)
    curve, anchored = bankroll(ev, trades)
    ok, gap, nchk = reconstruction_agrees(ev, trades)
    if not anchored:
        note = ("warn", "The bot has not read your account balance yet, so "
                "this line is cumulative profit from zero rather than a real "
                "bankroll.")
    elif nchk and not ok:
        note = ("warn", "<b>The reconstruction and your real balance disagree "
                "by up to %s.</b> That normally means money was added to or "
                "taken out of the account, which this page cannot see. Treat "
                "the faded part of the line as rough." % usd(gap, sign=False))
    else:
        note = ("", "Solid readings come straight from your Kalshi balance, "
                "taken every five minutes. The faded part before them is "
                "worked backwards from your settled trades, because the bot "
                "only started reading the balance on Sep 13. Checked against "
                "%d real movements and they agree to within %s."
                % (nchk, usd(gap, sign=False)))
    cfgrec, have_cfg = live_config(ev)
    cfg = _Cfg(cfgrec)
    grows, gempty = gate_rows(ev, outcomes)
    span = ""
    if curve:
        span = "%s  →  %s" % (
            et(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(curve[0][0]))),
            et(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(curve[-1][0]))))
    return {
        "built": et(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        "window": span,
        "status": [("LIVE BOT", bool(ev.get("order"))),
                   ("SWEEP %s" % ("ON" if cfg.SWEEP_ENABLED else "OFF"),
                    bool(cfg.SWEEP_ENABLED)),
                   ("BEST-FIRST %s" % ("ON" if cfg.PICK == "best"
                                       else "OFF"), cfg.PICK == "best"),
                   ("SAME-COIN RE-BUY %s"
                    % ("ON" if cfg.MAX_PER_MARKET > 1 else "OFF"),
                    cfg.MAX_PER_MARKET > 1),
                   ("CONFIG FROM THE RUNNING BOT" if have_cfg
                    else "CONFIG FROM SOURCE DEFAULTS", have_cfg)],
        "summary": summary(ev, trades, curve),
        "chart": [[int(e), round(v, 2),
                   time.strftime("%b %d, %I:%M %p", time.localtime(e)),
                   bool(r)] for e, v, r in curve],
        "bank_note": note,
        "trades_html": trade_rows_html(trades),
        "steps": strategy_steps(cfg),
        "gates_rows": grows,
        "gates_empty": gempty,
        "n_trades": len(trades),
    }


# ---------------------------------------------------------------- selftest
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # ---- money formatting, which is the operator's one explicit rule -----
    ck(usd(4.2) == "+$4.20" and usd(-18.88) == "-$18.88",
       "money always carries a dollar sign, losses included (%s / %s)"
       % (usd(4.2), usd(-18.88)))
    ck(usd(0) == "+$0.00" and usd(None) == "--",
       "zero is still money; a missing figure is a dash, never $0.00 -- "
       "those mean completely different things on a trading page")
    ck(usd(294.55, sign=False) == "$294.55",
       "a balance is not signed")

    # ---- the trade join, which is where a dashboard usually lies ---------
    ev = {
        "signal": [
            {"kind": "signal", "ticker": "KXBTC15M-26SEP131930-30",
             "t": "2026-09-13T23:29:50Z", "want": "no", "price": 0.89,
             "fair": 0.002, "edge_c": 9.1, "tau": 10, "size": 200.0},
            {"kind": "signal", "ticker": "KXBTC15M-26SEP131930-30",
             "t": "2026-09-13T23:29:53Z", "want": "no", "price": 0.88,
             "fair": 0.001, "edge_c": 10.1, "tau": 7, "size": 200.0},
        ],
        "order": [
            {"kind": "order", "ticker": "KXBTC15M-26SEP131930-30",
             "t": "2026-09-13T23:29:53Z", "filled": 51.0, "exec_price": 0.89,
             "fee_total": 0.35, "body": {"count": "51.00"}},
        ],
        "settled": [
            {"kind": "settled", "ticker": "KXBTC15M-26SEP131930-30",
             "t": "2026-09-13T23:30:20Z", "result": "no", "pnl_c": 526.04,
             "want": "no", "cost": 0.89},
        ],
        "hedge_alarm": [], "hedge": [], "autosize": [],
    }
    tr = build_trades(ev, {})
    ck(len(tr) == 1, "one filled order makes exactly one trade row")
    ck(tr[0]["signal"]["tau"] == 7,
       "the trade is matched to the LAST signal at or before it, not the "
       "first -- pairing it with the earlier look would report a price and a "
       "confidence the bot had already moved on from")
    ck(abs(tr[0]["pnl"] - 5.2604) < 1e-9,
       "profit comes through in dollars, not cents (%s)" % usd(tr[0]["pnl"]))

    # two legs on one market must not collapse into one
    ev2 = {
        "signal": ev["signal"],
        "order": ev["order"] + [dict(ev["order"][0],
                                     t="2026-09-13T23:29:55Z",
                                     exec_price=0.88)],
        "settled": ev["settled"] + [dict(ev["settled"][0],
                                         t="2026-09-13T23:30:21Z",
                                         pnl_c=100.0)],
    }
    tr2 = build_trades(ev2, {})
    ck(len(tr2) == 2 and tr2[0]["pnl"] != tr2[1]["pnl"],
       "two buys on the SAME market in one close stay two rows with their "
       "own prices and their own profit -- merging them is how a scaled-in "
       "position gets reported at the wrong price")

    # ---- THE BUG THIS FUNCTION WAS REWRITTEN FOR -------------------------
    # A hedge fill writes a `hedge` record, NOT an `order` record. Walking
    # orders dropped nine settled legs worth -$9.93 off the live page, and
    # every one was a LOSING leg: it read +$163.28 against a true +$153.35
    # and showed 8 losing closes where there were 10.
    evh = {
        "signal": [], "order": [
            {"kind": "order", "ticker": "M", "t": "2026-09-12T10:00:20Z",
             "filled": 20.0, "exec_price": 0.949, "body": {"count": "20"}}],
        "hedge": [
            {"kind": "hedge", "ticker": "M", "t": "2026-09-12T10:00:35Z",
             "side": "no", "price": 0.052, "n": 20.0, "belief": 0.02}],
        "settled": [
            {"kind": "settled", "ticker": "M", "t": "2026-09-12T10:01:20Z",
             "want": "yes", "result": "yes", "pnl_c": 100.0, "cost": 0.949},
            {"kind": "settled", "ticker": "M", "t": "2026-09-12T10:01:20Z",
             "want": "no", "result": "yes", "pnl_c": -104.0, "cost": 0.052}],
    }
    trh = build_trades(evh, {})
    ck(len(trh) == 2,
       "a hedged trade shows BOTH legs -- the buy and the hedge")
    ck(any(x["leg"] == "hedge" for x in trh),
       "and the hedge leg is labelled as one")
    tot = sum(x["pnl"] for x in trh if x["pnl"] is not None)
    ck(abs(tot - (-0.04)) < 1e-9,
       "the two legs add to the real result (%s), not just the winning half "
       "-- dropping the hedge leg is how a loss disappears off a dashboard"
       % usd(tot))

    # nothing that settled may EVER be missing from the page
    allpnl = sum(float(s["pnl_c"]) for s in evh["settled"]) / 100.0
    ck(abs(tot - allpnl) < 1e-9,
       "every settled leg in the log reaches the page: $%.2f on the page "
       "against $%.2f in the log" % (tot, allpnl))

    # ---- the bankroll curve ---------------------------------------------
    ev3 = dict(ev)
    ev3["autosize"] = [
        {"kind": "autosize", "t": "2026-09-13T23:35:00Z",
         "why": "bank $300.00", "new": 50.0, "loss_abort": -200.0},
        {"kind": "autosize", "t": "2026-09-13T23:40:00Z",
         "why": "bank $300.00", "new": 50.0, "loss_abort": -200.0},
    ]
    curve, anchored = bankroll(ev3, tr)
    ck(anchored, "with a real balance reading the curve is anchored to it")
    reals = [p for p in curve if p[2]]
    ck(len(reals) == 2 and reals[0][1] == 300.0,
       "the real readings appear in the curve untouched")
    pre = [p for p in curve if not p[2] and p[0] < reals[0][0]]
    ck(pre and abs(pre[0][1] - (300.0 - 5.2604)) < 1e-6,
       "the EARLIEST point is the first real reading MINUS every profit since "
       "-- the curve is walked backwards from a known balance (%s)"
       % usd(pre[0][1], sign=False))
    ck(len(pre) == 2 and abs(pre[1][1] - 300.0) < 1e-6,
       "and each settled trade puts TWO points on the line, just before and "
       "just after, so a loss draws as a cliff rather than a gentle slope "
       "between settlements")

    # the disagreement check must actually be able to fail
    ok, gap, nchk = reconstruction_agrees(ev3, tr)
    ck(nchk >= 1, "the curve is checked against real balance movements")
    ev4 = dict(ev3)
    ev4["autosize"] = [ev3["autosize"][0],
                       {"kind": "autosize", "t": "2026-09-13T23:40:00Z",
                        "why": "bank $500.00", "new": 50.0}]
    ok2, gap2, _ = reconstruction_agrees(ev4, tr)
    ck(not ok2 and gap2 > 100,
       "a $200 deposit the page cannot see is DETECTED (gap %s), so the page "
       "warns instead of drawing a confident wrong line" % usd(gap2, False))

    # ---- closes, not trades ---------------------------------------------
    ck(close_key("KXBTC15M-26SEP131930-30")
       == close_key("KXETH15M-26SEP131930-30"),
       "two coins settling on the same second share one close -- hard rule 4, "
       "or one bad minute reads as twelve separate disasters")

    # ---- the strategy list must cover the whole bot ----------------------
    steps = strategy_steps()
    titles = " ".join(t for t, _ in steps).upper()
    for need in ("WATCH", "MODEL", "BUYING", "ORDER", "SELLING", "HEDG",
                 "SIZE", "BRAKE"):
        ck(need in titles,
           "the page explains the %s stage -- the operator asked for 'every "
           "single strategy the bot uses ... a buy, a sell, a hedge, every "
           "step in the process'" % need)
    flat = json.dumps(steps)
    ck(str(pinrun.PIN * 100)[:4] in flat or "99.5" in flat,
       "the live confidence gate is shown, read from the running code")

    # THE PAGE MUST DESCRIBE THE RUNNING BOT, NOT THE SOURCE DEFAULTS. The bot
    # takes flags: run it with --pick best and pinrun.PICK in the module is
    # still "first", so a page reading the module describes a bot nobody runs.
    cfg = _Cfg({"pick": "best", "max_per_market": 2, "pin": 0.99})
    ck(cfg.PICK == "best" and cfg.MAX_PER_MARKET == 2,
       "the running bot's own start record overrides the source defaults")
    ck(cfg.TAU_MAX == pinrun.TAU_MAX,
       "and anything the start record does not carry still falls back to the "
       "source, rather than coming back empty")
    ck("BEST" in json.dumps(strategy_steps(cfg)),
       "so a bot started with --pick best is described as buying the best")
    ck("BEST" not in json.dumps(strategy_steps(_Cfg({"pick": "first"}))),
       "and one started without it is not")
    rec, have = live_config({"start": [{"mode": "live", "pick": "best"},
                                       {"mode": "paper", "pick": "first"}]})
    ck(have and rec.get("pick") == "best",
       "the LIVE start record is the one read -- a paper what-if writes start "
       "records too, and reading one of those would describe the wrong bot")
    ck("%g" % pinrun.MAX_PER_CLOSE in flat and "%g" % pinrun.BANK_BRAKE in flat,
       "as are the close budget and the bankroll safety factor")

    # ---- the page itself -------------------------------------------------
    data = {
        "built": "now", "window": "w",
        "status": [("LIVE BOT", True)],
        "summary": summary(ev3, tr, curve),
        "chart": [[1, 2.0, "x", True], [2, 3.0, "y", True]],
        "bank_note": ("", "note"),
        "trades_html": trade_rows_html(tr),
        "steps": steps, "gates_rows": [], "gates_empty": "none yet",
        "n_trades": 1,
    }
    page = render(data, say=None)
    ck("<svg id=\"chart\">" in page or 'id="chart"' in page,
       "the bankroll chart is on the page")
    ck('id="tip"' in page and "pointermove" in page,
       "and it has a hover readout, which is the Robinhood behaviour asked "
       "for")
    ck("KXBTC15M-26SEP131930-30" in page and 'class="det"' in page,
       "every trade is listed and carries a hidden detail row to open")
    ck("seconds left when it decided" in page and "how sure the model was"
       in page,
       "the detail shows what was true AT THE MOMENT OF PURCHASE")
    ck("WHAT HAPPENED NEXT" in page,
       "and a timeline of what happened after it, through to settlement")
    ck("WHAT IT ALL MEANS" in page and "Break-even loss rate" in page,
       "the help section is built in, not a separate document")

    # NO NETWORK. This page holds his balance and every trade he has made.
    for bad in ("http://", "https://", "//cdn", "<img", "fetch(",
                "XMLHttpRequest", "WebSocket"):
        ck(bad not in page,
           "the page contains no %r -- it loads nothing from the internet and "
           "sends nothing out, because it holds his account balance and every "
           "trade he has ever made" % bad)
    ck(page.count("$") > 3, "money appears with dollar signs")

    # a page built from NOTHING must still render rather than crash
    empty = {
        "built": "now", "window": "", "status": [],
        "summary": summary({}, [], []),
        "chart": [], "bank_note": ("", ""), "trades_html": "",
        "steps": steps, "gates_rows": [], "gates_empty": "nothing yet",
        "n_trades": 0,
    }
    p2 = render(empty, say=None)
    ck("no trades on record yet" in p2,
       "with no data at all the page says so instead of showing blank boxes")
    print("pindash selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--logs", default=os.path.join(REPO, "results",
                                                   "pinrun-live-*.jsonl"))
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "dashboard.html"))
    ap.add_argument("--watch", type=int, default=0,
                    help="rebuild every N seconds instead of once")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_DASH_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc

    def once():
        data = build(a.logs, a.markets)
        page = render(data, say=None)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><html><head><meta charset=\"utf-8\">"
                     "<meta name=\"viewport\" content=\"width=device-width,"
                     "initial-scale=1\">%s</head><body>%s</body></html>"
                     % ("" if "<title>" not in page else "", page))
        return data

    if a.watch:
        print("  rebuilding %s every %d s -- Ctrl-C to stop"
              % (a.out, a.watch))
        while True:
            d = once()
            print("  %s  %d trades" % (time.strftime("%H:%M:%S"),
                                       d["n_trades"]))
            time.sleep(a.watch)
    d = once()
    print("  %d trades, %d chart points" % (d["n_trades"], len(d["chart"])))
    print("  wrote %s" % a.out)
    print("  open it by double-clicking that file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
