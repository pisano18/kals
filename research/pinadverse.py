#!/usr/bin/env python3
"""pinadverse.py -- why does "certain" lose more than "nearly certain"?

pinsure found the model's calibration is INVERTED at the top:

    99.90% to 99.99%    76 trades   1 lost   1.32%
    99.99%+             67 trades   3 lost   4.48%

Three times the loss rate in the bucket that prints as 100%. Three losses is a
small number and the intervals overlap, so this is a lead rather than a fact.
But it points somewhere specific and cheap to check.

THE HYPOTHESIS: ADVERSE SELECTION, and it is the same mechanism that makes the
tape say 0.11% while live says 3.4%. To buy at extreme confidence we need
somebody to SELL us a near-certain winner at a discount. Most of the time that
is an ordinary holder taking their money off the table. But the bigger the
discount, the better the reason they might have for offering it -- and the
model cannot see their reason, only the price. So the very trades that look
best are the ones most likely to be somebody else's information.

IF THAT IS TRUE, a bigger apparent edge should come with a HIGHER loss rate,
not a lower one. That is a strange prediction -- it is backwards from how a
model is supposed to work -- and that is exactly what makes it worth testing.

THE COMPETING EXPLANATION is dull and must be ruled out first: staleness. At
extreme confidence the model leans hardest on prints already locked, so a slow
index read or an old book would corrupt precisely these trades. Both ages are
logged on every signal, so winners and losers can be compared directly.

SOURCE: live fills only, per the 2026-09-10 amendment. NOTHING HERE CHANGES
THE BOT.

    python research/pinadverse.py --selftest
    python research/pinadverse.py
"""
import argparse
import collections
import glob
import json
import statistics
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"
EDGE_BANDS = [(0, 1), (1, 2), (2, 4), (4, 8), (8, 1e9)]


def conf(fair, want):
    if fair is None or want is None:
        return None
    return float(fair) if want == "yes" else 1.0 - float(fair)


def eband(e):
    for lo, hi in EDGE_BANDS:
        if lo <= e < hi:
            return (lo, hi)
    return None


def elabel(b):
    lo, hi = b
    return "%gc+" % lo if hi > 1e8 else "%g to %gc" % (lo, hi)


def scan(rows):
    """[{conf, edge, won, idx_age, book_age, tau, price, series}]"""
    sig, out = {}, []
    for r in rows:
        k, tk = r.get("kind"), r.get("ticker")
        if not tk:
            continue
        if k == "signal":
            c = conf(r.get("fair"), r.get("want"))
            if c is None:
                continue
            sig[tk] = {"conf": c, "edge": r.get("edge_c"),
                       "idx_age": r.get("index_age_s"),
                       "book_age": r.get("book_age_ms"),
                       "tau": r.get("tau"), "price": r.get("price"),
                       "series": tk.split("-")[0]}
        elif k == "settled" and tk in sig:
            d = sig.pop(tk)
            d["won"] = (r.get("want") == r.get("result"))
            out.append(d)
    return out


def load():
    out = []
    for fp in sorted(glob.glob(LIVE)):
        rows = []
        for line in open(fp, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        out.extend(scan(rows))
    return out


def rate(got):
    if not got:
        return None
    return sum(1 for d in got if not d["won"]) / len(got)


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(abs(conf(0.00463, "no") - 0.99537) < 1e-9,
       "a NO trade's confidence is one minus fair, not fair")
    ck(conf(1.0, "yes") == 1.0, "and a YES trade's is fair itself")
    ck(eband(0.5) == (0, 1) and eband(9) == (4 + 4, 1e9),
       "edge bands cover the thin end and the open top")
    ck(eband(-1) is None, "NULL: a negative edge belongs to no band")
    rows = [{"kind": "signal", "ticker": "KXBTC15M-x", "fair": 1.0,
             "want": "yes", "edge_c": 7.0, "index_age_s": 0.4,
             "book_age_ms": 20, "tau": 30, "price": 0.93},
            {"kind": "settled", "ticker": "KXBTC15M-x", "want": "yes",
             "result": "no"}]
    got = scan(rows)
    ck(len(got) == 1 and got[0]["won"] is False and got[0]["series"] == "KXBTC15M",
       "a losing 100%% trade is captured with its series and its edge")
    ck(rate(got) == 1.0, "one trade, one loss, a rate of 1.0")
    ck(rate([]) is None, "NULL: no trades has no loss rate, not a rate of zero")
    print("pinadverse selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0
    rows = [d for d in load() if isinstance(d.get("edge"), (int, float))]
    if not rows:
        print("loaded nothing")
        return 0

    print("\nA. IS A BIGGER APPARENT EDGE MORE DANGEROUS?\n")
    print("  %-14s %8s %7s %11s" % ("edge at entry", "trades", "lost", "loss rate"))
    print("  " + "-" * 44)
    for b in EDGE_BANDS:
        got = [d for d in rows if eband(d["edge"]) == b]
        if got:
            print("  %-14s %8d %7d %10.2f%%"
                  % (elabel(b), len(got), sum(1 for d in got if not d["won"]),
                     100 * rate(got)))

    print("\nB. THE SAME SPLIT, ONLY FOR TRADES THE MODEL CALLED 100%%\n")
    top = [d for d in rows if d["conf"] >= 0.9999]
    print("  %-14s %8s %7s %11s" % ("edge at entry", "trades", "lost", "loss rate"))
    print("  " + "-" * 44)
    for b in EDGE_BANDS:
        got = [d for d in top if eband(d["edge"]) == b]
        if got:
            print("  %-14s %8d %7d %10.2f%%"
                  % (elabel(b), len(got), sum(1 for d in got if not d["won"]),
                     100 * rate(got)))

    print("\nC. THE DULL EXPLANATION: WAS OUR DATA STALE ON THE LOSERS?\n")
    for field, unit in (("idx_age", "s"), ("book_age", "ms"), ("tau", "s")):
        w = [d[field] for d in rows if d["won"] and isinstance(d[field], (int, float))]
        l = [d[field] for d in rows if not d["won"] and isinstance(d[field], (int, float))]
        if w and l:
            print("  %-10s winners median %8.3f%-2s    losers median %8.3f%s"
                  % (field, statistics.median(w), unit, statistics.median(l), unit))
    print("\n  If the losers' data was no older than the winners', staleness is")
    print("  not the explanation and the price is.")

    print("\nD. WHERE DO THE LOSSES LIVE?\n")
    per = collections.defaultdict(lambda: [0, 0])
    for d in rows:
        per[d["series"]][0] += 1
        per[d["series"]][1] += (not d["won"])
    for s, (n, l) in sorted(per.items(), key=lambda kv: -kv[1][1])[:8]:
        print("  %-14s %4d trades  %2d lost  %6.2f%%" % (s, n, l, 100 * l / n))

    print("\nE. THE INDIVIDUAL 100%% LOSSES\n")
    for d in [x for x in top if not x["won"]]:
        print("  %-14s edge %5.2fc  price %-7s tau %-4s index age %ss"
              % (d["series"], d["edge"], d["price"], d["tau"], d["idx_age"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
