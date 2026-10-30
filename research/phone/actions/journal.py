"""phone/actions/journal.py -- every phone action, one JSON line in results\\phone_actions.jsonl.

v-tg-step12 (2026-10-30, lane R). The operator acts from the phone while away: what was done, when, from which chat and
with what result must be on disk, not only in the chat. record() NEVER RAISES (a full disk or the test fence costs the
line, logged, never the action's answer). read() gives the records back (the money module's daily limit counts them).
"""
import json
import os
import threading
import time

from botdata import paths as _paths
from phone.log import log

NAME = "phone_actions.jsonl"
_LOCK = threading.Lock()


def path():
    """The journal file now (botdata.paths.RESULTS at call time: a test points it at a temp folder)."""
    return os.path.join(_paths.RESULTS, NAME)


def record(kind, t=None, **fields):
    """Append one record {t, utc, kind, ...fields}; True when written. Never raises."""
    t = time.time() if t is None else float(t)
    rec = {"t": round(t, 3), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)), "kind": kind}
    rec.update(fields)
    p = path()
    try:
        _paths.check_write(p)
        line = json.dumps(rec, sort_keys=True, default=str)
        with _LOCK:
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return True
    except Exception as e:                                      # noqa: BLE001
        log("phone_actions journal: could not write %s: %s" % (kind, e))
        return False


def read(kinds=None, since=None):
    """[record] in file order (kinds: only these; since: t >= since). A bad line is skipped; no file -> []."""
    out = []
    try:
        with open(path(), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict):
                    continue
                if kinds is not None and r.get("kind") not in kinds:
                    continue
                if since is not None and float(r.get("t") or 0) < since:
                    continue
                out.append(r)
    except OSError:
        return []
    return out
