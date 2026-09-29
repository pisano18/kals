#!/usr/bin/env python3
r"""fc_features.py -- the research dataset for "what separates the forecaster's losing buys from its winning ones".

One row per forecaster DECISION that found a buyable offer in the 33-day replay (fc_replay.py base fills, both fill
rules): the side, price, outcome (win = side == result), whether the 1-s survival rule filled it, the money under both
rules, the engine's own features, and ~40 more signals computed here from the clean-room digest using ONLY data
available at the decision instant (close + rel + 0.2 s):
  index   prints stamped <= close+rel        book   the end-of-second row for rel-1 and earlier
  trades  ts_ms < (close+rel+0.2)*1000       other coins: their index prints stamped <= close+rel
Every return / flow is ORIENTED to the side bought (+ = in our favour).

REPLAY population (displayed offers), not our fills: good for comparing rules, never a loss rate for us.

    python research/cleanroom/fc_features.py --selftest
    python research/cleanroom/fc_features.py --fills <base_fills.jsonl> --out <dataset.jsonl>
"""
import argparse
import bisect
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bettor_paper as B                        # noqa: E402
import fc_replay as FR                          # noqa: E402

COIN_IDX = {c: v[1] for c, v in B.COINS.items()}


def _ret(pr, t0, t1):
    """log return from the print at/before t0 to the print at/before t1 (pr: sorted [(rel, value)])."""
    a, b = _at(pr, t0), _at(pr, t1)
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return math.log(b / a)


def _at(pr, t):
    i = bisect.bisect_right([x[0] for x in pr], t) - 1
    return pr[i][1] if i >= 0 else None


def _sigma(pr, t, n):
    xs = [(r, v) for r, v in pr if t - n <= r <= t]
    rets = [math.log(b[1] / a[1]) for a, b in zip(xs, xs[1:]) if a[1] > 0 and b[1] > 0 and b[0] - a[0] == 1]
    if len(rets) < 5:
        return None
    m = sum(rets) / len(rets)
    return math.sqrt(max(sum((x - m) ** 2 for x in rets) / len(rets), 1e-18))


def _logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def features(cand, idx_all, book_rows, trades, thr, close_s, other_idx):
    """cand: {rel, side, price, p}. idx_all: sorted [(rel, value)] for this coin. book_rows: {rel: row}.
    trades: [[ts_ms, yes_px, count, taker]]. other_idx: {coin: sorted [(rel, value)]} for the other coins' same close.
    Returns a dict of features using only data available at close+rel+0.2."""
    rel, side, q, p = cand["rel"], cand["side"], cand["price"], cand["p"]
    sgn = 1.0 if side == "yes" else -1.0
    pr = [x for x in idx_all if x[0] <= rel]                     # prints stamped by the decision second
    f = {}
    sig60 = _sigma(pr, rel, 60)
    sig10 = _sigma(pr, rel, 10)
    f["x_sig60"] = sig60
    f["x_volratio_10_60"] = (sig10 / sig60) if (sig10 and sig60) else None
    v = _at(pr, rel)
    for k in (1, 2, 3, 5, 10, 20):
        r_ = _ret(pr, rel - k, rel)
        f["x_ret%d" % k] = None if (r_ is None or not sig60) else sgn * r_ / sig60
    if f["x_ret1"] is not None and f["x_ret2"] is not None:
        f["x_accel"] = f["x_ret1"] - (f["x_ret2"] - f["x_ret1"])
    else:
        f["x_accel"] = None
    rets10 = [math.log(b[1] / a[1]) for a, b in zip(pr[-11:], pr[-10:]) if a[1] > 0 and b[1] > 0]
    f["x_jump10"] = (max(abs(x) for x in rets10) / sig60) if (rets10 and sig60) else None
    f["x_adverse10"] = (min(sgn * x for x in rets10) / sig60) if (rets10 and sig60) else None
    remaining = max(1, -rel - 1)
    f["x_gap_sig"] = None if (v is None or not sig60) else sgn * (v - thr) / (v * sig60 * math.sqrt(remaining))
    # book: rows up to rel-1 (end-of-second states known by the decision)
    def side_book(row):
        if row is None:
            return None
        ybp, ybs, yd3, nbp, nbs, nd3 = row[1], row[2], row[3], row[4], row[5], row[6]
        if side == "yes":
            ask = None if nbp is None else 1 - nbp
            return {"ask": ask, "ask_sz": nbs, "ask_d3": nd3, "bid": ybp, "bid_sz": ybs, "bid_d3": yd3}
        ask = None if ybp is None else 1 - ybp
        return {"ask": ask, "ask_sz": ybs, "ask_d3": yd3, "bid": nbp, "bid_sz": nbs, "bid_d3": nd3}
    now = side_book(book_rows.get(rel - 1))
    if now:
        f["x_mid"] = None if (now["ask"] is None or now["bid"] is None) else (now["ask"] + now["bid"]) / 2
        f["x_imb"] = ((now["bid_sz"] - now["ask_sz"]) / (now["bid_sz"] + now["ask_sz"])
                      if (now["bid_sz"] + now["ask_sz"]) > 0 else None)
        f["x_imb3"] = ((now["bid_d3"] - now["ask_d3"]) / (now["bid_d3"] + now["ask_d3"])
                       if (now["bid_d3"] + now["ask_d3"]) > 0 else None)
        f["x_ask_d3"] = now["ask_d3"]
        f["x_logit_gap"] = None if f["x_mid"] is None else _logit(p) - _logit(f["x_mid"])
        if now["bid"] is not None and now["ask"] is not None and now["bid_sz"] + now["ask_sz"] > 0:
            micro = (now["bid"] * now["ask_sz"] + now["ask"] * now["bid_sz"]) / (now["bid_sz"] + now["ask_sz"])
            f["x_micro_minus_px"] = micro - q
        else:
            f["x_micro_minus_px"] = None
        for k in (3, 5, 10):
            old = side_book(book_rows.get(rel - 1 - k))
            f["x_ask_chg%d" % k] = (None if (not old or old["ask"] is None or now["ask"] is None)
                                    else now["ask"] - old["ask"])
            f["x_bid_chg%d" % k] = (None if (not old or old["bid"] is None or now["bid"] is None)
                                    else now["bid"] - old["bid"])
    # trades before the decision instant
    t_dec_ms = (close_s + rel + 0.2) * 1000
    tr = [t for t in trades if t[0] < t_dec_ms]
    def signed(window_s):
        lo = t_dec_ms - window_s * 1000
        s = 0.0
        n = 0
        for t in tr:
            if t[0] >= lo:
                s += t[2] if t[3] == side else -t[2]
                n += 1
        return s, n
    for k in (1, 3, 5, 10):
        s, n = signed(k)
        f["x_ofi%d" % k] = s
        f["x_ntr%d" % k] = n
    s30, n30 = signed(30)
    f["x_intensity"] = (f["x_ntr5"] / 5.0) / (n30 / 30.0) if n30 else None
    tot10 = sum(t[2] for t in tr if t[0] >= t_dec_ms - 10000)
    f["x_vpin10"] = abs(f["x_ofi10"]) / tot10 if tot10 else None
    f["x_big_against5"] = sum(1 for t in tr if t[0] >= t_dec_ms - 5000 and t[3] != side and t[2] >= 100)
    ours = [(t[1] if side == "yes" else 1 - t[1], t[2]) for t in tr if t[0] >= t_dec_ms - 10000]
    vol = sum(c for _, c in ours)
    f["x_vwap10_minus_px"] = (sum(px * c for px, c in ours) / vol - q) if vol else None
    # other coins at the same close: oriented to "the whole market moving my way"
    ups = []
    for c, opr in other_idx.items():
        o = [x for x in opr if x[0] <= rel]
        r5 = _ret(o, rel - 5, rel)
        s60 = _sigma(o, rel, 60)
        if r5 is not None and s60:
            ups.append(r5 / s60)
    f["x_mkt_ret5"] = (sgn * sum(ups) / len(ups)) if ups else None
    btc = other_idx.get("BTC")
    if btc:
        o = [x for x in btc if x[0] <= rel]
        r5, s60 = _ret(o, rel - 5, rel), _sigma(o, rel, 60)
        f["x_btc_ret5"] = None if (r5 is None or not s60) else sgn * r5 / s60
    else:
        f["x_btc_ret5"] = None
    hour = time.gmtime(close_s + rel).tm_hour
    f["x_hour_et"] = (hour - 4) % 24
    f["x_weekday"] = time.gmtime(close_s - 4 * 3600).tm_wday
    return f


def build(fills_path, out_path, digest=FR.DIGEST):
    rows = [json.loads(l) for l in open(fills_path, encoding="utf-8")]
    ms = {m["ticker"]: m for m in FR.load_markets(digest)}
    dec = {}
    real = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        key = (r["ticker"], r["rel"], r["side"])
        if r["fill"] == "opt":
            d = dec.setdefault(key, {"ticker": r["ticker"], "rel": r["rel"], "side": r["side"], "size": 0.0, "cost": 0.0,
                                     "opt_pnl": 0.0, "row": r})
            d["size"] += r["size"]
            d["cost"] += r["size"] * r["price"]
            d["opt_pnl"] += r["pnl"]
        else:
            real[key][0] += r["size"]
            real[key][1] += r["pnl"]
            # a realistic fill whose decision second had NO decision-instant fill (that rule had already hit its
            # per-side / per-close cap) is still a decision: 340 of 934 realistic fills were dropped before this
            # (found by the 2026-09-29 research verifiers)
            dec.setdefault(key, {"ticker": r["ticker"], "rel": r["rel"], "side": r["side"], "size": 0.0, "cost": 0.0,
                                 "opt_pnl": 0.0, "row": r, "real_only": True})
    for d in dec.values():
        if d.get("real_only"):
            d["size"], d["cost"] = real[(d["ticker"], d["rel"], d["side"])][0], 0.0
            d["cost"] = sum(x["size"] * x["price"] for x in rows if x["fill"] == "real" and
                            (x["ticker"], x["rel"], x["side"]) == (d["ticker"], d["rel"], d["side"]))
    by_day = defaultdict(list)
    for key, d in dec.items():
        by_day[ms[d["ticker"]]["day"]].append(d)
    out = open(out_path, "w", encoding="utf-8")
    n = 0
    for day in sorted(by_day):
        keep = {d["ticker"] for d in by_day[day]}
        books, idx, trades = FR.load_day(digest, day, True, keep)
        for d in by_day[day]:
            m = ms[d["ticker"]]
            r0 = d["row"]
            thr = float(m["strike"]) - 0.5 * 10 ** (-m["rd"])
            c = m["close_ts"]
            own = sorted((x[0], x[1]) for x in idx.get((COIN_IDX[m["coin"]], c), []))
            others = {cc: sorted((x[0], x[1]) for x in idx.get((ii, c), [])) for cc, ii in COIN_IDX.items()
                      if cc != m["coin"] and (ii, c) in idx}
            brows = {row[0]: row for row in books.get(d["ticker"], [])}
            cand = {"rel": d["rel"], "side": d["side"], "price": d["cost"] / d["size"], "p": r0.get("feat_p") or r0.get("p_side")}
            f = features(cand, own, brows, trades.get(d["ticker"], []), thr, c, others)
            key = (d["ticker"], d["rel"], d["side"])
            rec = {"ticker": d["ticker"], "coin": m["coin"], "day": day, "split": m["split"], "close_s": c,
                   "rel": d["rel"], "side": d["side"], "price": round(cand["price"], 4), "opt_size": d["size"],
                   "win": d["side"] == m["result"], "opt_pnl": round(d["opt_pnl"], 4),
                   "survived": real[key][0] > 0, "real_size": real[key][0], "real_pnl": round(real[key][1], 4),
                   "real_only": bool(d.get("real_only"))}
            rec.update({k: v for k, v in r0.items() if k.startswith("feat_")})
            rec.update({k: (round(v, 6) if isinstance(v, float) else v) for k, v in f.items()})
            out.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n += 1
        print(day, len(by_day[day]), "decisions", flush=True)
    out.close()
    print("wrote %d decision rows to %s" % (n, out_path))


def selftest():
    fails = []
    ck = lambda ok, msg: None if ok else fails.append(msg)
    C = 1_000_000 * 900
    idx = [(r, 100.0 + 0.01 * (r + 60)) for r in range(-240, 4)]          # rising 0.01/s
    rows = {r: [r, 0.20, 50.0, 80.0, 0.10, 30.0, 40.0, 1, 1] for r in range(-180, 1)}
    trades = [[(C - 21) * 1000 + 500, 0.80, 10.0, "yes"], [(C - 21) * 1000 + 900, 0.80, 4.0, "no"]]
    other = {"BTC": [(r, 50000.0 + 5.0 * (r + 60)) for r in range(-240, 4)]}
    cand = {"rel": -20, "side": "yes", "price": 0.90, "p": 0.97}
    f = features(cand, idx, rows, trades, 99.995, C, other)
    ck(f["x_ret5"] is not None and f["x_ret5"] > 0 and f["x_btc_ret5"] > 0, "rising index/BTC -> positive for YES")
    fn = features(dict(cand, side="no"), idx, rows, trades, 99.995, C, other)
    ck(fn["x_ret5"] < 0 and fn["x_btc_ret5"] < 0, "same move is negative for NO")
    ck(f["x_ofi1"] == 6.0 and fn["x_ofi1"] == -6.0, "signed flow: 10 YES-taker - 4 NO-taker = +6 for YES")
    ck(abs(f["x_mid"] - (0.90 + 0.20) / 2) < 1e-12 and abs(f["x_imb"] - (50 - 30) / 80) < 1e-12,
       "YES side: ask = 1 - NO bid, mid and imbalance from the rel-1 row")
    # no look-ahead: poison everything after the decision instant
    idx2 = [(r, (v if r <= -20 else 1e9)) for r, v in idx]
    rows2 = dict(rows)
    for r in range(-20, 1):
        rows2[r] = [r, 0.99, 1e6, 1e6, 0.001, 1e6, 1e6, 1, 1]
    trades2 = trades + [[(C - 20) * 1000 + 300, 0.10, 1e6, "no"]]
    other2 = {"BTC": [(r, (v if r <= -20 else 1.0)) for r, v in other["BTC"]]}
    f2 = features(cand, idx2, rows2, trades2, 99.995, C, other2)
    # the trade at close-20+0.3 s IS before the decision (close-20+0.2)? No: 0.3 > 0.2 -> excluded
    ck(all(f2[k] == f[k] for k in f), "poisoned future (prints after rel, rows >= rel, trades after +0.2 s) changes nothing")
    trades3 = trades + [[(C - 20) * 1000 + 100, 0.10, 7.0, "no"]]
    f3 = features(cand, idx, rows, trades3, 99.995, C, other)
    ck(f3["x_ofi1"] == -1.0, "a trade at +0.1 s (before the +0.2 s decision) IS counted")
    print("fc_features self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fills")
    ap.add_argument("--out")
    a = ap.parse_args()
    if not selftest():
        raise SystemExit(1)
    if a.selftest:
        return 0
    build(a.fills, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
