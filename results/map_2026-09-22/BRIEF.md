# PROJECT MAP 2026-09-22 -- shared brief for every investigator

Read this whole file, then `C:\kals-repo\CURRENT_STATE.md`, then the top two
sections of `C:\kals-repo\HANDOFF.md`, then your own assignment.

## The question

The operator, in his words: *"the bot was making consistent money but not as
much as it seemed like it could, so made some changes and tweaks to try and
grow that, now the bot loses money and we want to make money."* And: *"point
to them as clearly and detailed as possible and say we are bleeding because of
exactly this and also have a technical understanding of it."*

Priority order, his: **lose less / identify better > make more > everything
else.** Daily totals by the bot's own logs (`python research/pinday.py`):
09-15 +$76, 09-16 +$85, 09-17 +$116, 09-18 +$92, 09-19 -$161, 09-20 +$110,
09-21 -$3. Money put in $584.46 (research/pinxfer.py), no withdrawals, ever.

## Sources of truth, in order of trust

1. **Money per market: `results/kalshi_ledger.json`** -- Kalshi's own
   `/portfolio/settlements`, one row per market, a hedged market is ONE row
   with the net. Read it with `research/pinledger.py` (`load_cache`, `pnl`,
   `money`). This is the authority for what a market made or lost.
2. **Deposits: `research/pinxfer.py`.** Never treat a bank change as profit.
3. **What the bot decided and did: `results/pinrun-live-*.jsonl`** (124
   files, 7.6 MB, one per run). Kinds include `start` (its settings), `signal`,
   `order` (fills, exec price, ask seen), `settled` (per LEG: `pnl_c` in
   cents; a hedged market writes TWO rows -- sum them; NEVER sum `realised`,
   it is a running total that resets on restart), `refused` (with `gate`),
   `hedge`/`hedge_panic`/`hedge_prop`, `autosize` (bank, size), `halt`,
   `close_summary`. Read a few of each kind before trusting a field name.
4. **What changed when: `results/VERSIONS.md`** (newest first; UTC deploy
   time, what changed, evidence, revert) and `git log -p -- restart_bot.ps1`
   (the live flag list at every commit). Code changes that were not flags are
   in `git log -- research/pinrun.py`.
5. **The tape** -- `C:\kals\kalshi_data\<channel>\YYYYMMDDTHH.jsonl.gz`, one
   file per channel per UTC hour; `cfbenchmarks_value` is the 1/sec settlement
   index. READ ONLY, stream only the hours you need, never load it whole. The
   tape tells you what the index and the market DID. **It is never a source
   for how often WE lose** -- the operator's rule, earned: tape said 0.11%,
   our fills said 3.4% (CLAUDE.md, amendment 2026-09-10).
6. **The replay (`pinsim`, `pindata`) is a HYPOTHESIS, whatever its n.** If a
   claim rests on it, say so in its first sentence.

Paper arms: every arm number before 2026-09-20 is void (arms could not hedge
and ran stale settings); between 09-20 14:2xZ and 09-21 ~17:00Z arms matched
live; after the 09-21 hedge changes nothing matched until the resync at
2026-09-22 06:21Z. Use arms only inside a window where they matched live.

## Rules (CLAUDE.md hard rules -- not optional)

- **n is closes (or markets), never trades.** All coins settling on one
  quarter hour are ~1.2 independent observations, not 12. Floor: 30 closes
  before calling anything significant; print the multiple-looks threshold when
  a table has many cells.
- **Never claim what you did not measure.** A script that fails is reported
  as a failure, not estimated around.
- **State what would make a good-looking result an artefact, then check it.**
  Every large edge this project ever found was a measurement bug.
- **A loss is quoted next to the return that bought it.** Half a comparison
  is reported as half.
- **Price units:** decide once from the whole sample; the tick is 0.1c below
  10c and above 90c. Never infer a unit from one magnitude.
- Times in prose: US Eastern, EDT = UTC-4, written "ET". Data stays UTC.

## Resource rules -- a live money bot is running

- **Do not start, stop or signal any process. Do not edit any file** except
  your own output file below and files under your scratchpad folder
  `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\map\<your-name>\`.
- Never write under `C:\kals` or `C:\kals-repo\results` other than your file.
- Free RAM is ~2.6 GB with the live bot, 2 recorders and 25 paper bots
  running. Keep every python process under ~500 MB; do NOT call
  `replay.load_quotes` or build the flow cache. Check free RAM before
  anything that reads the tape; if under 1.0 GB, stop and report.
- Python is stdlib only (`C:\Python314\python.exe`). Use the Bash tool.

## Output -- CRASH-SAFE, THIS IS WHY THE LAST TWO MAPS PRODUCED NOTHING

Write `C:\kals-repo\results\map_2026-09-22\<NN>_<your-name>.md` **within
your first few minutes** (headings and "in progress"), and **update it after
every finding**, not at the end. Two earlier runs of this map died to network
errors and every investigator's work was lost because it lived only in the
reply.

Structure:

1. **Findings, ranked by dollars.** Each: the claim in one sentence; the
   mechanism (why it happens, technically); the evidence (numbers, source,
   window, n closes); the dollar impact over the window with the return it
   sits beside; confidence; what would make it an artefact and whether you
   checked.
2. **Refuted or not supported** -- things you expected and did not find.
3. **Could not measure, and why.**
4. **Solutions worth testing** -- concrete, each with how it would be
   validated on LIVE fills (or why it cannot be) and what it would block.
   A gate must never block a hedge; say what each proposal would block.

Your final reply: the top findings in <= 40 lines, with numbers and n.
