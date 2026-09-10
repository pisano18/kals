#!/usr/bin/env python3
# VERSION: 2026-09-10-pj1
"""pinjump.py -- DOES THE EXCHANGE TAPE KNOW BEFORE THE INDEX PRINTS?

THE EVENT (2026-09-10, KXXRP15M 05:00Z close, -$16.61). Reconstructed by hand
from the tape: the bot's inputs were exact, it stood +9.2 sd on YES at
04:59:39Z, index age 0.18 s, book age 2 ms. In THAT SAME SECOND the CF index
printed 1.39075 while Coinbase had already traded 1.38950 and Kraken 1.38989.
The index followed one second later and fell ~10 sd over the last 20 prints.
The seller who filled us at 82c had seen the exchange tick. The print was
stale inside its own second, and nothing we read could tell us.

CF Benchmarks prints once a second from the constituent exchanges. A move
that lands mid-second is on the exchanges' own tick streams up to a second
before it is in the print. crypto_feeds.py has recorded those streams since
2026-08-25 (`feed_data/coinbase`, `feed_data/kraken`, receipt-stamped) and the
live bot has never read them.

THE QUESTION: at the second the bot fires, take the freshest exchange trade
we could have seen BEFORE sending (receipt time <= t + 0.35 s, roughly our
own latency budget) and express its distance from the CF print in sigma,
signed so that positive means "moved against the side we are buying". Does
that number predict the flip?

CONTROL: the same number from ticks 2-4 seconds OLD. If stale ticks predict
as well as fresh ones, this is not a lead, it is a relabelled volatility
measure and must be reported as such.

COVERAGE: the feeds carry BTC, ETH, SOL, XRP, DOGE. BNB, ZEC, HYPE and NEAR
are not on them, so this file says nothing about those four.

n as markets AND closes; every significance claim from a permutation over
CLOSES; fit/holdout over closes for any threshold.
"""
import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402
from pintail import (window_state, sigma_at, ROUND_DIGITS,   # noqa: E402
                     SERIES_TO_INDEX, FULLTAPE)
from pinfirst import crossings                               # noqa: E402
from pincross import cp_interval, load_index_window, perm_test  # noqa: E402

ND = NormalDist()
FEEDS = r"C:\kals\feed_data"
GATE_Z = ND.inv_cdf(0.98)
SYMBOLS = {"BRTI": ("BTC-USD", "BTC/USD"), "ETHUSD_RTI": ("ETH-USD", "ETH/USD"),
           "SOLUSD_RTI": ("SOL-USD", "SOL/USD"),
           "XRPUSD_RTI": ("XRP-USD", "XRP/USD"),
           "DOGEUSD_RTI": ("DOGE-USD", "DOGE/USD")}
PRE_LO, PRE_HI = -1.5, 0.35        # what we could know before sending
STALE_LO, STALE_HI = -4.0, -2.0     # the control window
D_EDGES = [-99, 0.5, 1.0, 2.0, 4.0, 99]


def adverse(ex_px, cf_px, sigma, fav_yes):
    """Exchange-minus-print distance in sigma, positive = against our side."""
    d = (ex_px - cf_px) / sigma
    return -d if fav_yes else d


def selftest():
    print("SELF-TEST -- pinjump")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(adverse(99.0, 100.0, 0.5, True) == 2.0,
       "holding YES, the exchange 2 sigma BELOW the print reads +2 adverse")
    ck(adverse(101.0, 100.0, 0.5, False) == 2.0,
       "holding NO, the exchange 2 sigma ABOVE the print reads +2 adverse")
    ck(adverse(99.0, 100.0, 0.5, False) == -2.0,
       "and the same move reads -2 (in our favour) on the other side")

    # planted: flips only when adverse >= 2; the close-level test must see it
    rng = random.Random(3)
    cl = []
    for _ in range(150):
        n = rng.randint(2, 5)
        # planted above 1.0 sd (~20% of closes), because the statistic reads
        # the top QUARTILE; a first version planted above 2.0 sd (~5%) and
        # was diluted four-to-one by its own bucket boundary
        d = rng.gauss(0, 1.2)
        pr = 0.15 if d >= 1.0 else 0.005
        cl.append({"d": d, "n": n,
                   "flips": sum(1 for _ in range(n) if rng.random() < pr)})
    g = perm_test(cl, "d", draws=1500)
    ck(g is not None and g[1] < 0.01,
       f"a planted exchange-lead effect is found (p={g[1]:.4f})")
    hits = 0
    for w in range(40):
        rw = random.Random(700 + w)
        nul = [{"d": rw.gauss(0, 1.2), "n": rw.randint(2, 5), "flips": 0}
               for _ in range(150)]
        for c in nul:
            c["flips"] = sum(1 for _ in range(c["n"]) if rw.random() < 0.02)
        gg = perm_test(nul, "d", draws=400, seed=w)
        if gg and gg[1] < 0.05:
            hits += 1
    ck(hits <= 6, f"calibrated: {hits}/40 null worlds significant at 5%")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    return not f


def hour_of(sec):
    return time.strftime("%Y%m%dT%H", time.gmtime(sec))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--draws", type=int, default=4000)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    mk = []
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if (r["series"] in SERIES_TO_INDEX and r.get("settle") is not None
                    and SERIES_TO_INDEX[r["series"]] in SYMBOLS):
                mk.append(r)
    mk.sort(key=lambda r: r["close"])
    prev_settle = {(r["series"], int(r["close"])): float(r["settle"])
                   for r in mk}
    print(f"\n  {len(mk):,} settled markets on coins the exchange feeds cover")
    lo_sec, hi_sec = int(mk[0]["close"]) - 400, int(mk[-1]["close"])
    t0 = time.time()
    idx, nf, kept, _ = load_index_window(lo_sec, hi_sec)
    print(f"  index: {len(idx)} feeds, {kept:,} prints ({time.time()-t0:.0f}s)")

    # ---- every 0.98 crossing, with what the model saw at that second ----
    obs = []
    for r in mk:
        iid = SERIES_TO_INDEX[r["series"]]
        if iid not in idx:
            continue
        base, arr = idx[iid]
        cs = int(r["close"])
        ps = prev_settle.get((r["series"], cs - 900))
        K = (ps if ps is not None else float(r["strike"])) \
            - 0.5 * 10.0 ** (-ROUND_DIGITS[r["series"]])
        cx = crossings(arr, base, cs, K).get(0.980)
        if cx is None:
            continue
        tau, m, fav_yes = cx
        t = cs - tau
        i = t - base
        cf = arr[i] if (0 <= i < len(arr) and arr[i] == arr[i]) else None
        if cf is None and 0 <= i - 1 < len(arr) and arr[i - 1] == arr[i - 1]:
            cf = arr[i - 1]
        sg = sigma_at(arr, base, t)
        if cf is None or not sg:
            continue
        lk, rr, cov, spot = window_state(arr, base, cs, t)
        mu = (lk + rr * spot) / 60.0
        sd = sg * math.sqrt(var_factor(int(rr), [1.0]))
        z = (float(r["settle"]) - mu) / sd
        yes_won = float(r["settle"]) >= K
        obs.append({"close": cs, "sr": r["series"], "iid": iid, "t": t,
                    "tau": tau, "m": m, "fav_yes": fav_yes, "cf": cf,
                    "sigma": sg, "z_adv": (-z if fav_yes else z),
                    "flip": fav_yes != yes_won, "ticks": []})
    print(f"  {len(obs):,} crossings of the 0.98 gate, "
          f"{sum(1 for o in obs if o['flip'])} flips")

    # ---- stream the exchange feeds once, keeping ticks near crossings ----
    want = defaultdict(list)      # (hour, symbol) -> [obs index]
    for k, o in enumerate(obs):
        for h in {hour_of(o["t"] + STALE_LO - 1), hour_of(o["t"] + 2)}:
            for sym in SYMBOLS[o["iid"]]:
                want[(h, sym)].append(k)
    hours = sorted(set(h for h, _ in want))
    print(f"  streaming {len(hours)} hours of coinbase + kraken ...")
    t0 = time.time()
    nlines = 0
    for h in hours:
        for ex in ("coinbase", "kraken"):
            fp = os.path.join(FEEDS, ex, f"{h}.jsonl.gz")
            if not os.path.exists(fp):
                continue
            syms = [(sym, want[(h, sym)]) for sym in
                    set(s for s in (v for pair in SYMBOLS.values()
                                    for v in pair)) if (h, sym) in want]
            if not syms:
                continue
            try:
                with gzip.open(fp, "rt") as fh:
                    for line in fh:
                        nlines += 1
                        for sym, ks in syms:
                            if sym not in line:
                                continue
                            try:
                                d = json.loads(line)
                                rx = float(d["_rx"])
                                if ex == "coinbase":
                                    if d.get("product_id") != sym:
                                        continue
                                    px = float(d["price"])
                                else:
                                    dd = d["data"][0]
                                    if dd.get("symbol") != sym:
                                        continue
                                    px = float(dd["last"])
                            except Exception:
                                continue
                            for k in ks:
                                o = obs[k]
                                if o["t"] + STALE_LO - 1 <= rx <= o["t"] + 2:
                                    o["ticks"].append((rx, px, ex))
            except Exception:
                continue
    print(f"  {nlines:,} lines ({time.time()-t0:.0f}s)")

    # ---- the numbers ----
    scored = []
    for o in obs:
        tk = sorted(o["ticks"])
        pre = [p for p in tk if PRE_LO <= p[0] - o["t"] <= PRE_HI]
        stale = [p for p in tk if STALE_LO <= p[0] - o["t"] <= STALE_HI]
        if not pre or not stale:
            continue
        o["d_pre"] = adverse(pre[-1][1], o["cf"], o["sigma"], o["fav_yes"])
        o["d_pre_max"] = max(adverse(p[1], o["cf"], o["sigma"], o["fav_yes"])
                             for p in pre)
        o["d_stale"] = adverse(stale[-1][1], o["cf"], o["sigma"],
                               o["fav_yes"])
        scored.append(o)
    nfl = sum(1 for o in scored if o["flip"])
    print(f"\n  {len(scored):,} crossings carry a fresh AND a stale exchange "
          f"tick ({nfl} flips); {len(obs)-len(scored)} unscored")
    if len(scored) < 100:
        print("  loaded nothing usable")
        return

    def table(key, label):
        print(f"\n  {label}")
        print(f"  {'adverse (sd)':>14}{'markets':>9}{'closes':>8}{'flips':>7}"
              f"{'rate':>8}{'95% CI':>18}{'mean z_adv':>12}")
        for a_, b_ in zip(D_EDGES, D_EDGES[1:]):
            sel = [o for o in scored if a_ <= o[key] < b_]
            if not sel:
                continue
            fl = sum(1 for o in sel if o["flip"])
            cl = len(set(o["close"] for o in sel))
            lo, hi = cp_interval(fl, len(sel))
            mz = sum(o["z_adv"] for o in sel) / len(sel)
            print(f"  {a_:>6.1f}-{b_:<7.1f}{len(sel):>9}{cl:>8}{fl:>7}"
                  f"{100*fl/len(sel):>7.2f}%"
                  f"{'[' + f'{100*lo:.2f}, {100*hi:.2f}' + ']':>18}"
                  f"{mz:>12.3f}")

    table("d_pre", "BY THE FRESHEST TICK BEFORE SENDING (t-1.5s .. t+0.35s)")
    table("d_pre_max", "BY THE WORST TICK IN THAT WINDOW")
    table("d_stale", "CONTROL: BY A TICK 2-4 SECONDS OLD (must be weaker)")

    # permutation over closes, fresh vs stale
    def closes_for(key):
        by = defaultdict(lambda: {"n": 0, "flips": 0, "v": 0.0, "za": 0.0})
        for o in scored:
            c = by[o["close"]]
            c["n"] += 1
            c["flips"] += 1 if o["flip"] else 0
            c["v"] = max(c["v"], o[key]) if c["n"] > 1 else o[key]
            c["za"] += o["z_adv"]
        return [{"close": k, "n": c["n"], "flips": c["flips"], "v": c["v"],
                 "za": c["za"]} for k, c in by.items()]

    print(f"\n  PERMUTATION over closes (top quartile vs rest), "
          f"{a.draws} draws")
    for key, lbl in (("d_pre", "freshest tick"), ("d_pre_max", "worst fresh "
                     "tick"), ("d_stale", "stale tick (control)")):
        cl = closes_for(key)
        g = perm_test(cl, "v", draws=a.draws)
        if g:
            print(f"    flips   by {lbl:<22} lift {100*g[0]:+.2f}pp  "
                  f"p={g[1]:.4f}")

    # a rule, fit/holdout: refuse when d_pre >= k
    cl_all = sorted(set(o["close"] for o in scored))
    cut = cl_all[int(0.70 * len(cl_all))]
    fit = [o for o in scored if o["close"] < cut]
    hold = [o for o in scored if o["close"] >= cut]
    print(f"\n  REFUSE WHEN THE FRESH TICK IS >= k sd AGAINST US -- fit "
          f"{len(fit):,} / holdout {len(hold):,} crossings")
    print(f"  {'k':>5}{'FIT kept':>10}{'flips kept':>12}{'refused':>9}"
          f"{'HOLD kept':>11}{'flips kept':>12}{'refused':>9}")
    for k in (0.5, 1.0, 1.5, 2.0, 3.0):
        def row(rows):
            keep = [o for o in rows if o["d_pre"] < k]
            ref = [o for o in rows if o["d_pre"] >= k]
            return (len(keep) / max(1, len(rows)),
                    sum(1 for o in keep if o["flip"]),
                    sum(1 for o in ref if o["flip"]))
        f_, h_ = row(fit), row(hold)
        print(f"  {k:>5.1f}{100*f_[0]:>9.1f}%{f_[1]:>12}{f_[2]:>9}"
              f"{100*h_[0]:>10.1f}%{h_[1]:>12}{h_[2]:>9}")
    print(f"  ungated flips: fit {sum(1 for o in fit if o['flip'])}, "
          f"holdout {sum(1 for o in hold if o['flip'])}")

    print(f"\n  the flips, with what the exchanges showed at the crossing:")
    for o in scored:
        if o["flip"]:
            print(f"    {o['sr']:<10} {time.strftime('%m-%d %H:%M', time.gmtime(o['close']))}"
                  f"  tau {o['tau']:>2}  margin {o['m']:.2f}  fresh {o['d_pre']:+.2f}"
                  f"  worst {o['d_pre_max']:+.2f}  stale {o['d_stale']:+.2f}"
                  f"  realised {o['z_adv']:+.2f} sd")


if __name__ == "__main__":
    main()
