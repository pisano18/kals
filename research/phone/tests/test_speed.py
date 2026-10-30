"""test_speed.py -- /speed as a command module (research/phone/commands/speed.py).

v-tg-rebuild step 9 (2026-10-30, lane D5). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_speed.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed. KALS_TESTING=1 (the
write fence); the bots' logs are written to a temp folder, botstats.active_bots is planted for the test's length: no
network, no process table, no file under results\\ read or written.
"""
import json
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
from phone.html import Html, tg_html_problems                       # noqa: E402
from phone.commands import speed as SP                               # noqa: E402

SV = SP.SERVER_SINCE_EPOCH
T = SV + 3 * 86400                                   # the phone's clock: 3 days after the move
TMP = tempfile.mkdtemp(prefix="test_speed_")
pp.LOG = os.path.join(TMP, "pinphone.log")
SRVF, HOMEF = "pinrun-live-20261027T042114Z.jsonl", "pinrun-live-20261018T110121Z.jsonl"


def _iso(e):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e))


def _po(dt, tk, asked, got, ms, f=HOMEF):
    return {"t": SV + dt, "tk": tk, "filled": got, "asked": asked, "latency_ms": ms, "file": f}


def _wj(name, rows, mtime):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    os.utime(p, (mtime, mtime))


ORDERS = [_po(-13 * 86400, "H4", 10, 10, 70), _po(-5 * 86400, "H3", 20, 10, 45), _po(-3 * 86400, "H2", 10, 0, 50),
          _po(-1, "H1", 10, 10, 40), dict(_po(-2, "CMD", 10, 0, 999), file="cmdlive-20260917T000000Z.jsonl"),
          _po(0, "KXA15M-X", 10, 10, 15, SRVF), _po(120, "KXB15M-X", 10, 5, 12, SRVF), _po(180, "KXC15M-X", 20, 20, 18, SRVF)]
_wj(SRVF, [{"kind": "settled", "t": _iso(SV + 900), "ticker": "KXA15M-X", "pnl_c": 20.0},
           {"kind": "settled", "t": _iso(SV + 900), "ticker": "KXB15M-X", "pnl_c": 10.0},
           {"kind": "settled", "t": _iso(SV + 915), "ticker": "KXB15M-X", "pnl_c": -5.0}], SV + 3600)
_wj("fxtake-live-orders.jsonl", [
    {"t": _iso(SV - 2 * 86400), "kind": "placed", "status": 201, "filled": 10.0, "rtt": 0.140,
     "body": {"ticker": "KXGOLD15M-X", "count": "10.00"}},
    {"t": _iso(SV - 86400), "kind": "placed", "status": 404, "filled": 0.0, "rtt": 0.142,
     "body": {"ticker": "KXEURUSD15M-X", "count": "10.00"}},
    {"t": _iso(SV + 600), "kind": "placed", "status": 201, "filled": 10.0, "rtt": 0.015,
     "body": {"ticker": "KXGOLD15M-Y", "count": "10.00"}}], SV + 600)


def fake_ledger(orders=ORDERS, bank=1000.0):
    led = types.SimpleNamespace(results=TMP, hedges=[], settled=[], orders=list(orders))
    led.refresh = lambda: None
    led.bank = lambda: {"bank": bank} if bank is not None else None
    return led


def phone(led=None):
    ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=led or fake_ledger(), now_fn=lambda: T,
                  health_fn=lambda: {"alive": True}, procs_fn=lambda: [])
    ph.bs_procs = []
    return ph


class active:
    def __init__(self, bots):
        self.bots = bots

    def __enter__(self):
        self.saved = botstats.active_bots
        botstats.active_bots = lambda procs=None, now=None: list(self.bots)

    def __exit__(self, *exc):
        botstats.active_bots = self.saved


def test_declared_like_help():
    import tgcharts
    c = CM.of_module("phone.commands.speed")
    assert len(c) == 1 and c[0].names == ("/speed",) and (c[0].section, c[0].order) == ("server", 10)
    assert c[0].help_line in pp._HELP_TPL and c[0].kind_of("/speed") is None is tgcharts.kind_of("/speed")


def test_pinphone_reexports_the_same_objects():
    for n in ("SERVER_SINCE SERVER_SINCE_EPOCH SPEED_HOME_DAYS SPEED_MIN_ORDERS SPEED_MIN_OTHER SPEED_OTHERS "
              "SPEED_SKIPPED SPEED_LABEL _et_at _span_words _gb _ms _usd4 _pct0 _TAILS tail_rows _median _rank "
              "_speed_win pin_speed_orders speed_stats _other_order speed_pin_money speed_estimate speed_gather "
              "_speed_other_line speed_html").split():
        assert getattr(pp, n) is getattr(SP, n), n
    for n in ("dot", "pct_of", "pct1", "ret", "_of100"):        # copied verbatim: the same answers as pinphone's
        for args in ((None,), (0.0,), (0.0041,), (-0.2,), (3, 7), (7, 7), (0, 7), (1, 0), (2.5, 100.0), (2.5, None)):
            try:
                want = getattr(pp, n)(*args)
            except TypeError:
                continue
            assert getattr(SP, n)(*args) == want, (n, args)


def test_speed_gather_numbers():
    SP._TAILS.clear()
    d = SP.speed_gather(TMP, ORDERS, T)
    h, s, mo = d["pin"]["home"], d["pin"]["server"], d["pin"]["money"]
    assert (h["n"], h["zero"], h["got"], h["asked"]) == (4, 1, 30, 50) and h["med_ms"] == 47.5
    assert (s["n"], s["zero"], s["got"], s["asked"]) == (3, 0, 35, 40) and s["med_ms"] == 15
    assert abs(mo["usd"] - 0.25) < 1e-9 and mo["contracts"] == 15 and mo["open_contracts"] == 20
    fx = next(x for x in d["others"] if x["bot"] == "fx")
    assert fx["home"]["n"] == 1 and fx["server"]["n"] == 1 and fx["has_ms"], "a 404 is no race"


def test_command_identical_to_phone():
    for bots in (("pin", "race", "fx", "forecaster", "ladder"), ("pin",), ("pin", "fx")):
        for led in (fake_ledger(), fake_ledger([], None), fake_ledger(ORDERS[:3], 0.0)):
            with active(bots):
                ph = phone(led)
                SP._TAILS.clear()
                old = ph.text_speed()
                SP._TAILS.clear()
                new = CM.by_name("/speed").run(CX.Ctx.from_phone(ph, "/Speed@kalsbot"))
            assert type(new) is type(old) is Html and str(new) == str(old), (bots, str(new)[:200])
            assert not tg_html_problems(new)


def test_command_failure_wall_identical():
    led = fake_ledger()
    led.bank = lambda: 1 / 0
    with active(("pin",)):
        ph = phone(led)
        old = ph.text_speed()
        new = CM.by_name("/speed").run(CX.Ctx.from_phone(ph, "/speed"))
    assert new == old == ("Could not build /speed: division by zero\nEverything else still works -- /fills has "
                          "today's pin orders."), new


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
    print("test_speed: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
