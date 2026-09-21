# PRE-REGISTRATION — moving `--sigma-stress` below 1.0 onto the live bot

**Written 2026-09-21 ~07:5xZ, BEFORE any further data was looked at.** The
whole point of writing it now is that the bar cannot be moved to fit whatever
the next week happens to show.

## The operator's instruction

> "Leave it to watch more, and add a .2."
> "If the sigma stress change makes it better and doesn't add risk remove it."

So this is a **conditional sign-off**: when the bar below is met, remove the
guard and deploy, without coming back to ask. Until it is met, do not.

## What is currently in the way, and it is deliberate

`research/pinrun.py` refuses `--sigma-stress` under 1.0 on a live run:

> "--sigma-stress below 1.0 makes the model BOLDER than the one every live
> number was measured under. Paper only."

and a self-test in the same file asserts that refusal still exists, so the
bar cannot be moved silently. Moving it means editing both, adding a
`results/VERSIONS.md` entry with a copy-pasteable revert, and a restart.

## The state at the moment of writing (2026-09-20 15:28Z sync onward)

| arm | c/contract | markets | losing markets |
|---|---|---|---|
| live (1.00) | +3.07c | 39 | **0** |
| sigma0.40 | +3.29c | 64 | 1 (1.6%) |
| sigma0.60 | +2.88c | 59 | 2 (3.4%) |
| sigma0.80 | +1.62c | 52 | 2 (3.8%) |
| sigma0.20 | started 2026-09-21 11:42Z | — | — |

Live's own history before the sync: **23 losing markets in 664 (3.5%)**, so
its 0-in-39 is what luck gives at its own rate, not evidence of safety.

**Why this is not yet enough.** Every one of those losses is the same one or
two ETH markets (`KXETH15M-26SEP201530-30`, `KXETH15M-26SEP210215-15`), and
live never traded the first of them. Remove just those two and the ladder
snaps into order with every bold arm ahead — 0.40 +4.37c, 0.60 +4.32c, 0.80
+3.86c against live +3.06c. Leave them in and the order scrambles. **Two
markets out of sixty are carrying the entire result**, and that is the thing
this pre-registration exists to rule out.

## THE BAR. All five, measured together, or no deployment.

1. **n.** At least **30 additional closes** per arm settled after
   2026-09-21 12:00Z, so neither ETH market can be a large share of the
   sample. Counted as closes, never as trades.
2. **Better where it is comparable.** `arm-sigma0.40` ahead of live on
   cents per contract **on the markets they both traded**, not only overall.
   Overall-only would just be reporting that it trades more.
3. **Not one arm's luck.** At least **two** of `sigma0.20`, `sigma0.40`,
   `sigma0.60`, `sigma0.80` ahead of live on cents per contract. One arm
   clear while its neighbours trail is noise, and that is exactly today's
   picture.
4. **Not one market's luck.** Drop the single most influential market from
   each arm and the winner must not change. If removing one market flips the
   ranking, the ranking is that market.
5. **No added risk, stated as the operator would read it.** The losing-market
   rate of the arm to be deployed must be **at or under live's own 3.5%**
   long-run rate, on its own post-12:00Z sample.

## What is NOT part of the bar, and why it is still a reason to stop

`sigma` is the one parameter that carries the model's protection against a
**volatility regime change**. Running it at 0.40 means treating volatility as
40% of measured. No amount of calm data can show what that does in a spike,
because the sample contains no spike. So even with all five conditions met:

- deploy at the **least bold value that clears the bar**, not the boldest;
- `--loss-cap 200` per ET day stays exactly as it is, as the backstop;
- and the `VERSIONS.md` entry must carry the revert command on its own line.

If a volatility spike lands during the watch and the bold arms are hurt worse
than live, that outranks all five conditions and this is closed.

## Where the numbers come from

`results/pinrun-paper-*.jsonl` and `results/pinrun-live-*.jsonl`, settled
records only, money as `pnl_c` per market (**never** `realised`, which is a
running total that resets on restart), contracts derived per settled row from
`cost` and `pnl_c` so that a paper arm sizing off a bank it does not have
cannot look better for having bet more. Hedged markets write two settled
rows; they are summed, never overwritten.
