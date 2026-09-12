# RESULTS_tapegaps -- where the tape is SILENT, second by second

`research/tapegaps.py`, run 2026-09-12T14:47:58Z. Data `C:/kals/kalshi_data`, 1248 channel-hours, 41.4 GB of gzip. Census scanned in 729 s on 2026-09-12T14:36:04Z and read back from a cache here -- the reading code is untouched by the report, so this is the same census.

**1,429,655,772 records read.** `trade` 62,950,750 records over 414 hours; `orderbook_delta` 1,351,014,801 records over 416 hours; `cfbenchmarks_value` 15,690,221 records over 418 hours.

Reader integrity: **36** channel-hours raised on the ordinary reader, **36** were recovered member-by-member, **0** had a chunk whose needle count disagreed with its newline count, **0** carried a timestamp that was not ten digits or was more than a day from its own filename.
  * `cfbenchmarks_value/20260826T05` -- EOFError: Compressed file ended before the end-of-stream marker was reached (ordinary reader 22,676 records, salvage 23,990)
  * `cfbenchmarks_value/20260902T00` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 11,275 records, salvage 16,412)
  * `cfbenchmarks_value/20260902T01` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 2)
  * `cfbenchmarks_value/20260902T02` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 2)
  * `cfbenchmarks_value/20260902T03` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 2)
  * `cfbenchmarks_value/20260902T04` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 1)
  * `cfbenchmarks_value/20260902T05` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 2)
  * `cfbenchmarks_value/20260902T21` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 11,275 records, salvage 11,518)
  * `cfbenchmarks_value/20260902T22` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 1)
  * `cfbenchmarks_value/20260902T23` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 1)
  * `cfbenchmarks_value/20260903T00` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 8)
  * `cfbenchmarks_value/20260903T01` -- error: Error -3 while decompressing data: invalid block type (ordinary reader 0 records, salvage 1)

## The number that discounts the discount cliff

| `trade` channel | seconds | of covered |
|---|---|---|
| covered by a file, between the first and last print | 1,485,556 | 100% |
| with at least one print | 1,390,217 | 93.58% |
| SILENT | 95,339 | **6.42%** |
| ... inside a silent run >= 10 s | 84,645 | 5.70% |
| ... inside a silent run >= 60 s | 47,536 | 3.20% |

**The window that matters is the last 30 s before each 15-minute close** (`pinrun.TAU_MAX` = 30). Over **1,651 fully-taped close windows** (49,530 window-seconds):

| window seconds | count | fraction |
|---|---|---|
| inside a `trade` silent run >= 10 s | 1,879 | **3.794%** |
| silent at all (any run length) | 4,590 | 9.267% |

Narrowed to the band `pintrades.py` actually keeps -- `TAU_MIN <= tau <= TAU_MAX`, so tau in [3, 30], 28 seconds per close rather than 30 (46,228 window-seconds):

| window seconds, tau in [3, 30] | count | fraction |
|---|---|---|
| inside a `trade` silent run >= 10 s | 1,517 | **3.282%** |
| silent at all (any run length) | 4,103 | 8.876% |

**And the actionable version -- with a warning about the threshold.** The tables above pool everything, including the hours this file flags unusable. Restricting to closes whose whole window sits in a good hour gives:

| closes kept | closes | window s | in a run >= 10 s | fraction |
|---|---|---|---|---|
| all fully-taped | 1,651 | 49,530 | 1,879 | 3.794% |
| hours not flagged `HOLE` | 1,265 | 37,950 | 271 | **0.714%** |
| hours flagged `OK` (>2% silent = DEGRADED) | 13 | 390 | 1 | 0.256% |

**Read the middle row, not the bottom one, and here is why.** The `DEGRADED` threshold is 2% of an hour's seconds silent, and on this channel that is BELOW the baseline: the median `trade` hour is 3.78% silent with no long run in it at all. So 2% flags 313 of 414 hours and leaves 4 `OK`, which is not a measurement of anything -- it is a threshold set under the noise floor. The distribution is printed below so a later stage can pick its own. `HOLE` (any run >= 60 s) does not have this problem and is the exclusion that works.

## WHERE in the 15-minute cycle the holes sit

`seq` says whether a hole hid anything; this says whether it hid anything we would have traded. A market settles at the close and its replacement has no flow for a while, so silence just AFTER a close is structural. The bot trades just BEFORE one.

Split by length, because the two populations are nothing alike: the ordinary 10-59 s gap is a thin book, and a run over 60 s is an outage. Pooling them puts an hour-long outage in the dead-zone bucket and makes the structural silence look enormous.

| start of the run, relative to the 15-min cycle | runs 10-59 s | their silent s | runs >= 60 s | their silent s | longest |
|---|---|---|---|---|---|
| 0-15 s after a close (settlement dead zone) | 1,190 | 30,915 | 178 | 19,526 | 3600 |
| 15-60 s after | 49 | 675 | 0 | 0 | 22 |
| 1-5 min after | 7 | 119 | 16 | 13,648 | 2548 |
| 5 min after .. 30 s before the next close | 19 | 310 | 26 | 11,607 | 2124 |
| **the last 30 s before a close -- the window** | 190 | 5,090 | 8 | 2,755 | 1823 |
| **all** | **1,455** | **37,109** | **228** | **47,536** | **3600** |

## Did the silence hide anything? the `seq` verdict

Every `trade` silent run >= 30 s, on the exchange's own sequence number. This is not an inference from message density -- it is the exchange saying how many messages it sent.

**The two columns of lost messages are not the same failure and must not be added.** `in a clean file` is a stream loss: the exchange sent a message, the socket or the collector dropped it, and it was never written. `next to a damaged gzip` is a DISK loss: the bytes were written, then a collector restart left a member with no trailer and the decompressor cannot reach them (see `research/gzsalvage.py`). The second kind is concentrated in a handful of hours, is already flagged `HOLE`/`DEGRADED` below, and is excludable; the first kind is spread thin and is not.

| verdict | runs | silent seconds | lost, in a clean file | lost, next to a damaged gzip | meaning |
|---|---|---|---|---|---|
| `QUIET` | 1 | 33 | 0 | 0 | `seq` contiguous either side -- the exchange sent nothing, so no count was lost |
| `DROPPED` | 655 | 36,080 | 648 | 210,681 | `seq` skipped forward -- that many messages were sent and are not on disk |
| `RECONNECT` | 42 | 19,583 | unknowable | unknowable | `seq` reset to 1 -- a new subscription. Our socket dropped; how much was missed is NOT knowable from `seq` |
| `UNKNOWN` | 7 | 9,573 | unknowable | unknowable | no record either side of the hole inside continuous coverage, so `seq` was never compared and NOTHING can be claimed -- an adjacent hour has no file |
| **total** | **705** | **65,269** | **648** | **210,681** | |

And the density witnesses on the same runs -- a cross-tab, because the two axes are independent and the interesting cell is a hole whose book and index kept running:

| verdict | `BOOK_AND_INDEX_UP` | `BOOK_DOWN_INDEX_UP` | `BOTH_DOWN` | `INDEX_DOWN` | `MIXED` | `NO_WITNESS` |
|---|---|---|---|---|---|---|
| `QUIET` | 1 | 0 | 0 | 0 | 0 | 0 |
| `DROPPED` | 1 | 511 | 8 | 5 | 128 | 2 |
| `RECONNECT` | 0 | 38 | 3 | 0 | 1 | 0 |
| `UNKNOWN` | 0 | 2 | 4 | 0 | 1 | 0 |

* `BOOK_AND_INDEX_UP` -- book and index both running throughout
* `BOOK_DOWN_INDEX_UP` -- the book went silent too, but the 1/s index kept ticking on the same socket -- a market-data subscription failed, the connection did not
* `BOTH_DOWN` -- book and 1/s index silent at the same seconds -- the socket was down
* `INDEX_DOWN` -- the 1/s index metronome stopped, the book did not
* `MIXED` -- partial activity on the other channels
* `NO_WITNESS` -- a witness channel has no file for those seconds

Channel-wide, wherever they fall, and SPLIT ON THE SAME LINE: in files that decompressed cleanly `trade` has **3,534** forward `seq` jumps totalling **3,542 missing sequence numbers** against 62,950,750 records read -- **0.0056% of the stream** -- plus **45 subscription resets**. Everything else sits beside a damaged gzip.

| channel | records | clean-file jumps | numbers missing | % of stream | numbers missing beside a damaged gzip | resets |
|---|---|---|---|---|---|---|
| `trade` | 62,950,750 | 3,534 | 3,542 | 0.0056% | 210,717 | 45 |
| `orderbook_delta` | 1,351,014,801 | 6,505 | 64,740 | 0.0048% | 4,156,620 | 45 |
| `cfbenchmarks_value` | 15,690,221 | 1 | 2 | 0.0000% | 2,293,538 | 62 |

## The worst 20 `trade` silent runs

`s after close` is where the run starts in the 15-minute cycle: 0 is the close itself, 870-899 is the window the bot trades.

| start (UTC) | length s | s after close | book s active | index s active | `seq` | verdict | witness |
|---|---|---|---|---|---|---|---|
| 2026-09-03T07:00:00Z | **3600** | 0 | 4/3600 | 3596/3600 | never compared | `UNKNOWN` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-02T21:17:50Z | **2548** | 170 | 5/2548 | 1/2548 | lost 97,784 (damaged gzip) | `DROPPED` | `BOTH_DOWN` |
| 2026-09-09T21:00:00Z | **2547** | 0 | 0/2547 | 6/2547 | never compared | `UNKNOWN` | `BOTH_DOWN` |
| 2026-09-02T00:24:59Z | **2124** | 599 | 7/2124 | 1/2124 | lost 112,884 (damaged gzip) | `DROPPED` | `BOTH_DOWN` |
| 2026-09-09T13:29:37Z | **1823** | 877 | 1/1823 | 1/1823 | never compared | `UNKNOWN` | `BOTH_DOWN` |
| 2026-08-26T05:39:59Z | **1201** | 599 | 0/1201 | 0/1201 | never compared | `UNKNOWN` | `BOTH_DOWN` |
| 2026-09-01T05:01:07Z | **842** | 67 | 0/842 | 841/842 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-12T11:47:23Z | **822** | 143 | 0/822 | 821/822 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-06T07:16:52Z | **816** | 112 | 0/816 | 814/816 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-09T05:17:19Z | **786** | 139 | 0/786 | 785/786 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-12T06:18:21Z | **767** | 201 | 0/767 | 758/767 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-11T07:18:27Z | **757** | 207 | 0/757 | 756/757 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-08-29T08:32:35Z | **753** | 155 | 2/753 | 752/753 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-11T23:19:00Z | **729** | 240 | 0/729 | 727/729 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-09T07:03:10Z | **726** | 190 | 1/726 | 725/726 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-07T08:18:33Z | **714** | 213 | 0/714 | 713/714 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-02T05:48:43Z | **693** | 223 | 1/693 | 16/693 | reset | `RECONNECT` | `BOTH_DOWN` |
| 2026-09-07T07:33:43Z | **691** | 223 | 1/691 | 688/691 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-08-27T16:34:14Z | **687** | 254 | 0/687 | 683/687 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |
| 2026-09-07T08:34:24Z | **662** | 264 | 0/662 | 661/662 | reset | `RECONNECT` | `BOOK_DOWN_INDEX_UP` |

### the worst 10 on each of the other two channels, for contrast

| channel | start (UTC) | length s | s after close |
|---|---|---|---|
| `orderbook_delta` | 2026-08-27T07:00:03Z | 3597 | 3 |
| `orderbook_delta` | 2026-09-10T07:00:03Z | 3597 | 3 |
| `orderbook_delta` | 2026-09-03T07:00:04Z | 3596 | 4 |
| `orderbook_delta` | 2026-08-26T05:04:44Z | 3316 | 284 |
| `orderbook_delta` | 2026-09-09T21:00:00Z | 2547 | 0 |
| `orderbook_delta` | 2026-09-02T21:17:50Z | 2529 | 170 |
| `orderbook_delta` | 2026-09-02T00:24:59Z | 2101 | 599 |
| `orderbook_delta` | 2026-09-09T13:29:38Z | 1822 | 878 |
| `orderbook_delta` | 2026-09-01T05:01:07Z | 842 | 67 |
| `orderbook_delta` | 2026-09-12T11:47:23Z | 822 | 143 |
| `cfbenchmarks_value` | 2026-09-03T02:00:00Z | 7198 | 0 |
| `cfbenchmarks_value` | 2026-09-03T03:59:59Z | 3601 | 899 |
| `cfbenchmarks_value` | 2026-09-02T01:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-02T02:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-02T03:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-02T04:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-02T05:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-02T22:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-02T23:00:01Z | 3599 | 1 |
| `cfbenchmarks_value` | 2026-09-03T00:00:01Z | 3599 | 1 |

## message stamp vs receipt stamp

A hole in the exchange clock but not in ours means the exchange sent nothing; a hole in ours but not the exchange's means we flushed late.

| channel | silent s by `ts_ms` | silent s by `_rx_ms` | runs >= 10 s by `ts_ms` | by `_rx_ms` |
|---|---|---|---|---|
| `trade` | 95,339 (6.42%) | 110,025 (7.41%) | 1683 | 1710 |
| `orderbook_delta` | 87,831 (5.89%) | 99,051 (6.64%) | 1455 | 1496 |
| `cfbenchmarks_value` | 59,567 (3.96%) | 124,142 (8.26%) | 85 | 194 |

## Per day

`silent` counts seconds with zero messages on that channel, only inside hours whose file exists. `win` is the last 30 s before each fully-taped 15-minute close; `tau` narrows it to tau in [3, 30].

| day | hrs | trade silent s | % | book silent s | % | index silent s | % | closes | win s in run>=10s | % | tau s in run>=10s | % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-25 | 21 | 3,248 | 4.50 | 2,402 | 3.33 | 354 | 0.50 | 81 | 27 | 1.11 | 2 | **0.09** |
| 2026-08-26 | 6 | 2,315 | 10.72 | 4,092 | 18.94 | 1,306 | 6.05 | 24 | 98 | 13.61 | 88 | **13.10** |
| 2026-08-27 | 24 | 7,856 | 9.92 | 10,473 | 12.65 | 871 | 1.01 | 88 | 321 | 12.16 | 282 | **11.44** |
| 2026-08-28 | 24 | 3,806 | 4.41 | 2,649 | 3.07 | 100 | 0.12 | 96 | 90 | 3.12 | 65 | **2.42** |
| 2026-08-29 | 24 | 3,420 | 3.96 | 2,638 | 3.05 | 39 | 0.05 | 96 | 46 | 1.60 | 31 | **1.15** |
| 2026-08-30 | 24 | 3,084 | 3.57 | 2,113 | 2.45 | 238 | 0.28 | 96 | 49 | 1.70 | 29 | **1.08** |
| 2026-08-31 | 24 | 3,786 | 4.38 | 2,955 | 3.42 | 8 | 0.01 | 96 | 77 | 2.67 | 58 | **2.16** |
| 2026-09-01 | 24 | 3,800 | 4.40 | 2,700 | 3.12 | 300 | 0.35 | 96 | 71 | 2.47 | 37 | **1.38** |
| 2026-09-02 | 24 | 8,734 | 10.11 | 7,413 | 8.58 | 29,924 | 34.63 | 96 | 254 | 8.82 | 202 | **7.51** |
| 2026-09-03 | 24 | 6,969 | 8.42 | 5,843 | 7.06 | 21,657 | 25.07 | 92 | 150 | 5.43 | 122 | **4.74** |
| 2026-09-04 | 24 | 4,113 | 4.76 | 2,790 | 3.23 | 71 | 0.08 | 96 | 47 | 1.63 | 31 | **1.15** |
| 2026-09-05 | 24 | 3,162 | 3.66 | 2,231 | 2.58 | 0 | 0.00 | 96 | 8 | 0.28 | 0 | **0.00** |
| 2026-09-06 | 24 | 3,980 | 4.61 | 3,103 | 3.59 | 156 | 0.18 | 96 | 42 | 1.46 | 28 | **1.04** |
| 2026-09-07 | 24 | 5,582 | 6.46 | 4,571 | 5.29 | 108 | 0.12 | 96 | 140 | 4.86 | 126 | **4.69** |
| 2026-09-08 | 24 | 2,671 | 3.09 | 1,985 | 2.30 | 28 | 0.03 | 96 | 2 | 0.07 | 0 | **0.00** |
| 2026-09-09 | 17 | 8,074 | 13.19 | 7,381 | 12.06 | 4,367 | 7.14 | 68 | 205 | 10.05 | 189 | **9.93** |
| 2026-09-10 | 24 | 5,448 | 6.88 | 8,456 | 10.21 | 11 | 0.01 | 88 | 30 | 1.14 | 28 | **1.14** |
| 2026-09-11 | 24 | 9,038 | 10.46 | 8,340 | 9.65 | 18 | 0.02 | 96 | 130 | 4.51 | 115 | **4.28** |
| 2026-09-12 | 15 | 6,253 | 11.90 | 5,696 | 11.22 | 11 | 0.02 | 58 | 92 | 5.29 | 84 | **5.17** |
| **all** | **419** | **95,339** | **6.42** | **87,831** | **5.89** | **59,567** | **3.96** | **1651** | **1,879** | **3.79** | **1,517** | **3.28** |

## Per-hour recording health

`HOLE` = a silent run >= 60 s overlaps the hour. `DEGRADED` = more than 2% of its covered seconds silent, with no run that long. `MISSING` = no file on that channel for that hour. A later stage wanting a clean tape excludes `HOLE` and `DEGRADED`; the machine-readable list is `results/tapegaps_hours.json`, and every run >= 10 s with its classification is `results/tapegaps_runs.json`.

Per-hour silent fraction, so the thresholds can be judged rather than trusted. A channel whose median hour is already above the `DEGRADED` line cannot be filtered by it.

| channel | hours | p10 | p25 | **p50** | p75 | p90 | p99 | max |
|---|---|---|---|---|---|---|---|---|
| `trade` | 414 | 2.72% | 3.14% | **3.78%** | 4.94% | 9.69% | 52.47% | 100.00% |
| `orderbook_delta` | 416 | 1.58% | 2.03% | **2.69%** | 3.69% | 9.53% | 71.64% | 99.94% |
| `cfbenchmarks_value` | 418 | 0.00% | 0.00% | **0.00%** | 0.00% | 0.86% | 99.97% | 100.00% |

| channel | OK | DEGRADED | HOLE | MISSING |
|---|---|---|---|---|
| `trade` | 4 | 313 | 97 | 5 |
| `orderbook_delta` | 97 | 223 | 96 | 3 |
| `cfbenchmarks_value` | 393 | 3 | 22 | 1 |

**`trade`** -- `hour(longest run s/total silent s)`

* HOLE (97): 08-25T04(161/299), 08-25T18(438/515), 08-26T03(417/538), 08-26T04(417/75), 08-26T05(1201/1311), 08-27T00(374/1001), 08-27T01(366/486), 08-27T02(366/163), 08-27T04(609/708), 08-27T09(371/482), 08-27T10(586/1198), 08-27T12(519/601), 08-27T13(519/130), 08-27T15(503/593), 08-27T16(687/768), 08-28T07(655/765), 08-28T11(198/310), 08-29T08(753/851), 08-30T12(408/524), 08-30T13(408/135), 08-31T07(256/323), 08-31T08(632/727), 09-01T05(842/922), 09-02T00(2124/2157), 09-02T01(2124/102), 09-02T05(693/805), 09-02T06(693/143), 09-02T21(2548/2603), 09-02T22(2548/160), 09-03T07(3600/3600), 09-04T07(77/218), 09-04T12(434/544), 09-04T13(434/151), 09-05T01(60/166), 09-06T07(816/921), 09-06T14(150/332), 09-07T05(490/568), 09-07T07(691/779), 09-07T08(714/1815), 09-09T05(786/850), 09-09T07(726/807), 09-09T13(1823/1889), 09-09T21(2547/2580), 09-10T09(84/343), 09-10T10(277/498), 09-10T11(277/311), 09-10T12(79/305), 09-10T13(68/266), 09-10T14(78/287), 09-10T15(87/305), 09-10T16(62/242), 09-10T17(86/307), 09-10T18(81/287), 09-10T19(74/295), 09-10T20(92/315), 09-10T21(92/302), 09-10T22(83/288), 09-10T23(82/292), 09-11T00(94/342), 09-11T01(81/285), 09-11T02(93/349), 09-11T03(81/292), 09-11T04(80/306), 09-11T05(230/451), 09-11T06(82/311), 09-11T07(757/976), 09-11T08(98/335), 09-11T09(81/307), 09-11T10(67/290), 09-11T11(87/339), 09-11T12(198/435), 09-11T13(84/309), 09-11T14(84/303), 09-11T15(75/294), 09-11T16(88/354), 09-11T17(80/313), 09-11T18(84/303), 09-11T19(86/318), 09-11T20(82/285), 09-11T21(79/290), 09-11T22(80/284), 09-11T23(729/967), 09-12T00(99/350), 09-12T01(85/302), 09-12T02(84/308), 09-12T03(89/280), 09-12T04(97/340), 09-12T05(82/319), 09-12T06(767/1004), 09-12T07(104/340), 09-12T08(87/326), 09-12T09(72/329), 09-12T10(86/342), 09-12T11(822/1066), 09-12T12(822/335), 09-12T13(98/376), 09-12T14(84/236)
* DEGRADED (313): 08-25T05(38/121), 08-25T06(32/121), 08-25T07(34/152), 08-25T08(35/163), 08-25T09(27/136), 08-25T10(34/131), 08-25T11(34/147), 08-25T12(23/149), 08-25T13(28/115), 08-25T14(33/138), 08-25T15(34/136), 08-25T16(28/117), 08-25T17(32/138), 08-25T19(31/128), 08-25T20(33/159), 08-25T21(29/101), 08-25T22(38/165), 08-25T23(38/117), 08-26T00(32/140), 08-26T01(32/122), 08-26T02(29/129), 08-27T03(46/168), 08-27T05(52/164), 08-27T06(34/167), 08-27T11(34/152), 08-27T14(30/169), 08-27T17(41/172), 08-27T18(37/167), 08-27T19(34/111), 08-27T20(22/96), 08-27T21(20/94), 08-27T22(21/106), 08-27T23(34/160), 08-28T00(33/141), 08-28T01(30/172), 08-28T02(30/133), 08-28T03(29/118), 08-28T04(26/115), 08-28T05(20/81), 08-28T06(16/121), 08-28T08(28/145), 08-28T09(35/122), 08-28T10(14/149), 08-28T12(31/134), 08-28T13(33/137), 08-28T14(33/164), 08-28T15(36/157), 08-28T16(36/145), 08-28T17(37/124), 08-28T18(12/92), 08-28T20(18/83), 08-28T21(25/89), 08-28T22(29/118), 08-28T23(33/130), 08-29T00(36/112), 08-29T01(14/87), 08-29T02(21/97), 08-29T03(21/95), 08-29T04(25/100), 08-29T05(26/102), 08-29T06(26/123), 08-29T07(23/101), 08-29T09(34/99), 08-29T10(36/158), 08-29T11(32/127), 08-29T12(28/112), 08-29T13(28/108), 08-29T14(26/120), 08-29T15(27/109), 08-29T16(31/120), 08-29T17(35/123), 08-29T18(12/85), 08-29T19(38/132), 08-29T20(37/137), 08-29T21(33/135), 08-29T22(28/102), 08-29T23(22/85), 08-30T01(13/75), 08-30T02(36/102), 08-30T03(36/123), 08-30T04(31/118), 08-30T05(25/95), 08-30T07(38/126), 08-30T08(30/113), 08-30T09(21/75), 08-30T10(37/150), 08-30T11(31/114), 08-30T14(33/119), 08-30T15(25/95), 08-30T16(20/85), 08-30T17(13/75), 08-30T18(39/141), 08-30T19(39/161), 08-30T20(41/150), 08-30T21(15/109), 08-30T22(41/135), 08-30T23(40/141), 08-31T00(36/142), 08-31T01(32/128), 08-31T02(28/128), 08-31T03(25/98), 08-31T04(19/109), 08-31T05(36/154), 08-31T06(29/104), 08-31T09(31/113), 08-31T10(23/100), 08-31T11(39/156), 08-31T12(35/142), 08-31T13(24/103), 08-31T14(23/100), 08-31T15(17/88), 08-31T16(40/125), 08-31T17(38/174), 08-31T18(36/148), 08-31T19(36/144), 08-31T20(31/121), 08-31T21(29/126), 08-31T22(28/115), 08-31T23(26/118), 09-01T00(28/124), 09-01T01(28/120), 09-01T02(28/120), 09-01T03(25/126), 09-01T04(25/103), 09-01T06(35/146), 09-01T07(24/105), 09-01T08(38/122), 09-01T09(35/141), 09-01T10(25/135), 09-01T11(18/78), 09-01T12(39/155), 09-01T13(30/113), 09-01T14(25/116), 09-01T15(21/125), 09-01T16(16/104), 09-01T17(27/111), 09-01T18(27/146), 09-01T19(15/91), 09-01T20(42/160), 09-01T21(36/149), 09-01T22(34/156), 09-01T23(27/132), 09-02T02(22/96), 09-02T03(47/160), 09-02T04(39/166), 09-02T07(36/147), 09-02T08(30/125), 09-02T09(43/199), 09-02T10(35/145), 09-02T11(44/188), 09-02T12(36/182), 09-02T13(26/133), 09-02T14(47/137), 09-02T15(42/198), 09-02T16(37/178), 09-02T17(30/182), 09-02T18(29/127), 09-02T19(22/99), 09-02T20(28/140), 09-02T23(22/162), 09-03T00(32/142), 09-03T01(22/148), 09-03T02(21/110), 09-03T03(52/133), 09-03T04(44/127), 09-03T05(44/222), 09-03T06(41/153), 09-03T09(49/140), 09-03T10(49/191), 09-03T11(39/190), 09-03T12(31/166), 09-03T13(25/107), 09-03T14(47/168), 09-03T15(41/178), 09-03T16(33/140), 09-03T17(29/121), 09-03T18(25/146), 09-03T19(22/167), 09-03T20(42/155), 09-03T21(39/159), 09-03T22(37/149), 09-03T23(34/157), 09-04T00(48/186), 09-04T01(49/161), 09-04T02(50/166), 09-04T03(25/145), 09-04T04(49/188), 09-04T05(51/187), 09-04T06(37/143), 09-04T08(35/186), 09-04T09(46/147), 09-04T10(46/167), 09-04T11(37/179), 09-04T14(34/144), 09-04T15(38/109), 09-04T16(17/92), 09-04T17(47/158), 09-04T18(45/146), 09-04T19(35/136), 09-04T20(45/127), 09-04T21(26/134), 09-04T22(51/171), 09-04T23(32/128), 09-05T00(39/140), 09-05T02(43/159), 09-05T03(40/124), 09-05T04(19/102), 09-05T05(39/119), 09-05T06(45/137), 09-05T07(43/156), 09-05T08(34/127), 09-05T09(25/122), 09-05T10(22/131), 09-05T11(43/142), 09-05T12(36/152), 09-05T13(30/141), 09-05T14(24/121), 09-05T15(26/154), 09-05T16(51/129), 09-05T17(20/92), 09-05T18(46/122), 09-05T19(40/104), 09-05T20(40/145), 09-05T21(41/157), 09-05T22(40/127), 09-05T23(18/93), 09-06T00(20/97), 09-06T01(48/137), 09-06T02(21/109), 09-06T03(24/109), 09-06T04(43/119), 09-06T05(42/140), 09-06T06(35/145), 09-06T08(27/113), 09-06T09(21/106), 09-06T10(37/143), 09-06T11(33/130), 09-06T12(54/162), 09-06T13(17/96), 09-06T15(33/120), 09-06T16(44/129), 09-06T17(42/124), 09-06T18(37/117), 09-06T19(29/124), 09-06T20(41/126), 09-06T21(44/133), 09-06T22(40/131), 09-06T23(46/117), 09-07T00(36/106), 09-07T01(25/96), 09-07T02(22/90), 09-07T03(23/99), 09-07T04(21/115), 09-07T06(36/142), 09-07T09(34/117), 09-07T10(44/161), 09-07T11(32/128), 09-07T12(42/121), 09-07T13(23/99), 09-07T14(32/113), 09-07T15(35/131), 09-07T16(22/110), 09-07T17(30/118), 09-07T18(41/129), 09-07T19(26/110), 09-07T20(33/117), 09-07T21(35/114), 09-07T22(35/109), 09-07T23(16/95), 09-08T00(27/77), 09-08T01(35/124), 09-08T02(45/120), 09-08T03(36/115), 09-08T04(33/112), 09-08T05(35/96), 09-08T06(30/134), 09-08T07(39/107), 09-08T08(22/85), 09-08T09(36/119), 09-08T10(44/160), 09-08T11(22/98), 09-08T12(35/140), 09-08T13(46/100), 09-08T14(51/109), 09-08T15(34/110), 09-08T16(39/128), 09-08T17(28/93), 09-08T18(34/109), 09-08T19(37/126), 09-08T20(36/99), 09-08T21(25/84), 09-08T22(38/133), 09-08T23(16/93), 09-09T00(34/105), 09-09T01(40/108), 09-09T02(30/111), 09-09T03(45/104), 09-09T04(33/109), 09-09T06(34/110), 09-09T08(33/110), 09-09T09(28/117), 09-09T10(46/573), 09-09T11(36/120), 09-09T12(39/133), 09-09T22(34/107), 09-09T23(39/141), 09-10T00(37/108), 09-10T01(39/120), 09-10T02(41/111), 09-10T03(31/126), 09-10T04(32/121), 09-10T05(38/131), 09-10T06(26/88)
* MISSING (5): 08-27T07, 08-27T08, 09-03T08, 09-10T07, 09-10T08

**`orderbook_delta`** -- `hour(longest run s/total silent s)`

* HOLE (96): 08-25T04(359/610), 08-25T18(435/469), 08-26T03(416/458), 08-26T04(416/59), 08-26T05(3316/3352), 08-27T00(371/961), 08-27T01(366/416), 08-27T02(366/138), 08-27T04(609/680), 08-27T07(3597/3598), 08-27T09(370/438), 08-27T10(586/1198), 08-27T12(502/571), 08-27T13(502/67), 08-27T15(503/533), 08-27T16(687/696), 08-28T07(655/715), 08-28T11(196/256), 08-29T08(751/797), 08-30T12(408/452), 08-30T13(408/101), 08-31T07(256/302), 08-31T08(630/705), 09-01T05(842/864), 09-02T00(2101/2134), 09-02T05(692/782), 09-02T06(692/127), 09-02T21(2529/2560), 09-03T07(3596/3596), 09-04T07(77/186), 09-04T12(434/522), 09-04T13(434/127), 09-06T07(816/893), 09-06T14(150/275), 09-07T05(489/533), 09-07T07(690/763), 09-07T08(714/1498), 09-09T05(786/842), 09-09T07(725/786), 09-09T13(1822/1875), 09-09T21(2547/2579), 09-10T07(3597/3597), 09-10T09(82/283), 09-10T10(256/455), 09-10T11(256/265), 09-10T12(78/259), 09-10T13(66/249), 09-10T14(76/267), 09-10T15(86/247), 09-10T16(61/224), 09-10T17(85/300), 09-10T18(79/277), 09-10T19(73/252), 09-10T20(90/283), 09-10T21(91/294), 09-10T22(81/279), 09-10T23(81/274), 09-11T00(92/313), 09-11T01(80/274), 09-11T02(92/321), 09-11T03(77/270), 09-11T04(77/261), 09-11T05(230/426), 09-11T06(80/275), 09-11T07(757/944), 09-11T08(98/305), 09-11T09(80/284), 09-11T10(66/234), 09-11T11(86/310), 09-11T12(197/402), 09-11T13(83/285), 09-11T14(83/284), 09-11T15(74/253), 09-11T16(85/289), 09-11T17(77/269), 09-11T18(83/283), 09-11T19(84/292), 09-11T20(81/274), 09-11T21(77/261), 09-11T22(79/274), 09-11T23(729/957), 09-12T00(98/343), 09-12T01(82/287), 09-12T02(81/284), 09-12T03(88/274), 09-12T04(96/315), 09-12T05(81/284), 09-12T06(767/964), 09-12T07(103/308), 09-12T08(86/321), 09-12T09(71/261), 09-12T10(81/303), 09-12T11(822/1045), 09-12T12(822/283), 09-12T13(97/356), 09-12T14(68/68)
* DEGRADED (223): 08-25T05(36/90), 08-25T06(30/89), 08-25T07(32/77), 08-25T08(29/73), 08-25T10(32/95), 08-25T13(26/73), 08-25T17(31/80), 08-25T19(29/88), 08-25T22(31/103), 08-25T23(36/73), 08-26T00(26/83), 08-26T02(23/83), 08-27T03(43/105), 08-27T05(48/88), 08-27T06(28/105), 08-27T11(28/107), 08-27T14(28/99), 08-27T17(37/148), 08-27T18(34/103), 08-27T19(31/93), 08-27T23(31/134), 08-28T00(30/111), 08-28T01(27/105), 08-28T02(28/110), 08-28T03(25/93), 08-28T04(23/85), 08-28T08(25/90), 08-28T12(27/99), 08-28T13(27/104), 08-28T14(27/99), 08-28T15(28/109), 08-28T21(22/79), 08-28T22(27/104), 08-28T23(30/111), 08-29T03(18/74), 08-29T04(22/78), 08-29T05(24/89), 08-29T06(21/91), 08-29T07(20/79), 08-29T10(31/122), 08-29T11(28/108), 08-29T12(25/101), 08-29T13(23/87), 08-29T14(23/85), 08-29T15(24/91), 08-29T16(28/106), 08-29T17(32/101), 08-29T20(36/108), 08-29T21(32/113), 08-29T22(25/83), 08-30T03(33/95), 08-30T04(29/108), 08-30T05(21/77), 08-30T07(35/100), 08-30T08(24/90), 08-30T11(25/91), 08-30T14(26/96), 08-30T15(21/73), 08-30T18(36/82), 08-30T20(37/87), 08-30T22(37/84), 08-30T23(36/113), 08-31T00(33/94), 08-31T01(29/110), 08-31T02(25/95), 08-31T03(22/81), 08-31T05(33/99), 08-31T06(26/90), 08-31T09(26/92), 08-31T11(34/81), 08-31T12(28/98), 08-31T16(37/84), 08-31T17(34/133), 08-31T18(31/116), 08-31T19(30/111), 08-31T20(28/107), 08-31T21(26/100), 08-31T22(23/85), 08-31T23(23/88), 09-01T00(24/92), 09-01T01(24/93), 09-01T02(24/91), 09-01T03(21/78), 09-01T06(32/114), 09-01T09(32/109), 09-01T12(34/124), 09-01T13(26/100), 09-01T20(37/136), 09-01T21(32/124), 09-01T22(28/98), 09-02T03(35/74), 09-02T04(36/97), 09-02T07(33/118), 09-02T08(23/75), 09-02T09(39/106), 09-02T10(28/93), 09-02T11(41/146), 09-02T12(29/104), 09-02T13(23/81), 09-02T14(44/109), 09-02T15(37/107), 09-02T16(32/119), 09-02T17(27/100), 09-02T18(24/91), 09-02T19(20/77), 09-03T03(49/105), 09-03T05(42/129), 09-03T06(40/142), 09-03T10(45/105), 09-03T11(37/141), 09-03T12(30/108), 09-03T13(22/83), 09-03T14(45/81), 09-03T15(38/149), 09-03T16(30/117), 09-03T17(26/98), 09-03T18(23/87), 09-03T19(20/73), 09-03T20(41/128), 09-03T21(37/148), 09-03T22(34/134), 09-03T23(33/96), 09-04T00(47/124), 09-04T01(44/105), 09-04T02(18/74), 09-04T04(45/117), 09-04T05(41/127), 09-04T06(34/130), 09-04T08(27/101), 09-04T10(42/100), 09-04T11(35/136), 09-04T14(33/129), 09-04T17(46/87), 09-04T18(44/81), 09-04T20(18/78), 09-04T22(50/124), 09-04T23(30/83), 09-05T00(35/84), 09-05T01(59/159), 09-05T02(27/79), 09-05T03(37/95), 09-05T05(38/93), 09-05T06(44/108), 09-05T07(40/125), 09-05T08(31/115), 09-05T09(23/85), 09-05T12(34/129), 09-05T13(27/102), 09-05T14(22/84), 09-05T15(21/81), 09-05T16(50/107), 09-05T18(43/81), 09-05T20(38/96), 09-05T21(37/118), 09-05T22(39/98), 09-06T01(45/100), 09-06T04(42/81), 09-06T05(39/122), 09-06T06(33/98), 09-06T08(20/74), 09-06T10(35/105), 09-06T11(30/111), 09-06T12(51/103), 09-06T15(32/95), 09-06T16(43/120), 09-06T17(34/81), 09-06T18(36/107), 09-06T19(27/74), 09-06T20(40/102), 09-06T21(43/76), 09-06T22(39/96), 09-06T23(43/104), 09-07T00(35/84), 09-07T02(21/77), 09-07T03(21/80), 09-07T06(32/122), 09-07T09(33/91), 09-07T10(38/83), 09-07T11(31/103), 09-07T12(41/85), 09-07T14(27/99), 09-07T15(34/97), 09-07T17(29/99), 09-07T18(40/112), 09-07T19(25/77), 09-07T20(32/109), 09-07T22(34/89), 09-08T01(34/81), 09-08T02(42/108), 09-08T03(35/81), 09-08T04(29/89), 09-08T05(31/75), 09-08T06(29/83), 09-08T07(38/90), 09-08T09(35/94), 09-08T10(43/89), 09-08T12(34/96), 09-08T13(45/81), 09-08T14(50/104), 09-08T15(32/102), 09-08T17(27/79), 09-08T19(36/112), 09-08T20(35/79), 09-08T22(36/105), 09-09T00(33/93), 09-09T01(38/99), 09-09T02(29/100), 09-09T03(44/98), 09-09T04(32/88), 09-09T06(30/79), 09-09T09(27/78), 09-09T10(45/211), 09-09T11(34/112), 09-09T12(36/86), 09-09T22(33/83), 09-09T23(36/101), 09-10T00(34/101), 09-10T01(36/112), 09-10T02(38/103), 09-10T03(30/73), 09-10T04(31/98), 09-10T05(35/83), 09-10T06(25/81)
* MISSING (3): 08-27T08, 09-03T08, 09-10T08

**`cfbenchmarks_value`** -- `hour(longest run s/total silent s)`

* HOLE (22): 08-25T04(61/61), 08-26T05(1201/1201), 08-27T00(284/401), 09-02T00(2108/2108), 09-02T01(3599/3599), 09-02T02(3599/3599), 09-02T03(3599/3599), 09-02T04(3599/3599), 09-02T05(3599/3599), 09-02T21(2535/2553), 09-02T22(3599/3599), 09-02T23(3599/3599), 09-03T00(3599/3599), 09-03T01(3598/3598), 09-03T02(7198/3600), 09-03T03(7198/3599), 09-03T04(3601/3600), 09-03T05(3599/3599), 09-04T07(70/70), 09-06T14(144/154), 09-09T13(1822/1822), 09-09T21(2541/2541)
* DEGRADED (3): 08-25T14(45/76), 08-27T08(49/107), 08-27T09(49/140)
* MISSING (1): 08-25T03

## What this means for the discount cliff

Over the whole tape the `trade` channel is silent for 95,339 of 1,485,556 covered seconds (**6.42%**), 84,645 of them inside a run of 10 s or longer. **In the window the bot trades -- the last 30 s before a close -- 3.794% of window-seconds fall inside a silent run >= 10 s** (1,879 of 49,530, over 1,651 fully-taped closes), 9.267% are silent at any run length, and **narrowing to the band `pintrades.py` keeps (tau in [3, 30]) gives 3.282%. Excluding only the hours carrying a run >= 60 s -- the `HOLE` flag, the one whose threshold is above this channel's noise floor -- it is 0.714% over the 1,265 closes that survive.** That is the discount on the counts. Of the 1,683 `trade` runs >= 10 s, **198 start in the last 30 s before a close** and **1,417 start within 60 s AFTER one**, which is the settlement dead zone: the old market has settled and its replacement has no flow yet. **On whether the holes are collector-side or exchange-side, `seq` is decisive.** Of the 705 silent runs of 30 s or more, **exactly 1 has `seq` contiguous either side** -- one single run where the exchange genuinely sent nothing. 655 carry a forward `seq` jump (messages sent and missing), 42 end with `seq` RESET TO 1 (a new subscription: our socket dropped and reconnected), and 7 have no record either side inside continuous coverage, so `seq` was never compared and nothing can be claimed. The density witnesses agree: on **551 of 705** of those runs the order book went silent alongside `trade` while the 1/s index kept ticking on the same socket -- a market-data subscription failing, not a dead connection and not a quiet market. **The size of the loss has to be split or it is off by two orders of magnitude:** in files that decompressed cleanly the `trade` stream is missing **3,542 sequence numbers against 62,950,750 records, 0.0056%**, while a further 210,681 sit beside a gzip a collector restart broke -- bytes that were written and cannot be decompressed, concentrated in the hours flagged below, a different failure with a different fix. Plus 45 subscription resets. The reset case is the honest problem: it proves the hole is ours, and it destroys the evidence of how much it cost, so those windows are a lower bound by an unmeasured amount rather than by zero. The single worst run is 3600 s from 2026-09-03T07:00:00Z, 0 s after a close.

## What this does NOT say

* Nothing here is a loss rate and nothing here is about our own fills. CLAUDE.md 2026-09-10: loss rates come from live fills only. This file discounts COUNTS.
* A silent second is not a second with no trading. It is a second with no RECORDED trade. Where `seq` is contiguous across the silence the two are the same thing; where it jumps or resets, they are not.
* A `RECONNECT` run's loss is unknowable, not zero. `seq` restarting at 1 destroys the only evidence of how many messages the old subscription would have carried. Any count over such a window is a lower bound by an unmeasured amount, and this file will not guess it.
* The witness columns use `orderbook_delta` and `cfbenchmarks_value` presence as evidence of socket health. That is density, not proof: a channel can be subscribed and idle. Only `seq` proves a message existed and is absent.
* Runs are cut at the edge of a covered interval, so a hole spanning a MISSING hour is reported as two runs and not one.
* A `seq` jump beside a file that needed salvage is NOT a stream loss. The bytes were written and a broken gzip member is in the way, so those records may still be recoverable and are certainly not evidence that the exchange-to-collector path dropped anything. The two are reported in separate columns everywhere and must never be added together.
* The bias this leaves is not measured here and cannot be. A count over a window containing a hole is biased only if what the hole hid differs from what it did not, and no test on this tape can settle that -- the hidden prints are, by construction, not on it.

