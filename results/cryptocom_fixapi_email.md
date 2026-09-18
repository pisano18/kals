# Draft email to fixapi@crypto.com

**Subject:** FIX API onboarding enquiry — prediction markets — joepisano18@gmail.com

---

Hello,

I trade systematically on prediction markets and am looking to add
Crypto.com's prediction exchange as a venue. Support directed me to this
address to begin FIX onboarding. My account is under joepisano18@gmail.com.

Before I start the onboarding paperwork, could you confirm a few things so I
can tell whether my strategies transfer? My current activity is
high-frequency, short-horizon, and fully automated, so these are the points
that decide it:

1. **Do the prediction markets include short-duration crypto price
   contracts** — hourly, 15-minute, or other intraday up-or-down markets on
   BTC, ETH and similar? Everything I can find publicly is longer-horizon
   event contracts across politics, economics, sports and culture.

2. **For any crypto price contracts, what is the settlement methodology?**
   Specifically the reference index or price source, and whether settlement
   is a single print at expiry or an average over a window. Is there a
   published contract specification document I can read?

3. **Are the prediction markets reachable over FIX**, or is FIX 4.4 limited
   to the spot and derivatives exchange? If prediction markets are REST and
   WebSocket only, I would rather start there.

4. **Fee schedule for prediction contracts** — maker and taker, and whether
   maker rebates exist.

5. **Rate limits and any market-data entitlements** for order book depth,
   plus whether there is a test or sandbox environment.

6. **Minimum qualification requirements** for FIX access, if any — volume,
   balance, or entity type. I trade a personal account, not a firm.

If FIX is not the right starting point for prediction markets, please point
me to whoever handles programmatic access for that product.

Thank you,
Joe Pisano
joepisano18@gmail.com

---

## Why these six questions, and in this order

**Question 1 and 2 decide everything else.** Our entire edge rests on the
specific settlement mechanics of Kalshi's 15-minute crypto binaries: they
settle on the MEAN OF 60 one-second prints, so with `tau` seconds left,
`60 - tau` of those prints are already fixed and the remaining uncertainty
collapses far faster than time alone would suggest. See `THEORY.md` section 1.

If Crypto.com has no short-duration crypto contracts, **none of the modelling
transfers.** We would be starting from nothing on politics and sports
markets, where we have no model, no feed, and no measured edge. That is not a
venue change, it is a new project.

If they DO have them, question 2 decides the shape of the edge: an AVERAGED
settlement gives the late-certainty profile we already exploit; a SINGLE
PRINT at expiry gives the U-shaped profile we found in Kalshi's commodities.
Either is workable, but they demand different code, and knowing which one
BEFORE writing anything is the single highest-value fact to obtain.

**Question 3 matters because FIX is expensive.** Our stack speaks REST and
WebSocket. FIX 4.4 is a heavyweight session protocol — sequence numbers,
heartbeats, resend requests, session recovery. If prediction markets are
reachable over REST, that is days of work saved and nothing lost.

**Question 4 is not a detail.** At the prices we trade, the fee is a large
share of the edge. Kalshi's taker fee is `0.07 * p * (1-p)`, which is 0.33c at
95c, against a per-contract return of 2-5c. A venue with a flat fee, or a
materially higher one, could be unprofitable at the same win rate.
