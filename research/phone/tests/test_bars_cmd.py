"""test_bars_cmd.py -- phone/commands/bars_cmd.py (/bars) against Phone.text_bars (lane D6, rebuild step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_bars_cmd.py

research/bars.py is planted as a stand-in module (sys.modules['bars']): gather's numbers become the Phone's _bars_d
(the picture's source) exactly as before; a planted bars_fn is quoted with no wall; bars.py raising -> the old wall's
words and _bars_d None.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.bars_cmd as bars_cmd                           # noqa: E402

TEXT = ("BARS  every running test against its bar\n\nZ3 -- paper race arm\n  race 1\n  race 2\n"
        "VERDICT (z3): TOO EARLY\n\nGAP075 -- stopped\nVERDICT: KILL")


def _bars(ok=True):
    m = types.ModuleType("bars")

    def gather(results, now):
        if not ok:
            raise ValueError("planted: bars.py broke")
        return {"results": results, "now": now}
    m.gather = gather
    m.render = lambda d: TEXT
    return m


def _run(ph, text="/bars"):
    with W.patched():
        old = ph.text_bars()
        d_old = ph._bars_d
        ph._bars_d = "sentinel"
        old2, new = W.old_new(ph, text, lambda: None)
        return old, d_old, new, ph._bars_d


def test_gathered_and_failing():
    for ok in (True, False):
        saved = sys.modules.get("bars")
        sys.modules["bars"] = _bars(ok)
        try:
            ph = W.phone(W.PlantLedger(W.results_dir(races=False)))
            old, d_old, new, d_new = _run(ph)
        finally:
            if saved is None:
                sys.modules.pop("bars", None)
            else:
                sys.modules["bars"] = saved
        W.same(old, new, "bars ok=%s" % ok)
        assert d_old == d_new and ((d_new is None) != ok), (d_old, d_new)
        assert ("VERDICT" in str(new)) == ok and (str(new).startswith("Could not build /bars: planted")) != ok, new


def test_planted_text():
    ph = W.phone(W.PlantLedger(W.results_dir(races=False)), bars_fn=lambda: TEXT)
    old, d_old, new, d_new = _run(ph)
    W.same(old, new, "planted bars_fn")
    assert d_new == "sentinel"                      # a planted text leaves _bars_d alone, as before


def test_declared():
    import tgcharts
    c = bars_cmd.COMMAND
    assert c.names == ("/bars",) and c.section == "now" and c.order == 80
    assert c.kind_of("/bars") == tgcharts.kind_of("/bars") == "bars"


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_bars_cmd"))
