# lead_feedlead run 2026-09-25T02:27 UTC, 255 hours, 950 s

## Q1 -- does the constituent book lead the print?  (exchange clocks; every consecutive index print pair)
hours used: 86 (20260921T00 .. 20260924T23)

### (a) joint fit of the index 1-s change on the constituent mid change in six sub-windows (coefficient ~1 = already in the print, ~0 = not yet)
| coin | exchange | n seconds | R^2 all six | -1000..-900 | -900..-500 | -500..-200 | -200..0 | 0..+200 | +200..+500 |
|---|---|---|---|---|---|---|---|---|---|
| ADA | bitstamp | 282077 | 0.712 | 1.39 | 0.76 | 0.72 | 0.23 | -0.05 | 0.02 |
| ADA | coinbase | 281751 | 0.482 | 1.20 | 0.94 | 0.80 | 0.13 | -0.01 | -0.00 |
| ADA | kraken | 280016 | 0.257 | 0.98 | 1.02 | 1.10 | 0.48 | 0.12 | 0.06 |
| ADA | median | 282023 | 0.567 | 2.33 | 1.16 | 1.21 | 0.20 | -0.11 | -0.05 |
| BCH | bitstamp | 282077 | 0.674 | 1.42 | 0.72 | 0.71 | 0.30 | -0.05 | 0.02 |
| BCH | coinbase | 281680 | 0.544 | 0.95 | 0.79 | 0.71 | 0.18 | 0.01 | -0.01 |
| BCH | kraken | 253652 | 0.313 | 0.89 | 0.66 | 0.61 | 0.23 | 0.10 | 0.06 |
| BCH | median | 281937 | 0.574 | 1.46 | 0.87 | 0.84 | 0.23 | -0.01 | -0.01 |
| BTC | bitstamp | 282092 | 0.639 | 0.54 | 0.79 | 0.97 | 0.96 | 0.29 | 0.11 |
| BTC | coinbase | 281838 | 0.699 | 0.85 | 0.82 | 0.90 | 0.60 | 0.09 | 0.05 |
| BTC | gemini | 281991 | 0.534 | 0.37 | 0.63 | 0.76 | 0.71 | 0.39 | 0.17 |
| BTC | kraken | 282053 | 0.363 | -0.03 | 0.54 | 0.86 | 0.94 | 0.56 | 0.34 |
| BTC | median | 282082 | 0.694 | 0.84 | 0.99 | 1.25 | 1.30 | 0.18 | 0.06 |
| DOGE | bitstamp | 282075 | 0.780 | 1.12 | 0.88 | 0.95 | 0.83 | -0.06 | 0.04 |
| DOGE | coinbase | 281667 | 0.540 | 1.26 | 0.98 | 0.91 | 0.52 | -0.05 | -0.05 |
| DOGE | kraken | 281383 | 0.300 | 0.44 | 0.98 | 0.97 | 0.89 | 0.32 | 0.06 |
| DOGE | median | 282006 | 0.611 | 1.80 | 1.14 | 1.27 | 0.94 | -0.17 | -0.08 |
| ETH | bitstamp | 282086 | 0.619 | 1.03 | 0.73 | 0.79 | 0.69 | 0.12 | 0.10 |
| ETH | coinbase | 281807 | 0.574 | 1.03 | 0.82 | 0.77 | 0.40 | 0.01 | 0.03 |
| ETH | kraken | 282048 | 0.389 | 0.75 | 0.80 | 0.89 | 0.88 | 0.25 | 0.18 |
| ETH | median | 282080 | 0.610 | 1.68 | 0.95 | 1.07 | 0.83 | -0.04 | 0.02 |
| SOL | bitstamp | 282081 | 0.654 | 1.08 | 0.77 | 0.85 | 0.83 | -0.00 | 0.08 |
| SOL | coinbase | 281813 | 0.560 | 1.01 | 0.84 | 0.82 | 0.43 | 0.03 | 0.02 |
| SOL | kraken | 282045 | 0.352 | 0.95 | 0.82 | 0.94 | 0.66 | 0.15 | 0.10 |
| SOL | median | 282082 | 0.617 | 1.74 | 1.00 | 1.18 | 0.85 | -0.08 | -0.03 |
| XRP | bitstamp | 282084 | 0.672 | 1.10 | 0.61 | 0.61 | 0.52 | -0.02 | 0.03 |
| XRP | coinbase | 281817 | 0.561 | 0.92 | 0.68 | 0.59 | 0.29 | -0.02 | 0.00 |
| XRP | kraken | 281968 | 0.411 | 0.69 | 0.82 | 0.75 | 0.58 | 0.17 | 0.07 |
| XRP | median | 282074 | 0.648 | 1.71 | 0.78 | 0.80 | 0.57 | -0.11 | -0.03 |

### (b) lag scan: correlation of the index 1-s change with the constituent 1-s change shifted by k ms (peak k < 0 = the print reflects OLDER books = constituents lead)
| coin | exchange | n | peak k (ms) | corr at peak | R^2 at peak | corr k=0 | corr k=-200 | corr k=-500 | corr k=+200 | hit rate at peak |
|---|---|---|---|---|---|---|---|---|---|---|
| ADA | bitstamp | 282077 | -200 | 0.858 | 0.737 | 0.804 | 0.858 | 0.674 | 0.630 | 76.0% |
| ADA | coinbase | 281751 | -200 | 0.729 | 0.531 | 0.662 | 0.729 | 0.626 | 0.544 | 63.8% |
| ADA | kraken | 280016 | -100 | 0.508 | 0.258 | 0.503 | 0.497 | 0.402 | 0.468 | 57.5% |
| BCH | bitstamp | 282077 | -200 | 0.836 | 0.699 | 0.785 | 0.836 | 0.666 | 0.634 | 73.0% |
| BCH | coinbase | 281680 | -200 | 0.804 | 0.647 | 0.702 | 0.804 | 0.682 | 0.566 | 64.6% |
| BCH | kraken | 253652 | -200 | 0.596 | 0.355 | 0.540 | 0.596 | 0.504 | 0.463 | 58.3% |
| BTC | bitstamp | 282092 | +0 | 0.784 | 0.615 | 0.784 | 0.651 | 0.404 | 0.755 | 80.3% |
| BTC | coinbase | 281838 | -100 | 0.837 | 0.700 | 0.832 | 0.779 | 0.526 | 0.727 | 74.8% |
| BTC | gemini | 281991 | +100 | 0.700 | 0.490 | 0.690 | 0.561 | 0.337 | 0.680 | 72.6% |
| BTC | kraken | 282053 | +200 | 0.591 | 0.350 | 0.548 | 0.445 | 0.277 | 0.591 | 61.8% |
| DOGE | bitstamp | 282075 | +0 | 0.882 | 0.777 | 0.882 | 0.813 | 0.525 | 0.781 | 79.6% |
| DOGE | coinbase | 281667 | -100 | 0.750 | 0.563 | 0.722 | 0.723 | 0.564 | 0.606 | 64.8% |
| DOGE | kraken | 281383 | +100 | 0.543 | 0.294 | 0.541 | 0.500 | 0.387 | 0.525 | 58.7% |
| ETH | bitstamp | 282086 | +0 | 0.781 | 0.611 | 0.781 | 0.727 | 0.504 | 0.711 | 75.4% |
| ETH | coinbase | 281807 | -100 | 0.784 | 0.614 | 0.744 | 0.767 | 0.616 | 0.616 | 69.7% |
| ETH | kraken | 282048 | +0 | 0.618 | 0.381 | 0.618 | 0.570 | 0.454 | 0.597 | 63.0% |
| SOL | bitstamp | 282081 | +0 | 0.806 | 0.649 | 0.806 | 0.743 | 0.507 | 0.733 | 90.3% |
| SOL | coinbase | 281813 | -100 | 0.769 | 0.592 | 0.738 | 0.749 | 0.587 | 0.626 | 84.2% |
| SOL | kraken | 282045 | +0 | 0.592 | 0.350 | 0.592 | 0.564 | 0.455 | 0.559 | 73.9% |
| XRP | bitstamp | 282084 | -100 | 0.815 | 0.664 | 0.807 | 0.799 | 0.626 | 0.684 | 77.5% |
| XRP | coinbase | 281817 | -200 | 0.785 | 0.617 | 0.729 | 0.785 | 0.692 | 0.589 | 74.1% |
| XRP | kraken | 281968 | -100 | 0.641 | 0.411 | 0.638 | 0.634 | 0.551 | 0.597 | 64.5% |

### (c) single-window R^2 and sign hit rate (each window alone), median across exchanges where >=2 feeds
| coin | exchange | window | n | corr | R^2 | sign hit rate (both nonzero) | pairs both nonzero |
|---|---|---|---|---|---|---|---|
| ADA | bitstamp | prev1s | 282077 | 0.804 | 0.646 | 74.4% | 200207 |
| ADA | bitstamp | w_0_p200 | 282077 | 0.047 | 0.002 | 52.5% | 136104 |
| ADA | bitstamp | w_m1000_m900 | 282077 | 0.403 | 0.163 | 68.9% | 100080 |
| ADA | bitstamp | w_m200_0 | 282077 | 0.234 | 0.055 | 58.3% | 134929 |
| ADA | bitstamp | w_m500_m200 | 282077 | 0.484 | 0.234 | 65.5% | 158144 |
| ADA | bitstamp | w_m900_m500 | 282077 | 0.631 | 0.398 | 71.1% | 160808 |
| ADA | bitstamp | w_p200_p500 | 282077 | 0.011 | 0.000 | 50.8% | 133984 |
| ADA | coinbase | prev1s | 281751 | 0.662 | 0.438 | 63.2% | 262241 |
| ADA | coinbase | w_0_p200 | 281751 | 0.121 | 0.015 | 58.8% | 259148 |
| ADA | coinbase | w_m1000_m900 | 281751 | 0.352 | 0.124 | 61.8% | 258658 |
| ADA | coinbase | w_m200_0 | 281751 | 0.196 | 0.038 | 59.7% | 259138 |
| ADA | coinbase | w_m500_m200 | 281751 | 0.457 | 0.208 | 61.3% | 259721 |
| ADA | coinbase | w_m900_m500 | 281751 | 0.582 | 0.339 | 62.5% | 260218 |
| ADA | coinbase | w_p200_p500 | 281751 | 0.107 | 0.011 | 58.0% | 259601 |
| ADA | kraken | prev1s | 280016 | 0.503 | 0.253 | 57.5% | 260488 |
| ADA | kraken | w_0_p200 | 280016 | 0.229 | 0.053 | 57.0% | 259853 |
| ADA | kraken | w_m1000_m900 | 280016 | 0.258 | 0.067 | 56.8% | 259866 |
| ADA | kraken | w_m200_0 | 280016 | 0.276 | 0.076 | 57.2% | 259897 |
| ADA | kraken | w_m500_m200 | 280016 | 0.413 | 0.170 | 57.3% | 260024 |
| ADA | kraken | w_m900_m500 | 280016 | 0.436 | 0.190 | 57.2% | 260121 |
| ADA | kraken | w_p200_p500 | 280016 | 0.204 | 0.042 | 56.9% | 259904 |
| ADA | median | w_0_p200 | 282023 | 0.147 | 0.022 | 59.6% | 211419 |
| ADA | median | w_m1000_m900 | 282023 | 0.401 | 0.161 | 65.3% | 198054 |
| ADA | median | w_m200_0 | 282023 | 0.258 | 0.067 | 61.6% | 211160 |
| ADA | median | w_m500_m200 | 282023 | 0.512 | 0.262 | 64.4% | 219814 |
| ADA | median | w_m900_m500 | 282023 | 0.618 | 0.382 | 66.6% | 221107 |
| ADA | median | w_p200_p500 | 282023 | 0.101 | 0.010 | 58.7% | 210955 |
| BCH | bitstamp | prev1s | 282077 | 0.785 | 0.616 | 72.1% | 229824 |
| BCH | bitstamp | w_0_p200 | 282077 | 0.084 | 0.007 | 54.3% | 172704 |
| BCH | bitstamp | w_m1000_m900 | 282077 | 0.394 | 0.155 | 64.9% | 129596 |
| BCH | bitstamp | w_m200_0 | 282077 | 0.281 | 0.079 | 59.0% | 172162 |
| BCH | bitstamp | w_m500_m200 | 282077 | 0.490 | 0.241 | 64.7% | 198016 |
| BCH | bitstamp | w_m900_m500 | 282077 | 0.579 | 0.335 | 67.7% | 198135 |
| BCH | bitstamp | w_p200_p500 | 282077 | 0.038 | 0.001 | 53.0% | 173093 |
| BCH | coinbase | prev1s | 281680 | 0.702 | 0.493 | 63.8% | 260825 |
| BCH | coinbase | w_0_p200 | 281680 | 0.062 | 0.004 | 58.8% | 257986 |
| BCH | coinbase | w_m1000_m900 | 281680 | 0.302 | 0.091 | 62.2% | 257497 |
| BCH | coinbase | w_m200_0 | 281680 | 0.158 | 0.025 | 59.8% | 257968 |
| BCH | coinbase | w_m500_m200 | 281680 | 0.461 | 0.212 | 61.5% | 258539 |
| BCH | coinbase | w_m900_m500 | 281680 | 0.572 | 0.327 | 62.9% | 259022 |
| BCH | coinbase | w_p200_p500 | 281680 | 0.043 | 0.002 | 57.9% | 258444 |
| BCH | kraken | prev1s | 253652 | 0.540 | 0.292 | 58.4% | 207892 |
| BCH | kraken | w_0_p200 | 253652 | 0.101 | 0.010 | 57.7% | 207188 |
| BCH | kraken | w_m1000_m900 | 253652 | 0.208 | 0.043 | 57.6% | 207378 |
| BCH | kraken | w_m200_0 | 253652 | 0.162 | 0.026 | 57.9% | 207243 |
| BCH | kraken | w_m500_m200 | 253652 | 0.361 | 0.130 | 58.1% | 207386 |
| BCH | kraken | w_m900_m500 | 253652 | 0.425 | 0.181 | 58.0% | 207592 |
| BCH | kraken | w_p200_p500 | 253652 | 0.066 | 0.004 | 57.4% | 207220 |
| BCH | median | w_0_p200 | 281937 | 0.087 | 0.008 | 59.7% | 214495 |
| BCH | median | w_m1000_m900 | 281937 | 0.327 | 0.107 | 65.4% | 197944 |
| BCH | median | w_m200_0 | 281937 | 0.213 | 0.045 | 62.0% | 214380 |
| BCH | median | w_m500_m200 | 281937 | 0.483 | 0.234 | 65.1% | 224248 |
| BCH | median | w_m900_m500 | 281937 | 0.580 | 0.337 | 66.9% | 224665 |
| BCH | median | w_p200_p500 | 281937 | 0.051 | 0.003 | 58.6% | 214814 |
| BTC | bitstamp | prev1s | 282092 | 0.784 | 0.615 | 80.3% | 87533 |
| BTC | bitstamp | w_0_p200 | 282092 | 0.236 | 0.056 | 73.5% | 45145 |
| BTC | bitstamp | w_m1000_m900 | 282092 | 0.212 | 0.045 | 59.9% | 37143 |
| BTC | bitstamp | w_m200_0 | 282092 | 0.462 | 0.213 | 81.5% | 44980 |
| BTC | bitstamp | w_m500_m200 | 282092 | 0.574 | 0.329 | 82.8% | 51953 |
| BTC | bitstamp | w_m900_m500 | 282092 | 0.531 | 0.282 | 75.2% | 58315 |
| BTC | bitstamp | w_p200_p500 | 282092 | 0.139 | 0.019 | 66.5% | 52208 |
| BTC | coinbase | prev1s | 281838 | 0.832 | 0.692 | 76.1% | 154368 |
| BTC | coinbase | w_0_p200 | 281838 | 0.137 | 0.019 | 63.3% | 110436 |
| BTC | coinbase | w_m1000_m900 | 281838 | 0.304 | 0.092 | 63.0% | 101906 |
| BTC | coinbase | w_m200_0 | 281838 | 0.352 | 0.124 | 68.9% | 109672 |
| BTC | coinbase | w_m500_m200 | 281838 | 0.575 | 0.331 | 73.3% | 117153 |
| BTC | coinbase | w_m900_m500 | 281838 | 0.615 | 0.378 | 71.5% | 124344 |
| BTC | coinbase | w_p200_p500 | 281838 | 0.073 | 0.005 | 59.3% | 118107 |
| BTC | gemini | prev1s | 281991 | 0.690 | 0.476 | 72.8% | 165344 |
| BTC | gemini | w_0_p200 | 281991 | 0.192 | 0.037 | 57.9% | 131059 |
| BTC | gemini | w_m1000_m900 | 281991 | 0.124 | 0.015 | 60.9% | 122931 |
| BTC | gemini | w_m200_0 | 281991 | 0.332 | 0.110 | 61.8% | 130427 |
| BTC | gemini | w_m500_m200 | 281991 | 0.434 | 0.189 | 65.8% | 136783 |
| BTC | gemini | w_m900_m500 | 281991 | 0.418 | 0.175 | 67.0% | 142755 |
| BTC | gemini | w_p200_p500 | 281991 | 0.112 | 0.013 | 55.8% | 137303 |
| BTC | kraken | prev1s | 282053 | 0.548 | 0.301 | 59.7% | 146973 |
| BTC | kraken | w_0_p200 | 282053 | 0.346 | 0.119 | 63.3% | 120651 |
| BTC | kraken | w_m1000_m900 | 282053 | 0.144 | 0.021 | 51.7% | 116637 |
| BTC | kraken | w_m200_0 | 282053 | 0.432 | 0.187 | 62.3% | 119232 |
| BTC | kraken | w_m500_m200 | 282053 | 0.473 | 0.224 | 60.0% | 121978 |
| BTC | kraken | w_m900_m500 | 282053 | 0.373 | 0.139 | 55.7% | 128481 |
| BTC | kraken | w_p200_p500 | 282053 | 0.275 | 0.075 | 63.5% | 123000 |
| BTC | median | w_0_p200 | 282082 | 0.273 | 0.075 | 69.1% | 96185 |
| BTC | median | w_m1000_m900 | 282082 | 0.284 | 0.081 | 62.8% | 86341 |
| BTC | median | w_m200_0 | 282082 | 0.510 | 0.260 | 74.6% | 95339 |
| BTC | median | w_m500_m200 | 282082 | 0.645 | 0.415 | 77.0% | 103340 |
| BTC | median | w_m900_m500 | 282082 | 0.605 | 0.366 | 72.4% | 111558 |
| BTC | median | w_p200_p500 | 282082 | 0.158 | 0.025 | 64.5% | 104024 |
| DOGE | bitstamp | prev1s | 282075 | 0.882 | 0.777 | 79.6% | 217786 |
| DOGE | bitstamp | w_0_p200 | 282075 | 0.173 | 0.030 | 58.9% | 170399 |
| DOGE | bitstamp | w_m1000_m900 | 282075 | 0.319 | 0.102 | 62.3% | 134068 |
| DOGE | bitstamp | w_m200_0 | 282075 | 0.451 | 0.204 | 66.4% | 172445 |
| DOGE | bitstamp | w_m500_m200 | 282075 | 0.608 | 0.369 | 71.9% | 190935 |
| DOGE | bitstamp | w_m900_m500 | 282075 | 0.623 | 0.388 | 70.7% | 190295 |
| DOGE | bitstamp | w_p200_p500 | 282075 | 0.065 | 0.004 | 55.5% | 168499 |
| DOGE | coinbase | prev1s | 281667 | 0.722 | 0.522 | 64.5% | 242135 |
| DOGE | coinbase | w_0_p200 | 281667 | 0.122 | 0.015 | 59.4% | 236986 |
| DOGE | coinbase | w_m1000_m900 | 281667 | 0.341 | 0.116 | 62.6% | 236207 |
| DOGE | coinbase | w_m200_0 | 281667 | 0.275 | 0.075 | 60.7% | 236920 |
| DOGE | coinbase | w_m500_m200 | 281667 | 0.475 | 0.225 | 62.4% | 237825 |
| DOGE | coinbase | w_m900_m500 | 281667 | 0.583 | 0.340 | 63.6% | 238627 |
| DOGE | coinbase | w_p200_p500 | 281667 | 0.070 | 0.005 | 58.4% | 237667 |
| DOGE | kraken | prev1s | 281383 | 0.541 | 0.293 | 58.7% | 254167 |
| DOGE | kraken | w_0_p200 | 281383 | 0.247 | 0.061 | 58.0% | 253398 |
| DOGE | kraken | w_m1000_m900 | 281383 | 0.219 | 0.048 | 57.7% | 253314 |
| DOGE | kraken | w_m200_0 | 281383 | 0.319 | 0.101 | 58.2% | 253357 |
| DOGE | kraken | w_m500_m200 | 281383 | 0.402 | 0.162 | 58.4% | 253525 |
| DOGE | kraken | w_m900_m500 | 281383 | 0.437 | 0.191 | 58.2% | 253672 |
| DOGE | kraken | w_p200_p500 | 281383 | 0.186 | 0.034 | 57.6% | 253470 |
| DOGE | median | w_0_p200 | 282006 | 0.204 | 0.042 | 61.4% | 216289 |
| DOGE | median | w_m1000_m900 | 282006 | 0.378 | 0.143 | 64.3% | 203438 |
| DOGE | median | w_m200_0 | 282006 | 0.402 | 0.161 | 64.3% | 216784 |
| DOGE | median | w_m500_m200 | 282006 | 0.570 | 0.325 | 66.9% | 223678 |
| DOGE | median | w_m900_m500 | 282006 | 0.611 | 0.373 | 67.1% | 223982 |
| DOGE | median | w_p200_p500 | 282006 | 0.107 | 0.012 | 59.6% | 215961 |
| ETH | bitstamp | prev1s | 282086 | 0.781 | 0.611 | 75.4% | 168904 |
| ETH | bitstamp | w_0_p200 | 282086 | 0.233 | 0.054 | 65.3% | 114159 |
| ETH | bitstamp | w_m1000_m900 | 282086 | 0.292 | 0.085 | 61.1% | 85108 |
| ETH | bitstamp | w_m200_0 | 282086 | 0.422 | 0.178 | 70.7% | 115110 |
| ETH | bitstamp | w_m500_m200 | 282086 | 0.536 | 0.287 | 72.3% | 134357 |
| ETH | bitstamp | w_m900_m500 | 282086 | 0.536 | 0.287 | 68.2% | 133736 |
| ETH | bitstamp | w_p200_p500 | 282086 | 0.113 | 0.013 | 60.3% | 113532 |
| ETH | coinbase | prev1s | 281807 | 0.744 | 0.553 | 69.4% | 245447 |
| ETH | coinbase | w_0_p200 | 281807 | 0.113 | 0.013 | 60.3% | 233201 |
| ETH | coinbase | w_m1000_m900 | 281807 | 0.358 | 0.128 | 64.2% | 230603 |
| ETH | coinbase | w_m200_0 | 281807 | 0.270 | 0.073 | 62.9% | 232902 |
| ETH | coinbase | w_m500_m200 | 281807 | 0.491 | 0.241 | 65.8% | 235301 |
| ETH | coinbase | w_m900_m500 | 281807 | 0.598 | 0.357 | 67.1% | 237497 |
| ETH | coinbase | w_p200_p500 | 281807 | 0.073 | 0.005 | 58.1% | 235553 |
| ETH | kraken | prev1s | 282048 | 0.618 | 0.381 | 63.0% | 235915 |
| ETH | kraken | w_0_p200 | 282048 | 0.308 | 0.095 | 61.4% | 226981 |
| ETH | kraken | w_m1000_m900 | 282048 | 0.304 | 0.093 | 60.9% | 225202 |
| ETH | kraken | w_m200_0 | 282048 | 0.417 | 0.174 | 62.1% | 226399 |
| ETH | kraken | w_m500_m200 | 282048 | 0.497 | 0.247 | 62.6% | 227589 |
| ETH | kraken | w_m900_m500 | 282048 | 0.500 | 0.250 | 62.3% | 229927 |
| ETH | kraken | w_p200_p500 | 282048 | 0.256 | 0.065 | 60.4% | 228075 |
| ETH | median | w_0_p200 | 282080 | 0.239 | 0.057 | 66.0% | 173612 |
| ETH | median | w_m1000_m900 | 282080 | 0.390 | 0.152 | 67.4% | 160626 |
| ETH | median | w_m200_0 | 282080 | 0.421 | 0.177 | 69.3% | 173779 |
| ETH | median | w_m500_m200 | 282080 | 0.577 | 0.333 | 71.6% | 183131 |
| ETH | median | w_m900_m500 | 282080 | 0.610 | 0.372 | 70.5% | 184930 |
| ETH | median | w_p200_p500 | 282080 | 0.138 | 0.019 | 63.0% | 175203 |
| SOL | bitstamp | prev1s | 282081 | 0.806 | 0.649 | 90.3% | 93408 |
| SOL | bitstamp | w_0_p200 | 282081 | 0.231 | 0.053 | 70.3% | 63425 |
| SOL | bitstamp | w_m1000_m900 | 282081 | 0.312 | 0.097 | 70.3% | 44743 |
| SOL | bitstamp | w_m200_0 | 282081 | 0.457 | 0.209 | 78.5% | 68385 |
| SOL | bitstamp | w_m500_m200 | 282081 | 0.582 | 0.339 | 83.2% | 79901 |
| SOL | bitstamp | w_m900_m500 | 282081 | 0.573 | 0.328 | 80.8% | 73298 |
| SOL | bitstamp | w_p200_p500 | 282081 | 0.112 | 0.012 | 64.3% | 59712 |
| SOL | coinbase | prev1s | 281813 | 0.738 | 0.545 | 84.0% | 108865 |
| SOL | coinbase | w_0_p200 | 281813 | 0.131 | 0.017 | 69.4% | 93888 |
| SOL | coinbase | w_m1000_m900 | 281813 | 0.335 | 0.112 | 75.8% | 90966 |
| SOL | coinbase | w_m200_0 | 281813 | 0.284 | 0.080 | 73.9% | 94967 |
| SOL | coinbase | w_m500_m200 | 281813 | 0.507 | 0.257 | 78.7% | 97897 |
| SOL | coinbase | w_m900_m500 | 281813 | 0.587 | 0.344 | 80.5% | 99623 |
| SOL | coinbase | w_p200_p500 | 281813 | 0.087 | 0.008 | 65.5% | 95178 |
| SOL | kraken | prev1s | 282045 | 0.592 | 0.350 | 73.9% | 108631 |
| SOL | kraken | w_0_p200 | 282045 | 0.282 | 0.080 | 70.3% | 103173 |
| SOL | kraken | w_m1000_m900 | 282045 | 0.308 | 0.095 | 71.6% | 102081 |
| SOL | kraken | w_m200_0 | 282045 | 0.381 | 0.145 | 71.7% | 103395 |
| SOL | kraken | w_m500_m200 | 282045 | 0.494 | 0.244 | 73.0% | 104306 |
| SOL | kraken | w_m900_m500 | 282045 | 0.493 | 0.243 | 73.2% | 105302 |
| SOL | kraken | w_p200_p500 | 282045 | 0.242 | 0.059 | 68.3% | 103569 |
| SOL | median | w_0_p200 | 282082 | 0.231 | 0.054 | 76.2% | 79382 |
| SOL | median | w_m1000_m900 | 282082 | 0.394 | 0.155 | 80.4% | 71219 |
| SOL | median | w_m200_0 | 282082 | 0.421 | 0.177 | 81.6% | 82239 |
| SOL | median | w_m500_m200 | 282082 | 0.596 | 0.355 | 85.4% | 88894 |
| SOL | median | w_m900_m500 | 282082 | 0.617 | 0.380 | 84.8% | 87805 |
| SOL | median | w_p200_p500 | 282082 | 0.137 | 0.019 | 71.4% | 78424 |
| XRP | bitstamp | prev1s | 282084 | 0.807 | 0.651 | 78.6% | 220477 |
| XRP | bitstamp | w_0_p200 | 282084 | 0.136 | 0.018 | 58.4% | 170682 |
| XRP | bitstamp | w_m1000_m900 | 282084 | 0.365 | 0.133 | 62.5% | 135556 |
| XRP | bitstamp | w_m200_0 | 282084 | 0.364 | 0.132 | 64.9% | 174182 |
| XRP | bitstamp | w_m500_m200 | 282084 | 0.515 | 0.265 | 69.8% | 191117 |
| XRP | bitstamp | w_m900_m500 | 282084 | 0.579 | 0.336 | 69.8% | 190266 |
| XRP | bitstamp | w_p200_p500 | 282084 | 0.048 | 0.002 | 54.7% | 167783 |
| XRP | coinbase | prev1s | 281817 | 0.729 | 0.531 | 73.3% | 243711 |
| XRP | coinbase | w_0_p200 | 281817 | 0.078 | 0.006 | 59.4% | 220753 |
| XRP | coinbase | w_m1000_m900 | 281817 | 0.371 | 0.138 | 69.3% | 215660 |
| XRP | coinbase | w_m200_0 | 281817 | 0.242 | 0.058 | 63.4% | 220433 |
| XRP | coinbase | w_m500_m200 | 281817 | 0.471 | 0.222 | 68.3% | 225431 |
| XRP | coinbase | w_m900_m500 | 281817 | 0.606 | 0.367 | 71.6% | 229525 |
| XRP | coinbase | w_p200_p500 | 281817 | 0.055 | 0.003 | 56.6% | 224898 |
| XRP | kraken | prev1s | 281968 | 0.638 | 0.407 | 64.5% | 259260 |
| XRP | kraken | w_0_p200 | 281968 | 0.244 | 0.060 | 61.9% | 256688 |
| XRP | kraken | w_m1000_m900 | 281968 | 0.309 | 0.095 | 63.0% | 256181 |
| XRP | kraken | w_m200_0 | 281968 | 0.350 | 0.122 | 62.8% | 256562 |
| XRP | kraken | w_m500_m200 | 281968 | 0.508 | 0.258 | 63.6% | 257122 |
| XRP | kraken | w_m900_m500 | 281968 | 0.545 | 0.297 | 63.9% | 257624 |
| XRP | kraken | w_p200_p500 | 281968 | 0.250 | 0.062 | 60.7% | 257054 |
| XRP | median | w_0_p200 | 282074 | 0.171 | 0.029 | 63.3% | 202437 |
| XRP | median | w_m1000_m900 | 282074 | 0.446 | 0.199 | 71.5% | 185974 |
| XRP | median | w_m200_0 | 282074 | 0.373 | 0.139 | 68.1% | 203564 |
| XRP | median | w_m500_m200 | 282074 | 0.557 | 0.310 | 72.2% | 213275 |
| XRP | median | w_m900_m500 | 282074 | 0.642 | 0.412 | 74.0% | 215205 |
| XRP | median | w_p200_p500 | 282074 | 0.097 | 0.009 | 60.0% | 203616 |

### how stale the last quote was at the print's timestamp (share of seconds per bucket, ms) -- the feeds update only a few times a second
| coin | exchange | n | 0-50 | 50-100 | 100-250 | 250-500 | 500-1000 | >1000 |
|---|---|---|---|---|---|---|---|---|
| ADA | bitstamp | 282077 | 0% | 71% | 0% | 22% | 4% | 3% |
| ADA | coinbase | 281751 | 2% | 2% | 5% | 7% | 12% | 74% |
| ADA | kraken | 280016 | 0% | 0% | 1% | 2% | 4% | 92% |
| BCH | bitstamp | 282077 | 0% | 80% | 0% | 15% | 3% | 2% |
| BCH | coinbase | 281680 | 2% | 2% | 5% | 7% | 11% | 73% |
| BCH | kraken | 253652 | 0% | 0% | 1% | 2% | 3% | 93% |
| BTC | bitstamp | 282092 | 0% | 93% | 5% | 2% | 0% | 0% |
| BTC | coinbase | 281838 | 17% | 14% | 30% | 25% | 13% | 1% |
| BTC | gemini | 281991 | 23% | 9% | 15% | 13% | 14% | 26% |
| BTC | kraken | 282053 | 3% | 3% | 8% | 12% | 21% | 52% |
| DOGE | bitstamp | 282075 | 0% | 94% | 0% | 5% | 0% | 0% |
| DOGE | coinbase | 281667 | 2% | 2% | 4% | 6% | 11% | 75% |
| DOGE | kraken | 281383 | 1% | 1% | 2% | 3% | 6% | 87% |
| ETH | bitstamp | 282086 | 0% | 96% | 0% | 4% | 0% | 0% |
| ETH | coinbase | 281807 | 6% | 5% | 12% | 16% | 22% | 40% |
| ETH | kraken | 282048 | 2% | 2% | 5% | 8% | 15% | 68% |
| SOL | bitstamp | 282081 | 0% | 94% | 0% | 5% | 0% | 0% |
| SOL | coinbase | 281813 | 5% | 4% | 11% | 14% | 22% | 44% |
| SOL | kraken | 282045 | 2% | 1% | 4% | 7% | 14% | 72% |
| XRP | bitstamp | 282084 | 0% | 98% | 0% | 2% | 0% | 0% |
| XRP | coinbase | 281817 | 7% | 6% | 16% | 19% | 20% | 31% |
| XRP | kraken | 281968 | 2% | 1% | 4% | 7% | 12% | 74% |

### index 1-s move size (sd of the 1-s log change, bps, median over hours)
- ADA: 1.43 bps (n hours 81)
- BCH: 1.75 bps (n hours 81)
- BTC: 0.57 bps (n hours 81)
- DOGE: 1.53 bps (n hours 81)
- ETH: 0.70 bps (n hours 81)
- SOL: 0.94 bps (n hours 81)
- XRP: 1.10 bps (n hours 81)

## Q2 -- does BTC's index change predict each alt's index change, same second and next second?
| alt | same second: corr / hit / n | next second: corr / hit / n | 2 s later: corr / hit / n | reverse (alt now vs BTC next): corr | after a >=2 sd BTC second: same-sec hit (n) | next-sec hit (n) |
|---|---|---|---|---|---|---|
| ADA | 0.511 / 62.9% / 282309 | 0.173 / 54.0% / 282191 | 0.048 / 51.2% / 282073 | 0.028 | 91.1% (15727) | 62.9% (15572) |
| BCH | 0.206 / 57.6% / 282309 | 0.102 / 54.2% / 282191 | 0.042 / 51.8% / 282073 | 0.016 | 80.6% (15701) | 65.1% (15594) |
| BNB | 0.506 / 61.2% / 282308 | 0.165 / 54.2% / 282192 | 0.035 / 50.4% / 282074 | 0.032 | 89.4% (15762) | 61.5% (15644) |
| DOGE | 0.556 / 66.9% / 282309 | 0.063 / 51.9% / 282191 | 0.015 / 50.5% / 282073 | 0.040 | 95.1% (15733) | 53.0% (15238) |
| ETH | 0.721 / 69.7% / 282309 | 0.132 / 53.0% / 282191 | 0.008 / 49.9% / 282073 | 0.050 | 97.6% (15832) | 59.4% (15509) |
| HYPE | 0.373 / 58.6% / 282309 | 0.150 / 53.8% / 282191 | 0.049 / 51.4% / 282073 | 0.025 | 84.5% (15793) | 63.5% (15717) |
| NEAR | 0.182 / 56.7% / 282309 | 0.055 / 51.9% / 282191 | 0.022 / 50.6% / 282073 | 0.022 | 75.1% (14648) | 56.8% (14267) |
| SOL | 0.641 / 78.6% / 282309 | 0.126 / 56.3% / 282191 | 0.015 / 51.2% / 282073 | 0.052 | 98.5% (14278) | 64.8% (9615) |
| XRP | 0.546 / 65.7% / 282306 | 0.193 / 54.7% / 282188 | 0.032 / 50.7% / 282070 | 0.045 | 94.2% (15720) | 66.2% (15424) |
| ZEC | 0.264 / 57.3% / 282306 | 0.072 / 51.7% / 282188 | 0.021 / 50.5% / 282070 | 0.033 | 78.1% (15871) | 57.3% (15855) |
MDE: with 651 markets, base loss rate 2.6%, a rule flagging 10% of entries: power 49% to see a 3x loss rate in the flagged group (one-sided Fisher, p<0.05). Anything smaller than 3x is not detectable here.

## Q3 -- our live entries, constituent move AGAINST our side before the send (LOCAL clock)
entries settled: 651 markets; with a constituent feed for the coin: 376; without (BNB/NEAR/HYPE/ZEC): 275
losers (ledger P&L < 0): 17 of 651 markets, $-740.86; true flips (result != side): 13

### window m200 (median across the coin's exchanges; + = moved against us), feed coins only
| band | group | n mkts | $ | median move vs us (bps) | share >=1 sd | share >=2 sd | rank-sum p (losers more against) |
|---|---|---|---|---|---|---|---|
| tau<=20 | losers | 3 | $-48.87 | +0.00 | 0% | 0% | 0.558 |
| tau<=20 | winners | 87 | $+255.02 | +0.00 | 2% | 2% |  |
| tau 21-45 | losers | 5 | $-397.52 | +0.00 | 0% | 0% | 0.550 |
| tau 21-45 | winners | 281 | $+530.80 | -0.00 | 1% | 1% |  |
| tau>45 | losers | 0 | | | | | |
| tau>45 | winners | 0 | | | | | |

### window m500 (median across the coin's exchanges; + = moved against us), feed coins only
| band | group | n mkts | $ | median move vs us (bps) | share >=1 sd | share >=2 sd | rank-sum p (losers more against) |
|---|---|---|---|---|---|---|---|
| tau<=20 | losers | 3 | $-48.87 | +0.00 | 33% | 0% | 0.167 |
| tau<=20 | winners | 87 | $+255.02 | -0.00 | 2% | 2% |  |
| tau 21-45 | losers | 5 | $-397.52 | +0.00 | 0% | 0% | 0.773 |
| tau 21-45 | winners | 281 | $+530.80 | +0.00 | 5% | 2% |  |
| tau>45 | losers | 0 | | | | | |
| tau>45 | winners | 0 | | | | | |

### window m900 (median across the coin's exchanges; + = moved against us), feed coins only
| band | group | n mkts | $ | median move vs us (bps) | share >=1 sd | share >=2 sd | rank-sum p (losers more against) |
|---|---|---|---|---|---|---|---|
| tau<=20 | losers | 3 | $-48.87 | +0.00 | 33% | 33% | 0.131 |
| tau<=20 | winners | 87 | $+255.02 | +0.00 | 2% | 2% |  |
| tau 21-45 | losers | 5 | $-397.52 | +0.00 | 25% | 0% | 0.465 |
| tau 21-45 | winners | 281 | $+530.80 | -0.00 | 6% | 3% |  |
| tau>45 | losers | 0 | | | | | |
| tau>45 | winners | 0 | | | | | |

### window since_print (median across the coin's exchanges; + = moved against us), feed coins only
| band | group | n mkts | $ | median move vs us (bps) | share >=1 sd | share >=2 sd | rank-sum p (losers more against) |
|---|---|---|---|---|---|---|---|
| tau<=20 | losers | 3 | $-48.87 | +0.00 | 33% | 33% | 0.178 |
| tau<=20 | winners | 87 | $+255.02 | -0.00 | 2% | 2% |  |
| tau 21-45 | losers | 5 | $-397.52 | +0.00 | 0% | 0% | 0.813 |
| tau 21-45 | winners | 281 | $+530.80 | -0.00 | 5% | 2% |  |
| tau>45 | losers | 0 | | | | | |
| tau>45 | winners | 0 | | | | | |

### window m3000 (median across the coin's exchanges; + = moved against us), feed coins only
| band | group | n mkts | $ | median move vs us (bps) | share >=1 sd | share >=2 sd | rank-sum p (losers more against) |
|---|---|---|---|---|---|---|---|
| tau<=20 | losers | 3 | $-48.87 | +0.00 | 33% | 33% | 0.092 |
| tau<=20 | winners | 87 | $+255.02 | -0.00 | 4% | 2% |  |
| tau 21-45 | losers | 5 | $-397.52 | +0.00 | 25% | 25% | 0.352 |
| tau 21-45 | winners | 281 | $+530.80 | -0.00 | 11% | 5% |  |
| tau>45 | losers | 0 | | | | | |
| tau>45 | winners | 0 | | | | | |

### Rule grid: refuse the FIRST entry when the constituent move against us over the window >= X x (coin's trailing 300-s 1-s index sd). Ledger dollars of the markets it would have refused.
| window | X | flagged n | flagged losers | flagged $ losers | flagged winners | flagged $ winners | unflagged losers/n | one-sided Fisher p | loser days |
|---|---|---|---|---|---|---|---|---|---|
| m200 | 1 | 4 | 0 | $+0.00 | 4 | $+10.80 | 7/363 | 1.0000 |  |
| m200 | 2 | 4 | 0 | $+0.00 | 4 | $+10.80 | 7/363 | 1.0000 |  |
| m200 | 3 | 2 | 0 | $+0.00 | 2 | $+7.76 | 7/365 | 1.0000 |  |
| m500 | 1 | 16 | 1 | $-34.26 | 15 | $+36.77 | 6/351 | 0.2700 | 09-14 |
| m500 | 2 | 7 | 0 | $+0.00 | 7 | $+16.86 | 7/360 | 1.0000 |  |
| m500 | 3 | 3 | 0 | $+0.00 | 3 | $+8.93 | 7/364 | 1.0000 |  |
| m900 | 1 | 20 | 2 | $-99.20 | 18 | $+39.23 | 5/347 | 0.0503 | 09-14,09-20 |
| m900 | 2 | 12 | 1 | $-34.26 | 11 | $+28.39 | 6/355 | 0.2092 | 09-14 |
| m900 | 3 | 7 | 1 | $-34.26 | 6 | $+16.95 | 6/360 | 0.1271 | 09-14 |
| since_print | 1 | 16 | 1 | $-34.26 | 15 | $+29.13 | 6/351 | 0.2700 | 09-14 |
| since_print | 2 | 9 | 1 | $-34.26 | 8 | $+19.14 | 6/358 | 0.1608 | 09-14 |
| since_print | 3 | 5 | 1 | $-34.26 | 4 | $+13.21 | 6/362 | 0.0923 | 09-14 |
| m3000 | 1 | 34 | 2 | $-99.20 | 32 | $+58.67 | 5/333 | 0.1303 | 09-14,09-20 |
| m3000 | 2 | 19 | 2 | $-99.20 | 17 | $+40.24 | 5/348 | 0.0457 | 09-14,09-20 |
| m3000 | 3 | 9 | 2 | $-99.20 | 7 | $+20.96 | 5/358 | 0.0106 | 09-14,09-20 |

15 cells looked at; Bonferroni bar for one look at p<0.05 is p<0.0033.

### For comparison: the INDEX itself (no new feed). Same flag shape, max over the 1-3 s before the print second, X = 2 sd.
| ruler | population | flagged n | flagged losers | flagged $ | unflagged losers/n | Fisher p |
|---|---|---|---|---|---|---|
| BTC index (alts only) | 528 | 19 | 4 | $-209.86 | 8/509 | 0.0005 |
| BTC index incl. entry second (alts) | 528 | 27 | 4 | $-177.10 | 8/501 | 0.0020 |
| coin's own index | 624 | 16 | 1 | $-9.01 | 15/608 | 0.3434 |
| coin's own index, entry second only | 624 | 7 | 1 | $-59.40 | 15/617 | 0.1670 |

### Feed coverage at our entries (local clock): quote updates in the 900 ms before the send, per exchange
- bitstamp: 376 entries, updates in last 900 ms median 4, share with zero updates 1%
- coinbase: 376 entries, updates in last 900 ms median 1, share with zero updates 44%
- gemini: 99 entries, updates in last 900 ms median 3, share with zero updates 34%
- kraken: 375 entries, updates in last 900 ms median 0, share with zero updates 74%

### Every loser with a feed, one line each (window m900 / since_print in bps, + = against us; z = in sd units)
- 2026-09-24 KXBTC15M-26SEP232030-30 tau=26 age=0.18s $-130.41 flip=True | m900 -1.6 bps (z na) | since_print -0.0 bps | z_btc(1-3s) na | z_own(1-3s) na
- 2026-09-19 KXBTC15M-26SEP191600-00 tau=45 age=0.67s $-107.95 flip=True | m900 +0.0 bps (z +0.0) | since_print +0.0 bps | z_btc(1-3s) na | z_own(1-3s) +0.1
- 2026-09-19 KXBTC15M-26SEP190200-00 tau=35 age=0.11s $-66.34 flip=True | m900 +0.0 bps (z +0.0) | since_print +0.0 bps | z_btc(1-3s) na | z_own(1-3s) +0.4
- 2026-09-20 KXXRP15M-26SEP192345-45 tau=41 age=0.52s $-64.95 flip=False | m900 +0.9 bps (z +1.1) | since_print +0.0 bps | z_btc(1-3s) +3.6 | z_own(1-3s) +0.8
- 2026-09-14 KXBTC15M-26SEP140530-30 tau=13 age=0.93s $-34.26 flip=True | m900 +2.5 bps (z +4.8) | since_print +2.4 bps | z_btc(1-3s) na | z_own(1-3s) +4.6
- 2026-09-18 KXBTC15M-26SEP172115-15 tau=38 age=0.14s $-27.87 flip=True | m900 -0.0 bps (z -0.0) | since_print -0.0 bps | z_btc(1-3s) na | z_own(1-3s) -0.0
- 2026-09-16 KXDOGE15M-26SEP160900-00 tau=17 age=0.18s $-12.14 flip=False | m900 +0.0 bps (z +0.0) | since_print +0.0 bps | z_btc(1-3s) +0.6 | z_own(1-3s) +0.1
- 2026-09-23 KXDOGE15M-26SEP222245-45 tau=12 age=0.52s $-2.47 flip=True | m900 +0.0 bps (z +0.0) | since_print +0.0 bps | z_btc(1-3s) +1.8 | z_own(1-3s) +1.0
