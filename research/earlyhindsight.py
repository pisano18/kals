#!/usr/bin/env python3
"""earlyhindsight.py -- the 31-45 s "early" leg at a THIRD, at FULL size, or
OFF: which would have made the most money, scored close by close.

    python research/earlyhindsight.py --selftest
    python research/earlyhindsight.py                  # read-only, real data

WHY THIS EXISTS

2026-09-22 11:42:12Z (v-early-third) the live bot's early leg went from full
size back to a third (--early-frac 1.0 -> 0.333). The operator: *"Cut it to a
third but measure which would have been the best idea in hindsight."* This is
that measurement. It is run again as closes accumulate; nothing here changes
what the bot does.

WHAT IT MEASURES, PER CLOSE (n = closes, never trades or markets)

  LIVE   what Kalshi's ledger says the pin markets made in that close
         (pinledger.pnl; a hedged market is ONE row). The money authority.
         The bot's own `realised` is never read -- the logs miss every market
         held when a run died, and the ledger does not.
  THIRD  LIVE with every early-leg entry resized to 0.333 x SIZE.
  FULL   LIVE with every early-leg entry resized to 1.0 x SIZE, CAPPED at what
         was offered at that second (below).
  OFF    LIVE minus every early-leg entry and its share of the hedge.

Every policy is LIVE plus a DELTA computed from the bot's own order records,
so a market the logs never saw is identical in every column, and at the
actual size the delta is exactly zero (the self-test checks both).

HOW AN EARLY ENTRY IS RESIZED

* Contracts. Scaling DOWN: min(actual fill, frac x SIZE x band multiple).
  Scaling UP: min(frac x SIZE x band multiple, depth, close budget left),
  never below what actually filled unless the budget forces it. Depth is the larger of the touch size in
  the `signal` record and the tapered sweep depth in the `sweep_depth` record
  (`ladder`) -- exactly the two numbers the bot sizes an order from
  (pinrun: take_n = min(SIZE, touch, left); swept to min(SIZE, _deep, room)).
  An order that filled less than it asked (IOC partial) proves the depth at
  landing was the fill, so FULL cannot exceed it. No signal record -> no
  depth -> the fill is flagged UNCAPPED and counted as an upper bound.
* Price. Each extra (or removed) contract is priced along the ladder logged in
  the signal record at the decision second (levels at or under the order's
  own limit), plus the taker fee 0.07 p (1-p), and the whole curve is shifted
  by one constant per fill so that at the actual size it reproduces the
  actual cost exactly (the book moves in the ~100 ms before an order lands;
  the shift carries that move to the extra contracts too).
* Top-ups. pinrun's staged_take() completes a market to SIZE x mult at
  <= 30 s. At FULL the early leg already holds SIZE, so a later top-up is
  trimmed to what is left: min(actual, SIZE x mult - held, budget left).
* Hedge. The ledger's opposite-side contracts are the hedge; its P&L is
  payout - cost - fee from the ledger. The share attributable to the early
  position is (early contracts held at the first hedge fill) / (all entry
  contracts held then). Under a policy the hedge is resized in proportion to
  the policy's position at that second. Scaling UP is capped only where the
  depth is actually known: pinrun.hedge_depth logs ladder_n = max(touch,
  min(ladder, unhedged)), so an attempt whose ladder_n came in UNDER what it
  asked shows the real depth (cap = sum of ladder_n - filled over attempts);
  at or over it, nothing past `asked` was ever read and FULL's hedge is
  uncapped and flagged as an UPPER bound. Extra hedge contracts are priced
  at the market's average hedge price (a deeper hedge would pay more).
* Close budget. Every leg in a close is replayed in time order. A leg's room
  is the `budget_left` the bot logged at that signal (v-safety1 onward) less
  whatever the policy has already spent beyond the actual; before
  v-safety1 it is pinrun.close_budget_for rebuilt from the start record
  (MAX_PER_CLOSE x SIZE, the extra-coin and last-seconds allowances). So a
  FULL early leg SHRINKS a later leg of the same or another market exactly
  as the bot would (`later_leg_squeezed`, modelled).
* Side. Order records before ~09-21 carry no `want`; the body's Kalshi book
  side is read instead ('bid' = buy YES, 'ask' = buy NO). A first run
  without this read every older order as side None and booked THIRD
  +$3,482 / OFF +$6,578 on 205 closes; the ledger-vs-logs line (section E)
  is what caught it, and the self-test now pins the old shape.
* A market a policy removes entirely is exactly $0 (nothing bought, nothing
  hedged); the logs-vs-ledger fee rounding dropped with it is reported. A
  losing close is one under -$0.005.
* Moved fills, by direction. The reference is what the LOGGED decision-time
  ladder says a fill of that size costs (so an intended sweep up the ladder
  is not a move). An early fill landing >= 2c UNDER it is a PRICE-THROUGH
  (critic C6: the book collapsed in the ~100 ms before the order hit); >= 2c
  OVER it is DEARER. The landing book's depth was never logged, so FULL
  holds a price-through fill at the count that actually filled (like an IOC
  partial) -- it does not price extra contracts at a collapsed landing price.
  The two other readings are reported beside it: extra contracts at the
  landing price (the old shift) and at the decision-time book.
* FULL-lo, the conservative bound B1 must also pass. On every market whose
  FULL number rests on something nobody logged -- a price-through or dearer
  early fill, no logged depth, contracts priced past the logged ladder, or a
  hedge scaled up (priced at the market's average hedge price) -- FULL-lo
  takes the WORST of the three price readings and zero. Elsewhere FULL-lo ==
  FULL. OFF and THIRD only remove contracts that really filled.

WHAT IT DOES NOT MODEL (and counts, so the reader can see how often it bites)

* A SMALLER early leg freeing budget: the close_budget gate refused markets
  the bot never even priced (it fires before the book is read). Counted per
  policy: a refusal counts for THIRD only if the early contracts a third-size
  leg would NOT have bought (held x (1 - 0.333/frac as run)) plus the budget
  left reach one contract; for OFF, all early contracts held before it.
  Likewise later legs the budget bound as run (`room_bound_as_run`).
* OFF does not hand a market to the <=30 s window. The critic measured that
  163 of 203 early-leg markets were never offered at 90-98c later (tape), so
  OFF mostly loses them; where a top-up exists OFF keeps only the top-up,
  which is a lower bound for OFF on those markets (counted).
* THIRD in the calibration era cannot add top-ups the full-size bot never
  sent; it is a lower bound where the later window had depth.
* max_per_market: FULL buys in one fill where live used two, freeing a slot
  a late boost could use (counted). Hedge timing, the loss-cap/brake state,
  and any change in which market a scan picks.

STATUS. REPORT ONLY -- this page never names a winner. A first version
printed CALLED when a policy cleared its MDE with bootstrap P outside
[0.05, 0.95] after 30 early-leg closes, re-checked on every run. Review
(2026-09-22) fed it the real pre-freeze sequences re-scored at a third: it
read "FULL BEATS LIVE" at its very first eligible look, and in a null world
with the real loss tail it called FULL 36-50% of the time -- the leg's money
is many small wins and a rare large loss, so 30 closes often hold no loss
and the spread looks tiny. The ONE decision is FREEZE bar B1
(research/barcheck.py, results/FREEZE_bars.json): a fixed first 300 watched
closes, one look, effect floors, P >= 0.975, FULL on FULL-lo too. B1 reads
this file through freeze_rows(). P values are not printed below 30 closes.

UNITS. The tables count TRADED closes (a pin ledger row exists). B1 counts
WATCHED closes (the bot logged a close_summary, or Kalshi settled a pin
market there) -- about 2.8x as many. "Closes needed" lines are in watched
closes so they read against B1 directly.

SOURCES AND LABELS. Ledger (money) > live order records (sizes, prices, the
logged book) > paper arms. FULL's extra contracts are a counterfactual priced
on the book the bot logged, not a fill. The paper-arm section is labelled
paper -- hypothesis. No tape, no replay.

NOTHING HERE PLACES AN ORDER, WRITES OUTSIDE THIS REPO'S results/, OR READS
THE NETWORK.
"""
import argparse
import calendar
import collections
import glob
import hashlib
import json
import math
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinledger                                                  # noqa: E402
import pinday                                                     # noqa: E402
from downtime import et_offset                                    # noqa: E402

LIVE_RESULTS = r"C:\kals-repo\results"
OUT_MD = os.path.join(os.path.dirname(HERE), "results", "EARLY_HINDSIGHT.md")

DEPLOY = "2026-09-22T11:42:12Z"          # v-early-third, results/VERSIONS.md
CAL_FROM = "2026-09-17T13:05:02Z"        # first live run with the 45 s leg
FIXES_FROM = "2026-09-20T04:00:00Z"      # 09-20 00:00 ET, PROJECT_MAP "since the fixes"
THIRD, FULL = 0.333, 1.0
FEE_RATE = 0.07
MOVED = 0.02            # a fill >= 2c from what its logged book said (critic C6)
LOSS = -0.005           # a losing close: under minus half a cent (rounding is not a loss)
Z80 = 1.959964 + 0.841621                # two-sided 5 %, 80 % power
B_BOOT = 10000
FLOOR = 30              # CLAUDE.md: floor cluster counts; no P value is printed below it
# markets whose FULL number rests on something nobody logged (FULL-lo's set)
UNLOGGED = ("through", "dearer", "uncapped", "past_ladder", "hedge_up")

# pinrun.SERIES_TO_INDEX keys: the up/down series the pin bot trades. The
# coin race (KXCRYPTOLEAD15M) and commodity bots (KXWTI15M, KXGOLD15M, ...)
# share the ledger and are NOT this strategy.
PIN_SERIES = frozenset([
    "KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M",
    "KXBCH15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M", "KXADA15M"])

_MON = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
_TK = re.compile(r"^(KX[A-Z0-9]+)-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-")


# ---------------------------------------------------------------- small utils
def iso_ep(s):
    try:
        return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def ep_iso(e):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e))


def series_of(tk):
    return str(tk or "").split("-")[0]


def close_ep_of_ticker(tk):
    """UTC epoch of the close encoded (in ET) in a ticker, or None."""
    m = _TK.match(str(tk or ""))
    if not m or m.group(3) not in _MON:
        return None
    _s, yy, mon, dd, hh, mi = m.groups()
    local = calendar.timegm((2000 + int(yy), _MON[mon], int(dd), int(hh), int(mi), 0))
    return int(local - et_offset(local + 4 * 3600))


def et_day(close_ep):
    return pinday.et_day_of_epoch(close_ep)


def fee_pc(p, rate=FEE_RATE):
    p = float(p)
    return rate * p * (1.0 - p)


def band_mult(price, bands):
    m = 1.0
    for b in bands or ():
        try:
            lo, hi, mult = float(b[0]), float(b[1]), float(b[2])
        except (TypeError, ValueError, IndexError):
            continue
        if lo <= float(price) < hi:
            m = max(m, mult)
    return m


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def losing(v):
    """A losing close: under minus half a cent (fee rounding is not a loss)."""
    return v < LOSS


def code_sha256(path=None):
    """sha256 of this scorer's source with CRLF read as LF, so a Windows
    checkout and a Unix one hash the same. FREEZE bar B1 pins this value:
    an edit to the scorer after registration makes B1 INVALID until the
    edit is registered as a dated amendment."""
    p = path or os.path.abspath(__file__)
    try:
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------- loading
def load_ledger(path):
    return ledger_from_rows(pinledger.load_cache(path))


def ledger_from_rows(rows):
    """{ticker: {'pnl', 'result', 'yes_n', 'no_n', 'yes_c', 'no_c', 'fee'}}
    for pin series only, from raw Kalshi settlements. A ticker settled twice
    is summed. The self-test goes through this same function."""
    out = {}
    for s in rows.values():
        tk = s.get("ticker") or ""
        if series_of(tk) not in PIN_SERIES:
            continue
        r = out.setdefault(tk, {"pnl": 0.0, "result": None, "yes_n": 0.0,
                                "no_n": 0.0, "yes_c": 0.0, "no_c": 0.0, "fee": 0.0,
                                "settled": None})
        r["pnl"] += pinledger.pnl(s)
        r["result"] = str(s.get("market_result") or "").strip().lower() or r["result"]
        r["yes_n"] += pinledger.money(s, "yes_count_fp")
        r["no_n"] += pinledger.money(s, "no_count_fp")
        r["yes_c"] += pinledger.money(s, "yes_total_cost_dollars")
        r["no_c"] += pinledger.money(s, "no_total_cost_dollars")
        r["fee"] += pinledger.money(s, "fee_cost")
        r["settled"] = max(r["settled"] or "", s.get("settled_time") or "")
    return out


def read_jsonl(path):
    out = []
    try:
        fh = open(path, encoding="utf-8")
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                out.append(r)
    return out


KEEP = ("start", "autosize", "signal", "sweep_depth", "order", "hedge",
        "refused", "close_summary", "settled")
BOUND_GATES = ("close_budget", "max_per_market")


def load_live_runs(results_dir, since_iso):
    """[[record, ...] per live run], only runs whose file stamp is >= a day
    before `since_iso` (a run can start before the window and trade into it)."""
    runs = []
    floor = (iso_ep(since_iso) or 0) - 86400
    for p in sorted(glob.glob(os.path.join(results_dir, "pinrun-live-*.jsonl"))):
        m = re.search(r"(\d{8}T\d{6}Z)", os.path.basename(p))
        if m:
            e = iso_ep(m.group(1)[:4] + "-" + m.group(1)[4:6] + "-" + m.group(1)[6:8]
                       + "T" + m.group(1)[9:11] + ":" + m.group(1)[11:13] + ":"
                       + m.group(1)[13:15])
            if e is not None and e < floor:
                continue
        recs = []
        for r in read_jsonl(p):
            k = r.get("kind")
            if k not in KEEP:
                continue
            if k == "refused" and r.get("gate") not in BOUND_GATES:
                continue
            if k == "signal":
                r = dict(r)
            recs.append(r)
        if recs:
            runs.append({"path": p, "recs": recs})
    return runs


def extract(runs):
    """Fills (entry legs), hedge fills, and budget evidence from live runs.

    Each entry fill carries the run's config at that moment: early fraction
    (0 when the early leg was off), SIZE (autosize trail), band multiples,
    late window, close budget settings, the budget the bot itself logged as
    left for that candidate (`budget_left`, v-safety1 on), and the book the
    bot logged. Refusals are the close_budget and max_per_market gates --
    the two bounds a resized early leg could change."""
    fills, hedges, refusals = [], [], []
    seen_oid = set()
    for run in runs:
        cfg = {}
        size = None
        sig_by = {}
        sd_by = {}
        sig_hist = collections.defaultdict(list)
        for r in run["recs"]:
            k = r.get("kind")
            if k == "start":
                cfg = r
                size = fnum(r.get("size"), size)
                continue
            if k == "autosize":
                size = fnum(r.get("new"), size)
                continue
            if k == "signal":
                sig_by[(r.get("ticker"), r.get("t"))] = r
                sig_hist[r.get("ticker")].append(r)
                continue
            if k == "sweep_depth":
                sd_by[(r.get("ticker"), r.get("t"))] = r
                continue
            if k == "refused":
                ce = fnum(r.get("close_s")) or close_ep_of_ticker(r.get("ticker"))
                if ce:
                    refusals.append({
                        "gate": r.get("gate"), "ticker": r.get("ticker"),
                        "close": int(ce), "t": iso_ep(r.get("t")),
                        "tau": fnum(r.get("tau")),
                        "bleft": (fnum(r.get("budget_left")) if r.get("budget_left")
                                  is not None else
                                  (fnum(r.get("budget")) - fnum(r.get("spent"))
                                   if fnum(r.get("budget")) is not None
                                   and fnum(r.get("spent")) is not None else None)),
                        "size": fnum(r.get("size_now"), size)})
                continue
            if k == "hedge":
                n = fnum(r.get("n"), 0.0) or 0.0
                if n > 0 and r.get("live", True) is not False:
                    hedges.append({
                        "ticker": r.get("ticker"), "t": iso_ep(r.get("t")),
                        "side": r.get("side"), "n": n, "price": fnum(r.get("price")),
                        # pinrun.hedge_depth: ladder_n = max(touch, min(ladder,
                        # unhedged)). Below `asked` it is the real depth; at or
                        # above it the depth past `asked` was never read.
                        "ladder_n": fnum(r.get("ladder_n")),
                        "ask_size": fnum(r.get("ask_size")),
                        "asked": fnum(r.get("asked"))})
                continue
            if k != "order":
                continue
            filled = fnum(r.get("filled"), 0.0) or 0.0
            if filled <= 0:
                continue
            oid = r.get("order_id") or (r.get("ticker"), r.get("t"), filled)
            if oid in seen_oid:
                continue
            seen_oid.add(oid)
            tk = r.get("ticker")
            t = iso_ep(r.get("t"))
            sig = sig_by.get((tk, r.get("t")))
            if sig is None:                          # the second may have ticked
                for s in reversed(sig_hist.get(tk, [])):
                    st = iso_ep(s.get("t"))
                    if st is not None and t is not None and t - 3 <= st <= t:
                        sig = s
                        break
            sd = sd_by.get((tk, r.get("t")))
            etm = fnum(cfg.get("early_tau_max"), 30) or 30
            tmax = fnum(cfg.get("tau_max"), 30) or 30
            ef = fnum(cfg.get("early_frac"), 0.0) if etm > tmax else 0.0
            tau = fnum(r.get("tau_at_send"), fnum((sig or {}).get("tau")))
            leg = r.get("leg")
            if not leg:            # pre-A46 records carry no leg: infer it
                leg = "early" if (ef and tau is not None and tau > tmax) else "full"
            body = r.get("body") or {}
            want = side_of_order(r, sig)
            count = fnum(body.get("count"), filled)
            px = fnum(r.get("exec_price"))
            if px is None:
                px = fnum(r.get("limit_sent"), fnum(r.get("ask_seen"), 0.0))
            fee_total = fnum(r.get("fee_total"))
            if fee_total is None:
                fee_total = filled * fee_pc(px)
            limit = fnum(r.get("limit_sent"), fnum((sig or {}).get("price"), px))
            ladder = None
            if sig is not None and isinstance(sig.get("ladder"), list):
                ladder = sorted((float(a), float(b)) for a, b in sig["ladder"]
                                if fnum(a) is not None and fnum(b) is not None
                                and float(a) <= (limit or 1.0) + 1e-9 and float(b) > 0)
            sig_px = fnum((sig or {}).get("price"), px)
            # what the LOGGED decision-time book said a fill of this size costs:
            # an intended sweep up the ladder is not a move
            exp_px = ladder_avg(ladder, filled) if ladder else sig_px
            move = None
            if sig is not None and exp_px is not None and px is not None:
                if px <= exp_px - MOVED + 1e-9:
                    move = "through"          # landed well UNDER the logged book
                elif px >= exp_px + MOVED - 1e-9:
                    move = "dearer"           # landed well OVER it
            fills.append({
                "ticker": tk, "close": close_ep_of_ticker(tk), "t": t,
                "leg": leg, "want": want,
                "filled": filled, "count": count, "px": px, "fee_total": fee_total,
                "limit": limit, "tau": tau,
                "sig_price": sig_px, "exp_px": exp_px, "move": move,
                "touch": fnum((sig or {}).get("size")) if sig is not None else None,
                "sd_ladder": fnum((sd or {}).get("ladder")) if sd is not None else None,
                "bleft": fnum((sig or {}).get("budget_left")) if sig is not None else None,
                "ladder": ladder, "has_sig": sig is not None,
                "partial": filled < (count or filled) - 0.01,
                "ef": ef, "SIZE": size or fnum(cfg.get("size"), 20.0),
                "bands": cfg.get("band_mults") or [],
                "late_tau": fnum(cfg.get("late_tau"), 0) or 0,
                "late_mult": fnum(cfg.get("late_mult"), 1.0) or 1.0,
                "mpc": fnum(cfg.get("max_per_close"), 2) or 2,
                "extra": fnum(cfg.get("extra_coin"), 0.0) or 0.0,
                "late_extra": fnum(cfg.get("late_extra"), 0.0) or 0.0,
                "late_extra_tau": fnum(cfg.get("late_extra_tau"), 0.0) or 0.0,
                "run": os.path.basename(run["path"])})
    fills.sort(key=lambda f: (f["t"] or 0))
    hedges.sort(key=lambda h: (h["t"] or 0))
    refusals.sort(key=lambda x: (x["t"] or 0))
    return fills, hedges, refusals


# ---------------------------------------------------------------- pricing
def ladder_avg(ladder, n):
    """Average price (no fee) of n contracts walked up a logged ladder; past
    its end, the last level. None without a ladder or n."""
    if not ladder or not n or n <= 0:
        return None
    tot, left, last = 0.0, float(n), None
    for p, q in ladder:
        if left <= 1e-12:
            break
        take = min(q, left)
        tot += take * p
        left -= take
        last = p
    if left > 1e-12:
        tot += left * last
    return tot / float(n)


def cost_curve(fill, fee_rate=FEE_RATE, mode="shift"):
    """cost(n) in dollars incl. fee for n contracts of this fill, anchored so
    cost(actual filled) == actual cost exactly.

    mode "shift": the whole logged ladder is moved by one constant per
    contract so it reproduces the actual cost -- extra contracts carry the
    fill's own price move (for a price-through fill: the collapsed landing
    price). mode "add": contracts up to the actual count cost what they
    cost; EXTRA contracts are priced on the logged decision-time ladder with
    no move (the book the bot decided on)."""
    n_act = fill["filled"]
    actual = fill["px"] * n_act + fill["fee_total"]
    lv = fill.get("ladder") or []

    def walk(n):
        tot, left, last = 0.0, float(n), None
        for p, q in lv:
            if left <= 1e-12:
                break
            take = min(q, left)
            tot += take * (p + fee_pc(p, fee_rate))
            left -= take
            last = p
        if left > 1e-12:          # beyond the logged ladder: last level (or the fill's avg)
            p = last if last is not None else fill["px"]
            tot += left * (p + fee_pc(p, fee_rate))
        return tot

    if not lv or n_act <= 0:
        per = actual / n_act if n_act > 0 else 0.0
        return lambda n: per * n
    shift = (actual - walk(n_act)) / n_act
    if mode == "add":
        base = walk(n_act)
        return lambda n: (walk(n) + shift * n) if n <= n_act else (actual + walk(n) - base)
    return lambda n: walk(n) + shift * n


def side_of_order(r, sig=None):
    """'yes' or 'no' for an entry order. Newer records say `want`; older ones
    (every order before ~09-21) do not, and the body's `side` is Kalshi's
    book side: 'bid' buys YES at `price`, 'ask' sells YES at `price` = buys
    NO at 1 - price. A 2026-09-22 run without this read every older order as
    side None and booked THIRD +$3,482 / OFF +$6,578 on 205 closes."""
    w = r.get("want") or (sig or {}).get("want")
    if w in ("yes", "no"):
        return w
    bs = str((r.get("body") or {}).get("side") or "").lower()
    if bs in ("yes", "no"):
        return bs
    return {"bid": "yes", "ask": "no"}.get(bs)


def win_of(side, result):
    return 1.0 if side and result and side == result else 0.0


# ---------------------------------------------------------------- the policies
def budget_for(f, held_coins):
    """pinrun.close_budget_for, rebuilt from the run's start record. Used only
    where the bot did not log `budget_left` itself (every run before
    v-safety1). `held_coins` = coins already bought in this close; pinrun's
    `prev is None` is an empty set here."""
    size = f["SIZE"]
    base = f["mpc"] * size
    coin = series_of(f["ticker"])
    extra = f.get("extra") or 0.0
    lx = f.get("late_extra") or 0.0
    if lx and f["tau"] is not None and f["tau"] <= (f.get("late_extra_tau") or 0.0):
        extra = max(extra, lx)
        if not held_coins or coin in held_coins:
            return base + lx * size
    if not extra or not held_coins or coin in held_coins:
        return base
    return base + extra * size


def resize_close(fills, g, stats=None, through="cap"):
    """{fill index: policy contracts} for the fills of ONE close, in time
    order, at early fraction g (None = actual).

    through="cap" (the default, FULL's headline): a price-through early fill
    is never scaled past what filled -- the landing book's depth was not
    logged. "landing" / "decision" lift that cap so score() can price the
    extra contracts both ways for FULL-lo.

    The close budget binds every leg under the policy exactly as it bound the
    bot: the room for a fill is the `budget_left` the bot logged at that
    signal less whatever the policy has ALREADY spent beyond the actual
    (v-safety1 onward), or pinrun.close_budget_for rebuilt from the start
    record less the policy's spend (before it). So a FULL early leg can shrink
    a later leg of another market in the same close -- modelled, and tallied
    as `later_leg_squeezed`."""
    out = {}
    spent_pol = spent_act = 0.0
    coins_pol, coins_act = set(), set()
    held_mkt = collections.defaultdict(float)
    st = stats if stats is not None else collections.Counter()
    for i, f in sorted(fills, key=lambda x: (x[1]["t"] or 0)):
        n_act = f["filled"]
        size = f["SIZE"]
        coin = series_of(f["ticker"])
        logged = f.get("bleft") is not None
        if logged:
            room_act = f["bleft"]
            room = f["bleft"] - (spent_pol - spent_act)
        else:
            room_act = budget_for(f, coins_act) - spent_act
            room = budget_for(f, coins_pol) - spent_pol
        room = max(0.0, room)
        same = g is None or abs(g - f["ef"]) < 1e-9
        n = n_act
        if f["leg"] == "early" and not same:
            if g <= 0:
                n = 0.0
            else:
                cap = g * size * band_mult(f["sig_price"] or f["px"], f["bands"])
                if g < f["ef"]:
                    n = min(n_act, cap, room)
                else:
                    depth = None
                    if f["touch"] is not None or f["sd_ladder"] is not None:
                        depth = max(f["touch"] or 0.0, f["sd_ladder"] or 0.0)
                    else:
                        st["uncapped"] += 1
                    if f["partial"]:
                        depth = n_act if depth is None else min(depth, n_act)
                        st["partial_cap"] += 1
                    if f.get("move") == "through" and through == "cap":
                        depth = n_act if depth is None else min(depth, n_act)
                        st["through_cap"] += 1
                    want = cap if depth is None else min(cap, depth)
                    want = max(want, n_act)
                    if depth is not None and depth < cap - 1e-9:
                        st["depth_cap"] += 1
                    n = max(0.0, min(want, room))
                    st["scaled_up"] += 1
                    st["budget_logged" if logged else "budget_rebuilt"] += 1
                    if n < want - 1e-9:
                        st["budget_cap"] += 1
                        st["budget_cap_contracts"] += want - n
        elif f["leg"] == "topup" and not same and g > f["ef"]:
            late = f["late_tau"] and f["tau"] is not None and f["tau"] <= f["late_tau"]
            mult = max(band_mult(f["sig_price"] or f["px"], f["bands"]),
                       f["late_mult"] if late else 1.0)
            allowed = size * mult - held_mkt[f["ticker"]]
            n = max(0.0, min(n_act, allowed, room))
            if n < n_act - 1e-9:
                st["topup_trimmed"] += 1
                st["topup_contracts_cut"] += n_act - n
        else:
            if f["leg"] == "topup" and not same:
                st["topup_kept_as_run"] += 1       # OFF / smaller: see docstring
            if spent_pol > spent_act + 1e-9 and n_act > room + 1e-6:
                n = room
                st["later_leg_squeezed"] += 1
                st["later_leg_contracts_cut"] += n_act - room
            elif (spent_pol < spent_act - 1e-9 and f["leg"] != "early"
                  and n_act >= room_act - 0.01):
                # the budget bound this leg as run; a policy that spent less
                # could have bought more of it -- NOT modelled
                st["room_bound_as_run"] += 1
        out[i] = n
        spent_pol += n
        spent_act += n_act
        held_mkt[f["ticker"]] += n
        coins_act.add(coin)
        if n > 0:
            coins_pol.add(coin)
    return out


def score(ledger, fills, hedges, lo_ep, hi_ep, policies, fee_rate=FEE_RATE, through="cap"):
    """Per-close money for LIVE and each policy, plus diagnostics.

    policies: {name: early fraction, or None for LIVE-as-run}. Closes are the
    pin-series ledger rows with lo_ep < close <= hi_ep. `through` is how a
    price-through early fill is scaled up (resize_close); "decision" also
    prices the extra contracts of every moved fill on the decision-time book.

    Each row carries, besides the totals: `tickers` (the ledger markets
    summed into `live`), `mismatch` (markets whose ledger entry-side count
    differs from the logged fills by > 0.5 contract), `not_in_ledger` (log
    fills in this close with no ledger row), and per market the policy's
    delta (`mk`) and what it rested on (`fl`: UNLOGGED flags)."""
    by_close_mk = collections.defaultdict(list)
    for tk, row in ledger.items():
        ce = close_ep_of_ticker(tk)
        if ce is not None and lo_ep < ce <= hi_ep:
            by_close_mk[ce].append(tk)
    fills_by_close = collections.defaultdict(list)
    for i, f in enumerate(fills):
        if f["close"] is not None and lo_ep < f["close"] <= hi_ep:
            fills_by_close[f["close"]].append((i, f))
    hed_by_tk = collections.defaultdict(list)
    for h in hedges:
        hed_by_tk[h["ticker"]].append(h)
    led_set = set(ledger)
    nil_by_close = collections.Counter(
        f["close"] for f in fills if f["close"] is not None and lo_ep < f["close"] <= hi_ep
        and f["ticker"] not in led_set)
    stats = {name: collections.Counter() for name in policies}
    diag = collections.Counter()
    early_mk = set()
    rows = []
    curves = {}
    for ce in sorted(by_close_mk):
        cf = fills_by_close.get(ce, [])
        sizes = {name: resize_close(cf, g, stats[name], through)
                 for name, g in policies.items()}
        live = 0.0
        pol = {name: 0.0 for name in policies}
        mk, fl = {}, {}
        n_mismatch = 0
        cf_by_tk = collections.defaultdict(list)
        for i, f in cf:
            cf_by_tk[f["ticker"]].append((i, f))
        n_early = 0
        for tk in by_close_mk[ce]:
            row = ledger[tk]
            live += row["pnl"]
            mf = cf_by_tk.get(tk, [])
            if not mf:
                diag["markets_without_log_fills"] += 1
                for name in policies:
                    pol[name] += row["pnl"]
                continue
            if any(f["leg"] == "early" for _, f in mf):
                n_early += 1
                early_mk.add(tk)
            entry_side = mf[0][1]["want"]
            if any(f["want"] != entry_side for _, f in mf):
                diag["markets_both_sides_in_log"] += 1
            res = row["result"]
            # reconcile: the ledger's entry-side contracts against our fills
            led_n = row["yes_n"] if entry_side == "yes" else row["no_n"]
            log_n = sum(f["filled"] for _, f in mf if f["want"] == entry_side)
            if abs(led_n - log_n) > 0.5:
                diag["entry_count_mismatch"] += 1
                diag["entry_count_mismatch_contracts"] += led_n - log_n
                n_mismatch += 1
            # the hedge, from the ledger's opposite side
            hside = "no" if entry_side == "yes" else "yes"
            nh = row["no_n"] if hside == "no" else row["yes_n"]
            ch = row["no_c"] if hside == "no" else row["yes_c"]
            hk = [h for h in hed_by_tk.get(tk, []) if h["side"] == hside]
            hpnl_pc = None
            if nh > 0.01:
                ph = ch / nh
                hpnl_pc = (win_of(hside, res) - ph - fee_pc(ph, fee_rate))
                diag["hedged_markets"] += 1
            t_h = hk[0]["t"] if hk else None
            # contracts the hedge side could still have given, summed over the
            # logged attempts: known only where an attempt's ladder_n came in
            # UNDER what it asked (pinrun.hedge_depth caps ladder_n at the
            # unhedged count). One unread attempt -> unknown (None).
            h_extra = 0.0
            for h in hk:
                if (h["ladder_n"] is not None and h["asked"] is not None
                        and h["ladder_n"] < h["asked"] - 0.01):
                    h_extra += max(0.0, h["ladder_n"] - h["n"])
                else:
                    h_extra = None
                    break
            if not hk:
                h_extra = None
            mk[tk], fl[tk] = {}, {}
            for name in policies:
                delta = 0.0
                flags = set()
                for i, f in mf:
                    n_new = sizes[name][i]
                    if abs(n_new - f["filled"]) < 1e-12:
                        continue
                    if f["leg"] == "early" and n_new > f["filled"] + 1e-9:
                        if f.get("move"):
                            flags.add(f["move"])
                        if not f["has_sig"]:
                            flags.add("uncapped")
                    if (n_new > f["filled"] + 1e-9
                            and sum(q for _, q in (f.get("ladder") or [])) < n_new - 1e-9):
                        stats[name]["priced_past_logged_ladder"] += 1
                        flags.add("past_ladder")
                    mode = "add" if (through == "decision" and f.get("move")) else "shift"
                    if (i, mode) not in curves:
                        curves[(i, mode)] = cost_curve(f, fee_rate, mode)
                    w = win_of(f["want"], res)
                    c = curves[(i, mode)]
                    delta += (n_new * w - c(n_new)) - (f["filled"] * w - c(f["filled"]))
                if hpnl_pc is not None:
                    before = [(i, f) for i, f in mf
                              if t_h is None or (f["t"] or 0) <= t_h]
                    pos_act = sum(f["filled"] for _, f in before)
                    pos_new = sum(sizes[name][i] for i, _ in before)
                    if pos_act > 0 and abs(pos_new - pos_act) > 1e-12:
                        nh_new = nh * pos_new / pos_act
                        if nh_new > nh + 1e-9:
                            stats[name]["hedges_scaled_up"] += 1
                            flags.add("hedge_up")    # priced at the AVERAGE hedge price
                            if h_extra is None:
                                # depth past what was asked was never read:
                                # an UPPER bound on FULL's hedge, flagged
                                stats[name]["hedge_depth_unread"] += 1
                            elif nh_new > nh + h_extra + 1e-9:
                                nh_new = nh + h_extra
                                stats[name]["hedge_depth_cap"] += 1
                        stats[name]["hedges_resized"] += 1
                        delta += hpnl_pc * (nh_new - nh)
                val = row["pnl"] + delta
                if all(sizes[name][i] <= 1e-12 for i, _ in mf):
                    # nothing bought -> nothing hedged -> exactly $0. What is
                    # left is the logs' fee/price rounding against the ledger.
                    stats[name]["removed_markets"] += 1
                    stats[name]["removed_residue_abs"] += abs(val)
                    val = 0.0
                moved_dn = any(f["leg"] == "early" and f.get("move")
                               and sizes[name][i] < f["filled"] - 1e-9 for i, f in mf)
                if moved_dn and abs(val - row["pnl"]) > 1e-12:
                    # those contracts really filled; only a partial cut's price
                    # split is approximate
                    stats[name]["moved_down_markets"] += 1
                    stats[name]["moved_down_delta"] += val - row["pnl"]
                pol[name] += val
                mk[tk][name] = val - row["pnl"]
                fl[tk][name] = flags
        rows.append({"close": ce, "day": et_day(ce), "live": live, "pol": pol,
                     "early_markets": n_early, "markets": len(by_close_mk[ce]),
                     "tickers": sorted(by_close_mk[ce]), "mismatch": n_mismatch,
                     "not_in_ledger": nil_by_close.get(ce, 0), "mk": mk, "fl": fl})
    # log fills whose market has no ledger row (unsettled / not refreshed)
    diag["log_fills_not_in_ledger"] = sum(nil_by_close.values())
    diag["early_markets"] = len(early_mk)
    return rows, stats, diag


def score_bounds(ledger, fills, hedges, lo_ep, hi_ep, policies, fee_rate=FEE_RATE):
    """score() three ways -- price-through fills capped at what filled (the
    headline), their extra contracts at the landing price, and every moved
    fill's extras at the decision-time book -- and each row gets `lo`: the
    policy with every UNLOGGED-flagged market at the worst of the three and
    zero (FULL-lo). `flagged` counts those markets per policy."""
    rows, stats, diag = score(ledger, fills, hedges, lo_ep, hi_ep, policies, fee_rate, "cap")
    alt = {}
    for mode in ("landing", "decision"):
        rs, _s, _d = score(ledger, fills, hedges, lo_ep, hi_ep, policies, fee_rate, mode)
        alt[mode] = {r["close"]: r for r in rs}
    for r in rows:
        r["lo"], r["flagged"] = {}, {}
        rl, rd = alt["landing"][r["close"]], alt["decision"][r["close"]]
        for name in policies:
            lo_val, nfl = r["pol"][name], 0
            for tk in sorted(set(r["mk"]) | set(rl["mk"]) | set(rd["mk"])):
                flags = set()
                for rr in (r, rl, rd):
                    flags |= rr["fl"].get(tk, {}).get(name, set())
                if not flags:
                    continue
                d0 = r["mk"].get(tk, {}).get(name, 0.0)
                dl = rl["mk"].get(tk, {}).get(name, 0.0)
                dd = rd["mk"].get(tk, {}).get(name, 0.0)
                worst = min(d0, dl, dd, 0.0)
                lo_val += worst - d0
                nfl += 1
                st = stats[name]
                st["flagged_markets"] += 1
                st["flagged_delta"] += d0
                st["lo_minus_main"] += worst - d0
                if "through" in flags:
                    st["through_markets"] += 1
                    st["through_at_fill"] += d0
                    st["through_at_landing"] += dl
                    st["through_at_decision"] += dd
                if "dearer" in flags:
                    st["dearer_markets"] += 1
            r["lo"][name] = lo_val
            r["flagged"][name] = nfl
    return rows, stats, diag


# ---------------------------------------------------------------- statistics
def mde(diffs):
    """(sd per close, MDE per close, MDE total) at 80 % power, 5 % two-sided."""
    n = len(diffs)
    if n < 2:
        return None, None, None
    m = sum(diffs) / n
    sd = math.sqrt(sum((d - m) ** 2 for d in diffs) / (n - 1))
    return sd, Z80 * sd / math.sqrt(n), Z80 * sd * math.sqrt(n)


def boot(cols, base, names, B=B_BOOT, seed=7):
    """Close-clustered bootstrap. Returns ({name: P(total > base total)},
    {name: P(name has the highest total among `names`)}). Ties count half."""
    n = len(cols[base])
    if n == 0:
        return {k: None for k in names}, {k: None for k in names}
    rng = random.Random(seed)
    idx_all = range(n)
    beats = collections.Counter()
    best = collections.Counter()
    for _ in range(B):
        idx = rng.choices(idx_all, k=n)
        tot = {k: sum(cols[k][i] for i in idx) for k in set(names) | {base}}
        for k in names:
            d = tot[k] - tot[base]
            beats[k] += 1.0 if d > 1e-9 else (0.5 if d > -1e-9 else 0.0)
        top = max(tot[k] for k in names)
        winners = [k for k in names if tot[k] > top - 1e-9]
        for k in winners:
            best[k] += 1.0 / len(winners)
    return ({k: beats[k] / B for k in names}, {k: best[k] / B for k in names})


# ---------------------------------------------------------------- paper arms
ARM_IGNORE = ("t", "kind", "mode", "code_sha", "size", "minutes", "day_loss_at_start")


def _first_rec(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            r = json.loads(fh.readline())
        return r if isinstance(r, dict) else None
    except (OSError, ValueError):
        return None


def _span(path):
    """(first t, last t) epochs of a log's records, or (None, None)."""
    ts = [t for t in (iso_ep(r.get("t")) for r in read_jsonl(path)) if t is not None]
    return (min(ts), max(ts)) if ts else (None, None)


def arm_logs(results_dir, arm, since_ep=None):
    """An arm's paper logs, oldest first.

    results/arm-<name>.out names only the CURRENT log: sync_arms.ps1
    restarts an arm with Start-Process -RedirectStandardOutput, which
    TRUNCATES the file, and a paper start record carries no arm name. So:
    the logs the .out names, plus every other paper log whose start record
    equals the named log's on every setting (t, code_sha, size, minutes and
    day_loss_at_start ignored), that has records after `since_ep`, and that
    does not overlap in time a log already chosen -- a concurrent twin with
    the same settings would count the same closes twice."""
    p = os.path.join(results_dir, "arm-%s.out" % arm)
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except OSError:
        return []
    hits = re.findall(r"^\s*log\s+(\S*pinrun-paper-\d{8}T\d{6}Z\.jsonl)\s*$", txt, re.M)
    named = []
    for h in hits:
        q = os.path.join(results_dir, os.path.basename(h))
        if q not in named and os.path.exists(q):
            named.append(q)
    if not named:
        return []
    ref = _first_rec(sorted(named)[-1])
    if not ref or ref.get("kind") != "start":
        return sorted(named)

    def cfg(r):
        return {k: v for k, v in r.items() if k not in ARM_IGNORE}
    want = cfg(ref)
    chosen = [(q,) + _span(q) for q in named]
    cands = []
    for q in sorted(glob.glob(os.path.join(results_dir, "pinrun-paper-*.jsonl"))):
        if q in named:
            continue
        r = _first_rec(q)
        if not r or r.get("kind") != "start" or cfg(r) != want:
            continue
        a, b = _span(q)
        if a is None or (since_ep is not None and b < since_ep):
            continue
        cands.append((q, a, b))
    for q, a, b in sorted(cands, key=lambda x: x[1]):
        if any(ca is not None and not (b < ca or a > cb) for _q, ca, cb in chosen):
            continue
        chosen.append((q, a, b))
    return sorted(q for q, _a, _b in chosen)


def paper_by_close(paths):
    """({close: $}, info, {close: tickers}) from paper logs' per-position
    `settled` records (a paper hedge settles as its own record). Paper has no
    ledger, so this is the only source -- labelled hypothesis."""
    if isinstance(paths, str):
        paths = [paths]
    recs = []
    for path in paths:
        recs.extend(read_jsonl(path))
    by = collections.defaultdict(float)
    tk_close = collections.defaultdict(set)
    info = {"start": None, "last": None, "early_signals": 0, "early_full_size": 0,
            "signals": 0, "early_frac": None, "early_tau_max": None, "size": None}
    size = None
    for r in recs:
        t = iso_ep(r.get("t"))
        if t is not None:
            info["last"] = t if info["last"] is None else max(info["last"], t)
        k = r.get("kind")
        if k == "start" and info["start"] is None:
            info["start"] = t
            info["early_frac"] = r.get("early_frac")
            info["early_tau_max"] = r.get("early_tau_max")
            size = fnum(r.get("size"))
        elif k == "autosize":
            size = fnum(r.get("new"), size)
        elif k == "signal":
            info["signals"] += 1
            if r.get("leg") == "early":
                info["early_signals"] += 1
                tn = fnum(r.get("take_n"), 0.0)
                if size and tn >= 0.999 * min(size, fnum(r.get("size"), size)):
                    info["early_full_size"] += 1
        elif k == "settled":
            ce = close_ep_of_ticker(r.get("ticker"))
            if ce is not None:
                by[ce] += (fnum(r.get("pnl_c"), 0.0) or 0.0) / 100.0
                tk_close[ce].add(r.get("ticker"))
    info["size"] = size
    return dict(by), info, tk_close


# ---------------------------------------------------------------- report
def money(x):
    return "%+.2f" % x


def col_val(r, c, base="LIVE"):
    """A row's dollars under column c: LIVE, a policy, or '<policy>-lo'."""
    if c == base:
        return r["live"]
    if c.endswith("-lo"):
        return r["lo"][c[:-3]]
    return r["pol"][c]


def table(rows, cols, base, names, label_fn, B):
    """Per-ET-day lines + a cumulative line. cols: names incl. base. A P value
    is printed only for a group of >= FLOOR closes ('-' below)."""
    out = []
    head = "  %-10s %6s " % ("ET day", "closes") + " ".join("%10s" % c for c in cols) \
        + "   $/close " + "/".join(c for c in cols) \
        + "   losing closes " + "/".join(c for c in cols) \
        + "   " + " ".join("P(%s>%s)" % (k, base) for k in names)
    out.append(head)
    days = collections.OrderedDict()
    for r in rows:
        days.setdefault(r["day"], []).append(r)
    groups = [(d, rs) for d, rs in days.items()] + [("ALL", rows)]
    n_p = 0
    for label, rs in groups:
        n = len(rs)
        vals = {c: [label_fn(r, c) for r in rs] for c in cols}
        tot = {c: sum(vals[c]) for c in cols}
        pc = "/".join("%+.2f" % (tot[c] / n) if n else "-" for c in cols)
        lose = "/".join("%d" % sum(1 for v in vals[c] if losing(v)) for c in cols)
        if n >= FLOOR:
            pb, _ = boot(vals, base, names, B=(B if label == "ALL" else min(B, 3000)), seed=11)
            ps = " ".join(("%8.2f" % pb[k]) if pb[k] is not None else "       -" for k in names)
            n_p += len(names)
        else:
            ps = " ".join("       -" for _k in names)
        out.append("  %-10s %6d " % (label, n) + " ".join("%10s" % money(tot[c]) for c in cols)
                   + "   " + pc + "   " + lose + "   " + ps)
    return out, n_p


def section_policy(title, rows, cols, base, names, B, note_lines=()):
    """(lines, number of P values printed)."""
    out = ["", title, "-" * min(len(title), 80)]
    out.extend(note_lines)
    if not rows:
        out.append("  no settled pin closes in this window yet (n = 0): nothing to compare.")
        return out, 0
    cols_v = {c: [col_val(r, c, base) for r in rows] for c in cols}
    out.append("  minimum detectable difference (80 %% power, 5 %% two-sided), n = %d traded "
               "closes (a pin ledger row):" % len(rows))
    for k in names:
        d = [a - b for a, b in zip(cols_v[k], cols_v[base])]
        sd, m1, mt = mde(d)
        if sd is None:
            out.append("    %s - %s: n < 2 closes, no power at all" % (k, base))
        else:
            nz = sum(1 for x in d if abs(x) > 1e-9)
            out.append("    %s - %s: $%.2f total ($%.3f/close); sd $%.2f/close; "
                       "%d of %d closes differ at all"
                       % (k, base, mt, m1, sd, nz, len(d)))
    tl, n_p = table(rows, cols, base, names, lambda r, c: col_val(r, c, base), B)
    out.extend(tl)
    if len(rows) >= FLOOR:
        _, pbest = boot(cols_v, base, cols, B=B, seed=13)
        out.append("  chance each is the BEST of %s over the whole window (close-clustered "
                   "bootstrap): %s" % ("/".join(cols), ", ".join("%s %.2f" % (k, pbest[k])
                                                               for k in cols)))
        n_p += len(cols)
    else:
        out.append("  no P value below %d closes (%d here): with this few, one close decides it."
                   % (FLOOR, len(rows)))
    return out, n_p


STAT_KEYS = [
    ("scaled_up", "early legs scaled up"),
    ("depth_cap", "capped by the depth logged at that second"),
    ("partial_cap", "capped at an IOC partial fill"),
    ("through_cap", "price-through fills held at the count that filled"),
    ("uncapped", "NO depth logged -> uncapped, an UPPER bound"),
    ("priced_past_logged_ladder", "priced past the logged ladder (last level)"),
    ("budget_logged", "budget from the bot's own budget_left"),
    ("budget_rebuilt", "budget rebuilt from the start record"),
    ("budget_cap", "cut by the close budget"),
    ("budget_cap_contracts", "contracts cut by the budget"),
    ("later_leg_squeezed", "later legs of other markets squeezed by the budget"),
    ("later_leg_contracts_cut", "contracts cut from them"),
    ("room_bound_as_run", "later legs the budget bound as run (a smaller policy "
                          "could have bought more: NOT modelled)"),
    ("topup_trimmed", "top-ups trimmed (already held SIZE)"),
    ("topup_contracts_cut", "top-up contracts cut"),
    ("topup_kept_as_run", "top-ups kept as run"),
    ("hedges_resized", "hedges resized"),
    ("hedges_scaled_up", "hedges scaled up (extra contracts at the AVERAGE hedge price)"),
    ("hedge_depth_cap", "hedge scale-up capped by logged depth"),
    ("hedge_depth_unread", "hedge scale-up with depth past `asked` never read -> UPPER bound"),
    ("removed_markets", "markets removed entirely (set to exactly $0)"),
    ("removed_residue_abs", "  |logs-vs-ledger rounding| dropped with them, $"),
    ("moved_down_markets", "markets with a moved early fill cut down (really filled)"),
    ("moved_down_delta", "  this policy's $ difference from LIVE on those"),
    ("flagged_markets", "markets resting on something unlogged (-lo set)"),
    ("flagged_delta", "  this policy's $ difference from LIVE on those"),
    ("lo_minus_main", "  -lo minus the headline on those, $"),
]


def stats_lines(name, st):
    parts = []
    for k, lab in STAT_KEYS:
        v = st.get(k)
        if v:
            parts.append("%s %s" % (lab, ("%.1f" % v) if isinstance(v, float) else v))
    if not parts:
        return ["    %-5s nothing resized" % name]
    return ["    %-5s " % name + parts[0]] + ["          " + p for p in parts[1:]]


def b1_terms(path=None):
    """B1's registered rule in one clause, read from FREEZE_bars.json when it
    sits next to this repo's research/ (it is registered there, not here)."""
    p = path or os.path.join(os.path.dirname(HERE), "results", "FREEZE_bars.json")
    try:
        with open(p, encoding="utf-8") as fh:
            bars = json.load(fh)
        b1 = next(b for b in bars["bars"] if b["id"] == "B1")
        r = b1["rules"]
        return ("the first %d closes after %s; FULL must beat the third by >= $%.2f a close "
                "and OFF by >= $%.2f, each with resampled P >= %.3f and no single close over "
                "%.0f%% of the gain, FULL on FULL-lo as well; decided once"
                % (r["min_closes"], b1["window_start_utc"],
                   r["policies"]["full"]["min_gain_per_close"],
                   r["policies"]["off"]["min_gain_per_close"], r["min_boot_p"],
                   100 * r["max_single_close_share"]))
    except (OSError, ValueError, KeyError, StopIteration, TypeError):
        return "its registered rule is in results/FREEZE_bars.json"


def status_line(rows, watched, terms=None):
    """('REPORT ONLY', one line). This page never names a winner: an
    earlier CALLED rule, re-checked on every run with no fixed n, called
    FULL on the real pre-freeze sequences at its first eligible look and in
    36-50% of null worlds. The one decision is FREEZE bar B1."""
    k = sum(1 for r in rows if r["early_markets"])
    units = len(set(watched) | {r["close"] for r in rows})
    return "REPORT ONLY", (
        "this page never names a winner. The decision is FREEZE bar B1 (research/barcheck.py): "
        "%s. So far %d closes since the change as B1 counts them (watched or settled), %d with "
        "a pin ledger row, %d with an early-leg market"
        % (terms or b1_terms(), units, len(rows), k))


def watched_closes(runs, lo, hi):
    """Closes the live bot logged a close_summary for, lo < close <= hi."""
    out = set()
    for run in runs:
        for r in run["recs"]:
            if r.get("kind") == "close_summary":
                c = fnum(r.get("close"))
                if c is not None and lo < c <= hi:
                    out.add(int(c))
    return out


def closes_needed(rows, a, b, per_close, watched=()):
    """(closes, sd per close, closes the sd came from) to detect `per_close`
    dollars a close between columns a and b at 80 % power, in WATCHED
    closes (B1's unit): a watched close with no ledger row differs by 0."""
    d = {r["close"]: col_val(r, a) - col_val(r, b) for r in rows}
    for c in watched:
        d.setdefault(c, 0.0)
    sd, _m1, _mt = mde(list(d.values()))
    if not sd:
        return None, sd, len(d)
    return int(math.ceil((Z80 * sd / per_close) ** 2)), sd, len(d)


def not_modelled(lab, rows, fills, refusals, lo, hi):
    """Section D lines for one era: how often the bounds the model does not
    capture were live. A close_budget refusal (it fires when spent >= budget,
    before the book is read) counts as 'freed' for a policy only if the early
    contracts that policy would NOT have bought before it, plus the budget
    left, reach one contract: THIRD frees held x (1 - 0.333/frac as run) --
    nothing in an hour already at a third -- and OFF frees all of it."""
    out = []
    closes = {r["close"] for r in rows}
    early_c = {r["close"] for r in rows if r["early_markets"]}
    early_mk = {f["ticker"] for f in fills if f["leg"] == "early"
                and f["close"] in early_c}
    early_n = collections.defaultdict(list)          # close -> [(t, contracts, frac as run)]
    for f in fills:
        if f["leg"] == "early" and f["close"] in early_c:
            early_n[f["close"]].append((f["t"] or 0, f["filled"], f["ef"]))
    cb = [x for x in refusals if x["gate"] == "close_budget" and lo < x["close"] <= hi]
    cb_mk = {(x["close"], x["ticker"]) for x in cb}
    cb_early = {(x["close"], x["ticker"]) for x in cb if x["close"] in early_c}
    freed = {"THIRD": set(), "OFF": set()}
    room_c = {"THIRD": {}, "OFF": {}}        # close -> most room the policy would have freed
    unread = set()
    for x in cb:
        if x["close"] not in early_c:
            continue
        before = [(n, ef) for t, n, ef in early_n[x["close"]] if t <= (x["t"] or 0)]
        if not before:
            continue
        key = (x["close"], x["ticker"])
        if x["bleft"] is None:
            unread.add(key)
            continue
        room = max(0.0, x["bleft"])
        free = {"OFF": sum(n for n, _ef in before),
                "THIRD": sum(n * (1.0 - THIRD / ef) for n, ef in before
                             if ef and ef > THIRD + 1e-9)}
        for pol_ in freed:
            if free[pol_] > 1e-9 and room + free[pol_] >= 1.0:
                freed[pol_].add(key)
                room_c[pol_][x["close"]] = max(room_c[pol_].get(x["close"], 0.0), free[pol_])
    mpm = {(x["close"], x["ticker"]) for x in refusals
           if x["gate"] == "max_per_market" and lo < x["close"] <= hi}
    mpm_early = {k for k in mpm if k[1] in early_mk}
    out.append("  %s: %d closes, %d with an early-leg market. close_budget refusals: %d "
               "(%d in early-leg closes)." % (lab, len(closes), len(early_c),
                                              len(cb_mk), len(cb_early)))
    out.append("     A smaller early leg would have left room for >= 1 contract in %d of them "
               "at a third (%.0f contracts of room over %d closes), %d with the leg off (%.0f "
               "over %d closes). The gate fires before the book is read, so whether those "
               "markets were tradeable is unknown. NOT modelled: upside for the smaller leg. "
               "%d refusals carry no budget at all."
               % (len(freed["THIRD"]), sum(room_c["THIRD"].values()), len(room_c["THIRD"]),
                  len(freed["OFF"]), sum(room_c["OFF"].values()), len(room_c["OFF"]),
                  len(unread)))
    out.append("     max_per_market refusals: %d, %d of them on early-leg markets "
               "(FULL buys in one fill, freeing a slot a late boost could use: NOT modelled)."
               % (len(mpm), len(mpm_early)))
    return out, {"close_budget": len(cb_mk), "cb_early": len(cb_early),
                 "freed_third": len(freed["THIRD"]), "freed_off": len(freed["OFF"]),
                 "freed_third_contracts": sum(room_c["THIRD"].values()),
                 "freed_off_contracts": sum(room_c["OFF"].values()),
                 "unread": len(unread), "mpm": len(mpm), "mpm_early": len(mpm_early)}


def eras(runs, lo, hi):
    """'third 13:05Z-19:30Z 09-17, full ...' from each run's start record,
    consecutive runs with the same early fraction merged."""
    segs = []
    for run in runs:
        st = next((r for r in run["recs"] if r.get("kind") == "start"), None)
        ts = [t for t in (iso_ep(r.get("t")) for r in run["recs"] if r.get("t")) if t]
        if st is None or not ts or max(ts) <= lo or min(ts) >= hi:
            continue
        on = (fnum(st.get("early_tau_max"), 30) or 30) > (fnum(st.get("tau_max"), 30) or 30)
        ef = fnum(st.get("early_frac"), 0.0) if on else 0.0
        name = "off" if not ef else ("third" if abs(ef - THIRD) < 0.01 else
                                     "full" if ef >= 0.999 else "%.2f" % ef)
        a, b = max(min(ts), lo), min(max(ts), hi)
        if segs and segs[-1][0] == name:
            segs[-1][2] = b
        else:
            segs.append([name, a, b])
    return "; ".join("%s %s..%s" % (n, time.strftime("%m-%d %H:%MZ", time.gmtime(a)),
                                    time.strftime("%m-%d %H:%MZ", time.gmtime(b)))
                     for n, a, b in segs)


def freeze_rows(since_s, data_dir, now_s=None, ledger_rows=None):
    """B1's scorer -- results/FREEZE_bars.json names this function and pins
    this file's code_sha256(). One row per close after since_s:

      close, live (Kalshi's ledger for the pin markets settling then),
      full, off, full_lo (FULL-lo), tickers (the ledger markets in `live`),
      mismatch (markets whose ledger entry-side contracts differ from the
      logged fills), not_in_ledger (log fills with no ledger row), flagged
      (FULL's UNLOGGED markets), early_markets.

    `ledger_rows` = the raw settlements the CALLER already read, so caller
    and scorer judge one snapshot of the ledger. Read-only."""
    now_s = time.time() if now_s is None else now_s
    if ledger_rows is None:
        ledger = load_ledger(os.path.join(data_dir, "kalshi_ledger.json"))
    else:
        ledger = ledger_from_rows(ledger_rows)
    runs = load_live_runs(data_dir, ep_iso(since_s))
    fills, hedges, _refusals = extract(runs)
    rows, stats, diag = score_bounds(ledger, fills, hedges, since_s, now_s + 3600,
                                     {"FULL": FULL, "OFF": 0.0})
    out = [{"close": r["close"], "live": r["live"], "full": r["pol"]["FULL"],
            "off": r["pol"]["OFF"], "full_lo": r["lo"]["FULL"], "tickers": r["tickers"],
            "mismatch": r["mismatch"], "not_in_ledger": r["not_in_ledger"],
            "flagged": r["flagged"]["FULL"], "early_markets": r["early_markets"]}
           for r in rows]
    return {"rows": out, "diag": dict(diag),
            "stats": {k: dict(v) for k, v in stats.items()}, "code_sha256": code_sha256()}


def build_report(results_dir, now_ep, B=B_BOOT):
    lines = []
    ledger = load_ledger(os.path.join(results_dir, "kalshi_ledger.json"))
    if not ledger:
        return None, "the ledger (kalshi_ledger.json) loaded nothing"
    runs = load_live_runs(results_dir, CAL_FROM)
    if not runs:
        return None, "no pinrun-live-*.jsonl since %s" % CAL_FROM
    fills, hedges, refusals = extract(runs)
    newest = max((r["settled"] or "") for r in ledger.values())
    dep, cal, fix = iso_ep(DEPLOY), iso_ep(CAL_FROM), iso_ep(FIXES_FROM)
    hi_a = now_ep + 3600

    pa = {"FULL": FULL, "OFF": 0.0}
    rows_a, st_a, dg_a = score_bounds(ledger, fills, hedges, dep, hi_a, pa)
    pc = {"THIRD": THIRD, "FULL": FULL, "OFF": 0.0}
    rows_c, st_c, dg_c = score_bounds(ledger, fills, hedges, cal, dep, pc)
    rows_f = [r for r in rows_c if r["close"] >= fix]
    w_a = watched_closes(runs, dep, hi_a)
    w_c = watched_closes(runs, cal, dep)
    w_f = {c for c in w_c if c >= fix}
    word, why = status_line(rows_a, w_a)
    n_p = 0

    lines.append("EARLY HINDSIGHT -- the 31-45 s leg at a third (live) vs full size vs off")
    lines.append("generated %s; ledger newest settlement %s; %d live run logs read "
                 "(read-only); scorer code_sha256 %s"
                 % (ep_iso(now_ep), newest[:19] + "Z", len(runs), (code_sha256() or "?")[:16]))
    lines.append("")
    lines.append("STATUS: %s -- %s." % (word, why))
    src, w_src, srcn = ((rows_f, w_f, "since the fixes") if len(rows_f) >= 10
                        else (rows_c, w_c, "09-17..09-22"))
    for a_, b_ in (("FULL", "THIRD"), ("FULL-lo", "THIRD"), ("OFF", "THIRD")):
        for pcl in (0.50, 1.00):
            need, sd, nu = closes_needed(src, a_, b_, pcl, w_src)
            if need is not None:
                lines.append("  to see a $%.2f gap a WATCHED close %s vs %s at 80%% power needs "
                             "~%d watched closes (B1's unit; spread $%.2f a watched close, %s, "
                             "%d watched closes)" % (pcl, a_, b_, need, sd, srcn, nu))
    lines.append("")
    lines.append("Money: Kalshi's ledger (pinledger.pnl), pin series only. Tables count TRADED "
                 "closes (a pin ledger row); B1 counts watched closes (~2.8x as many). Every "
                 "policy = LIVE + a delta on early-leg entries, their hedge share, top-ups and "
                 "budget-squeezed later legs, priced on the book the bot logged (counterfactual, "
                 "not fills). FULL holds price-through fills at what filled; FULL-lo is FULL with "
                 "every market resting on something unlogged at its worst reading and zero. "
                 "ET days.")

    # ---- A: since v-early-third
    sec, k_ = section_policy(
        "A. SINCE v-early-third (closes after %s; live runs the early leg at a third)" % DEPLOY,
        rows_a, ["LIVE", "FULL", "FULL-lo", "OFF"], "LIVE", ["FULL", "FULL-lo", "OFF"], B,
        ["  LIVE = actual (third). FULL = early entries at full size, capped by the depth "
         "logged at that second and by the bot's own budget_left. OFF = early entries and "
         "their hedge share removed (markets NOT handed to the <=30 s window)."])
    lines += sec
    n_p += k_
    lines.append("  resizing tallies (closes in A):")
    for k in pa:
        lines += stats_lines(k, st_a[k])

    # ---- B: paper arms
    lines.append("")
    lines.append("B. PAPER ARMS -- paper -- HYPOTHESIS (their own `settled` records; no ledger; "
                 "paper fills never lose a race)")
    lines.append("-" * 72)
    live_close = collections.defaultdict(float)
    for tk, row in ledger.items():
        ce = close_ep_of_ticker(tk)
        if ce is not None:
            live_close[ce] += row["pnl"]
    newest_close = max(live_close) if live_close else 0
    live_span = []
    for run in runs:
        ts = [iso_ep(r.get("t")) for r in run["recs"] if r.get("t")]
        ts = [t for t in ts if t is not None]
        if ts:
            live_span.append((min(ts), max(ts)))
    live_mk = collections.defaultdict(set)
    for f in fills:
        if f["close"] is not None:
            live_mk[f["close"]].add(f["ticker"])
    for arm in ("early-full", "early-off"):
        ps = arm_logs(results_dir, arm, since_ep=dep)
        if not ps:
            lines.append("  arm-%s: no paper log named in results/arm-%s.out -- not scored"
                         % (arm, arm))
            continue
        by, info, tkc = paper_by_close(ps)
        lo = max(dep, (info["start"] or dep) + 45)
        hi = min(newest_close, (info["last"] or 0) - 30)
        shared = []
        c = lo - lo % 900 + 900
        while c <= hi:
            ran = any(a <= c - 45 and b >= c for a, b in live_span)
            if ran and (c in by or c in live_close):
                shared.append(c)
            c += 900
        off = (fnum(info["early_tau_max"], 45) or 45) <= 30
        lines.append("  arm-%s: %s (early_frac %s, early window to %s s%s, SIZE %s); started %s"
                     % (arm, ", ".join(os.path.basename(p) for p in ps), info["early_frac"],
                        info["early_tau_max"], " = leg OFF" if off else "", info["size"],
                        ep_iso(info["start"]) if info["start"] else "?"))
        lines.append("    flag exercised: %d early-leg signals of %d, %d at the full size cap"
                     % (info["early_signals"], info["signals"], info["early_full_size"]))
        if not shared:
            lines.append("    shared settled closes with live: 0 -- nothing to compare yet")
            continue
        a_v = [by.get(c, 0.0) for c in shared]
        l_v = [live_close.get(c, 0.0) for c in shared]
        same = sum(len(tkc.get(c, set()) & live_mk.get(c, set())) for c in shared)
        arm_only = sum(len(tkc.get(c, set()) - live_mk.get(c, set())) for c in shared)
        live_only = sum(len(live_mk.get(c, set()) - tkc.get(c, set())) for c in shared)
        sd, m1, mt = mde([a - b for a, b in zip(a_v, l_v)])
        if len(shared) >= FLOOR:
            pb, _ = boot({"ARM": a_v, "LIVE": l_v}, "LIVE", ["ARM"], B=B, seed=17)
            p_txt = "%.2f" % pb["ARM"]
            n_p += 1
        else:
            p_txt = "- (none below %d closes)" % FLOOR
        lines.append("    %sMDE on %d shared closes (either traded): %s"
                     % ("COLLECTING (< %d closes). " % FLOOR if len(shared) < FLOOR else "",
                        len(shared), "$%.2f total" % mt if mt is not None else "n < 2, none"))
        lines.append("    arm %s vs live %s ($/close %+.2f vs %+.2f); losing closes %d vs %d; "
                     "P(arm > live) %s"
                     % (money(sum(a_v)), money(sum(l_v)), sum(a_v) / len(shared),
                        sum(l_v) / len(shared),
                        sum(1 for v in a_v if losing(v)), sum(1 for v in l_v if losing(v)),
                        p_txt))
        lines.append("    markets traded by both: %d; arm only: %d; live only: %d "
                     "(different markets = not like-for-like)" % (same, arm_only, live_only))

    # ---- C: calibration
    sec, k_ = section_policy(
        "C. CALIBRATION -- %s .. %s; the early leg as run: %s" % (
            CAL_FROM, DEPLOY, eras(runs, cal, dep)),
        rows_c, ["LIVE", "THIRD", "FULL", "FULL-lo", "OFF"], "LIVE",
        ["THIRD", "FULL", "FULL-lo", "OFF"], B,
        ["  calibration, not the test. LIVE = what actually ran. THIRD/FULL/OFF = every "
         "early entry resized to that policy (hours already at that size are unchanged)."])
    lines += sec
    n_p += k_
    sec, k_ = section_policy(
        "C2. same, only since the fixes (closes from 09-20 00:00 ET = %s)" % FIXES_FROM,
        rows_f, ["LIVE", "THIRD", "FULL", "FULL-lo", "OFF"], "LIVE",
        ["THIRD", "FULL", "FULL-lo", "OFF"], B)
    lines += sec
    n_p += k_
    lines.append("  resizing tallies (closes in C):")
    for k in pc:
        lines += stats_lines(k, st_c[k])

    # ---- D: what is not modelled
    lines.append("")
    lines.append("D. WHAT IS NOT MODELLED, AND HOW OFTEN IT COULD MATTER")
    lines.append("-" * 55)
    lines += not_modelled("A", rows_a, fills, refusals, dep, hi_a)[0]
    lines += not_modelled("C", rows_c, fills, refusals, cal, dep)[0]
    lines.append("  FULL's budget: A %d early scale-ups cut by the close budget, %d later legs of "
                 "other markets squeezed (both MODELLED); C %d and %d."
                 % (st_a["FULL"]["budget_cap"], st_a["FULL"]["later_leg_squeezed"],
                    st_c["FULL"]["budget_cap"], st_c["FULL"]["later_leg_squeezed"]))
    for lab, st_ in (("A", st_a), ("C", st_c)):
        f_ = st_["FULL"]
        lines.append("  %s FULL: %d price-through early fills (landed >= 2c under what the logged "
                     "book said) held at the count that filled -> $%+.2f; their extra contracts "
                     "at the landing price would be $%+.2f, at the decision-time book $%+.2f. "
                     "%d markets landed >= 2c dearer. FULL-lo: %d markets rest on something "
                     "unlogged (moved fill, no depth, past the ladder, hedge scaled up at its "
                     "average price); FULL there $%+.2f, FULL-lo $%+.2f."
                     % (lab, f_["through_markets"], f_["through_at_fill"],
                        f_["through_at_landing"], f_["through_at_decision"],
                        f_["dearer_markets"], f_["flagged_markets"], f_["flagged_delta"],
                        f_["flagged_delta"] + f_["lo_minus_main"]))
        for k in st_:
            if k != "FULL" and st_[k]["moved_down_markets"]:
                lines.append("  %s %s: %d markets with a moved early fill cut down; %s's "
                             "difference from LIVE there $%+.2f (those contracts really filled; "
                             "only a partial cut's price split is approximate)."
                             % (lab, k, st_[k]["moved_down_markets"], k,
                                st_[k]["moved_down_delta"]))
    lines.append("  FULL upper bounds: early entries with no logged depth A %d / C %d; hedge "
                 "scale-ups whose depth past `asked` was never read A %d / C %d."
                 % (st_a["FULL"]["uncapped"], st_c["FULL"]["uncapped"],
                    st_a["FULL"]["hedge_depth_unread"], st_c["FULL"]["hedge_depth_unread"]))
    topup = collections.Counter()
    for f in fills:
        if f["leg"] == "topup" and f["close"]:
            topup["A" if f["close"] > dep else "C"] += 1
    lines.append("  OFF keeps top-ups as they ran and never hands a market to the <=30 s window "
                 "(critic G2: 163 of 203 early markets were never offered at 90-98c later, tape): "
                 "top-up fills A %d, C %d -- OFF is a lower bound there." % (topup["A"],
                                                                            topup["C"]))
    lines.append("  THIRD in C cannot add top-ups a full-size bot never sent (lower bound). Not "
                 "modelled anywhere: a different early size changing which market a scan "
                 "picks, hedge timing, or the loss-cap/brake state.")

    # ---- E: reconciliation
    lines.append("")
    lines.append("E. LEDGER vs LOGS")
    lines.append("-" * 17)
    for lab, dg in (("A", dg_a), ("C", dg_c)):
        lines.append("  %s: early-leg markets %d; hedged markets %d; ledger markets the logs "
                     "never saw (identical in every policy) %d; markets whose ledger "
                     "entry-side contracts differ from the logged fills by > 0.5: %d "
                     "(net %+.1f contracts); log fills with no ledger row yet: %d"
                     % (lab, dg["early_markets"], dg["hedged_markets"],
                        dg["markets_without_log_fills"], dg["entry_count_mismatch"],
                        dg["entry_count_mismatch_contracts"], dg["log_fills_not_in_ledger"]))
    lines.append("")
    lines.append("Multiple looks: %d P-values on this page; by chance alone about %.1f of them "
                 "land under 0.05 or over 0.95. None of them decides anything (B1 does)."
                 % (n_p, n_p * 0.10))
    return lines, None


# ---------------------------------------------------------------- self-test
def _tk(series, close_ep):
    """A ticker whose ET stamp encodes close_ep."""
    loc = close_ep + et_offset(close_ep)
    tm = time.gmtime(loc)
    mon = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV",
           "DEC"][tm.tm_mon - 1]
    return "%s-%02d%s%02d%02d%02d-%02d" % (series, tm.tm_year % 100, mon, tm.tm_mday,
                                           tm.tm_hour, tm.tm_min, tm.tm_min)


def _world(spec, cfg):
    """spec: list of markets {series, close, result, fills:[...], hedge:{...}}.
    Returns (ledger rows, runs) shaped exactly like the real files.

    cfg: SIZE, ef, mpc, extra, bands, late_tau, late_mult, fee_rate;
    start_size + autosize (the start record says start_size, an autosize
    record then sets SIZE before any fill); early_tau_max (30 = leg off);
    extra_ledger (raw rows added as they are). Per fill: sig (False = no
    signal record), sig_dt (the signal logged that many seconds BEFORE the
    order), sig_px, touch, sd, ladder, bleft, count, limit, old_format.
    Per market: in_ledger, fee_bump, ledger_extra_n (entry-side contracts
    the ledger holds that no log saw), refusals."""
    t_first = min(m["close"] for m in spec) - 3600
    recs = [dict({"kind": "start", "t": ep_iso(t_first),
                  "early_tau_max": cfg.get("early_tau_max", 45), "tau_max": 30,
                  "size": cfg.get("start_size", cfg["SIZE"]),
                  "early_frac": cfg["ef"], "max_per_close": cfg.get("mpc", 2),
                  "extra_coin": cfg.get("extra"), "band_mults": cfg.get("bands", []),
                  "late_tau": cfg.get("late_tau", 10), "late_mult": cfg.get("late_mult", 1.5)})]
    if cfg.get("autosize"):
        recs.append({"kind": "autosize", "t": ep_iso(t_first + 60),
                     "old": cfg.get("start_size"), "new": cfg["SIZE"]})
    ledger = {}
    oid = 0
    ev = []
    fr = cfg.get("fee_rate", FEE_RATE)
    for m in spec:
        tk = _tk(m["series"], m["close"])
        m["ticker"] = tk
        side_n = {"yes": 0.0, "no": 0.0}
        side_c = {"yes": 0.0, "no": 0.0}
        fee = 0.0
        for f in m["fills"]:
            oid += 1
            t = ep_iso(m["close"] - f["tau"])
            px, n = f["px"], f["n"]
            ft = n * fee_pc(px, fr)
            old = f.get("old_format")
            if f.get("sig", True):
                dt = f.get("sig_dt", 0)
                ev.append((m["close"] - f["tau"] - dt, {
                    "kind": "signal", "t": ep_iso(m["close"] - f["tau"] - dt), "ticker": tk,
                    "want": None if old else f["want"], "price": f.get("sig_px", px),
                    "size": f.get("touch", 500.0), "take_n": f.get("count", n),
                    "tau": f["tau"] + dt, "leg": f["leg"], "budget_left": f.get("bleft"),
                    "ladder": f.get("ladder", [[px, 500.0]])}))
            if f.get("sd") is not None:
                ev.append((m["close"] - f["tau"], {
                    "kind": "sweep_depth", "t": t, "ticker": tk, "want": f["want"],
                    "ladder": f["sd"], "now": min(cfg["SIZE"], f["sd"]), "was": f.get("count", n)}))
            orec = {
                "kind": "order", "t": t, "ticker": tk, "want": f["want"], "leg": f["leg"],
                "filled": n, "exec_price": px, "fee_total": ft, "limit_sent": f.get("limit", 0.98),
                "tau_at_send": f["tau"], "order_id": "o%d" % oid,
                "body": {"count": "%.2f" % f.get("count", n)}}
            if f.get("no_leg"):
                del orec["leg"]
            if old:        # pre-09-21 shape: no want, Kalshi book side in the body
                del orec["want"]
                lim = f.get("limit", 0.98)
                orec["body"].update(side=("bid" if f["want"] == "yes" else "ask"),
                                    price="%.4f" % (lim if f["want"] == "yes" else 1 - lim))
            ev.append((m["close"] - f["tau"] + 0.1, orec))
            side_n[f["want"]] += n
            side_c[f["want"]] += n * px
            fee += ft
        h = m.get("hedge")
        if h:
            ev.append((m["close"] - h["tau"] + 0.2, {
                "kind": "hedge", "t": ep_iso(m["close"] - h["tau"]), "ticker": tk,
                "side": h["side"], "n": h["n"], "price": h["px"], "ladder_n": h.get("depth"),
                "asked": h.get("asked", h["n"]), "ask_size": h.get("depth"), "live": True}))
            side_n[h["side"]] += h["n"]
            side_c[h["side"]] += h["n"] * h["px"]
            fee += h["n"] * fee_pc(h["px"], fr)
        for x in m.get("refusals", []):
            ev.append((m["close"] - x["tau"], {
                "kind": "refused", "gate": x["gate"], "ticker": _tk(x["series"], m["close"]),
                "close_s": m["close"], "tau": x["tau"], "budget_left": x.get("bleft"),
                "budget": x.get("budget"), "spent": x.get("spent"),
                "size_now": cfg["SIZE"], "t": ep_iso(m["close"] - x["tau"])}))
        # a bogus `realised`: if anything read the logs' money it would show
        ev.append((m["close"] + 20, {"kind": "settled", "t": ep_iso(m["close"] + 20),
                                     "ticker": tk, "realised": 999.0, "pnl_c": 99900}))
        ev.append((m["close"] + 5, {"kind": "close_summary", "t": ep_iso(m["close"] + 5),
                                    "close": m["close"]}))
        xn = m.get("ledger_extra_n", 0.0)
        if xn:
            s0 = m["fills"][0]["want"]
            side_n[s0] += xn
            side_c[s0] += xn * m["fills"][0]["px"]
        if m.get("in_ledger", True):
            ledger["%s|x" % tk] = {
                "ticker": tk, "market_result": m["result"],
                "yes_count_fp": "%.10f" % side_n["yes"], "no_count_fp": "%.10f" % side_n["no"],
                "yes_total_cost_dollars": "%.10f" % side_c["yes"],
                "no_total_cost_dollars": "%.10f" % side_c["no"],
                "fee_cost": "%.10f" % (fee + m.get("fee_bump", 0.0)),
                "settled_time": ep_iso(m["close"] + 5)}
    for extra in cfg.get("extra_ledger", []):
        ledger["%s|x" % extra["ticker"]] = extra
    ev.sort(key=lambda x: x[0])
    recs += [r for _, r in ev]
    return ledger, [{"path": "pinrun-live-selftest.jsonl", "recs": recs}]


def _run_world(spec, cfg, policies, lo, hi, fee_rate=FEE_RATE, keep=None, bounds=False):
    cfg = dict(cfg, fee_rate=fee_rate)
    led_rows, runs = _world(spec, cfg)
    ledger = ledger_from_rows(led_rows)       # the real loader: pin filter + pinledger.pnl
    fills, hedges, refusals = extract(runs)
    if keep is not None:
        keep.update(fills=fills, refusals=refusals, runs=runs, led_rows=led_rows)
    fn = score_bounds if bounds else score
    return fn(ledger, fills, hedges, lo, hi, policies, fee_rate)


def selftest():
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    import tempfile
    base = iso_ep("2026-09-23T14:00:00Z")
    lo, hi = base - 1, base + 86400
    third_n = THIRD * 90.0

    # 0. plumbing
    ck(close_ep_of_ticker("KXBTC15M-26SEP220745-45") == iso_ep("2026-09-22T11:45:00Z"),
       "a ticker's ET stamp 07:45 on 09-22 is 11:45Z (EDT, UTC-4)")
    ck(et_day(iso_ep("2026-09-22T00:15:00Z")) == "2026-09-21",
       "a close at 00:15Z belongs to the PREVIOUS ET day")
    ck(_tk("KXETH15M", iso_ep("2026-09-22T11:45:00Z")) == "KXETH15M-26SEP220745-45",
       "the self-test's ticker builder round-trips")
    ck(abs(Z80 - 2.801585) < 1e-6, "80 %% power at two-sided 5 %%: z = 1.959964 + 0.841621 "
       "(%.6f)" % Z80)
    ck(not losing(-0.004) and losing(-0.006) and not losing(0.0),
       "a losing close is under -$0.005: a cent of fee rounding is not a loss")
    d100 = [1.0, -1.0] * 50
    sd100 = math.sqrt(100.0 / 99.0)
    fake = [{"close": base + 900 * i, "live": 0.0, "pol": {"FULL": x, "THIRD": 0.0},
             "lo": {"FULL": x}} for i, x in enumerate(d100)]
    need, sd_, nu = closes_needed(fake, "FULL", "THIRD", 1.0)
    ck(need == int(math.ceil((Z80 * sd100) ** 2)) == 8 and abs(sd_ - sd100) < 1e-9 and nu == 100,
       "closes needed = ceil((z80 x sd / gap)^2): sd %.4f, $1 gap -> %s closes" % (sd100, need))
    need2, _sd2, nu2 = closes_needed(fake[:2], "FULL", "THIRD", 1.0,
                                     watched=[base + 900 * i for i in range(10)])
    ck(nu2 == 10 and need2 == int(math.ceil((Z80 * math.sqrt(2.0 / 9.0)) ** 2)),
       "closes needed is in WATCHED closes: 2 traded + 8 watched-only closes count as 10 "
       "(%s, %s)" % (nu2, need2))

    # 1. PLANTED: FULL wins by exactly X. 10 closes, one winning early leg each,
    #    a third of SIZE 90 at 95c, 500 offered at 95c.
    spec = [{"series": "KXBTC15M", "close": base + 900 * i, "result": "yes",
             "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                        "count": third_n, "touch": 500.0}]} for i in range(10)]
    pol = {"THIRD": THIRD, "FULL": FULL, "OFF": 0.0}
    rows, st, dg = _run_world(spec, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, bounds=True)
    per = 1.0 - 0.95 - fee_pc(0.95)
    X = 10 * (90.0 - third_n) * per
    live = sum(r["live"] for r in rows)
    full = sum(r["pol"]["FULL"] for r in rows)
    off = sum(r["pol"]["OFF"] for r in rows)
    ck(len(rows) == 10, "10 closes in, 10 closes scored (n = closes)")
    ck(abs(live - 10 * third_n * per) < 1e-6,
       "LIVE is the ledger: %.4f == 10 x %.2f x %.6f" % (live, third_n, per))
    ck(abs((full - live) - X) < 1e-6,
       "PLANTED: FULL beats LIVE by exactly $%.4f (got $%.4f)" % (X, full - live))
    ck(all(abs(r["lo"]["FULL"] - r["pol"]["FULL"]) < 1e-12 and r["flagged"]["FULL"] == 0
           for r in rows),
       "PLANTED: nothing unlogged -> FULL-lo == FULL on every close")
    ck(abs((off - live) + 10 * third_n * per) < 1e-6,
       "OFF removes exactly the early legs' P&L (-$%.4f)" % (10 * third_n * per))
    ck(all(abs(r["pol"]["THIRD"] - r["live"]) < 1e-9 for r in rows),
       "a policy equal to the run's own size changes NOTHING (THIRD == LIVE)")
    pb, pbest = boot({"LIVE": [r["live"] for r in rows],
                      "FULL": [r["pol"]["FULL"] for r in rows],
                      "OFF": [r["pol"]["OFF"] for r in rows]}, "LIVE", ["FULL", "OFF"], B=500)
    ck(pb["FULL"] == 1.0 and pb["OFF"] == 0.0 and pbest["FULL"] == 1.0,
       "the bootstrap sees it: P(FULL>LIVE) 1.0, P(OFF>LIVE) 0.0, FULL best 1.0")
    ck(st["FULL"]["scaled_up"] == 10 and st["FULL"]["depth_cap"] == 0,
       "all 10 scaled up, none depth-capped (500 offered > 90 wanted)")
    sec, n_p = section_policy("T", rows, ["LIVE", "FULL", "OFF"], "LIVE", ["FULL", "OFF"], 200)
    ck(n_p == 0 and any("no P value below 30 closes" in x for x in sec)
       and all("1.00" not in x.split("   ")[-1] for x in sec if x.startswith("  ALL")),
       "10 closes print NO P value (floor 30): with this few, one close decides it")

    # 2. NULL: no early legs at all -- every policy ties LIVE exactly
    specn = [{"series": "KXETH15M", "close": base + 900 * i, "result": ("yes" if i % 3 else "no"),
              "fills": [{"leg": "full", "want": "yes", "tau": 12, "px": 0.96, "n": 50.0}]}
             for i in range(12)]
    rows, st, dg = _run_world(specn, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, bounds=True)
    ck(all(abs(r["pol"][k] - r["live"]) < 1e-12 and abs(r["lo"][k] - r["live"]) < 1e-12
           for r in rows for k in pol),
       "NULL: with no early leg, THIRD == FULL == FULL-lo == OFF == LIVE on every close")
    pb, pbest = boot({"LIVE": [r["live"] for r in rows],
                      "FULL": [r["pol"]["FULL"] for r in rows],
                      "OFF": [r["pol"]["OFF"] for r in rows]}, "LIVE", ["FULL", "OFF"], B=500)
    ck(pb["FULL"] == 0.5 and pb["OFF"] == 0.5,
       "NULL: exact ties read P = 0.50, not a win (got %.2f, %.2f)" % (pb["FULL"], pb["OFF"]))
    ck(mde([0.0] * 12)[0] == 0.0, "NULL: zero spread -> zero MDE, no division blow-up")
    ck(mde([1.0])[0] is None, "one close has no power and says so")

    # 2b. NULL with signs: early legs at 50c, fee-free, win/lose alternate --
    #     scaling up is worth exactly nothing on average
    specs = [{"series": "KXSOL15M", "close": base + 900 * i, "result": ("yes" if i % 2 else "no"),
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.50, "n": third_n,
                         "count": third_n, "touch": 500.0, "ladder": [[0.50, 500.0]]}]}
             for i in range(40)]
    rows, st, dg = _run_world(specs, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, fee_rate=0.0)
    d = [r["pol"]["FULL"] - r["live"] for r in rows]
    pb, _ = boot({"LIVE": [r["live"] for r in rows], "FULL": [r["pol"]["FULL"] for r in rows]},
                 "LIVE", ["FULL"], B=2000)
    ck(abs(sum(d)) < 1e-6 and 0.3 < pb["FULL"] < 0.7,
       "NULL (random sign): FULL - LIVE sums to 0 and P(FULL>LIVE) = %.2f, near a coin flip"
       % pb["FULL"])
    sec, n_p = section_policy("T", rows, ["LIVE", "FULL"], "LIVE", ["FULL"], 300)
    ck(n_p > 0 and not any("no P value below" in x for x in sec),
       "40 closes (over the floor) do print P values")

    # 3. CAPPED DEPTH: 30 at 95c and 15 at 96c under the limit, taper depth 45
    specc = [{"series": "KXXRP15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 30.0, "sd": 45.0,
                         "ladder": [[0.95, 30.0], [0.96, 15.0], [0.99, 900.0]]}]}]
    rows, st, dg = _run_world(specc, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    want_cap = (30.0 - third_n) * (1 - 0.95 - fee_pc(0.95)) + 15.0 * (1 - 0.96 - fee_pc(0.96))
    got = rows[0]["pol"]["FULL"] - rows[0]["live"]
    ck(abs(got - want_cap) < 1e-6,
       "CAPPED: FULL buys only the 45 offered under the 98c limit, the last 15 at 96c "
       "(+$%.4f, got +$%.4f); the 900 at 99c are over the limit" % (want_cap, got))
    ck(st["FULL"]["depth_cap"] == 1, "and the tally says it was depth-capped")
    # the same book, but the signal was logged 2 s before the order (the second
    # ticked): the +-3 s fallback still finds it; 5 s before -> no book at all
    specc2 = [{"series": "KXXRP15M", "close": base, "result": "yes",
               "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                          "count": third_n, "touch": 45.0, "sig_dt": 2,
                          "ladder": [[0.95, 30.0], [0.96, 15.0], [0.99, 900.0]]}]}]
    rows, st, dg = _run_world(specc2, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want_cap) < 1e-6
       and st["FULL"]["uncapped"] == 0,
       "SIGNAL 2 s before the order: paired within 3 s, same 45-contract cap (%+.4f)"
       % (rows[0]["pol"]["FULL"] - rows[0]["live"]))
    specc2[0]["fills"][0]["sig_dt"] = 5
    rows, st, dg = _run_world(specc2, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(st["FULL"]["uncapped"] == 1, "SIGNAL 5 s before: not paired -> no book -> flagged uncapped")
    # partial fill: asked 29.97, got 10 -> the book at landing held 10; FULL cannot beat it
    specp = [{"series": "KXXRP15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": 10.0,
                         "count": third_n, "touch": 500.0}]}]
    rows, st, dg = _run_world(specp, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"]) < 1e-9 and st["FULL"]["partial_cap"] == 1,
       "CAPPED: an order that filled 10 of the 29.97 it asked is not scaled up at all")
    # no signal record -> uncapped, flagged; a WINNER -> FULL-lo holds it at 0
    specu = [{"series": "KXXRP15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "sig": False}]}]
    rows, st, dg = _run_world(specu, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, bounds=True)
    ck(st["FULL"]["uncapped"] == 1 and abs(rows[0]["pol"]["FULL"] - rows[0]["live"]
                                             - (90.0 - third_n) * (1 - 0.95 - fee_pc(0.95))) < 1e-6,
       "no logged book -> scaled to SIZE at the fill's own price and FLAGGED uncapped")
    ck(abs(rows[0]["lo"]["FULL"] - rows[0]["live"]) < 1e-9 and rows[0]["flagged"]["FULL"] == 1,
       "FULL-lo: that unlogged gain is held at 0 (FULL-lo == LIVE there)")

    # 3b. SIZE and band multiples come from the log, not the start record alone
    rows, st, dg = _run_world(spec[:1], {"SIZE": 90.0, "start_size": 60.0, "autosize": True,
                                          "ef": THIRD}, pol, lo, hi, keep={})
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - (90.0 - third_n) * per) < 1e-6,
       "AUTOSIZE: the start said 60, an autosize record said 90 before the fill -> FULL is 90")
    band_n = THIRD * 90.0 * 1.5
    specbm = [{"series": "KXBTC15M", "close": base, "result": "yes",
               "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": band_n,
                          "count": band_n, "touch": 500.0}]}]
    rows, st, dg = _run_world(specbm, {"SIZE": 90.0, "ef": THIRD, "mpc": 3,
                                       "bands": [[0.94, 0.97, 1.5]]}, pol, lo, hi)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - (135.0 - band_n) * per) < 1e-6,
       "BAND: a 95c early fill in a 1.5x band -> FULL = 1.5 x SIZE = 135, not 90")

    # 4. TOP-UP: a third early at 95c, then 60.03 topped up at 97c (tau 20).
    #    FULL holds 90 early, so staged_take leaves the top-up nothing.
    spect = [{"series": "KXBNB15M", "close": base, "result": "no",
              "fills": [{"leg": "early", "want": "no", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0},
                        {"leg": "topup", "want": "no", "tau": 20, "px": 0.97,
                         "n": 90.0 - third_n, "touch": 500.0, "ladder": [[0.97, 500.0]]}]}]
    rows, st, dg = _run_world(spect, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    want = (90.0 - third_n) * (1 - 0.95 - fee_pc(0.95)) - (90.0 - third_n) * (1 - 0.97 - fee_pc(0.97))
    got = rows[0]["pol"]["FULL"] - rows[0]["live"]
    ck(abs(got - want) < 1e-6 and st["FULL"]["topup_trimmed"] == 1,
       "TOP-UP: FULL swaps the 97c top-up for 95c early contracts: +$%.4f (got +$%.4f)"
       % (want, got))
    ck(abs(rows[0]["pol"]["OFF"] - rows[0]["live"] + third_n * (1 - 0.95 - fee_pc(0.95))) < 1e-6,
       "TOP-UP: OFF drops the early leg and keeps the top-up as it was")
    # inside the last 10 s the top-up may complete to 1.5 x SIZE (late_mult):
    # FULL's 90 early contracts leave it 45 of the 105.03 it bought, not 0
    late_n = 1.5 * 90.0 - third_n
    spect2 = [{"series": "KXBNB15M", "close": base, "result": "no",
               "fills": [{"leg": "early", "want": "no", "tau": 40, "px": 0.95, "n": third_n,
                          "count": third_n, "touch": 500.0},
                         {"leg": "topup", "want": "no", "tau": 8, "px": 0.97, "n": late_n,
                          "touch": 500.0, "ladder": [[0.97, 500.0]]}]}]
    rows, st, dg = _run_world(spect2, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    per97 = 1 - 0.97 - fee_pc(0.97)
    want = (90.0 - third_n) * per - (late_n - 45.0) * per97
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want) < 1e-6,
       "LATE TOP-UP: at 8 s the market may hold 1.5 x SIZE, so FULL keeps 45 of the top-up "
       "(%+.4f, got %+.4f)" % (want, rows[0]["pol"]["FULL"] - rows[0]["live"]))

    # 5. HEDGE: the early leg loses; hedged at 30c at tau 35 (before any top-up)
    hp = 0.30
    spech = [{"series": "KXHYPE15M", "close": base, "result": "no",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0}],
              "hedge": {"side": "no", "n": third_n, "px": hp, "tau": 35, "depth": 500.0}}]
    rows, st, dg = _run_world(spech, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, bounds=True)
    hpc = 1 - hp - fee_pc(hp)
    live1 = rows[0]["live"]
    ck(abs(live1 - (third_n * hpc - third_n * (0.95 + fee_pc(0.95)))) < 1e-6,
       "HEDGE: LIVE is the ledger's one row, entry and hedge together ($%.4f)" % live1)
    want_full = (90.0 - third_n) * (hpc - 0.95 - fee_pc(0.95))
    ck(abs(rows[0]["pol"]["FULL"] - live1 - want_full) < 1e-6,
       "HEDGE: FULL scales the early entry AND its hedge 3x ($%+.4f)" % want_full)
    ck(st["FULL"]["hedge_depth_unread"] == 1 and st["FULL"]["hedge_depth_cap"] == 0,
       "HEDGE: ladder_n at/over what was asked = depth past it never read -> "
       "uncapped and FLAGGED as an upper bound")
    ck(rows[0]["flagged"]["FULL"] == 1
       and abs(rows[0]["lo"]["FULL"] - live1 - min(0.0, want_full)) < 1e-9,
       "HEDGE: a scaled-up hedge (priced at its AVERAGE price) puts the market in FULL-lo's "
       "set: FULL-lo = LIVE + min(FULL's change, 0)")
    ck(abs(rows[0]["pol"]["OFF"]) < 1e-6,
       "HEDGE: OFF removes the entry and the whole hedge it caused (market -> $0)")
    # asked 29.97, only 20 under the limit (ladder_n 20 < asked: a REAL depth),
    # 10 filled -> 10 more were there; FULL's hedge is 10 + 10 = 20, not 30.03
    spech[0]["hedge"].update(n=10.0, depth=20.0, asked=third_n)
    rows, st, dg = _run_world(spech, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    want_hcap = (90.0 - third_n) * (-0.95 - fee_pc(0.95)) + 10.0 * hpc
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want_hcap) < 1e-6
       and st["FULL"]["hedge_depth_cap"] == 1 and st["FULL"]["hedge_depth_unread"] == 0,
       "HEDGE CAPPED: 20 offered, 10 filled -> FULL's hedge stops at 20 (%+.4f, got %+.4f)"
       % (want_hcap, rows[0]["pol"]["FULL"] - rows[0]["live"]))
    ck(abs(rows[0]["pol"]["OFF"]) < 1e-6,
       "HEDGE CAPPED: OFF still removes the entry and all 10 hedge contracts")
    # the hedge scales with the position held WHEN IT FIRED: a 60-contract
    # full leg bought after the hedge does not change FULL's hedge size
    spech2 = [{"series": "KXHYPE15M", "close": base, "result": "no",
               "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                          "count": third_n, "touch": 500.0},
                         {"leg": "full", "want": "yes", "tau": 20, "px": 0.95, "n": 60.0,
                          "count": 60.0, "touch": 500.0}],
               "hedge": {"side": "no", "n": third_n, "px": hp, "tau": 35, "depth": 500.0}}]
    rows, st, dg = _run_world(spech2, {"SIZE": 90.0, "ef": THIRD, "mpc": 3}, pol, lo, hi)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want_full) < 1e-6,
       "HEDGE TIMING: only contracts held at the hedge's second set its scale; a later leg "
       "does not (%+.4f, got %+.4f)" % (want_full, rows[0]["pol"]["FULL"] - rows[0]["live"]))

    # 6. BUDGET: three coins' early legs in one close, budget 2 x SIZE, no extra coin
    specb = [{"series": s, "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 42 - j, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0}]}
             for j, s in enumerate(["KXBTC15M", "KXETH15M", "KXSOL15M"])]
    rows, st, dg = _run_world(specb, {"SIZE": 90.0, "ef": THIRD, "mpc": 2, "extra": None},
                              pol, lo, hi)
    want = 2 * (90.0 - third_n) * per - third_n * per
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want) < 1e-6
       and st["FULL"]["budget_cap"] == 1,
       "BUDGET: at FULL the first two coins spend the close budget and the third coin's "
       "early leg never happens (%+.4f)" % want)
    # the rebuilt budget is pinrun.close_budget_for: the extra-coin allowance
    # is for a NEW coin only; the last-seconds allowance for any market
    fb = {"SIZE": 90.0, "mpc": 2, "ticker": "KXBTC15M-26SEP231000-00", "extra": 1.0,
          "late_extra": 0.0, "late_extra_tau": 0.0, "tau": 20.0}
    ck(budget_for(fb, {"KXETH15M"}) == 270.0 and budget_for(fb, set()) == 180.0
       and budget_for(fb, {"KXBTC15M"}) == 180.0,
       "BUDGET REBUILT: a new coin gets the extra coin (270); the first coin or a held coin "
       "does not (180)")
    fl_ = dict(fb, extra=0.0, late_extra=1.0, late_extra_tau=10.0, tau=8.0)
    ck(budget_for(fl_, set()) == 270.0 and budget_for(fl_, {"KXBTC15M"}) == 270.0
       and budget_for(dict(fl_, tau=12.0), set()) == 180.0,
       "BUDGET REBUILT: inside the last 10 s any market gets the late allowance (270); at "
       "12 s it does not (180)")

    # 7. CALIBRATION direction: a full-size run scaled DOWN takes the cheapest contracts
    specd = [{"series": "KXZEC15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40,
                         "px": (30 * 0.95 + 60 * 0.97) / 90.0, "n": 90.0, "count": 90.0,
                         "touch": 30.0, "ladder": [[0.95, 30.0], [0.97, 60.0]]}]}]
    led, runs = _world(specd, {"SIZE": 90.0, "ef": 1.0})
    rows, st, dg = _run_world(specd, {"SIZE": 90.0, "ef": 1.0}, pol, lo, hi)
    fl, _, _ = extract(runs)
    c = cost_curve(fl[0])
    ck(abs(c(90.0) - (90.0 * fl[0]["px"] + fl[0]["fee_total"])) < 1e-9
       and abs(cost_curve(fl[0], mode="add")(90.0) - c(90.0)) < 1e-9
       and abs(cost_curve(fl[0], mode="add")(0.0)) < 1e-9,
       "the price curve reproduces the actual fill's cost exactly at the actual size, in both "
       "modes, and costs nothing at 0")
    ck(fl[0]["move"] is None, "a sweep up the logged ladder (95c then 97c) is not a 'move'")
    # decided at a 92c touch, swept to an average of 96.7c along the LOGGED
    # ladder -- 4.7c over the decided price, but exactly what the book said;
    # not a move. (The real 09-18 02:30 ET DOGE fill at 97.8c is NOT this:
    # its logged ladder under the 98c limit held only 62 at 92c, so the book
    # it landed on had changed -> 'dearer'.)
    _l, runs_sw = _world([{"series": "KXDOGE15M", "close": base, "result": "yes",
                           "fills": [{"leg": "early", "want": "yes", "tau": 40,
                                      "px": (10 * 0.92 + 20 * 0.99) / 30.0, "sig_px": 0.92,
                                      "n": 30.0, "count": 30.0, "limit": 0.99,
                                      "ladder": [[0.92, 10.0], [0.99, 100.0]]}]}],
                         {"SIZE": 90.0, "ef": 1.0})
    fsw = extract(runs_sw)[0][0]
    ck(fsw["move"] is None and abs(fsw["exp_px"] - fsw["px"]) < 1e-9,
       "a fill 4.7c over the DECIDED price that the logged ladder explains is a sweep, not a "
       "move (reference = the ladder's price for that size, %.4f)" % fsw["exp_px"])
    shift = (90.0 * fl[0]["px"] + fl[0]["fee_total"]
             - (30 * (0.95 + fee_pc(0.95)) + 60 * (0.97 + fee_pc(0.97)))) / 90.0
    want = (third_n * 1.0 - (third_n * (0.95 + fee_pc(0.95)) + shift * third_n)) \
        - (90.0 - (90.0 * fl[0]["px"] + fl[0]["fee_total"]))
    ck(abs(rows[0]["pol"]["THIRD"] - rows[0]["live"] - want) < 1e-6,
       "CALIBRATION: THIRD of a full-size fill keeps the cheapest 29.97 at 95c (%+.4f)" % want)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"]) < 1e-12,
       "CALIBRATION: FULL of a full-size run is the run itself")
    # the leg OFF (early window 30 s = the regular window): every fill's early
    # fraction is 0, and the era reads 'off'
    kp = {}
    _run_world(specn[:2], {"SIZE": 90.0, "ef": THIRD, "early_tau_max": 30}, pol, lo, hi, keep=kp)
    ck(all(f["ef"] == 0.0 for f in kp["fills"])
       and eras(kp["runs"], lo - 7200, hi).startswith("off "),
       "LEG OFF (early window 30 s): early fraction 0 on every fill, era 'off' (%s)"
       % eras(kp["runs"], lo - 7200, hi)[:20])

    # 6b. LOGGED BUDGET beats the rebuilt one: budget_left says 100 (the start
    #     record would rebuild 180); coin 2 is cut to 10, coin 3 to 0
    specl = [{"series": s_, "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 42 - j, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0, "bleft": 100.0 - j * third_n}]}
             for j, s_ in enumerate(["KXBTC15M", "KXETH15M", "KXSOL15M"])]
    rows, st, dg = _run_world(specl, {"SIZE": 90.0, "ef": THIRD, "mpc": 2, "extra": None},
                              pol, lo, hi)
    want = (100.0 - 3 * third_n) * per
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want) < 1e-6
       and st["FULL"]["budget_logged"] == 3 and st["FULL"]["budget_cap"] == 2,
       "BUDGET (logged): FULL spends exactly the 100 the bot said was left (%+.4f, got %+.4f)"
       % (want, rows[0]["pol"]["FULL"] - rows[0]["live"]))

    # 6c. LATER LEG SQUEEZED: FULL's early coin eats the room a later full leg used
    specq = [{"series": "KXBTC15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0, "bleft": 120.0}]},
             {"series": "KXETH15M", "close": base, "result": "yes",
              "fills": [{"leg": "full", "want": "yes", "tau": 12, "px": 0.96, "n": 90.03,
                         "count": 90.03, "touch": 500.0, "bleft": 120.0 - third_n}]}]
    rows, st, dg = _run_world(specq, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    per96 = 1 - 0.96 - fee_pc(0.96)
    want = (90.0 - third_n) * per - (90.03 - 30.0) * per96
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want) < 1e-6
       and st["FULL"]["later_leg_squeezed"] == 1
       and abs(st["FULL"]["later_leg_contracts_cut"] - 60.03) < 1e-6,
       "SQUEEZE: FULL's 90 early contracts leave the 12 s ETH leg 30, not 90.03 (%+.4f)" % want)
    ck(st["OFF"]["room_bound_as_run"] == 1,
       "SQUEEZE: and OFF flags that ETH leg as budget-bound as run (upside NOT modelled)")

    # 6d. REFUSAL tallies: what section D counts, per policy
    def refusal_world(ef, n_early):
        return [{"series": "KXBTC15M", "close": base, "result": "yes",
                 "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": n_early,
                            "count": n_early, "touch": 500.0}],
                 "refusals": [{"gate": "close_budget", "series": "KXETH15M", "tau": 20,
                               "bleft": 0.0},
                              {"gate": "close_budget", "series": "KXSOL15M", "tau": 18,
                               "bleft": None},
                              {"gate": "close_budget", "series": "KXXRP15M", "tau": 45,
                               "bleft": 0.0},
                              {"gate": "max_per_market", "series": "KXBTC15M", "tau": 22,
                               "bleft": 60.0}]}]
    kp = {}
    rows, st, dg = _run_world(refusal_world(THIRD, third_n), {"SIZE": 90.0, "ef": THIRD},
                              pol, lo, hi, keep=kp)
    _l, nm = not_modelled("T", rows, kp["fills"], kp["refusals"], lo, hi)
    ck(nm["close_budget"] == 3 and nm["freed_off"] == 1 and nm["freed_third"] == 0
       and nm["unread"] == 1 and nm["mpm_early"] == 1,
       "REFUSALS in a THIRD-size hour: the leg OFF would have freed room for the ETH refusal, "
       "a third frees NOTHING (it already ran at a third); 1 unreadable; the one BEFORE the "
       "early fill not counted; the early market's max_per_market counted (%s)" % nm)
    kp = {}
    rows, st, dg = _run_world(refusal_world(1.0, 90.0), {"SIZE": 90.0, "ef": 1.0},
                              pol, lo, hi, keep=kp)
    _l, nm = not_modelled("T", rows, kp["fills"], kp["refusals"], lo, hi)
    ck(nm["freed_third"] == 1 and nm["freed_off"] == 1
       and abs(nm["freed_third_contracts"] - 90.0 * (1 - THIRD)) < 1e-6
       and abs(nm["freed_off_contracts"] - 90.0) < 1e-6,
       "REFUSALS in a FULL-size hour: a third would have freed 60.03 of the 90 early "
       "contracts, off all 90 (%s)" % nm)

    # 6e. STATUS: this page never names a winner, however strong the planted gap
    specv = [{"series": "KXBTC15M", "close": base + 900 * i, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95 - 0.001 * (i % 7),
                         "n": third_n, "count": third_n, "touch": 500.0}]} for i in range(40)]
    rows, st, dg = _run_world(specv, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, bounds=True)
    w1, why1 = status_line(rows, [r["close"] for r in rows], terms="(B1 terms)")
    ck(w1 == "REPORT ONLY" and "B1" in why1
       and not any(x in why1 for x in ("CALLED", "BEATS", "TRAILS"))
       and "40 closes since the change" in why1 and "40 with an early-leg market" in why1,
       "STATUS: 40 closes with FULL ahead on every one still names NO winner -- it points at "
       "B1 (%s)" % why1[:90])
    ck("verdict" not in globals(), "the old re-checked CALLED rule is gone, not merely unused")

    # 7b. PAPER ARM JOIN: the .out is TRUNCATED on restart, so it names only
    #     the newest log; the older log with identical settings is found by its
    #     start record; a concurrent twin and another arm's log are not
    tdir = tempfile.mkdtemp(prefix="earlyhindsight_")
    try:
        tk1, tk2 = _tk("KXBTC15M", base), _tk("KXETH15M", base + 900)
        st_full = {"kind": "start", "mode": "paper", "early_frac": 1.0, "early_tau_max": 45,
                   "size": 20.0, "pin": 0.995, "code_sha": "a"}
        logs = {"pinrun-paper-20260923T100000Z.jsonl": [
                    dict(st_full, t=ep_iso(base - 600)),
                    {"kind": "signal", "t": ep_iso(base - 40), "ticker": tk1, "leg": "early",
                     "size": 500.0, "take_n": 20.0},
                    {"kind": "settled", "t": ep_iso(base + 20), "ticker": tk1, "want": "yes",
                     "pnl_c": -1900.0},
                    {"kind": "settled", "t": ep_iso(base + 35), "ticker": tk1, "want": "no",
                     "pnl_c": 1400.0}],
                "pinrun-paper-20260923T100005Z.jsonl": [    # a concurrent twin: same settings
                    dict(st_full, t=ep_iso(base - 590)),
                    {"kind": "settled", "t": ep_iso(base + 20), "ticker": tk1, "want": "yes",
                     "pnl_c": 55500.0}],
                "pinrun-paper-20260923T110000Z.jsonl": [    # the restart (new code, same flags)
                    dict(st_full, t=ep_iso(base + 300), code_sha="b"),
                    {"kind": "settled", "t": ep_iso(base + 920), "ticker": tk2, "want": "yes",
                     "pnl_c": 100.0}],
                "pinrun-paper-20260923T120000Z.jsonl": [    # another arm: early_frac 0.333,
                    dict(st_full, t=ep_iso(base + 1000), early_frac=0.333),   # clear of the rest
                    {"kind": "settled", "t": ep_iso(base + 1820), "ticker": _tk("KXBTC15M",
                                                                                base + 1800),
                     "want": "yes", "pnl_c": 99900.0}]}
        for name, recs in logs.items():
            with open(os.path.join(tdir, name), "w", encoding="utf-8") as fh:
                fh.write("\n".join(json.dumps(r) for r in recs) + "\n")
        with open(os.path.join(tdir, "arm-early-full.out"), "w", encoding="utf-8") as fh:
            fh.write("SELF-TEST -- pinrun\n  ok   the log line in a test name is not a log\n"
                     "  log C:\\x\\pinrun-paper-20260923T110000Z.jsonl\n")
        ps = arm_logs(tdir, "early-full", since_ep=base - 3600)
        by, info, tkc = paper_by_close(ps)
        ck([os.path.basename(x) for x in ps] == ["pinrun-paper-20260923T100000Z.jsonl",
                                                  "pinrun-paper-20260923T110000Z.jsonl"]
           and abs(by.get(base, 0) - (-5.0)) < 1e-9 and abs(by.get(base + 900, 0) - 1.0) < 1e-9
           and info["early_signals"] == 1 and info["early_full_size"] == 1,
           "PAPER: the .out names only the restart's log; the earlier log with the same "
           "settings is found, the hedge's settled record nets (-19 + 14 = -5); the concurrent "
           "twin and the other arm's log are not read (%s)" % by)
        ck(arm_logs(tdir, "early-full", since_ep=base + 7200)
           == [os.path.join(tdir, "pinrun-paper-20260923T110000Z.jsonl")],
           "PAPER: a log that ended before the window is not added")
        ck(arm_logs(tdir, "early-off") == [], "PAPER: an arm with no .out scores nothing")

        # 7g. freeze_rows: B1's entry point, on real-shaped files; the caller's
        #     ledger snapshot wins over the file
        specm1 = [{"series": "KXBTC15M", "close": base, "result": "yes",
                   "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95,
                              "n": third_n, "count": third_n, "touch": 500.0}]},
                  {"series": "KXETH15M", "close": base, "result": "yes", "ledger_extra_n": 10.0,
                   "fills": [{"leg": "full", "want": "yes", "tau": 12, "px": 0.96, "n": 20.0}]},
                  {"series": "KXSOL15M", "close": base, "result": "yes", "in_ledger": False,
                   "fills": [{"leg": "full", "want": "yes", "tau": 11, "px": 0.96, "n": 5.0}]}]
        led_rows, runs_ = _world(specm1, {"SIZE": 90.0, "ef": THIRD})
        with open(os.path.join(tdir, "kalshi_ledger.json"), "w", encoding="utf-8") as fh:
            json.dump({"settlements": led_rows, "written": ep_iso(base + 60)}, fh)
        with open(os.path.join(tdir, "pinrun-live-20260923T120000Z.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in runs_[0]["recs"]) + "\n{\"kind\": \"ord")
        fr = freeze_rows(base - 600, tdir, now_s=base + 60)
        r0 = fr["rows"][0] if fr["rows"] else {}
        ck(len(fr["rows"]) == 1 and r0["close"] == base and r0["mismatch"] == 1
           and r0["not_in_ledger"] == 1 and abs(r0["full_lo"] - r0["full"]) < 1e-12
           and abs(r0["full"] - r0["live"] - (90.0 - third_n) * per) < 1e-6
           and len(r0["tickers"]) == 2 and len(fr["code_sha256"] or "") == 64,
           "freeze_rows: one row for the close; the ETH market the ledger holds 10 more of is a "
           "MISMATCH, the SOL fill with no ledger row is NOT IN LEDGER, FULL scales the early "
           "leg, the code hash is attached (%s)"
           % {k: r0.get(k) for k in ("mismatch", "not_in_ledger", "flagged")})
        snap = json.loads(json.dumps(led_rows))
        for v in snap.values():
            v["fee_cost"] = "%.10f" % (float(v["fee_cost"]) + 1.0)
        fr2 = freeze_rows(base - 600, tdir, now_s=base + 60, ledger_rows=snap)
        ck(abs(fr2["rows"][0]["live"] - (r0["live"] - 2.0)) < 1e-9,
           "freeze_rows: the caller's ledger snapshot is the one scored (a $1 fee on each of "
           "2 markets moves LIVE by exactly -$2)")
        with open(os.path.join(tdir, "lf.py"), "wb") as fh:
            fh.write(b"a = 1\nb = 2\n")
        with open(os.path.join(tdir, "crlf.py"), "wb") as fh:
            fh.write(b"a = 1\r\nb = 2\r\n")
        ck(code_sha256(os.path.join(tdir, "lf.py")) == code_sha256(os.path.join(tdir, "crlf.py"))
           and code_sha256(os.path.join(tdir, "nope.py")) is None,
           "the pinned code hash reads CRLF as LF (a Windows checkout hashes like git's)")
    finally:
        for fn in os.listdir(tdir):
            os.remove(os.path.join(tdir, fn))
        os.rmdir(tdir)

    # 7c. OLD RECORD SHAPE: no `want` on order or signal; a NO buy is body side
    #     'ask'. Must score exactly like the new shape (it once read side None
    #     for every order before 09-21 and every policy went wild).
    for shape in (False, True):
        spo = [{"series": "KXHYPE15M", "close": base, "result": "no",
                "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                           "count": third_n, "touch": 500.0, "old_format": shape}],
                "hedge": {"side": "no", "n": third_n, "px": hp, "tau": 35, "depth": 500.0}},
               {"series": "KXBTC15M", "close": base + 900, "result": "no",
                "fills": [{"leg": "early", "want": "no", "tau": 40, "px": 0.95, "n": third_n,
                           "count": third_n, "touch": 500.0, "old_format": shape}]}]
        rows, st, dg = _run_world(spo, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
        got = [round(r["pol"][k] - r["live"], 9) for r in rows for k in ("FULL", "OFF")]
        if not shape:
            new_shape = got
    want_o = [round(want_full, 9), round(-live1, 9), round((90.0 - third_n) * per, 9),
              round(-third_n * per, 9)]
    ck(got == new_shape and all(abs(a - b) < 1e-6 for a, b in zip(got, want_o))
       and dg["hedged_markets"] == 1 and dg["entry_count_mismatch"] == 0,
       "OLD SHAPE: body side 'bid'/'ask' with no want scores exactly like want=yes/no "
       "(%s vs %s)" % (got, new_shape))

    # 7d. ROUNDING: the ledger's fee is a cent over the logs'. OFF removes the
    #     market -> exactly $0, not -$0.01, and not a losing close.
    specf = [{"series": "KXBTC15M", "close": base, "result": "yes", "fee_bump": 0.01,
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0}]}]
    rows, st, dg = _run_world(specf, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(rows[0]["pol"]["OFF"] == 0.0 and st["OFF"]["removed_markets"] == 1
       and abs(st["OFF"]["removed_residue_abs"] - 0.01) < 1e-9
       and abs(rows[0]["live"] - (third_n * per - 0.01)) < 1e-9,
       "ROUNDING: a removed market is exactly $0 and the cent of fee rounding is reported, "
       "not booked as a loss")

    # 7e. PRICE-THROUGH: decided at 97.6c, landed at 11c (09-18 04:15 DOGE
    #     shape), hedged at 74c, lost. The landing book was never logged.
    specm = [{"series": "KXDOGE15M", "close": base, "result": "no",
              "fills": [{"leg": "early", "want": "yes", "tau": 32, "px": 0.11, "sig_px": 0.976,
                         "n": third_n, "count": third_n, "touch": 34.0, "sd": 2301.0,
                         "ladder": [[0.976, 34.0], [0.977, 434.0]]}],
              "hedge": {"side": "no", "n": third_n, "px": 0.74, "tau": 31, "depth": 398.0}}]
    kp = {}
    rows, st, dg = _run_world(specm, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, keep=kp,
                              bounds=True)
    fm = kp["fills"][0]
    extra = 90.0 - third_n
    walk_x = (34.0 - third_n) * (0.976 + fee_pc(0.976)) + (90.0 - 34.0) * (0.977 + fee_pc(0.977))
    shift_m = 0.11 + fee_pc(0.11) - 0.976 - fee_pc(0.976)
    h_up = extra * (1 - 0.74 - fee_pc(0.74))
    d_land = -(walk_x + shift_m * extra) + h_up
    d_dec = -walk_x + h_up
    ck(fm["move"] == "through" and abs(rows[0]["pol"]["FULL"] - rows[0]["live"]) < 1e-9
       and st["FULL"]["through_cap"] >= 1,
       "PRICE-THROUGH: FULL holds the fill at what filled -- it does NOT buy 60 more at the "
       "collapsed 11c (FULL - LIVE = $0)")
    ck(abs(st["FULL"]["through_at_landing"] - d_land) < 1e-6
       and abs(st["FULL"]["through_at_decision"] - d_dec) < 1e-6
       and abs(rows[0]["lo"]["FULL"] - rows[0]["live"] - min(d_land, d_dec, 0.0)) < 1e-6,
       "PRICE-THROUGH: the landing reading (%+.2f) and the decision-book reading (%+.2f) are "
       "both reported; FULL-lo takes the worst (%+.2f)" % (d_land, d_dec, min(d_land, d_dec)))
    ck(d_land > 0 > d_dec and rows[0]["lo"]["FULL"] < rows[0]["pol"]["FULL"],
       "PRICE-THROUGH: the old landing-price reading turned this LOSER into a FULL win; "
       "FULL-lo does not")
    rows, st, dg = _run_world(spec[:1], {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, keep=kp)
    ck(kp["fills"][0]["move"] is None and st["FULL"]["through_cap"] == 0,
       "a fill at the decided price is not a move")
    specdr = [{"series": "KXBTC15M", "close": base, "result": "yes",
               "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.97, "sig_px": 0.94,
                          "n": third_n, "count": third_n, "touch": 500.0,
                          "ladder": [[0.94, 500.0]]}]}]
    rows, st, dg = _run_world(specdr, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, keep=kp,
                              bounds=True)
    ck(kp["fills"][0]["move"] == "dearer" and st["FULL"]["dearer_markets"] == 1
       and rows[0]["lo"]["FULL"] <= rows[0]["pol"]["FULL"] + 1e-12
       and abs(rows[0]["lo"]["FULL"] - rows[0]["live"]) < 1e-9,
       "DEARER: landed 3c over the logged book -> flagged; its (winning) FULL gain is held "
       "at 0 in FULL-lo")

    # 7f. REFUSALS before v-safety1 carry budget and spent, not budget_left
    specr2 = [{"series": "KXBTC15M", "close": base, "result": "yes",
               "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                          "count": third_n, "touch": 500.0}],
               "refusals": [{"gate": "close_budget", "series": "KXETH15M", "tau": 20,
                             "budget": 180.0, "spent": 180.0}]}]
    kp = {}
    rows, st, dg = _run_world(specr2, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, keep=kp)
    _l, nm = not_modelled("T", rows, kp["fills"], kp["refusals"], lo, hi)
    ck(nm["freed_off"] == 1 and nm["unread"] == 0 and kp["refusals"][0]["bleft"] == 0.0,
       "REFUSALS: an old record's budget - spent (0) is read as budget_left (%s)" % nm)

    # 8. LEDGER AUTHORITY: a market the logs never saw; a coin-race row; bogus realised
    spec8 = [{"series": "KXBTC15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0}]}]
    ghost = {"ticker": _tk("KXDOGE15M", base), "market_result": "no", "no_count_fp": "10.00",
             "no_total_cost_dollars": "9.500000", "yes_total_cost_dollars": "0",
             "fee_cost": "0.030000", "settled_time": ep_iso(base + 5)}
    race = {"ticker": _tk("KXCRYPTOLEAD15M", base), "market_result": "yes",
            "yes_count_fp": "1.00", "yes_total_cost_dollars": "0.9", "fee_cost": "0",
            "settled_time": ep_iso(base + 5)}
    wti = {"ticker": _tk("KXWTI15M", base), "market_result": "yes",
           "yes_count_fp": "5.00", "yes_total_cost_dollars": "4.0", "fee_cost": "0",
           "settled_time": ep_iso(base + 5)}
    rows, st, dg = _run_world(spec8, {"SIZE": 90.0, "ef": THIRD,
                                      "extra_ledger": [ghost, race, wti]}, pol, lo, hi)
    g_pnl = pinledger.pnl(ghost)
    ck(abs(rows[0]["live"] - (third_n * per + g_pnl)) < 1e-6,
       "LEDGER: LIVE = the early market + the market the logs never saw; the coin race and "
       "commodity rows are not pin money; the logs' realised 999 is never read")
    ck(abs((rows[0]["pol"]["OFF"] - rows[0]["live"]) + third_n * per) < 1e-6
       and abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - (90.0 - third_n) * per) < 1e-6
       and dg["markets_without_log_fills"] == 1,
       "LEDGER: the unseen market is identical in every policy and counted once "
       "(%d)" % dg["markets_without_log_fills"])

    if fails:
        raise SystemExit("earlyhindsight selftest: FAILED -- %d check(s): %s"
                         % (len(fails), "; ".join(fails)))
    print("earlyhindsight selftest: OK")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--results", default=LIVE_RESULTS,
                    help="where the live logs and kalshi_ledger.json are READ from")
    ap.add_argument("--out", default=OUT_MD, help="markdown written here")
    ap.add_argument("--boot", type=int, default=B_BOOT)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    lines, err = build_report(a.results, time.time(), B=a.boot)
    if lines is None:
        print("earlyhindsight: " + err + " -- loaded nothing")
        return 1
    txt = "\n".join(lines)
    print(txt)
    try:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("# EARLY_HINDSIGHT -- written by research/earlyhindsight.py\n\n```\n"
                     + txt + "\n```\n")
        print("\nwritten: " + a.out)
    except OSError as e:
        print("\ncould not write %s: %s" % (a.out, e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
