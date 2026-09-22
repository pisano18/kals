# K4-drawdown-brake-code -- adversarial verifier, CODE lens

**Verdict: CONFIRMED.** Every factual part of the claim reproduces. Three small corrections are listed below; none changes the conclusion.
My own code, with no investigator scripts reused: `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\map\verify2\K4-drawdown-brake-code\`
(`ext.py`, `banks2.py`, `win.py`, `harness.py`, `rate.py`). Nothing under results/ or C:\kals was written except this file.
The harness asserts that `results/pinrun-hwm.json` is byte-identical before and after it runs.

## What the code does (research/pinrun.py, line numbers from the working tree at HEAD 73bbb7a)
- `MAX_DRAWDOWN = 0.20` is at line 1866. The high-water mark lives in `results/pinrun-hwm.json` (line 1868). `write_hwm` (1946) only ever raises the mark.
  `shift_hwm` (2024) is the only thing that lowers it. Nothing ages it, so "any number of days" is literally true.
- `drawdown()` (2059) = (hwm - bank)/hwm. The bank is CASH from `/portfolio/balance` (`read_bank`, 8205).
- `autosize_tick` (8368) skips while pinrun holds anything (8382). Otherwise it reads the bank and runs `classify_bank_move`
  (called at 8415, defined at 2002). Any unexplained move of $1 or more goes to `shift_hwm`. Then `write_hwm` runs and `state["drawdown"]` is set (8441-8444).
  The first tick of a run has no baseline (`ext_bank` is None), so it never classifies.
- `risk_abort` (7892-7899): `_dd >= MAX_DRAWDOWN` returns "DRAWDOWN brake". That halt is not in `TRANSIENT_HALTS` (7945), so it is terminal:
  the bot drains if it is holding (A74, hedge still armed), then hits `break` (9385-9387). `risk_abort` is called at 9320, AFTER the hedge pass.
- No `--max-drawdown` flag exists. CORRECTION to 06's "no flag disables it": `--no-auto-size` (10721) makes
  `autosize_tick` return at 8377, so `state["drawdown"]` is never set and the brake is dead. Harness T7: a bank of $500 against a mark of
  $958.90 does not halt. This is not a usable fix, because it also pins the size to --size 20.
- watch_bot.ps1 (111-112, 192-203) treats DRAWDOWN as a money brake: it waits 15 min, then restarts. Its own header (26-27) says "the
  brake resets per run anyway". That is FALSE for this brake. pindesk.py (1276-1281) tells the operator "watchdog restarts in
  ~N min, or press START now". Either way the bot halts again within 2 s. Nothing in the repo mitigates it.

## Harness: the real `autosize_tick` + `risk_abort`, with an injected bank reader, sandboxed files and no network
| test | result |
|---|---|
| T1 boundary at mark 958.90 | $767.13 and $767.12 trade; $767.11 halts (dd 0.20001). It trips when the bank falls below $767.12 |
| T2 six fresh "restarts" at $767 | 6 of 6 halt, 0 of 6 are transient, and the mark stays at 958.90 |
| T3 same, 30 days later | halts |
| T4 another bot loses $58.37 inside a run | classified as a withdrawal and the mark moves to 900.53; the dollar gap is unchanged, so the brake never sees the loss |
| T4b pinrun loses the same $58.37 | counted (dd 9.49%), mark unchanged |
| T5 another bot loses $58.37 while pinrun is DOWN | COUNTED (dd 9.49%), because the first tick has no baseline |
| T6 halted at $767, then $50 lands while the bot is down | the next run trades. This is a second way out besides a hand edit |
| T8 operator withdraws $160 while the bot is down (bank 757.92) | halts: a withdrawal made while the bot is down reads as a loss |

## Log + ledger evidence
- There are 19 `external` records across 124 live logs:
  - 1 is a real Kalshi deposit: $378.00 minus a $7.56 fee = $370.44, 09-19 07:13Z, in kalshi_transfers.json.
  - 17 match a NON-pinrun settlement in kalshi_ledger.json within 5.5 min: 13 oil/gold and 4 coin-race (two of the race ones share a settlement minute).
  - 1 (-$9.69, 09-17 23:16Z) matches an oil-bot ORDER in its cmdlive log.
  - **So 18 of 19 are other bots' money, and none is unmatched.** The -$58.37 at 09-17 20:16:58Z is WTI -58.76 plus gold +0.39, to the cent.
- CORRECTION: the 18 fakes net to **-$82.81**. The -$85.86 in 06 counts only the 14 oil fakes; the race fakes add +$3.05.
- The 09-20 mark of 1046.43 = 675.99 + 370.44. The last fake before the deposit was at 09-18 17:30Z (mark 615.27), and there was no
  external record between then and 09-19 07:13Z. So 675.99 was written by `write_hwm` from a real cash read. The oil
  fakes, including the $58.37, had already been overwritten and play NO part in the 09-20 halt. pinxfer.py (23-27) and the
  pindesk self-test text still say the $58.37 "inflated" the mark. They have the sign wrong: a fake withdrawal lowers the mark.
- The bank path reconciles to the cent against Kalshi:
  - 674.20 (05:03:59Z 09-19) to 557.18 just before the deposit = -117.02; the ledger says -117.02.
  - 927.62 to 810.59 at the halt = -117.03; the ledger says -117.03.
  - A +1.79 ZEC settlement at 05:15Z is the step from 674.20 to 675.99.
  - **The drawdown of -$235.84 is real. All of it is in pinrun's 9 crypto series: 70 settlements over 52 quarter-hours.**
- The halt repeated itself on 09-20 (bot logs + watch_bot.log lines 257-273). Halts at 03:45:35Z, 04:00:56Z (run started 04:00:54Z),
  04:16:38Z (started 04:16:37Z) and 04:30:42Z (started 04:30:40Z). Each time restart_bot reported "FAILED: pinrun did not come
  back". The next trading run started at 04:41:50Z, after the hand edit (dc036e9). That is 56 min, with the 04:00, 04:15 and 04:30Z closes missed.
- Now: the mark is 958.90 (set 09-21 19:50:20Z) and the last bank read was $917.92 (06:01Z 09-22). $150.80 of further losses trips it.
  The day cap is -$200 per ET day, so a single -$151 day trips the drawdown brake first. Arithmetic confirmed.

## Worst realistic cost (lost trading time, not a measured loss)
From the Kalshi ledger, pinrun series, ET days 09-15 to 09-21: +$236.35 total, **$33.76/day, $0.35 per 15-min slot**
(days: +76, +85, +100, +92, -223, +110, -3).
- An overnight self-repeating halt of about 8 h is 32 slots. That is **~$11 of expected profit at the 7-day rate, ~$28 at the median day**.
- The 09-20 halt cost about 3 slots (~$1).
- The halt itself is cheap, and it also stops losses in exactly the conditions that tripped it.
- The real cost is the hand reset. Resetting to $810.59 put the next trip at $648.47. That allows up to $398 (38%) below the equivalent high before the brake can fire again.

## Side hazard found (not in the claim, not measured as money)
`results/pinrun-hwm.json` is git-tracked; the committed copy at HEAD says 927.77. The live file was last modified at 06:31:57Z 09-22, but its
content is stamped 19:50:20Z 09-21. pinrun always stamps "at" with the current time, so something other than pinrun rewrote the file.
run_when_away.ps1 pulls with `--autostash`, which swaps the working file for the committed one during the pull. A failed stash pop, or a remote
commit of this file, would silently move the live mark.

## Smallest safe fix (the operator decides which behaviour; neither option touches the hedge path)
1. **Make the stop explicit instead of a 15-min re-halt loop.**
   - watch_bot: on "DRAWDOWN brake", write `pinrun-live.stop` with the reason and raise an alert; do not restart.
   - Add `pinrun.py --rebase-hwm`: it sets the mark to the current bank and logs `hwm_rebase {old,new,bank}`, so nobody hand-edits the JSON again.
   - Self-test: sandbox mark 958.90 and bank 767.00, and a fresh run halts. After the rebase the mark is 767.00 and a record with old=958.90 exists. The next fresh run trades.
     watch_bot -Once against a fake halt line creates the stop flag and starts nothing.
   - Alternative if he wants trading around the clock: halt until the next ET day, then rebase automatically with the same record. Same test, driven by `now`.
2. **Move the mark only on Kalshi's own transfer records**: pinxfer deposits/withdrawals with finalized_ts in (previous read, now]. Never infer transfers.
   The operator decides whether other bots' P&L counts.
   Self-test: a -$58.37 bank move with no Kalshi record gives no shift. A $370.44 deposit record gives +$370.44. A withdrawal record gives -X.
   Replaying the 19 logged events gives exactly one shift.
3. Stop git tracking `results/pinrun-hwm.json` (add it to .gitignore, then `git rm --cached`).

What each blocks:
- Fix 1 blocks nothing new; the bot is already stopped when it applies.
- Fix 2 makes the brake count other bots' losses too, which is tighter. It only applies if he chooses that.
- None of them blocks a hedge: the halt drains with the hedge armed (A74).

## Cuts tried / multiple looks
There were 7 data cuts plus 8 deterministic harness scenarios. The data cuts: external matching, mark provenance, 3 ledger windows, the halt list and the 7-day rate.
No claim here rests on a p-value. Every one is an exact to-the-cent reconciliation or deterministic code behaviour.
So the multiple-looks bar (0.05/7 = 0.007) is never used. n: 19 external events, and 52 quarter-hours in the drawdown window.
