"""botstats.py -- every live bot's numbers, in ONE place the phone and the desktop both read.

WHY THIS EXISTS. The operator, 2026-09-30: *"Can you make a spot in the bot to see each sub account,
what's running, and as much details about them as possible? Also telegram commands for each sub
account type so I can see everything I can about them like pin. Including day performance, long
performance, everything you can. And are their totals added to the main pages total stats?"*

Five bots trade real money from one Kalshi key, in four separate pots:

    bot         pot (subaccount)   its markets
    pin         0 (main)           the 15-minute coin series (pinday.CRYPTO) + the hourly ladders (KXBTCD...)
    race        0 (main)           KXCRYPTOLEAD / KXCRYPTOCOMP -- the coin race
    forecaster  2                  everything subaccount 2 settled (the 30-minute bettor test before it sent 0 orders)
    ladder      1                  everything subaccount 1 settled
    weather     3 (cash POOL 0)    everything subaccount 3 settled -- the weather dip-seller (sweep/dipsell_live.py,
                                   2026-10-04), daily-high temperature brackets
    fx          5 (pool 2) + 4     the FX taker (research/cleanroom/fxtake_live.py, 2026-10-25): the 8 commodity
                (pool 0)           15-minute series from 5, the 5 currency pairs from 4 (POT_POOL_ONLY)
    jumpband    3 (cash POOL 2)    the jump band (research/cleanroom/jumpband_live.py --live, 2026-10-30): BNB HYPE ZEC
                                   NEAR 15-minute markets. Subaccount 3's POOL 0 history is the weather dip-seller's
                                   (POT_POOL_ONLY / POT_OWNER split the number 3 by pool and by ticker)

**WHAT THE PHONE SHOWS (2026-10-30).** A bot is ACTIVE when its live copy runs (is_bot) and its stop file is absent
(is_active / active_bots); the pin bot always is. Every per-bot place on the phone lists the active bots only; a
paused or retired bot's past money stays in every total and, where a per-bot split must add up, sits on one line,
'earlier bots' (all_bots' `earlier`, shown_parts / shown_by).

**CASH POOLS (2026-10-04).** Kalshi keeps each pot's cash in separate pools (`exchange_index`): crypto
and commodities in pool 2, where pots 0-2 trade; weather in pool 0, where pot 3 trades. A
/portfolio/balance read names the pool and answers that pool only -- subaccount 3 reads $0.00 in pool 2
-- so each pot's cash read uses its OWN pool (`SUB_POOL`). Subaccounts 1 and 2 also exist, empty, in
pool 0; the cash listing is matched on subaccount number, so their pool-0 rows land in their own pots
($0) and never in the weather pot.

**THE ANSWER TO "ARE THEIR TOTALS IN THE MAIN PAGE?"** The main page reads `kalshi_ledger.json`,
which since 2026-09-29 holds subaccount 0 only -- pin + race (+ the old oil bot's rows, shown here as
`other`). The forecaster, the ladder and the weather bot are NOT in it. `all_bots()` is the only total
with all five.

**MONEY COMES FROM KALSHI, PER SUBACCOUNT.** `/portfolio/settlements` with NO subaccount mixes every
pot's rows under the same (ticker, settled_time) key -- the bug fixed in pinledger.py on 2026-09-29 --
so every request here names its subaccount, and the self-test fails if one does not. Per market:
payout on the winning side - both sides' cost - fee (`pinledger.pnl`, which a hedged market needs:
Kalshi reports its revenue as 0). A log number never becomes money here; the logs only say what the
bot DID today (orders sent, filled, refused). A bank difference is never profit (deposits move it).

A market belongs to the ET day of its CLOSE, read from the ticker (`pinday.et_day_of_ticker`), the
same rule pinday and pinledger use, so this cannot disagree with them.

**"Money put in"** is what the contracts cost, both sides (yes cost + no cost). Fees are inside the
money figure, not the put-in. Return = money / put in.

READ ONLY. Kalshi is reached only through a `getter(path, params) -> (status, body)` -- by default
`kauth.get`, which can only send a GET -- and only seven paths are ever asked for: three per pot
(settlements, positions, balance) and four account-wide LISTINGS (the subaccount transfer history,
every pot's cash by pool, deposits, withdrawals -- see "THE POT" below). This file holds no HTTP code
of its own, starts and stops nothing, and writes exactly one file: `results/botstats_cache.json`.
The self-test scans this source for any order, transfer-making or process-control call and fails if
it finds one.

**THE POT -- every money figure as a PERCENTAGE (2026-10-02).** The operator: *"Dollar amounts mean
nothing I don't know the sizes. You need to do percentages of their full bank and return on what they
spent on. 2 is bad if it's got $100 but if it's $10 that's good."* So every window also carries
`pot_pct` = money / the pot:
  - a window (today, yesterday, 7 days, month): what the pot HELD WHEN THE WINDOW BEGAN -- its cash in
    every pool + what its open bets cost -- plus any money moved INTO it during the window (so a pot
    that started empty and was funded mid-window is not divided by zero; a top-up only ever makes the
    % smaller). Worked back from now: pot now - money settled since the window began - money moved in
    since (deposits, withdrawals, subaccount transfers). Cash + open bets moves ONLY by settlements and
    transfers, so this is exact -- checked 2026-10-02 against every pot's whole history: main account
    off by $0.03, both subaccounts to the cent.
  - all time: the money put in -- deposits (after Kalshi's fee) - withdrawals for the whole account;
    for the main account, that less what was moved out to the bot pots; for a subaccount, what was
    moved into it less what came back.
Pin and race share the main account, so both are a % of the same main pot. A pot that cannot be
worked out from ONE consistent read (a failed read, a stale one, history still loading, the two cash
reads disagreeing about the unit) gives `pot_pct: None` with `pot_why` -- never a guess.

**THE CACHE.** Per subaccount: the settlement rows (trimmed to the ten fields the money needs), when
they were last read, and whether the whole history has been walked once. A read is made at most
every REFRESH_S (60 s); after the first full walk it pages backwards from the newest settlement and
stops at the first page it already holds (pinledger.fetch's rule), so the normal cost is one request
per pot. A first walk cut short is RESUMED, never mistaken for the whole history -- until it finishes,
every figure is flagged `complete: False`. The process table (10-12 s to read on this box) is cached
the same way; pass `procs=` to reuse a table the caller already holds (pinphone.python_procs()).

A failed read is reported as a failure, never as $0: money is None with the error, alive is None
("could not tell"), and a total missing a bot says which.

THE LAYOUT (v-tg-rebuild step 7, 2026-10-30). This file is a FACADE: the code is in research/botdata, one module a
concern, and every name callers ever used is still here (the same objects):

    tables    the per-bot tables, derived from the registry (research/bots): SPEC, BOTS, SUB_POOL, ..., owner()
    kalshi    the Kalshi reads and botstats_cache.json (one lock: concurrent callers make one pass; readonly mode)
    money     a settled market, money over windows, the 30-day average day
    pots      the pot every percentage is OF
    procs     the process table          status    which bots run / are shown (fleet, v-tg-active)
    logs      the bots' own logs         activity  what a bot did today, every bot's fills
    versions  VERSIONS.md                running   one bot right now (running, settings, halted, version)
    report    bot(), all_bots()          words     the phone's words (_bot_text, text_summary, ...)

Setting a name here (tests: botstats.RESULTS = <temp dir>; the golden harness: botstats._procs_native = <recorded>)
sets it where the code reads it (the _Botstats module class below). `botstats.py --selftest` runs every
research/botdata/tests/test_*.py; its exit code and last line ('botstats selftest: OK') are the phone's /update gate.
"""
import argparse
import importlib
import json
import os
import sys
import time
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinday                                                    # noqa: E402,F401  (callers read botstats.pinday ...)
import pinledger                                                 # noqa: E402,F401
import pinxfer                                                   # noqa: E402,F401  (... tgcharts reads bs.pinxfer)
from botdata import paths as _paths                              # noqa: E402
from botdata import (activity as _activity, clock as _clock, fmt as _fmt, kalshi as _kalshi,  # noqa: E402
                     logs as _logs, money as _money, pots as _pots, procs as _procs, report as _report,
                     running as _running, status as _status, tables as _tables, versions as _versions,
                     words as _words)

REPO = os.path.dirname(HERE)

# Every name botstats has ever offered, by the botdata module that owns it now (pinphone, tgcharts, pindesk, server_sync,
# the registry's test and the golden harness read these; botdata/tests/test_facade.py checks every one they use).
_OWNED = (
    (_tables, "POOL BOTS SUBS SUB_POOL FX_PAIRS POT_POOL_ONLY POT_OWNER JB_SERIES PIN_HOURLY SPEC SUB_NAME HALT_KINDS "
              "FILL_KINDS bot_subs sub_name owner pot_groups"),
    (_money, "describe market window LONG_DAYS avg_day avg_words windows WINDOW_KEYS window_span"),
    (_kalshi, "CACHE_NAME REFRESH_S PAGE MAX_PAGES POT_PATHS LEDGERS LEDGER_PATHS PATHS LEDGER_PAGES LEDGER_KEEP KEEP "
              "_MEMO LOCK set_readonly is_readonly load cache_path load_cache save_cache default_getter "
              "fetch_settlements fetch_positions fetch_balance fetch_ledgers refresh GOOD_MAX_S _remember_good "
              "pot_settlements cached_pots"),
    (_procs, "PROC_STALE_S _PS _norm_procs procs_for _procs_native read_procs"),
    (_status, "is_bot ALWAYS_SHOWN ACTIVE_TTL_S _ACTIVE stop_set is_active active_from active_bots fleet EARLIER "
              "EARLIER_LABEL shown_parts shown_by shown_name"),
    (_logs, "_BACK _t_of read_since last_record pin_logs"),
    (_activity, "_halt_why activity _jb_why fill_sub fill_of fills_since"),
    (_versions, "VERSIONS_NAME _VER WX_VER _VER_T INFRA_VER version_of"),
    (_running, "_toks opt settings_pin settings_race settings_fx settings_jumpband settings_weather settings_clean "
               "_read_json running"),
    (_pots, "MIN_POT POT_CHECK _int flows xfer_in_pot pot_rows _cash_all_pools _pot_now pot_context _days_of _pv "
            "pot_for attach_pots day_pot pot_check"),
    (_report, "_money_block _earlier_block _open_block _balance_block _bot_from _load _balances bot all_bots"),
    (_words, "PLAIN plain pot_words _wline _pot_note pot_as_of_note _bot_text text_summary shown_cash pot_check_lines"),
)
# the date and money helpers, under botstats' old names (pure functions: re-exported, never forwarded)
_HELPERS = {"_epoch": _clock.utc_epoch, "et_day": _clock.et_day, "day_start": _clock.day_start,
            "shift_day": _clock.shift_day, "day_label": _clock.day_label, "_ampm": _clock.ampm,
            "et_clock": _clock.et_clock, "usd": _fmt.usd, "pct": _fmt.pct, "pot_pct_txt": _fmt.pot_pct_txt,
            "_n": _fmt.plural, "_num": _fmt.num, "_c": _fmt.cents, "_fmt_g": _fmt.fmt_g}

_FORWARD = {}                           # name -> the botdata module a botstats.<name> = ... must reach
for _mod, _names in _OWNED:
    for _name in _names.split():
        globals()[_name] = getattr(_mod, _name)
        _FORWARD[_name] = _mod
globals().update(_HELPERS)
del _mod, _names, _name


class _Botstats(types.ModuleType):
    """botstats as a module object (v-tg-rebuild step 4, extended in step 7, 2026-10-30). Callers SET names here: tests
    point botstats.RESULTS at a temp folder, the golden harness sets botstats._procs_native / read_procs to its recorded
    table, tgcharts' test sets botstats._load, pinphone's sets botstats.bot / all_bots to fail. The code those names
    steer lives in botdata and its modules call each other through module attributes, so a name set here is set on its
    owner too (_FORWARD) and every caller sees it -- as when this was one file. RESULTS is a property over
    botdata.paths (read and set)."""

    @property
    def RESULTS(self):
        return _paths.RESULTS

    @RESULTS.setter
    def RESULTS(self, value):
        _paths.set_results(value)

    def __setattr__(self, name, value):
        owner = _FORWARD.get(name)
        if owner is not None:
            setattr(owner, name, value)
        types.ModuleType.__setattr__(self, name, value)


sys.modules[__name__].__class__ = _Botstats


# ---- self-test: every botdata test (v-tg-rebuild step 7) ---------------------------------------------------------------
def selftest():
    """Run every research/botdata/tests/test_*.py (the old one-piece self-test, split by module, plus the new modules'
    tests) in this process. Prints each check; exits non-zero on the first failing FILE's end with 'botstats selftest:
    FAILED -- <what>', else the last line is 'botstats selftest: OK' (the phone's /update gate reads both)."""
    os.environ["KALS_TESTING"] = "1"            # botdata/paths.py's write fence: a test never writes a live file
    tdir = os.path.join(HERE, "botdata", "tests")
    if tdir not in sys.path:
        sys.path.insert(0, tdir)
    failed = []
    t0 = time.time()
    for fn in sorted(os.listdir(tdir)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        name = fn[:-3]
        print("-- %s" % name, flush=True)
        try:
            mod = importlib.import_module(name)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s would not import\n%s" % (name, traceback.format_exc()), flush=True)
            continue
        for tname, fnc in list(vars(mod).items()):
            if not (tname.startswith("test_") and callable(fnc)):
                continue
            try:
                fnc()
                print("  ok   %s.%s" % (name, tname), flush=True)
            except BaseException as e:                          # noqa: BLE001  (a test's SystemExit is a failure too)
                if isinstance(e, KeyboardInterrupt):
                    raise
                failed.append("%s.%s" % (name, tname))
                print("  FAIL %s.%s\n%s" % (name, tname, traceback.format_exc()), flush=True)
    print("botstats selftest: %d failed (%.1f s)" % (len(failed), time.time() - t0), flush=True)
    if failed:
        raise SystemExit("botstats selftest: FAILED -- " + ", ".join(failed))
    print("botstats selftest: OK")


def main():
    ap = argparse.ArgumentParser(description="every live bot's numbers, from Kalshi (read only)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bot", default="all", choices=("all",) + BOTS)
    ap.add_argument("--json", action="store_true", help="print the dict instead of the phone text")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    if a.json:
        d = all_bots() if a.bot == "all" else bot(a.bot)
        print(json.dumps(d, indent=1, default=str))
    else:
        print(text_summary(a.bot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
