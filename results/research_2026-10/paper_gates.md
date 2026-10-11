# Paper arms vs twin vs live on shared closes -- gates, arms, fills (2026-09-22 06:21Z .. 2026-10-08 09:30Z)

**Paper arms cannot see adverse fills** (an offer that exists only because an informed seller dumped it, and that live takes but paper never sees), so paper understates live losses; paper is valid for DECISIONS and for comparing rule sets on markets both saw.

Read-only, written 2026-10-08 ~06:00Z (2:00 AM ET). Sources: every `results/pinrun-paper-*.jsonl` with records after 2026-09-22 06:21Z (283 logs; everything before is void), every `results/pinrun-live-*.jsonl` since then (28 logs, decisions only), live money from `results/kalshi_ledger.json` (main account, last settlement 2026-10-08T09:30:03.649227Z). Paper money = `settled.pnl_c`/100 per market (a hedged market has two rows, summed). Scripts in this session's scratchpad `final/`: `extract.py` (one streaming pass per log), `names.py`, `analysis.py`, `pg_report.py`; rows in `paper_gates.jsonl`.

**Method.** *Shared close* = a 15-minute close both compared logs were up for 60 s before (a record in the last 100..40 s before the close, or the bot's own close_summary for the 09-14 code which writes nothing between 10 min and 30 s out; the log must have begun 60 s before). *Refused the whole market* = the arm logged the gate and never bought that market in that close; *refused one leg* = it logged the gate but bought anyway (another level, or later). A market the arm never bought is credited to ONE gate: the refusal nearest the moment the comparison arm bought, and when several gates fired in the same second the rule gate (seller check, 97.8c cap, floor, dump guard...) over the plumbing one (attempts used up, no staged offer). `net` = comparison arm's money on those markets: **positive = the gate COST that much (missed wins), negative = it SAVED that much.** n is markets. Two identical paper copies drift $18-40 over a few days (PAPERS_1002_1003.md), so a difference under $40 is noise. UTC inside tables where marked; ET otherwise (EDT).

## 1. Arm inventory (every paper log with records after 09-22 06:21Z)

15-minute coin markets only (hourly KXBTCD in its own column). `alive` = records after 10-08 05:00Z. Flags differ from the twin (arm-live-twin = live argv of 09-29 minus --live: seller check on, 97.8c early cap, 0.90 floor, insurance at 0.40). The 09-22..09-24 sweeps (24-27 copies a batch, one flag each vs the live bot of that hour) are named by that flag; `live-copy` = no flag differed.

| arm | log(s) | code | start (ET) | end (ET) / alive | up closes | markets | net $ | bet $ | lost (worst) | hourly BTC n / $ | gates seen (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arm-afternoon | 20260924T035152Z | 252ed546fa68 | 09-23 23:51 | 09-26 23:51 | 288 | 224 | +242.97 | 8809 | 1 (BNB SEP261030-30 -46.38) | 0 / +0.00 | price_ceiling 583, confidence 465, jump_against 40, rebuy_band 25, dump_guard 12, early_cheap 6 |
| arm-lateadd-off? (20260925T0220) | 20260925T022032Z | ab19f2baf0a0 | 09-24 22:20 | 09-24 22:27 | 0 | 0 | +0.00 | 0 | 0 () | 0 / +0.00 |  |
| arm-early-off (20260925T0227) | 20260925T022729Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 8 | +7.94 | 283 | 0 () | 0 / +0.00 | confidence 24, price_ceiling 21, rebuy_band 2, jump_against 1, spike 1 |
| arm-brake3 (20260925T0227) | 20260925T022733Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 14 | +10.66 | 364 | 0 () | 1 / +0.02 | price_ceiling 54, confidence 42, rebuy_band 2, jump_against 2, early_cheap 1, dump_guard 1 |
| arm-lateadd-off? (20260925T0227) | 20260925T022736Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 14 | +18.04 | 503 | 0 () | 1 / +0.02 | price_ceiling 56, confidence 43, rebuy_band 3, jump_against 2, dump_guard 1, early_cheap 1 |
| arm-edge2c (20260925T0227) | 20260925T022739Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 8 | +7.87 | 225 | 0 () | 0 / +0.00 | confidence 42, rebuy_band 1, dump_guard 1, early_cheap 1, spike 1 |
| arm-btcd (20260925T0227) | 20260925T022743Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 14 | +10.92 | 361 | 0 () | 1 / +0.02 | price_ceiling 54, confidence 43, rebuy_band 2, jump_against 2, early_cheap 1, dump_guard 1 |
| arm-fresh500 (20260925T0227) | 20260925T022747Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 12 | +11.04 | 396 | 0 () | 0 / +0.00 | price_ceiling 57, confidence 42, fresh_level 10, rebuy_band 3, dump_guard 3, jump_against 2 |
| arm-toxic (20260925T0227) | 20260925T022751Z | ab19f2baf0a0 | 09-24 22:27 | 09-25 05:38 | 29 | 8 | +6.15 | 199 | 0 () | 0 / +0.00 | price_ceiling 57, confidence 43, toxic_fresh 8, early_cheap 3, jump_against 2, dump_guard 2 |
| arm-hourly-all (20260925T0306) | 20260925T030630Z | 59e9c213da0b | 09-24 23:06 | 09-25 05:38 | 26 | 14 | +10.88 | 364 | 0 () | 1 / +0.02 | price_ceiling 62, confidence 48, rebuy_band 2, jump_against 2, early_cheap 1, dump_guard 1 |
| arm-live-frozen | 20260925T063011Z | 52b3e5fb28f8 | 09-25 02:30 | 10-02 02:30 | 667 | 367 | +431.75 | 19993 | 7 (BTC SEP291330-30 -73.12; BTC SEP270000-00 -65.50; XRP SEP302000-00 -23.99) | 0 / +0.00 | price_ceiling 1144, confidence 1031, rebuy_band 106, jump_against 78, spike 52, dump_guard 15 |
| arm-early-off (20260925T0938) | 20260925T093824Z | 28f5e66b2169 | 09-25 05:38 | 09-25 08:25 | 11 | 4 | +4.77 | 188 | 0 () | 1 / +0.07 | confidence 13, price_ceiling 13 |
| arm-brake3 (20260925T0938) | 20260925T093827Z | 28f5e66b2169 | 09-25 05:38 | 09-25 08:25 | 11 | 6 | +4.81 | 219 | 0 () | 1 / +0.07 | confidence 23, price_ceiling 17, rebuy_band 1, jump_against 1 |
| arm-lateadd-off? (20260925T0938) | 20260925T093844Z | 28f5e66b2169 | 09-25 05:38 | 09-25 08:25 | 11 | 5 | +6.62 | 294 | 0 () | 1 / +0.07 | confidence 23, price_ceiling 19, rebuy_band 1, jump_against 1 |
| arm-edge2c (20260925T0938) | 20260925T093834Z | 28f5e66b2169 | 09-25 05:38 | 09-25 08:25 | 11 | 3 | +2.90 | 95 | 0 () | 1 / +0.08 | confidence 23, dump_guard 1, early_cheap 1, jump_against 1 |
| arm-fresh500 (20260925T0938) | 20260925T093841Z | 28f5e66b2169 | 09-25 05:38 | 09-25 08:25 | 11 | 5 | +2.55 | 129 | 0 () | 1 / +0.08 | confidence 23, price_ceiling 19, fresh_level 3, jump_against 2, dump_guard 1 |
| arm-hourly-all (20260925T0938) | 20260925T093848Z | 28f5e66b2169 | 09-25 05:38 | 09-25 08:25 | 11 | 5 | +5.02 | 239 | 0 () | 1 / +0.08 | confidence 26, price_ceiling 21, jump_against 1 |
| arm-early-off | 20260925T122541Z | f9548c5571ff | 09-25 08:25 | 10-02 08:25 | 667 | 199 | +363.39 | 15350 | 2 (BTC SEP270000-00 -127.52; XRP SEP301915-15 -1.66) | 18 / -1.46 | price_ceiling 681, confidence 632, rebuy_band 43, spike 37, jump_against 31, dump_guard 12 |
| arm-brake3 (20260925T1225) | 20260925T122545Z | f9548c5571ff | 09-25 08:25 | 09-27 23:35 | 253 | 158 | +95.77 | 7835 | 4 (BTC SEP270000-00 -63.85; BNB SEP261030-30 -41.12; ETH SEP270230-30 -36.46) | 9 / -0.91 | price_ceiling 532, confidence 415, jump_against 40, spike 22, early_cheap 18, rebuy_band 12 |
| arm-lateadd-off | 20260925T122549Z | f9548c5571ff | 09-25 08:25 | 10-02 08:25 | 667 | 365 | +333.74 | 17062 | 7 (BTC SEP270000-00 -63.71; BNB SEP261030-30 -41.12; BTC SEP291330-30 -23.20) | 25 / -0.92 | price_ceiling 1270, confidence 1147, jump_against 81, rebuy_band 61, spike 55, early_cheap 30 |
| arm-edge2c (20260925T1225) | 20260925T122552Z | f9548c5571ff | 09-25 08:25 | 09-27 23:35 | 253 | 92 | +64.80 | 4404 | 3 (BTC SEP270000-00 -65.55; BNB SEP261030-30 -41.12; ETH SEP270230-30 -10.69) | 7 / -0.98 | confidence 412, spike 23, early_cheap 21, rebuy_band 6, dump_guard 6, jump_against 6 |
| arm-btcd | 20260925T122556Z | f9548c5571ff | 09-25 08:25 | 10-01 04:29 | 556 | 315 | +268.57 | 15084 | 7 (BTC SEP270000-00 -63.96; BNB SEP261030-30 -41.12; BTC SEP291330-30 -22.65) | 19 / -0.47 | price_ceiling 1070, confidence 936, jump_against 66, spike 45, rebuy_band 31, early_cheap 25 |
| arm-fresh500 | 20260925T122559Z | f9548c5571ff | 09-25 08:25 | 10-02 08:26 | 667 | 286 | +381.33 | 15016 | 3 (BNB SEP261030-30 -47.11; ETH SEP270230-30 -36.46; XRP SEP301915-15 -1.90) | 21 / +1.03 | price_ceiling 1305, confidence 1161, fresh_level 208, jump_against 88, spike 57, rebuy_band 33 |
| arm-toxic (20260925T1226) | 20260925T122602Z | f9548c5571ff | 09-25 08:26 | 09-27 23:35 | 253 | 127 | +185.20 | 6568 | 1 (BNB SEP261030-30 -41.12) | 6 / +0.50 | price_ceiling 534, confidence 410, toxic_fresh 47, jump_against 42, spike 23, early_cheap 18 |
| arm-hourly-all | 20260925T122606Z | f9548c5571ff | 09-25 08:26 | 10-02 08:26 | 667 | 352 | +397.83 | 17648 | 5 (BTC SEP270000-00 -64.74; ETH SEP270230-30 -36.46; BTC SEP291330-30 -22.66) | 24 / -1.52 | price_ceiling 1419, confidence 1388, jump_against 83, spike 60, rebuy_band 37, early_cheap 31 |
| arm-early-full | 20260927T080949Z | 0f2c2a4bfa3f | 09-27 04:09 | 09-30 19:16 | 344 | 103 | +142.54 | 4911 | 2 (BNB SEP282000-00 -18.33; XRP SEP301915-15 -3.08) | 9 / +0.48 | price_ceiling 629, confidence 570, jump_against 31, toxic_fresh 31, spike 27, rebuy_band 14 |
| arm-0925 | 20260928T024717Z | 0f2c2a4bfa3f | 09-27 22:47 | 09-29 13:30 | 150 | 74 | +41.85 | 3018 | 1 (BTC SEP291330-30 -23.52) | 7 / +0.29 | confidence 268, price_ceiling 261, jump_against 13, rebuy_band 10, spike 9, early_cheap 5 |
| arm-0925-hedge20 | 20260928T024724Z | 0f2c2a4bfa3f | 09-27 22:47 | 09-29 13:30 | 150 | 74 | +46.17 | 3105 | 1 (BTC SEP291330-30 -23.52) | 6 / +0.27 | confidence 269, price_ceiling 257, spike 12, rebuy_band 11, jump_against 11, early_cheap 4 |
| arm-0925-nohedge | 20260928T024729Z | 0f2c2a4bfa3f | 09-27 22:47 | 09-29 13:30 | 150 | 75 | +14.43 | 3237 | 2 (BNB SEP282000-00 -27.19; BTC SEP291330-30 -26.66) | 7 / +0.30 | confidence 271, price_ceiling 258, jump_against 11, spike 9, rebuy_band 9, early_cheap 5 |
| arm-live-hedge20 | 20260928T024736Z | 0f2c2a4bfa3f | 09-27 22:47 | 09-30 19:15 | 269 | 77 | +36.95 | 2820 | 2 (XRP SEP301915-15 -50.88; BNB SEP282000-00 -0.19) | 8 / +0.48 | price_ceiling 512, confidence 480, spike 24, toxic_fresh 23, jump_against 23, early_cheap 9 |
| arm-live-nohedge | 20260928T024742Z | 0f2c2a4bfa3f | 09-27 22:47 | 09-30 19:15 | 269 | 82 | +8.80 | 2989 | 2 (XRP SEP301915-15 -79.32; BNB SEP282000-00 -1.50) | 5 / +0.30 | price_ceiling 513, confidence 479, jump_against 24, spike 22, toxic_fresh 19, rebuy_band 9 |
| arm-floor90 | 20260928T052115Z | 0f2c2a4bfa3f | 09-28 01:21 | 09-30 19:15 | 259 | 74 | +56.10 | 2365 | 2 (XRP SEP301915-15 -23.45; BNB SEP282000-00 -9.57) | 5 / +0.32 | price_ceiling 497, confidence 460, jump_against 25, spike 24, toxic_fresh 22, dump_guard 7 |
| arm-floor85 | 20260928T052121Z | 0f2c2a4bfa3f | 09-28 01:21 | 09-30 19:15 | 259 | 82 | +80.68 | 3010 | 2 (XRP SEP301915-15 -26.67; BNB SEP282000-00 -0.27) | 5 / +0.29 | price_ceiling 497, confidence 462, jump_against 24, spike 22, toxic_fresh 17, rebuy_band 9 |
| arm-floor80 | 20260928T052127Z | 0f2c2a4bfa3f | 09-28 01:21 | 09-30 19:15 | 259 | 77 | +68.07 | 2621 | 2 (XRP SEP301915-15 -16.67; BNB SEP282000-00 -0.27) | 5 / +0.29 | price_ceiling 494, confidence 463, jump_against 23, spike 21, toxic_fresh 18, rebuy_band 9 |
| arm-floor70 | 20260928T052133Z | 0f2c2a4bfa3f | 09-28 01:21 | 09-30 19:15 | 259 | 76 | +56.16 | 2268 | 2 (XRP SEP301915-15 -16.67; BNB SEP282000-00 -0.30) | 4 / +0.26 | price_ceiling 493, confidence 458, jump_against 25, spike 22, toxic_fresh 21, rebuy_band 7 |
| arm-floor90-full | 20260928T052139Z | 0f2c2a4bfa3f | 09-28 01:21 | 09-30 19:15 | 259 | 77 | +90.39 | 3064 | 2 (XRP SEP301915-15 -14.24; BNB SEP282000-00 -0.27) | 5 / +0.32 | price_ceiling 497, confidence 461, jump_against 24, toxic_fresh 22, spike 22, rebuy_band 14 |
| arm-live-twin | 20260929T185918Z, 20261006T185948Z | 7135aa467332/9afb6eca6a91 | 09-29 14:59 | ALIVE | 826 | 287 | +300.39 | 15017 | 8 (HYPE OCT050030-30 -70.88; SOL OCT022130-30 -45.34; XRP SEP301915-15 -24.30) | 14 / +0.84 | price_ceiling 1666, confidence 1512, toxic_fresh 143, early_dear 127, jump_against 103, spike 53 |
| arm-lockfix | 20261002T060334Z | bc5a3f43e2c5 | 10-02 02:03 | ALIVE | 590 | 214 | +215.41 | 10452 | 7 (HYPE OCT050030-30 -75.96; SOL OCT022130-30 -34.78; NEAR OCT061615-15 -21.06) | 10 / +0.67 | price_ceiling 1264, confidence 1104, toxic_fresh 124, early_dear 87, jump_against 77, spike 29 |
| arm-toxic15 | 20261003T050709Z | 9afb6eca6a91 | 10-03 01:07 | ALIVE | 498 | 167 | +164.55 | 7932 | 6 (HYPE OCT050030-30 -66.62; NEAR OCT061615-15 -20.59; BTC OCT030400-00 -13.37) | 9 / +0.62 | price_ceiling 1038, confidence 902, toxic_fresh 107, early_dear 77, jump_against 69, spike 30 |
| arm-toxic0 | 20261003T050810Z | 9afb6eca6a91 | 10-03 01:08 | ALIVE | 498 | 161 | +134.04 | 7353 | 6 (HYPE OCT050030-30 -75.75; NEAR OCT061615-15 -21.35; BTC OCT030400-00 -13.37) | 6 / +0.43 | price_ceiling 1047, confidence 898, toxic_fresh 127, early_dear 74, jump_against 71, spike 29 |
| arm-norebuy | 20261003T050909Z | 9afb6eca6a91 | 10-03 01:09 | ALIVE | 498 | 173 | +171.72 | 8320 | 6 (HYPE OCT050030-30 -75.30; NEAR OCT061615-15 -22.40; BTC OCT030400-00 -13.37) | 9 / +0.66 | price_ceiling 1041, confidence 903, toxic_fresh 100, early_dear 82, jump_against 70, spike 30 |
| arm-0925b | 20261004T003604Z | f9548c5571ff | 10-03 20:36 | ALIVE | 420 | 240 | +176.32 | 10524 | 6 (HYPE OCT050030-30 -70.72; HYPE OCT042015-15 -45.40; NEAR OCT061615-15 -22.30) | 20 / +0.95 | price_ceiling 858, confidence 745, jump_against 51, spike 26, rebuy_band 22, early_cheap 19 |
| arm-0914 | 20261004T031214Z | 06d396480a7a | 10-03 23:12 | ALIVE | 402 | 125 | -14.49 | 1878 | 4 (BTC OCT042115-15 -19.57; HYPE OCT050030-30 -19.44; HYPE OCT042015-15 -18.71) | 0 / +0.00 | price_ceiling 389, confidence 356, both_sides 112, rebuy_band 12, dump_guard 9 |

Sweep batches (09-19..09-25; each row one log; name = the flag that differed from live at launch):

| arm (flag @ start stamp) | code | start (ET) | end (ET) | up closes | markets | net $ | bet $ | lost (worst) |
|---|---|---|---|---|---|---|---|---|
| hedge_belief=0.9+hedge_max_tries=5+max_per_market=1+min_fill_frac=0.5 @20260919T122305Z | 438725fabfde | 09-19 08:23 | 09-22 08:23 | 24 | 4 | +2.24 | 78 | 0 () |
| hedge_belief=0.8+hedge_max_tries=5+max_per_market=1+min_fill_frac=0.5 @20260919T122309Z | 20b28c8fa0a4 | 09-19 08:23 | 09-22 08:23 | 24 | 4 | +2.22 | 76 | 0 () |
| hedge_belief=0.8+hedge_max_tries=5+max_per_market=1+min_fill_frac=0.5 @20260919T122314Z | 4b3abeba0cbc | 09-19 08:23 | 09-22 08:23 | 24 | 4 | +2.27 | 78 | 0 () |
| hedge_belief=0.8+hedge_max_tries=5+max_per_market=1+min_fill_frac=0.5 @20260919T122318Z | 1472f4e77e63 | 09-19 08:23 | 09-22 08:23 | 24 | 3 | +1.85 | 58 | 0 () |
| hedge_belief=0.8+hedge_max_tries=5+improve_scope=close+max_per_market=1+max_per_market_run=1+min_fill_frac=0.5+pick=first @20260919T122322Z | 100ca4058a18 | 09-19 08:23 | 09-22 08:23 | 24 | 4 | +2.27 | 78 | 0 () |
| pin=0.97 @20260922T062000Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 20 | +27.63 | 823 | 0 () |
| pin=0.975 @20260922T062003Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 21 | +19.91 | 756 | 0 () |
| pin=0.98 @20260922T062006Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 20 | +20.00 | 785 | 0 () |
| pin=0.985 @20260922T062008Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 17 | +17.72 | 719 | 0 () |
| pin=0.99 @20260922T062011Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 16 | +9.77 | 383 | 0 () |
| sigma_stress=0.2 @20260922T062014Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 20 | +10.72 | 891 | 2 (ZEC SEP220630-30 -40.90; BTC SEP220230-30 -3.93) |
| sigma_stress=0.4 @20260922T062017Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 23 | +43.29 | 809 | 2 (ZEC SEP220630-30 -5.22; BTC SEP220230-30 -4.32) |
| sigma_stress=0.6 @20260922T062020Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 24 | +38.06 | 880 | 1 (BTC SEP220230-30 -4.39) |
| sigma_stress=0.8 @20260922T062023Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 20 | +25.13 | 843 | 0 () |
| sigma_stress=1.25 @20260922T062026Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 2 | +0.74 | 30 | 0 () |
| sigma_stress=1.5 @20260922T062029Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=2.0 @20260922T062032Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:46 | 22 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.01 @20260922T062035Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:46 | 22 | 8 | +8.41 | 334 | 0 () |
| hedge_prop=True @20260922T062038Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 7 | +7.36 | 286 | 0 () |
| live-copy @20260922T062041Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 8 | +11.02 | 397 | 0 () |
| hedge_belief=0.6 @20260922T062044Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 6 | +5.67 | 228 | 0 () |
| hedge_slip=0.0 @20260922T062047Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 9 | +7.51 | 314 | 0 () |
| early_frac=0.5+early_tau_max=30 @20260922T062050Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 4 | +3.60 | 149 | 0 () |
| early_max_price=0.975 @20260922T062053Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:46 | 22 | 5 | +2.51 | 113 | 0 () |
| early_tau_max=60 @20260922T062056Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:46 | 22 | 21 | +18.60 | 730 | 0 () |
| bank_brake=3.0+bank_divisor=5.88 @20260922T062059Z | 6f6b1df38af6 | 09-22 02:20 | 09-22 07:45 | 22 | 8 | +6.16 | 276 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260922T062101Z | 6f6b1df38af6 | 09-22 02:21 | 09-22 07:45 | 22 | 7 | +8.42 | 331 | 0 () |
| live-copy @20260922T062104Z | 6f6b1df38af6 | 09-22 02:21 | 09-22 07:45 | 22 | 8 | +7.98 | 346 | 0 () |
| bank_brake=4.08+bank_divisor=7.9968+early_max_edge=3.0+extra_coin=0.0+hedge_belief=0.6+hedge_slip=0.0+late_extra=0.0+late_extra_tau=0+late_mult=1.0+late_tau=0 @20260922T062107Z | 6f6b1df38af6 | 09-22 02:21 | 09-22 16:00 | 55 | 26 | +28.63 | 919 | 0 () |
| hedge_belief=0.6+hedge_prop=True @20260922T062110Z | 6f6b1df38af6 | 09-22 02:21 | 09-22 16:00 | 55 | 24 | +28.78 | 953 | 0 () |
| pin=0.97 @20260922T114540Z | 6f6b1df38af6 | 09-22 07:45 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| pin=0.975 @20260922T114543Z | 6f6b1df38af6 | 09-22 07:45 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| pin=0.98 @20260922T114547Z | 6f6b1df38af6 | 09-22 07:45 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| pin=0.985 @20260922T114550Z | 6f6b1df38af6 | 09-22 07:45 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| pin=0.99 @20260922T114553Z | 6f6b1df38af6 | 09-22 07:45 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=0.2 @20260922T114557Z | 6f6b1df38af6 | 09-22 07:45 | 09-22 08:01 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=0.4 @20260922T114601Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=0.6 @20260922T114605Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=0.8 @20260922T114608Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=1.25 @20260922T114611Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=1.5 @20260922T114614Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=2.0 @20260922T114618Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:01 | 1 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.01 @20260922T114621Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| hedge_prop=True @20260922T114624Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| live-copy @20260922T114628Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.6 @20260922T114631Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| hedge_slip=0.0 @20260922T114634Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| early_frac=0.5+early_tau_max=30 @20260922T114638Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:01 | 1 | 0 | +0.00 | 0 | 0 () |
| early_frac=1.0 @20260922T114641Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| early_max_price=0.975 @20260922T114644Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| early_tau_max=60 @20260922T114647Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| bank_brake=3.0+bank_divisor=5.88 @20260922T114651Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260922T114654Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:00 | 1 | 0 | +0.00 | 0 | 0 () |
| live-copy @20260922T114657Z | 6f6b1df38af6 | 09-22 07:46 | 09-22 08:01 | 1 | 0 | +0.00 | 0 | 0 () |
| pin=0.97 @20260922T120102Z | 428d70ace217 | 09-22 08:01 | 09-22 16:01 | 32 | 34 | +31.61 | 1239 | 2 (BTC SEP221515-15 -14.73; DOGE SEP221600-00 -7.07) |
| pin=0.975 @20260922T120105Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 33 | +21.63 | 1115 | 2 (BTC SEP221515-15 -16.09; DOGE SEP221600-00 -2.24) |
| pin=0.98 @20260922T120110Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 30 | +20.04 | 1090 | 2 (BTC SEP221515-15 -16.34; DOGE SEP221600-00 -1.94) |
| pin=0.985 @20260922T120112Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 31 | +41.63 | 1114 | 0 () |
| pin=0.99 @20260922T120116Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 31 | +35.91 | 999 | 0 () |
| sigma_stress=0.2 @20260922T120119Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 29 | -14.94 | 1132 | 4 (DOGE SEP221600-00 -56.92; BTC SEP220815-15 -8.40) |
| sigma_stress=0.4 @20260922T120122Z | 428d70ace217 | 09-22 08:01 | 09-22 16:01 | 32 | 38 | -32.63 | 1291 | 4 (DOGE SEP221600-00 -56.92; ZEC SEP221500-00 -28.35) |
| sigma_stress=0.6 @20260922T120126Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 40 | -31.43 | 1062 | 4 (DOGE SEP221600-00 -56.92; BTC SEP220815-15 -11.43) |
| sigma_stress=0.8 @20260922T120129Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 31 | -15.70 | 1348 | 2 (DOGE SEP221600-00 -46.87; BTC SEP221515-15 -16.16) |
| sigma_stress=1.25 @20260922T120133Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 10 | +10.69 | 443 | 0 () |
| sigma_stress=1.5 @20260922T120136Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 6 | +4.60 | 160 | 0 () |
| sigma_stress=2.0 @20260922T120140Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 3 | +2.97 | 96 | 0 () |
| hedge_belief=0.01 @20260922T120143Z | 428d70ace217 | 09-22 08:01 | 09-22 16:01 | 32 | 20 | +30.98 | 810 | 0 () |
| hedge_prop=True @20260922T120146Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 23 | +25.53 | 714 | 0 () |
| live-copy @20260922T120150Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 22 | +23.79 | 656 | 0 () |
| hedge_belief=0.6 @20260922T120153Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 21 | +27.38 | 668 | 0 () |
| hedge_slip=0.0 @20260922T120157Z | 428d70ace217 | 09-22 08:01 | 09-22 16:00 | 32 | 21 | +27.26 | 693 | 0 () |
| early_frac=0.5+early_tau_max=30 @20260922T120200Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 11 | +11.39 | 411 | 0 () |
| early_frac=1.0 @20260922T120203Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 20 | +37.61 | 1006 | 0 () |
| early_max_price=0.975 @20260922T120207Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 14 | +23.80 | 620 | 0 () |
| early_tau_max=60 @20260922T120210Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 32 | -0.19 | 1082 | 2 (BNB SEP221230-30 -17.64; DOGE SEP221430-30 -14.62) |
| bank_brake=3.0+bank_divisor=5.88 @20260922T120213Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 19 | +22.01 | 659 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260922T120216Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 20 | +31.26 | 746 | 0 () |
| live-copy @20260922T120220Z | 428d70ace217 | 09-22 08:02 | 09-22 16:00 | 32 | 20 | +27.59 | 672 | 0 () |
| pin=0.97 @20260922T200519Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 45 | +15.44 | 1754 | 1 (DOGE SEP222245-45 -70.34) |
| pin=0.975 @20260922T200522Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 42 | +41.52 | 1532 | 1 (DOGE SEP222245-45 -22.92) |
| pin=0.98 @20260922T200526Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 41 | +28.71 | 1242 | 1 (DOGE SEP222245-45 -22.97) |
| pin=0.985 @20260922T200528Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 38 | +36.85 | 1456 | 1 (DOGE SEP222245-45 -23.85) |
| pin=0.99 @20260922T200532Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 35 | +23.12 | 1270 | 1 (DOGE SEP222245-45 -23.90) |
| sigma_stress=0.2 @20260922T200535Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 43 | +17.40 | 1272 | 2 (BTC SEP221730-30 -45.63; NEAR SEP222015-15 -3.58) |
| sigma_stress=0.4 @20260922T200538Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 48 | +13.92 | 1479 | 1 (BTC SEP221730-30 -50.69) |
| sigma_stress=0.6 @20260922T200541Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 49 | -47.57 | 1707 | 2 (BTC SEP221730-30 -51.60; DOGE SEP222245-45 -46.99) |
| sigma_stress=0.8 @20260922T200545Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 40 | +49.16 | 1432 | 1 (DOGE SEP222245-45 -6.45) |
| sigma_stress=1.25 @20260922T200548Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 14 | +20.30 | 600 | 0 () |
| sigma_stress=1.5 @20260922T200551Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 6 | +13.40 | 342 | 0 () |
| sigma_stress=2.0 @20260922T200554Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 3 | +2.95 | 106 | 0 () |
| hedge_belief=0.01 @20260922T200558Z | 6516ea937f09 | 09-22 16:05 | 09-23 03:30 | 46 | 31 | +37.29 | 967 | 1 (DOGE SEP222245-45 -0.97) |
| hedge_prop=True @20260922T200602Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:30 | 46 | 31 | -22.21 | 1005 | 1 (DOGE SEP222245-45 -57.62) |
| live-copy @20260922T200605Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 28 | -20.44 | 1046 | 1 (DOGE SEP222245-45 -55.71) |
| hedge_belief=0.6 @20260922T200608Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 31 | -38.12 | 1198 | 1 (DOGE SEP222245-45 -76.43) |
| hedge_slip=0.0 @20260922T200612Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 29 | -26.02 | 1019 | 1 (DOGE SEP222245-45 -59.77) |
| early_frac=0.5+early_tau_max=30 @20260922T200615Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 18 | -36.93 | 704 | 1 (DOGE SEP222245-45 -58.44) |
| early_frac=1.0 @20260922T200618Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 30 | -0.35 | 1575 | 1 (DOGE SEP222245-45 -57.79) |
| early_max_price=0.975 @20260922T200621Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 22 | +21.10 | 730 | 1 (DOGE SEP222245-45 -9.25) |
| early_tau_max=60 @20260922T200624Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 60 | +0.59 | 1646 | 1 (DOGE SEP222245-45 -55.58) |
| bank_brake=3.0+bank_divisor=5.88 @20260922T200628Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 29 | +31.07 | 1063 | 1 (DOGE SEP222245-45 -9.25) |
| bank_brake=6.0+bank_divisor=11.76 @20260922T200631Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 31 | -19.49 | 1136 | 1 (DOGE SEP222245-45 -57.51) |
| attempts_on_send=True @20260922T200634Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 30 | +35.90 | 956 | 1 (DOGE SEP222245-45 -0.91) |
| live-copy @20260922T200637Z | 6516ea937f09 | 09-22 16:06 | 09-23 03:31 | 46 | 32 | -30.30 | 1307 | 1 (DOGE SEP222245-45 -75.95) |
| pin=0.97 @20260923T073035Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 76 | +35.31 | 2535 | 2 (BTC SEP232030-30 -57.27; HYPE SEP231645-45 -5.91) |
| pin=0.975 @20260923T073037Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 76 | +14.23 | 2504 | 2 (BTC SEP232030-30 -57.27; HYPE SEP231645-45 -21.11) |
| pin=0.98 @20260923T073041Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 76 | +1.68 | 2259 | 2 (BTC SEP232030-30 -57.27; HYPE SEP231645-45 -21.11) |
| pin=0.985 @20260923T073044Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 72 | +25.65 | 2406 | 2 (BTC SEP232030-30 -58.12; HYPE SEP231645-45 -2.60) |
| pin=0.99 @20260923T073047Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 67 | +19.67 | 2241 | 2 (BTC SEP232030-30 -57.27; HYPE SEP231645-45 -2.52) |
| sigma_stress=0.2 @20260923T073051Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 75 | +157.40 | 2359 | 1 (ZEC SEP230400-00 -51.62) |
| sigma_stress=0.4 @20260923T073054Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 84 | +91.86 | 2870 | 2 (ZEC SEP230400-00 -49.41; BTC SEP232030-30 -45.11) |
| sigma_stress=0.6 @20260923T073058Z | f19c98a9dd0a | 09-23 03:30 | 09-23 21:15 | 71 | 91 | +68.07 | 2876 | 2 (BTC SEP232030-30 -50.15; HYPE SEP231645-45 -3.51) |
| sigma_stress=0.8 @20260923T073101Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:15 | 71 | 74 | +6.26 | 2378 | 2 (BTC SEP232030-30 -57.27; HYPE SEP231645-45 -20.44) |
| sigma_stress=1.25 @20260923T073104Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:15 | 71 | 14 | -51.43 | 486 | 1 (BTC SEP232030-30 -59.77) |
| sigma_stress=1.5 @20260923T073107Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:15 | 71 | 3 | +4.13 | 115 | 0 () |
| sigma_stress=2.0 @20260923T073111Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.01 @20260923T073114Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 44 | -25.22 | 1696 | 1 (BTC SEP232030-30 -74.67) |
| hedge_prop=True @20260923T073117Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 45 | -15.04 | 1708 | 1 (BTC SEP232030-30 -58.12) |
| live-copy @20260923T073120Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 48 | -13.36 | 1656 | 1 (BTC SEP232030-30 -58.12) |
| hedge_belief=0.6 @20260923T073124Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 44 | -5.00 | 1584 | 1 (BTC SEP232030-30 -46.16) |
| hedge_slip=0.0 @20260923T073127Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 48 | -4.92 | 1866 | 1 (BTC SEP232030-30 -58.12) |
| early_frac=0.5+early_tau_max=30 @20260923T073130Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 29 | -19.03 | 1319 | 1 (BTC SEP232030-30 -57.27) |
| early_frac=1.0 @20260923T073133Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 42 | -8.94 | 1856 | 1 (BTC SEP232030-30 -57.27) |
| early_max_price=0.975 @20260923T073137Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 34 | -9.05 | 1491 | 1 (BTC SEP232030-30 -57.27) |
| early_tau_max=60 @20260923T073141Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 71 | -24.72 | 2140 | 2 (BTC SEP232030-30 -57.27; HYPE SEP230900-00 -22.31) |
| bank_brake=3.0+bank_divisor=5.88 @20260923T073144Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 44 | -16.00 | 1639 | 1 (BTC SEP232030-30 -57.27) |
| bank_brake=6.0+bank_divisor=11.76 @20260923T073147Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 44 | -68.89 | 1632 | 2 (BTC SEP232030-30 -58.12; HYPE SEP231645-45 -49.34) |
| attempts_on_send=True @20260923T073150Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 46 | -69.11 | 1858 | 2 (BTC SEP232030-30 -58.12; HYPE SEP231645-45 -55.06) |
| doubt_mult=1.5 @20260923T073153Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 44 | -3.10 | 1979 | 1 (BTC SEP232030-30 -57.27) |
| doubt_mult=1.25 @20260923T073156Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 43 | +0.46 | 1980 | 1 (BTC SEP232030-30 -57.27) |
| live-copy @20260923T073159Z | f19c98a9dd0a | 09-23 03:31 | 09-23 21:16 | 71 | 44 | -13.04 | 1686 | 1 (BTC SEP232030-30 -57.27) |
| pin=0.97 @20260924T011528Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 6 | +7.84 | 197 | 0 () |
| pin=0.975 @20260924T011531Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 7 | +12.56 | 287 | 0 () |
| pin=0.98 @20260924T011535Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 7 | +10.69 | 240 | 0 () |
| pin=0.985 @20260924T011538Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 8 | +12.00 | 273 | 0 () |
| pin=0.99 @20260924T011541Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 6 | +6.24 | 198 | 0 () |
| sigma_stress=0.2 @20260924T011544Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 4 | +3.83 | 90 | 0 () |
| sigma_stress=0.4 @20260924T011548Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:30 | 5 | 5 | +6.60 | 154 | 0 () |
| sigma_stress=0.6 @20260924T011551Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:31 | 5 | 6 | +8.10 | 213 | 0 () |
| sigma_stress=0.8 @20260924T011554Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:31 | 5 | 8 | +11.96 | 332 | 0 () |
| sigma_stress=1.25 @20260924T011557Z | 0a5a83fe6ce6 | 09-23 21:15 | 09-23 22:31 | 5 | 2 | +0.77 | 34 | 0 () |
| sigma_stress=1.5 @20260924T011601Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 1 | +6.34 | 70 | 0 () |
| sigma_stress=2.0 @20260924T011604Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.01 @20260924T011607Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 6 | +6.15 | 173 | 0 () |
| hedge_prop=True @20260924T011611Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 6 | +12.16 | 297 | 0 () |
| live-copy @20260924T011614Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 7 | +12.05 | 276 | 0 () |
| hedge_belief=0.6 @20260924T011618Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 6 | +12.20 | 234 | 0 () |
| hedge_slip=0.0 @20260924T011621Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 6 | +10.70 | 178 | 0 () |
| early_frac=0.5+early_tau_max=30 @20260924T011625Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 3 | +7.88 | 168 | 0 () |
| early_frac=1.0 @20260924T011628Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 4 | +11.15 | 228 | 0 () |
| early_max_price=0.975 @20260924T011632Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 4 | +5.77 | 201 | 0 () |
| early_tau_max=60 @20260924T011635Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 9 | +10.22 | 319 | 0 () |
| bank_brake=3.0+bank_divisor=5.88 @20260924T011639Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 7 | +11.47 | 242 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260924T011642Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 6 | +16.35 | 242 | 0 () |
| attempts_on_send=True @20260924T011645Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 7 | +10.87 | 267 | 0 () |
| doubt_mult=1.5 @20260924T011649Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:31 | 5 | 6 | +12.98 | 309 | 0 () |
| doubt_mult=1.25 @20260924T011652Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:32 | 5 | 7 | +15.05 | 306 | 0 () |
| live-copy @20260924T011655Z | 0a5a83fe6ce6 | 09-23 21:16 | 09-23 22:32 | 5 | 5 | +11.66 | 203 | 0 () |
| pin=0.97 @20260924T023041Z | 3f37c9c0d7b6 | 09-23 22:30 | 09-23 23:35 | 4 | 4 | +3.95 | 149 | 0 () |
| pin=0.975 @20260924T023044Z | 3f37c9c0d7b6 | 09-23 22:30 | 09-23 23:35 | 4 | 4 | +3.27 | 130 | 0 () |
| pin=0.98 @20260924T023048Z | 3f37c9c0d7b6 | 09-23 22:30 | 09-23 23:35 | 4 | 4 | +3.12 | 123 | 0 () |
| pin=0.985 @20260924T023051Z | 3f37c9c0d7b6 | 09-23 22:30 | 09-23 23:35 | 4 | 4 | +3.32 | 133 | 0 () |
| pin=0.99 @20260924T023054Z | 3f37c9c0d7b6 | 09-23 22:30 | 09-23 23:36 | 4 | 2 | +1.70 | 58 | 0 () |
| sigma_stress=0.2 @20260924T023057Z | 3f37c9c0d7b6 | 09-23 22:30 | 09-23 23:36 | 4 | 3 | +3.94 | 123 | 0 () |
| sigma_stress=0.4 @20260924T023101Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 3 | +4.27 | 123 | 0 () |
| sigma_stress=0.6 @20260924T023105Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 3 | +2.12 | 56 | 0 () |
| sigma_stress=0.8 @20260924T023108Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 4 | +3.19 | 126 | 0 () |
| sigma_stress=1.25 @20260924T023112Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=1.5 @20260924T023116Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 0 | +0.00 | 0 | 0 () |
| sigma_stress=2.0 @20260924T023119Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.01 @20260924T023122Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 2 | +1.38 | 58 | 0 () |
| hedge_prop=True @20260924T023125Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 2 | +1.13 | 53 | 0 () |
| live-copy @20260924T023129Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 2 | +1.26 | 59 | 0 () |
| hedge_belief=0.6 @20260924T023132Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 2 | +1.26 | 59 | 0 () |
| hedge_slip=0.0 @20260924T023136Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 2 | +1.13 | 53 | 0 () |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 @20260924T023139Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 1 | +0.43 | 22 | 0 () |
| early_frac=1.0 @20260924T023142Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 2 | +2.25 | 111 | 0 () |
| early_max_price=0.975 @20260924T023145Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 1 | +0.78 | 33 | 0 () |
| early_tau_max=60 @20260924T023149Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:36 | 4 | 4 | +1.97 | 80 | 0 () |
| bank_brake=3.0+bank_divisor=5.88 @20260924T023152Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:37 | 4 | 2 | +1.13 | 53 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260924T023156Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:37 | 4 | 2 | +1.11 | 52 | 0 () |
| attempts_on_send=True @20260924T023159Z | 3f37c9c0d7b6 | 09-23 22:31 | 09-23 23:37 | 4 | 2 | +1.26 | 59 | 0 () |
| doubt_mult=1.5 @20260924T023203Z | 3f37c9c0d7b6 | 09-23 22:32 | 09-23 23:37 | 4 | 2 | +1.26 | 59 | 0 () |
| doubt_mult=1.25 @20260924T023206Z | 3f37c9c0d7b6 | 09-23 22:32 | 09-23 23:37 | 4 | 2 | +1.26 | 59 | 0 () |
| live-copy @20260924T023210Z | 3f37c9c0d7b6 | 09-23 22:32 | 09-23 23:37 | 4 | 2 | +1.26 | 59 | 0 () |
| live-copy @20260924T030010Z | 04f8a96e34c7 | 09-23 23:00 | 09-23 23:35 | 2 | 0 | +0.00 | 0 | 0 () |
| pin=0.97 @20260924T033553Z | 04f8a96e34c7 | 09-23 23:35 | 09-24 00:26 | 3 | 5 | +6.35 | 195 | 0 () |
| pin=0.975 @20260924T033556Z | 04f8a96e34c7 | 09-23 23:35 | 09-24 00:26 | 3 | 4 | +6.40 | 203 | 0 () |
| pin=0.98 @20260924T033600Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:26 | 3 | 5 | +3.94 | 191 | 0 () |
| pin=0.985 @20260924T033603Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:26 | 3 | 5 | +3.43 | 123 | 0 () |
| pin=0.99 @20260924T033607Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 4 | +3.97 | 168 | 0 () |
| sigma_stress=0.2 @20260924T033610Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 4 | -5.00 | 217 | 1 (HYPE SEP232345-45 -14.56) |
| sigma_stress=0.4 @20260924T033614Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 5 | +20.29 | 290 | 0 () |
| sigma_stress=0.6 @20260924T033617Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 5 | +9.00 | 178 | 0 () |
| sigma_stress=0.8 @20260924T033620Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 6 | +6.32 | 182 | 0 () |
| sigma_stress=1.25 @20260924T033624Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 4 | +4.05 | 201 | 0 () |
| sigma_stress=1.5 @20260924T033627Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 2 | +1.44 | 76 | 0 () |
| sigma_stress=2.0 @20260924T033630Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:20 | 3 | 0 | +0.00 | 0 | 0 () |
| hedge_belief=0.01 @20260924T033634Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| hedge_prop=True @20260924T033637Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| live-copy @20260924T033641Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| hedge_belief=0.6 @20260924T033644Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| hedge_slip=0.0 @20260924T033647Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.52 | 228 | 0 () |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 @20260924T033651Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| early_frac=1.0 @20260924T033654Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.38 | 228 | 0 () |
| early_max_price=0.975 @20260924T033658Z | 04f8a96e34c7 | 09-23 23:36 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| early_tau_max=60 @20260924T033701Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:27 | 3 | 3 | +5.52 | 228 | 0 () |
| bank_brake=3.0+bank_divisor=5.88 @20260924T033705Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:27 | 3 | 3 | +3.86 | 198 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260924T033708Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:27 | 3 | 3 | +5.52 | 228 | 0 () |
| attempts_on_send=True @20260924T033711Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:27 | 3 | 3 | +5.00 | 231 | 0 () |
| doubt_mult=1.5 @20260924T033715Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:27 | 3 | 3 | +5.52 | 228 | 0 () |
| doubt_mult=1.25 @20260924T033718Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:27 | 3 | 3 | +5.52 | 228 | 0 () |
| live-copy @20260924T033721Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:28 | 3 | 3 | +5.00 | 231 | 0 () |
| live-copy @20260924T033726Z | 04f8a96e34c7 | 09-23 23:37 | 09-24 00:28 | 3 | 3 | +4.36 | 229 | 0 () |
| bank_divisor=7.8+price_ceiling=0.975 @20260924T035653Z | 04f8a96e34c7 | 09-23 23:56 | 09-23 23:58 | 1 | 0 | +0.00 | 0 | 0 () |
| pin=0.97 @20260924T042657Z | 11ec840dce4f | 09-24 00:26 | 09-24 01:12 | 3 | 3 | +5.50 | 152 | 0 () |
| pin=0.975 @20260924T042700Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:13 | 3 | 3 | +5.50 | 152 | 0 () |
| pin=0.98 @20260924T042705Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:13 | 3 | 3 | +4.72 | 153 | 0 () |
| pin=0.985 @20260924T042708Z | 11ec840dce4f | 09-24 00:27 | 09-24 13:10 | 51 | 50 | +39.39 | 1623 | 1 (NEAR SEP240245-45 -0.47) |
| pin=0.99 @20260924T042711Z | 11ec840dce4f | 09-24 00:27 | 09-24 13:10 | 51 | 45 | +22.12 | 1623 | 2 (DOGE SEP240630-30 -20.60; NEAR SEP240245-45 -5.16) |
| hedge_belief=0.01 @20260924T042715Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:12 | 3 | 3 | +3.95 | 154 | 0 () |
| hedge_prop=True @20260924T042718Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:12 | 3 | 3 | +2.71 | 122 | 0 () |
| live-copy @20260924T042722Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:12 | 3 | 3 | +2.91 | 122 | 0 () |
| hedge_belief=0.6 @20260924T042725Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:12 | 3 | 3 | +3.95 | 154 | 0 () |
| hedge_slip=0.0 @20260924T042728Z | 11ec840dce4f | 09-24 00:27 | 09-24 05:14 | 20 | 11 | +11.95 | 471 | 0 () |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 @20260924T042732Z | 11ec840dce4f | 09-24 00:27 | 09-24 22:27 | 88 | 28 | +64.32 | 1652 | 0 () |
| early_frac=1.0 @20260924T042737Z | 11ec840dce4f | 09-24 00:27 | 09-24 13:10 | 51 | 36 | +43.15 | 1732 | 0 () |
| early_max_price=0.975 @20260924T042740Z | 11ec840dce4f | 09-24 00:27 | 09-24 13:11 | 51 | 22 | +31.01 | 987 | 0 () |
| early_tau_max=60 @20260924T042744Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:13 | 4 | 4 | +3.20 | 148 | 0 () |
| bank_brake=3.0+bank_divisor=5.88 @20260924T042747Z | 11ec840dce4f | 09-24 00:27 | 09-24 22:27 | 88 | 73 | +74.50 | 2342 | 0 () |
| bank_brake=6.0+bank_divisor=11.76 @20260924T042752Z | 11ec840dce4f | 09-24 00:27 | 09-24 01:13 | 4 | 3 | +3.95 | 154 | 0 () |
| attempts_on_send=True @20260924T042756Z | 11ec840dce4f | 09-24 00:27 | 09-24 13:11 | 51 | 39 | +32.58 | 1204 | 0 () |
| doubt_mult=1.5 @20260924T042759Z | 11ec840dce4f | 09-24 00:27 | 09-24 13:11 | 51 | 37 | +48.20 | 1536 | 0 () |
| doubt_mult=1.25 @20260924T042803Z | 11ec840dce4f | 09-24 00:28 | 09-24 13:11 | 51 | 41 | +45.11 | 1487 | 0 () |
| live-copy @20260924T042806Z | 11ec840dce4f | 09-24 00:28 | 09-24 22:27 | 88 | 71 | +73.83 | 2281 | 0 () |
| live-copy @20260924T042812Z | 11ec840dce4f | 09-24 00:28 | 09-24 01:13 | 3 | 3 | +3.95 | 154 | 0 () |
| edge_floor=0.02 @20260924T051727Z | ecd95bda7371 | 09-24 01:17 | 09-24 22:27 | 84 | 39 | +52.64 | 1284 | 0 () |
| live-copy @20260924T075757Z | 3bdcc10dfcf4 | 09-24 03:57 | 09-24 22:27 | 74 | 65 | +60.77 | 1642 | 0 () |
| live-copy @20260924T080823Z | f30716881ed7 | 09-24 04:08 | 09-24 22:27 | 73 | 51 | +47.38 | 1293 | 0 () |
| live-copy @20260925T035740Z | 8bbf33e6e6ae | 09-24 23:57 | 09-25 02:28 | 10 | 7 | +7.44 | 229 | 0 () |

## 2. Gate by gate: what each refusal would have won or lost (shared closes)

Whole-market refusals credited to one gate (see Method); `leg` rows = the arm bought the market anyway, delta = comparison arm's money minus the refusing arm's on those markets (positive = the gate cost the refusing arm). Pairs read `X refused -> Y bought`.

| gate | X refused -> Y bought | window (ET days / shared closes) | whole-market refusals -> Y bought | would have WON n / $ | would have LOST n / $ (markets) | net $ (+cost / -saved) | one-leg refusals -> Y bought, delta $ |
|---|---|---|---|---|---|---|---|
| toxic_fresh | arm-live-twin -> LIVE | 10 / 823 | 118 -> 50 | 46 / +49.44 | 4 / -165.03 (ZEC OCT070915-15 10-07 9:15 AM  -83.26; HYPE OCT042015-15 10-04 8:15 PM  -49.02; BTC OCT061615-15 10-06 4:15 PM  -16.59; BNB OCT060800-00 10-06 8:00 AM  -16.16) | **-115.59** | 25 -> 20, +11.81 |
| early_dear | arm-live-twin -> LIVE | 10 / 823 | 117 -> 24 | 24 / +11.02 | 0 / +0.00  | **+11.02** | 10 -> 7, +1.35 |
| early_cheap | arm-live-twin -> LIVE | 10 / 823 | 10 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +0.39 |
| dump_guard | arm-live-twin -> LIVE | 10 / 823 | 13 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 19 -> 13, -6.41 |
| confidence | arm-live-twin -> LIVE | 10 / 823 | 1242 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 260 -> 197, -69.49 |
| price_ceiling | arm-live-twin -> LIVE | 10 / 823 | 1485 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 172 -> 118, +9.50 |
| rebuy_band | arm-live-twin -> LIVE | 10 / 823 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 40 -> 32, -23.64 |
| late_refused | arm-live-twin -> LIVE | 10 / 823 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 7, -8.70 |
| jump_against | arm-live-twin -> LIVE | 10 / 823 | 88 -> 1 | 1 / +0.80 | 0 / +0.00  | **+0.80** | 15 -> 10, +0.34 |
| spike | arm-live-twin -> LIVE | 10 / 823 | 35 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 11, -2.30 |
| edge_floor | arm-live-twin -> LIVE | 10 / 823 | 3423 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 173 -> 121, +10.79 |
| staged_none | arm-live-twin -> LIVE | 10 / 823 | 23 -> 2 | 2 / +1.70 | 0 / +0.00  | **+1.70** | 18 -> 17, +8.18 |
| market_attempts | arm-live-twin -> LIVE | 10 / 823 | 170 -> 9 | 9 / +5.04 | 0 / +0.00  | **+5.04** | 24 -> 20, +18.14 |
| toxic_fresh | LIVE -> arm-live-twin | 10 / 823 | 42 -> 6 | 6 / +6.49 | 0 / +0.00  | **+6.49** | 13 -> 11, -1.43 |
| early_dear | LIVE -> arm-live-twin | 10 / 823 | 67 -> 5 | 5 / +9.55 | 0 / +0.00  | **+9.55** | 2 -> 2, -0.05 |
| early_cheap | LIVE -> arm-live-twin | 10 / 823 | 6 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 2, -0.93 |
| dump_guard | LIVE -> arm-live-twin | 10 / 823 | 13 -> 2 | 2 / +1.37 | 0 / +0.00  | **+1.37** | 18 -> 14, +13.09 |
| confidence | LIVE -> arm-live-twin | 10 / 823 | 1201 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 267 -> 196, +70.57 |
| price_ceiling | LIVE -> arm-live-twin | 10 / 823 | 1444 -> 29 | 29 / +39.74 | 0 / +0.00  | **+39.74** | 215 -> 144, -1.04 |
| rebuy_band | LIVE -> arm-live-twin | 10 / 823 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 62 -> 58, +9.55 |
| full_cap | LIVE -> arm-live-twin | 10 / 823 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 18 -> 13, +3.35 |
| full_cap_trim | LIVE -> arm-live-twin | 10 / 823 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 7, +1.00 |
| late_refused | LIVE -> arm-live-twin | 10 / 823 | 3 -> 3 | 3 / +6.01 | 0 / +0.00  | **+6.01** | 13 -> 12, +14.75 |
| jump_against | LIVE -> arm-live-twin | 10 / 823 | 92 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 19 -> 14, -3.16 |
| spike | LIVE -> arm-live-twin | 10 / 823 | 34 -> 1 | 1 / +0.89 | 0 / +0.00  | **+0.89** | 16 -> 12, +5.70 |
| edge_floor | LIVE -> arm-live-twin | 10 / 823 | 3377 -> 11 | 11 / +12.01 | 0 / +0.00  | **+12.01** | 208 -> 148, -2.03 |
| staged_none | LIVE -> arm-live-twin | 10 / 823 | 8 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 26 -> 16, -4.15 |
| market_attempts | LIVE -> arm-live-twin | 10 / 823 | 89 -> 1 | 1 / +1.06 | 0 / +0.00  | **+1.06** | 40 -> 24, +5.49 |
| toxic_fresh | arm-live-twin -> arm-0925b | 6 / 420 | 78 -> 54 | 52 / +45.37 | 2 / -61.91 (HYPE OCT042015-15 10-04 8:15 PM  -45.40; BTC OCT061615-15 10-06 4:15 PM  -16.51) | **-16.54** | 11 -> 8, +9.65 |
| early_dear | arm-live-twin -> arm-0925b | 6 / 420 | 62 -> 39 | 39 / +16.58 | 0 / +0.00  | **+16.58** | 8 -> 8, -2.51 |
| early_cheap | arm-live-twin -> arm-0925b | 6 / 420 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +5.26 |
| dump_guard | arm-live-twin -> arm-0925b | 6 / 420 | 4 -> 1 | 1 / +5.91 | 0 / +0.00  | **+5.91** | 12 -> 11, +38.02 |
| confidence | arm-live-twin -> arm-0925b | 6 / 420 | 607 -> 5 | 4 / +2.12 | 1 / -2.54 (BTC OCT042115-15 10-04 9:15 PM  -2.54) | **-0.42** | 135 -> 122, +49.82 |
| price_ceiling | arm-live-twin -> arm-0925b | 6 / 420 | 756 -> 6 | 6 / +2.58 | 0 / +0.00  | **+2.58** | 89 -> 78, +7.19 |
| rebuy_band | arm-live-twin -> arm-0925b | 6 / 420 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 17, +3.33 |
| late_refused | arm-live-twin -> arm-0925b | 6 / 420 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -3.26 |
| jump_against | arm-live-twin -> arm-0925b | 6 / 420 | 43 -> 2 | 2 / +1.51 | 0 / +0.00  | **+1.51** | 5 -> 5, +4.08 |
| spike | arm-live-twin -> arm-0925b | 6 / 420 | 18 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 5, +3.55 |
| edge_floor | arm-live-twin -> arm-0925b | 6 / 420 | 1680 -> 2 | 2 / +1.13 | 0 / +0.00  | **+1.13** | 87 -> 77, +3.06 |
| staged_none | arm-live-twin -> arm-0925b | 6 / 420 | 18 -> 1 | 1 / +1.18 | 0 / +0.00  | **+1.18** | 11 -> 9, +3.45 |
| market_attempts | arm-live-twin -> arm-0925b | 6 / 420 | 94 -> 8 | 8 / +9.01 | 0 / +0.00  | **+9.01** | 13 -> 11, +5.20 |
| early_cheap | arm-0925b -> arm-live-twin | 6 / 420 | 12 -> 6 | 6 / +12.05 | 0 / +0.00  | **+12.05** | 7 -> 4, -27.12 |
| dump_guard | arm-0925b -> arm-live-twin | 6 / 420 | 3 -> 1 | 1 / +1.18 | 0 / +0.00  | **+1.18** | 13 -> 9, -36.70 |
| confidence | arm-0925b -> arm-live-twin | 6 / 420 | 531 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 214 -> 122, -49.82 |
| price_ceiling | arm-0925b -> arm-live-twin | 6 / 420 | 687 -> 3 | 3 / +3.14 | 0 / +0.00  | **+3.14** | 171 -> 76, -7.26 |
| rebuy_band | arm-0925b -> arm-live-twin | 6 / 420 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 22 -> 16, -16.82 |
| late_refused | arm-0925b -> arm-live-twin | 6 / 420 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 7, -17.27 |
| jump_against | arm-0925b -> arm-live-twin | 6 / 420 | 36 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 5, -6.82 |
| spike | arm-0925b -> arm-live-twin | 6 / 420 | 15 -> 1 | 1 / +0.89 | 0 / +0.00  | **+0.89** | 11 -> 5, -3.55 |
| edge_cap | arm-0925b -> arm-live-twin | 6 / 420 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, -5.25 |
| edge_floor | arm-0925b -> arm-live-twin | 6 / 420 | 1654 -> 1 | 1 / +0.10 | 0 / +0.00  | **+0.10** | 164 -> 76, +2.11 |
| staged_none | arm-0925b -> arm-live-twin | 6 / 420 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 18 -> 13, +3.39 |
| market_attempts | arm-0925b -> arm-live-twin | 6 / 420 | 15 -> 1 | 1 / +2.39 | 0 / +0.00  | **+2.39** | 6 -> 4, +3.80 |
| early_cheap | arm-0925b -> LIVE | 6 / 418 | 12 -> 8 | 7 / +18.02 | 1 / -16.16 (BNB OCT060800-00 10-06 8:00 AM  -16.16) | **+1.86** | 7 -> 7, -29.07 |
| dump_guard | arm-0925b -> LIVE | 6 / 418 | 3 -> 1 | 0 / +0.00 | 1 / -83.26 (ZEC OCT070915-15 10-07 9:15 AM  -83.26) | **-83.26** | 13 -> 9, -44.00 |
| confidence | arm-0925b -> LIVE | 6 / 418 | 524 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 213 -> 155, -42.94 |
| price_ceiling | arm-0925b -> LIVE | 6 / 418 | 679 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 171 -> 118, -8.61 |
| rebuy_band | arm-0925b -> LIVE | 6 / 418 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 22 -> 16, -21.60 |
| late_refused | arm-0925b -> LIVE | 6 / 418 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 8, -30.17 |
| jump_against | arm-0925b -> LIVE | 6 / 418 | 36 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 8, +0.63 |
| spike | arm-0925b -> LIVE | 6 / 418 | 14 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 6, +0.64 |
| edge_cap | arm-0925b -> LIVE | 6 / 418 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, -1.18 |
| edge_floor | arm-0925b -> LIVE | 6 / 418 | 1644 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 164 -> 110, +3.98 |
| staged_none | arm-0925b -> LIVE | 6 / 418 | 5 -> 1 | 1 / +0.79 | 0 / +0.00  | **+0.79** | 17 -> 17, +5.27 |
| market_attempts | arm-0925b -> LIVE | 6 / 418 | 15 -> 2 | 2 / +2.51 | 0 / +0.00  | **+2.51** | 6 -> 6, +6.54 |
| toxic_fresh | LIVE -> arm-0925b | 6 / 418 | 2 -> 1 | 1 / +1.70 | 0 / +0.00  | **+1.70** | - |
| early_dear | LIVE -> arm-0925b | 6 / 418 | 4 -> 4 | 4 / +0.39 | 0 / +0.00  | **+0.39** | - |
| early_cheap | LIVE -> arm-0925b | 6 / 418 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, +4.37 |
| dump_guard | LIVE -> arm-0925b | 6 / 418 | 3 -> 1 | 1 / +5.91 | 0 / +0.00  | **+5.91** | 13 -> 11, +43.10 |
| confidence | LIVE -> arm-0925b | 6 / 418 | 539 -> 7 | 6 / +5.82 | 1 / -2.54 (BTC OCT042115-15 10-04 9:15 PM  -2.54) | **+3.28** | 165 -> 154, +44.02 |
| price_ceiling | LIVE -> arm-0925b | 6 / 418 | 679 -> 31 | 31 / +18.99 | 0 / +0.00  | **+18.99** | 143 -> 136, +13.07 |
| rebuy_band | LIVE -> arm-0925b | 6 / 418 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 27 -> 27, +30.50 |
| full_cap | LIVE -> arm-0925b | 6 / 418 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 18 -> 18, +15.55 |
| full_cap_trim | LIVE -> arm-0925b | 6 / 418 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 11, +1.48 |
| late_refused | LIVE -> arm-0925b | 6 / 418 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 8, +30.17 |
| jump_against | LIVE -> arm-0925b | 6 / 418 | 45 -> 1 | 1 / +0.71 | 0 / +0.00  | **+0.71** | 9 -> 9, +6.34 |
| spike | LIVE -> arm-0925b | 6 / 418 | 16 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 7, +3.28 |
| edge_cap | LIVE -> arm-0925b | 6 / 418 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, +3.14 |
| edge_floor | LIVE -> arm-0925b | 6 / 418 | 1597 -> 8 | 8 / +5.62 | 0 / +0.00  | **+5.62** | 132 -> 127, +15.95 |
| staged_none | LIVE -> arm-0925b | 6 / 418 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 19 -> 16, -1.40 |
| market_attempts | LIVE -> arm-0925b | 6 / 418 | 9 -> 1 | 1 / +1.70 | 0 / +0.00  | **+1.70** | 29 -> 26, +14.73 |
| toxic_fresh | arm-live-twin -> arm-0914 | 6 / 402 | 77 -> 28 | 26 / +9.66 | 2 / -36.46 (HYPE OCT042015-15 10-04 8:15 PM  -18.71; ZEC OCT070915-15 10-07 9:15 AM  -17.75) | **-26.80** | 11 -> 6, -6.65 |
| early_dear | arm-live-twin -> arm-0914 | 6 / 402 | 58 -> 4 | 4 / +1.83 | 0 / +0.00  | **+1.83** | - |
| early_cheap | arm-live-twin -> arm-0914 | 6 / 402 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, -2.45 |
| dump_guard | arm-live-twin -> arm-0914 | 6 / 402 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 12 -> 12, +31.14 |
| confidence | arm-live-twin -> arm-0914 | 6 / 402 | 584 -> 1 | 0 / +0.00 | 1 / -19.57 (BTC OCT042115-15 10-04 9:15 PM  -19.57) | **-19.57** | 131 -> 82, -52.37 |
| price_ceiling | arm-live-twin -> arm-0914 | 6 / 402 | 732 -> 3 | 3 / +0.62 | 0 / +0.00  | **+0.62** | 84 -> 41, -50.44 |
| rebuy_band | arm-live-twin -> arm-0914 | 6 / 402 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 15, +24.74 |
| late_refused | arm-live-twin -> arm-0914 | 6 / 402 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -8.94 |
| jump_against | arm-live-twin -> arm-0914 | 6 / 402 | 40 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 3, -0.57 |
| spike | arm-live-twin -> arm-0914 | 6 / 402 | 17 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 5, -12.20 |
| edge_floor | arm-live-twin -> arm-0914 | 6 / 402 | 1623 -> 1 | 1 / +0.14 | 0 / +0.00  | **+0.14** | 82 -> 32, +32.57 |
| staged_none | arm-live-twin -> arm-0914 | 6 / 402 | 17 -> 4 | 4 / +1.46 | 0 / +0.00  | **+1.46** | 11 -> 10, +2.26 |
| market_attempts | arm-live-twin -> arm-0914 | 6 / 402 | 89 -> 1 | 1 / +0.56 | 0 / +0.00  | **+0.56** | 13 -> 8, -7.96 |
| dump_guard | arm-0914 -> arm-live-twin | 6 / 402 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 7, +3.90 |
| confidence | arm-0914 -> arm-live-twin | 6 / 402 | 256 -> 1 | 1 / +0.06 | 0 / +0.00  | **+0.06** | 100 -> 72, +40.11 |
| price_ceiling | arm-0914 -> arm-live-twin | 6 / 402 | 336 -> 16 | 16 / +12.54 | 0 / +0.00  | **+12.54** | 53 -> 32, +47.14 |
| both_sides | arm-0914 -> arm-live-twin | 6 / 402 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 112 -> 71, +26.55 |
| rebuy_band | arm-0914 -> arm-live-twin | 6 / 402 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 12 -> 8, +8.52 |
| edge_floor | arm-0914 -> arm-live-twin | 6 / 402 | 1120 -> 37 | 37 / +25.26 | 0 / +0.00  | **+25.26** | 23 -> 9, -9.91 |
| toxic_fresh | arm-toxic15 -> arm-live-twin | 6 / 498 | 94 -> 9 | 9 / +18.35 | 0 / +0.00  | **+18.35** | 13 -> 11, +1.01 |
| early_dear | arm-toxic15 -> arm-live-twin | 6 / 498 | 68 -> 1 | 1 / +0.60 | 0 / +0.00  | **+0.60** | 9 -> 8, +0.53 |
| early_cheap | arm-toxic15 -> arm-live-twin | 6 / 498 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, +2.45 |
| dump_guard | arm-toxic15 -> arm-live-twin | 6 / 498 | 7 -> 1 | 1 / +1.18 | 0 / +0.00  | **+1.18** | 11 -> 11, -4.75 |
| confidence | arm-toxic15 -> arm-live-twin | 6 / 498 | 751 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 151 -> 144, -39.72 |
| price_ceiling | arm-toxic15 -> arm-live-twin | 6 / 498 | 948 -> 3 | 3 / +10.16 | 0 / +0.00  | **+10.16** | 90 -> 87, +0.62 |
| rebuy_band | arm-toxic15 -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 17, -11.06 |
| late_refused | arm-toxic15 -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 9 -> 9, -4.88 |
| jump_against | arm-toxic15 -> arm-live-twin | 6 / 498 | 59 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 10 -> 10, -3.84 |
| spike | arm-toxic15 -> arm-live-twin | 6 / 498 | 21 -> 1 | 1 / +0.89 | 0 / +0.00  | **+0.89** | 9 -> 9, -1.48 |
| edge_floor | arm-toxic15 -> arm-live-twin | 6 / 498 | 2154 -> 2 | 2 / +0.94 | 0 / +0.00  | **+0.94** | 94 -> 90, -15.76 |
| staged_none | arm-toxic15 -> arm-live-twin | 6 / 498 | 20 -> 2 | 2 / +3.06 | 0 / +0.00  | **+3.06** | 16 -> 14, -4.53 |
| market_attempts | arm-toxic15 -> arm-live-twin | 6 / 498 | 123 -> 3 | 3 / +6.56 | 0 / +0.00  | **+6.56** | 15 -> 12, +5.70 |
| toxic_fresh | arm-toxic0 -> arm-live-twin | 6 / 498 | 106 -> 17 | 17 / +17.56 | 0 / +0.00  | **+17.56** | 21 -> 19, +4.79 |
| early_dear | arm-toxic0 -> arm-live-twin | 6 / 498 | 66 -> 2 | 2 / +1.06 | 0 / +0.00  | **+1.06** | 8 -> 4, -0.39 |
| early_cheap | arm-toxic0 -> arm-live-twin | 6 / 498 | 6 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, +1.13 |
| dump_guard | arm-toxic0 -> arm-live-twin | 6 / 498 | 7 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 11, -14.14 |
| confidence | arm-toxic0 -> arm-live-twin | 6 / 498 | 758 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 140 -> 133, -8.19 |
| price_ceiling | arm-toxic0 -> arm-live-twin | 6 / 498 | 958 -> 5 | 5 / +11.10 | 0 / +0.00  | **+11.10** | 89 -> 83, +6.87 |
| rebuy_band | arm-toxic0 -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 13, +1.44 |
| late_refused | arm-toxic0 -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 7, +4.58 |
| jump_against | arm-toxic0 -> arm-live-twin | 6 / 498 | 62 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 9 -> 9, -3.37 |
| spike | arm-toxic0 -> arm-live-twin | 6 / 498 | 22 -> 1 | 1 / +0.89 | 0 / +0.00  | **+0.89** | 7 -> 7, +1.79 |
| edge_floor | arm-toxic0 -> arm-live-twin | 6 / 498 | 2159 -> 3 | 3 / +1.15 | 0 / +0.00  | **+1.15** | 91 -> 86, +11.83 |
| staged_none | arm-toxic0 -> arm-live-twin | 6 / 498 | 15 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 16, +2.39 |
| market_attempts | arm-toxic0 -> arm-live-twin | 6 / 498 | 128 -> 3 | 3 / +6.56 | 0 / +0.00  | **+6.56** | 20 -> 17, +15.53 |
| toxic_fresh | arm-norebuy -> arm-live-twin | 6 / 498 | 84 -> 3 | 3 / +0.45 | 0 / +0.00  | **+0.45** | 16 -> 12, -1.30 |
| early_dear | arm-norebuy -> arm-live-twin | 6 / 498 | 74 -> 2 | 2 / +1.06 | 0 / +0.00  | **+1.06** | 8 -> 5, -0.72 |
| early_cheap | arm-norebuy -> arm-live-twin | 6 / 498 | 6 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +3.01 |
| dump_guard | arm-norebuy -> arm-live-twin | 6 / 498 | 7 -> 1 | 1 / +1.18 | 0 / +0.00  | **+1.18** | 11 -> 10, -3.29 |
| confidence | arm-norebuy -> arm-live-twin | 6 / 498 | 747 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 156 -> 151, -14.36 |
| price_ceiling | arm-norebuy -> arm-live-twin | 6 / 498 | 946 -> 6 | 6 / +6.28 | 0 / +0.00  | **+6.28** | 95 -> 91, +11.93 |
| both_sides | arm-norebuy -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 4, +15.51 |
| rebuy_band | arm-norebuy -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 17, +5.22 |
| late_refused | arm-norebuy -> arm-live-twin | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 6, +2.52 |
| jump_against | arm-norebuy -> arm-live-twin | 6 / 498 | 62 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 8, +0.19 |
| spike | arm-norebuy -> arm-live-twin | 6 / 498 | 22 -> 1 | 1 / +0.89 | 0 / +0.00  | **+0.89** | 8 -> 8, +0.41 |
| edge_floor | arm-norebuy -> arm-live-twin | 6 / 498 | 2156 -> 2 | 2 / +0.94 | 0 / +0.00  | **+0.94** | 93 -> 89, +7.66 |
| staged_none | arm-norebuy -> arm-live-twin | 6 / 498 | 19 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 15, +1.75 |
| market_attempts | arm-norebuy -> arm-live-twin | 6 / 498 | 109 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 13, +3.47 |
| toxic_fresh | arm-live-twin -> arm-norebuy | 6 / 498 | 90 -> 4 | 4 / +2.79 | 0 / +0.00  | **+2.79** | 15 -> 14, +2.71 |
| early_dear | arm-live-twin -> arm-norebuy | 6 / 498 | 75 -> 1 | 1 / +0.11 | 0 / +0.00  | **+0.11** | 9 -> 7, +0.31 |
| early_cheap | arm-live-twin -> arm-norebuy | 6 / 498 | 6 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -1.16 |
| dump_guard | arm-live-twin -> arm-norebuy | 6 / 498 | 6 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 12 -> 11, -4.93 |
| confidence | arm-live-twin -> arm-norebuy | 6 / 498 | 739 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 164 -> 151, +14.36 |
| price_ceiling | arm-live-twin -> arm-norebuy | 6 / 498 | 944 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 106 -> 94, -9.15 |
| rebuy_band | arm-live-twin -> arm-norebuy | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 20 -> 19, -8.80 |
| late_refused | arm-live-twin -> arm-norebuy | 6 / 498 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -2.83 |
| jump_against | arm-live-twin -> arm-norebuy | 6 / 498 | 58 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 10, -0.19 |
| spike | arm-live-twin -> arm-norebuy | 6 / 498 | 20 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 9 -> 7, +0.00 |
| edge_floor | arm-live-twin -> arm-norebuy | 6 / 498 | 2146 -> 1 | 1 / +0.71 | 0 / +0.00  | **+0.71** | 102 -> 90, -3.07 |
| staged_none | arm-live-twin -> arm-norebuy | 6 / 498 | 20 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 15, +5.21 |
| market_attempts | arm-live-twin -> arm-norebuy | 6 / 498 | 113 -> 1 | 1 / +2.71 | 0 / +0.00  | **+2.71** | 19 -> 16, +2.04 |
| toxic_fresh | arm-lockfix -> LIVE | 7 / 587 | 104 -> 45 | 42 / +47.49 | 3 / -148.87 (ZEC OCT070915-15 10-07 9:15 AM  -83.26; HYPE OCT042015-15 10-04 8:15 PM  -49.02; BTC OCT061615-15 10-06 4:15 PM  -16.59) | **-101.38** | 19 -> 15, -5.66 |
| early_dear | arm-lockfix -> LIVE | 7 / 587 | 67 -> 16 | 16 / +5.32 | 0 / +0.00  | **+5.32** | 20 -> 15, -1.41 |
| early_cheap | arm-lockfix -> LIVE | 7 / 587 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 4, -5.98 |
| dump_guard | arm-lockfix -> LIVE | 7 / 587 | 7 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 16 -> 8, -24.45 |
| confidence | arm-lockfix -> LIVE | 7 / 587 | 901 -> 1 | 1 / +0.55 | 0 / +0.00  | **+0.55** | 193 -> 150, -131.32 |
| price_ceiling | arm-lockfix -> LIVE | 7 / 587 | 1130 -> 2 | 2 / +1.09 | 0 / +0.00  | **+1.09** | 126 -> 90, -12.98 |
| rebuy_band | arm-lockfix -> LIVE | 7 / 587 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 25 -> 21, -12.21 |
| late_refused | arm-lockfix -> LIVE | 7 / 587 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 10 -> 8, -21.11 |
| jump_against | arm-lockfix -> LIVE | 7 / 587 | 65 -> 2 | 2 / +1.46 | 0 / +0.00  | **+1.46** | 12 -> 8, +0.54 |
| spike | arm-lockfix -> LIVE | 7 / 587 | 20 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 5, +0.03 |
| edge_floor | arm-lockfix -> LIVE | 7 / 587 | 2601 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 129 -> 94, -18.87 |
| staged_none | arm-lockfix -> LIVE | 7 / 587 | 20 -> 4 | 4 / +4.79 | 0 / +0.00  | **+4.79** | 19 -> 19, -7.48 |
| market_attempts | arm-lockfix -> LIVE | 7 / 587 | 81 -> 6 | 6 / +3.19 | 0 / +0.00  | **+3.19** | 19 -> 17, +8.95 |
| toxic_fresh | arm-lockfix -> arm-live-twin | 7 / 590 | 104 -> 4 | 4 / +4.04 | 0 / +0.00  | **+4.04** | 20 -> 14, -11.97 |
| early_dear | arm-lockfix -> arm-live-twin | 7 / 590 | 67 -> 1 | 1 / +0.46 | 0 / +0.00  | **+0.46** | 20 -> 8, +0.08 |
| early_cheap | arm-lockfix -> arm-live-twin | 7 / 590 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 2, +1.16 |
| dump_guard | arm-lockfix -> arm-live-twin | 7 / 590 | 7 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 16 -> 13, -14.74 |
| confidence | arm-lockfix -> arm-live-twin | 7 / 590 | 909 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 195 -> 173, -64.46 |
| price_ceiling | arm-lockfix -> arm-live-twin | 7 / 590 | 1137 -> 4 | 4 / +5.47 | 0 / +0.00  | **+5.47** | 127 -> 112, -16.39 |
| rebuy_band | arm-lockfix -> arm-live-twin | 7 / 590 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 25 -> 24, -1.40 |
| late_refused | arm-lockfix -> arm-live-twin | 7 / 590 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 10 -> 10, -10.32 |
| jump_against | arm-lockfix -> arm-live-twin | 7 / 590 | 65 -> 1 | 1 / +0.63 | 0 / +0.00  | **+0.63** | 12 -> 12, +0.62 |
| spike | arm-lockfix -> arm-live-twin | 7 / 590 | 21 -> 1 | 1 / +0.89 | 0 / +0.00  | **+0.89** | 8 -> 7, -0.97 |
| edge_floor | arm-lockfix -> arm-live-twin | 7 / 590 | 2616 -> 2 | 2 / +2.03 | 0 / +0.00  | **+2.03** | 129 -> 112, -25.68 |
| staged_none | arm-lockfix -> arm-live-twin | 7 / 590 | 20 -> 2 | 2 / +2.13 | 0 / +0.00  | **+2.13** | 19 -> 17, -11.92 |
| market_attempts | arm-lockfix -> arm-live-twin | 7 / 590 | 81 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 19 -> 14, -1.61 |
| toxic_fresh | arm-live-twin -> arm-lockfix | 7 / 590 | 100 -> 9 | 8 / +7.70 | 1 / -7.42 (BNB OCT060800-00 10-06 8:00 AM  -7.42) | **+0.28** | 20 -> 16, +11.40 |
| early_dear | arm-live-twin -> arm-lockfix | 7 / 590 | 86 -> 8 | 8 / +5.81 | 0 / +0.00  | **+5.81** | 9 -> 8, -0.72 |
| early_cheap | arm-live-twin -> arm-lockfix | 7 / 590 | 7 -> 3 | 3 / +8.13 | 0 / +0.00  | **+8.13** | 2 -> 2, -1.16 |
| dump_guard | arm-live-twin -> arm-lockfix | 7 / 590 | 8 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 13 -> 13, +14.74 |
| confidence | arm-live-twin -> arm-lockfix | 7 / 590 | 914 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 187 -> 174, +64.42 |
| price_ceiling | arm-live-twin -> arm-lockfix | 7 / 590 | 1117 -> 3 | 3 / +0.35 | 0 / +0.00  | **+0.35** | 124 -> 113, +10.57 |
| rebuy_band | arm-live-twin -> arm-lockfix | 7 / 590 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 27 -> 26, +8.45 |
| late_refused | arm-live-twin -> arm-lockfix | 7 / 590 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +2.08 |
| jump_against | arm-live-twin -> arm-lockfix | 7 / 590 | 64 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 14, -0.24 |
| spike | arm-live-twin -> arm-lockfix | 7 / 590 | 20 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 9 -> 7, +0.97 |
| edge_floor | arm-live-twin -> arm-lockfix | 7 / 590 | 2570 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 121 -> 112, +24.82 |
| staged_none | arm-live-twin -> arm-lockfix | 7 / 590 | 21 -> 1 | 1 / +0.79 | 0 / +0.00  | **+0.79** | 17 -> 14, +3.62 |
| market_attempts | arm-live-twin -> arm-lockfix | 7 / 590 | 131 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 22 -> 17, +3.98 |
| toxic_fresh | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 37 -> 19 | 18 / +21.28 | 1 / -131.98 (BTC SEP270000-00 09-27 12:00 AM -131.98) | **-110.70** | 10 -> 8, +2.54 |
| dump_guard | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 6 -> 1 | 0 / +0.00 | 1 / -32.73 (ETH SEP270230-30 09-27 2:30 AM  -32.73) | **-32.73** | 3 -> 3, +0.26 |
| confidence | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 296 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 114 -> 80, +10.88 |
| price_ceiling | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 450 -> 1 | 1 / +0.00 | 0 / +0.00  | **+0.00** | 84 -> 57, -5.80 |
| rebuy_band | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 12, -6.86 |
| late_refused | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 5, +17.55 |
| jump_against | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 38 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 2, +0.06 |
| spike | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 15 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 6, +23.86 |
| edge_floor | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 1099 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 80 -> 51, -2.66 |
| staged_none | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +1.24 |
| market_attempts | arm-toxic (20260925T1226) -> LIVE | 3 / 253 | 41 -> 2 | 2 / +2.26 | 0 / +0.00  | **+2.26** | 6 -> 6, +2.51 |
| toxic_fresh | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 7 -> 1 | 1 / +0.56 | 0 / +0.00  | **+0.56** | 1 -> 1, +0.21 |
| dump_guard | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 2, -2.69 |
| confidence | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 321 -> 2 | 2 / +0.88 | 0 / +0.00  | **+0.88** | 92 -> 79, -10.24 |
| price_ceiling | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 466 -> 26 | 26 / +30.22 | 0 / +0.00  | **+30.22** | 78 -> 60, +6.68 |
| rebuy_band | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 16 -> 15, +4.82 |
| late_refused | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 2 -> 2 | 2 / +0.31 | 0 / +0.00  | **+0.31** | 5 -> 5, -17.55 |
| jump_against | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 37 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 3, +0.06 |
| spike | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 14 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 6, -23.86 |
| edge_cap | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 1 -> 1 | 1 / +0.12 | 0 / +0.00  | **+0.12** | - |
| edge_floor | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 1115 -> 4 | 4 / +6.15 | 0 / +0.00  | **+6.15** | 77 -> 63, +3.60 |
| staged_none | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 5, +2.64 |
| market_attempts | LIVE -> arm-toxic (20260925T1226) | 3 / 253 | 24 -> 1 | 1 / +0.25 | 0 / +0.00  | **+0.25** | 5 -> 2, +0.18 |
| toxic_fresh | LIVE -> arm-btcd | 7 / 556 | 27 -> 19 | 16 / +16.27 | 3 / -41.59 (BTC SEP291330-30 09-29 1:30 PM  -22.65; XRP SEP302000-00 09-30 8:00 PM  -17.55; BTCD-26SEP2719-T84199.99 09-27 7:00 PM  -1.39) | **-25.32** | 5 -> 5, +8.82 |
| early_dear | LIVE -> arm-btcd | 7 / 556 | 40 -> 30 | 30 / +13.45 | 0 / +0.00  | **+13.45** | 2 -> 2, +0.73 |
| dump_guard | LIVE -> arm-btcd | 7 / 556 | 8 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 5, +52.54 |
| confidence | LIVE -> arm-btcd | 7 / 556 | 783 -> 4 | 4 / +10.86 | 0 / +0.00  | **+10.86** | 162 -> 157, +115.50 |
| price_ceiling | LIVE -> arm-btcd | 7 / 556 | 975 -> 51 | 50 / +50.40 | 1 / -10.09 (ETH SEP262215-15 09-26 10:15 PM -10.09) | **+40.31** | 130 -> 126, +72.34 |
| rebuy_band | LIVE -> arm-btcd | 7 / 556 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 33 -> 33, +101.64 |
| late_refused | LIVE -> arm-btcd | 7 / 556 | 4 -> 4 | 4 / +7.18 | 0 / +0.00  | **+7.18** | 8 -> 8, -17.76 |
| jump_against | LIVE -> arm-btcd | 7 / 556 | 66 -> 5 | 5 / +5.15 | 0 / +0.00  | **+5.15** | 6 -> 6, -0.64 |
| spike | LIVE -> arm-btcd | 7 / 556 | 31 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 13 -> 13, +48.75 |
| edge_cap | LIVE -> arm-btcd | 7 / 556 | 1 -> 1 | 1 / +0.10 | 0 / +0.00  | **+0.10** | - |
| edge_floor | LIVE -> arm-btcd | 7 / 556 | 2254 -> 15 | 15 / +17.73 | 0 / +0.00  | **+17.73** | 132 -> 129, +60.27 |
| staged_none | LIVE -> arm-btcd | 7 / 556 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 10 -> 10, +9.77 |
| market_attempts | LIVE -> arm-btcd | 7 / 556 | 71 -> 8 | 8 / +5.42 | 0 / +0.00  | **+5.42** | 12 -> 10, +13.61 |
| toxic_fresh | LIVE -> arm-hourly-all | 8 / 667 | 40 -> 26 | 22 / +23.06 | 4 / -43.11 (BTC SEP291330-30 09-29 1:30 PM  -22.66; XRP SEP302000-00 09-30 8:00 PM  -17.87; BTCD-26SEP2719-T84199.99 09-27 7:00 PM  -1.42; BTCD-26OCT0201-T86599.99 10-02 1:00 AM  -1.16) | **-20.05** | 7 -> 7, +13.05 |
| early_dear | LIVE -> arm-hourly-all | 8 / 667 | 54 -> 43 | 43 / +27.80 | 0 / +0.00  | **+27.80** | 3 -> 3, -0.05 |
| early_cheap | LIVE -> arm-hourly-all | 8 / 667 | 21 -> 2 | 2 / +1.68 | 0 / +0.00  | **+1.68** | - |
| dump_guard | LIVE -> arm-hourly-all | 8 / 667 | 11 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 6, +39.56 |
| confidence | LIVE -> arm-hourly-all | 8 / 667 | 960 -> 2 | 2 / +1.32 | 0 / +0.00  | **+1.32** | 191 -> 182, +135.60 |
| price_ceiling | LIVE -> arm-hourly-all | 8 / 667 | 1173 -> 48 | 48 / +49.59 | 0 / +0.00  | **+49.59** | 147 -> 142, +45.59 |
| rebuy_band | LIVE -> arm-hourly-all | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 44 -> 44, +146.04 |
| late_refused | LIVE -> arm-hourly-all | 8 / 667 | 4 -> 4 | 4 / +3.59 | 0 / +0.00  | **+3.59** | 10 -> 9, +9.33 |
| jump_against | LIVE -> arm-hourly-all | 8 / 667 | 76 -> 3 | 3 / +1.80 | 0 / +0.00  | **+1.80** | 7 -> 7, +2.10 |
| spike | LIVE -> arm-hourly-all | 8 / 667 | 38 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 16, +73.75 |
| edge_cap | LIVE -> arm-hourly-all | 8 / 667 | 1 -> 1 | 1 / +0.13 | 0 / +0.00  | **+0.13** | - |
| edge_floor | LIVE -> arm-hourly-all | 8 / 667 | 2694 -> 15 | 15 / +21.96 | 0 / +0.00  | **+21.96** | 153 -> 149, +55.78 |
| staged_none | LIVE -> arm-hourly-all | 8 / 667 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 9, +1.95 |
| market_attempts | LIVE -> arm-hourly-all | 8 / 667 | 92 -> 11 | 11 / +12.50 | 0 / +0.00  | **+12.50** | 13 -> 10, +7.88 |
| toxic_fresh | LIVE -> arm-live-frozen | 8 / 664 | 35 -> 21 | 19 / +27.45 | 2 / -97.11 (BTC SEP291330-30 09-29 1:30 PM  -73.12; XRP SEP302000-00 09-30 8:00 PM  -23.99) | **-69.66** | 7 -> 7, +6.68 |
| early_dear | LIVE -> arm-live-frozen | 8 / 664 | 54 -> 41 | 41 / +46.19 | 0 / +0.00  | **+46.19** | 2 -> 2, +0.03 |
| early_cheap | LIVE -> arm-live-frozen | 8 / 664 | 21 -> 13 | 13 / +61.11 | 0 / +0.00  | **+61.11** | 3 -> 3, +4.93 |
| dump_guard | LIVE -> arm-live-frozen | 8 / 664 | 11 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 7, +43.38 |
| confidence | LIVE -> arm-live-frozen | 8 / 664 | 933 -> 5 | 5 / +3.29 | 0 / +0.00  | **+3.29** | 191 -> 173, +94.90 |
| price_ceiling | LIVE -> arm-live-frozen | 8 / 664 | 1151 -> 44 | 43 / +51.72 | 1 / -3.83 (ETH SEP262215-15 09-26 10:15 PM -3.83) | **+47.89** | 145 -> 136, +64.37 |
| rebuy_band | LIVE -> arm-live-frozen | 8 / 664 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 42 -> 41, +100.86 |
| late_refused | LIVE -> arm-live-frozen | 8 / 664 | 5 -> 3 | 3 / +6.89 | 0 / +0.00  | **+6.89** | 9 -> 7, -10.00 |
| jump_against | LIVE -> arm-live-frozen | 8 / 664 | 76 -> 4 | 4 / +14.33 | 0 / +0.00  | **+14.33** | 6 -> 6, -0.71 |
| spike | LIVE -> arm-live-frozen | 8 / 664 | 38 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 14, +67.57 |
| edge_floor | LIVE -> arm-live-frozen | 8 / 664 | 2654 -> 14 | 14 / +16.93 | 0 / +0.00  | **+16.93** | 151 -> 149, +94.47 |
| staged_none | LIVE -> arm-live-frozen | 8 / 664 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 11, +8.95 |
| market_attempts | LIVE -> arm-live-frozen | 8 / 664 | 89 -> 11 | 11 / +16.55 | 0 / +0.00  | **+16.55** | 13 -> 11, +7.67 |
| toxic_fresh | LIVE -> arm-fresh500 | 8 / 667 | 40 -> 13 | 13 / +13.09 | 0 / +0.00  | **+13.09** | 7 -> 4, +3.08 |
| early_dear | LIVE -> arm-fresh500 | 8 / 667 | 54 -> 37 | 37 / +17.84 | 0 / +0.00  | **+17.84** | 3 -> 3, -0.05 |
| early_cheap | LIVE -> arm-fresh500 | 8 / 667 | 21 -> 2 | 2 / +2.10 | 0 / +0.00  | **+2.10** | - |
| dump_guard | LIVE -> arm-fresh500 | 8 / 667 | 11 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 6, +39.64 |
| confidence | LIVE -> arm-fresh500 | 8 / 667 | 960 -> 1 | 1 / +0.70 | 0 / +0.00  | **+0.70** | 191 -> 164, +148.39 |
| price_ceiling | LIVE -> arm-fresh500 | 8 / 667 | 1173 -> 37 | 37 / +40.98 | 0 / +0.00  | **+40.98** | 147 -> 120, +15.64 |
| rebuy_band | LIVE -> arm-fresh500 | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 44 -> 38, +205.27 |
| late_refused | LIVE -> arm-fresh500 | 8 / 667 | 4 -> 4 | 4 / +2.95 | 0 / +0.00  | **+2.95** | 10 -> 10, -21.01 |
| jump_against | LIVE -> arm-fresh500 | 8 / 667 | 76 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 5, +0.00 |
| spike | LIVE -> arm-fresh500 | 8 / 667 | 38 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 15, +129.04 |
| edge_cap | LIVE -> arm-fresh500 | 8 / 667 | 1 -> 1 | 1 / +0.12 | 0 / +0.00  | **+0.12** | 1 -> 1, -0.91 |
| edge_floor | LIVE -> arm-fresh500 | 8 / 667 | 2694 -> 10 | 10 / +17.94 | 0 / +0.00  | **+17.94** | 153 -> 121, +8.27 |
| staged_none | LIVE -> arm-fresh500 | 8 / 667 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 10, +2.30 |
| market_attempts | LIVE -> arm-fresh500 | 8 / 667 | 92 -> 7 | 7 / +8.16 | 0 / +0.00  | **+8.16** | 13 -> 10, +6.83 |
| early_cheap | arm-fresh500 -> LIVE | 8 / 667 | 18 -> 2 | 2 / +4.42 | 0 / +0.00  | **+4.42** | 4 -> 2, +0.70 |
| dump_guard | arm-fresh500 -> LIVE | 8 / 667 | 11 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 10, -151.71 |
| confidence | arm-fresh500 -> LIVE | 8 / 667 | 899 -> 4 | 4 / +5.45 | 0 / +0.00  | **+5.45** | 262 -> 167, -146.74 |
| price_ceiling | arm-fresh500 -> LIVE | 8 / 667 | 1140 -> 1 | 1 / +0.05 | 0 / +0.00  | **+0.05** | 165 -> 103, -161.99 |
| rebuy_band | arm-fresh500 -> LIVE | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 33 -> 25, -159.88 |
| late_refused | arm-fresh500 -> LIVE | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 9, +23.22 |
| jump_against | arm-fresh500 -> LIVE | 8 / 667 | 82 -> 1 | 1 / +0.90 | 0 / +0.00  | **+0.90** | 6 -> 4, +0.12 |
| spike | arm-fresh500 -> LIVE | 8 / 667 | 39 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 18 -> 15, -127.05 |
| fresh_level | arm-fresh500 -> LIVE | 8 / 667 | 109 -> 27 | 27 / +26.15 | 0 / +0.00  | **+26.15** | 99 -> 67, -143.78 |
| edge_floor | arm-fresh500 -> LIVE | 8 / 667 | 2683 -> 1 | 1 / +1.76 | 0 / +0.00  | **+1.76** | 187 -> 104, -7.84 |
| staged_none | arm-fresh500 -> LIVE | 8 / 667 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 4, -152.06 |
| early_cheap | arm-fresh500 -> arm-live-twin | 4 / 261 | 3 -> 2 | 2 / +2.60 | 0 / +0.00  | **+2.60** | 1 -> 1, +0.45 |
| dump_guard | arm-fresh500 -> arm-live-twin | 4 / 261 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 4, -19.31 |
| confidence | arm-fresh500 -> arm-live-twin | 4 / 261 | 380 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 90 -> 65, -11.61 |
| price_ceiling | arm-fresh500 -> arm-live-twin | 4 / 261 | 443 -> 2 | 2 / +4.46 | 0 / +0.00  | **+4.46** | 50 -> 33, -6.85 |
| rebuy_band | arm-fresh500 -> arm-live-twin | 4 / 261 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 10 -> 10, +2.16 |
| late_refused | arm-fresh500 -> arm-live-twin | 4 / 261 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 5, +3.12 |
| jump_against | arm-fresh500 -> arm-live-twin | 4 / 261 | 30 -> 1 | 1 / +0.85 | 0 / +0.00  | **+0.85** | 2 -> 1, +0.62 |
| spike | arm-fresh500 -> arm-live-twin | 4 / 261 | 17 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 6, +4.05 |
| fresh_level | arm-fresh500 -> arm-live-twin | 4 / 261 | 37 -> 15 | 15 / +19.52 | 0 / +0.00  | **+19.52** | 30 -> 16, +10.21 |
| edge_floor | arm-fresh500 -> arm-live-twin | 4 / 261 | 1014 -> 2 | 2 / +2.19 | 0 / +0.00  | **+2.19** | 68 -> 39, -10.83 |
| staged_none | arm-fresh500 -> arm-live-twin | 4 / 261 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, +0.62 |
| toxic_fresh | LIVE -> arm-lateadd-off | 8 / 667 | 40 -> 27 | 23 / +20.65 | 4 / -42.94 (BTC SEP291330-30 09-29 1:30 PM  -23.20; XRP SEP302000-00 09-30 8:00 PM  -17.74; BTCD-26SEP2719-T84199.99 09-27 7:00 PM  -1.41; BTCD-26OCT0201-T86599.99 10-02 1:00 AM  -0.59) | **-22.29** | 7 -> 7, +4.66 |
| early_dear | LIVE -> arm-lateadd-off | 8 / 667 | 54 -> 43 | 43 / +23.72 | 0 / +0.00  | **+23.72** | 3 -> 3, -0.07 |
| early_cheap | LIVE -> arm-lateadd-off | 8 / 667 | 21 -> 1 | 1 / +0.85 | 0 / +0.00  | **+0.85** | - |
| dump_guard | LIVE -> arm-lateadd-off | 8 / 667 | 11 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 6, +49.09 |
| confidence | LIVE -> arm-lateadd-off | 8 / 667 | 960 -> 7 | 7 / +4.28 | 0 / +0.00  | **+4.28** | 191 -> 187, +82.35 |
| price_ceiling | LIVE -> arm-lateadd-off | 8 / 667 | 1173 -> 51 | 50 / +58.35 | 1 / -10.09 (ETH SEP262215-15 09-26 10:15 PM -10.09) | **+48.26** | 147 -> 144, +53.66 |
| rebuy_band | LIVE -> arm-lateadd-off | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 44 -> 44, +84.35 |
| late_refused | LIVE -> arm-lateadd-off | 8 / 667 | 4 -> 4 | 4 / +2.56 | 0 / +0.00  | **+2.56** | 10 -> 10, -16.28 |
| jump_against | LIVE -> arm-lateadd-off | 8 / 667 | 76 -> 3 | 3 / +3.56 | 0 / +0.00  | **+3.56** | 7 -> 7, -3.16 |
| spike | LIVE -> arm-lateadd-off | 8 / 667 | 38 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 17, +55.30 |
| edge_cap | LIVE -> arm-lateadd-off | 8 / 667 | 1 -> 1 | 1 / +0.11 | 0 / +0.00  | **+0.11** | 1 -> 1, +6.44 |
| edge_floor | LIVE -> arm-lateadd-off | 8 / 667 | 2694 -> 15 | 15 / +20.42 | 0 / +0.00  | **+20.42** | 153 -> 150, +40.15 |
| staged_none | LIVE -> arm-lateadd-off | 8 / 667 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 11, +8.64 |
| market_attempts | LIVE -> arm-lateadd-off | 8 / 667 | 92 -> 11 | 11 / +8.31 | 0 / +0.00  | **+8.31** | 13 -> 12, +15.41 |
| toxic_fresh | LIVE -> arm-early-off | 8 / 667 | 40 -> 14 | 12 / +21.03 | 2 / -2.55 (BTCD-26SEP2719-T84199.99 09-27 7:00 PM  -1.41; BTCD-26OCT0201-T86599.99 10-02 1:00 AM  -1.14) | **+18.48** | 7 -> 7, +7.05 |
| early_dear | LIVE -> arm-early-off | 8 / 667 | 54 -> 4 | 4 / +10.53 | 0 / +0.00  | **+10.53** | - |
| early_cheap | LIVE -> arm-early-off | 8 / 667 | 21 -> 11 | 11 / +19.16 | 0 / +0.00  | **+19.16** | 3 -> 1, -0.48 |
| dump_guard | LIVE -> arm-early-off | 8 / 667 | 11 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 5, +40.69 |
| confidence | LIVE -> arm-early-off | 8 / 667 | 960 -> 2 | 2 / +0.52 | 0 / +0.00  | **+0.52** | 191 -> 132, +59.07 |
| price_ceiling | LIVE -> arm-early-off | 8 / 667 | 1173 -> 30 | 30 / +44.71 | 0 / +0.00  | **+44.71** | 147 -> 74, +47.53 |
| rebuy_band | LIVE -> arm-early-off | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 44 -> 44, +50.55 |
| late_refused | LIVE -> arm-early-off | 8 / 667 | 4 -> 4 | 4 / +10.49 | 0 / +0.00  | **+10.49** | 10 -> 9, +6.73 |
| jump_against | LIVE -> arm-early-off | 8 / 667 | 76 -> 1 | 1 / +1.21 | 0 / +0.00  | **+1.21** | 7 -> 3, -0.21 |
| spike | LIVE -> arm-early-off | 8 / 667 | 38 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 17 -> 12, +6.20 |
| edge_cap | LIVE -> arm-early-off | 8 / 667 | 1 -> 1 | 1 / +0.07 | 0 / +0.00  | **+0.07** | 1 -> 1, +3.49 |
| edge_floor | LIVE -> arm-early-off | 8 / 667 | 2694 -> 11 | 11 / +20.04 | 0 / +0.00  | **+20.04** | 153 -> 67, +36.83 |
| staged_none | LIVE -> arm-early-off | 8 / 667 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 8, +6.97 |
| market_attempts | LIVE -> arm-early-off | 8 / 667 | 92 -> 5 | 5 / +9.90 | 0 / +0.00  | **+9.90** | 13 -> 10, +16.87 |
| dump_guard | arm-early-off -> LIVE | 8 / 667 | 3 -> 2 | 0 / +0.00 | 2 / -53.02 (ETH SEP270230-30 09-27 2:30 AM  -32.73; BNB SEP261030-30 09-26 10:30 AM -20.29) | **-53.02** | 9 -> 5, -40.69 |
| confidence | arm-early-off -> LIVE | 8 / 667 | 452 -> 2 | 2 / +1.18 | 0 / +0.00  | **+1.18** | 180 -> 118, -10.87 |
| price_ceiling | arm-early-off -> LIVE | 8 / 667 | 575 -> 21 | 21 / +14.17 | 0 / +0.00  | **+14.17** | 106 -> 55, -50.15 |
| rebuy_band | arm-early-off -> LIVE | 8 / 667 | 1 -> 1 | 1 / +2.38 | 0 / +0.00  | **+2.38** | 42 -> 28, -33.59 |
| late_refused | arm-early-off -> LIVE | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 9, -6.73 |
| jump_against | arm-early-off -> LIVE | 8 / 667 | 25 -> 1 | 1 / +0.57 | 0 / +0.00  | **+0.57** | 6 -> 1, -0.16 |
| spike | arm-early-off -> LIVE | 8 / 667 | 24 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 13 -> 9, -0.48 |
| edge_cap | arm-early-off -> LIVE | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 3, +1.99 |
| edge_floor | arm-early-off -> LIVE | 8 / 667 | 1746 -> 64 | 64 / +40.09 | 0 / +0.00  | **+40.09** | 80 -> 33, -50.45 |
| market_attempts | arm-early-off -> LIVE | 8 / 667 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, -3.49 |
| toxic_fresh | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 7 -> 3 | 2 / +0.25 | 1 / -1.42 (BTCD-26SEP2719-T84199.99 09-27 7:00 PM  -1.42) | **-1.17** | 1 -> 1, -1.00 |
| early_cheap | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 18 -> 1 | 1 / +0.83 | 0 / +0.00  | **+0.83** | - |
| dump_guard | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +19.80 |
| confidence | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 321 -> 2 | 2 / +0.86 | 0 / +0.00  | **+0.86** | 92 -> 57, +64.98 |
| price_ceiling | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 466 -> 14 | 14 / +19.85 | 0 / +0.00  | **+19.85** | 78 -> 48, +25.12 |
| rebuy_band | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 16 -> 14, +68.03 |
| late_refused | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 2 -> 1 | 1 / +0.03 | 0 / +0.00  | **+0.03** | 5 -> 3, -17.62 |
| jump_against | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 37 -> 1 | 1 / +1.10 | 0 / +0.00  | **+1.10** | 5 -> 2, -0.69 |
| spike | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 14 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 6, +43.35 |
| edge_cap | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 1 -> 1 | 1 / +0.14 | 0 / +0.00  | **+0.14** | - |
| edge_floor | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 1115 -> 2 | 2 / +5.07 | 0 / +0.00  | **+5.07** | 77 -> 42, +17.57 |
| staged_none | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 3, +1.62 |
| market_attempts | LIVE -> arm-edge2c (20260925T1225) | 3 / 253 | 24 -> 1 | 1 / +0.28 | 0 / +0.00  | **+0.28** | 5 -> 3, +2.22 |
| early_cheap | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 21 -> 1 | 1 / +1.55 | 0 / +0.00  | **+1.55** | - |
| dump_guard | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 4, +1.03 |
| confidence | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 330 -> 4 | 4 / +2.34 | 0 / +0.00  | **+2.34** | 82 -> 57, -64.34 |
| rebuy_band | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 5, +0.08 |
| late_refused | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 3, +17.62 |
| jump_against | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 4 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, -0.14 |
| spike | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 12 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 11 -> 6, -43.35 |
| edge_cap | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 1 -> 1 | 1 / +2.74 | 0 / +0.00  | **+2.74** | 1 -> 1, +3.59 |
| edge_floor | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 1175 -> 39 | 39 / +32.11 | 0 / +0.00  | **+32.11** | 77 -> 53, -88.06 |
| staged_none | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 3 -> 1 | 1 / +5.55 | 0 / +0.00  | **+5.55** | 2 -> 2, +5.08 |
| market_attempts | arm-edge2c (20260925T1225) -> LIVE | 3 / 253 | 20 -> 1 | 1 / +1.87 | 0 / +0.00  | **+1.87** | 1 -> 1, +3.65 |
| toxic_fresh | LIVE -> arm-0925 | 3 / 150 | 9 -> 6 | 5 / +6.39 | 1 / -23.52 (BTC SEP291330-30 09-29 1:30 PM  -23.52) | **-17.13** | - |
| early_dear | LIVE -> arm-0925 | 3 / 150 | 15 -> 11 | 11 / +4.33 | 0 / +0.00  | **+4.33** | 1 -> 1, +0.46 |
| confidence | LIVE -> arm-0925 | 3 / 150 | 239 -> 3 | 3 / +1.72 | 0 / +0.00  | **+1.72** | 33 -> 32, -1.21 |
| price_ceiling | LIVE -> arm-0925 | 3 / 150 | 250 -> 11 | 11 / +8.10 | 0 / +0.00  | **+8.10** | 25 -> 24, +2.14 |
| rebuy_band | LIVE -> arm-0925 | 3 / 150 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 9 -> 9, -6.74 |
| late_refused | LIVE -> arm-0925 | 3 / 150 | 1 -> 1 | 1 / +0.38 | 0 / +0.00  | **+0.38** | - |
| spike | LIVE -> arm-0925 | 3 / 150 | 8 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -0.74 |
| edge_cap | LIVE -> arm-0925 | 3 / 150 | 1 -> 1 | 1 / +0.12 | 0 / +0.00  | **+0.12** | - |
| edge_floor | LIVE -> arm-0925 | 3 / 150 | 560 -> 6 | 6 / +4.89 | 0 / +0.00  | **+4.89** | 29 -> 28, -8.88 |
| staged_none | LIVE -> arm-0925 | 3 / 150 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +1.21 |
| market_attempts | LIVE -> arm-0925 | 3 / 150 | 21 -> 4 | 4 / +4.75 | 0 / +0.00  | **+4.75** | 3 -> 2, +1.45 |
| early_cheap | LIVE -> arm-afternoon | 3 / 285 | 19 -> 11 | 11 / +23.43 | 0 / +0.00  | **+23.43** | 1 -> 1, +0.03 |
| dump_guard | LIVE -> arm-afternoon | 3 / 285 | 8 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 4, -25.79 |
| confidence | LIVE -> arm-afternoon | 3 / 285 | 358 -> 3 | 3 / +5.42 | 0 / +0.00  | **+5.42** | 133 -> 129, -81.73 |
| price_ceiling | LIVE -> arm-afternoon | 3 / 285 | 515 -> 33 | 33 / +26.23 | 0 / +0.00  | **+26.23** | 112 -> 109, -13.13 |
| rebuy_band | LIVE -> arm-afternoon | 3 / 285 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 20 -> 20, -5.36 |
| late_refused | LIVE -> arm-afternoon | 3 / 285 | 2 -> 1 | 1 / +0.04 | 0 / +0.00  | **+0.04** | 4 -> 4, -28.56 |
| jump_against | LIVE -> arm-afternoon | 3 / 285 | 38 -> 3 | 3 / +4.14 | 0 / +0.00  | **+4.14** | 5 -> 5, +0.44 |
| spike | LIVE -> arm-afternoon | 3 / 285 | 15 -> 4 | 4 / +12.85 | 0 / +0.00  | **+12.85** | 5 -> 5, -44.60 |
| edge_cap | LIVE -> arm-afternoon | 3 / 285 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, +8.30 |
| edge_floor | LIVE -> arm-afternoon | 3 / 285 | 1231 -> 6 | 6 / +4.78 | 0 / +0.00  | **+4.78** | 118 -> 117, -13.36 |
| staged_none | LIVE -> arm-afternoon | 3 / 285 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 5, +1.13 |
| market_attempts | LIVE -> arm-afternoon | 3 / 285 | 21 -> 1 | 1 / +1.07 | 0 / +0.00  | **+1.07** | 7 -> 7, +12.86 |
| toxic_fresh | arm-live-twin -> arm-hourly-all | 4 / 261 | 21 -> 14 | 12 / +8.80 | 2 / -19.03 (XRP SEP302000-00 09-30 8:00 PM  -17.87; BTCD-26OCT0201-T86599.99 10-02 1:00 AM  -1.16) | **-10.23** | 6 -> 6, +0.20 |
| early_dear | arm-live-twin -> arm-hourly-all | 4 / 261 | 31 -> 26 | 26 / +8.44 | 0 / +0.00  | **+8.44** | 1 -> 1, +0.00 |
| early_cheap | arm-live-twin -> arm-hourly-all | 4 / 261 | 3 -> 1 | 1 / +0.85 | 0 / +0.00  | **+0.85** | - |
| dump_guard | arm-live-twin -> arm-hourly-all | 4 / 261 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 5, +25.54 |
| confidence | arm-live-twin -> arm-hourly-all | 4 / 261 | 384 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 84 -> 78, +33.37 |
| price_ceiling | arm-live-twin -> arm-hourly-all | 4 / 261 | 427 -> 2 | 2 / +1.67 | 0 / +0.00  | **+1.67** | 54 -> 49, +32.32 |
| rebuy_band | arm-live-twin -> arm-hourly-all | 4 / 261 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 15 -> 15, +26.17 |
| late_refused | arm-live-twin -> arm-hourly-all | 4 / 261 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 6, +1.35 |
| jump_against | arm-live-twin -> arm-hourly-all | 4 / 261 | 25 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 1, +1.68 |
| spike | arm-live-twin -> arm-hourly-all | 4 / 261 | 16 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 8, +3.52 |
| edge_floor | arm-live-twin -> arm-hourly-all | 4 / 261 | 992 -> 1 | 1 / +0.55 | 0 / +0.00  | **+0.55** | 57 -> 51, +24.93 |
| staged_none | arm-live-twin -> arm-hourly-all | 4 / 261 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +7.01 |
| market_attempts | arm-live-twin -> arm-hourly-all | 4 / 261 | 42 -> 4 | 4 / +3.80 | 0 / +0.00  | **+3.80** | 2 -> 2, +1.05 |
| toxic_fresh | arm-live-twin -> arm-btcd | 3 / 150 | 10 -> 6 | 5 / +4.66 | 1 / -17.55 (XRP SEP302000-00 09-30 8:00 PM  -17.55) | **-12.89** | 4 -> 4, +1.55 |
| early_dear | arm-live-twin -> arm-btcd | 3 / 150 | 18 -> 14 | 14 / +4.85 | 0 / +0.00  | **+4.85** | 1 -> 1, +0.00 |
| dump_guard | arm-live-twin -> arm-btcd | 3 / 150 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +17.86 |
| confidence | arm-live-twin -> arm-btcd | 3 / 150 | 212 -> 1 | 1 / +10.02 | 0 / +0.00  | **+10.02** | 48 -> 45, +11.48 |
| price_ceiling | arm-live-twin -> arm-btcd | 3 / 150 | 238 -> 2 | 2 / +0.68 | 0 / +0.00  | **+0.68** | 36 -> 35, +18.30 |
| rebuy_band | arm-live-twin -> arm-btcd | 3 / 150 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 6, +14.18 |
| late_refused | arm-live-twin -> arm-btcd | 3 / 150 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 4, +1.24 |
| spike | arm-live-twin -> arm-btcd | 3 / 150 | 10 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +2.76 |
| edge_floor | arm-live-twin -> arm-btcd | 3 / 150 | 559 -> 1 | 1 / +0.55 | 0 / +0.00  | **+0.55** | 38 -> 35, +14.59 |
| market_attempts | arm-live-twin -> arm-btcd | 3 / 150 | 22 -> 3 | 3 / +3.39 | 0 / +0.00  | **+3.39** | 2 -> 2, +1.47 |
| toxic_fresh | arm-live-twin -> arm-live-frozen | 4 / 238 | 18 -> 10 | 9 / +12.88 | 1 / -23.99 (XRP SEP302000-00 09-30 8:00 PM  -23.99) | **-11.11** | 5 -> 5, +2.20 |
| early_dear | arm-live-twin -> arm-live-frozen | 4 / 238 | 31 -> 23 | 23 / +17.59 | 0 / +0.00  | **+17.59** | 1 -> 1, +0.00 |
| early_cheap | arm-live-twin -> arm-live-frozen | 4 / 238 | 3 -> 1 | 1 / +0.95 | 0 / +0.00  | **+0.95** | - |
| dump_guard | arm-live-twin -> arm-live-frozen | 4 / 238 | 5 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 6, +22.20 |
| confidence | arm-live-twin -> arm-live-frozen | 4 / 238 | 338 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 75 -> 68, +20.68 |
| price_ceiling | arm-live-twin -> arm-live-frozen | 4 / 238 | 379 -> 2 | 2 / +1.53 | 0 / +0.00  | **+1.53** | 49 -> 45, +40.06 |
| rebuy_band | arm-live-twin -> arm-live-frozen | 4 / 238 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 13 -> 12, +23.68 |
| late_refused | arm-live-twin -> arm-live-frozen | 4 / 238 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 5, -9.40 |
| spike | arm-live-twin -> arm-live-frozen | 4 / 238 | 16 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 8 -> 8, +3.36 |
| edge_floor | arm-live-twin -> arm-live-frozen | 4 / 238 | 878 -> 1 | 1 / +0.93 | 0 / +0.00  | **+0.93** | 52 -> 48, +33.55 |
| staged_none | arm-live-twin -> arm-live-frozen | 4 / 238 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -3.68 |
| market_attempts | arm-live-twin -> arm-live-frozen | 4 / 238 | 39 -> 4 | 4 / +4.40 | 0 / +0.00  | **+4.40** | 2 -> 2, +2.93 |
| toxic_fresh | arm-live-twin -> arm-early-full | 2 / 113 | 9 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 2, +1.08 |
| early_dear | arm-live-twin -> arm-early-full | 2 / 113 | 14 -> 5 | 5 / +1.07 | 0 / +0.00  | **+1.07** | 1 -> 1, +0.00 |
| dump_guard | arm-live-twin -> arm-early-full | 2 / 113 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +23.42 |
| confidence | arm-live-twin -> arm-early-full | 2 / 113 | 164 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 36 -> 24, +35.75 |
| price_ceiling | arm-live-twin -> arm-early-full | 2 / 113 | 180 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 27 -> 19, +29.45 |
| rebuy_band | arm-live-twin -> arm-early-full | 2 / 113 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 6 -> 3, +21.55 |
| late_refused | arm-live-twin -> arm-early-full | 2 / 113 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, +1.48 |
| spike | arm-live-twin -> arm-early-full | 2 / 113 | 9 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +1.27 |
| edge_floor | arm-live-twin -> arm-early-full | 2 / 113 | 409 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 29 -> 19, +30.47 |
| market_attempts | arm-live-twin -> arm-early-full | 2 / 113 | 16 -> 1 | 1 / +0.93 | 0 / +0.00  | **+0.93** | 1 -> 1, +1.08 |
| toxic_fresh | LIVE -> arm-early-full | 4 / 344 | 25 -> 3 | 3 / +4.34 | 0 / +0.00  | **+4.34** | 3 -> 3, +1.03 |
| early_dear | LIVE -> arm-early-full | 4 / 344 | 36 -> 10 | 10 / +6.91 | 0 / +0.00  | **+6.91** | 2 -> 2, +0.39 |
| dump_guard | LIVE -> arm-early-full | 4 / 344 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 2, +40.58 |
| confidence | LIVE -> arm-early-full | 4 / 344 | 497 -> 1 | 1 / +0.60 | 0 / +0.00  | **+0.60** | 76 -> 60, +39.63 |
| price_ceiling | LIVE -> arm-early-full | 4 / 344 | 554 -> 11 | 11 / +5.41 | 0 / +0.00  | **+5.41** | 59 -> 46, +39.16 |
| rebuy_band | LIVE -> arm-early-full | 4 / 344 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 20 -> 17, +41.85 |
| late_refused | LIVE -> arm-early-full | 4 / 344 | 2 -> 2 | 2 / +0.24 | 0 / +0.00  | **+0.24** | 1 -> 1, +0.11 |
| jump_against | LIVE -> arm-early-full | 4 / 344 | 30 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, -1.26 |
| spike | LIVE -> arm-early-full | 4 / 344 | 19 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 7 -> 7, +2.32 |
| edge_cap | LIVE -> arm-early-full | 4 / 344 | 1 -> 1 | 1 / +0.14 | 0 / +0.00  | **+0.14** | - |
| edge_floor | LIVE -> arm-early-full | 4 / 344 | 1284 -> 5 | 5 / +5.77 | 0 / +0.00  | **+5.77** | 63 -> 51, +52.09 |
| staged_none | LIVE -> arm-early-full | 4 / 344 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 3, +5.45 |
| market_attempts | LIVE -> arm-early-full | 4 / 344 | 48 -> 4 | 4 / +4.59 | 0 / +0.00  | **+4.59** | 7 -> 6, +6.69 |
| toxic_fresh | LIVE -> arm-floor90-full | 3 / 259 | 19 -> 6 | 6 / +7.81 | 0 / +0.00  | **+7.81** | 2 -> 2, +0.82 |
| early_dear | LIVE -> arm-floor90-full | 3 / 259 | 36 -> 7 | 7 / +6.75 | 0 / +0.00  | **+6.75** | 2 -> 2, -0.05 |
| early_cheap | LIVE -> arm-floor90-full | 3 / 259 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, +1.70 |
| dump_guard | LIVE -> arm-floor90-full | 3 / 259 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +28.71 |
| confidence | LIVE -> arm-floor90-full | 3 / 259 | 402 -> 1 | 1 / +0.08 | 0 / +0.00  | **+0.08** | 60 -> 46, +25.87 |
| price_ceiling | LIVE -> arm-floor90-full | 3 / 259 | 430 -> 5 | 5 / +3.70 | 0 / +0.00  | **+3.70** | 44 -> 32, +28.35 |
| rebuy_band | LIVE -> arm-floor90-full | 3 / 259 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 11, +17.97 |
| late_refused | LIVE -> arm-floor90-full | 3 / 259 | 1 -> 1 | 1 / +0.21 | 0 / +0.00  | **+0.21** | 1 -> 1, +0.18 |
| jump_against | LIVE -> arm-floor90-full | 3 / 259 | 24 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, -0.86 |
| spike | LIVE -> arm-floor90-full | 3 / 259 | 17 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 5, +1.93 |
| edge_floor | LIVE -> arm-floor90-full | 3 / 259 | 956 -> 4 | 4 / +3.79 | 0 / +0.00  | **+3.79** | 47 -> 38, +20.80 |
| staged_none | LIVE -> arm-floor90-full | 3 / 259 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 3, +3.43 |
| market_attempts | LIVE -> arm-floor90-full | 3 / 259 | 41 -> 2 | 2 / +7.47 | 0 / +0.00  | **+7.47** | 6 -> 6, +5.90 |
| toxic_fresh | LIVE -> arm-floor70 | 3 / 259 | 19 -> 3 | 3 / +2.09 | 0 / +0.00  | **+2.09** | 2 -> 1, +0.23 |
| early_dear | LIVE -> arm-floor70 | 3 / 259 | 36 -> 10 | 10 / +3.66 | 0 / +0.00  | **+3.66** | 2 -> 2, -0.07 |
| early_cheap | LIVE -> arm-floor70 | 3 / 259 | 1 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 2 -> 2, -1.56 |
| dump_guard | LIVE -> arm-floor70 | 3 / 259 | 2 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 3 -> 3, +26.42 |
| confidence | LIVE -> arm-floor70 | 3 / 259 | 402 -> 1 | 1 / +0.08 | 0 / +0.00  | **+0.08** | 60 -> 46, +13.63 |
| price_ceiling | LIVE -> arm-floor70 | 3 / 259 | 430 -> 3 | 3 / +0.50 | 0 / +0.00  | **+0.50** | 44 -> 33, +21.39 |
| rebuy_band | LIVE -> arm-floor70 | 3 / 259 | 0 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 14 -> 11, +15.58 |
| late_refused | LIVE -> arm-floor70 | 3 / 259 | 1 -> 1 | 1 / +0.23 | 0 / +0.00  | **+0.23** | 1 -> 1, +0.11 |
| jump_against | LIVE -> arm-floor70 | 3 / 259 | 24 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 1 -> 1, -0.86 |
| spike | LIVE -> arm-floor70 | 3 / 259 | 17 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 5 -> 5, +1.27 |
| edge_floor | LIVE -> arm-floor70 | 3 / 259 | 956 -> 3 | 3 / +2.16 | 0 / +0.00  | **+2.16** | 47 -> 39, +8.16 |
| staged_none | LIVE -> arm-floor70 | 3 / 259 | 3 -> 0 | 0 / +0.00 | 0 / +0.00  | **+0.00** | 4 -> 3, -2.83 |
| market_attempts | LIVE -> arm-floor70 | 3 / 259 | 41 -> 3 | 3 / +1.31 | 0 / +0.00  | **+1.31** | 6 -> 5, -1.22 |

Seller check inside 20 s (the toxic15 / toxic0 arms keep it on past the twin's 20-s stand-down; refusals by seconds left; twin's outcome):

| arm | band | refusals | whole-market -> twin bought | twin won n / $ | twin lost n / $ | net $ | leg -> twin bought, delta $ |
|---|---|---|---|---|---|---|---|
| arm-toxic15 | tau>20 | 96 | 4 | 4 / +6.27 | 0 / +0.00 | **+6.27** | 10 -> 8, -0.06 |
| arm-toxic15 | 15<tau<=20 | 11 | 8 | 8 / +18.64 | 0 / +0.00 | **+18.64** | 3 -> 3, +1.07 |
| arm-toxic0 | tau>20 | 100 | 3 | 3 / +6.24 | 0 / +0.00 | **+6.24** | 14 -> 13, +0.55 |
| arm-toxic0 | 15<tau<=20 | 9 | 6 | 6 / +10.79 | 0 / +0.00 | **+10.79** | 3 -> 3, +3.56 |
| arm-toxic0 | tau<=15 | 18 | 13 | 13 / +9.79 | 0 / +0.00 | **+9.79** | 4 -> 3, +0.68 |

Gate descriptions: `toxic_fresh` = seller check (fresh level < 500 ms with > 50% taker selling; stands down at tau_min); `early_dear` = 97.8c cap on the 45-s leg; `early_cheap` = 45-s leg price floor (0.90 / 0.95 / lower); `dump_guard` = dump guard (offer far below fair); `confidence` = confidence (fair < 0.995); `price_ceiling` = 98c ceiling on every leg; `both_sides` = no rebuy of the hedged side (--rebuy-mult 0); `rebuy_band` = scale-in band / one-full-bet (09-27 code); `full_cap` = one-full-bet cap (--max-full-bets 1); `full_cap_trim` = full-bet trim; `late_refused` = late add refused (jump too big); `late_add_full` = late add on a full position; `jump_against` = jump gate; `spike` = spike gate; `fresh_level` = fresh-offer rule (arm-fresh500); `edge_cap` = 10c edge cap; `edge_floor` = edge floor (0.3c; arm-edge2c 2c); `staged_none` = no staged offer; `market_attempts` = 3 tries used up.

### 2b. The 09-22..09-24 sweeps vs the live bot of that hour (confidence / insurance / sigma / early-leg variants)

Aggregated over every copy of the same flag (windows do not overlap). Direction `live refused -> arm bought` is what a looser rule would have added; `arm refused -> live bought` what a stricter one would have skipped. Paper size then mirrored live (20-50 contracts). Paper, so the loss side is optimistic.

| flag (arm) | direction | gate | copies / closes | markets | won n / $ | lost n / $ | net $ (+ = looser rule made more on paper) | lost markets |
|---|---|---|---|---|---|---|---|---|
| sigma_stress=0.2 | live refused -> arm bought | confidence | 7 / 183 | 109 | 103 / +253.55 | 6 / -126.77 | **+126.78** | ZEC SEP220630-30 09-22 6:30 AM ; BTC SEP220230-30 09-22 2:30 AM ; BTC SEP221515-15 09-22 3:15 PM ; BNB SEP221230-30 09-22 12:30 PM |
| sigma_stress=0.4 | live refused -> arm bought | confidence | 7 / 183 | 128 | 124 / +220.90 | 4 / -65.68 | **+155.22** | ZEC SEP220630-30 09-22 6:30 AM ; BTC SEP220230-30 09-22 2:30 AM ; BTC SEP221515-15 09-22 3:15 PM ; ZEC SEP230400-00 09-23 4:00 AM  |
| sigma_stress=2.0 | arm refused -> live bought | confidence | 7 / 183 | 84 | 82 / +132.68 | 2 / -132.88 | **-0.20** | DOGE SEP222245-45 09-22 10:45 PM; BTC SEP232030-30 09-23 8:30 PM  |
| sigma_stress=1.5 | arm refused -> live bought | confidence | 7 / 183 | 73 | 71 / +109.34 | 2 / -132.88 | **-23.54** | DOGE SEP222245-45 09-22 10:45 PM; BTC SEP232030-30 09-23 8:30 PM  |
| sigma_stress=0.2 | arm refused -> live bought | early_cheap | 6 / 180 | 18 | 16 / +40.31 | 2 / -132.88 | **-92.57** | DOGE SEP222245-45 09-22 10:45 PM; BTC SEP232030-30 09-23 8:30 PM  |
| sigma_stress=0.6 | live refused -> arm bought | confidence | 7 / 183 | 126 | 123 / +149.42 | 3 / -17.13 | **+132.29** | BTC SEP220230-30 09-22 2:30 AM ; BTC SEP221515-15 09-22 3:15 PM ; HYPE SEP231645-45 09-23 4:45 PM  |
| pin=0.97 | live refused -> arm bought | confidence | 7 / 183 | 87 | 85 / +103.72 | 2 / -20.64 | **+83.08** | BTC SEP221515-15 09-22 3:15 PM ; HYPE SEP231645-45 09-23 4:45 PM  |
| pin=0.975 | live refused -> arm bought | confidence | 7 / 183 | 81 | 79 / +74.58 | 2 / -37.20 | **+37.38** | BTC SEP221515-15 09-22 3:15 PM ; HYPE SEP231645-45 09-23 4:45 PM  |
| sigma_stress=0.8 | live refused -> arm bought | confidence | 7 / 183 | 76 | 74 / +66.34 | 2 / -36.60 | **+29.74** | BTC SEP221515-15 09-22 3:15 PM ; HYPE SEP231645-45 09-23 4:45 PM  |
| pin=0.98 | live refused -> arm bought | confidence | 7 / 183 | 76 | 74 / +63.02 | 2 / -37.45 | **+25.57** | BTC SEP221515-15 09-22 3:15 PM ; HYPE SEP231645-45 09-23 4:45 PM  |
| sigma_stress=1.25 | arm refused -> live bought | confidence | 7 / 183 | 51 | 50 / +68.40 | 1 / -2.47 | **+65.93** | DOGE SEP222245-45 09-22 10:45 PM |
| pin=0.985 | live refused -> arm bought | confidence | 8 / 234 | 71 | 69 / +59.88 | 2 / -3.07 | **+56.81** | HYPE SEP231645-45 09-23 4:45 PM ; NEAR SEP240245-45 09-24 2:45 AM  |
| attempts_on_send=True | live refused -> arm bought | dump_guard | 1 / 71 | 1 | 0 / +0.00 | 1 / -55.06 | **-55.06** | HYPE SEP231645-45 09-23 4:45 PM  |
| bank_brake=6.0+bank_divisor=11.76 | live refused -> arm bought | dump_guard | 1 / 71 | 1 | 0 / +0.00 | 1 / -49.34 | **-49.34** | HYPE SEP231645-45 09-23 4:45 PM  |
| live-copy | live refused -> arm bought | price_ceiling | 12 / 565 | 65 | 65 / +47.24 | 0 / +0.00 | **+47.24** |  |
| early_tau_max=60 | live refused -> arm bought | price_ceiling | 6 / 180 | 37 | 36 / +27.06 | 1 / -14.62 | **+12.44** | DOGE SEP221430-30 09-22 2:30 PM  |
| early_tau_max=60 | live refused -> arm bought | edge_floor | 6 / 180 | 71 | 71 / +41.02 | 0 / +0.00 | **+41.02** |  |
| pin=0.99 | live refused -> arm bought | confidence | 6 / 227 | 45 | 43 / +31.67 | 2 / -7.68 | **+23.99** | HYPE SEP231645-45 09-23 4:45 PM ; NEAR SEP240245-45 09-24 2:45 AM  |
| sigma_stress=0.4 | arm refused -> live bought | early_cheap | 5 / 175 | 14 | 13 / +29.75 | 1 / -2.47 | **+27.28** | DOGE SEP222245-45 09-22 10:45 PM |
| pin=0.985 | live refused -> arm bought | price_ceiling | 7 / 230 | 31 | 31 / +31.21 | 0 / +0.00 | **+31.21** |  |
| sigma_stress=0.8 | live refused -> arm bought | price_ceiling | 6 / 179 | 19 | 19 / +26.47 | 0 / +0.00 | **+26.47** |  |
| pin=0.99 | live refused -> arm bought | price_ceiling | 7 / 230 | 33 | 33 / +25.80 | 0 / +0.00 | **+25.80** |  |
| bank_brake=3.0+bank_divisor=5.88 | live refused -> arm bought | price_ceiling | 6 / 264 | 31 | 31 / +25.27 | 0 / +0.00 | **+25.27** |  |
| live-copy | live refused -> arm bought | edge_floor | 14 / 597 | 23 | 23 / +24.45 | 0 / +0.00 | **+24.45** |  |
| bank_brake=6.0+bank_divisor=11.76 | live refused -> arm bought | price_ceiling | 4 / 154 | 21 | 21 / +22.95 | 0 / +0.00 | **+22.95** |  |
| early_tau_max=60 | live refused -> arm bought | confidence | 3 / 149 | 3 | 2 / +1.02 | 1 / -17.64 | **-16.62** | BNB SEP221230-30 09-22 12:30 PM |
| hedge_belief=0.6 | live refused -> arm bought | price_ceiling | 5 / 176 | 20 | 20 / +17.93 | 0 / +0.00 | **+17.93** |  |
| early_frac=0.5+early_tau_max=30 | arm refused -> live bought | edge_floor | 5 / 176 | 25 | 25 / +17.53 | 0 / +0.00 | **+17.53** |  |
| pin=0.98 | live refused -> arm bought | price_ceiling | 6 / 179 | 17 | 17 / +17.53 | 0 / +0.00 | **+17.53** |  |
| hedge_slip=0.0 | live refused -> arm bought | price_ceiling | 5 / 176 | 21 | 21 / +17.28 | 0 / +0.00 | **+17.28** |  |
| attempts_on_send=True | live refused -> arm bought | price_ceiling | 4 / 173 | 17 | 17 / +16.86 | 0 / +0.00 | **+16.86** |  |
| early_max_price=0.975 | arm refused -> live bought | early_dear | 6 / 226 | 30 | 30 / +16.61 | 0 / +0.00 | **+16.61** |  |
| hedge_prop=True | live refused -> arm bought | price_ceiling | 4 / 154 | 21 | 21 / +15.74 | 0 / +0.00 | **+15.74** |  |
| pin=0.975 | live refused -> arm bought | price_ceiling | 5 / 176 | 16 | 16 / +15.73 | 0 / +0.00 | **+15.73** |  |
| pin=0.97 | live refused -> arm bought | price_ceiling | 6 / 179 | 16 | 16 / +15.44 | 0 / +0.00 | **+15.44** |  |
| hedge_belief=0.01 | live refused -> arm bought | price_ceiling | 5 / 176 | 21 | 21 / +15.13 | 0 / +0.00 | **+15.13** |  |
| sigma_stress=0.2 | live refused -> arm bought | price_ceiling | 3 / 122 | 7 | 7 / +14.64 | 0 / +0.00 | **+14.64** |  |
| early_frac=1.0 | live refused -> arm bought | price_ceiling | 5 / 205 | 19 | 19 / +14.25 | 0 / +0.00 | **+14.25** |  |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 | arm refused -> live bought | edge_floor | 2 / 92 | 25 | 25 / +13.97 | 0 / +0.00 | **+13.97** |  |
| doubt_mult=1.25 | live refused -> arm bought | price_ceiling | 3 / 127 | 13 | 13 / +13.40 | 0 / +0.00 | **+13.40** |  |
| early_max_price=0.975 | live refused -> arm bought | price_ceiling | 6 / 227 | 19 | 19 / +13.18 | 0 / +0.00 | **+13.18** |  |
| sigma_stress=0.2 | arm refused -> live bought | market_attempts | 4 / 152 | 7 | 7 / +13.17 | 0 / +0.00 | **+13.17** |  |
| sigma_stress=0.6 | arm refused -> live bought | early_cheap | 3 / 82 | 5 | 5 / +12.75 | 0 / +0.00 | **+12.75** |  |
| doubt_mult=1.5 | live refused -> arm bought | price_ceiling | 3 / 127 | 10 | 10 / +12.24 | 0 / +0.00 | **+12.24** |  |
| early_frac=0.5+early_tau_max=30 | live refused -> arm bought | price_ceiling | 4 / 154 | 13 | 13 / +11.67 | 0 / +0.00 | **+11.67** |  |
| edge_floor=0.02 | arm refused -> live bought | edge_floor | 1 / 84 | 22 | 22 / +10.95 | 0 / +0.00 | **+10.95** |  |
| bank_brake=3.0+bank_divisor=5.88 | live refused -> arm bought | edge_floor | 5 / 242 | 10 | 10 / +9.84 | 0 / +0.00 | **+9.84** |  |
| sigma_stress=0.6 | live refused -> arm bought | price_ceiling | 3 / 122 | 9 | 9 / +9.79 | 0 / +0.00 | **+9.79** |  |
| live-copy | live refused -> arm bought | confidence | 6 / 396 | 7 | 7 / +9.42 | 0 / +0.00 | **+9.42** |  |
| hedge_belief=0.01 | live refused -> arm bought | edge_floor | 3 / 125 | 4 | 4 / +9.10 | 0 / +0.00 | **+9.10** |  |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 | arm refused -> live bought | price_ceiling | 1 / 88 | 15 | 15 / +7.71 | 0 / +0.00 | **+7.71** |  |
| attempts_on_send=True | live refused -> arm bought | edge_floor | 4 / 173 | 6 | 6 / +7.31 | 0 / +0.00 | **+7.31** |  |
| sigma_stress=1.25 | arm refused -> live bought | dump_guard | 1 / 5 | 1 | 1 / +6.78 | 0 / +0.00 | **+6.78** |  |
| hedge_slip=0.0 | arm refused -> live bought | dump_guard | 1 / 5 | 1 | 1 / +6.78 | 0 / +0.00 | **+6.78** |  |
| early_frac=1.0 | arm refused -> live bought | dump_guard | 1 / 5 | 1 | 1 / +6.78 | 0 / +0.00 | **+6.78** |  |
| early_max_price=0.975 | arm refused -> live bought | dump_guard | 1 / 5 | 1 | 1 / +6.78 | 0 / +0.00 | **+6.78** |  |
| early_frac=0.5+early_tau_max=30 | arm refused -> live bought | confidence | 1 / 32 | 1 | 1 / +6.14 | 0 / +0.00 | **+6.14** |  |
| pin=0.985 | live refused -> arm bought | edge_floor | 4 / 173 | 5 | 5 / +5.96 | 0 / +0.00 | **+5.96** |  |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 | live refused -> arm bought | edge_floor | 1 / 88 | 1 | 1 / +5.95 | 0 / +0.00 | **+5.95** |  |
| pin=0.975 | arm refused -> live bought | early_cheap | 1 / 46 | 1 | 1 / +5.71 | 0 / +0.00 | **+5.71** |  |
| pin=0.98 | arm refused -> live bought | early_cheap | 1 / 46 | 1 | 1 / +5.71 | 0 / +0.00 | **+5.71** |  |
| sigma_stress=0.8 | arm refused -> live bought | early_cheap | 1 / 46 | 1 | 1 / +5.71 | 0 / +0.00 | **+5.71** |  |
| pin=0.97 | arm refused -> live bought | staged_none | 2 / 76 | 2 | 2 / +5.68 | 0 / +0.00 | **+5.68** |  |
| early_frac=0.5+early_tau_max=30 | live refused -> arm bought | edge_floor | 2 / 93 | 4 | 4 / +5.39 | 0 / +0.00 | **+5.39** |  |
| hedge_prop=True | live refused -> arm bought | edge_floor | 5 / 176 | 7 | 7 / +5.29 | 0 / +0.00 | **+5.29** |  |
| sigma_stress=0.4 | live refused -> arm bought | price_ceiling | 4 / 154 | 8 | 8 / +5.21 | 0 / +0.00 | **+5.21** |  |
| sigma_stress=0.8 | live refused -> arm bought | jump_against | 1 / 22 | 1 | 1 / +5.18 | 0 / +0.00 | **+5.18** |  |
| pin=0.99 | live refused -> arm bought | edge_floor | 3 / 154 | 6 | 6 / +4.77 | 0 / +0.00 | **+4.77** |  |
| early_frac=1.0 | live refused -> arm bought | edge_floor | 3 / 149 | 5 | 5 / +4.62 | 0 / +0.00 | **+4.62** |  |
| sigma_stress=0.4 | arm refused -> live bought | market_attempts | 3 / 106 | 3 | 3 / +4.49 | 0 / +0.00 | **+4.49** |  |
| bank_brake=3.0+bank_divisor=5.88 | arm refused -> live bought | price_ceiling | 4 / 237 | 6 | 6 / +4.47 | 0 / +0.00 | **+4.47** |  |
| sigma_stress=1.25 | live refused -> arm bought | price_ceiling | 5 / 157 | 8 | 8 / +4.34 | 0 / +0.00 | **+4.34** |  |
| hedge_belief=0.8+hedge_max_tries=5+improve_scope=close+max_per_market=1+max_per_market_run=1+min_fill_frac=0.5+pick=first | arm refused -> live bought | edge_floor | 1 / 24 | 3 | 3 / +4.33 | 0 / +0.00 | **+4.33** |  |
| bank_brake=6.0+bank_divisor=11.76 | live refused -> arm bought | edge_floor | 4 / 171 | 4 | 4 / +3.94 | 0 / +0.00 | **+3.94** |  |
| pin=0.97 | live refused -> arm bought | edge_floor | 3 / 139 | 3 | 3 / +3.92 | 0 / +0.00 | **+3.92** |  |
| pin=0.98 | live refused -> arm bought | edge_floor | 3 / 139 | 3 | 3 / +3.89 | 0 / +0.00 | **+3.89** |  |
| early_frac=0.5+early_min_price=0.9+early_tau_max=30 | live refused -> arm bought | price_ceiling | 1 / 88 | 5 | 5 / +3.81 | 0 / +0.00 | **+3.81** |  |
| pin=0.975 | live refused -> arm bought | edge_floor | 3 / 139 | 3 | 3 / +3.67 | 0 / +0.00 | **+3.67** |  |
| sigma_stress=1.25 | live refused -> arm bought | edge_floor | 3 / 139 | 3 | 3 / +3.67 | 0 / +0.00 | **+3.67** |  |
| early_frac=0.5+early_tau_max=30 | arm refused -> live bought | price_ceiling | 2 / 117 | 7 | 7 / +3.59 | 0 / +0.00 | **+3.59** |  |
| sigma_stress=0.8 | live refused -> arm bought | edge_floor | 3 / 122 | 3 | 3 / +3.51 | 0 / +0.00 | **+3.51** |  |
| sigma_stress=1.5 | live refused -> arm bought | price_ceiling | 2 / 35 | 4 | 4 / +3.42 | 0 / +0.00 | **+3.42** |  |
| hedge_belief=0.6+hedge_prop=True | live refused -> arm bought | price_ceiling | 1 / 55 | 4 | 4 / +3.41 | 0 / +0.00 | **+3.41** |  |
| hedge_belief=0.6 | live refused -> arm bought | edge_floor | 3 / 149 | 3 | 3 / +2.97 | 0 / +0.00 | **+2.97** |  |
| hedge_slip=0.0 | live refused -> arm bought | edge_floor | 3 / 108 | 5 | 5 / +2.53 | 0 / +0.00 | **+2.53** |  |
| early_tau_max=60 | live refused -> arm bought | close_budget | 2 / 117 | 4 | 4 / +2.47 | 0 / +0.00 | **+2.47** |  |
| early_tau_max=60 | arm refused -> live bought | price_ceiling | 3 / 139 | 3 | 3 / +1.68 | 0 / +0.00 | **+1.68** |  |
| hedge_prop=True | live refused -> arm bought | confidence | 2 / 117 | 3 | 3 / +1.67 | 0 / +0.00 | **+1.67** |  |
| edge_floor=0.02 | live refused -> arm bought | edge_floor | 1 / 84 | 3 | 3 / +1.66 | 0 / +0.00 | **+1.66** |  |
| doubt_mult=1.25 | live refused -> arm bought | edge_floor | 3 / 127 | 3 | 3 / +1.60 | 0 / +0.00 | **+1.60** |  |
| edge_floor=0.02 | arm refused -> live bought | confidence | 1 / 84 | 3 | 3 / +1.56 | 0 / +0.00 | **+1.56** |  |
| live-copy | arm refused -> live bought | fresh_level | 1 / 73 | 6 | 6 / +1.53 | 0 / +0.00 | **+1.53** |  |
| hedge_belief=0.6 | live refused -> arm bought | confidence | 2 / 117 | 3 | 3 / +1.25 | 0 / +0.00 | **+1.25** |  |
| hedge_slip=0.0 | live refused -> arm bought | confidence | 2 / 117 | 3 | 3 / +1.25 | 0 / +0.00 | **+1.25** |  |
| early_frac=1.0 | arm refused -> live bought | price_ceiling | 3 / 168 | 4 | 4 / +1.24 | 0 / +0.00 | **+1.24** |  |
| sigma_stress=0.6 | live refused -> arm bought | edge_floor | 3 / 108 | 3 | 3 / +1.20 | 0 / +0.00 | **+1.20** |  |
| bank_brake=4.08+bank_divisor=7.9968+early_max_edge=3.0+extra_coin=0.0+hedge_belief=0.6+hedge_slip=0.0+late_extra=0.0+late_extra_tau=0+late_mult=1.0+late_tau=0 | live refused -> arm bought | edge_floor | 1 / 55 | 3 | 3 / +1.06 | 0 / +0.00 | **+1.06** |  |
| live-copy | arm refused -> live bought | price_ceiling | 6 / 423 | 6 | 6 / +0.98 | 0 / +0.00 | **+0.98** |  |
| sigma_stress=2.0 | live refused -> arm bought | price_ceiling | 2 / 78 | 3 | 3 / +0.89 | 0 / +0.00 | **+0.89** |  |
| early_max_price=0.975 | arm refused -> live bought | price_ceiling | 3 / 168 | 3 | 3 / +0.50 | 0 / +0.00 | **+0.50** |  |
| bank_brake=4.08+bank_divisor=7.9968+early_max_edge=3.0+extra_coin=0.0+hedge_belief=0.6+hedge_slip=0.0+late_extra=0.0+late_extra_tau=0+late_mult=1.0+late_tau=0 | live refused -> arm bought | price_ceiling | 1 / 55 | 4 | 4 / +0.49 | 0 / +0.00 | **+0.49** |  |

## 3. Every live losing market since 09-22 (main account) and what the arms up at that close did

`refused` lists the arm's gates with seconds left (the first-named gate at the smallest tau is the one that was holding when live bought). Sweep copies are summarised.

| live market (ET) | live $ / contracts | named arms: bought $ (contracts) or refused (gate@s) | sweep copies |
|---|---|---|---|
| DOGE SEP222245-45 09-22 10:45 PM ET | -2.47 / 26.0 | - | 20 of 25 bought, $-76.43 .. -0.91 |
| BTC SEP232030-30 09-23 8:30 PM ET | -130.41 / 352.0 | - | 24 of 27 bought, $-74.67 .. -45.11 |
| BNB SEP261030-30 09-26 10:30 AM ET | -20.29 / 196.0 | arm-afternoon: bought -46.38 (196.0) [confidence@45, late_refused@6, late_refused@6]<br>arm-live-frozen: DID NOT BUY [confidence@45, spike@6, dump_guard@5]<br>arm-early-off: DID NOT BUY [confidence@30, spike@6, dump_guard@5]<br>arm-brake3 (20260925T1225): bought -41.12 (196.0) [confidence@45, spike@6, late_refused@5]<br>arm-lateadd-off: bought -41.12 (196.0) [confidence@45, spike@6, dump_guard@5, late_refused@5]<br>arm-edge2c (20260925T1225): bought -41.12 (196.0) [confidence@45, spike@6, dump_guard@5, late_refused@5]<br>arm-btcd: bought -41.12 (196.0) [confidence@45, spike@6, late_refused@5]<br>arm-fresh500: bought -47.11 (196.0) [confidence@45, spike@6, dump_guard@5, late_refused@5]<br>arm-toxic: bought -41.12 (196.0) [confidence@45, spike@6, late_refused@5]<br>arm-hourly-all: DID NOT BUY [confidence@45, spike@6, dump_guard@5] | - |
| BTC SEP270000-00 09-27 12:00 AM ET | -131.98 / 396.0 | arm-live-frozen: bought -65.50 (198.0) [confidence@45, spike@32, staged_none@30]<br>arm-early-off: bought -127.52 (396.0) [confidence@30, rebuy_band@30]<br>arm-brake3 (20260925T1225): bought -63.85 (198.0) [confidence@45, spike@32]<br>arm-lateadd-off: bought -63.71 (198.0) [confidence@45, spike@32]<br>arm-edge2c (20260925T1225): bought -65.55 (198.0) [confidence@45, spike@32, edge_floor@30]<br>arm-btcd: bought -63.96 (198.0) [confidence@45]<br>arm-fresh500: bought +21.36 (198.0) [confidence@45, spike@32, fresh_level@30, price_ceiling@29, dump_guard@25, staged_none@17, rebuy_band@17]<br>arm-toxic: DID NOT BUY [confidence@45, spike@32, toxic_fresh@30, market_attempts@30]<br>arm-hourly-all: bought -64.74 (198.0) [confidence@45, spike@32] | - |
| ETH SEP270230-30 09-27 2:30 AM ET | -32.73 / 176.0 | arm-live-frozen: bought -18.11 (132.0) [confidence@45, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-early-off: DID NOT BUY [confidence@30, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-brake3 (20260925T1225): bought -36.46 (176.0) [confidence@45, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-lateadd-off: bought -10.99 (60.0) [confidence@45, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-edge2c (20260925T1225): bought -10.69 (60.0) [confidence@45, edge_floor@29, dump_guard@18]<br>arm-btcd: bought -12.28 (66.0) [confidence@45, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-fresh500: bought -36.46 (176.0) [confidence@45, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-toxic: DID NOT BUY [confidence@45, edge_floor@29, price_ceiling@29, dump_guard@18, against_thin@5]<br>arm-hourly-all: bought -36.46 (176.0) [confidence@45, edge_floor@29, price_ceiling@29, rebuy_band@17, against_thin@5] | - |
| BNB SEP282000-00 09-28 8:00 PM ET | -8.26 / 90.9 | arm-live-frozen: bought -19.14 (151.0) [price_ceiling@45, confidence@30]<br>arm-early-off: bought +1.73 (93.0) [confidence@30, rebuy_band@22, price_ceiling@15, edge_floor@14]<br>arm-lateadd-off: bought +0.97 (93.0) [price_ceiling@45, confidence@30]<br>arm-btcd: bought +1.00 (93.0) [price_ceiling@45, confidence@30]<br>arm-fresh500: bought +1.11 (93.0) [price_ceiling@45, fresh_level@45, edge_floor@43, confidence@30]<br>arm-hourly-all: bought +1.04 (93.0) [price_ceiling@45, confidence@30]<br>arm-early-full: bought -18.33 (138.7) [price_ceiling@45, confidence@30]<br>arm-0925: bought +1.06 (93.0) [price_ceiling@45, confidence@30]<br>arm-0925-hedge20: bought +1.04 (93.0) [price_ceiling@45, confidence@30]<br>arm-0925-nohedge: bought -27.19 (121.2) [price_ceiling@45, confidence@30]<br>arm-live-hedge20: bought -0.19 (22.7) [price_ceiling@45, confidence@30]<br>arm-live-nohedge: bought -1.50 (22.7) [price_ceiling@45, confidence@30]<br>arm-floor90: bought -9.57 (79.3) [price_ceiling@45, confidence@30]<br>arm-floor85: bought -0.27 (22.7) [price_ceiling@45, confidence@30]<br>arm-floor80: bought -0.27 (22.7) [price_ceiling@45, confidence@30]<br>arm-floor70: bought -0.30 (22.7) [price_ceiling@45, confidence@30]<br>arm-floor90-full: bought -0.27 (22.7) [price_ceiling@45, confidence@30] | - |
| XRP SEP301915-15 09-30 7:15 PM ET | -42.60 / 178.0 | arm-live-twin: bought -24.30 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, rebuy_band@20, dump_guard@20]<br>arm-live-frozen: bought -2.47 (10.0) [confidence@45, price_ceiling@33, edge_floor@32]<br>arm-early-off: bought -1.66 (20.0) [price_ceiling@30, edge_floor@25, dump_guard@20]<br>arm-lateadd-off: bought -16.67 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20]<br>arm-btcd: bought -11.71 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20]<br>arm-fresh500: bought -1.90 (22.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20]<br>arm-hourly-all: bought -2.10 (20.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20]<br>arm-early-full: bought -3.08 (22.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20]<br>arm-live-hedge20: bought -50.88 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20]<br>arm-live-nohedge: bought -79.32 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, rebuy_band@20, dump_guard@20]<br>arm-floor90: bought -23.45 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, rebuy_band@20, dump_guard@20]<br>arm-floor85: bought -26.67 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20]<br>arm-floor80: bought -16.67 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20]<br>arm-floor70: bought -16.67 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20]<br>arm-floor90-full: bought -14.24 (178.0) [confidence@45, price_ceiling@33, edge_floor@32, dump_guard@20, rebuy_band@20] | - |
| SOL OCT022130-30 10-02 9:30 PM ET | -41.11 / 240.0 | arm-live-twin: bought -45.34 (240.0) [confidence@45, price_ceiling@25, edge_floor@24, rebuy_band@19]<br>arm-lockfix: bought -34.78 (192.0) [confidence@45, price_ceiling@25, edge_floor@24] | - |
| BTC OCT030400-00 10-03 4:00 AM ET | -13.01 / 63.3 | arm-live-twin: bought -13.37 (63.3) [confidence@45, price_ceiling@30, toxic_fresh@23, jump_against@22, against_thin@11, staged_none@7, market_attempts@7]<br>arm-lockfix: bought -13.05 (63.3) [confidence@45, price_ceiling@30, toxic_fresh@23, market_attempts@23]<br>arm-toxic15: bought -13.37 (63.3) [confidence@45, toxic_fresh@36, price_ceiling@30, market_attempts@23]<br>arm-toxic0: bought -13.37 (63.3) [confidence@45, price_ceiling@30, toxic_fresh@23, market_attempts@23]<br>arm-norebuy: bought -13.37 (63.3) [confidence@45, price_ceiling@30, toxic_fresh@23, staged_none@23, market_attempts@23] | - |
| NEAR OCT030645-45 10-03 6:45 AM ET | -86.95 / 188.0 | arm-live-twin: bought -3.46 (8.0) [confidence@45]<br>arm-lockfix: bought -1.78 (4.0) [confidence@45]<br>arm-toxic15: bought -3.57 (8.0) [confidence@45]<br>arm-toxic0: bought -3.60 (8.0) [confidence@45]<br>arm-norebuy: bought -3.44 (8.0) [confidence@45] | - |
| BTC OCT041615-15 10-04 4:15 PM ET | -6.08 / 90.9 | arm-live-twin: bought -1.96 (121.3) [confidence@30, dump_guard@10]<br>arm-lockfix: bought +11.85 (93.1) [staged_none@45, confidence@30, dump_guard@10, late_refused@10]<br>arm-toxic15: bought -1.62 (121.3) [confidence@30, dump_guard@10, late_refused@10]<br>arm-toxic0: bought -1.62 (121.3) [staged_none@45, confidence@30, dump_guard@10, late_refused@10]<br>arm-norebuy: bought -10.18 (60.6) [confidence@30, both_sides@10]<br>arm-0925b: bought +19.26 (136.5) [early_cheap@45, confidence@45, dump_guard@10, late_refused@10, late_refused@10]<br>arm-0914: bought +2.82 (20.0) [confidence@30, dump_guard@10, both_sides@None] | - |
| HYPE OCT042015-15 10-04 8:15 PM ET | -49.02 / 230.0 | arm-live-twin: DID NOT BUY [confidence@45, price_ceiling@28, edge_floor@28, toxic_fresh@24, market_attempts@24]<br>arm-lockfix: DID NOT BUY [confidence@45, price_ceiling@28, edge_floor@28, toxic_fresh@24, market_attempts@24]<br>arm-toxic15: DID NOT BUY [confidence@45, price_ceiling@28, edge_floor@28, toxic_fresh@24, market_attempts@24]<br>arm-toxic0: DID NOT BUY [confidence@45, price_ceiling@28, edge_floor@28, toxic_fresh@24, market_attempts@24]<br>arm-norebuy: DID NOT BUY [confidence@45, price_ceiling@28, edge_floor@28, toxic_fresh@24, market_attempts@24]<br>arm-0925b: bought -45.40 (230.0) [confidence@45, price_ceiling@28, edge_floor@28, rebuy_band@24, dump_guard@24, late_refused@9]<br>arm-0914: bought -18.71 (20.0) [confidence@30, price_ceiling@28, edge_floor@27, both_sides@None] | - |
| HYPE OCT050030-30 10-05 12:30 AM ET | -73.88 / 222.5 | arm-live-twin: bought -70.88 (205.0) [confidence@45, rebuy_band@22, edge_floor@18, dump_guard@16]<br>arm-lockfix: bought -75.96 (205.0) [confidence@45, rebuy_band@22, edge_floor@18, dump_guard@16, late_refused@8]<br>arm-toxic15: bought -66.62 (205.0) [confidence@45, rebuy_band@22, edge_floor@18, dump_guard@16, late_refused@8]<br>arm-toxic0: bought -75.75 (205.0) [confidence@45, rebuy_band@22, edge_floor@18, dump_guard@16, late_refused@8]<br>arm-norebuy: bought -75.30 (178.0) [confidence@45, rebuy_band@22, edge_floor@18, dump_guard@16, both_sides@8]<br>arm-0925b: bought -70.72 (194.3) [confidence@45, rebuy_band@22, edge_floor@18, dump_guard@16, late_refused@8]<br>arm-0914: bought -19.44 (20.0) [confidence@30, both_sides@None] | - |
| BNB OCT060800-00 10-06 8:00 AM ET | -16.16 / 178.0 | arm-live-twin: DID NOT BUY [confidence@45, toxic_fresh@34, early_cheap@34, market_attempts@34]<br>arm-lockfix: bought -7.42 (85.1) [confidence@45, early_cheap@34, dump_guard@34]<br>arm-toxic15: DID NOT BUY [confidence@45, staged_none@34, early_cheap@34, market_attempts@34]<br>arm-toxic0: DID NOT BUY [confidence@45, early_cheap@34, market_attempts@34]<br>arm-norebuy: DID NOT BUY [confidence@45, early_cheap@34, market_attempts@34]<br>arm-0925b: DID NOT BUY [confidence@45, staged_none@34, early_cheap@34, market_attempts@34]<br>arm-0914: bought +0.75 (20.0) [both_sides@None] | - |
| NEAR OCT061615-15 10-06 4:15 PM ET | -21.93 / 59.3 | arm-live-twin: bought -22.38 (62.3) [confidence@45, edge_floor@30, dump_guard@26]<br>arm-lockfix: bought -21.06 (100.3) [confidence@45, edge_floor@30, dump_guard@26]<br>arm-toxic15: bought -20.59 (100.3) [confidence@45, edge_floor@30, dump_guard@26]<br>arm-toxic0: bought -21.35 (59.3) [confidence@45, edge_floor@30, dump_guard@26, toxic_fresh@16, price_ceiling@16]<br>arm-norebuy: bought -22.40 (59.3) [confidence@45, edge_floor@30, dump_guard@26, both_sides@16]<br>arm-0925b: bought -22.30 (62.3) [confidence@45, edge_floor@30, dump_guard@26]<br>arm-0914: bought +0.10 (3.0) [confidence@30, edge_floor@30, dump_guard@26, both_sides@None] | - |
| BTC OCT061615-15 10-06 4:15 PM ET | -16.59 / 59.3 | arm-live-twin: DID NOT BUY [staged_none@45, toxic_fresh@45, market_attempts@45]<br>arm-lockfix: DID NOT BUY [staged_none@45, toxic_fresh@45, market_attempts@45]<br>arm-toxic15: DID NOT BUY [staged_none@45, toxic_fresh@45, market_attempts@45]<br>arm-toxic0: DID NOT BUY [staged_none@45, toxic_fresh@45, market_attempts@45]<br>arm-norebuy: DID NOT BUY [staged_none@45, toxic_fresh@45, market_attempts@45]<br>arm-0925b: bought -16.51 (59.3) [staged_none@45, confidence@30, against_thin@6, edge_floor@3]<br>arm-0914: DID NOT BUY [confidence@30, against_thin@6, edge_floor@3] | - |
| ZEC OCT070915-15 10-07 9:15 AM ET | -83.26 / 89.0 | arm-live-twin: DID NOT BUY [confidence@45, price_ceiling@25, dump_guard@23, toxic_fresh@23, market_attempts@23]<br>arm-lockfix: DID NOT BUY [confidence@45, price_ceiling@25, dump_guard@23, toxic_fresh@23, market_attempts@23]<br>arm-toxic15: DID NOT BUY [confidence@45, price_ceiling@25, dump_guard@23, toxic_fresh@23, market_attempts@23]<br>arm-toxic0: DID NOT BUY [confidence@45, price_ceiling@25, dump_guard@23, toxic_fresh@23, market_attempts@23]<br>arm-norebuy: DID NOT BUY [confidence@45, price_ceiling@25, dump_guard@23, toxic_fresh@23, market_attempts@23]<br>arm-0925b: DID NOT BUY [confidence@45, price_ceiling@25, dump_guard@23, edge_cap@23, market_attempts@23]<br>arm-0914: bought -17.75 (20.0) [confidence@30, price_ceiling@25, dump_guard@23, both_sides@None] | - |

Markets an arm refused (never bought) that live bought and WON -- what the rule would have cost live, per arm and gate (decisive gate, shared closes):

| arm | window (ET days / closes) | gate | live won n / $ | live lost n / $ | net |
|---|---|---|---|---|---|
| arm-early-off (20260925T0227) | 2 / 26 | price_ceiling | 2 / +1.33 | 0 / +0.00 | **+1.33** |
| arm-fresh500 (20260925T0227) | 2 / 26 | fresh_level | 3 / +5.88 | 0 / +0.00 | **+5.88** |
| arm-toxic (20260925T0227) | 2 / 26 | toxic_fresh | 6 / +10.32 | 0 / +0.00 | **+10.32** |
| arm-live-frozen | 8 / 664 | price_ceiling | 2 / +4.01 | 0 / +0.00 | **+4.01** |
| arm-live-frozen | 8 / 664 | edge_cap | 1 / +2.74 | 0 / +0.00 | **+2.74** |
| arm-live-frozen | 8 / 664 | rebuy_band | 1 / +2.38 | 0 / +0.00 | **+2.38** |
| arm-live-frozen | 8 / 664 | dump_guard | 0 / +0.00 | 1 / -20.29 | **-20.29** |
| arm-lateadd-off? (20260925T0938) | 1 / 11 | price_ceiling | 1 / +2.33 | 0 / +0.00 | **+2.33** |
| arm-hourly-all (20260925T0938) | 1 / 11 | price_ceiling | 1 / +2.33 | 0 / +0.00 | **+2.33** |
| arm-early-off | 8 / 667 | price_ceiling | 21 / +14.17 | 0 / +0.00 | **+14.17** |
| arm-early-off | 8 / 667 | rebuy_band | 1 / +2.38 | 0 / +0.00 | **+2.38** |
| arm-early-off | 8 / 667 | confidence | 2 / +1.18 | 0 / +0.00 | **+1.18** |
| arm-early-off | 8 / 667 | dump_guard | 0 / +0.00 | 2 / -53.02 | **-53.02** |
| arm-lateadd-off | 8 / 667 | early_cheap | 4 / +11.50 | 0 / +0.00 | **+11.50** |
| arm-edge2c (20260925T1225) | 3 / 253 | edge_cap | 1 / +2.74 | 0 / +0.00 | **+2.74** |
| arm-edge2c (20260925T1225) | 3 / 253 | confidence | 4 / +2.34 | 0 / +0.00 | **+2.34** |
| arm-edge2c (20260925T1225) | 3 / 253 | early_cheap | 1 / +1.55 | 0 / +0.00 | **+1.55** |
| arm-btcd | 7 / 556 | early_cheap | 3 / +8.28 | 0 / +0.00 | **+8.28** |
| arm-btcd | 7 / 556 | edge_cap | 1 / +2.74 | 0 / +0.00 | **+2.74** |
| arm-btcd | 7 / 556 | price_ceiling | 1 / +1.95 | 0 / +0.00 | **+1.95** |
| arm-fresh500 | 8 / 667 | fresh_level | 27 / +26.15 | 0 / +0.00 | **+26.15** |
| arm-fresh500 | 8 / 667 | confidence | 4 / +5.45 | 0 / +0.00 | **+5.45** |
| arm-fresh500 | 8 / 667 | early_cheap | 2 / +4.42 | 0 / +0.00 | **+4.42** |
| arm-toxic (20260925T1226) | 3 / 253 | toxic_fresh | 18 / +21.28 | 1 / -131.98 | **-110.70** |
| arm-toxic (20260925T1226) | 3 / 253 | dump_guard | 0 / +0.00 | 1 / -32.73 | **-32.73** |
| arm-hourly-all | 8 / 667 | early_cheap | 4 / +11.50 | 0 / +0.00 | **+11.50** |
| arm-hourly-all | 8 / 667 | dump_guard | 1 / +8.81 | 1 / -20.29 | **-11.48** |
| arm-hourly-all | 8 / 667 | edge_cap | 1 / +2.74 | 0 / +0.00 | **+2.74** |
| arm-hourly-all | 8 / 667 | price_ceiling | 1 / +1.95 | 0 / +0.00 | **+1.95** |
| arm-early-full | 4 / 344 | price_ceiling | 11 / +11.67 | 0 / +0.00 | **+11.67** |
| arm-early-full | 4 / 344 | early_cheap | 2 / +4.87 | 0 / +0.00 | **+4.87** |
| arm-0925 | 3 / 150 | early_cheap | 2 / +4.92 | 0 / +0.00 | **+4.92** |
| arm-0925-hedge20 | 3 / 150 | price_ceiling | 1 / +1.78 | 0 / +0.00 | **+1.78** |
| arm-0925-hedge20 | 3 / 150 | early_cheap | 1 / +1.51 | 0 / +0.00 | **+1.51** |
| arm-0925-nohedge | 3 / 150 | early_cheap | 2 / +4.92 | 0 / +0.00 | **+4.92** |
| arm-live-hedge20 | 4 / 269 | price_ceiling | 11 / +9.98 | 0 / +0.00 | **+9.98** |
| arm-live-hedge20 | 4 / 269 | early_cheap | 3 / +8.28 | 0 / +0.00 | **+8.28** |
| arm-live-hedge20 | 4 / 269 | toxic_fresh | 2 / +2.65 | 0 / +0.00 | **+2.65** |
| arm-live-nohedge | 4 / 269 | price_ceiling | 12 / +10.02 | 0 / +0.00 | **+10.02** |
| arm-live-nohedge | 4 / 269 | early_cheap | 3 / +8.28 | 0 / +0.00 | **+8.28** |
| arm-floor90 | 3 / 259 | price_ceiling | 13 / +11.80 | 0 / +0.00 | **+11.80** |
| arm-floor85 | 3 / 259 | price_ceiling | 11 / +11.03 | 0 / +0.00 | **+11.03** |
| arm-floor80 | 3 / 259 | price_ceiling | 11 / +11.67 | 0 / +0.00 | **+11.67** |
| arm-floor80 | 3 / 259 | dump_guard | 1 / +8.81 | 0 / +0.00 | **+8.81** |
| arm-floor70 | 3 / 259 | price_ceiling | 12 / +11.07 | 0 / +0.00 | **+11.07** |
| arm-floor90-full | 3 / 259 | price_ceiling | 12 / +11.77 | 0 / +0.00 | **+11.77** |
| arm-lockfix | 7 / 587 | toxic_fresh | 42 / +47.49 | 3 / -148.87 | **-101.38** |
| arm-lockfix | 7 / 587 | early_dear | 16 / +5.32 | 0 / +0.00 | **+5.32** |
| arm-lockfix | 7 / 587 | jump_against | 2 / +1.46 | 0 / +0.00 | **+1.46** |
| arm-lockfix | 7 / 587 | price_ceiling | 2 / +1.09 | 0 / +0.00 | **+1.09** |
| arm-toxic15 | 6 / 495 | toxic_fresh | 48 / +59.70 | 3 / -148.87 | **-89.17** |
| arm-toxic15 | 6 / 495 | early_dear | 25 / +11.39 | 0 / +0.00 | **+11.39** |
| arm-toxic15 | 6 / 495 | price_ceiling | 1 / +1.34 | 0 / +0.00 | **+1.34** |
| arm-toxic15 | 6 / 495 | early_cheap | 0 / +0.00 | 1 / -16.16 | **-16.16** |
| arm-toxic0 | 6 / 495 | toxic_fresh | 56 / +62.78 | 3 / -148.87 | **-86.09** |
| arm-toxic0 | 6 / 495 | early_dear | 23 / +10.96 | 0 / +0.00 | **+10.96** |
| arm-toxic0 | 6 / 495 | price_ceiling | 1 / +1.34 | 0 / +0.00 | **+1.34** |
| arm-toxic0 | 6 / 495 | early_cheap | 0 / +0.00 | 1 / -16.16 | **-16.16** |
| arm-norebuy | 6 / 495 | toxic_fresh | 42 / +45.76 | 3 / -148.87 | **-103.11** |
| arm-norebuy | 6 / 495 | early_dear | 25 / +11.63 | 0 / +0.00 | **+11.63** |
| arm-norebuy | 6 / 495 | early_cheap | 0 / +0.00 | 1 / -16.16 | **-16.16** |
| arm-0925b | 6 / 418 | early_cheap | 7 / +18.02 | 1 / -16.16 | **+1.86** |
| arm-0925b | 6 / 418 | dump_guard | 0 / +0.00 | 1 / -83.26 | **-83.26** |
| arm-0914 | 6 / 400 | price_ceiling | 25 / +17.42 | 0 / +0.00 | **+17.42** |
| arm-0914 | 6 / 400 | confidence | 1 / +1.28 | 0 / +0.00 | **+1.28** |
| arm-live-twin | 10 / 823 | toxic_fresh | 46 / +49.44 | 4 / -165.03 | **-115.59** |
| arm-live-twin | 10 / 823 | early_dear | 24 / +11.02 | 0 / +0.00 | **+11.02** |

## 4. Arm vs arm, cumulative on shared closes, by ET day (15-minute coins)

**twin vs 0925b vs 0914 vs toxic15 vs toxic0 vs norebuy vs LIVE (all seven up)** -- 400 shared closes, 10-03 11:15 PM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-live-twin | arm-0925b | arm-0914 | arm-toxic15 | arm-toxic0 | arm-norebuy | LIVE |
|---|---|---|---|---|---|---|---|
| 2026-10-03 (3) | +1.47 on 29 (5.12%), mk 1, lost 0 | +2.37 on 117 (2.02%), mk 2, lost 0 | +0.00 on 0 (-%), mk 0, lost 0 | +1.47 on 29 (5.12%), mk 1, lost 0 | +1.47 on 29 (5.12%), mk 1, lost 0 | +1.47 on 29 (5.12%), mk 1, lost 0 | +1.69 on 34 (4.93%), mk 2, lost 0 |
| 2026-10-04 (96) | +54.77 on 1291 (4.24%), mk 32, lost 1 (BTC OCT041615-15 -1.96) | +56.72 on 2460 (2.31%), mk 57, lost 2 (HYPE OCT042015-1 -45.40; BTC OCT042115-15 -2.54) | -19.03 on 458 (-4.16%), mk 34, lost 2 (BTC OCT042115-15 -19.57; HYPE OCT042015-1 -18.71) | +53.90 on 1148 (4.7%), mk 31, lost 1 (BTC OCT041615-15 -1.62) | +56.10 on 1193 (4.7%), mk 28, lost 1 (BTC OCT041615-15 -1.62) | +53.12 on 1228 (4.33%), mk 29, lost 1 (BTC OCT041615-15 -10.18) | +22.35 on 2398 (0.93%), mk 49, lost 2 (HYPE OCT042015-1 -49.02; BTC OCT041615-15 -6.08) |
| 2026-10-05 (95) | -25.83 on 1653 (-1.56%), mk 31, lost 1 (HYPE OCT050030-3 -70.88) | -5.88 on 2425 (-0.24%), mk 56, lost 1 (HYPE OCT050030-3 -70.72) | -7.72 on 426 (-1.81%), mk 29, lost 1 (HYPE OCT050030-3 -19.44) | -33.74 on 1327 (-2.54%), mk 27, lost 1 (HYPE OCT050030-3 -66.62) | -41.27 on 1306 (-3.16%), mk 27, lost 1 (HYPE OCT050030-3 -75.75) | -26.16 on 1585 (-1.65%), mk 30, lost 1 (HYPE OCT050030-3 -75.30) | -19.08 on 2297 (-0.83%), mk 48, lost 1 (HYPE OCT050030-3 -73.88) |
| 2026-10-06 (96) | +39.38 on 1870 (2.11%), mk 43, lost 1 (NEAR OCT061615-1 -22.38) | +44.26 on 2670 (1.66%), mk 62, lost 2 (NEAR OCT061615-1 -22.30; BTC OCT061615-15 -16.51) | +14.44 on 502 (2.88%), mk 33, lost 0 | +35.96 on 1821 (1.97%), mk 40, lost 1 (NEAR OCT061615-1 -20.59) | +31.68 on 1598 (1.98%), mk 37, lost 1 (NEAR OCT061615-1 -21.35) | +38.77 on 1777 (2.18%), mk 42, lost 1 (NEAR OCT061615-1 -22.40) | -0.84 on 2095 (-0.04%), mk 41, lost 3 (NEAR OCT061615-1 -21.93; BTC OCT061615-15 -16.59; BNB OCT060800-00 -16.16) |
| 2026-10-07 (95) | +54.60 on 1595 (3.42%), mk 29, lost 0 | +77.61 on 2357 (3.29%), mk 49, lost 0 | -3.80 on 454 (-0.84%), mk 27, lost 1 (ZEC OCT070915-15 -17.75) | +56.98 on 1587 (3.59%), mk 28, lost 0 | +54.54 on 1490 (3.66%), mk 28, lost 0 | +56.30 on 1657 (3.4%), mk 30, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 (ZEC OCT070915-15 -83.26) |
| 2026-10-08 (15) | +3.80 on 150 (2.53%), mk 4, lost 0 | +4.39 on 184 (2.39%), mk 4, lost 0 | +0.37 on 20 (1.9%), mk 1, lost 0 | +3.82 on 150 (2.54%), mk 4, lost 0 | +3.26 on 133 (2.45%), mk 4, lost 0 | +2.92 on 128 (2.29%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (400) | +128.19 on 6588 (1.95%), mk 140, lost 3 (HYPE OCT050030-3 -70.88; NEAR OCT061615-1 -22.38; BTC OCT041615-15 -1.96) | +179.47 on 10212 (1.76%), mk 230, lost 5 (HYPE OCT050030-3 -70.72; HYPE OCT042015-1 -45.40; NEAR OCT061615-1 -22.30) | -15.73 on 1859 (-0.85%), mk 124, lost 4 (BTC OCT042115-15 -19.57; HYPE OCT050030-3 -19.44; HYPE OCT042015-1 -18.71) | +118.40 on 6062 (1.95%), mk 131, lost 3 (HYPE OCT050030-3 -66.62; NEAR OCT061615-1 -20.59; BTC OCT041615-15 -1.62) | +105.80 on 5748 (1.84%), mk 125, lost 3 (HYPE OCT050030-3 -75.75; NEAR OCT061615-1 -21.35; BTC OCT041615-15 -1.62) | +126.41 on 6403 (1.97%), mk 136, lost 3 (HYPE OCT050030-3 -75.30; NEAR OCT061615-1 -22.40; BTC OCT041615-15 -10.18) | -30.99 on 8679 (-0.36%), mk 179, lost 7 (ZEC OCT070915-15 -83.26; HYPE OCT050030-3 -73.88; HYPE OCT042015-1 -49.02) |

arm-0914 is flat 20 contracts (its code cannot mirror live size); compare its % on money bet, not its dollars. The twin ran code 7135aa467332 until the 10-06 2:59 PM ET close and 9afb6eca6a91 after (same argv). Differences under $40 are copy noise.

**0925b vs twin vs LIVE (0925b's own window)** -- 418 shared closes, 10-03 8:45 PM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-0925b | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-10-03 (13) | +7.39 on 340 (2.18%), mk 11, lost 0 | +8.21 on 258 (3.18%), mk 6, lost 0 | +8.46 on 253 (3.34%), mk 6, lost 0 |
| 2026-10-04 (96) | +56.72 on 2460 (2.31%), mk 57, lost 2 | +54.77 on 1291 (4.24%), mk 32, lost 1 | +22.35 on 2398 (0.93%), mk 49, lost 2 |
| 2026-10-05 (95) | -5.88 on 2425 (-0.24%), mk 56, lost 1 | -25.83 on 1653 (-1.56%), mk 31, lost 1 | -19.08 on 2297 (-0.83%), mk 48, lost 1 |
| 2026-10-06 (96) | +44.26 on 2670 (1.66%), mk 62, lost 2 | +39.38 on 1870 (2.11%), mk 43, lost 1 | -0.84 on 2095 (-0.04%), mk 41, lost 3 |
| 2026-10-07 (95) | +77.61 on 2357 (3.29%), mk 49, lost 0 | +54.60 on 1595 (3.42%), mk 29, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 |
| 2026-10-08 (23) | +4.39 on 184 (2.39%), mk 4, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (418) | +184.49 on 10434 (1.77%), mk 239, lost 5 | +134.92 on 6817 (1.98%), mk 145, lost 3 | -24.23 on 8898 (-0.27%), mk 183, lost 7 |

**0914 vs twin vs LIVE** -- 400 shared closes, 10-03 11:15 PM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-0914 | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-10-03 (3) | +0.00 on 0 (-%), mk 0, lost 0 | +1.47 on 29 (5.12%), mk 1, lost 0 | +1.69 on 34 (4.93%), mk 2, lost 0 |
| 2026-10-04 (96) | -19.03 on 458 (-4.16%), mk 34, lost 2 | +54.77 on 1291 (4.24%), mk 32, lost 1 | +22.35 on 2398 (0.93%), mk 49, lost 2 |
| 2026-10-05 (95) | -7.72 on 426 (-1.81%), mk 29, lost 1 | -25.83 on 1653 (-1.56%), mk 31, lost 1 | -19.08 on 2297 (-0.83%), mk 48, lost 1 |
| 2026-10-06 (96) | +14.44 on 502 (2.88%), mk 33, lost 0 | +39.38 on 1870 (2.11%), mk 43, lost 1 | -0.84 on 2095 (-0.04%), mk 41, lost 3 |
| 2026-10-07 (95) | -3.80 on 454 (-0.84%), mk 27, lost 1 | +54.60 on 1595 (3.42%), mk 29, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 |
| 2026-10-08 (15) | +0.37 on 20 (1.9%), mk 1, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (400) | -15.73 on 1859 (-0.85%), mk 124, lost 4 | +128.19 on 6588 (1.95%), mk 140, lost 3 | -30.99 on 8679 (-0.36%), mk 179, lost 7 |

**toxic15 vs twin vs LIVE** -- 495 shared closes, 10-03 1:15 AM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-toxic15 | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-10-03 (90) | +53.96 on 1761 (3.06%), mk 35, lost 2 | +39.96 on 1845 (2.17%), mk 40, lost 2 | -28.37 on 2514 (-1.13%), mk 36, lost 2 |
| 2026-10-04 (96) | +53.90 on 1148 (4.7%), mk 31, lost 1 | +54.77 on 1291 (4.24%), mk 32, lost 1 | +22.35 on 2398 (0.93%), mk 49, lost 2 |
| 2026-10-05 (95) | -33.74 on 1327 (-2.54%), mk 27, lost 1 | -25.83 on 1653 (-1.56%), mk 31, lost 1 | -19.08 on 2297 (-0.83%), mk 48, lost 1 |
| 2026-10-06 (96) | +35.96 on 1821 (1.97%), mk 40, lost 1 | +39.38 on 1870 (2.11%), mk 43, lost 1 | -0.84 on 2095 (-0.04%), mk 41, lost 3 |
| 2026-10-07 (95) | +56.98 on 1587 (3.59%), mk 28, lost 0 | +54.60 on 1595 (3.42%), mk 29, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 |
| 2026-10-08 (23) | +3.82 on 150 (2.54%), mk 4, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (495) | +170.88 on 7794 (2.19%), mk 165, lost 5 | +166.68 on 8404 (1.98%), mk 179, lost 5 | -61.06 on 11159 (-0.55%), mk 213, lost 9 |

**toxic0 vs twin vs LIVE** -- 495 shared closes, 10-03 1:15 AM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-toxic0 | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-10-03 (90) | +36.52 on 1518 (2.41%), mk 35, lost 2 | +39.96 on 1845 (2.17%), mk 40, lost 2 | -28.37 on 2514 (-1.13%), mk 36, lost 2 |
| 2026-10-04 (96) | +56.10 on 1193 (4.7%), mk 28, lost 1 | +54.77 on 1291 (4.24%), mk 32, lost 1 | +22.35 on 2398 (0.93%), mk 49, lost 2 |
| 2026-10-05 (95) | -41.27 on 1306 (-3.16%), mk 27, lost 1 | -25.83 on 1653 (-1.56%), mk 31, lost 1 | -19.08 on 2297 (-0.83%), mk 48, lost 1 |
| 2026-10-06 (96) | +31.68 on 1598 (1.98%), mk 37, lost 1 | +39.38 on 1870 (2.11%), mk 43, lost 1 | -0.84 on 2095 (-0.04%), mk 41, lost 3 |
| 2026-10-07 (95) | +54.54 on 1490 (3.66%), mk 28, lost 0 | +54.60 on 1595 (3.42%), mk 29, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 |
| 2026-10-08 (23) | +3.26 on 133 (2.45%), mk 4, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (495) | +140.85 on 7237 (1.95%), mk 159, lost 5 | +166.68 on 8404 (1.98%), mk 179, lost 5 | -61.06 on 11159 (-0.55%), mk 213, lost 9 |

**norebuy vs twin vs LIVE** -- 495 shared closes, 10-03 1:15 AM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-norebuy | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-10-03 (90) | +57.01 on 1882 (3.03%), mk 36, lost 2 | +39.96 on 1845 (2.17%), mk 40, lost 2 | -28.37 on 2514 (-1.13%), mk 36, lost 2 |
| 2026-10-04 (96) | +53.12 on 1228 (4.33%), mk 29, lost 1 | +54.77 on 1291 (4.24%), mk 32, lost 1 | +22.35 on 2398 (0.93%), mk 49, lost 2 |
| 2026-10-05 (95) | -26.16 on 1585 (-1.65%), mk 30, lost 1 | -25.83 on 1653 (-1.56%), mk 31, lost 1 | -19.08 on 2297 (-0.83%), mk 48, lost 1 |
| 2026-10-06 (96) | +38.77 on 1777 (2.18%), mk 42, lost 1 | +39.38 on 1870 (2.11%), mk 43, lost 1 | -0.84 on 2095 (-0.04%), mk 41, lost 3 |
| 2026-10-07 (95) | +56.30 on 1657 (3.4%), mk 30, lost 0 | +54.60 on 1595 (3.42%), mk 29, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 |
| 2026-10-08 (23) | +2.92 on 128 (2.29%), mk 4, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (495) | +181.95 on 8257 (2.2%), mk 171, lost 5 | +166.68 on 8404 (1.98%), mk 179, lost 5 | -61.06 on 11159 (-0.55%), mk 213, lost 9 |

**lockfix vs twin vs LIVE** -- 587 shared closes, 10-02 2:15 AM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-lockfix | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-10-02 (87) | -3.02 on 1271 (-0.24%), mk 20, lost 1 | -12.70 on 1429 (-0.89%), mk 23, lost 1 | -15.66 on 1055 (-1.48%), mk 18, lost 1 |
| 2026-10-03 (95) | +71.75 on 2023 (3.55%), mk 44, lost 2 | +40.16 on 1853 (2.17%), mk 41, lost 2 | -27.67 on 2545 (-1.09%), mk 37, lost 2 |
| 2026-10-04 (96) | +69.90 on 1373 (5.09%), mk 35, lost 0 | +54.77 on 1291 (4.24%), mk 32, lost 1 | +22.35 on 2398 (0.93%), mk 49, lost 2 |
| 2026-10-05 (95) | -20.65 on 1786 (-1.16%), mk 33, lost 1 | -25.83 on 1653 (-1.56%), mk 31, lost 1 | -19.08 on 2297 (-0.83%), mk 48, lost 1 |
| 2026-10-06 (96) | +31.92 on 1855 (1.72%), mk 43, lost 2 | +39.38 on 1870 (2.11%), mk 43, lost 1 | -0.84 on 2095 (-0.04%), mk 41, lost 3 |
| 2026-10-07 (95) | +68.87 on 1879 (3.67%), mk 33, lost 0 | +54.60 on 1595 (3.42%), mk 29, lost 0 | -37.59 on 1773 (-2.12%), mk 36, lost 1 |
| 2026-10-08 (23) | +2.97 on 127 (2.33%), mk 4, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 | +2.48 on 81 (3.08%), mk 3, lost 0 |
| ALL (587) | +221.74 on 10314 (2.15%), mk 212, lost 6 | +154.17 on 9841 (1.57%), mk 203, lost 6 | -76.02 on 12245 (-0.62%), mk 232, lost 10 |

**copy noise: three one-flag arms vs the twin (same code 9afb6e, 498 closes)** -- 498 shared closes, 10-03 1:15 AM ET .. 10-08 5:30 AM ET

| ET day (closes) | arm-toxic15 | arm-toxic0 | arm-norebuy | arm-live-twin |
|---|---|---|---|---|
| 2026-10-03 (91) | +56.07 on 1808 (3.1%), mk 36, lost 2 | +38.17 on 1543 (2.47%), mk 36, lost 2 | +58.65 on 1907 (3.08%), mk 37, lost 2 | +44.47 on 1915 (2.32%), mk 41, lost 2 |
| 2026-10-04 (96) | +53.90 on 1148 (4.7%), mk 31, lost 1 | +56.10 on 1193 (4.7%), mk 28, lost 1 | +53.12 on 1228 (4.33%), mk 29, lost 1 | +54.77 on 1291 (4.24%), mk 32, lost 1 |
| 2026-10-05 (96) | -42.19 on 1417 (-2.98%), mk 28, lost 2 | -49.72 on 1397 (-3.56%), mk 28, lost 2 | -38.03 on 1624 (-2.34%), mk 31, lost 2 | -34.85 on 1731 (-2.01%), mk 32, lost 2 |
| 2026-10-06 (96) | +35.96 on 1821 (1.97%), mk 40, lost 1 | +31.68 on 1598 (1.98%), mk 37, lost 1 | +38.77 on 1777 (2.18%), mk 42, lost 1 | +39.38 on 1870 (2.11%), mk 43, lost 1 |
| 2026-10-07 (96) | +56.98 on 1587 (3.59%), mk 28, lost 0 | +54.54 on 1490 (3.66%), mk 28, lost 0 | +56.30 on 1657 (3.4%), mk 30, lost 0 | +54.60 on 1595 (3.42%), mk 29, lost 0 |
| 2026-10-08 (23) | +3.82 on 150 (2.54%), mk 4, lost 0 | +3.26 on 133 (2.45%), mk 4, lost 0 | +2.92 on 128 (2.29%), mk 4, lost 0 | +3.80 on 150 (2.53%), mk 4, lost 0 |
| ALL (498) | +164.55 on 7932 (2.07%), mk 167, lost 6 | +134.04 on 7353 (1.82%), mk 161, lost 6 | +171.72 on 8320 (2.06%), mk 173, lost 6 | +162.17 on 8552 (1.9%), mk 181, lost 6 |

**09-25 build (hourly-all) vs twin vs LIVE** -- 261 shared closes, 09-29 3:15 PM ET .. 10-02 8:15 AM ET

| ET day (closes) | arm-hourly-all | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-09-29 (35) | +19.05 on 843 (2.26%), mk 14, lost 0 | +15.76 on 701 (2.25%), mk 9, lost 0 | +9.39 on 463 (2.03%), mk 7, lost 0 |
| 2026-09-30 (96) | +55.29 on 2557 (2.16%), mk 56, lost 2 | +41.68 on 2348 (1.78%), mk 40, lost 1 | +12.39 on 1718 (0.72%), mk 29, lost 1 |
| 2026-10-01 (96) | +101.20 on 2151 (4.7%), mk 45, lost 0 | +88.81 on 1796 (4.95%), mk 31, lost 0 | +80.51 on 1695 (4.75%), mk 26, lost 0 |
| 2026-10-02 (34) | +23.69 on 994 (2.38%), mk 14, lost 0 | +18.07 on 764 (2.36%), mk 10, lost 0 | +9.18 on 393 (2.33%), mk 7, lost 0 |
| ALL (261) | +199.23 on 6545 (3.04%), mk 129, lost 2 | +164.32 on 5609 (2.93%), mk 90, lost 1 | +111.47 on 4269 (2.61%), mk 69, lost 1 |

**09-20 settings (live-frozen) vs twin vs LIVE** -- 238 shared closes, 09-29 3:15 PM ET .. 10-02 2:30 AM ET

| ET day (closes) | arm-live-frozen | arm-live-twin | LIVE |
|---|---|---|---|
| 2026-09-29 (35) | +21.99 on 890 (2.47%), mk 14, lost 0 | +15.76 on 701 (2.25%), mk 9, lost 0 | +9.39 on 463 (2.03%), mk 7, lost 0 |
| 2026-09-30 (96) | +54.95 on 2949 (1.86%), mk 56, lost 2 | +41.68 on 2348 (1.78%), mk 40, lost 1 | +12.39 on 1718 (0.72%), mk 29, lost 1 |
| 2026-10-01 (96) | +107.54 on 2257 (4.76%), mk 47, lost 0 | +88.81 on 1796 (4.95%), mk 31, lost 0 | +80.51 on 1695 (4.75%), mk 26, lost 0 |
| 2026-10-02 (11) | +4.50 on 184 (2.44%), mk 3, lost 0 | +4.47 on 183 (2.44%), mk 2, lost 0 | +2.63 on 91 (2.88%), mk 1, lost 0 |
| ALL (238) | +188.97 on 6280 (3.01%), mk 120, lost 2 | +150.72 on 5028 (3.0%), mk 82, lost 1 | +104.92 on 3967 (2.64%), mk 63, lost 1 |

**insurance 0.40 / 0.20 / none on the 09-25 settings, vs btcd and LIVE** -- 150 shared closes, 09-27 11:00 PM ET .. 09-29 1:30 PM ET

| ET day (closes) | arm-0925 | arm-0925-hedge20 | arm-0925-nohedge | arm-btcd | LIVE |
|---|---|---|---|---|---|
| 2026-09-27 (4) | +1.04 on 46 (2.28%), mk 2, lost 0 | +1.03 on 45 (2.31%), mk 2, lost 0 | +1.04 on 46 (2.28%), mk 2, lost 0 | +3.88 on 176 (2.21%), mk 2, lost 0 | +1.84 on 88 (2.1%), mk 1, lost 0 |
| 2026-09-28 (91) | +41.43 on 1753 (2.36%), mk 47, lost 0 | +45.11 on 1862 (2.42%), mk 46, lost 0 | +15.27 on 1858 (0.82%), mk 46, lost 1 | +47.36 on 1977 (2.4%), mk 48, lost 0 | +22.17 on 983 (2.26%), mk 22, lost 1 |
| 2026-09-29 (55) | -0.62 on 1220 (-0.05%), mk 25, lost 1 | +0.03 on 1199 (0.0%), mk 26, lost 1 | -1.88 on 1333 (-0.14%), mk 27, lost 1 | +3.83 on 1366 (0.28%), mk 26, lost 1 | +17.84 on 784 (2.28%), mk 13, lost 0 |
| ALL (150) | +41.85 on 3018 (1.39%), mk 74, lost 1 | +46.17 on 3105 (1.49%), mk 74, lost 1 | +14.43 on 3237 (0.45%), mk 75, lost 2 | +55.07 on 3519 (1.56%), mk 76, lost 1 | +41.86 on 1854 (2.26%), mk 36, lost 1 |

**insurance 0.20 / none on the live settings, vs twin and LIVE** -- 113 shared closes, 09-29 3:15 PM ET .. 09-30 7:15 PM ET

| ET day (closes) | arm-live-hedge20 | arm-live-nohedge | arm-live-twin | LIVE |
|---|---|---|---|---|
| 2026-09-29 (35) | +14.72 on 486 (3.03%), mk 9, lost 0 | +10.05 on 408 (2.46%), mk 9, lost 0 | +15.76 on 701 (2.25%), mk 9, lost 0 | +9.39 on 463 (2.03%), mk 7, lost 0 |
| 2026-09-30 (78) | -10.73 on 1116 (-0.96%), mk 26, lost 1 | -32.92 on 1377 (-2.39%), mk 28, lost 1 | +23.11 on 1702 (1.36%), mk 31, lost 1 | -5.23 on 1095 (-0.48%), mk 21, lost 1 |
| ALL (113) | +3.99 on 1602 (0.25%), mk 35, lost 1 | -22.87 on 1785 (-1.28%), mk 37, lost 1 | +38.87 on 2403 (1.62%), mk 40, lost 1 | +4.17 on 1558 (0.27%), mk 28, lost 1 |

norebuy minus twin, cumulative at each ET day end (bar: never more than $5 behind): 2026-10-03 +17.05; 2026-10-04 +15.40; 2026-10-05 +15.07; 2026-10-06 +14.46; 2026-10-07 +16.16; 2026-10-08 +15.28. Worst +0.00.

## 5. Fill realism: markets both paper and live bought (shared closes)

Paper contracts = the arm's own `signal.take_n` (it takes only what the tape shows at the level it reads; size mirrors live); live contracts = `order.filled`; prices are contract-weighted. Ratio = live / paper.

| paper arm | markets (closes) | ratio median (q25..q75) | live > 2x paper | live < 0.5x | contracts paper / live | live price - paper, median c (q25..q75) | live dearer in |
|---|---|---|---|---|---|---|---|
| arm-live-twin | 216 (823) | 1.00 (1.00..1.86) | 49 | 12 | 11770 / 13193 | +0.04 (+0.00..+0.40) | 101 |
| arm-0925b | 171 (418) | 1.00 (1.00..2.06) | 43 | 15 | 7836 / 8337 | -0.00 (+0.00..+0.31) | 77 |
| arm-toxic15 | 130 (495) | 1.00 (1.00..2.54) | 41 | 7 | 6269 / 7729 | +0.06 (+0.00..+0.39) | 66 |
| arm-norebuy | 141 (495) | 1.00 (1.00..2.28) | 38 | 9 | 7260 / 8338 | +0.10 (+0.00..+0.35) | 77 |
| arm-lockfix | 164 (587) | 1.00 (1.00..2.55) | 45 | 11 | 8230 / 9511 | +0.08 (+0.00..+0.50) | 85 |
| arm-btcd | 184 (556) | 1.00 (0.98..1.29) | 29 | 18 | 10147 / 10428 | +0.00 (+0.00..+0.25) | 71 |
| arm-hourly-all | 208 (667) | 1.00 (0.87..1.31) | 32 | 20 | 11753 / 12022 | +0.00 (+0.00..+0.27) | 79 |

Worst contract gaps, arm-live-twin vs live:

- DOGE OCT030700-00 10-03 7:00 AM ET: paper 2.0 @ 93.80c -> live 123.8 @ 97.84c (x61.9); paper +0.12, live +2.48
- ETH OCT060330-30 10-06 3:30 AM ET: paper 2.0 @ 97.30c -> live 89.0 @ 97.59c (x44.5); paper +0.05, live +2.00
- DOGE OCT011230-30 10-01 12:30 PM ET: paper 1.0 @ 97.10c -> live 30.3 @ 97.51c (x30.3); paper +0.03, live +0.70
- BNB OCT072045-45 10-07 8:45 PM ET: paper 1.0 @ 97.80c -> live 27.6 @ 98.00c (x27.6); paper +0.02, live +0.51
- NEAR OCT071100-00 10-07 11:00 AM ET: paper 1.0 @ 96.40c -> live 27.3 @ 96.95c (x27.3); paper +0.03, live +0.77
- XRP OCT072000-00 10-07 8:00 PM ET: paper 1.0 @ 97.20c -> live 28.0 @ 97.13c (x27.2); paper +0.03, live +0.75
- NEAR SEP301945-45 09-30 7:45 PM ET: paper 5.0 @ 94.80c -> live 127.5 @ 95.59c (x25.5); paper +0.24, live +5.25
- NEAR OCT030645-45 10-03 6:45 AM ET: paper 4.0 @ 94.57c -> live 94.0 @ 97.13c (x23.5); paper -3.46, live -86.95

Worst price gaps (live paid more), arm-live-twin vs live:

- ETH OCT031845-45 10-03 6:45 PM ET: paper @ 85.50c, live @ 92.83c (+7.33c), contracts 18.0 / 133.5; paper +2.45, live +8.94
- XRP SEP301915-15 09-30 7:15 PM ET: paper @ 89.00c, live @ 94.76c (+5.76c), contracts 89.0 / 89.0; paper -24.30, live -42.60
- DOGE OCT030700-00 10-03 7:00 AM ET: paper @ 93.80c, live @ 97.84c (+4.04c), contracts 2.0 / 123.8; paper +0.12, live +2.48
- ETH OCT060100-00 10-06 1:00 AM ET: paper @ 92.40c, live @ 96.10c (+3.70c), contracts 29.3 / 29.3; paper +2.08, live +1.07
- BNB SEP302030-30 09-30 8:30 PM ET: paper @ 94.40c, live @ 97.80c (+3.40c), contracts 86.0 / 28.6; paper +4.50, live +0.59
- XRP OCT041730-30 10-04 5:30 PM ET: paper @ 85.30c, live @ 88.40c (+3.10c), contracts 107.0 / 136.5; paper +14.79, live +14.85

Losing markets (either side), arm-live-twin vs live, with legs (leg, s left, price, n):

- XRP SEP301915-15 09-30 7:15 PM ET: paper 89.0 @ 89.00c -24.30 [['full', 20, 0.89, 89.0]] | live 89.0 @ 94.76c -42.60 [['full', 20, 0.9476, 89.0]]
- SOL OCT022130-30 10-02 9:30 PM ET: paper 104.0 @ 96.33c -45.34 [['full', 19, 0.962, 96.0], ['late_add', 8, 0.979, 8.0]] | live 144.0 @ 93.64c -41.11 [['full', 19, 0.9146, 96.0], ['late_add', 8, 0.98, 48.0]]
- BTC OCT030400-00 10-03 4:00 AM ET: paper 31.6 @ 96.30c -13.37 [['early', 36, 0.963, 31.635]] | live 31.6 @ 96.30c -13.01 [['early', 36, 0.963, 31.64]]
- NEAR OCT030645-45 10-03 6:45 AM ET: paper 4.0 @ 94.57c -3.46 [['early', 37, 0.938, 3.0], ['topup', 30, 0.969, 1.0]] | live 94.0 @ 97.13c -86.95 [['early', 37, 0.9646, 31.3], ['topup', 30, 0.9747, 62.7]]
- BTC OCT041615-15 10-04 4:15 PM ET: paper 91.0 @ 88.60c -1.96 [['early', 45, 0.958, 30.303], ['topup', 10, 0.85, 60.697]] | live 60.6 @ 90.12c -6.08 [['early', 45, 0.9524, 30.3], ['topup', 10, 0.85, 30.3]]
- HYPE OCT050030-30 10-05 12:30 AM ET: paper 116.0 @ 97.21c -70.88 [['full', 22, 0.97, 89.0], ['late_add', 8, 0.979, 27.0]] | live 133.5 @ 97.26c -73.88 [['full', 22, 0.97, 89.0], ['late_add', 8, 0.9777, 44.5]]
- NEAR OCT061615-15 10-06 4:15 PM ET: paper 32.7 @ 97.40c -22.38 [['early', 43, 0.975, 29.637], ['topup', 16, 0.964, 3.03]] | live 29.6 @ 97.50c -21.93 [['early', 43, 0.975, 29.64]]

Worst contract gaps, arm-0925b vs live:

- ETH OCT060100-00 10-06 1:00 AM ET: paper 1.0 @ 97.80c -> live 29.3 @ 96.10c (x29.3); paper +0.02, live +1.07
- ZEC OCT052245-45 10-05 10:45 PM ET: paper 1.0 @ 97.50c -> live 29.0 @ 97.64c (x29.0); paper +0.02, live +0.64
- DOGE OCT080530-30 10-08 5:30 AM ET: paper 1.0 @ 97.70c -> live 28.0 @ 97.80c (x28.0); paper +0.02, live +0.57
- BNB OCT072045-45 10-07 8:45 PM ET: paper 1.0 @ 97.80c -> live 27.6 @ 98.00c (x27.6); paper +0.02, live +0.51
- HYPE OCT041145-45 10-04 11:45 AM ET: paper 4.0 @ 96.40c -> live 90.0 @ 97.93c (x22.5); paper +0.13, live +1.73
- DOGE OCT050600-00 10-05 6:00 AM ET: paper 6.0 @ 95.50c -> live 121.6 @ 96.73c (x20.3); paper +5.29, live +3.71
- NEAR OCT051600-00 10-05 4:00 PM ET: paper 1.5 @ 97.70c -> live 28.3 @ 97.80c (x18.9); paper +0.03, live +0.58
- HYPE OCT042100-00 10-04 9:00 PM ET: paper 2.0 @ 97.20c -> live 29.3 @ 94.29c (x14.7); paper +0.05, live +1.56

Worst price gaps (live paid more), arm-0925b vs live:

- BTC OCT041615-15 10-04 4:15 PM ET: paper @ 85.00c, live @ 90.12c (+5.12c), contracts 136.5 / 60.6; paper +19.26, live -6.08
- ETH OCT050530-30 10-05 5:30 AM ET: paper @ 91.21c, live @ 95.99c (+4.78c), contracts 125.0 / 84.0; paper +10.30, live +3.14
- XRP OCT041730-30 10-04 5:30 PM ET: paper @ 85.00c, live @ 88.40c (+3.40c), contracts 136.5 / 136.5; paper +19.26, live +14.85
- BTC OCT040230-30 10-04 2:30 AM ET: paper @ 94.55c, live @ 97.58c (+3.03c), contracts 67.0 / 12.0; paper +3.41, live +0.27
- BNB OCT040930-30 10-04 9:30 AM ET: paper @ 93.18c, live @ 95.66c (+2.48c), contracts 118.0 / 89.0; paper +7.52, live +3.60
- BTC OCT062330-30 10-06 11:30 PM ET: paper @ 95.90c, live @ 98.00c (+2.10c), contracts 8.0 / 29.3; paper +0.31, live +0.55

Losing markets (either side), arm-0925b vs live, with legs (leg, s left, price, n):

- BTC OCT041615-15 10-04 4:15 PM ET: paper 136.5 @ 85.00c +19.26 [['full', 10, 0.85, 91.0], ['late_add', 10, 0.85, 45.5]] | live 60.6 @ 90.12c -6.08 [['early', 45, 0.9524, 30.3], ['topup', 10, 0.85, 30.3]]
- HYPE OCT042015-15 10-04 8:15 PM ET: paper 138.0 @ 94.73c -45.40 [['full', 24, 0.931, 92.0], ['late_add', 9, 0.98, 46.0]] | live 138.0 @ 95.07c -49.02 [['full', 24, 0.936, 92.0], ['late_add', 9, 0.98, 46.0]]
- HYPE OCT050030-30 10-05 12:30 AM ET: paper 105.3 @ 97.00c -70.72 [['full', 22, 0.97, 89.0], ['late_add', 8, 0.97, 16.35]] | live 133.5 @ 97.26c -73.88 [['full', 22, 0.97, 89.0], ['late_add', 8, 0.9777, 44.5]]
- BTC OCT061615-15 10-06 4:15 PM ET: paper 29.6 @ 95.70c -16.51 [['early', 45, 0.957, 29.637]] | live 29.6 @ 96.00c -16.59 [['early', 45, 0.96, 29.64]]
- NEAR OCT061615-15 10-06 4:15 PM ET: paper 32.7 @ 97.40c -22.30 [['early', 43, 0.975, 29.637], ['topup', 16, 0.964, 3.03]] | live 29.6 @ 97.50c -21.93 [['early', 43, 0.975, 29.64]]

## 6. Insurance level (hedge_belief 0.40 vs 0.20 vs none): markets whose money differs by more than $1 on shared closes

**arm-0925 / arm-0925-hedge20 / arm-0925-nohedge** -- 150 shared closes; 14 markets differ (most by which copy got the fill; the insurance events are the ones with alarms):

- BNB SEP282000-00 09-28 8:00 PM ET: arm-0925 / arm-0925-hedge20 / arm-0925-nohedge = +1.06 / +1.04 / -27.19 (0925 belief 0.17 at 32s (threshold 0.40); 0925-hedge20 belief 0.17 at 32s (threshold 0.20); 0925-nohedge belief 0.01 at 24s (threshold 0.01))
- BTC SEP291330-30 09-29 1:30 PM ET: arm-0925 / arm-0925-hedge20 / arm-0925-nohedge = -23.52 / -23.52 / -26.66 (0925 belief 0.02 at 9s (threshold 0.40); 0925-hedge20 belief 0.02 at 9s (threshold 0.20); 0925-nohedge belief 0.00 at 7s (threshold 0.01))

**arm-live-twin / arm-live-hedge20 / arm-live-nohedge** -- 113 shared closes; 22 markets differ (most by which copy got the fill; the insurance events are the ones with alarms):

- BTC SEP292000-00 09-29 8:00 PM ET: arm-live-twin / arm-live-hedge20 / arm-live-nohedge = +0.00 / +5.50 / +0.00 
- BTC SEP300230-30 09-30 2:30 AM ET: arm-live-twin / arm-live-hedge20 / arm-live-nohedge = +2.48 / +7.92 / +6.28 
- XRP SEP301915-15 09-30 7:15 PM ET: arm-live-twin / arm-live-hedge20 / arm-live-nohedge = -24.30 / -50.88 / -79.32 (live-twin belief 0.39 at 17s (threshold 0.40); live-hedge20 belief 0.19 at 9s (threshold 0.20); live-nohedge belief 0.00 at 2s (threshold 0.01))

