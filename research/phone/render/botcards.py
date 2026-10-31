"""botcards.py -- the bot cards: every bs_* renderer of /bots and the one-bot pages (/pin /fc /ladder /weather /fx /jb),
and the money tables, headlines and 'earlier bots' lines /status /today /days /race share with them.

v-tg-rebuild step 9, lane D2 (2026-10-30): MOVED HERE VERBATIM from pinphone.py (the "/bots /pin /forecaster /ladder"
section, with the few helpers it needs: BOT_WORD, DESK_BOT, main_sharers, main_shared, dot, ret, HALT_WORDS,
halt_words). pinphone re-exports every name below (pinphone.bs_all_html IS botcards.bs_all_html), so the old Phone
methods, tgcharts, bars.py and the self-tests are unchanged; the golden replay is byte-identical.
Pure renderers: they read nothing but botstats (imported late, _bs()) and the registry; never pinphone (under
--selftest pinphone runs as __main__). usd / dollars / _f / _cnt are botdata.fmt's, the same code pinphone's copies are.
"""
import re
import time

import bots as _bots
import pinday
from botdata.fmt import _f, cnt as _cnt, dollars, dot, ret, usd   # dot, ret: one copy since step 12
from phone.html import details, elines, esc, hbar, i_, norm_money, pre, table
from pindesk import coin

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
# v-tg-30d (2026-10-30): the last 30 days between the 7 days and the month (botdata.money.LAST_DAYS)
BS_WINDOWS = ("today", "yesterday", "last_7_days", "last_30_days", "this_month", "all_time")
BS_LABEL = {"today": "Today", "yesterday": "Yesterday", "last_7_days": "Last 7 days", "last_30_days": "Last 30 days",
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
        if k in ("last_7_days", "last_30_days", "all_time") and w and w["active_days"] > 1:
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
BS_SHORT = {"today": "Today", "yesterday": "Yest", "last_7_days": "7 days", "last_30_days": "30 days", "all_time": "All"}


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
    rows, base = [("", "Made", "Return", whose)], None
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
    rows = [("Day", "Made", "Return", "of bank", "Legs" if unit == "leg" else "Mkts", "Lost", "")]
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
    L = ["💰 <b>Money made</b> <i>(%s, read %s; a %s counts on the ET day it closed)</i>"
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
    """'🟢 Pin bot made +$5.31 today (+2.6% on $202.56 staked · +0.40% of its bank)' -- bs_window_line's own
    figures; nothing settled and unread are said. `when` names the window ('yesterday', 'last 7 days').
    v-tg-money-words (2026-10-31): money made is SAID as made ('made' / 'lost'), never a bare signed amount the
    operator can read as the bank."""
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
    made = ("lost " if w["money"] < -0.004 else "made ") + usd(w["money"])
    said = ("%s %s %s" % (who, made, when)) if who else "%s %s" % (when[:1].upper() + when[1:], made)
    return "%s <b>%s</b> (<b>%s</b> on %s staked%s)" % (
        dot(w["money"]), esc(said), esc(bs.pct(w["return_pct"])), esc(_cash(w.get("put_in"))), esc(share))


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
    rows = [("Bot", "Made", "of bank", "Return", "Lost")]
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
        rows = [("Bot", "Made", "Return", "of bank", "")]
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
        rows = [("Day", "Made", "of pots", "Return", "Lost", "")]
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
