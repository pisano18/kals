#!/usr/bin/env python3
# VERSION: 2026-09-11-rt1
"""pinracetest.py -- THE COIN RACE PENNY TEST. Ten one-contract buys, no more.

WHAT THIS IS FOR, AND THE ONE QUESTION IT ANSWERS
  pinlead.py showed the leader can be named (97.8% at tau 30, 99.5% at tau 20
  over 773 events) and pinleadprice.py showed somebody is paying ~94.7c for it
  at tau 15-20 against a 97.28c break-even. Every one of those prices is
  SOMEBODY ELSE'S FILL. The only thing left that tape cannot answer is whether
  WE can get one. That is the race, it is this project's oldest open risk, and
  a handful of real one-contract orders settles it for under ten dollars.

  IT IS NOT A STRATEGY AND IT IS NOT SIZED TO MAKE MONEY. Ten contracts at
  <=95c is at most $9.50 at risk, and the result that matters is the FILL
  RATE, not the P&L.

SCOPE OF THE SIGN-OFF, written down so it cannot drift
  The operator approved, in their own words, "a handful of one-contract buys
  in the last 20 seconds of a race, to check we can actually win the fills."
  This file is built to be incapable of exceeding that:

    SIZE           = 1 contract, a literal, not a parameter
    MAX_ATTEMPTS   = 10 orders, then it stops for good
    MAX_SPEND      = $10.00 of cumulative stake, then it stops for good
    PRICE_CAP      = 0.95, below the 97.28c break-even, so a fill is +EV
    TAU window     = [15, 20] seconds, the band that was measured
    --live         = required; without it nothing is sent and it only logs

  Every one of those is asserted by the self-test, including that no code path
  can raise them at runtime.

THE OPENING AVERAGE, and why it is not read from Kalshi
  A race settles on (closing 60s average / opening 60s average). The opening
  average is ALSO the strike Kalshi publishes for the up/down market closing
  on the same second -- but only to display precision. Checked on 720 pairs:
  they agree to 3.7e-05 relative and to 1e-6 on just 72% of them, because
  floor_strike is rounded to round_digits. So the opening average is computed
  from our own index feed, which reproduced settlement on 773 of 773 events,
  and the published strike is carried alongside only as a cross-check.
"""
import argparse
import json
import math
import os
import sys
import time
import calendar
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import livebook                                              # noqa: E402
import pinrun                                                # noqa: E402

COINS = {"BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI",
         "XRP": "XRPUSD_RTI", "HYPE": "HYPEUSD_RTI"}
N_AVG = 60
SERIES = "KXCRYPTOLEAD15M"

# ---- THE RAILS. Literals. Nothing reassigns these; the self-test proves it.
SIZE = 1                  # contracts per order
MAX_ATTEMPTS = 10         # orders ever sent by one process
MAX_SPEND = 10.00         # dollars of cumulative stake, then stop
PRICE_CAP = 0.95          # never pay more; break-even at tau 15-20 is 97.28c
TAU_LO, TAU_HI = 15, 20   # the measured band
SUBSCRIBE_LEAD = 100      # seconds before the decision window to subscribe
MAX_INDEX_AGE_S = 5

# BOOK STALENESS. pinrun uses 2000ms and that is right for the up/down books,
# which churn constantly. Coin Race books are QUIET: measured 2026-09-12, three
# of five races were refused with ages of 27s, 83s and 89s. A delta-maintained
# book that receives no deltas is not stale, it is UNCHANGED -- age_ms is time
# since the last message, not time since the book was last correct.
#
# The real risk a staleness gate guards against is a silently dead socket, and
# that is a property of the CONNECTION, not of one ticker. So: allow a long
# per-ticker age, and separately require that the socket has heard from
# SOMETHING recently.
MAX_BOOK_AGE_MS = 300000      # 5 minutes: a quiet book is still a book
MAX_FEED_SILENCE_MS = 15000   # but the socket itself must be alive

# MARGIN GATE. Our one paper candidate (2026-09-12 01:15) was a photo finish:
# HYPE +0.23203% against SOL +0.23101%, a margin of 0.00102%, and SOL won. The
# market was asking 81c precisely because it was close, and the market was
# right. Measured over 530 events at tau 20:
#     margin < 0.005%   23 events    83-91% correct
#     margin >= 0.005%  507 events   100.0% correct  [98.8, 100.0]
# So the gate is set at 0.005% of return. It would have refused exactly the
# race we got wrong and kept every race we got right.
MIN_MARGIN = 0.00005          # 0.005% of return, as a fraction


def fee(p, n=1.0):
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def open_twap(ticks, open_s):
    """Mean of the 60 prints over [open-60, open-1]; None if any are missing.

    Never a partial mean. A missing print means we cannot reconstruct the
    denominator settlement used, and the honest answer is to stand aside.
    """
    v = [ticks[s] for s in range(open_s - N_AVG, open_s) if s in ticks]
    if len(v) < N_AVG:
        return None
    return sum(v) / float(N_AVG)


def close_mu(ticks, close_s, now_s, spot):
    """Forecast of the closing 60s average: locked prints plus spot for the rest."""
    lo = close_s - N_AVG
    hi = min(now_s - 1, close_s - 1)
    got = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
    n = len(got)
    if n > N_AVG or spot is None:
        return None
    return (sum(got) + (N_AVG - n) * float(spot)) / float(N_AVG)


def feed_silence_ms(book, now_ms=None):
    """Milliseconds since the socket last delivered ANY book message.

    This is the honest test for "is the connection dead", which is the only
    thing a staleness gate should refuse on. A single ticker going quiet means
    nobody changed their order, not that we lost the feed. Returns None when
    no book has ever arrived, which the caller treats as no_book.
    """
    t = now_ms if now_ms is not None else livebook.now_ms()
    try:
        with book.lock:
            rx = [m["rx_ms"] for m in book.meta.values()
                  if m.get("rx_ms") is not None]
    except Exception:                                        # noqa: BLE001
        return None
    if not rx:
        return None
    return t - max(rx)


def leader(rets):
    """(winner set, margin first-to-second). A tie names every tied leg."""
    if len(rets) < 2:
        return set(), 0.0
    o = sorted(rets.items(), key=lambda kv: -kv[1])
    top = o[0][1]
    return {k for k, v in rets.items() if v >= top - 1e-15}, top - o[1][1]


class Rails:
    """The only thing that may authorise an order. Counts down, never up."""

    def __init__(self):
        self.attempts = 0
        self.spent = 0.0
        self.stopped = None
        self.lock = threading.RLock()

    def check(self, price, size):
        """Returns a list of refusals. Empty list means the order may go."""
        bad = []
        if self.stopped:
            bad.append("already stopped: " + self.stopped)
        if size != SIZE:
            bad.append("size %r is not the sanctioned %d" % (size, SIZE))
        if not (0 < price <= PRICE_CAP):
            bad.append("price %.4f outside (0, %.2f]" % (price, PRICE_CAP))
        if self.attempts >= MAX_ATTEMPTS:
            bad.append("attempt cap %d reached" % MAX_ATTEMPTS)
        if self.spent + price * size > MAX_SPEND + 1e-9:
            bad.append("spend cap $%.2f would be exceeded (spent $%.2f)"
                       % (MAX_SPEND, self.spent))
        return bad

    def book(self, price, size):
        with self.lock:
            self.attempts += 1
            self.spent += price * size
            if self.attempts >= MAX_ATTEMPTS:
                self.stopped = "attempt cap reached"
            elif self.spent >= MAX_SPEND - 1e-9:
                self.stopped = "spend cap reached"


def selftest():
    print("SELF-TEST -- pinracetest")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # ---- the rails, which are the whole point of this file ---------------
    ck(SIZE == 1 and MAX_ATTEMPTS == 10 and MAX_SPEND == 10.00
       and PRICE_CAP == 0.95 and (TAU_LO, TAU_HI) == (15, 20),
       "the sanctioned scope is exactly 1 contract, 10 orders, $10, 95c, tau 15-20")
    r = Rails()
    ck(r.check(0.94, 1) == [], "an in-scope order is allowed")
    ck(r.check(0.96, 1), "a price above the 95c cap is refused")
    ck(r.check(0.94, 2), "a size of 2 is refused -- the literal is 1")
    ck(r.check(0.0, 1) and r.check(-0.5, 1), "zero and negative prices refused")
    for _ in range(MAX_ATTEMPTS):
        r.book(0.50, 1)
    ck(r.check(0.50, 1), "after %d attempts every further order is refused"
       % MAX_ATTEMPTS)
    ck(r.stopped is not None, "and the rail latches stopped, it does not reset")
    # WORST CASE, stated as arithmetic rather than as a hope. Ten orders at
    # the 95c cap is $9.50, so MAX_SPEND = $10 is a backstop that CANNOT bind
    # while PRICE_CAP is 0.95. The first version of this test asserted the
    # spend cap bites first, which is false; the bound that actually holds is
    # the product, and that is what is asserted now.
    ck(MAX_ATTEMPTS * PRICE_CAP * SIZE <= MAX_SPEND,
       "worst case is %d x %.2f = $%.2f, inside the $%.2f backstop"
       % (MAX_ATTEMPTS, PRICE_CAP, MAX_ATTEMPTS * PRICE_CAP * SIZE, MAX_SPEND))
    r2 = Rails()
    tot = 0.0
    for _ in range(MAX_ATTEMPTS + 5):
        if r2.check(PRICE_CAP, SIZE):
            break
        r2.book(PRICE_CAP, SIZE)
        tot += PRICE_CAP
    ck(tot <= MAX_ATTEMPTS * PRICE_CAP + 1e-9 and r2.attempts <= MAX_ATTEMPTS,
       "a rail driven until it refuses spends at most $%.2f over %d orders"
       % (MAX_ATTEMPTS * PRICE_CAP, MAX_ATTEMPTS))
    r3 = Rails()
    r3.stopped = "operator"
    ck(r3.check(0.10, 1), "a stopped rail refuses even a 10c order")
    # THE CAPS MUST BE LITERALS NO PATH CAN RAISE. Match only a real binding
    # at the start of a line -- an earlier version matched its own `==`
    # assertion and failed on correct code.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for name in ("MAX_ATTEMPTS", "MAX_SPEND", "PRICE_CAP", "SIZE"):
        binds = [ln for ln in src.split("\n")
                 if ln.startswith(name + " = ")]
        rebind = [ln for ln in src.split("\n")
                  if ln.strip().startswith(name + " = ") and ln[:1] in " \t"]
        ck(len(binds) == 1 and not rebind,
           "%s is bound once at module level and never reassigned" % name)

    # ---- the settlement arithmetic ---------------------------------------
    tk = {s: 2.0 for s in range(940, 1000)}
    ck(open_twap(tk, 1000) == 2.0, "a flat 60-print window averages to the level")
    ck(open_twap({s: 1.0 for s in range(941, 1000)}, 1000) is None,
       "59 prints is not a window -- None, never a partial mean")
    tk2 = {s: float(s) for s in range(940, 1000)}
    ck(open_twap(tk2, 1000) == 969.5, "a ramp averages to the midpoint")
    ck(close_mu({s: 1.0 for s in range(940, 980)}, 1000, 980, 1.0) == 1.0,
       "40 locked prints at 1.0 plus spot 1.0 forecasts 1.0")
    got = close_mu({s: 0.0 for s in range(940, 980)}, 1000, 980, 60.0)
    ck(abs(got - 20.0) < 1e-12,
       "40 zeros and a spot of 60 forecasts (0 + 20*60)/60 = 20, not 60")

    w, m = leader({"BTC": 0.01, "ETH": 0.02})
    ck(w == {"ETH"} and abs(m - 0.01) < 1e-12, "the leader is the largest return")
    ck(leader({"A": 1.0, "B": 1.0})[0] == {"A", "B"}, "an exact tie names both")
    ck(leader({"A": 1.0})[0] == set(),
       "one leg is not a race -- it names nobody rather than guessing")

    # ---- PLANTED: a decided race is called, a dead heat is not -----------
    close = 10000
    tks = {}
    for c in COINS:
        base = 100.0
        tks[c] = {s: base for s in range(close - 960, close - 900)}
        drift = 1.02 if c == "HYPE" else 1.0
        tks[c].update({s: base * drift for s in range(close - 60, close - 19)})
    rets = {}
    for c in COINS:
        o = open_twap(tks[c], close - 900)
        mu = close_mu(tks[c], close, close - 20, tks[c][close - 20])
        rets[c] = mu / o - 1.0
    ck(leader(rets)[0] == {"HYPE"}, "a planted 2% leader is named at tau 20")
    flat = {}
    for c in COINS:
        flat[c] = {s: 100.0 for s in range(close - 960, close - 900)}
        flat[c].update({s: 100.0 for s in range(close - 60, close - 19)})
    r2 = {}
    for c in COINS:
        r2[c] = (close_mu(flat[c], close, close - 20, 100.0)
                 / open_twap(flat[c], close - 900) - 1.0)
    ck(len(leader(r2)[0]) == 5 and leader(r2)[1] == 0.0,
       "a dead heat names all five with zero margin, so the margin gate can see it")

    ck(abs(fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee matches the account's own reconciled charge")
    ck(0.95 < 0.9728, "the price cap sits BELOW the measured break-even")

    # ---- THE REGRESSION GUARD for the bug that wasted two races ----------
    # LiveBook.watch() records a trajectory and subscribes to NOTHING. Calling
    # it instead of subscribe() left every book empty and produced `no_book`
    # on a ticker the log cheerfully reported as `watched: True`.
    ck("book.subscribe(" in src,
       "the loop calls book.subscribe() -- the method that actually asks the "
       "exchange for a book")
    # Match a CALL -- a line whose first token is the call -- not a mention.
    # A plain substring test matches this very assertion and the comment above
    # it. That is the SECOND time in this file a self-test has failed on its
    # own text (the first was the "assigned exactly once" check), so the rule
    # is now explicit: a source assertion must anchor to line structure.
    ck(not [ln for ln in src.split("\n")
            if ln.strip().startswith("book.watch(")],
       "and never CALLS book.watch(), which only records a trajectory")
    ck(SUBSCRIBE_LEAD >= 60,
       "there is at least a minute of warm-up before the decision window "
       "(%ds) -- one shot per race, so a cold book wastes the whole race"
       % SUBSCRIBE_LEAD)

    # ---- the margin gate, set from 530 measured events -------------------
    ck(abs(MIN_MARGIN - 0.00005) < 1e-12,
       "the margin gate is 0.005%% of return, the level above which 507 of "
       "507 events were called correctly")
    _, m_tight = leader({"HYPE": 0.0023203, "SOL": 0.0023101, "XRP": 0.0021411})
    ck(m_tight < MIN_MARGIN,
       "the real photo finish we got WRONG (HYPE vs SOL, 2026-09-12 01:15) "
       "is refused by the gate")
    _, m_ok = leader({"A": 0.0023203, "B": 0.0021411})
    ck(m_ok >= MIN_MARGIN,
       "a 0.018%% margin, comfortably inside the 100%%-correct band, passes")

    # ---- feed silence is a CONNECTION property, not a ticker property ----
    class _FakeBook:
        def __init__(self, rx):
            self.lock = threading.RLock()
            self.meta = {("t%d" % i): {"rx_ms": v} for i, v in enumerate(rx)}
    ck(feed_silence_ms(_FakeBook([1000, 5000, 9000]), now_ms=9200) == 200,
       "silence is measured from the NEWEST message on any ticker")
    ck(feed_silence_ms(_FakeBook([])) is None,
       "and a book that has never received anything reports None, not zero")
    # IT IS DELIBERATELY NOT USED AS A GATE. The only tickers we subscribe to
    # are the five Coin Race legs and they go quiet together, so gating on it
    # re-created the bug it replaced and cost the 03:00 race on 2026-09-12.
    ck("feed_silent" not in [ln.strip().split("=")[-1].strip().strip('"')
                             for ln in src.split(chr(10))
                             if ln.strip().startswith("bad = ")],
       "and it is NOT used to refuse a trade -- index freshness and the "
       "suspect flag already prove the socket is alive")
    ck(MAX_BOOK_AGE_MS >= 60000,
       "one quiet ticker is tolerated for at least a minute (%ds) -- an "
       "unchanged book is not a stale one" % (MAX_BOOK_AGE_MS // 1000))
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for x in f:
        print("   - " + x)
    return not f


def discover():
    """Open Coin Race events -> {event: {"close": epoch, "legs": {coin: tk}}}."""
    sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    from kauth import get
    st, b = get("/markets", {"series_ticker": SERIES, "status": "open",
                             "limit": "200"})
    if st != 200 or not isinstance(b, dict):
        return {}
    out = {}
    for m in b.get("markets", []):
        tk = m.get("ticker") or ""
        evt, _, leg = tk.rpartition("-")
        coin = (m.get("custom_strike") or {}).get("Cryptocurrency") or leg
        if coin not in COINS:
            continue
        try:
            cs = calendar.timegm(time.strptime(m["close_time"],
                                               "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            continue
        e = out.setdefault(evt, {"close": float(cs), "legs": {}})
        e["legs"][coin] = tk
    return {k: v for k, v in out.items() if len(v["legs"]) == 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="actually send orders (operator sign-off required)")
    ap.add_argument("--minutes", type=float, default=90.0)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logpath = os.path.join(HERE, "..", "results",
                           "pinracetest-%s.jsonl" % stamp)
    logf = open(logpath, "a", encoding="utf-8")

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logf.write(json.dumps(kw) + "\n")
        logf.flush()

    rails = Rails()
    rec("start", live=bool(a.live), size=SIZE, max_attempts=MAX_ATTEMPTS,
        max_spend=MAX_SPEND, price_cap=PRICE_CAP, tau_lo=TAU_LO, tau_hi=TAU_HI,
        series=SERIES, scope="operator approved a handful of 1-contract buys "
                             "in the last 20 seconds of a race")
    print("\n  COIN RACE PENNY TEST -- %s"
          % ("LIVE, real money" if a.live else "PAPER, nothing is sent"))
    print("  rails: %d contracts max, %d orders max, $%.2f max, <= %.0fc, "
          "tau %d-%d" % (SIZE, MAX_ATTEMPTS, MAX_SPEND, 100 * PRICE_CAP,
                         TAU_LO, TAU_HI))
    print("  log: %s\n" % os.path.abspath(logpath))

    if a.live:
        import pintake
        pinrun.arm("coin race penny test, 10 x 1 contract, operator approved "
                   "2026-09-11")

    idx = pinrun.IndexWS(sorted(set(COINS.values()))).start()
    book = livebook.LiveBook()
    book.start()
    t0 = time.time()
    while time.time() - t0 < 25 and idx.stats.get("ticks", 0) < 10:
        time.sleep(0.5)
    print("  index up: %d ticks, %d feeds"
          % (idx.stats.get("ticks", 0), len(idx.ticks)))

    events = {}
    done = set()
    seen_why = set()
    watched = set()
    last_disc = 0.0
    try:
        while time.time() - t0 < a.minutes * 60 and not rails.stopped:
            now = time.time()
            if now - last_disc > 60:
                last_disc = now
                try:
                    events = discover()
                except Exception as e:                        # noqa: BLE001
                    rec("error", where="discover", err=str(e)[:200])
            for evt, e in sorted(events.items()):
                cs = int(e["close"])
                tau = cs - int(now)
                # SUBSCRIBE_LEAD seconds of warm-up before the decision window.
                # 25s was the first value and it is too tight: a subscribe has
                # to be queued, sent, acked and answered with a snapshot before
                # best() returns anything, and we only get one shot per race.
                if evt in done or not (TAU_LO <= tau <= TAU_HI + SUBSCRIBE_LEAD):
                    continue
                # SUBSCRIBE, not watch. LiveBook.watch() only records a
                # ticker's top-of-book TRAJECTORY for comparison against a
                # REST read -- it asks the exchange for nothing. The first
                # version called it and then wondered why every book was
                # empty: the 00:15 race on 2026-09-12 logged `no_book` with
                # `watched: True`, which is what caught this. subscribe() is
                # the method that actually adds a ticker to `wanted` and
                # pokes the socket.
                fresh = [t for t in e["legs"].values() if t not in watched]
                if fresh:
                    watched.update(fresh)
                    try:
                        book.subscribe(fresh)
                        rec("subscribe", event=evt, tickers=fresh, tau=tau)
                    except Exception as ex:                   # noqa: BLE001
                        rec("error", where="subscribe", tickers=fresh,
                            err=str(ex)[:200])
                if not (TAU_LO <= tau <= TAU_HI):
                    continue
                rets = {}
                why = None
                for coin, iid in COINS.items():
                    with idx.lock:
                        ticks = dict(idx.ticks.get(iid) or {})
                    sec, spot, iage = idx.spot(iid)
                    if spot is None or iage is None or iage > MAX_INDEX_AGE_S:
                        why = "stale_index:%s" % coin
                        break
                    o = open_twap(ticks, cs - 900)
                    mu = close_mu(ticks, cs, int(now), spot)
                    if o is None or not o:
                        # THE BLIND SPOT THIS RECORD EXISTS FOR. The opening
                        # 60 prints are [close-960, close-900). A process that
                        # started after that minute can NEVER evaluate this
                        # event, and the first version simply fell through and
                        # logged nothing -- indistinguishable from "no edge".
                        # It means the first evaluable race is the one whose
                        # window opens after launch, i.e. up to 15 minutes in.
                        why = "no_open_window:%s" % coin
                        break
                    if mu is None:
                        why = "no_close_forecast:%s" % coin
                        break
                    rets[coin] = mu / o - 1.0
                if why or len(rets) != 5:
                    if evt not in done:
                        rec("cannot_evaluate", event=evt, tau=tau,
                            why=why or "incomplete",
                            have=sorted(rets), close_s=cs)
                        done.add(evt)
                    continue
                win, margin = leader(rets)
                if len(win) != 1:
                    rec("skip", event=evt, why="tie_or_incomplete", tau=tau)
                    done.add(evt)
                    continue
                if margin < MIN_MARGIN:
                    # A photo finish. Stand aside -- see MIN_MARGIN above.
                    if (evt, "thin_margin") not in seen_why:
                        seen_why.add((evt, "thin_margin"))
                        rec("no_trade", event=evt, coin=sorted(win)[0],
                            ticker=e["legs"][sorted(win)[0]], tau=tau,
                            why="thin_margin", margin=round(margin, 9),
                            min_margin=MIN_MARGIN, yes_ask=None,
                            yes_ask_size=None, no_bid=None, watched=True)
                    continue
                coin = next(iter(win))
                tkr = e["legs"][coin]
                # EVERY REASON WE DO NOT BUY IS RECORDED, ONCE PER EVENT PER
                # REASON. The first version `continue`d silently here, so the
                # 23:45 race on 2026-09-11 produced NO log line at all -- the
                # same "silence looks like no edge" failure the
                # cannot_evaluate record was added to kill, one stage later.
                # "nobody was offering the winner" is the single most valuable
                # thing this test can learn, and it was the invisible case.
                b = book.best(tkr)
                bad = None
                if not b:
                    bad = "no_book"
                elif b.get("suspect"):
                    bad = "book_suspect"
                elif b.get("age_ms") is None:
                    bad = "book_no_age"
                # NO FEED-SILENCE GATE HERE, and that is deliberate.
                # v1 refused when no book message had arrived on ANY watched
                # ticker for 15s -- but the only tickers we watch are the five
                # Coin Race legs, and they are ALL quiet together. So the
                # check re-created, at connection level, exactly the bug it
                # replaced: it fired on 2026-09-12 03:00 and cost a race.
                # Liveness is already established twice over before we get
                # here: every one of the five index feeds was checked fresh
                # within MAX_INDEX_AGE_S (they publish once a second no matter
                # what the market does), and a reconnect sets `suspect` on
                # every book until a new snapshot arrives. A quiet order book
                # is the one thing that is NOT evidence of a dead socket.
                elif b["age_ms"] > MAX_BOOK_AGE_MS:
                    bad = "book_stale"       # no ms in the label: it is the
                                             # dedupe key, and a per-millisecond
                                             # label wrote 24 records per race
                else:
                    ask, asz = b.get("yes_ask"), b.get("yes_ask_size")
                    if not ask:
                        bad = "no_yes_ask"          # nobody offering the winner
                    elif not asz:
                        bad = "ask_zero_size"
                    elif ask >= 1.0:
                        bad = "ask_at_a_dollar"
                if bad:
                    key = (evt, bad)
                    if key not in seen_why:
                        seen_why.add(key)
                        rec("no_trade", event=evt, coin=coin, ticker=tkr,
                            tau=tau, why=bad, margin=round(margin, 8),
                            yes_ask=(b or {}).get("yes_ask"),
                            yes_ask_size=(b or {}).get("yes_ask_size"),
                            no_bid=(b or {}).get("no_bid"),
                            watched=tkr in watched)
                    continue
                ask, asz = b.get("yes_ask"), b.get("yes_ask_size")
                refusals = rails.check(float(ask), SIZE)
                rec("candidate", event=evt, coin=coin, ticker=tkr, tau=tau,
                    ask=round(float(ask), 4), ask_size=float(asz),
                    margin=round(margin, 8),
                    returns={k: round(v, 8) for k, v in rets.items()},
                    refusals=refusals, live=bool(a.live))
                if refusals:
                    if any("cap" in r for r in refusals):
                        done.add(evt)
                    continue
                done.add(evt)
                if not a.live:
                    rails.book(float(ask), SIZE)
                    print("  PAPER  %-34s %s @ %.0fc  tau %d"
                          % (tkr, coin, 100 * ask, tau))
                    continue
                try:
                    out = pintake.take(
                        pinrun.CREDS["base"], pinrun.CREDS["pk"],
                        pinrun.CREDS["key_id"], tkr, "yes", float(ask),
                        SIZE, float(cs), exchange_index=2)
                except Exception as ex:                       # noqa: BLE001
                    rec("error", where="take", ticker=tkr, err=str(ex)[:300])
                    continue
                rails.book(float(ask), SIZE)
                rec("order", event=evt, coin=coin, ticker=tkr, tau=tau,
                    ask=round(float(ask), 4),
                    filled=out.get("filled"), status=out.get("status"),
                    refused=out.get("refused"), order_id=out.get("order_id"),
                    exec_price=out.get("exec_price"))
                print("  ORDER  %-34s %s @ %.0fc  tau %d  filled=%s"
                      % (tkr, coin, 100 * ask, tau, out.get("filled")))
            time.sleep(0.25)
    finally:
        rec("end", attempts=rails.attempts, spent=round(rails.spent, 4),
            stopped=rails.stopped)
        try:
            book.stop()
        except Exception:
            pass
        idx.stop()
        logf.close()
    print("\n  %d orders, $%.2f staked, stopped: %s"
          % (rails.attempts, rails.spent, rails.stopped))
    print("  log %s" % os.path.abspath(logpath))


if __name__ == "__main__":
    main()
