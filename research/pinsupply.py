"""pinsupply.py -- is the opportunity actually going away, and what moves it?

WHY THIS EXISTS. The operator, 2026-09-18: *"Are you 100% certain opportunities
have halved. Is bargains 100% a measure of that, and even if not is that
everything we're looking for?... This needs to be watched like a hawk and is
terrifying."*

The honest answer to the first question was NO, and this file is the correction.

**THE BASELINE ERROR.** The claim "the pool halved on 2026-09-13" was made by
comparing 2026-09-13..17 against 2026-09-09..12. Those four days were the
highest four in the entire tape. Measured against the fourteen days BEFORE
them, the current level is HIGHER, not halved. Picking a peak as the baseline
is the same mistake as quoting a loss rate off the tape: the number is real and
the comparison is not. `baseline()` below refuses to compare against a window
without also reporting the full-sample mean, so this cannot be done quietly
again.

**WHAT A 'BARGAIN' ACTUALLY MEASURES, AND WHAT IT DOES NOT.** `pinpickoff`
counts a taker BUYING the winning side at 90-98c within 60s of a close. So:

- It counts EXECUTED trades, not resting offers. An offer nobody took is an
  opportunity we could have had and it is invisible here. Bargains therefore
  UNDERSTATE supply, and they fall when competitors go quiet even if the
  offers are still sitting there.
- It is bounded at 90-98c. If prices drift up -- more markets pinned at 99c --
  bargains fall with no change in real opportunity.
- It needs a settlement result per ticker. Missing settlements silently drop
  whole days. That has already happened once: `load_settlements` read one
  stale file and the report stopped dead at 09-12 while looking healthy.
- It is a count of trades, not of money. `contracts` is the better size proxy.

So bargains is ONE measure, and a lagging, bounded, execution-only one. This
file pairs it with the realised volatility of the underlying index, because
the working hypothesis is that opportunity BREATHES WITH VOLATILITY rather
than decaying: a quarter hour only offers a 95c favourite if the coin moved
far enough for one side to be clearly ahead, and a flat tape offers nothing to
anybody.

If that hypothesis holds, a quiet week is weather, not death, and the thing to
watch is the RESIDUAL -- bargains lower than the day's volatility predicts --
because that is what competition actually looks like.
"""
import argparse
import collections
import glob
import gzip
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DAILY = os.path.join(RESULTS, "pinsupply_daily.json")
DATA = r"C:\kals\kalshi_data"

# Hours sampled per day for the volatility estimate. A day holds 24 hour-files
# of ~70k lines each; parsing all of them for every day costs half an hour and
# buys nothing, because a daily volatility number is an average over thousands
# of seconds either way. These four are spread across the clock so a day is
# not judged on one quiet stretch.
VOL_HOURS = (2, 8, 14, 20)

# THE BITCOIN INDEX IS CALLED `BRTI`, NOT `BTCUSD_RTI`. Assuming the obvious
# name produced a clean run over ninety hours that measured exactly nothing
# and wrote a volatility file with zero days in it -- no error, no warning.
# `measured()` below reports which indices were actually found, so an absent
# feed can never again look like a calm market.
VOL_INDICES = ("BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "DOGEUSD_RTI")
VOL_INDEX = VOL_INDICES[0]

# The nine crypto series that have been in the tape the whole time. The five
# commodity series arrived 2026-09-14 and must not be folded into a trend.
CRYPTO_SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
                 "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M")


def et_day(epoch):
    """Eastern calendar day. Presentation only -- everything stored is UTC."""
    return time.strftime("%Y-%m-%d", time.localtime(epoch))


# ---------------------------------------------------------------- bargains

def rebuild_daily(cache=None, out=None):
    """Read pinpickoff's big cache ONCE and write a small per-day file.

    The cache is 115 MB of JSON and loading it costs about a gigabyte. Nothing
    that runs often should touch it -- the desktop app certainly must not --
    so this collapses it to a few kilobytes that anything can read.
    """
    import pinpickoff
    cache = cache or pinpickoff.CACHE
    out = out or DAILY
    with open(cache, encoding="utf-8") as fh:
        blob = json.load(fh)
    rows = blob.get("rows") or []
    # PER SERIES, PER DAY. Without this, a day when Kalshi listed four more
    # coins is indistinguishable from a day when the same coins got busier,
    # and the 2026-09-09..12 spike cannot be explained at all. Kept here
    # because re-reading the 115 MB cache to ask is not something the desktop
    # app can do.
    per_series = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        tk = r.get("ticker") or ""
        s = tk.split("-", 1)[0]
        per_series[et_day(r["close"])][s] += 1
    by = pinpickoff.summarise(rows)
    days = {}
    for d, v in by.items():
        tau = sorted(v["tau"])
        days[d] = {
            "closes": len(v["closes"]),
            "bargains": v["n"],
            "ours": v["ours"],
            "contracts": v["contracts"],
            "ours_contracts": v["ours_contracts"],
            "per_close": (v["n"] / len(v["closes"])) if v["closes"] else 0.0,
            "median_tau": tau[len(tau) // 2] if tau else None,
            "mean_price": (sum(v["paid"]) / len(v["paid"])) if v["paid"] else None,
            "series": dict(per_series.get(d) or {}),
        }
    # CRYPTO ONLY, AS WELL AS THE TOTAL. The commodity series entered the tape
    # on 2026-09-14 and immediately added 10-15k bargains a day. Comparing a
    # 14-series day against a 9-series day and calling the difference a trend
    # is the same error as comparing against a peak -- the denominator changed
    # under the measurement. Every trend the app shows uses this number.
    for d, row in days.items():
        ser = row["series"]
        row["crypto"] = sum(v for k, v in ser.items() if k in CRYPTO_SERIES)
        row["per_close_crypto"] = (row["crypto"] / row["closes"]) if row["closes"] else 0.0
        row["n_series"] = len(ser)
    payload = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "source": os.path.basename(cache), "days": days}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
    return payload


def load_daily(path=None):
    try:
        with open(path or DAILY, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------- volatility

def _raw_lines(path):
    """Text lines from one hour file, surviving a torn one.

    THE COLLECTOR IS KILLED MID-WRITE ROUTINELY -- the watchdog restarts it,
    the machine sleeps -- so some hours end in a half-written gzip member and
    raise `zlib.error: invalid block type` partway through. The first version
    of this let that propagate and one torn hour out of ninety-six killed the
    whole volatility run after it had already done the work. A torn hour is
    read as far as it goes and then dropped.

    THE READABLE PREFIX IS KEPT AND THE TAIL IS DROPPED -- deliberately NOT
    re-read through the salvager afterwards. Salvaging after a partial read
    would replay the lines already yielded, and duplicated consecutive
    timestamps become zero returns, which would quietly DEFLATE the very
    volatility number this is here to measure. Half an hour of clean seconds
    is a fine estimate of a day; the same half counted twice is not.
    """
    try:
        fh = gzip.open(path, "rt", encoding="utf-8", errors="replace")
    except OSError:
        return
    try:
        with fh:
            for line in fh:
                yield line
    except Exception:                                              # noqa: BLE001
        return


def _index_values(path, index_id=VOL_INDEX):
    """(ts_ms, value) for one index out of one hour file, streamed."""
    for iid, ts, v in _many_values(path, (index_id,)):
        yield ts, v


def _many_values(path, index_ids):
    """(index_id, ts_ms, value) for several indices in ONE pass of the file.

    One pass, not one per coin: an hour file holds every index interleaved and
    re-reading it five times costs five times as much for the same bytes.
    """
    ids = tuple(index_ids)
    for line in _raw_lines(path):
        # cheap reject before parsing: ~20 indices share the file and we want
        # a handful, so most lines never reach json.loads
        if not any(('"' + i + '"') in line for i in ids):
            continue
        try:
            m = json.loads(line).get("msg") or {}
        except ValueError:
            continue
        iid = m.get("index_id")
        if iid not in ids:
            continue
        try:
            d = json.loads(m.get("data") or "{}")
            yield iid, int(d["time"]), float(d["value"])
        except (KeyError, TypeError, ValueError):
            continue


def hour_vol(path, index_id=VOL_INDEX):
    """Standard deviation of 1-second log returns in one hour file.

    Returns (sd, n). A value of None means the hour had too little to say --
    NOT zero. A volatility of zero is a real and very different claim.
    """
    got = hour_vols(path, (index_id,))
    return got.get(index_id, (None, 0))


def hour_vols(path, index_ids=VOL_INDICES):
    """{index_id: (sd, n)} for one hour file, one pass.

    An index with too few prints is (None, n) and NEVER 0.0 -- an absent feed
    and a calm market are opposite findings and must not share a number.
    """
    prev = {}
    acc = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for iid, ts, v in _many_values(path, index_ids):
        if v <= 0:
            continue
        p = prev.get(iid)
        if p is not None and 0 < ts - p[0] <= 2000:
            r = math.log(v / p[1])
            a = acc[iid]
            a[0] += 1
            a[1] += r
            a[2] += r * r
        prev[iid] = (ts, v)
    out = {}
    for iid in index_ids:
        n, s, s2 = acc.get(iid, [0, 0.0, 0.0])
        if n < 60:
            out[iid] = (None, n)
            continue
        var = (s2 - s * s / n) / (n - 1)
        out[iid] = ((math.sqrt(var) if var > 0 else 0.0), n)
    return out


def daily_vol(data=None, hours=VOL_HOURS, index_ids=VOL_INDICES,
              on_progress=None, found=None):
    """{day: mean sd of 1-second returns across coins} from sampled hours.

    Averaged over several coins because the opportunity pool spans twelve
    series and one coin's quiet day is not the market's. `found`, if given, is
    filled with {index_id: hours it was actually measured in} -- the guard
    against a renamed feed reading as a calm market.
    """
    data = data or DATA
    pat = os.path.join(data, "cfbenchmarks_value", "*.jsonl.gz")
    want = {"T%02d" % h for h in hours}
    files = [f for f in sorted(glob.glob(pat))
             if os.path.basename(f)[8:11] in want]
    acc = collections.defaultdict(list)
    for i, f in enumerate(files):
        got = hour_vols(f, index_ids)
        sds = [sd for sd, _n in got.values() if sd is not None]
        if found is not None:
            for iid, (sd, _n) in got.items():
                if sd is not None:
                    found[iid] = found.get(iid, 0) + 1
        if not sds:
            continue
        b = os.path.basename(f)
        day = "%s-%s-%s" % (b[0:4], b[4:6], b[6:8])
        acc[day].append(sum(sds) / len(sds))
        if on_progress and not i % 10:
            on_progress(i, len(files))
    return {d: sum(v) / len(v) for d, v in acc.items() if v}


# ----------------------------------------------------------- the question

def baseline(days, recent=5, window=None):
    """Where the last `recent` days sit against EVERY earlier day, not a peak.

    Returns the recent mean, the mean of everything before it, the mean of the
    `window` days immediately before it, and the full-sample mean -- all four,
    always. `window` alone is what produced "the pool halved": the four days
    before 09-13 were the four highest in the tape.
    """
    keys = sorted(days)
    if len(keys) < recent + 2:
        return None
    rec = keys[-recent:]
    earlier = keys[:-recent]

    def mean(ks):
        vals = [days[k] for k in ks if days.get(k) is not None]
        return (sum(vals) / len(vals)) if vals else None

    prev = earlier[-window:] if window else earlier
    def median(ks):
        vals = sorted(days[k] for k in ks if days.get(k) is not None)
        if not vals:
            return None
        m = len(vals) // 2
        return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2.0

    # THE MEAN OF EVERY EARLIER DAY IS ITSELF DRAGGED UP BY THE SPIKE -- four
    # days at triple the usual level lift an 19-day mean by a fifth. The
    # MEDIAN cannot be moved by them, so it is the honest "what a normal day
    # looks like" and it is reported next to the mean, never instead of it.
    return {"recent_days": rec, "recent": mean(rec),
            "before_all": mean(earlier), "before_window": mean(prev),
            "before_median": median(earlier), "recent_median": median(rec),
            "pct_vs_before_median": _pct(mean(rec), median(earlier)),
            "window_days": prev, "all": mean(keys),
            "pct_vs_before_all": _pct(mean(rec), mean(earlier)),
            "pct_vs_window": _pct(mean(rec), mean(prev)),
            "peak_day": max(earlier, key=lambda k: days[k]) if earlier else None,
            "peak": max((days[k] for k in earlier), default=None)}


def _pct(a, b):
    if a is None or b is None or abs(b) < 1e-12:
        return None
    return 100.0 * (a - b) / b


def pearson(xs, ys):
    """r over paired days, or None. Two points is not a relationship."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 4:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fit(xs, ys):
    """Least-squares slope/intercept of y on x, for the residual."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 4:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    if sxx <= 0:
        return None
    b = sum((p[0] - mx) * (p[1] - my) for p in pairs) / sxx
    return b, my - b * mx


def residuals(days_vol, days_bargains):
    """{day: actual - predicted-from-volatility}.

    THIS IS THE NUMBER TO WATCH, not the raw count. A quiet day with few
    bargains is weather. A day with ordinary volatility and few bargains is
    somebody else getting there first, and that is the one that means the edge
    is being competed away.
    """
    keys = sorted(set(days_vol) & set(days_bargains))
    xs = [days_vol[k] for k in keys]
    ys = [days_bargains[k] for k in keys]
    f = fit(xs, ys)
    if not f:
        return {}, None
    b, a = f
    return {k: ys[i] - (a + b * xs[i]) for i, k in enumerate(keys)}, f


def assess(daily=None, vol=None, recent=5):
    """Everything the Health tab shows, as plain data."""
    daily = daily or load_daily()
    if not daily or not daily.get("days"):
        return None
    days = daily["days"]
    # CRYPTO ONLY. `per_close` counts whatever series happened to be listed
    # that day, and that changed on 09-14; `per_close_crypto` is the like-for-
    # like series. Older files lack it, so fall back rather than crash.
    per_close = {d: v.get("per_close_crypto", v["per_close"]) for d, v in days.items()}
    contracts = {d: v["contracts"] for d, v in days.items()}
    out = {"built": daily.get("built"),
           "n_days": len(days),
           "per_close": per_close,
           "per_close_all": {d: v["per_close"] for d, v in days.items()},
           "contracts": contracts,
           "n_series": {d: v.get("n_series") for d, v in days.items()},
           "baseline_per_close": baseline(per_close, recent=recent, window=4),
           "baseline_contracts": baseline(contracts, recent=recent, window=4)}
    if vol:
        keys = sorted(set(vol) & set(per_close))
        out["vol"] = {k: vol[k] for k in keys}
        out["r_vol_bargains"] = pearson([vol[k] for k in keys],
                                        [per_close[k] for k in keys])
        res, f = residuals(vol, per_close)
        out["residual"] = res
        out["fit"] = f
        if res:
            rk = sorted(res)[-recent:]
            out["residual_recent"] = sum(res[k] for k in rk) / len(rk)
    return out


def report(a, out=sys.stdout):
    def p(*x):
        print(*x, file=out)
    if not a:
        p("loaded nothing -- no supply history on file yet")
        return
    p("IS THE OPPORTUNITY GOING AWAY?")
    p("  %d days on file, built %s" % (a["n_days"], a.get("built")))
    for label, key in (("bargains per close (crypto only)", "baseline_per_close"),
                       ("contracts traded (all series)", "baseline_contracts")):
        b = a.get(key)
        if not b:
            continue
        p("")
        p("  %s" % label.upper())
        p("    last %d days           %10.1f" % (len(b["recent_days"]), b["recent"]))
        p("    the 4 days before      %10.1f   %s" % (
            b["before_window"], _fmt_pct(b["pct_vs_window"])))
        p("    EVERY earlier day      %10.1f   %s   (mean)" % (
            b["before_all"], _fmt_pct(b["pct_vs_before_all"])))
        p("    a NORMAL earlier day   %10.1f   %s   (median)" % (
            b["before_median"], _fmt_pct(b["pct_vs_before_median"])))
        p("    highest earlier day    %10.1f   on %s" % (b["peak"], b["peak_day"]))
        p("    -- the SECOND line is the one that said 'halved'. It is measured")
        p("       against the four highest days on record. The mean below it is")
        p("       dragged up by those same four days; the median is not, so the")
        p("       median line is what a normal day actually looks like.")
    if a.get("r_vol_bargains") is not None:
        p("")
        p("  DOES IT TRACK VOLATILITY?")
        p("    correlation over %d shared days: r = %+.2f" % (len(a["vol"]),
                                                             a["r_vol_bargains"]))
        p("    r near +1 means a quiet week explains a thin week, and the pool")
        p("    comes back when the market moves. r near 0 means it does not, and")
        p("    the decline is structural.")
        r = a["r_vol_bargains"]
        if abs(r) < 0.5:
            p("    THIS ONE IS WEAK: r = %+.2f explains only %.0f%% of the "
              "day-to-day" % (r, 100 * r * r))
            p("    swing, so the residual below is mostly noise and must not be")
            p("    read as a competition reading on its own.")
        if a.get("residual_recent") is not None:
            p("    recent days sit %+.0f bargains/close against what their own" %
              a["residual_recent"])
            p("    volatility predicts. NEGATIVE is the competition signal.")


def _fmt_pct(v):
    return "n/a" if v is None else ("%+.0f%%" % v)


def lines(a=None, vol=None):
    """Plain-language supply lines. ONE source for the app and the phone.

    The desktop tab and the Telegram reply were going to be written twice and
    would have drifted within a week, which is how a number ends up meaning
    two different things depending on where you read it.
    """
    if a is None:
        a = assess(vol=vol)
    if not a:
        return ["Opportunity: no history on file yet."]
    b = a.get("baseline_per_close") or {}
    c = a.get("baseline_contracts") or {}
    out = []
    if b.get("recent") is not None and b.get("before_median") is not None:
        out.append("Cheap offers near the close, last %d days: %.0f a quarter-hour."
                   % (len(b["recent_days"]), b["recent"]))
        out.append("A normal day before this ran %.0f, so we are %s."
                   % (b["before_median"], _updown(b["pct_vs_before_median"])))
        out.append("Against 09-09..09-12, the four busiest days ever recorded, "
                   "we are %s -- those four days are not a normal week and "
                   "must not be used as the yardstick."
                   % _updown(b["pct_vs_window"]))
    if c.get("recent") is not None and c.get("before_median") is not None:
        out.append("Contracts changing hands near the close: %s against a "
                   "normal day." % _updown(c["pct_vs_before_median"]))
    r = a.get("r_vol_bargains")
    if r is not None:
        out.append("It does NOT track how much the coins move (r = %+.2f), so a "
                   "quiet week does not explain a thin one." % r
                   if abs(r) < 0.5 else
                   "It tracks how much the coins move (r = %+.2f)." % r)
    if not out:
        # NEVER RETURN NOTHING. A blank panel reads as "fine"; that is not the
        # same as "too few days to say", and only one of those is true.
        out.append("Opportunity: only %d days on file, too few to compare "
                   "anything against yet." % a.get("n_days", 0))
    return out


def _updown(p):
    if p is None:
        return "not comparable"
    if abs(p) < 3:
        return "level with it"
    return ("up %.0f%%" % p) if p > 0 else ("down %.0f%%" % -p)


# ------------------------------------------------------------------ tests

def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinsupply selftest: FAILED -- " + msg)

    # THE BASELINE ERROR, PLANTED. A flat series at 400 with a four-day spike
    # at 1200 stuck in the middle, then a return to 600. Judged against the
    # spike it looks like a collapse; judged against the record it is a rise.
    days = {}
    for i in range(14):
        days["2026-08-%02d" % (25 - 0 + i) if False else "2026-09-%02d" % (i + 1)] = 400.0
    for i, d in enumerate(("2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18")):
        days[d] = 1200.0
    for d in ("2026-09-19", "2026-09-20", "2026-09-21", "2026-09-22", "2026-09-23"):
        days[d] = 600.0
    b = baseline(days, recent=5, window=4)
    ck(abs(b["recent"] - 600.0) < 1e-9, "the recent mean is the recent mean")
    ck(abs(b["pct_vs_window"] + 50.0) < 1e-9,
       "against the four-day SPIKE the last five days look 50% down -- this is "
       "the number that was reported to the operator as 'the pool halved'")
    ck(abs(b["before_median"] - 400.0) < 1e-9 and b["before_all"] > 400.0,
       "the MEDIAN earlier day is untouched by the four spike days while the "
       "mean is dragged above the baseline by them -- so a comparison against "
       "the mean understates how normal the recent days are")
    ck(b["pct_vs_before_median"] > 0,
       "...and against a normal day the recent days are UP")
    ck(b["pct_vs_before_all"] > 0,
       "against EVERY earlier day the very same days are UP -- so 'halved' was "
       "a choice of baseline, not a finding. baseline() returns both on purpose")
    ck(abs(b["before_all"] - (14 * 400 + 4 * 1200) / 18.0) < 1e-6,
       "...and the all-earlier mean is the plain mean of everything before")
    ck(b["peak"] == 1200.0 and b["peak_day"] in ("2026-09-15", "2026-09-16",
                                                 "2026-09-17", "2026-09-18"),
       "the peak is named, so a reader can see what the window was anchored to")
    ck(baseline({"a": 1.0}, recent=5) is None,
       "NULL: too few days is None, not a fabricated comparison")

    # THE CHANGED-DENOMINATOR TRAP, PLANTED. A day that added five new series
    # must not read as a day that got busier.
    fake = {"days": {
        "2026-09-01": {"closes": 10, "per_close": 100.0, "contracts": 1000.0,
                       "crypto": 1000, "per_close_crypto": 100.0, "n_series": 9,
                       "series": {"KXBTC15M": 1000}},
        "2026-09-02": {"closes": 10, "per_close": 200.0, "contracts": 2000.0,
                       "crypto": 1000, "per_close_crypto": 100.0, "n_series": 14,
                       "series": {"KXBTC15M": 1000, "KXWTI15M": 1000}},
    }}
    aa = assess(daily=fake, recent=1)
    ck(aa["per_close"]["2026-09-02"] == 100.0
       and aa["per_close_all"]["2026-09-02"] == 200.0,
       "a day that LISTED more series is flat on the like-for-like crypto "
       "measure and double on the raw one -- the commodity series joined the "
       "tape on 09-14 and would otherwise have looked like a doubling")
    ln = lines(a=aa)
    ck(ln and all(isinstance(s, str) and s for s in ln),
       "the shared plain-language lines render from an assessment")
    ck("too few" in ln[0],
       "NULL: two days is too few to compare, and it SAYS so rather than "
       "returning an empty panel -- a blank panel reads as 'fine'")
    big = {"days": {("2026-09-%02d" % (i + 1)): {
        "closes": 10, "per_close": 400.0, "contracts": 4000.0,
        "crypto": 4000, "per_close_crypto": 400.0, "n_series": 9,
        "series": {"KXBTC15M": 4000}} for i in range(12)}}
    ln2 = lines(a=assess(daily=big, recent=3))
    ck(any("quarter-hour" in s for s in ln2) and len(ln2) >= 3,
       "a real history renders the comparison lines")
    ck(not any(w in " ".join(ln2).lower() for w in ("tau", "sigma", "rho",
                                                    "clopper", "bootstrap")),
       "...with none of the jargon the operator has told us never to use")
    ck(_updown(0.4) == "level with it" and _updown(-30).startswith("down"),
       "a 0.4% move is 'level', not a trend dressed up as one")
    ck(assess(daily={"days": {}}) is None,
       "NULL: no days assesses to nothing, not to a flat zero trend")

    # CORRELATION: planted, and a planted NULL.
    vol = {"d%02d" % i: 0.001 * (i + 1) for i in range(12)}
    barg = {k: 100000.0 * v for k, v in vol.items()}
    ck(abs(pearson([vol[k] for k in sorted(vol)],
                   [barg[k] for k in sorted(barg)]) - 1.0) < 1e-9,
       "a perfectly proportional world gives r = +1.00")
    flat = {k: 500.0 for k in vol}
    ck(pearson([vol[k] for k in sorted(vol)],
               [flat[k] for k in sorted(flat)]) is None,
       "NULL: bargains that never move have no correlation with anything -- "
       "None, not 0.00, because zero reads as a measured absence of effect")
    ck(pearson([1.0, 2.0], [1.0, 2.0]) is None,
       "NULL: two points is not a relationship however well they line up")

    # RESIDUAL: the day that is thin for its own volatility.
    barg2 = dict(barg)
    barg2["d11"] = barg2["d11"] - 300.0
    res, f = residuals(vol, barg2)
    ck(res and res["d11"] < -100,
       "a day that under-delivers for its OWN volatility shows a negative "
       "residual -- that is the competition signal, and the raw count cannot "
       "distinguish it from a quiet day")
    ck(max(res, key=lambda k: abs(res[k])) == "d11",
       "...and it is the largest residual in the sample")

    # VOLATILITY out of a synthetic hour file.
    import tempfile
    td = tempfile.mkdtemp()
    # the real tape keeps each channel in its own directory, and daily_vol
    # globs that directory -- mirror it here or the test measures nothing
    os.makedirs(os.path.join(td, "cfbenchmarks_value"), exist_ok=True)
    hp = os.path.join(td, "cfbenchmarks_value", "20260910T14.jsonl.gz")
    with gzip.open(hp, "wt", encoding="utf-8") as fh:
        v = 100.0
        for i in range(600):
            v *= math.exp(0.0004 * (1 if i % 2 else -1))
            fh.write(json.dumps({"msg": {
                "index_id": VOL_INDEX,
                "data": json.dumps({"time": 1789000000000 + i * 1000,
                                    "value": "%.6f" % v})}}) + "\n")
            fh.write(json.dumps({"msg": {
                "index_id": "OTHERUSD_RTI",
                "data": json.dumps({"time": 1789000000000 + i * 1000,
                                    "value": "5.0"})}}) + "\n")
    sd, n = hour_vol(hp)
    ck(n == 599, "every consecutive second pairs into a return")
    ck(abs(sd - 0.0004) < 5e-5,
       "a planted 4-basis-point wobble is measured back as 4 basis points")
    empty = os.path.join(td, "cfbenchmarks_value", "20260910T15.jsonl.gz")
    with gzip.open(empty, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"msg": {"index_id": "OTHERUSD_RTI",
                                     "data": "{}"}}) + "\n")
    sd2, n2 = hour_vol(empty)
    ck(sd2 is None and n2 == 0,
       "NULL: an hour with none of our index is None, NOT zero -- a volatility "
       "of zero is a real claim and a very loud one")
    # A TORN HOUR MUST NOT KILL THE RUN. The collector is restarted by a
    # watchdog and some hours end mid-member; one of ninety-six killed the
    # first real volatility run after it had done the work.
    torn = os.path.join(td, "cfbenchmarks_value", "20260911T14.jsonl.gz")
    with open(hp, "rb") as src, open(torn, "wb") as dst:
        blob = src.read()
        dst.write(blob[:len(blob) // 2])
    sd3, n3 = hour_vol(torn)
    ck(n3 > 60 and sd3 is not None,
       "a half-written hour still yields its readable prefix instead of "
       "raising, so one torn file cannot throw away a whole run")
    ck(n3 < n, "...and it is honestly SHORTER than the whole hour")
    # THE RENAMED-FEED TRAP, PLANTED. Asking for an index that is not in the
    # file must report absence, never calm.
    miss = hour_vols(hp, ("NOSUCHUSD_RTI",))
    ck(miss["NOSUCHUSD_RTI"] == (None, 0),
       "an index that is not in the file is (None, 0) -- the real run asked "
       "for BTCUSD_RTI, which Kalshi calls BRTI, and 90 clean hours measured "
       "exactly nothing while raising no error at all")
    found = {}
    daily_vol(data=td, hours=(14,), index_ids=(VOL_INDEX, "NOSUCHUSD_RTI"),
              found=found)
    ck(found.get(VOL_INDEX) and not found.get("NOSUCHUSD_RTI"),
       "...and `found` names which feeds were really measured, so a missing "
       "one is visible in the run's own output")
    dv = daily_vol(data=td, hours=(14, 15), index_ids=(VOL_INDEX,))
    ck(sorted(dv) == ["2026-09-10", "2026-09-11"]
       and abs(dv["2026-09-10"] - sd) < 1e-12,
       "daily_vol averages the hours it could read and drops the ones it "
       "could not, rather than averaging a None in as zero -- the empty hour "
       "leaves 09-10 on its one good hour alone")
    print("pinsupply selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rebuild", action="store_true",
                    help="re-read pinpickoff's cache into the small daily file")
    ap.add_argument("--vol", action="store_true", help="also measure volatility")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--recent", type=int, default=5)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    if a.rebuild:
        print("reading pinpickoff cache (this is the expensive one)...", flush=True)
        d = rebuild_daily()
        print("  wrote %s: %d days" % (DAILY, len(d["days"])), flush=True)
    vol = None
    if a.vol:
        print("measuring index volatility...", flush=True)
        found = {}
        vol = daily_vol(data=a.data, found=found,
                        on_progress=lambda i, n: print("  %d/%d hours" % (i, n),
                                                       flush=True))
        for iid in VOL_INDICES:
            print("  %-14s measured in %d hours%s"
                  % (iid, found.get(iid, 0),
                     "   <-- NOT FOUND, check the index name"
                     if not found.get(iid) else ""), flush=True)
        if not vol:
            print("  loaded nothing -- no index values matched; NOT writing a "
                  "volatility file, because an empty one reads as a calm "
                  "market", flush=True)
        else:
            with open(os.path.join(RESULTS, "pinsupply_vol.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(vol, fh, indent=1, sort_keys=True)
    elif os.path.exists(os.path.join(RESULTS, "pinsupply_vol.json")):
        with open(os.path.join(RESULTS, "pinsupply_vol.json"), encoding="utf-8") as fh:
            vol = json.load(fh)
    report(assess(vol=vol, recent=a.recent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
