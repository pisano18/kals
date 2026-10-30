#!/usr/bin/env python3
r"""pinphone.py -- the bot in your pocket: a Telegram bot you message.

THE OPERATOR, 2026-09-17: "I want a way to access from my phone."

WHY TELEGRAM AND NOT A WEB PAGE. A web page on the laptop needs a port opened
to the internet (or a tunnel), and then anything on it -- including PAUSE and
STOP -- is reachable by whoever finds the address. A Telegram bot opens no
port: this program POLLS Telegram's servers for messages, answers only ONE
chat (yours, paired once with a secret), and works on cellular anywhere.
Nothing about the account, the key or the tape leaves the machine except the
text of the replies.

SETUP (once, two minutes, on the phone):
  1. In Telegram, message @BotFather, send /newbot, pick a name. It replies
     with a TOKEN like 123456789:AAH...  Paste it into C:\kals\telegram.json:
        {"token": "123456789:AAH...", "secret": "any words you choose"}
  2. Start this program (boot_all.ps1 starts it when the file exists).
  3. Open your new bot in Telegram and send:   /pair any words you choose
     From then on only that chat is answered. Anyone else is ignored.

COMMANDS
  /status     what the desktop banner shows, with its evidence
  /today  /yesterday  /days      money, %% return, closes, fills, hours up
  /open       open bets            /market    how active sellers are
  /losses     every bot's losses   /hedges    insurance and whether it was needed
  /stats      the whole record by window: money, win rate vs break-even, losses, timing
  /bots       every bot and its pot (subaccount): running, money by window, cash, the all-bots total
  /pin  /forecaster (/fc)  /ladder  /weather (/wx)  /fx  /jb (/jumpband)   one bot in full: running or not and why, version,
              settings, money today / yesterday / 7 days / month / all time, worst and best,
              open bets, cash, last markets, what its log did today (research/botstats.py)
  /race       the live coin race now (real money, main account; since v-race-snowball its bets grow
              with the bank), its last 10 races, and its money by window
  /racestats  the coin race record, and the paper arms on the same races
  /bars       every running test against its pre-registered bar: the numbers
              so far, days into the window, PASS / KILL / EXTEND / TOO EARLY
  /funds (/bank /accounts)   every Kalshi account's money: cash in each pool, open bets,
              total, what runs there, each bot's bet size now, its last 7 ET days of gains
              and losses from Kalshi's settlements, and the grand total
  /speed      did the move to the AWS server (10-27) win orders the laptop lost: the pin bot's
              order times and empty orders, home against server, and what speed added in $
              (an estimate); a line for the FX taker, forecaster and coin race
  /server     the server: CPU, memory, disk, uptime, a waiting Windows restart, the time to
              Kalshi, every pot's money (botstats' cache), the AWS bill (/server help: connect it)
  /pause     no new bets, wait for open ones, stop     /start    trade again
  /stop yes   stop right now (the word 'yes' is required)
  /mute  /unmute   alerts off / on          /help

ALERTS it sends by itself: every change of state (TRADING -> NOT RUNNING,
SAFETY BRAKE, PAUSED...), every LOSING close with its story, LOW DISK (once
under 8 GB free, again under 6 GB -- run_all.ps1 stops both recorders for good
at 5 GB and that tape cannot be recreated; re-armed once it climbs back over
9 GB), and one summary of yesterday at 8:00 AM ET. Routine wins are never
sent (the operator asked not to be cluttered with settlements).

The controls are the same functions the desktop app uses (research\pindesk.py):
PAUSE waits for open bets, STOP asks for 'yes', the kill checks the pid's
command line first. The stand-down flag is shared, so the phone and the
desktop always agree.

HOW A REPLY LOOKS (2026-10-18, the operator: "They're blobs of text and hard
to find my numbers"): Telegram HTML -- a headline with the number that
matters, short sections under bold headers, small aligned tables, money with
its percentage beside it, and the long sentences kept whole behind a tap (an
expandable quote). Only the layout changed: every figure is the one the plain
text carried, from the same source. See PRESENTATION below.

CHARTS (2026-10-18, the operator: "do actual x y charts and that solution should work for most
commands"): right after the words, most commands also get a real x-y chart, a PNG sent with sendPhoto
-- the running total through the day, $ and % of the bank by day, each running account's money over
time, a bot's running total and win rate, losses over time, each running test against its bar.
research/tgcharts.py draws them, from the same functions the words use, on ONE background thread
(never on the poll loop: alerts, /pause and /stop never wait for a picture). "charts": false in
telegram.json turns them off; without matplotlib the words still go, and pinphone.log says why.

    python research/pinphone.py --selftest
    python research/pinphone.py --preview        # print what each command would send (as the phone shows it)
    python research/pinphone.py                  # run (needs C:\kals\telegram.json)
"""
import html as _html
import json
import os
import queue
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

# 2026-10-26 (operator: "free up memory"): numpy's OpenBLAS -- pulled in by matplotlib when a chart is drawn -- commits a
# work buffer for each of the 16 CPU threads: measured +614 MB private on the first chart, +131 MB with one thread. The
# charts are small 2-D plots; one thread draws them the same. Must be set before numpy is first imported.
for _blas in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_blas, "1")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindesk                                                       # noqa: E402
from pindesk import (Ledger, et_day, et_day_start, et_str, et_now_str, coin, close_et, money, pct,   # noqa: E402
                     story_loss, story_hedge, story_day, status_of, hours_up_et_day)
import pinflat                                                       # noqa: E402

CONFIG = r"C:\kals\telegram.json"
from botdata import paths as _paths                                  # noqa: E402
# v-tg-rebuild step 2 (2026-10-30): RESULTS from the one place (botdata/paths.py) -- the same <repo>\results string
# pindesk.RESULTS is; tests and the golden harness still patch pinphone.RESULTS as before
RESULTS = _paths.RESULTS
HEARTBEAT = os.path.join(RESULTS, "pinphone.heartbeat")
UPDATE_FLAG = os.path.join(RESULTS, "pinphone.update")    # its presence = /update (update_flag_tick, 10-26)
LOG = os.path.join(RESULTS, "pinphone.log")
MAX_LEN = 3900
LOSSES_SHOWN = 30               # /losses lists this many (operator 10-26: "a bit more than just the last ten")
CHART_QUEUE = 2                 # pictures waiting to be drawn; one more is dropped (logged), never waited for
CHART_MAX_BYTES = 9_500_000     # Telegram takes photos up to 10 MB

import bots as _bots                                                 # noqa: E402
# v-tg-rebuild step 5 (2026-10-30): every per-bot table below is READ FROM THE REGISTRY (research/bots/<name>.py, one file
# a bot); a bot that moves, starts or stops is edited there, never here. bots/tests/test_registry.py and the golden
# harness (research/golden, 'data/tables') hold each table to the values it had when it was written out here (8a9c5e1).

# /funds (/bank /accounts): WHAT RUNS IN EACH KALSHI ACCOUNT (the bots' Pot.what, bots.EXTRA_POOLS for a pool no bot
# trades). Key = subaccount number (0 = the main account). A value is the words, or {cash pool: words} when one
# subaccount does different things in different pools. A subaccount Kalshi lists that is not here
# shows as "unknown". (2026-10-11, the operator: "Add a way in telegram to see the bankroll or fund
# sizes of all sub accounts.")
FUNDS_WHAT = _bots.FUNDS_WHAT
# v-tg-active (2026-10-30): the bots behind each FUNDS_WHAT entry. /funds names only the ACTIVE ones (botstats.active_bots:
# running live, no stop file); an entry whose bots are all paused or retired reads FUNDS_IDLE -- its money is still listed.
FUNDS_BOTS = _bots.FUNDS_BOTS
FUNDS_IDLE = "nothing runs here now (stopped)"
FUNDS_POOL_NAME = {0: "weather pool", 2: "crypto pool"}     # Kalshi's exchange_index; others say "pool N"
# whose bet size /funds shows under each account (read from that bot's own log by its Bot.funds_size, see funds_sizes)
FUNDS_SIZE_BOTS = _bots.FUNDS_SIZE_BOTS


def _pot_whats(n, pool=None):
    """[(Bot, its words)] for every bot pot in account n (in cash pool `pool`; None = every pool), in bot order."""
    sub = str(n)
    return [(b, p.what) for b in _bots.bots_on(sub) for p in b.pots if p.sub == sub and (pool is None or p.pool == pool)]


def funds_what(n, active=None):
    """FUNDS_WHAT's words for account n, naming only the ACTIVE bots (v-tg-active; None = the whole roster): an entry
    whose bots are all hidden reads FUNDS_IDLE; the main account names the coin race only while it runs (an always-shown
    bot -- the pin bot -- is always named). v-tg-rebuild step 5: the words are the active bots' Pot.what, joined."""
    what = FUNDS_WHAT.get(n)
    if what is None or active is None:
        return what

    def one(pool):
        words = [w for b, w in _pot_whats(n, pool) if b.always_shown or b.name in active]
        return " + ".join(words) if words else FUNDS_IDLE
    if isinstance(what, dict):
        return {ix: one(ix) for ix in what}
    return one(None)


# WHICH BOT a trade is (2026-10-26, the operator: "anywhere that trades or transactions are listed list the account or
# which bot"): the words a line uses for each bot (its Bot.word); 'earlier' = every paused or retired bot together,
# 'other' = a main-account market no bot claims (bots.NOT_BOT_WORD).
BOT_WORD = _bots.BOT_WORD

# the bot the desk is about (pindesk: the Ledger of kalshi_ledger.json's orders, /status, /pause, /start): the registry's
# always-shown bot, the pin bot. Its orders come from the Ledger; every other bot's from botstats.fills_since.
DESK_BOT = next(b.name for b in _bots.all_bots() if b.always_shown)


def main_sharers(present=None):
    """The main account's bots to name while it is SHARED: the desk bot, then every other bot with a pot in subaccount 0
    that is in `present` (None = all of them) -- [] while the desk bot is alone there. 'pin + race share the main
    account' is said only while the coin race runs (v-tg-active); v-tg-rebuild step 5: from the registry."""
    others = [b.name for b in _bots.bots_on("0") if b.name != DESK_BOT and (present is None or b.name in present)]
    return [DESK_BOT] + others if others else []


def main_shared(present=None, joiner=" + "):
    """'pin + race' (main_sharers joined by `joiner`) while the main account is shared among `present`, else ''."""
    return joiner.join(main_sharers(present))


def _tgc():
    """research/tgcharts.py, imported on first use (it imports matplotlib only when it draws)."""
    import tgcharts
    return tgcharts


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


def log(msg):
    """One line to stdout and to LOG. NEVER RAISES (2026-10-18): boot_all starts this program with stdout
    redirected to results/pinphone.out, and a redirected stdout on this box is cp1252 -- the emoji and box
    characters the phone's replies carry cannot be written there. Before this fix a raise here came out of
    say() AFTER the message had gone, and out of poll_once() BEFORE Telegram was told the update was
    handled: the process died, and the restart answered the same command again. So the console copy falls
    back to escapes; the log file (utf-8) keeps the real characters."""
    line = "%s  %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except Exception:                                           # noqa: BLE001
        try:
            print(line.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
        except Exception:                                       # noqa: BLE001
            pass
    try:
        _paths.check_write(LOG)              # v-tg-rebuild step 2: never the live log under KALS_TESTING=1 (an OSError)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def cprint(s):
    """print() that never raises on a console that cannot show a character (the self-test's and --preview's
    output carries emoji; a redirected console here is cp1252): the line falls back to escapes."""
    try:
        print(s, flush=True)
    except UnicodeEncodeError:
        print(str(s).encode("ascii", "backslashreplace").decode("ascii"), flush=True)


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


def usd(x):
    """+$1,234.56 / -$4.57 / $0.00 (botstats.usd's style, kept here so a broken botstats costs only the
    pages that need it). None -> '?'."""
    if x is None:
        return "?"
    s = "{:,.2f}".format(abs(x))
    return ("+$" if x > 0.004 else ("-$" if x < -0.004 else "$")) + s


def dollars(x):
    """An amount with no sign (a bank, a stake): $1,294.50. None -> '?'."""
    return "?" if x is None else "$" + "{:,.2f}".format(x)


def dot(x):
    """A colour for a money figure: up, down, or nothing either way / not known."""
    if x is None:
        return "⚪"
    return "🟢" if x > 0.004 else ("🔴" if x < -0.004 else "⚪")


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


def hm(epoch):
    """A short ET clock for a table: '3:15a', '10:15p'."""
    if not epoch:
        return "?"
    s = et_str(epoch, "%I:%M %p")
    return s[:-3] + s[-2].lower() if s.endswith(("AM", "PM")) else s


def pct_of(part, whole, digits=0):
    """'40%' -- a count's share of its total, or '' when the total is zero."""
    if not whole:
        return ""
    return ("%." + str(digits) + "f%%") % (100.0 * part / whole)


def pct1(part, whole):
    """A count's share with one decimal for a table, but '100%' and '0%' when it is all or none (keeps a
    column narrow on a phone); '-' when the total is zero."""
    if not whole:
        return "-"
    if part >= whole:
        return "100%"
    if part <= 0:
        return "0%"
    return "%.1f%%" % (100.0 * part / whole)


def ret(money_, base, digits=1):
    """'+2.7%' -- money as a share of what bought it (the bets' cost, a bank), signed; '' when the base is
    unknown or not positive. Worked from the two figures shown, never from anything else."""
    if money_ is None or not base or base <= 0:
        return ""
    return ("%+." + str(digits) + "f%%") % (100.0 * money_ / base)


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


# ===========================================================================
# transport
# ===========================================================================
class Telegram:
    def __init__(self, token):
        self.base = "https://api.telegram.org/bot%s/" % token

    def _call(self, method, params, http_timeout=45):
        data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
        req = urllib.request.Request(self.base + method, data=data)
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def get_updates(self, offset, timeout=25):
        d = self._call("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'},
                       http_timeout=timeout + 15)
        return d.get("result", []) if d.get("ok") else []

    def send(self, chat_id, text):
        """A plain str goes exactly as it always did. An Html reply goes with parse_mode=HTML, cut by
        split_html; if Telegram refuses a part's markup (HTTP 400, "can't parse entities") that part is
        sent again as plain text, so a formatting slip never costs a message. Any other failure is
        raised as before (say() logs it)."""
        if not getattr(text, "is_html", False):
            for chunk in split_text(text, MAX_LEN):
                self._call("sendMessage", {"chat_id": chat_id, "text": chunk})
            return
        for chunk in split_html(text, MAX_LEN):
            try:
                self._call("sendMessage", {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"})
            except urllib.error.HTTPError as e:
                if e.code != 400:
                    raise
                log("Telegram refused the HTML of one part (%s); sent it again as plain text" % e)
                for part in split_text(html_to_plain(chunk), MAX_LEN):
                    self._call("sendMessage", {"chat_id": chat_id, "text": part})

    def _post(self, method, body, ctype, http_timeout=60):
        req = urllib.request.Request(self.base + method, data=body, headers={"Content-Type": ctype})
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def send_photo(self, chat_id, png, caption=None):
        """One chart: sendPhoto, multipart (photo_body). The caption is plain text (no markup to refuse)."""
        boundary = "pinphone" + os.urandom(12).hex()
        d = self._post("sendPhoto", photo_body(chat_id, png, caption, boundary),
                       "multipart/form-data; boundary=" + boundary)
        if not (isinstance(d, dict) and d.get("ok")):
            raise RuntimeError("sendPhoto refused: %s" % (str(d)[:200],))


def photo_body(chat_id, png, caption, boundary):
    """multipart/form-data for sendPhoto: chat_id, caption (cut to Telegram's 1024), the PNG as `photo`."""
    B = boundary.encode()
    crlf = b"\r\n"
    out = []
    for k, v in (("chat_id", str(chat_id)), ("caption", (caption or "")[:1024] or None)):
        if v is not None:
            out.append(b"--" + B + crlf + b'Content-Disposition: form-data; name="' + k.encode() + b'"' + crlf + crlf
                       + v.encode("utf-8") + crlf)
    out.append(b"--" + B + crlf + b'Content-Disposition: form-data; name="photo"; filename="chart.png"' + crlf
               + b"Content-Type: image/png" + crlf + crlf + bytes(png) + crlf)
    out.append(b"--" + B + b"--" + crlf)
    return b"".join(out)


SUPPLY_STALE_D = 3.0        # /market: an opportunity trend measured longer ago than this is left out (2026-10-23)

HALT_WORDS = [   # 2026-10-23: a stop in a bot's own log, in plain words (the raw text stays in the log)
    (r"outcome UNKNOWN", "stopped itself -- Kalshi did not confirm an order (the connection dropped), so it would "
                         "not guess; the watchdog starts it again"),
    (r"^stop_file\b", "its stop file was set: it cancelled what was resting and stopped"),
    (r"^exit\b.*stop file", "it exited (stop file)"),
    (r"loss COUNT brake|loss abort|DRAWDOWN brake|DAY loss cap|day stop", "a loss brake stopped it"),
]


def halt_words(what, why):
    """One logged stop ('halt pintake halted: order pin-... outcome UNKNOWN (status -1, ...)') in plain words; an
    unknown kind keeps its own text, cut to a line."""
    raw = ("%s %s" % (what or "", why or "")).strip()
    for pat, words in HALT_WORDS:
        if re.search(pat, raw):
            return words
    return raw[:140]


RESEND_FOR_S = 15 * 60      # 2026-10-23: a send the connection dropped is tried again for this long ...
RESEND_GAP_S = 30           # ... this far apart
RESEND_KEEP = 20            # at most this many wait (the newest)
PHOTO_TRIES = (5, 20)       # a chart the connection dropped: sent again after these many seconds


def net_error(e):
    """True when a send failed on the CONNECTION (no answer, reset, TLS timeout, Telegram 5xx or 429) -- worth
    sending again. False when Telegram refused the message itself (HTTP 4xx), which a resend would only repeat."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code == 429
    import http.client
    return isinstance(e, (OSError, http.client.HTTPException))


class FakeTelegram:
    """For the self-test: a queue of incoming messages and a list of sent ones."""
    def __init__(self):
        self.incoming = []
        self.sent = []
        self.photos = []
        self.n = 0

    def push(self, chat_id, text):
        self.n += 1
        self.incoming.append({"update_id": self.n, "message": {"chat": {"id": chat_id}, "text": text}})

    def get_updates(self, offset, timeout=25):
        out = [u for u in self.incoming if u["update_id"] >= (offset or 0)]
        return out

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def send_photo(self, chat_id, png, caption=None):
        self.photos.append((chat_id, png, caption))


# ===========================================================================
# the bot
# ===========================================================================
HELP_TEXT = """📱 <b>Commands</b>

💰 <b>Money</b>
/today · /yesterday — every bot's money that day: % of all pots, and a table with each bot's % of its bank
/days — the last 7 days, every bot: each day's % of all pots, each bot's week
/stats — the whole record by window: money, win rate vs break-even, losses, timing
/funds (or /bank, /accounts) — the money in every account and subaccount: cash, open bets, total, what runs there, bet size now, each account's last 7 days{funds_split}, and the grand total
/bots — every bot running now: money today / 7 days / all time, each pot's cash, and the total of all of them

🤖 <b>One bot</b> <i>(the bots running now; a paused or stopped one comes back here when it runs again)</i>
{bot_lines}

🔎 <b>Right now</b>
/status — is it trading, with the evidence
/open — open bets in every pot
/fills — the pin bot's orders today: filled, price paid, seconds out; then every other bot's fills, each named
/market — how active sellers are, and which bot bought what at each of the last closes
/losses — every bot's losing markets: which bot, $ and % of its pot
/hedges — the pin bot's insurance, whether it was needed, % of the bank
/brief — the daily briefing: money, what changed, what it did, the market, what to watch
/bars — the September tests against their pre-registered bars (all finished; kept for the record)
/features — what each bot does and the settings it runs with now (read from boot_all.ps1), and the rules they run under

🖥 <b>Server</b> (every bot runs on an AWS server in Ohio since 12:20 AM ET Oct 27)
/speed: did the move win orders the laptop lost: the pin bot's order times and empty orders, home against server, and what speed added in $ (an estimate); a line for the other bots
/server: the server's CPU, memory, disk, uptime and Windows restarts, the time to Kalshi, every pot's money, and the AWS bill this month (<code>/server help</code>: connect the AWS cost)

🎛 <b>Controls</b>
/pause — no new bets, wait for open ones, then stop
/start — trade again
<code>/stop yes</code> — stop right now
/mute · /unmute — alerts off / on
/update — load the newest phone code (self-tests it first; back within ~10 min)

📈 Most commands send a chart right after the words (not /open, /help, /speed, /server or the controls).

<i>Alerts come by themselves: state changes, every losing close (with its % of the bank), low disk (under 8 GB, again under 6 GB), and yesterday's summary for every bot at 8 AM ET. Long details sit behind a tap on the quoted block.</i>"""

# v-tg-active (2026-10-30, the operator: "remove the paused and removed until they're added back, and show the details
# for the new one in any relevant commands"): /help lists a bot's command only while it is ACTIVE (botstats.active_bots).
# v-tg-rebuild step 5 (2026-10-30): each bot's lines are its Bot.help (research/bots/<name>.py), in bot order
HELP_BOT_LINES = _bots.HELP_BOT_LINES


def help_text(active=None):
    """/help with the one-bot commands of the ACTIVE bots only (None = every bot: the whole roster)."""
    act = set(active) if active is not None else None
    lines = [w for b, w in HELP_BOT_LINES if act is None or b in act]
    return Html(_HELP_TPL.replace("{bot_lines}", "\n".join(lines)).replace(
        "{funds_split}", (" (main bot and %s apart)" % " and ".join(BOT_WORD[x] for x in main_sharers(act)[1:]))
        if main_sharers(act) else ""))


_HELP_TPL = HELP_TEXT
HELP_TEXT = help_text()                  # the whole roster (the self-test's reference); /help sends help_text(active)

# the immediate reply to a control (the work itself runs on a thread, see Phone.control)
CONTROL_REPLY = {"start": Html("▶️ <b>Starting…</b>"),
                 "pause": Html("⏸ <b>Pausing</b>: no new bets; waiting for open ones to settle…"),
                 "stop": Html("⏹ <b>Stopping now…</b>"),
                 "busy": Html("⏳ Still working on the last command.")}
UP_TEXT = Html("📱 <b>Pin Bot phone link is up.</b> /status for the state, /help for commands.")
STOP_ASK = Html("⚠️ <b>STOP stops right now</b>, even with a bet open (it settles by itself but will not be "
                "hedged).\nTo confirm, send:  <code>/stop yes</code>\nOr use /pause to finish open bets first.")


def state_dot(state):
    return {"TRADING": "🟢", "PAUSING": "🟡", "STALE": "🟡", "BLIND": "🟠", "PAUSED": "⏸", "STOPPED": "⏹",
            "BRAKE": "🔴", "DOWN": "🔴"}.get(state, "⚪")


def alert_state_text(prev, state, hl, det):
    """STATE CHANGED: the words alerts_tick always sent, under a coloured headline."""
    body, _nl, ev = str(det).rpartition("\n")
    if not body:
        body, ev = ev, ""
    return Html("%s <b>STATE CHANGED: %s -&gt; %s</b>\n<b>%s</b>\n%s%s" % (
        state_dot(state), esc(prev), esc(state), esc(hl), esc(body), ("\n<i>%s</i>" % esc(ev)) if ev else ""))


def alert_recorder_text(rec, minutes):
    return Html("⚠️ <b>RECORDER %s</b> -- nothing written for %d+ min.\nThat tape cannot be recreated later. "
                "If the bot is also BLIND, the problem is the connection to Kalshi, not our programs."
                % (esc(rec), minutes))


def alert_recorder_back_text(was):
    return Html("✅ <b>RECORDERS WRITING AGAIN</b> (was %s)" % esc(was))


def disk_alert_html(msg, level):
    """disk_alert()'s words (unchanged, the self-test pins them) with the first sentence as a headline."""
    msg = str(msg)
    if level == 8:
        head, sep, rest = msg.partition(". ")
        head += "." if sep else ""
    else:
        head, _sep, rest = msg.partition(" -- ")
    return Html("%s <b>%s</b>%s" % ("🚨" if level == 6 else "⚠️", esc(head), ("\n" + esc(rest)) if rest else ""))


def alert_loss_text(ledger, close, net, legs):
    """A new losing close: story_loss's facts (pindesk), laid out -- the loss as the headline, one line a
    leg, why it hurts. The desktop's 'double-click a row' hint is left out: there is no row on a phone.
    2026-10-26 (operator: "anywhere that trades or transactions are listed list the account or which bot"): the headline
    names the bot and its account; each leg names its bot too when one close holds both main-account bots' legs."""
    b0 = ledger.bank_at(close - 1) if close else None
    whose = [BOT_WORD.get(main_bot_of(l_["tk"]), "?") for l_ in legs]
    who = list(dict.fromkeys(whose))
    L = ["🔴 <b>LOSS %s%s</b> · %s (main account) · the quarter-hour closing %s ET on %s" % (
        esc(usd(net)), (" (%s of the bank)" % esc(pct(net / b0))) if b0 else "", esc(" + ".join(who) or "?"),
        esc(et_str(close)), esc(et_str(close, "%b %d")))]
    for l_, w in zip(legs, whose):
        n = ledger.contracts_for(l_["tk"]) or _f(l_.get("n"))      # a coin-race leg is not in the pin bot's orders
        L.append("• %s<b>%s</b> %s at %.1fc, %g contracts → settled %s: <b>%s</b>" % (
            (esc(w) + " · ") if len(who) > 1 else "", esc(_mkt_short(l_["tk"])), esc(str(l_["want"]).upper()),
            100 * float(l_["cost"] or 0), n, esc(str(l_["result"]).upper()), esc(usd(l_["pnl"]))))
    L.append("")
    L.append("<b>WHY IT HURTS:</b> <i>a win here makes 2c to 4c a contract; a loss costs most of the 96c-98c "
             "paid. So one losing close wipes out many winning ones.</i>")
    L.append("<i>/losses for the list, /today for the day.</i>")
    return Html("\n".join(L))


def alert_daily_text(ledger, d, now):
    """The 8 AM summary: story_day's own lines (pindesk), under a headline with yesterday's money and its
    % of the bank at the start of the day -- the same two numbers its MONEY line carries."""
    s = Ledger.summary(ledger.settled_on(d))
    b0 = ledger.bank_at(et_day_start(d))
    lines = story_day(ledger, d, now=now).split("\n")
    body = [x for x in lines[1:] if x.strip()]
    out = ["☀️ <b>YESTERDAY %s (%s)</b> · %s" % (esc(usd(s["net"])), esc(pct((s["net"] / b0) if b0 else None)),
                                                  esc(time.strftime("%a %b %d", time.strptime(d, "%Y-%m-%d"))))]
    for x in body:
        head, sep, rest = norm_money(x).partition(": ")
        out.append(("<b>%s:</b> %s" % (esc(head), esc(rest))) if sep and head.isupper() else esc(norm_money(x)))
    return Html("\n".join(out))


def fmt_or_plain(build, plain):
    """An alert laid out (build()), or -- if laying it out fails -- the plain words it always had (plain()),
    so a layout bug can never swallow an alert."""
    try:
        return build()
    except Exception:                                           # noqa: BLE001
        log("alert layout failed, sending the plain words: %s" % traceback.format_exc()[-400:])
        return plain()


_CAPS_HEAD = re.compile(r"^[A-Z][A-Z0-9 ,'/&-]{4,}(?:\b|$)")


def brief_html(text):
    """/brief: pinbrief's text, unchanged in words (the phone quotes it, never rebuilds it) -- its title
    and its ALL-CAPS headings in bold, labels like MONEY: in bold, one money style."""
    try:
        out = []
        for k, ln in enumerate(norm_money(text).split("\n")):
            s = ln.strip()
            ind = ln[:len(ln) - len(ln.lstrip())]
            m = _CAPS_HEAD.match(s)
            if k == 0 and s:
                out.append("📰 <b>%s</b>" % esc(s))
            elif m and (m.end() == len(s) or s[m.end():m.end() + 1] in (",", " ")) and not re.match(r"^[A-Z]+:", s):
                out.append("%s<b>%s</b>%s" % (esc(ind), esc(s[:m.end()]), esc(s[m.end():])))
            elif re.match(r"^[A-Z][A-Z ]+: ", s):
                head, _sep, rest = s.partition(": ")
                out.append("%s<b>%s:</b> %s" % (esc(ind), esc(head), esc(rest)))
            else:
                out.append(esc(ln))
        return Html("\n".join(out))
    except Exception:                                           # noqa: BLE001
        return Html(esc(text))


_VERDICT = re.compile(r"(VERDICT(?: \([^)]*\))?): (PASS|KILL|EXTEND|TOO EARLY)\b")
_VERDICT_MARK = {"PASS": "✅", "KILL": "❌", "EXTEND": "🔁", "TOO EARLY": "⏳"}


def bars_html(text):
    """/bars: research/bars.py's text, unchanged in words (one place decides PASS / KILL / EXTEND / TOO
    EARLY; the phone quotes it). Laid out: the verdicts gathered under the title, each section's name in
    bold, every VERDICT marked, the long race lists and the watchers' report lines behind a tap."""
    try:
        blocks = norm_money(text).split("\n\n")
        verdicts, out = [], []
        for bi, blk in enumerate(blocks):
            lines = blk.split("\n")
            html, quote, last_head = [], [], None
            for li, ln in enumerate(lines):
                # a section's name: 'NAME -- ...' at the left margin; never the verdict line itself, nor a
                # 'So far: ...' line (2026-10-18: the summary had read 'VERDICT: EXTEND: EXTEND')
                h0 = ln.split(" -- ", 1)[0]
                if " -- " in ln and not ln.startswith(" ") and "VERDICT" not in h0 \
                        and not ln.startswith(("So far", "No ", "The bar")):
                    last_head = re.sub(r"\s+beside it$", "", h0.rstrip(":"))
                m = _VERDICT.search(ln)
                if m:
                    verdicts.append((last_head or "?", m.group(2)))
                if ln.startswith("  ") or ln.startswith("Those races: "):
                    quote.append(esc(ln.strip()))
                    continue
                if quote:
                    html.append(details(quote))
                    quote = []
                e = esc(ln)
                if li == 0:
                    if ln.startswith("BARS  "):
                        e = "<b>BARS</b>  " + "<i>%s</i>" % esc(ln[6:])
                    elif " -- " in ln:
                        h, _s, r = ln.partition(" -- ")
                        e = "<b>%s</b> -- %s" % (esc(h), esc(r))
                    elif ln.endswith(":") or len(ln) < 90:
                        e = "<b>%s</b>" % esc(ln)
                    elif ". " in ln:
                        h, _s, r = ln.partition(". ")
                        e = "<b>%s.</b> %s" % (esc(h), esc(r))
                e = _VERDICT.sub(lambda mm: "%s <b>%s: %s</b>" % (_VERDICT_MARK[mm.group(2)], mm.group(1), mm.group(2)), e)
                html.append(e)
            if quote:
                html.append(details(quote))
            out.append("\n".join(html))
        if verdicts:
            head = out[0].split("\n")
            n = {}
            for _w, v in verdicts:
                n[v] = n.get(v, 0) + 1
            top = "📏 <b>Bars</b>: " + " · ".join("%s %d %s" % (_VERDICT_MARK[v], n[v], v)
                                                   for v in ("PASS", "KILL", "EXTEND", "TOO EARLY") if n.get(v))
            summary = [top] + ["%s %s: <b>%s</b>" % (_VERDICT_MARK[v], esc(w), v) for w, v in verdicts] + [""]
            out[0] = "\n".join(summary + head)
        return Html("\n\n".join(out))
    except Exception:                                           # noqa: BLE001
        return Html(esc(text))


# ===========================================================================
# /stats, /race, /racestats -- what he would show a friend, and every number
# he asks for.
#
# MONEY IS KALSHI'S: results/kalshi_ledger.json through pinledger (payout
# minus both sides' cost minus fee, one row per market). The bots' own logs
# are read ONLY for what the exchange cannot know -- how many seconds were
# left when an order went out, what the penny bot is holding this minute,
# what a paper arm would have done -- and every such line says so.
# ===========================================================================
import calendar                                                      # noqa: E402
import datetime                                                      # noqa: E402
import re                                                            # noqa: E402
import subprocess                                                    # noqa: E402
import pinday                                                        # noqa: E402
import pinledger                                                     # noqa: E402

FIRST_LIVE_DAY = "2026-09-08"           # the first ET day real money traded
RACE_SERIES = "KXCRYPTOLEAD15M"
RACE30_UTC = "2026-09-22T07:03:00Z"     # v-race30: the penny test's current rails
RACE_ARMS = ("z3", "gap075", "racectl", "raceedge0", "racetau40")
# The z3 arm's pre-registered bar (HANDOFF 2026-09-22): PASS at 125 races with
# 0 losses or 250 with at most 1; KILL at 2 losses in the first 50.
Z3_PASS, Z3_PASS_ALT, Z3_KILL = (125, 0), (250, 1), (2, 50)
# pinrun.MAX_DRAWDOWN -- the halt line is this far under the high-water bank.
# Copied, not imported: pinrun pulls in kauth and sockets. The self-test
# reads pinrun.py's source and fails if the two drift.
MAX_DRAWDOWN = 0.20
PROC_TTL_S = 30
RACE_OPEN_GRACE_S = 20 * 60             # closed longer ago than this = "pending", not "open"
VERSIONS_MD = os.path.join(RESULTS, "VERSIONS.md")
RACE30_EPOCH = calendar.timegm(time.strptime(RACE30_UTC, "%Y-%m-%dT%H:%M:%SZ"))


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _cnt(n):
    """A count with thousands separators. Kalshi sells fractional contracts
    (26.31 of them, say): under 100 the decimals are kept, past it they are
    noise on a total and rounded away."""
    n = _f(n)
    if abs(n - round(n)) < 0.005 or n >= 100:
        return "{:,}".format(int(round(n)))
    return "{:,.2f}".format(n)


def _usd(x):
    """Whole dollars with thousands separators, for 'on $58,120 risked'."""
    return "{:,.0f}".format(_f(x))


def _of100(x):
    return "-" if x is None else "%.1f" % (100.0 * x)


def _md(day):
    return str(day or "")[5:].replace("-", "/")


def _leg_name(tk):
    """'BTC' for KXBTC15M-..., 'XRP' for a coin-race leg KXCRYPTOLEAD15M-...-XRP."""
    tk = str(tk or "")
    if tk.startswith(RACE_SERIES):
        return tk.rsplit("-", 1)[-1]
    return coin(tk)


def day_minus(day, k):
    d = datetime.date.fromisoformat(day) - datetime.timedelta(days=k)
    return d.isoformat()


def days_between(day0, day1):
    """Calendar days from day0 to day1 inclusive (1 when equal)."""
    return (datetime.date.fromisoformat(day1) - datetime.date.fromisoformat(day0)).days + 1


# ---- Kalshi's rows, cached on the file ------------------------------------
_RAW = {}


def raw_ledger(path):
    """Kalshi's settlement rows from `path`, re-read only when the file changes."""
    try:
        st = os.stat(path)
    except OSError:
        return []
    key = (st.st_mtime, st.st_size)
    hit = _RAW.get(path)
    if hit and hit[0] == key:
        return hit[1]
    rows = [r for r in pinledger.load_cache(path).values() if isinstance(r, dict)]
    _RAW[path] = (key, rows)
    return rows


def markets_from(rows, sides=None):
    """{ticker: market} -- ONE entry per market, everything from Kalshi's row.

    n / cost / fee / paid (= cost + fee, the dollars risked), pnl, payout,
    value (the settlement per contract: 1 on yes, 0 on no, 0.5 on a tie),
    won (net >= 0, so a hedged market is scored by its net), tie, hedged,
    the ENTRY side and its price, and hedge_pnl: what the other side got
    back, on its own.

    THE ENTRY SIDE comes from the bot's own records when it has them
    (`sides` = {ticker: 'yes'|'no'}; the opposite of what its hedge bought)
    and from the bigger count otherwise. Two real cases made both
    necessary: a FULL hedge has EQUAL counts (most of them do), and the
    count rule alone dropped every one -- 21 hedged losses that 'got back
    $0.44'; and a hedge can be BIGGER than its entry (26 NO at 97c hedged
    with 79 YES at 30c), where the count rule crowns the hedge as the entry
    and books the entry's loss as the hedge's take. With equal counts and
    no record the market keeps no side and no hedge figure, never a guess.
    """
    sides = sides or {}
    out = {}
    for s in rows:
        tk = s.get("ticker") or ""
        st = pindesk.parse_t(s.get("settled_time"))
        day = pinday.et_day_of_ticker(tk) or (pinday.et_day_of_epoch(st) if st is not None else None)
        if not tk or day is None:
            continue
        m = out.get(tk)
        if m is None:
            m = out[tk] = {"tk": tk, "day": day, "book": pinday.book_of(tk),
                           "close": pinflat.close_epoch(tk) or st,
                           "event": tk.rsplit("-", 1)[0],
                           "yes_n": 0.0, "no_n": 0.0, "yes_cost": 0.0, "no_cost": 0.0,
                           "fee": 0.0, "pnl": 0.0, "value": None, "result": None}
        m["yes_n"] += pinledger.money(s, "yes_count_fp")
        m["no_n"] += pinledger.money(s, "no_count_fp")
        m["yes_cost"] += pinledger.money(s, "yes_total_cost_dollars")
        m["no_cost"] += pinledger.money(s, "no_total_cost_dollars")
        m["fee"] += pinledger.money(s, "fee_cost")
        m["pnl"] += pinledger.pnl(s)
        res = str(s.get("market_result") or "").strip().lower()
        v = None
        if s.get("value") is not None:
            v = _f(s.get("value"), None)
            v = None if v is None or not (0.0 <= v <= 100.0) else v / 100.0
        if v is None:
            v = 1.0 if res == "yes" else (0.0 if res == "no" else None)
        m["value"] = v
        m["result"] = res or m["result"]
    for m in out.values():
        yn, nn, yc, nc = m["yes_n"], m["no_n"], m["yes_cost"], m["no_cost"]
        m["n"] = yn + nn
        m["cost"] = yc + nc
        m["paid"] = m["cost"] + m["fee"]
        m["won"] = m["pnl"] >= 0
        v = m["value"]
        m["tie"] = v is not None and 0.0 < v < 1.0
        m["hedged"] = yn > 0 and nn > 0
        if m["n"] > 0 and sides.get(m["tk"]) in ("yes", "no"):
            side = sides[m["tk"]]
        elif yn > nn:
            side = "yes"
        elif nn > yn:
            side = "no"
        else:
            side = None
        m["side"] = side
        m["payout"] = m["pnl"] + m["paid"]
        m["price"] = (yc / yn if side == "yes" else nc / nn) if side else None
        m["hedge_pnl"] = None
        if m["hedged"] and side and v is not None:
            hn, hc = (nn, nc) if side == "yes" else (yn, yc)
            vh = (1.0 - v) if side == "yes" else v
            m["hedge_pnl"] = hn * vh - hc
    return out


def first_entries(orders):
    """{ticker: seconds left when the FIRST filled order went out}. From the
    bots' order records (`tau_at_send`); None when the record has no clock."""
    out = {}
    for o in sorted((o for o in orders if o.get("tk") and o.get("t")), key=lambda o: o["t"]):
        if _f(o.get("filled")) <= 0:
            continue
        out.setdefault(o["tk"], o.get("tau"))
    return out


def window_stats(ms, taus):
    """Every number for one window of markets. `taus` is first_entries()."""
    st = {"markets": len(ms), "closes": len({m["close"] for m in ms}),
          "contracts": sum(m["n"] for m in ms), "risked": sum(m["paid"] for m in ms),
          "net": sum(m["pnl"] for m in ms), "fees": sum(m["fee"] for m in ms)}
    won = [m for m in ms if m["won"]]
    lost = [m for m in ms if not m["won"]]
    st["won"] = len(won)
    st["won_risked"] = sum(m["paid"] for m in won)
    days = {}
    for m in ms:
        days[m["day"]] = days.get(m["day"], 0.0) + m["pnl"]
    st["days"] = days
    st["best_day"] = max(days.items(), key=lambda kv: kv[1]) if days else None
    st["worst_day"] = min(days.items(), key=lambda kv: kv[1]) if days else None
    st["worst_market"] = min(ms, key=lambda m: m["pnl"]) if ms else None
    st["losses"] = len(lost)
    st["lost_total"] = sum(m["pnl"] for m in lost)
    st["largest_loss"] = min((m["pnl"] for m in lost), default=0.0)
    hl = [m for m in lost if m["hedged"]]
    hw = [m for m in won if m["hedged"]]
    st["hedged_losses"] = len(hl)
    st["recovered"] = sum(m["hedge_pnl"] or 0.0 for m in hl)
    st["hedged_wins"] = len(hw)
    st["wasted"] = sum(m["hedge_pnl"] or 0.0 for m in hw)
    c, r = st["contracts"], st["risked"]
    st["payout"] = sum(m["payout"] for m in ms)
    st["breakeven_d"] = (r / c) if c else None
    # PAYOUT PER CONTRACT is the actual that pairs with the break-even:
    # net = payout - paid exactly, so (win_n - breakeven_d) x contracts is
    # the money. 'Dollars on winning markets / dollars risked' is shown too
    # but it ignores what a lost-but-hedged market or a tie still paid, and
    # its gap to the break-even can carry the wrong sign.
    st["win_n"] = (st["payout"] / c) if c else None
    st["win_d"] = (st["won_risked"] / r) if r else None
    st["win_c"] = (len(won) / len(ms)) if ms else None
    pp = [m["paid"] / m["n"] for m in ms if m["n"] > 0]
    st["breakeven_c"] = (sum(pp) / len(pp)) if pp else None
    st["per100"] = (st["net"] / r * 100.0) if r else None
    tm = {"late": [0, 0.0], "early": [0, 0.0], "other": [0, 0.0]}
    for m in ms:
        tau = taus.get(m["tk"], "none")
        if tau == "none" or tau is None:
            k = "other"
        else:
            tau = _f(tau, 999)
            k = "late" if tau <= 20 else ("early" if tau <= 45 else "other")
        tm[k][0] += 1
        tm[k][1] += m["pnl"]
    st["timing"] = tm
    return st


def stats_block(title, st, ndays=None):
    if not st["markets"]:
        return "%s\nNothing settled." % title
    L = [title]
    L.append("Made %s on $%s risked; %s mkts, %s closes, %s contracts; fees $%.2f."
             % (money(st["net"]), _usd(st["risked"]), _cnt(st["markets"]), _cnt(st["closes"]),
                _cnt(st["contracts"]), st["fees"]))
    bd, wd = st["best_day"], st["worst_day"]
    d = ""
    if len(st["days"]) >= 2:
        d = "Best day %s (%s), worst %s (%s)" % (money(bd[1]), _md(bd[0]), money(wd[1]), _md(wd[0]))
    if ndays and ndays >= 2:
        d += "%savg %s/day over %d days" % ("; " if d else "", money(st["net"] / ndays), ndays)
    if d:
        L.append(d + ".")
    L.append("Won %s of %s mkts (%s of 100); %s of 100 contracts paid; by $ risked %s."
             % (_cnt(st["won"]), _cnt(st["markets"]), _of100(st["win_c"]), _of100(st["win_n"]),
                _of100(st["win_d"])))
    if st["breakeven_d"] is not None and st["win_n"] is not None:
        L.append("Break-even %s of 100 contracts at %.1fc avg paid (fee in): margin %+.1f pts = %s per "
                 "$100 risked. By count %s of 100 mkts must win; %s did."
                 % (_of100(st["breakeven_d"]), 100.0 * st["breakeven_d"],
                    100.0 * (st["win_n"] - st["breakeven_d"]), money(st["per100"]),
                    _of100(st["breakeven_c"]), _of100(st["win_c"])))
    if st["losses"]:
        wm = st["worst_market"]
        h = "%d hedged, their hedge legs netted %s" % (st["hedged_losses"], money(st["recovered"]))
        if st["hedged_wins"]:
            h += "; hedge legs on won mkts netted %s" % money(st["wasted"])
        L.append("Losses %d: %s, avg %s, worst %s (%s, %s %s); %s."
                 % (st["losses"], money(st["lost_total"]), money(st["lost_total"] / st["losses"]),
                    money(st["largest_loss"]), BOT_WORD.get(main_bot_of(wm["tk"]), "?"), _leg_name(wm["tk"]),
                    _md(wm["day"]), h))
    else:
        L.append("No losses.")
    tm = st["timing"]
    known = tm["late"][0] + tm["early"][0]
    if known:
        L.append("First buys: %.0f%% with 20 s or less left (%d mkts, %s), %.0f%% at 21-45 s (%d mkts, %s)%s."
                 % (100.0 * tm["late"][0] / known, tm["late"][0], money(tm["late"][1]),
                    100.0 * tm["early"][0] / known, tm["early"][0], money(tm["early"][1]),
                    ("; %d not timed" % tm["other"][0]) if tm["other"][0] else ""))
    return "\n".join(L)


# ---- versions ---------------------------------------------------------------
# A joined name ('# v-reopen98 + v-floor90 -- ...') and a 'LIVE ' before the
# date ('# v-ladder-settlefix -- LIVE 2026-09-29 ...') are both real headers;
# missing them made /stats date pin's window from a clean-room entry (09-30).
_VER_RE = re.compile(r"^#\s+(v-\S+(?:\s*\+\s*v-\S+)*)\s+--\s+(?:LIVE\s+)?(\d{4}-\d{2}-\d{2})"
                     r"(?:\s+(~?)(\d{2}):(\d[\dx])(?::\d{2})?Z?)?\s*(.*)$", re.I)
# Entries that are another bot's (the coin race, the clean-room forecaster and penny ladder, the boot entries that name
# them ...) are decided by ONE rule, the registry's (bots.version_claim, which botstats.version_of keeps); the self-test
# fails if the two pick different versions. v-tg-rebuild step 5 (2026-10-30): this file's own word list (_NOT_PIN_RE)
# is gone -- it knew neither the FX taker's v-fx / fxtake headings nor a combined heading's 'v-ladder-<x>' names.
INFRA_VER = r"v-(tg|phone|telegram|wifi|recorder|collector)\b"      # = botstats.INFRA_VER: no bot's version


def versions(path):
    """[(name, epoch, approx, title)] newest first, from the `# v-... -- <UTC>`
    headers of VERSIONS.md. A `~06:0xZ` time reads as 06:00 and is marked
    approximate; a header with no time is midnight ET of its date."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return out
    for line in lines:
        m = _VER_RE.match(line.rstrip())
        if not m:
            continue
        name, day, tilde, hh, mm, title = m.groups()
        approx = bool(tilde) or hh is None or "x" in str(mm or "").lower()
        if hh is None:
            epoch = et_day_start(day)
        else:
            try:
                epoch = calendar.timegm(time.strptime("%sT%s:%s" % (day, hh, mm.lower().replace("x", "0")),
                                                      "%Y-%m-%dT%H:%M"))
            except ValueError:
                continue
        out.append((name, epoch, approx, title.strip()))
    return out


def live_version(path):
    """The newest version entry that is about the UP/DOWN bot -- the coin
    race's entries (v-race30, v-race-tie1...) and the clean-room bots'
    (v-forecaster-*, v-ladder-*, v-keepalive-cleanroom) are other bots' and
    would otherwise sit on top and date every 'since the version' figure
    wrong."""
    for v in versions(path):
        if re.match(INFRA_VER, v[0].lower()) or _bots.version_claim(DESK_BOT, v[0], v[3]) is None:
            continue
        return v
    return None


# ---- the process table ------------------------------------------------------
_PROCS = {"t": 0.0, "rows": None}
PROC_REFRESH_S = 90                     # the background refresher's period
_PS_LIST = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            "ForEach-Object { \"$($_.ProcessId)" + chr(96) + "t$($_.CommandLine)\" }")


def list_python_procs(timeout=30):
    """[(pid, command line)] for every python.exe, from Windows itself, or
    None when the call fails. It takes 10-12 s on the operator's box with
    sixty python processes up, which is why it runs on a background thread
    (proc_refresher) and never inside a command. None, not [] -- an empty
    list would read as 'nothing running', and that is the one thing a
    failed read must never say."""
    rows = []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_LIST],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if out.returncode != 0:
            return None
        for line in (out.stdout or "").splitlines():
            pid, _tab, cl = line.partition("\t")
            if not cl.strip():
                continue
            try:
                rows.append((int(pid.strip()), cl.strip()))
            except ValueError:
                pass
    except Exception:                                           # noqa: BLE001
        return None
    return rows


def python_procs(max_age_s=None):
    """The cached process table, or None when it cannot be read. Fresh
    enough (the refresher keeps it under PROC_REFRESH_S old) it is returned
    at once; stale or empty, one synchronous read is made."""
    age = time.time() - _PROCS["t"]
    if _PROCS["rows"] is not None and age < (max_age_s or 2 * PROC_REFRESH_S):
        return _PROCS["rows"]
    rows = list_python_procs()
    if rows is not None:
        _PROCS.update(t=time.time(), rows=rows)
    return rows


def cached_python_procs():
    """The table the refresher last read while it is fresh, else None (= 'could not be read'). Never asks
    Windows itself, so a page that can live with 'unknown' (/racestats) never holds the poll thread -- and
    the alerts behind it -- for a 10-30 s WMI read when the cache is cold or stale."""
    if _PROCS["rows"] is not None and time.time() - _PROCS["t"] < 2 * PROC_REFRESH_S:
        return _PROCS["rows"]
    return None


def proc_refresher(period=None):
    """Background thread body: re-read the process table every `period` s."""
    while True:
        rows = list_python_procs()
        if rows is not None:
            _PROCS.update(t=time.time(), rows=rows)
        time.sleep(period or PROC_REFRESH_S)


def argv_opt(cl, flag):
    toks = str(cl or "").split()
    if flag in toks:
        i = toks.index(flag)
        if i + 1 < len(toks):
            return toks[i + 1]
    return None


def _log_name(path, prefix):
    b = os.path.basename(str(path or "").replace("\\", "/"))
    b = b[:-6] if b.endswith(".jsonl") else b
    return b[len(prefix):] if b.startswith(prefix) else b


def _fleet_scripts():
    """fleet()'s scripts in the order they are tried, and {script: Bot} of the main account's other live bot (the coin
    race). v-tg-rebuild step 5: the desk bot's and the race's scripts are the registry's Bot.script (every bot with a pot
    in subaccount 0); the desk bot's two older copies and the command-line paper arm are no registry bot's."""
    other = {b.script: b for b in _bots.bots_on("0") if b.name != DESK_BOT}
    return ("pinrun_afternoon.py", "pinrun913.py", _bots.get(DESK_BOT).script, "cmdarm.py") + tuple(other), other


def fleet(procs):
    """What is running, by role: the live up/down bot, the penny race bot,
    the paper arms (by --arm-name / log name) and the paper race arms."""
    out = {"live": None, "penny": None, "arms": [], "race_arms": [], "unknown": procs is None}
    scripts, race = _fleet_scripts()
    for pid, cl in (procs or []):
        low = cl.lower()
        script = next((s for s in scripts if s in low), None)
        if not script:
            continue
        toks = cl.split()
        is_live = "--live" in toks
        if script in race:
            if race[script].is_live(toks):              # the race's live rule: --live, not --paper-live
                out["penny"] = (pid, cl)
            else:
                out["race_arms"].append(_log_name(argv_opt(cl, "--log"), script[:-3] + "-") or "race-arm")
        elif script == "cmdarm.py":
            out["arms"].append(_log_name(argv_opt(cl, "--out"), "") or "cmdarm")
        elif is_live:
            out["live"] = (pid, cl)
        else:
            out["arms"].append(argv_opt(cl, "--arm-name") or script[:-3])
    out["arms"].sort()
    out["race_arms"].sort()
    return out


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# ---- the coin race ------------------------------------------------------------
def races_from(markets):
    """{event: race} from the coin-race markets: one race = one 15-minute
    contest, its legs = the markets we held. A race is a TIE when any leg
    settled at 50c (Kalshi's `value: 50`), WON when its net is >= 0 and not a
    tie, LOST otherwise."""
    out = {}
    for m in markets.values():
        if m["book"] != "coin race":
            continue
        r = out.setdefault(m["event"], {"event": m["event"], "close": m["close"], "day": m["day"],
                                        "legs": [], "pnl": 0.0, "paid": 0.0, "cost": 0.0,
                                        "n": 0.0, "payout": 0.0, "tie": False})
        r["legs"].append(m)
        r["pnl"] += m["pnl"]
        r["paid"] += m["paid"]
        r["cost"] += m["cost"]
        r["n"] += m["n"]
        r["payout"] += m["pnl"] + m["paid"]
        r["tie"] = r["tie"] or m["tie"]
        if m["close"] is not None and (r["close"] is None or m["close"] < r["close"]):
            r["close"] = m["close"]
    for r in out.values():
        r["legs"].sort(key=lambda m: m["tk"])
        r["won"] = (not r["tie"]) and r["pnl"] >= 0
        r["lost"] = (not r["tie"]) and r["pnl"] < 0
    return out


def race_line(r):
    legs = ["%s %s %.0fc" % (_leg_name(m["tk"]), m["side"] or "?", 100.0 * (m["price"] or 0)) for m in r["legs"]]
    if len(legs) > 3:
        legs = legs[:3] + ["+%d more" % (len(legs) - 3)]
    verdict = "TIE" if r["tie"] else ("WON" if r["won"] else "LOST")
    return "%s  %s  %s %s" % (et_str(r["close"], "%m/%d %I:%M %p") if r["close"] else "?",
                              " + ".join(legs), verdict, money(r["pnl"]))


def race_rows(races, n=10):
    """The newest n races as table lines for /race: a heading a day, then the close (ET), each leg (coin,
    side, price paid), the race's money and TIE / WON / LOST -- race_line's facts, one leg a row."""
    rows, day = [], None
    for r in sorted(races.values(), key=lambda r: -(r["close"] or 0))[:n]:
        d = et_str(r["close"], "%a %b %d") if r["close"] else "?"
        if d != day:
            rows.append((d,))
            day = d
        legs = ["%s %s %.0fc" % (_leg_name(m["tk"]), m["side"] or "?", 100.0 * (m["price"] or 0)) for m in r["legs"]]
        if len(legs) > 3:
            legs = legs[:3] + ["+%d more" % (len(legs) - 3)]
        verdict = "TIE" if r["tie"] else ("WON" if r["won"] else "LOST")
        rows.append((hm(r["close"]) if r["close"] else "?", legs[0] if legs else "-", usd(r["pnl"]), verdict))
        for x in legs[1:]:
            rows.append(("", x, "", ""))
    return table(rows, "llrl")


def race_tally(rs):
    n = len(rs)
    w = sum(1 for r in rs if r["won"])
    t = sum(1 for r in rs if r["tie"])
    lo = sum(1 for r in rs if r["lost"])
    return {"races": n, "won": w, "tie": t, "lost": lo, "net": sum(r["pnl"] for r in rs),
            "legs": sum(len(r["legs"]) for r in rs), "n": sum(r["n"] for r in rs),
            "paid": sum(r["paid"] for r in rs), "cost": sum(r["cost"] for r in rs),
            "payout": sum(r["payout"] for r in rs)}


def race_tally_line(t):
    if not t["races"]:
        return "no races."
    s = "%d races: %d won, %d tie, %d lost. %s." % (t["races"], t["won"], t["tie"], t["lost"], money(t["net"]))
    if t["n"] > 0:
        s += (" %d legs at %.1fc avg; break-even %s of 100 legs must pay, actual %s."
              % (t["legs"], 100.0 * t["cost"] / t["n"], _of100(t["paid"] / t["n"]), _of100(t["payout"] / t["n"])))
    return s


_LOGS = {}


def log_records(path, kinds):
    """The records of `kinds` in one jsonl log, cached on the file's size.
    Lines are screened by substring before json.loads -- a race log is a
    few MB of refusals for every record that matters."""
    try:
        st = os.stat(path)
    except OSError:
        return []
    key = (st.st_size, st.st_mtime, tuple(kinds))
    hit = _LOGS.get(path)
    if hit and hit[0] == key:
        return hit[1]
    needles = ['"%s"' % k for k in kinds]
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not any(n in line for n in needles):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("kind") in kinds:
                    out.append(r)
    except OSError:
        return []
    _LOGS[path] = (key, out)
    return out


def penny_view(recs, now, ledger_events=()):
    """The live coin race's own view of itself, from its log (pinracepenny-live.jsonl -- the file kept the
    name from its penny-test days): the last start record (rails), whether the stop rail has fired SINCE
    that start, the newest bank_size record since that start (v-race-snowball: the size it took from the
    bank), the legs it holds on races not yet scored, and the dollars out."""
    start = halt = size = None
    fills, done, staked = {}, set(), None
    for r in recs:
        k = r.get("kind")
        if k == "start":
            start, halt, size = r, None, None
        elif k == "bank_size":
            size = r
        elif k == "live_halt":
            halt = r
        elif k == "live_order":
            if _f(r.get("filled")) > 0 and r.get("event"):
                fills.setdefault(r["event"], []).append(r)
            if r.get("staked") is not None:
                staked = _f(r["staked"])
        elif k == "live_settled":
            if r.get("event"):
                done.add(r["event"])
            if r.get("staked_open") is not None:
                staked = _f(r["staked_open"])
    open_, pending = [], []
    for evt, legs in fills.items():
        if evt in done or evt in ledger_events:
            continue
        c = pinflat.close_epoch(legs[0].get("ticker"))
        (open_ if c is None or c >= now - RACE_OPEN_GRACE_S else pending).append((evt, c, legs))
    open_.sort(key=lambda x: x[1] or 0)
    pending.sort(key=lambda x: x[1] or 0)
    return {"start": start, "halt": halt, "open": open_, "pending": pending, "staked": staked, "bank_size": size}


def race_size_words(start, size):
    """How big the live coin race bets, in words, from its own log.

    IT IS NOT A PENNY TEST ANY MORE (2026-10-18; the operator read /race's 'penny bot ... 20 contracts a
    leg, $40 out at most' and asked whether it still bets a fixed size). Since v-race-snowball (10-11) a
    start record carries `bank_sizing` {contracts_per_bank, stake_per_bank}: contracts a leg =
    floor(bank x contracts_per_bank) and the open-stake cap = bank x stake_per_bank, the bank re-read
    from the main account at most every 5 minutes, only between races with no leg open (VERSIONS.md
    v-race-snowball), each read logged as a `bank_size` record. The start record's live_rails (20 / $40)
    are only the size it starts from. Without bank_sizing the size is fixed and the words say so. None
    when there is no start record."""
    if not start:
        return None
    rails = start.get("live_rails") or {}
    bsz = start.get("bank_sizing") or {}
    cpb, spb = _fnum(bsz.get("contracts_per_bank")), _fnum(bsz.get("stake_per_bank"))
    free = "; settled bets free it up" if rails.get("rolling") else ""
    if cpb and spb:
        n = _fnum((size or {}).get("contracts"))
        bank = _fnum((size or {}).get("bank"))
        stake = _fnum((size or {}).get("stake"))
        if n is not None and bank and stake is not None:
            when = pindesk.parse_t(size.get("t"))
            return ("bets grow with the bank: %g contracts a leg = the %s bank x %g, rounded down (%.2f per $100 "
                    "of bank); at most %s open at once = bank x %g (%.2f%%)%s. Bank last read %s ET" % (
                        n, dollars(bank), cpb, 100.0 * cpb, dollars(stake), spb, 100.0 * spb, free,
                        et_str(when, "%b %d %I:%M %p") if when else "?"))
        return ("bets grow with the bank: %.2f contracts a leg per $100 of bank and at most %.2f%% of the bank "
                "open at once%s; no size read logged since its start (it starts from %g contracts, $%.0f)" % (
                    100.0 * cpb, 100.0 * spb, free, _f(rails.get("max_contracts"), 1), _f(rails.get("max_stake"))))
    mc = _f(rails.get("max_contracts"), 1)
    return "fixed size: %g contract%s a leg, $%.0f out at most%s" % (
        mc, "" if mc == 1 else "s", _f(rails.get("max_stake")),
        " (settled bets give it back)" if rails.get("rolling") else " in total")


def race_rule_words(start):
    """When the live coin race buys and when it stops, from its start record. --live-max-losses N > 1
    (v-race40) stops it for the rest of the ET day after N losing races -- botstats.settings_race reads
    the same flag the same way."""
    if not start:
        return None
    rails = start.get("live_rails") or {}
    ml = _fnum(argv_opt(" ".join(str(a) for a in (start.get("argv") or [])), "--live-max-losses"))
    if ml is not None and ml > 1:
        stop = "stops for the rest of the ET day after %g losing races" % ml
    else:
        stop = "stops on the first loss" if rails.get("stop_on_loss") else "does NOT stop on a loss"
    return "only inside %d s, %.0fc or better, up to %d legs a race, %s" % (
        _f(rails.get("tau_max")), 100.0 * _f(rails.get("min_price")), _f(rails.get("max_legs")), stop)


def rails_words(rails):
    if not rails:
        return "rails unknown (no start record)"
    mc = _f(rails.get("max_contracts"), 1)
    w = ["%g contract%s a leg" % (mc, "" if mc == 1 else "s"),
         "$%.0f out at most%s" % (_f(rails.get("max_stake")),
                                  " (settled bets give it back)" if rails.get("rolling") else " in total"),
         "only inside %d s" % _f(rails.get("tau_max")),
         "%.0fc or better" % (100.0 * _f(rails.get("min_price"))),
         "up to %d legs" % _f(rails.get("max_legs")),
         "stops on the first loss" if rails.get("stop_on_loss") else "does NOT stop on a loss"]
    return ", ".join(w)


def arm_results(path):
    """{event: {'positions', 'pnl', 'tie'}} from a paper race arm's own log.
    A --paper-live arm scores its legs in `live_settled` (flagged paper);
    a plain arm in `settled`. The last record for an event wins."""
    recs = log_records(path, ("live_settled", "settled"))
    live = {r["event"]: r for r in recs if r.get("kind") == "live_settled" and r.get("event")}
    plain = {r["event"]: r for r in recs if r.get("kind") == "settled" and r.get("event")}
    src = live if live else plain
    out = {}
    for evt, r in src.items():
        out[evt] = {"positions": int(_f(r.get("positions"))), "pnl": _f(r.get("pnl")),
                    "tie": bool(r.get("tie")) or _f(r.get("ties")) > 0}
    return out


_SPANS = {}


def log_span(path):
    """{'first', 'last': epoch of the log's first / last record, 'end': True when the last record is an
    `end` record} -- from the first line and the last 64 KB only, cached on the file's size and mtime.
    None when the file cannot be read."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_size, st.st_mtime)
    hit = _SPANS.get(path)
    if hit and hit[0] == key:
        return hit[1]

    def rec(line):
        try:
            r = json.loads(line)
            return r if isinstance(r, dict) else None
        except ValueError:
            return None
    try:
        with open(path, "rb") as fh:
            head = fh.read(65536)
            fh.seek(max(0, st.st_size - 65536))
            tail = fh.read()
    except OSError:
        return None
    first = last = None
    for raw in head.decode("utf-8", "replace").split("\n"):
        r = rec(raw)
        if r and r.get("t"):
            first = r
            break
    tl = tail.decode("utf-8", "replace").split("\n")
    for raw in reversed(tl[1:] if st.st_size > 65536 else tl):     # a cut first line is not a record
        r = rec(raw)
        if r and r.get("t"):
            last = r
            break
    out = {"first": pindesk.parse_t((first or {}).get("t")), "last": pindesk.parse_t((last or {}).get("t")),
           "end": (last or {}).get("kind") == "end"}
    _SPANS[path] = (key, out)
    return out


RACE_ARMS_SCORED = "race_arms_scored.json"      # written once by .sweep\q-2026-10-18e\tg\harness\score_race_arms.py


def race_arms_scored(results):
    """The /racestats arms re-scored on Kalshi's results (results/race_arms_scored.json), or None. The arms
    are paper and STOPPED (09-27 .. 10-01), so a one-off scoring is final; text_racestats uses an arm's
    entry only while the arm's log is the size it was scored at."""
    return read_json(os.path.join(results, RACE_ARMS_SCORED))


def arm_record(results, races):
    """An arm's W/T/L on the given races (tie-aware: a race Kalshi tied is a
    tie whatever the arm's log booked), plus its own-log money."""
    w = t = lo = 0
    net = 0.0
    ties_as_wins = 0
    entered = 0
    for evt, r in races.items():
        a = results.get(evt)
        if not a or a["positions"] <= 0:
            continue
        entered += 1
        net += a["pnl"]
        if r["tie"] or a["tie"]:
            t += 1
            if a["pnl"] >= 0:
                ties_as_wins += 1
        elif a["pnl"] < 0:
            lo += 1
        else:
            w += 1
    return {"entered": entered, "won": w, "tie": t, "lost": lo, "net": net, "ties_as_wins": ties_as_wins}


def z3_progress(results, races_all):
    """The z3 arm against its bar, over EVERY race it entered: a loss is a
    losing race or a tie (Kalshi's, where we held a leg, or its own flag)."""
    rows = sorted(((evt, a) for evt, a in results.items() if a["positions"] > 0), key=lambda kv: kv[0])
    losses = [1 if (a["pnl"] < 0 or a["tie"] or (evt in races_all and races_all[evt]["tie"])) else 0
              for evt, a in rows]
    return {"races": len(rows), "losses": sum(losses), "first50_losses": sum(losses[:Z3_KILL[1]])}


# ---- the disk ---------------------------------------------------------------
# run_all.ps1 line 41: `if ($free -lt 5) { Write-Host "LOW DISK - stopping" ; break }`
# -- the watchdog leaves its loop and BOTH recorders stop being restarted. The
# tape ends there and cannot be recreated. So: one alert under 8 GB, one more
# under 6, re-armed only when free space climbs back over 9.
DISK_WARN_GB, DISK_STOP_GB, DISK_REARM_GB = 8.0, 6.0, 9.0
DISK_HARD_STOP_GB = 5.0
DISK_GB_PER_DAY = 4.0                   # OPEN_WORK C1: the recorders write ~4 GB a day


def disk_alert(level, disk_gb):
    """(new level, message or None). `level` is the line already announced:
    0 none, 8 the under-8 alert went, 6 the under-6 alert went. A reading over
    9 GB re-arms both. An unreadable reading (None) changes nothing."""
    if disk_gb is None:
        return level, None
    if disk_gb > DISK_REARM_GB:
        return 0, None
    if disk_gb < DISK_STOP_GB and level != 6:
        return 6, ("DISK %.1f GB FREE -- %.1f GB from the %.0f GB line where the recorders STOP FOR GOOD "
                   "and the tape ends. Free space or plug in the new drive NOW. (Sent again only if it "
                   "climbs over %.0f GB and falls back.)"
                   % (disk_gb, disk_gb - DISK_HARD_STOP_GB, DISK_HARD_STOP_GB, DISK_REARM_GB))
    if disk_gb < DISK_WARN_GB and level == 0:
        return 8, ("DISK %.1f GB free, under %.0f GB. The recorders stop themselves for good at %.0f GB and "
                   "that tape cannot be recreated; at about %.0f GB a day that is roughly %.1f days. "
                   "Next warning under %.0f GB."
                   % (disk_gb, DISK_WARN_GB, DISK_HARD_STOP_GB, DISK_GB_PER_DAY,
                      max(0.0, disk_gb - DISK_HARD_STOP_GB) / DISK_GB_PER_DAY, DISK_STOP_GB))
    return level, None


# ===========================================================================
# /bots /pin /forecaster /ladder, and the money windows under /race.
#
# THE OPERATOR, 2026-09-30: "Can you make a spot in the bot to see each sub
# account, what's running, and as much details about them as possible? Also
# telegram commands for each sub account type so I can see everything I can
# about them like pin. Including day performance, long performance,
# everything you can. And are their totals added to the main pages total
# stats?"
#
# EVERY NUMBER HERE IS research/botstats.py's: Kalshi's settlements read PER
# SUBACCOUNT (a read with none mixes the pots -- the 2026-09-29 pinledger
# bug), money per market = payout on the winning side - both sides' cost -
# fee. Only the WORDS are built here, so the phone and the desktop cannot
# disagree about a number. The bots' logs say only what a bot DID today.
# A failed read is said as a failure -- never $0, never "not running".
#
# HIS QUESTION, answered on /bots every time: the main page (/today /days
# /stats and the desktop) reads kalshi_ledger.json, the MAIN account only --
# pin + coin race. The forecaster (subaccount 2), the ladder (subaccount
# 1), the weather dip-seller (subaccount 3, 2026-10-04; its cash sits in
# Kalshi's weather pool, exchange_index 0) and the FX taker (subaccounts 5 +
# 4, 2026-10-25) are separate pots and are added up only in /bots.
# ===========================================================================
# v-tg-rebuild step 5 (2026-10-30): from the registry -- BOT_CMDS = the generic one-bot page's commands (every alias of
# a bot with no page of its own; the race has /race), BOT_CMD_OF = the one command the phone names for each bot
BOT_CMDS = _bots.BOT_CMDS
BOT_CMD_OF = _bots.BOT_CMD_OF
PAGE_FOOTER = _bots.PAGE_FOOTER             # the line under a one-bot page (Bot.page_footer)
BS_WINDOWS = ("today", "yesterday", "last_7_days", "this_month", "all_time")
BS_LABEL = {"today": "Today", "yesterday": "Yesterday", "last_7_days": "Last 7 days",
            "this_month": "This month", "all_time": "All time"}


def _bs():
    """botstats, imported late: a broken edit there costs these commands, never the phone."""
    import botstats
    return botstats


def _pot_words(b):
    """A botstats bot's pot in words: 'subaccount 1', or 'subaccount 5 + subaccount 4' for the FX taker's two."""
    bs = _bs()
    subs = tuple(str(x) for x in (b.get("subaccounts") or [b["subaccount"]]))
    if not all(x in bs.SUB_NAME for x in subs):
        return "subaccount %s" % b["subaccount"]
    return bs.sub_name(subs if len(subs) > 1 else subs[0])


def _nof(k, word):
    return "%s %s%s" % (_cnt(k), word, "" if _f(k) == 1 else "s")


def _cash(x):
    return "?" if x is None else _bs().usd(x).lstrip("+")


def _ago(s):
    if s is None:
        return "?"
    s = _f(s)
    if s < 120:
        return "%d s ago" % s
    if s < 7200:
        return "%d min ago" % (s // 60)
    return "%.1f h ago" % (s / 3600.0)


def bs_window_line(w, label, unit="market", fmt=None, whose="its bank"):
    """'Today: +$1.62 on $59.54 put in (+2.7%) = +0.15% of its bank ($1,100.00); 2 markets, 2 won, 0 lost'.
    The first % is the return on what the bets cost; the second (2026-10-02) is the share of the pot
    it had when the window began -- all time: of the money put in -- and is left out when the pot is
    unknown, never guessed. None = Kalshi unread."""
    fmt = fmt or _bs().usd
    if w is None:
        return "%s: COULD NOT READ KALSHI" % label
    if not w["markets"]:
        return "%s: nothing settled yet" % label
    pw = _bs().pot_words(w, whose)
    return "%s: %s on %s put in (%s)%s; %s, %s won, %s lost" % (
        label, fmt(w["money"]), _cash(w["put_in"]), _bs().pct(w["return_pct"]), (" = " + pw) if pw else "",
        _nof(w["markets"], unit), _cnt(w["won"]), _cnt(w["lost"]))


def _roi_tail(w):
    """' (+1.9% on bets · +0.24% of bank)' for a botstats window: its return on what the bets cost and, when its
    pot is known, its share of the pot. Operator 10-24: "put roi percentages everywhere applicable"."""
    bs = _bs()
    bits = []
    if w.get("return_pct") is not None:
        bits.append("%s on bets" % bs.pct(w["return_pct"]))
    if w.get("pot_pct") is not None:
        bits.append("%s of bank" % bs.pot_pct_txt(w["pot_pct"]))
    return (" (%s)" % " · ".join(bits)) if bits else ""


def _short(w, fmt):
    """'+$2.63 (+1.9% on bets · +0.24% of bank)' -- the money, its return on what the bets cost and, when its pot
    is known, its share of the pot."""
    if w is None:
        return "?"
    if not w["markets"]:
        return "nothing yet"
    return fmt(w["money"]) + _roi_tail(w)


def bs_running_lines(r):
    """Running or not, and WHY not: its stop file, a halt, or it died on its own."""
    L = []
    if r["alive"] is None:
        L.append("Running: COULD NOT TELL -- the Windows process list could not be read.")
    elif r["alive"]:
        L.append("Running: YES, pid %s, since %s." % (r["pid"], r["started_et"] or "an unknown time"))
    elif r["stop_flag"]:
        L.append("Running: NO -- stopped by its stop file (set %s)%s." % (
            r["stop_flag_et"] or "?", (': "%s"' % r["stop_flag_text"]) if r["stop_flag_text"] else ""))
    else:
        L.append("Running: NO, and there is no stop file -- it stopped on its own.")
    if r["halted"]:
        L.append("HALTED %s: %s." % (r["halted"]["t_et"], r["halted"]["why"] or r["halted"]["what"]))
    for p in r["problems"]:
        if not (p.startswith("NOT RUNNING and no stop file") or p.startswith("could not read the Windows")):
            L.append("! " + p)                           # the two skipped are said above
    if r["log"]:
        L.append("Its log last wrote %s (%s)." % (r["log_last_et"] or "?", _ago(r["log_age_s"])))
    return L


def bs_setup_lines(r):
    L = ["Version: %s, live since %s." % (r["version"], r["version_et"] or "an unrecorded time")
         if r["version"] else "Version: no entry for it in VERSIONS.md."]
    if r["settings_text"]:
        L.append("Settings: %s." % r["settings_text"])
    L.append("Keep-alive: %s." % (r["keepalive"] or "NONE -- if it dies, nothing restarts it"))
    return L


def bs_money_lines(m, unit="market", fmt=None):
    """Every money window of one bot, its worst and best market and day, and the last 7 days."""
    bs = _bs()
    fmt = fmt or bs.usd
    if not m["ok"]:
        return ["MONEY: COULD NOT READ KALSHI (%s). Nothing here is a zero -- it is unknown."
                % (m.get("error") or "?")]
    L = ["MONEY -- %s, read %s; a %s counts on the ET day it closed:"
         % (m["source"], m["as_of_et"] or "?", unit)]
    if not m["complete"]:
        L.append("HISTORY STILL LOADING: all time and this month are partial.")
    if m["stale"]:
        L.append("The last Kalshi read failed (%s); these are from %s." % (m["error"], m["as_of_et"] or "?"))
    for k in BS_WINDOWS:
        w = m[k]
        label = w["label"] if w else BS_LABEL[k]
        if k == "all_time" and m.get("first_day"):
            label += " (since %s)" % bs.day_label(m["first_day"])
        line = bs_window_line(w, label, unit, fmt)
        if k in ("last_7_days", "all_time") and w and w["active_days"] > 1:
            line += "; %s up, %d down" % (_nof(w["days_up"], "day"), w["days_down"])
        L.append(line)
    note = bs._pot_note(m)                  # what '% of its bank' means, or why it is not shown
    if note:
        L.append(note)
    at = m["all_time"]
    if at and not at["markets"]:
        L.append("Nothing settled yet on Kalshi for this bot.")
        return L
    for k, name in (("today", "today"), ("all_time", "all time")):
        w = m[k]
        if w and w["markets"]:
            wd = "" if k == "today" else " (%s)" % bs.day_label(w["worst"]["day"])
            bd = "" if k == "today" else " (%s)" % bs.day_label(w["best"]["day"])
            L.append("Worst %s %s: %s %s%s; best %s %s%s." % (
                unit, name, fmt(w["worst"]["money"]), w["worst"]["what"], wd,
                fmt(w["best"]["money"]), w["best"]["what"], bd))
    days = m.get("all_days") or []
    if len(days) > 1:
        bd = max(days, key=lambda d: d["money"])
        wd = min(days, key=lambda d: d["money"])
        L.append("Best day %s (%s), worst day %s (%s), over %d days with a settlement." % (
            fmt(bd["money"]), bs.day_label(bd["day"]), fmt(wd["money"]), bs.day_label(wd["day"]), len(days)))
    if at and at["fees"] > 0.004:
        L.append("Fees all time: %s (already inside the money above)." % _cash(at["fees"]))
    if at and at["hedged"]:
        L.append("Bought both sides (hedged): %s all time." % _nof(at["hedged"], unit))
    d7 = [d for d in m["days_7"] if not d["before_first"]]
    if d7:
        L.append("By day:")
        for d in d7:
            L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                                   "%s%s, %s (%d won, %d lost)" % (fmt(d["money"]), _roi_tail(d),
                                                                   _nof(d["markets"], unit), d["won"], d["lost"])))
    return L


def bs_open_lines(o, unit="bet"):
    if not o["ok"]:
        return ["Open now: COULD NOT READ (%s)." % (o.get("error") or "?")]
    if not o["count"]:
        return ["Open now: none."]
    L = ["Open now: %s, %s at risk%s:" % (_nof(o["count"], unit), _cash(o["at_risk"]),
                                          (" (the last read failed; from %s)" % o["as_of_et"]) if o.get("stale") else "")]
    for p in o["positions"][:8]:
        L.append("  %s %s x%s, %s at risk" % (p["what"], p["side"].upper(), _cnt(p["contracts"]), _cash(p["at_risk"])))
    if o["count"] > 8:
        L.append("  +%d more" % (o["count"] - 8))
    return L


def bs_cash_line(bal):
    if not bal["ok"]:
        return "Cash: COULD NOT READ (%s)." % (bal.get("error") or "?")
    each = ""
    if bal.get("by_sub"):
        each = " (%s)" % ", ".join("%s %s" % (_bs().SUB_NAME.get(str(k), k), _cash(v)) for k, v in bal["by_sub"].items())
    return "Cash: %s%s -- %s." % (_cash(bal["dollars"]), each, bal["note"])


def bs_last_lines(last, fmt=None):
    fmt = fmt or _bs().usd
    if not last:
        return []
    L = ["Last %d settled:" % len(last)]
    for x in last:
        day = pinday.et_day_of_ticker(x["ticker"])
        L.append("  %s %s %s x%s: %s on %s put in" % (
            _bs().day_label(day) if day else (x["time_et"] or "?"), x["what"],
            {"both": "BOTH SIDES", "-": "-"}.get(x["side"], str(x["side"]).upper()),
            _cnt(x["contracts"]), fmt(x["money"]), _cash(x["put_in"])))
    return L


def bs_activity_lines(name, a):
    """What the bot DID today by its own log -- orders, fills, passes. Never money."""
    if not a["ok"]:
        return ["Today, its own log: %s." % (a.get("note") or "unreadable")]
    s = "Today, its own log (what it did, not money): %s sent, %d filled (%s contracts)" % (
        _nof(a["sent"], "order"), a["filled"], _cnt(a["contracts_filled"]))
    if a["not_filled"]:
        s += ", %d got nothing" % a["not_filled"]
    if a["hedges"]:
        s += ", " + _nof(a["hedges"], "hedge")
    if a["cancelled"]:
        s += ", %d cancelled" % a["cancelled"]
    L = [s + "."]
    if a.get("note"):
        L.append("  (%s)" % a["note"])
    if a["refused"]:
        grouped = {}
        for k, v in a["refused_why"].items():
            w = _bs().plain(k)
            grouped[w] = grouped.get(w, 0) + v
        top = ", ".join("%s %d" % kv for kv in sorted(grouped.items(), key=lambda kv: -kv[1])[:4])
        L.append("  %s %s: %s." % ("Passed" if name == "pin" else "Refused", _nof(a["refused"], "time"), top))
    for h in a["halts"][-3:]:
        L.append("  %s: %s" % (h["t_et"], halt_words(h["what"], h["why"])))
    return L


def bs_bot_text(b, now_et):
    """One bot, everything botstats knows, for /pin /forecaster /ladder."""
    unit = _unit_of(b["name"])                   # v-tg-rebuild step 5: the registry's Bot.unit (the race: "leg")
    L = ["%s -- %s. %s" % (b["label"].upper(), b["what"], now_et)]
    pot = _pot_words(b)
    if b["shares_subaccount_with"]:
        pot += ", shared with the " + " and ".join(_bs().SPEC[x]["label"].lower() for x in b["shares_subaccount_with"])
    L.append("Pot: %s." % pot)
    L += bs_running_lines(b["running"])
    L += bs_setup_lines(b["running"])
    L.append("")
    L += bs_money_lines(b["money"], unit)
    L.append("")
    L += bs_open_lines(b["open"])
    L.append(bs_cash_line(b["balance"]))
    L += bs_last_lines(b["last_settled"])
    L += bs_activity_lines(b["name"], b["activity_today"])
    return "\n".join(L)


def bs_errors_line(errors):
    """Errors grouped by what failed, each said once: 'settlements read failed (HTTP 401): pin, race'."""
    by = {}
    for e in errors or []:
        who, _, what = str(e).partition(": ")
        by.setdefault(what or who, []).append(who)
    return ["! %s: %s" % (what, ", ".join(sorted(set(who)))) for what, who in sorted(by.items())]


# ---- v-tg-active (2026-10-30): only the ACTIVE bots by name ----------------------------------------------------------
# all_bots carries "active" (botstats.active_from: a live copy running and no stop file; the pin bot always) and
# "earlier" (every hidden bot's past markets as one money block). A page lists the active bots and, where its rows must
# add up to a total, one 'earlier' row; it never names a paused or retired bot. An older botstats (no "active") lists
# every bot as before.
# v-tg-rebuild step 5 (2026-10-30): a pot's words in the cash lines -- all_bots' balance keys: 'main' (subaccount 0), each
# other bot by name (its Bot.pot_word, else its Bot.word), and botstats.shown_cash's one entry for the hidden bots' pots
_POT_WORD = dict([("main", "main account")]
                 + [(b.name, b.pot_word or b.word) for b in _bots.all_bots() if "0" not in _bots.bot_subs(b.name)]
                 + [("earlier bots' pots", "earlier bots' pots")])


def _active_of(a):
    return [b for b in (a.get("active") or _bs().BOTS) if b in a.get("bots", {})]


def _shown_by(a, d, how="sum"):
    bs = _bs()
    return bs.shown_by(a, d, how) if hasattr(bs, "shown_by") else dict(d or {})


def _shown_name(a, name):
    bs = _bs()
    return bs.shown_name(a, name) if hasattr(bs, "shown_name") else name


def _shown_parts(a):
    """[(key, money block)]: the active bots, 'earlier' when it has a market, then 'other' (botstats.shown_parts)."""
    bs = _bs()
    if hasattr(bs, "shown_parts"):
        return bs.shown_parts(a)
    return [(b, a["bots"][b]["money"]) for b in bs.BOTS] + [("other", a["other"])]


def shown_cash(a):
    """[(pot key, dollars)]: one a pot whose bot runs, the rest on one 'earlier bots' pots' entry (botstats.shown_cash)."""
    bs = _bs()
    if hasattr(bs, "shown_cash"):
        return bs.shown_cash(a)
    bal = a["balances"]
    return [(k, bal.get(k)) for k in ("main", "forecaster", "ladder", "weather", "fx")]


def _shown_errors(a):
    """all_bots' error lines with a hidden bot's name said as 'earlier'."""
    out = []
    for e in a.get("errors") or []:
        who, sep, what = str(e).partition(": ")
        out.append((_shown_name(a, who) + sep + what) if sep else e)
    return sorted(set(out))


def earlier_lines(a):
    """One line for every hidden bot's past money (all_bots' 'earlier'), or [] when there is none: 'EARLIER BOTS
    (paused or stopped, not listed): today $0.00, 7 days +$1.20, all time -$41.02 on 412 markets.'"""
    e = a.get("earlier")
    if not e or not a.get("hidden"):
        return []
    if not e.get("ok"):
        return ["EARLIER BOTS (paused or stopped, not listed): money COULD NOT READ KALSHI."]
    at = e.get("all_time") or {}
    if not at.get("markets"):
        return []
    fmt = _bs().usd
    return ["EARLIER BOTS (paused or stopped, not listed): today %s, 7 days %s, all time %s on %s -- in every total "
            "above." % (_short(e["today"], fmt), _short(e["last_7_days"], fmt), fmt(at["money"]),
                        _nof(at["markets"], "market"))]


def bs_all_text(a):
    """/bots: the ALL-BOTS total with each bot's share, every pot's cash, and one line a bot."""
    bs = _bs()
    fmt = bs.usd
    L = ["ALL BOTS -- %s" % a["as_of_et"],
         "Money from Kalshi, every pot; a market counts on the ET day it closed.",
         "The %% after '=' or in brackets = share of the pot when the window began (its cash + open bets%s). All "
         "time = share of the money put in." % (("; %s share the main account" % main_shared(_active_of(a), " and "))
                                                if main_sharers(_active_of(a)) else "")]
    anything = False
    for k in BS_WINDOWS:
        t = a["total"][k]
        label = t["label"] if t["label"] != k else BS_LABEL[k]   # botstats labels an unread window by its key
        if t["partial"] and not t["markets"]:
            L.append("%s: unknown -- Kalshi could not be read" % label)          # never "nothing settled"
            continue
        L.append(bs_window_line(t, label, "market", fmt, "all pots"))
        if t["markets"]:
            anything = True
            # v-tg-active: the active bots by name, every hidden bot's money on ONE 'earlier' entry (botstats.shown_by)
            pp, bm = _shown_by(a, t.get("by_bot_pot_pct") or {}, "none"), _shown_by(a, t["by_bot_markets"])
            L.append("  " + " | ".join(
                "%s %s" % (b, (fmt(v) + ((" (%s)" % bs.pot_pct_txt(pp[b])) if pp.get(b) is not None else ""))
                           if bm.get(b) else "none")
                for b, v in _shown_by(a, t["by_bot"]).items() if b not in ("other", "earlier") or bm.get(b)))
    miss = [_shown_name(a, x) for x in a["total"]["all_time"]["missing"]]
    miss = sorted(set(miss), key=miss.index)
    if miss:
        L.append("PARTIAL: these totals leave out %s -- Kalshi could not be read for %s."
                 % (", ".join(miss), "it" if len(miss) == 1 else "them"))
    firsts = [m.get("first_day") for m in [a["bots"][b]["money"] for b in bs.BOTS] + [a["other"]]
              if m.get("first_day")]
    if anything:
        L.append("By day:")
        for d in a["total_days_7"]:
            if firsts and d["day"] < min(firsts):
                continue                                # before anything ever settled
            parts = ", ".join("%s %s" % (b, fmt(v)) for b, v in _shown_by(a, d["by_bot"]).items() if abs(v) > 0.004)
            L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                                   "%s, %s%s" % (fmt(d["money"]), _nof(d["markets"], "market"),
                                                 (" (%s)" % parts) if parts else "")))
    elif not miss:
        L.append("Nothing settled yet in any pot.")
    bal = a["balances"]
    sc = shown_cash(a)
    L.append("Cash: %s -- all pots %s." % (", ".join("%s %s" % (_POT_WORD.get(k, k), _cash(v)) for k, v in sc),
                                          _cash(bal["all"])))
    L.append("The main page (/today /days /stats, the desktop) counts the main account only (%s). Every other pot is "
             "separate, added up only here." % main_words(a.get("active")))
    # 2026-10-01: the operator saw about -$119 in Kalshi's app while every bot was up. Kalshi's apps do not
    # support subaccounts (API-only, docs.kalshi.com/getting_started/subaccounts), so the cash moved from the
    # main account into the two bot pots shows there as money gone.
    rest = [v for k, v in sc if k != "main"]
    if rest and all(v is not None for v in rest):
        L.append("Kalshi's own app shows the MAIN account only. The %s sitting in the other pots was moved out of it, "
                 "so Kalshi's screens read that much lower than all pots -- not a loss." % _cash(sum(rest)))
    L.append("")
    for name in _active_of(a):
        b = a["bots"][name]
        r, m, o = b["running"], b["money"], b["open"]
        if r["alive"] is None:
            run = "running? could not tell"
        elif r["alive"]:
            run = "running since %s" % (r["started_et"] or "?")
        elif r["stop_flag"]:
            run = "STOPPED by its stop file (%s)" % (r["stop_flag_et"] or "?")
        else:
            run = "NOT RUNNING and no stop file -- it stopped on its own"
        if r["halted"]:
            run += ", HALTED %s" % r["halted"]["t_et"]
        mon = ("money: COULD NOT READ KALSHI" if not m["ok"] else
               "today %s, 7 days %s, all time %s" % (_short(m["today"], fmt), _short(m["last_7_days"], fmt),
                                                    _short(m["all_time"], fmt)))
        op = ("open: ?" if not o["ok"] else "open: none" if not o["count"] else
              "open: %d (%s at risk)" % (o["count"], _cash(o["at_risk"])))
        L.append("%s (%s): %s. %s. %s; %s. %s" % (
            b["label"].upper(), _pot_words(b), run,
            r["version"] or "no version entry", mon, op, BOT_CMD_OF[name]))
    ot = a["other"]
    if ot.get("ok") and ot.get("all_time") and ot["all_time"]["markets"]:
        w = ot["all_time"]
        L.append("NOT ANY BOT'S (main account): all time %s on %s; worst %s %s (%s)." % (
            fmt(w["money"]), _nof(w["markets"], "market"), fmt(w["worst"]["money"]), w["worst"]["what"],
            bs.day_label(w["worst"]["day"])))
    L += earlier_lines(a)
    L += bs_errors_line(_shown_errors(a))
    L += bs.pot_check_lines(a.get("pot_check"))     # a pot Kalshi's own books do not explain
    if all(a["total"][k].get("pot_pct") is None for k in BS_WINDOWS if a["total"][k]["markets"]) \
            and any(a["total"][k]["markets"] for k in BS_WINDOWS):
        why = next((a["total"][k].get("pot_why") for k in BS_WINDOWS if a["total"][k].get("pot_why")), None)
        if why:
            L.append("%% of the pots: not shown -- %s." % why)
    return "\n".join(L)


# ---- the same pages, laid out for a phone (2026-10-18) ------------------------------------------------
# The words above stay the authority: the tables are drawn from the same dicts, and the long sentences
# are quoted whole in each page's tap-to-open details.
BS_SHORT = {"today": "Today", "yesterday": "Yest", "last_7_days": "7 days", "all_time": "All"}


def _wlabel(k, w):
    if k == "this_month":                         # botstats labels it with the month's name
        return str((w or {}).get("label") or "Month")[:3]
    return BS_SHORT[k]


# 2026-10-26, the operator: "/bots should change the color of the emoji for each type of bot, like a green emoji for a
# negative bank makes no sense". A red or green dot means MONEY, never the running state: a bot's headline dot is the sign
# of its money today, and whether it runs is said in words beside it -- loud when it does not.
def money_dot(m, key="today"):
    """A bot's headline colour from a botstats money block: the sign of its money in window `key` (dot) -- 🟢 up,
    🔴 down, ⚪ nothing settled or flat, ❔ Kalshi could not be read."""
    w = m.get(key) if m and m.get("ok") else None
    if w is None:
        return "❔"
    return dot(w["money"]) if w.get("markets") else "⚪"


def run_words(r):
    """Whether a bot runs, in words (Html), for the line under its name: 'running since Oct 23 9:45 PM ET' when all is
    well; loud when not -- '⚠️ NOT RUNNING ...', '🛑 HALTED ...', '⏸ STOPPED by its stop file ...'."""
    if r.get("alive") is None:
        return "❔ <b>running? could not tell</b> (the process list could not be read)"
    if r.get("alive"):
        since = esc(r.get("started_et") or "?")
        if r.get("halted"):
            return "🛑 <b>HALTED %s</b> -- no new bets (running since %s)" % (esc(r["halted"].get("t_et") or "?"), since)
        return "running since %s%s" % (since, " · ⏸ its stop file is set: it stops at its next check"
                                       if r.get("stop_flag") else "")
    if r.get("stop_flag"):
        return "⏸ <b>STOPPED</b> by its stop file (%s)" % esc(r.get("stop_flag_et") or "?")
    return "⚠️ <b>NOT RUNNING</b>%s -- no stop file, it stopped on its own" % (
        (" since about %s (its log's last write)" % esc(r["log_last_et"])) if r.get("log_last_et") else "")


def state_icon(r):
    """The running state as an icon that is not a money colour: ▶️ running, 🛑 halted, ⏸ stopped, ⚠️ not running,
    ❔ could not tell."""
    if r.get("alive") is None:
        return "❔"
    if r.get("alive"):
        return "🛑" if r.get("halted") else "▶️"
    return "⏸" if r.get("stop_flag") else "⚠️"


def bs_running_html(r):
    """bs_running_lines for a phone: the same words, a bot that is not running (or halted, or not known) said loud --
    its headline's dot is its money, not its state (2026-10-26)."""
    out = []
    for x in bs_running_lines(r):
        e = esc(norm_money(x))
        if x.startswith(("Running: NO", "Running: COULD NOT TELL")):
            e = "%s <b>%s</b>" % (state_icon(r), e)
        elif x.startswith("HALTED "):
            e = "🛑 <b>%s</b>" % e
        out.append(e)
    return out


# BOT_WORD (which bot a trade is, in words) is near the top: /help is built at import and names bots with it.


def main_words(active=None):
    """The main account's bots in words: 'pin bot + coin race' while the race is active, else 'pin bot' (v-tg-active).
    The main account's own books (/status, /today's tap, /days' tap) still carry every market it ever settled.
    v-tg-rebuild step 5: the words of main_sharers (the registry's bots in subaccount 0)."""
    return " + ".join(BOT_WORD[x] for x in (main_sharers(active) or [DESK_BOT]))


def main_bot_of(tk):
    """Which bot a MAIN-ACCOUNT market is: 'pin', 'race' or 'other' (botstats.owner, the /bots split; pinday's book when
    botstats cannot be imported -- each bot's Bot.ledger_book)."""
    try:
        return _bs().owner(tk, "0")
    except Exception:                                           # noqa: BLE001
        return {b.ledger_book: b.name for b in _bots.all_bots() if b.ledger_book}.get(pinday.book_of(tk), "other")


def _mkt_short(tk):
    """A market's short name without its clock: 'BTC', 'BTC hourly', 'SOL' (a coin-race leg), 'EURUSD', 'GOLD'."""
    t = str(tk or "")
    if t.startswith("KXCRYPTO"):
        return t.rsplit("-", 1)[-1]
    m = re.match(r"^KX([A-Z]+?)D-", t)
    if m:
        return "%s hourly" % m.group(1)
    return coin(t) if t else ""


def buys_words(name, fills):
    """What one bot bought on one quarter-hour's markets (botstats.fill_of dicts), short enough for a phone line:
    'coin race 2 (SOL YES)', 'forecaster 26 (ETH YES) + 2 (BTC YES)', 'FX taker 3 markets x10', 'ladder 3 markets, 288
    contracts'."""
    by = {}
    for f in fills:
        k = " ".join(x for x in (_mkt_short(f.get("ticker")), str(f.get("side") or "").upper()) if x)
        by[k] = by.get(k, 0.0) + _f(f.get("contracts"))
    who = BOT_WORD.get(name, name)
    items = sorted(by.items(), key=lambda kv: -kv[1])
    if len(items) <= 2:
        return "%s %s" % (who, " + ".join("%s%s" % (_cnt(n), (" (%s)" % k) if k else "") for k, n in items))
    if len({round(n, 2) for _k, n in items}) == 1:
        return "%s %d markets x%s" % (who, len(items), _cnt(items[0][1]))
    return "%s %d markets, %s contracts" % (who, len(items), _cnt(sum(n for _k, n in items)))


def bs_money_table(windows, whose="of bank"):
    """{window key: botstats window} -> (table lines, the base of a money-put-in share or None).
    Money, its return on what the bets cost, and its share of the pot when the window began (the same
    numbers bs_window_line words); '-' where the pot is unknown, never a guessed base."""
    bs = _bs()
    rows, base = [("", "Money", "Return", whose)], None
    for k in BS_WINDOWS:
        w = windows.get(k)
        lab = _wlabel(k, w)
        if w is None or (w.get("partial") and not w["markets"]):
            rows.append((lab, "unknown -- Kalshi unread"))
            continue
        if not w["markets"]:
            rows.append((lab, "nothing settled yet"))
            continue
        p = w.get("pot_pct")
        if p is None or w.get("pot") is None:
            pt = "-"
        else:
            pt = bs.pot_pct_txt(p)
            if w.get("pot_kind") == "money_in":
                pt += "*"
                base = w["pot"]
        rows.append((lab, usd(w["money"]), bs.pct(w["return_pct"]), pt))
    return table(rows), base


def money_legend(base, whose="its bank"):
    return i_("Return = on what the bets cost · of bank = of what %s held when the window began%s"
              % (whose, ("; * all time = of the %s put in" % dollars(base)) if base else ""))


def bs_days_table(days, unit="market"):
    """botstats' days_7 rows -> a small table with a text bar a day (light shade = a losing day)."""
    mx = max([abs(d["money"]) for d in days if d.get("markets")] or [0])
    bs = _bs()
    rows = [("Day", "Money", "Return", "of bank", "Legs" if unit == "leg" else "Mkts", "Lost", "")]
    for d in days:
        if not d.get("markets"):
            rows.append((d["label"], "nothing settled"))
            continue
        rp = d.get("return_pct")
        r = bs.pct(rp) if rp is not None else (ret(d["money"], d.get("put_in")) or "-")
        pp = d.get("pot_pct")
        rows.append((d["label"], usd(d["money"]), r, bs.pot_pct_txt(pp) if pp is not None else "-",
                     d["markets"], d.get("lost", ""), hbar(d["money"], mx, 5)))
    return table(rows, "lrrrrrl")


def _money_detail(m, unit):
    """bs_money_lines' sentences without its header, its warnings (shown above the table) and its by-day
    list (the table): every window in words, the pot note, worst and best, fees, hedged."""
    L = [x for x in bs_money_lines(m, unit, usd)[1:]
         if not x.startswith(("HISTORY STILL LOADING", "The last Kalshi read failed"))]
    return L[:L.index("By day:")] if "By day:" in L else L


def bs_money_html(m, unit="market", goal=None):
    """One bot's money block: where it comes from, the windows table, the average day as a % of its bank
    (with the goal, for the ladder), the 7-day table."""
    if not m["ok"]:
        return elines(bs_money_lines(m, unit, usd))           # the COULD NOT READ line, said once
    L = ["💰 <b>Money</b> <i>(%s, read %s; a %s counts on the ET day it closed)</i>"
         % (esc(m["source"]), esc(m["as_of_et"] or "?"), esc(unit))]
    if not m["complete"]:
        L.append("⚠️ HISTORY STILL LOADING: all time and this month are partial.")
    if m["stale"]:
        L.append("⚠️ The last Kalshi read failed (%s); these are from %s." % (esc(m["error"]), esc(m["as_of_et"] or "?")))
    tbl, base = bs_money_table({k: m[k] for k in BS_WINDOWS})
    L.append(pre(tbl))
    L.append(money_legend(base))
    asof = _bs().pot_as_of_note([m[k] for k in BS_WINDOWS]) if hasattr(_bs(), "pot_as_of_note") else None
    if asof:
        L.append(i_("ℹ️ " + asof))
    avg = bs_avg_day_line(m, goal)
    if avg:
        L.append(avg)
    avg30 = bs_avg30_line(m, goal)
    if avg30:
        L.append(avg30)
    if not any(m[k] and m[k]["pot_pct"] is not None for k in BS_WINDOWS if m[k] and m[k]["markets"]):
        note = _bs()._pot_note(m)
        if note:
            L.append(i_(note))
    d7 = [d for d in m["days_7"] if not d["before_first"]]
    if d7 and m["all_time"] and m["all_time"]["markets"]:
        L.append("")
        L.append("📅 <b>Last 7 days</b>")
        L.append(pre(bs_days_table(d7, unit)))
    return L


# operator 10-22: the ladder's target is 1% of its bank a day -- shown next to its %. v-tg-rebuild step 5: a bot's goal
# is its Bot.goal_pct (only the ladder has one)
LADDER_GOAL_PCT = _bots.LADDER_GOAL_PCT


def _unit_of(name):
    """What a bot counts its bets in: 'market', or the race's 'leg' (Bot.unit; 'market' for a name no bot has)."""
    b = _bots.get(name)
    return b.unit if b is not None else "market"


def _goal_of(name):
    """A bot's daily goal in % of its bank (Bot.goal_pct), or None."""
    b = _bots.get(name)
    return b.goal_pct if b is not None else None


def bs_avg_day_line(m, goal=None):
    """'📈 Average day, last 6 full days: +1.43% of its bank (goal 1.0%) · 5 of 6 at 1%+' -- each full ET day's money
    as a % of what the bank held THAT day (botstats days_7 pot_pct), averaged; today (still running) is left out.
    None when no full day has a known %. Operator 10-22: 'I can't know how close ladder is to 1%'."""
    ds = [d for d in (m.get("days_7") or [])[1:] if not d.get("before_first") and d.get("pot_pct") is not None]
    if not ds:
        return None
    bs = _bs()
    avg = sum(d["pot_pct"] for d in ds) / len(ds)
    txt = "📈 <b>Average day, last %d full days: %s of its bank</b>" % (len(ds), esc(bs.pot_pct_txt(avg)))
    if goal is not None:
        txt += " (goal %s) · %d of %d days at %s+" % (esc(bs.pot_pct_txt(goal).lstrip("+")),
                                                    sum(d["pot_pct"] >= goal for d in ds), len(ds),
                                                    esc(bs.pot_pct_txt(goal).lstrip("+")))
    return txt


def bs_avg30_line(m, goal=None):
    """'📈 Average day, last 30 full days: +2.1% of its bank (+$27.40 a day)' -- the 7-day line's long twin (2026-10-29,
    operator: "can we also add a lifetime or month average whichever is better"): botstats.avg_day over its days_30,
    the 30 FULL ET days before today, each day's money as a % of what the bank held that day. Same day rule as the
    7-day line: days from its first market on count, a quiet (or paused) day as 0; a bot younger than 30 days averages
    every day it has and says so ('since Oct 25, 4 days'). None when no day counts."""
    bs = _bs()
    if not hasattr(bs, "avg_day"):
        return None
    a = bs.avg_day(m.get("days_30"))
    if a is None:
        return None
    pc = a["pot_pct"]
    txt = "📈 <b>Average day, %s: %s</b>" % (
        esc(bs.avg_words(a)), esc("%s of its bank" % bs.pot_pct_txt(pc)) if pc is not None else "% of its bank unknown")
    txt += " (%s a day)" % esc(usd(a["money"]))
    if pc is not None and a["pct_days"] < a["days"]:
        txt += " · %% over the %d days its bank is known" % a["pct_days"]
    if goal is not None and pc is not None:
        ds = [d for d in m["days_30"] if not d.get("before_first") and d.get("pot_pct") is not None]
        txt += " · %d of %d days at %s+" % (sum(d["pot_pct"] >= goal for d in ds), len(ds),
                                           esc(bs.pot_pct_txt(goal).lstrip("+")))
    return txt


def bots_avg_table(a):
    """/days and /bots: the average FULL day of the last 30 (botstats.avg_day over each bot's days_30 and over
    total_days_30 for ALL), bot by bot: $ a day and the mean of its days' % of its own pot (ALL: of every pot). A bot
    younger than 30 days averages every day it has and is starred. A stopped bot with nothing settled in the 30 days,
    and 'other' without a market in them, are left out. Html lines; [] when no day counts."""
    bs = _bs()
    if not hasattr(bs, "avg_day") or not a.get("total_days_30"):
        return []
    rows, young = [("Bot", "a day", "of bank", "Days")], []

    def cells(name, x):
        if x["young"]:
            young.append("%s since %s" % (name, bs.day_label(x["first"])))
        return (name, usd(x["money"]), bs.pot_pct_txt(x["pot_pct"]) if x["pot_pct"] is not None else "-",
                "%d%s" % (x["days"], "*" if x["young"] else ""))
    for nm, m in _shown_parts(a):                     # v-tg-active: the active bots, 'earlier', 'other'
        if not m.get("ok"):
            continue
        busy = any(d["markets"] for d in m.get("days_30") or [])
        if not busy and (nm in ("other", "earlier") or _bot_parked(a["bots"].get(nm))):
            continue
        x = bs.avg_day(m.get("days_30"))
        if x is not None:
            rows.append(cells(nm, x))
    t = bs.avg_day(a["total_days_30"])
    if t is None or len(rows) < 2:
        return []
    rows.append(cells("ALL", t))
    return ["", "📈 <b>Average day, %s</b>" % esc(bs.avg_words(dict(t, young=False))), pre(table(rows, "lrrr")),
            i_("a day = its money on an average full ET day (today left out; a day with nothing settled counts $0) · "
               "of bank = the average of each day's share of its pot that day (ALL = every pot) · Days = days counted"
               + ("; * every day it has: %s" % ", ".join(young) if young else ""))]


def bs_headline(w, whose="of its bank", who="", goal=None, when="today"):
    """'🟢 Pin bot today +$5.31 (+2.6% on $202.56 staked · +0.40% of its bank)' -- bs_window_line's own
    figures; nothing settled and unread are said. `when` names the window ('yesterday', 'last 7 days')."""
    bs = _bs()
    lab = ("%s %s" % (who, when)) if who else when[:1].upper() + when[1:]
    if w is None:
        return "❔ <b>%s: COULD NOT READ KALSHI</b>" % esc(lab)
    if not w["markets"]:
        return "⚪ <b>%s: nothing settled yet</b>" % esc(lab)
    share = ""
    if w.get("pot_pct") is not None and w.get("pot") is not None:
        share = " · %s %s" % (bs.pot_pct_txt(w["pot_pct"]), whose)
        if goal is not None:
            share += " (goal %s)" % bs.pot_pct_txt(goal).lstrip("+")
    return "%s <b>%s %s</b> (<b>%s</b> on %s staked%s)" % (
        dot(w["money"]), esc(lab), esc(usd(w["money"])), esc(bs.pct(w["return_pct"])), esc(_cash(w.get("put_in"))),
        esc(share))


def bots_window_table(a, key, span="day"):
    """ONE botstats window (today / yesterday / last_7_days) bot by bot and every pot together: the money, its
    share of that bot's pot when the window began, its return on what the bets cost, and markets lost of those
    settled. Operator 10-26: "/yesterday doesn't look good or show % of bank return ... add the percentage
    anywhere it applied". Html lines (the table, its legend); [] when nothing settled in any pot."""
    bs = _bs()
    tot = a["total"][key]
    if not tot["markets"]:
        return []

    def cells(name, w):
        return (name, usd(w["money"]), bs.pot_pct_txt(w["pot_pct"]) if w.get("pot_pct") is not None else "-",
                bs.pct(w["return_pct"]) if w.get("return_pct") is not None else "-", "%d/%d" % (w["lost"], w["markets"]))
    rows = [("Bot", "Money", "of bank", "Return", "Lost")]
    for nm, m in _shown_parts(a):                     # v-tg-active: the active bots, 'earlier', 'other'
        w = m.get(key) if m.get("ok") else None
        if w and w["markets"]:
            rows.append(cells(nm, w))
    rows.append(cells("ALL", tot))
    return [pre(table(rows, "lrrrr")),
            i_("of bank = share of that bot's pot when the %s began (%sALL = every pot) · Return = on what the bets "
               "cost · Lost = markets lost / settled" % (span, ("%s share the main account; " % main_shared(_active_of(a)))
                                                         if main_sharers(_active_of(a)) else ""))]


def _day_long(day):
    """'2026-10-25' -> 'Sun Oct 25'."""
    try:
        return time.strftime("%a %b %d", time.strptime(day, "%Y-%m-%d")).replace(" 0", " ")
    except (TypeError, ValueError):
        return str(day)


def nice_coin(tk):
    """A market's short name for a person: 'ZEC', 'BTC hourly' (KXBTCD-...), 'coin race' (KXCRYPTOLEAD/COMP)."""
    t = str(tk or "")
    if re.match(r"^KXCRYPTO(LEAD|COMP)", t):
        return "coin race"
    m = re.match(r"^KX([A-Z]+?)D-", t)
    if m:
        return "%s hourly" % m.group(1)
    return coin(t)


def bs_bot_html(b, now_et):
    """One bot for /pin /forecaster /ladder /weather: headline, status, the money table, the last 7 days,
    open bets and cash; every sentence bs_bot_text wrote is in the details."""
    bs = _bs()
    unit = _unit_of(b["name"])                   # v-tg-rebuild step 5: the registry's Bot.unit (the race: "leg")
    r, m = b["running"], b["money"]
    pot = _pot_words(b)
    if b["shares_subaccount_with"]:
        pot += ", shared with the " + " and ".join(bs.SPEC[x]["label"].lower() for x in b["shares_subaccount_with"])
    L = [bs_headline(m["today"] if m["ok"] else None, who=b["label"],
                     goal=_goal_of(b["name"])),
         "%s <b>%s</b> -- %s" % (state_icon(r), esc(b["label"].upper()), esc(b["what"])),
         "<i>%s · Pot: %s.</i>" % (esc(now_et), esc(pot))]
    L.append("")
    L.append("⚙️ <b>Status</b>")
    L += bs_running_html(r)
    setup = bs_setup_lines(r)
    L += elines([x for x in setup if not x.startswith("Settings: ")])
    L.append("")
    L += bs_money_html(m, unit, goal=_goal_of(b["name"]))
    L.append("")
    ol = elines(bs_open_lines(b["open"]))
    L.append("📂 " + ol[0].replace("Open now:", "<b>Open now:</b>", 1))
    L += ol[1:]
    L.append("💵 " + esc(bs_cash_line(b["balance"])).replace("Cash:", "<b>Cash:</b>", 1))
    det = (elines(_money_detail(m, unit)) if m["ok"] else []) + elines([x for x in setup if x.startswith("Settings: ")])
    det += elines(bs_last_lines(b["last_settled"], usd)) + elines(bs_activity_lines(b["name"], b["activity_today"]))
    L.append(details(det, "🔎 Details: every window in words, settings, last settled, today's log"))
    return L


def _short_html(w):
    """_short() with the money in bold."""
    if w is None:
        return "?"
    if not w["markets"]:
        return "nothing yet"
    return "<b>%s</b>%s" % (esc(usd(w["money"])), esc(_roi_tail(w)))


def all_bots_avg_before(a, day, n=7):
    """(mean $ a day over the n ET days BEFORE `day`, days counted) for every bot together, from all_bots()'
    per-bot all_days (Kalshi's books); a day with nothing settled counts $0; days before the first market on any
    pot's books are left out. (None, 0) when there are none."""
    bs = _bs()
    blocks = [a["bots"][b]["money"] for b in bs.BOTS] + [a["other"]]
    firsts = [m.get("first_day") for m in blocks if m.get("first_day")]
    if not firsts:
        return None, 0
    ds = [d for d in (bs.shift_day(day, -k) for k in range(1, n + 1)) if d >= min(firsts)]
    if not ds:
        return None, 0
    tot = sum(x["money"] for m in blocks for x in (m.get("all_days") or []) if x["day"] in ds)
    return tot / len(ds), len(ds)


def _bot_parked(bt):
    """True for a bot stopped by its stop file (not just crashed), with no open bet and nothing settled in the
    last 7 days -- /bots gives it one line instead of a card and a 'none' row (2026-10-23: the weather
    dip-seller, stopped since 10-10, filled three rows with nothing)."""
    if not bt:
        return False
    r, m, o = bt.get("running") or {}, bt.get("money") or {}, bt.get("open") or {}
    return (r.get("alive") is False and bool(r.get("stop_flag")) and o.get("ok") is True and not o.get("count")
            and m.get("ok") is True and not ((m.get("last_7_days") or {}).get("markets")))


def bs_all_html(a):
    """/bots: the all-pots headline and table, 7 days by bot as a chart, one card a bot, the cash, the
    last 7 days; every sentence bs_all_text wrote is in the details."""
    bs = _bs()
    tot = a["total"]
    t = tot["today"]
    if t["partial"] and not t["markets"]:
        L = ["❔ <b>All bots today: unknown -- Kalshi could not be read</b>"]
    else:
        L = [bs_headline(t, "of all pots", "All bots")]
    L.append("<i>🤖 ALL BOTS · %s</i>" % esc(a["as_of_et"]))
    L.append("")
    L.append("💰 <b>Money, every pot</b> <i>(Kalshi; a market counts on the ET day it closed)</i>")
    anything = any(tot[k]["markets"] for k in BS_WINDOWS)
    tbl, base = bs_money_table(tot, "of pots")
    L.append(pre(tbl))
    L.append(money_legend(base, ("all pots (%s share the main account)" % main_shared(_active_of(a), " and "))
                          if main_sharers(_active_of(a)) else "all pots"))
    miss = [_shown_name(a, x) for x in tot["all_time"]["missing"]]
    miss = sorted(set(miss), key=miss.index)
    if miss:
        L.append("⚠️ PARTIAL: these totals leave out %s -- Kalshi could not be read for %s."
                 % (esc(", ".join(miss)), "it" if len(miss) == 1 else "them"))
    asof = bs.pot_as_of_note([tot[k] for k in BS_WINDOWS]) if hasattr(bs, "pot_as_of_note") else None
    if asof:
        L.append(i_("ℹ️ " + asof))
    t7 = tot["last_7_days"]
    if t7["markets"]:
        # a stopped bot with nothing in the week is one line further down, not a 'none' row here
        bm7 = _shown_by(a, t7["by_bot_markets"])       # v-tg-active: hidden bots on one 'earlier' row
        got = [(nm, v) for nm, v in _shown_by(a, t7["by_bot"]).items() if bm7.get(nm)
               or (nm not in ("other", "earlier") and not _bot_parked(a["bots"].get(nm)))]
        mx = max([abs(v) for nm, v in got if bm7.get(nm)] or [0])
        pin_, pp_ = _shown_by(a, t7.get("by_bot_put_in") or {}), _shown_by(a, t7.get("by_bot_pot_pct") or {}, "none")
        rows = [("Bot", "Money", "Return", "of bank", "")]
        for nm, v in got:
            if not bm7.get(nm):
                rows.append((nm, "none"))
                continue
            rows.append((nm, usd(v), ret(v, pin_.get(nm)) or "-",
                         bs.pot_pct_txt(pp_[nm]) if pp_.get(nm) is not None else "-", hbar(v, mx, 10)))
        L.append("")
        L.append("📊 <b>Last 7 days, by bot</b>")
        L.append(pre(table(rows, "lrrrl")))
    L += bots_avg_table(a)
    L.append("")
    parked = []
    for name in _active_of(a):                        # v-tg-active: a paused or retired bot gets no card
        bt = a["bots"][name]
        r, m, o = bt["running"], bt["money"], bt["open"]
        if _bot_parked(bt):                       # stopped by its stop file, nothing open, nothing this week
            at = (m.get("all_time") or {}) if m.get("ok") else {}
            parked.append("⏸ %s: stopped %s%s · %s" % (
                esc(bt["label"].lower()), esc(r["stop_flag_et"] or "?"),
                (" · all time %s" % esc(usd(at["money"]))) if at.get("markets") else "", BOT_CMD_OF[name]))
            continue
        mon = ("money: COULD NOT READ KALSHI" if not m["ok"] else
               "today %s · 7 days %s · all time %s" % (_short_html(m["today"]), _short_html(m["last_7_days"]),
                                                       _short_html(m["all_time"])))
        op = ("open: ?" if not o["ok"] else "open: none" if not o["count"] else
              "open: %d (%s at risk)" % (o["count"], esc(_cash(o["at_risk"]))))
        # 2026-10-26 (operator: "a green emoji for a negative bank makes no sense"): the dot is the bot's money TODAY, the
        # first figure on its money line; whether it runs is said in words on the line under its name, loud when it does not
        L.append("%s <b>%s</b> · %s · %s" % (money_dot(m), esc(bt["label"].upper()),
                                            esc(_pot_words(bt)), BOT_CMD_OF[name]))
        L.append("%s · %s" % (run_words(r), esc(r["version"] or "no version entry")))
        L.append("%s · %s" % (mon, op))
    ot = a["other"]
    if ot.get("ok") and ot.get("all_time") and ot["all_time"]["markets"]:
        w = ot["all_time"]
        L.append("%s NOT ANY BOT'S (main account): all time %s on %s; worst %s %s (%s)." % (
            dot(w["money"]), esc(usd(w["money"])), esc(_nof(w["markets"], "market")), esc(usd(w["worst"]["money"])),
            esc(w["worst"]["what"]), esc(bs.day_label(w["worst"]["day"]))))
    L += parked
    e_ = earlier_lines(a)
    if e_:
        L.append("⏸ " + esc(norm_money(e_[0])))
    bal = a["balances"]
    L.append("")
    L.append("💵 <b>Cash:</b> %s -- all pots <b>%s</b>." % (
        esc(", ".join("%s %s" % (_POT_WORD.get(k, k) + (" (%s)" % main_words(a.get("active")) if k == "main" else ""),
                                 _cash(v)) for k, v in shown_cash(a))), esc(_cash(bal["all"]))))
    firsts = [mm.get("first_day") for mm in [a["bots"][x]["money"] for x in bs.BOTS] + [a["other"]]
              if mm.get("first_day")]
    days = [d for d in a["total_days_7"] if not (firsts and d["day"] < min(firsts))]
    if anything and days:
        mx = max([abs(d["money"]) for d in days if d["markets"]] or [0])
        rows = [("Day", "Money", "of pots", "Return", "Lost", "")]
        for d in days:
            rows.append((d["label"], "nothing settled") if not d["markets"] else
                        (d["label"], usd(d["money"]),
                         bs.pot_pct_txt(d["pot_pct"]) if d.get("pot_pct") is not None else "-",
                         ret(d["money"], d.get("put_in")) or "-", "%d/%d" % (d.get("lost", 0), d["markets"]),
                         hbar(d["money"], mx, 4)))
        L.append("")
        L.append("📅 <b>By day</b> (all pots; of pots = share of all the pots when that day began)")
        L.append(pre(table(rows, "lrrrrl")))
    elif not anything and not miss:
        L.append("Nothing settled yet in any pot.")
    warn = bs_errors_line(_shown_errors(a)) + list(bs.pot_check_lines(a.get("pot_check")))
    if all(tot[k].get("pot_pct") is None for k in BS_WINDOWS if tot[k]["markets"]) \
            and any(tot[k]["markets"] for k in BS_WINDOWS):
        why = next((tot[k].get("pot_why") for k in BS_WINDOWS if tot[k].get("pot_why")), None)
        if why:
            warn.append("%% of the pots: not shown -- %s." % why)
    for x in warn:
        L.append("⚠️ " + esc(norm_money(x[2:] if x.startswith("! ") else x)))
    # the details: bs_all_text's own sentences, whole
    full = bs_all_text(a).split("\n")
    keep, skip = [], True
    for x in full[1:]:
        # v-tg-rebuild step 5: a bot card's line starts with its label (the registry's Bot.label, upper case); "PENNY
        # LADDER" = the ladder's label in an older botstats
        if x.startswith(tuple(bt_.label.upper() for bt_ in _bots.all_bots())
                        + ("PENNY LADDER", "EARLIER BOTS", "NOT ANY BOT'S", "! ", "PARTIAL:", "% of the pots", "Cash: ")):
            continue
        keep.append(x)
    while keep and not keep[-1].strip():
        keep.pop()
    L.append(details(elines(keep), "🔎 Details: each window by bot, each day by bot, what the % mean"))
    L.append("<i>A bot's dot = its money today: 🟢 up, 🔴 down, ⚪ no gain or loss yet, ❔ Kalshi unread; whether it runs "
             "is in words under its name. One bot in full: %s · every account's cash: /funds</i>"
             % " ".join(BOT_CMD_OF.get(b, "/" + b) for b in _active_of(a)))
    return L


# ===========================================================================
# /funds (/bank /accounts) -- every Kalshi account's money on one screen.
#
# THE OPERATOR, 2026-10-11: "Add a way in telegram to see the bankroll or fund sizes of all sub
# accounts." /bots says what each bot MADE; this says what SITS in every account now -- every account
# Kalshi lists, not only the ones a bot is known to use, so a stopped pot (the weather seller, the
# reward test) or a forgotten one is in front of him. What runs where: FUNDS_WHAT at the top.
#
# READ ONLY: three GET paths (FUNDS_PATHS) through `getter(path, params) -> (status, body)` -- by
# default botstats.default_getter(), i.e. kauth.get, which can only send a GET and times out each
# request at 20 s. The whole read also has a limit (FUNDS_DEADLINE_S) so a slow Kalshi cannot stall
# the phone for minutes; a read not made in time is SAID, never shown as $0.
#
# CASH UNITS (hard rule 5). The subaccount list's field is `balance`, a name that does not say its
# unit, so the list is used to FIND the accounts and pools. Each pool's cash is /portfolio/balance's
# `balance_dollars` (the unit is in the name). A listed 0 is $0 in any unit and is not re-read. When a
# direct read fails, the list's figure stands in ONLY if another pool's list figure matched its direct
# dollars read to the cent in the same pass -- the list's unit decided from the sample, never from a
# figure's size; otherwise that cash is COULD NOT READ.
#
# Open bets count at what they COST (market_exposure_dollars), not what they would sell for now.
# Bet sizes come from each bot's own log (no Kalshi read); every dollar on the page is Kalshi's.
# ===========================================================================
FUNDS_PATHS = ("/portfolio/subaccounts/balances", "/portfolio/balance", "/portfolio/positions")   # GET only
FUNDS_DEADLINE_S = 40.0          # the whole /funds read; kauth.get's own limit is 20 s a request
FUNDS_POS_PAGES = 5              # 1,000 open bets an account: a runaway pager stops loudly
FUNDS_FALLBACK_POOLS = (2, 0)    # the subaccount list failed: try FUNDS_WHAT's accounts in these pools


def _fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _fint(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _usd2(x):
    return "$" + "{:,.2f}".format(_f(x))


def _pool_name(ix):
    return FUNDS_POOL_NAME.get(ix, "pool %s" % ix)


def funds_read(getter, clock=time.monotonic, deadline_s=FUNDS_DEADLINE_S):
    """Every account's cash by pool and its open bets, from Kalshi. A failed read is recorded, never
    raised and never a zero:
      {"subs": {n: {"pools": {ix: {"dollars": x|None, "from_list": bool, "err": str|None, "listed": x|None}},
                    "open": dollars|None, "open_n": markets, "open_err": str|None}},
       "list_err": str|None, "kalshi_cash": {ix: x}|None (Kalshi's whole-account cash by pool),
       "asked": [(path, params)]}"""
    t0 = clock()
    asked = []

    def ask(path, q):
        if clock() - t0 > deadline_s:
            return None, "the %d s limit for /funds ran out first" % deadline_s
        asked.append((path, dict(q)))
        try:
            st, d = getter(path, q)
        except Exception as e:                                  # noqa: BLE001
            return None, "error: %s" % str(e)[:80]
        if st != 200 or not isinstance(d, dict):
            return None, "HTTP %s" % st
        return d, None

    out = {"subs": {}, "list_err": None, "kalshi_cash": None, "asked": asked}
    subs = out["subs"]
    listed = {}                                   # (subaccount, pool) -> the list's figure, unit unknown
    d, err = ask("/portfolio/subaccounts/balances", {})
    rows = d.get("subaccount_balances") if d is not None else None
    if err is None and not isinstance(rows, list):
        err = "no 'subaccount_balances' list in Kalshi's reply"
    if err:
        out["list_err"] = err
        for n in sorted(FUNDS_WHAT):
            for ix in FUNDS_FALLBACK_POOLS:
                listed[(n, ix)] = None
    else:
        for r in rows:
            if isinstance(r, dict) and _fint(r.get("subaccount_number")) is not None \
                    and _fint(r.get("exchange_index")) is not None:
                listed[(_fint(r["subaccount_number"]), _fint(r["exchange_index"]))] = _fnum(r.get("balance"))
    for n, ix in sorted(listed):
        s = subs.setdefault(n, {"pools": {}, "open": None, "open_n": 0, "open_err": None})
        p = s["pools"][ix] = {"dollars": None, "from_list": False, "err": None, "listed": listed[(n, ix)]}
        if p["listed"] == 0.0:
            p["dollars"] = 0.0                    # $0 in any unit: nothing to read
            continue
        d, err = ask("/portfolio/balance", {"subaccount": n, "exchange_index": ix})
        if d is not None and out["kalshi_cash"] is None and isinstance(d.get("balance_breakdown"), list):
            kc = {_fint(b.get("exchange_index")): _fnum(b.get("balance")) for b in d["balance_breakdown"]
                  if isinstance(b, dict)}
            if kc and None not in kc and None not in kc.values():
                out["kalshi_cash"] = kc
        bd = _fnum(d.get("balance_dollars")) if d is not None else None
        if bd is None:
            p["err"] = err or "no balance_dollars in Kalshi's reply"
        else:
            p["dollars"] = bd
    # the list's unit, decided once from the whole pass: some pool's list figure equals its dollars read
    unit_ok = any(p["listed"] and p["err"] is None and p["dollars"] is not None
                  and abs(p["listed"] - p["dollars"]) <= 0.011
                  for s in subs.values() for p in s["pools"].values())
    for s in subs.values():
        for p in s["pools"].values():
            if p["dollars"] is None and p["listed"] is not None and unit_ok:
                p["dollars"], p["from_list"] = p["listed"], True
    for n in sorted(subs):
        s = subs[n]
        tot, cnt, cursor, err = 0.0, 0, None, None
        for _ in range(FUNDS_POS_PAGES):
            q = {"subaccount": n, "settlement_status": "unsettled", "count_filter": "position", "limit": 200}
            if cursor:
                q["cursor"] = cursor
            d, err = ask("/portfolio/positions", q)
            got = d.get("market_positions") if d is not None else None
            if err is None and not isinstance(got, list):
                err = "no 'market_positions' list in Kalshi's reply"
            if err:
                break
            for x in got:
                if not isinstance(x, dict) or abs(pinledger.money(x, "position_fp", "position")) < 1e-9:
                    continue
                v = _fnum(x.get("market_exposure_dollars"))
                if v is None:                     # never read `market_exposure` (cents) in its place
                    err = "a bet came without market_exposure_dollars"
                    break
                tot += v
                cnt += 1
            cursor = d.get("cursor")
            if err or not got or not cursor:
                break
        else:
            err = "more than %d pages of open bets; stopped" % FUNDS_POS_PAGES
        if err:
            s["open_err"] = err
        else:
            s["open"], s["open_n"] = tot, cnt
    return out


def funds_sizes(results=RESULTS, active=None):
    """{subaccount: [words]}: each bot's bet size NOW, from its own log -- no Kalshi read. A log with no
    size record leaves that bot out; a log that cannot be read says so. Never a guess. `active` (v-tg-active): only
    those bots (None = every bot). v-tg-rebuild step 5 (2026-10-30): each bot's reader is its Bot.funds_size
    (research/bots/<name>.py, moved there verbatim); spec.SizeIn hands it the results folder, the account and these
    readers."""
    from bots.spec import SizeIn
    bs = _bs()

    def when(r):
        e = bs._epoch((r or {}).get("t"))
        return bs.et_clock(e) if e else "?"

    out = {}
    for n, bots in FUNDS_SIZE_BOTS.items():
        for b in bots:
            if active is not None and b not in active:
                continue                                        # v-tg-active: a paused or retired bot's size is not said
            try:
                # the FX taker: one start, a pot per account (SizeIn.sub)
                w = _bots.get(b).funds_size(SizeIn(results, n, when, bs.last_record, bs._epoch, _fnum, _usd2, read_json))
            except Exception as e:                              # noqa: BLE001
                w = "%s: its log could not be read (%s)" % (b, str(e)[:60])
            if w:
                out.setdefault(n, []).append(w)
    return out


# ---- /funds' PAST DAYS (2026-10-11) ------------------------------------------------------------------
# THE OPERATOR, 2026-10-11: "Make that funds command include some past days for each accounts and their
# gains/losses." Under every account: its last FUNDS_DAYS ET days, newest first -- the day's gain or loss
# in dollars, how many markets settled and how many of them lost -- and the FUNDS_DAYS total, also as a %
# of what the account holds now.
#
# MONEY = KALSHI'S SETTLEMENT RECORDS, NOTHING ELSE. GET /portfolio/settlements naming the subaccount
# (without it Kalshi mixes every subaccount's rows -- pinledger.py, 2026-09-29), paged newest first and
# stopped once a page reaches back past the first day shown: a market settles after it closes, so nothing
# settled earlier can belong to a day shown. Per market = pinledger.pnl (the payout from value/result,
# minus both sides' cost, minus the fee); a market with several rows is ONE market with its rows summed;
# the same row read twice (it can slide across a page edge) counts once (pinledger.key_of). Deposits,
# withdrawals and transfers between accounts are not settlements, are never read here, and so are never a
# gain -- a difference of balances would have counted them.
#
# A market's day is the ET day it CLOSED, read from its ticker (pinday.et_day_of_ticker -- the ticker is
# already Eastern); the settled time, on the ET clock, only for a ticker that carries no date. The main
# account is split so its two bots are separate: "main bot" = the 15-minute coin series (KX...15M, not
# the coin race, not the old commodity series) plus the main bot's hourly coin series (botstats.PIN_HOURLY,
# e.g. KXBTCD -- the same split /pin uses), "race" = the coin race (pinday.RACE: KXCRYPTOLEAD15M and
# KXCRYPTOCOMP15M), "other" = anything else (weather, oil) -- never folded into a bot.
#
# Each account's pull is kept FUNDS_HIST_TTL_S (60 s), so /funds sent twice does not read Kalshi twice. A
# failed or cut-short pull is not kept: the days it did reach are shown and the rest are named NOT READ.
#
# ONE READ, NOT TWO (2026-10-26). The operator: "check if ... you're collecting or doing something with the
# same data multiple times anywhere across the project". botstats' cache already holds every account's
# settlement rows, re-read at most once a minute, and /funds' own picture refreshed it seconds after this page
# had paged the same rows again (7 GETs on the live books, on a key the live bots share and Kalshi rate-limits).
# So the past days come from botstats.pot_settlements (funds_hist); this page's own pull (funds_settled) is
# kept for an account botstats does not hold or whose latest botstats read failed. Same rows, same rules,
# same figures.
# ---------------------------------------------------------------------------------------------------------
FUNDS_DAYS = 7
FUNDS_SHOW_DAYS = (7, 5, 3, 0)          # day lines listed, most first, until the page fits one message
FUNDS_HIST_TTL_S = 60
FUNDS_HIST_PAGES = 60                   # 12,000 settlements in FUNDS_DAYS days, one account: stops loudly
FUNDS_HIST_DEADLINE_S = 15.0            # the whole settlement read, every account; short: loss alerts wait on it
FUNDS_HIST_PATH = "/portfolio/settlements"                    # GET only
FUNDS_BOOKS = (("bot", "main bot"), ("race", "race"), ("other", "other"))


def funds_books(active=None):
    """FUNDS_BOOKS with the coin race's book named 'earlier bots' while the race is not active (v-tg-active)."""
    if active is None or "race" in active:
        return FUNDS_BOOKS
    return tuple((k, "earlier bots" if k == "race" else w) for k, w in FUNDS_BOOKS)
_FUNDS_HIST = {}                        # subaccount -> {"t": clock, "since": epoch, "res": a whole pull}


def funds_book(ticker):
    """Which part of the main account a market is: 'bot', 'race' or 'other'."""
    series = str(ticker or "").split("-")[0].upper()
    if series in pinday.RACE:
        return "race"
    if re.match(r"^KX[A-Z0-9]+15M$", series) and series not in pinday.COMMODITY:
        return "bot"
    if series in _bs().PIN_HOURLY:                      # the main bot's hourly coin bets, as /pin counts them
        return "bot"
    return "other"


def funds_settled(getter, subs, now, clock=time.monotonic, deadline_s=FUNDS_HIST_DEADLINE_S, memo=None,
                  days=FUNDS_DAYS):
    """Each account's settlement rows back to the start of the last `days` ET days, from Kalshi:
    {sub: {"rows": [...], "err": str|None, "oldest": epoch|None, "since": epoch, "cached": bool}}.
    `oldest` is the oldest settled time read; after an error only the days that began after it are whole.
    A pull that finished is kept FUNDS_HIST_TTL_S in `memo` (the module's own by default)."""
    memo = _FUNDS_HIST if memo is None else memo
    bs = _bs()
    since = bs.day_start(bs.shift_day(pinday.et_day_of_epoch(now), -(days - 1)))
    t0 = clock()
    out = {}
    for n in sorted(subs):
        m = memo.get(n)
        if m and m["since"] == since and clock() - m["t"] < FUNDS_HIST_TTL_S:
            out[n] = dict(m["res"], cached=True)
            continue
        rows, cursor, oldest, err = {}, None, None, None
        for _ in range(FUNDS_HIST_PAGES):
            if clock() - t0 > deadline_s:
                err = "the %d s limit for /funds ran out first" % deadline_s
                break
            q = {"limit": 200, "subaccount": n}
            if cursor:
                q["cursor"] = cursor
            try:
                st, d = getter(FUNDS_HIST_PATH, q)
            except Exception as e:                              # noqa: BLE001
                err = "error: %s" % str(e)[:80]
                break
            if st != 200 or not isinstance(d, dict):
                err = "HTTP %s" % st
                break
            got = d.get("settlements", "missing")
            got = [] if got is None else got
            if not isinstance(got, list):       # a renamed field is an error, never "nothing settled"
                err = "no 'settlements' list in Kalshi's reply"
                break
            for s in got:
                if not isinstance(s, dict):
                    continue
                rows.setdefault(pinledger.key_of(s), s)
                e = bs._epoch(s.get("settled_time"))
                if e is not None and (oldest is None or e < oldest):
                    oldest = e
            cursor = d.get("cursor")
            # an hour past the start: day_start of the November clock-change day is 1 AM ET, not midnight
            if not got or not cursor or (oldest is not None and oldest < since - 3600):
                break
        else:
            err = "more than %d pages of settlements in %d days; stopped" % (FUNDS_HIST_PAGES, days)
        res = {"rows": list(rows.values()), "err": err, "oldest": oldest, "since": since, "cached": False}
        if err is None:
            memo[n] = {"t": clock(), "since": since, "res": res}
        out[n] = res
    return out


def funds_hist(getter, subs, now, bs_getter=None, memo=None):
    """funds_settled's answer for accounts `subs`, read once: every account botstats' cache holds whole after its
    usual refresh (botstats.pot_settlements through `bs_getter`, the phone's botstats getter -- the read /bots and
    the /funds picture make anyway) is its rows from there; only the rest are pulled here (funds_settled through
    `getter`). A failing botstats costs nothing but that: every account is pulled as before."""
    bs = _bs()
    try:
        have, _why = bs.pot_settlements(now, bs_getter)
    except Exception:                                           # noqa: BLE001
        log(traceback.format_exc())
        have = {}
    since = bs.day_start(bs.shift_day(pinday.et_day_of_epoch(now), -(FUNDS_DAYS - 1)))
    # the whole history is on file, so every day shown is read (oldest is only consulted after an error)
    out = {n: {"rows": have[str(n)], "err": None, "oldest": None, "since": since, "cached": True}
           for n in subs if str(n) in have}
    rest = [n for n in subs if n not in out]
    if rest:
        out.update(funds_settled(getter, rest, now, memo=memo))
    return out


def funds_days(res, today, days=FUNDS_DAYS, sub=None):
    """One account's pull (funds_settled) -> its last `days` ET days, newest first:
    {"days": [{"day", "read", "all", "bot", "race", "other"}], "total": {"all", "bot", "race", "other"},
     "other_series": the series in "other" on the days read}.
    A cell is {"money": dollars, "n": markets settled, "lost": markets that lost}. A day is "read" when the
    pull reached back past its start; the total is over the days read."""
    bs = _bs()
    keys = ("all",) + tuple(k for k, _w in FUNDS_BOOKS)

    def cells():
        return {k: {"money": 0.0, "n": 0, "lost": 0} for k in keys}
    want = [bs.shift_day(today, -k) for k in range(days)]
    mk = {}                                 # ticker -> [day, book, money]: several rows, one market
    left = {"money": 0.0, "n": 0, "tk": set()}
    for s in res.get("rows") or []:
        tk = s.get("ticker")
        if not isinstance(tk, str) or not tk:
            continue                        # not a market: a transfer or anything else is never a gain here
        if sub is not None and str(sub) in getattr(bs, "POT_POOL_ONLY", {}) and bs.owner(tk, str(sub)) == "other":
            # 2026-10-26: the number 4 also names the old coin-race reward test's pool-2 pot; its legs are not the
            # FX pairs' (the summary showed 'fx pairs -15.91 (-25.8%)' from that test's 10-19..10-23 losses)
            d_ = pinday.et_day_of_ticker(tk)
            if d_ in set(bs.shift_day(today, -k) for k in range(days)):
                left["money"] += pinledger.pnl(s)
                left["tk"].add(tk)
            continue
        if tk not in mk:
            d = pinday.et_day_of_ticker(tk)
            if d is None:
                e = bs._epoch(s.get("settled_time"))
                d = pinday.et_day_of_epoch(e) if e is not None else None
            mk[tk] = [d, funds_book(tk), 0.0]
        mk[tk][2] += pinledger.pnl(s)
    by = {d: cells() for d in want}
    for d, book, v in mk.values():
        if d in by:
            for k in ("all", book):
                c = by[d][k]
                c["money"] += v
                c["n"] += 1
                c["lost"] += 1 if v < -0.004 else 0
    err, oldest = res.get("err"), res.get("oldest")
    out = {"days": [], "total": cells()}
    for d in want:
        read = err is None or (oldest is not None and bs.day_start(d) > oldest)
        out["days"].append(dict(by[d], day=d, read=read))
        if read:
            for k in keys:
                for f_ in ("money", "n", "lost"):
                    out["total"][k][f_] += by[d][k][f_]
    read_days = set(x["day"] for x in out["days"] if x["read"])
    out["other_series"] = sorted(set(tk.split("-")[0] for tk, (d, book, _v) in mk.items()
                                     if book == "other" and d in read_days))
    out["left_out"] = {"money": round(left["money"], 4), "n": len(left["tk"])}
    return out


def _funds_hist_lines(n, res, today, show, held, active=None):
    """The past-days lines under one account. `show` = how many day lines to list (the total always
    counts all FUNDS_DAYS); `held` = what the account holds now, or None when that was not read whole."""
    bs = _bs()
    if res is None:
        return ["  past %d ET days: not read" % FUNDS_DAYS]
    h = funds_days(res, today, sub=n)
    unread = [x["day"] for x in h["days"] if not x["read"]]
    if len(unread) == FUNDS_DAYS:
        return ["  past %d ET days: COULD NOT READ (%s)" % (FUNDS_DAYS, res.get("err"))]

    def cw(c, extra=""):
        return "%s (%d of %d lost%s)" % (bs.usd(c["money"]), c["lost"], c["n"], extra)

    def money_w(x, other_names=""):
        if n != 0 or not x["all"]["n"]:
            return cw(x["all"])
        return "%s = %s" % (bs.usd(x["all"]["money"]), " + ".join(
            "%s %s" % (w, cw(x[k], other_names if k == "other" else "")) for k, w in funds_books(active) if x[k]["n"]))

    def label(d):
        return "%s %s%s" % (time.strftime("%a", time.strptime(d, "%Y-%m-%d")), bs.day_label(d),
                            " so far" if d == today else "")
    tot = h["total"]
    if not tot["all"]["n"] and not unread:
        return ["  past %d ET days: nothing settled" % FUNDS_DAYS]
    L = ["  past %d ET days%s:" % (
        FUNDS_DAYS, "" if show >= FUNDS_DAYS else
        (" -- day lines left out to fit one message" if show <= 0 else
         " -- the newest %d listed to fit one message; the total counts all %d" % (show, FUNDS_DAYS)))]
    shown, i = h["days"][:max(show, 0)], 0
    while i < len(shown):                   # a run of empty (or unread) days is one line
        x = shown[i]
        what = ("NOT READ" if not x["read"] else "nothing settled") if not (x["read"] and x["all"]["n"]) else None
        if what is None:
            L.append("  %s: %s" % (label(x["day"]), money_w(x)))
            i += 1
            continue
        j = i
        while j + 1 < len(shown) and not (shown[j + 1]["read"] and shown[j + 1]["all"]["n"]) \
                and shown[j + 1]["read"] == x["read"]:
            j += 1
        L.append("  %s%s: %s" % (label(shown[j]["day"]) + " to " if j > i else "", label(x["day"]), what))
        i = j + 1
    if held is None:
        share = "% not shown: what it holds now was not read whole"
    elif held < 1.0:
        share = "% not shown: it holds under $1"
    else:
        share = "%s of the %s it holds now" % (bs.pot_pct_txt(100.0 * tot["all"]["money"] / held), _usd2(held))
    names = ", ".join(("%s hourly" % o[2:-1]) if o in bs.PIN_HOURLY else o for o in h["other_series"])
    L.append("  %s: %s; %s" % ("%d days" % FUNDS_DAYS if not unread else
                               "the %d days read" % (FUNDS_DAYS - len(unread)),
                               money_w(tot, ("; " + names) if names else ""), share))
    if unread:
        L.append("  NOT READ: %s (%s)" % (", ".join(label(d) for d in unread), res.get("err")))
    return L


def funds_text(f, sizes, now, hist=None, active=None):
    """/funds' words from funds_read() and funds_sizes(). Anything unread is named, and a total that
    leaves something out says 'at least' and what. With `hist` (funds_settled), every account also
    carries its last FUNDS_DAYS ET days; the day lines shrink through FUNDS_SHOW_DAYS until the page fits
    one Telegram message (MAX_LEN), and say so."""
    if hist is None:
        return _funds_page(f, sizes, now, None, 0, active)
    for show in FUNDS_SHOW_DAYS:
        t = _funds_page(f, sizes, now, hist, show, active)
        if len(t) <= MAX_LEN:
            break
    return t


# /funds on a phone (2026-10-18): a short name an account goes by in the summary table: its pots' Pot.short, joined
# with '+' (v-tg-rebuild step 5: from the registry); an account not here shows its FUNDS_WHAT words, cut short.
FUNDS_SHORT = _bots.FUNDS_SHORT


def funds_short(n, active=None):
    """FUNDS_SHORT's name for account n -- 'idle' when nothing active runs there, 'main' for the main account while the
    coin race is not active (v-tg-active; None = the whole roster). v-tg-rebuild step 5: the Pot.short of the active
    bots' pots there (an always-shown bot's always), joined with '+'; with none, the active bots' pot words (subaccount 3
    with only the weather dip-seller: 'weather')."""
    if active is None or n not in FUNDS_SHORT:
        return FUNDS_SHORT.get(n)
    if funds_idle(n, active):
        return "idle"
    sub = str(n)
    on = [(b, p) for b in _bots.bots_on(sub) for p in b.pots if p.sub == sub and (b.always_shown or b.name in active)]
    shorts = [p.short for _b, p in on if p.short]
    return "+".join(shorts) if shorts else ("+".join(b.pot_word or b.word for b, _p in on) or FUNDS_SHORT[n])


def funds_idle(n, active=None):
    """True when every pool of account n is marked stopped or empty in FUNDS_WHAT: money there runs
    nothing. (The operator, 2026-10-18: 'dead sitting money'.) Unknown accounts are not called idle.
    v-tg-active: with `active`, a pool whose bots are all hidden is stopped too (funds_what)."""
    what = funds_what(n, active)
    if what is None:
        return False
    vals = list(what.values()) if isinstance(what, dict) else [what]
    return all("(stopped)" in str(v) or str(v).strip() == "empty" for v in vals)


def _funds_day_label(d, today):
    return "%s %d%s" % (time.strftime("%a", time.strptime(d, "%Y-%m-%d")), int(d[8:]), "*" if d == today else "")


def _funds_days_html(n, res, today, show, held, active=None):
    """One account's past days as a table (money and how many of the markets settled lost), its total and
    that total's share of what it holds now -- the figures _funds_hist_lines words, from funds_days. For
    the main account the main bot / race / other split follows, its day-by-day lines behind a tap."""
    bs = _bs()
    if res is None:
        return ["<i>past %d ET days: not read</i>" % FUNDS_DAYS]
    h = funds_days(res, today, sub=n)
    unread = [x["day"] for x in h["days"] if not x["read"]]
    if len(unread) == FUNDS_DAYS:
        return ["past %d ET days: COULD NOT READ (%s)" % (FUNDS_DAYS, esc(res.get("err")))]
    tot = h["total"]
    lo = h.get("left_out") or {}
    lo_line = (i_("left out: %s of the old coin-race test in this subaccount's crypto pool (%s) -- not the FX pairs'"
                  % (_nof(lo["n"], "market"), usd(lo["money"]))) if lo.get("n") else None)
    if not tot["all"]["n"] and not unread:
        return ["<i>past %d ET days: nothing settled</i>" % FUNDS_DAYS] + ([lo_line] if lo_line else [])
    head = "Past %d ET days" % FUNDS_DAYS
    rows = [(head, "Money", "Lost")]
    shown, i = h["days"][:max(show, 0)], 0
    while i < len(shown):                   # a run of empty (or unread) days is one row
        x = shown[i]
        if x["read"] and x["all"]["n"]:
            rows.append((_funds_day_label(x["day"], today), usd(x["all"]["money"]),
                         "%d/%d" % (x["all"]["lost"], x["all"]["n"])))
            i += 1
            continue
        j = i
        while j + 1 < len(shown) and not (shown[j + 1]["read"] and shown[j + 1]["all"]["n"]) \
                and shown[j + 1]["read"] == x["read"]:
            j += 1
        lab = _funds_day_label(x["day"], today)
        if j > i:
            lab = _funds_day_label(shown[j]["day"], today) + "-" + lab
        rows.append((lab, "NOT READ" if not x["read"] else "nothing settled"))
        i = j + 1
    span = "%d days" % FUNDS_DAYS if not unread else "%d days read" % (FUNDS_DAYS - len(unread))
    L = []
    if len(rows) > 1:                       # no day rows when the page had to leave them out to fit
        L.append(pre(table(rows)))
    total = "%s: <b>%s</b> (%d of %d lost)" % (esc(span), esc(usd(tot["all"]["money"])), tot["all"]["lost"],
                                               tot["all"]["n"])
    if held is None:
        L.append("%s; %% not shown: what it holds now was not read whole" % total)
    elif held < 1.0:
        L.append("%s; %% not shown: it holds under $1" % total)
    else:
        L.append("%s = <b>%s</b> of the %s it holds now" % (
            total, esc(bs.pot_pct_txt(100.0 * tot["all"]["money"] / held)), esc(_usd2(held))))
    if n == 0 and tot["all"]["n"]:
        names = ", ".join(("%s hourly" % o[2:-1]) if o in bs.PIN_HOURLY else o for o in h["other_series"])
        L.append("Split: " + " · ".join(
            "%s <b>%s</b> (%d of %d lost%s)" % (esc(w), esc(usd(tot[k]["money"])), tot[k]["lost"], tot[k]["n"],
                                                esc("; " + names) if k == "other" and names else "")
            for k, w in funds_books(active) if tot[k]["n"]))
        # the day lines only: the total, its % and the NOT READ list are said above
        L.append(details(elines([x.strip() for x in _funds_hist_lines(n, res, today, show, held, active)[1:]
                                 if not x.strip().startswith(("NOT READ", "7 days:", "the "))]),
                         "Each day, %s" % " / ".join(w for _k, w in funds_books(active))))
    if lo_line:
        L.append(lo_line)
    if unread:
        L.append("⚠️ NOT READ: %s (%s)" % (esc(", ".join(_funds_day_label(d, "") for d in unread)),
                                           esc(res.get("err"))))
    return L


def _funds_page(f, sizes, now, hist, show, active=None):
    """/funds as Html: the grand total first, a one-line-an-account table, idle money named, then each
    account -- the same figures and the same 'at least' / COULD NOT READ rules as always."""
    today = pinday.et_day_of_epoch(now)
    cash_t = open_t = 0.0
    missing = []
    pool_t = {}                                   # pool -> cash over every account; None once one is unread
    accts = []
    for n in sorted(f["subs"]):
        s = f["subs"][n]
        what = funds_what(n, active)
        if what is None:
            what = "unknown (not in FUNDS_WHAT in pinphone.py)"
        if isinstance(what, dict):
            what = "; ".join("%s: %s" % (_pool_name(ix), w) for ix, w in sorted(what.items()))
        name = "MAIN ACCOUNT (0)" if n == 0 else "SUBACCOUNT %d" % n
        who = "main account" if n == 0 else "subaccount %d" % n
        cash, parts = 0.0, []
        for ix in sorted(s["pools"]):
            p = s["pools"][ix]
            if p["dollars"] is None:
                parts.append("%s COULD NOT READ (%s)" % (_pool_name(ix), p["err"]))
                missing.append("%s %s cash" % (who, _pool_name(ix)))
                pool_t[ix] = None
                continue
            cash += p["dollars"]
            if pool_t.get(ix, 0.0) is not None:       # a pool already unread stays unread
                pool_t[ix] = pool_t.get(ix, 0.0) + p["dollars"]
            if abs(p["dollars"]) > 0.004 or p["from_list"]:
                parts.append("%s %s%s" % (_pool_name(ix), _usd2(p["dollars"]),
                                          (" (from Kalshi's list; the direct read failed: %s)" % p["err"])
                                          if p["from_list"] else ""))
        if s["open"] is None:
            ow = "COULD NOT READ (%s)" % s["open_err"]
            missing.append("%s open bets" % who)
        else:
            ow = "none" if not s["open_n"] else "%s on %s" % (_usd2(s["open"]), _nof(s["open_n"], "market"))
        whole = s["open"] is not None and all(p["dollars"] is not None for p in s["pools"].values())
        cash_t += cash
        open_t += s["open"] or 0.0
        total = cash + (s["open"] or 0.0)
        wk = None
        if hist is not None and hist.get(n) is not None:
            hd = funds_days(hist[n], today, sub=n)
            if any(x["read"] for x in hd["days"]):
                wk = (hd["total"]["all"]["money"], hd["total"]["all"]["n"], all(x["read"] for x in hd["days"]))
        accts.append(dict(n=n, s=s, what=what, name=name, cash=cash, parts=parts, ow=ow, whole=whole,
                          total=total, wk=wk))
    L = []
    if not f["subs"]:
        L.append("❔ <b>NO ACCOUNT COULD BE READ.</b> Nothing below is a zero -- it is unknown.")
    elif missing:
        L.append("🏦 <b>ALL ACCOUNTS: at least %s</b> (cash %s + open bets %s)" % (
            esc(_usd2(cash_t + open_t)), esc(_usd2(cash_t)), esc(_usd2(open_t))))
        L.append("⚠️ That leaves out what could not be read: %s." % esc(", ".join(missing)))
    else:
        L.append("🏦 <b>ALL ACCOUNTS: %s</b> = cash %s + open bets %s." % (
            esc(_usd2(cash_t + open_t)), esc(_usd2(cash_t)), esc(_usd2(open_t))))
    L.append("<i>MONEY IN EVERY ACCOUNT -- %s, read from Kalshi now.</i>" % esc(_bs().et_clock(now)))
    if f["list_err"]:
        L.append("⚠️ Kalshi's list of subaccounts could not be read (%s), so only the ones known here (%s) are "
                 "shown -- any other is missing." % (esc(f["list_err"]), esc(", ".join(str(n) for n in sorted(FUNDS_WHAT)))))
    kc = f.get("kalshi_cash")
    if kc and f["subs"] and None not in pool_t.values():
        ours = sum(v for v in pool_t.values())
        if all(abs(pool_t.get(ix, 0.0) - kc.get(ix, 0.0)) <= 0.02 for ix in set(kc) | set(pool_t)):
            L.append("✅ The cash adds up to Kalshi's own whole-account figure (%s)." % esc(_usd2(sum(kc.values()))))
        else:
            L.append("⚠️ CHECK: Kalshi's own whole-account cash is %s, but the accounts above add to %s -- an "
                     "account is missing from Kalshi's list, or a bet filled between reads (send /funds again)."
                     % (esc(_usd2(sum(kc.values()))), esc(_usd2(ours))))
    if accts:
        # Share = the account's slice of ALL ACCOUNTS (shown only when every account was read whole)
        allt = cash_t + open_t
        rows = [("Account", "Total $", "Share") + (("7 days",) if hist is not None else ())]
        for a in accts:
            nm = "%d %s" % (a["n"], funds_short(a["n"], active) or str(a["what"])[:10])
            tt = ("" if a["whole"] else ">=") + "{:,.2f}".format(a["total"])
            sh = (pct_of(a["total"], allt, 1) or "-") if (not missing and allt > 0.004) else "-"
            if hist is None:
                rows.append((nm, tt, sh))
                continue
            wk = a["wk"]
            if wk is None:
                w7 = "?"
            elif not wk[1] and wk[2]:
                w7 = "none"
            else:
                w7 = usd(wk[0]).replace("$", "") + ("" if wk[2] else "~")
                if a["whole"] and a["total"] >= 1.0:          # its share of what the account holds now
                    w7 += " (%s)" % _bs().pot_pct_txt(100.0 * wk[0] / a["total"])
            rows.append((nm, tt, sh, w7))
        L.append(pre(table(rows)))
        if hist is not None:
            L.append(i_("7 days = that account's money over the past 7 ET days and its share of what it holds now"))
        idle = [a for a in accts if funds_idle(a["n"], active) and a["whole"] and a["total"] > 0.004]
        if idle:
            it = sum(a["total"] for a in idle)
            L.append("💤 <b>Idle: %s</b>%s sits in %s nothing now (%s)." % (
                esc(_usd2(it)), (" (%s of all)" % pct_of(it, allt, 1)) if allt > 0.004 and not missing else "",
                "an account that runs" if len(idle) == 1 else "%d accounts that run" % len(idle),
                esc("; ".join("%d: %s" % (a["n"], a["what"]) for a in idle))))
    if hist is not None and accts and show < FUNDS_DAYS:
        L.append(i_("Past days: %s to fit one message; every 7-day total still counts all %d days." % (
            "the day lines are left out" if show <= 0 else "only the newest %d day lines are listed" % show,
            FUNDS_DAYS)))
    for a in accts:
        s, n = a["s"], a["n"]
        L.append("")
        L.append("<b>%s</b> -- %s: <b>%s%s</b>" % (esc(a["name"]), esc(a["what"]), "" if a["whole"] else "at least ",
                                                  esc(_usd2(a["total"]))))
        L.append("cash: %s; open bets: %s" % (esc(", ".join(a["parts"]) if a["parts"] else "$0.00"), esc(a["ow"])))
        if sizes.get(n):
            L.append("bet size now: " + esc("; ".join(sizes[n])))
        if hist is not None:
            L.extend(_funds_days_html(n, hist.get(n), today, show, (a["cash"] + s["open"]) if a["whole"] else None,
                                      active))
    L.append("")
    L.append(i_("Open bets count at what they cost. Bet sizes are from each bot's own log."
                + (" Past days: Kalshi's settlement records -- what each market paid minus its cost and fees, on "
                   "the ET day it closed (* = so far today); Lost 2/28 = 2 of the 28 markets settled lost money. "
                   "Deposits and transfers are not gains. Liquidity rewards are paid outside these records and "
                   "are not counted." if hist is not None else "")))
    return Html("\n".join(L))


# ===========================================================================
# /features -- what every bot does, and the settings it runs with right now.
#
# THE OPERATOR, 2026-10-22: one block a bot -- its name, what it does in a sentence, its live settings. The
# settings are NOT typed here: boot_all.ps1 is read when the command comes and every python launch's argument
# array is turned into "flag: value" lines, so the page cannot say a setting the machine is not running. The
# ladder's rails (the share of the bank allowed in open bids, the daily loss stop, the contract cap) are read
# the same way from research\cleanroom\ladder_live.py's constants. Nothing is executed: both files are text.
#
# boot_all.ps1 starts a python program in three shapes, and boot_launches() reads all three:
#   $cleanroom = @( @{ n = "label"; ...; a = @("-u", "research\x.py", "--flag", "v"); ... }, ... )
#   Start-Process -FilePath $py -ArgumentList @("-u", "$repo\research\x.py", ...)      (an `if ($false -and`
#       guard above it means OFF, and the launch is not listed)
#   $live = @(...) + $a.x + @("--arm-name", $a.n) -- the pin bot's paper arms: one block, the shared flags.
# `$repo`, `$res`, `$kals` inside the strings are filled from the script's own assignments.
# ===========================================================================
BOOT_ALL = os.path.join(os.path.dirname(HERE), "boot_all.ps1")
LADDER_PY = os.path.join(HERE, "cleanroom", "ladder_live.py")

# the roster: (script file, a flag it must have or None, a flag it must NOT have or None, label, one sentence).
# A launch in boot_all that matches no row is still shown (by boot_all's own label); a row with no launch says so.
# v-tg-active (2026-10-30): a money bot's row (FEATURE_BOT) is shown only while that bot is ACTIVE; its paper rows stay.
# v-tg-rebuild step 5 (2026-10-30): both from the registry -- each bot's Bot.features rows (Feature.pos keeps their
# places) between the other programs' rows (bots.EXTRA_FEATURES); FEATURE_BOT = the rows that are a bot's own
# (Feature.hides), shown only while it is active.
FEATURE_BOT = _bots.FEATURE_BOT
FEATURES = _bots.FEATURES

# plain words for the flags an operator meets most; any other flag is shown by its own name
FLAG_WORDS = {"subaccount": "subaccount", "live": "real money", "minutes": "runs for (minutes)", "coins": "coins",
              "levels": "rungs (levels)", "auto-size": "bet size follows the pot", "auto-scale": "bet size follows the pot",
              "market-cap-x": "cap per market (x bid size)", "pot-per-contract": "pot dollars per contract of size",
              "max-contracts": "most contracts a bet", "max-stake": "most dollars a bet",
              "live-max-losses": "losses a day before it stops", "max-losses": "losses a day before it stops",
              "live-min-price": "lowest price it buys", "min-price": "lowest price it buys", "log": "log file",
              "size": "contracts a bet", "loss-abort": "day stop (dollars)", "variant": "variant", "variants": "variants",
              "crash-gap": "crash guard gap (dollars)", "model": "price model"}

_PS_STR = re.compile(r'"([^"]*)"|\'([^\']*)\'')
_PS_VAR = re.compile(r"^\$(\w+) = \"([^\"]*)\"\s*$", re.M)
_PS_ENTRY = re.compile(r'n = "(?P<n>[^"]*)";(?P<rest>[^{}]*?)\ba = @\((?P<a>[^)]*)\)')
_PS_INLINE = re.compile(r"-ArgumentList @\(([^)]*)\)")
_PS_LIVE = re.compile(r"\$live = @\(([^)]*)\)")
_PS_ARM = re.compile(r'@\{ n = "(arm-[^"]+)";\s*x = ')
_PY_CONST = re.compile(r"^([A-Z_][A-Z_0-9]*(?:, [A-Z_][A-Z_0-9]*)*) = (-?[\d.]+(?:, -?[\d.]+)*)\s*(?:#.*)?$", re.M)


def _ps_strings(array_text, vars_):
    """The quoted strings of a PowerShell @( ... ) body, in order, $name filled from `vars_`."""
    out = []
    for m in _PS_STR.finditer(array_text):
        s = m.group(1) if m.group(1) is not None else m.group(2)
        out.append(re.sub(r"\$(\w+)", lambda v: vars_.get(v.group(1), v.group(0)), s))
    return out


def boot_launches(text):
    """Every python program boot_all.ps1 starts, as [{"label", "script", "argv", "arms"}] in file order. `label`
    is boot_all's own (`n = "..."`), or None for a bare Start-Process; `script` the .py file name; `arms` the arm
    names for the pin bot's paper set (otherwise [])."""
    vars_ = dict(_PS_VAR.findall(text))
    for _ in range(2):                                           # $res = "$repo\results": two levels deep at most
        vars_ = {k: re.sub(r"\$(\w+)", lambda v: vars_.get(v.group(1), v.group(0)), s) for k, s in vars_.items()}
    found = []
    for m in _PS_ENTRY.finditer(text):
        st = re.search(r'\bstop = "([^"]*)"', m.group("rest"))       # boot_all leaves it off while this file exists
        stop = re.sub(r"\$(\w+)", lambda v: vars_.get(v.group(1), v.group(0)), st.group(1)) if st else None
        found.append((m.start(), m.group("n"), _ps_strings(m.group("a"), vars_), [], stop))
    for m in _PS_INLINE.finditer(text):
        guard = text.rfind("if (", 0, m.start())                 # the nearest `if (` above: `$false -and` = OFF
        if guard >= 0 and "$false" in text[guard:text.find("\n", guard)]:
            continue
        found.append((m.start(), None, _ps_strings(m.group(1), vars_), [], None))
    m = _PS_LIVE.search(text)
    if m:
        found.append((m.start(), None, _ps_strings(m.group(1), vars_), _PS_ARM.findall(text), None))
    out = []
    for _pos, label, argv, arms, stop in sorted(found, key=lambda f: f[0]):
        script = next((re.split(r"[\\/]", a)[-1] for a in argv if a.lower().endswith(".py")), "")
        if script:
            out.append({"label": label, "script": script, "argv": argv, "arms": arms, "stop": stop})
    return out


def _stopped_since(x):
    """The epoch its stop file was written when boot_all's entry `x` is stood down by it, else None."""
    try:
        return os.path.getmtime(x["stop"]) if x.get("stop") and os.path.exists(x["stop"]) else None
    except OSError:
        return None


def _is_flag(t):
    return t.startswith("--") or (len(t) > 1 and t[0] == "-" and t[1].isalpha())


def flag_value(argv, flag):
    """The token after `flag` in argv, or None when the flag is missing or has nothing after it."""
    i = argv.index(flag) if flag in argv else -1
    return argv[i + 1] if 0 <= i < len(argv) - 1 else None


def argv_lines(argv):
    """'flag: value' lines for one launch, plain words where FLAG_WORDS has them. -u and the script path are
    left out; a flag with no value reads 'on'; a file path shows its name; 'A,B,C' reads 'A, B, C'."""
    toks = [t for t in argv if t != "-u" and not t.lower().endswith(".py")]
    out, i = [], 0
    while i < len(toks):
        if not _is_flag(toks[i]):
            out.append(esc(toks[i]))
            i += 1
            continue
        flag, vals, j = toks[i].lstrip("-"), [], i + 1
        while j < len(toks) and not _is_flag(toks[j]):
            v = toks[j]
            if re.search(r"[\\/]", v):
                v = re.split(r"[\\/]", v)[-1]
            vals.append(v.replace(",", ", "))
            j += 1
        out.append("%s: %s" % (esc(FLAG_WORDS.get(flag, flag.replace("-", " "))), esc(" ".join(vals) or "on")))
        i = j
    return out


def py_consts(text, names):
    """{name: value} for the module-level number constants `names` in a python file's text, from plain
    `X = 1` lines and tuple lines `A, B = 0.20, 0.70` alike (the first assignment of each wins)."""
    out = {}
    for m in _PY_CONST.finditer(text):
        ks, vs = m.group(1).split(", "), m.group(2).split(", ")
        for k, v in zip(ks, vs):
            if k in names and k not in out:
                out[k] = float(v)
    return out


def ladder_rules_html(path=None):
    """'Rules the bots run under': the ladder's rails from ladder_live.py's constants, read now."""
    path = path or LADDER_PY
    L = ["<b>Rules the bots run under</b> (%s)" % esc(os.path.basename(path))]
    try:
        with open(path, encoding="utf-8") as fh:
            c = py_consts(fh.read(), ("COMMIT_FRAC", "DAY_STOP_FRAC", "MAX_CONTRACTS"))
    except OSError as e:
        L.append(esc("could not read it: %s" % e))
        return L
    if "COMMIT_FRAC" in c:
        L.append("Open bids: at most <b>%d%%</b> of the bank in resting bids at once (COMMIT_FRAC %s)."
                 % (round(c["COMMIT_FRAC"] * 100), esc(c["COMMIT_FRAC"])))
    if "DAY_STOP_FRAC" in c:
        L.append("Daily loss stop: down <b>%d%%</b> of the day's first pot and it stops bidding until tomorrow "
                 "(DAY_STOP_FRAC %s)." % (round(c["DAY_STOP_FRAC"] * 100), esc(c["DAY_STOP_FRAC"])))
    if "MAX_CONTRACTS" in c:
        L.append("Contracts out at once: at most <b>%dx</b> the bid size, resting and held together (MAX_CONTRACTS "
                 "%d per contract of size)." % (int(c["MAX_CONTRACTS"]), int(c["MAX_CONTRACTS"])))
    for k in ("COMMIT_FRAC", "DAY_STOP_FRAC", "MAX_CONTRACTS"):
        if k not in c:
            L.append(esc("%s: not found in the file" % k))
    return L


def _hand_started(bot, procs=None):
    """A live bot boot_all does not start: its settings from its own start record (botstats), said as such."""
    L = [i_("not started by boot_all: started by hand on the server (results\\jb_deploy.ps1); nothing restarts it if it dies")]
    try:
        r = _bs().running(bot, _bs()._norm_procs(procs) if procs is not None and not callable(procs) else None,
                          procs is not None and not callable(procs), time.time())
        if r.get("settings_text"):
            L.append(esc("settings: " + r["settings_text"]))
        if r.get("command"):
            toks = r["command"].replace('"', " ").split()
            i = next((k for k, t in enumerate(toks) if t.lower().endswith(".py")), -1)
            L.extend(argv_lines(toks[i + 1:]))                    # its flags, after the script (not python.exe)
    except Exception as e:                                      # noqa: BLE001
        L.append(esc("its settings could not be read: %s" % str(e)[:80]))
    return L


def features_html(boot_path=None, ladder_path=None, active=None, procs=None):
    """The /features page: a block a bot from FEATURES, its settings from boot_all.ps1 as it is now, the ladder's
    goal and rungs, then the rules block. Longer than one message: Telegram.send cuts it at a blank line.
    v-tg-active: with `active`, a money bot that is not active gets no block (its boot_all launch neither); an active bot
    boot_all does not start (the jump band, started by hand) shows its settings from its live start record."""
    boot_path = boot_path or BOOT_ALL
    try:
        with open(boot_path, encoding="utf-8") as fh:
            launches = boot_launches(fh.read())
        boot_err = None
    except OSError as e:
        launches, boot_err = [], str(e)
    L = ["🧩 <b>Features</b> -- what each bot does, and the settings it runs with now (read from %s)"
         % esc(os.path.basename(boot_path))]
    if boot_err:
        L.append(esc("could not read it: %s -- the settings below are missing" % boot_err))
    used = set()
    for script, must, must_not, label, what in FEATURES:
        mine = [k for k, x in enumerate(launches) if x["script"] == script
                and (must is None or must in x["argv"]) and (must_not is None or must_not not in x["argv"])]
        used.update(mine)
        bot = FEATURE_BOT.get((script, must))
        if active is not None and bot is not None and bot not in active:
            continue                                     # v-tg-active: a paused or retired bot is not listed
        if bot is not None and not mine and _bots.get(bot).keepalive is None:   # started by hand (the jump band)
            L.append("")
            L.append("<b>%s</b>" % esc(label))
            L.append(esc(what))
            L += _hand_started(bot, procs)
            continue
        # 2026-10-23: a bot boot_all keeps off with its stop file says so, without its settings (it read LIVE)
        off = [_stopped_since(launches[k]) for k in mine]
        if mine and all(t is not None for t in off):
            L.append("")
            L.append("⏸ <b>%s</b>" % esc(label.replace("LIVE, ", "STOPPED, ").replace("(LIVE)", "(STOPPED)")))
            L.append(esc(what))
            L.append(i_("stopped by its stop file since %s; boot_all leaves it off" % et_str(min(off), "%b %d")))
            continue
        L.append("")
        L.append("<b>%s</b>" % esc(label))
        L.append(esc(what))
        if script == "ladder_live.py":
            L.append("goal <b>1%/day</b> of its bank")
            L.append("98c rung: buy the already-decided side 2c below fair")
            if any("1" in (flag_value(launches[k]["argv"], "--levels") or "").split(",") for k in mine):
                L.append("95c rung: the same at 5c below fair")
        if not mine:
            L.append(i_("not started by boot_all" + (" (watch_bot.ps1 starts the live pin bot)"
                                                      if script == "pinrun.py" and must == "--live" else "")))
            continue
        for n, k in enumerate(mine, 1):
            x = launches[k]
            if len(mine) > 1:                                    # several launches: boot_all's label, or a count
                L.append(i_(x["label"] or "%d of %d" % (n, len(mine))))
            L.extend(argv_lines(x["argv"]))
            if x["arms"]:
                L.append("arms: <b>%d</b> -- %s" % (len(x["arms"]), esc(", ".join(x["arms"]))))
                L.append(i_("each arm adds its own band, early-leg or confidence flags to the shared ones above"))
    hidden_scripts = {sc for (sc, _m), b in FEATURE_BOT.items() if active is not None and b not in active}
    for k, x in enumerate(launches):
        if k not in used and x["script"] not in hidden_scripts:
            L.append("")
            off = _stopped_since(x)
            L.append("%s<b>%s</b>" % ("⏸ " if off is not None else "", esc(x["label"] or x["script"])))
            if off is not None:
                L.append(i_("stopped by its stop file since %s; boot_all leaves it off" % et_str(off, "%b %d")))
                continue
            L.append(i_("started by boot_all; not written up here yet"))
            L.extend(argv_lines(x["argv"]))
    L.append("")
    L.extend(ladder_rules_html(ladder_path))
    L.append("")
    L.append(i_("Read from the files each time you ask. A bot that is up keeps the settings it started with until "
                "boot_all starts it again (within 10 minutes of it stopping)."))
    return Html("\n".join(L))


# ===========================================================================
# /speed and /server (2026-10-27): the bots moved from the home laptop to an AWS server in Ohio.
#
# THE OPERATOR, 2026-10-27: "Yes add speed" (to: a /speed screen "that shows this, server against home, with the
# dollars") and "Yes add server command. If possible add server funds and cost and spending too to that".
#
# /speed splits the bots' OWN order logs at SERVER_SINCE: home = the SPEED_HOME_DAYS days before it (the laptop),
# server = since. The pin bot's orders are the Ledger's (every pinrun-live log, already in this process: read once,
# then only the new bytes); its money per filled contract comes from the `settled` rows of the pin logs written
# since the move; the FX taker, forecaster and coin race from their own logs, read once whole and then only what was
# added (tail_rows). No Kalshi read anywhere, so it answers in well under a second.
#
# /server reads the machine through Windows itself (ctypes: kernel32; winreg for a waiting restart; psutil is not
# installed and none is added), times a bare TCP connect to Kalshi (the handshake only: no request is sent, so no
# Kalshi rate limit is touched), shows every pot's money from botstats' cache (the last read /bots, /funds or a chart
# made: no read of its own) and the AWS bill from AWS's own Budgets and Cost Explorer APIs, signed here (SigV4 with
# hashlib and hmac) with the short-lived keys of the instance's IAM role from the EC2 metadata service: no stored
# keys, no boto3. Every reading is cached, has a short timeout, and none raises into the screen.
# ===========================================================================
# THE MOVE: the first live bot started on the server at this instant (00:20:52 ET, 10-27). Before it every bot and
# this phone link ran on the operator's home laptop; from it on, on the EC2 server. /speed's "server" is at or after
# it, "home" the SPEED_HOME_DAYS days before it.
SERVER_SINCE = "2026-10-27T04:20:52Z"
SERVER_SINCE_EPOCH = calendar.timegm(time.strptime(SERVER_SINCE, "%Y-%m-%dT%H:%M:%SZ"))
SPEED_HOME_DAYS = 14
SPEED_MIN_ORDERS = 50           # fewer pin orders than this on the server: "too early to tell"
SPEED_MIN_OTHER = 20            # ... and for another bot's line
# the other bots whose own logs say, per order, what was asked and what was got: (bot, log, the field that names a
# record, the order record's name). Only orders Kalshi took count (a refusal, e.g. 'market not found', is no race).
# v-tg-rebuild step 5 (2026-10-30): from the registry (each bot's Bot.speed: its order record, or why it is skipped;
# its log is its Logs.path; its name on the page its Bot.short)
SPEED_OTHERS = _bots.SPEED_OTHERS
SPEED_SKIPPED = _bots.SPEED_SKIPPED
SPEED_LABEL = _bots.SPEED_LABEL

# THE SERVER, as AWS shows it (the console, 10-27). The prices are AWS's on-demand list for us-east-2 and only feed the
# ESTIMATE /server shows next to (or, until the billing role exists, instead of) AWS's own figures.
AWS_REGION, AWS_AZ = "us-east-2", "us-east-2a"
AWS_INSTANCE_TYPE = "t3.medium"                 # 2 vCPU, 4 GB, Windows Server 2022
AWS_INSTANCE_ID = "i-0c9f332f93359f898"
AWS_INSTANCE_NAME = "kals-bot"
AWS_ELASTIC_IP = "18.216.240.218"
AWS_ACCOUNT_ID = "001634075101"                 # "Building Things"; the metadata service's own answer wins when read
AWS_DISK_GB = 50
AWS_EC2_HOURLY = 0.0600                         # t3.medium with the Windows licence, an hour
AWS_IPV4_HOURLY = 0.005                         # the public (Elastic) IPv4 address, an hour = $3.65 a month
AWS_DISK_MONTH = 4.00                           # 50 GB gp3 at $0.08 a GB-month
AWS_HOURS_MONTH = 730.0
AWS_BUDGET_USD = 120.0                          # the monthly budget / spend alert the operator set in the console
AWS_BILLED_FROM = "2026-10-27T03:05:44Z"        # the instance's first boot (Windows' install date there)
AWS_BILLED_FROM_EPOCH = calendar.timegm(time.strptime(AWS_BILLED_FROM, "%Y-%m-%dT%H:%M:%SZ"))
AWS_ROLE_NAME = "kals-server-billing"
AWS_IMDS = "http://169.254.169.254"             # the EC2 instance metadata service (IMDSv2: a token first)
AWS_IMDS_TIMEOUT_S = 0.6
AWS_API_TIMEOUT_S = 5.0
AWS_CREDS_SKEW_S = 300                          # a role key is renewed this long before AWS says it expires
AWS_NOT_CONNECTED_TTL_S = 300                   # no role yet: asked again after this long (a new role shows in 5 min)
AWS_BUDGET_TTL_S = 3600                         # DescribeBudgets is free; AWS refreshes a budget a few times a day
AWS_CE_TTL_S = 6 * 3600                         # Cost Explorer charges $0.01 a request: at most every 6 hours
AWS_ERR_TTL_S = 900                             # a failed Budgets / Cost Explorer read is tried again after this long
AWS_BUDGETS_HOST = "budgets.amazonaws.com"      # both are global APIs, signed for us-east-1
AWS_CE_HOST = "ce.us-east-1.amazonaws.com"
AWS_SERVICE_SHORT = {"Amazon Elastic Compute Cloud - Compute": "EC2 instance", "EC2 - Other": "EC2 other (disk, data)",
                     "Amazon Virtual Private Cloud": "public IPv4", "AWS Cost Explorer": "Cost Explorer reads",
                     "Tax": "tax", "AWS Budgets": "Budgets"}
KALSHI_HOST = "api.elections.kalshi.com"
KALSHI_PING_TTL_S = 60
KALSHI_PING_TRIES = 3
SERVER_WARN_CPU, SERVER_WARN_MEM, SERVER_WARN_DISK_GB = 90.0, 90, 8.0


def _et_at(epoch, with_day=True):
    """'Oct 27 12:20 AM ET' (or '12:20 AM ET') -- botstats.et_clock's style, kept here so a broken botstats costs only
    the pages that need it."""
    if epoch is None:
        return "?"
    tm = time.gmtime(float(epoch) + pinday.et_offset(float(epoch)))
    hm_ = "%d:%02d %s" % (tm.tm_hour % 12 or 12, tm.tm_min, "AM" if tm.tm_hour < 12 else "PM")
    return ("%s %d %s ET" % (time.strftime("%b", tm), tm.tm_mday, hm_)) if with_day else hm_ + " ET"


def _span_words(s):
    """'3 days 4 h' / '1 h 42 min' / '12 min' / '40 s'."""
    s = max(0.0, _f(s))
    if s < 60:
        return "%d s" % s
    if s < 3600:
        return "%d min" % (s // 60)
    if s < 86400:
        return "%d h %d min" % (s // 3600, (s % 3600) // 60)
    d = int(s // 86400)
    return "%d day%s %d h" % (d, "" if d == 1 else "s", (s % 86400) // 3600)


def _gb(x, digits=1):
    return "?" if x is None else ("%." + str(digits) + "f GB") % (x / 1e9)


def _ms(x):
    return "?" if x is None else ("%.0f ms" % x if x >= 10 else "%.1f ms" % x)


def _usd4(x):
    """A small amount to the hundredth of a cent, signed: +$0.0167 a contract."""
    if x is None:
        return "?"
    return ("+$" if x > 0 else ("-$" if x < 0 else "$")) + "%.4f" % abs(x)


def _pct0(x):
    return "-" if x is None else "%.0f%%" % x


# ---- an append-only log, read once and then only what was added ----------------------------------------------------
_TAILS = {}


def tail_rows(path, field, value):
    """Every record of an append-only jsonl log whose `field` is `value`, read ONCE whole and after that only the bytes
    added since the last call (a file that shrank was replaced: it is read again from the start). Lines are screened
    by substring before json.loads, and a cut last line waits for its end. [] when the file cannot be read."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    key = (path, field, value)
    hit = _TAILS.get(key)
    if hit is None or size < hit["off"]:
        hit = _TAILS[key] = {"off": 0, "rows": []}
    if size > hit["off"]:
        try:
            with open(path, "rb") as fh:
                fh.seek(hit["off"])
                chunk = fh.read(size - hit["off"])
        except OSError:
            return hit["rows"]
        cut = chunk.rfind(b"\n")
        if cut >= 0:
            needle = ('"%s"' % value).encode("utf-8")
            for line in chunk[:cut + 1].split(b"\n"):
                if needle not in line:
                    continue
                try:
                    r = json.loads(line.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get(field) == value:
                    hit["rows"].append(r)
            hit["off"] += cut + 1
    return hit["rows"]


# ---- /speed --------------------------------------------------------------------------------------------------------
def _median(xs):
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _rank(xs, q):
    """The nearest-rank q-th quantile of a sorted list (q=0.9: the 90th percentile), None when empty."""
    if not xs:
        return None
    k = int(q * len(xs))
    k = k if k == q * len(xs) else k + 1
    return xs[max(0, k - 1)]


def _speed_win(rows, t0, t1):
    return [o for o in rows if o.get("t") is not None and t0 <= o["t"] < t1]


def pin_speed_orders(orders):
    """The Ledger's order rows (pindesk) of the pin bot's own logs, as /speed counts them: t, ticker, got, asked, ms."""
    return [{"t": o.get("t"), "tk": o.get("tk"), "got": _f(o.get("filled")), "asked": _fnum(o.get("asked")),
             "ms": o.get("latency_ms")}
            for o in orders if str(o.get("file") or "").startswith("pinrun-live-")]


def speed_stats(rows):
    """One window's orders, worked out: n, zero (orders that got nothing) and its share, contracts got and asked, got
    of asked (over the orders whose ask is known), and the send-to-answer time: how many have one, median, p90."""
    lat = sorted(float(o["ms"]) for o in rows if isinstance(o.get("ms"), (int, float)) and o["ms"] >= 0)
    known = [o for o in rows if o.get("asked")]
    n = len(rows)
    zero = sum(1 for o in rows if _f(o.get("got")) <= 0)
    asked = sum(_f(o["asked"]) for o in known)
    return {"n": n, "zero": zero, "zero_share": (float(zero) / n) if n else None,
            "got": sum(_f(o.get("got")) for o in rows), "asked": asked,
            "got_share": (sum(_f(o.get("got")) for o in known) / asked) if asked > 0 else None,
            "lat_n": len(lat), "med_ms": _median(lat), "p90_ms": _rank(lat, 0.9)}


def _other_order(bot, r):
    """One other bot's order record as /speed counts it, or None when Kalshi did not take it."""
    t = pindesk.parse_t(r.get("t"))
    if bot == "race":
        code = r.get("status_code")
        took = code in (200, 201) if code is not None else r.get("status") in (
            "executed", "canceled", "partially_filled_then_canceled")
        return {"t": t, "tk": r.get("ticker"), "got": _f(r.get("filled")), "asked": _fnum(r.get("count_asked")),
                "ms": None} if took else None
    if r.get("status") not in (200, 201):
        return None
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    rtt = _fnum(r.get("rtt"))
    return {"t": t, "tk": body.get("ticker"), "got": _f(r.get("filled")), "asked": _fnum(body.get("count")),
            "ms": rtt * 1000.0 if rtt is not None else None}


def speed_pin_money(results, server_rows, since):
    """What the pin bot made on the server, per filled contract: the `settled` rows' pnl_c (each leg, a hedge's
    included, fees in) of the pin logs written since `since`, on the markets it got contracts in on the server, over those
    contracts. Markets not settled yet are left out (their contracts are `open_contracts`)."""
    import glob
    got = {}
    for o in server_rows:
        if o.get("tk") and _f(o.get("got")) > 0:
            got[o["tk"]] = got.get(o["tk"], 0.0) + _f(o["got"])
    made = {}
    for p in sorted(glob.glob(os.path.join(results, "pinrun-live-*.jsonl"))):
        try:
            if os.path.getmtime(p) < since:
                continue
        except OSError:
            continue
        for r in tail_rows(p, "kind", "settled"):
            t, tk = pindesk.parse_t(r.get("t")), r.get("ticker")
            if t is None or t < since or tk not in got:
                continue
            v = _fnum(r.get("pnl_c"))              # this leg's money in cents; `realised` is the RUN's running total
            if v is not None:
                made[tk] = made.get(tk, 0.0) + v / 100.0
    contracts = sum(got[tk] for tk in made)
    usd_ = sum(made.values())
    return {"usd": usd_, "contracts": contracts, "markets": len(made),
            "per": (usd_ / contracts) if contracts > 0 else None,
            "open_contracts": sum(v for tk, v in got.items() if tk not in made)}


def speed_estimate(home, srv, money, span_s):
    """What speed added, an ESTIMATE: (server got/asked - home got/asked) x contracts asked on the server = the extra
    contracts; x the $ the server's filled contracts made each. None-valued with `why` when a part is missing."""
    out = {"d_share": None, "extra": None, "usd": None, "per_day": None, "days": span_s / 86400.0, "why": None}
    if home["got_share"] is None:
        out["why"] = "no pin orders at home to compare with"
    elif srv["got_share"] is None:
        out["why"] = "no pin orders on the server yet"
    elif money["per"] is None:
        out["why"] = "none of the server's filled pin markets has settled yet"
    else:
        out["d_share"] = srv["got_share"] - home["got_share"]
        out["extra"] = out["d_share"] * srv["asked"]
        out["usd"] = out["extra"] * money["per"]
        if out["days"] >= 1.0:
            out["per_day"] = out["usd"] / out["days"]
    return out


def speed_gather(results, orders, now, since=None, home_days=None, active=None):
    """Everything /speed shows, worked from the logs (see the section's head). `orders` = the Ledger's order rows.
    `active` (v-tg-active): the other bots' lines for those bots only (None = every bot)."""
    since = SERVER_SINCE_EPOCH if since is None else since
    h0 = since - (SPEED_HOME_DAYS if home_days is None else home_days) * 86400
    pins = pin_speed_orders(orders)
    home, srv = _speed_win(pins, h0, since), _speed_win(pins, since, now + 1)
    d = {"since": since, "home_from": h0, "now": now, "others": [],
         "skipped": [x for x in SPEED_SKIPPED if active is None or x[0] in active],
         "pin": {"home": speed_stats(home), "server": speed_stats(srv)}}
    d["pin"]["money"] = speed_pin_money(results, srv, since)
    d["pin"]["est"] = speed_estimate(d["pin"]["home"], d["pin"]["server"], d["pin"]["money"], now - since)
    for bot, name, field, value in SPEED_OTHERS:
        if active is not None and bot not in active:
            continue
        p = os.path.join(results, name)
        if not os.path.exists(p):
            d["others"].append({"bot": bot, "missing": name})
            continue
        rows = [x for x in (_other_order(bot, r) for r in tail_rows(p, field, value)) if x and x["t"] is not None]
        d["others"].append({"bot": bot, "home": speed_stats(_speed_win(rows, h0, since)),
                            "server": speed_stats(_speed_win(rows, since, now + 1)),
                            "has_ms": any(x["ms"] is not None for x in rows)})
    return d


def _speed_other_line(x, min_other):
    name = SPEED_LABEL.get(x["bot"], x["bot"])
    if x.get("missing"):
        return "<b>%s</b>: skipped: no log here (%s)" % (esc(name), esc(x["missing"]))
    h, s = x["home"], x["server"]

    def part(st, where):
        if not st["n"]:
            return "%s: no orders" % where
        got = 100.0 * (1.0 - st["zero_share"])
        return "%s %s got something (%s of %s%s)" % (
            where, _pct0(got), _cnt(st["n"] - st["zero"]), _nof(st["n"], "order"),
            (", %s" % _ms(st["med_ms"])) if st["med_ms"] is not None else "")
    tail = []
    if s["n"] and s["n"] < min_other:
        tail.append("too few on the server to tell")
    if not x.get("has_ms"):
        tail.append("its log keeps no send time")
    return "<b>%s</b>: %s · %s%s" % (esc(name), esc(part(h, "home")), esc(part(s, "server")),
                                     (" · " + esc("; ".join(tail))) if tail else "")


def speed_html(d, bank=None, min_orders=None, min_other=None):
    """/speed's screen from speed_gather's numbers. `bank` = the main account's bank (the pin bot's), for the %."""
    min_orders = SPEED_MIN_ORDERS if min_orders is None else min_orders
    min_other = SPEED_MIN_OTHER if min_other is None else min_other
    pin = d["pin"]
    h, s, mo, est = pin["home"], pin["server"], pin["money"], pin["est"]
    early = s["n"] < min_orders
    bank_pct = (" (%s of the main account's %s bank)" % (ret(est["usd"], bank, 2), dollars(bank))
                if est["usd"] is not None and bank and ret(est["usd"], bank, 2) else "")
    L = []
    if not s["n"]:
        L.append("⏳ <b>SPEED: too early to tell, no pin orders on the server yet</b>")
    elif early:
        L.append("⏳ <b>SPEED: too early to tell, %s so far</b> on the server (the bar is %d)"
                 % (esc(_nof(s["n"], "order")), min_orders))
    else:
        L.append("⚡ <b>SPEED: %s on the server, was %s at home</b> (median, send to answer)"
                 % (esc(_ms(s["med_ms"])), esc(_ms(h["med_ms"]))))
    if s["n"]:
        L.append("Pin orders that got nothing: <b>%s</b> on the server, %s at home · contracts got of those asked: "
                 "<b>%s</b>, was %s" % (pct1(s["zero"], s["n"]), pct1(h["zero"], h["n"]),
                                        _of100(s["got_share"]) + "%" if s["got_share"] is not None else "-",
                                        _of100(h["got_share"]) + "%" if h["got_share"] is not None else "-"))
    if est["usd"] is not None:
        L.append("%s What speed added: about <b>%s</b>%s since the move%s · an estimate, not a proof" % (
            dot(est["usd"]), esc(usd(est["usd"])), esc(bank_pct),
            (" (too early: %s)" % esc(_nof(s["n"], "order"))) if early else ""))
    L.append(i_("Pin bot · home = %s to %s (%d days, the laptop) · server = since %s (%s so far, AWS Ohio)" % (
        _et_at(d["home_from"]), _et_at(d["since"]), round((d["since"] - d["home_from"]) / 86400.0),
        _et_at(d["since"]), _span_words(d["now"] - d["since"]))))
    L.append("")
    rows = [("Pin bot", "Home", "Server"),
            ("Orders", _cnt(h["n"]), _cnt(s["n"])),
            ("Median", _ms(h["med_ms"]) if h["lat_n"] else "-", _ms(s["med_ms"]) if s["lat_n"] else "-"),
            ("90% under", _ms(h["p90_ms"]) if h["lat_n"] else "-", _ms(s["p90_ms"]) if s["lat_n"] else "-"),
            ("Got nothing", pct1(h["zero"], h["n"]), pct1(s["zero"], s["n"])),
            ("Got / asked", (_of100(h["got_share"]) + "%") if h["got_share"] is not None else "-",
             (_of100(s["got_share"]) + "%") if s["got_share"] is not None else "-"),
            ("Contracts got", _cnt(h["got"]), _cnt(s["got"])),
            ("  asked", _cnt(h["asked"]), _cnt(s["asked"]))]
    L.append(pre(table(rows)))
    L.append("")
    L.append("💵 <b>What speed added (an estimate, not a proof)</b>")
    L.append(i_("extra contracts = (server got/asked - home got/asked) x contracts asked on the server; "
                "$ = extra contracts x the $ made per filled contract on the server"))
    if est["d_share"] is not None:
        L.append("(%s%% - %s%%) x %s asked on the server = <b>%s%s extra contracts</b>" % (
            _of100(s["got_share"]), _of100(h["got_share"]), _cnt(s["asked"]), "+" if est["extra"] > 0 else "",
            esc(_cnt(est["extra"]) if est["extra"] >= 0 else "-" + _cnt(-est["extra"]))))
        L.append("x %s a filled contract (%s on %s contracts in %s settled on the server) = <b>%s</b>%s" % (
            esc(_usd4(mo["per"])), esc(usd(mo["usd"])), esc(_cnt(mo["contracts"])), esc(_nof(mo["markets"], "market")),
            esc(usd(est["usd"])), esc(bank_pct)))
        if est["per_day"] is not None:
            L.append("About <b>%s a day</b> at this pace%s." % (
                esc(usd(est["per_day"])), (" (%s of the bank a day)" % esc(ret(est["per_day"], bank, 2)))
                if bank and ret(est["per_day"], bank, 2) else ""))
        if early:
            L.append("⏳ Too early to tell: %s so far (the bar is %d); a few orders swing this a lot."
                     % (esc(_nof(s["n"], "order")), min_orders))
    else:
        L.append("Not yet: %s." % esc(est["why"]))
    L.append("")
    L.append("🤖 <b>Other bots</b> (orders Kalshi took: how many got something, median send to answer)")
    for x in d["others"]:
        L.append(_speed_other_line(x, min_other))
    for bot, why in d["skipped"]:
        L.append("<b>%s</b>: %s" % (esc(SPEED_LABEL.get(bot, bot)), esc(why)))
    L.append(details(elines([
        "Send to answer = the pin bot's own latency_ms on each order: from sending it to Kalshi's reply. 90% under = "
        "the time 90% of the orders beat.",
        "Got nothing = an order Kalshi answered with no contracts: someone faster took them, or the price moved first.",
        "Got / asked = contracts filled over contracts asked, every order in the window.",
        "$ per filled contract = what the pin bot's markets settled on the server made (its own settled rows: both "
        "legs, a hedge's included, fees in), over the contracts it got in them. Markets still open are left out "
        "(%s contracts now)." % _cnt(mo["open_contracts"]),
        "Why only an estimate: it assumes the extra contracts made what the server's filled ones made, and that the "
        "markets of the two windows were alike. Neither is proven; the gap in got/asked is the measured part.",
        "Other bots: only orders Kalshi took count (a refusal such as 'market not found' is no race); their time is the "
        "bot's own send-to-answer time (rtt).%s" % (" The coin race keeps none." if any(x.get("bot") == "race"
                                                                                       for x in d["others"]) else ""),
        "Home = the %d days before the move (SERVER_SINCE = %s, a constant in pinphone.py); server = since. Read from "
        "the bots' own logs; nothing is asked of Kalshi." % (SPEED_HOME_DAYS, SERVER_SINCE)]),
        "🔎 How each figure is worked (tap)"))
    L.append(i_("/server: the machine, the time to Kalshi, the funds and the AWS bill"))
    return Html("\n".join(L))


# ---- /server: the machine, from Windows itself --------------------------------------------------------------------
_W32 = {}


def _w32():
    """kernel32 through ctypes, set up once in a private handle (its argtypes never touch ctypes.windll's shared one)."""
    if "k32" not in _W32:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        ft = ctypes.POINTER(wintypes.FILETIME)
        k.GetSystemTimes.argtypes = (ft, ft, ft)
        k.GetSystemTimes.restype = wintypes.BOOL
        k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        k.CloseHandle.restype = wintypes.BOOL
        k.GetProcessTimes.argtypes = (wintypes.HANDLE, ft, ft, ft, ft)
        k.GetProcessTimes.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD))
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k.K32EnumProcesses.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
        k.K32EnumProcesses.restype = wintypes.BOOL
        k.K32GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD)
        k.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        k.GlobalMemoryStatusEx.argtypes = (ctypes.c_void_p,)
        k.GlobalMemoryStatusEx.restype = wintypes.BOOL
        k.GetTickCount64.argtypes = ()
        k.GetTickCount64.restype = ctypes.c_ulonglong
        _W32.update(k32=k, ct=ctypes, wt=wintypes)
    return _W32["k32"], _W32["ct"], _W32["wt"]


def _ft(f):
    return (f.dwHighDateTime << 32) | f.dwLowDateTime          # 100-ns units


def _python_handles(k, ct, wt):
    """{pid: open handle} for every python.exe / pythonw.exe this account may query (the caller closes them)."""
    n = 4096
    while True:
        arr = (wt.DWORD * n)()
        got = wt.DWORD()
        if not k.K32EnumProcesses(arr, ct.sizeof(arr), ct.byref(got)):
            raise OSError("EnumProcesses failed (%d)" % ct.get_last_error())
        if got.value < ct.sizeof(arr):
            break
        n *= 2
    out = {}
    buf = ct.create_unicode_buffer(1024)
    for pid in arr[:got.value // ct.sizeof(wt.DWORD)]:
        if not pid:
            continue
        h = k.OpenProcess(0x1000 | 0x0010, False, pid)            # QUERY_LIMITED_INFORMATION | VM_READ
        if not h:
            h = k.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        size = wt.DWORD(len(buf))
        if k.QueryFullProcessImageNameW(h, 0, buf, ct.byref(size)) \
                and os.path.basename(buf.value).lower() in ("python.exe", "pythonw.exe"):
            out[pid] = h
        else:
            k.CloseHandle(h)
    return out


REBOOT_KEYS = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending")


def reboot_pending():
    """(True, by what) when Windows Update or a Windows component update waits for a restart (either key is there),
    (False, None) when neither is, (None, why) when the registry could not be read."""
    import winreg
    for path in REBOOT_KEYS:
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path))
            return True, ("Windows Update" if "WindowsUpdate" in path else "a Windows component update")
        except FileNotFoundError:
            continue
        except OSError as e:
            return None, str(e)[:80]
    return False, None


def machine_read(sample_s=0.5):
    """This machine now, from Windows itself. Every figure is None when its call fails, and why goes in `errs`.
    cpu = % busy over `sample_s` seconds, every core; py_cpu = the python processes' (the bots, the recorders, this
    phone link) share of the whole machine over the same seconds; py_mem = the RAM they hold (working sets, bytes)."""
    out = {"host": os.environ.get("COMPUTERNAME"), "ncpu": os.cpu_count(), "cpu": None, "py_cpu": None, "py_n": None,
           "py_mem": None, "mem_total": None, "mem_avail": None, "mem_load": None, "commit": None, "commit_limit": None,
           "disk_free": None, "disk_total": None, "uptime_s": None, "reboot": None, "reboot_why": None,
           "sample_s": sample_s, "errs": []}
    try:
        import shutil
        du = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        out["disk_free"], out["disk_total"] = float(du.free), float(du.total)
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("disk: %s" % str(e)[:80])
    try:
        out["reboot"], out["reboot_why"] = reboot_pending()
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("restart check: %s" % str(e)[:80])
    try:
        k, ct, wt = _w32()
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("Windows calls: %s" % str(e)[:80])
        return out
    try:
        class _MS(ct.Structure):
            _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ct.c_ulonglong),
                        ("ullAvailPhys", ct.c_ulonglong), ("ullTotalPageFile", ct.c_ulonglong),
                        ("ullAvailPageFile", ct.c_ulonglong), ("ullTotalVirtual", ct.c_ulonglong),
                        ("ullAvailVirtual", ct.c_ulonglong), ("ullAvailExtendedVirtual", ct.c_ulonglong)]
        ms = _MS()
        ms.dwLength = ct.sizeof(_MS)
        if not k.GlobalMemoryStatusEx(ct.byref(ms)):
            raise OSError("GlobalMemoryStatusEx failed (%d)" % ct.get_last_error())
        out.update(mem_total=float(ms.ullTotalPhys), mem_avail=float(ms.ullAvailPhys), mem_load=int(ms.dwMemoryLoad),
                   commit=float(ms.ullTotalPageFile - ms.ullAvailPageFile), commit_limit=float(ms.ullTotalPageFile))
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("memory: %s" % str(e)[:80])
    try:
        out["uptime_s"] = k.GetTickCount64() / 1000.0
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("uptime: %s" % str(e)[:80])

    def sys_times():
        i, kk, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        if not k.GetSystemTimes(ct.byref(i), ct.byref(kk), ct.byref(u)):
            raise OSError("GetSystemTimes failed (%d)" % ct.get_last_error())
        return _ft(i), _ft(kk) + _ft(u)                         # kernel time includes the idle time

    def proc_times(hs):
        tot = {}
        for pid, h in hs.items():
            c, e, kk, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
            if k.GetProcessTimes(h, ct.byref(c), ct.byref(e), ct.byref(kk), ct.byref(u)):
                tot[pid] = _ft(kk) + _ft(u)
        return tot
    hs = {}
    try:
        try:
            hs = _python_handles(k, ct, wt)
        except Exception as e:                                  # noqa: BLE001
            out["errs"].append("process list: %s" % str(e)[:80])
        idle0, all0 = sys_times()
        p0 = proc_times(hs)
        time.sleep(max(0.05, float(sample_s)))
        idle1, all1 = sys_times()
        p1 = proc_times(hs)
        d_all = all1 - all0
        if d_all > 0:
            out["cpu"] = max(0.0, min(100.0, 100.0 * (d_all - (idle1 - idle0)) / d_all))
            if hs:
                out["py_cpu"] = max(0.0, min(100.0, 100.0 * sum(p1[p] - p0[p] for p in p1 if p in p0) / d_all))
        if hs:
            class _PMC(ct.Structure):
                _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ct.c_size_t),
                            ("WorkingSetSize", ct.c_size_t), ("QuotaPeakPagedPoolUsage", ct.c_size_t),
                            ("QuotaPagedPoolUsage", ct.c_size_t), ("QuotaPeakNonPagedPoolUsage", ct.c_size_t),
                            ("QuotaNonPagedPoolUsage", ct.c_size_t), ("PagefileUsage", ct.c_size_t),
                            ("PeakPagefileUsage", ct.c_size_t)]
            mem, seen = 0, 0
            for h in hs.values():
                pm = _PMC()
                pm.cb = ct.sizeof(_PMC)
                if k.K32GetProcessMemoryInfo(h, ct.byref(pm), pm.cb):
                    mem += pm.WorkingSetSize
                    seen += 1
            out["py_n"] = len(hs)
            out["py_mem"] = float(mem) if seen else None
        elif not out["errs"]:
            out["py_n"] = 0
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("CPU: %s" % str(e)[:80])
    finally:
        for h in hs.values():
            try:
                k.CloseHandle(h)
            except Exception:                                   # noqa: BLE001
                pass
    return out


# ---- /server: the time to Kalshi -----------------------------------------------------------------------------------
_PING = {}


def kalshi_connect(host=KALSHI_HOST, port=443, tries=KALSHI_PING_TRIES, timeout=2.0):
    """A bare TCP connect to Kalshi's API, `tries` times: the handshake only (no TLS, no request), so it costs no
    Kalshi rate limit. {"ms": [each connect], "ip", "dns_ms", "err", "t"}."""
    import socket
    out = {"host": host, "ms": [], "ip": None, "dns_ms": None, "err": None, "t": time.time()}
    try:
        t0 = time.perf_counter()
        ai = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        out["dns_ms"] = (time.perf_counter() - t0) * 1000.0
        addr = ai[0][4]
        out["ip"] = addr[0]
    except Exception as e:                                      # noqa: BLE001
        out["err"] = "name lookup failed (%s)" % (str(e)[:60] or type(e).__name__)
        return out
    for _ in range(tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            t0 = time.perf_counter()
            s.connect(addr)
            out["ms"].append((time.perf_counter() - t0) * 1000.0)
        except Exception as e:                                  # noqa: BLE001
            out["err"] = "connect failed (%s)" % (str(e)[:60] or type(e).__name__)
        finally:
            s.close()
    return out


def kalshi_ping(max_age_s=KALSHI_PING_TTL_S):
    """kalshi_connect, at most once every `max_age_s` seconds (the last answer in between)."""
    hit = _PING.get("res")
    if hit and time.time() - hit["t"] < max_age_s:
        return hit
    _PING["res"] = kalshi_connect()
    return _PING["res"]


# ---- /server: the AWS bill, signed here --------------------------------------------------------------------------
def sigv4_sign(method, url, region, service, key_id, secret, body=b"", headers=None, token=None, amz_date=None,
               sign_body=False):
    """AWS Signature Version 4 with hashlib and hmac only (no boto3 on the server). Returns (the headers to send,
    the signature): every header given, plus host, x-amz-date, x-amz-security-token (a role's session token) and,
    with sign_body, x-amz-content-sha256 -- all of them signed -- and Authorization. The self-test checks it against
    AWS's own published test vectors."""
    import hashlib
    import hmac
    u = urllib.parse.urlsplit(url)
    amz_date = amz_date or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    day = amz_date[:8]
    body = body or b""
    h = {}
    for k, v in (headers or {}).items():
        h[str(k).lower().strip()] = " ".join(str(v).split())
    h.setdefault("host", u.netloc)
    h["x-amz-date"] = amz_date
    if token:
        h["x-amz-security-token"] = token
    payload = hashlib.sha256(body).hexdigest()
    if sign_body:
        h["x-amz-content-sha256"] = payload
    q = sorted((urllib.parse.quote(k, safe="-_.~"), urllib.parse.quote(v, safe="-_.~"))
               for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True))
    names = sorted(h)
    creq = "\n".join([method.upper(), urllib.parse.quote(u.path or "/", safe="/-_.~"),
                      "&".join("%s=%s" % kv for kv in q), "".join("%s:%s\n" % (n, h[n]) for n in names),
                      ";".join(names), payload])
    scope = "%s/%s/%s/aws4_request" % (day, region, service)
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(creq.encode("utf-8")).hexdigest()])
    key = ("AWS4" + secret).encode("utf-8")
    for part in (day, region, service, "aws4_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(key, sts.encode("utf-8"), hashlib.sha256).hexdigest()
    h["authorization"] = "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
        key_id, scope, ";".join(names), sig)
    return h, sig


def _aws_http(method, url, headers=None, body=None, timeout=AWS_API_TIMEOUT_S):
    """(status, bytes) of one HTTP request, never through a proxy (the metadata address must not leave the machine).
    An HTTP error status is returned, not raised; a network failure raises."""
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except Exception:                                       # noqa: BLE001
            return e.code, b""


_AWS = {}


def aws_role_creds(http=None, now=None):
    """(keys, None) or (None, why in plain words): the IAM role's short-lived keys from the EC2 metadata service
    (IMDSv2: a token, the role's name, its keys; the account from the instance's identity document), kept until
    AWS_CREDS_SKEW_S before they expire. No role / no metadata service is remembered for AWS_NOT_CONNECTED_TTL_S."""
    http = http or _aws_http
    now = time.time() if now is None else float(now)
    c = _AWS.get("creds")
    if c and c["exp"] - AWS_CREDS_SKEW_S > now:
        return c["keys"], None
    nc = _AWS.get("nocreds")
    if nc and 0 <= now - nc["t"] < AWS_NOT_CONNECTED_TTL_S:
        return None, nc["why"]
    why = None
    try:
        st, tok = http("PUT", AWS_IMDS + "/latest/api/token", {"X-aws-ec2-metadata-token-ttl-seconds": "300"}, b"",
                       AWS_IMDS_TIMEOUT_S)
        if st != 200 or not tok:
            why = "no EC2 metadata service answered (HTTP %s)" % st
        else:
            hd = {"X-aws-ec2-metadata-token": tok.decode("ascii", "replace").strip()}
            st, names = http("GET", AWS_IMDS + "/latest/meta-data/iam/security-credentials/", hd, None,
                             AWS_IMDS_TIMEOUT_S)
            role = (names or b"").decode("utf-8", "replace").split()[0] if st == 200 and (names or b"").strip() else None
            if st == 404 or (st == 200 and not role):
                why = "no IAM role on the server yet"
            elif st != 200:
                why = "the metadata service gave HTTP %s for the role" % st
            else:
                st, raw = http("GET", AWS_IMDS + "/latest/meta-data/iam/security-credentials/" + role, hd, None,
                               AWS_IMDS_TIMEOUT_S)
                d = json.loads((raw or b"{}").decode("utf-8", "replace")) if st == 200 else {}
                if not isinstance(d, dict) or d.get("Code") != "Success" or not d.get("AccessKeyId"):
                    why = "the role %s gave no keys (HTTP %s, %s)" % (role, st, (d or {}).get("Code") if isinstance(
                        d, dict) else "unreadable")
                else:
                    acct = None
                    try:
                        st2, doc = http("GET", AWS_IMDS + "/latest/dynamic/instance-identity/document", hd, None,
                                        AWS_IMDS_TIMEOUT_S)
                        if st2 == 200:
                            acct = (json.loads(doc.decode("utf-8", "replace")) or {}).get("accountId")
                    except Exception:                           # noqa: BLE001
                        acct = None
                    keys = {"key": d["AccessKeyId"], "secret": d.get("SecretAccessKey") or "", "token": d.get("Token"),
                            "role": role, "account": acct or AWS_ACCOUNT_ID}
                    exp = pindesk.parse_t(d.get("Expiration"))
                    _AWS["creds"] = {"keys": keys, "exp": exp if exp else now + 600}
                    _AWS.pop("nocreds", None)
                    return keys, None
    except Exception as e:                                      # noqa: BLE001
        why = "no EC2 metadata service reachable (%s)" % (type(e).__name__)
    _AWS["nocreds"] = {"t": now, "why": why}
    return None, why


def _aws_call(host, service, target, payload, keys, http):
    """One signed AWS JSON 1.1 call: (the reply dict, None) or (None, why)."""
    body = json.dumps(payload).encode("utf-8")
    url = "https://%s/" % host
    hd, _sig = sigv4_sign("POST", url, "us-east-1", service, keys["key"], keys["secret"], body,
                          {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": target}, keys.get("token"))
    try:
        st, raw = http("POST", url, hd, body, AWS_API_TIMEOUT_S)
    except Exception as e:                                      # noqa: BLE001
        return None, "could not reach AWS (%s)" % (str(e)[:60] or type(e).__name__)
    try:
        d = json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
    except ValueError:
        d = None
    if st == 200 and isinstance(d, dict):
        return d, None
    kind = str((d or {}).get("__type") or "").split("#")[-1] if isinstance(d, dict) else ""
    msg = str((d or {}).get("Message") or (d or {}).get("message") or "") if isinstance(d, dict) else ""
    if kind in ("ExpiredTokenException", "UnrecognizedClientException", "InvalidClientTokenId"):
        _AWS.pop("creds", None)                                 # the next read fetches new role keys
    return None, ("%s (HTTP %s)%s" % (kind or "error", st, (": " + msg[:110]) if msg else "")).strip()


def _aws_budget_rows(d):
    out = []
    for b in (d or {}).get("Budgets") or []:
        if not isinstance(b, dict):
            continue
        cs = b.get("CalculatedSpend") or {}
        lim = b.get("BudgetLimit") or {}
        out.append({"name": b.get("BudgetName"), "type": b.get("BudgetType"), "period": b.get("TimeUnit"),
                    "limit": _fnum(lim.get("Amount")), "unit": lim.get("Unit") or "USD",
                    "actual": _fnum((cs.get("ActualSpend") or {}).get("Amount")),
                    "forecast": _fnum((cs.get("ForecastedSpend") or {}).get("Amount")),
                    "updated": _fnum(b.get("LastUpdatedTime"))})
    return out


def _aws_ce_rows(d):
    days, svc, est = {}, {}, False
    for r in (d or {}).get("ResultsByTime") or []:
        day = (r.get("TimePeriod") or {}).get("Start")
        est = est or bool(r.get("Estimated"))
        groups = r.get("Groups") or []
        for g in groups:
            name = (g.get("Keys") or ["?"])[0]
            v = _fnum(((g.get("Metrics") or {}).get("UnblendedCost") or {}).get("Amount")) or 0.0
            days[day] = days.get(day, 0.0) + v
            svc[name] = svc.get(name, 0.0) + v
        if not groups:
            v = _fnum(((r.get("Total") or {}).get("UnblendedCost") or {}).get("Amount"))
            if v is not None:
                days[day] = days.get(day, 0.0) + v
    return {"days": days, "services": svc, "month": sum(days.values()), "estimated": est,
            "more": bool((d or {}).get("NextPageToken"))}


def _aws_cached(name, now, ttl, read):
    """One AWS read through its cache: re-read after `ttl` (AWS_ERR_TTL_S after a failure); a failed read keeps the last
    good answer, and says it failed. {"res", "res_t" (when that answer was read), "err", "t"}."""
    c = _AWS.get(name)
    if c is None or not (0 <= now - c["t"] < (ttl if c["err"] is None else AWS_ERR_TTL_S)):
        res, err = read()
        prev = c or {}
        c = _AWS[name] = {"t": now, "err": err, "res": res if res is not None else prev.get("res"),
                          "res_t": now if res is not None else prev.get("res_t")}
    return c


def aws_cost(now=None, http=None):
    """Everything /server says about the AWS bill. Never raises: {"connected", "why" (when not), "role", "budget"
    (DescribeBudgets' rows), "budget_err", "budget_t", "ce" (Cost Explorer: this month by day and by service),
    "ce_err", "ce_t"}."""
    now = time.time() if now is None else float(now)
    http = http or _aws_http
    out = {"connected": False, "why": None, "role": None, "budget": None, "budget_err": None, "budget_t": None,
           "ce": None, "ce_err": None, "ce_t": None}
    try:
        keys, why = aws_role_creds(http, now)
        if keys is None:
            out["why"] = why
            return out
        out.update(connected=True, role=keys.get("role"))

        def budgets():
            d, err = _aws_call(AWS_BUDGETS_HOST, "budgets", "AWSBudgetServiceGateway.DescribeBudgets",
                               {"AccountId": keys["account"], "MaxResults": 20}, keys, http)
            return (_aws_budget_rows(d) if d is not None else None), err

        def ce():
            t = time.gmtime(now)
            d, err = _aws_call(AWS_CE_HOST, "ce", "AWSInsightsIndexService.GetCostAndUsage", {
                "TimePeriod": {"Start": "%04d-%02d-01" % (t.tm_year, t.tm_mon),
                               "End": time.strftime("%Y-%m-%d", time.gmtime(now + 86400))},
                "Granularity": "DAILY", "Metrics": ["UnblendedCost"],
                "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]}, keys, http)
            return (_aws_ce_rows(d) if d is not None else None), err
        b = _aws_cached("budget", now, AWS_BUDGET_TTL_S, budgets)
        out.update(budget=b["res"], budget_err=b["err"], budget_t=b["res_t"])
        c = _aws_cached("ce", now, AWS_CE_TTL_S, ce)
        out.update(ce=c["res"], ce_err=c["err"], ce_t=c["res_t"])
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        out["why"] = out["why"] or "the AWS read failed (%s)" % str(e)[:80]
    return out


def aws_estimate(now):
    """The bill worked from the price list (the AWS_* constants), shown as an ESTIMATE wherever it appears: a month, a
    day, this month so far (since the server started, or the month began) and the whole of this month."""
    hourly = AWS_EC2_HOURLY + AWS_IPV4_HOURLY + AWS_DISK_MONTH / AWS_HOURS_MONTH
    t = time.gmtime(now)
    m0 = calendar.timegm((t.tm_year, t.tm_mon, 1, 0, 0, 0))
    m1 = calendar.timegm((t.tm_year + (1 if t.tm_mon == 12 else 0), t.tm_mon % 12 + 1, 1, 0, 0, 0))
    start = max(m0, AWS_BILLED_FROM_EPOCH)
    so_far = hourly * max(0.0, now - start) / 3600.0
    return {"hourly": hourly, "month": hourly * AWS_HOURS_MONTH, "day": hourly * 24.0, "since": start,
            "so_far": so_far, "this_month": so_far + hourly * max(0.0, m1 - max(now, start)) / 3600.0,
            "month_name": time.strftime("%B", t), "ec2_month": AWS_EC2_HOURLY * AWS_HOURS_MONTH,
            "ipv4_month": AWS_IPV4_HOURLY * AWS_HOURS_MONTH, "disk_month": AWS_DISK_MONTH}


SERVER_HELP = Html("""🖥 <b>/server help: connect the AWS cost</b> (once, about 3 minutes, in the AWS console)

/server reads this month's spending from AWS itself, with no stored keys: the server gets a read-only role, and the phone link asks the server's own metadata service for short-lived keys. Until then it shows the price-list estimate.

<b>1. The policy</b>: IAM → Policies → Create policy → JSON, replace everything with:
<code>{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["budgets:ViewBudget","ce:GetCostAndUsage"],"Resource":"*"}]}</code>
→ Next → Policy name <code>kals-server-billing-read</code> → Create policy.
<b>2. The role</b>: IAM → Roles → Create role → Trusted entity type: AWS service, Use case: EC2 → Next → tick <code>kals-server-billing-read</code> → Next → Role name <code>kals-server-billing</code> → Create role.
<b>3. Give it to the server</b>: EC2 → Instances → tick <code>kals-bot</code> → Actions → Security → Modify IAM role → pick <code>kals-server-billing</code> → Update IAM role.

Within 5 minutes /server shows "This month so far" from AWS. Nothing restarts.
If it says access denied: sign in as the root user → your name (top right) → Account → "IAM user and role access to Billing information" → Edit → Activate. If Cost Explorer says it is not enabled: open Billing → Cost Explorer once (AWS turns it on; its numbers show within a day).

What the role can do: read the budget and the cost totals, nothing else. It cannot start, stop or change anything, and the server holds no AWS key on disk.
<i>budgets:ViewBudget is the permission behind AWS's DescribeBudgets call (there is no separate budgets:DescribeBudgets permission). DescribeBudgets is free and is read at most once an hour; Cost Explorer costs $0.01 a read, so it is read at most every 6 hours and only when /server is asked (at most about $1.20 a month).</i>""")


def _server_pots_lines(pots, now, active=None):
    """/server's funds: every pot from botstats' cache (cached_pots: the last read /bots, /funds or a chart made)."""
    if not isinstance(pots, dict) or pots.get("err") or not pots.get("pots"):
        return ["💰 <b>Funds</b>: botstats' cache could not be read%s. /funds reads every account."
                % ((" (%s)" % esc(pots.get("err"))) if isinstance(pots, dict) and pots.get("err") else "")], None
    ps = pots["pots"]
    total = pots.get("total")
    L = ["💰 <b>Funds: all pots %s</b> <i>(Kalshi, as of %s, %s ago: the last read /bots, /funds or a chart made; "
         "nothing is read here)</i>" % (esc(dollars(total)) if total is not None else "?", esc(_et_at(pots.get("t"))),
                                        esc(_span_words(now - pots["t"])) if pots.get("t") else "?")]
    rows = [("Pot", "Total", "Share", "Bets")]
    notes = []
    for sub in sorted(ps, key=lambda s: int(s) if str(s).isdigit() else 99):
        p = ps[sub]
        name = (funds_short(int(sub), active) or "pot %s" % sub) if str(sub).isdigit() else str(sub)
        v = p.get("value")
        if v is None:
            notes.append("%s: %s%s" % (name, p.get("why") or "not read",
                                       ("; its cash alone %s" % dollars(p["cash"])) if p.get("cash") is not None else ""))
        rows.append((name, "{:,.2f}".format(v) if v is not None else "?",
                     pct_of(v, total) if v is not None and total else "-",
                     "{:,.2f}".format(p["open"]) if p.get("open") else ("0" if p.get("open") == 0 else "?")))
    L.append(pre(table(rows)))
    for x in notes:
        L.append("⚠️ " + esc(x))
    L.append(i_("Total = cash in every pool + what the open bets cost; Share = of all pots. /funds reads them fresh, "
                "with each pool, bet sizes and the last 7 days."))
    return L, total


def _server_aws_lines(aws, est, total, now):
    L = ["☁️ <b>AWS cost</b>"]

    def of_pots(x):
        r = ret(x, total, 2) if total else ""
        return (" = %s of all pots" % r.lstrip("+")) if r else ""
    b = None
    if aws.get("connected") and aws.get("budget"):
        rows = aws["budget"]
        b = next((r for r in rows if r["type"] == "COST" and r["period"] == "MONTHLY"), rows[0])
    if not aws.get("connected"):
        L.append("AWS cost: <b>not connected yet</b> (needs the read-only billing role on the server, see "
                 "<code>/server help</code>)")
        if aws.get("why"):
            L.append(i_("(%s)" % aws["why"]))
    else:
        if b is not None:
            lim = b["limit"]
            L.append("This month so far: <b>%s</b>%s%s" % (
                esc(dollars(b["actual"])), (" of the %s budget (%s)" % (esc(dollars(lim)), pct_of(b["actual"], lim)))
                if lim and b["actual"] is not None else "", esc(of_pots(b["actual"])) if b["actual"] is not None else ""))
            L.append("AWS's forecast for %s: %s" % (
                esc(est["month_name"]), ("<b>%s</b>%s" % (esc(dollars(b["forecast"])), esc(of_pots(b["forecast"]))))
                if b["forecast"] is not None else "none yet (AWS needs some weeks of history first)"))
            L.append(i_("AWS Budgets, budget '%s'%s; AWS updates it a few times a day%s" % (
                b["name"] or "?", (", as of %s" % _et_at(b["updated"])) if b["updated"] else "",
                (" · %d budgets on the account" % len(aws["budget"])) if len(aws["budget"]) > 1 else "")))
        elif aws.get("budget") == []:
            L.append("AWS Budgets: no budget on the account yet.")
        if aws.get("budget_err"):
            L.append("⚠️ Budgets read: %s" % esc(aws["budget_err"]))
        ce = aws.get("ce")
        if ce:
            yday = time.strftime("%Y-%m-%d", time.gmtime(now - 86400))
            top = sorted(ce["services"].items(), key=lambda kv: -kv[1])
            L.append("Cost Explorer: this month <b>%s</b>%s · yesterday (UTC) %s%s" % (
                esc(dollars(ce["month"])), esc(of_pots(ce["month"])), esc(dollars(ce["days"].get(yday, 0.0))),
                " · AWS's figures are still estimated" if ce.get("estimated") else ""))
            if top:
                L.append("By service: %s" % esc(", ".join("%s %s" % (AWS_SERVICE_SHORT.get(k, k), dollars(v))
                                                         for k, v in top[:5] if abs(v) >= 0.005) or "nothing yet"))
            if aws.get("ce_t"):
                L.append(i_("Cost Explorer read %s ($0.01 a read: at most every 6 hours)" % _et_at(aws["ce_t"])))
        if aws.get("ce_err"):
            L.append("⚠️ Cost Explorer read: %s" % esc(aws["ce_err"]))
    L.append("Estimate from the price list: about <b>%s a month</b> (%s a day)%s: Windows %s %s an hour (%s), %d GB "
             "disk %s, public IPv4 %s; data out not counted (small; the first 100 GB a month are free)." % (
                 esc(dollars(est["month"])), esc(dollars(est["day"])), esc(of_pots(est["month"])), AWS_INSTANCE_TYPE,
                 esc(dollars(AWS_EC2_HOURLY)), esc(dollars(est["ec2_month"])), AWS_DISK_GB, esc(dollars(est["disk_month"])),
                 esc(dollars(est["ipv4_month"]))))
    L.append("%s so far, since %s: about %s · all of %s: about %s (estimates) · budget %s a month." % (
        esc(est["month_name"]), esc(_et_at(est["since"])) + (" (the server started)" if est["since"] == AWS_BILLED_FROM_EPOCH
                                                            else ""),
        esc(dollars(est["so_far"])), esc(est["month_name"]), esc(dollars(est["this_month"])),
        esc(dollars(b["limit"] if b is not None and b.get("limit") else AWS_BUDGET_USD))))
    return L


def server_html(m, ping, pots, aws, est, now, pin_home=None, pin_srv=None, active=None):
    """/server's screen: the machine (machine_read), the time to Kalshi (kalshi_ping), every pot's money (botstats'
    cache), the AWS bill (aws_cost, aws_estimate). Each part says what it could not read; none stops the others."""
    best = min(ping["ms"]) if ping and ping.get("ms") else None
    used = (m["mem_total"] - m["mem_avail"]) if m.get("mem_total") is not None and m.get("mem_avail") is not None else None
    head = ["CPU %s" % _pct0(m.get("cpu")), "memory %s used" % _pct0(m.get("mem_load")),
            "disk %s free" % _gb(m.get("disk_free")), "Kalshi %s" % (_ms(best) if best is not None else "?")]
    L = ["🖥 <b>SERVER: %s</b>" % esc(" · ".join(head)),
         i_("AWS EC2 in Ohio (%s) · %s: 2 vCPU, 4 GB, Windows Server 2022, %d GB disk · %s, %s · this machine: %s · %s"
            % (AWS_AZ, AWS_INSTANCE_TYPE, AWS_DISK_GB, AWS_INSTANCE_NAME, AWS_ELASTIC_IP, m.get("host") or "?",
               _et_at(now)))]
    warn = []
    if m.get("cpu") is not None and m["cpu"] >= SERVER_WARN_CPU:
        warn.append("CPU is busy: %s" % _pct0(m["cpu"]))
    if m.get("mem_load") is not None and m["mem_load"] >= SERVER_WARN_MEM:
        warn.append("memory nearly full: %d%% used" % m["mem_load"])
    if m.get("disk_free") is not None and m["disk_free"] / 1e9 < SERVER_WARN_DISK_GB:
        warn.append("disk under %d GB free" % SERVER_WARN_DISK_GB)
    if m.get("reboot"):
        warn.append("%s waits for a restart" % (m.get("reboot_why") or "Windows"))
    if ping and ping.get("err"):
        warn.append("Kalshi: %s" % ping["err"])
    for w in warn:
        L.append("⚠️ <b>%s</b>" % esc(w))
    L.append("")
    L.append("⚙️ <b>Machine</b>")
    rows = [("CPU now", "%s (%s cores, %.1f s)" % (_pct0(m.get("cpu")), m.get("ncpu") or "?", _f(m.get("sample_s")))),
            ("  python", "%s · %s" % (_pct0(m.get("py_cpu")), ("%d process%s" % (m["py_n"], "" if m["py_n"] == 1 else "es"))
                                      if m.get("py_n") is not None else "? processes")),
            ("Memory", "%s of %s (%s)" % (_gb(used), _gb(m.get("mem_total")), _pct0(m.get("mem_load")))),
            ("  free", _gb(m.get("mem_avail"))),
            ("  python", _gb(m.get("py_mem"))),
            ("Committed", "%s of %s" % (_gb(m.get("commit")), _gb(m.get("commit_limit")))),
            ("Disk C:", "%s free of %s" % (_gb(m.get("disk_free")), _gb(m.get("disk_total"), 0))),
            ("Up", _span_words(m["uptime_s"]) if m.get("uptime_s") is not None else "?")]
    L.append(pre(table(rows, "ll")))
    boot = (now - m["uptime_s"]) if m.get("uptime_s") is not None else None
    L.append("Last boot: %s · Windows Update: %s" % (
        esc(_et_at(boot)), "<b>a restart is waiting</b> (%s)" % esc(m.get("reboot_why") or "?") if m.get("reboot")
        else ("no restart waiting" if m.get("reboot") is False else "could not tell (%s)" % esc(m.get("reboot_why") or "?"))))
    if m.get("errs"):
        L.append(i_("Could not read: %s" % "; ".join(m["errs"])))
    L.append(i_("python = every python process (the bots, the recorders and this phone link): its share of the whole "
                "machine and the memory it holds."))
    L.append("")
    if ping and ping.get("ms"):
        L.append("⚡ <b>Kalshi: %s</b> to connect (best of %d: %s; name lookup %s), checked %s" % (
            esc(_ms(best)), len(ping["ms"]), esc(", ".join(_ms(x) for x in ping["ms"])), esc(_ms(ping.get("dns_ms"))),
            esc(_et_at(ping.get("t"), False))))
    else:
        L.append("⚡ <b>Kalshi: could not connect</b> (%s)" % esc((ping or {}).get("err") or "not checked"))
    if pin_srv and pin_srv.get("lat_n"):
        L.append("The pin bot's own orders here: median <b>%s</b> send to answer, %s got nothing%s · /speed" % (
            esc(_ms(pin_srv["med_ms"])), pct1(pin_srv["zero"], pin_srv["n"]),
            (" (home: %s, %s)" % (esc(_ms(pin_home["med_ms"])), pct1(pin_home["zero"], pin_home["n"])))
            if pin_home and pin_home.get("lat_n") else ""))
    L.append(i_("A bare TCP connect to %s:443 (no request is sent, so no Kalshi limit is used), at most once a minute."
                % KALSHI_HOST))
    L.append("")
    fl, total = _server_pots_lines(pots, now, active)
    L += fl
    L.append("")
    L += _server_aws_lines(aws or {}, est, total, now)
    L.append("")
    L.append(i_("/speed: the bots' orders, server against home · /funds: every account read fresh · /server help: "
                "connect the AWS cost"))
    return Html("\n".join(L))


class Phone:
    def __init__(self, cfg, transport, ledger=None, health_fn=None, cfg_path=CONFIG, now_fn=None,
                 procs_fn=None, versions_path=None, race30_epoch=None):
        self.cfg = cfg
        self.cfg_path = cfg_path
        self.tg = transport
        self.ledger = ledger or Ledger()
        self.health_fn = health_fn or (lambda: pindesk.health(self.ledger))
        self.now = now_fn or time.time
        self.offset = None
        self.muted = False
        self.last_state = None
        self.last_rec = None
        self.seen_losses = None
        self.last_daily = None
        self.disk_level = 0                     # disk_alert(): 0 armed, 8 / 6 = that line already sent
        self.bars_fn = None                     # the self-test plants /bars' text
        self.busy = False
        # /stats, /race, /racestats read the process table, VERSIONS.md and
        # the v-race30 clock; the self-test plants all three.
        self.procs_fn = procs_fn or python_procs
        self.versions_path = versions_path or VERSIONS_MD
        self.race30_epoch = race30_epoch or RACE30_EPOCH
        # /bots /pin /forecaster /ladder and /race's money windows read Kalshi
        # through botstats. None = botstats' own: kauth.get (GET only, 60 s
        # cache) and its own process-table read (about 1.5 s natively; the
        # WMI read behind procs_fn now takes 28-35 s). The self-test plants
        # a fake Kalshi and a process table here.
        self.bs_getter = None
        self.bs_procs = None
        # /funds reads Kalshi through this getter; None = botstats.default_getter() (kauth.get, GET only).
        # The self-test plants a fake Kalshi here.
        self.funds_getter = None
        # CHARTS (2026-10-18): a picture after the words, drawn on one background thread (chart_after).
        # Off unless main() turns them on, so every self-test Phone sends words only unless it asks.
        self.charts_on = False
        self.chart_fn = None                    # None = tgcharts.build; the self-test plants its own
        self.chart_stale_s = None               # None = tgcharts.STALE_S
        self._chart_q = None
        self._bars_d = None                     # /bars' gathered numbers, for its picture
        self._resend = []                       # sends the connection dropped (say -> resend_tick)
        self._resend_lock = threading.Lock()
        # /server's readings (2026-10-27); None = the real ones: machine_read, kalshi_ping, botstats.cached_pots, and
        # _aws_http for the metadata service and AWS. The self-test plants all four.
        self.machine_fn = None
        self.ping_fn = None
        self.pots_fn = None
        self.aws_http = None

    # ---- helpers ----
    @property
    def chat_id(self):
        return self.cfg.get("chat_id")

    def active(self):
        """The bots shown now (v-tg-active, 2026-10-30): botstats.active_bots -- a live copy running and no stop file; the
        pin bot always. Fail-safe: any error shows every bot (a command never dies on it)."""
        bs = _bs()
        try:
            return tuple(bs.active_bots(procs=self.bs_procs))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return tuple(bs.BOTS)

    def text_hidden(self, name):
        """The answer to a paused or retired bot's own command (/race, /fc, /wx ... while it is not active)."""
        bs = _bs()
        label = bs.SPEC[name]["label"] if name in bs.SPEC else name
        why = "its stop file is set" if bs.stop_set(name) else "no live copy of it is running"
        return Html("⏸ <b>%s is not running now</b> (%s), so it is left off every page and /help.\n%s\n%s" % (
            esc(label), esc(why), i_("It comes back by itself -- here, in /help, /bots and the rest -- once it runs "
                                     "again with no stop file. Its past money stays in every total, on the 'earlier bots' "
                                     "line of /bots."),
            i_("The bots running now: %s" % " ".join(BOT_CMD_OF.get(b, "/" + b) for b in self.active()))))

    def save_cfg(self):
        try:
            _paths.check_write(self.cfg_path)        # v-tg-rebuild step 2: never C:\kals under KALS_TESTING=1
            with open(self.cfg_path, "w", encoding="utf-8") as fh:
                json.dump(self.cfg, fh, indent=2)
        except OSError as e:
            log("could not save config: %s" % e)

    def say(self, text, chat_id=None):
        """Send, and LOG WHAT WAS SENT. 2026-09-23: the operator got a
        RECORDER SILENT alert and the log held no trace of it -- only
        failures were logged -- so there was no way to audit whether an
        alert had fired, which is the whole point of having alerts.
        2026-10-23: a send the CONNECTION dropped is kept and tried again
        (resend_tick) -- that night the 'DOWN -> TRADING' alert was lost
        and the operator believed the bots were still down."""
        cid = chat_id or self.chat_id
        flat = " | ".join((html_to_plain(text) if getattr(text, "is_html", False) else str(text)).splitlines())
        if cid is None:
            log("NOT SENT (no paired chat): %s" % flat[:200])
            return
        try:
            self.tg.send(cid, text)
            log("SENT: %s" % flat[:300])
        except Exception as e:                            # noqa: BLE001
            again = net_error(e)
            log("send failed: %s -- %stext was: %s" % (e, "will try again; " if again else "", flat[:200]))
            if again:
                with self._resend_lock:
                    self._resend.append({"chat": cid, "text": text, "t": self.now(), "next": time.monotonic() + RESEND_GAP_S,
                                         "flat": flat})
                    del self._resend[:-RESEND_KEEP]

    def resend_tick(self):
        """Try the sends the connection dropped again, oldest first, each RESEND_GAP_S apart, for RESEND_FOR_S.
        A late one says so first ('sent late, from 9:53 PM ET'), since its numbers are from then. Never raises."""
        now_m = time.monotonic()
        with self._resend_lock:
            due = [x for x in self._resend if x["next"] <= now_m]
        for x in due:
            if self.now() - x["t"] > RESEND_FOR_S:
                with self._resend_lock:
                    if x in self._resend:
                        self._resend.remove(x)
                log("gave up resending (over %d min old): %s" % (RESEND_FOR_S // 60, x["flat"][:150]))
                continue
            late = "⏱ Sent late -- from %s ET; the connection dropped it then." % et_str(x["t"])
            t = x["text"]
            body = Html("<i>%s</i>\n%s" % (esc(late), t)) if getattr(t, "is_html", False) else "%s\n%s" % (late, t)
            try:
                self.tg.send(x["chat"], body)
                log("SENT (late, from %s): %s" % (et_str(x["t"]), x["flat"][:250]))
                with self._resend_lock:
                    if x in self._resend:
                        self._resend.remove(x)
            except Exception as e:                        # noqa: BLE001
                x["next"] = time.monotonic() + RESEND_GAP_S
                if not net_error(e):
                    with self._resend_lock:
                        if x in self._resend:
                            self._resend.remove(x)
                log("resend failed: %s" % e)
                break                                     # the connection is still down: the rest wait too

    def summary_line(self, rows, day=None, label=""):
        s = Ledger.summary(rows)
        dep = self.ledger.deposited()
        if day:
            b0 = self.ledger.bank_at(et_day_start(day))
            r = (s["net"] / b0) if b0 else None
        else:
            r = (s["net"] / dep) if dep else None
        out = "%s %s (%s)" % (label, money(s["net"]), pct(r))
        if s["closes"]:
            out += "\n  %d closes (%d bets): %d won, %d lost (%.1f%%)" % (s["closes"], s["markets"], s["won"], s["lost"], s["loss_rate"])
        else:
            out += "\n  no settled bets"
        if day:
            fs = Ledger.fill_stats(self.ledger.fills_on(day))
            try:
                up = hours_up_et_day(day, self.now() if day == et_day(self.now()) else et_day_start(day) + 86400)
            except Exception:                            # noqa: BLE001
                up = None
            out += "\n  %d fills, %g contracts, %d lost races" % (fs["fills"], fs["contracts"], fs["zero"])
            if up:
                out += "\n  %.1f h up, %s/h" % (up, money(s["net"] / up))
        return out

    def _staked(self, net, day=None):
        """What the bets of one ET day (None = every day) cost, from Kalshi's books (the /stats source:
        cost + fees of every main-account market) -- or None when that source's money for the same window
        is not the `net` shown (then a 'return on staked' would mix two sources, so none is shown)."""
        try:
            ms = [m for m in self._markets().values() if day is None or m["day"] == day]
        except Exception:                                       # noqa: BLE001
            return None
        if not ms:
            return None
        st = window_stats(ms, {})
        return st["risked"] if abs(st["net"] - net) <= 0.011 else None

    def day_html(self, rows, day=None, label=""):
        """summary_line's numbers laid out: the money and its % (of the bank at the start of the ET day; all
        time, of the money put in) as the headline; then closes won (count and %), the return on what the
        bets cost (when Kalshi's books give the same money), fills, hours, and the day as a sparkline of the
        running total close by close. Html lines."""
        s = Ledger.summary(rows)
        if day:
            b0 = self.ledger.bank_at(et_day_start(day))
            r = (s["net"] / b0) if b0 else None
            base = ("%% of the bank = of the %s it held at the start of the ET day" % dollars(b0)) if b0 else None
            what = "of the bank"
        else:
            dep = self.ledger.deposited()
            r = (s["net"] / dep) if dep else None
            base = None
            what = ("on the %s put in" % dollars(dep)) if dep else ""
        L = ["%s <b>%s %s (%s%s)</b>" % (dot(s["net"]), esc(label), esc(usd(s["net"])), esc(pct(r)),
                                           (" " + esc(what)) if r is not None and what else "")]
        if s["closes"]:
            staked = self._staked(s["net"], day) if s["markets"] else None
            L.append("<b>%d of %d</b> closes won (<b>%s</b>), %d lost (%.1f%%) · %s%s" % (
                s["won"], s["closes"], pct_of(s["won"], s["closes"], 1), s["lost"], s["loss_rate"],
                esc(_nof(s["markets"], "bet")),
                (" · <b>%s</b> on the %s staked" % (esc(ret(s["net"], staked, 2)), esc(dollars(staked))))
                if staked else ""))
        else:
            L.append("No settled bets.")
        if day:
            fs = Ledger.fill_stats(self.ledger.fills_on(day))
            try:
                up = hours_up_et_day(day, self.now() if day == et_day(self.now()) else et_day_start(day) + 86400)
            except Exception:                            # noqa: BLE001
                up = None
            L.append("Pin bot: %s, %s contracts%s" % (            # its own orders; the coin race's are in /race
                esc(_nof(fs["fills"], "fill")), "{:,.0f}".format(fs["contracts"] or 0),
                (" · %d of %d orders filled nothing (%s)" % (fs["zero"], fs["orders"], pct_of(fs["zero"], fs["orders"])))
                if fs["orders"] else ""))
            if up:
                L.append("%.1f h up · <b>%s</b> an hour" % (up, esc(usd(s["net"] / up))))
            closes = Ledger.by_close(rows)
            if len(closes) >= 3:
                run, cum = [], 0.0
                for k in sorted(closes):
                    cum += closes[k]
                    run.append(cum)
                L.append("Close by close, the running total: <code>%s</code>" % esc(spark(run)))
        if base and r is not None:
            L.append(i_(base))
        return L

    # ---- command texts ----
    def text_status(self):
        h = self.health_fn()
        state, hl, det, _c = status_of(h)
        b = self.ledger.bank()
        dep = self.ledger.deposited()
        body, _nl, ev = det.rpartition("\n")
        if not body:
            body, ev = ev, ""
        lines = ["%s <b>%s</b>" % (state_dot(state), esc(hl)), esc(body)]
        if ev:
            lines.append(i_(ev))
        if b:
            # 2026-10-26: was 'Bank $1,340.77 (+19.34% on the $1,123.46 put in)' -- the main account's bank against
            # the money put into EVERY pot (about $1,024 of it now sits in the other bots' pots), so the % read low
            lines.append("")
            lines.append("🏦 <b>Main account %s</b> (%s) · bet size %g contracts" % (
                esc(dollars(b["bank"])), esc(main_words(self.active())), b.get("size") or 0))
            try:
                a = self._bs_get("all")
                at, allc = a["total"]["all_time"], a["balances"].get("all")
                if allc is not None:
                    lines.append("💼 All pots %s%s · /bots" % (esc(dollars(allc)), (
                        " · all time <b>%s</b> (<b>%s</b> on the %s put in)" % (
                            esc(usd(at["money"])), esc(_bs().pot_pct_txt(at["pot_pct"])), esc(dollars(at["pot"]))))
                        if at.get("pot_pct") is not None and at.get("pot") else ""))
            except Exception:                                   # noqa: BLE001
                log(traceback.format_exc())
        today = et_day(self.now())
        lines.append("")
        lines += self.day_html(self.ledger.settled_on(today), today,
                               ("%s today" % main_shared(self.active()).capitalize()) if main_sharers(self.active())
                               else "Main account today")
        try:
            t_ = self._bs_get("all")["total"]["today"]
            if t_["markets"]:
                lines.append("🤖 All bots today <b>%s</b>%s · /today" % (esc(usd(t_["money"])), (
                    " (<b>%s</b> of all pots)" % esc(_bs().pot_pct_txt(t_["pot_pct"]))) if t_.get("pot_pct") is not None else ""))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
        opn = pinflat.positions(self.ledger.newest_rows) if h["alive"] else {}
        if opn:
            lines.append("")
            lines.append("📂 <b>Pin bot open:</b> " + esc(", ".join("%s %s closes %s" % (coin(t), "x%g" % self.ledger.contracts_for(t), close_et(t)) for t in opn)))
        wd = h.get("watchdog_s")
        rec = "both writing" if (h.get("kalshi_ok") and h.get("feeds_ok")) else "CHECK RECORDERS"
        lines.append("")
        lines.append("🖥 Watchdog %s · recorders %s · disk %.1f GB free" % (
            ("ok, %ds ago" % wd) if wd is not None and wd < 120 else "<b>NOT RUNNING</b>",
            esc(rec) if rec == "both writing" else "<b>%s</b>" % esc(rec), h.get("disk_gb") or 0))
        return Html("\n".join(lines))

    def _all_bots_day(self, day, label):
        """/today and /yesterday's top: EVERY bot's money that ET day from Kalshi's books (botstats.all_bots, the
        /bots source). The operator, 2026-10-23: "/today doesn't show the right total it says 11.22 right now it's
        really 24.85" -- the old headline was the main account only. 2026-10-26: "/yesterday doesn't look good or
        show % of bank return" -- now the headline carries the % of all pots, a bot-by-bot table carries each
        bot's % of its own bank and its return on the bets, and the averages carry their % too. [] when the day
        is neither today nor yesterday; one warning line when botstats fails."""
        try:
            a = self._bs_get("all")
        except Exception:                                        # noqa: BLE001
            log(traceback.format_exc())
            return ["❔ <b>All bots %s: could not be read</b> -- below is the main account only" % esc(label.lower())]
        bs = _bs()
        today = a["today_et"]
        key = "today" if day == today else ("yesterday" if day == bs.shift_day(today, -1) else None)
        if key is None:
            return []
        w = a["total"][key]
        if w["partial"] and not w["markets"]:
            L = ["❔ <b>All bots %s: unknown -- Kalshi could not be read</b>" % esc(label.lower())]
        else:
            L = [bs_headline(w, "of all pots", "All bots", when=label.lower())]
        L.append(i_("%s ET%s · every pot, Kalshi's books" % (
            _day_long(day), (" · %d of %d markets won" % (w["won"], w["markets"])) if w["markets"] else "")))
        if key == "today" and not w["partial"]:
            pace = self._pace_line(w["money"], day, w.get("pot"))
            if pace:
                L.append(pace)
        if w["partial"] and w["markets"]:
            L.append("⚠️ PARTIAL: leaves out %s (Kalshi could not be read)" % esc(", ".join(w["missing"])))
        tbl = bots_window_table(a, key)
        if tbl:
            L += ["", "📊 <b>By bot</b>"] + tbl
        avg, n = all_bots_avg_before(a, day)
        base = w.get("pot")

        def share(x):
            return (" (%s of all pots)" % bs.pot_pct_txt(100.0 * x / base)) if base else ""
        more = []
        if key == "today" and a["total"]["yesterday"]["markets"]:
            y = a["total"]["yesterday"]
            more.append("yesterday %s%s" % (usd(y["money"]), (" (%s)" % bs.pot_pct_txt(y["pot_pct"]))
                                             if y.get("pot_pct") is not None else ""))
        if avg is not None:
            if key == "today":
                more.append("%d-day average %s a day%s" % (n, usd(avg), share(avg)))
            elif w["markets"]:
                gap = w["money"] - avg
                more.append("the %d days before averaged %s a day%s, so this day was %s %s average" % (
                    n, usd(avg), share(avg), dollars(abs(gap)), "above" if gap >= 0 else "below"))
        # 2026-10-29: the 30-day average beside the 7-day one, the same rule (all_bots_avg_before: a quiet day counts $0,
        # days before the first market on any pot are left out -- so fewer than 30 only while the books are younger)
        avg30, n30 = all_bots_avg_before(a, day, bs.LONG_DAYS) if hasattr(bs, "LONG_DAYS") else (None, 0)
        if avg30 is not None and n30 > n:
            if key == "today":
                more.append("%d-day average %s a day%s" % (n30, usd(avg30), share(avg30)))
            elif w["markets"]:
                gap = w["money"] - avg30
                more.append("the %d days before averaged %s a day%s, %s %s that" % (
                    n30, usd(avg30), share(avg30), dollars(abs(gap)), "above" if gap >= 0 else "below"))
        if more:
            L.append("")
            L.append("📈 " + esc(" · ".join(more)))
        return L

    def _pace_line(self, so_far, day, base=None):
        """'📈 Ahead of pace: +$76.44 (+3.3%) so far vs +$20.10 (+0.86%) by 10:45 PM on an average day (last 7)' --
        every bot, today against the same ET clock on the days before (operator: judge 'on track' from midnight
        ET, and say 'behind' plainly); the % are of all pots at midnight (`base`). None when it cannot be worked
        out (it never costs the rest of /today)."""
        try:
            T = _tgc()
            now = self.now()
            b_, _p, rows, miss = T.all_day_markets({"now": now, "pp": sys.modules[__name__],
                                                    "bs_getter": self.bs_getter, "bs_procs": self.bs_procs})
            if miss:
                return None
            _sf, avg, n = T.by_now(rows, b_, day, now)
            if avg is None:
                return None
            ahead = so_far >= avg

            def sh(x):
                return (" (%s)" % b_.pot_pct_txt(100.0 * x / base)) if base else ""
            # 2026-10-29: the 30-day average day at the same clock after the 7-day one (ahead / behind stays the 7-day's)
            _sf30, avg30, n30 = T.by_now(rows, b_, day, now, getattr(b_, "LONG_DAYS", 0))
            more = (" · last %d: %s%s" % (n30, usd(avg30), sh(avg30))) if avg30 is not None and n30 > n else ""
            return "%s <b>%s</b>: %s%s so far vs %s%s by %s on an average day (last %d)%s" % (
                "📈" if ahead else "📉", "Ahead of pace" if ahead else "Behind pace", esc(usd(so_far)), esc(sh(so_far)),
                esc(usd(avg)), esc(sh(avg)),
                esc(et_str(b_.day_start(day) + (max(0.0, now - b_.day_start(day)) // 900) * 900)), n, esc(more))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return None

    def text_day(self, day, label):
        top = self._all_bots_day(day, label)
        if top:
            # inside the tap's quote: no <code> (Telegram refuses code inside a blockquote -- tg_html_problems)
            mw = main_words(self.active())
            L = [x.replace("<code>", "").replace("</code>", "")
                 for x in self.day_html(self.ledger.settled_on(day), day,
                                        main_shared(self.active()).capitalize() if main_sharers(self.active())
                                        else "Main account")]
            return Html("\n".join(top + ["", details(L, "🏦 %s (main account): closes, fills, "
                                                        "hours up -- tap" % (mw[:1].upper() + mw[1:])),
                                         i_("each bot in full: /bots · the week: /days")]))
        L = self.day_html(self.ledger.settled_on(day), day, label)
        if day == et_day(self.now()):                          # /today: yesterday beside it, for scale
            y = et_day(self.now() - 86400)
            s = Ledger.summary(self.ledger.settled_on(y))
            b0 = self.ledger.bank_at(et_day_start(y))
            L.append(i_("Yesterday %s (%s) · /days for the week" % (usd(s["net"]), pct((s["net"] / b0) if b0 else None))))
        return Html("\n".join(L))

    def _main_days(self):
        """The main account's (pin + race) last 7 ET days from the bot's own ledger: [(day, net, % of the bank
        that began it or None, lost closes, closes)], newest first."""
        out = []
        for d in list(reversed(self.ledger.days()))[:7]:
            s_ = Ledger.summary(self.ledger.settled_on(d))
            b0 = self.ledger.bank_at(et_day_start(d))
            out.append((d, s_["net"], (s_["net"] / b0) if b0 else None, s_["lost"], s_["closes"]))
        return out

    def _version_line(self):
        """'🏷 SINCE v-x (10/23 09:45 PM ET): +$58.11, 97 markets, 5 lost (5.2%)' for the pin bot's running
        version, or None. 2026-10-01, the operator: "/days doesn't show any recent negative days on this
        version" -- a deploy day mixes two versions, so the running one gets its own line (Kalshi's books, main
        account, markets closing after its deploy)."""
        ver = live_version(self.versions_path)
        if not ver:
            return None
        try:
            vs = [m for m in self._markets().values() if m["close"] is not None and m["close"] >= ver[1]]
        except Exception:                                    # noqa: BLE001
            return None
        lost = sum(1 for m in vs if m["pnl"] < -0.004)
        if not vs:
            return "🏷 <b>Pin bot since %s</b> (%s ET): nothing settled since" % (
                esc(ver[0]), esc(et_str(ver[1], "%m/%d %I:%M %p")))
        return "🏷 <b>Pin bot since %s</b> (%s ET): <b>%s</b>, %d markets, %d lost%s" % (
            esc(ver[0]), esc(et_str(ver[1], "%m/%d %I:%M %p")), esc(usd(sum(m["pnl"] for m in vs))), len(vs),
            lost, (" (%s)" % pct_of(lost, len(vs), 1)) if vs else "")

    def text_days(self):
        """/days: EVERY bot's last 7 ET days (2026-10-26, operator: "add the percentage anywhere it applied") --
        a day table with each day's % of all pots and its return on the bets, the week bot by bot with each bot's
        % of its bank, the all-time line; then the main account's own days (pin + race, behind a tap) and the pin
        bot's running version. Falls back to the main account's table alone when botstats cannot be read."""
        try:
            a = self._bs_get("all")
        except Exception:                                        # noqa: BLE001
            log(traceback.format_exc())
            a = None
        main = self._main_days()
        out = []
        if a is not None:
            bs = _bs()
            tot = a["total"]
            out.append(bs_headline(tot["last_7_days"], "of all pots", "All bots", when="last 7 days"))
            at = tot["all_time"]
            if at["markets"]:
                out.append(i_("all time %s%s · %s, %d lost · every pot, Kalshi's books; ET days" % (
                    usd(at["money"]), (" (%s on the %s put in)" % (bs.pot_pct_txt(at["pot_pct"]), dollars(at["pot"])))
                    if at.get("pot_pct") is not None and at.get("pot") else "", _nof(at["markets"], "market"), at["lost"])))
            firsts = [mm.get("first_day") for mm in [a["bots"][x]["money"] for x in bs.BOTS] + [a["other"]]
                      if mm.get("first_day")]               # every bot's books, hidden ones too: the totals' days
            days = [d for d in a["total_days_7"] if not (firsts and d["day"] < min(firsts))]
            if days:
                mx = max([abs(d["money"]) for d in days if d["markets"]] or [0])
                rows = [("Day", "Money", "of pots", "Return", "Lost", "")]
                for d in days:
                    if not d["markets"]:
                        rows.append((d["label"], "nothing settled"))
                        continue
                    rows.append((d["label"], usd(d["money"]),
                                 bs.pot_pct_txt(d["pot_pct"]) if d.get("pot_pct") is not None else "-",
                                 bs.pct(d["return_pct"]) if d.get("return_pct") is not None else "-",
                                 "%d/%d" % (d["lost"], d["markets"]), hbar(d["money"], mx, 4)))
                out += ["", "📅 <b>Last 7 days, every bot</b>", pre(table(rows, "lrrrrl")),
                        i_("of pots = share of all the pots when that day began · Return = on what the bets cost · "
                           "Lost = markets lost / settled")]
            tbl = bots_window_table(a, "last_7_days", "7 days")
            if tbl:
                out += ["", "📊 <b>Last 7 days, by bot</b>"] + tbl
            out += bots_avg_table(a)
            det = ["%s: <b>%s</b> (%s of the bank) · %d of %d closes lost" % (
                esc(bs.day_label(d)), esc(usd(v)), esc(pct(r)), lost, closes) for d, v, r, lost, closes in main]
            if det:
                mw = main_words(a.get("active"))
                out += ["", details(det, "🏦 %s (main account), day by day -- tap" % (mw[:1].upper() + mw[1:]))]
        else:
            rows, vals = [("Day", "Money", "% bank", "Lost", "")], []
            for d, v, r, lost, closes in main:
                vals.append(v)
                rows.append((d[5:], usd(v), pct(r), "%d/%d" % (lost, closes)))
            mx = max([abs(v) for v in vals] or [0])
            rows = [rows[0]] + [r + (hbar(v, mx, 4),) for r, v in zip(rows[1:], vals)]
            at_ = self.day_html(self.ledger.settled, None, "All time")
            out = [at_[0]] + at_[1:] + ["", "📅 <b>Last %d days</b> <i>(Kalshi's books, main account; ET days)</i>"
                                        % len(vals), pre(table(rows, "lrrrl")),
                                        i_("% bank = of the bank at the start of that day · Lost 1/25 = 1 losing close of 25")]
        vl = self._version_line()
        if vl:
            out += ["", vl]
        return Html("\n".join(out))

    def text_open(self):
        """Open bets in EVERY pot (2026-10-26 screen pass): the pin bot's own, with the seconds to each close, from
        its log; every other bot's from Kalshi's positions (botstats), with what is at risk and its share of
        that bot's cash."""
        h = self.health_fn()
        opn = pinflat.positions(self.ledger.newest_rows) if h["alive"] else {}
        L = []
        if opn:
            rows = []
            for t in opn:
                c = pinflat.close_epoch(t)
                rows.append((nice_coin(t), "x%g" % self.ledger.contracts_for(t), "closes %s" % close_et(t),
                             "(%d s)" % max(0, (c or 0) - self.now())))
            L += ["📂 <b>Pin bot: %d open</b>" % len(rows), pre(table(rows, "lrll"))]
        others, unread = [], []
        try:
            a = self._bs_get("all")
            bs = _bs()
            act = _active_of(a)
            for nm in bs.BOTS:
                if nm == DESK_BOT:                          # its own open bets are listed above (the Ledger)
                    continue
                bt = a["bots"][nm]
                o = bt["open"]
                if nm not in act and not (o["ok"] and o["count"]):
                    continue                             # v-tg-active: a hidden bot only if it still holds a bet
                label = bt["label"] if nm in act else "Earlier bot (not running)"
                if not o["ok"]:
                    unread.append(label.lower())
                    continue
                if not o["count"]:
                    continue
                cash = (bt.get("balance") or {}).get("dollars")
                others.append("📂 <b>%s: %d open</b> · %s at risk%s" % (
                    esc(label), o["count"], esc(_cash(o["at_risk"])),
                    (" (%s of its cash)" % esc(pct_of(o["at_risk"], cash + o["at_risk"], 1))) if cash else ""))
                for p_ in o["positions"][:8]:
                    others.append("  %s %s x%g · %s" % (esc(p_["what"]), esc(str(p_["side"]).upper()), p_["contracts"],
                                                       esc(_cash(p_["at_risk"]))))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            unread.append("the other bots (Kalshi could not be read)")
        L += others
        if not L:
            L.append("📂 <b>No open bets</b> in any pot.")
        if unread:
            L.append(i_("could not read: %s" % ", ".join(unread)))
        return Html("\n".join(L))

    def text_fills(self, day=None):
        """Every order the bot sent today: what filled, what we paid, how late.

        The operator, 2026-09-18: *"Make a telegram command to see the filled,
        paid, and seconds out info for the days bets."* He had asked where to
        see a fill price and the only answer was a column in the desktop app.

        ZERO-FILL ORDERS ARE SHOWN, not hidden. An order that filled nothing is
        a race we lost, and it is about one in five -- a list that quietly drops
        them would report a fill rate of 100%.

        2026-10-26 (operator: "anywhere that trades or transactions are listed list the account or which bot"): the
        table is the PIN BOT's orders (its own log) and says so; every other bot's fills that day follow, each line
        naming its bot (_other_fills_html).
        """
        day = day or et_day(self.now())
        rows = [o for o in self.ledger.orders
                if o.get("t") and et_day(o["t"]) == day]
        other = self._other_fills_html(day)
        if not rows:
            return Html("\n".join(["No pin bot orders today (%s)." % esc(day)] + other))
        rows.sort(key=lambda o: o["t"])
        tbl = [("Time", "Coin", "Got/asked", "Paid", "Left")]
        nf = got = asked = 0.0
        zero = 0
        for o in rows:
            f = float(o.get("filled") or 0)
            a = float(o.get("asked") or 0)
            got += f
            asked += a
            if f <= 0:
                zero += 1
            else:
                nf += 1
            px = o.get("price") or o.get("ask_seen")
            tau = o.get("tau")
            tbl.append((hm(o["t"]), coin(o.get("tk") or ""), ("%g/%g" % (f, a)) if a else ("%g" % f),
                        ("%.1fc" % (100 * float(px))) if px else "-",
                        ("%ss" % tau) if tau is not None else "(oil)"))
        out = ["🧾 <b>Pin bot orders today: %d</b> · %d filled · %d filled nothing%s" % (
            len(rows), int(nf), zero, (" (%s)" % pct_of(zero, len(rows))) if rows else ""),
            i_("%s ET · Left = seconds before the close when it was sent" % day),
            pre(table(tbl, "llrrr")),
            "Asked %g contracts, got <b>%g</b> (<b>%s</b>). %d orders: %d filled, %d lost the race." % (
                asked, got, esc(pct(got / asked, False) if asked else "-"), len(rows), int(nf), zero)]
        return Html("\n".join(out + other))

    def _other_fills_html(self, day, shown=8):
        """/fills' second part (2026-10-26): every OTHER bot's fills on ET day `day`, from its own log
        (botstats.fills_since, today's part only) -- how many each bot had, then the newest few, every line naming its
        bot. Html lines; a failure costs these lines only."""
        try:
            bs = _bs()
            act = self.active()
            fl, unread = bs.fills_since(et_day_start(day), [b for b in bs.BOTS if b != DESK_BOT])
            # v-tg-active: a paused or retired bot's fills (there should be none) are 'earlier bots', never its name
            names = [b for b in act if b != DESK_BOT] + ["earlier"]
            for f in fl:
                if f["bot"] not in act:
                    f["bot"] = "earlier"
            unread = {(b if b in act else "earlier"): w for b, w in unread.items()}
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return ["", i_("The other bots' fills could not be read.")]
        fl = [f for f in fl if f["t"] is not None and et_day(f["t"]) == day]
        when = "today" if day == et_day(self.now()) else _day_long(day)
        L = ["", "🧾 <b>Other bots' fills %s: %d</b> <i>(each bot's own log)</i>" % (esc(when), len(fl))]
        if fl:
            per = []
            for b in names:
                mine = [f for f in fl if f["bot"] == b]
                if mine:
                    per.append("%s %s, %s contracts" % (BOT_WORD.get(b, b), _nof(len(mine), "fill"),
                                                        _cnt(sum(f["contracts"] for f in mine))))
            L.append(esc(" · ".join(per)))
            for f in list(reversed(fl))[:shown]:
                side = " ".join(x for x in ("sold" if f["act"] == "sold" else "", (f["side"] or "").upper()) if x)
                what = f["what"][5:] if f["bot"] == "race" and f["what"].startswith("race ") else f["what"]
                L.append(esc("%s · %s · %s%s x%s%s" % (
                    hm(f["t"]), BOT_WORD.get(f["bot"], f["bot"]), what, (" " + side) if side else "",
                    _cnt(f["contracts"]), (" · %.1fc" % (100.0 * f["price"])) if f["price"] else "")))
            if len(fl) > shown:
                L.append(i_("the newest %d of %d, newest first" % (shown, len(fl))))
        else:
            L.append("None.")
        bad = [BOT_WORD.get(b, b) for b, why in unread.items() if why != "no log file found"]
        if bad:
            L.append(i_("could not read: %s" % ", ".join(bad)))
        return L

    def text_brief(self):
        """The daily briefing, from pinbrief -- the same words the CLI prints.

        NOT rebuilt here. The operator asked for one daily summary, and a
        phone copy that assembles its own version is a second summary to keep
        honest; the app and this bot have already disagreed about one day.
        """
        try:
            import pinbrief
            body = brief_html(pinbrief.text(pinbrief.brief(ledger=self.ledger)))
            top = self._all_bots_day(et_day(self.now()), "Today")      # 2026-10-26: every pot first, with its %
            if not top:
                return body
            mw = main_words(self.active())
            return Html("\n".join(top + ["", "🏦 <b>%s (main account)</b>" % esc(mw[:1].upper() + mw[1:]), str(body)]))
        except Exception as e:                                  # noqa: BLE001
            return ("Could not build today's briefing: %s\n"
                    "Everything else still works -- try /today again, or "
                    "/days for the plain numbers." % str(e)[:160])

    def text_market(self):
        act = self.ledger.activity()
        if act["recent"] is not None:
            out = ["🛒 <b>Sellers: %s</b> · <b>%.0f%%</b> of looks" % (esc(act["level"]), 100 * act["recent"]),
                   "Last 4 quarter-hours: someone selling the winning side on <b>%.0f%%</b> of looks (quiet &lt; %.0f%%, "
                   "typical %.0f%%, busy &gt; %.0f%%)."
                   % (100 * act["recent"], 100 * act["p25"], 100 * act["median"], 100 * act["p75"])]
        else:
            out = ["🛒 <b>Sellers: %s</b>" % esc(act["level"])]
        out.append("")
        # 2026-10-26, the operator: "On /market it lists the last closes can you include which bot made the trades". The
        # close summaries and their count are the PIN BOT's own (its log; the coin race's orders are in the race's log),
        # so each close says 'pin bot ...', then every other bot's buys on the markets closing then, from its own log.
        closes = list(reversed(self.ledger.closes))[:8]
        out.append("<b>Last %d closes</b> <i>(who bought, in contracts; sellers = share of the pin bot's looks with a "
                   "seller)</i>" % min(8, len(self.ledger.closes)))
        others, unread = self._close_buys(closes)
        want = {s["tk"]: s["want"] for s in self.ledger.signals if s.get("tk") and s.get("want") in ("yes", "no")}
        for c in closes:
            share = Ledger.offer_share(c)
            parts = [self._pin_close_words(c, want)] + others.get(int(c["close"]) if c["close"] else None, [])
            out.append("<b>%s</b> · sellers %s · %s" % (esc(et_str(c["close"]) if c["close"] else "?"),
                                                       esc(pct(share, False) if share is not None else "-"),
                                                       esc(" · ".join(parts))))
        if unread:
            out.append(i_("could not read %s, so its buys are not listed" % unread))
        today = et_day(self.now())
        fs = Ledger.fill_stats(self.ledger.fills_on(today))
        out.append("")
        out.append("<b>Pin bot today</b>: %d orders · %d filled · %d got nothing%s · wanted %s contracts, got <b>%s</b> "
                   "(%s)." % (fs["orders"], fs["fills"], fs["zero"],
                              (" (%s)" % pct_of(fs["zero"], fs["orders"])) if fs["orders"] else "",
                              "{:,.0f}".format(fs["asked"] or 0), "{:,.0f}".format(fs["contracts"] or 0),
                              esc(pct(fs["share"], False) if fs["share"] is not None else "-")))
        # IS THE OPPORTUNITY GOING AWAY. Same lines the desktop shows, from
        # the same function, so the phone and the app cannot drift apart.
        # Read from health() rather than recomputed: it is already there.
        try:
            h = self.health_fn()
            sl = h.get("supply_lines") or []
            age = h.get("supply_age_d")
            if sl and age is not None and age > SUPPLY_STALE_D:
                # 2026-10-23: the measurement stopped in September; a month-old trend is not shown as news
                out.append("")
                out.append(i_("The opportunity trend was last measured %.0f days ago, so it is left out." % age))
            elif sl:
                out.append("")
                out.append("📉 <b>IS THE OPPORTUNITY GOING AWAY?</b>")
                out += elines(sl)
                if age is not None:
                    out.append(i_("(measured up to %.1f days ago)" % age))
        except Exception:                                   # noqa: BLE001
            pass
        return Html("\n".join(out))

    def _pin_close_words(self, c, want):
        """What the PIN BOT did on one quarter-hour, from its own log (close summary, orders, hedges; `want` = {ticker:
        side} from its signals): 'pin bot bought 115 (NEAR NO)', '... + hedge 4 YES', 'pin bot LOST THE RACE: ordered 50,
        got 0 (someone bought it first)' or 'pin bot passed: <why>'. The count is Ledger.reason's: every pin order
        filled for that close."""
        why = self.ledger.reason(c)
        if not why.startswith("BOUGHT"):
            if why.startswith("LOST THE RACE"):
                return "pin bot " + why
            return "pin bot passed: " + ("nothing met its rules" if why == "nothing passed" else why)
        legs = []
        for o in self.ledger.orders:
            if o["close"] == c["close"] and o["filled"] > 0:
                side = want.get(o["tk"]) or (c.get("best_want") if o["tk"] == c.get("best_ticker") else None)
                k = " ".join(x for x in (_mkt_short(o["tk"]), str(side or "").upper()) if x)
                if k and k not in legs:
                    legs.append(k)
        s = "pin bot bought %g%s" % (sum(o["filled"] for o in self.ledger.orders if o["close"] == c["close"]),
                                     (" (%s)" % ", ".join(legs)) if legs else "")
        hed = [g for g in self.ledger.hedges if g.get("kind") == "hedge" and str(g.get("status")) == "executed"
               and g.get("tk") and pinflat.close_epoch(g["tk"]) == c["close"]]
        if hed:
            s += " + hedge " + ", ".join(" ".join(x for x in ("%g" % _f(g.get("n")), str(g.get("side") or "").upper())
                                                  if x) for g in hed)
        return s

    def _close_buys(self, closes):
        """({close epoch: ['coin race 2 (SOL YES)', 'forecaster 26 (ETH YES)', 'FX taker 3 markets x10']}, the bots whose
        log could not be read, in words, or None): what every bot but the pin bot bought on the markets closing at each
        of `closes`, from its own log (botstats.fills_since, back two hours past the oldest close: hundredths of a
        second). A failure costs these words only."""
        cs = {int(c["close"]) for c in closes if c.get("close")}
        if not cs:
            return {}, None
        try:
            bs = _bs()
            act = self.active()
            fl, unread = bs.fills_since(min(cs) - 2 * 3600, [b for b in bs.BOTS if b != DESK_BOT])
            names = [b for b in act if b != DESK_BOT] + ["earlier"]       # v-tg-active, as /fills
            for f in fl:
                if f["bot"] not in act:
                    f["bot"] = "earlier"
            unread = {(b if b in act else "earlier"): w for b, w in unread.items()}
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return {}, "the other bots' logs"
        by = {}
        for f in fl:
            if f["close"] is not None and int(f["close"]) in cs:
                by.setdefault(int(f["close"]), {}).setdefault(f["bot"], []).append(f)
        out = {k: [buys_words(b, v[b]) for b in names if b in v] for k, v in by.items()}
        bad = [BOT_WORD.get(b, b) for b, why in unread.items() if why != "no log file found"]
        return out, (", ".join(bad) if bad else None)

    def text_losses(self):
        """/losses: EVERY bot's losing markets (operator 10-26: "Make it so /losses outputs losses not just for pin and
        race and show which bot it lost. Show all the same information and show a bit more than just the last ten")
        from tgcharts.all_losses (botstats, Kalshi's books, every pot -- the chart's own source): the last
        LOSSES_SHOWN by ET day, each with its bot, the market, side and contracts, $ and % of that bot's pot, then
        every bot's count, last 7 days, $ lost and worst. The main account's losing closes (text_losses_main) when
        botstats cannot be read at all."""
        try:
            bs, rows, per, missing = _tgc().all_losses({"now": self.now(), "pp": sys.modules[__name__],
                                                         "bs_getter": self.bs_getter, "bs_procs": self.bs_procs})
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return self.text_losses_main()
        if not per:
            return self.text_losses_main()
        short = _tgc().BOT_SHORT
        lost = sum(p["lost"] for p in per.values())
        settled = sum(p["settled"] for p in per.values())
        if not rows:
            return Html("No losing markets in any pot (%s settled)." % _cnt(settled)
                        + (" ⚠️ Leaves out %s (Kalshi could not be read)." % esc(", ".join(missing)) if missing else ""))

        def line(r):
            what = r["what"][5:] if r["bot"] in ("race", "earlier") and r["what"].startswith("race ") else r["what"]
            held = ("hedged x%s" % _cnt(r["contracts"])) if r["side"] == "both" else \
                ("%s x%s" % (r["side"].upper(), _cnt(r["contracts"])) if r["side"] in ("yes", "no") else "")
            return "<b>%s</b>%s · %s · %s" % (esc(usd(r["money"])),
                                             (" (%s)" % esc(bs.pot_pct_txt(r["pct"]))) if r["pct"] is not None else "",
                                             esc(short.get(r["bot"], r["bot"])), esc(" ".join(x for x in (what, held) if x)))

        tbl = [("Bot", "Lost", "7d", "$ lost", "Worst")]
        for nm in tuple(bs.BOTS) + ("earlier", "other"):         # all_losses folds hidden bots into one row
            p = per.get(nm)
            if p and p["settled"]:
                tbl.append((short.get(nm, nm), "%d/%d" % (p["lost"], p["settled"]), str(p["lost_7d"]),
                            "%.2f" % p["money_lost"], "%.2f" % p["worst"] if p["worst"] is not None else "-"))
        worst = min((p["worst"] for p in per.values() if p["worst"] is not None), default=None)
        tbl.append(("ALL", "%d/%d" % (lost, settled), str(sum(p["lost_7d"] for p in per.values())),
                    "%.2f" % sum(p["money_lost"] for p in per.values()), "%.2f" % worst if worst is not None else "-"))
        tail = ["", "📊 <b>By bot, all time</b>", pre(table(tbl, "lrrrr")),
                i_("Lost = markets lost / settled · 7d = lost in the last 7 days · $ lost = all its losing markets "
                   "added up · Worst = its worst single market · /losses chart: every loss, coloured by bot")]
        n = min(LOSSES_SHOWN, len(rows))
        while True:
            out = ["🔴 <b>%s losing markets</b> of %s settled, every bot (%.1f%%) · %d in the last 7 days" % (
                       _cnt(lost), _cnt(settled), 100.0 * lost / settled if settled else 0.0,
                       sum(p["lost_7d"] for p in per.values())),
                   i_("the last %d, newest first · %% = of that bot's pot when its day began (%s) · Kalshi's books, "
                      "every pot" % (n, ("%s share the main account" % main_shared(per)) if main_sharers(per) else
                                     "earlier bots = the paused or stopped ones"))]
            if missing:
                out.append("⚠️ PARTIAL: leaves out %s (Kalshi could not be read)" % esc(", ".join(missing)))
            day = None
            for r in rows[:n]:
                if r["day"] != day:
                    day = r["day"]
                    out += ["", "<b>%s</b>" % esc(_day_long(day))]
                out.append(line(r))
            msg = "\n".join(out + tail)
            if len(msg) <= MAX_LEN or n <= 5:
                return Html(msg)
            n -= 5

    def text_losses_main(self):
        """The main account's losing closes from its own ledger (pin + race; the /losses of before 10-26), for when
        botstats cannot be read."""
        rows = self.ledger.losing_closes()[:LOSSES_SHOWN]
        if not rows:
            return Html("No losing closes.")
        s = Ledger.summary(self.ledger.settled)
        out = ["🔴 <b>%d losing closes</b> of %d all time (%.1f%%)" % (s["lost"], s["closes"], s["loss_rate"]),
               i_("the last %d, newest first · %% = of the bank just before it (Kalshi's books, main account: pin + "
                  "race)" % len(rows))]
        for close, net, legs in rows:
            b0 = self.ledger.bank_at(close - 1) if close else None
            out.append("<b>%s</b>%s · %s · %s" % (
                esc(usd(net)), (" (%s)" % esc(pct(net / b0))) if b0 else "",
                esc(et_str(close, "%a %b %d %I:%M %p").replace(" 0", " ") if close else "?"),
                esc(", ".join(sorted({nice_coin(l["tk"]) for l in legs})))))
        return Html("\n".join(out))

    def text_hedges(self):
        ho = list(reversed(self.ledger.hedge_outcomes()))[:8]
        if not ho:
            return Html("No hedges yet.")
        out = ["🛡 <b>Pin bot's insurance</b> (the last %d hedges, newest first)" % len(ho)]
        for g in ho:
            mark = {"NEEDED": "✅", "WASTED": "➖"}.get(g["verdict"], "⏳")
            b0 = self.ledger.bank_at(g["t"]) if g.get("t") and g.get("net") is not None else None
            out.append("%s <b>%s</b> · %s %s · belief %.0f%% · net <b>%s</b>%s" % (
                mark, esc(g["verdict"] or "pending"),
                esc(et_str(g["t"], "%a %b %d %I:%M %p").replace(" 0", " ") if g["t"] else "?"),
                esc(nice_coin(g["tk"])), 100 * float(g.get("belief") or 0),
                esc(usd(g["net"]) if g["net"] is not None else "-"),
                (" (%s of the bank)" % esc(pct(g["net"] / b0))) if b0 else ""))
        out.append(i_("belief = the bot's odds its side wins when it bought the insurance · NEEDED = the bet lost and "
                      "the insurance covered part of it; WASTED = the bet held and the insurance expired (its premium)"))
        return Html("\n".join(out))

    # ---- /stats /race /racestats ----
    def _sides(self):
        """{ticker: entry side} from the bot's own records. A hedge record
        names the side the hedge BOUGHT, so the entry is the other one --
        that is the authority, sent or not. Markets with no hedge record
        take the ledger's `want` (pindesk's own reading, count rule first,
        the log breaking an equal count)."""
        out = {}
        for g in self.ledger.hedges:
            if g.get("tk") and g.get("side") in ("yes", "no"):
                out[g["tk"]] = "no" if g["side"] == "yes" else "yes"
        for x in self.ledger.settled:
            if x.get("tk") and x["tk"] not in out and x.get("want") in ("yes", "no"):
                out[x["tk"]] = x["want"]
        return out

    def _markets(self):
        return markets_from(raw_ledger(os.path.join(self.ledger.results, pinday.LEDGER_NAME)), self._sides())

    def _race_summary(self, races):
        rs = [r for r in races.values() if r["close"] is not None and r["close"] >= self.race30_epoch]
        t = race_tally(rs)
        if not t["races"]:
            return "no real races on Kalshi's books since v-race30."
        return "%d races since %s: %d won (%s), %d tie, %d lost, %s (/race)." % (
            t["races"], et_str(self.race30_epoch, "%m/%d"), t["won"], pct_of(t["won"], t["races"], 1), t["tie"],
            t["lost"], usd(t["net"]))

    def text_stats(self):
        """Everything he would show a friend, by window. Money is Kalshi's;
        the seconds-left split is from the bots' order records; the bank,
        size and day count are the live bot's own files. On the phone: the
        lifetime money as the headline, the live bot, one table of every
        window, and each window's full sentences (stats_block) behind a tap."""
        now = self.now()
        today = et_day(now)
        res = self.ledger.results
        mk = self._markets()
        ms = [m for m in mk.values() if m["day"] >= FIRST_LIVE_DAY]
        if not ms:
            return Html("No Kalshi settlements on file since %s (results/kalshi_ledger.json)." % FIRST_LIVE_DAY)
        taus = first_entries(self.ledger.orders)
        fl = fleet(self.procs_fn())
        ver = live_version(self.versions_path)
        wins = [("LIFETIME (since %s)" % _md(FIRST_LIVE_DAY), ms, days_between(FIRST_LIVE_DAY, today), "Life"),
                ("LAST 7 DAYS", [m for m in ms if m["day"] >= day_minus(today, 6)], 7, "7 days"),
                ("LAST 3 DAYS", [m for m in ms if m["day"] >= day_minus(today, 2)], 3, "3 days"),
                ("TODAY (%s)" % _md(today), [m for m in ms if m["day"] == today], 1, "Today")]
        if ver:
            wins.append(("SINCE %s (%s ET)" % (ver[0], et_str(ver[1], "%m/%d %I:%M %p")),
                         [m for m in ms if m["close"] is not None and m["close"] >= ver[1]], None, "Version"))
        sts = [(title, window_stats(sub, taus), nd, lab, sub) for title, sub, nd, lab in wins]
        life = sts[0][1]
        # "every bot" was true until the forecaster and the ladder got their
        # own subaccounts; kalshi_ledger.json is the main account only now.
        L = ["%s <b>Lifetime %s</b> (<b>%s</b> on $%s risked) · since %s" % (
                 dot(life["net"]), esc(usd(life["net"])), esc(ret(life["net"], life["risked"], 2)),
                 esc(_usd(life["risked"])), esc(_md(FIRST_LIVE_DAY))),
             i_("📊 STATS · %s ET · Kalshi's books, main account (%s; every other bot: /bots); "
                "days are ET." % (et_str(now, "%a %m/%d %I:%M %p"), main_words(self.active())))]
        # % of the bank (2026-10-26): each window's money over the main account's bank when it began (pindesk's
        # bank_at, the /days figure); Life over the money put into the main account (botstats' pot, as /pin says)
        life_in = None
        try:
            life_in = ((self._bs_get(DESK_BOT).get("money") or {}).get("all_time") or {}).get("pot")
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
        starts = {"7 days": et_day_start(day_minus(today, 6)), "3 days": et_day_start(day_minus(today, 2)),
                  "Today": et_day_start(today), "Version": ver[1] if ver else None}
        rows = [("", "Money", "Return", "of bank", "Won", "Lost")]
        for title, st, nd, lab, sub in sts:
            if not st["markets"]:
                rows.append((lab, "nothing settled"))
                continue
            if lab == "Life":
                ob = (ret(st["net"], life_in, 0) + "*") if life_in else "-"
            else:
                b0 = self.ledger.bank_at(starts[lab]) if starts.get(lab) else None
                ob = ret(st["net"], b0, 2 if b0 and abs(st["net"] / b0) < 0.01 else 1) or "-"
            rows.append((lab, usd(st["net"]), ret(st["net"], st["risked"], 1) or "-", ob,
                         pct1(st["won"], st["markets"]), st["losses"]))
        L.append("")
        L.append("💰 <b>By window</b>")
        L.append(pre(table(rows)))
        L.append(i_("Return = on what the bets cost (fees in) · of bank = of the main account's bank when the window "
                    "began%s · Won = markets won · Lost = markets that lost" % (
                        (" (* Life: of the %s put into it)" % dollars(life_in)) if life_in else "")))
        if life["breakeven_d"] is not None and life["win_n"] is not None:
            L.append("🎯 Lifetime: won <b>%s%%</b> of markets (break-even needs %s%%) · contracts paid %s%% vs "
                     "break-even %s%%: <b>%+.1f pts</b>" % (
                         _of100(life["win_c"]), _of100(life["breakeven_c"]), _of100(life["win_n"]),
                         _of100(life["breakeven_d"]), 100.0 * (life["win_n"] - life["breakeven_d"])))
        by = {}
        for m in sts[0][4]:
            by[m["book"]] = by.get(m["book"], 0.0) + m["pnl"]
        act_ = self.active()
        names = dict([(b.ledger_book, b.word if (b.always_shown or b.name in act_) else BOT_WORD["earlier"])
                      for b in _bots.all_bots() if b.ledger_book] + [("commodity", "old oil bot (Sep)"), ("other", "other")])
        L.append(esc("Lifetime by bot: " + ", ".join("%s %s" % (names.get(b, b), usd(v))
                                                     for b, v in sorted(by.items(), key=lambda kv: -kv[1])) + "."))
        pid = fl["live"][0] if fl["live"] else None
        live_cl = fl["live"][1] if fl["live"] else ""
        if pid:
            where = ", pid %d" % pid
        elif fl["unknown"]:
            where = " (process table could not be read)"
        else:
            where = ", NOT in the process table"
        L.append("")
        if ver:
            L.append("⚙️ <b>LIVE %s</b> since %s ET%s%s." % (esc(ver[0]), esc(et_str(ver[1], "%m/%d %I:%M %p")),
                                                          " (about)" if ver[2] else "", esc(where)))
        else:
            L.append("⚙️ <b>LIVE version</b>: no readable header in VERSIONS.md%s." % esc(where))
        parts = []
        hb = argv_opt(live_cl, "--hedge-belief")
        if hb:
            parts.append("Hedge trigger: belief %.0f%%" % (100.0 * _f(hb)))
        sz = read_json(os.path.join(res, "pinrun-live-size.json")) or {}
        hwm = read_json(os.path.join(res, "pinrun-hwm.json")) or {}
        dl = read_json(os.path.join(res, "pinrun-dayloss.json")) or {}
        if sz.get("size") is not None:
            s = "Size %g contracts (auto)" % _f(sz["size"])
            if sz.get("bank") is not None:
                s += ", bank %s read %s" % (dollars(_f(sz["bank"])), et_str(pindesk.parse_t(sz.get("at")) or now))
            parts.append(s)
        if parts:
            L.append(esc(". ".join(parts) + "."))
        if hwm.get("hwm") and sz.get("bank") is not None:
            h = _f(hwm["hwm"])
            line = (1.0 - MAX_DRAWDOWN) * h
            room = _f(sz["bank"]) - line
            L.append("🛑 Halt if the bank falls to %s (%.0f%% under its high of %s): <b>%s of room</b>%s." % (
                esc(dollars(line)), 100.0 * MAX_DRAWDOWN, esc(dollars(h)), esc(dollars(room)),
                (" (%s of the bank)" % pct_of(room, _f(sz["bank"]), 1)) if _f(sz["bank"]) > 0 else ""))
        cap = argv_opt(live_cl, "--loss-cap")
        if dl.get("day") == today and dl.get("realised") is not None:
            L.append("Today by the bot's own count: <b>%s</b>%s." % (
                esc(usd(_f(dl["realised"]))), esc(" (stops at -$%s for the day)" % cap) if cap else ""))
        if fl["unknown"]:
            L.append("Paper arms: the process table could not be read.")
        else:
            arms = [a[4:] if a.startswith("arm-") else a for a in fl["arms"]]
            race_on = "race" in self.active()            # v-tg-active: the paused race and its arms are not said
            L.append(esc("Paper arms: %d%s%s." % (
                len(arms), (" (" + ", ".join(arms) + ")") if arms else "",
                (" + %d race arms%s" % (len(fl["race_arms"]), (" (" + ", ".join(fl["race_arms"]) + ")")
                                        if fl["race_arms"] else "")) if race_on else "")))
        if "race" in self.active():
            L.append("🏁 Coin race: " + esc(self._race_summary(races_from(mk))))
        det, seen = [], []
        for title, st, nd, lab, sub in sts:                 # every window's full sentences, one quote
            keys = frozenset(m["tk"] for m in sub)
            same = next((t0 for t0, k0 in seen if k0 == keys), None) if keys else None
            seen.append((title, keys))
            if same:                                        # e.g. a version deployed at midnight = TODAY
                det.append("%s: the same %s as %s, so the same numbers." % (b_(title), esc(_nof(len(keys), "market")),
                                                                           esc(same)))
                continue
            det.append(b_(title))
            det += elines(stats_block(title, st, nd).split("\n")[1:])
        L.append("")
        L.append(details(det, "🔎 Every window in words (tap)"))
        return Html("\n".join(L))

    def text_race(self):
        """The coin race's /market: the live race now (its own log and the
        process table), the last 10 races and today's money from Kalshi.

        2026-10-18: it is NOT the penny test any more and the page says so --
        real money in the main account, and since v-race-snowball its bets
        grow with the bank (race_size_words reads the size it last took from
        the bank, not the start record's 20 / $40 it starts from)."""
        now = self.now()
        today = et_day(now)
        res = self.ledger.results
        races = races_from(self._markets())
        fl = fleet(self.procs_fn())
        recs = log_records(os.path.join(res, "pinracepenny-live.jsonl"),
                           ("start", "live_halt", "live_order", "live_settled", "bank_size"))
        pv = penny_view(recs, now, ledger_events=set(races))
        st = pv["start"] or {}
        t = race_tally([r for r in races.values() if r["day"] == today])
        if t["races"]:
            L = ["%s <b>Coin race today %s</b> (<b>%s</b> on %s staked) · %d of %d won (%s)%s" % (
                dot(t["net"]), esc(usd(t["net"])), esc(ret(t["net"], t["paid"])), esc(dollars(t["paid"])),
                t["won"], t["races"], pct_of(t["won"], t["races"]),
                (" · %d tie, %d lost" % (t["tie"], t["lost"])) if (t["tie"] or t["lost"]) else "")]
        else:
            L = ["⚪ <b>Coin race today: no races settled yet</b>"]
        L.append(i_("🏁 COIN RACE · %s ET · live, real money, main account (Kalshi's books)"
                    % et_str(now, "%a %m/%d %I:%M %p")))
        if fl["penny"]:                 # 2026-10-26: a red / green dot means money; the state is an icon and words
            L.append("▶️ <b>RUNNING</b>, pid %d" % fl["penny"][0])
        elif fl["unknown"]:
            L.append("❔ <b>Running? The process table could not be read.</b>")
        else:
            L.append("⚠️ <b>NOT RUNNING</b> (no pinracearm --live in the process table).")
        if os.path.exists(os.path.join(res, "pinracepenny.stop")):
            L.append("⏸ <b>STOOD DOWN</b>: the stop file results/pinracepenny.stop is present.")
        L.append("")
        size, rules = race_size_words(pv["start"], pv["bank_size"]), race_rule_words(pv["start"])
        L.append("📏 <b>How it bets</b>%s" % ("" if fl["penny"] else " <i>(its last start record)</i>"))
        if size:
            head, _sep, rest = size.partition(": ")
            L.append("<b>%s</b>: %s" % (esc(head[:1].upper() + head[1:]), esc(rest)) if rest else esc(size))
            L.append(esc("Buys " + rules + "."))
        else:
            L.append("Rails unknown (no start record).")
        if pv["halt"]:
            L.append("🛑 <b>STOP RAIL FIRED %s ET</b>: %s. No real order since." % (
                esc(et_str(pindesk.parse_t(pv["halt"].get("t")) or now, "%m/%d %I:%M %p")), esc(pv["halt"].get("why"))))
        elif st:
            L.append("Stop rail: not fired since the restart at %s ET."
                     % esc(et_str(pindesk.parse_t(st.get("t")) or now, "%m/%d %I:%M %p")))
        else:
            L.append("Stop rail: unknown -- no start record in its log.")
        nxt = (int(now) // 900 + 1) * 900
        left = int(nxt - now)

        def legs_of(ls):
            return ", ".join("%s %s %.0fc x%g" % (_leg_name(o.get("ticker")), o.get("side"),
                                                  100.0 * _f(o.get("exec_price") or o.get("ask_seen")),
                                                  _f(o.get("filled"))) for o in ls)
        held = [x for x in pv["open"] if x[1] == nxt]
        others = [x for x in pv["open"] if x[1] != nxt]
        legs = "; ".join(legs_of(ls) for _e, _c, ls in held)
        L.append("")
        L.append("⏱ <b>Now</b>: race closing %s ET (%d:%02d left) -- %s. <b>%s out.</b>" % (
            esc(et_str(nxt)), left // 60, left % 60, esc(("holding " + legs) if legs else "no legs yet"),
            esc(dollars(pv["staked"] or 0.0))))
        if others:
            L.append("Awaiting Kalshi's result: " + esc("; ".join(
                "%s ET %s" % (et_str(c) if c else "?", legs_of(ls)) for _e, c, ls in others) + "."))
        if pv["pending"]:
            L.append("⚠️ %d older leg(s) the bot never scored and Kalshi has no row for (oldest %s ET)."
                     % (sum(len(ls) for _e, _c, ls in pv["pending"]),
                        esc(et_str(pv["pending"][0][1], "%m/%d %I:%M %p") if pv["pending"][0][1] else "?")))
        L.append("")
        L.append("🏆 <b>Last 10 races</b> <i>(Kalshi's books)</i>")
        if races:
            L.append(pre(race_rows(races, 10)))
        else:
            L.append("none on file.")
        L.append("Paper race arms running: %s." % esc(
            "process table could not be read" if fl["unknown"] else
            (", ".join(fl["race_arms"]) if fl["race_arms"] else "none")))
        L += self._race_money_lines()
        return Html("\n".join(L))

    def _race_money_lines(self):
        """/race's money by window (2026-09-30), from botstats: every coin-race
        market in the main account, read from Kalshi live, one leg = one coin's
        market. Plus what /race did not say: the version, its keep-alive, what
        Kalshi holds open, the shared cash and today's refusals. A failure
        costs these lines only -- the rest of /race still answers. Html lines;
        botstats' Settings line is left to /race's 'How it bets' above (it
        words the start-up size from the command line, not the size the race
        now takes from the bank)."""
        try:
            b = self._bs_get("race")
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ["", "Money by window: could not build it (%s). The lines above still stand." % esc(str(e)[:160])]
        L = [""]
        L += bs_money_html(b["money"], "leg")
        L.append("")
        L += elines([x for x in bs_setup_lines(b["running"]) if not x.startswith("Settings: ")])
        ol = elines(bs_open_lines(b["open"], "leg"))
        L.append("📂 " + ol[0].replace("Open now:", "<b>Open now:</b>", 1))
        L += ol[1:]
        L.append("💵 " + esc(bs_cash_line(b["balance"])).replace("Cash:", "<b>Cash:</b>", 1))
        det = (elines(_money_detail(b["money"], "leg")) if b["money"]["ok"] else [])
        det += elines(bs_activity_lines("race", b["activity_today"]))
        L.append(details(det, "🔎 Details: every window in words, today's log"))
        return L

    # ---- /bots /pin /forecaster /ladder ----
    def _bs_get(self, name):
        """botstats' dict for one bot, or for 'all'. Kalshi is read at most once a minute."""
        bs = _bs()
        if name == "all":
            return bs.all_bots(now=self.now(), getter=self.bs_getter, procs=self.bs_procs)
        return bs.bot(name, now=self.now(), getter=self.bs_getter, procs=self.bs_procs)

    def text_bots(self):
        try:
            return Html("\n".join(bs_all_html(self._bs_get("all"))))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /bots: %s\nEverything else still works -- /stats and /race carry the "
                    "main account's numbers." % str(e)[:200])

    def text_bot(self, name):
        cmd = BOT_CMD_OF.get(name, "/" + name)
        try:
            b = self._bs_get(name)
            out = bs_bot_html(b, _bs().et_clock(self.now()))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build %s: %s\nEverything else still works -- /stats and /race carry the "
                    "main account's numbers." % (cmd, str(e)[:200]))
        more = PAGE_FOOTER.get(name)                    # v-tg-rebuild step 5: the registry's Bot.page_footer
        return Html("\n".join(out) + ("\n\n" + i_(more) if more else ""))

    def text_racestats(self):
        """The live coin race's record by window (Kalshi's books) and every
        paper race arm on the same races.

        2026-10-18 (race-arms + skeptic, .sweep\\q-2026-10-18e\\prior): the
        five arms are PAPER and STOPPED (09-27 .. 10-01), and their own-log
        dollars were the arms' paper size (up to 250 contracts, priced at the
        touch) with ties booked as wins. So each arm now says PAPER and
        STOPPED with its dates (log_span; the process table says if one runs
        again), and its money is shown three ways on the same races: at its
        own size re-scored on Kalshi's results (a tie pays 50c), at the live
        bot's size, and what the live bot really made there. The first two
        come from results/race_arms_scored.json, used only while the arm's
        log is the size it was scored at; otherwise the arm's own-log money is
        shown and labelled so. Wins / ties / losses are this page's own count
        (a race Kalshi tied is a tie), as always."""
        now = self.now()
        today = et_day(now)
        res = self.ledger.results
        races = races_from(self._markets())
        if not races:
            return Html("No coin-race settlements on Kalshi's books yet.")
        r30 = self.race30_epoch
        first_day = min(r["day"] for r in races.values())
        allr = list(races.values())
        wins = [("ALL TIME (since %s)" % _md(first_day), allr, "All"),
                ("LAST 7 DAYS", [r for r in allr if r["day"] >= day_minus(today, 6)], "7 days"),
                ("LAST 3 DAYS", [r for r in allr if r["day"] >= day_minus(today, 2)], "3 days"),
                ("TODAY", [r for r in allr if r["day"] == today], "Today"),
                ("SINCE v-race30 (%s ET)" % et_str(r30, "%m/%d %I:%M %p"),
                 [r for r in allr if r["close"] is not None and r["close"] >= r30], "v30")]
        at = race_tally(allr)
        L = ["%s <b>Coin race all time %s</b> (<b>%s</b> on %s staked) · %d races, <b>%s</b> won" % (
                 dot(at["net"]), esc(usd(at["net"])), esc(ret(at["net"], at["paid"])), esc(dollars(at["paid"])),
                 at["races"], pct_of(at["won"], at["races"], 1)),
             i_("🏁 COIN RACE STATS · %s ET · Kalshi's books, real money. A race = one 15-min contest; a tie pays "
                "50c a leg and counts as a loss." % et_str(now, "%a %m/%d %I:%M %p"))]
        rows = [("", "Money", "Return", "Races", "Won", "T/L")]
        det = []
        for title, rs, lab in wins:
            t = race_tally(rs)
            if not t["races"]:
                rows.append((lab, "no races"))
                continue
            rows.append((lab, usd(t["net"]), ret(t["net"], t["paid"]) or "-", t["races"],
                         pct_of(t["won"], t["races"]), "%d/%d" % (t["tie"], t["lost"])))
            det.append(esc(norm_money("%s: %s" % (title, race_tally_line(t)))))
        L.append("")
        L.append(pre(table(rows)))
        L.append(i_("Return = on what the bets cost (fees in) · Won = races won · T/L = ties / losses · v30 = since "
                    "v-race30, %s ET (today's rules)" % et_str(r30, "%m/%d %I:%M %p")))
        # ---- the paper arms, on the races the live bot played since v-race30 ----
        since = {e: r for e, r in races.items() if r["close"] is not None and r["close"] >= r30}
        # the cached table only (the arms are stopped; 'unknown' is fine here, a cold-cache read is not)
        fl = fleet(cached_python_procs() if self.procs_fn is python_procs else self.procs_fn())
        sc = race_arms_scored(res) or {}
        cards, rec_rows, money_rows, said, run_det = [], [("Arm", "In", "Won", "W/T/L")], \
            [("Arm", "Own size", "At live", "Live bot")], [], []
        n_stopped = n_arms = n_scored = 0
        starred, star_ties = [], []
        z3res, z3_span = None, None
        last_ran = None
        for name in RACE_ARMS:
            p = os.path.join(res, "pinracearm-%s.jsonl" % name)
            if not os.path.exists(p):
                cards.append("<b>%s</b>: no log." % esc(name))
                continue
            n_arms += 1
            ar = arm_results(p)
            span = log_span(p) or {}
            if name == "z3":
                z3res, z3_span = ar, span
            if span.get("last") is not None:
                last_ran = max(last_ran or span["last"], span["last"])
            running = None if fl["unknown"] else (name in fl["race_arms"])
            quiet = span.get("last") is not None and now - span["last"] > 6 * 3600
            ran = "%s to %s" % (et_str(span["first"], "%b %d") if span.get("first") else "?",
                                et_str(span["last"], "%b %d") if span.get("last") else "?")
            if running:
                status = "PAPER, RUNNING (since %s)" % (et_str(span["first"], "%b %d") if span.get("first") else "?")
            elif span.get("end") or quiet:
                status = "PAPER, STOPPED · ran %s" % ran
                n_stopped += 1
            else:
                status = "PAPER · log written %s ET%s" % (
                    et_str(span["last"], "%b %d %I:%M %p") if span.get("last") else "?",
                    "; not in the process table" if running is False else "")
            a = (sc.get("arms") or {}).get(name) or {}
            try:
                fresh = bool(a) and int(a.get("log_size") or -1) == os.path.getsize(p)
            except OSError:
                fresh = False
            cards.append("<b>%s</b> · %s%s" % (esc(name), esc(status),
                                               (" · " + esc(a["own_size"])) if a.get("own_size") else ""))
            rec = arm_record(ar, since)
            evs = [e for e in since if (ar.get(e) or {}).get("positions", 0) > 0]
            live_same = sum(since[e]["pnl"] for e in evs)
            rec_rows.append((name, "%d %s" % (rec["entered"], pct_of(rec["entered"], len(since))),
                             pct_of(rec["won"], rec["entered"], 1) or "-",
                             "%d/%d/%d" % (rec["won"], rec["tie"], rec["lost"])))
            same = a.get("same") or {}
            if fresh and same.get("races") == rec["entered"]:
                n_scored += 1
                money_rows.append((name, usd(same.get("own")), usd(same.get("at_live")), usd(live_same)))
                if same.get("own_log") is not None and abs(_f(same["own_log"]) - _f(same.get("own"))) >= 0.005:
                    said.append("%s %s" % (name, usd(same["own_log"])))
                run = a.get("run") or {}
                if run:
                    run_det.append(esc("%s, whole run: %d races, %d won, %d tie, %d lost; own size %s, at the live "
                                       "bot's size %s." % (name, run.get("races", 0), run.get("won", 0),
                                                           run.get("tie", 0), run.get("lost", 0), usd(run.get("own")),
                                                           usd(run.get("at_live")))))
            else:
                money_rows.append((name, usd(rec["net"]) + "*", "-", usd(live_same)))
                if rec["entered"]:
                    starred.append(name)
                    if rec["ties_as_wins"]:
                        star_ties.append(name)
        # 2026-10-23 (operator: nothing out of date in front -- "the stopped September race arms"): when every arm
        # is stopped, the page says so in one line and the whole arms section goes behind the tap
        all_stopped = bool(n_arms) and n_stopped == n_arms
        page = L
        L = []
        L.append("")
        L.append("🧪 <b>PAPER ARMS</b> -- no real money%s" % (
            (" · all %d STOPPED" % n_arms) if all_stopped else ""))
        L += cards
        L.append("")
        L.append("On the <b>%d</b> races the live bot played since v-race30:" % len(since))
        L.append(pre(table(rec_rows, "lrrr")))
        L.append(pre(table(money_rows)))
        legend = "Own size = the arm's own paper size%s. " % (
            (", scored on Kalshi's results (a tie pays 50c)%s" % (
                (" -- their own logs said %s (a log books a tie as a win and does its own fee sums)"
                 % ", ".join(said)) if said else ""))
            if n_scored else "")
        if n_scored:
            legend += ("At live = the same legs at the live bot's size for that race, capped by what the book "
                       "showed. ")
        legend += ("Live bot = what the real bot made on those races (Kalshi). Paper is optimistic (race-arms "
                   "check, 10-18): on legs the live bot also sent, paper made 41% more than real fills, so At live "
                   "reads ~40% high; the 250-a-leg arms' Own size prices fills at the touch, and walking the book "
                   "cuts it 30-66%.")
        if starred:
            legend += " * = the arm's own log money (%s)%s." % (
                "no Kalshi re-scoring on file" if not sc.get("arms") else "its log changed after it was re-scored",
                ("; %s booked a tie as a win" % (
                    " and ".join("%s's" % x for x in star_ties) + (" own logs" if len(star_ties) > 1 else " own log")))
                if star_ties else "")
        L.append(i_(legend))
        if sc.get("made"):
            L.append(i_("Scored once on %s from Kalshi's results (results/%s); stopped arms do not change."
                        % (et_str(pindesk.parse_t(sc["made"]), "%b %d"), RACE_ARMS_SCORED)))
        if z3res is not None:
            z = z3_progress(z3res, races)
            verdict = ""
            if z["first50_losses"] >= Z3_KILL[0]:
                verdict = " -- AT THE KILL LINE"
            elif z["races"] >= Z3_PASS[0] and z["losses"] <= Z3_PASS[1]:
                verdict = " -- PASSED the %d bar" % Z3_PASS[0]
            elif z["races"] >= Z3_PASS_ALT[0] and z["losses"] <= Z3_PASS_ALT[1]:
                verdict = " -- PASSED the %d bar" % Z3_PASS_ALT[0]
            stopped = ""
            if (z3_span or {}).get("last") and not verdict and "z3" not in fl["race_arms"] \
                    and ((z3_span or {}).get("end") or now - z3_span["last"] > 6 * 3600):
                stopped = (" Neither passed nor killed: it STOPPED %s at %d of %d races, so the bar does not move "
                           "until it runs again." % (et_str(z3_span["last"], "%b %d"), z["races"], Z3_PASS_ALT[0]))
            L.append("")
            L.append("🎯 <b>z3 bar</b>: %d races so far, %d loss%s (first 50: %d). Pass = %d races with %d losses, "
                     "or %d with at most %d. Kill = %d losses in the first %d%s.%s" % (
                         z["races"], z["losses"], "" if z["losses"] == 1 else "es", z["first50_losses"],
                         Z3_PASS[0], Z3_PASS[1], Z3_PASS_ALT[0], Z3_PASS_ALT[1], Z3_KILL[0], Z3_KILL[1],
                         ("<b>%s</b>" % esc(verdict)) if verdict else "", esc(stopped)))
        arms, L = L, page
        if all_stopped:
            L.append("")
            L.append("🧪 <b>Paper arms</b>: none running -- all %d stopped, the last on %s. Their record on the live "
                     "bot's races is under the tap below." % (n_arms, esc(et_str(last_ran, "%b %d") if last_ran else "?")))
            extra = [esc(x) for a in arms for x in html_to_plain(a).split("\n") if x.strip()]
        else:
            L += arms
            extra = []
        L.append("")
        L.append(details(det + run_det + extra, "🔎 Legs, prices and break-even by window; each arm's whole run"
                         + (" and the stopped paper arms" if extra else "") + " (tap)"))
        return Html("\n".join(L))

    # ---- /funds /bank /accounts ----
    def text_funds(self):
        """Every Kalshi account's money (funds_read) with each bot's bet size (funds_sizes) and its last
        FUNDS_DAYS ET days of gains and losses (funds_hist: botstats' settlement rows, this page's own pull only
        for an account botstats could not give). A failure costs this command only."""
        try:
            getter = self.funds_getter or _bs().default_getter()
            f = funds_read(getter)
            now = self.now()
            act = self.active()
            return funds_text(f, funds_sizes(self.ledger.results, act), now,
                              funds_hist(getter, f["subs"], now, bs_getter=self.bs_getter), active=act)
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /funds: %s\nEverything else still works -- /bots shows each bot pot's "
                    "cash." % str(e)[:200])

    # ---- /speed and /server (2026-10-27: the move to the AWS server) ----
    def text_speed(self):
        """/speed (operator 10-27: "Yes add speed"): did the move to the server win orders the laptop used to lose? The
        pin bot's orders home against server, what speed added in $ (an estimate), and a line for each other bot whose
        log allows it (speed_gather). No Kalshi read: the pin orders are the Ledger's, already in memory."""
        try:
            d = speed_gather(self.ledger.results, self.ledger.orders, self.now(), active=self.active())
            return speed_html(d, (self.ledger.bank() or {}).get("bank"))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /speed: %s\nEverything else still works -- /fills has today's pin orders."
                    % str(e)[:200])

    def text_server(self, arg=""):
        """/server (operator 10-27: "add server command ... add server funds and cost and spending too"): the machine,
        the time to Kalshi, every pot's money (botstats' cache, no Kalshi read) and the AWS bill. `/server help` gives
        the console steps that connect the AWS cost. The self-test plants every reading (machine_fn, ping_fn, pots_fn,
        aws_http)."""
        if arg.strip().lower() in ("help", "?", "aws", "setup"):
            return SERVER_HELP
        try:
            now = self.now()
            m = (self.machine_fn or machine_read)()
            ping = (self.ping_fn or kalshi_ping)()
            try:
                pots = (self.pots_fn or _bs().cached_pots)()
            except Exception as e:                              # noqa: BLE001
                log(traceback.format_exc())
                pots = {"err": str(e)[:120]}
            aws = aws_cost(now, http=self.aws_http)
            pins = pin_speed_orders(self.ledger.orders)
            return server_html(m, ping, pots, aws, aws_estimate(now), now,
                               speed_stats(_speed_win(pins, SERVER_SINCE_EPOCH - SPEED_HOME_DAYS * 86400,
                                                      SERVER_SINCE_EPOCH)),
                               speed_stats(_speed_win(pins, SERVER_SINCE_EPOCH, now + 1)), active=self.active())
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /server: %s\nEverything else still works -- /funds has every account's money."
                    % str(e)[:200])

    # ---- /bars ----
    def text_bars(self):
        """Every running test against its pre-registered bar: research/bars.py's
        text, unchanged. NOT rebuilt here (the /brief rule): one place decides
        PASS / KILL / EXTEND / TOO EARLY, and the phone quotes it."""
        if self.bars_fn is not None:
            return bars_html(self.bars_fn())
        self._bars_d = None
        try:
            import bars
            # bars.text() is render(gather()); gathered here so /bars' picture uses these very numbers
            d = bars.gather(self.ledger.results, self.now())
            self._bars_d = d
            return bars_html(bars.render(d))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /bars: %s\nEverything else still works -- /stats and /racestats "
                    "carry the raw numbers." % str(e)[:200])

    # ---- controls ----
    def control(self, which):
        if self.busy:
            return CONTROL_REPLY["busy"]
        self.busy = True

        def worker():
            try:
                if which == "start":
                    pindesk.do_start(lambda m: self.say("start: " + m))
                elif which == "pause":
                    pindesk.do_pause(lambda m: self.say("pause: " + m), lambda s: self.say(s))
                elif which == "stop":
                    pindesk.do_stop(lambda m: self.say("stop: " + m))
                time.sleep(3)
                self.say(self.text_status())
            except Exception as e:                        # noqa: BLE001
                self.say("%s failed: %s" % (which, e))
                log(traceback.format_exc())
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()
        return CONTROL_REPLY[which]

    # ---- dispatch ----
    def handle(self, chat_id, text):
        """Reply text for one incoming message, or None to ignore it."""
        text = (text or "").strip()
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower().split("@")[0]
        if cmd == "/pair":
            if arg.strip() and arg.strip() == str(self.cfg.get("secret", "")).strip():
                self.cfg["chat_id"] = chat_id
                self.save_cfg()
                log("paired with chat %s" % chat_id)
                return Html("<b>Paired.</b> This chat now controls the bot.\n\n" + help_text(self.active()))
            log("refused pairing from chat %s" % chat_id)
            return None
        if self.chat_id is None or chat_id != self.chat_id:
            return None                                  # not ours: silence
        self.ledger.refresh()
        if cmd in ("/status", "/s", "/start@"):
            return self.text_status()
        if cmd == "/today":
            return self.text_day(et_day(self.now()), "Today")
        if cmd == "/yesterday":
            return self.text_day(et_day(self.now() - 86400), "Yesterday")
        if cmd == "/days":
            return self.text_days()
        if cmd == "/open":
            return self.text_open()
        # NOT `/today` -- that command already exists and gives the plain
        # money for the day. Taking its name would have silently replaced
        # something he uses with something longer.
        if cmd in ("/fills", "/bets"):
            return self.text_fills()
        if cmd in ("/brief", "/summary"):
            return self.text_brief()
        if cmd == "/market":
            return self.text_market()
        if cmd == "/losses":
            return self.text_losses()
        if cmd == "/hedges":
            return self.text_hedges()
        if cmd == "/stats":
            return self.text_stats()
        cmd_bot = _bots.by_command(cmd)                 # v-tg-rebuild step 5: /race /racestats and BOT_CMDS
        if cmd_bot is not None:
            if cmd_bot.name not in self.active():        # v-tg-active: a paused or retired bot is not shown
                return self.text_hidden(cmd_bot.name)
        if cmd == "/race":
            return self.text_race()
        if cmd == "/racestats":
            return self.text_racestats()
        if cmd == "/bots":
            return self.text_bots()
        if cmd in BOT_CMDS:
            return self.text_bot(BOT_CMDS[cmd])
        if cmd == "/bars":
            return self.text_bars()
        if cmd in ("/funds", "/bank", "/accounts"):
            return self.text_funds()
        if cmd == "/speed":
            return self.text_speed()
        if cmd == "/server":
            return self.text_server(arg)
        if cmd == "/pause":
            return self.control("pause")
        if cmd == "/start":
            return self.control("start")
        if cmd == "/stop":
            if arg.strip().lower() == "yes":
                return self.control("stop")
            return STOP_ASK
        if cmd == "/mute":
            self.muted = True
            return Html("🔕 Alerts off. /unmute to turn them back on.")
        if cmd == "/unmute":
            self.muted = False
            return Html("🔔 Alerts on.")
        if cmd == "/features":
            return self.text_features()
        if cmd == "/update":
            return self.text_update()
        if cmd in ("/help", "/?"):
            return help_text(self.active())
        return Html("I did not understand that.\n\n" + help_text(self.active()))

    def text_features(self):
        """/features (operator 10-22): every bot's job and its settings as boot_all.ps1 has them now, plus the
        ladder's rails from ladder_live.py -- features_html reads both files on each call. No Kalshi read."""
        try:
            return features_html(active=self.active(), procs=self.bs_procs)
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return "Could not build /features: %s" % str(e)[:200]

    def text_update(self):
        """/update (operator 10-22): load the newest phone code. This process runs elevated, so nothing else can
        restart it: it self-tests the files on disk off the poll thread and, only if they pass, the poll loop
        confirms the /update message to Telegram (so the new process does not answer it again) and exits;
        boot_all.ps1 (every 10 min) starts the missing phone link on the new code."""
        if getattr(self, "_updating", False):
            return Html("🔄 An update check is already running.")
        self._updating = True
        chat = self.chat_id

        def work():
            try:
                bad = []
                for f in (os.path.join(HERE, "pinphone.py"), os.path.join(HERE, "botstats.py")):
                    r = subprocess.run([sys.executable, "-u", f, "--selftest"], cwd=os.path.dirname(HERE),
                                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
                    if r.returncode != 0:
                        bad.append("%s (exit %s)" % (os.path.basename(f), r.returncode))
                if bad:
                    self.say(Html("⚠️ <b>Update NOT applied</b>: the new code failed its self-test: %s. The phone keeps "
                                  "running the old code." % esc(", ".join(bad))), chat_id=chat)
                    return
                self.say(Html("✅ <b>New code passed its self-test.</b> Restarting the phone link now; it is back on "
                              "the new code within ~10 minutes (boot_all) and says hello."), chat_id=chat)
                self._exit_now = True                     # the poll loop confirms the offset, then exits
            except Exception as e:                       # noqa: BLE001
                log(traceback.format_exc())
                self.say("Update check failed: %s" % str(e)[:200], chat_id=chat)
            finally:
                self._updating = False
        threading.Thread(target=work, daemon=True).start()
        return Html("🔄 <b>Checking the newest phone code</b> (self-test, a few minutes)…")

    def update_flag_tick(self):
        """results/pinphone.update (2026-10-26: the new /losses waited for the operator's /update while they slept;
        this elevated process can be restarted by nothing else). The file's presence runs /update exactly as the
        command does -- the two self-tests first, the old code kept on a failure, every step said in Telegram. The
        file is removed before anything runs, so it fires once. The reply said, or None when there is no flag."""
        if self.chat_id is None or not os.path.exists(UPDATE_FLAG):
            return None
        try:
            _paths.check_write(UPDATE_FLAG)          # v-tg-rebuild step 2: never the live flag under KALS_TESTING=1
            os.remove(UPDATE_FLAG)
        except OSError:
            return None
        log("update flag %s found: running /update" % UPDATE_FLAG)
        r = Html(str(self.text_update()) + "\n" + i_("asked for by the update flag file, not a message"))
        self.say(r)
        return r

    # ---- alerts ----
    def alerts_tick(self):
        """Called every poll cycle. Sends only on CHANGE."""
        if self.chat_id is None:
            return []
        sent = []
        self.ledger.refresh()
        h = self.health_fn()
        state, hl, det, _c = status_of(h)
        now = self.now()
        today = et_day(now)
        if self.last_state is None:
            # first tick after a (re)start: learn, do not announce. A daily
            # summary already due today is marked done, or every restart of
            # this program would re-send it.
            if (now - et_day_start(today)) >= 8 * 3600:
                self.last_daily = today
        # Every alert is laid out by an alert_* function; if that ever fails, the plain words it always had
        # go instead (fmt_or_plain) -- a layout bug must never swallow an alert.
        if self.last_state is not None and state != self.last_state and not self.muted:
            prev = self.last_state
            msg = fmt_or_plain(lambda: alert_state_text(prev, state, hl, det),
                               lambda: "STATE CHANGED: %s -> %s\n%s\n%s" % (prev, state, hl, det))
            self.say(msg)
            sent.append(msg)
        self.last_state = state
        # THE RECORDERS. 2026-09-21 the Kalshi recorder was alive and deaf for
        # 4 h 47 min and nothing told the operator; the tape from those hours
        # is gone for good. Same rule as the bot: send only on a CHANGE.
        silent = [n for n, k in (("Kalshi recorder", "kalshi_ok"),
                                 ("Exchange recorder", "feeds_ok"))
                  if h.get(k) is False]
        rec = ("SILENT: " + ", ".join(silent)) if silent else "writing"
        if self.last_rec is not None and rec != self.last_rec and not self.muted:
            was = self.last_rec
            if silent:
                msg = fmt_or_plain(lambda: alert_recorder_text(rec, pindesk.REC_FRESH_S // 60),
                                   lambda: ("RECORDER %s -- nothing written for %d+ min. That tape "
                                            "cannot be recreated later. If the bot is also BLIND, "
                                            "the problem is the connection to Kalshi, not our "
                                            "programs." % (rec, pindesk.REC_FRESH_S // 60)))
            else:
                msg = fmt_or_plain(lambda: alert_recorder_back_text(was),
                                   lambda: "RECORDERS WRITING AGAIN (was %s)" % was)
            self.say(msg)
            sent.append(msg)
        self.last_rec = rec
        # THE DISK. Tracked even when muted, so an unmute does not replay it.
        self.disk_level, dmsg = disk_alert(self.disk_level, h.get("disk_gb"))
        if dmsg and not self.muted:
            level = self.disk_level
            msg = fmt_or_plain(lambda: disk_alert_html(dmsg, level), lambda: dmsg)
            self.say(msg)
            sent.append(msg)
        losses = self.ledger.losing_closes()
        keys = {k for k, _n, _l in losses}
        if self.seen_losses is None:
            self.seen_losses = keys
        else:
            new = [x for x in losses if x[0] not in self.seen_losses]
            self.seen_losses = keys
            for close, net, legs in new:
                if not self.muted:
                    msg = fmt_or_plain(lambda: alert_loss_text(self.ledger, close, net, legs),
                                       lambda: "LOSS " + story_loss(self.ledger, close, net, legs))
                    self.say(msg)
                    sent.append(msg)
        if (now - et_day_start(today)) >= 8 * 3600 and self.last_daily != today and not self.muted:
            self.last_daily = today
            yday = et_day(now - 86400)
            msg = fmt_or_plain(lambda: self.daily_alert(yday, now),
                               lambda: "YESTERDAY\n" + story_day(self.ledger, yday, now=now))
            self.say(msg)
            sent.append(msg)
        return sent

    def daily_alert(self, d, now):
        """The 8 AM summary (2026-10-26 screen pass): yesterday over EVERY pot -- /yesterday's headline (its % of
        all pots), the bot-by-bot table (each bot's % of its bank) and the averages -- then the main account's
        story (story_day, pindesk) behind a tap. The old main-account-only summary when botstats cannot be read."""
        base = alert_daily_text(self.ledger, d, now)
        top = self._all_bots_day(d, "Yesterday")
        if not top or top[0].startswith("❔"):
            return base
        return Html("\n".join(["☀️ <b>YESTERDAY, %s</b> · every bot" % esc(_day_long(d))] + top + [
            "", details(str(base).split("\n"), "🏦 %s (main account): the day's story -- tap"
                        % (lambda w: w[:1].upper() + w[1:])(main_words(self.active())))]))

    # ---- charts (2026-10-18) ----
    def chart_after(self, chat_id, text):
        """Queue the picture for a command whose words were just sent. NEVER RAISES AND NEVER WAITS: the poll
        loop puts one job on a short queue and goes on; one background thread (_chart_loop) draws it and sends
        it. Only the paired chat, only a command research/tgcharts.py draws (never /pause /start /stop), and
        nothing while charts are off. A full queue drops the picture (logged); the words already went.
        Returns True when queued."""
        try:
            if not self.charts_on or chat_id is None or chat_id != self.chat_id:
                return False
            cmd = (text or "").strip().partition(" ")[0].lower().split("@")[0]
            tgc = _tgc()
            kind = tgc.kind_of(cmd)
            if kind is None:
                return False
            job = {"kind": kind, "cmd": cmd, "chat": chat_id, "queued": time.monotonic(),
                   "ctx": self._chart_ctx(kind, tgc)}
            try:
                self._chart_queue().put_nowait(job)
            except queue.Full:
                log("chart for %s skipped: %d pictures already waiting" % (cmd, CHART_QUEUE))
                return False
            return True
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return False

    def _chart_ctx(self, kind, tgc):
        """What the picture reads, fixed right after the words were built: the clock, a private copy of the
        ledger's lists (this thread keeps appending to the live ones), botstats' getter and process table as
        the words use them, and /bars' gathered numbers."""
        act = self.active()
        ctx = {"now": self.now(), "pp": sys.modules[__name__], "bs_getter": self.bs_getter,
               "bs_procs": self.bs_procs, "funds_what": {n: funds_what(n, act) for n in FUNDS_WHAT}, "active": act}
        if kind in tgc.LEDGER_KINDS:
            ctx["ledger"] = self._ledger_snapshot()
        if kind == "bars":
            ctx["bars"] = self._bars_d
        return ctx

    def _ledger_snapshot(self):
        import copy
        s = copy.copy(self.ledger)
        for k in ("settled", "orders", "hedges", "autosize", "external", "halts", "starts", "closes"):
            v = getattr(self.ledger, k, None)
            if isinstance(v, list):
                setattr(s, k, list(v))
        return s

    def _chart_queue(self):
        if self._chart_q is None:
            self._chart_q = queue.Queue(maxsize=CHART_QUEUE)
            threading.Thread(target=self._chart_loop, name="charts", daemon=True).start()
        return self._chart_q

    def _chart_loop(self):
        while True:
            job = self._chart_q.get()
            try:
                self._chart_one(job)
            except Exception:                                   # noqa: BLE001
                log(traceback.format_exc())
            finally:
                self._chart_q.task_done()

    def _chart_one(self, job):
        stale = self.chart_stale_s if self.chart_stale_s is not None else _tgc().STALE_S
        waited = time.monotonic() - job["queued"]
        if waited > stale:
            log("chart for %s dropped: its turn came %.0f s after the words (limit %d s)" % (job["cmd"], waited, stale))
            return
        t0 = time.monotonic()
        try:
            got = (self.chart_fn or _tgc().build)(job["kind"], job["ctx"])
        except ImportError as e:
            if "matplotlib" in str(e):
                self.charts_on = False
                log("charts OFF until restart: %s -- the words still go. Fix: C:\\Python314\\python.exe -m pip "
                    "install matplotlib, then restart pinphone." % e)
                return
            raise
        if not got:
            log("chart for %s: nothing live to draw (%.1f s)" % (job["cmd"], time.monotonic() - t0))
            return
        data, caption = got
        if len(data) > CHART_MAX_BYTES:
            log("chart for %s not sent: %d bytes is over %d" % (job["cmd"], len(data), CHART_MAX_BYTES))
            return
        for k, wait in enumerate((0,) + PHOTO_TRIES):      # 2026-10-23: the connection dropped charts that night
            if wait:
                time.sleep(wait)
            try:
                self.tg.send_photo(job["chat"], data, caption)
                break
            except Exception as e:                          # noqa: BLE001
                if k == len(PHOTO_TRIES) or not net_error(e):
                    raise
                log("chart for %s: send failed (%s) -- trying again in %d s" % (job["cmd"], e, PHOTO_TRIES[k]))
        log("SENT PHOTO for %s: %d KB, drawn in %.1f s -- %s" % (job["cmd"], len(data) // 1024,
                                                                 time.monotonic() - t0, (caption or "")[:120]))

    # ---- main loop ----
    def poll_once(self, timeout=25):
        if getattr(self, "_exit_now", False):           # /update passed: confirm what was handled, then leave
            try:
                self.tg.get_updates(self.offset, timeout=0)
            except Exception:                           # noqa: BLE001
                pass
            log("/update: exiting so boot_all starts the new code")
            os._exit(0)
        try:
            updates = self.tg.get_updates(self.offset, timeout=timeout)
        except Exception as e:                            # noqa: BLE001
            log("getUpdates failed: %s" % e)
            time.sleep(10)
            return
        for u in updates:
            self.offset = max(self.offset or 0, int(u.get("update_id", 0)) + 1)
            m = u.get("message") or {}
            chat = (m.get("chat") or {}).get("id")
            handled = True
            try:
                reply = self.handle(chat, m.get("text"))
            except Exception as e:                        # noqa: BLE001
                reply = "error: %s" % e
                handled = False
                log(traceback.format_exc())
            if reply:
                self.say(reply, chat_id=chat)
                if handled:
                    self.chart_after(chat, m.get("text"))     # queued, never drawn here (see chart_after)

    def run(self):
        log("pinphone starting; paired chat: %s; charts %s" % (self.chat_id, "on" if self.charts_on else "off"))
        # the process table for /stats and /race, read off the poll thread
        threading.Thread(target=proc_refresher, daemon=True).start()
        if self.chat_id:
            self.say(UP_TEXT)
        while True:
            try:
                _paths.check_write(HEARTBEAT)        # v-tg-rebuild step 2: never the live heartbeat under KALS_TESTING=1
                with open(HEARTBEAT, "w") as fh:
                    fh.write(time.strftime("%Y-%m-%dT%H:%M:%S"))
            except OSError:
                pass
            self.poll_once()
            try:
                self.update_flag_tick()
            except Exception:                            # noqa: BLE001
                log(traceback.format_exc())
            try:
                self.alerts_tick()
            except Exception:                            # noqa: BLE001
                log(traceback.format_exc())
            try:
                self.resend_tick()
            except Exception:                            # noqa: BLE001
                log(traceback.format_exc())


# ===========================================================================
def selftest():
    import tempfile
    import calendar
    # v-tg-rebuild step 2 (2026-10-30): a self-test never writes a LIVE file -- botdata/paths.py's fence refuses any
    # write under the real results\ or C:\kals while KALS_TESTING=1 (before this the pinphone self-test appended its
    # fake sends to the real results\pinphone.log)
    os.environ["KALS_TESTING"] = "1"

    def ck(cond, msg):
        cprint(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinphone selftest: FAILED -- " + msg)

    def P(x):
        """What the phone shows: an Html reply without its tags; a plain reply as it is."""
        return html_to_plain(x) if getattr(x, "is_html", False) else ("" if x is None else str(x))

    def fits(x):
        """Every message the transport would send for this reply is under Telegram's limit, and each
        one's tags are balanced (no tag left open across a cut)."""
        parts = split_html(x) if getattr(x, "is_html", False) else split_text(x)
        return all(len(c) <= MAX_LEN and not _open_after([], c) for c in parts)

    # ---- the presentation layer (2026-10-18) -------------------------------------------------------
    ck(esc("a<b & c>d") == "a&lt;b &amp; c&gt;d" and html_to_plain(Html("<b>x &lt; y &amp; z</b>")) == "x < y & z",
       "esc() escapes & < >; html_to_plain() gives back what the phone shows")
    ck(norm_money("Made $+1008.55, worst $-131.98, fees $248.98, $83,156 risked, per $100") ==
       "Made +$1,008.55, worst -$131.98, fees $248.98, $83,156 risked, per $100"
       and norm_money("stake $N + $N would pass the $N cap") == "stake $N + $N would pass the $N cap",
       "norm_money: one money style ('+$1,008.55'), the digits untouched, non-money '$N' left alone")
    ck(usd(1008.554) == "+$1,008.55" and usd(-4.57) == "-$4.57" and usd(0.004) == "$0.00" and usd(None) == "?"
       and dollars(1294.5) == "$1,294.50", "usd / dollars: sign first, thousands separators")
    ck(table([("Day", "Money", "Lost"), ("10-18", "+$7.10", "0/8"), ("10-17", "+$90.46", "0/34"),
              ("x", "nothing settled")]) ==
       ["Day     Money Lost", "10-18  +$7.10  0/8", "10-17 +$90.46 0/34", "x     nothing settled"],
       "table(): the first column left, numbers right-aligned; a short row spans and does not widen columns")
    ck(ret(7.10, 262.73, 2) == "+2.70%" and ret(-0.91, 3.907) == "-23.3%" and ret(1.0, 0) == "" and ret(None, 5) == ""
       and pct1(8, 8) == "100%" and pct1(0, 3) == "0%" and pct1(87, 88) == "98.9%" and pct1(1, 0) == "-",
       "ret(): money on what bought it, signed, '' with no base; pct1(): one decimal, '100%' / '0%' kept narrow")
    ck(tg_html_problems("<b>a</b> <i>b &amp; c &lt;</i> <pre>x\ny</pre> <blockquote expandable><b>t</b>\nz"
                        "</blockquote> <code>c</code>") == []
       and tg_html_problems("a < b") and tg_html_problems("<blockquote><pre>x</pre></blockquote>")
       and tg_html_problems("<b><code>x</code></b>") and tg_html_problems("<b>open") and tg_html_problems("<p>x</p>")
       and tg_html_problems("&nbsp;") and tg_html_problems("<b>x</i>"),
       "tg_html_problems(): Telegram's rules -- a raw <, pre/code inside a quote or a bold, an unclosed or "
       "unknown tag, an unknown entity, a tag closed out of order")
    # ---- the 30-day average day (2026-10-29), beside the 7-day one, which must not move -----------------------------
    _bsx = _bs()
    _td = "2026-10-29"
    _d7 = [{"day": _bsx.shift_day(_td, -k), "money": 9.0 if k == 0 else 1.0, "pot_pct": p_, "before_first": False}
           for k, p_ in enumerate((9.0, 1.0, 2.0, 0.0, 1.5, 0.5, 1.0))]
    _d30 = [{"day": _bsx.shift_day(_td, -k), "markets": 1, "money": 5.0 if k <= 10 else 2.0,
             "pot_pct": 2.5 if k <= 10 else 1.0, "before_first": False} for k in range(1, 31)]
    _m30 = {"days_7": _d7, "days_30": _d30}
    ck(bs_avg_day_line(_m30) == "📈 <b>Average day, last 6 full days: +1.0% of its bank</b>"
       and bs_avg_day_line(_m30, 1.0) == ("📈 <b>Average day, last 6 full days: +1.0% of its bank</b> (goal 1.0%) · "
                                          "4 of 6 days at 1.0%+"),
       "the 7-day line is unchanged by the 30-day one: today left out, 6 full days, mean of each day's %% (%s)"
       % bs_avg_day_line(_m30))
    _a30 = _bsx.avg_day(_d30)
    ck(_a30 == {"days": 30, "money": 3.0, "pot_pct": 1.5, "pct_days": 30, "first": "2026-09-29", "young": False}
       and bs_avg30_line(_m30) == "📈 <b>Average day, last 30 full days: +1.5% of its bank</b> (+$3.00 a day)"
       and bs_avg30_line(_m30, 1.0).endswith(" · 30 of 30 days at 1.0%+"),
       "the 30-day line: the 30 full days before today, $ a day = (10 x 5 + 20 x 2) / 30, %% = the mean of each "
       "day's %% of its bank (10 x 2.5 + 20 x 1.0) / 30; the ladder's goal count over the same days: %s"
       % bs_avg30_line(_m30, 1.0))
    _young = [dict(d, before_first=k >= 4, markets=0 if k >= 4 else 1, money=0.0 if k >= 4 else d["money"])
              for k, d in enumerate(_d30)]
    _young[2] = dict(_young[2], markets=0, money=0.0, pot_pct=0.0)                 # a quiet day after its first: $0, 0%
    _young[3] = dict(_young[3], pot_pct=None)                                      # its first day's bank unknown
    _ay = _bsx.avg_day(_young)
    ck(_ay["days"] == 4 and _ay["young"] and _ay["first"] == "2026-10-25" and abs(_ay["money"] - 15.0 / 4) < 1e-9
       and abs(_ay["pot_pct"] - 5.0 / 3) < 1e-3 and _ay["pct_days"] == 3
       and bs_avg30_line({"days_30": _young}) == ("📈 <b>Average day, since Oct 25, 4 days: +1.7% of its bank</b> "
                                                  "(+$3.75 a day) · % over the 3 days its bank is known"),
       "a bot younger than 30 days (first market Oct 25): every day it has, labelled 'since Oct 25, 4 days'; a quiet "
       "day after its first counts $0 and 0%%; a day whose bank is unknown leaves only the %% mean: %s"
       % bs_avg30_line({"days_30": _young}))
    ck(_bsx.avg_day([dict(d, before_first=True) for d in _d30]) is None and bs_avg30_line({"days_30": []}) is None,
       "no day on its books in the 30 -> no 30-day line")
    _run = {"alive": True, "stop_flag": False}
    _opn = {"ok": True, "count": 0}
    _aa = {"bots": {b_: {"running": _run, "open": _opn, "money": {"ok": True, "days_30": _young if b_ == "fx" else _d30,
                                                                    "last_7_days": {"markets": 1}}}
                    for b_ in _bsx.BOTS},
           "other": {"ok": True, "days_30": [dict(d, markets=0, money=0.0) for d in _d30]},
           "total_days_30": _d30}
    _tb = bots_avg_table(_aa)
    _tl = html_to_plain(Html("\n".join(_tb))).split("\n")
    ck(_tl[1] == "📈 Average day, last 30 full days" and _tl[2].split() == ["Bot", "a", "day", "of", "bank", "Days"]
       and _tl[3].split() == ["pin", "+$3.00", "+1.5%", "30"] and _tl[-2].split() == ["ALL", "+$3.00", "+1.5%", "30"]
       and any(x_.split() == ["fx", "+$3.75", "+1.7%", "4*"] for x_ in _tl) and not any(x_.startswith("other") for x_ in _tl)
       and "* every day it has: fx since Oct 25" in _tl[-1] and max(len(x_) for x_ in _tl[2:-1]) <= 40
       and not tg_html_problems(Html("\n".join(_tb))),
       "/days and /bots: the 30-day table, a row a bot and ALL, the young FX taker starred with its first day, "
       "'other' with nothing in the 30 days left out, <= 40 characters wide, Telegram-valid")
    # log() NEVER RAISES: boot_all redirects stdout to a file, which on this box is cp1252 and cannot hold an
    # emoji. Before 2026-10-18 the raise came out of say() after the send and out of poll_once() before
    # Telegram heard the update was handled -- the process died and its restart answered the command again.
    import io as _io
    _so, _lg0 = sys.stdout, globals()["LOG"]
    with tempfile.TemporaryDirectory() as _tdl:
        globals()["LOG"] = os.path.join(_tdl, "x.log")
        sys.stdout = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252", errors="strict")
        try:
            log("SENT: 🟢 Today +$7.10 · ▁▂█ → ok")
            _raised = None
        except Exception as e:                                  # noqa: BLE001
            _raised = e
        finally:
            sys.stdout.flush()
            _con = sys.stdout.buffer.getvalue().decode("cp1252")
            sys.stdout = _so
        with open(globals()["LOG"], encoding="utf-8") as _fh:
            _filed = _fh.read()
        globals()["LOG"] = _lg0
    ck(_raised is None and "\\U0001f7e2 Today +$7.10" in _con and "🟢 Today +$7.10 · ▁▂█ → ok" in _filed,
       "log(): a cp1252 console cannot print an emoji -- the console copy falls back to escapes, the utf-8 log "
       "keeps the real line, and nothing raises (raised: %r)" % (_raised,))
    ck(hbar(10, 10, 5) == "█████" and hbar(5, 10, 5) == "██▌" and hbar(-3, 10, 5) == "░░" and hbar(0, 10) == ""
       and hbar(0.01, 1000, 5) == "▏" and spark([1, 2, 3]) == "▁▅█",
       "text charts: full blocks and eighths, light shade for a loss, a sliver for a tiny gain")
    _big = Html("<b>Head</b>\n\n" + "\n".join("line %d %s" % (k, "x" * 60) for k in range(40)) + "\n<pre>"
                + "\n".join("row %d %s" % (k, "y" * 50) for k in range(80)) + "</pre>\n"
                + details([esc("detail %d %s" % (k, "z" * 70)) for k in range(30)]))
    _parts = split_html(_big, 1500)
    ck(len(_parts) > 3 and all(len(c) <= 1500 and not _open_after([], c) for c in _parts)
       and html_to_plain("\n".join(_parts)).replace("\n", "") == html_to_plain(_big).replace("\n", ""),
       "split_html: every message under the limit, every tag closed in the message that opened it and opened "
       "again in the next, nothing lost (%d parts)" % len(_parts))
    ck(split_html(Html("short")) == ["short"], "split_html: a short reply is one message, untouched")
    _sent = []

    def _fake_call(method, params, http_timeout=45):
        _sent.append(dict(params))
    _tr = Telegram("tok")
    _tr._call = _fake_call
    _tr.send(1, Html("<b>hi</b>"))
    _tr.send(1, "plain <b>as before</b>")
    ck(_sent[0].get("parse_mode") == "HTML" and _sent[0]["text"] == "<b>hi</b>"
       and "parse_mode" not in _sent[1] and _sent[1]["text"] == "plain <b>as before</b>",
       "the transport: an Html reply goes with parse_mode=HTML; a plain str goes exactly as it always did")
    _sent[:] = []

    def _refuse_html(method, params, http_timeout=45):
        if params.get("parse_mode"):
            raise urllib.error.HTTPError("x", 400, "Bad Request: can't parse entities", None, None)
        _sent.append(dict(params))
    _tr._call = _refuse_html
    _st_log0 = globals()["LOG"]
    with tempfile.TemporaryDirectory() as _tdl:
        globals()["LOG"] = os.path.join(_tdl, "x.log")
        _tr.send(1, Html("<b>LOSS -$4.57</b> x &lt; y"))
        globals()["LOG"] = _st_log0
    ck(_sent == [{"chat_id": 1, "text": "LOSS -$4.57 x < y"}],
       "...and if Telegram refuses the markup (HTTP 400) the same words go again as plain text -- never lost")
    with tempfile.TemporaryDirectory() as _tdl:
        globals()["LOG"] = os.path.join(_tdl, "x.log")
        _fp = fmt_or_plain(lambda: 1 / 0, lambda: "plain words")
        _fp2 = fmt_or_plain(lambda: Html("<b>laid out</b>"), lambda: "plain words")
        globals()["LOG"] = _st_log0
    ck(_fp == "plain words" and getattr(_fp2, "is_html", False) and _fp2 == "<b>laid out</b>",
       "fmt_or_plain: an alert whose layout fails goes out in its plain words; one that lays out goes as Html")

    _st_log = LOG
    with tempfile.TemporaryDirectory() as td:
        # every log() line the self-test causes (each "sent" reply) goes to this temp folder: the live phone
        # bot appends to results/pinphone.log, and a self-test's fake replies there would read as sent
        globals()["LOG"] = os.path.join(td, "pinphone.log")
        p = os.path.join(td, "pinrun-live-20260916T135734Z.jsonl")
        c1, c2 = "KXBNB15M-26SEP161000-00", "KXBTC15M-26SEP161015-15"
        rows = [
            {"kind": "start", "t": "2026-09-16T13:00:00Z", "size": 20, "hedge_belief": 0.6},
            {"kind": "autosize", "t": "2026-09-16T13:00:01Z", "old": 20, "new": 85, "why": "bank $500.00"},
            {"kind": "signal", "t": "2026-09-16T13:59:30Z", "ticker": c1, "want": "no", "price": 0.98, "edge_c": 1.5, "size": 85, "take_n": 85, "tau": 29, "fair": 0.004, "spot": 700.1, "strike": 700.2, "digits": 2},
            {"kind": "order", "t": "2026-09-16T13:59:31Z", "ticker": c1, "filled": 85.0, "exec_price": 0.979, "status": "executed", "body": {"count": "85.00"}},
            {"kind": "settled", "t": "2026-09-16T14:00:20Z", "ticker": c1, "want": "no", "result": "no", "cost": 0.979, "pnl_c": 166.26, "realised": 1.6626},
            {"kind": "close_summary", "t": "2026-09-16T14:00:05Z", "close": calendar.timegm((2026, 9, 16, 14, 0, 0)), "looks": 1000, "no_offer": 600, "tradeable": 100, "fired": True, "gates": {}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        L = Ledger(results=td)
        L.refresh()
        # PIN THE DEPOSITS. deposited() reads the REAL account's deposit
        # records (pinxfer), so this fixture's "+0.33% of $500" read +0.28%
        # the day real deposits reached $584.46 -- the self-test was failing
        # on the operator's money, not on the code.
        L.deposited = lambda: 500.0
        state = {"h": {"pid": 4242, "alive": True, "flag": None, "quiet_s": 12, "watchdog_s": 5, "open": {},
                       "halt": None, "kalshi_ok": True, "feeds_ok": True, "disk_gb": 30.0}}
        now = {"t": calendar.timegm((2026, 9, 16, 15, 0, 0))}           # 11 AM ET Sep 16
        tg = FakeTelegram()
        cfgp = os.path.join(td, "telegram.json")
        ph = Phone({"token": "x", "secret": "open sesame"}, tg, ledger=L, health_fn=lambda: state["h"],
                   cfg_path=cfgp, now_fn=lambda: now["t"])
        ck(ph.bs_getter is None and ph.bs_procs is None,
           "by default /bots /pin /fc /ladder read Kalshi through botstats' own getter (kauth.get, GET only)")

        # ---- the botstats sandbox ------------------------------------------
        # /race (below) and /bots /pin /forecaster /ladder read Kalshi through
        # botstats. A self-test must never reach the real Kalshi nor write the
        # real cache, so botstats' results folder moves into this temp dir and
        # the phone gets a fake Kalshi and a process table. Every number the
        # checks expect was worked by hand from the rows planted here; the
        # phone's clock is 11:00 AM ET, Wed Sep 16.
        import botstats as _bsm
        _bs_saved = (_bsm.RESULTS, dict(_bsm._MEMO), dict(_bsm._BACK))

        def _bs_sandbox(name):
            d = os.path.join(td, name)
            os.makedirs(d)
            _bsm.RESULTS = d
            _bsm._MEMO.update(key=None, data=None)
            _bsm._BACK.clear()
            return d

        def _S(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0):
            return {"ticker": tk, "settled_time": st, "market_result": res, "value": {"yes": 100, "no": 0}[res],
                    "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc,
                    "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc,
                    "fee_cost": "%.6f" % fee, "revenue": 0}
        _bs_world = {
            "0": [_S("KXBTC15M-26SEP161030-30", "2026-09-16T14:30:05Z", "no", nn=50, nc=49.00, fee=0.10),     # pin +0.90
                  _S("KXETH15M-26SEP160945-45", "2026-09-16T13:45:05Z", "yes", yn=40, yc=38.80, nn=40, nc=12.00,
                     fee=0.50),                                     # pin, both sides: 40 - 50.80 - 0.50 = -11.30
                  _S("KXSOL15M-26SEP152345-45", "2026-09-16T03:45:05Z", "yes", yn=30, yc=29.40, fee=0.06),    # pin +0.54, Sep 15
                  _S("KXCRYPTOLEAD15M-26SEP161015-XRP", "2026-09-16T14:16:00Z", "yes", yn=20, yc=19.60, fee=0.03),  # race +0.37
                  _S("KXWTI15M-26SEP151400-00", "2026-09-15T18:00:05Z", "no", yn=5, yc=4.50, fee=0.01)],     # other -4.51
            "1": [_S("KXNEAR15M-26SEP161030-30", "2026-09-16T14:30:05Z", "yes", yn=2, yc=1.958)],             # ladder +0.042
            "2": [_S("KXETH15M-26SEP161000-00", "2026-09-16T14:00:06Z", "no", yn=5, yc=2.45, fee=0.09),       # fc -2.54
                  _S("KXXRP15M-26SEP152300-00", "2026-09-16T03:00:06Z", "yes", yn=3, yc=2.42, fee=0.0328)]}   # fc +0.5472, Sep 15
        _bs_pos = {"0": [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00", "market_exposure_dollars": "29.10"},
                         {"ticker": "KXCRYPTOLEAD15M-26SEP161100-SOL", "position_fp": "20.00",
                          "market_exposure_dollars": "19.60"}]}
        _bs_bal = {"0": "1000.0000", "1": "15.1000", "2": "24.0000"}
        _bs_mode = {"m": "planted"}
        _bs_asked = []

        # The account's books (2026-10-02, the pot percentages). Planted so every pot RECONCILES: cash +
        # open bets = money put in + every settled market (main 1048.70 = 1062.70 - 14.00; ladder 15.10 =
        # 15.06 + 0.042; forecaster 24.00 = 25.99 - 1.9928), so no pot-check warning is due.
        def _T(s):
            return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
        _bs_books = {
            "transfers": [{"amount_cents": 2000, "created_ts": _T("2026-09-14T12:00:00Z"), "from_subaccount": 0,
                           "to_subaccount": 2},                                   # $20 main -> forecaster
                          {"amount_cents": 200, "created_ts": _T("2026-09-15T20:00:00Z"), "from_subaccount": 2,
                           "to_subaccount": 0},                                   # $2 back, 4 PM ET Sep 15
                          {"amount_cents": 1506, "created_ts": _T("2026-09-16T13:00:00Z"), "from_subaccount": 0,
                           "to_subaccount": 1},                                   # $15.06 -> ladder, 9 AM today
                          {"amount_cents": 799, "created_ts": _T("2026-09-16T13:30:00Z"), "from_subaccount": 0,
                           "to_subaccount": 2}],                                  # $7.99 -> forecaster today
            "deposits": [{"amount_cents": 100575, "fee_cents": 0, "status": "applied",
                          "finalized_ts": _T("2026-09-01T12:00:00Z")},
                         {"amount_cents": 10000, "fee_cents": 200, "status": "applied",   # $98 after the fee,
                          "finalized_ts": _T("2026-09-15T14:00:00Z")}],                   # 10 AM ET yesterday
            "withdrawals": [],
            # as Kalshi lists it since 2026-10-04: subaccounts 1 and 2 also hold an empty pool-0 row, and
            # subaccount 3 (the weather dip-seller) lives in pool 0 -- empty in this world
            "subaccount_balances": [{"subaccount_number": 0, "exchange_index": 0, "balance": "0.0000"},
                                    {"subaccount_number": 0, "exchange_index": 2, "balance": "1000.0000"},
                                    {"subaccount_number": 1, "exchange_index": 0, "balance": "0.0000"},
                                    {"subaccount_number": 1, "exchange_index": 2, "balance": "15.1000"},
                                    {"subaccount_number": 2, "exchange_index": 0, "balance": "0.0000"},
                                    {"subaccount_number": 2, "exchange_index": 2, "balance": "24.0000"},
                                    {"subaccount_number": 5, "exchange_index": 2, "balance": "0.0000"},   # the FX taker's pot (2026-10-25), empty here
                                    {"subaccount_number": 4, "exchange_index": 0, "balance": "0.0000"},   # its currency pot (pool 0, 10-25), empty here
                                    {"subaccount_number": 3, "exchange_index": 2, "balance": "0.0000"},   # the jump band's pool (10-30), empty here
                                    {"subaccount_number": 3, "exchange_index": 0, "balance": "0.0000"}]}
        # the WEATHER world (2026-10-04): $50 moved main -> subaccount 3 in POOL 0 at 3 AM ET Sep 15; one Sep 15
        # bracket settled (NY: sold YES at 40c x2, NO won, +0.80) and one is open (MIA NO x2, $1.10). Cash in
        # pool 0 = 50 + 0.80 - 1.10 = 49.70; the pot held $0 at midnight Sep 15 + the $50 moved in = $50.
        _wx_books = dict(_bs_books)
        _wx_books["transfers"] = _bs_books["transfers"] + [
            {"amount_cents": 5000, "created_ts": _T("2026-09-15T07:00:00Z"), "from_subaccount": 0, "to_subaccount": 3,
             "exchange_index": 0}]
        _wx_books["subaccount_balances"] = _bs_books["subaccount_balances"][:-1] + [
            {"subaccount_number": 3, "exchange_index": 0, "balance": "49.7000"}]

        def _bs_fake(path, q):
            _bs_asked.append((path, dict(q or {})))
            if _bs_mode["m"] == "down":
                return 401, {"error": "unauthorized"}
            wx = _bs_mode["m"] == "weather"
            for _lp, _lk, _pg in _bsm.LEDGERS:
                if path == _lp:
                    if _bs_mode["m"] == "noledger":
                        return 404, {}
                    return 200, {_lk: [] if _bs_mode["m"] == "empty" else (_wx_books if wx else _bs_books)[_lk],
                                 "cursor": ""}
            sub, empty = str((q or {}).get("subaccount")), _bs_mode["m"] == "empty"
            if wx and sub == "3":
                if path == "/portfolio/settlements":
                    return 200, {"settlements": [_S("KXHIGHNY-26SEP15-B72.5", "2026-09-16T14:00:05Z", "no", nn=2,
                                                    nc=1.20)], "cursor": ""}
                if path == "/portfolio/positions":
                    return 200, {"market_positions": [{"ticker": "KXHIGHMIA-26SEP16-B90.5", "position_fp": "-2.00",
                                                       "market_exposure_dollars": "1.10"}], "cursor": ""}
            if path == "/portfolio/settlements":
                return 200, {"settlements": [] if empty else _bs_world.get(sub, []), "cursor": ""}
            if path == "/portfolio/positions":
                return 200, {"market_positions": [] if empty else _bs_pos.get(sub, []), "cursor": ""}
            if path == "/portfolio/balance":
                # Kalshi answers for the NAMED pool only: each pot's trading pool as botstats has it (SUB_POOL: pot 3 is
                # pool 2 since the jump band, 10-30; the weather world below runs on its old pool 0)
                if (q or {}).get("exchange_index") != _bsm.SUB_POOL.get(sub, 2):
                    return 200, {"balance": 0, "balance_dollars": "0.0000"}
                if wx and sub == "3":
                    return 200, {"balance": 0, "balance_dollars": "49.7000"}
                return 200, {"balance": 0, "balance_dollars": "0.0000" if empty else _bs_bal.get(sub, "0")}
            return 404, {}
        _bs_procs = [
            (3882400, "2026-09-16T11:59:50Z", r"C:\Python314\python.exe -u C:\kals-repo\research\pinrun.py --live "
                                              r"--size 20 --max-losses 2"),
            (3739628, "2026-09-16T02:49:58Z", "python -u research/pinracearm.py --live --max-contracts 20 --max-stake 60 "
                                              "--live-tau-max 30 --live-min-price 0.90 --live-max-legs 5"),
            (2574672, "2026-09-15T05:56:08Z", "python -u research/pinracearm.py --paper-live --live-tau-max 60"),
            (4196192, "2026-09-16T12:34:56Z", r"python -u research\cleanroom\forecaster_live.py --subaccount 2 --live "
                                              r"--variant race1_98")]
        _bsdir = _bs_sandbox("botstats-planted")
        with open(os.path.join(_bsdir, "VERSIONS.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# Versions\n\n"
                      "# v-ladder-settlefix -- LIVE 2026-09-16 13:16:12Z (pid 5; research/cleanroom/ladder_live.py): "
                      "the penny ladder waits for yes/no\n"
                      "# v-keepalive-cleanroom -- 2026-09-16 12:37Z (boot_all.ps1): the clean-room bots restart "
                      "themselves -- LIVE forecaster_live and ladder_live\n"
                      "# v-forecaster-race1 -- LIVE 2026-09-16 12:35:02Z (pid 4196192): race1_98\n"
                      "# v-reopen98 + v-floor90 -- 2026-09-16 12:00:17Z (pid 3882400; no code change) -- LIVE: 98c\n"
                      "# v-race20 -- 2026-09-16 02:50Z (pid 3739628; pinracearm.py) -- LIVE: coin race penny bot 20\n")
        with open(os.path.join(_bsdir, "forecaster-live-orders.jsonl"), "w", encoding="utf-8") as _fh:
            for _r in ({"t": "2026-09-16T12:35:02.502Z", "ev": "start", "pid": 4196192, "live": True,
                        "variant": "race1_98", "rails": {"scale": "0.05", "per_side": 5, "per_close": 20,
                                                         "max_commit": 22.0, "px": [0.75, 0.985],
                                                         "day_stop": -12.0, "run_stop": -20.0}},
                       {"t": "2026-09-16T13:59:30.000Z", "ev": "placed", "filled": 5.0},
                       {"t": "2026-09-16T13:59:30.100Z", "ev": "live_fill", "n": 5, "ticker": "KXETH15M-26SEP161000-00",
                        "side": "yes", "px": 0.49},
                       {"t": "2026-09-16T13:59:41.000Z", "ev": "refused", "why": "in_flight"}):
                _fh.write(json.dumps(_r) + "\n")
        os.utime(os.path.join(_bsdir, "forecaster-live-orders.jsonl"), (now["t"] - 30, now["t"] - 30))
        with open(os.path.join(_bsdir, "ladder-live.stop"), "w", encoding="utf-8") as _fh:
            _fh.write("stood down by the operator")
        ph.bs_getter, ph.bs_procs = _bs_fake, _bs_procs

        # Plant a Kalshi ledger for the fixture: money comes from Kalshi now,
        # so a test that wants a TODAY figure has to provide Kalshi's books.
        import pinledger as _pl
        _pl_sv = _pl.LEDGER
        _pl.LEDGER = os.path.join(td, "kalshi_ledger.json")
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump({"settlements": {"k1": {
                "ticker": c1, "market_result": "no",
                "no_count_fp": "85.00", "no_total_cost_dollars": "83.30",
                "yes_count_fp": "0.00", "yes_total_cost_dollars": "0.00",
                "revenue": 8500, "fee_cost": "0.0374",
                "settled_time": "2026-09-16T14:00:20Z"}}}, _fh)
        ck(ph.handle(111, "/status") is None, "before pairing, every message is ignored")
        ck(ph.handle(111, "/pair wrong words") is None and ph.chat_id is None, "a wrong secret is refused silently")
        r = ph.handle(111, "/pair open sesame")
        ck(r and P(r).startswith("Paired") and ph.chat_id == 111 and "Commands" in P(r),
           "the right secret pairs the chat, and the reply carries the help")
        ck(json.load(open(cfgp))["chat_id"] == 111, "...and the chat id is saved to the config file")
        ck(ph.handle(222, "/status") is None, "another chat is still ignored after pairing")
        s = ph.handle(111, "/status")
        ck("TRADING" in P(s) and "Checked just now" in P(s) and "process 4242 is OPEN" in P(s),
           "/status carries the state and its evidence")
        ck(P(s).split("\n")[0].startswith("🟢 TRADING"), "/status: the state is the headline")
        # MONEY COMES FROM KALSHI NOW, not from the log this test plants, so
        # "today" is legitimately empty here. The bank still comes from the
        # bot's own autosize record, which is ours to read.
        ck("Main account $500.00 (pin bot + coin race)" in P(s) and "Pin + race today " in P(s)
           and "💼 All pots $1,039.10" in P(s) and "+19." not in P(s),
           "/status carries the main account's bank (no % against every pot's money -- 10-26), every pot's cash and "
           "the main account's Today line, named as such")
        t = ph.handle(111, "/today")
        _tl = P(t).split("\n")
        # 2026-10-23 (operator: "/today doesn't show the right total it says 11.22 right now it's really 24.85"): the
        # headline is EVERY bot's money (botstats.all_bots, the /bots number); the main account follows, as before
        # 2026-10-26 ("/yesterday doesn't look good or show % of bank return"): a bot-by-bot table with each bot's
        # % of its own bank, its return on the bets and its losers; the main account's block behind a tap
        ck(_tl[0].split(" ", 1)[-1].startswith("All bots today") and "% of all pots)" in _tl[0]
           and "🏦 Pin bot + coin race (main account)" in P(t) and "📊 By bot" in P(t)
           and any(x.split() == ["ALL", "-$12.53", "-1.1%", "-10.1%", "2/5"] for x in _tl)
           and any(x.split() == ["forecaster", "-$2.54", "-9.6%", "-103.7%", "1/1"] for x in _tl)
           and "🟢 Pin + race +$1.66 (+0.33% of the bank)" in _tl and "1 of 1 closes won (100.0%), 0 lost" in P(t)
           and "of the $500.00 it held at the start of the ET day" in P(t) and not tg_html_problems(t),
           "/today: every bot's money as the headline, then the main account's money and its %% of the bank at day "
           "start, then closes won with their %%: %r" % P(t)[:600])
        ck("+2.00% on the $83.34 staked" in P(t),
           "/today: the return on what the bets cost, from Kalshi's books (+1.6626 on 83.30 + 0.0374 fees) -- "
           "shown because Kalshi's money for the day is the headline's money")
        ck("No settled bets" in P(ph.handle(111, "/yesterday")), "/yesterday with nothing settled says so")
        # /market (2026-10-26, operator: "include which bot made the trades"): the FX taker's own log, planted for this
        # check and /fills' below (removed after them): three fills on markets closing at 10:00 AM ET and an order that
        # got nothing; the forecaster's planted fill is ETH 10:00 YES x5
        _fxlog = os.path.join(_bsdir, "fxtake-live-orders.jsonl")
        with open(_fxlog, "w", encoding="utf-8") as _fh:
            for _r in ({"t": "2026-09-16T13:59:31Z", "kind": "fill", "ticker": "KXEURUSD15M-26SEP161000-00", "side": "no",
                        "n": 10.0, "px": 0.99},
                       {"t": "2026-09-16T13:59:32Z", "kind": "fill", "ticker": "KXGOLD15M-26SEP161000-00", "side": "yes",
                        "n": 10.0, "px": 0.99},
                       {"t": "2026-09-16T13:59:33Z", "kind": "fill", "ticker": "KXWTI15M-26SEP161000-00", "side": "yes",
                        "n": 10.0, "px": 0.985},
                       {"t": "2026-09-16T13:59:34Z", "kind": "placed", "ticker": "KXSILVER15M-26SEP161000-00",
                        "filled": 0.0}):
                _fh.write(json.dumps(_r) + "\n")
        # v-tg-active (2026-10-30): the FX taker runs for /market and /fills (a bot that does not run is not named)
        _fxp = (676, "2026-09-16T00:00:00Z", r"python -u research\cleanroom\fxtake_live.py --subaccount 5 --live")
        ph.bs_procs = _bs_procs + [_fxp]
        _mk = P(ph.handle(111, "/market"))
        _mk10 = [x for x in _mk.split("\n") if x.startswith("10:00 AM · ")]
        ck("Sellers:" in _mk and _mk10 == ["10:00 AM · sellers 40.00% · pin bot bought 85 (BNB NO) · forecaster 5 "
                                           "(ETH YES) · FX taker 3 markets x10"] and "BOUGHT" not in _mk,
           "/market: each close names who bought -- the pin bot's own count with its coin and side (its signal), then "
           "every other bot's buys on the markets closing then, from its own log (the FX taker's 3 summed): %r" % _mk)
        ck(buys_words("forecaster", [{"ticker": "KXETH15M-26SEP161000-00", "side": "yes", "contracts": 26},
                                     {"ticker": "KXBTC15M-26SEP161000-00", "side": "yes", "contracts": 2.02}])
           == "forecaster 26 (ETH YES) + 2.02 (BTC YES)"
           and buys_words("race", [{"ticker": "KXCRYPTOLEAD15M-26SEP161000-SOL", "side": "yes", "contracts": 2}])
           == "coin race 2 (SOL YES)"
           and buys_words("ladder", [{"ticker": "KXNEAR15M-X", "side": "yes", "contracts": 96},
                                     {"ticker": "KXZEC15M-X", "side": "no", "contracts": 96},
                                     {"ticker": "KXXRP15M-X", "side": "yes", "contracts": 95}])
           == "ladder 3 markets, 287 contracts",
           "/market's words a bot: one or two markets each named with its side; three or more summed")
        # THE DAILY BRIEFING REACHES THE PHONE, and a failure inside it must
        # not take the command down -- he reads this when the app is not in
        # front of him.
        # /fills -- the operator's ask: filled, paid, seconds out, per order.
        _fl = ph.handle(111, "/fills")
        ck("Pin bot orders today:" in P(_fl) or "No pin bot orders today" in P(_fl),
           "/fills answers with the pin bot's orders today or says there were none")
        ck("🧾 Other bots' fills today: 4 (each bot's own log)\nforecaster 1 fill, 5 contracts · FX taker 3 fills, 30 "
           "contracts\n9:59a · FX taker · WTI 10:00 AM YES x10 · 98.5c\n9:59a · FX taker · GOLD 10:00 AM YES x10 · 99.0c\n"
           "9:59a · FX taker · EURUSD 10:00 AM NO x10 · 99.0c\n9:59a · forecaster · ETH 10:00 AM YES x5 · 49.0c" in P(_fl),
           "/fills (10-26): every other bot's fills today from its own log, a count a bot, then newest first, each line "
           "naming its bot -- the order that got nothing is not a fill: %r" % P(_fl))
        ck(ph.handle(111, "/bets") == _fl, "/bets is the same command")
        ph.bs_procs = _bs_procs                     # the FX taker stops: its fills are 'earlier bots', never named
        _fl0, _mk0 = P(ph.handle(111, "/fills")), P(ph.handle(111, "/market"))
        ck("FX taker" not in _fl0 and "earlier bots 3 fills, 30 contracts" in _fl0
           and "9:59a · earlier bots · GOLD 10:00 AM YES x10 · 99.0c" in _fl0
           and "forecaster 5 (ETH YES) · earlier bots 3 markets x10" in _mk0 and "FX taker" not in _mk0,
           "v-tg-active: a bot that is not running is not named on /fills or /market; a fill in its log (there should "
           "be none) is said as 'earlier bots', never dropped")
        _sv_o = L.orders
        L.orders = [
            {"t": now["t"], "tk": "KXBTC15M-26SEP180100-00", "filled": 77.0,
             "asked": 77.0, "price": 0.968, "tau": 12},
            {"t": now["t"], "tk": "KXETH15M-26SEP180100-00", "filled": 0.0,
             "asked": 50.0, "price": None, "tau": 30},
            {"t": now["t"], "tk": "KXWTI15M-26SEP180100-00", "filled": 20.0,
             "asked": 20.0, "ask_seen": 0.945, "tau": None},
        ]
        try:
            _f2 = P(ph.handle(111, "/fills"))
            _row = [x for x in _f2.split("\n") if "77/77" in x]
            ck(len(_row) == 1 and "96.8c" in _row[0] and _row[0].rstrip().endswith("12s"),
               "an order shows what filled, the price PAID in cents, and how "
               "many seconds were left -- the three things he asked for, on one table row")
            ck("0/50" in _f2 and "1 lost the race" in _f2 and _f2.split("\n")[0] ==
               "🧾 Pin bot orders today: 3 · 2 filled · 1 filled nothing (33%)",
               "a ZERO-FILL order is shown, not hidden -- about one order in "
               "five fills nothing, and dropping them would report a 100% fill "
               "rate; the headline counts it with its share")
            ck("94.5c" in _f2 and "(oil)" in _f2,
               "an oil order shows its price from `ask_seen` and says (oil) "
               "where the seconds would be, because cmdlive does not record a "
               "tau on the order")
            ck("got 97 (65.99%)" in _f2, "...and the footer totals contracts asked vs got, with the share")
            ck(max(len(x) for x in _f2.split("\n")[2:6]) <= 36, "/fills: the table fits a phone's width")
        finally:
            L.orders = _sv_o
        os.remove(_fxlog)                       # the FX taker's planted log: only for /market and /fills above
        _br = ph.handle(111, "/brief")
        ck("THE DAY --" in _br or "Could not build" in _br,
           "/brief answers with the daily briefing, or says plainly that it "
           "could not build one")
        # the briefing reads the live clock and live files, so two calls a
        # second apart can differ; assert the ROUTING, not the wording
        _sv_tb = ph.text_brief
        try:
            ph.text_brief = lambda: "BRIEF-STUB"
            ck(ph.handle(111, "/summary") == "BRIEF-STUB" == ph.handle(111, "/brief"),
               "/summary is the same command under its other name")
        finally:
            ph.text_brief = _sv_tb
        ck("THE DAY --" not in P(ph.handle(111, "/today") or ""),
           "and /today is UNTOUCHED -- it already existed and gives the plain "
           "money for the day; taking its name would have quietly replaced "
           "something he uses with something longer")
        # THE OPPORTUNITY TREND REACHES THE PHONE, and a health dict that does
        # not carry it must not break the command -- the operator reads
        # /market from his phone when the app is not in front of him.
        state["h"]["supply_lines"] = ["Cheap offers: up 7% on a normal day."]
        state["h"]["supply_age_d"] = 0.5
        mk = P(ph.handle(111, "/market"))
        ck("IS THE OPPORTUNITY GOING AWAY?" in mk and "up 7%" in mk,
           "/market carries the opportunity trend, from the same lines the "
           "desktop shows, so the two cannot drift apart")
        ck("0.5 days ago" in mk,
           "...and says how old the measurement is, because a stale trend is a "
           "reassuring number about a week that already ended")
        state["h"].pop("supply_lines")
        ck("Sellers:" in P(ph.handle(111, "/market")),
           "NULL: a health reading with no opportunity block still answers")
        _lo = P(ph.handle(111, "/losses"))
        _lb = _lo.split("By bot")
        ck(_lo.startswith("🔴 3 losing markets of 8 settled, every bot (37.5%)")
           and "Wed Sep 16\n-$2.54 (" in _lo and "Forecaster · ETH 10:00 AM YES x5" in _lo
           and "Pin bot · ETH 9:45 AM hedged x80" in _lo and "Tue Sep 15\n-$4.51" in _lo and "Other · WTI 2:00 PM YES x5" in _lo
           and _lo.index("Forecaster · ETH") < _lo.index("Pin bot · ETH") < _lo.index("Other · WTI")
           and len(_lb) == 2 and "Coin race" not in _lb[0] and "Ladder" not in _lb[1] and "Earlier bots  0/1" in _lb[1]
           and "ALL" in _lb[1] and "3/8" in _lb[1]                  # v-tg-active: the stopped ladder is 'Earlier bots'
           and fits(ph.handle(111, "/losses")),
           "/losses (10-26): EVERY bot's losing markets from Kalshi's books -- the forecaster's and the old oil bot's "
           "too -- each named by bot, newest day first, with side and contracts; the pin's hedged market on its own "
           "line; a bot-by-bot table: %r" % _lo)
        ck(ph.handle(111, "/hedges") == "No hedges yet.", "/hedges with none")
        _op = P(ph.handle(111, "/open"))
        ck(_op.startswith("📂 Coin race: 1 open · $19.60 at risk") and "race SOL 11:00 AM YES x20 · $19.60" in _op
           and "Pin bot" not in _op,
           "/open: every pot -- no pin bet open here (its own log), the coin race's one open leg from Kalshi's "
           "positions (botstats), with what is at risk: %r" % _op)
        _dd = P(ph.handle(111, "/days"))
        ck(_dd.startswith("🔴 All bots last 7 days -$15.95 (-10.0% on $160.13 staked · -1.4% of all pots)")
           and "all time -$15.95 (-1.4% on the $1,103.75 put in)" in _dd
           and any(x.split()[:6] == ["Sep", "16", "-$12.53", "-1.1%", "-10.1%", "2/5"] for x in _dd.split("\n"))
           and any(x.split() == ["ALL", "-$15.95", "-1.4%", "-10.0%", "3/8"] for x in _dd.split("\n"))
           and "Sep 16: +$1.66 (+0.33% of the bank) · 0 of 1 closes lost" in _dd,
           "/days: every bot's week as the headline with its % of all pots, all time on the money put in, each day's "
           "% of all pots, the week bot by bot, the main account's own days (with % of its bank) behind a tap")
        # ---- /stats, /race, /racestats -----------------------------------
        # A planted world: Kalshi's books (the ONLY money source), the bots'
        # order records (only for seconds-left), a VERSIONS.md, the live
        # bot's size / high-water / day-loss files, a process table, the
        # penny bot's log and two paper race arms' logs. Every expected
        # number below was worked by hand from the rows planted here.
        _led0 = open(_pl.LEDGER, encoding="utf-8").read()

        def _row(tk, res, yes_n=0, yes_c=0, no_n=0, no_c=0, fee=0.0, value=None,
                 st="2026-09-16T14:00:20Z"):
            r = {"ticker": tk, "market_result": res,
                 "yes_count_fp": "%.2f" % yes_n, "yes_total_cost_dollars": "%.6f" % yes_c,
                 "no_count_fp": "%.2f" % no_n, "no_total_cost_dollars": "%.6f" % no_c,
                 "fee_cost": "%.6f" % fee, "revenue": 0, "settled_time": st}
            if value is not None:
                r["value"] = value
            return r
        B_ = "KXBTC15M-26SEP151015-15"          # 09-15: lost 40 NO at 97c, no hedge  -38.80
        C_ = "KXETH15M-26SEP141030-30"          # 09-14: hedged loss -14.10, hedge got back +5.00
        D_ = "KXSOL15M-26SEP091200-00"          # 09-09: won +2.45 (lifetime only)
        E_ = "KXWTI15M-26SEP070500-00"          # 09-07: BEFORE live -- must be excluded
        F_ = "KXXRP15M-26SEP091300-00"          # 09-09: a FULL hedge (equal counts), lost -36.50
        G_ = "KXDOGE15M-26SEP091400-00"         # 09-09: hedge BIGGER than the entry, won by net +29.80
        R1X, R1B = "KXCRYPTOLEAD15M-26SEP160500-XRP", "KXCRYPTOLEAD15M-26SEP160500-BTC"
        R2X, R2H = "KXCRYPTOLEAD15M-26SEP160715-XRP", "KXCRYPTOLEAD15M-26SEP160715-HYPE"
        R3_ = "KXCRYPTOLEAD15M-26SEP150930-ETH"
        _plant = json.loads(_led0)
        _plant["settlements"].update({
            "b": _row(B_, "yes", no_n=40, no_c=38.80, st="2026-09-15T14:15:20Z"),
            "c": _row(C_, "yes", yes_n=10, yes_c=5.00, no_n=20, no_c=19.00, fee=0.10, st="2026-09-14T14:30:20Z"),
            "d": _row(D_, "yes", yes_n=50, yes_c=47.50, fee=0.05, st="2026-09-09T16:00:20Z"),
            "e": _row(E_, "yes", yes_n=10, yes_c=9.00, st="2026-09-07T09:00:20Z"),
            "f": _row(F_, "yes", yes_n=79, yes_c=40.00, no_n=79, no_c=75.00, fee=0.50, st="2026-09-09T17:00:20Z"),
            "g": _row(G_, "yes", yes_n=79, yes_c=23.70, no_n=26, no_c=25.20, fee=0.30, st="2026-09-09T18:00:20Z"),
            "r1x": _row(R1X, "yes", yes_n=1, yes_c=0.97, fee=0.0021, value=100, st="2026-09-16T09:00:38Z"),
            "r1b": _row(R1B, "no", no_n=1, no_c=0.98, fee=0.0014, value=0, st="2026-09-16T09:00:38Z"),
            "r2x": _row(R2X, "scalar", yes_n=1, yes_c=0.97, fee=0.0021, value=50, st="2026-09-16T11:15:38Z"),
            "r2h": _row(R2H, "scalar", no_n=1, no_c=0.98, fee=0.0014, value=50, st="2026-09-16T11:15:38Z"),
            "r3": _row(R3_, "yes", no_n=1, no_c=0.85, fee=0.006, value=100, st="2026-09-15T13:30:38Z"),
        })
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump(_plant, _fh)
        os.utime(_pl.LEDGER, (time.time() + 20, time.time() + 20))
        with open(os.path.join(td, "VERSIONS.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# v-race-tie1 -- 2026-09-16 ~14:0xZ -- COIN RACE, LIVE penny test: ties\n\nbody\n\n"
                      "# v-pinfix -- 2026-09-16 12:30Z (pid 1, code_sha abc) -- LIVE: a fix\n\n"
                      "# v-older -- 2026-09-15 -- LIVE: no time on this one\n")
        for _nm, _d in (("pinrun-live-size.json", {"size": 79.0, "bank": 930.04, "at": "2026-09-16T14:21:42Z"}),
                        ("pinrun-hwm.json", {"hwm": 1037.33, "at": "2026-09-15T23:48:38Z"}),
                        ("pinrun-dayloss.json", {"day": "2026-09-16", "realised": 11.1424})):
            with open(os.path.join(td, _nm), "w", encoding="utf-8") as _fh:
                json.dump(_d, _fh)
        _procs = [
            (2554960, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --live --size 20 --hedge-belief 0.40 --loss-cap 200 --bank-brake 4.00'),
            (11, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --size 20 --hedge-belief 0.40 --pin 0.985 --arm-name arm-pin0.985'),
            (12, r'"C:\Python314\python.exe" -u C:\kals-repo\research\cmdarm.py --minutes 4320 --series KXWTI15M --out C:\kals-repo\results\cmdarm-wide230.jsonl'),
            (13, r'C:\Python314\python.exe -u research/pinracearm.py --minutes 4320 --log C:/kals-repo/results/pinracearm-racectl.jsonl --model fair'),
            (14, r'C:\Python314\python.exe -u research/pinracearm.py --paper-live --minutes 10080 --min-z 3.0 --log C:/kals-repo/results/pinracearm-z3.jsonl'),
            (15, r'C:\Python314\python.exe -u research/pinracearm.py --live --max-contracts 1 --max-stake 20 --live-rolling-stake --live-tau-max 30 --minutes 10080 --log C:/kals-repo/results/pinracepenny-live.jsonl'),
            (16, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinphone.py'),
            (17, r'"C:\Python314\python.exe" kalshi_collector.py --key-id x --out ./kalshi_data'),
        ]
        ph.procs_fn = lambda: _procs
        ph.versions_path = os.path.join(td, "VERSIONS.md")
        ph.race30_epoch = calendar.timegm((2026, 9, 16, 0, 0, 0))
        _rails = {"max_contracts": 1.0, "max_stake": 20.0, "tau_max": 30, "min_price": 0.9,
                  "max_legs": 5, "confirm": 5, "clock_tau": 20, "rolling": True,
                  "stop_on_loss": True, "paper": False}
        _penny = os.path.join(td, "pinracepenny-live.jsonl")

        def _w(path, recs, mode="a"):
            with open(path, mode, encoding="utf-8") as _fh:
                for r in recs:
                    _fh.write(json.dumps(r) + "\n")
        _w(_penny, [
            {"kind": "start", "t": "2026-09-16T08:00:00Z", "live": True, "live_rails": _rails},
            {"kind": "live_order", "t": "2026-09-16T08:59:20Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "ticker": R1X, "side": "yes", "filled": 1.0, "exec_price": 0.97, "staked": 0.97},
            {"kind": "live_order", "t": "2026-09-16T08:59:30Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "ticker": R1B, "side": "no", "filled": 1.0, "exec_price": 0.98, "staked": 1.95},
            {"kind": "live_settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 2, "won": 2, "pnl": 0.0465, "staked_open": 0.0},
            {"kind": "live_order", "t": "2026-09-16T11:14:40Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "ticker": R2X, "side": "yes", "filled": 1.0, "exec_price": 0.97, "staked": 0.97},
            {"kind": "live_order", "t": "2026-09-16T11:14:41Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "ticker": R2H, "side": "no", "filled": 1.0, "exec_price": 0.98, "staked": 1.95},
            {"kind": "live_settled", "t": "2026-09-16T11:16:15Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "positions": 2, "won": 2, "pnl": 0.0465, "staked_open": 0.0},
            {"kind": "live_halt", "t": "2026-09-16T13:31:15Z", "staked": 2.81, "sends": 4,
             "why": "first real loss: KXCRYPTOLEAD15M-26SEP160930 no at 85c"},
        ], "w")
        _w(os.path.join(td, "pinracearm-z3.jsonl"), [
            {"kind": "start", "t": "2026-09-15T00:00:00Z", "paper_live": True},
            {"kind": "settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 1, "won": 1, "pnl": 4.65},                       # size-250 paper leg: IGNORED
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T09:01:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160500", "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T11:16:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160715", "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T12:31:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160830", "positions": 1, "won": 0, "pnl": -0.98},
            {"kind": "live_settled", "paper": True, "t": "2026-09-15T13:31:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP150930", "positions": 0, "won": 0, "pnl": 0.0},
        ], "w")
        _w(os.path.join(td, "pinracearm-racectl.jsonl"), [
            {"kind": "settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 2, "won": 2, "pnl": 5.0},
            {"kind": "settled", "t": "2026-09-16T11:16:15Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "positions": 1, "won": 1, "pnl": 4.0},
            {"kind": "settled", "t": "2026-09-15T13:31:15Z", "event": "KXCRYPTOLEAD15M-26SEP150930",
             "positions": 1, "won": 0, "pnl": -212.5},
        ], "w")
        _sv_o, _sv_g = L.orders, L.hedges
        # the bot's hedge record for F: it BOUGHT yes, so the entry was no
        L.hedges = [{"t": calendar.timegm((2026, 9, 9, 16, 59, 58)), "kind": "hedge", "tk": F_,
                     "belief": 0.3, "n": 79, "price": 0.51, "status": "executed", "side": "yes",
                     "entry": 0.95, "tau": 2, "file": "x"},
                    {"t": calendar.timegm((2026, 9, 9, 17, 59, 58)), "kind": "hedge", "tk": G_,
                     "belief": 0.2, "n": 79, "price": 0.30, "status": "executed", "side": "yes",
                     "entry": 0.97, "tau": 3, "file": "x"}]
        L.orders = [
            {"t": calendar.timegm((2026, 9, 16, 13, 59, 48)), "tk": c1, "filled": 85.0, "asked": 85.0, "price": 0.98, "tau": 12},
            {"t": calendar.timegm((2026, 9, 16, 13, 59, 55)), "tk": c1, "filled": 10.0, "asked": 10.0, "price": 0.99, "tau": 5},
            {"t": calendar.timegm((2026, 9, 15, 14, 14, 30)), "tk": B_, "filled": 40.0, "asked": 40.0, "price": 0.97, "tau": 30},
            {"t": calendar.timegm((2026, 9, 14, 14, 29, 20)), "tk": C_, "filled": 20.0, "asked": 20.0, "price": 0.95, "tau": 40},
            {"t": calendar.timegm((2026, 9, 9, 15, 59, 52)), "tk": D_, "filled": 50.0, "asked": 50.0, "price": 0.95, "tau": 8},
        ]
        try:
            # the pure pieces first
            _vs = versions(ph.versions_path)
            ck([v[0] for v in _vs] == ["v-race-tie1", "v-pinfix", "v-older"],
               "VERSIONS.md: every `# v-... -- <date>` header is read, newest first")
            ck(_vs[0][2] is True and _vs[0][1] == calendar.timegm((2026, 9, 16, 14, 0, 0)),
               "a `~14:0xZ` time reads as 14:00 and is marked approximate")
            ck(_vs[1][2] is False and _vs[1][1] == calendar.timegm((2026, 9, 16, 12, 30, 0)),
               "`12:30Z (pid ...)` reads as 12:30 exactly, the pid in brackets ignored")
            ck(_vs[2][1] == et_day_start("2026-09-15") and _vs[2][2] is True,
               "a header with no time is midnight ET of its date, marked approximate")
            ck(live_version(ph.versions_path)[0] == "v-pinfix",
               "the LIVE version skips the coin race's header sitting on top -- v-race-tie1 "
               "is the penny bot's, and dating the up/down bot's window from it would be wrong")
            _fl = fleet(_procs)
            ck(_fl["live"][0] == 2554960 and _fl["penny"][0] == 15,
               "the process table: pinrun --live is the money bot, pinracearm --live (not "
               "--paper-live) is the penny bot")
            ck(_fl["arms"] == ["arm-pin0.985", "cmdarm-wide230"] and _fl["race_arms"] == ["racectl", "z3"],
               "paper arms are named from --arm-name / --out, race arms from --log; the "
               "phone, the collector and the live bots are not arms")
            import re as _re
            with open(os.path.join(HERE, "pinrun.py"), encoding="utf-8", errors="replace") as _fh:
                _mdd = _re.search(r"^MAX_DRAWDOWN = ([0-9.]+)", _fh.read(), _re.M)
            ck(_mdd and abs(float(_mdd.group(1)) - MAX_DRAWDOWN) < 1e-12,
               "the halt line copied here (%.2f) is pinrun.MAX_DRAWDOWN -- drift fails" % MAX_DRAWDOWN)
            _mk = markets_from(raw_ledger(_pl.LEDGER))
            ck(abs(_mk[C_]["pnl"] + 14.10) < 1e-9 and _mk[C_]["hedged"] and _mk[C_]["side"] == "no"
               and abs(_mk[C_]["hedge_pnl"] - 5.00) < 1e-9,
               "a hedged market is ONE market at its net (-14.10), the entry is the bigger side, "
               "and the hedge leg's own take (+5.00) is what it got back")
            ck(_mk[R2X]["tie"] and abs(_mk[R2X]["pnl"] + 0.4721) < 1e-9 and not _mk[R1X]["tie"],
               "Kalshi's value 50 is a tie, paid 50c: -47.21c on a 97c leg")
            ck(abs(_mk[E_]["pnl"] - 1.00) < 1e-9 and _mk[E_]["day"] == "2026-09-07",
               "the pre-live row is parsed (day 09-07)... ")
            ck(_mk[F_]["hedged"] and _mk[F_]["side"] is None and _mk[F_]["hedge_pnl"] is None,
               "a FULL hedge has equal counts: with nothing to break the tie there is no side "
               "and no hedge figure -- never a guess")
            _mkf = markets_from(raw_ledger(_pl.LEDGER), {F_: "no"})
            ck(_mkf[F_]["side"] == "no" and abs(_mkf[F_]["hedge_pnl"] - 39.00) < 1e-9
               and abs(_mkf[F_]["pnl"] + 36.50) < 1e-9,
               "...and the bot's own side breaks it: entry NO, the 79 YES hedge got back "
               "79.00 - 40.00 = +39.00 of a -36.50 market")
            ck(ph._sides().get(F_) == "no",
               "the phone takes that side from the bot's hedge record (it bought YES, so "
               "the entry was NO)")
            _mkg = markets_from(raw_ledger(_pl.LEDGER), ph._sides())
            ck(_mkg[G_]["side"] == "no" and _mkg[G_]["won"] and abs(_mkg[G_]["hedge_pnl"] - 55.30) < 1e-9,
               "a hedge BIGGER than its entry (79 YES over 26 NO): the bot's record, not the "
               "count, names the entry, so the hedge's take is 79.00 - 23.70 = +55.30 on a "
               "market that won +29.80 by its net -- the count rule had booked -25.20")
            _fu = fleet(None)
            ck(_fu["unknown"] and _fu["live"] is None and _fu["arms"] == [],
               "NULL: a process table that could not be read is UNKNOWN, not empty")
            ck(first_entries(L.orders)[c1] == 12,
               "...and the FIRST filled order sets the seconds-left, not the later top-up")

            # /stats
            s = ph.handle(111, "/stats")
            ck(fits(s) and len(split_html(s)) == 1, "/stats fits one Telegram message on this world (%d chars)" % len(s))
            ps = P(s)
            ck(ps.split("\n")[0].startswith("🔴 Lifetime -$57.25 (") and " on $" in ps.split("\n")[0],
               "/stats: lifetime money and its return on what was risked is the headline")
            ck("LIVE v-pinfix since 09/16 08:30 AM ET, pid 2554960." in ps,
               "/stats names the live version, its start in ET and the pid")
            ck("Hedge trigger: belief 40%. Size 79 contracts (auto), bank $930.04 read 10:21 AM." in ps,
               "the hedge trigger from the live argv, the size and bank from the bot's size file")
            ck("Halt if the bank falls to $829.86 (20% under its high of $1,037.33): $100.18 of room (10.8% of the "
               "bank)." in ps,
               "the halt line is 20% under the high-water mark, with the room left in dollars and as a share")
            ck("Today by the bot's own count: +$11.14 (stops at -$200 for the day)." in ps,
               "the day figure from the bot's own file is labelled as the bot's, with the cap")
            ck("Paper arms: 2 (pin0.985, cmdarm-wide230) + 2 race arms (racectl, z3)." in ps,
               "the fleet, counted and named from the process table")
            ck("Coin race: 2 races since 09/15: 1 won (50.0%), 1 tie, 0 lost, -$0.91 (/race)." in ps,
               "the coin race summary line: the tie is a tie, not a win")
            ck(any(x.split() == ["Today", "+$0.76", "+0.9%", "+0.17%", "60.0%", "2"] for x in ps.split("\n"))
               and "of bank = of the main account's bank when the window began" in ps,
               "the window table: money, return on what was risked (0.76 / 87.24), its % of the bank that began the "
               "day (10-26), markets won, losses")
            _blk, _cur = {}, None
            for _ln in ps.split("\n"):                      # the windows' sentences, inside the one quote
                _k = _ln.split(" (")[0].split(":")[0]
                if _k in ("LIFETIME", "LAST 7 DAYS", "LAST 3 DAYS", "TODAY") or _k.startswith("SINCE v-"):
                    _cur = _k
                    _blk[_cur] = _ln
                elif _cur:
                    _blk[_cur] += "\n" + _ln
            ck(set(_blk) >= {"LIFETIME", "LAST 7 DAYS", "LAST 3 DAYS", "TODAY", "SINCE v-pinfix"}
               and s.count("<blockquote expandable>") == 1,
               "five windows: lifetime, 7 days, 3 days, today, since the live version -- in ONE tap-to-open quote")
            _t = _blk["TODAY"]
            ck("Made +$0.76 on $87 risked; 5 mkts, 3 closes, 89 contracts; fees $0.04." in _t,
               "TODAY: 1.6626 + 0.0279 + 0.0186 - 0.4721 - 0.4814 = +0.76 on the 87.24 risked; "
               "5 markets on 3 closes; 89 contracts")
            ck("Best day" not in _t, "a one-day window has no best/worst day line")
            ck("Won 3 of 5 mkts (60.0 of 100); 98.9 of 100 contracts paid; by $ risked 97.8." in _t,
               "win rate by market (3 of 5), by contracts paid (88 of 89: the tie paid half) "
               "and by dollars (85.29 of 87.24)")
            ck("Break-even 98.0 of 100 contracts at 98.0c avg paid (fee in): margin +0.8 pts = +$0.87 per "
               "$100 risked. By count 97.7 of 100 mkts must win; 60.0 did." in _t,
               "break-even = dollars paid / contracts (87.24 / 89 = 98.0c); the margin is against "
               "the contracts paid (98.9 - 98.0) and matches the real profit per $100 risked; "
               "the count version beside it")
            ck("Losses 2: -$0.95, avg -$0.48, worst -$0.48 (coin race, HYPE 09/16); 0 hedged, their hedge legs netted "
               "+$0.00." in _t,
               "TODAY's losses are the two tied legs; the worst names its bot (10-26): the main account holds pin and race")
            _7 = _blk["LAST 7 DAYS"]
            ck("Made -$53.00 on" in _7 and "8 mkts" in _7,
               "LAST 7 DAYS adds 09-15 and 09-14: -38.80 -14.10 -0.856 on top of today (09-09 is outside it)")
            ck("Losses 5: -$54.71, avg -$10.94, worst -$38.80 (pin bot, BTC 09/15); 1 hedged, their hedge legs netted "
               "+$5.00." in _7,
               "...five losses, the worst named, the hedged one counted with what its hedge got back")
            ck("LAST 3 DAYS: the same 8 markets as LAST 7 DAYS, so the same numbers." in _blk["LAST 3 DAYS"],
               "LAST 3 DAYS holds the same markets, so it says so instead of repeating every sentence")
            _l = _blk["LIFETIME"]
            ck("Made -$57.25 on" in _l and "11 mkts" in _l,
               "LIFETIME adds 09-09 (+2.45, the -36.50 full hedge, the +29.80 over-hedge) and "
               "EXCLUDES the 09-07 row: 11 markets, not 12")
            ck("Best day +$0.76 (09/16), worst -$39.66 (09/15); avg -$6.36/day over 9 days." in _l,
               "best and worst ET day, and the average over the calendar days since 09/08")
            ck("Losses 6: -$91.21, avg -$15.20, worst -$38.80 (pin bot, BTC 09/15); 2 hedged, their hedge legs "
               "netted +$44.00; hedge legs on won mkts netted +$55.30." in _l,
               "the FULL hedge counts (5.00 + 39.00 on two hedged losses) and the over-hedge's "
               "+55.30 sits with the won markets")
            ck("First buys: 50% with 20 s or less left (2 mkts, +$4.11), 50% at 21-45 s (2 mkts, -$52.90); 7 not timed." in _l,
               "seconds-left split from the ORDER records, money per bucket, untimed markets counted")
            ck("Lifetime by bot: coin race -$1.76, pin bot -$55.49." in ps,
               "the lifetime money split by bot, by the names a person knows")
            ck("Made +$1.66 on" in _blk["SINCE v-pinfix"] and "1 mkts" in _blk["SINCE v-pinfix"],
               "SINCE the version: only the market that closed after 12:30Z")
            # this planted world's order rows are /stats-shaped (no "close"), so the per-day loop is stubbed
            # out; the since-version line reads Kalshi's books through _markets(), which this world has
            _days0 = ph.ledger.days
            try:
                ph.ledger.days = lambda: []
                _dy = ph.text_days()
            finally:
                ph.ledger.days = _days0
            ck("Pin bot since v-pinfix (" in P(_dy) and ": +$1.66, 1 markets, 0 lost (0.0%)" in P(_dy)
               and P(_dy).startswith("🔴 All bots last 7 days "),
               "/days carries the running version's own line (a deploy day mixes two versions), same money as /stats; "
               "all time is its headline")

            # /race
            r = P(ph.handle(111, "/race"))
            ck("RUNNING, pid 15" in r and "Fixed size: 1 contract a leg, $20 out at most (settled bets give it back)"
               in r and "Buys only inside 30 s, 90c or better, up to 5 legs a race, stops on the first loss." in r,
               "/race: the live race's size and rails in words, from its own start record (a start record with no "
               "bank_sizing is a fixed size, and says so)")
            ck("penny" not in r.lower().replace("pinracepenny", ""),
               "/race never calls the live coin race a penny bot (2026-10-18: it sizes from the bank since "
               "v-race-snowball)")
            ck("STOP RAIL FIRED 09/16 09:31 AM ET: first real loss: KXCRYPTOLEAD15M-26SEP160930 no at 85c. No real order since." in r,
               "the stop-on-first-loss state, with when and why")
            ck(r.split("\n")[0] == "🔴 Coin race today -$0.91 (-23.2% on $3.91 staked) · 1 of 2 won (50%) · 1 tie, 0 lost",
               "today's coin-race money from Kalshi's books is the headline, with its return on what the legs cost "
               "(-0.907 on 3.90 + 0.007 fees) and the races won")
            _lines = r.split("\n")
            _i = _lines.index("🏆 Last 10 races (Kalshi's books)")
            ck(_lines[_i + 1:_i + 8] == ["Wed Sep 16", "7:15a HYPE no 98c -$0.95 TIE", "      XRP yes 97c",
                                         "5:00a BTC no 98c  +$0.05 WON", "      XRP yes 97c", "Tue Sep 15",
                                         "9:30a ETH no 85c  -$0.86 LOST"],
               "the last races newest first, a heading a day: legs, side, price paid, money, TIE / WON / LOST")
            ck("Paper race arms running: racectl, z3." in r, "the race arms from the process table")
            ph.procs_fn = lambda: None
            _ru = P(ph.handle(111, "/race"))
            ck("Running? The process table could not be read." in _ru
               and "Paper race arms running: process table could not be read." in _ru
               and "(process table could not be read)" in P(ph.handle(111, "/stats")),
               "NULL: when the process table cannot be read, /race and /stats SAY so -- "
               "never 'not running' or 'no arms'")
            ph.procs_fn = lambda: _procs
            # a restart clears the halt; a leg on the race closing now is 'holding'
            _w(_penny, [
                {"kind": "start", "t": "2026-09-16T14:40:00Z", "live": True, "live_rails": _rails},
                {"kind": "live_order", "t": "2026-09-16T14:59:40Z", "event": "KXCRYPTOLEAD15M-26SEP161115",
                 "ticker": "KXCRYPTOLEAD15M-26SEP161115-SOL", "side": "yes", "filled": 1.0,
                 "exec_price": 0.98, "staked": 0.98},
            ])
            r2 = P(ph.handle(111, "/race"))
            ck("Stop rail: not fired since the restart at 09/16 10:40 AM ET." in r2,
               "after a restart the rail reads as not fired -- a halt before the restart is history")
            ck("Now: race closing 11:15 AM ET (15:00 left) -- holding SOL yes 98c x1. $0.98 out." in r2,
               "the race closing next, the legs held on it and the dollars out")

            # /racestats
            qh = ph.handle(111, "/racestats")
            q = P(qh)
            ck("ALL TIME (since 09/15): 3 races: 1 won, 1 tie, 1 lost. -$1.76. 5 legs at 95.0c avg; "
               "break-even 95.3 of 100 legs must pay, actual 60.0." in q,
               "/racestats: races won/tie/lost, money, avg leg price, break-even vs actual per leg")
            ck("TODAY: 2 races: 1 won, 1 tie, 0 lost. -$0.91." in q, "...and today's")
            ck(q.split("\n")[0].startswith("🔴 Coin race all time -$1.76 (") and "3 races, 33.3% won" in q.split("\n")[0],
               "the all-time money, its return on what the legs cost and the share of races won lead the page")
            ck(any(x.split() == ["Today", "-$0.91", "-23.2%", "2", "50%", "1/0"] for x in q.split("\n")),
               "the window table: money, return, races, won, ties / losses")
            # the arms: in this world both are RUNNING (the process table names them) and nothing is re-scored
            ck("z3 · PAPER, RUNNING (since Sep 14)" in q and "racectl · PAPER, RUNNING (since Sep 16)" in q,
               "every arm is labelled PAPER, with whether it runs (the process table) and since when (its log)")
            ck(any(x.split() == ["z3", "2", "100%", "50.0%", "1/1/0"] for x in q.split("\n"))
               and any(x.split() == ["racectl", "2", "100%", "50.0%", "1/1/0"] for x in q.split("\n")),
               "a --paper-live arm and a plain arm on the same races: in 2 of 2, 1 won, the race Kalshi tied is a tie")
            ck(any(x.split() == ["z3", "+$0.04*", "-", "-$0.91"] for x in q.split("\n"))
               and any(x.split() == ["racectl", "+$9.00*", "-", "-$0.91"] for x in q.split("\n"))
               and "* = the arm's own log money (no Kalshi re-scoring on file" in q
               and "z3's and racectl's own logs booked a tie as a win" in q,
               "with no re-scoring on file: the arm's own-log money, starred and said so (its log booked the tie "
               "as a win), no live-size figure invented, and the live bot's money on the same races beside it")
            ck("raceedge0: no log." in q and "gap075: no log." in q, "an arm without a log says so")
            ck("z3 bar: 3 races so far, 2 losses (first 50: 2). Pass = 125 races with 0 losses, or 250 "
               "with at most 1. Kill = 2 losses in the first 50 -- AT THE KILL LINE." in q,
               "the z3 bar counts EVERY race the arm entered, a tie as a loss, and names the kill line")
            ck(fits(qh) and not tg_html_problems(qh), "/racestats: one message, Telegram-valid")
            # THE ARMS RE-SCORED ON KALSHI (results/race_arms_scored.json, 2026-10-18): used only while the arm's
            # log is the size it was scored at; z3 here is scored, racectl's file size does not match
            _zsz = os.path.getsize(os.path.join(td, "pinracearm-z3.jsonl"))
            with open(os.path.join(td, RACE_ARMS_SCORED), "w", encoding="utf-8") as _fh:
                json.dump({"made": "2026-10-18T10:00:00Z", "arms": {
                    "z3": {"log_size": _zsz, "own_size": "1 contract a leg",
                           "same": {"races": 2, "own": -0.47, "own_log": 0.04, "at_live": -9.40, "live": -0.91},
                           "run": {"races": 3, "won": 1, "tie": 1, "lost": 1, "own": -1.45, "at_live": -29.0}},
                    "racectl": {"log_size": 1, "own_size": "up to 250 a leg (avg 1)",
                                "same": {"races": 2, "own": 1.0, "own_log": 9.0, "at_live": 1.0, "live": -0.91}}}},
                          _fh)
            q2 = P(ph.handle(111, "/racestats"))
            ck(any(x.split() == ["z3", "-$0.47", "-$9.40", "-$0.91"] for x in q2.split("\n"))
               and any(x.split() == ["racectl", "+$9.00*", "-", "-$0.91"] for x in q2.split("\n"))
               and "z3 · PAPER, RUNNING (since Sep 14) · 1 contract a leg" in q2
               and "their own logs said z3 +$0.04 (a log books a tie as a win" in q2
               and "z3, whole run: 3 races, 1 won, 1 tie, 1 lost; own size -$1.45, at the live bot's size -$29.00." in q2
               and "* = the arm's own log money (its log changed after it was re-scored" in q2,
               "re-scored on Kalshi: z3's own-size money with the tie paid 50c and its money at the live bot's size, "
               "its own log's figure named; racectl's log changed, so its own-log money stays, starred")
            # STOPPED: an arm out of the process table whose log ended is PAPER, STOPPED, with its dates; z3's bar
            # says it cannot move
            _w(os.path.join(td, "pinracearm-z3.jsonl"), [{"kind": "end", "t": "2026-09-16T12:40:00Z"}])
            ph.procs_fn = lambda: [x for x in _procs if x[0] not in (13, 14)]
            q3 = P(ph.handle(111, "/racestats"))
            ck("z3 · PAPER, STOPPED · ran Sep 14 to Sep 16" in q3 and "racectl · PAPER, " in q3
               and "PAPER ARMS -- no real money" in q3,
               "an arm that left the process table, its log ended, reads PAPER, STOPPED with the dates it ran")
            ck(any(x.split() == ["z3", "+$0.04*", "-", "-$0.91"] for x in q3.split("\n")),
               "...and its log grew after it was scored, so the scored figures are no longer used")
            ck("paper made 41% more than real fills" in q3 and "walking the book cuts it 30-66%" in q3,
               "the legend gives the skeptic's paper-optimism figures (41% on the live bot's own legs; touch "
               "pricing of the 250-a-leg arms, 30-66%), not the milder 25%")
            # /racestats on the REAL table reader never reads Windows on the poll thread: with a cold cache it
            # shows the arms from their logs alone and list_python_procs is not called; a fresh cache is used
            _lpp_calls, _lpp0, _procs0 = [], list_python_procs, dict(_PROCS)

            def _lpp_spy(*a, **k):
                _lpp_calls.append(1)
                return []
            globals()["list_python_procs"] = _lpp_spy
            try:
                _PROCS.update(t=0.0, rows=None)
                ph.procs_fn = python_procs
                q4 = P(ph.handle(111, "/racestats"))
                _fresh_ok = (cached_python_procs() is None
                             and (_PROCS.update(t=time.time(), rows=[(7, "x")]) or cached_python_procs()) == [(7, "x")]
                             and (_PROCS.update(t=time.time() - 3 * PROC_REFRESH_S) or cached_python_procs()) is None)
            finally:
                globals()["list_python_procs"] = _lpp0
                _PROCS.clear()
                _PROCS.update(_procs0)
            ck(not _lpp_calls and _fresh_ok and "z3 · PAPER, STOPPED · ran Sep 14 to Sep 16" in q4
               and "PAPER ARMS -- no real money" in q4,
               "/racestats with the real reader and a cold cache: no synchronous WMI read (alerts never wait behind "
               "it), the arms still labelled from their logs; a fresh cache is used, a stale one reads as unknown")
            ph.procs_fn = lambda: _procs
            os.remove(os.path.join(td, RACE_ARMS_SCORED))
            ck(all("/%s" % c in HELP_TEXT for c in ("stats", "race", "racestats", "bars")), "the four are in /help")
            # /bars -- the operator's one-word verdicts. The text is bars.py's,
            # never rebuilt here; the phone only routes it.
            ph.bars_fn = lambda: "BARS-STUB"
            ck(P(ph.handle(111, "/bars")) == "BARS-STUB", "/bars returns bars.py's words unchanged (laid out only)")
            ph.bars_fn = None
            _bt = ph.handle(111, "/bars")
            ck("BARS  " in P(_bt) and "VERDICT:" in P(_bt) and "FRESH OFFER TEST" in P(_bt),
               "...and the real module answers on this world with its header and a verdict")
            _bl = P(_bt).split("\n")
            _okb = (_bl[0].startswith("📏 Bars: ") and "VERDICT: " not in _bl[1]
                    and any(x.startswith(("✅ ", "❌ ", "🔁 ", "⏳ ")) and "FRESH OFFER TEST" in x for x in _bl[:8]))
            ck(_okb, "/bars leads with the verdicts counted, then one line a test named by its section (never the "
                     "verdict line itself)" + ("" if _okb else " -- got %r" % (_bl[:6],)))
            ck(fits(_bt) and not any(tg_html_problems(c) for c in split_html(_bt)),
               "...in messages under Telegram's limit, each one Telegram-valid")
        finally:
            L.orders, L.hedges = _sv_o, _sv_g
            with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
                _fh.write(_led0)
            os.utime(_pl.LEDGER, (time.time() + 30, time.time() + 30))
            L.refresh()

        # ---- /bots /pin /forecaster /ladder, and /race's money windows -----
        # READ ONLY, BY CONSTRUCTION: the new code is scanned for any order,
        # cancel, transfer or process-control word. The words are assembled
        # from pieces so this check does not find itself.
        import inspect as _insp
        _newfns = (_bs, _nof, _cash, _ago, bs_window_line, _short, bs_running_lines, bs_setup_lines, bs_money_lines,
                   bs_open_lines, bs_cash_line, bs_last_lines, bs_activity_lines, bs_bot_text, bs_errors_line,
                   bs_all_text, Phone._race_money_lines, Phone._bs_get, Phone.text_bots, Phone.text_bot,
                   Phone.text_race,
                   # 2026-10-18, the phone layout: every new reader and formatter
                   log_span, race_arms_scored, race_size_words, race_rule_words, race_rows, Phone._staked,
                   Phone.day_html, pct1, ret, tg_html_problems, split_html, bs_bot_html, bs_all_html, bs_money_html,
                   _funds_days_html, _funds_page, fmt_or_plain, alert_loss_text, alert_daily_text, cprint)
        _nsrc = "\n".join(_insp.getsource(f) for f in _newfns)
        _bad = [w for w in (r"\b" + "PO" + r"ST\b", r"\b" + "DEL" + r"ETE\b", r"\b" + "PA" + r"TCH\b", r"\b" + "PU" + r"T\b",
                            "portfolio/" + "orders", "subaccounts/" + "transfer", "order" + "cli", "pin" + "take",
                            "url" + "open", "urllib" + r"\.request", r"do_" + "(stop|pause|start)", r"self\." + "control",
                            "Stop-" + "Process", r"\b" + "kill", "termin" + "ate", "sub" + "process", r"os\." + "remove")
                if re.search(w, _nsrc)]
        ck(not _bad and len(_nsrc) > 5000,
           "the new commands' code holds no order, cancel, transfer or process-control call (found: %s)" % _bad)
        _nb = len(_bs_asked)
        ck(_nb > 0 and all(q.get("subaccount") in _bsm.SUBS for _p, q in _bs_asked if _p in _bsm.POT_PATHS)
           and set(_p for _p, _q in _bs_asked) <= set(_bsm.PATHS),
           "every Kalshi read the phone caused (%d, all from /race above) is one of botstats' read paths, and "
           "every per-pot one names its subaccount -- with none, settlements mix every pot" % _nb)
        # the pin version: joined names and 'LIVE <date>' headers, and the SAME pick as botstats
        _vp = os.path.join(_bsdir, "VERSIONS.md")
        ck([v[0] for v in versions(_vp)] == ["v-ladder-settlefix", "v-keepalive-cleanroom", "v-forecaster-race1",
                                             "v-reopen98 + v-floor90", "v-race20"],
           "VERSIONS.md: a 'v-a + v-b' name and a 'LIVE <date>' header are read too")
        ck(live_version(_vp)[0] == "v-reopen98 + v-floor90" == _bsm.version_of("pin")[0]
           and live_version(_vp)[1] == calendar.timegm((2026, 9, 16, 12, 0, 0)),
           "/stats' pin version skips the ladder, the clean-room keep-alive and the forecaster and names "
           "v-reopen98 + v-floor90 -- the same entry botstats picks (it used to name v-keepalive-cleanroom)")
        _bsm.RESULTS = _bs_saved[0]
        try:
            _lv, _bv = live_version(VERSIONS_MD), _bsm.version_of("pin")
        finally:
            _bsm.RESULTS = _bsdir
        ck((_lv[0] if _lv else None) == (_bv[0] if _bv else None),
           "DRIFT: on the real VERSIONS.md the phone and botstats name the same pin version (%s / %s)"
           % (_lv[0] if _lv else None, _bv[0] if _bv else None))

        # /bots on the planted world
        bh_ = ph.handle(111, "/bots")
        b_ = P(bh_)
        ck(b_.split("\n")[1] == "🤖 ALL BOTS · Sep 16 11:00 AM ET", "/bots: header in ET")
        ck(b_.split("\n")[0] == "🔴 All bots today -$12.53 (-10.1% on $123.81 staked · -1.1% of all pots)",
           "/bots: today's money over every pot is the headline, with its return and its share of all pots")
        ck(fits(bh_) and not any(tg_html_problems(c) for c in split_html(bh_)), "/bots: Telegram-valid messages")
        # THE POT (2026-10-02), worked by hand. Now: main 1000 + open 29.10 + 19.60 = 1048.70; ladder
        # 15.10; forecaster 24.00; all 1087.80. TODAY: main settled -10.03, moved out 15.06 + 7.99 ->
        # 1048.70 + 10.03 + 23.05 = 1081.78 (pin -10.40 = -0.96%, race +0.37 = +0.03%); forecaster
        # 24 + 2.54 - 7.99 = 18.55 at midnight, + the 7.99 moved in = 26.54 (-9.6%); ladder ~0 at
        # midnight + 15.06 moved in = 15.06 (+0.28%); all 1087.80 + 12.528 = 1100.33 (-1.1%).
        # YESTERDAY: main 1048.70 + 14.00 - 76.95 = 985.75 at the start + 98 deposit + 2 back = 1085.75
        # (pin +0.05%, other -0.42%); forecaster 24 + 1.9928 - 5.99 = 20.00 (+2.7%); all 1103.75 (-0.31%).
        # v-tg-active (2026-10-30): in this world the ladder is stopped by its stop file and the weather dip-seller, the FX
        # taker and the jump band do not run -- none is named; the ladder's +$0.04 sits on the one 'earlier' entry
        ck("Today: -$12.53 on $123.81 put in (-10.1%) = -1.1% of all pots ($1,100.33); 5 markets, 3 won, 2 lost\n"
           "  pin -$10.40 (-0.96%) | race +$0.37 (+0.03%) | forecaster -$2.54 (-9.6%) | earlier +$0.04"
           in b_,
           "/bots TODAY is all four pots: -10.40 + 0.37 - 2.54 + 0.042 = -12.53 on 99.80 + 19.60 + 2.45 + 1.958 "
           "put in = -1.1% of the $1,100.33 all pots held at midnight; each running bot's share of ITS OWN pot listed, "
           "the stopped ladder's money on the 'earlier' entry (no pot %%: earlier bots' pots differ)")
        ck("Yesterday: -$3.42 on $36.32 put in (-9.4%) = -0.31% of all pots ($1,103.75); 3 markets, 2 won, 1 lost\n"
           "  pin +$0.54 (+0.05%) | race none | forecaster +$0.55 (+2.7%) | other -$4.51 (-0.42%)"
           in b_ and "ladder" not in b_.lower().replace("/ladder", "") and "weather" not in b_.lower()
           and "fx" not in b_.lower() and "jump" not in b_.lower(),
           "YESTERDAY: the SOL and XRP markets that closed before midnight ET count on Sep 15 though Kalshi "
           "settled them on the 16th (UTC); the oil market that is no bot's is shown as `other`; the $98 "
           "deposit made during the day is part of the pot")
        ck("All time: -$15.95 on $160.13 put in (-10.0%) = -1.4" in b_
           and "% on money put in ($1,103.75); 8 markets, 5 won, 3 lost" in b_,
           "ALL TIME: every settlement in every pot, each once; as a share of the $1,103.75 deposited after fees")
        ck("The % after '=' or in brackets = share of the pot when the window began" in b_
           and "Kalshi's books explain" not in b_,
           "/bots says once what the percentages are; every planted pot reconciles, so no pot warning")
        ck("  Sep 16: -$12.53, 5 markets (pin -$10.40, race +$0.37, forecaster -$2.54, earlier +$0.04)" in b_
           and "  Sep 15: -$3.42, 3 markets (pin +$0.54, forecaster +$0.55, other -$4.51)" in b_
           and "Sep 14" not in b_,
           "by day, with each bot's part; no line for the days before anything settled")
        ck("Cash: main account (pin bot + coin race) $1,000.00, forecaster $24.00, earlier bots' pots $15.10 -- all pots "
           "$1,039.10." in b_ and "counts the main account only (pin bot + coin race)" in b_,
           "the cash of every pot -- a stopped bot's pot on one 'earlier bots' pots' entry, so it still adds up -- and HIS "
           "QUESTION answered: the main page counts the main account only")
        ck("Kalshi's own app shows the MAIN account only. The $39.10 sitting in the other pots" in b_,
           "/bots says why Kalshi's app reads lower than all pots: the bot pots' cash (24.00 + 15.10) is outside it")
        # 2026-10-26 (operator: "a green emoji for a negative bank makes no sense"): a card's dot is the bot's money
        # TODAY -- the pin bot is running and DOWN, so red -- and whether it runs is in words on the line under it
        ck("🔴 PIN BOT · main account · /pin\nrunning since Sep 16 7:59 AM ET · v-reopen98 + v-floor90\ntoday -$10.40 "
           "(-10.4% on bets · -0.96% of bank) · 7 days -$9.86 (-7.6% on bets · -0.93% of bank) · all time -$9.86 "
           "(-7.6% on bets · -0.93% of bank) · open: 1 ($29.10 at risk)" in b_,
           "a card a bot: its dot is its money today (pin is running and down: red), running since (ET) in words, "
           "version, money with its share of the pot, open bets, its command")
        ck("LADDER ·" not in b_ and "STOPPED by its stop file" not in b_
           and "🔴 FORECASTER · subaccount 2 · /fc\nrunning since Sep 16 8:34 AM ET · v-forecaster-race1" in b_
           and "🟢 COIN RACE · main account · /race\nrunning since Sep 15 10:49 PM ET · v-race20" in b_
           and "⏸ EARLIER BOTS (paused or stopped, not listed): today +$0.04 (+2.1% on bets), 7 days +$0.04 (+2.1% on "
               "bets), all time +$0.04 on 1 market -- in every total above." in b_,
           "the paper race arm is not the live race (the race runs: its card); the ladder with a stop file gets NO card "
           "(v-tg-active, 2026-10-30) -- its money is one 'earlier bots' line, in every total; the forecaster runs and is "
           "down (red)")
        ck("WEATHER" not in b_ and "FX TAKER" not in b_ and "JUMP BAND" not in b_ and "NOT RUNNING" not in b_
           and "🟠" not in b_ and "A bot's dot = its money today" in b_
           and "One bot in full: /pin /race /fc · every account's cash: /funds" in b_,
           "bots that do not run (the weather dip-seller, the FX taker, the jump band) get no card and no command; the "
           "legend lists only the running bots' commands: %r" % b_[-300:])
        ck("🔴 NOT ANY BOT'S (main account): all time -$4.51 on 1 market; worst -$4.51 WTI 2:00 PM (Sep 15)." in b_,
           "a main-account market that is no bot's is shown on its own, never folded into pin; its dot is its money")
        _r0 = {"alive": True, "started_et": "Sep 16 7:59 AM ET", "halted": None, "stop_flag": False}
        ck(money_dot({"ok": True, "today": {"markets": 2, "money": -10.4}}) == "🔴"
           and money_dot({"ok": True, "today": {"markets": 1, "money": 0.9}}) == "🟢"
           and money_dot({"ok": True, "today": {"markets": 0, "money": 0.0}}) == "⚪"
           and money_dot({"ok": False, "today": None}) == "❔"
           and run_words(_r0) == "running since Sep 16 7:59 AM ET"
           and run_words(dict(_r0, halted={"t_et": "Sep 16 9:00 AM ET", "what": "day_stop", "why": ""}))
           == "🛑 <b>HALTED Sep 16 9:00 AM ET</b> -- no new bets (running since Sep 16 7:59 AM ET)"
           and run_words(dict(_r0, alive=False, stop_flag=True, stop_flag_et="Sep 10 5:47 AM ET"))
           == "⏸ <b>STOPPED</b> by its stop file (Sep 10 5:47 AM ET)"
           and run_words(dict(_r0, alive=False, log_last_et="Sep 16 10:58 AM ET"))
           == "⚠️ <b>NOT RUNNING</b> since about Sep 16 10:58 AM ET (its log's last write) -- no stop file, it stopped on its own"
           and run_words(dict(_r0, alive=None)).startswith("❔ <b>running? could not tell</b>")
           and run_words(dict(_r0, stop_flag=True)).endswith("its stop file is set: it stops at its next check")
           and [state_icon(dict(_r0, **x)) for x in ({}, {"halted": {"t_et": "x"}}, {"alive": False, "stop_flag": True},
                                                     {"alive": False}, {"alive": None})] == ["▶️", "🛑", "⏸", "⚠️", "❔"],
           "a dot is money (up / down / nothing / unread); the running state is words -- running since, HALTED, STOPPED, "
           "NOT RUNNING since its log's last write, could not tell -- and an icon that is not a money colour")
        # /pin
        ph_ = ph.handle(111, "/pin")
        p_ = P(ph_)
        ck(fits(ph_) and len(split_html(ph_)) == 1 and not tg_html_problems(ph_),
           "/pin fits one Telegram message on this world (%d chars), Telegram-valid" % len(ph_))
        ck(p_.split("\n")[0] == "🔴 Pin bot today -$10.40 (-10.4% on $99.80 staked · -0.96% of its bank)",
           "/pin: today's money, its return on what the bets cost and its share of the pot lead the page")
        ck(p_.split("\n")[1] == "▶️ PIN BOT -- 15-minute coin markets + hourly Bitcoin" and "🟢" not in p_.split("\n")[1],
           "/pin (10-26): under the red money headline the running state is an icon that is not a money colour")
        for _want, _why in (
                ("Pot: main account, shared with the coin race.", "its pot, and who shares it"),
                ("Running: YES, pid 3882400, since Sep 16 7:59 AM ET.", "running, pid, since when in ET"),
                ("Version: v-reopen98 + v-floor90, live since Sep 16 8:00 AM ET.", "its version from VERSIONS.md"),
                ("Settings: halts after 2 losing bets.", "its settings from its command line"),
                ("Keep-alive: watch_bot.ps1 restarts it", "what restarts it"),
                ("Money (Kalshi settlements, main account, read Sep 16 11:00 AM ET;", "where the money comes from"),
                ("Today: -$10.40 on $99.80 put in (-10.4%) = -0.96% of its bank ($1,081.78); 2 markets, 1 won, 1 lost",
                 "today: the both-sides ETH market pays its winning YES side (-$11.30, not -$51.30); -0.96% of the "
                 "main pot at midnight ET"),
                ("Yesterday: +$0.54 on $29.40 put in (+1.8%) = +0.05% of its bank ($1,085.75); 1 market, 1 won, 0 lost",
                 "yesterday"),
                ("Last 7 days: -$9.86 on $129.20 put in (-7.6%) = -0.93% of its bank ($1,062.70); 3 markets, 2 won, "
                 "1 lost; 1 day up, 1 down", "7 days, with days up and down"),
                ("All time (since Sep 15): -$9.86 on $129.20 put in (-7.6%) = -0.93% on money put in ($1,062.70)",
                 "all time, since its first day, of the main account's money put in (1103.75 deposited - 41.05 "
                 "moved to the bot pots)"),
                ("% of its bank = of what the pot held when the window began (cash + open bets, + any money moved in "
                 "during it); all time = of the money put in -- the pot is the whole main account, shared with the "
                 "coin race.", "what the percentages are, and that pin's pot is shared"),
                ("Worst market today: -$11.30 ETH 9:45 AM; best +$0.90 BTC 10:30 AM.", "worst and best today"),
                ("Worst market all time: -$11.30 ETH 9:45 AM (Sep 16); best +$0.90 BTC 10:30 AM (Sep 16).",
                 "worst and best all time, with the day"),
                ("Best day +$0.54 (Sep 15), worst day -$10.40 (Sep 16), over 2 days with a settlement.",
                 "best and worst day"),
                ("Fees all time: $0.66", "fees: 0.10 + 0.50 + 0.06"),
                ("Bought both sides (hedged): 1 market all time.", "hedged markets"),
                ("Open now: 1 bet, $29.10 at risk:\n  BTC 11:15 AM NO x30, $29.10 at risk",
                 "open bets from Kalshi: the race's SOL leg in the same pot is NOT pin's"),
                ("Cash: $1,000.00 -- shared: the coin race's cash sits in the same pot.", "cash, said to be shared"),
                ("  Sep 16 ETH 9:45 AM BOTH SIDES x80: -$11.30 on $50.80 put in", "the last markets, newest first"),
                ("Today, its own log: no log file found.", "no log is said, not shown as zero orders"),
                ("More on pin: /stats", "and where the rest of pin's numbers are")):
            ck(_want in p_, "/pin: " + _why)
        ck(p_.index("BTC 10:30 AM NO x50: +$0.90") < p_.index("ETH 9:45 AM BOTH SIDES") < p_.index("SOL 11:45 PM YES x30"),
           "/pin: last settled newest first")
        # /forecaster and /fc
        f_ = P(ph.handle(111, "/forecaster"))
        ck(P(ph.handle(111, "/fc")) == f_, "/fc is /forecaster")
        for _want, _why in (
                ("FORECASTER -- buys the 15-minute coin side its own forecast calls decided", "the forecaster's own page"),
                ("Pot: subaccount 2.", "its own pot"),
                ("Running: YES, pid 4196192, since Sep 16 8:34 AM ET.", "running"),
                ("Its log last wrote Sep 16 10:59 AM ET (30 s ago).", "how fresh its log is"),
                ("Version: v-forecaster-race1, live since Sep 16 8:35 AM ET.", "its version, not the keep-alive entry"),
                ("Settings: variant race1_98; 5% of paper size; up to 5 a side, 20 a quarter-hour; at most $22.00 in "
                 "play; buys 75c to 98.5c; stops the day at -$12.00, the run at -$20.00.", "its rails from its start record"),
                ("Today: -$2.54 on $2.45 put in (-103.7%) = -9.6% of its bank ($26.54); 1 market, 0 won, 1 lost",
                 "subaccount 2's money today: -$2.54 is -9.6% of the $26.54 it had (18.55 at midnight + 7.99 moved in)"),
                ("Yesterday: +$0.55 on $2.42 put in (+22.6%) = +2.7% of its bank ($20.00); 1 market, 1 won, 0 lost",
                 "and yesterday"),
                ("= -7.7% on money put in ($25.99)", "all time: of the 20 - 2 + 7.99 moved into its pot"),
                ("Cash: $24.00 -- its own pot (subaccount 2).", "its own cash"),
                ("1 order sent, 1 filled (5 contracts).", "what its log did today"),
                ("  Refused 1 time: order already in flight 1.", "its refusals in words")):
            ck(_want in f_, "/forecaster: " + _why)
        # /ladder: stopped by its stop file, so the command says so and nothing else (v-tg-active); its page, built
        # directly, still says why it is not running
        lh_ = P(ph.handle(111, "/ladder"))
        ck(lh_.startswith("⏸ Ladder is not running now (its stop file is set)") and "comes back by itself" in lh_
           and "Today:" not in lh_ and lh_.endswith("The bots running now: /pin /race /fc"),
           "/ladder while its stop file is set: one short answer -- not running, why, that it comes back by itself -- "
           "and the bots that do run: %r" % lh_)
        l_ = P(ph.text_bot("ladder"))
        ck("⏸ Running: NO -- stopped by its stop file (set " in l_ and ': "stood down by the operator".' in l_
           and "stopped on its own" not in l_ and l_.split("\n")[0].startswith("🟢 Ladder today +$0.04")
           and l_.split("\n")[1].startswith("⏸ LADDER -- "),
           "/ladder: NOT running, and WHY -- its stop file, with what the file says, said loud under a headline whose "
           "dot is its money (up: green)")
        ck("Today: +$0.04 on $1.96 put in (+2.1%) = +0.28% of its bank ($15.06); 1 market, 1 won, 0 lost" in l_
           and "Cash: $15.10 -- its own pot (subaccount 1)." in l_
           and "Version: v-ladder-settlefix, live since Sep 16 9:16 AM ET." in l_,
           "/ladder: subaccount 1's money, cash and version")
        # /race keeps everything it said and adds the windows
        rh_ = ph.handle(111, "/race")
        r_ = P(rh_)
        ck("COIN RACE · " in r_ and "Last 10 races (Kalshi's books)" in r_ and "Paper race arms running:" in r_,
           "/race still says everything it said before")
        ck("Money (Kalshi settlements, main account, read Sep 16 11:00 AM ET; a leg counts on the ET day it closed)"
           in r_ and "Today: +$0.37 on $19.60 put in (+1.9%) = +0.03% of its bank ($1,081.78); 1 leg, 1 won, 0 lost"
           in r_ and "All time (since Sep 16): +$0.37 on $19.60 put in (+1.9%) = +0.03% on money put in ($1,062.70); "
           "1 leg, 1 won, 0 lost" in r_,
           "/race adds the race's money by window, legs not races, each a share of the main pot it shares with pin")
        ck(r_.index("Paper race arms running:") < r_.index("Money (Kalshi settlements"),
           "...AFTER what /race already said")
        ck("Version: v-race20, live since Sep 15 10:50 PM ET." in r_
           and "Keep-alive: boot_all.ps1 (every 10 min) restarts it unless the stop file is there." in r_
           and "nothing restarts it" not in r_
           and "Open now: 1 leg, $19.60 at risk:\n  race SOL 11:00 AM YES x20, $19.60 at risk" in r_
           and "Cash: $1,000.00 -- shared: the pin bot's cash sits in the same pot." in r_,
           "/race: its version, its keep-alive (boot_all.ps1 has restarted the live race since 09-30, so 'nothing "
           "restarts it' is no longer said), the leg Kalshi holds open, the shared cash")
        ck("Settings: " not in r_ and "penny" not in r_.lower().replace("pinracepenny", ""),
           "/race: botstats' command-line Settings line (the 20 / $40 it STARTS from) is not shown -- 'How it bets' "
           "reads the size from the race's own log -- and nothing calls it a penny bot")
        ck(fits(rh_) and not any(tg_html_problems(c) for c in split_html(rh_)), "/race: Telegram-valid messages")
        ck(all(q.get("subaccount") in _bsm.SUBS for _p, q in _bs_asked if _p in _bsm.POT_PATHS)
           and set(_p for _p, _q in _bs_asked) <= set(_bsm.PATHS),
           "still every per-pot Kalshi read names its subaccount and every read is a read path")

        # v-tg-active (2026-10-30, the operator: "remove the paused and removed until they're added back, and show the
        # details for the new one in any relevant commands"): the server's shape -- the coin race RUNS with its stop file
        # set, the ladder is stopped, the jump band runs live beside its paper arm (which is never the bot)
        with open(os.path.join(_bsdir, "jumpband-live.jsonl"), "w", encoding="utf-8") as _fh:
            _fh.write(json.dumps({"t": "2026-09-16T08:13:26.86Z", "kind": "start", "pid": 2972, "live": True, "paper": False,
                                  "subaccount": 3, "max_contracts": 5, "max_cost": 20.0, "stop_line": -25.0,
                                  "day_stop": -15.0, "series": ["KXBNB15M", "KXHYPE15M", "KXZEC15M", "KXNEAR15M"],
                                  "k": 2.0, "lo": 0.7, "hi": 0.9, "tau": [10, 60]}) + "\n")
            _fh.write(json.dumps({"t": "2026-09-16T14:44:29Z", "kind": "trigger", "outcome": "buy"}) + "\n")
            _fh.write(json.dumps({"t": "2026-09-16T14:44:29.05Z", "kind": "order", "filled": 5.0, "status": 201}) + "\n")
            _fh.write(json.dumps({"t": "2026-09-16T14:44:29.06Z", "kind": "fill", "ticker": "KXBNB15M-26SEP161045-45",
                                  "side": "no", "qty": 5.0, "price": 0.88, "cost": 4.4, "fee": 0.04}) + "\n")
        _jbp = [(2972, "2026-09-16T08:13:20Z", r"C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live "
                                               r"--subaccount 3 --max-contracts 5 --minutes 20160"),
                (4276, "2026-09-16T08:00:00Z", r"C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --minutes 20160")]
        with open(os.path.join(_bsdir, _bsm.SPEC["race"]["stop"]), "w", encoding="utf-8") as _fh:
            _fh.write("paused by the operator")
        ph.bs_procs = _bs_procs + _jbp
        ck(ph.active() == ("pin", "forecaster", "jumpband"),
           "ACTIVE on the server's shape: the pin bot, the forecaster and the jump band -- not the race (running, stop "
           "file set), not the ladder (stop file), not the paper arm: %s" % (ph.active(),))
        _hp = P(ph.handle(111, "/help"))
        ck("/jb (or /jumpband) — the jump band" in _hp and "/fc" in _hp and "/race" not in _hp and "/racestats" not in _hp
           and "/ladder" not in _hp and "/weather" not in _hp and "/fx" not in _hp and "coin race apart" not in _hp
           and P(help_text(("pin", "race"))).count("/race") == 2 and not tg_html_problems(ph.handle(111, "/help"))
           and fits(ph.handle(111, "/help")),
           "/help lists only the running bots' commands (the jump band's included); the paused race, the stopped ladder "
           "and the bots not running are left out")
        _rh = P(ph.handle(111, "/race"))
        ck(_rh.startswith("⏸ Coin race is not running now (its stop file is set)") and "Last 10 races" not in _rh
           and P(ph.handle(111, "/racestats")) == _rh and P(ph.handle(111, "/fx")).startswith(
               "⏸ FX taker is not running now (no live copy of it is running)"),
           "/race and /racestats while the race's stop file is set: one short answer, no page; /fx (not running) the same")
        _jh = ph.handle(111, "/jb")
        _jp = P(_jh)
        for _want, _why in (
                ("JUMP BAND -- buys the 70-90c favourite on BNB/HYPE/ZEC/NEAR when the price jumps 2+ standard deviations "
                 "in the last minute, 5 contracts, holds to the end", "its own page, in plain words"),
                ("Pot: subaccount 3.", "its own pot (the weather dip-seller, stopped, is not named)"),
                ("Running: YES, pid 2972, since Sep 16 4:13 AM ET.", "the --live copy, not the paper arm"),
                ("up to 5 contracts a buy, at most $20.00 an order; buys the favourite at 70c-90c when the price moves 2+ "
                 "standard deviations in its last minute, 10-60 s before the close; coins BNB HYPE ZEC NEAR; stops the "
                 "day at -$15.00 settled; stands down for good at -$25.00 since it went live", "its settings, from its start record"),
                ("Keep-alive: NONE -- if it dies, nothing restarts it.", "it is not in boot_all, said plainly"),
                ("Today, its own log (what it did, not money): 1 order sent, 1 filled (5 contracts).", "what its log did today"),
                ("1 price jump judged today", "its triggers"),
                ("its pot (subaccount 3, crypto pool): /funds", "where its cash is")):
            ck(_want in _jp, "/jb: " + _why + ": %r" % _jp[:200])
        ck(P(ph.handle(111, "/jumpband")) == _jp and fits(_jh) and not tg_html_problems(_jh)
           and "weather" not in _jp.lower(), "/jumpband is /jb; Telegram-valid; no word of the weather dip-seller")
        _bj = P(ph.handle(111, "/bots"))
        ck("JUMP BAND · subaccount 3 · /jb\nrunning since Sep 16 4:13 AM ET" in _bj and "COIN RACE" not in _bj
           and "LADDER ·" not in _bj and "⏸ EARLIER BOTS (paused or stopped, not listed): today +$0.41" in _bj
           and "One bot in full: /pin /fc /jb ·" in _bj and "race +$" not in _bj and "| earlier +$0.41" in _bj
           and "Cash: main account (pin bot) $1,000.00, forecaster $24.00, jump band $0.00, earlier bots' pots $15.10 -- "
               "all pots $1,039.10." in _bj,
           "/bots: the jump band's card and command; the race (paused) and the ladder (stopped) are gone, their money on "
           "the one 'earlier bots' line (+0.37 + 0.04), every total and the cash still adding up: %r" % _bj[-900:])
        _s2 = P(ph.handle(111, "/status"))
        ck("Main account $500.00 (pin bot)" in _s2 and "coin race" not in _s2 and "Main account today" in _s2,
           "/status with the race paused names the main account's pin bot only")
        _fe = P(ph.handle(111, "/features"))
        ck("Jump band (LIVE, subaccount 3)" in _fe and "started by hand on the server" in _fe
           and "settings: up to 5 contracts a buy" in _fe and "Coin race (LIVE" not in _fe and "Penny ladder (LIVE" not in _fe
           and "Weather dip-seller" not in _fe,
           "/features: the jump band's block (started by hand, its settings), no block for a paused or stopped money bot")
        os.remove(os.path.join(_bsdir, _bsm.SPEC["race"]["stop"]))
        _hp2 = P(ph.handle(111, "/help"))
        ck(ph.active() == ("pin", "race", "forecaster", "jumpband") and "/race" in _hp2 and "/racestats" in _hp2
           and "COIN RACE · " in P(ph.handle(111, "/race")) and "COIN RACE · main account · /race" in P(ph.handle(111, "/bots")),
           "the race's stop file removed (its process still --live): it is back in /help, /race and /bots, no code change")
        ph.bs_procs = _bs_procs
        os.remove(os.path.join(_bsdir, "jumpband-live.jsonl"))

        # /weather and /wx (2026-10-04): the weather dip-seller, subaccount 3, cash in POOL 0
        _wxdir = _bs_sandbox("botstats-weather")
        _bs_mode["m"] = "weather"
        # v-tg-active (2026-10-30): this world is subaccount 3 as it was 10-04..10-29 (the weather pot, pool 0); since the
        # jump band the number 3 trades in pool 2. The world runs on the old settings, restored below.
        _wx_pool = (dict(_bsm.SUB_POOL), dict(_bsm.POT_POOL_ONLY))
        _bsm.SUB_POOL["3"] = 0
        _bsm.POT_POOL_ONLY.pop("3", None)
        with open(os.path.join(_wxdir, "dipsell-live-orders.jsonl"), "w", encoding="utf-8") as _fh:
            _fh.write(json.dumps({"t": "2026-09-15T07:56:53Z", "ev": "start", "pid": 3955508, "subaccount": 3,
                                  "live": True, "start_pot": 50.0,
                                  "rails": {"contracts": 2, "max_open": 5, "window_s": 10800, "day_stop_frac": 0.25,
                                            "kill_after": 60, "max_fills": 100, "max_days": 14, "pool": 0},
                                  "trigger": {"drop_c": 10.0, "hours_left": [6.0, 12.0]}}) + "\n")
        with open(os.path.join(_wxdir, "VERSIONS.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# Versions\n\n# v-dipsell-live -- LIVE 2026-09-15 07:56:53Z (pid 3955508, subaccount 3 pool 0, "
                      "$50): weather\n# v-reopen98 + v-floor90 -- 2026-09-16 12:00:17Z (pid 3882400) -- LIVE: 98c\n")
        _wx_n0 = len(_bs_asked)
        ph.bs_procs = _bs_procs + [(3955508, "2026-09-15T07:56:50Z", r"C:\Python314\python.exe -u "
                                    r"research\sweep\dipsell_live.py --subaccount 3 --live --minutes 21600")]
        w_ = P(ph.handle(111, "/weather"))
        ck(P(ph.handle(111, "/wx")) == w_, "/wx is /weather")
        for _want, _why in (
                ("WEATHER DIP-SELLER -- sells YES on a daily-high temperature bracket", "its own page"),
                ("Pot: subaccount 3.", "its own pot, shared with no bot"),
                ("Running: YES, pid 3955508, since Sep 15 3:56 AM ET.", "running: the --live dipsell_live.py"),
                ("Version: v-dipsell-live, live since Sep 15 3:56 AM ET.", "its VERSIONS.md entry"),
                ("2 contracts an order, one order a market", "its rails from its start record"),
                ("Keep-alive: boot_all.ps1 (every 10 min) restarts it unless the stop file is there.", "its keep-alive"),
                ("Yesterday: +$0.80 on $1.20 put in (+66.7%) = +1.6% of its bank ($50.00); 1 market, 1 won, 0 lost",
                 "yesterday's bracket, +1.6% of the $50 moved into its pot that day"),
                ("Open now: 1 bet, $1.10 at risk:\n  MIA high B90.5 NO x2, $1.10 at risk", "the bracket Kalshi holds open"),
                ("Cash: $49.70 -- its own pot (subaccount 3).", "its cash, read from POOL 0")):
            ck(_want in w_, "/weather: " + _why)
        ck(any(_p == "/portfolio/balance" and _q == {"subaccount": "3", "exchange_index": 0}
               for _p, _q in _bs_asked[_wx_n0:])
           and not any(_p == "/portfolio/balance" and _q.get("subaccount") == "3" and _q.get("exchange_index") != 0
                       for _p, _q in _bs_asked[_wx_n0:]),         # before this world: pool 2, the jump band's (10-30)
           "/weather: its cash is read from subaccount 3 in pool 0, never pool 2 (where Kalshi says $0.00)")
        wb_ = P(ph.handle(111, "/bots"))
        ck("WEATHER DIP-SELLER · subaccount 3 · /weather\nrunning since Sep 15 3:56 AM ET · v-dipsell-live" in wb_
           and "/weather" in wb_ and "| weather none" in wb_ and "weather +$0.80 (+1.6%)" in wb_
           and "forecaster $24.00, weather $49.70, earlier bots' pots $15.10 -- all pots $1,088.80." in wb_
           and "The $88.80 sitting in the other pots" in wb_ and "One bot in full: /pin /race /fc /weather ·" in wb_
           and "JUMP BAND" not in wb_ and "FX TAKER" not in wb_,
           "/bots: the weather bot's line while it runs, its share of yesterday, its cash in the all-pots cash (1000 + "
           "24 + 49.70 + the stopped ladder's 15.10 on the 'earlier bots' pots' entry, each pot once -- the empty pool-0 "
           "rows of subaccounts 1 and 2 add $0), and that Kalshi's app does not show it")
        ck(live_version(os.path.join(_wxdir, "VERSIONS.md"))[0] == "v-reopen98 + v-floor90" == _bsm.version_of("pin")[0],
           "/stats' pin version skips the weather entry, as botstats does")
        ph.bs_procs = _bs_procs
        _bsm.SUB_POOL.clear()
        _bsm.SUB_POOL.update(_wx_pool[0])
        _bsm.POT_POOL_ONLY.clear()
        _bsm.POT_POOL_ONLY.update(_wx_pool[1])

        # NULL (2026-10-02): the account's books unreadable -> the money stands, NO pot %, and the reason
        _bs_sandbox("botstats-noledger")
        _bs_mode["m"] = "noledger"
        n_, nb_ = P(ph.handle(111, "/pin")), P(ph.handle(111, "/bots"))
        ck("Today: -$10.40 on $99.80 put in (-10.4%); 2 markets, 1 won, 1 lost" in n_
           and "of its bank (" not in n_ and "on money put in" not in n_ and "of its bank)" not in n_
           and "% of its bank: not shown -- transfers read failed (HTTP 404)." in n_
           and "Today: -$12.53 on $123.81 put in (-10.1%); 5 markets, 3 won, 2 lost\n"
               "  pin -$10.40 | race +$0.37 | forecaster -$2.54 | earlier +$0.04\n" in nb_   # v-tg-active: ladder stopped
           and "today -$10.40 (-10.4% on bets) · 7 days -$9.86 (-7.6% on bets) · all time -$9.86 (-7.6% on bets) ·" in nb_
           and "% of the pots: not shown -- main account: transfers read failed (HTTP 404)." in nb_,
           "NULL: the deposit/transfer listings unreadable -> every dollar figure still shown, NO percentage of "
           "any pot anywhere (never a guessed base), and the reason said once")

        # EMPTY: nothing settled, nothing open, nothing running, no logs
        _bs_sandbox("botstats-empty")
        _bs_mode["m"], ph.bs_procs = "empty", []
        e_, eb_ = P(ph.handle(111, "/pin")), P(ph.handle(111, "/bots"))
        ck("Today: nothing settled yet" in e_ and "All time: nothing settled yet" in e_
           and "Nothing settled yet on Kalshi for this bot." in e_ and "Open now: none." in e_
           and "Running: NO, and there is no stop file -- it stopped on its own." in e_
           and "Version: no entry for it in VERSIONS.md." in e_ and "+$" not in e_ and "-$" not in e_,
           "EMPTY /pin: nothing settled YET, nothing open, not running and why -- no gain or loss invented")
        ck("Nothing settled yet in any pot." in eb_ and "today nothing yet · 7 days nothing yet · all time nothing yet"
           in eb_ and "+$" not in eb_ and "-$" not in eb_ and "By day:" not in eb_ and "By day (all pots)" not in eb_,
           "EMPTY /bots: says nothing has settled yet, no gain or loss, no empty day list")
        ck(P(ph.handle(111, "/losses")) == "No losing markets in any pot (0 settled).",
           "EMPTY /losses: no losing market in any pot, said plainly: %r" % P(ph.handle(111, "/losses")))
        # DOWN: Kalshi refuses and the process list cannot be read -- unknown, never $0 or 'not running'
        _bs_sandbox("botstats-down")
        _bs_mode["m"], ph.bs_procs = "down", (lambda: None)
        d_, db_ = P(ph.handle(111, "/pin")), P(ph.handle(111, "/bots"))
        ck("MONEY: COULD NOT READ KALSHI (settlements read failed (HTTP 401))" in d_
           and "Running: COULD NOT TELL" in d_ and "Open now: COULD NOT READ" in d_
           and "Cash: COULD NOT READ" in d_ and "$0.00" not in d_ and "nothing settled" not in d_,
           "DOWN /pin: a failed read is said as a failure -- never $0, never 'nothing settled', never 'not running'")
        ck("Today: unknown -- Kalshi could not be read" in db_ and "Last 7 days: unknown" in db_
           # v-tg-active: the process table unreadable (and no stop file in this sandbox), every bot is shown -- never
           # hidden on a failed read
           and "PARTIAL: these totals leave out pin, race, forecaster, ladder, weather, fx, jumpband, other" in db_
           and "running? could not tell" in db_ and "money: COULD NOT READ KALSHI" in db_
           and "money: settlements read failed (HTTP 401): forecaster, fx, jumpband, ladder, pin, race, weather" in db_
           and "JUMP BAND · subaccount 3 · /jb" in db_
           and "nothing settled" not in db_ and "Nothing settled" not in db_,
           "DOWN /bots: every total is 'unknown', the missing pots are named, each error said once")
        _lo = P(ph.handle(111, "/losses"))
        ck("every bot" not in _lo and "No losing markets" not in _lo and (_lo == "No losing closes." or "losing closes" in _lo),
           "DOWN /losses: no pot readable -> the main account's own ledger (never 'no losing markets'): %r" % _lo[:120])
        # BROKEN botstats: those commands say so; /race still answers
        _sv_b, _sv_a = _bsm.bot, _bsm.all_bots

        def _boom(*a, **k):
            raise RuntimeError("planted botstats failure")
        _bsm.bot = _bsm.all_bots = _boom
        _sv_log = LOG
        globals()["LOG"] = os.path.join(td, "pinphone.log")    # its planted tracebacks stay out of the real log
        try:
            ck(ph.handle(111, "/pin").startswith("Could not build /pin: planted botstats failure")
               and ph.handle(111, "/bots").startswith("Could not build /bots: planted botstats failure"),
               "a botstats failure is said by the command that hit it")
            _rb = P(ph.handle(111, "/race"))
            ck("Last 10 races (Kalshi's books)" in _rb
               and "Money by window: could not build it (planted botstats failure)." in _rb,
               "...and /race still gives everything it gave before, with the windows' failure said")
        finally:
            _bsm.bot, _bsm.all_bots = _sv_b, _sv_a
            globals()["LOG"] = _sv_log
        ck(all(c in HELP_TEXT for c in ("/bots", "/pin", "/forecaster", "/fc", "/ladder", "/weather", "/wx", "/fx")),
           "/bots /pin /forecaster /fc /ladder /weather /wx /fx are in /help")
        # the FX taker everywhere a bot is named (operator 10-26: "there's nothing for fx in the commands list ... Make
        # sure it's fully implemented"): its two pots by name, each pot's cash, /bots' pointer, /features' roster
        _fxb = {"subaccount": 5, "subaccounts": [5, 4]}
        _fxc = bs_cash_line({"ok": True, "dollars": 184.27, "by_sub": {"5": 123.30, "4": 60.97},
                             "note": "its own pots (subaccount 5 + subaccount 4)"})
        ck(_pot_words(_fxb) == "subaccount 5 + subaccount 4" and _pot_words({"subaccount": 1, "subaccounts": [1]}) == "subaccount 1"
           and _fxc == "Cash: $184.27 (subaccount 5 $123.30, subaccount 4 $60.97) -- its own pots (subaccount 5 + subaccount 4)."
           and "/fx" in BOT_CMDS and BOT_CMD_OF["fx"] == "/fx"
           and "One bot in full: /pin /race /fc /ladder /weather /fx" in "\n".join(bs_all_html(ph._bs_get("all")))
           and any(r[0] == "fxtake_live.py" and "subaccounts 5 + 4" in r[3] for r in FEATURES)
           and FUNDS_SIZE_BOTS.get(4) == ("fx",) and FUNDS_SIZE_BOTS.get(5) == ("fx",),
           "the FX taker: both pots named (5 + 4), each pot's cash on its card, /fx on /bots' pointer line, a /features "
           "row, a bet size under both accounts in /funds: %r" % _fxc)
        # ---- /features (2026-10-22): the settings come from boot_all.ps1's text, the rails from ladder_live.py's
        _ps = ('$repo = "C:\\kals-repo"\n$res = "$repo\\results"\n'
               '$live = @("-u", "$repo\\research\\pinrun.py", "--size", "20", "--minutes", "4320",\n'
               '          "--loss-abort", "-60.00", "--sweep-depth")\n'
               '@{ n = "arm-b-control"; x = $band + @("--early-tau", "45") + $m15 },\n'
               '@{ n = "arm-pin0.97"; x = @("--pin", "0.97") }\n'
               'if ($false -and -not (RunningPy \'*cmdlive.py*\')) {\n'
               '    Start-Process -FilePath $py -ArgumentList @("-u", "$repo\\research\\cmdlive.py", "--live", "--signoff", '
               '\'"commodity penny test"\', "--size", "20") -WorkingDirectory $repo\n}\n'
               'if (-not (RunningPy \'*pinledgerd.py*\')) {\n'
               '    Start-Process -FilePath $py -ArgumentList @("-u", "$repo\\research\\pinledgerd.py") `\n'
               '        -WorkingDirectory $repo\n}\n'
               '$cleanroom = @(\n'
               '    @{ n = "ladder_live (LIVE, subaccount 1)"; like = "*ladder_live.py*--live*"; unlike = @("*a*", "*b*"); stop = "$res\\ladder-live.stop";\n'
               '       a = @("-u", "research\\cleanroom\\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", '
               '"--market-cap-x", "2", "--levels", "0,1", "--coins", "KXNEAR15M,KXZEC15M", "--minutes", "10080");\n'
               '       o = "$res\\ladder-live-stdout.log"; e = "$res\\ladder-live-stderr.log" },\n'
               '    @{ n = "coin race (LIVE, main account)"; like = "*pinracearm.py --live*"; unlike = ""; stop = "";\n'
               '       a = @("-u", "research/pinracearm.py", "--live", "--max-contracts", "20", "--log", '
               '"C:/kals-repo/results/pinracepenny-live.jsonl");\n'
               '       o = "$res\\x.out"; e = "$res\\x.err" }\n)\n')
        _ls = boot_launches(_ps)
        ck([(x["label"], x["script"]) for x in _ls] ==
           [(None, "pinrun.py"), (None, "pinledgerd.py"), ("ladder_live (LIVE, subaccount 1)", "ladder_live.py"),
            ("coin race (LIVE, main account)", "pinracearm.py")]
           and _ls[0]["arms"] == ["arm-b-control", "arm-pin0.97"] and _ls[0]["argv"][1] == "C:\\kals-repo\\research\\pinrun.py"
           and _ls[2]["argv"][-2:] == ["--minutes", "10080"] and _ls[2]["label"].startswith("ladder_live"),
           "boot_launches: the three launch shapes in file order, $repo filled, the arm names, and the `$false -and` "
           "(OFF) launch left out")
        ck(argv_lines(_ls[0]["argv"]) == ["contracts a bet: 20", "runs for (minutes): 4320", "day stop (dollars): -60.00",
                                          "sweep depth: on"]
           and argv_lines(_ls[2]["argv"])[1:4] == ["real money: on", "bet size follows the pot: on", "cap per market (x bid size): 2"]
           and "coins: KXNEAR15M, KXZEC15M" in argv_lines(_ls[2]["argv"])
           and argv_lines(_ls[3]["argv"])[-1] == "log file: pinracepenny-live.jsonl",
           "argv_lines: -u and the script hidden, a negative number is a value, a bare flag is 'on', paths by name")
        ck(py_consts("X = 1\nDAY_STOP_FRAC, COMMIT_FRAC = 0.20, 0.70\nMAX_CONTRACTS = 10\nMAX_CONTRACTS = 99\n",
                     ("COMMIT_FRAC", "DAY_STOP_FRAC", "MAX_CONTRACTS")) == {"DAY_STOP_FRAC": 0.2, "COMMIT_FRAC": 0.7,
                                                                            "MAX_CONTRACTS": 10.0},
           "py_consts: a tuple line and a plain line; the first assignment wins")
        with tempfile.TemporaryDirectory() as _tdf:
            _bp, _lp = os.path.join(_tdf, "boot_all.ps1"), os.path.join(_tdf, "ladder_live.py")
            with open(_bp, "w", encoding="utf-8") as _fh:
                # this temp folder's stop file, not the real results\ one (2026-10-27: since the bots moved to the
                # server the laptop keeps real stop files, and this check read them and failed there)
                _fh.write(_ps.replace('stop = "$res\\ladder-live.stop"', 'stop = "%s"' % os.path.join(_tdf, "ladder-live.stop")))
            with open(_lp, "w", encoding="utf-8") as _fh:
                _fh.write("SIZE = Decimal('1')\nMAX_CONTRACTS = 10\nDAY_STOP_FRAC, COMMIT_FRAC = 0.20, 0.70\n")
            _sv_paths = globals()["BOOT_ALL"], globals()["LADDER_PY"]
            globals()["BOOT_ALL"], globals()["LADDER_PY"] = _bp, _lp
            try:
                r = ph.handle(111, "/features")
                t_ = P(r)
                ck(getattr(r, "is_html", False) and not tg_html_problems(r) and fits(r) and t_.startswith("🧩 Features")
                   and "Penny ladder (LIVE, subaccount 1)\n" in t_ and "goal 1%/day of its bank" in t_
                   and "98c rung: buy the already-decided side 2c below fair\n95c rung: the same at 5c below fair\n" in t_
                   and "rungs (levels): 0, 1" in t_ and "coins: KXNEAR15M, KXZEC15M" in t_
                   and "Pin bot (LIVE, main account)\n" in t_ and "not started by boot_all" in t_
                   and "Pin bot paper arms\n" in t_ and "arms: 2 -- arm-b-control, arm-pin0.97" in t_
                   and "Weather dip-seller (LIVE, subaccount 3)\nSells daily high-temperature markets (KXHIGH) into "
                       "dips, in Kalshi's weather cash pool.\nnot started by boot_all\n" in t_
                   and "Rules the bots run under (ladder_live.py)\nOpen bids: at most 70% of the bank" in t_
                   and "Daily loss stop: down 20% of the day's first pot" in t_
                   and "Contracts out at once: at most 10x the bid size" in t_ and "cmdlive" not in t_,
                   "/features: a block a bot with its live flags from boot_all.ps1, the ladder's goal and both rungs "
                   "(--levels 0,1), 'not started by boot_all' for the pin bot, the arms counted, the rails from "
                   "ladder_live.py, the OFF launch absent; valid HTML that fits Telegram's limit")
                globals()["BOOT_ALL"] = os.path.join(_tdf, "missing.ps1")
                t_ = P(ph.handle(111, "/features"))
                ck("could not read it" in t_ and t_.count("not started by boot_all") == len(FEATURES)
                   and "Open bids: at most 70%" in t_, "/features without boot_all.ps1: says so, every bot unstarted, rules kept")
                with open(_bp, "w", encoding="utf-8") as _fh:
                    _fh.write('$cleanroom = @(@{ n = "new thing"; a = @("-u", "research\\new_bot.py", "--x", "1") })\n')
                globals()["BOOT_ALL"] = _bp
                t_ = P(ph.handle(111, "/features"))
                ck("new thing\nstarted by boot_all; not written up here yet\nx: 1" in t_,
                   "/features: a launch boot_all has that the roster does not know is still shown, by boot_all's label")
            finally:
                globals()["BOOT_ALL"], globals()["LADDER_PY"] = _sv_paths
        t_ = P(ph.handle(111, "/features"))
        ck("/features" in HELP_TEXT and t_.startswith("🧩 Features") and "Rules the bots run under" in t_
           and fits(ph.handle(111, "/features")), "/features is in /help and the real boot_all.ps1 renders")
        _bs_mode["m"], ph.bs_procs = "planted", _bs_procs
        r = ph.handle(111, "/stop")
        ck("/stop yes" in P(r) and "STOP stops right now" in P(r) and not ph.busy,
           "/stop without yes only explains; nothing is stopped")
        ck(P(ph.handle(111, "/mute")) == "🔕 Alerts off. /unmute to turn them back on." and ph.muted, "/mute")
        ck(P(ph.handle(111, "/unmute")) == "🔔 Alerts on." and not ph.muted, "/unmute")
        _sv_flag, _sv_upd, _ups = UPDATE_FLAG, ph.text_update, []
        try:
            globals()["UPDATE_FLAG"] = os.path.join(td, "pinphone.update")
            ph.text_update = lambda: (_ups.append(1), Html("🔄 <b>Checking the newest phone code</b>"))[1]
            _n0 = len(tg.sent)
            _r0 = ph.update_flag_tick()
            open(UPDATE_FLAG, "w").close()
            _r1 = ph.update_flag_tick()
            _r2 = ph.update_flag_tick()
            ck(_r0 is None and _r2 is None and _ups == [1] and not os.path.exists(UPDATE_FLAG)
               and "Checking the newest phone code" in P(_r1) and "update flag file" in P(_r1)
               and len(tg.sent) == _n0 + 1,
               "update flag (10-26): no file -> nothing; the file -> /update runs ONCE (the file removed first) and the "
               "operator is told it came from the file")
        finally:
            globals()["UPDATE_FLAG"], ph.text_update = _sv_flag, _sv_upd
        ck("Commands" in P(ph.handle(111, "/help")) and "I did not understand that." in P(ph.handle(111, "what"))
           and "Commands" in P(ph.handle(111, "what")), "/help, and an unknown message gets the help")
        ck("Commands" in P(ph.handle(111, "/help@PinBotBot")), "a command with the @botname suffix still works")
        ck(all(not tg_html_problems(x) for x in (HELP_TEXT, STOP_ASK, UP_TEXT) + tuple(CONTROL_REPLY.values()))
           and all(getattr(x, "is_html", False) for x in tuple(CONTROL_REPLY.values()) + (HELP_TEXT, STOP_ASK)),
           "/help, the STOP question, the start-up line and the control replies are valid Telegram HTML")
        ck([P(CONTROL_REPLY[k]) for k in ("start", "pause", "stop", "busy")] ==
           ["▶️ Starting…", "⏸ Pausing: no new bets; waiting for open ones to settle…", "⏹ Stopping now…",
            "⏳ Still working on the last command."],
           "the control replies say what they always said (the work itself is unchanged: Phone.control)")

        # alerts: first tick only records; a change sends once
        ck(ph.alerts_tick() == [] and ph.last_state == "TRADING", "the first alert tick sends nothing, it only learns the state")
        ck(ph.alerts_tick() == [], "NULL: no change, no message")
        state["h"] = dict(state["h"], alive=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> DOWN" in P(sent[0]) and P(sent[0]).startswith("🔴 STATE CHANGED"),
           "the bot going down sends one alert, its new state as the headline")
        ck(not tg_html_problems(sent[0]) and getattr(sent[0], "is_html", False)
           and P(tg.sent[-1][1]) == P(sent[0]), "...valid Telegram HTML, and it is what went to the chat")
        ck(ph.alerts_tick() == [], "...and not a second one while it stays down")
        state["h"] = dict(state["h"], alive=True)
        ck("DOWN -> TRADING" in P(ph.alerts_tick()[0]), "coming back sends one too")
        state["h"] = dict(state["h"], blind={"since": None, "bad": 12, "why": "it cannot reach Kalshi"})
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> BLIND" in P(sent[0]) and "NOT TRADING" in P(sent[0]),
           "THE 09-21 NIGHT: alive but blind sends an alert -- it used to stay TRADING")
        state["h"] = dict(state["h"], blind=None)
        ck("BLIND -> TRADING" in P(ph.alerts_tick()[0]), "and seeing again sends one")
        state["h"] = dict(state["h"], kalshi_ok=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "RECORDER SILENT: Kalshi recorder" in P(sent[0]) and not tg_html_problems(sent[0]),
           "a silent Kalshi recorder sends one alert")
        ck(ph.alerts_tick() == [], "...and not a second while it stays silent")
        state["h"] = dict(state["h"], kalshi_ok=True)
        ck("WRITING AGAIN" in P(ph.alerts_tick()[0]), "and writing again sends one")
        # A LAYOUT BUG MUST NEVER SWALLOW AN ALERT: the state-change layout planted to fail -> the plain words go
        _sv_ast = globals()["alert_state_text"]
        try:
            globals()["alert_state_text"] = lambda *a: 1 / 0
            state["h"] = dict(state["h"], alive=False)
            sent = ph.alerts_tick()
        finally:
            globals()["alert_state_text"] = _sv_ast
        ck(len(sent) == 1 and not getattr(sent[0], "is_html", False)
           and sent[0].startswith("STATE CHANGED: TRADING -> DOWN\n"),
           "a state-change alert whose layout fails still goes, in the plain words it always had")
        state["h"] = dict(state["h"], alive=True)
        ck("DOWN -> TRADING" in P(ph.alerts_tick()[0]), "...and the next change is laid out again")
        # THE DISK. The pure function first, exact words; then the tick.
        ck(disk_alert(0, 30.0) == (0, None) and disk_alert(0, 9.01) == (0, None), "disk: plenty free, nothing")
        ck(disk_alert(0, 7.5) == (8, "DISK 7.5 GB free, under 8 GB. The recorders stop themselves for good at 5 GB and "
           "that tape cannot be recreated; at about 4 GB a day that is roughly 0.6 days. Next warning under 6 GB."),
           "disk: under 8 GB sends the first warning, with the days left to the hard stop")
        ck(disk_alert(8, 7.2) == (8, None), "...not again while it stays under 8")
        ck(disk_alert(8, 5.9) == (6, "DISK 5.9 GB FREE -- 0.9 GB from the 5 GB line where the recorders STOP FOR GOOD "
           "and the tape ends. Free space or plug in the new drive NOW. (Sent again only if it climbs over 9 GB and "
           "falls back.)"), "disk: under 6 GB sends the second, louder one")
        ck(disk_alert(0, 5.9)[0] == 6, "...straight to the under-6 alert if the first was never sent")
        ck(disk_alert(6, 5.5) == (6, None) and disk_alert(6, 7.5) == (6, None) and disk_alert(6, 8.5) == (6, None),
           "...and nothing more between 5 and 9 GB")
        ck(disk_alert(6, 9.5) == (0, None) and disk_alert(8, 9.5) == (0, None), "over 9 GB re-arms, silently")
        ck(disk_alert(8, None) == (8, None) and disk_alert(0, None) == (0, None), "NULL: an unreadable disk changes nothing")
        state["h"] = dict(state["h"], disk_gb=7.5)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and P(sent[0]).startswith("⚠️ DISK 7.5 GB free, under 8 GB.") and ph.disk_level == 8
           and P(sent[0]).replace("⚠️ ", "", 1).replace("\n", " ") == disk_alert(0, 7.5)[1],
           "the tick sends the under-8 alert once, disk_alert's exact words under a headline")
        state["h"] = dict(state["h"], disk_gb=7.1)
        ck(ph.alerts_tick() == [], "...and not again at 7.1")
        state["h"] = dict(state["h"], disk_gb=5.9)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and P(sent[0]).startswith("🚨 DISK 5.9 GB FREE") and ph.disk_level == 6
           and P(sent[0]).replace("🚨 ", "", 1).replace("\n", " -- ", 1) == disk_alert(8, 5.9)[1],
           "under 6 sends the second, its exact words")
        state["h"] = dict(state["h"], disk_gb=8.5)
        ck(ph.alerts_tick() == [] and ph.disk_level == 6, "8.5 GB: nothing, still armed at 6")
        state["h"] = dict(state["h"], disk_gb=9.5)
        ck(ph.alerts_tick() == [] and ph.disk_level == 0, "9.5 GB: re-armed, nothing sent")
        state["h"] = dict(state["h"], disk_gb=7.9)
        ck(len(ph.alerts_tick()) == 1, "...so the next dip under 8 is announced again")
        ph.muted = True
        state["h"] = dict(state["h"], disk_gb=5.0)
        ck(ph.alerts_tick() == [] and ph.disk_level == 6, "muted: the disk line is tracked but not sent")
        ph.muted = False
        state["h"] = dict(state["h"], disk_gb=30.0)
        ck(ph.alerts_tick() == [] and ph.disk_level == 0, "back to 30 GB: re-armed")
        # a new losing close
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "order", "t": "2026-09-16T14:14:31Z", "ticker": c2, "filled": 40.0, "exec_price": 0.97, "status": "executed", "body": {"count": "40.00"}}) + "\n")
            pass
        # THE LOSS ARRIVES IN KALSHI'S BOOKS, not in our log -- that is where
        # money lives now, and it is why the alert can no longer mistake one
        # leg of a hedged market for a losing trade.
        _led = json.load(open(_pl.LEDGER, encoding="utf-8"))
        _led["settlements"]["k2"] = {
            "ticker": c2, "market_result": "yes",
            "no_count_fp": "40.00", "no_total_cost_dollars": "38.80",
            "yes_count_fp": "0.00", "yes_total_cost_dollars": "0.00",
            "revenue": 0, "fee_cost": "0.00",
            "settled_time": "2026-09-16T14:15:20Z"}
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump(_led, _fh)
        os.utime(_pl.LEDGER, (time.time() + 5, time.time() + 5))
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and P(sent[0]).startswith("🔴 LOSS -$38.80 (-")
           and "% of the bank) · pin bot (main account) · the quarter-hour closing 10:15 AM ET on Sep 16"
           in P(sent[0]).split("\n")[0]
           and "\n• BTC NO at 97.0c, 40 contracts → settled YES: -$38.80" in P(sent[0]) and "WHY IT HURTS" in P(sent[0])
           and not tg_html_problems(sent[0]),
           "a new losing close is sent with its story: the loss as the headline naming the bot and its account (10-26), "
           "one line a leg")
        _mix = P(alert_loss_text(L, calendar.timegm((2026, 9, 16, 14, 15, 0)), -37.0, [
            {"tk": c2, "want": "no", "cost": 0.97, "result": "yes", "pnl": -38.80},
            {"tk": "KXCRYPTOLEAD15M-26SEP161015-SOL", "want": "yes", "cost": 0.9, "result": "yes", "pnl": 1.80, "n": 20.0}]))
        ck(" · pin bot + coin race (main account) · " in _mix.split("\n")[0]
           and "\n• pin bot · BTC NO at 97.0c, 40 contracts" in _mix and "\n• coin race · SOL YES at 90.0c, 20 contracts" in _mix,
           "a losing close holding both main-account bots' legs names both, and each leg its bot (the race leg's "
           "contracts are Kalshi's, not the pin bot's orders): %r" % _mix)
        ck(ph.alerts_tick() == [], "...once")
        ph.muted = True
        state["h"] = dict(state["h"], alive=False)
        ck(ph.alerts_tick() == [] and ph.last_state == "DOWN", "muted: the change is tracked but not sent")
        ph.muted = False
        ck(not any("YESTERDAY" in P(t_).split("\n")[0] for _c, t_ in tg.sent),
           "a summary already due at startup is NOT re-sent (it started at 11 AM ET)")
        # next day, 9 AM ET: the daily summary of the 16th goes out once
        now["t"] += 86400 - 2 * 3600
        sent = ph.alerts_tick()
        _dl = [m for m in sent if "YESTERDAY" in P(m).split("\n")[0]]
        ck(len(_dl) == 1 and P(_dl[0]).startswith("☀️ YESTERDAY, Wed Sep 16 · every bot")
           and "All bots yesterday" in P(_dl[0]) and "📊 By bot" in P(_dl[0])
           and "☀️ YESTERDAY -$37.14 (-7.43%) · Wed Sep 16" in P(_dl[0])
           and "MONEY: -$37.14, which is -7.43% of the $500.00" in P(_dl[0]) and not tg_html_problems(_dl[0]),
           "after 8 AM ET the daily summary of yesterday goes out: every bot's day with its % of all pots and each "
           "bot's % of its bank, then the main account's money and % of its day-start bank behind a tap")
        ck(not any("YESTERDAY" in P(m).split("\n")[0] for m in ph.alerts_tick()), "...once per day")
        ck(all(cid == 111 for cid, _t in tg.sent), "every alert went to the paired chat")
        # long messages are split by the real transport's rule
        big = "x" * (MAX_LEN * 2 + 5)
        chunks = split_text(big)
        ck(len(chunks) == 3 and sum(len(c) for c in chunks) == len(big), "a long reply is split under Telegram's limit")
        ck(split_text("a\n\nb\n\nc", 3) == ["a", "b", "c"] and split_text("ab\ncd\nef", 5) == ["ab", "cd\nef"]
           and split_text("", 5) == [""], "...at a blank line when one is there, else a line, else hard")
        _calls = []
        _real = Telegram("tok")
        _real._call = lambda method, params, http_timeout=45: _calls.append(params["text"])
        _real.send(111, "A" * 2500 + "\n\n" + "B" * 2500)
        ck(_calls == ["A" * 2500, "B" * 2500],
           "the real transport sends a long /bars in whole paragraphs, never mid-sentence")
        # poll_once routes replies to the sender and advances the offset
        tg.push(111, "/help")
        tg.push(333, "/status")
        ph.poll_once()
        ck(tg.sent[-1][0] == 111 and "Commands" in P(tg.sent[-1][1]) and ph.offset == 3, "poll: the paired chat gets its reply, the stranger nothing, offset advances")

        # ---- charts after the words (2026-10-18) -------------------------------------------------------
        # The picture is queued AFTER the words are sent and drawn on one background thread: poll_once never
        # waits for it, alerts run meanwhile, the controls never queue one, a stranger gets none, a failing or
        # late picture only logs, and a full queue drops (never blocks). tgcharts' own --selftest draws them.
        import threading as _thr
        _tgcm = _tgc()
        ck(all(_tgcm.kind_of(c_) is None for c_ in ("/open", "/help", "/pause", "/start", "/stop", "/mute", "/unmute",
                                                     "/pair"))
           and _tgcm.kind_of("/today") == "today" and _tgcm.kind_of("/funds") == "funds" and ph.charts_on is False,
           "charts: off unless main() turns them on; the controls, /open and /help never get a picture")
        _pb = photo_body(111, b"\x89PNG\r\n\x1a\nDATA", "Today +$1.00", "BND")
        ck(_pb.startswith(b"--BND\r\n") and b'name="chat_id"\r\n\r\n111\r\n' in _pb
           and b'name="caption"\r\n\r\nToday +$1.00\r\n' in _pb
           and _pb.endswith(b'filename="chart.png"\r\nContent-Type: image/png\r\n\r\n\x89PNG\r\n\x1a\nDATA\r\n--BND--\r\n'),
           "sendPhoto's multipart body: chat_id, caption, the PNG byte for byte, the closing boundary")
        _posted = []
        _tp = Telegram("tok")
        _tp._post = lambda method, body, ctype, http_timeout=60: (_posted.append((method, ctype, body)), {"ok": True})[1]
        _tp.send_photo(111, b"PNG", "cap")
        ck(_posted and _posted[0][0] == "sendPhoto" and _posted[0][1].startswith("multipart/form-data; boundary=pinphone")
           and (b"--" + _posted[0][1].split("=", 1)[1].encode() + b"--\r\n") in _posted[0][2],
           "the transport posts the picture to sendPhoto with its own boundary")
        _tp._post = lambda *a, **k: {"ok": False, "description": "Bad Request"}
        try:
            _tp.send_photo(111, b"PNG", "cap")
            _rf = None
        except RuntimeError as e:
            _rf = e
        ck(_rf is not None, "a refused sendPhoto raises (the chart thread logs it; the words already went)")
        _in, _gate, _seen = _thr.Event(), _thr.Event(), []

        def _slow_chart(kind, ctx):
            _seen.append((kind, ctx))
            _in.set()
            _gate.wait(20)
            return (b"\x89PNG fake", "caption " + kind)
        ph.chart_fn, ph.charts_on = _slow_chart, True
        _n0 = len(tg.sent)
        tg.push(111, "/today")
        _t0 = time.time()
        ph.poll_once()
        _dtp = time.time() - _t0
        ck(len(tg.sent) == _n0 + 1 and tg.photos == [] and _dtp < 5,
           "charts: the words go first; poll_once returns without waiting for the picture (%.2f s)" % _dtp)
        ck(_in.wait(20), "charts: the picture is drawn on the background thread")
        _sv = (ph.last_state, ph.last_rec, ph.seen_losses, ph.last_daily, ph.disk_level, list(tg.sent))
        ck(isinstance(ph.alerts_tick(), list), "charts: an alert check runs while a picture is still drawing")
        ph.last_state, ph.last_rec, ph.seen_losses, ph.last_daily, ph.disk_level, tg.sent[:] = _sv
        tg.push(111, "/stop")
        tg.push(111, "/help")
        tg.push(333, "/today")
        ph.poll_once()
        ck(ph._chart_q.qsize() == 0, "charts: /stop (its confirm question), /help and a stranger's /today queue nothing")
        tg.push(111, "/days")
        tg.push(111, "/losses")
        tg.push(111, "/stats")
        ph.poll_once()
        ck(ph._chart_q.qsize() == CHART_QUEUE,
           "charts: while one draws, %d wait and the next is dropped -- the poll loop never blocks" % CHART_QUEUE)
        _gate.set()
        ph._chart_q.join()
        ck([(c_, k_) for c_, _p, k_ in tg.photos] == [(111, "caption today"), (111, "caption days"), (111, "caption losses")]
           and tg.photos[0][1] == b"\x89PNG fake", "charts: each picture goes to the paired chat after its words, in order")
        _cx = _seen[0][1]
        ck(_seen[0][0] == "today" and _cx["ledger"] is not ph.ledger and _cx["ledger"].settled == ph.ledger.settled
           and _cx["ledger"].settled is not ph.ledger.settled and _cx["now"] == now["t"] and _cx["pp"].Phone is Phone,
           "charts: the picture reads a private copy of the ledger taken with the words, on the phone's clock")
        _n1 = len(tg.photos)
        for _fn, _why in ((lambda kind, ctx: 1 / 0, "ZeroDivisionError"), (lambda kind, ctx: None, "nothing live to draw")):
            ph.chart_fn = _fn
            tg.push(111, "/days")
            ph.poll_once()
            ph._chart_q.join()
            with open(LOG, encoding="utf-8") as _fh:
                _lgc = _fh.read()
            ck(len(tg.photos) == _n1 and _why in _lgc and ("All bots last 7 days" in P(tg.sent[-1][1]).split("\n")[0]
                                                            or "All time" in P(tg.sent[-1][1]).split("\n")[0]),
               "charts: a picture that fails or has nothing to draw only logs (%s); the words went as always" % _why)
        ph.chart_fn, ph.chart_stale_s = _slow_chart, -1
        tg.push(111, "/days")
        ph.poll_once()
        ph._chart_q.join()
        with open(LOG, encoding="utf-8") as _fh:
            _lgc = _fh.read()
        ck(len(tg.photos) == _n1 and "dropped: its turn came" in _lgc, "charts: a picture whose turn comes late is dropped, never sent stale")

        def _no_mpl(kind, ctx):
            raise ImportError("No module named 'matplotlib'")
        ph.chart_fn, ph.chart_stale_s = _no_mpl, None
        tg.push(111, "/days")
        ph.poll_once()
        ph._chart_q.join()
        tg.push(111, "/today")
        ph.poll_once()
        ck(ph.charts_on is False and ph._chart_q.qsize() == 0 and len(tg.photos) == _n1,
           "charts: without matplotlib the phone turns pictures off (logged once) and keeps sending the words")
        ph.chart_fn = None

        # ---- /funds /bank /accounts (2026-10-11) ----------------------------------------------------
        # A fake Kalshi with 3 accounts across 2 cash pools. Worked by hand: main = 500.00 + 1.50 cash +
        # 29.10 open = 530.60 (the 0-contract row's 9.99 is not a bet); sub 1 = 80.25; sub 3 = 40.00 +
        # 1.10 open = 41.10; all = 651.95 = cash 621.75 + open 30.20. Kalshi's whole-account cash: pool 0 =
        # 1.50 + 40.00 = 41.50, pool 2 = 580.25 -> 621.75. /portfolio/balance's `balance` is CENTS here
        # (as Kalshi sends it), so a reader that used it instead of balance_dollars would be 100x off.
        fw_list = [{"subaccount_number": 0, "exchange_index": 2, "balance": "500.0000"},
                   {"subaccount_number": 0, "exchange_index": 0, "balance": "1.5000"},
                   {"subaccount_number": 1, "exchange_index": 0, "balance": "0.0000"},
                   {"subaccount_number": 1, "exchange_index": 2, "balance": "80.2500"},
                   {"subaccount_number": 3, "exchange_index": 0, "balance": "40.0000"},
                   {"subaccount_number": 3, "exchange_index": 2, "balance": "0.0000"}]
        fw_pos = {0: [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00", "market_exposure_dollars": "29.10"},
                      {"ticker": "KXETH15M-26SEP161115-15", "position_fp": "0.00", "market_exposure_dollars": "9.99"}],
                  3: [{"ticker": "KXHIGHNY-26SEP16-B70.5", "position_fp": "-2.00", "market_exposure_dollars": "1.10"}]}
        fw_break = [{"balance": "41.5000", "exchange_index": 0}, {"balance": "0.0000", "exchange_index": 1},
                    {"balance": "580.2500", "exchange_index": 2}]

        # PAST DAYS: the same 3 accounts' settlement rows, pages newest first, in BOTH cash pools (ix). The
        # phone's clock for these checks: 11:00 AM ET Wed Sep 16, so the 7 days are Thu Sep 10 .. Wed Sep 16.
        # Worked by hand, per market = payout - cost - fee:
        #   main: Wed 16 = ETH 12:15 AM -19.62 (lost) + race +0.14 = -19.48 | Tue 15 = BTC 11:30 PM +0.19 +
        #         BTC hourly +1.00 = +1.19 | Mon 14 = BTC 12:00 PM in TWO rows (+0.57, -0.90) = ONE market
        #         -0.33 (lost) + NY high (pool 0) +0.80 = +0.47 -> 7 days -17.82 (2 of 6 lost) = main bot
        #         -19.76 (2 of 3) + race +0.14 (0 of 1) + other +1.80 (0 of 2); -3.4% of its $530.60.
        #   sub 1: Wed 16 +0.05; Sat 12 (9:15 PM ET, settled the 13th UTC) -9.90 -> -9.85 (1 of 2 lost),
        #          -12.3% of $80.25 -- the $50 moved into it that week is NOT a gain.
        #   sub 3 (pool 0): Tue 15 +0.50 (a ticker with no date: its settled time 11:40 PM ET, the 16th in
        #          UTC) + Mon 14 -1.70 (lost) -> -1.20 (1 of 2 lost), -2.9% of $41.10.
        def _R(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0, ix=2):
            return {"ticker": tk, "settled_time": st, "market_result": res, "value": {"yes": 100, "no": 0}[res],
                    "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc, "no_count_fp": "%.2f" % nn,
                    "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee, "revenue": 0, "exchange_index": ix}
        fr_race = _R("KXCRYPTOLEAD15M-26SEP160930-XRP", "2026-09-16T13:30:20Z", "yes", yn=5, yc=4.85, fee=0.01)
        fr_eth0015 = _R("KXETH15M-26SEP160015-15", "2026-09-16T04:15:03.2Z", "no", yn=20, yc=19.60, fee=0.02)
        fr_btc2330 = _R("KXBTC15M-26SEP152330-30", "2026-09-16T03:30:03.1Z", "no", nn=10, nc=9.80, fee=0.01)
        fr_hourly = _R("KXBTCD-26SEP1511-T60000", "2026-09-15T15:00:10Z", "yes", yn=2, yc=1.00)
        fr_wx0 = _R("KXHIGHNY-26SEP14-B70.5", "2026-09-15T12:00:00Z", "no", nn=2, nc=1.20, ix=0)
        fr_two_b = _R("KXBTC15M-26SEP141200-00", "2026-09-14T16:00:05Z", "no", yn=30, yc=0.90)
        fr_two_a = _R("KXBTC15M-26SEP141200-00", "2026-09-14T16:00:03Z", "no", nn=30, nc=29.40, fee=0.03)
        fr_old = _R("KXBTC15M-26SEP090900-00", "2026-09-09T13:00:03Z", "no", yn=50, yc=49.00)       # Sep 9: out
        fr_older = _R("KXBTC15M-26SEP081000-00", "2026-09-08T14:00:03Z", "no", yn=60, yc=59.00)     # never asked
        fw_xfer = {"amount_cents": 5000, "from_subaccount": 0, "to_subaccount": 1, "created_ts": 1789900000}
        fw_stl = {0: [[fr_race, fr_eth0015, fr_btc2330], [fr_hourly, fr_wx0, fr_two_b],
                      [dict(fr_two_b), fr_two_a, fr_old], [fr_older]],   # fr_two_b again: it slid across a page edge
                  1: [[_R("KXNEAR15M-26SEP160300-00", "2026-09-16T07:00:03Z", "no", nn=5, nc=4.95),
                       dict(fw_xfer, settled_time="2026-09-15T12:00:00Z", revenue=5000),   # money, but not a market
                       _R("KXBNB15M-26SEP122115-15", "2026-09-13T01:15:03Z", "yes", nn=10, nc=9.90)]],
                  3: [[_R("KXODD-XYZ", "2026-09-16T03:40:00Z", "yes", yn=1, yc=0.50, ix=0),
                       _R("KXHIGHNY-26SEP14-B71.5", "2026-09-15T12:00:00Z", "yes", nn=2, nc=1.70, ix=0)]]}

        def fw_get(asked, bad=lambda path, q: None, rows=None, pos=None, brk=None, stl=None):
            def get(path, q):
                asked.append((path, dict(q)))
                b = bad(path, q)
                if b == "raise":
                    raise OSError("connection reset")
                if b is not None:
                    return b
                if path == "/portfolio/settlements":          # pages per account, newest first (below)
                    pg = (stl if stl is not None else fw_stl).get(q["subaccount"], [[]])
                    i = int(q.get("cursor") or 0)
                    return 200, {"settlements": pg[i], "cursor": str(i + 1) if i + 1 < len(pg) else ""}
                if path in ("/portfolio/subaccounts/transfers", "/portfolio/deposits"):
                    return 200, {"transfers": [fw_xfer], "deposits": [{"amount_cents": 100000, "status": "applied"}],
                                 "cursor": ""}
                if path == "/portfolio/subaccounts/balances":
                    return 200, {"subaccount_balances": rows if rows is not None else fw_list}
                if path == "/portfolio/balance":
                    for r in (rows if rows is not None else fw_list):
                        if (r["subaccount_number"], r["exchange_index"]) == (q["subaccount"], q["exchange_index"]):
                            return 200, {"balance": int(round(100 * float(r["balance"]))), "balance_dollars": r["balance"],
                                         "balance_breakdown": brk if brk is not None else fw_break}
                    return 404, {"error": "not found"}
                if path == "/portfolio/positions":
                    return 200, {"market_positions": (pos if pos is not None else fw_pos).get(q["subaccount"], []),
                                 "event_positions": [], "cursor": ""}
                return 404, "unknown path"
            return get

        fa = []
        f_ = funds_read(fw_get(fa))
        _fw_act = ("pin", "race", "ladder")      # v-tg-active: the bots running in this world (the weather pot's stopped)
        t_ = funds_text(f_, {}, now["t"], active=_fw_act)
        cprint("    --- /funds, the fake world (as the phone shows it) ---\n    " + P(t_).replace("\n", "\n    "))
        ck(sorted(f_["subs"]) == [0, 1, 3] and f_["list_err"] is None, "/funds: the 3 listed accounts, from Kalshi's list")
        ck(getattr(t_, "is_html", False) and not tg_html_problems(t_) and fits(t_), "/funds: Telegram-valid, one message")
        tp_ = P(t_)
        ck("MAIN ACCOUNT (0) -- main bot (pin) + coin race: $530.60" in tp_
           and "\ncash: weather pool $1.50, crypto pool $500.00; open bets: $29.10 on 1 market" in tp_,
           "/funds: main = cash in BOTH pools + what its open bet cost = $530.60 (a 0-contract row is not a bet)")
        ck("SUBACCOUNT 1 -- penny ladder: $80.25" in tp_ and "SUBACCOUNT 3 -- weather pool: nothing runs here now "
           "(stopped); crypto pool: nothing runs here now (stopped): $41.10" in tp_ and "weather dip-seller" not in tp_,
           "/funds: each subaccount's total, and what runs in it from FUNDS_WHAT -- only the running bots named")
        ck(tp_.split("\n")[0] == "🏦 ALL ACCOUNTS: $651.95 = cash $621.75 + open bets $30.20.",
           "/funds: the grand total, 3 accounts x 2 pools, is the headline")
        ck(any(x.split() == ["0", "main+race", "530.60", "81.4%"] for x in tp_.split("\n"))
           and any(x.split() == ["1", "ladder", "80.25", "12.3%"] for x in tp_.split("\n"))
           and any(x.split() == ["3", "idle", "41.10", "6.3%"] for x in tp_.split("\n")),
           "/funds: one row an account, its total and its share of all of them (530.60 / 651.95 = 81.4%)")
        ck("💤 Idle: $41.10 (6.3% of all) sits in an account that runs nothing now (3: weather pool: nothing runs here "
           "now (stopped); crypto pool: nothing runs here now (stopped))." in tp_,
           "/funds: money in an account whose bots are all stopped is named as idle, with its share")
        # v-tg-active (2026-10-30): the jump band runs in subaccount 3's crypto pool; the coin race is paused
        _tj = P(funds_text(f_, {3: ["jump band up to 5 contracts a buy"]}, now["t"], active=("pin", "ladder", "jumpband")))
        ck("MAIN ACCOUNT (0) -- main bot (pin): $530.60" in _tj and "coin race" not in _tj
           and "SUBACCOUNT 3 -- weather pool: nothing runs here now (stopped); crypto pool: jump band: BNB/HYPE/ZEC/NEAR "
               "after a price jump (live stage 1, 2026-10-30): $41.10" in _tj
           and any(x.split() == ["3", "jump", "band", "41.10", "6.3%"] for x in _tj.split("\n"))
           and any(x.split() == ["0", "main", "530.60", "81.4%"] for x in _tj.split("\n"))
           and "Idle" not in _tj and "bet size now: jump band up to 5 contracts a buy" in _tj
           and funds_what(3) == FUNDS_WHAT[3] and funds_idle(2, ("pin",)) and not funds_idle(3, ("jumpband",)),
           "/funds with the jump band running and the race paused: the main account names the pin bot only, subaccount 3 "
           "its crypto pool's jump band and its bet size, no idle money: %r" % _tj[:400])
        ck("The cash adds up to Kalshi's own whole-account figure ($621.75)." in tp_,
           "/funds: checked against Kalshi's whole-account cash by pool")
        ck(not any(p == "/portfolio/balance" and (q["subaccount"], q["exchange_index"]) in ((1, 0), (3, 2)) for p, q in fa),
           "/funds: a pool listed at 0 is $0 in any unit -- not read again")
        ck(set(p for p, _q in fa) <= set(FUNDS_PATHS) and set(p for p, _q in f_["asked"]) == set(FUNDS_PATHS)
           and all("subaccount" in q for p, q in fa if p != FUNDS_PATHS[0])
           and all("exchange_index" in q for p, q in fa if p == "/portfolio/balance"),
           "/funds: only the three GET paths; every balance read names its account AND pool, every open-bets read its account")
        ck("SUBACCOUNT 7 -- unknown" in P(funds_text(funds_read(fw_get([], rows=fw_list + [
            {"subaccount_number": 7, "exchange_index": 2, "balance": "2.0000"}])), {}, now["t"])),
           "/funds: an account not in FUNDS_WHAT is shown as unknown, not dropped")
        t_ = P(funds_text(funds_read(fw_get([], brk=[{"balance": "41.5000", "exchange_index": 0},
                                                     {"balance": "600.0000", "exchange_index": 2}])), {}, now["t"]))
        ck("CHECK: Kalshi's own whole-account cash is $641.50, but the accounts above add to $621.75" in t_,
           "/funds: cash Kalshi holds that no listed account explains is said")
        # unreadable reads: said, never $0, never a crash
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (503, "busy") if p == "/portfolio/balance"
                                            and q["subaccount"] == 1 else None)), {}, now["t"]))
        ck("SUBACCOUNT 1 -- penny ladder: $80.25" in t_ and "crypto pool $80.25 (from Kalshi's list; the direct read failed: "
           "HTTP 503)" in t_ and "ALL ACCOUNTS: $651.95" in t_,
           "/funds: one direct cash read fails -> the list's figure, marked, because other pools proved its unit")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/balance" else None)),
                          {}, now["t"]))
        ck("$500.00" not in t_ and "$80.25" not in t_ and "crypto pool COULD NOT READ (HTTP 500)" in t_
           and t_.split("\n")[0] == "🏦 ALL ACCOUNTS: at least $30.20 (cash $0.00 + open bets $30.20)"
           and "That leaves out what could not be read: main account weather pool cash, main account crypto pool "
           "cash, subaccount 1 crypto pool cash, subaccount 3 weather pool cash." in t_ and "adds up" not in t_
           and "CHECK:" not in t_ and any(x.split() == ["0", "main+race", ">=29.10", "-"] for x in t_.split("\n")),
           "/funds: EVERY direct cash read fails -> the list's unit is unproven, so no cash figure is shown (hard rule 5), "
           "and no account's share is worked from totals that leave money out")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == FUNDS_PATHS[0] else
                                            "raise" if p == "/portfolio/balance" and q["subaccount"] == 1
                                            and q["exchange_index"] == 2 else None)), {}, now["t"]))
        ck("list of subaccounts could not be read (HTTP 500)" in t_
           and "MAIN ACCOUNT (0) -- main bot (pin) + coin race: $530.60" in t_
           and "SUBACCOUNT 1 -- penny ladder: at least $0.00" in t_
           and "crypto pool COULD NOT READ (error: connection reset)" in t_
           and "SUBACCOUNT 4 -- weather pool: FX taker: the 5 currency pairs (penny test, 2026-10-25); crypto pool: coin-race reward test (stopped): at least" in t_ and "ALL ACCOUNTS: at least" in t_,
           "/funds: the list fails and a read raises -> the known accounts are tried, what failed is named, no crash")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/positions"
                                            and q["subaccount"] == 3 else None,
                                            pos={0: [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00",
                                                      "market_exposure_dollars": "29.10"}],
                                                 1: [{"ticker": "KXNEAR15M-26SEP161115-15", "position_fp": "5.00",
                                                      "market_exposure": 110}]})), {}, now["t"], active=_fw_act))
        ck("SUBACCOUNT 3 -- weather pool: nothing runs here now (stopped); crypto pool: nothing runs here now (stopped): "
           "at least $40.00" in t_
           and "open bets: COULD NOT READ (HTTP 500)" in t_
           and "open bets: COULD NOT READ (a bet came without market_exposure_dollars)" in t_
           and "ALL ACCOUNTS: at least $650.85 (cash $621.75 + open bets $29.10)\n" in t_
           and "That leaves out what could not be read: subaccount 1 open bets, subaccount 3 open bets." in t_,
           "/funds: an unreadable open-bets read, and a bet with only cents (never read as dollars), are said")
        clk = {"t": 0.0}

        def _tick():
            clk["t"] += 1.0
            return clk["t"]
        fa = []
        t_ = P(funds_text(funds_read(fw_get(fa), clock=_tick, deadline_s=2), {}, now["t"]))
        ck(len(fa) == 2 and "the 2 s limit for /funds ran out first" in t_ and "ALL ACCOUNTS: at least" in t_,
           "/funds: a slow Kalshi hits the time limit -> the rest is said as not read, the phone is not stalled")
        # bet sizes from each bot's own log
        szd = os.path.join(td, "funds_sizes")
        os.makedirs(szd)
        ck(funds_sizes(szd) == {}, "/funds sizes: no logs -> no size invented")

        def _wl(name, recs):
            with open(os.path.join(szd, name), "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
        with open(os.path.join(szd, "pinrun-live-size.json"), "w", encoding="utf-8") as fh:
            json.dump({"size": 77.0, "bank": 900.0, "at": "2026-10-11T08:00:00Z"}, fh)
        ck(funds_sizes(szd) == {0: ["main bot 77 contracts a bet (sized Oct 11 4:00 AM ET on a $900.00 bank)"]},
           "/funds sizes: no live log yet -> the main bot's size file")
        _wl("pinrun-live-20261010T020723Z.jsonl", [{"kind": "autosize", "t": "2026-10-10T08:00:00Z", "old": 40, "new": 50,
                                                    "why": "bank $600.00"}])
        _wl("pinrun-live-20261010T221608Z.jsonl", [
            {"kind": "start", "t": "2026-10-10T22:16:08Z", "size": 20},
            {"kind": "autosize", "t": "2026-10-11T08:27:42Z", "old": 95.0, "new": 90.0, "why": "bank $1069.74"},
            {"kind": "autosize", "t": "2026-10-11T08:32:42Z", "old": 90.0, "new": 91.0, "why": "bank $1070.44"},
            {"kind": "signal", "t": "2026-10-11T08:33:00Z", "size": 91}])
        _wl("pinracepenny-live.jsonl", [{"kind": "start", "t": "2026-10-10T06:20:08Z",
                                         "live_rails": {"max_contracts": 20.0, "max_stake": 40.0}}])
        _wl("ladder-live-orders.jsonl", [
            {"t": "2026-10-07T12:14:18.105Z", "ev": "start", "subaccount": 1, "pot": 76.7293, "rails": {"size": 5}},
            {"t": "2026-10-11T04:00:10.450Z", "ev": "rescale", "old": 5, "new": 6, "pot": 84.5, "rails": {"size": 6}},
            {"t": "2026-10-11T04:01:00Z", "ev": "order", "count": 6}])
        _wl("forecaster-live-orders.jsonl", [
            {"t": "2026-10-10T06:20:10.831Z", "ev": "start", "pot": 83.9334, "rails": {"scale": "0.1332", "per_side": 13}},
            {"t": "2026-10-11T04:00:07.723Z", "ev": "rescale", "old": 0.1332, "new": 0.146, "pot": 91.9692,
             "rails": {"scale": "0.146", "per_side": 15}}])
        sz_ = funds_sizes(szd)
        ck(sz_ == {0: ["main bot 91 contracts a bet (sized Oct 11 4:32 AM ET on a $1,070.44 bank)",
                       "coin race 20 contracts a bet, at most $40 in play (set at its start Oct 10 2:20 AM ET)"],
                   1: ["ladder 6-contract bids (sized Oct 11 12:00 AM ET on a $84.50 pot)"],
                   2: ["forecaster 14.6% of the paper bot's size, up to 15 contracts a side "
                       "(sized Oct 11 12:00 AM ET on a $91.97 pot)"]},
           "/funds sizes: main = newest autosize in the NEWEST live log; ladder and forecaster = their newest "
           "rescale, not the older start")
        # v-race-snowball (2026-10-11): a start record with bank_sizing sizes from the bank -- the size in force is the
        # newest bank_size record after it, not the start-up live_rails (2026-10-18: /funds had said "20 contracts")
        _wl("pinracepenny-live.jsonl", [
            {"kind": "start", "t": "2026-10-10T06:20:08Z", "live_rails": {"max_contracts": 20.0, "max_stake": 40.0},
             "bank_sizing": {"contracts_per_bank": 0.019048, "stake_per_bank": 0.038095}},
            {"kind": "bank_size", "t": "2026-10-11T15:54:00Z", "bank": 1254.6932, "contracts": 23.0, "stake": 47.79}])
        ck(funds_sizes(szd)[0][1] == "coin race 23 contracts a leg, at most $47.79 in play (3.81% of a $1,254.69 bank; "
                                     "sized Oct 11 11:54 AM ET, grows with the bank)",
           "/funds sizes: the bank-sized coin race shows the size it last took from the bank (23 = floor(1254.69 x "
           "0.019048); stake cap 1254.69 x 0.038095 = $47.79)")
        th_ = funds_text(funds_read(fw_get([])), sz_, now["t"])
        t_ = P(th_)
        ck("\nbet size now: main bot 91 contracts a bet" in t_ and "\nbet size now: ladder 6-contract bids" in t_
           and "\nSUBACCOUNT 3" in t_ and len(th_) < MAX_LEN, "/funds: each account carries its bots' bet sizes; one message")
        # ---- /funds PAST DAYS (2026-10-11): the world and the hand-worked figures are above fw_get ----
        fnow = calendar.timegm((2026, 9, 16, 15, 0, 0))                 # 11:00 AM ET Wed Sep 16
        ck([funds_book(t) for t in ("KXBTC15M-X", "KXNEWCOIN15M-X", "KXCRYPTOLEAD15M-X", "KXCRYPTOCOMP15M-X",
                                    "KXGOLD15M-X", "KXBTCD-X", "KXHIGHNY-X", "")]
           == ["bot", "bot", "race", "race", "other", "bot", "other", "other"],
           "/funds past days: main bot = 15-minute coin series + its hourly coin series (as /pin); race = the coin "
           "race; weather, oil = other")
        ha = []
        hm = {}
        h_ = funds_settled(fw_get(ha), [0, 1, 3], fnow, memo=hm)
        ck(set(p for p, _q in ha) == {FUNDS_HIST_PATH} and all(q.get("subaccount") in (0, 1, 3) for _p, q in ha)
           and [q.get("cursor") for _p, q in ha if q["subaccount"] == 0] == [None, "1", "2"]
           and sorted(h_) == [0, 1, 3] and all(h_[n]["err"] is None for n in h_),
           "/funds past days: only GET /portfolio/settlements, every request names its account; main's walk stops "
           "on the page that reaches back past Thu Sep 10 (3 pages, the 4th never asked)")
        hd0 = funds_days(h_[0], "2026-09-16")
        hday = {x["day"]: x for x in hd0["days"]}
        ck([x["day"] for x in hd0["days"]] == ["2026-09-16", "2026-09-15", "2026-09-14", "2026-09-13", "2026-09-12",
                                               "2026-09-11", "2026-09-10"] and all(x["read"] for x in hd0["days"]),
           "/funds past days: the last 7 ET days, newest first, all read")
        ck(abs(hday["2026-09-15"]["bot"]["money"] - 1.19) < 1e-9 and hday["2026-09-15"]["bot"]["n"] == 2   # + hourly
           and abs(hday["2026-09-16"]["bot"]["money"] + 19.62) < 1e-9 and hday["2026-09-16"]["bot"]["n"] == 1,
           "/funds past days: an 11:30 PM ET close is that ET day (Tue 15, settled the 16th UTC); a 12:15 AM ET "
           "close is the next (Wed 16)")
        ck(hday["2026-09-14"]["bot"] == {"money": hday["2026-09-14"]["bot"]["money"], "n": 1, "lost": 1}
           and abs(hday["2026-09-14"]["bot"]["money"] + 0.33) < 1e-9,
           "/funds past days: a market with two rows is ONE market, its rows summed (-0.33, lost), and a row read "
           "twice across a page edge counts once")
        hd1, hd3 = funds_days(h_[1], "2026-09-16"), funds_days(h_[3], "2026-09-16")
        ck(hd1["total"]["all"]["n"] == 2 and abs(hd1["total"]["all"]["money"] + 9.85) < 1e-9
           and hd1["days"][4]["all"]["n"] == 1 and hd1["days"][4]["day"] == "2026-09-12",
           "/funds past days: a transfer is never a gain -- a transfer row among the settlements is not a market, "
           "the $50 moved into sub 1 is not read, its 7 days are its 2 settlements (-$9.85); 9:15 PM ET is Sat 12")
        ck(abs(hd3["days"][1]["all"]["money"] - 0.50) < 1e-9 and hd3["days"][0]["all"]["n"] == 0
           and abs(hd3["total"]["all"]["money"] + 1.20) < 1e-9,
           "/funds past days: a ticker with no date falls back to its settled time ON THE ET CLOCK (11:40 PM ET Tue "
           "15, not the 16th UTC); pool-0 weather rows count")
        ck(abs(hd0["total"]["all"]["money"] + 17.82) < 1e-9 and hd0["total"]["all"]["n"] == 6
           and hd0["total"]["all"]["lost"] == 2 and abs(hd0["total"]["bot"]["money"] + 18.76) < 1e-9
           and hd0["total"]["bot"]["n"] == 4 and abs(hd0["total"]["race"]["money"] - 0.14) < 1e-9
           and abs(hd0["total"]["other"]["money"] - 0.80) < 1e-9 and hd0["other_series"] == ["KXHIGHNY"],
           "/funds past days: main split -- main bot -18.76 (4 markets, BTC hourly +1.00 among them), race +0.14, "
           "other +0.80 (the pool-0 NY high); the Sep 9 market is outside the 7 days")
        th_ = funds_text(funds_read(fw_get([])), {}, fnow, h_)
        t_ = P(th_)
        cprint("    --- /funds with past days, the fake world ---\n    " + t_.replace("\n", "\n    "))
        _tl = [x.split() for x in t_.split("\n")]
        _i0 = t_.index("MAIN ACCOUNT (0)")
        _main = t_[_i0:t_.index("SUBACCOUNT 1")]
        ck(["Wed", "16*", "-$19.48", "1/2"] in _tl and ["Tue", "15", "+$1.19", "0/2"] in _tl
           and ["Mon", "14", "+$0.47", "1/2"] in _tl and ["Thu", "10-Sun", "13", "nothing", "settled"] in _tl
           and "7 days: -$17.82 (2 of 6 lost) = -3.4% of the $530.60 it holds now" in _main
           and "Split: main bot -$18.76 (2 of 4 lost) · race +$0.14 (0 of 1 lost) · other +$0.80 (0 of 1 lost; "
               "KXHIGHNY)" in _main
           and "Wed Sep 16 so far: -$19.48 = main bot -$19.62 (1 of 1 lost) + race +$0.14 (0 of 1 lost)\n"
               "Tue Sep 15: +$1.19 = main bot +$1.19 (0 of 2 lost)\n"
               "Mon Sep 14: +$0.47 = main bot -$0.33 (1 of 1 lost) + other +$0.80 (0 of 1 lost)\n"
               "Thu Sep 10 to Sun Sep 13: nothing settled" in _main
           and "Liquidity rewards are paid outside these records and are not counted." in t_,
           "/funds past days: the main account's days newest first (money, lost of settled), its 7-day total and "
           "its % of what it holds now, the main bot / race / other split, and each day split behind a tap")
        ck(any(x.split() == ["0", "main+race", "530.60", "81.4%", "-17.82", "(-3.4%)"] for x in t_.split("\n")),
           "/funds: the summary table carries each account's 7 days too, with its share of what it holds now")
        _s1, _s3 = t_[t_.index("SUBACCOUNT 1"):t_.index("SUBACCOUNT 3")], t_[t_.index("SUBACCOUNT 3"):]
        ck(["Wed", "16*", "+$0.05", "0/1"] in [x.split() for x in _s1.split("\n")]
           and ["Sun", "13-Tue", "15", "nothing", "settled"] in [x.split() for x in _s1.split("\n")]
           and ["Sat", "12", "-$9.90", "1/1"] in [x.split() for x in _s1.split("\n")]
           and "7 days: -$9.85 (1 of 2 lost) = -12.3% of the $80.25 it holds now" in _s1
           and ["Wed", "16*", "nothing", "settled"] in [x.split() for x in _s3.split("\n")]
           and ["Tue", "15", "+$0.50", "0/1"] in [x.split() for x in _s3.split("\n")]
           and ["Mon", "14", "-$1.70", "1/1"] in [x.split() for x in _s3.split("\n")]
           and "7 days: -$1.20 (1 of 2 lost) = -2.9% of the $41.10 it holds now" in _s3
           and t_.count("Past 7 ET days") == 3 and "Deposits and transfers are not gains." in t_
           and "to fit one message" not in t_ and len(th_) <= MAX_LEN and "Split:" not in _s1 + _s3,
           "/funds past days: each subaccount's days unsplit, empty days as one line, one message")
        # the 60 s cache
        hclk = {"t": 1000.0}
        ha = []
        hm = {}
        funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=lambda: hclk["t"], memo=hm)
        n1 = len(ha)
        hclk["t"] += 30
        h2 = funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=lambda: hclk["t"], memo=hm)
        n2 = len(ha)
        hclk["t"] += 31
        funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=lambda: hclk["t"], memo=hm)
        ck(n1 == 5 and n2 == n1 and all(h2[n]["cached"] for n in h2) and len(ha) == 2 * n1
           and abs(funds_days(h2[0], "2026-09-16")["total"]["all"]["money"] + 17.82) < 1e-9,
           "/funds past days: a second /funds within 60 s reads nothing from Kalshi (same figures); after 60 s it "
           "reads again")
        hclk["t"] += 1
        funds_settled(fw_get(ha), [0], fnow + 86400, clock=lambda: hclk["t"], memo=hm)
        ck(len(ha) > 2 * n1, "/funds past days: a new ET day reads again even inside the 60 s")
        # failed reads: what is known is shown, the gap is named, nothing failed is kept
        ha = []
        hm = {}
        h_ = funds_settled(fw_get(ha, bad=lambda p, q: (503, "busy") if p == FUNDS_HIST_PATH and q["subaccount"] == 0
                                  and q.get("cursor") == "2" else (500, {}) if p == FUNDS_HIST_PATH
                                  and q["subaccount"] == 1 else None), [0, 1, 3], fnow, memo=hm)
        t_ = P(funds_text(funds_read(fw_get([])), {}, fnow, h_))
        ck(["Tue", "15", "+$1.19", "0/2"] in [x.split() for x in t_.split("\n")]
           and ["Thu", "10-Mon", "14", "NOT", "READ"] in [x.split() for x in t_.split("\n")]
           and "2 days read: -$18.29 (1 of 4 lost) = -3.4% of the $530.60 it holds now" in t_
           and "Split: main bot -$18.43 (1 of 3 lost) · race +$0.14 (0 of 1 lost)" in t_
           and "Tue Sep 15: +$1.19 = main bot +$1.19 (0 of 2 lost)\nThu Sep 10 to Mon Sep 14: NOT READ" in t_
           and "NOT READ: Mon 14, Sun 13, Sat 12, Fri 11, Thu 10 (HTTP 503)" in t_
           and "SUBACCOUNT 1 -- penny ladder: $80.25\ncash: crypto pool $80.25; open bets: none\n"
           "past 7 ET days: COULD NOT READ (HTTP 500)" in t_ and "7 days: -$1.20 (1 of 2 lost)" in t_
           and sorted(hm) == [3],
           "/funds past days: main's 3rd page fails -> the 2 whole days are shown, Sep 10-14 named NOT READ (the "
           "half-read Sep 14 is not shown); sub 1 fails -> said; neither failed pull is kept")
        h_ = funds_settled(fw_get([], bad=lambda p, q: "raise" if p == FUNDS_HIST_PATH and q["subaccount"] == 3
                                  else (200, {"cursor": ""}) if p == FUNDS_HIST_PATH else None), [0, 3], fnow, memo={})
        ck(h_[0]["err"] == "no 'settlements' list in Kalshi's reply" and h_[3]["err"] == "error: connection reset"
           and "past 7 ET days: COULD NOT READ (no 'settlements' list in Kalshi's reply)"
           in P(funds_text(funds_read(fw_get([])), {}, fnow, h_)),
           "/funds past days: a reply without the settlements list is an error, never 'nothing settled'; a raise is "
           "said")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/balance" else None)),
                          {}, fnow, funds_settled(fw_get([]), [0, 1, 3], fnow, memo={})))
        ck("7 days: -$17.82 (2 of 6 lost); % not shown: what it holds now was not read whole" in t_
           and "% of the $" not in t_,
           "/funds past days: no % on a balance that was not read whole")
        t_ = P(funds_text(funds_read(fw_get([], rows=[{"subaccount_number": 0, "exchange_index": 2, "balance": "0.5000"}],
                                            pos={}, brk=[])), {}, fnow, funds_settled(fw_get([]), [0], fnow, memo={})))
        cprint("    --- /funds past days, an account holding 50c ---\n    " + t_.replace("\n", "\n    "))
        ck("7 days: -$17.82 (2 of 6 lost); % not shown: it holds under $1" in t_ and "% of the $" not in t_,
           "/funds past days: no % of an account holding under $1 (a % of cents is noise)")
        hclk2 = {"t": 0.0}

        def _htick():
            hclk2["t"] += 1.0
            return hclk2["t"]
        ha = []
        hm = {}
        h_ = funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=_htick, deadline_s=3, memo=hm)
        ck(h_[0]["err"] is None and h_[1]["err"] == h_[3]["err"] == "the 3 s limit for /funds ran out first"
           and sorted(hm) == [0] and "past 7 ET days: COULD NOT READ (the 3 s limit for /funds ran out first)"
           in P(funds_text(funds_read(fw_get([])), {}, fnow, h_)),
           "/funds past days: a slow Kalshi hits the history time limit -> the accounts not reached are said, not "
           "kept, and the phone is not stalled")
        # the length limit: 9 busy accounts do not fit 7 day lines each -> fewer, said, every 7-day total kept
        big_rows = [{"subaccount_number": k, "exchange_index": 2, "balance": "1000.0000"} for k in range(9)]
        big_stl = {k: [[_R("%s-26SEP%02d%s-00" % ("KXBTC15M" if j % 2 else "KXCRYPTOLEAD15M", 16 - d, "1015"),
                           "2026-09-%02dT14:15:03Z" % (16 - d), "no", yn=5, yc=1.0 + j) for d in range(7)
                        for j in range(2)] + [_R("KXBTCD-26SEP%02d10-T1" % (16 - d), "2026-09-%02dT14:00:09Z" % (16 - d),
                                                 "yes", yn=5, yc=4.0) for d in range(7)]] for k in range(9)}
        bg = fw_get([], rows=big_rows, brk=[], stl=big_stl)
        bf, bh = funds_read(bg), funds_settled(bg, range(9), fnow, memo={})
        t7 = _funds_page(bf, {}, fnow, bh, 7)
        th_ = funds_text(bf, {}, fnow, bh)
        t_ = P(th_)
        # (subaccount 4 is the FX pairs' pool-0 pot: its coin rows are the old reward test's, left out and said)
        ck(len(t7) > MAX_LEN and len(th_) <= MAX_LEN and t_.count("to fit one message") == 1
           and t_.count("\n7 days: ") == 8 and "left out: 21 markets of the old coin-race test" in t_,
           "/funds past days: when 7 day lines do not fit one message (%d chars), fewer are listed and that is said "
           "once (%d chars); all 9 accounts keep their 7-day total" % (len(t7), len(th_)))
        # routed: /funds /bank /accounts, through handle() and the poll loop
        ck(ph.funds_getter is None, "/funds reads Kalshi through botstats' getter (kauth.get, GET only) by default")
        _FUNDS_HIST.clear()
        _bs_sandbox("botstats-funds-down")                  # botstats cannot read Kalshi: /funds pulls its past days
        _bs_mode["m"] = "down"
        fa = []
        ph.funds_getter = fw_get(fa)
        ck(all(P(ph.handle(111, c_) or "").startswith("🏦 ALL ACCOUNTS: $651.95")
               and "MONEY IN EVERY ACCOUNT" in P(ph.handle(111, c_))
               for c_ in ("/funds", "/bank", "/accounts", "/Funds@pinbot")),
           "/funds, /bank and /accounts are routed to the funds page")
        t_ = P(ph.handle(111, "/funds"))
        ck(["Thu", "17*", "nothing", "settled"] in [x.split() for x in t_.split("\n")]
           and "\nThu Sep 17 so far: nothing settled\nWed Sep 16: -$19.48 = main bot" in t_
           and "Split: main bot -$18.76" in t_ and "7 days: -$17.82 (2 of 6 lost)" in t_
           and "7 days: -$9.85 (1 of 2 lost)" in t_
           and sum(1 for p, _q in fa if p == FUNDS_HIST_PATH) == 5,
           "/funds through handle() carries every account's past days (phone clock: Thu Sep 17); botstats cannot read "
           "Kalshi here, so /funds pulls them itself, and nine /funds inside 60 s read them once")
        ck(ph.handle(333, "/funds") is None, "/funds: a stranger gets nothing")
        ck("/funds" in HELP_TEXT and "/bank" in HELP_TEXT and "/accounts" in HELP_TEXT, "/funds is in /help")
        tg.push(111, "/funds")
        ph.poll_once()
        ck(tg.sent[-1][0] == 111 and "ALL ACCOUNTS: $651.95" in P(tg.sent[-1][1])
           and "main bot 85 contracts a bet" in P(tg.sent[-1][1]) and "Past 7 ET days" in P(tg.sent[-1][1]),
           "/funds through the poll loop: the paired chat gets the page, with the live log's bet size and past days")
        with open(LOG, encoding="utf-8") as _fh:
            _lg = _fh.read()
        ck(os.path.dirname(LOG) == td and "SENT: 🏦 ALL ACCOUNTS: $651.95" in _lg,
           "the self-test logs what it 'sent' to its own temp folder (the phone's words, utf-8), never the live "
           "phone bot's results/pinphone.log")
        # ONE READ (2026-10-26): botstats reads every pot whole -> the past days are its rows and /funds asks Kalshi
        # for no settlements itself; the page is exactly the one its own pull of the same rows gives
        _bs_sandbox("botstats-funds")
        _bs_mode["m"] = "planted"
        _FUNDS_HIST.clear()
        fa = []
        ph.funds_getter = fw_get(fa)
        t_ = ph.handle(111, "/funds")
        _own = funds_text(funds_read(fw_get([])), funds_sizes(ph.ledger.results, ph.active()), now["t"],
                          funds_settled(lambda p, q: _bs_fake(p, dict(q, subaccount=str(q["subaccount"]))), [0, 1, 3],
                                        now["t"], memo={}), active=ph.active())
        ck(str(t_) == str(_own) and not any(p == FUNDS_HIST_PATH for p, _q in fa) and not _FUNDS_HIST
           and "7 days: -$14.00 (2 of 5 lost)" in P(t_) and "7 days: +$0.04 (0 of 1 lost)" in P(t_),
           "/funds past days from botstats' rows: no settlements read of its own, and the same page (main -$14.00, "
           "ladder +$0.04) as this page's own pull of the same rows")
        _FUNDS_HIST.clear()
    globals()["LOG"] = _st_log
    _pl.LEDGER = _pl_sv
    _bsm.RESULTS = _bs_saved[0]
    _bsm._MEMO.clear()
    _bsm._MEMO.update(_bs_saved[1])
    _bsm._BACK.clear()
    _bsm._BACK.update(_bs_saved[2])

    # 2026-10-23: a send the CONNECTION drops is sent again, marked late; a refused one (HTTP 400) is not
    class _FlakyTG(FakeTelegram):
        def __init__(self):
            FakeTelegram.__init__(self)
            self.fail = []

        def send(self, chat_id, text):
            if self.fail:
                raise self.fail.pop(0)
            FakeTelegram.send(self, chat_id, text)
    _ftg = _FlakyTG()
    _rclk = {"t": 1792800000.0}
    _rph = Phone({"chat_id": 5}, _ftg, ledger=Ledger(results=tempfile.mkdtemp()), now_fn=lambda: _rclk["t"])
    _ftg.fail = [urllib.error.URLError("_ssl.c:1064: The handshake operation timed out")]
    _rph.say(Html("🟢 <b>STATE CHANGED</b>: DOWN -> TRADING"))
    _q1 = len(_rph._resend)
    _rph.resend_tick()                                      # not due yet: nothing sent
    _n_early = len(_ftg.sent)
    for _x in _rph._resend:
        _x["next"] = 0.0
    _ftg.fail = [ConnectionResetError(10054, "forcibly closed")]
    _rph.resend_tick()                                      # still down: kept for later
    _kept = len(_rph._resend)
    for _x in _rph._resend:
        _x["next"] = 0.0
    _rclk["t"] += 120
    _rph.resend_tick()
    _late = P(_ftg.sent[-1][1]) if _ftg.sent else ""
    ck(_q1 == 1 and _n_early == 0 and _kept == 1 and not _rph._resend and len(_ftg.sent) == 1
       and _late.startswith("⏱ Sent late -- from ") and "STATE CHANGED: DOWN -> TRADING" in _late,
       "RESEND: an alert the connection dropped waits, is tried again while the connection is down, and goes "
       "once it is back, marked late: %r" % _late[:80])
    _ftg.fail = [urllib.error.HTTPError("u", 400, "Bad Request", None, None)]
    _rph.say("plain words")
    _rclk["t"] += 10 * RESEND_FOR_S
    _ftg.fail = [urllib.error.URLError("timed out")]
    _rph.say("old news")
    for _x in _rph._resend:
        _x["next"] = 0.0
    _rclk["t"] += RESEND_FOR_S + 1
    _rph.resend_tick()
    ck(not _rph._resend and len(_ftg.sent) == 1 and net_error(ConnectionResetError()) and not net_error(
        urllib.error.HTTPError("u", 400, "x", None, None)) and net_error(urllib.error.HTTPError("u", 502, "x", None, None)),
       "RESEND: a message Telegram refused (400) is not repeated, and one older than %d min is given up"
       % (RESEND_FOR_S // 60))
    ck(halt_words("halt", "pintake halted: order pin-1 outcome UNKNOWN (status -1)").startswith("stopped itself")
       and halt_words("stop_file", "") .startswith("its stop file") and halt_words("exit", "stop file") == "it exited (stop file)"
       and halt_words("odd", "x" * 300) == ("odd " + "x" * 300)[:140],
       "a logged stop reads in plain words; an unknown one keeps its own text, one line")

    # ---- /speed and /server (2026-10-27: every bot moved to the AWS server in Ohio) ----------------------------------
    # SigV4 against AWS's own published test vectors (the aws-sig-v4 test suite, as kept in awslabs/aws-c-auth:
    # get-vanilla, get-vanilla-query-order-key-case, and post-x-www-form-urlencoded with the body hash signed)
    _ak, _sk, _adt = "AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "20150830T123600Z"
    _sh1, _sg1 = sigv4_sign("GET", "https://example.amazonaws.com/", "us-east-1", "service", _ak, _sk, amz_date=_adt)
    _sh2, _sg2 = sigv4_sign("GET", "https://example.amazonaws.com/?Param2=value2&Param1=value1", "us-east-1", "service",
                            _ak, _sk, amz_date=_adt)
    _sh3, _sg3 = sigv4_sign("POST", "https://example.amazonaws.com/", "us-east-1", "service", _ak, _sk, b"Param1=value1",
                            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": "13"},
                            amz_date=_adt, sign_body=True)
    ck(_sg1 == "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"
       and _sh1["authorization"] == ("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request, "
                                     "SignedHeaders=host;x-amz-date, Signature=" + _sg1)
       and _sg2 == "b97d918cfa904a5beff61c982a1b6f458b799221646efd99d3219ec94cdf2500"
       and _sg3 == "d3875051da38690788ef43de4db0d8f280229d82040bfac253562e56c3f20e0b"
       and _sh3["x-amz-content-sha256"] == "9095672bbd1f56dfc5b65f3e153adc8731a4a654192329106275f4c7b24d0b6e",
       "SigV4 signer (hashlib + hmac, no boto3) matches AWS's published test vectors: get-vanilla, the query sorted by "
       "key, and a signed POST body")
    ck(SERVER_SINCE == "2026-10-27T04:20:52Z" and SERVER_SINCE_EPOCH == 1793074852 and SPEED_HOME_DAYS == 14,
       "the move's moment is one constant (SERVER_SINCE, 00:20:52 ET 10-27); home = the 14 days before it")

    _lg_sv, _aws_sv, _tails_sv = globals()["LOG"], dict(_AWS), dict(_TAILS)
    with tempfile.TemporaryDirectory() as _tds:
        globals()["LOG"] = os.path.join(_tds, "pinphone.log")
        _sv = SERVER_SINCE_EPOCH
        _srvf, _homef = "pinrun-live-20261027T042114Z.jsonl", "pinrun-live-20261018T110121Z.jsonl"

        def _iso(e):
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e))

        def _po(dt, tk, asked, got, ms, f=_homef):
            return {"t": _sv + dt, "tk": tk, "filled": got, "asked": asked, "latency_ms": ms, "file": f,
                    "status": "executed" if got else "canceled"}
        # home (the 14 days before the move): 4 orders, 1 got nothing, 30 of 50 contracts, 40/45/50/70 ms
        # server (from the move on): 3 orders, none empty, 35 of 40 contracts, 12/15/18 ms; the one AT the move is the
        # server's, the one a second before it home's; 15 days back and another bot's log are left out
        _pord = [_po(-15 * 86400, "OLD", 10, 0, 500), _po(-13 * 86400, "H4", 10, 10, 70), _po(-5 * 86400, "H3", 20, 10, 45),
                 _po(-3 * 86400, "H2", 10, 0, 50), _po(-1, "H1", 10, 10, 40),
                 dict(_po(-2, "CMD", 10, 0, 999), file="cmdlive-20260917T000000Z.jsonl"),
                 _po(0, "KXA15M-X", 10, 10, 15, _srvf), _po(120, "KXB15M-X", 10, 5, 12, _srvf),
                 _po(180, "KXC15M-X", 20, 20, 18, _srvf)]

        def _wj(name, rows, mtime):
            p_ = os.path.join(_tds, name)
            with open(p_, "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            os.utime(p_, (mtime, mtime))
            return p_
        # the server log's settled legs: A +20c, B +10c and its hedge -5c (= +$0.25 on the 15 contracts got in A and B);
        # `realised` is the run's running total and must NOT be read; a leg before the move, a market not ordered on
        # the server, and the home log's rows (written before the move) are left out; C is still open
        _srvp = _wj(_srvf, [
            {"kind": "start", "t": _iso(_sv + 22)},
            {"kind": "order", "t": _iso(_sv), "ticker": "KXA15M-X", "filled": 10.0},
            {"kind": "settled", "t": _iso(_sv - 10), "ticker": "KXA15M-X", "pnl_c": 1000.0, "realised": 10.0},
            {"kind": "settled", "t": _iso(_sv + 900), "ticker": "KXA15M-X", "pnl_c": 20.0, "realised": 99.0},
            {"kind": "settled", "t": _iso(_sv + 900), "ticker": "KXB15M-X", "want": "no", "pnl_c": 10.0, "realised": 99.1},
            {"kind": "settled", "t": _iso(_sv + 915), "ticker": "KXB15M-X", "want": "yes", "pnl_c": -5.0, "realised": 99.05},
            {"kind": "settled", "t": _iso(_sv + 930), "ticker": "KXZZZ15M-X", "pnl_c": 500.0}], _sv + 3600)
        _wj(_homef, [{"kind": "settled", "t": _iso(_sv + 5), "ticker": "KXA15M-X", "pnl_c": 777.0}], _sv - 86400)
        # the FX taker: home 2 orders Kalshi took (one empty), a refusal (404) left out; server 1 order at 15 ms.
        # The coin race: one home order; no forecaster log here at all.
        _wj("fxtake-live-orders.jsonl", [
            {"t": _iso(_sv - 2 * 86400) + "", "kind": "placed", "status": 201, "filled": 10.0, "rtt": 0.140,
             "body": {"ticker": "KXGOLD15M-X", "count": "10.00"}},
            {"t": _iso(_sv - 2 * 86400 + 900), "kind": "placed", "status": 201, "filled": 0.0, "rtt": 0.150,
             "body": {"ticker": "KXWTI15M-X", "count": "10.00"}},
            {"t": _iso(_sv - 86400), "kind": "placed", "status": 404, "filled": 0.0, "rtt": 0.142,
             "body": {"ticker": "KXEURUSD15M-X", "count": "10.00"}},
            {"t": _iso(_sv - 86400), "kind": "fill", "ticker": "KXGOLD15M-X", "n": 10.0},
            {"t": _iso(_sv + 600), "kind": "placed", "status": 201, "filled": 10.0, "rtt": 0.015,
             "body": {"ticker": "KXGOLD15M-Y", "count": "10.00"}}], _sv + 600)
        _wj("pinracepenny-live.jsonl", [{"kind": "live_order", "t": _iso(_sv - 86400), "ticker": "KXCRYPTOLEAD15M-X",
                                         "count_asked": 1.0, "filled": 1.0, "status": "executed", "status_code": 201}],
            _sv - 86400)
        _snow = _sv + 3 * 86400                                   # the phone's clock: 3 days after the move
        _TAILS.clear()
        _sd = speed_gather(_tds, _pord, _snow)
        _hs, _ss, _sm, _se = _sd["pin"]["home"], _sd["pin"]["server"], _sd["pin"]["money"], _sd["pin"]["est"]
        ck(_hs["n"] == 4 and _hs["zero"] == 1 and _hs["got"] == 30 and _hs["asked"] == 50
           and abs(_hs["got_share"] - 0.6) < 1e-9 and _hs["med_ms"] == 47.5 and _hs["p90_ms"] == 70
           and _ss["n"] == 3 and _ss["zero"] == 0 and _ss["got"] == 35 and _ss["asked"] == 40
           and abs(_ss["got_share"] - 0.875) < 1e-9 and _ss["med_ms"] == 15 and _ss["p90_ms"] == 18,
           "/speed: home vs server split at SERVER_SINCE (an order AT the move is the server's, one a second before it "
           "home's; 15 days back and another bot's log left out): home 4 orders, 47.5 ms median, 1 empty, 30/50 "
           "contracts; server 3 orders, 15 ms, none empty, 35/40")
        ck(abs(_sm["usd"] - 0.25) < 1e-9 and _sm["contracts"] == 15 and _sm["markets"] == 2 and _sm["open_contracts"] == 20
           and abs(_sm["per"] - 0.25 / 15) < 1e-12,
           "/speed: $ per filled contract on the server = the settled legs' pnl_c (+20c, +10c, a -5c hedge = +$0.25) "
           "over the 15 contracts got in those markets; `realised` (the run's running total), a leg before the move, a "
           "market not ordered there and the home log are left out; the open market's 20 contracts wait")
        ck(abs(_se["d_share"] - 0.275) < 1e-9 and abs(_se["extra"] - 11.0) < 1e-9
           and abs(_se["usd"] - 11.0 * 0.25 / 15) < 1e-9 and abs(_se["per_day"] - _se["usd"] / 3.0) < 1e-9,
           "/speed's $ estimate on the planted case: (87.5% - 60%) x 40 asked on the server = 11 extra contracts, x "
           "$0.25/15 a filled contract = +$0.1833 (+$0.0611 a day over 3 days)")
        _st1 = speed_html(_sd, 1000.0)
        _pt1 = P(_st1)
        ck(_pt1.startswith("⏳ SPEED: too early to tell, 3 orders so far on the server (the bar is 50)")
           and "(87.5% - 60.0%) x 40 asked on the server = +11 extra contracts" in _pt1
           and "x +$0.0167 a filled contract (+$0.25 on 15 contracts in 2 markets settled on the server) = +$0.18 "
               "(+0.02% of the main account's $1,000.00 bank)" in _pt1
           and "extra contracts = (server got/asked - home got/asked) x contracts asked on the server; $ = extra "
               "contracts x the $ made per filled contract on the server" in _pt1
           and "an estimate, not a proof" in _pt1 and "⏳ Too early to tell: 3 orders so far" in _pt1
           and "Median        48 ms  15 ms" in _pt1 and "Got nothing   25.0%     0%" in _pt1,
           "/speed under 50 server orders says 'too early to tell, 3 orders so far', and still shows the formula, worked, "
           "with the bank's %%: %r" % _pt1[:120])
        ck("FX taker: home 50% got something (1 of 2 orders, 145 ms) · server 100% got something (1 of 1 order, 15 ms) "
           "· too few on the server to tell" in _pt1
           and "Forecaster: skipped: no log here (forecaster-live-orders.jsonl)" in _pt1
           and "Coin race: home 100% got something (1 of 1 order) · server: no orders · its log keeps no send time" in _pt1
           and "Ladder: skipped: its bids rest on the book" in _pt1,
           "/speed's other bots: the FX taker home vs server (a 404 refusal left out), a missing log says so, the coin "
           "race has no send time, the ladder is skipped and says why")
        ck(not tg_html_problems(_st1) and fits(_st1) and len(split_html(_st1)) == 1 and "\u2014" not in _pt1,
           "/speed: Telegram-valid, one message, no em-dash")
        _st2 = P(speed_html(_sd, 1000.0, min_orders=3))
        ck(_st2.startswith("⚡ SPEED: 15 ms on the server, was 48 ms at home (median, send to answer)")
           and "Too early" not in _st2 and "About +$0.06 a day at this pace" in _st2,
           "/speed past the bar: the headline is the two medians, and the $ a day shows")
        _st3 = P(speed_html(speed_gather(_tds, [o for o in _pord if o["t"] < _sv], _snow), 1000.0))
        ck(_st3.startswith("⏳ SPEED: too early to tell, no pin orders on the server yet")
           and "Not yet: no pin orders on the server yet." in _st3,
           "/speed with no server orders: too early, and no $ guessed")
        # read once, then only what was added: a second gather reads no byte; a leg appended is picked up
        _off0 = _TAILS[(_srvp, "kind", "settled")]["off"]
        speed_gather(_tds, _pord, _snow)
        _off1 = _TAILS[(_srvp, "kind", "settled")]["off"]
        _sz0 = os.path.getsize(_srvp)
        with open(_srvp, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "settled", "t": _iso(_sv + 1900), "ticker": "KXC15M-X", "pnl_c": 30.0}) + "\n")
        os.utime(_srvp, (_sv + 3700, _sv + 3700))
        _sd4 = speed_gather(_tds, _pord, _snow)
        ck(_off0 == _off1 == _sz0 and _TAILS[(_srvp, "kind", "settled")]["off"] == os.path.getsize(_srvp)
           and abs(_sd4["pin"]["money"]["usd"] - 0.55) < 1e-9 and _sd4["pin"]["money"]["contracts"] == 35,
           "/speed reads each log once, then only the bytes added (a new settled leg: +$0.30 on C's 20 contracts)")
        # through the phone: the paired chat, the Ledger's own orders and bank
        _sL = Ledger(results=_tds)
        _sL.refresh = lambda: False
        _sL.orders = list(_pord)
        _sL.bank = lambda: {"bank": 1000.0, "t": _snow}
        _sclk = {"t": _snow}
        _sph = Phone({"chat_id": 111}, FakeTelegram(), ledger=_sL, now_fn=lambda: _sclk["t"])
        _t0 = time.time()
        _hsp = _sph.handle(111, "/speed")
        ck(P(_hsp).startswith("⏳ SPEED: too early to tell, 3 orders so far") and str(_hsp) == str(speed_html(
            speed_gather(_tds, _pord, _snow, active=_sph.active()), 1000.0)) and _sph.handle(333, "/speed") is None
           and time.time() - _t0 < 2.0,
           "/speed through handle(): the paired chat gets the page in under 2 s; a stranger gets nothing")

        # ---- /server: planted machine, Kalshi, pots and AWS
        _AWS.clear()
        _mach = {"host": "EC2AMAZ-TEST", "ncpu": 2, "cpu": 23.4, "py_cpu": 18.2, "py_n": 14, "py_mem": 1.6e9,
                 "mem_total": 4.0e9, "mem_avail": 1.1e9, "mem_load": 72, "commit": 3.1e9, "commit_limit": 5.2e9,
                 "disk_free": 31.2e9, "disk_total": 53.7e9, "uptime_s": 6120.0, "reboot": False, "reboot_why": None,
                 "sample_s": 0.5, "errs": []}
        _pots = {"pots": {"0": {"value": 1246.86, "open": 12.30, "cash": 1234.56, "why": None, "t": _snow - 600},
                          "1": {"value": 683.54, "open": 0, "cash": 683.54, "why": None, "t": _snow - 600},
                          "2": {"value": None, "open": None, "cash": 129.49, "why": "the last cash read failed",
                                "t": _snow - 600}},
                 "total": None, "t": _snow - 600}
        _sph.machine_fn = lambda: dict(_mach)
        _sph.ping_fn = lambda: {"ms": [4.1, 5.2, 6.3], "dns_ms": 1.2, "ip": "1.2.3.4", "err": None, "t": _snow}
        _sph.pots_fn = lambda: _pots
        _awsq = []

        def _no_imds(method, url, headers=None, body=None, timeout=None):
            _awsq.append((method, url))
            raise urllib.error.URLError("timed out")
        _sph.aws_http = _no_imds
        _sv1 = _sph.handle(111, "/server")
        _pv1 = P(_sv1)
        ck(_pv1.startswith("🖥 SERVER: CPU 23% · memory 72% used · disk 31.2 GB free · Kalshi 4.1 ms")
           and "this machine: EC2AMAZ-TEST" in _pv1 and "CPU now   23% (2 cores, 0.5 s)" in _pv1
           and "  python  18% · 14 processes" in _pv1 and "Memory    2.9 GB of 4.0 GB (72%)" in _pv1
           and "Disk C:   31.2 GB free of 54 GB" in _pv1 and "Up        1 h 42 min" in _pv1
           and "Windows Update: no restart waiting" in _pv1
           and "Kalshi: 4.1 ms to connect (best of 3: 4.1 ms, 5.2 ms, 6.3 ms; name lookup 1.2 ms)" in _pv1
           and "The pin bot's own orders here: median 15 ms send to answer, 0% got nothing (home: 48 ms, 25.0%)" in _pv1,
           "/server's machine section from planted readings: CPU and the python share, memory, disk, uptime, Windows "
           "Update, the time to Kalshi, the pin bot's own order times: %r" % _pv1[:100])
        ck("AWS cost: not connected yet (needs the read-only billing role on the server, see /server help)" in _pv1
           and "Estimate from the price list: about $51.45 a month ($1.69 a day)" in _pv1
           and "Windows t3.medium $0.06 an hour ($43.80), 50 GB disk $4.00, public IPv4 $3.65" in _pv1
           and "budget $120.00 a month" in _pv1 and _awsq == [("PUT", AWS_IMDS + "/latest/api/token")],
           "/server with no metadata service (the call fails): AWS cost says not connected, points to /server help, and "
           "the price-list estimate shows, labelled; one metadata call, nothing else")
        # v-tg-active: a pot is named for the bots running now (this Phone reads this machine's process table)
        _sact = _sph.active()
        _n0, _n2 = funds_short(0, _sact), funds_short(2, _sact)
        ck("Funds: all pots ?" in _pv1 and any(x.split()[:2] == [_n0, "1,246.86"] for x in _pv1.split("\n"))
           and any(x.split()[:2] == [_n2, "?"] for x in _pv1.split("\n"))
           and "⚠️ %s: the last cash read failed; its cash alone $129.49" % _n2 in _pv1,
           "/server's funds from botstats' cache: a pot whose last read failed shows '?' and why, and no total is made up")
        _spl = "\n".join(_server_pots_lines(_pots, _snow, ("pin", "ladder", "fx", "jumpband"))[0])
        ck(any(x.split()[:2] == ["main", "1,246.86"] for x in _spl.split("\n"))
           and any(x.split()[:2] == ["idle", "?"] for x in _spl.split("\n")) and "forecaster" not in _spl
           and funds_short(3, ("pin", "jumpband")) == "jump band" and funds_short(0, ("pin", "race")) == "main+race",
           "/server's pots with the coin race paused and the forecaster stopped: 'main' and 'idle', never a hidden bot's "
           "name; subaccount 3 is the jump band's")
        _sph.handle(111, "/server")
        ck(len(_awsq) == 1, "/server: a missing metadata service is remembered for 5 minutes (no second call)")
        ck(not tg_html_problems(_sv1) and fits(_sv1) and len(split_html(_sv1)) == 1 and "\u2014" not in _pv1,
           "/server: Telegram-valid, one message, no em-dash")
        # the role exists: IMDSv2 token -> role -> keys -> identity; then Budgets and Cost Explorer, signed
        _AWS.clear()
        _awsq[:] = []

        def _aws_world(method, url, headers=None, body=None, timeout=None):
            _awsq.append((method, url, dict(headers or {}), body))
            if url == AWS_IMDS + "/latest/api/token":
                return (200, b"TOKEN123") if method == "PUT" and headers.get(
                    "X-aws-ec2-metadata-token-ttl-seconds") else (400, b"")
            if url.startswith(AWS_IMDS) and (headers or {}).get("X-aws-ec2-metadata-token") != "TOKEN123":
                return 401, b""
            if url == AWS_IMDS + "/latest/meta-data/iam/security-credentials/":
                return 200, b"kals-server-billing"
            if url == AWS_IMDS + "/latest/meta-data/iam/security-credentials/kals-server-billing":
                return 200, json.dumps({"Code": "Success", "AccessKeyId": "ASIATEST", "SecretAccessKey": "SECRETTEST",
                                        "Token": "SESSIONTOKEN", "Expiration": _iso(_snow + 6 * 3600)}).encode()
            if url == AWS_IMDS + "/latest/dynamic/instance-identity/document":
                return 200, json.dumps({"accountId": "001634075101", "region": "us-east-2"}).encode()
            tgt = (headers or {}).get("x-amz-target")
            if url == "https://budgets.amazonaws.com/" and tgt == "AWSBudgetServiceGateway.DescribeBudgets":
                return 200, json.dumps({"Budgets": [{"BudgetName": "kals-monthly", "BudgetType": "COST",
                                                     "TimeUnit": "MONTHLY",
                                                     "BudgetLimit": {"Amount": "120.0", "Unit": "USD"},
                                                     "CalculatedSpend": {"ActualSpend": {"Amount": "1.234", "Unit": "USD"},
                                                                         "ForecastedSpend": {"Amount": "8.4",
                                                                                             "Unit": "USD"}},
                                                     "LastUpdatedTime": _snow - 7200}]}).encode()
            if url == "https://ce.us-east-1.amazonaws.com/" and tgt == "AWSInsightsIndexService.GetCostAndUsage":
                yd = time.strftime("%Y-%m-%d", time.gmtime(_snow - 86400))
                return 200, json.dumps({"ResultsByTime": [
                    {"TimePeriod": {"Start": yd}, "Estimated": True, "Groups": [
                        {"Keys": ["Amazon Elastic Compute Cloud - Compute"],
                         "Metrics": {"UnblendedCost": {"Amount": "1.00", "Unit": "USD"}}},
                        {"Keys": ["EC2 - Other"], "Metrics": {"UnblendedCost": {"Amount": "0.20", "Unit": "USD"}}}]}]}
                ).encode()
            return 404, b"{}"
        _sph.aws_http = _aws_world
        _pots2 = {"pots": {"0": {"value": 2000.0, "open": 0, "cash": 2000.0, "why": None, "t": _snow - 60}},
                  "total": 2000.0, "t": _snow - 60}
        _sph.pots_fn = lambda: _pots2
        _mach["reboot"], _mach["reboot_why"] = True, "Windows Update"
        _pv2 = P(_sph.handle(111, "/server"))
        _bq = [x for x in _awsq if x[1] == "https://budgets.amazonaws.com/"]
        _bh = _bq[0][2] if _bq else {}
        _rh, _rsig = sigv4_sign("POST", "https://budgets.amazonaws.com/", "us-east-1", "budgets", "ASIATEST",
                                "SECRETTEST", _bq[0][3] if _bq else b"",
                                {"Content-Type": "application/x-amz-json-1.1",
                                 "X-Amz-Target": "AWSBudgetServiceGateway.DescribeBudgets"}, "SESSIONTOKEN",
                                amz_date=_bh.get("x-amz-date"))
        ck(len(_bq) == 1 and _bh.get("authorization") == _rh["authorization"] and _bh.get("x-amz-security-token")
           == "SESSIONTOKEN" and json.loads(_bq[0][3].decode()) == {"AccountId": "001634075101", "MaxResults": 20}
           and "SignedHeaders=content-type;host;x-amz-date;x-amz-security-token;x-amz-target," in _bh["authorization"],
           "/server's Budgets call: the role's short-lived keys from IMDSv2, the account from the instance's identity, "
           "the request signed (SigV4, the session token signed too)")
        ck("This month so far: $1.23 of the $120.00 budget (1%) = 0.06% of all pots" in _pv2
           and "AWS's forecast for October: $8.40 = 0.42% of all pots" in _pv2
           and "Cost Explorer: this month $1.20 = 0.06% of all pots · yesterday (UTC) $1.20" in _pv2
           and "By service: EC2 instance $1.00, EC2 other (disk, data) $0.20" in _pv2
           and "⚠️ Windows Update waits for a restart" in _pv2 and "a restart is waiting (Windows Update)" in _pv2
           and "not connected" not in _pv2,
           "/server connected: this month's spend against the budget, AWS's forecast, Cost Explorer by service, each "
           "with its share of all pots; a waiting Windows restart is said loudly")
        _n0 = len(_awsq)
        _sclk["t"] = _snow + 1800
        _sph.handle(111, "/server")
        _n1 = len(_awsq)
        _sclk["t"] = _snow + 3601
        _sph.handle(111, "/server")
        _new = [x[1] for x in _awsq[_n1:]]
        ck(_n1 == _n0 and _new == ["https://budgets.amazonaws.com/"],
           "/server's AWS reads are cached: nothing again inside an hour; after an hour the free Budgets read only "
           "(Cost Explorer, $0.01 a read, waits 6 hours); the role's keys are kept until they near expiry")
        _hl = P(_sph.handle(111, "/server help"))
        ck(_hl.startswith("🖥 /server help: connect the AWS cost") and "IAM → Roles → Create role" in _hl
           and "Use case: EC2" in _hl and "Role name kals-server-billing" in _hl
           and "EC2 → Instances → tick kals-bot → Actions → Security → Modify IAM role → pick kals-server-billing" in _hl
           and '"budgets:ViewBudget","ce:GetCostAndUsage"' in _hl and not tg_html_problems(SERVER_HELP)
           and fits(SERVER_HELP) and "\u2014" not in _hl,
           "/server help: the console steps (the read-only policy, the role for EC2, attaching it to kals-bot)")
        ck("/speed" in HELP_TEXT and "/server" in HELP_TEXT and "<code>/server help</code>" in HELP_TEXT
           and not tg_html_problems(HELP_TEXT) and fits(HELP_TEXT),
           "/speed and /server are in /help")
        ck(_tgc().kind_of("/speed") is None and _tgc().kind_of("/server") is None,
           "/speed and /server send words only (no chart; /help says so)")
    globals()["LOG"] = _lg_sv
    _AWS.clear()
    _AWS.update(_aws_sv)
    _TAILS.clear()
    _TAILS.update(_tails_sv)
    # the real readers on this machine: Windows answers, nothing raises, and a waiting restart is a yes / no / unknown
    _mr = machine_read(0.1)
    _rb = reboot_pending()
    ck(_mr["mem_total"] and _mr["disk_free"] and _mr["uptime_s"] and _mr["cpu"] is not None and 0 <= _mr["cpu"] <= 100
       and _mr["py_n"] and _mr["py_n"] >= 1 and _mr["mem_load"] is not None and _rb[0] in (True, False, None),
       "machine_read on this machine (ctypes, no psutil): CPU %.0f%%, memory %s%%, %s free on C:, %d python "
       "process(es), up %s; errors: %s" % (_mr["cpu"] or -1, _mr["mem_load"], _gb(_mr["disk_free"]), _mr["py_n"] or 0,
                                          _span_words(_mr["uptime_s"] or 0), _mr["errs"] or "none"))

    # 2026-10-30: the clock-change days. Every 'today', 'yesterday', 'since midnight' and 7-day window on the phone
    # starts at et_day_start / bs.day_start, which read the ET offset at NOON until today: on 2026-11-01 (clocks back
    # at 2 AM) that put midnight at 05:00Z, an hour late (the 12-1 AM hour booked to Oct 31, the 8 AM brief an hour
    # late); on 2026-03-08 an hour early.
    import botstats as _bsd
    _starts = {"2026-10-29": (2026, 10, 29, 4), "2026-11-01": (2026, 11, 1, 4), "2026-11-02": (2026, 11, 2, 5),
               "2026-03-08": (2026, 3, 8, 5), "2026-03-09": (2026, 3, 9, 4)}
    ck(all(et_day_start(k) == _bsd.day_start(k) == calendar.timegm(v + (0, 0)) for k, v in _starts.items()),
       "et_day_start and bs.day_start across both clock changes: Oct 29 04:00Z, Nov 1 04:00Z, Nov 2 05:00Z, Mar 8 "
       "05:00Z, Mar 9 04:00Z")
    ck(all(et_day(et_day_start(k)) == k and et_day(et_day_start(k) - 1) == day_minus(k, 1) == _bsd.shift_day(k, -1)
           for k in _starts)
       and {k: (et_day_start(day_minus(k, -1)) - et_day_start(k)) / 3600.0 for k in _starts}
       == {"2026-10-29": 24.0, "2026-11-01": 25.0, "2026-11-02": 24.0, "2026-03-08": 23.0, "2026-03-09": 24.0},
       "day_minus and shift_day agree with the clock across both changes and the days join up: Nov 1 is 25 hours, "
       "Mar 8 is 23, the rest 24")
    print("pinphone selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    if "--preview" in sys.argv:
        # what each command would send, AS THE PHONE SHOWS IT (tags dropped); --html prints the markup instead.
        # NOTE: /bots /pin /race /funds read Kalshi (GET only, botstats' getter) and the process table.
        raw = "--html" in sys.argv

        def show(x):
            return str(x) if raw or not getattr(x, "is_html", False) else html_to_plain(x)
        ph = Phone({"chat_id": 0}, FakeTelegram())
        ph.ledger.refresh()
        cprint(show(ph.text_status()))
        cprint("\n--- /market ---\n" + show(ph.text_market()))
        cprint("\n--- /hedges ---\n" + show(ph.text_hedges()))
        t0 = time.time()
        n = python_procs()
        cprint("\n(process table: %s in %.1f s -- the daemon reads it on a background thread)"
               % ("%d python processes" % len(n) if n is not None else "COULD NOT BE READ", time.time() - t0))
        for name, fn in (("/stats", ph.text_stats), ("/race", ph.text_race), ("/racestats", ph.text_racestats),
                         ("/bots", ph.text_bots), ("/pin", lambda: ph.text_bot("pin")),
                         ("/forecaster", lambda: ph.text_bot("forecaster")), ("/ladder", lambda: ph.text_bot("ladder")),
                         ("/weather", lambda: ph.text_bot("weather")), ("/fx", lambda: ph.text_bot("fx")),
                         ("/funds", ph.text_funds), ("/speed", ph.text_speed), ("/server", ph.text_server)):
            t0 = time.time()
            out = fn()
            parts = split_html(out) if getattr(out, "is_html", False) else split_text(out)
            cprint("\n--- %s (%d chars, %d message(s), %.1f s) ---\n%s" % (
                name, len(out), len(parts), time.time() - t0, show(out)))
        return 0
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as e:
        print("no usable %s (%s). See the docstring for setup." % (CONFIG, e))
        return 2
    if not cfg.get("token"):
        print("%s has no token" % CONFIG)
        return 2
    ph = Phone(cfg, Telegram(cfg["token"]))
    ph.charts_on = cfg.get("charts", True) is not False         # "charts": false in telegram.json = words only
    ph.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
