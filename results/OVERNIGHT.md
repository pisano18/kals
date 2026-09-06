# OVERNIGHT — 2026-09-06

**Five lines:**
1. **No order was ever sent.** The demo order dry-ran clean; the live send was blocked by Claude Code's own permission classifier, not by Kalshi. Lifecycle still unproven.
2. **`target_size` is not 1000 everywhere.** Gold/Silver/WTI/NatGas/Copper 15M pay the same $20 per 15 min against a target of **300** — 3.3× cheaper per unit of depth than Coin Race.
3. **But they only run 18:00→00:00 ET** (24 windows/day), so each family is worth $480/day advertised, not $1,920.
4. **And they already pay 96–98% of the time** — *more* reliably than Coin Race's 86% — so they are not empty space. Somebody is there.
5. **Eligibility could not be confirmed by API** (no such endpoint exists); the account has real funded fills, which implies completed KYC, but that is an inference and the only proof is earning a credit.

---

## What the operator has to run by hand

I am blocked from sending it. Nothing here risks real money — this key is
**demo-only**, proven: it returns 200 with a $10 balance on demo and 401
`NOT_FOUND` on production.

```
cd C:\kals-repo\research
python ordercli.py --ticker <a currently-open demo market> --price 0.05 --count 1 ^
  --key-id 6f64485b-3e4d-4110-bdb7-bb489e4d68c6 ^
  --key-file C:/kals/kalshi-demo.pem
```

That prints a **new sign-off token** (the old one, `3d9370ec65771595`, is dead
— its market has expired, and the token is bound to the exact order). Re-run
the same line with `--live --signoff <that token>` appended.

What it proves: that a `post_only` order can be placed, rests in the book,
and can be cancelled. What it does NOT prove: any of the money. Demo's
`/incentive_programs` carries stale data (`discount_factor_bps: 1`, not 5000;
`end_date: 2026-07-30`), so **rebate economics cannot be tested on demo at all.**

---

## Deposit cost, newly measured

`/portfolio/deposits` on production shows real deposits carrying a fee:
1021c on a 20c fee, 1939c on a 38c fee — **≈1.96%**. Funding $500 costs ~$10
before a single order is placed. That is a real drag on any small live test
and had not previously been counted.

## The thing I most want to check next

Live Coin Race, 20:10 UTC: **ETH's yes side had 3 contracts resting against a
target of 1000.** If "either side under target → nobody is paid" is a real
rule, that window pays nobody, and supplying the missing side costs the
*premium* (1,000 at 2c = $20), not the notional. Against a $20 pool that is
roughly break-even at worst and very good at best — which is exactly why I
distrust it. The load-bearing unknown is whether `paid_out: true` means money
reached a participant or merely that the programme was processed. Until that
is settled, every "% paid" number in this project, including the $5,051,195
total, has uncertain meaning.
