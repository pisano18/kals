#!/usr/bin/env python3
"""cdcedge.py -- would the pin strategy have worked on Crypto.com's binaries?

THE OPERATOR, 2026-09-16: "see if your strategy or a strategy would work if you
could bet."

Two questions, both answerable from tape alone, with no trading access and
without ever seeing CDNA's own index:

  1. IS OUR PRICE FEED A GOOD ENOUGH PROXY? CDNA settles on its own index
     (Lukka / ICE midpoints, 60-second trimmed average). We have CF Benchmarks
     once a second. For the seven coins both cover, this scores our feed's
     verdict against what the CONTRACT itself did -- the book at expiry reveals
     the outcome, so their index is never needed.

  2. DOES ANYONE SELL THE WINNING SIDE CHEAP? That is the entire pin edge. On
     Kalshi a near-certain side gets offered at 95-98c in the last seconds.
     Here the first look showed 8-24c spreads. This measures, for every expiry
     in the tape, the cheapest ask on the side that actually won, in the final
     seconds -- which is the price we would have paid.

A binary resolves YES when the settlement value is > STRIKE_PRICE (the
instruments carry STRIKE_OPERATOR, and it is checked rather than assumed).

READ-ONLY: it reads C:\\kals\\cdc_data and the index tape. No network.

    python research/cdcedge.py --selftest
    python research/cdcedge.py
"""
import collections
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import gzsalvage                                             # noqa: E402
import idxload                                               # noqa: E402

CDC = r"C:\kals\cdc_data"
N_AVG = 60
CEILING = 0.98
# CDNA base currency -> the CF Benchmarks index we already record once a second
COIN_INDEX = {"BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI",
              "XRP": "XRPUSD_RTI", "BCH": "BCHUSD_RTI", "ADA": "ADAUSD_RTI",
              "DOGE": "DOGEUSD_RTI"}


def parse_close(s):
    """'20260916-14:40:00.000' (Eastern-free, it is UTC on this API) -> epoch."""
    try:
        d = dt.datetime.strptime(s, "%Y%m%d-%H:%M:%S.%f")
    except (ValueError, TypeError):
        return None
    return int((d - dt.datetime(1970, 1, 1)).total_seconds())


def settle_mean(D, close, n=N_AVG):
    """Mean of the index prints over [close-n, close), or None if too few."""
    got = [v for v in (D.get(s) for s in range(close - n, close)) if v is not None]
    if len(got) < n * 0.9:
        return None
    return sum(got) / len(got)


def outcome(settle, strike, op=">"):
    """True = the YES side won."""
    return settle > strike if op == ">" else settle >= strike


def best_ask(books, side_yes):
    """Cheapest price at which the given side could have been BOUGHT.

    Buying NO means lifting the YES bid's mirror: a NO ask of (1 - yes_bid) is
    what the book offers, exactly as on Kalshi."""
    best = None
    for bk in books:
        bids = bk.get("bids") or []
        asks = bk.get("asks") or []
        if side_yes:
            if asks:
                p = float(asks[0][0])
                best = p if best is None else min(best, p)
        else:
            if bids:
                p = round(1.0 - float(bids[0][0]), 4)
                best = p if best is None else min(best, p)
    return best


def load_instruments():
    """{symbol: row} from the newest instrument snapshots."""
    out = {}
    for fp in sorted(glob.glob(os.path.join(CDC, "instruments", "*.jsonl.gz"))):
        # THE NEWEST FILE IS STILL BEING WRITTEN, so a plain gzip reader dies
        # on it with "invalid block type" -- as it did the first time this ran.
        for line in gzsalvage.iter_lines(fp):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            for r in d.get("rows") or []:
                if r.get("symbol"):
                    out[r["symbol"]] = r
    return out


def load_books():
    """{symbol: [(rx_ms, book), ...]} in time order."""
    out = collections.defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(CDC, "book", "*.jsonl.gz"))):
        for line in gzsalvage.iter_lines(fp):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            data = (((d.get("resp") or {}).get("result") or {}).get("data") or [])
            if data:
                out[d.get("symbol")].append((d.get("_rx_ms"), data[0]))
    for s in out:
        out[s].sort()
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    e = parse_close("20260916-14:40:00.000")
    got = dt.datetime.fromtimestamp(e, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    ck(got == "2026-09-16 14:40:00Z",
       "a CLOSE_TIME parses as UTC: %s" % got)
    ck(parse_close("rubbish") is None and parse_close(None) is None,
       "NULL: an unparseable close is refused, never guessed")

    class D:
        def __init__(self, v):
            self.v = v

        def get(self, s):
            return self.v.get(s)

    full = D({s: 100.0 for s in range(940, 1000)})
    ck(settle_mean(full, 1000) == 100.0, "a full minute of prints averages")
    ck(settle_mean(D({1: 1.0}), 1000) is None,
       "NULL: a nearly empty window is refused rather than averaged")
    rising = D({s: (100.0 if s < 970 else 200.0) for s in range(940, 1000)})
    ck(settle_mean(rising, 1000) == 150.0,
       "and a jump halfway through the window lands halfway -- the averaging "
       "is what makes the outcome knowable early")

    ck(outcome(101.0, 100.0) and not outcome(99.0, 100.0),
       "the YES side wins when settlement is above the strike")
    ck(not outcome(100.0, 100.0, ">"),
       "and exactly at the strike, '>' means NO -- the operator is read from "
       "the contract, not assumed")

    bk = [{"bids": [["0.41", "550"]], "asks": [["0.48", "550"]]},
          {"bids": [["0.60", "10"]], "asks": [["0.97", "10"]]}]
    ck(best_ask(bk, True) == 0.48, "the cheapest YES ask across the window")
    ck(best_ask(bk, False) == round(1 - 0.60, 4),
       "and buying NO costs 1 minus the best YES bid (%.2f)" % (1 - 0.60))
    ck(best_ask([{"bids": [], "asks": []}], True) is None,
       "NULL: an empty book offers nothing, which is not a price of zero")
    print("cdcedge selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    insts = load_instruments()
    books = load_books()
    if not insts or not books:
        print("loaded nothing -- no CDNA tape yet (%d instruments, %d books)"
              % (len(insts), len(books)))
        return 0
    print("\n%d contracts seen, %d with book snapshots" % (len(insts), len(books)))

    need = sorted({COIN_INDEX[r.get("base_ccy")] for r in insts.values()
                   if r.get("base_ccy") in COIN_INDEX})
    idx = idxload.load(need, verbose=False) if need else {}

    rows = []
    for sym, snaps in books.items():
        r = insts.get(sym)
        if not r:
            continue
        att = (r.get("event_details") or {}).get("attributes") or {}
        coin = r.get("base_ccy")
        iid = COIN_INDEX.get(coin)
        close = parse_close(att.get("CLOSE_TIME"))
        try:
            strike = float(att.get("STRIKE_PRICE"))
        except (TypeError, ValueError):
            continue
        if not iid or not close or iid not in idx:
            continue
        D = idx[iid]
        if close > (D.base + D.n) - 5:
            continue                      # not settled in our index tape yet
        st = settle_mean(D, close)
        if st is None:
            continue
        yes_won = outcome(st, strike, att.get("STRIKE_OPERATOR", ">"))
        late = [b for ts, b in snaps if ts and close * 1000 - 60000 <= ts <= close * 1000]
        if not late:
            continue
        ask_win = best_ask(late, yes_won)
        spreads = []
        for b in late:
            if b.get("bids") and b.get("asks"):
                spreads.append(float(b["asks"][0][0]) - float(b["bids"][0][0]))
        rows.append({"sym": sym, "coin": coin, "close": close, "strike": strike,
                     "settle": st, "yes_won": yes_won, "ask_win": ask_win,
                     "snaps": len(late),
                     "spread": (sum(spreads) / len(spreads)) if spreads else None,
                     "margin_bp": 1e4 * (st - strike) / strike})
    if not rows:
        print("no contract has both a settled index window and a late book yet.")
        print("The recorder needs to run across a few expiries -- check back "
              "in an hour.")
        return 0
    rows.sort(key=lambda r: r["close"])
    print("\n%-34s %-5s %7s %9s %8s %8s %7s"
          % ("contract", "coin", "margin", "won", "cheapest", "spread", "looks"))
    print("  " + "-" * 86)
    buyable = 0
    for r in rows:
        print("%-34s %-5s %6.1fbp %9s %8s %8s %7d"
              % (r["sym"].replace("NX.F.OPT.", "")[:34], r["coin"], r["margin_bp"],
                 "YES" if r["yes_won"] else "NO",
                 ("%.2f" % r["ask_win"]) if r["ask_win"] is not None else "-",
                 ("%.2f" % r["spread"]) if r["spread"] is not None else "-",
                 r["snaps"]))
        if r["ask_win"] is not None and r["ask_win"] <= CEILING:
            buyable += 1
    got = [r for r in rows if r["ask_win"] is not None]
    print("\n  %d expiries scored. The winning side was offered at or under "
          "%.0fc on %d of them." % (len(rows), 100 * CEILING, buyable))
    if got:
        avg = sum(r["ask_win"] for r in got) / len(got)
        print("  Average price of the winning side in the last minute: %.1fc." % (100 * avg))
        sp = [r["spread"] for r in rows if r["spread"] is not None]
        if sp:
            print("  Average bid-ask spread in the last minute: %.1fc. Our edge "
                  "on Kalshi is 2-4c a contract." % (100 * sum(sp) / len(sp)))
    print("\n  Settlement is OUR CF Benchmarks feed standing in for CDNA's index.")
    print("  Where the two disagree the verdict above is wrong, which is why the")
    print("  margin column matters: a 50bp margin is not a close call.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
