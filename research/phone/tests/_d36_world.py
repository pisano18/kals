"""_d36_world.py -- a small planted main-account world for the lane D3 / D6 command tests (test_race, test_racestats,
test_market, test_brief_cmd, test_bars_cmd, test_features, test_stats). Not a test file itself.

v-tg-rebuild step 9 (2026-10-30). Everything lives in a temp folder: Kalshi's settlement rows (kalshi_ledger.json), the
coin race's log, two paper race arms, the pin bot's size / high-water / day-loss files and a VERSIONS.md. botstats is
never asked anything real: `patched(...)` swaps the botstats functions these pages call (bot, all_bots, active_bots,
fills_since) for planted ones, on the botstats module both the old Phone and the new Ctx import. No network, no real
process table, nothing under results\\ read or written. KALS_TESTING=1 (the write fence).
"""
import calendar
import contextlib
import json
import os
import sys
import tempfile

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pindesk                                                       # noqa: E402
import pinphone as pp                                                # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import context as CX                                     # noqa: E402

T = calendar.timegm((2026, 9, 16, 15, 7, 30))      # Wed 09-16 11:07:30 AM ET
RACE30 = calendar.timegm((2026, 9, 15, 0, 0, 0))
pp.LOG = os.path.join(tempfile.mkdtemp(prefix="test_d36_log_"), "pinphone.log")     # log lines of the failure paths

R1X, R1B = "KXCRYPTOLEAD15M-26SEP160500-XRP", "KXCRYPTOLEAD15M-26SEP160500-BTC"
R2X, R2H = "KXCRYPTOLEAD15M-26SEP160715-XRP", "KXCRYPTOLEAD15M-26SEP160715-HYPE"
R3 = "KXCRYPTOLEAD15M-26SEP150930-ETH"
PIN_B, PIN_C, PIN_D = "KXBTC15M-26SEP151015-15", "KXETH15M-26SEP141030-30", "KXSOL15M-26SEP160900-00"
RAILS = {"max_contracts": 1.0, "max_stake": 20.0, "tau_max": 30, "min_price": 0.9, "max_legs": 5, "confirm": 5,
         "clock_tau": 20, "rolling": True, "stop_on_loss": True, "paper": False}
PROCS = [
    (2554960, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --live --size 20 --hedge-belief 0.40 '
              r'--loss-cap 200 --bank-brake 4.00'),
    (11, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --size 20 --pin 0.985 --arm-name arm-pin0.985'),
    (13, r'C:\Python314\python.exe -u research/pinracearm.py --minutes 4320 --log '
         r'C:/kals-repo/results/pinracearm-racectl.jsonl --model fair'),
    (15, r'C:\Python314\python.exe -u research/pinracearm.py --live --max-contracts 1 --max-stake 20 '
         r'--live-rolling-stake --live-tau-max 30 --minutes 10080 --log C:/kals-repo/results/pinracepenny-live.jsonl'),
]


def _row(tk, res, yes_n=0, yes_c=0, no_n=0, no_c=0, fee=0.0, value=None, st="2026-09-16T14:00:20Z"):
    r = {"ticker": tk, "market_result": res, "yes_count_fp": "%.2f" % yes_n, "yes_total_cost_dollars": "%.6f" % yes_c,
         "no_count_fp": "%.2f" % no_n, "no_total_cost_dollars": "%.6f" % no_c, "fee_cost": "%.6f" % fee,
         "revenue": 0, "settled_time": st}
    if value is not None:
        r["value"] = value
    return r


def _w(path, recs):
    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def results_dir(races=True, pins=True, race_log=True, arms=True, scored=False, stop=False, pin_files=True):
    """A fresh temp results folder with the planted files; returns its path."""
    td = tempfile.mkdtemp(prefix="test_d36_")
    rows = {}
    if pins:
        rows.update({"b": _row(PIN_B, "yes", no_n=40, no_c=38.80, st="2026-09-15T14:15:20Z"),
                     "c": _row(PIN_C, "yes", yes_n=10, yes_c=5.00, no_n=20, no_c=19.00, fee=0.10,
                               st="2026-09-14T14:30:20Z"),
                     "d": _row(PIN_D, "yes", yes_n=50, yes_c=47.50, fee=0.05, st="2026-09-16T13:00:20Z")})
    if races:
        rows.update({"r1x": _row(R1X, "yes", yes_n=1, yes_c=0.97, fee=0.0021, value=100, st="2026-09-16T09:00:38Z"),
                     "r1b": _row(R1B, "no", no_n=1, no_c=0.98, fee=0.0014, value=0, st="2026-09-16T09:00:38Z"),
                     "r2x": _row(R2X, "scalar", yes_n=1, yes_c=0.97, fee=0.0021, value=50, st="2026-09-16T11:15:38Z"),
                     "r2h": _row(R2H, "scalar", no_n=1, no_c=0.98, fee=0.0014, value=50, st="2026-09-16T11:15:38Z"),
                     "r3": _row(R3, "yes", no_n=1, no_c=0.85, fee=0.006, value=100, st="2026-09-15T13:30:38Z")})
    with open(os.path.join(td, "kalshi_ledger.json"), "w", encoding="utf-8") as fh:
        json.dump({"settlements": rows}, fh)
    with open(os.path.join(td, "VERSIONS.md"), "w", encoding="utf-8") as fh:
        fh.write("# v-pinfix -- 2026-09-16 12:30Z (pid 1, code_sha abc) -- LIVE: a fix\n\nbody\n\n"
                 "# v-older -- 2026-09-15 -- LIVE: no time on this one\n")
    if pin_files:
        for nm, d in (("pinrun-live-size.json", {"size": 79.0, "bank": 930.04, "at": "2026-09-16T14:21:42Z"}),
                      ("pinrun-hwm.json", {"hwm": 1037.33, "at": "2026-09-15T23:48:38Z"}),
                      ("pinrun-dayloss.json", {"day": "2026-09-16", "realised": 11.1424})):
            with open(os.path.join(td, nm), "w", encoding="utf-8") as fh:
                json.dump(d, fh)
    if race_log:
        _w(os.path.join(td, "pinracepenny-live.jsonl"), [
            {"kind": "start", "t": "2026-09-16T08:00:00Z", "live": True, "live_rails": RAILS,
             "argv": ["--live", "--live-max-losses", "2"]},
            {"kind": "live_order", "t": "2026-09-16T08:59:20Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "ticker": R1X, "side": "yes", "filled": 1.0, "exec_price": 0.97, "staked": 0.97},
            {"kind": "live_settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 2, "won": 2, "pnl": 0.0465, "staked_open": 0.0},
            {"kind": "live_order", "t": "2026-09-16T15:07:00Z", "event": "KXCRYPTOLEAD15M-26SEP161115",
             "ticker": "KXCRYPTOLEAD15M-26SEP161115-SOL", "side": "yes", "filled": 1.0, "exec_price": 0.98,
             "staked": 0.98},
            {"kind": "live_order", "t": "2026-09-16T12:00:00Z", "event": "KXCRYPTOLEAD15M-26SEP160815",
             "ticker": "KXCRYPTOLEAD15M-26SEP160815-ETH", "side": "no", "filled": 2.0, "exec_price": 0.95},
            {"kind": "live_halt", "t": "2026-09-16T13:31:15Z", "staked": 2.81, "sends": 4,
             "why": "first real loss: KXCRYPTOLEAD15M-26SEP160930 no at 85c"},
        ])
    if arms:
        _w(os.path.join(td, "pinracearm-z3.jsonl"), [
            {"kind": "start", "t": "2026-09-15T00:00:00Z", "paper_live": True},
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T09:01:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160500", "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T11:16:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160715", "positions": 1, "won": 1, "pnl": 0.0186},
        ])
        _w(os.path.join(td, "pinracearm-racectl.jsonl"), [
            {"kind": "settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 2, "won": 2, "pnl": 5.0},
            {"kind": "settled", "t": "2026-09-15T13:31:15Z", "event": "KXCRYPTOLEAD15M-26SEP150930",
             "positions": 1, "won": 0, "pnl": -212.5},
            {"kind": "end", "t": "2026-09-15T13:40:00Z"},
        ])
        if scored:
            size = os.path.getsize(os.path.join(td, "pinracearm-z3.jsonl"))
            with open(os.path.join(td, "race_arms_scored.json"), "w", encoding="utf-8") as fh:
                json.dump({"made": "2026-09-16T10:00:00Z", "arms": {"z3": {
                    "log_size": size, "own_size": "1 a leg", "same": {"races": 2, "own": 0.03, "at_live": 0.03,
                                                                      "own_log": 0.0372},
                    "run": {"races": 2, "won": 2, "tie": 0, "lost": 0, "own": 0.03, "at_live": 0.03}}}}, fh)
    if stop:
        with open(os.path.join(td, "pinracepenny.stop"), "w", encoding="utf-8") as fh:
            fh.write("stop\n")
    return td


class PlantLedger(pindesk.Ledger):
    """A pindesk.Ledger whose rows are planted (no log is read): refresh() does nothing, bank_at() is a constant."""

    def __init__(self, results, bank=1000.0, **rows):
        super().__init__(results)
        for k, v in rows.items():
            setattr(self, k, v)
        self._bank = bank

    def refresh(self):
        return None

    def bank_at(self, epoch):
        return self._bank


def phone(led, procs=PROCS, **seams):
    ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=led, now_fn=lambda: T,
                  health_fn=lambda: {"alive": True}, procs_fn=(lambda: procs),
                  versions_path=os.path.join(led.results, "VERSIONS.md"), race30_epoch=RACE30)
    for k, v in seams.items():
        setattr(ph, k, v)
    return ph


def _raise(*a, **k):
    raise RuntimeError("planted: botstats is not asked in this test")


@contextlib.contextmanager
def patched(active=("pin", "race"), bot=None, all_bots=None, fills_since=None, mod=None, **attrs):
    """botstats' bot / all_bots / active_bots / fills_since planted (None = raises), plus any other module attributes
    as mod={(module, name): value} -- all put back after. The failure paths' log lines are kept off the console."""
    import io
    import botstats
    saved = []

    def put(m, name, v):
        saved.append((m, name, getattr(m, name)))
        setattr(m, name, v)
    put(botstats, "active_bots", lambda procs=None: tuple(active))
    put(botstats, "bot", bot or _raise)
    put(botstats, "all_bots", all_bots or _raise)
    put(botstats, "fills_since", fills_since or _raise)
    for (m, name), v in (mod or {}).items():
        put(m, name, v)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield botstats
    finally:
        for m, name, v in reversed(saved):
            setattr(m, name, v)


def old_new(ph, text, method):
    """(old reply, new reply) for one message: Phone.<method>() and the new module's Command.run on the same Phone."""
    old = method()
    cmd = CX.split_command(text)[1]
    com = CM.by_name(cmd)
    assert com is not None, "no command declared for %s" % cmd
    new = com.run(CX.Ctx.from_phone(ph, text))
    return old, new


def same(old, new, what=""):
    assert type(old) is type(new) and str(old) == str(new), "%s\n--- old\n%s\n--- new\n%s" % (what, old, new)


def run_tests(glb, name):
    import time
    import traceback
    tests = [(k, v) for k, v in glb.items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for tn, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % tn, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(tn)
            print("  FAIL %s\n%s" % (tn, traceback.format_exc()), flush=True)
    print("%s: %d passed, %d failed (%.1f s)" % (name, passed, len(failed), time.time() - t0))
    return 1 if failed else 0
