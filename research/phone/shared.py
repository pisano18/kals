r"""phone/shared.py -- the phone's helpers module: every name the command modules read as ctx.pp, and the old pinphone
names other files import (research/bars.py, results/research_2026-10/scripts/phone_alert.py, the golden harness).

v-tg-rebuild step 11 (2026-10-30): pinphone.py was split three ways. research/pinphone.py is now the LAUNCHER (it
re-exports these names), research/phone/app.py the RUNTIME (class Phone: the poll loop, the ticks, the hello), and this
file is everything else pinphone's module level held: the constants and paths (RESULTS, LOG, HEARTBEAT, UPDATE_FLAG,
BOOT_ALL, LADDER_PY, VERSIONS_MD ...), the helpers not moved into a command module yet (the coin race's, /stats' money
windows, /features' boot_all reader, /brief's and /bars' layouts, the process-table names over botdata.procs), and
re-exports of what already moved (phone.html, phone.log, phone.transport, phone.render.botcards, the funds / speed /
server modules, phone.alerts). Nothing here answers a message: phone/router.py does.

A test or the golden harness that patches one of these names patches it HERE (phone.shared.LOG, .UPDATE_FLAG,
.BOOT_ALL, .machine_read ...): the command modules look them up on ctx.pp at call time, and log() asks this module's
LOG on every line (phone.log.set_path).

Step 13 moves the race helpers (bars.py imports them) and the rest into botdata / their commands; step 14 shrinks this
to the external contract.
"""
import html as _html
import json
import os
import re
import sys
import time
import traceback
import urllib.error                     # (urllib.error: the old self-test's planted HTTP errors)

# 2026-10-26 (operator: "free up memory"): numpy's OpenBLAS -- pulled in by matplotlib when a chart is drawn -- commits a
# work buffer for each of the 16 CPU threads: measured +614 MB private on the first chart, +131 MB with one thread. The
# charts are small 2-D plots; one thread draws them the same. Must be set before numpy is first imported.
for _blas in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_blas, "1")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # research\ (pinphone.HERE)
if HERE not in sys.path:
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
LOSSES_SHOWN = 30               # /losses lists this many (operator 10-26: "a bit more than just the last ten")
CHART_QUEUE = 2                 # pictures waiting to be drawn; one more is dropped (logged), never waited for
CHART_MAX_BYTES = 9_500_000     # Telegram takes photos up to 10 MB

import bots as _bots                                                 # noqa: E402
# v-tg-rebuild step 5 (2026-10-30): every per-bot table below is READ FROM THE REGISTRY (research/bots/<name>.py, one file
# a bot); a bot that moves, starts or stops is edited there, never here. bots/tests/test_registry.py and the golden
# harness (research/golden, 'data/tables') hold each table to the values it had when it was written out here (8a9c5e1).

# /funds (/bank /accounts): WHAT RUNS IN EACH KALSHI ACCOUNT (FUNDS_WHAT, FUNDS_BOTS, FUNDS_IDLE, FUNDS_POOL_NAME,
# FUNDS_SIZE_BOTS, funds_what). v-tg-rebuild step 9 (2026-10-30, lane D4): moved verbatim to
# research/phone/commands/funds/read.py with the rest of /funds; re-exported here (the very same objects).
from phone.commands.funds.read import (FUNDS_WHAT, FUNDS_BOTS, FUNDS_IDLE, FUNDS_POOL_NAME,  # noqa: E402,F401
                                       FUNDS_SIZE_BOTS, _pot_whats, funds_what)


# v-tg-rebuild step 9 (lane D2, 2026-10-30): moved verbatim to research/phone/render/botcards.py; re-exported
from phone.render.botcards import BOT_WORD, DESK_BOT, main_sharers, main_shared   # noqa: E402,F401


def _tgc():
    """research/tgcharts.py, imported on first use (it imports matplotlib only when it draws)."""
    import tgcharts
    return tgcharts


# v-tg-rebuild step 6 (2026-10-30): the log line, the HTML layout helpers and the message splitters live in
# research/phone/ (log.py, html.py), moved there verbatim; every name is re-exported here (bars.py, the golden harness and
# the self-test use them as pinphone.<name>). log() writes to THIS module's LOG, read at each call: a test that patches
# pinphone.LOG still moves every line (phone.log.set_path below).
from phone import log as _plog                                       # noqa: E402
from phone.log import log, cprint                                    # noqa: E402,F401
from phone.html import (MAX_LEN, Html, esc, html_to_plain, _MONEY_SIGN, _MONEY_BIG, norm_money, b_, i_,   # noqa: E402,F401
                        table, pre, details, elines, _EIGHTHS, hbar, _SPARK, spark, _TG_TAGS, _TG_STYLE, _TG_TOK,
                        tg_html_problems, _TAG, _open_after, _closers, _openers, _cut_long_line, split_html, split_text)
_plog.set_path(lambda: LOG)


# v-tg-rebuild step 10 (2026-10-30): usd / dollars are botdata.fmt's (the very code that stood here)
from botdata.fmt import usd, dollars                                 # noqa: E402,F401


# v-tg-rebuild step 9 (lane D2, 2026-10-30): moved verbatim to research/phone/render/botcards.py; re-exported
from phone.render.botcards import dot   # noqa: E402,F401


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


# v-tg-rebuild step 9 (lane D2, 2026-10-30): moved verbatim to research/phone/render/botcards.py; re-exported
from phone.render.botcards import ret   # noqa: E402,F401


# v-tg-rebuild step 6 (2026-10-30): Telegram, photo_body, net_error and FakeTelegram live in research/phone/transport.py
# (moved verbatim); re-exported here (phone_alert.py uses pinphone.Telegram).
from phone.transport import Telegram, photo_body, net_error, FakeTelegram   # noqa: E402,F401
from phone import alerts as _alerts                                  # noqa: E402


SUPPLY_STALE_D = 3.0        # /market: an opportunity trend measured longer ago than this is left out (2026-10-23)

# v-tg-rebuild step 9 (lane D2, 2026-10-30): moved verbatim to research/phone/render/botcards.py; re-exported
from phone.render.botcards import HALT_WORDS, halt_words   # noqa: E402,F401


RESEND_FOR_S = 15 * 60      # 2026-10-23: a send the connection dropped is tried again for this long ...
RESEND_GAP_S = 30           # ... this far apart
RESEND_KEEP = 20            # at most this many wait (the newest)
PHOTO_TRIES = (5, 20)       # a chart the connection dropped: sent again after these many seconds


# ===========================================================================
# the bot
# ===========================================================================
# /help (v-tg-rebuild step 10, 2026-10-30): built by research/phone/commands/help_cmd.py from the declared commands (the
# router calls help_cmd.use_commands after discover()): the same sections, order and lines HELP_TEXT always had; the
# one-bot lines are the registry's (bots.HELP_BOT_LINES), only the ACTIVE bots' (v-tg-active).
HELP_BOT_LINES = _bots.HELP_BOT_LINES


def help_text(active=None):
    """/help with the one-bot commands of the ACTIVE bots only (None = every bot: the whole roster)."""
    from phone.commands import help_cmd
    return help_cmd.help_html(active, sys.modules[__name__])


HELP_TEXT = help_text()                  # the whole roster (the self-test's reference); /help sends help_text(active)

# the controls' replies: research/phone/commands/controls.py (re-exported, the very same objects)
from phone.commands.controls import CONTROL_REPLY, STOP_ASK            # noqa: E402,F401
UP_TEXT = Html("📱 <b>Pin Bot phone link is up.</b> /status for the state, /help for commands.")


def state_dot(state):
    return {"TRADING": "🟢", "PAUSING": "🟡", "STALE": "🟡", "BLIND": "🟠", "PAUSED": "⏸", "STOPPED": "⏹",
            "BRAKE": "🔴", "DOWN": "🔴"}.get(state, "⚪")


# the alerts (their layouts, fmt_or_plain, the disk rule) live in research/phone/alerts.py since v-tg-rebuild step 10
from phone.alerts import (alert_recorder_text, alert_recorder_back_text, disk_alert_html,   # noqa: E402,F401
                          alert_daily_text, fmt_or_plain, disk_alert, DISK_WARN_GB, DISK_STOP_GB, DISK_REARM_GB,
                          DISK_HARD_STOP_GB, DISK_GB_PER_DAY)


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


# v-tg-rebuild step 10: _f and _cnt are botdata.fmt's, day_minus / days_between botdata.clock's (the same code)
from botdata.fmt import _f, cnt as _cnt                             # noqa: E402,F401
from botdata.clock import day_minus, days_between                  # noqa: E402,F401


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


def sides_of(ledger):
    """{ticker: entry side} from the bot's own records. A hedge record
    names the side the hedge BOUGHT, so the entry is the other one --
    that is the authority, sent or not. Markets with no hedge record
    take the ledger's `want` (pindesk's own reading, count rule first,
    the log breaking an equal count). (Phone._sides; Ctx.sides is the same)"""
    out = {}
    for g in ledger.hedges:
        if g.get("tk") and g.get("side") in ("yes", "no"):
            out[g["tk"]] = "no" if g["side"] == "yes" else "yes"
    for x in ledger.settled:
        if x.get("tk") and x["tk"] not in out and x.get("want") in ("yes", "no"):
            out[x["tk"]] = x["want"]
    return out


def chart_markets(led):
    """The main account's markets for a picture (ChartCtx.markets): markets_from over Kalshi's ledger file with the
    entry sides of the ledger snapshot `led` (phone.charts.ctx.phone_markets, the same reads in the same order)."""
    sides = sides_of(led)
    return markets_from(raw_ledger(os.path.join(led.results, pinday.LEDGER_NAME)), sides)


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


# ---- the process table: botdata/procs.py (v-tg-rebuild step 10) ----------------------------------------------------
# ONE reader for the phone and botstats: Windows itself in milliseconds (ctypes), PowerShell WMI only when that fails
# (10-35 s), a TTL cache and a background refresher. These names keep pinphone's shape: [(pid, command line)] or None
# (None, never [] -- an empty list would read as 'nothing running', the one thing a failed read must never say).
from botdata import procs as _bdprocs                                # noqa: E402
PROC_REFRESH_S = _bdprocs.TABLE_TTL_S     # the background refresher's period


def list_python_procs(timeout=30):
    """[(pid, command line)] for every python.exe, read now (native first, WMI fallback), or None."""
    return _bdprocs.pid_cmd(_bdprocs.read_all(timeout))


def python_procs(max_age_s=None):
    """The cached process table, or None when it cannot be read. Fresh enough (the refresher keeps it under
    PROC_REFRESH_S old) it is returned at once; stale or empty, one synchronous read is made (natively: milliseconds)."""
    return _bdprocs.pid_cmd(_bdprocs.table(max_age_s))


def cached_python_procs():
    """The table the refresher last read while it is fresh, else None (= 'could not be read'). Never asks
    Windows itself, so a page that can live with 'unknown' (/racestats) never holds the poll thread."""
    return _bdprocs.pid_cmd(_bdprocs.cached())


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
    """fleet_roles()' scripts in the order they are tried, and {script: Bot} of the main account's other live bot (the coin
    race). v-tg-rebuild step 5: the desk bot's and the race's scripts are the registry's Bot.script (every bot with a pot
    in subaccount 0); the desk bot's two older copies and the command-line paper arm are no registry bot's."""
    other = {b.script: b for b in _bots.bots_on("0") if b.name != DESK_BOT}
    return ("pinrun_afternoon.py", "pinrun913.py", _bots.get(DESK_BOT).script, "cmdarm.py") + tuple(other), other


def fleet_roles(procs):
    """(Was pinphone.fleet; renamed in v-tg-rebuild step 10 -- botdata.status.fleet is the bots' states.)
    What is running, by role: the live up/down bot, the penny race bot,
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


# ===========================================================================
# /bots /pin /forecaster /ladder, and the money windows under /race: the bot cards (every bs_* renderer and its
# helpers). v-tg-rebuild step 9 (lane D2, 2026-10-30): moved verbatim to research/phone/render/botcards.py (the
# operator's notes on them went along); every name is re-exported here.
# ===========================================================================
from phone.render.botcards import (                       # noqa: E402,F401
    BOT_CMDS, BOT_CMD_OF, PAGE_FOOTER, BS_WINDOWS, BS_LABEL, _bs, _pot_words, _nof, _cash, _ago, bs_window_line,
    _roi_tail, _short, bs_running_lines, bs_setup_lines, bs_money_lines, bs_open_lines, bs_cash_line, bs_last_lines,
    bs_activity_lines, bs_bot_text, bs_errors_line, _POT_WORD, _active_of, _shown_by, _shown_name, _shown_parts,
    shown_cash, _shown_errors, earlier_lines, bs_all_text, BS_SHORT, _wlabel, money_dot, run_words, state_icon,
    bs_running_html, main_words, main_bot_of, _mkt_short, buys_words, bs_money_table, money_legend, bs_days_table,
    _money_detail, bs_money_html, LADDER_GOAL_PCT, _unit_of, _goal_of, bs_avg_day_line, bs_avg30_line, bots_avg_table,
    bs_headline, bots_window_table, _day_long, nice_coin, bs_bot_html, _short_html, all_bots_avg_before, _bot_parked,
    bs_all_html)


# ===========================================================================
# /funds (/bank /accounts) -- every Kalshi account's money on one screen.
#
# v-tg-rebuild step 9 (2026-10-30, lane D4): MOVED VERBATIM to research/phone/commands/funds/ -- read.py (funds_read,
# funds_sizes, the past days: funds_settled / funds_hist / funds_days, _FUNDS_HIST) and page.py (funds_text,
# _funds_page, funds_short, funds_idle ...). Every name is re-exported here, the very same objects: Phone.text_funds,
# the self-test and the golden harness use them as pinphone.<name> unchanged.
# ===========================================================================
from phone.commands.funds.read import (FUNDS_PATHS, FUNDS_DEADLINE_S, FUNDS_POS_PAGES,  # noqa: E402,F401
                                       FUNDS_FALLBACK_POOLS, _fnum, _fint, _usd2, _pool_name, funds_read,
                                       funds_sizes, FUNDS_DAYS, FUNDS_SHOW_DAYS, FUNDS_HIST_TTL_S, FUNDS_HIST_PAGES,
                                       FUNDS_HIST_DEADLINE_S, FUNDS_HIST_PATH, FUNDS_BOOKS, funds_books, _FUNDS_HIST,
                                       funds_book, funds_settled, funds_hist, funds_days)
from phone.commands.funds.page import (_funds_hist_lines, funds_text, FUNDS_SHORT, funds_short,  # noqa: E402,F401
                                       funds_idle, _funds_day_label, _funds_days_html, _funds_page)


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
# v-tg-rebuild step 9 (2026-10-30, lane D5): MOVED VERBATIM to research/phone/commands/ -- speed.py (SERVER_SINCE,
# speed_gather, speed_html, tail_rows / _TAILS and the short number words), server/machine.py (machine_read,
# kalshi_ping), server/aws.py (the AWS_* price list, sigv4_sign, _aws_http, aws_cost, aws_estimate; the only command
# file with urllib) and server/page.py (SERVER_HELP, server_html). Every name is re-exported here, the very same
# objects: Phone.text_speed / text_server, the self-test and the golden seams (pinphone.machine_read, kalshi_ping)
# use them as pinphone.<name> unchanged.
# ===========================================================================
from phone.commands.speed import (SERVER_SINCE, SERVER_SINCE_EPOCH, SPEED_HOME_DAYS,  # noqa: E402,F401
                                  SPEED_MIN_ORDERS, SPEED_MIN_OTHER, SPEED_OTHERS, SPEED_SKIPPED, SPEED_LABEL,
                                  _et_at, _span_words, _gb, _ms, _usd4, _pct0, _TAILS, tail_rows, _median, _rank,
                                  _speed_win, pin_speed_orders, speed_stats, _other_order, speed_pin_money,
                                  speed_estimate, speed_gather, _speed_other_line, speed_html)
from phone.commands.server.aws import (AWS_REGION, AWS_AZ, AWS_INSTANCE_TYPE, AWS_INSTANCE_ID,  # noqa: E402,F401
                                       AWS_INSTANCE_NAME, AWS_ELASTIC_IP, AWS_ACCOUNT_ID, AWS_DISK_GB,
                                       AWS_EC2_HOURLY, AWS_IPV4_HOURLY, AWS_DISK_MONTH, AWS_HOURS_MONTH,
                                       AWS_BUDGET_USD, AWS_BILLED_FROM, AWS_BILLED_FROM_EPOCH, AWS_ROLE_NAME,
                                       AWS_IMDS, AWS_IMDS_TIMEOUT_S, AWS_API_TIMEOUT_S, AWS_CREDS_SKEW_S,
                                       AWS_NOT_CONNECTED_TTL_S, AWS_BUDGET_TTL_S, AWS_CE_TTL_S, AWS_ERR_TTL_S,
                                       AWS_BUDGETS_HOST, AWS_CE_HOST, AWS_SERVICE_SHORT, sigv4_sign, _aws_http, _AWS,
                                       aws_role_creds, _aws_call, _aws_budget_rows, _aws_ce_rows, _aws_cached,
                                       aws_cost, aws_estimate)
from phone.commands.server.machine import (KALSHI_HOST, KALSHI_PING_TTL_S, KALSHI_PING_TRIES,  # noqa: E402,F401
                                           _W32, _w32, _ft, _python_handles, REBOOT_KEYS, reboot_pending,
                                           machine_read, _PING, kalshi_connect, kalshi_ping)
from phone.commands.server.page import (SERVER_WARN_CPU, SERVER_WARN_MEM, SERVER_WARN_DISK_GB,  # noqa: E402,F401
                                        SERVER_HELP, _server_pots_lines, _server_aws_lines, server_html)
