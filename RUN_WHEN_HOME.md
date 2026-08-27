# Run this when you're home

```powershell
cd C:\kals-repo
git pull
python research\everything.py
```

That is the whole thing. No arguments, no paths, no placeholders. It finds the
repo, finds your data under `C:\kals`, works out how much of it there is, and
runs every job below in the right order.

When it finishes it prints one line:

```
    SEND ME THIS ONE FILE:  C:\kals-repo\kals-report-YYYYMMDD-HHMM.zip
```

Send that. It contains the report, `RESULTS.md`, the schema the loaders
detected, and the four API responses.

**Expect 30–60 minutes.** Progress prints as it goes with elapsed time, so you
can tell it apart from a hang. Everything is read-only: it never places an
order, never writes to `kalshi_data/` or `feed_data/`, and never kills your
recorder.

## One thing worth doing once, at the machine

The watchdog does `Set-Location C:\kals` and launches `python
crypto_feeds.py` — so it runs the copies of the collectors sitting **next to
your data**, not the ones in `C:\kals-repo`. A `git pull` updates the repo and
changes nothing about what is actually recording.

Step `0c` of the run now checks that and tells you if they have drifted. To
fix it:

```powershell
python research\everything.py --only sync --sync-collectors
```

Each file is backed up to `.bak`, and is copied only after it passes its own
self-test (or, where it has none, a compile check). Then **restart the
watchdog** — the running processes still hold the old code until they do.

There is currently one collector change waiting: Bitstamp's order book is
trimmed from 100 levels a side to 5 before it is written, which is 95.9% off
those records and ~89% off `feed_data`'s growth rate. Nothing reads levels
2–100. Data already on disk keeps its full depth.

---

If it dies partway, run it again — or `--skip go` to leave out the long stage,
`--only api` to run one piece. The report is rewritten after every step, so
even an interrupted run leaves something worth sending.

### The one thing it deliberately does NOT do

It adds the two comparison series to `run_all.ps1` but **does not restart your
watchdog**. Stopping your recorder unattended is not a risk worth taking. It
prints the restart command; do it when you're at the keyboard:

```
Ctrl+C in the watchdog window, then
powershell -ExecutionPolicy Bypass -File C:\kals\run_all.ps1
```

Until you do, `KXCRYPTOLEAD15M` and `KXCRYPTOCOMP15M` are still not being
recorded, and that is the one thing here where waiting costs something
permanent.

---

# What it runs, and why

Everything below happens automatically. It is written out so you can run any
piece by hand if you want to, and so you know what the report is telling you.

## 0. Read this first, before anything in RESULTS.md

```powershell
cd C:\kals-repo
python research\power.py --data C:\kals\kalshi_data
```

(It counts the hours and the settled history itself. Do not paste anything
with `<angle brackets>` into PowerShell — it reads them as redirection and
drops to a `>>` continuation prompt. Ctrl+C if that happens.)

New file. It answers the question that makes every other number readable:
**with the data that exists, what could we have detected at all?** A t of 1.4
means "there is no edge" or "there is an edge and we cannot see it", and until
now nothing here could tell those apart.

Two things it will tell you that matter more than any single stage:

- The independent unit is the **close time**, not the market. Twelve series
  closing simultaneously at 80% correlation are worth 1.22 independent bets,
  so a day of recording is 96 observations, not 1,152. Every "n = 4,300
  markets" in an earlier report was overstating the sample by roughly twelve
  times.
- One `go.py` run emits **several hundred** t-statistics. At the usual 0.05
  that is a dozen or more expected to fire on noise alone. The corrected
  threshold is printed; it is a long way above 3.

It runs a few minutes of simulation before it prints anything — that is the
self-test planting an effect of exactly the size it claims to detect and
checking that it fires four times in five. Let it finish.

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
curl.exe -s -o series_fin.json "https://api.elections.kalshi.com/trade-api/v2/series?category=Financials"
curl.exe -s -o series_crypto.json "https://api.elections.kalshi.com/trade-api/v2/series?category=Crypto"
```

(`-o` rather than `>`: PowerShell 5.1's `>` is Out-File, which writes
UTF-16LE with a BOM that `json.load` cannot read. `everything.py` does
these four probes itself with urllib and writes the bytes verbatim, so
you only need these if you are running the steps by hand.)

Send me both files. I want `fee_multiplier`, `ticker`, and anything with a
short cadence in the ticker name (15M, 30M, 1H).

---

## 3. Start recording the comparison markets (do this first — it's collection)

`kalshi_collector.py` deliberately excludes `KXCRYPTOLEAD15M` and
`KXCRYPTOCOMP15M`. PLAN dismissed them as "not decomposable into the
single-asset binaries, therefore not an arb" — true, and the wrong conclusion.

Those contracts price **relative** performance, so their price depends on the
CORRELATION between two coins:

```
P(A beats B) = Phi( (d_A - d_B) / sd )
sd^2 = 880 * (sigma_A^2 + sigma_B^2 - 2 * rho * sigma_A * sigma_B)
```

The numerator is computable from the index feeds we already record. So inverting
their price gives **implied correlation** — and realized correlation is directly
measurable from the same feeds. Implied correlation persistently exceeding
realized is one of the most durable risk premia in finance; the whole dispersion
trading business exists because of it. Nobody has to be wrong for it to pay.

Right now we record none of it. Two things:

**(a) Add them to the collector.** Stop the watchdog, edit `run_all.ps1`, add
`--series` with the full list plus the two comparison series, restart:

```
kalshi_collector.py --key-id $KeyId --key-file $KeyFile --out ./kalshi_data --series KXBTC15M KXETH15M KXSOL15M KXXRP15M KXDOGE15M KXBNB15M KXADA15M KXBCH15M KXZEC15M KXHYPE15M KXNEAR15M KXTON15M KXCRYPTOLEAD15M KXCRYPTOCOMP15M
```

Disk cost is small — two more series against fourteen.

**(b) Send me the exact contract terms**, so I build against the real spec
rather than my reconstruction of it:

```powershell
curl.exe -s -o comp.json "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXCRYPTOCOMP15M&status=settled&limit=2"
curl.exe -s -o lead.json "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXCRYPTOLEAD15M&status=settled&limit=2"
```

I want `rules_primary`, `floor_strike`, `expiration_value` and the ticker
format. I will not write the correlation model until I have seen them — the
formula above is my reconstruction, not confirmed.

---

## 4. If `replay` / `leadlag` report zero quotes parsed

```powershell
python research\doctor.py --data C:\kals\kalshi_data --feeds C:\kals\feed_data
python research\replay.py --dump-ticker --data C:\kals\kalshi_data
```

`doctor` writes `schema.json` which the loaders read, so this usually fixes
itself. If not, the dump shows me the raw message shape.

---

## 5. Refresh the settled-market outcomes

Several stages need `fulltape/markets.json` to be current — it maps tickers to
strike and result. If it's stale, markets recorded overnight won't have outcomes:

```powershell
cd C:\kals
python kalshi_fulltape.py --data .\kalshi_data --out .\fulltape --markets 400
```

---

## 6. The maker-fee question, if you feel like it

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

---

## Restarting the watchdog: do it near the top of an hour

The collector opens one gzip file per UTC hour and appends to it. On Windows it
cannot write a gzip trailer on shutdown, so a restart *inside* an hour leaves
that hour's file with two gzip members and no trailer on the first — and the
standard reader then throws the whole file away. Measured on a faithful
reproduction: **0 of 10 records recovered.**

`research/gzsalvage.py` now reads those files member by member and recovers
them, and every loader here goes through it, so this is no longer data loss.
But the fix for *new* files only takes effect after the collector restarts with
the current code, and restarting a minute past the hour still costs you the
tidiest version of that hour. Restart just after `:00` when you can.

`everything.py` reports, in its preflight, exactly how many of your recorded
files are affected and how many messages salvage recovers.
