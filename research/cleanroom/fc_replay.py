#!/usr/bin/env python3
r"""fc_replay.py -- replay the clean-room forecaster and its loss-cutting variants over the recorded tape.

REPLAY, NOT LIVE: every number this prints is the tape population (offers that were displayed), priced with the
paper's 1-s survival rule. The 2026-09-10 amendment applies: it is valid for comparing one rule with another on the
same tape, INVALID as a loss rate for us. The live forecaster (forecaster_live.py) is the only source for that.

Data: the clean-room digest (scratchpad clean/digest): markets.jsonl (result, strike, round digits), index/<day> (the
last 240 s of prints per index and close), book/<day> (END-OF-SECOND top of book per market for its last 180 s),
trades/<day> (every trade in the last 300 s). Days 2026-08-25..09-26; TRAIN = ..09-17, TEST = 09-18.. (the digest's
split; the forecaster's tables were fitted on TRAIN, so TEST is the honest half).

Timing (no look-ahead): the book row for second s (state at close+s+0.999) is applied at close+s+1.0. The engine
decides at close+rel+0.2, so it sees the row for rel-1; the 1-s survival check at close+rel+1.2 sees the row for rel.
A print stamped T is received at T+LAG (0.1 s, the digest's measured 70-130 ms). Only the best level of each side
exists in the digest, so a variant never takes a second price level (same for every variant).

    python research/cleanroom/fc_replay.py --selftest
    python research/cleanroom/fc_replay.py --variants base --days all --out DIR
    python research/cleanroom/fc_replay.py --variants base,one_side,edge3 --days 2026-09-18,2026-09-19 --out DIR
Writes DIR/<variant>_fills.jsonl (one row per fill with its decision features and money) and DIR/<variant>_days.json.
"""
import argparse
import gzip
import json
import os
import sys
import time
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bettor_paper as B                        # noqa: E402
import fc_variants as FV                        # noqa: E402

DIGEST = r"C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\clean\digest"
LAG = 0.1
FIRST_ROW = -45
SERIES = {v[0] for v in B.COINS.values()}


def load_markets(digest):
    ms = []
    exp = {}
    with open(os.path.join(digest, "markets.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("series") not in SERIES:
                continue
            exp[(r["series"], r["close_ts"])] = r.get("kalshi_expiration_value")
            if r.get("result") in ("yes", "no") and r.get("floor_strike") is not None:
                ms.append(r)
    out = []
    for r in ms:
        strike = Decimal(str(r["floor_strike"]))
        if r["coin"] == "DOGE":
            pe = exp.get((r["series"], r["close_ts"] - 900))
            if pe:
                strike = Decimal(str(pe).replace(",", ""))
        out.append({"ticker": r["ticker"], "coin": r["coin"], "close_ts": r["close_ts"], "result": r["result"],
                    "strike": strike, "rd": int(r["round_digits"]), "split": r.get("split"),
                    "day": time.strftime("%Y-%m-%d", time.gmtime(r["close_ts"]))})
    return out


def load_day(digest, day, want_trades, keep=None):
    """keep: optional set of tickers -- only their books/trades are held in memory."""
    books, idx, trades = {}, {}, {}
    p = os.path.join(digest, "book", day + ".jsonl.gz")
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if keep is None or r["ticker"] in keep:
                books[r["ticker"]] = r["rows"]
    with gzip.open(os.path.join(digest, "index", day + ".jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            idx[(r["index_id"], r["close_ts"])] = r["prints"]
    if want_trades:
        tp = os.path.join(digest, "trades", day + ".jsonl.gz")
        if os.path.exists(tp):
            with gzip.open(tp, "rt", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    if keep is not None and r["ticker"] not in keep:
                        continue
                    c = r["close_ts"]
                    trades[r["ticker"]] = [t for t in r["trades"] if t[0] >= (c + FIRST_ROW) * 1000]
    return books, idx, trades


def snap_msg(row):
    """digest row [rel, yes_bid_p, yes_bid_sz, yes_d3, no_bid_p, no_bid_sz, no_d3, ...] -> a book snapshot message."""
    y = [["%.4f" % row[1], "%.2f" % row[2]]] if row[1] is not None and row[2] > 0 else []
    n = [["%.4f" % row[4], "%.2f" % row[5]]] if row[4] is not None and row[5] > 0 else []
    return {"yes_dollars_fp": y, "no_dollars_fp": n}


def run_close(close_s, mkts, books, idx, trades, variants, tables, feed_trades):
    """Replay one quarter-hour through every variant engine. Returns {variant: [fill rows]}."""
    clock = [close_s - 200.0]
    engines = [(name, FV.VEngine(B.Logger(None, None), lambda: clock[0], tables, FV.VARIANTS[name], name))
               for name in variants]
    live = [m for m in mkts if m["ticker"] in books]
    if not live:
        return {name: [] for name in variants}
    for _, e in engines:
        for m in live:
            e.add_market(m["ticker"], m["coin"], close_s, m["strike"], m["rd"], "digest")
    seen_idx = set()
    for m in live:
        iid = B.COINS[m["coin"]][1]
        if iid in seen_idx:
            continue
        seen_idx.add(iid)
        for rel, val in idx.get((iid, close_s), ()):
            st = close_s + rel
            for _, e in engines:
                e.on_print(iid, st * 1000, repr(val), st + LAG)
    ev = []
    for m in live:
        for row in books[m["ticker"]]:
            if row[0] >= FIRST_ROW:
                ev.append((close_s + row[0] + 1.0, 0, m["ticker"], row))
        if feed_trades:
            for tr in trades.get(m["ticker"], ()):
                ev.append((tr[0] / 1000.0, 1, m["ticker"], tr))
    for rel in range(-60, 1):
        ev.append((close_s + rel + 0.2, 2, None, None))
    ev.sort(key=lambda x: (x[0], x[1]))
    for t, kind, tk, x in ev:
        clock[0] = t
        for name, e in engines:
            if kind == 0:
                e.on_snapshot(tk, snap_msg(x), 1)
            elif kind == 1:
                if name in feed_trades:
                    e.on_trade(tk, {"ts_ms": x[0], "yes_price_dollars": str(x[1]), "count_fp": str(x[2]),
                                    "taker_side": x[3], "trade_id": ""})
            else:
                e.tick()
    clock[0] = close_s + 5.0
    out = {}
    res = {m["ticker"]: m for m in live}
    for name, e in engines:
        e.tick()
        rows = []
        for tk, mk in list(e.markets.items()):
            r = res[tk]["result"]
            for f in mk.fills:
                if f["strat"] != "forecaster":
                    continue
                win = f["side"] == r
                pnl = (f["size"] * (1 - f["price"]) if win else -f["size"] * f["price"]) - f["fee"]
                rows.append(dict(f, close_s=close_s, result=r, win=win, pnl=round(pnl, 4), coin=res[tk]["coin"],
                                 split=res[tk]["split"], day=res[tk]["day"]))
        out[name] = rows
    return out


def main_run(a):
    variants = a.variants.split(",")
    for v in variants:
        if v not in FV.VARIANTS:
            raise SystemExit("unknown variant %s" % v)
    feed_trades = {v for v in variants if v == "base" or FV.VARIANTS[v].get("flow_against") or FV.VARIANTS[v].get("quiet_s") or FV.VARIANTS[v].get("quiet_mult")}
    tables = B.Tables()
    ms = load_markets(a.digest)
    keep = None
    if a.markets_from:
        keep = set()
        with open(a.markets_from, encoding="utf-8") as f:
            for line in f:
                keep.add(json.loads(line)["ticker"])
        ms = [m for m in ms if m["ticker"] in keep]
        print("markets restricted to %d where base had any fill (every variant trades a subset of them)" % len(ms), flush=True)
    days = sorted({m["day"] for m in ms}) if a.days == "all" else a.days.split(",")
    os.makedirs(a.out, exist_ok=True)
    fhs = {v: open(os.path.join(a.out, "%s_fills.jsonl" % v), "a", encoding="utf-8") for v in variants}
    t0 = time.time()
    for day in days:
        d = load_day(a.digest, day, bool(feed_trades), keep)
        if d is None:
            print(day, "no book file -- skipped", flush=True)
            continue
        books, idx, trades = d
        by_close = {}
        for m in ms:
            if m["day"] == day:
                by_close.setdefault(m["close_ts"], []).append(m)
        n_f = {v: 0 for v in variants}
        pnl = {v: 0.0 for v in variants}
        for c in sorted(by_close):
            out = run_close(c, by_close[c], books, idx, trades, variants, tables, feed_trades)
            for v, rows in out.items():
                for r in rows:
                    fhs[v].write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
                    if r["fill"] == "real":
                        n_f[v] += 1
                        pnl[v] += r["pnl"]
        for fh in fhs.values():
            fh.flush()
        print("%s closes %d  %s  (%.0fs)" % (day, len(by_close), "  ".join("%s %d fills %+.0f" % (v, n_f[v], pnl[v])
              for v in variants), time.time() - t0), flush=True)


# ---------------------------------------------------------------------------------------------------- self-test
def selftest():
    fails = []
    ck = lambda ok, msg: None if ok else fails.append(msg)
    tb = B.Tables()
    C = 1_800_000_000 - (1_800_000_000 % 900)
    idx = {("BRTI", C): [[r, 101.0 + (0.01 if r % 2 else 0.0)] for r in range(-240, 4)]}

    def rows(offer_from, offer_to, price_no_bid=0.20, size=50.0):
        """YES ask at 1-price_no_bid (NO bid) displayed for rows offer_from..offer_to; nothing else."""
        out = []
        for s in range(-180, 1):
            if offer_from <= s <= offer_to:
                out.append([s, None, 0.0, 0.0, price_no_bid, size, size, 0, 1])
            else:
                out.append([s, None, 0.0, 0.0, None, 0.0, 0.0, 0, 0])
        return out
    mk = [{"ticker": "BTC-T", "coin": "BTC", "close_ts": C, "result": "yes", "strike": Decimal("100.00"), "rd": 2,
           "split": "TEST", "day": "x"}]
    # 1. offer displayed rows -40..-20: first decision with r <= 30 is rel -31 (sees row -32) -> real fill at the
    #    rel -30 check (row -31 still shows it) of min(100 cap, 50 displayed)
    out = run_close(C, mk, {"BTC-T": rows(-40, -20)}, idx, {}, ["base"], tb, set())
    real = [r for r in out["base"] if r["fill"] == "real"]
    ck(len(real) >= 1 and real[0]["rel"] == -31 and real[0]["size"] == 50 and abs(real[0]["price"] - 0.80) < 1e-9,
       "planted offer: real fill 50 @0.80 decided at rel -31 (%s)" % [(r["rel"], r["size"], r["price"]) for r in real])
    ck(abs(sum(r["pnl"] for r in real) - sum(r["size"] * 0.2 - r["fee"] for r in real)) < 1e-9 and all(r["win"] for r in real),
       "planted offer settles YES: pnl = 0.20 per contract less the fee")
    # 2. an offer that exists ONLY in row -25 is never seen by the rel -25 decision (it sees row -26) -- no look-ahead;
    #    the rel -24 decision sees it, and its survival check sees row -24 where it is gone -> no real fill
    out = run_close(C, mk, {"BTC-T": rows(-25, -25)}, idx, {}, ["base"], tb, set())
    ck(not [r for r in out["base"] if r["fill"] == "real"], "a one-second offer: seen late, gone at the check -> no real fill")
    opt = [r for r in out["base"] if r["fill"] == "opt"]
    ck(len(opt) == 1 and opt[0]["rel"] == -24, "the decision-instant rule sees the row -25 offer only at rel -24 (%s)" % [r["rel"] for r in opt])
    # 3. a losing market: same book, result NO -> money lost is price x size + fee
    mk_no = [dict(mk[0], result="no")]
    out = run_close(C, mk_no, {"BTC-T": rows(-40, -20)}, idx, {}, ["base"], tb, set())
    real = [r for r in out["base"] if r["fill"] == "real"]
    ck(real and all(not r["win"] and abs(r["pnl"] + r["size"] * r["price"] + r["fee"]) < 1e-9 for r in real), "a losing fill costs price x size + fee")
    # 4. empty worlds: no book; index on the strike with an 80c offer
    out = run_close(C, mk, {"BTC-T": rows(99, 99)}, idx, {}, ["base"], tb, set())
    ck(out["base"] == [], "no offer: nothing")
    idx2 = {("BRTI", C): [[r, 99.994 if r % 2 else 99.996] for r in range(-240, 4)]}
    out = run_close(C, mk, {"BTC-T": rows(-40, -20)}, idx2, {}, ["base"], tb, set())
    ck(not [r for r in out["base"] if -31 <= r["rel"] <= -21], "coin-flip index: no buy while 21-30 prints remain")
    # 5. variants run side by side on one tape and a gate removes its target
    out = run_close(C, mk, {"BTC-T": rows(-40, -20)}, idx, {}, ["base", "floor85"], tb, set())
    ck(out["base"] and out["floor85"] == [], "floor85 removes the 80c fill that base takes")
    print("fc_replay self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--variants", default="base")
    ap.add_argument("--days", default="all")
    ap.add_argument("--digest", default=DIGEST)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(DIGEST), "fcvar"))
    ap.add_argument("--markets-from", help="a base _fills.jsonl: replay only the markets it traded in")
    a = ap.parse_args()
    if not (FV.selftest() and selftest()):
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    main_run(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
