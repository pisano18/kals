"""test_server.py -- /server as a command package (research/phone/commands/server: machine.py, aws.py, page.py).

v-tg-rebuild step 9 (2026-10-30, lane D5). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_server.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed. KALS_TESTING=1 (the
write fence); every reading is planted (the machine, the Kalshi ping, botstats' pots, the AWS http function) and
botstats.active_bots for the test's length: no network, no AWS, no process table, no file under results\\.
"""
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

import pinphone as pp                                                # noqa: E402
import botstats                                                      # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import context as CX                                     # noqa: E402
from phone.html import Html, tg_html_problems                       # noqa: E402
from phone.commands.server import aws as AW, machine as MA, page as PG   # noqa: E402
from phone.commands import speed as SP                               # noqa: E402

SV = SP.SERVER_SINCE_EPOCH
T = SV + 3 * 86400
TMP = tempfile.mkdtemp(prefix="test_server_")
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


def phone(**seams):
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
    for f in ("machine.py", "page.py", "__init__.py"):
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
            assert type(new) is type(old) is Html and str(new) == str(old), (bots, role, str(new)[:300])
            assert [c[:2] for c in c_new] == [c[:2] for c in c_old] and c_new, "the same AWS calls, in the same order"
            assert not tg_html_problems(new)
            assert ("This month so far: <b>$1.23</b>" in str(new)) is role, str(new)
            assert ("Cost Explorer read: AccessDeniedException (HTTP 403): not enabled" in str(new)) is role


def test_pots_failure_is_named_on_the_page():
    def bad():
        raise OSError("cache locked")
    with active(("pin",)):
        ph = phone(pots_fn=bad)
        old, _a, new, _b = old_and_new(ph)
    assert str(new) == str(old) and "botstats' cache could not be read (cache locked)" in str(new)


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
