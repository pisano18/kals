"""/help /? -- the command list; and the answer to a message the phone does not know ("I did not understand that.").

v-tg-rebuild step 9 (2026-10-30): pinphone.HELP_TEXT / help_text(active) and the last line of Phone.handle as a command
module, byte-identical (golden shadow: research/golden/shadow.py for /help /? /HELP, research/golden/shadow_more.py for
the unknown-command answer, unknown text and empty text).

HOW /help IS BUILT. One template, then the two substitutions help_text() always made:
  - the template is generated: a heading per section (phone.command.SECTIONS, in order), under it each command's
    help_line sorted by its `order`, the one-bot section holding the placeholder {bot_lines}; then the two footer lines;
  - {bot_lines} = the registry's Bot.help lines (bots.HELP_BOT_LINES) of the ACTIVE bots only (v-tg-active);
  - {funds_split} (inside /funds' help_line) = ' (main bot and X apart)' while the main account is shared.
Where the (section, order, help_line) rows come from:
  - step 9 (now): HELP_ENTRIES below, a static copy of CONTRACT.md's order table (the other lanes' modules are not
    merged yet), so /help does not depend on which command modules happen to be imported;
  - step 10: the router calls use_commands(phone.command.commands()) once after discover(): the rows are then read off
    the declared Commands themselves (Command.section / order / help_line). test_help_cmd.py checks that every Command
    declared today carries exactly its HELP_ENTRIES row, so the switch changes no byte.
"""
import bots
from phone.command import SECTIONS, Command, declare
from phone.html import Html

TOP = "📱 <b>Commands</b>"
HEADS = {
    "money": "💰 <b>Money</b>",
    "one_bot": "🤖 <b>One bot</b> <i>(the bots running now; a paused or stopped one comes back here when it runs again)</i>",
    "now": "🔎 <b>Right now</b>",
    "server": "🖥 <b>Server</b> (every bot runs on an AWS server in Ohio since 12:20 AM ET Oct 27)",
    "controls": "🎛 <b>Controls</b>",
}
FOOT = ("📈 Most commands send a chart right after the words (not /open, /help, /speed, /server or the controls).",
        "<i>Alerts come by themselves: state changes, every losing close (with its % of the bank), low disk (under 8 GB, "
        "again under 6 GB), and yesterday's summary for every bot at 8 AM ET. Long details sit behind a tap on the quoted "
        "block.</i>")
BOT_LINES = "{bot_lines}"           # the one-bot section's body: the active bots' Bot.help lines
FUNDS_SPLIT = "{funds_split}"       # inside /funds' help_line: ' (main bot and X apart)' while the main account is shared

# (section, order, help_line) of every listed command: CONTRACT.md's order table, the lines verbatim from HELP_TEXT.
# The one-bot pages are not here: their lines are the registry's (bots.HELP_BOT_LINES).
HELP_ENTRIES = (
    ("money", 10, "/today · /yesterday — every bot's money that day: % of all pots, and a table with each bot's % of its "
                  "bank"),
    ("money", 20, "/days — the last 7 days, every bot: each day's % of all pots, each bot's week"),
    ("money", 30, "/stats — the whole record by window: money, win rate vs break-even, losses, timing"),
    ("money", 40, "/funds (or /bank, /accounts) — the money in every account and subaccount: cash, open bets, total, "
                  "what runs there, bet size now, each account's last 7 days{funds_split}, and the grand total"),
    ("money", 50, "/bots — every bot running now: money today / 7 days / all time, each pot's cash, and the total of all "
                  "of them"),
    ("now", 10, "/status — is it trading, with the evidence"),
    ("now", 20, "/open — open bets in every pot"),
    ("now", 30, "/fills — the pin bot's orders today: filled, price paid, seconds out; then every other bot's fills, "
                "each named"),
    ("now", 40, "/market — how active sellers are, and which bot bought what at each of the last closes"),
    ("now", 50, "/losses — every bot's losing markets: which bot, $ and % of its pot"),
    ("now", 60, "/hedges — the pin bot's insurance, whether it was needed, % of the bank"),
    ("now", 70, "/brief — the daily briefing: money, what changed, what it did, the market, what to watch"),
    ("now", 80, "/bars — the September tests against their pre-registered bars (all finished; kept for the record)"),
    ("now", 90, "/features — what each bot does and the settings it runs with now (read from boot_all.ps1), and the "
                "rules they run under"),
    ("server", 10, "/speed: did the move win orders the laptop lost: the pin bot's order times and empty orders, home "
                   "against server, and what speed added in $ (an estimate); a line for the other bots"),
    ("server", 20, "/server: the server's CPU, memory, disk, uptime and Windows restarts, the time to Kalshi, every pot's "
                   "money, and the AWS bill this month (<code>/server help</code>: connect the AWS cost)"),
    ("controls", 10, "/pause — no new bets, wait for open ones, then stop"),
    ("controls", 20, "/start — trade again"),
    ("controls", 30, "<code>/stop yes</code> — stop right now"),
    ("controls", 40, "/mute · /unmute — alerts off / on"),
    ("controls", 50, "/update — load the newest phone code (self-tests it first; back within ~10 min)"),
)

UNKNOWN_HEAD = "I did not understand that.\n\n"


def entries(commands=None):
    """[(section, order, help_line)]: HELP_ENTRIES (commands None), or read off declared Commands (step 10): every Command
    with a section other than one_bot and a help_line."""
    if commands is None:
        return list(HELP_ENTRIES)
    return [(c.section, c.order, c.help_line) for c in commands
            if c.section is not None and c.section != "one_bot" and c.help_line]


def template(rows=None):
    """/help's template (pinphone._HELP_TPL): TOP, each section's heading over its lines sorted by order (the one-bot
    section's body is {bot_lines}), the footer; blocks a blank line apart."""
    rows = HELP_ENTRIES if rows is None else rows
    blocks = [TOP]
    for sec in SECTIONS:
        if sec == "one_bot":
            body = [BOT_LINES]
        else:
            body = [r[2] for r in sorted((r for r in rows if r[0] == sec), key=lambda r: r[1])]
        blocks.append("\n".join([HEADS[sec]] + body))
    blocks += list(FOOT)
    return "\n\n".join(blocks)


_TPL = [template()]


def use_commands(commands):
    """Step 10: build /help from the declared Commands (phone.command.commands() after discover()) from now on."""
    _TPL[0] = template(entries(commands))


def help_html(active, pp):
    """/help with the one-bot commands of the ACTIVE bots only (None = every bot: the whole roster). pinphone.help_text,
    verbatim: `pp` is the old pinphone module (main_sharers, BOT_WORD)."""
    act = set(active) if active is not None else None
    lines = [w for b, w in bots.HELP_BOT_LINES if act is None or b in act]
    return Html(_TPL[0].replace(BOT_LINES, "\n".join(lines)).replace(
        FUNDS_SPLIT, (" (main bot and %s apart)" % " and ".join(pp.BOT_WORD[x] for x in pp.main_sharers(act)[1:]))
        if pp.main_sharers(act) else ""))


def load(ctx):
    return ctx.active()


def render(active, ctx):
    return help_html(active, ctx.pp)


def unknown_reply(ctx):
    """The answer to any message no command claims (the router's last line; Phone.handle's last line): the words, then
    /help."""
    return Html(UNKNOWN_HEAD + help_html(ctx.active(), ctx.pp))


COMMAND = declare(Command(
    names=("/help", "/?"), section=None, chart=None, load=load, render=render))
