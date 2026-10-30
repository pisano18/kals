"""phone/alerts.py -- the alerts that come by themselves: a state change, a recorder going silent (and writing again), low
disk (under 8 GB, again under 6 GB), every new losing close, and yesterday's summary at 8 AM ET. Sends only on a CHANGE.

v-tg-rebuild step 9 (2026-10-30, lane E): Phone.alerts_tick, Phone.daily_alert, disk_alert and the alert_* layouts of
pinphone, moved here VERBATIM (golden: research/golden/shadow_more.py runs the golden alert scripts -- tick/alerts-state,
-recorder, -disk, -loss, -daily -- through tick() and wants the same messages and the same state as Phone.alerts_tick).
Nothing is switched over yet: Phone keeps its own methods until steps 10-11.

STATE. AlertState holds what the tick remembers between calls (last_state, last_rec, seen_losses, last_daily,
disk_level). tick(ctx, st) takes it explicitly; st=None uses ctx.state (the Phone, which has the same five attributes),
so step 10 can call tick(Ctx.from_phone(self)) with the state still on the Phone and step 11 can hand it an AlertState.
`muted` is NOT alert state: it is the runtime's flag that /mute writes (ctx.state.muted), read here at each check.

EVERY ALERT IS LAID OUT by an alert_* function; if that ever fails, the plain words it always had go instead
(fmt_or_plain) -- a layout bug must never swallow an alert. The layouts are looked up as this module's globals at call
time, so a test can plant a failing one (as the old self-test did with pinphone.alert_state_text).

`pp` is the old pinphone module (ctx.pp): the helpers not moved out yet (state_dot, BOT_WORD, main_bot_of, _mkt_short, _f,
main_words, _day_long). Never `import pinphone` here (under --selftest it runs as __main__).
"""
import time
import traceback
from dataclasses import dataclass
from typing import Optional

import pindesk
from botdata.fmt import usd                       # == pinphone.usd
from phone.html import Html, details, esc, norm_money
from phone.log import log
from pindesk import Ledger, et_day, et_day_start, et_str, pct, status_of, story_day, story_loss

# ---- the disk rule (from pinphone: only the alerts use it) ----------------------------------------------------------------
DISK_WARN_GB, DISK_STOP_GB, DISK_REARM_GB = 8.0, 6.0, 9.0
DISK_HARD_STOP_GB = 5.0
DISK_GB_PER_DAY = 4.0                   # OPEN_WORK C1: the recorders write ~4 GB a day
DAILY_AT_S = 8 * 3600                   # the summary of yesterday goes after 8 AM ET


@dataclass
class AlertState:
    """What the alerts tick remembers (the Phone's attributes of the same names until step 11)."""
    last_state: Optional[str] = None     # status_of's state at the last tick (None: not learnt yet -- the first tick)
    last_rec: Optional[str] = None       # 'writing' or 'SILENT: ...'
    seen_losses: Optional[set] = None    # the losing closes already known
    last_daily: Optional[str] = None     # the ET day whose 8 AM summary went (or was due at startup)
    disk_level: int = 0                  # disk_alert(): 0 armed, 8 / 6 = that line already sent


def disk_alert(level, disk_gb):                 # from pinphone.disk_alert
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


# ---- the layouts (from pinphone, verbatim; `pp` where an unmoved pinphone helper is used) ------------------------------
def alert_state_text(prev, state, hl, det, pp):
    """STATE CHANGED: the words alerts_tick always sent, under a coloured headline."""
    body, _nl, ev = str(det).rpartition("\n")
    if not body:
        body, ev = ev, ""
    return Html("%s <b>STATE CHANGED: %s -&gt; %s</b>\n<b>%s</b>\n%s%s" % (
        pp.state_dot(state), esc(prev), esc(state), esc(hl), esc(body), ("\n<i>%s</i>" % esc(ev)) if ev else ""))


def alert_recorder_text(rec, minutes):
    return Html("⚠️ <b>RECORDER %s</b> -- nothing written for %d+ min.\nThat tape cannot be recreated later. "
                "If the bot is also BLIND, the problem is the connection to Kalshi, not our programs."
                % (esc(rec), minutes))


def alert_recorder_back_text(was):
    return Html("✅ <b>RECORDERS WRITING AGAIN</b> (was %s)" % esc(was))


def disk_alert_html(msg, level):
    """disk_alert()'s words (unchanged, the self-test pins them) with the first sentence as a headline."""
    msg = str(msg)
    if level == 8:
        head, sep, rest = msg.partition(". ")
        head += "." if sep else ""
    else:
        head, _sep, rest = msg.partition(" -- ")
    return Html("%s <b>%s</b>%s" % ("🚨" if level == 6 else "⚠️", esc(head), ("\n" + esc(rest)) if rest else ""))


def alert_loss_text(ledger, close, net, legs, pp):
    """A new losing close: story_loss's facts (pindesk), laid out -- the loss as the headline, one line a
    leg, why it hurts. The desktop's 'double-click a row' hint is left out: there is no row on a phone.
    2026-10-26 (operator: "anywhere that trades or transactions are listed list the account or which bot"): the headline
    names the bot and its account; each leg names its bot too when one close holds both main-account bots' legs."""
    b0 = ledger.bank_at(close - 1) if close else None
    whose = [pp.BOT_WORD.get(pp.main_bot_of(l_["tk"]), "?") for l_ in legs]
    who = list(dict.fromkeys(whose))
    L = ["🔴 <b>LOSS %s%s</b> · %s (main account) · the quarter-hour closing %s ET on %s" % (
        esc(usd(net)), (" (%s of the bank)" % esc(pct(net / b0))) if b0 else "", esc(" + ".join(who) or "?"),
        esc(et_str(close)), esc(et_str(close, "%b %d")))]
    for l_, w in zip(legs, whose):
        n = ledger.contracts_for(l_["tk"]) or pp._f(l_.get("n"))   # a coin-race leg is not in the pin bot's orders
        L.append("• %s<b>%s</b> %s at %.1fc, %g contracts → settled %s: <b>%s</b>" % (
            (esc(w) + " · ") if len(who) > 1 else "", esc(pp._mkt_short(l_["tk"])), esc(str(l_["want"]).upper()),
            100 * float(l_["cost"] or 0), n, esc(str(l_["result"]).upper()), esc(usd(l_["pnl"]))))
    L.append("")
    L.append("<b>WHY IT HURTS:</b> <i>a win here makes 2c to 4c a contract; a loss costs most of the 96c-98c "
             "paid. So one losing close wipes out many winning ones.</i>")
    L.append("<i>/losses for the list, /today for the day.</i>")
    return Html("\n".join(L))


def alert_daily_text(ledger, d, now):
    """The 8 AM summary: story_day's own lines (pindesk), under a headline with yesterday's money and its
    % of the bank at the start of the day -- the same two numbers its MONEY line carries."""
    s = Ledger.summary(ledger.settled_on(d))
    b0 = ledger.bank_at(et_day_start(d))
    lines = story_day(ledger, d, now=now).split("\n")
    body = [x for x in lines[1:] if x.strip()]
    out = ["☀️ <b>YESTERDAY %s (%s)</b> · %s" % (esc(usd(s["net"])), esc(pct((s["net"] / b0) if b0 else None)),
                                                  esc(time.strftime("%a %b %d", time.strptime(d, "%Y-%m-%d"))))]
    for x in body:
        head, sep, rest = norm_money(x).partition(": ")
        out.append(("<b>%s:</b> %s" % (esc(head), esc(rest))) if sep and head.isupper() else esc(norm_money(x)))
    return Html("\n".join(out))


def fmt_or_plain(build, plain):
    """An alert laid out (build()), or -- if laying it out fails -- the plain words it always had (plain()),
    so a layout bug can never swallow an alert."""
    try:
        return build()
    except Exception:                                           # noqa: BLE001
        log("alert layout failed, sending the plain words: %s" % traceback.format_exc()[-400:])
        return plain()


def daily_alert(ctx, d, now, all_bots_day=None):
    """The 8 AM summary (Phone.daily_alert, 2026-10-26 screen pass): yesterday over EVERY pot -- /yesterday's headline (its
    % of all pots), the bot-by-bot table (each bot's % of its bank) and the averages -- then the main account's story
    (story_day, pindesk) behind a tap. The old main-account-only summary when botstats cannot be read.
    all_bots_day(d, title) -> [lines] is /today's every-bot block (None = phone.commands.day.all_bots_day on this ctx:
    the ONE copy, v-tg-rebuild step 10)."""
    pp = ctx.pp
    base = alert_daily_text(ctx.ledger, d, now)
    if all_bots_day is None:
        from phone.commands import day as _day
        top = _day.all_bots_day(ctx, d, "Yesterday")
    else:
        top = all_bots_day(d, "Yesterday")
    if not top or top[0].startswith("❔"):
        return base
    return Html("\n".join(["☀️ <b>YESTERDAY, %s</b> · every bot" % esc(pp._day_long(d))] + top + [
        "", details(str(base).split("\n"), "🏦 %s (main account): the day's story -- tap"
                    % (lambda w: w[:1].upper() + w[1:])(pp.main_words(ctx.active())))]))


def tick(ctx, st=None, all_bots_day=None):
    """Phone.alerts_tick, verbatim: called every poll cycle; sends only on CHANGE. Returns what it sent.
    ctx: the Ctx of the paired chat (Ctx.from_phone(phone)): chat_id, ledger, health(), now(), say, active(), pp, and
    state.muted. st: the AlertState (None = ctx.state, the Phone)."""
    st = ctx.state if st is None else st
    run = ctx.state                                  # the runtime's `muted` (written by /mute)
    pp = ctx.pp
    if ctx.chat_id is None:
        return []
    sent = []
    ctx.ledger.refresh()
    h = ctx.health()
    state, hl, det, _c = status_of(h)
    now = ctx.now()
    today = et_day(now)
    if st.last_state is None:
        # first tick after a (re)start: learn, do not announce. A daily
        # summary already due today is marked done, or every restart of
        # this program would re-send it.
        if (now - et_day_start(today)) >= DAILY_AT_S:
            st.last_daily = today
    if st.last_state is not None and state != st.last_state and not run.muted:
        prev = st.last_state
        msg = fmt_or_plain(lambda: alert_state_text(prev, state, hl, det, pp),
                           lambda: "STATE CHANGED: %s -> %s\n%s\n%s" % (prev, state, hl, det))
        ctx.say(msg)
        sent.append(msg)
    st.last_state = state
    # THE RECORDERS. 2026-09-21 the Kalshi recorder was alive and deaf for
    # 4 h 47 min and nothing told the operator; the tape from those hours
    # is gone for good. Same rule as the bot: send only on a CHANGE.
    silent = [n for n, k in (("Kalshi recorder", "kalshi_ok"),
                             ("Exchange recorder", "feeds_ok"))
              if h.get(k) is False]
    rec = ("SILENT: " + ", ".join(silent)) if silent else "writing"
    if st.last_rec is not None and rec != st.last_rec and not run.muted:
        was = st.last_rec
        if silent:
            msg = fmt_or_plain(lambda: alert_recorder_text(rec, pindesk.REC_FRESH_S // 60),
                               lambda: ("RECORDER %s -- nothing written for %d+ min. That tape "
                                        "cannot be recreated later. If the bot is also BLIND, "
                                        "the problem is the connection to Kalshi, not our "
                                        "programs." % (rec, pindesk.REC_FRESH_S // 60)))
        else:
            msg = fmt_or_plain(lambda: alert_recorder_back_text(was),
                               lambda: "RECORDERS WRITING AGAIN (was %s)" % was)
        ctx.say(msg)
        sent.append(msg)
    st.last_rec = rec
    # THE DISK. Tracked even when muted, so an unmute does not replay it.
    st.disk_level, dmsg = disk_alert(st.disk_level, h.get("disk_gb"))
    if dmsg and not run.muted:
        level = st.disk_level
        msg = fmt_or_plain(lambda: disk_alert_html(dmsg, level), lambda: dmsg)
        ctx.say(msg)
        sent.append(msg)
    losses = ctx.ledger.losing_closes()
    keys = {k for k, _n, _l in losses}
    if st.seen_losses is None:
        st.seen_losses = keys
    else:
        new = [x for x in losses if x[0] not in st.seen_losses]
        st.seen_losses = keys
        for close, net, legs in new:
            if not run.muted:
                msg = fmt_or_plain(lambda: alert_loss_text(ctx.ledger, close, net, legs, pp),
                                   lambda: "LOSS " + story_loss(ctx.ledger, close, net, legs))
                ctx.say(msg)
                sent.append(msg)
    if (now - et_day_start(today)) >= DAILY_AT_S and st.last_daily != today and not run.muted:
        st.last_daily = today
        yday = et_day(now - 86400)
        msg = fmt_or_plain(lambda: daily_alert(ctx, yday, now, all_bots_day),
                           lambda: "YESTERDAY\n" + story_day(ctx.ledger, yday, now=now))
        ctx.say(msg)
        sent.append(msg)
    return sent
