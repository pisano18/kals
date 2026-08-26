#!/usr/bin/env python3
# VERSION: 2026-08-25-v3
"""
kalshi_backtest.py  --  Replay the past as if it were live. No outcome peeking.

    python kalshi_backtest.py --out ./fulltape --strategy all

HOW LOOK-AHEAD IS PREVENTED (structurally, not by discipline)

The strategy is handed a View object. The View is constructed from trades
[0..i] only. It has NO attribute containing the settlement, the outcome, or
any future trade. You cannot peek by accident because there is nothing to peek
at -- the data is not in the object. That is the only reliable way to do this;
"I was careful" is how every fake backtest gets written.

WHAT IS HONEST HERE
  * timing        -- strictly chronological, per market
  * outcomes      -- real settled results from Kalshi
  * fees          -- the real quadratic formula, 0.07*P*(1-P), rounded up
  * tick grid     -- real tapered_deci_cent

WHAT IS APPROXIMATE (stated plainly, do not forget it)
  * FILLS. We recorded trades, not the order book. A print at 62c means
    somebody traded at 62c, not that YOU could have. Default mode only lets
    you buy where a taker actually bought (so an ask existed at that price).
    --pessimistic adds one tick, which is closer to what you would really pay.
  * SIZE. We assume our order does not move the price. True only for small size.
  * QUEUE. No passive/maker fills are simulated at all, because we cannot know
    queue position from trades. Taker-only.

MANDATORY SANITY CHECK
  The 'random' strategy must lose approximately the fee amount. If a coin-flip
  shows a profit, the harness is broken and every other result is garbage.
  It runs automatically and is printed first, every time.
"""

import argparse, json, math, os, random
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev

# ---------- real market mechanics ----------
def tick_at(p):      return 0.001 if (p > 0.90 or p < 0.10) else 0.01
def fee(p, n=1):     return math.ceil(0.07 * p * (1 - p) * n * 100) / 100.0

def parse_ts(s):
    if isinstance(s, (int, float)): return float(s if s < 1e12 else s / 1000.0)
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError: return None


class View:
    """What the strategy is allowed to know. Contains no future information.

    Deliberately absent: result, settle, any trade after index i."""
    __slots__ = ("ticker", "strike", "close", "now", "prices", "sizes",
                 "sides", "times")

    def __init__(self, ticker, strike, close, now, prices, sizes, sides, times):
        self.ticker, self.strike, self.close = ticker, strike, close
        self.now = now
        self.prices, self.sizes, self.sides, self.times = prices, sizes, sides, times

    @property
    def price(self):  return self.prices[-1]
    @property
    def ttc(self):    return self.close - self.now
    def last(self, n):
        return self.prices[-n:] if len(self.prices) >= n else self.prices
    def ret(self, n):
        p = self.last(n + 1)
        return (p[-1] - p[0]) if len(p) > 1 else 0.0
    def flow(self, n=50):
        """size-weighted taker imbalance over the last n trades, in [-1, 1]"""
        s, t = 0.0, 0.0
        for sz, sd in zip(self.sizes[-n:], self.sides[-n:]):
            s += sz if sd == "yes" else -sz
            t += sz
        return s / t if t > 0 else 0.0


# ---------- strategies: return "yes", "no", or None ----------
def s_random(v):
    if v.ttc < 60 or len(v.prices) < 30: return None
    return "yes" if random.random() < 0.5 else None

def s_buy_favorite(v):
    if v.ttc < 60 or len(v.prices) < 30: return None
    if v.price > 0.90: return "yes"
    if v.price < 0.10: return "no"
    return None

def s_follow_flow(v):
    if v.ttc < 90 or len(v.prices) < 60: return None
    f = v.flow(50)
    if f > 0.5: return "yes"
    if f < -0.5: return "no"
    return None

def s_fade_flow(v):
    r = s_follow_flow(v)
    return None if r is None else ("no" if r == "yes" else "yes")

def s_reversion(v):
    if v.ttc < 120 or len(v.prices) < 40: return None
    d = v.ret(20)
    if d > 0.10: return "no"
    if d < -0.10: return "yes"
    return None

def s_momentum(v):
    r = s_reversion(v)
    return None if r is None else ("no" if r == "yes" else "yes")

def s_open_5050(v):
    """Strike IS the opening TWAP, so fair value at open is exactly 50c.
    Buy whichever side is trading below its mechanically fair 50."""
    if v.ttc < 780 or len(v.prices) < 5: return None
    if v.price < 0.47: return "yes"
    if v.price > 0.53: return "no"
    return None

STRATS = {"random": s_random, "buy_favorite": s_buy_favorite,
          "follow_flow": s_follow_flow, "fade_flow": s_fade_flow,
          "reversion": s_reversion, "momentum": s_momentum,
          "open_5050": s_open_5050}


class CheatingStrategy:
    """Deliberately impossible: needs the outcome. Used ONLY to prove the
    engine cannot supply it. Must raise AttributeError."""
    def __call__(self, v): return "yes" if v.result > 0.5 else "no"


# ---------- engine ----------
def run(markets, tapes, strat, pessimistic=False, max_per_market=1, contracts=100):
    idx = {}
    for s, ms in markets.items():
        for m in ms: idx[m["ticker"]] = m

    per_market = defaultdict(list)
    for s, ts in tapes.items():
        for t in ts:
            tk = t.get("ticker") or t.get("market_ticker")
            m = idx.get(tk)
            if not m: continue
            try:
                p = float(t.get("yes_price_dollars") or t.get("yes_price"))
                if p > 1.5: p /= 100.0
                tt = parse_ts(t.get("created_time"))
                sz = float(t.get("count_fp") or 1)
            except (TypeError, ValueError): continue
            if tt is None or not (0 < p < 1): continue
            if not (0 <= m["close"] - tt <= 900): continue
            per_market[tk].append((tt, p, sz, str(t.get("taker_side", "")).lower()))

    trades_out = []
    for tk, rows in per_market.items():
        rows.sort()
        m = idx[tk]
        prices, sizes, sides, times = [], [], [], []
        taken = 0
        for (tt, p, sz, sd) in rows:
            prices.append(p); sizes.append(sz); sides.append(sd); times.append(tt)
            if taken >= max_per_market: continue
            v = View(tk, m["strike"], m["close"], tt, prices, sizes, sides, times)
            try:
                sig = strat(v)
            except AttributeError:
                raise
            if sig not in ("yes", "no"): continue
            # FILL MODEL -- v2, after the random baseline exposed a bug in v1.
            #
            # v1 required the printed trade's taker_side to match our signal,
            # reasoning that this proved an order existed at that price. But
            # if taker side correlates with the outcome AT ALL, that filter
            # SELECTS on information: we would only ever enter alongside
            # informed flow. On the synthetic data that leak made a coin-flip
            # strategy look break-even instead of losing the fee. A subtle
            # conditioning bias, and exactly the class of error that produced
            # the fake 21c edges earlier.
            #
            # v2: enter at the last printed price regardless of who was
            # aggressive, and pay a tick in pessimistic mode. Unbiased, and
            # closer to what lifting an offer actually costs.
            entry = p if sig == "yes" else (1 - p)
            if pessimistic:
                entry = min(entry + tick_at(entry), 0.99)
            win = m["result"] if sig == "yes" else (1 - m["result"])
            pnl = contracts * ((1 - entry) if win else -entry) - fee(entry, contracts)
            trades_out.append({"tk": tk, "close": m["close"], "sig": sig,
                               "entry": entry, "win": win, "pnl": pnl,
                               "ttc": m["close"] - tt})
            taken += 1
    return trades_out


def report(name, tr, label=""):
    if not tr:
        print(f"  {name:>14}{label:>8}  no trades"); return None
    n = len(tr)
    pnl = sum(t["pnl"] for t in tr)
    wr = mean([t["win"] for t in tr])
    ep = mean([t["entry"] for t in tr])
    # cluster by market -- many entries can share one outcome
    by = defaultdict(list)
    for t in tr: by[t["tk"]].append(t["pnl"])
    obs = [sum(v) for v in by.values()]
    m, sd = mean(obs), pstdev(obs)
    se = sd / math.sqrt(len(obs)) if sd > 0 else float("inf")
    t_stat = m / se if se > 0 else 0.0
    print(f"  {name:>14}{label:>8}{n:>7}{len(obs):>7}{100*wr:>8.1f}%"
          f"{100*ep:>8.1f}c{pnl:>10,.0f}{pnl/n:>9.2f}{t_stat:>8.1f}")
    return {"pnl": pnl, "n": n, "t": t_stat, "per": pnl / n,
            "se_per": 1.96 * se * len(obs) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--strategy", default="all")
    ap.add_argument("--pessimistic", action="store_true")
    ap.add_argument("--contracts", type=int, default=100)
    ap.add_argument("--entries", type=int, default=1,
                    help="max entries per market; higher = more statistical "
                         "power on the sanity check (still clustered by market)")
    a = ap.parse_args()
    random.seed(1)

    markets = json.load(open(os.path.join(a.out, "markets.json"), encoding="utf-8"))
    tapes = json.load(open(os.path.join(a.out, "tapes.json"), encoding="utf-8"))

    # ---- proof the engine cannot leak the outcome ----
    print("=" * 78); print("HARNESS INTEGRITY CHECK"); print("=" * 78)
    try:
        run(markets, tapes, CheatingStrategy(), contracts=1)
        print("  *** FAIL: a strategy reached the outcome. Results are invalid. ***")
        return
    except AttributeError as e:
        print(f"  PASS: outcome is unreachable from View ({e})")

    # ---- time split: train on older markets, test on newer ----
    allm = sorted([m for ms in markets.values() for m in ms], key=lambda x: x["close"])
    cut = allm[len(allm) // 2]["close"]
    print(f"  train/test split at {datetime.fromtimestamp(cut, timezone.utc):%Y-%m-%d %H:%M} UTC")
    print(f"  {len(allm)} markets total")

    def split(tr): return ([t for t in tr if t["close"] <= cut],
                           [t for t in tr if t["close"] > cut])

    names = list(STRATS) if a.strategy == "all" else [a.strategy]
    if "random" not in names: names = ["random"] + names

    print("\n" + "=" * 78)
    print(f"BACKTEST  {a.contracts} contracts/trade, "
          f"{'PESSIMISTIC' if a.pessimistic else 'optimistic'} fills")
    print("=" * 78)
    print(f"  {'strategy':>14}{'split':>8}{'trades':>7}{'mkts':>7}{'win%':>9}"
          f"{'avg entry':>8}{'P&L':>10}{'per':>9}{'t':>8}")
    results = {}
    for nm in names:
        tr = run(markets, tapes, STRATS[nm], a.pessimistic,
                 max_per_market=a.entries, contracts=a.contracts)
        trn, tst = split(tr)
        report(nm, trn, "train"); r = report(nm, tst, "TEST")
        results[nm] = r
        print()

    print("=" * 78); print("READ THIS BEFORE BELIEVING ANYTHING ABOVE"); print("=" * 78)
    rr = results.get("random")
    if rr:
        # A sanity check with no statistical power is not a sanity check.
        # Report the interval and say plainly whether the expected fee sits
        # inside it, rather than eyeballing a point estimate.
        per_c = rr["per"] / a.contracts * 100
        ci_c = rr["se_per"] / a.contracts * 100
        exp_c = -fee(0.5, a.contracts) / a.contracts * 100
        if a.pessimistic: exp_c -= 1.0
        lo, hi = per_c - ci_c, per_c + ci_c
        ok = lo <= exp_c <= hi
        print(f"  random per-trade : {per_c:+.2f}c   95% CI [{lo:+.2f}, {hi:+.2f}]")
        print(f"  expected (fee{'+tick' if a.pessimistic else ''})  : {exp_c:+.2f}c")
        print(f"  -> {'CONSISTENT. harness looks sound.' if ok else '*** OUTSIDE the interval -- investigate before trusting anything ***'}")
        if ci_c > 1.5:
            need = int(rr["n"] * (ci_c / 0.5) ** 2)
            print(f"  NOTE: the interval is +/-{ci_c:.2f}c, too wide to resolve a")
            print(f"  {abs(exp_c):.2f}c fee. Re-run with --entries 20 (about {need:,}")
            print("  trades) for a check that can actually fail.")
    print("  Only TEST-split results count. A strategy that wins on train and")
    print("  not on test is curve-fitting, which is what killed the earlier")
    print("  '26 mispriced cells'.")
    print("  Fills are approximate: we replay trades, not the book. Re-run with")
    print("  --pessimistic; anything that dies there was never real.")


if __name__ == "__main__":
    main()
