"""pinlook.py -- every opportunity, second by second, with our decision beside it.

WHY THIS EXISTS. The operator, 2026-09-18: *"I want to look through every
single opportunity myself. Every 15 minutes, every coin, just its raw data.
What price it was at each second from 30 all the way down, what the order book
looked like, whatever else I'm missing, and whatever other data you capture and
then something showing your decision and why. And then I want to see the best
like maybe 15-30 numbers today... and then the same thing for on the 13th."*

Everything the bot could see at the moment it decided, laid out so a human can
audit the decision rather than take my word for it. Four sources, joined on
(market, second):

  index     cfbenchmarks_value   the settlement index, one print a second
  book      ticker               best bid and ask, every update
  trades    trade                every print, price, size and which side took
  us        pinrun-live-*.jsonl  signal / refused / order / settled, with the
                                 gate name and the model's own fair value

THE RANKING IS BY WHAT WAS AVAILABLE, NOT BY WHAT WE DID. "Best opportunity"
means the cheapest ask on the side that went on to WIN, inside our window --
whether we bought it, refused it, or never saw it. A list of our own trades
would only ever show what we already know.

WHAT IT CANNOT SHOW, said plainly: the full depth ladder second by second.
That needs the orderbook_delta channel replayed from a snapshot, which is
millions of messages a day. The touch (best bid/ask) is here every second, and
the FULL ladder is here for any moment we ourselves recorded one -- our signal
records carry it. Everything else is the touch.
"""
import argparse
import collections
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DATA = r"C:\kals\kalshi_data"

CRYPTO = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M")
SERIES_INDEX = {"KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI",
                "KXSOL15M": "SOLUSD_RTI", "KXXRP15M": "XRPUSD_RTI",
                "KXDOGE15M": "DOGEUSD_RTI", "KXBNB15M": "BNBUSD_RTI",
                "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
                "KXZEC15M": "ZECUSD_RTI"}
TAU_KEEP = 60            # seconds before the close to keep per-second detail
WINDOW = (3, 45)         # the band the bot is allowed to trade in


def _hours_for_day(day, channel, data=None):
    """Tape hours that can hold a market closing on this ET day.

    ET days start at 04:00Z (or 05:00Z in winter), so a day needs the UTC
    hours from its own 04:00Z through the NEXT day's 04:00Z. Taking the
    matching UTC date instead silently drops the evening, which is the busiest
    part of the ET day -- the same ticker-clock trap that once reported a
    +$23 day as +$47.
    """
    import time as _t
    import pindesk
    data = data or DATA
    # pindesk.et_day_start is the ONE place that knows the Eastern offset and
    # the November clock change; every other file in the repo calls it rather
    # than recomputing, and a local copy is how a day boundary drifts.
    start = pindesk.et_day_start(day)
    want = set()
    for s in range(int(start) - 3600, int(start) + 26 * 3600, 3600):
        want.add(_t.strftime("%Y%m%dT%H", _t.gmtime(s)))
    out = []
    for f in sorted(glob.glob(os.path.join(data, channel, "*.jsonl.gz"))):
        if os.path.basename(f)[:11] in want:
            out.append(f)
    return out


def _lines(path):
    """Text lines, surviving a torn hour by keeping the readable prefix."""
    try:
        fh = gzip.open(path, "rt", encoding="utf-8", errors="replace")
    except OSError:
        return
    try:
        with fh:
            for line in fh:
                yield line
    except Exception:                                          # noqa: BLE001
        return


def collect(day, data=None, series=CRYPTO, tau_keep=TAU_KEEP, on_progress=None):
    """{ticker: {...}} -- everything visible, per market, for one ET day."""
    import pinflat
    import pinattrib
    data = data or DATA
    settled = pinattrib.load_outcomes(r"C:\kals\fulltape\markets.json")
    mk = {}

    def slot(tk):
        m = mk.get(tk)
        if m is None:
            close = pinflat.close_epoch(tk)
            if close is None:
                return None
            m = mk[tk] = {"ticker": tk, "series": tk.split("-", 1)[0],
                          "close": close, "result": settled.get(tk),
                          "index": {}, "book": {}, "trades": [], "ours": []}
        return m

    # ---- index: one print a second, per coin. Keyed by SERIES, then fanned
    # out to that series' markets, because the index is per coin and a coin
    # has one market per close.
    idx = collections.defaultdict(dict)
    want_iid = {SERIES_INDEX[s] for s in series if s in SERIES_INDEX}
    for i, f in enumerate(_hours_for_day(day, "cfbenchmarks_value", data)):
        for line in _lines(f):
            if not any(('"' + i2 + '"') in line for i2 in want_iid):
                continue
            try:
                msg = json.loads(line).get("msg") or {}
                iid = msg.get("index_id")
                if iid not in want_iid:
                    continue
                dd = json.loads(msg.get("data") or "{}")
                idx[iid][int(dd["time"]) // 1000] = float(dd["value"])
            except (KeyError, TypeError, ValueError):
                continue
        if on_progress:
            on_progress("index", i)

    # ---- book touch and trades
    for chan in ("ticker", "trade"):
        for i, f in enumerate(_hours_for_day(day, chan, data)):
            for line in _lines(f):
                if "15M-" not in line:
                    continue
                try:
                    msg = json.loads(line).get("msg") or {}
                except ValueError:
                    continue
                tk = msg.get("market_ticker") or ""
                if not tk.startswith(series):
                    continue
                m = slot(tk)
                if m is None:
                    continue
                try:
                    ts = int(msg.get("ts") or (int(line.split('"_rx_ms":')[1]
                                                   .split(",")[0].strip(" }")) // 1000))
                except (IndexError, TypeError, ValueError):
                    continue
                tau = m["close"] - ts
                if not (0 <= tau <= tau_keep):
                    continue
                if chan == "ticker":
                    try:
                        m["book"][tau] = (float(msg["yes_bid_dollars"]),
                                          float(msg["yes_ask_dollars"]))
                    except (KeyError, TypeError, ValueError):
                        pass
                else:
                    try:
                        m["trades"].append(
                            {"tau": tau, "yes_px": float(msg["yes_price_dollars"]),
                             "side": msg.get("taker_side"),
                             "n": float(msg.get("count_fp") or 0)})
                    except (KeyError, TypeError, ValueError):
                        pass
            if on_progress:
                on_progress(chan, i)

    # ---- the index path, per market
    for tk, m in mk.items():
        iid = SERIES_INDEX.get(m["series"])
        d = idx.get(iid) or {}
        for tau in range(0, tau_keep + 1):
            v = d.get(m["close"] - tau)
            if v is not None:
                m["index"][tau] = v

    # ---- what WE did, and why
    import pindesk
    for f in sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))):
        for line in _lines(f) if f.endswith(".gz") else open(
                f, encoding="utf-8", errors="replace"):
            if "15M-" not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            tk = r.get("ticker")
            if not tk or tk not in mk:
                continue
            k = r.get("kind")
            if k not in ("signal", "refused", "order", "settled", "hedge",
                         "hedge_alarm", "dumped", "sweep_depth"):
                continue
            mk[tk]["ours"].append(
                {kk: r.get(kk) for kk in
                 ("kind", "t", "tau", "gate", "want", "price", "fair", "edge_c",
                  "take_n", "size", "filled", "asked", "sigma", "spot",
                  "strike", "status", "pnl_c", "result", "ladder", "leg",
                  "yes_ask", "no_ask", "held")
                 if r.get(kk) is not None})
    return mk


def best_price(m, window=WINDOW):
    """The cheapest ask on the side that WON, inside the window, or None.

    This is the opportunity, whether or not we took it. `result` is the
    settled outcome, so the winning side is known with hindsight -- that is
    the point: it ranks what WAS there to be had.
    """
    res = m.get("result")
    if res not in ("yes", "no"):
        return None
    best = None
    for tau, (bid, ask) in m.get("book", {}).items():
        # JSON has no integer keys: a book that has been through
        # `results/pinlook_<day>.json` arrives keyed by "43", not 43, and the
        # comparison below raises rather than silently skipping. Coerce at the
        # boundary, as `confident_best` already does.
        tau = int(tau)
        if not (window[0] <= tau <= window[1]):
            continue
        # our side's ask: YES asks at `ask`; NO asks at 1 - bid
        px = ask if res == "yes" else (1.0 - bid if bid else None)
        if px and 0.0 < px < 1.0 and (best is None or px < best[0]):
            best = (px, tau)
    return best


def confident_best(m, window=WINDOW, pin=0.995):
    """The cheapest ask on the winning side AT A MOMENT OUR MODEL WAS SURE.

    WHY THIS EXISTS BESIDE `best_price`. Ranking purely by the cheapest ask on
    the side that won surfaces LOTTERY TICKETS: on 2026-09-18 the top row was
    an XRP market whose YES traded at 1.8c with 43 seconds left and then won.
    Nothing could have identified that in advance -- at 43 s the index was far
    from the strike and every model on earth, ours included, said the same
    thing the market did. It is hindsight, not a missed edge.

    This ranks the cheapest ask at a second where OUR OWN recorded fair value
    was at least `pin` on the side that won. Those are the ones we could
    actually have taken, and the gap between the two lists is the honest
    measure of what was reachable.

    Returns (price, tau, fair) or None. Uses only fair values the bot really
    wrote down -- it never re-runs the model, because a re-run would be a
    replay and rule 5 applies to those.
    """
    res = m.get("result")
    if res not in ("yes", "no"):
        return None
    sure = {}
    for r in m.get("ours") or []:
        f, tau = r.get("fair"), r.get("tau")
        if f is None or tau is None:
            continue
        ours_side = float(f) if res == "yes" else 1.0 - float(f)
        if ours_side >= pin:
            sure[int(tau)] = ours_side
    if not sure:
        return None
    best = None
    for tau, (bid, ask) in m.get("book", {}).items():
        tau = int(tau)
        if not (window[0] <= tau <= window[1]) or tau not in sure:
            continue
        px = ask if res == "yes" else (1.0 - bid if bid else None)
        if px and 0.0 < px < 1.0 and (best is None or px < best[0]):
            best = (px, tau, sure[tau])
    return best


def decision(m):
    """One line: what we did on this market, and why not."""
    ours = m.get("ours") or []
    fills = [r for r in ours if r.get("kind") == "order"
             and float(r.get("filled") or 0) > 0]
    if fills:
        # the fill price comes from the SIGNAL that produced it; an order
        # record carries `exec_price`, not `price`, and printing an empty
        # "BOUGHT 78 @ " was the first thing this function got wrong
        px = [r.get("price") for r in ours if r.get("kind") == "signal"
              and r.get("price") is not None]
        return "BOUGHT %g%s" % (
            sum(float(r["filled"]) for r in fills),
            (" @ " + ", ".join("%.3f" % float(x) for x in px)) if px else "")
    sig = [r for r in ours if r.get("kind") == "signal"]
    if sig:
        return "signalled, order filled nothing"
    gates = [r.get("gate") for r in ours if r.get("kind") == "refused"]
    if gates:
        return "refused: " + ", ".join(sorted(set(g for g in gates if g)))
    if ours:
        return "seen, no decision recorded"
    return "never evaluated"


def rank(mk, n=30, window=WINDOW, reachable=False):
    """The n cheapest winning-side opportunities of the day.

    `reachable=False` ranks what was THERE. `reachable=True` ranks only the
    seconds our own model had already called, so the list is what we could
    have acted on. Read them side by side: the first is the ceiling, the
    second is the ceiling minus hindsight.
    """
    rows = []
    for tk, m in mk.items():
        b = confident_best(m, window) if reachable else best_price(m, window)
        if b:
            rows.append((b[0], b[1], m))
    rows.sort(key=lambda r: r[0])
    return rows[:n]


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinlook selftest: FAILED -- " + msg)

    # BEST PRICE reads the side that WON, from the right half of the book.
    m = {"result": "yes", "book": {5: (0.90, 0.96), 20: (0.80, 0.93),
                                   50: (0.10, 0.20), 2: (0.99, 0.995)}}
    b = best_price(m)
    ck(b == (0.93, 20),
       "the best opportunity is the cheapest ASK on the winning side inside "
       "the window -- 93c at 20 s, not the 20c ask at 50 s which is outside "
       "it, and not the 99.5c at 2 s which is inside but dear")
    m2 = dict(m, result="no")
    b2 = best_price(m2)
    ck(b2 and abs(b2[0] - 0.10) < 1e-9 and b2[1] == 5,
       "when NO won, our side's ask is 1 minus the yes BID -- 10c at 5 s. "
       "Reading the yes ask for a NO winner is the sign error that once "
       "reported the dangerous bucket as the safest")
    ck(best_price({"result": None, "book": {5: (0.9, 0.96)}}) is None,
       "NULL: a market with no settlement has no known winning side and is "
       "not ranked, rather than guessed")
    ck(best_price({"result": "yes", "book": {}}) is None,
       "NULL: no book, no opportunity")
    jsonish = {"result": "yes", "book": {"5": (0.90, 0.96), "20": (0.80, 0.93),
                                         "50": (0.10, 0.20)}}
    ck(best_price(jsonish) == (0.93, 20) and confident_best(
        dict(jsonish, ours=[{"kind": "signal", "tau": 20, "fair": 0.999}]))[1] == 20,
       "a book read back from JSON is keyed by STRINGS, and both rankings "
       "must give the same answer as the in-memory one -- comparing '20' to "
       "an int raises, which is at least loud, but int('20') sorting after "
       "'5' would have been silent and wrong")

    # DECISION says what happened, and distinguishes the three silences.
    ck(decision({"ours": [{"kind": "order", "filled": 20.0, "price": 0.97}]})
       .startswith("BOUGHT 20"), "a fill reads as BOUGHT with the price paid")
    ck("refused: confidence" in decision(
        {"ours": [{"kind": "refused", "gate": "confidence"}]}),
       "a refusal names its gate")
    ck(decision({"ours": []}) == "never evaluated"
       and decision({"ours": [{"kind": "watch"}]}) == "seen, no decision recorded",
       "NULL: 'never evaluated' and 'seen but nothing recorded' are DIFFERENT "
       "answers -- collapsing them hides whether the bot looked at all")
    ck(decision({"ours": [{"kind": "signal"}, {"kind": "order", "filled": 0.0}]})
       == "signalled, order filled nothing",
       "a signal whose order filled nothing is a LOST RACE, not a refusal")

    # CONFIDENT BEST separates a reachable bargain from a lottery ticket.
    lot = {"result": "yes", "book": {43: (0.010, 0.018), 12: (0.95, 0.97)},
           "ours": [{"kind": "signal", "tau": 12, "fair": 0.999}]}
    ck(best_price(lot) == (0.018, 43),
       "the raw ranking picks the 1.8c ask at 43 s")
    cb = confident_best(lot)
    ck(cb and abs(cb[0] - 0.97) < 1e-9 and cb[1] == 12,
       "the reachable ranking REFUSES that 1.8c row -- at 43 s our model had "
       "said nothing, so no version of this bot could have taken it. It "
       "returns the 97c ask at 12 s, the second we were actually sure. "
       "Conflating the two is how a hindsight list gets read as lost money")
    ck(confident_best({"result": "yes", "book": {12: (0.95, 0.97)}, "ours": [
        {"kind": "signal", "tau": 12, "fair": 0.80}]}) is None,
       "NULL: sure of nothing, so nothing is reachable")
    ck(confident_best({"result": "no", "book": {12: (0.05, 0.07)}, "ours": [
        {"kind": "signal", "tau": 12, "fair": 0.001}]})[0] == 0.95,
       "when NO won, OUR confidence is 1 minus the recorded fair, and the "
       "price is 1 minus the yes bid -- both sides flip together or the "
       "NO half of the day is scored against the wrong number")

    # RANK is by the opportunity, never by what we did.
    mk = {"A": {"ticker": "A", "result": "yes", "book": {10: (0.5, 0.99)}, "ours": []},
          "B": {"ticker": "B", "result": "yes", "book": {10: (0.5, 0.91)},
                "ours": [{"kind": "refused", "gate": "confidence"}]}}
    r = rank(mk, n=5)
    ck(r and r[0][2]["ticker"] == "B",
       "the cheapest opportunity ranks first even though we REFUSED it and "
       "took the other -- ranking our own trades would only show what we "
       "already know")
    ck(len(rank(mk, n=1)) == 1, "and n caps the list")
    print("pinlook selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--day", default=None, help="ET day, YYYY-MM-DD")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    import time
    day = a.day or __import__("pindesk").et_day(time.time())
    print("collecting %s ..." % day, flush=True)
    mk = collect(day, data=a.data,
                 on_progress=lambda c, i: (print("  %s %d" % (c, i), flush=True)
                                           if not i % 8 else None))
    print("  %d markets" % len(mk), flush=True)
    out = a.out or os.path.join(RESULTS, "pinlook_%s.json" % day)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"day": day, "markets": mk}, fh)
    print("  wrote %s (%.1f MB)" % (out, os.path.getsize(out) / 1e6))
    for reach in (False, True):
        rows = rank(mk, n=a.top, reachable=reach)
        print()
        if reach:
            print("  REACHABLE -- the same list, cut down to seconds where OUR OWN")
            print("  model had already called the winner. This is what was takeable.")
        else:
            print("  EVERYTHING THAT WAS THERE -- cheapest ask on the side that WON,")
            print("  inside %d-%d s. Includes bargains nothing could have seen coming."
                  % WINDOW)
        print()
        print("  %-30s %8s %6s %10s  %s"
              % ("market", "best ask", "at", "settled", "what we did"))
        for px, tau, m in rows:
            print("  %-30s %8.3f %5ds %10s  %s"
                  % (m["ticker"][:30], px, tau, m.get("result"), decision(m)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
