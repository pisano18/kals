"""/funds (/bank /accounts), the READING half: what runs in each account, every account's cash and open bets from Kalshi
(funds_read), each bot's bet size from its own log (funds_sizes) and the last FUNDS_DAYS ET days of settlements
(funds_hist / funds_settled / funds_days). page.py words it.

v-tg-rebuild step 9 (2026-10-30, lane D4): MOVED VERBATIM out of research/pinphone.py, which re-exports every name here
(pinphone.funds_read, pinphone._FUNDS_HIST, ... are these very objects: its self-test and Phone.text_funds keep working
unchanged). The only edits: imports instead of pinphone's globals (_f from botdata.fmt, log from phone.log, the
registry as bots); its two copied helpers are shared since rebuild step 12 (_bs: phone.render.botcards, read_json:
botdata.paths). Kalshi is read only through the `getter` the
caller passes (GET only; ctx.funds_get() -- botstats.default_getter(), kauth.get -- in production).
"""
import re
import time
import traceback

import bots as _bots
import pinday
import pinledger
from botdata import paths as _paths
from botdata.fmt import _f
from botdata.paths import read_json                                # noqa: F401  (step 12: was a copy)
from phone.render.botcards import _bs                               # noqa: F401  (step 12: was a copy)
from phone.log import log

RESULTS = _paths.RESULTS                            # = pinphone.RESULTS (funds_sizes' default folder)


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


# ---- the command's reading half (Phone.text_funds' reads, in its order) ------------------------------------------------
def load(ctx):
    """Every account's money, the bet sizes and the past days -- exactly Phone.text_funds' reads: the getter, funds_read,
    the clock, the active bots, funds_sizes, then funds_hist (botstats' settlement rows; this page's own pull only for
    an account botstats could not give)."""
    getter = ctx.funds_get()
    f = funds_read(getter)
    now = ctx.now()
    act = ctx.active()
    sizes = funds_sizes(ctx.ledger.results, act)
    hist = funds_hist(getter, f["subs"], now, bs_getter=ctx.bs_getter)
    return {"f": f, "sizes": sizes, "now": now, "hist": hist, "active": act}
