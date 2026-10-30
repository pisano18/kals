"""test_funds.py -- /funds /bank /accounts as a command package (research/phone/commands/funds: read.py, page.py).

v-tg-rebuild step 9 (2026-10-30, lane D4). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_funds.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed. KALS_TESTING=1 (the
write fence); Kalshi is a planted fake getter, botstats' active_bots / pot_settlements are planted for the test's
length, the results folder is a temp folder: no network, no process table, no file under results\\ read or written.
"""
import os
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinphone as pp                                                # noqa: E402
import botstats                                                      # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import context as CX                                     # noqa: E402
from phone.html import Html, MAX_LEN, tg_html_problems              # noqa: E402
from phone.commands.funds import page as FP, read as FR              # noqa: E402

T = 1789700000.0            # 2026-09-18 01:33Z (Thu Sep 17, 9:33 PM ET)
TMP = tempfile.mkdtemp(prefix="test_funds_")
pp.LOG = os.path.join(TMP, "pinphone.log")      # tracebacks the failure cases log stay out of the real log


def fake_ledger():
    led = types.SimpleNamespace(results=TMP, hedges=[], settled=[], orders=[])
    led.refresh = lambda: None
    led.bank = lambda: {"bank": 1000.0}
    return led


def phone(**seams):
    ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=fake_ledger(), now_fn=lambda: T,
                  health_fn=lambda: {"alive": True}, procs_fn=lambda: [])
    ph.bs_procs = []
    for k, v in seams.items():
        setattr(ph, k, v)
    return ph


def _R(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0):
    return {"ticker": tk, "settled_time": st, "market_result": res, "value": {"yes": 100, "no": 0}[res],
            "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc, "no_count_fp": "%.2f" % nn,
            "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee, "revenue": 0}


LIST = [{"subaccount_number": 0, "exchange_index": 2, "balance": "500.0000"},
        {"subaccount_number": 0, "exchange_index": 0, "balance": "1.5000"},
        {"subaccount_number": 1, "exchange_index": 2, "balance": "80.2500"},
        {"subaccount_number": 3, "exchange_index": 0, "balance": "0.0000"}]
POS = {0: [{"ticker": "KXBTC15M-26SEP172200-00", "position_fp": "30.00", "market_exposure_dollars": "29.10"},
           {"ticker": "KXETH15M-26SEP172200-00", "position_fp": "0.00", "market_exposure_dollars": "0.00"}]}
STL = {0: [[_R("KXETH15M-26SEP160015-15", "2026-09-16T04:15:03Z", "no", yn=20, yc=19.60, fee=0.02),
            _R("KXCRYPTOLEAD15M-26SEP160930-XRP", "2026-09-16T13:30:20Z", "yes", yn=5, yc=4.85, fee=0.01)],
           [_R("KXBTCD-26SEP1511-T60000", "2026-09-15T15:00:10Z", "yes", yn=2, yc=1.00)]],
       1: [[_R("KXNEAR15M-26SEP160300-00", "2026-09-16T07:00:03Z", "no", nn=5, nc=4.95)]]}


def kalshi(asked, bad=lambda path, q: None):
    """A fake GET-only Kalshi: the subaccount list, each pool's balance, open positions and settlement pages."""
    def get(path, q):
        asked.append((path, dict(q)))
        b = bad(path, q)
        if b == "raise":
            raise OSError("connection reset")
        if b is not None:
            return b
        if path == "/portfolio/subaccounts/balances":
            return 200, {"subaccount_balances": LIST}
        if path == "/portfolio/balance":
            for r in LIST:
                if (r["subaccount_number"], r["exchange_index"]) == (q["subaccount"], q["exchange_index"]):
                    return 200, {"balance_dollars": r["balance"], "balance_breakdown": [
                        {"exchange_index": 2, "balance": "580.2500"}, {"exchange_index": 0, "balance": "1.5000"}]}
            return 404, {"error": "not found"}
        if path == "/portfolio/positions":
            return 200, {"market_positions": POS.get(q["subaccount"], []), "cursor": ""}
        if path == "/portfolio/settlements":
            pg = STL.get(q["subaccount"], [[]])
            i = int(q.get("cursor") or 0)
            return 200, {"settlements": pg[i], "cursor": str(i + 1) if i + 1 < len(pg) else ""}
        return 404, "unknown path"
    return get


class planted:
    """botstats' active_bots / pot_settlements planted for a block (both the old and the new path read them there)."""

    def __init__(self, active=("pin", "race", "ladder"), have=None):
        self.active, self.have = active, have

    def __enter__(self):
        self.saved = botstats.active_bots, botstats.pot_settlements
        botstats.active_bots = lambda procs=None, now=None: list(self.active)
        if self.have == "raise":
            botstats.pot_settlements = lambda now=None, getter=None: 1 / 0
        else:
            botstats.pot_settlements = lambda now=None, getter=None: (dict(self.have or {}), None)
        return self

    def __exit__(self, *exc):
        botstats.active_bots, botstats.pot_settlements = self.saved
        FR._FUNDS_HIST.clear()


def old_and_new(ph, text="/funds"):
    """(old reply, its Kalshi requests, new reply, its Kalshi requests) -- each path with a fresh 60 s settlement memo."""
    a_old, a_new = [], []
    FR._FUNDS_HIST.clear()
    ph.funds_getter = kalshi(a_old, getattr(ph, "_bad", lambda p, q: None))
    old = ph.text_funds()
    FR._FUNDS_HIST.clear()
    ph.funds_getter = kalshi(a_new, getattr(ph, "_bad", lambda p, q: None))
    new = CM.by_name(CX.split_command(text)[1]).run(CX.Ctx.from_phone(ph, text))
    return old, a_old, new, a_new


# ---- the declaration -------------------------------------------------------------------------------------------------
def test_declared_like_help_and_charts():
    import tgcharts
    c = CM.of_module("phone.commands.funds")
    assert len(c) == 1 and c[0].names == ("/funds", "/bank", "/accounts") and c[0].section == "money"
    assert c[0].order == 40 and c[0].help_line in pp._HELP_TPL, "the help line is pinphone.HELP_TEXT's, verbatim"
    for n in c[0].names:
        assert CM.by_name(n) is c[0] and c[0].kind_of(n) == tgcharts.kind_of(n) == "funds", n
    assert not CM.discover()


def test_pinphone_reexports_the_same_objects():
    """pinphone keeps every moved name as the very same object (Phone.text_funds, its self-test and the golden harness
    still say pinphone.<name>; a cache cleared there is the one the module reads)."""
    moved = {FR: ("FUNDS_WHAT FUNDS_BOTS FUNDS_IDLE FUNDS_POOL_NAME FUNDS_SIZE_BOTS _pot_whats funds_what FUNDS_PATHS "
                  "FUNDS_DEADLINE_S FUNDS_POS_PAGES FUNDS_FALLBACK_POOLS _fnum _fint _usd2 _pool_name funds_read "
                  "funds_sizes FUNDS_DAYS FUNDS_SHOW_DAYS FUNDS_HIST_TTL_S FUNDS_HIST_PAGES FUNDS_HIST_DEADLINE_S "
                  "FUNDS_HIST_PATH FUNDS_BOOKS funds_books _FUNDS_HIST funds_book funds_settled funds_hist funds_days"),
             FP: ("_funds_hist_lines funds_text FUNDS_SHORT funds_short funds_idle _funds_day_label _funds_days_html "
                  "_funds_page")}
    for mod, names in moved.items():
        for n in names.split():
            assert getattr(pp, n) is getattr(mod, n), "pinphone.%s is not %s.%s" % (n, mod.__name__, n)
    assert pp.FUNDS_WHAT == pp._bots.FUNDS_WHAT and pp.FUNDS_SIZE_BOTS == pp._bots.FUNDS_SIZE_BOTS
    assert pp.FUNDS_SHORT == pp._bots.FUNDS_SHORT


# ---- the reads ---------------------------------------------------------------------------------------------------------
def test_funds_read_get_only_and_named_failures():
    asked = []
    f = FR.funds_read(kalshi(asked))
    assert sorted(f["subs"]) == [0, 1, 3] and f["list_err"] is None and f["kalshi_cash"] == {2: 580.25, 0: 1.5}
    assert set(p for p, _q in asked) == set(FR.FUNDS_PATHS) and f["asked"] == asked
    assert all("subaccount" in q for p, q in asked if p != FR.FUNDS_PATHS[0])
    assert f["subs"][0]["open"] == 29.10 and f["subs"][0]["open_n"] == 1, "a 0-contract row is no bet"
    assert f["subs"][3]["pools"][0] == {"dollars": 0.0, "from_list": False, "err": None, "listed": 0.0}
    assert not any(p == "/portfolio/balance" and q["subaccount"] == 3 for p, q in asked), "a listed $0 is not re-read"
    f2 = FR.funds_read(kalshi([], lambda p, q: (503, "busy") if p == "/portfolio/balance" and q["subaccount"] == 1
                              else None))
    p1 = f2["subs"][1]["pools"][2]
    assert p1["dollars"] == 80.25 and p1["from_list"] and p1["err"] == "HTTP 503", "the list stands in (unit matched)"
    f3 = FR.funds_read(kalshi([], lambda p, q: "raise" if p == FR.FUNDS_PATHS[0] else None))
    assert f3["list_err"].startswith("error: connection reset") and sorted(f3["subs"]) == sorted(FR.FUNDS_WHAT)


def test_funds_settled_memo_and_days():
    asked, memo = [], {}
    h = FR.funds_settled(kalshi(asked), [0, 1], T, memo=memo)
    assert set(p for p, _q in asked) == {FR.FUNDS_HIST_PATH} and sorted(memo) == [0, 1]
    n0 = len(asked)
    h2 = FR.funds_settled(kalshi(asked), [0, 1], T, clock=lambda: memo[0]["t"] + 1, memo=memo)
    assert len(asked) == n0 and h2[0]["cached"], "a pull inside FUNDS_HIST_TTL_S is not read again"
    d = FR.funds_days(h[0], "2026-09-17", sub=0)
    days = {x["day"]: x for x in d["days"]}
    assert abs(days["2026-09-16"]["all"]["money"] - (-19.62 + 0.14)) < 1e-9 and days["2026-09-16"]["all"]["lost"] == 1
    assert days["2026-09-16"]["race"]["n"] == 1 and days["2026-09-15"]["bot"]["n"] == 1, "hourly BTC = the main bot"
    assert [FR.funds_book(t) for t in ("KXBTC15M-X", "KXCRYPTOLEAD15M-X", "KXBTCD-X", "KXHIGHNY-X")] == \
        ["bot", "race", "bot", "other"]


def test_funds_hist_prefers_botstats_rows():
    asked = []
    with planted(have={"0": STL[0][0]}):
        h = FR.funds_hist(kalshi(asked), [0, 1], T)
    assert h[0]["rows"] == STL[0][0] and h[0]["cached"] and all(q["subaccount"] == 1 for _p, q in asked), \
        "an account botstats holds is not pulled again; the rest are"


# ---- the command against Phone.text_funds ------------------------------------------------------------------------------
def test_command_identical_to_phone():
    for active, have in ((("pin", "race", "ladder"), None), (("pin",), {"0": STL[0][0] + STL[0][1]}),
                         (("pin", "ladder", "jumpband"), "raise")):
        with planted(active, have):
            ph = phone()
            for text in ("/funds", "/bank", "/Accounts@kalsbot"):
                old, a_old, new, a_new = old_and_new(ph, text)
                assert type(new) is type(old) is Html and str(new) == str(old), (active, text)
                assert a_new == a_old, "the same Kalshi requests, in the same order"
                assert len(str(new)) <= MAX_LEN and not tg_html_problems(new)
                assert "ALL ACCOUNTS: $610.85" in str(new), str(new)[:200]


def test_command_failure_wall_identical():
    with planted():
        ph = phone()
        ph._bad = lambda p, q: "raise"
        old, a_old, new, a_new = old_and_new(ph)      # every read failing is a page that says so, not a crash
        assert str(new) == str(old) and a_new == a_old and "COULD NOT READ" in str(new), str(new)[:300]
        ph.funds_getter = None
        boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("botstats is broken"))   # noqa: E731
        saved = botstats.default_getter
        botstats.default_getter = boom
        try:
            old = ph.text_funds()
            new = CM.by_name("/funds").run(CX.Ctx.from_phone(ph, "/funds"))
        finally:
            botstats.default_getter = saved
        assert new == old == ("Could not build /funds: botstats is broken\nEverything else still works -- /bots shows "
                              "each bot pot's cash."), new


def test_page_render_from_data_only():
    """render(data) builds the page from load's data alone: a FakeCtx with planted readers gives the same page as the
    words of the same reads."""
    asked = []
    f = FR.funds_read(kalshi(asked))
    hist = FR.funds_settled(kalshi(asked), [0, 1, 3], T, memo={})
    data = {"f": f, "sizes": {0: ["main bot 77 contracts a bet"]}, "now": T, "hist": hist, "active": ("pin", "ladder")}
    t = CM.by_name("/funds").render(data)
    assert str(t) == str(FP.funds_text(f, data["sizes"], T, hist, active=("pin", "ladder")))
    assert "bet size now: main bot 77 contracts a bet" in str(t) and "Past 7 ET days" in str(t)


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
            print(("  FAIL %s\n%s" % (name, traceback.format_exc())).encode("ascii", "backslashreplace").decode(),
                  flush=True)
    print("test_funds: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
