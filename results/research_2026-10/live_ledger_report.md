# Live ledger report -- the main bot's real-money markets, 2026-09-08 .. 2026-10-08

Money is Kalshi's own settlement row per market (results/kalshi_ledger.json written 2026-10-08T09:30:12Z; payout - both sides' cost - fees, as research/pinledger.py computes it). Decisions are the bot's live logs (results/pinrun-live-*.jsonl, 151 files). n is MARKETS everywhere. Main table = the 12 fifteen-minute coin series only; coin race, commodity (the separate commodity bot), the hourly KXBTCD ladder and anything else are tabulated apart in (f). Subaccount bots (ladder, forecaster, dip-seller) are not in this ledger file and are not here.

**All-time (main table):** 1362 markets, **+701.78** net on $66379 bet (1.06%), **45 losing markets** (3.30% per 100, 95% interval 2.42%..4.40%); 34 hedged markets. **Last 14 ET days (2026-09-25..):** 462 markets, +117.22 on $24447 bet (0.48%), 15 lost (3.25% per 100, 1.83%..5.30%).

## a) Per version (chronological; version = the latest LIVE main-bot header in results/VERSIONS.md at the log file's start; the argv in live_versions.json is the real version)

| # | version | first start UTC | last end UTC | hours up | log files | markets | net $ | bet $ | % on bet | $/day up | lost | key flags (first file; `*` = flags differ between its files) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z) | 2026-09-08T06:20:46Z | 2026-09-10T07:06:10Z | 32.3 | 34 | 82 | -14.66 | 1182 | -1.24% | -10.89 | 4 | pin 0.98 tau None-20 size 1 * |
| 2 | v-cond | 2026-09-10T07:47:12Z | 2026-09-10T07:47:14Z | 0.0 | 1 | 0 | - | - | - | - | 0 | pin 0.98 tau 3-30 ceil 0.98 minlvl 1.0 size 20.0 |
| 3 | v-pin995 | 2026-09-10T08:33:28Z | 2026-09-10T23:50:12Z | 15.2 | 2 | 28 | 18.06 | 469 | 3.85% | 28.44 | 1 | pin 0.995 tau 3-30 ceil 0.98 minlvl 1.0 size 20.0 |
| 4 | v-a10 | 2026-09-10T23:50:46Z | 2026-09-11T00:05:09Z | 0.2 | 1 | 0 | - | - | - | - | 0 | pin 0.995 tau 3-30 ceil 0.98 minlvl 1.0 size 20.0 |
| 5 | v-a10b | 2026-09-11T00:12:00Z | 2026-09-11T13:20:06Z | 13.0 | 3 | 25 | 3.67 | 440 | 0.83% | 6.76 | 1 | pin 0.995 tau 3-30 ceil 0.98 minlvl 1.0 size 20.0 |
| 6 | v-a10c | 2026-09-11T13:23:58Z | 2026-09-12T01:59:46Z | 12.6 | 1 | 21 | 16.02 | 345 | 4.65% | 30.52 | 0 | pin 0.995 tau 3-30 ceil 0.98 minlvl 1.0 size 20.0 |
| 7 | v-a12a | 2026-09-12T02:23:39Z | 2026-09-12T18:05:08Z | 15.4 | 10 | 66 | -2.49 | 1046 | -0.24% | -3.89 | 6 | pin 0.995 tau 3-30 ceil 0.98 minlvl 1.0 size 20.0 * |
| 8 | v-a15 | 2026-09-12T18:06:43Z | 2026-09-13T00:05:11Z | 6.0 | 1 | 24 | 8.92 | 410 | 2.17% | 35.83 | 1 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 |
| 9 | v-a16 | 2026-09-13T00:05:44Z | 2026-09-13T03:15:41Z | 3.2 | 1 | 13 | 13.21 | 222 | 5.94% | 100.11 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 |
| 10 | v-brake3 | 2026-09-13T03:20:29Z | 2026-09-13T09:20:09Z | 5.9 | 5 | 17 | 49.19 | 799 | 6.15% | 201.63 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 30..79 |
| 11 | v-a18 | 2026-09-13T09:24:04Z | 2026-09-13T11:05:14Z | 1.7 | 1 | 4 | 13.03 | 153 | 8.51% | 185.44 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 41..43 |
| 12 | v-a20 | 2026-09-13T11:10:01Z | 2026-09-13T11:50:18Z | 0.7 | 2 | 2 | 5.63 | 80 | 7.04% | 202.23 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 43..44 |
| 13 | v-a20b | 2026-09-13T11:57:14Z | 2026-09-13T17:50:05Z | 5.9 | 1 | 7 | 13.74 | 254 | 5.40% | 56.05 | 1 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 44..46 |
| 14 | v-a21 | 2026-09-13T17:51:18Z | 2026-09-13T18:45:44Z | 0.9 | 1 | 1 | 3.36 | 42 | 7.91% | 88.79 | 0 | pin 0.99 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 46..47 |
| 15 | v-revert1 | 2026-09-13T18:49:31Z | 2026-09-13T19:30:56Z | 0.7 | 1 | 1 | 0.88 | 46 | 1.90% | 30.44 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 47..47 |
| 16 | v-a22 | 2026-09-13T19:33:14Z | 2026-09-14T00:35:18Z | 5.0 | 1 | 16 | 30.64 | 682 | 4.49% | 146.05 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 47..52 |
| 17 | v-a24 | 2026-09-14T00:35:05Z | 2026-09-14T03:16:00Z | 2.7 | 1 | 3 | 3.27 | 116 | 2.83% | 29.29 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 52..53 |
| 18 | v-brake20 | 2026-09-14T03:18:22Z | 2026-09-14T06:05:18Z | 2.7 | 2 | 8 | 12.34 | 228 | 5.42% | 107.98 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 53..55 |
| 19 | v-ladder | 2026-09-14T06:12:18Z | 2026-09-14T12:50:11Z | 6.6 | 1 | 19 | 7.40 | 976 | 0.76% | 26.77 | 1 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 54..60 |
| 20 | v-brake2 | 2026-09-14T12:54:36Z | 2026-09-14T14:20:06Z | 1.4 | 1 | 3 | 8.30 | 156 | 5.31% | 139.75 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 56..58 |
| 21 | v-against | 2026-09-14T14:22:54Z | 2026-09-14T15:50:04Z | 1.5 | 1 | 4 | 9.28 | 224 | 4.14% | 153.37 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 58..59 |
| 22 | v-nofloor | 2026-09-14T15:53:06Z | 2026-09-15T04:15:42Z | 12.3 | 2 | 28 | 45.22 | 1641 | 2.76% | 88.16 | 1 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 57..67 |
| 23 | v-withdraw | 2026-09-15T04:19:19Z | 2026-09-17T07:00:05Z | 45.2 | 11 | 83 | 167.35 | 5450 | 3.07% | 88.87 | 3 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.8 minlvl 1.0 size 20.0 auto 67..95 * |
| 24 | v-hedge60 | 2026-09-17T07:25:22Z | 2026-09-17T19:35:14Z | 12.1 | 2 | 23 | 38.69 | 1188 | 3.26% | 76.77 | 0 | pin 0.995 tau 3-30 ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 95..102 * |
| 25 | v-early-full | 2026-09-17T19:41:57Z | 2026-09-18T01:14:26Z | 5.5 | 1 | 20 | 22.12 | 1428 | 1.55% | 95.80 | 1 | pin 0.995 tau 3-30 early x1.0@None-None ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 95..105 |
| 26 | v-a8fix | 2026-09-18T01:18:20Z | 2026-09-18T03:00:41Z | 1.7 | 2 | 6 | 15.23 | 430 | 3.54% | 219.59 | 0 | pin 0.995 tau 3-30 early x1.0@None-None ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 96..97 * |
| 27 | v-early49 | 2026-09-18T03:02:36Z | 2026-09-18T06:50:17Z | 3.8 | 1 | 17 | 39.88 | 893 | 4.46% | 252.23 | 0 | pin 0.995 tau 3-30 early x0.333@None-None ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 99..105 |
| 28 | v-bank8 | 2026-09-18T06:51:05Z | 2026-09-18T17:00:59Z | 10.1 | 3 | 21 | 16.94 | 696 | 2.43% | 40.36 | 0 | pin 0.995 tau 3-30 early x0.333@0.9-None ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 77..79 * |
| 29 | v-early-full2 | 2026-09-18T17:10:13Z | 2026-09-18T22:45:48Z | 5.5 | 2 | 16 | 27.04 | 1041 | 2.60% | 117.22 | 0 | pin 0.995 tau 3-30 early x1.0@0.9-None ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 76..79 |
| 30 | v-bands | 2026-09-18T22:46:12Z | 2026-09-19T04:00:20Z | 5.2 | 1 | 16 | 24.47 | 1124 | 2.18% | 112.19 | 0 | pin 0.995 tau 3-30 early x1.0@0.9-None ceil 0.98 hedge@ 0.6 minlvl 1.0 size 20.0 auto 79..82 |
| 31 | v-cap200 | 2026-09-19T04:03:58Z | 2026-09-19T12:20:03Z | 7.8 | 8 | 24 | -63.48 | 2210 | -2.87% | -196.58 | 2 | pin 0.995 tau 3-30 early x1.0@0.9-None ceil 0.98 hedge@ 0.6 late x1.5<=10s minlvl 1.0 size 20.0 auto 63..110 |
| 32 | v-mirror | 2026-09-19T12:26:03Z | 2026-09-19T18:01:01Z | 5.6 | 1 | 19 | -6.50 | 1706 | -0.38% | -27.92 | 1 | pin 0.995 tau 3-30 early x1.0@0.9-None ceil 0.98 hedge@ 0.6 late x1.5<=10s minlvl 1.0 size 20.0 auto 107..114 |
| 33 | v-taper | 2026-09-19T18:01:45Z | 2026-09-20T02:31:01Z | 8.3 | 4 | 26 | -50.64 | 2227 | -2.27% | -146.33 | 1 | pin 0.995 tau 3-30 early x1.0@0.9-None ceil 0.98 hedge@ 0.6 late x1.5<=10s minlvl 1.0 size 20.0 auto 97..110 |
| 34 | v-nocap | 2026-09-20T02:32:07Z | 2026-09-21T17:00:43Z | 37.3 | 10 | 86 | -15.96 | 5250 | -0.30% | -10.27 | 3 | pin 0.995 tau 3-30 early x1.0@0.9-None ceil 0.98 hedge@ 0.6 late x1.5<=10s minlvl 1.0 size 20.0 auto 70..104 * |
| 35 | v-hedgefull | 2026-09-21T17:03:22Z | 2026-09-21T18:05:09Z | 1.0 | 1 | 5 | 19.59 | 401 | 4.88% | 456.62 | 0 | pin 0.995 tau 3-30 early x1.0@0.9-1.0 ceil 0.98 hedge@ 0.6 late x1.5<=10s minlvl 1.0 size 20.0 auto 76..77 |
| 36 | v-hedgelastweek | 2026-09-21T18:14:18Z | 2026-09-21T20:05:09Z | 1.8 | 1 | 5 | 15.63 | 360 | 4.34% | 203.00 | 0 | pin 0.995 tau 3-30 early x1.0@0.9-1.0 ceil 0.98 hedge@ 0.6 late x1.5<=10s minlvl 1.0 size 20.0 auto 77..79 |
| 37 | v-hedge25 | 2026-09-21T20:12:16Z | 2026-09-22T11:35:20Z | 15.4 | 2 | 16 | -5.39 | 877 | -0.61% | -8.41 | 1 | pin 0.995 tau 3-30 early x1.0@0.9-1.0 ceil 0.98 hedge@ 0.25 late x1.5<=10s minlvl 1.0 size 20.0 auto 76..79 |
| 38 | v-safety1 | 2026-09-22T11:41:49Z | 2026-09-22T20:03:05Z | 8.3 | 2 | 14 | 27.33 | 772 | 3.54% | 78.91 | 0 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.25 late x1.5<=10s minlvl 1.0 size 20.0 auto 78..81 |
| 39 | v-instr1 | 2026-09-22T20:04:18Z | 2026-09-23T00:33:06Z | 4.5 | 1 | 7 | 14.99 | 278 | 5.39% | 80.32 | 0 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.25 late x1.5<=10s minlvl 1.0 size 20.0 auto 81..82 |
| 40 | v-unidefer | 2026-09-23T00:33:17Z | 2026-09-23T07:27:41Z | 6.9 | 1 | 15 | 16.46 | 625 | 2.63% | 57.18 | 1 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.25 late x1.5<=10s minlvl 1.0 size 20.0 auto 82..83 |
| 41 | v-traj1 | 2026-09-23T07:27:58Z | 2026-09-24T02:22:02Z | 18.9 | 2 | 41 | -62.58 | 2507 | -2.50% | -79.49 | 1 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.25 late x1.5<=10s minlvl 1.0 size 20.0 auto 77..88 * |
| 42 | v-cap20 | 2026-09-24T02:22:17Z | 2026-09-24T03:30:41Z | 1.1 | 1 | 2 | 2.08 | 102 | 2.04% | 43.75 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 78..78 |
| 43 | v-lateadd-live | 2026-09-24T03:31:00Z | 2026-09-24T04:21:21Z | 0.8 | 1 | 3 | 4.36 | 229 | 1.90% | 124.66 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 78..79 |
| 44 | v-lateadd-fix | 2026-09-24T04:21:40Z | 2026-09-25T02:20:21Z | 22.0 | 2 | 60 | 88.06 | 2455 | 3.59% | 96.18 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 79..86 |
| 45 | v-btcd1 | 2026-09-25T02:20:42Z | 2026-09-25T06:24:54Z | 4.1 | 2 | 10 | 23.02 | 602 | 3.82% | 135.99 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 86..88 |
| 46 | v-zerotake | 2026-09-25T06:25:09Z | 2026-09-25T08:55:22Z | 2.5 | 1 | 2 | 1.36 | 57 | 2.39% | 13.08 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 88..88 |
| 47 | v-safety2 | 2026-09-25T09:36:48Z | 2026-09-25T12:23:41Z | 2.8 | 1 | 5 | 5.01 | 248 | 2.02% | 43.21 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 88..89 |
| 48 | v-scalein-caps | 2026-09-25T12:23:57Z | 2026-09-27T07:05:01Z | 42.7 | 2 | 91 | -28.89 | 5013 | -0.58% | -16.25 | 3 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 85..99 |
| 49 | v-toxic-live | 2026-09-27T07:05:10Z | 2026-09-27T08:10:41Z | 1.1 | 1 | 2 | 7.94 | 194 | 4.08% | 174.62 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.978 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 86..87 |
| 50 | v-ceiling978 | 2026-09-27T08:10:49Z | 2026-09-28T14:35:41Z | 30.4 | 1 | 29 | 54.00 | 1553 | 3.48% | 42.61 | 0 | pin 0.995 tau 3-30 early x0.333@0.95-1.0 ceil 0.978 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 87..92 |
| 51 | v-onefull | 2026-09-28T14:35:53Z | 2026-09-30T12:11:41Z | 45.6 | 1 | 48 | 69.26 | 2406 | 2.88% | 36.46 | 1 | pin 0.995 tau 3-30 early x0.333@0.9-0.978 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 86..92 |
| 52 | v-topup | 2026-09-30T12:12:06Z | 2026-10-03T08:00:35Z | 67.8 | 1 | 72 | 55.60 | 4338 | 1.28% | 19.68 | 3 | pin 0.995 tau 3-30 early x0.333@0.9-0.978 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 80..96 |
| 53 | v-bankmove | 2026-10-03T08:15:52Z | 2026-10-04T03:22:41Z | 19.1 | 1 | 27 | -33.62 | 1870 | -1.80% | -42.22 | 1 | pin 0.995 tau 3-30 early x0.333@0.9-0.978 ceil 0.98 hedge@ 0.4 late x1.5<=10s toxic True minlvl 1.0 size 20.0 auto 87..94 |
| 54 | v-revert0925 | 2026-10-04T03:22:52Z | 2026-10-04T09:20:21Z | 6.0 | 1 | 12 | 20.32 | 564 | 3.60% | 81.86 | 0 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.4 late x1.5<=10s minlvl 1.0 size 20.0 auto 87..89 |
| 55 | v-revert0925-fullcap | 2026-10-04T09:20:40Z | 2026-10-05T14:23:41Z | 28.8 | 2 | 56 | -49.64 | 2631 | -1.89% | -41.38 | 3 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.4 fullcap 1.0 late x1.5<=10s minlvl 1.0 size 20.0 auto 83..92 |
| 56 | v-skiphype | 2026-10-05T14:24:02Z | 2026-10-06T15:41:01Z | 25.3 | 1 | 49 | 38.89 | 2179 | 1.78% | 36.92 | 1 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.4 fullcap 1.0 skip ['KXHYPE15M'] late x1.5<=10s minlvl 1.0 size 20.0 auto 85..89 |
| 57 | v-bankfix-nodd | 2026-10-06T15:41:22Z | 2026-10-08T09:41:01Z | 41.7 | 2 | 61 | -42.12 | 2961 | -1.42% | -24.22 | 3 | pin 0.995 tau 3-30 early x0.333@0.9-1.0 ceil 0.98 hedge@ 0.4 fullcap 1.0 skip ['KXHYPE15M'] late x1.5<=10s minlvl 1.0 size 20.0 auto 81..89 |

Losing markets and the biggest win, per version (price = first filled leg, our side; tau = seconds to close at that send; size = contracts on the bet side):

- **pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z)** (82 markets, -14.66): biggest win KXSOL15M-26SEP090115-15 2026-09-09 01:15 ET +15.36 on 20 contracts @22.0c.
    - LOST KXNEAR15M-26SEP082045-45 2026-09-08 20:45 ET **-52.60** paid 96.2c tau 22s leg full size 59
    - LOST KXBNB15M-26SEP100130-30 2026-09-10 01:30 ET **-17.60** paid 94.0c tau 26s leg full size 19
    - LOST KXXRP15M-26SEP100100-00 2026-09-10 01:00 ET **-16.61** paid 82.0c tau 21s leg full size 20
    - LOST KXBTC15M-26SEP080315-15 2026-09-08 03:15 ET **-0.00** paid -c tau Nones leg None size 0
- **v-pin995** (28 markets, +18.06): biggest win KXBNB15M-26SEP100830-30 2026-09-10 08:30 ET +2.06 on 20 contracts @89.0c.
    - LOST KXDOGE15M-26SEP101815-15 2026-09-10 18:15 ET **-2.12** paid 10.0c tau 11s leg full size 20
- **v-a10b** (25 markets, +3.67): biggest win KXBTC15M-26SEP102030-30 2026-09-10 20:30 ET +1.76 on 20 contracts @90.6c.
    - LOST KXSOL15M-26SEP110830-30 2026-09-11 08:30 ET **-12.16** paid 59.1c tau 30s leg full size 20
- **v-a10c** (21 markets, +16.02): biggest win KXSOL15M-26SEP111845-45 2026-09-11 18:45 ET +3.20 on 20 contracts @83.0c.
- **v-a12a** (66 markets, -2.49): biggest win KXBNB15M-26SEP120000-00 2026-09-12 00:00 ET +2.82 on 20 contracts @85.0c.
    - LOST KXSOL15M-26SEP112300-00 2026-09-11 23:00 ET **-19.61** paid 97.9c tau 29s leg full size 20
    - LOST KXSOL15M-26SEP120400-00 2026-09-12 04:00 ET **-18.88** paid 94.0c tau 19s leg full size 20
    - LOST KXETH15M-26SEP121115-15 2026-09-12 11:15 ET **-5.16** paid 98.0c tau 29s leg full size 20 HEDGED (hedge side -5.26)
    - LOST KXBTC15M-26SEP121100-00 2026-09-12 11:00 ET **-1.09** paid 90.0c tau 30s leg full size 20 HEDGED (hedge side -2.80)
    - LOST KXSOL15M-26SEP120600-00 2026-09-12 06:00 ET **-0.01** paid -c tau Nones leg None size 1 HEDGED (hedge side -0.05)
    - LOST KXETH15M-26SEP120545-45 2026-09-12 05:45 ET **-0.00** paid -c tau Nones leg None size 1
- **v-a15** (24 markets, +8.92): biggest win KXETH15M-26SEP121745-45 2026-09-12 17:45 ET +3.01 on 20 contracts @84.0c.
    - LOST KXZEC15M-26SEP122000-00 2026-09-12 20:00 ET **-8.63** paid 96.2c tau 25s leg full size 11 HEDGED (hedge side +2.10)
- **v-a16** (13 markets, +13.21): biggest win KXBTC15M-26SEP122115-15 2026-09-12 21:15 ET +2.63 on 20 contracts @86.0c.
- **v-brake3** (17 markets, +49.19): biggest win KXSOL15M-26SEP130145-45 2026-09-13 01:45 ET +9.74 on 74 contracts @86.0c.
- **v-a18** (4 markets, +13.03): biggest win KXSOL15M-26SEP130615-15 2026-09-13 06:15 ET +5.01 on 41 contracts @87.0c.
- **v-a20** (2 markets, +5.63): biggest win KXZEC15M-26SEP130715-15 2026-09-13 07:15 ET +4.83 on 43 contracts @88.0c.
- **v-a20b** (7 markets, +13.74): biggest win KXBTC15M-26SEP130900-00 2026-09-13 09:00 ET +6.21 on 44 contracts @85.0c.
    - LOST KXBNB15M-26SEP131230-30 2026-09-13 12:30 ET **-1.10** paid 92.3c tau 5s leg full size 32 HEDGED (hedge side -3.20)
- **v-a21** (1 markets, +3.36): biggest win KXBTC15M-26SEP131415-15 2026-09-13 14:15 ET +3.36 on 46 contracts @92.2c.
- **v-revert1** (1 markets, +0.88): biggest win KXETH15M-26SEP131515-15 2026-09-13 15:15 ET +0.88 on 47 contracts @98.0c.
- **v-a22** (16 markets, +30.64): biggest win KXBTC15M-26SEP131930-30 2026-09-13 19:30 ET +5.26 on 51 contracts @89.0c.
- **v-a24** (3 markets, +3.27): biggest win KXSOL15M-26SEP132100-00 2026-09-13 21:00 ET +1.79 on 52 contracts @96.3c.
- **v-brake20** (8 markets, +12.34): biggest win KXBTC15M-26SEP140045-45 2026-09-14 00:45 ET +7.98 on 53 contracts @84.0c.
- **v-ladder** (19 markets, +7.40): biggest win KXDOGE15M-26SEP140315-15 2026-09-14 03:15 ET +7.04 on 56 contracts @86.6c.
    - LOST KXBTC15M-26SEP140530-30 2026-09-14 05:30 ET **-34.26** paid 97.2c tau 13s leg full size 60 HEDGED (hedge side +25.20)
- **v-brake2** (3 markets, +8.30): biggest win KXSOL15M-26SEP140930-30 2026-09-14 09:30 ET +4.37 on 57 contracts @91.8c.
- **v-against** (4 markets, +9.28): biggest win KXDOGE15M-26SEP141115-15 2026-09-14 11:15 ET +3.31 on 58 contracts @93.9c.
- **v-nofloor** (28 markets, +45.22): biggest win KXBTC15M-26SEP141930-30 2026-09-14 19:30 ET +11.14 on 59 contracts @80.0c.
    - LOST KXHYPE15M-26SEP141600-00 2026-09-14 16:00 ET **-29.90** paid 95.2c tau 30s leg full size 62 HEDGED (hedge side +30.38)
- **v-withdraw** (83 markets, +167.35): biggest win KXBNB15M-26SEP162115-15 2026-09-16 21:15 ET +15.05 on 91 contracts @82.5c.
    - LOST KXDOGE15M-26SEP160900-00 2026-09-16 09:00 ET **-12.14** paid 97.9c tau 17s leg full size 87 HEDGED (hedge side -13.05)
    - LOST KXNEAR15M-26SEP160430-30 2026-09-16 04:30 ET **-9.22** paid 91.4c tau 21s leg full size 84 HEDGED (hedge side -15.12)
    - LOST KXBNB15M-26SEP161230-30 2026-09-16 12:30 ET **-0.47** paid 97.7c tau 30s leg full size 1 HEDGED (hedge side +0.53)
- **v-hedge60** (23 markets, +38.69): biggest win KXBNB15M-26SEP171500-00 2026-09-17 15:00 ET +6.71 on 100 contracts @92.8c.
- **v-early-full** (20 markets, +22.12): biggest win KXZEC15M-26SEP172115-15 2026-09-17 21:15 ET +12.09 on 99 contracts @87.0c.
    - LOST KXBTC15M-26SEP172115-15 2026-09-17 21:15 ET **-27.87** paid 53.0c tau 38s leg early size 99 HEDGED (hedge side +27.72)
- **v-a8fix** (6 markets, +15.23): biggest win KXXRP15M-26SEP172300-00 2026-09-17 23:00 ET +9.43 on 194 contracts @95.1c.
- **v-early49** (17 markets, +39.88): biggest win KXHYPE15M-26SEP172330-30 2026-09-17 23:30 ET +16.41 on 198 contracts @91.6c.
- **v-bank8** (21 markets, +16.94): biggest win KXXRP15M-26SEP180515-15 2026-09-18 05:15 ET +2.48 on 78 contracts @96.6c.
- **v-early-full2** (16 markets, +27.04): biggest win KXSOL15M-26SEP181600-00 2026-09-18 16:00 ET +4.59 on 78 contracts @93.7c.
- **v-bands** (16 markets, +24.47): biggest win KXBTC15M-26SEP182345-45 2026-09-18 23:45 ET +2.16 on 82 contracts @97.2c.
- **v-cap200** (24 markets, -63.48): biggest win KXZEC15M-26SEP190100-00 2026-09-19 01:00 ET +8.04 on 75 contracts @88.6c.
    - LOST KXBTC15M-26SEP190200-00 2026-09-19 02:00 ET **-66.34** paid 94.4c tau 35s leg early size 70
    - LOST KXBNB15M-26SEP190145-45 2026-09-19 01:45 ET **-57.76** paid 75.0c tau 24s leg full size 76 HEDGED (hedge side +0.24)
- **v-mirror** (19 markets, -6.50): biggest win KXHYPE15M-26SEP191200-00 2026-09-19 12:00 ET +10.59 on 113 contracts @90.0c.
    - LOST KXBNB15M-26SEP191230-30 2026-09-19 12:30 ET **-61.75** paid 97.3c tau 23s leg full size 84 HEDGED (hedge side +21.70)
- **v-taper** (26 markets, -50.64): biggest win KXHYPE15M-26SEP192200-00 2026-09-19 22:00 ET +6.10 on 102 contracts @93.6c.
    - LOST KXBTC15M-26SEP191600-00 2026-09-19 16:00 ET **-107.95** paid 98.0c tau 45s leg early size 110
- **v-nocap** (86 markets, -15.96): biggest win KXBNB15M-26SEP200215-15 2026-09-20 02:15 ET +7.69 on 70 contracts @88.3c.
    - LOST KXXRP15M-26SEP192345-45 2026-09-19 23:45 ET **-64.95** paid 97.7c tau 41s leg early size 104 HEDGED (hedge side -65.52)
    - LOST KXNEAR15M-26SEP211245-45 2026-09-21 12:45 ET **-59.09** paid 91.1c tau 44s leg early size 81 HEDGED (hedge side +16.00)
    - LOST KXHYPE15M-26SEP192345-45 2026-09-19 23:45 ET **-43.92** paid 94.1c tau 33s leg early size 104 HEDGED (hedge side -47.84)
- **v-hedgefull** (5 markets, +19.59): biggest win KXBTC15M-26SEP211315-15 2026-09-21 13:15 ET +11.76 on 114 contracts @89.0c.
- **v-hedgelastweek** (5 markets, +15.63): biggest win KXETH15M-26SEP211445-45 2026-09-21 14:45 ET +6.71 on 77 contracts @90.7c.
- **v-hedge25** (16 markets, -5.39): biggest win KXNEAR15M-26SEP212000-00 2026-09-21 20:00 ET +5.45 on 77 contracts @92.4c.
    - LOST KXHYPE15M-26SEP211815-15 2026-09-21 18:15 ET **-31.27** paid 98.0c tau 43s leg early size 55 HEDGED (hedge side +23.65)
- **v-safety1** (14 markets, +27.33): biggest win KXBTC15M-26SEP221130-30 2026-09-22 11:30 ET +6.14 on 79 contracts @91.7c.
- **v-instr1** (7 markets, +14.99): biggest win KXBTC15M-26SEP221730-30 2026-09-22 17:30 ET +6.29 on 81 contracts @91.7c.
- **v-unidefer** (15 markets, +16.46): biggest win KXSOL15M-26SEP230100-00 2026-09-23 01:00 ET +7.15 on 219 contracts @96.7c.
    - LOST KXDOGE15M-26SEP222245-45 2026-09-22 22:45 ET **-2.47** paid 93.4c tau 12s leg full size 13 HEDGED (hedge side +0.26)
- **v-traj1** (41 markets, -62.58): biggest win KXETH15M-26SEP232130-30 2026-09-23 21:30 ET +6.78 on 77 contracts @90.6c.
    - LOST KXBTC15M-26SEP232030-30 2026-09-23 20:30 ET **-130.41** paid 87.0c tau 26s leg full size 176 HEDGED (hedge side +24.87)
- **v-cap20** (2 markets, +2.08): biggest win KXXRP15M-26SEP232300-00 2026-09-23 23:00 ET +1.59 on 78 contracts @97.5c.
- **v-lateadd-live** (3 markets, +4.36): biggest win KXDOGE15M-26SEP232345-45 2026-09-23 23:45 ET +1.45 on 78 contracts @98.0c.
- **v-lateadd-fix** (60 markets, +88.06): biggest win KXXRP15M-26SEP241700-00 2026-09-24 17:00 ET +17.11 on 124 contracts @85.4c.
- **v-btcd1** (10 markets, +23.02): biggest win KXHYPE15M-26SEP250215-15 2026-09-25 02:15 ET +5.76 on 132 contracts @95.3c.
- **v-zerotake** (2 markets, +1.36): biggest win KXBTC15M-26SEP250300-00 2026-09-25 03:00 ET +0.76 on 29 contracts @97.2c.
- **v-safety2** (5 markets, +5.01): biggest win KXBNB15M-26SEP250645-45 2026-09-25 06:45 ET +2.33 on 115 contracts @97.7c.
- **v-scalein-caps** (91 markets, -28.89): biggest win KXBTC15M-26SEP252245-45 2026-09-25 22:45 ET +22.13 on 141 contracts @83.0c.
    - LOST KXBTC15M-26SEP270000-00 2026-09-27 00:00 ET **-131.98** paid 97.9c tau 30s leg full size 198 HEDGED (hedge side +64.35)
    - LOST KXETH15M-26SEP270230-30 2026-09-27 02:30 ET **-32.73** paid 83.5c tau 17s leg full size 88 HEDGED (hedge side -44.88)
    - LOST KXBNB15M-26SEP261030-30 2026-09-26 10:30 ET **-20.29** paid 59.5c tau 5s leg full size 98 HEDGED (hedge side -56.62)
- **v-toxic-live** (2 markets, +7.94): biggest win KXBTC15M-26SEP270315-15 2026-09-27 03:15 ET +5.55 on 86 contracts @93.1c.
- **v-ceiling978** (29 markets, +54.00): biggest win KXBTC15M-26SEP270430-30 2026-09-27 04:30 ET +7.48 on 130 contracts @93.7c.
- **v-onefull** (48 markets, +69.26): biggest win KXBTC15M-26SEP300230-30 2026-09-30 02:30 ET +8.81 on 129 contracts @92.2c.
    - LOST KXBNB15M-26SEP282000-00 2026-09-28 20:00 ET **-8.26** paid 97.5c tau 44s leg early+topup size 30 HEDGED (hedge side +21.82)
- **v-topup** (72 markets, +55.60): biggest win KXBNB15M-26OCT011000-00 2026-10-01 10:00 ET +16.03 on 132 contracts @84.0c.
    - LOST KXXRP15M-26SEP301915-15 2026-09-30 19:15 ET **-42.60** paid 94.8c tau 20s leg full size 89 HEDGED (hedge side +43.61)
    - LOST KXSOL15M-26OCT022130-30 2026-10-02 21:30 ET **-41.11** paid 91.5c tau 19s leg full+late_add size 96 HEDGED (hedge side +48.96)
    - LOST KXBTC15M-26OCT030400-00 2026-10-03 04:00 ET **-13.01** paid 96.3c tau 36s leg early size 32 HEDGED (hedge side -13.55)
- **v-bankmove** (27 markets, -33.62): biggest win KXETH15M-26OCT031845-45 2026-10-03 18:45 ET +8.94 on 134 contracts @92.8c.
    - LOST KXNEAR15M-26OCT030645-45 2026-10-03 06:45 ET **-86.95** paid 96.5c tau 37s leg early+topup size 94 HEDGED (hedge side +4.85)
- **v-revert0925** (12 markets, +20.32): biggest win KXDOGE15M-26OCT040115-15 2026-10-04 01:15 ET +5.79 on 132 contracts @95.3c.
- **v-revert0925-fullcap** (56 markets, -49.64): biggest win KXXRP15M-26OCT041730-30 2026-10-04 17:30 ET +14.85 on 136 contracts @88.4c.
    - LOST KXHYPE15M-26OCT050030-30 2026-10-05 00:30 ET **-73.88** paid 97.0c tau 22s leg full+late_add size 89 HEDGED (hedge side +13.45)
    - LOST KXHYPE15M-26OCT042015-15 2026-10-04 20:15 ET **-49.02** paid 93.6c tau 24s leg full+late_add size 92 HEDGED (hedge side +39.10)
    - LOST KXBTC15M-26OCT041615-15 2026-10-04 16:15 ET **-6.08** paid 95.2c tau 45s leg early+topup size 30 HEDGED (hedge side +23.63)
- **v-skiphype** (49 markets, +38.89): biggest win KXDOGE15M-26OCT051645-45 2026-10-05 16:45 ET +3.97 on 86 contracts @97.6c.
    - LOST KXBNB15M-26OCT060800-00 2026-10-06 08:00 ET **-16.16** paid 88.0c tau 34s leg early+topup size 89 HEDGED (hedge side -20.45)
- **v-bankfix-nodd** (61 markets, -42.12): biggest win KXETH15M-26OCT061745-45 2026-10-06 17:45 ET +7.33 on 86 contracts @90.9c.
    - LOST KXZEC15M-26OCT070915-15 2026-10-07 09:15 ET **-83.26** paid 93.1c tau 23s leg full size 89
    - LOST KXNEAR15M-26OCT061615-15 2026-10-06 16:15 ET **-21.93** paid 97.5c tau 43s leg early size 30 HEDGED (hedge side +7.41)
    - LOST KXBTC15M-26OCT061615-15 2026-10-06 16:15 ET **-16.59** paid 96.0c tau 45s leg early size 30 HEDGED (hedge side -17.19)

## b) By price of the FIRST filled leg, and by its tau -- all-time and last 14 ET days

1358 of 1362 main-table markets have a logged first fill (the rest: Kalshi settled them, no log order -- see h). Fee = 0.07 x p x (1-p) per contract (taker). 'break-even (measured)' = avg win / (avg win + avg loss) per contract.

### All-time -- price buckets (cents)

| bucket | markets | lost | loss rate per 100 [95% CI] | net $ | bet $ | net $/contract | avg win $/contract | avg loss $/contract | break-even loss rate (1-p-fee at mean price) | break-even (measured win/loss sizes) |
|---|---|---|---|---|---|---|---|---|---|---|
| <90 | 52 | 9 | 17.3% [8.2%, 30.3%] | -9.95 | 2413 | -0.0034 | 0.1357 | -0.4608 | 19.2% (price 79.6c) | 22.7% |
| 90-93 | 69 | 5 | 7.2% [2.4%, 16.1%] | 191.69 | 3763 | 0.0466 | 0.0798 | -0.3566 | 8.0% (price 91.5c) | 18.3% |
| 93-95 | 108 | 8 | 7.4% [3.3%, 14.1%] | -29.17 | 5635 | -0.0049 | 0.0537 | -0.6539 | 5.5% (price 94.1c) | 7.6% |
| 95-96 | 79 | 2 | 2.5% [0.3%, 8.8%] | 129.52 | 4045 | 0.0306 | 0.0400 | -0.3899 | 4.2% (price 95.5c) | 9.3% |
| 96-97 | 186 | 5 | 2.7% [0.9%, 6.2%] | 130.25 | 9717 | 0.0129 | 0.0313 | -0.7892 | 3.2% (price 96.5c) | 3.8% |
| 97-98 | 600 | 10 | 1.7% [0.8%, 3.0%] | 204.47 | 28844 | 0.0069 | 0.0220 | -0.6102 | 2.2% (price 97.6c) | 3.5% |
| >=98 | 264 | 3 | 1.1% [0.2%, 3.3%] | 85.00 | 11960 | 0.0070 | 0.0191 | -0.7804 | 1.8% (price 98.0c) | 2.4% |
| ALL | 1358 | 42 | 3.1% [2.2%, 4.2%] | 701.79 | 66377 | 0.0102 | 0.0338 | -0.5699 | 3.6% (price 96.1c) | 5.6% |

### All-time -- tau buckets (seconds to close at the first filled send)

| bucket | markets | lost | loss rate per 100 [95% CI] | net $ | bet $ | net $/contract | avg win $/contract | avg loss $/contract | break-even loss rate (1-p-fee at mean price) | break-even (measured win/loss sizes) |
|---|---|---|---|---|---|---|---|---|---|---|
| <=10 | 133 | 2 | 1.5% [0.2%, 5.3%] | 408.38 | 8781 | 0.0440 | 0.0470 | -0.1645 | 5.3% (price 94.3c) | 22.2% |
| 11-20 | 219 | 8 | 3.7% [1.6%, 7.1%] | 285.41 | 12119 | 0.0225 | 0.0386 | -0.3939 | 4.3% (price 95.4c) | 8.9% |
| 21-30 | 454 | 18 | 4.0% [2.4%, 6.2%] | -66.89 | 21952 | -0.0029 | 0.0321 | -0.6676 | 3.5% (price 96.2c) | 4.6% |
| 31-45 | 552 | 14 | 2.5% [1.4%, 4.2%] | 74.89 | 23524 | 0.0031 | 0.0276 | -0.5957 | 2.9% (price 96.8c) | 4.4% |

### Last 14 ET days (2026-09-25..) -- price buckets (cents)

| bucket | markets | lost | loss rate per 100 [95% CI] | net $ | bet $ | net $/contract | avg win $/contract | avg loss $/contract | break-even loss rate (1-p-fee at mean price) | break-even (measured win/loss sizes) |
|---|---|---|---|---|---|---|---|---|---|---|
| <90 | 11 | 3 | 27.3% [6.0%, 61.0%] | 22.04 | 840 | 0.0221 | 0.1263 | -0.2516 | 15.5% (price 83.6c) | 33.4% |
| 90-93 | 13 | 1 | 7.7% [0.2%, 36.0%] | 30.68 | 927 | 0.0303 | 0.0784 | -0.4282 | 7.9% (price 91.5c) | 15.5% |
| 93-95 | 27 | 3 | 11.1% [2.4%, 29.2%] | -84.74 | 1889 | -0.0423 | 0.0520 | -0.6477 | 5.6% (price 94.0c) | 7.4% |
| 95-96 | 18 | 1 | 5.6% [0.1%, 27.3%] | 42.71 | 1182 | 0.0346 | 0.0405 | -0.2008 | 4.2% (price 95.5c) | 16.8% |
| 96-97 | 70 | 3 | 4.3% [0.9%, 12.0%] | 18.38 | 4473 | 0.0040 | 0.0302 | -0.7506 | 3.2% (price 96.5c) | 3.9% |
| 97-98 | 237 | 4 | 1.7% [0.5%, 4.3%] | 10.39 | 11204 | 0.0009 | 0.0221 | -0.6804 | 2.3% (price 97.6c) | 3.2% |
| >=98 | 86 | 0 | 0.0% [0.0%, 4.2%] | 77.75 | 3932 | 0.0194 | 0.0194 | - | 1.9% (price 98.0c) | - |
| ALL | 462 | 15 | 3.2% [1.8%, 5.3%] | 117.22 | 24447 | 0.0046 | 0.0315 | -0.5486 | 3.1% (price 96.7c) | 5.4% |

### Last 14 ET days (2026-09-25..) -- tau buckets (seconds to close at the first filled send)

| bucket | markets | lost | loss rate per 100 [95% CI] | net $ | bet $ | net $/contract | avg win $/contract | avg loss $/contract | break-even loss rate (1-p-fee at mean price) | break-even (measured win/loss sizes) |
|---|---|---|---|---|---|---|---|---|---|---|
| <=10 | 41 | 1 | 2.4% [0.1%, 12.9%] | 149.88 | 3941 | 0.0360 | 0.0419 | -0.2070 | 4.7% (price 94.9c) | 16.8% |
| 11-20 | 66 | 3 | 4.5% [0.9%, 12.7%] | 62.08 | 5149 | 0.0116 | 0.0350 | -0.4265 | 3.5% (price 96.3c) | 7.6% |
| 21-30 | 93 | 4 | 4.3% [1.2%, 10.6%] | -159.33 | 7053 | -0.0219 | 0.0263 | -0.7225 | 2.6% (price 97.2c) | 3.5% |
| 31-45 | 262 | 7 | 2.7% [1.1%, 5.4%] | 64.59 | 8304 | 0.0075 | 0.0284 | -0.5052 | 2.9% (price 96.9c) | 5.3% |

## c) Per coin, per ET hour of day, per weekday

| coin | markets | lost | loss rate [95% CI] | net $ | bet $ | % on bet |
|---|---|---|---|---|---|---|
| BTC | 258 | 11 | 4.3% [2.1%, 7.5%] | -44.11 | 13409 | -0.33% |
| BNB | 189 | 8 | 4.2% [1.8%, 8.2%] | 94.98 | 8255 | 1.15% |
| XRP | 172 | 3 | 1.7% [0.4%, 5.0%] | 146.80 | 8073 | 1.82% |
| HYPE | 158 | 5 | 3.2% [1.0%, 7.2%] | -16.23 | 7229 | -0.22% |
| DOGE | 128 | 3 | 2.3% [0.5%, 6.7%] | 204.71 | 6359 | 3.22% |
| NEAR | 121 | 5 | 4.1% [1.4%, 9.4%] | -61.42 | 5639 | -1.09% |
| SOL | 120 | 5 | 4.2% [1.4%, 9.5%] | 104.50 | 6000 | 1.74% |
| ZEC | 109 | 2 | 1.8% [0.2%, 6.5%] | 122.49 | 6060 | 2.02% |
| ETH | 107 | 3 | 2.8% [0.6%, 8.0%] | 150.07 | 5356 | 2.80% |

| ET hour | markets | lost | net $ | % on bet |  | weekday | markets | lost | net $ | % on bet |
|---|---|---|---|---|---|---|---|---|---|---|
| 00 | 67 | 2 | -114.48 | -3.8% |  | Mon | 181 | 6 | 81.66 | 0.9% |
| 01 | 76 | 3 | 60.96 | 1.8% |  | Tue | 164 | 6 | 119.18 | 1.6% |
| 02 | 78 | 2 | 40.96 | 1.0% |  | Wed | 204 | 6 | 66.18 | 0.6% |
| 03 | 53 | 1 | 85.64 | 3.3% |  | Thu | 191 | 4 | 276.52 | 3.2% |
| 04 | 39 | 3 | 13.48 | 0.8% |  | Fri | 186 | 3 | 187.24 | 2.3% |
| 05 | 55 | 2 | 44.04 | 1.7% |  | Sat | 255 | 15 | -166.55 | -1.3% |
| 06 | 64 | 2 | 13.31 | 0.4% |  | Sun | 181 | 5 | 137.55 | 1.5% |
| 07 | 67 | 0 | 99.03 | 2.9% |  |  |  |  |  |  |
| 08 | 63 | 2 | 59.12 | 2.0% |  |  |  |  |  |  |
| 09 | 44 | 2 | -30.62 | -1.4% |  |  |  |  |  |  |
| 10 | 32 | 1 | 45.72 | 2.6% |  |  |  |  |  |  |
| 11 | 39 | 2 | 73.82 | 3.4% |  |  |  |  |  |  |
| 12 | 50 | 4 | -38.70 | -1.6% |  |  |  |  |  |  |
| 13 | 50 | 0 | 66.78 | 3.1% |  |  |  |  |  |  |
| 14 | 45 | 0 | 64.33 | 2.9% |  |  |  |  |  |  |
| 15 | 39 | 0 | 81.85 | 3.8% |  |  |  |  |  |  |
| 16 | 69 | 5 | -68.24 | -1.9% |  |  |  |  |  |  |
| 17 | 52 | 0 | 104.66 | 4.6% |  |  |  |  |  |  |
| 18 | 56 | 2 | 60.01 | 2.2% |  |  |  |  |  |  |
| 19 | 70 | 1 | 68.79 | 1.9% |  |  |  |  |  |  |
| 20 | 80 | 5 | -140.77 | -3.4% |  |  |  |  |  |  |
| 21 | 64 | 2 | 38.02 | 1.2% |  |  |  |  |  |  |
| 22 | 46 | 1 | 84.38 | 4.8% |  |  |  |  |  |  |
| 23 | 64 | 3 | -10.32 | -0.3% |  |  |  |  |  |  |

## d) Loss anatomy -- every losing market, then 60 random winners (seed 7) from the same versions

Seller-check inputs are those logged on the FIRST filled leg (sell_share_3s / taker_n_3s / trade_age_s exist only from v-tradefeed, 2026-09-25; level_age_ms from v-ladder, 09-14). 'ask_seen->limit' shows the sweep: limit above the ask means the bot bid up through the ladder. Additional filled legs of each loser are listed under the table.

| ticker | close ET | version | $ net | bet $ | contracts | legs filled | 1st leg | 1st price | 1st tau s | ask_seen->limit | model conf | edge c | level_age_ms | sell_share_3s | taker_n_3s | trade_age_s | hedge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KXBTC15M-26SEP270000-00 | 2026-09-27 00:00 ET | v-scalein-caps | -131.98 | 193 | 198 | full | full | 0.9789 | 30 | 0.979->0.980 | 0.99800 | 1.76 | 148 | 0.5591 | 62286.76 | 0.171 | belief 0.044 @67.0c n 99.0; belief 0.044 @68.0c n 99.0 | hedge $ 64.35 |
| KXBTC15M-26SEP232030-30 | 2026-09-23 20:30 ET | v-traj1 | -130.41 | 152 | 176 | full | full | 0.8700 | 26 | 0.860->0.980 SWEPT | 0.99896 | 13.05 | 113 | None | None | None | belief 0.111 @79.5c n 21.1; belief 0.111 @81.9c n 8.0; belief 0.083 @87.0c n 66.9; belief 0.083 @87.0c n 80.0 | hedge $ 24.87 |
| KXBTC15M-26SEP191600-00 | 2026-09-19 16:00 ET | v-taper | -107.95 | 108 | 110 | early | early | 0.9800 | 45 | 0.980->0.980 | 0.99944 | 1.81 | 81 | None | None | None | no |
| KXNEAR15M-26OCT030645-45 | 2026-10-03 06:45 ET | v-bankmove | -86.95 | 91 | 94 | early+topup | early | 0.9646 | 37 | 0.938->0.978 SWEPT | 0.99666 | 5.46 | 577 | 0.0 | 85.46 | 0.638 | belief 0.000 @94.9c n 31.3; belief 0.000 @94.8c n 62.7 | hedge $ 4.85 |
| KXZEC15M-26OCT070915-15 | 2026-10-07 09:15 ET | v-bankfix-nodd | -83.26 | 83 | 89 | full | full | 0.9310 | 23 | 0.915->0.980 SWEPT | 0.99951 | 7.91 | 5 | 0.6387 | 6026.15 | 0.037 | no |
| KXHYPE15M-26OCT050030-30 | 2026-10-05 00:30 ET | v-revert0925-fullcap | -73.88 | 86 | 89 | full+late_add | full | 0.9700 | 22 | 0.970->0.980 | 0.99526 | 2.32 | 3133 | 0.8801 | 292.01 | 0.099 | belief 0.031 @86.0c n 89.0 | hedge $ 13.45 |
| KXBTC15M-26SEP190200-00 | 2026-09-19 02:00 ET | v-cap200 | -66.34 | 66 | 70 | early | early | 0.9440 | 35 | 0.943->0.980 SWEPT | 0.99687 | 5.01 | 59 | None | None | None | no |
| KXXRP15M-26SEP192345-45 | 2026-09-19 23:45 ET | v-nocap | -64.95 | 102 | 104 | early | early | 0.9766 | 41 | 0.977->0.980 | 0.99919 | 2.06 | 35 | None | None | None | belief 0.273 @63.0c n 104.0 | hedge $ -65.52 |
| KXBNB15M-26SEP191230-30 | 2026-09-19 12:30 ET | v-mirror | -61.75 | 82 | 84 | full | full | 0.9727 | 23 | 0.915->0.980 SWEPT | 0.99863 | 7.82 | 64 | None | None | None | belief 0.154 @44.0c n 1.0; belief 0.154 @62.0c n 22.0; belief 0.006 @77.0c n 16.0; belief 0.006 @80.0c n 43.8; belief 0.006 @80.0c n 1.7 | hedge $ 21.70 |
| KXNEAR15M-26SEP211245-45 | 2026-09-21 12:45 ET | v-nocap | -59.09 | 74 | 81 | early | early | 0.9110 | 44 | 0.955->0.980 **fill 4c under ask** | 0.99557 | 3.76 | 75 | None | None | None | belief 0.392 @70.0c n 40.5; belief 0.123 @90.5c n 40.5 | hedge $ 16.00 |
| KXBNB15M-26SEP190145-45 | 2026-09-19 01:45 ET | v-cap200 | -57.76 | 57 | 76 | full | full | 0.7498 | 24 | 0.850->0.980 **fill 10c under ask** | 0.99926 | 14.03 | 256 | None | None | None | belief 0.116 @76.0c n 1.0 | hedge $ 0.24 |
| KXNEAR15M-26SEP082045-45 | 2026-09-08 20:45 ET | pre-VERSIONS.md (no en | -52.60 | 52 | 59 | full | full | 0.9620 | 22 | 0.962->0.962 | 0.98174 | 1.72 | None | None | None | None | no |
| KXHYPE15M-26OCT042015-15 | 2026-10-04 20:15 ET | v-revert0925-fullcap | -49.02 | 86 | 92 | full+late_add | full | 0.9360 | 24 | 0.931->0.980 SWEPT | 0.99988 | 6.44 | 23 | 0.7419 | 1262.62 | 0.061 | belief 0.295 @58.5c n 92.0 | hedge $ 39.10 |
| KXHYPE15M-26SEP192345-45 | 2026-09-19 23:45 ET | v-nocap | -43.92 | 98 | 104 | early | early | 0.9410 | 33 | 0.975->0.980 **fill 3c under ask** | 0.99959 | 2.29 | 37 | None | None | None | belief 0.501 @46.0c n 104.0 | hedge $ -47.84 |
| KXXRP15M-26SEP301915-15 | 2026-09-30 19:15 ET | v-topup | -42.60 | 84 | 89 | full | full | 0.9476 | 20 | 0.880->0.980 SWEPT | 1.00000 | 11.26 | 859848 | 0.5562 | 6842.22 | 0.035 | belief 0.394 @51.0c n 89.0 | hedge $ 43.61 |
| KXSOL15M-26OCT022130-30 | 2026-10-02 21:30 ET | v-topup | -41.11 | 88 | 96 | full+late_add | full | 0.9146 | 19 | 0.962->0.980 **fill 5c under ask** | 0.99998 | 3.54 | 24 | 0.6061 | 7130.21 | 0.046 | belief 0.363 @50.0c n 96.0 | hedge $ 48.96 |
| KXBTC15M-26SEP140530-30 | 2026-09-14 05:30 ET | v-ladder | -34.26 | 58 | 60 | full | full | 0.9720 | 13 | 0.979->0.980 | 0.99992 | 1.95 | 62 | None | None | None | belief 0.214 @58.0c n 60.0 | hedge $ 25.20 |
| KXETH15M-26SEP270230-30 | 2026-09-27 02:30 ET | v-scalein-caps | -32.73 | 73 | 88 | full | full | 0.8347 | 17 | 0.860->0.980 | 1.00000 | 13.16 | 92 | 0.7878 | 6431.47 | 0.068 | belief 0.351 @51.0c n 88.0 | hedge $ -44.88 |
| KXHYPE15M-26SEP211815-15 | 2026-09-21 18:15 ET | v-hedge25 | -31.27 | 54 | 55 | early | early | 0.9800 | 43 | 0.980->0.980 | 0.99890 | 1.75 | 57 | None | None | None | belief 0.230 @57.0c n 55.0 | hedge $ 23.65 |
| KXHYPE15M-26SEP141600-00 | 2026-09-14 16:00 ET | v-nofloor | -29.90 | 59 | 62 | full | full | 0.9516 | 30 | 0.950->0.980 SWEPT | 0.99617 | 4.29 | 6465 | None | None | None | belief 0.559 @51.0c n 62.0 | hedge $ 30.38 |
| KXBTC15M-26SEP172115-15 | 2026-09-17 21:15 ET | v-early-full | -27.87 | 52 | 99 | early | early | 0.5300 | 38 | 0.978->0.980 **fill 45c under ask** | 0.99561 | 1.61 | 89 | None | None | None | belief 0.150 @72.0c n 99.0 | hedge $ 27.72 |
| KXNEAR15M-26OCT061615-15 | 2026-10-06 16:15 ET | v-bankfix-nodd | -21.93 | 29 | 30 | early | early | 0.9750 | 43 | 0.975->0.980 | 0.99541 | 1.87 | 816132 | 0.3795 | 52.7 | 0.544 | belief 0.201 @75.0c n 29.6 | hedge $ 7.41 |
| KXBNB15M-26SEP261030-30 | 2026-09-26 10:30 ET | v-scalein-caps | -20.29 | 58 | 98 | full | full | 0.5954 | 5 | 0.890->0.980 **fill 29c under ask** | 0.99722 | 10.04 | 427 | 0.0293 | 2751.67 | 0.092 | belief 0.034 @57.8c n 98.0 | hedge $ -56.62 |
| KXSOL15M-26SEP112300-00 | 2026-09-11 23:00 ET | v-a12a | -19.61 | 20 | 20 | full | full | 0.9790 | 29 | 0.979->0.979 | 0.99968 | 1.92 | None | None | None | None | no |
| KXSOL15M-26SEP120400-00 | 2026-09-12 04:00 ET | v-a12a | -18.88 | 19 | 20 | full | full | 0.9400 | 19 | 0.940->0.940 | 0.99764 | 5.37 | None | None | None | None | no |
| KXBNB15M-26SEP100130-30 | 2026-09-10 01:30 ET | pre-VERSIONS.md (no en | -17.60 | 18 | 19 | full | full | 0.9400 | 26 | 0.940->0.940 | 0.98507 | 4.11 | None | None | None | None | no |
| KXXRP15M-26SEP100100-00 | 2026-09-10 01:00 ET | pre-VERSIONS.md (no en | -16.61 | 16 | 20 | full | full | 0.8200 | 21 | 0.957->0.957 **fill 14c under ask** | 1.00000 | 4.01 | None | None | None | None | no |
| KXBTC15M-26OCT061615-15 | 2026-10-06 16:15 ET | v-bankfix-nodd | -16.59 | 28 | 30 | early | early | 0.9600 | 45 | 0.956->0.980 SWEPT | 0.99505 | 3.61 | 10 | 0.5367 | 16894.91 | 0.035 | belief 0.336 @58.0c n 29.6 | hedge $ -17.19 |
| KXBNB15M-26OCT060800-00 | 2026-10-06 08:00 ET | v-skiphype | -16.16 | 83 | 89 | early+topup | early | 0.8800 | 34 | 0.900->0.980 | 0.99588 | 8.96 | 53 | 0.6293 | 1238.69 | 0.088 | belief 0.144 @22.3c n 29.6; belief 0.144 @23.3c n 59.4 | hedge $ -20.45 |
| KXBTC15M-26OCT030400-00 | 2026-10-03 04:00 ET | v-topup | -13.01 | 30 | 32 | early | early | 0.9630 | 36 | 0.963->0.978 | 0.99651 | 3.10 | 222 | 0.5 | 21770.6 | 0.04 | belief 0.381 @42.9c n 31.6 | hedge $ -13.55 |
| KXSOL15M-26SEP110830-30 | 2026-09-11 08:30 ET | v-a10b | -12.16 | 12 | 20 | full | full | 0.5910 | 30 | 0.700->0.700 **fill 11c under ask** | 0.99508 | 28.04 | None | None | None | None | no |
| KXDOGE15M-26SEP160900-00 | 2026-09-16 09:00 ET | v-withdraw | -12.14 | 85 | 87 | full | full | 0.9793 | 17 | 0.979->0.980 SWEPT | 0.99537 | 1.49 | 845044 | None | None | None | belief 0.485 @15.0c n 87.0 | hedge $ -13.05 |
| KXNEAR15M-26SEP160430-30 | 2026-09-16 04:30 ET | v-withdraw | -9.22 | 77 | 84 | full | full | 0.9139 | 21 | 0.918->0.980 | 1.00000 | 7.67 | 19 | None | None | None | belief 0.766 @18.0c n 84.0 | hedge $ -15.12 |
| KXZEC15M-26SEP122000-00 | 2026-09-12 20:00 ET | v-a15 | -8.63 | 11 | 11 | full | full | 0.9620 | 25 | 0.963->0.963 | 0.99732 | 3.18 | None | None | None | None | belief 0.525 @80.0c n 1.0; belief 0.525 @81.0c n 10.0 | hedge $ 2.10 |
| KXBNB15M-26SEP282000-00 | 2026-09-28 20:00 ET | v-onefull | -8.26 | 30 | 30 | early+topup | early | 0.9749 | 44 | 0.950->0.978 SWEPT | 0.99968 | 4.63 | 116 | 0.2468 | 191.24 | 0.146 | belief 0.172 @30.0c n 30.3 | hedge $ 21.82 |
| KXBTC15M-26OCT041615-15 | 2026-10-04 16:15 ET | v-revert0925-fullcap | -6.08 | 29 | 30 | early+topup | early | 0.9524 | 45 | 0.958->0.980 | 0.99925 | 3.84 | 92 | 0.4591 | 62906.84 | 0.077 | belief 0.395 @37.0c n 30.3 | hedge $ 23.63 |
| KXETH15M-26SEP121115-15 | 2026-09-12 11:15 ET | v-a12a | -5.16 | 20 | 20 | full | full | 0.9800 | 29 | 0.980->0.980 | 0.99533 | 1.40 | None | None | None | None | belief 0.664 @26.0c n 14.0; belief 0.691 @27.0c n 6.0 | hedge $ -5.26 |
| KXDOGE15M-26SEP222245-45 | 2026-09-22 22:45 ET | v-unidefer | -2.47 | 3 | 13 | full | full | 0.9340 | 12 | 0.980->0.980 **fill 5c under ask** | 0.99559 | 1.42 | 866790 | None | None | None | belief 0.051 @94.8c n 2.0; belief 0.051 @98.6c n 11.0 | hedge $ 0.26 |
| KXDOGE15M-26SEP101815-15 | 2026-09-10 18:15 ET | v-pin995 | -2.12 | 2 | 20 | full | full | 0.0998 | 11 | 0.530->0.530 **fill 43c under ask** | 1.00000 | 45.26 | None | None | None | None | no |
| KXBNB15M-26SEP131230-30 | 2026-09-13 12:30 ET | v-a20b | -1.10 | 30 | 32 | full | full | 0.9230 | 5 | 0.920->0.980 SWEPT | 0.99612 | 7.10 | 286 | None | None | None | belief 0.643 @10.0c n 32.0 | hedge $ -3.20 |
| KXBTC15M-26SEP121100-00 | 2026-09-12 11:00 ET | v-a12a | -1.09 | 18 | 20 | full | full | 0.9000 | 30 | 0.900->0.900 | 0.99555 | 8.93 | None | None | None | None | belief 0.887 @14.0c n 20.0 | hedge $ -2.80 |
| KXBNB15M-26SEP161230-30 | 2026-09-16 12:30 ET | v-withdraw | -0.47 | 1 | 1 | full | full | 0.9770 | 30 | 0.977->0.980 | 0.99521 | 1.66 | 229 | None | None | None | belief 0.533 @47.0c n 1.0 | hedge $ 0.53 |
| KXSOL15M-26SEP120600-00 | 2026-09-12 06:00 ET | v-a12a | -0.01 | 1 | 1 | None | None | - | None | -->- | - | - | None | None | None | None | belief 0.020 @94.9c n 1.0 | hedge $ -0.05 |
| KXETH15M-26SEP120545-45 | 2026-09-12 05:45 ET | v-a12a | -0.00 | 0 | 1 | None | None | - | None | -->- | - | - | None | None | None | None | no |
| KXBTC15M-26SEP080315-15 | 2026-09-08 03:15 ET | pre-VERSIONS.md (no en | -0.00 | 0 | 0 | None | None | - | None | -->- | - | - | None | None | None | None | no |

Every filled leg of each losing market (leg#source: l=logged, d=derived from tau for pre-09-17 logs):

- KXBTC15M-26SEP270000-00 2026-09-27 00:00 ET -131.98 (v-scalein-caps), 2 filled legs; log settled -131.98:
    - full#l yes lim 0.980 ask 0.979 exec 0.9789 fill 99.0/99.0 tau 30 | lvl_age 148 ms sell3s 0.5591 tk3s 62286.76 trade_age 0.171 s book_age 37 ms | swept False hdrm 0.1c | fair 0.998 edge 1.756c sigma 0.962123
    - full#l yes lim 0.973 ask 0.973 exec 0.9700 fill 99.0/99.0 tau 30 | lvl_age 50 ms sell3s 0.5831 tk3s 73906.96 trade_age 0.034 s book_age 4 ms | swept False hdrm 0.0c | fair 0.998 edge 2.316c sigma 0.962123
    - HEDGE 2026-09-27T03:59:36Z side no belief 0.044 ask 0.670 limit 0.770 price 0.670 asked 99.0 filled 99.0 status executed tau 24 locked_loss 64.89c
    - HEDGE 2026-09-27T03:59:36Z side no belief 0.044 ask 0.670 limit 0.770 price 0.680 asked 99.0 filled 99.0 status executed tau 24 locked_loss 65.0c
    - first hedge_alarm 2026-09-27T03:59:36Z belief 0.044 tau 24 (2 alarms; 30 hedge_quote records, min belief 0.044)
    - refusals on this market (gate: n): {"close_budget": 1, "confidence": 1, "rebuy_band": 1, "spike": 1}
- KXBTC15M-26SEP232030-30 2026-09-23 20:30 ET -130.41 (v-traj1), 2 filled legs; log settled -130.40:
    - full#l yes lim 0.980 ask 0.860 exec 0.8700 fill 88.0/88.0 tau 26 | lvl_age 113 ms sell3s None tk3s None trade_age None s book_age 2 ms | swept True hdrm 12.0c | fair 0.99896 edge 13.054c sigma 3.459899
    - full#l yes lim 0.980 ask 0.860 exec 0.8613 fill 88.0/88.0 tau 26 | lvl_age 39 ms sell3s None tk3s None trade_age None s book_age 4 ms | swept True hdrm 12.0c | fair 0.99896 edge 13.054c sigma 3.459899
    - HEDGE 2026-09-24T00:29:43Z side no belief 0.111 ask 0.770 limit 0.800 price 0.795 asked 88.0 filled 21.1 status partially_filled_then_canceled tau 17 locked_loss 66.53c
    - HEDGE 2026-09-24T00:29:43Z side no belief 0.111 ask 0.790 limit 0.820 price 0.819 asked 88.0 filled 8.0 status partially_filled_then_canceled tau 17 locked_loss 68.0c
    - HEDGE 2026-09-24T00:29:44Z side no belief 0.083 ask 0.840 limit 0.870 price 0.870 asked 66.9 filled 66.9 status executed tau 16 locked_loss 74.0c
    - HEDGE 2026-09-24T00:29:44Z side no belief 0.083 ask 0.860 limit 0.890 price 0.870 asked 80.0 filled 80.0 status executed tau 16 locked_loss 73.13c
    - first hedge_alarm 2026-09-24T00:29:43Z belief 0.111 tau 17 (2 alarms; 26 hedge_quote records, min belief 0.083)
    - refusals on this market (gate: n): {"close_budget": 1, "confidence": 1}
- KXBTC15M-26SEP191600-00 2026-09-19 16:00 ET -107.95 (v-taper), 1 filled legs; log settled -107.95:
    - early#l no lim 0.980 ask 0.980 exec 0.9800 fill 110.0/110.0 tau 45 | lvl_age 81 ms sell3s None tk3s None trade_age None s book_age 2 ms | swept False hdrm 0.0c | fair 0.00056 edge 1.807c sigma 1.577956
    - refusals on this market (gate: n): {"price_ceiling": 1}
- KXNEAR15M-26OCT030645-45 2026-10-03 06:45 ET -86.95 (v-bankmove), 2 filled legs; log settled -86.96:
    - early#l no lim 0.978 ask 0.938 exec 0.9646 fill 31.3/31.3 tau 37 | lvl_age 577 ms sell3s 0.0 tk3s 85.46 trade_age 0.638 s book_age 15 ms | swept True hdrm 4.0c | fair 0.00334 edge 5.459c sigma 0.000277
    - topup#l no lim 0.980 ask 0.969 exec 0.9747 fill 62.7/62.7 tau 30 | lvl_age 941 ms sell3s 0.0 tk3s 6.0 trade_age 0.978 s book_age 7 ms | swept True hdrm 1.1c | fair 0.00362 edge 2.527c sigma 0.000273
    - HEDGE 2026-10-03T10:44:48Z side yes belief 0.000 ask 0.949 limit 0.999 price 0.949 asked 31.3 filled 31.3 status executed tau 12 locked_loss 91.38c
    - HEDGE 2026-10-03T10:44:48Z side yes belief 0.000 ask 0.948 limit 0.999 price 0.948 asked 62.7 filled 62.7 status executed tau 12 locked_loss 92.27c
    - first hedge_alarm 2026-10-03T10:44:48Z belief 0.000 tau 12 (2 alarms; 37 hedge_quote records, min belief 0.000)
    - refusals on this market (gate: n): {"confidence": 1, "early_once": 1, "max_per_market": 1}
- KXZEC15M-26OCT070915-15 2026-10-07 09:15 ET -83.26 (v-bankfix-nodd), 1 filled legs; log settled -83.26:
    - full#l yes lim 0.980 ask 0.915 exec 0.9310 fill 89.0/89.0 tau 23 | lvl_age 5 ms sell3s 0.6387 tk3s 6026.15 trade_age 0.037 s book_age 2 ms | swept True hdrm 6.5c | fair 0.99951 edge 7.907c sigma 0.197762
    - first hedge_alarm 2026-10-07T13:14:59Z belief 0.000 tau 1 (1 alarms; 23 hedge_quote records, min belief 0.450)
    - refusals on this market (gate: n): {"confidence": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_cap": 1, "market_attempts": 1, "price_ceiling": 1}
- KXHYPE15M-26OCT050030-30 2026-10-05 00:30 ET -73.88 (v-revert0925-fullcap), 2 filled legs; log settled -73.88:
    - full#l no lim 0.980 ask 0.970 exec 0.9700 fill 89.0/89.0 tau 22 | lvl_age 3133 ms sell3s 0.8801 tk3s 292.01 trade_age 0.099 s book_age 7 ms | swept False hdrm 1.0c | fair 0.00474 edge 2.323c sigma 0.005694
    - late_add#l yes lim 0.980 ask 0.979 exec 0.9777 fill 44.5/44.5 tau 8 | lvl_age 850977 ms sell3s 0.4682 tk3s 5062.8 trade_age 0.061 s book_age 0 ms | swept False hdrm 0.1c | fair 0.99612 edge 1.568c sigma 0.008219
    - HEDGE 2026-10-05T04:29:45Z side yes belief 0.031 ask 0.880 limit 0.980 price 0.860 asked 89.0 filled 89.0 status executed tau 15 locked_loss 83.0c
    - first hedge_alarm 2026-10-05T04:29:45Z belief 0.031 tau 15 (1 alarms; 22 hedge_quote records, min belief 0.031)
    - refusals on this market (gate: n): {"confidence": 1, "depth_floor": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_floor": 1, "max_per_market": 1, "rebuy_band": 1}
- KXBTC15M-26SEP190200-00 2026-09-19 02:00 ET -66.34 (v-cap200), 1 filled legs; log settled 0.00:
    - early#l no lim 0.980 ask 0.943 exec 0.9440 fill 70.0/70.0 tau 35 | lvl_age 59 ms sell3s None tk3s None trade_age None s book_age 14 ms | swept True hdrm 3.7c | fair 0.00313 edge 5.011c sigma 2.525906
    - refusals on this market (gate: n): {"confidence": 1, "early_once": 1}
- KXXRP15M-26SEP192345-45 2026-09-19 23:45 ET -64.95 (v-nocap), 1 filled legs; log settled -64.95:
    - early#l no lim 0.980 ask 0.977 exec 0.9766 fill 104.0/104.0 tau 41 | lvl_age 35 ms sell3s None tk3s None trade_age None s book_age 1 ms | swept False hdrm 0.3c | fair 0.00081 edge 2.062c sigma 0.00011
    - HEDGE 2026-09-20T03:44:30Z side yes belief 0.273 ask 0.630 limit 0.660 price 0.630 asked 104.0 filled 104.0 status executed tau 30 locked_loss 60.66c
    - first hedge_alarm 2026-09-20T03:44:30Z belief 0.273 tau 30 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"close_budget": 1, "depth_floor": 1, "early_once": 1, "price_ceiling": 1}
- KXBNB15M-26SEP191230-30 2026-09-19 12:30 ET -61.75 (v-mirror), 2 filled legs; log settled -61.75:
    - full#l yes lim 0.980 ask 0.915 exec 0.9727 fill 82.8/171.0 tau 23 | lvl_age 64 ms sell3s None tk3s None trade_age None s book_age 0 ms | swept True hdrm 6.5c | fair 0.99863 edge 7.818c sigma 0.037158
    - full#l yes lim 0.980 ask 0.980 exec 0.9787 fill 1.7/35.0 tau 23 | lvl_age 9 ms sell3s None tk3s None trade_age None s book_age 2 ms | swept False hdrm 0.0c | fair 0.99863 edge 1.726c sigma 0.037158
    - HEDGE 2026-09-19T16:29:49Z side no belief 0.154 ask 0.440 limit - price 0.440 asked 28.0 filled 1.0 status partially_filled_then_canceled tau 11 locked_loss 41.27c
    - HEDGE 2026-09-19T16:29:49Z side no belief 0.154 ask 0.570 limit - price 0.570 asked 1.7 filled 0.0 status canceled tau 11 locked_loss 54.87c
    - HEDGE 2026-09-19T16:29:50Z side no belief 0.154 ask 0.720 limit - price 0.620 asked 22.0 filled 22.0 status executed tau 10 locked_loss 59.27c
    - HEDGE 2026-09-19T16:29:50Z side no belief 0.154 ask 0.620 limit - price 0.620 asked 1.7 filled 0.0 status canceled tau 10 locked_loss 59.87c
    - HEDGE 2026-09-19T16:29:51Z side no belief 0.006 ask 0.770 limit - price 0.770 asked 16.0 filled 16.0 status executed tau 9 locked_loss 74.27c
    - HEDGE 2026-09-19T16:29:51Z side no belief 0.006 ask 0.770 limit - price 0.770 asked 1.7 filled 0.0 status canceled tau 9 locked_loss 74.87c
    - HEDGE 2026-09-19T16:29:52Z side no belief 0.006 ask 0.800 limit - price 0.800 asked 43.8 filled 43.8 status executed tau 8 locked_loss 77.27c
    - HEDGE 2026-09-19T16:29:52Z side no belief 0.006 ask 0.800 limit - price 0.800 asked 1.7 filled 1.7 status executed tau 8 locked_loss 77.87c
    - first hedge_alarm 2026-09-19T16:29:49Z belief 0.154 tau 11 (2 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"confidence": 1, "max_per_market": 1, "price_ceiling": 1, "staged_none": 1}
- KXNEAR15M-26SEP211245-45 2026-09-21 12:45 ET -59.09 (v-nocap), 1 filled legs; log settled -59.09:
    - early#l yes lim 0.980 ask 0.955 exec 0.9110 fill 81.0/81.0 tau 44 | lvl_age 75 ms sell3s None tk3s None trade_age None s book_age 5 ms | swept False hdrm 2.5c | fair 0.99557 edge 3.756c sigma 0.000728
    - HEDGE 2026-09-21T16:44:29Z side no belief 0.392 ask 0.710 limit 0.740 price 0.700 asked 40.5 filled 40.5 status executed tau 31 locked_loss 61.1c
    - HEDGE 2026-09-21T16:44:32Z side no belief 0.123 ask 0.905 limit 0.935 price 0.905 asked 40.5 filled 40.5 status executed tau 28 locked_loss 81.6c
    - first hedge_alarm 2026-09-21T16:44:18Z belief 0.569 tau 42 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"confidence": 1, "depth_floor": 1, "early_once": 1, "edge_floor": 1, "price_ceiling": 1, "rebuy_band": 1}
- KXBNB15M-26SEP190145-45 2026-09-19 01:45 ET -57.76 (v-cap200), 1 filled legs; log settled -57.76:
    - full#l yes lim 0.980 ask 0.850 exec 0.7498 fill 76.0/76.0 tau 24 | lvl_age 256 ms sell3s None tk3s None trade_age None s book_age 6 ms | swept False hdrm 13.0c | fair 0.99926 edge 14.034c sigma 0.027949
    - HEDGE 2026-09-19T05:44:39Z side no belief 0.268 ask 0.510 limit - price 0.510 asked 7.0 filled 0.0 status canceled tau 21 locked_loss 25.98c
    - HEDGE 2026-09-19T05:44:40Z side no belief 0.147 ask 0.700 limit - price 0.700 asked 76.0 filled 0.0 status canceled tau 20 locked_loss 44.98c
    - HEDGE 2026-09-19T05:44:41Z side no belief 0.116 ask 0.760 limit - price 0.760 asked 25.0 filled 1.0 status partially_filled_then_canceled tau 19 locked_loss 50.98c
    - first hedge_alarm 2026-09-19T05:44:37Z belief 0.227 tau 23 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"both_sides": 1, "confidence": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_floor": 1, "price_ceiling": 1, "rebuy_band": 1}
- KXNEAR15M-26SEP082045-45 2026-09-08 20:45 ET -52.60 (pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z)), 3 filled legs; log settled -52.60:
    - full#d no lim 0.962 ask 0.962 exec 0.9620 fill 20.0/20.0 tau 22 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 90 ms | swept None hdrm Nonec | fair 0.01826 edge 1.718c sigma 0.000278
    - full#d no lim 0.956 ask 0.956 exec 0.9560 fill 20.0/20.0 tau 21 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 21 ms | swept None hdrm Nonec | fair 0.01235 edge 2.87c sigma 0.000278
    - full#d no lim 0.730 ask 0.730 exec 0.7300 fill 19.0/20.0 tau 17 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 13 ms | swept None hdrm Nonec | fair 0.00173 edge 25.447c sigma 0.000275
- KXHYPE15M-26OCT042015-15 2026-10-04 20:15 ET -49.02 (v-revert0925-fullcap), 2 filled legs; log settled -49.02:
    - full#l no lim 0.980 ask 0.931 exec 0.9360 fill 92.0/92.0 tau 24 | lvl_age 23 ms sell3s 0.7419 tk3s 1262.62 trade_age 0.061 s book_age 3 ms | swept True hdrm 4.9c | fair 0.00012 edge 6.439c sigma 0.003725
    - late_add#l yes lim 0.980 ask 0.980 exec 0.9800 fill 46.0/46.0 tau 9 | lvl_age 849867 ms sell3s 0.2698 tk3s 2011.09 trade_age 0.09 s book_age 33 ms | swept False hdrm 0.0c | fair 0.99677 edge 1.539c sigma 0.004104
    - HEDGE 2026-10-05T00:14:44Z side yes belief 0.295 ask 0.550 limit 0.650 price 0.585 asked 92.0 filled 92.0 status executed tau 16 locked_loss 52.1c
    - first hedge_alarm 2026-10-05T00:14:44Z belief 0.295 tau 16 (1 alarms; 24 hedge_quote records, min belief 0.295)
    - refusals on this market (gate: n): {"confidence": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_floor": 1, "max_per_market": 1, "price_ceiling": 1, "rebuy_band": 1}
- KXHYPE15M-26SEP192345-45 2026-09-19 23:45 ET -43.92 (v-nocap), 1 filled legs; log settled -43.92:
    - early#l no lim 0.980 ask 0.975 exec 0.9410 fill 104.0/104.0 tau 33 | lvl_age 37 ms sell3s None tk3s None trade_age None s book_age 6 ms | swept False hdrm 0.5c | fair 0.00041 edge 2.288c sigma 0.007912
    - HEDGE 2026-09-20T03:44:31Z side yes belief 0.501 ask 0.460 limit 0.490 price 0.460 asked 104.0 filled 104.0 status executed tau 29 locked_loss 40.1c
    - first hedge_alarm 2026-09-20T03:44:29Z belief 0.437 tau 31 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"close_budget": 1, "depth_floor": 1, "early_once": 1, "jump_against": 1, "price_ceiling": 1}
- KXXRP15M-26SEP301915-15 2026-09-30 19:15 ET -42.60 (v-topup), 1 filled legs; log settled -42.59:
    - full#l yes lim 0.980 ask 0.880 exec 0.9476 fill 89.0/89.0 tau 20 | lvl_age 859848 ms sell3s 0.5562 tk3s 6842.22 trade_age 0.035 s book_age 3 ms | swept True hdrm 10.0c | fair 1.0 edge 11.261c sigma 8.4e-05
    - HEDGE 2026-09-30T23:14:43Z side no belief 0.394 ask 0.250 limit 0.350 price 0.250 asked 89.0 filled 0.0 status canceled tau 17 locked_loss 19.76c
    - HEDGE 2026-09-30T23:14:44Z side no belief 0.394 ask 0.500 limit 0.600 price 0.510 asked 89.0 filled 89.0 status executed tau 16 locked_loss 45.76c
    - first hedge_alarm 2026-09-30T23:14:43Z belief 0.394 tau 17 (1 alarms; 20 hedge_quote records, min belief 0.394)
    - refusals on this market (gate: n): {"confidence": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_floor": 1, "price_ceiling": 1, "rebuy_band": 1}
- KXSOL15M-26OCT022130-30 2026-10-02 21:30 ET -41.11 (v-topup), 2 filled legs; log settled -41.11:
    - full#l no lim 0.980 ask 0.962 exec 0.9146 fill 96.0/96.0 tau 19 | lvl_age 24 ms sell3s 0.6061 tk3s 7130.21 trade_age 0.046 s book_age 0 ms | swept False hdrm 1.8c | fair 2e-05 edge 3.542c sigma 0.005964
    - late_add#l yes lim 0.980 ask 0.979 exec 0.9800 fill 48.0/48.0 tau 8 | lvl_age 851005 ms sell3s 0.2151 tk3s 7964.18 trade_age 0.055 s book_age 1 ms | swept True hdrm 0.1c | fair 0.99998 edge 1.954c sigma 0.00665
    - HEDGE 2026-10-03T01:29:46Z side yes belief 0.363 ask 0.500 limit 0.600 price 0.500 asked 96.0 filled 96.0 status executed tau 14 locked_loss 41.46c
    - first hedge_alarm 2026-10-03T01:29:46Z belief 0.363 tau 14 (1 alarms; 19 hedge_quote records, min belief 0.363)
    - refusals on this market (gate: n): {"confidence": 1, "edge_floor": 1, "max_per_market": 1, "price_ceiling": 1, "rebuy_band": 1}
- KXBTC15M-26SEP140530-30 2026-09-14 05:30 ET -34.26 (v-ladder), 1 filled legs; log settled -34.26:
    - full#d no lim 0.980 ask 0.979 exec 0.9720 fill 60.0/60.0 tau 13 | lvl_age 62 ms sell3s None tk3s None trade_age None s book_age 2 ms | swept False hdrm 0.1c | fair 8e-05 edge 1.948c sigma 4.073757
    - HEDGE 2026-09-14T09:29:49Z side yes belief 0.214 ask 0.430 limit - price 0.430 asked 0.0 filled 0.0 status canceled tau 11 locked_loss 40.2c
    - HEDGE 2026-09-14T09:29:50Z side yes belief 0.214 ask 0.610 limit - price 0.580 asked 60.0 filled 60.0 status executed tau 10 locked_loss 55.2c
    - first hedge_alarm 2026-09-14T09:29:49Z belief 0.214 tau 11 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"both_sides": 1, "confidence": 1, "depth_floor": 1, "edge_floor": 1, "price_ceiling": 1}
- KXETH15M-26SEP270230-30 2026-09-27 02:30 ET -32.73 (v-scalein-caps), 1 filled legs; log settled -32.72:
    - full#l yes lim 0.980 ask 0.860 exec 0.8347 fill 88.0/88.0 tau 17 | lvl_age 92 ms sell3s 0.7878 tk3s 6431.47 trade_age 0.068 s book_age 0 ms | swept False hdrm 12.0c | fair 1.0 edge 13.157c sigma 0.086939
    - HEDGE 2026-09-27T06:29:50Z side no belief 0.351 ask 0.500 limit 0.600 price 0.510 asked 88.0 filled 88.0 status executed tau 10 locked_loss 34.47c
    - first hedge_alarm 2026-09-27T06:29:50Z belief 0.351 tau 10 (1 alarms; 17 hedge_quote records, min belief 0.351)
    - refusals on this market (gate: n): {"confidence": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_floor": 1, "price_ceiling": 1}
- KXHYPE15M-26SEP211815-15 2026-09-21 18:15 ET -31.27 (v-hedge25), 1 filled legs; log settled -31.27:
    - early#l yes lim 0.980 ask 0.980 exec 0.9800 fill 55.0/55.0 tau 43 | lvl_age 57 ms sell3s None tk3s None trade_age None s book_age 30 ms | swept False hdrm 0.0c | fair 0.9989 edge 1.753c sigma 0.007384
    - HEDGE 2026-09-21T22:14:26Z side no belief 0.230 ask 0.550 limit 0.580 price 0.570 asked 55.0 filled 55.0 status executed tau 34 locked_loss 55.0c
    - first hedge_alarm 2026-09-21T22:14:26Z belief 0.230 tau 34 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"confidence": 1, "depth_floor": 1, "early_once": 1, "edge_floor": 1, "price_ceiling": 1}
- KXHYPE15M-26SEP141600-00 2026-09-14 16:00 ET -29.90 (v-nofloor), 1 filled legs; log settled -29.90:
    - full#d no lim 0.980 ask 0.950 exec 0.9516 fill 62.0/62.0 tau 30 | lvl_age 6465 ms sell3s None tk3s None trade_age None s book_age 94 ms | swept True hdrm 3.0c | fair 0.00383 edge 4.285c sigma 0.003675
    - HEDGE 2026-09-14T19:59:41Z side yes belief 0.559 ask 0.540 limit - price 0.510 asked 62.0 filled 62.0 status executed tau 19 locked_loss 46.16c
    - first hedge_alarm 2026-09-14T19:59:41Z belief 0.559 tau 19 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"both_sides": 1}
- KXBTC15M-26SEP172115-15 2026-09-17 21:15 ET -27.87 (v-early-full), 1 filled legs; log settled 0.00:
    - early#l yes lim 0.980 ask 0.978 exec 0.5300 fill 99.0/99.0 tau 38 | lvl_age 89 ms sell3s None tk3s None trade_age None s book_age 6 ms | swept False hdrm 0.2c | fair 0.99561 edge 1.61c sigma 3.608357
    - HEDGE 2026-09-18T01:14:24Z side no belief 0.214 ask 0.630 limit - price 0.630 asked 99.0 filled 0.0 status canceled tau 36 locked_loss 16.0c
    - HEDGE 2026-09-18T01:14:25Z side no belief 0.214 ask 0.660 limit - price 0.660 asked 99.0 filled 0.0 status canceled tau 35 locked_loss 19.0c
    - HEDGE 2026-09-18T01:14:26Z side no belief 0.150 ask 0.720 limit - price 0.720 asked 99.0 filled 99.0 status executed tau 34 locked_loss 25.0c
    - first hedge_alarm 2026-09-18T01:14:24Z belief 0.214 tau 36 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"confidence": 1, "early_once": 1}
- KXNEAR15M-26OCT061615-15 2026-10-06 16:15 ET -21.93 (v-bankfix-nodd), 1 filled legs; log settled -21.93:
    - early#l no lim 0.980 ask 0.975 exec 0.9750 fill 29.6/29.6 tau 43 | lvl_age 816132 ms sell3s 0.3795 tk3s 52.7 trade_age 0.544 s book_age 7 ms | swept False hdrm 0.5c | fair 0.00459 edge 1.87c sigma 0.000722
    - HEDGE 2026-10-06T20:14:35Z side yes belief 0.201 ask 0.800 limit 0.900 price 0.750 asked 29.6 filled 29.6 status executed tau 25 locked_loss 72.5c
    - first hedge_alarm 2026-10-06T20:14:35Z belief 0.201 tau 25 (1 alarms; 43 hedge_quote records, min belief 0.201)
    - refusals on this market (gate: n): {"confidence": 1, "depth_floor": 1, "dump_guard": 1, "dumped(A10)": 1, "early_once": 1, "edge_floor": 1, "price_ceiling": 1}
- KXBNB15M-26SEP261030-30 2026-09-26 10:30 ET -20.29 (v-scalein-caps), 1 filled legs; log settled -20.29:
    - full#l no lim 0.980 ask 0.890 exec 0.5954 fill 98.0/98.0 tau 5 | lvl_age 427 ms sell3s 0.0293 tk3s 2751.67 trade_age 0.092 s book_age 15 ms | swept False hdrm 9.0c | fair 0.00278 edge 10.037c sigma 0.013617
    - HEDGE 2026-09-26T14:29:55Z side yes belief 0.034 ask 0.540 limit 0.640 price 0.578 asked 98.0 filled 98.0 status executed tau 5 locked_loss 17.31c
    - first hedge_alarm 2026-09-26T14:29:55Z belief 0.034 tau 5 (1 alarms; 5 hedge_quote records, min belief 0.034)
    - refusals on this market (gate: n): {"confidence": 1, "spike": 1}
- KXSOL15M-26SEP112300-00 2026-09-11 23:00 ET -19.61 (v-a12a), 1 filled legs; log settled -19.61:
    - full#d no lim 0.979 ask 0.979 exec 0.9790 fill 20.0/20.0 tau 29 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 26 ms | swept None hdrm Nonec | fair 0.00032 edge 1.924c sigma 0.00429
- KXSOL15M-26SEP120400-00 2026-09-12 04:00 ET -18.88 (v-a12a), 1 filled legs; log settled -18.88:
    - full#d yes lim 0.940 ask 0.940 exec 0.9400 fill 20.0/20.0 tau 19 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 3 ms | swept None hdrm Nonec | fair 0.99764 edge 5.369c sigma 0.003568
- KXBNB15M-26SEP100130-30 2026-09-10 01:30 ET -17.60 (pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z)), 1 filled legs; log settled -17.60:
    - full#d yes lim 0.940 ask 0.940 exec 0.9400 fill 18.6/18.6 tau 26 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 2 ms | swept None hdrm Nonec | fair 0.98507 edge 4.112c sigma 0.035339
- KXXRP15M-26SEP100100-00 2026-09-10 01:00 ET -16.61 (pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z)), 1 filled legs; log settled -16.61:
    - full#d yes lim 0.957 ask 0.957 exec 0.8200 fill 20.0/20.0 tau 21 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 2 ms | swept None hdrm Nonec | fair 1.0 edge 4.012c sigma 7.9e-05
- KXBTC15M-26OCT061615-15 2026-10-06 16:15 ET -16.59 (v-bankfix-nodd), 1 filled legs; log settled -16.59:
    - early#l no lim 0.980 ask 0.956 exec 0.9600 fill 29.6/29.6 tau 45 | lvl_age 10 ms sell3s 0.5367 tk3s 16894.91 trade_age 0.035 s book_age 1 ms | swept True hdrm 2.4c | fair 0.00495 edge 3.611c sigma 1.63326
    - HEDGE 2026-10-06T20:14:46Z side yes belief 0.336 ask 0.580 limit 0.680 price 0.580 asked 29.6 filled 29.6 status executed tau 14 locked_loss 54.0c
    - first hedge_alarm 2026-10-06T20:14:46Z belief 0.336 tau 14 (1 alarms; 45 hedge_quote records, min belief 0.336)
    - refusals on this market (gate: n): {"against_thin": 1, "confidence": 1, "depth_floor": 1, "early_once": 1, "edge_floor": 1, "staged_none": 1}
- KXBNB15M-26OCT060800-00 2026-10-06 08:00 ET -16.16 (v-skiphype), 2 filled legs; log settled -16.16:
    - early#l yes lim 0.980 ask 0.900 exec 0.8800 fill 29.6/29.6 tau 34 | lvl_age 53 ms sell3s 0.6293 tk3s 1238.69 trade_age 0.088 s book_age 8 ms | swept False hdrm 8.0c | fair 0.99588 edge 8.958c sigma 0.009201
    - topup#l yes lim 0.980 ask 0.960 exec 0.9629 fill 59.4/59.4 tau 30 | lvl_age 723 ms sell3s 0.0 tk3s 115.52 trade_age 0.408 s book_age 0 ms | swept True hdrm 2.0c | fair 0.99803 edge 3.534c sigma 0.009212
    - HEDGE 2026-10-06T11:59:38Z side no belief 0.144 ask 0.210 limit 0.310 price 0.223 asked 29.6 filled 29.6 status executed tau 22 locked_loss 10.26c
    - HEDGE 2026-10-06T11:59:38Z side no belief 0.144 ask 0.220 limit 0.320 price 0.233 asked 59.4 filled 59.4 status executed tau 22 locked_loss 19.63c
    - first hedge_alarm 2026-10-06T11:59:38Z belief 0.144 tau 22 (2 alarms; 34 hedge_quote records, min belief 0.144)
    - refusals on this market (gate: n): {"close_budget": 1, "confidence": 1, "early_once": 1, "max_per_market": 1, "staged_none": 1}
- KXBTC15M-26OCT030400-00 2026-10-03 04:00 ET -13.01 (v-topup), 1 filled legs; log settled -13.01:
    - early#l yes lim 0.978 ask 0.963 exec 0.9630 fill 31.6/31.6 tau 36 | lvl_age 222 ms sell3s 0.5 tk3s 21770.6 trade_age 0.04 s book_age 3 ms | swept False hdrm 1.5c | fair 0.99651 edge 3.101c sigma 1.769589
    - HEDGE 2026-10-03T07:59:41Z side no belief 0.381 ask 0.440 limit 0.540 price 0.428 asked 31.6 filled 31.6 status executed tau 19 locked_loss 39.15c
    - first hedge_alarm 2026-10-03T07:59:41Z belief 0.381 tau 19 (1 alarms; 36 hedge_quote records, min belief 0.381)
    - refusals on this market (gate: n): {"confidence": 1, "depth_floor": 1, "early_once": 1, "market_attempts": 1, "price_ceiling": 1, "toxic_fresh": 1}
- KXSOL15M-26SEP110830-30 2026-09-11 08:30 ET -12.16 (v-a10b), 1 filled legs; log settled -12.16:
    - full#d no lim 0.700 ask 0.700 exec 0.5910 fill 20.0/20.0 tau 30 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 5 ms | swept None hdrm Nonec | fair 0.00492 edge 28.038c sigma 0.010373
- KXDOGE15M-26SEP160900-00 2026-09-16 09:00 ET -12.14 (v-withdraw), 1 filled legs; log settled -12.15:
    - full#d no lim 0.980 ask 0.979 exec 0.9793 fill 87.0/87.0 tau 17 | lvl_age 845044 ms sell3s None tk3s None trade_age None s book_age 12 ms | swept True hdrm 0.1c | fair 0.00463 edge 1.493c sigma 8e-06
    - HEDGE 2026-09-16T12:59:48Z side yes belief 0.485 ask 0.170 limit - price 0.150 asked 87.0 filled 87.0 status executed tau 12 locked_loss 12.93c
    - first hedge_alarm 2026-09-16T12:59:48Z belief 0.485 tau 12 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"both_sides": 1, "confidence": 1}
- KXNEAR15M-26SEP160430-30 2026-09-16 04:30 ET -9.22 (v-withdraw), 1 filled legs; log settled -9.22:
    - full#d yes lim 0.980 ask 0.918 exec 0.9139 fill 84.0/84.0 tau 21 | lvl_age 19 ms sell3s None tk3s None trade_age None s book_age 1 ms | swept False hdrm 6.2c | fair 1.0 edge 7.673c sigma 0.000287
    - HEDGE 2026-09-16T08:29:42Z side no belief 0.766 ask 0.210 limit - price 0.180 asked 84.0 filled 84.0 status executed tau 18 locked_loss 9.39c
    - first hedge_alarm 2026-09-16T08:29:42Z belief 0.766 tau 18 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"both_sides": 1, "dump_guard": 1, "dumped(A10)": 1, "edge_floor": 1, "price_ceiling": 1}
- KXZEC15M-26SEP122000-00 2026-09-12 20:00 ET -8.63 (v-a15), 1 filled legs; log settled -7.66:
    - full#d yes lim 0.963 ask 0.963 exec 0.9620 fill 11.0/11.0 tau 25 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 4 ms | swept None hdrm Nonec | fair 0.99732 edge 3.182c sigma 0.03736
    - HEDGE 2026-09-12T23:59:39Z side no belief 0.525 ask 0.800 limit - price 0.800 asked 1.0 filled 1.0 status executed tau 21 locked_loss 76.2c
    - HEDGE 2026-09-12T23:59:40Z side no belief 0.525 ask 0.810 limit - price 0.810 asked 10.0 filled 10.0 status executed tau 20 locked_loss 77.2c
    - first hedge_alarm 2026-09-12T23:59:39Z belief 0.525 tau 21 (1 alarms; 0 hedge_quote records, min belief -)
- KXBNB15M-26SEP282000-00 2026-09-28 20:00 ET -8.26 (v-onefull), 2 filled legs; log settled -8.26:
    - early#l yes lim 0.978 ask 0.950 exec 0.9749 fill 30.3/30.3 tau 44 | lvl_age 116 ms sell3s 0.2468 tk3s 191.24 trade_age 0.146 s book_age 3 ms | swept True hdrm 2.8c | fair 0.99968 edge 4.635c sigma 0.010595
    - topup#l no lim 0.980 ask 0.980 exec 0.9800 fill 30.3/30.3 tau 22 | lvl_age 836959 ms sell3s 0.0535 tk3s 235.07 trade_age 0.622 s book_age 44 ms | swept False hdrm 0.0c | fair 0.00371 edge 1.492c sigma 0.016058
    - HEDGE 2026-09-28T23:59:28Z side no belief 0.172 ask 0.350 limit 0.450 price 0.300 asked 30.3 filled 30.3 status executed tau 32 locked_loss 27.49c
    - first hedge_alarm 2026-09-28T23:59:28Z belief 0.172 tau 32 (1 alarms; 44 hedge_quote records, min belief 0.172)
    - refusals on this market (gate: n): {"confidence": 1, "early_once": 1, "max_per_market": 1, "price_ceiling": 1}
- KXBTC15M-26OCT041615-15 2026-10-04 16:15 ET -6.08 (v-revert0925-fullcap), 2 filled legs; log settled -6.08:
    - early#l no lim 0.980 ask 0.958 exec 0.9524 fill 30.3/30.3 tau 45 | lvl_age 92 ms sell3s 0.4591 tk3s 62906.84 trade_age 0.077 s book_age 16 ms | swept False hdrm 2.2c | fair 0.00075 edge 3.843c sigma 1.423659
    - topup#l yes lim 0.980 ask 0.850 exec 0.8500 fill 30.3/30.3 tau 10 | lvl_age 44 ms sell3s 0.3782 tk3s 69631.06 trade_age 0.059 s book_age 1 ms | swept False hdrm 13.0c | fair 0.99667 edge 13.775c sigma 1.618605
    - HEDGE 2026-10-04T20:14:30Z side yes belief 0.395 ask 0.370 limit 0.470 price 0.370 asked 30.3 filled 30.3 status executed tau 30 locked_loss 32.24c
    - first hedge_alarm 2026-10-04T20:14:30Z belief 0.395 tau 30 (1 alarms; 45 hedge_quote records, min belief 0.395)
    - refusals on this market (gate: n): {"confidence": 1, "dump_guard": 1, "dumped(A10)": 1, "early_once": 1, "max_per_market": 1}
- KXETH15M-26SEP121115-15 2026-09-12 11:15 ET -5.16 (v-a12a), 1 filled legs; log settled -5.42:
    - full#d no lim 0.980 ask 0.980 exec 0.9800 fill 20.0/20.0 tau 29 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 26 ms | swept None hdrm Nonec | fair 0.00467 edge 1.396c sigma 0.127933
    - HEDGE 2026-09-12T15:14:32Z side yes belief 0.664 ask 0.280 limit - price 0.280 asked 20.0 filled 0.0 status canceled tau 28 locked_loss 26.0c
    - HEDGE 2026-09-12T15:14:33Z side yes belief 0.664 ask 0.280 limit - price 0.260 asked 14.0 filled 14.0 status executed tau 27 locked_loss 24.0c
    - HEDGE 2026-09-12T15:14:34Z side yes belief 0.691 ask 0.270 limit - price 0.270 asked 6.0 filled 6.0 status executed tau 26 locked_loss 25.0c
    - first hedge_alarm 2026-09-12T15:14:32Z belief 0.664 tau 28 (1 alarms; 0 hedge_quote records, min belief -)
- KXDOGE15M-26SEP222245-45 2026-09-22 22:45 ET -2.47 (v-unidefer), 2 filled legs; log settled -2.47:
    - full#l no lim 0.980 ask 0.980 exec 0.9340 fill 2.0/2.0 tau 12 | lvl_age 866790 ms sell3s None tk3s None trade_age None s book_age 2 ms | swept False hdrm 0.0c | fair 0.00441 edge 1.422c sigma 1.1e-05
    - full#l no lim 0.980 ask 0.980 exec 0.0710 fill 11.0/11.0 tau 11 | lvl_age 38 ms sell3s None tk3s None trade_age None s book_age 1 ms | swept False hdrm 0.0c | fair 0.00441 edge 1.422c sigma 1.1e-05
    - HEDGE 2026-09-23T02:44:50Z side yes belief 0.051 ask 0.936 limit 0.966 price 0.948 asked 2.0 filled 2.0 status executed tau 10 locked_loss 88.15c
    - HEDGE 2026-09-23T02:44:50Z side yes belief 0.051 ask 0.949 limit 0.979 price 0.949 asked 11.0 filled 0.0 status canceled tau 10 locked_loss 2.0c
    - HEDGE 2026-09-23T02:44:51Z side yes belief 0.051 ask 0.980 limit 0.999 price 0.986 asked 11.0 filled 11.0 status executed tau 9 locked_loss 5.7c
    - first hedge_alarm 2026-09-23T02:44:50Z belief 0.051 tau 10 (2 alarms; 12 hedge_quote records, min belief 0.051)
    - refusals on this market (gate: n): {"confidence": 1, "max_per_market": 1, "price_ceiling": 1}
- KXDOGE15M-26SEP101815-15 2026-09-10 18:15 ET -2.12 (v-pin995), 1 filled legs; log settled -2.12:
    - full#d no lim 0.530 ask 0.530 exec 0.0998 fill 20.0/20.0 tau 11 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 3 ms | swept None hdrm Nonec | fair 0.0 edge 45.256c sigma 5e-06
- KXBNB15M-26SEP131230-30 2026-09-13 12:30 ET -1.10 (v-a20b), 1 filled legs; log settled -1.10:
    - full#d no lim 0.980 ask 0.920 exec 0.9230 fill 32.0/32.0 tau 5 | lvl_age 286 ms sell3s None tk3s None trade_age None s book_age 6 ms | swept True hdrm 6.0c | fair 0.00388 edge 7.097c sigma 0.037852
    - HEDGE 2026-09-13T16:29:56Z side yes belief 0.643 ask 0.100 limit - price 0.100 asked 32.0 filled 32.0 status executed tau 4 locked_loss 2.3c
    - first hedge_alarm 2026-09-13T16:29:56Z belief 0.643 tau 4 (1 alarms; 0 hedge_quote records, min belief -)
- KXBTC15M-26SEP121100-00 2026-09-12 11:00 ET -1.09 (v-a12a), 1 filled legs; log settled -1.09:
    - full#d no lim 0.900 ask 0.900 exec 0.9000 fill 20.0/20.0 tau 30 | lvl_age None ms sell3s None tk3s None trade_age None s book_age 2 ms | swept None hdrm Nonec | fair 0.00445 edge 8.925c sigma 1.172346
    - HEDGE 2026-09-12T14:59:36Z side yes belief 0.887 ask 0.140 limit - price 0.140 asked 20.0 filled 20.0 status executed tau 24 locked_loss 4.0c
    - first hedge_alarm 2026-09-12T14:59:36Z belief 0.887 tau 24 (1 alarms; 0 hedge_quote records, min belief -)
- KXBNB15M-26SEP161230-30 2026-09-16 12:30 ET -0.47 (v-withdraw), 1 filled legs; log settled -0.47:
    - full#d no lim 0.980 ask 0.977 exec 0.9770 fill 1.0/1.0 tau 30 | lvl_age 229 ms sell3s None tk3s None trade_age None s book_age 100 ms | swept False hdrm 0.3c | fair 0.00479 edge 1.664c sigma 0.025341
    - HEDGE 2026-09-16T16:29:40Z side yes belief 0.533 ask 0.470 limit - price 0.470 asked 1.0 filled 1.0 status executed tau 20 locked_loss 44.7c
    - first hedge_alarm 2026-09-16T16:29:40Z belief 0.533 tau 20 (1 alarms; 0 hedge_quote records, min belief -)
    - refusals on this market (gate: n): {"both_sides": 1, "confidence": 1}
- KXSOL15M-26SEP120600-00 2026-09-12 06:00 ET -0.01 (v-a12a), 0 filled legs; log settled -0.01:
    - HEDGE 2026-09-12T09:59:35Z side yes belief 0.020 ask - limit - price 0.949 asked 1.0 filled 1.0 status executed tau 25 locked_loss 0.1c
    - first hedge_alarm 2026-09-12T09:59:35Z belief 0.020 tau 25 (1 alarms; 0 hedge_quote records, min belief -)
- KXETH15M-26SEP120545-45 2026-09-12 05:45 ET -0.00 (v-a12a), 0 filled legs; log settled -0.00:
    - first hedge_alarm 2026-09-12T09:44:35Z belief 0.000 tau 25 (1 alarms; 0 hedge_quote records, min belief -)
- KXBTC15M-26SEP080315-15 2026-09-08 03:15 ET -0.00 (pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z)), 0 filled legs:

### 60 random winning markets from the same versions (seed 7; pool 968 winners)

| ticker | close ET | version | $ net | bet $ | contracts | legs filled | 1st leg | 1st price | 1st tau s | ask_seen->limit | model conf | edge c | level_age_ms | sell_share_3s | taker_n_3s | trade_age_s | hedge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KXETH15M-26SEP090300-00 | 2026-09-09 03:00 ET | pre-VERSIONS.md (no en | 2.82 | 17 | 20 | full | full | 0.8500 | 30 | 0.850->0.850 | 1.00000 | 14.11 | None | None | None | None | no |
| KXHYPE15M-26SEP090530-30 | 2026-09-09 05:30 ET | pre-VERSIONS.md (no en | 0.45 | 20 | 20 | full | full | 0.9760 | 25 | 0.976->0.976 | 0.99998 | 2.23 | None | None | None | None | no |
| KXETH15M-26SEP090630-30 | 2026-09-09 06:30 ET | pre-VERSIONS.md (no en | 0.52 | 19 | 20 | full | full | 0.9720 | 22 | 0.972->0.972 | 0.98499 | 1.11 | None | None | None | None | no |
| KXXRP15M-26SEP090645-45 | 2026-09-09 06:45 ET | pre-VERSIONS.md (no en | 0.56 | 19 | 20 | full | full | 0.9700 | 12 | 0.970->0.970 | 0.99563 | 2.36 | None | None | None | None | no |
| KXBNB15M-26SEP092015-15 | 2026-09-09 20:15 ET | pre-VERSIONS.md (no en | 0.45 | 20 | 20 | full | full | 0.9760 | 30 | 0.976->0.976 | 0.98157 | 0.39 | None | None | None | None | no |
| KXHYPE15M-26SEP092030-30 | 2026-09-09 20:30 ET | pre-VERSIONS.md (no en | 0.37 | 20 | 20 | full | full | 0.9800 | 24 | 0.980->0.980 | 0.99816 | 1.68 | None | None | None | None | no |
| KXDOGE15M-26SEP092215-15 | 2026-09-09 22:15 ET | pre-VERSIONS.md (no en | 1.06 | 19 | 20 | full | full | 0.9430 | 17 | 0.944->0.944 | 0.98955 | 4.18 | None | None | None | None | no |
| KXBNB15M-26SEP100030-30 | 2026-09-10 00:30 ET | pre-VERSIONS.md (no en | 0.46 | 11 | 11 | full | full | 0.9550 | 30 | 0.955->0.955 | 0.99753 | 3.95 | None | None | None | None | no |
| KXSOL15M-26SEP100115-15 | 2026-09-10 01:15 ET | pre-VERSIONS.md (no en | 0.41 | 20 | 20 | full | full | 0.9780 | 30 | 0.978->0.978 | 0.99884 | 1.93 | None | None | None | None | no |
| KXBNB15M-26SEP101045-45 | 2026-09-10 10:45 ET | v-pin995 | 0.66 | 12 | 13 | full | full | 0.9460 | 9 | 0.947->0.947 | 0.99828 | 4.78 | None | None | None | None | no |
| KXETH15M-26SEP101245-45 | 2026-09-10 12:45 ET | v-pin995 | 0.56 | 19 | 20 | full | full | 0.9700 | 24 | 0.970->0.970 | 0.99885 | 2.68 | None | None | None | None | no |
| KXBNB15M-26SEP101515-15 | 2026-09-10 15:15 ET | v-pin995 | 0.42 | 16 | 17 | full | full | 0.9730 | 14 | 0.975->0.975 | 0.99996 | 2.33 | None | None | None | None | no |
| KXSOL15M-26SEP101700-00 | 2026-09-10 17:00 ET | v-pin995 | 1.70 | 18 | 20 | full | full | 0.9090 | 10 | 0.909->0.909 | 0.99546 | 8.07 | None | None | None | None | no |
| KXBTC15M-26SEP102030-30 | 2026-09-10 20:30 ET | v-a10b | 1.76 | 18 | 20 | full | full | 0.9059 | 27 | 0.906->0.906 | 0.99643 | 8.45 | None | None | None | None | no |
| KXHYPE15M-26SEP110315-15 | 2026-09-11 03:15 ET | v-a10b | 0.37 | 20 | 20 | full | full | 0.9800 | 29 | 0.980->0.980 | 0.99862 | 1.72 | None | None | None | None | no |
| KXBTC15M-26SEP110700-00 | 2026-09-11 07:00 ET | v-a10b | 0.00 | 0 | 0 | full | full | 0.9500 | 12 | 0.950->0.950 | 0.99746 | 4.41 | None | None | None | None | no |
| KXXRP15M-26SEP112345-45 | 2026-09-11 23:45 ET | v-a12a | 0.30 | 10 | 10 | full | full | 0.9680 | 30 | 0.968->0.968 | 0.99946 | 2.93 | None | None | None | None | no |
| KXBTC15M-26SEP120215-15 | 2026-09-12 02:15 ET | v-a12a | 1.67 | 18 | 20 | full | full | 0.9110 | 28 | 0.914->0.914 | 0.99512 | 7.56 | None | None | None | None | no |
| KXBTC15M-26SEP120500-00 | 2026-09-12 05:00 ET | v-a12a | 0.41 | 20 | 20 | full | full | 0.9780 | 30 | 0.980->0.980 | 0.99990 | 1.85 | None | None | None | None | no |
| KXBTC15M-26SEP121300-00 | 2026-09-12 13:00 ET | v-a12a | 0.78 | 19 | 20 | full | full | 0.9580 | 7 | 0.959->0.959 | 0.99932 | 3.76 | None | None | None | None | no |
| KXDOGE15M-26SEP121530-30 | 2026-09-12 15:30 ET | v-a15 | 0.37 | 20 | 20 | full | full | 0.9800 | 20 | 0.980->0.980 | 0.99648 | 1.51 | None | None | None | None | no |
| KXNEAR15M-26SEP140300-00 | 2026-09-14 03:00 ET | v-ladder | 1.12 | 54 | 55 | full | full | 0.9782 | 25 | 0.972->0.980 SWEPT | 0.99511 | 2.12 | 1040 | None | None | None | no |
| KXNEAR15M-26SEP140445-45 | 2026-09-14 04:45 ET | v-ladder | 3.59 | 54 | 58 | full | full | 0.9338 | 30 | 0.933->0.980 SWEPT | 0.99653 | 5.92 | 839327 | None | None | None | no |
| KXXRP15M-26SEP140515-15 | 2026-09-14 05:15 ET | v-ladder | 4.86 | 54 | 59 | full | full | 0.9121 | 10 | 0.890->0.980 SWEPT | 0.99938 | 10.25 | 52 | None | None | None | no |
| KXHYPE15M-26SEP141915-15 | 2026-09-14 19:15 ET | v-nofloor | 3.87 | 54 | 58 | full | full | 0.9285 | 20 | 0.914->0.980 SWEPT | 0.99760 | 7.81 | 324 | None | None | None | no |
| KXNEAR15M-26SEP152130-30 | 2026-09-15 21:30 ET | v-withdraw | 1.81 | 77 | 79 | full | full | 0.9755 | 26 | 0.969->0.980 SWEPT | 0.99885 | 2.77 | 695152 | None | None | None | no |
| KXBNB15M-26SEP160715-15 | 2026-09-16 07:15 ET | v-withdraw | 2.80 | 81 | 84 | full | full | 0.9642 | 5 | 0.957->0.980 SWEPT | 1.00000 | 4.01 | 773 | None | None | None | no |
| KXBNB15M-26SEP161845-45 | 2026-09-16 18:45 ET | v-withdraw | 1.77 | 88 | 90 | full | full | 0.9789 | 30 | 0.977->0.980 SWEPT | 0.99969 | 2.11 | 293 | None | None | None | no |
| KXHYPE15M-26SEP190615-15 | 2026-09-19 06:15 ET | v-cap200 | 1.97 | 104 | 106 | full | full | 0.9800 | 24 | 0.980->0.980 | 0.99993 | 1.86 | 832489 | None | None | None | no |
| KXETH15M-26SEP190745-45 | 2026-09-19 07:45 ET | v-cap200 | 2.72 | 105 | 108 | early | early | 0.9730 | 44 | 0.974->0.980 | 0.99568 | 1.99 | 96 | None | None | None | no |
| KXHYPE15M-26SEP191545-45 | 2026-09-19 15:45 ET | v-taper | 0.78 | 25 | 26 | early | early | 0.9680 | 45 | 0.968->0.980 | 0.99593 | 2.58 | 812664 | None | None | None | no |
| KXHYPE15M-26SEP191630-30 | 2026-09-19 16:30 ET | v-taper | 1.86 | 96 | 98 | early | early | 0.9797 | 45 | 0.978->0.980 SWEPT | 1.00000 | 2.05 | 825 | None | None | None | no |
| KXHYPE15M-26SEP192315-15 | 2026-09-19 23:15 ET | v-nocap | 2.93 | 100 | 103 | full | full | 0.9696 | 21 | 0.968->0.980 SWEPT | 0.99901 | 2.88 | 827547 | None | None | None | no |
| KXBNB15M-26SEP200045-45 | 2026-09-20 00:45 ET | v-nocap | 0.38 | 18 | 18 | full | full | 0.9774 | 12 | 0.980->0.980 | 1.00000 | 1.86 | 175504 | None | None | None | no |
| KXBTC15M-26SEP200145-45 | 2026-09-20 01:45 ET | v-nocap | 1.82 | 91 | 93 | early | early | 0.9790 | 32 | 0.979->0.980 | 0.99523 | 1.48 | 448 | None | None | None | no |
| KXZEC15M-26SEP200645-45 | 2026-09-20 06:45 ET | v-nocap | 1.41 | 70 | 72 | early | early | 0.9790 | 45 | 0.979->0.980 | 0.99796 | 1.75 | 811669 | None | None | None | no |
| KXXRP15M-26SEP220230-30 | 2026-09-22 02:30 ET | v-hedge25 | 3.20 | 75 | 78 | early | early | 0.9560 | 33 | 0.909->0.980 SWEPT | 0.99730 | 8.25 | 47 | None | None | None | no |
| KXSOL15M-26SEP230615-15 | 2026-09-23 06:15 ET | v-traj1 | 0.52 | 27 | 28 | early | early | 0.9800 | 44 | 0.980->0.980 | 0.99822 | 1.69 | 815003 | None | None | None | no |
| KXHYPE15M-26SEP230900-00 | 2026-09-23 09:00 ET | v-traj1 | 2.09 | 26 | 28 | early | early | 0.9210 | 44 | 0.959->0.980 **fill 4c under ask** | 0.99591 | 3.42 | 90 | None | None | None | no |
| KXDOGE15M-26SEP231445-45 | 2026-09-23 14:45 ET | v-traj1 | 0.54 | 28 | 29 | early | early | 0.9800 | 45 | 0.979->0.980 SWEPT | 0.99777 | 1.73 | 181 | None | None | None | no |
| KXHYPE15M-26SEP231600-00 | 2026-09-23 16:00 ET | v-traj1 | 0.75 | 28 | 29 | early | early | 0.9721 | 45 | 0.970->0.980 SWEPT | 0.99646 | 2.44 | 229 | None | None | None | no |
| KXXRP15M-26SEP231930-30 | 2026-09-23 19:30 ET | v-traj1 | 0.87 | 28 | 29 | early | early | 0.9680 | 44 | 0.978->0.980 | 0.99960 | 2.01 | 50 | None | None | None | no |
| KXHYPE15M-26SEP232100-00 | 2026-09-23 21:00 ET | v-traj1 | 0.48 | 25 | 26 | early | early | 0.9800 | 45 | 0.980->0.980 | 0.99981 | 1.84 | 813983 | None | None | None | no |
| KXNEAR15M-26SEP250845-45 | 2026-09-25 08:45 ET | v-scalein-caps | 2.71 | 86 | 89 | full | full | 0.9673 | 24 | 0.954->0.980 SWEPT | 0.99614 | 3.91 | 358 | 0.4031 | 231.51 | 0.251 | no |
| KXHYPE15M-26SEP251115-15 | 2026-09-25 11:15 ET | v-scalein-caps | 2.04 | 88 | 90 | early+topup | early | 0.9670 | 31 | 0.967->0.980 | 0.99547 | 2.62 | 165 | 0.2609 | 319.32 | 0.064 | no |
| KXDOGE15M-26SEP251530-30 | 2026-09-25 15:30 ET | v-scalein-caps | 16.48 | 117 | 135 | full | full | 0.8700 | 3 | 0.870->0.980 | 1.00000 | 12.21 | 377 | 0.0436 | 7719.53 | 0.073 | no |
| KXBTC15M-26SEP251900-00 | 2026-09-25 19:00 ET | v-scalein-caps | 2.06 | 90 | 92 | full | full | 0.9760 | 6 | 0.976->0.980 | 0.99676 | 1.91 | 40 | 0.6405 | 138217.83 | 0.052 | no |
| KXBNB15M-26SEP251900-00 | 2026-09-25 19:00 ET | v-scalein-caps | 2.11 | 90 | 92 | early+topup | early | 0.9700 | 35 | 0.980->0.980 | 0.99509 | 1.37 | 843127 | 0.9106 | 149.42 | 0.601 | no |
| KXXRP15M-26SEP252000-00 | 2026-09-25 20:00 ET | v-scalein-caps | 2.14 | 90 | 92 | full | full | 0.9750 | 25 | 0.972->0.980 SWEPT | 0.99752 | 2.36 | 42 | 0.9388 | 1994.79 | 0.057 | no |
| KXBTC15M-26SEP261115-15 | 2026-09-26 11:15 ET | v-scalein-caps | 4.20 | 139 | 144 | full+late_add | full | 0.9644 | 22 | 0.956->0.980 SWEPT | 0.99836 | 3.94 | 224 | 0.7989 | 21819.04 | 0.104 | no |
| KXNEAR15M-26SEP261230-30 | 2026-09-26 12:30 ET | v-scalein-caps | 0.86 | 31 | 32 | early | early | 0.9716 | 41 | 0.969->0.980 SWEPT | 0.99523 | 2.41 | 1199 | 0.0 | 97.0 | 1.744 | no |
| KXDOGE15M-26SEP261630-30 | 2026-09-26 16:30 ET | v-scalein-caps | 0.64 | 32 | 33 | early | early | 0.9790 | 44 | 0.979->0.980 | 0.99883 | 1.84 | 29 | 0.757 | 561.04 | 0.068 | no |
| KXZEC15M-26SEP270300-00 | 2026-09-27 03:00 ET | v-scalein-caps | 2.51 | 83 | 86 | full | full | 0.9686 | 26 | 0.960->0.980 SWEPT | 0.99696 | 3.43 | 832116 | 0.058 | 1024.45 | 0.11 | no |
| KXBNB15M-26SEP291745-45 | 2026-09-29 17:45 ET | v-onefull | 0.51 | 24 | 25 | full | full | 0.9780 | 21 | 0.978->0.980 | 0.99877 | 1.93 | 39 | 0.0883 | 475.79 | 0.098 | no |
| KXHYPE15M-26SEP302130-30 | 2026-09-30 21:30 ET | v-topup | 4.26 | 124 | 129 | full+late_add | full | 0.9654 | 10 | 0.965->0.980 SWEPT | 0.99676 | 2.94 | 849106 | 0.2352 | 1341.36 | 0.076 | no |
| KXBNB15M-26OCT042000-00 | 2026-10-04 20:00 ET | v-revert0925-fullcap | 1.17 | 29 | 31 | early | early | 0.9590 | 45 | 0.959->0.980 | 0.99642 | 3.47 | 5956 | 0.0864 | 9.49 | 0.704 | no |
| KXETH15M-26OCT042245-45 | 2026-10-04 22:45 ET | v-revert0925-fullcap | 0.48 | 25 | 26 | early | early | 0.9800 | 43 | 0.980->0.980 | 0.99805 | 1.67 | 56 | 0.6469 | 1878.16 | 0.242 | no |
| KXBNB15M-26OCT050015-15 | 2026-10-05 00:15 ET | v-revert0925-fullcap | 0.52 | 23 | 23 | early | early | 0.9760 | 45 | 0.975->0.980 SWEPT | 0.99912 | 2.24 | 99 | 0.0052 | 192.95 | 0.542 | no |
| KXBTC15M-26OCT051845-45 | 2026-10-05 18:45 ET | v-skiphype | 0.91 | 28 | 29 | early | early | 0.9660 | 41 | 0.958->0.980 SWEPT | 0.99520 | 3.44 | 22 | 0.5267 | 27231.62 | 0.057 | no |
| KXDOGE15M-26OCT070015-15 | 2026-10-07 00:15 ET | v-bankfix-nodd | 0.72 | 29 | 29 | early | early | 0.9736 | 36 | 0.969->0.980 SWEPT | 0.99539 | 2.43 | 33 | 0.0817 | 1061.77 | 0.271 | no |

Population comparison (first filled leg; only markets where the field is logged):

| field | losers: n / median | winners (the 60): n / median | all winners: n / median |
|---|---|---|---|
| price | 42 / 0.9458 | 60 / 0.9708 | 1316 / 0.9750 |
| tau | 42 / 27.5000 | 60 / 28.5000 | 1316 / 30.0000 |
| level_age_ms | 32 / 92.0000 | 39 / 358.0000 | 1068 / 240.5000 |
| sell_share_3s | 15 / 0.5562 | 17 / 0.2609 | 449 / 0.4279 |
| taker_n_3s | 15 / 6026.1500 | 17 / 1024.4500 | 449 / 1327.9300 |
| trade_age_s | 15 / 0.0770 | 17 / 0.1040 | 449 / 0.0790 |
| book_age_ms | 42 / 4.5000 | 60 / 8.0000 | 1316 / 8.0000 |
| edge_c | 42 / 3.9275 | 60 / 2.4205 | 1316 / 2.2390 |
| sweep_headroom_c | 32 / 2.4500 | 39 / 1.0000 | 1053 / 0.5000 |
| model conf on the side bought | 42 / 0.9975 | 60 / 0.9977 | 1316 / 0.9973 |
| fill under the ask seen, cents | 42 / 0.0000 | 60 / 0.0000 | 1316 / 0.0000 |
| fill >= 3c under the ask seen (count) | 10 of 45 | 1 of 60 | 25 of 1316 |
| stale-book fills (>= 3c under the ask seen), all main markets | 35 markets, 10 lost, net -123.35 | | |
| swept (count true) | 12 of 45 | 21 of 60 | 499 of 1316 |
| leg mix | {'full': 25, 'early': 10, 'early+topup': 4, 'full+late_add': 3, None: 3} | {'full': 37, 'early': 19, 'early+topup': 2, 'full+late_add': 2} | {'full': 757, 'early': 492, 'early+topup': 46, 'full+late_add': 21} |

## e) Hedge / insurance accounting, lifetime (the main bot: the 12 coins since 09-08, plus its KXBTCD rung if any)

A hedge = a `hedge` log record that filled (n > 0), or a Kalshi row holding BOTH sides. Hedge $ = the OTHER side's payout minus its cost (Kalshi's counts and costs; fees are in the market's net, not here). False alarm = the bet side won anyway. Where Kalshi's other-side count exceeds the hedge records' n, the difference is an ORDER-path buy on the other side (the A68 late flip, logged as `late_add`, or a top-up re-buy into the other side) -- counted in hedge $ here because it is insurance in effect.

| ticker | close ET | version | bet side | bet won? | belief at hedge | hedge price c | hedge contracts (log n / Kalshi) | hedge $ | market net $ | kind |
|---|---|---|---|---|---|---|---|---|---|---|
| KXSOL15M-26SEP120600-00 | 2026-09-12 06:00 ET | v-a12a | yes | True | 0.020 | 94.9 | 1.0 / 1.0 | -0.05 | -0.01 | false alarm |
| KXBTC15M-26SEP121100-00 | 2026-09-12 11:00 ET | v-a12a | no | True | 0.887 | 14.0 | 20.0 / 20.0 | -2.80 | -1.09 | false alarm |
| KXETH15M-26SEP121115-15 | 2026-09-12 11:15 ET | v-a12a | no | True | 0.664, 0.691 | 26.0, 27.0 | 14.0, 6.0 / 20.0 | -5.26 | -5.16 | false alarm |
| KXZEC15M-26SEP122000-00 | 2026-09-12 20:00 ET | v-a15 | yes | False | 0.525, 0.525 | 80.0, 81.0 | 1.0, 10.0 / 11.0 | 2.10 | -8.63 | real |
| KXBNB15M-26SEP131230-30 | 2026-09-13 12:30 ET | v-a20b | no | True | 0.643 | 10.0 | 32.0 / 32.0 | -3.20 | -1.10 | false alarm |
| KXBTC15M-26SEP140530-30 | 2026-09-14 05:30 ET | v-ladder | no | False | 0.214 | 58.0 | 60.0 / 60.0 | 25.20 | -34.26 | real |
| KXHYPE15M-26SEP141600-00 | 2026-09-14 16:00 ET | v-nofloor | no | False | 0.559 | 51.0 | 62.0 / 62.0 | 30.38 | -29.90 | real |
| KXNEAR15M-26SEP160430-30 | 2026-09-16 04:30 ET | v-withdraw | yes | True | 0.766 | 18.0 | 84.0 / 84.0 | -15.12 | -9.22 | false alarm |
| KXDOGE15M-26SEP160900-00 | 2026-09-16 09:00 ET | v-withdraw | no | True | 0.485 | 15.0 | 87.0 / 87.0 | -13.05 | -12.14 | false alarm |
| KXBNB15M-26SEP161230-30 | 2026-09-16 12:30 ET | v-withdraw | no | False | 0.533 | 47.0 | 1.0 / 1.0 | 0.53 | -0.47 | real |
| KXBTC15M-26SEP172115-15 | 2026-09-17 21:15 ET | v-early-full | yes | False | 0.150 | 72.0 | 99.0 / 99.0 | 27.72 | -27.87 | real |
| KXDOGE15M-26SEP180015-15 | 2026-09-18 00:15 ET | v-early49 | yes | False | 0.243 | 74.0 | 33.6 / 33.6 | 8.74 | 4.36 | real |
| KXBNB15M-26SEP190145-45 | 2026-09-19 01:45 ET | v-cap200 | yes | False | 0.116 | 76.0 | 1.0 / 1.0 | 0.24 | -57.76 | real |
| KXBNB15M-26SEP191230-30 | 2026-09-19 12:30 ET | v-mirror | yes | False | 0.154, 0.154, 0.006, 0.006, 0.006 | 44.0, 62.0, 77.0, 80.0, 80.0 | 1.0, 22.0, 16.0, 43.8, 1.7 / 84.5 | 21.70 | -61.75 | real |
| KXHYPE15M-26SEP192345-45 | 2026-09-19 23:45 ET | v-nocap | no | True | 0.501 | 46.0 | 104.0 / 104.0 | -47.84 | -43.92 | false alarm |
| KXXRP15M-26SEP192345-45 | 2026-09-19 23:45 ET | v-nocap | no | True | 0.273 | 63.0 | 104.0 / 104.0 | -65.52 | -64.95 | false alarm |
| KXNEAR15M-26SEP211245-45 | 2026-09-21 12:45 ET | v-nocap | yes | False | 0.392, 0.123 | 70.0, 90.5 | 40.5, 40.5 / 81.0 | 16.00 | -59.09 | real |
| KXHYPE15M-26SEP211815-15 | 2026-09-21 18:15 ET | v-hedge25 | yes | False | 0.230 | 57.0 | 55.0 / 55.0 | 23.65 | -31.27 | real |
| KXDOGE15M-26SEP222245-45 | 2026-09-22 22:45 ET | v-unidefer | no | False | 0.051, 0.051 | 94.8, 98.6 | 2.0, 11.0 / 13.0 | 0.26 | -2.47 | real |
| KXBTC15M-26SEP232030-30 | 2026-09-23 20:30 ET | v-traj1 | yes | False | 0.111, 0.111, 0.083, 0.083 | 79.5, 81.9, 87.0, 87.0 | 21.1, 8.0, 66.9, 80.0 / 176.0 | 24.87 | -130.41 | real |
| KXBNB15M-26SEP261030-30 | 2026-09-26 10:30 ET | v-scalein-caps | no | True | 0.034 | 57.8 | 98.0 / 98.0 | -56.62 | -20.29 | false alarm |
| KXBTC15M-26SEP270000-00 | 2026-09-27 00:00 ET | v-scalein-caps | yes | False | 0.044, 0.044 | 67.0, 68.0 | 99.0, 99.0 / 198.0 | 64.35 | -131.98 | real |
| KXETH15M-26SEP270230-30 | 2026-09-27 02:30 ET | v-scalein-caps | yes | True | 0.351 | 51.0 | 88.0 / 88.0 | -44.88 | -32.73 | false alarm |
| KXBNB15M-26SEP282000-00 | 2026-09-28 20:00 ET | v-onefull | yes | False | 0.172 | 30.0 | 30.3 / 60.6 | 21.82 | -8.26 | real |
| KXXRP15M-26SEP301915-15 | 2026-09-30 19:15 ET | v-topup | yes | False | 0.394 | 51.0 | 89.0 / 89.0 | 43.61 | -42.60 | real |
| KXSOL15M-26OCT022130-30 | 2026-10-02 21:30 ET | v-topup | no | False | 0.363 | 50.0 | 96.0 / 144.0 | 48.96 | -41.11 | real |
| KXBTC15M-26OCT030400-00 | 2026-10-03 04:00 ET | v-topup | yes | True | 0.381 | 42.9 | 31.6 / 31.6 | -13.55 | -13.01 | false alarm |
| KXNEAR15M-26OCT030645-45 | 2026-10-03 06:45 ET | v-bankmove | no | False | 0.000, 0.000 | 94.9, 94.8 | 31.3, 62.7 / 94.0 | 4.85 | -86.95 | real |
| KXBTC15M-26OCT041615-15 | 2026-10-04 16:15 ET | v-revert0925-fullcap | no | False | 0.395 | 37.0 | 30.3 / 60.6 | 23.63 | -6.08 | real |
| KXHYPE15M-26OCT042015-15 | 2026-10-04 20:15 ET | v-revert0925-fullcap | no | False | 0.295 | 58.5 | 92.0 / 138.0 | 39.10 | -49.02 | real |
| KXHYPE15M-26OCT050030-30 | 2026-10-05 00:30 ET | v-revert0925-fullcap | no | False | 0.031 | 86.0 | 89.0 / 133.5 | 13.45 | -73.88 | real |
| KXBNB15M-26OCT060800-00 | 2026-10-06 08:00 ET | v-skiphype | yes | True | 0.144, 0.144 | 22.3, 23.3 | 29.6, 59.4 / 89.0 | -20.45 | -16.16 | false alarm |
| KXBTC15M-26OCT061615-15 | 2026-10-06 16:15 ET | v-bankfix-nodd | no | True | 0.336 | 58.0 | 29.6 / 29.6 | -17.19 | -16.59 | false alarm |
| KXNEAR15M-26OCT061615-15 | 2026-10-06 16:15 ET | v-bankfix-nodd | no | False | 0.201 | 75.0 | 29.6 / 29.6 | 7.41 | -21.93 | real |

- lifetime: false alarm 13 markets, hedge side -305.54 (market net -236.36); real 21 markets, hedge side +448.57 (market net -901.34); hedge-side total +143.03
- through 2026-09-27 ET (memory says -$55: 9 false -$263 / 13 real +$208): false alarm 10 markets, hedge side -254.34 (market net -190.60); real 13 markets, hedge side +245.74 (market net -571.50); hedge-side total -8.60
- hedge orders that did NOT fill: 11 (statuses {'canceled': 11})
- both-sides rows OUTSIDE the main bot's book (not counted above): KXBTC15M-26SEP062145-45 2026-09-06 net -0.00; KXWTI15M-26SEP171615-15 2026-09-17 net -58.76; KXWTI15M-26SEP181015-15 2026-09-18 net -9.41

## f) The other books in this ledger file (not the main table)

| book / series | markets | lost | net $ | bet $ (both sides) | % on bet | first ET day | last ET day | note |
|---|---|---|---|---|---|---|---|---|
| KXCRYPTOLEAD15M | 243 | 11 | 23.29 | 1133 | 2.06% | 2026-09-06 | 2026-10-07 | coin race (pinracearm, main account): 172 races (events); one ticker per coin leg |
| KXWTI15M | 39 | 3 | -77.51 | 367 | -21.14% | 2026-09-17 | 2026-09-18 | the separate commodity bot (cmdlive), not pinrun |
| KXBTCD | 32 | 1 | -17.75 | 58 | -30.78% | 2026-08-15 | 2026-10-07 | hourly BTC ladder: 31 markets bought by pinrun (1 contract each, v-btcd1 09-24 on), net +1.25; the rest predate the bot (Aug 15: -19.00) |
| KXGOLD15M | 9 | 2 | -6.62 | 131 | -5.04% | 2026-09-07 | 2026-09-17 | the separate commodity bot (cmdlive), not pinrun |
| KXBTC15M | 4 | 3 | -19.99 | 38 | -52.34% | 2026-08-15 | 2026-09-06 | 15-minute coin rows from BEFORE 2026-09-08 (manual / pre-bot) |
| KXNATGAS15M | 3 | 3 | -24.14 | 24 | -100.00% | 2026-09-07 | 2026-09-07 | the separate commodity bot (cmdlive), not pinrun |
| KXCOPPER15M | 1 | 0 | 0.21 | 1 | 26.58% | 2026-09-07 | 2026-09-07 | the separate commodity bot (cmdlive), not pinrun |
| KXTENCENTSHARE | 1 | 1 | -10.00 | 10 | -100.00% | 2026-09-28 | 2026-09-28 | not a bot market (manual) |

Coin race by ET day (markets, lost, net $): 2026-09-06 1/1 -0.01; 2026-09-07 2/2 -0.02; 2026-09-15 1/1 -0.00; 2026-09-21 26/2 -1.20; 2026-09-22 39/0 +1.03; 2026-09-23 57/2 +0.24; 2026-09-24 19/0 +1.86; 2026-09-25 14/0 +2.59; 2026-09-26 29/0 +3.86; 2026-09-27 7/0 +3.80; 2026-09-28 3/0 +2.81; 2026-09-29 6/0 +4.24; 2026-09-30 2/1 -0.77; 2026-10-01 5/0 +7.22; 2026-10-03 5/0 +3.58; 2026-10-04 9/0 +3.48; 2026-10-05 2/0 +1.49; 2026-10-06 5/0 +2.77; 2026-10-07 11/2 -13.68

## g) Pot math per price bucket -- expected $ per 100 contracts at the measured loss rate, and the loss rate that turns it negative

E[$ per 100] = 100 x [(1 - L) x avg win per contract - L x avg loss per contract], with L the measured loss rate; the same at the interval's low and high ends. Turns negative above L* = avg win / (avg win + avg loss). ABOVE break-even = the measured L is below L*.

### All-time

| bucket | markets | L (lost per 100) [95% CI] | E[$/100] at L | at CI low | at CI high | L* (turns negative) | verdict |
|---|---|---|---|---|---|---|---|
| <90 | 52 | 17.31% [8.23%, 30.33%] | 3.25 | 8.66 | -4.52 | 22.75% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| 90-93 | 69 | 7.25% [2.39%, 16.11%] | 4.82 | 6.93 | 0.95 | 18.29% | ABOVE break-even -- whole interval above |
| 93-95 | 108 | 7.41% [3.25%, 14.07%] | 0.13 | 3.07 | -4.59 | 7.59% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| 95-96 | 79 | 2.53% [0.31%, 8.85%] | 2.91 | 3.87 | 0.20 | 9.31% | ABOVE break-even -- whole interval above |
| 96-97 | 186 | 2.69% [0.88%, 6.16%] | 0.93 | 2.41 | -1.92 | 3.82% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| 97-98 | 600 | 1.67% [0.80%, 3.04%] | 1.14 | 1.69 | 0.27 | 3.48% | ABOVE break-even -- whole interval above |
| >=98 | 264 | 1.14% [0.23%, 3.28%] | 1.00 | 1.72 | -0.72 | 2.39% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| ALL | 1358 | 3.09% [2.24%, 4.16%] | 1.51 | 2.02 | 0.87 | 5.59% | ABOVE break-even -- whole interval above |

### Last 14 ET days

| bucket | markets | L (lost per 100) [95% CI] | E[$/100] at L | at CI low | at CI high | L* (turns negative) | verdict |
|---|---|---|---|---|---|---|---|
| <90 | 11 | 27.27% [6.02%, 60.97%] | 2.33 | 10.36 | -10.41 | 33.43% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| 90-93 | 13 | 7.69% [0.19%, 36.03%] | 3.94 | 7.74 | -10.41 | 15.47% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| 93-95 | 27 | 11.11% [2.35%, 29.16%] | -2.57 | 3.56 | -15.20 | 7.44% | BELOW break-even -- interval reaches back under L* |
| 95-96 | 18 | 5.56% [0.14%, 27.29%] | 2.71 | 4.01 | -2.54 | 16.78% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| 96-97 | 70 | 4.29% [0.89%, 12.02%] | -0.33 | 2.32 | -6.36 | 3.87% | BELOW break-even -- interval reaches back under L* |
| 97-98 | 237 | 1.69% [0.46%, 4.26%] | 1.03 | 1.89 | -0.78 | 3.15% | ABOVE break-even -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money |
| >=98 | 86 | 0.00% [0.00%, 4.20%] | 1.94 | 1.94 | - | - | no loss yet in bucket; L* unknown |
| ALL | 462 | 3.25% [1.83%, 5.30%] | 1.26 | 2.09 | 0.07 | 5.42% | ABOVE break-even -- whole interval above |

## h) Data-quality notes

- Main-table markets Kalshi settled with NO order record in any live log (bot died / never logged): 4 -- KXBTC15M-26SEP080315-15 2026-09-08 03:15 ET -0.00 (close_time_in_log_span); KXETH15M-26SEP120545-45 2026-09-12 05:45 ET -0.00 (close_time_in_log_span); KXSOL15M-26SEP120600-00 2026-09-12 06:00 ET -0.01 (close_time_in_log_span); KXBTC15M-26SEP151615-15 2026-09-15 16:15 ET +0.00 (None)
- Main-table markets with no `settled` log record (position open when the run died, or settled by a later run that did not know it): 14 -- KXBTC15M-26SEP080315-15 -0.00; KXHYPE15M-26SEP081200-00 +0.49; KXBTC15M-26SEP112200-00 +1.57; KXHYPE15M-26SEP112200-00 +0.10; KXSOL15M-26SEP112200-00 +1.14; KXBTC15M-26SEP112330-30 +0.39; KXSOL15M-26SEP112330-30 +0.04; KXXRP15M-26SEP112330-30 +0.50; KXBTC15M-26SEP151615-15 +0.00; KXBTC15M-26SEP172115-15 -27.87; KXZEC15M-26SEP172115-15 +12.09; KXBTC15M-26SEP190200-00 -66.34; KXETH15M-26SEP190200-00 +4.06; KXBTC15M-26OCT010300-00 +2.38
- Markets with a FILLED order in a log but no Kalshi ledger row: 0 -- none
- Markets a log settled/hedged with no filled order and no ledger row: 0 -- none
- Main-table markets where the log's summed pnl_c disagrees with Kalshi by more than $0.05: 15 of 1360 with both -- KXHYPE15M-26SEP081200-00 kalshi +0.49 log +0.00; KXSOL15M-26SEP081930-30 kalshi +2.98 log +1.86; KXBTC15M-26SEP082000-00 kalshi +2.15 log +0.99; KXBTC15M-26SEP112200-00 kalshi +1.57 log +0.00; KXHYPE15M-26SEP112200-00 kalshi +0.10 log +0.00; KXSOL15M-26SEP112200-00 kalshi +1.14 log +0.00; KXBTC15M-26SEP112330-30 kalshi +0.39 log +0.00; KXXRP15M-26SEP112330-30 kalshi +0.50 log +0.00; KXETH15M-26SEP121115-15 kalshi -5.16 log -5.42; KXZEC15M-26SEP122000-00 kalshi -8.63 log -7.66; KXBTC15M-26SEP172115-15 kalshi -27.87 log +0.00; KXZEC15M-26SEP172115-15 kalshi +12.09 log +0.00; KXBTC15M-26SEP190200-00 kalshi -66.34 log +0.00; KXETH15M-26SEP190200-00 kalshi +4.06 log +0.00; KXBTC15M-26OCT010300-00 kalshi +2.38 log +0.00
- Markets where the orchestrator's formula (revenue/100 + min(yes,no) - costs - fee) differs from pinledger's value-aware payout by > $0.005: 0 -- none
- Live log files with no VERSIONS.md name (before the first entry, v-cond 2026-09-10 07:47Z): 34 files, pinrun-live-20260908T062046Z.jsonl .. pinrun-live-20260910T070608Z.jsonl; their flags are in live_versions.json
- Files matched to a version whose header time is AFTER the file start (within the 10-min slack for '~hh:mx' headers): 5 -- pinrun-live-20260910T083328Z.jsonl -> v-pin995 (2026-09-10T08:40:00Z); pinrun-live-20260917T194157Z.jsonl -> v-early-full (2026-09-17T19:50:00Z); pinrun-live-20260918T065105Z.jsonl -> v-bank8 (2026-09-18T07:00:00Z); pinrun-live-20260922T114149Z.jsonl -> v-safety1 (2026-09-22T11:50:00Z); pinrun-live-20260922T200418Z.jsonl -> v-instr1 (2026-09-22T20:10:00Z)
- Files with no code_sha in the start record: 17 (code_sha first appears pinrun-live-20260908T163644Z.jsonl)
- Overlapping live log files (two live processes at once): [{"a": "pinrun-live-20260913T193314Z.jsonl", "a_end": "2026-09-14T00:35:18Z", "b": "pinrun-live-20260914T003505Z.jsonl", "b_start": "2026-09-14T00:35:05Z", "overlap_s": 13}]
- Order records with an exchange error: 30 ({"{'code': 'TRADING_BLOCKED', 'message': '": 25, "{'code': 'invalid_price', 'message': 'in": 5})
- Order records refused before the send (rail): 203
- Main-table markets attributed to no log file at all: 1 -- KXBTC15M-26SEP151615-15 2026-09-15 16:15 ET +0.00
- Main-table markets holding both sides on Kalshi with no filled `hedge` record (plant test, A68 flip buy, or a dead run's hedge): 0 -- none
- Main-table markets whose bet-side contract count in the logs differs from Kalshi's by > 0.5: 0 -- none

## Reconciliation against `python research/pinday.py --days 60`

pinday run saved in pinday_60.txt (its ledger: 2026-10-08 05:30 ET; this report's ledger written 2026-10-08T09:30:12Z).

| ET day | pinday crypto markets | pinday $ | pinday losses | this dataset markets | $ | losses | $ gap |
|---|---|---|---|---|---|---|---|
| 2026-09-08 | 32 | -40.59 | 2 | 32 | -40.59 | 2 | +0.00 |
| 2026-09-09 | 40 | +48.74 | 0 | 40 | +48.74 | 0 | -0.00 |
| 2026-09-10 | 44 | +0.23 | 3 | 44 | +0.23 | 3 | -0.00 |
| 2026-09-11 | 49 | +1.25 | 2 | 49 | +1.25 | 2 | -0.00 |
| 2026-09-12 | 96 | +38.04 | 6 | 96 | +38.04 | 6 | +0.00 |
| 2026-09-13 | 49 | +114.78 | 1 | 49 | +114.78 | 1 | +0.00 |
| 2026-09-14 | 61 | +81.10 | 2 | 61 | +81.10 | 2 | +0.00 |
| 2026-09-15 | 36 | +76.32 | 0 | 36 | +76.32 | 0 | -0.00 |
| 2026-09-16 | 45 | +85.11 | 3 | 45 | +85.11 | 3 | +0.00 |
| 2026-09-17 | 55 | +99.87 | 1 | 55 | +99.87 | 1 | +0.00 |
| 2026-09-18 | 68 | +91.85 | 0 | 68 | +91.85 | 0 | -0.00 |
| 2026-09-19 | 73 | -223.46 | 6 | 73 | -223.46 | 6 | -0.00 |
| 2026-09-20 | 53 | +109.63 | 0 | 53 | +109.63 | 0 | +0.00 |
| 2026-09-21 | 48 | -2.97 | 2 | 48 | -2.97 | 2 | -0.00 |
| 2026-09-22 | 34 | +53.70 | 1 | 34 | +53.70 | 1 | +0.00 |
| 2026-09-23 | 54 | -42.46 | 1 | 54 | -42.46 | 1 | -0.00 |
| 2026-09-24 | 63 | +93.42 | 0 | 63 | +93.42 | 0 | +0.00 |
| 2026-09-25 | 50 | +107.18 | 0 | 50 | +107.18 | 0 | -0.00 |
| 2026-09-26 | 49 | +46.54 | 1 | 49 | +46.54 | 1 | +0.00 |
| 2026-09-27 | 30 | -109.21 | 2 | 30 | -109.21 | 2 | -0.00 |
| 2026-09-28 | 24 | +22.61 | 1 | 24 | +22.61 | 1 | +0.00 |
| 2026-09-29 | 21 | +30.59 | 0 | 21 | +30.59 | 0 | +0.00 |
| 2026-09-30 | 29 | +12.39 | 1 | 29 | +12.39 | 1 | -0.00 |
| 2026-10-01 | 26 | +80.51 | 0 | 26 | +80.51 | 0 | +0.00 |
| 2026-10-02 | 19 | -13.03 | 1 | 19 | -13.03 | 1 | +0.00 |
| 2026-10-03 | 37 | -27.67 | 2 | 37 | -27.67 | 2 | -0.00 |
| 2026-10-04 | 49 | +22.35 | 2 | 49 | +22.35 | 2 | -0.00 |
| 2026-10-05 | 48 | -19.08 | 1 | 48 | -19.08 | 1 | -0.00 |
| 2026-10-06 | 41 | -0.84 | 3 | 41 | -0.84 | 3 | +0.00 |
| 2026-10-07 | 36 | -37.59 | 1 | 36 | -37.59 | 1 | -0.00 |
| 2026-10-08 | 3 | +2.48 | 0 | 3 | +2.48 | 0 | +0.00 |
| **since 09-08** | 1362 | +701.79 | | 1362 | +701.78 | | -0.01 |

Difference over the same days: **-0.01** (dataset +701.78 vs pinday +701.79; markets 1362 vs 1362).
