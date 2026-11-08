"""test_unbooked.py -- v-ledger-unreadable (2026-11-07): a Kalshi settlement row whose money cannot be worked out (a count,
a cost or the fee missing -- what a renamed field looks like) or a voided market is in NO money total, and is counted.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_unbooked.py   (or all of them: research\\botstats.py --selftest)
  - the per-bot money block, the pot rows, the coin race and /funds' past days leave both out; before this the
    unreadable row booked as the whole stake lost (-$49.10 here) and the voided one too;
  - botdata/ledgercheck.py counts them over every pot of botstats' cache and the main account's kalshi_ledger.json (a
    settlement in both once), remembers the answer until a file changes, and finds nothing on a healthy cache;
  - THE RULE: no module of botdata / phone / bots reads a pot's settled rows except through money.booked_rows (the
    counter itself excepted), and every phone reader of kalshi_ledger.json filters with pinledger.booked.
"""
import calendar
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

import pinledger                                                    # noqa: E402
from botdata import kalshi as _kalshi                               # noqa: E402
from botdata import ledgercheck as _lc                              # noqa: E402
from botdata import money as _money                                 # noqa: E402
from botdata import pots as _pots                                   # noqa: E402
from botdata import report as _report                               # noqa: E402

NOW = float(calendar.timegm((2026, 9, 30, 16, 30, 0)))          # 12:30 PM ET, Wed Sep 30
RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def S(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0, value=None):
    v = {"yes": 100, "no": 0}.get(res) if value is None else value
    return {"ticker": tk, "settled_time": st, "market_result": res, "value": v,
            "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc,
            "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee, "revenue": 0}


def world():
    good = S("KXBTC15M-26SEP301145-45", "2026-09-30T15:45:05Z", "no", nn=50, nc=49.0, fee=0.10)      # +0.90
    bad = S("KXETH15M-26SEP301130-30", "2026-09-30T15:30:05Z", "no", nn=50, nc=49.0, fee=0.10)       # won: +0.90
    del bad["no_count_fp"]                                                                            # ... renamed
    void = S("KXSOL15M-26SEP301115-15", "2026-09-30T15:15:05Z", "void", nn=50, nc=49.0, fee=0.10, value=0)
    return good, bad, void


def _cache(rows_by_sub):
    return {"v": 1, "subs": {s: {"rows": {pinledger.key_of(r): r for r in rows}, "fetched": NOW, "tried": NOW,
                                 "complete": True} for s, rows in rows_by_sub.items()}, "ledgers": {}}


def test_the_bug_it_stops():
    good, bad, void = world()
    ck(abs(pinledger.pnl(bad) + 49.10) < 1e-9 and abs(pinledger.pnl(good) - 0.90) < 1e-9,
       "without the rule the WON market with a renamed count books -$49.10 (the whole stake), its twin +$0.90")
    ck(abs(pinledger.pnl(void) + 0.10) < 1e-9,
       "a voided market books only its fee (-$0.10), never the whole stake")
    ck([r["ticker"] for r in _money.booked_rows({"rows": {"a": good, "b": bad, "c": void}})] == [good["ticker"]],
       "money.booked_rows keeps only the readable, not-voided row")


def test_money_block_leaves_them_out():
    good, bad, void = world()
    b = _report._money_block_raw(_cache({"0": [good, bad, void]}), "pin", "2026-09-30")
    ck(b["today"]["markets"] == 1 and abs(b["today"]["money"] - 0.90) < 1e-9 and b["all_time"]["markets"] == 1
       and [m["ticker"] for m in b["markets"]] == [good["ticker"]] and b["today"]["lost"] == 0,
       "the pin bot's money block: 1 market, +$0.90 today, no loss (it read -$97.30 and 2 losses before the rule)")


def test_pot_rows_race_and_funds_days():
    good, bad, void = world()
    x = {"rows": {"a": good, "b": bad, "c": void}}
    ck([r["ticker"] for r in _pots.pot_rows(x, "0")] == [good["ticker"]], "pots.pot_rows: booked rows only")
    race_ok = S("KXCRYPTOLEAD15M-26SEP301030-XRP", "2026-09-30T14:31:10Z", "yes", yn=20, yc=19.60, fee=0.03)
    race_bad = dict(race_ok, ticker="KXCRYPTOLEAD15M-26SEP301045-XRP", settled_time="2026-09-30T14:46:10Z")
    del race_bad["fee_cost"]
    import botstats as bs
    from botdata import series as _series
    rr = _series.race_rows(bs, _cache({"0": [race_ok, race_bad]}))
    ck(len(rr) == 1 and abs(rr[0][1] - 0.37) < 1e-9, "the coin race's rows: the unreadable leg is no race (%s)" % (rr,))
    with sandbox():
        with open(_kalshi.cache_path(), "w", encoding="utf-8") as fh:
            json.dump(_cache({s: ([good, bad, void] if s == "0" else []) for s in bs.SUBS}), fh)
        old = _kalshi.set_readonly(True)                # the cache as it is: no Kalshi read, no write
        try:
            rows, why = _kalshi.pot_settlements(NOW)
        finally:
            _kalshi.set_readonly(old)
        ck([r["ticker"] for r in rows.get("0", [])] == [good["ticker"]] and not why,
           "pot_settlements (/funds' past days from botstats' cache): booked rows only (%s)" % (why,))


def test_funds_settled_leaves_them_out():
    good, bad, void = world()
    from phone.commands.funds import read as F
    res = F.funds_settled(lambda path, q: (200, {"settlements": [good, bad, void], "cursor": ""}), [0], NOW, memo={})
    ck([r["ticker"] for r in res[0]["rows"]] == [good["ticker"]], "/funds' own settlement pull keeps booked rows only")


def test_ledgercheck_counts_each_settlement_once():
    good, bad, void = world()
    bad1 = dict(bad, ticker="KXNEAR15M-26SEP301130-30")
    only_main = S("KXXRP15M-26SEP301100-00", "2026-09-30T15:00:05Z", "scalar", yn=5, yc=4.0, value=None)
    with sandbox() as td:
        _lc.forget()
        with open(_kalshi.cache_path(), "w", encoding="utf-8") as fh:
            json.dump(_cache({"0": [good, bad, void], "1": [bad1]}), fh)
        pinledger.save_cache({pinledger.key_of(r): r for r in (good, bad, only_main)}, os.path.join(td, _lc.LEDGER_NAME))
        s = _lc.scan(td)
        ck(s["unreadable"] == 3 and s["void"] == 1 and s["by_pot"] == {"0": 2, "1": 1} and s["error"] is None,
           "3 unreadable (the main account's twice-listed one counted once, subaccount 1's, the ledger-only tie with no "
           "value) and 1 voided: %s" % s)
        ck(("KXETH15M-26SEP301130-30", "no no_count_fp") in s["examples"]
           and any("no usable value" in w for _t, w in s["examples"]) and s["void_examples"] == [void["ticker"]],
           "each with why, in words")
        s["examples"].append("x")
        ck(len(_lc.scan(td)["examples"]) == 3, "a caller changing its copy changes nothing remembered")
        # each file alone is watched (the 2026-11-07 tests review: a memo keyed on the ledger alone passed every suite)
        with open(_kalshi.cache_path(), "w", encoding="utf-8") as fh:
            json.dump(_cache({"0": [good, bad, void], "1": []}), fh)
        os.utime(_kalshi.cache_path(), (NOW + 1, NOW + 1))
        s1 = _lc.scan(td)
        ck(s1["unreadable"] == 2 and s1["by_pot"] == {"0": 2}, "ONLY the cache changed -> read again: %s" % s1)
        pinledger.save_cache({pinledger.key_of(r): r for r in (good, bad)}, os.path.join(td, _lc.LEDGER_NAME))
        os.utime(os.path.join(td, _lc.LEDGER_NAME), (NOW + 2, NOW + 2))
        s1 = _lc.scan(td)
        ck(s1["unreadable"] == 1 and s1["by_pot"] == {"0": 1}, "ONLY the ledger changed -> read again: %s" % s1)
        with open(_kalshi.cache_path(), "w", encoding="utf-8") as fh:
            json.dump(_cache({"0": [good], "1": []}), fh)
        os.utime(_kalshi.cache_path(), (NOW + 5, NOW + 5))
        pinledger.save_cache({pinledger.key_of(good): good}, os.path.join(td, _lc.LEDGER_NAME))
        s2 = _lc.scan(td)
        ck(s2["unreadable"] == 0 and s2["void"] == 0 and s2["examples"] == [],
           "NULL: a healthy cache and ledger (the files changed) -> nothing left out")
        _lc.forget()


def test_ledgercheck_never_raises():
    with sandbox() as td:
        _lc.forget()
        with open(_kalshi.cache_path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        s = _lc.scan(td)
        ck(s["unreadable"] == 0 and s["error"] is None, "an unreadable cache file reads as empty (load_cache's rule)")
        saved = _kalshi.load_cache
        _kalshi.load_cache = lambda: (_ for _ in ()).throw(RuntimeError("planted"))
        try:
            _lc.forget()
            s = _lc.scan(td)
        finally:
            _kalshi.load_cache = saved
            _lc.forget()
        ck(s["unreadable"] == 0 and "planted" in (s["error"] or ""), "a failing read: zero counts and its error")


def test_the_rule_every_reader_goes_through_booked_rows():
    """Fix the class: a raw read of a pot's settled rows, or of kalshi_ledger.json without pinledger.booked, anywhere in
    botdata / phone / bots is a test failure (money.booked_rows and the counter are the only exceptions)."""
    raw = re.compile(r"""(\.get\(["']rows["']\)\s*or\s*\{\}\)\s*\.(values|items)\(|\[["']rows["']\]\s*\.(values|items)\()""")
    ck(raw.search('rows = list((x.get("rows") or {}).values())') and raw.search('for k, s in x["rows"].items():'),
       "the rule finds the old raw reads (pots.pot_rows before 11-07), so a pass means something")
    allowed = {os.path.join("botdata", "money.py"), os.path.join("botdata", "ledgercheck.py")}
    bad, led = [], []
    for top in ("botdata", "phone", "bots"):
        for d, dirs, files in os.walk(os.path.join(RESEARCH, top)):
            dirs[:] = [x for x in dirs if x not in ("tests", "__pycache__")]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(d, fn)
                rel = os.path.relpath(p, RESEARCH)
                with open(p, encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        if raw.search(line) and rel not in allowed:
                            bad.append("%s:%d" % (rel, i))
                        if "pinledger.load_cache(" in line and "booked" not in line and rel not in allowed:
                            led.append("%s:%d" % (rel, i))
    ck(bad == [], "no raw read of a pot's settled rows outside money.booked_rows (found: %s)" % bad)
    ck(led == [], "every phone / botdata reader of kalshi_ledger.json filters with pinledger.booked (found: %s)" % led)


if __name__ == "__main__":
    sys.exit(run(globals(), "test_unbooked"))
