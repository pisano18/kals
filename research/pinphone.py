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
  /race       the coin race penny bot now, and its last 10 races
  /racestats  the coin race record, and the paper arms on the same races
  /bars       every running test against its pre-registered bar: the numbers
              so far, days into the window, PASS / KILL / EXTEND / TOO EARLY
  /pause      no new bets, wait for open ones, stop     /start    trade again
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
/race - the coin race penny bot right now, and its last 10 races
/racestats - the coin race record, and the paper arms on the same races
/bars - every running test against its pre-registered bar: numbers so far, days into the window, PASS / KILL / EXTEND / TOO EARLY
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
_VER_RE = re.compile(r"^#\s+(v-\S+)\s+--\s+(\d{4}-\d{2}-\d{2})"
                     r"(?:\s+(~?)(\d{2}):(\d[\dx])(?::\d{2})?Z?)?\s*(.*)$", re.I)


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
    race's entries (v-race30, v-race-tie1...) are its own bot's and would
    otherwise sit on top and date every 'since the version' figure wrong."""
    for v in versions(path):
        if re.search(r"coin.?race|penny", v[3], re.I):
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
        L = ["STATS  %s ET. Money = Kalshi's books, every bot; days are ET." % et_str(now, "%a %m/%d %I:%M %p")]
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
        return "\n".join(L)

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
        if cmd == "/bars":
            return self.text_bars()
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

    with tempfile.TemporaryDirectory() as td:
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
    _pl.LEDGER = _pl_sv
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
        for name, fn in (("/stats", ph.text_stats), ("/race", ph.text_race), ("/racestats", ph.text_racestats)):
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
