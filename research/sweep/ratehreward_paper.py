#!/usr/bin/env python3
"""ratehreward_paper.py -- Treasury hourly ladder reward-pair PAPER recorder (spec 20261015-R1-C2-01, rule V2).

PAPER ONLY. GETs only: no order endpoint, no non-GET method, no request body anywhere in this file (the self-test
asserts it from the source text, rain_paper.py check 8). The only writes are results/ratehreward-paper.* files.
Spec: .sweep/hunt-2026-10-15/spec-20261015-R1-C2-01/SPEC.md (read it before changing a number here).

WHAT IT RECORDS (weekdays 07:00-20:59Z; one event per tenor-hour on KX2/5/7/10/30YRRATEH, ~75-80 strikes an hour,
each with a $10 / target 1,000 / 0.5-per-tick liquidity program over HH:00:00-HH:59:00 = 3,540 s)
  * the books (WebSocket orderbook_delta via research/livebook.LiveBook, imported) and the trade prints (same socket,
    `trade` channel) of every RATEH strike of the hour;
  * rule V2's ghost pairs: at HH:00:30, per tenor, y_hat = the ladder-implied yield (YES mid crosses 0.50); every
    strike 6.0 <= |K - y_hat| x 100 < 8.0 bp gets a GHOST 1,000 at $0.01 on the safe side + 1,100 at $0.01 on the dead
    side unless refused (blackout hour; program not listed or list unreadable; opposite best bid >= $0.99; others hold
    >= target/5 above 1c on the safe side AND the walk leaves our 1,000 a share < 0.01 there; the day risk budget is
    full). Ghosts are inserted into the scoring only -- nobody can react to them (spec risk 2);
  * SIBLING CANCEL (V2 step 5): the first dead-side 1c trade group reaching >= 100 lots on ANY RATEH strike >= 4 bp
    from its tenor's live y_hat this hour ends every V2 ghost at its WS receipt + 300 ms; nothing more posts that hour;
  * reward credit per ghost per second by the filed walk (post-July rule, no 99c exclusion; the old rule is logged),
    a second counting only when both sides reach the target incl. ours; $1 floor per market-period; x 0.9;
  * the cost side: other people's >= 500-lot dead-side 1c stacks (episodes: SWEPT / PULLED / PULLED_AFTER_SIBLING /
    SURVIVED, exposure per band x time-left cell, lambda_lo / lambda_hi), every >= 100-lot dead-side 1c sweep, the
    burst share at each sweeper hour's first sweep, and three ghost estimators: E_low (own-market prints, queue),
    E_main (dominance, pessimistic -- the bar's), and the imputation of unobservable hours (done in --report);
  * logged-only variants (hypotheses, never the verdict): V1 = V2 without the sibling cancel; V2w = band 5.0-8.0 bp;
    V2s = V2 + skip the hour after a sweeper hour;
  * the blackout list below, committed BEFORE the first run (BLS / BEA / Census / Fed / Treasury calendars, read
    2026-10-17).
  Close + 3 min: results per event (GET /markets?event_ticker=). Close + 10 min: AUDIT -- every WS trade must be in
  GET /markets/trades and vice versa, else the hour is `tape_gap` (excluded from the bar, counted).

WHAT IT CANNOT TELL: whether Kalshi pays a one-account 1c/1c pair (only the signed-off live probe of spec 6.6 can);
whether our real presence would create sweeper hours (ghosts are invisible; KILL item 3 is the proxy); the burst on
OUR stacks (measured only on other people's).

THE PRE-REGISTERED BAR -- SPEC section 6, verbatim (written 2026-10-17 before any recorder output exists):
  6.1 Population. Weekdays from the first full run day (planned Mon 2026-10-19), 07:00-20:59Z, NON-blackout hours, WS
  continuous (no seq gap > 5 s in the hour) and audit clean. Cluster = the HOUR (all 5 tenors together; the sweeper
  hits them together). `n` is reported as hours and as strike-hours, never trades.
  BLACKOUT (filled by the builder from the BLS/BEA/Fed/Treasury calendars BEFORE the first run, committed in RULES):
  the hour containing any 8:30 ET / 10:00 ET major release (CPI, PPI, payrolls, retail sales, GDP, PCE, claims if
  large), the FOMC statement and press-conference hours, and the hour of each 2/5/7/10/20/30-year auction result
  (13:00 ET). EDT until 11-01: 8:30 ET = the 12:59Z hour.
  6.2 PASS (-> put the live payment probe, 6.5, to the operator) -- all of:
    - >= 50 observable non-blackout hours on >= 5 weekdays;
    - V2 net-if-paid (credit floored x 0.9 minus E_main cost) >= +$2.00 per strike-hour posted, with the first sweep
      of each sweeper hour hitting one ghost and the burst share set to its 90% upper bound;
    - positive in both halves (first half of the days vs second half);
    - V2 mean credit-if-paid >= $5.00 per strike-hour;
    - >= 60 V2 strike-hours per weekday (else it cannot matter: 60 x $2 = $120/day).
  6.3 KILL (stop the recorder; the lone-pair RATEH family is dead) -- any of, after >= 3 weekdays / >= 30 hours:
    - V2 net-if-paid <= $0 per strike-hour at the POINT burst share (not the bound);
    - even E_low (own-market prints only, the kindest) V2 net-if-paid <= $0;
    - sweeper present in >= 80% of observable hours (it is presence-driven; our ghosts would make every hour a sweeper
      hour);
    - mean credit-if-paid < $3.00 (others took the pot);
    - RATEH programs not listed on 2 consecutive weekdays.
  Otherwise EXTEND to 10 weekdays with no rule change.
  6.4 Reproduction gate: `--history 2026-10-16` must reproduce the spec folder's 10-16 numbers (6-8 bp, stayed far: 6
  sweeps >= 500 lots over 3.15 stack-hours, all in the 16:59Z and 18:59Z hours) within +-1 sweep and +-10%
  stack-hours. A recorder that cannot reproduce a known day is not read.
  READS (spec 7): KILL read `ratehreward-paper-kill3` due 2026-10-21T21:30Z = Wed 10-21 5:30 PM ET (the 6.3 checks
  after 3 weekdays); PASS read `ratehreward-paper-bar5` due 2026-10-23T21:30Z = Fri 10-23 5:30 PM ET (the 6.2 bar).
  How: python research/sweep/ratehreward_paper.py --report

BUILDER'S CHOICES (the spec is silent; fixed here before any output, all in RULES and the start record)
  * budget order inside an hour: highest pair score at plan time first (our yes + no share with the pair inserted),
    ties by ticker; each variant has its own virtual pot, day budget and posts;
  * a "sweep" = consecutive dead-side 1c prints on one strike, each within 10 s of the previous (sweeps_new.group),
    firing when the running size reaches 100 lots (the receipt of the print that crossed); dead side from the live
    y_hat at that instant;
  * burst share = of the other >= 500-lot dead-side 1c stacks resting at a sweeper hour's first sweep, the share
    swept (a >= 100-lot sweep received) within the 300 ms cancel window; pooled over sweeper hours; its 90% upper
    bound = the upper end of the two-sided 90% Clopper-Pearson interval. Cost of a V2 sweeper hour with G ghosts
    resting at the first sweep = $11 x (pre + max(window_dominance, 1 + b x (G - 1))) + $10 per safe fill;
  * THE FIRST SWEEP (6.2 "hitting one ghost", 4.6; review fix 1, 2026-10-17): under V2 / V2w / V2s it takes ONE ghost
    -- the one on its own market, else the nearest (assumed) -- never every ghost it "dominates"; the others are lost
    only to real dominating sweeps landing before the cancel (window_dominance) or to b x (G - 1). V1 (no cancel)
    keeps dominance at the first sweep (the spec's V1 hour model). Before the fix a 5.5 bp first sweep cost V2 all 6
    ghosts ($66, = V1) at b = 0; it now costs $11;
  * after any fill a ghost stops earning in every variant (conservative for V1); E_low's credit ends at its first
    queue fill too;
  * yield OFF the ladder (every readable YES mid >= 0.5, or every one < 0.5; spec risk 6): the live y_hat is set to
    the top strike + 1 bp (bottom - 1 bp) and logged `yhat_off_ladder`, so the -$10 safe-side charge still fires at
    the ladder edges where the ghosts sit. Never used to plan (1.1: no crossing -> the tenor-hour is skipped);
  * a SILENT socket (no frame of any kind for > 300 s while an hour is subscribed, measured from max(last frame, the
    hour's subscribe)) is blind: the silent span inside [open, exit] counts as a WS gap (excluded by 6.1) and the
    socket is resynced. Evidence that a live RATEH socket is never that quiet: the tops of book changed in all 101
    REST polls 40-60 s apart of the 10-15 09Z hour (refuters' live_poll.jsonl / watch.jsonl) -- one hour only;
  * a >= 100-lot 1c print on one ticker that cannot be sided (its tenor had no y_hat: ladder non-monotone or
    unreadable) excludes the hour (`unclassified_1c`): its cost is unknown, never assumed zero;
  * the safe-side refusal (spec 1.3, "our safe share would be ~0"): >= 200 lots above 1c AND the walk's safe-side
    share for our 1,000 < 0.01 (200 at 2c leaves 0.67 -> posted; 200 at 10c 0.008 -> refused; 200 at 89c ~0);
  * blackout: the hour (HH:00-HH:59Z, the market's period) containing each event below; weekly claims are blacked
    out EVERY Thursday (the spec's "claims if large" cannot be judged ex ante); 10:00 ET majors = ISM manufacturing,
    ISM services, JOLTS; ECI is added to the 8:30 list (a quarterly wage print the rates market trades). The list
    covers 2026-10-19..2026-11-30 ET; any hour outside it is refused `blackout_list_not_covering` (never posted);
  * the book REST fallback of spec 2/10 is NOT built: at <= 1 book GET/s it would break the shared 1-call-per-2-s
    budget. A socket that is down or suspect makes the hour non-continuous (excluded), which is what 6.1 asks.
  * the hour's tickers are subscribed at HH-1:59:45 (spec: HH:00:00) so stacks posted at the open are seen from the
    first second.

FILES  results/ratehreward-paper.jsonl (UTC `t`, `ev`), .state.json (a snapshot; the LOG is the truth on restart),
       .stop (ends a running instance cleanly), .lock (one instance), start script results/start_ratehreward_paper.ps1;
       the self-test's scratch is results/ratehreward-paper.selftest-<pid>/ (removed when it ends)

    python research/sweep/ratehreward_paper.py --selftest
    python research/sweep/ratehreward_paper.py --once                 # plan the current/next hour over REST, print
    python -u research/sweep/ratehreward_paper.py --minutes 20160     # the paper run (14 days; stop file ends it)
    python research/sweep/ratehreward_paper.py --history 2026-10-16   # the 6.4 reproduction gate (~300 GETs)
    python research/sweep/ratehreward_paper.py --report               # the bar, per ET day and pooled
"""
import argparse
import collections
import hashlib
import json
import math
import os
import queue
import sys
import threading
import time
from array import array
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(RESEARCH)
RESULTS = os.path.join(REPO, "results")
sys.path.insert(0, RESEARCH)
import livebook  # noqa: E402  -- the WebSocket book (market data only); imported, never copied

LOG_PATH = os.path.join(RESULTS, "ratehreward-paper.jsonl")
STATE_PATH = os.path.join(RESULTS, "ratehreward-paper.state.json")
STOP_PATH = os.path.join(RESULTS, "ratehreward-paper.stop")
LOCK_PATH = os.path.join(RESULTS, "ratehreward-paper.lock")
UTC = timezone.utc
EPS = 1e-9

SERIES = ("KX2YRRATEH", "KX5YRRATEH", "KX7YRRATEH", "KX10YRRATEH", "KX30YRRATEH")
HOURS_Z = tuple(range(7, 21))          # hour opens 07:00Z .. 20:00Z (closes 07:59Z .. 20:59Z)
PERIOD_S = 3540.0                      # HH:00:00-HH:59:00
PX = 0.01
SAFE_N, DEAD_N = 1000.0, 1100.0
PLAN_S = 30.0                          # plan at HH:00:30
EXIT_S = 600.0                         # ghost expiry close-600 s
SUB_LEAD_S = 15.0                      # subscribe at open-15 s
DISCOVER_LEAD_S = 120.0                # HH-1:58:00
BAND_V2 = (6.0, 8.0)
BAND_V2W = (5.0, 8.0)
FAR_BP = 4.0                           # trigger / episode distance
TRIGGER_N = 100.0                      # sweep size that fires (and that E_main / E_low-whole count)
GROUP_GAP_S = 10.0                     # sweeps_new.group
EP_ON, EP_OFF = 500.0, 250.0
SWEPT_FRAC, SWEPT_WIN_S = 0.5, 10.0
SIBLING_PULL_S = 150.0
CANCEL_LAG_S = 0.300                   # first sweep's WS receipt + 300 ms
BURST_WINDOWS = (0.3, 1.0, 5.0)
DOMINANCE_BP = 0.5
SAFE_CROSS_BP = 1.0
DEAD_COST, SAFE_COST = 11.0, 10.0
CROSS_PX = 0.99
FLOOR_USD = 1.00
PAID_FRAC = 0.9
POT0 = 300.0
DAY_BUDGET_FRAC = 0.22
COLLATERAL_PER_PAIR = 21.0
NEAR_BP = 3.0
CREDIT_LAG_DAYS = 2                    # credits land 22-60 h later; the virtual pot books them 2 ET days later
BLIND_MAX_S = 5.0                      # 6.1: WS continuous (no gap > 5 s in the hour)
SILENT_S = 300.0                       # no frame at all for this long while subscribed = blind (risk 10), + resync
OFF_LADDER_BP = 1.0                    # yield off the ladder: y_hat = top strike + 1 bp (bottom - 1 bp)
SAFE_SHARE_MIN = 0.01                  # 1.3 "our safe share would be ~0": the walk's safe-side share below this
ERR_LOG_EVERY_S = 60.0                 # a repeating step() exception is logged at most once a minute (with a count)
FIRST_DAY = "2026-10-19"
VARIANTS = ("V2", "V1", "V2w", "V2s")
BAR_VARIANT = "V2"
REST_MIN_GAP_S = 3.0                   # <= 1 public call per 3 s: the per-IP limit is shared with the live bots and
                                       # a 2 s spacing already met a 429 on 10-17 (review); hard cap 1 per 2 s
REST_429_S = 10.0
PROG_PAGES_MAX = 10
TRADE_PAGES_MAX = 5
BUCKETS = [(0, 600), (600, 1200), (1200, 1800), (1800, 2400), (2400, 3000), (3000, 3600)]

# BLACKOUT -- (ET date, ET time, what). Sources read 2026-10-17: bls.gov/schedule/2026/10_sched_list.htm and
# 11_sched_list.htm; bea.gov/news/schedule; census.gov/retail/release_schedule.html; federalreserve.gov (FOMC
# 2026-10-27/28: statement 14:00 ET, press conference 14:30 ET, ~1 h); home.treasury.gov Tentative Auction Schedule
# (coupon auctions 2/5/7/10/20/30-year; results 13:00 ET). Weekly claims: every Thursday 8:30 ET (Wed 11-25,
# Thanksgiving week). Converted to UTC hours at run time (EDT until 2026-11-01 06:00Z, EST after).
BLACKOUT_ET = [
    ("2026-10-21", "13:00", "20Y auction"),
    ("2026-10-22", "08:30", "jobless claims"),
    ("2026-10-26", "13:00", "2Y auction"),
    ("2026-10-27", "13:00", "5Y auction"),
    ("2026-10-28", "14:00", "FOMC statement"),
    ("2026-10-28", "14:30", "FOMC press conference"),
    ("2026-10-28", "15:30", "FOMC press conference (second hour)"),
    ("2026-10-29", "08:30", "GDP advance Q3 + PCE (Sep) + jobless claims"),
    ("2026-10-29", "13:00", "7Y auction"),
    ("2026-10-30", "08:30", "Employment Cost Index Q3"),
    ("2026-11-02", "10:00", "ISM manufacturing"),
    ("2026-11-03", "10:00", "JOLTS"),
    ("2026-11-04", "10:00", "ISM services"),
    ("2026-11-05", "08:30", "jobless claims"),
    ("2026-11-06", "08:30", "Employment Situation (payrolls)"),
    ("2026-11-10", "08:30", "CPI"),
    ("2026-11-10", "13:00", "10Y auction"),
    ("2026-11-12", "08:30", "jobless claims"),
    ("2026-11-12", "13:00", "30Y auction"),
    ("2026-11-13", "08:30", "PPI"),
    ("2026-11-17", "08:30", "retail sales"),
    ("2026-11-18", "13:00", "20Y auction"),
    ("2026-11-19", "08:30", "jobless claims"),
    ("2026-11-23", "13:00", "2Y auction"),
    ("2026-11-24", "13:00", "5Y auction"),
    ("2026-11-25", "08:30", "GDP second Q3 + PCE (Oct) + jobless claims"),
    ("2026-11-25", "13:00", "7Y auction"),
]
BLACKOUT_FROM, BLACKOUT_TO = "2026-10-19", "2026-11-30"

RULES = dict(series=list(SERIES), hours_z=[HOURS_Z[0], HOURS_Z[-1]], plan_s=PLAN_S, exit_s=EXIT_S,
             band_v2=list(BAND_V2), band_v2w=list(BAND_V2W), far_bp=FAR_BP, trigger_n=TRIGGER_N,
             group_gap_s=GROUP_GAP_S, episode_on_off=[EP_ON, EP_OFF], swept=[SWEPT_FRAC, SWEPT_WIN_S],
             sibling_pull_s=SIBLING_PULL_S, cancel_lag_s=CANCEL_LAG_S, dominance_bp=DOMINANCE_BP,
             safe_cross_bp=SAFE_CROSS_BP, sizes=[SAFE_N, DEAD_N], price=PX, cost=[DEAD_COST, SAFE_COST],
             floor=FLOOR_USD, paid_frac=PAID_FRAC, pot=POT0, day_budget_frac=DAY_BUDGET_FRAC, near_bp=NEAR_BP,
             blind_max_s=BLIND_MAX_S, first_day=FIRST_DAY, variants=list(VARIANTS), bar_variant=BAR_VARIANT,
             silent_s=SILENT_S, off_ladder_bp=OFF_LADDER_BP, safe_share_min=SAFE_SHARE_MIN,
             first_sweep="V2/V2w/V2s: the first far sweep takes ONE ghost (its own market's, else the nearest, "
                         "assumed); the rest only by real dominating sweeps before the cancel or b x (G-1) in "
                         "--report. V1: dominance at the first sweep too (the spec's V1 hour model)",
             elow_credit_end="first queue fill, safe fill, cancel or exit, whichever is first",
             exclude_unclassified_1c_lots=TRIGGER_N,
             budget_order="pair score at plan desc, ticker", walk="post-July (no 99c exclusion); old rule logged",
             burst="pooled share of other >=500 1c stacks swept within 0.3 s of a sweeper hour's first sweep; "
                   "upper = two-sided 90% Clopper-Pearson upper end",
             blackout=BLACKOUT_ET, blackout_cover=[BLACKOUT_FROM, BLACKOUT_TO], rest_min_gap_s=REST_MIN_GAP_S,
             book_rest_fallback=False, paper_only=True)


# ================================================================================================ time
def iso(t):
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % int((t % 1) * 1000)


def iso_hour(t):
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%MZ")


def parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _nth_sunday(y, month, n):
    d = datetime(y, month, 1, tzinfo=UTC)
    return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))


def et_offset_h(t):
    """-4 (EDT) from the 2nd Sunday of March 07:00Z to the 1st Sunday of November 06:00Z, else -5 (EST).
    Copied from racereward_live.et_offset_h."""
    dt_ = datetime.fromtimestamp(t, UTC)
    a = _nth_sunday(dt_.year, 3, 2) + timedelta(hours=7)
    b = _nth_sunday(dt_.year, 11, 1) + timedelta(hours=6)
    return -4 if a <= dt_ < b else -5


def et_date(t):
    return (datetime.fromtimestamp(t, UTC) + timedelta(hours=et_offset_h(t))).strftime("%Y-%m-%d")


def et_label(t):
    return (datetime.fromtimestamp(t, UTC) + timedelta(hours=et_offset_h(t))).strftime("%a %m-%d %I:%M %p ET")


def et_to_utc(date_s, hm):
    """ET wall time -> UTC epoch, choosing the offset the instant itself is in."""
    wall = datetime.strptime(date_s + " " + hm, "%Y-%m-%d %H:%M").replace(tzinfo=UTC).timestamp()
    for off in (4, 5):
        t = wall + off * 3600
        if et_offset_h(t) == -off:
            return t
    return wall + 5 * 3600


def hour_open(t):
    return math.floor(t / 3600.0) * 3600.0


def is_trading_hour(o):
    d = datetime.fromtimestamp(o, UTC)
    return d.weekday() < 5 and d.hour in HOURS_Z


def blackout_map():
    out = collections.defaultdict(list)
    for d, hm, what in BLACKOUT_ET:
        out[hour_open(et_to_utc(d, hm))].append(what)
    return dict(out)


BLACKOUT = blackout_map()


def blackout_of(o):
    """(reason or None) for an hour open o. Outside the list's cover -> refused, never assumed clean."""
    day = et_date(o)
    if day < BLACKOUT_FROM or day > BLACKOUT_TO:
        return "blackout_list_not_covering"
    w = BLACKOUT.get(o)
    return ("blackout: " + "; ".join(w)) if w else None


# ================================================================================================ the filed walk
def f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def ticks_between(hi, lo):
    """linear_cent ticks from lo up to hi (0 when lo >= hi). racereward_live.ticks_between, linear branch."""
    if hi <= lo + 1e-9:
        return 0
    return int(round((hi - lo) * 100))


def walk(levels, target, df, ours=0.0, our_px=PX, old_rule=False):
    """The filed walk for ONE side (COPY of racereward_live.walk with the July change). `levels` = everyone else's
    bids {px: size}; `ours` = our size at our_px. Walk best-first adding whole levels; reference = the first level
    where the running size reaches target/5; stop where it reaches target; no qualifying bids if it never does.
    Score = df ** ticks below the reference x size. old_rule=True keeps the removed exclusion (best bid at the
    highest possible price, 99c -> nobody qualifies). Returns {q, ref, tot, share}."""
    lv = {round(p, 4): s for p, s in levels.items() if s > 0}
    if ours > 0:
        lv[round(our_px, 4)] = lv.get(round(our_px, 4), 0.0) + ours
    pxs = sorted(lv, reverse=True)
    if not pxs or (old_rule and pxs[0] >= 0.99 - 1e-9):
        return {"q": False, "ref": None, "tot": 0.0, "share": 0.0}
    tot, ref, used, reached = 0.0, None, [], False
    for p in pxs:
        tot += lv[p]
        used.append(p)
        if ref is None and tot >= target / 5.0 - 1e-9:
            ref = p
        if tot >= target - 1e-9:
            reached = True
            break
    if not reached:
        return {"q": False, "ref": ref, "tot": tot, "share": 0.0}
    s_all = sum(df ** ticks_between(ref, p) * lv[p] for p in used)
    s_us = 0.0
    if ours > 0 and any(abs(p - our_px) < 1e-9 for p in used):
        s_us = df ** ticks_between(ref, our_px) * ours
    return {"q": True, "ref": ref, "tot": tot, "share": (s_us / s_all) if s_all > 0 else 0.0}


def pair_score(yes_lv, no_lv, dead, prog, old_rule=False):
    """One second of our ghost pair: (counted, share_yes + share_no, yref, nref, share_yes, share_no)."""
    oy = DEAD_N if dead == "yes" else SAFE_N
    on = SAFE_N if dead == "yes" else DEAD_N
    y = walk(yes_lv, prog["target"], prog["df"], ours=oy, old_rule=old_rule)
    n = walk(no_lv, prog["target"], prog["df"], ours=on, old_rule=old_rule)
    ok = bool(y["q"] and n["q"])
    return ok, (y["share"] + n["share"]) if ok else 0.0, y["ref"], n["ref"], y["share"], n["share"]


def credit(reward, period_s, share_seconds):
    """racereward_live.credit: reward x (sum over counted seconds of yes + no share) / (2 x period)."""
    if not period_s or period_s <= 0:
        return 0.0
    return reward * share_seconds / (2.0 * period_s)


def floored(x):
    return x if x >= FLOOR_USD - 1e-9 else 0.0


def period_of(prog):
    return (prog["end"] - prog["start"]) if prog.get("end") and prog.get("start") else PERIOD_S


# ================================================================================================ the ladder
def yhat_of(rows):
    """rows [(K, best YES bid or None, best NO bid or None)] -> (y_hat, why). YES mid = (yes bid + 1 - no bid)/2 where
    both exist; mids fall with K; the one adjacent pair with mid >= 0.5 > mid -> linear interpolation at 0.5."""
    pts = sorted((K, (yb + 1.0 - nb) / 2.0) for K, yb, nb in rows if yb is not None and nb is not None)
    down = [(a, b) for a, b in zip(pts, pts[1:]) if a[1] >= 0.5 > b[1]]
    up = [(a, b) for a, b in zip(pts, pts[1:]) if a[1] < 0.5 <= b[1]]
    if not down:
        return None, "no_crossing"
    if len(down) > 1 or up:
        return None, "ladder_nonmonotone"
    (k1, m1), (k2, m2) = down[0]
    return round(k1 + (m1 - 0.5) / (m1 - m2) * (k2 - k1), 6), None


def yhat_off_ladder(rows):
    """The yield has run OFF the ladder (spec risk 6: ghosts sit at the edges): every readable YES mid >= 0.5 ->
    the yield is above the top readable strike -> (top + 1 bp, "above"); every mid < 0.5 -> (bottom - 1 bp,
    "below"); else (None, None). Used for the live distance / dead side / safe-side check only -- never to plan
    (spec 1.1: no crossing -> skip the tenor-hour)."""
    pts = sorted((K, (yb + 1.0 - nb) / 2.0) for K, yb, nb in rows if yb is not None and nb is not None)
    if len(pts) < 2:
        return None, None
    if all(m >= 0.5 for _, m in pts):
        return round(pts[-1][0] + OFF_LADDER_BP / 100.0, 6), "above"
    if all(m < 0.5 for _, m in pts):
        return round(pts[0][0] - OFF_LADDER_BP / 100.0, 6), "below"
    return None, None


def dist_bp(K, y):
    return round(abs(K - y) * 100.0, 6)


def band_of(d):
    if d is None:
        return "?"
    if d < 4.0:
        return "<4"
    if d < 6.0:
        return "4-6"
    if d < 8.0:
        return "6-8"
    return ">=8"


def bucket(s_left):
    """hazard_new.bucket (copied)."""
    for i, (a, b) in enumerate(BUCKETS):
        if a <= s_left < b:
            return i
    return len(BUCKETS) - 1


def classify(dist_signed_bp, taker_side, yes_px):
    """sweeps_new.classify (copied). dist = strike - yield (bp); positive = YES is the dead side."""
    if yes_px is None:
        return None
    if dist_signed_bp > 0:
        if taker_side == "no" and abs(yes_px - 0.01) < 1e-6:
            return "dead_sweep"
        if taker_side == "yes" and abs(yes_px - 0.99) < 1e-6:
            return "safe_fill"
    elif dist_signed_bp < 0:
        if taker_side == "yes" and abs(yes_px - 0.99) < 1e-6:
            return "dead_sweep"
        if taker_side == "no" and abs(yes_px - 0.01) < 1e-6:
            return "safe_fill"
    return None


def hits_bid_1c(side, taker_side, yes_px):
    """Does this print take a 1c bid on `side`? YES 1c bid <- taker bought NO at 99c; NO 1c bid <- taker bought YES."""
    if yes_px is None:
        return False
    if side == "yes":
        return taker_side == "no" and abs(yes_px - 0.01) < 1e-6
    return taker_side == "yes" and abs(yes_px - 0.99) < 1e-6


def group(rows):
    """sweeps_new.group (copied): rows (t, kind, count) -> events; same kind within 10 s of the previous = one."""
    out = []
    for t, k, c in sorted(rows):
        if out and out[-1]["kind"] == k and t - out[-1]["t_last"] <= GROUP_GAP_S:
            out[-1]["n"] += c
            out[-1]["t_last"] = t
        else:
            out.append({"t0": t, "t_last": t, "kind": k, "n": c})
    return out


def presence_minutes(mins, dead):
    """hazard_new.presence_minutes (copied): [(end_ts, bid_close, ask_close, bid_high, ask_low)] -> minutes with a 1c
    dead-side bid (last value carried forward; the minute's high/low catches a stack inside the minute)."""
    out, lb, la = [], None, None
    for e, bc, ac, bh, al in sorted(mins, key=lambda r: r[0]):
        lb = bc if bc is not None else lb
        la = ac if ac is not None else la
        if dead == "yes":
            hit = (lb is not None and abs(lb - 0.01) < 1e-6) or (bh is not None and abs(bh - 0.01) < 1e-6)
        else:
            hit = (la is not None and abs(la - 0.99) < 1e-6) or (al is not None and abs(al - 0.99) < 1e-6)
        if hit:
            out.append(e)
    return out


def plan_candidates(ladder, y, progs, band, target_default=1000.0):
    """ladder [(K, ticker, yes_lv, no_lv)] of ONE tenor, y = y_hat -> (candidates, refusals). A candidate:
    {ticker, K, dead, d, score}. Refusals {ticker: reason} for in-band strikes only."""
    cands, refused = [], {}
    for K, tk, ylv, nlv in ladder:
        d = dist_bp(K, y)
        if not (band[0] - 1e-9 <= d < band[1] - 1e-9):
            continue
        dead = "yes" if K > y else "no"
        prog = (progs or {}).get(tk)
        if prog is None:
            refused[tk] = "no_program"
            continue
        by = max(ylv) if ylv else None
        bn = max(nlv) if nlv else None
        if (bn is not None and bn >= CROSS_PX - 1e-9) or (by is not None and by >= CROSS_PX - 1e-9):
            refused[tk] = "would_cross"
            continue
        safe_lv = nlv if dead == "yes" else ylv
        tgt = prog.get("target", target_default)
        above = sum(s for p, s in safe_lv.items() if p > PX + 1e-9)
        # spec 1.3: ">= 200 lots above 1c on the safe side (our safe share would be ~0; the 89c x 200 case)". The
        # spec's REASON decides: refuse only when the walk gives our 1,000 at 1c a share < SAFE_SHARE_MIN there
        # (200 at 2c leaves us ~0.71 -> posted; 200 at 89c ~1e-27 -> refused)
        if above >= tgt / 5.0 - 1e-9 and \
                walk(safe_lv, tgt, prog.get("df", 0.5), ours=SAFE_N)["share"] < SAFE_SHARE_MIN:
            refused[tk] = "safe_share_zero"
            continue
        ok, sc, yr, nr, ys, ns = pair_score(ylv, nlv, dead, prog)
        cands.append({"ticker": tk, "K": K, "dead": dead, "d": d, "score": round(sc, 6)})
    return cands, refused


# ================================================================================================ statistics
def _binom_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    s = 0.0
    lp, lq = math.log(p), math.log1p(-p)
    for i in range(0, k + 1):
        s += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(1.0, s)


def cp_upper(k, n, conf=0.90):
    """Upper end of the two-sided `conf` Clopper-Pearson interval for k of n (n = 0 -> 1.0)."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    a = (1.0 - conf) / 2.0
    lo, hi = k / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _binom_cdf(k, n, mid) > a:
            lo = mid
        else:
            hi = mid
    return hi


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


# ================================================================================================ log
class Log:
    """rain_paper.Log / racereward_live.Log pattern: one JSON object a line, UTC `t`, `ev`."""

    def __init__(self, path=None, clock=time.time):
        self.path, self.clock = path, clock
        self.rows = []
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def write(self, ev, **kw):
        r = {"t": iso(self.clock()), "ev": ev}
        r.update(kw)
        if self.fh is not None:
            try:
                self.fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
                self.fh.flush()
            except Exception:
                pass
        else:
            self.rows.append(r)
        return r


class InstanceLock:
    """COPY of racereward_live.InstanceLock: an OS byte-range lock the OS drops when the holder dies."""
    OFFSET = 4096

    def __init__(self, path):
        self.path, self.fd = path, None

    def acquire(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, self.OFFSET, 0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self.fd = fd
        try:
            os.lseek(fd, 0, 0)
            os.write(fd, ("pid %d since %s" % (os.getpid(), iso(time.time()))).ljust(80).encode() + b"\n")
        except OSError:
            pass
        return True

    def release(self):
        if self.fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(self.fd, self.OFFSET, 0)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None


# ================================================================================================ REST (GET only)
class Rest:
    """Every public call goes through here: >= REST_MIN_GAP_S apart, 10 s back-off on 429, a short retry on a
    network error. `get` is kauth.get-shaped: get(path, params, auth=False) -> (status, body)."""

    def __init__(self, get, clock=time.time, sleep=time.sleep, min_gap=REST_MIN_GAP_S):
        self.get, self.clock, self.sleep, self.min_gap = get, clock, sleep, min_gap
        self.last = 0.0
        self.n = 0
        self.n429 = 0
        self.lock = threading.Lock()

    def call(self, path, params=None):
        st, b = None, None
        with self.lock:
            for i in range(4):
                wait = self.last + self.min_gap - self.clock()
                if wait > 0:
                    self.sleep(wait)
                self.last = self.clock()
                self.n += 1
                st, b = self.get(path, dict(params or {}), auth=False)
                if st == 429:
                    self.n429 += 1
                    self.sleep(REST_429_S)
                    continue
                if st == -1:
                    self.sleep(5.0)
                    continue
                return st, b
        return st, b


def job_discover(call, close_ts):
    """The hour's markets FROM THE API (never constructed): per series, the markets closing at close_ts.
    Returns [market row] or None if any series is unreadable."""
    out = []
    for s in SERIES:
        got, readable = None, False
        base = {"series_ticker": s, "min_close_ts": str(int(close_ts) - 60), "max_close_ts": str(int(close_ts) + 60),
                "limit": "200"}
        for extra in ({"status": "unopened"}, {}, {"status": "open"}):
            q = dict(base)
            q.update(extra)
            st, b = call("/markets", q)
            if st != 200 or not isinstance(b, dict):
                continue
            readable = True
            ms = [m for m in (b.get("markets") or []) if parse_ts(m.get("close_time")) == close_ts]
            if ms:
                got = ms
                break
        if not readable:
            return None
        for m in got or []:
            K = f(m.get("floor_strike"))
            if K is None or not m.get("ticker"):
                continue
            out.append({"ticker": m["ticker"], "series": s, "event": m.get("event_ticker"), "K": K,
                        "strike_type": m.get("strike_type"), "pls": m.get("price_level_structure"),
                        "open": parse_ts(m.get("open_time")), "close": parse_ts(m.get("close_time")),
                        "status": m.get("status")})
    return out


def job_programs(call, tickers):
    """{ticker: program} for these tickers from GET /incentive_programs (upcoming + active, paged; the endpoint
    ignores market filters). None if unreadable (the hour is then refused; never an assumed $10/1,000).
    period_reward is CENTI-CENTS (100000 = $10)."""
    want, out = set(tickers), {}
    for status in ("upcoming", "active"):
        cur = None
        for _ in range(PROG_PAGES_MAX):
            q = {"status": status, "limit": "5000"}
            if cur:
                q["cursor"] = cur
            st, b = call("/incentive_programs", q)
            if st != 200 or not isinstance(b, dict):
                return None
            rows = b.get("incentive_programs") or []
            for p in rows:
                tk = p.get("market_ticker")
                if tk not in want:
                    continue
                rw, tg, df = f(p.get("period_reward")), f(p.get("target_size_fp")), f(p.get("discount_factor_bps"))
                if rw is None or tg is None or df is None:
                    continue
                out[tk] = {"reward": rw / 10000.0, "target": tg, "df": df / 10000.0,
                           "start": parse_ts(p.get("start_date")), "end": parse_ts(p.get("end_date")),
                           "id": p.get("id"), "type": p.get("incentive_type")}
            cur = b.get("next_cursor") or b.get("cursor")
            del rows, b
            if not cur:
                break
    return out


def job_results(call, events):
    out = {}
    for e in events:
        st, b = call("/markets", {"event_ticker": e, "limit": "200"})
        if st != 200 or not isinstance(b, dict):
            return None
        for m in b.get("markets") or []:
            out[m.get("ticker")] = {"result": m.get("result"), "settle": f(m.get("expiration_value")),
                                    "vol": f(m.get("volume_fp"), 0.0), "status": m.get("status")}
    return out


def job_trades(call, tickers, t_lo, t_hi):
    """{ticker: [(trade_id, created_ts, count, yes_px, taker_side)]} or None if any read failed."""
    out, bounded = {}, True
    for tk in tickers:
        rows, cur = [], None
        for _ in range(TRADE_PAGES_MAX):
            q = {"ticker": tk, "limit": "1000"}
            if bounded:
                q.update(min_ts=str(int(t_lo)), max_ts=str(int(t_hi)))
            if cur:
                q["cursor"] = cur
            st, b = call("/markets/trades", q)
            if st == 400 and bounded and not cur:
                bounded = False                      # the time bounds were refused: read unbounded, filter locally
                q.pop("min_ts", None)
                q.pop("max_ts", None)
                st, b = call("/markets/trades", q)
            if st != 200 or not isinstance(b, dict):
                return None
            for x in b.get("trades") or []:
                rows.append((x.get("trade_id"), parse_ts(x.get("created_time")), f(x.get("count_fp"), 0.0),
                             f(x.get("yes_price_dollars")), x.get("taker_side")))
            cur = b.get("cursor") or b.get("next_cursor")
            if not cur or not b.get("trades"):
                break
        out[tk] = rows
    return out


class Jobs:
    """REST work off the main thread (the per-second scoring never waits on a GET). sync=True runs inline (tests)."""

    def __init__(self, sync=False):
        self.sync = sync
        self.inq, self.outq = queue.Queue(), queue.Queue()
        self.busy = set()
        if not sync:
            threading.Thread(target=self._worker, name="rateh-rest", daemon=True).start()

    def submit(self, name, key, fn):
        k = (name, key)
        if k in self.busy:
            return False
        self.busy.add(k)
        if self.sync:
            self.outq.put((name, key, self._run(fn)))
        else:
            self.inq.put((name, key, fn))
        return True

    @staticmethod
    def _run(fn):
        try:
            return fn()
        except Exception as e:                                  # noqa: BLE001
            return {"_error": repr(e)[:300]}

    def _worker(self):
        while True:
            name, key, fn = self.inq.get()
            self.outq.put((name, key, self._run(fn)))

    def poll(self):
        out = []
        while True:
            try:
                r = self.outq.get_nowait()
            except queue.Empty:
                break
            self.busy.discard((r[0], r[1]))
            out.append(r)
        return out


# ================================================================================================ the socket
class RecBook(livebook.LiveBook):
    """livebook.LiveBook plus an event queue, in arrival order, of what the recorder needs: every 1c level change
    (either side), every snapshot's 1c sizes, every trade print (full msg). Nothing else is changed."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.evq = collections.deque()
        self.last_rx_ms = None

    def on_frame(self, raw, rx_ms=None):
        rx_ms = livebook.now_ms() if rx_ms is None else rx_ms
        self.last_rx_ms = rx_ms
        return super().on_frame(raw, rx_ms)

    def apply_snapshot(self, msg, sid, seq, rx_ms):
        super().apply_snapshot(msg, sid, seq, rx_ms)
        tk = msg.get("market_ticker")
        with self.lock:
            b = self.books.get(tk)
            if b is None:
                return
            y1, n1 = b["yes"].get(PX, 0.0), b["no"].get(PX, 0.0)
        self.evq.append(("snap", rx_ms / 1000.0, tk, y1, n1))

    def apply_delta(self, msg, sid, seq, rx_ms):
        ok = super().apply_delta(msg, sid, seq, rx_ms)
        if ok:
            try:
                if abs(livebook.px(msg["price_dollars"]) - PX) < 1e-9:
                    tk, side = msg["market_ticker"], msg["side"]
                    with self.lock:
                        sz = self.books[tk][side].get(PX, 0.0)
                    self.evq.append(("lvl", rx_ms / 1000.0, tk, side, sz))
            except Exception:                                   # noqa: BLE001
                self.stats["rec_hook_errors"] += 1
        return ok

    def _on_trade(self, msg, rx_ms):
        super()._on_trade(msg, rx_ms)
        self.evq.append(("trade", rx_ms / 1000.0, dict(msg)))

    def drop(self, tickers):
        """livebook.drop() leaves `_age` behind (~80 tickers an hour, ~11k in 14 days): clear it here too."""
        super().drop(tickers)
        with self.lock:
            for tk in tickers:
                self._age.pop(tk, None)


class WS:
    """The recorder's view of a RecBook (production and the frame-driven self-tests share it)."""

    def __init__(self, lb):
        self.lb = lb
        self.started = False

    def drain(self):
        out, q = [], self.lb.evq
        while q:
            out.append(q.popleft())
        return out

    def best(self, tk):
        lb = self.lb
        with lb.lock:
            b, m = lb.books.get(tk), lb.meta.get(tk)
            if b is None or m is None or m.get("suspect") or m.get("await_snapshot"):
                return None
            return (max(b["yes"]) if b["yes"] else None, max(b["no"]) if b["no"] else None)

    def levels(self, tk):
        lb = self.lb
        with lb.lock:
            b, m = lb.books.get(tk), lb.meta.get(tk)
            if b is None or m is None or m.get("suspect") or m.get("await_snapshot"):
                return None
            return dict(b["yes"]), dict(b["no"])

    def one_c(self, tk):
        """(YES 1c size, NO 1c size) from the synced book, or None."""
        lb = self.lb
        with lb.lock:
            b, m = lb.books.get(tk), lb.meta.get(tk)
            if b is None or m is None or m.get("suspect") or m.get("await_snapshot"):
                return None
            return b["yes"].get(PX, 0.0), b["no"].get(PX, 0.0)

    def connected(self):
        return self.lb.connected.is_set()

    def subscribe(self, tks):
        if not self.started:
            self.lb.start(list(tks))
            self.started = True
        else:
            self.lb.subscribe(list(tks))

    def drop(self, tks):
        self.lb.drop(list(tks))

    def resync(self):
        self.lb.resync()

    def last_rx_s(self):
        v = self.lb.last_rx_ms
        return None if v is None else v / 1000.0

    def health(self):
        s = self.lb.stats
        return {k: int(s.get(k, 0)) for k in ("connects", "disconnects", "resyncs", "seq_gaps", "trade_seq_gaps",
                                              "deltas_applied", "trades_applied", "snapshots_applied",
                                              "subscribe_refused", "trade_subscribe_refused", "frame_exceptions")}


# ================================================================================================ one hour
class Ghost:
    def __init__(self, tk, series, K, dead, d0, t_post, prog, exit_t, ahead0, variants):
        self.tk, self.series, self.K, self.dead, self.d0 = tk, series, K, dead, d0
        self.t_post, self.prog, self.exit = t_post, prog, exit_t
        self.variants = list(variants)
        n = max(0, int(math.ceil(exit_t - t_post)))
        self.inc = array("d", [0.0]) * n            # share-seconds per second (new rule), index = second since post
        self.inc_old = array("d", [0.0]) * n
        self.cnt = array("b", [0]) * n
        self.next_i = 0
        self.t_safe = None
        self.safe_prints = 0.0
        self.ahead = ahead0                            # E_low queue: 1c dead-side size ahead of us at post
        self.q_fill = 0.0
        self.q_hist = [(t_post, 0.0)]
        self.pend_dec = []
        self.recent = []                               # [t, n, unmatched]
        self.t_whole = None
        self.last = None                               # last scored (shares, refs) for score10

    def credit_until(self, t_end, old=False):
        """Raw credit $ over [t_post, t_end)."""
        arr = self.inc_old if old else self.inc
        x = max(0.0, min(t_end, self.exit) - self.t_post)
        k = int(x)
        s = sum(arr[:min(k, len(arr))])
        if k < len(arr):
            s += (x - k) * arr[k]
        return credit(self.prog["reward"], period_of(self.prog), s)

    def counted_until(self, t_end):
        k = int(max(0.0, min(t_end, self.exit) - self.t_post))
        return int(sum(self.cnt[:min(k, len(self.cnt))]))

    def q_fill_at(self, t_end):
        v = 0.0
        for t, c in self.q_hist:
            if t < t_end:
                v = c
        return v

    def first_fill_before(self, t_end):
        """E_low: the time of the first queue fill before t_end, or None (after any fill a ghost stops earning)."""
        for t, c in self.q_hist:
            if c > 0 and t < t_end:
                return t
        return None

    def cum_min(self):
        out, n = [], len(self.inc)
        for i in range(0, n + 60, 60):
            out.append(round(self.credit_until(self.t_post + min(i, n)), 5))
            if i >= n:
                break
        return out


class HourRec:
    """Everything one hour records and decides. Fed by WS events (on_event) and once-a-second ticks (tick)."""

    def __init__(self, o, log, partial=False):
        self.open, self.close = o, o + PERIOD_S
        self.exit = self.close - EXIT_S
        self.key = iso_hour(o)
        self.day = et_date(o)
        self.log = log
        self.partial = partial
        self.restarted = False
        self.blackout = blackout_of(o)
        self.markets = None                    # ticker -> row
        self.tenors = {}                       # series -> [(K, ticker)]
        self.progs = None                      # ticker -> program; None = not read
        self.prog_status = "pending"           # pending | listed | none | unreadable
        self.lvl = {}                          # ticker -> {"yes": size, "no": size} at 1c
        self.yh = {}                           # series -> current y_hat
        self.yh_hist = {}                      # series -> array per second since open (nan = unknown)
        self.ep_open, self.ep_ending, self.ep_done = {}, [], []
        self.expo = collections.defaultdict(float)
        self.ep_cnt = collections.defaultdict(collections.Counter)
        self.trades = {}                       # trade_id -> (ticker, rx, ts_ms, taker_side, yes_px, n)
        self.trades_noid = []
        self.unclassified = 0
        self.groups = {}
        self.sweeps = []
        self.safe_fills_real = []
        self.t1 = None
        self.trigger = None
        self.burst = None
        self.burst_pending = None
        self.ghosts = {}
        self.ghost_order = []
        self.var = {v: {"posted": [], "refused": {}, "why": None} for v in VARIANTS}
        self.planned = False
        self.plan_y = {}
        self.blind_run, self.blind_max, self.last_tick = 0, 0, None
        self.silent_max = 0.0                  # longest no-frame span inside [open, exit] while subscribed (s)
        self.sub_t = None                      # when this hour's tickers were subscribed
        self.off = {}                          # series -> "above" / "below" while the yield is off the ladder
        self.off_s = collections.Counter()     # series -> seconds off the ladder
        self.off_logs = collections.Counter()
        self.unclass_1c = collections.defaultdict(float)   # ticker -> 1c lots printed while its tenor had no y_hat
        self.outcome = None
        self.results = None
        self.audit = None
        self.audit_tries = 0
        self.results_tries = 0
        self.discover_next = 0.0
        self.discover_empty_after_open = False
        self.prog_next = 0.0
        self.subscribed = False
        self.dropped = False
        self.summary = None
        self.prev_sweeper = False
        self.ep_seq = 0

    # ---------------- setup ----------------
    def set_markets(self, rows):
        self.markets = {}
        for m in rows:
            if m.get("strike_type") not in (None, "greater"):
                self.log.write("error", where="discover", hour=self.key, ticker=m["ticker"],
                               err="strike_type %s (the rule assumes 'greater'); market ignored" % m.get("strike_type"))
                continue
            self.markets[m["ticker"]] = m
        self.tenors = collections.defaultdict(list)
        for tk, m in self.markets.items():
            self.tenors[m["series"]].append((m["K"], tk))
            self.lvl[tk] = {"yes": 0.0, "no": 0.0}
        for s in self.tenors:
            self.tenors[s].sort()
            self.yh_hist[s] = array("d", [float("nan")]) * 3600
            self.yh[s] = None

    def sec(self, t):
        return int(t - self.open)

    def dist_now(self, tk):
        m = self.markets.get(tk)
        y = self.yh.get(m["series"]) if m else None
        return None if y is None else dist_bp(m["K"], y)

    def yh_at(self, series, t):
        a = self.yh_hist.get(series)
        if a is None:
            return None
        i = min(max(int(t - self.open), 0), 3599)
        while i >= 0:
            v = a[i]
            if v == v:
                return v
            i -= 1
        return None

    def ghost_dist_at(self, g, t):
        y = self.yh_at(g.series, t)
        return g.d0 if y is None else dist_bp(g.K, y)

    # ---------------- episodes ----------------
    def _cell(self, ep, t):
        y = self.yh.get(ep["series"])
        d = None if y is None else dist_bp(ep["K"], y)
        return "%s|%d" % (band_of(d), bucket(self.close - t))

    def _accrue(self, ep, t):
        t = min(t, self.exit)
        if t > ep["last_t"]:
            self.expo[ep["cell"]] += t - ep["last_t"]
            ep["last_t"] = t

    def _start_ep(self, tk, side, t, size, exact):
        m = self.markets[tk]
        self.ep_seq += 1
        ep = {"id": self.ep_seq, "tk": tk, "series": m["series"], "K": m["K"], "side": side, "t0": t, "last_t": t,
              "size": size, "max": size, "hist": [(t, size)], "exact": exact, "d0": self.dist_now(tk)}
        ep["cell"] = self._cell(ep, t)
        self.ep_open[tk] = ep

    def _end_ep(self, ep, t, why):
        self._accrue(ep, t)
        ep["t_end"], ep["end_kind"] = t, why
        ep["cell_end"] = ep["cell"]
        self.ep_open.pop(ep["tk"], None)
        self.ep_ending.append(ep)

    def _finalize_ep(self, ep):
        tk, side, te = ep["tk"], ep["side"], ep["t_end"]
        if ep["end_kind"] == "survived":
            cause = "SURVIVED"
        else:
            ref = max([s for t, s in ep["hist"] if t >= te - SWEPT_WIN_S] +
                      [s for t, s in ep["hist"] if t < te - SWEPT_WIN_S][-1:] or [ep["max"]])
            took = sum(r[5] for r in self.trades.values()
                       if r[0] == tk and te - SWEPT_WIN_S <= r[1] <= te + SWEPT_WIN_S and hits_bid_1c(side, r[3], r[4]))
            took += sum(r[5] for r in self.trades_noid
                        if r[0] == tk and te - SWEPT_WIN_S <= r[1] <= te + SWEPT_WIN_S and hits_bid_1c(side, r[3], r[4]))
            ep["took"], ep["ref"] = round(took, 2), ref
            if took >= SWEPT_FRAC * ref - 1e-9:
                cause = "SWEPT"
            elif any(s["far"] and s["tk"] != tk and te - SIBLING_PULL_S <= s["t"] <= te for s in self.sweeps):
                cause = "PULLED_AFTER_SIBLING"
            else:
                cause = "PULLED"
        ep["cause"] = cause
        self.ep_cnt[ep["cell_end"]][cause] += 1
        self.ep_done.append(ep)
        self.log.write("episode", hour=self.key, id=ep["id"], ticker=tk, side=side, cause=cause, size_max=ep["max"],
                       t0=iso(ep["t0"]), t_end=iso(te), s_left=round(self.close - te, 1), d0=ep["d0"],
                       cell=ep["cell_end"], exact=ep["exact"], took=ep.get("took"), ref=ep.get("ref"),
                       dur_s=round(te - ep["t0"], 3))

    def _dead_side_now(self, tk):
        m = self.markets[tk]
        y = self.yh.get(m["series"])
        if y is None or abs(m["K"] - y) < 1e-12:
            return None
        return "yes" if m["K"] > y else "no"

    def _maybe_start(self, tk, t, exact):
        if tk in self.ep_open or t >= self.exit or t < self.open:
            return
        side = self._dead_side_now(tk)
        d = self.dist_now(tk)
        if side is None or d is None or d < FAR_BP - 1e-9:
            return
        sz = self.lvl[tk][side]
        if sz >= EP_ON - 1e-9:
            self._start_ep(tk, side, t, sz, exact)

    # ---------------- events ----------------
    def on_event(self, ev):
        kind, t = ev[0], ev[1]
        if kind == "lvl":
            _, _, tk, side, sz = ev
            if tk not in self.lvl:
                return
            prev = self.lvl[tk][side]
            self.lvl[tk][side] = sz
            g = self.ghosts.get(tk)
            if g is not None and side == g.dead and sz < prev and g.t_post <= t < g.exit:
                g.pend_dec.append((t, prev - sz))
            ep = self.ep_open.get(tk)
            if ep is not None and ep["side"] == side:
                ep["hist"].append((t, sz))
                ep["max"] = max(ep["max"], sz)
                if sz < EP_OFF - 1e-9:
                    self._end_ep(ep, t, "dropped")
            elif ep is None and sz >= EP_ON - 1e-9:
                self._maybe_start(tk, t, True)
        elif kind == "snap":
            _, _, tk, y1, n1 = ev
            if tk not in self.lvl:
                return
            self.lvl[tk] = {"yes": y1, "no": n1}
            ep = self.ep_open.get(tk)
            if ep is not None:
                sz = self.lvl[tk][ep["side"]]
                ep["hist"].append((t, sz))
                if sz < EP_OFF - 1e-9:
                    self._end_ep(ep, t, "snapshot")
        elif kind == "trade":
            self.on_trade(t, ev[2])

    def on_trade(self, t, msg):
        tk = msg.get("market_ticker")
        if tk not in self.markets:
            return
        side, yes_px, n = msg.get("taker_side"), f(msg.get("yes_price_dollars")), f(msg.get("count_fp"))
        if n is None:
            n = f(msg.get("count"), 0.0)
        ts_ms = msg.get("ts_ms")
        rec = (tk, t, ts_ms, side, yes_px, n)
        tid = msg.get("trade_id")
        if tid:
            self.trades[tid] = rec
        else:
            self.trades_noid.append(rec)
        if not (self.open - 60 <= t < self.close + 60) or not n or n <= 0:
            return
        g = self.ghosts.get(tk)
        if g is not None and g.t_post <= t < g.exit and hits_bid_1c(g.dead, side, yes_px):
            over = n - g.ahead
            if over > 0:
                g.q_fill = min(DEAD_N, g.q_fill + over)
                g.ahead = 0.0
                g.q_hist.append((t, g.q_fill))
            else:
                g.ahead -= n
            g.recent.append([t, n, n])
        if g is not None and g.t_post <= t < g.exit and hits_bid_1c("no" if g.dead == "yes" else "yes", side, yes_px):
            g.safe_prints += n
        m = self.markets[tk]
        y = self.yh.get(m["series"])
        if y is None:
            self.unclassified += 1
            # a 1c print we cannot side (no y_hat yet / ladder unreadable): could be the trigger or a sweep of a
            # ghost -> counted; >= TRIGGER_N lots on one ticker before exit excludes the hour from the bar
            if (hits_bid_1c("yes", side, yes_px) or hits_bid_1c("no", side, yes_px)) and self.open <= t < self.exit:
                self.unclass_1c[tk] += n
            return
        sd = round((m["K"] - y) * 100.0, 6)
        kind = classify(sd, side, yes_px)
        if kind == "safe_fill":
            self.safe_fills_real.append((tk, t, n))
            return
        if kind != "dead_sweep":
            return
        gk = (tk, "dead")
        gr = self.groups.get(gk)
        if gr is not None and t - gr["t_last"] <= GROUP_GAP_S:
            gr["n"] += n
            gr["t_last"] = t
        else:
            gr = self.groups[gk] = {"t0": t, "t_last": t, "n": n, "fired": None}
        if gr["fired"] is None and gr["n"] >= TRIGGER_N - 1e-9:
            d = abs(sd)
            s_left = self.close - t
            lag = None
            try:
                lag = int(t * 1000) - int(ts_ms)
            except (TypeError, ValueError):
                pass
            stacks = [[e["tk"], e["side"], self.lvl[e["tk"]][e["side"]], self.dist_now(e["tk"])]
                      for e in self.ep_open.values()]
            S = {"i": len(self.sweeps), "tk": tk, "series": m["series"], "t": t, "d": d, "far": d >= FAR_BP - 1e-9,
                 "n_fire": round(gr["n"], 2), "s_left": round(s_left, 1), "lag_ms": lag,
                 "z": round(d / math.sqrt(max(s_left / 60.0, 0.25)), 3), "group": gr}
            gr["fired"] = S
            self.sweeps.append(S)
            if g is not None and g.t_post <= t < g.exit and g.t_whole is None and hits_bid_1c(g.dead, side, yes_px):
                g.t_whole = t
            first = S["far"] and self.t1 is None and t < self.exit
            self.log.write("sweep", hour=self.key, ticker=tk, tenor=m["series"], size=S["n_fire"], s_left=S["s_left"],
                           d=round(d, 3), far=S["far"], z=S["z"], lag_ms=lag, first=first, stacks=stacks)
            if first:
                self.fire_trigger(S)

    def fire_trigger(self, S):
        self.t1 = S["t"]
        self.trigger = S
        at_risk = [tk for tk in self.ep_open if tk != S["tk"]]
        self.burst_pending = {"t1": S["t"], "at_risk": at_risk}
        resting = [g.tk for g in self.ghosts.values()
                   if any(v in ("V2", "V2w", "V2s") for v in g.variants) and g.t_post <= S["t"] < g.exit]
        self.log.write("cancel", hour=self.key, trigger=S["tk"], t_trigger=iso(S["t"]),
                       t_cancel=iso(S["t"] + CANCEL_LAG_S), d=round(S["d"], 3), size=S["n_fire"],
                       s_from_open=round(S["t"] - self.open, 1), ghosts_cancelled=resting,
                       variants=["V2", "V2w", "V2s"], before_plan=not self.planned)

    def _finish_burst(self, now):
        bp = self.burst_pending
        if bp is None or now < bp["t1"] + max(BURST_WINDOWS) + 1.0:
            return
        hits = {}
        for w in BURST_WINDOWS:
            hits["hits_%g" % w] = sum(1 for tk in bp["at_risk"]
                                      if any(s["tk"] == tk and bp["t1"] < s["t"] <= bp["t1"] + w + 1e-9
                                             for s in self.sweeps))
        self.burst = dict(at_risk=len(bp["at_risk"]), **hits)
        self.burst_pending = None

    # ---------------- ticks ----------------
    def update_yhat(self, t, ws):
        for s, lad in self.tenors.items():
            rows = []
            for K, tk in lad:
                b = ws.best(tk)
                if b is not None:
                    rows.append((K, b[0], b[1]))
            y, why = yhat_of(rows)
            off = None
            if y is None and why == "no_crossing":
                y, off = yhat_off_ladder(rows)
            if y is not None:
                self.yh[s] = y
                if off != self.off.get(s):
                    if self.off_logs[s] < 20:
                        self.off_logs[s] += 1
                        self.log.write("yhat_off_ladder" if off else "yhat_on_ladder", hour=self.key, tenor=s,
                                       side=off, y_hat=y, s_from_open=round(t - self.open, 1))
                    self.off[s] = off
                if off and self.open <= t < self.exit:
                    self.off_s[s] += 1
            i = self.sec(t)
            if 0 <= i < 3600 and self.yh[s] is not None:
                self.yh_hist[s][i] = self.yh[s]

    def tick(self, t, ws):
        """t = an integer second."""
        if self.markets is None:
            return
        if t >= self.open - 1:
            self.update_yhat(t, ws)
        if self.open <= t <= self.exit:
            blind = (not ws.connected()) or any(ws.best(tk) is None for tk in self.markets)
            self.blind_run = self.blind_run + 1 if blind else 0
            self.blind_max = max(self.blind_max, self.blind_run)
        # the book is the authority for the 1c sizes once a second (an event can be missed; a book cannot)
        for tk in self.markets:
            oc = ws.one_c(tk)
            if oc is not None:
                self.lvl[tk] = {"yes": oc[0], "no": oc[1]}
        # episodes: accrue, re-cell, end (below 250 / at exit), start
        for ep in list(self.ep_open.values()):
            self._accrue(ep, t)
            ep["cell"] = self._cell(ep, t)
            ep["size"] = self.lvl[ep["tk"]][ep["side"]]
            if t >= self.exit:
                self._end_ep(ep, self.exit, "survived")
            elif ep["size"] < EP_OFF - 1e-9:
                ep["hist"].append((float(t), ep["size"]))
                self._end_ep(ep, float(t), "tick")
        if self.open <= t < self.exit:
            for tk in self.markets:
                if tk not in self.ep_open:
                    self._maybe_start(tk, t, False)
        for ep in list(self.ep_ending):
            if t >= ep["t_end"] + SWEPT_WIN_S:
                self.ep_ending.remove(ep)
                self._finalize_ep(ep)
        self._finish_burst(t)
        # ghosts: score each whole second, E_low reconcile, safe fill
        for g in self.ghosts.values():
            self._score_ghost(g, t, ws)

    def _score_ghost(self, g, t, ws):
        upto = min(len(g.inc), int(t - g.t_post))
        if upto > g.next_i:
            lv = ws.levels(g.tk)
            if lv is None:
                ok, sc, sc_old, yr, nr, ys, ns = False, 0.0, 0.0, None, None, 0.0, 0.0
            else:
                ok, sc, yr, nr, ys, ns = pair_score(lv[0], lv[1], g.dead, g.prog)
                ok2, sc_old, _, _, _, _ = pair_score(lv[0], lv[1], g.dead, g.prog, old_rule=True)
            for i in range(g.next_i, upto):
                g.inc[i] = sc
                g.inc_old[i] = sc_old
                g.cnt[i] = 1 if ok else 0
            g.next_i = upto
            g.last = (round(ys, 5), round(ns, 5), 1 if ok else 0, yr, nr)
        # E_low: decreases older than 2 s are matched to prints within 2 s; the rest are cancels ahead of us
        keep = []
        for td, dq in g.pend_dec:
            if t - td < 2.0:
                keep.append((td, dq))
                continue
            for r in g.recent:
                if dq <= 0:
                    break
                if abs(r[0] - td) <= 2.0 and r[2] > 0:
                    m = min(dq, r[2])
                    r[2] -= m
                    dq -= m
            if dq > 0:
                g.ahead = max(0.0, g.ahead - dq)
        g.pend_dec = keep
        g.recent = [r for r in g.recent if t - r[0] < 10.0]
        # safe-side fill: the live y_hat crosses K by >= 1 bp before exit (pessimistic -$10)
        if g.t_safe is None and g.t_post <= t < g.exit:
            y = self.yh.get(g.series)
            if y is not None:
                beyond = (y - g.K) * 100.0 if g.dead == "yes" else (g.K - y) * 100.0
                if beyond >= SAFE_CROSS_BP - 1e-9:
                    g.t_safe = float(t)
                    self.log.write("vfill", hour=self.key, ticker=g.tk, kind="safe_cross", t_fill=iso(t),
                                   y=y, K=g.K, cost=SAFE_COST, variants=g.variants)

    def score10(self, t):
        if not self.ghost_order or not (self.open + PLAN_S < t <= self.exit) or int(t - self.open) % 10:
            return
        rows = []
        for i, tk in enumerate(self.ghost_order):
            g = self.ghosts[tk]
            if g.last is None:
                continue
            rows.append([i, g.last[0], g.last[1], g.last[2], g.last[3], g.last[4], round(g.credit_until(t), 4)])
        if rows:
            self.log.write("score10", hour=self.key, s=int(t - self.open), g=rows)

    # ---------------- the plan ----------------
    def plan(self, t, ws, budget_room):
        """Rule V2 + variants at HH:00:30. budget_room(variant, n_resting) -> bool."""
        self.planned = True
        hour_why = None
        if self.partial:
            hour_why = "partial_hour"
        elif self.blackout:
            hour_why = self.blackout
        elif not self.markets:
            hour_why = "no_markets"
        elif self.prog_status == "unreadable" or self.prog_status == "pending":
            hour_why = "programs_unreadable"
        elif self.prog_status == "none":
            hour_why = "no_program_listed"
        tenor_info, union = {}, {}
        for s, lad in sorted(self.tenors.items()):
            ladder, rows = [], []
            for K, tk in lad:
                lv = ws.levels(tk)
                if lv is None:
                    continue
                ladder.append((K, tk, lv[0], lv[1]))
                rows.append((K, max(lv[0]) if lv[0] else None, max(lv[1]) if lv[1] else None))
            y, why = yhat_of(rows)
            if len(ladder) < len(lad):
                y, why = None, "ladder_unreadable"
            self.plan_y[s] = y
            info = {"y_hat": y, "why": why, "n": len(lad), "prev_settle": None}
            if y is not None:
                for name, band in (("v2", BAND_V2), ("v2w", BAND_V2W)):
                    c, r = plan_candidates(ladder, y, self.progs or {}, band)
                    info[name] = c
                    info[name + "_refused"] = r
                    for x in c:
                        x["series"] = s
                        union[x["ticker"]] = x
            tenor_info[s] = info
        posts = {}
        for v in VARIANTS:
            st = self.var[v]
            why = hour_why
            if why is None and v != "V1" and self.t1 is not None:
                why = "sibling_sweep_before_plan"
            if why is None and v == "V2s" and self.prev_sweeper:
                why = "v2s_skip_after_sweeper_hour"
            st["why"] = why
            if why is not None:
                continue
            key = "v2w" if v == "V2w" else "v2"
            cands = []
            for s, info in tenor_info.items():
                cands.extend(info.get(key) or [])
                for tk, r in (info.get(key + "_refused") or {}).items():
                    st["refused"][tk] = r
            cands.sort(key=lambda c: (-c["score"], c["ticker"]))
            for c in cands:
                if budget_room(v, len(st["posted"])):
                    st["posted"].append(c["ticker"])
                    posts.setdefault(c["ticker"], []).append(v)
                else:
                    st["refused"][c["ticker"]] = "budget"
        for tk in sorted(posts):
            c = union[tk]
            lv = ws.levels(tk)
            ahead = (lv[0] if c["dead"] == "yes" else lv[1]).get(PX, 0.0) if lv else 0.0
            g = Ghost(tk, c["series"], c["K"], c["dead"], c["d"], float(t), self.progs[tk], self.exit, ahead, posts[tk])
            self.ghosts[tk] = g
            self.ghost_order.append(tk)
        self.log.write("hour_plan", hour=self.key, et=et_label(self.open), day=self.day, blackout=self.blackout,
                       partial=self.partial, programs=self.prog_status, n_markets=len(self.markets or {}),
                       hour_refused=hour_why, prev_sweeper=self.prev_sweeper,
                       tenors={s: {"y_hat": i["y_hat"], "why": i["why"], "n": i["n"],
                                   "v2": [[c["ticker"], c["K"], c["dead"], c["d"], c["score"]] for c in i.get("v2") or []],
                                   "v2w_extra": [[c["ticker"], c["d"]] for c in i.get("v2w") or []
                                                 if not (BAND_V2[0] - 1e-9 <= c["d"])],
                                   "refused": i.get("v2w_refused") or {}} for s, i in tenor_info.items()},
                       variants={v: {"posted": self.var[v]["posted"], "why": self.var[v]["why"],
                                     "refused": self.var[v]["refused"]} for v in VARIANTS},
                       ghost_order=self.ghost_order)
        for tk in self.ghost_order:
            g = self.ghosts[tk]
            self.log.write("post", hour=self.key, ticker=tk, series=g.series, K=g.K, dead=g.dead, d=g.d0,
                           t_post=g.t_post, exit=g.exit, ahead=g.ahead, variants=g.variants,
                           prog={k: g.prog.get(k) for k in ("reward", "target", "df", "start", "end", "id")},
                           safe=SAFE_N, dead_n=DEAD_N, price=PX)

    # ---------------- the outcome (at exit + 12 s) ----------------
    def _emain(self, v):
        """E_main for one variant: ghosts end at the first dominating sweep (any tenor, live distance <= the ghost's
        + 0.5 bp) before their cancel/exit/safe fill. THE FIRST SWEEP of a sweeper hour (spec 6.2 "hitting one
        ghost", 4.6): under the cancel variants it is one print group on ONE market, so it takes exactly one ghost --
        the one resting on its own market, else the nearest (assumed); the others are lost only to real dominating
        sweeps landing before the cancel (n_win) or, in --report, to the burst share b x (G - 1). Under V1 (no
        cancel) it dominates as any sweep does, and takes the nearest if it dominates none (the spec's V1 hour
        model: the sweeper takes every band stack at its first sweep). Returns (end times, swept times, stats)."""
        gs = [self.ghosts[tk] for tk in self.var[v]["posted"]]
        cancel = (self.t1 + CANCEL_LAG_S) if (v != "V1" and self.t1 is not None) else None
        end = {}
        for g in gs:
            e = g.exit
            if g.t_safe is not None:
                e = min(e, g.t_safe)
            if cancel is not None:
                e = min(e, cancel)
            end[g.tk] = e
        swept = {}
        g1, n_pre, n_win, assumed = 0, 0, 0, None
        for S in sorted(self.sweeps, key=lambda s: s["t"]):
            if S["t"] >= self.exit:
                break
            resting = [g for g in gs if g.tk not in swept and g.t_post <= S["t"] < end[g.tk]]
            is_first = self.trigger is S
            if is_first:
                g1 = len(resting)
            if is_first and v != "V1":
                hit = [g for g in resting if g.tk == S["tk"]]
            else:
                hit = [g for g in resting if S["d"] <= self.ghost_dist_at(g, S["t"]) + DOMINANCE_BP + 1e-9]
            if is_first and not hit and resting:
                near = min(resting, key=lambda g: (self.ghost_dist_at(g, S["t"]), g.tk))
                hit = [near]
                assumed = near.tk
            for g in hit:
                swept[g.tk] = S["t"]
                end[g.tk] = min(end[g.tk], S["t"])
                if self.t1 is not None and S["t"] >= self.t1 - 1e-9:
                    n_win += 1 if (cancel is None or S["t"] <= cancel + 1e-9) else 0
                else:
                    n_pre += 1
        if v == "V1":
            n_win = sum(1 for tk, ts in swept.items() if self.t1 is not None and ts >= self.t1 - 1e-9)
        return end, swept, {"g1": g1, "n_pre": n_pre, "n_win": n_win, "assumed": assumed}

    def compute_outcome(self):
        out = {}
        for v in VARIANTS:
            posted = self.var[v]["posted"]
            end, swept, st = self._emain(v)
            cancel = (self.t1 + CANCEL_LAG_S) if (v != "V1" and self.t1 is not None) else None
            rows, cr_raw, cr_fl, cr_old, n_safe = [], 0.0, 0.0, 0.0, 0
            el_cost, el_whole, el_cr = 0.0, 0, 0.0
            for tk in posted:
                g = self.ghosts[tk]
                e = end[tk]
                raw = g.credit_until(e)
                old = g.credit_until(e, old=True)
                safe = g.t_safe is not None and g.t_safe <= e + 1e-9 and tk not in swept
                n_safe += 1 if safe else 0
                # E_low: own-market prints until the ghost's end WITHOUT dominance
                e_low = g.exit
                if g.t_safe is not None:
                    e_low = min(e_low, g.t_safe)
                if cancel is not None:
                    e_low = min(e_low, cancel)
                qf = g.q_fill_at(e_low)
                t_qf = g.first_fill_before(e_low)
                whole = g.t_whole is not None and g.t_whole < e_low
                elr = g.credit_until(min(e_low, g.t_whole) if whole else e_low)
                el_cost += qf * PX
                el_whole += 1 if whole else 0
                el_cr += floored(g.credit_until(e_low if t_qf is None else t_qf)) * PAID_FRAC
                cr_raw += raw
                cr_fl += floored(raw)
                cr_old += old
                rows.append({"tk": tk, "d0": g.d0, "end": round(e - self.open, 3),
                             "cause": "swept" if tk in swept else ("safe" if safe else (
                                 "cancel" if cancel is not None and e >= cancel - 1e-9 and e < g.exit else "exit")),
                             "raw": round(raw, 5), "old": round(old, 5), "counted": g.counted_until(e),
                             "elow_q": round(qf, 2), "elow_whole": whole, "elow_raw_whole": round(elr, 5),
                             "elow_t_fill": None if t_qf is None else round(t_qf - self.open, 3)})
                if tk in swept:
                    self.log.write("vfill", hour=self.key, ticker=tk, kind="dead_swept_emain", variant=v,
                                   t_fill=iso(swept[tk]), cost=DEAD_COST, assumed=(st["assumed"] == tk))
            n = len(posted)
            n_sw = len(swept)
            if v == "V1":
                cost_det = DEAD_COST * max(n_sw, 1 if st["g1"] >= 1 else 0) + SAFE_COST * n_safe
            else:
                cost_det = DEAD_COST * (st["n_pre"] + (max(st["n_win"], 1) if st["g1"] >= 1 else 0)) \
                    + SAFE_COST * n_safe
            out[v] = {"n": n, "why": self.var[v]["why"], "credit_raw": round(cr_raw, 5), "credit_fl": round(cr_fl, 5),
                      "credit_x09": round(cr_fl * PAID_FRAC, 5), "credit_old_raw": round(cr_old, 5),
                      "n_swept": n_sw, "n_safe": n_safe, "g1": st["g1"], "n_pre": st["n_pre"], "n_win": st["n_win"],
                      "assumed": st["assumed"], "cost_det": round(cost_det, 4),
                      "net_det": round(cr_fl * PAID_FRAC - cost_det, 4),
                      "elow_cost": round(el_cost + SAFE_COST * n_safe, 4), "elow_whole": el_whole,
                      "elow_credit_x09": round(el_cr, 5), "ghosts": rows}
        sweeper = self.t1 is not None and self.t1 < self.exit
        # observable = something showed either way: a >= 500-lot far stack (an episode) or any >= 100-lot dead-side
        # 1c sweep (a near one dominates every ghost under E_main and is cost evidence, never imputed away)
        observable = sweeper or any(e["t0"] < self.exit for e in self.ep_done) \
            or any(s_["t"] < self.exit for s_ in self.sweeps)
        cells = sorted(set(self.expo) | set(self.ep_cnt))
        self.outcome = {
            "observable": observable, "sweeper": sweeper,
            "t1_from_open": round(self.t1 - self.open, 3) if self.t1 is not None else None,
            "trigger": ({k: self.trigger[k] for k in ("tk", "d", "n_fire", "s_left", "lag_ms")}
                        if self.trigger else None),
            "burst": self.burst, "n_sweeps": len(self.sweeps),
            "n_sweeps_far": sum(1 for s in self.sweeps if s["far"]),
            "episodes": {c: dict(self.ep_cnt[c]) for c in cells if self.ep_cnt[c]},
            "exposure_s": {c: round(self.expo[c], 3) for c in cells if self.expo[c] > 0},
            "unclassified_trades": self.unclassified, "safe_prints_real": len(self.safe_fills_real),
            "unclassified_1c_max": round(max(self.unclass_1c.values() or [0.0]), 2),
            "yhat_off_s": dict(self.off_s), "ws_silent_max_s": round(self.silent_max, 1),
            "var": out,
            "ghosts": {tk: {"series": g.series, "K": g.K, "dead": g.dead, "d0": g.d0,
                            "t_post": round(g.t_post - self.open, 3),
                            "t_safe": None if g.t_safe is None else round(g.t_safe - self.open, 3),
                            "safe_prints": g.safe_prints, "cum_min": g.cum_min()}
                       for tk, g in self.ghosts.items()},
        }
        return self.outcome

    def audit_check(self, rest_trades):
        """Every WS trade of the hour must be in REST and vice versa (by trade_id)."""
        lo, hi = self.open - 60, self.close + 60
        ws_ids = {tid for tid, r in self.trades.items() if lo <= r[1] <= hi + 30}
        rest_ids = set()
        for tk, rows in rest_trades.items():
            for tid, ct, n, yp, side in rows:
                if tid and ct is not None and lo <= ct <= hi:
                    rest_ids.add(tid)
        ws_in = {tid for tid in ws_ids if self.trades[tid][2] is None or
                 lo <= (f(self.trades[tid][2], 0.0) / 1000.0) <= hi}
        miss_rest = sorted(ws_in - rest_ids)
        miss_ws = sorted(rest_ids - ws_ids)
        clean = not miss_rest and not miss_ws and not self.trades_noid
        return {"status": "clean" if clean else "tape_gap", "ws": len(ws_in), "rest": len(rest_ids),
                "missing_in_rest": miss_rest[:20], "missing_in_ws": miss_ws[:20], "n_missing_in_rest": len(miss_rest),
                "n_missing_in_ws": len(miss_ws), "ws_noid": len(self.trades_noid)}

    def audit_tickers(self):
        tks = {r[0] for r in self.trades.values()} | {r[0] for r in self.trades_noid}
        if self.results:
            tks |= {tk for tk, r in self.results.items() if tk in self.markets and (r.get("vol") or 0) > 0}
        else:
            tks |= set(self.markets or {})
        return sorted(tks)


# ================================================================================================ the recorder
class Recorder:
    def __init__(self, log, now=time.time):
        self.log, self.now = log, now
        self.hours = {}
        self.tk_hour = {}
        self.outcomes = {}          # open -> {"day", "var": {v: {"cost_det", "credit_x09"}}, "sweeper"}
        self.planned_restore = {}   # open -> [post records]
        self.summaries = 0
        self.last_sec = None
        self.last_health = 0.0
        self.last_resync = 0.0
        self.finished = set()

    # ---------------- the virtual pot (spec 3.6) ----------------
    def pot_at_day_start(self, v, day):
        pot = POT0
        d0 = datetime.strptime(day, "%Y-%m-%d")
        for o, oc in self.outcomes.items():
            od = oc["day"]
            if od >= day:
                continue
            x = oc["var"].get(v) or {}
            pot -= x.get("cost_det", 0.0)
            if (d0 - datetime.strptime(od, "%Y-%m-%d")).days >= CREDIT_LAG_DAYS:
                pot += x.get("credit_x09", 0.0)
        return pot

    def day_loss(self, v, day):
        return sum((oc["var"].get(v) or {}).get("cost_det", 0.0) for oc in self.outcomes.values() if oc["day"] == day)

    def budget_room_fn(self, day):
        def room(v, n_resting):
            budget = DAY_BUDGET_FRAC * self.pot_at_day_start(v, day)
            need = self.day_loss(v, day) + DEAD_COST * n_resting + DEAD_COST
            return need <= budget + 1e-9
        return room

    # ---------------- restore from the log (the log is the truth) ----------------
    def restore(self, path):
        if not path or not os.path.exists(path):
            return {"outcomes": 0, "posts": 0}
        n_post = 0
        keys = _ev_keys(("hour_outcome", "hour_plan", "post"))
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not any(k in line for k in keys):
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ev = r.get("ev")
                if ev == "hour_outcome":
                    o = r.get("open")
                    self.outcomes[o] = {"day": r.get("day"), "sweeper": r.get("sweeper"),
                                        "var": {v: {"cost_det": (x or {}).get("cost_det", 0.0),
                                                    "credit_x09": (x or {}).get("credit_x09", 0.0)}
                                                for v, x in (r.get("var") or {}).items()}}
                elif ev == "hour_plan":
                    o = parse_ts(r["hour"].replace("Z", ":00Z"))
                    self.planned_restore.setdefault(o, [])
                elif ev == "post":
                    o = parse_ts(r["hour"].replace("Z", ":00Z"))
                    self.planned_restore.setdefault(o, []).append(r)
                    n_post += 1
        return {"outcomes": len(self.outcomes), "posts": n_post, "planned_hours": len(self.planned_restore)}

    def _new_hour(self, o, now):
        partial = now > o + PLAN_S + 1
        h = HourRec(o, self.log, partial=partial)
        prev = self.outcomes.get(o - 3600)
        h.prev_sweeper = bool(prev and prev.get("sweeper"))
        if o in self.planned_restore:
            h.restarted = True
            h.partial = True
        self.hours[o] = h
        return h

    def _restore_ghosts(self, h, ws, now):
        posts = self.planned_restore.get(h.open)
        h.planned = True
        for r in posts or []:
            tk = r["ticker"]
            if tk not in (h.markets or {}) or tk in h.ghosts:
                continue
            p = dict(r.get("prog") or {})
            lv = ws.levels(tk)
            ahead = (lv[0] if r["dead"] == "yes" else lv[1]).get(PX, 0.0) if lv else 0.0
            g = Ghost(tk, r["series"], r["K"], r["dead"], r["d"], r["t_post"], p, r["exit"], ahead, r["variants"])
            g.next_i = max(0, min(len(g.inc), int(now - g.t_post)))   # the seconds we were down earn nothing
            h.ghosts[tk] = g
            h.ghost_order.append(tk)
            for v in r["variants"]:
                h.var[v]["posted"].append(tk)
        self.log.write("restored_hour", hour=h.key, ghosts=h.ghost_order, note="planned before a restart: no re-plan, "
                       "no double post; hour flagged partial (excluded from the bar)")

    # ---------------- the loop body ----------------
    def step(self, now, ws, jobs, rest_call):
        for ev in ws.drain():
            tk = ev[2].get("market_ticker") if ev[0] == "trade" else ev[2]
            h = self.tk_hour.get(tk)
            if h is not None:
                h.on_event(ev)
        for name, key, res in jobs.poll():
            self.on_job(name, key, res, now, ws)
        cur = hour_open(now)
        for o in (cur, cur + 3600):
            if o not in self.hours and o not in self.finished and is_trading_hour(o) \
                    and now >= o - DISCOVER_LEAD_S and now < o + PERIOD_S - EXIT_S:
                self._new_hour(o, now)
        sec = int(now)
        new_sec = self.last_sec is None or sec > self.last_sec
        for o in sorted(self.hours):
            h = self.hours[o]
            self.schedule(h, now, ws, jobs, rest_call)
            if new_sec:
                h.tick(sec, ws)
                h.score10(sec)
        self.last_sec = sec
        if hasattr(ws, "last_rx_s"):
            self.check_silence(now, ws)
        if now - self.last_health >= 600:
            self.last_health = now
            lb_rx = getattr(getattr(ws, "lb", None), "last_rx_ms", None)
            self.log.write("health", ws=ws.health(), connected=ws.connected(), hours=[h.key for h in self.hours.values()],
                           last_rx_age_s=None if lb_rx is None else round(now - lb_rx / 1000.0, 1),
                           rest_calls=getattr(getattr(rest_call, "__self__", None), "n", None))
        done = [o for o, h in self.hours.items() if h.summary is not None]
        for o in done:
            h = self.hours.pop(o)
            self.finished.add(o)
            for tk in h.markets or {}:
                if self.tk_hour.get(tk) is h:
                    self.tk_hour.pop(tk, None)

    def check_silence(self, now, ws):
        """Spec 6.1 / risk 10: a socket that is "connected" but delivers nothing is BLIND, not a quiet book (the
        collector's went near-silent 10-15 07:00Z; RATEH tops of book changed in every one of 101 REST polls 40-60 s
        apart over the 10-15 09Z hour, refuters' live_poll / watch logs). No frame of any kind for > SILENT_S while an
        hour is subscribed -> that hour's silent span inside [open, exit] is a WS gap (blind_max, excluded by 6.1),
        measured from max(last frame, the hour's subscribe) so an overnight-idle socket never blinds 07Z; and the
        socket is resynced (fresh snapshots) at most once per SILENT_S."""
        rx = ws.last_rx_s()
        quiet_h = []
        for h in self.hours.values():
            if not h.subscribed or h.sub_t is None or not (h.open - SUB_LEAD_S <= now < h.close):
                continue
            since = h.sub_t if rx is None else max(rx, h.sub_t)
            quiet = now - since
            if quiet <= SILENT_S:
                continue
            span = min(now, h.exit) - max(since, h.open)
            if span > h.silent_max:
                h.silent_max = span
                h.blind_max = max(h.blind_max, span)
            quiet_h.append((h, quiet))
        if quiet_h and now - self.last_resync > SILENT_S:
            self.last_resync = now
            self.log.write("ws_silent", silent_s=round(max(q for _, q in quiet_h), 1),
                           hours=[h.key for h, _ in quiet_h], last_rx=None if rx is None else iso(rx),
                           action="resync; the silent span inside [open, exit] counts as a WS gap")
            ws.resync()

    def schedule(self, h, now, ws, jobs, call):
        o = h.open
        if h.markets is None:
            if h.discover_empty_after_open or now >= h.exit:
                h.planned = True
                h.markets = {}
                self.log.write("hour_skip", hour=h.key, why="no_markets listed for this hour (holiday or withdrawn)")
                h.summary = {"skipped": True}
            elif now >= h.discover_next:
                jobs.submit("discover", o, lambda c=h.close: job_discover(call, c))
            return
        if h.prog_status in ("pending", "unreadable") and now >= h.prog_next and now < o + PLAN_S and h.markets:
            jobs.submit("programs", o, lambda t=tuple(h.markets): job_programs(call, t))
        if not h.subscribed and now >= o - SUB_LEAD_S and h.markets:
            ws.subscribe(sorted(h.markets))
            h.subscribed = True
            h.sub_t = now
            for tk in h.markets:
                self.tk_hour[tk] = h
        if not h.planned and now >= o + PLAN_S:
            if h.open in self.planned_restore:
                self._restore_ghosts(h, ws, now)
            else:
                day = h.day
                h.plan(int(now) if not h.partial else now, ws, self.budget_room_fn(day))
        if h.outcome is None and now >= h.exit + SWEPT_WIN_S + 2:
            for tk in list(h.ep_open):
                h._end_ep(h.ep_open[tk], h.exit, "survived")
            for ep in list(h.ep_ending):
                h.ep_ending.remove(ep)
                h._finalize_ep(ep)
            h._finish_burst(now + 999)
            oc = h.compute_outcome()
            self.outcomes[o] = {"day": h.day, "sweeper": oc["sweeper"],
                                "var": {v: {"cost_det": x["cost_det"], "credit_x09": x["credit_x09"]}
                                        for v, x in oc["var"].items()}}
            self.log.write("hour_outcome", hour=h.key, open=o, day=h.day, sweeper=oc["sweeper"],
                           observable=oc["observable"],
                           var={v: {k: x[k] for k in ("n", "cost_det", "credit_x09", "net_det")} for v, x in oc["var"].items()})
            self._state(h)
        if not h.dropped and now >= h.close + 60 and h.subscribed:
            ws.drop(sorted(h.markets))
            h.dropped = True
        if h.results is None and h.results_tries < 5 and now >= h.close + 180 + 120 * h.results_tries:
            evs = sorted({m["event"] for m in h.markets.values() if m.get("event")})
            if jobs.submit("results", o, lambda e=tuple(evs): job_results(call, e)):
                h.results_tries += 1
        if h.audit is None and h.outcome is not None and now >= h.close + 600 + 300 * h.audit_tries \
                and (h.results is not None or h.results_tries >= 5):
            if h.audit_tries >= 3:
                h.audit = {"status": "failed"}
            else:
                tks = h.audit_tickers()
                if jobs.submit("audit", o, lambda t=tuple(tks), lo=h.open - 60, hi=h.close + 60: job_trades(call, t, lo, hi)):
                    h.audit_tries += 1
        if h.summary is None and h.audit is not None and h.outcome is not None:
            self.write_summary(h)

    def on_job(self, name, o, res, now, ws):
        h = self.hours.get(o)
        if h is None:
            return
        err = res.get("_error") if isinstance(res, dict) else None
        if name == "discover":
            if res is None or err:
                h.discover_next = now + 30
                self.log.write("error", where="discover", hour=h.key, err=err or "unreadable; retry in 30 s")
            elif not res:
                if now >= o:
                    h.discover_empty_after_open = True
                h.discover_next = max(now + 30, o + 5)
                self.log.write("discover", hour=h.key, n=0, note="no markets listed for this hour")
            else:
                h.set_markets(res)
                self.log.write("discover", hour=h.key, n=len(h.markets),
                               per_series={s: len(v) for s, v in h.tenors.items()},
                               closes=sorted({iso(m["close"]) for m in h.markets.values() if m.get("close")}),
                               pls=sorted({str(m.get("pls")) for m in h.markets.values()}))
        elif name == "programs":
            if res is None or err:
                h.prog_status = "unreadable"
                h.prog_next = now + 30
                self.log.write("programs", hour=h.key, status="unreadable", err=err, retry_s=30)
            else:
                h.progs = res
                mine = {tk: p for tk, p in res.items() if tk in h.markets}
                h.prog_status = "listed" if mine else "none"
                rewards = collections.Counter(round(p["reward"], 4) for p in mine.values())
                self.log.write("programs", hour=h.key, status=h.prog_status, n_listed=len(mine),
                               n_markets=len(h.markets), rewards={str(k): c for k, c in rewards.items()},
                               targets=sorted({p["target"] for p in mine.values()}),
                               dfs=sorted({p["df"] for p in mine.values()}),
                               periods=sorted({period_of(p) for p in mine.values()}))
        elif name == "results":
            if res is None or err:
                self.log.write("error", where="results", hour=h.key, err=err or "unreadable")
            else:
                h.results = res
                self.log.write("results", hour=h.key,
                               settle={s: next((r["settle"] for tk, r in res.items()
                                                if tk in h.markets and h.markets[tk]["series"] == s), None)
                                       for s in h.tenors},
                               n_vol=sum(1 for tk, r in res.items() if tk in h.markets and (r.get("vol") or 0) > 0))
        elif name == "audit":
            if res is None or err:
                self.log.write("error", where="audit", hour=h.key, err=err or "unreadable", tries=h.audit_tries)
            else:
                h.audit = h.audit_check(res)
                self.log.write("audit", hour=h.key, **h.audit)

    def write_summary(self, h):
        oc = h.outcome
        s = {"hour": h.key, "open": h.open, "day": h.day, "et": et_label(h.open),
             "weekday": datetime.fromtimestamp(h.open, UTC).weekday() < 5, "blackout": h.blackout,
             "partial": h.partial, "restarted": h.restarted, "ws_blind_max_s": round(h.blind_max, 1),
             "audit": (h.audit or {}).get("status"), "programs": h.prog_status,
             "n_markets": len(h.markets or {}), "prev_sweeper": h.prev_sweeper}
        s.update(oc)
        h.summary = s
        self.summaries += 1
        self.log.write("hour_summary", **s)
        if datetime.fromtimestamp(h.open, UTC).hour == HOURS_Z[-1]:
            day_rows = [x for x in self.outcomes.values() if x["day"] == h.day]
            self.log.write("day_summary", day=h.day, hours=len(day_rows),
                           var={v: {"cost_det": round(sum((x["var"].get(v) or {}).get("cost_det", 0) for x in day_rows), 4),
                                    "credit_x09": round(sum((x["var"].get(v) or {}).get("credit_x09", 0)
                                                            for x in day_rows), 4),
                                    "pot_start": round(self.pot_at_day_start(v, h.day), 4)} for v in VARIANTS})

    def _state(self, h):
        if not getattr(self.log, "path", None):
            return
        try:
            st = {"t": iso(self.now()), "last_hour": h.key,
                  "pot_start_today": {v: round(self.pot_at_day_start(v, h.day), 4) for v in VARIANTS},
                  "loss_today": {v: round(self.day_loss(v, h.day), 4) for v in VARIANTS},
                  "hours_recorded": len(self.outcomes),
                  "current": {k: {"ghosts": x.ghost_order, "planned": x.planned} for k, x in
                              ((x.key, x) for x in self.hours.values())}}
            tmp = STATE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(st, fh, indent=1)
            os.replace(tmp, STATE_PATH)
        except Exception as e:                                  # noqa: BLE001
            self.log.write("error", where="state", err=repr(e)[:200])


def loop(rec, ws, jobs, rest_call, clock, sleep, stop_path, end_t, dt=0.1, max_steps=None):
    """The main loop (production and the self-test's fake clock). Returns the stop reason."""
    steps = 0
    errs = {}                                   # repr -> [last logged t, repeats since]
    while True:
        if stop_path and os.path.exists(stop_path):
            rec.log.write("stop", why="stop file", path=stop_path)
            return "stop_file"
        now = clock()
        if now >= end_t:
            rec.log.write("stop", why="minutes elapsed")
            return "minutes"
        try:
            rec.step(now, ws, jobs, rest_call)
        except Exception as e:                                  # noqa: BLE001
            # throttled: a persistent exception at 10 steps/s would otherwise write ~860k rows a day
            k = repr(e)[:400]
            st = errs.get(k)
            if st is None or now - st[0] >= ERR_LOG_EVERY_S:
                rec.log.write("error", where="step", err=k, repeats_since_last=0 if st is None else st[1])
                errs[k] = [now, 0]
                if len(errs) > 50:
                    errs.pop(next(iter(errs)))
            else:
                st[1] += 1
        steps += 1
        if max_steps is not None and steps >= max_steps:
            return "max_steps"
        sleep(dt)


# ================================================================================================ the bar (--report)
def _hour_cost_credit(s, v, b, p, ttfs, estimator="main"):
    """(n, credit, cost, imputed) for one hour summary and variant under burst share b, sweeper rate p, ttfs."""
    x = (s.get("var") or {}).get(v) or {}
    n = x.get("n", 0) or 0
    if n == 0:
        return 0, 0.0, 0.0, False
    if estimator == "low":
        return n, x.get("elow_credit_x09", 0.0), x.get("elow_cost", 0.0), False
    n_safe = x.get("n_safe", 0)
    if s.get("observable"):
        g1 = x.get("g1", 0)
        if v == "V1":
            cost = x.get("cost_det", 0.0)
        elif g1 >= 1:
            cost = DEAD_COST * (x.get("n_pre", 0) + max(x.get("n_win", 0), 1.0 + b * (g1 - 1))) + SAFE_COST * n_safe
        else:
            cost = DEAD_COST * x.get("n_pre", 0) + SAFE_COST * n_safe
        return n, x.get("credit_x09", 0.0), cost, False
    # unobservable: the observed sweeper-hour rate, the sweep at the ghost's post + median time-to-first-sweep
    if p is None or ttfs is None:
        return n, x.get("credit_x09", 0.0), SAFE_COST * n_safe, "unimputable"
    gh = s.get("ghosts") or {}
    rows = x.get("ghosts") or []
    full = sum(floored(r.get("raw", 0.0)) * PAID_FRAC for r in rows)
    t_posts = [gh.get(r["tk"], {}).get("t_post", PLAN_S) for r in rows]
    t_imp = (min(t_posts) if t_posts else PLAN_S) + ttfs
    exit_rel = PERIOD_S - EXIT_S
    if t_imp >= exit_rel:
        return n, full, SAFE_COST * n_safe, True
    trunc, g_imp = 0.0, 0
    for r in rows:
        meta = gh.get(r["tk"], {})
        cm = meta.get("cum_min") or [0.0]
        tp = meta.get("t_post", PLAN_S)
        x_s = max(0.0, t_imp - tp)
        i = int(x_s // 60)
        if i + 1 < len(cm):
            val = cm[i] + (cm[i + 1] - cm[i]) * ((x_s - 60 * i) / 60.0)
        else:
            val = cm[-1]
        end_rel = r.get("end", exit_rel)
        if r.get("cause") in ("safe",) and end_rel <= t_imp:
            trunc += floored(r.get("raw", 0.0)) * PAID_FRAC
            continue
        g_imp += 1
        trunc += floored(min(val, r.get("raw", val))) * PAID_FRAC
    if v == "V1":
        swept_cost = DEAD_COST if g_imp else 0.0
        cred = full
    else:
        swept_cost = DEAD_COST * (1.0 + b * (g_imp - 1)) if g_imp else 0.0
        cred = (1 - p) * full + p * trunc
    return n, cred, p * swept_cost + SAFE_COST * n_safe, True


EXCLUSIONS = ("skipped", "weekend", "before_first_day", "blackout", "partial", "ws_gap", "tape_gap", "audit_not_clean",
              "unclassified_1c")


def exclusion_of(s):
    """6.1 population: None if the hour is in it, else the FIRST reason it is not (each hour counted once)."""
    if s.get("skipped"):
        return "skipped"
    if not s.get("weekday"):
        return "weekend"
    if (s.get("day") or "") < FIRST_DAY:
        return "before_first_day"
    if s.get("blackout"):
        return "blackout"
    if s.get("partial"):
        return "partial"
    if (s.get("ws_blind_max_s") or 0) > BLIND_MAX_S + 1e-9:
        return "ws_gap"
    if s.get("audit") != "clean":
        return "tape_gap" if s.get("audit") == "tape_gap" else "audit_not_clean"
    if (s.get("unclassified_1c_max") or 0) >= TRIGGER_N - 1e-9:
        return "unclassified_1c"                 # a >= 100-lot 1c print we could not side: cost unknown
    return None


def evaluate_bar(summaries, program_days=None, variant=BAR_VARIANT):
    """The pre-registered bar of SPEC 6 over hour summaries. Returns a dict with the verdict and every number."""
    pop = []
    excl = {k: 0 for k in EXCLUSIONS}
    for s in summaries:
        why = exclusion_of(s)
        if why is None:
            pop.append(s)
        else:
            excl[why] = excl.get(why, 0) + 1
    days = sorted({s["day"] for s in pop})
    obs = [s for s in pop if s.get("observable")]
    sw = [s for s in obs if s.get("sweeper")]
    p = (len(sw) / len(obs)) if obs else None
    ttfs = median([s["t1_from_open"] for s in sw if s.get("t1_from_open") is not None])
    at_risk = sum((s.get("burst") or {}).get("at_risk", 0) for s in sw)
    hits = sum((s.get("burst") or {}).get("hits_0.3", 0) for s in sw)
    b_point = (hits / at_risk) if at_risk else 0.0
    b_up = cp_upper(hits, at_risk, 0.90)

    def agg(rows, b, est="main", v=variant):
        n_tot, c_tot, k_tot, per, imp = 0, 0.0, 0.0, [], 0
        for s in rows:
            n, c, k, im = _hour_cost_credit(s, v, b, p, ttfs, est)
            n_tot += n
            c_tot += c
            k_tot += k
            imp += 1 if im is True else 0
            if n:
                per.append((n, c - k))
        net = (c_tot - k_tot) / n_tot if n_tot else None
        se = None
        if n_tot and len(per) >= 2 and net is not None:
            mbar = n_tot / len(per)
            se = math.sqrt(sum((y - net * n) ** 2 for n, y in per) / (len(per) * (len(per) - 1))) / mbar
        return {"strike_hours": n_tot, "hours_with_posts": len(per), "credit": round(c_tot, 4), "cost": round(k_tot, 4),
                "net_per_sh": None if net is None else round(net, 4),
                "credit_per_sh": round(c_tot / n_tot, 4) if n_tot else None,
                "se_cluster_hour": None if se is None else round(se, 4), "imputed_hours": imp}

    main_up = agg(pop, b_up)
    main_pt = agg(pop, b_point)
    low_pt = agg(pop, b_point, "low")
    half = (len(days) + 1) // 2
    h1 = agg([s for s in pop if s["day"] in days[:half]], b_up)
    h2 = agg([s for s in pop if s["day"] in days[half:]], b_up)
    sh_per_day = (main_up["strike_hours"] / len(days)) if days else 0.0
    obs_days = len({s["day"] for s in obs})
    pass_checks = {
        "observable_hours>=50_on>=5_weekdays": len(obs) >= 50 and obs_days >= 5,
        "net_at_b_upper>=+2.00": main_up["net_per_sh"] is not None and main_up["net_per_sh"] >= 2.0,
        "positive_both_halves": all(x["net_per_sh"] is not None and x["net_per_sh"] > 0 for x in (h1, h2)),
        "credit_per_sh>=5.00": main_up["credit_per_sh"] is not None and main_up["credit_per_sh"] >= 5.0,
        "strike_hours_per_weekday>=60": sh_per_day >= 60.0,
    }
    kill_ready = len(days) >= 3 and len(pop) >= 30
    prog_kill = False
    if program_days:
        wd = sorted(program_days)
        for a, b2 in zip(wd, wd[1:]):
            if not program_days[a] and not program_days[b2]:
                prog_kill = True
    kill_checks = {
        "net_at_b_point<=0": main_pt["net_per_sh"] is not None and main_pt["net_per_sh"] <= 0.0,
        "elow_net<=0": low_pt["net_per_sh"] is not None and low_pt["net_per_sh"] <= 0.0,
        "sweeper_share>=0.80": p is not None and p >= 0.80,
        "credit_per_sh<3.00": main_pt["credit_per_sh"] is not None and main_pt["credit_per_sh"] < 3.0,
        "programs_unlisted_2_consecutive_weekdays": prog_kill,
    }
    if kill_ready and any(kill_checks.values()):
        verdict = "KILL"
    elif all(pass_checks.values()):
        verdict = "PASS"
    elif kill_ready:
        verdict = "EXTEND"
    else:
        verdict = "TOO_EARLY"
    variants = {}
    for v in VARIANTS:
        if v != variant:
            variants[v] = {"b_point": agg(pop, b_point, v=v), "b_upper": agg(pop, b_up, v=v)}
    return {"verdict": verdict, "population_hours": len(pop), "clusters": len(pop), "weekdays": len(days),
            "days": days, "observable_hours": len(obs), "observable_days": obs_days, "sweeper_hours": len(sw),
            "sweeper_share": None if p is None else round(p, 4), "ttfs_median_s": ttfs,
            "burst": {"at_risk": at_risk, "hits": hits, "b_point": round(b_point, 4), "b_upper90": round(b_up, 4)},
            "v2_b_upper": main_up, "v2_b_point": main_pt, "v2_elow": low_pt, "half1": h1, "half2": h2,
            "strike_hours_per_weekday": round(sh_per_day, 2), "pass_checks": pass_checks,
            "kill_ready": kill_ready, "kill_checks": kill_checks, "excluded": excl,
            "logged_only_variants": variants}


REPORT_EVS = ("hour_summary", "programs")


def _ev_keys(evs):
    """Substrings a line must contain to be parsed at all (compact or spaced JSON); the `ev` check follows."""
    return tuple(fmt % e for e in evs for fmt in ('"ev":"%s"', '"ev": "%s"'))


def read_log(path, evs=REPORT_EVS):
    """The log rows whose `ev` is in evs (None = every row). Only matching lines are parsed: the whole log is ~2-3 MB
    a weekday and parsing every row put --report at 168 MB at 10 weekdays (review finding 5)."""
    rows = []
    if not os.path.exists(path):
        return rows
    keys = None if evs is None else _ev_keys(evs)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if keys is not None and not any(k in line for k in keys):
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if evs is None or r.get("ev") in evs:
                rows.append(r)
    return rows


def program_days_of(rows):
    """{ET weekday: any RATEH program listed} from `programs` records, for days the recorder read >= 10 hours."""
    per = collections.defaultdict(lambda: [0, False])
    for r in rows:
        if r.get("ev") != "programs" or r.get("status") == "unreadable":
            continue
        o = parse_ts(str(r.get("hour", "")).replace("Z", ":00Z"))
        if o is None:
            continue
        d = et_date(o)
        per[d][0] += 1
        per[d][1] = per[d][1] or r.get("status") == "listed"
    return {d: v[1] for d, v in per.items() if v[0] >= 10}


def report(path=LOG_PATH, out=print):
    rows = read_log(path, REPORT_EVS)
    sums = [r for r in rows if r.get("ev") == "hour_summary"]
    out("ratehreward_paper --report: %d hour summaries in %s" % (len(sums), path))
    by_day = collections.defaultdict(list)
    for s in sums:
        by_day[s.get("day")].append(s)
    for d in sorted(by_day):
        e = evaluate_bar(by_day[d])
        m = e["v2_b_point"]
        out("  %s ET: hours %d (observable %d, sweeper %d) | V2 strike-hours %d | credit/sh %s | net/sh at b point %s | "
            "E_low net/sh %s" % (d, e["population_hours"], e["observable_hours"], e["sweeper_hours"], m["strike_hours"],
                                 m["credit_per_sh"], m["net_per_sh"], e["v2_elow"]["net_per_sh"]))
    e = evaluate_bar(sums, program_days_of(rows))
    out("POOLED: " + json.dumps({k: e[k] for k in ("verdict", "population_hours", "weekdays", "observable_hours",
                                                   "sweeper_share", "ttfs_median_s", "burst",
                                                   "strike_hours_per_weekday")}))
    for k in ("v2_b_upper", "v2_b_point", "v2_elow", "half1", "half2"):
        out("  %-11s %s" % (k, json.dumps(e[k])))
    out("  PASS checks: %s" % json.dumps(e["pass_checks"]))
    out("  KILL checks (ready=%s): %s" % (e["kill_ready"], json.dumps(e["kill_checks"])))
    out("  excluded hours: %s" % json.dumps(e["excluded"]))
    out("  logged-only variants (hypotheses, never the verdict): %s" % json.dumps(e["logged_only_variants"]))
    out("VERDICT: %s" % e["verdict"])
    e["log_rows_parsed"] = len(rows)
    return e


# ================================================================================================ --history
def history(day, call, out=print, gate=True):
    """6.4 reproduction gate: candle presence (no size) + the trade tape for a settled weekday, with hazard_new's
    estimator. Population: strikes 6-8 bp from the PREVIOUS hour's settle; 'stayed_far' = >= 4 bp from its own."""
    d0 = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
    lo, hi = d0 + 7 * 3600, d0 + 21 * 3600
    mk = []
    for s in SERIES:
        got = None
        for extra in ({}, {"status": "settled"}, {"status": "closed"}):
            cur, rows, ok = None, [], False
            for _ in range(5):
                q = {"series_ticker": s, "min_close_ts": str(int(lo)), "max_close_ts": str(int(hi)), "limit": "1000"}
                q.update(extra)
                if cur:
                    q["cursor"] = cur
                st, b = call("/markets", q)
                if st != 200 or not isinstance(b, dict):
                    break
                ok = True
                rows.extend(b.get("markets") or [])
                cur = b.get("cursor")
                if not cur or not b.get("markets"):
                    break
            if ok and rows:
                got = rows
                break
        for m in got or []:
            mk.append({"t": m["ticker"], "s": s, "k": f(m.get("floor_strike")), "set": f(m.get("expiration_value")),
                       "close": parse_ts(m.get("close_time")), "open": parse_ts(m.get("open_time")),
                       "vol": f(m.get("volume_fp"), 0.0)})
    settle = {(m["s"], m["close"]): m["set"] for m in mk if m["set"] is not None and m["close"]}
    pop = []
    for m in mk:
        if m["set"] is None or m["k"] is None or m["close"] is None:
            continue
        p = settle.get((m["s"], m["close"] - 3600))
        if p is None:
            continue
        d0_ = (m["k"] - p) * 100.0
        if 6.0 - 1e-9 <= abs(d0_) < 8.0 - 1e-9:
            m["d0"], m["d1"], m["dead"] = round(d0_, 2), round((m["k"] - m["set"]) * 100.0, 2), (
                "yes" if d0_ > 0 else "no")
            pop.append(m)
    out("history %s: markets %d, 6-8 bp population %d" % (day, len(mk), len(pop)))
    expo = collections.defaultdict(lambda: [0.0] * len(BUCKETS))
    hits = collections.defaultdict(lambda: [0] * len(BUCKETS))
    hours_swept = collections.defaultdict(set)
    for m in pop:
        st, c = call("/series/%s/markets/%s/candlesticks" % (m["s"], m["t"]),
                     {"start_ts": str(int(m["open"])), "end_ts": str(int(m["close"]) + 60), "period_interval": "1"})
        cs = (c or {}).get("candlesticks") or [] if st == 200 and isinstance(c, dict) else []
        mins = []
        for x in cs:
            yb, ya = x.get("yes_bid") or {}, x.get("yes_ask") or {}
            mins.append((x.get("end_period_ts"), f(yb.get("close_dollars")), f(ya.get("close_dollars")),
                         f(yb.get("high_dollars")), f(ya.get("low_dollars"))))
        key = "into_play" if abs(m["d1"]) < 4.0 else "stayed_far"
        for e in presence_minutes([r for r in mins if r[0] is not None], m["dead"]):
            s_left = m["close"] - e + 30.0
            if s_left >= 0:
                expo[key][bucket(s_left)] += 60.0
        if m["vol"] > 0:
            stt, tr = call("/markets/trades", {"ticker": m["t"], "limit": "1000"})
            raw = []
            for x in ((tr or {}).get("trades") or []) if stt == 200 and isinstance(tr, dict) else []:
                k = classify(m["d0"], x.get("taker_side"), f(x.get("yes_price_dollars")))
                if k:
                    raw.append((parse_ts(x.get("created_time")), k, f(x.get("count_fp"), 0.0)))
            for ev in group(raw):
                if ev["kind"] == "dead_sweep" and ev["n"] >= 500:
                    hits[key][bucket(m["close"] - ev["t0"])] += 1
                    hours_swept[key].add(datetime.fromtimestamp(m["close"], UTC).strftime("%H:%MZ"))
    res = {}
    for key in sorted(set(expo) | set(hits)):
        sh = sum(expo[key]) / 3600.0
        res[key] = {"stack_hours": round(sh, 3), "sweeps_ge500": sum(hits[key]),
                    "hazard_per_h": round(sum(hits[key]) / sh, 3) if sh > 0 else None,
                    "by_bucket_stack_hours": [round(x / 3600.0, 3) for x in expo[key]], "by_bucket_sweeps": hits[key],
                    "hours_swept": sorted(hours_swept[key])}
        out("  %-10s %s" % (key, json.dumps(res[key])))
    if gate and day == "2026-10-16":
        sf = res.get("stayed_far") or {"sweeps_ge500": 0, "stack_hours": 0.0}
        ok = abs(sf["sweeps_ge500"] - 6) <= 1 and abs(sf["stack_hours"] - 3.15) <= 0.315
        out("REPRODUCTION GATE 6.4 (stayed_far 6-8 bp: 6 +-1 sweeps, 3.15 +-10%% stack-hours): %s"
            % ("PASS" if ok else "FAIL"))
        res["gate"] = ok
    return res


# ================================================================================================ --once
def once(call, now, out=print, log=None):
    """Plan the current (open) or next weekday hour over REST, print it; no socket, nothing posted."""
    o = hour_open(now)
    if not (is_trading_hour(o) and now < o + PERIOD_S):
        o = o + 3600
        while not is_trading_hour(o):
            o += 3600
    close = o + PERIOD_S
    rows = job_discover(call, close)
    out("once: hour %s (%s), blackout=%s, markets=%s" % (iso_hour(o), et_label(o), blackout_of(o),
                                                       None if rows is None else len(rows)))
    if not rows:
        return None
    progs = job_programs(call, [m["ticker"] for m in rows])
    out("  programs: %s" % ("UNREADABLE (hour refused)" if progs is None else "%d of %d listed" % (len(progs), len(rows))))
    if now < o:
        out("  books open at %s; the plan is made at HH:00:30 from the live ladder" % iso_hour(o))
        return {"hour": iso_hour(o), "markets": len(rows), "programs": None if progs is None else len(progs)}
    by = collections.defaultdict(list)
    for m in rows:
        by[m["series"]].append(m)
    plan = {}
    for s, ms in sorted(by.items()):
        evs = sorted({m["event"] for m in ms if m.get("event")})
        quotes = {}
        for e in evs:
            st, b = call("/markets", {"event_ticker": e, "limit": "200"})
            for x in (b or {}).get("markets") or [] if st == 200 and isinstance(b, dict) else []:
                yb, ya = f(x.get("yes_bid_dollars")), f(x.get("yes_ask_dollars"))
                quotes[x.get("ticker")] = (yb if yb and yb > 0 else None,
                                           (1.0 - ya) if ya is not None and 0 < ya < 1 else None)
        y, why = yhat_of([(m["K"],) + quotes.get(m["ticker"], (None, None)) for m in ms])
        if y is None:
            out("  %s: no y_hat (%s)" % (s, why))
            continue
        ladder = []
        for m in sorted(ms, key=lambda m: m["K"]):
            if BAND_V2W[0] - 1e-9 <= dist_bp(m["K"], y) < BAND_V2[1]:
                st, ob = call("/markets/%s/orderbook" % m["ticker"], {})
                o_ = (ob or {}).get("orderbook_fp") or {} if isinstance(ob, dict) else {}
                ylv = {round(float(p), 4): float(z) for p, z in (o_.get("yes_dollars") or [])}
                nlv = {round(float(p), 4): float(z) for p, z in (o_.get("no_dollars") or [])}
                ladder.append((m["K"], m["ticker"], ylv, nlv))
        c, r = plan_candidates(ladder, y, progs or {}, BAND_V2)
        plan[s] = {"y_hat": y, "v2": c, "refused": r}
        out("  %s y_hat %.4f%%: V2 candidates %s refused %s" % (s, y, [(x["ticker"], x["d"], x["dead"], x["score"])
                                                                   for x in c], r))
    if log is not None:
        log.write("once_plan", hour=iso_hour(o), plan=plan)
    return plan


# ================================================================================================ self-test
class _FakeWS:
    """A plain dict world for the bar / restore tests (the frame-driven tests use RecBook + WS)."""

    def __init__(self):
        self.books, self.q, self.subs, self.up = {}, [], [], True

    def drain(self):
        out, self.q = self.q, []
        return out

    def best(self, tk):
        b = self.books.get(tk)
        return None if b is None else (max(b[0]) if b[0] else None, max(b[1]) if b[1] else None)

    def levels(self, tk):
        b = self.books.get(tk)
        return None if b is None else (dict(b[0]), dict(b[1]))

    def one_c(self, tk):
        b = self.books.get(tk)
        return None if b is None else (b[0].get(PX, 0.0), b[1].get(PX, 0.0))

    def connected(self):
        return self.up

    def subscribe(self, tks):
        self.subs.extend(tks)

    def drop(self, tks):
        pass

    def health(self):
        return {}


def _ladder_world(y=5.105, ks=None, series="KX10YRRATEH", tick="ZZ", stacks=None, safe_extra=None):
    """Snapshots of a ladder whose YES mid crosses 0.5 at y. Tickers are deliberately NOT in Kalshi's format: the
    recorder must use whatever the API returns. stacks {K: (side, size)} = others' 1c dead-side stacks."""
    ks = ks or [round(5.03 + 0.01 * i, 2) for i in range(15)]
    rows, frames = [], []
    for K in ks:
        tk = "%s-%s-T%s" % (series, tick, int(round(K * 100)))
        if K < y - 0.009:
            yes, no = {0.97: 50.0}, {0.01: 0.0}
        elif K > y + 0.009:
            yes, no = {0.01: 0.0}, {0.97: 50.0}
        elif K < y:
            yes, no = {0.59: 40.0}, {0.39: 40.0}
        else:
            yes, no = {0.39: 40.0}, {0.59: 40.0}
        if stacks and K in stacks:
            sd, sz = stacks[K]
            (yes if sd == "yes" else no)[0.01] = sz
        if safe_extra and K in safe_extra:
            sd, p, sz = safe_extra[K]
            (yes if sd == "yes" else no)[p] = sz
        yes = {p: s for p, s in yes.items() if s > 0}
        no = {p: s for p, s in no.items() if s > 0}
        rows.append({"ticker": tk, "series": series, "event": "%s-%s" % (series, tick), "K": K,
                     "strike_type": "greater", "pls": "linear_cent"})
        frames.append((tk, yes, no))
    return rows, frames


def _snap(tk, yes, no, seq):
    return json.dumps({"type": "orderbook_snapshot", "sid": 1, "seq": seq,
                       "msg": {"market_ticker": tk,
                               "yes_dollars_fp": [["%.4f" % p, "%.2f" % s] for p, s in yes.items()],
                               "no_dollars_fp": [["%.4f" % p, "%.2f" % s] for p, s in no.items()]}})


class _Seq:
    def __init__(self):
        self.book, self.trade = 0, 0

    def b(self):
        self.book += 1
        return self.book

    def t(self):
        self.trade += 1
        return self.trade


def _delta(tk, side, p, d, t):
    return lambda sq: json.dumps({"type": "orderbook_delta", "sid": 1, "seq": sq.b(),
                                  "msg": {"market_ticker": tk, "price_dollars": "%.4f" % p, "delta_fp": "%.2f" % d,
                                          "side": side, "ts_ms": int(t * 1000) - 30}})


def _trade(tk, taker, yes_px, n, ts_ms, tid):
    def build(sq):
        msg = {"trade_id": tid, "market_ticker": tk, "yes_price_dollars": "%.4f" % yes_px,
               "no_price_dollars": "%.4f" % (1 - yes_px), "count_fp": "%.2f" % n,
               "taker_side": taker, "ts": ts_ms // 1000, "ts_ms": ts_ms}
        if tid is None:
            msg.pop("trade_id")
        return json.dumps({"type": "trade", "sid": 2, "seq": sq.t(), "msg": msg})
    return build


class _World:
    """A frame-driven hour: RecBook (the live parser) + WS + a sync job runner + a fake REST."""

    def __init__(self, o, ladders, programs=True, prog_reward=100000, log=None, hb=20.0):
        self.o = o
        # the live RATEH socket is never quiet for long (tops changed in every 40-60 s REST poll, 10-15 09Z): a
        # world sends a no-book frame every `hb` s unless told to go silent (hb=None, or `silent` spans)
        self.hb, self.next_hb, self.silent = hb, None, []
        self.snap_off = -SUB_LEAD_S              # the books' first snapshots arrive at open + snap_off
        self.lb = RecBook(key_id="x", key_file="x")
        self.lb.connected.set()
        self.lb.on_frame(json.dumps({"type": "subscribed", "id": 1, "msg": {"channel": "orderbook_delta", "sid": 1}}))
        self.lb.on_frame(json.dumps({"type": "subscribed", "id": 2, "msg": {"channel": "trade", "sid": 2}}))
        self.ws = WS(self.lb)
        self.ws.subscribe = lambda tks: None
        self.ws.drop = lambda tks: None
        self.seq = _Seq()
        self.rows = [r for rows, _ in ladders for r in rows]
        self.frames = [fr for _, frs in ladders for fr in frs]
        self.programs = programs
        self.prog_reward = prog_reward
        self.rest_trades = {}
        self.log = log or Log(None, clock=lambda: self.t)
        self.rec = Recorder(self.log, now=lambda: self.t)
        self.jobs = Jobs(sync=True)
        self.t = o - 130.0
        self.pending = []           # (t, frame builder)
        self.calls = []
        self.n_tid = 0

    def get(self, path, params, auth=False):
        self.calls.append((path, dict(params)))
        if path == "/markets" and "series_ticker" in params:
            c = int(params["max_close_ts"]) - 60
            ms = [{"ticker": r["ticker"], "event_ticker": r["event"], "floor_strike": r["K"],
                   "strike_type": r["strike_type"], "price_level_structure": r["pls"],
                   "open_time": iso(self.o), "close_time": iso(self.o + PERIOD_S).replace(".000Z", "Z"),
                   "status": "initialized"} for r in self.rows if r["series"] == params["series_ticker"]]
            return 200, {"markets": ms if c == int(self.o + PERIOD_S) else [], "cursor": ""}
        if path == "/incentive_programs":
            if self.programs is None:
                return 500, "down"
            ps = [] if not self.programs or params.get("status") != "upcoming" else [
                {"market_ticker": r["ticker"], "period_reward": self.prog_reward, "target_size_fp": "1000.00",
                 "discount_factor_bps": 5000, "start_date": iso(self.o), "end_date": iso(self.o + PERIOD_S),
                 "id": "p-" + r["ticker"]} for r in self.rows]
            return 200, {"incentive_programs": ps + [{"market_ticker": "OTHER-1", "period_reward": 1,
                                                     "target_size_fp": "1", "discount_factor_bps": 1}],
                         "next_cursor": ""}
        if path == "/markets" and "event_ticker" in params:
            return 200, {"markets": [{"ticker": r["ticker"], "result": "no", "expiration_value": "5.1",
                                      "volume_fp": "0", "status": "settled"} for r in self.rows
                                     if r["event"] == params["event_ticker"]]}
        if path == "/markets/trades":
            return 200, {"trades": self.rest_trades.get(params["ticker"], []), "cursor": ""}
        return 404, {}

    def call(self, path, params=None):
        return self.get(path, params or {})

    def at(self, t, build):
        self.pending.append((t, build))

    def delta(self, t, tk, side, d, p=PX):
        self.at(t, _delta(tk, side, p, d, t))

    def trade(self, t, tk, taker, yes_px, n, rest=True, tid=None, noid=False):
        self.n_tid += 1
        tid = tid or "tid-%06d" % self.n_tid
        self.at(t, _trade(tk, taker, yes_px, n, int(t * 1000) - 40, None if noid else tid))
        if rest:
            self.rest_trades.setdefault(tk, []).append(
                {"trade_id": tid, "created_time": iso(t - 0.04), "count_fp": "%.2f" % n,
                 "yes_price_dollars": "%.4f" % yes_px, "taker_side": taker})
        return tid

    def run(self, until, dt=1.0):
        snapped = False
        while self.t < until:
            if not snapped and self.t >= self.o + self.snap_off:
                for tk, yes, no in self.frames:
                    self.lb.on_frame(_snap(tk, yes, no, self.seq.b()), int(self.t * 1000))
                snapped = True
            due = sorted([x for x in self.pending if x[0] <= self.t], key=lambda x: x[0])
            self.pending = [x for x in self.pending if x[0] > self.t]
            for tt, build in due:
                self.lb.on_frame(build(self.seq), int(round(tt * 1000)))
            if snapped and self.hb:
                if self.next_hb is None:
                    self.next_hb = self.t
                if self.t >= self.next_hb:
                    if not any(a <= self.t < b for a, b in self.silent):
                        self.lb.on_frame('{"type": "ok"}', int(round(self.t * 1000)))
                    self.next_hb += self.hb
            self.rec.step(self.t, self.ws, self.jobs, self.call)
            nxt = min([x[0] for x in self.pending if x[0] > self.t] + [self.t + dt])
            self.t = nxt if nxt > self.t else self.t + dt
        return self.rec

    def evs(self, name):
        return [r for r in self.log.rows if r["ev"] == name]


def _tk(series, K, tick="ZZ"):
    return "%s-%s-T%s" % (series, tick, int(round(K * 100)))


def selftest(verbose=True):
    """Every check below plants an answer and fails on a miss or on a find in an empty world. Its scratch files live in
    results/ratehreward-paper.selftest-<pid>/ (never %TEMP%) and are removed however it ends."""
    tmpd = os.path.join(RESULTS, "ratehreward-paper.selftest-%d" % os.getpid())
    os.makedirs(tmpd, exist_ok=True)
    try:
        return _selftest(verbose, tmpd)
    finally:
        try:
            for fn in os.listdir(tmpd):
                os.remove(os.path.join(tmpd, fn))
            os.rmdir(tmpd)
        except OSError:
            pass


def _selftest(verbose, tmpd):
    say = print if verbose else (lambda *a, **k: None)
    checks = 0
    prog = {"reward": 10.0, "target": 1000.0, "df": 0.5, "start": 0.0, "end": PERIOD_S}
    S10, S30 = "KX10YRRATEH", "KX30YRRATEH"
    o = datetime(2026, 10, 20, 14, 0, tzinfo=UTC).timestamp()       # Tue 10-20 10:00 ET, not a blackout hour
    assert blackout_of(o) is None

    # 1. the walk: alone -> 1.0; 118 at 99c on the safe side -> 1000/1118 (new rule), 0 (old rule); 200 at 89c -> ~0
    assert abs(walk({}, 1000, 0.5, ours=1000)["share"] - 1.0) < 1e-12
    w1 = walk({0.99: 118.0}, 1000, 0.5, ours=1000)
    assert w1["q"] and abs(w1["share"] - 1000 / 1118) < 1e-12 and w1["ref"] == 0.01, w1
    assert walk({0.99: 118.0}, 1000, 0.5, ours=1000, old_rule=True)["q"] is False
    w89 = walk({0.89: 200.0}, 1000, 0.5, ours=1000)
    assert w89["q"] and w89["ref"] == 0.89 and w89["share"] < 1e-20, w89
    for lv in ({0.98: 118.0}, {0.50: 30.0, 0.30: 10.0}, {}, {0.89: 200.0}):
        a, b = walk(lv, 1000, 0.5, ours=1000), walk(lv, 1000, 0.5, ours=1000, old_rule=True)
        assert a == b, (lv, a, b)
    assert walk({0.01: 500.0}, 1000, 0.5)["q"] is False
    say("  1 walk: alone 1.0; 118@99c -> 1000/1118 new, unqualified old; 200@89c -> %.1e; rules differ only at 99c ok"
        % w89["share"])
    checks += 1

    # 2. credit: alone both sides for exactly 1,770 counted s -> $5.00; $0.99 floors to 0; one side 999 -> 0
    ok, sc, *_ = pair_score({}, {}, "yes", prog)
    assert ok and abs(sc - 2.0) < 1e-12
    assert abs(credit(10.0, PERIOD_S, sc * 1770) - 5.0) < 1e-9
    assert floored(0.99) == 0.0 and floored(1.0) == 1.0
    assert walk({}, 1000, 0.5, ours=999)["q"] is False
    assert pair_score({}, {}, "yes", dict(prog, target=1000.5))[0] is False      # the safe side holds 1,000 only
    g2 = Ghost("T", S10, 5.17, "yes", 6.5, 0.0, prog, 3000.0, 0.0, ["V2"])
    for i in range(1770):
        g2.inc[i] = 2.0
    assert abs(g2.credit_until(1770.0) - 5.0) < 1e-9
    assert abs(g2.credit_until(885.5) - (885.5 * 2.0 * 10.0 / 7080.0)) < 1e-9
    say("  2 credit: 1,770 counted s alone = $5.00; $0.99 floors to $0; a side at 999 never counts ok")
    checks += 1

    # 3. y_hat
    y, why = yhat_of([(5.09, 0.75, 0.15), (5.10, 0.59, 0.39), (5.11, 0.39, 0.59), (5.12, 0.1, 0.8)])
    assert abs(y - 5.105) < 1e-9 and why is None, (y, why)
    assert yhat_of([(5.09, 0.75, 0.15), (5.10, 0.70, 0.2)]) == (None, "no_crossing")
    assert yhat_of([(5.09, 0.75, 0.15), (5.10, None, 0.2)]) == (None, "no_crossing")
    assert yhat_of([(1, .9, .05), (2, .3, .6), (3, .7, .2), (4, .1, .8)])[1] == "ladder_nonmonotone"
    say("  3 y_hat: 0.6/0.4 at 5.10/5.11 -> 5.105; all above 0.5 -> None; non-monotone -> None ok")
    checks += 1

    # 4. candidates: y_hat 5.105, strikes 5.03..5.17 -> exactly {5.03 NO 7.5, 5.04 NO 6.5, 5.17 YES 6.5}
    rows, frames = _ladder_world()
    lad = [(r["K"], r["ticker"], fr[1], fr[2]) for r, fr in zip(rows, frames)]
    progs = {r["ticker"]: prog for r in rows}
    c, r = plan_candidates(lad, 5.105, progs, BAND_V2)
    got = sorted((x["K"], x["dead"], x["d"]) for x in c)
    assert got == [(5.03, "no", 7.5), (5.04, "no", 6.5), (5.17, "yes", 6.5)], got
    assert not r
    lad2 = [(K, tk, ylv, ({0.99: 5.0} if K == 5.17 else nlv)) for K, tk, ylv, nlv in lad]
    lad2 = [(K, tk, ({**ylv, 0.89: 200.0} if K == 5.04 else ylv), nlv) for K, tk, ylv, nlv in lad2]
    c2, r2 = plan_candidates(lad2, 5.105, progs, BAND_V2)
    assert [x["K"] for x in c2] == [5.03] and r2 == {_tk(S10, 5.17): "would_cross",
                                                     _tk(S10, 5.04): "safe_share_zero"}, (c2, r2)
    c3, r3 = plan_candidates(lad, 5.105, {}, BAND_V2)
    assert not c3 and set(r3.values()) == {"no_program"}
    c4, _ = plan_candidates(lad, 5.105, progs, BAND_V2W)
    assert sorted(x["K"] for x in c4) == [5.03, 5.04, 5.05, 5.16, 5.17], c4

    def safe_ref(p_, sz_):     # others' NO bid on 5.17's SAFE side (dead YES): refused only if our share would be ~0
        ladx = [(K, tk, ylv, ({**nlv, p_: sz_} if K == 5.17 else nlv)) for K, tk, ylv, nlv in lad]
        cx, rx_ = plan_candidates(ladx, 5.105, progs, BAND_V2)
        return rx_.get(_tk(S10, 5.17)), [x["K"] for x in cx]
    assert safe_ref(0.02, 200.0) == (None, [5.03, 5.04, 5.17]), safe_ref(0.02, 200.0)      # share 0.67 -> posted
    assert safe_ref(0.09, 200.0) == (None, [5.03, 5.04, 5.17])                             # 0.015 -> posted
    assert safe_ref(0.10, 200.0) == ("safe_share_zero", [5.03, 5.04])                      # 0.0078 -> refused
    assert safe_ref(0.89, 200.0) == ("safe_share_zero", [5.03, 5.04])
    assert safe_ref(0.89, 149.0) == (None, [5.03, 5.04, 5.17])                             # 50 + 149 < 200
    say("  4 candidates: {5.03 NO 7.5, 5.04 NO 6.5, 5.17 YES 6.5}; NO 0.99 -> would_cross; 200@89c safe -> "
        "safe_share_zero; 200@2c / 9c posted, 10c refused (share < 0.01); no program -> refused; V2w adds 5.05/5.16 ok")
    checks += 1

    # 5. episodes from synthetic WS frames (through livebook's own parser): SWEPT / PULLED / PULLED_AFTER_SIBLING
    w = _World(o, [_ladder_world(series=S10)])
    A, B, C, D = _tk(S10, 5.17), _tk(S10, 5.16), _tk(S10, 5.03), _tk(S10, 5.04)
    tA0, tB0, tC0, tsib = o + 600.25, o + 200.5, o + 800.75, o + 900.0
    w.delta(tA0, A, "yes", 1600)
    w.trade(tA0 + 120.0, A, "no", 0.01, 1600)
    w.delta(tA0 + 120.2, A, "yes", -1600)
    w.delta(tB0, B, "yes", 800)
    w.delta(tB0 + 50.0, B, "yes", -800)
    w.delta(tC0, C, "no", 900)
    w.delta(tsib - 0.5, D, "no", 300)
    w.trade(tsib, D, "yes", 0.99, 300)
    w.delta(tsib + 60.0, C, "no", -900)
    w.run(o + PERIOD_S + 700)
    eps = {e["ticker"]: e for e in w.evs("episode")}
    assert len(eps) == 3, eps
    assert eps[A]["cause"] == "SWEPT" and abs(eps[A]["s_left"] - (PERIOD_S - 720.45)) < 0.06, eps[A]
    assert eps[B]["cause"] == "PULLED" and eps[C]["cause"] == "PULLED_AFTER_SIBLING", (eps[B], eps[C])
    summ = w.evs("hour_summary")
    assert len(summ) == 1, [r_["ev"] for r_ in w.log.rows][-30:]
    s5 = summ[0]
    expo = s5["exposure_s"]
    tot = sum(expo.values())
    planted = 120.2 + 50.0 + (tsib + 60.0 - tC0)
    assert abs(tot - planted) < 1e-6, (tot, planted, expo)
    n_sw = sum(v.get("SWEPT", 0) for v in s5["episodes"].values())
    n_pas = sum(v.get("PULLED_AFTER_SIBLING", 0) for v in s5["episodes"].values())
    lam_lo, lam_hi = n_sw / tot * 3600, (n_sw + n_pas) / tot * 3600
    assert n_sw == 1 and n_pas == 1
    assert abs(lam_lo - 1 / planted * 3600) < 1e-9 and abs(lam_hi - 2 / planted * 3600) < 1e-9
    assert s5["audit"] == "clean" and s5["observable"] and s5["sweeper"] and s5["ws_blind_max_s"] == 0, s5
    assert abs(s5["t1_from_open"] - 720.25) < 1e-6 and s5["trigger"]["tk"] == A
    say("  5 episodes from frames: SWEPT at s_left %.2f, PULLED, PULLED_AFTER_SIBLING; exposure %.2f s; "
        "lambda_lo %.4f/h lambda_hi %.4f/h exact ok" % (eps[A]["s_left"], tot, lam_lo, lam_hi))
    checks += 1

    # 6. V2 cancel (the planted ladder where a sweep happens and the cancel must fire). Ghosts: 10Y 5.03 7.5,
    #    5.04 6.5, 5.17 6.5, 5.18 7.5; 30Y 5.47 6.5, 5.48 7.5. First sweep at t on 10Y 5.19 (8.5 bp -- farther than
    #    every ghost + 0.5): it dominates none, so the nearest ghost is assumed hit and everything else is cancelled
    #    at t + 0.3 s. A real sweep at t + 0.1 s on 30Y 5.48 (7.5 bp) sweeps every ghost at >= 7.0 bp; at t + 2 s it
    #    is too late. A later 8.5 bp sweep (V1 only) never sweeps a nearer ghost.
    def cancel_world(dt_c):
        la = _ladder_world(series=S10, ks=[round(5.03 + 0.01 * i, 2) for i in range(17)])
        lc = _ladder_world(y=5.405, series=S30, ks=[round(5.39 + 0.01 * i, 2) for i in range(10)])
        ww = _World(o, [la, lc])
        t = o + 1200.0
        far = _tk(S10, 5.19)
        ww.delta(t - 5, far, "yes", 600)
        ww.trade(t, far, "no", 0.01, 600)
        ww.delta(t + 0.05, far, "yes", -600)
        ww.trade(t + dt_c, _tk(S30, 5.48), "no", 0.01, 150)
        ww.trade(t + 100.0, far, "no", 0.01, 400)
        ww.run(o + PERIOD_S + 700)
        return ww
    w6 = cancel_world(0.1)
    s6 = w6.evs("hour_summary")[0]
    v2 = s6["var"]["V2"]
    causes = {g_["tk"]: g_["cause"] for g_ in v2["ghosts"]}
    assert len(causes) == 6, causes
    cz = w6.evs("cancel")
    assert len(cz) == 1 and abs(parse_ts(cz[0]["t_cancel"]) - (o + 1200.3)) < 0.002 and cz[0]["trigger"] == _tk(S10, 5.19)
    near = v2["assumed"]
    assert near == _tk(S10, 5.04) and causes[near] == "swept", (near, causes)
    swept_real = {tk for tk, c_ in causes.items() if c_ == "swept" and tk != near}
    saved = {tk for tk, c_ in causes.items() if c_ == "cancel"}
    assert swept_real == {_tk(S10, 5.03), _tk(S10, 5.18), _tk(S30, 5.48)}, swept_real
    assert saved == {_tk(S10, 5.17), _tk(S30, 5.47)}, saved
    assert v2["g1"] == 6 and v2["n_win"] == 4 and v2["n_pre"] == 0 and v2["cost_det"] == 44.0, v2
    v1 = s6["var"]["V1"]
    assert v1["n_swept"] == 4 and v1["n"] == 6, v1
    w6b = cancel_world(2.0)
    v2b = w6b.evs("hour_summary")[0]["var"]["V2"]
    assert v2b["n_win"] == 1 and [g_["tk"] for g_ in v2b["ghosts"] if g_["cause"] == "swept"] == [near], v2b
    assert v2b["cost_det"] == 11.0 and w6b.evs("hour_summary")[0]["var"]["V1"]["n_swept"] == 4
    wn = _World(o, [_ladder_world(series=S10)])
    wn.trade(o + 1000.0, _tk(S10, 5.14), "no", 0.01, 150)        # 3.5 bp: dead-side 1c, >= 100 lots, NOT far
    wn.run(o + PERIOD_S + 700)
    sn = wn.evs("hour_summary")[0]
    assert not wn.evs("cancel") and not sn["sweeper"] and sn["observable"] and sn["n_sweeps"] == 1, sn
    assert sn["var"]["V2"]["n_pre"] == 3 and sn["var"]["V2"]["cost_det"] == 33.0, sn["var"]["V2"]
    assert _hour_cost_credit(sn, "V2", 0.5, 0.5, 100.0)[2] == 33.0
    say("  6 V2 cancel: the first sweep fires the cancel at +0.300 s; nearest ghost assumed hit; a 7.5 bp sweep at "
        "+0.1 s takes the 3 ghosts >= 7.0 bp, 2 saved ($44); at +2 s only the assumed one is lost ($11); a farther "
        "sweep never takes a nearer ghost; a 3.5 bp sweep fires no cancel but takes all 3 ($33, observed, not imputed) ok")
    checks += 1

    # 7. NULL worlds
    #   (a) books + others' far stacks, no trades -> 0 sweeps, cost 0, credit > 0 -> never KILL on cost
    wa = _World(o, [_ladder_world(series=S10, stacks={5.16: ("yes", 700.0)})])
    wa.trade(o + 400.0, _tk(S10, 5.10), "yes", 0.55, 400)        # an ATM print, not 1c
    wa.trade(o + 500.0, _tk(S10, 5.17), "yes", 0.99, 300)        # a SAFE-side fill on a dead-YES strike
    wa.trade(o + 600.0, _tk(S10, 5.16), "no", 0.02, 600)         # 2c, not the 1c stack
    wa.trade(o + 700.0, _tk(S10, 5.16), "no", 0.01, 99)          # a 1c print below the 100-lot trigger
    wa.run(o + PERIOD_S + 700)
    sa = wa.evs("hour_summary")[0]
    va = sa["var"]["V2"]
    assert va["n"] == 3 and sa["n_sweeps"] == 0 and va["cost_det"] == 0 and va["credit_x09"] > 0, (va, sa["n_sweeps"])
    assert sa["safe_prints_real"] == 1 and not wa.evs("cancel") and not wa.evs("vfill")
    assert sa["observable"] and not sa["sweeper"] and sa["audit"] == "clean"
    ea = evaluate_bar(_clone(sa, 3, 10))
    assert not ea["kill_checks"]["net_at_b_point<=0"] and not ea["kill_checks"]["elow_net<=0"], ea["kill_checks"]
    assert ea["verdict"] != "KILL", ea["verdict"]
    #   (b) every stack swept 47 s after the open -> net < 0 -> KILL
    stacks = {5.15: ("yes", 800.0), 5.16: ("yes", 900.0)}
    wb = _World(o, [_ladder_world(series=S10, stacks=stacks)])
    for K, (sd, sz) in stacks.items():
        wb.trade(o + 47.0, _tk(S10, K), "no", 0.01, sz)
        wb.delta(o + 47.1, _tk(S10, K), "yes", -sz)
    wb.run(o + PERIOD_S + 700)
    sb = wb.evs("hour_summary")[0]
    vb = sb["var"]["V2"]
    assert sb["sweeper"] and abs(sb["t1_from_open"] - 47.0) < 1e-6 and vb["n"] == 3 and vb["net_det"] < 0, vb
    assert vb["n_win"] == 3 and vb["credit_x09"] == 0.0, vb
    eb = evaluate_bar(_clone(sb, 3, 10))
    assert eb["verdict"] == "KILL" and eb["kill_checks"]["net_at_b_point<=0"], eb
    #   (c) no programs listed -> no posts, hour refused, $0; programs unreadable -> refused too
    wc = _World(o, [_ladder_world(series=S10)], programs=False)
    wc.run(o + PERIOD_S + 700)
    sc_ = wc.evs("hour_summary")[0]
    assert all(sc_["var"][v]["n"] == 0 for v in VARIANTS) and not wc.evs("post"), sc_["var"]
    assert wc.evs("hour_plan")[0]["hour_refused"] == "no_program_listed"
    assert sum(sc_["var"][v]["credit_x09"] + sc_["var"][v]["cost_det"] for v in VARIANTS) == 0
    wd = _World(o, [_ladder_world(series=S10)], programs=None)
    wd.run(o + PERIOD_S + 700)
    assert wd.evs("hour_plan")[0]["hour_refused"] == "programs_unreadable" and not wd.evs("post")
    say("  7 NULL: (a) 4 decoy prints, no sweep -> 0 sweeps, cost $0, credit $%.2f/hour, verdict %s (not KILL); (b) all swept at "
        "+47 s -> net $%.2f/hour -> KILL; (c) no program -> no post, $0, hour refused; unreadable -> refused ok"
        % (va["credit_x09"], ea["verdict"], vb["net_det"]))
    checks += 1

    # 8. the bar evaluator: one hour of 12 strike-hours is ONE cluster; planted nets -> PASS / KILL / EXTEND
    one = _synth_summary("2026-10-20", 14, n=12, credit_each=7.0, observable=True, sweeper=False)
    e1 = evaluate_bar([one])
    assert e1["clusters"] == 1 and e1["v2_b_point"]["strike_hours"] == 12 and e1["v2_b_point"]["hours_with_posts"] == 1
    days5 = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
    good = []
    for d in days5:
        for hh in range(8, 20):
            sw_ = (hh % 5 == 0)
            good.append(_synth_summary(d, hh, n=4, credit_each=7.0, observable=True, sweeper=sw_, g1=4 if sw_ else 0,
                                       at_risk=8 if sw_ else 0))
    ep = evaluate_bar(good)
    assert ep["verdict"] == "EXTEND" and not ep["pass_checks"]["strike_hours_per_weekday>=60"], ep["pass_checks"]
    assert all(v_ for k_, v_ in ep["pass_checks"].items() if k_ != "strike_hours_per_weekday>=60"), ep["pass_checks"]
    good2 = [_synth_summary(s_["day"], int(s_["hour"][11:13]), n=8, credit_each=7.0, observable=True,
                            sweeper=s_["sweeper"], g1=8 if s_["sweeper"] else 0, at_risk=8 if s_["sweeper"] else 0)
             for s_ in good]
    ep2 = evaluate_bar(good2)
    assert ep2["verdict"] == "PASS", (ep2["pass_checks"], ep2["kill_checks"], ep2["v2_b_upper"])
    bad = [_synth_summary(d, hh, n=6, credit_each=7.0, observable=True, sweeper=True, g1=6, n_win=6, at_risk=4,
                          hits=4) for d in days5[:3] for hh in range(8, 19)]
    ek = evaluate_bar(bad)
    assert ek["verdict"] == "KILL" and ek["kill_checks"]["sweeper_share>=0.80"], ek["kill_checks"]
    mid = [_synth_summary(d, hh, n=6, credit_each=4.0, observable=True, sweeper=(hh % 3 == 0),
                          g1=6 if hh % 3 == 0 else 0, at_risk=5 if hh % 3 == 0 else 0)
           for d in days5[:3] for hh in range(8, 19)]
    em = evaluate_bar(mid)
    assert em["verdict"] == "EXTEND", (em["pass_checks"], em["kill_checks"])
    assert evaluate_bar(mid[:20])["verdict"] == "TOO_EARLY"
    assert evaluate_bar(mid, {"2026-10-19": True, "2026-10-20": False, "2026-10-21": False})["verdict"] == "KILL"
    assert abs(cp_upper(0, 20) - (1 - 0.05 ** (1 / 20))) < 1e-6 and cp_upper(0, 0) == 1.0
    # an unobservable hour is imputed: p = 1/2, the sweep at post + the median ttfs -> half the credit after it lost
    un = _synth_summary("2026-10-21", 9, n=1, credit_each=0.0, observable=False, sweeper=False)
    un["var"]["V2"]["ghosts"] = [{"tk": "G", "raw": 8.0, "end": 2940.0, "cause": "exit"}]
    un["ghosts"] = {"G": {"t_post": 30.0, "cum_min": [round(8.0 * min(60 * i, 2910) / 2910, 5) for i in range(50)]}}
    n_, cr_, co_, im_ = _hour_cost_credit(un, "V2", 0.0, 0.5, 1455.0)
    assert im_ is True and n_ == 1 and abs(co_ - 5.5) < 1e-9 and abs(cr_ - (0.5 * 7.2 + 0.5 * 3.6)) < 0.01, (cr_, co_)
    say("  8 bar: 12 strike-hours in one hour = 1 cluster; planted nets -> PASS / KILL (sweeper 100%%) / EXTEND / "
        "TOO_EARLY; 2 unlisted weekdays -> KILL; an unobservable hour is imputed; CP upper 0/20 = %.4f ok"
        % cp_upper(0, 20))
    checks += 1

    # 9. audit: a WS trade missing from REST -> tape_gap -> excluded from the bar
    wg = _World(o, [_ladder_world(series=S10)])
    wg.trade(o + 500.0, _tk(S10, 5.10), "yes", 0.55, 10, rest=False)
    wg.run(o + PERIOD_S + 700)
    sg = wg.evs("hour_summary")[0]
    assert sg["audit"] == "tape_gap" and wg.evs("audit")[0]["n_missing_in_rest"] == 1
    assert evaluate_bar([sg])["population_hours"] == 0 and evaluate_bar([sg])["excluded"]["tape_gap"] == 1
    say("  9 audit: WS trade absent from REST -> tape_gap, excluded ok")
    checks += 1

    # 10. time: et_date / ET labels across 2026-11-01 06:00Z; blackout hours from ET; tickers from the API only
    t_dst = datetime(2026, 11, 1, 6, 0, tzinfo=UTC).timestamp()
    assert et_date(t_dst - 1) == "2026-11-01" and et_offset_h(t_dst - 1) == -4 and et_offset_h(t_dst) == -5
    assert et_date(datetime(2026, 11, 2, 4, 30, tzinfo=UTC).timestamp()) == "2026-11-01"
    assert et_date(datetime(2026, 10, 27, 3, 30, tzinfo=UTC).timestamp()) == "2026-10-26"
    assert hour_open(et_to_utc("2026-10-29", "08:30")) == datetime(2026, 10, 29, 12, tzinfo=UTC).timestamp()
    assert hour_open(et_to_utc("2026-11-06", "08:30")) == datetime(2026, 11, 6, 13, tzinfo=UTC).timestamp()
    assert blackout_of(datetime(2026, 10, 21, 17, tzinfo=UTC).timestamp()).startswith("blackout: 20Y")
    assert blackout_of(datetime(2026, 10, 28, 18, tzinfo=UTC).timestamp()).startswith("blackout: FOMC")
    assert blackout_of(datetime(2026, 10, 28, 19, tzinfo=UTC).timestamp()).startswith("blackout: FOMC")
    assert blackout_of(datetime(2026, 10, 28, 17, tzinfo=UTC).timestamp()) is None
    assert blackout_of(datetime(2026, 11, 10, 18, tzinfo=UTC).timestamp()).startswith("blackout: 10Y")
    assert blackout_of(datetime(2026, 11, 10, 13, tzinfo=UTC).timestamp()).startswith("blackout: CPI")
    assert blackout_of(datetime(2026, 12, 1, 15, tzinfo=UTC).timestamp()) == "blackout_list_not_covering"
    assert all(datetime.fromtimestamp(et_to_utc(d, hm), UTC).weekday() < 5 for d, hm, _ in BLACKOUT_ET)
    assert et_label(datetime(2026, 10, 21, 21, 30, tzinfo=UTC).timestamp()) == "Wed 10-21 05:30 PM ET"
    assert et_label(datetime(2026, 10, 23, 21, 30, tzinfo=UTC).timestamp()) == "Fri 10-23 05:30 PM ET"
    assert w.evs("post") and all("-ZZ-" in r_["ticker"] for r_ in w.evs("post"))
    ob = datetime(2026, 10, 21, 17, 0, tzinfo=UTC).timestamp()      # Wed 10-21 13:00 ET: the 20Y auction result
    wbk = _World(ob, [_ladder_world(series=S10)])
    wbk.run(ob + PERIOD_S + 700)
    sbk = wbk.evs("hour_summary")[0]
    assert wbk.evs("hour_plan")[0]["hour_refused"].startswith("blackout: 20Y") and not wbk.evs("post"), sbk["blackout"]
    assert evaluate_bar([sbk])["population_hours"] == 0 and evaluate_bar([sbk])["excluded"]["blackout"] == 1
    src = open(__file__, encoding="utf-8").read()
    for pat in ("%y" + "%b" + "%d", "%d" + "%b" + "%y", "%y" + "%b"):
        assert pat not in src, pat
    say("  10 time: EDT->EST at 2026-11-01 06:00Z; 8:30 ET = 12Z hour (EDT) / 13Z (EST); FOMC 18Z+19Z; a blackout "
        "hour posts nothing and is excluded; list expiry refuses; tickers used exactly as the API gave them ok")
    checks += 1

    # 11. restore: a log cut mid-hour -> ghosts, budget, day totals rebuilt; no double post; the stop file exits
    lp = os.path.join(tmpd, "log.jsonl")
    w11 = _World(o, [_ladder_world(series=S10)])
    w11.run(o + 300)
    posts = w11.evs("post")
    assert len(posts) == 5 and sum(1 for p_ in posts if "V2" in p_["variants"]) == 3, posts
    prior = {"t": iso(o - 7200), "ev": "hour_outcome", "hour": iso_hour(o - 7200), "open": o - 7200, "day": et_date(o),
             "sweeper": True, "var": {"V2": {"n": 2, "cost_det": 22.0, "credit_x09": 3.0, "net_det": -19.0}}}
    with open(lp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(prior) + "\n")
        for r_ in w11.log.rows:
            if r_["ev"] in ("hour_plan", "post", "discover", "programs"):
                fh.write(json.dumps(r_) + "\n")
        fh.write('{"t": "cut mid-li')
    w12 = _World(o, [_ladder_world(series=S10)])
    w12.t = o + 600.0
    info = w12.rec.restore(lp)
    assert info["posts"] == 5 and info["outcomes"] == 1, info
    assert abs(w12.rec.day_loss("V2", et_date(o)) - 22.0) < 1e-9
    room = w12.rec.budget_room_fn(et_date(o))
    assert room("V2", 3) and not room("V2", 4)            # 22 + 33 + 11 = 66 <= 66; 22 + 44 + 11 = 77 > 66
    assert room("V1", 5) and not room("V1", 6)            # a fresh variant: at most 6 pairs at risk
    w12.run(o + 700)
    assert not w12.evs("post") and w12.evs("restored_hour"), [r_["ev"] for r_ in w12.log.rows]
    h12 = w12.rec.hours[o]
    assert len(h12.ghosts) == 5 and h12.partial and h12.restarted and len(h12.var["V2"]["posted"]) == 3
    assert all(g_.next_i >= 569 for g_ in h12.ghosts.values())        # the down seconds earn nothing
    stop = os.path.join(tmpd, "x.stop")
    open(stop, "w").close()
    lg = Log(None)
    why = loop(Recorder(lg), _FakeWS(), Jobs(sync=True), lambda p_, q_=None: (200, {}), time.time, lambda s_: None,
               stop, time.time() + 60)
    assert why == "stop_file" and lg.rows[-1]["ev"] == "stop"
    os.remove(stop)
    os.remove(lp)
    say("  11 restore: cut log -> 5 ghosts rebuilt (3 V2), day loss $22 -> room for 3 more not 4, no re-plan / double "
        "post; stop file exits ok")
    checks += 1

    # 12. PAPER ONLY: no order endpoint, no non-GET method, no request body; no replay / pinsim / pindata import
    assert ("portfolio/" + "orders") not in src and ("portfolio/" + "events") not in src
    assert ("PO" + "ST") not in src and ("DEL" + "ETE") not in src and ("PU" + "T\"") not in src
    assert ("meth" + "od=" + chr(34)) not in src and ("meth" + "od=" + chr(39)) not in src
    assert ("urlopen(req, " + "da" + "ta") not in src and ("da" + "ta=" + "body") not in src
    for ln in src.splitlines():
        s_ = ln.strip()
        assert not (s_.startswith(("import ", "from ")) and any(x in s_ for x in ("replay", "pinsim", "pindata"))), s_
    imports = sorted({ln.strip().split()[1].split(".")[0] for ln in src.splitlines()
                      if ln.startswith(("import ", "from "))})
    assert set(imports) <= {"argparse", "collections", "hashlib", "json", "math", "os", "queue", "sys", "threading",
                            "time", "array", "datetime", "livebook"}, imports
    calls_ = {p_ for p_, _ in w.calls}
    assert calls_ <= {"/markets", "/incentive_programs", "/markets/trades"}, calls_
    say("  12 paper only: GET helpers only, no order path / non-GET / body in the source; imports %s ok"
        % ",".join(imports))
    checks += 1

    # 13. --history estimator on a planted settled day, and --once on a planted ladder (REST glue)
    d0 = datetime(2026, 10, 16, tzinfo=UTC).timestamp()
    c1, c2 = d0 + 15 * 3600 + 3540, d0 + 16 * 3600 + 3540

    def hget(path, q):
        if path == "/markets":
            if q.get("series_ticker") != S10 or q.get("status"):
                return 200, {"markets": [], "cursor": ""}
            mk_ = [{"ticker": "H-A-T510", "floor_strike": 5.10, "expiration_value": "5.10", "close_time": iso(c1),
                    "open_time": iso(c1 - 3540), "volume_fp": "0"},
                   {"ticker": "H-B-T517", "floor_strike": 5.17, "expiration_value": "5.11", "close_time": iso(c2),
                    "open_time": iso(c2 - 3540), "volume_fp": "900"},
                   {"ticker": "H-B-T513", "floor_strike": 5.13, "expiration_value": "5.11", "close_time": iso(c2),
                    "open_time": iso(c2 - 3540), "volume_fp": "0"}]
            return 200, {"markets": mk_, "cursor": ""}
        if path.endswith("/candlesticks"):
            cs_ = [{"end_period_ts": int(c2 - 3540 + 60 * (i + 1)),
                    "yes_bid": {"close_dollars": "0.0100" if i < 30 else "0.0000"},
                    "yes_ask": {"close_dollars": "0.0300"}} for i in range(59)]
            return 200, {"candlesticks": cs_}
        if path == "/markets/trades":
            return 200, {"trades": [{"created_time": iso(c2 - 3000), "taker_side": "no", "yes_price_dollars": "0.0100",
                                     "count_fp": "400"},
                                    {"created_time": iso(c2 - 2995), "taker_side": "no", "yes_price_dollars": "0.0100",
                                     "count_fp": "200"},
                                    {"created_time": iso(c2 - 100), "taker_side": "no", "yes_price_dollars": "0.0100",
                                     "count_fp": "100"}], "cursor": ""}
        return 404, {}
    hres = history("2026-10-16", lambda p_, q_=None: hget(p_, q_ or {}), out=lambda *a_: None)
    sf = hres["stayed_far"]
    assert sf["sweeps_ge500"] == 1 and abs(sf["stack_hours"] - 0.5) < 1e-9 and sf["hours_swept"] == ["16:59Z"], sf
    assert hres["gate"] is False and "into_play" not in hres
    w13 = _World(o, [_ladder_world(series=S10)])
    pl = once(w13.call, o - 20, out=lambda *a_: None)
    assert pl == {"hour": iso_hour(o), "markets": 15, "programs": 15}, pl
    say("  13 history: planted day -> 1 sweep >= 500 over 0.50 stack-hours, gate reads FAIL for it; once plans "
        "the next hour from the API ok")
    checks += 1
    # 14. THE FIRST SWEEP TAKES ONE GHOST under the cancel variants (6.2 "the first sweep of each sweeper hour
    #     hitting one ghost", 4.6; review fix 1). Ghosts V2: 10Y 5.03 7.5 / 5.04 6.5 / 5.17 6.5 / 5.18 7.5, 30Y 5.47
    #     6.5 / 5.48 7.5. (a) first far sweep on 10Y 5.16 (5.5 bp, no V2 ghost there): V2 loses ONE (the nearest,
    #     assumed) = $11 and cancels 5; V1 (dominance) loses all 6 = $66; V2w has a ghost ON 5.16 and loses exactly it.
    #     (b) first sweep on 5.17 (a V2 ghost's own market): V2 loses exactly 5.17, nothing assumed.
    def first_sweep_world(K):
        la = _ladder_world(series=S10, ks=[round(5.03 + 0.01 * i, 2) for i in range(17)])
        lc = _ladder_world(y=5.405, series=S30, ks=[round(5.39 + 0.01 * i, 2) for i in range(10)])
        ww = _World(o, [la, lc])
        t = o + 1200.0
        tk = _tk(S10, K)
        ww.delta(t - 5, tk, "yes", 600)
        ww.trade(t, tk, "no", 0.01, 600)
        ww.delta(t + 0.05, tk, "yes", -600)
        ww.run(o + PERIOD_S + 700)
        return ww.evs("hour_summary")[0]

    def swept_of(x):
        return sorted(g_["tk"] for g_ in x["ghosts"] if g_["cause"] == "swept")
    s14 = first_sweep_world(5.16)
    v2, v1, v2w = s14["var"]["V2"], s14["var"]["V1"], s14["var"]["V2w"]
    assert s14["trigger"]["d"] == 5.5 and v2["n"] == 6 and v2["g1"] == 6 and v2["n_win"] == 1 and v2["n_pre"] == 0, v2
    assert swept_of(v2) == [_tk(S10, 5.04)] and v2["assumed"] == _tk(S10, 5.04) and v2["cost_det"] == 11.0, \
        (swept_of(v2), v2["cost_det"])
    assert sum(1 for g_ in v2["ghosts"] if g_["cause"] == "cancel") == 5
    assert v1["n_swept"] == 6 and v1["cost_det"] == 66.0, (v1["n_swept"], v1["cost_det"])
    assert swept_of(v2w) == [_tk(S10, 5.16)] and v2w["assumed"] is None and v2w["cost_det"] == 11.0, swept_of(v2w)
    assert _hour_cost_credit(s14, "V2", 0.0, 0.5, 1700.0)[2] == 11.0
    assert abs(_hour_cost_credit(s14, "V2", 0.5, 0.5, 1700.0)[2] - 38.5) < 1e-9       # 11 x (1 + 0.5 x 5)
    assert abs(_hour_cost_credit(s14, "V2", 1.0, 0.5, 1700.0)[2] - 66.0) < 1e-9       # the bound at 1 = V1
    s14b = first_sweep_world(5.17)
    v2b = s14b["var"]["V2"]
    assert swept_of(v2b) == [_tk(S10, 5.17)] and v2b["assumed"] is None and v2b["n_win"] == 1, (swept_of(v2b), v2b)
    assert v2b["cost_det"] == 11.0 and s14b["var"]["V1"]["n_swept"] == 6
    say("  14 first sweep: 5.5 bp on a ghost-free strike -> V2 loses 1 assumed ghost ($11, 5 cancelled), V1 all 6 "
        "($66), V2w exactly its own 5.16; on a ghost's own market -> exactly that ghost; bar b=0/0.5/1 -> $11/$38.5/$66 ok")
    checks += 1

    # 15. WS CONTINUITY (6.1, risk 10): a reconnect blind 10 s -> excluded, 5 s -> kept; connected() false 7 s ->
    #     excluded; a SILENT socket (no frame at all) 419 s -> ws_silent + one resync + the span is a WS gap ->
    #     excluded; 219 s -> nothing; the whole hour -> excluded; an overnight-stale last frame before the 07Z subscribe
    #     is not silence; RecBook.drop clears livebook's _age.
    def cont_world(setup=None, hb=20.0):
        ww = _World(o, [_ladder_world(series=S10)], hb=hb)
        n_rs = [0]
        orig = ww.ws.resync

        def rs():
            n_rs[0] += 1
            orig()
        ww.ws.resync = rs
        if setup:
            setup(ww)
        ww.run(o + PERIOD_S + 700)
        s_ = ww.evs("hour_summary")[0]
        return s_, len(ww.evs("ws_silent")), n_rs[0], evaluate_bar([s_])["population_hours"]

    def reconnect(back):
        def setup(ww):
            ww.at(o + 1000.0, lambda sq: (ww.lb._on_connect(), '{"type": "ok"}')[1])
            for tk_, y_, n_ in ww.frames:
                ww.at(o + back, (lambda a_, b_, c_: lambda sq: _snap(a_, b_, c_, sq.b()))(tk_, y_, n_))
        return setup
    sa15, _, _, pa15 = cont_world(reconnect(1010.0))
    sb15, _, _, pb15 = cont_world(reconnect(1004.5))
    assert sa15["ws_blind_max_s"] == 10 and pa15 == 0 and exclusion_of(sa15) == "ws_gap", sa15["ws_blind_max_s"]
    assert sb15["ws_blind_max_s"] == 5 and pb15 == 1, sb15["ws_blind_max_s"]

    def down7(ww):
        ww.at(o + 1500.0, lambda sq: (ww.lb.connected.clear(), '{"type": "ok"}')[1])
        ww.at(o + 1507.0, lambda sq: (ww.lb.connected.set(), '{"type": "ok"}')[1])
    sc15, _, _, pc15 = cont_world(down7)
    assert sc15["ws_blind_max_s"] == 7 and pc15 == 0, sc15["ws_blind_max_s"]

    def silent(a_, b_):
        def setup(ww):
            ww.silent = [(o + a_, o + b_)]
        return setup
    sd15, nsd, rsd, pd15 = cont_world(silent(1000.0, 1400.0))      # last frame +985, next +1405
    assert nsd == 1 and rsd == 1 and abs(sd15["ws_silent_max_s"] - 419.0) < 1e-6 and pd15 == 0, \
        (nsd, rsd, sd15["ws_silent_max_s"], sd15["ws_blind_max_s"])
    assert abs(sd15["ws_blind_max_s"] - 419.0) < 1e-6 and exclusion_of(sd15) == "ws_gap"
    se15, nse, rse, pe15 = cont_world(silent(1000.0, 1200.0))      # 219 s: not silence
    assert nse == 0 and rse == 0 and se15["ws_blind_max_s"] == 0 and pe15 == 1, (nse, se15["ws_blind_max_s"])
    sf15, nsf, rsf, pf15 = cont_world(hb=None)                     # nothing after the open snapshots
    assert nsf >= 9 and rsf == nsf and abs(sf15["ws_blind_max_s"] - (PERIOD_S - EXIT_S)) < 1e-6 and pf15 == 0, \
        (nsf, rsf, sf15["ws_blind_max_s"])

    def stale(ww):
        ww.lb.last_rx_ms = int((o - 36000.0) * 1000)                # yesterday's last frame
        ww.snap_off = 3.0                                          # this hour's snapshots land 18 s after subscribe
    sg15, nsg, rsg, pg15 = cont_world(stale)
    assert nsg == 0 and rsg == 0 and pg15 == 1 and sg15["ws_blind_max_s"] == 3, (nsg, sg15["ws_blind_max_s"])
    lbx = RecBook(key_id="x", key_file="x")
    lbx.on_frame(json.dumps({"type": "subscribed", "id": 1, "msg": {"channel": "orderbook_delta", "sid": 1}}))
    sqx = _Seq()
    lbx.on_frame(_snap("AGE-1", {0.5: 10.0}, {0.4: 10.0}, sqx.b()), 1000)
    lbx.on_frame(_delta("AGE-1", "yes", 0.55, 5.0, 2.0)(sqx), 2000)
    assert "AGE-1" in lbx._age and lbx._age["AGE-1"]["yes"]
    WS(lbx).drop(["AGE-1"])
    assert "AGE-1" not in lbx._age and "AGE-1" not in lbx.books
    say("  15 WS continuity: reconnect blind 10 s -> excluded, 5 s -> kept; down 7 s -> excluded; silent 419 s -> 1 "
        "ws_silent, 1 resync, gap 419 s -> excluded; 219 s -> kept; silent hour -> %d resyncs, excluded; stale "
        "overnight frame -> no false silence; drop clears _age ok" % rsf)
    checks += 1

    # 16. SAFE SIDE (3.5, -$10): the yield moves 5.105 -> 5.185 ON a 5.03..5.25 ladder at +900 s -> ghost 5.17 (dead
    #     YES) is 1.5 bp in the money -> $10, 5.18 (0.5 bp) is not; the same move OFF a 5.03..5.17 ladder (risk 6) ->
    #     y_hat = top + 1 bp = 5.18, logged, -> 5.17 still charged $10; off the BOTTOM -> 5.02 -> both dead-NO ghosts
    #     charged ($20); a ladder already off at the plan posts nothing for that tenor (1.1: no crossing -> skip).
    def move_world(ks, side=None, ynew=None, at=900.0):
        ww = _World(o, [_ladder_world(series=S10, ks=ks)])
        for K in ks:
            up = (side == "above") or (side is None and K < ynew)
            yes, no = ({0.97: 50.0}, {0.02: 50.0}) if up else ({0.02: 50.0}, {0.97: 50.0})
            ww.at(o + at, (lambda a_, b_, c_: lambda sq: _snap(a_, b_, c_, sq.b()))(_tk(S10, K), yes, no))
        ww.run(o + PERIOD_S + 700)
        return ww

    def v2_safe(ww):
        return [(r_["ticker"], r_["cost"]) for r_ in ww.evs("vfill") if r_.get("kind") == "safe_cross"
                and "V2" in r_["variants"]]
    w16 = move_world([round(5.03 + 0.01 * i, 2) for i in range(23)], ynew=5.185)
    s16 = w16.evs("hour_summary")[0]
    assert sorted(w16.evs("hour_plan")[0]["variants"]["V2"]["posted"]) == [_tk(S10, K) for K in (5.03, 5.04, 5.17,
                                                                                                 5.18)]
    assert v2_safe(w16) == [(_tk(S10, 5.17), 10.0)] and s16["var"]["V2"]["n_safe"] == 1, v2_safe(w16)
    assert s16["var"]["V2"]["cost_det"] == 10.0 and not w16.evs("yhat_off_ladder")
    ks15 = [round(5.03 + 0.01 * i, 2) for i in range(15)]
    w16b = move_world(ks15, side="above")
    s16b = w16b.evs("hour_summary")[0]
    off = w16b.evs("yhat_off_ladder")
    assert len(off) == 1 and off[0]["side"] == "above" and abs(off[0]["y_hat"] - 5.18) < 1e-9, off
    assert v2_safe(w16b) == [(_tk(S10, 5.17), 10.0)] and s16b["var"]["V2"]["cost_det"] == 10.0, v2_safe(w16b)
    assert s16b["yhat_off_s"] == {S10: int(PERIOD_S - EXIT_S - 900)}, s16b["yhat_off_s"]
    w16c = move_world(ks15, side="below")
    s16c = w16c.evs("hour_summary")[0]
    assert [x[0] for x in sorted(v2_safe(w16c))] == [_tk(S10, 5.03), _tk(S10, 5.04)], v2_safe(w16c)
    assert s16c["var"]["V2"]["n_safe"] == 2 and s16c["var"]["V2"]["cost_det"] == 20.0
    assert w16c.evs("yhat_off_ladder")[0]["side"] == "below" and abs(w16c.evs("yhat_off_ladder")[0]["y_hat"] -
                                                                       5.02) < 1e-9
    w16d = move_world(ks15, side="above", at=10.0)
    p16d = w16d.evs("hour_plan")[0]
    assert p16d["tenors"][S10]["y_hat"] is None and p16d["tenors"][S10]["why"] == "no_crossing", p16d["tenors"]
    assert not w16d.evs("post") and not v2_safe(w16d)
    say("  16 safe side: on-ladder cross 1.5 bp -> $10 on 5.17 only; off the top -> y_hat 5.18 logged, $10; off the "
        "bottom -> 5.02, $20; off at the plan -> tenor skipped ok")
    checks += 1

    # 17. E_low QUEUE: 30 lots of others' 1c ahead of ghost 5.17 at post; a 50-lot dead-side 1c print at +600 s (no
    #     sweep: < 100) fills 20 of ours = $0.20 and ends its E_low credit at +600 s; a 10-lot cancel ahead first
    #     -> 30 filled = $0.30. Ghosts with no print: $0.
    def queue_world(cancel_ahead):
        ww = _World(o, [_ladder_world(series=S10, stacks={5.17: ("yes", 30.0)})])
        A = _tk(S10, 5.17)
        if cancel_ahead:
            ww.delta(o + 300.0, A, "yes", -10)
        ww.trade(o + 600.0, A, "no", 0.01, 50)
        ww.delta(o + 600.05, A, "yes", -(20 if cancel_ahead else 30))
        ww.run(o + PERIOD_S + 700)
        return ww.evs("hour_summary")[0]
    s17 = queue_world(False)
    v17 = s17["var"]["V2"]
    r17 = {g_["tk"]: g_ for g_ in v17["ghosts"]}
    A17 = _tk(S10, 5.17)
    assert s17["n_sweeps"] == 0 and r17[A17]["elow_q"] == 20.0 and abs(r17[A17]["elow_t_fill"] - 600.0) < 1e-6, r17[A17]
    assert v17["elow_cost"] == 0.2 and all(r17[tk]["elow_q"] == 0 for tk in r17 if tk != A17), v17["elow_cost"]
    sc17 = 1100.0 / 1130.0 + 1000.0 / 1050.0                       # YES 30 + our 1,100; NO 50 at 97c + our 1,000
    exp17 = floored(credit(10.0, PERIOD_S, 570 * sc17)) * PAID_FRAC + sum(
        floored(r17[tk]["raw"]) * PAID_FRAC for tk in r17 if tk != A17)
    assert abs(v17["elow_credit_x09"] - exp17) < 1e-4 and v17["elow_credit_x09"] < v17["credit_x09"] - 1.0, \
        (v17["elow_credit_x09"], exp17, v17["credit_x09"])
    s17b = queue_world(True)
    assert s17b["var"]["V2"]["elow_cost"] == 0.3, s17b["var"]["V2"]["elow_cost"]
    say("  17 E_low queue: 30 ahead, 50-lot print -> 20 filled $0.20, credit ends at the fill ($%.4f); a 10-lot cancel "
        "ahead first -> $0.30 ok" % v17["elow_credit_x09"])
    checks += 1

    # 18. a far sweep BEFORE the plan (+10 s, 5.5 bp): V2 / V2w / V2s post nothing that hour, V1 posts its 3
    w18 = _World(o, [_ladder_world(series=S10)])
    w18.trade(o + 10.0, _tk(S10, 5.16), "no", 0.01, 150)
    w18.run(o + PERIOD_S + 700)
    p18 = w18.evs("hour_plan")[0]["variants"]
    assert all(p18[v]["why"] == "sibling_sweep_before_plan" and not p18[v]["posted"] for v in ("V2", "V2w", "V2s")), p18
    assert p18["V1"]["why"] is None and len(p18["V1"]["posted"]) == 3, p18["V1"]
    cz18 = w18.evs("cancel")
    assert len(cz18) == 1 and cz18[0]["before_plan"] is True and cz18[0]["ghosts_cancelled"] == []
    assert w18.evs("hour_summary")[0]["var"]["V2"]["n"] == 0
    say("  18 pre-plan far sweep: V2/V2w/V2s post nothing, V1 posts 3 ok")
    checks += 1

    # 19. population from the recorder: a late start (+100 s) -> partial, refused, excluded; an id-less WS trade ->
    #     tape_gap; a 150-lot 1c print while the tenor has no y_hat (non-monotone ladder) -> unclassified_1c, excluded;
    #     a hour with no stack and no sweep -> NOT observable (imputed in the bar)
    w19 = _World(o, [_ladder_world(series=S10)])
    w19.t = o + 100.0
    w19.run(o + PERIOD_S + 700)
    s19 = w19.evs("hour_summary")[0]
    assert w19.evs("hour_plan")[0]["hour_refused"] == "partial_hour" and not w19.evs("post") and s19["partial"]
    assert exclusion_of(s19) == "partial"
    w19b = _World(o, [_ladder_world(series=S10)])
    w19b.trade(o + 500.0, _tk(S10, 5.10), "yes", 0.55, 10, rest=False, noid=True)
    w19b.run(o + PERIOD_S + 700)
    a19 = w19b.evs("audit")[0]
    assert a19["status"] == "tape_gap" and a19["ws_noid"] == 1 and a19["n_missing_in_rest"] == 0 \
        and a19["n_missing_in_ws"] == 0, a19
    assert exclusion_of(w19b.evs("hour_summary")[0]) == "tape_gap"
    rows19, frames19 = _ladder_world(series=S10)
    fix19 = {_tk(S10, 5.08): ({0.30: 10.0}, {0.60: 10.0}), _tk(S10, 5.09): ({0.80: 10.0}, {0.10: 10.0})}
    frames19 = [(tk, *fix19.get(tk, (yy, nn))) for tk, yy, nn in frames19]
    w19c = _World(o, [(rows19, frames19)])
    w19c.trade(o + 600.0, _tk(S10, 5.16), "no", 0.01, 150)
    w19c.run(o + PERIOD_S + 700)
    s19c = w19c.evs("hour_summary")[0]
    assert w19c.evs("hour_plan")[0]["tenors"][S10]["why"] == "ladder_nonmonotone" and s19c["n_sweeps"] == 0
    assert s19c["unclassified_1c_max"] == 150.0 and exclusion_of(s19c) == "unclassified_1c", s19c["unclassified_1c_max"]
    w19d = _World(o, [_ladder_world(series=S10)])
    w19d.run(o + PERIOD_S + 700)
    s19d = w19d.evs("hour_summary")[0]
    assert s19d["observable"] is False and not s19d["sweeper"] and s19d["var"]["V2"]["n"] == 3
    D5 = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
    e19 = evaluate_bar([_syn(d, hh, sw=(hh == 9)) for d in D5[:3] for hh in range(8, 18)] + [s19d])
    assert e19["population_hours"] == 31 and e19["observable_hours"] == 30 and e19["v2_b_upper"]["imputed_hours"] == 1
    say("  19 population: late start -> partial; id-less WS trade -> tape_gap; 150 unsided 1c lots -> excluded; a "
        "quiet hour is unobservable and imputed ok")
    checks += 1

    # 20. THE BAR, item by item at its boundary (6.2 / 6.3). Synthetic hours: 5 strike-hours paying $7 each; a
    #     sweeper hour has its 5 ghosts resting at the first sweep; at_risk 0 -> burst point 0, 90% bound 1.0.
    P_OBS, P_NET, P_HALF = "observable_hours>=50_on>=5_weekdays", "net_at_b_upper>=+2.00", "positive_both_halves"
    P_CR, P_SH = "credit_per_sh>=5.00", "strike_hours_per_weekday>=60"
    K_NET, K_EL, K_SW, K_CR, K_PROG = ("net_at_b_point<=0", "elow_net<=0", "sweeper_share>=0.80", "credit_per_sh<3.00",
                                       "programs_unlisted_2_consecutive_weekdays")
    H12 = list(range(8, 20))

    def pool(days, hours=H12, sw_hours=(9, 15), per=None, **kw):
        out_ = []
        for d in days:
            for hh in hours:
                k_ = dict(kw)
                k_.update((per or {}).get((d, hh), {}))
                out_.append(_syn(d, hh, sw=k_.pop("sw", hh in sw_hours), **k_))
        return out_

    def expect(e, verdict, pass_false=(), kill_true=(), name=""):
        assert e["verdict"] == verdict, (name, verdict, e["verdict"], e["pass_checks"], e["kill_checks"])
        if pass_false is not None:
            assert {k for k, v_ in e["pass_checks"].items() if not v_} == set(pass_false), (name, e["pass_checks"])
        assert {k for k, v_ in e["kill_checks"].items() if v_} == set(kill_true), (name, e["kill_checks"])
        return e
    base = pool(D5)
    eb0 = expect(evaluate_bar(base), "PASS", name="base")
    assert eb0["v2_b_upper"]["net_per_sh"] == round(1550 / 300, 4) and eb0["v2_b_point"]["net_per_sh"] == \
        round(1990 / 300, 4), (eb0["v2_b_upper"], eb0["v2_b_point"])
    assert eb0["burst"]["b_point"] == 0.0 and eb0["burst"]["b_upper90"] == 1.0 and eb0["sweeper_share"] == 0.1667
    assert eb0["strike_hours_per_weekday"] == 60.0 and eb0["half1"]["net_per_sh"] == eb0["half2"]["net_per_sh"] == \
        round(1550 / 300, 4) and eb0["v2_elow"]["net_per_sh"] == 7.0
    expect(evaluate_bar(pool(D5, per={(D5[0], 8): {"n": 4}})), "EXTEND", (P_SH,), name="59.8 sh/day")
    un10 = {(D5[0], hh): {"obs": False} for hh in H12 if hh not in (9, 15)}
    expect(evaluate_bar(pool(D5, per=un10)), "PASS", name="50 observable")
    expect(evaluate_bar(pool(D5, per={**un10, (D5[1], 8): {"obs": False}})), "EXTEND", (P_OBS,), name="49 obs")
    expect(evaluate_bar(pool(D5[:4], hours=range(7, 20))), "EXTEND", (P_OBS,), name="52 obs on 4 days")
    safe40 = {(d, hh): {"n_safe": 1} for d in D5 for hh in H12 if hh not in (9, 11, 15, 17)}
    en2 = expect(evaluate_bar(pool(D5, sw_hours=(9, 11, 15, 17), per=safe40)), "PASS", name="net 2.00")
    assert en2["v2_b_upper"]["net_per_sh"] == 2.0, en2["v2_b_upper"]
    e199 = expect(evaluate_bar(pool(D5, sw_hours=(9, 11, 15, 17), per={**safe40, (D5[0], 8): {"n_safe": 1, "c": 6.98}})),
                  "EXTEND", (P_NET,), name="net 1.9997")             # $0.10 less credit in one hour
    assert e199["v2_b_upper"]["net_per_sh"] == 1.9997, e199["v2_b_upper"]
    safe45 = {**safe40, **{(D5[0], hh): {"n_safe": 2} for hh in (8, 10, 12, 13, 14)}}
    safe45[(D5[0], 9)] = {"at_risk": 1}
    ebd = expect(evaluate_bar(pool(D5, sw_hours=(9, 11, 15, 17), per=safe45)), "EXTEND", (P_NET,), name="bound")
    assert ebd["burst"]["b_upper90"] == round(cp_upper(0, 1), 4) == 0.95 and ebd["v2_b_upper"]["net_per_sh"] == 1.98 \
        and ebd["v2_b_point"]["net_per_sh"] == round(1430 / 300, 4), (ebd["burst"], ebd["v2_b_upper"])
    heavy = [3] * 7 + [2] * 5                                       # 31 safe fills = $310 on a $420 - $110 day
    for days_neg, nm in ((D5[3:], "second half <= 0"), (D5[:3], "first half <= 0")):
        per_ = {(d, hh): {"n_safe": heavy[i]} for d in days_neg for i, hh in enumerate(H12)}
        eh = expect(evaluate_bar(pool(D5, per=per_)), "EXTEND", (P_HALF,), name=nm)
        assert eh["v2_b_upper"]["net_per_sh"] >= 2.0 and min(eh["half1"]["net_per_sh"], eh["half2"]["net_per_sh"]) \
            == 0.0, (eh["half1"], eh["half2"])
    expect(evaluate_bar(pool(D5, c=5.0)), "PASS", name="credit 5.00")
    expect(evaluate_bar(pool(D5, c=4.99)), "EXTEND", (P_CR,), name="credit 4.99")
    # KILL (3 weekdays x 12 hours = 36 >= 30): each item alone, at its boundary
    k0 = expect(evaluate_bar(pool(D5[:3])), "EXTEND", (P_OBS,), name="kill base")
    assert k0["kill_ready"]
    pre24 = {(d, hh): {"n_pre": 1, "n_safe": 1} for d in D5[:3] for hh in H12 if hh not in (9, 15)}
    pre24.update({k_: {"n_safe": 1} for k_ in list(pre24)[24:]})   # 24 near sweeps + 30 safe fills = $564 + $66
    ek = expect(evaluate_bar(pool(D5[:3], c=3.5, per=pre24)), "KILL", None, (K_NET,), name="net 0")
    assert ek["v2_b_point"]["net_per_sh"] == 0.0 and ek["v2_elow"]["net_per_sh"] > 0, ek["v2_b_point"]
    pre24b = {**pre24, list(pre24)[-1]: {}}
    expect(evaluate_bar(pool(D5[:3], c=3.5, per=pre24b)), "EXTEND", None, (), name="net +0.06")
    expect(evaluate_bar(pool(D5[:3], elow_k=35.0)), "KILL", None, (K_EL,), name="elow 0")
    expect(evaluate_bar(pool(D5[:3], elow_k=35.0, per={(D5[0], 8): {"elow_k": 34.82}})), "EXTEND", None, (),
           name="elow +0.001")

    def sweepy(day3_hours, day3_non, extra=()):
        rows_ = []
        for d, hours, non in ((D5[0], range(8, 21), (8, 20)), (D5[1], range(8, 21), (8, 20)),
                              (D5[2], day3_hours, day3_non)):
            rows_ += [_syn(d, hh, sw=hh not in non) for hh in hours]
        return rows_ + list(extra)
    es = expect(evaluate_bar(sweepy(range(7, 21), (7, 8, 19, 20))), "KILL", None, (K_SW,), name="sweeper 32/40")
    assert es["sweeper_share"] == 0.8
    expect(evaluate_bar(sweepy(range(8, 21), (8, 9, 19, 20))), "EXTEND", None, (), name="sweeper 31/39")
    esd = expect(evaluate_bar(sweepy(range(7, 21), (7, 8, 19, 20), [_syn(D5[3], hh, obs=False) for hh in range(8, 18)])),
                 "KILL", None, (K_SW,), name="sweeper share over OBSERVABLE hours")
    assert esd["population_hours"] == 50 and esd["sweeper_share"] == 0.8
    r29 = [_syn(d, hh, sw=hh != 8) for d in D5[:2] for hh in range(8, 18)] + \
          [_syn(D5[2], hh, sw=hh in (9, 10, 11, 12, 13, 14)) for hh in range(8, 17)]
    expect(evaluate_bar(r29), "TOO_EARLY", None, (K_SW,), name="29 hours")
    r30 = r29 + [_syn(D5[2], 17, sw=False)]
    expect(evaluate_bar(r30), "KILL", None, (K_SW,), name="30 hours")
    expect(evaluate_bar(pool(D5[:3], c=2.99, sw_hours=())), "KILL", None, (K_CR,), name="credit 2.99")
    expect(evaluate_bar(pool(D5[:3], c=3.0, sw_hours=())), "EXTEND", None, (), name="credit 3.00")
    expect(evaluate_bar(pool(D5[:3]), {D5[0]: True, D5[1]: False, D5[2]: False}), "KILL", None, (K_PROG,),
           name="2 consecutive unlisted")
    expect(evaluate_bar(pool(D5[:3]), {D5[0]: False, D5[1]: True, D5[2]: False}), "EXTEND", None, (),
           name="unlisted, not consecutive")
    eb_ = evaluate_bar(pool(D5[:3], at_risk=8, hits=2))
    assert eb_["burst"]["at_risk"] == 48 and eb_["burst"]["hits"] == 12 and eb_["burst"]["b_point"] == 0.25
    assert eb_["v2_b_point"]["net_per_sh"] == round((1260 - 132) / 180, 4), eb_["v2_b_point"]
    assert eb_["v2_b_upper"]["net_per_sh"] == round((1260 - 66 * (1 + 4 * cp_upper(12, 48))) / 180, 4)
    # 6.1 exclusions: each one a toxic hour (n_pre 200 = -$2,200) that would KILL the pool if it leaked in
    tox = dict(c=0.0, n_pre=200)
    popx = pool(D5[:3], hours=range(8, 18), sw_hours=()) + [
        _syn(D5[0], 18, blackout="blackout: test", **tox), _syn(D5[0], 19, partial=True, **tox),
        _syn(D5[1], 18, ws_blind_max_s=6.0, **tox), _syn(D5[1], 19, audit="tape_gap", **tox),
        _syn(D5[2], 18, audit="failed", **tox), _syn(D5[2], 19, audit=None, **tox),
        _syn("2026-10-24", 14, **tox), _syn("2026-10-16", 14, **tox), _syn(D5[3], 14, skipped=True, **tox),
        _syn(D5[3], 15, unclassified_1c_max=100.0, **tox),
        _syn(D5[3], 16, ws_blind_max_s=5.0), _syn(D5[3], 17, unclassified_1c_max=99.0)]
    ex = expect(evaluate_bar(popx), "EXTEND", None, (), name="exclusions")
    assert ex["population_hours"] == 32 and ex["excluded"] == {
        "skipped": 1, "weekend": 1, "before_first_day": 1, "blackout": 1, "partial": 1, "ws_gap": 1, "tape_gap": 1,
        "audit_not_clean": 2, "unclassified_1c": 1}, ex["excluded"]
    say("  20 bar: base PASS (net $%.4f at the bound, $%.4f at the point); each PASS item flips alone at its boundary "
        "(59.8 sh/day, 49 obs, 4 days, net 1.9997, bound 0.95 -> 1.98, a half at 0, credit 4.99); each KILL item alone "
        "(net 0, E_low 0, sweeper 32/40 of OBSERVABLE, credit 2.99, 2 unlisted days), 29 h -> TOO_EARLY; 9 exclusion "
        "reasons, 5.0 s / 99 lots kept ok" % (eb0["v2_b_upper"]["net_per_sh"], eb0["v2_b_point"]["net_per_sh"]))
    checks += 1

    # 21. --report reads only hour_summary / programs rows (review fix 5: the full log put it at 168 MB at 10 weekdays)
    lp21 = os.path.join(tmpd, "report.jsonl")
    with open(lp21, "w", encoding="utf-8") as fh:
        for s_ in base:
            fh.write(json.dumps(dict(s_, t="x", ev="hour_summary"), separators=(",", ":")) + "\n")
        for i in range(2000):
            fh.write(json.dumps({"t": "x", "ev": "score10", "note": "hour_summary", "g": [[i] * 7] * 8},
                                separators=(",", ":")) + "\n")
        fh.write(json.dumps({"t": "x", "ev": "programs", "hour": "2026-10-19T08:00Z", "status": "listed"}) + "\n")
        fh.write(json.dumps({"t": "x", "ev": "score10", "inner": {"ev": "hour_summary"}}, separators=(",", ":")) + "\n")
        fh.write('{"t": "x", "ev":"hour_summ')
    got21 = read_log(lp21)
    assert len(got21) == 61 and sum(1 for r_ in got21 if r_["ev"] == "hour_summary") == 60, len(got21)
    assert len(read_log(lp21, None)) == 2062
    e21 = report(lp21, out=lambda *a_: None)
    assert e21["verdict"] == "PASS" and e21["v2_b_upper"] == eb0["v2_b_upper"] and e21["pass_checks"] == eb0["pass_checks"]
    assert e21["log_rows_parsed"] == 61, e21["log_rows_parsed"]
    os.remove(lp21)
    say("  21 report: parses only hour_summary/programs rows (61 of 2,063 lines), same verdict as the evaluator ok")
    checks += 1

    # 22. a step() exception repeating at 8 steps/s is logged once a minute with a count (not 860k rows a day)
    class _Boom(Recorder):
        def step(self, now, ws, jobs, call):
            raise ValueError("boom")
    lg22, clk = Log(None), [1000.0]
    why22 = loop(_Boom(lg22), _FakeWS(), Jobs(sync=True), None, lambda: clk[0],
                 lambda s_: clk.__setitem__(0, clk[0] + s_), None, 1e12, dt=0.125, max_steps=1300)
    e22 = [r_ for r_ in lg22.rows if r_["ev"] == "error"]
    assert why22 == "max_steps" and len(e22) == 3 and e22[0]["repeats_since_last"] == 0 \
        and e22[1]["repeats_since_last"] == 479, (len(e22), e22[:2])
    say("  22 step errors: 1,300 failing steps -> 3 rows (479 repeats counted) ok")
    checks += 1

    # 23. the walk on a LIVE ghost: others bid 118 at 99c on 5.17's safe side (NO) for exactly 600 s. The post-July
    #     rule (the decision) keeps counting -- NO share 1000/1168 -- the old rule (logged) counts nothing then:
    #     raw - old = $10 x 600 s x (1 + 1000/1168) / 7,080 s
    w23 = _World(o, [_ladder_world(series=S10)])
    A23 = _tk(S10, 5.17)
    w23.delta(o + 600.0, A23, "no", 118, p=0.99)
    w23.delta(o + 1200.0, A23, "no", -118, p=0.99)
    w23.run(o + PERIOD_S + 700)
    g23 = {g_["tk"]: g_ for g_ in w23.evs("hour_summary")[0]["var"]["V2"]["ghosts"]}[A23]
    exp23 = credit(10.0, PERIOD_S, 600 * (1.0 + 1000.0 / 1168.0))
    assert abs((g23["raw"] - g23["old"]) - exp23) < 1e-4, (g23["raw"], g23["old"], exp23)
    say("  23 live walk: a 99c safe bid for 600 s costs the old rule $%.4f, the post-July rule keeps it ok" % exp23)
    checks += 1

    # 24. REST: every call >= REST_MIN_GAP_S after the previous one, 10 s after a 429, never authenticated
    t24, seen24 = [1000.0], []
    reply24 = iter([(429, {}), (200, {}), (200, {}), (200, {})])

    def get24(path, params, auth=None):
        seen24.append((t24[0], auth))
        return next(reply24)
    rr = Rest(get24, clock=lambda: t24[0], sleep=lambda x: t24.__setitem__(0, t24[0] + x))
    for path_ in ("/a", "/b", "/c"):
        assert rr.call(path_, {})[0] == 200
    ts24 = [x[0] for x in seen24]
    assert rr.n == 4 and rr.n429 == 1 and all(a is False for _, a in seen24), seen24
    assert ts24[1] - ts24[0] == REST_429_S and min(b - a for a, b in zip(ts24[1:], ts24[2:])) >= REST_MIN_GAP_S >= 2.0
    say("  24 REST: calls %s s apart after a 429 back-off of %g s, auth=False always ok"
        % ([b - a for a, b in zip(ts24[1:], ts24[2:])], REST_429_S))
    checks += 1
    say("SELF-TEST PASSED: %d check groups" % checks)
    return checks


def _clone(s, n_days, n_hours):
    days = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"][:n_days]
    out = []
    for d in days:
        for hh in range(n_hours):
            x = json.loads(json.dumps(s))
            x["day"] = d
            x["hour"] = "%sT%02d:00Z" % (d, 8 + hh)
            out.append(x)
    return out


def _synth_summary(day, hh, n, credit_each, observable, sweeper, g1=0, n_win=0, at_risk=0, hits=0):
    o = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() + hh * 3600
    cost = DEAD_COST * max(n_win, 1) if sweeper and g1 else 0.0
    v = {"n": n, "credit_x09": credit_each * n, "elow_credit_x09": credit_each * n, "elow_cost": 0.0, "g1": g1,
         "n_pre": 0, "n_win": n_win, "n_safe": 0, "cost_det": cost, "ghosts": []}
    return {"hour": iso_hour(o), "open": o, "day": day, "weekday": True, "blackout": None, "partial": False,
            "ws_blind_max_s": 0, "audit": "clean", "observable": observable, "sweeper": sweeper,
            "t1_from_open": 1700.0 if sweeper else None,
            "burst": {"at_risk": at_risk, "hits_0.3": hits} if sweeper else None, "var": {"V2": v}, "ghosts": {}}


def _syn(day, hh, n=5, c=7.0, obs=True, sw=False, at_risk=0, hits=0, n_safe=0, n_pre=0, elow_c=None, elow_k=None,
         **flags):
    """A synthetic hour summary for the bar checks: n V2 strike-hours each paying c (already floored x 0.9); a sweeper
    hour has all n ghosts resting at its first sweep (n_win 1) and `at_risk` / `hits` for the burst share; n_pre near
    sweeps and n_safe safe fills; ghost rows + per-minute credit so an unobservable hour can be imputed."""
    o_ = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() + hh * 3600
    raw, span = c / PAID_FRAC, PERIOD_S - EXIT_S - PLAN_S
    rows = [{"tk": "G%d" % i, "raw": raw, "end": PERIOD_S - EXIT_S, "cause": "exit"} for i in range(n)]
    meta = {"G%d" % i: {"t_post": PLAN_S, "cum_min": [round(raw * min(60 * k, span) / span, 6) for k in range(50)]}
            for i in range(n)}
    v = {"n": n, "credit_x09": c * n, "g1": n if sw else 0, "n_pre": n_pre, "n_win": 1 if (sw and n) else 0,
         "n_safe": n_safe, "cost_det": DEAD_COST * (n_pre + (1 if sw and n else 0)) + SAFE_COST * n_safe,
         "elow_credit_x09": c * n if elow_c is None else elow_c,
         "elow_cost": SAFE_COST * n_safe if elow_k is None else elow_k, "ghosts": rows}
    s = {"hour": iso_hour(o_), "open": o_, "day": day, "weekday": datetime.fromtimestamp(o_, UTC).weekday() < 5,
         "blackout": None, "partial": False, "ws_blind_max_s": 0, "audit": "clean", "observable": obs, "sweeper": sw,
         "t1_from_open": 1700.0 if sw else None, "burst": {"at_risk": at_risk, "hits_0.3": hits} if sw else None,
         "var": {"V2": v}, "ghosts": meta, "unclassified_1c_max": 0.0}
    s.update(flags)
    return s

# ================================================================================================ main
def code_sha():
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser(description="RATEH reward-pair PAPER recorder (GET only)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--once", action="store_true", help="plan the current/next hour over REST and print it (no WS)")
    ap.add_argument("--minutes", type=float, default=None, help="the paper run, this many minutes")
    ap.add_argument("--history", metavar="YYYY-MM-DD", help="candle + tape back-fill of a settled weekday (6.4 gate)")
    ap.add_argument("--report", action="store_true", help="the pre-registered bar from the log")
    ap.add_argument("--log", default=LOG_PATH)
    a = ap.parse_args()
    if "--live" in sys.argv:
        print("REFUSING: this file is paper only")
        return 2
    try:
        selftest(verbose=a.selftest)
    except Exception as e:                                  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("SELF-TEST FAILED:", repr(e))
        return 2
    if a.selftest:
        return 0
    if a.report:
        report(a.log)
        return 0
    import kauth                    # GET-only signed helper; opens the key file, so only after the self-test
    rest = Rest(kauth.get)
    if a.history:
        history(a.history, rest.call)
        print("REST calls %d (429s %d)" % (rest.n, rest.n429))
        return 0
    log = Log(a.log)
    if a.once:
        once(rest.call, time.time(), log=log)
        print("REST calls %d (429s %d)" % (rest.n, rest.n429))
        return 0
    if a.minutes is None:
        ap.print_help()
        return 0
    lock = InstanceLock(LOCK_PATH)
    if not lock.acquire():
        print("REFUSING: another instance holds %s" % LOCK_PATH)
        return 3
    try:
        rec = Recorder(log)
        restored = rec.restore(a.log)
        log.write("start", pid=os.getpid(), argv=sys.argv, code_sha=code_sha(), rules=RULES, restored=restored,
                  minutes=a.minutes, blackout_hours={iso_hour(k): v for k, v in sorted(BLACKOUT.items())},
                  stop_file=STOP_PATH, selftest="passed")
        print("ratehreward_paper start pid %d sha %s restored %s" % (os.getpid(), code_sha(), restored), flush=True)
        lb = RecBook(key_id=kauth.KEY_ID, key_file=kauth.KEY_FILE)
        ws = WS(lb)
        jobs = Jobs()
        why = loop(rec, ws, jobs, rest.call, time.time, time.sleep, STOP_PATH, time.time() + a.minutes * 60.0)
        try:
            lb.stop()
        except Exception:                                   # noqa: BLE001
            pass
        print("stopped: %s; REST calls %d (429s %d)" % (why, rest.n, rest.n429), flush=True)
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
