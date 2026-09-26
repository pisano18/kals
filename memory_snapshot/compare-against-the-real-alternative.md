---
name: compare-against-the-real-alternative
description: "Before calling something a defect, price the action against what we could actually have done instead - not against never having entered"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-18T14:19:04.901Z
---

2026-09-18. Live oil lost $9.52. I found we had bought BOTH sides of that
market (10 NO at 95.2c, then 5 YES at 97.6c seven seconds later), computed
that the locked pairs cost 92.8c each, called it a guaranteed -$5.52 defect,
and started editing the live guard in `research/cmdlive.py`.

**It was wrong.** Checked against Kalshi's own settlement record, the
opposite-side trade was marginally PROFITABLE in both markets it ever happened
on (+$0.08 and +$0.12) and made the loss smaller, not bigger. The money was
lost by the first leg being on the wrong side, full stop.

**Why I got it wrong:** I priced the pair against *never having entered*, which
was not on the table. By the time the second trade was decided we already held
the first, so the only real choice was "buy the other side or don't" -- and
buying it was the better of the two.

**How to apply:** when something looks like a defect, write down the decision
as it actually stood at that moment, and price every option that was really
available. "Guaranteed loss versus a clean slate" is almost never the
comparison anyone faced. This is the same family as
[[baseline-error-is-our-recurring-bug]] -- a correct calculation against the
wrong reference point.

**And: I nearly changed live-money behaviour on it.** Running the check first
cost two minutes. Do that before touching `restart_bot.ps1`, `cmdlive.py` or
anything else the money flows through, every time, even when the priority order
says lose-less comes first -- especially then.

The real open question from that market is different and still unanswered: the
model bought NO at 9 seconds out and YES at 2 seconds out, reversing itself
inside seven seconds. Whether that reversal predicts the first leg losing is
worth measuring; it has only happened twice on real money, which is far too few.
