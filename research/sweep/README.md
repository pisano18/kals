# The money-idea sweep -- how to run it again

**Say to any Claude session: "run the money sweep"** (optionally: "focus on
sports", "the bank is now $2,000", "also consider X"). Claude reads this file
and does the steps below. Nothing here places an order; it is read-only
research that ends in a ranked list.

First run: 2026-09-25 (report `results/IDEA_SWEEP_2026-09-25.md`). The
operator's brief, which every run inherits: *"check EVERY type of bet it can
possibly find and come up with creative ideas for how a realistic bot could
make money on it... it just must come out on top... combine ideas nobody else
would... be critical of yourself and accurate... they can pull any information
from anywhere and make money in any way possible."*

## What it is

A Workflow (multi-agent) script, `research/sweep/money_idea_sweep.js`:

1. **Scout** -- 12 agents: one per market family (sports games; props,
   parlays and futures; elections and politics; economics, financials and
   commodities; crypto beyond our live markets; weather and science;
   entertainment, mentions and companies; cross-venue; exchange mechanics and
   incentives; calibration/bias across settled markets), one free-roaming
   "what would a pro shop do" scout, and one **revisit** scout that works the
   ledger's unresolved items.
2. **Combine** -- 4 agents cross-breed the scouts' ideas (consistency and
   arbitrage; information speed; incentives and loss-hedging; wild card).
3. **Merge** -- dedupe, drop re-proposals of dead ledger ideas, rank priors.
4. **Check** then **Refute** -- each idea gets a quick measured viability
   check; every one that is not dead goes to an independent skeptic who must
   re-derive a decisive number.
5. **Critic** -- wrongful kills, weak survivors, unexamined families, up to 8
   new ideas (checked too).
6. **Write** -- `results/IDEA_SWEEP_<date>.md` (plain language, for the
   operator), `results/idea_sweep_<date>.json` (everything), and an in-place
   update of **`results/IDEA_LEDGER.md`**.

**The ledger is what makes each run better than the last.** Every idea ever
checked is a row with status and reason; HOT AREAS and UNRESOLVED sections say
where to look next. Agents read it first, skip dead ideas unless they have a
new angle, and the writer updates it. Never delete a row.

## Steps for Claude

1. **Check the box first.** Free RAM (`FreePhysicalMemory`), free disk (stop
   below 6 GB), and that `kalshi_collector.py`, `crypto_feeds.py` and the live
   `pinrun.py --live` are running. The laptop runs ~7 agents at a time safely;
   lower `limit` if free RAM is under ~1.5 GB.
2. **Rebuild the catalogue** (5-15 min, GET only):
   `python research/sweep/sweep_catalogue.py` -> `.sweep/catalogue/`
   (gitignored). Add `--with-mve` only if the run is about parlays (45 min).
3. **Load the `workflow-authoring` skill**, then run the Workflow with
   `scriptPath: research/sweep/money_idea_sweep.js` and args, e.g.
   `{"date": "2026-10-05", "bank": "$1,500", "focus": ["sports"], "extra": "operator's added notes"}`.
   `date` is required (UTC). `focus` limits the family scouts (revisit always
   runs). `maxCheck` (default 60) and `limit` (default 7) are optional.
   To change the brief, edit the `PRE` block or a scout's `brief` in the script.
4. **When it finishes**: read the report adversarially (reconcile every
   $/day by hand, check the supply is on the RIGHT market), then commit
   `results/IDEA_SWEEP_<date>.md`, `results/idea_sweep_<date>.json`,
   `results/IDEA_LEDGER.md`, and add any survivor to `OPEN_WORK.md` with a
   "Say:" handle. Nothing trades without the operator's per-order sign-off.
5. Tell the operator the answer in plain language: what makes money, how sure,
   what the next test is.

## Cost and time

The 2026-09-25 run: roughly 11 scouts + 4 combiners + 1 merge + up to 60
checks + refutations + critic + writer (100+ agents), several hours of wall
clock at 7 at a time. Scale down with `focus` and `maxCheck` for a quick run.

## Other tools the sweep leans on

- `research/rungtrades.py` -- worked example of Kalshi trade-history analysis
  (who bought what, at what price, how long before the close).
- `research/poly/poly_ws_record.py` + `poly_ws_report.py` -- Polymarket US
  real-time book recorder (read key) and its report. They write next to
  themselves; copy them to a scratch folder to run.
- `research/sweep/sweep_catalogue.py` -- the catalogue builder above.
