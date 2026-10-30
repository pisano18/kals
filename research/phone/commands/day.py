"""/today, /yesterday -- every bot's money that ET day from Kalshi's books (the /bots source): the headline with its %
of all pots, the pace against an average day (today), a bot-by-bot table, the 7- and 30-day averages; the main
account's own closes, fills and hours behind a tap. When the day is neither today nor yesterday on botstats' clock:
the main account's day alone (and yesterday beside today, for scale).

v-tg-rebuild step 9, lane D1 (2026-10-30): Phone.text_day, _all_bots_day, _pace_line and day_html as a command module
(load + render), byte-identical (golden shadow). day_data / day_lines (Phone.day_html split into its reads and its
words, with Phone._staked) are shared with /status and /days.
"""
import traceback

from botdata.fmt import dollars, usd                  # == pinphone.dollars / usd
from phone.command import Command, declare
from phone.html import Html, details, esc, i_, spark
from phone.log import log
from phone.render.botcards import (_day_long, _nof, all_bots_avg_before, bots_window_table, bs_headline, dot,
                                   main_shared, main_sharers, main_words, ret)
from pindesk import Ledger, et_day, et_day_start, et_str, hours_up_et_day, pct


# ---- Phone.day_html, split: day_data (the reads) + day_lines (the words) ----------------------------------------------
def staked(ctx, net, day=None):
    """Phone._staked: what the bets of one ET day (None = every day) cost, from Kalshi's books (the /stats source:
    cost + fees of every main-account market) -- or None when that source's money for the same window is not the `net`
    shown (then a 'return on staked' would mix two sources, so none is shown)."""
    try:
        ms = [m for m in ctx.markets().values() if day is None or m["day"] == day]
    except Exception:                                       # noqa: BLE001
        return None
    if not ms:
        return None
    st = ctx.pp.window_stats(ms, {})
    return st["risked"] if abs(st["net"] - net) <= 0.011 else None


def day_data(ctx, rows, day=None):
    """Everything Phone.day_html read, in its order: the summary of `rows`, the bank at the day's start (all time: the
    money put in), what the bets cost (Kalshi's books), the pin bot's fills, the hours up, the closes."""
    s = Ledger.summary(rows)
    d = {"s": s, "day": day}
    if day:
        d["b0"] = ctx.ledger.bank_at(et_day_start(day))
    else:
        d["dep"] = ctx.ledger.deposited()
    if s["closes"]:
        d["staked"] = staked(ctx, s["net"], day) if s["markets"] else None
    if day:
        d["fs"] = Ledger.fill_stats(ctx.ledger.fills_on(day))
        try:
            d["up"] = hours_up_et_day(day, ctx.now() if day == et_day(ctx.now()) else et_day_start(day) + 86400)
        except Exception:                            # noqa: BLE001
            d["up"] = None
        d["closes"] = Ledger.by_close(rows)
    return d


def day_lines(d, label, pp):
    """Phone.day_html's words from day_data: the money and its % (of the bank at the start of the ET day; all time, of
    the money put in) as the headline; closes won, the return on what the bets cost, fills, hours, the sparkline.
    `pp` = the old pinphone module (pct_of). Html lines."""
    s, day = d["s"], d["day"]
    if day:
        b0 = d["b0"]
        r = (s["net"] / b0) if b0 else None
        base = ("%% of the bank = of the %s it held at the start of the ET day" % dollars(b0)) if b0 else None
        what = "of the bank"
    else:
        dep = d["dep"]
        r = (s["net"] / dep) if dep else None
        base = None
        what = ("on the %s put in" % dollars(dep)) if dep else ""
    L = ["%s <b>%s %s (%s%s)</b>" % (dot(s["net"]), esc(label), esc(usd(s["net"])), esc(pct(r)),
                                       (" " + esc(what)) if r is not None and what else "")]
    if s["closes"]:
        staked_ = d["staked"]
        L.append("<b>%d of %d</b> closes won (<b>%s</b>), %d lost (%.1f%%) · %s%s" % (
            s["won"], s["closes"], pp.pct_of(s["won"], s["closes"], 1), s["lost"], s["loss_rate"],
            esc(_nof(s["markets"], "bet")),
            (" · <b>%s</b> on the %s staked" % (esc(ret(s["net"], staked_, 2)), esc(dollars(staked_))))
            if staked_ else ""))
    else:
        L.append("No settled bets.")
    if day:
        fs, up = d["fs"], d["up"]
        L.append("Pin bot: %s, %s contracts%s" % (            # its own orders; the coin race's are in /race
            esc(_nof(fs["fills"], "fill")), "{:,.0f}".format(fs["contracts"] or 0),
            (" · %d of %d orders filled nothing (%s)" % (fs["zero"], fs["orders"], pp.pct_of(fs["zero"], fs["orders"])))
            if fs["orders"] else ""))
        if up:
            L.append("%.1f h up · <b>%s</b> an hour" % (up, esc(usd(s["net"] / up))))
        closes = d["closes"]
        if len(closes) >= 3:
            run, cum = [], 0.0
            for k in sorted(closes):
                cum += closes[k]
                run.append(cum)
            L.append("Close by close, the running total: <code>%s</code>" % esc(spark(run)))
    if base and r is not None:
        L.append(i_(base))
    return L


# ---- Phone._pace_line, split ------------------------------------------------------------------------------------------
def pace_data(ctx, so_far, day, base=None):
    """The numbers of '📈 Ahead of pace ...' (every bot, today against the same ET clock on the days before), or None
    when they cannot be worked out (logged; it never costs the rest of /today)."""
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
        # 2026-10-29: the 30-day average day at the same clock after the 7-day one (ahead / behind stays the 7-day's)
        _sf30, avg30, n30 = T.by_now(rows, b_, day, now, getattr(b_, "LONG_DAYS", 0))
        return {"bs": b_, "now": now, "so_far": so_far, "day": day, "base": base, "avg": avg, "n": n,
                "avg30": avg30, "n30": n30}
    except Exception:                                       # noqa: BLE001
        log(traceback.format_exc())
        return None


def pace_line(p):
    """'📈 Ahead of pace: +$76.44 (+3.3%) so far vs +$20.10 (+0.86%) by 10:45 PM on an average day (last 7)' -- the % are
    of all pots at midnight (`base`). None when pace_data had none."""
    if p is None:
        return None
    b_, base, so_far, avg, n, avg30, n30, day, now = (p["bs"], p["base"], p["so_far"], p["avg"], p["n"], p["avg30"],
                                                      p["n30"], p["day"], p["now"])
    ahead = so_far >= avg

    def sh(x):
        return (" (%s)" % b_.pot_pct_txt(100.0 * x / base)) if base else ""
    more = (" · last %d: %s%s" % (n30, usd(avg30), sh(avg30))) if avg30 is not None and n30 > n else ""
    return "%s <b>%s</b>: %s%s so far vs %s%s by %s on an average day (last %d)%s" % (
        "📈" if ahead else "📉", "Ahead of pace" if ahead else "Behind pace", esc(usd(so_far)), esc(sh(so_far)),
        esc(usd(avg)), esc(sh(avg)),
        esc(et_str(b_.day_start(day) + (max(0.0, now - b_.day_start(day)) // 900) * 900)), n, esc(more))


# ---- Phone._all_bots_day, split -------------------------------------------------------------------------------------
def top_data(ctx, day):
    """The all-bots top's reads: {'failed': True} when botstats failed (logged); None when the day is neither today nor
    yesterday on botstats' clock (no top); else {'a', 'bs', 'key', 'w', 'pace'}."""
    try:
        a = ctx.bs_get("all")
    except Exception:                                        # noqa: BLE001
        log(traceback.format_exc())
        return {"failed": True}
    bs = ctx.bs()
    today = a["today_et"]
    key = "today" if day == today else ("yesterday" if day == bs.shift_day(today, -1) else None)
    if key is None:
        return None
    w = a["total"][key]
    pace = None
    if key == "today" and not w["partial"]:
        pace = pace_data(ctx, w["money"], day, w.get("pot"))
    return {"a": a, "bs": bs, "key": key, "w": w, "pace": pace}


def top_lines(t, day, label):
    """Phone._all_bots_day's lines from top_data."""
    if t.get("failed"):
        return ["❔ <b>All bots %s: could not be read</b> -- below is the main account only" % esc(label.lower())]
    a, bs, key, w = t["a"], t["bs"], t["key"], t["w"]
    if w["partial"] and not w["markets"]:
        L = ["❔ <b>All bots %s: unknown -- Kalshi could not be read</b>" % esc(label.lower())]
    else:
        L = [bs_headline(w, "of all pots", "All bots", when=label.lower())]
    L.append(i_("%s ET%s · every pot, Kalshi's books" % (
        _day_long(day), (" · %d of %d markets won" % (w["won"], w["markets"])) if w["markets"] else "")))
    if key == "today" and not w["partial"]:
        pace = pace_line(t["pace"])
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


# ---- the command ------------------------------------------------------------------------------------------------------
def load(ctx):
    """Phone.text_day's reads, in its order, for /today (today's ET day) or /yesterday (the one before)."""
    if ctx.cmd == "/yesterday":
        day, label = et_day(ctx.now() - 86400), "Yesterday"
    else:
        day, label = et_day(ctx.now()), "Today"
    d = {"day": day, "label": label, "top": top_data(ctx, day)}
    if d["top"] is not None:
        d["mw"] = main_words(ctx.active())
        settled = ctx.ledger.settled_on(day)
        d["main_label"] = main_shared(ctx.active()).capitalize() if main_sharers(ctx.active()) else "Main account"
        d["main"] = day_data(ctx, settled, day)
        return d
    d["main"] = day_data(ctx, ctx.ledger.settled_on(day), day)
    d["yesterday"] = None
    if day == et_day(ctx.now()):                          # /today: yesterday beside it, for scale
        y = et_day(ctx.now() - 86400)
        s = Ledger.summary(ctx.ledger.settled_on(y))
        d["yesterday"] = (s, ctx.ledger.bank_at(et_day_start(y)))
    return d


def render(d, ctx):
    day, label = d["day"], d["label"]
    if d["top"] is not None:
        top = top_lines(d["top"], day, label)
        # inside the tap's quote: no <code> (Telegram refuses code inside a blockquote -- tg_html_problems)
        mw = d["mw"]
        L = [x.replace("<code>", "").replace("</code>", "") for x in day_lines(d["main"], d["main_label"], ctx.pp)]
        return Html("\n".join(top + ["", details(L, "🏦 %s (main account): closes, fills, "
                                                    "hours up -- tap" % (mw[:1].upper() + mw[1:])),
                                     i_("each bot in full: /bots · the week: /days")]))
    L = day_lines(d["main"], label, ctx.pp)
    if d["yesterday"] is not None:
        s, b0 = d["yesterday"]
        L.append(i_("Yesterday %s (%s) · /days for the week" % (usd(s["net"]), pct((s["net"] / b0) if b0 else None))))
    return Html("\n".join(L))


COMMAND = declare(Command(
    names=("/today", "/yesterday"), section="money", order=10,
    help_line="/today · /yesterday — every bot's money that day: % of all pots, and a table with each bot's % of its "
              "bank",
    chart={"/today": "today", "/yesterday": "yesterday"}, load=load, render=render))
