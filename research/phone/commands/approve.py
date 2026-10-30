"""/approve -- the changes waiting for the operator's yes, run once from the phone with a 4-digit code.

v-tg-step12 (2026-10-30, lane R; the operator: "approve waiting changes from the phone" -- yes). The list is
results\\approvals\\approvals.json (phone/actions/approvals.py says what may be in it and why):

  /approve                        the waiting changes (and the last ones that ran)
  /approve pin15                  one change in full: what it does, its stop rule, the script and its log; and a code
  /approve pin15 yes 4821         runs it ONCE: powershell -NoProfile -ExecutionPolicy Bypass -File <its script>,
                                  detached through WMI (phone/actions/launch.py); when it ends, its exit code and the
                                  new lines of its log are said, and the list marks it done. The code stands 10 minutes.

Only a script listed in the manifest runs, only from inside the results folder, only while its text matches the sha256
the list holds, never with arguments, never twice. Every step is a line in results\\phone_actions.jsonl.
"""
import threading
import time
import traceback

from phone.actions import approvals as _ap
from phone.actions import confirm as _confirm
from phone.actions import journal as _journal
from phone.actions import launch as _launch
from phone.command import Command, declare
from phone.html import Html, esc, i_
from phone.log import log
from pindesk import et_str

ASK_TTL_S = 600                 # the code stands 10 minutes
WAIT_S = 1800                   # a script still running after 30 minutes is said as such (it keeps running)
_BUSY = set()
_BUSY_LOCK = threading.Lock()


def _when(t):
    try:
        return "%s ET %s" % (et_str(float(t)), time.strftime("%m-%d", time.gmtime(float(t))))
    except (TypeError, ValueError):
        return "?"


def _ran_words(s):
    st = s.get("status")
    if st == "running":
        return "started %s (pid %s), no end seen yet" % (_when(s.get("t_start")), s.get("pid"))
    if st == "done":
        return "ran %s: %s" % (_when(s.get("t_end") or s.get("t_start")), s.get("result") or "?")
    if st == "failed_to_start":
        return "could not start %s: %s (it may be tried again)" % (_when(s.get("t_start")), s.get("error") or "?")
    return st or "?"


def listing(items, why):
    if why:
        return Html("📝 <b>No waiting changes</b>: %s." % esc(why))
    state = _ap.read_state()
    wait = [it for it in items if (state.get(it.get("id")) or {}).get("status") not in _ap.RAN]
    ran = [it for it in items if (state.get(it.get("id")) or {}).get("status") in _ap.RAN]
    L = ["📝 <b>Waiting changes (%d)</b>" % len(wait) if wait else "📝 <b>No change is waiting</b> for your yes."]
    for it in wait:
        L.append("• <b>%s</b> — %s%s" % (esc(it.get("id")), esc(it.get("title") or "?"),
                                         (" ⚠️ " + esc(it["bad"])) if it.get("bad") else ""))
        L.append("   " + i_("added %s by %s · see it: /approve %s" % (it.get("date"), it.get("added_by"), it.get("id"))))
    if ran:
        L.append("")
        L.append("<b>Already run</b>")
        for it in ran[-5:]:
            L.append("• %s — %s: %s" % (esc(it.get("id")), esc(it.get("title") or "?"),
                                        esc(_ran_words(state.get(it["id"]) or {}))))
    L.append(i_("Each change runs once, only after /approve <id> shows it and you send its code back."))
    return Html("\n".join(L))


def details(ctx, it):
    s = _ap.read_state().get(it["id"]) or {}
    if s.get("status") in _ap.RAN:
        return Html("📝 <b>%s</b> — %s\nAlready %s. It runs only once." % (
            esc(it["id"]), esc(it.get("title") or ""), esc(_ran_words(s))))
    path, why = _ap.check(it)
    L = ["📝 <b>%s</b> — %s" % (esc(it["id"]), esc(it.get("title") or "")), esc(it.get("description") or "")]
    if it.get("stop_rule"):
        L.append("<b>Stop rule:</b> " + esc(it["stop_rule"]))
    L.append(i_("script results\\%s · log results\\%s · added %s by %s" % (
        it.get("script"), it.get("log") or "(none)", it.get("date"), it.get("added_by"))))
    if path is None:
        _confirm.drop(ctx.chat_id, "approve")
        L.append("⛔ <b>It cannot run</b>: %s." % esc(why))
        return Html("\n".join(L))
    code = _confirm.ask(ctx.chat_id, "approve", it["id"], ctx.now(), ASK_TTL_S, code=True)
    L.append("To run it once, reply <code>/approve %s yes %s</code> within %d minutes." % (
        esc(it["id"]), code, ASK_TTL_S // 60))
    return Html("\n".join(L))


def run_it(ctx, it, code):
    chat, now = ctx.chat_id, ctx.now()
    got, why = _confirm.take(chat, "approve", now, key=it["id"], code=code)
    if got is None:
        head = {"expired": "That code has expired.", "other": "The code waiting is for another change.",
                "code": "That is not the code."}.get(why, "Nothing is waiting for a yes.")
        return Html("%s Send <code>/approve %s</code> for a new one; nothing ran." % (head, esc(it["id"])))
    s = _ap.read_state().get(it["id"]) or {}
    if s.get("status") in _ap.RAN:
        return "%s already %s. It runs only once." % (it["id"], _ran_words(s))
    path, why = _ap.check(it)                   # again: the file may have changed since the question
    if path is None:
        _journal.record("approve", t=now, id=it["id"], chat=chat, ok=False, error=why)
        return "%s cannot run: %s. Nothing ran." % (it["id"], why)
    with _BUSY_LOCK:
        if it["id"] in _BUSY:
            return "⏳ %s is already starting." % it["id"]
        _BUSY.add(it["id"])
    logp = _ap.log_path(it)
    offset = _ap.size_of(logp)
    try:
        _ap.set_state(it["id"], status="running", t_start=now, chat=chat, script=path, sha256=it["sha256"], pid=None)
    except Exception as e:                                      # noqa: BLE001
        with _BUSY_LOCK:
            _BUSY.discard(it["id"])
        log(traceback.format_exc())
        return "Could not mark %s as running (%s), so it was NOT started." % (it["id"], str(e)[:160])
    _journal.record("approve", t=now, id=it["id"], chat=chat, script=path, sha256=it["sha256"], ok=True)

    def worker():
        try:
            pid, err = _launch.run_script(path)
            if pid is None:
                _ap.set_state(it["id"], status="failed_to_start", error=err)
                _journal.record("approve_start", t=time.time(), id=it["id"], ok=False, error=err)
                ctx.say("%s could not start: %s (nothing ran; it may be tried again)" % (it["id"], err))
                return
            _ap.set_state(it["id"], pid=pid)
            _journal.record("approve_start", t=time.time(), id=it["id"], ok=True, pid=pid)
            ctx.say("%s started (pid %s, through WMI). Its log is read back when it ends." % (it["id"], pid))
            code_ = _launch.WAIT(pid, WAIT_S)
            lines = _ap.new_lines(logp, offset) if logp else []
            if code_ is None:
                result = "still running after %d minutes" % (WAIT_S // 60)
                _ap.set_state(it["id"], note=result)
            else:
                result = "exit code %s" % code_ if code_ >= 0 else "ended (exit code unknown)"
                _ap.set_state(it["id"], status="done", t_end=time.time(), exit=code_, result=result,
                              log_tail=lines[-5:])
            _journal.record("approve_done", t=time.time(), id=it["id"], pid=pid, exit=code_, result=result,
                            log_tail=lines[-5:])
            ctx.say(Html("📝 <b>%s</b>: %s.\n%s" % (
                esc(it["id"]), esc(result),
                ("<pre>%s</pre>" % esc("\n".join(x[:200] for x in lines))) if lines
                else i_("(no new lines in results\\%s)" % (it.get("log") or "?")))))
        except Exception as e:                                  # noqa: BLE001
            ctx.say("%s: the run could not be followed: %s" % (it["id"], e))
            log(traceback.format_exc())
        finally:
            with _BUSY_LOCK:
                _BUSY.discard(it["id"])
    threading.Thread(target=worker, daemon=True).start()
    return Html("📝 <b>Running %s</b> once: %s …" % (esc(it["id"]), esc(it.get("title") or "")))


def approve(ctx):
    words = ctx.arg.split()
    items, why = _ap.load()
    if not words:
        return listing(items, why)
    it = _ap.find(items, words[0])
    if it is None:
        return Html("❓ No waiting change is called <b>%s</b>. /approve lists them." % esc(words[0]))
    if len(words) >= 2 and words[1].lower() == "yes":
        return run_it(ctx, it, words[2] if len(words) > 2 else "")
    return details(ctx, it)


COMMAND = declare(Command(
    # the bare form and '/approve <id>' only read (smoke and --preview run the bare one); '... yes <code>' starts a worker
    names=("/approve",), section="controls", order=60,
    help_line="/approve — changes waiting for your yes (pre-written scripts only): see one, run it once with its code",
    chart=None, handle=approve, examples=("/approve nosuch",)))
