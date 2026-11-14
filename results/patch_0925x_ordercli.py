"""Apply v-0925x connect (build 0925x) to a COPY of the live pin build's research\\ordercli.py (C:\\kals-live-0925w:
ordercli.py sha256[:12] 467782077a23, unchanged since 0925t). Patches ordercli.py in place, CRLF preserved; every anchor
must occur exactly once; refuses an already-patched file, a file that is not 467782077a23, and any result whose sha is
not EXPECTED_ORDERCLI (nothing is written then). Every refusal is an explicit exit, not an assert.
usage: python patch_0925x_ordercli.py <build_dir>      (build_dir holds research\\ordercli.py)
Goes with results\\patch_0925x.py (pinrun.py): pinrun's v-0925x connect checks read the mark this adds and FAIL
without it, so a build with only one of the two patches does not pass its startup self-test.

  connect  a failure in the CONNECT phase of a request on the kept-connection path (--keep-conn on, live) -- the TCP
           connect or the TLS handshake, before one byte of the request is written -- now ends its text with
           CONNECT_NOT_SENT (" [connect phase: not sent]"). The text still starts "<urlopen error", exactly as before.
           pinrun.hedge_never_sent() reads the mark: a reset or a timeout DURING the handshake ("[WinError 10054]",
           "timed out" -- no never-sent marker of their own) on a hedge is then known never sent and is sent again
           next second, instead of being counted covered (UNKNOWN) until ktruth reopens it 3+ s later. A write- or
           read-phase failure never carries the mark (a write may be retried here on a fresh connection; a failed
           retry's own connect does carry it, which is right: the first write did not complete -- the reason it was
           retried -- and the retry wrote nothing). v-keepconn "outcome UNKNOWN" texts are built from str(error),
           never from text(), so they cannot carry it. Nothing else changes: no order, retry or timeout moves.
"""
import hashlib
import os
import sys

BASE_ORDERCLI = "467782077a23"
EXPECTED_ORDERCLI = "f40c43061ea3"   # the reviewed result (the patch refuses to write anything else)


def refuse(msg):
    sys.stderr.write("REFUSED: " + msg + "\n")
    sys.exit(2)


if len(sys.argv) != 2:
    sys.stderr.write("usage: python patch_0925x_ordercli.py <build_dir>   (build_dir holds research\\ordercli.py)\n")
    sys.exit(2)
B = sys.argv[1]
OC = os.path.join(B, "research", "ordercli.py")
if not os.path.isfile(OC):
    refuse("%s does not exist" % OC)


def sha12(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


class Src:
    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read().decode("utf-8")
        if "\r\n" not in raw:
            refuse(path + ": not CRLF")
        self.s = raw.replace("\r\n", "\n")
        if "\r" in self.s:
            refuse(path + ": stray CR")

    def once(self, anchor):
        n = self.s.count(anchor)
        if n != 1:
            refuse("%s: anchor found %d times (need exactly 1), nothing written: %r"
                   % (self.path, n, anchor[:90]))

    def after(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, anchor + text)

    def before(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, text + anchor)

    def replace(self, old, new):
        self.once(old)
        self.s = self.s.replace(old, new)

    def write(self, expected=None):
        data = self.s.replace("\n", "\r\n").encode("utf-8")
        got = hashlib.sha256(data).hexdigest()[:12]
        if expected is not None and got != expected:
            refuse("%s: the patched file would be %s, not the reviewed %s; nothing written"
                   % (self.path, got, expected))
        open(self.path, "wb").write(data)
        return got


if sha12(OC) != BASE_ORDERCLI:
    refuse("research/ordercli.py is not %s (%s); nothing written" % (BASE_ORDERCLI, sha12(OC)))
O = Src(OC)
if "CONNECT_NOT_SENT" in O.s or "v-0925x" in O.s:
    refuse("already patched (v-0925x is in it); nothing written")
if "def _send_kept(" not in O.s or "class _Fail(object):" not in O.s:
    refuse("not the v-keepconn ordercli (no _send_kept / _Fail); nothing written")

# 1. the mark, and the connect phase's text carries it
O.replace('''class _Fail(object):
    """One failed attempt: which phase, on a kept or a fresh connection."""
    __slots__ = ("phase", "reused", "err", "idle")

    def __init__(self, phase, reused, err, idle):
        self.phase, self.reused, self.err, self.idle = phase, reused, err, idle

    def text(self):
        """What the old urllib path returned for the same failure: an
        OSError while connecting or writing came back wrapped as URLError."""
        if self.phase in ("connect", "write") and isinstance(self.err, OSError):
            return "<urlopen error %s>" % (self.err,)
        return str(self.err)
''', '''# v-0925x connect (2026-11-13): the end of a CONNECT-phase failure's text.
# The connect phase is the TCP connect and the TLS handshake (conn.connect()
# in _attempt): not one byte of the request has been written, so nothing can
# have been placed. pinrun.hedge_never_sent() reads this mark (its
# _NEVER_SENT_MARKERS), so a hedge whose handshake was RESET or TIMED OUT --
# texts with no never-sent marker of their own -- is sent again next second
# instead of being counted covered while ktruth looks it up.
CONNECT_NOT_SENT = " [connect phase: not sent]"


class _Fail(object):
    """One failed attempt: which phase, on a kept or a fresh connection."""
    __slots__ = ("phase", "reused", "err", "idle")

    def __init__(self, phase, reused, err, idle):
        self.phase, self.reused, self.err, self.idle = phase, reused, err, idle

    def text(self):
        """What the old urllib path returned for the same failure: an
        OSError while connecting or writing came back wrapped as URLError.
        v-0925x connect: a CONNECT-phase OSError ends with CONNECT_NOT_SENT
        (still "<urlopen error ..." first); write and read never do."""
        if self.phase in ("connect", "write") and isinstance(self.err, OSError):
            t = "<urlopen error %s>" % (self.err,)
            return t + CONNECT_NOT_SENT if self.phase == "connect" else t
        return str(self.err)
''')

# 2. ordercli's own self-test: the refused connect (a real fresh connection on the loopback) carries the mark, and
#    only the connect phase ever does
O.replace('''        ck(st == -1 and isinstance(r, str) and r.startswith("<urlopen error")
           and ("[WinError 10061]" in r or "Connection refused" in r),
           "a refused connect is -1 '<urlopen error ...refused...>', the text "
           "pinrun.hedge_never_sent() reads (%r)" % (str(r)[:70],))
''', '''        ck(st == -1 and isinstance(r, str) and r.startswith("<urlopen error")
           and ("[WinError 10061]" in r or "Connection refused" in r),
           "a refused connect is -1 '<urlopen error ...refused...>', the text "
           "pinrun.hedge_never_sent() reads (%r)" % (str(r)[:70],))
        # 10b. v-0925x connect: a CONNECT-phase failure says so at the end of
        #      its text (pinrun reads it as never sent): the refused connect
        #      above, a reset or a timeout inside the handshake; a write- or
        #      read-phase failure, or a non-OSError, never does
        _x_rst = ConnectionResetError(10054, "An existing connection was "
                                             "forcibly closed by the remote host")
        _x_txt = (_Fail("connect", False, _x_rst, None).text(),
                  _Fail("connect", False, TimeoutError("timed out"), None).text(),
                  _Fail("write", True, _x_rst, 3.0).text(),
                  _Fail("write", False, _x_rst, None).text(),
                  _Fail("read", False, TimeoutError("timed out"), None).text(),
                  _Fail("connect", False, ValueError("refusing scheme"), None).text())
        ck(CONNECT_NOT_SENT == " [connect phase: not sent]"
           and isinstance(r, str) and r.endswith(CONNECT_NOT_SENT)
           and _x_txt[0].startswith("<urlopen error") and _x_txt[0].endswith(CONNECT_NOT_SENT)
           and _x_txt[1] == "<urlopen error timed out>" + CONNECT_NOT_SENT
           and not any(CONNECT_NOT_SENT in t for t in _x_txt[2:])
           and _x_txt[2].startswith("<urlopen error") and _x_txt[4] == "timed out",
           "v-0925x connect: a CONNECT-phase failure (refused, reset or timed "
           "out in the handshake) ends with the not-sent mark pinrun reads; a "
           "write, a read or a non-OSError failure never carries it (%r)"
           % (str(r)[-40:],))
''')

_got = O.write(EXPECTED_ORDERCLI)
print("patched", OC, _got, "(checked: the reviewed %s)" % EXPECTED_ORDERCLI)
