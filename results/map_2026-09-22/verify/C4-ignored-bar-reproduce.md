# Verify C4-ignored-bar -- lens REPRODUCE (verify2 run)

**Status: COMPLETE (2026-09-22 ~08:2xZ). Verdict: WEAKENED.** The process part holds: the bar was met, nothing acted on it, and the cap is still 10.0. The -$94.31 reproduces to the cent, but it is **not** what the looser cap bought, and the 09-19 23:44 ET trigger trade is one the old 3c cap would also have taken.

Claim (07_evidence-audit.md F1/F3/solution 1): v-cheap's pre-registered undo rule (revert --early-max-edge 10 -> 3 after TWO losing closes among early fills under 96c in the first 40 such fills) was met 09-19 ~23:44 ET (09-20 03:44Z) and never acted on. The claim says those ~19 buys total ~-$94.31 on the ledger and the cap is still 10.0 in restart_bot.ps1. Solution 1 says reverting "Blocks: early-leg buys under ~96.5c (19 fills so far, -$94.31)".

The bar, verbatim (results/VERSIONS.md v-cheap; restart_bot.ps1 line 186): "BAR: revert to 3.0 at TWO losing closes on early fills under 96c in the first 40 such fills."

The code is my own, in scratchpad map/verify2/C4-ignored-bar-reproduce/: c4.py, c4b.py and c4c.py. It uses the `order` records with leg=='early', filled>0 and t >= the first `start` with early_max_edge==10. Money comes from the ledger via pinledger.load_cache/pnl, one row per market, so hedges are included. The signal edge is joined on ticker+t+leg. I did not read the tape or use the replay. Both recorders were alive at the end (collector pid 105304, feeds pid 105352). Free RAM was 1.5 GB and free disk 30.5 GB.

## Reproduced exactly

| item | audit | mine | source |
|---|---|---|---|
| v-cheap live | 09-19 05:08Z | first start with early_max_edge 10.0: **2026-09-19T05:08:21Z** (01:08 ET) | start records |
| cap now | 10.0 | all **26 of 26** starts since have 10.0 (last 2026-09-22T05:30:27Z). restart_bot.ps1 line 189 has `"--early-max-edge", "10.0"`, and the working tree matches HEAD | start records, git |
| early fills with fill price < 96.0c | 19 | **19 fills / 19 markets / 17 closes** (of 119 early fills since deploy) | order.exec_price, the price of the side bought |
| their ledger net | -$94.31 | **-$94.31**, 3 losing markets | ledger |
| 2nd losing close | fill #9, HYPE 09-20 03:44Z | **#9, KXHYPE15M-26SEP192345-45, 03:44:27Z = 09-19 23:44 ET** | ledger |
| 3rd | #17 NEAR -$59.09 | **#17, KXNEAR15M-26SEP211245-45, -$59.09** | ledger |
| the 10 fills after the bar | -$17.66 | **-$17.66** | ledger |
| acted on? | no | no. No commit message or VERSIONS entry after v-cheap mentions the bar. After 09-20 03:44Z the launcher changed **8** times (v-noboost reverted a *different* setting on its own bar 4 h later), and the bot restarted **13** times with 10.0 | git log, VERSIONS.md |

The three losing markets:
- **#2 BTC, 02:00 ET close on 09-19:** -$66.34. Our side lost, and there was no hedge because the process died.
- **#9 HYPE, 23:45 ET close on 09-19:** -$43.92. **Our side WON.** The loss is a false-alarm hedge: 104 YES bought for $47.84.
- **#17 NEAR, 12:45 ET close on 09-21:** -$59.09. Our side lost, and the hedge bought 81 NO for $65.00.

## Where the audit's reading is wrong

The cap tests the edge at the SIGNAL price, not at the fill price. The check is `early_wide_block(_leg46, e)` at pinrun.py ~10129, with `e` taken from the signal. I joined every fill to its signal:

| population | fills | closes | ledger net | losing mkts |
|---|---|---|---|---|
| audit's 19 (fill < 96c) | 19 | 17 | -$94.31 | 3 |
| of those, signal edge > 3c (the 3c cap would have refused that tick) | 16 | -- | -$60.30 | 2 |
| of those, signal edge <= 3c (**the 3c cap would ALSO have bought them**) | 3 | -- | -$34.01 | 1 |
| **what the 10c cap actually admitted:** every early fill with signal edge > 3c, at any fill price | **25** | **23** | **-$35.40** (2 losers -$125.43, 23 winners +$90.03) | 2 |
| every other early fill since deploy (edge <= 3c) | 91 | -- | -$79.55 | 3 |

- The 3 fills in the 19 that were not admitted by the cap change:
  - **HYPE #9:** signal 97.5c, edge 2.29c, filled at 94.1c, -$43.92.
  - **BNB #13:** 97.8c to 94.6c, +$3.70.
  - **SOL #16:** 97.2c to 91.4c, +$6.20.
  - Each filled below 96c only because the offers dropped between the signal and the fill. The 3c-cap era (09-18 06:51Z to 09-19 05:08Z) had 41 early fills and 0 under 96c.
- 9 fills that the cap change DID admit are missing from the 19 because they filled at 96.0-97.1c. Together they net +$24.90.
- Report 01 counts "26 legs, -$34.59" for the same cap-admitted cut, within $0.81 of mine. My 3 fills without a same-second signal all have edge <= 3c at the adjacent second (-$27.37 total), so they cannot explain the gap to -$94.31.
- **So reverting to 3c would have blocked about -$35.40 on 23 closes, not -$94.31.** It would not have blocked the HYPE -$43.92, and replacement buys later in the same market are not measurable from the ledger. For NEAR the model's confidence fell to 0.57 within 2 s and to 0.12 by 28 s, so a 3c-cap bot plausibly never buys it. For BTC the process died, so that one is unknown.

**When the bar was met depends on the reading, but it was met under every reading I tried:**

| definition of the population / of "losing" | 2nd losing close |
|---|---|
| fill price < 96c, market net < 0 on the ledger (the audit's reading) | #9 HYPE, 09-19 23:44 ET |
| fill price < 96c, whole close net < 0 on the ledger (the 3 losing closes were -$62.28, -$108.86 and -$59.09) | #9 HYPE, 09-19 23:44 ET |
| fill price < 96.5c or < 97c, market net < 0 | HYPE, 09-19 23:44 ET |
| fill price < 96c, our side lost | #17 NEAR, **09-21 12:44 ET** |
| price the bot saw (ask_seen or signal price) < 96c | NEAR, 09-21 12:44 ET |
| cap-admitted (signal edge > 3c), any loss definition | NEAR, 09-21 12:44 ET |

The audit's 23:44 ET date needs HYPE to count, and HYPE is a trade the old cap would have taken whose own side won. The conservative date is **09-21 12:44 ET**. Even then, 4 restarts followed with 10.0 still in place (09-21 13:03, 14:14 and 16:12 ET, and 09-22 01:30 ET).

## Cuts tried and multiple looks

I tried 10 cuts:
- fill < 96.0c, fill < 96.5c and fill < 97.0c
- ask_seen < 96c
- signal price < 96c
- signal edge > 3c, and its complement
- the 3c-cap era
- close-level nets
- two definitions of losing (market or close net < 0, versus our side lost)

With 10 looks the multiple-looks bar is p < 0.005 (|z| >= 2.81). **No significance is claimed.** Every dollar comparison here covers 17-23 closes, below the 30-close floor. The "bar met" conclusion is not cherry-picked: it holds under all 10 cuts, and only its date moves.

## Could not measure

- Whether a 3c-cap bot would have re-bought the refused markets later in the same close, or at 30 s or less. That needs the tape order book at each second, and I did not load it for this.
- Whether the BTC 02:00 ET loss would have happened under 3c. The process died at 05:59:25Z, and nothing after that was logged.

## Side note, not the claim

Two of the three losers filled 3.4-4.4c BELOW the price the bot saw, and both hedge alarms came 2 s later. Of the 116 early fills with a signal, 5 filled more than 1c below the signal price, and 2 of those 5 lost (n=5). That is C6's territory (collapse-fill).

## Verdict: WEAKENED

**Corrected claim.** The v-cheap bar was met and never acted on:
- by the audit's literal reading at 09-19 23:44 ET;
- by any reading tied to what the cap change admitted, or to our side losing, at 09-21 12:44 ET.

The cap is still 10.0 in restart_bot.ps1 and in every start record through 09-22 05:30Z.

The 19 early fills under 96c do net -$94.31, but 3 of them (-$34.01, including the triggering HYPE -$43.92, whose side won) would have been bought under the 3c cap too. What the looser cap actually admitted is 25 fills over 23 closes, netting -$35.40: 2 losers at -$125.43 against 23 winners at +$90.03. That is what a revert would block, before any replacement buys. It is below the 30-close floor.
