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
  never below what actually filled. Depth is the larger of the touch size in
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
  the policy's position at that second, capped (when scaling up) at the
  largest hedge-side depth the hedge records logged.
* Close budget. Early legs are resized in time order inside each close, and
  each one is capped by what the policy has left of the close budget
  (MAX_PER_CLOSE x SIZE, plus the extra-coin allowance for a coin not yet
  held). A FULL early leg can therefore SHRINK a later early leg in the same
  close, exactly as the bot would.

WHAT IT DOES NOT MODEL (and counts, so the reader can see how often it bites)

* Later full-window legs of OTHER markets in a close are not squeezed by a
  bigger early leg's budget use. The report counts the closes where FULL's
  contracts would have exceeded the budget and how many close_budget
  refusals the bot actually logged.
* OFF does not hand a market to the <=30 s window. The critic measured that
  163 of 203 early-leg markets were never offered at 90-98c later (tape), so
  OFF mostly loses them; where a top-up exists OFF keeps only the top-up,
  which is a lower bound for OFF on those markets (counted).
* THIRD in the calibration era cannot add top-ups the full-size bot never
  sent; it is a lower bound where the later window had depth (counted).
* max-per-market / max-per-close COUNT caps, hedge timing changes, and any
  change in which market a scan picks.

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
Z80 = 1.959964 + 0.841621                # two-sided 5 %, 80 % power
B_BOOT = 10000

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
                        "tau": fnum(r.get("tau")), "bleft": fnum(r.get("budget_left")),
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
            fills.append({
                "ticker": tk, "close": close_ep_of_ticker(tk), "t": t,
                "leg": leg, "want": r.get("want"),
                "filled": filled, "count": count, "px": px, "fee_total": fee_total,
                "limit": limit, "tau": tau,
                "sig_price": fnum((sig or {}).get("price"), px),
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
def cost_curve(fill, fee_rate=FEE_RATE):
    """cost(n) in dollars incl. fee for n contracts of this fill, anchored so
    cost(actual filled) == actual cost exactly."""
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
    return lambda n: walk(n) + shift * n


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


def resize_close(fills, g, stats=None):
    """{fill index: policy contracts} for the fills of ONE close, in time
    order, at early fraction g (None = actual).

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


def score(ledger, fills, hedges, lo_ep, hi_ep, policies, fee_rate=FEE_RATE):
    """Per-close money for LIVE and each policy, plus diagnostics.

    policies: {name: early fraction, or None for LIVE-as-run}. Closes are the
    pin-series ledger rows with lo_ep < close <= hi_ep."""
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
    stats = {name: collections.Counter() for name in policies}
    diag = collections.Counter()
    early_mk = set()
    rows = []
    curves = {}
    for ce in sorted(by_close_mk):
        cf = fills_by_close.get(ce, [])
        sizes = {name: resize_close(cf, g, stats[name])
                 for name, g in policies.items()}
        live = 0.0
        pol = {name: 0.0 for name in policies}
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
            for name in policies:
                delta = 0.0
                for i, f in mf:
                    n_new = sizes[name][i]
                    if abs(n_new - f["filled"]) < 1e-12:
                        continue
                    if i not in curves:
                        curves[i] = cost_curve(f, fee_rate)
                    if n_new > f["filled"] + 1e-9 and                             sum(q for _, q in (f.get("ladder") or [])) < n_new - 1e-9:
                        stats[name]["priced_past_logged_ladder"] += 1
                    w = win_of(f["want"], res)
                    c = curves[i]
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
                            if h_extra is None:
                                # depth past what was asked was never read:
                                # an UPPER bound on FULL's hedge, flagged
                                stats[name]["hedge_depth_unread"] += 1
                            elif nh_new > nh + h_extra + 1e-9:
                                nh_new = nh + h_extra
                                stats[name]["hedge_depth_cap"] += 1
                        stats[name]["hedges_resized"] += 1
                        delta += hpnl_pc * (nh_new - nh)
                pol[name] += row["pnl"] + delta
        rows.append({"close": ce, "day": et_day(ce), "live": live, "pol": pol,
                     "early_markets": n_early, "markets": len(by_close_mk[ce])})
    # log fills whose market has no ledger row (unsettled / not refreshed)
    led_set = set(ledger)
    diag["log_fills_not_in_ledger"] = sum(
        1 for f in fills if f["close"] is not None and lo_ep < f["close"] <= hi_ep
        and f["ticker"] not in led_set)
    diag["early_markets"] = len(early_mk)
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
def arm_logs(results_dir, arm):
    """Every paper log an arm's results/arm-<name>.out has named (a restart
    appends a new `log ...` line), oldest first. The paper start record
    carries no arm name, so the .out file is the only reliable join."""
    p = os.path.join(results_dir, "arm-%s.out" % arm)
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except OSError:
        return []
    hits = re.findall(r"^\s*log\s+(\S*pinrun-paper-\d{8}T\d{6}Z\.jsonl)\s*$", txt, re.M)
    out = []
    for h in hits:
        q = os.path.join(results_dir, os.path.basename(h))
        if q not in out:
            out.append(q)
    return sorted(out)


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


def table(rows, cols, base, names, label_fn, B):
    """Per-ET-day lines + a cumulative line. cols: names incl. base."""
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
    for label, rs in groups:
        n = len(rs)
        vals = {c: [label_fn(r, c) for r in rs] for c in cols}
        tot = {c: sum(vals[c]) for c in cols}
        pc = "/".join("%+.2f" % (tot[c] / n) if n else "-" for c in cols)
        lose = "/".join("%d" % sum(1 for v in vals[c] if v < -1e-9) for c in cols)
        pb, _ = boot(vals, base, names, B=(B if label == "ALL" else min(B, 3000)), seed=11)
        ps = " ".join(("%8.2f" % pb[k]) if pb[k] is not None else "       -" for k in names)
        out.append("  %-10s %6d " % (label, n) + " ".join("%10s" % money(tot[c]) for c in cols)
                   + "   " + pc + "   " + lose + "   " + ps)
    return out


def section_policy(title, rows, cols, base, names, B, note_lines=()):
    out = ["", title, "-" * len(title)]
    out.extend(note_lines)
    if not rows:
        out.append("  no settled pin closes in this window yet (n = 0): nothing to compare.")
        return out
    lab = (lambda r, c: r["live"] if c == base else r["pol"][c])
    cols_v = {c: [lab(r, c) for r in rows] for c in cols}
    out.append("  minimum detectable difference (80 %% power, 5 %% two-sided), n = %d closes:"
               % len(rows))
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
    out.extend(table(rows, cols, base, names, lab, B))
    _, pbest = boot(cols_v, base, cols, B=B, seed=13)
    out.append("  chance each is the BEST of %s over the whole window (close-clustered "
               "bootstrap): %s" % ("/".join(cols), ", ".join("%s %.2f" % (k, pbest[k])
                                                           for k in cols)))
    return out


STAT_KEYS = [
    ("scaled_up", "early legs scaled up"),
    ("depth_cap", "capped by the depth logged at that second"),
    ("partial_cap", "capped at an IOC partial fill"),
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
    ("hedges_scaled_up", "hedges scaled up"),
    ("hedge_depth_cap", "hedge scale-up capped by logged depth"),
    ("hedge_depth_unread", "hedge scale-up with depth past `asked` never read -> UPPER bound"),
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


FLOOR = 30          # CLAUDE.md: floor cluster counts before claiming anything


def verdict(rows, base, names):
    """(status word, one line). COLLECTING until at least FLOOR closes hold an
    early-leg market AND a policy is apart from LIVE by more than the MDE with
    bootstrap P outside [0.05, 0.95]."""
    k = sum(1 for r in rows if r["early_markets"])
    if not rows or k < FLOOR:
        return "COLLECTING", ("%d settled closes since the change, %d of them with an early-leg "
                              "market; nothing is called before %d such closes"
                              % (len(rows), k, FLOOR))
    lab = (lambda r, c: r["live"] if c == base else r["pol"][c])
    cols = {c: [lab(r, c) for r in rows] for c in [base] + list(names)}
    pb, _ = boot(cols, base, names, B=4000, seed=23)
    calls = []
    for c in names:
        d = [a - b for a, b in zip(cols[c], cols[base])]
        _sd, _m1, mt = mde(d)
        tot = sum(d)
        if mt is not None and abs(tot) > mt and (pb[c] > 0.95 or pb[c] < 0.05):
            calls.append("%s %s LIVE by $%.2f (MDE $%.2f, P %.2f)"
                         % (c, "BEATS" if tot > 0 else "TRAILS", abs(tot), mt, pb[c]))
    if not calls:
        return "COLLECTING", ("%d closes (%d with an early-leg market); no policy is apart "
                              "from LIVE by more than the MDE" % (len(rows), k))
    return "CALLED", "; ".join(calls)


def closes_needed(rows, a, b, per_close):
    """Closes needed to detect `per_close` dollars a close between policies a
    and b at 80 % power, from the per-close spread in `rows`."""
    d = [r["pol"][a] - (r["live"] if b == "LIVE" else r["pol"][b]) for r in rows]
    sd, _m1, _mt = mde(d)
    if not sd:
        return None, sd
    return int(math.ceil((Z80 * sd / per_close) ** 2)), sd


def not_modelled(lab, rows, fills, refusals, lo, hi):
    """Section D lines for one era: how often the bounds the model does not
    capture were live."""
    out = []
    closes = {r["close"] for r in rows}
    early_c = {r["close"] for r in rows if r["early_markets"]}
    early_mk = {f["ticker"] for f in fills if f["leg"] == "early"
                and f["close"] in early_c}
    early_n = collections.defaultdict(list)          # close -> [(t, contracts)]
    for f in fills:
        if f["leg"] == "early" and f["close"] in early_c:
            early_n[f["close"]].append((f["t"] or 0, f["filled"]))
    cb = [x for x in refusals if x["gate"] == "close_budget" and lo < x["close"] <= hi]
    cb_mk = {(x["close"], x["ticker"]) for x in cb}
    cb_early = {(x["close"], x["ticker"]) for x in cb if x["close"] in early_c}
    freed = set()
    unread = set()
    for x in cb:
        if x["close"] not in early_c:
            continue
        held_early = sum(n for t, n in early_n[x["close"]] if t <= (x["t"] or 0))
        if held_early <= 0:
            continue
        if x["bleft"] is None:
            unread.add((x["close"], x["ticker"]))
        elif x["bleft"] + held_early >= 1.0:
            freed.add((x["close"], x["ticker"]))
    mpm = {(x["close"], x["ticker"]) for x in refusals
           if x["gate"] == "max_per_market" and lo < x["close"] <= hi}
    mpm_early = {k for k in mpm if k[1] in early_mk}
    out.append("  %s: %d closes, %d with an early-leg market. close_budget refused %d markets "
               "(%d distinct close/market pairs in closes that also traded; %d in early-leg "
               "closes)." % (lab, len(closes), len(early_c), len(cb_mk),
                             len({k for k in cb_mk if k[0] in closes}), len(cb_early)))
    out.append("     of those in early-leg closes, OFF/THIRD would have had >= 1 contract of "
               "room for %d (budget_left + the early contracts held); %d refusals carry no "
               "budget_left (before v-safety1) -- this upside for a SMALLER early leg is NOT "
               "modelled." % (len(freed), len(unread)))
    out.append("     max_per_market refused %d market-closes, %d of them early-leg markets "
               "(FULL buys in one fill, freeing a slot a late boost could use: NOT modelled)."
               % (len(mpm), len(mpm_early)))
    return out, {"close_budget": len(cb_mk), "cb_early": len(cb_early), "freed": len(freed),
                 "unread": len(unread), "mpm": len(mpm), "mpm_early": len(mpm_early)}


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
    rows_a, st_a, dg_a = score(ledger, fills, hedges, dep, hi_a, pa)
    pc = {"THIRD": THIRD, "FULL": FULL, "OFF": 0.0}
    rows_c, st_c, dg_c = score(ledger, fills, hedges, cal, dep, pc)
    rows_f = [r for r in rows_c if r["close"] >= fix]
    word, why = verdict(rows_a, "LIVE", ["FULL", "OFF"])

    lines.append("EARLY HINDSIGHT -- the 31-45 s leg at a third (live) vs full size vs off")
    lines.append("generated %s; ledger newest settlement %s; %d live run logs read "
                 "(read-only)" % (ep_iso(now_ep), newest[:19] + "Z", len(runs)))
    lines.append("")
    lines.append("STATUS: %s -- %s." % (word, why))
    for a_, b_ in (("FULL", "THIRD"), ("OFF", "THIRD")):
        src = rows_f if len(rows_f) >= 10 else rows_c
        srcn = "since the fixes" if src is rows_f else "09-17..09-22"
        for pcl in (0.50, 1.00):
            need, sd = closes_needed(src, a_, b_, pcl)
            if need is not None:
                lines.append("  to see a $%.2f/close gap %s vs %s at 80%% power needs ~%d closes "
                             "(per-close spread $%.2f, calibration %s, %d closes)"
                             % (pcl, a_, b_, need, sd, srcn, len(src)))
    lines.append("")
    lines.append("Money: Kalshi's ledger (pinledger.pnl), pin series only; n = closes. Every "
                 "policy = LIVE + a delta on early-leg entries, their hedge share, top-ups and "
                 "budget-squeezed later legs, priced on the book the bot logged (counterfactual, "
                 "not fills). ET days.")

    # ---- A: since v-early-third
    lines += section_policy(
        "A. SINCE v-early-third (closes after %s; live runs the early leg at a third)" % DEPLOY,
        rows_a, ["LIVE", "FULL", "OFF"], "LIVE", ["FULL", "OFF"], B,
        ["  LIVE = actual (third). FULL = early entries at full size, capped by the depth "
         "logged at that second and by the bot's own budget_left. OFF = early entries and "
         "their hedge share removed (markets NOT handed to the <=30 s window)."])
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
        ps = [p for p in arm_logs(results_dir, arm) if os.path.exists(p)]
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
        lines.append("  arm-%s: %s (early_frac %s, early window to %s s, SIZE %s); started %s"
                     % (arm, ", ".join(os.path.basename(p) for p in ps), info["early_frac"],
                        info["early_tau_max"], info["size"],
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
        pb, _ = boot({"ARM": a_v, "LIVE": l_v}, "LIVE", ["ARM"], B=B, seed=17)
        lines.append("    MDE on %d shared closes (either traded): %s"
                     % (len(shared), "$%.2f total" % mt if mt is not None else "n < 2, none"))
        lines.append("    arm %s vs live %s ($/close %+.2f vs %+.2f); losing closes %d vs %d; "
                     "P(arm > live) %s"
                     % (money(sum(a_v)), money(sum(l_v)), sum(a_v) / len(shared),
                        sum(l_v) / len(shared),
                        sum(1 for v in a_v if v < -1e-9), sum(1 for v in l_v if v < -1e-9),
                        "%.2f" % pb["ARM"] if pb["ARM"] is not None else "-"))
        lines.append("    markets traded by both: %d; arm only: %d; live only: %d "
                     "(different markets = not like-for-like)" % (same, arm_only, live_only))

    # ---- C: calibration
    lines += section_policy(
        "C. CALIBRATION -- %s .. %s (mostly full size; a third on 09-17 13:05-19:35Z and "
        "09-18 03:02-16:31Z; off 09-18 01:48-03:00Z)" % (CAL_FROM, DEPLOY),
        rows_c, ["LIVE", "THIRD", "FULL", "OFF"], "LIVE", ["THIRD", "FULL", "OFF"], B,
        ["  calibration, not the test. LIVE = what actually ran. THIRD/FULL/OFF = every "
         "early entry resized to that policy (hours already at that size are unchanged)."])
    lines += section_policy(
        "C2. same, only since the fixes (closes from 09-20 00:00 ET = %s)" % FIXES_FROM,
        rows_f, ["LIVE", "THIRD", "FULL", "OFF"], "LIVE", ["THIRD", "FULL", "OFF"], B)
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
    lines.append("  FULL upper bounds: early entries with no logged depth A %d / C %d; hedge "
                 "scale-ups whose depth past `asked` was never read A %d / C %d; extra hedge "
                 "contracts priced at the market's average hedge price (a deeper hedge pays "
                 "more)." % (st_a["FULL"]["uncapped"], st_c["FULL"]["uncapped"],
                             st_a["FULL"]["hedge_depth_unread"],
                             st_c["FULL"]["hedge_depth_unread"]))
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
    looks = 2 * (len({r['day'] for r in rows_a}) + 1) + 3 * (len({r['day'] for r in rows_c}) + 1) \
        + 3 * (len({r['day'] for r in rows_f}) + 1)
    lines.append("")
    lines.append("Multiple looks: %d P-values on this page; by chance alone about %.1f of them "
                 "land under 0.05 or over 0.95. Per-day cells are description, not tests."
                 % (looks, looks * 0.10))
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
    Returns (ledger rows, runs) shaped exactly like the real files."""
    recs = [dict({"kind": "start", "t": ep_iso(min(m["close"] for m in spec) - 3600),
                  "early_tau_max": 45, "tau_max": 30, "size": cfg["SIZE"],
                  "early_frac": cfg["ef"], "max_per_close": cfg.get("mpc", 2),
                  "extra_coin": cfg.get("extra"), "band_mults": cfg.get("bands", []),
                  "late_tau": cfg.get("late_tau", 10), "late_mult": cfg.get("late_mult", 1.5)})]
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
            if f.get("sig", True):
                ev.append((m["close"] - f["tau"], {
                    "kind": "signal", "t": t, "ticker": tk, "want": f["want"], "price": px,
                    "size": f.get("touch", 500.0), "take_n": f.get("count", n),
                    "tau": f["tau"], "leg": f["leg"], "budget_left": f.get("bleft"),
                    "ladder": f.get("ladder", [[px, 500.0]])}))
            if f.get("sd") is not None:
                ev.append((m["close"] - f["tau"], {
                    "kind": "sweep_depth", "t": t, "ticker": tk, "want": f["want"],
                    "ladder": f["sd"], "now": min(cfg["SIZE"], f["sd"]), "was": f.get("count", n)}))
            ev.append((m["close"] - f["tau"] + 0.1, {
                "kind": "order", "t": t, "ticker": tk, "want": f["want"], "leg": f["leg"],
                "filled": n, "exec_price": px, "fee_total": ft, "limit_sent": f.get("limit", 0.98),
                "tau_at_send": f["tau"], "order_id": "o%d" % oid,
                "body": {"count": "%.2f" % f.get("count", n)}}))
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
                "size_now": cfg["SIZE"], "t": ep_iso(m["close"] - x["tau"])}))
        # a bogus `realised`: if anything read the logs' money it would show
        ev.append((m["close"] + 20, {"kind": "settled", "t": ep_iso(m["close"] + 20),
                                     "ticker": tk, "realised": 999.0, "pnl_c": 99900}))
        if m.get("in_ledger", True):
            ledger["%s|x" % tk] = {
                "ticker": tk, "market_result": m["result"],
                "yes_count_fp": "%.10f" % side_n["yes"], "no_count_fp": "%.10f" % side_n["no"],
                "yes_total_cost_dollars": "%.10f" % side_c["yes"],
                "no_total_cost_dollars": "%.10f" % side_c["no"],
                "fee_cost": "%.10f" % fee, "settled_time": ep_iso(m["close"] + 5)}
    for extra in cfg.get("extra_ledger", []):
        ledger["%s|x" % extra["ticker"]] = extra
    ev.sort(key=lambda x: x[0])
    recs += [r for _, r in ev]
    return ledger, [{"path": "pinrun-live-selftest.jsonl", "recs": recs}]


def _run_world(spec, cfg, policies, lo, hi, fee_rate=FEE_RATE, keep=None):
    cfg = dict(cfg, fee_rate=fee_rate)
    led_rows, runs = _world(spec, cfg)
    ledger = ledger_from_rows(led_rows)       # the real loader: pin filter + pinledger.pnl
    fills, hedges, refusals = extract(runs)
    if keep is not None:
        keep.update(fills=fills, refusals=refusals)
    return score(ledger, fills, hedges, lo, hi, policies, fee_rate)


def selftest():
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

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

    # 1. PLANTED: FULL wins by exactly X. 10 closes, one winning early leg each,
    #    a third of SIZE 90 at 95c, 500 offered at 95c.
    spec = [{"series": "KXBTC15M", "close": base + 900 * i, "result": "yes",
             "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                        "count": third_n, "touch": 500.0}]} for i in range(10)]
    pol = {"THIRD": THIRD, "FULL": FULL, "OFF": 0.0}
    rows, st, dg = _run_world(spec, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
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

    # 2. NULL: no early legs at all -- every policy ties LIVE exactly
    specn = [{"series": "KXETH15M", "close": base + 900 * i, "result": ("yes" if i % 3 else "no"),
              "fills": [{"leg": "full", "want": "yes", "tau": 12, "px": 0.96, "n": 50.0}]}
             for i in range(12)]
    rows, st, dg = _run_world(specn, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(all(abs(r["pol"][k] - r["live"]) < 1e-12 for r in rows for k in pol),
       "NULL: with no early leg, THIRD == FULL == OFF == LIVE on every close")
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

    # 3. CAPPED DEPTH: 30 at 95c and 15 at 96c under the limit, taper depth 45
    specc = [{"series": "KXXRP15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 30.0, "sd": 45.0,
                         "ladder": [[0.95, 30.0], [0.96, 15.0], [0.99, 900.0]]}]}]
    rows, st, dg = _run_world(specc, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    want = (30.0 - third_n) * (1 - 0.95 - fee_pc(0.95)) + 15.0 * (1 - 0.96 - fee_pc(0.96))
    got = rows[0]["pol"]["FULL"] - rows[0]["live"]
    ck(abs(got - want) < 1e-6,
       "CAPPED: FULL buys only the 45 offered under the 98c limit, the last 15 at 96c "
       "(+$%.4f, got +$%.4f); the 900 at 99c are over the limit" % (want, got))
    ck(st["FULL"]["depth_cap"] == 1, "and the tally says it was depth-capped")
    # partial fill: asked 29.97, got 10 -> the book at landing held 10; FULL cannot beat it
    specp = [{"series": "KXXRP15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": 10.0,
                         "count": third_n, "touch": 500.0}]}]
    rows, st, dg = _run_world(specp, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"]) < 1e-9 and st["FULL"]["partial_cap"] == 1,
       "CAPPED: an order that filled 10 of the 29.97 it asked is not scaled up at all")
    # no signal record -> uncapped, flagged
    specu = [{"series": "KXXRP15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "sig": False}]}]
    rows, st, dg = _run_world(specu, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    ck(st["FULL"]["uncapped"] == 1 and abs(rows[0]["pol"]["FULL"] - rows[0]["live"]
                                             - (90.0 - third_n) * (1 - 0.95 - fee_pc(0.95))) < 1e-6,
       "no logged book -> scaled to SIZE at the fill's own price and FLAGGED uncapped")

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

    # 5. HEDGE: the early leg loses; hedged at 30c at tau 35 (before any top-up)
    hp = 0.30
    spech = [{"series": "KXHYPE15M", "close": base, "result": "no",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0}],
              "hedge": {"side": "no", "n": third_n, "px": hp, "tau": 35, "depth": 500.0}}]
    rows, st, dg = _run_world(spech, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
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
    ck(abs(rows[0]["pol"]["OFF"]) < 1e-6,
       "HEDGE: OFF removes the entry and the whole hedge it caused (market -> $0)")
    # asked 29.97, only 20 under the limit (ladder_n 20 < asked: a REAL depth),
    # 10 filled -> 10 more were there; FULL's hedge is 10 + 10 = 20, not 30.03
    spech[0]["hedge"].update(n=10.0, depth=20.0, asked=third_n)
    rows, st, dg = _run_world(spech, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    want_cap = (90.0 - third_n) * (-0.95 - fee_pc(0.95)) + 10.0 * hpc
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"] - want_cap) < 1e-6
       and st["FULL"]["hedge_depth_cap"] == 1 and st["FULL"]["hedge_depth_unread"] == 0,
       "HEDGE CAPPED: 20 offered, 10 filled -> FULL's hedge stops at 20 (%+.4f, got %+.4f)"
       % (want_cap, rows[0]["pol"]["FULL"] - rows[0]["live"]))
    ck(abs(rows[0]["pol"]["OFF"]) < 1e-6,
       "HEDGE CAPPED: OFF still removes the entry and all 10 hedge contracts")

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

    # 7. CALIBRATION direction: a full-size run scaled DOWN takes the cheapest contracts
    specd = [{"series": "KXZEC15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40,
                         "px": (30 * 0.95 + 60 * 0.97) / 90.0, "n": 90.0, "count": 90.0,
                         "touch": 30.0, "ladder": [[0.95, 30.0], [0.97, 60.0]]}]}]
    led, runs = _world(specd, {"SIZE": 90.0, "ef": 1.0})
    # the fill's fee is on its average price; the ladder's on each level -- the shift absorbs it
    rows, st, dg = _run_world(specd, {"SIZE": 90.0, "ef": 1.0}, pol, lo, hi)
    fl, _, _ = extract(runs)
    c = cost_curve(fl[0])
    ck(abs(c(90.0) - (90.0 * fl[0]["px"] + fl[0]["fee_total"])) < 1e-9,
       "the price curve reproduces the actual fill's cost exactly at the actual size")
    shift = (90.0 * fl[0]["px"] + fl[0]["fee_total"]
             - (30 * (0.95 + fee_pc(0.95)) + 60 * (0.97 + fee_pc(0.97)))) / 90.0
    want = (third_n * 1.0 - (third_n * (0.95 + fee_pc(0.95)) + shift * third_n)) \
        - (90.0 - (90.0 * fl[0]["px"] + fl[0]["fee_total"]))
    ck(abs(rows[0]["pol"]["THIRD"] - rows[0]["live"] - want) < 1e-6,
       "CALIBRATION: THIRD of a full-size fill keeps the cheapest 29.97 at 95c (%+.4f)" % want)
    ck(abs(rows[0]["pol"]["FULL"] - rows[0]["live"]) < 1e-12,
       "CALIBRATION: FULL of a full-size run is the run itself")

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

    # 6d. REFUSAL tallies: what section D counts
    specr = [{"series": "KXBTC15M", "close": base, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95, "n": third_n,
                         "count": third_n, "touch": 500.0}],
              "refusals": [{"gate": "close_budget", "series": "KXETH15M", "tau": 20,
                            "bleft": 0.5},
                           {"gate": "close_budget", "series": "KXSOL15M", "tau": 18,
                            "bleft": None},
                           {"gate": "close_budget", "series": "KXXRP15M", "tau": 45,
                            "bleft": 0.0},
                           {"gate": "max_per_market", "series": "KXBTC15M", "tau": 22,
                            "bleft": 60.0}]}]
    kp = {}
    rows, st, dg = _run_world(specr, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, keep=kp)
    _l, nm = not_modelled("T", rows, kp["fills"], kp["refusals"], lo, hi)
    ck(nm["close_budget"] == 3 and nm["freed"] == 1 and nm["unread"] == 1
       and nm["mpm_early"] == 1,
       "REFUSALS: 3 budget refusals; 1 a smaller early leg would have freed (0.5 left + 29.97 "
       "early), 1 unreadable (no budget_left), the one BEFORE the early fill not counted; the "
       "early market's max_per_market refusal counted (%s)" % nm)

    # 6e. VERDICT: COLLECTING under the floor and on a null; CALLED on a big planted gap
    w0, _ = verdict(rows, "LIVE", ["FULL", "OFF"])
    ck(w0 == "COLLECTING", "VERDICT: one close is COLLECTING, whatever it shows")
    specv = [{"series": "KXBTC15M", "close": base + 900 * i, "result": "yes",
              "fills": [{"leg": "early", "want": "yes", "tau": 40, "px": 0.95 - 0.001 * (i % 7),
                         "n": third_n, "count": third_n, "touch": 500.0}]} for i in range(40)]
    rows, st, dg = _run_world(specv, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi)
    w1, why1 = verdict(rows, "LIVE", ["FULL", "OFF"])
    ck(w1 == "CALLED" and "FULL BEATS" in why1 and "OFF TRAILS" in why1,
       "VERDICT: 40 closes, FULL ahead on every one -> CALLED (%s)" % why1)
    rows, st, dg = _run_world(specs, {"SIZE": 90.0, "ef": THIRD}, pol, lo, hi, fee_rate=0.0)
    w2, why2 = verdict(rows, "LIVE", ["FULL"])
    ck(w2 == "COLLECTING", "VERDICT: 40-close random-sign null stays COLLECTING (%s)" % why2)

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
    rows, st, dg = _run_world(spec8, {"SIZE": 90.0, "ef": THIRD, "extra_ledger": [ghost, race]},
                              pol, lo, hi)
    g_pnl = pinledger.pnl(ghost)
    ck(abs(rows[0]["live"] - (third_n * per + g_pnl)) < 1e-6,
       "LEDGER: LIVE = the early market + the market the logs never saw; the coin race row "
       "is not pin money; the logs' realised 999 is never read")
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
