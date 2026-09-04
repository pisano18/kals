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
  surface   given an implied/true sigma ratio, WHERE is it worth crossing
            the spread? Needs no data. The mechanism: if the market's sigma is
            too low its prices are too confident, so the cheap side is always
            the one below 50c -- and tau cancels exactly, so the edge does not
            depend on time to close at all, only on price. What does depend on
            price is the cost: the quadratic fee peaks at 50c and the tick is
            TAPERED, 0.1c below 10c against 1c above it. At 0.895 the net is
            positive below ~30c, best at 7c, and negative at the money.
  oos       WALK-FORWARD, and the only stage here that is not in-sample.
            Closes in time order; at each one, fit `a` on markets that settled
            STRICTLY BEFORE it, price this close's markets off that, take the
            trades whose edge beats the spread and the fee, and settle them.
            The parameter refits as the tape advances, so every trade is
            priced by a number that existed before its outcome did. Its
            self-test proves the absence of look-ahead rather than asserting
            it: `a` jumps mid-fixture and the fit must LAG the jump, which
            nothing that peeks can do. n is CLOSES; the null is what the
            strategy earns if the book is right, which is negative.
  calfit    the calibration curve as ONE number. P(win) = Phi(a*Phi^-1(p)),
            fitted by maximum likelihood over every settled market, clustered
            on close time. a = 1 is calibrated; a > 1 means outcomes come out
            more extreme than prices. It is not an arbitrary curve: a is
            exactly sigma_implied/sigma_true, so a = 1/r and it measures the
            SAME parameter reconcile.py gets from settlement dispersion, by a
            completely different route. Fisher information is zero at 50c and
            rises into the wings, so it down-weights the mid-book for free.
  term      the volatility TERM STRUCTURE. Every other vol result here is a
            LEVEL -- implied divided by a realised sigma we estimated -- so a
            bias in our estimator lands entirely in the answer. This is a
            SHAPE, compared within one market against itself, and needs no
            realised sigma at all. Invert every quote through the exact
            var_factor: if the market uses the same formula, implied sigma is
            FLAT in tau whatever it believes. sqrt(tau) makes it explode into
            the close (9.7x at tau=10), sqrt(tau-39.5) makes it collapse below
            40s. endgame.py has already priced what the first one is worth.
  endgame   the LAST sixty seconds, the mirror of openwindow. With tau left,
            60-tau of the settlement prints are already locked on disk, so
            sd/sigma falls to 0.017 at tau=1 and fair value stops depending on
            a volatility estimate at all. Naive sqrt(tau) is 9.7x too large at
            tau=10, which pins a quote near 50c exactly when the truth has gone
            deterministic. Prices each market off its OWN pre-endgame sigma,
            never a pooled one: the self-test measures what pooling costs at
            +2.5c claimed against -4.2c realised on a zero-edge tape.
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

# Checks that run even under --only. The full self-test gate does not: a
# single stage is meant to be fast, and that is reasonable for a measurement
# bug, which is confined to its own stage. It is NOT reasonable for an
# ENVIRONMENT bug, which breaks every stage at once and looks like sixteen
# separate failures.
#
# On 2026-08-28 a whole run died in fourteen stages because research/ held a
# file called compression.py and Python 3.14 added a stdlib package by that
# name, so `import gzip` resolved to ours. run_when_away.ps1 drives stages one
# at a time with --only, so the gate never ran, and the gate would not have
# caught it anyway: self-tests do not import gzip, and the stages that do are
# exactly the ones skipped when there is no data. It cost a full evening of
# recording time.
PREFLIGHT = [
    # The report, not the fixtures: this runs before EVERY stage, and the
    # fixtures spawn seven child interpreters each. Verifying the checker
    # itself belongs in the gate below, which runs once.
    ("stdlib shadowing", ["shadow.py", ".."]),
    # Cheap, and it guards the one failure mode that corrupts a GOOD run's
    # reading rather than the run itself: prose that trips EMPTY_MARKERS.
    # endgame.py printed "an edge in a bucket with no quotes is not an edge"
    # under a table of 89,757 quote-seconds and a full P&L, and the whole
    # stage was labelled EMPTY -- the one label that says do not read this.
    ("empty-marker prose", ["markers.py", ".."]),
]

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
    ("endgame", ["endgame.py", "--selftest"]),
    ("implied vol", ["implied.py", "--selftest"]),
    ("term structure", ["term.py", "--selftest"]),
    ("edge surface", ["surface.py", "--selftest"]),
    ("constituent feeds", ["feeds.py", "--selftest"]),
    ("path statistics", ["pathstats.py", "--selftest"]),
    ("proxy reference", ["proxy.py", "--selftest"]),
    # power.py touches no data, but it is what makes every null result in the
    # report readable, and it is simulation code that can be silently wrong.
    ("student-t", ["tdist.py", "--selftest"]),
    ("gzip salvage", ["gzsalvage.py", "--selftest"]),
    ("disk census", ["whatate.py", "--selftest"]),
    # Run from research/, so the two collectors at the repo root are
    # reached by "..". They are the only code in this project that
    # writes data nothing can re-record, which is exactly why their
    # self-tests belong in the same gate as the analysis.
    ("feed collector", [os.path.join("..", "crypto_feeds.py"),
                        "--selftest"]),
    ("maker economics", ["maker.py", "--selftest"]),
    ("vol timing", ["voltiming.py", "--selftest"]),
    ("calibration", ["calib.py", "--selftest"]),
    ("vol referee", ["reconcile.py", "--selftest"]),
    # patterntrade was called compression.py until Python 3.14 added a stdlib
    # package by that name. research/ is first on sys.path in every stage, so
    # `import gzip` resolved `compression._common` to OUR file and every stage
    # that touches compressed data died on import. shadow.py now guards this.
    ("pattern trade", ["patterntrade.py", "--selftest"]),
    ("calibration fit", ["calfit.py", "--selftest"]),
    ("walk-forward", ["oos.py", "--selftest"]),
    # cheap, and it is the only check that looks INSIDE main() --
    # the one function no self-test in this project executes
    ("stdlib shadow checker", ["shadow.py", "--selftest"]),
    ("empty-marker checker", ["markers.py", "--selftest"]),
    ("unbound names", ["unbound.py", "--selftest"]),
    ("repo name scan", ["unbound.py", ".."]),
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
    # Was "no cfbenchmarks_value DATA", and the word `data` is the reason five
    # stages could report ok on an index feed that delivered nothing. The
    # directory exists as soon as the collector subscribes, so the `need` guard
    # passes; cross, openwindow, implied, term and proxy then each print
    # "no cfbenchmarks_value -- ..." and return 0. None of them says "data".
    # The two that do (leadlag, replay) capitalise it "No", and the match is
    # not case-insensitive. Zero of seven matched. Now the feed name alone,
    # and every match below is case-insensitive.
    r"\bno cfbenchmarks_value\b",
    r"\bno settled markets\b",
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
    # endgame mirrors openwindow at the other end of the window. Its whole
    # point is that sd/sigma collapses to 0.017 at tau=1, so fair value stops
    # depending on any volatility estimate and starts depending on prints we
    # already have on disk.
    ("endgame", ["research/endgame.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    ("implied", ["research/implied.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    # term reads the same inversions implied does, but as a SHAPE in tau
    # rather than a level, so no error in our own realised-sigma estimate can
    # reach it. It is the only vol result here that is immune to that.
    ("term", ["research/term.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    # surface needs NO data at all -- it is what a given implied/true sigma
    # ratio would be worth, with the real fee and the real tapered tick. It is
    # in the report so the trading rule is written down BEFORE the number it
    # depends on is re-measured, rather than chosen after seeing it.
    ("surface", ["research/surface.py", "--data", "{data}"], None),
    # patterntrade backtests the calibration shape calib.py measures: whether
    # outcomes come out MORE extreme than prices. The 2026-08-28 23:00 run made
    # this urgent -- calib's grid column says they do (20c realises 16.9%, 90c
    # realises 94.4%), which is the OPPOSITE sign to reconcile's implied/settle
    # of 0.81. It has never run on real data; it was self-test only.
    ("patterntrade", ["research/patterntrade.py", "--data", "{data}",
                      "--out", "{out}"], "{data}/ticker"),
    # calfit fits ONE parameter to every settled market instead of one trade
    # per market. Same data, 3.5x the power: at 578 clusters its MDE is 1.6c
    # in money terms against patterntrade's 5.7c, which is the difference
    # between resolving the 3-5c calibration curve and not.
    ("calfit", ["research/calfit.py", "--data", "{data}", "--out", "{out}"],
     "{data}/ticker"),
    # oos is the only test here that is not in-sample. Every trade is priced
    # by an `a` fitted on closes strictly EARLIER than its own, so it answers
    # the question none of the others can: with only what was known at the
    # time, what would this have made? It is the slowest stage by design --
    # it refits as the tape advances.
    ("oos", ["research/oos.py", "--data", "{data}", "--out", "{out}"],
     "{data}/ticker"),
    # informed is the conditional cut of the strongest clean number this
    # project has produced: the taker's +0.612c signed markout (t=54.4).
    # maker.py pooled it and the pooled verdict is settled; this asks WHICH
    # trades carry the information and how far it drifts -- to settlement --
    # against the two live strategies: follow the informed tail as a taker,
    # or quote only in cells where the resting side is not run over.
    ("informed", ["research/informed.py", "--data", "{data}",
                  "--out", "{out}"], "{data}/trade"),
    # pin hunts the endgame's sleeping quotes: seconds where the locked
    # settlement prints say the outcome is decided (fair beyond 0.98) and a
    # quote is still on the wrong side of it. Four of the strategy panel's
    # twenty-one candidates were this one idea; it needs nobody to be wrong
    # about anything difficult -- only slow. Its report flags its own
    # overconfidence: realised below the fair band means OUR tail was wrong.
    ("pin", ["research/pin.py", "--data", "{data}", "--out", "{out}"],
     "{data}/cfbenchmarks_value"),
    # strikes needs no mispricing at all: within one event, P(settle >= K)
    # is decreasing in K by arithmetic, so ask(K_low) < bid(K_high) is a
    # riskless credit net of two fees. Thin fast books produce transient
    # crossings; nobody has looked.
    ("strikes", ["research/strikes.py", "--data", "{data}",
                 "--out", "{out}"], "{data}/ticker"),
    # flow reads the LARGEST thing on disk, and the only channel nobody has
    # read: 395,685,479 orderbook deltas, about twenty times the rest of the
    # tape put together. Every other stage here asks whether the PRICE is
    # wrong. This one asks whether the order flow knows, one second early,
    # where the price is going -- a different question, and the only one left
    # that this tape can answer. It streams and caches per day, so the first
    # run is slow and every run after it is not.
    ("flow", ["research/flow.py", "--data", "{data}", "--out", "{out}",
              "--cache", "./flow_cache"], "{data}/orderbook_delta"),
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
    # voltiming after maker: it asks whether the ONE confirmed finding is
    # already in the price. Its analytic half needs no data either.
    ("voltiming", ["research/voltiming.py", "--data", "{data}",
                   "--out", "{out}", "--feeds", "{feeds}"], "{data}/ticker"),
    # calib last: it decides whether D-FINAL's eight cells are a market
    # mispricing or the side that happened to trade.
    ("calib", ["research/calib.py", "--data", "{data}", "--out", "{out}"],
     "{data}/ticker"),
    # reconcile last: the canonical implied-vs-settle vol measurement, under
    # the referee's rules. This is the number the vol question rests on.
    ("reconcile", ["research/reconcile.py", "--data", "{data}",
                   "--out", "{out}"], "{data}/ticker"),
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
    if not a.skip_selftests:
        print("\nPREFLIGHT (runs even under --only)")
        chunks.append("\n## Preflight\n")
        for name, cmd in PREFLIGHT:
            rc, out, dt = run(cmd, HERE, 300)
            print(f"  {name:>22}  {'PASS' if rc == 0 else 'FAIL'}  ({dt:.0f}s)")
            chunks.append(f"\n### {name} — "
                          f"{'PASS' if rc == 0 else 'FAIL'}\n\n```\n{out}\n```\n")
            if rc != 0:
                print(f"\n*** PREFLIGHT FAILED: {name}. Nothing was run.")
                print(out)
                chunks.append("\n**Preflight failed. No stage ran.**\n")
                write_report(a.report, chunks)
                raise SystemExit(1)

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
    crashed = []
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
        # oos refits the parameter as the tape advances and sweeps seven
        # taus, seven edge floors and nine series, so it is the one stage
        # that legitimately needs hours rather than minutes.
        # flow is the slowest by a wide margin on its FIRST run -- it reads
        # every orderbook message on disk once. After that it reads its own
        # per-day cache and takes seconds.
        budget_s = 600 if a.quick else (
            14400 if name in ("oos", "flow") else 3600)
        if name == "informed":
            budget_s = 7200      # 27.7M trades; maker's fixed loop took ~25min
        rc, out, dt = run(cmd, ROOT, budget_s)
        # A STAGE THAT LOADED NOTHING IS NOT "ok". The first real run reported
        # ok for all thirteen while eight of them had no data at all: Kalshi
        # had renamed its websocket fields, every loader returned empty, and
        # every stage exited 0. Report that as EMPTY so it cannot read as a
        # null result.
        empty = rc == 0 and any(re.search(p, out, re.I) for p in EMPTY_MARKERS)
        label = ("EMPTY -- no data loaded" if empty
                 else "ok" if rc == 0 else f"exit {rc}")
        if empty:
            empties.append(name)
        if rc != 0:
            crashed.append((name, rc))
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

    # A STAGE THAT CRASHED IS NOT A NULL RESULT EITHER. The flow stage died
    # on a traceback 3,185 seconds in, go.py exited 0 anyway, and the runner
    # logged it as "flow -> 5.8 KB" alongside nineteen genuine successes. The
    # only place the failure appeared was thirty lines into the report.
    if crashed:
        msg = ("\n**%d stage(s) CRASHED and produced no result: %s.** A stage "
               "that raised has measured nothing. Its section below is a "
               "traceback, not a finding.\n"
               % (len(crashed), ", ".join(f"{n} (exit {r})"
                                          for n, r in crashed)))
        chunks.append(msg)
        print(f"\n*** {len(crashed)} stage(s) CRASHED: "
              f"{', '.join(n for n, _ in crashed)}")

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
    # Non-zero so the runner's own per-stage check sees it. The report is
    # written FIRST, so a failing exit never costs the results.
    if crashed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
