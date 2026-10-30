"""test_monitor_balance.py -- the balance check (v-tg-rebuild step 12, lane Q): Kalshi's cash + open bets in a pot
(botstats' cache) against what the one bot trading there says it holds (its Bot.books hook), alerted only when the gap
is past the tolerance on two Kalshi reads in a row, explained in $ (money Kalshi lists moving, markets only Kalshi has,
the rest), once per episode, 'agrees again'; a read in flight is skipped; the monitor's own Kalshi refresh waits.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_monitor_balance.py   (exit 0 = every test passed)
A fake clock, a hand-made botstats_cache.json and ladder log in a temp results folder, a Kalshi getter that refuses.
KALS_TESTING=1; no network.
"""
import json
import os
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import bots                                                          # noqa: E402
from botdata import kalshi, paths, watch                             # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_monitor_balance_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)
T0 = 1793370120.0               # 2026-10-30 14:22Z = 10:22 AM ET
LIVE = {b.name: [1000 + i, "", "python.exe -u %s --live" % b.script] for i, b in enumerate(bots.all_bots())}
ASKED = []


def refuse(path, params):
    ASKED.append(path)
    return 599, "tests: no Kalshi"


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def ladder_log(extra=()):
    recs = [{"t": iso(T0 - 7200), "ev": "start", "pot": 700.0, "rails": {"day_stop": -140.0}},
            {"t": iso(T0 - 3600), "ev": "rescale", "pot": 800.0, "rails": {"day_stop": -160.0}},
            {"t": iso(T0 - 3000), "ev": "live_fill", "ticker": "KXXRP15M-26OCT300930-30", "delta": 10},
            {"t": iso(T0 - 2900), "ev": "live_settle", "ticker": "KXXRP15M-26OCT300930-30", "pnl": 0.2},
            {"t": iso(T0 - 1500), "ev": "live_settle", "ticker": "KXZEC15M-26OCT300945-45", "pnl": -9.8}] + list(extra)
    with open(os.path.join(TMP, "ladder-live-orders.jsonl"), "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def cache(read_t, ladder_cash=790.4, open_cost=0.0, transfers=(), rows=None):
    """A botstats cache where every pot was read at read_t; subaccount 1 (the ladder) holds ladder_cash + open_cost."""
    subs, bal = {}, []
    for s in bots.subs():
        cash = ladder_cash if s == "1" else 10.0
        pool = 0 if s == "4" else 2
        subs[s] = {"tried": read_t, "fetched": read_t, "complete": True, "rows": dict(rows or {}) if s == "1" else {},
                   "positions": [{"ticker": "X", "at_risk": open_cost, "fees": 0.0}] if (s == "1" and open_cost) else [],
                   "pos_t": read_t, "balance": cash, "bal_t": read_t}
        bal.append({"subaccount_number": int(s), "exchange_index": pool, "balance": "%.4f" % cash})
    c = {"v": 1, "subs": subs, "procs": None, "pad": "x" * int(read_t % 97),
         "ledgers": {"tried": read_t, "fetched": read_t, "subaccount_balances": bal, "transfers": list(transfers),
                     "deposits": [], "withdrawals": []}}
    with open(kalshi.cache_path(), "w", encoding="utf-8") as fh:
        json.dump(c, fh)
    os.utime(kalshi.cache_path(), (read_t, read_t))


class Rig:
    def __init__(self):
        self.now = T0
        self.sent = []
        self.st = types.SimpleNamespace()
        self.ctx = FakeCtx(now_fn=lambda: self.now, bs_procs=[LIVE["ladder"]], cfg={}, bs_getter=refuse,
                           pots={"pots": {}})
        for b in bots.all_bots():
            p = os.path.join(TMP, b.stop_file)
            if b.name != "ladder":
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write("x")

    def tick(self, dt, **kw):
        self.now = T0 + dt
        if kw is not None:
            cache(T0 + dt - 5, **kw)
        before = len(self.sent)
        M.check_balance(self.ctx, M.state_of(self.st), lambda msg, urgent=False: self.sent.append((str(msg), urgent)),
                        self.now)
        return self.sent[before:]


def test_the_ladders_book():
    ladder_log()
    (b,) = watch.books("ladder", T0)
    assert (b.sub, b.value0, b.settled, b.markets, b.since) == ("1", 800.0, -9.6, 2, "its last resize"), b
    assert b.tickers == frozenset({"KXXRP15M-26OCT300930-30", "KXZEC15M-26OCT300945-45"})
    assert watch.books("ladder", T0 - 3300)[0].markets == 0          # Kalshi's read time bounds the book
    assert watch.books("ladder", T0 - 5000)[0].since == "its start"


def test_agreeing_pots_say_nothing():
    ladder_log()
    r = Rig()
    for dt in (0, 60, 120):
        assert r.tick(dt) == []                    # 790.40 = 800 - 9.60
    assert r.tick(180, ladder_cash=780.4, open_cost=10.0) == []   # an open bet is still the pot's money


def test_two_reads_then_once_then_agrees_again():
    ladder_log()
    r = Rig()
    assert r.tick(0, ladder_cash=765.4) == []      # read 1: $25 short
    got = r.tick(60, ladder_cash=765.4)             # read 2: the alert
    assert len(got) == 1 and got[0][1] is True, got
    msg = got[0][0]
    assert msg.startswith("⚠️ <b>BALANCE: Ladder's pot (subaccount 1) has $25.00 less on Kalshi than its books say</b>"), msg
    assert ("Kalshi <b>$765.40</b> (cash + open bets) · its books <b>$790.40</b> = $800.00 at its last resize (9:22 AM "
            "ET) - $9.60 settled in 2 markets since · gap <b>-$25.00</b> (-3.27% of the pot)") in msg, msg
    assert "• money Kalshi lists moving in or out since then: $0.00\n" in msg, msg
    assert "• markets Kalshi settled that its books do not have: none" in msg
    assert "• not explained by either: <b>-$25.00</b> -- a missed fill, a manual trade, or a money move" in msg
    assert "Seen on 2 Kalshi reads in a row (10:21 AM, 10:22 AM ET); the tolerance here is $7.75." in msg, msg
    assert r.tick(120, ladder_cash=765.4) == []    # once per episode
    assert r.tick(120, ladder_cash=765.4) == []    # the same read again: not judged twice
    got = r.tick(180)
    assert got == [("✅ <b>BALANCE: Ladder's pot (subaccount 1) agrees with its books again</b> -- Kalshi $790.40, books "
                    "$790.40 (off by $0.00, inside the $8.00 tolerance).", True)], got


def test_one_odd_read_is_not_enough():
    ladder_log()
    r = Rig()
    assert r.tick(0, ladder_cash=765.4) == []
    assert r.tick(60) == []
    assert r.tick(120, ladder_cash=765.4) == []    # the streak started again


def test_the_gap_explained():
    ladder_log()
    r = Rig()
    xfer = [{"amount_cents": 5000, "created_ts": int(T0 - 600), "from_subaccount": 0, "to_subaccount": 1,
             "exchange_index": 2}]
    row = {"k": {"ticker": "KXDOGE15M-26OCT301000-00", "settled_time": iso(T0 - 900), "market_result": "yes",
                 "no_count_fp": "10", "no_total_cost_dollars": "9.80", "yes_count_fp": "0",
                 "yes_total_cost_dollars": "0", "fee_cost": "0", "revenue": 0}}
    r.tick(0, ladder_cash=830.6, transfers=xfer, rows=row)
    got = r.tick(60, ladder_cash=830.6, transfers=xfer, rows=row)
    assert len(got) == 1, got
    msg = got[0][0]
    assert "has $40.20 more on Kalshi than its books say" in msg, msg
    assert "• money Kalshi lists moving in or out since then: +$50.00 -- a move its books do not know" in msg, msg
    assert "• markets Kalshi settled that its books do not have: DOGE 10:00 AM -$9.80" in msg, msg
    assert "• not explained by either: <b>$0.00</b>\n" in msg, msg


def test_in_flight_and_unchecked_pots():
    ladder_log([{"t": iso(T0 + 30), "ev": "live_fill", "ticker": "KXNEAR15M-26OCT301030-30", "delta": 10}])
    r = Rig()
    assert r.tick(60, ladder_cash=765.4) == []     # its fill 25 s before the read: in flight, not judged
    assert r.tick(150, ladder_cash=765.4) == []    # 115 s after it: judged (read 1)
    assert M.state_of(r.st).bal[("ladder", "1")]["streak"] == 1
    r.ctx.bs_procs = []                            # nothing trading in the pot: not checked
    assert r.tick(180, ladder_cash=700.0) == [] and r.tick(240, ladder_cash=700.0) == []


def test_the_monitors_own_refresh_waits():
    ladder_log()
    del ASKED[:]
    r = Rig()
    r.tick(0)
    assert ASKED == [] and M.state_of(r.st).bal_next == T0 + M.BAL_REFRESH_S   # the first tick never reads Kalshi
    r.now = T0 + M.BAL_REFRESH_S + 1
    cache(T0 - 4000)                               # an old cache: botstats' own refresh asks (here: refused)
    M.check_balance(r.ctx, M.state_of(r.st), lambda msg, urgent=False: None, r.now)
    assert ASKED and set(ASKED) <= set(kalshi.PATHS), ASKED


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("test_monitor_balance: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
