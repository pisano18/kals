"""test_watch_cmd.py -- phone/commands/watch_cmd.py (/watch; v-kwatch 2026-11-07): the page over a state file the real
scanner wrote from its fixtures (research/kalshi_watch.py demo_state: the baseline scan, a null scan and the planted
world's two scans), the file names the two share, the not-installed answer, LATE, a failing check's streak, the size
limit, the wall, its declaration, and the off switch (/watch off asks, /watch off yes writes the stop file the scanner
obeys, /watch on removes it).

The scanner's own --self-test is NOT run here: this file is a stage of pinphone --selftest (the phone's /update gate), and
a watch regression must not block a phone update; the watch runs its self-test before every scan and says on the phone
when it fails.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_watch_cmd.py   (exit 0 = every test passed)
A temp RESULTS folder (botdata.paths.set_results); KALS_TESTING=1; no network, no Kalshi, no key, no Telegram.
"""
import json
import os
import sys
import tempfile

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import kalshi_watch as K                                             # noqa: E402
from botdata import paths                                            # noqa: E402
from phone import command as CM                                      # noqa: E402
from phone.actions import confirm as CF                              # noqa: E402
from phone.actions import journal as JR                              # noqa: E402
from phone.commands import watch_cmd as WC                           # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402
from phone.html import MAX_LEN, Html, html_to_plain, tg_html_problems  # noqa: E402

_DEMO = {}
CHAT = 4242


def _demo():
    """The scanner's own state after its fixture scans (built once; each test gets a copy)."""
    if "st" not in _DEMO:
        st, _ph = K.demo_state(tempfile.mkdtemp(prefix="test_watch_demo_"))
        _DEMO["st"] = json.loads(json.dumps(st))
    return json.loads(json.dumps(_DEMO["st"]))


def _world(st=None):
    td = tempfile.mkdtemp(prefix="test_watch_cmd_")
    if st is not None:
        K.save_state(st, os.path.join(td, WC.STATE))
    return paths.set_results(td), td


def _run(now, text="/watch"):
    return WC.COMMAND.run(FakeCtx(text=text, now=now, chat_id=CHAT))


def test_declared():
    import tgcharts
    c = WC.COMMAND
    assert c.names == ("/watch",) and c.section == "server" and c.order == 40 and c.chart is None
    assert c.needs_ledger is False and c.fail is not None and c.handle is not None and c.load is None
    assert c.help_line.startswith("/watch: ") and "\u2014" not in c.help_line and "\u2013" not in c.help_line
    assert "/watch off" in c.help_line and "/watch on" in c.help_line
    assert c.kind_of("/watch") is None and tgcharts.kind_of("/watch") is None
    failed = CM.discover()
    assert not failed, failed
    assert CM.by_name("/watch") is c
    places = [(x.section, x.order) for x in CM.commands() if x.section == "server"]
    assert places.count(("server", 40)) == 1, places


def test_the_scanner_and_the_page_share_their_files():
    assert WC.STATE == K.STATE_NAME == "kalshi_watch_state.json", (WC.STATE, K.STATE_NAME)
    assert WC.STOP == K.STOP_NAME == "kalshi_watch.stop", (WC.STOP, K.STOP_NAME)
    assert WC.EVERY_MIN == K.EVERY_MIN == 30


def test_not_installed_yet():
    old, _td = _world()
    try:
        out = _run(K.T_SAT)
        s = str(out)
        assert type(out) is Html and s == WC.NOT_YET and "has not scanned yet" in s, s
        assert "kalshi_watch_install.ps1" in s and not tg_html_problems(s)
    finally:
        paths.set_results(old)


def test_page_over_a_real_scan():
    st = _demo()
    old, _td = _world(st)
    try:
        now = st["last_scan_s"] + 600
        out = _run(now)
        s = str(out)
        plain = html_to_plain(s)
        assert type(out) is Html and len(s) <= MAX_LEN and not tg_html_problems(s), (len(s), tg_html_problems(s))
        assert s.startswith("👁 <b>Kalshi watch</b> (a scan every 30 minutes"), s[:120]
        assert "Last scan: Nov 7 6:30 PM ET (10 minutes ago) · 4 scans so far · 20 signed Kalshi reads in the last one" \
            in plain, plain
        assert "LATE" not in plain and "OFF" not in plain
        for _cid, label in K.CHECKS:
            assert ("🟢 %s: " % label) in plain, label
        idx = [plain.index("🟢 %s: " % label) for _cid, label in K.CHECKS]
        assert idx == sorted(idx), "the checks are listed in the scanner's order"
        assert "candlesticks endpoint (urgent" not in plain, "'candlesticks' is not an urgent 'tick'"
        assert "🟢 Kalshi API changelog: 6 entries; the newest is dated Nov 20, 2026 (in 13 days)" in plain, plain
        assert "Open now (%d)" % len(st["open"]) in plain and len(st["open"]) >= 5, plain
        assert "🚨 Kalshi has paused trading outside its schedule · since Nov 7 6:00 PM ET" in plain, plain
        assert "🔔 Server disk C: is down to 12.0 GB free · since Nov 7 6:00 PM ET" in plain, plain
        i_urgent = plain.index("🚨 Kalshi has paused")
        assert i_urgent < plain.index("🔔 Server disk"), "urgent conditions are listed first"
        cl = plain.split("Kalshi's newest changelog entries", 1)[1].split("Last alerts sent", 1)[0]
        assert cl.count("\n• ") == 5, "exactly the 5 newest changelog entries: %r" % cl
        assert "• Nov 20, 2026: Event candlesticks endpoint" in cl
        assert "• Nov 9, 2026: fee_multiplier changes for crypto series (urgent: crypto, fee)" in cl, cl
        sent = plain.split("Last alerts sent", 1)[1]
        assert sent.count("\n• ") == 5, "exactly the last 5 alerts sent: %r" % sent
        newest = [h["head"] for h in reversed(st["history"])][:5]
        assert len(st["history"]) > 5 and all(h in sent for h in newest), (newest, sent)
        assert [sent.index(h) for h in newest] == sorted(sent.index(h) for h in newest), "newest alert first"
        assert "\u2014" not in s and "waiting" not in plain
        assert str(_run(now, "/Watch@kalsbot")) == s, "the router's name forms give the same page"
    finally:
        paths.set_results(old)


def test_late_failing_and_waiting():
    st = _demo()
    st["checks"]["kalshi_api"].update(status="failed", fail_streak=2, last_ok=st["last_scan"],
                                      detail="0 of 3 signed reads ok; 3 got no answer or a Kalshi server error")
    st["outbox"] = [{"id": "x", "head": "h", "body": "b", "urgent": False, "t": st["last_scan"]}] * 2
    st["open"]["disk_low"]["quiet"] = True
    old, _td = _world(st)
    try:
        plain = html_to_plain(str(_run(st["last_scan_s"] + 95 * 60)))
        assert "LATE: no scan for 95 minutes: it should run every 30 minutes" in plain, plain
        assert ("🔴 Kalshi's answers (signed reads): FAILED 2 scans in a row: 0 of 3 signed reads ok; 3 got no answer "
                "or a Kalshi server error (last good read Nov 7 6:30 PM ET)") in plain, plain
        assert "2 alerts waiting: Telegram did not take them yet; they go at the next scan." in plain, plain
        assert "is down to 12.0 GB free · since Nov 7 6:00 PM ET (keeps coming and going" in plain, plain
        plain = html_to_plain(str(_run(st["last_scan_s"] + 3 * 86400)))
        assert "LATE: no scan for 3 days" in plain, plain
    finally:
        paths.set_results(old)


def test_size_limit_and_bad_state():
    st = _demo()
    for i in range(60):
        st["open"]["x%d" % i] = {"check": "disk", "head": "h" * 300 + str(i), "body": "b", "urgent": i % 2 == 0,
                                 "since": st["last_scan"]}
    for c in st["checks"].values():
        c["detail"] = "d" * 400
    old, _td = _world(st)
    try:
        s = str(_run(st["last_scan_s"] + 60))
        assert len(s) <= MAX_LEN and not tg_html_problems(s), len(s)
        assert "Open now (%d)" % len(st["open"]) in html_to_plain(s) and "h" * 300 not in s
        assert "d" * 400 not in s and s.count("🟢") == len(K.CHECKS), "every check still listed, its words cut"
    finally:
        paths.set_results(old)
    for bad in ({"last_scan": "2026-11-07T23:30:00Z", "checks": [], "open": "x", "history": None},
                {"runs": 3}, [1, 2]):
        old, td = _world()
        try:
            with open(os.path.join(td, WC.STATE), "w", encoding="utf-8") as fh:
                json.dump(bad, fh)
            s = str(_run(K.T_SAT + 9000))
            assert s.startswith("👁 <b>Kalshi watch</b>") and not s.startswith("Could not"), s[:200]
        finally:
            paths.set_results(old)
    saved = paths.read_json
    paths.read_json = lambda p: (_ for _ in ()).throw(ValueError("planted"))
    try:
        r = _run(K.T_SAT)
    finally:
        paths.read_json = saved
    assert r == "Could not build /watch: planted", r


def test_off_and_on():
    st = _demo()
    old, td = _world(st)
    stop = os.path.join(td, WC.STOP)
    now = st["last_scan_s"] + 600
    try:
        CF.drop()
        r = str(_run(now, "/watch off yes"))
        assert "Nothing is waiting for a yes" in r and not os.path.exists(stop), r
        r = str(_run(now, "/watch off"))
        assert "Turn the Kalshi watch off?" in r and "/watch off yes" in r and not os.path.exists(stop), r
        assert "Pin and every bot keep trading as before" in r and not tg_html_problems(r)
        r = str(_run(now + 400, "/watch off yes"))
        assert "expired" in r and not os.path.exists(stop), r
        _run(now, "/watch off")
        r = str(_run(now + 30, "/watch off yes"))
        assert "Kalshi watch off" in r and os.path.exists(stop), r
        with open(stop, encoding="utf-8") as fh:
            assert "operator /watch off" in fh.read()
        page = html_to_plain(str(_run(now + 4 * 3600)))
        assert "OFF since" in page and "/watch on starts it again" in page and "LATE" not in page, page
        assert "already off" in str(_run(now + 60, "/watch off"))
        r = str(_run(now + 120, "/watch on"))
        assert "Kalshi watch on again" in r and not os.path.exists(stop), r
        assert "on already" in str(_run(now + 130, "/watch on"))
        page = html_to_plain(str(_run(now + 4 * 3600)))
        assert "OFF" not in page and "LATE" in page, page
        kinds = [x.get("kind") for x in JR.read()]
        assert kinds.count("watch_off") == 1 and kinds.count("watch_on") == 1, kinds
        assert "/watch off stops it" in html_to_plain(str(_run(now, "/watch help")))
        # the scanner obeys the file the phone writes (the same path, the same name)
        _run(now, "/watch off")
        _run(now + 1, "/watch off yes")
        assert os.path.exists(os.path.join(td, K.STOP_NAME))
    finally:
        CF.drop()
        paths.set_results(old)
    # not scanned yet, but switched off: the page says both
    old, td = _world()
    try:
        _run(K.T_SAT, "/watch off")
        _run(K.T_SAT + 1, "/watch off yes")
        s = html_to_plain(str(_run(K.T_SAT + 60)))
        assert "has not scanned yet" in s and "OFF since" in s, s
    finally:
        CF.drop()
        paths.set_results(old)


def test_off_write_refused():
    """A stop file that cannot be written (the write fence, a full disk): the answer says so and nothing changes."""
    old, td = _world(_demo())
    saved = paths.check_write
    paths.check_write = lambda p: (_ for _ in ()).throw(PermissionError("planted: refused"))
    try:
        CF.drop()
        _run(K.T_SAT, "/watch off")
        r = str(_run(K.T_SAT + 1, "/watch off yes"))
        assert r.startswith("Could not turn the Kalshi watch off: planted: refused") and "Nothing changed" in r, r
        assert not os.path.exists(os.path.join(td, WC.STOP))
    finally:
        paths.check_write = saved
        CF.drop()
        paths.set_results(old)


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_watch_cmd"))
