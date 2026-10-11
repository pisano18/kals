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
  /losses     losing closes        /hedges    insurance and whether it was needed
  /stats      the whole record by window: money, win rate vs break-even, losses, timing
  /bots       every bot and its pot (subaccount): running, money by window, cash, the all-bots total
  /pin  /forecaster (/fc)  /ladder  /weather (/wx)   one bot in full: running or not and why, version,
              settings, money today / yesterday / 7 days / month / all time, worst and best,
              open bets, cash, last markets, what its log did today (research/botstats.py)
  /race       the coin race penny bot now, its last 10 races, and its money by window
  /racestats  the coin race record, and the paper arms on the same races
  /bars       every running test against its pre-registered bar: the numbers
              so far, days into the window, PASS / KILL / EXTEND / TOO EARLY
  /funds (/bank /accounts)   every Kalshi account's money: cash in each pool, open bets,
              total, what runs there, each bot's bet size now, its last 7 ET days of gains
              and losses from Kalshi's settlements, and the grand total
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

    python research/pinphone.py --selftest
    python research/pinphone.py --preview        # print what /status would send
    python research/pinphone.py                  # run (needs C:\kals\telegram.json)
"""
import json
import os
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindesk                                                       # noqa: E402
from pindesk import (Ledger, et_day, et_day_start, et_str, et_now_str, coin, close_et, money, pct,   # noqa: E402
                     story_loss, story_hedge, story_day, status_of, hours_up_et_day)
import pinflat                                                       # noqa: E402

CONFIG = r"C:\kals\telegram.json"
RESULTS = pindesk.RESULTS
HEARTBEAT = os.path.join(RESULTS, "pinphone.heartbeat")
LOG = os.path.join(RESULTS, "pinphone.log")
MAX_LEN = 3900

# /funds (/bank /accounts): WHAT RUNS IN EACH KALSHI ACCOUNT -- edit here when a bot moves, starts or stops.
# Key = subaccount number (0 = the main account). A value is the words, or {cash pool: words} when one
# subaccount does different things in different pools. A subaccount Kalshi lists that is not here
# shows as "unknown". (2026-10-11, the operator: "Add a way in telegram to see the bankroll or fund
# sizes of all sub accounts.")
FUNDS_WHAT = {
    0: "main bot (pin) + coin race",
    1: "penny ladder",
    2: "forecaster",
    3: {0: "weather dip-seller (stopped)", 2: "empty"},
    4: "coin-race reward test (stopped)",
}
FUNDS_POOL_NAME = {0: "weather pool", 2: "crypto pool"}     # Kalshi's exchange_index; others say "pool N"
# whose bet size /funds shows under each account (read from that bot's own log, see funds_sizes)
FUNDS_SIZE_BOTS = {0: ("pin", "race"), 1: ("ladder",), 2: ("forecaster",)}


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
    line = "%s  %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


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
        for chunk in split_text(text, MAX_LEN):
            self._call("sendMessage", {"chat_id": chat_id, "text": chunk})


class FakeTelegram:
    """For the self-test: a queue of incoming messages and a list of sent ones."""
    def __init__(self):
        self.incoming = []
        self.sent = []
        self.n = 0

    def push(self, chat_id, text):
        self.n += 1
        self.incoming.append({"update_id": self.n, "message": {"chat": {"id": chat_id}, "text": text}})

    def get_updates(self, offset, timeout=25):
        out = [u for u in self.incoming if u["update_id"] >= (offset or 0)]
        return out

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


# ===========================================================================
# the bot
# ===========================================================================
HELP_TEXT = """Commands:
/status - is it trading, with the evidence
/today /yesterday /days - money and % return
/open - open bets
/fills - every order today: filled, price paid, seconds out
/brief - the daily briefing: money, what changed, what it did, the market, what to watch
/market - how active sellers are
/losses - losing closes
/hedges - insurance and whether it was needed
/stats - the whole record by window: money, win rate vs break-even, losses, timing
/bots - every bot: running or not, money today / 7 days / all time, each pot's cash, and the total of all of them
/pin - the pin bot: running or not and why, version, settings, money today / yesterday / 7 days / month / all time, worst, open bets, cash, last markets
/race - the coin race penny bot right now, its last 10 races, and its money by window
/racestats - the coin race record, and the paper arms on the same races
/forecaster (or /fc) - the forecaster (subaccount 2), the same detail as /pin
/ladder - the penny ladder (subaccount 1), the same detail as /pin
/weather (or /wx) - the weather dip-seller (subaccount 3, weather cash pool), the same detail as /pin
/bars - every running test against its pre-registered bar: numbers so far, days into the window, PASS / KILL / EXTEND / TOO EARLY
/funds (or /bank, /accounts) - the money in every account and subaccount: cash, open bets, total, what runs there, bet size now, each account's gain or loss on each of the last 7 days (main bot and coin race apart), and the grand total
/pause - no new bets, wait for open ones, then stop
/start - trade again
/stop yes - stop right now
/mute /unmute - alerts off / on
Alerts come by themselves: state changes, every losing close, low disk (under 8 GB, again under 6 GB), and yesterday's summary at 8 AM ET."""


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
        L.append("Losses %d: %s, avg %s, worst %s (%s %s); %s."
                 % (st["losses"], money(st["lost_total"]), money(st["lost_total"] / st["losses"]),
                    money(st["largest_loss"]), _leg_name(wm["tk"]), _md(wm["day"]), h))
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
# Entries that are another bot's: the coin race, the clean-room forecaster and
# penny ladder, and the boot entries that name them. botstats.version_of uses
# the same words, and the self-test fails if the two pick different versions.
_NOT_PIN_RE = re.compile(r"coin.?race|penny|cleanroom|clean-room|bettor|forecaster|ladder_live|dipsell|dip.?sell",
                         re.I)


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
        if v[0].lower().startswith("v-race") or _NOT_PIN_RE.search(v[0] + " " + v[3]):
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


def fleet(procs):
    """What is running, by role: the live up/down bot, the penny race bot,
    the paper arms (by --arm-name / log name) and the paper race arms."""
    out = {"live": None, "penny": None, "arms": [], "race_arms": [], "unknown": procs is None}
    for pid, cl in (procs or []):
        low = cl.lower()
        script = next((s for s in ("pinrun_afternoon.py", "pinrun913.py", "pinrun.py",
                                   "cmdarm.py", "pinracearm.py") if s in low), None)
        if not script:
            continue
        toks = cl.split()
        is_live = "--live" in toks
        if script == "pinracearm.py":
            if is_live and "--paper-live" not in toks:
                out["penny"] = (pid, cl)
            else:
                out["race_arms"].append(_log_name(argv_opt(cl, "--log"), "pinracearm-") or "race-arm")
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
    """The penny bot's own view of itself, from its log: the last start
    record (rails), whether the stop rail has fired SINCE that start, the
    legs it holds on races not yet scored, and the dollars out."""
    start = halt = None
    fills, done, staked = {}, set(), None
    for r in recs:
        k = r.get("kind")
        if k == "start":
            start, halt = r, None
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
    return {"start": start, "halt": halt, "open": open_, "pending": pending, "staked": staked}


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
# 1) and the weather dip-seller (subaccount 3, 2026-10-04; its cash sits in
# Kalshi's weather pool, exchange_index 0) are separate pots and are added
# up only in /bots.
# ===========================================================================
BOT_CMDS = {"/pin": "pin", "/forecaster": "forecaster", "/fc": "forecaster", "/ladder": "ladder",
            "/weather": "weather", "/wx": "weather"}
BOT_CMD_OF = {"pin": "/pin", "race": "/race", "forecaster": "/fc", "ladder": "/ladder", "weather": "/weather"}
BS_WINDOWS = ("today", "yesterday", "last_7_days", "this_month", "all_time")
BS_LABEL = {"today": "Today", "yesterday": "Yesterday", "last_7_days": "Last 7 days",
            "this_month": "This month", "all_time": "All time"}


def _bs():
    """botstats, imported late: a broken edit there costs these commands, never the phone."""
    import botstats
    return botstats


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


def bs_window_line(w, label, unit="market", fmt=None, whose="its pot"):
    """'Today: +$1.62 on $59.54 put in (+2.7%) = +0.15% of its pot ($1,100.00); 2 markets, 2 won, 0 lost'.
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


def _short(w, fmt):
    """'+$2.63 (+0.24%)' -- the money and, when its pot is known, its share of the pot."""
    if w is None:
        return "?"
    if not w["markets"]:
        return "nothing yet"
    p = w.get("pot_pct")
    return fmt(w["money"]) + ((" (%s)" % _bs().pot_pct_txt(p)) if p is not None else "")


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
    note = bs._pot_note(m)                  # what '% of its pot' means, or why it is not shown
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
                                   "%s, %s (%d won, %d lost)" % (fmt(d["money"]), _nof(d["markets"], unit),
                                                                 d["won"], d["lost"])))
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
    return "Cash: %s -- %s." % (_cash(bal["dollars"]), bal["note"])


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
        L.append("  %s: %s %s" % (h["t_et"], h["what"], h["why"]))
    return L


def bs_bot_text(b, now_et):
    """One bot, everything botstats knows, for /pin /forecaster /ladder."""
    unit = "leg" if b["name"] == "race" else "market"
    L = ["%s -- %s. %s" % (b["label"].upper(), b["what"], now_et)]
    pot = _bs().SUB_NAME.get(str(b["subaccount"]), "subaccount %s" % b["subaccount"])
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


def bs_all_text(a):
    """/bots: the ALL-BOTS total with each bot's share, every pot's cash, and one line a bot."""
    bs = _bs()
    fmt = bs.usd
    L = ["ALL BOTS -- %s" % a["as_of_et"],
         "Money from Kalshi, every pot; a market counts on the ET day it closed.",
         "The % after '=' or in brackets = share of the pot when the window began (its cash + open bets; "
         "pin and race share the main account). All time = share of the money put in."]
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
            pp = t.get("by_bot_pot_pct") or {}
            L.append("  " + " | ".join(
                "%s %s" % (b, (fmt(v) + ((" (%s)" % bs.pot_pct_txt(pp[b])) if pp.get(b) is not None else ""))
                           if t["by_bot_markets"].get(b) else "none")
                for b, v in t["by_bot"].items() if b != "other" or t["by_bot_markets"].get(b)))
    miss = a["total"]["all_time"]["missing"]
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
            parts = ", ".join("%s %s" % (b, fmt(v)) for b, v in d["by_bot"].items() if abs(v) > 0.004)
            L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                                   "%s, %s%s" % (fmt(d["money"]), _nof(d["markets"], "market"),
                                                 (" (%s)" % parts) if parts else "")))
    elif not miss:
        L.append("Nothing settled yet in any pot.")
    bal = a["balances"]
    L.append("Cash: main account %s (pin + race share it), forecaster %s, ladder %s, weather %s -- all pots %s."
             % (_cash(bal["main"]), _cash(bal["forecaster"]), _cash(bal["ladder"]), _cash(bal.get("weather")),
                _cash(bal["all"])))
    L.append("The main page (/today /days /stats, the desktop) counts pin + race only. The forecaster, "
             "the ladder and the weather dip-seller are separate pots, added up only here.")
    # 2026-10-01: the operator saw about -$119 in Kalshi's app while every bot was up. Kalshi's apps do not
    # support subaccounts (API-only, docs.kalshi.com/getting_started/subaccounts), so the cash moved from the
    # main account into the two bot pots shows there as money gone.
    if all(bal.get(k) is not None for k in ("forecaster", "ladder", "weather")):
        L.append("Kalshi's own app shows the MAIN account only. The %s sitting in the forecaster, ladder and "
                 "weather pots was moved out of it, so Kalshi's screens read that much lower than all pots -- "
                 "not a loss." % _cash(bal["forecaster"] + bal["ladder"] + bal["weather"]))
    L.append("")
    for name in bs.BOTS:
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
            b["label"].upper(), bs.SUB_NAME.get(str(b["subaccount"]), "?"), run,
            r["version"] or "no version entry", mon, op, BOT_CMD_OF[name]))
    ot = a["other"]
    if ot.get("ok") and ot.get("all_time") and ot["all_time"]["markets"]:
        w = ot["all_time"]
        L.append("NOT ANY BOT'S (main account): all time %s on %s; worst %s %s (%s)." % (
            fmt(w["money"]), _nof(w["markets"], "market"), fmt(w["worst"]["money"]), w["worst"]["what"],
            bs.day_label(w["worst"]["day"])))
    L += bs_errors_line(a["errors"])
    L += bs.pot_check_lines(a.get("pot_check"))     # a pot Kalshi's own books do not explain
    if all(a["total"][k].get("pot_pct") is None for k in BS_WINDOWS if a["total"][k]["markets"]) \
            and any(a["total"][k]["markets"] for k in BS_WINDOWS):
        why = next((a["total"][k].get("pot_why") for k in BS_WINDOWS if a["total"][k].get("pot_why")), None)
        if why:
            L.append("%% of the pots: not shown -- %s." % why)
    return "\n".join(L)


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


def funds_sizes(results=RESULTS):
    """{subaccount: [words]}: each bot's bet size NOW, from its own log -- no Kalshi read. A log with no
    size record leaves that bot out; a log that cannot be read says so. Never a guess."""
    import glob
    bs = _bs()

    def when(r):
        e = bs._epoch((r or {}).get("t"))
        return bs.et_clock(e) if e else "?"

    def pin():
        logs = sorted(glob.glob(os.path.join(results, "pinrun-live-*.jsonl")))
        r = bs.last_record(logs[-1], ("autosize",)) if logs else None
        if r and _fnum(r.get("new")) is not None:
            m = re.search(r"bank \$([\d.]+)", str(r.get("why") or ""))
            return "main bot %g contracts a bet (sized %s%s)" % (
                _fnum(r["new"]), when(r), (" on a %s bank" % _usd2(m.group(1))) if m else "")
        sz = read_json(os.path.join(results, "pinrun-live-size.json")) or {}
        if _fnum(sz.get("size")) is None:
            return None
        return "main bot %g contracts a bet (sized %s%s)" % (
            _fnum(sz["size"]), when({"t": sz.get("at")}),
            (" on a %s bank" % _usd2(sz["bank"])) if _fnum(sz.get("bank")) is not None else "")

    def race():
        r = bs.last_record(os.path.join(results, "pinracepenny-live.jsonl"), ("start",))
        lr = (r or {}).get("live_rails") or {}
        if _fnum(lr.get("max_contracts")) is None:
            return None
        return "coin race %g contracts a bet%s (set at its start %s)" % (
            _fnum(lr["max_contracts"]),
            (", at most %s in play" % _usd2(lr["max_stake"]).replace(".00", "")) if _fnum(lr.get("max_stake")) else "",
            when(r))

    def ladder():
        r = bs.last_record(os.path.join(results, "ladder-live-orders.jsonl"), ("rescale", "start"))
        size = _fnum(((r or {}).get("rails") or {}).get("size"))
        if size is None:
            size = _fnum((r or {}).get("new"))
        if size is None:
            return None
        pot = _fnum(r.get("pot") if r.get("pot") is not None else r.get("sub_balance"))
        return "ladder %g-contract bids (sized %s%s)" % (size, when(r), (" on a %s pot" % _usd2(pot)) if pot else "")

    def forecaster():
        r = bs.last_record(os.path.join(results, "forecaster-live-orders.jsonl"), ("rescale", "start"))
        rails = (r or {}).get("rails") or {}
        sc = _fnum(rails.get("scale"))
        if sc is None:
            return None
        pot = _fnum(r.get("pot") if r.get("pot") is not None else r.get("sub_balance"))
        return "forecaster %g%% of the paper bot's size%s (sized %s%s)" % (
            round(100.0 * sc, 2), (", up to %s contracts a side" % rails["per_side"]) if rails.get("per_side") else "",
            when(r), (" on a %s pot" % _usd2(pot)) if pot else "")

    readers = {"pin": pin, "race": race, "ladder": ladder, "forecaster": forecaster}
    out = {}
    for n, bots in FUNDS_SIZE_BOTS.items():
        for b in bots:
            try:
                w = readers[b]()
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
# ---------------------------------------------------------------------------------------------------------
FUNDS_DAYS = 7
FUNDS_SHOW_DAYS = (7, 5, 3, 0)          # day lines listed, most first, until the page fits one message
FUNDS_HIST_TTL_S = 60
FUNDS_HIST_PAGES = 60                   # 12,000 settlements in FUNDS_DAYS days, one account: stops loudly
FUNDS_HIST_DEADLINE_S = 15.0            # the whole settlement read, every account; short: loss alerts wait on it
FUNDS_HIST_PATH = "/portfolio/settlements"                    # GET only
FUNDS_BOOKS = (("bot", "main bot"), ("race", "race"), ("other", "other"))
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


def funds_days(res, today, days=FUNDS_DAYS):
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
    for s in res.get("rows") or []:
        tk = s.get("ticker")
        if not isinstance(tk, str) or not tk:
            continue                        # not a market: a transfer or anything else is never a gain here
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
    return out


def _funds_hist_lines(n, res, today, show, held):
    """The past-days lines under one account. `show` = how many day lines to list (the total always
    counts all FUNDS_DAYS); `held` = what the account holds now, or None when that was not read whole."""
    bs = _bs()
    if res is None:
        return ["  past %d ET days: not read" % FUNDS_DAYS]
    h = funds_days(res, today)
    unread = [x["day"] for x in h["days"] if not x["read"]]
    if len(unread) == FUNDS_DAYS:
        return ["  past %d ET days: COULD NOT READ (%s)" % (FUNDS_DAYS, res.get("err"))]

    def cw(c, extra=""):
        return "%s (%d of %d lost%s)" % (bs.usd(c["money"]), c["lost"], c["n"], extra)

    def money_w(x, other_names=""):
        if n != 0 or not x["all"]["n"]:
            return cw(x["all"])
        return "%s = %s" % (bs.usd(x["all"]["money"]), " + ".join(
            "%s %s" % (w, cw(x[k], other_names if k == "other" else "")) for k, w in FUNDS_BOOKS if x[k]["n"]))

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


def funds_text(f, sizes, now, hist=None):
    """/funds' words from funds_read() and funds_sizes(). Anything unread is named, and a total that
    leaves something out says 'at least' and what. With `hist` (funds_settled), every account also
    carries its last FUNDS_DAYS ET days; the day lines shrink through FUNDS_SHOW_DAYS until the page fits
    one Telegram message (MAX_LEN), and say so."""
    if hist is None:
        return _funds_page(f, sizes, now, None, 0)
    for show in FUNDS_SHOW_DAYS:
        t = _funds_page(f, sizes, now, hist, show)
        if len(t) <= MAX_LEN:
            break
    return t


def _funds_page(f, sizes, now, hist, show):
    today = pinday.et_day_of_epoch(now)
    L = ["MONEY IN EVERY ACCOUNT -- %s, read from Kalshi now." % _bs().et_clock(now)]
    if f["list_err"]:
        L.append("Kalshi's list of subaccounts could not be read (%s), so only the ones known here (%s) are "
                 "shown -- any other is missing." % (f["list_err"], ", ".join(str(n) for n in sorted(FUNDS_WHAT))))
    cash_t = open_t = 0.0
    missing = []
    pool_t = {}                                   # pool -> cash over every account; None once one is unread
    for n in sorted(f["subs"]):
        s = f["subs"][n]
        what = FUNDS_WHAT.get(n, "unknown (not in FUNDS_WHAT in pinphone.py)")
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
        L.append("")
        L.append("%s -- %s: %s%s" % (name, what, "" if whole else "at least ", _usd2(cash + (s["open"] or 0.0))))
        L.append("  cash: %s; open bets: %s" % (", ".join(parts) if parts else "$0.00", ow))
        if sizes.get(n):
            L.append("  bet size now: " + "; ".join(sizes[n]))
        if hist is not None:
            L.extend(_funds_hist_lines(n, hist.get(n), today, show, (cash + s["open"]) if whole else None))
    L.append("")
    if not f["subs"]:
        L.append("NO ACCOUNT COULD BE READ. Nothing above is a zero -- it is unknown.")
    elif missing:
        L.append("ALL ACCOUNTS: at least %s (cash %s + open bets %s) -- leaves out what could not be read: %s."
                 % (_usd2(cash_t + open_t), _usd2(cash_t), _usd2(open_t), ", ".join(missing)))
    else:
        L.append("ALL ACCOUNTS: %s = cash %s + open bets %s." % (_usd2(cash_t + open_t), _usd2(cash_t), _usd2(open_t)))
    kc = f.get("kalshi_cash")
    if kc and f["subs"] and None not in pool_t.values():
        ours = sum(v for v in pool_t.values())
        if all(abs(pool_t.get(ix, 0.0) - kc.get(ix, 0.0)) <= 0.02 for ix in set(kc) | set(pool_t)):
            L.append("The cash adds up to Kalshi's own whole-account figure (%s)." % _usd2(sum(kc.values())))
        else:
            L.append("CHECK: Kalshi's own whole-account cash is %s, but the accounts above add to %s -- an "
                     "account is missing from Kalshi's list, or a bet filled between reads (send /funds again)."
                     % (_usd2(sum(kc.values())), _usd2(ours)))
    L.append("Open bets count at what they cost. Bet sizes are from each bot's own log.")
    if hist is not None:
        L.append("Past days, newest first, from Kalshi's settlement records: what each market paid minus its "
                 "cost and fees, on the ET day it closed; (2 of 28 lost) = 2 of the 28 markets settled lost "
                 "money. Deposits and transfers are not gains. Liquidity rewards are paid outside these "
                 "records and are not counted.")
    return "\n".join(L)


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

    # ---- helpers ----
    @property
    def chat_id(self):
        return self.cfg.get("chat_id")

    def save_cfg(self):
        try:
            with open(self.cfg_path, "w", encoding="utf-8") as fh:
                json.dump(self.cfg, fh, indent=2)
        except OSError as e:
            log("could not save config: %s" % e)

    def say(self, text, chat_id=None):
        """Send, and LOG WHAT WAS SENT. 2026-09-23: the operator got a
        RECORDER SILENT alert and the log held no trace of it -- only
        failures were logged -- so there was no way to audit whether an
        alert had fired, which is the whole point of having alerts."""
        cid = chat_id or self.chat_id
        flat = " | ".join(str(text).splitlines())
        if cid is None:
            log("NOT SENT (no paired chat): %s" % flat[:200])
            return
        try:
            self.tg.send(cid, text)
            log("SENT: %s" % flat[:300])
        except Exception as e:                            # noqa: BLE001
            log("send failed: %s -- text was: %s" % (e, flat[:200]))

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

    # ---- command texts ----
    def text_status(self):
        h = self.health_fn()
        state, hl, det, _c = status_of(h)
        b = self.ledger.bank()
        dep = self.ledger.deposited()
        lines = [hl, det, ""]
        if b:
            lines.append("Bank $%.2f, size %g contracts" % (b["bank"], b.get("size") or 0))
            if dep:
                lines.append("%s on $%.2f put in" % (pct((b["bank"] - dep) / dep), dep))
        today = et_day(self.now())
        lines.append("")
        lines.append(self.summary_line(self.ledger.settled_on(today), today, "TODAY"))
        opn = pinflat.positions(self.ledger.newest_rows) if h["alive"] else {}
        if opn:
            lines.append("")
            lines.append("Open: " + ", ".join("%s %s closes %s" % (coin(t), "x%g" % self.ledger.contracts_for(t), close_et(t)) for t in opn))
        wd = h.get("watchdog_s")
        rec = "both writing" if (h.get("kalshi_ok") and h.get("feeds_ok")) else "CHECK RECORDERS"
        lines.append("")
        lines.append("Watchdog %s. Recorders %s. Disk %.1f GB." % (
            ("ok, %ds ago" % wd) if wd is not None and wd < 120 else "NOT RUNNING", rec, h.get("disk_gb") or 0))
        return "\n".join(lines)

    def text_day(self, day, label):
        return self.summary_line(self.ledger.settled_on(day), day, label)

    def text_days(self):
        out = []
        for d in list(reversed(self.ledger.days()))[:7]:
            s = Ledger.summary(self.ledger.settled_on(d))
            b0 = self.ledger.bank_at(et_day_start(d))
            out.append("%s  %s (%s)  %d closes, %d lost" % (d[5:], money(s["net"]), pct((s["net"] / b0) if b0 else None), s["closes"], s["lost"]))
        # 2026-10-01, the operator: "/days doesn't show any recent negative days on this version". A deploy day
        # mixes two versions (09-30: +$30.45 before v-topup, -$18.77 after, shown as one +$11.68), so the running
        # version gets its own line -- Kalshi's books, main account, markets closing after its deploy.
        ver = live_version(self.versions_path)
        if ver:
            try:
                vs = [m for m in self._markets().values() if m["close"] is not None and m["close"] >= ver[1]]
            except Exception:                                    # noqa: BLE001
                vs = None
            if vs is not None:
                out.append("")
                out.append("SINCE %s (%s ET): %s, %d markets, %d lost" % (
                    ver[0], et_str(ver[1], "%m/%d %I:%M %p"), money(sum(m["pnl"] for m in vs)), len(vs),
                    sum(1 for m in vs if m["pnl"] < -0.004)))
        out.append("")
        out.append(self.summary_line(self.ledger.settled, None, "ALL TIME"))
        return "\n".join(out)

    def text_open(self):
        h = self.health_fn()
        opn = pinflat.positions(self.ledger.newest_rows) if h["alive"] else {}
        if not opn:
            return "No open bets."
        out = []
        for t in opn:
            c = pinflat.close_epoch(t)
            out.append("%s x%g, closes %s (%d s)" % (coin(t), self.ledger.contracts_for(t), close_et(t), max(0, (c or 0) - self.now())))
        return "\n".join(out)

    def text_fills(self, day=None):
        """Every order the bot sent today: what filled, what we paid, how late.

        The operator, 2026-09-18: *"Make a telegram command to see the filled,
        paid, and seconds out info for the days bets."* He had asked where to
        see a fill price and the only answer was a column in the desktop app.

        ZERO-FILL ORDERS ARE SHOWN, not hidden. An order that filled nothing is
        a race we lost, and it is about one in five -- a list that quietly drops
        them would report a fill rate of 100%.
        """
        day = day or et_day(self.now())
        rows = [o for o in self.ledger.orders
                if o.get("t") and et_day(o["t"]) == day]
        if not rows:
            return "No orders today (%s)." % day
        rows.sort(key=lambda o: o["t"])
        out = ["ORDERS TODAY (%s)" % day, ""]
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
            out.append("%s  %-5s %s  %s  %s" % (
                et_str(o["t"]),
                coin(o.get("tk") or ""),
                ("%g/%g" % (f, a)) if a else ("%g" % f),
                ("%.1fc" % (100 * float(px))) if px else "  -  ",
                ("%ss out" % tau) if tau is not None else "(oil)"))
        out.append("")
        out.append("%d orders: %d filled, %d lost the race. Asked %g contracts, "
                   "got %g (%s)." % (len(rows), int(nf), zero, asked, got,
                                     pct(got / asked, False) if asked else "-"))
        return "\n".join(out)

    def text_brief(self):
        """The daily briefing, from pinbrief -- the same words the CLI prints.

        NOT rebuilt here. The operator asked for one daily summary, and a
        phone copy that assembles its own version is a second summary to keep
        honest; the app and this bot have already disagreed about one day.
        """
        try:
            import pinbrief
            return pinbrief.text(pinbrief.brief(ledger=self.ledger))
        except Exception as e:                                  # noqa: BLE001
            return ("Could not build today's briefing: %s\n"
                    "Everything else still works -- try /today again, or "
                    "/days for the plain numbers." % str(e)[:160])

    def text_market(self):
        act = self.ledger.activity()
        out = ["SELLERS: %s" % act["level"]]
        if act["recent"] is not None:
            out.append("Last 4 quarter-hours: someone selling the winning side on %.0f%% of looks (quiet < %.0f%%, typical %.0f%%, busy > %.0f%%)."
                       % (100 * act["recent"], 100 * act["p25"], 100 * act["median"], 100 * act["p75"]))
        out.append("")
        for c in list(reversed(self.ledger.closes))[:8]:
            share = Ledger.offer_share(c)
            out.append("%s  sellers %s  %s" % (et_str(c["close"]) if c["close"] else "?", pct(share, False) if share is not None else "-", self.ledger.reason(c)))
        today = et_day(self.now())
        fs = Ledger.fill_stats(self.ledger.fills_on(today))
        out.append("")
        out.append("Today: %d orders, %d filled, %d lost races; asked %g got %g (%s)." % (
            fs["orders"], fs["fills"], fs["zero"], fs["asked"], fs["contracts"], pct(fs["share"], False) if fs["share"] is not None else "-"))
        # IS THE OPPORTUNITY GOING AWAY. Same lines the desktop shows, from
        # the same function, so the phone and the app cannot drift apart.
        # Read from health() rather than recomputed: it is already there.
        try:
            h = self.health_fn()
            sl = h.get("supply_lines") or []
            if sl:
                out.append("")
                out.append("IS THE OPPORTUNITY GOING AWAY?")
                out += sl
                age = h.get("supply_age_d")
                if age is not None:
                    out.append("(measured up to %.1f days ago)" % age)
        except Exception:                                   # noqa: BLE001
            pass
        return "\n".join(out)

    def text_losses(self):
        rows = self.ledger.losing_closes()[:10]
        if not rows:
            return "No losing closes."
        s = Ledger.summary(self.ledger.settled)
        out = ["%d losing closes of %d all time (%.1f in 100)." % (s["lost"], s["closes"], s["loss_rate"]), ""]
        for close, net, legs in rows:
            out.append("%s  %s  %s" % (et_str(close, "%m/%d %I:%M %p") if close else "?", money(net), ", ".join(sorted({coin(l["tk"]) for l in legs}))))
        return "\n".join(out)

    def text_hedges(self):
        ho = list(reversed(self.ledger.hedge_outcomes()))[:8]
        if not ho:
            return "No hedges yet."
        out = []
        for g in ho:
            out.append("%s %s belief %.0f%%: %s  bet %s, hedge %s, net %s" % (
                et_str(g["t"], "%m/%d %I:%M %p") if g["t"] else "?", coin(g["tk"]), 100 * float(g.get("belief") or 0),
                g["verdict"] or "pending", money(g["bet_pnl"]) if g["bet_pnl"] is not None else "-",
                money(g["hedge_pnl"]) if g["hedge_pnl"] is not None else "-", money(g["net"]) if g["net"] is not None else "-"))
        return "\n".join(out)

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
        return "%d races since %s: %d won, %d tie, %d lost, %s (/race)." % (
            t["races"], et_str(self.race30_epoch, "%m/%d"), t["won"], t["tie"], t["lost"], money(t["net"]))

    def text_stats(self):
        """Everything he would show a friend, by window. Money is Kalshi's;
        the seconds-left split is from the bots' order records; the bank,
        size and day count are the live bot's own files."""
        now = self.now()
        today = et_day(now)
        res = self.ledger.results
        mk = self._markets()
        ms = [m for m in mk.values() if m["day"] >= FIRST_LIVE_DAY]
        if not ms:
            return "No Kalshi settlements on file since %s (results/kalshi_ledger.json)." % FIRST_LIVE_DAY
        taus = first_entries(self.ledger.orders)
        fl = fleet(self.procs_fn())
        ver = live_version(self.versions_path)
        # "every bot" was true until the forecaster and the ladder got their
        # own subaccounts; kalshi_ledger.json is the main account only now.
        L = ["STATS  %s ET. Money = Kalshi's books, main account (pin + coin race; forecaster and "
             "ladder: /bots); days are ET." % et_str(now, "%a %m/%d %I:%M %p")]
        pid = fl["live"][0] if fl["live"] else None
        live_cl = fl["live"][1] if fl["live"] else ""
        if pid:
            where = ", pid %d" % pid
        elif fl["unknown"]:
            where = " (process table could not be read)"
        else:
            where = ", NOT in the process table"
        if ver:
            L.append("LIVE %s since %s ET%s%s." % (ver[0], et_str(ver[1], "%m/%d %I:%M %p"),
                                                  " (about)" if ver[2] else "", where))
        else:
            L.append("LIVE version: no readable header in VERSIONS.md%s." % where)
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
                s += ", bank $%.2f read %s" % (_f(sz["bank"]), et_str(pindesk.parse_t(sz.get("at")) or now))
            parts.append(s)
        if parts:
            L.append(". ".join(parts) + ".")
        if hwm.get("hwm") and sz.get("bank") is not None:
            h = _f(hwm["hwm"])
            line = (1.0 - MAX_DRAWDOWN) * h
            L.append("Halt if the bank falls to $%.2f (%.0f%% under its high of $%.2f): $%.2f of room."
                     % (line, 100.0 * MAX_DRAWDOWN, h, _f(sz["bank"]) - line))
        cap = argv_opt(live_cl, "--loss-cap")
        if dl.get("day") == today and dl.get("realised") is not None:
            L.append("Today by the bot's own count: %s%s." % (
                money(_f(dl["realised"])), (" (stops at $-%s for the day)" % cap) if cap else ""))
        if fl["unknown"]:
            L.append("Paper arms: the process table could not be read.")
        else:
            arms = [a[4:] if a.startswith("arm-") else a for a in fl["arms"]]
            L.append("Paper arms: %d%s + %d race arms%s." % (
                len(arms), (" (" + ", ".join(arms) + ")") if arms else "",
                len(fl["race_arms"]), (" (" + ", ".join(fl["race_arms"]) + ")") if fl["race_arms"] else ""))
        L.append("Coin race: " + self._race_summary(races_from(mk)))
        wins = [("LIFETIME (since %s)" % _md(FIRST_LIVE_DAY), ms, days_between(FIRST_LIVE_DAY, today)),
                ("LAST 7 DAYS", [m for m in ms if m["day"] >= day_minus(today, 6)], 7),
                ("LAST 3 DAYS", [m for m in ms if m["day"] >= day_minus(today, 2)], 3),
                ("TODAY (%s)" % _md(today), [m for m in ms if m["day"] == today], 1)]
        if ver:
            wins.append(("SINCE %s (%s ET)" % (ver[0], et_str(ver[1], "%m/%d %I:%M %p")),
                         [m for m in ms if m["close"] is not None and m["close"] >= ver[1]], None))
        for i, (title, sub, nd) in enumerate(wins):
            L.append("")
            L.append(stats_block(title, window_stats(sub, taus), nd))
            if i == 0:
                by = {}
                for m in sub:
                    by[m["book"]] = by.get(m["book"], 0.0) + m["pnl"]
                L.append("By bot: " + ", ".join("%s %s" % (b, money(v)) for b, v in sorted(by.items())) + ".")
        return "\n".join(L)

    def text_race(self):
        """The coin race's /market: the penny bot now (its own log and the
        process table), the last 10 races and today's money from Kalshi."""
        now = self.now()
        today = et_day(now)
        res = self.ledger.results
        races = races_from(self._markets())
        fl = fleet(self.procs_fn())
        recs = log_records(os.path.join(res, "pinracepenny-live.jsonl"),
                           ("start", "live_halt", "live_order", "live_settled"))
        pv = penny_view(recs, now, ledger_events=set(races))
        st = pv["start"] or {}
        L = ["COIN RACE  %s ET" % et_str(now, "%a %m/%d %I:%M %p")]
        if fl["penny"]:
            L.append("Penny bot: RUNNING, pid %d. Real bets: %s." % (fl["penny"][0], rails_words(st.get("live_rails"))))
        elif fl["unknown"]:
            L.append("Penny bot: process table could not be read. Its rails: %s." % rails_words(st.get("live_rails")))
        else:
            L.append("Penny bot: NOT RUNNING (no pinracearm --live in the process table). Last rails: %s."
                     % rails_words(st.get("live_rails")))
        if os.path.exists(os.path.join(res, "pinracepenny.stop")):
            L.append("STOOD DOWN: the stop file results/pinracepenny.stop is present.")
        if pv["halt"]:
            L.append("STOP RAIL FIRED %s ET: %s. No real order since." % (
                et_str(pindesk.parse_t(pv["halt"].get("t")) or now, "%m/%d %I:%M %p"), pv["halt"].get("why")))
        elif st:
            L.append("Stop rail: not fired since the restart at %s ET."
                     % et_str(pindesk.parse_t(st.get("t")) or now, "%m/%d %I:%M %p"))
        else:
            L.append("Stop rail: unknown -- no start record in the penny log.")
        nxt = (int(now) // 900 + 1) * 900
        left = int(nxt - now)

        def legs_of(ls):
            return ", ".join("%s %s %.0fc x%g" % (_leg_name(o.get("ticker")), o.get("side"),
                                                  100.0 * _f(o.get("exec_price") or o.get("ask_seen")),
                                                  _f(o.get("filled"))) for o in ls)
        held = [x for x in pv["open"] if x[1] == nxt]
        others = [x for x in pv["open"] if x[1] != nxt]
        legs = "; ".join(legs_of(ls) for _e, _c, ls in held)
        L.append("Now: race closing %s ET (%d:%02d left) -- %s. $%.2f out." % (
            et_str(nxt), left // 60, left % 60, ("holding " + legs) if legs else "no legs yet",
            pv["staked"] or 0.0))
        if others:
            L.append("Awaiting Kalshi's result: " + "; ".join(
                "%s ET %s" % (et_str(c) if c else "?", legs_of(ls)) for _e, c, ls in others) + ".")
        if pv["pending"]:
            L.append("%d older leg(s) the bot never scored and Kalshi has no row for (oldest %s ET)."
                     % (sum(len(ls) for _e, _c, ls in pv["pending"]),
                        et_str(pv["pending"][0][1], "%m/%d %I:%M %p") if pv["pending"][0][1] else "?"))
        t = race_tally([r for r in races.values() if r["day"] == today])
        L.append("Today: %s" % ("no races settled yet." if not t["races"] else
                                "%s on %d races: %d won, %d tie, %d lost."
                                % (money(t["net"]), t["races"], t["won"], t["tie"], t["lost"])))
        L.append("")
        L.append("Last 10 races (Kalshi's books):")
        if races:
            for r in sorted(races.values(), key=lambda r: -(r["close"] or 0))[:10]:
                L.append(race_line(r))
        else:
            L.append("none on file.")
        L.append("")
        L.append("Paper race arms running: %s." % (
            "process table could not be read" if fl["unknown"] else
            (", ".join(fl["race_arms"]) if fl["race_arms"] else "none")))
        L += self._race_money_lines()
        return "\n".join(L)

    def _race_money_lines(self):
        """/race's money by window (2026-09-30), from botstats: every coin-race
        market in the main account, read from Kalshi live, one leg = one coin's
        market. Plus what /race did not say: the version, that NOTHING restarts
        the live race if it dies, what Kalshi holds open, the shared cash and
        today's refusals. A failure costs these lines only -- the rest of
        /race still answers."""
        try:
            b = self._bs_get("race")
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ["", "Money by window: could not build it (%s). The lines above still stand." % str(e)[:160]]
        L = [""]
        L += bs_money_lines(b["money"], "leg", money)
        L.append("")
        L += bs_setup_lines(b["running"])
        L += bs_open_lines(b["open"], "leg")
        L.append(bs_cash_line(b["balance"]))
        L += bs_activity_lines("race", b["activity_today"])
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
            return bs_all_text(self._bs_get("all"))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /bots: %s\nEverything else still works -- /stats and /race carry the "
                    "main account's numbers." % str(e)[:200])

    def text_bot(self, name):
        cmd = BOT_CMD_OF.get(name, "/" + name)
        try:
            b = self._bs_get(name)
            out = bs_bot_text(b, _bs().et_clock(self.now()))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build %s: %s\nEverything else still works -- /stats and /race carry the "
                    "main account's numbers." % (cmd, str(e)[:200]))
        more = {"pin": "More on pin: /stats (win rate vs break-even), /fills (today's orders), /open, /losses, /hedges.",
                "forecaster": "Every bot: /bots.", "ladder": "Every bot: /bots.",
                "weather": "Every bot: /bots."}.get(name)
        return out + ("\n\n" + more if more else "")

    def text_racestats(self):
        """The penny test's record by window (Kalshi's books) and every paper
        race arm on the same races (their own logs, tie-aware)."""
        now = self.now()
        today = et_day(now)
        res = self.ledger.results
        races = races_from(self._markets())
        if not races:
            return "No coin-race settlements on Kalshi's books yet."
        r30 = self.race30_epoch
        L = ["COIN RACE STATS  %s ET. Kalshi's books; a race = one 15-min contest; "
             "a tie pays 50c a leg and counts as a loss." % et_str(now, "%a %m/%d %I:%M %p")]
        first_day = min(r["day"] for r in races.values())
        allr = list(races.values())
        wins = [("ALL TIME (since %s)" % _md(first_day), allr),
                ("LAST 7 DAYS", [r for r in allr if r["day"] >= day_minus(today, 6)]),
                ("LAST 3 DAYS", [r for r in allr if r["day"] >= day_minus(today, 2)]),
                ("TODAY", [r for r in allr if r["day"] == today]),
                ("SINCE v-race30 (%s ET)" % et_str(r30, "%m/%d %I:%M %p"),
                 [r for r in allr if r["close"] is not None and r["close"] >= r30])]
        for title, rs in wins:
            L.append("%s: %s" % (title, race_tally_line(race_tally(rs))))
        since = {e: r for e, r in races.items() if r["close"] is not None and r["close"] >= r30}
        L.append("")
        L.append("Paper arms on the same %d races since v-race30 (their own logs and size; "
                 "a race Kalshi tied is a tie):" % len(since))
        z3res = None
        for name in RACE_ARMS:
            p = os.path.join(res, "pinracearm-%s.jsonl" % name)
            if not os.path.exists(p):
                L.append("%s: no log." % name)
                continue
            ar = arm_results(p)
            if name == "z3":
                z3res = ar
            rec = arm_record(ar, since)
            if not rec["entered"]:
                L.append("%s: in none of them." % name)
                continue
            note = ""
            if rec["ties_as_wins"]:
                note = " (its log booked %s)" % ("1 tie as a win" if rec["ties_as_wins"] == 1
                                                 else "%d ties as wins" % rec["ties_as_wins"])
            L.append("%s: in %d of %d: %d won, %d tie, %d lost, %s%s." % (
                name, rec["entered"], len(since), rec["won"], rec["tie"], rec["lost"], money(rec["net"]), note))
        if z3res is not None:
            z = z3_progress(z3res, races)
            verdict = ""
            if z["first50_losses"] >= Z3_KILL[0]:
                verdict = " -- AT THE KILL LINE"
            elif z["races"] >= Z3_PASS[0] and z["losses"] <= Z3_PASS[1]:
                verdict = " -- PASSED the %d bar" % Z3_PASS[0]
            elif z["races"] >= Z3_PASS_ALT[0] and z["losses"] <= Z3_PASS_ALT[1]:
                verdict = " -- PASSED the %d bar" % Z3_PASS_ALT[0]
            L.append("z3 bar: %d races so far, %d loss%s (first 50: %d). Pass = %d races with %d losses, "
                     "or %d with at most %d. Kill = %d losses in the first %d%s." % (
                         z["races"], z["losses"], "" if z["losses"] == 1 else "es", z["first50_losses"],
                         Z3_PASS[0], Z3_PASS[1], Z3_PASS_ALT[0], Z3_PASS_ALT[1], Z3_KILL[0], Z3_KILL[1], verdict))
        return "\n".join(L)

    # ---- /funds /bank /accounts ----
    def text_funds(self):
        """Every Kalshi account's money (funds_read) with each bot's bet size (funds_sizes) and its last
        FUNDS_DAYS ET days of gains and losses (funds_settled). A failure costs this command only."""
        try:
            getter = self.funds_getter or _bs().default_getter()
            f = funds_read(getter)
            now = self.now()
            return funds_text(f, funds_sizes(self.ledger.results), now, funds_settled(getter, f["subs"], now))
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /funds: %s\nEverything else still works -- /bots shows each bot pot's "
                    "cash." % str(e)[:200])

    # ---- /bars ----
    def text_bars(self):
        """Every running test against its pre-registered bar: research/bars.py's
        text, unchanged. NOT rebuilt here (the /brief rule): one place decides
        PASS / KILL / EXTEND / TOO EARLY, and the phone quotes it."""
        if self.bars_fn is not None:
            return self.bars_fn()
        try:
            import bars
            return bars.text(results=self.ledger.results, now=self.now())
        except Exception as e:                                  # noqa: BLE001
            log(traceback.format_exc())
            return ("Could not build /bars: %s\nEverything else still works -- /stats and /racestats "
                    "carry the raw numbers." % str(e)[:200])

    # ---- controls ----
    def control(self, which):
        if self.busy:
            return "Still working on the last command."
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
        return {"start": "Starting...", "pause": "Pausing: no new bets; waiting for open ones to settle...",
                "stop": "Stopping now..."}[which]

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
                return "Paired. This chat now controls the bot.\n\n" + HELP_TEXT
            log("refused pairing from chat %s" % chat_id)
            return None
        if self.chat_id is None or chat_id != self.chat_id:
            return None                                  # not ours: silence
        self.ledger.refresh()
        if cmd in ("/status", "/s", "/start@"):
            return self.text_status()
        if cmd == "/today":
            return self.text_day(et_day(self.now()), "TODAY")
        if cmd == "/yesterday":
            return self.text_day(et_day(self.now() - 86400), "YESTERDAY")
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
        if cmd == "/pause":
            return self.control("pause")
        if cmd == "/start":
            return self.control("start")
        if cmd == "/stop":
            if arg.strip().lower() == "yes":
                return self.control("stop")
            return "STOP stops right now, even with a bet open (it settles by itself but will not be hedged). Send:  /stop yes\nOr use /pause to finish open bets first."
        if cmd == "/mute":
            self.muted = True
            return "Alerts off. /unmute to turn them back on."
        if cmd == "/unmute":
            self.muted = False
            return "Alerts on."
        if cmd in ("/help", "/?"):
            return HELP_TEXT
        return "I did not understand that.\n\n" + HELP_TEXT

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
        if self.last_state is not None and state != self.last_state and not self.muted:
            msg = "STATE CHANGED: %s -> %s\n%s\n%s" % (self.last_state, state, hl, det)
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
            if silent:
                msg = ("RECORDER %s -- nothing written for %d+ min. That tape "
                       "cannot be recreated later. If the bot is also BLIND, "
                       "the problem is the connection to Kalshi, not our "
                       "programs." % (rec, pindesk.REC_FRESH_S // 60))
            else:
                msg = "RECORDERS WRITING AGAIN (was %s)" % self.last_rec
            self.say(msg)
            sent.append(msg)
        self.last_rec = rec
        # THE DISK. Tracked even when muted, so an unmute does not replay it.
        self.disk_level, dmsg = disk_alert(self.disk_level, h.get("disk_gb"))
        if dmsg and not self.muted:
            self.say(dmsg)
            sent.append(dmsg)
        losses = self.ledger.losing_closes()
        keys = {k for k, _n, _l in losses}
        if self.seen_losses is None:
            self.seen_losses = keys
        else:
            new = [x for x in losses if x[0] not in self.seen_losses]
            self.seen_losses = keys
            for close, net, legs in new:
                if not self.muted:
                    msg = "LOSS " + story_loss(self.ledger, close, net, legs)
                    self.say(msg)
                    sent.append(msg)
        if (now - et_day_start(today)) >= 8 * 3600 and self.last_daily != today and not self.muted:
            self.last_daily = today
            yday = et_day(now - 86400)
            msg = "YESTERDAY\n" + story_day(self.ledger, yday, now=now)
            self.say(msg)
            sent.append(msg)
        return sent

    # ---- main loop ----
    def poll_once(self, timeout=25):
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
            try:
                reply = self.handle(chat, m.get("text"))
            except Exception as e:                        # noqa: BLE001
                reply = "error: %s" % e
                log(traceback.format_exc())
            if reply:
                self.say(reply, chat_id=chat)

    def run(self):
        log("pinphone starting; paired chat: %s" % self.chat_id)
        # the process table for /stats and /race, read off the poll thread
        threading.Thread(target=proc_refresher, daemon=True).start()
        if self.chat_id:
            self.say("Pin Bot phone link is up. /status for the state, /help for commands.")
        while True:
            try:
                with open(HEARTBEAT, "w") as fh:
                    fh.write(time.strftime("%Y-%m-%dT%H:%M:%S"))
            except OSError:
                pass
            self.poll_once()
            try:
                self.alerts_tick()
            except Exception:                            # noqa: BLE001
                log(traceback.format_exc())


# ===========================================================================
def selftest():
    import tempfile
    import calendar

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinphone selftest: FAILED -- " + msg)

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
                # Kalshi answers for the NAMED pool only: pots 0-2 trade in pool 2, the weather pot (3) in pool 0
                if (q or {}).get("exchange_index") != (0 if sub == "3" else 2):
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
                       {"t": "2026-09-16T13:59:30.100Z", "ev": "live_fill", "n": 5},
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
        ck(r and r.startswith("Paired") and ph.chat_id == 111, "the right secret pairs the chat")
        ck(json.load(open(cfgp))["chat_id"] == 111, "...and the chat id is saved to the config file")
        ck(ph.handle(222, "/status") is None, "another chat is still ignored after pairing")
        s = ph.handle(111, "/status")
        ck("TRADING" in s and "Checked just now" in s and "process 4242 is OPEN" in s, "/status carries the state and its evidence")
        # MONEY COMES FROM KALSHI NOW, not from the log this test plants, so
        # "today" is legitimately empty here. The bank still comes from the
        # bot's own autosize record, which is ours to read.
        ck("Bank $500.00" in s and "TODAY" in s,
           "/status carries the bank and a TODAY line; the money itself is "
           "Kalshi's (results/kalshi_ledger.json) and is absent in this fixture")
        t = ph.handle(111, "/today")
        ck("$+1.66" in t and "+0.33%" in t and "1 closes" in t, "/today: money, %% of the bank at day start, closes")
        ck("no settled bets" in ph.handle(111, "/yesterday"), "/yesterday with nothing settled says so")
        ck("SELLERS:" in ph.handle(111, "/market") and "BOUGHT 85" in ph.handle(111, "/market"), "/market: level and what happened")
        # THE DAILY BRIEFING REACHES THE PHONE, and a failure inside it must
        # not take the command down -- he reads this when the app is not in
        # front of him.
        # /fills -- the operator's ask: filled, paid, seconds out, per order.
        _fl = ph.handle(111, "/fills")
        ck("ORDERS TODAY" in _fl or "No orders today" in _fl,
           "/fills answers with today's orders or says there were none")
        ck(ph.handle(111, "/bets") == _fl, "/bets is the same command")
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
            _f2 = ph.handle(111, "/fills")
            ck("96.8c" in _f2 and "12s out" in _f2 and "77/77" in _f2,
               "an order shows what filled, the price PAID in cents, and how "
               "many seconds were left -- the three things he asked for")
            ck("0/50" in _f2 and "1 lost the race" in _f2,
               "a ZERO-FILL order is shown, not hidden -- about one order in "
               "five fills nothing, and dropping them would report a 100% fill "
               "rate")
            ck("94.5c" in _f2 and "(oil)" in _f2,
               "an oil order shows its price from `ask_seen` and says (oil) "
               "where the seconds would be, because cmdlive does not record a "
               "tau on the order")
            ck("got 97" in _f2, "...and the footer totals contracts asked vs got")
        finally:
            L.orders = _sv_o
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
        ck("THE DAY --" not in (ph.handle(111, "/today") or ""),
           "and /today is UNTOUCHED -- it already existed and gives the plain "
           "money for the day; taking its name would have quietly replaced "
           "something he uses with something longer")
        # THE OPPORTUNITY TREND REACHES THE PHONE, and a health dict that does
        # not carry it must not break the command -- the operator reads
        # /market from his phone when the app is not in front of him.
        state["h"]["supply_lines"] = ["Cheap offers: up 7% on a normal day."]
        state["h"]["supply_age_d"] = 0.5
        mk = ph.handle(111, "/market")
        ck("IS THE OPPORTUNITY GOING AWAY?" in mk and "up 7%" in mk,
           "/market carries the opportunity trend, from the same lines the "
           "desktop shows, so the two cannot drift apart")
        ck("0.5 days ago" in mk,
           "...and says how old the measurement is, because a stale trend is a "
           "reassuring number about a week that already ended")
        state["h"].pop("supply_lines")
        ck("SELLERS:" in ph.handle(111, "/market"),
           "NULL: a health reading with no opportunity block still answers")
        ck(ph.handle(111, "/losses") == "No losing closes.", "/losses with none")
        ck(ph.handle(111, "/hedges") == "No hedges yet.", "/hedges with none")
        ck(ph.handle(111, "/open") == "No open bets.", "/open with none")
        ck("ALL TIME" in ph.handle(111, "/days"), "/days ends with all time")
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
            ck(len(s) < MAX_LEN, "/stats fits one Telegram message on this world (%d chars)" % len(s))
            ck("LIVE v-pinfix since 09/16 08:30 AM ET, pid 2554960." in s,
               "/stats names the live version, its start in ET and the pid")
            ck("Hedge trigger: belief 40%. Size 79 contracts (auto), bank $930.04 read 10:21 AM." in s,
               "the hedge trigger from the live argv, the size and bank from the bot's size file")
            ck("Halt if the bank falls to $829.86 (20% under its high of $1037.33): $100.18 of room." in s,
               "the halt line is 20% under the high-water mark, with the room left in dollars")
            ck("Today by the bot's own count: $+11.14 (stops at $-200 for the day)." in s,
               "the day figure from the bot's own file is labelled as the bot's, with the cap")
            ck("Paper arms: 2 (pin0.985, cmdarm-wide230) + 2 race arms (racectl, z3)." in s,
               "the fleet, counted and named from the process table")
            ck("Coin race: 2 races since 09/15: 1 won, 1 tie, 0 lost, $-0.91 (/race)." in s,
               "the coin race summary line: the tie is a tie, not a win")
            _blk = {}
            for _part in s.split("\n\n"):
                _blk[_part.split("\n")[0].split(" (")[0]] = _part
            ck(set(_blk) >= {"LIFETIME", "LAST 7 DAYS", "LAST 3 DAYS", "TODAY", "SINCE v-pinfix"},
               "five windows: lifetime, 7 days, 3 days, today, since the live version")
            _t = _blk["TODAY"]
            ck("Made $+0.76 on $87 risked; 5 mkts, 3 closes, 89 contracts; fees $0.04." in _t,
               "TODAY: 1.6626 + 0.0279 + 0.0186 - 0.4721 - 0.4814 = +0.76 on the 87.24 risked; "
               "5 markets on 3 closes; 89 contracts")
            ck("Best day" not in _t, "a one-day window has no best/worst day line")
            ck("Won 3 of 5 mkts (60.0 of 100); 98.9 of 100 contracts paid; by $ risked 97.8." in _t,
               "win rate by market (3 of 5), by contracts paid (88 of 89: the tie paid half) "
               "and by dollars (85.29 of 87.24)")
            ck("Break-even 98.0 of 100 contracts at 98.0c avg paid (fee in): margin +0.8 pts = $+0.87 per "
               "$100 risked. By count 97.7 of 100 mkts must win; 60.0 did." in _t,
               "break-even = dollars paid / contracts (87.24 / 89 = 98.0c); the margin is against "
               "the contracts paid (98.9 - 98.0) and matches the real profit per $100 risked; "
               "the count version beside it")
            ck("Losses 2: $-0.95, avg $-0.48, worst $-0.48 (HYPE 09/16); 0 hedged, their hedge legs netted $+0.00." in _t,
               "TODAY's losses are the two tied legs")
            _3 = _blk["LAST 3 DAYS"]
            ck("Made $-53.00 on" in _3 and "8 mkts" in _3,
               "LAST 3 DAYS adds 09-15 and 09-14: -38.80 -14.10 -0.856 on top of today")
            ck("Losses 5: $-54.71, avg $-10.94, worst $-38.80 (BTC 09/15); 1 hedged, their hedge legs netted $+5.00." in _3,
               "...five losses, the worst named, the hedged one counted with what its hedge got back")
            ck("Made $-53.00 on" in _blk["LAST 7 DAYS"],
               "LAST 7 DAYS is the same: 09-09 is outside it")
            _l = _blk["LIFETIME"]
            ck("Made $-57.25 on" in _l and "11 mkts" in _l,
               "LIFETIME adds 09-09 (+2.45, the -36.50 full hedge, the +29.80 over-hedge) and "
               "EXCLUDES the 09-07 row: 11 markets, not 12")
            ck("Best day $+0.76 (09/16), worst $-39.66 (09/15); avg $-6.36/day over 9 days." in _l,
               "best and worst ET day, and the average over the calendar days since 09/08")
            ck("Losses 6: $-91.21, avg $-15.20, worst $-38.80 (BTC 09/15); 2 hedged, their hedge legs "
               "netted $+44.00; hedge legs on won mkts netted $+55.30." in _l,
               "the FULL hedge counts (5.00 + 39.00 on two hedged losses) and the over-hedge's "
               "+55.30 sits with the won markets")
            ck("First buys: 50% with 20 s or less left (2 mkts, $+4.11), 50% at 21-45 s (2 mkts, $-52.90); 7 not timed." in _l,
               "seconds-left split from the ORDER records, money per bucket, untimed markets counted")
            ck("By bot: coin race $-1.76, crypto $-55.49." in _l,
               "the lifetime line splits the account by bot")
            ck("Made $+1.66 on" in _blk["SINCE v-pinfix"] and "1 mkts" in _blk["SINCE v-pinfix"],
               "SINCE the version: only the market that closed after 12:30Z")
            # this planted world's order rows are /stats-shaped (no "close"), so the per-day loop is stubbed
            # out; the since-version line reads Kalshi's books through _markets(), which this world has
            _days0 = ph.ledger.days
            try:
                ph.ledger.days = lambda: []
                _dy = ph.text_days()
            finally:
                ph.ledger.days = _days0
            ck("SINCE v-pinfix (" in _dy and ": $+1.66, 1 markets, 0 lost" in _dy
               and _dy.index("SINCE v-pinfix") < _dy.index("ALL TIME"),
               "/days carries the running version's own line (a deploy day mixes two versions), same money as /stats")

            # /race
            r = ph.handle(111, "/race")
            ck("Penny bot: RUNNING, pid 15. Real bets: 1 contract a leg, $20 out at most (settled bets "
               "give it back), only inside 30 s, 90c or better, up to 5 legs, stops on the first loss." in r,
               "/race: the penny bot's rails in words, from its own start record")
            ck("STOP RAIL FIRED 09/16 09:31 AM ET: first real loss: KXCRYPTOLEAD15M-26SEP160930 no at 85c. No real order since." in r,
               "the stop-on-first-loss state, with when and why")
            ck("Today: $-0.91 on 2 races: 1 won, 1 tie, 0 lost." in r,
               "today's coin-race money from Kalshi's books")
            _lines = r.split("\n")
            _i = _lines.index("Last 10 races (Kalshi's books):")
            ck(_lines[_i + 1] == "09/16 07:15 AM  HYPE no 98c + XRP yes 97c  TIE $-0.95"
               and _lines[_i + 2] == "09/16 05:00 AM  BTC no 98c + XRP yes 97c  WON $+0.05"
               and _lines[_i + 3] == "09/15 09:30 AM  ETH no 85c  LOST $-0.86",
               "the last races newest first: legs, side, price paid, TIE / WON / LOST, money")
            ck("Paper race arms running: racectl, z3." in r, "the race arms from the process table")
            ph.procs_fn = lambda: None
            _ru = ph.handle(111, "/race")
            ck("Penny bot: process table could not be read. Its rails:" in _ru
               and "Paper race arms running: process table could not be read." in _ru
               and "(process table could not be read)" in ph.handle(111, "/stats"),
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
            r2 = ph.handle(111, "/race")
            ck("Stop rail: not fired since the restart at 09/16 10:40 AM ET." in r2,
               "after a restart the rail reads as not fired -- a halt before the restart is history")
            ck("Now: race closing 11:15 AM ET (15:00 left) -- holding SOL yes 98c x1. $0.98 out." in r2,
               "the race closing next, the legs held on it and the dollars out")

            # /racestats
            q = ph.handle(111, "/racestats")
            ck("ALL TIME (since 09/15): 3 races: 1 won, 1 tie, 1 lost. $-1.76. 5 legs at 95.0c avg; "
               "break-even 95.3 of 100 legs must pay, actual 60.0." in q,
               "/racestats: races won/tie/lost, money, avg leg price, break-even vs actual per leg")
            ck("TODAY: 2 races: 1 won, 1 tie, 0 lost. $-0.91." in q, "...and today's")
            ck("z3: in 2 of 2: 1 won, 1 tie, 0 lost, $+0.04 (its log booked 1 tie as a win)." in q,
               "a --paper-live arm on the same races: its own log's money, the tie taken from Kalshi")
            ck("racectl: in 2 of 2: 1 won, 1 tie, 0 lost, $+9.00 (its log booked 1 tie as a win)." in q,
               "a plain paper arm reads its `settled` records the same way")
            ck("raceedge0: no log." in q and "gap075: no log." in q, "an arm without a log says so")
            ck("z3 bar: 3 races so far, 2 losses (first 50: 2). Pass = 125 races with 0 losses, or 250 "
               "with at most 1. Kill = 2 losses in the first 50 -- AT THE KILL LINE." in q,
               "the z3 bar counts EVERY race the arm entered, a tie as a loss, and names the kill line")
            ck(all("/%s" % c in HELP_TEXT for c in ("stats", "race", "racestats", "bars")), "the four are in /help")
            # /bars -- the operator's one-word verdicts. The text is bars.py's,
            # never rebuilt here; the phone only routes it.
            ph.bars_fn = lambda: "BARS-STUB"
            ck(ph.handle(111, "/bars") == "BARS-STUB", "/bars returns bars.py's text unchanged")
            ph.bars_fn = None
            _bt = ph.handle(111, "/bars")
            ck(_bt.startswith("BARS  ") and "VERDICT:" in _bt and "FRESH OFFER TEST" in _bt,
               "...and the real module answers on this world with its header and a verdict")
            ck(all(len(c) <= MAX_LEN for c in split_text(_bt)), "...in chunks under Telegram's limit")
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
                   Phone.text_race)
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
        b_ = ph.handle(111, "/bots")
        ck(b_.startswith("ALL BOTS -- Sep 16 11:00 AM ET"), "/bots: header in ET")
        # THE POT (2026-10-02), worked by hand. Now: main 1000 + open 29.10 + 19.60 = 1048.70; ladder
        # 15.10; forecaster 24.00; all 1087.80. TODAY: main settled -10.03, moved out 15.06 + 7.99 ->
        # 1048.70 + 10.03 + 23.05 = 1081.78 (pin -10.40 = -0.96%, race +0.37 = +0.03%); forecaster
        # 24 + 2.54 - 7.99 = 18.55 at midnight, + the 7.99 moved in = 26.54 (-9.6%); ladder ~0 at
        # midnight + 15.06 moved in = 15.06 (+0.28%); all 1087.80 + 12.528 = 1100.33 (-1.1%).
        # YESTERDAY: main 1048.70 + 14.00 - 76.95 = 985.75 at the start + 98 deposit + 2 back = 1085.75
        # (pin +0.05%, other -0.42%); forecaster 24 + 1.9928 - 5.99 = 20.00 (+2.7%); all 1103.75 (-0.31%).
        ck("Today: -$12.53 on $123.81 put in (-10.1%) = -1.1% of all pots ($1,100.33); 5 markets, 3 won, 2 lost\n"
           "  pin -$10.40 (-0.96%) | race +$0.37 (+0.03%) | forecaster -$2.54 (-9.6%) | ladder +$0.04 (+0.28%)"
           in b_,
           "/bots TODAY is all four pots: -10.40 + 0.37 - 2.54 + 0.042 = -12.53 on 99.80 + 19.60 + 2.45 + 1.958 "
           "put in = -1.1% of the $1,100.33 all pots held at midnight; each bot's share of ITS OWN pot listed")
        ck("Yesterday: -$3.42 on $36.32 put in (-9.4%) = -0.31% of all pots ($1,103.75); 3 markets, 2 won, 1 lost\n"
           "  pin +$0.54 (+0.05%) | race none | forecaster +$0.55 (+2.7%) | ladder none | weather none | other -$4.51 (-0.42%)"
           in b_,
           "YESTERDAY: the SOL and XRP markets that closed before midnight ET count on Sep 15 though Kalshi "
           "settled them on the 16th (UTC); the oil market that is no bot's is shown as `other`; the $98 "
           "deposit made during the day is part of the pot")
        ck("All time: -$15.95 on $160.13 put in (-10.0%) = -1.4" in b_
           and "% on money put in ($1,103.75); 8 markets, 5 won, 3 lost" in b_,
           "ALL TIME: every settlement in every pot, each once; as a share of the $1,103.75 deposited after fees")
        ck("The % after '=' or in brackets = share of the pot when the window began" in b_
           and "Kalshi's books explain" not in b_,
           "/bots says once what the percentages are; every planted pot reconciles, so no pot warning")
        ck("  Sep 16: -$12.53, 5 markets (pin -$10.40, race +$0.37, forecaster -$2.54, ladder +$0.04)" in b_
           and "  Sep 15: -$3.42, 3 markets (pin +$0.54, forecaster +$0.55, other -$4.51)" in b_
           and "Sep 14" not in b_,
           "by day, with each bot's part; no line for the days before anything settled")
        ck("Cash: main account $1,000.00 (pin + race share it), forecaster $24.00, ladder $15.10, weather $0.00 -- all pots "
           "$1,039.10." in b_ and "counts pin + race only" in b_,
           "the cash of every pot, and HIS QUESTION answered: the main page counts pin + race only")
        ck("Kalshi's own app shows the MAIN account only. The $39.10 sitting in the forecaster, ladder and weather pots" in b_,
           "/bots says why Kalshi's app reads lower than all pots: the bot pots' cash (24.00 + 15.10) is outside it")
        ck("PIN BOT (main account): running since Sep 16 7:59 AM ET. v-reopen98 + v-floor90. today -$10.40 "
           "(-0.96%), 7 days -$9.86 (-0.93%), all time -$9.86 (-0.93%); open: 1 ($29.10 at risk). /pin" in b_,
           "one line a bot: running since (ET), version, money with its share of the pot, open bets, its command")
        ck("PENNY LADDER (subaccount 1): STOPPED by its stop file" in b_
           and "FORECASTER (subaccount 2): running since Sep 16 8:34 AM ET. v-forecaster-race1." in b_
           and "COIN RACE (main account): running since Sep 15 10:49 PM ET. v-race20." in b_,
           "the paper race arm is not the live race; the ladder with a stop file is STOPPED, not dead")
        ck("NOT ANY BOT'S (main account): all time -$4.51 on 1 market; worst -$4.51 WTI 2:00 PM (Sep 15)." in b_,
           "a main-account market that is no bot's is shown on its own, never folded into pin")
        # /pin
        p_ = ph.handle(111, "/pin")
        ck(len(p_) < MAX_LEN, "/pin fits one Telegram message on this world (%d chars)" % len(p_))
        for _want, _why in (
                ("Pot: main account, shared with the coin race.", "its pot, and who shares it"),
                ("Running: YES, pid 3882400, since Sep 16 7:59 AM ET.", "running, pid, since when in ET"),
                ("Version: v-reopen98 + v-floor90, live since Sep 16 8:00 AM ET.", "its version from VERSIONS.md"),
                ("Settings: halts after 2 losing bets.", "its settings from its command line"),
                ("Keep-alive: watch_bot.ps1 restarts it", "what restarts it"),
                ("MONEY -- Kalshi settlements, main account, read Sep 16 11:00 AM ET;", "where the money comes from"),
                ("Today: -$10.40 on $99.80 put in (-10.4%) = -0.96% of its pot ($1,081.78); 2 markets, 1 won, 1 lost",
                 "today: the both-sides ETH market pays its winning YES side (-$11.30, not -$51.30); -0.96% of the "
                 "main pot at midnight ET"),
                ("Yesterday: +$0.54 on $29.40 put in (+1.8%) = +0.05% of its pot ($1,085.75); 1 market, 1 won, 0 lost",
                 "yesterday"),
                ("Last 7 days: -$9.86 on $129.20 put in (-7.6%) = -0.93% of its pot ($1,062.70); 3 markets, 2 won, "
                 "1 lost; 1 day up, 1 down", "7 days, with days up and down"),
                ("All time (since Sep 15): -$9.86 on $129.20 put in (-7.6%) = -0.93% on money put in ($1,062.70)",
                 "all time, since its first day, of the main account's money put in (1103.75 deposited - 41.05 "
                 "moved to the bot pots)"),
                ("% of its pot = of what the pot held when the window began (cash + open bets, + any money moved in "
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
        f_ = ph.handle(111, "/forecaster")
        ck(ph.handle(111, "/fc") == f_, "/fc is /forecaster")
        for _want, _why in (
                ("FORECASTER -- clean-room forecaster", "the forecaster's own page"),
                ("Pot: subaccount 2.", "its own pot"),
                ("Running: YES, pid 4196192, since Sep 16 8:34 AM ET.", "running"),
                ("Its log last wrote Sep 16 10:59 AM ET (30 s ago).", "how fresh its log is"),
                ("Version: v-forecaster-race1, live since Sep 16 8:35 AM ET.", "its version, not the keep-alive entry"),
                ("Settings: variant race1_98; 5% of paper size; up to 5 a side, 20 a quarter-hour; at most $22.00 in "
                 "play; buys 75c to 98.5c; stops the day at -$12.00, the run at -$20.00.", "its rails from its start record"),
                ("Today: -$2.54 on $2.45 put in (-103.7%) = -9.6% of its pot ($26.54); 1 market, 0 won, 1 lost",
                 "subaccount 2's money today: -$2.54 is -9.6% of the $26.54 it had (18.55 at midnight + 7.99 moved in)"),
                ("Yesterday: +$0.55 on $2.42 put in (+22.6%) = +2.7% of its pot ($20.00); 1 market, 1 won, 0 lost",
                 "and yesterday"),
                ("= -7.7% on money put in ($25.99)", "all time: of the 20 - 2 + 7.99 moved into its pot"),
                ("Cash: $24.00 -- its own pot (subaccount 2).", "its own cash"),
                ("1 order sent, 1 filled (5 contracts).", "what its log did today"),
                ("  Refused 1 time: order already in flight 1.", "its refusals in words")):
            ck(_want in f_, "/forecaster: " + _why)
        # /ladder
        l_ = ph.handle(111, "/ladder")
        ck("Running: NO -- stopped by its stop file (set " in l_ and ': "stood down by the operator".' in l_
           and "stopped on its own" not in l_,
           "/ladder: NOT running, and WHY -- its stop file, with what the file says")
        ck("Today: +$0.04 on $1.96 put in (+2.1%) = +0.28% of its pot ($15.06); 1 market, 1 won, 0 lost" in l_
           and "Cash: $15.10 -- its own pot (subaccount 1)." in l_
           and "Version: v-ladder-settlefix, live since Sep 16 9:16 AM ET." in l_,
           "/ladder: subaccount 1's money, cash and version")
        # /race keeps everything it said and adds the windows
        r_ = ph.handle(111, "/race")
        ck(r_.startswith("COIN RACE  ") and "Last 10 races (Kalshi's books):" in r_ and "Paper race arms running:" in r_,
           "/race still says everything it said before")
        ck("MONEY -- Kalshi settlements, main account, read Sep 16 11:00 AM ET; a leg counts on the ET day it closed:"
           in r_ and "Today: $+0.37 on $19.60 put in (+1.9%) = +0.03% of its pot ($1,081.78); 1 leg, 1 won, 0 lost"
           in r_ and "All time (since Sep 16): $+0.37 on $19.60 put in (+1.9%) = +0.03% on money put in ($1,062.70); "
           "1 leg, 1 won, 0 lost" in r_,
           "/race adds the race's money by window, in /race's own money style, legs not races, each a share of "
           "the main pot it shares with pin")
        ck(r_.index("Paper race arms running:") < r_.index("MONEY -- Kalshi settlements"),
           "...AFTER what /race already said")
        ck("Version: v-race20, live since Sep 15 10:50 PM ET." in r_
           and "Keep-alive: NONE -- if it dies, nothing restarts it." in r_
           and "Open now: 1 leg, $19.60 at risk:\n  race SOL 11:00 AM YES x20, $19.60 at risk" in r_
           and "Cash: $1,000.00 -- shared: the pin bot's cash sits in the same pot." in r_,
           "/race: its version, that nothing restarts it, the leg Kalshi holds open, the shared cash")
        ck(all(q.get("subaccount") in _bsm.SUBS for _p, q in _bs_asked if _p in _bsm.POT_PATHS)
           and set(_p for _p, _q in _bs_asked) <= set(_bsm.PATHS),
           "still every per-pot Kalshi read names its subaccount and every read is a read path")

        # /weather and /wx (2026-10-04): the weather dip-seller, subaccount 3, cash in POOL 0
        _wxdir = _bs_sandbox("botstats-weather")
        _bs_mode["m"] = "weather"
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
        w_ = ph.handle(111, "/weather")
        ck(ph.handle(111, "/wx") == w_, "/wx is /weather")
        for _want, _why in (
                ("WEATHER DIP-SELLER -- sells YES on a daily-high temperature bracket", "its own page"),
                ("Pot: subaccount 3.", "its own pot, shared with no bot"),
                ("Running: YES, pid 3955508, since Sep 15 3:56 AM ET.", "running: the --live dipsell_live.py"),
                ("Version: v-dipsell-live, live since Sep 15 3:56 AM ET.", "its VERSIONS.md entry"),
                ("2 contracts an order, one order a market", "its rails from its start record"),
                ("Keep-alive: boot_all.ps1 (every 10 min) restarts it unless the stop file is there.", "its keep-alive"),
                ("Yesterday: +$0.80 on $1.20 put in (+66.7%) = +1.6% of its pot ($50.00); 1 market, 1 won, 0 lost",
                 "yesterday's bracket, +1.6% of the $50 moved into its pot that day"),
                ("Open now: 1 bet, $1.10 at risk:\n  MIA high B90.5 NO x2, $1.10 at risk", "the bracket Kalshi holds open"),
                ("Cash: $49.70 -- its own pot (subaccount 3).", "its cash, read from POOL 0")):
            ck(_want in w_, "/weather: " + _why)
        ck(any(_p == "/portfolio/balance" and _q == {"subaccount": "3", "exchange_index": 0}
               for _p, _q in _bs_asked[_wx_n0:])
           and not any(_p == "/portfolio/balance" and _q.get("subaccount") == "3" and _q.get("exchange_index") != 0
                       for _p, _q in _bs_asked),
           "/weather: its cash is read from subaccount 3 in pool 0, never pool 2 (where Kalshi says $0.00)")
        wb_ = ph.handle(111, "/bots")
        ck("WEATHER DIP-SELLER (subaccount 3): running since Sep 15 3:56 AM ET. v-dipsell-live." in wb_
           and "/weather" in wb_ and "| weather none" in wb_ and "weather +$0.80 (+1.6%)" in wb_
           and "ladder $15.10, weather $49.70 -- all pots $1,088.80." in wb_
           and "The $88.80 sitting in the forecaster, ladder and weather pots" in wb_
           and "the ladder and the weather dip-seller are separate pots" in wb_,
           "/bots: the weather bot's line, its share of yesterday, its cash in the all-pots cash (1000 + 24 + "
           "15.10 + 49.70, each pot once -- the empty pool-0 rows of subaccounts 1 and 2 add $0), and that "
           "Kalshi's app does not show it")
        ck(live_version(os.path.join(_wxdir, "VERSIONS.md"))[0] == "v-reopen98 + v-floor90" == _bsm.version_of("pin")[0],
           "/stats' pin version skips the weather entry, as botstats does")
        ph.bs_procs = _bs_procs

        # NULL (2026-10-02): the account's books unreadable -> the money stands, NO pot %, and the reason
        _bs_sandbox("botstats-noledger")
        _bs_mode["m"] = "noledger"
        n_, nb_ = ph.handle(111, "/pin"), ph.handle(111, "/bots")
        ck("Today: -$10.40 on $99.80 put in (-10.4%); 2 markets, 1 won, 1 lost" in n_
           and "of its pot (" not in n_ and "on money put in" not in n_
           and "% of its pot: not shown -- transfers read failed (HTTP 404)." in n_
           and "Today: -$12.53 on $123.81 put in (-10.1%); 5 markets, 3 won, 2 lost\n"
               "  pin -$10.40 | race +$0.37 | forecaster -$2.54 | ladder +$0.04 | weather none\n" in nb_
           and "today -$10.40, 7 days -$9.86, all time -$9.86;" in nb_
           and "% of the pots: not shown -- main account: transfers read failed (HTTP 404)." in nb_,
           "NULL: the deposit/transfer listings unreadable -> every dollar figure still shown, NO percentage of "
           "any pot anywhere (never a guessed base), and the reason said once")

        # EMPTY: nothing settled, nothing open, nothing running, no logs
        _bs_sandbox("botstats-empty")
        _bs_mode["m"], ph.bs_procs = "empty", []
        e_, eb_ = ph.handle(111, "/pin"), ph.handle(111, "/bots")
        ck("Today: nothing settled yet" in e_ and "All time: nothing settled yet" in e_
           and "Nothing settled yet on Kalshi for this bot." in e_ and "Open now: none." in e_
           and "Running: NO, and there is no stop file -- it stopped on its own." in e_
           and "Version: no entry for it in VERSIONS.md." in e_ and "+$" not in e_ and "-$" not in e_,
           "EMPTY /pin: nothing settled YET, nothing open, not running and why -- no gain or loss invented")
        ck("Nothing settled yet in any pot." in eb_ and "today nothing yet, 7 days nothing yet, all time nothing yet"
           in eb_ and "+$" not in eb_ and "-$" not in eb_ and "By day:" not in eb_,
           "EMPTY /bots: says nothing has settled yet, no gain or loss, no empty day list")
        # DOWN: Kalshi refuses and the process list cannot be read -- unknown, never $0 or 'not running'
        _bs_sandbox("botstats-down")
        _bs_mode["m"], ph.bs_procs = "down", (lambda: None)
        d_, db_ = ph.handle(111, "/pin"), ph.handle(111, "/bots")
        ck("MONEY: COULD NOT READ KALSHI (settlements read failed (HTTP 401))" in d_
           and "Running: COULD NOT TELL" in d_ and "Open now: COULD NOT READ" in d_
           and "Cash: COULD NOT READ" in d_ and "$0.00" not in d_ and "nothing settled" not in d_,
           "DOWN /pin: a failed read is said as a failure -- never $0, never 'nothing settled', never 'not running'")
        ck("Today: unknown -- Kalshi could not be read" in db_ and "Last 7 days: unknown" in db_
           and "PARTIAL: these totals leave out pin, race, forecaster, ladder, weather, other" in db_
           and "running? could not tell" in db_ and "money: COULD NOT READ KALSHI" in db_
           and "! money: settlements read failed (HTTP 401): forecaster, ladder, pin, race, weather" in db_
           and "nothing settled" not in db_ and "Nothing settled" not in db_,
           "DOWN /bots: every total is 'unknown', the missing pots are named, each error said once")
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
            _rb = ph.handle(111, "/race")
            ck("Last 10 races (Kalshi's books):" in _rb
               and "Money by window: could not build it (planted botstats failure)." in _rb,
               "...and /race still gives everything it gave before, with the windows' failure said")
        finally:
            _bsm.bot, _bsm.all_bots = _sv_b, _sv_a
            globals()["LOG"] = _sv_log
        ck(all(c in HELP_TEXT for c in ("/bots", "/pin", "/forecaster", "/fc", "/ladder", "/weather", "/wx")),
           "/bots /pin /forecaster /fc /ladder /weather /wx are in /help")
        _bs_mode["m"], ph.bs_procs = "planted", _bs_procs
        r = ph.handle(111, "/stop")
        ck("/stop yes" in r and not ph.busy, "/stop without yes only explains; nothing is stopped")
        ck(ph.handle(111, "/mute") == "Alerts off. /unmute to turn them back on." and ph.muted, "/mute")
        ck(ph.handle(111, "/unmute") == "Alerts on." and not ph.muted, "/unmute")
        ck("Commands:" in ph.handle(111, "/help") and "Commands:" in ph.handle(111, "what"), "/help, and an unknown message gets the help")
        ck("Commands:" in ph.handle(111, "/help@PinBotBot"), "a command with the @botname suffix still works")

        # alerts: first tick only records; a change sends once
        ck(ph.alerts_tick() == [] and ph.last_state == "TRADING", "the first alert tick sends nothing, it only learns the state")
        ck(ph.alerts_tick() == [], "NULL: no change, no message")
        state["h"] = dict(state["h"], alive=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> DOWN" in sent[0], "the bot going down sends one alert")
        ck(ph.alerts_tick() == [], "...and not a second one while it stays down")
        state["h"] = dict(state["h"], alive=True)
        ck("DOWN -> TRADING" in ph.alerts_tick()[0], "coming back sends one too")
        state["h"] = dict(state["h"], blind={"since": None, "bad": 12, "why": "it cannot reach Kalshi"})
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> BLIND" in sent[0] and "NOT TRADING" in sent[0],
           "THE 09-21 NIGHT: alive but blind sends an alert -- it used to stay TRADING")
        state["h"] = dict(state["h"], blind=None)
        ck("BLIND -> TRADING" in ph.alerts_tick()[0], "and seeing again sends one")
        state["h"] = dict(state["h"], kalshi_ok=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "RECORDER SILENT: Kalshi recorder" in sent[0],
           "a silent Kalshi recorder sends one alert")
        ck(ph.alerts_tick() == [], "...and not a second while it stays silent")
        state["h"] = dict(state["h"], kalshi_ok=True)
        ck("WRITING AGAIN" in ph.alerts_tick()[0], "and writing again sends one")
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
        ck(len(sent) == 1 and sent[0].startswith("DISK 7.5 GB free, under 8 GB") and ph.disk_level == 8,
           "the tick sends the under-8 alert once")
        state["h"] = dict(state["h"], disk_gb=7.1)
        ck(ph.alerts_tick() == [], "...and not again at 7.1")
        state["h"] = dict(state["h"], disk_gb=5.9)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and sent[0].startswith("DISK 5.9 GB FREE") and ph.disk_level == 6, "under 6 sends the second")
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
        ck(len(sent) == 1 and sent[0].startswith("LOSS") and "$-38.80" in sent[0] and "WHY IT HURTS" in sent[0], "a new losing close is sent with its story")
        ck(ph.alerts_tick() == [], "...once")
        ph.muted = True
        state["h"] = dict(state["h"], alive=False)
        ck(ph.alerts_tick() == [] and ph.last_state == "DOWN", "muted: the change is tracked but not sent")
        ph.muted = False
        ck(not any(t_.startswith("YESTERDAY") for _c, t_ in tg.sent), "a summary already due at startup is NOT re-sent (it started at 11 AM ET)")
        # next day, 9 AM ET: the daily summary of the 16th goes out once
        now["t"] += 86400 - 2 * 3600
        sent = ph.alerts_tick()
        ck(any(m.startswith("YESTERDAY") and "2026-09-16" in m for m in sent), "after 8 AM ET the daily summary of yesterday goes out")
        ck(not any(m.startswith("YESTERDAY") for m in ph.alerts_tick()), "...once per day")
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
        ck(tg.sent[-1][0] == 111 and "Commands:" in tg.sent[-1][1] and ph.offset == 3, "poll: the paired chat gets its reply, the stranger nothing, offset advances")

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
        t_ = funds_text(f_, {}, now["t"])
        print("    --- /funds, the fake world ---\n    " + t_.replace("\n", "\n    "))
        ck(sorted(f_["subs"]) == [0, 1, 3] and f_["list_err"] is None, "/funds: the 3 listed accounts, from Kalshi's list")
        ck("MAIN ACCOUNT (0) -- main bot (pin) + coin race: $530.60" in t_
           and "  cash: weather pool $1.50, crypto pool $500.00; open bets: $29.10 on 1 market" in t_,
           "/funds: main = cash in BOTH pools + what its open bet cost = $530.60 (a 0-contract row is not a bet)")
        ck("SUBACCOUNT 1 -- penny ladder: $80.25" in t_ and "SUBACCOUNT 3 -- weather pool: weather dip-seller (stopped); "
           "crypto pool: empty: $41.10" in t_, "/funds: each subaccount's total, and what runs in it from FUNDS_WHAT")
        ck("ALL ACCOUNTS: $651.95 = cash $621.75 + open bets $30.20." in t_, "/funds: the grand total, 3 accounts x 2 pools")
        ck("The cash adds up to Kalshi's own whole-account figure ($621.75)." in t_,
           "/funds: checked against Kalshi's whole-account cash by pool")
        ck(not any(p == "/portfolio/balance" and (q["subaccount"], q["exchange_index"]) in ((1, 0), (3, 2)) for p, q in fa),
           "/funds: a pool listed at 0 is $0 in any unit -- not read again")
        ck(set(p for p, _q in fa) <= set(FUNDS_PATHS) and set(p for p, _q in f_["asked"]) == set(FUNDS_PATHS)
           and all("subaccount" in q for p, q in fa if p != FUNDS_PATHS[0])
           and all("exchange_index" in q for p, q in fa if p == "/portfolio/balance"),
           "/funds: only the three GET paths; every balance read names its account AND pool, every open-bets read its account")
        ck("SUBACCOUNT 7 -- unknown" in funds_text(funds_read(fw_get([], rows=fw_list + [
            {"subaccount_number": 7, "exchange_index": 2, "balance": "2.0000"}])), {}, now["t"]),
           "/funds: an account not in FUNDS_WHAT is shown as unknown, not dropped")
        t_ = funds_text(funds_read(fw_get([], brk=[{"balance": "41.5000", "exchange_index": 0},
                                                   {"balance": "600.0000", "exchange_index": 2}])), {}, now["t"])
        ck("CHECK: Kalshi's own whole-account cash is $641.50, but the accounts above add to $621.75" in t_,
           "/funds: cash Kalshi holds that no listed account explains is said")
        # unreadable reads: said, never $0, never a crash
        t_ = funds_text(funds_read(fw_get([], bad=lambda p, q: (503, "busy") if p == "/portfolio/balance"
                                          and q["subaccount"] == 1 else None)), {}, now["t"])
        ck("SUBACCOUNT 1 -- penny ladder: $80.25" in t_ and "crypto pool $80.25 (from Kalshi's list; the direct read failed: "
           "HTTP 503)" in t_ and "ALL ACCOUNTS: $651.95" in t_,
           "/funds: one direct cash read fails -> the list's figure, marked, because other pools proved its unit")
        t_ = funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/balance" else None)),
                        {}, now["t"])
        ck("$500.00" not in t_ and "$80.25" not in t_ and "crypto pool COULD NOT READ (HTTP 500)" in t_
           and "ALL ACCOUNTS: at least $30.20 (cash $0.00 + open bets $30.20) -- leaves out what could not be read: "
           "main account weather pool cash, main account crypto pool cash, subaccount 1 crypto pool cash, "
           "subaccount 3 weather pool cash." in t_ and "adds up" not in t_ and "CHECK:" not in t_,
           "/funds: EVERY direct cash read fails -> the list's unit is unproven, so no cash figure is shown (hard rule 5)")
        t_ = funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == FUNDS_PATHS[0] else
                                          "raise" if p == "/portfolio/balance" and q["subaccount"] == 1
                                          and q["exchange_index"] == 2 else None)), {}, now["t"])
        ck("list of subaccounts could not be read (HTTP 500)" in t_
           and "MAIN ACCOUNT (0) -- main bot (pin) + coin race: $530.60" in t_
           and "SUBACCOUNT 1 -- penny ladder: at least $0.00" in t_
           and "crypto pool COULD NOT READ (error: connection reset)" in t_
           and "SUBACCOUNT 4 -- coin-race reward test (stopped): at least" in t_ and "ALL ACCOUNTS: at least" in t_,
           "/funds: the list fails and a read raises -> the known accounts are tried, what failed is named, no crash")
        t_ = funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/positions"
                                          and q["subaccount"] == 3 else None,
                                          pos={0: [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00",
                                                    "market_exposure_dollars": "29.10"}],
                                               1: [{"ticker": "KXNEAR15M-26SEP161115-15", "position_fp": "5.00",
                                                    "market_exposure": 110}]})), {}, now["t"])
        ck("SUBACCOUNT 3 -- weather pool: weather dip-seller (stopped); crypto pool: empty: at least $40.00" in t_
           and "open bets: COULD NOT READ (HTTP 500)" in t_
           and "open bets: COULD NOT READ (a bet came without market_exposure_dollars)" in t_
           and "ALL ACCOUNTS: at least $650.85 (cash $621.75 + open bets $29.10) -- leaves out what could not be read: "
           "subaccount 1 open bets, subaccount 3 open bets." in t_,
           "/funds: an unreadable open-bets read, and a bet with only cents (never read as dollars), are said")
        clk = {"t": 0.0}

        def _tick():
            clk["t"] += 1.0
            return clk["t"]
        fa = []
        t_ = funds_text(funds_read(fw_get(fa), clock=_tick, deadline_s=2), {}, now["t"])
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
        t_ = funds_text(funds_read(fw_get([])), sz_, now["t"])
        ck("  bet size now: main bot 91 contracts a bet" in t_ and "  bet size now: ladder 6-contract bids" in t_
           and "\nSUBACCOUNT 3" in t_ and len(t_) < MAX_LEN, "/funds: each account carries its bots' bet sizes; one message")
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
        t_ = funds_text(funds_read(fw_get([])), {}, fnow, h_)
        print("    --- /funds with past days, the fake world ---\n    " + t_.replace("\n", "\n    "))
        ck("  past 7 ET days:\n"
           "  Wed Sep 16 so far: -$19.48 = main bot -$19.62 (1 of 1 lost) + race +$0.14 (0 of 1 lost)\n"
           "  Tue Sep 15: +$1.19 = main bot +$1.19 (0 of 2 lost)\n"
           "  Mon Sep 14: +$0.47 = main bot -$0.33 (1 of 1 lost) + other +$0.80 (0 of 1 lost)\n"
           "  Thu Sep 10 to Sun Sep 13: nothing settled\n"
           "  7 days: -$17.82 = main bot -$18.76 (2 of 4 lost) + race +$0.14 (0 of 1 lost) + other +$0.80 (0 of 1 "
           "lost; KXHIGHNY); -3.4% of the $530.60 it holds now\n\nSUBACCOUNT 1" in t_
           and "Liquidity rewards are paid outside these records and are not counted." in t_,
           "/funds past days: the main account's days, newest first, split main bot / race / other, and its 7-day "
           "total as a % of what it holds now")
        ck("  Wed Sep 16 so far: +$0.05 (0 of 1 lost)\n  Sun Sep 13 to Tue Sep 15: nothing settled\n"
           "  Sat Sep 12: -$9.90 (1 of 1 lost)\n  Thu Sep 10 to Fri Sep 11: nothing settled\n"
           "  7 days: -$9.85 (1 of 2 lost); -12.3% of the $80.25 it holds now" in t_
           and "  Wed Sep 16 so far: nothing settled\n  Tue Sep 15: +$0.50 (0 of 1 lost)\n"
           "  Mon Sep 14: -$1.70 (1 of 1 lost)\n  Thu Sep 10 to Sun Sep 13: nothing settled\n"
           "  7 days: -$1.20 (1 of 2 lost); -2.9% of the $41.10 it holds now" in t_
           and t_.count("  past 7 ET days:") == 3 and "Deposits and transfers are not gains." in t_
           and "to fit one message" not in t_ and len(t_) <= MAX_LEN,
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
        t_ = funds_text(funds_read(fw_get([])), {}, fnow, h_)
        ck("  Tue Sep 15: +$1.19 = main bot +$1.19 (0 of 2 lost)\n"
           "  Thu Sep 10 to Mon Sep 14: NOT READ\n"
           "  the 2 days read: -$18.29 = main bot -$18.43 (1 of 3 lost) + race +$0.14 (0 of 1 lost); -3.4% of the "
           "$530.60 it holds now\n"
           "  NOT READ: Mon Sep 14, Sun Sep 13, Sat Sep 12, Fri Sep 11, Thu Sep 10 (HTTP 503)" in t_
           and "SUBACCOUNT 1 -- penny ladder: $80.25\n  cash: crypto pool $80.25; open bets: none\n"
           "  past 7 ET days: COULD NOT READ (HTTP 500)" in t_ and "  7 days: -$1.20 (1 of 2 lost)" in t_
           and sorted(hm) == [3],
           "/funds past days: main's 3rd page fails -> the 2 whole days are shown, Sep 10-14 named NOT READ (the "
           "half-read Sep 14 is not shown); sub 1 fails -> said; neither failed pull is kept")
        h_ = funds_settled(fw_get([], bad=lambda p, q: "raise" if p == FUNDS_HIST_PATH and q["subaccount"] == 3
                                  else (200, {"cursor": ""}) if p == FUNDS_HIST_PATH else None), [0, 3], fnow, memo={})
        ck(h_[0]["err"] == "no 'settlements' list in Kalshi's reply" and h_[3]["err"] == "error: connection reset"
           and "past 7 ET days: COULD NOT READ (no 'settlements' list in Kalshi's reply)"
           in funds_text(funds_read(fw_get([])), {}, fnow, h_),
           "/funds past days: a reply without the settlements list is an error, never 'nothing settled'; a raise is "
           "said")
        t_ = funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/balance" else None)),
                        {}, fnow, funds_settled(fw_get([]), [0, 1, 3], fnow, memo={}))
        ck("  7 days: -$17.82 = main bot" in t_ and "% not shown: what it holds now was not read whole" in t_
           and "% of the $" not in t_,
           "/funds past days: no % on a balance that was not read whole")
        t_ = funds_text(funds_read(fw_get([], rows=[{"subaccount_number": 0, "exchange_index": 2, "balance": "0.5000"}],
                                          pos={}, brk=[])), {}, fnow, funds_settled(fw_get([]), [0], fnow, memo={}))
        print("    --- /funds past days, an account holding 50c ---\n    " + t_.replace("\n", "\n    "))
        ck("  7 days: -$17.82 = main bot" in t_ and "% not shown: it holds under $1" in t_ and "% of the $" not in t_,
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
           in funds_text(funds_read(fw_get([])), {}, fnow, h_),
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
        t_ = funds_text(bf, {}, fnow, bh)
        ck(len(t7) > MAX_LEN and len(t_) <= MAX_LEN and "to fit one message" in t_
           and t_.count("  7 days: ") == 9 and t_.count("  past 7 ET days -- ") == 9,
           "/funds past days: when 7 day lines do not fit one message (%d chars), fewer are listed and that is said "
           "(%d chars); all 9 accounts keep their 7-day total" % (len(t7), len(t_)))
        # routed: /funds /bank /accounts, through handle() and the poll loop
        ck(ph.funds_getter is None, "/funds reads Kalshi through botstats' getter (kauth.get, GET only) by default")
        _FUNDS_HIST.clear()
        fa = []
        ph.funds_getter = fw_get(fa)
        ck(all((ph.handle(111, c_) or "").startswith("MONEY IN EVERY ACCOUNT") and "ALL ACCOUNTS: $651.95" in ph.handle(111, c_)
               for c_ in ("/funds", "/bank", "/accounts", "/Funds@pinbot")),
           "/funds, /bank and /accounts are routed to the funds page")
        t_ = ph.handle(111, "/funds")
        ck("  past 7 ET days:\n  Thu Sep 17 so far: nothing settled\n  Wed Sep 16: -$19.48 = main bot" in t_
           and "  7 days: -$17.82 = main bot -$18.76" in t_ and "  7 days: -$9.85 (1 of 2 lost)" in t_
           and sum(1 for p, _q in fa if p == FUNDS_HIST_PATH) == 5,
           "/funds through handle() carries every account's past days (phone clock: Thu Sep 17), and nine /funds "
           "inside 60 s read the settlements once")
        ck(ph.handle(333, "/funds") is None, "/funds: a stranger gets nothing")
        ck("/funds" in HELP_TEXT and "/bank" in HELP_TEXT and "/accounts" in HELP_TEXT, "/funds is in /help")
        tg.push(111, "/funds")
        ph.poll_once()
        ck(tg.sent[-1][0] == 111 and "ALL ACCOUNTS: $651.95" in tg.sent[-1][1] and "main bot 85 contracts a bet" in tg.sent[-1][1]
           and "  past 7 ET days:" in tg.sent[-1][1],
           "/funds through the poll loop: the paired chat gets the page, with the live log's bet size and past days")
        with open(LOG, encoding="utf-8") as _fh:
            _lg = _fh.read()
        ck(os.path.dirname(LOG) == td and "SENT: MONEY IN EVERY ACCOUNT" in _lg,
           "the self-test logs what it 'sent' to its own temp folder, never the live phone bot's results/pinphone.log")
        _FUNDS_HIST.clear()
    globals()["LOG"] = _st_log
    _pl.LEDGER = _pl_sv
    _bsm.RESULTS = _bs_saved[0]
    _bsm._MEMO.clear()
    _bsm._MEMO.update(_bs_saved[1])
    _bsm._BACK.clear()
    _bsm._BACK.update(_bs_saved[2])
    print("pinphone selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    if "--preview" in sys.argv:
        ph = Phone({"chat_id": 0}, FakeTelegram())
        ph.ledger.refresh()
        print(ph.text_status())
        print("\n--- /market ---\n" + ph.text_market())
        print("\n--- /hedges ---\n" + ph.text_hedges())
        t0 = time.time()
        n = python_procs()
        print("\n(process table: %s in %.1f s -- the daemon reads it on a background thread)"
              % ("%d python processes" % len(n) if n is not None else "COULD NOT BE READ", time.time() - t0))
        for name, fn in (("/stats", ph.text_stats), ("/race", ph.text_race), ("/racestats", ph.text_racestats),
                         ("/bots", ph.text_bots), ("/pin", lambda: ph.text_bot("pin")),
                         ("/forecaster", lambda: ph.text_bot("forecaster")), ("/ladder", lambda: ph.text_bot("ladder")),
                         ("/weather", lambda: ph.text_bot("weather")), ("/funds", ph.text_funds)):
            t0 = time.time()
            out = fn()
            print("\n--- %s (%d chars, %.1f s) ---\n%s" % (name, len(out), time.time() - t0, out))
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
    Phone(cfg, Telegram(cfg["token"])).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
