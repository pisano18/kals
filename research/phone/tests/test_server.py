"""test_server.py -- /server as a command package (research/phone/commands/server: machine.py, aws.py, page.py).

v-tg-rebuild step 9 (2026-10-30, lane D5). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_server.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed. KALS_TESTING=1 (the
write fence); every reading is planted (the machine, the Kalshi ping, botstats' pots, the AWS http function) and
botstats.active_bots for the test's length: no network, no AWS, no process table, no file under results\\.
"""
import calendar
import json
import os
import re
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

from _legacy import pp, NEW                                         # noqa: E402  (pp: pinphone_legacy + NEW)
import botstats                                                      # noqa: E402
from botdata import paths as _paths                                  # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import context as CX                                     # noqa: E402
from phone.html import Html, tg_html_problems                       # noqa: E402
from phone.commands.server import aws as AW, machine as MA, page as PG, worth as WO   # noqa: E402
from phone.commands import speed as SP                               # noqa: E402

SV = SP.SERVER_SINCE_EPOCH
T = SV + 3 * 86400
TMP = tempfile.mkdtemp(prefix="test_server_")
WTMP = tempfile.mkdtemp(prefix="test_server_worth_")               # the worth-of-the-move world's pin logs (11-05)
# 2026-11-08: the page's log-rotation line (phone/rotation.py -> log_rotate.health) reads botdata.paths.RESULTS at call
# time. Left at the default, it read the SERVER's real results\log_rotate_installed.json the moment the rotation was
# installed there, the page grew a line the frozen legacy page has not, and the three "identical" tests failed on the
# server alone: the phone's /update gate refused the new code. This world has no file under results\ -- so RESULTS
# points at this test's own empty folder for the whole run.
_paths.set_results(TMP)
H0 = SV - SP.SPEED_HOME_DAYS * 86400
THU = calendar.timegm((2026, 10, 22, 7, 0, 0))                     # a Thursday 07:00Z inside the home window
pp.LOG = os.path.join(TMP, "pinphone.log")
HELPS = ("/server help", "/server ?", "/Server@kalsbot AWS", "/server  setup ", "/server Help")

MACH = {"host": "EC2AMAZ-TEST", "ncpu": 2, "cpu": 23.4, "py_cpu": 18.2, "py_n": 14, "py_mem": 1.6e9,
        "mem_total": 4.0e9, "mem_avail": 1.1e9, "mem_load": 72, "commit": 3.1e9, "commit_limit": 5.2e9,
        "disk_free": 31.2e9, "disk_total": 53.7e9, "uptime_s": 6120.0, "reboot": False, "reboot_why": None,
        "sample_s": 0.5, "errs": []}
PING = {"ms": [4.1, 5.2, 6.3], "dns_ms": 1.2, "ip": "1.2.3.4", "err": None, "t": T}
POTS = {"pots": {"0": {"value": 1246.86, "open": 12.30, "cash": 1234.56, "why": None, "t": T - 600},
                 "1": {"value": 683.54, "open": 0, "cash": 683.54, "why": None, "t": T - 600},
                 "2": {"value": None, "open": None, "cash": 129.49, "why": "the last cash read failed", "t": T - 600}},
        "total": 1930.40, "t": T - 600}
ORDERS = [{"t": SV - 86400, "tk": "H1", "filled": 10, "asked": 10, "latency_ms": 48, "file": "pinrun-live-a.jsonl"},
          {"t": SV + 60, "tk": "S1", "filled": 0, "asked": 10, "latency_ms": 15, "file": "pinrun-live-b.jsonl"},
          {"t": SV + 120, "tk": "S2", "filled": 10, "asked": 10, "latency_ms": 12, "file": "pinrun-live-b.jsonl"}]


def _iso(e):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e))


def aws_world(calls, role=True):
    """A fake metadata service + Budgets + Cost Explorer (Phone.aws_http's shape). role=False: no IAM role yet."""
    def http(method, url, headers=None, body=None, timeout=None):
        calls.append((method, url, body))
        headers = headers or {}
        if url == AW.AWS_IMDS + "/latest/api/token":
            return 200, b"TOKEN123"
        if url == AW.AWS_IMDS + "/latest/meta-data/iam/security-credentials/":
            return (200, b"kals-server-billing") if role else (404, b"")
        if url == AW.AWS_IMDS + "/latest/meta-data/iam/security-credentials/kals-server-billing":
            return 200, json.dumps({"Code": "Success", "AccessKeyId": "ASIATEST", "SecretAccessKey": "SECRETTEST",
                                    "Token": "SESSIONTOKEN", "Expiration": _iso(T + 6 * 3600)}).encode()
        if url == AW.AWS_IMDS + "/latest/dynamic/instance-identity/document":
            return 200, json.dumps({"accountId": "001634075101"}).encode()
        tgt = headers.get("x-amz-target")
        if tgt == "AWSBudgetServiceGateway.DescribeBudgets":
            return 200, json.dumps({"Budgets": [{
                "BudgetName": "kals-monthly", "BudgetType": "COST", "TimeUnit": "MONTHLY",
                "BudgetLimit": {"Amount": "120.0", "Unit": "USD"},
                "CalculatedSpend": {"ActualSpend": {"Amount": "1.234"}, "ForecastedSpend": {"Amount": "8.4"}},
                "LastUpdatedTime": T - 7200}]}).encode()
        if tgt == "AWSInsightsIndexService.GetCostAndUsage":
            return 403, json.dumps({"__type": "AccessDeniedException", "Message": "not enabled"}).encode()
        return 404, b"{}"
    return http


def phone(led=None, **seams):
    if led is None:
        led = types.SimpleNamespace(results=TMP, hedges=[], settled=[], orders=list(ORDERS))
        led.refresh = lambda: None
        led.bank = lambda: {"bank": 1000.0}
    ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=led, now_fn=lambda: T,
                  health_fn=lambda: {"alive": True}, procs_fn=lambda: [])
    ph.bs_procs = []
    ph.machine_fn = lambda: dict(MACH)
    ph.ping_fn = lambda: dict(PING)
    ph.pots_fn = lambda: POTS
    for k, v in seams.items():
        setattr(ph, k, v)
    return ph


class active:
    def __init__(self, bots):
        self.bots = bots

    def __enter__(self):
        self.saved = botstats.active_bots
        botstats.active_bots = lambda procs=None, now=None: list(self.bots)

    def __exit__(self, *exc):
        botstats.active_bots = self.saved
        AW._AWS.clear()


def old_and_new(ph, text="/server", role=True):
    c_old, c_new = [], []
    AW._AWS.clear()
    ph.aws_http = aws_world(c_old, role)
    old = ph.text_server(CX.split_command(text)[2])
    AW._AWS.clear()
    ph.aws_http = aws_world(c_new, role)
    new = CM.by_name("/server").run(CX.Ctx.from_phone(ph, text))
    return old, c_old, new, c_new


WORTH_HEAD, MACHINE_HEAD = "🏆 <b>Worth of the move", "⚙️ <b>Machine</b>"


def without_worth(s):
    """The new page minus its worth-of-the-move section (11-05): what the frozen legacy page must still equal."""
    a, b = s.find(WORTH_HEAD), s.find(MACHINE_HEAD)
    assert 0 <= a < b, "the worth section sits between the header and the machine block: %r" % s[:400]
    return s[:a] + s[b:]


# ---- the declaration -------------------------------------------------------------------------------------------------
def test_declared_like_help():
    import tgcharts
    c = CM.of_module("phone.commands.server")
    assert len(c) == 1 and c[0].names == ("/server",) and (c[0].section, c[0].order) == ("server", 20)
    assert c[0].help_line in pp._HELP_TPL and c[0].kind_of("/server") is None is tgcharts.kind_of("/server")
    assert c[0].examples == ("/server help", "/server ?", "/server aws", "/server setup")


def test_pinphone_reexports_the_same_objects():
    moved = {AW: [n for n in vars(AW) if n.startswith("AWS_")] + "sigv4_sign _aws_http _AWS aws_role_creds _aws_call "
             "_aws_budget_rows _aws_ce_rows _aws_cached aws_cost aws_estimate".split(),
             MA: "KALSHI_HOST KALSHI_PING_TTL_S KALSHI_PING_TRIES _W32 _w32 _ft _python_handles REBOOT_KEYS "
                 "reboot_pending machine_read _PING kalshi_connect kalshi_ping".split(),
             PG: "SERVER_WARN_CPU SERVER_WARN_MEM SERVER_WARN_DISK_GB SERVER_HELP _server_pots_lines _server_aws_lines "
                 "server_html".split()}
    for mod, names in moved.items():
        assert len(names) > 6
        for n in names:
            assert getattr(pp, n) is getattr(mod, n), "pinphone.%s is not %s.%s" % (n, mod.__name__, n)


def test_only_aws_has_urllib():
    d = os.path.join(RESEARCH, "phone", "commands")
    for f in ("machine.py", "page.py", "__init__.py", "worth.py"):
        with open(os.path.join(d, "server", f), encoding="utf-8") as fh:
            assert not re.search(r"^\s*(import|from)\s+urllib", fh.read(), re.M), f
    with open(os.path.join(d, "server", "aws.py"), encoding="utf-8") as fh:
        assert "urllib.request" in fh.read()


# ---- /server help ------------------------------------------------------------------------------------------------------
def test_help_variants_read_nothing():
    boom = lambda: 1 / 0                                                  # noqa: E731
    ph = phone(machine_fn=boom, ping_fn=boom, pots_fn=boom, aws_http=lambda *a, **k: 1 / 0)
    for text in HELPS:
        new = CM.by_name("/server").run(CX.Ctx.from_phone(ph, text))
        assert new is PG.SERVER_HELP is ph.text_server(CX.split_command(text)[2]), text
    assert CM.by_name("/server").load(CX.FakeCtx(text="/server ?")) is None, "help: no reading at all"


# ---- the command against Phone.text_server -----------------------------------------------------------------------------
def test_command_identical_to_phone():
    for bots in (("pin", "race", "ladder", "fx", "jumpband"), ("pin",), ("pin", "jumpband")):
        for role in (True, False):
            with active(bots):
                ph = phone()
                old, c_old, new, c_new = old_and_new(ph, "/Server@kalsbot", role)
            assert type(new) is type(old) is Html and without_worth(str(new)) == str(old), (bots, role, str(new)[:300])
            assert [c[:2] for c in c_new] == [c[:2] for c in c_old] and c_new, "the same AWS calls, in the same order"
            assert not tg_html_problems(new)
            assert ("This month so far: <b>$1.23</b>" in str(new)) is role, str(new)
            assert ("Cost Explorer read: AccessDeniedException (HTTP 403): not enabled" in str(new)) is role
            # the fixture's two server orders are under the bar and no pin market has settled: the section says so
            assert "🏆 <b>Worth of the move: too early to tell</b> (2 pin orders on the server, 3 days 0 h; none of the " \
                   "server's filled pin markets has settled yet)" in str(new), str(new)


def test_pots_failure_is_named_on_the_page():
    def bad():
        raise OSError("cache locked")
    with active(("pin",)):
        ph = phone(pots_fn=bad)
        old, _a, new, _b = old_and_new(ph)
    assert without_worth(str(new)) == str(old) and "botstats' cache could not be read (cache locked)" in str(new)


# ---- the worth of the move (11-05) --------------------------------------------------------------------------------------
def _wj(name, rows, mtime):
    p = os.path.join(WTMP, name)
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    os.utime(p, (mtime, mtime))


def worth_world():
    """Pin logs in WTMP. Home (the laptop's last 14 days): a close_summary row every 15 min from H0 to SV except one
    2-hour hole (8 closes) and Kalshi's Thursday maintenance (135 min from THU), 3 conn_events. Server: a row every
    15 min from SV to T, 1 conn_event, 60 settled markets at $0.20 each. Orders: 20 at home (7 of 10 filled), 60 on the
    server (8 of 10 filled, 480 of 600 contracts). Returns the Ledger's order rows."""
    hole0 = H0 + 3 * 86400
    rows = []
    t = H0 + 300
    while t < SV:
        if not (hole0 <= t < hole0 + 8 * 900) and not (THU <= t < THU + 135 * 60):
            rows.append({"kind": "close_summary", "t": _iso(t), "close": t})
        t += 900
    rows += [{"kind": "conn_event", "t": _iso(H0 + 86400 * (k + 1)), "event": "stale_replaced"} for k in range(3)]
    _wj("pinrun-live-20261013T000000Z.jsonl", rows, SV - 60)
    rows = []
    t = SV + 300
    while t < T:
        rows.append({"kind": "close_summary", "t": _iso(t), "close": t})
        t += 900
    rows.append({"kind": "conn_event", "t": _iso(SV + 3600), "event": "read_retry"})
    rows += [{"kind": "settled", "t": _iso(SV + 1000 + i * 900), "ticker": "S%d" % i, "pnl_c": 20.0} for i in range(60)]
    _wj("pinrun-live-20261027T042114Z.jsonl", rows, T)
    orders = [{"t": H0 + 3600 * (i + 1), "tk": "H%d" % i, "filled": 7, "asked": 10, "latency_ms": 45,
               "file": "pinrun-live-a.jsonl"} for i in range(20)]
    orders += [{"t": SV + 900 * (i + 1), "tk": "S%d" % i, "filled": 8, "asked": 10, "latency_ms": 13,
                "file": "pinrun-live-b.jsonl"} for i in range(60)]
    return orders


def worth_ledger(orders, bank=1000.0):
    led = types.SimpleNamespace(results=WTMP, hedges=[], settled=[], orders=list(orders))
    led.refresh = lambda: None
    led.bank = lambda: {"bank": bank}
    return led


def test_maintenance_rule():
    assert WO.is_maintenance(THU - 600, 9000), "a Thursday gap from 06:50Z lasting 2 h 30 min is Kalshi's"
    assert not WO.is_maintenance(THU + 86400 - 600, 9000), "the same gap on a Friday is a stop"
    assert not WO.is_maintenance(THU - 600, 4 * 3600), "a Thursday gap of 4 hours is a stop"
    assert not WO.is_maintenance(THU + 2 * 3600, 9000), "a Thursday gap from 09:00Z is a stop"
    # the window follows the Eastern clock: after the clocks went back (11-01) the pause starts at 08:00Z
    est_thu = calendar.timegm((2026, 11, 5, 8, 0, 0))
    assert WO.is_maintenance(est_thu, 8100), "Thu 11-05 08:00Z = 3:00 AM EST is Kalshi's"
    assert not WO.is_maintenance(est_thu - 3600, 8100), "Thu 11-05 07:00Z = 2:00 AM EST is a stop"
    assert WO.is_maintenance(THU - 600, 8100), "Thu 10-22 06:50Z = 2:50 AM EDT is Kalshi's"


def test_server_worth_numbers():
    orders = worth_world()
    w = WO.server_worth(orders, WTMP, T, bank=1000.0)
    assert w["home"]["n"] == 20 and w["srv"]["n"] == 60
    assert abs(w["home"]["got_share"] - 0.7) < 1e-9 and abs(w["srv"]["got_share"] - 0.8) < 1e-9
    assert abs(w["money"]["per"] - 12.0 / 480) < 1e-9 and w["money"]["markets"] == 60
    assert abs(w["est"]["extra"] - 60.0) < 1e-6 and abs(w["est"]["usd"] - 1.50) < 1e-6, w["est"]
    hourly = AW.aws_estimate(T)["hourly"]
    cost = hourly * (T - AW.AWS_BILLED_FROM_EPOCH) / 3600.0
    assert abs(w["cost"] - cost) < 1e-9 and abs(w["net"] - (1.50 - cost)) < 1e-9 and abs(w["per_day"] - w["net"] / 3) < 1e-9
    assert abs(w["matched"] - 1.50) < 1e-6, "every order asked 10: matching by size changes nothing"
    rh, rs = w["rec_home"], w["rec_srv"]
    assert rh["closes"] == 14 * 96 - 8 - 9 and rh["gaps"] == 1 and rh["missed"] == 8 and rh["maint"] == 1 \
        and rh["conn"] == 3, rh
    assert abs(rh["longest"][1] - 9 * 900) < 1e-6 and abs(rh["hours"] - 2.25) < 1e-9
    assert rs["closes"] == 288 and rs["gaps"] == 0 and rs["missed"] == 0 and rs["maint"] == 0 and rs["conn"] == 1, rs
    assert abs(w["per_close"] - 12.0 / 288) < 1e-9 and abs(w["stop_rate"] - 8.0 / (1327 + 8)) < 1e-12
    assert abs(w["laptop_style"] - w["stop_rate"] * 288 * w["per_close"]) < 1e-9


def test_worth_lines_words():
    w = WO.server_worth(worth_world(), WTMP, T, bank=1000.0)
    s = "\n".join(WO.worth_lines(w))
    net = w["net"]
    assert s.startswith("🏆 <b>Worth of the move: 🔴 -$%.2f net so far</b> (3 days 0 h on the server: speed added +$1.50 in "
                        "pin fills, the server cost $%.2f) · about <b>-$%.2f a day</b> · %+.2f%% of the main account's "
                        "$1,000.00 bank · an estimate, not a proof" % (-net, w["cost"], -net / 3, 100 * net / 1000)), s
    assert "Speed: (80.0% - 70.0% got of asked) x 600 asked here = +60 extra contracts x +$0.0250 each = <b>+$1.50</b>, " \
           "the /speed figure; matched by order size (the server's orders are bigger) it reads <b>+$1.50</b>" in s, s
    assert "Cost: $1.69 a day from the price list since the first boot (Oct 26 11:05 PM ET) = <b>$%.2f</b>; AWS's own " \
           "bill needs the billing role (<code>/server help</code>)" % w["cost"] in s, s
    assert "Record: the laptop missed 8 closes (1 stop, the longest 2 h 15 min from Oct 16 12:10 AM ET), 3 connection " \
           "hiccups in its last 14 days; the server missed 0 closes, 1 connection hiccup in 3 days 0 h. Kalshi's " \
           "Thursday maintenance (1 gap and 0 gaps) is left out of both." in s, s
    assert "At the server's +$0.04 a close, the laptop's stop rate (0.6% of its closes) would have cost about " \
           "<b>+$0.07</b> here: shown, not added" in s, s
    assert "a gap over 20 min between rows is a stop" in s
    assert not tg_html_problems(Html(s))
    # no bank: the % of bank is left out, nothing else changes
    s2 = "\n".join(WO.worth_lines(WO.server_worth(worth_world(), WTMP, T, bank=None)))
    assert "of the main account's" not in s2 and "an estimate, not a proof" in s2
    # too early: under the bar, the headline says so and still gives the figure
    s3 = "\n".join(WO.worth_lines(w, min_orders=100))
    assert "⏳ too early: 60 orders, the bar is 100" in s3 and "net so far</b>" in s3
    # could not be worked
    s4 = "\n".join(WO.worth_lines({"err": "boom"}))
    assert s4 == "🏆 <b>Worth of the move</b>: could not be worked (boom). /speed has the fill figures."


def test_worth_on_the_page_and_the_rest_identical():
    """With the worth world planted the page carries the section and, without it, is still the frozen legacy page."""
    with active(("pin",)):
        ph = phone(led=worth_ledger(worth_world()))
        old, _a, new, _b = old_and_new(ph)
    s = str(new)
    assert without_worth(s) == str(old) and "🏆 <b>Worth of the move: 🔴 -$" in s and not tg_html_problems(new), s[:600]
    assert s.index(WORTH_HEAD) < s.index(MACHINE_HEAD) < s.index("💰 <b>Funds"), "the section sits under the header"
    # a bank read that fails costs only the % of bank; a worth that fails names itself and the page still shows
    led = worth_ledger(worth_world())
    led.bank = lambda: 1 / 0
    with active(("pin",)):
        ph = phone(led=led)
        old, _a, new, _b = old_and_new(ph)
    assert without_worth(str(new)) == str(old) and "of the main account's" not in str(new)
    saved = PG.server_worth
    PG.server_worth = lambda *a, **k: 1 / 0
    try:
        with active(("pin",)):
            ph = phone()
            old, _a, new, _b = old_and_new(ph)
    finally:
        PG.server_worth = saved
    assert without_worth(str(new)) == str(old)
    assert "🏆 <b>Worth of the move</b>: could not be worked (division by zero). /speed has the fill figures." in str(new)


def test_command_failure_wall_identical():
    with active(("pin",)):
        ph = phone(machine_fn=lambda: None)          # server_html cannot read a None machine
        old, _a, new, _b = old_and_new(ph)
    assert isinstance(new, str) and new == old and new.startswith("Could not build /server: ") and new.endswith(
        "\nEverything else still works -- /funds has every account's money."), new


def test_aws_not_connected_and_cached():
    calls = []
    AW._AWS.clear()
    a = AW.aws_cost(T, http=aws_world(calls, role=False))
    assert not a["connected"] and a["why"] == "no IAM role on the server yet" and len(calls) == 2
    AW.aws_cost(T + 60, http=aws_world(calls, role=False))
    assert len(calls) == 2, "no role is remembered for AWS_NOT_CONNECTED_TTL_S"
    AW._AWS.clear()
    est = AW.aws_estimate(T)
    assert abs(est["month"] - 51.45) < 0.01 and est["since"] == AW.AWS_BILLED_FROM_EPOCH


def test_machine_ping_seams_resolve_on_pinphone():
    """Ctx.machine() / ping() with no planted function read pinphone.machine_read / kalshi_ping AT CALL TIME -- the
    re-exported names the golden harness patches."""
    ph = phone(machine_fn=None, ping_fn=None)
    c = CX.Ctx.from_phone(ph, "/server")
    saved = pp.machine_read, pp.kalshi_ping
    try:
        pp.machine_read = lambda: {"patched": 1}
        pp.kalshi_ping = lambda: {"patched": 2}
        assert c.machine() == {"patched": 1} and c.ping() == {"patched": 2}
    finally:
        pp.machine_read, pp.kalshi_ping = saved
    assert pp.machine_read is MA.machine_read


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
    print("test_server: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
