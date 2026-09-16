# CDNA trading access — the email, and where it goes

Written 2026-09-16. The operator asked for it twice; keep it here so a cleared
session does not redraft it from scratch.

## Why this is the blocker

Everything else about the venue is solved. `cdc_record.py` pulls their whole
public market-data surface with no key. `cdcchain.py` shows our CF Benchmarks
feed reproduces their published strikes to about 2 basis points on the four
big coins, so we can price their contracts. The one thing we cannot do from
here is send an order: their own docs list REST and WebSocket order entry for
predictions as "coming soon" and FIX as available, and FIX needs them to
issue a session.

## Where to send it

1. **https://institutions.crypto.com/sign_up** — the institutional front door,
   and the only route confirmed live in September 2026. Paste the body into
   the enquiry field.
2. Reply to whatever address answers. Do NOT start at
   `scott.kallback@nadex.com`, which appears in CDNA's 2022 CFTC filing in
   this repo (`results/_cdna_btc_filing.txt`): nadex.com was retired in
   December 2025 and CDNA's compliance officer is reported to have left, so
   that address is probably dead. It is a fallback, not a first try.

## Subject

    FIX access for CDNA prediction contracts

## Body

REWRITTEN 2026-09-16 on the operator's instruction: *"Make the email look less
ai. Especially the em dashes."* No dashes of any kind, no bolded list, no
"Five questions:" scaffolding. Short sentences, one idea each.

    Hi,

    I want to place orders programmatically on CDNA's crypto binary options,
    the 5 and 15 minute ones (NX.F.OPT.* on the DCM).

    I'm already using your public market data (get-instruments, get-book and
    get-trades on api.crypto.com/dcm/v1) and it works well. I can't find any
    documented way to send an order though. The docs show REST and WebSocket
    order entry as coming soon and FIX as available, so I'm assuming FIX is
    what I need.

    A few things I'd like to know.

    Is FIX order entry available to an individual or a small firm, or do I
    need to be a member? If membership is required, what's involved and what
    does it cost?

    Do the crypto binaries trade on the prediction markets FIX surface? The
    docs for that describe sports contracts (Product 460 = 102) and I want to
    confirm the binaries are covered before I go further.

    What does onboarding look like? Certification, test environment,
    SenderCompID, IP allow listing, and roughly how long it takes.

    What are the fees per contract at trade and at settlement, and is there a
    separate market data cost on top?

    Is there a minimum volume or capital requirement?

    I run an automated strategy on Kalshi's 15 minute crypto binaries now and
    want to do the same on CDNA. Happy to jump on a call if that's easier.

    Thanks,
    Joe Pisano
    joepisano18@gmail.com

## Why each question is there

- **(2) is the one that could kill this.** Their FIX prediction-markets page
  describes prediction markets as sports events carrying Product tag 460 with
  value 102. If the crypto binaries are not on that surface, FIX access does
  not get us what we want and we should find out before spending weeks on
  onboarding.
- **(4) is the one that could kill the economics.** Nadex historically billed
  a flat fee per contract at trade and again at settlement. Flat-per-contract
  on a $1-equivalent binary is roughly a hundred times Kalshi's
  `0.07*p*(1-p)`, which on a 97c contract is about a fifth of a cent. A fee
  structure like that eats the entire edge and no amount of access fixes it.
