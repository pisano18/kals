"""words.py -- botstats' numbers in plain words for a phone screen: refusal reasons (PLAIN, plain), a window's line,
the pot notes, one bot's page (_bot_text, also the desktop's), the all-bots summary (text_summary), the cash line
(shown_cash) and the pot-check warnings.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
"""
import re

import bots as _reg
import pinday
from botdata import money as _money
from botdata import report as _report
from botdata import status as _status
from botdata import tables as _tables
from botdata.clock import day_label, et_clock
from botdata.fmt import pct, plural as _n, pot_pct_txt, usd


def pot_words(w, whose="its bank"):
    """'-0.93% of its bank ($1,088.32)' / '-1.9% on money put in ($946.00)', or None when the pot is
    unknown -- a percentage is never shown on a guessed base."""
    if not w or w.get("pot_pct") is None or w.get("pot") is None:
        return None
    base = usd(w["pot"]).lstrip("+")
    if w.get("pot_kind") == "money_in":
        return "%s on money put in (%s)" % (pot_pct_txt(w["pot_pct"]), base)
    return "%s of %s (%s)" % (pot_pct_txt(w["pot_pct"]), whose, base)


# ---- words for a phone screen -------------------------------------------------
# The bots' refusal reasons in ordinary words (the dict keeps the raw names). v-tg-rebuild step 3 (2026-10-30): the
# shared part (bots.PLAIN_BASE) then each bot's own Records.refusal_words, in bot order; the first match wins.
PLAIN = _reg.table("PLAIN")


def plain(why):
    for pat, words in PLAIN:
        if re.search(pat, str(why)):
            return words
    return str(why)


def _wline(w, name, whose="its bank"):
    if w is None:
        return "%s: COULD NOT READ KALSHI" % name
    if not w["markets"]:
        return "%s: nothing settled" % name
    pw = pot_words(w, whose)
    return "%s: %s on %s in (%s)%s, %d won, %d lost" % (
        name, usd(w["money"]), usd(w["put_in"]).lstrip("+"), pct(w["return_pct"]),
        (" = " + pw) if pw else "", w["won"], w["lost"])


def _pot_note(m):
    """One line on what the pot percentages are, or why none is shown (None if nothing to say)."""
    ws = [m.get(k) for k in _money.WINDOW_KEYS if m.get(k) and m[k]["markets"]]
    if not ws:
        return None
    if any(w.get("pot_pct") is not None for w in ws):
        shared = m.get("pot_shared_with") or []
        return ("%% of its bank = of what the pot held when the window began (cash + open bets, + any money "
                "moved in during it); all time = of the money put in%s." % (
                    " -- the pot is the whole main account, shared with the %s" % " and the ".join(
                        _tables.SPEC[b]["label"].lower() for b in shared) if shared else ""))
    why = next((w.get("pot_why") for w in ws if w.get("pot_why")), None)
    return ("%% of its bank: not shown -- %s." % why) if why else None


def pot_as_of_note(windows):
    """'% from the balances Kalshi gave at 9:43 PM ET -- its latest read failed.' when any of these windows'
    percentages rest on the last good read (pot_context's fallback), else None."""
    t = next((w.get("pot_as_of") for w in windows if w and w.get("pot_as_of")), None)
    return ("%% from the balances Kalshi gave at %s -- its latest read failed (connection), so they are that "
            "old." % et_clock(t)) if t else None


def _bot_text(b):
    L = []
    r = b["running"]
    L.append("%s -- %s" % (b["label"].upper(), b["what"]))
    L.append("Pot: %s" % (" + ".join(_tables.SUB_NAME[str(s)] for s in (b.get("subaccounts") or [b["subaccount"]])) + (" (shared with %s)" % ", ".join(
        _tables.SPEC[x]["label"].lower() for x in b["shares_subaccount_with"]) if b["shares_subaccount_with"] else "")))
    if r["alive"] is None:
        L.append("Running: COULD NOT TELL (process list unreadable)")
    elif r["alive"]:
        L.append("Running: yes, since %s (pid %s)" % (r["started_et"] or "?", r["pid"]))
    else:
        L.append("Running: NO" + (" -- stopped by its stop file (%s)" % r["stop_flag_et"] if r["stop_flag"] else ""))
    if r["halted"]:
        L.append("HALTED %s: %s" % (r["halted"]["t_et"], r["halted"]["why"] or r["halted"]["what"]))
    for p in r["problems"]:
        if not p.startswith("stop file is set") or r["alive"]:
            L.append("! " + p)
    if r["version"]:
        L.append("Version: %s (%s)" % (r["version"], r["version_et"] or "no time"))
    if r["settings_text"]:
        L.append("Settings: " + r["settings_text"])
    if not r["keepalive"]:
        L.append("Keep-alive: none -- if it dies nothing restarts it")
    m = b["money"]
    L.append("")
    if not m["ok"]:
        L.append("MONEY: COULD NOT READ KALSHI (%s)" % (m["error"] or "?"))
    else:
        head = "Money (Kalshi, by market close day ET)"
        if not m["complete"]:
            head += " -- HISTORY STILL LOADING, all-time is partial"
        if m["stale"]:
            head += " -- last read failed, showing %s" % (m["as_of_et"] or "?")
        L.append(head + ":")
        for k in _money.WINDOW_KEYS:
            L.append(_wline(m[k], m[k]["label"]))
        if _pot_note(m):
            L.append("  " + _pot_note(m))
        for k in ("today", "all_time"):
            w = m[k]
            if w["markets"]:
                wd = "" if k == "today" else " (%s)" % day_label(w["worst"]["day"])
                bd = "" if k == "today" else " (%s)" % day_label(w["best"]["day"])
                L.append("  %s worst %s %s%s, best %s %s%s" % (w["label"].lower(), usd(w["worst"]["money"]),
                                                              w["worst"]["what"], wd, usd(w["best"]["money"]),
                                                              w["best"]["what"], bd))
        if m["all_time"]["hedged"]:
            L.append("  hedged markets: %d all time" % m["all_time"]["hedged"])
        days = [d for d in m["days_7"] if not d["before_first"]]
        if days:
            L.append("By day:")
            for d in days:
                L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                                       "%s, %s (%d won)" % (usd(d["money"]), _n(d["markets"], "market"), d["won"])))
        if m["first_day"]:
            L.append("First settled: %s" % day_label(m["first_day"]))
    o = b["open"]
    if not o["ok"]:
        L.append("Open now: COULD NOT READ (%s)" % o["error"])
    elif not o["count"]:
        L.append("Open now: none")
    else:
        L.append("Open now: %d, %s at risk" % (o["count"], usd(o["at_risk"]).lstrip("+")))
        for p in o["positions"][:6]:
            L.append("  %s %s x%g" % (p["what"], p["side"].upper(), p["contracts"]))
    bal = b["balance"]
    L.append("Cash: %s (%s)" % ((usd(bal["dollars"]).lstrip("+") if bal["ok"] else "COULD NOT READ"), bal["note"]))
    if b["last_settled"]:
        L.append("Last settled:")
        for x in b["last_settled"]:
            day = pinday.et_day_of_ticker(x["ticker"])
            L.append("  %s %s %s x%g %s" % (day_label(day) if day else (x["time_et"] or "?"), x["what"],
                                            {"both": "BOTH SIDES", "-": "-"}.get(x["side"], x["side"].upper()),
                                            x["contracts"], usd(x["money"])))
    a = b["activity_today"]
    if not a["ok"]:
        L.append("Today's log: %s" % a["note"])
    else:
        s = "Today (its log): %s sent, %d filled (%g contracts)" % (_n(a["sent"], "order"), a["filled"],
                                                                    a["contracts_filled"])
        if b["name"] == "pin" and a["hedges"]:
            s += ", " + _n(a["hedges"], "hedge")
        if b["name"] in ("ladder", "weather"):
            s += ", %d cancelled" % a["cancelled"]
        L.append(s)
        if a["refused"]:
            grouped = {}
            for k, v in a["refused_why"].items():
                grouped[plain(k)] = grouped.get(plain(k), 0) + v
            top = ", ".join("%s %d" % (k, v) for k, v in sorted(grouped.items(), key=lambda kv: -kv[1])[:3])
            L.append("  %s %d times (%s)" % ("passed" if b["name"] == "pin" else "refused", a["refused"], top))
        for h in a["halts"][-3:]:
            L.append("  %s %s %s" % (h["t_et"], h["what"], h["why"]))
    return "\n".join(L)


def text_summary(name="all", now=None, getter=None, procs=None):
    """Plain words, ET, short lines, for a phone screen. `name` is a bot or 'all'."""
    if name != "all":
        return _bot_text(_report.bot(name, now=now, getter=getter, procs=procs))
    a = _report.all_bots(now=now, getter=getter, procs=procs)
    L = ["ALL BOTS -- %s" % a["as_of_et"],
         "% of a pot = of what it held when the window began; all time = of the money put in."]
    for w in _money.WINDOW_KEYS:
        t = a["total"][w]
        L.append(_wline(t, t["label"], "all pots"))
        bm, bp = _status.shown_by(a, t["by_bot_markets"]), _status.shown_by(a, t["by_bot_pot_pct"], "none")   # v-tg-active
        bits = ["%s %s%s" % (b, usd(v) if bm[b] else "none",
                             (" (%s)" % pot_pct_txt(bp[b])) if bm[b] and bp.get(b) is not None else "")
                for b, v in _status.shown_by(a, t["by_bot"]).items() if b not in ("other", _status.EARLIER) or bm[b]]
        if t["markets"]:
            L.append("  " + " | ".join(bits))
        if t["partial"]:
            L.append("  PARTIAL -- could not read: %s" % ", ".join(t["missing"]))
    L.append("By day:")
    for d in a["total_days_7"]:
        L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                               "%s, %s" % (usd(d["money"]), _n(d["markets"], "market"))))
    bal = a["balances"]

    def cash(x):
        return "?" if x is None else usd(x).lstrip("+")
    L.append("Cash: %s, all %s" % (", ".join("%s %s" % (k, cash(v)) for k, v in shown_cash(a)), cash(bal["all"])))
    L.append("Main-page totals include the main account only (pin%s); the other pots are separate."
             % (" + race" if "race" in a["active"] else ""))
    run = []
    for b in a["active"]:
        r = a["bots"][b]["running"]
        s = "?" if r["alive"] is None else ("yes" if r["alive"] else ("stopped (flag)" if r["stop_flag"] else "NO"))
        if r["halted"]:
            s += ", HALTED"
        run.append("%s %s" % (b, s))
    L.append("Running: " + ", ".join(run))
    for b in a["active"]:
        o = a["bots"][b]["open"]
        if o["ok"] and o["count"]:
            L.append("Open: %s %d (%s at risk)" % (b, o["count"], usd(o["at_risk"]).lstrip("+")))
    for e in a["errors"]:
        L.append("! " + e)
    L += pot_check_lines(a.get("pot_check"))
    return "\n".join(L)


def shown_cash(a):
    """[(name, dollars)] one a pot whose bot is active -- 'main' always -- and every other pot's cash on ONE line, 'earlier
    bots' pots' (v-tg-active), so the list still adds up to all pots. None = could not read."""
    bal, act = a["balances"], set(a.get("active") or _tables.BOTS)
    out, rest, unread = [], 0.0, False
    for k, bots in (bal.get("pot_bots") or {}).items():
        v = bal.get(k)
        if k == "main" or any(b in act for b in bots):
            out.append((k if k == "main" else next(b for b in bots if b in act), v))   # named for its running bot
        elif v is None:
            unread = True
        else:
            rest += v
    if unread or abs(rest) > 0.004:
        out.append(("earlier bots' pots", None if unread else round(rest, 4)))
    return out


def pot_check_lines(pc):
    """'! The main account's books are $153.65 off: ...' for each pot whose cash + open bets is not
    explained by money put in + every settled market. Nothing when they agree or cannot be checked."""
    out = []
    for k in _tables.SUBS:                                       # per pot; 'all' would repeat them
        x = (pc or {}).get(k)
        if x and x.get("off"):
            out.append("! The %s holds %s %s than Kalshi's books explain (cash + open bets %s; money put in "
                       "%s, all settled %s) -- money moved that no listing shows, so its %% may be off by "
                       "up to that." % (x["of"], usd(abs(x["unexplained"])).lstrip("+"),
                                        "more" if x["unexplained"] > 0 else "less", usd(x["now"]).lstrip("+"),
                                        usd(x["money_in"]).lstrip("+"), usd(x["settled"])))
    return out
