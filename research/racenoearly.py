#!/usr/bin/env python3
"""racenoearly.py -- is there money in buying a Coin Race NO EARLY?

THE OPERATOR, 2026-09-21: "is there potential in picking earlier NO's, since
that'll get us in cheaper, and it seems like it's a lot easier to calculate an
early NO with 5 coins than it is to do a yes. They hold value longer than other
markets and seem more certain."

HIS REASONING, which is sound as far as it goes. A Coin Race has five legs and
EXACTLY ONE wins. So four legs in five are a NO, and "coin X will not lead" is
a structurally easier call than "coin X will lead". Buy that NO further from
the close and you pay less for the same dollar.

THE COUNTER-HYPOTHESIS, which is what this file is built to distinguish. An
early NO is cheap because the race can still turn. Everything we have measured
on this product so far lives inside the last 60 seconds, where the settlement
average is mostly locked. At tau = 900 nothing is locked: the unlocked variance
is var_factor(900) = 860 seconds' worth against 20.5 at tau = 60, a 42x wider
distribution. A model that cannot tell a beaten leg from a live one at 900 s
will price every leg near 20% and the gate will simply never fire -- and if it
DOES fire, the question becomes whether it fires on anything real.

WHAT IS MEASURED, out to fifteen minutes:

  1. AVAILABILITY -- at each tau, is there a NO we could actually buy at or
     below the live bot's 0.98 ceiling, and at what price and size? A strategy
     with no supply is not a strategy. Reported at two staleness caps so "no
     quote" is never confused with "an old quote".
  2. VALUE -- one entry per race per tau band, taken at the EARLIEST qualifying
     second counting down from the top of the band, gated on the model's own
     edge. Races, losing races, cents per contract, dollars a day at a 100-lot.
  3. EARLY NO vs LATE NO vs LATE YES, on cents per contract AND loss rate.
  4. PERSISTENCE -- the direct test of "they hold value longer". Take the coin
     the model calls most beaten at tau 300 and ask how often it is still the
     most beaten at 120, 60, 30 and still not the winner at 0. Then the same
     for the model's LEADER at 300. THE BASELINE FOR THE NO SIDE IS 80%, not
     50%: four legs in five lose whatever anyone forecasts, so a NO that wins
     82% of the time has shown nothing. That baseline is printed next to every
     NO number here.

THE LAG CONTROL IS NOT OPTIONAL AND IS NOT A FOOTNOTE. A forecast built
through second S, matched to a quote stamped inside second S, can see a
fraction of a second of the future. On this product that fraction has been
worth the entire apparent edge -- racegrid's best rule makes +12c at lag 0 and
LOSES at lag 2. So every headline number here is printed twice: lag 0, and
with the forecast STALED BY 2 SECONDS. If a result dies at lag 2 it was never
real and this file says so in those words.

SOURCES. The Kalshi `ticker` channel (top of book with sizes) and the
1/sec CF Benchmarks index. Not pinsim, not the replay. Per the standing rule
the ordering is index > tape > our fills > replay; this is index + tape. Every
dollar here is therefore a CEILING on what the book offered, never a fill rate
and never our loss rate -- lifting an offer that was resting is not the same
population as someone actively selling to us.

    python research/racenoearly.py --selftest
    python research/racenoearly.py --hours 600
"""
import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

import racebook                                                  # noqa: E402

COINS = racebook.COINS
order_fee = racebook.order_fee

# The tau list the operator asked for: far beyond the 60 s everything else
# here lives inside. 900 is the whole window -- the race's own open. 750 and
# 880 were added after the first run found ZERO quotes at 900: the new race's
# legs are not quoting yet in the second its window opens, and without a tau
# between 600 and 900 that zero would have read as "nobody wants an early NO"
# rather than "the market is not open yet".
TAUS = (20, 30, 45, 60, 90, 120, 180, 240, 300, 450, 600, 750, 880, 900)
BAND_W = 10          # a band is its top tau and the nine seconds below it
LAG = 2              # the staleness that has killed every earlier race rule
MAXAGE = 30          # a quote older than this is not an offer
LOOSE_AGE = 120      # ... and this cap says whether staleness is the binder
PRICE_CEIL = 0.98    # the live bot refuses anything dearer
CAP = 100            # contracts per entry, the size the headline dollars use
BARS = (0.00, 0.01, 0.02, 0.04, 0.08, 0.15)
GRIDDIR = os.path.join(REPO, "flow_cache", "racenoearly")

# Persistence is measured from this tau forward.
PERS_FROM = 300
PERS_AT = (120, 60, 30)


def utcstamp(ts):
    """Epoch seconds -> a naive UTC datetime. EVERYTHING INSIDE THE REPO IS
    UTC; conversion to Eastern happens at the moment of speaking, never in a
    file."""
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(tzinfo=None)


def band_taus(top, width=BAND_W):
    """The seconds a band covers, EARLIEST FIRST.

    Earliest first is the whole point: taking the last chance before the close
    is the most informed and the cheapest print, and reaching for it is how
    this product was over-measured the first three times."""
    return [top - j for j in range(width)]


def needed_taus(taus=TAUS, width=BAND_W, lag=LAG):
    """Every second a forecast is needed for, once, across all bands."""
    out = set()
    for t in taus:
        for tau in band_taus(t, width):
            out.add(tau)
            out.add(tau + lag)
    out |= set(PERS_AT) | {PERS_FROM}
    return sorted(out)


def quote_taus(taus=TAUS, width=BAND_W):
    """Every second a top-of-book snapshot is needed for."""
    out = set()
    for t in taus:
        out.update(band_taus(t, width))
    return sorted(out)


# ------------------------------------------------------------------- scan
def scan_ages(rows, close, taus):
    """{tau: {coin: (bid, ask, bsz, asz, age)}} at the requested seconds.

    Top of book carried forward from the last message at or before that
    second, with the AGE of that message rather than a staleness verdict --
    one pass then serves every age cap the report wants, so "there was no
    quote" and "there was an old quote" are never collapsed into one number.

    Rows must be this race's only. Nothing at or after the close is read: the
    book after a close is a settlement artefact, not an offer."""
    legs = {}
    rows = sorted(rows)
    out = {}
    i = 0
    for sec in sorted(close - t for t in taus if t >= 1):
        while i < len(rows) and rows[i][0] // 1000 <= sec:
            rx_ms, _st, coin, bid, ask, bsz, asz = rows[i]
            if coin in COINS:
                legs[coin] = (bid, ask, bsz, asz, rx_ms // 1000)
            i += 1
        out[close - sec] = {c: (L[0], L[1], L[2], L[3], sec - L[4])
                            for c, L in legs.items()}
    return out


# -------------------------------------------------------------- the offers
def no_offers(quotes, max_age=MAXAGE, ceiling=PRICE_CEIL):
    """[(coin, price, size)] -- the NO legs buyable at one second.

    BUYING NO MEANS MATCHING A RESTING YES BID, never the ask. Price is
    1 - yes_bid and the size available is the yes BID size. Getting this
    backwards prices the trade at the wrong side of the spread and invents
    liquidity that is not there."""
    out = []
    for coin, q in quotes.items():
        bid, _ask, bsz, _asz, age = q
        if age > max_age or bsz < 1 or not (0.0 < bid < 1.0):
            continue
        price = round(1.0 - bid, 4)
        if price > ceiling:
            continue
        out.append((coin, price, bsz))
    return out


def yes_offers(quotes, max_age=MAXAGE, ceiling=PRICE_CEIL):
    """[(coin, price, size)] -- the YES legs buyable at one second (the ask)."""
    out = []
    for coin, q in quotes.items():
        _bid, ask, _bsz, asz, age = q
        if age > max_age or asz < 1 or not (0.0 < ask < 1.0) or ask > ceiling:
            continue
        out.append((coin, round(ask, 4), asz))
    return out


# ------------------------------------------------------------------- rules
def run_band(grid, top, width=BAND_W, side="no", bar=0.0, lag=0, cap=CAP,
             max_age=MAXAGE, ceiling=PRICE_CEIL, pick="edge", floor=0.0):
    """One position per race, in one tau band. Returns a list of bets.

    The forecast used at second `tau` is the one built at `tau + lag`. A NO on
    coin C wins when C is not the winner; a YES wins when it is.

    `pick` decides WHICH leg is bought once more than one clears the bar, and
    the two answers are not the same strategy:

      "edge" -- the biggest gap between model and price. This is what every
                other rule in this repo does, and on the race it reaches for
                the MARGINAL leg: the dead leg is already priced at 97c and
                offers no gap, so the gap lives on a 45c leg that genuinely
                might win.
      "safe" -- the leg the model is most sure about. This is the operator's
                actual proposal ("four of five lose, name the deadest one"),
                and it buys a different contract at a different price. Running
                only "edge" would have answered a question he did not ask.

    `floor` is a MINIMUM price, and it is here so this file can reproduce the
    rule the running race paper arms actually use (--min-price 0.90). Without
    it "early NO vs what we do now" would compare against a rule nobody is
    running."""
    bets = []
    for close, winner, P, Q in grid:
        for tau in band_taus(top, width):
            quotes = Q.get(tau)
            probs = P.get(tau + lag)
            if not quotes or not probs:
                continue
            offers = (no_offers(quotes, max_age, ceiling) if side == "no"
                      else yes_offers(quotes, max_age, ceiling))
            best = None
            for coin, price, size in offers:
                p = probs.get(coin)
                if p is None or price < floor:
                    continue
                worth = (1.0 - p) if side == "no" else p
                edge = worth - price - order_fee(1, price)
                if edge < bar:
                    continue
                rank = edge if pick == "edge" else worth
                if best is None or rank > best[0]:
                    best = (rank, edge, coin, price, size)
            if best is None:
                continue
            _rank, edge, coin, price, size = best
            n = min(int(size), cap)
            if n < 1:
                continue
            won = (coin != winner) if side == "no" else (coin == winner)
            pnl = n * ((1.0 - price) if won else -price) - order_fee(n, price)
            bets.append((close, tau, coin, side, price, n, won, pnl,
                         100.0 * edge))
            break                      # ONE ENTRY PER RACE. Never relax.
    return bets


def confident_leg(grid, tau, side="no", lag=0, cap=CAP, max_age=MAXAGE,
                  ceiling=PRICE_CEIL):
    """The operator's idea on its own terms, with NO edge bar at all.

    At one second, name the leg the model is most sure about -- the most
    beaten for a NO, the leader for a YES -- and buy it if the book will sell
    it at or below the ceiling. No gap test, no shopping around.

    Returns (bets, scored, blocked, unquoted): how many races had a forecast,
    how many were refused because the leg was already dearer than the ceiling
    (that refusal IS the answer to "is it cheaper early?"), and how many had
    no usable quote on that leg at all."""
    bets = []
    scored = blocked = unquoted = 0
    for close, winner, P, Q in grid:
        probs = P.get(tau + lag)
        quotes = Q.get(tau)
        if not probs or len(probs) < len(COINS) or quotes is None:
            continue
        scored += 1
        coin = (min(probs, key=lambda c: probs[c]) if side == "no"
                else max(probs, key=lambda c: probs[c]))
        q = quotes.get(coin)
        if q is None or q[4] > max_age:
            unquoted += 1
            continue
        bid, ask, bsz, asz, _age = q
        if side == "no":
            price, size = round(1.0 - bid, 4), bsz
            ok = bsz >= 1 and 0.0 < bid < 1.0
        else:
            price, size = round(ask, 4), asz
            ok = asz >= 1 and 0.0 < ask < 1.0
        if not ok:
            unquoted += 1
            continue
        if price > ceiling:
            blocked += 1
            continue
        p = probs[coin]
        worth = (1.0 - p) if side == "no" else p
        edge = worth - price - order_fee(1, price)
        n = min(int(size), cap)
        if n < 1:
            unquoted += 1
            continue
        won = (coin != winner) if side == "no" else (coin == winner)
        pnl = n * ((1.0 - price) if won else -price) - order_fee(n, price)
        bets.append((close, tau, coin, side, price, n, won, pnl, 100.0 * edge))
    return bets, scored, blocked, unquoted


# ---------------------------------------------------------------- reporting
def pct(v, q):
    if not v:
        return float("nan")
    v = sorted(v)
    i = max(0, min(len(v) - 1, int(q * (len(v) - 1) + 0.5)))
    return v[i]


def breakeven(price):
    """The loss rate at which a bet bought at `price` exactly breaks even.

    Per contract a win pays (1 - price), a loss costs price, and the taker fee
    is paid either way, so E = (1 - price) - L - fee and E = 0 at
    L = 1 - price - fee. THIS COLUMN IS WHY THE TABLES BELOW ARE READABLE: a
    row that lost 0 of 55 races at 96c looks flawless and is not, because it
    only needed to lose 3 to be flat. The fee is the unrounded 0.07p(1-p);
    real fees round up per order, so the true bar is very slightly tighter."""
    return 1.0 - price - 0.07 * price * (1.0 - price)


def upper95(k, n):
    """95% upper bound on a rate of k out of n -- pinracemodel's function,
    copied so this file stands alone. A zero cell is the rule of three, never
    a zero: 0 losses out of 55 is 'at most 5.5%', which at a 96c price is
    WORSE than the 4.1% break-even, so 0-of-55 establishes nothing."""
    if n <= 0:
        return 1.0
    if k <= 0:
        return min(1.0, 3.0 / n)
    z = 1.96
    ph = k / float(n)
    den = 1.0 + z * z / n
    cen = ph + z * z / (2 * n)
    import math
    rad = z * math.sqrt(ph * (1 - ph) / n + z * z / (4.0 * n * n))
    return min(1.0, (cen + rad) / den)


HEAD = ("  %-26s %6s %5s %6s %6s %6s %7s %6s %9s %9s %8s"
        % ("rule", "races", "lost", "lost%", "<=95%", "need%", "contr",
           "paid", "c/contract", "total $", "$/day"))


def line(bets, label, days):
    if not bets:
        print("  %-26s %6s" % (label, "-"))
        return
    cts = sum(b[5] for b in bets)
    pnl = sum(b[7] for b in bets)
    bad = sum(1 for b in bets if not b[6])
    paid = sum(b[4] * b[5] for b in bets) / cts
    print("  %-26s %6d %5d %5.1f%% %5.1f%% %5.1f%% %7.0f %5.1fc %+8.2fc "
          "%+9.2f %+8.2f"
          % (label, len(bets), bad, 100.0 * bad / len(bets),
             100.0 * upper95(bad, len(bets)), 100.0 * breakeven(paid), cts,
             100 * paid, 100 * pnl / cts, pnl, pnl / days if days else 0.0))


# ------------------------------------------------------------- persistence
def persistence(grid, frm=PERS_FROM, at=PERS_AT):
    """How long does a verdict at `frm` survive?

    Returns (n, {tau: still_beaten}, {tau: still_leading}, no_wins, yes_wins,
    med_claim_no, med_claim_yes).

    "Still beaten" is the strict test -- still the single most beaten of the
    five. "no_wins" is the terminal fact that actually pays: the coin called
    most beaten at `frm` was not the winner. FOUR LEGS IN FIVE LOSE ANYWAY, so
    80% is the baseline for no_wins and 20% for yes_wins."""
    n = 0
    sb = {t: 0 for t in at}
    sl = {t: 0 for t in at}
    seen = {t: 0 for t in at}
    no_wins = yes_wins = 0
    cl_no, cl_yes = [], []
    for _close, winner, P, _Q in grid:
        p0 = P.get(frm)
        if not p0 or len(p0) < len(COINS):
            continue
        beaten = min(p0, key=lambda c: p0[c])
        leader = max(p0, key=lambda c: p0[c])
        n += 1
        cl_no.append(1.0 - p0[beaten])
        cl_yes.append(p0[leader])
        for t in at:
            pt = P.get(t)
            if not pt or len(pt) < len(COINS):
                continue
            seen[t] += 1
            if min(pt, key=lambda c: pt[c]) == beaten:
                sb[t] += 1
            if max(pt, key=lambda c: pt[c]) == leader:
                sl[t] += 1
        no_wins += 1 if beaten != winner else 0
        yes_wins += 1 if leader == winner else 0
    return n, sb, sl, seen, no_wins, yes_wins, cl_no, cl_yes


# --------------------------------------------------------------- the grid
def build_grid(races, M, F, idx, ruler="3600", kappa=1.0, progress=False):
    """[(close, winner, {tau: probs}, {tau: quotes})] -- priced once."""
    ntaus = needed_taus()
    qtaus = quote_taus()
    out = []
    for k, (close, _stamp, rows) in enumerate(races):
        rets = M.returns_at(idx, close, 0)
        if len(rets) < len(COINS):
            continue
        winner = max(rets, key=lambda c: rets[c])
        Q = scan_ages(rows, close, qtaus)
        if not any(Q.values()):
            continue
        ser = F.RaceSeries(idx, close)
        P = {}
        for tau in ntaus:
            pr, _ = F.fair_at(idx, ser, close, tau, ruler, (kappa,))
            if pr is not None:
                P[tau] = pr[kappa]
        if P:
            out.append((close, winner, P, Q))
        if progress and (k + 1) % 50 == 0:
            print("  ... %d/%d races priced" % (k + 1, len(races)), flush=True)
    return out


def save_grid(grid, path):
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as fh:
        for close, winner, P, Q in grid:
            fh.write(json.dumps([
                close, winner,
                {str(t): {c: round(p, 5) for c, p in d.items()}
                 for t, d in P.items()},
                {str(t): {c: list(q) for c, q in d.items()}
                 for t, d in Q.items()}]) + "\n")
    os.replace(tmp, path)


def load_grid(path):
    out = []
    with gzip.open(path, "rt") as fh:
        for line_ in fh:
            close, winner, P, Q = json.loads(line_)
            out.append((close, winner,
                        {int(t): d for t, d in P.items()},
                        {int(t): {c: tuple(q) for c, q in d.items()}
                         for t, d in Q.items()}))
    return out


# -------------------------------------------------------------- self-test
def _q(bid, ask, bsz, asz, age=0):
    return (bid, ask, bsz, asz, age)


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # ---- the break-even column, which is what makes a 0-loss row readable
    ck(abs(breakeven(0.50) - (0.5 - 0.0175)) < 1e-12,
       "a 50c bet breaks even losing %.1f%% of the time" % (100 * breakeven(0.5)))
    ck(0.040 < breakeven(0.956) < 0.042,
       "a 95.6c bet breaks even at a %.1f%% loss rate -- 4 losses in 100"
       % (100 * breakeven(0.956)))
    ck(breakeven(0.98) < 0.02 and breakeven(0.99) < 0.01,
       "and at the 98c ceiling the whole margin is under 2c a contract")
    ck(breakeven(0.90) > breakeven(0.96),
       "a cheaper bet tolerates more losses, which is the operator's point")
    ck(0.054 < upper95(0, 55) < 0.056,
       "0 losses in 55 races is AT MOST %.1f%% -- above the 4.1%% a 95.6c "
       "bet needs, so a flawless row of 55 establishes nothing"
       % (100 * upper95(0, 55)))
    ck(upper95(0, 550) < upper95(0, 55) and upper95(0, 0) == 1.0,
       "ten times the races tightens it to %.1f%%; no races at all is 100%%"
       % (100 * upper95(0, 550)))
    ck(all(upper95(k, n) >= k / float(n) for n in (30, 200) for k in (0, 1, 9)),
       "and the bound is never below the measured rate")

    # ---- the band walks DOWN from its top --------------------------------
    ck(band_taus(300)[0] == 300 and band_taus(300)[-1] == 291,
       "a band runs from its top second downward, 300 first")
    ck(band_taus(300) == sorted(band_taus(300), reverse=True),
       "and EARLIEST FIRST -- the entry is the first chance, not the best one")
    ck(max(needed_taus()) == 902 and 302 in needed_taus(),
       "the forecast list reaches tau+lag so a staled decision has something "
       "to read (max %d)" % max(needed_taus()))

    # ---- which side of the book is a NO ----------------------------------
    qs = {"BTC": _q(0.10, 0.14, 30.0, 40.0), "ETH": _q(0.0, 1.0, 0.0, 0.0)}
    off = no_offers(qs)
    ck(off == [("BTC", 0.90, 30.0)],
       "a 10c YES BID is a NO at 90c for 30 contracts -- the BID size, not "
       "the ask (%s)" % off)
    ck(yes_offers(qs) == [("BTC", 0.14, 40.0)],
       "and the same book offers YES at the 14c ask for 40")
    ck(no_offers({"BTC": _q(0.01, 0.03, 50.0, 50.0)}) == [],
       "a 1c bid is a NO at 99c and is REFUSED by the 0.98 ceiling")
    ck(no_offers({"BTC": _q(0.10, 0.14, 0.0, 40.0)}) == [],
       "a price with no bid size is not an offer")
    ck(no_offers({"BTC": _q(0.10, 0.14, 30.0, 40.0, age=31)}) == [],
       "a quote 31 s old is refused at the 30 s cap")
    ck(no_offers({"BTC": _q(0.10, 0.14, 30.0, 40.0, age=31)},
                 max_age=120) != [],
       "and accepted at the loose cap -- which is how 'no quote' is told "
       "apart from 'old quote'")
    ck(no_offers({"BTC": _q(0.0, 1.0, 0.0, 0.0)}) == [],
       "the empty-book print (bid 0, size 0) offers nothing")

    # ---- a planted world where a NO is worth buying ----------------------
    # BTC is hopeless (model 1%), offered as a NO at 90c. ETH wins the race.
    beaten = {"BTC": 0.01, "ETH": 0.50, "SOL": 0.20, "XRP": 0.20, "HYPE": 0.09}
    book = {"BTC": _q(0.10, 0.14, 30.0, 40.0),
            "ETH": _q(0.45, 0.55, 30.0, 30.0)}
    P = {t: beaten for t in needed_taus()}
    Q = {t: book for t in quote_taus()}
    g = [(1000, "ETH", P, Q), (2000, "BTC", P, Q)]
    b = run_band(g, 300, side="no", bar=0.05, cap=CAP)
    ck(len(b) == 2, "two races, two entries -- ONE PER RACE (%d)" % len(b))
    ck(all(x[1] == 300 for x in b),
       "each taken at the earliest second of the band, tau 300")
    ck(all(x[2] == "BTC" and x[3] == "no" and abs(x[4] - 0.90) < 1e-9
           for x in b),
       "and each is a NO on BTC at 90c -- the best edge on the book")
    ck(b[0][6] and not b[1][6],
       "the race ETH wins scores the BTC NO a WIN; the race BTC wins scores "
       "it a LOSS")
    exp_w = 30 * 0.10 - order_fee(30, 0.90)
    exp_l = -30 * 0.90 - order_fee(30, 0.90)
    ck(abs(b[0][7] - exp_w) < 1e-12 and abs(b[1][7] - exp_l) < 1e-12,
       "hand-reconciled: 30 NO at 90c wins $%.2f after fee and loses $%.2f -- "
       "the loss is the full 90c plus the fee, never netted" % (exp_w, exp_l))
    ck(sum(x[7] for x in b) < 0,
       "NULL-ISH: one win and one loss at 90c is NET NEGATIVE ($%.2f). A 90c "
       "NO needs far better than four-in-five" % sum(x[7] for x in b))
    ck(run_band(g, 300, side="no", bar=0.20) == [],
       "NULL: demand 20c of edge and a 9c edge does not qualify")
    ck(run_band(g, 300, side="no", bar=0.05, cap=10)[0][5] == 10,
       "the position cap binds at 10 contracts")
    ck(run_band(g, 5, side="no", bar=0.05) == [],
       "a band the grid holds no quotes for fires nothing")

    # ---- NULL: a fairly priced book must yield nothing -------------------
    flat = {c: 0.2 for c in COINS}
    # every leg bid at 18c -> NO at 82c, worth 80c: negative before fees
    fair_book = {c: _q(0.18, 0.22, 30.0, 30.0) for c in COINS}
    gn = [(1000 + 900 * i, "ETH", {t: flat for t in needed_taus()},
           {t: fair_book for t in quote_taus()}) for i in range(20)]
    ck(run_band(gn, 300, side="no", bar=0.0) == [],
       "NULL: 20 races of a correctly priced book yield NO entries at a zero "
       "edge bar -- the estimator does not manufacture trades")
    ck(run_band(gn, 300, side="yes", bar=0.0) == [],
       "NULL: and none on the YES side either")
    ck(len(run_band(gn, 300, side="no", bar=-0.05)) == 20,
       "while a NEGATIVE bar takes all 20 -- so the null above is the gate "
       "refusing, not the scan failing to see the book")

    # ---- the lag control must bite ---------------------------------------
    # One second wide, so the two columns differ ONLY in which forecast they
    # read: lag 0 reads tau 300, lag 2 reads tau 302.
    Pl = {t: (beaten if t == 300 else flat) for t in needed_taus()}
    only_btc = {t: {"BTC": _q(0.10, 0.14, 30.0, 40.0)} for t in quote_taus()}
    gl = [(1000, "ETH", Pl, only_btc)]
    ck(run_band(gl, 300, width=1, side="no", bar=0.05, lag=0),
       "at lag 0 the fresh forecast (BTC 1%) clears a 5c bar at 90c")
    ck(run_band(gl, 300, width=1, side="no", bar=0.05, lag=2) == [],
       "and the SAME second priced with a 2 s stale forecast (BTC 20%) does "
       "not -- the lag control bites")
    ck(run_band(gl, 298, width=1, side="no", bar=0.05, lag=2)
       and run_band(gl, 298, width=1, side="no", bar=0.05, lag=0) == [],
       "and tau 298 is the mirror image: it fires at lag 2 (which reads the "
       "confident tau-300 forecast) and NOT at lag 0. Lag shifts WHICH "
       "forecast is read; it is not a blanket refusal")

    # ---- pick="edge" and pick="safe" buy DIFFERENT legs ------------------
    # BTC is dead (1%) but already priced at 97c; SOL is live (20%) and cheap.
    two = {"BTC": _q(0.03, 0.05, 50.0, 50.0),        # NO at 97c, worth 99c
           "SOL": _q(0.45, 0.55, 50.0, 50.0),        # NO at 55c, worth 80c
           "ETH": _q(0.45, 0.55, 50.0, 50.0)}        # the model's leader
    Pt = {t: beaten for t in needed_taus()}
    Qt = {t: two for t in quote_taus()}
    gt = [(1000, "ETH", Pt, Qt)]
    be_ = run_band(gt, 300, side="no", bar=0.01, pick="edge")
    bs_ = run_band(gt, 300, side="no", bar=0.01, pick="safe")
    ck(be_ and be_[0][2] == "SOL",
       "pick=edge buys SOL at 55c -- a 24c gap on a leg that might still win")
    ck(bs_ and bs_[0][2] == "BTC",
       "pick=safe buys the DEAD leg, BTC at 97c, for a 1c gap. Two different "
       "contracts at two different prices; running only one answers only "
       "half the question")
    ck(run_band(gt, 300, side="no", bar=0.05, pick="safe")[0][2] == "SOL",
       "and the bar still binds under pick=safe: a 5c bar rules BTC's 1c gap "
       "out and falls to the next-surest leg that clears")
    ck(run_band(gt, 300, side="no", bar=0.30, pick="safe") == [],
       "NULL: a 30c bar clears nothing on this book under either pick")
    ck(run_band(gt, 300, side="no", bar=0.01, pick="edge", floor=0.90)[0][2]
       == "BTC",
       "a 90c price FLOOR -- the rule the live race arms run -- throws the "
       "55c leg out and leaves only the 97c one")
    ck(run_band(gt, 300, side="no", bar=0.01, floor=0.99) == [],
       "NULL: a floor above everything on the book fires nothing")

    # ---- confident_leg: no bar at all ------------------------------------
    cb, sc, bl, un = confident_leg(gt, 300, side="no")
    ck(sc == 1 and len(cb) == 1 and cb[0][2] == "BTC"
       and abs(cb[0][4] - 0.97) < 1e-9,
       "confident_leg buys the model's most beaten leg at 97c with no edge "
       "test at all -- the operator's idea on its own terms")
    cy, _s, _b, _u = confident_leg(gt, 300, side="yes")
    ck(cy and cy[0][2] == "ETH" and abs(cy[0][4] - 0.55) < 1e-9,
       "and on the YES side it buys the model's LEADER, ETH, at the 55c ask")
    dear = {t: {"BTC": _q(0.01, 0.03, 50.0, 50.0)} for t in quote_taus()}
    _cb2, sc2, bl2, un2 = confident_leg([(1000, "ETH", Pt, dear)], 300,
                                        side="no")
    ck(sc2 == 1 and bl2 == 1 and un2 == 0,
       "a most-beaten leg already priced at 99c is counted BLOCKED, not "
       "missing -- 'it is too dear' and 'it is not there' are different "
       "answers to 'is it cheaper early'")
    empty = {t: {"BTC": _q(0.0, 1.0, 0.0, 0.0)} for t in quote_taus()}
    _cb3, sc3, bl3, un3 = confident_leg([(1000, "ETH", Pt, empty)], 300,
                                        side="no")
    ck(sc3 == 1 and bl3 == 0 and un3 == 1,
       "and an empty book on that leg is counted UNQUOTED")

    # ---- the entry is the EARLIEST qualifying second, not the best -------
    Qe = {t: {c: _q(0.0, 1.0, 0.0, 0.0) for c in COINS} for t in quote_taus()}
    Qe[295] = {"BTC": _q(0.10, 0.14, 30.0, 40.0)}          # 90c
    Qe[292] = {"BTC": _q(0.02, 0.06, 99.0, 99.0)}          # 98c, far better $
    ge = [(1000, "ETH", P, Qe)]
    be = run_band(ge, 300, side="no", bar=0.05)
    ck(len(be) == 1 and be[0][1] == 295,
       "with chances at tau 295 and 292 the entry is at 295 -- the EARLIEST, "
       "even though 292 is the bigger position (tau %d)"
       % (be[0][1] if be else -1))

    # ---- persistence ------------------------------------------------------
    def race(pfrom, plater, winner):
        Pp = {PERS_FROM: pfrom}
        for t in PERS_AT:
            Pp[t] = plater
        return (1000, winner, Pp, {})

    low_btc = {"BTC": 0.01, "ETH": 0.50, "SOL": 0.20, "XRP": 0.20,
               "HYPE": 0.09}
    low_xrp = {"BTC": 0.30, "ETH": 0.30, "SOL": 0.20, "XRP": 0.01,
               "HYPE": 0.19}
    gp = [race(low_btc, low_btc, "ETH")] * 4 + [race(low_btc, low_xrp, "BTC")]
    n, sb, sl, seen, nw, yw, cn, cy = persistence(gp)
    ck(n == 5 and all(seen[t] == 5 for t in PERS_AT),
       "five races, all five scored at every later second")
    ck(all(sb[t] == 4 for t in PERS_AT),
       "PLANTED: the most-beaten leg at 300 is still most beaten later in "
       "exactly the 4 races where it was planted to be (%s)"
       % [sb[t] for t in PERS_AT])
    ck(all(sl[t] == 4 for t in PERS_AT),
       "and the leader likewise in 4")
    ck(nw == 4 and yw == 4,
       "the NO on the beaten leg wins the 4 races it did not win; the leader's "
       "YES wins the 4 it led")
    gp2 = [race(low_btc, low_xrp, "ETH")] * 6
    n2, sb2, sl2, seen2, nw2, _yw2, _c, _c2 = persistence(gp2)
    ck(n2 == 6 and all(sb2[t] == 0 for t in PERS_AT),
       "NULL: a world where the verdict NEVER survives reads 0 persistence at "
       "every later second, not a small positive number")
    ck(nw2 == 6,
       "and the NO still wins all 6 -- which is exactly why 80% is the "
       "baseline and 'the NO won' is not evidence of a forecast")

    # ---- scan_ages --------------------------------------------------------
    close = 1_000_000
    rows = [((close - 500) * 1000, "S", "BTC", 0.10, 0.14, 30.0, 40.0),
            ((close - 200) * 1000, "S", "BTC", 0.20, 0.24, 10.0, 10.0),
            ((close + 10) * 1000, "S", "BTC", 0.90, 0.95, 99.0, 99.0)]
    sa = scan_ages(rows, close, [600, 300, 100])
    ck(sa[600] == {}, "before any message there is no book at all")
    ck(sa[300]["BTC"][:4] == (0.10, 0.14, 30.0, 40.0) and sa[300]["BTC"][4] == 200,
       "at tau 300 the last message is the one from tau 500, carried forward "
       "with an age of 200 s")
    ck(sa[100]["BTC"][:4] == (0.20, 0.24, 10.0, 10.0),
       "at tau 100 the newer message has replaced it")
    ck(all(v["BTC"][0] != 0.90 for v in sa.values() if "BTC" in v),
       "NO LOOK-AHEAD: a message stamped AFTER the close is never read")

    # ---- the grid round-trips --------------------------------------------
    import tempfile
    fd, tp = tempfile.mkstemp(suffix=".jsonl.gz")
    os.close(fd)
    try:
        save_grid(g, tp)
        back = load_grid(tp)
        ck(run_band(back, 300, side="no", bar=0.05)
           == run_band(g, 300, side="no", bar=0.05),
           "the priced grid round-trips through disk to identical decisions")
    finally:
        os.remove(tp)

    print("racenoearly selftest:", "OK" if ok else "FAILED")
    return ok


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=racebook.DATA)
    ap.add_argument("--hours", type=int, default=600)
    ap.add_argument("--ruler", default="3600")
    ap.add_argument("--kappa", type=float, default=1.0)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if not selftest():
        return 1
    if a.selftest:
        return 0

    os.makedirs(GRIDDIR, exist_ok=True)
    gp = os.path.join(GRIDDIR, "grid_%s_%.2f_%d_w%d.jsonl.gz"
                      % (a.ruler, a.kappa, a.hours, BAND_W))
    if os.path.exists(gp) and not a.rebuild:
        print("\nreusing the priced grid at %s" % gp)
        grid = load_grid(gp)
    else:
        files = sorted(glob.glob(os.path.join(a.data, "ticker", "*.jsonl.gz")))
        if a.hours:
            files = files[-a.hours:]
        if not files:
            print("loaded nothing -- no ticker files under %s" % a.data)
            return 0
        cand, got = racebook.parse_rate(files)
        print("\n%d ticker hour files; parser check %d/%d lines"
              % (len(files), got, cand))
        if cand and got < 0.95 * cand:
            print("REFUSING TO REPORT -- the ticker wire format no longer "
                  "matches the parser. Fix racebook._fields() first.")
            return 1
        by_race = collections.defaultdict(list)
        for k, fp in enumerate(files):
            for r in racebook.cached_hour(fp):
                by_race[r[1]].append(r)
            if (k + 1) % 150 == 0:
                print("  ... %d/%d files read" % (k + 1, len(files)),
                      flush=True)
        races = []
        for stamp, rows in by_race.items():
            c = racebook.close_of(stamp)
            if c is None or len({r[2] for r in rows}) < len(COINS):
                continue
            races.append((c, stamp, rows))
        races.sort()
        del by_race
        print("  %d races with all five legs quoting" % len(races))
        import idxload
        import pinracefair as F
        import pinracemodel as M
        idx = idxload.load(sorted(set(M.COINS.values())), verbose=False)
        if not idx or idx.get("BRTI") is None:
            print("loaded nothing -- no index on disk")
            return 0
        D = idx["BRTI"]
        races = [r for r in races
                 if r[0] - 4700 >= D.base and r[0] <= D.base + D.n]
        print("  %d of those have an hour of index history behind them"
              % len(races))
        grid = build_grid(races, M, F, idx, ruler=a.ruler, kappa=a.kappa,
                          progress=True)
        del races, idx
        save_grid(grid, gp)
        print("  grid saved: %s" % gp)

    if len(grid) < 30:
        print("loaded nothing -- only %d priced races, below the 30-cluster "
              "floor" % len(grid))
        return 0
    grid.sort()
    days = (grid[-1][0] - grid[0][0]) / 86400.0
    print("\n%d priced races over %.1f days, %s .. %s (UTC)"
          % (len(grid), days,
             utcstamp(grid[0][0]).strftime("%m-%d %H:%M"),
             utcstamp(grid[-1][0]).strftime("%m-%d %H:%M")))
    print("Every race is one cluster. n is races, never trades.")

    # ================================================================== 1
    print("\n## 1. IS THERE A NO TO BUY AT ALL?")
    print("At each second, how many races had a YES BID of 2c or more (a NO at")
    print("0.98 or below) on at least one leg -- and how cheap and how big.")
    print("A strategy with no supply is not a strategy.")
    print("  %5s %6s | %s | %s"
          % ("", "", "fresh quotes (age<=%ds)" % MAXAGE,
             "stale allowed (age<=%ds)" % LOOSE_AGE))
    print("  %5s %6s %7s %7s %7s %6s %6s  %7s %7s %7s %6s %6s"
          % ("tau", "market", "races", "%", "cheap", "size", "legs",
             "races", "%", "cheap", "size", "legs"))
    for tau in TAUS:
        cells = []
        quoting = 0
        n = 0
        for _c, _w, _P, Q in grid:
            q = Q.get(tau)
            if q is None:
                continue
            n += 1
            if q:
                quoting += 1
        for age in (MAXAGE, LOOSE_AGE):
            have = 0
            cheap, size, legs = [], [], []
            for _c, _w, _P, Q in grid:
                q = Q.get(tau)
                if q is None:
                    continue
                off = no_offers(q, max_age=age)
                if off:
                    have += 1
                    best = min(off, key=lambda o: o[1])
                    cheap.append(best[1])
                    size.append(best[2])
                    legs.append(len(off))
            cells.append((have, cheap, size, legs))
        row = "  %5d %5.0f%%" % (tau, 100.0 * quoting / n if n else 0.0)
        for have, cheap, size, legs in cells:
            row += (" %7d %6.1f%% %6.0fc %6.0f %6.1f"
                    % (have, 100.0 * have / n if n else 0.0,
                       100 * pct(cheap, 0.5) if cheap else float("nan"),
                       pct(size, 0.5) if size else float("nan"),
                       (sum(legs) / len(legs)) if legs else float("nan")))
        print(row)
    print("  'market' is the share of races where the five legs had EVER")
    print("  quoted by that second -- a 0 there means the market is not open")
    print("  yet, not that nobody wants an early NO. 'cheap' is the median")
    print("  across races of the CHEAPEST buyable NO, 'size' the yes-bid size")
    print("  at that leg, 'legs' how many of the five were buyable at once.")
    print("\n  DO NOT READ 'cheap' AS 'what a good NO costs'. The cheapest NO")
    print("  in a race is the one on the leg most likely to WIN -- a 5c NO is")
    print("  a NO on the favourite, which is the worst contract on the board,")
    print("  not the bargain it looks like. The price of a NO on a BEATEN leg")
    print("  is the 'paid' column of section 2c, and it runs 93c-98c.")

    # ================================================================== 2
    print("\n## 2. BUYING THE NO THE MODEL LIKES, ONE ENTRY PER RACE PER BAND")
    print("Band top T covers seconds T..T-%d; the entry is the EARLIEST second"
          % (BAND_W - 1))
    print("whose best NO clears the edge bar. Cap %d contracts. Fees charged."
          % CAP)
    for lag in (0, LAG):
        print("\n--- LAG %d %s" % (lag, "(forecast built at the same second -- "
                                   "CONTAMINATED, shown for contrast)" if lag == 0
                                   else "(forecast staled %d s -- THIS IS THE "
                                   "HONEST COLUMN)" % LAG))
        print(HEAD)
        for bar in (0.02, 0.05):
            for top in TAUS:
                line(run_band(grid, top, side="no", bar=bar, lag=lag),
                     "tau %3d-%3d, edge>=%.0fc"
                     % (top - BAND_W + 1, top, 100 * bar), days)
            print("  %s" % ("-" * 100))

    # ================================================================== 2b
    print("\n## 2b. THE EDGE BAR SWEPT, at the far bands (lag %d)" % LAG)
    print(HEAD)
    for top in (880, 750, 600, 450, 300):
        for bar in BARS:
            line(run_band(grid, top, side="no", bar=bar, lag=LAG),
                 "tau %3d, edge>=%.0fc" % (top, 100 * bar), days)
        print("  %s" % ("-" * 100))

    # ================================================================== 2c
    print("\n## 2c. BUY THE DEADEST LEG, NOT THE BIGGEST GAP (lag %d)" % LAG)
    print("Section 2 buys the biggest gap between model and price, which on")
    print("this product reaches for the MARGINAL leg -- the dead leg is")
    print("already priced at 97c and offers no gap. The operator's proposal is")
    print("the other one: name the deadest leg and buy it. No edge bar at all.")
    print("  %5s %6s %7s %8s %6s %5s %5s %5s %6s %9s %8s"
          % ("tau", "races", "blocked", "unquoted", "bought", "lost", "<=95%",
             "need%", "paid", "c/contract", "$/day"))
    for tau in TAUS:
        bets, sc, bl, un = confident_leg(grid, tau, side="no", lag=LAG)
        if not sc:
            continue
        if not bets:
            print("  %5d %6d %7d %8d %6d" % (tau, sc, bl, un, 0))
            continue
        cts = sum(b[5] for b in bets)
        pnl = sum(b[7] for b in bets)
        bad = sum(1 for b in bets if not b[6])
        paid = sum(b[4] * b[5] for b in bets) / cts
        print("  %5d %6d %7d %8d %6d %5d %4.1f%% %4.1f%% %5.1fc %+8.2fc %+8.2f"
              % (tau, sc, bl, un, len(bets), bad,
                 100.0 * upper95(bad, len(bets)), 100.0 * breakeven(paid),
                 100 * paid, 100 * pnl / cts, pnl / days if days else 0.0))
    print("  'blocked' = the deadest leg was already dearer than %.2f, so"
          % PRICE_CEIL)
    print("  there was nothing cheap to buy. THAT COLUMN IS THE ANSWER TO")
    print("  'is it cheaper early': if it falls as tau grows, early is cheaper.")
    print("  'unquoted' = no usable quote on that leg at that second.")

    print("\n  ... and the same thing on the YES side, for contrast:")
    print("  %5s %6s %7s %8s %6s %5s %5s %5s %6s %9s %8s"
          % ("tau", "races", "blocked", "unquoted", "bought", "lost", "<=95%",
             "need%", "paid", "c/contract", "$/day"))
    for tau in TAUS:
        bets, sc, bl, un = confident_leg(grid, tau, side="yes", lag=LAG)
        if not sc:
            continue
        if not bets:
            print("  %5d %6d %7d %8d %6d" % (tau, sc, bl, un, 0))
            continue
        cts = sum(b[5] for b in bets)
        pnl = sum(b[7] for b in bets)
        bad = sum(1 for b in bets if not b[6])
        paid = sum(b[4] * b[5] for b in bets) / cts
        print("  %5d %6d %7d %8d %6d %5d %4.1f%% %4.1f%% %5.1fc %+8.2fc %+8.2f"
              % (tau, sc, bl, un, len(bets), bad,
                 100.0 * upper95(bad, len(bets)), 100.0 * breakeven(paid),
                 100 * paid, 100 * pnl / cts, pnl / days if days else 0.0))

    print("\n  AND AT LAG 0, the deadest-leg NO, for the staleness contrast:")
    print("  %5s %6s %7s %8s %6s %5s %5s %5s %6s %9s %8s"
          % ("tau", "races", "blocked", "unquoted", "bought", "lost", "<=95%",
             "need%", "paid", "c/contract", "$/day"))
    for tau in TAUS:
        bets, sc, bl, un = confident_leg(grid, tau, side="no", lag=0)
        if not sc or not bets:
            continue
        cts = sum(b[5] for b in bets)
        pnl = sum(b[7] for b in bets)
        bad = sum(1 for b in bets if not b[6])
        paid = sum(b[4] * b[5] for b in bets) / cts
        print("  %5d %6d %7d %8d %6d %5d %4.1f%% %4.1f%% %5.1fc %+8.2fc %+8.2f"
              % (tau, sc, bl, un, len(bets), bad,
                 100.0 * upper95(bad, len(bets)), 100.0 * breakeven(paid),
                 100 * paid, 100 * pnl / cts, pnl / days if days else 0.0))

    # ================================================================== 2d
    print("\n## 2d. THE SAME BANDS UNDER pick=safe (surest leg clearing the "
          "bar, lag %d)" % LAG)
    print(HEAD)
    for bar in (0.02, 0.05):
        for top in TAUS:
            line(run_band(grid, top, side="no", bar=bar, lag=LAG, pick="safe"),
                 "tau %3d-%3d, edge>=%.0fc"
                 % (top - BAND_W + 1, top, 100 * bar), days)
        print("  %s" % ("-" * 100))

    # ================================================================== 3
    print("\n## 3. THE HEADLINE: EARLY NO vs LATE NO vs LATE YES")
    print("Same grid, same one-entry-per-race rule, same 2c bar, same cap.")
    print("The last four rows carry the 90c price floor the running race paper")
    print("arms use, so 'early' is compared against a rule somebody runs.")
    for lag in (0, LAG):
        print("\n--- LAG %d" % lag)
        print(HEAD)
        for label, top, side, fl in (
                ("EARLY NO  tau 871-880", 880, "no", 0.0),
                ("EARLY NO  tau 741-750", 750, "no", 0.0),
                ("EARLY NO  tau 591-600", 600, "no", 0.0),
                ("EARLY NO  tau 291-300", 300, "no", 0.0),
                ("MID   NO  tau 111-120", 120, "no", 0.0),
                ("LATE  NO  tau  51- 60", 60, "no", 0.0),
                ("LATE  NO  tau  21- 30", 30, "no", 0.0),
                ("LATE  NO  tau  11- 20", 20, "no", 0.0),
                ("LATE  YES tau  21- 30", 30, "yes", 0.0),
                ("LATE  YES tau  11- 20", 20, "yes", 0.0),
                ("ARM  NO  21-30 >=90c", 30, "no", 0.90),
                ("ARM  YES 21-30 >=90c", 30, "yes", 0.90),
                ("ARM-ish NO 291-300 >=90c", 300, "no", 0.90),
                ("ARM-ish NO 591-600 >=90c", 600, "no", 0.90)):
            line(run_band(grid, top, side=side, bar=0.02, lag=lag, floor=fl),
                 label, days)
    print("\n  A rule that gains at lag 0 and loses at lag 2 was never a rule.")

    # ================================================================== 4
    print("\n## 4. DOES A NO HOLD ITS VALUE LONGER THAN A YES?")
    n, sb, sl, seen, nw, yw, cn, cy = persistence(grid)
    print("Take the model's most-beaten leg at tau %d and its leader at tau %d."
          % (PERS_FROM, PERS_FROM))
    print("How often is each still the same leg later, and how often does the")
    print("bet actually pay? %d races." % n)
    if n < 30:
        print("  UNDER THE 30-CLUSTER FLOOR -- nothing below is significant.")
    print("  %-34s %8s %8s" % ("", "most beaten", "leader"))
    print("  %-34s %7.1f%% %7.1f%%"
          % ("model's own claim at tau %d" % PERS_FROM,
             100 * (sum(cn) / len(cn)) if cn else float("nan"),
             100 * (sum(cy) / len(cy)) if cy else float("nan")))
    for t in PERS_AT:
        s = seen[t] or 1
        print("  %-34s %7.1f%% %7.1f%%"
              % ("still the same leg at tau %d" % t,
                 100.0 * sb[t] / s, 100.0 * sl[t] / s))
    print("  %-34s %7.1f%% %7.1f%%"
          % ("the bet pays (settled)", 100.0 * nw / n if n else 0.0,
             100.0 * yw / n if n else 0.0))
    print("  %-34s %7.1f%% %7.1f%%" % ("BASELINE, no forecast at all", 80.0, 20.0))
    print("\n  READ THE LAST TWO ROWS TOGETHER. Four legs in five lose whatever")
    print("  anyone forecasts, so a NO that pays 80% of the time has shown")
    print("  NOTHING. What the forecast is worth is the gap between the two")
    print("  rows, and the same gap on the YES side is against a 20% baseline.")

    # ================================================================== 5
    print("\n## 5. WHAT THE EARLY NO ACTUALLY BUYS (tau 291-300, 2c bar, lag %d)"
          % LAG)
    best = run_band(grid, 300, side="no", bar=0.02, lag=LAG)
    if not best:
        print("  nothing fires at that band and bar.")
    else:
        print("  %-14s %7s %7s %9s %10s" % ("price paid", "races", "lost",
                                            "contracts", "$"))
        for lo, hi in ((0.0, 0.50), (0.50, 0.70), (0.70, 0.85), (0.85, 0.93),
                       (0.93, 0.99)):
            s = [b for b in best if lo <= b[4] < hi]
            if not s:
                continue
            print("  %-14s %7d %7d %9.0f %+10.2f"
                  % ("%.0f-%.0fc" % (100 * lo, 100 * hi), len(s),
                     sum(1 for b in s if not b[6]), sum(b[5] for b in s),
                     sum(b[7] for b in s)))
        bad = [b for b in best if not b[6]]
        print("\n  EVERY LOSS: %d of %d races" % (len(bad), len(best)))
        for b in sorted(bad, key=lambda x: x[7])[:20]:
            print("    %s tau %3d  NO %-4s at %.0fc x %3.0f  edge %+.1fc  $%.2f"
                  % (utcstamp(b[0]).strftime("%m-%d %H:%MZ"),
                     b[1], b[2], 100 * b[4], b[5], b[8], b[7]))

    print("\nCEILING, NOT A FILL RATE, AND NEVER OUR LOSS RATE. Every entry here")
    print("lifts an offer that was resting in the book. Whether it would be")
    print("ours, and whether the ones we win are the bad ones, only live or")
    print("paper fills can say.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
