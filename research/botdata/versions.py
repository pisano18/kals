"""versions.py -- each bot's running version: the newest VERSIONS.md heading that is its own (version_of; the
ownership rule is the registry's bots.version_claim). Headings written before going live (INSTALLED / PREPARED), for
something stopped for good (KILLED / STOPPED / REVERTED / DEAD / WITHDRAWN) or about the phone / PC / recorders
(INFRA_VER) are no bot's running version.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata). pinphone
keeps its own VERSIONS parser (_VER_RE / _NOT_PIN_RE) until its step moves to this one.
"""
import calendar
import os
import re
import time

import bots as _reg
from bots import pin as _b_pin
from botdata import paths as _paths


VERSIONS_NAME = "VERSIONS.md"

# ---- VERSIONS.md headings ----------------------------------------------------
_VER = re.compile(r"^#\s+(v-[\w.-]+(?:\s*\+\s*v-[\w.-]+)*)\s+--\s+(.*)$")
# the weather dip-seller's VERSIONS.md entries (v-dipsell-live ...); pinphone._NOT_PIN_RE carries the same words
WX_VER = _b_pin.WX_VER                          # r"dipsell|dip.?sell" (bots/pin.py, bots/weather.py)
_VER_T = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+~?(\d{2}):(\d[\dx])(?::(\d{2}))?Z?)?", re.I)
# VERSIONS.md entries that change the phone, the PC or the recorders -- never a trading bot's version (2026-10-23)
INFRA_VER = r"v-(tg|phone|telegram|wifi|recorder|collector)\b"


def version_of(name):
    """The newest VERSIONS.md heading for this bot: (name, epoch or None, title) or None."""
    try:
        with open(os.path.join(_paths.RESULTS, VERSIONS_NAME), encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    for line in lines:
        m = _VER.match(line.rstrip())
        if not m:
            continue
        vname, rest = m.group(1), m.group(2)
        # 2026-10-18: a heading written BEFORE it goes live ('-- INSTALLED <date> ... LIVE at the next restart',
        # '-- PREPARED <date>') is not the running version. The phone's /stats parser (pinphone._VER_RE) never took
        # one; this one did, so /pin named v-nopause live while v-ladderboost ran (and pinphone's DRIFT check failed).
        if re.match(r"(INSTALLED|PREPARED)\b", rest.strip()):
            continue
        # 2026-10-23: a heading for something that was STOPPED for good is no bot's running version (the coin race
        # showed 'v-racev2-live-test', the killed reward test); nor is a phone / PC / recorder change (INFRA_VER)
        # 2026-10-29: WITHDRAWN too (v-wrongside2 was built and withdrawn before it ran; /pin named it live)
        if re.match(r"(KILLED|STOPPED|REVERTED|DEAD|WITHDRAWN)\b", rest.strip()) or re.match(INFRA_VER, vname):
            continue
        # 2026-10-01: a heading that ships several bots at once names every bot and belongs to each bot one of its
        # names is about; a single heading is a bot's when it is about that bot alone (its own v-fx / v-jb name wins
        # over words about the pots it shares); the pin bot's is every heading no other bot claims and no clean-room
        # word names. v-tg-rebuild step 3 (2026-10-30): that rule is the registry's (bots.version_claim, each bot's
        # VersionRule) -- the old per-bot dicts and flags, verbatim, moved there.
        shown = _reg.version_claim(name, vname, rest)
        if shown is None:
            continue
        t = None
        mt = _VER_T.search(rest)
        if mt:
            day, hh, mm = mt.group(1), mt.group(2), mt.group(3)
            try:
                t = float(calendar.timegm(time.strptime(
                    "%sT%s:%s" % (day, hh or "00", (mm or "00").lower().replace("x", "0")), "%Y-%m-%dT%H:%M")))
            except ValueError:
                t = None
        return shown, t, rest.strip()
    return None
