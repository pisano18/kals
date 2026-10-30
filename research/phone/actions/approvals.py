"""phone/actions/approvals.py -- the changes waiting for the operator's yes: results\\approvals\\approvals.json, and which ran.

v-tg-step12 (2026-10-30, lane R; the operator: "approve waiting changes from the phone" -- yes). A change the assistant
may not make itself (the classifier keeps it off the live launcher, boot_all and the trading bots) is written as a
PowerShell script in results\\ and listed here; the operator runs it from the phone with /approve <id> and a code.

THE MANIFEST (results\\approvals\\approvals.json, in git): {"items": [{id, title, description, stop_rule, script, log,
added_by, date, sha256}, ...]}
  id        lower-case letters, digits and '-', at most 24 characters: what the operator types
  script    a .ps1 file named relative to results\\ (launch.resolve_script: inside the results folder, no '..', exists)
  log       the file it writes, relative to results\\ (its new lines are read back when it ends)
  sha256    of the script's text (CRLF -> LF, BOM dropped): a script edited after it was listed is NOT run
  superseded_by   (optional) the id of a later item that does this change too: this one is listed apart and never runs
Nothing typed in the chat reaches the command line: the script runs with NO arguments, exactly as listed.

THE STATE (results\\approvals\\state.json, not in git): {id: {status, t, ...}}. Each item runs ONCE: 'running' is written
BEFORE the launch, 'done' (exit code, the log's new lines) after it ends; only an item whose launch never started a
process ('failed_to_start') may be tried again.
"""
import hashlib
import json
import os
import re

from botdata import paths as _paths
from phone.actions import launch as _launch

DIR = "approvals"
MANIFEST = "approvals.json"
STATE = "state.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
FIELDS = ("id", "title", "description", "script", "added_by", "date", "sha256")
RAN = ("running", "done")                       # an item in one of these never runs again


def folder():
    return os.path.join(_paths.RESULTS, DIR)


def manifest_path():
    return os.path.join(folder(), MANIFEST)


def state_path():
    return os.path.join(folder(), STATE)


def text_sha(path):
    """sha256 of a script's TEXT: CRLF -> LF, a UTF-8 BOM dropped (so a git checkout's line endings do not matter)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load():
    """(items, None) or ([], why). items: [dict] as listed (each checked by check(); a bad one keeps its 'bad' reason)."""
    try:
        with open(manifest_path(), encoding="utf-8") as fh:
            d = json.load(fh)
    except FileNotFoundError:
        return [], "no list of waiting changes (results\\approvals\\approvals.json is not there)"
    except (OSError, ValueError) as e:
        return [], "the list of waiting changes could not be read: %s" % str(e)[:160]
    items = d.get("items") if isinstance(d, dict) else None
    if not isinstance(items, list):
        return [], "the list of waiting changes has no 'items' list"
    out, seen = [], set()
    for it in items:
        if not isinstance(it, dict):
            continue
        it = dict(it)
        it["bad"] = None
        miss = [f for f in FIELDS if not isinstance(it.get(f), str) or not it.get(f)]
        if miss:
            it["bad"] = "missing %s" % ", ".join(miss)
        elif not ID_RE.match(it["id"]):
            it["bad"] = "its id is not a short lower-case name"
        elif it["id"] in seen:
            it["bad"] = "its id is listed twice"
        elif it.get("superseded_by"):                            # v-fx-onepot: a later item carries this change too
            it["bad"] = "superseded by %s: run that one instead" % it["superseded_by"]
        seen.add(it.get("id"))
        out.append(it)
    return out, None


def check(it):
    """(full script path, None) when item `it` may run now, else (None, why in words)."""
    if it.get("bad"):
        return None, it["bad"]
    if "args" in it or "arguments" in it:
        return None, "it lists arguments; a listed script runs with none"
    try:
        path = _launch.resolve_script(it["script"])
    except ValueError as e:
        return None, str(e)
    log = it.get("log")
    if log and (os.path.isabs(log) or ".." in log.replace("\\", "/").split("/")):
        return None, "its log must be named relative to the results folder"
    try:
        sha = text_sha(path)
    except OSError as e:
        return None, "the script could not be read: %s" % e
    if sha != it["sha256"].lower():
        return None, ("the script changed after it was listed (its text's sha256 is %s, the list says %s): it is not "
                      "run until the list is updated" % (sha[:12], it["sha256"][:12]))
    return path, None


def find(items, ident):
    ident = str(ident or "").strip().lower()
    return next((it for it in items if it.get("id") == ident), None)


def log_path(it):
    return os.path.join(_paths.RESULTS, it["log"]) if it.get("log") else None


def read_state():
    try:
        with open(state_path(), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def set_state(ident, **fields):
    """Merge fields into state[ident] and write state.json whole (a temp file, then os.replace). Raises on failure."""
    st = read_state()
    cur = dict(st.get(ident) or {})
    cur.update(fields)
    st[ident] = cur
    p = state_path()
    _paths.check_write(p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1, sort_keys=True)
    os.replace(tmp, p)
    return cur


def size_of(path):
    try:
        return os.path.getsize(path)
    except (OSError, TypeError):
        return 0


def new_lines(path, offset, n=15):
    """The log's lines written after byte `offset` (the last n of them); [] when nothing new or unreadable."""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, int(offset)))
            raw = fh.read(65536)
    except (OSError, TypeError):
        return []
    txt = raw.decode("utf-8", errors="replace").lstrip("﻿")
    lines = [x.rstrip() for x in txt.splitlines() if x.strip()]
    return lines[-n:]
