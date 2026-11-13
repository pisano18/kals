"""test_other.py -- every booked settled row in every pot is counted exactly once: by the one bot that owns it, or by
'other' (v-other-every-pot, 2026-11-13).

The defect it guards: bots.owner() calls a row no bot claims in a pot with no catch-all bot 'other' -- subaccount 4 holds
the old coin-race reward test's KXCRYPTOLEAD15M legs (10-11 and 10-23, -$29.88) beside the FX taker's pairs -- but the
'other' money block read the main account only, so those rows were in NO money block: the phone's all-bots all-time
total read +$2,909.36 while every booked row added up to +$2,879.48 (pot_check['all'].settled), and the /days bars of
10-11 and 10-23 read high. Fix the class: in a planted world with every series some pot claims, and some no pot claims,
in EVERY pot, the bots plus 'other' must be every booked row, each once -- block by block, in all_bots' total and day by
day in series.all_day_markets (the /days and /share_brag source). A new pot, bot or series cannot drop a row unseen.
Run:
    C:\\Python314\\python.exe research\\botdata\\tests\\test_other.py      (or all of them: research\\botstats.py --selftest)
"""
import calendar
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

import botstats as bs                                               # noqa: E402
import pinledger                                                    # noqa: E402
from botdata import kalshi, money, report, series, tables           # noqa: E402

NOW = float(calendar.timegm((2026, 11, 13, 17, 0, 0)))          # noon ET, Fri Nov 13
TODAY = "2026-11-13"
# (Kalshi's day code, the ET day, a settled time that day): today, yesterday, two days inside the 30-day list (the reward
# test's own days) and one older than it (all time only)
DAYS = (("26NOV13", "2026-11-13", "2026-11-13T16:45:05Z"), ("26NOV12", "2026-11-12", "2026-11-12T16:45:05Z"),
        ("26OCT23", "2026-10-23", "2026-10-23T15:45:05Z"), ("26OCT11", "2026-10-11", "2026-10-11T15:45:05Z"),
        ("26SEP30", "2026-09-30", "2026-09-30T15:45:05Z"))
# every series some pot claims (the pin bot's coins and ladder, the race, the jump band's coins, the FX pairs, a
# commodity, a weather bracket) and two no pot claims (the old oil bot's, an unknown one)
SERIES = ("KXBTC15M", "KXBTCD", "KXCRYPTOLEAD15M", "KXNEAR15M", "KXEURUSD15M", "KXGOLD15M", "KXHIGHNY", "KXWTI15M",
          "KXZZZ15M")


def _ticker(sr, code):
    if sr == "KXBTCD":
        return "KXBTCD-%s11-T82899.99" % code
    if sr == "KXHIGHNY":
        return "KXHIGHNY-%s-B72.5" % code
    if sr == "KXCRYPTOLEAD15M":
        return "KXCRYPTOLEAD15M-%s1145-XRP" % code
    return "%s-%s1145-45" % (sr, code)


def _row(tk, st, won, n, cost, fee, pool):
    """A whole settled row: n YES contracts that cost `cost`; won = the market settled YES."""
    return {"ticker": tk, "settled_time": st, "market_result": "yes" if won else "no", "value": 100 if won else 0,
            "event_ticker": tk.rsplit("-", 1)[0], "yes_count_fp": "%.2f" % n, "yes_total_cost_dollars": "%.6f" % cost,
            "no_count_fp": "0.00", "no_total_cost_dollars": "0.000000", "fee_cost": "%.6f" % fee, "revenue": 0,
            "exchange_index": pool}


def _world():
    """{sub: [rows]}: every SERIES on every DAY in EVERY pot (each row its own money: a lost or a won market of a
    size no other row has), plus one unreadable row in subaccount 4 that no total may count."""
    out, k = {}, 0
    for s in tables.SUBS:
        rows = []
        for sr in SERIES:
            for code, _day, st in DAYS:
                k += 1
                n = 2 + k % 7
                won = k % 3 != 0
                rows.append(_row(_ticker(sr, code), st, won, n, round(n * 0.96 + k * 0.0007, 6), round(0.01 + k * 0.0001, 6),
                                 0 if (s == "4" and sr == "KXEURUSD15M") else 2))
        out[s] = rows
    out["4"].append({"ticker": "KXCRYPTOLEAD15M-26OCT230430-ETH", "settled_time": "2026-10-23T15:45:05Z",
                     "market_result": "yes", "exchange_index": 2})            # no counts, no costs: unreadable
    return out


def _cache(world):
    def sub(rows):
        return {"fetched": NOW - 60, "tried": NOW - 60, "complete": True,
                "rows": {pinledger.key_of(r): r for r in rows}, "positions": [], "pos_t": NOW - 60,
                "balance": 100.0, "bal_t": NOW - 60}
    return {"v": 1, "subs": {s: sub(rows) for s, rows in world.items()}, "procs": None,
            "ledgers": {"fetched": NOW - 60, "tried": NOW - 60, "transfers": [], "deposits": [], "withdrawals": [],
                        "subaccount_balances": []}}


def _every(c):
    """[(sub, booked row)] over every pot (money.booked_rows: what any money total may count)."""
    return [(s, r) for s in tables.SUBS for r in money.booked_rows(c["subs"].get(s) or {})]


def test_the_world_has_unowned_rows_outside_the_main_account():
    c = _cache(_world())
    unowned = sorted({s for s, r in _every(c) if tables.owner(r.get("ticker"), s) == "other"})
    ck("0" in unowned and "4" in unowned,
       "the planted world has rows no bot owns in the main account (oil, unknown) AND outside it (subaccount 4's coin "
       "legs), so the rule below bites: %s" % unowned)
    ck(tables.owner("KXCRYPTOLEAD15M-26OCT230415-XRP", "4") == "other"
       and tables.owner("KXEURUSD15M-26OCT231145-45", "4") == "fx",
       "subaccount 4: an FX pair is the FX taker's, the old reward test's coin leg is no bot's")
    ck(len([1 for s in tables.SUBS for r in (c["subs"][s]["rows"] or {}).values() if not pinledger.booked(r)]) == 1,
       "one unreadable row is planted (money.booked_rows leaves it out of every total and of the expected sum)")


def test_every_booked_row_is_in_exactly_one_money_block():
    """Block by block: the markets of every bot plus 'other' are every booked row in every pot, each once."""
    with sandbox():
        c = _cache(_world())
        names = tuple(tables.BOTS) + ("other",)
        blocks = {n: report._money_block_raw(c, n, TODAY) for n in names}
        ck(all(blocks[n]["ok"] for n in names), "every block reads (%s)" % [n for n in names if not blocks[n]["ok"]])
        every = _every(c)
        want = collections.Counter((r["ticker"], round(pinledger.pnl(r), 4)) for _s, r in every)
        got = collections.Counter((m["ticker"], round(m["money"], 4)) for n in names for m in blocks[n]["markets"])
        ck(got == want,
           "every booked row in every pot is in exactly one block -- missing %s, extra %s"
           % (sorted((want - got).elements())[:6], sorted((got - want).elements())[:6]))
        tot = sum(pinledger.pnl(r) for _s, r in every)
        alltime = sum(blocks[n]["all_time"]["money"] for n in names if blocks[n].get("all_time"))
        ck(abs(alltime - tot) < 1e-6 and sum(blocks[n]["all_time"]["markets"] for n in names) == len(every),
           "all time: the bots plus 'other' = pinledger.pnl over every booked row in every pot (%s vs %s, %d markets)"
           % (bs.usd(alltime), bs.usd(tot), len(every)))
        sub4 = sum(pinledger.pnl(r) for s, r in every if s == "4" and tables.owner(r.get("ticker"), s) == "other")
        main = sum(pinledger.pnl(r) for s, r in every if s == "0" and tables.owner(r.get("ticker"), s) == "other")
        ck(abs(blocks["other"]["all_time"]["money"] - (main + sub4)) < 1e-6 and abs(sub4) > 0.01,
           "'other' = the main account's unowned rows (%s) + subaccount 4's (%s)" % (bs.usd(main), bs.usd(sub4)))
        ck(blocks["other"]["subaccount"] == 0 and blocks["other"]["source"] == "Kalshi settlements, main account",
           "'other' keeps the main account as its pot (its % base and its words)")


def test_all_bots_total_and_every_day_add_up_to_every_row():
    """all_bots' all-time total and series.all_day_markets' days (the /days and /share_brag bars) = every booked row."""
    with sandbox():
        c = _cache(_world())
        with open(kalshi.cache_path(), "w", encoding="utf-8") as fh:
            json.dump(c, fh)
        kalshi.set_readonly(True)
        try:
            a = report.all_bots(now=NOW, procs=[])
            _bs, _ctx, rows, missing = series.all_day_markets(bs, NOW, procs=[])
        finally:
            kalshi.set_readonly(False)
        every = _every(c)
        tot = sum(pinledger.pnl(r) for _s, r in every)
        parts = [a["bots"][b]["money"] for b in tables.BOTS] + [a["other"]]
        alltime = sum(m["all_time"]["money"] for m in parts if m.get("all_time"))
        ck(abs(alltime - tot) < 1e-6 and abs(a["total"]["all_time"]["money"] - tot) < 1e-6
           and not a["total"]["all_time"]["partial"],
           "all_bots: the sum over every bot plus 'other' of all-time money, and the ALL-BOTS total, = every booked row in "
           "every pot (%s, %s vs %s)" % (bs.usd(alltime), bs.usd(a["total"]["all_time"]["money"]), bs.usd(tot)))
        want = collections.defaultdict(float)
        for _s, r in every:
            m = money.market(r)
            want[m["day"]] += m["money"]
        got = collections.defaultdict(float)
        for d, _t, v, _b in rows:
            got[d] += v
        bad = [(d, round(got.get(d, 0.0), 4), round(v, 4)) for d, v in sorted(want.items()) if abs(got.get(d, 0.0) - v) > 1e-6]
        ck(not missing and not bad and len(rows) == len(every) and set(got) == set(want),
           "series.all_day_markets: every ET day's money = every booked row of that day in every pot (the reward test's "
           "10-11 and 10-23 included): %s" % (bad or "all %d days agree" % len(want)))
        d30 = {d["day"]: d["money"] for d in a["total_days_30"]}
        ck(all(abs(d30[d] - want[d]) < 1e-6 for d in ("2026-10-23", "2026-11-12")),
           "and all_bots' 30-day list carries them too (10-23: %s)" % bs.usd(d30["2026-10-23"]))


if __name__ == "__main__":
    sys.exit(run(globals(), "test_other"))
