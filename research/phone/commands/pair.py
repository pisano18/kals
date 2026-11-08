"""/pair <secret> -- make this chat the one that controls the bot (telegram.json's chat_id), then show /help.

v-tg-rebuild step 9 (2026-10-30): the /pair branch of Phone.handle as a command module, byte-identical (golden shadow:
research/golden/shadow.py with --case "/pair <secret>=phone.commands.pair"; research/golden/shadow_more.py runs the
golden pair/* cases -- right, right with @bot, wrong, empty -- on an UNPAIRED phone).

THE ROUTER (step 10) must run /pair BEFORE its paired-chat check (it is the one command an unpaired or other chat may
send) and WITHOUT the ledger refresh (Phone.handle answered /pair before refreshing): needs_ledger=False says the second.
A wrong or empty secret answers nothing (None) and logs the refusal, exactly as before.

v-tg-pairlock (2026-11-07, the phone audit: "/pair works from ANY chat even after pairing, with no rate limit and no
notice"). FIRST-TIME PAIRING IS UNCHANGED (no paired chat: the right secret pairs at once). Once a chat is paired:
  - the right secret from ANOTHER chat pairs nothing: it is a takeover request. The paired chat is told (with the other
    chat's id) and control moves only if the paired chat replies /pair allow within TAKEOVER_S (2 minutes; /pair deny
    refuses it at once). The asking chat is told it waits for that answer.
  - every /pair from another chat is reported to the paired chat (a wrong secret too: it is not answered there).
  - wrong secrets are rate-limited: WRONG_MAX (5) from one chat in WRONG_WINDOW_S (an hour), or WRONG_ALL_MAX (20) from
    every other chat together, and after that every /pair from that chat (from every other chat) is ignored until the
    hour has passed -- logged, and said to the paired chat ONCE when the limit is reached, so a flood cannot flood the
    operator's phone too.
  - /pair <secret> from the paired chat itself pairs it again and shows /help, as before (a wrong one: nothing).
  - NOTHING PAIRED YET (first setup): the limit applies too, but there is no paired chat to tell, so the asking chat is
    told 'Too many wrong secrets ... until HH:MM ET' (the try that reaches the limit and every one after), or the
    operator, phone only, could not tell why the right secret now does nothing.
  - an OLD /pair (v-tg-stale: sent over 5 minutes before it is read, e.g. queued while the phone was down) is never run;
    from another chat it is still reported to the paired chat (stale(): a wrong secret counts toward the limit; the
    right one says someone knows the secret).
The pending request and the counts live in memory only (confirm.py's rule): a phone restart forgets them, so a request
delivered again after a restart finds nothing to allow. A new device on the SAME Telegram account is the same chat (a
private chat's id is the account's), so it needs no takeover. LOSING the paired Telegram account leaves no phone path
back (the paired chat must allow a takeover): set "chat_id" to null in C:\\kals\\telegram.json on the server, and the next
/pair <secret> pairs as the first time.
"""
import threading

from botdata import paths as _paths
from phone.command import Command, declare
from phone.commands.help_cmd import help_html
from phone.html import Html, esc
from phone.log import log

TAKEOVER_S = 120                # the paired chat has this long to answer /pair allow
WRONG_MAX = 5                   # wrong secrets one chat may send in WRONG_WINDOW_S; then its /pair is ignored
WRONG_ALL_MAX = 20              # wrong secrets from every other chat together in WRONG_WINDOW_S; then all are ignored
WRONG_WINDOW_S = 3600

_LOCK = threading.Lock()
_STATE = {"wrong": [], "takeover": None, "told": {}}    # wrong: [(t, chat)]; takeover: {"chat", "t"}; told: limit -> when said


def reset():
    """Forget every count and request (a test; a phone restart does the same)."""
    with _LOCK:
        _STATE.update(wrong=[], takeover=None, told={})


def save_cfg(cfg, cfg_path):                    # from pinphone.Phone.save_cfg (only /pair saves the config)
    """telegram.json, rewritten (indent 2) in ONE step (botdata.paths.write_json_atomic: a temp file, then os.replace --
    v-tg-pairlock: an in-place rewrite cut short left half a config, and the phone could not start). A failure is logged,
    never raised."""
    try:
        _paths.write_json_atomic(cfg_path, cfg, indent=2)   # check_write inside: never C:\kals under KALS_TESTING=1
    except OSError as e:
        log("could not save config: %s" % e)


# ---- the rate limit ---------------------------------------------------------------------------------------------------
def _recent(now):
    """The wrong tries inside the window (older ones dropped). Call under _LOCK."""
    _STATE["wrong"] = [(t, c) for t, c in _STATE["wrong"] if 0.0 <= now - t < WRONG_WINDOW_S]
    return _STATE["wrong"]


def limited(chat, now):
    """'chat' when this chat used its WRONG_MAX tries this hour, 'all' when every other chat together used
    WRONG_ALL_MAX, else None."""
    with _LOCK:
        w = _recent(now)
        if sum(1 for _t, c in w if c == chat) >= WRONG_MAX:
            return "chat"
        if len(w) >= WRONG_ALL_MAX:
            return "all"
        return None


def _note_wrong(chat, now):
    """Count one wrong try; (this chat's tries this hour, every chat's)."""
    with _LOCK:
        w = _recent(now)
        w.append((float(now), chat))
        return sum(1 for _t, c in w if c == chat), len(w)


def free_at(lim, chat, now):
    """When the limit `lim` ('chat' / 'all', from limited) lifts: the hour after the oldest try that still keeps the
    count at its maximum."""
    with _LOCK:
        w = _recent(now)
        if lim == "chat":
            ts, mx = sorted(t for t, c in w if c == chat), WRONG_MAX
        else:
            ts, mx = sorted(t for t, _c in w), WRONG_ALL_MAX
    if len(ts) < mx:
        return float(now)
    return ts[len(ts) - mx] + WRONG_WINDOW_S


def _until(lim, chat, now):
    from pindesk import et_str
    return et_str(free_at(lim, chat, now))


def echo(text):
    """What a log line or a reply may repeat of a /pair message (Command.echo): the command alone, never the secret."""
    return "/pair"


def _tell_paired(ctx, paired, text):
    try:
        ctx.say(Html(text), chat_id=paired)
    except Exception as e:                                      # noqa: BLE001  (a report must never cost the answer)
        log("could not tell the paired chat about a /pair: %s" % e)


# ---- the answers ------------------------------------------------------------------------------------------------------
def _paired_reply(ctx):
    return Html("<b>Paired.</b> This chat now controls the bot.\n\n" + help_html(ctx.active(), ctx.pp))


def _from_paired(ctx, now):
    """A /pair from the paired chat: allow / deny a waiting takeover, or (as before) pair this chat again."""
    word = ctx.arg.strip().lower()
    with _LOCK:
        req = _STATE["takeover"]
        if req is not None and not (0.0 <= now - req["t"] <= TAKEOVER_S):
            req = _STATE["takeover"] = None
        if word in ("allow", "deny") and req is not None:
            _STATE["takeover"] = None
    if word == "allow" and req is not None:
        old, new = ctx.chat_id, req["chat"]
        ctx.cfg["chat_id"] = new
        save_cfg(ctx.cfg, ctx.cfg_path)
        log("paired with chat %s (allowed by chat %s)" % (new, old))
        try:
            ctx.say(_paired_reply(ctx), chat_id=new)
        except Exception as e:                                  # noqa: BLE001
            log("could not tell chat %s it is paired: %s" % (new, e))
        return Html("✅ <b>Control moved</b> to chat %s. This chat is no longer answered; send /pair with the secret "
                    "from here to take it back (that chat will be asked)." % esc(new))
    if word == "deny" and req is not None:
        log("takeover by chat %s refused by the paired chat %s" % (req["chat"], ctx.chat_id))
        return Html("⛔ Refused: chat %s does not get control. Nothing changed." % esc(req["chat"]))
    if word in ("allow", "deny"):
        if word != str(ctx.cfg.get("secret", "")).strip().lower():
            return Html("No other chat is waiting to take control (a request stands %d minutes). Nothing changed."
                        % (TAKEOVER_S // 60))
    arg = ctx.arg
    if arg.strip() and arg.strip() == str(ctx.cfg.get("secret", "")).strip():
        ctx.cfg["chat_id"] = ctx.chat_id
        save_cfg(ctx.cfg, ctx.cfg_path)
        log("paired with chat %s" % ctx.chat_id)
        return _paired_reply(ctx)
    log("refused pairing from chat %s" % ctx.chat_id)
    return None


def _right(ctx):
    arg = ctx.arg
    return bool(arg.strip()) and arg.strip() == str(ctx.cfg.get("secret", "")).strip()


def _limit_why(lim):
    return ("this chat sent %d wrong secrets this hour" % WRONG_MAX if lim == "chat" else
            "%d wrong secrets from other chats this hour" % WRONG_ALL_MAX)


def _locked_reply(lim, chat, now):
    """Nothing paired yet (first setup): the asking chat is told why its /pair does nothing, and until when."""
    return Html("⛔ <b>Too many wrong /pair secrets</b> (%s in the last hour). /pair is ignored %s until %s ET; then "
                "send /pair with the secret again. Nothing is paired yet." % (
                    "%d from this chat" % WRONG_MAX if lim == "chat" else "%d from all chats" % WRONG_ALL_MAX,
                    "here" if lim == "chat" else "from every chat", esc(_until(lim, chat, now))))


def _report_wrong(ctx, paired, chat, mine, every, now, ago=None):
    """Tell the paired chat about a wrong secret from `chat` (the limit reached: said once an hour at most). `ago`: the
    words for an OLD /pair's age (stale)."""
    with _LOCK:
        key = ("chat", chat) if mine >= WRONG_MAX else (("all", None) if every >= WRONG_ALL_MAX else None)
        said = _STATE["told"].get(key) if key is not None else None
        first = key is not None and (said is None or not 0.0 <= now - said < WRONG_WINDOW_S)
        if first:
            _STATE["told"][key] = float(now)        # said once an hour at most
    when = (" %s ago (it reached the phone only now)" % esc(ago)) if ago else ""
    if key is None:
        _tell_paired(ctx, paired, "⚠️ <b>Another Telegram chat (id %s) sent /pair with a wrong secret%s.</b> "
                     "Nothing changed and it got no answer. Wrong tries from that chat in the last hour: %d of "
                     "%d (then it is ignored for the hour)." % (esc(chat), when, mine, WRONG_MAX))
    elif first and key[0] == "chat":
        _tell_paired(ctx, paired, "⛔ <b>Another Telegram chat (id %s) sent %d wrong /pair secrets in the last "
                     "hour.</b> Nothing changed. Its /pair is ignored until %s ET, and no more of its tries "
                     "are reported here." % (esc(chat), mine, esc(_until("chat", chat, now))))
    elif first:
        _tell_paired(ctx, paired, "⛔ <b>%d wrong /pair secrets from other chats in the last hour.</b> Nothing "
                     "changed. Every /pair from another chat is ignored until %s ET, and no more are reported "
                     "here." % (every, esc(_until("all", chat, now))))


def stale(ctx, age_s):
    """An OLD /pair (v-tg-stale: phone/router.py never runs one sent over 5 minutes before it is read) from a chat other
    than the paired one: reported to the paired chat all the same (every try from another chat is). A wrong secret
    counts toward the limit; the right one says someone knows the secret, and nothing waits for /pair allow. Always
    None: the asking chat is not answered (a stranger while paired gets silence)."""
    now = ctx.now()
    chat, paired = ctx.chat_id, ctx.cfg.get("chat_id")
    if paired is None or chat == paired:
        return None
    lim = limited(chat, now)
    if lim is not None:
        log("ignored an old /pair from chat %s: %s" % (chat, _limit_why(lim)))
        return None
    from phone.monitor import span_words
    ago = span_words(age_s)
    if _right(ctx):
        log("an old /pair with the right secret from chat %s (sent %d s ago): not acted on" % (chat, age_s))
        _tell_paired(ctx, paired, "⚠️ <b>Another Telegram chat (id %s) sent /pair with the RIGHT secret %s ago</b> (it "
                     "reached the phone only now, so it was not acted on). Nothing changed and nothing waits for "
                     "<code>/pair allow</code>. If this was not you, someone knows the secret." % (esc(chat), esc(ago)))
        return None
    mine, every = _note_wrong(chat, now)
    log("refused an old pairing from chat %s" % chat)
    _report_wrong(ctx, paired, chat, mine, every, now, ago=ago)
    return None


def handle(ctx):
    now = ctx.now()
    chat = ctx.chat_id
    paired = ctx.cfg.get("chat_id")
    if paired is not None and chat == paired:
        return _from_paired(ctx, now)
    lim = limited(chat, now)
    if lim is not None:
        log("ignored /pair from chat %s: %s" % (chat, _limit_why(lim)))
        return _locked_reply(lim, chat, now) if paired is None else None
    if not _right(ctx):
        mine, every = _note_wrong(chat, now)
        log("refused pairing from chat %s" % chat)
        if paired is not None:
            _report_wrong(ctx, paired, chat, mine, every, now)
            return None
        lim = limited(chat, now)                                # first setup: the try that reaches the limit says so
        return _locked_reply(lim, chat, now) if lim is not None else None
    if paired is None:                                          # first-time pairing: unchanged
        ctx.cfg["chat_id"] = chat
        save_cfg(ctx.cfg, ctx.cfg_path)
        log("paired with chat %s" % chat)
        return _paired_reply(ctx)
    with _LOCK:
        _STATE["takeover"] = {"chat": chat, "t": float(now)}
    log("takeover asked by chat %s (right secret); waiting for the paired chat %s" % (chat, paired))
    from pindesk import et_str
    _tell_paired(ctx, paired, "⚠️ <b>Another Telegram chat (id %s) sent /pair with the RIGHT secret and asks to take "
                 "control of the bots.</b> Nothing changes unless you reply <code>/pair allow</code> within %d minutes "
                 "(until %s ET); <code>/pair deny</code> refuses it now. If this was not you, someone knows the secret: "
                 "do not allow it." % (esc(chat), TAKEOVER_S // 60, esc(et_str(now + TAKEOVER_S))))
    return Html("⏳ This bot is already paired with another chat. That chat was asked to confirm: if it replies "
                "<code>/pair allow</code> within %d minutes, this chat takes control. Nothing changed yet."
                % (TAKEOVER_S // 60))


COMMAND = declare(Command(
    names=("/pair",), section=None, chart=None, handle=handle, needs_ledger=False, control=True, echo=echo,
    examples=("/pair not-the-secret",)))
