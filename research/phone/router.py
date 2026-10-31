"""phone/router.py -- one message in, one reply out: which command answers it, and the rules every command shares.

v-tg-rebuild step 10 (2026-10-30): the integration flip. Phone.handle's ~40-branch if-chain is gone; dispatch() routes a
message to the Command its research/phone/commands/<x>.py declared (phone/command.py), with the rules Phone.handle had,
in its order:

  1. /pair first, before the paired-chat check and WITHOUT the ledger refresh: it is the one command another (or no)
     chat may send. Its Ctx carries the MESSAGE's chat (the chat that pairs).
  2. Only the paired chat is answered; anything else -> None (silence).
  3. The ledger is refreshed for every command that needs it (all of them today but /pair) and for unknown text, as
     Phone.handle refreshed for every message after the chat check.
  4. A paused / stopped / retired bot's own command (/race, /fc, /wx ... while it is not ACTIVE) answers the short
     'X is not running now ...' page (Phone.text_hidden, verbatim: hidden_reply).
  5. The Command runs (Command.run: its `fail` turns an exception into the old 'Could not build /x: ...' answer; a
     command with no `fail` lets the exception out, and the poll loop answers 'error: ...' as it always did).
  6. Nothing claims the message -> help_cmd.unknown_reply ('I did not understand that.' + /help).

FAULT ISOLATION (DESIGN section 2). Every command module is imported inside a try (discover(): phone.command.discover
does one module at a time). A module that fails to import costs only its own commands: their names answer 'this command
failed to load: ...' (logged), the rest of the phone keeps working, and the import is tried again on each such message
(a fixed file is picked up without a restart). The names of a module that never imported are read from its source text
(its quoted '/names'; a registry bot's command belongs to the module that declares the one-bot pages).

/help is built from the declared Commands (help_cmd.use_commands, once discover() has run): the same sections, order and
lines as the static HELP_TEXT of before, the one-bot lines from the registry filtered by the ACTIVE rule.

The chart after a reply is the declaring Command's (Command.kind_of): kind_of() / chart_kinds() here; the drawing side's
table (phone.charts.CMD_KIND) is held equal to it by phone/tests/test_router.py.
"""
import importlib
import importlib.util
import os
import re
import threading
import traceback

import bots as _bots
from phone import command as _cmd
from phone.context import Ctx
from phone.html import Html, esc, i_
from phone.log import log

PACKAGE = "phone.commands"
HELP_MODULE = PACKAGE + ".help_cmd"
PAIR = "/pair"

_LOCK = threading.RLock()
_STATE = {"done": False, "failed": {}}          # discover() ran; {module: the exception of its last import attempt}


# ---- discovery ---------------------------------------------------------------------------------------------------------
def _use_help():
    """/help from the declared Commands (never raises: a broken help module keeps its static rows)."""
    try:
        importlib.import_module(HELP_MODULE).use_commands(_cmd.commands())
    except Exception:                                           # noqa: BLE001
        log("help could not be rebuilt from the commands:\n%s" % traceback.format_exc())


def discover(force=False):
    """Import every command module once (each inside its own try); {module: exception} of those that failed (logged).
    Never raises. force=True imports again (a test, or a module fixed on disk)."""
    with _LOCK:
        if _STATE["done"] and not force:
            return dict(_STATE["failed"])
        try:
            failed = _cmd.discover(PACKAGE)
        except Exception as e:                                  # noqa: BLE001  (the package itself is broken)
            log(traceback.format_exc())
            failed = {PACKAGE: e}
        for name, e in sorted(failed.items()):
            log("command module %s failed to load: %s: %s" % (name, type(e).__name__, e))
        _STATE.update(done=True, failed=dict(failed))
        _use_help()
        return dict(failed)


def failed_modules():
    """{module: exception} of the command modules that did not import (discover() first)."""
    discover()
    return dict(_STATE["failed"])


def _retry_failed():
    """Import each failed module again (lazy import inside a try); those that now import are declared and dropped from
    the failed list (and /help is rebuilt)."""
    with _LOCK:
        fixed = False
        for name in list(_STATE["failed"]):
            try:
                importlib.import_module(name)
            except Exception as e:                              # noqa: BLE001
                _STATE["failed"][name] = e
                continue
            del _STATE["failed"][name]
            fixed = True
            log("command module %s loads now" % name)
        if fixed:
            _use_help()


def _source_of(module):
    """The text of a module's file (a package: every .py file in it), or '' when it cannot be found or read."""
    try:
        spec = importlib.util.find_spec(module)
    except Exception:                                           # noqa: BLE001
        return ""
    if spec is None or not spec.origin:
        return ""
    files = [spec.origin]
    if spec.submodule_search_locations:
        d = os.path.dirname(spec.origin)
        files = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".py")]
    out = []
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                out.append(fh.read())
        except OSError:
            pass
    return "\n".join(out)


def owner_of_broken(cmd):
    """(module, exception) when `cmd` belongs to a command module that failed to import, else None. Its names are read
    from its source (a quoted '/name'); a registry bot's command (/pin, /fc ...) with no live declaration belongs to a
    failed module that builds the one-bot pages from the registry (BOT_CMDS)."""
    failed = _STATE["failed"]
    if not failed:
        return None
    rx = re.compile(r"""["']%s["']""" % re.escape(cmd))
    srcs = {m: _source_of(m) for m in failed}
    for m, e in sorted(failed.items()):
        if rx.search(srcs[m]):
            return m, e
    if _bots.by_command(cmd) is not None:
        for m, e in sorted(failed.items()):
            if "BOT_CMDS" in srcs[m]:
                return m, e
    if PACKAGE in failed:                       # the whole package failed: every command is that module's
        return PACKAGE, failed[PACKAGE]
    return None


def command_for(cmd):
    """(Command or None, (module, exception) or None): the Command declared for `cmd`; else, when a module that failed
    to import owns it, that module and its error (after one more import attempt)."""
    discover()
    c = _cmd.by_name(cmd)
    if c is not None:
        return c, None
    if _STATE["failed"]:
        _retry_failed()
        c = _cmd.by_name(cmd)
        if c is not None:
            return c, None
        return None, owner_of_broken(cmd)
    return None, None


def commands():
    """Every declared Command (discover() first)."""
    discover()
    return _cmd.commands()


# ---- charts -------------------------------------------------------------------------------------------------------------
def kind_of(cmd):
    """The picture after `cmd`'s words (its Command's chart for that name), or None."""
    discover()
    c = _cmd.by_name(cmd)
    return c.kind_of(cmd) if c is not None else None


def chart_kinds():
    """{name: kind} for every declared name that has a picture (== phone.charts.CMD_KIND, test_router)."""
    out = {}
    for c in commands():
        for n in c.names:
            k = c.kind_of(n)
            if k is not None:
                out[n] = k
    return out


# ---- the answers the router itself gives ---------------------------------------------------------------------------
def hidden_reply(ctx, name):
    """The answer to a paused or retired bot's own command (/race, /fc, /wx ... while it is not active). Phone.text_hidden,
    verbatim."""
    from phone.render.botcards import BOT_CMD_OF, strategy_html
    bs = ctx.bs()
    label = bs.SPEC[name]["label"] if name in bs.SPEC else name
    why = "its stop file is set" if bs.stop_set(name) else "no live copy of it is running"
    st = strategy_html(name)                     # v-tg-strategy: what it does, even while it is not running
    return Html("⏸ <b>%s is not running now</b> (%s), so it is left off every page and /help.\n%s%s\n%s" % (
        esc(label), esc(why), ("\n".join(st) + "\n") if st else "",
        i_("It comes back by itself -- here, in /help, /bots and the rest -- once it runs "
           "again with no stop file. Its past money stays in every total, on the 'earlier bots' "
           "line of /bots."),
        i_("The bots running now: %s" % " ".join(BOT_CMD_OF.get(b, "/" + b) for b in ctx.active()))))


def failed_reply(cmd, module, err):
    """A command whose module did not import: say so (logged); everything else still works."""
    log("%s: this command failed to load: %s: %s: %s" % (cmd, module, type(err).__name__, err))
    return "%s: this command failed to load: %s: %s\nEverything else still works -- /help lists the commands." % (
        cmd, type(err).__name__, str(err)[:200])


def unknown(ctx):
    """Nothing claims the message: help_cmd.unknown_reply (the words, then /help); plain words if that module is
    broken."""
    try:
        help_cmd = importlib.import_module(HELP_MODULE)
    except Exception as e:                                      # noqa: BLE001
        log("help module failed to load: %s" % e)
        return "I did not understand that. (/help failed to load: %s)" % str(e)[:200]
    return help_cmd.unknown_reply(ctx)


# ---- dispatch -----------------------------------------------------------------------------------------------------------
def dispatch(phone, chat_id, text):
    """The reply for one incoming message to `phone` (the runtime: phone.app.Phone), or None to ignore it. Phone.handle's
    rules, in its order (see the module note). A command with no `fail` may raise: the poll loop answers 'error: ...'."""
    ctx = Ctx.from_phone(phone, text, chat_id=chat_id)
    cmd = ctx.cmd
    if cmd == PAIR:
        c, broken = command_for(PAIR)
        if c is None:
            if broken:
                log("refused pairing from chat %s: %s failed to load: %s" % (chat_id, broken[0], broken[1]))
            return None
        return c.run(ctx)
    if phone.chat_id is None or chat_id != phone.chat_id:
        return None                                  # not ours: silence
    c, broken = command_for(cmd)
    if c is None or c.needs_ledger:
        phone.ledger.refresh()
    bot = _bots.by_command(cmd)                     # v-tg-active: a paused or retired bot's own command
    if bot is not None and bot.name not in ctx.active():
        return hidden_reply(ctx, bot.name)
    if c is not None:
        return c.run(ctx)
    if broken:
        return failed_reply(cmd, *broken)
    return unknown(ctx)
