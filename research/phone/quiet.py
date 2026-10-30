"""phone/quiet.py -- quiet hours (v-tg-rebuild step 12, lane Q, 2026-10-30; the operator: "only urgent alerts overnight").

The setting lives in the phone's own config file next to the pairing (telegram.json, never the repo): "quiet_hours":
[23, 7] (from 11 PM to 7 AM ET, the default when the key is absent) or "off". /quiet shows it, /quiet 23-7 sets it,
/quiet off and /quiet on (phone/commands/quiet_cmd.py).

While it is quiet only URGENT alerts are sent: a bot DOWN (and back), a stop tripped, a single loss over $50 or 3% of
its pot, a balance mismatch, and the pin bot's state changes (its crash / halt alert). Everything else is held (in
memory: a restart in the night loses what was held) and sent as ONE summary at the first tick after quiet hours end.
It applies only where the runtime runs the monitor (Phone.monitor_on); muted, nothing is sent or held.
"""
import re

from pindesk import et_str

KEY = "quiet_hours"
DEFAULT = (23, 7)
OFF = "off"
URGENT_LOSS_USD = 50.0                  # a single loss this big is urgent ...
URGENT_LOSS_FRAC = 0.03                 # ... or this big a share of its pot


def hours(cfg):
    """(start hour, end hour) ET, or None when off. A bad stored value reads as the default."""
    v = (cfg or {}).get(KEY, list(DEFAULT))
    if v == OFF or v is False or v is None:
        return None
    try:
        a, b = int(v[0]), int(v[1])
        if 0 <= a <= 23 and 0 <= b <= 23 and a != b:
            return a, b
    except (TypeError, ValueError, IndexError, KeyError):
        pass
    return DEFAULT


def hour_words(h):
    return "%d %s" % (h % 12 or 12, "AM" if h < 12 else "PM")


def words(cfg):
    """'11 PM to 7 AM ET', or 'off'."""
    h = hours(cfg)
    return "off" if h is None else "%s to %s ET" % (hour_words(h[0]), hour_words(h[1]))


def is_quiet(cfg, now):
    """True while the ET wall clock is inside the quiet hours."""
    h = hours(cfg)
    if h is None:
        return False
    hh = int(et_str(now, "%H"))
    a, b = h
    return (a <= hh < b) if a < b else (hh >= a or hh < b)


def parse(arg):
    """/quiet's argument: ('show',), ('off',), ('on',), ('set', (a, b)) or ('bad', why)."""
    a = (arg or "").strip().lower()
    if not a:
        return ("show",)
    if a in ("off", "none", "no", "0"):
        return ("off",)
    if a in ("on", "default", "yes"):
        return ("on",)
    m = re.match(r"^(\d{1,2})(?::00)?\s*(?:-|to)\s*(\d{1,2})(?::00)?$", a)
    if not m:
        return ("bad", "write it as two hours of the 24-hour clock, ET: /quiet 23-7")
    x, y = int(m.group(1)), int(m.group(2))
    if not (0 <= x <= 23 and 0 <= y <= 23):
        return ("bad", "an hour is 0 to 23 (ET): /quiet 23-7")
    if x == y:
        return ("bad", "the start and the end are the same hour -- /quiet off turns quiet hours off")
    return ("set", (x, y))


def loss_is_urgent(net, bank):
    """A single loss over $50, or over 3% of its pot (bank: the pot before it, or None)."""
    loss = -float(net or 0.0)
    return loss >= URGENT_LOSS_USD or (bool(bank) and loss >= URGENT_LOSS_FRAC * float(bank))


__all__ = ["KEY", "DEFAULT", "OFF", "hours", "words", "is_quiet", "parse", "loss_is_urgent", "hour_words"]
