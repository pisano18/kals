# Verify C1-early-leg -- REPRODUCE lens (run 2, verify2)

Status: DONE 2026-09-22. Verdict: **WEAKENED**. Every dollar figure reproduces exactly. The reports do not disagree with each other: each one uses a different definition or time window. But the claim's framing does not survive: "main bleed", "5 of 8", "<=30 s positive on the same days", and "it pays more".

Scripts (my own; no investigator code reused): C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\map\verify2\C1-early-leg-reproduce\ (build.py, recon.py, a1-a11.py). No tape, no replay, no paper arms. Python < 100 MB. Free RAM 1.55 GB at start.

## Join check (done first)
- Ledger (`kalshi_ledger.json`, pnl = payout - costs - fees): 9 crypto pin series, 749 markets with live fills, **+$487.20**. This matches 10's 749 markets and +$487.20.
- Entry fills are `order` rows with filled > 0. Hedges are logged only as `hedge` rows: 0 of 34 hedge order_ids appear as `order` rows.
- For every UNHEDGED market, the P&L rebuilt from our fills equals the ledger to within 2c (0 mismatches). 17 markets hold both sides (hedged). Hedge P&L = ledger - entry P&L, which is exact per market.
- Leg label vs tau: all 203 `leg=early` fills have tau_at_send 31-45, and no other fill has tau > 30. First early fill 09-17 13:29Z, last 09-22 07:44Z. The early settings timeline from the `start` records matches the claim: frac 0.333 at 13:05Z 09-17, 1.0 at 19:41Z, off at 09-18 01:48Z, 0.333 at 03:02Z, 1.0 from 09-18 16:33Z, edge cap 10 from 09-19 05:08Z.

## 1. Headline numbers reproduced (since 09-17 13:05Z unless stated)
| definition | mine: mkts / closes / ledger $ | report | reconciles? |
|---|---|---|---|
| markets with ANY early fill, ledger to 09-22 08:00Z | 203 / 150 / **-57.38** | 09: 203 / -57.38 | exact |
| same, cut 09-22 06:29Z | 202 / 149 / **-59.00** | 02/05/07: 202 / 149 / -59.00 | exact (the 203rd is XRP 09-22 03:45 ET, +$1.62) |
| early-ONLY markets (no <=30 s fill) | 197 / 145 / **-69.84** | 10: 197 / -69.84 | exact |
| early LEGS, fill-level split, hedges assigned to their leg, cut 06:30Z | 202 / 149, 12,792 ct / **-65.39** | 01: 202 / 149 / 12,793 ct / -65.41 | yes (2c of mixed-market hedge rounding) |
| <=30 s LEGS, same cut | 110 fills, 7,157 ct / **+124.09** | 01: +124.08 | yes |
| main-only markets, cut 06:29Z | 89 / **+117.67** | 02/07: 89 / +117.67 | exact (to 08:00Z: 90 / +118.27) |
| main-only by ET day 09-17..22 (from 09-17 00:00 ET) | 98 / **+139.59** | 09: +139.59 | exact (includes 8 markets, +$21.32, before the leg existed) |
| since full size 09-18 16:33Z, cut 06:29Z | early 143 / 107 / -108.01; main 66 / 60 / +49.78 | 07: identical | exact |
| since v-nocap 09-20 09:48Z | early 62 / +9.78; main 28 / +68.85 | 07: identical | exact |
| early_frac 1.0 hours vs 1/3-1/2 hours | 161 / 117 / -96.48 vs 41 / 32 / +37.48 | 05: identical | exact (stake $11,370 vs 05's $11,276: a stake definition, not money) |
| first fill UTC >= 09-19 | early 129 / -126.70; main 60 / +34.62 | 02: identical | exact |
| ET days 09-19..22 | early 120 / -140.88; <=30 s 58 / +31.37 | 09: identical | exact |

**Why the -$57 to -$108 range exists:** it comes only from the window and the definition. 6 markets are MIXED (an early fill plus a <=30 s top-up). They net +$12.46 and all six won. Those six markets and the 09-22 cutoff account for the whole spread among -57.38, -59.00, -65.41 and -69.84. The -96 to -141 figures cover later windows, which cut out the leg's good first 1.5 days (09-17/18: +$83.50).

## 2. Era C (close ET day >= 09-19): the 76% claim
- 178 markets, net -$109.51. 8 losing markets, -$493.03. Both reproduce 10 exactly.
- **The early leg holds 6 of those 8 losing markets, not 5**, for -$373.51 (75.8%). The dollars in 10 and in the claim are right; the count is wrong. The 6 markets fall in 5 of the 7 losing closes, because XRP and HYPE share the 23:45 close.
  - BTC 09-19 16:00 -107.95: 110 ct at 98c, tau 45. No hedge ran (residue -0.01).
  - BTC 09-19 02:00 -66.34: tau 35. No hedge ran.
  - XRP 09-19 23:45 -64.95: **the bet WON**; the hedge lost -67.21.
  - HYPE 09-19 23:45 -43.92: **the bet WON**; the hedge lost -49.66.
  - NEAR 09-21 12:45 -59.09: the hedge recovered +15.15.
  - HYPE 09-21 18:15 -31.27: the hedge recovered +22.70.
- **4 of the 6 are hedge failures, -$283.16 of the -$373.51.** Two are false alarms on winning bets. In the other two no hedge ran, which the reports attribute to since-fixed bugs (a crash and the loss-cap pause). I verified only that no hedge fill exists for either; the bug attribution is theirs.
- Early fills are 63.2% of C's fills and 65.5% of its contracts. This matches "63%".
- Fill loss rate since 09-17 13Z: early 6 of 203 (2.96%), other legs 3 of 111 (2.70%). By market: 6 of 203 vs 2 of 96. By close: 6 of 150 vs 2 of 83. This reproduces "does not lose more often".
- Era C prices: early paid 96.91c (3.09c margin) and lost 3.61% of its contracts; other legs paid 95.98c (4.02c margin) and lost 3.49%. All four figures reproduce 10 exactly.
  - Fees are 0.20c a contract for early and 0.25c for other legs. With fees, the break-even contract-loss share is **2.89% for early vs 3.76% for other legs**. So early is below break-even and other legs are above.
  - That point estimate rests on **4 losing early fills**. On 4 of 120 the 95% interval is roughly 0.9-8.3%, which spans break-even.

## 3. Where the claim does not hold up
1. **"Main bleed" is one day.** Early-leg P&L (legs split, ledger) by ET day:
   - 09-17 +20.03
   - 09-18 +58.90
   - **09-19 -174.62**
   - 09-20 +74.21
   - 09-21 -47.12
   - 09-22 +4.83

   Without 09-19 the leg is **+$110.85**. Since 09-20 00:00 ET, after the bug fixes, it is **+$31.92**, against +$82.03 for the late window. It currently earns less per contract (+0.71c vs +3.92c). It is not losing money outside 09-19 and 09-21.
2. **The sign is not established.** Close-clustered bootstrap, 202 closes, per-leg dollars: early -$63.80, 95% CI [-$464, +$242], **P(early >= 0) = 0.39**. The early-minus-late gap is -2.23c/ct, CI [-5.94, +1.52], P = 0.12. From 09-20 on the gap is -3.20c, P = 0.004. That does not clear the ~0.001 multiple-looks bar. Without 09-19 the gap has P < 5e-5, but that is an artefact: the late window has ZERO losses outside 09-19, so the bootstrap can never draw one.
3. **"<=30 s buys are net positive in the same days" is false on the day that matters.** On ET 09-19, late-only markets made **-$50.63**: BNB 01:45 -57.76 and BNB 12:30 -61.75. The statement is true in aggregate (+$118.27) and on every other day.
4. **"It pays more" is era-specific.** Since 09-17 the average prices are 96.45c early vs 96.07c late, a gap of 0.38c, not 0.93c.
   - On 09-17 and 09-18 the early leg paid LESS than the late window: 94.31c vs 95.19c, and 96.33c vs 97.25c.
   - The median winning fill price is 97.8c for both legs.
   - In era C, half of the 0.93c gap comes from 4 late fills that filled 2c or more under the ask the bot saw (the book fell between decision and fill). Without them the gap is 0.50c (post-hoc cut).
5. **Crowd-out: not measured, and the one proxy does not show it.** Distinct close_budget refusals (the gate that fires when a close's budget is spent) hit 30 of 152 closes (20%) before the leg and 39 of 202 (19%) after. The refusal log is de-duplicated, so this is weak. Within-market crowd-out (a full-size early leg leaves no room for a <=30 s buy) cannot be valued without a replay: the log has no price for the offer that was not taken.

## 4. The counterfactual disagreement: there is none
- 01's "09-19: -$48.85 instead of -$223.46" covers **one ET day** (+$174.61).
- 01's all-days total of the same counterfactual is **+$65.41**. My per-day version matches 01's table to the cent: 09-17 +79.85, 09-18 +32.95, 09-19 -48.85, 09-20 +35.42, 09-21 +44.14.
- 10's **+$69.84** is the all-days total with early-ONLY markets removed.
- The two totals differ by $4.43. That is +$6.07 of early fills inside the 6 mixed markets (01 drops them, 10 keeps them) minus the $1.62 XRP market after 01's 06:30Z cut.
- **Both are right for their own definition, and both assume the freed budget sits idle.** Neither measures what the <=30 s window would have bought instead.
- Neither accounts for the -$200 loss-cap pause on 09-19. Without the early losses that pause would not have fired, so the rest of that day would have run differently. This is unmeasured.

## 5. Cuts and multiple looks
About 50 cuts: 7 definitions, 12 day x leg cells, 12 margin cells, 6 windows, 4 bootstraps, 4 price-through splits, plus the loss-rate, era and refusal tables. **Multiple-looks bar: p ~ 0.05/50 = 0.001.** Nothing that bears on the claim clears it. The one sub-0.001 result is the artefact in 3.2.
