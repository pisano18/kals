# The whole project, explained like you're five

_Every number in here is real and measured. Nothing is made up to make the
story nicer._

---

## 1. The game we are playing

There is a place on the internet called Kalshi. On Kalshi you can make tiny
bets about what happens in the next **15 minutes**.

Like this: *"Will Bitcoin cost more 15 minutes from now than it does right
now?"*

If you think **yes**, you pay some pennies for a ticket. Maybe 40 pennies.

- If you were **right**, your ticket turns into **one dollar**. You made 60
  pennies.
- If you were **wrong**, your ticket turns into **nothing**. You lost 40
  pennies.

A new game starts every 15 minutes. All day. Every day. Forever.

**We want to build a robot that plays this game and wins more than it loses.**

Not a big win. A tiny win, over and over, thousands of times. That is how
money is actually made in games like this.

---

## 2. There are two ways to play, and they are very different

Imagine a playground where kids swap marbles.

### The Grabber
You walk up and say **"I'll take it!"** right now, at whatever price is
offered. You get what you want immediately. But you pay a little extra for
being in a hurry.

### The Waiter
You set up a little stall and put up a sign:

> *"I'll BUY a marble for 4 pennies. I'll SELL a marble for 5 pennies."*

Then you wait. If one kid sells you a marble for 4 and another kid buys one
from you for 5, **you keep 1 penny** and you never had to guess which way
marbles were going. You just sat there.

The Waiter looks like the smarter job. **Most of this project has been about
finding out whether it really is.**

---

## 3. What we actually built

### A. A tape recorder that never sleeps
Your computer sits there day and night writing down **everything** that
happens on Kalshi. Every price. Every trade. Every time anyone changes their
mind.

It has written down **72 million** little notes so far. That is about **2
gigabytes** — more writing than every book in a small library.

It also listens to four other websites where people trade Bitcoin, so we can
see the real price at the same moment Kalshi sees it.

### B. A pile of measuring machines
Twenty little programs. Each one asks the tape recorder **one question**:

- *Is there a pattern in when prices jump around?*
- *Does Kalshi's price move before or after the real price?*
- *Are some coins priced differently from their friends?*
- *If we had bet, would we have won?*

### C. One rule that matters more than all the rest

> **Before a measuring machine is allowed to look at real data, it has to
> measure something where we ALREADY KNOW the answer — and get it right.**

Here is why. Imagine you build a ruler and it says your dog is 40 feet long.
You would not say *"wow, big dog."* You would say *"my ruler is broken."*

So: we build a **fake** pretend-world where we secretly hide a treasure. Then
we point the machine at it. If it finds the treasure, the machine works. If it
misses the treasure, or if it finds treasure in a world where we hid **none**,
the machine is broken and we throw it away.

**We have caught about thirty broken rulers this way.** Every single one of
them looked like exciting good news first.

---

## 4. The things that went wrong (and this is normal)

### The notebook was written in a language we forgot
Kalshi quietly changed the *names* of things. Our robot was looking for a box
labelled **"price"**. Kalshi had started calling it **"price_dollars"**.

So the robot opened the notebook, saw nothing it recognised, and cheerfully
said **"all done!"**

**69 million notes read. Zero understood.** Fixed.

### The notebook pages were getting torn
When your computer crashed, the tape recorder was in the middle of writing.
The page never got closed properly. Then when it started again, it wrote a
*second* page on top. And our reader threw **the whole thing** away.

We wrote a new reader that carefully picks up both halves. **It rescues pages
that were already written and were being thrown in the bin.**

### We were counting the page numbers wrong
Every note has a number on it so we can tell if one is missing. We thought
each *market* counted 1, 2, 3. Actually the *whole notebook* counts 1, 2, 3
across all markets at once.

So it looked like pages were missing constantly. **We rebuilt 24 markets out
of 1,090** and threw away the rest for no reason. Fixed.

### And a mistake I made myself, twice
I built a measuring machine and I tested it on the wrong thing — I **checked**
one number and then **printed a different one**. Both were wrong and the test
passed anyway.

That is exactly the same mistake as the broken ruler, wearing a new hat.
**Testing something different from what you report is the same as not testing
at all.**

---

## 5. The one thing we found that is definitely TRUE

> **Wild days come after wild days. Calm days come after calm days.**

When Bitcoin has been jumping around a lot, it keeps jumping around. When it
has been sleepy, it stays sleepy.

We checked this on **5,195 real finished games** across six different coins. We
tried very hard to break it — five different ways, including throwing away the
single wildest day. **It held up every time.**

This is real. **But it is not money yet.** It is only money if Kalshi's prices
*don't already know it*. A shop isn't a bargain just because you know what
bread costs — only if the shop is charging the wrong price.

That is the very next thing to measure.

---

## 6. The sad discovery about being the Waiter

Remember the marble stall? Here is the problem.

**Kids only walk over to your stall when they know something you don't.**

Maybe they just saw the marble truck coming. So when they buy from you, the
marble is about to be worth *more* than you sold it for. When they sell to
you, it's about to be worth *less*.

And here is the mean part: **the fair charges kids 2 pennies just to visit
your stall.**

So a kid will only bother walking over if they think they'll make **more than
2 pennies**. Which means when they arrive, they are *really* sure. And you
lose.

We wrote it down as maths and it is worse than it sounds:

> **However clever you make your sign, you lose about what the fair charged
> them.** Making your prices wider doesn't help — it just makes them *more*
> sure before they walk over.

At the middle of the board that is **1.75 pennies lost every single time**
somebody trades with you.

### But there is a door left open

Not every kid is clever. Some kids swap marbles because they are **bored**, or
**in a hurry**, or **just want a red one**. Those kids pay you your penny and
take nothing back.

So the whole question becomes one number:

> **How many of the people trading are just being silly, and how many actually
> know something?**

If **more than about 8 out of every 10** are being silly, the stall makes
money. If fewer, it loses.

**Nobody knows that number yet. We built the machine that measures it. That is
what runs next.**

---

## 7. What happens next, in order

1. **The tape recorder keeps recording.** It is running right now. Every hour
   we don't record is gone forever, so this never stops.
2. **You run one command.** It takes about two and a half hours and does
   everything by itself.
3. **The new machine counts the silly people.** This is the big one. It tells
   us if the marble stall works.
4. **If the answer is good** → we practise with *pretend* money and check the
   robot does what we designed before any real money moves.
5. **If the answer is bad** → we cross the marble stall off the list, the same
   way we crossed off four other ideas, and we go look somewhere else.

---

## 8. Some honest things a grown-up should hear

**We might find nothing.** Lots of very clever people with much faster
computers are already playing this game. There may be no room left. That is a
real possible ending and we are not pretending otherwise.

**We have crossed off more than we've found.** Delta-hedging: dead, costs
5–200× what it earns. "Every game starts at 50 pennies": false. "Stock markets
charge half the fee": false. "The book lags the real price": false — it's
actually *ahead*. Every one of those took real work to kill, and killing them
is progress, because it stops us betting money on them.

**One true thing so far.** Wild follows wild. Not yet money.

**Not a single order has ever been placed.** There is no code in this entire
project that can buy or sell anything. That is deliberate and it stays that
way until something is actually proven.

**The biggest danger is not losing a bet. It is believing a broken ruler.**
Every exciting result this project has ever produced turned out to be a
measuring mistake — about thirty of them. That is why everything gets tested
against a known answer first, and why I keep telling you when I get something
wrong. If I ever stop doing that, stop trusting the numbers.

---

## 9. Where things actually stand today

| | |
|---|---|
| Tape recorder | **running** |
| Recorded so far | ~46 hours, 72 million notes, 2 GB |
| Measuring machines | 20, all passing their known-answer tests |
| Things proven true | 1 (wild follows wild) |
| Things proven false | 4 |
| The big open question | how many traders are just being silly |
| Real money at risk | **£0 / $0. Nothing. By design.** |
