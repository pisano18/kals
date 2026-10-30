"""/brief /summary -- the daily briefing: every pot's money today first (the /today top, with its %), then pinbrief's
words for the main account, unchanged (the phone quotes pinbrief, never rebuilds it: one daily summary to keep honest).

v-tg-rebuild step 9 (2026-10-30): Phone.text_brief as a command module (load + render), byte-identical (golden
shadow). The old method's wall covers everything and logs NOTHING, so it is kept here as written (no `fail`: Command.run
would log a traceback). all_bots_day / pace_line are Phone._all_bots_day / Phone._pace_line, copied verbatim with
ctx for self: /today, /yesterday (lane D1, commands/day.py) and the 8 AM alert use the same two -- the integrator keeps
ONE copy (step 10).
"""
import traceback

from botdata.fmt import usd                       # == pinphone.usd (botdata/fmt.py)
from phone.command import Command, declare
from phone.html import Html, esc, i_
from phone.log import log
from pindesk import et_day, et_str


def failed(e):
    return ("Could not build today's briefing: %s\n"
            "Everything else still works -- try /today again, or "
            "/days for the plain numbers." % str(e)[:160])


def load(ctx):
    """{'body': pinbrief's words laid out, 'top': every pot's lines for today ([] = none), 'mw': the main account's
    bots in words} or {'err': exception} (nothing logged, as before)."""
    try:
        import pinbrief
        body = ctx.pp.brief_html(pinbrief.text(pinbrief.brief(ledger=ctx.ledger)))
        top = all_bots_day(ctx, et_day(ctx.now()), "Today")      # 2026-10-26: every pot first, with its %
        if not top:
            return {"body": body, "top": top}
        return {"body": body, "top": top, "mw": ctx.pp.main_words(ctx.active())}
    except Exception as e:                                      # noqa: BLE001
        return {"err": e}


def render(d):
    if "err" in d:
        return failed(d["err"])
    try:
        body, top = d["body"], d["top"]
        if not top:
            return body
        mw = d["mw"]
        return Html("\n".join(top + ["", "🏦 <b>%s (main account)</b>" % esc(mw[:1].upper() + mw[1:]), str(body)]))
    except Exception as e:                                      # noqa: BLE001
        return failed(e)


# ---- from pinphone.Phone._all_bots_day / Phone._pace_line (shared with /today, /yesterday and the 8 AM alert) --------
def all_bots_day(ctx, day, label):
    """/today and /yesterday's top: EVERY bot's money that ET day from Kalshi's books (botstats.all_bots, the /bots
    source): the headline with the % of all pots, a bot-by-bot table (each bot's % of its own bank and its return on
    the bets), the averages with their %. [] when the day is neither today nor yesterday; one warning line when
    botstats fails. (Phone._all_bots_day, verbatim)"""
    P = ctx.pp
    try:
        a = ctx.bs_get("all")
    except Exception:                                        # noqa: BLE001
        log(traceback.format_exc())
        return ["❔ <b>All bots %s: could not be read</b> -- below is the main account only" % esc(label.lower())]
    bs = ctx.bs()
    today = a["today_et"]
    key = "today" if day == today else ("yesterday" if day == bs.shift_day(today, -1) else None)
    if key is None:
        return []
    w = a["total"][key]
    if w["partial"] and not w["markets"]:
        L = ["❔ <b>All bots %s: unknown -- Kalshi could not be read</b>" % esc(label.lower())]
    else:
        L = [P.bs_headline(w, "of all pots", "All bots", when=label.lower())]
    L.append(i_("%s ET%s · every pot, Kalshi's books" % (
        P._day_long(day), (" · %d of %d markets won" % (w["won"], w["markets"])) if w["markets"] else "")))
    if key == "today" and not w["partial"]:
        pace = pace_line(ctx, w["money"], day, w.get("pot"))
        if pace:
            L.append(pace)
    if w["partial"] and w["markets"]:
        L.append("⚠️ PARTIAL: leaves out %s (Kalshi could not be read)" % esc(", ".join(w["missing"])))
    tbl = P.bots_window_table(a, key)
    if tbl:
        L += ["", "📊 <b>By bot</b>"] + tbl
    avg, n = P.all_bots_avg_before(a, day)
    base = w.get("pot")
    dollars = P.dollars

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
    avg30, n30 = P.all_bots_avg_before(a, day, bs.LONG_DAYS) if hasattr(bs, "LONG_DAYS") else (None, 0)
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


def pace_line(ctx, so_far, day, base=None):
    """'📈 Ahead of pace: +$76.44 (+3.3%) so far vs +$20.10 (+0.86%) by 10:45 PM on an average day (last 7)' -- every
    bot, today against the same ET clock on the days before; the % are of all pots at midnight (`base`). None when it
    cannot be worked out (it never costs the rest of the page). (Phone._pace_line, verbatim)"""
    try:
        T = ctx.pp._tgc()
        now = ctx.now()
        b_, _p, rows, miss = T.all_day_markets({"now": now, "pp": ctx.pp,
                                                "bs_getter": ctx.bs_getter, "bs_procs": ctx.bs_procs})
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


COMMAND = declare(Command(
    names=("/brief", "/summary"), section="now", order=70,
    help_line="/brief — the daily briefing: money, what changed, what it did, the market, what to watch",
    chart="days", load=load, render=render))
