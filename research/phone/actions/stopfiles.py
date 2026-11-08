"""phone/actions/stopfiles.py -- a bot's stop file: the ONLY phone code that writes or removes one.

v-tg-step12 (2026-10-30, lane R). Every registry bot but the pin bot stands down by its OWN rule when its stop file
(Bot.stop_file in results\\) appears: no new orders, and it exits once flat (fxtake_live / jumpband_live / ladder_live /
forecaster_live / pinracearm check it every tick); boot_all.ps1 does not restart a bot whose stop file is there. So a
pause from the phone is exactly that file, and a resume is removing it (boot_all brings a keep-alive bot back within
10 minutes; a bot with a Bot.start recipe is started by the phone, phone/actions/launch.py). The pin bot's flag
(pinrun-live.stop) is NOT handled here: /pause /start keep pindesk's own controls (phone/commands/controls.py).

Paths are botdata.paths.RESULTS at call time (a test points it at a temp folder); every write passes
botdata.paths.check_write (KALS_TESTING=1 refuses the live results folder).

v-kwatch (2026-11-07): the Kalshi watch's off switch lives here too (watch_*): results\\kalshi_watch.stop, which
research\\kalshi_watch.py obeys (every scheduled scan exits at once while it is there). It is not a registry bot; the
/watch module (phone/commands/watch_cmd.py) is its only caller.
"""
import os
import time

import bots as _bots
from botdata import paths as _paths

PIN = "pin"


def path_of(name):
    """The stop file of registry bot `name` (KeyError-free: AttributeError for a name that is no bot)."""
    return os.path.join(_paths.RESULTS, _bots.get(name).stop_file)


def is_set(name):
    try:
        return os.path.exists(path_of(name))
    except (OSError, AttributeError):
        return False


def since(name):
    """The stop file's mtime (epoch), or None."""
    try:
        return os.path.getmtime(path_of(name))
    except (OSError, AttributeError):
        return None


def text_of(name, limit=300):
    """The stop file's first `limit` characters (who wrote it and why), '' when unreadable or absent."""
    try:
        with open(path_of(name), encoding="utf-8", errors="replace") as fh:
            return fh.read(limit).strip()
    except (OSError, AttributeError):
        return ""


def write(name, why, now=None):
    """Write bot `name`'s stop file (never the pin bot's). Returns its path. Raises on failure (the caller says it)."""
    if name == PIN:
        raise ValueError("the pin bot's flag is pindesk's (/pause), not a phone stop file")
    p = path_of(name)
    _paths.check_write(p)
    t = time.time() if now is None else float(now)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("%s -- written by the phone (/pause) %s. Delete this file, or send /resume on the phone, to resume.\n"
                 % (why, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))))
    return p


def remove(name):
    """Remove bot `name`'s stop file (never the pin bot's). True when it was there and is gone, False when it was not
    there. Raises on failure."""
    if name == PIN:
        raise ValueError("the pin bot's flag is pindesk's (/start), not a phone stop file")
    p = path_of(name)
    _paths.check_write(p)
    try:
        os.remove(p)
    except FileNotFoundError:
        return False
    return True


# ---- the Kalshi watch's off switch (v-kwatch) --------------------------------------------------------------------------
WATCH = "kalshi_watch.stop"                     # research/kalshi_watch.py STOP_NAME


def watch_path():
    return os.path.join(_paths.RESULTS, WATCH)


def watch_since():
    """When /watch off was sent (the file's mtime, epoch), or None: the watch is on."""
    try:
        return os.path.getmtime(watch_path())
    except OSError:
        return None


def watch_write(why, now=None):
    """Write the Kalshi watch's stop file. Returns its path. Raises on failure (the caller says it)."""
    p = watch_path()
    _paths.check_write(p)
    t = time.time() if now is None else float(now)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("%s -- written by the phone (/watch off) %s. Send /watch on (or delete this file) to turn the Kalshi "
                 "watch back on.\n" % (why, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))))
    return p


def watch_remove():
    """Remove it: True when it was there and is gone, False when it was not there. Raises on failure."""
    p = watch_path()
    _paths.check_write(p)
    try:
        os.remove(p)
    except FileNotFoundError:
        return False
    return True
