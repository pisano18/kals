"""phone/incoming.py -- what ONE Telegram update is, before the router sees it: its kind, its text, who sent it.

v-tg-unknown (2026-11-08). The operator: "I keep getting that error in telegram" -- nine times since 11-06 the phone
answered 'I did not understand that.' + /help seconds after it had sent a page or a photo, and the log held nothing
about what had ARRIVED (poll_once read only message.text and handed the router a None for everything else: a photo,
a sticker, a service message such as 'pinned_message', a forwarded page -- each got the whole /help). So:

  describe(update)   ONE Incoming for any update Telegram can send: its kind (KINDS), its text (the message's text, or
                     the caption of a photo / video / file: a caption that names a command runs it), its chat and date,
                     whether it was a reply to one of the phone's messages, whether it was forwarded.
  words(inc)         the kind in plain words for a reply: 'a photo', 'a forwarded sticker', 'a voice message'.
  line(inc, text)    the kind and the (already safe) text for ONE log line: 'text "what" (a reply to the phone's
                     message)', 'caption "look" on a photo', 'sticker', 'service message (pinned_message)'.
  quote(text, n)     the first n characters, newlines collapsed, '...' when cut -- what a reply or a log line shows.

WHAT EACH KIND GETS (phone/router.py decides; the words are help_cmd's):
  text / caption     routed as the message; unknown -> 'I did not understand that. You sent "..."' + /help, logged.
  MEDIA              a sticker, photo, voice ... from the paired chat: ONE line ('I got a sticker. I only read typed
                     commands: /help lists them.'), no /help list (it was not an attempt at a command), logged.
  SILENT             never answered, one log line: an edited message (an edit of an old '/stop yes' must not run, and
                     a cosmetic edit deserves no complaint), a reaction, a callback (the phone sends no inline
                     keyboards), a service message (pinning one of the phone's pages makes Telegram send the bot a
                     'pinned_message' message -- the likeliest cause of the nine answers), and anything unrecognised
                     ('other': its field names are logged so it can be classified).
The transport asks Telegram for messages only (allowed_updates ["message"]), so edits, reactions and callbacks do not
arrive today; describe() names them anyway so a change of that list can never bring the whole /help back.
"""
from dataclasses import dataclass

TEXT_KINDS = ("text", "caption")
MEDIA = (("sticker", "a sticker"), ("photo", "a photo"), ("voice", "a voice message"),
         ("video_note", "a video message"), ("video", "a video"), ("animation", "a GIF"), ("document", "a file"),
         ("audio", "an audio file"), ("contact", "a contact"), ("location", "a location"), ("venue", "a location"),
         ("poll", "a poll"), ("dice", "a dice roll"), ("game", "a game"), ("story", "a story"),
         ("paid_media", "paid media"))
MEDIA_WORDS = dict(MEDIA)
SILENT_KINDS = ("edited", "callback", "reaction", "service", "other")
KINDS = TEXT_KINDS + tuple(k for k, _w in MEDIA) + SILENT_KINDS
# an update's top-level key -> the kind of everything in it that is not a plain message
UPDATE_KINDS = (("message", "message"), ("edited_message", "edited"), ("channel_post", "message"),
                ("edited_channel_post", "edited"), ("business_message", "message"),
                ("edited_business_message", "edited"), ("callback_query", "callback"),
                ("message_reaction", "reaction"), ("message_reaction_count", "reaction"))
# a message's fields that are not its content
ENVELOPE = frozenset(("message_id", "message_thread_id", "from", "sender_chat", "sender_boost_count",
                      "sender_business_bot", "date", "business_connection_id", "chat", "forward_origin",
                      "forward_from", "forward_from_chat", "forward_from_message_id", "forward_signature",
                      "forward_sender_name", "forward_date", "is_topic_message", "is_automatic_forward",
                      "reply_to_message", "external_reply", "quote", "reply_to_story", "via_bot", "edit_date",
                      "has_protected_content", "is_from_offline", "media_group_id", "author_signature",
                      "paid_star_count", "entities", "caption_entities", "link_preview_options", "effect_id",
                      "show_caption_above_media", "has_media_spoiler", "reply_markup", "text", "caption"))
QUOTE_REPLY = 60                # the characters of the message a reply quotes
QUOTE_LOG = 80                  # ... and a log line


@dataclass(frozen=True)
class Incoming:
    """One update, described (describe()). kind is one of KINDS; text is '' when the update carries none."""
    kind: str = "text"
    text: str = ""
    chat: object = None
    sent_at: object = None
    reply: bool = False         # a reply to one of the phone's messages
    forwarded: bool = False
    keys: tuple = ()            # 'other': the content fields the message had (names only, never values)

    @property
    def is_text(self):
        return self.kind in TEXT_KINDS

    @property
    def silent(self):
        return self.kind in SILENT_KINDS


def _chat_of(m):
    try:
        return (m.get("chat") or {}).get("id")
    except AttributeError:
        return None


def _is_reply(m):
    """A reply to one of the phone's messages: reply_to_message from a bot (in the paired private chat the only other
    sender IS the phone; a reply_to_message with no `from` is taken as the phone's)."""
    r = m.get("reply_to_message")
    if not isinstance(r, dict):
        return False
    frm = r.get("from")
    return True if not isinstance(frm, dict) else bool(frm.get("is_bot", True))


def _message(m, kind_if_text="text"):
    """An Incoming for a Message object (a plain one: kind_if_text 'text'; an edited one is described by the caller)."""
    chat, sent_at = _chat_of(m), m.get("date")
    fwd = any(k in m for k in ("forward_origin", "forward_date", "forward_from", "forward_from_chat"))
    reply = _is_reply(m)
    text = m.get("text")
    if isinstance(text, str):
        return Incoming(kind_if_text, text, chat, sent_at, reply, fwd)
    media = tuple(k for k, _w in MEDIA if k in m)
    cap = m.get("caption")
    if isinstance(cap, str) and cap.strip():
        return Incoming("caption", cap, chat, sent_at, reply, fwd, media[:1])      # keys: what it captions
    if media:
        return Incoming(media[0], "", chat, sent_at, reply, fwd)
    keys = tuple(sorted(k for k in m if k not in ENVELOPE))
    if keys:                                # a service message (pinned_message, new_chat_members ...) or a new content type
        return Incoming("service", "", chat, sent_at, reply, fwd, keys)
    return Incoming("other", "", chat, sent_at, reply, fwd, keys)


def describe(update):
    """The Incoming for one getUpdates entry. Never raises on a shape it does not know: that is kind 'other'."""
    if not isinstance(update, dict):
        return Incoming("other")
    for key, kind in UPDATE_KINDS:
        u = update.get(key)
        if not isinstance(u, dict):
            continue
        if kind == "message":
            return _message(u)
        if kind == "edited":
            inc = _message(u)
            return Incoming("edited", inc.text, inc.chat, u.get("date"), inc.reply, inc.forwarded, inc.keys)
        if kind == "callback":
            m = u.get("message") if isinstance(u.get("message"), dict) else {}
            data = u.get("data")
            return Incoming("callback", data if isinstance(data, str) else "", _chat_of(m), m.get("date"))
        return Incoming("reaction", "", _chat_of(u), u.get("date"))
    keys = tuple(sorted(k for k in update if k != "update_id"))
    return Incoming("other", "", None, None, False, False, keys)


def quote(text, n=QUOTE_REPLY):
    """The first n characters of `text` with every run of whitespace (newlines too) one space; '...' marks a cut."""
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[:n].rstrip() + "..."


def words(inc):
    """The kind in plain words, for a reply: 'a photo', 'a forwarded sticker', 'a message with no text'."""
    w = MEDIA_WORDS.get(inc.kind)
    if w is None:
        w = {"service": "a chat event", "edited": "an edited message", "reaction": "a reaction",
             "callback": "a button tap"}.get(inc.kind, "a message with no text")
    if inc.forwarded and inc.kind in MEDIA_WORDS:
        art, _sp, rest = w.partition(" ")
        w = "a forwarded " + rest if art in ("a", "an") and rest else "forwarded " + w
    return w


def line(inc, safe_text=None):
    """One log line's description of the update: its kind, the (SAFE: the caller masked it) text quoted to QUOTE_LOG
    characters, 'on a photo' for a caption, '(forwarded)', '(a reply to the phone's message)', a service message's
    field names. The log never shows a text the caller did not pass."""
    t = quote(safe_text, QUOTE_LOG) if safe_text is not None else None
    if inc.kind == "text":
        s = 'text "%s"' % t if t else "text (empty)"
    elif inc.kind == "caption":
        s = 'caption "%s" on %s' % (t, MEDIA_WORDS.get(inc.keys[0], "a message") if inc.keys else "a message")
    elif inc.kind == "edited":
        s = 'edited message "%s"' % t if t else "edited message (no text)"
    elif inc.kind == "callback":
        s = 'callback "%s"' % t if t else "callback"
    elif inc.kind in ("service", "other"):
        s = "%s (%s)" % ("service message" if inc.kind == "service" else "unrecognised update",
                         ", ".join(inc.keys) or "no fields")
    else:
        s = inc.kind.replace("_", " ")
    tags = []
    if inc.forwarded:
        tags.append("forwarded")
    if inc.reply:
        tags.append("a reply to the phone's message")
    return s + (" (%s)" % "; ".join(tags) if tags else "")
