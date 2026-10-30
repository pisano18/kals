"""phone/html.py -- Telegram HTML: the Html reply type, escaping, the small layout helpers (tables, <pre>, tap-to-open
details, text bars, sparklines), Telegram's markup rules (tg_html_problems) and the message splitters (split_text,
split_html).

v-tg-rebuild step 6 (2026-10-30): moved verbatim out of research/pinphone.py, which re-exports every name here (bars.py
imports pinphone.MAX_LEN and pinphone.split_text; the golden harness and the self-test use pinphone.split_html,
pinphone.Html ...). Pure functions: no file, no network, no clock.
"""
import html as _html
import re

MAX_LEN = 3900                  # one Telegram message, with room to spare (Telegram's limit is 4096)


def split_text(s, limit=MAX_LEN):
    """Chunks of at most `limit` chars for Telegram, cut at a blank line when
    one sits in the second half of the chunk, else at a line, else hard --
    so a /bars block is not sliced mid-sentence."""
    s = str(s)
    out = []
    while len(s) > limit:
        cut = s.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = s.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        out.append(s[:cut].rstrip("\n"))
        s = s[cut:].lstrip("\n")
    if s or not out:
        out.append(s)
    return out


# ===========================================================================
# PRESENTATION (2026-10-18). THE OPERATOR: "Make the telegram responses better to read and more pleasant
# and human friendly to look at. They're blobs of text and hard to find my numbers. Charts and graphs
# included would be neat only if possible. Also make sure numbers include their percentages next to them
# wherever possible."
#
# A reply is Telegram HTML (parse_mode=HTML): its FIRST LINE is a headline with the number that matters
# (e.g. "Today +$7.10 (+0.55% of the bank)"), then short sections under bold headers, small aligned tables
# in <pre> (at most about 36 characters a line, a phone's monospace width), money with its percentage
# beside it, and the long sentences the bot always wrote kept whole behind a tap (<blockquote
# expandable>, one per reply where possible, so a reply stays one message). ONLY THE LAYOUT CHANGED:
# every figure is the one the plain text carried, from the same source, or a percentage worked from two
# of those figures (money / what the bets cost; a count / its total). One money style: +$1,234.56 / -$4.57.
#
# SAFE BY CONSTRUCTION: every piece of data goes through esc() before it meets a tag; a reply built here
# is an Html (a str marked is_html) and only an Html is sent as HTML -- a plain str (an error, a control
# callback's words) goes exactly as before. Telegram's nesting rules are kept (tg_html_problems, run by the
# self-test over every reply): <pre>/<code> never inside a quote or a bold, a quote never inside a quote.
# split_html never leaves a tag open across messages, and if Telegram refuses the markup anyway the
# transport re-sends that part as plain text: a formatting slip can never cost an alert. log() never
# raises (the redirected console is cp1252 and cannot print an emoji).
#
# CHARTS are drawn with text (block characters in <pre>, a sparkline in <code>): no plotting library is
# installed for C:\Python314 (matplotlib, PIL, numpy: none -- checked 2026-10-18), and none is added, so
# nothing here sends a photo.
# ===========================================================================
class Html(str):
    """A reply written in Telegram HTML; every piece of data inside went through esc()."""
    is_html = True


def esc(x):
    """Text made safe inside Telegram HTML: & < > become entities (quotes may stay)."""
    return _html.escape(str(x), quote=False)


def html_to_plain(s):
    """What the phone shows for an Html reply: the tags dropped, the entities decoded."""
    return _html.unescape(re.sub(r"<[^<>]+>", "", str(s)))


_MONEY_SIGN = re.compile(r"\$([+-])(?=\d)")


_MONEY_BIG = re.compile(r"(?<![\d,.])\$(\d{4,})(?![\d,])")


def norm_money(s):
    """The one money style, for lines written by other modules: '$+1008.55' -> '+$1,008.55',
    '$-4.57' -> '-$4.57'. Only the dress changes -- the digits are the same digits."""
    s = _MONEY_SIGN.sub(lambda m: m.group(1) + "$", str(s))
    return _MONEY_BIG.sub(lambda m: "$" + "{:,}".format(int(m.group(1))), s)


def b_(x):
    return "<b>%s</b>" % esc(x)


def i_(x):
    return "<i>%s</i>" % esc(x)


def table(rows, align=None):
    """Rows of cells -> aligned lines for pre(). The first column is left-aligned, the rest right-aligned
    (or `align`, one 'l'/'r' a column). A row with fewer cells than the widest (a day heading, 'nothing
    settled yet') is written as its first cell padded, then the rest, and does not widen the columns."""
    n = max(len(r) for r in rows) if rows else 0
    align = align or ("l" + "r" * (n - 1))
    w = [0] * n
    for r in rows:
        if len(r) == n:
            for k, c in enumerate(r):
                w[k] = max(w[k], len(str(c)))
    out = []
    for r in rows:
        if len(r) != n:
            out.append((str(r[0]).ljust(w[0]) + (" " + " ".join(str(c) for c in r[1:]) if len(r) > 1 else ""))
                       .rstrip())
            continue
        out.append(" ".join(str(c).ljust(w[k]) if align[k] == "l" else str(c).rjust(w[k])
                            for k, c in enumerate(r)).rstrip())
    return out


def pre(lines):
    return "<pre>%s</pre>" % esc("\n".join(lines))


def details(html_lines, title=None):
    """Long lines behind a tap: Telegram shows the first lines of an expandable quote and opens the rest
    when it is tapped. `html_lines` are already escaped (elines)."""
    body = "\n".join(html_lines)
    if not body.strip():
        return ""
    return "<blockquote expandable>%s%s</blockquote>" % (("<b>%s</b>\n" % esc(title)) if title else "", body)


def elines(lines):
    """Another module's plain lines, in this file's money style, escaped for HTML."""
    return [esc(norm_money(x)) for x in lines]


_EIGHTHS = "▏▎▍▌▋▊▉"


def hbar(v, mx, width=10):
    """A text bar for one figure against the biggest one shown: full blocks plus an eighth, light shade
    for a negative figure. '' when there is nothing to draw against."""
    if v is None or not mx:
        return ""
    n = min(abs(v) / float(mx), 1.0) * width
    if v < -0.004:
        return "░" * max(1, int(round(n)))
    if v <= 0.004:
        return ""
    full = int(n)
    k = int((n - full) * 8)
    return ("█" * full + (_EIGHTHS[k - 1] if k else "")) or "▏"


_SPARK = "▁▂▃▄▅▆▇█"


def spark(vals):
    """A one-line chart of a series (lowest = ▁, highest = █)."""
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return _SPARK[0] * len(vals)
    return "".join(_SPARK[int(round((v - lo) / (hi - lo) * 7))] for v in vals)


# Telegram's HTML rules (Bot API, "Formatting options"), checked by the self-test over every reply. A
# reply that breaks one is refused (HTTP 400) and goes again as plain text -- readable, but unformatted.
_TG_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "blockquote",
            "tg-spoiler", "span"}


_TG_STYLE = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "tg-spoiler", "span"}


_TG_TOK = re.compile(r"<[^<>]*>|&[#a-zA-Z0-9]*;|[<>&]")


def tg_html_problems(s):
    """What Telegram would refuse in `s`: an unknown tag, a raw < > &, an unknown entity, a tag closed out
    of order or left open, <pre>/<code> inside a quote or a bold/italic, a quote inside a quote."""
    bad, stack = [], []
    for m in _TG_TOK.finditer(str(s)):
        t = m.group(0)
        if t in ("<", ">", "&"):
            bad.append("raw %r" % t)
            continue
        if t.startswith("&"):
            if t not in ("&lt;", "&gt;", "&amp;", "&quot;") and not re.match(r"^&#(\d+|x[0-9a-fA-F]+);$", t):
                bad.append("entity %s" % t)
            continue
        mm = re.match(r"^<(/?)([a-zA-Z][a-zA-Z0-9-]*)(\s[^<>]*)?>$", t)
        if not mm:
            bad.append("tag %r" % t)
            continue
        close, name, attrs = mm.group(1) == "/", mm.group(2).lower(), (mm.group(3) or "").strip()
        if name not in _TG_TAGS:
            bad.append("<%s> is not a Telegram tag" % name)
        if close:
            if not stack or stack[-1] != name:
                bad.append("</%s> closes %s" % (name, stack[-1] if stack else "nothing"))
            else:
                stack.pop()
            continue
        inside = set(stack)
        if name == "blockquote" and attrs not in ("", "expandable"):
            bad.append("<blockquote %s>" % attrs)
        if "code" in inside or ("pre" in inside and name != "code"):
            bad.append("<%s> inside pre/code" % name)
        if name in ("pre", "code") and inside & (_TG_STYLE | {"blockquote", "a"}):
            bad.append("<%s> inside %s" % (name, "/".join(sorted(inside))))
        if name == "blockquote" and "blockquote" in inside:
            bad.append("a quote inside a quote")
        stack.append(name)
    if stack:
        bad.append("left open: %s" % ", ".join(stack))
    return bad


_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)(?:\s[^<>]*)?>")


def _open_after(stack, text):
    st = list(stack)
    for m in _TAG.finditer(text):
        name = m.group(2).lower()
        if m.group(1):
            for k in range(len(st) - 1, -1, -1):
                if st[k][0] == name:
                    del st[k]
                    break
        else:
            st.append((name, m.group(0)))
    return st


def _closers(stack):
    return "".join("</%s>" % n for n, _o in reversed(stack))


def _openers(stack):
    return "".join(o for _n, o in stack)


def _cut_long_line(line, room):
    """A single line longer than a message: cut at a space outside any tag or entity."""
    out = []
    while len(line) > room:
        spaces, inside = [], False
        for k, ch in enumerate(line[:room]):
            if ch == "<":
                inside = True
            elif ch == ">":
                inside = False
            elif ch == " " and not inside:
                spaces.append(k)
        cut = spaces[-1] if spaces and spaces[-1] > room // 2 else -1
        if cut < 0:
            cut = room
            lt, amp = line.rfind("<", 0, cut), line.rfind("&", 0, cut)
            if lt > line.rfind(">", 0, cut):
                cut = lt
            if amp > line.rfind(";", 0, cut) and cut - amp < 10:
                cut = amp
            cut = max(cut, 1)
        out.append(line[:cut])
        line = line[cut:].lstrip(" ")
    out.append(line)
    return out


def split_html(s, limit=MAX_LEN):
    """split_text for an Html reply: chunks of at most `limit` chars, cut at the last blank line when one
    sits past the first quarter of the chunk (so a section -- a table, a tap-to-open quote -- moves whole to
    the next message rather than being cut), else at a line. Every chunk stands on its own: a tag open at
    a cut is closed at the end of the chunk and opened again at the start of the next, so Telegram never
    sees half a tag."""
    s = str(s)
    if len(s) <= limit:
        return [s]
    lines = []
    for ln in s.split("\n"):
        lines.extend(_cut_long_line(ln, limit - 400) if len(ln) > limit - 400 else [ln])
    out = []
    start = []                              # tags open where the current chunk begins
    cur = []                                # [(line, tags open after it)]

    def body(items):
        return "\n".join(x for x, _st in items)

    def emit(k):
        nonlocal start, cur
        part, end = cur[:k], (cur[k - 1][1] if k else start)
        text = (_openers(start) + body(part)).rstrip("\n") + _closers(end)
        if html_to_plain(text).strip():
            out.append(text)
        start, cur = end, cur[k:]
        while cur and not cur[0][0].strip():
            cur = cur[1:]
    for ln in lines:
        while True:
            st_after = _open_after(cur[-1][1] if cur else start, ln)
            if not (cur and len(_openers(start)) + len(body(cur + [(ln, st_after)])) + len(_closers(st_after))
                    > limit):
                break
            k = len(cur)
            for j in range(len(cur) - 1, 0, -1):     # the last blank line, if it is past the first quarter
                if not cur[j][0].strip():
                    if len(body(cur[:j])) >= limit // 4:
                        k = j
                    break
            emit(k)                                   # takes at least one line off `cur`
        if cur or ln.strip():
            cur.append((ln, st_after))
    if cur:
        emit(len(cur))
    return out or [""]
