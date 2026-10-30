"""test_context.py -- phone/context.py (Ctx, FakeCtx), phone/command.py (Command, the registry) and the first command
module, phone/commands/hedges.py; plus the source rules every phone/commands/*.py module must keep (CONTRACT.md).

v-tg-rebuild step 9 (2026-10-30). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_context.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed. KALS_TESTING=1 (the
write fence); no network, no real process table, no file under results\\ read or written (a temp folder stands in).
"""
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
from phone import command as CM                                     # noqa: E402
from phone import context as CX                                     # noqa: E402
from phone.html import Html                                          # noqa: E402

T = 1793448000.0            # 2026-10-30 14:40Z
TMP = tempfile.mkdtemp(prefix="test_context_")


def fake_ledger(outcomes=None, bank=1000.0):
    led = types.SimpleNamespace(results=TMP, hedges=[], settled=[])
    led.hedge_outcomes = lambda: list(outcomes or [])
    led.bank_at = lambda t: bank
    led.refresh = lambda: None
    return led


def phone(led=None, **seams):
    ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=led or fake_ledger(), now_fn=lambda: T,
                  health_fn=lambda: {"alive": True}, procs_fn=lambda: [(1, "python x.py")])
    for k, v in seams.items():
        setattr(ph, k, v)
    return ph


HEDGES = [   # oldest first, as the Ledger gives them
    {"tk": "KXZECD-26OCT2910-T300", "t": T - 86400, "verdict": "NEEDED", "net": -6.36, "belief": 0.0},
    {"tk": "KXBNB15M-26OCT301300-00", "t": T - 7200, "verdict": None, "net": None, "belief": None},
    {"tk": "KXCRYPTOLEAD15M-26OCT301300", "t": None, "verdict": "WASTED", "net": 1.56, "belief": 0.89},
] + [{"tk": "KXETH15M-26OCT30%02d00-00" % h, "t": T - h * 3600, "verdict": "WASTED", "net": 0.5 * h, "belief": 0.9}
     for h in range(1, 9)]


# ---- Ctx ---------------------------------------------------------------------------------------------------------------
def test_split_command_like_handle():
    assert CX.split_command("  /Stop@kalsbot  yes ") == ("/Stop@kalsbot  yes", "/stop", " yes")
    assert CX.split_command(None) == ("", "", "")
    assert CX.split_command("/server help") == ("/server help", "/server", "help")


def test_from_phone_is_the_phones_seams():
    ph = phone(bs_getter=object(), bs_procs=[[1, "", "x"]], funds_getter=object(), machine_fn=lambda: {"m": 1},
               ping_fn=lambda: {"p": 1}, pots_fn=lambda: {"pots": 1}, aws_http=object(), bars_fn=lambda: "b",
               chart_fn=object(), chart_stale_s=5)
    c = CX.Ctx.from_phone(ph, "/Server@kalsbot help")
    assert (c.cmd, c.arg, c.text, c.chat_id) == ("/server", "help", "/Server@kalsbot help", 7)
    assert c.pp is pp and c.ledger is ph.ledger and c.results == TMP and c.state is ph
    for k in CX._SEAMS:
        assert getattr(c, k) is getattr(ph, k), k
    assert c.now() == T and c.health() == {"alive": True} and c.procs() == [(1, "python x.py")]
    assert c.machine() == {"m": 1} and c.ping() == {"p": 1} and c.pots() == {"pots": 1}
    assert c.funds_get() is ph.funds_getter
    c.say("hello")
    assert ph.tg.sent and ph.tg.sent[-1][1] == "hello"


def test_providers_resolve_defaults_at_call_time():
    """machine_fn / ping_fn None -> the OLD module's machine_read / kalshi_ping, looked up when called (a patch made
    after the Ctx was built is seen, exactly as the old method saw it)."""
    ph = phone()
    c = CX.Ctx.from_phone(ph, "/server")
    saved = pp.machine_read, pp.kalshi_ping, pp.python_procs, pp.cached_python_procs
    try:
        pp.machine_read = lambda: {"patched": "machine"}
        pp.kalshi_ping = lambda: {"patched": "ping"}
        assert c.machine() == {"patched": "machine"} and c.ping() == {"patched": "ping"}
        pp.cached_python_procs = lambda: [(9, "cached")]
        assert c.procs_cached() == [(1, "python x.py")], "a planted procs_fn is asked itself"
        c.procs_fn = pp.python_procs
        assert c.procs_cached() == [(9, "cached")], "the default reader -> the cached table (Phone.text_racestats)"
    finally:
        pp.machine_read, pp.kalshi_ping, pp.python_procs, pp.cached_python_procs = saved


def test_sides_markets_active_bs_get_match_phone():
    led = fake_ledger()
    led.hedges = [{"tk": "A", "side": "yes"}, {"tk": "B", "side": "no"}, {"tk": "", "side": "yes"}]
    led.settled = [{"tk": "A", "want": "no"}, {"tk": "C", "want": "yes"}, {"tk": "D", "want": "?"}]
    ph = phone(led)
    c = CX.Ctx.from_phone(ph, "/stats")
    assert c.sides() == ph._sides() == {"A": "no", "B": "yes", "C": "yes"}
    assert c.markets() == ph._markets()                         # no pin ledger file in the temp folder: both empty
    calls = []
    fake_bs = types.SimpleNamespace(BOTS=("pin", "race"),
                                    active_bots=lambda procs=None: calls.append(procs) or ["pin"],
                                    all_bots=lambda now, getter, procs: {"all": now},
                                    bot=lambda name, now, getter, procs: {name: now})
    c.bs = lambda: fake_bs
    assert c.active() == ("pin",) and c.bs_get("all") == {"all": T} and c.bs_get("race") == {"race": T}
    fake_bs.active_bots = lambda procs=None: 1 / 0
    assert c.active() == ("pin", "race"), "any error shows every bot (Phone.active's fail-safe)"


def test_with_message_keeps_seams():
    ph = phone(bs_getter=object())
    c = CX.Ctx.from_phone(ph, "/today").with_message("/yesterday x")
    assert (c.cmd, c.arg) == ("/yesterday", "x") and c.bs_getter is ph.bs_getter and c.ledger is ph.ledger


def test_unknown_field_refused():
    try:
        CX.Ctx(nonsense=1)
    except TypeError:
        return
    raise AssertionError("Ctx(nonsense=1) was accepted")


def test_fakectx_planted_and_missing():
    led = fake_ledger()
    f = CX.FakeCtx(text="/Hedges", now=T, ledger=led, active=("pin",), bs_get={"all": {"x": 1}}, health={"h": 1})
    assert (f.cmd, f.now(), f.results, f.active(), f.bs_get("all"), f.health()) == ("/hedges", T, TMP, ("pin",),
                                                                                   {"x": 1}, {"h": 1})
    f.say("hi")
    assert f.said == [(None, "hi")]
    for read in (lambda: f.pp.usd(1), lambda: f.machine(), lambda: f.procs(), lambda: f.funds_get(),
                 lambda: f.markets(), lambda: f.bs_getter.x):
        try:
            read()
        except CX.CtxMissing:
            continue
        raise AssertionError("an unplanted read did not raise CtxMissing")


# ---- Command and the registry ------------------------------------------------------------------------------------------
def _bad(**kw):
    try:
        CM.Command(**kw)
    except ValueError:
        return True
    return False


def test_command_validation():
    ld, rd = (lambda ctx: 1), (lambda data: data)
    assert _bad(names=("/X",), load=ld, render=rd), "upper case"
    assert _bad(names=("/x@bot",), load=ld, render=rd), "@"
    assert _bad(names=("x",), load=ld, render=rd), "no slash"
    assert _bad(names=(), load=ld, render=rd), "no names"
    assert _bad(names=("/x",)), "no entry point"
    assert _bad(names=("/x",), load=ld, render=rd, handle=ld), "both"
    assert _bad(names=("/x",), load=ld, render=rd, section="nope"), "section"
    assert _bad(names=("/x",), load=ld, render=rd, chart={"/y": "k"}), "chart for a name it has not"
    assert _bad(names=("/x",), load=ld, render=lambda a, b, c: 1), "render arity"
    c = CM.Command(names="/x", load=ld, render=rd, chart={"/x": "k"})
    assert c.names == ("/x",) and c.name == "/x" and c.kind_of("/x") == "k" and c.kind_of("/y") is None
    c2 = CM.Command(names=("/a", "/b"), handle=ld, chart="k")
    assert c2.kind_of() == "k" and c2.kind_of("/b") == "k" and c2.kind_of("/z") is None


def test_command_run_paths():
    f = CX.FakeCtx(text="/x", now=T)
    assert CM.Command(names=("/x",), load=lambda c: c.now(), render=lambda d: "t=%d" % d).run(f) == "t=%d" % T
    assert CM.Command(names=("/x",), load=lambda c: 2, render=lambda d, c: (d, c.cmd)).run(f) == (2, "/x")
    assert CM.Command(names=("/x",), handle=lambda c: c.cmd).run(f) == "/x"
    boom = CM.Command(names=("/x",), load=lambda c: 1 / 0, render=lambda d: d,
                      fail=lambda e: "Could not build /x: %s" % str(e)[:200])
    assert boom.run(f) == "Could not build /x: division by zero"
    try:
        CM.Command(names=("/x",), load=lambda c: 1 / 0, render=lambda d: d).run(f)
    except ZeroDivisionError:
        pass
    else:
        raise AssertionError("no fail: the exception must reach the router")


def test_declare_registry():
    g = {"__name__": "phone.commands._test_a"}
    exec("from phone.command import Command, declare\n"
         "COMMAND = declare(Command(names=('/zz_one', '/zz_alias'), handle=lambda c: 1))", g)
    c = g["COMMAND"]
    assert c.module == "phone.commands._test_a" and CM.by_name("/zz_alias") is c and c in CM.commands()
    exec("COMMAND = declare(Command(names=('/zz_one',), handle=lambda c: 2))", g)   # a re-import replaces
    assert CM.by_name("/zz_one") is g["COMMAND"] and CM.by_name("/zz_alias") is None
    h = {"__name__": "phone.commands._test_b"}
    try:
        exec("from phone.command import Command, declare\n"
             "COMMAND = declare(Command(names=('/zz_one',), handle=lambda c: 3))", h)
    except ValueError:
        pass
    else:
        raise AssertionError("two modules declared /zz_one")
    exec("COMMAND = declare()", g)          # clean up: the test module declares nothing any more
    assert CM.by_name("/zz_one") is None


def test_discover_and_of_module():
    failed = CM.discover()
    assert not failed, failed
    hd = CM.of_module("phone.commands.hedges")
    assert len(hd) == 1 and CM.by_name("/hedges") is hd[0] and hd[0].section == "now"


# ---- /hedges: the new module against Phone.text_hedges, on planted ledgers ---------------------------------------------
def test_hedges_identical_to_phone():
    for outcomes, bank in ((HEDGES, 1000.0), (HEDGES[:2], None), ([], 1000.0), (HEDGES[2:3], 0)):
        ph = phone(fake_ledger(outcomes, bank))
        old = ph.text_hedges()
        new = CM.of_module("phone.commands.hedges")[0].run(CX.Ctx.from_phone(ph, "/hedges"))
        assert type(new) is type(old) and isinstance(new, Html) and str(new) == str(old), (str(old), str(new))
    f = CX.FakeCtx(text="/hedges", now=T, ledger=fake_ledger(HEDGES), pp=pp)
    assert str(CM.of_module("phone.commands.hedges")[0].run(f)).count("\n") == 9    # title + 8 hedges + legend
    import tgcharts
    assert CM.by_name("/hedges").kind_of("/hedges") == tgcharts.kind_of("/hedges")


# ---- the rules every command module keeps (CONTRACT.md) ----------------------------------------------------------------
def test_command_sources_rules():
    d = os.path.join(RESEARCH, "phone", "commands")
    bad = []
    files = sorted(os.path.relpath(os.path.join(r, f), d) for r, _ds, fs in os.walk(d) for f in fs
                   if f.endswith(".py") and os.path.relpath(r, d).split(os.sep)[0] != "tests")   # tests may import pinphone
    for f in files:
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            src = fh.read()
        parts = f[:-3].split(os.sep)                     # server\aws.py -> server_aws; server\__init__.py -> server
        stem = "_".join(x for x in parts if x != "__init__")
        if re.search(r"\burllib\b", src) and stem not in ("server", "server_aws", "aws"):
            bad.append("%s: urllib (only phone/transport.py and the /server AWS module)" % f)
        if re.search(r"\bsubprocess\b", src) and not stem.startswith("update"):
            bad.append("%s: subprocess (only the /update module)" % f)
        if re.search(r"\bdo_(start|pause|stop)\b", src) and not stem.startswith("control"):
            bad.append("%s: pindesk.do_* (only the controls module)" % f)
        if re.search(r"\bimport\s+pinphone\b|\bfrom\s+pinphone\s+import\b", src):
            bad.append("%s: imports pinphone (use ctx.pp: under --selftest pinphone is __main__)" % f)
        for m in re.finditer(r"\bopen\(([^()]*(\([^()]*\))?[^()]*)\)", src):
            args = m.group(1)
            if "encoding=" not in args and not re.search(r"""['"][rwax+]*b[rwax+]*['"]""", args):
                bad.append("%s: open(%s) without encoding=" % (f, args[:60]))
    assert not bad, "\n".join(bad)


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
    print("test_context: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
