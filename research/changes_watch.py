#!/usr/bin/env python3
"""changes_watch.py -- READ-ONLY daily report on the main bot's recent live changes.

For each change, since the moment it went LIVE: the money it made, the money it
gave up, the losses it caused, and a one-line verdict against its stop rule.
The operator's only rule for a change: keep it only if it makes MORE money.

    python -I research/changes_watch.py              # the report
    python -I research/changes_watch.py --json       # same numbers, machine-readable
    python -I research/changes_watch.py --selftest

SOURCES (every number in the output names one of these):
  [K]  results/kalshi_ledger.json -- Kalshi /portfolio/settlements, main account,
       read through research/pinledger.py (pnl(), payout()). Market money,
       contracts held per side, cost per side, fees.
  [L]  results/pinrun-live-*.jsonl -- the live bot's own records: start (flags),
       order (filled, exec_price, fee_total -- Kalshi's fill reply), band_boost,
       hedge_alarm (trigger belief/jump), hedge (fill), hedge_quote (belief + ask
       every second a position is held), refused, settled.
  [T]  results/pintraj-live-*.jsonl -- only to infer the result of a market the
       bot never traded (a refused 95.5c-floor buy); marked "inferred".

CHANGES WATCHED
  1 v-band15     --band-mult 0.955 0.981 1.5, LIVE 2026-10-21 11:01Z.
                 Extra contracts = filled on a band_boost decision minus the
                 pre-boost size `was` the bot recorded (what it would have sent
                 at 1.0x). Their money = extra x (Kalshi per-contract payout of
                 our side - that order's exec price) - their share of that
                 order's fee + their pro-rata share of the hedge leg's money.
  2 v-hedgejump6 --hedge-jump 6, live from the first start record with hedge_jump
                 set. Each hedge_alarm with trigger "jump": the hedge actually
                 bought vs what the 0.40 belief line alone would have bought
                 (the same contracts at the hedge-side ask of the first second
                 the bot's belief went under 0.40; nothing if it never did).
                 The counterfactual is priced at the ASK, the real hedge at its
                 FILL, so the comparison leans against the jump (conservative).
                 STOP RULE: first 10 jump-fired hedges net below -$50 -> remove.
  3 floor 95.5c  live from the first start record carrying an entry floor key
                 (entry_min_price / min_entry_price / entry_floor) >= 0.95.
                 Before then: SHADOW -- every entry the bot really bought with
                 ask_seen < 95.5c since --floor-since, scored on Kalshi money.
                 After: every refused record whose gate names the floor, one per
                 market, scored at the refused price and size.
  4 v-nopause    --max-losses 2 -> 0, LIVE 2026-10-18 11:01:21Z. Replays the old
                 brake on Kalshi market money: count losing markets per run, a
                 2nd loss halts the run, watch_bot restarts ~15 min later
                 (--pause-min) and the count resets. Money the pause would have
                 given up = Kalshi net of markets first entered inside a pause.

Writes nothing. Stops nothing. Places nothing.
"""
import argparse
import calendar
import collections
import glob
import json
import math
import os
import sys
import time

REPO = r"C:\kals-repo"
RESEARCH = os.path.join(REPO, "research")
RESULTS = os.path.join(REPO, "results")
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
import pinledger                                                   # noqa: E402

BAND_LIVE = "2026-10-21T11:01:51Z"
NOPAUSE_LIVE = "2026-10-18T11:01:21Z"
HEDGE_BELIEF = 0.40
JUMP_STOP_N, JUMP_STOP_USD = 10, -50.0
FLOOR = 0.955
FLOOR_KEYS = ("entry_min_price", "min_entry_price", "entry_floor", "entry_min")
FLOOR_GATES = ("entry_min_price", "entry_min", "min_entry_price", "entry_floor")
ENTRY_LEGS = ("early", "full", "topup", "late_add", "rebuy")
KINDS = ("start", "order", "band_boost", "hedge_alarm", "hedge", "hedge_quote",
         "refused", "settled", "signal")


def ts(t):
    t = t.rstrip("Z").split(".")[0]
    return calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))


def iso(s):
    return time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(s))


def et_day(s):
    """ET calendar day: EDT (UTC-4) 2nd Sun Mar .. 1st Sun Nov, else EST."""
    y = time.gmtime(s).tm_year
    mar = calendar.timegm((y, 3, 8, 7, 0, 0))
    mar += ((6 - time.gmtime(mar).tm_wday) % 7) * 86400
    nov = calendar.timegm((y, 11, 1, 6, 0, 0))
    nov += ((6 - time.gmtime(nov).tm_wday) % 7) * 86400
    off = -4 if mar <= s < nov else -5
    return time.strftime("%Y-%m-%d", time.gmtime(s + off * 3600))


def fee_est(n, p):
    """Kalshi taker fee, 7% of n*p*(1-p), rounded up to the cent per order."""
    if not n or p is None:
        return 0.0
    return math.ceil(0.07 * n * p * (1.0 - p) * 100.0 - 1e-9) / 100.0


# ---------------------------------------------------------------- Kalshi [K]
def load_kalshi(path=None):
    """ticker -> {net, yes_n, no_n, yes_cost, no_cost, fee, v (yes payout/ct)}"""
    rows = pinledger.load_cache(path or pinledger.LEDGER)
    out = {}
    for s in rows.values():
        tk = s.get("ticker")
        m = out.setdefault(tk, dict(net=0.0, yes_n=0.0, no_n=0.0, yes_cost=0.0,
                                    no_cost=0.0, fee=0.0, v=None, settled=None))
        m["net"] += pinledger.pnl(s)
        m["yes_n"] += pinledger.money(s, "yes_count_fp")
        m["no_n"] += pinledger.money(s, "no_count_fp")
        m["yes_cost"] += pinledger.money(s, "yes_total_cost_dollars")
        m["no_cost"] += pinledger.money(s, "no_total_cost_dollars")
        m["fee"] += pinledger.money(s, "fee_cost")
        val = s.get("value")
        try:
            m["v"] = float(val) / 100.0
        except (TypeError, ValueError):
            res = str(s.get("market_result") or "").lower()
            m["v"] = 1.0 if res == "yes" else 0.0 if res == "no" else m["v"]
        m["settled"] = s.get("settled_time")
    return out


def side_pay(k, side):
    """Kalshi payout per contract of `side` (1.0 win, 0.0 loss, 0.5 tie)."""
    if k is None or k.get("v") is None:
        return None
    return k["v"] if side == "yes" else 1.0 - k["v"]


def opp(side):
    return "no" if side == "yes" else "yes"


def hedge_leg_net(k, our_side):
    """Kalshi money on the OPPOSITE side of our bet (the insurance leg), fee
    estimated by the formula on its average price."""
    o = opp(our_side)
    n, cost = k.get(o + "_n", 0.0), k.get(o + "_cost", 0.0)
    if n <= 0:
        return 0.0
    return n * side_pay(k, o) - cost - fee_est(n, cost / n)


# ---------------------------------------------------------------- logs [L]
def live_files(since_s, results=RESULTS):
    out = []
    for fn in glob.glob(os.path.join(results, "pinrun-live-*.jsonl")):
        if os.path.getmtime(fn) >= since_s:
            out.append(fn)
    return sorted(out)


def read_logs(files):
    """One pass. Returns starts, per-ticker records, and band decisions with
    the fills that followed each (until the next signal for that ticker)."""
    starts, orders, alarms, hedges, quotes, refused, settled = [], [], [], [], [], [], []
    boosts, open_boost = [], {}
    pre = tuple('"kind": "%s"' % k for k in KINDS)
    for fn in files:
        with open(fn, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not any(p in line for p in pre):
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                k, tk = d.get("kind"), d.get("ticker")
                if k == "start":
                    starts.append(d)
                elif k == "signal":
                    open_boost.pop(tk, None)
                elif k == "band_boost":
                    b = dict(d, filled=0.0, fills=[])
                    boosts.append(b)
                    open_boost[tk] = b
                elif k == "order":
                    if d.get("leg") in ENTRY_LEGS and (d.get("filled") or 0) > 0:
                        orders.append(d)
                        b = open_boost.get(tk)
                        if b is not None:
                            b["filled"] += float(d["filled"])
                            b["fills"].append(d)
                elif k == "hedge_alarm":
                    alarms.append(d)
                elif k == "hedge":
                    hedges.append(d)
                elif k == "hedge_quote":
                    quotes.append(d)
                elif k == "refused":
                    g = str(d.get("gate") or "")
                    if any(x in g for x in FLOOR_GATES):
                        refused.append(d)
                elif k == "settled":
                    settled.append(d)
    return dict(starts=starts, orders=orders, alarms=alarms, hedges=hedges,
                quotes=quotes, refused=refused, settled=settled, boosts=boosts)


def first_start(starts, pred):
    for s in sorted(starts, key=lambda r: r["t"]):
        if pred(s):
            return s
    return None


# ---------------------------------------------------------------- 1 band
def band_report(L, K, live_s):
    rows = []
    for b in L["boosts"]:
        if ts(b["t"]) < live_s:
            continue
        extra = max(0.0, b["filled"] - float(b.get("was") or 0.0))
        k = K.get(b["ticker"])
        row = dict(t=b["t"], ticker=b["ticker"], want=b["want"], price=b["price"],
                   size=b.get("size"), was=b.get("was"), now=b.get("now"),
                   filled=round(b["filled"], 2), extra=round(extra, 2),
                   pnl=None, status="open" if k is None else "settled")
        if extra > 0 and k is not None:
            pay = side_pay(k, b["want"])
            money, rem = 0.0, extra
            # extra contracts are the LAST ones filled on this decision
            for o in reversed(b["fills"]):
                take = min(rem, float(o["filled"]))
                if take <= 0:
                    break
                px = float(o.get("exec_price") or o.get("ask_seen") or b["price"])
                fee = float(o.get("fee_total") or 0.0) * take / float(o["filled"])
                money += take * (pay - px) - fee
                rem -= take
            side_n = k.get(b["want"] + "_n", 0.0)
            hshare = hedge_leg_net(k, b["want"]) * (extra / side_n) if side_n > 0 else 0.0
            row["pnl"] = round(money + hshare, 2)
            row["hedge_share"] = round(hshare, 2)
            row["kalshi_market_net"] = round(k["net"], 2)
        elif extra > 0:
            row["status"] = "open"
        rows.append(row)
    done = [r for r in rows if r["pnl"] is not None]
    return dict(rows=rows,
                decisions=len(rows),
                with_extra=sum(1 for r in rows if r["extra"] > 0),
                extra_contracts=round(sum(r["extra"] for r in rows), 2),
                pnl=round(sum(r["pnl"] for r in done), 2),
                won=round(sum(r["pnl"] for r in done if r["pnl"] > 0), 2),
                losses=round(sum(r["pnl"] for r in done if r["pnl"] < 0), 2),
                losing_markets=sum(1 for r in done if r["pnl"] < 0),
                open=sum(1 for r in rows if r["extra"] > 0 and r["pnl"] is None))


# ---------------------------------------------------------------- 2 jump
def jump_report(L, K, live_s):
    if live_s is None:
        return dict(live=False, rows=[], n=0, net=0.0)
    q_by = collections.defaultdict(list)
    for q in L["quotes"]:
        q_by[q["ticker"]].append(q)
    h_by = collections.defaultdict(list)
    for h in L["hedges"]:
        if h.get("status") in ("executed", "partially_filled_then_canceled") or (h.get("n") or 0) > 0:
            h_by[h["ticker"]].append(h)
    rows, seen = [], set()
    for a in sorted(L["alarms"], key=lambda r: r["t"]):
        if a.get("trigger") != "jump" or ts(a["t"]) < live_s or a["ticker"] in seen:
            continue
        seen.add(a["ticker"])
        tk, want, n = a["ticker"], a["want"], float(a.get("n") or 0.0)
        k = K.get(tk)
        at = ts(a["t"])
        hs = [h for h in h_by[tk] if ts(h["t"]) >= at - 1]
        hn = sum(float(h.get("n") or 0.0) for h in hs)
        hcost = sum(float(h.get("n") or 0.0) * float(h.get("price") or 0.0) for h in hs)
        # when the 0.40 line alone would have fired: the alarm second if its
        # belief was already under the line, else the first quote under it
        fire = None
        if a.get("belief") is not None and float(a["belief"]) < HEDGE_BELIEF:
            fire = at
        qs = sorted(q_by[tk], key=lambda r: r["t"])
        cf_ask = None
        for q in qs:
            qt = ts(q["t"])
            if qt < at:
                continue
            if fire is None and q.get("belief") is not None and float(q["belief"]) < HEDGE_BELIEF:
                fire = qt
            if fire is not None and qt >= fire and q.get("ask") is not None:
                cf_ask = float(q["ask"])
                break
        row = dict(t=a["t"], ticker=tk, want=want, n=n, jump_sd=a.get("jump_sd"),
                   belief_at_alarm=a.get("belief"), hedge_n=round(hn, 2),
                   hedge_avg=round(hcost / hn, 4) if hn else None,
                   belief_fire=iso(fire) if fire else None, cf_ask=cf_ask,
                   actual=None, cf=None, diff=None)
        if k is not None:
            pay = side_pay(k, opp(want))
            # the insurance leg as KALSHI booked it (opposite-side contracts and
            # cost), so a partial fill or a later belief top-up is counted once
            kn, kc = k.get(opp(want) + "_n", 0.0), k.get(opp(want) + "_cost", 0.0)
            if kn > 0:
                hn, hcost = kn, kc
                row.update(hedge_n=round(hn, 2), hedge_avg=round(hcost / hn, 4))
            actual = hn * pay - hcost - fee_est(hn, hcost / hn if hn else None)
            if fire == at:
                cf = actual           # belief was already under 0.40: the jump changed nothing
            elif fire is None:
                cf = 0.0
            elif cf_ask is None:      # line crossed but no ask left to buy
                cf = 0.0
            else:
                cf = n * (pay - cf_ask) - fee_est(n, cf_ask)
            row.update(actual=round(actual, 2), cf=round(cf, 2),
                       diff=round(actual - cf, 2), result=k.get("v"))
        rows.append(row)
    run, first = 0.0, []
    for r in rows:
        if r["diff"] is None:
            continue
        if len(first) < JUMP_STOP_N:
            first.append(r)
            run += r["diff"]
        r["running_first10"] = round(run, 2) if r in first else None
    return dict(live=True, rows=rows, n=len(rows), scored=len(first),
                net_first10=round(run, 2),
                net_all=round(sum(r["diff"] for r in rows if r["diff"] is not None), 2))


# ---------------------------------------------------------------- 3 floor
def traj_result(tickers, results=RESULTS, since_s=0):
    """Inferred YES payout for markets the bot never traded: the bot's own
    fair P(YES) at the smallest tau it logged (>= 0.98 -> 1, <= 0.02 -> 0)."""
    want, best = set(tickers), {}
    if not want:
        return {}
    for fn in glob.glob(os.path.join(results, "pintraj-live-*.jsonl")):
        if os.path.getmtime(fn) < since_s:
            continue
        with open(fn, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                tk0 = line[13:13 + 40]
                if not any(t in tk0 for t in want):
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                tk = d.get("ticker")
                if tk in want and d.get("fair") is not None:
                    if tk not in best or d.get("tau", 999) <= best[tk][0]:
                        best[tk] = (d.get("tau", 999), float(d["fair"]))
    out = {}
    for tk, (tau, f) in best.items():
        if tau <= 5 and (f >= 0.98 or f <= 0.02):
            out[tk] = 1.0 if f >= 0.98 else 0.0
    return out


def floor_report(L, K, live_s, shadow_since_s):
    rows = []
    if live_s is None:          # SHADOW: the buys the floor WOULD have refused
        by = collections.defaultdict(list)
        for o in L["orders"]:
            if ts(o["t"]) < shadow_since_s:
                continue
            px = o.get("ask_seen")
            if px is None or float(px) >= FLOOR - 1e-9:
                continue
            by[o["ticker"]].append(o)
        for tk, os_ in by.items():
            k = K.get(tk)
            want = os_[0]["want"]
            n = sum(float(o["filled"]) for o in os_)
            row = dict(t=os_[0]["t"], ticker=tk, want=want, n=round(n, 2),
                       ask=min(float(o["ask_seen"]) for o in os_), pnl=None,
                       source="K+L")
            if k is not None:
                pay = side_pay(k, want)
                m = sum(float(o["filled"]) * (pay - float(o.get("exec_price") or o["ask_seen"]))
                        - float(o.get("fee_total") or 0.0) for o in os_)
                side_n = k.get(want + "_n", 0.0)
                hs = hedge_leg_net(k, want) * (n / side_n) if side_n > 0 else 0.0
                row.update(pnl=round(m + hs, 2), hedge_share=round(hs, 2))
            rows.append(row)
    else:                       # LIVE: refused records from the floor gate
        first = {}
        for r in sorted(L["refused"], key=lambda r: r["t"]):
            if ts(r["t"]) >= live_s and r.get("ticker") not in first:
                first[r["ticker"]] = r
        need = [tk for tk in first if tk not in K]
        inferred = traj_result(need, since_s=live_s)
        for tk, r in first.items():
            want = r.get("want") or r.get("wanted_side")
            px = r.get("price")
            n = min(float(r.get("size") or 0.0), float(r.get("size_now") or 1e9))
            v = K[tk]["v"] if tk in K else inferred.get(tk)
            row = dict(t=r["t"], ticker=tk, want=want, n=round(n, 2), ask=px,
                       pnl=None, source="K" if tk in K else ("T inferred" if v is not None else "-"))
            if v is not None and px is not None and want:
                pay = v if want == "yes" else 1.0 - v
                row["pnl"] = round(n * (pay - float(px)) - fee_est(n, float(px)), 2)
            rows.append(row)
    done = [r for r in rows if r["pnl"] is not None]
    gave_up = round(sum(r["pnl"] for r in done if r["pnl"] > 0), 2)
    avoided = round(-sum(r["pnl"] for r in done if r["pnl"] < 0), 2)
    return dict(live=live_s is not None, rows=rows, n=len(rows),
                gave_up=gave_up, avoided=avoided, net_effect=round(avoided - gave_up, 2),
                open=len(rows) - len(done))


# ---------------------------------------------------------------- 4 nopause
def nopause_report(L, K, live_s, pause_min):
    first_entry = {}
    for o in L["orders"]:
        s = ts(o["t"])
        if o["ticker"] not in first_entry or s < first_entry[o["ticker"]]:
            first_entry[o["ticker"]] = s
    mk = []
    for tk, s in first_entry.items():
        k = K.get(tk)
        if k is None or s < live_s:
            continue
        st = ts(k["settled"]) if k.get("settled") else s
        mk.append((st, tk, k["net"], s))
    mk.sort()
    run_starts = sorted(ts(s["t"]) for s in L["starts"] if ts(s["t"]) >= live_s)
    pauses, count, si, until = [], 0, 0, None
    for st, tk, net, _ in mk:
        while si < len(run_starts) and run_starts[si] <= st:
            count, si = 0, si + 1          # a real restart resets the count
        if until is not None and st <= until:
            continue                        # settled while paused: already open
        if net < -0.005:
            count += 1
            if count >= 2:
                until = st + pause_min * 60
                pauses.append(dict(t=iso(st), ticker=tk, net=round(net, 2), until=iso(until), _a=st, _b=until))
                count = 0
    given = []
    for p in pauses:
        a, b = p["_a"], p["_b"]
        inside = [(tk, net) for st, tk, net, fe in mk if a < fe <= b]
        p["markets_skipped"] = len(inside)
        p["money_skipped"] = round(sum(n for _, n in inside), 2)
        given.append(p["money_skipped"])
    days = sorted({et_day(p["_a"]) for p in pauses})
    return dict(markets=len(mk), losing=sum(1 for m in mk if m[2] < -0.005),
                pauses=pauses, pause_days=days,
                money_in_pauses=round(sum(given), 2))


# ---------------------------------------------------------------- output
def table(head, rows):
    w = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
         for i, h in enumerate(head)]
    out = ["  " + "  ".join(str(h).ljust(w[i]) for i, h in enumerate(head)),
           "  " + "  ".join("-" * x for x in w)]
    for r in rows:
        out.append("  " + "  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))
    return "\n".join(out)


def usd(x):
    return "-" if x is None else ("%+.2f" % x)


def render(R):
    o = []
    o.append("CHANGES WATCH  %s   (now %s)" % (R["window"], R["now"]))
    o.append("sources: [K] %s (%d settlements)   [L] %d live logs: %s" % (
        R["ledger"], R["ledger_rows"], len(R["files"]),
        ", ".join(os.path.basename(f) for f in R["files"])))
    o.append("")
    b = R["band"]
    o.append("1) v-band15  --band-mult 0.955 0.981 1.5   LIVE %s [L start record]" % R["band_live"])
    o.append(table(["t (UTC)", "ticker", "side", "ask", "SIZE", "was", "filled", "extra", "extra $ [K+L]"],
                   [[r["t"][5:16], r["ticker"], r["want"], r["price"], r["size"], r["was"],
                     r["filled"], r["extra"], usd(r["pnl"]) if r["extra"] > 0 else "-"]
                    for r in b["rows"]]))
    o.append(table(["band decisions", "with extra", "extra contracts", "extra $ net", "won", "losses caused", "losing mkts", "open"],
                   [[b["decisions"], b["with_extra"], b["extra_contracts"], usd(b["pnl"]),
                     usd(b["won"]), usd(b["losses"]), b["losing_markets"], b["open"]]]))
    o.append("   VERDICT: " + R["verdict_band"])
    o.append("")
    j = R["jump"]
    o.append("2) v-hedgejump6  --hedge-jump 6   %s" % (
        ("LIVE %s [L start record hedge_jump=%s]" % (R["jump_live"], R["jump_val"])) if j["live"]
        else "NOT LIVE YET (no start record with hedge_jump set; installed for the next restart)"))
    o.append(table(["t (UTC)", "ticker", "side", "n", "jump sd", "hedge n@avg", "0.40 line fires", "cf ask", "jump $ [K]", "0.40-only $", "diff", "run (first 10)"],
                   [[r["t"][5:16], r["ticker"], r["want"], r["n"], r["jump_sd"],
                     "%s@%s" % (r["hedge_n"], r["hedge_avg"]), r["belief_fire"] or "never",
                     r["cf_ask"], usd(r["actual"]), usd(r["cf"]), usd(r["diff"]),
                     usd(r.get("running_first10"))] for r in j["rows"]]))
    o.append(table(["jump hedges", "scored (first 10)", "net vs 0.40 line (first 10)", "net all", "stop line"],
                   [[j["n"], j.get("scored", 0), usd(j.get("net_first10")), usd(j.get("net_all")), "-50.00 after 10"]]))
    o.append("   VERDICT: " + R["verdict_jump"])
    o.append("")
    f = R["floor"]
    o.append("3) 95.5c entry floor   %s" % (
        "LIVE %s [L start record]" % R["floor_live"] if f["live"]
        else "NOT LIVE YET -- SHADOW: entries really bought with ask < 95.5c since %s, Kalshi money" % R["floor_since"]))
    o.append(table(["t (UTC)", "ticker", "side", "ask", "contracts", "would-have $", "source"],
                   [[r["t"][5:16], r["ticker"], r["want"], r["ask"], r["n"], usd(r["pnl"]), r["source"]]
                    for r in f["rows"]]))
    o.append(table(["refused buys", "money given up (their wins)", "losses avoided", "floor net effect", "open"],
                   [[f["n"], usd(-f["gave_up"]), usd(f["avoided"]), usd(f["net_effect"]), f["open"]]]))
    o.append("   VERDICT: " + R["verdict_floor"])
    o.append("")
    p = R["nopause"]
    o.append("4) v-nopause  (--max-losses 2 -> 0)   LIVE %s; replay of the 2-loss pause (%d min) on [K] market money" % (NOPAUSE_LIVE[:16] + "Z", R["pause_min"]))
    o.append(table(["2nd loss at", "ticker", "loss $ [K]", "paused until", "mkts it would skip", "their $ [K]"],
                   [[x["t"], x["ticker"], usd(x["net"]), x["until"], x["markets_skipped"], usd(x["money_skipped"])]
                    for x in p["pauses"]]))
    o.append(table(["markets", "losing", "pauses", "ET days it would have paused", "money pauses would have given up"],
                   [[p["markets"], p["losing"], len(p["pauses"]), len(p["pause_days"]) and ",".join(p["pause_days"]) or "0",
                     usd(p["money_in_pauses"])]]))
    o.append("   VERDICT: " + R["verdict_nopause"])
    return "\n".join(o)


def verdicts(R):
    b, j, f, p = R["band"], R["jump"], R["floor"], R["nopause"]
    if b["with_extra"] == 0:
        R["verdict_band"] = "no extra contracts filled yet -- nothing to judge."
    else:
        R["verdict_band"] = ("%s: extra contracts net %s (losses caused %s on %d markets). Bar: keep while net >= 0; "
                             "pre-registered risk: erased by ~6 more losing markets than the 15 observed (VERSIONS.md)."
                             % ("KEEP" if b["pnl"] >= 0 else "LOSING", usd(b["pnl"]), usd(b["losses"]), b["losing_markets"]))
    if not j["live"]:
        R["verdict_jump"] = "not live -- 0 of 10 jump-fired hedges; stop rule not testable yet."
    elif j.get("scored", 0) >= JUMP_STOP_N:
        R["verdict_jump"] = ("STOP -- remove --hedge-jump" if j["net_first10"] < JUMP_STOP_USD else "PASS -- keep") + \
            " (first 10 net %s vs -$50 line)." % usd(j["net_first10"])
    else:
        R["verdict_jump"] = "%d of 10 scored, net %s vs the 0.40 line; %s" % (
            j.get("scored", 0), usd(j.get("net_first10")),
            "ALREADY BELOW -$50 (decides at 10)" if j.get("net_first10", 0) < JUMP_STOP_USD else "keep running.")
    if not f["live"]:
        R["verdict_floor"] = ("shadow only: the floor would have changed money by %s (avoided %s of losses, gave up %s of wins). "
                              "It makes MORE money only if this stays > 0." % (usd(f["net_effect"]), usd(f["avoided"]), usd(f["gave_up"])))
    else:
        R["verdict_floor"] = ("%s: floor net effect %s (losses avoided %s, wins given up %s). Bar: keep while >= 0 at the 14-day read."
                              % ("KEEP" if f["net_effect"] >= 0 else "COSTING MONEY", usd(f["net_effect"]), usd(f["avoided"]), usd(f["gave_up"])))
    R["verdict_nopause"] = ("%s: the old pause would have fired %d times on %d ET days and skipped markets worth %s. "
                            "No-pause makes more money while that is >= 0."
                            % ("KEEP no-pause" if p["money_in_pauses"] >= 0 else "the pause would have SAVED money",
                               len(p["pauses"]), len(p["pause_days"]), usd(p["money_in_pauses"])))


def build(a):
    now = time.time()
    K = load_kalshi(a.ledger)
    fs = a.floor_since if a.floor_since.endswith("Z") else a.floor_since + ":00Z"
    files = live_files(min(ts(NOPAUSE_LIVE), ts(fs)), a.results)
    L = read_logs(files)
    bstart = first_start(L["starts"], lambda s: s.get("band_mults") and ts(s["t"]) >= ts(BAND_LIVE) - 60)
    band_live = bstart["t"] if bstart else BAND_LIVE
    jstart = first_start(L["starts"], lambda s: s.get("hedge_jump") is not None)
    fstart = first_start(L["starts"], lambda s: any((s.get(k) or 0) >= 0.95 for k in FLOOR_KEYS))
    R = dict(now=iso(now), window="%s .. %s" % (NOPAUSE_LIVE[:16] + "Z", iso(now)),
             ledger=pinledger.LEDGER if not a.ledger else a.ledger, ledger_rows=sum(1 for _ in pinledger.load_cache(a.ledger or pinledger.LEDGER)),
             files=files, band_live=band_live,
             jump_live=jstart["t"] if jstart else None, jump_val=jstart.get("hedge_jump") if jstart else None,
             floor_live=fstart["t"] if fstart else None, floor_since=fs, pause_min=a.pause_min)
    R["band"] = band_report(L, K, ts(band_live))
    R["jump"] = jump_report(L, K, ts(jstart["t"]) if jstart else None)
    R["floor"] = floor_report(L, K, ts(fstart["t"]) if fstart else None, ts(fs))
    R["nopause"] = nopause_report(L, K, ts(NOPAUSE_LIVE), a.pause_min)
    verdicts(R)
    return R


def selftest():
    ok = 0
    K = {"A": dict(net=-50.0, yes_n=0.0, no_n=100.0, yes_cost=0.0, no_cost=96.0, fee=0.3, v=1.0, settled="2026-10-21T12:00:00Z")}
    assert side_pay(K["A"], "no") == 0.0 and side_pay(K["A"], "yes") == 1.0; ok += 1
    L = dict(boosts=[dict(t="2026-10-21T11:59:31Z", ticker="A", want="no", price=0.96, size=100.0, was=100.0, now=150.0,
                          filled=150.0, fills=[dict(filled=150.0, exec_price=0.96, fee_total=0.6)])],
             starts=[], orders=[], alarms=[], hedges=[], quotes=[], refused=[], settled=[])
    b = band_report(L, K, ts(BAND_LIVE))
    assert b["extra_contracts"] == 50.0 and abs(b["pnl"] - (50 * (0 - 0.96) - 0.2)) < 0.01, b; ok += 1
    L["alarms"] = [dict(t="2026-10-21T11:59:40Z", ticker="A", want="no", n=100.0, belief=0.9, trigger="jump", jump_sd=7.0)]
    L["hedges"] = [dict(t="2026-10-21T11:59:41Z", ticker="A", n=100.0, price=0.30, status="executed")]
    L["quotes"] = [dict(t="2026-10-21T11:59:45Z", ticker="A", ask=0.80, belief=0.3)]
    j = jump_report(L, K, 0)
    assert j["rows"][0]["actual"] == round(100 * 0.7 - fee_est(100, 0.3), 2), j; ok += 1
    assert j["rows"][0]["cf"] == round(100 * 0.2 - fee_est(100, 0.8), 2); ok += 1
    L["quotes"] = []
    assert jump_report(L, K, 0)["rows"][0]["cf"] == 0.0; ok += 1
    L["alarms"][0]["belief"] = 0.2
    r0 = jump_report(L, K, 0)["rows"][0]
    assert r0["diff"] == 0.0, r0; ok += 1
    assert et_day(ts("2026-10-22T03:00:00Z")) == "2026-10-21"; ok += 1
    print("selftest PASSED (%d checks)" % ok)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=RESULTS)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--floor-since", default=BAND_LIVE[:16], help="shadow start for the 95.5c floor (UTC)")
    ap.add_argument("--pause-min", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    R = build(a)
    if a.json:
        print(json.dumps(R, indent=1, default=str))
    else:
        print(render(R))


if __name__ == "__main__":
    main()
