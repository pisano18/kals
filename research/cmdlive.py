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

  GOLD    2-15 s at 90-99c, SKIPPING 08-14 ET (in the COMEX session that cell
          is 32 markets / 2 lost; outside it 117 / 0), plus a FAR window at
          91-180 s and 98-99c (129 markets, 0 lost -- the safest cell found).
  WTI     2-60 s at 95-99c (153 markets, 3 lost); 2-45 s at 90-95c.
  SILVER  2-5 s, the NEGATIVE control: it loses 5.4% of markets even there.
          If silver comes out ahead in this test, the test is wrong.

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
MAX_SPEND = 10.00           # dollars of cost across the entire run
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
        self.armed = False


def guard(state, tau, price, count, balance, stop=None):
    """Every reason NOT to send, in a list. Empty list means send.

    Runs before pintake's own rails, not instead of them: pintake refuses on
    the order body and the close time, this refuses on the money.
    """
    bad = []
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
    ck(cmdarm.BANDS is not None and "KXGOLD15M" in cmdarm.BANDS
       and "KXCOPPER15M" not in cmdarm.BANDS,
       "the windows come from cmdarm.BANDS -- one source for the paper control "
       "and the live test; copper and gas are in neither")
    g_near, g_far = cmdarm.BANDS["KXGOLD15M"]
    ck(cmdarm.decide({"yes_ask": 0.95, "yes_ask_size": 50.0, "age_ms": 100}, 10,
                     g_near, hour=11) is None,
       "the live test inherits the COMEX skip: no gold at 11:00 ET")
    ck(cmdarm.decide({"yes_ask": 0.985, "yes_ask_size": 50.0, "age_ms": 100}, 120,
                     g_far, hour=11) == ("yes", 0.985, 50.0),
       "...and inherits the far window: gold at 98.5c with 120 s left is a bet")

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

    # ---- the money ceilings
    s2 = State(); s2.armed = True; s2.spent = 9.50
    ck(guard(s2, **ok_args), "NULL: $9.50 spent + 95c is past the $10 run ceiling")
    s2.spent = 9.00
    ck(guard(s2, **ok_args) == [], "...but $9.00 spent leaves room for one more")
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
    head = src[:src.rindex("def " + "selftest(")]
    ck(head.count("arm_" + "prod(") == 1,
       "production is armed in exactly one place in the working code")
    ck(float(SIZE) == 1.0 and MAX_SPEND <= 10.0 and MAX_LOSSES <= 2,
       "the SHIPPED defaults are one contract, a $10 run ceiling and a 2-loss brake")
    print("cmdlive selftest: OK")


def trade_loop(state, series, minutes, rec, dry=False):
    """The loop. One paper-priced decision per market per window, guarded,
    then at most one order."""
    book = livebook.LiveBook().start()
    watching, pend, per_close, looked, bets = {}, {}, collections.Counter(), set(), []
    last_disc, last_bal, balance = 0.0, 0.0, None
    end = time.time() + minutes * 60
    while time.time() < end:
        now = time.time()
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
                refused = guard(state, tau, px, n, balance, stopped())
                if refused:
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
                out = pintake.take(state.creds["base"], state.creds["pk"],
                                   state.creds["key_id"], tk, want, px, n,
                                   close_s, exchange_index=exi)
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
                    if not sc["won"]:
                        state.losses += 1
                    rec("settled", ticker=t, result=got[t], won=sc["won"],
                        pnl_c=round(100 * sc["pnl"], 2), losses=state.losses)
                    print("  SETTLED %s -> %s  $%+.2f   (losses %d/%d)"
                          % (t, "WON" if sc["won"] else "LOST", sc["pnl"],
                             state.losses, MAX_LOSSES), flush=True)
                if state.losses >= MAX_LOSSES:
                    with open(STOP_FILE, "w", encoding="utf-8") as fh:
                        fh.write("%d losses at %s\n" % (state.losses, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
                    rec("brake", losses=state.losses)
                    print("  *** %d LOSSES -- BRAKE. stop file written. ***" % state.losses, flush=True)
        time.sleep(0.25)
    return bets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--signoff", default=None)
    ap.add_argument("--dry", action="store_true",
                    help="arm, guard, log what WOULD be sent, send nothing")
    ap.add_argument("--series", nargs="*", default=sorted(cmdarm.BANDS))
    ap.add_argument("--size", type=float, default=SIZE)
    ap.add_argument("--minutes", type=float, default=1440)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()

    state = State(size=a.size)
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
        balance_floor=BALANCE_FLOOR, balance_at_start=bal,
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
