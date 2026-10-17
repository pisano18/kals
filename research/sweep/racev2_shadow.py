#!/usr/bin/env python3
"""racev2_shadow.py -- PAPER SHADOW of the Coin Race 1c reward filler v2, replayed hour by hour on OUR OWN tape.

Spec: .sweep/hunt-2026-10-15/spec-20261015-R1-C2-02/SPEC.md, section 2 (Part A, "the paper shadow"; the spec calls the
file racefill_shadow.py). PAPER BY CONSTRUCTION: no order is ever sent, no API key is ever loaded (kauth is not
imported), there is no non-GET request anywhere in this file, and the self-test asserts all of that from the source.

WHAT IT ANSWERS
  1. Supply now: postable dead legs per race, and when they become postable.
  2. Tape cost now, under five fill models, on fresh days: the paper gate (4.1 below) before any live test.
  3. Once v2 runs live (results/racereward-v2-live.jsonl): our live fills next to every tape model on the same legs,
     and posted vs control legs' 1c-sale + 99c-add flow (the "do sellers target our bid" read, spec 4.3).

INPUTS (all read-only)
  * Our tape C:\\kals\\kalshi_data\\{orderbook_snapshot,orderbook_delta,trade}\\<YYYYMMDD>T<HH>.jsonl.gz, KXCRYPTOLEAD15M
    lines only, CLOSED hours only (hour H once the clock is past H+1:02 and a LATER hour's delta file exists -- normally
    H+1; an hour with no file at all is logged `missing`, never waited on, and never counts toward the 12-empty-hours
    stop; 20261015T08 and 20261014T04..20261015T03 are missing on the real tape), one hour file
    streamed at a time, never opened for write. Book state carries across hours (a race closing at :00 opens its
    window at :53:20 of the hour before). Book rebuild = extract.py's Leg logic: the level-carrying snapshot, then deltas
    with the same sid and seq > the snapshot's; an empty mid-life snapshot clears the book; a delta before any snapshot
    is counted and skipped; sizes rounded to 0.01 after every update. Units come from the FIELD NAME (price_dollars,
    yes_price_dollars are dollars); a non-whole-cent price is counted and flags the leg, never rescaled (hard rule 5).
    Multi-member gzip files are read to the end; a corrupt tail is counted and the rest of that file is skipped.
  * Trades: a sale into 1c YES bids = the taker sold YES (taker_outcome_side 'no', else taker_book_side 'ask', else the
    deprecated taker_side 'no') at yes_price_dollars <= 0.0100. Checked on the 2026-10-17T03 tape: 506 of 506 coin-race
    prints carry all three fields, as (yes, yes, bid) or (no, no, ask).
  * Public GETs, unauthenticated, >= 2.0 s apart (429 -> 10 s back-off): /incentive_programs status=active and
    upcoming, type=liquidity, once an hour (period_reward is CENTI-CENTS: /10000 = dollars); status=closed then paid_out
    only for a race whose program was never seen (a catch-up), each ticker searched once by a listing that did not
    fail, paging stopped once every program on a page ended > 1 day before the oldest close looked up (the
    listings are newest-first); /markets?series_ticker=KXCRYPTOLEAD15M&min_close_ts&max_close_ts once per tape hour
    with a file for close_time (the API's, not the ticker's: the tickers are ET and repeat 01:00-02:00 ET on
    2026-11-01) and result, plus one targeted call for a leg that hourly window missed. A leg with no program is NOT
    scored (never an assumed $20/1,000). A race whose program listing or /markets call FAILED is held and retried
    each hour (up to 3), then logged with `lookup_failed` -- never as programs-missing, never silently dropped.
  * Our own v2 live log results/racereward-v2-live.jsonl (when it exists): placed / fill / cancelled / expired rows.
    Our remaining size is subtracted from the tape's 1c YES level between placement and our off time (rr.others_of);
    a leg where that would go negative (beyond 2 s of the placement/off edges and a 15 s fill-poll lag) is flagged and
    not scored.

THE RULE IT REPLAYS (v2; parameters fixed by the spec, NOT tuned here)
  Scored with racereward_live's OWN functions, imported (leg_refusal, snapshot, credit, floored, period_of, others_of,
  et_offset_h, et_day, InstanceLock), so the paper makes the decision the live bot would. Per leg with a program, at
  integer seconds L = 360 .. 116 left, on everyone else's book:
    place at the FIRST L where rr.leg_refusal(...) is None [(a) best YES <= $0.03, (b) others' YES < target, (c) best NO
    <= $0.98, (d) NO walk qualifies] AND the projection (rr.Bot.floor_check's arithmetic) (L - 115 - 2) x share_now x
    reward / (2 x 900) >= $1.25 with size min(1,100, target + 100) at $0.01; it rests from L-1 (1 s send latency).
    Each second, on the state at that second, BEFORE crediting: cancel if others' best YES > $0.05 (alive); cancel if
    YES side incl. our remaining < target for 5 consecutive seconds (starved). Gone at 115 s (server-side expiry).
    Credit per counted second = share x reward / (2 x 900), with NO levels at 99c removed from the NO book while we
    rest (with our bid there they would have crossed it). Under walk_july a 99c top no longer disqualifies a side, so
    the removal can only LOWER credit, and only when the 99c size is what lifts the NO side to its target (self-test
    0b plants that case). paid = floored(0.987 x credit): $0 under $1.00.
  THE JULY RULE: the walk used for credit is walk_july = rr.walk minus its "highest bid must be under the highest
  possible price" exclusion, which the filed rule (2026-07-15) no longer has (results/STRATEGY_HUNT_2026-10-15.md, Facts
  learned: "The July rule removed the 'best bid below the top price' exclusion that research/sweep/racereward_live.py's
  walk still applies."). The self-test shows walk_july == rr.walk on every book whose best bid is under 99c. In the v2
  replay neither side can top at 99c while we rest (99c NO removed; YES over 5c cancels), so the two agree there; each
  leg logs rule_diff_s, the seconds where they did not.
  Fill models (per placed leg; all capped at our remaining size):
    low     1c sales after the 1c queue that was ahead of us at placement; the queue shrinks by sales only
    mid     as low, but the queue also shrinks by 1c YES cancels (max(0, neg1c - sold1c))
    high    every 1c sale while we rest fills us
    x99     high + NO size ADDED at 99c while we rest, replace-adjusted (an add matched by 99c removals in the same or
            previous 3 s is a re-post: refute-stats x99check2 `new99`); x99g = the same with gross adds
    latent  per ET day: sales into others' >= 1,100 1c piles on dead legs at 285..116 s per pile-second, x our resting
            seconds (high world), capped at 1,100 (computed in the `day` row; reference rates logged next to it:
            refute-execution 0.072/s, tester 80-94 per window)
  Each model is its own world: its fills shrink our remaining, so its starved cancel and credit are its own. Costs:
  conservative (every filled contract -$0.01; THE BARS USE THIS) and outcome-signed (-$0.01 NO leg, +$0.99 YES leg).
  Rails: `open` (every postable leg; the pot is the only cap) and `as_live` (rail (f) exactly as rr.Bot.rails_refusal /
  check_day_stop with v2's caps: realized - unsettled fill cost - resting collateral - this order's $11 >= -$30 on the
  ET day, <= 5 resting, collateral <= $40; fills known only when they happen; each order counts at most its own $11;
  credits invisible; models low/mid/high/x99). Free variants (logged, never traded): exit 60/90/150 s, size
  1,250/1,500, early-join behind an incumbent pile.

PRE-REGISTERED BARS, quoted verbatim from SPEC.md section 4 (written 2026-10-16, before any forward-shadow number or any
v2 fill existed). They are not moved here.

  ### 4.1 Paper gate (shadow; decides whether to RECOMMEND the live test)
  Read after the first **3 full ET days** of `--follow` (>= 250 scored races with a program and all 5 legs clean),
  `open` rails, conservative cost. **HOLD** the live test if ANY of these:
  - x99 (replace-adjusted) cost > **70%** of paid-model credit (10-07..10-15 gave 47.8%);
  - placed legs < **0.7 per race** (was 2.0);
  - programs missing on > **5%** of races.
  Otherwise recommend the live test to the operator with the shadow's numbers. The gate cannot PASS the idea. Only
  live fills can.

  ### 4.2 Live bar (the hunter's numbers, unchanged; middle zone and payment kill added and labelled as additions)
  Sample = the first **20 races with >= 1 v2 order** (~35-45 legs, ~20 race clusters, >= 2 ET days, >= 5 races closing
  00-04 ET, via `--every 3`, started between 21:00 and 23:00 ET so that 00-04 ET falls inside and the run crosses an ET
  midnight). Read main pool 0 **2 h after the last race**, and the `paid_out` flags **48 h** after it.
  - C = filled contracts x $0.01 on test legs (conservative: gains on legs that settle YES are ignored).
  - M = sum over test legs whose projection at placement was >= $1.25 of (filing walk on the bot's per-second snapshots
    x 0.987, $0 under $1.00).
  - P = main pool 0 increase attributed to the test windows.
  - **PASS: C <= 0.25 M AND P >= 0.90 M.** -> put the v3 credit-aware budget to the operator.
  - **KILL: C > 0.50 M** (hunter) **or P < 0.50 M at 48 h** (addition: Kalshi not paying at this scale).
  - Between (addition): **EXTEND by 20 more races**, same settings, and decide on the pooled 40 by the same lines. If it
    is still between at 40, the bot stays at rail (f) (<= $30/day at risk), and the credit-aware budget goes to the
    operator with the measured ratio. Nothing scales automatically.
  - Power: with ~20 race clusters the standard error of C/M is about 0.10. That tells 25% from 50%, but NOT 40% from 50%.
    **One full 1,100 dump = $11, about 20 points of C/M on a ~$50 test.** So the count of full dumps is reported next
    to the ratio.
  - Break-even is C ~ 0.9 M, so a 25-50% result still makes money. The kill line is deliberately conservative.

  How this file reads 4.1 (fixed here before any number is seen): "x99 cost" = the x99 world's conservative fill cost
  WITH v2's starved cancel; "paid-model credit" = that same world's paid credit; both summed over the placed legs of
  the scored races of the first 3 full ET days (`full` = every UTC hour overlapping the day, plus the hour before, was
  processed by this follow log). Printed next to it for comparison with the 47.8% reference: x99 cost over the high
  world's paid, and the no-starved-rule construction. "Placed legs per race" = open-rail placed legs / scored races.
  "Programs missing" = clean races (5 legs, tape clean) with a leg Kalshi listed no program for / clean races.
  AMENDED 2026-10-17 after the independent review, before any gate day existed (the bar's text is unchanged):
  (a) a race whose program listing FAILED is left out of that line's numerator AND base (unknown, not missing) and
  counted separately in the report; (b) that line is read FIRST, before the 250-scored-race floor, because missing
  programs also remove races from the scored count -- read after it, its HOLD turned into NOT_READY above ~13%
  missing. 4.2 is read from live fills by racereward_live v2 --report, never from this file; the shadow supplies the
  4.3 calibration table.

WHAT THE SHADOW CANNOT SEE
  Sellers who sell only because our bid is there (the latent question). The tape shows who sold into OTHER 1c bids and
  who rested NO at 99c; it cannot show demand that appears only when a 1,100-lot is resting. Only live fills settle that.

LOG results/racev2-shadow.jsonl (UTC `t`, `ev`): start (pid, argv, code_sha, rr_sha, rules) / hour_done (missing,
  empty_run, races held, diag, calls, bytes, rss, disk, recorder file ages) / leg (one per leg per race) / race
  (lookup_failed, deferred_hours) / day (once all its races are final, held ones included; races_unseen = quarter-hours
  with no race on the tape) / stop. State results/racev2-shadow.state.json (the cursor: next hour, program cache).
  Stop file results/racev2-shadow.stop ends a running instance cleanly between hours. Idempotent by race: a restart re-reads
  the hour before its cursor (books carry across hours) and skips every race already in the log.

    python research/sweep/racev2_shadow.py --selftest
    python -u research/sweep/racev2_shadow.py --follow --hours 336 --since 20261017T03    (catch up, then hourly)
    python research/sweep/racev2_shadow.py --backfill 20261016        (one ET day into its own log, then exit)
    python research/sweep/racev2_shadow.py --report [--days 3]        (the 4.1 gate table and the 4.3 calibration)
    python research/sweep/racev2_shadow.py --compare-dry [PATH]       (v2 --dry-run would_place vs the shadow, bar 90%)

RESOURCES: one hour streamed at a time, about 10 live legs in memory, < 150 MB (checked each hour; the process stops
itself above it); ~6-15 s of CPU per tape hour; about 4 public calls an hour (~100 a day, ~3 MB an hour of program
listings); worst case (Kalshi lists none of an hour's programs) 7 fallback pages, 13.2 MB an hour on top (measured
on the real listings 2026-10-17; 24 pages / ~45 MB without the paging stop); stops itself
under 15 GB free disk or after 12 consecutive hours whose file holds no coin-race line (missing hours not counted).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(RESEARCH)
RESULTS = os.path.join(REPO, "results")
sys.path.insert(0, HERE)
import racereward_live as rr  # noqa: E402  -- the live bot's own scoring, imported, never re-derived

TAPE = r"C:\kals\kalshi_data"
FEEDS = r"C:\kals\feed_data"
NAME = "racev2-shadow"
LOG = os.path.join(RESULTS, NAME + ".jsonl")
STATE = os.path.join(RESULTS, NAME + ".state.json")
STOP = os.path.join(RESULTS, NAME + ".stop")
LIVE_V2_LOG = os.path.join(RESULTS, "racereward-v2-live.jsonl")
BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = rr.SERIES
COINS = rr.COINS
TK_PREFIX = SERIES + "-"

# ---- v2 parameters, fixed by the spec (section 2 "The rule it replays"; section 3 items 1-3, 6) -- NOT tuned here
EXIT_S = 115
COUNT_CAP = 1100
CUSHION = 100
POST_FLOOR = 1.25
PAID_FACTOR = 0.987
WINDOW = int(rr.WINDOW_S)                 # 360
STARVE_N = 5
MAX_COLLATERAL_V2 = 40.00
DAY_STOP = rr.DAY_STOP                    # -30
MAX_RESTING = rr.MAX_RESTING              # 5
PILE_LO, PILE_HI = 116, 285
PILE_MIN = 1100.0
X99_LOOKBACK = 3
MODELS = ("low", "mid", "high", "x99", "x99g")
RAIL_MODELS = ("none", "low", "mid", "high", "x99")      # 'none' = no fills: what a dry run's rail (f) sees
VARIANT_EXITS = (60, 90, 150)
VARIANT_SIZES = (1250, 1500)
REF_LATENT_RATE = 0.072                   # refute-execution forward poll, contracts per pile-second
REF_LATENT_WINDOW = "80-94"               # tester, contracts per 115-300 s window
# ---- tape and process
REC_MAX = 400
MIN_L = 61                                # seconds that must be present for a leg to be scored (exit-60 variant)
GAP_MAX_S = 60
KEEP_CUM = 2200.0
KEEP_LEVELS = 60
OWN_EDGE_S = 2.0
OWN_POLL_LAG_S = 15.0
CALL_SPACING_S = 2.0
BACKOFF_429_S = 10.0
HTTP_TIMEOUT_S = 30
PROGRAM_PAGE = 5000
PROGRAM_REFRESH_S = 3300
FALLBACK_PAGES = 12
FALLBACK_STOP_MARGIN_S = 86400            # the listings are newest-first: stop a status once every program on a page
                                          # ended > 1 day before the oldest close looked up
DEFER_TRIES = 3                           # hours a race is held back and retried after a failed program/markets lookup
HOUR_GRACE_S = 120
MEM_LIMIT_MB = 150.0
DISK_MIN_GB = 15.0
EMPTY_HOURS_STOP = 12
PACE_S = 2.0
RECORDER_STALE_S = 600
OFF_EVENTS = ("cancelled", "cancel_confirmed", "expired", "exchange_cancelled", "never_created", "rejected")
MON = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
RULES = {"series": SERIES, "window_s": WINDOW, "exit_s": EXIT_S, "count": "min(%d, target + %d)" % (COUNT_CAP, CUSHION),
         "post_floor": POST_FLOOR, "pay_floor": rr.FLOOR_USD, "paid_factor": PAID_FACTOR, "dead_yes": rr.DEAD_YES,
         "alive_yes": rr.ALIVE_YES, "no_max": rr.NO_MAX, "starve_n": STARVE_N, "send_latency_s": 1,
         "no99_removed_while_resting": True, "walk": "walk_july (rr.walk minus the top-price exclusion)",
         "rail_as_live": {"day_stop": DAY_STOP, "max_resting": MAX_RESTING, "max_collateral": MAX_COLLATERAL_V2},
         "models": list(MODELS) + ["latent"], "x99_lookback_s": X99_LOOKBACK, "pile": [PILE_LO, PILE_HI, PILE_MIN],
         "gap_max_s": GAP_MAX_S, "variants": {"exit": VARIANT_EXITS, "size": VARIANT_SIZES, "early_join": True},
         "paper_only": True}


# ------------------------------------------------------------------------------------------------ writes: ONE gate
def _inside_results(path):
    full, root = os.path.abspath(path), os.path.abspath(RESULTS)
    try:
        return os.path.commonpath([full, root]) == root
    except ValueError:
        return False


def _open_w(path, mode="a"):
    """The only place this file opens anything for writing. Refuses every path outside results/."""
    full = os.path.abspath(path)
    if not _inside_results(full):
        raise PermissionError("racev2_shadow writes only under results/: %s" % full)
    if mode == "wb":
        return open(full, mode)
    if mode not in ("a", "w"):
        raise ValueError("mode %r" % mode)
    return open(full, mode, encoding="utf-8")


def _remove_own(path):
    """Delete one of this file's own temporary files (self-test), only under results/."""
    full = os.path.abspath(path)
    if os.path.commonpath([full, os.path.abspath(RESULTS)]) == os.path.abspath(RESULTS) and os.path.isfile(full):
        os.remove(full)


class Log:
    def __init__(self, path, mode):
        self.path, self.mode = path, mode
        self.fh = _open_w(path, "a")

    def write(self, ev, **kw):
        r = {"t": rr.utc_iso(time.time()), "ev": ev, "mode": self.mode}
        r.update(kw)
        self.fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
        self.fh.flush()
        return r

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass


def iter_rows(path, needles=None):
    """Stream a jsonl log; with `needles`, only lines containing one of them are parsed (the log grows ~1.5 MB a day,
    so nothing reads it whole into memory)."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if needles is not None and not any(n in line for n in needles):
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    pass
    except OSError:
        return


def read_rows(path, needles=None):
    return list(iter_rows(path, needles))


def save_json(path, obj):
    tmp = path + ".tmp"
    with _open_w(tmp, "w") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    _open_w(path, "a").close()           # asserts the target path too
    for i in range(10):                  # Windows: a scanner can hold a just-written file for a moment
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.3)


def file_sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------ time
def hour_ts(h):
    return datetime.strptime(h, "%Y%m%dT%H").replace(tzinfo=timezone.utc).timestamp()


def hour_str(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%dT%H")


def next_hour(h):
    return hour_str(hour_ts(h) + 3600)


def et_dt(t):
    return datetime.fromtimestamp(t, timezone.utc) + timedelta(hours=rr.et_offset_h(t))


def race_day(close):
    """The ET day a race belongs to (its last second, so a race closing at 00:00 ET is the day before's)."""
    return rr.et_day(close - 1)


def et_block(close):
    h = et_dt(close - 1).hour // 4 * 4
    return "%02d-%02d" % (h, h + 4)


def et_midnight_utc(day):
    """UTC timestamp of 00:00 ET on `day` (YYYY-MM-DD); EDT/EST decided by rr.et_offset_h at that instant."""
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    t = base + 4 * 3600
    return t if rr.et_offset_h(t) == -4 else base + 5 * 3600


def day_bounds(day):
    nxt = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return et_midnight_utc(day), et_midnight_utc(nxt)


def close_from_ticker(tk):
    """FALLBACK ONLY (the API close is the one scored): the ticker's time is the close in ET local time. Ambiguous
    01:00-02:00 ET on the November change reads as EDT; a leg whose close came from here is never scored."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?:-|$)", tk)
    if not m or m.group(2) not in MON:
        return None
    loc = datetime(2000 + int(m.group(1)), MON.index(m.group(2)) + 1, int(m.group(3)), int(m.group(4)),
                   int(m.group(5)), tzinfo=timezone.utc).timestamp()
    return loc + 4 * 3600 if rr.et_offset_h(loc + 4 * 3600) == -4 else loc + 5 * 3600


# ------------------------------------------------------------------------------------------------ the July walk
def walk_july(levels, target, df, ours=0.0, our_px=0.01, linear=True):
    """rr.walk (the filing's walk) with ONE change: no 'highest bid must be under the highest possible price'
    exclusion, which the July 2026 filing removed. Everything else -- whole levels best-first, Reference at target/5,
    stop at target, df ** ticks below the Reference -- is rr.walk's code, line for line (the self-test compares)."""
    lv = {p: s for p, s in levels.items() if s > 0}
    if ours > 0:
        k = round(our_px, 4)
        lv[k] = lv.get(k, 0.0) + ours
    pxs = sorted(lv, reverse=True)
    if not pxs:
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
    s_all = sum(df ** rr.ticks_between(ref, p, linear) * lv[p] for p in used)
    s_us = 0.0
    if ours > 0 and any(abs(p - our_px) < 1e-9 for p in used):
        s_us = df ** rr.ticks_between(ref, our_px, linear) * ours
    return {"q": True, "ref": ref, "tot": tot, "share": (s_us / s_all) if s_all > 0 else 0.0}


def snapshot_july(yes_others, no_lv, ours, prog, linear=True):
    """rr.snapshot with walk_july (same rounding of the share to 5 dp as the bot's snapshot)."""
    y = walk_july(yes_others, prog["target"], prog["df"], ours=ours, linear=linear)
    n = walk_july(no_lv, prog["target"], prog["df"], linear=linear)
    ok = bool(y["q"] and n["q"])
    return {"ok": ok, "sh": round(y["share"], 5) if ok else 0.0}


def count_for_v2(prog):
    """Spec section 3 item 3: min(COUNT_CAP 1,100, round(target) + CUSHION 100)."""
    return int(min(COUNT_CAP, max(1, round(prog["target"]) + CUSHION)))


def projection(d, yes_d, no_d, count, t, exit_s):
    """rr.Bot.floor_check's arithmetic, line for line, with the v2 exit: (exit - now - 2 s) x share now x reward /
    (2 x period), the end clipped to the program's end and the start to its start."""
    sn = rr.snapshot(yes_d, no_d, count, d.prog, d.linear)
    end = d.close - exit_s
    if d.prog.get("end"):
        end = min(end, d.prog["end"])
    start = max(t, d.prog.get("start") or t)
    secs = max(0.0, end - start - rr.FLOOR_MARGIN_S)
    return rr.credit(d.prog["reward"], rr.period_of(d.prog), secs * sn["sh"])


# ------------------------------------------------------------------------------------------------ tape
def stream_lines(fp, diag, needle=b"CRYPTOLEAD"):
    """extract.py's stream_lines, plus: multi-member gzip read to the end; every error counted, never raised."""
    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buf = b""
    with open(fp, "rb") as fh:
        while True:
            try:
                chunk = fh.read(1 << 19)
            except Exception:
                diag["read_error"] += 1
                break
            if not chunk:
                break
            pieces, err = [], False
            try:
                pieces.append(dec.decompress(chunk))
                while dec.eof and dec.unused_data:
                    rest = dec.unused_data
                    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    diag["gzip_members_extra"] += 1
                    pieces.append(dec.decompress(rest))
            except Exception:
                diag["corrupt_tail"] += 1
                err = True
            lines = (buf + b"".join(pieces)).split(b"\n")
            buf = lines.pop()
            for ln in lines:
                if needle in ln:
                    yield ln
            if err:
                break
    if buf and needle in buf:
        yield buf


class TapeSource:
    """The real tape, read-only."""

    def __init__(self, root=TAPE):
        self.root = root

    def path(self, ch, h):
        return os.path.join(self.root, ch, h + ".jsonl.gz")

    def exists(self, h):
        return os.path.exists(self.path("orderbook_delta", h))

    def lines(self, ch, h, diag):
        fp = self.path(ch, h)
        if not os.path.exists(fp):
            diag["missing_" + ch] += 1
            return iter(())
        return stream_lines(fp, diag)


def px_of(s):
    """(price in dollars, whole_cent) from a *_dollars field; None if unreadable. Never rescaled (hard rule 5)."""
    try:
        p = round(float(s), 4)
    except (TypeError, ValueError):
        return None, False
    return p, abs(p * 100.0 - round(p * 100.0)) <= 1e-6


def sells_yes(msg, diag):
    """True if the taker SOLD YES (hit a YES bid). taker_outcome_side, else taker_book_side, else taker_side."""
    a, b, c = msg.get("taker_outcome_side"), msg.get("taker_book_side"), msg.get("taker_side")
    va = None if a not in ("yes", "no") else a == "no"
    vb = None if b not in ("bid", "ask") else b == "ask"
    vc = None if c not in ("yes", "no") else c == "no"
    vals = [v for v in (va, vb, vc) if v is not None]
    if len(set(vals)) > 1:
        diag["trade_side_fields_disagree"] += 1
    for v in (va, vb, vc):
        if v is not None:
            return v
    return None


class LegBook:
    __slots__ = ("tk", "evt", "coin", "close", "close_src", "yes", "no", "valid", "sid", "seq", "rec", "sold",
                 "neg1c", "add99", "rem99", "gap_max", "nwc")

    def __init__(self, tk, close, close_src):
        self.tk, self.close, self.close_src = tk, close, close_src
        self.evt, _, self.coin = tk.rpartition("-")
        self.yes, self.no, self.valid, self.sid, self.seq = {}, {}, False, None, -1
        self.rec = [None] * (REC_MAX + 1)
        self.sold, self.neg1c, self.add99, self.rem99 = (defaultdict(float), defaultdict(float),
                                                          defaultdict(float), defaultdict(float))
        self.gap_max, self.nwc = 0, 0

    def flow(self, name, sec, x):
        L = int(self.close - sec)
        if -5 <= L <= REC_MAX + 5:
            getattr(self, name)[L] += x


def _trunc(levels, cum_key=None):
    out, cum = [], 0.0
    for p, s in levels:
        out.append((p, s))
        if cum_key is None or cum_key(p):
            cum += s
        if cum >= KEEP_CUM or len(out) >= KEEP_LEVELS:
            break
    return tuple(out)


def summarize(leg):
    """The state at the start of a second: (others' YES levels desc, YES total, YES 1c, NO levels desc, NO total)."""
    ylv = sorted(((p, s) for p, s in leg.yes.items() if s > 0), reverse=True)
    nlv = sorted(((p, s) for p, s in leg.no.items() if s > 0), reverse=True)
    return (_trunc(ylv), round(sum(s for _, s in ylv), 2), round(leg.yes.get(0.01, 0.0), 2),
            _trunc(nlv, lambda p: p < 0.99 - 1e-9), round(sum(s for _, s in nlv), 2))


class Rebuilder:
    """extract.py's run_day loop as an object that lives across hours: one global second clock driven by the coin-race
    deltas; at each new second every valid leg with 0..400 s left records its state as of the start of that second."""

    def __init__(self, close_lookup):
        self.close_lookup = close_lookup
        self.legs, self.done, self.gsec = {}, [], None
        self.final_tks, self.no_close = {}, set()

    def leg(self, tk, diag):
        lg = self.legs.get(tk)
        if lg is None:
            close, src = self.close_lookup(tk)
            if close is None:
                if tk not in self.no_close:
                    self.no_close.add(tk)
                    diag["leg_close_unknown"] += 1
                return None
            lg = self.legs[tk] = LegBook(tk, close, src)
        return lg

    def _levels(self, rows, lg, diag):
        d = {}
        for row in rows or []:
            try:
                p, ok = px_of(row[0])
                s = round(float(row[1]), 2)
            except (TypeError, ValueError, IndexError):
                diag["bad_snapshot_level"] += 1
                continue
            if p is None:
                continue
            if not ok:
                diag["non_whole_cent"] += 1
                lg.nwc += 1
            if s > 0:
                d[p] = round(d.get(p, 0.0) + s, 2)
        return d

    def _snapshot(self, rx, sid, seq, msg, diag):
        tk = msg.get("market_ticker") or ""
        if tk in self.final_tks:
            return
        lg = self.leg(tk, diag)
        if lg is None:
            return
        if "yes_dollars_fp" in msg or "no_dollars_fp" in msg:
            lg.yes = self._levels(msg.get("yes_dollars_fp"), lg, diag)
            lg.no = self._levels(msg.get("no_dollars_fp"), lg, diag)
            if lg.valid:
                diag["re_snapshot"] += 1
            lg.valid, lg.sid, lg.seq = True, sid, seq
        elif rx / 1000.0 < lg.close - 1:
            diag["empty_snap_midlife"] += 1
            if lg.yes or lg.no:
                diag["empty_snap_wiped_book"] += 1
            lg.yes, lg.no, lg.valid, lg.sid, lg.seq = {}, {}, True, sid, seq

    def _advance(self, sec, diag):
        if self.gsec is None:
            self.gsec = sec
            return
        if sec <= self.gsec:
            return
        jump = sec - self.gsec
        if jump > 1:
            diag["silence_max_s"] = max(diag.get("silence_max_s", 0), jump)
            for lg in self.legs.values():
                if self.gsec + 1 <= lg.close and sec - 1 >= lg.close - REC_MAX:
                    lg.gap_max = max(lg.gap_max, jump)
        steps = range(self.gsec + 1, sec + 1) if jump < 4000 else (sec,)
        for lg in self.legs.values():
            if not lg.valid:
                continue
            snap = None
            for s in steps:
                L = int(lg.close - s)
                if 0 <= L <= REC_MAX:
                    if snap is None:
                        snap = summarize(lg)
                    lg.rec[L] = snap
        self.gsec = sec
        for tk in [tk for tk, lg in self.legs.items() if lg.close < self.gsec - 2]:
            self.done.append(self.legs.pop(tk))
            self.final_tks[tk] = self.gsec
        if len(self.final_tks) > 400:
            for tk in sorted(self.final_tks, key=self.final_tks.get)[:200]:
                del self.final_tks[tk]

    def process_hour(self, src, h):
        diag = Counter()
        if not src.exists(h):
            diag["missing_hour"] = 1
            return diag
        for ln in src.lines("trade", h, diag):
            try:
                msg = json.loads(ln)["msg"]
            except Exception:
                diag["bad_trade_line"] += 1
                continue
            tk = msg.get("market_ticker") or ""
            if not tk.startswith(TK_PREFIX) or tk in self.final_tks:
                continue
            diag["trades"] += 1
            sold = sells_yes(msg, diag)
            if sold is None:
                diag["trade_side_unknown"] += 1
                continue
            p, ok = px_of(msg.get("yes_price_dollars"))
            if not sold or p is None or p > 0.0100 + 1e-9:
                continue
            lg = self.leg(tk, diag)
            if lg is None:
                continue
            if not ok:
                diag["non_whole_cent"] += 1
                lg.nwc += 1
            n = rr.f(msg.get("count_fp"), rr.f(msg.get("count"), 0.0)) or 0.0
            try:
                sec = int(msg.get("ts_ms")) // 1000
            except (TypeError, ValueError):
                diag["trade_no_ts"] += 1
                continue
            lg.flow("sold", sec, n)
            diag["trades_1c"] += 1
            diag["sold_1c"] += n
        snaps = []
        for ln in src.lines("orderbook_snapshot", h, diag):
            try:
                m = json.loads(ln)
                msg = m["msg"]
            except Exception:
                diag["bad_snapshot_line"] += 1
                continue
            if str(msg.get("market_ticker", "")).startswith(TK_PREFIX):
                snaps.append((m.get("_rx_ms") or 0, m.get("seq") or 0, m.get("sid"), msg))
        snaps.sort(key=lambda x: (x[0], x[1]))
        si = 0
        for ln in src.lines("orderbook_delta", h, diag):
            try:
                m = json.loads(ln)
            except Exception:
                diag["bad_delta_line"] += 1
                continue
            rx = m.get("_rx_ms") or 0
            while si < len(snaps) and snaps[si][0] <= rx:
                self._snapshot(snaps[si][0], snaps[si][2], snaps[si][1], snaps[si][3], diag)
                si += 1
            d = m.get("msg") or {}
            tk = d.get("market_ticker") or ""
            if not tk.startswith(TK_PREFIX):
                continue
            diag["coin_lines"] += 1
            ts = d.get("ts_ms")
            if ts is None:
                diag["delta_no_ts"] += 1
                continue
            sec = int(ts) // 1000
            self._advance(sec, diag)
            if tk in self.final_tks:
                diag["delta_after_final"] += 1
                continue
            lg = self.leg(tk, diag)
            if lg is None:
                continue
            if not lg.valid:
                diag["delta_before_snapshot"] += 1
                continue
            sid, seq = m.get("sid"), m.get("seq") or 0
            if sid == lg.sid and seq <= lg.seq:
                diag["delta_older_than_snapshot"] += 1
                continue
            p, ok = px_of(d.get("price_dollars"))
            dl = rr.f(d.get("delta_fp"), None)
            side = d.get("side")
            if p is None or dl is None or side not in ("yes", "no"):
                diag["bad_delta"] += 1
                continue
            if not ok:
                diag["non_whole_cent"] += 1
                lg.nwc += 1
            bk = lg.yes if side == "yes" else lg.no
            v = round(bk.get(p, 0.0) + dl, 2)
            if v <= 0:
                if v < -0.005:
                    diag["negative_level"] += 1
                bk.pop(p, None)
            else:
                bk[p] = v
            if side == "yes" and abs(p - 0.01) < 1e-9 and dl < 0:
                lg.flow("neg1c", sec, -dl)
            elif side == "no" and abs(p - 0.99) < 1e-9:
                if dl > 0:
                    lg.flow("add99", sec, dl)
                elif dl < 0:
                    lg.flow("rem99", sec, -dl)
        while si < len(snaps):
            self._snapshot(snaps[si][0], snaps[si][2], snaps[si][1], snaps[si][3], diag)
            si += 1
        return diag

    def take_done(self):
        d, self.done = self.done, []
        return d


# ------------------------------------------------------------------------------------------------ our own v2 orders
class OwnOrders:
    """results/racereward-v2-live.jsonl (v1 field names: placed{evt,coin,left,body.count}, fill{filled,left},
    cancelled{left,sent_left}, expired, ...). An optional exchange-time fill row ('exchange_fill' {evt, coin,
    filled, created_time}) is preferred over the poll-time 'fill' rows when present."""

    def __init__(self, path):
        self.path, self.sig, self.by_tk = path, None, {}

    def get(self, tk):
        self._load()
        return self.by_tk.get(tk)

    def _load(self):
        try:
            st = os.stat(self.path)
        except OSError:
            self.by_tk, self.sig = {}, None
            return
        sig = (st.st_size, st.st_mtime)
        if sig == self.sig:
            return
        by = {}
        for r in read_rows(self.path):
            evt, coin, ev = r.get("evt"), r.get("coin") or r.get("c"), r.get("ev")
            if not evt or not coin:
                continue
            o = by.setdefault("%s-%s" % (evt, coin), {"placed_left": None, "count": None, "fills": [], "xfills": [],
                                                      "off_left": None, "off_why": None})
            if ev == "placed" and o["placed_left"] is None:
                o["placed_left"] = rr.f(r.get("left"))
                o["count"] = rr.f((r.get("body") or {}).get("count"), rr.f(r.get("count")))
            elif ev == "fill":
                o["fills"].append((rr.f(r.get("left"), 0.0), rr.f(r.get("filled"), 0.0)))
            elif ev == "exchange_fill":
                o["xfills"].append((rr.f(r.get("left"), 0.0), rr.f(r.get("filled"), 0.0)))
            elif ev in OFF_EVENTS and o["off_left"] is None:
                o["off_left"] = rr.f(r.get("sent_left"), rr.f(r.get("left")))
                o["off_why"] = "%s:%s" % (ev, r.get("why"))
        self.by_tk = {k: v for k, v in by.items() if v["placed_left"] is not None and v["count"]}
        self.sig = sig


def own_remaining(o, L, lag=0.0):
    """Our remaining size on the book at the start of second L (None when not resting). lag > 0 counts fills logged
    up to `lag` seconds later (the poll lag of 'fill' rows)."""
    if o is None or not (L < o["placed_left"] and L > (o["off_left"] if o["off_left"] is not None else 0.0)):
        return None
    rows = o["xfills"] or o["fills"]
    done = max([fl for left, fl in rows if left > L - lag] or [0.0])
    return max(0.0, o["count"] - done)


def apply_own(b, o):
    """Subtract our resting size from the tape's 1c YES level (rr.others_of). True if it would have gone negative
    outside the placement/off edges and the fill-poll lag (the leg is then flagged and not scored)."""
    negative = False
    for L in range(REC_MAX + 1):
        r = b.rec[L]
        rem = own_remaining(o, L)
        if r is None or not rem:
            continue
        y1 = r[2]
        edge = abs(L - o["placed_left"]) <= OWN_EDGE_S or (o["off_left"] is not None
                                                           and abs(L - o["off_left"]) <= OWN_EDGE_S)
        if y1 + 0.5 < rem and not edge:
            lagged = own_remaining(o, L, lag=OWN_POLL_LAG_S) or 0.0
            if y1 + 0.5 < lagged:
                negative = True
        yo = rr.others_of(dict(r[0]), rem)
        ylv = tuple(sorted(((p, s) for p, s in yo.items() if s > 0), reverse=True))
        b.rec[L] = (ylv, round(sum(s for _, s in ylv), 2), round(yo.get(0.01, 0.0), 2), r[3], r[4])
    return negative


# ------------------------------------------------------------------------------------------------ public GETs
class PublicGet:
    """Unauthenticated GET only (no key, no signature, no request body). >= 2.0 s between calls; 429 -> 10 s."""

    def __init__(self, spacing=CALL_SPACING_S, clock=time.time, sleep=time.sleep):
        self.spacing, self.clock, self.sleep = spacing, clock, sleep
        self.last, self.calls, self.bytes, self.errors, self.n429 = -1e18, 0, 0, 0, 0

    def __call__(self, path, params):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for _ in range(4):
            wait = self.spacing - (self.clock() - self.last)
            if wait > 0:
                self.sleep(wait)
            self.last = self.clock()
            self.calls += 1
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:
                    raw = r.read()
                    self.bytes += len(raw)
                    return r.status, json.loads(raw.decode() or "{}")
            except urllib.error.HTTPError as e:
                if e.code == 429:              # the per-IP limit is shared with the live bots: back off, never push
                    self.n429 += 1
                    self.sleep(BACKOFF_429_S)
                    continue
                self.errors += 1
                return e.code, None
            except Exception:
                self.errors += 1
                return -1, None
        return 429, None


def parse_program(p):
    """(ticker, program) from one /incentive_programs row; program None if a field is unreadable (never assumed)."""
    tk = str(p.get("market_ticker") or "")
    if not tk.startswith(TK_PREFIX):
        return None, None
    rw, tg, df = rr.f(p.get("period_reward")), rr.f(p.get("target_size_fp")), rr.f(p.get("discount_factor_bps"))
    if rw is None or tg is None or df is None or str(p.get("incentive_type", "liquidity")) != "liquidity":
        return tk, None
    return tk, {"reward": rw / 10000.0, "target": tg, "df": df / 10000.0, "start": rr.parse_ts(p.get("start_date")),
                "end": rr.parse_ts(p.get("end_date")), "id": p.get("id")}


def fetch_programs(http, statuses, want=None, max_pages=FALLBACK_PAGES, older_than=None):
    """older_than: stop paging a status once EVERY program on a page (any market, not only coin-race ones, so the rule
    still works if Kalshi stops listing coin-race programs) ended before it. The listings are newest-first; the
    margin is set by the caller (1 day before the oldest close looked up). Bounds the worst case to a few pages an
    hour instead of 12 + 12 of ~1.9 MB."""
    out, ok, pages = {}, True, 0
    for st in statuses:
        cur = None
        for _ in range(max_pages):
            q = {"status": st, "type": "liquidity", "limit": PROGRAM_PAGE}
            if cur:
                q["cursor"] = cur
            code, b = http("/incentive_programs", q)
            pages += 1
            if code != 200 or not isinstance(b, dict):
                ok = False
                break
            rows = b.get("incentive_programs") or []
            ends = []
            for p in rows:
                e = rr.parse_ts(p.get("end_date"))
                if e is not None:
                    ends.append(e)
                tk, pr = parse_program(p)
                if pr:
                    out[tk] = pr
            cur = b.get("next_cursor") or b.get("cursor")
            if not cur or not rows or (want is not None and want <= set(out)):
                break
            if older_than is not None and ends and max(ends) < older_than:
                break
        if want is not None and want <= set(out):
            break
    return out, ok, pages


def fetch_markets(http, lo, hi):
    out, cur, ok = {}, None, True
    for _ in range(5):
        q = {"series_ticker": SERIES, "min_close_ts": int(lo), "max_close_ts": int(hi), "limit": 200}
        if cur:
            q["cursor"] = cur
        code, b = http("/markets", q)
        if code != 200 or not isinstance(b, dict):
            ok = False
            break
        for m in b.get("markets") or []:
            tk, cs = str(m.get("ticker") or ""), rr.parse_ts(m.get("close_time"))
            if not tk.startswith(TK_PREFIX) or cs is None:
                continue
            res = m.get("result")
            out[tk] = {"close": cs, "result": res if res in ("yes", "no") else None,
                       "pls": m.get("price_level_structure"),
                       "linear": m.get("price_level_structure") in (None, "linear_cent")}
        cur = b.get("cursor")
        if not cur:
            break
    return out, ok


# ------------------------------------------------------------------------------------------------ the replay
class LegData:
    """One leg ready to simulate: its per-second states (others only), flows by L, program, close, result."""
    __slots__ = ("tk", "coin", "close", "result", "prog", "linear", "rec", "sold", "neg1c", "add99", "rem99")

    def __init__(self, tk, close, result, prog, linear, rec, sold, neg1c, add99, rem99):
        self.tk, self.coin, self.close, self.result, self.prog, self.linear = tk, tk.rpartition("-")[2], close, \
            result, prog, linear
        self.rec, self.sold, self.neg1c, self.add99, self.rem99 = rec, sold, neg1c, add99, rem99

    def rem3(self, L):
        return sum(self.rem99.get(L + k, 0.0) for k in range(X99_LOOKBACK + 1))


class _S:
    __slots__ = ("d", "z", "placed", "q", "q0", "rem", "filled", "ss", "counted", "run", "starved", "cancel", "off",
                 "on", "refusals", "proj", "rest_s", "n99", "new99", "rule_diff")

    def __init__(self, d, z):
        self.d, self.z = d, z
        self.placed, self.q, self.q0, self.rem, self.filled, self.ss, self.counted = None, 0.0, None, float(z),             0.0, 0.0, 0
        self.run, self.starved, self.cancel, self.off, self.on = 0, 0, None, None, False
        self.refusals, self.proj, self.rest_s, self.n99, self.new99, self.rule_diff = Counter(), None, 0, 0, 0.0, 0

    def stop(self, why, L):
        self.on, self.cancel, self.off = False, why, L

    def summary(self):
        cr = rr.credit(self.d.prog["reward"], rr.period_of(self.d.prog), self.ss) if self.placed is not None else 0.0
        paid = rr.floored(PAID_FACTOR * cr)
        res = self.d.result
        signed = None if res is None else round(self.filled * (0.99 if res == "yes" else -0.01), 4)
        return {"placed_left": self.placed, "proj": None if self.proj is None else round(self.proj, 5),
                "queue": self.q0, "filled": round(self.filled, 2),
                "credit": round(cr, 6), "paid": round(paid, 6), "cost_cons": round(0.01 * self.filled, 4),
                "pnl_signed": signed, "cancel": self.cancel, "off_left": self.off, "counted_s": self.counted,
                "share_s": round(self.ss, 5), "starved_s": self.starved, "rest_s": self.rest_s,
                "refusals": dict(self.refusals), "n99_s": self.n99, "new99": round(self.new99, 2),
                "rule_diff_s": self.rule_diff, "size": self.z}


def fill_step(model, s, L):
    d, rem = s.d, s.rem
    if rem <= 1e-9 or model == "none":
        return 0.0
    sold = d.sold.get(L, 0.0)
    if model == "high":
        return min(rem, sold)
    if model in ("low", "mid"):
        take = min(s.q, sold)
        s.q -= take
        f = min(rem, sold - take)
        if model == "mid":
            s.q = max(0.0, s.q - max(0.0, d.neg1c.get(L, 0.0) - sold))
        return f
    add = d.add99.get(L, 0.0)
    if model in ("x99", "x99g"):
        fh = min(rem, sold)
        extra = add if model == "x99g" else max(0.0, add - d.rem3(L))
        if extra > 0:
            s.n99 += 1
            s.new99 += extra
        return fh + min(rem - fh, extra)
    if model in ("ej_mid", "ej_x99"):
        flow = sold + (max(0.0, add - d.rem3(L)) if model == "ej_x99" else 0.0)
        take = min(s.q, flow)
        s.q -= take
        f = min(rem, flow - take)
        s.q = max(0.0, s.q - max(0.0, d.neg1c.get(L, 0.0) - sold))
        return f
    raise ValueError(model)


class Rail:
    """rail (f) exactly as rr.Bot.rails_refusal / check_day_stop, v2 caps. State per (model, ET day)."""

    def __init__(self):
        self.realized = defaultdict(float)
        self.halted = set()

    def refusal(self, model, count, t, sts):
        d = rr.et_day(t)
        if (model, d) in self.halted:
            return "day_stop"
        resting = [s for s in sts if s.on]
        if len(resting) >= MAX_RESTING:
            return "max_resting"
        rest_c = sum(0.01 * s.rem for s in resting)
        unset = sum(0.01 * s.filled for s in sts)
        if rest_c + unset + 0.01 * count > MAX_COLLATERAL_V2 + 1e-9:
            return "max_collateral"
        if self.realized[(model, d)] - unset - rest_c - 0.01 * count < DAY_STOP - 1e-9:
            return "day_budget"
        return None

    def day_stop(self, model, t, sts):
        d = rr.et_day(t)
        if (model, d) in self.halted:
            return False
        if self.realized[(model, d)] - sum(0.01 * s.filled for s in sts) <= DAY_STOP + 1e-9:
            self.halted.add((model, d))
            return True
        return False

    def settle(self, model, sts, close):
        """rr.Bot.settle: pnl = (filled if YES) - cost, booked to the close's ET day; unknown result = lost."""
        d = rr.et_day(close)
        delta = sum((s.filled if s.d.result == "yes" else 0.0) - 0.01 * s.filled for s in sts if s.filled > 0)
        self.realized[(model, d)] += delta
        return d, round(delta, 4)


def simulate_race(legs, model, exit_s=EXIT_S, size=None, floor=POST_FLOOR, starve_n=STARVE_N, rail=None,
                  early_join=False, check_rule=False):
    """One world: the v2 rule on these legs (one race) under one fill model. rail=None is the `open` rail."""
    sts = [_S(d, count_for_v2(d.prog) if size is None else int(size)) for d in legs]
    if not sts:
        return {}, sts
    close = legs[0].close
    for L in range(WINDOW, int(exit_s), -1):
        t = close - L
        for s in sts:                                   # (1) cancels, on the state at L, before crediting
            if not s.on or s.placed <= L:
                continue
            r = s.d.rec[L]
            if r is None:
                continue
            if r[0] and r[0][0][0] > rr.ALIVE_YES + 1e-9:
                s.stop("alive", L)
                continue
            if r[1] + s.rem < s.d.prog["target"] - 1e-9:
                s.run += 1
                s.starved += 1
                if starve_n and s.run >= starve_n:
                    s.stop("starved", L)
            else:
                s.run = 0
        for s in sts:                                   # (2) placements (each coin at most once per race)
            if s.placed is not None:
                continue
            r = s.d.rec[L]
            if r is None:
                s.refusals["no_book"] += 1
                continue
            yes_d, no_d = dict(r[0]), dict(r[3])
            why = rr.leg_refusal(yes_d, no_d, s.d.prog["target"], s.d.linear)
            if why == "yes_side_full" and early_join:          # behind the pile: (b) relaxed, (c)/(d) still apply
                why = rr.leg_refusal({}, no_d, s.d.prog["target"], s.d.linear)
            if why:
                s.refusals[why] += 1
                continue
            proj = projection(s.d, yes_d, no_d, s.z, t, exit_s)
            if proj < floor - 1e-9:
                s.refusals["under_floor"] += 1
                continue
            if rail is not None:
                w = rail.refusal(model, s.z, t, sts)
                if w:
                    s.refusals["rail_" + w] += 1
                    continue
            s.placed, s.q, s.q0, s.proj, s.on = L, r[2], round(r[2], 2), proj, True
        for s in sts:                                   # (3) credit this second, then this second's fills
            if not s.on or s.placed <= L:
                continue
            r = s.d.rec[L]
            if r is None:
                continue
            s.rest_s += 1
            yes_d = dict(r[0])
            no_sc = {p: v for p, v in r[3] if p < 0.99 - 1e-9}
            sn = snapshot_july(yes_d, no_sc, s.rem, s.d.prog, s.d.linear)
            if sn["ok"]:
                s.ss += sn["sh"]
                s.counted += 1
            if check_rule:
                o = rr.snapshot(yes_d, no_sc, s.rem, s.d.prog, s.d.linear)
                if o["ok"] != sn["ok"] or abs(o["sh"] - sn["sh"]) > 1e-12:
                    s.rule_diff += 1
            f = fill_step(model, s, L)
            if f > 0:
                s.rem = round(s.rem - f, 4)
                s.filled = round(s.filled + f, 4)
        if rail is not None and rail.day_stop(model, t, sts):
            for s in sts:
                if s.on:
                    s.stop("day_stop", L)
    for s in sts:
        if s.on:
            s.stop("exit", int(exit_s))
    return {s.d.tk: s.summary() for s in sts}, sts


def static_leg(d):
    """Model-free reads of one leg: dead at 300, first postable second, latent pile seconds/sales, the incumbent pull,
    and flows for the control comparison."""
    tg = d.prog["target"] if d.prog else 1000.0
    r300 = d.rec[300]
    dead300 = bool(r300 is not None and (not r300[0] or r300[0][0][0] <= rr.DEAD_YES + 1e-9))
    first = None
    for L in range(WINDOW, EXIT_S, -1):
        r = d.rec[L]
        if r is not None and rr.leg_refusal(dict(r[0]), dict(r[3]), tg, d.linear) is None:
            first = L
            break
    pile_s, pile_sold = 0, 0.0
    for L in range(PILE_LO, PILE_HI + 1):
        r = d.rec[L]
        if r is None or (r[0] and r[0][0][0] > rr.DEAD_YES + 1e-9) or r[2] < PILE_MIN - 1e-9:
            continue
        pile_s += 1
        pile_sold += min(PILE_MIN, d.sold.get(L, 0.0))
    pull = None
    for L in range(REC_MAX - 1, EXIT_S, -1):
        a, b = d.rec[L + 1], d.rec[L]
        if a is None or b is None or a[2] < tg - 1e-9 or b[2] >= tg - 1e-9:
            continue
        drop = a[2] - b[2]
        canc = max(0.0, d.neg1c.get(L + 1, 0.0) - d.sold.get(L + 1, 0.0))
        if drop > 0 and canc >= 0.5 * drop:
            pull = {"pull_left": L, "pile": a[2], "sold_30_before": round(sum(d.sold.get(L + k, 0.0) for k in range(1, 31)), 2),
                    "sold_30_after": round(sum(d.sold.get(L - k, 0.0) for k in range(0, 30)), 2)}
            break
    fl = {"s": 0, "sold1c": 0.0, "add99": 0.0, "new99": 0.0}
    for L in range(WINDOW, EXIT_S, -1):
        r = d.rec[L]
        if r is None or (r[0] and r[0][0][0] > rr.DEAD_YES + 1e-9) or r[1] >= tg - 1e-9:
            continue
        fl["s"] += 1
        fl["sold1c"] += d.sold.get(L, 0.0)
        fl["add99"] += d.add99.get(L, 0.0)
        fl["new99"] += max(0.0, d.add99.get(L, 0.0) - d.rem3(L))
    return {"dead_at_300": dead300, "first_postable_left": first, "pile_s": pile_s, "pile_sold": round(pile_sold, 2),
            "pile_pull": pull, "flow": {k: round(v, 2) for k, v in fl.items()}}


def flow_over(d, lo, hi):
    """1c sales and 99c adds over integer seconds lo < L < hi (a live resting window)."""
    fl = {"s": 0, "sold1c": 0.0, "add99": 0.0, "new99": 0.0}
    for L in range(int(hi), int(lo), -1):
        if not (lo < L < hi) or d.rec[L] is None:
            continue
        fl["s"] += 1
        fl["sold1c"] += d.sold.get(L, 0.0)
        fl["add99"] += d.add99.get(L, 0.0)
        fl["new99"] += max(0.0, d.add99.get(L, 0.0) - d.rem3(L))
    return {k: round(v, 2) for k, v in fl.items()}


def _vsum(res, keys=("placed_left", "paid", "filled", "starved_s", "cancel")):
    return {k: res.get(k) for k in keys}


# ------------------------------------------------------------------------------------------------ the runner
def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            s = json.load(fh)
        if isinstance(s, dict) and s.get("next_hour"):
            s.setdefault("programs", {})
            s.setdefault("prog_t", -1e18)
            return s
    except (OSError, ValueError):
        pass
    return None


def mem_mb():
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(c)
        k32, ps = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        if ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return round(c.WorkingSetSize / 1e6, 1), round(c.PeakWorkingSetSize / 1e6, 1)
    except Exception:
        pass
    return None, None


def recorder_ages(now):
    """Recorder liveness by READING file ages only (never touched). python.exe command lines are blank to a
    Get-CimInstance query from this user session (checked 2026-10-17), so the process list cannot name them."""
    out = {}
    for name, d in (("collector_delta", os.path.join(TAPE, "orderbook_delta")),
                    ("collector_index", os.path.join(TAPE, "cfbenchmarks_value")),
                    ("feeds_coinbase", os.path.join(FEEDS, "coinbase"))):
        age = None
        for h in (hour_str(now), hour_str(now - 3600)):
            try:
                age = round(now - os.stat(os.path.join(d, h + ".jsonl.gz")).st_mtime)
                break
            except OSError:
                continue
        out[name] = age
    out["ok"] = all(v is not None and v < RECORDER_STALE_S for v in out.values())
    out["method"] = "file_mtime"
    return out


class Runner:
    def __init__(self, mode, log_path, state_path, source=None, http=None, clock=time.time, sleep=time.sleep,
                 live_log=LIVE_V2_LOG, out=print, checks=True):
        self.mode, self.log_path, self.state_path = mode, log_path, state_path
        self.src = source or TapeSource()
        self.http = http or PublicGet(clock=clock, sleep=sleep)
        self.clock, self.sleep, self.out, self.checks = clock, sleep, out, checks
        self.own = OwnOrders(live_log)
        self.state = (load_state(state_path) if state_path else None) or {}
        self.fresh = not self.state
        self.programs = dict(self.state.get("programs") or {})
        self.searched, self.minfo = set(), {}
        self.mkt_searched = set()            # tickers a SUCCESSFUL targeted /markets call was asked about
        self.deferred, self.defer_n = {}, Counter()   # evt -> books of a race held back by a failed lookup
        self.rb = Rebuilder(self._close_lookup)
        rows = read_rows(log_path, ('"ev":"race"', '"ev":"day"', '"ev":"hour_done"'))
        self.logged = {r["evt"] for r in rows if r.get("ev") == "race"}
        self.days_done = {r["day"] for r in rows if r.get("ev") == "day"}
        self.pending_days = {r["race_day"] for r in rows if r.get("ev") == "race"} - self.days_done
        self.rail = Rail()
        for r in rows:
            if r.get("ev") != "race":
                continue
            for m, a in (r.get("as_live") or {}).items():
                if a.get("book_day"):
                    self.rail.realized[(m, a["book_day"])] += float(a.get("realized_delta") or 0.0)
                if a.get("halted_day"):
                    self.rail.halted.add((m, a["halted_day"]))
        self.hours_ok = {r["hour"] for r in rows if r.get("ev") == "hour_done" and not r.get("missing")}
        self.log = Log(log_path, mode)
        self.empty_run = 0
        self.coin_total = 0
        self.processed = 0

    # ---- inputs
    def _close_lookup(self, tk):
        mi = self.minfo.get(tk)
        if mi:
            return mi["close"], "api"
        return close_from_ticker(tk), "ticker"

    def refresh_programs(self, force=False):
        now = self.clock()
        if not force and now - float(self.state.get("prog_t", -1e18)) < PROGRAM_REFRESH_S:
            return None
        got, ok, pages = fetch_programs(self.http, ("active", "upcoming"))
        self.programs.update(got)
        self.state["prog_t"] = now
        return {"ok": ok, "pages": pages, "coinrace": len(got)}

    def ensure_programs(self, tks):
        """The closed / paid_out listings for tickers no program row was seen for. A ticker counts as SEARCHED (and
        its race as genuinely programs-missing) only after a listing that did not fail; a failed listing leaves it
        unsearched, so its race is held back and retried (lookup_failed), never logged programs-missing."""
        miss = {tk for tk in tks if tk not in self.programs and tk not in self.searched}
        if not miss:
            return None
        closes = [c for c in ((self.minfo.get(tk) or {}).get("close") or close_from_ticker(tk) for tk in miss) if c]
        older = (min(closes) - FALLBACK_STOP_MARGIN_S) if closes else None
        got, ok, pages = fetch_programs(self.http, ("closed", "paid_out"), want=miss, older_than=older)
        self.programs.update(got)
        if ok:
            self.searched |= miss
        return {"ok": ok, "pages": pages, "wanted": len(miss), "found": len(miss & set(got))}

    def load_markets(self, h):
        t0 = hour_ts(h)
        got, ok = fetch_markets(self.http, t0 - 900, t0 + 3600 + 900)
        self.minfo.update(got)
        # kept long enough for a race held back DEFER_TRIES hours by a failed lookup
        for tk in [tk for tk, v in self.minfo.items() if v["close"] < t0 - (DEFER_TRIES + 3) * 3600]:
            del self.minfo[tk]
        return ok, len(got)

    def ensure_markets(self, races):
        """A leg the hourly /markets window did not return (that call failed, or the leg was first seen before it):
        ONE /markets call over just these races' closes (+-1 h: a ticker close can be an hour off on the November
        change). A ticker counts as asked only after a call that did not fail; a market the API never lists is then
        close_unverified (never scored), and a failed call holds the race back for a retry (lookup_failed)."""
        need = [b for books in races for b in books if b.tk not in self.minfo and b.tk not in self.mkt_searched]
        if not need:
            return None
        lo, hi = min(b.close for b in need), max(b.close for b in need)
        got, ok = fetch_markets(self.http, lo - 3600 - 120, hi + 3600 + 120)
        self.minfo.update(got)
        if ok:
            self.mkt_searched |= {b.tk for b in need}
        return {"ok": ok, "wanted": len(need), "found": sum(1 for b in need if b.tk in got)}

    def lookup_failed(self, books):
        """Why this race's inputs are unknown because OUR lookup failed (not because Kalshi lacks them)."""
        why = []
        if any(b.tk not in self.programs and b.tk not in self.searched for b in books):
            why.append("program_lookup_failed")
        if any(b.tk not in self.minfo and b.tk not in self.mkt_searched for b in books):
            why.append("markets_lookup_failed")
        return why

    def prune_programs(self, h):
        lim = hour_ts(h) - 3 * 86400
        for tk in [tk for tk, p in self.programs.items() if (p.get("end") or 0) < lim]:
            del self.programs[tk]

    # ---- one race
    def finalise_race(self, evt, books):
        order = {c: i for i, c in enumerate(COINS)}
        books = sorted(books, key=lambda b: (order.get(b.coin, 99), b.tk))
        close = books[0].close
        info = []
        lf = self.lookup_failed(books)
        for b in books:
            mi = self.minfo.get(b.tk)
            tape = []
            if mi and b.close_src != "api" and abs(mi["close"] - b.close) <= 0.5:
                b.close_src = "api_checked"      # opened on the ticker's close; the API confirmed it before scoring
            if not mi or b.close_src not in ("api", "api_checked"):
                tape.append("close_unverified")
            if not b.valid:
                tape.append("never_valid")
            elif any(b.rec[L] is None for L in range(MIN_L, WINDOW + 1)):
                tape.append("missing_seconds")
            if b.gap_max > GAP_MAX_S:
                tape.append("gap")
            if b.nwc:
                tape.append("non_whole_cent")
            own = self.own.get(b.tk)
            if own and b.valid and apply_own(b, own):
                tape.append("own_sub_negative")
            prog = self.programs.get(b.tk)
            plf = prog is None and b.tk not in self.searched      # our listing failed: unknown, not missing
            reasons = tape + ([] if prog else (["program_lookup_failed"] if plf else []) + ["no_program"])
            d = LegData(b.tk, close, (mi or {}).get("result"), prog, (mi or {}).get("linear", True), b.rec,
                        dict(b.sold), dict(b.neg1c), dict(b.add99), dict(b.rem99))
            info.append({"b": b, "d": d, "tape": tape, "reasons": reasons, "own": own, "prog": prog, "plf": plf})
        clean = len(books) == 5 and all(not x["tape"] for x in info)
        # 'programs missing' (gate line 3) = Kalshi listed no program after a listing that did NOT fail
        prog_missing = any(x["prog"] is None and not x["plf"] for x in info)
        scored_race = clean and not any(x["prog"] is None for x in info) and len(books) == 5
        sc = [x["d"] for x in info if not x["reasons"]]
        worlds = {}
        if sc:
            for m in MODELS:
                worlds[m] = simulate_race(sc, m, check_rule=(m == "x99"))[0]
                worlds["ns_" + m] = simulate_race(sc, m, starve_n=None)[0]
            for e in VARIANT_EXITS:
                for m in ("high", "x99"):
                    worlds["exit%d_%s" % (e, m)] = simulate_race(sc, m, exit_s=e)[0]
            for z in VARIANT_SIZES:
                for m in ("high", "x99"):
                    worlds["size%d_%s" % (z, m)] = simulate_race(sc, m, size=z)[0]
            for m in ("ej_mid", "ej_x99"):
                worlds[m] = simulate_race(sc, m, early_join=True)[0]
        live = {}
        if scored_race:
            for m in RAIL_MODELS:
                res, sts = simulate_race(sc, m, rail=self.rail)
                book_day, delta = self.rail.settle(m, sts, close)
                halted = sorted(dd for (mm, dd) in self.rail.halted if mm == m and dd in (rr.et_day(close - WINDOW),
                                                                                       rr.et_day(close)))
                live[m] = {"res": res, "book_day": book_day, "realized_delta": delta,
                           "halted_day": halted[-1] if halted else None}
        posted_any = any(x["own"] for x in info)
        rd, blk = race_day(close), et_block(close)
        every3 = (int((close % 86400) // 60) // 15) % 3 == 0
        leg_rows = []
        for x in info:
            b, d = x["b"], x["d"]
            row = {"evt": evt, "tk": b.tk, "coin": b.coin, "close": rr.utc_iso(close)[:19] + "Z", "race_day": rd,
                   "block": blk, "et_hour": et_dt(close - 1).hour, "every3": every3, "close_src": b.close_src,
                   "result": d.result, "program": None if not x["prog"] else
                   {k: x["prog"].get(k) for k in ("reward", "target", "df", "id")},
                   "scored": not x["reasons"], "unscored_why": x["reasons"], "gap_max_s": b.gap_max,
                   "non_whole_cent": b.nwc, "posted_live": bool(x["own"]),
                   "flow_all": {"sold1c": round(sum(v for L, v in d.sold.items() if 0 <= L <= REC_MAX), 2),
                                "neg1c": round(sum(v for L, v in d.neg1c.items() if 0 <= L <= REC_MAX), 2),
                                "add99": round(sum(v for L, v in d.add99.items() if 0 <= L <= REC_MAX), 2),
                                "rem99": round(sum(v for L, v in d.rem99.items() if 0 <= L <= REC_MAX), 2)}}
            if x["own"]:
                o = x["own"]
                fl = max([v for _, v in (o["xfills"] or o["fills"])] or [0.0])
                row["live"] = {"filled": fl, "cost": round(0.01 * fl, 4), "placed_left": o["placed_left"],
                               "off_left": o["off_left"], "off_why": o["off_why"],
                               "flow_live": flow_over(d, o["off_left"] or 0.0, o["placed_left"])}
            if row["scored"]:
                row.update(static_leg(d))
                mx = worlds["x99"][b.tk]
                row["placed_left"] = mx["placed_left"]
                row["proj_at_place"] = mx["proj"]
                row["queue_ahead"] = mx["queue"]
                row["why_not_placed"] = None if mx["placed_left"] is not None else \
                    (max(mx["refusals"], key=mx["refusals"].get) if mx["refusals"] else "none")
                row["refusals"] = mx["refusals"]
                row["models"] = {m: {k: worlds[m][b.tk][k] for k in ("filled", "credit", "paid", "cost_cons",
                                                                     "pnl_signed", "cancel", "off_left", "counted_s",
                                                                     "share_s", "starved_s", "rest_s")}
                                 for m in MODELS}
                row["credit_model"], row["paid_model"] = mx["credit"], mx["paid"]
                row["floor_ok"] = mx["paid"] > 0
                row["fills"] = {"low": worlds["low"][b.tk]["filled"], "mid": worlds["mid"][b.tk]["filled"],
                                "high": worlds["high"][b.tk]["filled"], "x99_gross": worlds["x99g"][b.tk]["filled"],
                                "x99": mx["filled"], "latent": None}
                row["fills_nostarve"] = {"low": worlds["ns_low"][b.tk]["filled"], "mid": worlds["ns_mid"][b.tk]["filled"],
                                         "high": worlds["ns_high"][b.tk]["filled"],
                                         "x99_gross": worlds["ns_x99g"][b.tk]["filled"],
                                         "x99": worlds["ns_x99"][b.tk]["filled"]}
                row["paid_nostarve_high"] = worlds["ns_high"][b.tk]["paid"]
                row["latent_rest_s"] = worlds["high"][b.tk]["rest_s"]
                row["starved_s"], row["n99_adds_s"], row["new99"] = mx["starved_s"], mx["n99_s"], mx["new99"]
                row["rule_diff_s"] = mx["rule_diff_s"]
                row["size"] = mx["size"]
                row["variants"] = {}
                for e in VARIANT_EXITS:
                    h_, x_ = worlds["exit%d_high" % e][b.tk], worlds["exit%d_x99" % e][b.tk]
                    row["variants"]["exit%d" % e] = {"placed_left": x_["placed_left"], "paid_high": h_["paid"],
                                                     "fills_high": h_["filled"], "paid_x99": x_["paid"],
                                                     "fills_x99": x_["filled"], "starved_s_x99": x_["starved_s"]}
                for z in VARIANT_SIZES:
                    h_, x_ = worlds["size%d_high" % z][b.tk], worlds["size%d_x99" % z][b.tk]
                    row["variants"]["size%d" % z] = {"placed_left": x_["placed_left"], "paid_high": h_["paid"],
                                                     "fills_high": h_["filled"], "paid_x99": x_["paid"],
                                                     "fills_x99": x_["filled"], "starved_s_x99": x_["starved_s"]}
                em, ex = worlds["ej_mid"][b.tk], worlds["ej_x99"][b.tk]
                row["variants"]["early_join"] = {"placed_left": em["placed_left"], "paid_mid": em["paid"],
                                                 "credit_mid": em["credit"], "fills_mid": em["filled"],
                                                 "paid_x99": ex["paid"], "fills_x99": ex["filled"]}
                row["control"] = bool(posted_any and not x["own"] and row["first_postable_left"] is not None)
                if live:
                    row["as_live"] = {m: _vsum(live[m]["res"][b.tk], ("placed_left", "paid", "filled", "cost_cons",
                                                                      "cancel")) for m in RAIL_MODELS}
            leg_rows.append(row)
        for row in leg_rows:
            self.log.write("leg", **row)
        drop = None
        if not scored_race:
            if len(books) != 5:
                drop = "legs_missing"
            else:
                for w in ("never_valid", "missing_seconds", "gap", "non_whole_cent", "close_unverified",
                          "own_sub_negative", "program_lookup_failed", "no_program"):
                    if any(w in x["reasons"] for x in info):
                        drop = w
                        break
        placed = [r for r in leg_rows if r.get("placed_left") is not None]
        race = {"evt": evt, "close": rr.utc_iso(close)[:19] + "Z", "race_day": rd, "block": blk, "every3": every3,
                "legs_seen": len(books), "clean": clean, "programs_missing": prog_missing, "scored": scored_race,
                "drop_why": drop, "lookup_failed": lf, "deferred_hours": self.defer_n.get(evt, 0),
                "placed_open": len(placed) if scored_race else None,
                "paid_open": {m: round(sum(r["models"][m]["paid"] for r in placed), 5) for m in MODELS}
                if scored_race else None,
                "cost_open": {m: round(sum(r["models"][m]["cost_cons"] for r in placed), 4) for m in MODELS}
                if scored_race else None,
                "as_live": {m: {"placed": sum(1 for v in live[m]["res"].values() if v["placed_left"] is not None),
                                "paid": round(sum(v["paid"] for v in live[m]["res"].values()), 5),
                                "cost_cons": round(sum(v["cost_cons"] for v in live[m]["res"].values()), 4),
                                "book_day": live[m]["book_day"], "realized_delta": live[m]["realized_delta"],
                                "halted_day": live[m]["halted_day"]} for m in live} or None,
                "posted_live": posted_any}
        self.log.write("race", **race)
        self.logged.add(evt)
        self.pending_days.add(rd)
        return race

    # ---- one hour
    def do_hour(self, h, reread=False):
        t0 = self.clock()
        c0, b0, q0 = self.http.calls, self.http.bytes, getattr(self.http, "n429", 0)
        pr = self.refresh_programs()
        # an hour with no file costs no /markets call (its legs, if any, carry a > 60 s gap and are never scored)
        mok, mn = self.load_markets(h) if self.src.exists(h) else (None, 0)
        diag = self.rb.process_hour(self.src, h)
        done = self.rb.take_done()
        by_evt = defaultdict(dict)
        for b in done:
            by_evt[b.evt][b.tk] = b
        for evt, books in self.deferred.items():          # races held back by a failed lookup: retried. A held book
            for b in books:                               # was complete when held; it wins over one a re-read (after
                by_evt[evt][b.tk] = b                     # an error) rebuilt from a later hour -- never two per leg
        groups = {e: list(v.values()) for e, v in by_evt.items()}
        todo = [e for e in groups if e not in self.logged]
        fb = self.ensure_programs([b.tk for e in todo for b in groups[e]])
        fm = self.ensure_markets([groups[e] for e in todo])
        fin = skipped = scored = placed = held = 0
        for evt in sorted(groups, key=lambda e: groups[e][0].close):
            if evt in self.logged:
                skipped += 1
                self.deferred.pop(evt, None)
                continue
            if self.lookup_failed(groups[evt]) and self.defer_n[evt] < DEFER_TRIES:
                self.deferred[evt] = groups[evt]
                self.defer_n[evt] += 1
                held += 1
                continue
            self.deferred.pop(evt, None)
            r = self.finalise_race(evt, groups[evt])
            fin += 1
            scored += 1 if r["scored"] else 0
            placed += r["placed_open"] or 0
        self.prune_programs(h)
        coin = diag.get("coin_lines", 0)
        self.coin_total += coin
        # an hour with NO FILE neither counts toward nor resets the 12-empty-hours stop (a 24 h outage is a missing
        # stretch, not 'loaded nothing'); an hour whose file exists but holds no coin-race line counts
        self.empty_run = 0 if coin else (self.empty_run if diag.get("missing_hour") else self.empty_run + 1)
        rss, peak = mem_mb()
        now = self.clock()
        try:
            disk = round(shutil.disk_usage(REPO).free / 1e9, 1)
        except OSError:
            disk = None
        missing = bool(diag.get("missing_hour"))
        row = {"hour": h, "reread": reread, "missing": missing, "coin_lines": coin, "legs_live": len(self.rb.legs),
               "legs_finalised": len(done), "races_finalised": fin, "races_scored": scored, "placed_open": placed,
               "races_skipped_logged": skipped, "races_held": held, "held_now": sorted(self.deferred),
               "empty_run": self.empty_run, "diag": dict(diag), "programs_refresh": pr, "programs_fallback": fb,
               "markets_ok": mok, "markets_n": mn, "markets_fallback": fm,
               "calls": self.http.calls - c0, "bytes": self.http.bytes - b0,
               "http_429": getattr(self.http, "n429", 0) - q0,
               "elapsed_s": round(now - t0, 1), "rss_mb": rss, "peak_mb": peak, "disk_free_gb": disk,
               "recorders": recorder_ages(now) if self.checks else None}
        self.log.write("hour_done", **row)
        if not missing:
            self.hours_ok.add(h)
        self.out("racev2_shadow hour %s%s: coin lines %d, races %d (scored %d, placed legs %d, skipped %d), calls %d, "
                 "rss %s MB" % (h, " (re-read)" if reread else "", coin, fin, scored, placed, skipped,
                                row["calls"], rss), flush=True)
        self.maybe_days(h)
        if not reread:
            self.state["next_hour"] = next_hour(h)
            self.processed += 1
        self.state.setdefault("covered_from", h)
        self.state["programs"] = self.programs
        if self.state_path:
            save_json(self.state_path, self.state)
        return row

    def maybe_days(self, h):
        t = hour_ts(h)
        held = {race_day(books[0].close) for books in self.deferred.values()}
        for D in sorted(self.pending_days - self.days_done):
            if t < day_bounds(D)[1] or D in held:          # a day row waits for its held races
                continue
            rows = read_rows(self.log_path, ('"race_day":"%s"' % D,))
            s = day_summary(rows, D, self.hours_ok)
            self.log.write("day", **s)
            self.days_done.add(D)
            self.out("racev2_shadow day %s: races scored %d of %d seen, placed/race %s, x99 cost/paid %s, full %s"
                     % (D, s["races_scored"], s["races_seen"], s["placed_per_race"],
                        s["open"]["x99"]["ratio"], s["full"]), flush=True)

    def hour_ready(self, h, now):
        """Hour h is closed once the clock is past h+1:02 AND a LATER hour's delta file exists -- normally h+1, but any
        later hour counts, so a whole missing hour (PC off, collector down: 20261015T08, 20261014T04..20261015T03 on
        the real tape) is processed as missing instead of stalling the cursor forever. A missing h itself is ready the
        same way (do_hour logs it `missing`, and the day it touches can never be `full`)."""
        if now < hour_ts(h) + 3600 + HOUR_GRACE_S:
            return False
        t = hour_ts(h) + 3600
        while t <= now:
            if self.src.exists(hour_str(t)):
                return True
            t += 3600
        return False

    def guards(self):
        rss, peak = mem_mb()
        if peak is not None and peak > MEM_LIMIT_MB:
            return "memory peak %.0f MB > %.0f MB" % (peak, MEM_LIMIT_MB)
        try:
            if shutil.disk_usage(REPO).free / 1e9 < DISK_MIN_GB:
                return "free disk under %.0f GB" % DISK_MIN_GB
        except OSError:
            pass
        return None

    # ---- modes
    def start(self, argv, since):
        if self.fresh:
            self.state = {"next_hour": since, "covered_from": since, "programs": self.programs, "prog_t": -1e18}
        self.log.write("start", pid=os.getpid(), argv=argv, code_sha=file_sha(os.path.abspath(__file__)),
                       rr_sha=file_sha(os.path.abspath(rr.__file__)), rules=RULES, next_hour=self.state["next_hour"],
                       fresh=self.fresh, races_logged=len(self.logged), log=self.log_path, state=self.state_path)

    def flush_deferred(self):
        """At any stop, and at the end of a backfill: every race still held back by a failed lookup is logged with
        that failure (lookup_failed, drop_why program_lookup_failed / close_unverified), so a race seen on the tape
        always gets a row and is never counted as programs-missing."""
        n = 0
        for evt in sorted(self.deferred, key=lambda e: self.deferred[e][0].close):
            if evt not in self.logged:
                self.finalise_race(evt, self.deferred[evt])
                n += 1
        self.deferred.clear()
        return n

    def follow(self, hours_limit, stop_path=STOP, max_hours=None, once=False):
        try:
            return self._follow(hours_limit, stop_path, max_hours, once)
        finally:
            try:
                n = self.flush_deferred()
                if n:
                    self.log.write("held_flushed", races=n)
            except Exception as e:
                self.log.write("error", where="flush_deferred", err=repr(e)[:300])

    def _follow(self, hours_limit, stop_path, max_hours, once):
        t_end = self.clock() + hours_limit * 3600.0
        need_reread = not self.fresh
        errors = 0
        last_wait = self.clock()
        while True:
            if need_reread:
                # books carry across hours: (re)build them from the hour before the cursor; races already in the log
                # are skipped, so this never writes a second row for a race
                need_reread = False
                try:
                    self.do_hour(hour_str(hour_ts(self.state["next_hour"]) - 3600), reread=True)
                except Exception as e:
                    errors += 1
                    self.log.write("error", where="reread", err=repr(e)[:300], errors=errors)
                    self.rb, need_reread = Rebuilder(self._close_lookup), True
                    if errors >= 20:
                        self.log.write("stop", why="20 errors")
                        return 5
                    self.sleep(60)
                    continue
            if os.path.exists(stop_path):
                self.log.write("stop", why="stop file", path=stop_path)
                self.out("racev2_shadow: stop file present; exiting", flush=True)
                return 0
            if self.clock() >= t_end:
                self.log.write("stop", why="hours elapsed")
                return 0
            g = self.guards() if self.checks else None
            if g:
                self.log.write("stop", why=g)
                self.out("racev2_shadow: STOPPING -- %s" % g, flush=True)
                return 3
            h = self.state["next_hour"]
            if self.hour_ready(h, self.clock()):
                try:
                    self.do_hour(h)
                except Exception as e:
                    # the books may hold half an hour: drop them and re-read from the hour before the cursor (which
                    # did not advance); a hard fault repeats, so 20 errors in a run stop it
                    errors += 1
                    self.log.write("error", where="hour", hour=h, err=repr(e)[:300], errors=errors)
                    self.out("racev2_shadow: error in hour %s: %r -- re-reading" % (h, e), flush=True)
                    self.rb, need_reread = Rebuilder(self._close_lookup), True
                    if errors >= 20:
                        self.log.write("stop", why="20 errors")
                        return 5
                    self.sleep(60)
                    continue
                if self.empty_run >= EMPTY_HOURS_STOP:
                    self.log.write("stop", why="%d closed hours with no coin-race line" % self.empty_run)
                    print("racev2_shadow: loaded nothing from the tape for %d consecutive closed hours -- stopping"
                          % self.empty_run, flush=True)
                    return 4
                if once or (max_hours is not None and self.processed >= max_hours):
                    if self.coin_total == 0:
                        self.log.write("stop", why="loaded nothing")
                        print("racev2_shadow: loaded nothing (no coin-race delta line in the hours read) -- stopping",
                              flush=True)
                        return 4
                    self.log.write("stop", why="max hours" if max_hours is not None else "once")
                    return 0
                self.sleep(PACE_S)
                continue
            if once or max_hours is not None:
                self.log.write("stop", why="no closed hour ready", next_hour=h)
                return 0
            if self.clock() - last_wait >= 6 * 3600:
                last_wait = self.clock()
                self.log.write("waiting", next_hour=h)
            for _ in range(12):
                if os.path.exists(stop_path):
                    break
                self.sleep(5)

    def run_hours(self, hours):
        """Process an explicit list of hours in order (backfill; self-test)."""
        for h in hours:
            self.do_hour(h)
        if self.flush_deferred() and hours:
            self.maybe_days(hours[-1])
        if self.coin_total == 0:
            self.log.write("stop", why="loaded nothing")
            print("racev2_shadow: loaded nothing (no coin-race delta line in the hours read) -- stopping", flush=True)
            return 4
        self.log.write("stop", why="hours done")
        return 0


# ------------------------------------------------------------------------------------------------ day rows, report
def _ratio(c, p):
    return round(c / p, 4) if p else None


def _agg(placed, model):
    paid = sum(r["models"][model]["paid"] for r in placed)
    cost = sum(r["models"][model]["cost_cons"] for r in placed)
    rat = sorted((r["models"][model]["cost_cons"] / r["models"][model]["paid"]) if r["models"][model]["paid"] > 0
                 else (99.0 if r["models"][model]["cost_cons"] > 0.005 else 0.0) for r in placed)
    return {"legs": len(placed), "paid": round(paid, 5), "cost_cons": round(cost, 4), "ratio": _ratio(cost, paid),
            "median_leg_ratio": round(rat[len(rat) // 2], 4) if rat else None, "net": round(paid - cost, 4),
            "filled": round(sum(r["models"][model]["filled"] for r in placed), 2),
            "legs_filled": sum(1 for r in placed if r["models"][model]["filled"] > 0)}


def day_summary(rows, D, hours_ok):
    legs = [r for r in rows if r.get("ev") == "leg" and r.get("race_day") == D]
    races = [r for r in rows if r.get("ev") == "race" and r.get("race_day") == D]
    scored = {r["evt"] for r in races if r.get("scored")}
    clean = [r for r in races if r.get("clean")]
    L = [r for r in legs if r["evt"] in scored]
    placed = [r for r in L if r.get("placed_left") is not None]
    pile_s = sum(r.get("pile_s", 0) for r in L)
    pile_sold = sum(r.get("pile_sold", 0.0) for r in L)
    rate = (pile_sold / pile_s) if pile_s else 0.0
    # gate line 3's base: clean races whose program lookup did NOT fail (a failed listing is our failure, not a
    # missing program; it is counted separately and printed next to the share)
    known = [r for r in clean if "program_lookup_failed" not in (r.get("lookup_failed") or [])]
    start, end = day_bounds(D)
    expected = int(round((end - start) / 900.0))          # 96; 92 / 100 on the clock-change days
    closes = {r.get("close") for r in races}
    out = {"day": D, "races_seen": len(races), "races_clean": len(clean), "races_scored": len(scored),
           "races_expected": expected, "races_unseen": max(0, expected - len(closes)),
           "dropped": dict(Counter(r.get("drop_why") for r in races if not r.get("scored"))),
           "races_lookup_failed": sum(1 for r in races if r.get("lookup_failed")),
           "races_programs_known": len(known),
           "programs_missing_races": sum(1 for r in known if r.get("programs_missing")),
           "programs_missing_share": _ratio(sum(1 for r in known if r.get("programs_missing")), len(known)),
           "placed_open": len(placed), "placed_per_race": _ratio(len(placed), len(scored)),
           "open": {m: _agg(placed, m) for m in MODELS}}
    lat_cost = sum(0.01 * min(r.get("size", COUNT_CAP), rate * r.get("latent_rest_s", 0)) for r in placed)
    lat_paid = out["open"]["high"]["paid"]
    out["open"]["latent"] = {"legs": len(placed), "paid": lat_paid, "cost_cons": round(lat_cost, 4),
                             "ratio": _ratio(lat_cost, lat_paid), "net": round(lat_paid - lat_cost, 4),
                             "filled": round(lat_cost / 0.01, 2)}
    out["latent"] = {"pile_s": pile_s, "pile_sold": round(pile_sold, 2), "rate_per_s": round(rate, 6),
                     "per_170s_window": round(rate * 170, 2), "ref_refute_exec_rate_per_s": REF_LATENT_RATE,
                     "ref_tester_per_window": REF_LATENT_WINDOW}
    out["x99_cost_over_high_paid"] = _ratio(out["open"]["x99"]["cost_cons"], out["open"]["high"]["paid"])
    ns_cost = sum(0.01 * (r.get("fills_nostarve") or {}).get("x99", 0.0) for r in placed)
    ns_paid = sum(r.get("paid_nostarve_high", 0.0) for r in placed)
    out["x99_nostarve_cost_over_high_paid"] = _ratio(ns_cost, ns_paid)
    al = defaultdict(lambda: {"placed": 0, "paid": 0.0, "cost_cons": 0.0})
    for r in races:
        if r.get("scored") and r.get("as_live"):
            for m, a in r["as_live"].items():
                al[m]["placed"] += a["placed"]
                al[m]["paid"] += a["paid"]
                al[m]["cost_cons"] += a["cost_cons"]
    out["as_live"] = {m: {"placed": v["placed"], "paid": round(v["paid"], 5), "cost_cons": round(v["cost_cons"], 4),
                          "net": round(v["paid"] - v["cost_cons"], 4)} for m, v in sorted(al.items())}

    def sub(pred):
        ev = {r["evt"] for r in races if r.get("scored") and pred(r)}
        pl = [r for r in placed if r["evt"] in ev]
        return {"races": len(ev), "placed": len(pl), "x99": _agg(pl, "x99"), "high": _agg(pl, "high")}
    out["block_00_04"] = sub(lambda r: r.get("block") == "00-04")
    out["halves"] = {"first": sub(lambda r: (et_dt(rr.parse_ts(r["close"]) - 1).hour < 12)),
                     "second": sub(lambda r: (et_dt(rr.parse_ts(r["close"]) - 1).hour >= 12))}
    out["every3"] = sub(lambda r: r.get("every3"))
    need = {hour_str(t) for t in range(int(start) - 3600, int(end) + 1, 3600)}
    out["hours_missing"] = sorted(need - set(hours_ok))
    out["full"] = not out["hours_missing"]
    return out


def gate(days):
    """4.1 on the first 3 full ET days (open rails, conservative cost). Returns (verdict, reasons, numbers).
    The programs-missing line is read FIRST, on clean races whose program lookup did not fail: a missing program also
    takes its race out of the scored count, so reading that line only after the 250-scored-race floor would turn its
    HOLD into NOT_READY whenever more than ~13% of races miss a program."""
    n = {"days": [d["day"] for d in days], "races_scored": sum(d["races_scored"] for d in days),
         "races_clean": sum(d["races_clean"] for d in days),
         "races_programs_known": sum(d.get("races_programs_known", d["races_clean"]) for d in days),
         "races_lookup_failed": sum(d.get("races_lookup_failed", 0) for d in days),
         "races_unseen": sum(d.get("races_unseen", 0) for d in days),
         "programs_missing_races": sum(d["programs_missing_races"] for d in days),
         "placed": sum(d["placed_open"] for d in days),
         "x99_paid": round(sum(d["open"]["x99"]["paid"] for d in days), 4),
         "x99_cost": round(sum(d["open"]["x99"]["cost_cons"] for d in days), 4),
         "high_paid": round(sum(d["open"]["high"]["paid"] for d in days), 4)}
    n["x99_ratio"] = _ratio(n["x99_cost"], n["x99_paid"])
    n["x99_cost_over_high_paid"] = _ratio(n["x99_cost"], n["high_paid"])
    n["placed_per_race"] = _ratio(n["placed"], n["races_scored"])
    n["programs_missing_share"] = _ratio(n["programs_missing_races"], n["races_programs_known"])
    if len(days) < 3:
        return "NOT_READY", ["need 3 full ET days (have %d)" % len(days)], n
    why = []
    if (n["programs_missing_share"] or 0.0) > 0.05:
        why.append("programs missing on %s of races > 5%%" % n["programs_missing_share"])
    if n["races_scored"] < 250 or not n["races_clean"]:
        if why:
            return "HOLD", why + ["only %d scored races (< 250), so the cost and placement lines are not read"
                                  % n["races_scored"]], n
        return "NOT_READY", ["need 3 full ET days and >= 250 scored races (have %d days, %d races)"
                             % (len(days), n["races_scored"])], n
    if n["x99_ratio"] is None or n["x99_ratio"] > 0.70:
        why.append("x99 cost %s of paid-model credit > 70%%" % n["x99_ratio"])
    if (n["placed_per_race"] or 0.0) < 0.7:
        why.append("placed legs %s per race < 0.7" % n["placed_per_race"])
    return ("HOLD" if why else "RECOMMEND_LIVE_TEST"), why, n


def report(log_path=LOG, days=3, out=print, mode="follow"):
    rows = read_rows(log_path, ('"ev":"day"', '"posted_live":true', '"control":true'))
    dayrows = sorted((r for r in rows if r.get("ev") == "day" and r.get("mode") == mode), key=lambda r: r["day"])
    out("racev2_shadow report: %s" % log_path)
    out("ET day      full  races seen/clean/scored  placed/race  x99 paid  x99 cost  x99 cost/paid  high cost/paid  "
        "latent cost/paid  00-04 x99 cost/paid  prog-missing  unseen  lookup-failed")
    for d in dayrows:
        o = d["open"]
        out("%s  %-5s %5d/%5d/%6d     %9s  %8.2f  %8.2f  %13s  %14s  %16s  %19s  %12s  %6s  %s" % (
            d["day"], d["full"], d["races_seen"], d["races_clean"], d["races_scored"], d["placed_per_race"],
            o["x99"]["paid"], o["x99"]["cost_cons"], o["x99"]["ratio"], o["high"]["ratio"], o["latent"]["ratio"],
            d["block_00_04"]["x99"]["ratio"], d["programs_missing_share"], d.get("races_unseen"),
            d.get("races_lookup_failed")))
    full = [d for d in dayrows if d.get("full")][:days]
    verdict, why, n = gate(full)
    out("4.1 PAPER GATE (pre-registered 2026-10-16): HOLD if x99 cost > 70% of paid-model credit, OR placed legs < 0.7 "
        "per race, OR programs missing on > 5% of races; read after the first 3 full ET days (>= 250 scored races).")
    out("  first %d full days %s: races scored %d, placed/race %s, x99 cost $%.2f / paid $%.2f = %s (vs high-world "
        "paid %s), programs missing %s (of %d clean races with a program listing read; listing failed on %d races; "
        "%d quarter-hours with no race on the tape)"
        % (len(full), n["days"], n["races_scored"], n["placed_per_race"], n["x99_cost"], n["x99_paid"], n["x99_ratio"],
           n["x99_cost_over_high_paid"], n["programs_missing_share"], n["races_programs_known"],
           n["races_lookup_failed"], n["races_unseen"]))
    out("  VERDICT: %s%s" % (verdict, (" -- " + "; ".join(why)) if why else ""))
    out("  The gate cannot PASS the idea; only live fills can (4.2, read by racereward_live v2 --report).")
    posted = [r for r in rows if r.get("ev") == "leg" and r.get("mode") == mode and r.get("posted_live")
              and r.get("scored")]
    if not posted:
        out("4.3 calibration: no v2 live leg in this log yet.")
        return 0
    live_c = sum(r["live"]["cost"] for r in posted)
    out("4.3 calibration on %d posted legs: live fill cost $%.2f vs tape low $%.2f / mid $%.2f / high $%.2f / x99 $%.2f"
        % (len(posted), live_c, *(sum(r["models"][m]["cost_cons"] for r in posted) for m in ("low", "mid", "high", "x99"))))
    ctl = [r for r in rows if r.get("ev") == "leg" and r.get("mode") == mode and r.get("control")]
    ps = sum(r["live"]["flow_live"]["s"] for r in posted)
    pf = sum(r["live"]["flow_live"]["sold1c"] + r["live"]["flow_live"]["new99"] for r in posted)
    cs = sum(r["flow"]["s"] for r in ctl)
    cf = sum(r["flow"]["sold1c"] + r["flow"]["new99"] for r in ctl)
    out("  flow per resting second: posted %s (%d s) vs controls %s (%d s); > 2x means sellers target our bid"
        % (_ratio(pf, ps), ps, _ratio(cf, cs), cs))
    return 0


def compare_dry(log_path, dry_path, out=print, mode="follow", tol_s=3.0):
    """Spec section 2 'paper_mode': before live, racereward_live v2 --dry-run's would_place decisions must match the
    shadow's on the same legs (placed or not, placement within 3 s) on >= 90% of legs, else a bug is found first.
    Compared against the shadow's as_live world with NO fills (a dry run's rail (f) never sees a fill). Races = those
    with a 'race' row in the dry log (the v1 dry log writes one per prepared race); legs = the shadow's scored legs."""
    dry = read_rows(dry_path, ('"race"', '"would_place"'))
    races = {r.get("evt") for r in dry if r.get("ev") == "race"}
    rows = [r for r in iter_rows(log_path, ('"ev":"leg"',)) if r.get("evt") in races]
    wp = {}
    for r in dry:
        if r.get("ev") == "would_place" and r.get("evt") and r.get("coin"):
            wp.setdefault("%s-%s" % (r["evt"], r["coin"]), rr.f(r.get("left")))
    legs = [r for r in rows if r.get("ev") == "leg" and r.get("mode") == mode and r.get("scored")
            and r.get("evt") in races and r.get("as_live")]
    agree, diffs = 0, []
    for r in legs:
        dl, sl = wp.get(r["tk"]), r["as_live"]["none"]["placed_left"]
        ok = (dl is None and sl is None) or (dl is not None and sl is not None and abs(dl - sl) <= tol_s)
        agree += 1 if ok else 0
        if not ok:
            diffs.append((r["tk"], sl, dl))
    share = (agree / len(legs)) if legs else None
    verdict = "NO_OVERLAP" if not legs else ("MATCH" if share >= 0.90 - 1e-9 else "BUG_FIRST")
    out("dry-run vs shadow (as_live, no fills): %d of %d legs agree (%s) in %d races -> %s (bar: >= 90%%)"
        % (agree, len(legs), None if share is None else round(share, 4), len({r["evt"] for r in legs}), verdict))
    for x in diffs[:20]:
        out("  differs: %s shadow placed_left %s, dry would_place left %s" % x)
    return verdict, share


# ------------------------------------------------------------------------------------------------ self-test
class _World:
    """A planted tape, as JSON lines by channel and UTC hour, plus the API's programs and markets for it."""

    def __init__(self):
        self.items = {"trade": [], "orderbook_snapshot": [], "orderbook_delta": []}
        self.programs, self.markets = {}, {}
        self.n = 0

    def _add(self, ch, rx_ms, obj):
        self.n += 1
        self.items[ch].append((rx_ms, self.n, obj))

    @staticmethod
    def ticker_time(close):
        dt = et_dt(close)
        return "%02d%s%02d%02d%02d" % (dt.year % 100, MON[dt.month - 1], dt.day, dt.hour, dt.minute)

    def race(self, close, legs, program=True, silence=None, omit_market=(), suffix=""):
        """legs: {coin: {"yes": {px: n}, "no": {px: n}, "events": [...], "result": "no"}}. events:
        ("d", L, side, px_str, delta) -> a delta in the second with L left (visible from L-1);
        ("t", L, n, yes_px_str, fields) -> a trade in that second. silence = (lo, hi): no delta in seconds with
        lo <= L <= hi left."""
        evt = "%s-%s%s" % (SERIES, self.ticker_time(close), suffix)
        first = None
        for coin, sp in legs.items():
            tk = "%s-%s" % (evt, coin)
            first = first or tk
            if coin not in omit_market:
                self.markets[tk] = {"ticker": tk, "close_time": rr.utc_iso(close)[:19] + "Z",
                                    "result": sp.get("result", "no"), "price_level_structure": "linear_cent"}
            if program:
                self.programs[tk] = {"market_ticker": tk, "period_reward": 200000, "target_size_fp": "1000.00",
                                     "discount_factor_bps": 5000, "incentive_type": "liquidity", "id": "p-" + tk,
                                     "start_date": rr.utc_iso(close - 900)[:19] + "Z",
                                     "end_date": rr.utc_iso(close)[:19] + "Z"}
            snap = {"market_ticker": tk}
            if sp.get("yes") is not None or sp.get("no") is not None:
                snap["yes_dollars_fp"] = [["%.4f" % p, "%.2f" % s] for p, s in sorted((sp.get("yes") or {}).items())]
                snap["no_dollars_fp"] = [["%.4f" % p, "%.2f" % s] for p, s in sorted((sp.get("no") or {}).items())]
            self._add("orderbook_snapshot", int((close - 415) * 1000), {"type": "orderbook_snapshot", "sid": 4,
                                                                        "msg": snap})
            for i, ev in enumerate(sp.get("events") or []):
                if ev[0] == "d":
                    _, L, side, px, dl = ev
                    s = close - L
                    self._add("orderbook_delta", int(s * 1000 + 100 + i),
                              {"type": "orderbook_delta", "sid": 4, "msg": {"market_ticker": tk, "price_dollars": px,
                                                                            "delta_fp": "%.2f" % dl, "side": side,
                                                                            "ts_ms": int(s * 1000)}})
                else:
                    _, L, n, px, fields = ev
                    s = close - L
                    m = {"market_ticker": tk, "yes_price_dollars": px, "count_fp": "%.2f" % n,
                         "ts_ms": int(s * 1000 + 500)}
                    m.update(fields)
                    self._add("trade", int(s * 1000 + 505), {"type": "trade", "sid": 5, "msg": m})
        for s in range(int(close) - 430, int(close) + 9):
            L = close - s
            if silence and silence[0] <= L <= silence[1]:
                continue
            self._add("orderbook_delta", int(s * 1000 + 10),
                      {"type": "orderbook_delta", "sid": 4, "msg": {"market_ticker": first, "price_dollars": "0.5000",
                                                                    "delta_fp": "0.00", "side": "yes",
                                                                    "ts_ms": int(s * 1000)}})

    def source(self):
        lines = {}
        seq = 0
        allv = sorted(self.items["orderbook_snapshot"] + self.items["orderbook_delta"], key=lambda x: (x[0], x[1]))
        chans = {id(x): ch for ch in ("orderbook_snapshot", "orderbook_delta") for x in self.items[ch]}
        for x in allv:
            seq += 1
            obj = dict(x[2], seq=seq, _rx_ms=x[0])
            lines.setdefault((chans[id(x)], hour_str(x[0] / 1000.0)), []).append(json.dumps(obj).encode())
        for x in sorted(self.items["trade"], key=lambda x: (x[0], x[1])):
            obj = dict(x[2], seq=x[1], _rx_ms=x[0])
            lines.setdefault(("trade", hour_str(x[0] / 1000.0)), []).append(json.dumps(obj).encode())
        hours = {h for _, h in lines}
        return _WorldSource(lines, hours)


class _WorldSource:
    def __init__(self, lines, hours, extra_hours=()):
        self.l, self.hours = lines, set(hours) | set(extra_hours)

    def exists(self, h):
        return True

    def lines(self, ch, h, diag):
        return iter(self.l.get((ch, h), []))


class _FakeHttp:
    def __init__(self, world, statuses_with=("closed",)):
        self.w, self.calls, self.bytes, self.with_ = world, 0, 0, statuses_with
        self.log = []

    def __call__(self, path, params):
        self.calls += 1
        self.log.append((path, dict(params)))
        if path == "/incentive_programs":
            rows = list(self.w.programs.values()) if params.get("status") in self.with_ else []
            rows.append({"market_ticker": "KXOTHER-26OCT20-X", "period_reward": 1, "target_size_fp": "1",
                         "discount_factor_bps": 1})
            return 200, {"incentive_programs": rows, "next_cursor": ""}
        if path == "/markets":
            lo, hi = float(params["min_close_ts"]), float(params["max_close_ts"])
            ms = [m for m in self.w.markets.values() if lo <= rr.parse_ts(m["close_time"]) <= hi]
            return 200, {"markets": ms, "cursor": ""}
        return 404, None


class _GapSource:
    """A planted tape with WHOLE hours missing (no file at all), and no file after `last` (not written yet)."""

    def __init__(self, inner, missing, last):
        self.inner, self.missing, self.last = inner, set(missing), last

    def exists(self, h):
        return h not in self.missing and hour_ts(h) <= hour_ts(self.last)

    def lines(self, ch, h, diag):
        return iter(()) if not self.exists(h) else self.inner.lines(ch, h, diag)


class _FailHttp:
    """_FakeHttp with planted failures: fail[(path, status or None)] = how many calls fail (-1 = every call), or a
    function (path, params) -> True to fail that call."""

    def __init__(self, inner, fail):
        self.inner, self.calls, self.bytes, self.log = inner, 0, 0, []
        self.fail = fail if callable(fail) else dict(fail)

    def __call__(self, path, params):
        self.calls += 1
        k = (path, params.get("status"))
        self.log.append(k)
        if callable(self.fail):
            if self.fail(path, params):
                return 503, None
            return self.inner(path, params)
        n = self.fail.get(k, 0)
        if n:
            self.fail[k] = n - 1 if n > 0 else n
            return 503, None
        return self.inner(path, params)


class _PagedHttp:
    """A paged /incentive_programs listing: pages[status] = [rows of page 0, rows of page 1, ...]."""

    def __init__(self, pages):
        self.p, self.calls, self.bytes, self.log = pages, 0, 0, []

    def __call__(self, path, params):
        self.calls += 1
        st, i = params.get("status"), int(params.get("cursor") or 0)
        self.log.append((st, i))
        pg = self.p.get(st) or []
        return 200, {"incentive_programs": pg[i] if i < len(pg) else [],
                     "next_cursor": str(i + 1) if i + 1 < len(pg) else ""}


def _st(yes, no):
    ylv = tuple(sorted(((p, s) for p, s in yes.items() if s > 0), reverse=True))
    nlv = tuple(sorted(((p, s) for p, s in no.items() if s > 0), reverse=True))
    return ylv, round(sum(s for _, s in ylv), 2), yes.get(0.01, 0.0), nlv, round(sum(s for _, s in nlv), 2)


def _mk_leg_by_L(tk, close, book_at, prog, result="no", sold=None, neg1c=None, add99=None, rem99=None):
    """A LegData whose book at second L is book_at(L) = (others' YES {px: n}, NO {px: n}); flows keyed by L."""
    return LegData(tk, close, result, prog, True, [_st(*book_at(L)) for L in range(REC_MAX + 1)], sold or {},
                   neg1c or {}, add99 or {}, rem99 or {})


def _mk_leg(tk, close, yes, no, prog, result="no"):
    """A LegData with the same book every second and no flows (unit-level rail tests)."""
    ylv = tuple(sorted(((p, s) for p, s in yes.items() if s > 0), reverse=True))
    nlv = tuple(sorted(((p, s) for p, s in no.items() if s > 0), reverse=True))
    st = (ylv, round(sum(s for _, s in ylv), 2), yes.get(0.01, 0.0), nlv, round(sum(s for _, s in nlv), 2))
    return LegData(tk, close, result, prog, True, [st] * (REC_MAX + 1), {}, {}, {}, {})


def selftest(verbose=False):
    fails, notes = [], []

    def ck(ok, m):
        (notes if ok else fails).append(m)

    def near(a, b, tol=1e-5):
        return a is not None and b is not None and abs(a - b) <= tol

    P = {"reward": 20.0, "target": 1000.0, "df": 0.5, "start": None, "end": None}
    NO = {0.95: 1500.0}
    LEADER = {"yes": {0.95: 500.0, 0.90: 600.0}, "no": {0.04: 500.0, 0.03: 600.0}, "result": "yes"}
    A = {"yes": {}, "no": NO}

    # ---- 0. the July walk is rr.walk minus ONE exclusion; projection = floor_check's arithmetic; v2 count
    import random
    rnd = random.Random(20261017)
    same = 0
    for _ in range(3000):
        lv = {round(rnd.randint(1, 98) / 100.0, 2): float(rnd.choice([1, 5, 20, 100, 120, 300, 999, 1100]))
              for _ in range(rnd.randint(0, 6))}
        ours = rnd.choice([0.0, 1100.0, 984.0])
        tg = rnd.choice([1000.0, 1500.0])
        if walk_july(lv, tg, 0.5, ours=ours) == rr.walk(lv, tg, 0.5, ours=ours):
            same += 1
    ck(same == 3000, "walk_july == rr.walk on 3,000 random books with every bid under 99c (%d)" % same)
    o, j = rr.walk({0.99: 50.0, 0.95: 1500.0}, 1000.0, 0.5), walk_july({0.99: 50.0, 0.95: 1500.0}, 1000.0, 0.5)
    ck(not o["q"] and j["q"] and j["ref"] == 0.95,
       "a 99c top bid: rr.walk excludes the side (old rule), walk_july qualifies it (July rule, ref 95c)")
    ck(snapshot_july({}, NO, 1100, P) == {"ok": True, "sh": 1.0}, "snapshot_july: alone at 1c with NO 1,500 -> share 1")
    ck(count_for_v2({"target": 1000.0}) == 1100 and count_for_v2({"target": 1500.0}) == 1100,
       "v2 count: target 1,000 -> 1,100; target 1,500 -> capped at 1,100")
    dA = _mk_leg("KXCRYPTOLEAD15M-X-BTC", 1e9, {}, NO, P)
    ck(near(projection(dA, {}, NO, 1100, 1e9 - 360, EXIT_S), 2.70) and
       near(projection(dA, {}, NO, 1100, 1e9 - 220, EXIT_S), 103 / 90.0) and
       near(projection(dA, {}, NO, 1100, 1e9 - 230, EXIT_S), 113 / 90.0),
       "projection (L-115-2) x share x 20/1800: 2.70 at 360, 1.1444 at 220, 1.2556 at 230")
    P15 = dict(P, target=1500.0)
    res, _ = simulate_race([_mk_leg("KXCRYPTOLEAD15M-X-BTC", 1e9, {}, {0.95: 2000.0}, P15)], "x99")
    r15 = res["KXCRYPTOLEAD15M-X-BTC"]
    ck(r15["placed_left"] is None and r15["refusals"].get("under_floor") == WINDOW - EXIT_S,
       "target 1,500: 1,100 cannot fill the side alone (share 0) -> refused under_floor every second")

    # ---- 0b. rule details no tape world pinned (review 2026-10-17: 12 mutations passed). Unit worlds, hand answers.
    Ct, tkU = 1e9, "KXCRYPTOLEAD15M-X-BTC"
    # 99c NO is removed from the NO book while we rest. NO 95c 1,000 until L=251; from L=250 95c 900 + 99c 150. With
    # the removal the NO side is short from L=250: 359..251 = 109 counted s. (Kept, the July walk would count 1,050.)
    u1 = simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({}, {0.95: 1000.0} if L > 250 else {0.95: 900.0, 0.99: 150.0}),
                                     P)], "high", check_rule=True)[0][tkU]
    ck(u1["placed_left"] == 360 and u1["counted_s"] == 109 and near(u1["credit"], 109 / 90.0)
       and u1["rule_diff_s"] == 0 and u1["cancel"] == "exit",
       "0b. 99c NO removed while resting: NO short from L=250 -> 109 counted s, credit $1.21111, not 244 s (%s %s)"
       % (u1["counted_s"], u1["credit"]))
    # placement is refused while a 99c NO bid is up ((c) would_cross, 360..301 = 60 s); placed the second it is gone
    u2 = simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({}, {0.99: 50.0, 0.95: 1500.0} if L > 300 else
                                                         {0.95: 1500.0}), P)], "x99")[0][tkU]
    ck(u2["placed_left"] == 300 and u2["refusals"] == {"would_cross": 60},
       "0b. a 99c NO bid at a postable second refuses placement (would_cross x 60 s); placed at L=300 (%s %s)"
       % (u2["placed_left"], u2["refusals"]))
    # starved = 5 CONSECUTIVE short seconds: a 150 sale at L=300 leaves 950; others' 1c 100 is there at L=296 and from
    # L=292, so the side is short 299..297 and 295..293 (6 s, never 5 in a row) -> rests to exit. YES leg: +$0.99 each.
    u3 = simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({0.01: 100.0} if (L == 296 or L <= 292) else {}, NO), P,
                                     result="yes", sold={300: 150.0})], "high")[0][tkU]
    ck(u3["filled"] == 150.0 and u3["starved_s"] == 6 and u3["cancel"] == "exit" and u3["pnl_signed"] == 148.5,
       "0b. starved needs 5 CONSECUTIVE short seconds (6 in two runs of 3 -> rests to exit); 150 filled on a YES leg "
       "signs +$148.50 (%s %s %s)" % (u3["starved_s"], u3["cancel"], u3["pnl_signed"]))
    # queue models: 20 ahead of us at 1c; 15 of them cancel at L=250 (no sale); a 10 sale at L=200.
    #   low: queue 20 -> 10 by the sale, 0 filled; mid: queue 20 -> 5 by the cancels, the sale fills 5; high: 10
    lm = {m: simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({0.01: 20.0}, NO), P, sold={200: 10.0},
                                         neg1c={250: 15.0})], m)[0][tkU]["filled"] for m in ("low", "mid", "high")}
    ck(lm == {"low": 0.0, "mid": 5.0, "high": 10.0},
       "0b. queue models: low 0, mid 5 (cancels ahead shrink its queue), high 10 (%s)" % lm)
    # the $1.00 pay floor comes AFTER the 0.987 factor: alive at L=268 -> 359..269 = 91 s -> credit $1.01111;
    # 0.987 x 1.01111 = $0.99797 < $1.00 -> paid $0 (floor first would pay $0.998)
    u5 = simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({0.06: 10.0} if L <= 268 else {}, NO), P)], "x99")[0][tkU]
    ck(u5["cancel"] == "alive" and u5["off_left"] == 268 and near(u5["credit"], 91 / 90.0) and u5["paid"] == 0.0,
       "0b. pay floor after the 0.987 factor: credit $1.01111 -> paid $0 (%s %s)" % (u5["credit"], u5["paid"]))
    # alive = others' best YES OVER 5c: exactly 5c from L=250 is not alive
    u6 = simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({0.05: 10.0} if L <= 250 else {}, NO), P)], "x99")[0][tkU]
    ck(u6["cancel"] == "exit", "0b. a 5c YES bid is not 'alive' (cancel at > 5c): rests to exit (%s)" % u6["cancel"])
    # x99 re-post window: a 99c add matched by 99c removals in the same or the 3 seconds before is a re-post.
    #   removal L=200 + add L=197 (3 s later) -> re-post, 0; removal L=150 + add L=146 (4 s later) -> new, 50 filled
    u7 = simulate_race([_mk_leg_by_L(tkU, Ct, lambda L: ({}, NO), P, add99={197: 50.0, 146: 50.0},
                                     rem99={200: 50.0, 150: 50.0})], "x99")[0][tkU]
    ck(u7["filled"] == 50.0 and u7["new99"] == 50.0 and u7["n99_s"] == 1,
       "0b. x99 re-post window 3 s: an add 3 s after a removal is a re-post (0), 4 s after is new (50) (%s)"
       % u7["filled"])
    # a race closing at exactly 00:00 ET belongs to the day before (its last second), block 20-24
    m21 = et_midnight_utc("2026-10-21")
    ck(race_day(m21) == "2026-10-20" and et_block(m21) == "20-24" and race_day(m21 + 900) == "2026-10-21"
       and et_block(m21 + 900) == "00-04", "0b. a race closing at 00:00 ET is the day before's, block 20-24")
    # rail (f) counts UNSETTLED fills (spec check 9): an order cancelled after $9 of fills, not yet settled -> one more
    # $11 order fits (-$9 - $11 = -$20), a second does not (-$9 - $11 resting - $11 = -$31 < -$30)
    dR = _mk_leg(tkU, Ct, {}, NO, P)
    s1, s2 = _S(dR, 1100), _S(dR, 1100)
    s1.filled, s1.rem, s2.on = 900.0, 200.0, True
    rlu = Rail()
    ck(rlu.refusal("x99", 1100, Ct - 360, [s1]) is None
       and rlu.refusal("x99", 1100, Ct - 360, [s1, s2]) == "day_budget",
       "0b. rail (f) after $9 of UNSETTLED fills: 1 more order fits, the 2nd is refused day_budget")

    # ---- planted tape worlds, run end to end through the runner (tape lines -> rebuild -> rule -> log rows)
    W = _World()
    t0 = datetime(2026, 10, 20, 12, 15, tzinfo=timezone.utc).timestamp()
    C1, C2, C3, C4, C5, C8, C7 = t0, t0 + 3600, t0 + 7200, t0 + 10800, t0 + 14400, t0 + 18000, t0 + 21600
    C6 = t0 + 86400
    C11 = C6 + 3600
    C10 =datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc).timestamp()
    C9 = datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc).timestamp()
    sale = {"taker_side": "no", "taker_outcome_side": "no", "taker_book_side": "ask"}
    W.race(C1, {"BTC": A,
                "ETH": {"yes": {0.01: 20.0}, "no": NO, "events": [
                    ("t", 200, 15, "0.0100", sale), ("d", 200, "yes", "0.0100", -15), ("d", 190, "yes", "0.0100", -5),
                    ("d", 180, "no", "0.9900", 101), ("d", 170, "no", "0.9900", 50), ("d", 169, "no", "0.9900", -50),
                    ("d", 169, "no", "0.9900", 50)]},
                "SOL": {"yes": {0.01: 1200.0}, "no": NO, "events": [("t", 250, 40, "0.0100", sale),
                                                                     ("d", 250, "yes", "0.0100", -40)]},
                "XRP": {"yes": {}, "no": NO, "events": [("d", 251, "yes", "0.0600", 10)]},
                "HYPE": LEADER})
    W.race(C2, {"BTC": {"yes": {}, "no": {0.95: 900.0}, "events": [("d", 221, "no", "0.9500", 600)]},
                "ETH": {"yes": {}, "no": {0.95: 900.0}, "events": [("d", 231, "no", "0.9500", 600)]},
                "SOL": {"yes": {}, "no": {}},
                "XRP": {"yes": {}, "no": NO, "events": [
                    ("d", 300, "yes", "0.0050", 5), ("d", 290, "yes", "0.0100", 3), ("d", 289, "yes", "0.0100", -3),
                    ("t", 280, 7, "0.0100", {"taker_book_side": "ask"}), ("t", 270, 9, "0.0100", {"taker_book_side": "bid"}),
                    ("t", 265, 5, "0.0100", {"taker_outcome_side": "no"}), ("t", 260, 11, "0.0200", {"taker_side": "no"})]},
                "HYPE": LEADER})
    W.race(C3, {"BTC": {"yes": {}, "no": NO, "events": [("d", 300, "yes", "0.0100", 1100),
                                                       ("d", 150, "yes", "0.0100", -1100)]},
                "ETH": {"yes": {}, "no": NO, "events": [("d", 300, "yes", "0.0100", 500),
                                                       ("d", 150, "yes", "0.0100", -500)]},
                "SOL": A, "XRP": A, "HYPE": LEADER})
    W.race(C4, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER}, silence=(240, 299))
    W.race(C5, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER}, silence=(241, 299))
    W.race(C8, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER}, program=False)
    W.race(C7, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER}, omit_market=("BTC",))
    W.race(C6, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER})
    W.race(C11, {"BTC": A, "ETH": A, "XRP": A, "HYPE": LEADER})          # 4 of 5 legs on the tape
    W.race(C10,{"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER})
    W.race(C9, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER}, suffix="X")
    src = W.source()
    tmpdir = os.path.join(RESULTS, "_racev2_selftest_%d_%d" % (os.getpid(), int(time.time() * 1000)))
    os.makedirs(tmpdir, exist_ok=False)
    runners = []
    lg, stp, live = (os.path.join(tmpdir, "shadow.jsonl"), os.path.join(tmpdir, "shadow.state.json"),
                     os.path.join(tmpdir, "live.jsonl"))
    try:
        ev3 = "%s-%s" % (SERIES, _World.ticker_time(C3))
        with _open_w(live, "w") as fh:
            for coin in ("BTC", "ETH"):
                fh.write(json.dumps({"ev": "placed", "evt": ev3, "coin": coin, "left": 300.4,
                                     "body": {"count": "1100.00"}}) + "\n")
                fh.write(json.dumps({"ev": "cancelled", "evt": ev3, "coin": coin, "left": 149.6,
                                     "sent_left": 149.6, "why": "exit"}) + "\n")
        hours = [hour_str(c) for c in (C1, C2, C3, C4, C5, C8, C7)] + [hour_str(C7 + 3600), hour_str(day_bounds(
            "2026-10-20")[1]), hour_str(C6), hour_str(C11), hour_str(day_bounds("2026-10-21")[1]), hour_str(C10),
            hour_str(C9),
            hour_str(day_bounds("2026-11-01")[1])]
        http = _FakeHttp(W)
        sink = []
        R = Runner("selftest", lg, stp, source=src, http=http, live_log=live, out=lambda *a, **k: sink.append(a),
                   checks=False)
        runners.append(R)
        R.start(["selftest"], hours[0])
        rc = R.run_hours(hours)
        rows = read_rows(lg)
        legs = {r["tk"]: r for r in rows if r.get("ev") == "leg"}
        races = {r["evt"]: r for r in rows if r.get("ev") == "race"}
        days = {r["day"]: r for r in rows if r.get("ev") == "day"}
        ck(rc == 0 and len(races) == 11 and len(legs) == 54, "runner: 11 planted races, 54 leg rows, rc 0 (%s %d %d)"
           % (rc, len(races), len(legs)))
        r11 = races.get("%s-%s" % (SERIES, _World.ticker_time(C11))) or {}
        ck(r11.get("legs_seen") == 4 and r11.get("clean") is False and r11.get("drop_why") == "legs_missing"
           and not r11.get("scored"), "a race with 4 of its 5 legs on the tape is NOT clean (so out of the "
           "programs-missing base) and is dropped legs_missing (%s)" % {k: r11.get(k) for k in ("clean", "drop_why")})

        def leg(c, coin, suffix=""):
            return legs.get("%s-%s%s-%s" % (SERIES, _World.ticker_time(c), suffix, coin)) or {}

        # 1. Leg A
        a = leg(C1, "BTC")
        ck(a.get("placed_left") == 360 and near(a.get("proj_at_place"), 2.70) and near(a.get("credit_model"), 244 / 90.0)
           and near(a.get("paid_model"), 0.987 * 244 / 90.0) and a["fills"] == {"low": 0.0, "mid": 0.0, "high": 0.0,
                                                                              "x99_gross": 0.0, "x99": 0.0, "latent": None},
           "1. leg A: placed 360 (proj $2.70), credit $2.71111, paid $2.67587, every fill model 0 (%s %s %s)"
           % (a.get("placed_left"), a.get("credit_model"), a.get("paid_model")))
        ck(all(a["models"][m]["cost_cons"] == 0.0 for m in MODELS) and a["models"]["x99"]["rest_s"] == 244,
           "1. leg A: cost 0 in every model; rests 359..116 = 244 s")
        # 2. Leg B
        b = leg(C1, "ETH")
        ck(b.get("fills_nostarve") == {"low": 0.0, "mid": 0.0, "high": 15.0, "x99_gross": 216.0, "x99": 166.0},
           "2. leg B, no starved rule: low 0, mid 0, high 15, x99_gross 216, x99 166 (%s)" % b.get("fills_nostarve"))
        ck(b.get("fills", {}).get("x99") == 116.0 and b["models"]["x99"]["cancel"] == "starved"
           and b["models"]["x99"]["off_left"] == 175 and b.get("starved_s") == 5,
           "2. leg B, starved rule: x99 116, cancelled starved at L=175 after 5 seconds (%s)" % b.get("fills"))
        ck(near(b.get("credit_model"), 1.96774) and near(b.get("paid_model"), 1.94216)
           and near(b["models"]["x99"]["cost_cons"], 1.16, 1e-9),
           "2. leg B x99: credit $1.96774, paid $1.94216, conservative cost $1.16 (%s %s %s)"
           % (b.get("credit_model"), b.get("paid_model"), b["models"]["x99"]["cost_cons"]))
        ck(b["fills"]["low"] == 0.0 and b["fills"]["mid"] == 0.0 and b["fills"]["high"] == 15.0
           and near(b["models"]["high"]["credit"], 2.678850) and b["models"]["high"]["cancel"] == "exit",
           "2. leg B high world: 15 filled, never starved, credit $2.67885 (hand: 160x0.98214+10x0.99541+74)")
        ck(b.get("rule_diff_s") == 0 and b.get("queue_ahead") == 20.0,
           "2. July and old walks agree on every resting second (99c NO removed); queue ahead 20")
        # 3. Leg C
        c = leg(C1, "SOL")
        ck(c.get("placed_left") is None and c.get("why_not_placed") == "yes_side_full" and c["paid_model"] == 0.0
           and c["models"]["x99"]["cost_cons"] == 0.0 and c.get("pile_s") == 170 and c.get("pile_sold") == 40.0,
           "3. leg C: never placed (yes_side_full), credit 0, cost 0; pile 40 contracts over 170 pile-seconds")
        ej = (c.get("variants") or {}).get("early_join") or {}
        ck(ej.get("placed_left") == 360 and near(ej.get("credit_mid"), 1.309227) and near(ej.get("paid_mid"), 1.292207)
           and ej.get("fills_mid") == 0.0, "3. early-join variant behind the 1,200 pile: placed 360, credit $1.30923, "
           "paid $1.29221, 0 filled (the 40 sale eats the queue) (%s)" % ej)
        d10 = days.get("2026-10-20") or {}
        ck(near((d10.get("latent") or {}).get("rate_per_s"), 40 / 170.0, 1e-6),
           "3. latent pile rate on the day = 40/170 = 0.23529 /s (%s)" % (d10.get("latent") or {}).get("rate_per_s"))
        # 4. Leg D
        dd = leg(C1, "XRP")
        ck(dd["models"]["x99"]["cancel"] == "alive" and dd["models"]["x99"]["off_left"] == 250
           and near(dd.get("credit_model"), 109 / 90.0) and near(dd.get("paid_model"), 1.19537),
           "4. leg D: alive cancel at L=250, credit $1.21111, paid $1.19537 (%s %s)"
           % (dd.get("credit_model"), dd.get("paid_model")))
        ck(leg(C1, "HYPE").get("why_not_placed") == "not_dead", "the leader leg is refused not_dead")
        # 5. floor
        e1, e2 = leg(C2, "BTC"), leg(C2, "ETH")
        ck(e1.get("placed_left") is None and e1.get("why_not_placed") in ("under_floor", "no_side_short")
           and e1["refusals"].get("under_floor") == 220 - EXIT_S,
           "5. NO qualifies at L=220: proj $1.144 < $1.25 every second after -> never placed (%s)" % e1.get("refusals"))
        ck(e2.get("placed_left") == 230 and near(e2.get("proj_at_place"), 113 / 90.0)
           and near(e2.get("credit_model"), 114 / 90.0) and near(e2.get("paid_model"), 0.987 * 114 / 90.0),
           "5. NO qualifies at L=230: proj $1.2556 -> placed 230, credit $1.26667, paid $1.25020")
        # NULL: empty book -> 0 fills
        eb = leg(C2, "SOL")
        ck(eb.get("scored") and eb.get("placed_left") is None and eb.get("why_not_placed") == "no_side_short"
           and all(v in (0.0, None) for v in eb["fills"].values()) and eb["paid_model"] == 0.0,
           "NULL: an empty book is never placed (no_side_short): 0 fills, $0 credit")
        # 6. units and trade fields
        u = leg(C2, "XRP")
        ck(u.get("non_whole_cent") == 1 and not u.get("scored") and "non_whole_cent" in u.get("unscored_why", []),
           "6. a delta at price 0.0050: counted once, the leg flagged and not scored, never rescaled")
        ck(u.get("flow_all", {}).get("sold1c") == 12.0 and u["flow_all"]["neg1c"] == 3.0,
           "6. trades: taker_book_side 'ask' (7) and taker_outcome_side 'no' (5) are 1c sales; 'bid' and a 2c print "
           "are not; the 0.0100 delta is the 1c level (%s)" % u.get("flow_all"))
        h2 = [r for r in rows if r.get("ev") == "hour_done" and r["hour"] == hour_str(C2)][0]
        ck(h2["diag"].get("non_whole_cent") == 1, "6. hour_done diag counts non_whole_cent = 1")
        dg = Counter()
        ck(sells_yes({"taker_side": "no", "taker_outcome_side": "no", "taker_book_side": "ask"}, dg) is True
           and dg["trade_side_fields_disagree"] == 0
           and sells_yes({"taker_outcome_side": "yes", "taker_book_side": "ask", "taker_side": "no"}, dg) is False
           and dg["trade_side_fields_disagree"] == 1 and sells_yes({"taker_side": "no"}, dg) is True
           and sells_yes({}, dg) is None,
           "6. taker_outcome_side is preferred over taker_book_side over taker_side; disagreement counted; none -> None")
        # 7. our own order
        o7, n7 = leg(C3, "BTC"), leg(C3, "ETH")
        ck(o7.get("posted_live") and o7.get("scored") and o7.get("placed_left") == 360
           and near(o7.get("credit_model"), 244 / 90.0) and o7["live"]["placed_left"] == 300.4,
           "7. our 1,100 at 1c (live log 300.4..149.6) is subtracted: others' YES empty, the leg posted_live and scored")
        ck(n7.get("posted_live") and not n7.get("scored") and "own_sub_negative" in n7.get("unscored_why", []),
           "7. a live log claiming 1,100 where the tape holds 500: subtraction would go negative -> flagged, not scored")
        ck(leg(C3, "SOL").get("control") is True and leg(C3, "HYPE").get("control") is False,
           "7. a dead postable leg we did not post on, in a race we posted in, is a control leg")
        # 8. gap
        ck(races["%s-%s" % (SERIES, _World.ticker_time(C4))]["drop_why"] == "gap" and
           leg(C4, "BTC").get("gap_max_s") == 61 and not leg(C4, "BTC").get("scored"),
           "8. a 61 s delta silence at L=300..239 -> scored false, race dropped 'gap'")
        r5 = races["%s-%s" % (SERIES, _World.ticker_time(C5))]
        ck(r5["scored"] and leg(C5, "BTC").get("gap_max_s") == 60 and near(leg(C5, "BTC").get("credit_model"), 244 / 90.0),
           "8. a 60 s silence is kept (threshold is OVER 60 s): scored, credit $2.71111")
        ck((d10.get("dropped") or {}).get("gap") == 1, "8. the gap race is counted in day.dropped")
        # NULL: no program -> $0
        np_ = leg(C8, "BTC")
        r8 = races["%s-%s" % (SERIES, _World.ticker_time(C8))]
        ck(np_.get("program") is None and not np_.get("scored") and np_.get("unscored_why") == ["no_program"]
           and "paid_model" not in np_ and r8["clean"] and r8["programs_missing"] and not r8["scored"],
           "NULL: no program -> not scored, never placed, $0 credit; the race counts as programs-missing")
        ck(leg(C7, "BTC").get("close_src") == "ticker" and "close_unverified" in leg(C7, "BTC")["unscored_why"]
           and leg(C7, "ETH").get("scored"), "a leg whose close the API did not give is never scored")
        # 9. rails
        r6 = races["%s-%s" % (SERIES, _World.ticker_time(C6))]
        ck(r6["as_live"]["x99"]["placed"] == 2 and r6["placed_open"] == 4
           and leg(C6, "SOL")["as_live"]["x99"]["placed_left"] is None,
           "9. rails: 4 postable legs on a fresh ET day -> as_live places exactly 2 (open: 4)")
        ck(leg(C6, "SOL")["as_live"]["x99"]["paid"] == 0.0 and r6["as_live"]["x99"]["realized_delta"] == 0.0,
           "9. the refused legs earn nothing in as_live; no fills -> realized 0")
        legs4 = [_mk_leg("KXCRYPTOLEAD15M-26OCT211215-%s" % cn, C6, {}, NO, P) for cn in ("BTC", "ETH", "SOL", "XRP")]
        rl = Rail()
        res, _ = simulate_race(legs4, "x99", rail=rl)
        ck(sum(1 for v in res.values() if v["placed_left"] is not None) == 2
           and res[legs4[2].tk]["refusals"] == {"rail_day_budget": 360 - 229, "under_floor": 229 - EXIT_S},
           "9. unit: the third order would take the worst case to -$33 < -$30 -> refused day_budget at every second "
           "while its floor holds (360..230), then under_floor (the bot checks the floor before the rail)")
        rl9 = Rail()
        rl9.realized[("x99", rr.et_day(C6 - 360))] = -9.0
        res9, _ = simulate_race(legs4, "x99", rail=rl9)
        ck(sum(1 for v in res9.values() if v["placed_left"] is not None) == 1,
           "9. unit: after $9 of fills (realized -$9) only 1 more order fits")
        # 10. DST
        ck(leg(C10, "BTC").get("race_day") == "2026-11-01" and leg(C9, "BTC", "X").get("race_day") == "2026-11-01"
           and leg(C10, "BTC").get("block") == "00-04" and leg(C9, "BTC", "X").get("block") == "00-04"
           and rr.et_offset_h(C10) == -4 and rr.et_offset_h(C9) == -5,
           "10. DST: closes 05:30Z (01:30 EDT) and 06:30Z (01:30 EST) -> ET day 2026-11-01, block 00-04, both")
        ck(close_from_ticker("KXCRYPTOLEAD15M-26NOV010130-BTC") == C10 and
           close_from_ticker("KXCRYPTOLEAD15M-26OCT200815-BTC") == C1,
           "10. the ticker time is ET; the repeated 01:30 reads as EDT (so the API close is the one scored)")
        d11 = days.get("2026-11-01") or {}
        ck(d11.get("races_scored") == 2 and d11.get("block_00_04", {}).get("races") == 2,
           "10. the DST day row holds both races in its 00-04 ET block")
        ck(d10.get("races_expected") == 96 and d10.get("races_unseen") == 89 and d11.get("races_expected") == 100
           and d11.get("races_unseen") == 98,
           "day rows count quarter-hours with NO race on the tape: 10-20 96 expected, 7 seen -> 89; the 25-hour "
           "11-01 100 expected, 2 seen -> 98 (%s %s)" % (d10.get("races_unseen"), d11.get("races_unseen")))
        # day rows
        paid10 = 5 * 0.987 * 244 / 90.0 + 1.942158 + 0.987 * 109 / 90.0
        ck(d10.get("races_scored") == 2 and d10.get("placed_open") == 7 and d10.get("races_clean") == 3
           and d10.get("programs_missing_races") == 1 and near(d10["open"]["x99"]["cost_cons"], 1.16, 1e-9)
           and near(d10["open"]["x99"]["paid"], paid10, 1e-4),
           "day 10-20: 2 scored races, 7 placed, 3 clean, 1 missing a program; x99 cost $1.16 on paid $%.5f (%s)"
           % (paid10, d10.get("open", {}).get("x99")))
        lat_a = 0.01 * 244 * 40 / 170.0
        ck(near(d10["open"]["latent"]["cost_cons"], lat_a * 6 + 0.01 * 109 * 40 / 170.0, 1e-3),
           "day 10-20 latent: 0.23529/s x resting seconds (A legs 244 s -> 57.41 each; D 109 s) (%s)"
           % d10["open"]["latent"])
        d21 = days.get("2026-10-21") or {}
        ck(d21.get("latent", {}).get("rate_per_s") == 0.0 and d21["open"]["latent"]["cost_cons"] == 0.0,
           "NULL: a day with no incumbent pile -> latent rate 0 and latent cost $0 (not a find)")
        ck(d21.get("as_live", {}).get("x99", {}).get("placed") == 2, "day 10-21 as_live x99 placed 2")
        # the --report path on this log: the day table, the gate (not ready: no full day), the 4.3 calibration
        rep = []
        report(lg, 3, out=rep.append, mode="selftest")
        rtxt = " | ".join(rep)
        ck("VERDICT: NOT_READY" in rtxt and "4.3 calibration on 1 posted legs: live fill cost $0.00" in rtxt
           and "2026-10-20" in rtxt and "controls" in rtxt,
           "--report prints the day table, NOT_READY before 3 full days, and the posted-vs-control calibration")
        # the pre-live dry-run comparison (as_live with no fills)
        ck(r6["as_live"]["none"]["placed"] == 2 and leg(C1, "ETH")["as_live"]["none"]["placed_left"] == 360
           and leg(C1, "XRP")["as_live"]["none"]["placed_left"] is None,
           "as_live 'none' (a dry run's view): 2 orders per fresh race; the third refused by rail (f)")
        dry = os.path.join(tmpdir, "dry.jsonl")
        e1, e6 = "%s-%s" % (SERIES, _World.ticker_time(C1)), "%s-%s" % (SERIES, _World.ticker_time(C6))
        base = [{"ev": "race", "evt": e1}, {"ev": "race", "evt": e6},
                {"ev": "would_place", "evt": e1, "coin": "BTC", "left": 359.6},
                {"ev": "would_place", "evt": e1, "coin": "ETH", "left": 355.0},
                {"ev": "would_place", "evt": e6, "coin": "BTC", "left": 359.5},
                {"ev": "would_place", "evt": e6, "coin": "ETH", "left": 358.9}]
        for extra, want in (([], ("MATCH", 0.9)), ([{"ev": "would_place", "evt": e1, "coin": "XRP", "left": 300.0}],
                                                    ("BUG_FIRST", 0.8))):
            with _open_w(dry, "w") as fh:
                for x in base + extra:
                    fh.write(json.dumps(x) + chr(10))
            v, sh = compare_dry(lg, dry, out=lambda *a: None, mode="selftest")
            ck(v == want[0] and near(sh, want[1], 1e-9), "dry-run comparison: %s at %s (planted %s)" % (v, sh, want))
        # idempotent restart
        n_leg = len(legs)
        R2 = Runner("selftest", lg, stp, source=src, http=_FakeHttp(W), live_log=live, out=lambda *a, **k: None,
                    checks=False)
        runners.append(R2)
        R2.run_hours(hours[:3])
        rows2 = read_rows(lg)
        ck(sum(1 for r in rows2 if r.get("ev") == "leg") == n_leg and not R2.fresh
           and sum(1 for r in rows2 if r.get("ev") == "day") == len(days),
           "restart: the same hours re-read write no second leg/race/day row (idempotent by race)")
        nst = Counter(q.get("status") for p, q in http.log if p == "/incentive_programs")
        ck(nst["closed"] == 2 and nst["paid_out"] == 1 and nst["active"] == 1 and nst["upcoming"] == 1,
           "programs: one hourly active+upcoming read; past races from the closed listing; paid_out paged only for "
           "the race whose program was never listed; each ticker searched once (%s)" % dict(nst))
        # 11. hour readiness, stop file, follow
        ws = _WorldSource({}, set())
        ck(Runner.hour_ready(type("X", (), {"src": ws})(), "20261017T03", hour_ts("20261017T04") + 119) is False and
           Runner.hour_ready(type("X", (), {"src": ws})(), "20261017T03", hour_ts("20261017T04") + 121) is True,
           "an hour is processed only once a later file exists and the clock is past H+1:02")
        # 11b. (review 2026-10-17 must-fix) a WHOLE hour with no file, and a 13-hour outage (> the 12-empty-hours
        #      stop): the cursor looks past them; every hour is processed once; missing hours never count as empty
        gsrc = _GapSource(_WorldSource({}, set()), {"20261017T04"}, "20261017T05")
        X = type("X", (), {"src": gsrc})()
        ck(Runner.hour_ready(X, "20261017T03", hour_ts("20261017T04") + 121) is False
           and Runner.hour_ready(X, "20261017T03", hour_ts("20261017T05") + 5) is True
           and Runner.hour_ready(X, "20261017T04", hour_ts("20261017T05") + 121) is True
           and Runner.hour_ready(X, "20261017T05", hour_ts("20261017T07") + 121) is False,
           "11b. H+1 has no file: H waits until a later file (H+2) exists, then is ready; the missing H+1 is ready "
           "too; with no later file nothing is ready")
        W2 = _World()
        g0 = datetime(2026, 10, 25, 12, 15, tzinfo=timezone.utc).timestamp()
        race_k, gap_k = (0, 1, 2, 16, 17, 18, 21, 22), set(range(3, 16)) | {20}

        def hk(k):
            return hour_str(g0 + 3600 * k)
        for k in race_k:                      # k = 19 has a file with no coin-race line; k = 23 is the newest file
            W2.race(g0 + 3600 * k, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER})
        gclk = [g0 - 600]
        http2 = _FakeHttp(W2)
        g_log = os.path.join(tmpdir, "gap.jsonl")
        Rg = Runner("selftest", g_log, os.path.join(tmpdir, "gap.state.json"),
                    source=_GapSource(W2.source(), {hk(k) for k in gap_k}, hk(23)), http=http2, live_log=live,
                    out=lambda *a, **k: None, checks=False, clock=lambda: gclk[0],
                    sleep=lambda x: gclk.__setitem__(0, gclk[0] + x))
        runners.append(Rg)
        Rg.start(["selftest"], hk(0))
        rcg = Rg.follow(30.0, stop_path=os.path.join(tmpdir, "no.stop"))
        gr = read_rows(g_log)
        hd = [r for r in gr if r.get("ev") == "hour_done"]
        emp = {r["hour"]: r.get("empty_run") for r in hd}
        graces = [r for r in gr if r.get("ev") == "race"]
        gstops = [r.get("why") for r in gr if r.get("ev") == "stop"]
        gday = next((r for r in gr if r.get("ev") == "day" and r.get("day") == "2026-10-25"), {})
        ck([r["hour"] for r in hd] == [hk(k) for k in range(23)]
           and {r["hour"] for r in hd if r["missing"]} == {hk(k) for k in gap_k},
           "11b. one missing hour + a 13-hour outage: hours 0..22 each processed once, in order; exactly the 14 with "
           "no file logged missing (%d rows; cursor %s)" % (len(hd), Rg.state["next_hour"]))
        ck(len(graces) == 8 and all(r["scored"] for r in graces) and rcg == 0 and gstops == ["hours elapsed"]
           and Rg.state["next_hour"] == hk(23),
           "11b. all 8 planted races logged and scored; never stopped as 'no coin-race line' (rc %s, %s)"
           % (rcg, gstops))
        ck(emp.get(hk(19)) == 1 and emp.get(hk(20)) == 1 and emp.get(hk(21)) == 0
           and all(emp.get(hk(k)) == 0 for k in range(3, 16)),
           "11b. empty-hours count: +1 on a file with no coin-race line (19), unchanged on a missing hour (20 and the "
           "13-hour outage), reset by coin-race lines (21) (%s)" % [emp.get(hk(k)) for k in (19, 20, 21)])
        ck(not any(p == "/markets" and q.get("min_close_ts") == int(hour_ts(hk(k)) - 900)
                   for p, q in http2.log for k in gap_k)
           and {hk(k) for k in range(3, 16)} <= set(gday.get("hours_missing") or []) and gday.get("full") is False,
           "11b. a missing hour costs no /markets call; the ET day it touches is never 'full' (hours_missing)")
        # 11c. (review should-fix 5, 7) a FAILED lookup never makes a race programs-missing or close-unverified for
        #      good: the race is held and retried hourly (DEFER_TRIES), then logged with the failure named
        W3 = _World()
        d0 = datetime(2026, 10, 27, 12, 15, tzinfo=timezone.utc).timestamp()
        W3.race(d0, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER})
        src3 = W3.source()
        h3 = [hour_str(d0 + 3600 * k) for k in range(5)] + [hour_str(day_bounds("2026-10-27")[1])]

        def run3(name, fail, hrs, world=W3, wsrc=src3):
            lg3 = os.path.join(tmpdir, "lk_%s.jsonl" % name)
            R_ = Runner("selftest", lg3, None, source=wsrc, http=_FailHttp(_FakeHttp(world), fail), live_log=live,
                        out=lambda *a, **k: None, checks=False)
            runners.append(R_)
            R_.run_hours(hrs)
            rw = read_rows(lg3)
            return [[r for r in rw if r.get("ev") == e] for e in ("race", "leg", "day")]
        LP, LM = ("/incentive_programs", "closed"), ("/incentive_programs", "paid_out")
        ra, la, _ = run3("once", {LP: 1, LM: 1, ("/markets", None): 2}, h3[:3])
        ck(len(ra) == 1 and ra[0]["scored"] and ra[0]["deferred_hours"] == 1 and ra[0]["lookup_failed"] == []
           and not ra[0]["programs_missing"] and len(la) == 5
           and all(x["close_src"] == "api_checked" and x["scored"] for x in la)
           and near(next(x for x in la if x["coin"] == "BTC")["credit_model"], 244 / 90.0),
           "11c. program listings AND /markets failing in the race's hour: held 1 hour, the retry finds both -> "
           "scored, credit $2.71111, closes confirmed by the API (api_checked), not programs-missing")
        rb_, lb_, db_ = run3("always", {LP: -1, LM: -1}, h3)
        dd3 = db_[0] if db_ else {}
        ck(len(rb_) == 1 and rb_[0]["drop_why"] == "program_lookup_failed" and rb_[0]["clean"]
           and not rb_[0]["programs_missing"] and rb_[0]["deferred_hours"] == DEFER_TRIES
           and lb_[0]["unscored_why"] == ["program_lookup_failed", "no_program"]
           and dd3.get("races_lookup_failed") == 1 and dd3.get("races_programs_known") == 0
           and dd3.get("programs_missing_races") == 0,
           "11c. listings failing every hour: held %d hours, then logged program_lookup_failed -- NOT programs-missing "
           "and out of that line's base (%s)" % (DEFER_TRIES, {k: dd3.get(k) for k in ("races_lookup_failed",
                                                                                     "races_programs_known")}))
        rc_, _, _ = run3("flush", {LP: -1, LM: -1}, h3[:2])
        ck(len(rc_) == 1 and rc_[0]["deferred_hours"] == 2 and rc_[0]["drop_why"] == "program_lookup_failed",
           "11c. a race still held when the run ends is logged with its lookup failure (never dropped silently)")
        # a race held across its ET day's end: the day row waits for it. Race 2 closes 23:45 ET; every /markets call
        # covering its close fails 4 times (its hour and the day-end hour, hourly + targeted) -> held 2 hours, scored
        # at 05Z; the 10-27 day row is written then, with both races.
        W4 = _World()
        late = day_bounds("2026-10-27")[1] - 900
        W4.race(d0, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER})
        W4.race(late, {"BTC": A, "ETH": A, "SOL": A, "XRP": A, "HYPE": LEADER})
        nbad = [0]

        def bad_late(path, q):
            if path == "/markets" and q["min_close_ts"] <= late <= q["max_close_ts"] and nbad[0] < 4:
                nbad[0] += 1
                return True
            return False
        rd_, _, dd_ = run3("dayheld", bad_late, [hour_str(d0), hour_str(late), hour_str(late + 900),
                                                  hour_str(late + 4500)], world=W4, wsrc=W4.source())
        rl4 = [r for r in rd_ if r["close"] == rr.utc_iso(late)[:19] + "Z"]
        ck(nbad[0] == 4 and len(rl4) == 1 and rl4[0]["scored"] and rl4[0]["deferred_hours"] == 2 and len(dd_) == 1
           and dd_[0]["day"] == "2026-10-27" and dd_[0]["races_seen"] == 2 and dd_[0]["races_scored"] == 2,
           "11c. a race held over its ET day's end: the day row waits and holds both races (%s)"
           % [(d["day"], d["races_seen"]) for d in dd_])
        # 11d. (review should-fix 8) the program fallback stops paging once every program on a page ended > 1 day
        #      before the oldest close looked up: a never-listed ticker costs 4 pages, not 12 + 12 x 1.9 MB
        def prow(i, end):
            return {"market_ticker": "%s-26OCT01%04d-BTC" % (SERIES, i), "period_reward": 200000,
                    "target_size_fp": "1000.00", "discount_factor_bps": 5000, "incentive_type": "liquidity",
                    "id": "q%d" % i, "start_date": rr.utc_iso(end - 900)[:19] + "Z",
                    "end_date": rr.utc_iso(end)[:19] + "Z"}
        pages = {"closed": [[prow(1, d0 - 3600)], [prow(2, d0 - 23 * 3600)], [prow(3, d0 - 25 * 3600)]]
                 + [[prow(10 + i, d0 - (26 + i) * 3600)] for i in range(7)],
                 "paid_out": [[prow(30 + i, d0 - (30 + i) * 3600)] for i in range(10)]}
        Rq = Runner("selftest", os.path.join(tmpdir, "pg.jsonl"), None, source=_WorldSource({}, set()),
                    http=_PagedHttp(pages), live_log=live, out=lambda *a, **k: None, checks=False)
        runners.append(Rq)
        tq = "%s-%s-BTC" % (SERIES, _World.ticker_time(d0))
        fq = Rq.ensure_programs([tq])
        ph0 = _PagedHttp(pages)
        fetch_programs(ph0, ("closed", "paid_out"), want={tq})
        ck(fq == {"ok": True, "pages": 4, "wanted": 1, "found": 0} and tq in Rq.searched
           and Rq.http.log == [("closed", 0), ("closed", 1), ("closed", 2), ("paid_out", 0)] and ph0.calls == 20,
           "11d. a never-listed ticker: closed 3 pages (the 3rd ends > 1 day before its close) + paid_out 1 = 4, not "
           "the 20 listed (%s %s)" % (fq, Rq.http.log))
        # the same listing with NO coin-race row at all (Kalshi stopped listing them): the stop reads every row's
        # end, so it still stops at 4; and one recent non-coin row on a page keeps the paging going (control)
        oth = {st: [[dict(r, market_ticker="KXOTHER-26OCT01-X%d" % j) for r in pg] for j, pg in enumerate(v)]
               for st, v in pages.items()}
        ph1 = _PagedHttp(oth)
        _, _, n1 = fetch_programs(ph1, ("closed", "paid_out"), want={tq}, older_than=d0 - FALLBACK_STOP_MARGIN_S)
        mix = dict(pages, closed=[pages["closed"][0], pages["closed"][1],
                                  pages["closed"][2] + [dict(prow(77, d0 - 2 * 3600), market_ticker="KXOTHER-X")]]
                   + pages["closed"][3:])
        ph2 = _PagedHttp(mix)
        _, _, n2 = fetch_programs(ph2, ("closed", "paid_out"), want={tq}, older_than=d0 - FALLBACK_STOP_MARGIN_S)
        ck(n1 == 4 and n2 == 5 and ph2.log[:4] == [("closed", 0), ("closed", 1), ("closed", 2), ("closed", 3)],
           "11d. no coin-race row listed at all -> still 4 pages; a page holding one recent program of any market is "
           "not the end (5 pages) (%s %s)" % (n1, n2))
        sf = os.path.join(tmpdir, "stop")
        with _open_w(sf, "w") as fh:
            fh.write("stop\n")
        R3 = Runner("selftest", os.path.join(tmpdir, "f.jsonl"), os.path.join(tmpdir, "f.state.json"), source=src,
                    http=_FakeHttp(W), live_log=live, out=lambda *a, **k: None, checks=False, sleep=lambda s: None)
        runners.append(R3)
        R3.start(["selftest"], hours[0])
        rc3 = R3.follow(1.0, stop_path=sf)
        ck(rc3 == 0 and any(r.get("ev") == "stop" and r.get("why") == "stop file"
                            for r in read_rows(os.path.join(tmpdir, "f.jsonl"))),
           "the stop file ends a follow cleanly with a stop row")
        # a fault inside an hour: logged, the books dropped and re-read from the hour before; no duplicate row
        class _Flaky:
            def __init__(self, inner, bad_hour):
                self.inner, self.bad, self.fired = inner, bad_hour, False

            def exists(self, h):
                return True

            def lines(self, ch, h, diag):
                if ch == "orderbook_delta" and h == self.bad and not self.fired:
                    self.fired = True
                    raise RuntimeError("planted fault")
                return self.inner.lines(ch, h, diag)
        fl_log, fl_st = os.path.join(tmpdir, "flaky.jsonl"), os.path.join(tmpdir, "flaky.state.json")
        R4 = Runner("selftest", fl_log, fl_st, source=_Flaky(src, hour_str(C2)), http=_FakeHttp(W), live_log=live,
                    out=lambda *a, **k: None, checks=False, clock=lambda: C6 + 30 * 86400, sleep=lambda s: None)
        runners.append(R4)
        R4.start(["selftest"], hour_str(C1))
        rc4 = R4.follow(1.0, stop_path=os.path.join(tmpdir, "no.stop"), max_hours=3)
        fr = read_rows(fl_log)
        ftk = [r["tk"] for r in fr if r.get("ev") == "leg"]
        ck(rc4 == 0 and sum(1 for r in fr if r.get("ev") == "error") == 1 and len(ftk) == 15 and len(set(ftk)) == 15
           and any(r.get("ev") == "hour_done" and r.get("reread") for r in fr)
           and abs(next(r for r in fr if r.get("tk") == leg(C1, "ETH")["tk"])["credit_model"] - 1.967739) < 1e-5,
           "a planted fault mid-hour: one error row, a re-read from the hour before, 15 legs each logged once")
        # a race HELD by a failed /markets lookup, then a fault in the next hour: the re-read rebuilds that race's
        # books too; the held books win, so the race is finalised once with 5 legs (not 10)
        fh_log = os.path.join(tmpdir, "heldflaky.jsonl")
        R5 = Runner("selftest", fh_log, os.path.join(tmpdir, "heldflaky.state.json"),
                    source=_Flaky(src3, hour_str(d0 + 3600)), http=_FailHttp(_FakeHttp(W3), {("/markets", None): 2}),
                    live_log=live, out=lambda *a, **k: None, checks=False, clock=lambda: d0 + 30 * 86400,
                    sleep=lambda s: None)
        runners.append(R5)
        R5.start(["selftest"], hour_str(d0))
        rc5 = R5.follow(1.0, stop_path=os.path.join(tmpdir, "no.stop"), max_hours=2)
        f5 = read_rows(fh_log)
        r5r = [r for r in f5 if r.get("ev") == "race"]
        ck(rc5 == 0 and len(r5r) == 1 and r5r[0]["legs_seen"] == 5 and r5r[0]["scored"]
           and r5r[0]["deferred_hours"] == 1 and sum(1 for r in f5 if r.get("ev") == "leg") == 5
           and sum(1 for r in f5 if r.get("ev") == "error") == 1,
           "a held race + a fault + the re-read: finalised once, 5 legs, scored (%s)"
           % [(r["legs_seen"], r["scored"]) for r in r5r])
        # 12. null world
        empty = _WorldSource({}, set())
        cap = []
        Rn = Runner("selftest", os.path.join(tmpdir, "null.jsonl"), None, source=empty, http=_FakeHttp(_World()),
                    live_log=live, out=lambda *a, **k: None, checks=False)
        runners.append(Rn)
        import io
        old = sys.stdout
        sys.stdout = io.StringIO()
        try:
            rcn = Rn.run_hours(["20261020T03", "20261020T04"])
            cap.append(sys.stdout.getvalue())
        finally:
            sys.stdout = old
        ck(rcn == 4 and "loaded nothing" in cap[0] and not any(r.get("ev") == "leg" for r in
                                                                read_rows(os.path.join(tmpdir, "null.jsonl"))),
           "12. a world with no coin-race lines prints 'loaded nothing' and stops, with no leg row")
        # multi-member gzip and a corrupt tail
        import gzip as _gz
        gzp = os.path.join(tmpdir, "gz.jsonl.gz")
        with _open_w(gzp, "wb") as fh:
            fh.write(_gz.compress(b'{"a":"CRYPTOLEAD 1"}\n{"a":"other"}\n'))
            fh.write(_gz.compress(b'{"a":"CRYPTOLEAD 2"}\n'))
            fh.write(b"\x1f\x8b\x08\x00garbage-tail")
        dg2 = Counter()
        got = list(stream_lines(gzp, dg2))
        ck(len(got) == 2 and dg2["gzip_members_extra"] >= 1 and dg2["corrupt_tail"] == 1,
           "tape reader: both gzip members read, the corrupt tail counted, nothing raised (%s %s)" % (len(got), dict(dg2)))
        # report gate
        def fake_day(day, races, placed, paid, cost, clean=None, miss=0, known=None):
            return {"day": day, "full": True, "races_seen": races, "races_clean": clean or races, "races_scored": races,
                    "races_programs_known": known or clean or races,
                    "programs_missing_races": miss, "placed_open": placed,
                    "open": {"x99": {"paid": paid, "cost_cons": cost}, "high": {"paid": paid}}}
        ck(gate([fake_day("2026-10-1%d" % i, 50, 100, 100.0, 50.0, clean=86, miss=36) for i in (7, 8, 9)])[0] == "HOLD",
           "gate: programs missing on 42% of clean races (so only 150 scored) -> HOLD, not NOT_READY")
        ck(gate([fake_day("2026-10-1%d" % i, 90, 180, 100.0, 50.0, clean=100, miss=5, known=90)
                 for i in (7, 8, 9)])[0] == "HOLD",
           "gate: the programs-missing base leaves out failed listings: 15 of 270 (5.6%) -> HOLD (15 of 300 would not)")
        ok3 = [fake_day("2026-10-1%d" % i, 90, 180, 100.0, 50.0) for i in (7, 8, 9)]
        ck(gate(ok3)[0] == "RECOMMEND_LIVE_TEST", "gate: 270 races, 2.0 placed/race, 50% cost, 0 missing -> recommend")
        ck(gate([fake_day("2026-10-1%d" % i, 90, 180, 100.0, 71.0) for i in (7, 8, 9)])[0] == "HOLD",
           "gate: x99 cost 71% of paid -> HOLD")
        ck(gate([fake_day("2026-10-1%d" % i, 90, 60, 100.0, 10.0) for i in (7, 8, 9)])[0] == "HOLD",
           "gate: 0.67 placed legs per race -> HOLD")
        ck(gate([fake_day("2026-10-1%d" % i, 90, 180, 100.0, 10.0, clean=94, miss=5) for i in (7, 8, 9)])[0] == "HOLD",
           "gate: programs missing on 15 of 282 clean races (5.3%) -> HOLD")
        ck(gate(ok3[:2])[0] == "NOT_READY" and gate([fake_day("2026-10-1%d" % i, 80, 160, 100.0, 50.0)
                                                    for i in (7, 8, 9)])[0] == "NOT_READY",
           "gate: 2 days, or 240 scored races, -> NOT_READY (the bar is not read early)")
        # writes only under results/
        try:
            _open_w(os.path.join(REPO, "racev2_selftest_outside.tmp"), "a")
            ck(False, "_open_w refused a path outside results/")
        except PermissionError:
            ck(not os.path.exists(os.path.join(REPO, "racev2_selftest_outside.tmp")),
               "_open_w refuses any path outside results/ (nothing created)")
    finally:
        for x in runners:
            x.log.close()
        for fn in os.listdir(tmpdir):
            try:
                _remove_own(os.path.join(tmpdir, fn))
            except OSError as e:
                fails.append("self-test temp file not removed: %s (%r)" % (fn, e))
        try:
            os.rmdir(tmpdir)
        except OSError as e:
            fails.append("self-test temp dir not removed: %r" % e)

    # ---- 11. source assertion: paper by construction
    src_txt = open(os.path.abspath(__file__), encoding="utf-8").read()
    bad = [w for w in ("P" + "OST", "DEL" + "ETE", "P" + "UT") if re.search(r"\b%s\b" % w, src_txt)]
    ck(not bad, "source: no non-GET method name (%s)" % bad)
    ck(("/portfolio/" + "events/orders") not in src_txt and ("portfolio/" + "orders") not in src_txt
       and ("import " + "ordercli") not in src_txt and ("from " + "ordercli") not in src_txt
       and ("auth=" + "True") not in src_txt and ("load_" + "quotes") not in src_txt,
       "source: no order endpoint, no ordercli, no authenticated call, no replay quote loader")
    imps = [ln.strip() for ln in src_txt.splitlines() if ln.strip().startswith(("import ", "from "))]
    ck(not any(w in ln for ln in imps for w in ("kauth", "replay", "pinsim", "pindata", "ordercli")),
       "source: never imports kauth (no key loaded), replay, pinsim, pindata or ordercli")
    ck(not re.search(r"(?<![\w.])open\([^)\n]*['\"](?:w|a|wb|ab|x|w\+|a\+|r\+)['\"]", src_txt),
       "source: every write goes through _open_w (results/ only)")
    ck(("da" + "ta=") not in src_txt.replace("data = ", "").replace("data += ", ""),
       "source: no request body is ever built")
    used = set(re.findall(r"\brr\.([A-Za-z_]+)", src_txt))
    allowed = {"walk", "snapshot", "credit", "floored", "leg_refusal", "others_of", "et_offset_h", "et_day",
               "InstanceLock", "ticks_between", "period_of", "utc_iso", "parse_ts", "f", "SERIES", "COINS",
               "FLOOR_USD", "FLOOR_MARGIN_S", "DEAD_YES", "ALIVE_YES", "NO_MAX", "MAX_RESTING", "DAY_STOP",
               "WINDOW_S", "Bot", "__file__"}
    ck(used <= allowed, "source: only racereward_live's scoring/time helpers are used (%s)" % sorted(used - allowed))

    if verbose:
        for m in notes:
            print("  ok  ", m)
    for m in fails:
        print("  FAIL", m)
    if fails:
        raise AssertionError("%d of %d self-test checks failed" % (len(fails), len(fails) + len(notes)))
    print("racev2_shadow selftest ok: %d checks (planted-world groups 0-12, 0b rule details, 11b missing hours, 11c "
          "failed lookups, 11d paging + NULLs: no program -> $0, empty book -> 0 fills, no pile -> latent 0)"
          % len(notes), flush=True)
    return len(notes)


# ------------------------------------------------------------------------------------------------ main
def main():
    if "--live" in sys.argv:
        print("REFUSED: racev2_shadow is paper only; there is no --live", flush=True)
        return 2
    ap = argparse.ArgumentParser(description="Coin Race 1c filler v2 -- PAPER shadow on our own tape")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--follow", action="store_true", help="catch up from the cursor (or --since), then hourly")
    ap.add_argument("--hours", type=float, default=336.0, help="wall-clock run length of --follow (default 14 days)")
    ap.add_argument("--since", default=None, help="first tape hour YYYYMMDDTHH when no cursor exists")
    ap.add_argument("--max-hours", type=int, default=None, help="process at most N tape hours, then exit (smoke)")
    ap.add_argument("--once", action="store_true", help="process the next closed hour, then exit")
    ap.add_argument("--backfill", default=None, help="one ET day YYYYMMDD into its own log, then exit")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--compare-dry", nargs="?", const=os.path.join(RESULTS, "racereward-v2-dry.jsonl"), default=None,
                    help="compare racereward_live v2 --dry-run would_place rows with the shadow (bar >= 90%%)")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--log", default=None)
    ap.add_argument("--state", default=None)
    a = ap.parse_args()
    try:
        selftest(verbose=a.verbose)
    except AssertionError as e:
        print("SELFTEST FAILED: %s -- refusing to read real data" % e, flush=True)
        return 2
    except Exception as e:
        print("SELFTEST ERROR: %r -- refusing to read real data" % e, flush=True)
        return 2
    if a.selftest:
        return 0
    if a.report:
        return report(a.log or LOG, a.days)
    if a.compare_dry:
        v, _ = compare_dry(a.log or LOG, a.compare_dry)
        return 0 if v == "MATCH" else 1
    if not (a.follow or a.once or a.backfill or a.max_hours):
        ap.print_help()
        return 2
    now = time.time()
    if a.backfill:
        D = "%s-%s-%s" % (a.backfill[:4], a.backfill[4:6], a.backfill[6:8])
        start, end = day_bounds(D)
        if now < end + 3600 + HOUR_GRACE_S:
            print("REFUSED: ET day %s is not finished on the tape yet" % D, flush=True)
            return 2
        log_path = a.log or os.path.join(RESULTS, "%s-backfill-%s-%s.jsonl" % (NAME, a.backfill,
                                                                               time.strftime("%H%M%S", time.gmtime())))
        hours = [hour_str(t) for t in range(int(start) - 3600, int(end) + 1, 3600)]
        if not _inside_results(log_path):
            print("REFUSED: racev2_shadow writes only under results/ (%s)" % log_path, flush=True)
            return 2
        lock = rr.InstanceLock(log_path + ".lock")
        if not lock.acquire():
            print("REFUSED: another instance holds %s (%s)" % (log_path + ".lock", lock.holder()), flush=True)
            return 3
        try:
            R = Runner("backfill", log_path, None)
            R.start(sys.argv, hours[0])
            return R.run_hours(hours)
        finally:
            lock.release()
    log_path, state_path = a.log or LOG, a.state or STATE
    since = a.since or hour_str(day_bounds(rr.et_day(now))[0] - 3600)
    if not re.match(r"^\d{8}T\d{2}$", since):
        print("REFUSED: --since must be YYYYMMDDTHH", flush=True)
        return 2
    if not (_inside_results(log_path) and _inside_results(state_path)):
        print("REFUSED: racev2_shadow writes only under results/ (%s, %s)" % (log_path, state_path), flush=True)
        return 2           # checked BEFORE the lock, so no lock file is created outside results/
    lock = rr.InstanceLock(log_path + ".lock")
    if not lock.acquire():
        print("REFUSED: another instance holds %s (%s)" % (log_path + ".lock", lock.holder()), flush=True)
        return 3
    try:
        R = Runner("follow", log_path, state_path)
        R.start(sys.argv, since)
        print("racev2_shadow PAPER start pid %d: next hour %s, races already logged %d, log %s"
              % (os.getpid(), R.state["next_hour"], len(R.logged), log_path), flush=True)
        return R.follow(a.hours, max_hours=a.max_hours, once=a.once)
    except KeyboardInterrupt:
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
