"""/racestats -- the live coin race's record by window (Kalshi's books) and every paper race arm on the same races.

v-tg-rebuild step 9 (2026-10-30): Phone.text_racestats as a command module (load + render), byte-identical (golden
shadow, research/golden/shadow_race_world.py: the fixture worlds have the race paused, so /racestats is only compared
in the race-active worlds that file adds).

Reads (load, in the old order): the clock, the main account's markets -> races (none: the one-line answer, nothing
else read), the CACHED process table (the arms are stopped; 'unknown' is fine here, a cold-cache read is not:
ctx.procs_cached()), results/race_arms_scored.json, then per paper arm its log's results, span and size. No wall:
an exception propagates as before. The race helpers stay in pinphone for now (research/bars.py imports them):
ctx.pp.<name>.
"""
import os

import pindesk
from phone.command import Command, declare
from phone.html import Html, details, esc, html_to_plain, i_, norm_money, pre, table
from pindesk import et_day, et_str


def load(ctx):
    P = ctx.pp
    now = ctx.now()
    res = ctx.ledger.results
    races = P.races_from(ctx.markets())
    if not races:
        return {"races": races}
    r30 = ctx.race30_epoch
    fl = P.fleet_roles(ctx.procs_cached())
    sc = P.race_arms_scored(res) or {}
    arms = []
    for name in P.RACE_ARMS:
        p = os.path.join(res, "pinracearm-%s.jsonl" % name)
        if not os.path.exists(p):
            arms.append({"name": name, "log": False})
            continue
        ar = P.arm_results(p)
        span = P.log_span(p) or {}
        a = (sc.get("arms") or {}).get(name) or {}
        try:
            fresh = bool(a) and int(a.get("log_size") or -1) == os.path.getsize(p)
        except OSError:
            fresh = False
        arms.append({"name": name, "log": True, "ar": ar, "span": span, "a": a, "fresh": fresh})
    return {"now": now, "races": races, "r30": r30, "fl": fl, "sc": sc, "arms": arms}


def render(d, ctx):
    P = ctx.pp
    races = d["races"]
    if not races:
        return Html("No coin-race settlements on Kalshi's books yet.")
    now, r30, fl, sc = d["now"], d["r30"], d["fl"], d["sc"]
    today = et_day(now)
    race_tally, pct_of, usd, ret, dollars, _f = P.race_tally, P.pct_of, P.usd, P.ret, P.dollars, P._f
    first_day = min(r["day"] for r in races.values())
    allr = list(races.values())
    wins = [("ALL TIME (since %s)" % P._md(first_day), allr, "All"),
            ("LAST 7 DAYS", [r for r in allr if r["day"] >= P.day_minus(today, 6)], "7 days"),
            ("LAST 3 DAYS", [r for r in allr if r["day"] >= P.day_minus(today, 2)], "3 days"),
            ("TODAY", [r for r in allr if r["day"] == today], "Today"),
            ("SINCE v-race30 (%s ET)" % et_str(r30, "%m/%d %I:%M %p"),
             [r for r in allr if r["close"] is not None and r["close"] >= r30], "v30")]
    at = race_tally(allr)
    L = ["%s <b>Coin race all time %s</b> (<b>%s</b> on %s staked) · %d races, <b>%s</b> won" % (
             P.dot(at["net"]), esc(usd(at["net"])), esc(ret(at["net"], at["paid"])), esc(dollars(at["paid"])),
             at["races"], pct_of(at["won"], at["races"], 1)),
         i_("🏁 COIN RACE STATS · %s ET · Kalshi's books, real money. A race = one 15-min contest; a tie pays "
            "50c a leg and counts as a loss." % et_str(now, "%a %m/%d %I:%M %p"))]
    rows = [("", "Money", "Return", "Races", "Won", "T/L")]
    det = []
    for title, rs, lab in wins:
        t = race_tally(rs)
        if not t["races"]:
            rows.append((lab, "no races"))
            continue
        rows.append((lab, usd(t["net"]), ret(t["net"], t["paid"]) or "-", t["races"],
                     pct_of(t["won"], t["races"]), "%d/%d" % (t["tie"], t["lost"])))
        det.append(esc(norm_money("%s: %s" % (title, P.race_tally_line(t)))))
    L.append("")
    L.append(pre(table(rows)))
    L.append(i_("Return = on what the bets cost (fees in) · Won = races won · T/L = ties / losses · v30 = since "
                "v-race30, %s ET (today's rules)" % et_str(r30, "%m/%d %I:%M %p")))
    # ---- the paper arms, on the races the live bot played since v-race30 ----
    since = {e: r for e, r in races.items() if r["close"] is not None and r["close"] >= r30}
    cards, rec_rows, money_rows, said, run_det = [], [("Arm", "In", "Won", "W/T/L")], \
        [("Arm", "Own size", "At live", "Live bot")], [], []
    n_stopped = n_arms = n_scored = 0
    starred, star_ties = [], []
    z3res, z3_span = None, None
    last_ran = None
    for arm in d["arms"]:
        name = arm["name"]
        if not arm["log"]:
            cards.append("<b>%s</b>: no log." % esc(name))
            continue
        n_arms += 1
        ar, span = arm["ar"], arm["span"]
        if name == "z3":
            z3res, z3_span = ar, span
        if span.get("last") is not None:
            last_ran = max(last_ran or span["last"], span["last"])
        running = None if fl["unknown"] else (name in fl["race_arms"])
        quiet = span.get("last") is not None and now - span["last"] > 6 * 3600
        ran = "%s to %s" % (et_str(span["first"], "%b %d") if span.get("first") else "?",
                            et_str(span["last"], "%b %d") if span.get("last") else "?")
        if running:
            status = "PAPER, RUNNING (since %s)" % (et_str(span["first"], "%b %d") if span.get("first") else "?")
        elif span.get("end") or quiet:
            status = "PAPER, STOPPED · ran %s" % ran
            n_stopped += 1
        else:
            status = "PAPER · log written %s ET%s" % (
                et_str(span["last"], "%b %d %I:%M %p") if span.get("last") else "?",
                "; not in the process table" if running is False else "")
        a, fresh = arm["a"], arm["fresh"]
        cards.append("<b>%s</b> · %s%s" % (esc(name), esc(status),
                                           (" · " + esc(a["own_size"])) if a.get("own_size") else ""))
        rec = P.arm_record(ar, since)
        evs = [e for e in since if (ar.get(e) or {}).get("positions", 0) > 0]
        live_same = sum(since[e]["pnl"] for e in evs)
        rec_rows.append((name, "%d %s" % (rec["entered"], pct_of(rec["entered"], len(since))),
                         pct_of(rec["won"], rec["entered"], 1) or "-",
                         "%d/%d/%d" % (rec["won"], rec["tie"], rec["lost"])))
        same = a.get("same") or {}
        if fresh and same.get("races") == rec["entered"]:
            n_scored += 1
            money_rows.append((name, usd(same.get("own")), usd(same.get("at_live")), usd(live_same)))
            if same.get("own_log") is not None and abs(_f(same["own_log"]) - _f(same.get("own"))) >= 0.005:
                said.append("%s %s" % (name, usd(same["own_log"])))
            run = a.get("run") or {}
            if run:
                run_det.append(esc("%s, whole run: %d races, %d won, %d tie, %d lost; own size %s, at the live "
                                   "bot's size %s." % (name, run.get("races", 0), run.get("won", 0),
                                                       run.get("tie", 0), run.get("lost", 0), usd(run.get("own")),
                                                       usd(run.get("at_live")))))
        else:
            money_rows.append((name, usd(rec["net"]) + "*", "-", usd(live_same)))
            if rec["entered"]:
                starred.append(name)
                if rec["ties_as_wins"]:
                    star_ties.append(name)
    # 2026-10-23 (operator: nothing out of date in front -- "the stopped September race arms"): when every arm
    # is stopped, the page says so in one line and the whole arms section goes behind the tap
    all_stopped = bool(n_arms) and n_stopped == n_arms
    page = L
    L = []
    L.append("")
    L.append("🧪 <b>PAPER ARMS</b> -- no real money%s" % (
        (" · all %d STOPPED" % n_arms) if all_stopped else ""))
    L += cards
    L.append("")
    L.append("On the <b>%d</b> races the live bot played since v-race30:" % len(since))
    L.append(pre(table(rec_rows, "lrrr")))
    L.append(pre(table(money_rows)))
    legend = "Own size = the arm's own paper size%s. " % (
        (", scored on Kalshi's results (a tie pays 50c)%s" % (
            (" -- their own logs said %s (a log books a tie as a win and does its own fee sums)"
             % ", ".join(said)) if said else ""))
        if n_scored else "")
    if n_scored:
        legend += ("At live = the same legs at the live bot's size for that race, capped by what the book "
                   "showed. ")
    legend += ("Live bot = what the real bot made on those races (Kalshi). Paper is optimistic (race-arms "
               "check, 10-18): on legs the live bot also sent, paper made 41% more than real fills, so At live "
               "reads ~40% high; the 250-a-leg arms' Own size prices fills at the touch, and walking the book "
               "cuts it 30-66%.")
    if starred:
        legend += " * = the arm's own log money (%s)%s." % (
            "no Kalshi re-scoring on file" if not sc.get("arms") else "its log changed after it was re-scored",
            ("; %s booked a tie as a win" % (
                " and ".join("%s's" % x for x in star_ties) + (" own logs" if len(star_ties) > 1 else " own log")))
            if star_ties else "")
    L.append(i_(legend))
    if sc.get("made"):
        L.append(i_("Scored once on %s from Kalshi's results (results/%s); stopped arms do not change."
                    % (et_str(pindesk.parse_t(sc["made"]), "%b %d"), P.RACE_ARMS_SCORED)))
    if z3res is not None:
        Z3_KILL, Z3_PASS, Z3_PASS_ALT = P.Z3_KILL, P.Z3_PASS, P.Z3_PASS_ALT
        z = P.z3_progress(z3res, races)
        verdict = ""
        if z["first50_losses"] >= Z3_KILL[0]:
            verdict = " -- AT THE KILL LINE"
        elif z["races"] >= Z3_PASS[0] and z["losses"] <= Z3_PASS[1]:
            verdict = " -- PASSED the %d bar" % Z3_PASS[0]
        elif z["races"] >= Z3_PASS_ALT[0] and z["losses"] <= Z3_PASS_ALT[1]:
            verdict = " -- PASSED the %d bar" % Z3_PASS_ALT[0]
        stopped = ""
        if (z3_span or {}).get("last") and not verdict and "z3" not in fl["race_arms"] \
                and ((z3_span or {}).get("end") or now - z3_span["last"] > 6 * 3600):
            stopped = (" Neither passed nor killed: it STOPPED %s at %d of %d races, so the bar does not move "
                       "until it runs again." % (et_str(z3_span["last"], "%b %d"), z["races"], Z3_PASS_ALT[0]))
        L.append("")
        L.append("🎯 <b>z3 bar</b>: %d races so far, %d loss%s (first 50: %d). Pass = %d races with %d losses, "
                 "or %d with at most %d. Kill = %d losses in the first %d%s.%s" % (
                     z["races"], z["losses"], "" if z["losses"] == 1 else "es", z["first50_losses"],
                     Z3_PASS[0], Z3_PASS[1], Z3_PASS_ALT[0], Z3_PASS_ALT[1], Z3_KILL[0], Z3_KILL[1],
                     ("<b>%s</b>" % esc(verdict)) if verdict else "", esc(stopped)))
    arms, L = L, page
    if all_stopped:
        L.append("")
        L.append("🧪 <b>Paper arms</b>: none running -- all %d stopped, the last on %s. Their record on the live "
                 "bot's races is under the tap below." % (n_arms, esc(et_str(last_ran, "%b %d") if last_ran else "?")))
        extra = [esc(x) for a in arms for x in html_to_plain(a).split("\n") if x.strip()]
    else:
        L += arms
        extra = []
    L.append("")
    L.append(details(det + run_det + extra, "🔎 Legs, prices and break-even by window; each arm's whole run"
                     + (" and the stopped paper arms" if extra else "") + " (tap)"))
    return Html("\n".join(L))


COMMAND = declare(Command(
    names=("/racestats",), section="one_bot", order=21, help_line=None,
    chart="bot:race", load=load, render=render))
