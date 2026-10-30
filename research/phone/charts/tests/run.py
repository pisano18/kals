"""run.py -- every chart test, in order, by our own tiny runner (no pytest on C:\\Python314).

v-tg-rebuild step 8 (2026-10-30). `python research/tgcharts.py --selftest` runs this (and keeps its last line
'tgcharts selftest: OK (matplotlib X)' and its exit code: a failed check raises SystemExit('tgcharts selftest: FAILED
-- ...'), exit 1). Also runnable on its own:  C:\\Python314\\python.exe research\\phone\\charts\\tests\\run.py
Every picture is drawn from planted data (no file outside a temp folder, no network); KALS_TESTING=1 fences every live
file (botdata.paths).
"""
import os
import sys

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)

MODULES = ("test_main_account", "test_series", "test_botstats_charts", "test_kinds_palette_bars", "test_ctx")


def main():
    os.environ.setdefault("KALS_TESTING", "1")
    import importlib
    from phone.charts.base import mpl
    for name in MODULES:
        mod = importlib.import_module("phone.charts.tests." + name)
        for fn in mod.TESTS:
            print("-- %s.%s" % (name, fn.__name__), flush=True)
            fn()
    print("tgcharts selftest: OK (matplotlib %s)" % mpl()["version"])


if __name__ == "__main__":
    main()
