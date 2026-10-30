"""phone/transport.py -- Telegram itself: getUpdates, sendMessage (Html with parse_mode=HTML, re-sent as plain text when
Telegram refuses the markup), sendPhoto (multipart, photo_body); net_error (is a failed send worth sending again);
FakeTelegram for the self-tests.

v-tg-rebuild step 6 (2026-10-30): moved verbatim out of research/pinphone.py, which re-exports every name here
(results/research_2026-10/scripts/phone_alert.py uses pinphone.Telegram). The resend queue stays in pinphone.Phone (it
is the Phone's state: _resend, resend_tick). The only module of the phone that opens a URL (DESIGN section 2's rule;
the AWS reader at /server is the other).
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from phone.html import MAX_LEN, html_to_plain, split_html, split_text
from phone.log import log


# ===========================================================================
# transport
# ===========================================================================
class Telegram:
    def __init__(self, token):
        self.base = "https://api.telegram.org/bot%s/" % token

    def _call(self, method, params, http_timeout=45):
        data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
        req = urllib.request.Request(self.base + method, data=data)
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def get_updates(self, offset, timeout=25):
        d = self._call("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'},
                       http_timeout=timeout + 15)
        return d.get("result", []) if d.get("ok") else []

    def send(self, chat_id, text):
        """A plain str goes exactly as it always did. An Html reply goes with parse_mode=HTML, cut by
        split_html; if Telegram refuses a part's markup (HTTP 400, "can't parse entities") that part is
        sent again as plain text, so a formatting slip never costs a message. Any other failure is
        raised as before (say() logs it)."""
        if not getattr(text, "is_html", False):
            for chunk in split_text(text, MAX_LEN):
                self._call("sendMessage", {"chat_id": chat_id, "text": chunk})
            return
        for chunk in split_html(text, MAX_LEN):
            try:
                self._call("sendMessage", {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"})
            except urllib.error.HTTPError as e:
                if e.code != 400:
                    raise
                log("Telegram refused the HTML of one part (%s); sent it again as plain text" % e)
                for part in split_text(html_to_plain(chunk), MAX_LEN):
                    self._call("sendMessage", {"chat_id": chat_id, "text": part})

    def _post(self, method, body, ctype, http_timeout=60):
        req = urllib.request.Request(self.base + method, data=body, headers={"Content-Type": ctype})
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def send_photo(self, chat_id, png, caption=None):
        """One chart: sendPhoto, multipart (photo_body). The caption is plain text (no markup to refuse)."""
        boundary = "pinphone" + os.urandom(12).hex()
        d = self._post("sendPhoto", photo_body(chat_id, png, caption, boundary),
                       "multipart/form-data; boundary=" + boundary)
        if not (isinstance(d, dict) and d.get("ok")):
            raise RuntimeError("sendPhoto refused: %s" % (str(d)[:200],))


def photo_body(chat_id, png, caption, boundary):
    """multipart/form-data for sendPhoto: chat_id, caption (cut to Telegram's 1024), the PNG as `photo`."""
    B = boundary.encode()
    crlf = b"\r\n"
    out = []
    for k, v in (("chat_id", str(chat_id)), ("caption", (caption or "")[:1024] or None)):
        if v is not None:
            out.append(b"--" + B + crlf + b'Content-Disposition: form-data; name="' + k.encode() + b'"' + crlf + crlf
                       + v.encode("utf-8") + crlf)
    out.append(b"--" + B + crlf + b'Content-Disposition: form-data; name="photo"; filename="chart.png"' + crlf
               + b"Content-Type: image/png" + crlf + crlf + bytes(png) + crlf)
    out.append(b"--" + B + b"--" + crlf)
    return b"".join(out)


def get_url(url, timeout=10):
    """One GET of `url` -- the outside 'is it alive' ping (phone/alive.py; step 12, lane Q). Returns the HTTP status;
    raises on a network error or an HTTP error status (the caller logs it). Reads at most 1 KB of the answer."""
    req = urllib.request.Request(url, headers={"User-Agent": "kals-phone-alive/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read(1024)
        return int(getattr(r, "status", 200) or 200)


def net_error(e):
    """True when a send failed on the CONNECTION (no answer, reset, TLS timeout, Telegram 5xx or 429) -- worth
    sending again. False when Telegram refused the message itself (HTTP 4xx), which a resend would only repeat."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code == 429
    import http.client
    return isinstance(e, (OSError, http.client.HTTPException))


class FakeTelegram:
    """For the self-test: a queue of incoming messages and a list of sent ones."""
    def __init__(self):
        self.incoming = []
        self.sent = []
        self.photos = []
        self.n = 0

    def push(self, chat_id, text):
        self.n += 1
        self.incoming.append({"update_id": self.n, "message": {"chat": {"id": chat_id}, "text": text}})

    def get_updates(self, offset, timeout=25):
        out = [u for u in self.incoming if u["update_id"] >= (offset or 0)]
        return out

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def send_photo(self, chat_id, png, caption=None):
        self.photos.append((chat_id, png, caption))
