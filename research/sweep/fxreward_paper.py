#!/usr/bin/env python3
"""fxreward_paper.py -- PAPER quoter for the FX 15-minute reward share at the touch (spec 20261015-R1-C2-03).

WHAT IS BEING DECIDED
  Whether resting S = 60 contracts a side at the others' best bid on the FX 15-minute markets (KXEURUSD15M,
  KXGBPUSD15M; JPY/AUD/CAD simulated and reported, not in the bar) earns more Liquidity-Incentive credit than the
  pick-offs a slower quote suffers cost. The credit is settled arithmetic ($2.3-4.8 a window); the fills at our seat
  break even on the public trade tape; the open number is how much MORE than the tape our stale quote loses while a
  cancel is in flight. Only the order-book delta stream shows that, so this file streams fxbook_rec.py's hour files.
  NOTHING HERE PLACES AN ORDER (the self-test scans this file for an order verb). Source rank: (1) recorded book
  and trade frames; V5 calibrates the engine against (3) our own live maker fills. No replay is used.

THE RULE, parameters fixed before any FX book was recorded (nothing fitted on the paper data except the Kraken
guard G, which has a holdout):
  - Markets: every open market of the recorded series with an active program row (period_reward >= 500000
    centi-cents = $50, target 300, discount 5000 bps). A market without one is not quoted.
  - Span: window open (900 s left) to 300 s left (T_STOP).
  - Price: JOIN -- rest S YES at the others' best YES bid and S NO at the others' best NO bid; never improve the
    touch. Only while our order's YES-equivalent price is inside 0.10-0.90 (credit lost to the band is logged).
  - Size S = 60 a side; net position (YES fills minus NO fills) capped at +-S; a side with no room is not quoted,
    and a landing order is clipped to the room left -- S minus the position on that side minus our OTHER live
    orders on that side (an old order whose cancel is still in flight can fill too), so |position| never passes
    S; an order clipped to nothing re-decides the side when the old order dies.
  - Re-peg: decided at the END of each exchange millisecond. If the others' best on our side differs from our
    price -- including when the others LEFT our price and we would be alone above the next level -- cancel and
    re-post at the new best. The new order lands, and the old one dies, at t + L (a cancel needs the order id, so
    nothing dies before its own land time + L); until then the old order is live at its old price with its queue
    place -- that is the pick-off, and it is kept. A landing order that would cross the displayed opposite best is
    rejected (post_only), counted, and re-decided at once.
  - At 300 s left both are cancelled (they die at t + L) and any net position is held to settlement.
  - Our orders are NOT in the recorded book (assumption A1: we change nobody's behaviour).

FILLS (makersim rules 3-6, unchanged, ported to S-lot orders and dollar prices in tenths of a cent)
  ONE budget per print: the taker sold q, so our fills from one print never exceed q -- our orders above the
         print price are reached first (walk, best price first), then the queue at the print price
  queue  a print of q at our price fills min(rem, q_left - ahead - our earlier orders' fills at that price), in
         queue order; ahead falls by q (q_left = q minus the walk fills, capped at the displayed level)
  walk   a print at a price worse than ours while nothing displayed is ahead of us fills min(rem, q_left) (if the
         level still shows size, the credit waits for a same-millisecond delta that empties it)
  cross  a new opposite-side order with our_yes + its_no >= 1.00 while ours is live and nothing shows ahead of us
         fills min(rem, its size)
  queue models: last (every arrival in front of us), fifo_behind, fifo_prorata, fifo_front; ahead <= displayed.
  Every fill is tagged queue / walk / cross and stale (our price was above the others' best when the ms began).
  A trade print is merged BEFORE the deltas of its own millisecond and netted against the next negative delta at
  its level (makersim measured 21,545 of 21,545 on crypto; V3 re-measures it here).

CREDIT (the filing's walk, copied from racereward_live.walk, linear_cent)
  At each whole exchange second from open to T_STOP, per side, walk the others' displayed levels plus our live
  order; the second counts only if BOTH sides reach the target. Credit = reward x sum over counted seconds of
  (our YES share + our NO share) / (2 x period seconds); a market-period pays only if that is >= $1.00 (the floor);
  payout factor 0.9 (the one measured payout, coin race 10-11) applied in the report, 1.0 shown beside it.

P&L PER FILL
  settlement: won - price (YES at p plus NO at q nets to exactly 1 - p - q); markouts at +10 s and +60 s against
  the others' book mid (1 - mid for NO fills), each with a RANDOM-SIGN control (the same fills, side flipped by a
  seeded coin; it must sit inside its own MDE). Net per window = credit (floored, x payout) + fills marked at 60 s.

VARIANTS (one engine pass feeds all 26): S = 60 x L in {50, 150, 300, 600, 1000} ms x the 4 queue models;
  S = 100 and S = 300 at L = 300 fifo_prorata; Kraken guard -- pull a side for 2 s when the Kraken mid moved >= G
  pips against it over the last 500 ms (mid now minus the mid 500 ms earlier), G in {0.3, 0.5, 1, 2}, chosen on
  trading days 1-2 and read on days 3-5 only. Kraken frames are placed on the exchange clock at _rx_ms minus the
  hour's measured Kalshi delta lag (median _rx_ms - ts_ms): AN ASSUMPTION, stated in every report.
  Report-only: Kraken lead/lag -- for each Kalshi "flight" (>= 50% of the best level's size cancelled within 300 ms
  with no print at it) the Kraken mid change in the 2 s before it (signed: positive = against the side that fled)
  and the median lead (flight time minus the last Kraken mid change before it, within 2 s).

DAYS: "ET day" = ET calendar day of the close (G5, the per-day summary rows). "Trading day" (the 5 weekdays, days
  1-2 / 3-5, the guard holdout) = the FX day 17:00 ET -> 17:00 ET, labelled by the ET date it ends on -- that is
  what makes the spec's 96 windows a weekday, 88 on Thursday, ~470 a week. A "complete weekday" = a weekday FX day
  with >= 60 non-void record-variant windows (FULL_DAY_MIN: the BUILDER'S definition -- the spec gives none).
  The credit KILL line ($1.50) is read on credit AFTER the 0.9 payout (the builder's reading; --report prints both).

VALIDATION GATES -- any failure VOIDS the read (it is not a pass and not a kill):
  V1 book integrity: the rebuilt best YES bid and its size, and best YES ask (1 - best NO bid) and its size, equal
     the `ticker` channel's (price exact, size within max(1, 2%) -- research/lipcheck.py's tolerance) in >= 99% of
     sampled market-seconds (first ticker frame per market-second, state at the end of its millisecond).
  V2 completeness: prints per market sum to the settled volume_fp (within max(0.5, 0.2%)) in >= 95% of windows.
  V3 merge: >= 95% of trades are consumed by a negative delta at their level in the SAME millisecond.
  V4 coverage: >= 90% of rewarded windows per pair recorded from open to T_STOP (first snapshot at or before the
     open) with < 5 s suspect (recorder suspect spans, plus any heartbeat gap > 15 s). A window failing it is void.
  V5 engine calibration on OUR OWN live maker fills (--v5): the penny ladder's real Kalshi orders
     (results/ladder-live-orders.jsonl: `placed` with the exchange ts_ms, `cancelled`, `live_fill`) replayed through
     the SAME engine on C:\\kals\\kalshi_data (read-only, one hour file at a time), fifo_prorata, orders landing at
     their exchange time. Engine contracts must land within 0.67-1.5x of live and the 60 s markout within
     1c/contract of live. (The spec named results/ladder-live.jsonl's order/fill rows; those are the ladder's own
     paper model -- size_opt/size_pess -- not Kalshi fills, so V5 uses the Kalshi-confirmed rows.) Hours that
     ended less than 15 min before the run are left out (still being written). The bar uses ONLY the last V5 row
     that is scope "full" (no --from/--to/--max-hours/--max-seconds cut), complete, and written by THIS code
     (sha256[:12] equal to the paper run's): any code change means V5 is re-run. The 10 s markout is printed beside
     the 60 s one (report only: the ladder fills in the last ~30 s, so its 60 s marks mostly resolve to settlement).

THE PRE-REGISTERED BAR (spec section 5, quoted exactly; --report prints the verdict against it):

  "Read **after 5 complete weekdays of recording** (target Mon 10-19 to Fri 10-23, about 450-470 rewarded windows per
  pair; minimum 400 per pair with V1-V5 passing). Due **2026-10-24T12:00Z**. Variant of record: S = 60, join, T_STOP 300 s,
  net cap 60, band 10-90c, payout 0.9, `fifo_prorata`. Primary metric: **net per window = credit + fills marked at 60 s**
  (markout, 4-5x less noisy than settlement); settlement P&L is the cross-check. n = windows; EURUSD and GBPUSD share
  close times, so the pooled SE clusters by close.

  - **GO to a live micro (operator sign-off still required) for a pair if ALL of:**
    - G1 at L = 300 ms: mean net >= **+$1.00 per window**, 95% lower bound of the mean > $0, and the late half (days 3-5)
      mean >= +$0.50.
    - G2 at L = 300 ms under `last` (worst queue): mean net >= $0.
    - G3 settlement mean net is not below the markout mean by more than 2 SE (the markout is not hiding a drift).
    - G4 the engine sees pick-offs: >= 1 stale fill per 10 windows at L = 300 (zero means it is blind -> void, not GO).
    - G5 tails at S = 60 (settlement): worst window >= -$45, worst ET day >= -$150.
  - **KILL the family for a pair if:** at L = 150 ms `fifo_prorata` the mean net < $0 with the 95% upper bound < +$1.00
    (even a fast quoter pays the credit away), OR the mean credit at S = 60 < $1.50 per window (the share collapsed or
    the pot was cut).
  - **Otherwise INCONCLUSIVE:** extend once by 5 weekdays (about 930 windows per pair), then GO only on G1-G5, else KILL.
  - **MDE:** per-window SD of the markout net is estimated at $4-6 (refuter: 0.62c/contract SE over 100 windows at ~70
    fills) -> SE about $0.25 over 470 windows -> smallest detectable effect about **$0.70 per window** (95%, 80% power),
    below the $1.00 GO line. Settlement alone (SD ~$28/window) detects only about $3.60 -- it cannot decide. If the
    measured markout SD exceeds $10/window the report must say "no power", not "no effect"."

  The live micro's own bar (set by the test, not read here): credit >= 80% of the formula for our resting size; fill
  P&L per contract no worse than 2c below this paper's prediction for the same windows and variant; net >= $0 over
  96 windows.

OUTPUT
  results/fxbook/paper/<YYYYMMDD of the close, UTC>.jsonl.gz -- one row per (window, variant) (gitignored with
  results/fxbook/; ~26 variants x ~480 windows a day). results/fxreward-paper.jsonl -- start, paper_hour,
  validation (V1/V3 per hour), one summary row per (ET day, pair, variant); V5 writes v5_start (code sha, argv,
  scope, hours), one v5_hour row per replayed hour (a crash leaves a trace), and validation_v5 at the end.

REVIEW FIXES 2026-10-17 (v2), each with a self-test that fails on the old behaviour:
  1. gzip is read by gz_lines (here), streamed in bounded memory in every file state; gzsalvage's whole-file
     salvage pass is never used (it took ~3.4 MB of RAM per decompressed MB: ~2.7 GB on the collector's current
     delta hour). V5 leaves out unfinished hours, writes start / per-hour rows with the code sha, and only a full,
     complete run of this code counts for the bar.
  2. A recorder that dies inside an hour voids the windows it was down for: the hour's last heartbeat is checked
     against the NEXT hour's first one. --batch, like --follow, skips an hour until 15 min after it ends.
  3. One print fills at most its own size across all our orders; two of our orders on one side never take the
     position past S (see the Size rule and FILLS).
  4. Kraken frames are streamed, not held for the hour; the --follow day buffer keeps compact tuples, not rows.
  The self-test itself peaked at 148 MB (v1: 144 MB) -- its 120-window null world buffered every frame before
  writing; it now writes one 15-min slot at a time: peak ~70 MB, ~64 MB left when main() goes on to the real work.
  Also: a mark due after the close is always the settlement value (defensive: the quoter's own marks are all due
  before the close, T_STOP being 300 s before it); each gate (G1 late half, G3, G4, G5 window and day, KILL upper bound, credit after payout,
  V1, MIN_WINDOWS, V5 tolerance) has its own planted check.

USAGE
    python research/sweep/fxreward_paper.py --selftest
    python research/sweep/fxreward_paper.py --follow              # each finished hour (start_fxreward_paper.ps1)
    python research/sweep/fxreward_paper.py --batch [--from H --to H]
    python research/sweep/fxreward_paper.py --report
    python research/sweep/fxreward_paper.py --v5 [--from H --to H --max-hours N --max-seconds S]

stdlib only (research/tdist.py for t critical values; gzip read by gz_lines here, in bounded memory). Each process
stays well under 150 MB: one hour of trades and tickers in memory; the delta and Kraken files streamed;
open markets only.
"""
import argparse
import collections
import ctypes
import datetime as dt
import glob
import gzip
import hashlib
import heapq
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
import time
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(RESEARCH)
RESULTS = os.path.join(REPO, "results")
sys.path.insert(0, RESEARCH)
from tdist import crit as tcrit                                       # noqa: E402
import zlib                                                            # noqa: E402

UTC = dt.timezone.utc
YES, NO = 0, 1
EPS = 1e-6
FX_SERIES = ("KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M", "KXAUDUSD15M", "KXUSDCAD15M")
STAGE2_SERIES = ("KXPALLADIUM15M", "KXPLATINUM15M")
BAR_SERIES = ("KXEURUSD15M", "KXGBPUSD15M")
SERIES_PAIR = {"KXEURUSD15M": "EUR/USD", "KXGBPUSD15M": "GBP/USD", "KXUSDJPY15M": "USD/JPY",
               "KXAUDUSD15M": "AUD/USD", "KXUSDCAD15M": "USD/CAD"}
PIP = {"USD/JPY": 0.01}                     # every other pair: 0.0001
T_OPEN_S, T_STOP_S = 900, 300
BAND = (100, 900)                           # tenths of a cent, YES-equivalent price of OUR order, inclusive
TOP = 990                                   # the filing: the highest bid must be under the highest price (0.99)
PROGRAM_RULE = {"period_reward": 500000, "target": 300.0, "df_bps": 5000}
PAYOUT, PAYOUT_ALT = 0.9, 1.0
FLOOR_USD = 1.00
LATENCIES = (50, 150, 300, 600, 1000)
MODELS = ("last", "fifo_behind", "fifo_prorata", "fifo_front")
GUARDS = (0.3, 0.5, 1.0, 2.0)
GUARD_WINDOW_MS, GUARD_PULL_MS = 500, 2000
MARK_MS = (10000, 60000)
FLIGHT_FRAC, FLIGHT_MS, LEAD_MS = 0.5, 300, 2000
PEND_TTL = 2000
HB_GAP_MS = 15000
WARM_HOURS = 8
FOLLOW_WAIT_S = 15 * 60                     # an hour is processed once its end is this far behind (settlements in)
FXBOOK = os.path.join(RESULTS, "fxbook")
PAPER_DIR = os.path.join(FXBOOK, "paper")
SUMMARY_LOG = os.path.join(RESULTS, "fxreward-paper.jsonl")
STOP_PATH = os.path.join(RESULTS, "fxreward-paper.stop")
LOCK_PATH = os.path.join(RESULTS, "fxreward-paper.lock")
LADDER_ORDERS = os.path.join(RESULTS, "ladder-live-orders.jsonl")
KALSHI_DATA = r"C:\kals\kalshi_data"
RSS_ABORT_MB = 150.0
V1_MIN, V2_MIN, V3_MIN, V4_MIN = 0.99, 0.95, 0.95, 0.90
V5_RATIO = (0.67, 1.5)
V5_MARK_C = 1.0
MIN_WINDOWS = 400
TRADING_DAYS_NEEDED = 5
FULL_DAY_MIN = 60          # BUILDER'S definition, not in the spec: a "complete weekday" has >= 60 non-void windows
WEEKDAY_WINDOWS, CAL_WINDOWS = 96.0, 470.0 / 7.0

Variant = collections.namedtuple("Variant", "name S L q G")


def default_variants():
    out = [Variant("S60_L%d_%s" % (L, q), 60, L, q, None) for L in LATENCIES for q in MODELS]
    out.append(Variant("S100_L300_fifo_prorata", 100, 300, "fifo_prorata", None))
    out.append(Variant("S300_L300_fifo_prorata", 300, 300, "fifo_prorata", None))
    out += [Variant("S60_L300_fifo_prorata_G%s" % g, 60, 300, "fifo_prorata", g) for g in GUARDS]
    return out


RECORD = "S60_L300_fifo_prorata"
FAST = "S60_L150_fifo_prorata"
WORSTQ = "S60_L300_last"


class UnitError(ValueError):
    pass


class RssAbort(RuntimeError):
    """Raised inside a stream when the process passes RSS_ABORT_MB; run_hour turns it into 'rss_abort'."""


def _sidekey(e):
    return (e[0], e[1])


# ================================================================================================ units and time
def px(s):
    """A `*_dollars` price string -> tenths of a cent ('0.5500' -> 550). The unit is the FIELD's (dollars), never
    inferred from the magnitude (hard rule 5); outside [0, 1] dollars aborts."""
    try:
        v = Decimal(str(s))
    except (InvalidOperation, ValueError, TypeError):
        raise UnitError("unreadable dollar price %r" % (s,))
    if v < 0 or v > 1:
        raise UnitError("dollar price outside [0, 1]: %r -- refusing to rescale" % (s,))
    return int((v * 1000).to_integral_value())


def cc_to_usd(x):
    """`period_reward` is CENTI-CENTS (the program schema's unit): 500000 -> 50.00 dollars."""
    return float(Decimal(str(x)) / Decimal(10000))


def iso_ms(s):
    try:
        return int(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def utc_iso(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def ms_iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def hour_start_ms(tag):
    return int(dt.datetime.strptime(tag, "%Y%m%dT%H").replace(tzinfo=UTC).timestamp() * 1000)


def hour_of_ms(ms):
    return dt.datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y%m%dT%H")


def next_hour(tag):
    return hour_of_ms(hour_start_ms(tag) + 3600 * 1000)


def _nth_sunday(y, month, n):
    d = dt.datetime(y, month, 1, tzinfo=UTC)
    return d + dt.timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))


def et_offset_h(t):
    """-4 (EDT) from the 2nd Sunday of March 07:00Z to the 1st Sunday of November 06:00Z, else -5 (EST)
    (racereward_live.et_offset_h, copied)."""
    d = dt.datetime.fromtimestamp(t, UTC)
    a = _nth_sunday(d.year, 3, 2) + dt.timedelta(hours=7)
    b = _nth_sunday(d.year, 11, 1) + dt.timedelta(hours=6)
    return -4 if a <= d < b else -5


def et_day(ms):
    t = (ms - 1) / 1000.0
    return (dt.datetime.fromtimestamp(t, UTC) + dt.timedelta(hours=et_offset_h(t))).strftime("%Y-%m-%d")


def fx_day(ms):
    """The FX trading day a window closing at `ms` belongs to: 17:00 ET -> 17:00 ET, labelled by its end date."""
    t = (ms - 1) / 1000.0
    return (dt.datetime.fromtimestamp(t, UTC) + dt.timedelta(hours=et_offset_h(t) + 7)).strftime("%Y-%m-%d")


def code_sha():
    with open(os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def variants_hash(vs):
    return hashlib.sha256(json.dumps([list(v) for v in vs]).encode()).hexdigest()[:8]


def rss_mb():
    try:
        if sys.platform == "win32":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            fn = getattr(k32, "K32GetProcessMemoryInfo", None) or ctypes.windll.psapi.GetProcessMemoryInfo
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
            if not fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return -1.0
            return pmc.WorkingSetSize / 1048576.0
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return -1.0


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    k = len(xs) // 2
    return xs[k] if len(xs) % 2 else 0.5 * (xs[k - 1] + xs[k])


def _bump(st, k, n=1):
    if st is not None:
        st[k] = st.get(k, 0) + n


# ================================================================================================ bounded-memory gzip
GZ_MAGIC = b"\x1f\x8b\x08"
GZ_READ = 1 << 18            # raw bytes per read
GZ_FEED = 1 << 14            # raw bytes per decompress call: a member that breaks loses at most this call's output
GZ_OUT_MAX = 1 << 22         # decompressed bytes per call (bounds a pathological compression ratio)
GZ_TRIAL = 1 << 18           # raw bytes a candidate member's first line must come out of
GZ_MAX_LINE = 1 << 24        # a fragment this long with no newline is dropped (a corrupt stream)
GZ_HOLD = 1 << 16            # raw bytes of a member decoded but not yet yielded (the garbage hold-back)


def _gz_member_at(fh, off):
    """True if a gzip member plausibly starts at byte `off`: its header parses, and what it decompresses to BEFORE
    any error (fed in small pieces, so a member that itself breaks later still counts) holds a complete first line
    that looks like a JSONL record ('{' ... '}'). A chance magic inside compressed data never does."""
    fh.seek(off)
    blob = fh.read(GZ_TRIAL)
    d = zlib.decompressobj(31)
    out = b""
    for i in range(0, len(blob), 512):
        piece = blob[i:i + 512]
        snap = d.copy()
        try:
            out += d.decompress(piece, 1 << 20)
        except zlib.error:
            d = snap
            for j in range(len(piece)):
                try:
                    out += d.decompress(piece[j:j + 1])
                except zlib.error:
                    break
            break
        if b"\n" in out or d.eof or len(out) >= (1 << 20):
            break
    k = out.find(b"\n")
    if k < 0:
        return False
    first = out[:k].strip()
    return first.startswith(b"{") and first.endswith(b"}")


def _gz_next_member(fh, frm):
    """Offset of the first plausible member header at or after `frm`, or None. Streamed in 1 MB blocks."""
    pos, tail = frm, b""
    while True:
        fh.seek(pos)
        blk = fh.read(1 << 20)
        if not blk:
            return None
        hay = tail + blk
        base = pos - len(tail)
        i = 0
        while True:
            j = hay.find(GZ_MAGIC, i)
            if j < 0:
                break
            if base + j >= frm and _gz_member_at(fh, base + j):
                return base + j
            i = j + 1
        tail = hay[-2:]
        pos += len(blk)


def _gz_split(data):
    """Complete lines of `data` (CR removed) and the trailing fragment."""
    k = data.rfind(b"\n")
    if k < 0:
        return [], data
    out = []
    for ln in data[:k].decode("utf-8", "replace").split("\n"):
        if ln and ln[-1] == "\r":
            ln = ln[:-1]
        if ln:
            out.append(ln)
    return out, data[k + 1:]


def _gz_decode_upto(fh, snap, carry, a0, cut):
    """(lines, ok): the lines decoded from raw bytes [a0, cut), starting from decompressor state `snap` and fragment
    `carry`. ok = False if the bytes before the cut themselves fail to decode (corruption inside the member)."""
    fh.seek(a0)
    blob = fh.read(cut - a0)
    d = snap.copy()
    try:
        out = d.decompress(blob) + d.flush()
    except zlib.error:
        return [], False
    return _gz_split(carry + out)[0], True


def gz_lines(path, stat=None):
    """The text lines (WITHOUT the line end; a trailing CR of the recorders' Windows CRLF is removed, as text mode
    does) of a gzip JSONL file, in BOUNDED memory whatever state the file is in: one or many members; an untrailered
    last member (the hour still being written, or a hard kill) yields every complete line flushed so far; a broken
    member followed by a restart's new member (the collector's crash case, gzsalvage.py's docstring) yields the
    first member's lines up to the break, then resyncs on the next real member header (a candidate must decompress
    to a '{...}' first line). The file is never read whole (review 2026-10-17, must-fix 1: gzsalvage's salvage
    pass loads and decompresses the whole file, ~3.4 MB of RAM per decompressed MB -- 2.7 GB on the collector's
    current delta hour).
    HOLD-BACK: the last GZ_HOLD raw bytes of a member are decoded but not yet yielded. A member killed in the middle
    of a block makes the decoder read the NEXT member's bytes as data and emit garbage until it errors; a member
    corrupted on disk does the same (seen on 2026-09-02/03 collector files: '{"type":"determint_lifecycle_v2",...}'
    parses as JSON). When a member breaks: if the next member starts at or before the error, the piece holding that
    start is decoded again from its own saved state up to that byte only, so exactly the genuine lines are kept;
    if the error comes before any next member (corruption inside the member, its start unknown), the held-back
    lines are dropped (gz_garbage_lines_dropped counts both). A fragment that never got its newline is dropped and
    counted (gz_fragments_dropped). Measured 2026-10-17 on the 24 broken / untrailered collector lifecycle files
    (2026-08-25..10-14): gz_lines yields 97,382 lines, every one a valid frame; gzsalvage yields 99,142, of which
    1,750 are not valid frames, and 10 valid-looking frames that gz_lines drops (all in the hold-back of 5 files
    corrupted inside a member, so genuine or garbage cannot be told)."""
    try:
        fh = open(path, "rb")
    except OSError:
        return
    with fh:
        start = pos = 0                  # current member's first byte; file offset of `pend`'s first byte
        d = zlib.decompressobj(31)
        fed = False
        carry = b""
        pend = b""
        hold = collections.deque()       # (raw start, raw end, [lines]) of the newest pieces of this member
        held = 0
        while True:
            if not pend:
                fh.seek(pos)
                pend = fh.read(GZ_READ)
                if not pend:
                    break
            piece, pend = pend[:GZ_FEED], pend[GZ_FEED:]
            fed = True
            err_at = None
            snap = d.copy()
            carry0 = carry
            outs = []
            data_in = piece
            try:
                while True:
                    o = d.decompress(data_in, GZ_OUT_MAX)
                    if o:
                        outs.append(o)
                    data_in = d.unconsumed_tail
                    if d.eof or not data_in:
                        break
            except zlib.error:
                # decompress() raises WITHOUT the output it had already made: this piece's lines are recovered below,
                # by decoding it again from `snap` up to the next member's start
                outs = []
                err_at = pos + len(piece)
            lines = []
            for o in outs:
                data = carry + o if carry else o
                k = data.rfind(b"\n")
                if k < 0:
                    carry = data
                    if len(carry) > GZ_MAX_LINE:
                        _bump(stat, "gz_fragments_dropped")
                        carry = b""
                    continue
                carry = data[k + 1:]
                for ln in data[:k].decode("utf-8", "replace").split("\n"):
                    if ln and ln[-1] == "\r":
                        ln = ln[:-1]
                    if ln:
                        lines.append(ln)
            outs = None
            hold.append((pos, pos + len(piece), lines, snap, carry0))
            held += len(piece)
            while hold and held - (hold[0][1] - hold[0][0]) >= GZ_HOLD:
                a0, b0, ls = hold.popleft()[:3]
                held -= b0 - a0
                for ln in ls:
                    yield ln
            if err_at is not None:
                _bump(stat, "gz_broken_members")
                if carry:
                    _bump(stat, "gz_fragments_dropped")
                    carry = b""
                nxt = _gz_next_member(fh, start + 1)
                if nxt is not None and nxt <= err_at:
                    cut = nxt                    # this member ends where the next begins; anything decoded from the
                    #                              next member's bytes (a mid-block kill) is garbage and is cut off
                else:
                    cut = -1                     # corrupt inside the member, the point unknown: drop the hold-back
                good, ok = None, True
                if cut >= 0:
                    for a0, b0, ls, snap0, carry_0 in hold:
                        if a0 < cut < b0:
                            # the piece holding the cut: decode again from its own start, bytes before the cut only
                            good, ok = _gz_decode_upto(fh, snap0, carry_0, a0, cut)
                    if not ok:
                        cut = -1                 # the bytes before the next member are corrupt too: drop the hold-back
                if hold and hold[0][0] > cut >= 0:
                    _bump(stat, "gz_garbage_maybe_yielded")
                for a0, b0, ls, snap0, carry_0 in hold:
                    if cut >= 0 and b0 <= cut:
                        for ln in ls:
                            yield ln
                    elif cut >= 0 and a0 < cut:
                        for ln in good:
                            yield ln
                        _bump(stat, "gz_garbage_lines_dropped", max(0, len(ls) - len(good)))
                    else:
                        _bump(stat, "gz_garbage_lines_dropped", len(ls))
                hold.clear()
                held = 0
                if nxt is None:
                    fed = False              # broken, not untrailered: counted above
                    break
                _bump(stat, "gz_resyncs")
                start = pos = nxt
                pend = b""
                d = zlib.decompressobj(31)
                fed = False
                continue
            if d.eof:
                end = pos + len(piece) - len(d.unused_data)
                if carry:
                    _bump(stat, "gz_fragments_dropped")
                    carry = b""
                for e0 in hold:
                    for ln in e0[2]:
                        yield ln
                hold.clear()
                held = 0
                pend = d.unused_data + pend
                start = pos = end
                d = zlib.decompressobj(31)
                fed = False
                continue
            pos += len(piece)
        for e0 in hold:                      # end of file: an untrailered tail decodes correctly up to the cut
            for ln in e0[2]:
                yield ln
        if fed and not d.eof:
            _bump(stat, "gz_untrailered")
        if carry:
            _bump(stat, "gz_fragments_dropped")


# ================================================================================================ the credit walk
def ticks(hi, lo):
    """Ticks from lo up to hi on the linear_cent grid (prices in tenths of a cent); 0 when lo >= hi."""
    return 0 if hi <= lo else int(round((hi - lo) / 10.0))


def walk(levels, target, df, ours=None, no_qual=False):
    """The filing's walk for ONE side (racereward_live.walk, linear=True, generalised to our order(s) {px: size}).
    `levels` = everyone ELSE's bids {px: size}. Highest bid must be under 0.99; walk best-first adding whole levels;
    reference = the first level where the running size reaches target/5; stop where it reaches target; no qualifying
    bids if it never does. Score = df ** ticks below the reference x size. Returns (qualifies, ref, size walked,
    our normalised share). `no_qual` is the self-test's mutant (scores every level, never disqualifies)."""
    if ours:
        d = dict(levels)
        for p, s in ours.items():
            if s > EPS:
                d[p] = d.get(p, 0.0) + s
    else:
        d = levels
    pxs = sorted((p for p, s in d.items() if s > EPS), reverse=True)
    if not pxs:
        return (False, None, 0.0, 0.0)
    if pxs[0] >= TOP and not no_qual:
        return (False, None, 0.0, 0.0)
    tot, ref, used, reached = 0.0, None, [], False
    for p in pxs:
        tot += d[p]
        used.append(p)
        if ref is None and tot >= target / 5.0 - 1e-9:
            ref = p
        if tot >= target - 1e-9 and not no_qual:
            reached = True
            break
    if no_qual:
        reached = True
        ref = ref if ref is not None else pxs[0]
    if not reached:
        return (False, ref, tot, 0.0)
    s_all = sum(df ** ticks(ref, p) * d[p] for p in used)
    s_us = 0.0
    if ours:
        for p, s in ours.items():
            if s > EPS and p in used:
                s_us += df ** ticks(ref, p) * s
    return (True, ref, tot, (s_us / s_all) if s_all > 0 else 0.0)


def credit_usd(reward_usd, period_s, share_sum):
    """reward x (sum over counted seconds of our YES + NO share) / (2 x seconds in the period)."""
    return reward_usd * share_sum / (2.0 * period_s) if period_s and period_s > 0 else 0.0


def floored(x):
    return x if x >= FLOOR_USD - 1e-9 else 0.0


# ================================================================================================ the engine
class Order(object):
    __slots__ = ("price", "rem", "ahead", "ahead0", "land_at", "die_at", "landed", "stale", "kid")

    def __init__(self, price, size, land_at, die_at=None, kid=None):
        self.price, self.rem, self.land_at, self.die_at, self.kid = price, float(size), land_at, die_at, kid
        self.ahead = self.ahead0 = 0.0
        self.landed = False
        self.stale = False


class Fill(object):
    __slots__ = ("s", "price", "q", "ts", "mech", "stale", "marks", "eps", "kid")

    def __init__(self, s, price, q, ts, mech, stale, eps, kid=None):
        self.s, self.price, self.q, self.ts, self.mech, self.stale, self.eps, self.kid = \
            s, price, q, ts, mech, stale, eps, kid
        self.marks = [None, None]


class VS(object):
    """One variant's state in one market."""
    __slots__ = ("orders", "inv", "writes", "rejects", "cap_drops", "sh", "counted", "scored", "rest_s", "fills",
                 "stale_ep", "stale_ms", "pulled", "reason", "band_out_s", "band_lost", "guard_pulls",
                 "inv_at_stop", "max_abs_inv", "exposure_clips")

    def __init__(self):
        self.orders = [[], []]
        self.inv = 0.0
        self.max_abs_inv = 0.0
        self.exposure_clips = 0
        self.writes = self.rejects = self.cap_drops = self.counted = self.scored = 0
        self.sh = [0.0, 0.0]
        self.rest_s = [0, 0]
        self.fills = []
        self.stale_ep = 0
        self.stale_ms = 0
        self.pulled = [-1, -1]
        self.reason = [None, None]
        self.band_out_s = [0, 0]
        self.band_lost = 0.0
        self.guard_pulls = 0
        self.inv_at_stop = None


class Mkt(object):
    def __init__(self, tk, nvar):
        self.tk = tk
        self.series = tk.split("-")[0]
        self.pair = SERIES_PAIR.get(self.series)
        self.books = ({}, {})
        self.best = [None, None]
        self.pending = {}               # (s, p) -> [print qty not yet netted, ts of the last print]
        self.v3 = {}                    # (s, p, ts) -> [print qty, same-ms consumed qty, n trades]
        self.walk_pending = []
        self.sid = None
        self.snap = False
        self.first_snap_ts = None
        self.open_ms = self.close_ms = self.tstop_ms = None
        self.prog = None
        self.last_ts = None
        self.touch0 = [None, None]
        self.size0 = [0.0, 0.0]
        self.dirty = True
        self.vs = [VS() for _ in range(nvar)]
        self.marks = []                 # heap (due, vi, fill index, which) ; vi = -1 -> a probe (V5 live fill)
        self.probes = []
        self.suspect = False
        self.suspect_ms = 0
        self.flight = [None, None]
        self.prints = 0.0
        self.n_trades = 0
        self.events = 0
        self.scheduled = False
        self.quiet_since = None
        self.wakes = []                 # decision times after an exposure cap-drop (the old order's death)

    def prog_ok(self):
        return bool(self.prog and self.prog.get("ok"))


class Engine(object):
    def __init__(self, variants=None, prefixes=None, meta=None, mut_lat0=False, mut_ignore_queue=False,
                 mut_no_qual=False, seed=20261017, scheduled=False):
        self.variants = list(variants or default_variants())
        self.prefixes = tuple(prefixes or (s + "-" for s in FX_SERIES))
        self.meta = meta
        self.mut_lat0, self.mut_ignore_queue, self.mut_no_qual = mut_lat0, mut_ignore_queue, mut_no_qual
        self.scheduled = scheduled
        self.markets = {}
        self.stat = collections.Counter()
        self.rng = random.Random(seed)
        self.kr_books = {}               # symbol -> {"b": {price: qty}, "a": {...}}
        self.kr_hist = collections.defaultdict(collections.deque)    # symbol -> deque[(ts, mid)]
        self.kr_last_change = {}
        self.active_by_pair = collections.defaultdict(set)
        self.v1 = collections.Counter()
        self.v3 = collections.Counter()
        self.flights = []
        self.lag_ms = 30
        self.last_hb_rx = None
        self.guard_idx = [i for i, v in enumerate(self.variants) if v.G is not None]
        self.injected = collections.defaultdict(list)   # tk -> [(vi, side, price, size, land, die, kid)]
        self._new_lands = []
        self._new_wakes = []
        self.kr_emit = {}                                 # symbol -> last mid streamed (kraken_iter)
        self.trade_windows = None                         # V5: tk -> [(lo, hi)] -- prints outside are not needed

    # ---------------------------------------------------------------- markets and meta
    def market(self, tk, create=True):
        m = self.markets.get(tk)
        if m is None and create:
            m = self.markets[tk] = Mkt(tk, len(self.variants))
            m.scheduled = self.scheduled
            self.apply_meta(m)
            for (vi, s, price, size, land, die, kid) in self.injected.pop(tk, []):
                m.vs[vi].orders[s].append(Order(price, size, land, die, kid))
        return m

    def apply_meta(self, m):
        info = self.meta.get(m.tk) if self.meta is not None else None
        if not info:
            return
        if info.get("open_ms") and info.get("close_ms"):
            m.open_ms, m.close_ms = info["open_ms"], info["close_ms"]
            m.tstop_ms = m.close_ms - T_STOP_S * 1000
        if info.get("prog"):
            m.prog = info["prog"]

    def refresh_meta(self):
        for m in self.markets.values():
            self.apply_meta(m)

    def inject(self, tk, vi, side, price, size, land, die, kid):
        """V5: a real order replayed at its exchange land time and its cancel time (scheduled mode)."""
        m = self.markets.get(tk)
        if m is None:
            self.injected[tk].append((vi, side, price, size, land, die, kid))
        else:
            m.vs[vi].orders[side].append(Order(price, size, land, die, kid))

    def probe(self, tk, due, key):
        m = self.market(tk)
        idx = len(m.probes)
        m.probes.append([key, None])
        heapq.heappush(m.marks, (due, -1, idx, 0))

    # ---------------------------------------------------------------- book helpers (makersim)
    @staticmethod
    def _recompute_best(m, s):
        b = m.books[s]
        m.best[s] = max((p for p, z in b.items() if z > EPS), default=None)

    def _deff(self, m, s, p, ts):
        d = m.books[s].get(p, 0.0)
        pe = m.pending.get((s, p))
        if pe is not None and ts - pe[1] <= PEND_TTL:
            d -= pe[0]
        return d if d > 0.0 else 0.0

    @staticmethod
    def _live(o, ts):
        return o.landed and (o.die_at is None or o.die_at > ts)

    def _mid(self, m):
        if m.best[YES] is None or m.best[NO] is None:
            return None
        return 0.5 * (m.best[YES] + (1000 - m.best[NO]))

    def _lat(self, vi):
        return 0 if self.mut_lat0 else self.variants[vi].L

    # ---------------------------------------------------------------- time
    def _advance(self, m, ts):
        """Bring market m to exchange time ts: the decision at the end of the last millisecond, then the timeline
        (open, T_STOP, guard expiries, landings and deaths, whole-second credit snapshots) up to ts."""
        if m.last_ts is None:
            m.last_ts = ts
            m.touch0 = list(m.best)
            m.size0 = [m.books[s].get(m.best[s], 0.0) if m.best[s] is not None else 0.0 for s in (YES, NO)]
            return
        if ts <= m.last_ts:
            return
        base = m.last_ts
        self._v3_close(m, base)
        if m.walk_pending:
            self.stat["anom_walk_past_nonempty_uncredited"] += len(m.walk_pending)
            m.walk_pending = []
        if m.dirty:
            self._decide(m, base)
            m.dirty = False
        self._stale_accrue(m, base, ts)
        if m.suspect and m.open_ms is not None:
            lo, hi = max(base, m.open_ms), min(ts, m.tstop_ms)
            if hi > lo:
                m.suspect_ms += hi - lo
        self._timeline(m, base, ts)
        while m.marks and m.marks[0][0] < ts:
            if m.close_ms is not None and m.marks[0][0] > m.close_ms:
                break                    # a mark due after the close is the settlement value: finish() sets it
            due, vi, idx, which = heapq.heappop(m.marks)
            self._resolve_mark(m, vi, idx, which, self._mid(m))
        m.last_ts = ts
        m.touch0 = list(m.best)
        m.size0 = [m.books[s].get(m.best[s], 0.0) if m.best[s] is not None else 0.0 for s in (YES, NO)]

    def _resolve_mark(self, m, vi, idx, which, mid):
        if vi < 0:
            m.probes[idx][1] = mid
        else:
            m.vs[vi].fills[idx].marks[which] = mid

    def _timeline(self, m, base, ts):
        """Every point in (base, ts] where something happens with no tape event: the open and T_STOP decisions,
        guard expiries, each order's landing (post_only is checked AT landing and a rejection is re-decided at
        once), and the whole-second credit snapshots. A heap, so landings created inside the interval are kept."""
        pts = []
        if not m.scheduled:
            if m.open_ms is not None:
                if base < m.open_ms <= ts:
                    pts.append((m.open_ms, 1))
                if base < m.tstop_ms <= ts:
                    pts.append((m.tstop_ms, 1))
                if m.prog_ok():
                    lo, hi = max(base + 1, m.open_ms), min(ts, m.tstop_ms - 1)
                    if lo <= hi:
                        for T in range(((lo + 999) // 1000) * 1000, hi + 1, 1000):
                            pts.append((T, 0))
            for vi in self.guard_idx:
                for s in (YES, NO):
                    pu = m.vs[vi].pulled[s]
                    if base < pu <= ts:
                        pts.append((pu, 1))
        for vs in m.vs:
            for s in (YES, NO):
                for o in vs.orders[s]:
                    if not o.landed and base < o.land_at <= ts:
                        pts.append((o.land_at, 2))
        for w in m.wakes:
            if base < w <= ts:
                pts.append((w, 1))
        heapq.heapify(pts)
        while pts:
            P, kind = heapq.heappop(pts)
            self._new_lands = []
            self._new_wakes = []
            if self._land_die(m, P):
                self._decide(m, P)
            if kind == 0:
                self._score(m, P)
            elif kind == 1:
                self._decide(m, P)
            for la in self._new_lands:
                if P < la <= ts:
                    heapq.heappush(pts, (la, 2))
            for wk in self._new_wakes:
                if P < wk <= ts:
                    heapq.heappush(pts, (wk, 1))
        self._new_lands = []
        self._new_wakes = []
        if self._land_die(m, ts):
            self._decide(m, ts)
        self._new_lands = []
        self._new_wakes = []
        if m.wakes:
            m.wakes = [w for w in m.wakes if w > ts]

    def _land_die(self, m, P):
        """Orders whose land time / death time has come. Returns True if something needs a decision now."""
        redo = False
        for vi, vs in enumerate(m.vs):
            cap = self.variants[vi].S
            for s in (YES, NO):
                lst = vs.orders[s]
                if not lst:
                    continue
                keep = []
                for o in lst:
                    if o.die_at is not None and o.die_at <= P:
                        continue
                    if not o.landed and o.land_at <= P:
                        opp = m.best[1 - s]
                        if not m.scheduled and opp is not None and o.price + opp >= 1000:
                            vs.rejects += 1
                            redo = True
                            continue
                        if not m.scheduled:
                            # the room left counts our OTHER live orders on this side too (a stale order whose
                            # cancel is still in flight can fill as well): |position| can never pass S (review
                            # 2026-10-17, must-fix 3). Only bites when two of our orders on one side overlap.
                            others = [x for x in lst if x is not o and x.landed and x.rem > EPS
                                      and (x.die_at is None or x.die_at > P)]
                            room = (cap - vs.inv if s == YES else cap + vs.inv) - sum(x.rem for x in others)
                            if o.rem > room:
                                o.rem = max(0.0, room)
                                if others:
                                    vs.exposure_clips += 1
                            if o.rem <= EPS:
                                vs.cap_drops += 1
                                dies = [x.die_at for x in others if x.die_at is not None]
                                if dies:
                                    m.wakes.append(min(dies))     # re-decide when the old order is gone
                                    self._new_wakes.append(min(dies))
                                continue
                        o.landed = True
                        o.ahead = o.ahead0 = self._deff(m, s, o.price, P)
                    keep.append(o)
                vs.orders[s] = keep
        return redo

    def _stale_accrue(self, m, a, b):
        """Time a live order of ours spends ABOVE the others' best on its side (alone, waiting for its cancel)."""
        for vs in m.vs:
            for s in (YES, NO):
                touch = m.best[s]
                for o in vs.orders[s]:
                    if not o.landed and o.land_at > a:
                        lo = max(a, o.land_at)
                    else:
                        lo = a
                    hi = b if o.die_at is None else min(b, o.die_at)
                    live_now = (o.landed or o.land_at <= a) and (o.die_at is None or o.die_at > a)
                    st = live_now and (touch is None or o.price > touch)
                    if st and not o.stale:
                        vs.stale_ep += 1
                    o.stale = st
                    if st and hi > lo:
                        vs.stale_ms += hi - lo

    def _in_span(self, m, t):
        return (m.prog_ok() and m.snap and not m.suspect and m.open_ms is not None
                and m.open_ms <= t < m.tstop_ms)

    def _decide(self, m, base):
        if m.scheduled:
            return
        span = self._in_span(m, base)
        if m.tstop_ms is not None and base >= m.tstop_ms:
            for vs in m.vs:
                if vs.inv_at_stop is None:
                    vs.inv_at_stop = vs.inv
        for vi, var in enumerate(self.variants):
            vs = m.vs[vi]
            L = self._lat(vi)
            for s in (YES, NO):
                lst = vs.orders[s]
                target = None
                for o in lst:
                    if o.die_at is None:
                        target = o.price
                desired, reason, room = None, None, 0.0
                if not span:
                    reason = "off"
                else:
                    touch = m.best[s]
                    if touch is None:
                        reason = "empty"
                    else:
                        yes_eq = touch if s == YES else 1000 - touch
                        room = var.S - vs.inv if s == YES else var.S + vs.inv
                        if not (BAND[0] <= yes_eq <= BAND[1]):
                            reason = "band"
                        elif var.G is not None and vs.pulled[s] > base:
                            reason = "guard"
                        elif room <= EPS:
                            reason = "cap"
                        else:
                            desired = touch
                vs.reason[s] = reason
                if desired != target:
                    for o in lst:
                        if o.die_at is None:
                            o.die_at = max(base + L, o.land_at + L)
                            vs.writes += 1
                    if desired is not None:
                        lst.append(Order(desired, min(var.S, room), base + L))
                        vs.writes += 1
                        self._new_lands.append(base + L)

    def _ours(self, vs, s, T):
        d = None
        for o in vs.orders[s]:
            if o.landed and o.land_at <= T and (o.die_at is None or o.die_at > T) and o.rem > EPS:
                if d is None:
                    d = {}
                d[o.price] = d.get(o.price, 0.0) + o.rem
        return d

    def _score(self, m, T):
        if m.suspect or not m.snap:
            return
        tgt, df = m.prog["target"], m.prog["df"]
        cache = {}
        for vi, var in enumerate(self.variants):
            vs = m.vs[vi]
            oy, on = self._ours(vs, YES, T), self._ours(vs, NO, T)
            ky = (YES, tuple(sorted(oy.items())) if oy else None)
            kn = (NO, tuple(sorted(on.items())) if on else None)
            wy = cache.get(ky)
            if wy is None:
                wy = cache[ky] = walk(m.books[YES], tgt, df, oy, self.mut_no_qual)
            wn = cache.get(kn)
            if wn is None:
                wn = cache[kn] = walk(m.books[NO], tgt, df, on, self.mut_no_qual)
            vs.scored += 1
            if oy:
                vs.rest_s[YES] += 1
            if on:
                vs.rest_s[NO] += 1
            if wy[0] and wn[0]:
                vs.counted += 1
                vs.sh[YES] += wy[3]
                vs.sh[NO] += wn[3]
            for s, (w_this, w_other, ours_other) in ((YES, (wy, wn, on)), (NO, (wn, wy, oy))):
                if vs.reason[s] == "band" and m.best[s] is not None:
                    vs.band_out_s[s] += 1
                    room = var.S - vs.inv if s == YES else var.S + vs.inv
                    if room > EPS:
                        sh = walk(m.books[s], tgt, df, {m.best[s]: min(var.S, room)}, self.mut_no_qual)
                        if sh[0] and w_other[0]:
                            vs.band_lost += sh[3]

    # ---------------------------------------------------------------- V3 and flights
    def _v3_close(self, m, ts):
        if not m.v3:
            return
        for key in [k for k in m.v3 if k[2] <= ts]:
            q, used, n = m.v3.pop(key)
            self.v3["trades"] += n
            if used >= q - 1e-6:
                self.v3["matched"] += n

    def _flight_cancel(self, m, s, p, c, size_before, ts):
        if m.best[s] != p and not (m.best[s] is None):
            return
        f = m.flight[s]
        if f is None or ts - f["t0"] > FLIGHT_MS or f["p"] != p:
            f = m.flight[s] = {"t0": ts, "p": p, "size0": size_before, "canc": 0.0, "printed": False, "done": False}
        f["canc"] += c
        if not f["done"] and not f["printed"] and f["size0"] > EPS and f["canc"] >= FLIGHT_FRAC * f["size0"] - EPS:
            f["done"] = True
            self._record_flight(m, s, ts)

    def _record_flight(self, m, s, ts):
        if not m.pair or m.open_ms is None or not (m.open_ms <= ts < m.close_ms):
            return
        h = self.kr_hist.get(m.pair)
        if not h:
            self.flights.append({"tk": m.tk, "s": s, "ts": ts, "move": None, "lead": None})
            return
        now = self._kr_mid_at(m.pair, ts)
        then = self._kr_mid_at(m.pair, ts - LEAD_MS)
        pip = PIP.get(m.pair, 0.0001)
        move = None
        if now is not None and then is not None:
            move = (now - then) / pip
            move = -move if s == YES else move             # positive = Kraken moved against the side that fled
        lc = self.kr_last_change.get(m.pair)
        lead = (ts - lc) if lc is not None and 0 <= ts - lc <= LEAD_MS else None
        self.flights.append({"tk": m.tk, "s": s, "ts": ts, "move": move, "lead": lead})

    def _kr_mid_at(self, sym, t):
        h = self.kr_hist.get(sym)
        if not h:
            return None
        best = None
        for (tt, mid) in h:
            if tt <= t:
                best = mid
            else:
                break
        return best

    # ---------------------------------------------------------------- fills
    def _fill(self, m, vi, s, o, f, ts, mech):
        vs = m.vs[vi]
        o.rem -= f
        vs.inv += f if s == YES else -f
        if abs(vs.inv) > vs.max_abs_inv:
            vs.max_abs_inv = abs(vs.inv)
        stale = 1 if (m.touch0[s] is None or o.price > m.touch0[s]) else 0
        fl = Fill(s, o.price, round(f, 6), ts, mech, stale, 1 if self.rng.random() < 0.5 else -1, o.kid)
        vs.fills.append(fl)
        idx = len(vs.fills) - 1
        for which, h in enumerate(MARK_MS):
            heapq.heappush(m.marks, (ts + h, vi, idx, which))
        self.stat["fills"] += 1
        self.stat["fill_" + mech] += 1
        m.dirty = True

    @staticmethod
    def _prune(vs, s):
        if any(o.rem <= EPS for o in vs.orders[s]):
            vs.orders[s] = [o for o in vs.orders[s] if o.rem > EPS]

    # ---------------------------------------------------------------- events
    def on_snapshot(self, tk, sid, yes_levels, no_levels, ts):
        m = self.market(tk)
        if m.last_ts is not None:
            self._advance(m, ts)
        m.sid = sid
        m.books = ({}, {})
        for side, lv in ((YES, yes_levels), (NO, no_levels)):
            for p, z in lv:
                z = float(z)
                if z > EPS:
                    m.books[side][px(p)] = z
        self._recompute_best(m, YES)
        self._recompute_best(m, NO)
        m.pending.clear()
        m.v3.clear()
        for vs in m.vs:
            for s in (YES, NO):
                for o in vs.orders[s]:
                    if o.landed:
                        o.ahead = min(o.ahead, m.books[s].get(o.price, 0.0))
        if m.snap:
            self.stat["resnapshot"] += 1
        m.snap = True
        if m.suspect:
            m.suspect = False
            self.stat["suspect_cleared"] += 1
        if m.first_snap_ts is None:
            m.first_snap_ts = ts
        m.dirty = True
        if m.last_ts is None:
            self._advance(m, ts)
        self.stat["snap"] += 1

    def on_suspect(self, tks, ts):
        for tk in tks:
            m = self.markets.get(tk)
            if m is None:
                continue
            self._suspect(m, ts)

    def on_global_suspect(self, ts):
        self.stat["heartbeat_gaps"] += 1
        for m in list(self.markets.values()):
            if m.close_ms is not None and m.close_ms <= ts:
                continue                 # already closed: nothing left to void, and its marks wait for finish()
            self._suspect(m, ts)

    def _suspect(self, m, ts):
        if m.last_ts is not None:
            self._advance(m, ts)
        m.suspect = True
        self.stat["suspect_starts"] += 1
        for vs in m.vs:
            for s in (YES, NO):
                for o in vs.orders[s]:
                    if o.die_at is None or o.die_at > ts:
                        o.die_at = ts
        m.dirty = True

    def on_trade(self, tk, taker_side, yes_t, no_t, q, ts):
        m = self.markets.get(tk)
        if m is not None:
            m.prints += q
            m.n_trades += 1
        if m is None or not m.snap:
            self.stat["trade_no_book"] += 1
            if m is None and tk.startswith(self.prefixes):
                m = self.market(tk)
                m.prints += q
                m.n_trades += 1
            return
        self._advance(m, ts)
        m.events += 1
        s, p = (NO, no_t) if taker_side == "yes" else (YES, yes_t)
        g = m.v3.get((s, p, ts))
        if g is None:
            m.v3[(s, p, ts)] = [q, 0.0, 1]
        else:
            g[0] += q
            g[2] += 1
        f = m.flight[s]
        if f is not None and f["p"] == p and ts - f["t0"] <= FLIGHT_MS:
            f["printed"] = True
        if m.suspect:
            self._pend(m, s, p, q, ts)
            return
        deff = self._deff(m, s, p, ts)
        if q > deff + EPS:
            self.stat["anom_print_exceeds_level"] += 1
            q_eff = deff
        else:
            q_eff = q
        for vi, var in enumerate(self.variants):
            vs = m.vs[vi]
            lst = vs.orders[s]
            if not lst:
                continue
            hit = False
            # ONE budget per print (review 2026-10-17, must-fix 3): the taker sold q; our orders above the print price
            # are reached first (walk, best price first), then the queue at the print price -- the others ahead of
            # each of our orders, then that order, in queue order. Our fills from one print never exceed q.
            left = q
            at_p = []
            for o in sorted(lst, key=lambda x: -x.price):
                if not self._live(o, ts) or o.rem <= EPS:
                    continue
                if o.price == p:
                    at_p.append(o)
                elif o.price > p:
                    if left <= EPS:
                        continue
                    if self._deff(m, s, o.price, ts) <= EPS:
                        fq = min(o.rem, left)
                        self._fill(m, vi, s, o, fq, ts, "walk")
                        left -= fq
                        hit = True
                    else:
                        self.stat["anom_walk_past_nonempty"] += 1
                        wq = min(o.rem, left)
                        m.walk_pending.append([s, o.price, ts, vi, o, wq])
                        left -= wq                       # reserved for the same-ms delta that empties that level
            if at_p:
                avail = left if self.mut_ignore_queue else min(q_eff, left)
                taken = 0.0
                for o in sorted(at_p, key=lambda x: (x.ahead, x.land_at)):
                    if self.mut_ignore_queue:
                        ahead = 0.0
                    else:
                        ahead = deff if var.q == "last" else o.ahead
                    fq = min(o.rem, avail - ahead - taken)
                    if fq > EPS:
                        self._fill(m, vi, s, o, fq, ts, "queue")
                        taken += fq
                        hit = True
                if var.q != "last" and not self.mut_ignore_queue:
                    for o in at_p:
                        o.ahead = max(0.0, o.ahead - q_eff)
            if hit:
                self._prune(vs, s)
        self._pend(m, s, p, q, ts)

    @staticmethod
    def _pend(m, s, p, q, ts):
        pe = m.pending.get((s, p))
        if pe is not None and ts - pe[1] <= PEND_TTL:
            pe[0] += q
            pe[1] = ts
        else:
            m.pending[(s, p)] = [q, ts]

    def on_delta(self, tk, sid, side, p, dq, ts):
        m = self.markets.get(tk)
        if m is None or not m.snap:
            self.stat["delta_before_snapshot"] += 1
            return
        if sid is not None and m.sid is not None and sid != m.sid:
            self.stat["delta_other_sid"] += 1
            return
        self._advance(m, ts)
        m.events += 1
        s = YES if side == "yes" else NO
        book = m.books[s]
        d0 = book.get(p, 0.0)
        if dq < 0.0:
            c = -dq
            used = 0.0
            pe = m.pending.get((s, p))
            if pe is not None:
                if ts - pe[1] <= PEND_TTL:
                    used = min(c, pe[0])
                    pe[0] -= used
                    if pe[0] <= EPS:
                        del m.pending[(s, p)]
                else:
                    del m.pending[(s, p)]
            g = m.v3.get((s, p, ts))
            if g is not None:
                g[1] += min(c, max(0.0, g[0] - g[1]))
            cancel = c - used
            d_after = d0 - c
            if d_after < -EPS:
                self.stat["anom_level_negative"] += 1
            if d_after < 0.0:
                d_after = 0.0
            if cancel > EPS:
                self.stat["cancel_events"] += 1
                self._flight_cancel(m, s, p, cancel, d0, ts)
                d_bc = max(0.0, d0 - used)
                if not m.suspect:
                    for vi, var in enumerate(self.variants):
                        if var.q == "last":
                            continue
                        for o in m.vs[vi].orders[s]:
                            if not o.landed or o.price != p:
                                continue
                            if var.q == "fifo_prorata":
                                o.ahead = (o.ahead * d_after / d_bc) if d_bc > EPS else 0.0
                            elif var.q == "fifo_front":
                                o.ahead = max(0.0, o.ahead - cancel)
                            if o.ahead > d_after:
                                o.ahead = d_after
            if d_after > EPS:
                book[p] = d_after
            else:
                book.pop(p, None)
                if m.best[s] == p:
                    self._recompute_best(m, s)
                    m.dirty = True
                if m.walk_pending:
                    keep = []
                    for w in m.walk_pending:
                        ws, wp, wts, wv, wo, wq = w
                        if ws == s and wp == p and wts == ts:
                            if wo.rem > EPS and self._live(wo, ts):
                                self._fill(m, wv, ws, wo, min(wo.rem, wq), ts, "walk")
                                self.stat["walk_deferred"] += 1
                                self._prune(m.vs[wv], ws)
                        else:
                            keep.append(w)
                    m.walk_pending = keep
        else:
            book[p] = d0 + dq
            if m.best[s] is None or p > m.best[s]:
                m.best[s] = p
                m.dirty = True
            if m.suspect:
                return
            s2 = 1 - s
            lim = 1000 - p
            for vi in range(len(self.variants)):
                vs = m.vs[vi]
                lst = vs.orders[s2]
                if not lst:
                    continue
                hit = False
                left = dq
                for o in sorted(lst, key=lambda x: -x.price):
                    if o.price >= lim and self._live(o, ts) and o.rem > EPS and left > EPS:
                        if self._deff(m, s2, o.price, ts) <= EPS:
                            fq = min(o.rem, left)
                            self._fill(m, vi, s2, o, fq, ts, "cross")
                            left -= fq
                            hit = True
                        else:
                            self.stat["anom_cross_nonempty"] += 1
                if hit:
                    self._prune(vs, s2)

    def on_kraken(self, sym, mid, ts):
        h = self.kr_hist[sym]
        if h and h[-1][1] != mid:
            self.kr_last_change[sym] = ts
        elif not h:
            self.kr_last_change[sym] = ts
        h.append((ts, mid))
        # keep the newest entry at or before the oldest look-back (it is the mid "as of" that time)
        while len(h) >= 2 and h[1][0] <= ts - 3 * LEAD_MS:
            h.popleft()
        if not self.guard_idx:
            return
        then = self._kr_mid_at(sym, ts - GUARD_WINDOW_MS)
        if then is None:
            return
        pip = PIP.get(sym, 0.0001)
        move = (mid - then) / pip
        for tk in list(self.active_by_pair.get(sym, ())):
            m = self.markets.get(tk)
            if m is None or m.open_ms is None or not (m.open_ms <= ts < m.tstop_ms):
                continue
            self._advance(m, ts)
            for vi in self.guard_idx:
                G = self.variants[vi].G
                vs = m.vs[vi]
                if move <= -G + 1e-9 and vs.pulled[YES] < ts + GUARD_PULL_MS:
                    vs.pulled[YES] = ts + GUARD_PULL_MS
                    vs.guard_pulls += 1
                    m.dirty = True
                if move >= G - 1e-9 and vs.pulled[NO] < ts + GUARD_PULL_MS:
                    vs.pulled[NO] = ts + GUARD_PULL_MS
                    vs.guard_pulls += 1
                    m.dirty = True

    def on_ticker(self, tk, tup, ts):
        """V1: the exchange's own top of book (yes bid, its size, yes ask, its size) against ours, at the end of
        the ticker's millisecond."""
        m = self.markets.get(tk)
        if m is None or not m.snap or m.suspect or not tk.startswith(self.prefixes):
            return
        self._advance(m, ts)
        yb, ybs, ya, yas = tup

        def same(state_best, state_size):
            by, bn = state_best
            sy, sn = state_size
            my_yb, my_ybs = (by, sy) if by is not None else (0, 0.0)
            my_ya, my_yas = (1000 - bn, sn) if bn is not None else (1000, 0.0)
            ok_b = my_yb == yb and abs(my_ybs - ybs) <= max(1.0, 0.02 * ybs)
            ok_a = my_ya == ya and abs(my_yas - yas) <= max(1.0, 0.02 * yas)
            return ok_b, ok_a
        cur_best = list(m.best)
        cur_size = [m.books[s].get(m.best[s], 0.0) if m.best[s] is not None else 0.0 for s in (YES, NO)]
        ob, oa = same(cur_best, cur_size)
        eb, ea = same(m.touch0, m.size0)
        self.v1["n"] += 1
        self.v1["ok"] += 1 if (ob and oa) else 0
        self.v1["ok_bid"] += 1 if ob else 0
        self.v1["ok_ask"] += 1 if oa else 0
        self.v1["ok_either"] += 1 if ((ob and oa) or (eb and ea)) else 0

    # ---------------------------------------------------------------- finishing a window
    def finish(self, m, result, volume, run_id="", hour=None):
        if m.close_ms is None:
            del self.markets[m.tk]
            self.stat["finished_without_meta"] += 1
            return []
        if m.last_ts is not None:
            self._advance(m, m.close_ms)
        won = None if result not in ("yes", "no") else (1000 if result == "yes" else 0)
        while m.marks:
            due, vi, idx, which = heapq.heappop(m.marks)
            self._resolve_mark(m, vi, idx, which, self._mid(m) if due <= m.close_ms else won)
        for vs in m.vs:
            if vs.inv_at_stop is None:
                vs.inv_at_stop = vs.inv
        self.active_by_pair[m.pair].discard(m.tk) if m.pair else None
        del self.markets[m.tk]
        if m.scheduled:
            return [m, won]
        v4_ok = (m.first_snap_ts is not None and m.open_ms is not None and m.first_snap_ts <= m.open_ms
                 and m.suspect_ms < 5000 and m.snap)
        v2_ok = None
        if volume is not None:
            v2_ok = abs(m.prints - volume) <= max(0.5, 0.002 * volume)
        rows = []
        prog = m.prog or {}
        period_s = prog.get("period_s") or (T_OPEN_S if m.open_ms is None else (m.close_ms - m.open_ms) / 1000.0)
        for vi, var in enumerate(self.variants):
            vs = m.vs[vi]
            cred = credit_usd(prog.get("reward_usd", 0.0), period_s, vs.sh[YES] + vs.sh[NO]) if prog else 0.0
            band_lost = credit_usd(prog.get("reward_usd", 0.0), period_s, vs.band_lost) if prog else 0.0
            kinds = collections.Counter()
            fy = fn = 0.0
            ps = m10 = m60 = m60r = m60nc = psnc = 0.0
            miss = 0
            for fl in vs.fills:
                kinds[fl.mech] += fl.q
                if fl.stale:
                    kinds["stale"] += fl.q
                    kinds["n_stale"] += 1
                if fl.s == YES:
                    fy += fl.q
                else:
                    fn += fl.q
                pay = fl.price if fl.s == YES else fl.price
                if won is not None:
                    v = ((won - pay) if fl.s == YES else ((1000 - won) - pay)) * fl.q / 1000.0
                    ps += v
                    if fl.mech != "cross":
                        psnc += v
                for which in (0, 1):
                    mid = fl.marks[which]
                    if mid is None:
                        miss += 1
                        continue
                    v = ((mid - pay) if fl.s == YES else ((1000 - mid) - pay)) * fl.q / 1000.0
                    if which == 0:
                        m10 += v
                    else:
                        m60 += v
                        m60r += fl.eps * v
                        if fl.mech != "cross":
                            m60nc += v
            rows.append({
                "tk": m.tk, "series": m.series, "pair": m.pair, "open": ms_iso(m.open_ms) if m.open_ms else None,
                "close": ms_iso(m.close_ms), "close_ms": m.close_ms, "et_day": et_day(m.close_ms),
                "fx_day": fx_day(m.close_ms), "variant": var.name, "S": var.S, "L": var.L, "queue": var.q,
                "guard": var.G, "prog_ok": m.prog_ok(), "reward_usd": prog.get("reward_usd"),
                "target": prog.get("target"), "df": prog.get("df"),
                "credit_usd": round(cred, 6), "credit_floored_usd": round(floored(cred), 6),
                "counted_s": vs.counted, "scored_s": vs.scored,
                "share_y": round(vs.sh[YES] / vs.counted, 6) if vs.counted else 0.0,
                "share_n": round(vs.sh[NO] / vs.counted, 6) if vs.counted else 0.0,
                "rest_s_y": vs.rest_s[YES], "rest_s_n": vs.rest_s[NO], "fills_y": round(fy, 4),
                "fills_n": round(fn, 4), "n_fills": len(vs.fills),
                "kinds": {k: round(v, 4) for k, v in kinds.items()},
                "pnl_settle_usd": round(ps, 6) if won is not None else None,
                "pnl_settle_nocross_usd": round(psnc, 6) if won is not None else None,
                "mark10_usd": round(m10, 6), "mark60_usd": round(m60, 6), "mark60_randsign_usd": round(m60r, 6),
                "mark60_nocross_usd": round(m60nc, 6), "marks_missing": miss,
                "stale_episodes": vs.stale_ep, "stale_ms": vs.stale_ms, "rejects": vs.rejects,
                "writes": vs.writes, "cap_drops": vs.cap_drops, "inv_at_stop": round(vs.inv_at_stop, 4),
                "max_abs_inv": round(vs.max_abs_inv, 4), "exposure_clips": vs.exposure_clips,
                "result": result, "suspect_s": round(m.suspect_ms / 1000.0, 3),
                "first_snap_before_open": (m.first_snap_ts is not None and m.open_ms is not None
                                           and m.first_snap_ts <= m.open_ms),
                "v4_ok": bool(v4_ok), "v2_ok": v2_ok, "prints_sum": round(m.prints, 4), "volume_fp": volume,
                "band_out_s_y": vs.band_out_s[YES], "band_out_s_n": vs.band_out_s[NO],
                "band_lost_usd": round(band_lost, 6), "guard_pulls": vs.guard_pulls, "void": not v4_ok,
                "run": run_id, "hour": hour})
        return rows


# ================================================================================================ meta (small channels)
class Meta(object):
    """Program rows, market times, results and settled volumes from the recorder's small channels, across every hour
    file present (they are written when first seen, often hours before the window). Files are re-read only when
    their size changes."""

    def __init__(self, root):
        self.root = root
        self.seen = {}
        self.info = collections.defaultdict(dict)       # tk -> {open_ms, close_ms, prog, result, volume}
        self.prog_rows = {}                              # tk -> program row (newest by _rx_ms)
        self.prog_rx = {}

    def get(self, tk):
        return self.info.get(tk)

    def _rows(self, chan, upto_hour=None):
        for fp in sorted(glob.glob(os.path.join(self.root, chan, "*.jsonl.gz"))):
            tag = os.path.basename(fp)[:11]
            if upto_hour is not None and tag > upto_hour:
                continue
            try:
                sz = os.path.getsize(fp)
            except OSError:
                continue
            if self.seen.get(fp) == sz:
                continue
            self.seen[fp] = sz
            for line in gz_lines(fp):
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    def refresh(self, upto_hour=None):
        for d in self._rows("programs", upto_hour):
            r = d.get("row") or {}
            tk = r.get("market_ticker")
            if not tk:
                continue
            rx = d.get("_rx_ms", 0)
            if rx >= self.prog_rx.get(tk, -1):
                self.prog_rx[tk] = rx
                self.prog_rows[tk] = r
                self.info[tk]["prog"] = program_of(r)
                s0, e0 = iso_ms(r.get("start_date")), iso_ms(r.get("end_date"))
                if s0 and e0 and not self.info[tk].get("open_ms"):
                    self.info[tk]["open_ms"], self.info[tk]["close_ms"] = s0, e0
        for d in self._rows("markets", upto_hour):
            mk = d.get("market") or {}
            tk = mk.get("ticker")
            o, c = iso_ms(mk.get("open_time")), iso_ms(mk.get("close_time"))
            if tk and o and c:
                self.info[tk]["open_ms"], self.info[tk]["close_ms"] = o, c
        for d in self._rows("market_lifecycle_v2", upto_hour):
            msg = d.get("msg") or {}
            tk = msg.get("market_ticker")
            if not tk:
                continue
            if msg.get("event_type") == "created" and isinstance(msg.get("open_ts"), (int, float)):
                self.info[tk].setdefault("open_ms", int(msg["open_ts"]) * 1000)
                self.info[tk].setdefault("close_ms", int(msg["close_ts"]) * 1000)
            if msg.get("event_type") == "determined" and str(msg.get("result", "")).lower() in ("yes", "no"):
                self.info[tk]["result"] = str(msg["result"]).lower()
        for d in self._rows("settled", upto_hour):
            mk = d.get("market") or {}
            tk = mk.get("ticker")
            if not tk:
                continue
            if mk.get("result") in ("yes", "no"):
                self.info[tk].setdefault("result", mk["result"])
            if mk.get("volume_fp") is not None:
                try:
                    self.info[tk]["volume"] = float(mk["volume_fp"])
                except (TypeError, ValueError):
                    pass


def program_of(r):
    """A program row -> the numbers the walk needs, units from the field names."""
    try:
        reward = cc_to_usd(r.get("period_reward"))
        target = float(r.get("target_size_fp") if r.get("target_size_fp") is not None else r.get("target_size"))
        dfb = int(r.get("discount_factor_bps"))
    except (TypeError, ValueError, InvalidOperation):
        return {"ok": False, "why": "unreadable"}
    s0, e0 = iso_ms(r.get("start_date")), iso_ms(r.get("end_date"))
    ok = (int(r.get("period_reward")) >= PROGRAM_RULE["period_reward"] and abs(target - PROGRAM_RULE["target"]) < 1e-9
          and dfb == PROGRAM_RULE["df_bps"])
    return {"ok": ok, "reward_usd": reward, "target": target, "df": dfb / 10000.0,
            "period_s": (e0 - s0) / 1000.0 if s0 and e0 else None, "start_ms": s0, "end_ms": e0,
            "id": r.get("id")}


# ================================================================================================ the hour pass
def _path(root, chan, h):
    return os.path.join(root, chan, h + ".jsonl.gz")


def _iter(root, chan, h, stat=None):
    fp = _path(root, chan, h)
    if not os.path.exists(fp):
        return
    for line in gz_lines(fp, stat):
        try:
            yield json.loads(line)
        except Exception:
            if stat is not None:
                stat["unparsed_" + chan] = stat.get("unparsed_" + chan, 0) + 1


_TK_KEY = '"market_ticker":"'


def _tk_of(line):
    """The market_ticker of a raw frame line without parsing it (a cheap prefilter; '' if absent)."""
    i = line.find(_TK_KEY)
    if i < 0:
        i = line.find('"market_ticker": "')
        if i < 0:
            return ""
        i += 18
    else:
        i += len(_TK_KEY)
    j = line.find('"', i)
    return line[i:j] if j > i else ""


def _iter_tk(root, chan, h, prefixes, stat=None):
    """Frames of one channel-hour whose market_ticker starts with one of `prefixes`; others are never parsed."""
    fp = _path(root, chan, h)
    if not os.path.exists(fp):
        return
    for line in gz_lines(fp, stat):
        if not _tk_of(line).startswith(prefixes):
            continue
        try:
            yield json.loads(line)
        except Exception:
            if stat is not None:
                stat["unparsed_" + chan] = stat.get("unparsed_" + chan, 0) + 1


def estimate_lag(root, h, prefixes, n_max=20000):
    lags = []
    fp = _path(root, "orderbook_delta", h)
    if not os.path.exists(fp):
        return None
    for line in gz_lines(fp):
        if len(lags) >= n_max:
            break
        if not _tk_of(line).startswith(prefixes):
            continue
        try:
            d = json.loads(line)
            msg = d.get("msg") or {}
            if not str(msg.get("market_ticker", "")).startswith(prefixes):
                continue
            lags.append(d["_rx_ms"] - int(msg["ts_ms"]))
        except Exception:
            continue
    return median(lags)


def kraken_iter(eng, root, h, lag):
    """Kraken book frames of hour h, STREAMED in file (receive) order -> (eff_ts, 0, symbol, mid), one per validated
    frame (the guard is evaluated on every frame, as a live quoter would on every message); books carried across
    hours. A frame the recorder flagged _crc_ok false drops that symbol's book until the next snapshot. Nothing is
    held for the hour (review 2026-10-17, must-fix 4: the old list held every frame, ~46 MB an hour at Saturday
    rates, and would cross the 150 MB abort on a busy weekday). eff_ts = _rx_ms - lag is kept non-decreasing (the
    merge needs sorted input; a clock step back is clamped and counted)."""
    last = None
    n = 0
    for d in _iter(root, "kraken_book", h):
        n += 1
        if (n & 0xFFFF) == 0:
            r = rss_mb()
            if r > RSS_ABORT_MB:
                eng.stat["rss_abort_mb"] = round(r, 1)
                raise RssAbort("rss %.0f MB > %.0f MB in the Kraken stream" % (r, RSS_ABORT_MB))
        if d.get("channel") != "book":
            continue
        rx = d.get("_rx_ms")
        oks = d.get("_crc_ok")
        items = d.get("data") or []
        if not isinstance(oks, list):
            oks = [oks] * len(items)
        for item, ok in zip(items, oks):
            sym = item.get("symbol")
            if d.get("type") == "snapshot":
                bk = eng.kr_books[sym] = {"b": {}, "a": {}}
            else:
                bk = eng.kr_books.get(sym)
                if bk is None:
                    continue
            for side, key in (("b", "bids"), ("a", "asks")):
                for lv in item.get(key) or []:
                    p, q = float(lv["price"]), float(lv["qty"])
                    if q == 0:
                        bk[side].pop(p, None)
                    else:
                        bk[side][p] = q
            if len(bk["b"]) > 10:
                for p in sorted(bk["b"], reverse=True)[10:]:
                    del bk["b"][p]
            if len(bk["a"]) > 10:
                for p in sorted(bk["a"])[10:]:
                    del bk["a"][p]
            if ok is False:
                eng.kr_books.pop(sym, None)
                eng.stat["kraken_crc_dropped"] += 1
                continue
            if ok is None and d.get("type") != "snapshot":
                continue
            if bk["b"] and bk["a"]:
                mid = 0.5 * (max(bk["b"]) + min(bk["a"]))
                t = rx - lag
                if last is not None and t < last:
                    eng.stat["kraken_ts_clamped"] += 1
                    t = last
                last = t
                eng.stat["kraken_frames_streamed"] += 1
                yield (t, 0, sym, mid)


def first_heartbeat(root, h):
    """_rx_ms of the first heartbeat row of hour h, or None (no file, or no row yet)."""
    for d in _iter(root, "heartbeat", h):
        rx = d.get("_rx_ms")
        if isinstance(rx, (int, float)):
            return int(rx)
    return None


def heartbeat_gaps(eng, root, h, st):
    """Exchange-clock times at which every open market goes SUSPECT because the recorder was down (a heartbeat gap
    > HB_GAP_MS). Inside the hour: between consecutive heartbeats. At the END of the hour: from the hour's last
    heartbeat to the NEXT hour's first one -- a recorder that died at 14:16 and never came back, or came back at
    15:10, leaves the 14:15 window suspect from 14:16:05 (review 2026-10-17, must-fix 2: that gap used to surface
    only in the next hour, after the window had already been finished as clean). The next hour's file exists by the
    time an hour is processed (--follow waits 15 min past the hour end; --batch skips unfinished hours), so a missing
    one means the recorder was down. No heartbeat channel at all (the collector's tape, V5) = no check."""
    if not os.path.isdir(os.path.join(root, "heartbeat")):
        return []
    hs = hour_start_ms(h)
    he = hs + 3600 * 1000
    hbs = sorted(d.get("_rx_ms", 0) for d in _iter(root, "heartbeat", h, st))
    out = []
    if not hbs:
        st["hours_without_heartbeat"] += 1
        out.append(hs)
        return out
    if eng.last_hb_rx is None and hbs[0] - hs > HB_GAP_MS:
        out.append(hs)                   # the first hour this engine sees: a late first heartbeat
    for a, b in zip(hbs, hbs[1:]):
        if b - a > HB_GAP_MS:
            out.append(a + 5000)
    nxt = first_heartbeat(root, next_hour(h))
    if nxt is None or nxt - hbs[-1] > HB_GAP_MS:
        out.append(min(hbs[-1] + 5000, he - 1))
        st["heartbeat_tail_gaps"] += 1
    eng.last_hb_rx = hbs[-1]
    return out


def run_hour(eng, root, h, say=None, stop_check=None):
    """One hour of the recorder's files through the engine, merged on the exchange clock."""
    t0 = time.time()
    st = eng.stat
    prefixes = eng.prefixes
    lag = estimate_lag(root, h, prefixes)
    if lag is not None:
        eng.lag_ms = int(round(lag))
    lag = eng.lag_ms
    # -- the book side stream: snapshots + suspect markers + heartbeat gaps (small, in memory), deltas streamed
    pre = []
    for d in _iter_tk(root, "orderbook_snapshot", h, prefixes, st):
        msg = d.get("msg") or {}
        tk = msg.get("market_ticker") or ""
        if not tk.startswith(prefixes):
            continue
        n = d.get("_rx_n", d.get("seq", 0))
        pre.append((d.get("_rx_ms", 0), n, "snap", (tk, d.get("sid"), msg.get("yes_dollars_fp") or [],
                                                     msg.get("no_dollars_fp") or [])))
    for d in _iter(root, "suspect", h, st):
        if d.get("type") == "suspect" and d.get("state") == "start":
            pre.append((d.get("_rx_ms", 0), -1, "sus", list(d.get("tickers") or [])))
    for g in heartbeat_gaps(eng, root, h, st):
        pre.append((g, -2, "gsus", None))
    pre.sort(key=lambda x: (x[0], x[1]))
    # -- side channels merged by exchange time: kraken (0), trades (1) before same-ms deltas; tickers (3) after.
    #    Trades and tickers (a few per market-second at most) are held for the hour; Kraken is STREAMED.
    side = []
    for d in _iter_tk(root, "trade", h, prefixes, st):
        msg = d.get("msg") or {}
        tk = msg.get("market_ticker") or ""
        if not tk.startswith(prefixes):
            continue
        if msg.get("is_block_trade"):
            st["trade_block_skipped"] += 1
            continue
        if eng.trade_windows is not None:
            tsw = msg.get("ts_ms")
            if not isinstance(tsw, (int, float)) or not any(lo <= tsw <= hi for lo, hi in
                                                            eng.trade_windows.get(tk, ())):
                st["trade_outside_v5_windows"] += 1
                continue
        try:
            side.append((int(msg["ts_ms"]), 1, sys.intern(tk), (sys.intern(msg["taker_side"]),
                                                                 px(msg["yes_price_dollars"]),
                                                                 px(msg["no_price_dollars"]),
                                                                 float(msg["count_fp"]))))
        except (KeyError, TypeError, ValueError) as e:
            if isinstance(e, UnitError):
                raise
            st["trade_bad_fields"] += 1
    v1_sec = {}
    for d in (() if eng.scheduled else _iter_tk(root, "ticker", h, prefixes, st)):
        msg = d.get("msg") or {}
        tk = msg.get("market_ticker") or ""
        if not tk.startswith(prefixes) or not isinstance(msg.get("ts_ms"), (int, float)):
            continue
        sec = int(msg["ts_ms"]) // 1000
        if v1_sec.get(tk) == sec:
            continue                                  # V1 samples the first ticker frame per market-second
        v1_sec[tk] = sec
        try:
            tup = (px(msg["yes_bid_dollars"]), float(msg["yes_bid_size_fp"]), px(msg["yes_ask_dollars"]),
                   float(msg["yes_ask_size_fp"]))
        except UnitError:
            raise
        except (KeyError, TypeError, ValueError):
            eng.v1["unreadable"] += 1
            continue
        side.append((int(msg["ts_ms"]), 3, sys.intern(tk), tup))
    v1_sec = None
    side.sort(key=_sidekey)
    n_side = len(side)
    st["side_events_held_max"] = max(st.get("side_events_held_max", 0), n_side)
    merged = heapq.merge(kraken_iter(eng, root, h, lag), side, key=_sidekey)
    head = [None]
    try:
        head[0] = next(merged, None)
    except RssAbort:
        return "rss_abort"

    def drain(ts_b):
        while head[0] is not None:
            e = head[0]
            if e[0] < ts_b or (e[0] == ts_b and e[1] < 2):
                head[0] = next(merged, None)
                if e[1] == 0:
                    eng.on_kraken(e[2], e[3], e[0])
                elif e[1] == 1:
                    ts_, (tsd, yp, np_, q) = e[0], e[3]
                    eng.on_trade(e[2], tsd, yp, np_, q, ts_)
                else:
                    eng.on_ticker(e[2], e[3], e[0])
            else:
                break
    pi = 0

    def do_pre(item):
        rx, n, kind, pay = item
        ts = rx - lag
        drain(ts)
        if kind == "snap":
            tk, sid, yl, nl = pay
            eng.on_snapshot(tk, sid, yl, nl, ts)
            m = eng.markets.get(tk)
            if m is not None and m.pair:
                eng.active_by_pair[m.pair].add(tk)
        elif kind == "sus":
            eng.on_suspect(pay, ts)
        else:
            eng.on_global_suspect(ts)
    r = rss_mb()
    if r > RSS_ABORT_MB:
        st["rss_abort_mb"] = round(r, 1)
        return "rss_abort"
    n_lines = 0
    try:
        fp = _path(root, "orderbook_delta", h)
        if os.path.exists(fp):
            for line in gz_lines(fp, st):
                n_lines += 1
                if not _tk_of(line).startswith(prefixes):
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    st["delta_unparsed"] += 1
                    continue
                msg = d.get("msg") or {}
                tk = msg.get("market_ticker") or ""
                if not tk.startswith(prefixes):
                    continue
                key = (d.get("_rx_ms", 0), d.get("_rx_n", d.get("seq", 0)))
                while pi < len(pre) and (pre[pi][0], pre[pi][1]) < key:
                    do_pre(pre[pi])
                    pi += 1
                try:
                    ts = int(msg["ts_ms"])
                    p = px(msg["price_dollars"])
                    dq = float(msg["delta_fp"])
                    sd = msg["side"]
                except UnitError:
                    raise
                except (KeyError, TypeError, ValueError):
                    st["delta_bad_fields"] += 1
                    continue
                drain(ts)
                eng.on_delta(tk, d.get("sid"), sd, p, dq, ts)
                if (n_lines & 0xFFFF) == 0:
                    if stop_check is not None and stop_check():
                        return "stop_file"
                    r = rss_mb()
                    if r > RSS_ABORT_MB:
                        st["rss_abort_mb"] = round(r, 1)
                        return "rss_abort"
        while pi < len(pre):
            do_pre(pre[pi])
            pi += 1
        drain(hour_start_ms(h) + 3600 * 1000 + 10 ** 9)
    except RssAbort:
        return "rss_abort"
    st["hour_secs"] = round(time.time() - t0, 1)
    st["hour_rss_mb"] = round(rss_mb(), 1)
    if say:
        say("  %s: %d delta lines, %d trade/ticker events held, %d Kraken frames streamed (run total), %d book "
            "markers, lag %s ms, %.1f s, rss %.0f MB" % (h, n_lines, n_side, st.get("kraken_frames_streamed", 0),
                                                       len(pre), lag, time.time() - t0, rss_mb()))
    return True


def finish_due(eng, meta, until_ms, run_id, hour):
    """Finish every market whose close is at or before until_ms; returns the window rows."""
    rows = []
    for tk in sorted(eng.markets):
        m = eng.markets[tk]
        if m.close_ms is None:
            eng.apply_meta(m)
        if m.close_ms is None:
            if m.last_ts is not None and m.last_ts < until_ms - 2 * 3600 * 1000:
                del eng.markets[tk]
                eng.stat["dropped_no_meta"] += 1
            continue
        if m.close_ms <= until_ms:
            info = meta.get(tk) or {}
            rows += eng.finish(m, info.get("result"), info.get("volume"), run_id, hour)
    return rows


# ================================================================================================ outputs
def append_rows(rows, paper_dir):
    by = collections.defaultdict(list)
    for r in rows:
        by[dt.datetime.fromtimestamp(r["close_ms"] / 1000.0, UTC).strftime("%Y%m%d")].append(r)
    os.makedirs(paper_dir, exist_ok=True)
    for day, rs in by.items():
        with gzip.open(os.path.join(paper_dir, day + ".jsonl.gz"), "at", encoding="utf-8") as fh:
            for r in rs:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")


class SLog(object):
    def __init__(self, path):
        self.path = path

    def write(self, ev, **kw):
        r = {"t": utc_iso(time.time()), "ev": ev}
        r.update(kw)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
        return r


def read_log(path):
    out = []
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def iter_paper_rows(paper_dir):
    for fp in sorted(glob.glob(os.path.join(paper_dir, "*.jsonl.gz"))):
        for line in gz_lines(fp):
            try:
                yield json.loads(line)
            except Exception:
                continue


def _day_compact(r):
    """The few numbers a day summary needs, as a tuple (a full window row is ~5.7 KB in memory, this ~0.2 KB: the
    --follow day buffer stays ~3 MB a day instead of ~29 MB -- review 2026-10-17, must-fix 4). None = not counted."""
    if r.get("void") or not r.get("prog_ok"):
        return None
    return (r["series"], r["variant"], paid(r), net_mark(r),
            None if r.get("pnl_settle_usd") is None else net_settle(r),
            r["fills_y"] + r["fills_n"], r["kinds"].get("n_stale", 0), r["close_ms"])


def day_summaries_compact(day, cs):
    """One summary row per (pair, variant) of ET day `day`, from _day_compact tuples."""
    g = collections.defaultdict(list)
    for c in cs:
        g[(c[0], c[1])].append(c)
    out = []
    for (ser, var), rs in sorted(g.items()):
        nets = [c[4] for c in rs if c[4] is not None]
        out.append({"et_day": day, "series": ser, "variant": var, "n": len(rs),
                    "credit_paid_mean": round(sum(c[2] for c in rs) / len(rs), 4),
                    "net_mark60_mean": round(sum(c[3] for c in rs) / len(rs), 4),
                    "net_settle_sum": round(sum(nets), 4) if nets else None,
                    "fills_mean": round(sum(c[5] for c in rs) / len(rs), 3),
                    "stale_fills": sum(c[6] for c in rs)})
    return out


def day_summaries(rows):
    """One summary row per (ET day, pair, variant), from full window rows."""
    g = collections.defaultdict(list)
    for r in rows:
        c = _day_compact(r)
        if c is not None:
            g[r["et_day"]].append(c)
    out = []
    for day in sorted(g):
        out += day_summaries_compact(day, g[day])
    return out


def paid(r, payout=PAYOUT):
    return r["credit_floored_usd"] * payout


def net_mark(r, payout=PAYOUT, nocross=False):
    return paid(r, payout) + (r["mark60_nocross_usd"] if nocross else r["mark60_usd"])


def net_settle(r, payout=PAYOUT):
    return paid(r, payout) + (r["pnl_settle_usd"] or 0.0)


class InstanceLock(object):
    """One paper process at a time (racereward_live.InstanceLock, copied): an OS byte-range lock the OS drops when
    the holder dies, so a crash never leaves a stale lock."""
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
            os.write(fd, ("pid %d since %s" % (os.getpid(), utc_iso(time.time()))).ljust(80).encode() + b"\n")
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


# ================================================================================================ the batch / follow driver
def available_hours(root):
    hs = set()
    for chan in ("orderbook_delta", "heartbeat", "orderbook_snapshot"):
        for fp in glob.glob(os.path.join(root, chan, "*.jsonl.gz")):
            b = os.path.basename(fp)[:11]
            if re.fullmatch(r"\d{8}T\d{2}", b):
                hs.add(b)
    return sorted(hs)


def process(args, follow=False, say=print, now_fn=time.time):
    """--follow / --batch. In BOTH modes an hour is processed only once its end is FOLLOW_WAIT_S behind the clock: an
    hour still being recorded would be finished from partial files, its rows written, and never redone (its hour
    is `done` for this run id). now_fn is the self-test's clock."""
    root = os.path.abspath(args.root)
    paper_dir = os.path.abspath(args.paper_dir)
    slog = SLog(args.log)
    variants = default_variants()
    run_id = "%s-%s" % (code_sha(), variants_hash(variants))
    prefixes = tuple(s + "-" for s in (FX_SERIES + STAGE2_SERIES + tuple(args.series or ())))
    meta = Meta(root)
    eng = Engine(variants, prefixes=prefixes, meta=meta)
    done = set(r["hour"] for r in read_log(args.log) if r.get("ev") == "paper_hour" and r.get("run") == run_id)
    slog.write("start", argv=sys.argv, code_sha=code_sha(), run=run_id, root=root, paper_dir=paper_dir,
               variants=[v.name for v in variants], done_hours=len(done), follow=follow,
               assumption="Kraken frames placed at _rx_ms minus the hour's median Kalshi delta lag")
    processed = set()
    day_rows = collections.defaultdict(list)
    summarized = set(r.get("et_day") for r in read_log(args.log) if r.get("ev") == "day_summary_done"
                     and r.get("run") == run_id)
    while True:
        hours = available_hours(root)
        if args.from_hour:
            hours = [h for h in hours if h >= args.from_hour]
        if args.to_hour:
            hours = [h for h in hours if h <= args.to_hour]
        now_ms = int(now_fn() * 1000)
        ready = [h for h in hours if hour_start_ms(h) + 3600 * 1000 + FOLLOW_WAIT_S * 1000 <= now_ms]
        unfinished = len(hours) - len(ready)
        todo = [h for h in ready if h not in processed]
        if todo and not processed:
            first_new = min([h for h in todo if h not in done] or [todo[-1]])
            warm_from = hour_of_ms(hour_start_ms(first_new) - WARM_HOURS * 3600 * 1000)
            todo = [h for h in todo if h >= warm_from]
        for h in todo:
            if os.path.exists(args.stop):
                slog.write("stop", why="stop_file")
                return 0
            meta.refresh(upto_hour=None)
            eng.refresh_meta()
            ok = run_hour(eng, root, h, say=say, stop_check=lambda: os.path.exists(args.stop))
            if ok is not True:
                slog.write("stop", why=ok, hour=h, rss_mb=round(rss_mb(), 1))
                return 0 if ok == "stop_file" else 2
            meta.refresh(upto_hour=None)
            he = hour_start_ms(h) + 3600 * 1000
            rows = finish_due(eng, meta, he, run_id, h)
            processed.add(h)
            v1 = dict(eng.v1)
            v3 = dict(eng.v3)
            eng.v1.clear()
            eng.v3.clear()
            fl = eng.flights
            eng.flights = []
            if h in done:
                continue                      # a warm-up hour: its output is already on disk
            append_rows(rows, paper_dir)
            for r in rows:
                lst = day_rows[r["et_day"]]
                c = _day_compact(r)
                if c is not None:
                    lst.append(c)
            slog.write("validation", hour=h, run=run_id, V1=v1, V3=v3,
                       flights={"n": len(fl), "adverse_ge_0.3": sum(1 for f in fl if (f["move"] or 0) >= 0.3),
                                "lead_ms_median": median([f["lead"] for f in fl if f["lead"] is not None]),
                                "move_pips_median": median([f["move"] for f in fl if f["move"] is not None])},
                       stat={k: v for k, v in eng.stat.items() if not k.startswith("fill")})
            slog.write("paper_hour", hour=h, run=run_id, rows=len(rows), windows=len(rows) // max(1, len(variants)),
                       open_markets=len(eng.markets), rss_mb=round(rss_mb(), 1))
            for day in sorted(day_rows):
                day_end = None
                rs = day_rows[day]
                if rs:
                    day_end = max(c[7] for c in rs)
                et_now = et_day(he + 1)
                if day < et_now and day not in summarized:
                    for srow in day_summaries_compact(day, rs):
                        slog.write("day_summary", run=run_id, **srow)
                    slog.write("day_summary_done", run=run_id, et_day=day,
                               last_close=ms_iso(day_end) if day_end else None)
                    summarized.add(day)
                    del day_rows[day]
            r = rss_mb()
            if r > RSS_ABORT_MB:
                slog.write("rss_abort", rss_mb=round(r, 1), limit=RSS_ABORT_MB, hour=h)
                return 2
        if not follow:
            for day in sorted(day_rows):
                if day not in summarized:
                    for srow in day_summaries_compact(day, day_rows[day]):
                        slog.write("day_summary", run=run_id, partial=True, **srow)
            slog.write("end", processed=len(processed), run=run_id, unfinished_hours_skipped=unfinished)
            return 0
        for _ in range(60):
            if os.path.exists(args.stop):
                slog.write("stop", why="stop_file")
                return 0
            time.sleep(1)


# ================================================================================================ the report and the bar
def mean_se(xs):
    n = len(xs)
    if n == 0:
        return None, None, 0
    mu = sum(xs) / n
    if n < 2:
        return mu, None, n
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    return mu, math.sqrt(var / n), n


def stats_of(vals):
    mu, se, n = mean_se(vals)
    if mu is None:
        return {"n": 0}
    out = {"n": n, "mean": mu, "se": se}
    if se is not None:
        c = tcrit(0.05, n - 1)
        out.update(lo=mu - c * se, hi=mu + c * se, sd=se * math.sqrt(n), mde=(c + 0.8416) * se)
    return out


def verdict(rows_by_var, validations, n_trading_days, late_days):
    """The section-5 decision for ONE pair. rows_by_var: variant -> list of window rows (non-void, programmed).
    validations: {"V1": bool|None, ..., "V5": bool|None}. Returns a dict with every gate and the decision."""
    rec = rows_by_var.get(RECORD, [])
    out = {"n_windows": len(rec), "trading_days": n_trading_days}
    void = [k for k in ("V1", "V2", "V3", "V4", "V5") if validations.get(k) is not True]
    nets = [net_mark(r) for r in rec]
    s = stats_of(nets)
    out["net_mark60"] = s
    sett = [net_settle(r) for r in rec if r.get("pnl_settle_usd") is not None]
    out["net_settle"] = stats_of(sett)
    late = [net_mark(r) for r in rec if r["fx_day"] in late_days]
    out["late_mean"] = (sum(late) / len(late)) if late else None
    worst = rows_by_var.get(WORSTQ, [])
    ws = stats_of([net_mark(r) for r in worst])
    fast = stats_of([net_mark(r) for r in rows_by_var.get(FAST, [])])
    diff = stats_of([net_settle(r) - net_mark(r) for r in rec if r.get("pnl_settle_usd") is not None])
    stale = sum(r["kinds"].get("n_stale", 0) for r in rec)
    credit = stats_of([paid(r) for r in rec])
    days = collections.defaultdict(float)
    for r in rec:
        if r.get("pnl_settle_usd") is not None:
            days[r["et_day"]] += net_settle(r)
    worst_window = min(sett) if sett else None
    worst_day = min(days.values()) if days else None
    g = {}
    g["G1"] = bool(s.get("n") and s["mean"] >= 1.00 and s.get("lo") is not None and s["lo"] > 0
                   and out["late_mean"] is not None and out["late_mean"] >= 0.50)
    g["G2"] = bool(ws.get("n") and ws["mean"] >= 0.0)
    g["G3"] = bool(diff.get("n") and diff.get("se") is not None and diff["mean"] >= -2 * diff["se"])
    g["G4"] = bool(rec and stale / float(len(rec)) >= 0.1)
    g["G5"] = bool(worst_window is not None and worst_window >= -45.0 and worst_day is not None
                   and worst_day >= -150.0)
    out.update(gates=g, stale_per_window=(stale / float(len(rec))) if rec else None, credit_paid=credit,
               worst_window_settle=worst_window, worst_et_day_settle=worst_day, fast=fast, worstq=ws,
               settle_minus_mark=diff)
    kill = bool((fast.get("n") and fast.get("hi") is not None and fast["mean"] < 0 and fast["hi"] < 1.00)
                or (credit.get("n") and credit["mean"] < 1.50))
    sd = s.get("sd")
    out["no_power"] = bool(sd is not None and sd > 10.0)
    reasons = []
    if void:
        reasons.append("validation failed or not run: " + ",".join(void))
    if n_trading_days < TRADING_DAYS_NEEDED:
        reasons.append("only %d complete trading days (need %d)" % (n_trading_days, TRADING_DAYS_NEEDED))
    if len(rec) < MIN_WINDOWS:
        reasons.append("only %d windows (need %d)" % (len(rec), MIN_WINDOWS))
    if rec and stale == 0:
        reasons.append("G4: zero stale fills -- the engine is blind")
    if reasons:
        out["decision"] = "VOID"
        out["why"] = reasons
    elif kill:
        out["decision"] = "KILL"
    elif all(g.values()):
        out["decision"] = "GO (operator sign-off still required)"
    else:
        out["decision"] = "INCONCLUSIVE" + (" -- no power (markout SD > $10/window)" if out["no_power"] else "")
    return out


def pick_v5(log_rows, code):
    """The V5 row the bar may use: the LAST `validation_v5` row written by THIS code (sha), over the FULL set of
    finished ladder hours, run to completion. A --max-hours / --from / --to run, a stopped run, or a run of other
    code never counts (review 2026-10-17, must-fix 1: a one-hour smoke row used to read as V5 PASS). Returns
    (row or None, why-not text or None)."""
    v5 = [r for r in log_rows if r.get("ev") == "validation_v5"]
    ok = [r for r in v5 if r.get("code_sha") == code and r.get("scope") == "full" and r.get("complete")]
    if ok:
        return ok[-1], None
    if not v5:
        return None, "V5 never run"
    last = v5[-1]
    return None, ("no complete full-scope V5 run by code %s (latest: code %s, scope %s, complete %s)"
                  % (code, last.get("code_sha"), last.get("scope"), last.get("complete")))


def validations_from(log_rows, paper_rows, run_id, meta=None):
    v1 = collections.Counter()
    v3 = collections.Counter()
    v5, v5_why = pick_v5(log_rows, (run_id or "").split("-")[0])
    for r in log_rows:
        if r.get("ev") == "validation" and r.get("run") == run_id:
            v1.update(r.get("V1") or {})
            v3.update(r.get("V3") or {})
    rec = [r for r in paper_rows if r["variant"] == RECORD and r.get("prog_ok")]
    v2_n = sum(1 for r in rec if r.get("v2_ok") is not None)
    v2_ok = sum(1 for r in rec if r.get("v2_ok"))
    v4 = {}
    for ser in FX_SERIES:
        rs = [r for r in rec if r["series"] == ser]
        denom = len(rs)
        if meta is not None and rs:
            lo, hi = min(r["close_ms"] for r in rs), max(r["close_ms"] for r in rs)
            denom = max(denom, sum(1 for tk, i in meta.info.items() if tk.startswith(ser + "-") and i.get("prog")
                                   and i["prog"].get("ok") and i.get("close_ms") and lo <= i["close_ms"] <= hi))
        v4[ser] = {"windows": denom, "ok": sum(1 for r in rs if r.get("v4_ok"))}
    out = {
        "V1": {"n": v1["n"], "ok": v1["ok"], "share": v1["ok"] / v1["n"] if v1["n"] else None,
               "either_share": v1["ok_either"] / v1["n"] if v1["n"] else None},
        "V2": {"n": v2_n, "ok": v2_ok, "share": v2_ok / v2_n if v2_n else None},
        "V3": {"trades": v3["trades"], "matched": v3["matched"],
               "share": v3["matched"] / v3["trades"] if v3["trades"] else None},
        "V4": v4,
        "V5": v5,
        "V5_why_not": v5_why}
    flags = {"V1": out["V1"]["share"] is not None and out["V1"]["share"] >= V1_MIN,
             "V2": out["V2"]["share"] is not None and out["V2"]["share"] >= V2_MIN,
             "V3": out["V3"]["share"] is not None and out["V3"]["share"] >= V3_MIN,
             "V5": bool(v5 and v5.get("pass"))}
    return out, flags


def report(args, out=print):
    rows = {}
    for r in iter_paper_rows(args.paper_dir):
        rows[(r["tk"], r["variant"])] = r                 # dedupe: the last row written wins
    rows = list(rows.values())
    logs = read_log(args.log)
    runs = [r.get("run") for r in logs if r.get("ev") == "paper_hour"]
    run_id = runs[-1] if runs else None
    meta = Meta(os.path.abspath(args.root))
    meta.refresh()
    vals, flags = validations_from(logs, rows, run_id, meta)
    out("FX 15M reward paper -- %d window-variant rows, run %s" % (len(rows), run_id))
    out("Source: the recorder's own Kalshi book + trade frames (rank 1); no replay. Kraken placed at _rx_ms minus the "
        "hour's Kalshi delta lag (an assumption).")
    out("V1 book vs ticker: %s ; V2 prints vs volume_fp: %s ; V3 same-ms merge: %s ; V5: %s"
        % (_pct(vals["V1"]["share"]), _pct(vals["V2"]["share"]), _pct(vals["V3"]["share"]),
           ("NOT USABLE -- " + vals["V5_why_not"]) if not vals["V5"] else
           ("%s (code %s, %s hours %s..%s, engine/live contracts %s, 60 s mark %s vs live %s c)"
            % ("PASS" if vals["V5"].get("pass") else "FAIL", vals["V5"].get("code_sha"), vals["V5"].get("hours"),
               vals["V5"].get("first_hour"), vals["V5"].get("last_hour"),
               _f((vals["V5"].get("v5_fifo_prorata") or {}).get("ratio")),
               _f((vals["V5"].get("v5_fifo_prorata") or {}).get("mark60_c")), _f(vals["V5"].get("live_mark60_c"))))))
    out("A 'complete weekday' = a weekday FX day with >= %d non-void windows of the record variant (the builder's "
        "definition; the spec does not give one)." % FULL_DAY_MIN)
    fl_n = fl_adv = 0
    leads = []
    for r in logs:
        if r.get("ev") == "validation" and r.get("run") == run_id and r.get("flights"):
            fl_n += r["flights"].get("n") or 0
            fl_adv += r["flights"].get("adverse_ge_0.3") or 0
            if r["flights"].get("lead_ms_median") is not None:
                leads.append(r["flights"]["lead_ms_median"])
    out("Kraken lead/lag (report only): %d Kalshi flights, %s preceded by a >= 0.3 pip Kraken move against the side "
        "in the 2 s before; median of hourly median leads %s ms" % (fl_n, _pct(fl_adv / float(fl_n)) if fl_n else "-",
                                                                  _f(median(leads))))
    verdicts = {}
    for ser in FX_SERIES:
        rs = [r for r in rows if r["series"] == ser and r.get("prog_ok")]
        if not rs:
            continue
        v4 = vals["V4"].get(ser, {})
        v4ok = v4.get("windows") and v4["ok"] / float(v4["windows"]) >= V4_MIN
        good = [r for r in rs if not r.get("void")]
        by = collections.defaultdict(list)
        for r in good:
            by[r["variant"]].append(r)
        tdays = sorted(set(r["fx_day"] for r in by.get(RECORD, [])
                           if dt.date.fromisoformat(r["fx_day"]).weekday() < 5))
        full_days = [d for d in tdays if sum(1 for r in by[RECORD] if r["fx_day"] == d) >= FULL_DAY_MIN]
        late = set(full_days[2:5])
        out("")
        out("== %s  (%s)  windows %d (void %d), V4 coverage %s, trading days %s"
            % (ser, "IN THE BAR" if ser in BAR_SERIES else "report only", len(by.get(RECORD, [])),
               len(rs) - len(good), _pct(v4["ok"] / float(v4["windows"]) if v4.get("windows") else None),
               ",".join(full_days)))
        out("  %-28s %5s %8s %7s %8s %8s %8s %9s %9s %8s %9s %9s"
            % ("variant", "n", "credit", "fills", "c/settle", "c/mk60", "c/rand", "net mk60", "se", "net set",
               "worst win", "worst day"))
        for v in default_variants():
            rr = by.get(v.name, [])
            if not rr:
                continue
            q = sum(r["fills_y"] + r["fills_n"] for r in rr)
            nm = stats_of([net_mark(r) for r in rr])
            ns = [net_settle(r) for r in rr if r.get("pnl_settle_usd") is not None]
            days = collections.defaultdict(float)
            for r in rr:
                if r.get("pnl_settle_usd") is not None:
                    days[r["et_day"]] += net_settle(r)
            out("  %-28s %5d %8.2f %7.1f %8s %8s %8s %9.2f %9s %8s %9s %9s"
                % (v.name, len(rr), sum(paid(r) for r in rr) / len(rr), q / len(rr),
                   _c(sum((r["pnl_settle_usd"] or 0) for r in rr), q), _c(sum(r["mark60_usd"] for r in rr), q),
                   _c(sum(r["mark60_randsign_usd"] for r in rr), q), nm["mean"],
                   "%.2f" % nm["se"] if nm.get("se") is not None else "-",
                   "%.2f" % (sum(ns) / len(ns)) if ns else "-", "%.2f" % min(ns) if ns else "-",
                   "%.2f" % min(days.values()) if days else "-"))
        rec = by.get(RECORD, [])
        if rec:
            half = sorted(r["close_ms"] for r in rec)[len(rec) // 2]
            e = stats_of([net_mark(r) for r in rec if r["close_ms"] < half])
            l = stats_of([net_mark(r) for r in rec if r["close_ms"] >= half])
            nc = stats_of([net_mark(r, nocross=True) for r in rec])
            p10 = stats_of([net_mark(r, payout=PAYOUT_ALT) for r in rec])
            nm = stats_of([net_mark(r) for r in rec])
            out("  record variant: early half %s, late half %s; without cross fills %s; payout 1.0 %s; "
                "$/day %.0f at 96 weekday windows, %.0f at 470/7 a calendar day"
                % (_f(e.get("mean")), _f(l.get("mean")), _f(nc.get("mean")), _f(p10.get("mean")),
                   nm["mean"] * WEEKDAY_WINDOWS, nm["mean"] * CAL_WINDOWS))
            cr_raw = sum(r["credit_floored_usd"] for r in rec) / len(rec)
            out("  credit per window: %.2f before the 0.9 payout, %.2f after; the KILL line ($1.50) is read AFTER the "
                "payout (the builder's reading of 'mean credit at S = 60' with payout 0.9 in the variant of record)"
                % (cr_raw, cr_raw * PAYOUT))
            rs_c = stats_of([100.0 * r["mark60_randsign_usd"] / (r["fills_y"] + r["fills_n"]) for r in rec
                             if r["fills_y"] + r["fills_n"] > 0])
            if rs_c.get("mde") is not None:
                out("  random-sign control (60 s, c/contract per window with fills): %.3f, MDE %.3f -> %s"
                    % (rs_c["mean"], rs_c["mde"], "inside its MDE" if abs(rs_c["mean"]) < rs_c["mde"] else
                       "OUTSIDE its MDE: the markout is not a clean measure here -- read the settlement cross-check"))
            gsel = guard_holdout(by, full_days)
            if gsel:
                out("  Kraken guard: G=%s chosen on days 1-2 (%.2f/window); days 3-5 %.2f vs no guard %.2f"
                    % (gsel["G"], gsel["train"], gsel["test"], gsel["base_test"]))
        valflags = dict(flags)
        valflags["V4"] = bool(v4ok)
        vd = verdict(by, valflags, len(full_days), late)
        verdicts[ser] = vd
        if ser in BAR_SERIES:
            out("  BAR: %s; G1..G5 %s; stale fills/window %s; markout SD %s/window (MDE %s)%s"
                % (vd["decision"], vd["gates"], _f(vd.get("stale_per_window")), _f(vd["net_mark60"].get("sd")),
                   _f(vd["net_mark60"].get("mde")), ("; " + "; ".join(vd["why"])) if vd.get("why") else ""))
    pooled = collections.defaultdict(float)
    for r in rows:
        if r["series"] in BAR_SERIES and r["variant"] == RECORD and r.get("prog_ok") and not r.get("void"):
            pooled[r["close_ms"]] += net_mark(r)
    if pooled:
        ps = stats_of(list(pooled.values()))
        out("")
        out("EUR+GBP pooled, clustered by close: %d closes, mean net per close %.2f (se %s)"
            % (ps["n"], ps["mean"], _f(ps.get("se"))))
    return verdicts


def guard_holdout(by, full_days):
    if len(full_days) < 3:
        return None
    train, test = set(full_days[:2]), set(full_days[2:5])
    best = None
    for g in GUARDS:
        rr = by.get("%s_G%s" % (RECORD, g), [])
        tr = [net_mark(r) for r in rr if r["fx_day"] in train]
        if tr and (best is None or sum(tr) / len(tr) > best[1]):
            best = (g, sum(tr) / len(tr))
    if best is None:
        return None
    te = [net_mark(r) for r in by.get("%s_G%s" % (RECORD, best[0]), []) if r["fx_day"] in test]
    bt = [net_mark(r) for r in by.get(RECORD, []) if r["fx_day"] in test]
    return {"G": best[0], "train": best[1], "test": sum(te) / len(te) if te else float("nan"),
            "base_test": sum(bt) / len(bt) if bt else float("nan")}


def _pct(x):
    return "-" if x is None else "%.1f%%" % (100.0 * x)


def _c(usd, q):
    return "-" if q <= 0 else "%.2f" % (100.0 * usd / q)


def _f(x):
    return "-" if x is None else "%.2f" % x


# ================================================================================================ V5
def load_ladder(path):
    """Kalshi-confirmed ladder orders: placed (exchange ts_ms), cancelled, live_fill. Units from the fields:
    body.price is the YES price ('bid' = buy YES at price; 'ask' = sell YES at price = a NO bid at 1 - price)."""
    placed, canc, fills, closes = {}, {}, collections.defaultdict(list), {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if '"placed"' not in line and '"cancelled"' not in line and '"live_fill"' not in line \
                    and '"live_market"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            ev = d.get("ev")
            if ev == "placed":
                b = d.get("body") or {}
                mt = re.search(r"'ts_ms': (\d+)", str(d.get("resp", "")))
                if not mt or b.get("side") not in ("bid", "ask"):
                    continue
                yp = px(b["price"])
                side, price = (YES, yp) if b["side"] == "bid" else (NO, 1000 - yp)
                placed[d["order_id"]] = {"tk": b["ticker"], "s": side, "price": price, "size": float(b["count"]),
                                         "land": int(mt.group(1)), "sent": iso_ms(d["t"])}
            elif ev == "cancelled":
                mt = re.search(r"'ts_ms': (\d+)", str(d.get("resp", "")))
                canc[d["order_id"]] = {"t": iso_ms(d["t"]), "status": d.get("status"),
                                       "ts": int(mt.group(1)) if (mt and d.get("status") == 200) else None}
            elif ev == "live_fill":
                fills[d["kid"]].append({"t": iso_ms(d["t"]), "q": float(d.get("delta") or 0)})
            elif ev == "live_market":
                if d.get("close_s"):
                    closes[d["ticker"]] = int(d["close_s"]) * 1000
    orders = []
    for kid, o in placed.items():
        c = canc.get(kid) or {}
        close = closes.get(o["tk"])
        if c.get("ts") is not None:
            die = c["ts"]
        elif c.get("t") is not None:
            die = min(c["t"], close) if close else c["t"]
        else:
            die = close
        orders.append(dict(o, kid=kid, die=die, close=close, live_q=sum(f["q"] for f in fills.get(kid, [])),
                           live_fills=fills.get(kid, [])))
    return orders


def v5_gate(complete, ratio, eng_mark_c, live_mark_c):
    """V5 passes only on a complete run with engine contracts within 0.67-1.5x of live AND the 60 s markout within
    V5_MARK_C cents/contract of live (fifo_prorata)."""
    return bool(complete and ratio is not None and V5_RATIO[0] <= ratio <= V5_RATIO[1]
                and eng_mark_c is not None and live_mark_c is not None
                and abs(eng_mark_c - live_mark_c) <= V5_MARK_C)


def v5_hours(orders, from_hour=None, to_hour=None, max_hours=0, now_ms=None):
    """The collector hours V5 replays: every hour holding a Kalshi-confirmed ladder order, minus any hour whose end
    is less than FOLLOW_WAIT_S ago (the collector is still writing it, and the next hour's `determined` frames are not
    in yet -- review 2026-10-17, must-fix 1). Returns (hours, unfinished hours left out, scope): scope is 'full' only
    when no --from/--to/--max-hours cut was asked for; only a 'full' run can pass the bar's V5."""
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    hours = sorted(set(hour_of_ms(o["land"]) for o in orders))
    unfinished = [h for h in hours if hour_start_ms(h) + 3600 * 1000 + FOLLOW_WAIT_S * 1000 > now_ms]
    hours = [h for h in hours if h not in set(unfinished)]
    cut = bool(from_hour or to_hour or max_hours)
    if from_hour:
        hours = [h for h in hours if h >= from_hour]
    if to_hour:
        hours = [h for h in hours if h <= to_hour]
    if max_hours:
        hours = hours[:max_hours]
    return hours, unfinished, ("subset" if cut else "full")


def run_v5(args, say=print):
    data = args.data
    slog = SLog(args.log)
    orders = load_ladder(args.orders)
    hours, unfinished, scope = v5_hours(orders, args.from_hour, args.to_hour, args.max_hours)
    if args.max_seconds:
        scope = "subset"
    hs = set(hours)
    orders = [o for o in orders if hour_of_ms(o["land"]) in hs]
    sha = code_sha()
    slog.write("v5_start", argv=sys.argv, code_sha=sha, scope=scope, data=data, orders_path=args.orders,
               orders=len(orders), hours_planned=len(hours), first_hour=hours[0] if hours else None,
               last_hour=hours[-1] if hours else None, unfinished_hours_left_out=unfinished,
               rss_mb=round(rss_mb(), 1))

    def on_hour(row):
        slog.write("v5_hour", code_sha=sha, scope=scope, **row)
    res = v5_replay(data, orders, hours, say=say, max_seconds=args.max_seconds, stop_path=args.stop,
                    on_hour=on_hour)
    res.update(code_sha=sha, scope=scope, unfinished_hours_left_out=unfinished,
               bar_ok=bool(res.get("pass") and res.get("complete") and scope == "full"))
    slog.write("validation_v5", **res)
    say(json.dumps(res, indent=1)[:3000])
    return 0 if res.get("complete") else 3


def v5_replay(data, orders, hours, say=None, max_seconds=None, results_override=None, stop_path=None,
              on_hour=None):
    """Replay real orders hour by hour through the SAME engine (scheduled mode) on a collector-format tape."""
    t0 = time.time()
    variants = [Variant("v5_" + q, None, 0, q, None) for q in MODELS]
    by_hour = collections.defaultdict(list)
    for o in orders:
        by_hour[hour_of_ms(o["land"])].append(o)
    totals = {v.name: {"q": 0.0, "mark_usd": 0.0, "mark_q": 0.0, "m10_usd": 0.0, "m10_q": 0.0} for v in variants}
    eng_kid = collections.defaultdict(float)          # fifo_prorata contracts per order
    live_kid = {o["kid"]: o["live_q"] for o in orders}
    live = {"q": 0.0, "mark_usd": 0.0, "mark_q": 0.0, "m10_usd": 0.0, "m10_q": 0.0}
    n_orders = 0
    done_hours = []
    complete = True
    stopped = None
    for h in hours:
        if max_seconds and time.time() - t0 > max_seconds:
            complete = False
            stopped = "max_seconds"
            break
        if stop_path and os.path.exists(stop_path):
            complete = False
            stopped = "stop_file"
            break
        hs_orders = by_hour.get(h, [])
        tks = sorted(set(o["tk"] for o in hs_orders))
        if not tks:
            continue
        results = dict(results_override or {})
        if results_override is None:
            for hh in (h, next_hour(h)):
                for d in _iter(data, "market_lifecycle_v2", hh):
                    msg = d.get("msg") or {}
                    if msg.get("event_type") == "determined" and msg.get("market_ticker") in tks:
                        results[msg["market_ticker"]] = str(msg.get("result", "")).lower()
        eng = Engine(variants, prefixes=tuple(tks), meta=None, scheduled=True)
        tw = collections.defaultdict(list)
        for o in hs_orders:
            tw[o["tk"]].append((o["land"] - 5000, (o["die"] or o["land"]) + 1000))
        eng.trade_windows = dict(tw)
        for o in hs_orders:
            for vi in range(len(variants)):
                eng.inject(o["tk"], vi, o["s"], o["price"], o["size"], o["land"], o["die"], o["kid"])
            for f in o["live_fills"]:
                eng.probe(o["tk"], f["t"] + 60000, (o["kid"], f["q"], o["s"], o["price"], 60))
                eng.probe(o["tk"], f["t"] + 10000, (o["kid"], f["q"], o["s"], o["price"], 10))
            n_orders += 1
        ok = run_hour(eng, data, h, say=say,
                      stop_check=(lambda: os.path.exists(stop_path)) if stop_path else None)
        if ok is not True:
            complete = False
            stopped = ok
            break
        # also the next hour's head, for orders that live across the boundary (the ladder trades the last 30 s)
        for tk in list(eng.markets):
            m = eng.markets[tk]
            close = max([o["close"] or 0 for o in hs_orders if o["tk"] == tk] or [0])
            m.close_ms = close or (m.last_ts or 0)
            won_m = eng.finish(m, results.get(tk), None)
            if not won_m:
                continue
            mm, won = won_m
            for vi, v in enumerate(variants):
                for fl in mm.vs[vi].fills:
                    totals[v.name]["q"] += fl.q
                    if v.q == "fifo_prorata":
                        eng_kid[fl.kid] += fl.q
                    for which, ku, kq in ((1, "mark_usd", "mark_q"), (0, "m10_usd", "m10_q")):
                        mid = fl.marks[which]
                        if mid is not None:
                            val = ((mid - fl.price) if fl.s == YES else ((1000 - mid) - fl.price)) * fl.q / 1000.0
                            totals[v.name][ku] += val
                            totals[v.name][kq] += fl.q
            for (key, mid) in mm.probes:
                kid, q, s, price, hz = key
                ku, kq = ("mark_usd", "mark_q") if hz == 60 else ("m10_usd", "m10_q")
                if hz == 60:
                    live["q"] += q
                if mid is not None:
                    live[ku] += ((mid - price) if s == YES else ((1000 - mid) - price)) * q / 1000.0
                    live[kq] += q
        done_hours.append(h)
        if on_hour is not None:
            on_hour({"hour": h, "orders": len(hs_orders), "live_contracts_total": round(live["q"], 4),
                     "engine_contracts_total": {k: round(t["q"], 4) for k, t in totals.items()},
                     "secs": round(time.time() - t0, 1), "rss_mb": round(rss_mb(), 1)})
    out = {"hours": len(done_hours), "hours_planned": len(hours), "orders": n_orders, "complete": complete,
           "stopped": stopped, "first_hour": done_hours[0] if done_hours else None,
           "last_hour": done_hours[-1] if done_hours else None,
           "live_contracts": live["q"], "secs": round(time.time() - t0, 1),
           "live_mark60_c": 100.0 * live["mark_usd"] / live["mark_q"] if live["mark_q"] else None,
           "live_mark10_c": 100.0 * live["m10_usd"] / live["m10_q"] if live["m10_q"] else None,
           "note_marks": "the ladder fills in the last ~30 s, so most 60 s marks resolve to settlement for BOTH sides; "
                         "the 10 s mark (report only, not in the gate) is the one that sees the book"}
    for name, tt in totals.items():
        out[name] = {"contracts": tt["q"], "ratio": tt["q"] / live["q"] if live["q"] else None,
                     "mark60_c": 100.0 * tt["mark_usd"] / tt["mark_q"] if tt["mark_q"] else None,
                     "mark10_c": 100.0 * tt["m10_usd"] / tt["m10_q"] if tt["m10_q"] else None}
    kids = set(k for k, q in live_kid.items() if q > 0) | set(k for k, q in eng_kid.items() if q > 0)
    out["orders_filled"] = {"both": sum(1 for k in kids if live_kid.get(k, 0) > 0 and eng_kid.get(k, 0) > 0),
                            "live_only": sum(1 for k in kids if live_kid.get(k, 0) > 0 and eng_kid.get(k, 0) <= 0),
                            "engine_only": sum(1 for k in kids if live_kid.get(k, 0) <= 0 and eng_kid.get(k, 0) > 0)}
    pr = out["v5_fifo_prorata"]
    out["pass"] = v5_gate(complete, pr["ratio"], pr["mark60_c"], out["live_mark60_c"])
    return out


# ================================================================================================ self-test
class Tape(object):
    """Writes a synthetic hour in the recorder's real file format (gzip JSONL per channel, frames as received)."""

    def __init__(self, root):
        self.root = root
        self.buf = collections.defaultdict(list)
        self.n = 0

    def _w(self, chan, rx, obj):
        self.n += 1
        obj["_rx_ms"] = rx
        self.buf[(chan, hour_of_ms(rx))].append((rx, self.n, obj))

    @staticmethod
    def d(x):
        return "%.4f" % (x / 1000.0)

    def snap(self, tk, sid, yes, no, rx):
        self._w("orderbook_snapshot", rx, {"type": "orderbook_snapshot", "sid": sid, "seq": 0, "msg": {
            "market_ticker": tk, "market_id": "x", "yes_dollars_fp": [[self.d(p), "%.2f" % z] for p, z in yes],
            "no_dollars_fp": [[self.d(p), "%.2f" % z] for p, z in no]}})

    def delta(self, tk, sid, side, p, dq, ts, lag=10):
        self._w("orderbook_delta", ts + lag, {"type": "orderbook_delta", "sid": sid, "seq": 0, "msg": {
            "market_ticker": tk, "market_id": "x", "price_dollars": self.d(p), "delta_fp": "%.2f" % dq,
            "side": side, "ts_ms": ts}})

    def trade(self, tk, taker_side, yes_p, q, ts, lag=10, raw_yes=None):
        self._w("trade", ts + lag, {"type": "trade", "sid": 2, "seq": 0, "msg": {
            "trade_id": "t%d" % self.n, "market_ticker": tk,
            "yes_price_dollars": raw_yes if raw_yes is not None else self.d(yes_p),
            "no_price_dollars": self.d(1000 - yes_p), "count_fp": "%.2f" % q, "taker_side": taker_side,
            "is_block_trade": False, "ts_ms": ts}})

    def ticker(self, tk, yb, ybs, ya, yas, ts, lag=50):
        self._w("ticker", ts + lag, {"type": "ticker", "sid": 3, "msg": {
            "market_ticker": tk, "yes_bid_dollars": self.d(yb), "yes_ask_dollars": self.d(ya),
            "yes_bid_size_fp": "%.2f" % ybs, "yes_ask_size_fp": "%.2f" % yas, "ts_ms": ts}})

    def program(self, tk, open_ms, close_ms, rx, reward=500000, target="300.00", dfb=5000):
        self._w("programs", rx, {"type": "program", "row": {
            "id": "p-" + tk, "market_ticker": tk, "period_reward": reward, "target_size_fp": target,
            "discount_factor_bps": dfb, "start_date": ms_iso(open_ms), "end_date": ms_iso(close_ms),
            "paid_out": False}})

    def market(self, tk, open_ms, close_ms, rx):
        self._w("markets", rx, {"type": "rest_market", "market": {
            "ticker": tk, "status": "initialized", "open_time": ms_iso(open_ms), "close_time": ms_iso(close_ms)}})

    def determined(self, tk, result, rx):
        self._w("market_lifecycle_v2", rx, {"type": "market_lifecycle_v2", "sid": 1, "seq": 0, "msg": {
            "market_ticker": tk, "event_type": "determined", "result": result}})

    def settled(self, tk, result, volume, rx):
        self._w("settled", rx, {"type": "settled", "market": {"ticker": tk, "result": result,
                                                              "volume_fp": "%.2f" % volume}})

    def suspect(self, tks, rx):
        self._w("suspect", rx, {"type": "suspect", "state": "start", "tickers": list(tks), "why": "seq_gap"})

    def heartbeat(self, rx):
        self._w("heartbeat", rx, {"type": "heartbeat", "kalshi": True, "kraken": True})

    def kraken(self, sym, bid, ask, rx, snapshot=False, ok=True):
        self._w("kraken_book", rx, {"channel": "book", "type": "snapshot" if snapshot else "update", "data": [{
            "symbol": sym, "bids": [{"price": bid, "qty": 100.0}], "asks": [{"price": ask, "qty": 100.0}],
            "checksum": 0}], "_crc_ok": ok})

    def close(self):
        """Written in RECEIVE order, as the recorder's single socket thread writes them; _rx_n follows that order."""
        allrec = sorted((rx, n, chan, h, obj) for (chan, h), lst in self.buf.items() for rx, n, obj in lst)
        fh = {}
        for k, (rx, n, chan, h, obj) in enumerate(allrec):
            obj["_rx_n"] = k + 1
            if (chan, h) not in fh:
                d = os.path.join(self.root, chan)
                os.makedirs(d, exist_ok=True)
                fh[(chan, h)] = gzip.open(os.path.join(d, h + ".jsonl.gz"), "at", encoding="utf-8")
            fh[(chan, h)].write(json.dumps(obj, separators=(",", ":")) + "\n")
        for f in fh.values():
            f.close()
        self.buf.clear()


def _run_world(root, variants, mutants=None, hours=None, prefixes=None):
    mutants = mutants or {}
    meta = Meta(root)
    meta.refresh()
    eng = Engine(variants, prefixes=prefixes or tuple(s + "-" for s in FX_SERIES), meta=meta, **mutants)
    rows = []
    for h in hours or available_hours(root):
        meta.refresh()
        eng.refresh_meta()
        run_hour(eng, root, h)
        meta.refresh()
        rows += finish_due(eng, meta, hour_start_ms(h) + 3600 * 1000, "selftest", h)
    return eng, rows


def selftest(verbose=False):
    n = [0]

    def ck(cond, what):
        n[0] += 1
        if not cond:
            raise AssertionError("SELFTEST FAIL: " + what)
    tmp = tempfile.mkdtemp(prefix="fxreward_selftest_")
    try:
        _selftest_body(tmp, ck, verbose)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("fxreward_paper selftest OK: %d checks" % n[0])
    return True


def _peak_mb():
    """Peak working set of this process so far, MB (Windows); ru_maxrss elsewhere."""
    try:
        if sys.platform == "win32":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                            ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            fn = getattr(k32, "K32GetProcessMemoryInfo", None) or ctypes.windll.psapi.GetProcessMemoryInfo
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
            if not fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return -1.0
            return pmc.PeakWorkingSetSize / 1048576.0
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return -1.0


def _gz_member(lines, level=6, trailer=True, cut=None, enc="utf-8"):
    """One gzip member as bytes (zlib wbits 31), each line sync-flushed like the collector's per-line flush; no
    trailer = a writer that was killed; cut = keep only the first `cut` bytes (killed in the middle of a block)."""
    c = zlib.compressobj(level, zlib.DEFLATED, 31)
    out = []
    for ln in lines:
        out.append(c.compress((ln + "\n").encode(enc)))
        out.append(c.flush(zlib.Z_SYNC_FLUSH))
    if trailer:
        out.append(c.flush())
    b = b"".join(out)
    return b[:cut] if cut is not None else b


def _selftest_streams(tmp, ck, say):
    """Must-fix 1 and 4 of the 2026-10-17 review: the gzip reader and the Kraken stream in BOUNDED memory, and the
    reader's correctness on every file state the two recorders leave. Runs FIRST, while the process is small, so a
    reader that loads a file whole shows up in the peak working set."""
    # -- correctness on planted files
    L1 = ['{"n":%d,"m":1}' % i for i in range(300)]
    L2 = ['{"n":%d,"m":2}' % i for i in range(200)]

    def read(name, blob):
        fp = os.path.join(tmp, name)
        with open(fp, "wb") as fh:
            fh.write(blob)
        st = {}
        return list(gz_lines(fp, st)), st
    got, st = read("one.gz", _gz_member(L1))
    ck(got == L1 and not st, "gz_lines: a healthy one-member file, every line, nothing flagged: %r" % st)
    got, st = read("two.gz", _gz_member(L1) + _gz_member(L2))
    ck(got == L1 + L2 and not st, "gz_lines: two healthy members (an appended restart that closed cleanly)")
    got, st = read("untr.gz", _gz_member(L1, trailer=False))
    ck(got == L1 and st.get("gz_untrailered") == 1, "gz_lines: an untrailered member (the hour still being written) "
       "yields every flushed line: %d of %d, %r" % (len(got), len(L1), st))
    got, st = read("crash.gz", _gz_member(L1, trailer=False) + _gz_member(L2))
    ck(got == L1 + L2 and st.get("gz_broken_members") == 1 and st.get("gz_resyncs") == 1,
       "gz_lines: a killed member + the restart's member (gzsalvage's case): both halves, no duplicates: %d, %r"
       % (len(got), st))
    full1 = _gz_member(L1, trailer=False)
    got, st = read("cut.gz", full1[:len(full1) * 2 // 3 + 7] + _gz_member(L2))
    js = []
    for g in got:
        try:
            js.append(json.loads(g))
        except ValueError:
            pass
    n1 = [j["n"] for j in js if j.get("m") == 1]
    n2 = [j["n"] for j in js if j.get("m") == 2]
    ck(n2 == list(range(200)) and n1 == list(range(len(n1))) and 150 <= len(n1) < 300 and st.get("gz_resyncs") == 1,
       "gz_lines: a member cut mid-block + a new member: the cut member's head, then ALL of the new one: %d + %d, %r"
       % (len(n1), len(n2), st))
    # a chance gzip magic INSIDE the broken member's bytes (a stored block of raw text) must not be taken for the
    # restart's member: the resync validates every candidate before trusting it
    Lm = ["x\x1f\x8b\x08\x00junk-%d" % i for i in range(5)] + L1[:20]
    mblob = _gz_member(Lm, level=0, trailer=False, enc="latin-1") + _gz_member(L2)
    want_m = [x.encode("latin-1").decode("utf-8", "replace") for x in Lm] + L2
    ck(mblob.count(GZ_MAGIC) == 7, "the planted file holds 5 raw magics inside member 1's stored blocks: %d"
       % mblob.count(GZ_MAGIC))
    got, st = read("magic.gz", mblob)
    ck(got == want_m and st.get("gz_resyncs") == 1, "gz_lines: 5 chance magics inside a broken member are skipped by "
       "the candidate check: %d lines, %r" % (len(got), st))
    # corruption INSIDE a member just before the restart's member (bytes overwritten, decoding to garbage lines
    # before it errors): the garbage must not come out, the new member must
    m1 = _gz_member(L1, trailer=False)
    blob_c = None
    for seed in range(300):
        rr = random.Random(seed)
        at = 1500 + rr.randrange(1200)
        cand = m1[:at] + bytes(rr.getrandbits(8) for _ in range(120)) + m1[at + 120:]
        dd = zlib.decompressobj(31)
        outb = b""
        for i in range(len(cand)):
            try:
                outb += dd.decompress(cand[i:i + 1])
            except zlib.error:
                break
        if any(x.rstrip(b"\r").decode("utf-8", "replace") not in set(L1) for x in outb.split(b"\n")[:-1]):
            blob_c = cand
            break
    ck(blob_c is not None, "a junk overwrite that decodes to garbage lines exists in 300 tries")
    got, st = read("corrupt_then_member.gz", blob_c + _gz_member(L2))
    ck(set(got) <= set(L1) | set(L2) and [g for g in got if '"m":2' in g] == L2,
       "gz_lines: garbage decoded from a corrupt stretch before the next member is dropped, the next member kept: "
       "%d lines, %r" % (len(got), st))
    # the hold-back drop itself: at a 32-byte piece size a garbage run spans several pieces before the decoder errors
    # (seed 0: 1-360 junk bytes near the member's end); the pieces before the failing one must be dropped too
    global GZ_FEED
    feed0 = GZ_FEED
    try:
        GZ_FEED = 32
        rr = random.Random(0)
        J = 60 + rr.randrange(300)
        gap = rr.randrange(3) * 50
        at = len(m1) - J - gap
        blob_h = m1[:at] + bytes(rr.getrandbits(8) for _ in range(J)) + m1[at + J:]
        for name, tail in (("no member after", b""), ("a member after", _gz_member(L2))):
            got, st = read("holdback.gz", blob_h + tail)
            ck(set(got) <= set(L1) | set(L2) and st.get("gz_garbage_lines_dropped", 0) > 0,
               "gz_lines hold-back (%s): a garbage run over several pieces is dropped, none yielded: %r" % (name, st))
    finally:
        GZ_FEED = feed0
    got, st = read("empty.gz", b"")
    ck(got == [] and not st, "gz_lines: an empty file")
    # big members (poorly compressible lines, so the hold-back window and piece boundaries are exercised)
    rng0 = random.Random(5)
    LB = ['{"n":%d,"m":1,"x":"%s"}' % (i, "%032x%032x" % (rng0.getrandbits(128), rng0.getrandbits(128)))
          for i in range(4000)]
    LC = ['{"n":%d,"m":2,"x":"%s"}' % (i, "%032x" % rng0.getrandbits(128)) for i in range(500)]
    ends, c0, acc = [], zlib.compressobj(6, zlib.DEFLATED, 31), []
    for ln in LB:                                    # raw offset at which each line is fully flushed
        acc.append(c0.compress((ln + "\n").encode()))
        acc.append(c0.flush(zlib.Z_SYNC_FLUSH))
        ends.append(sum(len(x) for x in acc))
    mb = b"".join(acc)
    # (i) killed in the middle of a block, then a restart member: the decoder reads the new member as data (garbage)
    cut_at = int(len(mb) * 0.7) + 3
    got, st = read("bigcut.gz", mb[:cut_at] + _gz_member(LC))
    pre = [g for g in got if '"m":1' in g]
    ck(set(got) <= set(LB) | set(LC) and pre == LB[:len(pre)] and [g for g in got if '"m":2' in g] == LC,
       "gz_lines: a big member cut mid-block + a restart: no garbage line, the cut member's head in order, all of the "
       "new member: %d + %d, %r" % (len(pre), len(got) - len(pre), st))
    ck(len(pre) >= sum(1 for e in ends if e <= cut_at) - 1, "gz_lines: the cut member keeps every line flushed "
       "before the cut (bar one): %d of %d" % (len(pre), sum(1 for e in ends if e <= cut_at)))
    # (i-b) the same, at a cut where the decoder runs ON into the new member's bytes for a while (garbage) before it
    #       errors -- found by scanning cut points; the garbage must be dropped and the head before the cut kept
    mc = _gz_member(LC)
    gcut, glen = None, 0
    for k in range(400):
        cand = int(len(mb) * 0.7) + 11 * k
        dd = zlib.decompressobj(31)
        dd.decompress(mb[:cand])
        blob = mc[:4096]
        nout = 0
        for i in range(len(blob)):
            try:
                nout += len(dd.decompress(blob[i:i + 1]))
            except zlib.error:
                break
        if nout > 0:
            gcut, glen = cand, nout
            break
    ck(gcut is not None, "a cut point whose decoder turns the next member's bytes into output exists in 400 tries")
    got, st = read("bigcutg.gz", mb[:gcut] + mc)
    pre = [g for g in got if '"m":1' in g]
    ck(set(got) <= set(LB) | set(LC) and pre == LB[:len(pre)] and [g for g in got if '"m":2' in g] == LC
       and len(pre) >= sum(1 for e in ends if e <= gcut) - 2 and st.get("gz_resyncs") == 1,
       "gz_lines: a cut that turns the next member into %d bytes of garbage: none of it yielded, the head (%d of %d) "
       "and the whole new member kept: %r" % (glen, len(pre), sum(1 for e in ends if e <= gcut), st))
    # (ii) corrupted inside a member (bytes overwritten), no member after: drop the hold-back, never yield garbage
    bad_at = int(len(mb) * 0.6)
    junk = bytes(rng0.getrandbits(8) for _ in range(4000))
    got, st = read("bigcorrupt.gz", mb[:bad_at] + junk + mb[bad_at + 4000:])
    ck(set(got) <= set(LB) and got == LB[:len(got)]
       and len(got) >= sum(1 for e in ends if e <= bad_at - GZ_HOLD - GZ_FEED) - 1,
       "gz_lines: a member corrupted inside: only genuine lines, in order, all but the last <= %d KB before the "
       "corruption: %d lines, %r" % ((GZ_HOLD + GZ_FEED) // 1024, len(got), st))
    # -- bounded memory: a ~30 MB (decompressed) UNTRAILERED Kraken hour, written streaming (no spike while writing)
    root = os.path.join(tmp, "krmem")
    os.makedirs(os.path.join(root, "kraken_book"))
    fp = os.path.join(root, "kraken_book", "20261019T14.jsonl.gz")
    hs = hour_start_ms("20261019T14")
    n_fr = 150000
    tmpl = ('{"channel":"book","type":"update","data":[{"symbol":"EUR/USD","bids":[{"price":1.%05d,"qty":125.5}],'
            '"asks":[{"price":1.%05d,"qty":98.25}],"checksum":3735928559}],"_crc_ok":true,"_rx_ms":%d}')
    c = zlib.compressobj(6, zlib.DEFLATED, 31)
    nbytes = 0
    with open(fp, "wb") as fh:
        snap = ('{"channel":"book","type":"snapshot","data":[{"symbol":"EUR/USD","bids":[{"price":1.12340,"qty":1.0}],'
                '"asks":[{"price":1.12342,"qty":1.0}],"checksum":0}],"_crc_ok":true,"_rx_ms":%d}\n' % hs)
        fh.write(c.compress(snap.encode()))
        buf = []
        for i in range(n_fr):
            k = 12340 - (i % 7)
            buf.append(tmpl % (k, k + 2, hs + 1 + i * 20))
            if len(buf) == 2000:
                blob = ("\n".join(buf) + "\n").encode()
                nbytes += len(blob)
                fh.write(c.compress(blob))
                fh.write(c.flush(zlib.Z_SYNC_FLUSH))
                buf = []
        # deliberately NO c.flush(): no trailer, the state of a file still being written
    p0 = _peak_mb()
    t0 = time.time()
    st = {}
    nl = sum(1 for _ in gz_lines(fp, st))
    p1 = _peak_mb()
    say("  gz_lines on %.1f MB decompressed / %.1f MB on disk, untrailered: %d lines in %.2f s, peak +%.1f MB"
        % (nbytes / 1e6, os.path.getsize(fp) / 1e6, nl, time.time() - t0, p1 - p0))
    ck(nl == n_fr + 1 and st.get("gz_untrailered") == 1, "gz_lines: every line of the big untrailered file: %d" % nl)
    ck(p0 > 0 and p1 - p0 < 12.0, "gz_lines reads a %.0f MB untrailered file in bounded memory: peak grew %.1f MB "
       "(the salvage pass would grow ~%.0f MB)" % (nbytes / 1e6, p1 - p0, 3.36 * nbytes / 1048576.0))
    eng = Engine([Variant(RECORD, 60, 300, "fifo_prorata", None)])     # no guard variant: on_kraken stays cheap
    gen = kraken_iter(eng, root, "20261019T14", 30)
    ck(hasattr(gen, "__next__") and not isinstance(gen, (list, tuple)), "kraken_iter is a stream, not a list")
    gen.close()
    p0 = _peak_mb()
    t0 = time.time()
    ok = run_hour(eng, root, "20261019T14")
    p1 = _peak_mb()
    nk = eng.stat["kraken_frames_streamed"]
    say("  run_hour on a %d-frame Kraken hour: %.2f s, peak +%.1f MB" % (nk, time.time() - t0, p1 - p0))
    ck(ok is True and nk == n_fr + 1 and eng.stat["side_events_held_max"] == 0,
       "run_hour: every validated Kraken frame streamed, none held: %d" % nk)
    ck(p1 - p0 < 12.0, "run_hour streams %d Kraken frames in bounded memory: peak grew %.1f MB (holding them as a "
       "list ~%.0f MB)" % (nk, p1 - p0, nk * 214 / 1048576.0))
    shutil.rmtree(root, ignore_errors=True)


def _selftest_body(tmp, ck, verbose):
    say = print if verbose else (lambda *a, **k: None)
    _selftest_streams(tmp, ck, say)
    H = "20261019T14"
    hs = hour_start_ms(H)
    T0 = hs + 15 * 60 * 1000                       # open 14:15Z, close 14:30Z, T_STOP 14:25Z
    C0 = T0 + 900 * 1000

    # ---------------------------------------------------------------- (e) units
    ck(px("0.5500") == 550 and px("0.0100") == 10 and px("1.0000") == 1000, "dollar strings -> tenths of a cent")
    for bad in ("1.2", "55", "-0.01", "x"):
        try:
            px(bad)
            ck(False, "price %r must abort" % bad)
        except UnitError:
            ck(True, "unit abort")
    ck(abs(cc_to_usd(500000) - 50.0) < 1e-12, "500000 centi-cents -> $50.00")
    ck(_tk_of('{"type":"trade","msg":{"market_ticker":"KXEURUSD15M-X","ts_ms":1}}') == "KXEURUSD15M-X"
       and _tk_of('{"msg": {"market_ticker": "KXGBPUSD15M-Y"}}') == "KXGBPUSD15M-Y" and _tk_of('{"a":1}') == "",
       "the ticker prefilter reads both JSON separators")

    # ---------------------------------------------------------------- (c) the credit walk, by hand
    Y = 60.0 / 622.5
    Nn = 60.0 / (70 + 75 * 0.5 + 75 * 0.25 + 75 * 0.125 + 75 * 0.0625)
    w = walk({550: 562.5}, 300.0, 0.5, {550: 60.0})
    ck(w[0] and w[1] == 550 and abs(w[3] - Y) < 1e-12, "YES walk share 60/622.5: %r" % (w,))
    nob = {400: 10.0, 390: 75.0, 380: 75.0, 370: 75.0, 360: 75.0, 350: 75.0}
    w = walk(nob, 300.0, 0.5, {400: 60.0})
    ck(w[0] and w[1] == 400 and abs(w[3] - Nn) < 1e-12, "NO walk share 60/140.3125: %r" % (w,))
    ck(not walk({400: 10.0, 390: 75.0, 380: 75.0}, 300.0, 0.5, {400: 60.0})[0], "short side does not qualify")
    ck(not walk({990: 400.0}, 300.0, 0.5)[0], "a 99c best bid disqualifies the side (filing)")

    # ---------------------------------------------------------------- a tape with planted answers (a), (b), (c)
    root = os.path.join(tmp, "w1")
    tp = Tape(root)
    TA, TB, TC, TD, TE = ("KXEURUSD15M-26OCT191030-A", "KXEURUSD15M-26OCT191030-B", "KXGBPUSD15M-26OCT191030-C",
                          "KXGBPUSD15M-26OCT191030-D", "KXUSDJPY15M-26OCT191030-E")
    TF, TG, TH = "KXAUDUSD15M-26OCT191030-F", "KXAUDUSD15M-26OCT191030-G", "KXUSDCAD15M-26OCT191030-H"
    for tk in (TA, TB, TC, TD, TE, TF, TG, TH):
        tp.program(tk, T0, C0, hs + 1000)
        tp.market(tk, T0, C0, hs + 1000)
    for k in range(0, 3600, 5):
        tp.heartbeat(hs + k * 1000 + 500)
    deep_no = [(400, 100.0)] + [(p, 300.0) for p in range(390, 340, -10)]
    deep_yes = [(550, 100.0)] + [(p, 300.0) for p in range(540, 490, -10)]
    # (a) queue: we join behind 100 at 0.55; +50 behind us; -40 cancel; a taker sells 105 at 0.55
    tp.snap(TA, 9, deep_yes, deep_no, T0 - 60000)
    tp.delta(TA, 9, "no", 300, 1.0, T0 + 1000)                    # a far event after the open lands our orders
    tp.delta(TA, 9, "yes", 550, 50.0, T0 + 2000)
    tp.delta(TA, 9, "yes", 550, -40.0, T0 + 3000)
    tp.trade(TA, "no", 550, 105.0, T0 + 4000)
    tp.delta(TA, 9, "yes", 550, -105.0, T0 + 4000)
    tp.ticker(TA, 550, 5.0, 600, 100.0, T0 + 4000)                # V1: matches the rebuilt book at the end of the ms
    tp.ticker(TA, 550, 5.0, 610, 100.0, T0 + 5000)                # V1: a planted mismatch (wrong ask)
    # (b) pick-off: 562.5 at 0.55 leave at t0; a 100-lot NO bid at 0.45 arrives at t0 + 200 ms
    t0b = T0 + 10000
    tp.snap(TB, 9, [(550, 562.5), (540, 75.0), (530, 300.0)], deep_no, T0 - 50000)
    tp.delta(TB, 9, "no", 300, 1.0, T0 + 1000)
    tp.delta(TB, 9, "yes", 550, -562.5, t0b)
    tp.delta(TB, 9, "no", 450, 100.0, t0b + 200)
    # (c) credit: 562.5 on YES; NO = 10 + 75 per cent; a 10-second NO dip below the target
    tp.snap(TC, 9, [(550, 562.5)], [(400, 10.0), (390, 75.0), (380, 75.0), (370, 75.0), (360, 75.0),
                                    (350, 75.0)], T0 - 40000)
    tp.delta(TC, 9, "no", 350, -75.0, T0 + 100500)
    tp.delta(TC, 9, "no", 360, -75.0, T0 + 100500)
    tp.delta(TC, 9, "no", 360, 75.0, T0 + 110500)
    # (c) the floor: NO qualifies only 30 s (k = 200..229) -> raw credit < $1 -> floored to 0
    tp.snap(TD, 9, [(550, 562.5)], [(400, 10.0), (390, 75.0), (380, 75.0)], T0 - 30000)
    tp.delta(TD, 9, "no", 370, 150.0, T0 + 199500)
    tp.delta(TD, 9, "no", 370, -150.0, T0 + 229500)
    # V4: a market with a 10-second suspect span inside its window
    tp.snap(TE, 9, deep_yes, deep_no, T0 - 20000)
    tp.suspect([TE], T0 + 50000)
    tp.snap(TE, 9, deep_yes, deep_no, T0 + 60000)
    # post_only: we re-peg up to 0.56; the 0.56 others leave and NO rises to 0.44 before our order lands
    t1 = T0 + 20000
    tp.snap(TF, 9, deep_yes, [(400, 100.0)] + [(p, 300.0) for p in range(390, 340, -10)] + [(430, 0.0)], T0 - 15000)
    tp.delta(TF, 9, "no", 300, 1.0, T0 + 1000)
    tp.delta(TF, 9, "yes", 560, 100.0, t1)
    tp.delta(TF, 9, "yes", 560, -100.0, t1 + 100)
    tp.delta(TF, 9, "no", 440, 100.0, t1 + 150)
    # the band: YES best 0.95 and NO best 0.03 are both outside 10-90c -> never quoted
    tp.snap(TG, 9, [(950, 400.0)], [(30, 400.0)], T0 - 10000)
    tp.trade(TG, "no", 950, 2.0, T0 + 6000)                       # V3: consumed 50 ms later, not in its own ms
    tp.delta(TG, 9, "yes", 950, -2.0, T0 + 6050)
    # walk-past pick-off on the NO side: the 0.40 NO bids leave at t2; a taker buys YES through NO 0.39 at
    # t2 + 200 ms -> our stale 0.40 NO (L=300) is walked past for 30; at L=150 it was already re-pegged
    t2 = T0 + 30000
    tp.snap(TH, 9, deep_yes, deep_no, T0 - 5000)
    tp.delta(TH, 9, "no", 300, 1.0, T0 + 1000)
    tp.delta(TH, 9, "no", 400, -100.0, t2)
    tp.trade(TH, "yes", 610, 30.0, t2 + 200)
    tp.delta(TH, 9, "no", 390, -30.0, t2 + 200)
    for tk in (TA, TB, TC, TD, TE, TF, TG, TH):
        tp.determined(tk, "no", C0 + 2000)
    tp.settled(TA, "no", 105.0, C0 + 360000)
    tp.settled(TB, "no", 7.0, C0 + 360000)                         # V2: a planted mismatch (no prints, 7 settled)
    tp.close()
    V = [Variant("S60_L300_%s" % q, 60, 300, q, None) for q in MODELS]
    V += [Variant("S60_L150_fifo_prorata", 60, 150, "fifo_prorata", None)]
    eng, rows = _run_world(root, V)
    R = {(r["tk"], r["variant"]): r for r in rows}
    ck(len(rows) == 8 * len(V), "one row per window and variant: %d" % len(rows))
    rh3, rh1 = R[(TH, "S60_L300_fifo_prorata")], R[(TH, "S60_L150_fifo_prorata")]
    ck(rh3["fills_n"] == 30.0 and rh3["kinds"].get("walk") == 30.0 and rh3["kinds"].get("stale") == 30.0
       and rh1["n_fills"] == 0, "walk-past: a stale 30-lot NO fill at L=300, none at L=150: %r %r"
       % (rh3["kinds"], rh1["kinds"]))
    ck(abs(rh3["mark60_usd"] - ((1000 - 580) - 400) * 30 / 1000.0) < 1e-9
       and abs(rh3["pnl_settle_usd"] - (1000 - 400) * 30 / 1000.0) < 1e-9,
       "NO fill: 60 s markout (1 - mid 0.58) - 0.40 = +2c x 30 and settlement +$18.00: %r %r"
       % (rh3["mark60_usd"], rh3["pnl_settle_usd"]))
    ck(R[(TA, "S60_L300_fifo_front")]["kinds"].get("stale", 0) == 0, "(a) a queue fill at the touch is not stale")
    rf = R[(TF, "S60_L300_fifo_prorata")]
    ck(rf["rejects"] == 1 and rf["n_fills"] == 0, "post_only: the landing 0.56 bid would cross NO 0.44 -> rejected "
       "once: %r" % ((rf["rejects"], rf["kinds"]),))
    rg = R[(TG, "S60_L300_fifo_prorata")]
    ck(rg["rest_s_y"] == 0 and rg["rest_s_n"] == 0 and rg["band_out_s_y"] == 599 and rg["band_out_s_n"] == 599
       and rg["band_lost_usd"] > 0 and rg["credit_usd"] == 0.0, "band 10-90c: never quoted, the lost credit "
       "is logged: %r" % ((rg["rest_s_y"], rg["band_out_s_y"], rg["band_lost_usd"]),))
    # YES 400 others until the 2-lot leaves at +6.05 s (6 s at 60/460, then 593 s at 60/458); NO 599 s at 60/460
    want_g = 50.0 * (6 * 60.0 / 460.0 + 593 * 60.0 / 458.0 + 599 * 60.0 / 460.0) / 1800.0
    ck(abs(rg["band_lost_usd"] - want_g) < 1e-6, "band-lost credit by hand %.6f: %r" % (want_g, rg["band_lost_usd"]))
    want_a = {"last": 0.0, "fifo_behind": 5.0, "fifo_prorata": 105.0 - 100.0 * 110.0 / 150.0, "fifo_front": 45.0}
    for q, want in want_a.items():
        got = R[(TA, "S60_L300_%s" % q)]["fills_y"]
        ck(abs(got - want) < 1e-4, "(a) queue fill under %s: want %.4f got %.4f" % (q, want, got))
    rb3, rb1 = R[(TB, "S60_L300_fifo_prorata")], R[(TB, "S60_L150_fifo_prorata")]
    ck(rb1["fills_y"] == 0.0 and rb1["n_fills"] == 0, "(b) L=150: the old order died before the cross: %r"
       % rb1["kinds"])
    ck(abs(rb3["fills_y"] - 60.0) < 1e-9 and rb3["kinds"].get("cross") == 60.0 and rb3["kinds"].get("stale") == 60.0,
       "(b) L=300: a full 60-lot stale cross fill: %r" % rb3["kinds"])
    ck(rb3["cap_drops"] == 1 and rb3["inv_at_stop"] == 60.0, "(b) at the +60 cap the re-pegged YES bid is dropped at "
       "landing: %r" % ((rb3["cap_drops"], rb3["inv_at_stop"]),))
    ck(abs(rb3["mark60_usd"] - (545 - 550) * 60 / 1000.0) < 1e-9, "(b) 60 s markout to the mid 0.545: %r"
       % rb3["mark60_usd"])
    ck(abs(rb3["pnl_settle_usd"] - (0 - 550) * 60 / 1000.0) < 1e-9, "(b) settles NO: -$33.00")
    ck(rb3["stale_episodes"] == 1 and rb3["stale_ms"] == 200, "(b) L=300: stale 200 ms until picked off: %r"
       % ((rb3["stale_episodes"], rb3["stale_ms"]),))
    ck(rb1["stale_episodes"] == 1 and rb1["stale_ms"] == 150, "(b) L=150: stale 150 ms until the cancel lands: %r"
       % ((rb1["stale_episodes"], rb1["stale_ms"]),))
    rc = R[(TC, "S60_L300_fifo_prorata")]
    want_c = 50.0 * 589 * (Y + Nn) / 1800.0
    # 600 scored seconds; 10 (the NO dip) do not qualify; second 0 qualifies but our orders land at +300 ms, so
    # 589 seconds carry our share
    ck(rc["counted_s"] == 590 and rc["scored_s"] == 600 and abs(rc["credit_usd"] - want_c) < 1e-6
       and abs(rc["credit_floored_usd"] - want_c) < 1e-6,
       "(c) credit %.6f: got %r over %r counted s" % (want_c, rc["credit_usd"], rc["counted_s"]))
    ck(abs(rc["share_y"] - Y * 589 / 590.0) < 1e-6 and abs(rc["share_n"] - Nn * 589 / 590.0) < 1e-6,
       "(c) mean shares over counted seconds by hand: %r %r" % (rc["share_y"], rc["share_n"]))
    ck(rc["n_fills"] == 0 and rc["writes"] == 4, "(c) a static book: 2 posts + 2 cancels at T_STOP: %r"
       % rc["writes"])
    rd = R[(TD, "S60_L300_fifo_prorata")]
    want_d = 50.0 * 30 * (Y + 60.0 / 145.0) / 1800.0
    ck(rd["counted_s"] == 30 and abs(rd["credit_usd"] - want_d) < 1e-6 and rd["credit_floored_usd"] == 0.0,
       "(c) under-$1 window floored to 0: raw %r want %.6f" % (rd["credit_usd"], want_d))
    ck(R[(TE, RECORD)]["v4_ok"] is False and abs(R[(TE, RECORD)]["suspect_s"] - 10.0) < 0.05,
       "V4: a 10 s suspect span voids the window: %r" % R[(TE, RECORD)]["suspect_s"])
    ck(R[(TA, RECORD)]["v4_ok"] is True and R[(TA, RECORD)]["v2_ok"] is True, "V2/V4 pass on a clean window")
    ck(R[(TB, RECORD)]["v2_ok"] is False, "V2: prints != volume_fp is caught")
    ck(eng.v3["trades"] == 3 and eng.v3["matched"] == 2, "V3: two prints consumed in their own ms, one 50 ms late: %r"
       % dict(eng.v3))
    ck(eng.v1["n"] == 2 and eng.v1["ok"] == 1, "V1: one ticker matches, the planted mismatch does not: %r"
       % dict(eng.v1))

    # ---------------------------------------------------------------- the batch driver and --report, end to end
    ns = argparse.Namespace(root=root, paper_dir=os.path.join(tmp, "paper"), log=os.path.join(tmp, "plog.jsonl"),
                            stop=os.path.join(tmp, "nostop"), from_hour=None, to_hour=None, series=[])
    ck(process(ns, follow=False, say=lambda *a: None, now_fn=lambda: 4.0e9) == 0, "batch driver runs")
    lg = read_log(ns.log)
    ck([r["ev"] for r in lg if r["ev"] in ("start", "paper_hour", "end")] == ["start", "paper_hour", "end"]
       and sum(1 for r in lg if r["ev"] == "day_summary") > 0, "start / paper_hour / day_summary / end rows")
    prow = list(iter_paper_rows(ns.paper_dir))
    ck(len(prow) == 8 * 26, "26 variants x 8 windows written: %d" % len(prow))
    lines = []
    vd = report(ns, out=lines.append)
    ck(any("KXEURUSD15M" in x and "IN THE BAR" in x for x in lines) and vd["KXEURUSD15M"]["decision"] == "VOID",
       "--report runs and a 1-window read is VOID: %r" % vd.get("KXEURUSD15M", {}).get("why"))
    process(ns, follow=False, say=lambda *a: None, now_fn=lambda: 4.0e9)
    ck(len(list(iter_paper_rows(ns.paper_dir))) == 8 * 26, "a second batch run re-uses its done hours (no new rows)")

    # ---------------------------------------------------------------- (d) mutants must be REJECTED
    _, rows_m = _run_world(root, V, {"mut_lat0": True})
    Rm = {(r["tk"], r["variant"]): r for r in rows_m}
    ck(Rm[(TB, "S60_L300_fifo_prorata")]["n_fills"] == 0, "(d) latency forced to 0 loses the pick-off -> rejected")
    _, rows_m = _run_world(root, V, {"mut_ignore_queue": True})
    Rm = {(r["tk"], r["variant"]): r for r in rows_m}
    ck(abs(Rm[(TA, "S60_L300_fifo_behind")]["fills_y"] - 5.0) > 1.0, "(d) queue ignored fills too much -> rejected")
    _, rows_m = _run_world(root, V, {"mut_no_qual": True})
    Rm = {(r["tk"], r["variant"]): r for r in rows_m}
    ck(abs(Rm[(TD, "S60_L300_fifo_prorata")]["credit_usd"] - want_d) > 0.1,
       "(d) counting unqualified seconds changes the credit -> rejected")

    # ---------------------------------------------------------------- (e) a price > 1 in a tape aborts the run
    root_u = os.path.join(tmp, "units")
    tp = Tape(root_u)
    tp.program(TA, T0, C0, hs + 1000)
    tp.market(TA, T0, C0, hs + 1000)
    tp.snap(TA, 9, deep_yes, deep_no, T0 - 60000)
    tp.trade(TA, "no", 550, 5.0, T0 + 4000, raw_yes="55")
    tp.close()
    try:
        _run_world(root_u, V)
        ck(False, "(e) a '55' dollar price must abort the hour")
    except UnitError:
        ck(True, "(e) unit abort in the stream")

    # ---------------------------------------------------------------- heartbeat gap -> suspect (V4)
    root_h = os.path.join(tmp, "hb")
    tp = Tape(root_h)
    tp.program(TA, T0, C0, hs + 1000)
    tp.market(TA, T0, C0, hs + 1000)
    tp.snap(TA, 9, deep_yes, deep_no, T0 - 60000)
    for k in range(0, 3600, 5):
        t = hs + k * 1000
        if not (T0 + 100000 <= t <= T0 + 140000):
            tp.heartbeat(t)
    tp.delta(TA, 9, "no", 300, 1.0, T0 + 1000)
    tp.snap(TA, 9, deep_yes, deep_no, T0 + 150000)               # the recorder came back
    tp.close()
    _, rows_h = _run_world(root_h, [Variant(RECORD, 60, 300, "fifo_prorata", None)])
    ck(len(rows_h) == 1 and rows_h[0]["v4_ok"] is False and rows_h[0]["suspect_s"] > 40,
       "a heartbeat gap > 15 s is suspect until the next snapshot: %r" % (rows_h[0]["suspect_s"],))

    # ---------------------------------------------------------------- the recorder dies INSIDE the hour (must-fix 2)
    REC1 = [Variant(RECORD, 60, 300, "fifo_prorata", None)]
    v4 = {}
    for case in ("up_all_hour", "dies_1416_back_1510", "dies_1416_never_back"):
        rt = os.path.join(tmp, "hbt_" + case)
        tp = Tape(rt)
        tp.program(TA, T0, C0, hs + 1000)
        tp.market(TA, T0, C0, hs + 1000)
        tp.snap(TA, 9, deep_yes, deep_no, T0 - 60000)
        last_hb = hs + 3600 * 1000 if case == "up_all_hour" else T0 + 60000
        for k in range(0, 3600, 5):
            if hs + k * 1000 <= last_hb:
                tp.heartbeat(hs + k * 1000)
        tp.delta(TA, 9, "no", 300, 1.0, T0 + 1000)
        if case != "dies_1416_never_back":
            h15 = hs + 3600 * 1000
            for k in range(0 if case == "up_all_hour" else 600, 3600, 5):
                tp.heartbeat(h15 + k * 1000)
        tp.determined(TA, "no", C0 + 2000)
        tp.close()
        _, rr = _run_world(rt, REC1, hours=[H])
        v4[case] = rr[0]
    ck(v4["up_all_hour"]["v4_ok"] is True and v4["up_all_hour"]["suspect_s"] == 0.0,
       "a recorder up all hour leaves its window clean: %r" % v4["up_all_hour"]["suspect_s"])
    for case in ("dies_1416_back_1510", "dies_1416_never_back"):
        ck(v4[case]["v4_ok"] is False and v4[case]["void"] and v4[case]["suspect_s"] > 500,
           "a recorder that dies at 14:16 (%s) voids the 14:15 window although the gap ends after the hour: "
           "suspect %r s" % (case, v4[case]["suspect_s"]))

    # ---------------------------------------------------------------- one print never fills more than it printed
    #                                                                   (must-fix 3), unit level on the engine
    def one_print(q_model, orders, books, q=30.0, p=540):
        e1 = Engine([Variant("u", 60, 300, q_model, None)], prefixes=("KXEURUSD15M-",))
        mk = e1.market("KXEURUSD15M-UNIT")
        mk.snap = True
        mk.books = ({k: v for k, v in books.items()}, {400: 100.0})
        e1._recompute_best(mk, YES)
        e1._recompute_best(mk, NO)
        mk.last_ts = 1000
        mk.dirty = False
        for (price, rem, ahead) in orders:
            o = Order(price, rem, 0, 10 ** 12)
            o.landed, o.ahead, o.ahead0 = True, ahead, ahead
            mk.vs[0].orders[YES].append(o)
        e1.on_trade("KXEURUSD15M-UNIT", "no", p, 1000 - p, q, 2000)
        fl = mk.vs[0].fills
        return sum(f.q for f in fl), collections.Counter(f.mech for f in fl)
    for qm in MODELS:
        tot, mech = one_print(qm, [(550, 60.0, 0.0), (540, 60.0, 10.0)], {540: 110.0, 530: 300.0})
        ck(abs(tot - 30.0) < 1e-9 and mech["walk"] == 1 and mech.get("queue", 0) == 0,
           "%s: a 30-lot print walks our stale 0.55 order for 30 and leaves nothing for our 0.54 order: %.1f %r"
           % (qm, tot, dict(mech)))
        tot, _ = one_print(qm, [(540, 30.0, 0.0), (540, 30.0, 5.0)], {540: 110.0, 530: 300.0})
        want = 0.0 if qm == "last" else 30.0
        ck(abs(tot - want) < 1e-9, "%s: two of our orders at the print price share ONE 30-lot print: %.1f (want %.1f)"
           % (qm, tot, want))
    tot, _ = one_print("fifo_front", [(540, 60.0, 10.0)], {540: 110.0, 530: 300.0})
    ck(abs(tot - 20.0) < 1e-9, "one order 10 behind the front: a 30-lot print fills 20: %.1f" % tot)

    # ---------------------------------------------------------------- two of OUR orders on one side never take the
    #  position past S (must-fix 3): the touch moves twice inside L, the old order is still live when the new one
    #  lands -> the new one is clipped by the old one's size, and the side is re-decided when the old one dies
    def overlap_world(name, second_print):
        rt = os.path.join(tmp, name)
        tp = Tape(rt)
        tp.program(TA, T0, C0, hs + 1000)
        tp.market(TA, T0, C0, hs + 1000)
        for k in range(0, 3600, 5):
            tp.heartbeat(hs + k * 1000)
        for k in range(0, 3600, 5):
            tp.heartbeat(hs + 3600 * 1000 + k * 1000)
        tp.snap(TA, 9, [(550, 100.0), (540, 10.0), (530, 300.0), (520, 300.0)], deep_no, T0 - 60000)
        tp.delta(TA, 9, "yes", 550, -100.0, T0 + 100)       # the others leave 0.55 before our first order lands
        tp.delta(TA, 9, "yes", 540, 100.0, T0 + 450)        # 100 join the 0.54 level
        tp.trade(TA, "no", 540, 30.0, T0 + 500)             # a taker sells 30 at 0.54
        tp.delta(TA, 9, "yes", 540, -30.0, T0 + 500)
        if second_print:
            tp.trade(TA, "no", 540, 70.0, T0 + 550)         # ... and 70 more
            tp.delta(TA, 9, "yes", 540, -70.0, T0 + 550)
        tp.determined(TA, "no", C0 + 2000)
        tp.close()
        _, rr = _run_world(rt, [Variant("S60_L300_%s" % q, 60, 300, q, None) for q in MODELS], hours=[H])
        return {r["variant"]: r for r in rr}
    ow = overlap_world("ovl1", False)
    for qm in MODELS:
        r = ow["S60_L300_%s" % qm]
        ck(abs(r["fills_y"] - 30.0) < 1e-9 and r["kinds"].get("stale") == 30.0 and r["exposure_clips"] == 1
           and r["max_abs_inv"] <= 60.0 + 1e-9, "%s: the stale 0.55 order is walked for 30, the overlapping 0.54 "
           "order is clipped to nothing: %r" % (qm, (r["fills_y"], r["kinds"], r["exposure_clips"])))
        ck(r["rest_s_y"] == 599, "%s: the side is re-quoted when the old order dies (a decision at its death): "
           "rested %d s of 599" % (qm, r["rest_s_y"]))
    ow = overlap_world("ovl2", True)
    for qm in MODELS:
        r = ow["S60_L300_%s" % qm]
        ck(r["max_abs_inv"] <= 60.0 + 1e-9 and abs(r["fills_y"] - 60.0) < 1e-9,
           "%s: two prints (30 + 70) never take the position past +60: max %r, fills %r"
           % (qm, r["max_abs_inv"], r["fills_y"]))
    # the same overlap with NO print afterwards: nothing marks the market dirty, so only the decision at the old
    # order's death re-quotes the side
    rt = os.path.join(tmp, "ovl3")
    tp = Tape(rt)
    tp.program(TA, T0, C0, hs + 1000)
    tp.market(TA, T0, C0, hs + 1000)
    for k in range(0, 7200, 5):
        tp.heartbeat(hs + k * 1000)
    tp.snap(TA, 9, [(550, 100.0), (540, 10.0), (530, 300.0), (520, 300.0)], deep_no, T0 - 60000)
    tp.delta(TA, 9, "yes", 550, -100.0, T0 + 100)
    tp.delta(TA, 9, "yes", 540, 100.0, T0 + 450)
    tp.determined(TA, "no", C0 + 2000)
    tp.close()
    _, rr = _run_world(rt, [Variant(RECORD, 60, 300, "fifo_prorata", None)], hours=[H])
    ck(rr[0]["exposure_clips"] == 1 and rr[0]["n_fills"] == 0 and rr[0]["rest_s_y"] == 599,
       "with no later event the side is re-quoted at the old order's death: rested %d s of 599, clips %d"
       % (rr[0]["rest_s_y"], rr[0]["exposure_clips"]))

    # ---------------------------------------------------------------- the Kraken guard pulls a side for 2 s
    root_k = os.path.join(tmp, "kr")
    tp = Tape(root_k)
    tp.program(TA, T0, C0, hs + 1000)
    tp.market(TA, T0, C0, hs + 1000)
    tp.snap(TA, 9, deep_yes, deep_no, T0 - 60000)
    for k in range(0, 3600, 5):
        tp.heartbeat(hs + k * 1000)
    tp.kraken("EUR/USD", 1.12340, 1.12342, T0 - 5000, snapshot=True)
    tp.delta(TA, 9, "no", 300, 1.0, T0 + 1000)
    tp.kraken("EUR/USD", 1.12320, 1.12322, T0 + 20000, snapshot=True)    # -2 pips at once: pull YES at G <= 2
    tp.delta(TA, 9, "no", 300, 1.0, T0 + 30000)
    tp.close()
    VG = [Variant(RECORD, 60, 300, "fifo_prorata", None), Variant(RECORD + "_G1.0", 60, 300, "fifo_prorata", 1.0)]
    _, rows_k = _run_world(root_k, VG)
    Rk = {r["variant"]: r for r in rows_k}
    ck(Rk[RECORD + "_G1.0"]["guard_pulls"] == 1 and Rk[RECORD]["guard_pulls"] == 0,
       "the guard fires once on a -2 pip Kraken move: %r" % Rk[RECORD + "_G1.0"]["guard_pulls"])
    ck(Rk[RECORD]["rest_s_y"] - Rk[RECORD + "_G1.0"]["rest_s_y"] == 2,
       "the pulled YES side rests 2 s less: %r vs %r" % (Rk[RECORD]["rest_s_y"], Rk[RECORD + "_G1.0"]["rest_s_y"]))

    # ---------------------------------------------------------------- (f) NULL world and an adverse world
    def world(adverse, seed):
        """120 windows. NULL: a random-walk mid, takers of either side at the touch only >= 2 s after any book
        move, every move made without a crossing add while a stale order of ours could still be live, so fills are
        queue fills whose timing is independent of the future path: the 60 s markout is the half-spread (+0.5c)
        and the random-sign control is 0. ADVERSE: also, every 25-45 s a seller sweeps the YES bid (and 60 more one
        level down), then the price falls 3c over the next 2.6 s."""
        rootw = os.path.join(tmp, "null%d" % int(adverse))
        rng = random.Random(seed)
        tpw = Tape(rootw)
        for slot in range(4):
            o = hs + slot * 900000
            c = o + 900000
            for j in range(30):
                tk = "KXEURUSD15M-NULL%d-%02d" % (slot, j)
                tpw.program(tk, o, c, hs)
                tpw.market(tk, o, c, hs)
                bk = {"yes": {}, "no": {}}
                st = {"bid": 500, "ask": 510}
                for i in range(6):
                    bk["yes"][500 - 10 * i] = 100.0 if i == 0 else 300.0
                    bk["no"][490 - 10 * i] = 100.0 if i == 0 else 300.0
                tpw.snap(tk, 9, sorted(bk["yes"].items(), reverse=True), sorted(bk["no"].items(), reverse=True),
                         o - 5000)

                def dl(side, p, dq, t, tk=tk, bk=bk):
                    tpw.delta(tk, 9, side, p, dq, t)
                    v = bk[side].get(p, 0.0) + dq
                    if v <= 1e-9:
                        bk[side].pop(p, None)
                    else:
                        bk[side][p] = v

                def refill(t, bk=bk, st=st, dl=dl):
                    for i in range(1, 6):
                        if st["bid"] - 10 * i not in bk["yes"]:
                            dl("yes", st["bid"] - 10 * i, 300.0, t)
                        if (1000 - st["ask"]) - 10 * i not in bk["no"]:
                            dl("no", (1000 - st["ask"]) - 10 * i, 300.0, t)
                t = o + 2000
                last_move = o
                next_inf = o + rng.randint(20, 60) * 1000
                while t < c - 300000:
                    bid, ask = st["bid"], st["ask"]
                    if adverse and t >= next_inf and t - last_move >= 2000 and bid >= 350:
                        qq = bk["yes"][bid]
                        tpw.trade(tk, "no", bid, qq, t)
                        tpw.trade(tk, "no", bid - 10, 60.0, t)
                        dl("yes", bid, -qq, t)
                        dl("yes", bid - 10, -60.0, t)
                        for step in range(3):
                            tt = t + 2000 + 300 * step
                            new_ask = st["ask"] - 10
                            for pp in [pp for pp in list(bk["yes"]) if pp >= new_ask]:
                                dl("yes", pp, -bk["yes"][pp], tt)
                            dl("no", 1000 - new_ask, 100.0, tt)
                            st["ask"] = new_ask
                        st["bid"] = max(bk["yes"])
                        if st["bid"] < st["ask"] - 10:
                            dl("yes", st["ask"] - 10, 100.0, t + 2700)
                            st["bid"] = st["ask"] - 10
                        refill(t + 2800)
                        t += 4000
                        last_move = t
                        next_inf = t + rng.randint(25, 45) * 1000
                        continue
                    if t - last_move >= 2000 and rng.random() < 0.5:
                        if rng.random() < 0.5:
                            q = min(rng.randint(20, 80), bk["yes"].get(bid, 0.0))
                            if q > 0:
                                tpw.trade(tk, "no", bid, q, t)
                                dl("yes", bid, -q, t)
                                dl("yes", bid, q, t + 1)
                        else:
                            nb = 1000 - ask
                            q = min(rng.randint(20, 80), bk["no"].get(nb, 0.0))
                            if q > 0:
                                tpw.trade(tk, "yes", ask, q, t)
                                dl("no", nb, -q, t)
                                dl("no", nb, q, t + 1)
                    elif t - last_move >= 2000 and rng.random() < 0.12 and 300 <= bid <= 700:
                        if rng.random() < 0.5:                  # up: the NO best leaves, YES improves 1.5 s later
                            dl("no", 1000 - ask, -bk["no"][1000 - ask], t)
                            dl("yes", bid + 10, 100.0, t + 1500)
                            st["bid"], st["ask"] = bid + 10, ask + 10
                        else:                                   # down: the YES best leaves, NO improves 1.5 s later
                            dl("yes", bid, -bk["yes"][bid], t)
                            dl("no", 1000 - (ask - 10), 100.0, t + 1500)
                            st["bid"], st["ask"] = bid - 10, ask - 10
                        refill(t + 1600)
                        last_move = t + 1600
                        t += 2000
                        continue
                    t += 1000
                tpw.determined(tk, "yes" if st["bid"] >= 500 else "no", c + 2000)
            tpw.close()          # one 15-min slot at a time: the buffered frames of 120 windows peaked ~+96 MB
        tpw.close()
        _, rws = _run_world(rootw, [Variant(RECORD, 60, 300, "fifo_prorata", None)], prefixes=("KXEURUSD15M-",))
        return rws

    def mark_stats(rws, key):
        per = [r[key] / (r["fills_y"] + r["fills_n"]) * 100.0 for r in rws if r["fills_y"] + r["fills_n"] > 0]
        return stats_of(per)
    null = world(False, 7)
    s_mk = mark_stats(null, "mark60_usd")
    s_rs = mark_stats(null, "mark60_randsign_usd")
    say("  null: n %d windows with fills, mark60 %.3f c (se %.3f), rand %.3f c (se %.3f)"
        % (s_mk["n"], s_mk["mean"], s_mk["se"], s_rs["mean"], s_rs["se"]))
    ck(s_mk["n"] >= 60, "(f) the null world produces fills in most windows: %d" % s_mk["n"])
    ck(abs(s_mk["mean"] - 0.5) < s_mk["mde"], "(f) NULL: markout = the half-spread +0.5c within its MDE: %.3f +- %.3f"
       % (s_mk["mean"], s_mk["mde"]))
    ck(abs(s_rs["mean"]) < s_rs["mde"], "(f) NULL: the random-sign control sits inside its MDE: %.3f +- %.3f"
       % (s_rs["mean"], s_rs["mde"]))
    adv = world(True, 8)
    a_mk = mark_stats(adv, "mark60_usd")
    a_rs = mark_stats(adv, "mark60_randsign_usd")
    say("  adverse: mark60 %.3f c (se %.3f), rand %.3f c" % (a_mk["mean"], a_mk["se"], a_rs["mean"]))
    ck(a_mk["mean"] - 0.5 < -a_mk["mde"] and (0.5 - a_mk["mean"]) / a_mk["se"] > 5.0,
       "(f) ADVERSE: sellers before a 3c drop are detected below the half-spread: %.3f +- %.3f"
       % (a_mk["mean"], a_mk["mde"]))
    ck(abs(a_rs["mean"]) < max(a_rs["mde"], 0.5) or abs(a_rs["mean"]) < abs(a_mk["mean"]),
       "(f) ADVERSE: the random-sign control stays far smaller than the signal")

    # ---------------------------------------------------------------- V5 on a collector-format tape
    root5 = os.path.join(tmp, "v5")
    tp = Tape(root5)
    TK5 = "KXBTC15M-26OCT191030-30"
    tp.snap(TK5, 4, [(970, 50.0), (960, 100.0)], [(20, 80.0)], T0 - 1000)
    tp.delta(TK5, 4, "yes", 970, 1.0, T0 + 870000)               # our own order's add (lands behind 50)
    tp.trade(TK5, "no", 970, 51.0, T0 + 880000)                  # sweeps 50 ahead + our 1
    tp.delta(TK5, 4, "yes", 970, -51.0, T0 + 880000)
    tp.determined(TK5, "yes", C0 + 1000)
    tp.close()
    orders5 = [{"tk": TK5, "s": YES, "price": 970, "size": 1.0, "land": T0 + 870000, "die": C0, "kid": "k1",
                "close": C0, "live_q": 1.0, "live_fills": [{"t": T0 + 880500, "q": 1.0}]},
               {"tk": TK5, "s": YES, "price": 960, "size": 1.0, "land": T0 + 870000, "die": C0, "kid": "k2",
                "close": C0, "live_q": 0.0, "live_fills": []}]
    res = v5_replay(root5, orders5, [H])
    ck(res["v5_fifo_prorata"]["contracts"] == 1.0 and res["live_contracts"] == 1.0 and res["pass"]
       and res["orders_filled"] == {"both": 1, "live_only": 0, "engine_only": 0},
       "V5: the engine reproduces the planted live fill, order for order: %r" % res)
    orders5[1]["live_fills"] = [{"t": T0 + 880500, "q": 1.0}]
    orders5[1]["live_q"] = 1.0
    res = v5_replay(root5, orders5, [H])
    ck(not res["pass"] and abs(res["v5_fifo_prorata"]["ratio"] - 0.5) < 1e-9,
       "V5: half the live fills -> ratio 0.5 -> FAIL")

    # ---------------------------------------------------------------- the verdict logic on planted rows
    def mkrow(ser, var, close_ms, credit, m60, settle, stale=0, cross=0.0):
        return {"tk": "%s-%d" % (ser, close_ms), "series": ser, "variant": var, "close_ms": close_ms,
                "et_day": et_day(close_ms), "fx_day": fx_day(close_ms), "credit_floored_usd": credit,
                "mark60_usd": m60, "mark60_nocross_usd": m60 - cross, "pnl_settle_usd": settle,
                "kinds": {"n_stale": stale}, "fills_y": 30.0, "fills_n": 30.0, "prog_ok": True, "void": False}
    base = int(dt.datetime(2026, 10, 19, 4, 0, tzinfo=UTC).timestamp() * 1000)
    rng = random.Random(3)
    closes = [base + i * 900000 for i in range(5 * 96)]

    def rowset(net_mean, credit, settle_sd=8.0, noise_sd=4.0):
        by = collections.defaultdict(list)
        for i, c in enumerate(closes):
            e = rng.gauss(0, noise_sd)
            cr = credit
            m60 = net_mean - cr * PAYOUT + e
            st = m60 + rng.gauss(0, settle_sd)
            for var in (RECORD, WORSTQ, FAST):
                by[var].append(mkrow("KXEURUSD15M", var, c, cr, m60, max(-40.0, st), stale=1 if i % 5 == 0 else 0))
        return by
    days = sorted(set(fx_day(c) for c in closes))
    allv = {"V1": True, "V2": True, "V3": True, "V4": True, "V5": True}
    vg = verdict(rowset(2.0, 3.0), allv, 5, set(days[2:5]))
    ck(vg["decision"].startswith("GO"), "verdict: a planted +$2/window world is GO: %s %r" % (vg["decision"],
                                                                                            vg["gates"]))
    vk = verdict(rowset(-1.0, 3.0), allv, 5, set(days[2:5]))
    ck(vk["decision"] == "KILL", "verdict: a planted -$1/window world is KILL: %s" % vk["decision"])
    vc = verdict(rowset(1.0, 1.2), allv, 5, set(days[2:5]))
    ck(vc["decision"] == "KILL", "verdict: credit $1.08 paid < $1.50 is KILL: %s" % vc["decision"])
    vv = verdict(rowset(2.0, 3.0), dict(allv, V5=None), 5, set(days[2:5]))
    ck(vv["decision"] == "VOID" and "V5" in vv["why"][0], "verdict: V5 not run -> VOID: %r" % vv.get("why"))
    vi = verdict(rowset(0.6, 3.0), allv, 5, set(days[2:5]))
    ck(vi["decision"].startswith("INCONCLUSIVE"), "verdict: +$0.60 is INCONCLUSIVE: %s" % vi["decision"])
    vi = verdict(rowset(0.8, 3.0, settle_sd=1.0, noise_sd=1.0), allv, 5, set(days[2:5]))
    ck(vi["decision"].startswith("INCONCLUSIVE") and not vi["gates"]["G1"] and vi["gates"]["G2"]
       and vi["net_mark60"]["lo"] > 0 and vi["late_mean"] >= 0.5,
       "verdict: a tight +$0.80 fails only G1's $1.00 line -> INCONCLUSIVE: %s %r" % (vi["decision"], vi["gates"]))
    # every gate on its own, at its own threshold (the review's mutants of each slipped through before)
    def setrows(rec_fn, fast_fn=None, worst_fn=None, stale_every=5, n=5 * 96):
        by = collections.defaultdict(list)
        for i, c in enumerate(closes[:n]):
            cr, m60, st = rec_fn(i, c)
            by[RECORD].append(mkrow("KXEURUSD15M", RECORD, c, cr, m60, st, stale=1 if i % stale_every == 0 else 0))
            for var, fn in ((FAST, fast_fn), (WORSTQ, worst_fn)):
                cr2, m2, s2 = (fn or rec_fn)(i, c)
                by[var].append(mkrow("KXEURUSD15M", var, c, cr2, m2, s2))
        return by

    def net_to(net, i, sd=1.0, cr=3.0, settle_off=0.0, settle_sd=1.0):
        """credit cr, a markout giving net per window = net +- sd (alternating, so the mean is exact)."""
        m60 = net - cr * PAYOUT + (sd if i % 2 else -sd)
        return cr, m60, m60 + settle_off + (settle_sd if (i // 2) % 2 else -settle_sd)
    late = set(days[2:5])
    vb = verdict(setrows(lambda i, c: net_to(2.0, i)), allv, 5, late)
    ck(vb["decision"].startswith("GO") and all(vb["gates"].values()), "the planted base world is GO: %s %r"
       % (vb["decision"], vb["gates"]))
    vk = verdict(setrows(lambda i, c: net_to(2.0, i), fast_fn=lambda i, c: net_to(-0.05, i, sd=2.0)), allv, 5, late)
    ck(vk["decision"] == "KILL" and vk["fast"]["mean"] < 0 < vk["fast"]["hi"] < 1.0,
       "KILL: L=150 mean -$0.05 with its upper bound +%.2f (between $0 and $1.00) is KILL: %s"
       % (vk["fast"].get("hi", float("nan")), vk["decision"]))
    vg3 = verdict(setrows(lambda i, c: net_to(2.0, i, settle_off=-1.5, settle_sd=0.5)), allv, 5, late)
    ck(not vg3["gates"]["G3"] and vg3["decision"].startswith("INCONCLUSIVE") and vg3["gates"]["G1"],
       "G3: settlement $1.50 below the markout (many SE) fails G3 alone: %r" % vg3["gates"])
    vg5w = verdict(setrows(lambda i, c: (lambda t: (t[0], t[1], -50.0 - t[0] * PAYOUT) if i == 77 else t)(
        net_to(2.0, i))), allv, 5, late)
    ck(not vg5w["gates"]["G5"] and vg5w["worst_window_settle"] < -45.0,
       "G5: one window at -$50 (settlement) fails G5: %r" % vg5w["worst_window_settle"])
    d3 = et_day(closes[200])
    hit = [i for i, c in enumerate(closes) if et_day(c) == d3][:30]
    vg5d = verdict(setrows(lambda i, c: (lambda t: (t[0], t[1], -20.0 - t[0] * PAYOUT) if i in hit else t)(
        net_to(2.0, i))), allv, 5, late)
    ck(not vg5d["gates"]["G5"] and vg5d["worst_window_settle"] >= -45.0 and vg5d["worst_et_day_settle"] < -150.0,
       "G5: 30 windows of one ET day at -$20 (each above -$45, the day %.0f) fail G5's day clause"
       % vg5d["worst_et_day_settle"])
    vg1 = verdict(setrows(lambda i, c: net_to(0.2 if fx_day(c) in late else 3.0, i, sd=0.5)), allv, 5, late)
    ck(not vg1["gates"]["G1"] and vg1["net_mark60"]["mean"] >= 1.0 and vg1["net_mark60"]["lo"] > 0
       and vg1["late_mean"] < 0.5, "G1: overall +$%.2f but the late half +$0.20 fails G1 on the late-half rule"
       % vg1["net_mark60"]["mean"])
    vg4 = verdict(setrows(lambda i, c: net_to(2.0, i), stale_every=20), allv, 5, late)
    ck(not vg4["gates"]["G4"] and abs(vg4["stale_per_window"] - 0.05) < 1e-9,
       "G4: 1 stale fill per 20 windows is under the 1-per-10 line: %r" % vg4["stale_per_window"])
    vn = verdict(setrows(lambda i, c: net_to(2.0, i), n=300), allv, 5, late)
    ck(vn["decision"] == "VOID" and any("only 300 windows" in w for w in vn["why"]),
       "MIN_WINDOWS: 300 windows is VOID: %r" % vn.get("why"))
    ck(abs(paid({"credit_floored_usd": 10.0}) - 9.0) < 1e-12, "payout 0.9: $10.00 of credit pays $9.00")
    vcr = verdict(setrows(lambda i, c: net_to(2.0, i, cr=1.6)), allv, 5, late)
    ck(vcr["decision"] == "KILL" and abs(vcr["credit_paid"]["mean"] - 1.44) < 1e-9,
       "credit KILL is read after the payout: $1.60 x 0.9 = $1.44 < $1.50 -> KILL: %s" % vcr["decision"])
    # V1 / V5 gates and which V5 row the bar may use
    lr = [{"ev": "validation", "run": "abc-x", "V1": {"n": 1000, "ok": 985}, "V3": {"trades": 10, "matched": 10}}]
    ck(validations_from(lr, [], "abc-x")[1]["V1"] is False, "V1: 98.5% book matches is under the 99% line")
    lr[0]["V1"] = {"n": 1000, "ok": 995}
    ck(validations_from(lr, [], "abc-x")[1]["V1"] is True, "V1: 99.5% passes")
    ck(v5_gate(True, 1.0, 2.0, 2.8) and not v5_gate(True, 1.0, 2.0, 3.5) and not v5_gate(True, 0.6, 2.0, 2.0)
       and not v5_gate(True, 1.6, 2.0, 2.0) and not v5_gate(False, 1.0, 2.0, 2.0) and v5_gate(True, 0.7, 2.0, 2.0),
       "V5 gate: 0.67-1.5x contracts and the 60 s mark within 1c of live, on a complete run only")
    v5rows = [{"ev": "validation_v5", "code_sha": "abc", "scope": "subset", "complete": True, "pass": True},
              {"ev": "validation_v5", "code_sha": "old", "scope": "full", "complete": True, "pass": True}]
    pv, why = pick_v5(v5rows, "abc")
    ck(pv is None and "no complete full-scope" in why, "a one-hour (subset) V5 row or another code's row never "
       "counts: %r" % why)
    ck(validations_from(v5rows, [], "abc-x")[1]["V5"] is False, "-> V5 is not passed for the bar")
    v5rows.append({"ev": "validation_v5", "code_sha": "abc", "scope": "full", "complete": False, "pass": False})
    v5rows.append({"ev": "validation_v5", "code_sha": "abc", "scope": "full", "complete": True, "pass": True})
    ck(pick_v5(v5rows, "abc")[0] is v5rows[-1] and validations_from(v5rows, [], "abc-x")[1]["V5"] is True,
       "the full, complete V5 run of this code is the one used")
    od = [{"land": hs + 60000}, {"land": hs + 3600 * 1000 + 60000}]
    hv, unf, scope = v5_hours(od, now_ms=hs + 2 * 3600 * 1000 + 10 * 60 * 1000)
    ck(hv == [H] and unf == [next_hour(H)] and scope == "full", "V5 leaves out an hour that ended < 15 min ago "
       "(the collector is still writing it): %r %r" % (hv, unf))
    ck(v5_hours(od, max_hours=1, now_ms=hs + 9 * 3600 * 1000)[2] == "subset", "a --max-hours run is a subset")
    # --batch never processes an hour that is still being recorded
    ns2 = argparse.Namespace(root=root, paper_dir=os.path.join(tmp, "paper2"), log=os.path.join(tmp, "plog2.jsonl"),
                             stop=os.path.join(tmp, "nostop"), from_hour=None, to_hour=None, series=[])
    process(ns2, follow=False, say=lambda *a: None, now_fn=lambda: hs / 1000.0 + 3600 + 600)
    lg2 = read_log(ns2.log)
    ck(not list(iter_paper_rows(ns2.paper_dir)) and [r for r in lg2 if r["ev"] == "end"][0]["unfinished_hours_skipped"]
       == 1, "--batch 10 min after the hour end skips the hour (it waits 15 min, like --follow)")
    ck(fx_day(int(dt.datetime(2026, 10, 18, 21, 15, tzinfo=UTC).timestamp() * 1000)) == "2026-10-19",
       "trading day: Sunday 17:15 ET belongs to Monday")
    ck(fx_day(int(dt.datetime(2026, 10, 19, 21, 0, tzinfo=UTC).timestamp() * 1000)) == "2026-10-19",
       "trading day: Monday 17:00 ET close is Monday's last window")
    ck(et_day(int(dt.datetime(2026, 10, 19, 3, 0, tzinfo=UTC).timestamp() * 1000)) == "2026-10-18",
       "ET day: 03:00Z is the previous ET date (EDT)")

    # ---------------------------------------------------------------- (g) no tape loader, no order verb
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for bad in ("PO" + "ST", "DEL" + "ETE", "/port" + "folio", "am" + "end", "bat" + "ched", "load_" + "quotes",
                "import " + "replay", "from replay" + " import", "url" + "open", "ka" + "uth",
                "gzsalvage" + ".iter_lines", "import " + "gzsalvage"):
        ck(bad not in src, "forbidden token in source: %s" % bad)


def main():
    ap = argparse.ArgumentParser(description="FX 15M reward paper quoter (no orders)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    mx = ap.add_mutually_exclusive_group()
    mx.add_argument("--follow", action="store_true", help="process each finished hour as it appears")
    mx.add_argument("--batch", action="store_true", help="process every available hour once")
    mx.add_argument("--report", action="store_true")
    mx.add_argument("--v5", action="store_true", help="engine calibration on the ladder's live fills")
    ap.add_argument("--root", default=FXBOOK)
    ap.add_argument("--paper-dir", default=PAPER_DIR)
    ap.add_argument("--log", default=SUMMARY_LOG)
    ap.add_argument("--stop", default=STOP_PATH)
    ap.add_argument("--lock", default=LOCK_PATH)
    ap.add_argument("--from", dest="from_hour", default=None)
    ap.add_argument("--to", dest="to_hour", default=None)
    ap.add_argument("--series", nargs="*", default=[])
    ap.add_argument("--data", default=KALSHI_DATA)
    ap.add_argument("--orders", default=LADDER_ORDERS)
    ap.add_argument("--max-hours", type=int, default=0)
    ap.add_argument("--max-seconds", type=float, default=0)
    args = ap.parse_args()
    if "--live" in sys.argv:
        raise SystemExit("REFUSING: there is no live mode in the paper quoter")
    if args.selftest:
        return 0 if selftest(args.verbose) else 1
    if os.environ.get("KALS_SELFTESTED") != "1":
        selftest()
    if args.report:
        report(args)
        return 0
    lock = InstanceLock(args.lock)
    if not lock.acquire():
        raise SystemExit("another fxreward_paper holds %s" % args.lock)
    try:
        if args.v5:
            return run_v5(args)
        return process(args, follow=args.follow)
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
