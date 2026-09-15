#!/usr/bin/env python3
# VERSION: 2026-09-14-h1
"""pinhealth.py -- the early warning: is the edge being competed away?

THE OPERATOR, 2026-09-14, after I explained why the edge might decay:
"And yes build it now."

WHAT DECAY WOULD LOOK LIKE, AND WHY IT NEEDS A DEDICATED TEST. The people
selling us a 100c contract for 96c lose on nearly every trade. At our current
size they apparently have not noticed. If they do -- or if anyone copies us --
they stop quoting under 98c in the final seconds and the edge is gone. The
measured shape of that is already visible: at 15 seconds out the side we want
has NOTHING under 98c on 94% of market-sides. We are feeding on the 6% who
have not adjusted.

THE SIGNATURE OF DECAY IS NOT A BAD WEEK. A bad week is fewer chances AND less
money. Decay is the opposite pairing:

    VOLUME UP, CENTS PER CONTRACT DOWN.

We trade more, and each contract earns less, because the counterparty is
pulling in and we are reaching further for what is left. That pairing is what
this file watches for, because either half alone is just weather.

THE KILL LINE IS ARITHMETIC, NOT A FEELING. Measured on our own fills, a
winning close pays +4.58c per contract and a losing one costs -35.8c. So at a
loss rate L the edge is  (1-L)*win - L*35.8 , and it reaches zero at

    win = L * 35.8 / (1 - L)

At our 4.15% loss rate that is 1.55c. Below roughly 1.5c per contract the
strategy is dead even though every individual trade still looks like a winner.
"""
import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_DASH_SELFTESTED", "1")
import pindash                                                 # noqa: E402

LOSS_COST_C = 35.8       # measured cents/contract on the ten real losing closes
WIN_C = 4.58             # measured cents/contract on winning closes
TREND_DAYS = 3           # consecutive days of the decay pairing before alarm


# ===========================================================================
# WHO IS ON THE OTHER SIDE, AND ARE THEY THINNING OUT?
#
# THE OPERATOR, 2026-09-14: "Small participants, that's great!!! They're very
# much unlikely to notice a systemic takeover of a tiny portion of their
# strategy that they already don't expect to win and hardly hurts them. A
# metric about that should be on the health check."
#
# He is right that it matters, and it is measurable even though Kalshi's tape
# carries NO counterparty identity. What it does carry is every individual ADD
# of liquidity, and behaviour has a fingerprint:
#
#   A DESK quotes round lots, repeatedly, at consistent size. If the top few
#   orders supply most of the liquidity we eat, we depend on a handful of
#   participants and one of them noticing ends us.
#
#   A CROWD posts odd little sizes -- 3, 4, 6, 9, 42 -- each one once. No
#   member loses enough to care, and there is nobody to coordinate a
#   withdrawal.
#
# CONCENTRATION is the measure: what share of the contracts we could buy comes
# from the biggest five orders. Low is safe. It is the Herfindahl idea without
# pretending we can identify accounts we cannot see.
#
# FLEETING is the second half of his question -- whether the supply itself is
# drying up. Counted as adds per hour and contracts per hour in the final
# thirty seconds, tracked day over day.
# ===========================================================================
CROWD_FILE = os.path.join(REPO, "results", "CROWD.json")


def crowd_scan(delta_dir, hours=2, lo=0.90, hi=0.98, tau_max=30):
    """Fingerprint the liquidity offered at prices we would buy.

    Reads the raw orderbook deltas, which is the only place individual orders
    appear. Expensive (~117 MB/hour), so it is a separate pass, cached.
    """
    import calendar
    import gzsalvage
    MON = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
           'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
    PFX = ("KXBTC", "KXETH", "KXSOL", "KXXRP", "KXDOGE", "KXBNB", "KXHYPE",
           "KXNEAR", "KXZEC")

    def close_of(tk):
        try:
            p = tk.split("-")[1]
            return calendar.timegm((2000 + int(p[:2]), MON[p[2:5]],
                                    int(p[5:7]), int(p[7:9]) + 4,
                                    int(p[9:11]), 0, 0, 0, 0))
        except Exception:                                # noqa: BLE001
            return None
    files = sorted(glob.glob(os.path.join(delta_dir, "*.jsonl.gz")))[-hours:]
    adds = []
    for fp in files:
        for line in gzsalvage.iter_lines(fp):
            if "15M-" not in line:
                continue
            try:
                m = json.loads(line)["msg"]
            except (ValueError, KeyError):
                continue
            tk = m.get("market_ticker")
            if not tk or not tk.startswith(PFX):
                continue
            try:
                d = float(m["delta_fp"])
                if d <= 0:
                    continue
                cl = close_of(tk)
                if cl is None:
                    continue
                tau = cl - int(m["ts_ms"]) / 1000.0
                if not (0 < tau <= tau_max):
                    continue
                ask = 1.0 - round(float(m["price_dollars"]), 4)
            except (KeyError, TypeError, ValueError):
                continue
            if lo <= ask <= hi:
                adds.append(d)
    if not adds:
        return None
    adds.sort(reverse=True)
    tot = sum(adds)
    # EFFECTIVE NUMBER OF SUPPLIERS, the operator's own question: "how many
    # different people are supplying the contracts at the end". We cannot see
    # accounts -- Kalshi's tape has no identity. What we CAN compute is the
    # inverse Herfindahl of the order sizes: 1 / sum(share^2). It answers
    # "how many EQUAL-SIZED suppliers would produce this much concentration".
    # Ten orders of equal size gives 10. One order of 90% plus ten tiny ones
    # gives about 1.2. It is the standard competition measure and it does not
    # pretend to identify anybody.
    #
    # IT IS AN UPPER BOUND ON PEOPLE, NOT A COUNT OF THEM: one participant
    # posting twenty separate orders reads as twenty. It still moves the right
    # way -- if suppliers withdraw, it falls.
    hhi = sum((x / tot) ** 2 for x in adds) if tot else 1.0
    eff = (1.0 / hhi) if hhi else 0.0
    return {"adds": len(adds), "contracts": round(tot, 1),
            "effective_suppliers": round(eff, 1),
            "distinct_sizes": len(set(round(x, 1) for x in adds)),
            "median_size": adds[len(adds) // 2],
            "top5_share": round(100.0 * sum(adds[:5]) / tot, 1),
            "round50_share": round(
                100.0 * sum(1 for x in adds
                            if x >= 50 and abs(x - round(x / 50) * 50) < 0.01)
                / len(adds), 1),
            "hours": len(files),
            "per_hour_adds": round(len(adds) / max(1, len(files)), 1),
            "per_hour_contracts": round(tot / max(1, len(files)), 1),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def book_trend(rows=None, bar=0.50):
    """Per ET day: closes, median and p75 touch depth, and the largest logged
    size still fillable at `bar` of the buyable moments.

    Reads `close_summary` rows the bot already writes. `logged_to` is the
    largest size that day's curve actually recorded -- when CAP equals it, the
    answer is CENSORED and the true ceiling is higher. Reporting a censored
    value as a measurement is exactly how a capacity limit gets invented."""
    import datetime as _dt
    if rows is None:
        rows = []
        for q in sorted(glob.glob(os.path.join(REPO, "results",
                                                "pinrun-live-*.jsonl"))):
            for line in open(q, encoding="utf-8"):
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("kind") == "close_summary" and d.get("depth"):
                    rows.append(d)
    byday = {}
    for d in rows:
        try:
            day = (_dt.datetime.strptime(d["t"][:19], "%Y-%m-%dT%H:%M:%S")
                   - _dt.timedelta(hours=4)).strftime("%Y-%m-%d")
        except (KeyError, ValueError):
            continue
        byday.setdefault(day, []).append(d)
    out = []
    for day in sorted(byday):
        rs = byday[day]
        med = sorted(r["depth"]["median"] for r in rs)
        p75 = sorted(r["depth"]["p75"] for r in rs)
        agg = {}
        for r in rs:
            for k, v in (r["depth"].get("kept") or {}).items():
                agg[int(k)] = agg.get(int(k), 0) + v
        base = agg.get(1) or 0
        cap = None
        if base:
            for s in sorted(agg, reverse=True):
                if agg[s] / float(base) >= bar:
                    cap = s
                    break
        out.append({"day": day, "closes": len(rs),
                    "med": med[len(med) // 2], "p75": p75[len(p75) // 2],
                    "cap": cap, "logged_to": max(agg) if agg else None})
    return out


def crowd_history(rec=None, path=None):
    """Append today's scan and return the stored history."""
    path = path or CROWD_FILE
    try:
        with open(path, encoding="utf-8") as fh:
            hist = json.load(fh)
    except (OSError, ValueError):
        hist = []
    if rec:
        day = rec["at"][:10]
        hist = [h for h in hist if h.get("at", "")[:10] != day] + [rec]
        hist.sort(key=lambda h: h.get("at", ""))
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(hist[-60:], fh, indent=1)
        except OSError:
            pass
    return hist


# ---------------------------------------------------------------- grading
# Each metric gets a PEAK (what good looks like) and a DEAD line (where the
# strategy stops working). The operator asked for exactly this: "what peak
# health is and what deadly unhealthy starting is."
GRADES = {
    "edge":   {"peak": 4.0,  "warn": 2.5,  "dead": 1.55, "hi_good": True,
               "unit": "c", "what": "cents earned per contract"},
    "margin": {"peak": 2.5,  "warn": 1.5,  "dead": 1.0,  "hi_good": True,
               "unit": "x", "what": "how far above the kill line"},
    "loss":   {"peak": 3.0,  "warn": 7.0,  "dead": 11.4, "hi_good": False,
               "unit": "%", "what": "closes that lose money"},
    "top5":   {"peak": 25.0, "warn": 50.0, "dead": 70.0, "hi_good": False,
               "unit": "%", "what": "liquidity from the biggest 5 orders"},
    "median": {"peak": 10.0, "warn": 40.0, "dead": 100.0, "hi_good": False,
               "unit": "", "what": "typical order size on the other side"},
    "supply": {"peak": 600.0, "warn": 250.0, "dead": 80.0, "hi_good": True,
               "unit": "", "what": "contracts offered per hour"},
    "suppliers": {"peak": 30.0, "warn": 10.0, "dead": 4.0, "hi_good": True,
                  "unit": "", "what": "effective number of separate suppliers"},
}


def grade(key, value):
    """('peak'|'ok'|'warn'|'dead', explanation) for one metric."""
    g = GRADES.get(key)
    if g is None or value is None:
        return "ok", ""
    hi = g["hi_good"]
    def worse(a, b):
        return a < b if hi else a > b
    if worse(value, g["dead"]):
        band = "dead"
    elif worse(value, g["warn"]):
        band = "warn"
    elif worse(value, g["peak"]):
        band = "ok"
    else:
        band = "peak"
    return band, ("peak %g%s, trouble at %g%s, dead at %g%s"
                  % (g["peak"], g["unit"], g["warn"], g["unit"],
                     g["dead"], g["unit"]))


def kill_line(loss_rate):
    """Cents per contract at which the edge is exactly zero."""
    if loss_rate >= 1.0:
        return float("inf")
    return loss_rate * LOSS_COST_C / (1.0 - loss_rate)


def daily(trades):
    """{day: {contracts, net, legs, closes, losing_closes, mean_price}}"""
    out = defaultdict(lambda: {"contracts": 0.0, "net": 0.0, "legs": 0,
                               "px": 0.0, "closes": set(), "bad": set()})
    per_close = defaultdict(float)
    close_day = {}
    for t in trades:
        if t["pnl"] is None or not t.get("t"):
            continue
        e = pindash.to_epoch(t["t"])
        if e is None:
            continue
        d = time.strftime("%Y-%m-%d", time.localtime(e))
        a = out[d]
        a["contracts"] += t["filled"]
        a["net"] += t["pnl"]
        a["legs"] += 1
        if t["price"]:
            a["px"] += float(t["price"]) * t["filled"]
        k = pindash.close_key(t["ticker"])
        a["closes"].add(k)
        per_close[k] += t["pnl"]
        close_day[k] = d
    for k, v in per_close.items():
        if v < 0:
            out[close_day[k]]["bad"].add(k)
    return out


def assess(rows, days=TREND_DAYS):
    """(alarm, reason). `rows` is [(day, contracts, cents_per_contract)]."""
    if len(rows) < days + 1:
        return False, ("only %d days on record; the trend test needs %d"
                       % (len(rows), days + 1))
    tail = rows[-(days + 1):]
    vol_up = all(tail[i][1] < tail[i + 1][1] for i in range(len(tail) - 1))
    edge_dn = all(tail[i][2] > tail[i + 1][2] for i in range(len(tail) - 1))
    if vol_up and edge_dn:
        return True, ("%d straight days of MORE contracts and LESS per "
                      "contract -- the signature of the other side pulling "
                      "in, not of a quiet market" % days)
    if edge_dn:
        return False, ("%d days of falling cents per contract, but volume is "
                       "NOT rising -- that is a quiet market, not decay"
                       % days)
    return False, "no decay pattern"


def report(tr, loss_rate=None, say=print):
    d = daily(tr)
    if not d:
        return "pinhealth: loaded nothing -- no settled trade on file"
    days = sorted(d)
    rows = []
    for k in days:
        a = d[k]
        c = a["contracts"]
        rows.append((k, c, 100.0 * a["net"] / c if c else 0.0))
    tot_closes = sum(len(d[k]["closes"]) for k in days)
    tot_bad = sum(len(d[k]["bad"]) for k in days)
    lr = loss_rate if loss_rate is not None else (
        tot_bad / tot_closes if tot_closes else 0.0)
    kl = kill_line(lr)
    lines = []
    w = lines.append
    w("  THE ONE NUMBER: cents earned per contract.")
    w("")
    w("  day        | closes | contracts |     net | c/contract | mean price")
    w("  -----------|--------|-----------|---------|------------|-----------")
    for k in days:
        a = d[k]
        c = a["contracts"]
        w("  %-10s | %6d | %9.0f | %+7.2f | %+9.2fc | %9.1fc"
          % (k, len(a["closes"]), c, a["net"],
             100.0 * a["net"] / c if c else 0.0,
             100.0 * a["px"] / c if c else 0.0))
    # ---- DOWNTIME: a day the bot could not trade is not a weak day ------
    # Operator, 2026-09-15: "We lost 7 hours of trade time today. Make sure
    # that's known for any future calculations so it doesn't make our daily
    # calculations look worse." results/DOWNTIME.json holds the windows.
    try:
        import downtime
        _lost = downtime.lost_by_et_day()
    except (ImportError, OSError, ValueError) as _e:
        _lost = {}
        w("  (downtime file unreadable: %s -- daily $ below is per CALENDAR day)" % _e)
    _hit = [k for k in days if _lost.get(k, 0) > 0]
    if _hit:
        w("")
        w("  DAYS THE BOT COULD NOT TRADE FOR PART OF (results/DOWNTIME.json):")
        w("  day        | hours lost | hours up |  net $ | $ per hour up | same, if it had traded 24h")
        w("  (hours up counts only time that has already happened -- today is partial)")
        for k in _hit:
            up = downtime.hours_up_et_day(k)
            rate = (d[k]["net"] / up) if up > 0 else None
            w("  %-10s | %10.2f | %8.2f | %+6.2f | %13s | %s"
              % (k, _lost[k], up, d[k]["net"],
                 "-" if rate is None else "%+.2f" % rate,
                 "-" if rate is None else "%+.2f" % (rate * 24.0)))
        w("  Compare days on $ per hour up, never on the raw daily total.")
    w("")
    w("  loss rate so far        : %.2f%%  (%d losing of %d closes)"
      % (100 * lr, tot_bad, tot_closes))
    w("  the edge dies below     : %+.2fc per contract" % kl)
    last = rows[-1][2] if rows else 0.0
    w("  most recent day         : %+.2fc per contract" % last)
    if last > kl:
        w("  headroom                : %+.2fc  (%.1fx the kill line)"
          % (last - kl, last / kl if kl else float("inf")))
    else:
        w("  *** BELOW THE KILL LINE. At this rate the strategy loses money "
          "even though most trades still win. ***")
    alarm, why = assess(rows)
    w("")
    w("  DECAY TEST: %s" % ("*** ALARM *** " + why if alarm else why))
    # ---- how deep is the book, and how high can the cap go ----------
    # Operator, 2026-09-15: "start tracking the order books ... Also to get an
    # idea of how high the cap will go." Read from the close summaries the bot
    # already writes -- no book walk, no extra cost.
    # NO BARE SWALLOW. The first version wrapped this in `except Exception:
    # bt = None`, and `RESULTS` was not a name in this file -- so the whole
    # section disappeared from the report with no error and no gap. A health
    # check that silently drops a section is worse than one that crashes.
    try:
        bt = book_trend()
    except (OSError, ValueError, KeyError, TypeError) as _e:
        bt = None
        w("")
        w("  THE BOOK WE BUY FROM: unavailable (%s: %s)"
          % (type(_e).__name__, _e))
    if bt:
        w("")
        w("  THE BOOK WE BUY FROM (per ET day, from %d closes)"
          % sum(x["closes"] for x in bt))
        w("    %-12s %8s %10s %10s %9s %10s"
          % ("day", "closes", "touch med", "touch p75", "CAP", "logged to"))
        for x in bt[-7:]:
            w("    %-12s %8d %10.0f %10.0f %9s %10s"
              % (x["day"], x["closes"], x["med"], x["p75"],
                 ("%d" % x["cap"]) if x["cap"] else "--",
                 ("%d" % x["logged_to"]) if x["logged_to"] else "--"))
        if len(bt) >= 4:
            old = sum(x["med"] for x in bt[:len(bt) // 2]) / (len(bt) // 2)
            new = sum(x["med"] for x in bt[len(bt) // 2:]) / (len(bt) - len(bt) // 2)
            if old > 0:
                r = new / old
                verdict = ("DEEPER" if r >= 1.15 else
                           "THINNER -- fewer contracts to buy" if r <= 0.85
                           else "flat")
                w("    -> book depth %s (%.2fx, first half of the record vs "
                  "second)" % (verdict, r))
        cap = bt[-1]["cap"]
        lg = bt[-1]["logged_to"]
        if cap and lg and cap >= lg:
            w("    -> CAP is censored: the log stops at %d and the book still "
              "fills there." % lg)
            w("       The real ceiling is higher than this number and is not "
              "yet measured.")
        elif cap:
            w("    -> at the touch alone, %d contracts still fill at half the "
              "buyable moments." % cap)
            w("       The bot buys down the LADDER, so this is a FLOOR on what "
              "it can actually take.")
    # ---- who is on the other side -----------------------------------
    hist = crowd_history()
    if hist:
        c = hist[-1]
        w("")
        w("  WHO IS SELLING TO US (order book fingerprint, %s)" % c["at"][:10])
        for key, val, lab in (
                ("top5", c.get("top5_share"),
                 "liquidity from the biggest 5 orders"),
                ("median", c.get("median_size"), "typical order size"),
                ("suppliers", c.get("effective_suppliers"),
                 "effective number of separate suppliers"),
                ("supply", c.get("per_hour_contracts"),
                 "contracts offered per hour")):
            band, scale = grade(key, val)
            w("    %-38s %10s   [%s]  %s"
              % (lab, ("%g" % val) if val is not None else "--",
                 band.upper(), scale))
        w("    %-38s %10d" % ("distinct order sizes seen",
                              c.get("distinct_sizes", 0)))
        w("    %-38s %9.1f%%" % ("posted at a round lot of 50+",
                                 c.get("round50_share", 0)))
        if (c.get("top5_share") or 0) < 25 and (c.get("median_size") or 0) < 40:
            w("    -> A CROWD, not a desk. No single participant supplies "
              "enough for their withdrawal to matter.")
        else:
            w("    -> CONCENTRATED. A few participants supply most of what we "
              "buy; one of them noticing would end this.")
        if len(hist) > 1:
            a0, a1 = hist[-2], hist[-1]
            dc = a1.get("per_hour_contracts", 0) - a0.get("per_hour_contracts", 0)
            w("    supply vs the previous scan: %+.0f contracts/hour" % dc)
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    ck(abs(kill_line(0.0415) - 1.55) < 0.02,
       "at our 4.15%% loss rate the edge dies at %.2fc per contract"
       % kill_line(0.0415))
    ck(kill_line(0.0) == 0.0, "with no losses any positive edge survives")
    ck(kill_line(0.10) > kill_line(0.04),
       "a higher loss rate needs a bigger edge to survive (%.2fc vs %.2fc)"
       % (kill_line(0.10), kill_line(0.04)))

    # THE PAIRING IS THE TEST. Either half alone must NOT alarm.
    decay = [("d1", 100, 5.0), ("d2", 200, 4.0), ("d3", 300, 3.0),
             ("d4", 400, 2.0)]
    a, why = assess(decay)
    ck(a, "volume up AND edge down for three days raises the alarm")

    quiet = [("d1", 400, 5.0), ("d2", 300, 4.0), ("d3", 200, 3.0),
             ("d4", 100, 2.0)]
    a2, why2 = assess(quiet)
    ck(not a2,
       "but a falling edge on FALLING volume does NOT -- that is a quiet "
       "market, and confusing the two would cry wolf every slow week (%s)"
       % why2)

    grow = [("d1", 100, 2.0), ("d2", 200, 3.0), ("d3", 300, 4.0),
            ("d4", 400, 5.0)]
    ck(not assess(grow)[0],
       "and growing on both counts is not an alarm either")
    ck(not assess([("d1", 100, 5.0), ("d2", 200, 4.0)])[0],
       "two days is not enough to call a trend")

    # the report must SAY it when the edge is under water
    class _T(dict):
        pass
    tr = [{"pnl": 0.01, "filled": 100.0, "price": 0.97,
           "ticker": "KXBTC15M-26SEP140100-00", "t": "2026-09-14T05:00:00Z"},
          {"pnl": -5.0, "filled": 100.0, "price": 0.97,
           "ticker": "KXETH15M-26SEP140115-15", "t": "2026-09-14T05:20:00Z"}]
    txt = report(tr, loss_rate=0.0415, say=None)
    ck("BELOW THE KILL LINE" in txt,
       "a day earning under the kill line is called out in words, not left "
       "for the reader to work out from a table")
    txt2 = report([{"pnl": 5.0, "filled": 100.0, "price": 0.93,
                    "ticker": "KXBTC15M-26SEP140100-00",
                    "t": "2026-09-14T05:00:00Z"}], loss_rate=0.0415, say=None)
    ck("headroom" in txt2, "and a healthy day reports its headroom")
    # ---- grading, both directions ------------------------------------
    ck(grade("edge", 5.0)[0] == "peak" and grade("edge", 3.0)[0] == "ok"
       and grade("edge", 2.0)[0] == "warn" and grade("edge", 1.0)[0] == "dead",
       "cents per contract grades peak/ok/warn/dead as it falls")
    ck(grade("loss", 2.0)[0] == "peak" and grade("loss", 12.0)[0] == "dead",
       "and the loss RATE grades the other way round -- lower is better, so a "
       "metric read backwards would paint a dying strategy green")
    ck(grade("top5", 20.0)[0] == "peak" and grade("top5", 80.0)[0] == "dead",
       "counterparty concentration: a crowd is healthy, a handful is not")
    ck(grade("supply", 800.0)[0] == "peak" and grade("supply", 50.0)[0] == "dead",
       "and supply is the opposite again -- more offered is better")
    ck(grade("nope", 1.0)[0] == "ok" and grade("edge", None)[0] == "ok",
       "an unknown metric or a missing value never invents a verdict")

    # ---- effective number of suppliers --------------------------------
    def eff(sizes):
        t=float(sum(sizes))
        return 1.0/sum((x/t)**2 for x in sizes)
    ck(abs(eff([10]*10)-10.0)<1e-9,
       "ten equal orders read as ten effective suppliers")
    ck(abs(eff([100])-1.0)<1e-9, "one order reads as one")
    ck(eff([900]+[10]*10) < 1.5,
       "one whale plus ten minnows reads as ~1, not 11 -- counting orders "
       "would call that a crowd when it is one participant (%.2f)"
       % eff([900]+[10]*10))
    ck(eff([20]*150) > 100,
       "and 150 small equal orders reads as a genuine crowd (%.0f)"
       % eff([20]*150))
    ck(grade("suppliers", 40)[0]=="peak" and grade("suppliers", 3)[0]=="dead",
       "more separate suppliers is healthier; a handful is the dead zone")

    # ---- the book-depth trend ----------------------------------------
    def _cs(day, kept, med=100.0, p75=200.0):
        return {"kind": "close_summary", "t": "%sT12:00:00Z" % day,
                "depth": {"median": med, "p75": p75, "kept": kept}}
    _k250 = {"1": 100, "250": 90}
    _bt = book_trend([_cs("2026-09-10", _k250)], bar=0.50)
    ck(len(_bt) == 1 and _bt[0]["cap"] == 250 and _bt[0]["logged_to"] == 250,
       "a curve that STOPS at 250 while still filling reports cap 250 AND "
       "logged_to 250 -- the pair is what says the answer is censored")
    _bt2 = book_trend([_cs("2026-09-16", {"1": 100, "250": 90, "1000": 80})],
                      bar=0.50)
    ck(_bt2[0]["cap"] == 1000 and _bt2[0]["logged_to"] == 1000,
       "with the extended curve the same book reports 1000 -- the old number "
       "was a floor, not a ceiling")
    _bt3 = book_trend([_cs("2026-09-16", {"1": 100, "250": 90, "1000": 10})],
                      bar=0.50)
    ck(_bt3[0]["cap"] == 250 and _bt3[0]["logged_to"] == 1000,
       "and when the book genuinely runs out, cap is BELOW logged_to -- that "
       "is the shape of a real measurement rather than a censored one")
    ck(book_trend([]) == [],
       "NULL: no close summaries reports nothing, never a fabricated day")
    _bt4 = book_trend([_cs("2026-09-10", {"1": 0})], bar=0.5)
    ck(_bt4[0]["cap"] is None,
       "a day with no buyable moments reports no cap, never zero")
    _many = book_trend([_cs("2026-09-10", _k250, med=50.0),
                        _cs("2026-09-11", _k250, med=200.0)])
    ck([x["day"] for x in _many] == ["2026-09-10", "2026-09-11"]
       and _many[0]["med"] == 50.0 and _many[1]["med"] == 200.0,
       "days come back in order with their own medians, so a trend can be read")

    # ---- the crowd fingerprint ---------------------------------------
    import tempfile as _tf
    _d = _tf.mkdtemp(prefix="crowd-")
    try:
        _p = os.path.join(_d, "c.json")
        h = crowd_history({"at": "2026-09-14T05:00:00Z", "top5_share": 10.0},
                          path=_p)
        ck(len(h) == 1, "a scan is stored")
        h = crowd_history({"at": "2026-09-14T09:00:00Z", "top5_share": 12.0},
                          path=_p)
        ck(len(h) == 1 and h[0]["top5_share"] == 12.0,
           "a second scan the SAME day replaces it rather than double-counting")
        h = crowd_history({"at": "2026-09-15T09:00:00Z", "top5_share": 30.0},
                          path=_p)
        ck(len(h) == 2 and h[-1]["top5_share"] == 30.0,
           "and a new day is appended, so the trend is one point per day")
    finally:
        for f in os.listdir(_d):
            os.remove(os.path.join(_d, f))
        os.rmdir(_d)
    print("pinhealth selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--logs", default=os.path.join(REPO, "results",
                                                   "pinrun-live-*.jsonl"))
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "HEALTH.txt"))
    ap.add_argument("--crowd", type=int, default=0,
                    help="also fingerprint the other side from this many "
                         "hours of raw order book deltas (~117MB/hour)")
    ap.add_argument("--deltas",
                    default="C:/kals/kalshi_data/orderbook_delta")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_HEALTH_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    ev = pindash.load(sorted(glob.glob(a.logs)))
    tr = pindash.build_trades(ev, pindash.load_outcomes(a.markets))
    if a.crowd:
        print("  fingerprinting the other side from %d hours of book..."
              % a.crowd)
        rec = crowd_scan(a.deltas, hours=a.crowd)
        if rec:
            crowd_history(rec)
            print("    %d orders, %d distinct sizes, median %g contracts, "
                  "top-5 share %.1f%%" % (rec["adds"], rec["distinct_sizes"],
                                          rec["median_size"], rec["top5_share"]))
    txt = report(tr)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("EDGE HEALTH -- written %s ET%s%s"
                 % (time.strftime("%Y-%m-%d %H:%M"), nl, nl))
        fh.write(txt + nl)
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
