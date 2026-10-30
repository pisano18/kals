"""_legacy.py -- OLD against NEW after the integration flip (v-tg-rebuild steps 10-11). Not a test file itself.

Until step 10 the command tests compared a NEW command module with the OLD Phone.text_* method of the same pinphone.
The flip deleted those methods; the frozen pre-step-10 phone is research/pinphone_legacy.py (it still runs as the
launcher's fallback), so the tests compare against IT now:

  OLD   pinphone_legacy: its Phone and its text_* methods, its module globals
  NEW   the helpers module the command modules read as ctx.pp (phone.shared since step 11; pinphone at step 10)

`pp` (Both) is what the tests import as `pp`: reading a name gives OLD's (pp.Phone is the legacy Phone, pp.HELP_TEXT
the legacy roster), setting one sets it on OLD and -- when NEW has the name -- on NEW too, so a planted global reaches
both sides. patch_pairs() expands a (pp, name, value) patch into one patch per module (each put back to its own value).
new_ctx(ph, text) is Ctx.from_phone on the legacy Phone with NEW as ctx.pp: the seams are the very same values.
"""
import importlib
import os
import sys

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinphone_legacy as OLD                                        # noqa: E402

try:
    NEW = importlib.import_module("phone.shared")
except ModuleNotFoundError as _e:                                    # step 10: the helpers still live in pinphone
    if _e.name != "phone.shared":
        raise
    NEW = importlib.import_module("pinphone")


class Both:
    """Read from OLD; write to OLD and (where it has the name) NEW."""

    def __getattr__(self, name):
        try:
            return getattr(OLD, name)
        except AttributeError:          # a name only NEW has (fleet_roles, chart_markets ...): a planted Ctx reads it
            return getattr(NEW, name)

    def __setattr__(self, name, value):
        setattr(OLD, name, value)
        if hasattr(NEW, name):
            setattr(NEW, name, value)


pp = Both()
# Ctx.from_phone(<a legacy Phone>) takes the runtime's `pp` attribute when it has one: every new-side Ctx built on a
# legacy Phone then reads NEW (the legacy Phone's own methods never read self.pp)
OLD.Phone.pp = NEW


def patch_pairs(triples):
    """[(module, name, value)] with every (pp, name, value) split into OLD's and NEW's (NEW only when it has the name)."""
    out = []
    for m, n, v in triples:
        if m is pp:
            out.append((OLD, n, v))
            if hasattr(NEW, n):
                out.append((NEW, n, v))
        else:
            out.append((m, n, v))
    return out


def new_ctx(ph, text="", chat_id=None):
    """The Ctx the router builds for `text`, on the (legacy) Phone `ph`, with NEW as ctx.pp."""
    from phone import context as CX
    c = CX.Ctx.from_phone(ph, text, chat_id=chat_id)
    c.pp = NEW
    return c
