#!/usr/bin/env python3
# VERSION: 2026-09-04-n1
"""
newseries.py -- is the collector actually recording what we told it to?

    python research/newseries.py --selftest
    python research/newseries.py --data ./kalshi_data

WHY THIS EXISTS

Adding a series to the collector is two steps that look identical whether
they worked or not. `discover()` polls REST per series and skips anything
that returns a non-200 -- so a series ticker that does not exist produces no
error, no log line, and no data. The collector keeps running happily and the
tape simply never contains it.

This project has already lost a whole branch to exactly that shape:
`everything.py` patched `run_all.ps1` to add the Coin Race series and it
never took effect, because the watchdog runs the collector from C:\\kals and
not from the repo. Nobody noticed for weeks, because nothing said so.

So: read the most recent file of each channel on disk, count messages by
series prefix, and print what is ACTUALLY arriving. A series we asked for and
are not receiving is named as a failure, loudly.
"""

import argparse
import glob
import gzip
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CHANNELS = ("ticker", "trade", "orderbook_delta", "orderbook_snapshot",
            "cfbenchmarks_value")


def series_of(ticker):
    """KXBTC15M-26SEP0412-T79000 -> KXBTC15M."""
    return ticker.split("-")[0] if ticker else ""


def tail_counts(data_dir, channel, files_back=1, max_lines=400_000):
    """Series -> message count, from the newest `files_back` files."""
    pat = os.path.join(data_dir, channel, "*.jsonl.gz")
    files = sorted(glob.glob(pat))[-files_back:]
    c = Counter()
    n = 0
    for fp in files:
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as f:
                for line in f:
                    n += 1
                    if n > max_lines:
                        break
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(m, dict):
                        continue
                    d = m.get("msg") or {}
                    tk = d.get("market_ticker") or d.get("ticker") or ""
                    s = series_of(tk)
                    if s:
                        c[s] += 1
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
    return c, files


def report(data_dir, want, verbose=True):
    """Returns (present, missing). `want` is the series list we asked for."""
    seen_any = defaultdict(int)
    if verbose:
        print("=" * 78)
        print("WHAT IS ACTUALLY ARRIVING -- newest file per channel")
        print("=" * 78)
    for ch in CHANNELS:
        c, files = tail_counts(data_dir, ch)
        if not files:
            if verbose:
                print(f"\n  {ch}: no files on disk")
            continue
        for s, n in c.items():
            seen_any[s] += n
        if verbose:
            base = os.path.basename(files[-1])
            print(f"\n  {ch}  ({base})")
            if not c:
                print("    no market_ticker in this channel "
                      "(normal for cfbenchmarks_value)")
            for s, n in sorted(c.items(), key=lambda x: -x[1])[:20]:
                mark = "" if s in want else "   (not in the asked-for list)"
                print(f"    {s:<20}{n:>10,}{mark}")

    present = sorted(s for s in want if seen_any.get(s))
    missing = sorted(s for s in want if not seen_any.get(s))
    if verbose:
        print("\n" + "=" * 78)
        print("VERDICT")
        print("=" * 78)
        print(f"  asked for {len(want)} series; {len(present)} are arriving")
        if missing:
            print(f"\n  *** {len(missing)} ASKED FOR AND NOT ARRIVING: "
                  f"{', '.join(missing)}")
            print("  A series that does not exist under that exact ticker is")
            print("  skipped by discover() with no error and no log line. If")
            print("  these were just added, give the collector a few minutes")
            print("  (it re-discovers every 30s, and 15-minute windows open")
            print("  on the quarter hour). If they persist, the ticker is")
            print("  wrong -- check it against the API before waiting a day")
            print("  for a tape that will be empty.")
        else:
            print("  every asked-for series is on disk.")
    return present, missing


# ===========================================================================
def _fixture(root, per_series):
    os.makedirs(os.path.join(root, "ticker"), exist_ok=True)
    fp = os.path.join(root, "ticker", "20260904T00.jsonl.gz")
    with gzip.open(fp, "wt", encoding="utf-8") as f:
        for s, n in per_series.items():
            for i in range(n):
                f.write(json.dumps({
                    "type": "ticker", "sid": 1, "seq": i,
                    "msg": {"market_ticker": f"{s}-26SEP0412-T{i}",
                            "yes_bid_dollars": 0.4}}) + "\n")
    return root


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []
    tmp = tempfile.mkdtemp(prefix="newseries_")
    try:
        want = ["KXBTC15M", "KXETH15M", "KXCRYPTOLEAD15M", "KXGHOST15M"]
        _fixture(tmp, {"KXBTC15M": 40, "KXETH15M": 25,
                       "KXCRYPTOLEAD15M": 7})
        present, missing = report(tmp, want, verbose=False)
        print(f"\n  planted 3 of 4 asked-for series")
        print(f"    arriving: {present}")
        print(f"    missing:  {missing}")
        if present != ["KXBTC15M", "KXCRYPTOLEAD15M", "KXETH15M"]:
            fails.append(f"present list wrong: {present}")
        if missing != ["KXGHOST15M"]:
            fails.append(f"a series with NO messages must be reported "
                         f"missing; got {missing}")

        # a series arriving with a single message still counts as arriving --
        # the failure this tool exists to catch is ZERO, not "few"
        c, _ = tail_counts(tmp, "ticker")
        print(f"    counts: {dict(c)}")
        if c.get("KXCRYPTOLEAD15M") != 7:
            fails.append("message counts are wrong")

        # an empty directory must not read as success
        empty = tempfile.mkdtemp(prefix="newseries_empty_")
        p2, m2 = report(empty, want, verbose=False)
        print(f"    on an EMPTY data dir: present={p2}, missing={len(m2)}")
        if p2 or len(m2) != len(want):
            fails.append("an empty data directory reported series as present")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print("=" * 78)
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        print("=" * 78)
        return False
    print("=" * 78)
    print("SELF-TEST PASSED -- names what is arriving, and names what was")
    print("asked for and is not.")
    print("=" * 78)
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--collector", default=None,
                    help="path to kalshi_collector.py whose CRYPTO_15M list "
                         "is the asked-for set (default: the DEPLOYED one "
                         "next to --data, then the repo's)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    # THE DEPLOYED FILE, not the repo's. The repo's list is what we INTEND;
    # the deployed one is what is running. everything.py's Coin Race patch
    # was lost for weeks in exactly that gap -- the watchdog runs the
    # collector from C:\kals, not from the repo.
    cands = []
    if a.collector:
        cands.append(a.collector)
    cands.append(os.path.join(os.path.dirname(os.path.abspath(a.data)),
                              "kalshi_collector.py"))
    cands.append(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "kalshi_collector.py"))
    want, src = [], None
    for c in cands:
        if not os.path.exists(c):
            continue
        try:
            txt = open(c, encoding="utf-8").read()
        except OSError:
            continue
        i = txt.find("CRYPTO_15M = [")
        if i < 0:
            continue
        j = txt.find("]", i)
        import re
        want = re.findall(r'"([A-Z0-9]+)"', txt[i:j])
        src = c
        break
    if not want:
        print("  could not read CRYPTO_15M from any collector file; "
              f"looked in: {cands}")
        return
    print(f"\n  asked-for series read from the DEPLOYED collector at {src}")
    print(f"  {len(want)} series: {', '.join(want)}\n")
    present, missing = report(a.data, want)
    raise SystemExit(1 if missing else 0)


if __name__ == "__main__":
    main()
