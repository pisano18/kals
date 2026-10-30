"""/status (/s) -- is it trading, with the evidence: the desktop banner's state and why, the main account's bank and
bet size, every pot together (/bots), the main account's day, every bot's day (/today), the pin bot's open bets, the
watchdog, recorders and disk. Step 12 (lane Q): a bot that is DOWN (not running, no stop file) gets one warning line at
the top (phone/monitor.py down_lines).

v-tg-rebuild step 9, lane D1 (2026-10-30): Phone.text_status as a command module (load + render), byte-identical (golden
shadow). No wall around the whole (as before); each of the two botstats lines keeps its own: an error there costs only
that line, the traceback logged.
"""
import traceback

import pinflat
from botdata.fmt import dollars, usd                  # == pinphone.dollars / usd
from phone.command import Command, declare
from phone.commands.day import day_data, day_lines
from phone.html import Html, esc, i_
from phone.log import log
from phone import monitor as _monitor
from phone.render.botcards import _bs, main_shared, main_sharers, main_words
from pindesk import close_et, coin, et_day, status_of


def _all_bots(ctx):
    """Phone._bs_get('all'), or None when it fails (logged, as the old line's wall did)."""
    try:
        return ctx.bs_get("all")
    except Exception:                                       # noqa: BLE001
        log(traceback.format_exc())
        return None


def load(ctx):
    """Phone.text_status's reads, in its order."""
    down = _monitor.down_lines(ctx)         # step 12 (lane Q): a DOWN bot's warning line at the top
    h = ctx.health()
    state, hl, det, _c = status_of(h)
    b = ctx.ledger.bank()
    dep = ctx.ledger.deposited()
    d = {"h": h, "state": state, "hl": hl, "det": det, "b": b, "dep": dep, "down": down}
    if b:
        d["mw"] = main_words(ctx.active())
        d["a1"] = _all_bots(ctx)
    today = et_day(ctx.now())
    settled = ctx.ledger.settled_on(today)
    label = ("%s today" % main_shared(ctx.active()).capitalize()) if main_sharers(ctx.active()) else "Main account today"
    d["day"], d["day_label"] = day_data(ctx, settled, today), label
    d["a2"] = _all_bots(ctx)
    opn = pinflat.positions(ctx.ledger.newest_rows) if h["alive"] else {}
    d["open"] = [(t, ctx.ledger.contracts_for(t)) for t in opn]
    return d


def render(d, ctx):
    h, b = d["h"], d["b"]
    body, _nl, ev = d["det"].rpartition("\n")
    if not body:
        body, ev = ev, ""
    lines = list(d.get("down") or []) + ["%s <b>%s</b>" % (ctx.pp.state_dot(d["state"]), esc(d["hl"])), esc(body)]
    if ev:
        lines.append(i_(ev))
    if b:
        # 2026-10-26: was 'Bank $1,340.77 (+19.34% on the $1,123.46 put in)' -- the main account's bank against
        # the money put into EVERY pot (about $1,024 of it now sits in the other bots' pots), so the % read low
        lines.append("")
        lines.append("🏦 <b>Main account %s</b> (%s) · bet size %g contracts" % (
            esc(dollars(b["bank"])), esc(d["mw"]), b.get("size") or 0))
        a = d["a1"]
        if a is not None:
            try:
                at, allc = a["total"]["all_time"], a["balances"].get("all")
                if allc is not None:
                    lines.append("💼 All pots %s%s · /bots" % (esc(dollars(allc)), (
                        " · all time <b>%s</b> (<b>%s</b> on the %s put in)" % (
                            esc(usd(at["money"])), esc(_bs().pot_pct_txt(at["pot_pct"])), esc(dollars(at["pot"]))))
                        if at.get("pot_pct") is not None and at.get("pot") else ""))
            except Exception:                                   # noqa: BLE001
                log(traceback.format_exc())
    lines.append("")
    lines += day_lines(d["day"], d["day_label"], ctx.pp)
    a = d["a2"]
    if a is not None:
        try:
            t_ = a["total"]["today"]
            if t_["markets"]:
                lines.append("🤖 All bots today <b>%s</b>%s · /today" % (esc(usd(t_["money"])), (
                    " (<b>%s</b> of all pots)" % esc(_bs().pot_pct_txt(t_["pot_pct"]))) if t_.get("pot_pct") is not None else ""))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
    if d["open"]:
        lines.append("")
        lines.append("📂 <b>Pin bot open:</b> " + esc(", ".join("%s %s closes %s" % (coin(t), "x%g" % n, close_et(t))
                                                              for t, n in d["open"])))
    wd = h.get("watchdog_s")
    rec = "both writing" if (h.get("kalshi_ok") and h.get("feeds_ok")) else "CHECK RECORDERS"
    lines.append("")
    lines.append("🖥 Watchdog %s · recorders %s · disk %.1f GB free" % (
        ("ok, %ds ago" % wd) if wd is not None and wd < 120 else "<b>NOT RUNNING</b>",
        esc(rec) if rec == "both writing" else "<b>%s</b>" % esc(rec), h.get("disk_gb") or 0))
    return Html("\n".join(lines))


COMMAND = declare(Command(
    names=("/status", "/s"), section="now", order=10,
    help_line="/status — is it trading, with the evidence",
    chart="status", load=load, render=render))
