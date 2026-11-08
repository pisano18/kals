"""ledgercheck.py -- the Kalshi settlement rows no money total books, counted (v-ledger-unreadable, 2026-11-07).

THE PHONE AUDIT: pinledger.money read a missing field as 0, so a renamed Kalshi field would have shown every market as a
total loss (no contracts paid) or as pure profit (nothing cost anything), on every money page, with no error anywhere.
pinledger.unreadable now names such a row (a count, a cost or the fee missing or not a number, or a result with no
usable value) and every money total leaves it out (botdata.money.booked_rows, phone.shared.raw_ledger, pindesk.Ledger,
pinday); a voided market is left out too (Kalshi gives the stake back). This module COUNTS what was left out, over
every pot in botstats' cache and the main account's kalshi_ledger.json (a settlement in both is counted once), so the
operator is told instead of reading a total that quietly lost markets. The words are the phone's
(phone/render/unbooked.py: the line on every money page, the one alert).

  scan(results)   {"unreadable": markets, "void": markets, "examples": [(ticker, why)], "void_examples": [ticker],
                   "by_pot": {pot: markets unreadable}, "error": why the scan failed or None} -- re-read only when one
                   of the two files changes; never raises

A healthy feed trips nothing: 0 of 2,550 main-account rows and 0 of 3,736 cache rows (all six pots), measured 11-07.
"""
import os
import threading

import pinledger
from botdata import kalshi as _kalshi
from botdata import paths as _paths

LEDGER_NAME = "kalshi_ledger.json"
EXAMPLES = 3

_LOCK = threading.Lock()
_MEMO = {"key": None, "out": None}


def _stat(p):
    try:
        st = os.stat(p)
        return (p, st.st_mtime, st.st_size)
    except OSError:
        return (p, None, None)


def empty(err=None):
    return {"unreadable": 0, "void": 0, "examples": [], "void_examples": [], "by_pot": {}, "error": err}


def scan(results=None):
    """What no money total books, over botstats' cache (every pot) and `results`\\kalshi_ledger.json (the main
    account). Remembered until either file changes. Never raises: a failed read gives zero counts and its "error"."""
    led_path = os.path.join(results or _paths.RESULTS, LEDGER_NAME)
    key = (_stat(_kalshi.cache_path()), _stat(led_path))
    with _LOCK:
        if _MEMO["key"] == key:
            return _copy(_MEMO["out"])
    try:
        out = _scan(led_path)
    except Exception as e:                                      # noqa: BLE001
        out = empty("%s: %s" % (type(e).__name__, str(e)[:160]))
    with _LOCK:
        _MEMO.update(key=key, out=out)
    return _copy(out)


def _copy(out):
    return dict(out, examples=list(out["examples"]), void_examples=list(out["void_examples"]),
                by_pot=dict(out["by_pot"]))


def _scan(led_path):
    seen = {}                                   # (pot, key) -> ("unreadable", ticker, why) | ("void", ticker, None)
    c = _kalshi.load_cache()
    for sub, x in sorted((c.get("subs") or {}).items()):
        for k, s in ((x or {}).get("rows") or {}).items():
            _judge(seen, str(sub), k, s)
    for k, s in pinledger.load_cache(led_path).items():
        _judge(seen, "0", k, s)
    out = empty()
    for (pot, _k), (what, tk, why) in sorted(seen.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if what == "unreadable":
            out["unreadable"] += 1
            out["by_pot"][pot] = out["by_pot"].get(pot, 0) + 1
            if len(out["examples"]) < EXAMPLES:
                out["examples"].append((tk, why))
        else:
            out["void"] += 1
            if len(out["void_examples"]) < EXAMPLES:
                out["void_examples"].append(tk)
    return out


def _judge(seen, pot, key, s):
    why = pinledger.unreadable(s)
    tk = s.get("ticker") if isinstance(s, dict) else None
    if why is not None:
        seen[(pot, key)] = ("unreadable", tk, why)
    elif pinledger.is_void(s):
        seen[(pot, key)] = ("void", tk, None)


def forget():
    """Read both files again on the next scan (a test)."""
    with _LOCK:
        _MEMO.update(key=None, out=None)
