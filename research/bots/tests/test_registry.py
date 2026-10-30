"""test_registry.py -- the registry (research/bots) reproduces every per-bot table and rule it will replace.

v-tg-rebuild step 1 (2026-10-30). Run:  C:\\Python314\\python.exe research\\bots\\tests\\test_registry.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed.

What it proves, against the LIVE modules (botstats, pinphone, tgcharts imported as they are):
  - EQUALITY of every derived table with the legacy table it replaces (botstats SPEC, BOTS, SUBS, SUB_POOL,
    POT_POOL_ONLY, POT_OWNER, HALT_KINDS, FILL_KINDS, ALWAYS_SHOWN, PLAIN, SUB_NAME, PIN_HOURLY, FX_PAIRS, JB_SERIES;
    pinphone BOT_CMDS, BOT_CMD_OF, BOT_WORD, HELP_BOT_LINES, FUNDS_WHAT, FUNDS_BOTS, FUNDS_SIZE_BOTS, FUNDS_SHORT,
    FEATURES, FEATURE_BOT, SPEED_*, LADDER_GOAL_PCT, text_bot's footers, the race's 'leg'; tgcharts BOT_SHORT,
    BOT_COLOUR, BOT_ORDER, CMD_KIND's bot entries, ACCOUNT_NAME, POT_WHAT);
  - owner() equal to botstats.owner on every (sub, ticker) the golden fixture's botstats cache holds, plus synthetic
    edge tickers in every sub and in subs that do not exist;
  - is_bot, bot_subs, fill_sub, the settings hooks, the activity hooks, fill_of's fields and the VERSIONS.md ownership
    rule equal to botstats' on fixture data and synthetic records.
Read only: the fixture (C:\\kals-golden\\fixtures\\..., or KALS_GOLDEN_FIXTURE) is only read; synthetic logs go to a temp
folder; KALS_TESTING=1 fences every live file.
"""
import ast
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import bots                                                          # noqa: E402
from bots.spec import Bot, Logs, Pot, Records, SettingsIn, VersionRule, live_flag   # noqa: E402
import botstats as bs                                                # noqa: E402
import pinphone as pp                                                # noqa: E402
import tgcharts as tgc                                               # noqa: E402

FIXTURE = os.environ.get("KALS_GOLDEN_FIXTURE", r"C:\kals-golden\fixtures\20261030T132932Z")
FIX_RESULTS = os.path.join(FIXTURE, "results")

SYNTH_TICKERS = [  # golden/gl_cases.SYNTH_TICKERS + more edges of every family
    "KXBTC15M-26OCT301300-00", "KXETH15M-26OCT301300-00", "KXBNB15M-26OCT301300-00", "KXHYPE15M-26OCT301300-00",
    "KXZEC15M-26OCT301300-00", "KXNEAR15M-26OCT301300-00", "KXCRYPTOLEAD15M-26OCT301300", "KXCRYPTOLEADX-26OCT30",
    "KXBTCD-26OCT3013-T100000", "KXDOGED-26OCT3013-T0.2", "KXEURUSD15M-26OCT301300-T1.08", "KXUSDJPY15M-26OCT301300-T150",
    "KXGOLD15M-26OCT301300-T2600", "KXHIGHNY-26OCT30-T60", "KXRAINNYC-26OCT30", "KXNFLGAME-26NOV01NYGDAL-DAL", "",
    "KXCRYPTOCOMP15M-26OCT301300-BTC", "KXCRYPTOLEAD", "KXSOL15M-26OCT301300-00", "KXXRP15M-26OCT301300-00",
    "KXDOGE15M-26OCT301300-00", "KXHYPED-26OCT3013-T40", "KXBNBD-26OCT3013-T600", "KXGBPUSD15M-26OCT301300-T1.3",
    "KXAUDUSD15M-26OCT301300", "KXUSDCAD15M-26OCT301300", "KXWTI15M-26OCT301300-T70", "KXHIGHTSFO-26SEP29-B72.5",
    "kxbtc15m-26oct301300-00", "KXBTC15M", "-", "KXOIL-26OCT30", None]
SYNTH_SUBS = ["0", "1", "2", "3", "4", "5", "6", "", None, 1, 3, "main", "03"]


def eq(a, b, what):
    if a != b:
        raise AssertionError("%s differs:\n  registry: %r\n  legacy:   %r" % (what, a, b))


def eq_ordered(a, b, what):
    """Equal AND in the same order (dict items, list items)."""
    eq(a, b, what)
    if isinstance(a, dict):
        eq(list(a.items()), list(b.items()), what + " (order)")


# ---- discovery -----------------------------------------------------------------------------------------------------
def test_discovery_finds_every_bot_in_order():
    eq(bots.names(), bs.BOTS, "bots.names() vs botstats.BOTS")
    eq(tuple(b.order for b in bots.all_bots()), tuple(range(1, 8)), "orders")
    for b in bots.all_bots():
        assert bots.get(b.name) is b
    assert bots.get("nosuchbot") is None


def test_import_is_lazy_and_cycle_free():
    """`import bots` imports no bot file and none of the phone's modules; the first lookup loads them."""
    code = ("import sys; sys.path.insert(0, %r); import bots; "
            "bad = [m for m in sys.modules if m.startswith('bots.') or m in ('botstats', 'pinphone', 'tgcharts', 'pinday')]; "
            "print('LOADED', bad); bots.names(); print('AFTER', sorted(m for m in sys.modules if m.startswith('bots.')))"
            % RESEARCH)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    assert "LOADED ['bots.spec']" in r.stdout or "LOADED []" in r.stdout, r.stdout
    for n in bs.BOTS:
        assert "bots.%s" % n in r.stdout, r.stdout
    assert "botstats" not in r.stdout and "pinphone" not in r.stdout, r.stdout


def test_validate_refuses_bad_registries():
    base = bots.get("ladder")

    def clone(**kw):
        d = {f: getattr(base, f) for f in base.__dataclass_fields__}
        d.update(kw)
        return Bot(**d)
    good = list(bots.all_bots())
    assert bots.validate(good)
    for bad, why in ((good + [clone()], "repeated name"),
                     (good + [clone(name="ladder2", order=4)], "repeated order"),
                     (good + [clone(name="ladder2", order=99, commands=("/ladder2", "/fc"), command="/ladder2")],
                      "repeated command"),
                     (good + [clone(name="ladder2", order=99, commands=("/l2",), command="/l2",
                                    pots=(Pot("1", 2),))], "two catch-all pots in sub 1"),
                     (good + [clone(name="ladder2", order=99, commands=("/l2",), command="/l2",
                                    pots=(Pot("4", 2, claims=lambda s, t: False, pool_only=True),))],
                      "two pool-only pots in sub 4"),
                     (good + [clone(name="ladder2", order=99, commands=("/l2",), command="/l3")], "command not listed"),
                     (good + [clone(name="ladder2", order=99, commands=("/l2",), command="/l2", pots=())], "no pot"),
                     (good + [clone(name="other", order=99, commands=("/l2",), command="/l2")], "reserved name")):
        try:
            bots.validate(bad)
        except bots.RegistryError:
            continue
        raise AssertionError("validate accepted a registry with a %s" % why)


def test_lazy_hook_resolves():
    assert bots.resolve("botstats:settings_fx") is bs.settings_fx
    assert bots.resolve(None) is None
    f = bots.get("fx").settings
    assert bots.resolve(f) is f


# ---- botstats' tables ----------------------------------------------------------------------------------------------
def test_botstats_spec():
    spec = bots.legacy_spec()
    eq(list(spec), list(bs.SPEC), "SPEC bot order")
    for n in bs.SPEC:
        eq_ordered(spec[n], bs.SPEC[n], "SPEC[%r]" % n)


def test_botstats_tables():
    eq(bots.BOTS, bs.BOTS, "BOTS")
    eq(bots.SUBS, bs.SUBS, "SUBS")
    eq_ordered(bots.SUB_POOL, bs.SUB_POOL, "SUB_POOL")
    eq_ordered(bots.POT_POOL_ONLY, bs.POT_POOL_ONLY, "POT_POOL_ONLY")
    eq_ordered(bots.POT_OWNER, bs.POT_OWNER, "POT_OWNER")
    eq_ordered(bots.HALT_KINDS, bs.HALT_KINDS, "HALT_KINDS")
    eq_ordered(bots.FILL_KINDS, bs.FILL_KINDS, "FILL_KINDS")
    eq(bots.ALWAYS_SHOWN, bs.ALWAYS_SHOWN, "ALWAYS_SHOWN")
    eq(bots.PLAIN, bs.PLAIN, "PLAIN")
    eq_ordered(bots.SUB_NAME, bs.SUB_NAME, "SUB_NAME")
    eq(bots.EARLIER, bs.EARLIER, "EARLIER")
    from bots import fx as b_fx, jumpband as b_jb, pin as b_pin, weather as b_wx
    eq(b_pin.PIN_HOURLY, bs.PIN_HOURLY, "PIN_HOURLY")
    eq(b_fx.FX_PAIRS, bs.FX_PAIRS, "FX_PAIRS")
    eq(b_jb.JB_SERIES, bs.JB_SERIES, "JB_SERIES")
    eq(b_wx.WX_VER, bs.WX_VER, "WX_VER")
    eq(b_pin.WX_VER, bs.WX_VER, "pin's WX_VER")
    eq([bots.table("BOTS")], [bs.BOTS], "table()")


def test_plain_words_same_answers():
    """bots.PLAIN gives botstats.plain's answer for every pattern's own example and some strays."""
    samples = ["no_offer", "edge_floor", "tau 12 is past", "price 0.9 is under", "max_cost", "day_stop", "held",
               "per_close", "unfunded_pool", "pool 0 is not 2", "under_one_contract", "no_pool", "stopped", "done",
               "killed", "no_cash", "max_open", "one_per_market", "something new", "close_budget_x", "halted: x"]

    def plain(w):
        for pat, words in bots.PLAIN:
            if re.search(pat, str(w)):
                return words
        return str(w)
    for w in samples:
        eq(plain(w), bs.plain(w), "plain(%r)" % w)


# ---- pinphone's tables ---------------------------------------------------------------------------------------------
def test_pinphone_tables():
    eq_ordered(bots.BOT_CMDS, pp.BOT_CMDS, "BOT_CMDS")
    eq_ordered(bots.BOT_CMD_OF, pp.BOT_CMD_OF, "BOT_CMD_OF")
    eq_ordered(bots.BOT_WORD, pp.BOT_WORD, "BOT_WORD")
    eq(bots.HELP_BOT_LINES, pp.HELP_BOT_LINES, "HELP_BOT_LINES")
    eq_ordered(bots.FUNDS_WHAT, pp.FUNDS_WHAT, "FUNDS_WHAT")
    for n in pp.FUNDS_WHAT:
        if isinstance(pp.FUNDS_WHAT[n], dict):
            eq_ordered(bots.FUNDS_WHAT[n], pp.FUNDS_WHAT[n], "FUNDS_WHAT[%d]" % n)
    eq_ordered(bots.FUNDS_BOTS, pp.FUNDS_BOTS, "FUNDS_BOTS")
    eq_ordered(bots.FUNDS_SIZE_BOTS, pp.FUNDS_SIZE_BOTS, "FUNDS_SIZE_BOTS")
    eq_ordered(bots.FUNDS_SHORT, pp.FUNDS_SHORT, "FUNDS_SHORT")
    eq(bots.FEATURES, pp.FEATURES, "FEATURES")
    eq_ordered(bots.FEATURE_BOT, pp.FEATURE_BOT, "FEATURE_BOT")
    eq(bots.SPEED_OTHERS, pp.SPEED_OTHERS, "SPEED_OTHERS")
    eq(bots.SPEED_SKIPPED, pp.SPEED_SKIPPED, "SPEED_SKIPPED")
    eq(bots.SPEED_LABEL, pp.SPEED_LABEL, "SPEED_LABEL (as a dict; pinphone's literal lists ladder before jumpband)")
    eq(bots.LADDER_GOAL_PCT, pp.LADDER_GOAL_PCT, "LADDER_GOAL_PCT")
    # every bot named by SPEED_* reads the log its SPEC names
    for b, log, _f, _k in pp.SPEED_OTHERS:
        eq(log, bs.SPEC[b]["log"], "SPEED_OTHERS log of %s" % b)


def _src(mod):
    with open(mod.__file__, encoding="utf-8") as fh:
        return fh.read()


def _func(mod, qual):
    """The ast node of function `qual` ('Phone.text_bot' or 'running') in mod's source."""
    tree = ast.parse(_src(mod))
    parts = qual.split(".")
    nodes = tree.body
    for i, p in enumerate(parts):
        node = next(n for n in nodes if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == p)
        nodes = node.body
    return node


# v-tg-rebuild step 5 (2026-10-30): pinphone now READS these from the registry, so its source holds no literal to compare
# against; the legacy values are frozen here as they stood in pinphone.py at 8a9c5e1 (the golden baseline B0).
LEGACY_TEXT_BOT_FOOTERS = {
    "pin": "More on pin: /stats (win rate vs break-even), /fills (today's orders), /open, /losses, /hedges.",
    "forecaster": "Every bot: /bots.", "ladder": "Every bot: /bots.",
    "weather": "Every bot: /bots.", "fx": "Every bot: /bots · both FX pots' cash: /funds.",
    "jumpband": "Every bot: /bots · its pot (subaccount 3, crypto pool): /funds."}


def test_text_bot_footers():
    """pinphone.Phone.text_bot's footers (8a9c5e1's `more = {...}.get(name)`) == the registry's page_footer, and
    pinphone reads them from the registry."""
    eq_ordered(bots.PAGE_FOOTER, LEGACY_TEXT_BOT_FOOTERS, "text_bot footers")
    eq(pp.PAGE_FOOTER, LEGACY_TEXT_BOT_FOOTERS, "pinphone.PAGE_FOOTER")
    assert "more = PAGE_FOOTER.get(name)" in _src(pp)


def test_units_and_goal_rules():
    """The race counts legs (8a9c5e1's pinphone: unit = "leg" if b["name"] == "race"), the ladder alone shows its goal
    (goal=LADDER_GOAL_PCT if b["name"] == "ladder"); pinphone now asks the registry (_unit_of, _goal_of)."""
    eq({n: u for n, u in bots.UNIT.items() if u != "market"}, {"race": "leg"}, "units")
    eq([b.name for b in bots.all_bots() if b.goal_pct is not None], ["ladder"], "goal_pct bots")
    eq({n: pp._unit_of(n) for n in bots.names()}, {n: ("leg" if n == "race" else "market") for n in bots.names()},
       "pinphone._unit_of")
    eq({n: pp._goal_of(n) for n in bots.names()}, {n: (1.0 if n == "ladder" else None) for n in bots.names()},
       "pinphone._goal_of")


# ---- tgcharts' tables ----------------------------------------------------------------------------------------------
def test_tgcharts_tables():
    eq_ordered(bots.BOT_SHORT, tgc.BOT_SHORT, "BOT_SHORT")
    eq_ordered(bots.BOT_COLOUR, tgc.BOT_COLOUR, "BOT_COLOUR")
    eq(bots.BOT_ORDER, tgc.BOT_ORDER, "BOT_ORDER")
    eq_ordered(bots.CMD_KIND_BOTS, {c: k for c, k in tgc.CMD_KIND.items() if k.startswith("bot:")}, "CMD_KIND bot entries")
    eq_ordered(bots.ACCOUNT_NAME, tgc.ACCOUNT_NAME, "ACCOUNT_NAME")
    eq_ordered(bots.POT_WHAT, tgc.POT_WHAT, "POT_WHAT")
    # a bot's commands are the ones pinphone answers (BOT_CMDS + the race's own) and tgcharts draws for
    for b in bots.all_bots():
        for c in b.commands + b.extra_commands:
            eq(bots.by_command(c), b, "by_command(%s)" % c)
    assert bots.by_command("/status") is None


# ---- owner() ---------------------------------------------------------------------------------------------------------
def _fixture_pairs():
    with open(os.path.join(FIX_RESULTS, "botstats_cache.json"), encoding="utf-8") as fh:
        c = json.load(fh)
    pairs = set()
    for sub, x in (c.get("subs") or {}).items():
        for k, r in (x.get("rows") or {}).items():
            pairs.add((str(sub), str((r or {}).get("ticker") or k.split("|")[0])))
        for p in (x.get("positions") or []):
            if isinstance(p, dict) and p.get("ticker"):
                pairs.add((str(sub), str(p["ticker"])))
    return pairs


def test_owner_fixture_tickers():
    """owner() == botstats.owner on every (sub, ticker) of the golden fixture's botstats cache, each ticker also tried
    in every other sub."""
    if not os.path.exists(os.path.join(FIX_RESULTS, "botstats_cache.json")):
        print("    (skipped: no golden fixture at %s)" % FIXTURE)
        return
    pairs = _fixture_pairs()
    assert len(pairs) > 100, len(pairs)
    tks = sorted(set(t for _s, t in pairs))
    n = 0
    for sub, tk in sorted(pairs):
        eq(bots.owner(tk, sub), bs.owner(tk, sub), "owner(%r, %r)" % (tk, sub))
        n += 1
    for tk in tks:
        for sub in SYNTH_SUBS:
            eq(bots.owner(tk, sub), bs.owner(tk, sub), "owner(%r, %r)" % (tk, sub))
            n += 1
    print("    %d owner() calls on %d fixture tickers (%d in their own sub)" % (n, len(tks), len(pairs)))


def test_owner_synthetic():
    for tk in SYNTH_TICKERS:
        for sub in SYNTH_SUBS:
            eq(bots.owner(tk, sub), bs.owner(tk, sub), "owner(%r, %r)" % (tk, sub))
    eq(bots.owner("KXBNB15M-26OCT301300-00", "3"), "jumpband", "sub 3 coin")
    eq(bots.owner("KXHIGHNY-26OCT30-T60", "3"), "weather", "sub 3 bracket")
    eq(bots.owner("KXCRYPTOLEAD15M-X", "0"), "race", "race")
    eq(bots.owner("KXGOLD15M-X", "4"), "other", "sub 4 non-pair")


def test_bot_subs_cash_pool_fill_sub():
    for n in bs.BOTS + ("other", "nosuch"):
        eq(bots.bot_subs(n), bs.bot_subs(n), "bot_subs(%r)" % n)
    for s in bs.SUBS:
        eq(bots.cash_pool(s), bs.SUB_POOL[s], "cash_pool(%r)" % s)
    for n in bs.BOTS:
        for tk in SYNTH_TICKERS:
            eq(bots.fill_sub(n, tk), bs.fill_sub(n, tk), "fill_sub(%r, %r)" % (n, tk))
        eq(tuple(x.name for x in bots.bots_on(bs.SPEC[n]["sub"]))[:1] != (), True, "bots_on")
    eq(tuple(b.name for b in bots.bots_on("0")), ("pin", "race"), "bots_on('0')")
    eq(tuple(b.name for b in bots.bots_on("3")), ("weather", "jumpband"), "bots_on('3')")


# ---- is_bot -----------------------------------------------------------------------------------------------------------
def _cmdlines():
    out = []
    p = os.path.join(FIXTURE, "procs.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            out += [r[2] for r in json.load(fh) if isinstance(r, list) and len(r) > 2]
    py = r'"C:\Python314\python.exe" -u '
    for b in bots.all_bots():
        for root in (r"C:\kals-repo\research\\", r"C:\kals-repo\research\cleanroom\\", "research/", ""):
            s = root + b.script
            out += [py + s + " --live", py + s, py + s + " --live --dry-run", py + s + " --live --paper-live",
                    py + s + " --paper-live", py + '"' + s + '" --live --subaccount 3', py + "x" + s + " --live",
                    py + s + ".bak --live", py + s + " --dry-run --live", "pythonw " + s + " --live --minutes 9"]
    out += ["", None, "--live", "python -c pass"]
    return out


def test_is_bot_and_is_live():
    cls = _cmdlines()
    assert len(cls) > 200, len(cls)
    hits = 0
    for n in bs.BOTS:
        for cl in cls:
            a, b = bots.is_bot(n, cl), bs.is_bot(n, cl)
            eq(a, b, "is_bot(%r, %r)" % (n, cl))
            hits += a
    assert hits >= 7 * 4, hits


# ---- settings hooks ---------------------------------------------------------------------------------------------------
def _legacy_settings(name, start, cl, sizef):
    """botstats.running's dispatch, verbatim."""
    if name == "pin":
        return bs.settings_pin(start, cl, sizef)
    if name == "race":
        return bs.settings_race(start, cl)
    if name == "weather":
        return bs.settings_weather(start, cl)
    if name == "fx":
        return bs.settings_fx(start)
    if name == "jumpband":
        return bs.settings_jumpband(start)
    return bs.settings_clean(name, start, cl)


def _fixture_starts(name):
    """Start records of bot `name` from the fixture's logs (the newest few), or []."""
    out = []
    if not os.path.isdir(FIX_RESULTS):
        return out
    spec = bs.SPEC[name]
    if "log_glob" in spec:
        import glob
        for p in sorted(glob.glob(os.path.join(FIX_RESULTS, spec["log_glob"])))[-3:]:
            try:
                with open(p, encoding="utf-8") as fh:
                    r = json.loads(fh.readline() or "{}")
                out.append(r)
            except (OSError, ValueError):
                pass
        return out
    p = os.path.join(FIX_RESULTS, spec["log"])
    if os.path.exists(p):
        for pred in (None, lambda r: r.get("live") is not False, lambda r: r.get("live") is True):
            r = bs.last_record(p, ("start",), pred)
            if r:
                out.append(r)
    return out


SYN_STARTS = [
    None, {}, {"kind": "start"},
    {"size": 20, "price_ceiling": 0.98, "tau_max": 25, "early_tau_max": 45, "early_frac": 0.333, "early_min_price": 0.9,
     "hedge_belief": 0.4, "loss_cap": 60, "ladder_series": ["KXBTCD"], "code_sha": "abc"},
    {"early_tau_max": 40, "early_frac": 0.5, "early_max_price": 0.97, "price_ceiling": 0.99},
    {"live_rails": {"stop_on_loss": True}, "argv": ["--max-contracts", "4", "--live-min-price", "0.97",
                                                   "--live-tau-max", "30", "--max-stake", "40"], "version": "v-race40"},
    {"rails": {"scale": 0.25, "per_side": 3, "per_close": 6, "max_commit": 40, "px": [0.97, 0.99], "day_stop": -10,
               "run_stop": -25, "size": 2, "live_levels": [0], "max_live_per_close": 3, "max_contracts": 12},
     "variant": "main", "variant_params": {"a": 1}},
    {"rails": {"contracts": 2, "max_open": 5, "window_s": 10800, "day_stop_frac": 0.2, "kill_after": 10, "max_fills": 40,
               "max_days": 14, "pool": 0}, "trigger": {"drop_c": 10, "hours_left": [2, 8]}, "start_pot": 50,
     "subaccount": 3},
    {"size": 10, "fav": 0.98, "cap": 0.99, "hold_s": 5, "entry_from": 45, "entry_to": 15, "max_per_close": 6,
     "max_held": 70, "day_stop": -10, "t": "x", "pid": 1, "series": ["A"]},
    {"max_contracts": 5, "max_cost": 20, "k": 2, "lo": 0.7, "hi": 0.9, "tau": [10, 60],
     "series": ["KXBNB15M", "KXHYPE15M"], "stop_line": -25, "day_stop": -15, "subaccount": 3},
    {"max_contracts": 5, "lo": 0.7, "hi": 0.9, "k": 2, "tau": [10]},
]
SYN_CLS = [None, "", "python pinrun.py --live --series-size 2 --max-losses 3 --jump-gate --one-full-bet",
           "python pinracearm.py --live --max-contracts 6 --live-max-losses 3 --live-max-legs 2 --live-confirm 4",
           "python forecaster_live.py --live --variant quiet", "python forecaster_live.py --live --variant main"]
SIZEF = [None, {"size": 77.0, "bank": 900.0, "at": "2026-10-11T08:00:00Z"}, {"size": 12, "epoch": 1793366972.7}]


def test_settings_hooks():
    n = 0
    for name in bs.BOTS:
        b = bots.get(name)
        starts = SYN_STARTS + _fixture_starts(name)
        for start in starts:
            for cl in SYN_CLS:
                for sizef in SIZEF:
                    rj = (lambda fn, _s=sizef: _s if fn == "pinrun-live-size.json" else None)
                    eq(b.settings(SettingsIn(start, cl, rj)), _legacy_settings(name, start, cl, sizef),
                       "%s settings(start=%r, cl=%r, sizef=%r)" % (name, start, cl, sizef))
                    n += 1
    print("    %d settings comparisons" % n)


def test_start_and_halt_rules_match_running():
    """botstats.running's per-bot lists == the registry's Logs.start_rule / Records.halt_lifts_next_day.
    v-tg-rebuild step 3 (2026-10-30, lane A): once running() reads those rules FROM the registry its source holds no
    per-bot list to compare; then the registry is checked against the lists running() held at 8a9c5e1 (frozen here) and
    running() must read the registry's rules."""
    src = inspect.getsource(bs.running)
    m = re.search(r'name in \(([^)]*)\):\s*\n\s*start = last_record\(log, \("start",\), lambda r: r.get\("pid"\) == pid\)',
                  src)
    legacy = m is not None
    if legacy:
        pid_bots = tuple(ast.literal_eval("(" + m.group(1) + ",)"))
    else:
        pid_bots = ("forecaster", "ladder", "weather", "fx", "jumpband")       # running() at 8a9c5e1
        for needle in ("logs.start_rule", "records.halt_lifts_next_day", "records.halt_lifts", "HALT_KINDS[name]"):
            assert needle in src, "running() reads neither the legacy rule nor the registry's %s" % needle
    eq(tuple(b.name for b in bots.all_bots() if b.logs.start_rule == "pid_then_live"), pid_bots, "pid start rule")
    eq(tuple(b.name for b in bots.all_bots() if b.logs.start_rule == "first_line"), ("pin",), "first-line start rule")
    eq(tuple(b.name for b in bots.all_bots() if b.logs.glob), ("pin",), "glob logs")
    if legacy:
        assert 'h and name == "jumpband" and h.get("kind") == "day_stop"' in src
    eq({b.name: b.records.halt_lifts_next_day for b in bots.all_bots() if b.records.halt_lifts_next_day},
       {"jumpband": ("day_stop",)}, "halt lifts next day")
    if legacy:
        assert 'HALT_KINDS[name] + ("resume",)' in src
    eq(set(b.records.halt_lifts for b in bots.all_bots()), {("resume",)}, "halt lifts")


# ---- activity hooks -----------------------------------------------------------------------------------------------
def _activity_via(name, since):
    """botstats.activity, driven by the registry's hooks (the loop step 3 lifts into botstats)."""
    b = bots.get(name)
    if b.logs.glob:
        paths = [p for p in bs.pin_logs() if os.path.getmtime(p) >= since]
        if not bs.pin_logs():
            paths = None
    else:
        p = os.path.join(bs.RESULTS, b.logs.path)
        paths = [p] if os.path.exists(p) else None
    out = {"ok": paths is not None, "source": None, "sent": 0, "filled": 0, "contracts_filled": 0.0,
           "not_filled": 0, "refused": 0, "refused_why": {}, "cancelled": 0, "hedges": 0,
           "halts": [], "note": None}
    if paths is None:
        out["note"] = "no log file found"
        return out
    out["source"] = [os.path.basename(p) for p in paths]
    why, st = {}, {"triggers": 0, "filled_tk": set()}
    jb = bots.get("jumpband").halt_why
    for p in paths:
        for r in bs.read_since(p, since) or []:
            k = r.get("kind") or r.get("ev")
            if b.activity:
                b.activity(k, r, out, why, st)
            if k in b.records.halts or k in ("stop_file", "exit"):
                w = r.get("why") or r.get("day_pnl") or r.get("run_pnl") or jb(r) or ""
                if k == "exit" and r.get("stopped") is True and not r.get("why"):
                    w = "stop file, its run %s" % bs.usd(bs._num(r.get("run_pnl")) or 0.0)
                out["halts"].append({"t_et": bs.et_clock(bs._t_of(r)), "what": k, "why": str(w)[:120]})
    out["refused_why"] = dict(sorted(why.items(), key=lambda kv: -kv[1]))
    out["contracts_filled"] = round(out["contracts_filled"], 2)
    if b.activity_note:
        b.activity_note(out, st)
    return out


def _synthetic_records(t0):
    kinds = ["order", "hedge", "refused", "late_refused", "live_order", "live_refused", "placed", "live_fill",
             "dropped", "body_refused", "cancelled", "rail_refused", "trigger", "fill", "cancel", "rejected", "no_cash",
             "max_cost", "order_skip", "halt", "entries_stopped", "pause", "live_halt", "day_stop", "run_stop", "kill",
             "done", "stop_line", "stop_file", "exit", "resume", "start"]
    out = []
    i = 0
    for k in kinds:
        for v in range(3):
            i += 1
            t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0 + 60 * i))
            r = {"t": t, ("ev" if v == 2 else "kind"): k, "filled": [0, 2, 1.5][v], "n": [1, 0, 3][v], "delta": [1, 2, 0][v],
                 "qty": [5, 0, 2][v], "ticker": ["KXBNB15M-26OCT301300-00", "KXHIGHNY-26OCT30-T60", "KXBNB15M-26OCT301300-00"][v],
                 "act": [True, False, True][v]}
            if v == 0:
                r["why"] = ["price 0.91 is under 0.95", "YES on BTC 3 legs"][i % 2] if k == "live_refused" else "max_cost"
                r["gate"] = "edge_floor"
            if v == 1:
                r["status"] = 503
                r["day_money"], r["day"], r["day_stop"] = -15.2, "2026-10-30", -15
                r["line_money"], r["stop_line"] = -26, -25
                r["stopped"], r["run_pnl"] = True, -3.5
            if k == "live_refused" and v == 2:
                r["why"] = ["tau 41 is past 40", "x"]
            out.append(r)
    return out


def test_activity_hooks_synthetic():
    td = tempfile.mkdtemp(prefix="bots-act-")
    old = bs.RESULTS
    try:
        bs.RESULTS = td
        t0 = time.time() - 3 * 3600
        recs = _synthetic_records(t0)
        for b in bots.all_bots():
            p = os.path.join(td, b.logs.path or "pinrun-live-20261030T000000Z.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
        for name in bs.BOTS:
            a = _activity_via(name, t0 - 1)
            eq(a, bs.activity(name, t0 - 1), "activity(%s) on synthetic records" % name)
            assert a["sent"] or a["filled"] or a["cancelled"] or a["hedges"], (name, a)
        for name in bs.BOTS:                                 # a missing log
            os.remove(os.path.join(td, bots.get(name).logs.path or "pinrun-live-20261030T000000Z.jsonl"))
            eq(_activity_via(name, t0), bs.activity(name, t0), "activity(%s) with no log" % name)
    finally:
        bs.RESULTS = old
        shutil.rmtree(td, ignore_errors=True)


def test_activity_hooks_fixture():
    if not os.path.isdir(FIX_RESULTS):
        print("    (skipped: no golden fixture)")
        return
    with open(os.path.join(FIXTURE, "env.json"), encoding="utf-8") as fh:
        T = float(json.load(fh)["T"])
    old = bs.RESULTS
    try:
        bs.RESULTS = FIX_RESULTS
        for name in bs.BOTS:
            for since in (bs.day_start(bs.et_day(T)), T - 3 * 86400):
                eq(_activity_via(name, since), bs.activity(name, since), "activity(%s, %s) on the fixture" % (name, since))
    finally:
        bs.RESULTS = old


# ---- fill_of ----------------------------------------------------------------------------------------------------------
def _fill_of_via(name, r):
    """botstats.fill_of driven by the registry's Records (the rule step 3 lifts into botstats)."""
    if not isinstance(r, dict):
        return None
    b = bots.get(name)
    rec = b.records
    k = r.get("kind") or r.get("ev")
    if k not in rec.fills:
        return None
    hedge = rec.hedge is not None and k == rec.hedge
    if hedge and str(r.get("status")) != "executed":
        return None
    import pinledger
    n = pinledger.money(r, "n" if hedge else rec.fill_qty)
    if n <= 0:
        return None
    tk = r.get("ticker")
    side = str(r.get("side" if hedge else rec.fill_side) or "").lower()
    px = next((bs._num(r.get(f)) for f in ("exec_price", "px", "price") if r.get(f) is not None), None)
    close = None
    if tk:
        try:
            import pinflat
            close = pinflat.close_epoch(tk)
        except Exception:                                       # noqa: BLE001
            close = None
    return {"bot": name, "sub": bots.fill_sub(name, tk), "ticker": tk, "what": bs.describe(tk) if tk else "?",
            "side": rec.fixed_side or (side if side in ("yes", "no") else None),
            "contracts": round(n, 2), "price": px, "t": bs._t_of(r), "close": close, "hedge": hedge,
            "act": rec.act}


def test_fill_of_fields():
    recs = _synthetic_records(time.time() - 3600)
    extra = []
    for r in recs:
        for st in ("executed", "failed"):
            for side, want in (("YES", "no"), ("no", "yes"), ("", None), (None, "maybe")):
                x = dict(r, status=st, side=side, want=want, exec_price=0.97, ticker=r["ticker"])
                extra.append(x)
                extra.append(dict(x, ticker="KXEURUSD15M-26OCT301300-T1.08", px=0.5))
    extra += [None, [], {"kind": "fill"}, {"kind": "fill", "qty": 1, "n": 1, "delta": 1, "filled": 1}]
    n = 0
    for name in bs.BOTS:
        for r in recs + extra:
            eq(_fill_of_via(name, r), bs.fill_of(name, r), "fill_of(%s, %r)" % (name, r))
            n += 1
    print("    %d fill_of comparisons" % n)


# ---- VERSIONS.md ------------------------------------------------------------------------------------------------------
def _version_via(name, lines):
    """botstats.version_of's loop with the ownership rule from the registry (bots.version_claim)."""
    import calendar
    for line in lines:
        m = bs._VER.match(line.rstrip())
        if not m:
            continue
        vname, rest = m.group(1), m.group(2)
        if re.match(r"(INSTALLED|PREPARED)\b", rest.strip()):
            continue
        if re.match(r"(KILLED|STOPPED|REVERTED|DEAD|WITHDRAWN)\b", rest.strip()) or re.match(bs.INFRA_VER, vname):
            continue
        shown = bots.version_claim(name, vname, rest)
        if shown is None:
            continue
        t = None
        mt = bs._VER_T.search(rest)
        if mt:
            day, hh, mm = mt.group(1), mt.group(2), mt.group(3)
            try:
                t = float(calendar.timegm(time.strptime(
                    "%sT%s:%s" % (day, hh or "00", (mm or "00").lower().replace("x", "0")), "%Y-%m-%dT%H:%M")))
            except ValueError:
                t = None
        return shown, t, rest.strip()
    return None


SYN_HEADINGS = [
    "# v-race40 + v-forecaster-scale + v-ladder-size + v-crash-guard -- 2026-10-01 04:10Z combined",
    "# v-reopen98 + v-floor90 -- 2026-09-30 12:00Z pin pair",
    "# v-reopen98 + v-penny-thing -- 2026-09-30 12:00Z the penny ladder too",
    "# v-a + v-b -- 2026-09-30 cleanroom boot",
    "# v-fx-from45 -- 2026-10-30 14:00Z the FX taker, it shares the coin race pots and the forecaster",
    "# v-fx-hold5 + v-race-x -- 2026-10-26 two bots",
    "# v-jb-stage1 -- 2026-10-30 08:13Z jumpband_live --live, the forecaster's coins",
    "# v-jumpband-live -- 2026-10-30 jump band live",
    "# v-jb1 + v-fxtake2 -- 2026-10-30 both",
    "# v-dipsell-live -- 2026-10-04 15:3xZ weather",
    "# v-dip-sell2 -- 2026-10-05 ~06:0xZ weather approx",
    "# v-ladder-settlefix -- LIVE 2026-09-29 ladder_live fix",
    "# v-ladder7 -- 2026-09-20 hourly ladders for pin",
    "# v-keepalive-cleanroom -- 2026-09-28 forecaster and ladder_live keep-alive",
    "# v-coinrace-tie -- 2026-10-02 coin race tie rule",
    "# v-pinthing -- INSTALLED 2026-10-20 live at the next restart",
    "# v-pinthing2 -- PREPARED 2026-10-20",
    "# v-racev2-live-test -- KILLED 2026-10-23",
    "# v-wrongside2 -- WITHDRAWN 2026-10-29",
    "# v-tg-active -- 2026-10-30 phone",
    "# v-recorder-x -- 2026-10-30 recorder",
    "# v-plain -- 2026-10-30 23:59:59Z pin with seconds",
    "# v-bad -- 2026-13-45 99:99Z a bad date",
    "# v-forecaster-variant + v-dipsell-x -- 2026-10-10 two",
    "# v-penny-ladder -- 2026-09-27 penny ladder rails",
    "# v-bettor -- 2026-09-27 clean-room bettor",
    "# v-x + v-y + v-jumpband-z -- 2026-10-30 three",
    "not a heading", "# v-nodash 2026-10-30",
]


def test_version_rule():
    """Every heading of the fixture's VERSIONS.md and SYN_HEADINGS, alone and all together, gives each bot the same
    answer from the registry's rule as from botstats.version_of."""
    lines = list(SYN_HEADINGS)
    p = os.path.join(FIX_RESULTS, "VERSIONS.md")
    real = []
    if os.path.exists(p):
        with open(p, encoding="utf-8", errors="replace") as fh:
            real = fh.readlines()
    heads = [ln for ln in real if ln.startswith("#")] + lines
    td = tempfile.mkdtemp(prefix="bots-ver-")
    old = bs.RESULTS
    n = 0
    try:
        bs.RESULTS = td
        cases = [[h] for h in heads] + [real, lines + real, real + lines]
        for c in cases:
            with open(os.path.join(td, "VERSIONS.md"), "w", encoding="utf-8") as fh:
                fh.write("".join(x if x.endswith("\n") else x + "\n" for x in c))
            for name in bs.BOTS:
                eq(_version_via(name, c), bs.version_of(name), "version_of(%s) on %r" % (name, c[:1]))
                n += 1
    finally:
        bs.RESULTS = old
        shutil.rmtree(td, ignore_errors=True)
    print("    %d version_of comparisons over %d headings (%d from the fixture)" % (n, len(heads), len(heads) - len(lines)))


# ---- the runner -------------------------------------------------------------------------------------------------------
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
    print("test_registry: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
