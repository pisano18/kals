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