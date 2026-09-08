#!/usr/bin/env python3
"""
pinfeat_book.py -- FEATURE FAMILY 2: the order book as a risk signal.

Read-only. Places nothing. Writes only under a scratch dir it owns.

WHAT IT ANSWERS
    pin buys a near-certain binary in the last seconds of a 15-minute crypto
    market. Today p_flip is whatever the gaussian settlement model says. The
    per-trade floor is  fee + p_flip*price/(1-p_flip), so p_flip IS the risk
    budget. This file asks whether the ORDER BOOK at the instant of decision
    carries information about p_flip that the gaussian does not.

STAGES
    1  ground truth   -- decided calls, and did the favoured side actually win
    2  touch features -- from the ticker channel (the channel pin reads)
    3  book features  -- from orderbook_delta, replayed seq-ordered
    4  scoring        -- Brier / log-loss lift over the gaussian, walk forward,
                         with a deliberately leaking variant as the control
"""
import argparse
import gzip
import json
import math
import os
import sys
from array import array
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)          # repo modules FIRST -- kals-work shadows some
from engine import var_factor                              # noqa: E402
from statistics import NormalDist                          # noqa: E402

ND = NormalDist()
N_AVG = 60

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape"
WORK = os.path.join(os.environ.get("TEMP", "/tmp"), "pinfeat_book")

# round_digits per series -- NEVER inferred from magnitude. Operator-supplied,
# cross-checked below against the strike/settle identity.
ROUND_DIGITS = {
    "KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
    "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
    "KXHYPE15M": 4, "KXNEAR15M": 4,
    "KXDOGE15M": 7,
}
SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXBNB15M": "BNBUSD_RTI",
    "KXSOL15M": "SOLUSD_RTI", "KXXRP15M": "XRPUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
    "KXDOGE15M": "DOGEUSD_RTI",
}


def keff(floor_strike, rd):
    """The level settlement must EXCEED for YES. Kalshi rounds the settle to
    `rd` digits and compares to the floor strike, so the knife edge sits half
    a rounding unit below the strike."""
    return floor_strike - 0.5 * (10.0 ** -rd)


# ==========================================================================
# stage 1a -- markets, with DOGE's truncated strike repaired from the identity
# ==========================================================================
def load_markets(fulltape=FULLTAPE, verbose=True):
    raw = json.load(open(os.path.join(fulltape, "markets.json")))
    out = {}
    repaired = 0
    for s, rows in raw.items():
        if not rows or s not in ROUND_DIGITS:
            continue
        rows = sorted(rows, key=lambda m: m["close"])
        prev = None
        for m in rows:
            st = m.get("strike")
            cl = m.get("close")
            if st is None or cl is None:
                prev = m
                continue
            # strike(N+1) == settle(N) EXACTLY (verified on BTC 1193/1193 and
            # SOL 1197/1197). markets.json stores DOGE's strike truncated to
            # 6 dp while round_digits is 7, so the PREVIOUS window's settle --
            # published 900 s before OUR close, hence not lookahead -- is the
            # full-precision floor strike.
            if (prev is not None and prev.get("settle") is not None
                    and abs(cl - prev["close"] - 900) < 1.0
                    and abs(prev["settle"] - st) < 10.0 ** -(ROUND_DIGITS[s] - 1)
                    and prev["settle"] != st):
                st = prev["settle"]
                repaired += 1
            out[m["ticker"]] = {
                "tk": m["ticker"], "series": s, "close": int(cl),
                "strike": st, "settle": m.get("settle"),
                "result": m.get("result"), "rd": ROUND_DIGITS[s],
            }
            prev = m
    if verbose:
        print("  markets: {:,} settled, {:,} strikes repaired from the "
              "previous window's settle".format(len(out), repaired))
    return out


def check_outcomes(markets, verbose=True):
    """result must equal (settle > K_eff). If it does not, every flip label
    below is wrong and nothing else in this file means anything."""
    agree = disagree = skip = 0
    bad = []
    per = defaultdict(lambda: [0, 0])
    for m in markets.values():
        if m["settle"] is None or m["result"] is None:
            skip += 1
            continue
        pred = 1.0 if m["settle"] > keff(m["strike"], m["rd"]) else 0.0
        if pred == m["result"]:
            agree += 1
            per[m["series"]][0] += 1
        else:
            disagree += 1
            per[m["series"]][1] += 1
            if len(bad) < 6:
                bad.append((m["tk"], repr(m["strike"]), repr(m["settle"]),
                            m["result"]))
    if verbose:
        print("  outcome rule (settle > strike - 0.5e-rd): agree {:,} "
              "disagree {:,} skip {:,}".format(agree, disagree, skip))
        for s in sorted(per):
            print("     {:<12} agree {:<5} disagree {}".format(
                s, per[s][0], per[s][1]))
        for b in bad:
            print("     mismatch", b)
    return agree, disagree


# ==========================================================================
# stage 1b -- the 1/sec settlement index
# ==========================================================================
def iter_gz(path):
    """Yield raw lines. The newest hour file of any channel is a live,
    truncated gzip: EOFError and zlib.error both mean 'that is all there is'."""
    try:
        with gzip.open(path, "rb") as f:
            for line in f:
                yield line
    except EOFError:
        return
    except OSError:
        return
    except Exception as e:
        if type(e).__name__ != "error":       # zlib.error
            raise
        return


def load_index(data=DATA, verbose=True):
    """index_id -> (base_sec, array('d')) dense per second, nan where missing.

    Values come from msg.data (the raw CF Benchmarks payload) whose `time` is
    the print's own second -- not received_at, which lags."""
    # accumulate into typed arrays, not tuples: ~10M prints as (int, float)
    # tuples costs the better part of a gigabyte and this box is shared.
    ts = defaultdict(lambda: array("q"))
    vs = defaultdict(lambda: array("d"))
    files = sorted(os.listdir(os.path.join(data, "cfbenchmarks_value")))
    for i, fn in enumerate(files):
        fp = os.path.join(data, "cfbenchmarks_value", fn)
        for line in iter_gz(fp):
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("msg") or {}
            iid = msg.get("index_id")
            if not iid:
                continue
            try:
                inner = json.loads(msg["data"])
                t = int(inner["time"]) // 1000
                v = float(inner["value"])
            except Exception:
                continue
            ts[iid].append(t)
            vs[iid].append(v)
        if verbose and (i + 1) % 80 == 0:
            print("    index {}/{} files".format(i + 1, len(files)), flush=True)
    out = {}
    for iid in list(ts):
        tt, vv = ts.pop(iid), vs.pop(iid)
        base, top = min(tt), max(tt)
        arr = array("d", [math.nan]) * (top - base + 1)
        for j in range(len(tt)):
            arr[tt[j] - base] = vv[j]
        out[iid] = (base, arr)
        if verbose:
            n = sum(1 for x in arr if x == x)
            print("    {:<14} {:,} ticks over {:,} s ({:.1f}% dense)".format(
                iid, n, len(arr), 100.0 * n / len(arr)))
    return out


def tick_at(idx, sec):
    base, arr = idx
    i = sec - base
    if i < 0 or i >= len(arr):
        return None
    v = arr[i]
    return None if v != v else v


def save_index(idx, path):
    with open(path, "wb") as f:
        f.write(json.dumps({k: [v[0], len(v[1])] for k, v in idx.items()}
                           ).encode() + b"\n")
        for k in sorted(idx):
            idx[k][1].tofile(f)


def load_index_cache(path):
    with open(path, "rb") as f:
        head = json.loads(f.readline())
        out = {}
        for k in sorted(head):
            base, n = head[k]
            a = array("d")
            a.fromfile(f, n)
            out[k] = (base, a)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="1")
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if a.stage == "1":
        mk = load_markets()
        check_outcomes(mk)
    elif a.stage == "index":
        idx = load_index(a.data)
        save_index(idx, os.path.join(WORK, "index.bin"))
        print("  wrote", os.path.join(WORK, "index.bin"))


if __name__ == "__main__":
    main()
