"""test_fixes_cmd.py -- phone/commands/fixes_cmd.py (/fixes, /changes; v-fixes 2026-11-04): the page over the synthetic
pin logs of botdata/tests/test_fixes.py, its declaration, the empty results folder (the smoke's real folder may hold no
pin log), the size limit (events trimmed first), the bank fallback, the alias and the wall.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_fixes_cmd.py   (exit 0 = every test passed)
A temp RESULTS folder (botdata.paths.set_results); KALS_TESTING=1; no network, no Kalshi, no real log.
"""
import json
import os
import sys
import tempfile
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
BOTDATA_TESTS = os.path.join(RESEARCH, "botdata", "tests")
if BOTDATA_TESTS not in sys.path:
    sys.path.insert(0, BOTDATA_TESTS)
os.environ["KALS_TESTING"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import test_fixes as TF                                              # noqa: E402  (write_logs, NOW: the synthetic logs)
from botdata import fixes as F                                       # noqa: E402
from botdata import paths                                            # noqa: E402
from phone import command as CM                                      # noqa: E402
from phone.commands import fixes_cmd as FC                           # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402
from phone.html import MAX_LEN, Html                                 # noqa: E402

BANK = 2800.0


def _ctx(text="/fixes", ledger=True, now=TF.NOW):
    kw = {"text": text, "now": now}
    if ledger:
        kw["ledger"] = types.SimpleNamespace(bank_at=lambda e: BANK, results=paths.RESULTS)
    return FakeCtx(**kw)


def _world(logs=True):
    td = tempfile.mkdtemp(prefix="test_fixes_cmd_")
    if logs:
        TF.write_logs(td)
    F._CACHE.clear()
    return paths.set_results(td), td


def _run(text="/fixes", **kw):
    return FC.COMMAND.run(_ctx(text, **kw))


def test_declared():
    import tgcharts
    c = FC.COMMAND
    assert c.names == ("/fixes", "/changes") and c.section == "now" and c.order == 65 and c.chart is None
    assert c.help_line == "/fixes — every live pin change: times engaged, net $ so far"
    assert c.fail is not None and c.load is not None and c.render is not None and c.handle is None
    for n in c.names:
        assert c.kind_of(n) is None and tgcharts.kind_of(n) is None, n
    assert CM.by_name("/changes") is c and CM.by_name("/fixes") is c
    failed = CM.discover()
    assert not failed, failed
    assert not [x for x in CM.commands() if x is not c and ({"/fixes", "/changes"} & set(x.names))]


def test_page_over_the_synthetic_logs():
    old, _td = _world()
    try:
        out = _run()
        s = str(out)
        assert type(out) is Html and len(s) <= MAX_LEN, len(s)
        assert s.startswith("🔧 <b>Pin changes</b>") and "\u2014" not in s, "no em dash on the phone"
        for cid in F.IDS:
            assert "<b>%s %s</b>" % (cid, F.NAMES[cid]) in s, cid
        # A and B: one engagement each, with its line (the page is full, so each change shows its last event, cut)
        assert "since Nov 1 3:37 PM ET\nengaged 1 time, last Nov 2 9:00 AM ET\n🟢 net <b>+$35.61</b> (+1.27% of the bank)" in s, s
        assert "engaged 1 time, last Nov 2 9:29 AM ET\n🟢 net <b>+$5.32</b> (+0.19% of the bank)" in s, s
        assert "Nov 2 9:29 AM ET · NEAR · +$5.32 · it skipped a hedge of 50 Yes" in s, s
        # C: 5 engagements, 2 open; its newest event (TRX, open) is listed, and J's too
        assert "engaged 5 times, last Nov 5 1:44 AM ET · 2 open\n🟢 net <b>+$95.94</b>" in s, s
        cblock = s.split("<b>D ")[0].split("<b>C ")[1]
        assert s.count("Nov 5 1:44 AM ET · TRX · open ·") == 2 and "ZEC" not in cblock and "SOL" not in cblock, s
        for k in "ABCDEFGHIJ":
            blk = s.split("<b>%s " % k)[1].split("\n\n")[0]
            assert blk.count("\n  ") == 1, "every engaged change shows its last event: %s\n%s" % (k, blk)
        # D..J: live since the new build, with their money
        assert "<b>D boost rail</b>\nthe 1.5x boost switches off only on a losing boosted-side leg" in s
        assert "since Nov 5 12:00 AM ET\nengaged 1 time, last Nov 5 12:30 AM ET\n🔴 net <b>-$9.55</b> (-0.34% of the bank)" in s, s
        assert "🔴 net <b>-$0.80</b>" in s and "🔴 net <b>-$21.68</b>" in s and "🔴 net <b>-$0.37</b>" in s
        assert "🟢 net <b>+$4.23</b>" in s and "🟢 net <b>+$29.78</b>" in s and "🟢 net <b>+$17.00</b>" in s
        assert "no jump hedge while the hedge side asks under 5.0c" in s, "the bar read off the new start record"
        T = F.totals(F.report(now=TF.NOW))
        assert T["engaged"] == 15 and T["open"] == 2, "J (2 engaged, 1 open) stays out of the total: %s" % T
        assert "the total leaves J out" in s, s
        assert s.rstrip().endswith("<b>All changes: net %s</b> (%s%.2f%% of the bank) · engaged 15 times · 2 open" % (
            ("+$%.2f" % T["net_usd"]) if T["net_usd"] > 0 else ("-$%.2f" % -T["net_usd"]),
            "+" if T["net_usd"] >= 0 else "-", abs(T["net_usd"]) / BANK * 100)), s[-200:]
        # the alias is the same page
        assert str(_run("/changes")) == s and str(_run("/Fixes@kalsbot")) == s
    finally:
        paths.set_results(old)


def test_before_the_new_build_and_empty_folder():
    old, td = _world()
    try:
        os.remove(os.path.join(td, "pinrun-live-20261105T050000Z.jsonl"))
        F._CACHE.clear()
        s = str(_run())
        assert s.count("not live yet (comes with the new build)") == 7, s
        assert "<b>I max positions 5</b>\nup to 5 positions open at once (was 3)\nnot live yet" in s
        assert "engaged 2 times, last Nov 2 11:44 AM ET · 1 open\n🟢 net <b>+$85.15</b>" in s, s
        for p in os.listdir(td):
            os.remove(os.path.join(td, p))
        F._CACHE.clear()
        s = str(_run())                                        # the smoke's real folder may hold no pin log at all
        assert s.count("not engaged yet") == 3 and s.count("not live yet") == 7 and "⚪ <b>All changes: net $0.00</b>" in s, s
        assert "(+0.00% of the bank)" in s and "engaged 0 times" in s
    finally:
        paths.set_results(old)


def test_size_limit_trims_events_first():
    old, _td = _world()
    try:
        d = FC.load(_ctx())
        for c in d["changes"]:
            c["engaged"], c["since"], c["last_engaged"] = 9, "Nov 5 12:00 AM ET", "Nov 5 1:00 AM ET"
            c["events"] = [{"et": "Nov 5 1:00 AM ET", "coin": "ZEC", "usd": 1.0, "words": "w" * 400, "open": False}] * 9
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and "engaged 9 times" in s and "w" * 400 not in s, (len(s), s[:300])
        assert s.count("w" * 59 + "…") == 10, "one event per change, its words cut to 60"
        for c in d["changes"]:
            c["events"] = c["events"][:1]
            c["events"][0] = dict(c["events"][0], words="x" * 2000)
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and "x" * 2000 not in s and s.count("x" * 59 + "…") == 10, "one cut event each"
        for c in d["changes"]:
            c["what"] = "y" * 300                              # the blocks alone are over the limit: no events at all
        s = str(FC.render(d, _ctx()))
        assert "xxxx" not in s and s.count("y" * 300) == 10, "when even one cut event each does not fit, the blocks alone"
        for c in d["changes"]:
            c["what"], c["events"] = "short", []
        d["changes"][0]["events"] = [{"et": "Nov 5 1:00 AM ET", "coin": "ZEC", "usd": 1.0, "words": "w" * 400, "open": False}]
        s = str(FC.render(d, _ctx()))
        assert "w" * 400 in s, "when it fits, the events are shown whole"
    finally:
        paths.set_results(old)


def test_bank_fallback_and_wall():
    old, td = _world(logs=False)
    try:
        s = str(_run(ledger=False))                            # no ledger planted: no % at all
        assert "of the bank" not in s and "All changes: net $0.00" in s, s
        with open(os.path.join(td, "pinrun-live-size.json"), "w", encoding="utf-8") as fh:
            json.dump({"bank": 1400.0, "size": 160}, fh)
        s = str(_run(ledger=False))
        assert "(+0.00% of the bank)" in s, "the pin bot's own size file is the fallback bank"
        saved = F.report
        F.report = lambda **k: (_ for _ in ()).throw(ValueError("planted"))
        try:
            r = _run()
        finally:
            F.report = saved
        assert r == "Could not build /fixes: planted", r
    finally:
        paths.set_results(old)


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_fixes_cmd"))
