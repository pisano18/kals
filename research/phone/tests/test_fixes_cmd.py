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
from botdata.fmt import usd                                          # noqa: E402
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


def _pin_line(s):
    """The page's headline total: PIN's changes only (v-tg-fixes-pin, 11-16), the line under it the ladder's / stops'."""
    got = [ln for ln in str(s).split("\n") if "<b>Pin's changes: net " in ln]
    assert len(got) == 1, str(s)[-400:]
    return got[0]


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
        for cid in F.IDS + F.FIXED_IDS:
            assert "<b>%s %s</b>" % (cid, F.NAMES[cid]) in s, cid
        # A and B: one engagement each. With fourteen changes (N, 11-08) the blocks with one 30-char event each run over
        # one message (3,665 chars + the header and the total), so the full page is the blocks whole and NO event lines;
        # the per-event words are on the watcher's $10+ alerts and in botdata.fixes (test_fixes); a two-message page is
        # the next step
        assert "since Nov 1 3:37 PM ET\nengaged 1 time, last Nov 2 9:00 AM ET\n🟢 net <b>+$35.61</b> (+1.27% of the bank)" in s, s
        assert "engaged 1 time, last Nov 2 9:29 AM ET\n🟢 net <b>+$5.32</b> (+0.19% of the bank)" in s, s
        assert "it skipped a hedge of 50 Yes" not in s and "\n  Nov" not in s, "no event lines once the blocks fill the page"
        # C: 5 engagements, 2 open
        assert "engaged 5 times, last Nov 5 1:44 AM ET · 2 open\n🟢 net <b>+$95.94</b>" in s, s
        # N (shelved, not live): folded into the one short 'not live' line (fixes: change["retired"]), never a block
        assert "\n\nnot live: <b>N hedge line 0.60</b> (shelved 11-09)\n\n" in s and "SHELVED" not in s, s
        for k in "ABCDEFGHIJ":
            blk = s.split("<b>%s " % k)[1].split("\n\n")[0]
            assert blk.count("\n  ") == 0, "the blocks whole, no event lines: %s\n%s" % (k, blk)
        # D..J: live since the new build, with their money (D re-sized order by order: test_fixes' run_d). With the
        # two measured-once rows (LAD, STOP: 11-14) the "what" lines go first; each change's block keeps its own
        assert ("<b>D boost rail</b>\nsince Nov 5 12:00 AM ET\nengaged 3 times, last Nov 5 1:29 AM ET\n🔴 net <b>-$2.40</b> "
                "(-0.09% of the bank)\nre-sized order by order as the old rule would have: 3 markets after 1 trip") in s, s
        assert "🔴 net <b>-$0.80</b>" in s and "🔴 net <b>-$21.68</b>" in s and "🔴 net <b>-$0.37</b>" in s
        assert "🟢 net <b>+$4.23</b>" in s and "🟢 net <b>+$29.78</b>" in s and "🟢 net <b>+$17.00</b>" in s
        rep = F.report(now=TF.NOW)
        Fx = next(c for c in rep if c["id"] == "F")
        assert FC.block(Fx, BANK, 0)[1].startswith("no jump hedge while the hedge side asks under 5.0c"), \
            "the bar read off the new start record"
        # LAD and STOP: measured once by the 11-14 retro, said so on their since line, their assumption line under it
        # (their % never of pin's bank: the ladder's pot -- no ladder log here, so none -- and none for the stops)
        assert ("<b>LAD ladder's 4 changes</b>\nsince Oct 22 11:40 AM ET · measured once, to Nov 14 1:16 PM ET (not "
                "running)\n🟢 net <b>+$123.40</b>\nthe 11-14 replay's central fill model") in s, s
        assert ("<b>STOP the 4 stops</b>\nsince Oct 27 10:02 PM ET · measured once, to Nov 14 1:16 PM ET (not running)\n"
                "🟢 net <b>+$27.90</b>\nrests on the moved money earning ~2.2%/day") in s, s
        T = F.totals(rep)
        assert T["engaged"] == 17 and T["open"] == 2, "J (2 engaged, 1 open) stays out of the total: %s" % T
        assert "leaves J out" in s and "the total is pin's only" in s, s
        g = T["groups"]
        # the headline is PIN's changes only (the operator 11-16: the ladder's and the stops' rows "only affect" them):
        # never LAD's +$123.40 or STOP's +$27.90, its % of pin's bank; they are on their own line under it
        assert T["pin_net_usd"] == g["pin"] == round(T["net_usd"] - 123.40 - 27.90, 2) and T["pin_engaged"] == 17
        x = T["pin_net_usd"]
        assert _pin_line(s) == "%s <b>Pin's changes: net %s</b> (%s%.2f%% of pin's bank) · engaged 17 times · 2 open" % (
            FC._mark(x), usd(x), "+" if x >= 0 else "-", abs(x) / BANK * 100), _pin_line(s)
        assert s.rstrip().endswith("\nLadder's changes (not pin): +$123.40 · stops: +$27.90"), s[-300:]
        assert "All changes" not in s and "+$%.2f" % T["net_usd"] not in s.split("\n")[-2], "no pin+ladder sum anywhere"
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
        # with the measured-once rows (11-14) the "what" lines go first when the page fills; K's own block carries its
        # what, its money is on the page whatever step it lands on (the 11-14 retro's prices: test_fixes)
        K = next(c for c in F.report(now=TF.NOW_K) if c["id"] == "K")
        assert FC.block(K, BANK, 0)[1].startswith("no first buy under 98.0c in a market closing 6 AM to 10 AM ET"), K["what"]
        assert "since Nov 7 7:00 AM ET\nengaged 3 times, last Nov 7 9:44 AM ET · 1 open\n🟢 net <b>+$107.04</b>" in blk, blk
        assert "\nwithout the rule: the 2 settled skips would have lost $107.04 (1 won, 1 flipped, hedges in)" in blk, blk
        whole = "\n".join(FC.block(K, BANK, 0, None, None))
        assert ("\nwithout the rule: the 2 settled skips would have lost $107.04 (1 won, 1 flipped, hedges in) · 1 still "
                "open\ncloses 6 AM to 10 AM ET since the rule (1 settled market): pin made +$1.50 with it, -$105.54 "
                "without it\npriced on pin's own 6-10 ET cheap first buys before the rule") in whole, whole
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
        # the page is full (K's and L's lines, the measured-once rows): the "what" lines are the first to go, then the
        # lines are cut, then each row keeps only its first; L's money and its first line's start are on the page at any step
        assert "since Nov 8 2:00 PM ET\nengaged 4 times, last Nov 8 4:44 PM ET · 1 open\n🔴 net <b>-$54.17</b> (-1.93% of the bank)" in blk, blk
        assert "\nwould have paid $7.23 in premiums on 2 won markets · would have saved $51.05 on 1 flip" in blk, blk
        assert "—" not in s and "not live yet" not in blk.split("\n\n")[0]
        lblk = FC.block(next(c for c in F.report(now=TF.NOW_L) if c["id"] == "L"), BANK, 0)
        assert lblk[1] == ("the jump hedge is in shadow: it sends nothing; this is what it would have made (6 sd alarm, 8 sd cap, "
                           "5.0c bar as before)"), lblk[1]
        assert lblk[-2:] == ["would have paid $7.23 in premiums on 2 won markets · would have saved $51.05 on 1 flip (vs the odds "
                             "hedge pin really bought) · 1 still open",
                             "so it would have made $54.17 (pin's odds hedge really paid $10.35 on those won markets); not counted: "
                             "1 capped (8 sd or more), 1 under the 5.0c bar"], lblk[-2:]
        # the page is full here (K's and L's lines), so the events are the first to go; L's own block is what matters
        blk_only = "\n".join(FC.block(next(c for c in F.report(now=TF.NOW_L) if c["id"] == "L"), BANK, 1, None))
        assert blk_only.endswith("\n  Nov 8 4:44 PM ET · SOL · open · a 6.4 sd jump against No with 30 s left: it would have bought "
                                 "30 Yes at 8.0c (odds 90% our way); nothing was sent"), blk_only[-300:]
        T = F.totals(F.report(now=TF.NOW_L))
        assert T["engaged"] == 24 and T["open"] == 4, "L is in the total: %s" % T
        assert T["pin_engaged"] == 24 and _pin_line(s).endswith("· engaged 24 times · 4 open"), _pin_line(s)
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
        assert "since Nov 8 4:00 PM ET\nengaged 2 times, last Nov 8 5:59 PM ET\n🟢 net <b>+$95.45</b> (+3.41% of the bank)" in blk, blk
        assert "—" not in s and "not live yet" not in blk.split("\n\n")[0]
        # with K, L, M live and the measured-once rows the full page has given up the "what" lines (they go before any
        # money line) and keeps M's first line, its money first; M's own block carries its what, the whole lines, events
        assert "yes" not in blk.split("\n\n")[0].split("\n")[1][:4] and "\nheld back: would have made $2.51 on 1 won" in blk, blk
        M = next(c for c in F.report(now=TF.NOW_M) if c["id"] == "M")
        assert FC.block(M, BANK, 0)[1] == ("a close spends 2 bets, never a 3rd (--extra-coin 0 --late-extra 0, brake 4.50, the same "
                                           "bet size; the old argv allowed one more on a new coin or inside 15 s); the net is what "
                                           "that held back on pin's own buys"), FC.block(M, BANK, 0)[1]
        blk_only = "\n".join(FC.block(M, BANK, 1, None))
        assert ("\nheld back: would have made $2.51 on 1 won, lost $97.96 on 1 flipped (2 buys cut to the 2-bet budget where "
                "the old argv had room for a 3rd; priced on the book past each fill, hedges in)\n"
                "a true 3rd bet, NOT in the net (the old build dropped it too, at its base check): 4 closes hit the budget, 4 would "
                "have gone out (1 had no offer, 1 failed a gate, 1 found the slot taken), won $2.79 on 1, lost $96.27 on 1, so "
                "blocking them saved $93.48 · 2 open; the 12-08 read reverts B only above $5/day\n") in blk_only, blk_only
        assert blk_only.endswith("\n  Nov 8 5:59 PM ET · DOGE · +$97.96 · a Yes buy at 97.8c with 8 s left was held to the 2-bet "
                                 "budget: 50 went out; with the old 3rd bet the late boost would have bought 100 more (at 97.8c, "
                                 "the book past what filled, under the 98.0c limit, inside the late window); the bet LOST, so "
                                 "holding them back saved $97.96"), blk_only[-400:]
        cut = "\n".join(FC.block(M, BANK, 1, 30, 120))
        l1 = FC._cut(M["extra"][0], 120)
        assert len(l1) <= 120 and l1.endswith("…") and ("\n%s\n" % l1) in cut and M["extra"][0] not in cut, "the lines cut to 120"
        assert cut.endswith("· DOGE · +$97.96 · " + FC._cut(M["events"][-1]["words"], 30)) and "a Yes buy at 97.8c with 8 s" in cut, cut[-120:]
        assert "\nheld back" not in "\n".join(FC.block(M, BANK, 0, None, 0)), "extra_cut 0 leaves the lines out"
        first = FC.block(M, BANK, 0, None, (1, 90))
        assert first[-1].startswith("held back: would have made $2.51 on 1 won, lost $97.96") and "a true 3rd bet" not in "\n".join(first), \
            "(k, n): the first line only, its money first: %s" % first
        T = F.totals(F.report(now=TF.NOW_M))
        assert T["engaged"] == 26 and T["open"] == 4, "M's net is in the total, its third list is not: %s" % T
        assert T["pin_engaged"] == 26 and _pin_line(s).endswith("· engaged 26 times · 4 open"), _pin_line(s)
    finally:
        paths.set_results(old)


def test_o_withdrawn_never_a_problem():
    """v-ladder-rail100 WITHDRAWN 11-14 (fixes.O_WITHDRAWN, the shipped value): the same untracked 100% log that makes O
    a problem below puts no ⚠️ anywhere: O's block says withdrawn (and that the latest start runs 1.0 all the same), the
    total leaves it out; on the 0.82 log its block is the withdrawn words alone."""
    old, td = _world()
    try:
        with open(os.path.join(td, "ladder-live-orders.jsonl"), "w", encoding="utf-8") as fh:
            for r in TF.run_o([], with_rail100=False) + [TF._old_code_start("2026-11-15T09:50:00.000Z")]:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_O))
        assert len(s) <= MAX_LEN and "⚠️" not in s and "PROBLEM" not in s, s[:600]
        # folded with N into the one 'not live' line; the 1.0 start said there too, never the '82%' that is not true
        assert ("\n\nnot live: <b>N hedge line 0.60</b> (shelved 11-09) · <b>O ladder cash limit 100%</b> (withdrawn "
                "11-14; but the ladder's latest start (Nov 15 4:50 AM ET) runs --commit-frac 1.0: nothing of it is "
                "counted here)\n\n") in s, s
        rep = F.report(now=TF.NOW_O)
        O = next(c for c in rep if c["id"] == "O")
        blk = "\n".join(FC.block(O, BANK, 0))                  # its own block (not on the page) keeps the whole words
        assert blk.endswith("\nwithdrawn 11-14: it could not be tracked against never changing it, so the ladder stays at "
                            "82%; but the ladder's latest start (Nov 15 4:50 AM ET) runs --commit-frac 1.0: nothing of it "
                            "is counted here"), blk
        assert O["withdrawn"] and FC.problems_line(rep) is None and F.totals(rep)["problems"] == []
        for step in FC.PLAN:                                   # no problem line at any shrink step, even if one were set
            b = FC.block(dict(O, problem=F.O_UNTRACKED), BANK, *step)
            assert not any("⚠️" in x for x in b), (step, b)
        assert FC.problems_line([dict(O, problem=F.O_UNTRACKED)]) is None
        with open(os.path.join(td, "ladder-live-orders.jsonl"), "w", encoding="utf-8") as fh:
            for r in TF.run_o([], with_rail100=False):
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        F._CACHE.clear()
        s2 = str(_run(now=TF.NOW_O))
        assert "⚠️" not in s2 and ("\n\nnot live: <b>N hedge line 0.60</b> (shelved 11-09) · <b>O ladder cash limit "
                                   "100%</b> (withdrawn 11-14, stays at 82%)\n\n") in s2, s2
    finally:
        paths.set_results(old)


def test_o_untracked_problem_on_top_and_in_its_block():
    """v-ladder-rail100 tracking (11-14): the ladder on its 100% rail under the OLDER code (start record: commit_frac 1.0,
    no argv / old_limit; it never marks a bid) -- O says ON THE 100% RAIL BUT NOT TRACKED in its block (before 'not
    engaged yet', so it is never hidden) and the page counts it on a top line; at every shrink step both stay. A tracked
    ladder (the marking code's start record) has no problem line anywhere. (O's machinery, as if O had not been
    withdrawn: TF.o_live.)"""
    with TF.o_live():
        _o_untracked_problem()


def _o_untracked_problem():
    old, td = _world()
    try:
        with open(os.path.join(td, "ladder-live-orders.jsonl"), "w", encoding="utf-8") as fh:
            for r in TF.run_o([], with_rail100=False) + [TF._old_code_start("2026-11-15T09:50:00.000Z")]:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_O))
        assert len(s) <= MAX_LEN, len(s)
        top = ("⚠️ <b>1 PROBLEM</b>: O ladder cash limit 100%: ON THE 100% RAIL BUT NOT TRACKED (the ladder code that marks "
               "the bids is not running)")
        assert s.split("\n")[2] == top, s[:600]
        blk = s.split("<b>O ladder cash limit 100%</b>")[1].split("\n\n")[0]
        assert ("\n⚠️ <b>ON THE 100% RAIL BUT NOT TRACKED (the ladder code that marks the bids is not running)</b>\n"
                "since Nov 15 4:50 AM ET\nnot engaged yet") in blk, blk
        T = F.totals(F.report(now=TF.NOW_O))
        last = s.rstrip().split("\n")[-1]
        # pin's headline leaves the ladder's rows out; the ladder's line has its % of the ladder's pot (its start's 1,338.63)
        assert T["problems"] == ["O"] and ("engaged %d times" % T["pin_engaged"]) in _pin_line(s), _pin_line(s)
        lx = T["ladder_net_usd"]
        assert T["ladder_pot"] == 1338.6325 and last == "Ladder's changes (not pin): %s (%s%.2f%% of the ladder's pot) · " \
            "stops: +$27.90" % (usd(lx), "+" if lx >= 0 else "-", abs(lx) / 1338.6325 * 100), last
        O = next(c for c in F.report(now=TF.NOW_O) if c["id"] == "O")
        warn = FC.PROBLEM % F.O_UNTRACKED
        for step in FC.PLAN:                                   # never cut, whatever step the page lands on
            b = FC.block(O, BANK, *step)
            assert warn in b and b.index(warn) < b.index("not engaged yet"), (step, b)
        # the marking code starts: no problem line anywhere
        with open(os.path.join(td, "ladder-live-orders.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(TF._lad_start("2026-11-15T10:20:00.000Z", TF.O_ARGV100, 1.0), separators=(",", ":")) + "\n")
        F._CACHE.clear()
        s2 = str(_run(now=TF.NOW_O))
        assert "⚠️" not in s2 and "PROBLEM" not in s2 and F.totals(F.report(now=TF.NOW_O))["problems"] == [], s2[:600]
        assert FC.problems_line(F.report(now=TF.NOW_O)) is None
    finally:
        paths.set_results(old)


def test_p_band99_late_block():
    """v-0925x band99late (11-14): P's block carries its net (pin's blocked legs' real money less what the skipped early
    band legs would have made), the given up / gained / net line and the gross line; 'none yet' before any shadow."""
    old, td = _world()
    try:
        TF.write_p(td)
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_P))
        assert len(s) <= MAX_LEN, len(s)
        blk = s.split("<b>P band99 late-only</b>")[1].split("\n\n")[0]
        assert "since Nov 14 1:11 PM ET\nengaged 6 times, last Nov 14 2:14 PM ET · 1 open\n🔴 net <b>-$8.05</b> (-0.29% of the bank)" in blk, blk
        assert "\nnet -$8.05: the early band bets skipped would have lost $10.23 (4 won, 1 lost); pin's own bets they wou" in blk, blk
        assert "—" not in s and "not live yet" not in blk
        P = next(c for c in F.report(now=TF.NOW_P) if c["id"] == "P")
        whole = FC.block(P, BANK, 1, None)
        assert whole[1].startswith("the band99 leg (a tenth of the bet at up to 99c) only with 30 s or less left"), whole[1]
        assert whole[5:7] == ["net -$8.05: the early band bets skipped would have lost $10.23 (4 won, 1 lost); pin's own "
                              "bets they would have blocked lost $18.28 · 1 open",
                              "gross, before hedges (the market's own, pro rata, where pin held the side; else 41% of a "
                              "band loss): they would have lost $27.72; blocked: 2 early legs (top-ups: 1 not at the full bet: not counted), 1 3rd fill, 1 later "
                              "band leg"], whole
        assert whole[-1] == ("  Nov 14 2:14 PM ET · SOL · open · an early band bet skipped: 30 No at 98.5c with 40 s left "
                             "(it would have been the market's early leg); it would have blocked none of pin's own bets; not "
                             "settled yet"), whole[-1]
        T = F.totals(F.report(now=TF.NOW_P))
        assert _pin_line(s).endswith("· engaged %d times · %d open" % (T["pin_engaged"], T["pin_open"])), _pin_line(s)
        # live with no shadow yet: 'none yet'
        with open(os.path.join(td, "pinrun-live-20261114T181141Z.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(TF.run_p([])[0]) + "\n")
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_P))
        blk = s.split("<b>P band99 late-only</b>")[1].split("\n\n")[0]
        assert blk.endswith("since Nov 14 1:11 PM ET\nnot engaged yet"), blk
    finally:
        paths.set_results(old)


def test_r_5hz_hedge_block_and_its_stop_rule():
    """v-hedge5live (11-16): R's block carries its net against the 1 Hz line and its lines (the split, the stop rule);
    under -$25 while pin still runs --index-5hz hedge the stop rule is a ⚠️ problem, on top of the page and in R's
    block, at every shrink step; back to shadow, no problem anywhere."""
    old, td = _world()
    try:
        eth11, traj11 = TF._r_eth11()
        TF.write_r5(td, eth11, traj11)
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_R))
        assert len(s) <= MAX_LEN and "—" not in s, len(s)
        warn = ("net -$47.23 since 11-16, under the operator's -$25 stop: back to shadow (results\\pin_hedge5live.ps1 "
                "-Revert + restart while flat)")
        assert s.split("\n")[2] == "⚠️ <b>1 PROBLEM</b>: R 5 Hz hedge: " + warn, s[:700]
        blk = s.split("<b>R 5 Hz hedge</b>")[1].split("\n\n")[0]
        assert ("\n⚠️ <b>%s</b>\nsince Nov 16 8:08 AM ET\nengaged 5 times, last Nov 16 2:44 PM ET · 1 open\n🔴 net "
                "<b>-$47.23</b> (-1.69%% of the bank)" % warn) in blk, blk
        R = next(c for c in F.report(now=TF.NOW_R) if c["id"] == "R")
        whole = FC.block(R, BANK, 1, None, None)
        assert whole[1] == ("the hedge fires on the 5 Hz index when it crosses first (live 11-16 8:08 AM ET); each such "
                            "hedge priced against what the 1 Hz line would have done"), whole[1]
        assert whole[-3:-1] == ["the 1 Hz line followed on 2 markets: +$14.93 (1 flip, 1 won bet) · 2 false alarms the "
                                "1 Hz line never confirmed: -$62.16 · 1 open", F.R_STOP], whole[-3:]
        assert whole[-1].startswith("  Nov 16 2:44 PM ET · DOGE · open · a 5 Hz hedge 0.20 s before the 1 Hz print"), whole[-1]
        for step in FC.PLAN:                                   # the stop rule's line is never cut
            assert (FC.PROBLEM % warn) in FC.block(R, BANK, *step), step
        T = F.totals(F.report(now=TF.NOW_R))
        assert T["problems"] == ["R"] and ("· engaged %d times · %d open" % (T["pin_engaged"], T["pin_open"])) in \
            _pin_line(s), s[-300:]
        # back to shadow: the net stops, no problem anywhere
        with open(os.path.join(td, "pinrun-live-20261116T170000Z.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(TF._r("start", "2026-11-16T17:00:00Z", index_5hz="shadow", **TF.R_START)) + "\n")
        F._CACHE.clear()
        s2 = str(_run(now=TF.NOW_R))
        assert "⚠️" not in s2 and "PROBLEM" not in s2 and F.totals(F.report(now=TF.NOW_R))["problems"] == [], s2[:600]
        assert "\n🔴 net <b>-$47.23</b>" in s2.split("<b>R 5 Hz hedge</b>")[1].split("\n\n")[0], s2
    finally:
        paths.set_results(old)


def test_q_midnight_reset_and_the_full_page():
    """v-ladder-dayreset (11-14): Q's block carries the money the ladder made after its midnight reset (the old code stayed
    halted); with the ladder log the page is A..N, O (withdrawn), P, Q -- every change -- and still one message, P's and
    Q's money lines on it."""
    old, td = _world()
    try:
        TF.write_p(td)
        with open(os.path.join(td, "ladder-live-orders.jsonl"), "w", encoding="utf-8") as fh:
            for r in TF.run_q([]):
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        F._CACHE.clear()
        s = str(_run(now=TF.NOW_Q))
        assert len(s) <= MAX_LEN, len(s)
        for cid in F.IDS + F.LADDER_IDS:
            assert "<b>%s %s</b>" % (cid, F.NAMES[cid]) in s, cid
        assert s.index("<b>N ") < s.index("<b>O ") < s.index("<b>P ") < s.index("<b>Q "), "letter order"
        blk = s.split("<b>Q ladder midnight reset</b>")[1].split("\n\n")[0]
        # a ladder row's % is of the ladder's pot (its start record's 1,338.63), never pin's bank
        assert ("since Nov 14 12:53 PM ET\nengaged 1 time, last Nov 15 12:00 AM ET\n🟢 net <b>+$12.04</b> (+0.90% of the "
                "ladder's pot)") in blk, blk
        assert "\nmoney the ladder made after a midnight reset (the old code stayed halted)" in blk, blk
        assert FC.block(next(c for c in F.report(now=TF.NOW_Q) if c["id"] == "Q"), BANK, 0, None, None)[-1].endswith(
            "(the old code stayed halted): +$12.04 over 1 reset since Nov 14 12:53 PM ET (4 markets settled)"), "Q's line whole"
        assert "withdrawn 11-14" in s.split("<b>O ")[1].split("\n\n")[0] and "⚠️" not in s
        assert "\nnet -$8.05: the early band bets skipped would have lost $10.23" in s.split("<b>P ")[1].split("\n\n")[0]
        Q = next(c for c in F.report(now=TF.NOW_Q) if c["id"] == "Q")
        assert FC.block(Q, BANK, 1, None)[-1] == (
            "  Nov 15 12:00 AM ET · ladder · +$12.04 · the day stop of Nov 14 (the day at -$280.00) ended at midnight ET "
            "and the ladder bid again: until its next start (Nov 15 4:50 AM ET) it made $12.04 on 4 markets; the old code "
            "would have stayed halted"), FC.block(Q, BANK, 1, None)[-1]
        rep = F.report(now=TF.NOW_Q)
        T = F.totals(rep)
        assert T["net_usd"] == round(sum(c["net_usd"] for c in rep if c["id"] not in "JO"), 2) and T["problems"] == []
        # the full page (every change, the ladder's log read): pin's headline is pin's rows only -- Q (the ladder's,
        # engaged once) out of its engagements, LAD + Q on the ladder's line with their % of the ladder's pot
        assert T["pin_engaged"] == T["engaged"] - 1 and T["pin_net_usd"] == round(
            sum(c["net_usd"] - c["overlap_usd"] for c in rep if c["group"] == "pin" and c["id"] != "J"), 2)
        assert _pin_line(s).endswith("· engaged %d times · %d open" % (T["pin_engaged"], T["pin_open"])), _pin_line(s)
        assert s.rstrip().endswith("\nLadder's changes (not pin): +$135.44 (+10.12% of the ladder's pot) · stops: "
                                   "+$27.90"), s[-300:]
        lad = next(c for c in rep if c["id"] == "LAD")
        assert FC.net_line(lad, BANK) == "🟢 net <b>+$123.40</b> (+9.22% of the ladder's pot)", FC.net_line(lad, BANK)
        stop = next(c for c in rep if c["id"] == "STOP")
        assert FC.net_line(stop, BANK) == "🟢 net <b>+$27.90</b>", "the stops' row: no % (never pin's bank)"
    finally:
        paths.set_results(old)


def test_page_room_retired_fold_and_money_cut():
    """Page room (11-14: the server's logs ran the page to 3,880 of 3,900 chars): N (shelved) and O (withdrawn) fold into
    ONE short 'not live' line in N's place, never two blocks; a retired change with a problem keeps its block; P's net
    leads its line, so the 120-char cut keeps it; no cut ever lands inside a money figure."""
    old, td = _world()
    try:
        TF.write_p(td)
        with open(os.path.join(td, "ladder-live-orders.jsonl"), "w", encoding="utf-8") as fh:
            for r in TF.run_q([]):
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        F._CACHE.clear()
        rep = F.report(now=TF.NOW_Q)
        s = str(_run(now=TF.NOW_Q))
        line = ("not live: <b>N hedge line 0.60</b> (shelved 11-09) · <b>O ladder cash limit 100%</b> (withdrawn 11-14, "
                "stays at 82%)")
        assert s.count(line) == 1 and ("\n\n%s\n\n<b>P band99 late-only</b>" % line) in s, s
        assert "SHELVED" not in s and "could not be tracked" not in s, "the long not-live words are off the page"
        assert FC.retired_line(rep) == line and FC.retired_line([c for c in rep if c["id"] not in "NO"]) is None
        blocks = len("\n" + "\n".join(FC.block(next(c for c in rep if c["id"] == "N"), BANK, 0, None, None, 0))
                     + "\n\n" + "\n".join(FC.block(next(c for c in rep if c["id"] == "O"), BANK, 0, None, None, 0)))
        assert blocks - len(line) >= 200, "the fold wins back %d chars on the page" % (blocks - len(line))
        # a retired change that says a problem keeps its block (its warning line); a live N is a block again
        N = next(c for c in rep if c["id"] == "N")
        bad = [dict(N, problem="x")] + [c for c in rep if c["id"] != "N"]
        s_bad = str(FC.render({"changes": bad, "bank": BANK}, _ctx(now=TF.NOW_Q)))
        nblk = s_bad.split("\n\n<b>N hedge line 0.60</b>\n")[1].split("\n\n")[0]
        assert "⚠️ <b>x</b>" in nblk and F.N_NOT_LIVE in nblk and "not live: <b>O ladder cash limit 100%</b>" in s_bad, s_bad
        live_n = [dict(N, since="Nov 9 12:00 AM ET", retired=None)] + [c for c in rep if c["id"] != "N"]
        s_live = str(FC.render({"changes": live_n, "bank": BANK}, _ctx(now=TF.NOW_Q)))
        assert "\n<b>N hedge line 0.60</b>\n" in s_live and "not live: <b>O ladder cash limit 100%</b>" in s_live, s_live
        # P's net first: the 120-char cut keeps it whole
        P = next(c for c in rep if c["id"] == "P")
        cut = FC.block(P, BANK, 0, None, 120)
        assert any(x.startswith("net -$8.05: the early band bets skipped would have lost $10.23") and x.endswith("…")
                   for x in cut), cut
        # never inside a money figure: at every cut point of a money line the figures left are whole
        for text in P["extra"] + [e["words"] for e in P["events"]] + ["-$1,234.56 opens it: then words"]:
            for n in range(2, len(text) + 2):
                got = FC._cut(text, n)
                body = got[:-1] if got.endswith("…") and got != text else got
                for m in FC._MONEY.finditer(body):
                    whole = FC._MONEY.match(text, m.start())
                    assert whole and whole.group() == m.group(), (text, n, got)
                assert len(got) <= n or FC._MONEY.match(text), (text, n, got)
        assert FC._cut("lost $15.56 (4 won)", 10) == "lost…" and FC._cut("lost $15.56 (4 won)", 13) == "lost $15.56…"
        assert FC._cut("net -$2.72: x", 6) == "net…" and FC._cut("$15.56 and more", 4) == "$15.56…"
    finally:
        paths.set_results(old)


def test_before_the_new_build_and_empty_folder():
    old, td = _world()
    try:
        os.remove(os.path.join(td, "pinrun-live-20261105T050000Z.jsonl"))
        os.remove(os.path.join(td, "pinrun-live-20261105T060000Z.jsonl"))       # the new build's later run (D's)
        F._CACHE.clear()
        s = str(_run())
        assert s.count("not live yet (comes with the new build)") == 8, s   # D..J and K
        # with the measured-once rows (11-14) the page gives up the "what" lines; each block keeps its own waiting words
        assert "<b>L jump hedge shadow</b>\nnot live yet (comes with the next pin restart)" in s, s
        assert "<b>M 3rd bet blocked</b>\nnot live yet (comes with the first pin start on call B)" in s, s
        assert "<b>I max positions 5</b>\nnot live yet" in s
        rep = F.report(now=TF.NOW)
        L, M, I = (next(c for c in rep if c["id"] == k) for k in "LMI")
        assert FC.block(L, BANK, 0)[1:] == ["the jump hedge is in shadow: it sends nothing; this is what it would have made "
                                            "(6 sd alarm, 8 sd cap, 5.0c bar as before)",
                                            "not live yet (comes with the next pin restart)"], FC.block(L, BANK, 0)
        assert FC.block(M, BANK, 0)[1:] == ["a close spends 2 bets, never a 3rd (--extra-coin 0 --late-extra 0, brake 4.50, "
                                            "the same bet size; the old argv allowed one more on a new coin or inside 15 s); "
                                            "the net is what that held back on pin's own buys",
                                            "not live yet (comes with the first pin start on call B)"], FC.block(M, BANK, 0)
        assert FC.block(I, BANK, 0)[1] == "up to 5 positions open at once (was 3)", FC.block(I, BANK, 0)
        assert "engaged 2 times, last Nov 2 11:44 AM ET · 1 open\n🟢 net <b>+$85.15</b>" in s, s
        for p in os.listdir(td):
            os.remove(os.path.join(td, p))
        F._CACHE.clear()
        s = str(_run())                                        # the smoke's real folder may hold no pin log at all
        # no pin log: every pin row waits; the two measured-once rows (LAD, STOP) are there all the same, their money
        # the only money on the page
        assert (s.count("not engaged yet") == 3 and s.count("not live yet") == 13 and s.count("(shelved 11-09)") == 1
                and _pin_line(s) == "⚪ <b>Pin's changes: net $0.00</b> (+0.00% of pin's bank) · engaged 0 times"
                and s.rstrip().endswith("\nLadder's changes (not pin): +$123.40 · stops: +$27.90")), s
        assert "not live yet (comes with the first pin start on --band99-max-tau 30)" in s, "P: its own waiting words"
        assert "not live yet (comes with a pin start on --wrongside-rise-c above 0)" in s, "WS: its own waiting words"
        assert "not live yet (comes with the first pin start on --index-5hz hedge)" in s, "R: its own waiting words"
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
        # nineteen rows, every one engaged (N, 11-08; P, 11-14; WS, LAD, STOP 11-14; R 11-16): even the blocks whole with
        # no events are over one message, so the "what" lines go (they go before any money line); one 30-char event each
        # no longer fits beside the rows' lines, so the page is the blocks with their lines and no event (the first PLAN
        # step that fits); with twelve one 30-char event each fits with their whats
        A_what = next(c for c in d["changes"] if c["id"] == "A")["what"]
        n = len(d["changes"])
        fits = []
        for step in FC.PLAN:
            saved, FC.PLAN = FC.PLAN, (step,)
            try:
                fits.append((step, len(str(FC.render(d, _ctx()))) <= MAX_LEN))
            finally:
                FC.PLAN = saved
        first = next(st for st, ok in fits if ok)
        assert n == 19 and first == (0, None, None, 0) and "w" * 30 not in s and s.count("\n\n<b>") == n and A_what not in s, \
            "the nineteen blocks without their whats and events, at the first step that fits: %s" % (first,)
        d["changes"] = d["changes"][:12]
        for c in d["changes"]:
            c["extra"] = []                                    # (D's line under its net since 11-14: this is about events)
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and s.count("w" * 29 + "…") == 12 and "w" * 59 not in s, "twelve: one event each, cut to 30"
        for c in d["changes"]:
            c["events"] = c["events"][:1]
            c["events"][0] = dict(c["events"][0], words="x" * 2000)
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and "x" * 2000 not in s and s.count("x" * 29 + "…") == 12, "one cut event each"
        for c in d["changes"]:
            c["what"] = "y" * 300                              # the whats alone are over the limit: they go, the events return
        s = str(FC.render(d, _ctx()))
        assert len(s) <= MAX_LEN and "yyyy" not in s and s.count("x" * 29 + "…") == 12, \
            "when the blocks with their whats do not fit, the whats go before any money line and the events come back"
        for c in d["changes"]:
            c["extra"] = ["z" * 200, "z" * 200]                # ...and the extra lines go last: cut to 120, then left out
        s = str(FC.render(d, _ctx()))                          # (12 x 2 x 200-char lines are over one message with anything)
        assert (len(s) <= MAX_LEN and "z" * 120 not in s and "yyyy" not in s and s.count("z" * 119 + "…") == 12
                and s.count("\nzzz") == 12), \
            "each row keeps its FIRST line (its money line), cut to 120; the second is left out, never whole"
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


def test_undo_ws_and_the_split_total():
    """The 11-14 undo (M, K, WS switched off; B's cap dropped): each undone row says UNDONE on its since line and its
    NET LINE carries both periods, 'with the rule: net $X (..%) · since the undo (vs keeping it): $Y (..%) on N', at
    every shrink step (the 11-14 review: the last step dropped every undo line); the bold net and its dot stay the
    rule's money against never making it, the undo's has its own dot and is beside the total, never in it; B's net line
    says the share of it C counts too; the total line splits pin's, the ladder's and the stops' money."""
    old, td = _world(logs=False)
    try:
        TF._write(td, "pinrun-live-20261115T100000Z.jsonl", TF.run_u([]))
        TF.write_ws(td)
        F._CACHE.clear()
        now = 1794780000.0
        s = str(_run(now=now))
        assert len(s) <= MAX_LEN, len(s)
        rep = F.report(now=now)
        ws = next(x for x in rep if x["id"] == "WS")             # (its prices read pin's markets of both logs here)

        def p(x):
            return "(%s%.2f%% of the bank)" % ("+" if x >= 0 else "-", abs(x) / BANK * 100)
        want = {"M": "⚪ with the rule: net <b>$0.00</b> %s · 🟢 since the undo (vs keeping it): <b>+$1.48</b> %s on 1 bet"
                     % (p(0.0), p(1.48)),
                "K": "⚪ with the rule: net <b>$0.00</b> %s · 🟢 since the undo (vs keeping it): <b>+$2.00</b> %s on 1 market"
                     % (p(0.0), p(2.0)),
                "WS": "%s with the rule: net <b>%s</b> %s · 🔴 since the undo (vs keeping it): <b>-$48.50</b> %s on 2 "
                      "markets" % (FC._mark(ws["rule_usd"]), usd(ws["rule_usd"]), p(ws["rule_usd"]), p(-48.5))}
        for k, line in want.items():
            c = next(x for x in rep if x["id"] == k)
            blk = s.split("<b>%s %s</b>" % (k, F.NAMES[k]))[1].split("\n\n")[0]
            assert "· UNDONE Nov 15 6:00 AM ET\n" in blk and ("\n%s" % line) in blk, (k, blk)
            for step in FC.PLAN:                                 # never on a line a shrink step can drop
                assert line in FC.block(c, BANK, *step), (k, step)
            assert c["net_usd"] == c["rule_usd"], "the bold net is the rule's money vs never making it: %s" % k
        kblk = s.split("<b>K cheap morning skip</b>")[1].split("\n\n")[0]
        assert "UNDONE Nov 15 6:00 AM ET\nnot engaged while the rule was on\n" + want["K"] in kblk, kblk
        kc = next(x for x in rep if x["id"] == "K")
        assert FC.block(kc, BANK, 0, None, None, 0)[-1] == ("since the undo: 1 more the wrong-side rule would have skipped "
                                                           "first: in WS's row"), "K's undo note: its last line"
        # the step before the last keeps only the measured-once rows' assumption lines; the undo money stays on K's net line
        fx = (0, None, (1, 90, "fixed"), 0)
        lad = next(x for x in rep if x["id"] == "LAD")
        assert fx in FC.PLAN and FC.PLAN.index(fx) == len(FC.PLAN) - 4 and FC.block(kc, BANK, *fx)[-1] == want["K"] \
            and FC.block(lad, BANK, *fx)[-1].startswith("the 11-14 replay's central fill model; $119.42 to $140.63"), \
            (FC.block(kc, BANK, *fx), FC.block(lad, BANK, *fx))
        bblk = s.split("<b>B jump cap</b>")[1].split("\n\n")[0]
        assert ("since Nov 1 3:37 PM ET · DROPPED Nov 15 6:00 AM ET\nnot engaged while the rule was on\n⚪ net <b>$0.00</b> "
                "%s\n" % p(0.0) in bblk and "\nthe cap was DROPPED Nov 15 6:00 AM ET" in bblk), bblk
        T = F.totals(rep)
        g = T["groups"]
        last = _pin_line(s)
        assert last.startswith("🟢 <b>Pin's changes: net %s</b> (+%.2f%% of pin's bank) · engaged %d times" % (
            usd(g["pin"]), g["pin"] / BANK * 100, T["pin_engaged"])) and T["pin_net_usd"] == g["pin"], s[-300:]
        assert last.endswith(" · the undos (vs keeping the rules): -$45.02") and T["undo_usd"] == -45.02, last
        assert s.rstrip().endswith("\nLadder's changes (not pin): +$123.40 · stops: +$27.90"), s[-200:]
        assert "an UNDONE rule's net ends at its undo; the undo's money (vs keeping the rule) is beside it, not in the " \
               "total" in s, "the legend says what an undone rule's net is"
        assert "—" not in s
        # a costly rule whose undo wins: the bold net and its dot stay the rule's (red), the undo's money its own (green)
        c = {"id": "M", "net_usd": -57.5, "rule_usd": -57.5, "undo": {"since": "Nov 14 2:30 PM ET", "net_usd": 80.0,
                                                                      "engaged": 3, "open": 1}}
        assert FC.net_line(c, BANK) == ("🔴 with the rule: net <b>-$57.50</b> %s · 🟢 since the undo (vs keeping it): "
                                        "<b>+$80.00</b> %s on 3 bets · 1 open" % (p(-57.5), p(80.0))), FC.net_line(c, BANK)
        assert FC.net_line({"id": "B", "net_usd": -25.12, "overlap_usd": 11.57}, BANK) == \
            "🔴 net <b>-$25.12</b> %s · of it +$11.57 is C's extra legs too" % p(-25.12), "B's share C counts too, on its net line"
    finally:
        paths.set_results(old)


def test_bank_fallback_and_wall():
    old, td = _world(logs=False)
    try:
        s = str(_run(ledger=False))                            # no ledger planted: no % at all
        assert "of the bank" not in s and "% of pin's bank" not in s and _pin_line(s) == (
            "⚪ <b>Pin's changes: net $0.00</b> · engaged 0 times"), s   # LAD + STOP only: never in pin's figure
        with open(os.path.join(td, "pinrun-live-size.json"), "w", encoding="utf-8") as fh:
            json.dump({"bank": 1400.0, "size": 160}, fh)
        s = str(_run(ledger=False))
        assert "(+0.00% of pin's bank)" in _pin_line(s) and "(+8.81% of the bank)" not in s, \
            "the pin bot's own size file is the fallback bank (pin's headline has its %), never LAD's base"
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
