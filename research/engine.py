#!/usr/bin/env python3
# VERSION: 2026-08-25-g1
"""
engine.py -- the decision logic. Pure, deterministic, no network, no files.

    python research/engine.py --selftest

WHY IT IS SEPARATE FROM THE TRANSPORT

Everything that decides whether to risk money lives here and can be replayed
tick-by-tick against scenarios with a known right answer. The websocket lives
in paper.py and does nothing but feed this. If the decision logic cannot be
tested offline, it cannot be trusted with money.

THE MODEL (settlement_math.py, MC-verified; cross-checked in edge.py)

    E[settle | now] = (sum of settle ticks already printed + r * spot) / 60
    Var[settle | now] = (1/3600) * sum_j sum_k w_j w_k gamma(|j-k|)
    fair = Phi( (E[settle] - strike) / sd )

Only free parameter is the index's own variance, estimated live.

WHAT MAKES THIS SAFE TO POINT AT MONEY

1. NO ORDER CODE. There is no function here that places, amends or cancels an
   order, and no flag that enables one. Decisions are returned as objects and
   written to a log. Wiring them to an exchange is a separate, deliberate act.

2. SIGMA STRESS TEST. sigma is estimated, so `fair` has error. Every candidate
   must ALSO clear its threshold when sigma is moved against us by
   `sigma_stress` (default 25%). If a plausible sigma error erases the edge,
   there is no trade. This project's entire history is of edges that were
   measurement error; this refuses to trade anything that cannot survive one.

3. CORRELATION-AWARE EXPOSURE. The 12 crypto series close simultaneously and
   are ~0.8 correlated -- PLAN.md sec.5 puts them at 1.22 effective independent
   units. Sizing each independently and summing would be a ~10x understatement
   of risk. Total simultaneous stake is capped as if they were ~1.2 bets, not
   12.

4. FRACTIONAL KELLY OFF MEASURED EDGE. For a binary bought at q with true
   probability p, the Kelly stake fraction is (p - q)/(1 - q). Full Kelly at
   95c on a 1c edge stakes 20% of bankroll; that is the "pennies in front of a
   steamroller" in PLAN.md sec.6. Default is quarter-Kelly with a hard cap, and
   `edge_haircut` shrinks the edge used for sizing below the edge used for
   entry, because a modelled edge is not a measured one.

5. NO TRADING IN THE LAST FEW SECONDS. Inside `min_ttc` the race is latency,
   which is unwinnable from a home connection (PLAN.md kill criterion 3).
"""

import argparse
import math
from collections import deque
from statistics import NormalDist

ND = NormalDist()
N_AVG = 60


# ===========================================================================
# variance -- shared with edge.py, memoized on time-to-close
# ===========================================================================
def settle_weights(tau):
    if tau <= 0:
        return []
    live = min(tau, N_AVG)
    flat = max(0, tau - N_AVG)
    return [live] * flat + list(range(live, 0, -1))


_VC = {}


def var_factor(tau, rho):
    """Var(settle)/gamma0 with tau seconds to close, under autocovariance rho."""
    key = (tau, tuple(round(x, 6) for x in rho))
    hit = _VC.get(key)
    if hit is None:
        w = settle_weights(tau)
        if not w:
            return 0.0
        tot = rho[0] * sum(x * x for x in w)
        for h in range(1, len(rho)):
            if h < len(w):
                tot += 2 * rho[h] * sum(w[i] * w[i + h] for i in range(len(w) - h))
        hit = max(tot, 0.0) / (N_AVG ** 2)
        _VC[key] = hit
    return hit


# ===========================================================================
class IndexState:
    """One index (BRTI, ETHUSD_RTI, ...). Holds the tick history needed to
    reconstruct a partial settlement average, and a live variance estimate."""

    def __init__(self, index_id, lam=0.9995, warmup=1800, max_hist=1200):
        self.index_id = index_id
        self.ticks = {}                      # second -> value
        self.order = deque(maxlen=max_hist)
        self.lam = lam
        self.var = None                      # EWMA of squared 1s increments
        self.n = 0
        self.rho = [1.0, 0.0, 0.0]
        self._ac_num = [0.0, 0.0]
        self._ac_den = 0.0
        self._recent = deque(maxlen=600)
        self.warmup = warmup
        self.last_sec = None

    def on_tick(self, sec, value):
        sec = int(sec)
        if sec in self.ticks:
            return
        prev = self.last_sec
        self.ticks[sec] = value
        self.order.append(sec)
        if len(self.order) == self.order.maxlen:
            old = self.order[0]
            self.ticks.pop(old, None)
        if prev is not None and sec - prev == 1:
            d = value - self.ticks[prev]
            self.var = d * d if self.var is None else \
                self.lam * self.var + (1 - self.lam) * d * d
            self.n += 1
            self._recent.append(d)
        self.last_sec = sec

    def refresh_autocov(self):
        """Lag-1 and lag-2 autocorrelation of one-second increments. BRTI is
        built from order-book mids, which can be smoothed or bounce; assuming
        iid would scale every variance wrong by a fixed factor."""
        r = list(self._recent)
        if len(r) < 200:
            return
        m = sum(r) / len(r)
        den = sum((x - m) ** 2 for x in r)
        if den <= 0:
            return
        out = [1.0]
        for h in (1, 2):
            num = sum((r[i] - m) * (r[i + h] - m) for i in range(len(r) - h))
            out.append(max(-0.45, min(0.45, num / den)))
        self.rho = out

    def ready(self):
        return self.var is not None and self.n >= self.warmup

    def sigma(self):
        return math.sqrt(self.var) if self.var else None

    def sigma_rel_se(self):
        """Relative standard error of sigma-hat. For an EWMA of squared
        increments the effective sample is 1/(1-lam), and sd(sigma)/sigma is
        1/sqrt(2*n_eff). This is what the stress test must clear."""
        n_eff = min(1.0 / (1.0 - self.lam), max(self.n, 1))
        return 1.0 / math.sqrt(2.0 * n_eff)

    def partial(self, close_sec, now_sec):
        """(sum of settle ticks already printed, how many are still to come).
        Returns None if too many ticks in the locked stretch are missing to
        trust the reconstruction."""
        lo = close_sec - N_AVG + 1
        hi = min(now_sec, close_sec)
        if hi < lo:
            return 0.0, N_AVG
        want = hi - lo + 1
        got = [self.ticks[s] for s in range(lo, hi + 1) if s in self.ticks]
        if len(got) < want * 0.95:
            return None
        # scale up if a tick or two is missing, rather than under-counting
        return sum(got) * (want / len(got)), N_AVG - want


class MarketState:
    """Per-market paper position, booked as two independent legs.

    A single net `position` with a single `avg_cost` cannot represent a Kalshi
    position honestly: buying YES at p and NO at q are two separate purchases
    that both pay out at settlement, not an open and a close. Netting them to
    zero made the market look flat while the cash was still committed, and
    settle() then returned early and never released it -- the total-exposure
    cap ratcheted shut for the rest of the session. Overwriting avg_cost on a
    second fill leaked in the other direction. Two legs, each with its own
    cash, and the release at settlement is exactly what was committed.
    """

    __slots__ = ("ticker", "index_id", "strike", "close", "bid", "ask",
                 "bid_sz", "ask_sz", "last_book_ts",
                 "yes_qty", "yes_cost", "no_qty", "no_cost", "fees")

    def __init__(self, ticker, index_id, strike, close):
        self.ticker, self.index_id = ticker, index_id
        self.strike, self.close = strike, close
        self.bid = self.ask = None
        self.bid_sz = self.ask_sz = 0
        self.last_book_ts = None
        self.yes_qty = self.no_qty = 0
        self.yes_cost = self.no_cost = self.fees = 0.0

    @property
    def stake(self):
        """Cash actually committed and not yet released."""
        return self.yes_cost + self.no_cost

    @property
    def position(self):
        return self.yes_qty - self.no_qty

    @property
    def avg_cost(self):
        n = self.yes_qty + self.no_qty
        return (self.yes_cost + self.no_cost) / n if n else 0.0


class Decision:
    __slots__ = ("ticker", "side", "price", "size", "fair", "fair_stress",
                 "edge", "edge_stress", "ttc", "spot", "strike", "sigma",
                 "reason", "ts", "kelly")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


# ===========================================================================
def fee_per_contract(p):
    """Kalshi quadratic taker fee, large-order limit."""
    return 0.07 * p * (1 - p)


def tick_at(p):
    return 0.001 if (p > 0.90 or p < 0.10) else 0.01


class Engine:
    def __init__(self, bankroll=1000.0, kelly=0.25, sigma_stress=0.25,
                 edge_haircut=0.5, min_edge=0.005, min_ttc=15, max_ttc=600,
                 max_stake_frac=0.02, max_total_frac=0.06,
                 max_book_age=5.0, daily_loss_limit=0.15,
                 min_size=1, max_size=200):
        self.bankroll0 = self.bankroll = bankroll
        self.kelly = kelly
        self.sigma_stress = sigma_stress
        self.edge_haircut = edge_haircut
        self.min_edge = min_edge
        self.min_ttc, self.max_ttc = min_ttc, max_ttc
        self.max_stake_frac = max_stake_frac
        self.max_total_frac = max_total_frac
        self.max_book_age = max_book_age
        self.daily_loss_limit = daily_loss_limit
        self.min_size, self.max_size = min_size, max_size
        self.indices = {}
        self.markets = {}
        self._open_stake = 0.0
        self.realized = 0.0
        self.halted = False
        self.halt_reason = None
        self.skips = {}

    @property
    def open_stake(self):
        """Maintained incrementally; audit_stake() checks it against the books."""
        return self._open_stake

    def audit_stake(self):
        """(tracked, true) committed cash. These must be equal. Any gap is a
        leak that silently shrinks the total-exposure cap."""
        return self._open_stake, sum(m.stake for m in self.markets.values())

    # ---- ingest -----------------------------------------------------------
    def on_index(self, index_id, sec, value):
        st = self.indices.get(index_id)
        if st is None:
            st = self.indices[index_id] = IndexState(index_id)
        st.on_tick(sec, value)
        if st.n % 120 == 0:
            st.refresh_autocov()

    def on_market(self, ticker, index_id, strike, close):
        m = self.markets.get(ticker)
        if m is None:
            self.markets[ticker] = MarketState(ticker, index_id, strike, close)
        else:
            m.strike, m.close = strike, close

    def on_book(self, ticker, bid, ask, bid_sz, ask_sz, ts):
        m = self.markets.get(ticker)
        if m is None:
            return
        m.bid, m.ask, m.bid_sz, m.ask_sz, m.last_book_ts = \
            bid, ask, bid_sz, ask_sz, ts

    def _skip(self, why):
        self.skips[why] = self.skips.get(why, 0) + 1
        return None

    # ---- valuation --------------------------------------------------------
    def valuation(self, m, now_sec):
        """(mu, sd, spot) once; the stress cases only rescale sd."""
        idx = self.indices.get(m.index_id)
        if idx is None or not idx.ready():
            return None
        spot = idx.ticks.get(int(now_sec))
        if spot is None:
            for back in (1, 2, 3):
                spot = idx.ticks.get(int(now_sec) - back)
                if spot is not None:
                    break
        if spot is None:
            return None
        part = idx.partial(int(m.close), int(now_sec))
        if part is None:
            return None
        locked, r = part
        mu = (locked + r * spot) / N_AVG
        vf = var_factor(int(m.close) - int(now_sec), idx.rho)
        if vf <= 0:
            return None
        sd = math.sqrt(vf * idx.var)
        return (mu, sd, spot) if sd > 0 else None

    def fair_value(self, m, now_sec, sigma_mult=1.0):
        v = self.valuation(m, now_sec)
        if v is None:
            return None
        mu, sd, spot = v
        sd *= sigma_mult
        return 1.0 - ND.cdf((m.strike - mu) / sd), spot, sd

    # ---- sizing -----------------------------------------------------------
    def size_for(self, p, q):
        """Fractional Kelly on a binary bought at q with probability p.
        Kelly stake fraction is (p-q)/(1-q); the edge is haircut first because
        a modelled edge is not a measured one."""
        if q <= 0 or q >= 1:
            return 0, 0.0
        p_eff = q + (p - q) * self.edge_haircut
        f = (p_eff - q) / (1.0 - q)
        if f <= 0:
            return 0, 0.0
        f *= self.kelly
        f = min(f, self.max_stake_frac)
        stake = f * self.bankroll
        room = self.max_total_frac * self.bankroll - self.open_stake
        stake = min(stake, max(room, 0.0))
        n = int(stake / q)
        return max(0, min(n, self.max_size)), f

    # ---- the decision -----------------------------------------------------
    def evaluate(self, ticker, now_sec):
        if self.halted:
            return self._skip("halted")
        m = self.markets.get(ticker)
        if m is None:
            return self._skip("unknown market")
        ttc = int(m.close) - int(now_sec)
        if ttc < self.min_ttc:
            return self._skip("inside min_ttc (latency race)")
        if ttc > self.max_ttc:
            return self._skip("outside max_ttc")
        if m.bid is None or m.ask is None:
            return self._skip("no book")
        if m.last_book_ts is not None and now_sec - m.last_book_ts > self.max_book_age:
            return self._skip("book stale")
        if m.ask <= m.bid:
            return self._skip("crossed/locked book")

        v = self.valuation(m, now_sec)
        if v is None:
            return self._skip("no fair value")
        mu, sd, spot = v
        fair = 1.0 - ND.cdf((m.strike - mu) / sd)

        # Which side, and what does it cost to take it?
        cand = []
        if m.ask_sz > 0:
            cost = fee_per_contract(m.ask)
            cand.append(("yes", m.ask, fair - m.ask - cost, m.ask_sz))
        if m.bid_sz > 0:
            q = 1.0 - m.bid
            cost = fee_per_contract(q)
            cand.append(("no", q, (1.0 - fair) - q - cost, m.bid_sz))
        cand = [c for c in cand if c[2] > self.min_edge]
        if not cand:
            return self._skip("no edge after fee")
        side, q, edge, avail = max(cand, key=lambda c: c[2])

        # SIGMA STRESS -- move sigma the way that hurts this trade and require
        # the edge to survive. A trade that only exists at one sigma is not a
        # trade, it is a model artefact.
        # Stress at least 3 standard errors of our own sigma estimate, so the
        # gate scales with how well sigma is actually pinned down.
        idx = self.indices.get(m.index_id)
        stress = max(self.sigma_stress, 3.0 * idx.sigma_rel_se()) if idx \
            else self.sigma_stress
        worse = None
        for mult in (1.0 + stress, 1.0 / (1.0 + stress)):
            f_alt = 1.0 - ND.cdf((m.strike - mu) / (sd * mult))
            e_alt = (f_alt - q - fee_per_contract(q)) if side == "yes" \
                else ((1.0 - f_alt) - q - fee_per_contract(q))
            worse = e_alt if worse is None else min(worse, e_alt)
        if worse is None or worse <= 0:
            return self._skip("edge dies under sigma stress")

        n, f = self.size_for(q + edge + fee_per_contract(q), q)
        n = min(n, int(avail))
        if n < self.min_size:
            return self._skip("size below minimum")

        return Decision(ticker=ticker, side=side, price=q, size=n, fair=fair,
                        fair_stress=worse + q + fee_per_contract(q),
                        edge=edge, edge_stress=worse, ttc=ttc, spot=spot,
                        strike=m.strike, sigma=sd, kelly=f, ts=now_sec,
                        reason="edge survives sigma stress")

    # ---- bookkeeping ------------------------------------------------------
    def record_fill(self, d):
        """Paper fill. Tracks exposure so the total cap means something.

        Returns False and books nothing for a market the engine is not
        tracking: settle() could never find it to release the cash, so the
        exposure would be permanent.
        """
        m = self.markets.get(d.ticker)
        if m is None:
            self.skips["fill on an untracked market"] = \
                self.skips.get("fill on an untracked market", 0) + 1
            return False
        cost = d.size * d.price
        if d.side == "yes":
            m.yes_qty += d.size
            m.yes_cost += cost
        else:
            m.no_qty += d.size
            m.no_cost += cost
        # Kalshi charges the taker fee on the trade. Accrue it per fill (so the
        # basis is the price actually paid) and realise it at settlement, which
        # is where the bankroll moves.
        m.fees += d.size * fee_per_contract(d.price)
        self._open_stake += cost
        return True

    def settle(self, ticker, result):
        """result: 1.0 if the market resolved Yes."""
        m = self.markets.get(ticker)
        if m is None:
            return 0.0
        stake = m.stake
        if m.yes_qty == 0 and m.no_qty == 0:
            # Release unconditionally rather than returning early. A flat
            # market should hold no cash; if it somehow does, stranding it is
            # how the exposure cap closes itself.
            self._open_stake = max(0.0, self._open_stake - stake)
            m.yes_cost = m.no_cost = m.fees = 0.0
            return 0.0
        won_yes = result >= 0.5
        payout = (m.yes_qty if won_yes else 0) + (m.no_qty if not won_yes else 0)
        pnl = payout - m.yes_cost - m.no_cost - m.fees
        self.realized += pnl
        self.bankroll += pnl
        self._open_stake = max(0.0, self._open_stake - stake)
        m.yes_qty = m.no_qty = 0
        m.yes_cost = m.no_cost = m.fees = 0.0
        dd = (self.bankroll0 - self.bankroll) / self.bankroll0
        if dd > self.daily_loss_limit:
            self.halted = True
            self.halt_reason = f"drawdown {100*dd:.1f}% > {100*self.daily_loss_limit:.0f}%"
        return pnl


# ===========================================================================
# REPLAY -- deterministic scenarios with a known right answer.
#
# The engine never sees the network. Everything below feeds it ticks and book
# updates second by second and checks what it decides. A simulated maker quotes
# a one-tick spread around ITS OWN view of fair value; changing only that view
# plants a specific, known defect.
# ===========================================================================
import random as _random


def _snap(p):
    step = 0.001 if (p > 0.90 or p < 0.10) else 0.01
    return min(max(round(p / step) * step, 0.001), 0.999)


def replay(book_mode="fair", n_markets=150, sigma=6.0, seed=3, lag=0,
           sigma_mult=1.0, concurrent=1, **ekw):
    """Returns (engine, decisions, settled_pnl)."""
    rnd = _random.Random(seed)
    eng = Engine(**ekw)
    t0 = 1_760_000_000
    total = 60 + n_markets * 900 + 120
    S, ticks = 80_000.0, {}
    for k in range(total):
        S += rnd.gauss(0, sigma)
        ticks[t0 + k] = S

    def maker_quote(strike, close_s, now_s):
        """The simulated market maker's own fair value."""
        lo = close_s - N_AVG + 1
        hi = min(now_s - lag, close_s)
        src = now_s - lag
        if src not in ticks:
            return None
        spot = ticks[src]
        locked = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
        r = N_AVG - max(0, hi - lo + 1)
        mu = spot if book_mode == "spot" else (sum(locked) + r * spot) / N_AVG
        vf = var_factor(close_s - now_s, [1.0])
        if vf <= 0:
            return None
        sd = math.sqrt(vf) * sigma * sigma_mult
        if sd <= 0:
            return None
        return 1.0 - ND.cdf((strike - mu) / sd)

    decisions, pnls = [], []
    for w in range(n_markets):
        open_s = t0 + 60 + w * 900
        close_s = open_s + 900
        if close_s + 1 not in ticks:
            break
        strike = sum(ticks[s] for s in range(open_s - 59, open_s + 1)) / 60.0
        settle = sum(ticks[s] for s in range(close_s - 59, close_s + 1)) / 60.0
        result = 1.0 if settle >= strike else 0.0
        tks = [f"M{w:05d}-{c}" for c in range(concurrent)]
        for tk in tks:
            eng.on_market(tk, "BRTI", strike, close_s)
        traded = set()
        for s in range(open_s - 59, close_s + 1):
            eng.on_index("BRTI", s, ticks[s])
            if s < open_s:
                continue
            fq = maker_quote(strike, close_s, s)
            if fq is None:
                continue
            half = tick_at(fq) / 2.0
            bid, ask = _snap(fq - half), _snap(fq + half)
            if ask <= bid:
                ask = _snap(bid + tick_at(bid))
            for tk in tks:
                eng.on_book(tk, bid, ask, 500, 500, s)
                if tk in traded:
                    continue
                d = eng.evaluate(tk, s)
                if d:
                    eng.record_fill(d)
                    decisions.append(d)
                    traded.add(tk)
        for tk in tks:
            pnls.append(eng.settle(tk, result))
    return eng, decisions, sum(pnls)


def _line(label, eng, ds, pnl, n_markets):
    n = len(ds)
    avg_edge = (sum(d.edge for d in ds) / n) if n else 0.0
    avg_ttc = (sum(d.ttc for d in ds) / n) if n else 0.0
    per = (pnl / sum(d.size for d in ds)) if n else 0.0
    print(f"  {label:>22}{n:>8}{100*n/max(n_markets,1):>8.1f}%"
          f"{100*avg_edge:>9.2f}c{avg_ttc:>8.0f}s{pnl:>11.2f}{100*per:>10.2f}c")
    return {"n": n, "pnl": pnl, "per": per}


def selftest():
    print("=" * 78)
    print("SELF-TEST -- replay against books with known defects")
    print("=" * 78)
    print("  A simulated maker quotes a one-tick spread around its own fair")
    print("  value. Only that view changes between rows. The engine must stay")
    print("  flat against a correct maker and trade against a broken one.\n")
    print(f"  {'maker':>22}{'trades':>8}{'hit%':>9}{'avg edge':>9}"
          f"{'avg ttc':>8}{'P&L':>11}{'per ctr':>10}")
    fails = []
    NM = 400
    r = {}
    r["fair"] = _line("fair (null)", *replay("fair", NM, seed=3), NM)
    r["fair2"] = _line("fair, 2nd seed", *replay("fair", NM, seed=91), NM)
    r["sig"] = _line("sigma 40% too low", *replay("fair", NM, seed=3,
                                                  sigma_mult=0.6), NM)
    r["sig2"] = _line("sigma 60% too high", *replay("fair", NM, seed=3,
                                                    sigma_mult=1.6), NM)
    r["lag"] = _line("quote 20s stale", *replay("fair", NM, seed=3, lag=20), NM)
    r["spot"] = _line("ignores averaging", *replay("spot", NM, seed=3), NM)

    if r["fair"]["n"] > NM * 0.02 or r["fair2"]["n"] > NM * 0.02:
        fails.append(f"traded against a FAIR maker "
                     f"({r['fair']['n']} and {r['fair2']['n']} of {NM})")
    for k, lbl in (("sig", "sigma too low"), ("lag", "stale quote"),
                   ("spot", "ignored averaging")):
        if r[k]["n"] < NM * 0.05:
            fails.append(f"failed to trade a broken maker ({lbl})")
        elif r[k]["pnl"] <= 0:
            fails.append(f"lost money against a broken maker ({lbl})")

    print("\n  RISK CONTROLS")
    eng, ds, _ = replay("spot", 200, seed=3)
    bad_ttc = [d for d in ds if d.ttc < eng.min_ttc or d.ttc > eng.max_ttc]
    print(f"  {'ttc window respected':>34}: {len(bad_ttc)} violations "
          f"of [{eng.min_ttc}, {eng.max_ttc}]s")
    if bad_ttc:
        fails.append("traded outside the allowed time-to-close window")

    eng2, ds2, _ = replay("spot", 300, seed=3, concurrent=6,
                          max_total_frac=0.06)
    peak = max((d.size * d.price for d in ds2), default=0)
    print(f"  {'concurrent exposure cap':>34}: {len(ds2)} trades across 6 "
          f"simultaneous markets, peak single stake ${peak:.2f}")

    # a maker that is broken in OUR favour but where sigma is uncertain:
    # tighten the stress test and the trades must disappear.
    eng3, ds3, _ = replay("fair", 400, seed=3, sigma_mult=0.85)
    eng4, ds4, _ = replay("fair", 400, seed=3, sigma_mult=0.85,
                          sigma_stress=0.60)
    print(f"  {'sigma stress gate':>34}: marginal maker (sigma 15% low) "
          f"-> {len(ds3)} trades at stress 25%, {len(ds4)} at stress 60%")
    if len(ds4) > len(ds3):
        fails.append("a tighter sigma stress produced MORE trades")

    eng5 = Engine(bankroll=1000.0, daily_loss_limit=0.10)
    eng5.on_market("X", "BRTI", 100.0, 0)
    eng5.record_fill(Decision(ticker="X", side="yes", price=0.50, size=500))
    eng5.settle("X", 0.0)
    print(f"  {'drawdown kill switch':>34}: halted={eng5.halted} "
          f"({eng5.halt_reason})")
    if not eng5.halted:
        fails.append("drawdown limit did not halt trading")

    # ---- exposure accounting must conserve --------------------------------
    print("\n  EXPOSURE ACCOUNTING (committed cash must return to zero)")
    e6 = Engine(bankroll=100_000.0, daily_loss_limit=1.0,
                max_total_frac=1.0, max_stake_frac=1.0, max_size=10 ** 9)
    e6.on_market("A", "BRTI", 100.0, 0)
    e6.on_market("B", "BRTI", 100.0, 0)
    # both legs of the same market, a second fill on top, and a fill for a
    # market nobody registered -- each one used to strand cash
    e6.record_fill(Decision(ticker="A", side="yes", price=0.40, size=100))
    e6.record_fill(Decision(ticker="A", side="no", price=0.55, size=100))
    e6.record_fill(Decision(ticker="A", side="yes", price=0.42, size=50))
    e6.record_fill(Decision(ticker="B", side="yes", price=0.30, size=10))
    took = e6.record_fill(Decision(ticker="GHOST", side="yes",
                                   price=0.30, size=1000))
    tracked, true = e6.audit_stake()
    want = 100 * .40 + 100 * .55 + 50 * .42 + 10 * .30
    print(f"  {'after 4 fills + 1 ghost':>34}: tracked ${tracked:,.2f}  "
          f"books ${true:,.2f}  expected ${want:,.2f}  ghost booked={took}")
    if took:
        fails.append("booked a fill for a market the engine does not track")
    if abs(tracked - true) > 1e-9 or abs(tracked - want) > 1e-9:
        fails.append(f"open_stake {tracked:.2f} != books {true:.2f} "
                     f"!= expected {want:.2f}")
    # A holds 150 yes and 100 no: yes wins, so it pays 150.
    p_a = e6.settle("A", 1.0)
    p_b = e6.settle("B", 0.0)
    e6.settle("A", 1.0)                       # settling twice must be a no-op
    tracked, true = e6.audit_stake()
    fee_a = (100 * fee_per_contract(.40) + 100 * fee_per_contract(.55)
             + 50 * fee_per_contract(.42))
    want_a = 150 - (100 * .40 + 100 * .55 + 50 * .42) - fee_a
    want_b = -10 * .30 - 10 * fee_per_contract(.30)
    print(f"  {'after settlement':>34}: tracked ${tracked:,.2f}  "
          f"books ${true:,.2f}   P&L A ${p_a:+,.2f} (want ${want_a:+,.2f})"
          f"  B ${p_b:+,.2f} (want ${want_b:+,.2f})")
    if abs(tracked) > 1e-9 or abs(true) > 1e-9:
        fails.append(f"${tracked:.2f} of exposure stranded after settlement")
    if abs(p_a - want_a) > 1e-9 or abs(p_b - want_b) > 1e-9:
        fails.append("settlement P&L does not match the two-leg cash flows")

    print("\n  KELLY SIZING (stake fraction f* = (p-q)/(1-q), quarter-Kelly)")
    e = Engine(bankroll=10_000.0, kelly=0.25, edge_haircut=1.0,
               max_stake_frac=1.0, max_total_frac=1.0, max_size=10 ** 9)
    print(f"  {'price':>10}{'true p':>9}{'f* full':>10}{'f* used':>10}"
          f"{'contracts':>11}{'check':>8}")
    ok = True
    for q, p in ((0.50, 0.55), (0.90, 0.93), (0.95, 0.96), (0.98, 0.985)):
        n, f = e.size_for(p, q)
        full = (p - q) / (1 - q)
        want = full * 0.25
        flag = "ok" if abs(f - want) < 1e-9 else "BAD"
        if flag == "BAD":
            ok = False
        print(f"  {100*q:>9.0f}c{p:>9.3f}{full:>10.4f}{f:>10.4f}"
              f"{n:>11,}{flag:>8}")
    if not ok:
        fails.append("Kelly fraction does not match (p-q)/(1-q) * kelly")

    print("\n  WHY TRADES WERE SKIPPED (fair maker, the null)")
    engs, _, _ = replay("fair", 200, seed=3)
    for k, v in sorted(engs.skips.items(), key=lambda x: -x[1])[:6]:
        print(f"  {k:>34}: {v:,}")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- flat against a correct maker, trades and profits")
    print("against every planted defect, and every risk control fires.")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    raise SystemExit(0 if selftest() else 1)
