#!/usr/bin/env python3
# VERSION: 2026-09-03-s1
"""
strikes.py -- can one event's strikes contradict each other, executably?

    python research/strikes.py --selftest
    python research/strikes.py --data ./kalshi_data --out ./fulltape

THE ONE IDEA THAT NEEDS NO MISPRICING

Every other test in this project asks whether the market's OPINION is wrong,
and the market has answered eight times: it is not. This asks something
weaker and therefore stronger: whether the market is ever INCONSISTENT WITH
ITSELF for a moment.

One 15-minute event carries many strikes of the same contract: pays 100 if
settlement >= K. P(settle >= K) is decreasing in K by arithmetic, not by
opinion. So at any instant, for K_low < K_high:

    ask(K_low)  >=  bid(K_high)      must hold

If it ever fails, buying K_low at its ask and selling K_high at its bid
locks a credit, and the position's settlement payoff 100*(Y_low - Y_high) is
NEVER negative -- it is zero when both strikes agree and +100 when settlement
lands between them. The only costs are the two taker fees.

Books here are 55 contracts deep at the touch and reprice through bursts a
snapshot at a time. Transient crossings are exactly what thin, fast, multi-
instrument books produce, and NOBODY HAS LOOKED.

HONESTY REQUIREMENTS, because an arb counter has its own ways to lie:

  * both quotes must be FRESH. A crossing against a 29-second-old quote is
    usually a quote that no longer exists. Two tiers are reported: STRICT
    (both sides quoted within 2s) and LOOSE (within 30s). Only strict is
    evidence; loose is an upper bound on what better data could reveal.
  * fees are charged on BOTH legs before anything is called a violation.
  * an episode (consecutive seconds of the same crossed pair) is counted
    ONCE, at its first second's credit and size -- the same resting
    contracts cannot be harvested sixty times.
  * the money column uses min(ask size, bid size) at the touch, nothing
    deeper.
  * a 1-second grid cannot see sub-second life. A strict episode lasting
    one grid-second may still be unhittable at human-plus-API latency; the
    actionable class is duration >= 3s, and the table splits it out.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import fee_per_contract                        # noqa: E402

STRICT_AGE = 2.0
LOOSE_AGE = 30.0
WINDOW = 900


def fee_c(price_c):
    """Taker fee in cents for a contract at price_c cents."""
    return 100.0 * fee_per_contract(price_c / 100.0)


# ===========================================================================
def scan_event(rows, close, outcomes, out):
    """One event: rows = [(strike, ticker, quotes)], quotes sorted by sec.

    Appends violation EPISODES to `out`. An episode is one (pair, tier) run
    of consecutive crossed seconds; it carries its first second's economics.
    """
    rows = sorted(rows)
    n = len(rows)
    ptr = [0] * n
    last = [None] * n          # (qsec, bid_c, ask_c, bsz, asz)
    open_ep = {}               # (i, j, tier) -> episode dict

    for sec in range(close - WINDOW, close):
        fresh = [None] * n
        for i, (_k, _tk, q) in enumerate(rows):
            p = ptr[i]
            while p < len(q) and q[p][0] <= sec:
                last[i] = q[p]
                p += 1
            ptr[i] = p
            if last[i] is not None:
                age = sec - last[i][0]
                if age <= LOOSE_AGE:
                    fresh[i] = (age, last[i][1] * 100.0, last[i][2] * 100.0,
                                last[i][3], last[i][4])
        hit = set()
        for tier, max_age in (("strict", STRICT_AGE), ("loose", LOOSE_AGE)):
            # suffix max of bid over strikes ABOVE i, within this tier
            best = [None] * (n + 1)   # (bid_c, j)
            for j in range(n - 1, -1, -1):
                best[j] = best[j + 1]
                f = fresh[j]
                if f is not None and f[0] <= max_age:
                    if best[j] is None or f[1] > best[j][0]:
                        best[j] = (f[1], j)
            for i in range(n - 1):
                f = fresh[i]
                if f is None or f[0] > max_age or best[i + 1] is None:
                    continue
                bid_hi, j = best[i + 1]
                ask_lo = f[2]
                gross = bid_hi - ask_lo
                fees = fee_c(ask_lo) + fee_c(bid_hi)
                net = gross - fees
                if net <= 0:
                    continue
                key = (i, j, tier)
                hit.add(key)
                if key in open_ep:
                    open_ep[key]["dur"] += 1
                else:
                    fj = fresh[j]
                    yl = outcomes.get(rows[i][1])
                    yh = outcomes.get(rows[j][1])
                    bonus = (100.0 * (yl - yh)
                             if yl is not None and yh is not None else None)
                    open_ep[key] = {
                        "tier": tier, "close": close, "sec": sec,
                        "lo": rows[i][1], "hi": rows[j][1],
                        "k_lo": rows[i][0], "k_hi": rows[j][0],
                        "gross": gross, "fees": fees, "net": net,
                        "size": min(f[4], fj[3]),
                        "age": max(f[0], fj[0]), "dur": 1, "bonus": bonus,
                    }
        for key in [k for k in open_ep if k not in hit]:
            out.append(open_ep.pop(key))
    out.extend(open_ep.values())


def scan(quotes, markets, verbose=True):
    """Group tickers into events and scan each. Returns episodes, stats."""
    events = defaultdict(list)
    outcomes = {}
    from replay import series_of
    from endgame import outcome_of
    for tk, m in markets.items():
        q = quotes.get(tk)
        st = m.get("strike")
        close = m.get("close")
        if not q or st is None or close is None:
            continue
        events[(series_of(tk), int(round(float(close))))].append(
            (float(st), tk, q))
        y = outcome_of(m)
        if y is not None:
            outcomes[tk] = y
    episodes = []
    stats = defaultdict(int)
    done = 0
    for (ser, close), rows in events.items():
        done += 1
        if verbose and done % 500 == 0:
            print(f"    {done:,}/{len(events):,} events, "
                  f"{len(episodes):,} episodes", flush=True)
        if len(rows) < 2:
            stats["single_strike_events"] += 1
            continue
        stats["events"] += 1
        stats["strike_pairs"] += len(rows) * (len(rows) - 1) // 2
        scan_event(rows, close, outcomes, episodes)
    stats["episodes"] = len(episodes)
    return episodes, dict(stats)


# ===========================================================================
def report(episodes, stats):
    ev = stats.get("events", 0)
    ss = stats.get("single_strike_events", 0)
    print(f"\n  {ev:,} multi-strike events scanned, "
          f"{stats.get('strike_pairs', 0):,} strike pairs, "
          f"{ss:,} single-strike skipped")
    if ev == 0 and ss:
        # THE ZERO MEANS SOMETHING DIFFERENT FROM "no crossings found", and
        # reading it the other way would be the project's favourite mistake.
        # Measured 2026-09-04: 7,907 events, EVERY ONE of them a single
        # strike. These 15-minute crypto contracts carry one strike per
        # window -- set to the previous window's settlement, which is the
        # same fact as strike(N+1) == settle(N). There is no second strike
        # to cross against, so cross-strike arbitrage is not mispriced here,
        # it is UNDEFINED.
        print("\n  *** EVERY event has exactly ONE strike. This product has")
        print("  one strike per window (strike(N+1) == settle(N)), so there")
        print("  is no second leg to cross against. The zero below is not")
        print("  'no crossings were found' -- the question does not exist")
        print("  for this contract. It WOULD exist for a multi-outcome")
        print("  series such as the Coin Race (KXCRYPTOLEAD15M), where the")
        print("  legs must sum to 100c; point this at that tape once it has")
        print("  a few days on disk.")
    for tier in ("strict", "loose"):
        eps = [e for e in episodes if e["tier"] == tier]
        print("\n" + "=" * 78)
        print(f"{tier.upper()} tier -- both quotes at most "
              f"{STRICT_AGE if tier == 'strict' else LOOSE_AGE:.0f}s old"
              + ("  (the evidence)" if tier == "strict"
                 else "  (an upper bound, mostly phantom quotes)"))
        print("=" * 78)
        if not eps:
            print("  zero violation episodes. The strikes never "
                  "contradicted each other executably in this tier.")
            continue
        closes = {e["close"] for e in eps}
        days = max(1.0, (max(closes) - min(closes)) / 86400.0)
        total = sum(e["net"] * e["size"] for e in eps) / 100.0
        durs = sorted(e["dur"] for e in eps)
        nets = sorted(e["net"] for e in eps)
        szs = sorted(e["size"] for e in eps)
        long_eps = [e for e in eps if e["dur"] >= 3]
        long_total = sum(e["net"] * e["size"] for e in long_eps) / 100.0
        print(f"  {len(eps):,} episodes over {len(closes):,} closes "
              f"(~{len(eps) / days:.1f}/day)")
        print(f"  net credit/contract: median {nets[len(nets)//2]:.2f}c, "
              f"max {nets[-1]:.2f}c   duration: median "
              f"{durs[len(durs)//2]}s, max {durs[-1]}s")
        print(f"  executable size: median {szs[len(szs)//2]:.0f}, "
              f"max {szs[-1]:.0f} contracts")
        print(f"  theoretical take, one hit per episode at touch size: "
              f"${total:,.2f} over the tape (${total / days:,.2f}/day)")
        print(f"  the ACTIONABLE class (duration >= 3s): {len(long_eps):,} "
              f"episodes, ${long_total:,.2f} (${long_total / days:,.2f}/day)")
        bon = [e for e in eps if e.get("bonus") is not None]
        if bon:
            nb = sum(1 for e in bon if e["bonus"] > 0)
            print(f"  settlement landed BETWEEN the strikes (the free +100) "
                  f"in {nb:,} of {len(bon):,} settled episodes")
        top = sorted(eps, key=lambda e: -e["net"] * e["size"])[:5]
        print("\n  the five largest:")
        for e in top:
            print(f"    {e['lo']} x {e['hi']}  net {e['net']:.2f}c  "
                  f"size {e['size']:.0f}  dur {e['dur']}s  "
                  f"age {e['age']:.0f}s")
    print("\n  A strict episode of one grid-second may still be unhittable")
    print("  at real latency. The >=3s line is the one a bot could take.")


# ===========================================================================
def _mk_quotes(specs):
    """specs: strike -> [(sec, bid_c, ask_c)] -> quotes in load_quotes shape."""
    out = {}
    for st, ql in specs.items():
        tk = f"KXTEST-EV-T{int(st)}"
        out[tk] = [(sec, b / 100.0, a / 100.0, 40.0, 60.0)
                   for (sec, b, a) in ql]
    return out


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []
    import replay
    close = 1767226500
    t0 = close - WINDOW

    def mkts(strikes, results=None):
        out = {}
        for st in strikes:
            tk = f"KXTEST-EV-T{int(st)}"
            out[tk] = {"ticker": tk, "close": close, "strike": float(st),
                       "result": (results or {}).get(st, 1.0)}
        return out

    # ---- 1. a monotone book must produce ZERO episodes -------------------
    print("\n  A properly ordered book: P falls with the strike, spreads")
    print("  1-2c. Zero violations, in both tiers.")
    specs = {}
    rnd = random.Random(3)
    for i, st in enumerate((100, 200, 300, 400)):
        base = 80 - 18 * i
        specs[st] = [(t0 + s, base + rnd.choice((-1, 0, 1)),
                      base + 2 + rnd.choice((0, 1))) for s in range(WINDOW)]
    eps, stt = scan(_mk_quotes(specs), mkts((100, 200, 300, 400)),
                    verbose=False)
    print(f"    {stt['events']} event, {len(eps)} episodes")
    if eps:
        fails.append(f"a monotone book produced {len(eps)} violation "
                     "episodes -- the scanner invents free money")

    # ---- 2. a planted crossing must be recovered EXACTLY -----------------
    print("\n  A planted crossing: for 5 seconds the 200-strike asks 40c")
    print("  while the 300-strike bids 46c. Gross 6c, fees "
          f"{fee_c(40) + fee_c(46):.2f}c.")
    specs = {}
    for st, base in ((100, 70), (200, 50), (300, 44), (400, 20)):
        specs[st] = [(t0 + s, base - 1, base + 1) for s in range(WINDOW)]
    for s in range(100, 105):     # the crossing
        specs[200][s] = (t0 + s, 38, 40)
        specs[300][s] = (t0 + s, 46, 48)
    eps, _ = scan(_mk_quotes(specs), mkts((100, 200, 300, 400),
                                          {100: 1.0, 200: 1.0, 300: 0.0,
                                           400: 0.0}), verbose=False)
    strict = [e for e in eps if e["tier"] == "strict"]
    want_net = 6.0 - fee_c(40) - fee_c(46)
    ok = (len(strict) == 1 and abs(strict[0]["net"] - want_net) < 1e-9
          and strict[0]["dur"] == 5 and strict[0]["size"] == 40.0)
    got = (strict[0] if strict else None)
    print(f"    recovered: {len(strict)} strict episode(s), "
          + (f"net {got['net']:.2f}c dur {got['dur']}s size "
             f"{got['size']:.0f}, bonus {got['bonus']}" if got else "none"))
    if not ok:
        fails.append(f"planted crossing (net {want_net:.2f}c, 5s, size 40) "
                     f"came back as {got}")
    # settlement landed between the strikes: Y(200)=1, Y(300)=0 -> +100
    if strict and strict[0]["bonus"] != 100.0:
        fails.append("the between-the-strikes settlement bonus was not "
                     "+100 on a fixture built to produce it")

    # ---- 3. a crossing SMALLER than the two fees is not a violation ------
    print("\n  A 1c crossing against ~3.4c of fees must NOT count.")
    specs2 = {st: list(ql) for st, ql in specs.items()}
    for st in specs2:
        specs2[st] = [(t0 + s, {100: 69, 200: 49, 300: 43, 400: 19}[st],
                       {100: 71, 200: 51, 300: 45, 400: 21}[st])
                      for s in range(WINDOW)]
    for s in range(200, 210):
        specs2[200][s] = (t0 + s, 43, 45)
        specs2[300][s] = (t0 + s, 46, 48)     # gross 1c < fees
    eps2, _ = scan(_mk_quotes(specs2), mkts((100, 200, 300, 400)),
                   verbose=False)
    print(f"    episodes: {len(eps2)}")
    if eps2:
        fails.append("a crossing below the round-trip fee was counted")

    # ---- 4. a crossing against a STALE quote is loose, never strict ------
    # The first version of this fixture let the crossing begin one second
    # after the quote went silent -- at age 1 and 2 the quote is still
    # "fresh" by the strict definition, so strict fired and the test blamed
    # the scanner. The quote must be SANE while alive and only crossed once
    # it is 11 seconds dead.
    print("\n  The high strike's book dies quoting sanely; 11 seconds")
    print("  later the low strike drops through its ghost. Loose tier")
    print("  only -- a stale quote is usually a phantom.")
    specs3 = {}
    for st, base in ((200, 50), (300, 44)):
        specs3[st] = [(t0 + s, base - 1, base + 1) for s in range(WINDOW)]
    specs3[300] = specs3[300][:300]           # silent from second 300
    for s in range(310, 330):                 # ghost bid 43 vs ask 32
        specs3[200][s] = (t0 + s, 30, 32)
    eps3, _ = scan(_mk_quotes(specs3), mkts((200, 300)), verbose=False)
    tiers = sorted({e["tier"] for e in eps3})
    print(f"    tiers hit: {tiers}")
    if "strict" in tiers:
        fails.append("a 20-second-old quote was treated as executable in "
                     "the strict tier")
    if "loose" not in tiers:
        fails.append("the loose tier missed a crossing it defines")

    # ---- 5. non-adjacent pairs must be seen ------------------------------
    # The first fixture kept the middle strikes' tight books, so dropping
    # the 100-strike's ask to 42 ALSO crossed the 200-strike's bid at 51 --
    # a bigger violation, which the scanner correctly preferred, and the
    # test blamed the scanner. The middle books must be wide enough that
    # only the far pair crosses.
    print("\n  The crossing is between strikes 100 and 400; the middle")
    print("  strikes quote WIDE (30-60) so only the far pair crosses.")
    print("  Adjacent-only scanning misses it.")
    specs4 = {}
    for st, (b_, a_) in ((100, (54, 56)), (200, (30, 60)), (300, (28, 62)),
                         (400, (46, 48))):
        specs4[st] = [(t0 + s, b_, a_) for s in range(WINDOW)]
    for s in range(400, 406):
        specs4[100][s] = (t0 + s, 40, 42)
        specs4[400][s] = (t0 + s, 50, 52)
    eps4, _ = scan(_mk_quotes(specs4), mkts((100, 200, 300, 400)),
                   verbose=False)
    pairs = {(e["k_lo"], e["k_hi"]) for e in eps4 if e["tier"] == "strict"}
    print(f"    strict pairs found: {sorted(pairs)}")
    if (100.0, 400.0) not in pairs:
        fails.append("the 100x400 crossing was missed -- the scan is "
                     "adjacent-only and the suffix maximum is wrong")

    print()
    if fails:
        print("=" * 78)
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        print("=" * 78)
        return False
    print("=" * 78)
    print("SELF-TEST PASSED -- silent on a sane book, exact on a planted")
    print("crossing net of both fees, blind to phantoms in the strict tier,")
    print("and sees non-adjacent pairs.")
    print("=" * 78)
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    from replay import load_quotes, load_markets
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to analyse")
        return
    markets = load_markets(a.out)
    if not markets:
        print("\n  *** NO SETTLED MARKETS -- nothing to analyse")
        return
    print("\n" + "=" * 78)
    print("DO THE STRIKES EVER CONTRADICT EACH OTHER, EXECUTABLY?")
    print("=" * 78)
    episodes, stats = scan(quotes, markets, verbose=True)
    report(episodes, stats)


if __name__ == "__main__":
    main()
