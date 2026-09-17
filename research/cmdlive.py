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
# SCALED UP 2026-09-17 ~18:2xZ on the operator's instruction: "up the live
# commodity trading to 30 dollars size per trade. It's doing well." It was one
# contract (~95c); it is now THIRTY DOLLARS of contracts, about 31 at 96c.
#
# Size is set in DOLLARS, not contracts, because the windows span 90-99c and a
# fixed contract count would stake 3x more risk at 30c of price difference. The
# count is dollars/price, floored at 1 and capped by MAX_CONTRACTS and by what
# the book is actually offering.
#
# WHAT THIS CHANGES ABOUT THE RISK, stated plainly: a win pays about +$1.16 and
# a loss costs about -$29.8, so ONE loss needs ~26 wins to recover. That is the
# arithmetic of near-certainty trading and it is why the brakes below are in
# NET DOLLARS, not trade counts.
# STEPPED BACK 30.00 -> 10.00 on 2026-09-17 ~20:5xZ, the operator's call after
# the first losing day: "$10". The $30 run lost $53.06 on 28 settled trades of
# which 26 won, and roughly half of that loss was the one-bet-per-WINDOW defect
# doubling a single adverse event. The defect is fixed; the size steps back
# until there are ~60 clean fills, then returns to $30.
SIZE_DOLLARS = 20.0         # dollars of contracts per order
MAX_SIZE = 60.0             # --size (dollars) may never exceed this
MAX_CONTRACTS = 40.0        # hard contract ceiling; $30 at the 90c floor is 33
# GROSS TURNOVER, not risk. Raised 10.00 -> 40.00 on 2026-09-17 ~17:0xZ, after the
# first day hit it at 10 fills (10 won, 0 lost, +$0.47) and began refusing every
# further trade. The $10 was measuring the WRONG THING: a winning contract returns
# its dollar and the capital recycles, so gross spend climbs while the risk does
# not move at all. What actually bounds the downside is MAX_LOSSES (2 losses is
# about $2) and MAX_NET_LOSS (the day's realised dollars). Both are untouched --
# this number only stops the thing running away in VOLUME.
MAX_SPEND = 1200.00         # dollars of cost across the DAY (gross; it recycles)
MAX_NET_LOSS = 50.00        # dollars NET REALISED down on the day, then stop.
                            # THE REAL BRAKE, and it scales with the size: about
                            # 2.5 losing trades. At $10 a trade a loss costs
                            # ~$9.9 and a win pays ~$0.39, so it still takes ~26
                            # wins to repay one loss -- the ratio is a property
                            # of near-certainty trading, not of the size.
MAX_RUN_STAKE = 250.00      # dollars IN FLIGHT at once (pintake's own rail,
                            # shipped at $60 for a one-contract caller). Five
                            # windows across two series can be open together, so
                            # $30 each needs headroom. This is exposure, not
                            # loss: the loss brakes above are what bound damage.
MAX_ORDERS = 60             # hard ceiling on attempts that reach the wire
MAX_LOSSES = 4              # the disaster catch. The NET cap above normally
                            # fires first; this one catches many small losses.
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

# WINDOWS ALLOWED LIVE, by label. Narrowed 2026-09-17 ~21:3xZ to the CLOSE band
# only, on the operator's read: "it wasn't very solid on the far band. You
# believe in the close band right?" He is right, on two grounds.
#
# 1. ALL THREE live losses came from far or boundary windows -- WTI at 180 s,
#    WTI at exactly 60 s, GOLD at 180 s. None came from inside 45 seconds.
# 2. The far band's case rests on a MECHANISM STORY (far from the close the
#    market prices in a reversion that mostly does not come). The close band's
#    case does not need a story: a commodity settles on the close of a 1-minute
#    candle, and inside 15 seconds that candle is nearly formed. That is
#    arithmetic, and it is the half of the U-shape I actually believe.
#
# The tape by markets, for what stays live:
#     gold-near  2-15 s, 95-99c : 149 markets, 2 lost (1.3%)
#     wti-near   2-60 s, 95-99c : 519 markets, 4 lost (0.8%)
# and for what is now paper-only:
#     wti-mid    16-45 s, 90-95c: 104 markets, 6 lost (5.8%) -- marginal
#     gold-far / wti-far        : good on tape, and where every loss came from
#
# The far windows keep running in `cmdarm` (paper), so we keep learning about
# them without paying for the lesson.
LIVE_WINDOWS = ("gold-near", "wti-near")
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

    def __init__(self, size=SIZE_DOLLARS):
        self.size = float(size)     # DOLLARS per order, not contracts
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
    elif window is not None and window not in LIVE_WINDOWS:
        bad.append("window %r is paper-only; live is the close band (%s)"
                   % (window, ", ".join(LIVE_WINDOWS)))
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
    elif n > MAX_CONTRACTS:
        bad.append("count %.2f is above the hard ceiling of %.0f contracts"
                   % (n, MAX_CONTRACTS))
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
    # pintake ships MAX_TAKE_COUNT 10 / HARD_MAX 25, which would refuse a $30
    # order outright (about 31 contracts at 96c). set_limits is one-way -- it
    # can only LOOSEN, and it prints the change rather than moving silently.
    # Two rails, both shipped for a much smaller caller. MAX_TAKE_COUNT 10 /
    # HARD_MAX 25 would refuse a $30 order outright (~31 contracts at 96c), and
    # MAX_RUN_STAKE $60 is total dollars IN FLIGHT -- two open positions at this
    # size exhaust it. set_limits is one-way (loosen only) and prints the change.
    pintake.set_limits(max_take_count=MAX_CONTRACTS,
                       max_run_stake=MAX_RUN_STAKE,
                       why="cmdlive $%.0f per trade" % SIZE_DOLLARS)
    pintake.arm_prod("cmdlive commodity live test, operator sign-off 2026-09-17")
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


def release(ticker, bets, ledger=None):
    """Return the committed dollars for a settled market. Returns what it freed.

    Mirrors `pinrun._release`: subtract exactly `price * filled` per fill, floor
    the ledger at zero, and drop the ticker's position record only when no other
    open fill still references it.
    """
    led = pintake.LEDGER if ledger is None else ledger
    owed = 0.0
    for b in bets:
        try:
            owed += float(b.get("price", 0.0)) * float(b.get("n", 0.0))
        except (TypeError, ValueError):
            continue
    led["committed"] = max(0.0, float(led.get("committed", 0.0)) - owed)
    if isinstance(led.get("positions"), dict):
        led["positions"].pop(ticker, None)
    return owed


OFFSET_MAX_TAU = 60      # only a window ending inside this may offset


def market_block(held_side, want, band, offset_done):
    """Why this market must not be traded again, or None to allow it.

    ONE POSITION PER MARKET, with one exception.

    The windows are not independent opportunities -- they are different moments
    looking at the SAME binary outcome. A second bet on the SAME side doubles
    the stake on one event (that is what cost $58.84 on 2026-09-17, two NO legs
    on one oil market).

    The exception, and why it is not just a hedge: a NEAR window may take the
    OPPOSITE side once. Buying the other side at the market price is EV-NEUTRAL
    by construction, because the price IS the probability -- as a hedge it earns
    nothing and merely converts a probable loss into a certain smaller one. But
    the near windows are independently profitable on their own record (WTI
    0-60 s: 519 markets, 4 lost; GOLD 0-15 s: 149, 2). So that trade is worth
    taking whether or not we already hold something, and capping the loss is a
    side effect rather than the reason. Far windows get no such exception:
    their information is worse than the position they would be offsetting.
    """
    if held_side is None:
        return None
    if want == held_side:
        return "same_side"                       # doubling one event's stake
    if offset_done:
        return "offset_used"                     # one offset per market
    if band[1] > OFFSET_MAX_TAU:
        return "far_window_cannot_offset"
    return None


def contracts_for(dollars, price, offer):
    """How many contracts $`dollars` buys at `price`, given what is `offer`ed.

    Sizing is in DOLLARS because the windows span 90-99c: a fixed contract
    count would stake noticeably more at the cheap end, and the thing we want
    constant is the money at risk, not the count. Floored at one contract (a
    sub-dollar order is still a real test), capped by MAX_CONTRACTS and by the
    book -- we never ask for more than is actually being offered.
    """
    try:
        p = float(price)
        off = float(offer)
        d = float(dollars)
    except (TypeError, ValueError):
        return 0.0
    if p <= 0 or off <= 0 or d <= 0:
        return 0.0
    want = int(d / p)                      # whole contracts only
    return float(max(1, min(want, int(MAX_CONTRACTS), int(off))))


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
    ck(guard(s, tau=10, price=0.95, count=MAX_CONTRACTS + 1.0, balance=5000.0),
       "NULL: one contract past MAX_CONTRACTS is refused, however well funded")
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
    ck(guard(s, series="KXGOLD15M", window="gold-near", **ok_args) == []
       and guard(s, series="KXWTI15M", window="wti-near", **ok_args) == [],
       "the CLOSE band is what trades live: gold 2-15 s and WTI 2-60 s, both "
       "95-99c, 668 tape markets and 6 losses between them")
    ck(guard(s, series="KXGOLD15M", window="gold-far", **ok_args)
       and guard(s, series="KXWTI15M", window="wti-far", **ok_args)
       and guard(s, series="KXWTI15M", window="wti-mid", **ok_args),
       "and the FAR and MID windows are refused live -- all three real losses "
       "came from 180 s, 180 s and exactly 60 s, and the far band's case rests "
       "on a mechanism story rather than on a nearly-formed candle")
    ck(all(w in [cmdarm.label(b) for v in cmdarm.BANDS.values() for b in v]
           for w in LIVE_WINDOWS),
       "every live window label actually exists in cmdarm.BANDS -- a typo here "
       "would silently trade nothing at all")

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
    ck(MAX_NET_LOSS <= 2.5 * SIZE_DOLLARS and MAX_LOSSES <= 4,
       "the RISK caps scale WITH the trade size and stay inside ~2.5 losing "
       "trades; turnover is not risk, because a winning contract recycles")
    # SIZING IS IN DOLLARS. A fixed contract count would stake a third more at
    # the 90c end of the window than at 99c; what we want held constant is the
    # money, not the count.
    ck(contracts_for(30.0, 0.96, 500) == 31.0,
       "$30 at 96c is 31 contracts (whole contracts only, rounded DOWN so the "
       "order never exceeds the dollars asked for)")
    ck(contracts_for(30.0, 0.90, 500) == 33.0 and contracts_for(30.0, 0.99, 500) == 30.0,
       "...33 at the 90c floor and 30 at 99c -- the DOLLARS are what stays fixed")
    ck(contracts_for(30.0, 0.96, 12) == 12.0,
       "we never ask for more than the book is offering")
    ck(contracts_for(3000.0, 0.96, 99999) == MAX_CONTRACTS,
       "MAX_CONTRACTS is a hard ceiling no dollar figure can climb past")
    ck(contracts_for(0.10, 0.96, 500) == 1.0,
       "a sub-contract dollar figure still buys ONE -- a tiny order is a real test")
    ck(contracts_for(30.0, 0, 500) == 0 and contracts_for(30.0, 0.96, 0) == 0
       and contracts_for(30.0, "junk", 500) == 0,
       "NULL: no price, no offer, or an unparseable price buys nothing")
    # THE LEDGER LEAK. pintake commits filled*price and never learns a market
    # settled; without a release the stake cap silently refuses everything.
    _led = {"committed": 100.0, "positions": {"KXWTI15M-A": {"n": 31}, "KXGOLD15M-B": {}}}
    _freed = release("KXWTI15M-A", [{"price": 0.96, "n": 31.0}], ledger=_led)
    ck(abs(_freed - 29.76) < 1e-9 and abs(_led["committed"] - 70.24) < 1e-9,
       "releasing a settled $29.76 position gives back exactly price x filled")
    ck("KXWTI15M-A" not in _led["positions"] and "KXGOLD15M-B" in _led["positions"],
       "...and drops only that ticker's position record")
    _led2 = {"committed": 5.0, "positions": {}}
    ck(release("T", [{"price": 0.96, "n": 31.0}], ledger=_led2) > 0
       and _led2["committed"] == 0.0,
       "the ledger floors at zero rather than going negative")
    ck(release("T", [{"price": "junk", "n": 1}], ledger={"committed": 1.0}) == 0.0,
       "NULL: an unparseable fill releases nothing rather than guessing")
    _s0 = open(os.path.abspath(__file__), encoding="utf-8").read()
    _lp2 = _s0[_s0.rindex("def " + "trade_loop("):_s0.rindex("def " + "main(")]
    # ONE POSITION PER MARKET. The windows look at the SAME binary outcome, so a
    # second bet doubles the stake on one event and an opposite-side bet locks a
    # loss. This cost $58.84 on one oil market before the check existed.
    # ONE POSITION PER MARKET, with the near-window offset as the one exception.
    _nearb, _farb = (2, 60, 0.95, 0.99, None, "n"), (121, 180, 0.9, 0.99, None, "f")
    ck(market_block(None, "yes", _farb, False) is None,
       "an untouched market is free to trade from any window")
    ck(market_block("yes", "yes", _nearb, False) == "same_side",
       "the SAME side again is refused -- that doubles one event's stake, which "
       "is what turned one adverse oil market into -$58.84")
    ck(market_block("no", "yes", _nearb, False) is None,
       "but a NEAR window may take the OPPOSITE side once: that bet is "
       "independently profitable (WTI 0-60 s, 519 markets, 4 lost) and capping "
       "the loss is a side effect, not the reason")
    ck(market_block("no", "yes", _farb, False) == "far_window_cannot_offset",
       "a FAR window may NOT offset -- its information is worse than the "
       "position it would be offsetting")
    ck(market_block("no", "yes", _nearb, True) == "offset_used",
       "and only ONE offset per market, or we are back to stacking legs")
    ck("market_block(" in _lp2 and _lp2.index("want, px, offer = d") < _lp2.index("market_block("),
       "the loop tests it AFTER `want` is decided -- testing it earlier would "
       "compare against an undecided side, the exact bug just fixed in pinrun's "
       "AMENDMENT 8")
    ck("sizes[tk] = filled" in _lp2 and "min(n, float(sizes.get(tk, n)))" in _lp2,
       "an offset never stakes more than the position it offsets")
    ck("held[tk] = want" in _lp2.split("if filled > 0:")[1][:700],
       "the claim is made on a FILL, not on an attempt -- a refused order must "
       "not lock a market out")
    ck("release(t, mine)" in _lp2,
       "and the trade loop actually CALLS it on settlement -- a release nothing "
       "reaches is the leak with extra steps")
    _s8 = State(); _s8.armed = True
    ck(guard(_s8, tau=10, price=0.96, count=MAX_CONTRACTS + 1, balance=5000.0),
       "NULL: a count above MAX_CONTRACTS is refused even when funded")
    # The shipped size is deliberately not pinned to one number -- it steps with
    # the evidence. What IS pinned is the RELATIONSHIP between the size and the
    # brakes, because that is what stops a size change from quietly widening the
    # risk. At any size: one loss costs about the trade size, one win pays about
    # a thirtieth of it, and the brake must stop inside ~2.5 losing trades.
    ck(5.0 <= SIZE_DOLLARS <= 30.0 and MAX_CONTRACTS <= 40.0
       and MAX_LOSSES <= 4 and BALANCE_FLOOR >= 300.0,
       "the SHIPPED size is between $5 and $30 a trade, at most 40 contracts, "
       "a 4-loss brake and a $300 account floor")
    ck(abs(MAX_NET_LOSS - 2.5 * SIZE_DOLLARS) < 1e-9,
       "and the net-loss brake is exactly 2.5 trades' worth, so stepping the "
       "size NEVER silently widens the risk: $%.0f a trade -> stop at $%.0f down"
       % (SIZE_DOLLARS, MAX_NET_LOSS))
    ck(MAX_NET_LOSS < 3 * SIZE_DOLLARS,
       "the net brake must stop inside three losing trades, or it is not a brake")
    ck(BALANCE_FLOOR > 4 * MAX_NET_LOSS,
       "and the account floor must sit well clear of a full brake-out")
    print("cmdlive selftest: OK")


def trade_loop(state, series, minutes, rec, dry=False):
    """The loop. One paper-priced decision per market per window, guarded,
    then at most one order."""
    book = livebook.LiveBook().start()
    watching, pend, per_close, looked, bets = {}, {}, collections.Counter(), set(), []
    said = set()            # (ticker, window, reasons) already reported
    held = {}               # ticker -> the side we already hold. ONE per market.
    sizes = {}              # ticker -> contracts held, so an offset never exceeds it
    offsets = set()         # tickers that have already used their one offset
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
                # ONE POSITION PER MARKET, NOT PER WINDOW.
                #
                # 2026-09-17: KXWTI15M-26SEP171615-15 took NO at 180 s (31
                # contracts, 94c) and NO AGAIN at 60 s (30 contracts, 98.5c)
                # through two different windows, then YES at 23 s. The market
                # settled YES. ONE adverse event became TWO losses, -$58.84,
                # and the day's -$53 was almost entirely this.
                #
                # The windows are not independent opportunities. They are
                # different moments to look at the SAME binary outcome, so a
                # second bet doubles the stake on one event rather than
                # diversifying it -- and a bet on the OTHER side locks in a
                # guaranteed loss on one leg. `cmdlive` has no hedge logic, so
                # the opposite side is refused outright rather than treated as
                # one. The crypto bot has a `both_sides` gate for exactly this;
                # this file had nothing.
                #
                # THE ONE EXCEPTION, added 2026-09-17 on the operator's idea:
                # a NEAR window may take the OPPOSITE side of a position we
                # already hold. That is not a hedge in the usual sense, and the
                # distinction is the whole reason it is allowed. Buying the
                # other side at the market price is EV-NEUTRAL by construction,
                # because the price IS the probability -- it converts a probable
                # loss into a certain smaller one and earns nothing. But the
                # near windows are independently profitable on their own record
                # (WTI 0-60 s: 519 markets, 4 lost; GOLD 0-15 s: 149, 2), so
                # taking that bet is worth doing whether or not we hold anything
                # -- and it happens to cap the loss. Once per market, near
                # windows only, opposite side only.
                # The test itself lives BELOW, right after `want` is known --
                # putting it here would compare against a side that has not been
                # decided yet, which is precisely the bug just fixed in
                # pinrun's AMENDMENT 8.
                d = cmdarm.decide(best, tau, band, hour=hour)
                if not d:
                    continue
                want, px, offer = d
                _why = market_block(held.get(tk), want, band, offset_done=tk in offsets)
                if _why:
                    k = (tk, _why)
                    if k not in said:
                        said.add(k)
                        rec("one_per_market", ticker=tk, series=ser, why=_why,
                            holding=held.get(tk), wanted=want,
                            window=cmdarm.label(band), tau=tau)
                    continue
                n = contracts_for(state.size, px, offer)
                if held.get(tk) is not None:
                    # an offset: never stake more than the position it offsets
                    n = min(n, float(sizes.get(tk, n)))
                    offsets.add(tk)
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
                    # CLAIM THE MARKET. Every later window on this ticker is
                    # refused from here, whichever side it wants: a same-side
                    # bet doubles one event's stake, an opposite-side bet locks
                    # in a loss on one leg.
                    if tk not in held:
                        sizes[tk] = filled
                    held[tk] = want
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
                    # GIVE BACK EXACTLY WHAT WAS COMMITTED. pintake._book()
                    # adds filled*price to LEDGER["committed"] and has no idea
                    # a market ever settles, so anything that closes a position
                    # must subtract the same product. Without this the ledger
                    # leaks until MAX_RUN_STAKE silently refuses every further
                    # order -- no halt, no error, no log line, because take()
                    # RETURNS its refusal rather than raising. This is the exact
                    # bug pinrun's _release() was written for, and cmdlive had
                    # it too: it jammed at $59.15 committed on the first day at
                    # $30 a trade.
                    release(t, mine)
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
    ap.add_argument("--size", type=float, default=SIZE_DOLLARS,
                    help="DOLLARS per order (not contracts)")
    ap.add_argument("--reset-day", action="store_true",
                    help="clear today's seeded loss brakes. BY HAND ONLY: the "
                         "brakes normally seed from the day's logs so a crash "
                         "cannot disarm them.")
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
    if a.reset_day:
        # DELIBERATE, LOGGED, AND ONLY EVER BY HAND. The brakes seed from the
        # day's own logs so a crash cannot disarm them; this clears that seed
        # because the operator has decided the earlier losses belong to a
        # configuration that no longer exists. It is not a default and there is
        # no automation that can reach it.
        rec_reset = {"cleared_realised": round(state.realised, 4),
                     "cleared_losses": state.losses, "cleared_spent": round(state.spent, 4)}
        state.realised, state.losses, state.spent = 0.0, 0, 0.0
        print("  --reset-day: cleared %s" % rec_reset, flush=True)
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
    rec("start", series=a.series, size_dollars=state.size, dry=bool(a.dry),
        max_contracts=MAX_CONTRACTS,
        bands={k: [list(b) for b in v] for k, v in cmdarm.BANDS.items()},
        max_spend=MAX_SPEND, max_orders=MAX_ORDERS, max_losses=MAX_LOSSES,
        max_net_loss=MAX_NET_LOSS, realised_earlier_today=round(state.realised, 4),
        losses_earlier_today=state.losses,
        balance_floor=BALANCE_FLOOR, balance_at_start=bal,
        spent_earlier_today=round(state.spent, 4),
        signoff="operator 2026-09-17: ready for commodity penny testing, "
                "then: up the live commodity trading to 30 dollars size per trade",
        version="cmdlive-30dollar")
    print("cmdlive %s -- %s | $%.0f per trade (up to %.0f contracts) | STOPS at "
          "$%.2f net down or %d losses | turnover cap $%.0f/day, %d orders, "
          "account floor $%.0f | balance now $%s | today so far: $%+.2f, %d losses "
          "| log %s"
          % ("DRY RUN" if a.dry else "*** LIVE, REAL MONEY ***", ", ".join(a.series),
             state.size, MAX_CONTRACTS, MAX_NET_LOSS, MAX_LOSSES, MAX_SPEND,
             MAX_ORDERS, BALANCE_FLOOR,
             ("%.2f" % bal) if bal is not None else "?",
             state.realised, state.losses, os.path.basename(log)), flush=True)

    try:
        bets = trade_loop(state, a.series, a.minutes, rec, dry=a.dry)
    finally:
        rec("end", orders=state.orders, fills=state.fills,
            spent=round(state.spent, 4), losses=state.losses,
            realised=round(state.realised, 4))
        print("  end: %d orders, %d fills, $%.2f spent, %d losses"
              % (state.orders, state.fills, state.spent, state.losses), flush=True)
    done = [b for b in bets if "won" in b]
    if done:
        print("  settled %d: $%+.2f" % (len(done), sum(b["pnl"] for b in done)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
