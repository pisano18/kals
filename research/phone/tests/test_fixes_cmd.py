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


def test_k_cheap_window_block():
    """v-cheapwin: K's block carries its net, the skips without the rule and the window with / without it."""
    old, td = _world()
    try:
        with open(os.path.join(td, "pinrun-live-20261107T101819Z.jsonl"), "w", encoding="utf-8") as fh:
            for r in TF.run_k([]):
                fh.write(json.dumps(r) + "\n")
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_K))
        assert len(s) <= MAX_LEN, len(s)
        blk = s.split("<b>K cheap morning skip</b>")[1]
        assert blk.startswith("\nno first buy under 98.0c in a market closing 6 AM to 10 AM ET"), blk[:200]
        assert "since Nov 7 7:00 AM ET\nengaged 3 times, last Nov 7 9:44 AM ET · 1 open\n🟢 net <b>+$111.50</b>" in blk, blk
        assert ("\nwithout the rule: the 2 settled skips would have lost $111.50 (1 won, 1 flipped, hedges in) · 1 still "
                "open\ncloses 6 AM to 10 AM ET since the rule (1 settled market): pin made +$1.50 with it, -$110.00 "
                "without it\n") in blk, blk
        assert "—" not in s
    finally:
        paths.set_results(old)


def test_l_jump_shadow_block():
    """v-0925v JS: L's block carries its net (+ premium kept, - save missed), what the shadowed jump hedge would have
    paid and saved and so made, and the alarms the cap or the bar would have stopped anyway."""
    old, td = _world()
    try:
        for name, recs in (("pinrun-live-20261107T101819Z.jsonl", TF.run_k([])),
                           ("pinrun-live-20261108T190000Z.jsonl", TF.run_l([]))):
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_L))
        assert len(s) <= MAX_LEN, len(s)
        blk = s.split("<b>L jump hedge shadow</b>")[1]
        assert blk.startswith("\nthe jump hedge is in shadow: it sends nothing; this is what it would have made (6 sd alarm, "
                              "8 sd cap, 5.0c bar as before)\n"), blk[:300]
        assert "since Nov 8 2:00 PM ET\nengaged 4 times, last Nov 8 4:44 PM ET · 1 open\n🔴 net <b>-$54.17</b> (-1.93% of the bank)" in blk, blk
        assert ("\nwould have paid $7.23 in premiums on 2 won markets · would have saved $51.05 on 1 flip (vs the odds hedge pin "
                "really bought) · 1 still open\nso it would have made $54.17 (pin's odds hedge really paid $10.35 on those won "
                "markets); not counted: 1 capped (8 sd or more), 1 under the 5.0c bar\n") in blk, blk
        assert "—" not in s and "not live yet" not in blk.split("\n\n")[0]
        # the page is full here (K's and L's lines), so the events are the first to go; L's own block is what matters
        blk_only = "\n".join(FC.block(next(c for c in F.report(now=TF.NOW_L) if c["id"] == "L"), BANK, 1, None))
        assert blk_only.endswith("\n  Nov 8 4:44 PM ET · SOL · open · a 6.4 sd jump against No with 30 s left: it would have bought "
                                 "30 Yes at 8.0c (odds 90% our way); nothing was sent"), blk_only[-300:]
        T = F.totals(F.report(now=TF.NOW_L))
        assert T["engaged"] == 22 and T["open"] == 4, "L is in the total: %s" % T
        assert s.rstrip().endswith("· engaged 22 times · 4 open"), s[-200:]
    finally:
        paths.set_results(old)


def test_m_third_bet_block():
    """call B (11-08): M's block carries its net (the contracts the 2-bet budget held back on pin's own buys), the
    held-back line and the true-3rd-bet line (not in the net), and the page with all thirteen changes still fits."""
    old, td = _world()
    try:
        for name, recs in (("pinrun-live-20261107T101819Z.jsonl", TF.run_k([])),
                           ("pinrun-live-20261108T190000Z.jsonl", TF.run_l([]))):
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
        TF.write_m(td)
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_M))
        assert len(s) <= MAX_LEN, len(s)
        blk = s.split("<b>M 3rd bet blocked</b>")[1]
        assert blk.startswith("\na close spends 2 bets, never a 3rd (--extra-coin 0 --late-extra 0, brake 4.50, the same bet size; "
                              "the old argv allowed one more on a new coin or inside 15 s); the net is what that held back on pin's "
                              "own buys\n"), blk[:300]
        assert "since Nov 8 4:00 PM ET\nengaged 2 times, last Nov 8 5:59 PM ET\n🟢 net <b>+$96.29</b> (+3.44% of the bank)" in blk, blk
        assert "—" not in s and "not live yet" not in blk.split("\n\n")[0]
        # with K, L and M all live and engaged the page is at its last step (no events, no extra lines: measured 3,379
        # chars against 4,402 with the lines); M's own block carries the two lines and the events
        assert "held back:" not in s and "a true 3rd bet" not in s and "\n  Nov" not in s, s
        M = next(c for c in F.report(now=TF.NOW_M) if c["id"] == "M")
        blk_only = "\n".join(FC.block(M, BANK, 1, None))
        assert ("\nheld back: 2 full buys cut to the 2-bet budget where the old argv had room for a 3rd; the contracts not bought "
                "would have made $1.67 on 1 won, lost $97.96 on 1 flipped\n"
                "a true 3rd bet, NOT in the net (the old build dropped it too, at its base check): 4 closes hit the budget, 4 would "
                "have gone out (1 had no offer, 1 failed a gate, 1 found the slot taken), won $2.79 on 1, lost $96.27 on 1, so "
                "blocking them saved $93.48 · 2 open; the 12-08 read reverts B only above $5/day\n") in blk_only, blk_only
        assert blk_only.endswith("\n  Nov 8 5:59 PM ET · DOGE · +$97.96 · a full Yes buy at 97.8c with 8 s left was held to the 2-bet "
                                 "budget: 50 went out (the book had 500 under 98.0c; the old argv's third bet had room for 100 more, "
                                 "a new coin); the bet LOST, so holding them back saved $97.96"), blk_only[-400:]
        cut = "\n".join(FC.block(M, BANK, 1, 30, 120))
        l1 = FC._cut(M["extra"][0], 120)
        assert len(l1) == 120 and l1.endswith("…") and ("\n%s\n" % l1) in cut and M["extra"][0] not in cut, "the lines cut to 120"
        assert cut.endswith("· DOGE · +$97.96 · " + FC._cut(M["events"][-1]["words"], 30)) and "a full Yes buy at 97.8c with…" in cut, cut[-120:]
        assert "\nheld back" not in "\n".join(FC.block(M, BANK, 0, None, 0)), "extra_cut 0 leaves the lines out"
        T = F.totals(F.report(now=TF.NOW_M))
        assert T["engaged"] == 24 and T["open"] == 4, "M's net is in the total, its third list is not: %s" % T
        assert s.rstrip().endswith("· engaged 24 times · 4 open"), s[-200:]
    finally:
        paths.set_results(old)


def test_before_the_new_build_and_empty_folder():
    old, td = _world()
    try:
        os.remove(os.path.join(td, "pinrun-live-20261105T050000Z.jsonl"))
        F._CACHE.clear()
        s = str(_run())
        assert s.count("not live yet (comes with the new build)") == 8, s   # D..J and K
        assert "<b>L jump hedge shadow</b>\nthe jump hedge is in shadow: it sends nothing; this is what it would have made " \
               "(6 sd alarm, 8 sd cap, 5.0c bar as before)\n" \
               "not live yet (comes with the next pin restart)" in s, s     # L: its own waiting words
        assert "<b>M 3rd bet blocked</b>\na close spends 2 bets, never a 3rd (--extra-coin 0 --late-extra 0, brake 4.50, the " \
               "same bet size; the old argv allowed one more on a new coin or inside 15 s); the net is what that held back on " \
               "pin's own buys\nnot live yet (comes with the first pin start on call B)" in s, s   # M: its own waiting words
        assert "<b>I max positions 5</b>\nup to 5 positions open at once (was 3)\nnot live yet" in s
        assert "engaged 2 times, last Nov 2 11:44 AM ET · 1 open\n🟢 net <b>+$85.15</b>" in s, s
        for p in os.listdir(td):
            os.remove(os.path.join(td, p))
        F._CACHE.clear()
        s = str(_run())                                        # the smoke's real folder may hold no pin log at all
        assert s.count("not engaged yet") == 3 and s.count("not live yet") == 10 and "⚪ <b>All changes: net $0.00</b>" in s, s
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
        # thirteen changes, every one engaged (M, 11-08): even one 30-char event each is over one message (the blocks
        # alone are 3,361 chars), so the page is the blocks whole, no event lines; with twelve one 30-char event each fit
        assert "w" * 29 not in s and "\n  Nov" not in s and s.count("\n\n<b>") == 13, "the thirteen blocks whole, no events"
        d["changes"] = d["changes"][:12]
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and s.count("w" * 29 + "…") == 12 and "w" * 59 not in s, "twelve: one event each, cut to 30"
        for c in d["changes"]:
            c["events"] = c["events"][:1]
            c["events"][0] = dict(c["events"][0], words="x" * 2000)
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and "x" * 2000 not in s and s.count("x" * 29 + "…") == 12, "one cut event each"
        for c in d["changes"]:
            c["what"] = "y" * 300                              # the blocks alone are over the limit: no events at all
        s = str(FC.render(d, _ctx()))
        assert "xxxx" not in s and s.count("y" * 300) == 12, "when even one cut event each does not fit, the blocks alone"
        for c in d["changes"]:
            c["extra"] = ["z" * 200, "z" * 200]                # ...and the extra lines go last: cut to 120, then left out
        s = str(FC.render(d, _ctx()))                          # (the 300-char whats alone are over one message here)
        assert "z" * 200 not in s and "zzzz" not in s and s.count("y" * 300) == 12, "the long lines are left out, never whole"
        for c in d["changes"]:
            c["what"], c["extra"] = "short", []
        d["changes"][0]["extra"] = ["z" * 200, "z" * 200]
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and s.count("z" * 200) == 2 and "x" * 29 in s, "when they fit, the lines and an event are whole"
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
