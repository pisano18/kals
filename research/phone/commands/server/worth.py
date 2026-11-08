"""/server's "worth of the move" section: what the server has earned since the bots moved to it (the /speed estimate of
the pin fills speed added), what it has cost (the price-list estimate since the instance's first boot), the net and a
day's pace; then the two machines' records (closes the pin bot missed, connection hiccups: the laptop's last 14 days
against the server's whole life) and what the laptop's stop rate would have cost here (a guess, shown but not added).

2026-11-05 (operator: "How much has the server earned us so far that we wouldn't have gotten if we didn't migrate? And
make that trackable in slash server telegram"). Reads the Ledger's order rows (already in this process) and the pin
bot's own logs through tail_rows (once, then only the new bytes); nothing is asked of Kalshi or AWS. Every figure says
what it is: the speed part is /speed's own estimate (its method is spelled out there), the cost is the price list, the
record is counted from the logs, and the laptop's would-have-cost is a guess about a machine that no longer runs the
bots. Written so a failure in any part names itself on the page and the rest of /server still shows.
"""
import os
import time

import pindesk
import pinday
from botdata import dirlist as _dirlist
import logfiles                                                      # archived pin logs (log_rotate.py)
from botdata.fmt import cnt as _cnt, dollars, dot, nof as _nof, of100 as _of100, pct_of, ret, usd
from phone.html import esc, i_
from phone.commands.server.aws import AWS_BILLED_FROM_EPOCH, aws_estimate
from phone.commands.speed import (SERVER_SINCE_EPOCH, SPEED_HOME_DAYS, SPEED_MIN_ORDERS, _et_at, _span_words,
                                  _speed_win, _usd4, pin_speed_orders, speed_estimate, speed_pin_money, speed_stats,
                                  tail_rows)

WORTH_CLOSE_S = 900                      # a 15-minute close
WORTH_GAP_S = 20 * 60                    # no close_summary row for longer than this: the pin bot was not watching
# Kalshi's weekly maintenance: every THURSDAY the 15-minute markets pause for about 2 h 15 min from 3:00 AM ET (seen
# Thu 10-15, 10-22, 10-29 at 07:00Z and Thu 11-05 at 08:00Z, after the clocks went back: no close on either machine;
# Kalshi keeps Eastern time). A gap that starts in this window (Eastern clock) and lasts under 3 h is Kalshi's, not the
# machine's, and is left out on both sides.
MAINT_WDAY = 3                           # tm_wday of the Eastern clock: Monday 0 -> Thursday 3
MAINT_FROM_S, MAINT_TO_S, MAINT_MAX_S = 2 * 3600 + 30 * 60, 3 * 3600 + 30 * 60, 3 * 3600   # 2:30-3:30 AM ET start
# the asked-size buckets of the size-matched estimate (the server's orders are bigger than the laptop's were: matching
# by size compares like with like; the bucket edges are the ones the 11-05 study used)
WORTH_BUCKETS = ((0, 25), (25, 60), (60, 150), (150, float("inf")))


def is_maintenance(start, length_s):
    """True for a gap that is Kalshi's Thursday maintenance window (Eastern clock), not a machine's stop."""
    tm = time.gmtime(float(start) + pinday.et_offset(float(start)))
    day_s = tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec
    return tm.tm_wday == MAINT_WDAY and MAINT_FROM_S <= day_s <= MAINT_TO_S and length_s <= MAINT_MAX_S


def pin_rows(results, kind, t0):
    """Every `kind` row of the pin logs that could hold a row at or after t0 (a log last written before t0 cannot)."""
    out = []
    for p in logfiles.glob(os.path.join(results, "pinrun-live-*.jsonl"), globber=_dirlist.glob):
        try:
            if os.path.getmtime(p) < t0:
                continue
        except OSError:
            continue
        out.extend(tail_rows(p, "kind", kind))
    return out


def _times(rows, t0, t1):
    out = set()
    for r in rows:
        t = pindesk.parse_t(r.get("t"))
        if t is not None and t0 <= t < t1:
            out.add(t)
    return sorted(out)


def watch_record(results, t0, t1):
    """One machine's record over [t0, t1): the closes the pin bot watched (one close_summary row each), the gaps longer
    than WORTH_GAP_S between them -- the window's edges included, Kalshi's Thursday maintenance left out -- with the
    closes inside them, their hours and the longest; and the connection hiccups (conn_event rows). t1 is `now` for a
    window still open, so a bot down right now shows as a gap."""
    ts = _times(pin_rows(results, "close_summary", t0), t0, t1)
    gaps, maint = [], 0
    edges = [t0] + ts + [t1] if ts else []
    for a, b in zip(edges, edges[1:]):
        if b - a > WORTH_GAP_S:
            if is_maintenance(a, b - a):
                maint += 1
                continue
            gaps.append((a, b - a))
    missed = sum(max(0, int(round(d / float(WORTH_CLOSE_S))) - 1) for a, d in gaps)
    conn = len(_times(pin_rows(results, "conn_event", t0), t0, t1))
    return {"closes": len(ts), "gaps": len(gaps), "missed": missed, "hours": sum(d for a, d in gaps) / 3600.0,
            "longest": max(gaps, key=lambda g: g[1]) if gaps else None, "maint": maint, "conn": conn,
            "span_s": t1 - t0}


def matched_extra(home, srv):
    """The extra contracts the server filled, matched by asked size: for each WORTH_BUCKETS band, (server got/asked -
    home got/asked) x the contracts the server asked in that band; bands with no orders on one side add nothing."""
    extra, bands = 0.0, []
    for lo, hi in WORTH_BUCKETS:
        h = speed_stats([o for o in home if o.get("asked") and lo < o["asked"] <= hi])
        s = speed_stats([o for o in srv if o.get("asked") and lo < o["asked"] <= hi])
        if h["got_share"] is None or s["got_share"] is None:
            bands.append((lo, hi, h, s, None))
            continue
        e = (s["got_share"] - h["got_share"]) * s["asked"]
        extra += e
        bands.append((lo, hi, h, s, e))
    return extra, bands


def server_worth(orders, results, now, bank=None):
    """Everything the section shows, worked out. Never raises for a missing part: a part that cannot be worked is None
    (its line says so)."""
    since = SERVER_SINCE_EPOCH
    h0 = since - SPEED_HOME_DAYS * 86400
    pins = pin_speed_orders(orders)
    home, srv = _speed_win(pins, h0, since), _speed_win(pins, since, now + 1)
    hs, ss = speed_stats(home), speed_stats(srv)
    money = speed_pin_money(results, srv, since)
    est = speed_estimate(hs, ss, money, now - since)
    hourly = aws_estimate(now)["hourly"]
    cost = hourly * max(0.0, now - AWS_BILLED_FROM_EPOCH) / 3600.0
    days = (now - since) / 86400.0
    net = (est["usd"] - cost) if est["usd"] is not None else None
    m_extra, bands = matched_extra(home, srv)
    matched = (m_extra * money["per"]) if money["per"] is not None else None
    rec_home, rec_srv = watch_record(results, h0, since), watch_record(results, since, now + 1)
    per_close = (money["usd"] / rec_srv["closes"]) if rec_srv["closes"] else None
    home_total = rec_home["closes"] + rec_home["missed"]
    stop_rate = (rec_home["missed"] / float(home_total)) if home_total else None
    laptop_style = (stop_rate * (rec_srv["closes"] + rec_srv["missed"]) * per_close) \
        if stop_rate is not None and per_close is not None else None
    return {"since": since, "home_from": h0, "now": now, "days": days, "home": hs, "srv": ss, "money": money,
            "est": est, "hourly": hourly, "cost": cost, "net": net,
            "per_day": (net / days) if net is not None and days >= 1.0 else None, "bank": bank,
            "matched_extra": m_extra, "matched": matched, "bands": bands,
            "rec_home": rec_home, "rec_srv": rec_srv, "per_close": per_close, "stop_rate": stop_rate,
            "laptop_style": laptop_style}


def _signed_cnt(x):
    return ("+" if x > 0 else "-" if x < 0 else "") + _cnt(abs(x))


def worth_lines(w, min_orders=None):
    """The section's lines (HTML). `w` = server_worth's dict, or {"err": why} when it could not be worked."""
    min_orders = SPEED_MIN_ORDERS if min_orders is None else min_orders
    if not isinstance(w, dict) or w.get("err"):
        return ["🏆 <b>Worth of the move</b>: could not be worked%s. /speed has the fill figures."
                % ((" (%s)" % esc(w["err"])) if isinstance(w, dict) and w.get("err") else "")]
    est, s, h, mo, bank = w["est"], w["srv"], w["home"], w["money"], w.get("bank")
    early = s["n"] < min_orders
    span = _span_words(w["now"] - w["since"])
    L = []
    if est["usd"] is None:
        L.append("🏆 <b>Worth of the move: too early to tell</b> (%s on the server, %s; %s)" % (
            esc(_nof(s["n"], "pin order")), esc(span), esc(est["why"] or "no estimate yet")))
    else:
        of_bank = ret(w["net"], bank, 2) if bank else ""
        L.append("🏆 <b>Worth of the move: %s %s net so far</b> (%s on the server: speed added %s in pin fills, the "
                 "server cost %s)%s%s · an estimate, not a proof%s" % (
                     dot(w["net"]), esc(usd(w["net"])), esc(span), esc(usd(est["usd"])), esc(dollars(w["cost"])),
                     (" · about <b>%s a day</b>" % esc(usd(w["per_day"]))) if w["per_day"] is not None else "",
                     (" · %s of the main account's %s bank" % (esc(of_bank), esc(dollars(bank)))) if of_bank else "",
                     (" · ⏳ too early: %s, the bar is %d" % (esc(_nof(s["n"], "order")), min_orders)) if early else ""))
        L.append("Speed: (%s%% - %s%% got of asked) x %s asked here = %s extra contracts x %s each = <b>%s</b>, the "
                 "/speed figure%s" % (
                     _of100(s["got_share"]), _of100(h["got_share"]), _cnt(s["asked"]), _signed_cnt(est["extra"]),
                     esc(_usd4(mo["per"])), esc(usd(est["usd"])),
                     ("; matched by order size (the server's orders are bigger) it reads <b>%s</b>" % esc(usd(w["matched"])))
                     if w.get("matched") is not None else ""))
    L.append("Cost: %s a day from the price list since the first boot (%s) = <b>%s</b>; AWS's own bill needs the "
             "billing role (<code>/server help</code>)" % (
                 esc(dollars(w["hourly"] * 24.0)), esc(_et_at(AWS_BILLED_FROM_EPOCH)), esc(dollars(w["cost"]))))
    rh, rs = w["rec_home"], w["rec_srv"]
    if not rh["closes"] and not rs["closes"]:
        L.append("Record: no close_summary rows in the pin logs here, so the two machines' stops cannot be counted.")
    else:
        def stops(r, where):
            if not r["closes"]:
                return "%s: no pin log here" % where
            s_ = "%s missed %s" % (where, _nof(r["missed"], "close"))
            if r["gaps"]:
                a, d = r["longest"]
                s_ += " (%s, the longest %s from %s" % (_nof(r["gaps"], "stop"), _span_words(d), _et_at(a))
                s_ += ")" if r["gaps"] == 1 else "; %s in all)" % _span_words(r["hours"] * 3600.0)
            s_ += ", %s" % _nof(r["conn"], "connection hiccup")
            return s_
        L.append("Record: %s in its last %d days; %s in %s. Kalshi's Thursday maintenance (%s) is left out of both." % (
            esc(stops(rh, "the laptop")), SPEED_HOME_DAYS, esc(stops(rs, "the server")), esc(span),
            esc("%s and %s" % (_nof(rh["maint"], "gap"), _nof(rs["maint"], "gap")))))
        if w["laptop_style"] is not None and w["stop_rate"] is not None:
            L.append("At the server's %s a close, the laptop's stop rate (%s of its closes) would have cost about <b>%s</b> "
                     "here: shown, not added (a guess about a machine that no longer runs the bots)." % (
                         esc(usd(w["per_close"])), pct_of(w["stop_rate"], 1.0, 1), esc(usd(w["laptop_style"]))))
    L.append(i_("Speed is /speed's method (extra contracts x the $ a filled contract made on the server, markets settled "
                "here; its page spells it out). Cost is the price list, not the bill. A close is watched when the pin "
                "bot wrote its close_summary row; a gap over %d min between rows is a stop. Home = the %d days before "
                "the move (%s)." % (WORTH_GAP_S // 60, SPEED_HOME_DAYS, _et_at(w["since"]))))
    return L
