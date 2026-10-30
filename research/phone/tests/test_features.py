"""test_features.py -- phone/commands/features.py (/features) against Phone.text_features (lane D6, rebuild step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_features.py

boot_all.ps1 and ladder_live.py are planted through pinphone's BOOT_ALL / LADDER_PY (the globals features_html reads);
a missing boot_all; and features_html raising (the old wall: logged, 'Could not build /features: ...').
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.features as features                           # noqa: E402

BOOT = ("Start-Bot 'pin' \"research\\pinrun.py --live --size 20 --hedge-belief 0.40\"\n"
        "Start-Bot 'race' \"research\\pinracearm.py --live --max-contracts 20 --log results/pinracepenny-live.jsonl\"\n")


def _files(boot=True):
    td = tempfile.mkdtemp(prefix="test_features_")
    b = os.path.join(td, "boot_all.ps1")
    if boot:
        with open(b, "w", encoding="utf-8") as fh:
            fh.write(BOOT)
    return {(W.pp, "BOOT_ALL"): b, (W.pp, "LADDER_PY"): os.path.join(td, "ladder_live.py")}


def _check(what, **kw):
    ph = W.phone(W.PlantLedger(W.results_dir(races=False)), bs_procs=[])
    with W.patched(**kw):
        old, new = W.old_new(ph, "/features", ph.text_features)
    W.same(old, new, what)
    return str(new)


def test_page():
    r = _check("boot planted", mod=_files())
    assert "Features" in r, r
    _check("no boot_all", mod=_files(boot=False), active=("pin",))


def test_wall():
    def broken(**k):
        raise KeyError("planted")
    mod = _files()
    mod[(W.pp, "features_html")] = broken
    r = _check("features_html raises", mod=mod)
    assert r == "Could not build /features: 'planted'", r


def test_declared():
    import tgcharts
    c = features.COMMAND
    assert c.names == ("/features",) and c.section == "now" and c.order == 90 and c.chart is None
    assert tgcharts.kind_of("/features") is None and c.fail is not None
    assert c.help_line in W.pp.HELP_TEXT.split("\n")


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_features"))
