"""phone/alive.py -- the outside 'is it alive' check (v-tg-rebuild step 12, lane Q, 2026-10-30).

Nothing inside the server can say the server itself has died. So, every EVERY_S (5 min) while the phone is running
and the bots are healthy (no bot DOWN past its debounce: phone/monitor.py), the phone GETs one URL the operator makes
at a free monitoring service (a 'heartbeat' / 'cron' check, e.g. healthchecks.io: period 5 min, grace 10 min). When
the GETs stop -- the server off, the phone dead, Windows stuck, a bot down -- that service emails or texts the operator.

The URL is in the phone's config file next to the pairing (telegram.json "alive_url"; empty = off), set from the phone
with /alive set <url> (phone/commands/alive_cmd.py). The GET goes through phone/transport.py (the one module that opens
a URL), on its own short thread so the poll loop never waits for it (RUN_IN_THREAD; the tests run it inline). A failed
GET is logged and counted; it never raises and never alerts (the outside service is the alert).
"""
import threading
from dataclasses import dataclass

from phone.log import log

KEY = "alive_url"
EVERY_S = 300
TIMEOUT_S = 10
RUN_IN_THREAD = True
GET = None                              # None = phone.transport.get_url (tests plant their own)


@dataclass
class AliveState:
    """What the pinger remembers (on the monitor's state: m.alive)."""
    last_t: float = None                # when the last GET was started
    last_ok_t: float = None             # when a GET last answered 2xx
    last_status: object = None          # its HTTP status, or the error's words
    ok: int = 0                         # GETs answered since the phone started
    failed: int = 0
    skipped_why: str = None             # why the last due ping was skipped (a bot down), None when it went
    busy: bool = False                  # a GET is in flight


def url_of(cfg):
    u = str((cfg or {}).get(KEY) or "").strip()
    return u or None


def valid(url):
    """True for an http(s) URL with a host and no spaces."""
    u = str(url or "")
    return u.lower().startswith(("https://", "http://")) and "." in u.split("/")[2] if u.count("/") >= 2 else False


def masked(url):
    """'hc-ping.com/…c0ffee': the host and the last 6 characters (the rest is the operator's secret)."""
    u = str(url or "")
    host = u.split("/")[2] if u.count("/") >= 2 else u
    return "%s/…%s" % (host, u[-6:]) if len(u) > len(host) + 10 else host


def _get(url):
    fn = GET
    if fn is None:
        from phone import transport
        fn = transport.get_url
    return fn(url, timeout=TIMEOUT_S)


def ping(a, url, now):
    """One GET; records the answer on AliveState `a`. Never raises."""
    try:
        st = _get(url)
        a.last_status = st
        if 200 <= int(st) < 300:
            a.ok += 1
            a.last_ok_t = now
        else:
            a.failed += 1
            log("alive ping: HTTP %s from %s" % (st, masked(url)))
    except Exception as e:                                      # noqa: BLE001
        a.failed += 1
        a.last_status = "%s: %s" % (type(e).__name__, str(e)[:120])
        log("alive ping failed (%s): %s" % (masked(url), a.last_status))
    finally:
        a.busy = False


def unhealthy(m):
    """Why the bots are not healthy now (a bot DOWN past its debounce), or None."""
    down = sorted(n for n, e in (getattr(m, "down", None) or {}).items() if e.get("sent"))
    if down:
        from phone.monitor import label
        return "%s %s down" % (", ".join(label(n) for n in down), "is" if len(down) == 1 else "are")
    return None


def check(ctx, m, send, now):
    """The monitor's check: a GET when one is due, the URL is set and the bots are healthy."""
    a = getattr(m, "alive", None)
    if a is None:
        a = m.alive = AliveState()
    url = url_of(ctx.cfg)
    if url is None or not valid(url) or a.busy:
        return
    if a.last_t is not None and 0.0 <= now - a.last_t < EVERY_S:
        return
    why = unhealthy(m)
    a.skipped_why = why
    if why is not None:
        return                                          # no ping: the outside service notices the silence
    a.last_t, a.busy = now, True
    if RUN_IN_THREAD:
        threading.Thread(target=ping, args=(a, url, now), name="alive-ping", daemon=True).start()
    else:
        ping(a, url, now)


__all__ = ["KEY", "EVERY_S", "AliveState", "url_of", "valid", "masked", "ping", "check", "unhealthy"]
