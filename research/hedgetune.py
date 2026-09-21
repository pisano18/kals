#!/usr/bin/env python3
"""hedgetune.py -- where to set the hedge trigger, and how much to buy.

THE OPERATOR, 2026-09-21: "it'll definitely be right when it fires but not
fire on everything. I really need you to do the math to tune it to catch the
most it can while having enough certainty to offset as much total losses as
possible." And, correcting the objective: "It's not cutting losses that
matters it's losing the least amount of money."

THE TRADE-OFF, stated before any number is looked at. A hedge trigger is one
dial. Turn it up and we hedge more alarms -- catching more real losses, and
also more alarms that were going to be fine, which cost the whole premium.
Turn it down and every hedge is right but most losses go uncovered. There is
an optimum and it is a number, not an opinion.

WHY THIS FILE EXISTS AND THE EARLIER ANSWER DOES NOT COUNT. A first pass
scored every threshold at the price available AT THE ALARM SECOND. That is
only correct for an alarm whose confidence was ALREADY under the threshold
when it fired. For any lower threshold the bot has to WAIT for confidence to
fall, and the price of insurance rises as confidence falls -- that is exactly
what A76 did on 2026-09-21 and it paid 70c and then 90.5c for what was 39c
at the alarm. Scoring a wait at the pre-wait price flatters it by the whole
size of that effect.

So this file rebuilds, for every real-money alarm we have:

  * our model's CONFIDENCE second by second, from `pinrun.fair` on the raw
    1/sec index -- the same function the bot used, not a reimplementation;
  * the HEDGE PRICE and the SIZE OFFERED second by second, from the ticker
    tape;

and then, for a trigger T, buys at the FIRST second confidence falls under T,
at whatever insurance cost by then, capped by what was actually offered.

Nothing here is a fill. Every price is one that was quoted and every size is
one that was advertised. Our own fills are the 18 alarms themselves.

    python research/hedgetune.py --selftest
    python research/hedgetune.py --build      # rebuild the per-second table
    python research/hedgetune.py              # tune on the cached table
"""
import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

import racebook                                                # noqa: E402

TABLE = os.path.join(REPO, "flow_cache", "hedgetune_table.json")
LOOKBACK = 12          # seconds before the alarm to start watching
TRIGGERS = (0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10)


def fee(q, n):
    """Kalshi taker fee in dollars, rounded up to the cent per order."""
    if n <= 0:
        return 0.0
    return math.ceil(0.07 * n * q * (1.0 - q) * 100.0 - 1e-9) / 100.0


def hedge_outcome(prim, lost, n_hedge, price):
    """Dollars on the whole market -- the original bet plus the hedge leg.

    The hedge pays $1 a contract when the ORIGINAL BET LOST, because it is
    the other side of the same market."""
    if n_hedge <= 0 or not (0.0 < price < 1.0):
        return prim
    return prim + n_hedge * ((1.0 - price) if lost else -price) \
        - fee(price, n_hedge)


def simulate(events, trigger, mult=1.0, money=False, cap_depth=True,
             max_mult=None):
    """Hedge each alarm at the FIRST second its confidence falls under
    `trigger`, at the price quoted THEN.

    `money` sizes the hedge to cover the whole sum at risk, which is
    risk/(1-price) contracts; `mult` sizes it as a multiple of the position.
    Returns (total, fired, fired_on_real_losses, rows)."""
    total = 0.0
    fired = real = 0
    rows = []
    for e in events:
        path = e.get("path") or []
        hit = None
        for sec, bel, price, depth in path:
            if bel is not None and bel < trigger and price is not None \
                    and 0.0 < price < 1.0 and depth >= 1:
                hit = (sec, bel, price, depth)
                break
        if hit is None:
            total += e["prim"]
            rows.append((e, None, 0, e["prim"]))
            continue
        sec, bel, price, depth = hit
        risk = e["n"] * e["entry"]
        n = (risk / (1.0 - price)) if money else mult * e["n"]
        if max_mult is not None:
            n = min(n, max_mult * e["n"])
        if cap_depth:
            n = min(n, depth)
        if n < 1:
            total += e["prim"]
            rows.append((e, None, 0, e["prim"]))
            continue
        v = hedge_outcome(e["prim"], e["lost"], n, price)
        total += v
        fired += 1
        real += 1 if e["lost"] else 0
        rows.append((e, hit, n, v))
    return total, fired, real, rows


# -------------------------------------------------------------- self-test
def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(abs(fee(0.50, 1) - 0.02) < 1e-12, "fee at 50c on one contract is 2c")
    ck(fee(0.5, 0) == 0.0, "no contracts, no fee")

    # the arithmetic of a hedge, both outcomes
    ck(abs(hedge_outcome(-70.0, True, 100, 0.40) - (-70.0 + 60.0 - fee(0.40, 100)))
       < 1e-12, "a LOST bet: 100 contracts of 40c insurance pays 60c each")
    ck(abs(hedge_outcome(+5.0, False, 100, 0.40) - (5.0 - 40.0 - fee(0.40, 100)))
       < 1e-12, "a WON bet: the same insurance is 40c a contract of pure cost")
    ck(hedge_outcome(-70.0, True, 0, 0.40) == -70.0, "no hedge, no change")
    ck(hedge_outcome(-70.0, True, 100, 1.0) == -70.0,
       "insurance at $1 cannot help and is refused")

    # PLANTED WORLD: confidence falls 0.9 -> 0.1 while insurance rises
    path = [(100, 0.90, 0.12, 500), (101, 0.70, 0.30, 500),
            (102, 0.50, 0.50, 500), (103, 0.30, 0.70, 500),
            (104, 0.10, 0.90, 500)]
    lost = {"tk": "L", "prim": -80.0, "lost": True, "n": 100, "entry": 0.80,
            "path": path}
    won = {"tk": "W", "prim": +8.0, "lost": False, "n": 100, "entry": 0.80,
           "path": path}
    t80, f80, _, _ = simulate([lost], 0.80)
    t20, f20, _, _ = simulate([lost], 0.20)
    ck(f80 == 1 and f20 == 1, "both triggers fire on a confidence that collapses")
    ck(t80 > t20,
       "WAITING COSTS MONEY: triggering at 0.80 buys insurance at 30c and "
       "ends %+.2f; waiting for 0.20 pays 90c and ends %+.2f" % (t80, t20))
    ck(abs(t80 - hedge_outcome(-80.0, True, 100, 0.30)) < 1e-12,
       "and the 0.80 trigger really did buy at the 0.30 second, not the 0.12 one")
    tw, _, _, _ = simulate([won], 0.80)
    ck(tw < won["prim"],
       "on a bet that WINS the same hedge is pure cost (%+.2f from %+.2f)"
       % (tw, won["prim"]))

    # NULL: a confidence that never falls must never fire
    flat = [{"tk": "F", "prim": -5.0, "lost": True, "n": 10, "entry": 0.5,
             "path": [(s, 0.95, 0.10, 500) for s in range(100, 110)]}]
    t, f, _, _ = simulate(flat, 0.50)
    ck(f == 0 and abs(t - (-5.0)) < 1e-12,
       "NULL: confidence never falls under the trigger, nothing is bought")

    # depth is a hard cap, and a book with nothing offered cannot be used
    t, f, _, rows = simulate([dict(lost, path=[(100, 0.10, 0.30, 7)])], 0.50)
    ck(f == 1 and rows[0][2] == 7, "the hedge is capped at the 7 offered")
    t, f, _, _ = simulate([dict(lost, path=[(100, 0.10, 0.30, 0)])], 0.50)
    ck(f == 0, "and a second with nothing offered is skipped, not filled")

    # money-cover sizing
    e = {"tk": "M", "prim": -80.0, "lost": True, "n": 100, "entry": 0.80,
         "path": [(100, 0.10, 0.60, 10000)]}
    _, _, _, rows = simulate([e], 0.50, money=True)
    ck(abs(rows[0][2] - (100 * 0.80) / 0.40) < 1e-6,
       "cover-the-money buys risk/(1-price) = %.0f contracts" % ((100 * 0.8) / 0.4))
    ck(abs(rows[0][3] + fee(0.60, 200)) < 1e-9,
       "which brings a lost bet to exactly MINUS THE FEE, not to zero "
       "(%+.2f, fee $%.2f) -- covering the money never quite covers it, and "
       "a rule that claims break-even has forgotten the fee"
       % (rows[0][3], fee(0.60, 200)))
    _, _, _, rows = simulate([e], 0.50, money=True, max_mult=2.0)
    ck(abs(rows[0][2] - 200) < 1e-9, "and a 2x ceiling caps it at 200")

    print("hedgetune selftest:", "OK" if ok else "FAILED")
    return ok


def _fair_at(D, close_s, now_s, strike, sigma, digits, pinrun, settlewin):
    """P(settle >= effective strike) at `now_s`, from the recorded index.

    `pinrun.fair` cannot be reused: it reads the LIVE websocket index through
    `.partial()` and `.spot()`, and `.spot()` is by definition the newest
    print, not a historical one. So the same arithmetic is assembled here from
    `settlewin.partial` (the locked/remaining split, which already rescales a
    dropped second rather than letting it shrink the mean) and pinrun's own
    `eff_strike`, `var_factor` and `conf_of`. Nothing is reimplemented that
    the bot owns -- only the two live reads are replaced."""
    lo = close_s - pinrun.N_AVG
    ticks = {}
    for s in range(lo, min(now_s, close_s - 1) + 1):
        v = D.get(s)
        if v is not None:
            ticks[s] = v
    p = settlewin.partial(ticks, close_s, now_s)
    if p is None:
        return None
    locked, r = p
    spot = None
    for s in range(now_s, now_s - 30, -1):
        v = D.get(s)
        if v is not None:
            spot = v
            break
    if spot is None:
        return None
    K = pinrun.eff_strike(strike, digits)
    mu = (locked + r * spot) / pinrun.N_AVG
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = sigma * math.sqrt(pinrun.var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return pinrun.conf_of((mu - K) / sd)


# ------------------------------------------------------------------ build
def build():
    """Rebuild the per-second (confidence, hedge price, depth) table."""
    import idxload
    import pinrun
    import settlewin
    import replay

    alarms, sigs, sett = {}, {}, collections.defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(REPO, "results",
                                            "pinrun-live-*.jsonl"))):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            if k == "hedge_alarm" and r["ticker"] not in alarms:
                alarms[r["ticker"]] = r
            elif k == "signal" and r["ticker"] not in sigs:
                sigs[r["ticker"]] = r
            elif k == "settled" and r.get("pnl_c") is not None:
                sett[r["ticker"]].append(r)

    def nof(s):
        c = float(s["cost"])
        p = float(s["pnl_c"]) / 100.0
        f = 0.07 * c * (1 - c)
        per = ((1 - c) - f) if s.get("result") == s.get("want") else -(c + f)
        return abs(p / per)

    events = []
    for tk, a in alarms.items():
        S, sg = sett.get(tk), sigs.get(tk)
        if not S or not sg:
            continue
        prim = [s for s in S if s.get("want") == a.get("want")]
        if not prim:
            continue
        # the stamp block is EASTERN on every Kalshi crypto ticker;
        # racebook.close_of is the version proven against 761 settled races
        close_s = racebook.close_of(tk.split("-")[1])
        events.append({
            "tk": tk, "want": a["want"], "entry": float(prim[0]["cost"]),
            "n": sum(nof(s) for s in prim),
            "lost": prim[0].get("result") != prim[0].get("want"),
            "prim": sum(float(s["pnl_c"]) for s in prim) / 100.0,
            "actual": sum(float(s["pnl_c"]) for s in S) / 100.0,
            "alarm_s": int(dt.datetime.strptime(
                a["t"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc).timestamp()),
            "belief_at_alarm": float(a.get("belief") or 0),
            "strike": float(sg["strike"]), "digits": sg.get("digits"),
            "sigma": float(sg["sigma"]), "close_s": close_s})
    print("  %d alarms with a settlement, an entry signal and a close"
          % len(events))

    iids = sorted({replay.SERIES_TO_INDEX.get(e["tk"].split("-")[0])
                   for e in events} - {None})
    idx = idxload.load(iids, verbose=False, use_cache=False)

    # the book, second by second, for every alarm's market
    need = collections.defaultdict(set)
    for e in events:
        for s in range(e["alarm_s"] - LOOKBACK, (e["close_s"] or e["alarm_s"]) + 1):
            need[dt.datetime.utcfromtimestamp(s).strftime("%Y%m%dT%H")].add(e["tk"])
    book = collections.defaultdict(list)
    for hour, tks in sorted(need.items()):
        fp = os.path.join(racebook.DATA, "ticker", "%s.jsonl.gz" % hour)
        if not os.path.exists(fp):
            continue
        try:
            for line in gzip.open(fp, "rt"):
                t = racebook._grab(line, "market_ticker")
                if t not in tks:
                    continue
                try:
                    rx = int(racebook._grab(line, "_rx_ms")) // 1000
                    bid = float(racebook._grab(line, "yes_bid_dollars"))
                    ask = float(racebook._grab(line, "yes_ask_dollars"))
                    bsz = float(racebook._grab(line, "yes_bid_size_fp"))
                    asz = float(racebook._grab(line, "yes_ask_size_fp"))
                except (TypeError, ValueError):
                    continue
                book[t].append((rx, bid, ask, bsz, asz))
        except (EOFError, OSError):
            pass
    for t in book:
        book[t].sort()

    for e in events:
        iid = replay.SERIES_TO_INDEX.get(e["tk"].split("-")[0])
        D = idx.get(iid)
        rows = book.get(e["tk"], [])
        path, j, q = [], 0, None
        lo = e["alarm_s"] - LOOKBACK
        hi = (e["close_s"] or e["alarm_s"] + 60) - 1
        for sec in range(lo, hi + 1):
            while j < len(rows) and rows[j][0] <= sec:
                q = rows[j][1:]
                j += 1
            bel = None
            if D is not None and e["close_s"]:
                f = _fair_at(D, e["close_s"], sec, e["strike"], e["sigma"],
                             e["digits"], pinrun, settlewin)
                if f is not None:
                    bel = f if e["want"] == "yes" else 1.0 - f
            price = depth = None
            if q:
                bid, ask, bsz, asz = q
                # hedging a YES position means BUYING NO, which matches a
                # resting YES bid: price 1-bid, size the yes-bid size
                if e["want"] == "yes":
                    price, depth = round(1.0 - bid, 4), bsz
                else:
                    price, depth = ask, asz
            path.append((sec, bel, price, depth if depth is not None else 0))
        e["path"] = path
    os.makedirs(os.path.dirname(TABLE), exist_ok=True)
    json.dump(events, open(TABLE, "w"), indent=0)
    ok = sum(1 for e in events if any(p[1] is not None for p in e["path"]))
    print("  confidence rebuilt on %d of %d alarms; table -> %s"
          % (ok, len(events), TABLE))
    return events


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0
    if a.build or not os.path.exists(TABLE):
        print("\nrebuilding the per-second table...")
        E = build()
    else:
        E = json.load(open(TABLE))
        print("\nreusing %s (%d alarms)" % (TABLE, len(E)))
    E = [e for e in E if any(p[1] is not None for p in e["path"])]
    if len(E) < 8:
        print("loaded nothing -- only %d alarms with a rebuilt confidence" % len(E))
        return 0
    nl = sum(e["prim"] for e in E if e["lost"])
    nw = sum(e["prim"] for e in E if not e["lost"])
    print("%d alarms: %d were real losses, %d false. Never hedging: "
          "$%+.2f on the losses, $%+.2f on the false alarms, $%+.2f total"
          % (len(E), sum(1 for e in E if e["lost"]),
             sum(1 for e in E if not e["lost"]), nl, nw, nl + nw))

    print("\n## THE DIAL. Hedge when confidence falls under the trigger,")
    print("## at the price quoted THEN, capped by what was offered.")
    print("  %-9s %6s %6s %7s %9s %11s %11s %11s"
          % ("trigger", "fires", "real", "right%", "avg paid", "the losses",
             "false alarms", "TOTAL"))
    best = None
    for T in TRIGGERS:
        tot, f, real, rows = simulate(E, T)
        if not f:
            continue
        paid = [r[1][2] for r in rows if r[1]]
        tl = sum(r[3] for r in rows if r[0]["lost"])
        tw = sum(r[3] for r in rows if not r[0]["lost"])
        print("  <%-8.0f%% %6d %6d %6.0f%% %8.2fc %+11.2f %+11.2f %+11.2f%s"
              % (100 * T, f, real, 100.0 * real / f,
                 100 * sum(paid) / len(paid), tl, tw, tot,
                 "  <-" if best is None or tot > best[0] else ""))
        if best is None or tot > best[0]:
            best = (tot, T)
    print("  %-9s %6d %6s %7s %9s %+11.2f %+11.2f %+11.2f"
          % ("never", 0, "-", "-", "-", nl, nw, nl + nw))

    print("\n## AND HOW MUCH TO BUY, at each trigger")
    print("  %-9s %-16s %11s %11s %11s"
          % ("trigger", "size", "the losses", "false alarms", "TOTAL"))
    grid = [("1x the position", {"mult": 1.0}), ("2x", {"mult": 2.0}),
            ("3x", {"mult": 3.0}),
            ("cover the money", {"money": True}),
            ("cover, max 3x", {"money": True, "max_mult": 3.0})]
    top = None
    for T in (0.60, 0.50, 0.40, 0.30, 0.25, 0.20):
        for lab, kw in grid:
            tot, f, real, rows = simulate(E, T, **kw)
            tl = sum(r[3] for r in rows if r[0]["lost"])
            tw = sum(r[3] for r in rows if not r[0]["lost"])
            print("  <%-8.0f%% %-16s %+11.2f %+11.2f %+11.2f%s"
                  % (100 * T, lab, tl, tw, tot,
                     "  <-" if top is None or tot > top[0] else ""))
            if top is None or tot > top[0]:
                top = (tot, T, lab)
        print("  %s" % ("-" * 66))
    print("\n  BEST: trigger under %.0f%%, %s -> $%+.2f "
          "(never hedging $%+.2f, so $%+.2f better)"
          % (100 * top[1], top[2], top[0], nl + nw, top[0] - (nl + nw)))

    print("\n## LEAVE ONE OUT -- is the winner carried by a single alarm?")
    for lab, kw in (("1x", {"mult": 1.0}), ("cover the money", {"money": True})):
        for T in (0.60, 0.30, 0.25):
            gains = []
            for i in range(len(E)):
                S = [x for j, x in enumerate(E) if j != i]
                base = sum(x["prim"] for x in S)
                gains.append((simulate(S, T, **kw)[0] - base, E[i]["tk"]))
            gains.sort()
            print("  <%.0f%% %-16s worst drop-one $%+8.2f (%s) ... best $%+8.2f"
                  % (100 * T, lab, gains[0][0], gains[0][1][:24], gains[-1][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
