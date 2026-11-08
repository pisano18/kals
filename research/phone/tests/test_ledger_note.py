"""test_ledger_note.py -- v-ledger-unreadable (2026-11-07) on the phone: Kalshi rows left out of the money are SAID.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_ledger_note.py   (exit 0 = every test passed)
  - every money page (the 'money' and 'one_bot' sections, /status /losses /hedges /fills /brief) gets the line
    '3 markets unreadable (Kalshi field change?)' at the top, through the router; no other page does; a healthy world adds
    nothing (so every older page test is byte-for-byte unchanged), nor does a voided market (its alert tells it once);
  - the monitor sends ONE alert when unreadable markets appear (not again while the count grows), one when they are gone,
    and one when more markets are voided while it runs (a restart learns the voids already there: nothing repeats);
  - the main account's readers leave both out: phone.shared.raw_ledger (/today /days /stats, the charts), pindesk's
    Ledger (the desk, ledger.settled) and pinday (python research/pinday.py), which counts them as set aside.
KALS_TESTING=1; botdata.paths.RESULTS is a temp folder; no network.
"""
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _dlane import T, botstats, fake_ledger, patched, quiet, run       # noqa: E402

import pinday                                                        # noqa: E402
import pindesk                                                       # noqa: E402
import pinledger                                                     # noqa: E402
from botdata import kalshi as _kalshi                               # noqa: E402
from botdata import ledgercheck as LC                               # noqa: E402
from botdata import paths as _paths                                 # noqa: E402
from phone import app as A                                          # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import monitor as MON                                    # noqa: E402
from phone import router as R                                       # noqa: E402
from phone import shared as S                                       # noqa: E402
from phone.html import Html, html_to_plain                          # noqa: E402
from phone.render import unbooked as UB                             # noqa: E402


def row(tk, st, res="no", nn=50.0, nc=49.0, fee=0.10, value=0):
    return {"ticker": tk, "settled_time": st, "market_result": res, "value": value, "yes_count_fp": "0.00",
            "yes_total_cost_dollars": "0.000000", "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc,
            "fee_cost": "%.6f" % fee, "revenue": 0}


GOOD = row("KXBTC15M-26OCT310745-45", "2026-10-31T11:45:05Z")
BAD = {k: v for k, v in row("KXETH15M-26OCT310730-30", "2026-10-31T11:30:05Z").items() if k != "no_count_fp"}
BAD2 = {k: v for k, v in row("KXSOL15M-26OCT310715-15", "2026-10-31T11:15:05Z").items() if k != "fee_cost"}
VOID = row("KXXRP15M-26OCT310700-00", "2026-10-31T11:00:05Z", res="void")


def _plant(td, rows_main, rows_sub=()):
    """botstats' cache (main account + subaccount 1) and kalshi_ledger.json in `td`."""
    c = {"v": 1, "subs": {"0": {"rows": {pinledger.key_of(r): r for r in rows_main}, "complete": True},
                          "1": {"rows": {pinledger.key_of(r): r for r in rows_sub}, "complete": True}}}
    with open(os.path.join(td, _kalshi.CACHE_NAME), "w", encoding="utf-8") as fh:
        json.dump(c, fh)
    pinledger.save_cache({pinledger.key_of(r): r for r in rows_main}, os.path.join(td, LC.LEDGER_NAME))
    LC.forget()


class _Results:
    def __enter__(self):
        self.td = tempfile.mkdtemp(prefix="test_ledger_note_")
        self.old = _paths.set_results(self.td)
        LC.forget()
        return self.td

    def __exit__(self, *a):
        _paths.set_results(self.old)
        LC.forget()


def _phone(td):
    led = fake_ledger()
    led.results = td
    return A.Phone({"chat_id": 7, "secret": "s"}, A.FakeTelegram(), ledger=led, now_fn=lambda: T,
                   health_fn=lambda: {}, procs_fn=lambda: [])


def _declare(*pages):
    """Declare test pages [(name, section)] in ONE declaration (a module's second declare replaces its first)."""
    return CM.declare(*[CM.Command(names=(n,), section=sec, handle=lambda ctx: Html("PAGE")) for n, sec in pages])


def _undeclare(*names):
    for n in names:
        c = CM._BY_NAME.pop(n, None)
        if c is not None:
            CM._BY_MODULE[c.module] = [x for x in CM._BY_MODULE.get(c.module, []) if x is not c]


def test_every_money_page_gets_the_line_and_no_other():
    R.discover()
    with _Results() as td, patched((botstats, "active_bots", lambda procs=None, now=None: ["pin"])), quiet():
        _plant(td, [GOOD, BAD, VOID], [BAD2])
        _declare(("/zzmoney", "money"), ("/zzbot", "one_bot"), ("/zznow", "now"))
        try:
            ph = _phone(td)
            for name in ("/zzmoney", "/zzbot"):
                r = ph.handle(7, name)
                assert isinstance(r, Html) and r.startswith("⚠️ <b>2 markets unreadable (Kalshi field change?)</b>"), r
                assert "ETH 7:30 AM: no no_count_fp" in r and "SOL 7:15 AM: no fee_cost" in r, r
                assert "left out of every total here, not counted as a loss or a win" in r, r
                assert "voided" not in r and r.endswith("\n\nPAGE"), "a void is told once, by its alert, not on every page"
            assert ph.handle(7, "/zznow") == "PAGE", "a page that shows no money gets no line"
            for c in R.commands():
                if c.section in R.MONEY_SECTIONS or c.name in R.MONEY_PAGES:
                    assert R.is_money_page(c), c.name
            for n in ("/status", "/losses", "/hedges", "/fills", "/brief", "/today", "/days", "/bots", "/funds", "/pin",
                      "/week", "/stats"):
                assert R.is_money_page(CM.by_name(n)), n
            for n in ("/help", "/pause", "/server", "/market", "/open"):
                assert not R.is_money_page(CM.by_name(n)), n
            plain = R.money_note(ph.ctx("/zzmoney"), CM.by_name("/zzmoney"), "plain words")
            assert plain.startswith("⚠️ 2 markets unreadable") and plain.endswith("\nplain words"), plain
            assert R.money_note(ph.ctx("/zzmoney"), CM.by_name("/zzmoney"), None) is None
            _plant(td, [GOOD], [])
            assert ph.handle(7, "/zzmoney") == "PAGE", "NULL: every row reads -> the page is exactly as before"
            _plant(td, [GOOD, VOID], [])
            assert ph.handle(7, "/zzmoney") == "PAGE", "a voided market alone adds no line (its alert told it once)"
        finally:
            _undeclare("/zzmoney", "/zzbot", "/zznow")


def test_a_failing_check_costs_the_page_nothing():
    with _Results() as td, quiet():
        saved = LC.scan
        LC.scan = lambda results=None: (_ for _ in ()).throw(RuntimeError("planted"))
        try:
            ph = _phone(td)
            _declare(("/zzmoney2", "money"))
            assert ph.handle(7, "/zzmoney2") == "PAGE"
        finally:
            LC.scan = saved
            _undeclare("/zzmoney2")


def test_one_alert_up_one_alert_down_one_for_a_void():
    st = types.SimpleNamespace(muted=False, monitor_on=True)
    m = MON.state_of(st)
    sent = []

    def send(msg, urgent=False):
        sent.append((str(msg), urgent))
    scans = {"s": LC.empty()}
    saved = LC.scan
    LC.scan = lambda results=None: dict(scans["s"])
    ctx = types.SimpleNamespace(results="x")
    try:
        now = T
        MON.check_ledger(ctx, m, send, now)
        assert sent == [], "NULL: nothing unreadable, nothing said"
        scans["s"] = dict(LC.empty(), unreadable=2, by_pot={"0": 1, "1": 1},
                          examples=[("KXETH15M-26OCT310730-30", "no no_count_fp"), ("KXSOL15M-26OCT310715-15", "no fee_cost")])
        MON.check_ledger(ctx, m, send, now + 10)
        assert sent == [], "read at most every LEDGER_EVERY_S"
        now += MON.LEDGER_EVERY_S
        MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 1 and sent[0][1] is True, sent
        w = html_to_plain(sent[0][0])
        assert w.startswith("⚠️ 2 markets unreadable (Kalshi field change?)") and "LEFT OUT of every money total" in w, w
        assert "ETH 7:30 AM: no no_count_fp" in w and "main account 1, subaccount 1 1" in w and "watch the next fills" in w
        scans["s"] = dict(scans["s"], unreadable=5)
        now += MON.LEDGER_EVERY_S
        MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 1, "it does not repeat while the count grows (the pages show the count now)"
        scans["s"] = LC.empty()
        now += MON.LEDGER_EVERY_S
        MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 2 and sent[1][1] is True and "Every Kalshi settlement reads again" in sent[1][0], sent
        assert "(2 markets were)" in sent[1][0], "it names the count it told"
        scans["s"] = dict(LC.empty(), void=1, void_examples=["KXXRP15M-26OCT310700-00"])
        now += MON.LEDGER_EVERY_S
        MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 3 and sent[2][1] is False and "1 market voided by Kalshi" in sent[2][0], sent
        assert "XRP 7:00 AM" in sent[2][0] and "never booked as a loss" in sent[2][0]
        now += MON.LEDGER_EVERY_S
        MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 3, "the same void is told once"
        scans["s"] = dict(LC.empty(), error="boom")
        now += MON.LEDGER_EVERY_S
        with quiet():
            MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 3, "a failed scan says nothing (logged)"
        assert ("ledger", MON.check_ledger) in MON.CHECKS
        # two more voids later: told once, as news ('2 markets more (3 in all)')
        scans["s"] = dict(LC.empty(), void=3, void_examples=["KXXRP15M-26OCT310700-00"])
        now += MON.LEDGER_EVERY_S
        MON.check_ledger(ctx, m, send, now)
        assert len(sent) == 4 and "2 markets more (3 in all) voided by Kalshi" in sent[3][0], sent[3:]
        # A PHONE RESTART (a new monitor state) with the same 3 voids on file: nothing repeats (the safety review: every
        # restart used to send the void alert again); a NEW void after it is told
        m2 = MON.state_of(types.SimpleNamespace(muted=False, monitor_on=True))
        sent2 = []
        MON.check_ledger(ctx, m2, lambda msg, urgent=False: sent2.append((str(msg), urgent)), T)
        assert sent2 == [], "the voids already there are learnt at the first scan, not told again"
        scans["s"] = dict(scans["s"], void=4)
        MON.check_ledger(ctx, m2, lambda msg, urgent=False: sent2.append((str(msg), urgent)), T + MON.LEDGER_EVERY_S)
        assert len(sent2) == 1 and "1 market more (4 in all) voided by Kalshi" in sent2[0][0], sent2
        # ... while unreadable markets ARE told again after a restart (urgent: the totals are still missing them)
        scans["s"] = dict(LC.empty(), unreadable=1, by_pot={"0": 1}, examples=[(None, "no fee_cost")])
        m3 = MON.state_of(types.SimpleNamespace(muted=False, monitor_on=True))
        sent3 = []
        MON.check_ledger(ctx, m3, lambda msg, urgent=False: sent3.append((str(msg), urgent)), T)
        assert len(sent3) == 1 and sent3[0][1] is True and "1 market unreadable" in sent3[0][0], sent3
    finally:
        LC.scan = saved


def test_the_main_accounts_readers_leave_them_out():
    with _Results() as td, quiet():
        path = os.path.join(td, LC.LEDGER_NAME)
        pinledger.save_cache({pinledger.key_of(r): r for r in (GOOD, BAD, BAD2, VOID)}, path)
        rows = S.raw_ledger(path)
        assert [r["ticker"] for r in rows] == [GOOD["ticker"]], "phone.shared.raw_ledger: booked rows only"
        ms = S.markets_from(rows)
        assert list(ms) == [GOOD["ticker"]] and abs(ms[GOOD["ticker"]]["pnl"] - 0.90) < 1e-9
        saved = pinledger.LEDGER
        pinledger.LEDGER = path
        try:
            L = pindesk.Ledger(td)
            L._load_kalshi()
        finally:
            pinledger.LEDGER = saved
        assert [x["tk"] for x in L.settled] == [GOOD["ticker"]], [x["tk"] for x in L.settled]
        assert sorted(t for t, _w in L.unbooked["unreadable"]) == sorted([BAD["ticker"], BAD2["ticker"]])
        assert L.unbooked["void"] == [VOID["ticker"]]
        led, skipped = pinday.ledger_markets({pinledger.key_of(r): r for r in (GOOD, BAD, BAD2, VOID)})
        assert list(led) == [GOOD["ticker"]] and skipped == 3, (list(led), skipped)


def test_words():
    assert UB.note_lines(LC.empty()) == [] and UB.note_lines(None) == []
    one = dict(LC.empty(), unreadable=1, examples=[(None, "no fee_cost")])
    lines = UB.note_lines(one)
    assert lines[0].startswith("⚠️ <b>1 market unreadable") and "so it is left out" in lines[0] and lines[-1] == ""
    assert "a row with no ticker: no fee_cost" in lines[0]
    assert "<" not in html_to_plain(UB.alert_text(dict(one, by_pot={"3": 1}), 0)) and "subaccount 3 1" in html_to_plain(
        UB.alert_text(dict(one, by_pot={"3": 1}), 0))


if __name__ == "__main__":
    sys.exit(run(globals(), "test_ledger_note"))
