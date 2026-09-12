# PRE-REGISTRATION -- the SOL question. Written 2026-09-12 14:1xZ, before the data.

## Why this exists

At the current 0.995 gate, SOL has lost **3 of 14 closes** (21.4%, CI [4.7, 50.8])
against **1 of 101** for the other eight coins. Alone that is p = 0.0055. Scored
honestly -- as the worst of nine coins we went looking through -- it is **p = 0.060**,
and over all live runs p = 0.333. In one afternoon the worst-of-nine p-value went
0.060 -> 0.0285 -> 0.060 as two half-penny hedge-test plants entered and left the
loss count. **That instability is the result.** A coin blacklist decided on 14
closes would be decided by noise. So the test is written down first.

Full analysis: `results/RESULTS_coin.md` (Opus agent, commit 51e6ce6). Two of its
findings bind here: "SOL's feed is the calmest" is a QUANTIZATION ARTEFACT (SOL is
quoted in 0.01 steps against a 0.0082 one-second sigma, so 70% of SOL seconds print
no change) and is withdrawn; and every reconstructable losing close carried a
one-second jump past 5 sigma, but 22-37% of ALL closes do and we win nearly all of
them, so "there was a jump" can never be a gate.

## THE TEST -- fixed before any further SOL close is scored

**Population:** the next **30 SOL closes** on which the live gate (as it stands at the
time, currently PIN 0.995, ceiling 0.98, 15c guard, one fill per market) takes at
least one fill. Plants and hedge legs are excluded by order id (`plant-`, `hedge-`).
Counted by CLOSE, never by fill (hard rule 4: the three NEAR "losses" of 09-09 were
one close).

**Null:** SOL's per-close loss rate equals the pool's. Pool at the current gate is
1 of 101; use 2% as the null rate (conservative toward SOL).

**Decision rule, stated now:**
- **SOL loses 3 or more of the 30** -> P(>= 3 | 30, 2%) = 2.2%. SOL is EXCLUDED from
  the live universe pending a review that must include the mechanism (was each loss a
  >5-sigma one-second jump? at what tau?) and a re-run of RESULTS_coin.md section 4.
- **SOL loses 0 or 1 of the 30** -> the question is CLOSED; SOL stays; no per-coin rule.
- **SOL loses exactly 2** -> inconclusive; extend to 60 closes with the same rule
  (>= 5 of 60 excludes; <= 2 closes it). No third extension.

**Power, stated now:** a coin at 4x the pool rate (8%) loses >= 3 of 30 with
probability ~43%; at 6x (12%) ~70%. So this test can catch a coin that is badly
worse and will miss one that is mildly worse. That is deliberate: a mildly worse coin
costs less than the income lost by excluding it on noise.

**Timing:** ~14 SOL closes are fired per ~4 days at current activity, so 30 closes is
roughly 8-9 days. The count starts with the first SOL fill after this file's commit.

## What would make a positive an artefact

- Plants or hedge legs counted as losses (excluded by id; checked twice).
- Fills counted instead of closes (the NEAR triple).
- A gate change mid-test: if PIN, ceiling, or the guard changes, the count restarts
  and this file gets a dated entry saying so.

## Not amended. If this bar moves, the move is dated and explained here.
