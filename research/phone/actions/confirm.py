"""phone/actions/confirm.py -- the two-step confirmations every phone action waits on.

v-tg-step12 (2026-10-30, lane R). A question ('Pause Jump band? ... Reply /pause jb yes') leaves ONE pending answer per
chat and kind ('pause', 'resume', 'approve', 'move'); the answer is taken at most once (take() removes it), only within
its time (ttl_s), only for the thing it asked about (key), and -- when the question carried a code -- only with that
code. Three wrong codes drop it. A new question of the same kind replaces the old one. Pending answers live in memory
only: a phone restart forgets them, so a Telegram message delivered again after a restart finds nothing to confirm.
"""
import secrets
import threading

_LOCK = threading.Lock()
_PENDING = {}               # (chat, kind) -> {"key", "code", "plan", "t", "ttl", "bad"}
MAX_BAD = 3


def new_code():
    """A 4-digit code, 1000-9999 (a test replaces CODE)."""
    return "%04d" % (1000 + secrets.randbelow(9000))


CODE = new_code


def ask(chat, kind, key, now, ttl_s, plan=None, code=False):
    """Remember the question; returns its code (str) when code=True, else None."""
    c = CODE() if code else None
    with _LOCK:
        _PENDING[(chat, kind)] = {"key": key, "code": c, "plan": plan, "t": float(now), "ttl": float(ttl_s), "bad": 0}
    return c


def peek(chat, kind, now):
    """The pending question of this kind, if one is still in time (not taken), else None."""
    with _LOCK:
        p = _PENDING.get((chat, kind))
        if p is None or float(now) - p["t"] > p["ttl"]:
            return None
        return dict(p)


def take(chat, kind, now, key=None, code=None):
    """(plan, None) and the question is gone; or (None, why) -- why in words:
    'nothing' (no question waiting), 'expired', 'other' (it asked about another key), 'code' (wrong code; dropped
    after MAX_BAD)."""
    with _LOCK:
        p = _PENDING.get((chat, kind))
        if p is None:
            return None, "nothing"
        if float(now) - p["t"] > p["ttl"] or float(now) < p["t"] - 5:
            del _PENDING[(chat, kind)]
            return None, "expired"
        if key is not None and p["key"] != key:
            return None, "other"
        if p["code"] is not None and str(code or "").strip() != p["code"]:
            p["bad"] += 1
            if p["bad"] >= MAX_BAD:
                del _PENDING[(chat, kind)]
            return None, "code"
        del _PENDING[(chat, kind)]
        return {"key": p["key"], "plan": p["plan"], "t": p["t"]}, None


def drop(chat=None, kind=None):
    """Forget pending questions (all, one chat's, or one chat's of one kind)."""
    with _LOCK:
        for k in list(_PENDING):
            if (chat is None or k[0] == chat) and (kind is None or k[1] == kind):
                del _PENDING[k]
