#!/usr/bin/env python3
# VERSION: 2026-08-25-d1
"""
doctor.py -- read the real collector output and tell the truth about it.

    python research/doctor.py --data C:\\kals\\kalshi_data --feeds C:\\kals\\feed_data

WHY THIS EXISTS

Every loader downstream of the collector guesses at field names. `yes_bid` or
`bid` or `best_bid`? Cents or dollars? Timestamp in `ts`, `created_time`, or
only in the local `_rx_ms` stamp? A wrong guess does not crash -- it silently
returns nothing, or worse, returns something subtly wrong. R4 lost 2,213 rows
to exactly that and it took a self-test to notice.

So stop guessing. This reads what is actually on disk, infers each channel's
schema, and writes `schema.json`. The loaders read that file and use the field
names that are really there.

IT ALSO ANSWERS THE QUESTION EVERYTHING DEPENDS ON

Is `cfbenchmarks_value` actually flowing? RUNBOOK warns that a
`{"type":"subscribed"}` reply is NOT success -- the channel returns it and then
delivers nothing unless the `index_ids` param is right. Without that feed there
is no model, no lead-lag test, and no project. This says yes or no in one line,
per index, with the observed tick rate.

WHAT IT CHECKS
  * every channel: files, messages, span, rate, how many files are mid-write
  * cfbenchmarks_value: which indices, ticks/sec, coverage gaps, avg_60s_data
  * ticker / orderbook: which bid-ask fields exist, and the price unit
  * orderbook_delta: sequence gaps (a gap means the book is wrong from there on)
  * the clock chain: CF timestamp -> Kalshi received_at -> our _rx_ms
  * disk growth rate and how long until the watchdog's 5GB floor

Read-only. Never writes anywhere under the data directories.
"""

import argparse
import glob
import gzip
import json
import zlib
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gzsalvage import iter_lines as salvage_lines   # noqa: E402

# concepts we need to locate, and the names they plausibly go by
# Kalshi suffixes its websocket fields with the UNIT: `_dollars` for prices
# (sent as strings like "0.4700") and `_fp` for fixed-point quantities (also
# strings, and genuinely fractional -- counts come back as "1.53"). Matching on
# the bare names silently found nothing: in the first real run, 68,976,084 of
# 68,976,084 orderbook deltas were unparsed and seven stages ran on zero
# quotes, every one of them exiting 0. SUFFIXES below strips those so a future
# rename cannot repeat it.
FIELD_CANDIDATES = {
    "ticker":    ["market_ticker", "ticker", "market", "market_id"],
    "yes_bid":   ["yes_bid", "yes_bid_dollars", "bid", "best_bid",
                  "yes_bid_price", "bid_price"],
    "yes_ask":   ["yes_ask", "yes_ask_dollars", "ask", "best_ask",
                  "yes_ask_price", "ask_price"],
    "bid_size":  ["yes_bid_size", "yes_bid_size_fp", "bid_size",
                  "best_bid_size", "bid_qty"],
    "ask_size":  ["yes_ask_size", "yes_ask_size_fp", "ask_size",
                  "best_ask_size", "ask_qty"],
    "price":     ["yes_price", "yes_price_dollars", "price", "price_dollars",
                  "last_price"],
    "delta":     ["delta", "delta_fp", "change", "size_delta"],
    "count":     ["count", "count_fp", "size", "quantity"],
    "taker":     ["taker_side", "side", "aggressor", "taker"],
    "ts":        ["ts", "created_time", "timestamp", "time", "received_at"],
    "seq":       ["seq", "sequence", "seq_num"],
    "index_id":  ["index_id", "index", "id", "index_ticker"],
}

# Unit suffixes Kalshi appends. Stripped only AFTER every exact match has been
# tried, so an exact hit always wins and the priority order is preserved.
SUFFIXES = ("_dollars", "_fp", "_cents", "_price", "_value")


def read_jsonl_gz(pattern, limit=None):
    n_partial = 0
    n = 0
    for fp in sorted(glob.glob(pattern)):
        try:
            for line in salvage_lines(fp):
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    n += 1
                    if limit and n >= limit:
                        return
        except (OSError, EOFError, zlib.error, gzip.BadGzipFile):
            n_partial += 1
            continue


def walk_paths(obj, prefix="", out=None, depth=0):
    """Every leaf path in a JSON object, with the type seen. Also descends into
    values that are themselves JSON *strings* -- the collector nests
    cfbenchmarks payloads that way and a naive walk misses them entirely."""
    if out is None:
        out = defaultdict(lambda: defaultdict(int))
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                walk_paths(v, p, out, depth + 1)
            elif isinstance(v, str) and v[:1] in "{[":
                try:
                    walk_paths(json.loads(v), p + "(json)", out, depth + 1)
                except (json.JSONDecodeError, ValueError):
                    out[p]["str"] += 1
            else:
                out[p][type(v).__name__] += 1
    elif isinstance(obj, list):
        for v in obj[:3]:
            walk_paths(v, prefix + "[]", out, depth + 1)
    return out


def sample_channel(data_dir, chan, n=4000):
    msgs = []
    for m in read_jsonl_gz(os.path.join(data_dir, chan, "*.jsonl.gz"), limit=n):
        msgs.append(m)
    return msgs


def _strip_unit(leaf):
    for suf in SUFFIXES:
        if leaf.endswith(suf) and len(leaf) > len(suf):
            return leaf[:-len(suf)]
    return leaf


def find_field(paths, concept):
    """Match a concept to a real path, preferring the shallowest match and the
    earliest candidate name.

    Exact matches first, then unit-suffix-tolerant ones. An exact hit always
    outranks a stripped one, so nothing that used to resolve can be stolen by
    the fallback -- but `yes_bid_dollars` now answers to `yes_bid`, which it
    did not, which is why the largest channel on disk went entirely unread.
    """
    cands = FIELD_CANDIDATES[concept]
    for stripped in (False, True):
        hits = []
        for i, cand in enumerate(cands):
            for p in paths:
                leaf = p.split(".")[-1].replace("(json)", "")
                if stripped:
                    leaf = _strip_unit(leaf)
                if leaf == cand:
                    hits.append((i, p.count("."), p))
        if hits:
            hits.sort()
            return hits[0][2]
    return None


def get_path(obj, path):
    """Read a dotted path, transparently decoding nested JSON strings."""
    cur = obj
    for part in path.split("."):
        nested = part.endswith("(json)")
        if nested:
            part = part[:-6]
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if nested and isinstance(cur, str):
            try:
                cur = json.loads(cur)
            except (json.JSONDecodeError, ValueError):
                return None
    return cur


def channel_stats(data_dir, chan):
    files = sorted(glob.glob(os.path.join(data_dir, chan, "*.jsonl.gz")))
    if not files:
        return None
    n, partial, bytes_ = 0, 0, 0
    for fp in files:
        try:
            bytes_ += os.path.getsize(fp)
        except OSError:
            pass
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as f:
                for _ in f:
                    n += 1
        except Exception:
            partial += 1
    return {"files": len(files), "msgs": n, "partial": partial, "bytes": bytes_}


# ===========================================================================
def report_channels(data_dir, label):
    print("=" * 78)
    print(f"CHANNELS under {label}")
    print("=" * 78)
    if not os.path.isdir(data_dir):
        print(f"  *** {data_dir} does not exist ***")
        return {}
    chans = sorted(d for d in os.listdir(data_dir)
                   if os.path.isdir(os.path.join(data_dir, d)))
    if not chans:
        print("  *** no channel directories -- the collector has written "
              "nothing ***")
        return {}
    print(f"  {'channel':<22}{'files':>7}{'messages':>12}{'MB':>9}"
          f"{'mid-write':>11}   status")
    out = {}
    for c in chans:
        s = channel_stats(data_dir, c)
        if not s:
            continue
        out[c] = s
        status = "OK" if s["msgs"] else "*** EMPTY ***"
        print(f"  {c:<22}{s['files']:>7}{s['msgs']:>12,}"
              f"{s['bytes']/1e6:>9.1f}{s['partial']:>11}   {status}")
    return out


def report_schema(data_dir, chan, msgs):
    print(f"\n  --- {chan} ---")
    if not msgs:
        print("    no messages")
        return {}
    paths = defaultdict(lambda: defaultdict(int))
    for m in msgs[:1500]:
        walk_paths(m, out=paths)
    top = sorted(paths.items(), key=lambda kv: -sum(kv[1].values()))[:18]
    print(f"    {len(paths)} distinct field paths. Most common:")
    for p, types in top:
        tt = ",".join(sorted(types))
        print(f"      {p:<46}{sum(types.values()):>7}  {tt}")
    mapping = {}
    for concept in FIELD_CANDIDATES:
        f = find_field(paths, concept)
        if f:
            mapping[concept] = f
    if mapping:
        print("    RESOLVED:")
        for k, v in sorted(mapping.items()):
            samples = [get_path(m, v) for m in msgs[:400]]
            samples = [s for s in samples if s is not None][:3]
            print(f"      {k:<12} -> {v:<40} e.g. {samples}")
    return mapping


def price_unit(msgs, path):
    """Cents or dollars, decided ONCE from the whole sample. Per-observation
    inference reads a 0.5-cent quote as 50 cents (that bug was worth
    75c/contract against a fair book)."""
    vals = []
    for m in msgs:
        v = get_path(m, path)
        try:
            vals.append(abs(float(v)))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None, 0
    mx = max(vals)
    return ("cents" if mx > 1.5 else "dollars"), len(vals)


def report_index_health(data_dir):
    print("\n" + "=" * 78)
    print("cfbenchmarks_value  --  THE feed everything depends on")
    print("=" * 78)
    msgs = sample_channel(data_dir, "cfbenchmarks_value", n=400_000)
    if not msgs:
        print("  *** NOT FLOWING. No messages at all. ***")
        print("  RUNBOOK: the channel needs param `index_ids` with values like")
        print("  BRTI, ETHUSD_RTI, ... A {'type':'subscribed'} reply is NOT")
        print("  success -- only a data frame is. Check the collector's [neg]")
        print("  lines in logs\\collector.out.log for 'NO WORKING PARAM FOUND'.")
        print("\n  Without this feed there is no model and no lead-lag test.")
        return None
    per = defaultdict(list)
    have_avg, wsz = 0, []
    lat_cf, lat_us = [], []
    for m in msgs:
        d = m.get("msg") or {}
        idx = d.get("index_id")
        inner = d.get("data")
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                inner = None
        if not idx or not isinstance(inner, dict):
            continue
        try:
            t = float(inner["time"]) / 1000.0
            v = float(inner["value"])
        except (KeyError, TypeError, ValueError):
            continue
        per[idx].append((t, v))
        a = d.get("avg_60s_data")
        if isinstance(a, dict):
            have_avg += 1
            try:
                wsz.append(int(a.get("window_size", 0)))
            except (TypeError, ValueError):
                pass
        ra, rx = d.get("received_at"), m.get("_rx_ms")
        if ra:
            try:
                lat_cf.append(float(ra) - float(inner["time"]))
            except (KeyError, TypeError, ValueError):
                pass
            if rx:
                try:
                    lat_us.append(float(rx) - float(ra))
                except (TypeError, ValueError):
                    pass
    print(f"  {'index':>14}{'ticks':>10}{'span (h)':>10}{'ticks/sec':>11}"
          f"   verdict")
    ok = 0
    for k, v in sorted(per.items(), key=lambda x: -len(x[1])):
        ts = sorted(t for t, _ in v)
        span = (ts[-1] - ts[0]) if len(ts) > 1 else 0
        rate = len(ts) / span if span > 0 else 0
        good = rate > 0.85
        ok += 1 if good else 0
        print(f"  {k:>14}{len(v):>10,}{span/3600:>10.2f}{rate:>11.3f}"
              f"   {'OK' if good else 'GAPPY'}")
    print(f"\n  {len(per)} indices delivering, {ok} at a healthy ~1/sec.")
    if have_avg:
        print(f"  avg_60s_data present on {100*have_avg/len(msgs):.1f}% of "
              f"messages", end="")
        if wsz:
            wsz.sort()
            print(f"; window_size median {wsz[len(wsz)//2]}")
            print("  ^ Kalshi publishes the running 60s average itself -- that")
            print("    is the settlement quantity, handed to us precomputed.")
        else:
            print()
    if lat_cf:
        lat_cf.sort()
        print(f"\n  latency CF -> Kalshi:  median {lat_cf[len(lat_cf)//2]:,.0f} ms"
              f"   p90 {lat_cf[int(len(lat_cf)*.9)]:,.0f} ms")
    if lat_us:
        lat_us.sort()
        print(f"  latency Kalshi -> here: median {lat_us[len(lat_us)//2]:,.0f} ms"
              f"   p90 {lat_us[int(len(lat_us)*.9)]:,.0f} ms")
        print("  (absolute value includes clock offset; the median-to-p90")
        print("   SPREAD is offset-free and is the number that matters)")
    return per


def report_orderbook(data_dir):
    print("\n" + "=" * 78)
    print("orderbook_delta  --  sequence integrity")
    print("=" * 78)
    msgs = sample_channel(data_dir, "orderbook_delta", n=200_000)
    if not msgs:
        print("  no orderbook_delta messages.")
        return
    gaps, seen, flagged = 0, {}, 0
    for m in msgs:
        if m.get("_seq_gap"):
            flagged += 1
        sid = m.get("sid")
        # Kalshi puts `seq` at the TOP level of the frame, not inside `msg`;
        # the emitted schema.json resolves it there. Reading msg.seq returned
        # None for every message, so gaps were counted over ZERO pairs and the
        # prober printed "Clean. A book reconstructed from these deltas is
        # trustworthy" about a channel that was, in the same run, 100%
        # unparseable. A green light computed from n=0 is worse than none.
        d = m.get("msg") or {}
        sq = m.get("seq", d.get("seq"))
        if sid is None or sq is None:
            continue
        prev = seen.get(sid)
        if prev is not None and sq != prev + 1:
            gaps += 1
        seen[sid] = sq
    print(f"  {len(msgs):,} messages across {len(seen):,} subscriptions")
    print(f"  sequence gaps: {gaps:,} (collector flagged {flagged:,})")
    if not seen:
        # NEVER certify from an empty sample. This branch printed "Clean...
        # trustworthy" over zero (sid, seq) pairs, in a run where the channel
        # it was certifying failed to parse 68,976,084 times out of
        # 68,976,084. The "0 subscriptions" on the line above was the only
        # clue, and nothing keyed on it.
        print("  *** NO (sid, seq) PAIRS FOUND -- this says NOTHING about "
              "book integrity.")
        print("  Either the channel is empty or the sequence field is not "
              "where this expects it.")
    elif gaps:
        print("  A gap means the reconstructed book is WRONG from that point")
        print("  until the next snapshot. Any fill model built on it is fiction.")
    else:
        print(f"  Clean across {len(seen):,} subscriptions. A book "
              f"reconstructed from these deltas is trustworthy.")


def report_disk(data_dir, feeds_dir):
    print("\n" + "=" * 78)
    print("DISK")
    print("=" * 78)
    tot = 0
    for d, label in ((data_dir, "kalshi_data"), (feeds_dir, "feed_data")):
        if not d or not os.path.isdir(d):
            continue
        b, oldest, newest = 0, None, None
        for fp in glob.glob(os.path.join(d, "*", "*.jsonl.gz")):
            try:
                st = os.stat(fp)
            except OSError:
                continue
            b += st.st_size
            oldest = st.st_mtime if oldest is None else min(oldest, st.st_mtime)
            newest = st.st_mtime if newest is None else max(newest, st.st_mtime)
        tot += b
        span_h = (newest - oldest) / 3600.0 if (oldest and newest) else 0
        rate = (b / 1e6 / span_h) if span_h > 0.5 else float("nan")
        print(f"  {label:<14}{b/1e6:>10.1f} MB over {span_h:>6.2f} h"
              f"   -> {rate:>7.1f} MB/h  ({rate*24/1000:.2f} GB/day)")
    try:
        import shutil
        free = shutil.disk_usage(data_dir).free / 1e9
        print(f"\n  free on this volume: {free:.1f} GB")
        print("  run_all.ps1 halts below 5 GB.")
    except Exception:
        pass


# ===========================================================================
def selftest():
    """Prove the prober finds the right fields regardless of which naming
    convention the collector actually used."""
    import tempfile, shutil
    print("=" * 78)
    print("SELF-TEST -- does schema discovery survive different field names?")
    print("=" * 78)
    fails = []
    VARIANTS = {
        "kalshi-style": lambda: {"type": "ticker", "msg": {
            "market_ticker": "KXBTC15M-A", "yes_bid": 47, "yes_ask": 48,
            "yes_bid_size": 300, "yes_ask_size": 250, "ts": 1760000000}},
        "short-names": lambda: {"type": "ticker", "msg": {
            "ticker": "KXBTC15M-A", "bid": 0.47, "ask": 0.48,
            "bid_size": 300, "ask_size": 250, "timestamp": 1760000000}},
        "best-prefixed": lambda: {"type": "ticker", "msg": {
            "market": "KXBTC15M-A", "best_bid": 47.0, "best_ask": 48.0,
            "best_bid_size": 300, "best_ask_size": 250,
            "created_time": "2026-08-25T00:00:00Z"}},
    }
    print(f"  {'variant':>16}{'ticker':>10}{'bid':>12}{'ask':>12}"
          f"{'size':>16}{'unit':>9}")
    for name, mk in VARIANTS.items():
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, "ticker"))
            with gzip.open(os.path.join(tmp, "ticker", "x.jsonl.gz"), "wt", encoding="utf-8") as f:
                for _ in range(500):
                    f.write(json.dumps(mk()) + "\n")
            msgs = sample_channel(tmp, "ticker")
            paths = defaultdict(lambda: defaultdict(int))
            for m in msgs[:500]:
                walk_paths(m, out=paths)
            got = {c: find_field(paths, c) for c in
                   ("ticker", "yes_bid", "yes_ask", "bid_size")}
            unit = price_unit(msgs, got["yes_bid"])[0] if got["yes_bid"] else "?"
            print(f"  {name:>16}{str(got['ticker']).split('.')[-1]:>10}"
                  f"{str(got['yes_bid']).split('.')[-1]:>12}"
                  f"{str(got['yes_ask']).split('.')[-1]:>12}"
                  f"{str(got['bid_size']).split('.')[-1]:>16}{unit:>9}")
            for c in ("ticker", "yes_bid", "yes_ask", "bid_size"):
                if not got[c]:
                    fails.append(f"{name}: failed to locate {c}")
            v = get_path(msgs[0], got["ticker"]) if got["ticker"] else None
            if v != "KXBTC15M-A":
                fails.append(f"{name}: resolved ticker path reads {v!r}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # nested-JSON-string payload, as cfbenchmarks_value really arrives
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "cfbenchmarks_value"))
        with gzip.open(os.path.join(tmp, "cfbenchmarks_value", "x.jsonl.gz"), "wt", encoding="utf-8") as f:
            for i in range(500):
                f.write(json.dumps({"type": "cfbenchmarks_value", "msg": {
                    "index_id": "BRTI",
                    "data": json.dumps({"time": (1760000000 + i) * 1000,
                                        "value": 80000.0 + i})}}) + "\n")
        msgs = sample_channel(tmp, "cfbenchmarks_value")
        paths = defaultdict(lambda: defaultdict(int))
        for m in msgs[:500]:
            walk_paths(m, out=paths)
        found = [p for p in paths if "value" in p]
        print(f"\n  nested JSON string: found {found}")
        if not any("(json)" in p for p in found):
            fails.append("did not descend into a nested JSON string payload")
        got = get_path(msgs[0], "msg.data(json).value")
        if got != 80000.0:
            fails.append(f"nested path read {got!r}, expected 80000.0")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- field discovery works across naming conventions")
    print("and descends into nested JSON-string payloads.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--feeds", default="./feed_data")
    ap.add_argument("--schema", default="./schema.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    print("\n\n" + "#" * 78)
    print("# COLLECTOR HEALTH")
    print("#" * 78)
    chans = report_channels(a.data, a.data)
    report_channels(a.feeds, a.feeds)

    print("\n" + "=" * 78)
    print("SCHEMA -- what the fields are ACTUALLY called")
    print("=" * 78)
    schema = {}
    for c in ("ticker", "trade", "orderbook_delta", "cfbenchmarks_value"):
        if c not in chans or not chans[c]["msgs"]:
            continue
        msgs = sample_channel(a.data, c, n=4000)
        m = report_schema(a.data, c, msgs)
        for pc in ("yes_bid", "price"):
            if m.get(pc):
                u, n = price_unit(msgs, m[pc])
                if u:
                    m[pc + "_unit"] = u
                    print(f"    price unit for {pc}: {u} (from {n} samples)")
        schema[c] = m

    report_index_health(a.data)
    report_orderbook(a.data)
    report_disk(a.data, a.feeds)

    # tmp + replace: a truncated schema.json is silently swallowed by
    # replay.load_schema, and every loader then reverts to GUESSING field
    # names -- producing numbers that look valid and are subtly wrong, which
    # is this project's entire failure mode.
    with open(a.schema + ".tmp", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    os.replace(a.schema + ".tmp", a.schema)
    print(f"\n  wrote {a.schema} -- the loaders read this instead of guessing.")
    print("\n  If cfbenchmarks_value is flowing and ticker resolved bid/ask,")
    print("  everything downstream will run. If not, the lines above say why.")


if __name__ == "__main__":
    main()
