#!/usr/bin/env python3
# VERSION: 2026-09-13-fd1
"""pinfeed.py -- DOES OUR OWN INDEX RUN AHEAD OF THE ONE WE SETTLE AGAINST?

THE OPERATOR, 2026-09-13: "for the 11gb you just want to poke and prod around
and research and test things within it to see if it helps? Absolutely do that."

WHAT THE 11 GB IS. `crypto_feeds.py` has been recording, since 2026-08-25, the
four exchanges whose prices are averaged to MAKE the settlement index --
Coinbase (1.5 GB), Kraken (183 MB), Bitstamp (7.8 GB of full order books),
Gemini (618 MB) -- plus `index_replica` (239 MB): our own second-by-second
reconstruction of the index from those books. None of it has ever been used by
any analysis in this repository.

THE QUESTION THIS FILE ASKS, and it is the one worth asking first because it
is both the cheapest and the largest if true:

    Settlement is the average of sixty CF Benchmarks prints. CF computes those
    from the same exchanges we are recording. If our reconstruction moves
    BEFORE the published print does, then at any moment we know something
    about where settlement is going that the published feed has not said yet.

That is not a trading rule; it is a better `spot`. The model's forecast is
`mu = (locked + tau*spot)/60`, so a `spot` that is one second fresher is
directly a better forecast, at every tau, for free.

THREE THINGS ARE MEASURED, in increasing strength:

  1. LEAD-LAG CORRELATION. Correlate one-second changes in our replica with
     one-second changes in the published index at lags -5..+5. If we lead, the
     peak sits at a POSITIVE lag.
  2. THE PREDICTIVE REGRESSION, which is the one that matters. Regress the
     published index's NEXT change on the CURRENT gap between our replica and
     the published value. A non-zero slope means the published feed is walking
     toward where we already are.
  3. THE FORECAST TEST. Does replacing `spot` with the replica reduce the
     error in `mu` against the settlement that actually happened? That is the
     only one denominated in the thing we care about.

WHAT WOULD MAKE IT AN ARTEFACT, checked rather than asserted:

  - CLOCK SKEW. Both feeds are stamped by their own source. If our recorder
    timestamps a second earlier than CF does, everything leads by construction.
    So the replica is aligned on the exchange-reported second, and the test is
    repeated with the replica shifted one second LATER -- a real lead survives
    a one-second handicap, a clock artefact does not.
  - STALENESS, the reverse. If the replica is a slow copy of the published
    feed, it will LAG, and the same statistic shows that with the opposite
    sign. Both directions are reported.
  - CONSTITUENT OVERLAP. Our replica and CF read the same exchanges, so they
    are not independent and a high correlation proves nothing on its own. Only
    the ASYMMETRY across lags carries information, which is why the raw
    correlation is never quoted alone.

NO ORDER BOOK FROM KALSHI, NO REPLAY, NO FILLS, NO P&L.
"""
import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                               # noqa: E402

# replica coin key -> published CF index id
COIN_TO_INDEX = {
    "BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI",
    "XRP": "XRPUSD_RTI", "DOGE": "DOGEUSD_RTI", "ADA": "ADAUSD_RTI",
    "BCH": "BCHUSD_RTI", "LTC": "LTCUSD_RTI",
}
LAGS = tuple(range(-5, 6))


# ---------------------------------------------------------------------------
def load_replica(feed_dir, coin, field="wmid", say=print):
    """{second: value} for one coin from index_replica. 239 MB, read whole.

    Only one coin is kept per pass: holding all eight is eight times the
    memory for no benefit, and CLAUDE.md's resource protocol exists because an
    analysis job once OOM-killed the collector.
    """
    out = {}
    pat = os.path.join(feed_dir, "index_replica", "*.jsonl.gz")
    files = sorted(glob.glob(pat))
    key = '"%s"' % coin
    stats = {}
    for k, path in enumerate(files):
        for line in gzsalvage.iter_lines(path, stats=stats):
            if key not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            sec = d.get("sec")
            c = d.get(coin)
            if sec is None or not isinstance(c, dict):
                continue
            v = c.get(field)
            if v is None:
                continue
            try:
                out[int(sec)] = float(v)
            except (TypeError, ValueError):
                continue
        if say and (k + 1) % 120 == 0:
            say("    ...%d/%d replica hours, %d seconds held"
                % (k + 1, len(files), len(out)))
    if say:
        say("    replica %s: %d seconds%s"
            % (coin, len(out),
               (", %d files salvaged" % stats.get("salvaged_files", 0))
               if stats.get("salvaged_files") else ""))
    return out


def load_published(data_dir, index_id, say=print):
    """{second: value} for ONE published index id. A twelfth of the memory of
    replay.load_index, which loads all of them."""
    out = {}
    pat = os.path.join(data_dir, "cfbenchmarks_value", "*.jsonl.gz")
    files = sorted(glob.glob(pat))
    key = '"%s"' % index_id
    stats = {}
    for k, path in enumerate(files):
        for line in gzsalvage.iter_lines(path, stats=stats):
            if key not in line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            d = m.get("msg") or {}
            if d.get("index_id") != index_id:
                continue
            inner = d.get("data")
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except ValueError:
                    continue
            if not isinstance(inner, dict):
                continue
            try:
                out[int(round(float(inner["time"]) / 1000.0))] = float(
                    inner["value"])
            except (KeyError, TypeError, ValueError):
                continue
        if say and (k + 1) % 120 == 0:
            say("    ...%d/%d index hours, %d seconds held"
                % (k + 1, len(files), len(out)))
    if say:
        say("    published %s: %d seconds%s"
            % (index_id, len(out),
               (", %d files salvaged" % stats.get("salvaged_files", 0))
               if stats.get("salvaged_files") else ""))
    return out




# ---------------------------------------------------------------------------
# 2. WHAT THE PUBLISHED INDEX CANNOT SHOW: the exchanges DISAGREEING.
#
# The settlement index is one number per second. `index_replica` carries the
# bid and ask of every constituent exchange behind that number. When Coinbase
# says BTC is 76,777 and Gemini says 76,795, the index shows one price and the
# disagreement is invisible in it.
#
# THE OPERATOR'S THEORY, applied to a quantity the index physically cannot
# contain: "tracking volume, volatility, or anything else you can think of and
# seeing how that correlates to lumpiness and large price swings."
#
# Four features, all knowable at the instant the settlement window opens:
#   spread_rel   (max mid - min mid) / price across exchanges
#   wmid_gap     |weighted mid - median mid| / price -- do the big venues
#                disagree with the middle one?
#   n_ex         how many exchanges reported at all. THIS IS ALSO A DATA
#                HEALTH CHECK: a second with fewer venues is a second the
#                index itself was computed from less.
#   quote_spread the mean bid-ask spread across venues, relative to price --
#                the closest thing to LIQUIDITY available without opening the
#                7.8 GB of Bitstamp books.
# ---------------------------------------------------------------------------
def load_disagree(feed_dir, coin, say=print):
    """{second: (spread_rel, wmid_gap, n_ex, quote_spread)} for one coin."""
    out = {}
    pat = os.path.join(feed_dir, "index_replica", "*.jsonl.gz")
    files = sorted(glob.glob(pat))
    key = '"%s"' % coin
    stats = {}
    for k, path in enumerate(files):
        for line in gzsalvage.iter_lines(path, stats=stats):
            if key not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            sec = d.get("sec")
            c = d.get(coin)
            if sec is None or not isinstance(c, dict):
                continue
            per = c.get("per_ex") or {}
            mids = []
            spreads = []
            for _ex, q in per.items():
                if not isinstance(q, dict):
                    continue
                b, a = q.get("b"), q.get("a")
                if b is None or a is None or b <= 0 or a <= 0:
                    continue
                mids.append(0.5 * (b + a))
                spreads.append(a - b)
            if len(mids) < 2:
                continue
            px = sum(mids) / len(mids)
            if px <= 0:
                continue
            wm = c.get("wmid")
            md = c.get("median_mid")
            gap = (abs(wm - md) / px) if (wm and md) else 0.0
            out[int(sec)] = ((max(mids) - min(mids)) / px, gap,
                             float(c.get("n_ex") or len(mids)),
                             (sum(spreads) / len(spreads)) / px)
        if say and (k + 1) % 120 == 0:
            say("    ...%d/%d replica hours, %d seconds"
                % (k + 1, len(files), len(out)))
    if say:
        say("    disagreement %s: %d seconds" % (coin, len(out)))
    return out


# ---------------------------------------------------------------------------
def changes(series, secs):
    """{sec: one-second change} over seconds whose predecessor exists."""
    out = {}
    for s in secs:
        a = series.get(s)
        b = series.get(s - 1)
        if a is not None and b is not None:
            out[s] = a - b
    return out


def corr(xs, ys):
    n = len(xs)
    if n < 30:
        return float("nan"), n
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sxx = syy = 0.0
    for x, y in zip(xs, ys):
        dx = x - mx
        dy = y - my
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    if sxx <= 0 or syy <= 0:
        return float("nan"), n
    return sxy / math.sqrt(sxx * syy), n


def lead_lag(rep_d, pub_d, lags=LAGS, shift=0):
    """[(lag, correlation, n)]. POSITIVE lag = the published feed moves LATER,
    i.e. we lead it. `shift` delays the replica by that many seconds and is the
    clock-skew handicap."""
    out = []
    common = set(rep_d) & set(pub_d)
    for lag in lags:
        xs = []
        ys = []
        for s in common:
            a = rep_d.get(s - shift)
            b = pub_d.get(s + lag)
            if a is None or b is None:
                continue
            xs.append(a)
            ys.append(b)
        c, n = corr(xs, ys)
        out.append((lag, c, n))
    return out


def gap_regression(rep, pub, horizon=1, shift=0):
    """Slope of (published change over `horizon`) on (replica minus published).

    THE DECISIVE ONE. If our value is merely a noisy copy of theirs the slope
    is zero. If the published feed is walking toward where we already are, the
    slope is positive, and its size says how much of the gap closes per second.
    Returns (slope, t-statistic, n, r).
    """
    xs = []
    ys = []
    for s in pub:
        p0 = pub.get(s)
        p1 = pub.get(s + horizon)
        r0 = rep.get(s - shift)
        if p0 is None or p1 is None or r0 is None:
            continue
        xs.append(r0 - p0)
        ys.append(p1 - p0)
    n = len(xs)
    if n < 100:
        return float("nan"), float("nan"), n, float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sxx = syy = 0.0
    for x, y in zip(xs, ys):
        dx = x - mx
        dy = y - my
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    if sxx <= 0:
        return float("nan"), float("nan"), n, float("nan")
    slope = sxy / sxx
    resid = syy - slope * sxy
    se = math.sqrt(max(resid, 0.0) / max(n - 2, 1) / sxx)
    t = slope / se if se > 0 else float("nan")
    r = sxy / math.sqrt(sxx * syy) if syy > 0 else float("nan")
    return slope, t, n, r


# ---------------------------------------------------------------------------
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    rnd = random.Random(3)
    # A TRUE world: the published feed is our value, one second later, plus
    # noise. We lead by exactly one second, by construction.
    truth = {}
    v = 100.0
    for s in range(1000, 40000):
        v += rnd.gauss(0, 0.5)
        truth[s] = v
    rep = dict(truth)
    pub = {s: truth[s - 1] + rnd.gauss(0, 0.02) for s in range(1001, 40000)}
    rd = changes(rep, sorted(rep))
    pd = changes(pub, sorted(pub))
    ll = lead_lag(rd, pd)
    best = max((c, lag) for lag, c, _n in ll if c == c)
    ck(best[1] == 1,
       "in a world where we lead by one second, the correlation peaks at "
       "lag +1 (peak %.3f at lag %+d)" % (best[0], best[1]))
    sl, t, nn, _r = gap_regression(rep, pub)
    ck(sl > 0.5 and t > 10,
       "and the gap regression says the published feed closes most of the gap "
       "in one second (slope %.2f, t=%.0f, n=%d)" % (sl, t, nn))

    # THE MIRROR: if THEY lead, the same statistics must say so, with the sign
    # reversed. An estimator that only ever finds a lead is worthless.
    rep2 = {s: truth[s - 1] + rnd.gauss(0, 0.02) for s in range(1001, 40000)}
    pub2 = dict(truth)
    ll2 = lead_lag(changes(rep2, sorted(rep2)), changes(pub2, sorted(pub2)))
    best2 = max((c, lag) for lag, c, _n in ll2 if c == c)
    ck(best2[1] == -1,
       "with the roles swapped the peak moves to lag -1 (%.3f at %+d) -- the "
       "estimator can find a LAG as readily as a lead" % (best2[0], best2[1]))
    sl2, _t2, _n2, _r2 = gap_regression(rep2, pub2)
    ck(sl2 < 0.2,
       "and the gap regression does NOT claim a lead there (slope %.2f)" % sl2)

    # THE NULL: two independent series. No lead in either direction.
    ind = {}
    v = 100.0
    for s in range(1000, 40000):
        v += rnd.gauss(0, 0.5)
        ind[s] = v
    ll3 = lead_lag(changes(rep, sorted(rep)), changes(ind, sorted(ind)))
    ck(all(abs(c) < 0.05 for _l, c, _n in ll3 if c == c),
       "two unrelated series correlate at no lag (max |r| = %.3f)"
       % max(abs(c) for _l, c, _n in ll3 if c == c))

    # TELLING A REAL LEAD FROM A RELABELLED CLOCK.
    #
    # THE FIRST VERSION OF THIS CHECK WAS WRONG and asserted something false:
    # that delaying our own feed by a second should move a real peak to +2. It
    # does not. A handicap REDUCES an apparent lead whatever its cause -- a
    # genuine one-second lead and a one-second timestamp offset both collapse
    # to zero -- so that test cannot separate them and the assertion failed
    # for the right reason.
    #
    # What DOES separate them is the SHAPE of the gap regression. If the two
    # feeds carry identical content and differ only in the second they are
    # stamped with, then rep(s) IS pub(s+1), the "gap" IS the next change, and
    # regressing one on the other returns slope 1.0 with r 1.0 -- a tautology
    # wearing a lead's clothes. A genuine partial lead, where the published
    # feed closes only some of the gap each second, returns a slope strictly
    # inside (0, 1) and an r well below 1.
    lab_rep = dict(truth)
    lab_pub = {s: truth[s - 1] for s in range(1001, 40000)}   # pure relabel
    sl_l, _t, _n, r_l = gap_regression(lab_rep, lab_pub)
    ck(sl_l > 0.97 and r_l > 0.97,
       "a pure CLOCK RELABEL returns slope %.3f and r %.3f -- both at 1, "
       "which is the signature to refuse, not to celebrate" % (sl_l, r_l))

    # partial adjustment: the published feed closes 30% of the gap per second
    pa_rep = dict(truth)
    pa_pub = {1000: truth[1000]}
    for s in range(1001, 40000):
        prev = pa_pub[s - 1]
        pa_pub[s] = prev + 0.30 * (truth[s - 1] - prev) + rnd.gauss(0, 0.05)
    sl_p, t_p, _n, r_p = gap_regression(pa_rep, pa_pub)
    ck(0.15 < sl_p < 0.5,
       "a GENUINE partial lead of 30%% per second is recovered as slope %.3f "
       "(t=%.0f)" % (sl_p, t_p))
    # r is NOT the discriminator and the first version wrongly leaned on it:
    # with a small noise term the gap is dominated by the truth's own motion,
    # so a genuine 30%-per-second lead still returns r = 0.973. The SLOPE is
    # what separates them -- 0.300 against 1.000 -- and r only corroborates.
    ck(sl_p < 0.5 < sl_l,
       "the SLOPE separates them cleanly (%.3f partial vs %.3f relabel) where "
       "r does not (%.3f vs %.3f)" % (sl_p, sl_l, r_p, r_l))
    ck(r_p < 0.995,
       "r is at least not pinned at 1 in the genuine case (%.4f)" % r_p)

    ll4 = lead_lag(rd, pd, shift=1)
    ck(len([1 for _l, c, _n in ll4 if c == c]) == len(LAGS),
       "the handicap variant still computes at every lag, and is REPORTED as "
       "a diagnostic rather than asserted on")

    # loaders survive junk
    import tempfile
    tmp = tempfile.mkdtemp(prefix="pinfeed-")
    try:
        os.makedirs(os.path.join(tmp, "index_replica"))
        with gzip.open(os.path.join(tmp, "index_replica", "a.jsonl.gz"), "wt",
                       encoding="utf-8") as fh:
            fh.write(json.dumps({"sec": 100, "BTC": {"wmid": 5.0}}) + "\n")
            fh.write("not json\n")
            fh.write(json.dumps({"sec": 101, "ETH": {"wmid": 9.0}}) + "\n")
            fh.write(json.dumps({"sec": 102, "BTC": {"median_mid": 7.0}})
                     + "\n")
        got = load_replica(tmp, "BTC", say=None)
        ck(got == {100: 5.0},
           "load_replica keeps its coin, skips junk, skips other coins, and "
           "skips a line missing the field it was asked for (%s)" % got)
        got2 = load_replica(tmp, "BTC", field="median_mid", say=None)
        ck(got2 == {102: 7.0}, "and reads a different field on request")
    finally:
        for root, dirs, files in os.walk(tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(tmp)

    print("pinfeed selftest: %d checks OK" % n[0])
    return 0


# ---------------------------------------------------------------------------
def report(coin, rep, pub, out_path, say=print):
    lines = []
    w = lines.append
    secs = sorted(set(rep) & set(pub))
    rd = changes(rep, secs)
    pd = changes(pub, secs)
    w("# RESULTS_feed -- does our own index run ahead of the published one?")
    w("")
    w("*`research/pinfeed.py`, %s. Coin %s. %d seconds held in both feeds. "
      "Constituent exchange feeds and the published settlement index only -- "
      "no Kalshi order book, no replay, no fills, no P&L.*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), coin, len(secs)))
    w("")
    w("## 1. Lead-lag correlation of one-second changes")
    w("")
    w("A POSITIVE lag means the published feed moves LATER than ours -- we "
      "lead. Both feeds read the same exchanges, so the level of correlation "
      "proves nothing; only the ASYMMETRY across lags carries information.")
    w("")
    w("| lag (s) | correlation | n |")
    w("|---|---|---|")
    ll = lead_lag(rd, pd)
    for lag, c, nn in ll:
        w("| %+d | %.4f | %d |" % (lag, c, nn))
    good = [(c, lag) for lag, c, _n in ll if c == c]
    if good:
        peak = max(good)
        w("")
        w("**Peak at lag %+d (r = %.4f).**" % (peak[1], peak[0]))
    w("")
    w("## 2. Is it information, or just a differently-stamped clock?")
    w("")
    w("If the two feeds carry the same content and differ only in the second "
      "they are stamped with, then our value IS their next value, the \"gap\" "
      "IS their next change, and regressing one on the other returns a slope "
      "of 1.0 with an r of 1.0 -- a tautology wearing a lead's clothes. A "
      "genuine partial lead, where the published feed closes only part of the "
      "gap each second, returns a slope strictly inside (0, 1) and an r well "
      "below 1.")
    w("")
    sl_c, t_c, n_c, r_c = gap_regression(rep, pub, horizon=1)
    if sl_c == sl_c:
        if sl_c > 0.90:
            verdict = ("**REFUSE.** slope %.3f, r %.3f. This is the clock-"
                       "relabel signature and must not be read as a lead."
                       % (sl_c, r_c))
        elif sl_c > 0.02:
            verdict = ("**Information, not a clock.** slope %.3f, r %.3f, "
                       "t = %.0f: the published feed closes about %.0f%% of "
                       "the gap to us each second, and the low r says it is "
                       "not simply our own series relabelled."
                       % (sl_c, r_c, t_c, 100 * sl_c))
        else:
            verdict = ("**No lead.** slope %.3f, r %.3f, t = %.1f."
                       % (sl_c, r_c, t_c))
        w(verdict)
    w("")
    w("A one-second handicap on our own feed is reported in section 3 as a "
      "diagnostic. It is NOT a discriminator: a genuine one-second lead and a "
      "one-second timestamp offset both collapse under it, which is why the "
      "shape test above is the one that decides.")
    w("")
    w("## 3. The gap regression -- the decisive one")
    w("")
    w("Regress the published index's NEXT change on the CURRENT gap between "
      "our value and theirs. A noisy copy gives a slope of zero. A feed "
      "walking toward where we already are gives a positive slope, and the "
      "slope is the share of the gap that closes per second.")
    w("")
    w("| horizon | slope | t | r | n |")
    w("|---|---|---|---|---|")
    for h in (1, 2, 5, 10, 30):
        sl, t, nn, r = gap_regression(rep, pub, horizon=h)
        w("| %d s | %.4f | %.1f | %.4f | %d |" % (h, sl, t, r, nn))
    sl1, t1, _n1, _r1 = gap_regression(rep, pub, horizon=1)
    sl1h, t1h, _n, _r = gap_regression(rep, pub, horizon=1, shift=1)
    w("")
    w("With the one-second clock handicap, the one-second slope is %.4f "
      "(t = %.1f) against %.4f (t = %.1f) without it."
      % (sl1h, t1h, sl1, t1))
    w("")
    w("**Nothing here is a trading rule and nothing here is a loss rate.** "
      "What a lead would buy is a fresher `spot` inside the model's own "
      "forecast, which is a better forecast at every tau and costs nothing to "
      "use. Whether that survives contact with our fills is a separate "
      "question this file does not touch.")
    w("")
    txt = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(txt)
    say(txt)
    return txt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--feed", default="C:/kals/feed_data")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--coin", default="BTC")
    ap.add_argument("--field", default="wmid")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    iid = COIN_TO_INDEX.get(a.coin)
    if not iid:
        print("pinfeed: no published index known for %r" % a.coin)
        return 0
    rep = load_replica(a.feed, a.coin, field=a.field)
    if not rep:
        print("pinfeed: no replica seconds for %s -- nothing to analyse"
              % a.coin)
        return 0
    pub = load_published(a.data, iid)
    if not pub:
        print("pinfeed: no published index for %s -- nothing to analyse" % iid)
        return 0
    out = a.out or os.path.join(os.path.dirname(HERE), "results",
                                "RESULTS_feed_%s.md" % a.coin)
    report(a.coin, rep, pub, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
