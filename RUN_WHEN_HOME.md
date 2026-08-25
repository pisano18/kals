# Run these when you're home

Everything here is read-only. Nothing places an order.
Paste the output back, or just send `RESULTS.md`.

---

## 1. The main run — one command, does almost everything

```powershell
cd C:\kals-repo
git pull
python research\go.py --data C:\kals\kalshi_data --out C:\kals\fulltape --feeds C:\kals\feed_data
```

Takes ~6 minutes of self-tests, then the stages. Writes `C:\kals-repo\RESULTS.md`.
**Send me that file.** If a self-test fails it stops and prints why on screen.

The single most important line in the output is from the `doctor` stage:
whether `cfbenchmarks_value` is delivering, per index, at what rate. Every
model-based test depends on it.

---

## 2. The ten-second one that might matter most

Your `PLAN.md` says S&P/Nasdaq series carry a **0.035** fee multiplier — half
crypto's 0.07 — but "have no short-cadence markets". If that's changed, the
cost bar halves and the set of edges that clear it roughly doubles. That is
worth more than any modelling improvement I could make.

```powershell
curl.exe -s "https://api.elections.kalshi.com/trade-api/v2/series?category=Financials" > series_fin.json
curl.exe -s "https://api.elections.kalshi.com/trade-api/v2/series?category=Crypto" > series_crypto.json
```

Send me both files. I want `fee_multiplier`, `ticker`, and anything with a
short cadence in the ticker name (15M, 30M, 1H).

---

## 3. If `replay` / `leadlag` report zero quotes parsed

```powershell
python research\doctor.py --data C:\kals\kalshi_data --feeds C:\kals\feed_data
python research\replay.py --dump-ticker --data C:\kals\kalshi_data
```

`doctor` writes `schema.json` which the loaders read, so this usually fixes
itself. If not, the dump shows me the raw message shape.

---

## 4. Refresh the settled-market outcomes

Several stages need `fulltape/markets.json` to be current — it maps tickers to
strike and result. If it's stale, markets recorded overnight won't have outcomes:

```powershell
cd C:\kals
python kalshi_fulltape.py --data .\kalshi_data --out .\fulltape --markets 400
```

---

## 5. The maker-fee question, if you feel like it

`PLAN.md` §9 action 1. Secondary sources say maker = 25% of taker (0.0175 vs
0.07), but not confirmed from Kalshi's own schedule and it's unclear whether
the 15-minute crypto series is even maker-fee eligible. Resting one contract
far from the touch and reading `fees_paid` on the fill answers it for under a
dollar. Only worth doing if you're curious — it doesn't gate anything.

---

## Housekeeping

- **Disk**: measured growth is **4.57 GB/day** (1.38 kalshi + 3.19 feeds). At
  49 GB free and a watchdog that halts below 5 GB, that's **~10 days**. When it
  gets close, the feeds directory is the one to prune — but see below.
- **`feed_data` is irreplaceable.** Exchange websockets have no backfill. Every
  hour not recorded is gone permanently. If you have to free space, delete from
  `kalshi_data` first (Kalshi's REST history can rebuild most of it) and only
  compress, never delete, `feed_data`.
- **Leave the watchdog window running.**
