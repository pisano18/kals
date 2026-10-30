"""/stats -- the main account's whole record by window: lifetime money as the headline, one table of every window with
its % of the bank, the live pin bot (version, pid, size, halt line, today's own count), the paper arms, the coin race
while it is active, and each window's full sentences behind a tap.

v-tg-rebuild step 9 (2026-10-30): Phone.text_stats (+ Phone._race_summary, used by /stats alone: copied here verbatim
with ctx for self) as a command module (load + render), byte-identical (golden shadow). Money is Kalshi's (the main
account's kalshi_ledger.json); the seconds-left split is from the bots' order records; the bank, size and day count
are the live bot's own files. No wall: an exception propagates as before (only the botstats lifetime pot is guarded,
logged, as before).
"""
import os
import traceback

import bots as _bots
import pindesk
from phone.command import Command, declare
from phone.html import Html, b_, details, elines, esc, i_, pre, table
from phone.log import log
from pindesk import et_day, et_day_start, et_str


def load(ctx):
    """Everything /stats reads, in Phone.text_stats' order. {'empty': True} when nothing settled since the first live
    day (nothing more is read)."""
    P = ctx.pp
    now = ctx.now()
    today = et_day(now)
    res = ctx.ledger.results
    mk = ctx.markets()
    ms = [m for m in mk.values() if m["day"] >= P.FIRST_LIVE_DAY]
    if not ms:
        return {"empty": True}
    taus = P.first_entries(ctx.ledger.orders)
    fl = P.fleet_roles(ctx.procs())
    ver = P.live_version(ctx.versions_path)
    _md, day_minus = P._md, P.day_minus
    wins = [("LIFETIME (since %s)" % _md(P.FIRST_LIVE_DAY), ms, P.days_between(P.FIRST_LIVE_DAY, today), "Life"),
            ("LAST 7 DAYS", [m for m in ms if m["day"] >= day_minus(today, 6)], 7, "7 days"),
            ("LAST 3 DAYS", [m for m in ms if m["day"] >= day_minus(today, 2)], 3, "3 days"),
            ("TODAY (%s)" % _md(today), [m for m in ms if m["day"] == today], 1, "Today")]
    if ver:
        wins.append(("SINCE %s (%s ET)" % (ver[0], et_str(ver[1], "%m/%d %I:%M %p")),
                     [m for m in ms if m["close"] is not None and m["close"] >= ver[1]], None, "Version"))
    sts = [(title, P.window_stats(sub, taus), nd, lab, sub) for title, sub, nd, lab in wins]
    main_words = P.main_words(ctx.active())
    life_in = None
    try:
        life_in = ((ctx.bs_get(P.DESK_BOT).get("money") or {}).get("all_time") or {}).get("pot")
    except Exception:                                       # noqa: BLE001
        log(traceback.format_exc())
    starts = {"7 days": et_day_start(day_minus(today, 6)), "3 days": et_day_start(day_minus(today, 2)),
              "Today": et_day_start(today), "Version": ver[1] if ver else None}
    banks = {}
    for title, st, nd, lab, sub in sts:
        if st["markets"] and lab != "Life":
            banks[lab] = ctx.ledger.bank_at(starts[lab]) if starts.get(lab) else None
    act_ = ctx.active()
    sz = P.read_json(os.path.join(res, "pinrun-live-size.json")) or {}
    hwm = P.read_json(os.path.join(res, "pinrun-hwm.json")) or {}
    dl = P.read_json(os.path.join(res, "pinrun-dayloss.json")) or {}
    race_on = ("race" in ctx.active()) if not fl["unknown"] else None      # v-tg-active: as text_stats asks it
    race_shown = "race" in ctx.active()
    return {"empty": False, "now": now, "today": today, "mk": mk, "fl": fl, "ver": ver, "sts": sts,
            "main_words": main_words, "life_in": life_in, "banks": banks, "act_": act_, "sz": sz, "hwm": hwm,
            "dl": dl, "race_on": race_on, "race_shown": race_shown, "race30_epoch": ctx.race30_epoch}


def render(d, ctx):
    P = ctx.pp
    if d["empty"]:
        return Html("No Kalshi settlements on file since %s (results/kalshi_ledger.json)." % P.FIRST_LIVE_DAY)
    now, today, fl, ver, sts, life_in = d["now"], d["today"], d["fl"], d["ver"], d["sts"], d["life_in"]
    usd, ret, dollars, _f, _md, _of100 = P.usd, P.ret, P.dollars, P._f, P._md, P._of100
    FIRST_LIVE_DAY = P.FIRST_LIVE_DAY
    life = sts[0][1]
    # "every bot" was true until the forecaster and the ladder got their
    # own subaccounts; kalshi_ledger.json is the main account only now.
    L = ["%s <b>Lifetime %s</b> (<b>%s</b> on $%s risked) · since %s" % (
             P.dot(life["net"]), esc(usd(life["net"])), esc(ret(life["net"], life["risked"], 2)),
             esc(P._usd(life["risked"])), esc(_md(FIRST_LIVE_DAY))),
         i_("📊 STATS · %s ET · Kalshi's books, main account (%s; every other bot: /bots); "
            "days are ET." % (et_str(now, "%a %m/%d %I:%M %p"), d["main_words"]))]
    # % of the bank (2026-10-26): each window's money over the main account's bank when it began (pindesk's
    # bank_at, the /days figure); Life over the money put into the main account (botstats' pot, as /pin says)
    rows = [("", "Money", "Return", "of bank", "Won", "Lost")]
    for title, st, nd, lab, sub in sts:
        if not st["markets"]:
            rows.append((lab, "nothing settled"))
            continue
        if lab == "Life":
            ob = (ret(st["net"], life_in, 0) + "*") if life_in else "-"
        else:
            b0 = d["banks"][lab]
            ob = ret(st["net"], b0, 2 if b0 and abs(st["net"] / b0) < 0.01 else 1) or "-"
        rows.append((lab, usd(st["net"]), ret(st["net"], st["risked"], 1) or "-", ob,
                     P.pct1(st["won"], st["markets"]), st["losses"]))
    L.append("")
    L.append("💰 <b>By window</b>")
    L.append(pre(table(rows)))
    L.append(i_("Return = on what the bets cost (fees in) · of bank = of the main account's bank when the window "
                "began%s · Won = markets won · Lost = markets that lost" % (
                    (" (* Life: of the %s put into it)" % dollars(life_in)) if life_in else "")))
    if life["breakeven_d"] is not None and life["win_n"] is not None:
        L.append("🎯 Lifetime: won <b>%s%%</b> of markets (break-even needs %s%%) · contracts paid %s%% vs "
                 "break-even %s%%: <b>%+.1f pts</b>" % (
                     _of100(life["win_c"]), _of100(life["breakeven_c"]), _of100(life["win_n"]),
                     _of100(life["breakeven_d"]), 100.0 * (life["win_n"] - life["breakeven_d"])))
    by = {}
    for m in sts[0][4]:
        by[m["book"]] = by.get(m["book"], 0.0) + m["pnl"]
    act_ = d["act_"]
    names = dict([(b.ledger_book, b.word if (b.always_shown or b.name in act_) else P.BOT_WORD["earlier"])
                  for b in _bots.all_bots() if b.ledger_book] + [("commodity", "old oil bot (Sep)"), ("other", "other")])
    L.append(esc("Lifetime by bot: " + ", ".join("%s %s" % (names.get(b, b), usd(v))
                                                 for b, v in sorted(by.items(), key=lambda kv: -kv[1])) + "."))
    pid = fl["live"][0] if fl["live"] else None
    live_cl = fl["live"][1] if fl["live"] else ""
    if pid:
        where = ", pid %d" % pid
    elif fl["unknown"]:
        where = " (process table could not be read)"
    else:
        where = ", NOT in the process table"
    L.append("")
    if ver:
        L.append("⚙️ <b>LIVE %s</b> since %s ET%s%s." % (esc(ver[0]), esc(et_str(ver[1], "%m/%d %I:%M %p")),
                                                      " (about)" if ver[2] else "", esc(where)))
    else:
        L.append("⚙️ <b>LIVE version</b>: no readable header in VERSIONS.md%s." % esc(where))
    parts = []
    argv_opt = P.argv_opt
    hb = argv_opt(live_cl, "--hedge-belief")
    if hb:
        parts.append("Hedge trigger: belief %.0f%%" % (100.0 * _f(hb)))
    sz, hwm, dl = d["sz"], d["hwm"], d["dl"]
    if sz.get("size") is not None:
        s = "Size %g contracts (auto)" % _f(sz["size"])
        if sz.get("bank") is not None:
            s += ", bank %s read %s" % (dollars(_f(sz["bank"])), et_str(pindesk.parse_t(sz.get("at")) or now))
        parts.append(s)
    if parts:
        L.append(esc(". ".join(parts) + "."))
    if hwm.get("hwm") and sz.get("bank") is not None:
        h = _f(hwm["hwm"])
        line = (1.0 - P.MAX_DRAWDOWN) * h
        room = _f(sz["bank"]) - line
        L.append("🛑 Halt if the bank falls to %s (%.0f%% under its high of %s): <b>%s of room</b>%s." % (
            esc(dollars(line)), 100.0 * P.MAX_DRAWDOWN, esc(dollars(h)), esc(dollars(room)),
            (" (%s of the bank)" % P.pct_of(room, _f(sz["bank"]), 1)) if _f(sz["bank"]) > 0 else ""))
    cap = argv_opt(live_cl, "--loss-cap")
    if dl.get("day") == today and dl.get("realised") is not None:
        L.append("Today by the bot's own count: <b>%s</b>%s." % (
            esc(usd(_f(dl["realised"]))), esc(" (stops at -$%s for the day)" % cap) if cap else ""))
    if fl["unknown"]:
        L.append("Paper arms: the process table could not be read.")
    else:
        arms = [a[4:] if a.startswith("arm-") else a for a in fl["arms"]]
        race_on = d["race_on"]            # v-tg-active: the paused race and its arms are not said
        L.append(esc("Paper arms: %d%s%s." % (
            len(arms), (" (" + ", ".join(arms) + ")") if arms else "",
            (" + %d race arms%s" % (len(fl["race_arms"]), (" (" + ", ".join(fl["race_arms"]) + ")")
                                    if fl["race_arms"] else "")) if race_on else "")))
    if d["race_shown"]:
        L.append("🏁 Coin race: " + esc(race_summary(ctx, P.races_from(d["mk"]), d["race30_epoch"])))
    det, seen = [], []
    for title, st, nd, lab, sub in sts:                 # every window's full sentences, one quote
        keys = frozenset(m["tk"] for m in sub)
        same = next((t0 for t0, k0 in seen if k0 == keys), None) if keys else None
        seen.append((title, keys))
        if same:                                        # e.g. a version deployed at midnight = TODAY
            det.append("%s: the same %s as %s, so the same numbers." % (b_(title), esc(P._nof(len(keys), "market")),
                                                                       esc(same)))
            continue
        det.append(b_(title))
        det += elines(P.stats_block(title, st, nd).split("\n")[1:])
    L.append("")
    L.append(details(det, "🔎 Every window in words (tap)"))
    return Html("\n".join(L))


# ---- from pinphone.Phone._race_summary (/stats alone uses it) --------------------------------------------------------
def race_summary(ctx, races, race30_epoch):
    """'N races since MM/DD: W won (x%), T tie, L lost, $ (/race).' on the races since v-race30. (Phone._race_summary,
    verbatim; self.race30_epoch -> race30_epoch)"""
    P = ctx.pp
    rs = [r for r in races.values() if r["close"] is not None and r["close"] >= race30_epoch]
    t = P.race_tally(rs)
    if not t["races"]:
        return "no real races on Kalshi's books since v-race30."
    return "%d races since %s: %d won (%s), %d tie, %d lost, %s (/race)." % (
        t["races"], et_str(race30_epoch, "%m/%d"), t["won"], P.pct_of(t["won"], t["races"], 1), t["tie"],
        t["lost"], P.usd(t["net"]))


COMMAND = declare(Command(
    names=("/stats",), section="money", order=30,
    help_line="/stats — the whole record by window: money, win rate vs break-even, losses, timing",
    chart="stats", load=load, render=render))
