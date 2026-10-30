"""/funds (/bank /accounts), the WORDS: the grand total, a one-line-an-account table, idle money, then each account's
cash, open bets, bet size and its last FUNDS_DAYS ET days (funds_text -> _funds_page), shrunk to fit one message.

v-tg-rebuild step 9 (2026-10-30, lane D4): MOVED VERBATIM out of research/pinphone.py, which re-exports every name here.
The only edits: imports instead of pinphone's globals (usd / _nof from botdata.fmt, the HTML helpers from phone.html,
the readers from read.py); pct_of is botdata.fmt's since rebuild step 12 (it was a verbatim copy).
"""
import time

import bots as _bots
import pinday
from botdata.fmt import nof as _nof, pct_of, usd                 # pct_of: botdata.fmt's since step 12
from phone.html import MAX_LEN, Html, details, elines, esc, i_, pre, table
from phone.commands.funds.read import (FUNDS_BOOKS, FUNDS_DAYS, FUNDS_SHOW_DAYS, FUNDS_WHAT, _bs, _pool_name,  # noqa: F401
                                       _usd2, funds_books, funds_days, funds_what)


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
            what = "unknown (no bot or pool in the registry, research/bots, names it)"
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


# ---- the command's words ------------------------------------------------------------------------------------------------
def render(d):
    return funds_text(d["f"], d["sizes"], d["now"], d["hist"], active=d["active"])


def fail(e):
    """Phone.text_funds' wall: any failure costs this command only."""
    return ("Could not build /funds: %s\nEverything else still works -- /bots shows each bot pot's "
            "cash." % str(e)[:200])
