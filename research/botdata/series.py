"""series.py -- the numbers the phone's pictures are drawn from (and that /today's pace line and /losses' words read):
every bot's settled markets, its losing markets, the average day before a day, today's pace. DATA only: no drawing,
no matplotlib, never imports the phone.

v-tg-rebuild step 8 (2026-10-30): moved VERBATIM out of tgcharts.py (all_markets was _all_markets, fold was _fold,
race_rows was _race_rows, account_series was _account_series). The only change is how botstats arrives: tgcharts read it
from ctx["pp"]._bs() (the phone module passed into the charts); here every function that needs it takes `bs`, the
botstats module (or anything with its names: _load, _money_block, pot_context, day_pot, pot_for, et_day, day_start,
shift_day, BOTS, SPEC, is_bot, is_active, bot_subs, ...), so a test can plant one and a broken botstats still costs only
the caller that asked. tgcharts.py keeps the old names (all_losses(ctx), all_day_markets(ctx), by_now, ...) as a facade.

Two rules every function here shares (both from tgcharts, unchanged):
  * the AVG_DAYS (7) / LONG_DAYS (30) day averages are always the days BEFORE the day drawn (today never averages
    itself); a calendar day inside that span with nothing settled counts as $0; days before the first day on the books
    are left out (so the first week averages the days there are);
  * v-tg-active (2026-10-30): a bot that is not ACTIVE is counted as 'earlier' (fold), never by its own name.
"""
import bisect
import os
import sys

_RESEARCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RESEARCH not in sys.path:
    sys.path.insert(0, _RESEARCH)
from pindesk import Ledger, et_day, et_day_start                     # noqa: E402
from botdata.clock import prev_day                                   # noqa: E402,F401  (tgcharts.prev_day, verbatim)
import bots                                                          # noqa: E402

# ---- the 7-day average (operator 10-23: "The 7 day average should be on the other charts too where possible.
# Like on /today as a 3rd line.") ---------------------------------------------------------------------------------
AVG_DAYS = 7
# 2026-10-29, the operator: "For bots with 7 day average can we also add a lifetime or month average whichever is better.
# And I think more charts may benefit from history averages too". 30 ET days, not lifetime: the bots' rules and sizes
# changed a lot since August. Every chart with a 7-day line gets a 30-day one beside it, by the SAME rule (the days
# BEFORE the day drawn, a quiet day $0, days before the first on the books left out -- so a young bot's '30-day' is
# every day it has, and the key says how many). botstats.LONG_DAYS is the words' copy of this number.
LONG_DAYS = 30
# ---- today's pace (operator 10-22: "for each bot ... a graph of today with an overlay of yesterday and then
# another overlay of the last 7 days so I can see if it's on track above or behind") ---------------------------
PACE_DAYS = 7
WINDOW_DAYS = 45                        # day-by-day pictures show this many days (their totals count all)


# ---- the main account's own ledger (pindesk.Ledger): the pictures drawn when botstats cannot be read --------------
def closes_cum(rows):
    """[(close epoch, running total, that close's net)] -- Ledger.by_close, the /today sparkline's source."""
    closes = Ledger.by_close(rows)
    out, cum = [], 0.0
    for k in sorted(c for c in closes if c is not None):
        cum += closes[k]
        out.append((k, cum, closes[k]))
    return out


def ledger_days(led):
    """[(ET day, net)] for every day Ledger.days() lists; net = Ledger.summary(settled_on(day))['net']."""
    by = {}
    for s in led.settled:
        if s["t"]:
            d = et_day(s["close"] or s["t"])
            by[d] = by.get(d, 0.0) + s["pnl"]
    return [(d, by.get(d, 0.0)) for d in led.days()]


def day_avg(led, day, n=AVG_DAYS):
    """The average day of the n (AVG_DAYS) ET days before `day`, close by close on the ET clock:
    ([(seconds after midnight ET, mean running $)] on a 15-minute grid, days averaged) -- ([], 0) when none."""
    listed = led.days()
    if not listed:
        return [], 0
    ds, d = [], day
    for _ in range(n):
        d = prev_day(d)
        if d >= listed[0]:
            ds.append(d)
    if not ds:
        return [], 0
    curves = []
    for d in ds:
        t0 = et_day_start(d)
        curves.append([(k - t0, c) for k, c, _v in closes_cum(led.settled_on(d))])

    def at(pts, g):
        v = 0.0
        for x, y in pts:
            if x > g:
                break
            v = y
        return v
    grid = list(range(0, 86400 + 1, 900))
    return [(g, sum(at(c, g) for c in curves) / len(curves)) for g in grid], len(ds)


def avg_by_day(vals, days, n=AVG_DAYS):
    """{day: mean of `vals` (a {day: number} dict) over that day and the n-1 (AVG_DAYS-1) calendar days before it},
    for each of `days` (sorted ET days); a day missing from `vals` counts as 0; days before min(vals) are left out."""
    if not vals:
        return {}
    first = min(vals)
    out = {}
    for day in days:
        span, d = [], day
        for _ in range(n):
            if d < first:
                break
            span.append(vals.get(d, 0.0))
            d = prev_day(d)
        out[day] = (sum(span) / len(span)) if span else None
    return out


# ---- which bots are drawn ------------------------------------------------------------------------------------------
def bot_stopped(bs, name, prows, ok):
    """True when its stop file is set, or the process table was read and holds no live copy of it -- not ACTIVE
    (botstats.is_active, v-tg-active 2026-10-30: the coin race RUNS with its stop file set and is stopped here)."""
    if hasattr(bs, "is_active") and name not in getattr(bs, "ALWAYS_SHOWN", ()):
        return not bs.is_active(name, prows, ok)
    if os.path.exists(os.path.join(bs.RESULTS, bs.SPEC[name]["stop"])):
        return True
    return bool(ok) and not any(bs.is_bot(name, r[2]) for r in (prows or []))


def fold(bs, name, prows, ok):
    """v-tg-active: a bot that is not ACTIVE is drawn and counted as 'earlier' (one colour, one key, one row), never by
    its own name; 'other' and the active bots keep theirs."""
    if name in bs.SPEC and hasattr(bs, "is_active") and not bs.is_active(name, prows, ok):
        return "earlier"
    return name


# ---- every bot's markets, from botstats (Kalshi's books, every pot) -------------------------------------------------
def all_markets(bs, now, getter=None, procs=None):
    """Every bot's settled markets from botstats, whole: (bs, c, process rows, process table read?, pot context,
    [(bot, botstats.market row)] by settled time, [bots whose pots could not be read])."""
    c, prows, ok = bs._load(now, getter, procs)
    today = bs.et_day(now)
    pctx_ = bs.pot_context(c, today)
    out, missing = [], []
    for name in tuple(bs.BOTS) + ("other",):
        blk = bs._money_block(c, name, today, pctx_)
        key = fold(bs, name, prows, ok)                 # a hidden bot's markets are 'earlier' (v-tg-active)
        if not blk.get("ok"):
            if key not in missing:
                missing.append(key)
            continue
        out += [(key, m) for m in blk.get("markets") or [] if m["t"] is not None and m["day"]]
    out.sort(key=lambda r: r[1]["t"])
    return bs, c, prows, ok, pctx_, out, missing


def all_day_markets(bs, now, getter=None, procs=None):
    """Every bot's settled markets from botstats (the /bots source, Kalshi's books, every pot):
    (bs, pot context, [(ET close day, settled epoch, $, bot)] by time, [pots that could not be read])."""
    bs, _c, _prows, _ok, pctx_, ms, missing = all_markets(bs, now, getter, procs)
    return bs, pctx_, [(m["day"], m["t"], m["money"], name) for name, m in ms], missing


def all_losses(bs, now, getter=None, procs=None, week_days=7):
    """Every bot's LOSING markets from botstats (the /bots source, Kalshi's books, every pot). Operator 10-26: "Make
    it so /losses outputs losses not just for pin and race and show which bot it lost" -- /losses was the main
    account only (pin + race, one row a quarter-hour). (bs, losers newest day first and newest settled first in a
    day, {bot: totals}, [bots whose pots could not be read]). A loser is botstats.market's row plus bot, pot (that
    bot's pot when its day began + money moved in that day: botstats.day_pot, the /bots base) and pct (None when
    the pot is unknown -- never a guessed base). Totals: settled, lost, lost_7d, money_lost, worst."""
    c, _prows, _ok = bs._load(now, getter, procs)
    today = bs.et_day(now)
    pctx_ = bs.pot_context(c, today)
    week = {bs.shift_day(today, -k) for k in range(week_days)}
    out, per, missing, pots = [], {}, [], {}
    for name in tuple(bs.BOTS) + ("other",):
        blk = bs._money_block(c, name, today, pctx_)
        if not blk.get("ok"):
            missing.append(fold(bs, name, _prows, _ok))
            continue
        subs = bs.bot_subs(name)
        key = subs if len(subs) > 1 else subs[0]
        ms = blk.get("markets") or []
        lost = [m for m in ms if m["money"] < -0.004]
        won_days = {}
        for m in ms:
            if m["money"] > 0.004 and m["day"]:
                won_days[m["day"]] = won_days.get(m["day"], 0.0) + m["money"]
        per[name] = {"settled": len(ms), "lost": len(lost), "lost_7d": sum(1 for m in lost if m["day"] in week),
                     "money_lost": round(sum(m["money"] for m in lost), 4),
                     "worst": min((m["money"] for m in lost), default=None),
                     "won_days": won_days}                  # ET day -> $ its winning markets made (the chart)
        for m in lost:
            if (key, m["day"]) not in pots:
                pots[(key, m["day"])] = bs.day_pot(pctx_, key, m["day"]) if m["day"] else None
            pot = pots[(key, m["day"])]
            out.append(dict(m, bot=name, pot=pot, pct=(100.0 * m["money"] / pot) if pot else None))
    # v-tg-active: every paused or retired bot's losses on ONE 'earlier' row (each loss keeps its own pot's %)
    folded = {n: fold(bs, n, _prows, _ok) for n in per}
    if any(f != n for n, f in folded.items()):
        merged = {}
        for n, p in per.items():
            q = merged.setdefault(folded[n], {"settled": 0, "lost": 0, "lost_7d": 0, "money_lost": 0.0, "worst": None,
                                              "won_days": {}})
            for k in ("settled", "lost", "lost_7d", "money_lost"):
                q[k] = round(q[k] + p[k], 4) if k == "money_lost" else q[k] + p[k]
            if p["worst"] is not None and (q["worst"] is None or p["worst"] < q["worst"]):
                q["worst"] = p["worst"]
            for d, v in p["won_days"].items():
                q["won_days"][d] = q["won_days"].get(d, 0.0) + v
        per = {n: q for n, q in merged.items() if n != "earlier" or q["settled"]}
        for r in out:
            r["bot"] = folded.get(r["bot"], r["bot"])
    missing = sorted(set(missing), key=missing.index)
    out.sort(key=lambda r: (r["day"] or "", r["t"] or 0), reverse=True)
    return bs, out, per, missing


def by_now(rows, bs, day, now, n=AVG_DAYS):
    """(money so far on `day`, the average of the n days before it at the same ET clock -- rounded down to the
    quarter-hour, as /today's orange line is drawn -- and how many days were averaged) from all_day_markets' rows.
    The average is None when there is no earlier day. Days before the first market are left out."""
    d0 = bs.day_start(day)
    g = (max(0.0, now - d0) // 900) * 900
    so_far = sum(v for dd, _t, v, _b in rows if dd == day)
    first = min((r[0] for r in rows), default=None)
    ds, d = [], day
    for _ in range(n):
        d = bs.shift_day(d, -1)
        if first is not None and d >= first:
            ds.append(d)
    if not ds:
        return so_far, None, 0
    tot = 0.0
    for d in ds:
        t0 = bs.day_start(d)
        tot += sum(v for dd, t, v, _b in rows if dd == d and min(max(t, t0), t0 + 86400) - t0 <= g)
    return so_far, tot / len(ds), len(ds)


# ---- deposit-neutral money over time (v-tg-neutral, rebuild step 12, 2026-10-30) ----------------------------------
# The operator: "Robinhood ... the shape of the graph is only affected by the trading and a withdrawal or deposit
# doesn't spike or change it at all ... acting like it's always been the [balance] it's currently at ... this applies to
# all charts on graphs anywhere and everywhere". A money-over-time line is drawn as
#     value(t) = the money now - the trading after t
# = balance(t) + every deposit, withdrawal and transfer (in or out of that pot, between pots too) made after t, when
# Kalshi's books explain the pot. Only trading (each settlement, fees in) moves the line; the last point IS the money
# now. Lines that are already trading only (running totals, a day's pace) are unchanged; percentages of a bank keep
# their own rule (what the pot held when the window began, botdata.pots).
NEUTRAL_NOTE = "deposits and transfers removed"


def trading_only(grid, trades, end):
    """[(t, end - the trading after t)] for each t of `grid` (epochs, ascending; its last one is 'now'): `trades`
    [(epoch, $)] are the account's trading events (settlements); one after the last grid point is not counted (it is
    not in 'now' either). A deposit, withdrawal or transfer is not a trade, so it never moves the line, and the last
    point is `end` (the money now)."""
    if not grid:
        return []
    t_end = grid[-1]
    ts = sorted((t, v) for t, v in trades if t is not None and t <= t_end)
    times = [t for t, _v in ts]
    after = [0.0] * (len(ts) + 1)                     # after[k] = the trading of ts[k:]
    for k in range(len(ts) - 1, -1, -1):
        after[k] = after[k + 1] + ts[k][1]
    return [(g, end - after[bisect.bisect_right(times, g)]) for g in grid]


# ---- one account's money over time (/funds) -----------------------------------------------------------------------
def account_series(bs, c, sub, now, window_days=WINDOW_DAYS, neutral=False):
    """[(epoch, dollars)] for pot `sub`, or a tuple of pots added up (the FX taker's 5 + 4): money moved in
    (botstats.flows) + every settlement (botstats.market), hour by hour, worked forward from Kalshi's books; plus the
    pot now (botstats._pot_now) or why not, and each pot's part now (None for one pot). A pool-only pot
    (botstats.POT_POOL_ONLY: subaccount 4 = its pool 0) counts its own pool's money, cash and markets only.
    neutral=True (v-tg-neutral, the /funds picture): the same hours drawn deposit-neutral (trading_only) -- the pot
    now (or, when it cannot be read, the books' figure now) minus the settlements after each hour, so money moved in or
    out, and transfers between pots, never move the line."""
    subs = sub if isinstance(sub, tuple) else (sub,)
    led = c.get("ledgers") or {}
    sett = sorted((m["t"], m["money"]) for s in subs
                  for m in (bs.market(r) for r in bs.pot_rows((c.get("subs") or {}).get(s) or {}, s))
                  if m["t"] is not None)
    times = [t for t, _m in sett]
    cum, run = [], 0.0
    for _t, v in sett:
        run += v
        cum.append(run)
    flow_t = []
    if "0" in subs:
        for k in ("deposits", "withdrawals"):
            for r in led.get(k) or []:
                if bs.pinxfer.is_done(r) and bs.pinxfer.when(r) is not None:
                    flow_t.append(bs.pinxfer.when(r))
    for r in led.get("transfers") or []:
        t = bs._int(r.get("created_ts"))
        if t is not None and any(s in (str(r.get("to_subaccount")), str(r.get("from_subaccount"))) and bs.xfer_in_pot(r, s)
                                 for s in subs):
            flow_t.append(t)
    first = min(times[:1] + flow_t) if (times or flow_t) else None
    if first is None:
        return [], None, "nothing on Kalshi's books yet", None
    grid = list(range(max(int(first) - 1800, int(now - window_days * 86400)), int(now), 3600)) + [now]
    pts = []
    for g in grid:
        k = bisect.bisect_right(times, g)
        pts.append((g, bs.flows(led, sub, None, g + 1e-6) + (cum[k - 1] if k else 0.0)))
    nows = [bs._pot_now(c, s, own=True) for s in subs]
    why = next((w for v, w in nows if v is None), None)
    v = None if why is not None else sum(v for v, _w in nows)
    if neutral and pts:
        pts = trading_only([g for g, _y in pts], sett, v if v is not None else pts[-1][1])
    return pts, v, why, ([v_ for v_, _w in nows] if len(subs) > 1 else None)


# ---- the coin race: one race = the legs of one event ----------------------------------------------------------------
def race_rows(bs, c, name="race"):
    """The coin race from botstats' rows: [(close epoch, race net, won, tie)] -- a race = the legs of one event;
    a TIE when any leg settled at 50c (Kalshi's `value`), WON when not a tie and its net >= 0 (races_from's rule).
    v-tg-rebuild step 8 (2026-10-30): the race's pot and its markets come from the registry (its pot's subaccount,
    bots.owner) -- the same subaccount 0 and the same owner rule botstats.owner had."""
    sub = bots.bot_subs(name)[0]
    rows = ((c.get("subs") or {}).get(sub) or {}).get("rows") or {}
    ev = {}
    for s in rows.values():
        if bots.owner(s.get("ticker"), sub) != name:
            continue
        m = bs.market(s)
        if m["t"] is None:
            continue
        e = ev.setdefault(m["ticker"].rsplit("-", 1)[0], {"t": m["t"], "net": 0.0, "tie": False})
        e["t"] = min(e["t"], m["t"])
        e["net"] += m["money"]
        try:
            v = float(s.get("value"))
            e["tie"] = e["tie"] or (0.0 < v < 100.0)
        except (TypeError, ValueError):
            pass
    out = [(e["t"], e["net"], (not e["tie"]) and e["net"] >= 0, e["tie"]) for e in ev.values()]
    out.sort()
    return out


# ---- today's pace, one bot ------------------------------------------------------------------------------------------
def day_base(bs, pctx_, sub, day):
    """What pot `sub` held at midnight ET starting `day`, + money moved in during that day -- botstats.pot_for's
    rule for one day (so a mid-day top-up only ever makes that day's % smaller). None when it cannot be known.
    It IS botstats.day_pot, which also falls back to the last good read when the latest one failed."""
    if any((pctx_.get("subs") or {}).get(s) is None for s in (sub if isinstance(sub, tuple) else (sub,))):
        return None
    return bs.day_pot(pctx_, sub, day)


def pace_curves(bs, pctx_, sub, ms, today, now):
    """{'today': [(hour, cum %)], 'yesterday': [...], 'avg7': [...] (the mean of the PACE_DAYS days before today,
    on a 15-minute grid; days before the bot's first market are left out), 'n7': days averaged, 'avg30' / 'n30': the
    same over the LONG_DAYS days before today (10-29; None when it would count no more days than avg7), 'unit': '%'}. A day
    whose base is unknown is left out. When TODAY's base is unknown (no good balance read at all), every curve is
    in dollars instead ('unit': '$') -- the panel is never left blank (operator 10-23: 'the top most one was blank')."""
    dollars = day_base(bs, pctx_, sub, today) is None

    def curve(day):
        base = 100.0 if dollars else day_base(bs, pctx_, sub, day)       # 100 * cum / 100 = the dollars themselves
        if base is None:
            return None
        t0 = bs.day_start(day)
        pts, cum = [(0.0, 0.0)], 0.0
        for m in ms:
            if bs.et_day(m["t"]) == day:
                cum += m["money"]
                pts.append(((m["t"] - t0) / 3600.0, 100.0 * cum / base))
        return pts

    def at(pts, h):
        v = 0.0
        for x, y in pts:
            if x > h:
                break
            v = y
        return v
    first = min((m["t"] for m in ms), default=None)
    out = {"today": curve(today), "yesterday": curve(bs.shift_day(today, -1)), "avg7": None, "n7": 0,
           "avg30": None, "n30": 0, "unit": "$" if dollars else "%"}
    if out["today"] is not None:
        out["today"].append((min(24.0, (now - bs.day_start(today)) / 3600.0), out["today"][-1][1]))
    if out["yesterday"] is not None:
        out["yesterday"].append((24.0, out["yesterday"][-1][1]))
    grid = [i / 4.0 for i in range(0, 97)]
    for n_, key, nkey in ((PACE_DAYS, "avg7", "n7"), (LONG_DAYS, "avg30", "n30")):
        days = [bs.shift_day(today, -k) for k in range(1, n_ + 1)]
        cs = [c for d in days if first is not None and bs.day_start(bs.shift_day(d, 1)) > first
              for c in [curve(d)] if c is not None]
        if cs and len(cs) > out["n7"]:                   # the 30-day curve only when it counts more days than the 7
            out[key] = [(h, sum(at(c, h) for c in cs) / len(cs)) for h in grid]
            out[nkey] = len(cs)
    return out


def at_hour(pts, h):
    """The step curve `pts` [(hour, value)] at hour h (0 before its first point)."""
    v = 0.0
    for x, y in pts:
        if x > h:
            break
        v = y
    return v
