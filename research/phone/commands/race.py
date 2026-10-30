"""/race -- the coin race's own page: the live race now (its log and the process table), the last 10 races and its
money by window from botstats.

v-tg-rebuild step 9 (2026-10-30): Phone.text_race (+ Phone._race_money_lines) as a command module (load + render),
byte-identical (golden shadow, research/golden/shadow_race_world.py: the fixture worlds have the race paused, so
/race is only compared in the race-active worlds that file adds).

Reads (load, in the old order): the clock, the main account's markets (kalshi_ledger.json) -> races, the process
table (fleet), the race's own log (pinracepenny-live.jsonl), its stop file, then botstats' race dict (Kalshi, at most
once a minute). A botstats failure costs the money lines only (logged), exactly as before; no other wall.
The race helpers (races_from, penny_view, race_tally, race_rows, race_size_words ...) stay in pinphone for now
(research/bars.py imports them from there): ctx.pp.<name>.
"""
import os
import traceback

import pindesk
from phone.command import Command, declare
from phone.html import Html, details, elines, esc, i_, pre
from phone.log import log
from pindesk import et_day, et_str

RACE_LOG = "pinracepenny-live.jsonl"
RACE_STOP = "pinracepenny.stop"
RACE_KINDS = ("start", "live_halt", "live_order", "live_settled", "bank_size")


def load(ctx):
    """Everything /race reads, in Phone.text_race's order."""
    P = ctx.pp
    now = ctx.now()
    res = ctx.ledger.results
    races = P.races_from(ctx.markets())
    fl = P.fleet_roles(ctx.procs())
    recs = P.log_records(os.path.join(res, RACE_LOG), RACE_KINDS)
    pv = P.penny_view(recs, now, ledger_events=set(races))
    stop = os.path.exists(os.path.join(res, RACE_STOP))
    money = money_load(ctx)
    return {"now": now, "races": races, "fl": fl, "pv": pv, "stop": stop, "money": money}


def money_load(ctx):
    """botstats' race dict, or the exception (logged here, as Phone._race_money_lines did)."""
    try:
        return {"b": ctx.bs_get("race")}
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        return {"err": e}


def render(d, ctx):
    P = ctx.pp
    now, races, fl, pv = d["now"], d["races"], d["fl"], d["pv"]
    today = et_day(now)
    st = pv["start"] or {}
    t = P.race_tally([r for r in races.values() if r["day"] == today])
    if t["races"]:
        L = ["%s <b>Coin race today %s</b> (<b>%s</b> on %s staked) · %d of %d won (%s)%s" % (
            P.dot(t["net"]), esc(P.usd(t["net"])), esc(P.ret(t["net"], t["paid"])), esc(P.dollars(t["paid"])),
            t["won"], t["races"], P.pct_of(t["won"], t["races"]),
            (" · %d tie, %d lost" % (t["tie"], t["lost"])) if (t["tie"] or t["lost"]) else "")]
    else:
        L = ["⚪ <b>Coin race today: no races settled yet</b>"]
    L.append(i_("🏁 COIN RACE · %s ET · live, real money, main account (Kalshi's books)"
                % et_str(now, "%a %m/%d %I:%M %p")))
    if fl["penny"]:                 # 2026-10-26: a red / green dot means money; the state is an icon and words
        L.append("▶️ <b>RUNNING</b>, pid %d" % fl["penny"][0])
    elif fl["unknown"]:
        L.append("❔ <b>Running? The process table could not be read.</b>")
    else:
        L.append("⚠️ <b>NOT RUNNING</b> (no pinracearm --live in the process table).")
    if d["stop"]:
        L.append("⏸ <b>STOOD DOWN</b>: the stop file results/pinracepenny.stop is present.")
    L.append("")
    size, rules = P.race_size_words(pv["start"], pv["bank_size"]), P.race_rule_words(pv["start"])
    L.append("📏 <b>How it bets</b>%s" % ("" if fl["penny"] else " <i>(its last start record)</i>"))
    if size:
        head, _sep, rest = size.partition(": ")
        L.append("<b>%s</b>: %s" % (esc(head[:1].upper() + head[1:]), esc(rest)) if rest else esc(size))
        L.append(esc("Buys " + rules + "."))
    else:
        L.append("Rails unknown (no start record).")
    if pv["halt"]:
        L.append("🛑 <b>STOP RAIL FIRED %s ET</b>: %s. No real order since." % (
            esc(et_str(pindesk.parse_t(pv["halt"].get("t")) or now, "%m/%d %I:%M %p")), esc(pv["halt"].get("why"))))
    elif st:
        L.append("Stop rail: not fired since the restart at %s ET."
                 % esc(et_str(pindesk.parse_t(st.get("t")) or now, "%m/%d %I:%M %p")))
    else:
        L.append("Stop rail: unknown -- no start record in its log.")
    nxt = (int(now) // 900 + 1) * 900
    left = int(nxt - now)
    _f, _leg_name = P._f, P._leg_name

    def legs_of(ls):
        return ", ".join("%s %s %.0fc x%g" % (_leg_name(o.get("ticker")), o.get("side"),
                                              100.0 * _f(o.get("exec_price") or o.get("ask_seen")),
                                              _f(o.get("filled"))) for o in ls)
    held = [x for x in pv["open"] if x[1] == nxt]
    others = [x for x in pv["open"] if x[1] != nxt]
    legs = "; ".join(legs_of(ls) for _e, _c, ls in held)
    L.append("")
    L.append("⏱ <b>Now</b>: race closing %s ET (%d:%02d left) -- %s. <b>%s out.</b>" % (
        esc(et_str(nxt)), left // 60, left % 60, esc(("holding " + legs) if legs else "no legs yet"),
        esc(P.dollars(pv["staked"] or 0.0))))
    if others:
        L.append("Awaiting Kalshi's result: " + esc("; ".join(
            "%s ET %s" % (et_str(c) if c else "?", legs_of(ls)) for _e, c, ls in others) + "."))
    if pv["pending"]:
        L.append("⚠️ %d older leg(s) the bot never scored and Kalshi has no row for (oldest %s ET)."
                 % (sum(len(ls) for _e, _c, ls in pv["pending"]),
                    esc(et_str(pv["pending"][0][1], "%m/%d %I:%M %p") if pv["pending"][0][1] else "?")))
    L.append("")
    L.append("🏆 <b>Last 10 races</b> <i>(Kalshi's books)</i>")
    if races:
        L.append(pre(P.race_rows(races, 10)))
    else:
        L.append("none on file.")
    L.append("Paper race arms running: %s." % esc(
        "process table could not be read" if fl["unknown"] else
        (", ".join(fl["race_arms"]) if fl["race_arms"] else "none")))
    L += money_lines(d["money"], ctx)
    return Html("\n".join(L))


def money_lines(m, ctx):
    """/race's money by window (2026-09-30), from botstats: every coin-race market in the main account, one leg = one
    coin's market. Plus the version, its keep-alive, what Kalshi holds open, the shared cash and today's refusals. A
    botstats failure costs these lines only. botstats' Settings line is left to 'How it bets' above. (Phone.
    _race_money_lines)"""
    P = ctx.pp
    if "err" in m:
        return ["", "Money by window: could not build it (%s). The lines above still stand." % esc(str(m["err"])[:160])]
    b = m["b"]
    L = [""]
    L += P.bs_money_html(b["money"], "leg")
    L.append("")
    L += elines([x for x in P.bs_setup_lines(b["running"]) if not x.startswith("Settings: ")])
    ol = elines(P.bs_open_lines(b["open"], "leg"))
    L.append("📂 " + ol[0].replace("Open now:", "<b>Open now:</b>", 1))
    L += ol[1:]
    L.append("💵 " + esc(P.bs_cash_line(b["balance"])).replace("Cash:", "<b>Cash:</b>", 1))
    det = (elines(P._money_detail(b["money"], "leg")) if b["money"]["ok"] else [])
    det += elines(P.bs_activity_lines("race", b["activity_today"]))
    L.append(details(det, "🔎 Details: every window in words, today's log"))
    return L


COMMAND = declare(Command(
    names=("/race",), section="one_bot", order=20, help_line=None,
    chart="bot:race", load=load, render=render))
