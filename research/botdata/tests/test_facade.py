"""test_facade.py -- botstats.py is a facade over botdata: every name its callers use is there (the same objects), and
setting a name on botstats reaches the module that reads it.

v-tg-rebuild step 7 (2026-10-30). Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_facade.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import RESEARCH, ck, run, sandbox                          # noqa: E402

import botstats as bs                                               # noqa: E402
from botdata import kalshi, paths, procs, report, status, tables, words   # noqa: E402

# what pinphone, tgcharts, pindesk, server_sync, bars, the registry's test and the golden harness read from botstats
# (scanned 2026-10-30 at the split; test_names_used_today rescans the files as they are now)
CONTRACT = ("ALWAYS_SHOWN BOTS EARLIER FILL_KINDS FX_PAIRS HALT_KINDS INFRA_VER JB_SERIES LEDGERS LONG_DAYS PATHS "
            "PIN_HOURLY PLAIN POT_OWNER POT_PATHS POT_POOL_ONLY RESULTS SPEC SUBS SUB_NAME SUB_POOL WX_VER _BACK _MEMO "
            "_VER _VER_T _epoch _int _load _money_block _norm_procs _num _pot_note _pot_now _t_of active_bots "
            "active_from activity all_bots avg_day avg_words bot bot_subs cached_pots day_label day_pot day_start "
            "default_getter describe et_clock et_day fill_of fill_sub fills_since flows is_active is_bot last_record "
            "load_cache market owner pct pin_logs pinxfer plain pot_as_of_note pot_check_lines pot_context pot_for "
            "pot_pct_txt pot_rows pot_settlements pot_words read_since running settings_clean settings_fx "
            "settings_jumpband settings_pin settings_race settings_weather shift_day shown_by shown_cash shown_name "
            "shown_parts stop_set sub_name usd version_of xfer_in_pot "
            # pindesk (getattr), the golden seams, the CLI
            "_bot_text text_summary _procs_native read_procs selftest main").split()
USERS = ("pinphone.py", "tgcharts.py", "pindesk.py", "server_sync.py", "bars.py", os.path.join("bots", "tests",
         "test_registry.py"), os.path.join("golden", "gl_cases.py"), os.path.join("golden", "gl_child.py"))


def test_contract_names():
    missing = [n for n in CONTRACT if not hasattr(bs, n)]
    ck(not missing, "every name botstats' callers use is on the facade (%d names; missing %s)" % (len(CONTRACT), missing))
    ck(bs.SPEC is tables.SPEC and bs.SUB_POOL is tables.SUB_POOL and bs._MEMO is kalshi._MEMO
       and bs.all_bots is report.all_bots and bs._bot_text is words._bot_text and bs._ACTIVE is status._ACTIVE
       and bs.procs_for is procs.procs_for,
       "the facade's names ARE botdata's objects (a dict changed in place is changed for every reader)")


def test_names_used_today():
    names = set()
    for f in USERS:
        p = os.path.join(RESEARCH, f)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            src = fh.read()
        names |= set(re.findall(r"(?<![\w.])(?:botstats|bs|_bs\(\)|BS|_bsm|_bsd|_bsc)\.(\w+)", src))
    names.discard("py")
    missing = sorted(n for n in names if not hasattr(bs, n))
    ck(not missing, "every botstats.<name> the callers' files use today exists (%d names; missing %s)" % (len(names), missing))


def test_setting_a_name_reaches_its_module():
    saved = report._load
    try:
        fake = lambda now, getter, procs_: (_ for _ in ()).throw(RuntimeError("planted _load"))   # noqa: E731
        bs._load = fake
        ck(report._load is fake, "botstats._load = f sets botdata.report._load (tgcharts' test does this)")
        try:
            bs.all_bots(now=1.0)
            ok = False
        except RuntimeError as e:
            ok = "planted _load" in str(e)
        ck(ok, "and all_bots, which calls _load, uses it -- as when botstats was one file")
    finally:
        bs._load = saved
    ck(report._load is saved and bs._load is saved, "setting it back restores both")
    old = bs.RESULTS
    with sandbox() as td:
        ck(bs.RESULTS == td == paths.RESULTS, "botstats.RESULTS reads botdata.paths.RESULTS")
    bs.RESULTS = os.path.join(old, "x")
    try:
        ck(paths.RESULTS == os.path.join(old, "x") and kalshi.cache_path() == os.path.join(old, "x", kalshi.CACHE_NAME),
           "botstats.RESULTS = d moves every botdata reader (the cache path too)")
    finally:
        bs.RESULTS = old
    ck(paths.RESULTS == old, "and back")


def test_facade_is_small():
    with open(bs.__file__, encoding="utf-8") as fh:
        n = sum(1 for _ in fh)
    ck(n < 400, "botstats.py is a facade (%d lines, its docstring included)" % n)


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_facade"))
