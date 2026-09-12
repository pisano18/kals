#!/usr/bin/env python3
# VERSION: 2026-09-12-count1
"""pincount.py -- WHY WE TRADE NOTHING ON HALF THE CLOSES THE MODEL IS SURE OF.

THE QUESTION. `results/RESULTS_maker.md` measured that at the live gate an
acceptable offer existed on only 694 of 7,266 model-certain markets (9.6%) and
on 411 of 793 closes (51.8%). So on roughly HALF the closes where the model is
certain we trade nothing at all -- and not because our rules refuse. Every
PRICE lever has now been measured and killed (resting a bid: killed;
entry-time features: null; being pickier on discount or price: killed on the
per-close arithmetic, `results/SKIM.md`). COUNT is what is left, and COUNT has
three possible causes with three different fixes:

    liquidity  nobody is offering the winning side at any price
    price      an offer exists and is above PRICE_CEILING
    size       an offer exists at an acceptable price and is too small

This file separates them, on the REBUILT replay, and then prices the levers
that act on them (MIN_FILL_FRAC, PRICE_CEILING, TAU_MAX) in $ PER CLOSE --
the unit that has killed three ideas here, because a lever that trades more
closes for less money per close is a loss dressed as progress.

SCOPE, set 2026-09-12: the SIZE sweep belongs to `research/pinlevels.py`,
which does it over all 422 book hours with bootstrap intervals, and a
full-history sweep supersedes anything 7 days can say about SIZE. What lives
HERE is the decomposition -- whether size is even the binding constraint --
and MIN_FILL_FRAC, which is a different lever: it loosens the FLOOR while
leaving the maximum at SIZE, so it buys extra closes without giving up size
on the deep books. Cite `results/RESULTS_levels.md` for size.

WHAT IT REUSES AND WHAT IT ADDS. It reimplements no decision: `pinrun.fair`,
`pinrun.net_edge`, `pinrun.expected_value`, `pinrun.billed_fee` and pinrun's
own constants make every call, fed by `pinsim`'s certified event walk
(`pinsim.Walk`, `pinsim.load_hour`, `pinsim.book_view`, `pinsim.TapeIndex`).
It imports `pinrun`, exactly as `pinsim` does, and therefore imports `pintake`
transitively -- it never calls into it, and no code path here can send an
order. What it ADDS is the REASON: pinsim counts a skip once per (market,
reason) and never asks which reason was closest to a trade, so its tally
cannot be read as a decomposition. Here every market gets EXACTLY ONE reason
per close, the best rung it reached on the ladder below.

TWO PASSES, BECAUSE THE TAPE IS EXPENSIVE AND THE ARITHMETIC IS NOT.

  pass 1 (`--pass1`)  one iteration of each hour's event stream. For every
      tracked market and every second in tau [3, 60] it computes the model
      ONCE (fair is constant within a second: `Walk` feeds the index only at
      second boundaries) and then records the BOOK STATE on the model's side
      after every book event, deduplicated on consecutive equality. That is a
      few thousand rows per hour, written gzipped to a cell file. Memory is
      one hour at a time; the hour cache is evicted, as pinsim's run() does
      after three OOM kills on 2026-09-12.

  a third, cheap pass (`--gaps`) counts the collector's own `_seq_gap` flags
      over the same window by raw substring scan (2.3 s/hour against the 17 s
      a parsing pass costs), so the report quotes the count ITS window holds
      instead of a remembered rate.

  pass 2 (`--report`)  reads the cells and replays THE DECISION offline, in
      the tape's own event order, under every configuration. Because the cells
      hold the raw book state, a configuration change is arithmetic and not
      another tape pass -- which is what makes a 20-configuration sweep over 7
      days affordable at all.

WHAT PASS 2 ENFORCES, IN PINRUN'S OWN ORDER (research/pinrun.py ~2337-2548):

    MAX_PER_CLOSE -> MAX_PER_MARKET      the counting rails, before the book
    MAX_BOOK_AGE_MS, MAX_INDEX_AGE_S     staleness
    PIN                                  the gate (fixed at the live 0.995)
    an ask on our side, < $1             else `no_offer`
    take_n >= max(MIN_LEVEL, MIN_FILL_FRAC*SIZE)   else `too_shallow`
    net_edge >= EDGE_FLOOR               else `no_edge`
    discount <= DUMP_DISCOUNT            else `dumped`
    price < best_so_far - IMPROVE_BY     else `no_improve` (does NOT retire)
    price <= PRICE_CEILING               else `over_ceiling`
    expected_value >= EV_FLOOR           else `neg_ev`

THE LADDER, and why it is ordered this way. One reason per market per close,
and it is the CLOSEST the market ever came to a trade across every second in
the band -- because "there was no ask for 25 of the 28 seconds" is not the
reason we did not trade if on the other 3 there was one and it was too small.

    bought
    dumped / no_improve / market_cap / close_cap   we COULD have; we chose not
    over_ceiling / neg_ev / no_edge                PRICE
    too_shallow                                    SIZE
    no_offer                                       LIQUIDITY
    stale_book / stale_index                       our view of the book
    no_gate                                        the model never got there
    no_model                                       no sigma / no fair

WHAT THIS CANNOT SAY, and it is the same limit every replay here has: whether
the offer would have been OURS. Live we fill ~70% of the attempts we make, and
the 2026-09-10 house rule stands -- A LOSS RATE FOR US IS NEVER QUOTED FROM
THE TAPE. So every dollar figure below is computed two ways and both are
printed: `tape` (the settled outcome of each replayed fill -- valid as a
RANKING of levers, invalid as our P&L) and `ev` (pinrun.expected_value at the
price paid, which carries the project's own MEASURED_FLIP). Where the two
disagree the lever is not established.
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys
import tempfile
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                  # noqa: E402
import pindata                                                 # noqa: E402
import pinsim                                                  # noqa: E402
import tdist                                                   # noqa: E402
from pincross import cp_interval                              # noqa: E402

SCAN_TAU_MIN = 3
SCAN_TAU_MAX = 60          # widest band any configuration may ask for
CELLS = os.path.join(tempfile.gettempdir(), "pincount_cells")

# side codes in a cell row
S_NO, S_YES, S_UNDEC, S_NOMODEL = 0, 1, -1, -2

# the ladder, best rung first. `bought` is rung 0.
LADDER = ["bought", "dumped", "no_improve", "market_cap", "close_cap",
          "over_ceiling", "neg_ev", "no_edge", "too_shallow", "no_offer",
          "stale_book", "stale_index", "no_gate", "no_model"]
RANK = {r: i for i, r in enumerate(LADDER)}
# how the report groups the ladder into the three causes the question asks for
CAUSE = {"bought": "traded",
         "dumped": "our rules", "no_improve": "our rules",
         "market_cap": "our rules", "close_cap": "our rules",
         "over_ceiling": "PRICE", "neg_ev": "PRICE", "no_edge": "PRICE",
         "too_shallow": "SIZE",
         "no_offer": "LIQUIDITY",
         "stale_book": "our book", "stale_index": "our book",
         "no_gate": "no signal", "no_model": "no signal"}


# --------------------------------------------------------------- the config
class Cfg:
    """One configuration of the live gate. Everything else comes from pinrun."""

    __slots__ = ("name", "size", "ceiling", "tau_max", "min_fill_frac",
                 "ev_gate", "dump")

    def __init__(self, name, size=None, ceiling=None, tau_max=None,
                 min_fill_frac=None, ev_gate=True, dump=True):
        self.name = name
        self.size = float(pinrun.SIZE if size is None else size)
        self.ceiling = float(pinrun.PRICE_CEILING if ceiling is None
                             else ceiling)
        self.tau_max = int(pinrun.TAU_MAX if tau_max is None else tau_max)
        self.min_fill_frac = float(pinrun.MIN_FILL_FRAC
                                   if min_fill_frac is None else min_fill_frac)
        self.ev_gate = ev_gate
        self.dump = dump

    def floor(self):
        return max(pinrun.MIN_LEVEL, self.min_fill_frac * self.size)


# ------------------------------------------------------- the decision, offline
# THE RAILS ARE PINSIM'S, NOT A COPY. An earlier version of this file
# reimplemented MAX_PER_CLOSE / MAX_PER_MARKET / IMPROVE_BY locally, which is
# a fourth copy of a decision that has already diverged from live once.
# pinsim.close_slot_ok / close_slot_book are the certified implementations
# (commit 0b49a52) and are called directly; the self-test asserts the
# identity, so a later local re-implementation fails the gate.
rails = pinsim.close_slot_ok
book_slot = pinsim.close_slot_book


def simulate_close(rows, mk, cfg):
    """Replay ONE close's recorded book states under `cfg`.

    rows: the close's cell rows in the tape's own event order, each
          [ev, sec, tau, mi, fair, side, price, size, age_ms, iage, opp]
    mk:   list of market dicts, indexed by `mi`
    Returns (buys, reason_by_market) where a buy is a dict and a reason is one
    string per market index that appeared in the band.

    THE ONLY THING THIS DOES NOT REPLAY is the market's book between recorded
    states: a state is recorded whenever (price, size) changes on our side, so
    nothing that could have been bought is missing, and a state that persists
    is not re-offered. A refusal never retires a market -- live re-checks it on
    the next tick -- and a FILL does, because MAX_PER_MARKET is 1.
    """
    sv = (pinrun.SIZE, pinrun.PRICE_CEILING, pinrun.MIN_FILL_FRAC)
    pinrun.SIZE = cfg.size
    pinrun.PRICE_CEILING = cfg.ceiling
    pinrun.MIN_FILL_FRAC = cfg.min_fill_frac
    floor = cfg.floor()
    try:
        per_close = {}          # close -> pinrun's `fired` shape
        cs_key = None
        filled = set()
        best = {}           # mi -> (rank, reason)
        buys = []

        def note(mi, reason):
            r = RANK[reason]
            cur = best.get(mi)
            if cur is None or r < cur[0]:
                best[mi] = (r, reason)

        for row in rows:
            _, sec, tau, mi, fv, side, price, size, age, iage, _opp = row
            if not (pinrun.TAU_MIN <= tau <= cfg.tau_max):
                continue
            if side == S_NOMODEL:
                note(mi, "no_model")
                continue
            if side == S_UNDEC:
                note(mi, "no_gate")
                continue
            tk = mk[mi]["ticker"]
            if mi in filled:
                continue
            cs_key = mk[mi]["close"]
            sl = rails(per_close.get(cs_key), tk, None)
            if sl:
                note(mi, sl)
                continue
            if age is None or age > pinrun.MAX_BOOK_AGE_MS:
                note(mi, "stale_book")
                continue
            if iage is None or iage > pinrun.MAX_INDEX_AGE_S:
                note(mi, "stale_index")
                continue
            if price is None or price >= 1.0 or not size:
                note(mi, "no_offer")
                continue
            want = "yes" if side == S_YES else "no"
            take_n = min(cfg.size, float(size))
            if take_n < floor:
                note(mi, "too_shallow")
                continue
            if pinrun.net_edge(fv, price, want) < pinrun.EDGE_FLOOR:
                note(mi, "no_edge")
                continue
            conf = fv if want == "yes" else 1.0 - fv
            if cfg.dump and (conf - price) > pinrun.DUMP_DISCOUNT:
                note(mi, "dumped")
                continue
            sl = rails(per_close.get(cs_key), tk, price)
            if sl:                      # only `no_improve` can reach here
                note(mi, sl)
                continue                # NOT retired: live re-checks next tick
            if price > cfg.ceiling:
                note(mi, "over_ceiling")
                continue
            ev1 = pinrun.expected_value(price)
            if cfg.ev_gate and ev1 < pinrun.EV_FLOOR:
                note(mi, "neg_ev")
                continue
            won = (mk[mi]["result_yes"] == (want == "yes"))
            fee = pinrun.billed_fee(price, take_n)
            pnl = (take_n * (1.0 - price) if won else -take_n * price) - fee
            buys.append({"mi": mi, "tk": tk, "want": want, "price": price,
                         "n": take_n, "tau": tau, "sec": sec, "won": won,
                         "pnl": pnl, "ev": take_n * ev1, "depth": float(size),
                         "conf": conf, "series": mk[mi]["series"]})
            note(mi, "bought")
            filled.add(mi)
            book_slot(per_close, cs_key, tk, price)
        return buys, {mi: v[1] for mi, v in best.items()}
    finally:
        pinrun.SIZE, pinrun.PRICE_CEILING, pinrun.MIN_FILL_FRAC = sv


# ------------------------------------------------------------- pass 1, the tape
def scan_hour(stamp, mkall, say=print):
    """One iteration of one hour's event stream -> one cell dict.

    The model is computed ONCE per (market, second) because `pinsim.Walk` feeds
    the index only at second boundaries, so fair cannot change within a second.
    The BOOK is read at every event, which is the whole reason the rebuilt
    replay reproduces our losses and the old one did not.
    """
    hour = pinsim.load_hour(stamp, mkall)
    if not hour["ticks"]:
        return None
    idx = pinsim.TapeIndex(sorted(hour["ticks"]))
    pend = {k: list(v) for k, v in hour["ticks"].items()}
    wk = pinsim.Walk(mkall, idx, pend, per_event=True)
    mi_of = {}
    mkts = []
    rows = []
    fair_cache = {}          # (tk, sec) -> (side, fair)
    last = {}                # mi -> (sec, price, size, opp)
    ev = 0
    for kind, tk, sec, ts in wk.drive(hour["events"]):
        if kind == 0:
            continue
        r = mkall.get(tk)
        if r is None:
            continue
        cs = int(float(r["close"]))
        tau = cs - sec
        if not (SCAN_TAU_MIN <= tau <= SCAN_TAU_MAX):
            continue
        iid = pindata.SERIES_TO_INDEX[r["series"]]
        if iid not in idx.ticks:
            continue
        mi = mi_of.get(tk)
        if mi is None:
            mi = mi_of[tk] = len(mkts)
            res = r["result"]
            yes = (str(res).lower() == "yes") if isinstance(res, str) \
                else float(res) >= 0.5
            mkts.append({"ticker": tk, "series": r["series"], "close": cs,
                         "result_yes": bool(yes),
                         "strike": float(r["strike"])})
        key = (mi, sec)
        got = fair_cache.get(key)
        if got is None:
            sg = idx.sigma(iid)
            f = None
            if sg is not None:
                f = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                                sg * pinrun.SIGMA_STRESS,
                                round_digits=pindata.ROUND_DIGITS.get(
                                    r["series"]))
            if f is None:
                side = S_NOMODEL
            elif f >= pinrun.PIN:
                side = S_YES
            elif f <= 1.0 - pinrun.PIN:
                side = S_NO
            else:
                side = S_UNDEC
            _, _spot, iage = idx.spot(iid)
            got = fair_cache[key] = (side, f, iage)
            if len(fair_cache) > 6000:
                fair_cache = {key: got}
        side, f, iage = got
        if side in (S_NOMODEL, S_UNDEC):
            # one row per (market, second) -- these carry no book state
            if last.get(mi) == (sec, None, None, None):
                continue
            last[mi] = (sec, None, None, None)
            ev += 1
            rows.append([ev, sec, tau, mi, 0.0, side,
                         None, 0.0, None, None, 0])
            continue
        b = pinsim.book_view(wk.books[tk], ts)
        want = "yes" if side == S_YES else "no"
        other = "no" if side == S_YES else "yes"
        price = b.get(f"{want}_ask")
        size = b.get(f"{want}_ask_size") or 0.0
        oa = b.get(f"{other}_ask")
        opp = 1 if (oa is not None and oa < 1.0) else 0
        if price is not None and price >= 1.0:
            price, size = None, 0.0
        sig = (sec, price, size, opp)
        if last.get(mi) == sig:
            continue
        last[mi] = sig
        ev += 1
        rows.append([ev, sec, tau, mi, round(f, 6), side,
                     (round(price, 4) if price is not None else None),
                     float(size), b["age_ms"],
                     (round(iage, 2) if iage is not None else None), opp])
    cell = {"stamp": stamp, "pin": pinrun.PIN, "markets": mkts, "rows": rows,
            "events": wk.events, "moments": wk.moments, "bad": wk.bad,
            "ts_back": wk.ts_back}
    pinsim._HOUR_CACHE.pop(stamp, None)
    return cell


def count_gaps(hours, end, cells, say=print):
    """THE COLLECTOR'S OWN `_seq_gap` FLAGS, for THIS window.

    kalshi_collector.py stamps `_seq_gap` on any frame whose `seq` is not
    prev+1. At that instant the book for that subscription is provably wrong,
    and the missing deltas could have belonged to any market, so every
    tracked book is suspect until its next snapshot. pinsim counts these
    (commit 2bb9c45) and measured ~11 an hour against ~2.6M deltas.

    This is a RAW SUBSTRING COUNT -- no JSON parsing -- because that is 2.3 s
    per hour against the 17 s a parsing pass costs, and the flag is a
    top-level key that appears on no other field. The number is written beside
    the cells so the report can quote the count its OWN window contains
    rather than a remembered rate.
    """
    out = {}
    t0 = time.time()
    stamps = pinsim.book_hours(hours, end)
    for i, stamp in enumerate(stamps):
        fp = os.path.join(pinsim.DATA, "orderbook_delta", f"{stamp}.jsonl.gz")
        n = tot = 0
        try:
            with gzip.open(fp, "rb") as fh:
                for line in fh:
                    tot += 1
                    if b'"_seq_gap"' in line:
                        n += 1
        except (OSError, EOFError, Exception):                 # noqa: BLE001
            pass
        out[stamp] = [n, tot]
        if (i + 1) % 24 == 0:
            say(f"    gaps {stamp}  {sum(v[0] for v in out.values()):,} flags "
                f"in {i + 1} hours ({(time.time()-t0)/(i+1):.1f}s/hour)",
                flush=True)
    os.makedirs(cells, exist_ok=True)
    with open(os.path.join(cells, "gaps.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    tf = sum(v[0] for v in out.values())
    td = sum(v[1] for v in out.values())
    say(f"  {tf:,} `_seq_gap` flags over {td:,} delta messages in "
        f"{len(out)} hours ({tf/max(len(out),1):.1f} per hour, "
        f"{100.0*tf/max(td,1):.5f}%)")
    return out


def cell_path(cells, stamp):
    return os.path.join(cells, f"{stamp}.json.gz")


def pass1(hours, end, cells, say=print, force=False):
    os.makedirs(cells, exist_ok=True)
    mkall = pinsim.load_markets()
    stamps = pinsim.book_hours(hours, end)
    ns = pinsim.newest_settlement(mkall)
    say(f"  {len(mkall):,} settled markets on file; newest settlement "
        f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ns))}")
    say(f"  {len(stamps)} book hours {stamps[0]} .. {stamps[-1]}; "
        f"gate PIN={pinrun.PIN} scan tau [{SCAN_TAU_MIN},{SCAN_TAU_MAX}]")
    t0 = time.time()
    for i, stamp in enumerate(stamps):
        fp = cell_path(cells, stamp)
        if os.path.exists(fp) and not force:
            say(f"    {stamp}  cached", flush=True)
            continue
        cell = scan_hour(stamp, mkall, say=say)
        if cell is None:
            say(f"    {stamp}  no index ticks -- skipped", flush=True)
            continue
        tmp = fp + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(cell, fh, separators=(",", ":"))
        os.replace(tmp, fp)
        el = time.time() - t0
        say(f"    {stamp}  {len(cell['markets'])} markets, "
            f"{len(cell['rows']):,} rows, {cell['events']:,} events "
            f"({el / (i + 1):.0f}s/hour)", flush=True)
    return stamps


def load_cells(cells, stamps=None):
    """Yield one hour's cell at a time. Never holds two."""
    fps = sorted(glob.glob(os.path.join(cells, "2026*.json.gz")))
    for fp in fps:
        stamp = os.path.basename(fp)[:11]
        if stamps is not None and stamp not in stamps:
            continue
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as fh:
                yield json.load(fh)
        except (OSError, EOFError, ValueError) as e:
            print(f"  *** cell {stamp} unreadable: {e}")


# --------------------------------------------------------------- the arithmetic
def by_close(cell):
    """Split one hour's rows into per-close (rows, markets) in event order."""
    out = defaultdict(list)
    for row in cell["rows"]:
        out[cell["markets"][row[3]]["close"]].append(row)
    return out


class Acc:
    """Per-configuration accumulator. Per CLOSE, because hard rule 4."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.pnl = defaultdict(float)      # close -> tape P&L
        self.ev = defaultdict(float)       # close -> EV P&L
        self.fills = defaultdict(int)
        self.px = []
        self.taus = []
        self.depths = []
        self.contracts = 0.0
        self.buys = []           # (close, tau, price, won, pnl, n) per fill
        self.lost = defaultdict(int)
        self.reasons = defaultdict(int)            # market-level
        self.by_close = {}                         # close -> {reason: markets}
        self.close_reason = {}                     # close -> best reason
        self.certain_closes = set()
        self.certain_markets = 0
        self.markets_seen = 0

    def add(self, cs, buys, reasons):
        if not reasons:
            return
        self.markets_seen += len(reasons)
        cert = [m for m, r in reasons.items() if r not in ("no_gate",
                                                           "no_model")]
        self.certain_markets += len(cert)
        if cert:
            self.certain_closes.add(cs)
        bc = self.by_close.setdefault(cs, defaultdict(int))
        for r in reasons.values():
            self.reasons[r] += 1
            bc[r] += 1
        bestr = min(reasons.values(), key=lambda r: RANK[r]) if reasons else None
        if bestr is not None:
            cur = self.close_reason.get(cs)
            if cur is None or RANK[bestr] < RANK[cur]:
                self.close_reason[cs] = bestr
        for b in buys:
            self.pnl[cs] += b["pnl"]
            self.ev[cs] += b["ev"]
            self.fills[cs] += 1
            self.px.append(b["price"])
            self.taus.append(b["tau"])
            self.depths.append(b["depth"])
            self.contracts += b["n"]
            self.buys.append((cs, b["tau"], b["price"], b["won"],
                              b["pnl"], b["n"]))
            if not b["won"]:
                self.lost[cs] += 1


def mean_sd(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(v)


def per_close_stats(acc, denom_closes):
    """$/close over a FIXED denominator, so configurations are comparable.

    EVERY field is restricted to `denom_closes`. A first version took `fills`,
    `contracts`, `mean_px` and `mean_tau` from the whole accumulator, so the
    train and holdout blocks reported the FULL-WINDOW fill count beside a
    subset P&L -- three identical 475s under `all`, `train` and `holdout`.
    Nothing printed used those fields, but they were in the published JSON,
    and a number that is wrong where nobody looks is still wrong.
    """
    keep = set(denom_closes)
    xs = [acc.pnl.get(c, 0.0) for c in denom_closes]
    es = [acc.ev.get(c, 0.0) for c in denom_closes]
    bs = [b for b in acc.buys if b[0] in keep]
    m, sd = mean_sd(xs)
    me, _ = mean_sd(es)
    n = len(denom_closes)
    se = sd / math.sqrt(n) if n else 0.0
    tc = tdist.crit(0.05, max(n - 1, 1))
    return {"closes_denom": n,
            "closes_traded": sum(1 for c in denom_closes if acc.fills.get(c)),
            "fills": len(bs),
            "contracts": sum(b[5] for b in bs),
            "pnl": sum(xs), "per_close": m, "sd": sd, "se": se,
            "t": (m / se if se else 0.0), "tcrit": tc,
            "ev_per_close": me, "ev_total": sum(es),
            "lost_closes": sum(1 for c in denom_closes if acc.lost.get(c)),
            "lost_fills": sum(1 for b in bs if not b[3]),
            "mean_px": mean_sd([b[2] for b in bs])[0],
            "mean_tau": mean_sd([b[1] for b in bs])[0]}


def paired_mde(a, b, denom_closes):
    """MDE on the DIFFERENCE in $/close between two configurations, paired on
    the close. Stated before the estimate, per CLAUDE.md."""
    d = [a.pnl.get(c, 0.0) - b.pnl.get(c, 0.0) for c in denom_closes]
    m, sd = mean_sd(d)
    n = len(d)
    se = sd / math.sqrt(n) if n else 0.0
    tc = tdist.crit(0.05, max(n - 1, 1))
    return {"diff": m, "se": se, "mde": tc * se, "t": (m / se if se else 0.0),
            "n": n}


def split_diff(a, base, denom_closes):
    """WHERE a lever's money comes from, which is the artefact check every
    COUNT lever needs. A lever sold as "more closes" that in fact earns its
    money by taking a SECOND fill on closes we already traded has not answered
    this question at all, and the three components below sum exactly to the
    paired difference.

      new     closes the lever trades and the base does not   -> COUNT
      lost    closes the base trades and the lever does not   -> a cost
      shared  closes both trade, so the change is per-close   -> not COUNT
    """
    newc = [c for c in denom_closes
            if a.fills.get(c) and not base.fills.get(c)]
    lostc = [c for c in denom_closes
             if base.fills.get(c) and not a.fills.get(c)]
    both = [c for c in denom_closes
            if a.fills.get(c) and base.fills.get(c)]
    return {"new_closes": len(newc),
            "pnl_new": sum(a.pnl.get(c, 0.0) for c in newc),
            "lost_closes": len(lostc),
            "pnl_lost": -sum(base.pnl.get(c, 0.0) for c in lostc),
            "shared_closes": len(both),
            "pnl_shared": sum(a.pnl.get(c, 0.0) - base.pnl.get(c, 0.0)
                              for c in both),
            "extra_fills_shared": sum(a.fills.get(c, 0) - base.fills.get(c, 0)
                                      for c in both)}


def days_positive(acc, denom_closes):
    d = defaultdict(float)
    for c in denom_closes:
        d[time.strftime("%Y-%m-%d", time.gmtime(c))] += acc.pnl.get(c, 0.0)
    return sum(1 for v in d.values() if v > 0), len(d)


# ------------------------------------------------------------------ self-test
def _row(ev, sec, tau, mi, fair, side, price, size, age=100, iage=0.2, opp=1):
    return [ev, sec, tau, mi, fair, side, price, size, age, iage, opp]


def _world(n_closes, price, size, *, absent_every=None, fair=1.0,
           markets_per_close=1, secs=(10, 9, 8)):
    """A world with one certain YES market per close, offered at `price` and
    `size`. On every `absent_every`-th close there is NO ask at all."""
    closes = {}
    mk = []
    for c in range(n_closes):
        cs = 100000 + 900 * c
        rows = []
        for m in range(markets_per_close):
            mi = len(mk)
            mk.append({"ticker": f"T{c}_{m}", "series": "KXBTC15M",
                       "close": cs, "result_yes": True, "strike": 1.0})
            gone = absent_every and (c % absent_every == 0)
            for k, s in enumerate(secs):
                rows.append(_row(len(rows) + 1, cs - s, s, mi, fair, S_YES,
                                 None if gone else price,
                                 0.0 if gone else size))
        closes[cs] = rows
    return closes, mk


def _run_world(closes, mk, cfg):
    acc = Acc(cfg)
    for cs, rows in closes.items():
        buys, reasons = simulate_close(rows, mk, cfg)
        acc.add(cs, buys, reasons)
    return acc


def selftest():
    print("SELF-TEST -- pincount")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- the ladder is the LIVE order, read out of pinrun's own source -----
    src = open(os.path.join(HERE, "pinrun.py"), encoding="utf-8").read()
    lo = src.index("AMENDMENT 6: buy what is THERE")
    seg = src[lo:lo + 4000]
    order = []
    for pat, name in (("take_n < max(MIN_LEVEL", "too_shallow"),
                      ("if e < EDGE_FLOOR", "no_edge"),
                      ("_disc > DUMP_DISCOUNT", "dumped"),
                      ("price >= prev[\"best\"] - IMPROVE_BY", "no_improve"),
                      ("price > PRICE_CEILING", "over_ceiling"),
                      ("if ev < EV_FLOOR", "neg_ev")):
        i = seg.find(pat)
        ck(i >= 0, f"pinrun still contains the `{name}` test")
        order.append((i, name))
    live_order = [n for _, n in sorted(order)]
    ck(live_order == ["too_shallow", "no_edge", "dumped", "no_improve",
                      "over_ceiling", "neg_ev"],
       f"and they are in the order this file applies them ({live_order})")
    mine = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = mine[mine.index("def simulate_close"):mine.index("def scan_hour")]
    # `no_improve` is raised by rails(), not by a literal note(), so each
    # test is located by the EXPRESSION that implements it.
    MARK = {"too_shallow": "if take_n < floor:",
            "no_edge": "pinrun.net_edge(fv, price, want)",
            "dumped": "pinrun.DUMP_DISCOUNT",
            "no_improve": "sl = rails(per_close.get(cs_key), tk, price)",
            "over_ceiling": "if price > cfg.ceiling:",
            "neg_ev": "cfg.ev_gate and ev1"}
    for nm, pat in MARK.items():
        ck(pat in body, f"simulate_close implements `{nm}` as `{pat}`")
    got = [n for _, n in sorted((body.index(MARK[n]), n) for n in live_order)]
    ck(got == live_order,
       f"simulate_close applies them in pinrun's order too ({got})")

    # ---- PLANTED LIQUIDITY: offers absent on a KNOWN fraction of closes ----
    for every, n in ((2, 40), (4, 40), (5, 30)):
        closes, mk = _world(n, 0.96, 500.0, absent_every=every)
        want_absent = sum(1 for c in range(n) if c % every == 0)
        acc = _run_world(closes, mk, Cfg("base", size=20))
        ck(acc.reasons["no_offer"] == want_absent
           and acc.reasons["bought"] == n - want_absent,
           f"a world with no ask on {want_absent} of {n} closes decomposes to "
           f"exactly {want_absent} `no_offer` and {n - want_absent} `bought` "
           f"(got {acc.reasons['no_offer']} / {acc.reasons['bought']})")
        st = per_close_stats(acc, sorted(closes))
        ck(st["closes_traded"] == n - want_absent,
           f"and {n - want_absent} closes traded")
        # the zero closes must be IN the denominator
        exp = (n - want_absent) * (20 * 0.04
                                   - pinrun.billed_fee(0.96, 20)) / n
        ck(abs(st["per_close"] - exp) < 1e-9,
           f"and $/close counts the untraded closes as zero "
           f"(${st['per_close']:.4f} == ${exp:.4f})")

    # ---- THE NULL: deep, cheap offers everywhere plant nothing ------------
    closes, mk = _world(50, 0.96, 500.0)
    acc = _run_world(closes, mk, Cfg("base", size=20))
    ck(acc.reasons["no_offer"] == 0 and acc.reasons["too_shallow"] == 0
       and acc.reasons["over_ceiling"] == 0 and acc.reasons["neg_ev"] == 0
       and acc.reasons["bought"] == 50,
       "a world where every close has a deep cheap offer reports NO liquidity, "
       "size or price problem at all -- the estimator does not invent one")

    # ---- PLANTED SIZE: a smaller SIZE must unlock a KNOWN number of closes -
    #      6 contracts on offer: floor is 10 at SIZE 20, 5 at SIZE 10.
    for n_unlock in (7, 23):
        closes, mk = _world(n_unlock, 0.96, 6.0)
        a20 = _run_world(closes, mk, Cfg("s20", size=20))
        a10 = _run_world(closes, mk, Cfg("s10", size=10))
        ck(a20.reasons["too_shallow"] == n_unlock
           and a20.reasons["bought"] == 0,
           f"{n_unlock} closes offering 6 contracts are ALL `too_shallow` at "
           f"SIZE 20 (floor {Cfg('x', size=20).floor():g}) "
           f"(got {a20.reasons['too_shallow']})")
        ck(a10.reasons["bought"] == n_unlock,
           f"and SIZE 10 (floor {Cfg('x', size=10).floor():g}) unlocks exactly "
           f"{n_unlock} of them (got {a10.reasons['bought']})")
        s10 = per_close_stats(a10, sorted(closes))
        ck(s10["closes_traded"] == n_unlock
           and abs(s10["fills"] - n_unlock) < 1e-9,
           "and trades them, one fill per close")
        # and it takes only what is there, not SIZE
        ck(abs(sum(a10.depths) - 6.0 * n_unlock) < 1e-9,
           "and the depth it saw is the 6 contracts on offer")

    # MIN_FILL_FRAC is the same lever without giving up size on deep books
    closes, mk = _world(12, 0.96, 6.0)
    af = _run_world(closes, mk, Cfg("frac", size=20, min_fill_frac=0.05))
    ck(af.reasons["bought"] == 12,
       "and MIN_FILL_FRAC 0.05 at SIZE 20 unlocks the same 12 closes")
    mixed, mk2 = _world(1, 0.96, 500.0)
    afd = _run_world(mixed, mk2, Cfg("frac", size=20, min_fill_frac=0.05))
    ck(abs(sum(b for b in [x for x in afd.px]) - 0.96) < 1e-9
       and sum(afd.fills.values()) == 1,
       "while a DEEP book at SIZE 20 still fills 20 -- the frac lever only "
       "loosens the floor")

    # ---- PLANTED PRICE: ceiling vs the EV gate, which are not the same -----
    closes, mk = _world(9, 0.99, 500.0)
    a98 = _run_world(closes, mk, Cfg("c98", size=20, ceiling=0.98))
    ck(a98.reasons["over_ceiling"] == 9,
       f"9 closes offered only at 99c are all `over_ceiling` at 0.98 "
       f"(got {a98.reasons['over_ceiling']})")
    a995 = _run_world(closes, mk, Cfg("c995", size=20, ceiling=0.995))
    ck(a995.reasons["neg_ev"] == 9,
       f"raising the ceiling to 0.995 does NOT unlock them -- pinrun's own EV "
       f"gate refuses all 9 (got {a995.reasons['neg_ev']}); "
       f"EV(0.99)={100*pinrun.expected_value(0.99):.3f}c < "
       f"{100*pinrun.EV_FLOOR:.1f}c")
    a995n = _run_world(closes, mk, Cfg("c995x", size=20, ceiling=0.995,
                                       ev_gate=False))
    ck(a995n.reasons["bought"] == 9,
       "and only lifting the EV gate as well unlocks them -- so the ceiling "
       "and the EV floor are two levers, not one")

    # ---- THE EV ARITHMETIC, RECONCILED BY HAND ----------------------------
    #      CLAUDE.md: reconcile the arithmetic by hand before believing a good
    #      number. The ceiling answer rests entirely on these six values, so
    #      they are computed here on paper and checked against pinrun.
    #
    #        EV(p) = (1-flip)(1-p) - flip*p - ceil(0.07*p*(1-p), $0.0001)
    #        flip = 0.0090, EV_FLOOR = 0.0030
    #
    #        p=0.9800  0.991*0.0200=0.0198200  0.009*0.9800=0.0088200
    #                  fee 0.07*0.98*0.02   =0.00137200 -> 0.0014
    #                  EV = 0.0198200-0.0088200-0.0014 = +0.0096  (+0.96c)
    #        p=0.9850  0.991*0.0150=0.0148650  0.009*0.9850=0.0088650
    #                  fee 0.07*0.985*0.015 =0.00103425 -> 0.0011
    #                  EV = 0.0148650-0.0088650-0.0011 = +0.0049  (+0.49c)
    #        p=0.9870  0.991*0.0130=0.0128830  0.009*0.9870=0.0088830
    #                  fee 0.07*0.987*0.013 =0.00089817 -> 0.0009
    #                  EV = 0.0128830-0.0088830-0.0009 = +0.0031  (+0.31c) PASS
    #        p=0.9875  0.991*0.0125=0.0123875  0.009*0.9875=0.0088875
    #                  fee 0.07*0.9875*0.0125=0.00086406 -> 0.0009
    #                  EV = 0.0123875-0.0088875-0.0009 = +0.0026  (+0.26c) FAIL
    #        p=0.9900  0.991*0.0100=0.0099100  0.009*0.9900=0.0089100
    #                  fee 0.07*0.99*0.01   =0.00069300 -> 0.0007
    #                  EV = 0.0099100-0.0089100-0.0007 = +0.0003  (+0.03c) FAIL
    #        p=0.9950  0.991*0.0050=0.0049550  0.009*0.9950=0.0089550
    #                  fee 0.07*0.995*0.005 =0.00034825 -> 0.0004
    #                  EV = 0.0049550-0.0089550-0.0004 = -0.0044  (-0.44c) FAIL
    #
    #      So the EV gate, not PRICE_CEILING, is what stops a ceiling above
    #      98.7c, and "raise the ceiling to 0.99" is arithmetically a no-op.
    HAND = {0.9800: 0.0096, 0.9850: 0.0049, 0.9870: 0.0031,
            0.9875: 0.0026, 0.9900: 0.0003, 0.9950: -0.0044}
    for _p, _want in HAND.items():
        _got = pinrun.expected_value(_p)
        ck(abs(_got - _want) < 5e-7,
           f"EV({_p:.4f}) = {100*_got:+.3f}c, hand-computed "
           f"{100*_want:+.3f}c")
    ck(abs(pinrun.MEASURED_FLIP - 0.009) < 1e-12
       and abs(pinrun.EV_FLOOR - 0.003) < 1e-12,
       f"and the hand table is computed at the CONSTANTS THAT ARE LIVE "
       f"(flip {pinrun.MEASURED_FLIP}, floor {pinrun.EV_FLOOR}) -- if either "
       f"moves this test fails rather than quietly lying")
    ck(abs(_ev_break() - 0.987) < 1e-9,
       f"and the highest price clearing the EV floor is 0.987 "
       f"(got {_ev_break()}), which is BELOW three of the four ceilings the "
       f"brief asked about, so 0.985/0.987/0.99/0.995 can differ only up to 0.987")

    # ---- the DUMP guard ---------------------------------------------------
    closes, mk = _world(5, 0.80, 500.0, fair=1.0)
    ad = _run_world(closes, mk, Cfg("dump", size=20))
    ck(ad.reasons["dumped"] == 5,
       f"a certainty offered 20c below fair is refused by the dump guard "
       f"({100*pinrun.DUMP_DISCOUNT:.0f}c) on all 5 closes "
       f"(got {ad.reasons['dumped']})")
    adn = _run_world(closes, mk, Cfg("nodump", size=20, dump=False))
    ck(adn.reasons["bought"] == 5, "and bought on all 5 with the guard off")

    # ---- the rails are PINSIM'S FUNCTIONS, not a local copy ---------------
    ck(rails is pinsim.close_slot_ok and book_slot is pinsim.close_slot_book,
       "the per-close rails are pinsim.close_slot_ok / close_slot_book "
       "themselves (commit 0b49a52), not a fourth copy of the decision")
    ck("pinrun.MAX_PER_CLOSE" not in body
       and "pinrun.MAX_PER_MARKET" not in body
       and "pinrun.IMPROVE_BY" not in body,
       "and simulate_close does not read those constants itself -- if it did, "
       "the rails could drift from live without this file changing")

    # ---- the PER-CLOSE RAILS ---------------------------------------------
    sv = (pinrun.MAX_PER_CLOSE, pinrun.MAX_PER_MARKET, pinrun.IMPROVE_BY)
    try:
        pinrun.MAX_PER_CLOSE, pinrun.MAX_PER_MARKET = 2, 1
        pinrun.IMPROVE_BY = 0.005
        cs = 100000
        mk = [{"ticker": "A", "series": "KXBTC15M", "close": cs,
               "result_yes": True, "strike": 1.0},
              {"ticker": "B", "series": "KXETH15M", "close": cs,
               "result_yes": True, "strike": 1.0},
              {"ticker": "C", "series": "KXSOL15M", "close": cs,
               "result_yes": True, "strike": 1.0}]
        rows = [_row(1, cs - 20, 20, 0, 1.0, S_YES, 0.96, 500.0),
                _row(2, cs - 19, 19, 0, 1.0, S_YES, 0.95, 500.0),
                _row(3, cs - 18, 18, 1, 1.0, S_YES, 0.96, 500.0),
                _row(4, cs - 17, 17, 1, 1.0, S_YES, 0.90, 500.0),
                _row(5, cs - 16, 16, 2, 1.0, S_YES, 0.89, 500.0)]
        buys, reasons = simulate_close(rows, mk, Cfg("rails", size=20))
        ck(len(buys) == 2 and [b["tk"] for b in buys] == ["A", "B"]
           and [b["price"] for b in buys] == [0.96, 0.90],
           f"the rails allow 2 fills on 2 markets, the second only at a price "
           f"IMPROVE_BY better (got {[(b['tk'], b['price']) for b in buys]})")
        ck(reasons[2] == "close_cap",
           f"and the third market is `close_cap` (got {reasons[2]})")
        ck(reasons[0] == "bought" and reasons[1] == "bought",
           "with the two fills recorded as `bought`")
        # a market that only failed the improve bar is NOT retired
        rows2 = [_row(1, cs - 20, 20, 0, 1.0, S_YES, 0.96, 500.0),
                 _row(2, cs - 19, 19, 1, 1.0, S_YES, 0.958, 500.0),
                 _row(3, cs - 18, 18, 1, 1.0, S_YES, 0.93, 500.0)]
        buys2, reasons2 = simulate_close(rows2, mk, Cfg("rails", size=20))
        ck(len(buys2) == 2 and buys2[1]["price"] == 0.93,
           "a market refused by the improve bar at 95.8c still fills at 93c "
           "seconds later -- the refusal does not retire it")
        # one fill per market
        rows3 = [_row(1, cs - 20, 20, 0, 1.0, S_YES, 0.96, 500.0),
                 _row(2, cs - 19, 19, 0, 1.0, S_YES, 0.90, 500.0)]
        buys3, reasons3 = simulate_close(rows3, mk, Cfg("rails", size=20))
        ck(len(buys3) == 1,
           f"and MAX_PER_MARKET={pinrun.MAX_PER_MARKET} stops the same market "
           f"filling twice even at a better price (got {len(buys3)})")
    finally:
        pinrun.MAX_PER_CLOSE, pinrun.MAX_PER_MARKET, pinrun.IMPROVE_BY = sv

    # ---- THE LADDER: one reason per market, the CLOSEST it came -----------
    cs = 100000
    mk = [{"ticker": "A", "series": "KXBTC15M", "close": cs,
           "result_yes": True, "strike": 1.0}]
    rows = [_row(1, cs - 25, 25, 0, 1.0, S_YES, None, 0.0),      # no_offer
            _row(2, cs - 24, 24, 0, 1.0, S_YES, None, 0.0),
            _row(3, cs - 23, 23, 0, 1.0, S_YES, 0.99, 500.0),    # over_ceiling
            _row(4, cs - 22, 22, 0, 1.0, S_YES, None, 0.0),
            _row(5, cs - 21, 21, 0, 1.0, S_YES, 0.97, 4.0)]      # too_shallow
    _, reasons = simulate_close(rows, mk, Cfg("ladder", size=20))
    ck(reasons[0] == "over_ceiling",
       f"a market that was mostly unoffered but once showed a 99c offer and "
       f"once a shallow 97c one is `over_ceiling` -- the closest rung it "
       f"reached, not the commonest (got {reasons[0]})")
    rows_b = rows[:2] + [rows[4]]
    _, rb = simulate_close(rows_b, mk, Cfg("ladder", size=20))
    ck(rb[0] == "too_shallow",
       f"drop the 99c moment and the same market reads `too_shallow` "
       f"(got {rb[0]})")
    _, rc = simulate_close(rows[:2], mk, Cfg("ladder", size=20))
    ck(rc[0] == "no_offer",
       f"drop both and it reads `no_offer` (got {rc[0]})")

    # ---- the TAU band is a filter, and `no_gate` / `no_model` are separated
    rows_t = [_row(1, cs - 45, 45, 0, 1.0, S_YES, 0.96, 500.0),
              _row(2, cs - 20, 20, 0, 1.0, S_UNDEC, None, 0.0)]
    b30, r30 = simulate_close(rows_t, mk, Cfg("t30", size=20, tau_max=30))
    b60, r60 = simulate_close(rows_t, mk, Cfg("t60", size=20, tau_max=60))
    ck(not b30 and r30[0] == "no_gate",
       f"at TAU_MAX 30 a 96c offer at tau 45 is invisible and the market reads "
       f"`no_gate` from its tau-20 undecided moment (got {r30[0]})")
    ck(len(b60) == 1 and b60[0]["tau"] == 45,
       "and at TAU_MAX 60 it is bought at tau 45")
    rows_m = [_row(1, cs - 20, 20, 0, 0.0, S_NOMODEL, None, 0.0)]
    _, rm = simulate_close(rows_m, mk, Cfg("m", size=20))
    ck(rm[0] == "no_model",
       "a market with no sigma reads `no_model`, never `no_offer` -- "
       "'no power' and 'no effect' are different results")

    # ---- staleness -------------------------------------------------------
    rows_s = [_row(1, cs - 20, 20, 0, 1.0, S_YES, 0.96, 500.0,
                   age=pinrun.MAX_BOOK_AGE_MS + 1)]
    _, rs = simulate_close(rows_s, mk, Cfg("stale", size=20))
    ck(rs[0] == "stale_book",
       f"a cheap deep offer on a book {pinrun.MAX_BOOK_AGE_MS + 1} ms old is "
       f"`stale_book`, as live requires (got {rs[0]})")
    rows_i = [_row(1, cs - 20, 20, 0, 1.0, S_YES, 0.96, 500.0,
                   iage=pinrun.MAX_INDEX_AGE_S + 1)]
    _, ri = simulate_close(rows_i, mk, Cfg("stalei", size=20))
    ck(ri[0] == "stale_index", f"and a stale index is its own reason ({ri[0]})")

    # ---- THE CENSUS WEIGHTING, which is where the first bug was -----------
    #      One busy market with an ask at every event, one thin market with
    #      none. Per market-second the truth is 50/50; state-weighted it is
    #      not, and that is the error this test exists to catch.
    cs3 = 200000
    BUSY, THIN = 8, 1                 # book states per second
    mkts = [{"ticker": "BUSY", "series": "KXBTC15M", "close": cs3,
             "result_yes": True, "strike": 1.0},
            {"ticker": "THIN", "series": "KXNEAR15M", "close": cs3,
             "result_yes": True, "strike": 1.0}]
    rws = []
    nsec = 20
    for k in range(nsec):
        sec3 = cs3 - 3 - k
        tau3 = cs3 - sec3
        for j in range(BUSY):
            rws.append(_row(len(rws) + 1, sec3, tau3, 0, 1.0, S_YES,
                            0.996, 500.0 + j))
        for j in range(THIN):
            rws.append(_row(len(rws) + 1, sec3, tau3, 1, 1.0, S_YES,
                            None, 0.0))
    cen3 = defaultdict(int)
    cb3, at3, am3 = {}, defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    census_cell({"markets": mkts, "rows": rws}, cen3, cb3, at3, am3)
    ck(cen3["rows"] == 2 * nsec,
       f"a world of {BUSY} book states a second on one market and {THIN} on "
       f"another, over {nsec} seconds, is {2*nsec} MARKET-SECONDS and not "
       f"{nsec*(BUSY+THIN)} states (got {cen3['rows']})")
    ck(cen3["ask_our_side"] == nsec and cen3["no_ask_our_side"] == nsec,
       f"and the census splits them 50/50 -- {nsec} with an ask, {nsec} "
       f"without (got {cen3['ask_our_side']} / "
       f"{cen3['no_ask_our_side']}), NOT "
       f"{100.0*BUSY/(BUSY+THIN):.0f}% / {100.0*THIN/(BUSY+THIN):.0f}% as a "
       f"state-weighted count would say")
    ck(cen3["px >99.5c"] == nsec and cen3["px <=98.0c"] == 0,
       f"and prices them once each in the >99.5c bucket "
       f"(got {cen3['px >99.5c']})")
    ck(at3[min(3 // 5 * 5, 60)][0] > 0 and am3[0][0] == 2,
       "the per-MARKET tau tally counts each market once in a tau bucket, "
       f"not once per second (got {am3[0][0]} markets in bucket 0-4s)")
    # a stale book must not be counted as an offer
    rws2 = [_row(1, cs3 - 5, 5, 0, 1.0, S_YES, 0.96, 500.0,
                 age=pinrun.MAX_BOOK_AGE_MS + 1)]
    cen4 = defaultdict(int)
    census_cell({"markets": mkts, "rows": rws2}, cen4, {},
                defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]))
    ck(cen4["stale"] == 1 and cen4["ask_our_side"] == 0,
       f"and a market-second whose only state was a stale book is counted "
       f"stale and never as an offer (got stale {cen4['stale']}, "
       f"ask {cen4['ask_our_side']})")

    # ---- per_close_stats must SUBSET every field, not just the P&L --------
    closes2, mk2 = _world(10, 0.96, 500.0)
    acc2 = _run_world(closes2, mk2, Cfg("s", size=20))
    allc = sorted(closes2)
    st_all = per_close_stats(acc2, allc)
    st_half = per_close_stats(acc2, allc[:5])
    ck(st_all["fills"] == 10 and st_half["fills"] == 5,
       f"the fill count follows the denominator -- 10 closes give 10 fills "
       f"and the first 5 give 5 (got {st_all['fills']} / "
       f"{st_half['fills']}), NOT the whole accumulator's 10 both times")
    ck(abs(st_half["contracts"] - 100.0) < 1e-9,
       f"and so does the contract count (got {st_half['contracts']})")
    ck(abs(st_half["mean_px"] - 0.96) < 1e-9
       and abs(st_all["pnl"] - 2 * st_half["pnl"]) < 1e-9,
       "and the mean price and P&L are the subset's own")

    # ---- the MDE is on the PAIRED per-close difference --------------------
    closes, mk = _world(40, 0.96, 6.0)
    a20 = _run_world(closes, mk, Cfg("s20", size=20))
    a10 = _run_world(closes, mk, Cfg("s10", size=10))
    d = paired_mde(a10, a20, sorted(closes))
    ck(d["n"] == 40 and abs(d["se"]) < 1e-12 and d["mde"] == 0.0,
       "a world where every close moves by the SAME amount has zero paired "
       "variance, so the MDE is 0 and the difference is certain")
    closes2 = dict(closes)
    for i, cs2 in enumerate(sorted(closes2)):
        if i % 2:
            for r in closes2[cs2]:
                r[6] = None
                r[7] = 0.0
    a20b = _run_world(closes2, mk, Cfg("s20", size=20))
    a10b = _run_world(closes2, mk, Cfg("s10", size=10))
    d2 = paired_mde(a10b, a20b, sorted(closes2))
    ck(d2["se"] > 0 and d2["mde"] > 0 and d2["t"] > 2,
       f"and when only half the closes move, the MDE is positive "
       f"(${d2['mde']:.4f}) and the measured difference "
       f"(${d2['diff']:.4f}) still beats it, t={d2['t']:.1f}")

    # ---- the model is pinrun's, not a copy --------------------------------
    ck(pinsim.TapeIndex.partial is pinrun.IndexWS.partial
       and pinsim.TapeIndex.sigma is pinrun.IndexWS.sigma,
       "the index this file drives is pinrun's own partial()/sigma()")
    # built from pieces so the test does not match ITSELF -- the first
    # version of this line failed because the needle was in the haystack
    _d = "de" + "f "
    ck(all((_d + nm) not in mine
           for nm in ("fair(", "net_edge", "expected_value", "billed_fee",
                      "var_factor", "partial")),
       "and nothing here reimplements fair/net_edge/expected_value/"
       "billed_fee/var_factor/partial -- they are pinrun's")

    if fails:
        print(f"SELF-TEST *** FAILED *** ({len(fails)})")
        for m in fails:
            print("   - " + m)
        return False
    print("SELF-TEST passed")
    return True


# ---------------------------------------------------------------- the report
def gate_line():
    return (f"PIN={pinrun.PIN} ceiling={pinrun.PRICE_CEILING} "
            f"tau=[{pinrun.TAU_MIN},{pinrun.TAU_MAX}] SIZE={pinrun.SIZE:g} "
            f"min_fill_frac={pinrun.MIN_FILL_FRAC} "
            f"min_level={pinrun.MIN_LEVEL:g} "
            f"edge_floor={pinrun.EDGE_FLOOR} ev_floor={pinrun.EV_FLOOR} "
            f"flip={pinrun.MEASURED_FLIP} dump={pinrun.DUMP_DISCOUNT} "
            f"max_per_close={pinrun.MAX_PER_CLOSE} "
            f"max_per_market={pinrun.MAX_PER_MARKET} "
            f"improve_by={pinrun.IMPROVE_BY} "
            f"book_age<={pinrun.MAX_BOOK_AGE_MS}ms "
            f"index_age<={pinrun.MAX_INDEX_AGE_S}s")


def configs(size_live):
    """Every configuration measured, base first."""
    cs = [Cfg("BASE (live gate)", size=size_live)]
    for s in (10, 5, 2, 1):
        cs.append(Cfg(f"SIZE {s}", size=s))
    for fr in (0.25, 0.05):
        cs.append(Cfg(f"SIZE {size_live:g} frac {fr}", size=size_live,
                      min_fill_frac=fr))
    for c in (0.985, 0.987, 0.99, 0.995):
        cs.append(Cfg(f"ceiling {c}", size=size_live, ceiling=c))
    for c in (0.985, 0.99, 0.995):
        cs.append(Cfg(f"ceiling {c} noEV", size=size_live, ceiling=c,
                      ev_gate=False))
    # 35 and 40 are here because the prior kill (pinrun AMENDMENT 4, at the
    # OLD gate PIN=0.98) measured 31-45 as a BLOCK and called it a wall. If a
    # wall exists at the current 0.995 gate it has a location, and 30/35/40/45
    # finds it; if 35 and 40 look like 30 and only 45 breaks, that is a
    # different fact from "do not go past 30".
    for t in (35, 40, 45, 60):
        cs.append(Cfg(f"TAU_MAX {t}", size=size_live, tau_max=t))
    cs.append(Cfg("SIZE 5 + frac 0.05", size=5, min_fill_frac=0.05))
    cs.append(Cfg(f"SIZE {size_live:g} frac 0.05 + TAU_MAX 45",
                  size=size_live, min_fill_frac=0.05, tau_max=45))
    cs.append(Cfg("ceiling 0.987 + TAU_MAX 45", size=size_live,
                  ceiling=0.987, tau_max=45))
    return cs


def census_cell(cell, cen, close_best, acc_tau, acc_tau_mk):
    """The CENSUS for one hour's cell, aggregated to ONE ROW PER
    (MARKET, SECOND) before anything is counted.

    Extracted so it has its own planted self-test. The first version
    counted BOOK STATES: KXBTC15M, whose book changes ~7x a second and
    always carries an ask, contributed 204 rows to a close where
    KXNEAR15M contributed 28, and the census read "an ask exists 84% of
    the time" when the per-second truth was 32%. The thin books -- the
    entire subject of this file -- had been weighted out of their own
    measurement. A state-weighted census is a statement about the
    busiest market, not about the product.

    Mutates the four accumulators in place; returns nothing.
    """
    mk = cell["markets"]
    seen = set()
    seen_mk = set()
    sec_agg = {}             # (market, second) -> the census aggregate
    band = set()             # (market, second) present at all in the band
    for row in cell["rows"]:
        _, sec, tau, mi, fv, side, px, sz, age, iage, opp = row
        # COVERAGE FIRST, and it counts every row regardless of the model.
        # The trade/book channels have collector-side recording holes
        # (results/RESULTS_tapegaps.md: 3.28% of trading-window seconds fall
        # in a silent run >= 10 s). A hole does NOT show up as a stale book
        # here: with no events arriving, `Walk`'s clock never reaches those
        # seconds and the replay generates NO MOMENT AT ALL, so the seconds
        # are simply absent. The only way to see them is to count the
        # market-seconds we DO have against the ones the band should hold.
        if pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX:
            band.add((mi, sec))
        if side in (S_UNDEC, S_NOMODEL):
            continue
        want_yes = side == S_YES
        ok = (mk[mi]["result_yes"] == want_yes)
        bkt = min(tau // 5 * 5, 60)
        # AND the exact bands pinrun's AMENDMENT 4 used, so the re-test is a
        # like-for-like comparison with the number that killed this lever.
        a4 = ("3-10" if tau <= 10 else "11-20" if tau <= 20 else
              "21-30" if tau <= 30 else "31-45" if tau <= 45 else "46-60")
        if (mi, sec) not in seen:
            seen.add((mi, sec))
            b = acc_tau[bkt]
            b[0] += 1
            b[1] += 1 if ok else 0
            b2 = acc_tau["A4 " + a4]
            b2[0] += 1
            b2[1] += 1 if ok else 0
        if (mi, bkt) not in seen_mk:
            seen_mk.add((mi, bkt))
            b = acc_tau_mk[bkt]
            b[0] += 1
            b[1] += 1 if ok else 0
        if (mi, a4) not in seen_mk:
            seen_mk.add((mi, a4))
            b2 = acc_tau_mk["A4 " + a4]
            b2[0] += 1
            b2[1] += 1 if ok else 0
        # ---- the census, LIVE band only -----------------------------
        # AGGREGATED TO ONE ROW PER (MARKET, SECOND) FIRST. A first
        # version counted BOOK STATES, and BTC -- whose book changes
        # ~7x a second and always has an ask -- contributed 204 rows to
        # a close where KXNEAR contributed 28. That weighting makes the
        # thin books vanish and reads as "84% of the time there is an
        # offer", which is a statement about BTC, not about the product.
        if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
            continue
        fresh = (age is not None and age <= pinrun.MAX_BOOK_AGE_MS
                 and iage is not None and iage <= pinrun.MAX_INDEX_AGE_S)
        k = (mi, sec)
        g = sec_agg.get(k)
        if g is None:
            g = sec_agg[k] = {"fresh": False, "ask": False, "opp": False,
                              "px": {}}
        if fresh:
            g["fresh"] = True
        else:
            continue                # a stale state offers us nothing
        if px is None or not sz:
            if opp:
                g["opp"] = True
            continue
        g["ask"] = True
        # the deepest size ever seen at this price this second
        if sz > g["px"].get(px, 0.0):
            g["px"][px] = sz
    cen["band_ms"] += len(band)
    cen["band_markets"] += len(set(mi for mi, _ in band))
    # --- classify each (market, second) exactly once -----------------
    for (mi, sec), g in sec_agg.items():
        cen["rows"] += 1
        if not g["fresh"]:
            cen["stale"] += 1
            continue
        cen["fresh"] += 1
        cs0 = mk[mi]["close"]
        cb = close_best.get(cs0)
        if cb is None:
            cb = close_best[cs0] = {"deep": None, "any": None,
                                    "ask": False, "opp": False}
        if not g["ask"]:
            cen["no_ask_our_side"] += 1
            cen["no_ask_but_opp_has_one" if g["opp"]
                else "book_dead_both"] += 1
            if g["opp"]:
                cb["opp"] = True
            continue
        cen["ask_our_side"] += 1
        cb["ask"] = True
        for lab, floor in (("d10", 10.0), ("d5", 5.0), ("d2", 2.0),
                           ("d1", 1.0)):
            ok = [p for p, s in g["px"].items() if s >= floor]
            if not ok:
                continue
            cen["ask_" + lab] += 1
            if min(ok) <= pinrun.PRICE_CEILING:
                cen["ok_px_" + lab] += 1
        cheapest = min(g["px"])
        deep = [p for p, s in g["px"].items() if s >= 10.0]
        for lo2, hi2, lab in ((0.0, 0.980, "<=98.0c"),
                              (0.980, 0.987, "98.0-98.7c"),
                              (0.987, 0.990, "98.7-99.0c"),
                              (0.990, 0.995, "99.0-99.5c"),
                              (0.995, 1.0, ">99.5c")):
            if lo2 < cheapest <= hi2:
                cen["px " + lab] += 1
            if deep and lo2 < min(deep) <= hi2:
                cen["pxdeep " + lab] += 1
        if deep and (cb["deep"] is None or min(deep) < cb["deep"]):
            cb["deep"] = min(deep)
        if cb["any"] is None or cheapest < cb["any"]:
            cb["any"] = cheapest


def report(cells, size_live, out, stamps=None, say=print):
    cfgs = configs(size_live)
    accs = [Acc(c) for c in cfgs]
    # model accuracy by tau, from the replay: what the model computed vs what
    # the market did. ONE row per (market, second) certain moment, and a
    # second tally clustered to ONE ROW PER MARKET per tau bucket, because
    # seconds within a market are not independent (hard rule 4).
    acc_tau = defaultdict(lambda: [0, 0])
    acc_tau_mk = defaultdict(lambda: [0, 0])
    # THE OFFER CENSUS. Over every certain (market, second) in the LIVE band,
    # what was actually on our side of the book. A census, not an inference:
    # market-seconds are the unit and are never used as `n` for a t.
    cen = defaultdict(int)
    # and PER CLOSE: the cheapest ask seen anywhere in the close, at each of
    # two size floors. This is what separates a SIZE fix from a PRICE fix.
    close_best = {}          # close -> {"deep": px|None, "any": px|None,
    #                                    "ask": bool, "opp": bool}
    hours = 0
    rows_tot = 0
    days = set()
    base_certain = set()
    all_closes = set()
    for cell in load_cells(cells, stamps):
        hours += 1
        rows_tot += len(cell["rows"])
        mk = cell["markets"]
        census_cell(cell, cen, close_best, acc_tau, acc_tau_mk)
        for cs, rows in by_close(cell).items():
            all_closes.add(cs)
            days.add(time.strftime("%Y-%m-%d", time.gmtime(cs)))
            for cfg, acc in zip(cfgs, accs):
                buys, reasons = simulate_close(rows, mk, cfg)
                acc.add(cs, buys, reasons)
        base_certain |= accs[0].certain_closes
    if not hours:
        say("  loaded nothing -- no cell files")
        return None
    # THE DENOMINATOR. A first version used the closes certain inside the
    # LIVE band [3,30], and that silently deleted the TAU_MAX levers' whole
    # point: a close the model only reaches at tau 38 is not in that set, so
    # its P&L was dropped from the numerator and the lever measured as
    # smaller than it is. The denominator is therefore the closes certain
    # anywhere in the SCANNED band [3,60] -- the widest any configuration
    # here can see -- so it is identical for every row and no configuration
    # can gain a close that lies outside it.
    _t60 = next((i for i, c in enumerate(cfgs)
                 if c.tau_max >= SCAN_TAU_MAX), None)
    denom = sorted(accs[_t60].certain_closes if _t60 is not None
                   else base_certain)
    denom30 = sorted(base_certain)
    n = len(denom)
    n30 = len(denom30)
    cut = int(round(0.70 * n))
    train, hold = denom[:cut], denom[cut:]
    say(f"  {hours} book hours, {rows_tot:,} cell rows, "
        f"{len(all_closes)} closes seen, {n30} certain in the live band "
        f"[{pinrun.TAU_MIN},{pinrun.TAU_MAX}], {n} certain in the scanned "
        f"band [{SCAN_TAU_MIN},{SCAN_TAU_MAX}] (the denominator), "
        f"{len(days)} UTC days")

    L = []
    W = L.append
    W("# RESULTS_count -- why we trade nothing on half the certain closes")
    W("")
    W(f"Generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} by "
      f"`research/pincount.py` on the REBUILT replay (`pinsim` commit with "
      f"per-close rails). Every decision is pinrun's own `fair`, `net_edge`, "
      f"`expected_value`, `billed_fee` and constants.")
    W("")
    W(f"**Gate replayed:** `{gate_line()}`")
    W("")
    W(f"**Window:** {hours} book hours, {len(days)} UTC days "
      f"({min(days)} .. {max(days)}), {len(all_closes)} closes seen. "
      f"**{n30} closes carry a model-certain market inside the LIVE band tau "
      f"[{pinrun.TAU_MIN},{pinrun.TAU_MAX}]** -- that is the number section 1 "
      f"decomposes. **{n} carry one anywhere in the SCANNED band tau "
      f"[{SCAN_TAU_MIN},{SCAN_TAU_MAX}], and that is the fixed denominator "
      f"for every $/close figure**, because it is the widest band any row "
      f"here can see: no configuration can gain a close outside it, and no "
      f"lever can flatter itself by shrinking its own denominator. Divide by "
      f"{len(all_closes)} instead if you want $ per quarter-hour of "
      f"wall-clock.")
    W("")
    W("**Clustering:** one observation = one CLOSE. Twelve series settle on "
      "the same second at rho ~ 0.8, so per-market counts are reported as "
      "counts only and never as `n` for a t-statistic (CLAUDE.md hard rule 4).")
    W("")
    gp = os.path.join(cells, "gaps.json")
    if os.path.exists(gp):
        gd = json.load(open(gp, encoding="utf-8"))
        gd = {k: v for k, v in gd.items() if stamps is None or k in stamps}
        gf = sum(v[0] for v in gd.values())
        gt = sum(v[1] for v in gd.values())
        W(f"**The book is not perfect, and here is how imperfect.** The "
          f"collector stamps `_seq_gap` on any frame whose `seq` is not "
          f"prev+1; at that instant the book for that subscription is "
          f"provably wrong. This window contains **{gf:,} such flags over "
          f"{gt:,} delta messages across {len(gd)} hours "
          f"({gf/max(len(gd),1):.1f} per hour, "
          f"{100.0*gf/max(gt,1):.5f}%)**. Nothing below refuses a decision on "
          f"a gap -- pinsim's own note explains why 11 events an hour cannot "
          f"justify the decision-time cost -- so no number here should be "
          f"believed to the cent.")
        W("")
    else:
        W("**`_seq_gap` NOT COUNTED for this window** -- run "
          "`pincount.py --gaps` to fill it in. The collector flags frames "
          "whose `seq` is not prev+1 and the book is provably wrong at each "
          "of them; pinsim measured ~11 an hour.")
        W("")
    W("**Loss rates:** no loss rate for US is quoted from the tape "
      "(CLAUDE.md 2026-09-10 rule 5). Every dollar column appears twice: "
      "`tape` is the settled outcome of each replayed fill and is a RANKING "
      "of levers only; `ev` is `pinrun.expected_value` at the price paid, "
      "which carries the project's own MEASURED_FLIP "
      f"({100*pinrun.MEASURED_FLIP:.1f}%) and is the criterion the live bot "
      "itself applies.")
    W("")
    # THE VERDICT IS HAND-WRITTEN AND LIVES IN ITS OWN FILE, so that re-running
    # the tables cannot silently delete it and so that it is obvious which
    # sentences are a judgement and which are output.
    vf = os.path.join(os.path.dirname(out), "_count_verdict.md")
    if os.path.exists(vf):
        W(open(vf, encoding="utf-8").read().rstrip())
        W("")
    else:
        W("> _(the verdict section is hand-written in "
          "`results/_count_verdict.md` and inserted here; it is absent from "
          "this build.)_")
        W("")

    # ---- 1. the decomposition -------------------------------------------
    base = accs[0]
    traded = {c for c in denom30 if base.fills.get(c)}
    silent = [c for c in denom30 if c not in traded]
    W("## 1. The decomposition")
    W("")
    W(f"Live band only, so this is directly comparable with "
      f"`RESULTS_maker.md`'s 411 of 793. Of **{n30} closes with a "
      f"model-certain market in tau [{pinrun.TAU_MIN},{pinrun.TAU_MAX}]**, "
      f"we trade on **{len(traded)} ({100.0*len(traded)/max(n30,1):.1f}%)** "
      f"and nothing at all on **{len(silent)} "
      f"({100.0*len(silent)/max(n30,1):.1f}%)**.")
    W("")
    W("### Per MARKET, one reason each -- the closest rung it reached")
    W("")
    W("| reason | cause | markets | share of certain |")
    W("|---|---|---|---|")
    cert_m = base.certain_markets
    for r in LADDER:
        k = base.reasons.get(r, 0)
        if not k or r in ("no_gate", "no_model"):
            continue
        W(f"| `{r}` | {CAUSE[r]} | {k:,} | "
          f"{100.0*k/cert_m if cert_m else 0:.1f}% |")
    W(f"| **total certain markets** | | **{cert_m:,}** | 100% |")
    W(f"| (`no_gate`: never certain) | no signal | "
      f"{base.reasons.get('no_gate', 0):,} | -- |")
    W(f"| (`no_model`: no sigma/fair) | no signal | "
      f"{base.reasons.get('no_model', 0):,} | -- |")
    W("")
    # the same, rolled up by cause
    bycause = defaultdict(int)
    for r in LADDER:
        if r in ("no_gate", "no_model"):
            continue
        bycause[CAUSE[r]] += base.reasons.get(r, 0)
    W("| cause | markets | share | the fix it implies |")
    W("|---|---|---|---|")
    FIX = {"traded": "none",
           "our rules": "loosen a rail (measured elsewhere)",
           "PRICE": "raise PRICE_CEILING / EV_FLOOR",
           "SIZE": "lower SIZE or MIN_FILL_FRAC",
           "LIQUIDITY": "nothing we can price -- nobody is offering",
           "our book": "faster book / longer staleness budget"}
    for c2, k in sorted(bycause.items(), key=lambda kv: -kv[1]):
        W(f"| **{c2}** | {k:,} | {100.0*k/cert_m if cert_m else 0:.1f}% | "
          f"{FIX.get(c2, '')} |")
    W("")
    W("### The SAME table restricted to the closes we traded NOTHING on")
    W("")
    W(f"This is the table the question asks for: the {len(silent)} certain "
      f"closes where we bought nothing, decomposed over their markets. The "
      f"rungs a traded close reaches -- `close_cap`, `no_improve`, `bought` "
      f"-- cannot appear here, so what is left is the reason the close was "
      f"untradeable.")
    W("")
    sil = defaultdict(int)
    sil_cert = 0
    for c in silent:
        for r, k in base.by_close.get(c, {}).items():
            sil[r] += k
            if r not in ("no_gate", "no_model"):
                sil_cert += k
    W("| reason | cause | markets | share of certain markets on silent closes |")
    W("|---|---|---|---|")
    for r in LADDER:
        k = sil.get(r, 0)
        if not k or r in ("no_gate", "no_model"):
            continue
        W(f"| `{r}` | {CAUSE[r]} | {k:,} | "
          f"{100.0*k/max(sil_cert,1):.1f}% |")
    W(f"| **total certain markets on silent closes** | | **{sil_cert:,}** | "
      f"100% |")
    W(f"| (`no_gate`) | no signal | {sil.get('no_gate', 0):,} | -- |")
    W(f"| (`no_model`) | no sigma/fair | {sil.get('no_model', 0):,} | -- |")
    W("")
    _sb = defaultdict(int)
    for r in LADDER:
        if r in ("no_gate", "no_model"):
            continue
        _sb[CAUSE[r]] += sil.get(r, 0)
    W("| cause | markets | share | the fix it implies |")
    W("|---|---|---|---|")
    for c2, k in sorted(_sb.items(), key=lambda kv: -kv[1]):
        if not k:
            continue
        W(f"| **{c2}** | {k:,} | {100.0*k/max(sil_cert,1):.1f}% | "
          f"{FIX.get(c2, '')} |")
    W("")
    W("### Per CLOSE -- the best rung any of its markets reached")
    W("")
    W("| best reason on the close | cause | closes | share |")
    W("|---|---|---|---|")
    cr = defaultdict(int)
    for c in denom30:
        cr[base.close_reason.get(c, "no_gate")] += 1
    for r in LADDER:
        if not cr.get(r):
            continue
        W(f"| `{r}` | {CAUSE[r]} | {cr[r]:,} | "
          f"{100.0*cr[r]/max(n30,1):.1f}% |")
    W("")
    W("**Read the per-close table, not the per-market one, for what to fix.** "
      "A close is tradeable if ANY of its twelve markets is; the per-market "
      "table is dominated by the many markets in a close we already traded.")
    W("")

    # ---- 1b. the offer census -------------------------------------------
    W("### Coverage first -- how much of the band the tape actually holds")
    W("")
    _wid = pinrun.TAU_MAX - pinrun.TAU_MIN + 1
    _exp = cen["band_markets"] * _wid
    W(f"The live band is {_wid} seconds wide. "
      f"**{cen['band_markets']:,} markets appear in it at all, so a complete "
      f"tape would hold {_exp:,} market-seconds; the replay produced "
      f"{cen['band_ms']:,} ({100.0*cen['band_ms']/max(_exp,1):.1f}%).**")
    W("")
    W("The shortfall is NOT a stale book and cannot be read off the stale "
      "count. With no events arriving, `pinsim.Walk`'s clock never reaches "
      "those seconds and the replay generates no moment at all -- the second "
      "is absent, not stale. `results/RESULTS_tapegaps.md` measured 3.28% of "
      "trading-window seconds inside a silent run of >= 10 s, collector-side, "
      "with the book going quiet alongside the trades. **So every COUNT below "
      "is a lower bound**, and a market that never produced a single book "
      "event in the band does not appear in the market total above either.")
    W("")
    W("### The offer census -- what was actually on our side of the book")
    W("")
    W(f"Every certain (market, second) inside tau "
      f"[{pinrun.TAU_MIN},{pinrun.TAU_MAX}] with a fresh book and index. "
      f"A CENSUS: market-seconds are the unit and are never used as `n` for a "
      f"t-statistic. {cen['rows']:,} certain market-seconds, of which "
      f"{cen['stale']:,} ({100.0*cen['stale']/max(cen['rows'],1):.1f}%) had a "
      f"stale book or index and are excluded below.")
    W("")
    fr = max(cen["fresh"], 1)
    W("| on our side of the book | market-seconds | share of fresh certain |")
    W("|---|---|---|")
    for lab, k in (("an ask exists", cen["ask_our_side"]),
                   ("...and >= 10 contracts rest on it (the SIZE 20 floor)",
                    cen["ask_d10"]),
                   ("...and >= 10 AND at or below the 98c ceiling",
                    cen["ok_px_d10"]),
                   ("...>= 5 contracts", cen["ask_d5"]),
                   ("...>= 5 AND at or below 98c", cen["ok_px_d5"]),
                   ("...>= 2 contracts", cen["ask_d2"]),
                   ("...>= 2 AND at or below 98c", cen["ok_px_d2"]),
                   ("...>= 1 contract", cen["ask_d1"]),
                   ("...>= 1 AND at or below 98c", cen["ok_px_d1"]),
                   ("NO ask on our side at any price",
                    cen["no_ask_our_side"]),
                   ("...but the LOSING side still had an ask",
                    cen["no_ask_but_opp_has_one"]),
                   ("...and neither side had one (book dead)",
                    cen["book_dead_both"])):
        W(f"| {lab} | {k:,} | {100.0*k/fr:.1f}% |")
    W("")
    W("**The one-sidedness is the mechanism.** When the outcome becomes "
      "obvious the losing side's bids vanish, so the winner has no ask -- "
      f"that is {cen['no_ask_but_opp_has_one']:,} of the "
      f"{cen['no_ask_our_side']:,} unoffered market-seconds "
      f"({100.0*cen['no_ask_but_opp_has_one']/max(cen['no_ask_our_side'],1):.1f}%"
      "), where the book was NOT dead, just one-sided against us. That is a "
      "capacity limit, not a data limit, and no threshold reaches it.")
    W("")
    W("Two SEPARATE distributions, not a subset: the left column is the "
      "cheapest ask of any size, the right the cheapest ask holding at least "
      "10 contracts. A market-second can sit in different buckets in the two "
      "columns, so the right column is not a subset of the left.")
    W("")
    W("| price bucket | market-seconds by CHEAPEST ask | "
      "market-seconds by cheapest >= 10-DEEP ask |")
    W("|---|---|---|")
    for lab in ("<=98.0c", "98.0-98.7c", "98.7-99.0c", "99.0-99.5c",
                ">99.5c"):
        W(f"| {lab} | {cen['px ' + lab]:,} | {cen['pxdeep ' + lab]:,} |")
    W("")

    # ---- 1c. the per-close 2x2: which fix would reach each silent close --
    W("### The silent closes, by the CHEAPEST offer that ever appeared on them")
    W("")
    W(f"For each of the {len(silent)} certain closes we traded nothing on: "
      f"the cheapest ask that appeared on the model's side, on any of its "
      f"markets, at any second in tau [{pinrun.TAU_MIN},{pinrun.TAU_MAX}], "
      f"with a fresh book -- at two size floors. "
      f"**98.7c is where pinrun's own EV gate stops, not where the ceiling "
      f"stops** (hand-reconciled in the self-test: EV(0.987)=+0.31c clears "
      f"the 0.30c floor and EV(0.988)=+0.21c does not), so the "
      f"`98.0-98.7c` rows are the only price headroom that exists without "
      f"also moving EV_FLOOR or MEASURED_FLIP.")
    W("")
    W("| the best offer the close ever showed | closes | share of silent | "
      "the lever that would reach it |")
    W("|---|---|---|---|")
    buck = defaultdict(int)
    for c in silent:
        cb = close_best.get(c)
        if cb is None or not cb["ask"]:
            buck["no ask on our side, ever" if (cb is None or not cb["opp"])
                 else "no ask on our side; the loser still had one"] += 1
            continue
        d, a = cb["deep"], cb["any"]
        if d is not None and d <= pinrun.PRICE_CEILING:
            buck["deep AND at or below 98c (blocked downstream)"] += 1
        elif d is not None and d <= 0.987:
            buck["deep, 98.0-98.7c"] += 1
        elif a is not None and a <= pinrun.PRICE_CEILING:
            buck["at or below 98c but under 10 deep"] += 1
        elif a is not None and a <= 0.987:
            buck["98.0-98.7c and under 10 deep"] += 1
        else:
            buck["dearer than 98.7c only"] += 1
    LEV = {"deep AND at or below 98c (blocked downstream)":
           "none -- a rail or the edge/EV/dump test refused it",
           "deep, 98.0-98.7c": "**PRICE_CEILING -> 0.987**",
           "at or below 98c but under 10 deep":
           "**MIN_FILL_FRAC (or SIZE)**",
           "98.0-98.7c and under 10 deep": "BOTH of the above",
           "dearer than 98.7c only": "EV_FLOOR / MEASURED_FLIP, not the "
                                      "ceiling",
           "no ask on our side, ever": "nothing -- LIQUIDITY",
           "no ask on our side; the loser still had one":
           "nothing -- LIQUIDITY (one-sided book)"}
    for lab, k in sorted(buck.items(), key=lambda kv: -kv[1]):
        W(f"| {lab} | {k} | {100.0*k/max(len(silent),1):.1f}% | "
          f"{LEV.get(lab,'')} |")
    W("")

    # ---- the MDE, before the estimates ----------------------------------
    W("## 2. The MDE, stated before the estimates")
    W("")
    sd0 = mean_sd([base.pnl.get(c, 0.0) for c in denom])[1]
    tc = tdist.crit(0.05, max(n - 1, 1))
    W(f"Per-close P&L at the base gate has sd **${sd0:.4f}** over {n} closes, "
      f"so the smallest change in $/close this window can distinguish from "
      f"zero at t={tc:.2f} is **${tc*sd0/math.sqrt(n):.4f}/close** on the "
      f"LEVEL.")
    W("")
    W("Every lever below is compared to the base on the SAME closes, so the "
      "relevant MDE is on the PAIRED difference, which is much smaller "
      "because the closes both configurations trade identically cancel. Each "
      "row carries its own paired MDE.")
    W("")

    def table(title, idxs, note=None):
        W(f"### {title}")
        W("")
        if note:
            W(note)
            W("")
        W("| config | floor | closes traded | fills | $/close (tape) | "
          "$/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |")
        W("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i in idxs:
            a = accs[i]
            st = per_close_stats(a, denom)
            d = paired_mde(a, base, denom)
            dp, dn = days_positive(a, denom)
            f_ = st["fills"]
            W(f"| {a.cfg.name} | {a.cfg.floor():g} | {st['closes_traded']} "
              f"({100.0*st['closes_traded']/n:.1f}%) | {f_:,} | "
              f"${st['per_close']:.4f} | ${st['ev_per_close']:.4f} | "
              f"{'$%.4f' % (st['pnl']/f_) if f_ else '--'} | "
              f"{st['mean_px']:.4f} | {dp}/{dn} | "
              f"{'--' if i == 0 else '$%+.4f' % d['diff']} | "
              f"{'--' if i == 0 else '$%.4f' % d['mde']} | "
              f"{'--' if i == 0 else '%+.1f' % d['t']} |")
        W("")
        W("Where the difference comes from -- **a COUNT lever must earn it on "
          "NEW closes**, and the three components sum to the paired "
          "difference exactly:")
        W("")
        W("| config | NEW closes | $ from new | closes LOST | $ lost | "
          "shared closes | extra fills on shared | $ change on shared |")
        W("|---|---|---|---|---|---|---|---|")
        for i in idxs:
            if i == 0:
                continue
            sp = split_diff(accs[i], base, denom)
            W(f"| {accs[i].cfg.name} | {sp['new_closes']} | "
              f"${sp['pnl_new']:+.2f} | {sp['lost_closes']} | "
              f"${sp['pnl_lost']:+.2f} | {sp['shared_closes']} | "
              f"{sp['extra_fills_shared']:+d} | ${sp['pnl_shared']:+.2f} |")
        W("")

    ceil_idx = [0] + [i for i, c in enumerate(cfgs)
                      if c.name.startswith("ceiling ")]
    tau_idx = [0] + [i for i, c in enumerate(cfgs)
                     if c.name.startswith("TAU_MAX ")]
    combo_idx = [0] + [i for i, c in enumerate(cfgs)
                       if "+" in c.name]

    W("## 3. The size question -- SCOPE: the floor, not the size")
    W("")
    W(f"`too_shallow` refuses an offer smaller than "
      f"max(MIN_LEVEL, MIN_FILL_FRAC x SIZE) = "
      f"{max(pinrun.MIN_LEVEL, pinrun.MIN_FILL_FRAC*size_live):g} contracts "
      f"at SIZE {size_live:g}. Two DIFFERENT levers lower that floor: cut "
      f"SIZE, which also cuts what we win on the deep books, or cut "
      f"MIN_FILL_FRAC, which keeps the maximum at {size_live:g} and only "
      f"allows a partial.")
    W("")
    _lv = os.path.join(os.path.dirname(out), "RESULTS_levels.md")
    W("**The authoritative SIZE table is `results/RESULTS_levels.md`** "
      "(`research/pinlevels.py`), a concurrent full-history job sweeping "
      "SIZE over all 422 book hours with hedge on and off and bootstrap "
      "intervals. A full-history sweep supersedes anything a 7-day window "
      "can say about SIZE, so the SIZE rows below are printed for continuity "
      "with the decomposition and **must not be quoted against it**. What "
      "THIS file owns is the `too_shallow` COUNT above -- whether size is "
      "even the binding constraint -- and the MIN_FILL_FRAC rows, which that "
      "job does not sweep."
      + ("" if os.path.exists(_lv) else
         " **As of this build `results/RESULTS_levels.md` does not exist on "
         "disk**, so the SIZE question is formally unanswered here; do not "
         "read the collapsed rows below as the answer."))
    W("")
    table("MIN_FILL_FRAC -- the floor alone, maximum size unchanged",
          [0] + [i for i, c in enumerate(cfgs) if "frac" in c.name
                 and c.size == size_live and "TAU" not in c.name])
    W("<details><summary>SIZE rows, for continuity only -- "
      "RESULTS_levels.md is authoritative</summary>")
    W("")
    table("SIZE (superseded by results/RESULTS_levels.md)",
          [0] + [i for i, c in enumerate(cfgs)
                 if c.name.startswith("SIZE ") and "frac" not in c.name])
    W("</details>")
    W("")

    W("## 4. The ceiling question")
    W("")
    W(f"PRICE_CEILING is {pinrun.PRICE_CEILING}. **Raising it alone cannot "
      f"work above ~{_ev_break():.3f}**, because pinrun's EV gate "
      f"(EV_FLOOR {pinrun.EV_FLOOR}, MEASURED_FLIP "
      f"{pinrun.MEASURED_FLIP}) refuses everything dearer: "
      + ", ".join(f"EV({p:.3f})={100*pinrun.expected_value(p):+.2f}c"
                  for p in (0.980, 0.985, 0.988, 0.990, 0.995))
      + f" against a floor of {100*pinrun.EV_FLOOR:.1f}c. The `noEV` rows "
        f"lift that gate to show what is THERE; they are not a proposal, "
        f"because the loss rate WE would suffer at 99c+ has never been "
        f"measured live -- we have never bought above "
        f"{pinrun.PRICE_CEILING}.")
    W("")
    W("**And the live loss rate cannot price this lever, which is the honest "
      "answer to \"use the live rate, not the tape rate\".** The live rate we "
      "have is at the CLOSE level -- 2 losses in 59 closes at the current "
      "gate, `results/SKIM.md` -- and it is not decomposable by price. If "
      "3.4% were applied flatly per fill, EV at 98.0c would be "
      f"{100*((1-0.034)*(1-0.98) - 0.034*0.98 - pinrun.billed_fee(0.98, 1)):+.2f}c "
      "per contract, i.e. every trade we take would lose money -- which is "
      "not what the live ledger records. So a flat rate is the wrong model, "
      "which is precisely why `MEASURED_FLIP` is estimated on DEAR trades "
      "only. **The consequence for this lever is that there is NO live loss "
      "rate above 98.0c at all, because we have never bought there.** Any "
      "ceiling above 98.7c is therefore an extrapolation and is not "
      "proposable from this file; the tape columns rank, they do not price.")
    W("")
    table("Ceiling", ceil_idx)
    table("Ceiling with the EV gate lifted (COUNT ONLY, NOT A PROPOSAL)",
          [0] + [i for i, c in enumerate(cfgs) if c.name.endswith("noEV")])

    # --- where the ceiling lever's money sits, and what breaks it ----------
    _c987 = next((i for i, c in enumerate(cfgs)
                  if c.name == "ceiling 0.987"), None)
    if _c987 is not None:
        a987 = accs[_c987]
        W("### The fills the ceiling lever ADDS, and the loss rate that "
          "flips their sign")
        W("")
        W("Every fill `ceiling 0.987` takes, by price. The rows above 98.0c "
          "are the ones the lever adds and they are the whole of its risk. "
          "**The loss column is the REPLAY's population, not ours** -- it is "
          "here to locate the money, not to price it.")
        W("")
        W("| price of the fill | fills | lost (replay) | total $ | $/fill | "
          "mean px |")
        W("|---|---|---|---|---|---|")
        for lo4, hi4, lab in ((0.0, 0.90, "<=90c"), (0.90, 0.95, "90-95c"),
                              (0.95, 0.97, "95-97c"), (0.97, 0.98, "97-98c"),
                              (0.98, 0.985, "**98.0-98.5c (new)**"),
                              (0.985, 0.987, "**98.5-98.7c (new)**")):
            xs = [b for b in a987.buys if lo4 < b[2] <= hi4]
            if not xs:
                continue
            W(f"| {lab} | {len(xs)} | {sum(1 for b in xs if not b[3])} | "
              f"${sum(b[4] for b in xs):+.2f} | "
              f"${sum(b[4] for b in xs)/len(xs):+.4f} | "
              f"{sum(b[2] for b in xs)/len(xs):.4f} |")
        W("")
        dear = [b for b in a987.buys if b[2] > pinrun.PRICE_CEILING]
        if dear:
            nd = len(dear)
            pxd = sum(b[2] for b in dear) / nd
            cnd = sum(b[5] for b in dear) / nd
            feed = sum(pinrun.billed_fee(b[2], b[5]) for b in dear) / nd
            real = sum(b[4] for b in dear)
            W(f"**{nd} fills above the {100*pinrun.PRICE_CEILING:.0f}c "
              f"ceiling, {sum(1 for b in dear if not b[3])} lost in the "
              f"replay, ${real:+.2f} realised.** At a mean {100*pxd:.2f}c on "
              f"{cnd:.1f} contracts, here is what the SAME fills are worth at "
              f"other loss rates -- the arithmetic the tape cannot settle, "
              f"because we have never bought above "
              f"{100*pinrun.PRICE_CEILING:.0f}c live and so have no live rate "
              f"at these prices:")
            W("")
            W("| loss rate on the dear fills | $/dear fill | total over this "
              "window |")
            W("|---|---|---|")
            for rate in (0.005, 0.01, 0.015, 0.02, 0.03, 0.05):
                e4 = (1 - rate) * cnd * (1 - pxd) - rate * cnd * pxd - feed
                W(f"| {100*rate:.1f}% | ${e4:+.4f} | ${e4*nd:+.2f} |")
            W("")
            W(f"The replay realised {100.0*sum(1 for b in dear if not b[3])/nd:.1f}% "
              f"here. The tape's loss rate on a population like this is "
              f"structurally ~31x too optimistic (0.11% tape vs 3.4% live at "
              f"the current gate, intervals that do not overlap). **Between "
              f"1% and 2% the lever changes sign.**")
            W("")

    W("## 5. The tau question, re-tested on the rebuilt replay")
    W("")
    W("Extending TAU_MAX was killed as 'dearer AND less accurate' on the OLD "
      "replay, which sampled once a second and applied every snapshot at ts 0. "
      "Re-measured here.")
    W("")
    W("Model accuracy by tau, from the replay -- what the model computed "
      "against what the market did, on every certain (market, second) moment. "
      "**This is a model-calibration statistic, not our loss rate**: its "
      "population is 'the model was certain', not 'someone sold it to us'.")
    W("")
    W("Reported twice. Market-seconds are the raw census; **MARKETS is the "
      "unit that means anything**, because seconds inside one market are not "
      "independent (one wrong call prints ~28 wrong seconds).")
    W("")
    W("| tau band | certain market-seconds | won | acc | certain MARKETS | "
      "won | acc | markets the model got WRONG |")
    W("|---|---|---|---|---|---|---|---|")
    for lo2 in sorted(x for x in (set(acc_tau) | set(acc_tau_mk))
                      if isinstance(x, int)):
        k, w = acc_tau.get(lo2, [0, 0])
        km, wm = acc_tau_mk.get(lo2, [0, 0])
        if not k and not km:
            continue
        W(f"| {lo2}-{lo2+4}s | {k:,} | {w:,} | "
          f"{(100.0*w/k) if k else 0:.3f}% | {km:,} | {wm:,} | "
          f"{(100.0*wm/km) if km else 0:.2f}% | {km - wm} |")
    W("")
    W("**The same thing in AMENDMENT 4's own bands, which is the number that "
      "killed this lever.** pinrun's comment records, at the OLD gate "
      "PIN=0.98: tau 3-10 575 moments 0 flips; 11-20 1,772 / 0; 21-30 2,872 "
      "/ 0; 31-45 7,302 / 25 (3.7x overconfident); 46-60 10,047 / 126 "
      "(10.9x). The gate is now 0.995, so the population is not the same one "
      "and the comparison is of TODAY'S gate against that wall.")
    W("")
    W("| tau band | certain market-seconds | flips | flip rate | "
      "certain MARKETS | markets the model got WRONG | market flip rate | "
      "95% CI on the market rate |")
    W("|---|---|---|---|---|---|---|---|")
    for lab in ("3-10", "11-20", "21-30", "31-45", "46-60"):
        k, w = acc_tau.get("A4 " + lab, [0, 0])
        km, wm = acc_tau_mk.get("A4 " + lab, [0, 0])
        if not k and not km:
            continue
        lo3, hi3 = cp_interval(km - wm, km) if km else (0.0, 0.0)
        W(f"| {lab}s | {k:,} | {k - w:,} | "
          f"{(100.0*(k-w)/k) if k else 0:.4f}% | {km:,} | {km - wm:,} | "
          f"{(100.0*(km-wm)/km) if km else 0:.3f}% | "
          f"[{100*lo3:.3f}, {100*hi3:.3f}] |")
    W("")
    W("**And what the extra fills actually cost, which is the other half of "
      "the old kill (\"dearer AND less accurate\").** Every fill the widest "
      "configuration takes, grouped by the tau it was taken at. If the long "
      "horizon were dearer, the price column would rise with tau.")
    W("")
    W("| tau of the fill | fills | mean price | tape wins | tape $/fill | "
      "mean contracts |")
    W("|---|---|---|---|---|---|")
    _wide = accs[_t60] if _t60 is not None else base
    _bb = defaultdict(list)
    for _cs, tau_, px_, won_, pnl_, n_ in _wide.buys:
        _bb["3-10" if tau_ <= 10 else "11-20" if tau_ <= 20 else
            "21-30" if tau_ <= 30 else "31-45" if tau_ <= 45
            else "46-60"].append((px_, won_, pnl_, n_))
    for lab in ("3-10", "11-20", "21-30", "31-45", "46-60"):
        rws = _bb.get(lab)
        if not rws:
            continue
        W(f"| {lab}s | {len(rws):,} | "
          f"{sum(r[0] for r in rws)/len(rws):.4f} | "
          f"{sum(1 for r in rws if r[1]):,} | "
          f"${sum(r[2] for r in rws)/len(rws):+.4f} | "
          f"{sum(r[3] for r in rws)/len(rws):.1f} |")
    W("")
    table("TAU_MAX", tau_idx)
    table("Combinations", combo_idx)

    # ---- holdout ---------------------------------------------------------
    W("## 6. The holdout -- first 70% / last 30% of closes")
    W("")
    W(f"Chronological split of the {n} certain closes: "
      f"**{len(train)} train** "
      f"({time.strftime('%m-%dT%H', time.gmtime(train[0]))} .. "
      f"{time.strftime('%m-%dT%H', time.gmtime(train[-1]))}) and "
      f"**{len(hold)} holdout** "
      f"({time.strftime('%m-%dT%H', time.gmtime(hold[0]))} .. "
      f"{time.strftime('%m-%dT%H', time.gmtime(hold[-1]))}). "
      f"Nothing is a survivor unless the paired difference holds in the "
      f"holdout.")
    W("")
    _sb1 = per_close_stats(base, train)
    _sb2 = per_close_stats(base, hold)
    W(f"**READ THE POWER BEFORE THE TABLE.** The BASE gate itself earns "
      f"${_sb1['per_close']:.4f}/close in the train half and "
      f"${_sb2['per_close']:.4f} in the holdout -- it trades the same share "
      f"of closes in both ({100.0*_sb1['closes_traded']/max(len(train),1):.1f}% "
      f"vs {100.0*_sb2['closes_traded']/max(len(hold),1):.1f}%) and pays the "
      f"same mean price ({_sb1['mean_px']:.4f} vs {_sb2['mean_px']:.4f}), so "
      f"the COUNT is stable and it is the OUTCOMES in the holdout window that "
      f"are worse: {_sb2['lost_fills']} of {_sb2['fills']} replayed fills "
      f"lost there against {_sb1['lost_fills']} of {_sb1['fills']} in the "
      f"train half. **That is the replay's own population, not ours, and it "
      f"is not a loss rate for us** (CLAUDE.md 2026-09-10 rule 5) -- it is "
      f"quoted only to explain the variance. The consequence is that the "
      f"holdout's per-close sd RISES to ${_sb2['sd']:.4f}, so its MDEs are "
      f"5-20x the base's own holdout level and **every 'fails in the holdout' "
      f"below is NO POWER, not NO EFFECT**. The holdout can refute a lever "
      f"that is large; it cannot confirm or deny one worth a few cents a "
      f"close.")
    W("")
    W("| config | train closes traded | train $/close | train diff | "
      "hold closes traded | hold $/close | hold diff | hold MDE | hold t | "
      "hold NEW closes | hold $ from new |")
    W("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, a in enumerate(accs):
        st1 = per_close_stats(a, train)
        st2 = per_close_stats(a, hold)
        d1 = paired_mde(a, base, train)
        d2 = paired_mde(a, base, hold)
        sp2 = split_diff(a, base, hold)
        W(f"| {a.cfg.name} | {st1['closes_traded']} | "
          f"${st1['per_close']:.4f} | "
          f"{'--' if i == 0 else '$%+.4f' % d1['diff']} | "
          f"{st2['closes_traded']} | ${st2['per_close']:.4f} | "
          f"{'--' if i == 0 else '$%+.4f' % d2['diff']} | "
          f"{'--' if i == 0 else '$%.4f' % d2['mde']} | "
          f"{'--' if i == 0 else '%+.1f' % d2['t']} | "
          f"{'--' if i == 0 else sp2['new_closes']} | "
          f"{'--' if i == 0 else '$%+.2f' % sp2['pnl_new']} |")
    W("")
    W(f"With {len(accs) - 1} levers on the table, the multiple-looks bar at "
      f"5% two-sided is |t| >= "
      f"{_bonf(len(accs) - 1, len(hold)):.2f} in the holdout, not 2.0.")
    W("")

    # ---- the machine-readable summary ------------------------------------
    summ = {"hours": hours, "days": sorted(days), "closes_seen":
            len(all_closes), "closes_certain": n, "gate": gate_line(),
            "decomp_market": dict(base.reasons),
            "decomp_close": dict(cr),
            "tau_accuracy": {str(k): acc_tau[k]
                             for k in sorted(acc_tau, key=str)},
            "tau_accuracy_markets": {str(k): acc_tau_mk[k]
                                     for k in sorted(acc_tau_mk, key=str)},
            "census": dict(cen), "silent_buckets": dict(buck),
            "closes_certain_live_band": n30,
            "configs": []}
    for a in accs:
        st = per_close_stats(a, denom)
        d = paired_mde(a, base, denom)
        dh = paired_mde(a, base, hold)
        summ["configs"].append(
            {"name": a.cfg.name, "size": a.cfg.size,
             "ceiling": a.cfg.ceiling, "tau_max": a.cfg.tau_max,
             "min_fill_frac": a.cfg.min_fill_frac, "ev_gate": a.cfg.ev_gate,
             "floor": a.cfg.floor(), "stats": st, "paired": d,
             "paired_holdout": dh,
             "split": split_diff(a, base, denom),
             "split_holdout": split_diff(a, base, hold),
             "days_positive": days_positive(a, denom),
             "train": per_close_stats(a, train),
             "holdout": per_close_stats(a, hold)})
    with open(out + ".json", "w", encoding="utf-8") as fh:
        json.dump(summ, fh, indent=1)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    say(f"  wrote {out} and {out}.json")
    for ln in L:
        say(ln)
    return summ


def _ev_break():
    """The highest price whose EV still clears EV_FLOOR."""
    p = 0.999
    while p > 0.90:
        if pinrun.expected_value(p) >= pinrun.EV_FLOOR:
            return p
        p = round(p - 0.0005, 4)
    return 0.0


def _bonf(k, n):
    """Two-sided 5% t critical value after k looks (Bonferroni)."""
    # tdist gives 5% two-sided; approximate the k-look bar by the normal
    # quantile ratio, which is conservative for n >= 30.
    from statistics import NormalDist
    z1 = NormalDist().inv_cdf(1 - 0.025)
    zk = NormalDist().inv_cdf(1 - 0.025 / max(k, 1))
    base_t = tdist.crit(0.05, max(n - 1, 1))
    return base_t * zk / z1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pass1", action="store_true",
                    help="iterate the tape and write cell files")
    ap.add_argument("--report", action="store_true",
                    help="read cell files and write RESULTS_count.md")
    ap.add_argument("--gaps", action="store_true",
                    help="count the collector's own `_seq_gap` flags over the "
                         "window (a raw substring scan, ~2.3s/hour)")
    ap.add_argument("--hours", type=int, default=168)
    ap.add_argument("--end", default=None)
    ap.add_argument("--size", type=float, default=20.0,
                    help="the LIVE size the base gate runs at")
    ap.add_argument("--cells", default=CELLS)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results",
                                                  "RESULTS_count.md"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    pinrun.SIZE = a.size
    if a.pass1:
        pass1(a.hours, a.end, a.cells)
    if a.gaps:
        count_gaps(a.hours, a.end, a.cells)
    if a.report:
        stamps = set(pinsim.book_hours(a.hours, a.end))
        report(a.cells, a.size, os.path.abspath(a.out), stamps=stamps)
    if not (a.pass1 or a.report or a.gaps):
        print("nothing to do -- pass --pass1, --gaps and/or --report")


if __name__ == "__main__":
    main()
