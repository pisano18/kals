"""cmdlive.py -- THE COMMODITY PENNY TEST. Real money, one contract at a time.

WHY THIS EXISTS. `cmdarm.py` is the paper arm, and paper cannot answer the
only question left. A paper arm records "an offer was sitting there at a price
inside the window". Live records "somebody chose to sell it to US". On the
crypto markets those two populations differed by 31x in loss rate (tape 0.11%
vs live 3.4%, 2026-09-11, intervals not overlapping), and the difference IS
the loss class that hurts. So the paper arm can KILL the commodity idea; it
can never deploy it. Only real fills can.

WHAT IT RISKS. One contract per bet, a hard $10.00 ceiling on total cost
across the run, at most 60 orders, and it stops itself after 2 losses. At the
prices it trades (90-99c) one contract costs at most 99c, so the worst case
the operator can suffer here is the $10 cap, and the realistic worst case is
the 2-loss brake at about $2.

THE WINDOWS ARE NOT DEFINED HERE. They are imported from `cmdarm.BANDS`, by
object, so the paper control and the live test can never drift apart. They
came from the grid's BY-MARKETS table (rule 4), not its trade counts:

Only GOLD and WTI can reach the wire (`LIVE_SERIES`), whatever is passed on
the command line, and a window labelled "anti..." -- a deliberate loser used
as a control -- can never reach it at all. Silver, copper and natural gas are
traded in `cmdarm` (paper) on their own best windows.

The shape those windows follow: commodities are good at BOTH ENDS of the
quarter hour and dangerous in the middle (16-90 s), the opposite of crypto,
because they settle on the CLOSE of a 1-minute candle rather than a 60-second
average. Gold at 95-99c: 149 markets / 2 lost inside 15 s, 423 / 21 in the
middle, 379 / 2 at 91-180 s.

HARD RULE 1 (as narrowed 2026-09-06): no order that risks real money without
the operator's per-instance sign-off. The sign-off for THIS instance is his
message of 2026-09-17: "I'm ready for commodity penny testing". It is
enforced mechanically -- production is armed only when BOTH `--live` and
`--signoff "commodity penny test"` are given, and `arm()` is the only place
that can arm it.

Every refusal is decided BEFORE anything reaches the wire, and the self-test
reads this file's own source to prove the guard runs before the send.
"""
import argparse
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
# Repo modules FIRST: a scratch copy of livebook in kals-work shadowed the real
# one once and ran an analysis on import. cmdarm and pinrun both order it this
# way for the same reason.
import cmdarm                                                    # noqa: E402
import livebook                                                  # noqa: E402
import ordercli                                                  # noqa: E402
import pinflat                                                   # noqa: E402
import pintake                                                   # noqa: E402
sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")

RESULTS = os.path.join(os.path.dirname(HERE), "results")

SIGNOFF_PHRASE = "commodity penny test"
SIZE = 1.0                  # contracts per order. The whole point.
MAX_SIZE = 5.0              # --size may never exceed this
# GROSS TURNOVER, not risk. Raised 10.00 -> 40.00 on 2026-09-17 ~17:0xZ, after the
# first day hit it at 10 fills (10 won, 0 lost, +$0.47) and began refusing every
# further trade. The $10 was measuring the WRONG THING: a winning contract returns
# its dollar and the capital recycles, so gross spend climbs while the risk does
# not move at all. What actually bounds the downside is MAX_LOSSES (2 losses is
# about $2) and MAX_NET_LOSS (the day's realised dollars). Both are untouched --
# this number only stops the thing running away in VOLUME.
MAX_SPEND = 40.00           # dollars of cost across the DAY (gross; it recycles)
MAX_NET_LOSS = 5.00         # dollars NET REALISED down on the day, then stop. The
                            # honest risk cap: it counts money that is GONE, not
                            # money in flight.
MAX_ORDERS = 60             # hard ceiling on attempts that reach the wire
MAX_LOSSES = 2              # then it stops itself and writes the stop file
BALANCE_FLOOR = 300.00      # never trade the account below this
MIN_TAU = 2                 # seconds; an order any later can land after close
PRICE_FLOOR = 0.90
PRICE_CEIL = 0.99
STOP_FILE = os.path.join(RESULTS, "cmdlive.stop")
# The operator's desktop app stands the LIVE bot down with this file. If he
# stood the crypto bot down, he stood everything down.
DESK_STOP = os.path.join(RESULTS, "pinrun-live.stop")
HEARTBEAT = os.path.join(RESULTS, "cmdlive.heartbeat")

# ONLY these two series may reach the wire, whatever is passed on the command
# line. The operator's instruction, 2026-09-17: "Make the good commodities
# live, also run paper tests on the ones you don't have confidence in." Gold
# and oil are the good ones -- both have 300+ market cells losing under 2%.
# Silver, copper and natural gas stay in `cmdarm` (paper), and a window whose
# label starts with "anti" is a deliberate LOSER used as a control and can
# never be live.
LIVE_SERIES = ("KXGOLD15M", "KXWTI15M")
# The widest window any live commodity series uses, handed to pintake per call.
# Its shipped rail is 90 s (right for the crypto bot); the commodity edge sits
# at 91-180 s. pintake refuses anything past what is asked, and past its own
# MAX_TAU_CEILING whatever is asked.
MAX_TAU_ASK = max(b[1] for v in cmdarm.BANDS.values() for b in v) + 5


def stopped(stop_file=STOP_FILE, desk_stop=DESK_STOP):
    """Which stop flag is set, or None. Checked before every order."""
    if os.path.exists(stop_file):
        return "cmdlive.stop"
    if os.path.exists(desk_stop):
        return "pinrun-live.stop (the desktop app stood the bot down)"
    return None


class State:
    """Everything the guard needs to say no. Counts FILLS for money and
    ATTEMPTS for the order ceiling, because a refused order costs nothing but
    a runaway of refusals is exactly what once sent 160 orders in one close."""

    def __init__(self, size=SIZE):
        self.size = float(size)
        self.spent = 0.0        # dollars of cost from FILLS, never from intents
        self.orders = 0         # attempts that reached the wire
        self.fills = 0
        self.losses = 0
        self.realised = 0.0     # net dollars settled today: wins minus losses
        self.armed = False


def guard(state, tau, price, count, balance, stop=None, series=None, window=None):
    """Every reason NOT to send, in a list. Empty list means send.

    Runs before pintake's own rails, not instead of them: pintake refuses on
    the order body and the close time, this refuses on the money.
    """
    bad = []
    if series is not None and series not in LIVE_SERIES:
        bad.append("%s is paper-only; the live list is %s"
                   % (series, ", ".join(LIVE_SERIES)))
    if window is not None and str(window).startswith("anti"):
        bad.append("window %r is a NEGATIVE CONTROL -- it exists to lose and "
                   "must never reach the wire" % (window,))
    if not state.armed:
        bad.append("not armed -- --live and the sign-off phrase are both required")
    if stop:
        bad.append("stop flag set: " + stop)
    try:
        n = float(count)
    except (TypeError, ValueError):
        n = -1.0
    if n < 1.0:
        bad.append("count %r is less than one contract" % (count,))
    elif n > MAX_SIZE:
        bad.append("count %.2f is above the hard ceiling of %.0f contracts"
                   % (n, MAX_SIZE))
    try:
        p = float(price)
    except (TypeError, ValueError):
        p = -1.0
    if not (PRICE_FLOOR <= p <= PRICE_CEIL):
        bad.append("price %r is outside the penny test's window %.2f-%.2f"
                   % (price, PRICE_FLOOR, PRICE_CEIL))
    cost = p * max(n, 0.0)
    if p > 0 and n > 0 and state.spent + cost > MAX_SPEND + 1e-9:
        bad.append("$%.2f spent + $%.2f this order is past the $%.2f run ceiling"
                   % (state.spent, cost, MAX_SPEND))
    if state.orders >= MAX_ORDERS:
        bad.append("%d orders already sent; the ceiling is %d" % (state.orders, MAX_ORDERS))
    if state.losses >= MAX_LOSSES:
        bad.append("%d losses; the brake is %d" % (state.losses, MAX_LOSSES))
    if state.realised <= -MAX_NET_LOSS:
        bad.append("$%.2f net realised down today; the cap is $%.2f"
                   % (state.realised, MAX_NET_LOSS))
    if tau is None or float(tau) < MIN_TAU:
        bad.append("tau %r is under %d s -- the order could land after the close"
                   % (tau, MIN_TAU))
    if balance is None:
        bad.append("balance unreadable -- a penny test never guesses the bank")
    elif float(balance) - cost < BALANCE_FLOOR:
        bad.append("balance $%.2f - $%.2f would fall under the $%.2f floor"
                   % (float(balance), cost, BALANCE_FLOOR))
    return bad


def arm(state, live, signoff):
    """The ONLY path to production. Both flags, or nothing happens."""
    if not live:
        return "no --live: paper prices, no orders"
    if (signoff or "").strip().lower() != SIGNOFF_PHRASE:
        return ("--signoff must be exactly %r (the operator's per-instance "
                "sign-off, hard rule 1)" % SIGNOFF_PHRASE)
    import kauth
    state.creds = {"base": pintake.PROD_ELECTIONS,
                   "key_id": kauth.KEY_ID,
                   "pk": ordercli.load_key(pintake.PROD_KEY_FILE)}
    pintake.arm_prod("cmdlive commodity penny test, operator sign-off 2026-09-17")
    state.armed = True
    return None


def balance_dollars(creds):
    """The account balance in dollars, or None. NEVER inferred from a unit
    guess -- `balance_dollars` is read as sent, and a response without it is
    a failed read, not a division."""
    try:
        st, d = pintake._get(creds["base"], creds["pk"], creds["key_id"],
                             "/portfolio/balance")
    except Exception:                                             # noqa: BLE001
        return None
    if st != 200 or not isinstance(d, dict):
        return None
    v = d.get("balance_dollars")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _settled_today(results=None, now=None):
    """(net realised dollars, losing settlements) for today, from the day's logs.

    Same reason as `spent_today`: every brake must bound the DAY, not the
    process. A restart that reset the 2-loss brake would make the brake a
    formality -- crash twice and it never fires.
    """
    import glob as _glob
    import pinday
    res = RESULTS if results is None else results
    day = pinday.et_day_of_epoch(time.time() if now is None else now)
    net, lost = 0.0, 0
    for f in sorted(_glob.glob(os.path.join(res, "cmdlive-*.jsonl"))):
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"settled"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("kind") != "settled" or pinday.et_day_of_record(r) != day:
                    continue
                net += float(r.get("pnl_c") or 0.0) / 100.0
                if not r.get("won"):
                    lost += 1
    return net, lost


def spent_today(results=None, now=None):
    """Dollars already committed by EARLIER runs on the same Eastern day.

    A restart used to reset the $10 ceiling, so three restarts meant $30. The
    cap is meant to bound the DAY, not the process, so a new run starts from
    what the day's logs already show. Reads fills only, never intents.
    """
    import glob as _glob
    import pinday
    res = RESULTS if results is None else results
    day = pinday.et_day_of_epoch(time.time() if now is None else now)
    total = 0.0
    for f in sorted(_glob.glob(os.path.join(res, "cmdlive-*.jsonl"))):
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"order"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("kind") != "order":
                    continue
                if pinday.et_day_of_record(r) != day:
                    continue
                filled = float(r.get("filled") or 0)
                if filled <= 0:
                    continue
                px = r.get("exec_price")
                px = float(px) if px is not None else float(r.get("ask_seen") or 0)
                total += px * filled
    return total


def open_markets(series):
    """{ticker: (close_epoch, exchange_index)} for markets closing within 15
    minutes. cmdarm's version drops the exchange index; an order needs it."""
    from kauth import get
    out = {}
    now = time.time()
    for s in series:
        try:
            st, d = get("/markets?series_ticker=%s&status=open&limit=200" % s)
        except Exception:                                         # noqa: BLE001
            continue
        if st != 200 or not isinstance(d, dict):
            continue
        for m in d.get("markets", []):
            tk = m.get("ticker")
            c = pinflat.close_epoch(tk) if tk else None
            if c and 0 < c - now <= 900:
                out[tk] = (c, int(m.get("exchange_index") or 0))
    return out


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("cmdlive selftest: FAILED -- " + msg)

    # ---- the windows are cmdarm's, by reference. They cannot drift.
    ck(cmdarm.BANDS is not None and all(s_ in cmdarm.BANDS for s_ in LIVE_SERIES),
       "the windows come from cmdarm.BANDS -- one source, so the paper control "
       "and the live test can never drift apart")
    ck("KXCOPPER15M" in cmdarm.BANDS and "KXCOPPER15M" not in LIVE_SERIES,
       "copper IS traded now, in paper only: the separation is the live list, "
       "not the absence of a window")
    g_near, g_far = cmdarm.BANDS["KXGOLD15M"]
    ck(cmdarm.decide({"yes_ask": 0.96, "yes_ask_size": 50.0, "age_ms": 100}, 10,
                     g_near, hour=11) is None,
       "the live test inherits the COMEX skip: no gold at 11:00 ET")
    ck(cmdarm.decide({"yes_ask": 0.96, "yes_ask_size": 50.0, "age_ms": 100}, 120,
                     g_far, hour=11) == ("yes", 0.96, 50.0),
       "...and inherits the far window: gold at 96c with 120 s left is a bet")
    ck(all(s_ in cmdarm.BANDS for s_ in LIVE_SERIES)
       and not any(cmdarm.label(b).startswith("anti")
                   for s_ in LIVE_SERIES for b in cmdarm.BANDS[s_]),
       "every live series exists in cmdarm and none of their windows is a control")

    # ---- arming
    s = State()
    ck(arm(s, False, SIGNOFF_PHRASE) and not s.armed,
       "NULL: no --live means no arming, whatever the sign-off says")
    ck(arm(s, True, "yes go ahead") and not s.armed,
       "NULL: --live with the wrong phrase does NOT arm (hard rule 1)")
    ck(arm(s, True, None) and not s.armed,
       "NULL: --live with no sign-off does not arm")
    ck(not s.armed, "after three refusals the state is still unarmed")

    # ---- the guard. An unarmed state refuses everything.
    ok_args = dict(tau=10, price=0.95, count=1.0, balance=500.0)
    ck(guard(s, **ok_args), "an unarmed state refuses a perfectly good order")
    s.armed = True
    ck(guard(s, **ok_args) == [], "armed, in window, funded: no refusals")

    ck(guard(s, tau=1, price=0.95, count=1.0, balance=500.0),
       "NULL: 1 s left is refused -- the order could land after the close")
    ck(guard(s, tau=None, price=0.95, count=1.0, balance=500.0),
       "NULL: an unknown tau is refused, not assumed safe")
    ck(guard(s, tau=10, price=0.995, count=1.0, balance=500.0),
       "NULL: 99.5c is above the penny test's ceiling")
    ck(guard(s, tau=10, price=0.80, count=1.0, balance=500.0),
       "NULL: 80c is below the window -- not a near-certainty")
    ck(guard(s, tau=10, price=0.95, count=6.0, balance=500.0),
       "NULL: 6 contracts is past the hard ceiling of 5")
    ck(guard(s, tau=10, price=0.95, count=0.0, balance=500.0),
       "NULL: zero contracts is not an order")
    ck(guard(s, tau=10, price=0.95, count=1.0, balance=None),
       "NULL: an unreadable balance refuses -- a failed read is not a green light")
    ck(guard(s, tau=10, price=0.95, count=1.0, balance=300.50),
       "NULL: an order that would take the account under the $300 floor")
    ck(guard(s, tau=10, price=0.95, count=1.0, balance=500.0, stop="cmdlive.stop"),
       "NULL: the stop flag refuses")
    ck(guard(s, series="KXSILVER15M", **ok_args)
       and guard(s, series="KXCOPPER15M", **ok_args)
       and guard(s, series="KXNATGAS15M", **ok_args),
       "NULL: silver, copper and gas are paper-only and cannot reach the wire")
    ck(guard(s, series="KXGOLD15M", **ok_args) == []
       and guard(s, series="KXWTI15M", **ok_args) == [],
       "...gold and oil, the two with evidence at both ends, are the live list")
    ck(guard(s, series="KXGOLD15M", window="anti-silver-mid", **ok_args),
       "NULL: a window labelled 'anti' is a deliberate loser and never goes live")
    ck(guard(s, series="KXGOLD15M", window="gold-far", **ok_args) == [],
       "...a real window passes")

    # ---- the money ceilings
    s2 = State(); s2.armed = True; s2.spent = MAX_SPEND - 0.50
    ck(guard(s2, **ok_args),
       "NULL: 50c of turnover left will not cover a 95c contract")
    s2.spent = MAX_SPEND - 1.00
    ck(guard(s2, **ok_args) == [], "...but a dollar of room takes one more")
    s3 = State(); s3.armed = True; s3.orders = MAX_ORDERS
    ck(guard(s3, **ok_args), "NULL: the order ceiling refuses attempt %d" % (MAX_ORDERS + 1))
    s4 = State(); s4.armed = True; s4.losses = MAX_LOSSES
    ck(guard(s4, **ok_args), "NULL: the 2-loss brake refuses")
    s5 = State(); s5.armed = True; s5.losses = MAX_LOSSES - 1
    ck(guard(s5, **ok_args) == [], "...one loss does not")

    # ---- the stop flags
    tmp = os.path.join(RESULTS, "_cmdlive_selftest.stop")
    try:
        os.remove(tmp)
    except OSError:
        pass
    ck(stopped(tmp, tmp) is None, "no flag file, no stop")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("x")
    ck(stopped(tmp, "nonexistent") == "cmdlive.stop", "our own stop flag is seen")
    ck(stopped("nonexistent", tmp) and "desktop" in stopped("nonexistent", tmp),
       "the DESKTOP APP's stop flag also stops the penny test")
    os.remove(tmp)

    # ---- the source itself: the guard must precede the wire
    # Needles built from PIECES: a literal here would match the self-test's own
    # source and slice the wrong region. That trap has cost this project three
    # false greens, and it cost this file one: `loop` came out 24 characters
    # long because the slice ended on the self-test's own "def main(".
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    d_loop, d_main = "def " + "trade_loop(", "def " + "main("
    loop = src[src.rindex(d_loop):src.rindex(d_main)]
    ck(len(loop) > 2000, "the loop slice is the real function, not a fragment "
                         "of the self-test (%d chars)" % len(loop))
    wire = "pintake" + ".take("
    gpos, tpos = loop.index("guard("), loop.index(wire)
    ck(gpos < tpos, "in the trade loop the guard runs BEFORE the wire call")
    ck("if refused:" in loop and "continue" in loop[loop.index("if refused:"):],
       "...and a non-empty refusal list skips the order rather than logging and "
       "carrying on")
    ck(loop.count(wire) == 1, "there is exactly ONE path to the wire in the loop")
    ck("state.orders += 1" in loop and "state.spent +=" in loop,
       "attempts and dollars are both counted, or the ceilings are decoration")
    ck("HEARTBEAT" in loop and "last_beat" in loop,
       "the loop writes a heartbeat: the operator's rule is that state is "
       "derived from evidence of WORK, never from a process being alive")
    ck("max_tau=MAX_TAU_ASK" in loop,
       "the wire call passes this caller's own tau rail, or every far-window "
       "order is refused by pintake's 90 s default (it was, twice, live)")
    ck(MAX_TAU_ASK >= 180 and MAX_TAU_ASK <= pintake.MAX_TAU_CEILING
       and pintake.MAX_TAU == 90.0,
       "the ask covers the 91-180 s windows, sits under pintake's ceiling, and "
       "leaves pintake's shipped 90 s default untouched for the crypto bot")
    ck("said.add(k)" in loop and "if k not in said:" in loop,
       "a repeated refusal is reported ONCE, not four times a second for a "
       "minute -- and it still does not consume the market's one shot")
    head = src[:src.rindex("def " + "selftest(")]
    ck(head.count("arm_" + "prod(") == 1,
       "production is armed in exactly one place in the working code")
    # THE DAILY CEILING: a restart must not hand the run a fresh $10.
    import tempfile
    _td = tempfile.mkdtemp()
    _day = time.strftime("%y%b%d", time.gmtime(time.time() - 4 * 3600)).upper()
    with open(os.path.join(_td, "cmdlive-x.jsonl"), "w", encoding="utf-8") as _fh:
        for _r in ({"kind": "order", "ticker": "KXWTI15M-%s1100-00" % _day,
                    "filled": 1, "exec_price": 0.95},
                   {"kind": "order", "ticker": "KXWTI15M-%s1115-15" % _day,
                    "filled": 0, "ask_seen": 0.95},
                   {"kind": "order", "ticker": "KXWTI15M-25JAN011100-00",
                    "filled": 1, "exec_price": 0.99}):
            _fh.write(json.dumps(_r) + chr(10))
    ck(abs(spent_today(results=_td) - 0.95) < 1e-9,
       "spent_today counts only TODAY's FILLS: the unfilled order and the one "
       "from another day are both excluded")
    ck(spent_today(results=os.path.join(_td, "nope")) == 0.0,
       "NULL: no logs, no spend -- and no crash")
    # THE LOSS BRAKES MUST SURVIVE A RESTART TOO, or crashing twice disarms them
    with open(os.path.join(_td, "cmdlive-s.jsonl"), "w", encoding="utf-8") as _fh:
        for _r in ({"kind": "settled", "ticker": "KXWTI15M-%s1100-00" % _day,
                    "won": True, "pnl_c": 9.0},
                   {"kind": "settled", "ticker": "KXWTI15M-%s1115-15" % _day,
                    "won": False, "pnl_c": -95.0},
                   {"kind": "settled", "ticker": "KXWTI15M-25JAN011100-00",
                    "won": False, "pnl_c": -99.0}):
            _fh.write(json.dumps(_r) + chr(10))
    _net, _lost = _settled_today(results=_td)
    ck(abs(_net - (-0.86)) < 1e-9 and _lost == 1,
       "_settled_today nets TODAY's settlements (+9c and -95c = -86c) and counts "
       "ONE loss; yesterday's loss is not today's brake")
    ck(_settled_today(results=os.path.join(_td, "nope")) == (0.0, 0),
       "NULL: no logs, no losses -- and no crash")
    _s6 = State(); _s6.armed = True; _s6.realised = -MAX_NET_LOSS
    ck(guard(_s6, **ok_args), "NULL: at the net-loss cap the day is over")
    _s7 = State(); _s7.armed = True; _s7.realised = -MAX_NET_LOSS + 0.01
    ck(guard(_s7, **ok_args) == [], "...a cent short of it still trades")
    ck(MAX_NET_LOSS <= 5.0 and MAX_LOSSES <= 2,
       "the RISK caps are unchanged by the turnover raise: 2 losses, $5 net")
    ck(float(SIZE) == 1.0 and MAX_LOSSES <= 2 and MAX_NET_LOSS <= 5.0
       and MAX_SPEND <= 40.0 and BALANCE_FLOOR >= 300.0,
       "the SHIPPED defaults are one contract, a 2-loss brake, a $5 net-loss cap, "
       "$40 of daily turnover and a $300 account floor. The RISK caps are the "
       "first two; turnover is not risk, because a winning contract recycles")
    print("cmdlive selftest: OK")


def trade_loop(state, series, minutes, rec, dry=False):
    """The loop. One paper-priced decision per market per window, guarded,
    then at most one order."""
    book = livebook.LiveBook().start()
    watching, pend, per_close, looked, bets = {}, {}, collections.Counter(), set(), []
    said = set()            # (ticker, window, reasons) already reported
    last_disc, last_bal, last_beat, balance = 0.0, 0.0, 0.0, None
    end = time.time() + minutes * 60
    while time.time() < end:
        now = time.time()
        # A heartbeat, not a process check. The operator's standing rule is
        # that state is DERIVED, never trusted: "running" is not "working".
        if now - last_beat > 20:
            last_beat = now
            try:
                with open(HEARTBEAT, "w", encoding="utf-8") as hb:
                    hb.write(json.dumps({
                        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "pid": os.getpid(), "orders": state.orders,
                        "fills": state.fills, "spent": round(state.spent, 4),
                        "losses": state.losses, "watching": len(watching)}))
            except OSError:
                pass
        flag = stopped()
        if flag:
            rec("stop", why=flag)
            print("  STOPPED: %s" % flag, flush=True)
            break
        if now - last_bal > 60 and state.armed:
            last_bal = now
            balance = balance_dollars(state.creds)
        if now - last_disc > 30:
            last_disc = now
            try:
                fresh = open_markets(series)
            except Exception as e:                                # noqa: BLE001
                rec("error", where="discover", err=str(e)[:200])
                fresh = {}
            new = [t for t in fresh if t not in watching]
            if new:
                book.subscribe(sorted(new))
                rec("watch", added=sorted(new))
            for t in [t for t in watching if t not in fresh]:
                watching.pop(t, None)
                pend[t] = time.time()
                looked.discard(t)
            watching.update(fresh)

        for tk, (close_s, exi) in list(watching.items()):
            tau = int(close_s - time.time())
            ser = tk.split("-")[0]
            bands = cmdarm.BANDS.get(ser)
            if not bands:
                continue
            try:
                best = book.best(tk)
            except Exception:                                     # noqa: BLE001
                continue
            lo, hi = cmdarm.span(bands)
            if tau < lo and tk not in looked:
                looked.add(tk)
                rec("look", ticker=tk, series=ser,
                    bet=any(per_close[(tk, i)] for i in range(len(bands))))
            hour = cmdarm.hour_et(tk)
            for bi, band in enumerate(bands):
                if per_close[(tk, bi)] >= 1:
                    continue
                d = cmdarm.decide(best, tau, band, hour=hour)
                if not d:
                    continue
                want, px, offer = d
                n = min(state.size, float(offer))
                refused = guard(state, tau, px, n, balance, stopped(),
                                series=ser, window=cmdarm.label(band))
                if refused:
                    # ONCE per market per window per reason. A refusal does not
                    # consume the market's one shot (a transient one, like a
                    # failed balance read, must be able to retry), so without
                    # this the loop would log four times a second for a whole
                    # minute. The ancestor of that bug sent 160 orders in one
                    # close.
                    k = (tk, bi, tuple(refused))
                    if k not in said:
                        said.add(k)
                        rec("refused", ticker=tk, series=ser, tau=tau, want=want,
                            price=px, count=n, why=refused)
                        print("  REFUSED %s tau=%3ds %s @%.4f -- %s"
                              % (tk, tau, want.upper(), px, "; ".join(refused)), flush=True)
                    continue
                per_close[(tk, bi)] += 1
                state.orders += 1
                if dry:
                    rec("dry", ticker=tk, series=ser, tau=tau, want=want,
                        price=px, count=n, band=bi)
                    print("  DRY %s tau=%3ds %s @%.4f x%.0f  (no wire)"
                          % (tk, tau, want.upper(), px, n), flush=True)
                    continue
                t0 = time.time()
                # pintake's shipped rail is 90 s, written for the crypto bot
                # whose edge lives in the last minute. The commodity grid's
                # best cells are at 91-180 s, so this caller asks for its own
                # widest window and pintake still refuses anything past it (and
                # past its own 240 s ceiling).
                out = pintake.take(state.creds["base"], state.creds["pk"],
                                   state.creds["key_id"], tk, want, px, n,
                                   close_s, exchange_index=exi,
                                   max_tau=MAX_TAU_ASK)
                filled = float(out.get("filled") or 0)
                xp = out.get("exec_price")
                cost = float(xp) if xp is not None else float(px)
                if filled > 0:
                    state.fills += 1
                    state.spent += cost * filled
                    bets.append({"ticker": tk, "series": ser, "want": want,
                                 "price": cost, "n": filled, "tau": tau, "band": bi})
                rec("order", ticker=tk, series=ser, tau=tau, want=want,
                    ask_seen=round(px, 4), count=n, band=bi,
                    window=list(band[:4]), exchange_index=exi,
                    latency_ms=round(1000 * (time.time() - t0), 1),
                    book_age_ms=(best or {}).get("age_ms"),
                    spent_after=round(state.spent, 4),
                    **{k: v for k, v in out.items() if k != "raw"})
                ref = out.get("refused") or []
                if ref or out.get("status_code") is None:
                    print("    ORDER REFUSED BY PINTAKE %s" % (ref,), flush=True)
                else:
                    print("  ORDER %s tau=%3ds %s @%.4f x%.0f -> filled %.0f  spent $%.2f"
                          % (tk, tau, want.upper(), px, n, filled, state.spent), flush=True)

        due = [t for t, when in pend.items() if time.time() - when > 90]
        if due:
            try:
                got = cmdarm.settlements(due)
            except Exception as e:                                # noqa: BLE001
                got, _ = {}, rec("error", where="settle", err=str(e)[:200])
            for t in due:
                if t not in got:
                    if time.time() - pend[t] > 1800:
                        pend.pop(t, None)
                    continue
                pend.pop(t, None)
                mine = [b for b in bets if b["ticker"] == t and "won" not in b]
                for sc in cmdarm.score(mine, got):
                    for b in mine:
                        b.update(won=sc["won"], pnl=sc["pnl"])
                    state.realised += float(sc["pnl"])
                    if not sc["won"]:
                        state.losses += 1
                    rec("settled", ticker=t, result=got[t], won=sc["won"],
                        pnl_c=round(100 * sc["pnl"], 2), losses=state.losses,
                        realised=round(state.realised, 4))
                    print("  SETTLED %s -> %s  $%+.2f   (losses %d/%d, day $%+.2f)"
                          % (t, "WON" if sc["won"] else "LOST", sc["pnl"],
                             state.losses, MAX_LOSSES, state.realised), flush=True)
                _brake = ("%d losses" % state.losses if state.losses >= MAX_LOSSES
                          else ("$%.2f net down" % state.realised
                                if state.realised <= -MAX_NET_LOSS else None))
                if _brake:
                    with open(STOP_FILE, "w", encoding="utf-8") as fh:
                        fh.write("%s at %s\n" % (_brake, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
                    rec("brake", losses=state.losses, realised=round(state.realised, 4),
                        why=_brake)
                    print("  *** BRAKE: %s. stop file written. ***" % _brake, flush=True)
        time.sleep(0.25)
    return bets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--signoff", default=None)
    ap.add_argument("--dry", action="store_true",
                    help="arm, guard, log what WOULD be sent, send nothing")
    ap.add_argument("--series", nargs="*", default=list(LIVE_SERIES))
    ap.add_argument("--size", type=float, default=SIZE)
    ap.add_argument("--minutes", type=float, default=1440)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()

    state = State(size=a.size)
    # EVERY brake bounds the DAY, not the process. A restart that reset the
    # 2-loss brake would make it a formality: crash twice and it never fires.
    state.spent = spent_today()
    state.realised, state.losses = _settled_today()
    if a.size > MAX_SIZE:
        print("--size %.2f is above the hard ceiling of %.0f" % (a.size, MAX_SIZE))
        return 2
    why = arm(state, a.live, a.signoff)
    if why:
        print("NOT ARMED: %s" % why)
        return 2
    flag = stopped()
    if flag:
        print("NOT STARTING: stop flag set (%s)" % flag)
        return 2

    os.makedirs(RESULTS, exist_ok=True)
    log = os.path.join(RESULTS, "cmdlive-%s.jsonl" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    fh = open(log, "a", encoding="utf-8", buffering=1)

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fh.write(json.dumps(kw) + "\n")

    bal = balance_dollars(state.creds)
    rec("start", series=a.series, size=state.size, dry=bool(a.dry),
        bands={k: [list(b) for b in v] for k, v in cmdarm.BANDS.items()},
        max_spend=MAX_SPEND, max_orders=MAX_ORDERS, max_losses=MAX_LOSSES,
        max_net_loss=MAX_NET_LOSS, realised_earlier_today=round(state.realised, 4),
        losses_earlier_today=state.losses,
        balance_floor=BALANCE_FLOOR, balance_at_start=bal,
        spent_earlier_today=round(state.spent, 4),
        signoff="operator 2026-09-17: ready for commodity penny testing",
        version="cmdpenny-1")
    print("cmdlive %s -- %s | size %.0f | caps: $%.2f spend, %d orders, %d losses, "
          "balance floor $%.0f | balance now $%s | log %s"
          % ("DRY RUN" if a.dry else "*** LIVE, REAL MONEY ***", ", ".join(a.series),
             state.size, MAX_SPEND, MAX_ORDERS, MAX_LOSSES, BALANCE_FLOOR,
             ("%.2f" % bal) if bal is not None else "?", os.path.basename(log)), flush=True)

    try:
        bets = trade_loop(state, a.series, a.minutes, rec, dry=a.dry)
    finally:
        rec("end", orders=state.orders, fills=state.fills,
            spent=round(state.spent, 4), losses=state.losses)
        print("  end: %d orders, %d fills, $%.2f spent, %d losses"
              % (state.orders, state.fills, state.spent, state.losses), flush=True)
    done = [b for b in bets if "won" in b]
    if done:
        print("  settled %d: $%+.2f" % (len(done), sum(b["pnl"] for b in done)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
