"""_dlane.py -- what lanes D1 / D2's command tests share (test_botcards, test_bots_page, test_bot_page, test_open_bets,
test_fills, test_losses, test_status, test_day, test_days): a planted Ledger, a Phone around it, patches that put
botstats / tgcharts / the clock-free helpers back, and old-vs-new: the OLD Phone method and the NEW command module on
the same planted world must give the same reply (type and bytes). Not a test file itself (no test_ prefix).

v-tg-rebuild step 9, lanes D1 + D2 (2026-10-30). The golden shadow (research\\golden\\shadow.py) proves the modules on the
server's real data in 8 worlds; these tests cover what those worlds never reach (botstats failing, the forecaster and
weather pages while they are paused there, /losses' shrink-to-fit loop ...). KALS_TESTING=1; no network, no real process
table, nothing under results\\ read or written (a temp folder stands in; the log goes there too).
"""
import contextlib
import io
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

import botstats                                                      # noqa: E402
import pindesk                                                       # noqa: E402
import pinphone as pp                                                # noqa: E402
import tgcharts                                                      # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import context as CX                                     # noqa: E402
from phone.html import Html                                          # noqa: E402

T = 1793448000.0            # 2026-10-31 12:00Z (8:00 AM ET)
DAY = pindesk.et_day(T)
TMP = tempfile.mkdtemp(prefix="test_dlane_")
pp.LOG = os.path.join(TMP, "pinphone.log")       # every log() line of these tests (phone.log asks pinphone's LOG)


def _no_kalshi(*a, **k):
    raise RuntimeError("tests: no Kalshi (a botstats read was not planted)")


# a read a test forgot to plant fails (Kalshi) or reads as unreadable (the process table): never kauth, a key, or this
# machine's processes
import botdata.kalshi as _bk                                         # noqa: E402
import botdata.procs as _bp                                          # noqa: E402
_bk.default_getter = botstats.default_getter = _no_kalshi
for _name in ("native_rows", "wmi_rows", "read_all"):
    if hasattr(_bp, _name):
        setattr(_bp, _name, lambda *a, **k: None)

HEALTH = {"alive": False, "pid": None, "quiet_s": None, "flag": False, "open": {}, "watchdog_s": 30,
          "kalshi_ok": True, "feeds_ok": True, "disk_gb": 42.5, "checked": "Checked just now"}


def settled_row(t, pnl, tk="KXBTC15M-26OCT301045-45", close=None, want="yes"):
    return {"t": t, "close": close if close is not None else t, "pnl": pnl, "tk": tk, "want": want}


def order_row(t, filled, asked=5.0, tk="KXETH15M-26OCT301045-45", price=0.97, tau=12):
    return {"t": t, "close": t + 60, "filled": filled, "asked": asked, "tk": tk, "price": price, "tau": tau}


SETTLED = [settled_row(T - 3600 * h, p, close=T - 3600 * h) for h, p in
           ((1, 1.2), (2, -4.5), (3, 0.8), (5, 2.0), (26, -1.0), (27, 0.6), (50, 3.3))]
ORDERS = [order_row(T - 600 * k, f) for k, f in ((1, 5.0), (2, 0.0), (3, 2.5), (4, 0.0))]


def fake_ledger(settled=(), orders=(), bank=None, bank_at=1000.0, deposited=900.0):
    """A Ledger stand-in: the real Ledger's own methods over planted rows (settled_on, fills_on, days, losing_closes),
    planted bank figures, and a results folder with no file in it."""
    led = types.SimpleNamespace(results=TMP, hedges=[], settled=list(settled), orders=list(orders), newest_rows=[])
    for name in ("settled_on", "fills_on", "days", "losing_closes"):
        setattr(led, name, types.MethodType(getattr(pindesk.Ledger, name), led))
    led.bank = lambda: bank
    led.deposited = lambda: deposited
    led.bank_at = lambda t: bank_at
    led.contracts_for = lambda tk: 5
    led.hedge_outcomes = lambda: []
    led.refresh = lambda: None
    return led


def phone(led=None, health=None):
    ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=led or fake_ledger(), now_fn=lambda: T,
                  health_fn=lambda: dict(health or HEALTH), procs_fn=lambda: [], versions_path=os.path.join(TMP, "none.md"))
    return ph


@contextlib.contextmanager
def patched(*triples):
    """patched((module, name, value), ...): set, then put every one back."""
    saved = [(m, n, getattr(m, n)) for m, n, _v in triples]
    try:
        for m, n, v in triples:
            setattr(m, n, v)
        yield
    finally:
        for m, n, v in reversed(saved):
            setattr(m, n, v)


@contextlib.contextmanager
def quiet():
    """The planted failures' logged tracebacks off the console (they still go to the temp log)."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def boom(*a, **k):
    raise RuntimeError("planted failure")


def new_reply(module, ph, text):
    """The NEW path for `text` on phone `ph`: the module's Command for that name, run on Ctx.from_phone."""
    _t, cmd, _a = CX.split_command(text)
    com = next(c for c in CM.of_module(module) if cmd in c.names)
    return com.run(CX.Ctx.from_phone(ph, text))


def same(old, new, what=""):
    assert type(old) is type(new), "%s: type %s vs %s" % (what, type(old).__name__, type(new).__name__)
    assert str(old) == str(new), "%s: the replies differ\n--- old\n%s\n--- new\n%s" % (what, old, new)


def chart_and_help(module):
    """Every name's chart kind is tgcharts.kind_of's; a help line is /help's own line, verbatim."""
    for c in CM.of_module(module):
        for n in c.names:
            assert c.kind_of(n) == tgcharts.kind_of(n), (n, c.kind_of(n), tgcharts.kind_of(n))
        if c.help_line is not None:
            assert c.help_line in pp.HELP_TEXT.split("\n"), c.help_line


def run(g, name):
    """The plain runner: every test_* in g; exit code 1 when one failed."""
    tests = [(k, v) for k, v in g.items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for k, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % k, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(k)
            print("  FAIL %s\n%s" % (k, traceback.format_exc()), flush=True)
    print("%s: %d passed, %d failed (%.1f s)" % (name, passed, len(failed), time.time() - t0))
    return 1 if failed else 0


__all__ = ["CM", "CX", "Html", "botstats", "pindesk", "pp", "tgcharts", "T", "DAY", "TMP", "HEALTH", "SETTLED", "ORDERS",
           "settled_row", "order_row", "fake_ledger", "phone", "patched", "quiet", "boom", "new_reply", "same", "chart_and_help",
           "run"]
