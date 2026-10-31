"""test_settings_now.py -- v-tg-settings-now and v-tg-twr (2026-10-31): what a running bot changes by itself, and money
moved in or out, reach every page.

The operator deposited $1,000 on 10-30 at 10:50 PM ET; the pin bot resized itself (162 -> 279 contracts, loss abort
-$268 -> -$459) and the phone kept reading its START record ("hourly KXBTCD: 1 contract a market"), while its % of bank
counted the deposit as if it had been there all day ("Why aren't some charts showing the updated pricing on pin ...
Shouldn't it happen automatically? And what if I go to remove some"). The rules this file enforces:

  1. a setting a running bot changes by itself is read from its newest self-change record (Records.resize), through
     botdata.logs.settings_now -- every self-change kind a live script writes is declared in the registry, and no
     reader takes a bot's start record alone (a source scan; a deliberate start-only read says '# start-only: <why>');
  2. a deposit or a withdrawal counts in a % base only from when it landed (botdata.pots.span_base: the window's share
     after it; several days chained day by day), and never moves a money-over-time line (series.trading_only).

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_settings_now.py
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import bots                                                          # noqa: E402
from botdata import logs, pots, series                               # noqa: E402
from botdata.clock import day_start                                  # noqa: E402

SELF_CHANGE = ("autosize", "loss_cap", "rescale", "resize")          # the kinds a bot writes when it resizes itself
WRITE = re.compile(r"""(?:\.write|\brec|\blog)\(\s*["'](%s)["']""" % "|".join(SELF_CHANGE))


def _script_path(name):
    for root, _dirs, files in os.walk(RESEARCH):
        if name in files and "tests" not in root and "golden" not in root:
            return os.path.join(root, name)
    return None


def test_every_self_change_kind_is_declared():
    bad, seen = [], []
    for b in bots.all_bots(retired=False):
        p = _script_path(b.script)
        if not p:
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            kinds = set(WRITE.findall(fh.read()))
        seen.append((b.name, sorted(kinds)))
        missing = kinds - set(b.records.resize)
        if missing:
            bad.append("%s writes %s but its Records.resize is %r" % (b.name, sorted(missing), b.records.resize))
    assert not bad, "; ".join(bad)
    assert dict(seen).get("ladder") == ["rescale"] and dict(seen).get("fx") == ["resize"], seen
    assert set(bots.get("pin").records.resize) == {"autosize", "loss_cap"}


def test_no_reader_takes_the_start_record_alone():
    """A last_record(..., (... "start" ...)) read in bots/ or botdata/ must also ask for its bot's self-change kinds,
    go through settings_now on the same line, or say '# start-only: <why>' (the run's start time, its book's origin)."""
    bad = []
    for folder in ("bots", "botdata"):
        for fn in sorted(os.listdir(os.path.join(RESEARCH, folder))):
            if not fn.endswith(".py") or fn == "logs.py":
                continue
            b = bots.get(fn[:-3]) if folder == "bots" else None
            need = set(b.records.resize) if b is not None else set()
            with open(os.path.join(RESEARCH, folder, fn), encoding="utf-8") as fh:
                lines = fh.read().split("\n")
            for i, ln in enumerate(lines):
                m = re.search(r"last_record\([^,]+,\s*\(([^)]*)\)", ln)
                if not m or '"start"' not in m.group(1):
                    continue
                kinds = set(re.findall(r'"(\w+)"', m.group(1)))
                ok = ("settings_now(" in ln or "# start-only:" in ln or "# start-only:" in lines[i - 1]
                      or (folder == "bots" and need and need <= kinds) or (folder == "bots" and not need))
                if not ok:
                    bad.append("%s/%s:%d: %s" % (folder, fn, i + 1, ln.strip()))
    assert not bad, "a start-record read that misses the bot's own resizes:\n  " + "\n  ".join(bad)


def _log(recs):
    d = tempfile.mkdtemp(prefix="settings_now_")
    p = os.path.join(d, "x.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return d, p


def test_pin_reads_its_newest_sizing():
    start = {"t": "2026-10-30T21:32:41Z", "kind": "start", "size": 20.0, "loss_abort": -60.0, "series_size": 1,
             "ladder_series": ["KXBTCD"]}
    recs = [start,
            {"old": 20.0, "new": 158.0, "why": "bank $1396.33", "loss_abort": -261.11, "max_run_stake": 958.0,
             "series_size": 18.0, "loss_cap": 261.11, "t": "2026-10-30T21:32:42Z", "kind": "autosize"},
            {"old": 261.11, "new": 268.47, "bank": 1435.66, "loss_abort": -268.47, "size": 162.0,
             "t": "2026-10-31T01:48:35Z", "kind": "loss_cap"},
            {"old": 162.0, "new": 279.0, "why": "bank $2461.45", "loss_abort": -459.29, "max_run_stake": 1684.0,
             "series_size": 33.0, "loss_cap": 459.29, "t": "2026-10-31T03:32:36Z", "kind": "autosize"}]
    d, p = _log(recs)
    try:
        pin = bots.get("pin")
        now = logs.settings_now(p, start, pin.records.resize, pin.records.resize_as_start)
        assert now["size"] == 279.0 and now["loss_abort"] == -459.29 and now["series_size"] == 33.0, now
        assert now["bank_at_sizing"] == 2461.45 and now["changed_kind"] == "autosize" and now["t"] == start["t"], now
        s, text = pin.settings(bots.spec.SettingsIn(now, None))
        assert "bet 279 contracts" in text and "33 contracts a market" in text and "halts after a $459.29 run loss" \
            in text, text
        before = logs.settings_now(p, start, (), None)
        assert before is start, "no kinds: the start record as it is"
        older = dict(start, t="2026-10-31T05:00:00Z")          # a restart after every change: nothing laid over it
        assert logs.settings_now(p, older, pin.records.resize, pin.records.resize_as_start) == older
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _ctx(now_v, days, led, today, t_read):
    return {"today": today, "led": led, "as_of": None, "stale_why": None, "t_read": t_read,
            "subs": {"0": {"now": now_v, "why": None, "complete": True, "days": days}}}


def test_a_deposit_counts_from_when_it_landed():
    """The operator's 10-30: ~$1,340 all day, +$120.96 made, $1,000 in at 10:50 PM ET, read at 11:59 PM ET."""
    today = "2026-10-30"
    t0 = day_start(today)
    dep_t = t0 + 22 * 3600 + 50 * 60
    read = t0 + 23 * 3600 + 59 * 60
    led = {"fetched": 1.0, "deposits": [{"amount_cents": 100000, "fee_cents": 0, "status": "applied",
                                          "finalized_ts": dep_t}], "withdrawals": [], "transfers": []}
    ctx = _ctx(1340.0 + 120.96 + 1000.0, {today: 120.96}, led, today, read)
    pot = pots.day_pot(ctx, "0", today)
    share = (read - dep_t) / float(read - t0)
    assert abs(pot - (1340.0 + 1000.0 * share)) < 0.01, pot
    pct = 100 * 120.96 / pot
    assert 8.5 < pct < 9.0, "the day reads about +8.6%% of its bank (was +5.2%% with the whole $1,000 in): %.2f" % pct
    # the 7-day window: the deposit on its last evening barely moves the base
    old = pots.flows(led, "0", t0, None)
    assert old == 1000.0 and pots.flows_weighted(led, "0", t0, read) < 50.0


def test_a_withdrawal_counts_until_it_left():
    today = "2026-11-02"
    t0 = day_start(today)
    out_t = t0 + 12 * 3600                                    # $500 out at noon ET, read at midnight (the day's end)
    led = {"fetched": 1.0, "deposits": [], "transfers": [],
           "withdrawals": [{"amount_cents": 50000, "fee_cents": 0, "status": "applied", "finalized_ts": out_t}]}
    ctx = _ctx(2000.0 - 500.0 + 40.0, {today: 40.0}, led, today, t0 + 24 * 3600)
    ctx["today"] = "2026-11-03"
    pot = pots.day_pot(ctx, "0", today)
    assert abs(pot - (2000.0 - 500.0 * 0.5)) < 0.01, "the $2,000 it began with, less the $500 for the half day after " \
        "it left: %s (before v-tg-twr: $2,000, a withdrawal counted nothing)" % pot


def test_an_empty_pot_starts_when_its_money_lands():
    today = "2026-10-30"
    t0 = day_start(today)
    led = {"fetched": 1.0, "deposits": [], "withdrawals": [],
           "transfers": [{"amount_cents": 5000, "created_ts": t0 + 5000, "from_subaccount": 0, "to_subaccount": 3,
                          "exchange_index": 2}]}
    ctx = {"today": today, "led": led, "as_of": None, "stale_why": None, "t_read": t0 + 30000,
           "subs": {"3": {"now": 46.5, "why": None, "complete": True, "days": {today: -3.5}}}}
    assert abs(pots.day_pot(ctx, "3", today) - 50.0) < 1e-6, "a new pot: the % of the $50 it began with"


def test_several_days_are_chained():
    blk = {"today": None, "yesterday": None,
           "last_7_days": {"money": 30.0, "markets": 3, "pot_kind": "start", "pot": 1500.0, "pot_pct": 2.0},
           "days_7": [{"day": "2026-10-30", "money": 10.0}, {"day": "2026-10-29", "money": 10.0},
                      {"day": "2026-10-28", "money": 10.0}] + [{"day": "2026-10-2%d" % d, "money": 0.0} for d in (7, 6, 5, 4)],
           "days_30": []}
    led = {"fetched": 1.0, "deposits": [{"amount_cents": 100000, "fee_cents": 0, "status": "applied",
                                          "finalized_ts": day_start("2026-10-30") + 60}], "withdrawals": [],
           "transfers": []}
    ctx = _ctx(1000.0 + 30.0 + 1000.0, {"2026-10-30": 10.0, "2026-10-29": 10.0, "2026-10-28": 10.0}, led,
               "2026-10-30", day_start("2026-10-31") - 1)
    pots.attach_pots(blk, ctx, "0")
    w = blk["last_7_days"]
    # $1,000 made $10 on each of two days (+1.0%, +0.99%), then $2,020 made $10 (+0.5%): chained about +2.5%
    assert w.get("pot_rule") == "days chained" and 2.4 < w["pot_pct"] < 2.6, w


def test_a_money_line_never_jumps():
    grid = [1000.0 * k for k in range(10)]
    trades = [(1500.0, 5.0), (4500.0, -2.0), (8500.0, 3.0)]
    pts = series.trading_only(grid, trades, 2461.68)             # a $1,000 deposit at t=6000 is not a trade
    assert pts[-1][1] == 2461.68 and [round(b - a, 2) for (_t, a), (_u, b) in zip(pts, pts[1:])] == \
        [0.0, 5.0, 0.0, 0.0, -2.0, 0.0, 0.0, 0.0, 3.0], pts


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
    print("test_settings_now: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
