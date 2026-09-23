"""pinledger.py -- the books, taken from KALSHI, not from our own logs.

WHY THIS EXISTS. The operator, 2026-09-18: *"go make the tool derive all data
exactly from Kalshi from the api and not try to calculate it itself. It's got
many numbers and trades wrong about today."* He was right, and the count of
ways our own logs got it wrong in one evening is the argument:

1. day totals were CRYPTO-ONLY, because nothing read `cmdlive-*.jsonl`;
2. de-duplicating on `(ticker, t)` silently dropped the SECOND LEG of any
   market that settled twice in the same second, which reported a commodity
   day as -$23.14 when the records summed to -$51.94;
3. five positions open when a process was killed NEVER GOT A SETTLED RECORD AT
   ALL, so they were simply missing (-$4.89);
4. a UTC date filter pulled in the previous evening and turned $23 into $47.

Every one of those is a bookkeeping bug in a log we write ourselves. **Kalshi
already keeps these books and its copy is the one that matters**, so this file
reads `/portfolio/settlements` and computes nothing it can look up:

    P&L = revenue - (yes cost + no cost) - fees

all four terms straight from the exchange, per settled market. A position we
forgot, a leg we double-counted, a process we killed -- none of it can go
missing, because the exchange settled it whether or not our bot was alive.

**The cache is append-only and keyed by (ticker, settled_time).** A refresh
pages backwards from the newest settlement and stops at the first one already
on file, so the normal run costs a handful of requests. `--backfill` walks the
whole history once.

WHAT THIS FILE IS NOT. It is not a substitute for the trade logs. Those carry
WHY we traded -- the gates, the model's belief, the book we saw. This carries
only WHAT HAPPENED, and it is the authority on that.
"""
import argparse
import calendar
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinday                                                    # noqa: E402

RESULTS = os.path.join(os.path.dirname(HERE), "results")
LEDGER = os.path.join(RESULTS, "kalshi_ledger.json")
PAGE = 200


def money(s, *names):
    """First present field, as a float. Missing or unparseable -> 0.0.

    Kalshi sends dollars as decimal STRINGS and revenue as an integer of
    CENTS, and mixing those two up is the exact class of error this file was
    written to end. Every caller here names the field it wants and the unit is
    handled once, at the call site, in `pnl()`.
    """
    for n in names:
        if n in s:
            try:
                return float(s[n])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def payout(s):
    """Dollars the exchange paid for this settled market.

    **NOT `revenue`.** Kalshi reports `revenue: 0` on a market where we held
    BOTH sides, even though the winning side still pays a dollar a contract --
    seen on `KXBTC15M-26SEP172115-15`, where we held 99 YES and 99 NO, the
    market settled NO, and `revenue` read 0 against a true payout of $99.
    Trusting it turned a -$27.87 loss into -$126.87 and made the whole
    all-time figure -$122 on an account that is up $422.

    The winning side pays $1.00 a contract and the losing side pays nothing.
    That is the definition of the instrument, so it is derived from the two
    numbers Kalshi is never wrong about: the settled result and how many
    contracts of each side we held.
    """
    res = str(s.get("market_result") or "").strip().lower()
    # 2026-09-23: A TIE PAYS HALF, AND THIS FUNCTION BOOKED IT AS ZERO.
    # KXCRYPTOLEAD15M-26SEP230715 settled `market_result: "scalar"` with
    # `value: 50` -- two coins tied for the lead, so every contract paid 50c.
    # We held 1 XRP YES at 97c and 1 HYPE NO at 98c: a real loss of ~48c each,
    # which this reported as -$1.95, the whole stake. `value` is the settlement
    # in cents and Kalshi sets it on EVERY row (100 on yes, 0 on no, 50 here;
    # checked across all 960 settlements), so it covers all three cases and the
    # yes/no arithmetic below is unchanged by construction.
    val = s.get("value")
    if val is not None:
        try:
            v = float(val) / 100.0
        except (TypeError, ValueError):
            v = None
        if v is not None and 0.0 <= v <= 1.0:
            return money(s, "yes_count_fp") * v + money(s, "no_count_fp") * (1.0 - v)
    if res == "yes":
        return money(s, "yes_count_fp")
    if res == "no":
        return money(s, "no_count_fp")
    # A result we do not understand and no usable `value`: pay nothing and be
    # visible about it rather than guessing a payout.
    return 0.0


def pnl(s):
    """Dollars made or lost on one settled market, entirely from Kalshi.

    payout - what both sides cost - fees. Costs and fees are dollars as sent.
    Nothing here is modelled or recomputed from a price we remember.
    """
    cost = money(s, "yes_total_cost_dollars") + money(s, "no_total_cost_dollars")
    return payout(s) - cost - money(s, "fee_cost")


def key_of(s):
    return "%s|%s" % (s.get("ticker"), s.get("settled_time"))


def load_cache(path=LEDGER):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}
    return d.get("settlements", {}) if isinstance(d, dict) else {}


def save_cache(rows, path=LEDGER):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"settlements": rows,
                   "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh)
    os.replace(tmp, path)


def merge(rows, page):
    """Add a page of settlements. Returns how many were NEW.

    Append-only on (ticker, settled_time): the exchange's own record of a
    settlement never changes, so a key we already hold is never rewritten and
    a re-run can never double-count.
    """
    new = 0
    for s in page:
        k = key_of(s)
        if k in rows:
            continue
        rows[k] = s
        new += 1
    return new


def by_et_day(rows):
    """{'YYYY-MM-DD': {'n', 'dollars', 'losses', 'series'}} on the ET clock."""
    out = collections.defaultdict(
        lambda: {"n": 0, "dollars": 0.0, "losses": 0, "series": collections.Counter()})
    for s in rows.values():
        tk = s.get("ticker") or ""
        d = pinday.et_day_of_ticker(tk)
        if d is None:
            t = s.get("settled_time") or ""
            try:
                ts = calendar.timegm(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
                d = pinday.et_day_of_epoch(ts)
            except (TypeError, ValueError):
                continue
        v = pnl(s)
        out[d]["n"] += 1
        out[d]["dollars"] += v
        if v < 0:
            out[d]["losses"] += 1
        out[d]["series"][tk.split("-")[0]] += 1
    return dict(out)


def fetch(rows, creds, backfill=False, page=PAGE, getter=None):
    """Page BACKWARDS from the newest settlement, stopping at one we hold.

    Kalshi returns settlements newest-first, so an incremental refresh only
    needs to read until it recognises something. `--backfill` reads to the end
    once. Returns (new rows added, pages read).
    """
    get = getter
    if get is None:
        import pintake
        def get(path, q):                                        # noqa: E306
            return pintake._get(creds["base"], creds["pk"], creds["key_id"], path, q)
    cursor, added, pages = None, 0, 0
    while True:
        q = {"limit": page}
        if cursor:
            q["cursor"] = cursor
        st, d = get("/portfolio/settlements", q)
        pages += 1
        if st != 200 or not isinstance(d, dict):
            break
        got = d.get("settlements") or []
        if not got:
            break
        n = merge(rows, got)
        added += n
        cursor = d.get("cursor")
        if not cursor:
            break
        if not backfill and n == 0:
            break            # this whole page was already on file
    return added, pages


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinledger selftest: FAILED -- " + msg)

    # A REAL settlement, copied from the API: 4 NO contracts at 98c that won.
    s = {"ticker": "KXNEAR15M-26SEP172345-45", "market_result": "no",
         "no_count_fp": "4.00", "no_total_cost_dollars": "3.920000",
         "yes_total_cost_dollars": "0.000000", "revenue": 400,
         "fee_cost": "0.005500", "settled_time": "2026-09-18T03:45:04.700045Z"}
    ck(abs(pnl(s) - (4.00 - 3.92 - 0.0055)) < 1e-9,
       "P&L is payout minus cost minus fee (+$0.0745 on this one): 4 winning NO "
       "contracts pay $4.00 against $3.92 of stake")
    ck(abs(pnl(dict(s, market_result="yes")) + (3.92 + 0.0055)) < 1e-9,
       "the same market settling the OTHER way pays nothing and costs the whole "
       "stake plus the fee")
    # THE BUG THIS FUNCTION EXISTS FOR: both sides held, revenue reported as 0.
    both = {"ticker": "KXBTC15M-26SEP172115-15", "market_result": "no",
            "yes_count_fp": "99.00", "yes_total_cost_dollars": "52.470000",
            "no_count_fp": "99.00", "no_total_cost_dollars": "71.280000",
            "revenue": 0, "fee_cost": "3.123400",
            "settled_time": "2026-09-18T01:15:04.588332Z"}
    ck(abs(payout(both) - 99.0) < 1e-9,
       "a HEDGED market pays for its winning side even though Kalshi reports "
       "revenue: 0 -- 99 winning NO contracts are $99")
    ck(abs(pnl(both) - (-27.8734)) < 1e-4,
       "so the hedged Bitcoin market is -$27.87, the number the operator saw. "
       "Trusting `revenue` made it -$126.87 and the all-time total -$122 on an "
       "account that is up $422")
    # A TIE. Both rows copied from the API: KXCRYPTOLEAD15M-26SEP230715
    # settled `scalar` with `value: 50` -- two coins tied for the lead at
    # 09-23 13:55:38Z, and every contract paid 50c.
    tie_y = {"ticker": "KXCRYPTOLEAD15M-26SEP230715-XRP", "market_result": "scalar",
             "value": 50, "revenue": 50, "yes_count_fp": "1.00",
             "yes_total_cost_dollars": "0.970000", "no_count_fp": "0.00",
             "no_total_cost_dollars": "0.000000", "fee_cost": "0.002100"}
    tie_n = {"ticker": "KXCRYPTOLEAD15M-26SEP230715-HYPE", "market_result": "scalar",
             "value": 50, "revenue": 50, "no_count_fp": "1.00",
             "no_total_cost_dollars": "0.980000", "yes_count_fp": "0.00",
             "yes_total_cost_dollars": "0.000000", "fee_cost": "0.001400"}
    ck(abs(payout(tie_y) - 0.50) < 1e-9 and abs(payout(tie_n) - 0.50) < 1e-9,
       "A TIE PAYS HALF TO BOTH SIDES: one YES and one NO each collect 50c")
    ck(abs(pnl(tie_y) + 0.4721) < 1e-4 and abs(pnl(tie_n) + 0.4814) < 1e-4,
       "so the real 09-23 tie cost 47c and 48c -- not the 97c and 98c whole "
       "stake this function booked before (it paid 0 on any non-yes/no result)")
    ck(abs(payout(dict(s, value=0)) - payout(s)) < 1e-9
       and abs(payout(dict(both, value=0)) - payout(both)) < 1e-9,
       "NULL: `value` on an ordinary NO market gives exactly the old answer, "
       "so nothing that already settled moves")
    ck(abs(payout({"market_result": "yes", "value": 100, "yes_count_fp": "7",
                   "no_count_fp": "3"}) - 7.0) < 1e-9,
       "and `value: 100` on a YES market pays its YES contracts only")
    ck(payout(dict(tie_y, value="junk")) == 0.0
       and abs(payout(dict(tie_y, value=140)) - 0.0) < 1e-9,
       "NULL: an unreadable or impossible `value` falls through to the result "
       "and a `scalar` result pays nothing rather than inventing a payout")
    ck(pnl({}) == 0.0 and payout({}) == 0.0,
       "NULL: an empty settlement is worth nothing, not a crash")
    ck(payout(dict(s, market_result="")) == 0.0
       and payout(dict(s, market_result="void")) == 0.0,
       "NULL: a market with no yes/no result pays nothing rather than guessing")
    ck(pnl(dict(s, no_count_fp="junk", fee_cost=None)) == -3.92,
       "unparseable numbers read as zero rather than poisoning the total")

    # append-only, and a re-run cannot double-count
    rows = {}
    ck(merge(rows, [s, s]) == 1 and len(rows) == 1,
       "the same settlement twice in one page is stored once")
    ck(merge(rows, [s]) == 0, "and a later page containing it adds nothing")
    s2 = dict(s, settled_time="2026-09-18T04:00:00Z")
    ck(merge(rows, [s2]) == 1,
       "but the SAME ticker settling at a different time is a different "
       "settlement -- this is exactly what (ticker, t) de-duplication broke")

    # the ET day comes from the ticker, not the settled_time
    d = by_et_day(rows)
    ck("2026-09-17" in d and "2026-09-18" not in d,
       "a market closing 23:45 ET on the 17th belongs to the 17th, though "
       "Kalshi settles it at 03:45Z on the 18th")
    ck(d["2026-09-17"]["n"] == 2 and d["2026-09-17"]["series"]["KXNEAR15M"] == 2,
       "both settlements land on that day and are counted by series")
    ck(by_et_day({}) == {}, "NULL: no settlements, no invented days")

    # the pager stops at the first page it already has, unless backfilling
    pages = [{"settlements": [s], "cursor": "c1"},
             {"settlements": [s2], "cursor": "c2"},
             {"settlements": [], "cursor": None}]
    seen = {"i": 0}
    def fake(path, q):                                           # noqa: E306
        i = seen["i"]; seen["i"] += 1
        return 200, pages[min(i, len(pages) - 1)]
    r2 = {}
    added, np_ = fetch(r2, None, backfill=True, getter=fake)
    ck(added == 2 and len(r2) == 2, "backfill reads until the pages run out")
    seen["i"] = 0
    added2, _ = fetch(r2, None, backfill=False, getter=fake)
    ck(added2 == 0,
       "an incremental refresh stops at the first page it already holds, so "
       "the normal run costs one request")
    def dead(path, q):                                           # noqa: E306
        return 401, {"error": "nope"}
    r3 = {}
    ck(fetch(r3, None, getter=dead) == (0, 1) and r3 == {},
       "NULL: an auth failure adds nothing and does not wipe the cache")
    print("pinledger selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--backfill", action="store_true",
                    help="read the WHOLE settlement history, not just what is new")
    ap.add_argument("--days", type=int, default=8)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    import ordercli
    import pintake
    import kauth
    creds = {"base": pintake.PROD_ELECTIONS, "key_id": kauth.KEY_ID,
             "pk": ordercli.load_key(pintake.PROD_KEY_FILE)}
    rows = load_cache()
    had = len(rows)
    added, pages = fetch(rows, creds, backfill=a.backfill)
    save_cache(rows)
    print("settlements on file: %d (+%d new, %d requests)" % (len(rows), added, pages))
    if not rows:
        print("loaded nothing")
        return 0
    days = by_et_day(rows)
    print("\n  FROM KALSHI'S OWN BOOKS -- revenue minus cost minus fees, by EASTERN day")
    print("  %-12s %6s %11s %8s   %s" % ("ET day", "markets", "made", "losses", "series"))
    for d in sorted(days)[-a.days:]:
        v = days[d]
        top = ", ".join("%s %d" % (k.replace("15M", "").replace("KX", ""), n)
                        for k, n in v["series"].most_common(4))
        print("  %-12s %6d %+11.2f %8d   %s" % (d, v["n"], v["dollars"], v["losses"], top))
    tot = sum(v["dollars"] for v in days.values())
    n = sum(v["n"] for v in days.values())
    print("  %-12s %6d %+11.2f" % ("ALL TIME", n, tot))
    today = pinday.et_day_of_epoch(time.time())
    v = days.get(today)
    print("\n  TODAY (%s ET): %s" % (today, "nothing settled yet" if not v else
          "%d markets, %+.2f, %d losses" % (v["n"], v["dollars"], v["losses"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
