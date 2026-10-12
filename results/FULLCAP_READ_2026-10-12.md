# FULLCAP READ 2026-10-12 -- v-revert0925-fullcap (`--max-full-bets 1.0`), READS_DUE id `fullcap-live`

**VERDICT: KEEP.** Rule never broken (0 of 310 markets over 1.0x the full bet; 0 hedges missing or short on the 43 capped markets). Week 1 cost (2026-10-04T09:20:40Z..2026-10-11T09:20:40Z): winners gave up -$0.03 net of proportional insurance, and $28.03 at most with no insurance credit and every stopped contract assumed filled. Both are under the $30 bar. No losing market was cut (0 of 43 touched markets lost).

Source: OUR LIVE FILLS (`results/pinrun-live-*.jsonl`, 9 logs from `20261004T092040Z` to `20261012T111511Z`) joined to Kalshi per-market money (`results/kalshi_ledger.json`). No tape and no pinsim were used. Script: `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\fullcap_read_2026-10-12.py` (session scratchpad, not committed). Its method is `results/fullcap_measure_2026-10-04.py`, turned around for a cap that is live: history is already capped, so the script adds back what the cap stopped.

## Deploy confirmed
- The start record at 2026-10-04T09:20:40Z has code_sha `269958db6d68`, max_full_bets 1.0, mode live, late_mult 1.5 at tau <= 10 and band_mults [].
- Every later start record has max_full_bets 1.0: 2026-10-05T04:46:15Z (269958db6d68), 2026-10-05T14:24:02Z (3776ff66b2fb), 2026-10-06T15:41:22Z and 2026-10-07T13:30:39Z (c0fe4953e891), 2026-10-10T02:07:23Z and 2026-10-10T22:16:08Z (5075b1783acf), 2026-10-11T10:43:32Z (deda2006d5ae) and 2026-10-12T11:15:11Z (813f1806e3ad).
- Ledger reach: the last Kalshi settlement is 2026-10-12T14:30:03Z. All 310 markets with a live fill in the window have a ledger row (none missing), so the window ends there.

## 1. Rule-broken checks
| check | result |
|---|---|
| any market whose bet side held more than 1.0x the full bet in force (SIZE, or the KXBTCD series size, x1.5 at tau <= 10 else x1), tested on both Kalshi's count and the log's | **0 of 310 markets** |
| log vs Kalshi bet-side count mismatch > 0.5 contract | 0 |
| a hedge missing or smaller than the position on a market where full_cap / full_cap_trim fired | **0 of 43**. One touched market alarmed: KXZEC15M-26OCT101800-00, held 92 yes; the hedge asked 92 and Kalshi shows 92 no |
| a full_cap refusal on a hedge leg (would mean the gate blocked a hedge) | 0 (the legs were late_add 15 and full 14) |

Capability check: the same rule test was run on the uncapped 09-25 build window (2026-09-25T06:25:09Z..2026-09-27T08:11:15Z). It flagged **7 of 107** markets over 1.0x, mostly same-second double orders (for example KXSOL15M-26SEP251015-15: 178 held vs 89 allowed). So the 0 above comes from a check that does fire when the rule is absent. At that rate, about 20 of the 310 would be expected without the cap.

For completeness, and outside the entry rule: in 4 untouched markets the insurance side ended above the bet side (1.5x hedges: KXBTC15M-26OCT041615-15, KXHYPE15M-26OCT042015-15, KXHYPE15M-26OCT050030-30, KXETH15M-26OCT100915-15). Hedges are not entries, and the cap never governs them.

## 2. Cost: every refused full_cap and every full_cap_trim since the deploy
- **Records:** 29 refusals and 16 trim records. One trim was an exact duplicate (KXBTC15M-26OCT092300-00, the same second, was and now), which leaves 15 trims.
- **Markets touched:** 43 markets on 43 distinct closes. 29 are 15-minute markets. 14 are KXBTCD ladder rungs at 1 contract each.
- **Winners and losers (Kalshi result):** all 43 won and none lost.

**How the cost is counted:**
- **Stopped contracts.** A refusal counts the order it would have sent. A trim counts the contracts it cut (was - now).
- **Upper bound.** Every stopped contract is assumed filled at the refusal or trim price.
- **Fill-checked.** A trim counts 0 when its trimmed order did not fill in full: an immediate-or-cancel order at the same limit that could not fill `now` could not have filled more. A refusal stays at the upper bound because the book depth is unknown.
- **Winner given-up** = stopped contracts x (1 - price - 0.07 p(1-p)), plus the insurance net x stopped/held. That last term assumes the insurance is sized in proportion. It is <= 0 for a winner, so it lowers the cost.

| window (UTC) | markets / closes | refusals | trims | lost | stopped contracts (upper / fill-checked) | winners' given-up, net of proportional insurance (upper / fill-checked) | given-up with NO insurance credit (upper / fill-checked) | losers' saved |
|---|---|---|---|---|---|---|---|---|
| W1 2026-10-04T09:20:40Z..2026-10-11T09:20:40Z (7 days) | 41 / 41 (27 15-min, 14 ladder) | 29 | 12 | 0 | 854.52 / 758.00 | **-$0.03 / -$1.91** | **$28.03 / $26.15** | $0.00 |
| W2 2026-10-11T09:20:40Z..2026-10-12T14:30:03Z (1.2 days, partial) | 2 / 2 | 0 | 3 | 0 | 173.44 / 94.62 | $3.43 / $1.76 | $3.43 / $1.76 | $0.00 |
| ALL 8.2 days | 43 / 43 | 29 | 15 | 0 | 1,027.96 / 852.62 | $3.41 / -$0.15 | $31.47 / $27.91 | $0.00 |

- **Split:** the KXBTCD ladder accounts for only $0.41 upper of the total. The rest is the 15-minute markets.
- **Context:** the window traded 310 markets for a Kalshi net of +$142.45. In W1 that was 264 markets and +$84.62, with 7 bet-side losses.
- **Largest single item:** KXZEC15M-26OCT101800-00 (2026-10-10T21:59:47Z). The cap refused a late add of 46 at 0.87. Gross, that is $5.62 given up. The market's 92-contract insurance lost $56.12, so proportional insurance on 46 more contracts would have cost a further $28.06. That one market is the whole gap between the "net of insurance" column and the "no credit" column.
- **The usual pattern:** most of the cost is the half-bet late add at tau 11-15 (15 refusals) and same-second duplicate orders. KXZEC15M-26OCT120730-30 is an example: a second 95 order was trimmed to 0.38 after the first filled 94.62.
- **Pre-registered estimate:** $11.38 per 7 days, measured 09-27..10-04 at 1.0x. The W1 cost with no insurance credit came in 2.5x higher, at $28.03. W1 net of insurance came in lower, at -$0.03. That estimate came from one-full-bet builds that rarely went past 1x; the 09-25 build's late add and duplicate sends hit the cap more often.

## 3. Verdict against the bar (as pre-registered)
The bar says: "back ... at once if ANY market holds more than 1.0x the full bet ... or any hedge on a market where full_cap/full_cap_trim fired is missing or smaller than the position; otherwise keep unless the refused/trimmed winners give up more than $30 over the week with no losing market cut".
- **First condition (rule broken):** 0 markets. Not triggered.
- **Second condition (hedge missing or short):** 0 hedges. Not triggered.
- **Third condition (cost):** no losing market was cut, so the cost test applies. W1 given-up is -$0.03 net of proportional insurance and $28.03 at the most conservative reading. Both are under $30.

**Verdict: KEEP.** The margin is thin at the most conservative reading: $1.97 under the bar.

## 4. What could make this an artefact, and what was checked
- **Full bet in force mis-computed.** band_mults is [] and doubt is off in every start record. SIZE is taken from the latest start/autosize record. The KXBTCD size is 1 before 2026-10-11T10:43:32Z and floor(0.12 x SIZE) after, per VERSIONS v-btcd1 and v-snowball. The check uses both the allowed size at the last bet-side fill and the maximum allowed. It fired on 7 of 107 markets in the uncapped 09-25 window, so it is capable of finding a breach.
- **Log under-counting holdings.** Held is taken from Kalshi's settled count, and its mismatch with the log is 0 on all 310 markets.
- **Refusals that would have been refused anyway.** In both builds' code (`C:\kals-live-0925b`, `C:\kals-live-0925i`), the full_cap gate sits after every other entry gate and before the signal. A refusal therefore means every other gate had passed.
- **Fill assumptions.** The upper bound assumes every stopped contract fills. The fill-checked column drops trims whose trimmed order could not fill in full. Trims were matched to their order by the order's requested count == `now`. The first-pass matching by time alone mis-paired same-second orders, and it was fixed before these numbers. Refusal depth is unknown, so refusals stay at the upper bound.
- **Proportional insurance.** This is an assumption carried over from the method, and it decides the "net" column through one market (ZEC 10-10). The hedge book there showed 100 at 0.61, so a 138 hedge might not have filled in full. The "no insurance credit" column is the answer if the assumption is wrong. It is also under $30.
- **Duplicate records.** One identical trim record was dropped. There is one refusal per market, so there was no double counting.
- **Week 2's lack of refusals.** The gate still fires in W2 (3 trims). Late-add signals are 0-2 a day all window, so the quiet is low traffic, not a lost gate.
- **What this window cannot show.** The cap's benefit, losses it cuts on doubled losing positions, was not exercised: 0 of 43 touched markets lost. The 7 bet-side losses in W1 were all within 1.0x, so the cap did not touch them. This read measures the cost side only.
