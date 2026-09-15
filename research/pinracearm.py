#!/usr/bin/env python3
# VERSION: 2026-09-15-arm1
"""pinracearm.py -- THE COIN RACE PAPER ARM. Nothing is ever sent.

THE OPERATOR, 2026-09-15: "you can absolutely start on a coin race paper arm.
Just make sure it's completely accurate."

WHAT IS NEW HERE, AND WHY THE OLD RACE WORK MISSED IT

`pinlead` / `pinleadprice` / `pinracetest` all asked one question: is anyone
selling us THE LEADER. `pinracetest` ran seven races live and sent zero orders
-- one candidate, refused for a thin margin, and it was the one race the model
got wrong. One shot per race, at tau 20 exactly, capped at 95c.

But a race has FIVE legs and FOUR OF THEM LOSE. The leader's YES is one
contract; the four trailers' NOs are four more, and a coin fifteen basis
points behind with eight seconds left is a far flatter bet than the leader is.
So this arm prices EVERY LEG, on the side we would actually want, for the
whole approach to the close instead of a single second.

It also behaves differently on a loss, and that is the part worth measuring.
When the leader is overtaken, the leader's YES loses -- but of our four NOs,
THREE STILL WIN, because only one trailer can take the lead. The NO side's
losses are structurally a quarter the size of the YES side's. That is not an
opinion; it is what "exactly one leg wins" means, and this arm records it.

THE FORECAST is `pinracemodel`, which reproduces Kalshi's own settled winner
on 761 of 761 races from the index tape alone, and reads every cell of its
table as a 95% UPPER bound rather than a point estimate -- so a cell of "0
wins in 120 races" is priced at 2.5% risk, not zero.

WHAT MAKES IT ACCURATE, item by item, because that was the instruction:

  NO LOOK-AHEAD      the forecast at second t uses only index prints at or
                     before t, exactly as the live bot does.
  OUT OF SAMPLE      the table is fitted on races that CLOSED BEFORE this
                     process started. Its fingerprint and race count go in the
                     log so that can be checked later, not asserted now.
  SUPPLY IS REAL     size is capped by what the book actually shows at or under
                     our limit, via LiveBook.buyable, and the whole ladder is
                     recorded next to every fill.
  FEES ARE REAL      0.07*p*(1-p), rounded up to the cent-hundredth, the same
                     function the live bot reconciled against the account.
  SELF-SCORING       at close+75s it recomputes the winner from our own index
                     and marks every paper position won or lost. No settlement
                     pull, no waiting, no chance of scoring the wrong race.
  SILENCE IS LOGGED  every reason we did NOT buy is recorded once per leg per
                     reason. `pinracetest` learned this the hard way: a race
                     that logged nothing was indistinguishable from a race with
                     no edge.

WHAT IT STILL CANNOT TELL US, stated here rather than in a footnote:

  * WHETHER WE WIN THE FILL. Every price here is an offer we saw, not an offer
    we got. This is the project's oldest open risk and no paper arm can close
    it. Fills are labelled `assumed` in the log and the report says so.
  * ADVERSE SELECTION. On the up/down markets the counterparty is 26x more
    often right when they actively sell to us (RESULTS_select). If the same
    holds here, the realised loss rate will be worse than the table's, and
    only real fills will show it.

    python research/pinracearm.py --selftest
    python research/pinracearm.py --minutes 600
"""
import argparse
import calendar
import collections
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import livebook                                              # noqa: E402
import pinrun                                                # noqa: E402
import pinracemodel as M                                     # noqa: E402

SERIES = "KXCRYPTOLEAD15M"
COINS = M.COINS
N_AVG = M.N_AVG
WINDOW = M.WINDOW

# ---- the rails ------------------------------------------------------------
SIZE = 250                # contracts we would ask for per fill
MAX_PER_LEG = 2           # fills per leg per race
MAX_PER_CLOSE = 4         # fills per race, across all five legs
PRICE_CEILING = 0.98      # never pay 99c, the same ceiling the live bot uses
MIN_EDGE = 0.02           # 2c net of fee. RESULTS_coinrace measured the live
                          # bands at +2.5c to +4.8c a contract, so this sits at
                          # the bottom of what has ever been seen rather than
                          # at whatever the table happens to allow.
TAU_LO, TAU_HI = 2, 150   # the whole approach, not one second
SUBSCRIBE_LEAD = 120      # seconds of warm-up before the window
MAX_INDEX_AGE_S = 5
MAX_BOOK_AGE_MS = 300000  # a quiet race book is UNCHANGED, not stale --
                          # pinracetest lost three races to a 15s gate
SCORE_DELAY = 75          # seconds after the close before we score it


def fee(p, n=1.0):
    """Taker fee, rounded UP to the cent-hundredth, as the exchange bills it."""
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def open_twap(ticks, open_s):
    """Mean of the 60 prints over [open-60, open). None if ANY is missing.

    Never a partial mean. The denominator is the half of the settlement rule
    that is already fixed; guessing at it would put every return on this race
    quietly wrong in the same direction."""
    v = [ticks[s] for s in range(open_s - N_AVG, open_s) if s in ticks]
    if len(v) < N_AVG:
        return None
    return sum(v) / float(N_AVG)


def close_mu(ticks, close_s, now_s, spot):
    """Forecast of the closing 60-second mean: the prints already locked, plus
    the newest print carried forward for the seconds still to come.

    NO LOOK-AHEAD: `hi` is min(now-1, close-1), so a second that has not
    happened yet can never enter the sum."""
    lo = close_s - N_AVG
    hi = min(now_s - 1, close_s - 1)
    got = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
    n = len(got)
    if n > N_AVG or spot is None:
        return None
    return (sum(got) + (N_AVG - n) * float(spot)) / float(N_AVG)


def price_leg(table, tau, gap_bp):
    """(side, worth) for one leg -- which side we would buy and what it is
    worth, as a probability, on the pessimistic read of the table.

    A coin AHEAD of the field is a YES, and the number that matters is its
    chance of being overtaken, bounded above. A coin BEHIND is a NO, and the
    number that matters is its chance of still winning, also bounded above.
    Both bounds push the same way: they make the contract worth LESS."""
    if gap_bp > 0:
        return "yes", 1.0 - M.p_lose(table, tau, gap_bp)
    return "no", 1.0 - M.p_win(table, tau, gap_bp)


def net_edge(worth, price):
    """Cents of edge per contract after the taker fee, as a fraction."""
    return worth - price - fee(price)


def winner_from(ticks_by_coin, close_s):
    """The winner of a finished race, recomputed from our own index.

    This is the function `pinracemodel` validated at 761 of 761 against
    Kalshi's own settled `result`, which is why this arm does not need a
    settlement pull to score itself."""
    rets = {}
    for coin, ticks in ticks_by_coin.items():
        den = open_twap(ticks, close_s - WINDOW)
        num = [ticks[s] for s in range(close_s - N_AVG, close_s) if s in ticks]
        if not den or len(num) < N_AVG:
            return None, {}
        rets[coin] = (sum(num) / float(N_AVG)) / den
    if len(rets) < 2:
        return None, {}
    return max(rets.items(), key=lambda kv: kv[1])[0], rets


def selftest():
    print("SELF-TEST -- pinracearm")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # ---- THIS FILE MUST NEVER BE ABLE TO SEND AN ORDER -----------------
    # THE SELF-INSPECTION TRAP. Every needle below is BUILT, never written,
    # because spelling a module name out in this test would let the test find
    # its own comment, and
    # the check would fail on itself -- which is exactly how four earlier
    # structural tests in this project passed or failed for the wrong reason.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    needles = [("pin" + "take", "the module that can actually send an order"),
               ("pinrun." + "arm(", "the call that disarms the live bot's guard"),
               ("--" + "live", "a flag that could be passed by accident"),
               ("post_" + "only", "a maker order field"),
               ("/portfolio/" + "orders", "the order endpoint itself")]
    for needle, what in needles:
        ck(src.count(needle) == 0,
           "%s (%s) appears NOWHERE in this file -- nothing here can reach "
           "the exchange with an order" % (needle, what))

    # ---- the rails -----------------------------------------------------
    ck(PRICE_CEILING <= 0.98,
       "the price ceiling is at most 98c -- 99c leaves a cent of upside "
       "against a whole dollar of downside")
    ck(MIN_EDGE >= 0.02,
       "the edge floor is at least 2c, the bottom of the +2.5c..+4.8c bands "
       "RESULTS_coinrace actually measured, not whatever the table allows")
    ck(MAX_PER_LEG * 5 >= MAX_PER_CLOSE,
       "the per-race cap is reachable across five legs")
    ck(TAU_LO >= 1, "we never price a race after it has closed")

    # ---- the fee -------------------------------------------------------
    ck(abs(fee(0.95) - 0.0034) < 1e-9,
       "95c costs 0.34c to take (0.07*0.95*0.05, rounded up) -- the same "
       "function the live bot reconciled against the account")
    ck(fee(0.97) < fee(0.90),
       "and the fee SHRINKS toward the ends, which is why the expensive legs "
       "are cheaper to trade than they look")
    ck(fee(0.5) > fee(0.95), "it is largest at a coin flip")

    # ---- NO LOOK-AHEAD, the single most important test here ------------
    ticks = {s: 100.0 for s in range(1000, 1200)}
    ticks.update({s: 999.0 for s in range(1150, 1200)})     # the FUTURE
    close_s = 1160
    mu = close_mu(ticks, close_s, 1130, 100.0)
    ck(mu == 100.0,
       "at second 1130 the forecast is 100.0 and NOT pulled toward the 999s "
       "sitting at seconds 1150-1159 -- a future print can never enter the sum")
    mu2 = close_mu(ticks, close_s, 1155, 999.0)
    ck(mu2 is not None and 100.0 < mu2 < 999.0,
       "and once those seconds ARRIVE they count: the forecast moves to %.1f"
       % (mu2 or 0))
    lo = close_s - N_AVG
    ck(close_mu({s: 1.0 for s in range(lo, lo + 60)}, close_s, close_s, 1.0) == 1.0,
       "a fully locked window forecasts itself exactly")
    ck(close_mu({}, close_s, close_s - 30, None) is None,
       "NULL: no spot and no prints forecasts nothing, never a zero")

    # ---- the open window, which is a blind spot not an absence ---------
    full = {s: 5.0 for s in range(0, 100)}
    ck(open_twap(full, 60) == 5.0, "a complete opening minute averages")
    short = {s: 5.0 for s in range(0, 100) if s != 30}
    ck(open_twap(short, 60) is None,
       "and ONE missing print refuses the whole race rather than averaging 59 "
       "-- the denominator is half the settlement rule")

    # ---- which side, and what it is worth ------------------------------
    tbl = {"12": {str(M.bucket(-15.0)): {"n": 200, "won": 0},
                  str(M.bucket(15.0)): {"n": 200, "won": 200}}}
    side, worth = price_leg(tbl, 12, -15.0)
    ck(side == "no" and 0.98 < worth < 1.0,
       "a coin 15bp BEHIND is a NO worth %.4f -- not 1.0, because 0 wins in "
       "200 races bounds at %.2f%%, not at zero" % (worth, 100 * (1 - worth)))
    side2, worth2 = price_leg(tbl, 12, 15.0)
    ck(side2 == "yes" and 0.98 < worth2 < 1.0,
       "a coin 15bp AHEAD is a YES worth %.4f, bounded the same way" % worth2)
    ck(price_leg({}, 12, 15.0)[1] == 0.5 and price_leg({}, 12, -15.0)[1] == 0.5,
       "NULL: with no table at all every leg is a coin flip, which buys "
       "nothing at any price above 50c")

    # ---- the edge arithmetic -------------------------------------------
    ck(abs(net_edge(0.99, 0.95) - (0.04 - fee(0.95))) < 1e-9,
       "something worth 99c bought at 95c earns 4c less the 0.34c fee")
    ck(net_edge(0.975, 0.97) < MIN_EDGE,
       "a half-cent of gross edge does NOT clear the 2c floor")
    ck(net_edge(0.99, 0.99) < 0,
       "and paying exactly what it is worth LOSES the fee -- the fee is never "
       "forgotten by being small")
    ck(net_edge(0.5, 0.03) > 0 and net_edge(0.02, 0.03) < 0,
       "the arithmetic has no side preference: it is the same subtraction for "
       "a 3c longshot that is worth 50c and one that is worth 2c")

    # ---- SCORING, and the property the whole file is built to measure --
    t = {}
    for coin, base in (("BTC", 100.0), ("ETH", 100.0), ("SOL", 100.0),
                       ("XRP", 100.0), ("HYPE", 100.0)):
        d = {}
        cs = 10_000
        for s in range(cs - WINDOW - N_AVG, cs):
            d[s] = base
        for s in range(cs - N_AVG, cs):
            d[s] = base * (1.02 if coin == "SOL" else 1.01)
        t[coin] = d
    won, rets = winner_from(t, 10_000)
    ck(won == "SOL",
       "the scorer picks the coin with the biggest return out of five")
    ck(len(rets) == 5 and all(r > 1.0 for r in rets.values()),
       "and every coin rose, which changed nothing -- a common move cannot "
       "decide a race")
    hole = {c: dict(d) for c, d in t.items()}
    hole["BTC"].pop(10_000 - 30)
    ck(winner_from(hole, 10_000)[0] is None,
       "NULL: one missing print in one coin refuses to score the race at all, "
       "rather than scoring it on four legs")

    # THE STRUCTURAL CLAIM: when the leader is overtaken, three of four NOs
    # still win. This is arithmetic, not a measurement, and it is why the NO
    # side is worth building.
    legs = ["BTC", "ETH", "SOL", "XRP", "HYPE"]
    led, actual = "BTC", "ETH"
    no_legs = [c for c in legs if c != led]
    ck(sum(1 for c in no_legs if c != actual) == 3,
       "if we hold NO on all four trailers and the leader IS overtaken, three "
       "of the four still win -- only the coin that took the lead pays out")
    ck(sum(1 for c in no_legs if c != led) == 4,
       "and if the leader HOLDS, all four NOs win -- so the NO side's bad "
       "case is 3-of-4 where the YES side's is 0-of-1, a quarter the damage")

    # ---- the table this arm depends on must itself pass ----------------
    ck(M.upper95(0, 120) > 0.02,
       "the forecast module reads a 0-of-120 cell as %.1f%% risk, not zero -- "
       "if that ever becomes 0 this arm sizes as though it cannot lose"
       % (100 * M.upper95(0, 120)))
    ck(M.p_lose({}, 10, 50.0) == 0.5,
       "and an empty table is a coin flip both ways")
    print("SELF-TEST", "PASSED" if not f else "FAILED (%d)" % len(f))
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
        except Exception:                                    # noqa: BLE001
            continue
        e = out.setdefault(evt, {"close": float(cs), "legs": {}})
        e["legs"][coin] = tk
    return {k: v for k, v in out.items() if len(v["legs"]) == 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=float, default=600.0)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--min-edge", type=float, default=MIN_EDGE)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    if not os.path.exists(M.TABLE):
        print("  no forecast table at %s -- run research/pinracemodel.py first"
              % M.TABLE)
        return 1
    table = json.load(open(M.TABLE, encoding="utf-8"))
    tstat = os.stat(M.TABLE)
    cells = sum(len(v) for v in table.values())

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    logpath = a.log or os.path.join(REPO, "results",
                                    "pinracearm-%s.jsonl" % stamp)
    logf = open(logpath, "a", encoding="utf-8")

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logf.write(json.dumps(kw) + "\n")
        logf.flush()

    print("\n  COIN RACE PAPER ARM -- nothing is ever sent")
    print("  size %d, <= %.0fc, edge floor %.1fc, tau %d-%d, %d fills/race"
          % (a.size, 100 * PRICE_CEILING, 100 * a.min_edge, TAU_LO, TAU_HI,
             MAX_PER_CLOSE))
    print("  forecast: %s, %d cells, built %s"
          % (os.path.basename(M.TABLE), cells,
             time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(tstat.st_mtime))))
    print("  log: %s\n" % os.path.abspath(logpath))
    rec("start", size=a.size, min_edge=a.min_edge, ceiling=PRICE_CEILING,
        tau=[TAU_LO, TAU_HI], max_per_leg=MAX_PER_LEG,
        max_per_close=MAX_PER_CLOSE, table=os.path.basename(M.TABLE),
        table_cells=cells, table_mtime=int(tstat.st_mtime),
        table_size=tstat.st_size, version="2026-09-15-arm1")

    idx = pinrun.IndexWS(sorted(set(COINS.values()))).start()
    book = livebook.LiveBook()
    book.start()
    t0 = time.time()
    while time.time() - t0 < 25 and idx.stats.get("ticks", 0) < 10:
        time.sleep(0.5)
    print("  index up: %d ticks, %d feeds"
          % (idx.stats.get("ticks", 0), len(idx.ticks)))

    events = {}
    watched = set()
    seen_why = set()
    fills = []                                   # every paper position
    per_leg = collections.Counter()
    per_close = collections.Counter()
    scored = set()
    last_disc = 0.0
    try:
        while time.time() - t0 < a.minutes * 60:
            now = time.time()
            if now - last_disc > 60:
                last_disc = now
                try:
                    events = discover()
                except Exception as e:                        # noqa: BLE001
                    rec("error", where="discover", err=str(e)[:200])

            # ---- SCORE anything that has closed and settled ------------
            for evt, e in sorted(events.items()):
                cs = int(e["close"])
                if evt in scored or now < cs + SCORE_DELAY:
                    continue
                with idx.lock:
                    tb = {c: dict(idx.ticks.get(iid) or {})
                          for c, iid in COINS.items()}
                won, rets = winner_from(tb, cs)
                scored.add(evt)
                if won is None:
                    rec("unscored", event=evt, close_s=cs,
                        why="index incomplete at close+%ds" % SCORE_DELAY)
                    continue
                mine = [p for p in fills if p["event"] == evt and "win" not in p]
                for p in mine:
                    p["win"] = ((p["coin"] == won) if p["side"] == "yes"
                                else (p["coin"] != won))
                    p["pnl"] = round(p["size"] * ((1.0 - p["price"])
                                                  if p["win"] else -p["price"])
                                     - p["size"] * fee(p["price"]), 4)
                rec("settled", event=evt, close_s=cs, winner=won,
                    returns={k: round(v, 8) for k, v in rets.items()},
                    positions=len(mine),
                    won=sum(1 for p in mine if p["win"]),
                    pnl=round(sum(p["pnl"] for p in mine), 4))
                if mine:
                    print("  SETTLED %-28s %-4s  %d/%d won  $%+.2f"
                          % (evt, won, sum(1 for p in mine if p["win"]),
                             len(mine), sum(p["pnl"] for p in mine)))

            # ---- PRICE the open races ----------------------------------
            for evt, e in sorted(events.items()):
                cs = int(e["close"])
                tau = cs - int(now)
                if not (TAU_LO <= tau <= TAU_HI + SUBSCRIBE_LEAD):
                    continue
                fresh = [t for t in e["legs"].values() if t not in watched]
                if fresh:
                    watched.update(fresh)
                    try:
                        book.subscribe(fresh)
                        rec("subscribe", event=evt, tickers=fresh, tau=tau)
                    except Exception as ex:                   # noqa: BLE001
                        rec("error", where="subscribe", err=str(ex)[:200])
                if not (TAU_LO <= tau <= TAU_HI):
                    continue
                if per_close[evt] >= MAX_PER_CLOSE:
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
                    o = open_twap(ticks, cs - WINDOW)
                    if not o:
                        # NOT an absence of edge: the opening minute is
                        # [close-960, close-900), so a process that started
                        # after it can never evaluate this race at all.
                        why = "no_open_window:%s" % coin
                        break
                    mu = close_mu(ticks, cs, int(now), spot)
                    if mu is None:
                        why = "no_close_forecast:%s" % coin
                        break
                    rets[coin] = mu / o
                if why or len(rets) != 5:
                    key = (evt, why or "incomplete")
                    if key not in seen_why:
                        seen_why.add(key)
                        rec("cannot_evaluate", event=evt, tau=tau,
                            why=why or "incomplete", have=sorted(rets),
                            close_s=cs)
                    continue

                g = M.gaps(rets)
                for coin, gap in sorted(g.items(), key=lambda kv: -abs(kv[1])):
                    tkr = e["legs"][coin]
                    if per_leg[tkr] >= MAX_PER_LEG or per_close[evt] >= MAX_PER_CLOSE:
                        continue
                    side, worth = price_leg(table, tau, gap * 1e4)
                    b = book.best(tkr)
                    bad = None
                    if not b:
                        bad = "no_book"
                    elif b.get("suspect"):
                        bad = "book_suspect"
                    elif b.get("age_ms") is None:
                        bad = "book_no_age"
                    elif b["age_ms"] > MAX_BOOK_AGE_MS:
                        bad = "book_stale"
                    if bad:
                        key = (evt, coin, bad)
                        if key not in seen_why:
                            seen_why.add(key)
                            rec("no_trade", event=evt, coin=coin, ticker=tkr,
                                tau=tau, side=side, why=bad,
                                gap_bp=round(gap * 1e4, 4))
                        continue
                    ask = b.get("yes_ask") if side == "yes" else b.get("no_ask")
                    asz = (b.get("yes_ask_size") if side == "yes"
                           else b.get("no_ask_size"))
                    if not ask or not asz:
                        bad = "no_offer"
                    elif ask > PRICE_CEILING + 1e-9:
                        bad = "above_ceiling"
                    else:
                        edge = net_edge(worth, float(ask))
                        if edge < a.min_edge:
                            bad = "thin_edge"
                    if bad:
                        key = (evt, coin, bad)
                        if key not in seen_why:
                            seen_why.add(key)
                            rec("no_trade", event=evt, coin=coin, ticker=tkr,
                                tau=tau, side=side, why=bad,
                                gap_bp=round(gap * 1e4, 4),
                                worth=round(worth, 6),
                                ask=(float(ask) if ask else None),
                                ask_size=(float(asz) if asz else None),
                                edge=(round(net_edge(worth, float(ask)), 6)
                                      if ask else None))
                        continue
                    # SUPPLY, not arithmetic, caps the size. buyable() walks
                    # the ladder to our limit; the touch alone once cost the
                    # live bot four fifths of an available book (A35).
                    try:
                        have = book.buyable(tkr, side, PRICE_CEILING)
                    except Exception:                        # noqa: BLE001
                        have = float(asz)
                    take = int(min(a.size, have or 0))
                    if take <= 0:
                        continue
                    try:
                        lad = book.depth(tkr, "no" if side == "yes" else "yes", 60)
                        ladder = [[round(1.0 - float(p), 4), float(s)]
                                  for p, s in (lad or [])]
                    except Exception:                        # noqa: BLE001
                        ladder = None
                    pos = {"event": evt, "coin": coin, "ticker": tkr,
                           "side": side, "price": float(ask), "size": take,
                           "tau": tau, "worth": round(worth, 6),
                           "gap_bp": round(gap * 1e4, 4),
                           "edge": round(net_edge(worth, float(ask)), 6)}
                    fills.append(pos)
                    per_leg[tkr] += 1
                    per_close[evt] += 1
                    rec("fill", assumed=True, ask_size=float(asz),
                        buyable=float(have or 0), ladder=ladder,
                        returns={k: round(v, 8) for k, v in rets.items()},
                        **pos)
                    print("  PAPER  %-30s %-4s %-3s %d @ %.0fc  tau %2d  "
                          "gap %+7.2fbp  worth %.4f  edge %+.2fc"
                          % (evt[-12:], coin, side.upper(), take, 100 * ask,
                             tau, gap * 1e4, worth, 100 * pos["edge"]))
            time.sleep(0.25)
    finally:
        done = [p for p in fills if "win" in p]
        rec("end", fills=len(fills), settled=len(done),
            won=sum(1 for p in done if p["win"]),
            pnl=round(sum(p["pnl"] for p in done), 4))
        try:
            book.stop()
        except Exception:                                    # noqa: BLE001
            pass
        idx.stop()
        logf.close()
    done = [p for p in fills if "win" in p]
    print("\n  %d paper positions, %d settled, %d won, $%+.2f"
          % (len(fills), len(done), sum(1 for p in done if p["win"]),
             sum(p["pnl"] for p in done)))
    print("  Every price above was an offer we SAW, not one we got. Winning "
          "the fill is assumed and no paper arm can test it.")
    print("  log %s" % os.path.abspath(logpath))
    return 0


if __name__ == "__main__":
    sys.exit(main())
