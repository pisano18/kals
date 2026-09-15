#!/usr/bin/env python3
"""pinhourlyedge.py -- does the pin edge EXIST on the hourly markets?

THE OPERATOR, 2026-09-15: "Definitely start the hourly markets."

`pinhourly.py` established that fourteen hourly crypto series settle on a rule
word for word identical to ours -- the simple average of the sixty seconds of
the same CF Benchmarks index -- and sampled a real close second by second into
results/hourly_book_sample.jsonl. It never scored those samples. This does.

THE QUESTION IS NOT THE MODEL. The model needs no change at all: same index,
same sixty-second average, same collapse of uncertainty. The question is
whether ANYBODY OFFERS THE WINNING SIDE AT A PRICE WE WOULD PAY in the final
seconds. On the 15-minute markets that is the whole edge and it happens rarely.

WHY IT MIGHT NOT, and the reason is structural rather than bad luck. The
15-minute market has ONE strike, set to the previous window's settlement, so it
starts AT the money. People hold it, and near the close some of them exit --
selling a near-certain winner at 95-97c. That exit flow IS our edge.

The hourly market has a LADDER of 188 strikes. The near-certain ones were never
at the money, so nobody holds them, so nobody exits them. Polled live at
2026-09-15 04:35Z, every far strike on KXBTCD read exactly 1.00 / 0.01: the
certain winner offered at a DOLLAR, the certain loser at a cent. No edge in
either.

So the only place an edge could live is the one or two strikes nearest the
money in the final seconds, once they become near-certain but still have
holders. That is what this scores.

METHOD. For every sampled book row: recover the strike from the ticker and the
close from its hour, read the settlement index at that second from our own
tape, price it through `pinrun.fair` -- the bot's own function, not a copy --
and ask whether the side the model calls near-certain was buyable at or under
the 98c ceiling.

READ-ONLY. No orders, no network; it reads two files on disk.

    python research/pinhourlyedge.py --selftest
    python research/pinhourlyedge.py
"""
import collections
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinrun                                                  # noqa: E402
import idxload                                                 # noqa: E402

SAMPLE = os.path.join(REPO, "results", "hourly_book_sample.jsonl")
CEILING = pinrun.PRICE_CEILING
PIN = pinrun.PIN
SERIES_INDEX = {"KXBTCD": "BRTI", "KXETHD": "ETHUSD_RTI", "KXSOLD": "SOLUSD_RTI",
                "KXXRPD": "XRPUSD_RTI", "KXDOGED": "DOGEUSD_RTI",
                "KXBNBD": "BNBUSD_RTI", "KXHYPED": "HYPEUSD_RTI"}


def parse_ticker(tk):
    """('KXBTCD', close_epoch, strike) from KXBTCD-26SEP1319-T76599.99.

    The date-hour block is EASTERN, the same convention the 15-minute tickers
    use -- KXBTC15M-26SEP140530-30 is the 05:30 ET close. Reading it as UTC
    puts every sample four hours from its own close and silently scores the
    wrong second.
    """
    try:
        series, when, strike = tk.split("-", 2)
        if not strike.startswith("T"):
            return None
        strike = float(strike[1:])
        day = dt.datetime.strptime(when[:7], "%y%b%d")
        hour = int(when[7:])
        et = day.replace(hour=hour % 24)
        # ET is UTC-4 in September
        close = int((et - dt.datetime(1970, 1, 1)).total_seconds()) + 4 * 3600
        return series, close, strike
    except (ValueError, IndexError):
        return None


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    p = parse_ticker("KXBTCD-26SEP1319-T76599.99")
    ck(p is not None and p[0] == "KXBTCD" and abs(p[2] - 76599.99) < 1e-9,
       "the series and strike come off the ticker")
    got = dt.datetime.utcfromtimestamp(p[1]).strftime("%Y-%m-%d %H:%MZ")
    ck(got == "2026-09-13 23:00Z",
       "and 26SEP13 hour 19 is the 19:00 EASTERN close = %s. Reading the hour "
       "as UTC would put it four hours out and score the wrong second." % got)
    ck(parse_ticker("KXBTC15M-26SEP140530-30") is None,
       "a 15-minute ticker has no T-strike and is refused, not guessed at")
    ck(parse_ticker("rubbish") is None and parse_ticker("") is None,
       "and rubbish is refused")
    # the ask-side test, on planted numbers
    def buyable(ask, ceiling=CEILING):
        return ask is not None and 0.0 < ask <= ceiling + 1e-9
    ck(buyable(0.95) and buyable(0.98),
       "95c and 98c are buyable")
    ck(not buyable(0.99) and not buyable(1.00),
       "99c and a DOLLAR are not -- and a dollar is exactly what the hourly "
       "ladder quotes on its certain winners")
    ck(not buyable(None) and not buyable(0.0),
       "a missing or zero ask is not an offer")
    print("pinhourlyedge selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    if not os.path.exists(SAMPLE):
        print("loaded nothing -- %s missing; run research/pinhourly.py first"
              % SAMPLE)
        return 0
    rows = []
    for line in open(SAMPLE, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        p = parse_ticker(d.get("ticker", ""))
        if p is None:
            continue
        d["series"], d["close"], d["strike"] = p
        d["tau"] = d["close"] - d.get("sec", 0)
        rows.append(d)
    if not rows:
        print("loaded nothing -- no parseable hourly rows")
        return 0
    print("\n%d sampled book rows over %d markets, %d closes"
          % (len(rows), len(set(r["ticker"] for r in rows)),
             len(set(r["close"] for r in rows))))
    taus = sorted(r["tau"] for r in rows)
    print("seconds to close: %d .. %d\n" % (taus[0], taus[-1]))

    idx = idxload.load(sorted(set(SERIES_INDEX[r["series"]] for r in rows
                                  if r["series"] in SERIES_INDEX)),
                       verbose=False)
    scored = 0
    certain = 0
    offered = collections.Counter()
    examples = []
    for r in rows:
        iid = SERIES_INDEX.get(r["series"])
        D = idx.get(iid)
        if D is None or not (3 <= r["tau"] <= 30):
            continue
        ix = pinrun.IndexWS([iid])
        lo = r["close"] - 70
        for s in range(lo, r["sec"] + 1):
            v = D.get(s)
            if v is not None:
                ix.ticks[iid][s] = v
        sg = ix.sigma(iid)
        if sg is None:
            continue
        f = pinrun.fair(ix, iid, r["close"], r["sec"], r["strike"], sg)
        if f is None:
            continue
        scored += 1
        if f >= PIN:
            want, ask = "yes", r.get("yes_ask")
        elif f <= 1.0 - PIN:
            want, ask = "no", (None if r.get("yes_bid") is None
                               else round(1.0 - r["yes_bid"], 4))
        else:
            offered["not near-certain"] += 1
            continue
        certain += 1
        if ask is None or ask <= 0:
            offered["no offer at all"] += 1
        elif ask > CEILING + 1e-9:
            offered["offered ABOVE our 98c ceiling"] += 1
        else:
            offered["BUYABLE at or under 98c"] += 1
            if len(examples) < 8:
                examples.append((r, want, ask, f))
    print("  scored %d rows inside tau 3-30 with an index and a sigma" % scored)
    print("  of those, %d had a NEAR-CERTAIN side (>= %.1f%%)\n"
          % (certain, 100 * PIN))
    for k in ("BUYABLE at or under 98c", "offered ABOVE our 98c ceiling",
              "no offer at all", "not near-certain"):
        if k in offered:
            base = certain if k != "not near-certain" else scored
            print("    %-34s %6d  %5.1f%%"
                  % (k, offered[k], 100.0 * offered[k] / max(1, base)))
    if examples:
        print("\n  THE BUYABLE ONES:")
        for r, want, ask, f in examples:
            print("    %-34s tau %2ds  want %-3s @ %.3f  model %.5f"
                  % (r["ticker"], r["tau"], want, ask, f))
    else:
        print("\n  NOT ONE near-certain side was buyable at or under 98c.")
    print("\n  For comparison, the 15-minute markets: a near-certain side is")
    print("  offered under the ceiling on about 2%% of scanned moments, and that")
    print("  2%% is the entire strategy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
