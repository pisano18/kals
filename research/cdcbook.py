#!/usr/bin/env python3
"""cdcbook.py -- what the Crypto.com book actually looks like into expiry.

cdcedge.py said the winning side averaged 97.4c, which would be a live edge.
Before believing that, three things have to be true and none of them are
checked by a price alone:

  SIZE      a 97c ask for one contract is not a business.
  TWO SIDES eleven of sixteen expiries had NO quote on the winning side. An
            empty book is not a cheap book.
  FEES      CDNA bills per contract, not per dollar of risk. A fee that is
            flat in notional eats a 3c edge in a way Kalshi's 0.2c never does.

This prints the raw ladder for the last two minutes of each contract, plus
every print that actually changed hands, so the above is read off the tape
rather than assumed.

READ-ONLY.

    python research/cdcbook.py --selftest
    python research/cdcbook.py --last 6
"""
import argparse
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import cdcedge                                               # noqa: E402
import gzsalvage                                             # noqa: E402

CDC = cdcedge.CDC


def ladder(bk, n=3):
    """'0.41x550 | 0.48x550' -- the top n levels each side, as seen."""
    def side(rows):
        return " ".join("%sx%s" % (r[0], r[1]) for r in (rows or [])[:n]) or "(empty)"
    return "%-34s | %s" % (side(bk.get("bids")), side(bk.get("asks")))


def top_size(bk, side_yes):
    """Contracts available at the best price on the side we would BUY."""
    rows = bk.get("asks") if side_yes else bk.get("bids")
    if not rows:
        return 0
    try:
        return float(rows[0][1])
    except (TypeError, ValueError, IndexError):
        return 0


def load_channel(channel, key="symbol"):
    out = collections.defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(CDC, channel, "*.jsonl.gz"))):
        for line in gzsalvage.iter_lines(fp):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            out[d.get(key)].append(d)
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    bk = {"bids": [["0.41", "550"], ["0.30", "10"]], "asks": [["0.48", "7"]]}
    s = ladder(bk)
    ck("0.41x550" in s and "0.48x7" in s, "the ladder shows price and size")
    ck("(empty)" in ladder({"bids": [], "asks": [["0.9", "1"]]}),
       "NULL: a missing side prints as empty, not as zero")
    ck(top_size(bk, True) == 7.0,
       "buying YES takes the ask size (7), not the 550 sitting on the bid")
    ck(top_size(bk, False) == 550.0, "and buying NO takes the bid size (550)")
    ck(top_size({"bids": [], "asks": []}, True) == 0,
       "NULL: an empty book offers zero contracts")
    print("cdcbook selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--last", type=int, default=6, help="how many expiries")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    insts = cdcedge.load_instruments()
    books = cdcedge.load_books()
    trades = load_channel("trades")
    idx = cdcedge.idxload.load(sorted({cdcedge.COIN_INDEX[r["base_ccy"]]
                                       for r in insts.values()
                                       if r.get("base_ccy") in cdcedge.COIN_INDEX}),
                               verbose=False)

    scored = []
    for sym, snaps in books.items():
        r = insts.get(sym) or {}
        att = (r.get("event_details") or {}).get("attributes") or {}
        close = cdcedge.parse_close(att.get("CLOSE_TIME"))
        iid = cdcedge.COIN_INDEX.get(r.get("base_ccy"))
        if not close or not iid or iid not in idx:
            continue
        try:
            strike = float(att.get("STRIKE_PRICE"))
        except (TypeError, ValueError):
            continue
        st = cdcedge.settle_mean(idx[iid], close)
        if st is None:
            continue
        scored.append((close, sym, strike, st,
                       cdcedge.outcome(st, strike, att.get("STRIKE_OPERATOR", ">")),
                       snaps, att))
    scored.sort()
    for close, sym, strike, st, yes_won, snaps, att in scored[-a.last:]:
        print("\n%s  strike %s  our settle %.4f  -> %s wins"
              % (sym, att.get("STRIKE_PRICE"), st, "YES" if yes_won else "NO"))
        print("   %-8s %-34s | %s" % ("t-left", "bids (buy NO here)", "asks (buy YES here)"))
        for ts, bk in snaps[-14:]:
            print("   %+7.0fs %s" % ((ts / 1000.0) - close, ladder(bk)))
        got = [top_size(bk, yes_won) for ts, bk in snaps
               if ts and close * 1000 - 60000 <= ts <= close * 1000]
        if got:
            print("   contracts available on the WINNING side in the last minute: "
                  "%s" % ", ".join("%g" % g for g in got))
        tr = []
        for d in trades.get(sym, []):
            for t in (((d.get("resp") or {}).get("result") or {}).get("data") or []):
                tr.append((t.get("t"), t.get("p"), t.get("q"), t.get("s")))
        tr = sorted(set(tr))
        print("   prints: %s" % (", ".join("%s@%s x%s" % (s, p, q)
                                           for _, p, q, s in tr[-8:]) or "NONE -- "
                                 "nothing changed hands"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
