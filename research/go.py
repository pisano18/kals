#!/usr/bin/env python3
# VERSION: 2026-08-25-go1
"""
go.py -- one command. Runs everything in order, writes one report.

    python research/go.py                       # from C:\\kals
    python research/go.py --quick               # skip the slow null draws
    python research/go.py --only chain          # a single stage

WHAT IT DOES

  1. Every self-test, first. If any fails, the run STOPS and no real data is
     touched. Four bugs of the fake-edge family were caught by these tests in
     two days; they are not a formality.
  2. Then each analysis stage, in dependency order, skipping any whose input
     is missing rather than failing the run.
  3. Writes RESULTS.md with the command, the raw output, and the exit status
     of every stage.

STAGES

  doctor    what is ACTUALLY on disk: which channels are flowing, at what
            rate, and what the fields are really called. Writes schema.json so
            no loader has to guess. Also answers the one question everything
            depends on -- is cfbenchmarks_value delivering?
  book      rebuild the real order book from snapshot+delta, with sequence
            integrity, and re-measure the queue depth that PLAN sec.4 used to
            kill the maker strategy.
  chain     strike(N+1) == settle(N). Gates the contract, and yields a
            15-min-spaced TWAP series per asset from PUBLIC settled records.
            Needs only the internet. Start here.
  volmodel  is the tail fat, or is it vol clustering? Decides which model to
            build. Needs chain_cache.json from the stage above.
  placebo   what does the calibration estimator return when the market IS
            efficient? Makes the existing 450-market result readable.
            Needs fulltape/.
  replay    run the decision engine over recorded collector data and score the
            P&L against its null. Needs kalshi_data/ and fulltape/.
  cross     is any ONE series mispriced relative to its peers? Demeaning the
            close-time cluster deletes the common crypto move, which is the
            term that made 12 correlated series worth only 1.22 independent
            ones. Measured power gain: 2.2x in t, 4.8x in variance.
  maker     can you QUOTE these markets rather than cross them? Makers pay NO
            fee on all sixteen 15-minute series while a taker crossing a 1c
            spread at the money pays 1.75c. The analytic half needs no data:
            a resting quote is a written option, exercised exactly when fair
            value moves through it, and the sigma cancels -- so the viable
            region is the same for BTC and DOGE. The measured half is realised
            adverse selection off the tape, against an exogenous-grid null.
  proxy     which price is the maker ACTUALLY quoting off? Nothing forces them
            to use BRTI; a desk quotes what it already has wired in. If they
            quote Coinbase or a delayed BRTI, every divergence is a knowable
            mispricing and nobody is wrong.
  pathstats is the contract price a martingale in its OWN right? Needs no
            index and no settlements. A violation is tradeable without ever
            holding to expiry -- enter, wait, exit -- which is a far better
            risk shape than betting on the outcome.
  feeds     the 3+ GB/day of constituent exchange books that NOTHING has ever
            read. They are not correlated with the settlement index -- they are
            its inputs. Does our replica lead Kalshi's published value, and does
            book imbalance predict the next seconds of index?
  implied   what the market BELIEVES, read straight out of its prices: the
            implied volatility surface. Needs NO settlements, so it runs on
            however many hours exist. Level = variance risk premium (a premium,
            not a mistake -- being paid it is a strategy). Term tilt = the
            market uses a different variance formula than ours. Smile = fat
            tails already priced. Per-series = where attention is thin.
  openwindow the first 60 seconds. strike(N+1) == settle(N), so the strike is
            knowable the instant the previous window closes -- before Kalshi
            stamps it. Also gates our strike reconstruction against
            floor_strike. H5 measures the MEAN opening edge, which is zero by
            symmetry; this measures the SIZE, which is what you trade.
  leadlag   does the book FOLLOW the index? PLAN_V3 ranks this the single most
            likely surviving edge, because it is plumbing rather than opinion.
            Needs kalshi_data/ and fulltape/.

Not stages. Run these around the results rather than inside them:

  research/power.py --data ./kalshi_data
Read this BEFORE the report. It says what this much data could have detected at
all. A stage whose measured effect is smaller than its minimum detectable
effect has produced no information -- positive or negative -- and "no edge
found" is not a finding there. It also counts the several hundred statistics
one run emits and prints the corrected threshold, which is a long way above 3.

  research/viability.py --edge 0.01 --price 0.95
Run this once you have a MEASURED edge. It prices the consequences rather than
looking for one: Sharpe with the correlation penalty applied, drawdown,
losing-month rate, and how long you would have to trade before the P&L could
tell the edge from luck.

NOTHING HERE PLACES AN ORDER. There is no order code in this repository and no
flag that enables one.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SELFTESTS = [
    ("settlement math", ["settlement_math.py", "--selftest"]),
    ("chain harness", ["chain.py", "--selftest"]),
    ("vol discriminator", ["volmodel.py", "--selftest"]),
    ("model-vs-market", ["edge.py", "--selftest"]),
    ("null calibrator", ["placebo.py", "--selftest"]),
    ("decision engine", ["engine.py", "--selftest"]),
    ("replay", ["replay.py", "--selftest"]),
    ("lead-lag", ["leadlag.py", "--selftest"]),
    ("format prober", ["doctor.py", "--selftest"]),
    ("book rebuild", ["book.py", "--selftest"]),
    ("cross-section", ["cross.py", "--selftest"]),
    ("open window", ["openwindow.py", "--selftest"]),
    ("implied vol", ["implied.py", "--selftest"]),
    ("constituent feeds", ["feeds.py", "--selftest"]),
    ("path statistics", ["pathstats.py", "--selftest"]),
    ("proxy reference", ["proxy.py", "--selftest"]),
    # power.py touches no data, but it is what makes every null result in the
    # report readable, and it is simulation code that can be silently wrong.
    ("student-t", ["tdist.py", "--selftest"]),
    ("gzip salvage", ["gzsalvage.py", "--selftest"]),
    ("maker economics", ["maker.py", "--selftest"]),
    ("detectability", ["power.py", "--selftest", "--quick"]),
]

# Paths are all relative to the repo root, and every stage runs there, so
# ./chain_cache.json means the same thing to the stage that writes it and the
# stage that reads it.
# Phrases a stage prints when its loader came back empty. Matching on the
# stage's own words is crude, but the alternative is every stage growing a
# machine-readable exit protocol, and the failure this catches -- eight
# stages reporting ok on no data -- is worth catching crudely today.
# Matched as REGEXES with word boundaries, not as bare substrings. The first
# version of this used `"0 markets" in out` and flagged five stages that had
# each loaded 1,090 markets and ~710,000 messages -- because "1,09|0 markets|"
# contains it. A false EMPTY is worse than no flag at all: it buries a real
# result under the one label that says "do not read this".
EMPTY_MARKERS = (
    r"could not locate ticker/bid/ask fields",
    r"no ticker messages on disk",
    r"Nothing rebuilt",
    r"\bno quotes\b",
    r"\bnothing to analyse\b",
    r"\bno cfbenchmarks_value data\b",
    r"\bnot enough overlapping data\b",
    r"(?<![\d,.])0 markets\b",
)

STAGES = [
    # doctor runs FIRST: it writes schema.json, which every loader downstream
    # reads instead of guessing at field names.
    ("doctor", ["research/doctor.py", "--data", "{data}", "--feeds", "{feeds}",
                "--schema", "./schema.json"], "{data}"),
    ("book", ["research/book.py", "--data", "{data}"],
     "{data}/orderbook_delta"),
    ("chain", ["research/chain.py", "--markets", "5000",
               "--cache", "./chain_cache.json"], None),
    ("volmodel", ["research/volmodel.py", "--cache", "./chain_cache.json"],
     "chain_cache.json"),
    ("placebo", ["research/placebo.py", "--out", "{out}"],
     "{out}/tapes.json"),   # placebo needs BOTH; tapes.json is the later write
    ("replay", ["research/replay.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    ("leadlag", ["research/leadlag.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    ("cross", ["research/cross.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    ("openwindow", ["research/openwindow.py", "--data", "{data}",
                    "--out", "{out}"], "{data}/cfbenchmarks_value"),
    ("implied", ["research/implied.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    ("feeds", ["research/feeds.py", "--feeds", "{feeds}", "--data", "{data}"],
     "{feeds}"),
    ("pathstats", ["research/pathstats.py", "--data", "{data}",
                   "--out", "{out}"], "{out}/markets.json"),
    ("proxy", ["research/proxy.py", "--data", "{data}", "--feeds", "{feeds}",
               "--out", "{out}"], "{data}/cfbenchmarks_value"),
    # maker last: it reads the same quotes every other stage does, and its
    # analytic half needs no data at all
    ("maker", ["research/maker.py", "--data", "{data}", "--out", "{out}"],
     "{data}/ticker"),
]


def run(cmd, cwd, timeout):
    t0 = time.time()
    try:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        p = subprocess.run([sys.executable] + cmd, cwd=cwd, timeout=timeout,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return 124, out + f"\n*** TIMED OUT after {timeout}s ***", time.time() - t0
    except Exception as e:
        return 1, f"*** {type(e).__name__}: {e} ***", time.time() - t0


def write_report(report, chunks):
    path = os.path.join(ROOT, report)
    # utf-8 explicitly: on Windows the default is cp1252 and this file embeds
    # whatever the stages printed. Dying here would throw away the whole run.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(chunks))
    os.replace(tmp, path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--feeds", default="./feed_data")
    ap.add_argument("--report", default="RESULTS.md")
    ap.add_argument("--only", choices=[s[0] for s in STAGES],
                    help="run a single stage. Validated: a typo used to skip "
                         "the self-tests (a.only is truthy) AND every stage "
                         "(none match), then exit 0 with an empty report.")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--skip-selftests", action="store_true",
                    help="not recommended; they exist because this project's "
                         "history is of measurement bugs producing fake edges")
    a = ap.parse_args()

    # Our own stdout is the last unprotected encoder in the chain. The
    # children are forced to utf-8, but this process re-prints their output
    # and (in everything.py) Kalshi's rules_primary text verbatim -- external
    # legalese full of curly quotes and en-dashes. Redirect this to a file in
    # PowerShell and sys.stdout becomes cp1252, which cannot encode them.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    chunks = [f"# RESULTS — automated run\n\n`{stamp}`\n",
              "Generated by `research/go.py`. Every stage's raw output is "
              "reproduced verbatim.\n"]
    print("=" * 78)
    print(f"go.py   {stamp}")
    print(f"  cwd={os.getcwd()}  data={a.data}  out={a.out}")
    print("=" * 78)

    ok = True
    if not a.skip_selftests and not a.only:
        print("\nSELF-TESTS (a failure here stops the run)")
        chunks.append("\n## Self-tests\n")
        for name, cmd in SELFTESTS:
            # power.py simulates for minutes; everything else is under
            # 150s. A flat cap sized for the fast ones kills the slow one on
            # slower hardware, and go.py then stops the whole run over a
            # timeout rather than a failure.
            budget = 2400 if cmd[0] == "power.py" else 900
            rc, out, dt = run(cmd, HERE, budget)
            passed = (rc == 0)
            ok = ok and passed
            print(f"  {name:>20}  {'PASS' if passed else '*** FAIL ***'}"
                  f"  ({dt:.0f}s)")
            chunks.append(f"\n### {name} — "
                          f"{'PASS' if passed else 'FAIL'} ({dt:.0f}s)\n")
            if not passed:
                chunks.append("```\n" + out[-4000:] + "\n```\n")
                # Show it here too. Burying the reason in the report cost a
                # whole round trip the first time this fired.
                tail = [ln for ln in out.strip().splitlines() if ln.strip()]
                for ln in tail[-6:]:
                    print(f"        | {ln[:110]}")
        if ok:
            os.environ["KALS_SELFTESTED"] = "1"
        if not ok:
            print("\n*** A SELF-TEST FAILED. Stopping; no real data touched. ***")
            print("    The failing output is in the report. Send it back.")
            chunks.append("\n**A self-test failed — no real data was "
                          "analysed.**\n")
            write_report(a.report, chunks)
            raise SystemExit(1)

    print("\nSTAGES")
    chunks.append("\n## Stages\n")
    empties = []
    for name, cmd, need in STAGES:
        if a.only and a.only != name:
            continue
        cmd = [c.replace("{data}", a.data).replace("{out}", a.out)
                .replace("{feeds}", a.feeds) for c in cmd]
        if need:
            path = (need.replace("{data}", a.data).replace("{out}", a.out)
                    .replace("{feeds}", a.feeds))
            if not os.path.exists(os.path.join(ROOT, path)) and \
               not os.path.exists(path):
                print(f"  {name:>20}  SKIPPED (missing {path})")
                chunks.append(f"\n### {name} — SKIPPED\n\nMissing `{path}`.\n")
                continue
        if a.quick and name in ("placebo",):
            cmd += ["--reps", "60"]
        rc, out, dt = run(cmd, ROOT, 600 if a.quick else 3600)
        # A STAGE THAT LOADED NOTHING IS NOT "ok". The first real run reported
        # ok for all thirteen while eight of them had no data at all: Kalshi
        # had renamed its websocket fields, every loader returned empty, and
        # every stage exited 0. Report that as EMPTY so it cannot read as a
        # null result.
        empty = rc == 0 and any(re.search(p, out) for p in EMPTY_MARKERS)
        label = ("EMPTY -- no data loaded" if empty
                 else "ok" if rc == 0 else f"exit {rc}")
        if empty:
            empties.append(name)
        print(f"  {name:>20}  {label}  ({dt:.0f}s)")
        chunks.append(f"\n### {name}{' — EMPTY' if empty else ''}\n\n"
                      f"```\npython {' '.join(cmd)}\n```\n")
        chunks.append(f"\nexit {rc}, {dt:.0f}s\n\n```\n{out[-60000:]}\n```\n")
        # after EVERY stage, not once at the end. Stages run for up to an hour
        # each; a Ctrl+C or a timeout two hours in used to throw away every
        # result already computed.
        write_report(a.report, chunks)

    if empties:
        msg = ("\n**%d stage(s) loaded NO DATA and must not be read as a null "
               "result: %s.** A stage that finds nothing because its loader "
               "returned an empty sample has measured nothing at all. Check "
               "the `doctor` stage's schema section against what the loaders "
               "asked for.\n" % (len(empties), ", ".join(empties)))
        chunks.append(msg)
        print(f"\n*** {len(empties)} stage(s) loaded NO DATA: "
              f"{', '.join(empties)}")
        print("    That is not a null result. See the doctor stage's schema "
              "section.")

    chunks.append("\n## How to read this\n\n"
                  "- `n` is always a number of MARKETS or CLOSE-TIME CLUSTERS, "
                  "never trades.\n"
                  "- A P&L figure means nothing without its null band; the "
                  "replay stage prints both.\n"
                  "- Every large edge this project has produced so far was a "
                  "measurement bug. Treat anything eye-catching as a bug until "
                  "it survives its own null.\n")
    path = write_report(a.report, chunks)
    print(f"\nwrote {path}")
    print("Send that file back.")


if __name__ == "__main__":
    main()
