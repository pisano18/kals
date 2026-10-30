"""test_leaf.py -- phone/log.py, phone/html.py, phone/transport.py: moved out of pinphone.py and still the same objects.

v-tg-rebuild step 6 (2026-10-30). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_leaf.py
Plain test_* functions and a tiny runner (no pytest on C:\\Python314). Exit 0 = every test passed. KALS_TESTING=1: the
write fence refuses every live file; no network (Telegram's _call is replaced), nothing under results\\ is written.

What it proves:
  - every moved name is re-exported by pinphone as the very same object (bars.py, phone_alert.py, the golden harness
    and pinphone's self-test use them as pinphone.<name>);
  - DESIGN risk 2: a patch of pinphone.LOG still moves every log() line -- the transport's too -- and with no patch,
    under KALS_TESTING=1, the real log is refused (the fence), never appended;
  - the transport sends an Html reply with parse_mode=HTML and a plain str as before, re-sends refused markup as plain
    text, and net_error tells a dropped connection from a refused message;
  - every text open() in the three modules names its encoding, and only transport.py opens a URL.
"""
import io
import os
import re
import sys
import tempfile
import time
import traceback
import urllib.error

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinphone as pp                                                # noqa: E402
from phone import html as H, log as L, transport as T               # noqa: E402

MOVED = {
    L: ("log", "cprint"),
    H: ("MAX_LEN", "Html", "esc", "html_to_plain", "_MONEY_SIGN", "_MONEY_BIG", "norm_money", "b_", "i_", "table", "pre",
        "details", "elines", "_EIGHTHS", "hbar", "_SPARK", "spark", "_TG_TAGS", "_TG_STYLE", "_TG_TOK", "tg_html_problems",
        "_TAG", "_open_after", "_closers", "_openers", "_cut_long_line", "split_html", "split_text"),
    T: ("Telegram", "photo_body", "net_error", "FakeTelegram"),
}


def test_reexported_same_objects():
    for mod, names in MOVED.items():
        for n in names:
            assert getattr(pp, n) is getattr(mod, n), "pinphone.%s is not %s.%s" % (n, mod.__name__, n)
    assert pp.MAX_LEN == 3900


def test_log_follows_pinphone_LOG():
    old = pp.LOG
    with tempfile.TemporaryDirectory() as td:
        try:
            pp.LOG = os.path.join(td, "x.log")
            pp.log("one line 🟢")
            sent = []
            tr = pp.Telegram("tok")

            def refuse(method, params, http_timeout=45):
                if params.get("parse_mode"):
                    raise urllib.error.HTTPError("x", 400, "Bad Request: can't parse entities", None, None)
                sent.append(dict(params))
            tr._call = refuse
            tr.send(1, pp.Html("<b>LOSS -$4.57</b> x &lt; y"))
        finally:
            pp.LOG = old
        with open(os.path.join(td, "x.log"), encoding="utf-8") as fh:
            got = fh.read()
    assert "one line 🟢" in got, got
    assert "Telegram refused the HTML of one part" in got, got        # the transport's line went to the patched LOG
    assert sent == [{"chat_id": 1, "text": "LOSS -$4.57 x < y"}], sent
    assert L.log_path() == pp.LOG


def test_unpatched_log_is_fenced():
    """No patch, KALS_TESTING=1: log() refuses the real log (an OSError inside, nothing raised, nothing written)."""
    real = pp.LOG
    st0 = os.stat(real) if os.path.exists(real) else None
    so = sys.stdout
    try:
        sys.stdout = io.StringIO()
        pp.log("test_leaf: this line must NOT reach the real log")
    finally:
        sys.stdout = so
    st1 = os.stat(real) if os.path.exists(real) else None
    assert (st0 and (st0.st_size, st0.st_mtime)) == (st1 and (st1.st_size, st1.st_mtime)), (st0, st1)


def test_log_never_raises_on_cp1252():
    so = sys.stdout
    old = pp.LOG
    with tempfile.TemporaryDirectory() as td:
        try:
            pp.LOG = os.path.join(td, "x.log")
            sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
            pp.log("SENT: 🟢 Today +$7.10")
            pp.cprint("🟢 cprint")
            sys.stdout.flush()
            con = sys.stdout.buffer.getvalue().decode("cp1252")
        finally:
            sys.stdout = so
            pp.LOG = old
    assert "\\U0001f7e2 Today +$7.10" in con and "\\U0001f7e2 cprint" in con, con


def test_transport_html_and_plain():
    sent = []
    tr = T.Telegram("tok")
    tr._call = lambda method, params, http_timeout=45: sent.append((method, dict(params)))
    tr.send(5, H.Html("<b>hi</b>"))
    tr.send(5, "plain <b>as before</b>")
    assert sent[0] == ("sendMessage", {"chat_id": 5, "text": "<b>hi</b>", "parse_mode": "HTML"}), sent
    assert sent[1] == ("sendMessage", {"chat_id": 5, "text": "plain <b>as before</b>"}), sent
    big = H.Html("\n".join("<b>line %d</b> %s" % (k, "x" * 80) for k in range(200)))
    sent[:] = []
    tr.send(5, big)
    assert len(sent) > 1 and all(len(p["text"]) <= H.MAX_LEN for _m, p in sent)
    assert all(not H.tg_html_problems(p["text"]) for _m, p in sent)


def test_net_error_and_photo_body():
    assert T.net_error(ConnectionResetError()) and T.net_error(urllib.error.HTTPError("u", 502, "x", None, None))
    assert T.net_error(urllib.error.HTTPError("u", 429, "x", None, None))
    assert not T.net_error(urllib.error.HTTPError("u", 400, "x", None, None))
    b = T.photo_body(111, b"\x89PNGDATA", "Today +$1.00", "BND")
    assert b.startswith(b"--BND\r\n") and b.endswith(b"--BND--\r\n") and b"\x89PNGDATA" in b and b"Today +$1.00" in b
    f = T.FakeTelegram()
    f.push(7, "/status")
    assert f.get_updates(0)[0]["message"]["text"] == "/status"


def test_sources_safe():
    """Every text open() names its encoding; only transport.py may open a URL; no subprocess anywhere here."""
    for mod in (L, H, T):
        with open(mod.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for m in re.finditer(r"\bopen\(([^)]*)\)", src):
            assert "encoding=" in m.group(1) or "\"rb\"" in m.group(1) or "\"wb\"" in m.group(1), \
                "%s: %s" % (os.path.basename(mod.__file__), m.group(0))
        assert "sub" + "process" not in src
        if mod is not T:
            assert "url" + "open" not in src and "urllib" + ".request" not in src, mod.__name__


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
    print("test_leaf: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
