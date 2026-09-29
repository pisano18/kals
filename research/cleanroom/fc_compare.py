#!/usr/bin/env python3
"""fc_compare.py -- each forecaster variant against base, from fc_replay.py fill files (REPLAY) or from the side-by-side
paper log results/fcvar-paper.jsonl (PAPER). Money per market = sum of its 'real' fills (size still shown 1 s later).

Per variant and half (TRAIN / TEST, or the paper window): markets traded, losing markets, money lost in losing markets,
money won, net, return on money staked, worst day, days below zero; and against base: net change, losses saved.

    python research/cleanroom/fc_compare.py --replay DIR
    python research/cleanroom/fc_compare.py --paper results/fcvar-paper.jsonl [--since 2026-09-29T01:28]
    python research/cleanroom/fc_compare.py --selftest
"""
import argparse
import collections
import glob
import json
import os
import sys


def summarise(fills):
    """fills: dicts with ticker, day, pnl, size, price, split. -> {split: stats}."""
    out = {}
    for sp in sorted({f["split"] for f in fills}):
        mk = collections.defaultdict(lambda: [0.0, 0.0, None])     # pnl, cost, day
        for f in fills:
            if f["split"] != sp:
                continue
            m = mk[f["ticker"]]
            m[0] += f["pnl"]
            m[1] += f["size"] * f["price"]
            m[2] = f["day"]
        days = collections.defaultdict(float)
        for pnl, cost, day in mk.values():
            days[day] += pnl
        lost = [v[0] for v in mk.values() if v[0] < 0]
        won = [v[0] for v in mk.values() if v[0] >= 0]
        cost = sum(v[1] for v in mk.values())
        net = sum(v[0] for v in mk.values())
        out[sp] = {"markets": len(mk), "losing": len(lost), "lost": round(sum(lost), 2), "won": round(sum(won), 2),
                   "net": round(net, 2), "staked": round(cost, 2), "ret": round(100 * net / cost, 2) if cost else None,
                   "worst_day": round(min(days.values()), 2) if days else 0.0,
                   "days_below_zero": sum(1 for v in days.values() if v < 0), "days": len(days),
                   "worst_market": round(min([v[0] for v in mk.values()] or [0.0]), 2)}
    return out


def load_replay(d):
    res = {}
    for p in sorted(glob.glob(os.path.join(d, "*_fills.jsonl"))):
        v = os.path.basename(p)[:-len("_fills.jsonl")]
        fills = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["fill"] == "real":
                    fills.append(r)
        res[v] = fills
    return res


def load_paper(path, since=None):
    res = collections.defaultdict(list)
    fills, results = collections.defaultdict(list), {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if '"ev":"fill"' not in line and '"ev":"settle"' not in line:
                continue
            r = json.loads(line)
            if since and r["t"] < since:
                continue
            if r["ev"] == "fill" and r.get("fill") == "real" and r.get("strat") == "forecaster":
                fills[(r["v"], r["ticker"])].append(r)
            elif r["ev"] == "settle" and r.get("result") in ("yes", "no"):
                results[r["ticker"]] = (r["result"], r["t"][:10])
    for (v, tk), fs in fills.items():
        if tk not in results:
            continue
        res_, day = results[tk]
        for x in fs:
            win = x["side"] == res_
            pnl = (x["size"] * (1 - x["price"]) if win else -x["size"] * x["price"]) - x["fee"]
            res[v].append({"ticker": tk, "day": day, "pnl": pnl, "size": x["size"], "price": x["price"], "split": "PAPER"})
    return dict(res)


def report(res, title):
    lines = ["%s" % title, ""]
    base = summarise(res.get("base", []))
    order = ["base"] + sorted(v for v in res if v != "base")
    for sp in sorted(base) or ["PAPER"]:
        lines.append("%s" % sp)
        lines.append("| version | markets | losing | lost $ | net $ | return on stake | worst day $ | days < 0 | net vs base $ | losses saved vs base $ |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        b = base.get(sp)
        for v in order:
            s = summarise(res.get(v, [])).get(sp)
            if not s:
                lines.append("| %s | 0 | | | | | | | | |" % v)
                continue
            dn = "" if not b or v == "base" else "%+.0f" % (s["net"] - b["net"])
            ds = "" if not b or v == "base" else "%+.0f" % (s["lost"] - b["lost"])
            lines.append("| %s | %d | %d | %.0f | %+.0f | %s%% | %+.0f | %d of %d | %s | %s |" % (
                v, s["markets"], s["losing"], s["lost"], s["net"], s["ret"], s["worst_day"], s["days_below_zero"],
                s["days"], dn, ds))
        lines.append("")
    return "\n".join(lines)


def selftest():
    fails = []
    f = [{"ticker": "A", "day": "d1", "pnl": 5.0, "size": 10, "price": 0.5, "split": "T"},
         {"ticker": "A", "day": "d1", "pnl": -7.0, "size": 10, "price": 0.7, "split": "T"},
         {"ticker": "B", "day": "d2", "pnl": 3.0, "size": 10, "price": 0.7, "split": "T"}]
    s = summarise(f)["T"]
    if not (s["markets"] == 2 and s["losing"] == 1 and s["lost"] == -2.0 and s["net"] == 1.0 and s["staked"] == 19.0
            and s["worst_day"] == -2.0 and s["days_below_zero"] == 1):
        fails.append("summarise: two fills in A net -2 (one losing market), B +3; %s" % s)
    if summarise([]) != {}:
        fails.append("empty input gives nothing")
    txt = report({"base": f, "v": f[2:]}, "t")
    if "| v | 1 | 0 | 0 | +3 |" not in txt or "| +2 | +2 |" not in txt:
        fails.append("report: v keeps only B: net +3 (+2 vs base), losses saved +2\n" + txt)
    print("fc_compare self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--replay")
    ap.add_argument("--paper")
    ap.add_argument("--since")
    a = ap.parse_args()
    if not selftest():
        raise SystemExit(1)
    if a.selftest:
        return 0
    if a.replay:
        print(report(load_replay(a.replay), "REPLAY (tape population, 1-s survival rule) -- %s" % a.replay))
    if a.paper:
        print(report(load_paper(a.paper, a.since), "PAPER (live feed, displayed offers, 1-s survival rule) -- %s" % a.paper))
    return 0


if __name__ == "__main__":
    sys.exit(main())
