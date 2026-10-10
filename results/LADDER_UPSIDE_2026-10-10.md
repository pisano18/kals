VERDICT.md was not written to disk because this harness does not let subagents write report files. The full text is below. Scripts and outputs are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\ladder_upside\` (`vchk_ladder.py/.out`, `vchk_race.py/.out`, `vchk_progs_all.py`, `vchk_pull.py`, `v_sub1_*.json`).

# Ladder upside: skeptic's verdict
Checked Thu 10-09, 10:10–11:40 PM ET. I only read data and sent GET requests; no orders were placed or changed. Both recorders were alive at the end (collector 43 MB, feeds 45 MB). Free disk was 16.3 GB, and none of my scripts went above 25 MB.

## Bottom line
1. **The ladder can't make meaningful money without new money.** At its current ~$80 it makes about $1.47 a day, which is 1.8% of its pot a day. The only lever is bigger bids, and the bot sets its bid size from its pot: pot ÷ $14 contracts per bid.
   - The trade record shows enough sellers. At 50 contracts a bid (about a $700 pot, so ~$620 of new money) it would have made **$10.60–11.10 a day over 10-01..10-08**, but only if every market still won.
   - That is still only ~1.5% of the pot a day. So the ladder is a place to put new money. It doesn't make the existing money earn more, and moving money over from the main bot gains nothing.
2. **The $10 is shaky, for three reasons.**
   - Nothing has ever run live above 5 contracts a bid.
   - Sellers are thinning:
     - Over 10-01..10-08, the second half made 14% less than the first.
     - The same tape method made about half as much in early October as in mid-September.
     - So by the time a 3-week step-up is finished, $10 could be $6–8.
   - One losing market at 50 a bid costs $49–98, which is 5–9 days of income. 131 wins in a row can't yet rule out losses being that common.
3. **Kalshi's market-maker rewards pay the ladder $0, and always will in its current form.** Confirmed below.
4. **The only idea with real size is a different bot: collecting the Coin Race reward with 1c bids on coins that have already lost.**
   - The pot is $20 per coin per 15 minutes. That is confirmed, and the repo's 10-02 "$0.20, dead" was a 100x misreading of the units.
   - Whether Kalshi would pay this account has never been tested.
   - The gross estimate rests on just 3 races.
   - Realistic range: anywhere from $0 to a few hundred dollars a day. Only a small live test can tell.

**How sure:**
- High: the reward terms, and that sellers exist beyond our 5-contract bids.
- Medium: the $/day at bigger sizes, before losses.
- Low: that bigger bids fill like that live; the ladder's true loss rate; whether Kalshi pays us rewards.

## What I re-checked

| Claim | My check (primary source) | Verdict |
|---|---|---|
| Ladder: 131 filled markets, 0 lost, +$14.87 on $723 (+2.06% per dollar) | Fresh Kalshi pull for subaccount 1: 131 settled, 0 lost, +$14.87 on $723.01, 738 contracts, 0 fees paid as taker | **Confirmed** |
| About $1.25–1.60 a day | By ET day 10-01..10-08: $2.52, 1.10, 1.18, 1.60, 1.60, 1.24, 1.31, 1.22. Average $1.47 a day, 12.5 filled markets a day. First 4 days $1.60, last 4 days $1.34 (−16%) | **Confirmed** |
| Sellers sell far past our 5 (median 124 below 98c; 66% of markets ≥50; 37% ≥200) | Raw trade tape, timed from when our bids actually went up. All 738 of our fills were found on the tape. In the 120 markets filled since 09-30, sellers sold below our price after we bid: median **139** per market; **86 of 120** markets had ≥50; **51 of 120** had ≥200 | **Confirmed** (a little better than claimed) |
| Bigger bids add contracts, not new markets | In 9,039 of 9,041 markets where we bid and got nothing, nobody sold below our price after we bid | **Confirmed** |
| $/day: $350 → $4.2–6.5; $700 → $8.1–11.8; $1,400 → $15.3–20.0 | One bid of each size at our real bid times, 10-01..10-08, +2c a contract if all win: 25 → $5.6–5.7; 50 → $10.6–11.1; 100 → $19.4–20.6. Last 4 days: $5.3, $9.8, $17.7 | **Confirmed**, upper half of their ranges. Losses not priced |
| Reward pot is $20 per coin per 15 min, not $0.20 | Kalshi's docs, verbatim: period_reward is "Total reward for the period in centi-cents". All 300,721 programs paged tonight: every one of 22,405 coin-race programs is 200000, which is $20.00. The smallest reward program ever is $1.00, the legal minimum in the filing. The repo's own lipscan.py, lipwatch.py and ordercli.py already divide by 10,000 | **Confirmed**. SI05 and SI21 should be reopened |
| Coin-race rewards are really paid out | 21,492 coin-race programs are marked paid out | **Confirmed**. Paid to someone; not shown to be this account |
| No reward program ever on our 12 up/down markets or the hourly ladders | Full paging: none that pays for resting bids, ever. Only volume programs on BTC/ETH 15-min, which ended Jan–May 2026 | **Confirmed** |
| This account has never been paid a reward (lifetime leftover cash $1.46) | Not re-run | **Unverified** (my subaccount-1 money matches theirs to the cent) |
| Coin-race reward bot grosses $8.55–13.41 a race, or $820–1,290 a day | Spot-checked one poll's arithmetic and it is right: 1,000 ÷ 6,440 = 15.5% share. I did not re-poll. The sample is 3 races in one Thursday-night hour | **Unverified as a daily figure**. Too few races to project to a day |

## The ladder: what $10 a day would take
- **Money:** about $620 of new money, for a $700 pot and 50 contracts a bid. That is your deposit to make.
- **Code:** none needed. The bot sizes up by itself at its next daily resize, once nothing is open.
- **Risk:** one losing market costs $49 (one bid filled) to $98 (two bids).
  - At 50 a bid, an average winning market earns ~$0.85.
  - So it breaks even at about 1 loss per 58–116 filled markets.
  - 131 clean markets is still consistent with about 2 losses per 100, which would lose money.
  - Proving it takes ~180–350 clean filled markets, which is 4–18 more days at today's pace.
- **Time:** the bar is already written: at least 7 days and 60 filled markets per size step. That is about 3 weeks to get to 50–100 a bid, while sellers keep thinning.

## The coin-race reward bot: what it would take
- **Cost side, from the raw tape:** 10-01..10-09, 846 races, 2,315 coin-windows where the coin lost.
  - Contracts sold into 1c bids in the last 6 minutes: typically 44, average 133 per losing coin.
  - 1,000 or more happened only 3.4% of the time.
  - If our stack had soaked up every one: ~$3.50 a race, ~$350 a day.
- **That cost is rising fast.** 8,600 contracts on 10-01 versus 58,100 on 10-09. So more people are selling into 1c bids, or other stacks are competing, or both. Tonight one losing XRP coin already had 5,440 contracts at 1c from others.
- **Upside:** 33 of 2,106 coins that traded at 2c or less in the last 6 minutes came back to win. That is 1.6%, and a 1c holder makes 99c on each.
- **Money at risk:** about $40 at a time. Worst case is $10 per losing coin if its 1,000 bid is fully sold into, or $40 a race.
- **Code:** a new bot, not built yet. It must be checked so it can't trade against the live coin-race bot, and it needs a day stop.
- **How a test would tell whether Kalshi pays us:**
  - Run it for about a day.
  - Kalshi marks coin-race rewards paid 16–40 hours after each window. So check for unexplained cash about 2 days later.
  - Subaccounts reconcile to $0.00 today, so even $1 would show.

## What cannot be known yet
- Whether sellers keep selling into 25–100 contract bids at 98c, and whether competitors step in just above us. Only live size steps answer this.
- The ladder's true loss rate.
- Whether Kalshi pays this account rewards, and whether a credit would land in a subaccount or the main account.
- How much of the coin-race pot we would get across a whole day, how fast competitors grow, and whether Kalshi ends the program. It can at any time; the filing runs to 2027-01-01.

## What I need from you
- Ladder: (a) leave it as is, at about $1.50 a day; (b) you add $270, giving 25 a bid, about $5 a day, with one bad market costing $25–49; or (c) you add $620, giving 50 a bid, about $10 a day, with one bad market costing $49–98. My pick is (b) for 7 days, then (c) only if it held.
- Coin-race reward bot (a new bot, not the ladder): OK to build it and run a 1-day live test, with about $40 at risk at a time and a $30 day stop, then check 2 days later whether Kalshi paid?

---

# Appendix A: incentive-program research (agent report, verbatim)

REPORT.md was not written: the harness blocks subagents from writing report files. The full report is below. Supporting data and scripts are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\ladder_upside\lip\`.

# Kalshi incentive programs vs the ladder

Everything here was read-only, pulled 2026-10-10 02:11–03:00Z (Thu 22:11–23:00 ET). I sent only GET requests, through `pintake._get` with PROD_ELECTIONS creds. The recorders were still alive at the end (`kalshi_collector.py` 45 MB, `crypto_feeds.py` 50 MB). Free disk is 16.3 GB, and none of my processes went above 60 MB.

Evidence classes used below:
- **FACT-API**: Kalshi's own records, pulled tonight.
- **FACT-DOC**: docs.kalshi.com, the help centre, or the CFTC filing text.
- **SUPPLY**: what the live book offered tonight. It is not a fill, not a loss rate and not a payment.
- **REPLAY**: the 09-25 money sweep's tape rebuild, which counts as a hypothesis.
- **REPORTED**: a secondary source.

## Answer first

1. **The ladder as it runs earns $0 from every incentive Kalshi has, and its current shape can never earn one.**
   - **No liquidity program on its markets, ever.** 0 of 300,711 programs (2025-09-18 to 2026-11-30) were on the 12 `KX*15M` up/down series or any hourly crypto ladder (`KXBTCD`, `KXETHD`, …). FACT-API.
   - **The volume program ending 10-13 changes nothing for us.**
     - `KXBTC15M`/`KXETH15M` had a volume program only from 2026-01-26 to 2026-05-12, at $10–20 per 15-minute market. FACT-API.
     - No volume program on any market has been listed since 2026-09-15. FACT-API.
     - Ladder fills at 98c would fall outside that program's 3–97c band anyway (band is REPORTED).
   - **Even if Kalshi added these series, a 30-second bid cannot earn.**
     - The $1.00 minimum payout per market per period needs at least 90 s of owning 100% of one side of a $20 pot.
     - In the last 30 s of a decided market the far side is empty, so that second is excluded and pays nobody.
   - **Tonight's test of the ladder's exact form came out $0.00 in 15 of 15 coin-race leg-windows.** That form is 5 contracts at 98c on the decided side, last 30 s. SUPPLY.

2. **This account has never been paid a meaningful incentive credit.** FACT-API (`recon.py`, `recon.out`).
   - For the whole account (main plus subaccounts 1/2/3), I took cash + open positions − net deposits − the P&L of all 1,978 settled markets. The leftover is **+$1.46 over the account's whole life**.
   - Subaccounts 1, 2 and 3 each reconcile to **$0.0000**.
   - The $1.46 sits in main and is about the size of the September interest credit (3.5% a year on cash, paid early October; HANDOFF expected about $1.20).
   - So every incentive credit ever received is at most $1.46, and most likely $0.

3. **The only crypto incentive money is the Coin Race (`KXCRYPTOLEAD15M`) liquidity program.**
   - It pays **$20.00 per leg per 15-minute window**: 5 legs × 96 windows = $9,600/day.
   - Rules: target 1,000 contracts a side, credit halves for each 1c below the reference price, prices on a plain 1c grid.
   - Every coin-race program that ended between 2026-08-29 and 2026-10-09 10:00Z is marked `paid_out`: 21,492 of 21,885 since 08-24.
   - The unpaid ones are 73 from the 08-24..29 launch plus the last ~16 h not yet processed.
   - $437,700 has been paid on this series to someone. FACT-API.

4. **The repo's 2026-10-02 kill of coin-race rewards rests on a 100x unit error.**
   - IDEA_LEDGER SJ36 (and the status edits on SI02/SI05/SI21) says the pot is "$0.20 per leg per 15 min", under the $1 floor, so "dead by rule".
   - The docs define `period_reward` as "Total reward for the period in centi-cents". Coin race shows 200000, which is **$20.00**.
   - **Independent check against the filing:**
     - The filing allows a period reward of no less than $1 and no more than $1,000 per calendar day.
     - Read as centi-cents, the smallest of all 278,351 liquidity programs ever listed is exactly $1.00, and the largest active one is $333 per calendar day. Both fit the filing.
     - Read the 10-02 way, every active program would sit below the legal $1 minimum.
   - SI05 and SI21 should go back to their 09-25 verdict of plausible-needs-data. FACT-DOC + FACT-API.

5. **The only incentive route with real size is a sibling bot, not the ladder: a 1c YES "filler" on the coin race's dead legs in the last 6 minutes (SI05/I05).**
   - It is new money (an exchange subsidy) and needs about $40 of capital at a time.
   - A 1,000-contract order can lose at most $10 per leg-window.
   - The book offered it **$8.55, $10.49 and $13.41 per race** tonight, over 3 races. If every race looked like these, that is about $820–1,290/day gross.
   - Two things cannot be known without a live probe: whether Kalshi pays this account for it, and what our own fills would cost.

## 1. Which markets are in the program right now (FACT-API: `progscan.py` → `progs_agg.json`, `active_rows.json`)

- **Whole exchange:** 300,711 programs listed. Active plus upcoming: 8,739 programs, all liquidity type, across 612 series, with **$340,243/day** in active pools.
- **No per-account cap:** no program carries `max_reward_per_account`.
- **15-minute families with programs now:**
  - KXCRYPTOLEAD15M: $20 per leg per window, target 1,000.
  - KXNATGAS15M, KXCOPPER15M, KXPLATINUM15M, KXPALLADIUM15M, KXEURUSD15M, KXGBPUSD15M, KXUSDJPY15M: $20–50 per window, target 300.
  - Gold, silver and WTI 15M programs stopped in September.
- **Other crypto programs:** only monthly and yearly range markets (KXBTCMAXMON and similar), with short ~$75 pools when each month lists. None on KX*15M up/down, KXBTCD/KXETHD hourly, or KXCRYPTOCOMP15M.
- **Fees:** KXCRYPTOLEAD15M, KXBTC15M and KXETH15M are all `quadratic`, multiplier 1, with no scheduled fee changes. Makers still pay $0.

## 2. Exact scoring (FACT-DOC: CFTC filing 2026-07-15, text in `C:\kals-repo\results\LIP_FILING_2026-07-15.txt`; help.kalshi.com article 13823851; API fields)

- **Who is eligible:** most regular U.S. members. Excluded: Kalshi affiliates and employees, introducing-broker/FCM customers, and non-U.S. users. The 07-15 amendment removed the exclusion of market-maker-agreement holders. The program runs to 2027-01-01, and Kalshi can end or change it at any time.
- **Snapshots:** one per second, taken at a random moment within the second.
- **Reference price, per side:** walk down from the best bid adding size. The reference is the first price level where cumulative size reaches Target/5.
- **Cutoff:** the walk stops at the level where cumulative size reaches Target. Orders beyond that score 0.
- **Score:** size × 0.5 for each tick below the reference, or full credit at or above it.
- **Exclusion:** a second counts only if BOTH sides hold at least Target in total across everyone.
- **"Two-sided" is a condition on the whole book, not on each participant.**
  - Your score for a second is your share of the yes side plus your share of the no side.
  - Payout = your share of all scores × the period reward × (counted seconds ÷ all seconds).
  - So an order on one side only can earn up to half the pot.
- **No max-spread or minimum-size rule.** Distance from the price is handled only through the reference price and the halving.
- **$1.00 floor per market per period** (not per day). A coin-race leg-window pays at most $20. Owning 100% of one side for t seconds pays $20 × t ÷ 1,800, so you need at least 90 s to reach $1.
- **How payment shows up:** there is no API line item and no endpoint. It appears only as unexplained cash. Coin-race programs are marked paid roughly 16–40 h after they end.

## 3. What the ladder would earn, and what a qualifying design looks like

`racepoll.py` read all 5 coin-race order books about every 8 s through 3 consecutive races (02:15–03:00Z). Race 1 was covered from minute 3 onward. It scored hypothetical orders with the filing's rules on the market's own 1c grid. Results are in `racepoll_an.out`. Dollars are per race with the $1 floor applied per leg:

| design | race 1 | race 2 | race 3 | $/day if every race looked like these | class |
|---|---|---|---|---|---|
| H3, the ladder's own form: 5 @ 98c on the decided side, last 30 s | $0.00 | $0.00 | $0.00 | **$0** | SUPPLY |
| H1, filler: 1,000 YES @ 1c on non-crossing legs, last 6 min | $8.55 | $10.49 | $13.41 | ~$820–1,290 gross | SUPPLY |
| H2, two-sided style: 200 NO at the NO reference, minutes 2–9 | $7.03 | $5.60 | $3.34 | ~$320–675 gross | SUPPLY |

"Gross" means the share of the pot if Kalshi pays as filed, before any fill costs.

**Why H1 earns:**
- In the last 3 minutes the 4 losing legs usually had zero YES bids. The incumbent's 1c stacks are pulled about 3 minutes before close, as the 09-25 sweep found.
- With that side empty, every second was excluded and paid nobody.
- A lone 1,000 at 1c fills the side, makes those seconds count, and takes 100% of that side's credit. Example: ETH in race 3 earned $3.89 of a possible $4.00 for 360 s.
- Posting would have crossed a 99c NO bid (and been rejected) in 0–13% of late polls.

**H1 filler (SI05/I05), priced honestly:**
- Loss is capped at $10 per leg-window. A fill on a leg that comes back to win is a 99c gain.
- REPLAY over 235 races (09-17..25): reward $9.2–9.4 per race; about 130 contracts per race actually sold into 1c bids, costing $1.3–1.6; net $7.6–8.0 per race, or **$730–760/day**. All 9 days were positive.
- Leaving 180 s before close instead: $3.9 per race, about $370/day.
- The refuter's range:
  - $0/day if Kalshi does not pay this account.
  - About $40/day if the incumbent (1,000–21,120-contract stacks at 1c) starts staying to the close.
  - Up to about $700/day.
- More capital does not add money, because the pot is fixed at $20. It has never been tested live.

**H2, two-sided quoting near the reference (SI21/I21):** this is the market making the project already killed.
- On the tape, resting quotes here lose to better-informed traders. Two-sided quoting lost 1.60c per contract in all 12 variants (MAKER_SIM, D17).
- Coin-race makers lost $20,101 over 7 days, 1.29c per contract.
- The only live maker test (NatGas, 09-07) lost about 40c per contract on about 60 contracts, a tiny sample.
- REPLAY: +$260–440/day if the incumbent's 120-contract re-quotes never hit our stale bid, but **−$77 to +$55/day if they do**. They did in 230 of 350 races.
- Realistic: $0–150/day on about $750 of capital, with daily swings of ±$650.
- Not recommended.

**Commodity/FX 15M rewards:** the pools exist, but the ladder's 60-print-average edge does not apply on those series. The 09-25 replay's filler controls on natgas and copper lost $0.67 and $1.45 per window.

## 4. Has the account earned any credit? (FACT-API: `recon.py`/`recon.out`, snapshot 10-10 02:18:03Z, zero resting orders on any subaccount)

| account | cash | open positions | money in | settled P&L (n markets) | leftover |
|---|---|---|---|---|---|
| main (0) | $1,065.80 | $0 | deposits net $584.46; transfers to subaccounts −$165.98 | +$645.86 (1,741) | **+$1.46** |
| sub 1 (ladder) | $79.87 | $0 | $65.00 | +$14.87 (131) | **$0.0000** |
| sub 2 | $83.25 | $0 | $50.98 | +$32.27 (84) | **$0.0000** |
| sub 3 (dip-seller) | $38.17 | $5.00 | $50.00 | −$6.83 (22) | **$0.0000** |

- The only times the account rested orders in reward-eligible markets:
  - The 09-07 commodity tests: 1–5.5% time on the book, predicted $0 under the floor.
  - The 09-26 Tencent order, 1,000 at 1c, which filled after 1 h 40 min.
- Because subaccounts reconcile to the cent, **a fresh subaccount is a clean detector**: any credit of $1 or more there is unambiguous.

## 5. Repo corrections (for the orchestrator; I did not edit anything)

- **The $0.20 figures are 100x too small.** Affected: `results/IDEA_LEDGER.md` line 29, U16, SI02, SI05, SI21, SJ36, and `idea_sweep_2026-10-02.json` id 20261002-36. Wrong figures: "$0.20 per leg per 15 min", "programme ~$2,800/day", "NFL pools $1.60/market/day". Correct: $20.00 per leg per window, about $340k/day exchange-wide. The 09-06 and 09-25 work had the unit right.
- **`research/lipscan.py` can never show the coin race.** It skips exchange_index 2 (crypto and commodities) by design. Its tick step is tapered, which is wrong for the coin race's plain 1c grid.

## 6. What cannot be known without money

- Whether Kalshi credits this account for a stack that sits only at 1c. The filed rules say it counts; it has never been observed.
- What our own fills cost. Flow that only takes, hitting a 1c bid in the last 3 minutes, is invisible on the tape because nobody has a bid there.
- How the incumbent responds once someone fills the gap.
- Whether Kalshi revokes rewards as "inconsistent with the purpose".
- Tonight is only 3 races on a Thursday night. The program can be ended at any time.

## 7. Cheapest decisive step (needs the operator's go: a new strategy family with real money)

This is the 09-25 sweep's probe, unchanged in shape:
- Use a NEW subaccount.
- In each race's last 360 s, on every leg whose YES side holds under 1,000 and whose best NO bid is 98c or lower, rest one post_only order for 1,000 YES at 1c with `self_trade_prevention_type=maker`. Cancel at close.
- Run 20 races, about 5 hours.
- **Risk:** at most $10 per leg-window, about $40 per race. Expected fill cost about $1–3 per race; expected credit if paid about $9–11 per race.
- **Readout:** the subaccount's leftover cash 24–48 h after the last race.
- **Pass bar, written before the first order:** a credit of at least $1.00 on at least 15 of 20 races where we sat alone for 90 s or more; fill cost at most 50% of the credit; zero self-matches.
- **Check first:** the coin-race taker bot's price ceiling must stay at 98c or below, because a 1c YES bid is the same as a 99c NO offer.

## Files (all in `...\scratchpad\final\ladder_upside\lip\`)

- `progscan.py`, `progscan.out`, `progs_agg.json`, `active_rows.json`, `crypto_rows.jsonl`: the full program pull
- `progan.py`, `progan.out`: programs by series and month
- `racepoll.py`, `racepoll.jsonl`, `racepoll.out`, `racepoll_an.py`, `racepoll_an.out`: the live coin-race books and scoring
- `recon.py`, `recon.out`, `recon.json`: the credit reconciliation

## Sources

- docs.kalshi.com/api-reference/incentive-programs/get-incentives.md: "period_reward … in centi-cents"; status and type parameters
- docs.kalshi.com/changelog: margin maker-volume (08-27) and taker-volume (09-10) program types; programs on hidden events excluded (07-22)
- docs.kalshi.com/llms.txt: no incentive-payout endpoint; /series/fee_changes exists
- help.kalshi.com/en/articles/13823851-liquidity-incentive-program: eligibility, $1–$1,000 per market per day, $1.00 minimum payout
- CFTC filing 2026-07-15 (Kalshi public-docs PDF "Liquidity Incentive Program - July 15, 2026 Update"), text at `C:\kals-repo\results\LIP_FILING_2026-07-15.txt`
- Volume program ending 2026-10-13: REPORTED (PredictionMarketPulse, 5 Oct 2026); not re-verified because kalshi.com notices returned 429
- Repo: `results/IDEA_LEDGER.md`, `results/idea_sweep_2026-09-25.json` (I05, I21), `results/overnight/INCENTIVE_FAMILIES.md`, `HANDOFF_ARCHIVE_2026-09.md`

---

# Appendix B: ladder capital ceiling (agent report, verbatim)

REPORT.md was not written: this harness doesn't allow subagents to write report .md files. The full report follows. Script outputs are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\ladder_upside\ceiling\` (`live_out.txt`, `calib_out.txt`, `q2_out.txt`, plus their JSONs). Fresh Kalshi pulls (GET only, subaccount 1, taken 10-10 about 02:10Z) are in `sub1_settlements_now.json` and `sub1_fills_now.json`.

# TASK B: the ladder's real capital ceiling

## Bottom line
- **Size is what limits the ladder, not sellers.** When a seller hits our 5-contract bid, they almost always take all 5 and keep selling below 98c.
- In the markets where our ladder got filled, the tape shows this much sold below 98c (capped at 200 per market):
  - median 124 contracts per market;
  - 66% of those markets had 50 or more;
  - 37% had 200 or more.
- Our own median fill was 5.
- More size gets more contracts from the same seller events. It does not add more events.
- Calibrated against live fills, the ladder as it is (auto-size, all 9 coins, at most 2 bids per market):

| pot | size per bid | $/day (low–high) | middle |
|---|---|---|---|
| $350 | 25 | $4.2–6.5 | about $5.3 (1.5% of pot a day) |
| $700 | 50 | $8.1–11.8 | about $9.9 (1.4%) |
| $1,400 | 100 | $15.3–20.0 | about $17.6 (1.3%) |

- Today it makes about $1.3/day on $80, which is 1.6% of the pot a day.
- **Nothing has run live above 5 contracts a bid.**
- Supply is falling: about 12–13% per 5 days on the tape and about 22% live.

## Live evidence (Kalshi subaccount 1, 09-28 to 10-09 about 17:15 ET)
- **Overall:** 131 filled markets, 0 lost, +$14.87 on $723.01 bet (+2.06%).
  - 738 contracts, all filled as maker; fees $0.0002 in total.
  - Every Kalshi fill matches an order in the bot's log, so the reconciliation is exact.
- **(1) Filled contracts vs bid size.**
  - 10-03 onward (size 5, at most 2 bids per market), 79 filled markets: 63 filled exactly one bid, 5 part of a bid, 10 hit the 2-bid cap, and 1 went over the cap (the known capfix bug).
  - 86 of 91 filled bids (94.5%) filled completely.
  - 09-30 to 10-03 (no cap): 56 of 56 filled bids filled completely.
  - The second bid usually goes unfilled because the seller's sweep is one event, over within about a second. Whatever size is resting at that moment is what we get.
- **(2) Queue ahead of us at 98c** (median 58 contracts; 3 in 4 bids had 232 or fewer ahead, 9 in 10 had 656 or fewer):

  | contracts ahead | bids | share filled |
  |---|---|---|
  | 0 | 1,558 | 6.6% |
  | 1–50 | 3,116 | 1.3% |
  | 50–200 | 2,534 | 0.59% |
  | 200–1,000 | 2,058 | 0.24% |
  | over 1,000 | 700 | 0.14% |

  - 112 of the 131 filled markets came from a bid with nobody ahead of it.
  - The share of our bids that were first in line fell from 20–22% (09-30, 10-01) to 12–15% (10-03 to 10-09).
  - When we were first in line, the fill rate fell from 10–13% to about 5%.
  - Size doesn't change our queue place. A 98.1c price would jump the 98.0c queue; the tape says that is worth about +7% at 50 contracts.
- **(3) The rule rested a bid but nothing filled** in 9,005 of 9,136 markets (98.6%).
  - Unfilled bids rested a median 24.7 s; 9,661 of 9,802 were cancelled at the close.
  - In 0 of those 9,005 markets did a seller sell below our price after we placed, so no seller ever traded past us.
  - Fill rate by coin: NEAR 4.1%, ZEC 2.6%, XRP 1.8%, BTC 0.5%, ETH 0.4%. NEAR, ZEC and XRP made 72% of the money.
  - Fills come a median 6.6 s before the close and 1.6 s after our first bid in that market. Sellers arrive the moment a market is decided, so speed matters.
- **(4) Money by ET day (size 5):**

  | ET day | 10-01 | 10-02 | 10-03 | 10-04 | 10-05 | 10-06 | 10-07 | 10-08 | 10-09 (partial) |
  |---|---|---|---|---|---|---|---|---|---|
  | $ | 2.52 | 1.10 | 1.18 | 1.60 | 1.60 | 1.24 | 1.31 | 1.22 | 0.90 |

  - The first 4 days averaged $1.60/day (80 contracts a day); the last 5 averaged $1.25/day (62 contracts a day).
  - Filled markets run about 11.6 a day.

## Reconciling with the design study (tape = supply evidence, never our loss rate)
I reused the verifier's independent fill model and data extracts. They count only volume sold strictly below our price, with no refill, and end 10-08 09:30Z.
- **Calibration on the same live-bid markets, size-5 period:**
  - Live 571 contracts in 97 markets.
  - Model at 0.3 s order timing: 442 contracts at size 5 (live is 1.29x) and 864 at size 10 (live is 0.66x).
  - Model at 1.0 s timing: live is 1.65x at size 5 and 0.85x at size 10.
  - Filled markets match well: 87 filled in both, 10 live only, 3 model only.
  - The live bot, with refills up to 2 bids, catches about two-thirds of what one resting 10-lot would.
- **Model $/day, all 9 coins at 98c:**

  | contracts per market | 25 | 50 | 100 | 200 |
  |---|---|---|---|---|
  | all 10 full days, 0.3 s | $5.67 | $10.52 | $19.07 | $32.17 |
  | last 5 full days (10-03 to 10-07), 0.3 s | $5.21 | $9.77 | $17.84 | $30.28 |
  | last 5 full days, 1.0 s | $4.19 | $8.11 | $15.25 | $26.54 |

  - The design study's numbers on the same tape (25 → $5.56, 50 → $10.29) reproduce within about 2%.
  - The design's $12.5–17/day needs coin weighting (most money on NEAR/ZEC/XRP, about +$4.8/day at the same capital per the verifier), the 98.1c/97.1c prices, and the older, richer days. It also needs a pot of about $700, because of the rule that at most 70% of the pot can be bid or held at once.
- **How the range is built:** low = the 1.0 s model at one bid of size S; high = 0.66 × the 0.3 s model at 2S. At size 5 this gives $0.87–1.44, and live actually made $1.39 over 10-03 to 10-07.

## Per pot: income, cost of one loss, live markets needed

| pot (new money) | $/day low–mid–high | one losing market (full 2 bids / 1 bid) | worst single close (70% rail) | break-even losses per 100 filled markets | clean filled markets needed (95%, 0 losses) |
|---|---|---|---|---|---|
| today $80, size 5 | about $1.3 (live) | $9.80 / $4.90 | $56 | 1.13 | about 264 |
| $350 (+$270), size 25 | 4.2 – 5.3 – 6.5 | $49 (about 9 days of income) / $24.50 | $245 | 0.94 | about 320 |
| $700 (+$620), size 50 | 8.1 – 9.9 – 11.8 | $98 (about 10 days) / $49 | $490 | 0.87 | about 340 |
| $1,400 (+$1,320), size 100 | 15.3 – 17.6 – 20.0 | $196 (about 11 days) / $98 | $980 | 0.78 | about 385 |

- **Today:** 0 losses in 131 filled markets. With 95% confidence the true rate is under 2.26 per 100, which is still above every break-even line above. The live record alone cannot yet show the ladder beats break-even, even at today's size.
- **Why it's believed safe today:** the price-index check found the rule wrong in 1 market out of 24,553, and a bid there would not have filled. That is evidence about the rule, not a loss rate from our fills.
- **Filled markets at any size count toward the loss evidence.** The set of filled markets doesn't change with size; only contracts per market do. A loss is priced as filling the full 2 bids.
- **Stage reads (the bar already written for the maker stage):**
  - each step needs at least 60 filled markets AND at least 7 ET days;
  - live contracts at least 70% of the tape model on the same closes and size;
  - 0 losses;
  - at least +1% of the pot a day: $3.50 at $350, $7 at $700, $14 at $1,400.
- **Stage timing:** 7 days per step is the binding limit, about 3 weeks for all three steps. That ends near 131 + 21 × 11.6 ≈ 375 clean filled markets, roughly what the $1,400 step needs.
- All three steps pass the money bar at the middle estimate. At $1,400 the low case is only 9% above it.

## What cannot be known yet
1. Whether sellers keep selling into a 25–100 contract bid at 98c. The tape shows what they sold against other people's bids. Only live size steps can measure this.
2. Whether competing bids at 98c and above keep growing.
3. The true loss rate, and whether losses come in clusters (several coins wrong at one close).
4. Whether supply keeps falling. At the recent pace, the estimates above could be 30–50% lower by the time the $1,400 step is read.

## Check-ins
- Every process stayed under about 60 MB. I streamed the 156 MB ladder log line by line and never touched `orderbook_delta`.
- Both recorders are alive: kalshi_collector (pid 2532788) and crypto_feeds (pid 105352).
- 16.4 GB free disk, 1.08 GB free RAM.