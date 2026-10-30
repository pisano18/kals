"""/pause <bot>, /resume <bot> (/play, /start <bot>) -- pause or resume ONE bot from the phone, by its stop file.

v-tg-step12 (2026-10-30, lane R; the operator: "telegram control to pause and play certain bots"). Plain /pause and
/start (and /pause pin, /resume pin) stay the pin bot's controls exactly as before (phone/commands/controls.py:
pindesk's pause and start); this module is every OTHER registry bot:

  /pause jb        asks: 'Pause Jump band? It holds 1 open bet ($4.40 at risk) ... Reply /pause jb yes' (5 minutes)
  /pause jb yes    writes its stop file (phone/actions/stopfiles.py): the bot takes no new bets from its next tick and
                   exits once flat, by its own rule; nothing restarts it (boot_all skips a bot whose stop file is set)
  /resume jb       asks, showing what the stop file says (who wrote it, why: a stop line says so) and how it comes back
  /resume jb yes   removes the stop file. A bot boot_all keeps alive (Bot.keepalive) is back within 10 minutes by
                   itself; a bot with a start recipe (Bot.start: the jump band's results\\jb_deploy.ps1 -Stage live) is
                   started now, detached through WMI (phone/actions/launch.py), and its log is read back; a bot with
                   neither is NOT touched -- the phone says so instead of guessing.
  /resume          (or /play) alone: which bots are paused, and how to resume one.

Every answer ends with the bot's state read again (botdata.status: the registry's live rule + the stop file), every
action is one line in results\\phone_actions.jsonl. Only the paired chat reaches here (the router).
"""
import os
import threading
import time
import traceback

import bots as _bots
from botdata import paths as _paths
from botdata import status as _status
from botdata.fmt import dollars
from phone.actions import confirm as _confirm
from phone.actions import journal as _journal
from phone.actions import launch as _launch
from phone.actions import stopfiles as _stop
from phone.command import Command, declare
from phone.html import Html, esc, i_
from phone.log import log
from pindesk import et_day, et_str

PIN = "pin"
ASK_TTL_S = 300                     # a pause / resume question stands 5 minutes
STATE_WORDS = {
    _status.ACTIVE: "🟢 running, no stop file",
    _status.STOPPING: "🟡 still running with its stop file set: no new bets; it exits by itself once its open bets settle",
    _status.STOPPED: "⏸ stopped: stop file set, not running",
    _status.DOWN: "🔴 not running and no stop file",
    _status.UNKNOWN: "⚪ unknown: the process table could not be read",
    _status.RETIRED: "retired",
}
_BUSY = set()                       # bots whose start worker is running
_BUSY_LOCK = threading.Lock()


# ---- names ------------------------------------------------------------------------------------------------------------
def names_of(b):
    """Every word that names bot b: its registry name and its commands without the slash."""
    return [b.name] + [c.lstrip("/") for c in tuple(b.commands) + tuple(b.extra_commands)]


def resolve(word):
    """The registry Bot a word names ('jb', '/jumpband', 'FX', 'race'), or None."""
    w = str(word or "").strip().lower().lstrip("/")
    for b in _bots.all_bots():
        if w in names_of(b):
            return b
    return None


def short(b):
    """The word the phone uses in its own instructions: the bot's command without the slash ('jb', 'fc', 'wx')."""
    return b.command.lstrip("/")


def bot_list():
    """'jb (Jump band) · fx (FX taker) · ...': every non-retired bot but the pin bot."""
    return " · ".join("%s (%s)" % (short(b), b.label) for b in _bots.all_bots(retired=False) if b.name != PIN)


# ---- reads -------------------------------------------------------------------------------------------------------------
def state_of(ctx, name):
    """botdata.status's BotStatus for `name`, the process table read now (ctx.procs), or None when that failed."""
    try:
        return _status.fleet(procs=ctx.procs).by_name.get(name)
    except Exception:                                           # noqa: BLE001
        log(traceback.format_exc())
        return None


def state_line(ctx, name):
    st = state_of(ctx, name)
    if st is None:
        return "Now: ⚪ could not be read"
    pids = (" (pid %s)" % ", ".join(str(p) for p in st.pids)) if st.pids else ""
    return "Now: %s%s" % (STATE_WORDS.get(st.state, st.state), pids)


def open_words(ctx, name):
    """'It holds 1 open bet ($4.40 at risk).' from botstats' per-bot read (Kalshi, cached); words, never raises."""
    try:
        o = (ctx.bs_get(name) or {}).get("open") or {}
    except Exception as e:                                      # noqa: BLE001
        log("botctl: open bets of %s: %s" % (name, e))
        return "Its open bets could not be read."
    if not o.get("ok"):
        return "Its open bets could not be read (%s)." % (o.get("error") or "not read yet")
    n = int(o.get("count") or 0)
    if not n:
        return "It holds no open bets."
    return "It holds %d open bet%s (%s at risk)." % (n, "" if n == 1 else "s", dollars(o.get("at_risk") or 0.0))


def _since(name):
    """'10-27 10:02 PM ET': when the stop file was written (ET), or '?'."""
    t = _stop.since(name)
    return "%s %s ET" % (et_day(t)[5:], et_str(t)) if t else "?"


def _comes_back(b):
    """How a resumed bot comes back, in words; None when the phone has no safe way (no keep-alive, no recipe)."""
    if b.keepalive:
        return "its keep-alive brings it back by itself (%s) -- within about 10 minutes" % b.keepalive
    if b.start is not None:
        return "the phone starts it now: %s" % b.start.words
    return None


# ---- /pause <bot> -----------------------------------------------------------------------------------------------------
def unknown_bot(word, verb):
    return Html("❓ No bot is called <b>%s</b>.\n<code>/%s jb</code> (one of: %s); <code>/%s</code> alone is the pin bot."
                % (esc(word), verb, esc(bot_list()), "pause" if verb == "pause" else "start"))


def pause_cmd(ctx):
    """/pause <bot> [yes] for any bot but the pin bot (controls.pause sends those here)."""
    words = ctx.arg.split()
    b = resolve(words[0])
    if b is None:
        return unknown_bot(words[0], "pause")
    yes = len(words) > 1 and words[1].lower() == "yes"
    chat, now = ctx.chat_id, ctx.now()
    if b.retired:
        return Html("%s is retired; there is nothing to pause." % esc(b.label))
    if _stop.is_set(b.name):
        _confirm.drop(chat, "pause")
        return Html("⏸ <b>%s is already paused</b> (stop file since %s: “%s”).\n%s\n%s" % (
            esc(b.label), esc(_since(b.name)), esc(_stop.text_of(b.name, 160)), esc(state_line(ctx, b.name)),
            i_("Resume: /resume %s" % short(b))))
    if not yes:
        _confirm.ask(chat, "pause", b.name, now, ASK_TTL_S)
        return Html("⏸ <b>Pause %s?</b> %s It takes no new bets once its stop file is there and exits after they "
                    "settle, by its own rule; nothing restarts it until you resume it.\nReply <code>/pause %s yes</code> "
                    "within %d minutes." % (esc(b.label), esc(open_words(ctx, b.name)), esc(short(b)), ASK_TTL_S // 60))
    got, why = _confirm.take(chat, "pause", now, key=b.name)
    if got is None:
        return _not_confirmed(why, "pause", b)
    try:
        p = _stop.write(b.name, "operator PAUSE of %s" % b.label, now)
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        _journal.record("pause", t=now, bot=b.name, chat=chat, ok=False, error=str(e)[:200])
        return "Could not pause %s: %s\nNothing changed." % (b.label, str(e)[:200])
    line = state_line(ctx, b.name)
    _journal.record("pause", t=now, bot=b.name, chat=chat, ok=True, stop_file=p, state=line)
    return Html("⏸ <b>%s paused</b>: its stop file is written (%s ET).\n%s\n%s" % (
        esc(b.label), esc(et_str(now)), esc(line), i_("Resume: /resume %s" % short(b))))


def _not_confirmed(why, verb, b):
    if why == "expired":
        head = "That question has expired."
    elif why == "other":
        head = "The question waiting is about another bot."
    else:
        head = "Nothing is waiting for a yes."
    return Html("%s Send <code>/%s %s</code> first; nothing changed." % (head, verb, esc(short(b))))


# ---- /resume <bot> ----------------------------------------------------------------------------------------------------
def paused_list(ctx):
    """/resume alone: which bots are paused (stop file set), and how to resume one."""
    rows = []
    for b in _bots.all_bots(retired=False):
        if b.name == PIN:
            continue
        if _stop.is_set(b.name):
            rows.append("⏸ %s (/%s) -- stop file since %s" % (b.label, short(b), _since(b.name)))
    head = "▶️ <b>Paused bots</b>" if rows else "▶️ <b>No bot is paused</b> (no stop file is set)."
    return Html("\n".join([head] + [esc(r) for r in rows] + [
        i_("Resume one: /resume jb (asks first). Pause one: /pause fx. The pin bot: /pause, /start.")]))


def resume_cmd(ctx):
    """/resume <bot> [yes] (also /play, and /start <bot> from controls)."""
    from phone.commands import controls                         # (the pin bot stays pindesk's: controls.control)
    words = ctx.arg.split()
    if not words:
        return paused_list(ctx)
    b = resolve(words[0])
    if b is None:
        return unknown_bot(words[0], "resume")
    if b.name == PIN:
        return controls.control(ctx, "start")
    yes = len(words) > 1 and words[1].lower() == "yes"
    chat, now = ctx.chat_id, ctx.now()
    if b.retired:
        return Html("%s is retired; it cannot be resumed from the phone." % esc(b.label))
    stop_set = _stop.is_set(b.name)
    st = state_of(ctx, b.name)
    running = st is not None and bool(st.pids)
    how = _comes_back(b)
    if not stop_set and running:
        _confirm.drop(chat, "resume")
        return Html("▶️ <b>%s is already running</b> (no stop file).\n%s" % (esc(b.label), esc(state_line(ctx, b.name))))
    if how is None:
        return Html("⚠️ <b>%s has no keep-alive and no start recipe</b>, so the phone will not guess how to start it. "
                    "Nothing changed.\n%s" % (esc(b.label), esc(state_line(ctx, b.name))))
    if stop_set and running and not b.keepalive:
        _confirm.drop(chat, "resume")
        return Html("⏳ <b>%s is still winding down</b> (its stop file is set and it is still running): a bot that saw "
                    "its stop file finishes its open bets and exits, and nothing would start it again. Send "
                    "<code>/resume %s</code> once it has stopped; nothing changed.\n%s" % (
                        esc(b.label), esc(short(b)), esc(state_line(ctx, b.name))))
    if not stop_set and b.start is None:
        return Html("▶️ %s has no stop file, so there is nothing to resume: %s.\n%s" % (
            esc(b.label), esc(how), esc(state_line(ctx, b.name))))
    if not yes:
        _confirm.ask(chat, "resume", b.name, now, ASK_TTL_S)
        said = _stop.text_of(b.name, 200) if stop_set else ""
        warn = ""
        if "stop line" in said.lower():
            warn = "\n⚠️ It stood itself down at its STOP LINE. It counts its money from its log again when it starts, " \
                   "so it may stop again at once."
        return Html("▶️ <b>Resume %s?</b> %s\nHow it comes back: %s.%s\nReply <code>/resume %s yes</code> within %d minutes."
                    % (esc(b.label),
                       esc(("Its stop file (since %s) says: “%s”" % (_since(b.name), said)) if stop_set
                           else "It has no stop file and is not running."),
                       esc(how), esc(warn), esc(short(b)), ASK_TTL_S // 60))
    got, why = _confirm.take(chat, "resume", now, key=b.name)
    if got is None:
        return _not_confirmed(why, "resume", b)
    path = None
    if not (b.keepalive or running):                # the phone starts it: the recipe must be runnable BEFORE anything
        try:
            path = _launch.resolve_script(b.start.script)
        except ValueError as e:
            _journal.record("resume", t=now, bot=b.name, chat=chat, ok=False, error=str(e)[:200])
            return "%s: its start recipe cannot run (%s), so its stop file stays. Nothing changed." % (
                b.label, str(e)[:200])
    try:
        removed = _stop.remove(b.name)
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        _journal.record("resume", t=now, bot=b.name, chat=chat, ok=False, error=str(e)[:200])
        return "Could not remove %s's stop file: %s\nNothing changed." % (b.label, str(e)[:200])
    if b.keepalive or running:
        line = state_line(ctx, b.name)
        _journal.record("resume", t=now, bot=b.name, chat=chat, ok=True, removed=removed, state=line)
        return Html("▶️ <b>%s resumed</b>: its stop file is %s (%s ET). %s.\n%s" % (
            esc(b.label), "removed" if removed else "already gone", esc(et_str(now)),
            esc(("It is still running; if it already saw the file it finishes its open bets and exits, and %s"
                 % how) if running else how[0].upper() + how[1:]),
            esc(line)))
    return start_bot(ctx, b, path, removed, now)


def start_bot(ctx, b, path, removed, now):
    """Run b.start (its script already resolved: `path`) detached through WMI on a worker: reply now, then say the
    launch, the log tail and the state."""
    chat = ctx.chat_id
    with _BUSY_LOCK:
        if b.name in _BUSY:
            return "⏳ Still starting %s from the last command." % b.label
        _BUSY.add(b.name)

    def worker():
        try:
            pid, err = _launch.run_script(path, b.start.args)
            _journal.record("start", t=time.time(), bot=b.name, chat=chat, script=path, args=list(b.start.args),
                            pid=pid, ok=pid is not None, error=err)
            if pid is None:
                ctx.say("start %s failed: %s" % (b.label, err))
                return
            ctx.say("start %s: %s launched through WMI (pid %s); reading its log in %d s" % (
                b.label, b.start.script, pid, b.start.wait_s))
            time.sleep(b.start.wait_s)
            lines = _launch.tail(_launch_path(b.start.log), 8) if b.start.log else []
            ctx.say(Html("▶️ <b>%s</b> after the start:\n%s\n%s" % (
                esc(b.label), esc(state_line(ctx, b.name)),
                ("<pre>%s</pre>" % esc("\n".join(x[:160] for x in lines))) if lines else i_("(its log is empty)"))))
        except Exception as e:                                  # noqa: BLE001
            ctx.say("start %s failed: %s" % (b.label, e))
            log(traceback.format_exc())
        finally:
            with _BUSY_LOCK:
                _BUSY.discard(b.name)
    _journal.record("resume", t=now, bot=b.name, chat=chat, ok=True, removed=removed, start=b.start.script)
    threading.Thread(target=worker, daemon=True).start()
    return Html("▶️ <b>Starting %s</b>: stop file %s; running %s detached …" % (
        esc(b.label), "removed" if removed else "already gone", esc(b.start.script)))


def _launch_path(name):
    return os.path.join(_paths.RESULTS, name)


COMMANDS = declare(
    # the bare form only reads (smoke and --preview run it); '/resume <bot> yes' may start a worker (a start recipe)
    Command(names=("/resume", "/play"), section="controls", order=25,
            help_line="/pause jb · /resume jb (or /play jb) — pause or resume ONE bot: jb fx ladder fc race wx "
                      "(asks first; /resume alone lists the paused ones)",
            chart=None, handle=resume_cmd, examples=("/resume jb", "/play fx", "/resume nosuch")),
)
