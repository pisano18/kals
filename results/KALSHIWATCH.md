# Kalshi change watcher (`research/kalshiwatch.py`)

Built Sep 25, 2026, 3:30-4:00 AM ET. **It is not running.** Two real snapshots were taken and it stopped. The start command is below.

## What it is for

Kalshi sometimes changes things without warning: a field gets renamed, a fee moves, the price steps change, a rule gets a new sentence. Once, a field rename left every one of 68,976,084 order-book updates unreadable, and nothing noticed, because every program still ran without an error. This watcher checks for that kind of change once an hour. It **only reads**. It never places, changes or cancels an order. Every Kalshi call it makes is a read-only GET, and its self-test fails if the file ever builds any other kind of request.

## What it checks every hour

1. **The shape of every answer the bot depends on.** It records each field name and what kind of value it holds, for the 42 read-only calls the live bots and the ledger make: the market list for all 13 series we trade, one market, the order book, the balance, one order record, fills, settlements, the series and the event. Shapes are stored per series, so a series with no open market that hour counts as "not seen", never as "field removed".
2. **The money settings of every series:** fee type and multiplier, how many seconds after the close the result is fixed, the price steps, the strike rule, where the settlement price comes from, and the rules text. In the rules text, times, dates and strike prices are blanked out, so a new market is not a change but a new sentence is.
3. **Changes Kalshi has already scheduled:** its list of upcoming series and event fee changes, and its maintenance windows. These are the earliest warning there is.
4. **Public pages:** Kalshi's API changelog (all 329 entries, including dated future ones), the fee schedule PDF, and the docs pages for the 22 endpoints and live-feed channels we use.
5. **The recorder's own tape.** It reads without writing, one finished hour file at a time. It records the shape of our markets' live-feed messages and every fee override Kalshi broadcasts on our series.

## How loud each change is

- **ALERT** (worth waking up for):
  - a field whose name appears in the bot's code disappears or changes type;
  - fee, settle-timer, price-step, strike-rule or settlement-source change;
  - new rules sentence;
  - a fee change scheduled on one of our series;
  - a changelog entry that names a field our bot uses;
  - the fee schedule PDF changes;
  - an endpoint the bot calls answers "not found";
  - maintenance gets scheduled.
- **WARN:**
  - a new field;
  - a field the bot does not read is missing two hours running;
  - a docs page gets edited;
  - a page stays unreadable for a day.
- **INFO:** a changelog entry that touches nothing we use.

A failed fetch is never counted as a change: the old value is kept.

## What the first real snapshot captured (Sep 25, 3:47 AM ET)

- All 42 Kalshi reads worked. They cover 50 answers and feed channels and about 1,430 field names.
- **All 13 series charge the normal fee (quadratic, multiplier 1).** Scheduled fee changes on our series: **0**. Maintenance windows: **0**.
- The 15-minute up/down markets settle 1 second after the close and use 0.1-cent price steps under 10c and over 90c. Coin Race settles 1 second after the close and uses 1-cent steps. The hourly BTC ladder settles 60 seconds after the close and uses 1-cent steps. KXADA15M and KXBCH15M had no open market, which is already known.
- The fee tape has 157 hour files from Aug 25 to Sep 25 holding 6,748 fee overrides. **Every one was a baseball market. None was ours.**
- All 24 public pages were read. The first try at the fee PDF was refused with "too many requests". It read normally once the request identified itself as a normal browser.
- **Kalshi has announced five changes dated Oct 1.** The only one on the markets we trade removes the `liquidity_dollars` field from market answers. **Our bot never reads that field.** I checked all four live files and found 0 uses. None of the other four touches us: two are FIX-only, one is for margin, and one is an RFQ filter.

## How far to trust it (measured)

- **Quiet when nothing changes:**
  - two real snapshots 34 seconds apart raised 0 alerts;
  - a third, 8 minutes later, also raised 0;
  - the feed half, checked against 8 different real hours from 2 to 50 hours back, raised 0.
- **One problem was found and fixed during that check.** The first version raised 30 false warnings over those 8 hours. They came from sports-market messages whose extra fields change from sport to sport. The watcher now reads feed messages for our series only, and the same check then gave 0.
- **It has only been shown to catch planted changes, not a real one.** Its self-test plants 12 kinds of change and all are caught, each announced once and not repeated every hour. It also plants 6 harmless ones: a new market, a series with no market, an empty book side, a blocked page, a docs edit that only bumps the version number, and a margin-only changelog entry. None of those fire. Replaying 16 hours spread over the whole month of tape found no real removed or retyped field in our markets' feed. The one real addition it found was a strike field added to "market created" messages by Sep 5.
- **The first real test is set in advance.** When Kalshi removes `liquidity_dollars` on Oct 1, the watcher must WARN "field gone" within 2 hourly snapshots. If it stays silent, it is broken.

## Start and stop

Start it detached, from the Bash tool or a prompt. It runs its self-test first and refuses to touch Kalshi if that fails:

```
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Python314\python.exe' -ArgumentList '-u','C:\kals-repo\research\kalshiwatch.py','--loop' -WorkingDirectory 'C:\kals-repo' -WindowStyle Hidden -RedirectStandardOutput 'C:\kals-repo\results\kalshiwatch-stdout.log' -RedirectStandardError 'C:\kals-repo\results\kalshiwatch-stderr.log'"
```

- **Stop:** create the file `C:\kals-repo\results\kalshiwatch.stop`. It exits within 10 seconds. **Delete that file before starting again**, or the loop exits at once.
- **Cost:** 42 Kalshi reads and 24 page reads per hour. About 2 KB of log per hour. The state file is about 190 KB and is overwritten, not grown.
- **Files:** alerts go to `results/kalshiwatch-alerts.jsonl`, which only exists once something has changed. The last snapshot is in `results/kalshiwatch-state.json`.

## Phone alerts (not wired; pinphone was not edited)

The watcher never sends Telegram itself. Adding one line inside `alerts_tick()` in `research/pinphone.py`, plus `import kalshiwatch` at the top, would forward every ALERT to the phone:

```python
for m in kalshiwatch.poll_alerts(self): self.muted or self.say(m)
```

- On its first call it skips the alert backlog, so a restart never replays old alerts.
- It never reads a half-written line.
- Importing it does not load the API key.

## Limits

- It checks once an hour. A rename that lands mid-hour costs up to an hour before the ALERT. The bot's own errors will usually show sooner. The watcher's value is mainly in scheduled fee changes, changelog entries and rules text, which arrive before they take effect.
- The fee PDF is compared as raw bytes. A change means "go and read it", not "the fees went up".
- The `/portfolio/orders` record shape comes from our single most recent order. If fields differed between canceled and filled orders, that could raise a false ALERT. This has not been seen, but it has not been tested either.
