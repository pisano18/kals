#!/usr/bin/env python3
"""pingrow.py -- every trading day from the first live order to three days
past the 250-contract cap, and whether we are on track.

WHAT IT IS FOR. The operator, 2026-09-14: "save this somewhere so we can
compare what really happens to it. This should be like an 'are we on track'
kind of thing."

So it writes results/GROWTH_TRACK.md: the actuals to date, a projection, and
an ON-TRACK line comparing the two. Re-run it any day; the actuals extend and
the projection re-anchors on the real bank.

THE PROJECTION USES THE CURRENT VERSION ONLY. The bot changed almost daily and
the early days do not describe what runs now -- 2026-09-08 to 09-11 netted
+$3.11 combined at a fixed size of 20, before auto-sizing existed. The rate
comes from the window since the depth floor was removed (2026-09-14 14:53Z).

THE DEPTH CURVE IS MEASURED, NOT ASSUMED. research/pincap.py walked 13,984
real ask ladders: the money a single order earns, relative to a 50-lot, is
1.00x at 50, 1.48x at 75, 2.40x at 125, 4.51x at 250, 8.16x at 500. Per unit
of size that is an efficiency of 1.000 / 0.987 / 0.960 / 0.902 / 0.816 -- the
uncapped projection interpolates on it, so "what the market supports" is a
measurement rather than a hope.

    python research/pingrow.py --selftest
    python research/pingrow.py                 # prints and writes the file
"""
import collections
import datetime
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results", "GROWTH_TRACK.md")
BRAKE = 5.88
CAP = 250
CPS = 58                 # contracts per unit of size per day, current version
MEASURED_MAX = 500       # pincap walked real ladders to here; past it, guesswork
# THE REALISTIC CAP. 250 is the constant in the code today; it was chosen
# before the book had been measured. pincap.py walked 13,984 real ask ladders:
# a 500-lot still fills IN FULL on 75.3% of tradeable moments, at a mean
# 95.45c against 95.10c for a 50-lot. So 500 is the largest size the market is
# MEASURED to support, and it is the cap this file projects. Past 500 there is
# no measurement, so the projection stops growing size there rather than
# guessing.
REALISTIC_CAP = 500

# pincap.py: money per unit of size, relative to a 50-lot
# MEASURED, not guessed. research/pincap.py walked 13,984 real ask ladders;
# "money vs a 50-lot" divided by size gives efficiency per unit of size. The
# 1000 entry used to be a round 0.700 placeholder -- it is 0.716 measured. The
# curve now runs to 3,000 contracts, which is where the measurement stops.
DEPTH = [(10, 1.000), (25, 1.000), (50, 1.000), (75, 0.987),
         (125, 0.960), (250, 0.902), (500, 0.816), (1000, 0.716),
         (2000, 0.611), (3000, 0.551)]
MEASURED_SIZE_MAX = 3000

VERSIONS = {
    "2026-09-07": "pre-pin  natgas market-making, both sides quoted",
    "2026-09-08": "v0-v14   pin goes live 07:09Z; EV gate, tau 30, size 1->20",
    "2026-09-09": "v14      size 20 fixed; first big loss (NEAR -$52.60)",
    "2026-09-10": "v15-v16  scale-in, price ceiling",
    "2026-09-11": "v17      15c dump guard live 08:29 ET",
    "2026-09-12": "v18-v22  AUTO-SIZING BEGINS; hedge trigger 0.80",
    "2026-09-13": "v-pick   best-market-first (A24) 20:35 ET",
    "2026-09-14": ("v-ladder 02:1 ET, v-spend, v-brake20, "
                   "v-nofloor 10:53 ET, v-jump 21:39 ET"),
}


def eff(size):
    """Money per unit of size at `size`, relative to a 50-lot. Linear between
    the measured points, flat outside them."""
    if size <= DEPTH[0][0]:
        return DEPTH[0][1]
    if size >= DEPTH[-1][0]:
        return DEPTH[-1][1]
    for (x0, y0), (x1, y1) in zip(DEPTH, DEPTH[1:]):
        if x0 <= size <= x1:
            return y0 + (y1 - y0) * (size - x0) / (x1 - x0)
    return DEPTH[-1][1]


def project(bank, cpc, base_size, cap=CAP, cps=CPS, brake=BRAKE, days=60):
    """(bank, size, contracts, earned) per day. `cpc` is cents per contract
    measured at `base_size`; the depth curve rescales it as size moves."""
    out = []
    b = float(bank)
    base = eff(base_size)
    for _ in range(days):
        size = b / brake
        if cap:
            size = min(cap, size)
        rate = cpc * eff(size) / base
        c = cps * size
        earn = c * rate / 100.0
        out.append((b, size, c, earn))
        b += earn
    return out


def et(t):
    return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S") - datetime.timedelta(hours=4)


def actuals():
    """Per ET day from the live logs: fills, wins, losses, contracts, net."""
    net = collections.defaultdict(float)
    con = collections.Counter()
    fills = collections.Counter()
    wins = collections.Counter()
    losefill = collections.Counter()
    loseclose = collections.defaultdict(set)
    sizes = collections.defaultdict(list)
    banks = []
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        sig, order_day = {}, {}
        for line in open(p, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("t")
            if not t:
                continue
            k = d.get("kind")
            day = et(t).strftime("%Y-%m-%d")
            if k == "signal":
                sig.setdefault(d["ticker"], d.get("want"))
            elif k == "order" and (d.get("filled") or 0) > 0:
                con[day] += d["filled"]
                fills[day] += 1
                order_day.setdefault(d["ticker"], day)
            elif k == "settled":
                net[day] += d.get("pnl_c", 0) / 100.0
                if sig.get(d["ticker"]) == d.get("want"):
                    od = order_day.get(d["ticker"], day)
                    if d.get("result") == d.get("want"):
                        wins[od] += 1
                    else:
                        losefill[od] += 1
                        loseclose[od].add(d["ticker"].rsplit("-", 2)[-2])
            elif k == "autosize" and (d.get("why") or "").startswith("bank $"):
                sizes[day].append(d.get("new"))
                banks.append((t, float(d["why"].split("$")[1])))
    banks.sort()
    return net, con, fills, wins, losefill, loseclose, sizes, banks


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(abs(eff(50) - 1.0) < 1e-9 and abs(eff(250) - 0.902) < 1e-9,
       "the depth curve returns pincap's measured points exactly")
    ck(eff(50) > eff(125) > eff(250) > eff(500),
       "and is monotonically worse as the order grows -- 1.000 / 0.960 / "
       "0.902 / 0.816")
    ck(abs(eff(187.5) - (0.960 + 0.902) / 2) < 1e-9,
       "halfway between two measured points is the midpoint")
    ck(eff(5) == eff(10) and eff(5000) == eff(MEASURED_SIZE_MAX),
       "outside the measured range it is flat, never extrapolated -- the "
       "curve now runs to %d contracts" % MEASURED_SIZE_MAX)
    ck(abs(eff(2000) - 0.611) < 1e-9 and abs(eff(3000) - 0.551) < 1e-9,
       "and the far end is pincap's measured 0.611 at 2000, 0.551 at 3000 -- "
       "not the round 0.700 placeholder that used to sit at 1000")

    r = project(1000.0, 2.4, 62)
    ck(all(x[1] <= CAP + 1e-9 for x in r), "capped: size NEVER exceeds 250")
    ck(abs(project(1e6, 2.4, 62)[0][1] - CAP) < 1e-9,
       "a huge bank is capped at 250, not scaled")
    big = project(1e6, 2.4, 62)
    ck(abs(big[0][3] - big[1][3]) < 1e-9,
       "and past the cap the daily amount is FLAT -- growth stops being "
       "exponential, which is the point of the table")
    u = project(1e6, 2.4, 62, cap=None)
    ck(u[0][1] > CAP, "uncapped: size is free to exceed 250")
    ck(u[1][3] > u[0][3], "and the daily amount keeps growing")
    # the depth curve must BITE: uncapped growth is slower than a naive model
    naive = 1e6 / BRAKE * CPS * 2.4 / 100.0
    ck(u[0][3] < naive,
       "uncapped earnings are BELOW a naive linear model (%.0f vs %.0f) -- "
       "the measured depth curve is doing work, not decoration"
       % (u[0][3], naive))
    z = project(1000.0, 0.0, 62)
    ck(all(abs(x[3]) < 1e-12 for x in z) and abs(z[-1][0] - 1000.0) < 1e-9,
       "NULL: at zero cents per contract nothing is earned, ever, and the "
       "bank never moves")
    ck(project(1000.0, 2.4, 62)[0][3] > project(1000.0, 1.5, 62)[0][3],
       "a worse edge always earns less")
    ck(REALISTIC_CAP == MEASURED_MAX,
       "the realistic cap IS the edge of measurement (%d) -- the projection "
       "never grows size into a region pincap never walked" % REALISTIC_CAP)
    ck(REALISTIC_CAP > CAP,
       "and it is above the %d in the code today, which predates the "
       "measurement" % CAP)
    rr = project(1e7, 2.4, 62, cap=REALISTIC_CAP)
    ck(abs(rr[0][1] - REALISTIC_CAP) < 1e-9 and abs(rr[0][3] - rr[1][3]) < 1e-9,
       "at the realistic cap the daily amount is FLAT too -- raising the cap "
       "moves the ceiling, it does not remove it")
    print("pingrow selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    net, con, fills, wins, losefill, loseclose, sizes, banks = actuals()
    days = sorted(set(list(net) + list(con)))
    first_read = {}
    for t, b in banks:
        first_read.setdefault(et(t).strftime("%Y-%m-%d"), b)
    START = {"2026-09-12": 193.76}
    for d in reversed([x for x in days if x < "2026-09-12"]):
        START[d] = START[days[days.index(d) + 1]] - net[d]
    for d in [x for x in days if x > "2026-09-12"]:
        prv = days[days.index(d) - 1]
        START[d] = first_read.get(d, START[prv] + net[prv])

    L = []
    A = L.append
    A("# GROWTH_TRACK -- are we on track?\n")
    A("*Written by `research/pingrow.py`. Re-run it any day: the actuals extend")
    A("and the projection re-anchors on the real bank. Compare the ON TRACK")
    A("line at the bottom.*\n")
    A("**Last updated: %s ET**\n" % datetime.datetime.utcnow()
      .__sub__(datetime.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"))
    A("\n---\n")
    A("## Part 1 -- every day, actual\n")
    A("Bank is the balance at the START of that ET day. Before 2026-09-12 the bot")
    A("ran a fixed size and never read the balance, so those rows are inferred")
    A("backwards from P&L off the first real read ($193.76).\n")
    A("| day | # | version | bank start | size | max/close | trades | won | lost | losing closes | contracts | c/contract | net | cumulative | return |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    A("| 2026-09-07 | 1 | %s | $65.18 | 20 | - | 16 quotes | 0 | 0 | 0 | 0 | - | **$0.00** | $0.00 | 0.0%% |"
      % VERSIONS["2026-09-07"])
    A("| 2026-09-08 | 2 | *(smoke test 06:34-07:15Z)* | $41.04 | 0.01 | - | 1 | 1 | 0 | 0 | 0.01 | - | **$0.00** | $0.00 | 0.0% |")
    cum = 0.0
    for i, d in enumerate(days):
        ss = sizes.get(d) or []
        med = sorted(ss)[len(ss) // 2] if ss else 20
        b = START[d]
        n = net[d]
        cum += n
        A("| %s | %d | %s | $%.2f | %.0f | %.0f | %d | %d | %d | %d | %.0f | %+.2fc | **%+.2f** | %+.2f | %+.1f%% |"
          % (d, i + 2, VERSIONS.get(d, ""), b, med, 2 * med, fills[d], wins[d],
             losefill[d], len(loseclose[d]), con[d],
             100 * n / max(1, con[d]), n, cum, 100 * n / b))
    tot_c = sum(con.values())
    A("| **TOTAL** | | | | | | **%d** | **%d** | **%d** | **%d** | **%.0f** | **%+.2fc** | **%+.2f** | | |"
      % (sum(fills.values()), sum(wins.values()), sum(losefill.values()),
         sum(len(v) for v in loseclose.values()), tot_c, 100 * cum / tot_c, cum))
    A("")
    A("**Funding.** $38.83 at the first pin version. One deposit of $150, of which")
    A("only **$113.04** reached the crypto shard -- the rest landed on a shard where")
    A("it could not trade. **No deposit since.** The 09-13 and 09-14 bank moves match")
    A("P&L to within 4 cents, so everything after that is traded money.")
    A("")
    A("*(The $65.18 on 09-07 and $41.04 on 09-08 are balances on different shards")
    A("at different moments, not a loss between them -- the account holds more than")
    A("one and only the crypto shard can trade these markets.)*")
    A("")
    A("**The shape of it.** The first four pin days (09-08..09-11) netted **+$3.11")
    A("combined** at a fixed size of 20. Every dollar since is the last three days,")
    A("which is exactly when auto-sizing arrived and the execution fixes landed:")
    A("contracts per unit of size went **25 -> 47 -> 58** as the ladder sweep and")
    A("then the depth-floor removal went in. Same model; it just started buying what")
    A("was in front of it.")
    A("\n---\n")

    bank_now = banks[-1][1]
    med_now = sorted(sizes[days[-1]])[len(sizes[days[-1]]) // 2]
    A("## Part 2 -- projection\n")
    A("Anchored on the real bank, **$%.2f**, and the CURRENT version's measured rate:" % bank_now)
    A("**%d contracts per unit of size per day**, from the window since the depth" % CPS)
    A("floor came off (2026-09-14 14:53Z, 12.2 hours, 21 closes).\n")
    A("That window earned +2.74c per contract and contained **no losses**, so the")
    A("projection does not use it. The cases are **1.5c / 2.4c / 3.5c**, where 2.4c")
    A("is our all-time live average with every loss included.\n")
    A("Size = bank / %.2f. The depth curve is `research/pincap.py`'s measured" % BRAKE)
    A("ladder scaling, so bigger orders earn proportionally less per contract.\n")
    # today's trading is already in the bank we just anchored on, so day 1 is
    # tomorrow. Anchoring on today would double-count the day we just had.
    d0 = datetime.date.today() + datetime.timedelta(days=1)
    def day_table(cpc, cap, limit_after=10):
        """Every day to the cap, plus `limit_after` beyond it."""
        r = project(bank_now, cpc, med_now, cap=cap, days=200)
        cd = next((k for k, x in enumerate(r) if x[1] >= cap - 0.5), None)
        end = (cd + limit_after + 1) if cd is not None else 30
        return r, cd, min(end, len(r))

    A("### The cap, and why 500\n")
    A("`pinrun` caps size at **250** contracts today. That number was chosen")
    A("before the book had ever been measured. `research/pincap.py` then walked")
    A("**13,984 real ask ladders**: a **500-lot still fills in full on 75.3%** of")
    A("tradeable moments, at a mean price of 95.45c against 95.10c for a 50-lot.")
    A("So **500 is the largest size the market is measured to support**, and it is")
    A("the cap used below. Past 500 there is no measurement and this file refuses")
    A("to guess -- size simply stops growing there.\n")
    A("Reaching 500 needs a bank of **$%s** (500 x %.2f). For comparison, the"
      % ("{:,.0f}".format(REALISTIC_CAP * BRAKE), BRAKE))
    A("250 cap needs $%s and is reached roughly a week earlier.\n"
      % "{:,.0f}".format(CAP * BRAKE))
    A("**The risk does not change shape.** At any size, one worst-case close costs")
    A("`2 x size x 0.98` -- a third of the bank, by design. At 500 that is **$980**")
    A("of a $2,940 bank. The 20% drawdown brake still stops the bot before a full")
    A("worst close completes.\n")

    for name, cpc in (("LOW -- 1.5c per contract", 1.5),
                      ("EXPECTED -- 2.4c per contract", 2.4),
                      ("HIGH -- 3.5c per contract", 3.5)):
        r, cd, end = day_table(cpc, REALISTIC_CAP)
        A("### %s\n" % name)
        A("| date | day | bank start | size | max/close | contracts | net | cumulative | return |")
        A("|---|---|---|---|---|---|---|---|---|")
        cum2 = 0.0
        for k in range(end):
            b, s, c, e = r[k]
            cum2 += e
            A("| %s | %d | $%s | %.0f | %.0f | %s | %+.2f | %s | %+.1f%% |%s"
              % ((d0 + datetime.timedelta(days=k)).strftime("%a %d %b"), k + 1,
                 "{:,.2f}".format(b), s, 2 * s, "{:,.0f}".format(c), e,
                 "{:,.2f}".format(cum2), 100 * e / b,
                 " **<== 500 CAP, flat from here**" if k == cd else
                 (" *(250 cap would bind here)*" if abs(s - CAP) < 0.5 or
                  (k and r[k - 1][1] < CAP <= s) else "")))
        A("")
        A("- reaches 500 contracts on **%s** (day %d), bank $%s"
          % ((d0 + datetime.timedelta(days=cd)).strftime("%a %d %b"), cd + 1,
             "{:,.0f}".format(r[cd][0])))
        A("- steady state from there: **$%s/day**, flat"
          % "{:,.0f}".format(r[cd][3]))
        r250, cd250, _ = day_table(cpc, CAP)
        A("- for comparison, capped at 250 it would be **$%s/day** -- the extra"
          % "{:,.0f}".format(r250[cd250][3]))
        A("  250 contracts are worth **$%s/day more**, forever"
          % "{:,.0f}".format(r[cd][3] - r250[cd250][3]))
        A("")

    # Part 3 scores against the EXPECTED case at the realistic cap
    r, cd, _ = day_table(2.4, REALISTIC_CAP)

    A("\n---\n")
    A("## Part 3 -- ON TRACK?\n")
    A("Fill this in as the days land. The projection re-anchors every time this is")
    A("re-run, so compare the **actual net** against the EXPECTED row for that date")
    A("as it stood on 2026-09-15.\n")
    A("| date | projected net (expected) | actual net | on track? |")
    A("|---|---|---|---|")
    for i in range(min(21, cd + 4)):
        A("| %s | %+.2f | | |"
          % ((d0 + datetime.timedelta(days=i)).strftime("%Y-%m-%d"), r[i][3]))
    A("")
    A("**What would put us off track, and what it would mean:**\n")
    A("- **net below the LOW case two days running** -- the edge is decaying, or the")
    A("  market got harder. Check `python research/pinhealth.py` first: the kill line")
    A("  is +1.53c per contract.")
    A("- **contracts per unit of size falling below ~40** -- we are not filling what")
    A("  we used to. That is execution, not edge.")
    A("- **two losing closes in a day** -- the loss brake stops the bot at two, so")
    A("  this shows up as a halt, not a drawdown.")
    A("- **hitting the cap early with the bank still small** -- means the edge ran")
    A("  hot, not that anything is wrong.")
    txt = "\n".join(L) + "\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(txt)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
