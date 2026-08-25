# Kalshi 15-Minute Crypto — Plan v2 (post-recon)

`VERSION: 2026-08-25-v2`

Supersedes v1. Recon ran 2026-08-25T00:32Z. Facts below are **confirmed from
Kalshi's own API** unless marked otherwise.

---

## 1. What recon settled

**Settlement mechanics — CONFIRMED, exactly as hypothesised.** From
`rules_primary` on a settled market:

> "If the simple average of the sixty seconds of CF Benchmarks' BRTI before
> 7:45 PM EDT is at least the simple average of the sixty seconds of CF
> Benchmarks' BRTI before 7:30 PM EDT, then the market resolves Yes."

So the strike **is** the opening 60-second TWAP, and settlement is the closing
60-second TWAP. Corroborated by `floor_strike: 78788.19` — an observed index
value to the cent, not a round band, with `custom_strike: {round_digits: "2"}`.

**Correction to v1.** I had the variance at `820σ²`. That was wrong. The strike
window *ends* at market open, so the two averaging windows are 840s apart, not
780s:

```
[0,60] strike TWAP → open → 900s trading → [900,960] settle TWAP → close
Var(settle − strike) = 20 + 920 − 2(30) = 880σ²
```

Effective horizon 880s, not 820s. Everything downstream is recalibrated.

**Volatility — calibrated and independently sanity-checked.** 997 settled
windows: sd of (settle − strike) = $135.78 at BTC ≈ $60,882 → 0.2230% per
window → **42.2% annualized**. That is a completely plausible BTC vol, arrived
at through a chain that never touched an external volatility source. The model
is internally consistent. At today's ~$78,788 that's **$175.7 per window**,
σ = $5.92/√s.

**The two apparent "signals" are noise. Do not build on them.**
- Mean drift −$3.99, SE $4.30 → **t = −0.93**
- Up-rate 48.04%, SE 1.58pp → **t = −1.24**

Both well inside noise. The −$3.99 is just BTC drifting down over the ~10 days
those windows span — one realized path, not an edge.

**Fees — partially answered.** Every series returns
`fee_type: "quadratic", fee_multiplier: 1`. That confirms taker =
`0.07 × P × (1−P)` at the standard, un-halved rate. **It does not answer the
maker question** — there is no maker field on the series record. Still open.

**Tick grid — CONFIRMED `tapered_deci_cent`**, and this is the important find:

| Band | Tick |
|---|---|
| $0.00–$0.10 | **0.1¢** |
| $0.10–$0.90 | 1.0¢ |
| $0.90–$1.00 | **0.1¢** |

**14 series, not 7.** BTC, ETH, SOL, XRP, DOGE, BNB, ADA, BCH, ZEC, HYPE,
NEAR, TON as up/down. Plus `KXCRYPTOLEAD15M` (coin race) and
`KXCRYPTOCOMP15M` (comparison), which use different contract terms
(`CRYPTORETURN15M.pdf`). Those are relative-performance contracts and **do not
decompose into the single-asset markets** — P(BTC return > ETH return) is not
any combination of two own-strike binaries. Not an arb. Excluded from scope.

**API gotcha found.** REST `/orderbook?depth=N` returns levels **ascending**
and truncates from the bottom, so top-of-book was hidden in the recon output
(it showed yes bids 0.30–0.39 while the market object said best bid 0.40). The
collector uses the WebSocket book stream, which is unaffected — but any REST
book code must not assume index 0 is best.

---

## 2. The finding that redirects the project

Because the strike is the opening TWAP, **every window opens at exactly 50¢
fair value by construction**. There is no directional view to have at open. The
entire information content of the contract is the drift away from strike during
the window — and residual uncertainty collapses as `(60−s)^1.5` once the
settlement averaging begins.

Combine that with the tick grid and the fee curve and the geography is stark:

| Time to close | Residual σ | P(outside 10–90¢) | P(outside 1–99¢) |
|---|---|---|---|
| 300s | $95.51 | 39.9% | 12.6% |
| 120s | $52.98 | 68.1% | 45.6% |
| 60s | $26.49 | **84.3%** | 72.0% |
| 30s | $9.37 | 94.5% | 90.1% |

By the time averaging starts, **84% of windows have already left the 10–90¢
band** — into the region where ticks are 10× finer and fees up to 5× lower:

| Price | Fee | Tick | Fee + ½ spread = breakeven edge |
|---|---|---|---|
| 50¢ | 1.750¢ | 1.0¢ | **2.25 pp** |
| 90¢ | 0.630¢ | 1.0¢ | 1.13 pp |
| 95¢ | 0.333¢ | **0.1¢** | **0.38 pp** |
| 98¢ | 0.137¢ | **0.1¢** | **0.19 pp** |

The cost of trading at 95¢ is **one sixth** the cost at 50¢. The 90–99¢ band in
the last two minutes is the only region of this market where a small edge could
survive costs. Everything else is a fee trap.

Where v1 aimed at the whole surface, **v2 aims at one cell of it.**

---

## 3. The experiment, quantified

If a quoter decays uncertainty on `√(time-to-close)` off spot rather than
modelling the TWAP, here is the disagreement at a true 94.5¢ contract:

| ttc | true | naive quote | gross edge | cost | net |
|---|---|---|---|---|---|
| 180s | 94.5¢ | 92.6¢ | 2.0¢ | 0.53¢ | +1.4¢ |
| 120s | 94.5¢ | 90.9¢ | 3.6¢ | 0.63¢ | +3.0¢ |
| 60s | 94.5¢ | 82.8¢ | 11.8¢ | 1.05¢ | +10.7¢ |
| 30s | 94.5¢ | 68.2¢ | 26.3¢ | 1.57¢ | +24.8¢ |
| 15s | 94.5¢ | 59.3¢ | 35.2¢ | 1.74¢ | +33.4¢ |

**Read this as a hypothesis test, not a forecast.** Those are the numbers *if*
the book is naive. My prior is that it is not. The recon book — 1¢ spread (the
minimum tick in that band), ~3,767 contracts resting at the bid, 14 series
quoted continuously 24/7 — is what a professionally made market looks like.
Someone is running real infrastructure here.

The experiment is genuinely two-sided, and the null is the likely outcome:

- **H1:** the book decays on √t → large exploitable edge in the last 2 minutes.
- **H0:** the book prices the TWAP correctly → edge ≈ 0, project dies.

The measurement costs nothing and resolves in a week.

---

## 4. The queue problem — a new negative finding

Observed: best bid 0.40 with **3,767 contracts** resting, spread already at the
1¢ minimum. Joining that queue puts you behind ~3,767 contracts. You fill only
when the market trades *through* your level — which is exactly the moment you
are adversely selected.

This substantially weakens the passive/maker plan from v1 **even if maker fees
turn out to be zero**. Free entry is worth nothing at a 4% fill rate on the
trades you'd least like to win.

Consequence: **model the taker path as primary.** Treat any maker advantage as
an upside case that must be proven with measured queue data, not assumed. Kill
criterion 5 (fill rate < 20%) is now the *expected* outcome rather than a
remote risk.

---

## 5. Statistical power — corrected

**v2 first draft was wrong here and this supersedes it.** I claimed 8,064
independent windows/week resolving a 0.5¢ edge. Two errors:

1. Samples *within* a window share one Bernoulli outcome, so 180 samples per
   window do not give √180 noise reduction. Independence lives at the window
   level.
2. The 12 crypto series close simultaneously and are ~0.8 correlated. At
   ρ = 0.8, twelve series give **1.22 effective independent units**, not 12.

So the real unit is the **close-time cluster**: 96/day, 672/week. The analyzer
now clusters on close-time, not ticker. Ticker clustering would have inflated
t-stats roughly 10×.

Corrected detection thresholds (at p ≈ 0.95, t = 2):

| Edge | Clusters needed | Days |
|---|---|---|
| 0.5¢ | 30,400 | 317 |
| 1.0¢ | 7,600 | 79 |
| 2.0¢ | 1,900 | 20 |
| 3.6¢ | 586 | **6** |
| 11.8¢ | 55 | **1** |

**A week still works for the test that matters.** If H1 (naive quoter) is
true, §3 says the edge is 3.6–36¢, detectable in 1–6 days. If the edge is only
~1¢, it needs 79 days *and* barely clears the 0.38pp cost bar — not worth
chasing. So read a one-week null as "no large mispricing exists," which is
exactly the decision we need.

Where 12 series *does* buy real power: **cross-sectional** comparison. Asking
"is ZEC mispriced relative to BTC?" differences out the common crypto move,
so correlation helps rather than hurts. The analyzer buckets by series for
this reason.

## 6. Revised sizing — what it's worth if H1 survives

~470 candidate windows/day sit in the 90–99¢ band during the last 30–120s.
Trading 10% of them:

| Edge | 50 contracts | 200 contracts |
|---|---|---|
| 0.5¢ | $12/day | $47/day |
| 1.0¢ | $24/day | $94/day |
| 2.0¢ | $47/day | $188/day |

At 200 contracts you are risking ~$190 per trade at 95¢ to win ~$10. That is
picking up pennies in front of a steamroller: you lose the full stake 5% of the
time, and those losses cluster on exactly the windows where the underlying
moved hard. Any live sizing must be Kelly-fractional off a **measured** edge,
never a modelled one.

---

## 7. Next actions, in order

1. **Answer the maker-fee question empirically.** Rest 1 contract on a live
   KXBTC15M market far from the touch, let it fill, read `fees_paid` on the
   fill. Costs under a dollar and is the only unambiguous answer. Do it on the
   website — no code needed.
2. **Start `kalshi_collector.py`** on the 24/7 box. It needs an API key (RSA
   PEM) because the WebSocket authenticates even for public channels. Run with
   `--verbose` for the first hour and watch for rejected channel names —
   `cfbenchmarks_value` is the one that must work.
3. **Save the settled-market pull** to `settled.json`, and re-pull daily so it
   stays aligned with the recording window.
4. **After 48 hours**, run `kalshi_analyze.py` for GATE 1 only. If the
   reconstructed TWAP doesn't match `expiration_value` to the cent, stop and
   fix the understanding before collecting another day.
5. **After 7 days**, run the full gates.

---

## 8. Kill criteria — unchanged, now sharper

1. Reconstructed settlement TWAP ≠ `expiration_value`. Stop.
2. No bucket where the model beats the mid at t > 2 with ≥1,000 windows.
3. Edge exists only inside the final ~15s → latency race, unwinnable from home.
4. Edge < fee + half-spread in every bucket with tradeable depth. **Note the
   bar is now 0.38pp at 95¢, not 2.25pp at 50¢** — this criterion got
   materially easier to clear, and it's the one genuinely encouraging
   development from recon.
5. Passive fill rate < 20% → maker path dead (now the expected outcome).
6. Eight weeks, no measured edge. Stop.

---

## 9. Still open

- Maker fee on KXBTC15M. *(Action 1.)*
- Exact `cfbenchmarks` passthrough path and history granularity.
- Does the book price `(60−s)^1.5` or `√(60−s)`? **The core experiment.**
- Realized queue position and fill rate at top of book.
- Whether the thinner series (ZEC, HYPE, NEAR, TON) are less efficiently made
  than BTC. Wider spreads there could mean worse costs *or* a lazier quoter —
  the analyzer buckets by series, so this comes out for free.
- Tax treatment: event contracts are not clearly Section 1256, and this
  generates a very high trade count. Confirm before scaling volume.

---

## 10. Additions after review (v2.1)

Three gaps found on a second pass. Two were unrecoverable if left another 48h.

**10.1 We were only recording what Kalshi shows us.** BRTI is computed from the
**order books of constituent exchanges**, once per second, and CME's own white
paper calls the methodology reproducible and replicable. Those exchanges
(Coinbase, Kraken, Bitstamp, Gemini) publish free, public, unauthenticated
WebSocket feeds. So the inputs to our settlement index are streamable directly.

This weakens the "latency race we lose from home" conclusion in §3. We are not
restricted to Kalshi's relayed value — we can compute a BRTI replica in
parallel with CF and measure whether it leads Kalshi's `cfbenchmarks_value`.
Because settlement is a 60-second average, we don't need microsecond speed; we
need an earlier read on where the running average is heading. `crypto_feeds.py`
records this. **Exchange feeds have no backfill — every hour not recorded is
gone permanently.**

Also added `pyth_value` to the collector: a second independent oracle, free to
record, potentially a leading indicator.

**10.2 We were going to wait 48 hours to learn anything, unnecessarily.**
`/historical/trades` returns executed prints with timestamps; joined to settled
outcomes, that is a direct calibration study on real money already traded.
`kalshi_backfill.py` runs it today. If trades at 95¢ settled Yes 95% of the
time, the market is efficient and we know within an afternoon.

**10.3 The Gaussian assumption may invert the §2 conclusion.** v2 says
concentrate in the 90–99¢ band because ticks and fees are cheapest there. That
rests on a Gaussian distribution for (settle − strike). Crypto is fat-tailed.
Excess kurtosis means extreme moves happen more often than Gaussian predicts —
so a 95¢ contract (a bet the move stays small) loses more often than the model
says, and the Gaussian model **systematically overvalues exactly what v2 told
us to buy**. `kalshi_backfill.py` section C tests this directly. If the tail
ratio exceeds ~1.15 at the 95¢ threshold, the model must be refit with a
Student-t before any tail strategy is considered.

**10.4 Nothing was protecting the run.** The collector reconnects its
WebSocket, but a dead Python process stops everything silently. `run_all.ps1`
restarts both recorders and watches disk.
