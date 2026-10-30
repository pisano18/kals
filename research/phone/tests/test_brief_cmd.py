"""test_brief_cmd.py -- phone/commands/brief_cmd.py (/brief /summary) against Phone.text_brief (lane D6, rebuild step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_brief_cmd.py

pinbrief is planted (brief / text) and botstats.all_bots too: every pot's top read and failing (one warning line), a
day botstats calls neither today nor yesterday (no top: pinbrief's words alone), Kalshi unreadable for today, and
pinbrief failing (the old wall's words, nothing logged).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.brief_cmd as brief_cmd                         # noqa: E402
import pinbrief                                                      # noqa: E402

BRIEF_TEXT = ("DAILY BRIEFING -- Wed Sep 16\n\nMONEY: +$1.66 today\nWHAT CHANGED, since yesterday\n"
              "  nothing new\nWATCH: the race")


def _pinbrief(ok=True):
    def brief(ledger=None, **k):
        if not ok:
            raise OSError("planted: pinbrief could not read its files")
        return {"planted": True}
    return {(pinbrief, "brief"): brief, (pinbrief, "text"): lambda b: BRIEF_TEXT}


def _all(today="2026-09-16", partial=True, markets=0):
    import botstats
    w = {"partial": partial, "markets": markets, "won": 0, "money": 0.0, "missing": ["fx"], "pot": None}
    return lambda now=None, getter=None, procs=None: {
        "today_et": today, "total": {"today": dict(w), "yesterday": dict(w, markets=0)},
        "bots": {b: {"money": {}} for b in botstats.BOTS}, "other": {}}


def _check(what, **kw):
    ph = W.phone(W.PlantLedger(W.results_dir()))
    for text in ("/brief", "/summary"):
        with W.patched(**kw):
            old, new = W.old_new(ph, text, ph.text_brief)
        W.same(old, new, "%s %s" % (what, text))
    return str(new)


def test_all_bots_failing_and_read():
    r = _check("all_bots raises", mod=_pinbrief())
    assert "All bots today: could not be read" in r and "(main account)" in r and "DAILY BRIEFING" in r, r
    r = _check("today unknown", mod=_pinbrief(), all_bots=_all())
    assert "All bots today: unknown -- Kalshi could not be read" in r, r


def test_not_today_and_pinbrief_failing():
    r = _check("another day", mod=_pinbrief(), all_bots=_all(today="2026-09-20"))
    assert r.startswith("📰 <b>DAILY BRIEFING") and "main account" not in r, r
    r = _check("pinbrief raises", mod=_pinbrief(ok=False))
    assert r.startswith("Could not build today's briefing: planted: pinbrief"), r


def test_declared():
    import tgcharts
    c = brief_cmd.COMMAND
    assert c.names == ("/brief", "/summary") and c.section == "now" and c.order == 70 and c.fail is None
    assert c.kind_of("/brief") == c.kind_of("/summary") == tgcharts.kind_of("/brief") == tgcharts.kind_of("/summary")


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_brief_cmd"))
