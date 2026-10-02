#!/usr/bin/env python3
"""fc_variants.py -- loss-cutting VARIANTS of the clean-room forecaster, as a subclass of bettor_paper's Engine.

Operator 2026-09-29: "start working on methods that keep its great earning potential but minimizes losses and test
them on the side as a paper ... You can try as many versions as you want."

VEngine(params) is bettor_paper.Engine with the forecaster rule reimplemented line for line (same model, same tables,
same take()/resolve_pending() plumbing) plus optional gates. With params == {} it must make exactly the decisions the
paper forecaster makes; the self-test drives both through the same planted worlds and compares every fill.

Gates (each off by default):
  r_max        only trade with at most this many prints to come (paper 30)
  min_price    / max_price   price band of the side bought (paper 0.75 / 0.985)
  min_edge     p_side - q - fee (paper 0.02)
  min_p        p_side floor
  one_side     never buy the second side of a market (the paper's only 09-28 loss bought both)
  survive_s    seconds the offer must still be displayed at the same price (paper 1.0)
  max_age      skip an offer that has been the best ask for more than this many seconds (stale offers)
  min_age      skip an offer that became the best ask less than this many seconds ago (fresh offers)
  stable_k/stable_p   p_side >= stable_p on each of the last stable_k decisions (no recent flip)
  no_toward    skip if |index - threshold| shrank over the last no_toward seconds (index heading for the strike)
  flow_against skip if, in the last 2 s, takers bought the OTHER side more than ours (needs on_trade)
  crash_gap    at the 1-s check, skip the real fill if the best ask on our side is more than this under the order
               price (logged taker_miss why=crash). The paper copy of forecaster_live's v-crash-guard (CRASH_GAP),
               tested on the same book at the same instant. One known difference: a refused live trigger still uses
               up the live paper engine's per-side cap, here a skipped one does not -- live carries the refused paper
               count into its next order on that side, so the two land close, not identical.
Every forecaster fill carries the features at its decision (feat_*), so a replay can also price a gate offline.
"""
import math
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bettor_paper as B                        # noqa: E402

DEFAULTS = {"r_max": B.F_R_MAX, "min_price": B.F_MIN_PRICE, "max_price": B.F_MAX_PRICE, "min_edge": B.F_MIN_EDGE,
            "min_p": 0.0, "one_side": False, "survive_s": B.SURVIVE_S, "max_age": None, "min_age": None,
            "stable_k": 0, "stable_p": 0.9, "no_toward": 0, "flow_against": False,
            "quiet_s": None, "race_x": None, "race_p": 0.96, "hedge_p": None, "quiet_mult": None, "crash_gap": None}

VARIANTS = {
    "base": {},
    "one_side": {"one_side": True},
    "edge3": {"min_edge": 0.03},
    "edge4": {"min_edge": 0.04},
    "floor80": {"min_price": 0.80},
    "floor85": {"min_price": 0.85},
    "p95": {"min_p": 0.95},
    "p98": {"min_p": 0.98},
    "r20": {"r_max": 20},
    "r15": {"r_max": 15},
    "survive2": {"survive_s": 2.0},
    "age_max5": {"max_age": 5},
    "age_max10": {"max_age": 10},
    "age_min1": {"min_age": 1},
    "stable3": {"stable_k": 3, "stable_p": 0.9},
    "no_toward5": {"no_toward": 5},
    "flow_ok": {"flow_against": True},
    "quiet12": {"quiet_s": 1.2},
    "race2": {"race_x": 2.0, "race_p": 0.96},
    "race05_98": {"race_x": 0.5, "race_p": 0.98},
    "hedge40": {"hedge_p": 0.40},
    "hedge20": {"hedge_p": 0.20},
    "quiet12_race2": {"quiet_s": 1.2, "race_x": 2.0, "race_p": 0.96},
    "race05_98_hedge40": {"race_x": 0.5, "race_p": 0.98, "hedge_p": 0.40},
    "race1_98": {"race_x": 1.0, "race_p": 0.98},
    "race05_99": {"race_x": 0.5, "race_p": 0.99},
    "hedge50": {"hedge_p": 0.50},
    "stable2": {"stable_k": 2, "stable_p": 0.9},
    "stable3_p85": {"stable_k": 3, "stable_p": 0.85},
    "stable3_hedge40": {"stable_k": 3, "stable_p": 0.9, "hedge_p": 0.40},
    "stable3_race05_98_hedge40": {"stable_k": 3, "stable_p": 0.9, "race_x": 0.5, "race_p": 0.98, "hedge_p": 0.40},
    "stable2_race05_98_hedge40": {"stable_k": 2, "stable_p": 0.9, "race_x": 0.5, "race_p": 0.98, "hedge_p": 0.40},
    "quiet2x": {"quiet_mult": 2.0},
    "race05_98_quiet2x": {"race_x": 0.5, "race_p": 0.98, "quiet_mult": 2.0},
    # 2026-10-02: the live crash guard on paper (operator: "Should we add a crash guard to the paper ... Or maybe a
    # variation"). race1_98_crash10 is the rule forecaster_live runs (--variant race1_98 --crash-gap 0.10).
    "crash10": {"crash_gap": 0.10},
    "race1_98_crash05": {"race_x": 1.0, "race_p": 0.98, "crash_gap": 0.05},
    "race1_98_crash10": {"race_x": 1.0, "race_p": 0.98, "crash_gap": 0.10},
    "race1_98_crash15": {"race_x": 1.0, "race_p": 0.98, "crash_gap": 0.15},
    # 2026-10-02 (live record, our own fills): first entries with 30+ s left lost 5 of 14 markets (-$12.73);
    # every later entry lost 4 of 40 (+$16.27). Paper test of skipping the first seconds, on top of the live rule.
    "race1_98_crash10_r28": {"race_x": 1.0, "race_p": 0.98, "crash_gap": 0.10, "r_max": 28},
    "race1_98_crash10_r25": {"race_x": 1.0, "race_p": 0.98, "crash_gap": 0.10, "r_max": 25},
}


class VEngine(B.Engine):
    def __init__(self, log, now_fn, tables, params=None, name="base"):
        super().__init__(log, now_fn, tables, ["forecaster"])
        self.P = dict(DEFAULTS)
        self.P.update(params or {})
        self.name = name
        self.phist = {}                           # ticker -> deque of p (yes) per decision
        self.best = {}                            # (ticker, side) -> (best ask price str, since t)
        self.flow = {}                            # ticker -> deque (ts_s, taker_side, count)

    # --- memory: per-ticker state is dropped once a market's close group is finished (09-29: the side-by-side
    # paper bot reached 592 MB because flow/phist/best were never pruned -- ~850 markets a day x 14 engines) ---
    def finish_group(self, m):
        super().finish_group(m)
        live = set(self.markets)
        for t in [t for t in self.flow if t not in live]:
            del self.flow[t]
        for t in [t for t in self.phist if t not in live]:
            del self.phist[t]
        for k in [k for k in self.best if k[0] not in live]:
            self.best.pop(k, None)

    # --- offer age: when did the current best ask on each side become the best ---
    def _mark_best(self, ticker):
        b = self.books.get(ticker)
        if b is None:
            return
        now = self.now()
        for side in ("yes", "no"):
            lad = b.no if side == "yes" else b.yes
            p = (1 - max(lad)) if lad else None
            key = (ticker, side)
            ps = None if p is None else str(p)
            old = self.best.get(key)
            if old is None or old[0] != ps:
                self.best[key] = (ps, now)

    def on_snapshot(self, ticker, msg, seq, sid=None):
        super().on_snapshot(ticker, msg, seq, sid)
        self._mark_best(ticker)

    def on_delta(self, ticker, msg, seq, sid=None):
        super().on_delta(ticker, msg, seq, sid)
        self._mark_best(ticker)

    def on_trade(self, ticker, msg):
        super().on_trade(ticker, msg)
        if ticker in self.markets:
            self.flow.setdefault(ticker, deque(maxlen=512)).append(
                (msg["ts_ms"] / 1000.0, msg["taker_side"], float(msg["count_fp"])))

    def age_of(self, ticker, side, q):
        """Seconds the best ask on `side` has stood at its current price, if q is that price; else None."""
        x = self.best.get((ticker, side))
        if x is None or x[0] is None:
            return None
        if abs(float(x[0]) - q) > 1e-9:
            return None
        return self.now() - x[1]

    def flow2(self, ticker, side, now):
        mine = other = 0.0
        for ts, tk, c in self.flow.get(ticker, ()):
            if now - 2.0 <= ts <= now:
                if tk == side:
                    mine += c
                else:
                    other += c
        return mine, other

    # --- the 1-s survival check, with the variant's survive_s ---
    def resolve_pending(self, m, now):
        if not m.pending:
            return
        keep = []
        for p in m.pending:
            due = p["t_dec"] + self.P["survive_s"]
            if now < due:
                keep.append(p)
                continue
            q = float(p["price"])
            self.late_max = max(getattr(self, "late_max", 0.0), now - due)
            self.book_spend(m, p["strat"], "real", p["side"], q, -p["want"])
            b = self.books.get(m.ticker)
            why = None
            crash_ask = None
            if due >= m.close_s:
                why, k, still = "closed", 0, None
            elif b is None or not b.synced:
                why, k, still = "book_unsynced", 0, None
            else:
                still = b.ask_size_at(p["side"], p["price"])
                k = math.floor(min(p["want"], p["displayed"], still - m.taken.get(p["key"], 0.0)) + 1e-9)
                if k < 1:
                    why, k = "gone", 0
                elif self.P["crash_gap"] is not None and not p["extra"].get("hedge"):
                    # forecaster_live's v-crash-guard: the offer is collapsing if the best ask on our side is already
                    # more than crash_gap under the price we are about to pay. Never applied to a hedge (operator
                    # rule 09-19: a gate must never block a hedge) -- no crash variant has hedge_p today.
                    bp, _ = b.best_ask(p["side"])
                    if bp is not None and float(bp) < q - self.P["crash_gap"] - 1e-9:
                        why, k, crash_ask = "crash", 0, round(float(bp), 4)
            if k >= 1:
                m.taken[p["key"]] = m.taken.get(p["key"], 0.0) + k
                self.book_spend(m, p["strat"], "real", p["side"], q, k)
                self.add_fill(m, p["strat"], "real", p["side"], q, k, B.taker_fee(k, q), kind="take", rel=p["rel"],
                              displayed=p["displayed"], still_1s=still, want=p["want"], **p["extra"])
            else:
                self.log.write("taker_miss", strat=p["strat"], ticker=m.ticker, side=p["side"], price=str(p["price"]),
                               want=p["want"], rel=p["rel"], why=why, still_1s=still,
                               **({"best_ask": crash_ask} if why == "crash" else {}))
        m.pending = keep

    # --- insurance: when the side held falls below hedge_p, buy the other side up to the contracts held ---
    def hedge(self, m, p, b, now, rel):
        n = 0
        for held_side in ("yes", "no"):
            other = "no" if held_side == "yes" else "yes"
            ph = p if held_side == "yes" else 1.0 - p
            if ph >= self.P["hedge_p"]:
                continue

            def want(fm, q, held_side=held_side, other=other):
                if q > self.P["max_price"] or q >= 1.0:
                    return None
                return (m.side_n.get(("forecaster", fm, held_side), 0.0)
                        - m.side_n.get(("forecaster", fm, other), 0.0))
            if max(want(fm, 0.5) for fm in B.FILLS) < 1:
                continue
            n += self.take(m, "forecaster", other, b, now, rel, want,
                           {"p_side": round(1.0 - ph, 6), "hedge": True, "feat_p": round(1.0 - ph, 6), "feat_r": -rel - 1})
        return n

    # --- the forecaster, as bettor_paper.Engine.forecaster, plus gates and features ---
    def forecaster(self, m, rel, v, proj, r, exact_yes, b, now):
        P = self.P
        if r > P["r_max"]:
            return {"why": "r"}
        t = rel
        if exact_yes is not None:
            p = 1.0 if exact_yes else 0.0
        else:
            s = self.tb.f_sig(m.coin, r, self.f_local_sigma(m.index_id, m.close_s + t))
            if s is None:
                return {"why": "no_sigma"}
            sd = v * s * math.sqrt(B.s_coef(t)) / 60.0
            p = (1.0 if proj >= m.thr_f else 0.0) if sd <= 0 else 1.0 - B.phi((m.thr_f - proj) / sd)
        p = self.tb.f_calibrate(p, r)
        h = self.phist.setdefault(m.ticker, deque(maxlen=16))
        h.append(p)
        out = {"p": round(p, 6), "r": r, "n": 0}
        if b is None:
            out["why"] = "book"
            return out
        if P["hedge_p"] is not None:
            out["n"] += self.hedge(m, p, b, now, rel)
        d = self.prints.get(m.index_id, {})
        stamp = m.close_s + rel
        gap_now = abs(v - m.thr_f)
        back = [d[stamp - k][0] for k in (5,) if (stamp - k) in d]
        toward5 = (gap_now - abs(back[0] - m.thr_f)) / max(gap_now, 1e-12) if back else None
        for side in ("yes", "no"):
            ps = p if side == "yes" else 1.0 - p
            other = "no" if side == "yes" else "yes"
            if ps < P["min_p"]:
                continue
            lad0 = b.no if side == "yes" else b.yes
            if not lad0:
                continue
            q0 = float(1 - max(lad0))
            if q0 > P["max_price"] or (q0 >= P["min_price"] and ps - q0 - B.fee1(q0) < P["min_edge"]):
                continue
            hist_side = [x if side == "yes" else 1.0 - x for x in h]
            if P["stable_k"] and (len(hist_side) < P["stable_k"]
                                  or min(hist_side[-P["stable_k"]:]) < P["stable_p"]):
                continue
            if P["no_toward"]:
                bk = (stamp - P["no_toward"]) in d and d[stamp - P["no_toward"]][0]
                if bk and gap_now < abs(bk - m.thr_f) - 1e-12:
                    continue
            mine, oth = self.flow2(m.ticker, side, now)
            if P["flow_against"] and oth > mine:
                continue
            if P["quiet_s"] is not None:
                lt0 = m.recent_trades[-1] if m.recent_trades else None
                if lt0 is None or now - lt0[0] > P["quiet_s"]:
                    continue
            if P["race_x"] is not None and toward5 is not None and toward5 < -P["race_x"] and ps < P["race_p"]:
                continue
            feat = {"feat_p": round(ps, 6), "feat_r": r, "feat_toward5": None if toward5 is None else round(toward5, 4),
                    "feat_flow_mine": mine, "feat_flow_other": oth,
                    "feat_min3": round(min(hist_side[-3:]), 6), "feat_min5": round(min(hist_side[-5:]), 6),
                    "feat_other_held": m.side_n.get(("forecaster", "real", other), 0.0)}

            def want(fm, q, ps=ps, side=side, other=other):
                if q > P["max_price"] or q >= 1.0:
                    return None
                if q < P["min_price"]:
                    return 0
                if ps - q - B.fee1(q) < P["min_edge"]:
                    return 0
                if P["one_side"] and m.side_n.get(("forecaster", fm, other), 0.0) > 0:
                    return 0
                if P["max_age"] is not None or P["min_age"] is not None:
                    age = self.age_of(m.ticker, side, q)
                    if P["max_age"] is not None and age is not None and age > P["max_age"]:
                        return 0
                    if P["min_age"] is not None and (age is None or age < P["min_age"]):
                        return 0
                cap = B.F_MAX_SIDE
                if P["quiet_mult"] and not any(t >= m.close_s - 45 for t, _ in m.recent_trades):
                    cap = B.F_MAX_SIDE * P["quiet_mult"]      # no trade in this market since close-45 s
                return min(cap - m.side_n.get(("forecaster", fm, side), 0.0),
                           B.F_MAX_CLOSE - self.close_spent.get(("forecaster", fm, m.close_s), 0.0))

            best_p, disp = b.best_ask(side)
            age = self.age_of(m.ticker, side, float(best_p)) if best_p is not None else None
            feat["feat_age"] = None if age is None else round(age, 2)
            feat["feat_edge_best"] = None if best_p is None else round(ps - float(best_p) - B.fee1(float(best_p)), 5)
            lad = b.yes if side == "yes" else b.no
            bid = float(max(lad)) if lad else None
            feat["feat_bid"] = bid
            feat["feat_spread"] = None if (bid is None or best_p is None) else round(float(best_p) - bid, 4)
            feat["feat_disp"] = disp
            lt = m.recent_trades[-1] if m.recent_trades else None
            feat["feat_last_px"] = None if lt is None else round(lt[1] if side == "yes" else 1.0 - lt[1], 4)
            feat["feat_last_age"] = None if lt is None else round(now - lt[0], 2)
            feat["feat_vol5"] = sum(c for ts, _, c in self.flow.get(m.ticker, ()) if now - 5.0 <= ts <= now)
            loc = self.f_local_sigma(m.index_id, stamp)
            g = self.tb.f_sigma.get(m.coin)
            feat["feat_sig_ratio"] = None if (loc is None or not g) else round(loc / g, 3)
            out["n"] += self.take(m, "forecaster", side, b, now, rel, want, dict(p_side=round(ps, 6), **feat))
        return out


def selftest():
    """VEngine({}) must reproduce the paper forecaster fill for fill; each gate must remove what it targets."""
    from decimal import Decimal
    fails = []
    ck = lambda ok, msg: None if ok else fails.append(msg)
    tb = B.Tables()
    C = 1_000_000

    def world(eng_fn, book, deltas=(), vals=("101.00", "101.01"), rels=range(-60, 0), trades=()):
        clock = [0.0]
        sink = []
        eng = eng_fn(B.Logger(None, sink), lambda: clock[0])
        clock[0] = C - 200
        eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
        for s in range(C - 240, C + 1):
            eng.on_print("BRTI", s * 1000, vals[s % 2] if isinstance(vals, tuple) else vals(s), s + 0.1)
        eng.on_snapshot("BTC-T", book, 1)
        for rel in rels:
            clock[0] = C + rel + 0.2
            for (at, dl) in deltas:
                if at == rel:
                    eng.on_delta("BTC-T", dl, 2 + rel + 100)
            for (at, tr) in trades:
                if at == rel:
                    eng.on_trade("BTC-T", tr)
            eng.tick()
        clock[0] = C + 5
        eng.tick()
        eng.on_result("BTC-T", "yes", "101.00", clock[0])
        return [(r["fill"], r["side"], r["price"], r["size"]) for r in sink if r["ev"] == "fill" and r["strat"] == "forecaster"], sink

    book = {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}
    dl = [(-30, {"side": "no", "price_dollars": "0.2000", "delta_fp": "-30.00"})]
    paper = lambda lg, nf: B.Engine(lg, nf, tb, ["forecaster"])
    base = lambda lg, nf: VEngine(lg, nf, tb, {})
    fp, _ = world(paper, book, dl)
    fv, sv = world(base, book, dl)
    ck(fp == fv and len(fp) >= 2, "VEngine({}) == paper forecaster, fill for fill (%s vs %s)" % (fp, fv))
    ck(any(r["ev"] == "fill" and r.get("feat_p") is not None and r.get("feat_age") is not None for r in sv),
       "fills carry decision features")
    # gates
    f, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"min_price": 0.85}), book, dl)
    ck(f == [], "floor 85c removes the 80c buys")
    f, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"r_max": 20}), book, dl)
    ck(f and all(True for _ in f), "r_max 20 still trades later (book stays)")
    f2, s2 = world(lambda lg, nf: VEngine(lg, nf, tb, {"r_max": 20}), book, dl)
    ck(all(r["rel"] >= -21 for r in s2 if r["ev"] == "fill"), "r_max 20: no fill before 20 prints remain")
    f, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"max_age": 5}), book, dl)
    ck(f == [], "max_age 5: an ask standing since before the window (>5 s) is refused")
    f, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"survive_s": 2.0}), book,
                 dl + [(-29, {"side": "no", "price_dollars": "0.2000", "delta_fp": "-20.00"})])
    ck([x for x in f if x[0] == "real"] == [], "survive_s 2: gone within 2 s -> no real fill")
    # one_side: planted flip -- YES favoured early, then NO; both sides offered at 80c
    flip = lambda s: "101.00" if s < C - 20 else "95.00"
    book2 = {"no_dollars_fp": [["0.2000", "100.00"]], "yes_dollars_fp": [["0.2000", "100.00"]]}
    fb, _ = world(base, book2, (), vals=flip)
    fo, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"one_side": True}), book2, (), vals=flip)
    ck({x[1] for x in fb if x[0] == "real"} == {"yes", "no"}, "planted flip: base buys both sides")
    ck({x[1] for x in fo if x[0] == "real"} == {"yes"}, "one_side: only the first side")
    # no_toward: index walking toward the strike
    walk = lambda s: "%.3f" % (101.0 - 0.01 * max(0, s - (C - 60)))
    fw, _ = world(base, book, dl, vals=walk)
    fn_, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"no_toward": 5}), book, dl, vals=walk)
    ck(fw and not fn_, "no_toward: base buys, the gate buys nothing while the index walks to the strike (%s vs %s)" % (fw, fn_))
    # flow_against: someone buying NO hard in the last 2 s
    tr = [(-31, {"ts_ms": (C - 31) * 1000 + 100, "yes_price_dollars": "0.2000", "count_fp": "500.00", "taker_side": "no",
                 "trade_id": "x"})]
    ff, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"flow_against": True}), book, dl, trades=tr)
    ck(not any(x[3] == 50 and x[0] == "opt" for x in ff), "flow_against: no buy at rel -31 against 500 NO bought")
    # quiet: no trade at all -> nothing; a trade 0.5 s before the rel -31 decision -> the rel -31 buy happens
    fq, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"quiet_s": 1.2}), book, dl)
    ck(fq == [], "quiet 1.2: no trade seen -> no buy")
    trq = [(-31, {"ts_ms": (C - 31) * 1000 - 300, "yes_price_dollars": "0.8000", "count_fp": "5.00", "taker_side": "yes",
                  "trade_id": "q"})]
    fq2, sq2 = world(lambda lg, nf: VEngine(lg, nf, tb, {"quiet_s": 1.2}), book, dl, trades=trq)
    ck(any(r["ev"] == "fill" and r["rel"] == -31 for r in sq2), "quiet 1.2: a trade 0.5 s earlier -> the rel -31 buy")
    # race: index falls 1.0 toward the strike in the 5 s before rel -31, then stops
    race = lambda s: "101.00" if s <= C - 36 else ("%.2f" % (101.0 - 0.18 * (s - (C - 36))) if s <= C - 31 else "100.10")
    fr0, sr0 = world(base, book, dl, vals=race)
    fr1, sr1 = world(lambda lg, nf: VEngine(lg, nf, tb, {"race_x": 2.0, "race_p": 1.01}), book, dl, vals=race)
    ck(any(r["ev"] == "fill" and r["rel"] == -31 for r in sr0), "race world: base buys at rel -31")
    ck(not any(r["ev"] == "fill" and -31 <= r["rel"] <= -28 for r in sr1) and any(r["ev"] == "fill" for r in sr1),
       "race gate: no buy while the 5-s gap shrink is > 2x (rel -31..-28), buys once it eases")
    # hedge: YES bought, then a hard flip; NO offered at 98.5c (no edge for the plain rule) -> only the hedge buys NO
    book3 = {"no_dollars_fp": [["0.2000", "100.00"]], "yes_dollars_fp": [["0.0150", "500.00"]]}
    fh0, _ = world(base, book3, (), vals=flip)
    fh1, sh1 = world(lambda lg, nf: VEngine(lg, nf, tb, {"hedge_p": 0.40}), book3, (), vals=flip)
    ck({x[1] for x in fh0 if x[0] == "real"} == {"yes"}, "hedge world: base holds YES only")
    yes_n = sum(x[3] for x in fh1 if x[0] == "real" and x[1] == "yes")
    no_n = sum(x[3] for x in fh1 if x[0] == "real" and x[1] == "no")
    ck(yes_n > 0 and no_n == yes_n and all(r.get("hedge") for r in sh1 if r["ev"] == "fill" and r["side"] == "no"),
       "hedge 0.40: buys NO equal to the YES held (%s vs %s)" % (no_n, yes_n))
    # quiet_mult: no trade since close-45 s -> per-side cap 200; one trade at close-40 -> 100
    bookq = {"no_dollars_fp": [["0.2000", "500.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}
    fqq, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"quiet_mult": 2.0}), bookq, ())
    ck(sum(x[3] for x in fqq if x[0] == "real") == 200, "quiet_mult 2: quiet market buys 200 (%s)" % fqq)
    trn = [(-40, {"ts_ms": (C - 40) * 1000, "yes_price_dollars": "0.8000", "count_fp": "1.00", "taker_side": "yes", "trade_id": "n"})]
    fqn, _ = world(lambda lg, nf: VEngine(lg, nf, tb, {"quiet_mult": 2.0}), bookq, (), trades=trn, rels=range(-60, 0))
    ck(sum(x[3] for x in fqn if x[0] == "real") == 100, "quiet_mult 2: a trade at close-40 keeps the cap at 100 (%s)" % fqn)
    # crash_gap (forecaster_live's v-crash-guard on paper): just before the first 1-s check (rel -30) a new offer
    # appears 15c under our 80c price (YES ask 65c = a NO bid at 35c; below the 75c floor, so nobody buys it)
    crash = [(-30, {"side": "no", "price_dollars": "0.3500", "delta_fp": "5.00"})]
    v_ = lambda prm: (lambda lg, nf: VEngine(lg, nf, tb, prm))
    fcb, scb = world(base, book, crash)
    fcc, scc = world(v_({"crash_gap": 0.10}), book, crash)
    ck(any(x[0] == "real" and abs(x[2] - 0.80) < 1e-9 for x in fcb), "crash world: base books the 80c real fill (%s)" % fcb)
    ck(fcc and not any(x[0] == "real" for x in fcc),
       "crash10: best ask 15c under the 80c price at the check -> no real fill (%s)" % fcc)
    ck(any(r["ev"] == "taker_miss" and r["why"] == "crash" and r.get("best_ask") == 0.65 for r in scc),
       "crash10: the skip is logged taker_miss why=crash with the best ask seen")
    ck([x for x in fcc if x[0] == "opt"] == [x for x in fcb if x[0] == "opt"], "crash10 leaves the opt fills alone")
    fcr, _ = world(v_(VARIANTS["race1_98_crash10"]), book, crash)
    fr98, _ = world(v_(VARIANTS["race1_98"]), book, crash)
    ck(fcr == fcc and fr98 == fcb, "race1_98_crash10 / race1_98 in the crash world: = crash10 / = base (no race planted)")
    drop5 = [(-30, {"side": "no", "price_dollars": "0.2500", "delta_fp": "5.00"})]
    f5, s5 = world(v_({"crash_gap": 0.10}), book, drop5)
    ck(any(x[0] == "real" and abs(x[2] - 0.80) < 1e-9 for x in f5)
       and not any(r["ev"] == "taker_miss" and r["why"] == "crash" for r in s5),
       "crash10: a 5c drop (best ask 75c) is still filled at 80c (%s)" % f5)
    f15, _ = world(v_(VARIANTS["race1_98_crash15"]), book, crash)
    ck(any(x[0] == "real" and abs(x[2] - 0.80) < 1e-9 for x in f15), "crash15: a 15c drop is NOT more than 15c -> filled")
    # NULL: crash_gap None never refuses; crash10 on a book with no collapse changes nothing
    fn0, sn0 = world(v_({"crash_gap": None}), book, crash)
    ck(fn0 == fcb and not any(r.get("why") == "crash" for r in sn0), "crash_gap None: same fills as base, no why=crash")
    fst, sst = world(v_({"crash_gap": 0.10}), book, dl)
    ck(fst == fv and not any(r.get("why") == "crash" for r in sst), "crash10 on a steady book: same fills as base")
    ck(all(set(v) <= set(DEFAULTS) for v in VARIANTS.values()), "every variant names only known params")
    # the crash guard never blocks a hedge: hedge world, and at the hedge's 1-s check (rel -19) a NO ask appears at
    # 50c, 48.5c under the 98.5c hedge price -- the hedge still fills, equal to the YES held
    hcr = [(-19, {"side": "yes", "price_dollars": "0.5000", "delta_fp": "5.00"})]
    fhc, shc = world(v_({"hedge_p": 0.40, "crash_gap": 0.10}), book3, hcr, vals=flip)
    yes_c = sum(x[3] for x in fhc if x[0] == "real" and x[1] == "yes")
    ck(yes_c > 0 and any(r["ev"] == "fill" and r["fill"] == "real" and r.get("hedge") and abs(r["price"] - 0.985) < 1e-9
                         and r["size"] == yes_c for r in shc)
       and not any(r["ev"] == "taker_miss" and r.get("why") == "crash" and r["side"] == "no" and r["rel"] == -20
                   for r in shc),
       "crash guard never blocks a hedge (%s)" % fhc)
    # memory: after the close settles, the engine keeps no per-ticker trade flow, p history or best-ask clock
    clockM = [0.0]
    engM = VEngine(B.Logger(None, []), lambda: clockM[0], tb, {"flow_against": True})
    clockM[0] = C - 200
    engM.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
    for s_ in range(C - 240, C + 1):
        engM.on_print("BRTI", s_ * 1000, ("101.00", "101.01")[s_ % 2], s_ + 0.1)
    engM.on_snapshot("BTC-T", book, 1)
    engM.on_trade("BTC-T", {"ts_ms": (C - 40) * 1000, "yes_price_dollars": "0.8000", "count_fp": "1.00", "taker_side": "yes", "trade_id": "m"})
    for rel in range(-60, 0):
        clockM[0] = C + rel + 0.2
        engM.tick()
    ck(engM.flow and engM.phist and engM.best, "memory test world: state exists while the market is open")
    clockM[0] = C + 5
    engM.tick()
    engM.on_result("BTC-T", "yes", "101.00", clockM[0])
    ck(not engM.flow and not engM.phist and not engM.best and not engM.markets,
       "memory: settled markets leave no flow / p history / best-ask entries behind")
    # empty world
    fe, _ = world(base, {"no_dollars_fp": [], "yes_dollars_fp": []}, ())
    ck(fe == [], "no book: nothing")
    print("fc_variants self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
