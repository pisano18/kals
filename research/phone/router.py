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

v-tg-stale (2026-11-07, the phone audit: the phone starts polling with offset None and never looked at a message's date,
so a '/stop yes', '/start' or '/pause' queued while it was down ran hours late). A CONTROL (Command.is_control: every
'controls' command, /pair, /alive) whose Telegram message is older than STALE_S (5 minutes) when it is handled is NOT
run: the chat is told it was ignored and why (stale_reply), in words that never repeat a secret (Command.echo: /pair's
secret, /alive's ping URL -- the reply and its log line both). An old /pair from a stranger while paired: no answer to
it, and the paired chat is told (pair.stale). A message with no date is handled as fresh: the self-tests' FakeTelegram,
and every message of a poll the runtime re-armed promptly after a short batch (phone/app.py PROMPT_GAP_S: delivered at
once, so a fast server clock can never lock the controls out).
v-tg-unknown (2026-11-08, the operator: "I keep getting that error in telegram" -- nine 'I did not understand that.'
answers since 11-06, each seconds after a page or a photo, and no trace of what had arrived). The poll loop now
describes every update (phone/incoming.py: its kind, text or caption, reply, forwarded) and hands it in as `about`;
dispatch: a SILENT kind (an edited message, a reaction, a callback, a service message such as 'pinned_message', an
unrecognised update) is never run and never answered, one log line ('ignored from chat 7: service message
(pinned_message)'), BEFORE the /pair rule (an edited '/pair' or '/stop yes' never acts); a MEDIA message from the paired
chat (a sticker, photo, voice ...) gets help_cmd.media_reply, one line without the /help list, logged; unknown text
gets ONE log line ('not understood from chat 7: text "what" (a reply to the phone's message)') and an answer that
quotes it (help_cmd.unknown_head). What a log line or a reply quotes is safe_text(): the pairing secret and every URL
masked, and a message whose first word names a command with an echo (/pair, /alive) quoted as Command.echo gives it.
The command forms a phone keyboard makes ('/Today', '/today ', '/today@bot', '📊 /today', '/today.') are the command
(phone/context.py split_command).
v-ledger-unreadable (2026-11-07): every money page (MONEY_SECTIONS, MONEY_PAGES) gets the warning line at the top when
Kalshi rows were left out of its totals -- '3 markets unreadable (Kalshi field change?)' (money_note; the count is
botdata/ledgercheck.py's, the words phone/render/unbooked.py's). Nothing is added when every row reads.

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
from botdata import dirlist as _dirlist
from phone import command as _cmd
from phone import incoming as _inc
from phone.context import Ctx, split_command
from phone.html import Html, esc, i_
from phone.log import log

PACKAGE = "phone.commands"
HELP_MODULE = PACKAGE + ".help_cmd"
PAIR = "/pair"
STALE_S = 300                   # v-tg-stale: a control whose message is older than this is not run
MONEY_SECTIONS = ("money", "one_bot")                                   # v-ledger-unreadable: every page of these ...
MONEY_PAGES = ("/status", "/losses", "/hedges", "/fills", "/brief")     # ... and these gets the unreadable line
_URL_RX = re.compile(r"(?i)\b(?:https?|wss?|ftp)://\S+")                # v-tg-unknown: never in a log line or a reply
MASKED_URL = "[url]"
MASKED_SECRET = "[secret]"

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


def message_age(ctx, sent_at):
    """Seconds since the message was sent (its Telegram `date`), when that is over STALE_S; else None (fresh, or no
    date: the self-tests' FakeTelegram sends none)."""
    try:
        if sent_at is None:
            return None
        age = float(ctx.now()) - float(sent_at)
    except (TypeError, ValueError):
        return None
    return age if age > STALE_S else None


def echo_of(c, ctx):
    """What a log line or a reply may repeat of this message: Command.echo_of (never a secret: /pair's, /alive's URL)."""
    return c.echo_of(ctx.text) if c is not None else (ctx.cmd or "")


def stale_reply(ctx, age_s, sent_at, c=None):
    """A control that waited too long: not run, and why (v-tg-stale). It may have been done already: a phone ended
    while hung (boot_all, v-tg-hung) gets again from Telegram what it had handled but not yet confirmed -- so the words
    say how to tell."""
    from phone.monitor import span_words, when_words
    return Html("⏱ <b>Not done now: %s</b> was sent %s ago (%s ET) and reached the phone only now (it was restarting or "
                "offline). A control older than %d minutes is never run late: what it does may not be what you want "
                "now. If you already got an answer to it then, it was done then; if not, send it again if you still "
                "want it." % (esc(echo_of(c, ctx)), esc(span_words(age_s)),
                              esc(when_words(float(sent_at), ctx.now())), STALE_S // 60))


def _pair_stale(ctx, age):
    """An old /pair from a stranger while paired: no answer to it; pair.stale tells the paired chat. Never raises."""
    try:
        from phone.commands import pair as _pair
        _pair.stale(ctx, age)
    except Exception:                                           # noqa: BLE001
        log("could not report an old /pair:\n%s" % traceback.format_exc())
    return None


def is_money_page(c):
    return c is not None and (c.section in MONEY_SECTIONS or c.name in MONEY_PAGES)


def money_note(ctx, c, reply):
    """`reply` with the unreadable-markets line on top when `c` is a money page and Kalshi rows were left out of the
    totals (v-ledger-unreadable); `reply` as it is otherwise. Never raises."""
    if reply is None or not is_money_page(c):
        return reply
    try:
        from botdata import ledgercheck as _lc
        from phone.render.unbooked import note_lines
        s = _lc.scan(ctx.results)
        if s.get("error"):
            log("ledger check failed: %s" % s["error"])
        lines = note_lines(s)
        if not lines:
            return reply
        if getattr(reply, "is_html", False):
            return Html("\n".join(lines) + "\n" + reply)
        from phone.html import html_to_plain
        return html_to_plain("\n".join(lines)) + "\n" + str(reply)
    except Exception:                                           # noqa: BLE001
        log("money note failed:\n%s" % traceback.format_exc())
        return reply


def safe_text(ctx, text):
    """What a log line or a reply may quote of `text` (v-tg-unknown; Command.echo's rule for every message): the
    pairing secret (ctx.cfg['secret'], as a whole word, any case) and every URL masked; a message whose first word
    names a command with an echo (/pair, /alive -- with or without its slash: 'pair words' forgot it) is quoted as that
    echo gives it, never as typed. Never raises: a failure quotes nothing."""
    try:
        s = str(text or "")
        if not s.strip():
            return ""
        _t, cmd, _a = split_command(s)
        if cmd and not cmd.startswith("/"):
            cmd = "/" + cmd
        c = _cmd.by_name(cmd)
        if c is not None and c.echo is not None:
            return c.echo_of(s)
        s = _URL_RX.sub(MASKED_URL, s)
        cfg = getattr(ctx, "cfg", None)
        secret = cfg.get("secret") if isinstance(cfg, dict) else None
        if isinstance(secret, str) and secret.strip():
            s = re.sub(r"(?i)(?<!\w)%s(?!\w)" % re.escape(secret.strip()), MASKED_SECRET, s)
        return s
    except Exception:                                           # noqa: BLE001
        return ""


def _incoming(ctx, text, about):
    """The Incoming for this message: the poll loop's (`about`), or a plain text one (Phone.handle(chat, text): the
    self-tests, the smoke, --preview)."""
    if isinstance(about, _inc.Incoming):
        return about
    return _inc.Incoming("text", str(text or ""), ctx.chat_id)


def unknown(ctx, inc=None):
    """Nothing claims the message: ONE log line saying what arrived (v-tg-unknown: its kind, the text quoted -- safe --
    whether it answered a phone message), then help_cmd.unknown_reply (the words quoting it, then /help); plain words if
    that module is broken."""
    inc = inc if inc is not None else _incoming(ctx, ctx.text, None)
    safe = safe_text(ctx, inc.text)
    log("not understood from chat %s: %s" % (ctx.chat_id, _inc.line(inc, safe)))
    quote = _inc.quote(safe, _inc.QUOTE_REPLY)
    try:
        help_cmd = importlib.import_module(HELP_MODULE)
    except Exception as e:                                      # noqa: BLE001
        log("help module failed to load: %s" % e)
        return "I did not understand that. (/help failed to load: %s)" % str(e)[:200]
    return help_cmd.unknown_reply(ctx, quote=quote, reply=inc.reply)


def media_reply(ctx, inc):
    """A sticker, photo, voice ... from the paired chat (v-tg-unknown): one log line, one plain line back, no /help
    list; plain words if the help module is broken."""
    log("not understood from chat %s: %s" % (ctx.chat_id, _inc.line(inc, None)))
    what = _inc.words(inc)
    try:
        return importlib.import_module(HELP_MODULE).media_reply(what)
    except Exception as e:                                      # noqa: BLE001
        log("help module failed to load: %s" % e)
        return "I got %s. I only read typed commands: /help lists them." % what


# ---- dispatch -----------------------------------------------------------------------------------------------------------
def dispatch(phone, chat_id, text, sent_at=None, about=None):
    """The reply for one incoming message to `phone` (the runtime: phone.app.Phone), or None to ignore it. Phone.handle's
    rules, in its order (see the module note). A command with no `fail` may raise: the poll loop answers 'error: ...'.
    v-tg-fast2: one tap (botdata.dirlist.tap): the results folder is listed once for all of the reply's globs.
    v-tg-stale: `sent_at` is the message's Telegram date (epoch seconds; None = fresh).
    v-tg-unknown: `about` is the poll loop's description of the update (phone/incoming.Incoming); None = plain text."""
    with _dirlist.tap():
        return _dispatch(phone, chat_id, text, sent_at, about)


def _dispatch(phone, chat_id, text, sent_at=None, about=None):
    ctx = Ctx.from_phone(phone, text, chat_id=chat_id)
    cmd = ctx.cmd
    inc = _incoming(ctx, text, about)
    if inc.silent:                                   # v-tg-unknown: an edit, a reaction, a callback, a chat event: never
        if phone.chat_id is None or chat_id == phone.chat_id:       # run, never answered; one log line (ours only)
            log("ignored from chat %s: %s (no reply)" % (chat_id, _inc.line(inc, safe_text(ctx, inc.text))))
        return None
    if cmd == PAIR:
        c, broken = command_for(PAIR)
        if c is None:
            if broken:
                log("refused pairing from chat %s: %s failed to load: %s" % (chat_id, broken[0], broken[1]))
            return None
        age = message_age(ctx, sent_at)
        if age is not None:                         # v-tg-stale: an old /pair is never run late
            log("ignored /pair from chat %s: sent %d s ago" % (chat_id, age))
            if phone.chat_id is None or chat_id == phone.chat_id:
                return stale_reply(ctx, age, sent_at, c)
            return _pair_stale(ctx, age)            # a stranger while paired: silence, the paired chat is told
        return c.run(ctx)
    if phone.chat_id is None or chat_id != phone.chat_id:
        return None                                  # not ours: silence
    if not inc.is_text:                              # v-tg-unknown: a sticker, photo, voice ... one line, no /help
        return media_reply(ctx, inc)
    c, broken = command_for(cmd)
    if c is not None and c.is_control:              # v-tg-stale: a control queued while the phone was down
        age = message_age(ctx, sent_at)
        if age is not None:
            log("ignored %s: sent %d s ago (over %d s)" % (echo_of(c, ctx)[:60], age, STALE_S))
            return stale_reply(ctx, age, sent_at, c)
    if c is None or c.needs_ledger:
        phone.ledger.refresh()
    bot = _bots.by_command(cmd)                     # v-tg-active: a paused or retired bot's own command
    if bot is not None and bot.name not in ctx.active():
        return hidden_reply(ctx, bot.name)
    if c is not None:
        return money_note(ctx, c, c.run(ctx))
    if broken:
        return failed_reply(cmd, *broken)
    return unknown(ctx, inc)
