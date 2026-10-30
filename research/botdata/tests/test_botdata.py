"""test_botdata.py -- botdata.paths / clock / fmt are the code they were copied from, and the write fence works.

v-tg-rebuild step 2 (2026-10-30). Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_botdata.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed.
"""
import os
import subprocess
import sys
import tempfile
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)

from botdata import clock, fmt, paths                               # noqa: E402
import botstats as bs                                                # noqa: E402
import pindesk                                                       # noqa: E402
import pinphone as pp                                                # noqa: E402
import tgcharts as tgc                                               # noqa: E402

MONEY = [None, 0, 0.0, 0.004, 0.0045, 0.005, 0.0051, -0.004, -0.0045, -0.005, 0.01, -0.01, 1, -1, 1234.567, -1234.5,
         1e6, -0.0001, 12.345, 99.995, 0.3333]
PCTS = [None, 0, 0.5, -0.5, 0.999, 1, -1, 1.04, 12.345, -0.004, 100]
COUNTS = [0, 1, 1.0, 2, 26.31, 99.999, 100, 100.4, 1234, 1234.5, "3", None, "x", 0.004]
DAYS = ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2026-03-07", "2026-03-08", "2026-03-09",
        "2026-01-01", "2025-12-31", "2028-02-29"]


def eq(a, b, what):
    if a != b:
        raise AssertionError("%s differs: botdata %r, legacy %r" % (what, a, b))


def test_results_is_the_same_string():
    eq(paths.RESULTS, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(bs.__file__))), "results"), "RESULTS")
    eq(bs.RESULTS, paths.RESULTS, "botstats.RESULTS")
    eq(pp.RESULTS, pindesk.RESULTS, "pinphone.RESULTS vs pindesk.RESULTS")
    eq(pp.RESULTS, paths.RESULTS, "pinphone.RESULTS")


def test_set_results_and_results():
    old = paths.set_results(r"C:\somewhere")
    try:
        eq(paths.results("a.json"), os.path.join(r"C:\somewhere", "a.json"), "results()")
    finally:
        paths.set_results(old)
    eq(paths.RESULTS, old, "restored")


def test_write_fence():
    env = dict(os.environ)
    try:
        os.environ.pop("KALS_TESTING", None)
        paths.check_write(os.path.join(paths.DEFAULT_RESULTS, "botstats_cache.json"))     # nothing when not a test
        os.environ["KALS_TESTING"] = "1"
        for p in (os.path.join(paths.DEFAULT_RESULTS, "botstats_cache.json"), r"C:\kals-repo\results\pinphone.log",
                  r"c:\KALS-REPO\RESULTS\pinphone.update", r"C:\kals\telegram.json", paths.DEFAULT_RESULTS):
            try:
                paths.check_write(p)
            except paths.WriteFenced as e:
                assert isinstance(e, PermissionError) and isinstance(e, OSError)
                continue
            raise AssertionError("not fenced: %s" % p)
        td = tempfile.mkdtemp(prefix="botdata-")
        paths.check_write(os.path.join(td, "x.json"))                      # a temp folder is fine
        paths.check_write(r"C:\kals-repo\results-other\x")                 # a sibling name is not inside
        paths.check_write(r"C:\kalsx\x")
        os.rmdir(td)
    finally:
        os.environ.clear()
        os.environ.update(env)


def test_fence_in_the_writers():
    """Under KALS_TESTING=1 botstats.save_cache and pinphone.log never touch the live files (a child process, so the
    patched-dead-name situation is real: nothing here is redirected)."""
    code = ("import os, sys; sys.path.insert(0, %r); os.environ['KALS_TESTING'] = '1'; import botstats, pinphone; "
            "p = botstats.cache_path(); m = os.path.getmtime(p) if os.path.exists(p) else None; "
            "r = botstats.save_cache({'v': 1, 'subs': {}}); "
            "l = pinphone.LOG; lm = os.path.getmtime(l) if os.path.exists(l) else None; pinphone.log('fence test'); "
            "print('SAVE', r, (os.path.getmtime(p) if os.path.exists(p) else None) == m, "
            "(os.path.getmtime(l) if os.path.exists(l) else None) == lm)" % RESEARCH)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "SAVE False True True" in r.stdout, r.stdout[-2000:]


def test_fmt_matches_legacy():
    for x in MONEY:
        eq(fmt.usd(x), bs.usd(x), "usd(%r) vs botstats" % (x,))
        eq(fmt.usd(x), pp.usd(x), "usd(%r) vs pinphone" % (x,))
        for s in (True, False):
            eq(fmt.usd_chart(x, s), tgc.usd(x, s), "usd_chart(%r, %r) vs tgcharts" % (x, s))
        if x is not None:
            eq(fmt.dollars(x), pp.dollars(x), "dollars(%r)" % (x,))
            eq(fmt.cash(x), pp._cash(x), "cash(%r)" % (x,))
            eq(fmt.pct_frac(x), pindesk.pct(x), "pct_frac(%r)" % (x,))
            eq(fmt.pct_frac(x, False), pindesk.pct(x, False), "pct_frac(%r, False)" % (x,))
    eq(fmt.cash(None), pp._cash(None), "cash(None)")
    eq(fmt.pct_frac(None), pindesk.pct(None), "pct_frac(None)")
    eq(fmt.dollars(None), pp.dollars(None), "dollars(None)")
    # the documented difference (step 12 decides): 0.0045 is '+$0.00' in usd, '$0.00' in usd_chart
    eq((fmt.usd(0.0045), fmt.usd_chart(0.0045)), ("+$0.00", "$0.00"), "the zero-band difference")
    for x in PCTS:
        eq(fmt.pct(x), bs.pct(x), "pct(%r)" % (x,))
        eq(fmt.pot_pct_txt(x), bs.pot_pct_txt(x), "pot_pct_txt(%r)" % (x,))
    for k in COUNTS:
        eq(fmt.cnt(k), pp._cnt(k), "cnt(%r)" % (k,))
        eq(fmt.nof(k, "market"), pp._nof(k, "market"), "nof(%r)" % (k,))
        if isinstance(k, int):
            eq(fmt.plural(k, "order"), bs._n(k, "order"), "plural(%r)" % (k,))
    for x in [None, 0, 0.98, 0.978, "0.5", 1, 0.0001, "x"]:
        eq(fmt.num(x), bs._num(x), "num(%r)" % (x,))
        eq(fmt.fmt_g(x), bs._fmt_g(x), "fmt_g(%r)" % (x,))
        if x != "x":
            eq(fmt.cents(x), bs._c(x), "cents(%r)" % (x,))


def test_clock_matches_legacy():
    for d in DAYS:
        eq(clock.day_start(d), bs.day_start(d), "day_start(%s)" % d)
        eq(clock.day_start(d), pindesk.et_day_start(d), "day_start(%s) vs pindesk" % d)
        eq(clock.prev_day(d), tgc.prev_day(d), "prev_day(%s)" % d)
        eq(clock.prev_day(d), bs.shift_day(d, -1), "prev_day(%s) vs shift_day" % d)
        eq(clock.day_label(d), bs.day_label(d), "day_label(%s)" % d)
        for k in (-40, -7, -1, 0, 1, 7, 31):
            eq(clock.shift_day(d, k), bs.shift_day(d, k), "shift_day(%s, %d)" % (d, k))
            eq(clock.day_minus(d, k), pp.day_minus(d, k), "day_minus(%s, %d)" % (d, k))
        for d1 in DAYS:
            if d1 >= d:
                eq(clock.days_between(d, d1), pp.days_between(d, d1), "days_between(%s, %s)" % (d, d1))
    eq(clock.day_label("junk"), bs.day_label("junk"), "day_label(junk)")
    t0 = bs.day_start("2026-10-31")
    for k in range(0, 72 * 4):
        e = t0 + 900 * k + 7
        eq(clock.et_day(e), bs.et_day(e), "et_day(%s)" % e)
        eq(clock.et_day(e), pindesk.et_day(e), "et_day(%s) vs pindesk" % e)
        eq(clock.et_clock(e), bs.et_clock(e), "et_clock(%s)" % e)
        eq(clock.et_clock(e, False), bs.et_clock(e, False), "et_clock(%s, False)" % e)
    eq(clock.et_clock(None), bs.et_clock(None), "et_clock(None)")
    for t in ("2026-09-30T04:15:06.437143Z", "2026-09-30T04:15:06Z", None, "junk", 5):
        eq(clock.utc_epoch(t), bs._epoch(t), "utc_epoch(%r)" % (t,))


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
    print("test_botdata: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
