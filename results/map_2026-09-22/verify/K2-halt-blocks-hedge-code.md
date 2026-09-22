# K2-halt-blocks-hedge -- CODE verifier (adversarial)

Status: DONE 2026-09-22. Scripts (own, not the investigator's):
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\map\verify2\K2-halt-blocks-hedge-code\`
harness.py (+ .out), logscan.py (+ .out), hedgeval.py (+ .out), outage.py. Code at SHA 73bbb7a.

Claim (06_code-and-infra.md F4): one failed/timed-out/5xx/unreadable/resting order sets pintake's
halt, pinrun never clears it, take() then refuses every order INCLUDING HEDGES for the ~600 s drain.
Never fired in 1,198 orders; tonight's outage returned -1 on 388 REST calls.

## Verdict: CONFIRMED (mechanism exact); framing needs three corrections

1. The money-relevant block is the REST OF THE CURRENT CLOSE (entries only at tau <= 45 s:
   tau_max 30, early_tau_max 45 in the 09-22 05:30Z start record), not 600 s. 600 s is only the
   drain cap; the drain ends when flat; if flat at the trigger there is no drain at all.
2. Denominator: 1,204 `order` records = 978 x 201 + 25 x 409 + 201 rail-refused (never sent).
   So 0 of 1,003 SENT entry orders and 0 of 34 live hedge sends hit a halting code, ever.
3. A naive fix ("hedges skip the halt") can OVER-hedge: when the hedge's own POST is UNKNOWN,
   pinrun books n=0 and would resend the full amount next second. The fix must handle that.

## Code evidence (line numbers)
- ordercli.py:190-195 `send()`: urlopen timeout=20 s; HTTPError -> (code, text); any other exception -> (-1, str).
- pintake.py:584-669 `_book()`: 4xx -> release, no halt (658). -1/3xx/5xx/2xx missing a count -> halt (660-669).
  IOC rested -> halt at 631 (cancel needed / late fill), 645 (cancel unverified), 655 (no unrest run).
- pintake.py:437-438 `check_take()`: `if L.get("halt"): bad.append("ledger HALTED")` -- no exemption.
- pintake.py:679-702 `take()`: any violation -> return refusal before `send`; signature has no hedge flag.
- pintake.py:286 `clear_halt()`: called nowhere in the repo outside pintake's self-test (grep *.py, *.ps1).
  pinrun's `"halt": None` writes (3845, 5479, 5519, 5716) are all inside `_selftest_body` (def 3175).
  `reset_ledger` in pinrun: self-test only. Only a new process clears it.
- pinrun.py:9258 hedge = `pintake.take(..., exchange_index=2)`; 9265-9269 refusal -> `hedge_refused take_refused`, continue.
  HEDGE_PANIC (9149) bypasses hedge_price/normal/attempt_cap only -- NOT pintake. Panic hedges are blocked too.
- pinrun.py:7779-7780 risk_abort -> "pintake halted: ..."; TRANSIENT_HALTS (7945) excludes it -> terminal.
- pinrun.py:9367-9387 A74 drain: `open_contracts(pintake.LEDGER) or len(open_pos)`; loop until flat or DRAIN_MAX_S 600 (7952).
  Hedge pass (8965-9312) runs above risk_abort (9320) during the drain -- and every send is refused.
- No mitigation found: pinrun never reads /portfolio/orders or /portfolio/positions (only /portfolio/balance, 8219).

## Harness (offline; fake wire, urlopen replaced by a raiser; pinrun functions exec'd from source)
Hold 10 BTC, trigger, then a BTC hedge with a HEALTHY wire (13 cells):
| trigger | halt | hedge reached wire |
|---|---|---|
| 201 fill / 429 / 400 (controls) | no | yes |
| -1 timeout; -1 DNS; 503; 502; 301; 200 `{}`; 201 no remaining_count | YES | NO (take_refused) |
| 201 IOC rested, cancel verified; 201 rested, cancel unreadable | YES | NO |
| the hedge's OWN POST -1, then the top-up | YES | NO |
Persistence: 21 of 21 hedge tries over 600 s refused; after `clear_halt()` the hedge is sent (201).
risk_abort -> "pintake halted..."; halt_is_transient False; holding -> drain; flat -> immediate halt+exit.

## Live-log facts (124 files, 09-08 06:20Z .. 09-22 09:20Z)
- status codes on sent entry orders: 201 x978, 409 x25; no -1/5xx/3xx. hedge_refused: 0 ever. halt records: 10, none from pintake.
- universe -1: 393 total; 388 in one cluster 09-22 00:50:09Z-05:37:13Z (20:50-01:37 ET, 4.78 h) -- claim exact;
  4 on other nights (09-09, 09-11, 09-14, 09-17) + 1 at 09-22 09:01Z. Spread over all 11 series (25-45 each),
  never 2 in one second, max 3/min: INTERMITTENT, most calls in each sweep succeeded (per-call failure
  roughly 4-8% from 388 fails over ~480-860 sweeps x 11 series -- an ESTIMATE, successful calls are not logged). That is the worst case for this halt:
  one failure in ~12-25 calls would lock out the 92-96% of hedge POSTs that would have gone through.
- 0 fills inside the outage cluster (nearest 1,361 s after). Bot held nothing: confirmed "never fired".

## Worst realistic cost (bot's settled rows, hedge leg vs entry leg; ledger has no leg split)
17 hedged markets / 16 closes (below the 30 floor). Hedge legs total -$35.57 (hedging lost money net).
Blocking a hedge costs money only on a TRUE flip: hedge-leg gains +$15.16, +$20.61, +$22.71, +$24.18,
+$29.30 at 55-84 contracts; on false alarms blocking would have SAVED (-$67.22, -$49.65, -$15.99, -$13.83).
Per event: ~$15-30 per blocked market; tail ~2-3 markets in one close = ~$60-90. Expected value of the
block is NOT shown to be negative (sign unknown at n=16 closes). Missed trading from the exit+restart:
~1 close (median restart gap 156 s per 06 F7) -- cents.

## Adjacent doors the claim does not name (same code, same trigger)
- An UNKNOWN ENTRY that actually filled is invisible: not in open_pos (10614-10650 books only filled>0), never
  hedged, not counted by open_contracts (so a flat bot exits at once), and pinflat reads the bot's log (filled 0).
  Worst: one full leg (~78 x $0.97 = ~$76) riding unhedged and unbooked.
- The 20 s urlopen timeout (ordercli.py:190) freezes the whole loop, hedge pass included, per timed-out POST;
  at tau <= 45 s one hang can eat most of the hedge window with or without the halt.

## Smallest safe fix + self-test
pintake: `check_take(..., hedge=False)` / `take(..., hedge=False)`; when hedge=True skip ONLY the halt
(and LOSS_ABORT / MAX_RUN_STAKE); keep count, HARD_MAX, price, IOC, post_only, tau, prod-arming. Log each bypass.
pinrun 9258: pass `hedge=True`. On a hedge UNKNOWN (not readable 2xx, not 4xx): treat `_hn_take` as COVERED
(`hedge_remain` reduced, `hedged.add` if <= 0) -- errs toward today's under-hedge, never over-hedge; optionally
confirm via GET /portfolio/orders?ticker= matching client_order_id and correct.
Self-test (behavioural, fake wire): (1) entry -1 -> halt; hedge=True POST reaches wire; entry still refused.
(2) hedge=True with count>HARD_MAX / GTC / post_only True / tau>MAX_TAU / unarmed prod -> each refused.
(3) NULL: no halt -> hedge=True and False give identical body and ledger. (4) hedge's own POST -1 -> no resend
on that position next second (wire count unchanged); a second held position's hedge IS sent.
(5) risk_abort still terminal "pintake halted". Anchor any source check on the whole call line with rindex.
Blocks: nothing. Newly allows: hedges after an UNKNOWN (bounded by 4).

## Looks
13 harness cells + persistence + 2 risk_abort cells + 6 log cuts (status codes, hedge_refused, halts,
-1 by day, -1 clustering/series, hedge-leg value) = 22 looks. No conclusion rests on a significance test;
for reference a 5% bar over 22 looks is p < 0.0023. Hedge-value sign is NOT established (16 closes < 30).
