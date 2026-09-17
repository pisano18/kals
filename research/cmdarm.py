#!/usr/bin/env python3
r"""cmdarm.py -- THE COMMODITIES PAPER ARM. Nothing is ever ordered.

THE OPERATOR, 2026-09-17: "Most important thing right now is figuring out the
commodities method. Prioritize that."

WHAT THE METHOD TURNED OUT TO BE, AND WHY IT IS NOT WHAT I EXPECTED

I assumed we would need a Pyth price feed and a distance-to-strike model, the
way the crypto bot needs the settlement index. Three findings changed that:

  1. THE SETTLEMENT RULE, from Kalshi's own market metadata (verbatim):
     "If the close price of the 1-minute candlestick for Gold ... at 9:45 AM
     EDT is at least the close price of the 1-minute Pyth GOLD candlestick at
     9:30 AM EDT ... then the market resolves to Yes."
     So: settle = the close of the 1-minute Pyth candle AT the close, and the
     strike = the same thing one 15-minute window earlier. Verified: the strike
     equalled the previous settlement on 38 of 39 consecutive gold closes.
     Unlike our crypto markets NOTHING is locked in early -- it is one price at
     one instant, not a 60-second average. That is why the original kill said
     the pin edge does not exist here, and that part was right.

  2. WE CANNOT SEE THAT PRICE. Pyth's hermes and benchmarks APIs now answer
     401 without a key (and their TLS chain needs certifi, not the system
     store). Kalshi's own `pyth_value` websocket channel accepts a
     subscription for GOLD/SILVER/COPPER/WTI/NATGAS and then publishes
     NOTHING -- and nothing for BTC/ETH either, which was the control, so the
     channel is simply not serving us rather than the commodity side being
     special.

  3. WE DO NOT NEED IT. The tape says the MARKET'S OWN PRICE already identifies
     the near-certainties, and underprices them. Every taker buy at 90-98c in
     the last 30 s of 300 settled markets per series, scored on the settlement
     (a TAPE population -- rule 5 -- this is what the market did, never our
     loss rate):

        series   band      trades   bought the LOSING side   EV per contract
        GOLD     0-5 s      1,547            0.13%               +3.72c
        GOLD     6-15 s     2,893            2.45%               +2.22c
        GOLD     16-30 s    3,615            7.69%               -2.82c
        WTI      16-30 s    2,596            1.04%               +3.82c
        WTI      6-15 s     1,975            2.03%               +1.92c
        WTI      0-5 s      1,160            1.64%               +2.00c
        SILVER   0-5 s      1,089            2.85%               +1.16c
        COPPER, NATGAS: 5.7-11.3% at every horizon -- dead.

     Break-even at 95c is about 5%. Our crypto bot keeps ~3c a contract, so
     WTI at 16-30 s (+3.82c) is better than the business we already run, and
     at the horizon our machinery already trades.

SO THE RULE THIS ARM TESTS IS DELIBERATELY STUPID, AND THAT IS THE POINT:
buy whatever the book offers at 90-98c inside a series' own good time band.
No model, no feed. If that survives contact with real fills it is a second
product; if it does not, we have lost a day and not a dollar.

THE ONE THING THIS ARM CANNOT SEE, STATED BEFORE ANY NUMBER IT PRINTS

Rule 5 and the 31x. The tape's population is "a trade happened at 90-98c".
Ours would be "we took a resting offer". On the crypto markets those differed
by 31x (tape 0.11% loss, live 3.4%) because the offer that reaches us is the
one somebody chose to sell. Gold at 0.13% could be 4% live, which is
break-even. THIS ARM ASSUMES ITS FILLS. It measures availability, price, band
and settlement -- never our loss rate. A live penny test is the only thing
that can answer the fill question, and it needs operator sign-off per the
standing rule.

    python research/cmdarm.py --selftest
    python research/cmdarm.py --minutes 1440
"""
import argparse
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# IMPORT ORDER MATTERS AND IT BIT ME. kals-work holds SCRATCH copies of several
# repo modules, including an old `livebook.py` that runs a Coin Race liquidity
# analysis at import time. Putting that directory on the path FIRST silently
# shadowed research/livebook.py -- the arm would have traded on a different
# book implementation than the one it was written against, and the only visible
# symptom was an unrelated table printed during the self-test. So: repo modules
# are imported FIRST, and kals-work goes on the path only afterwards and only
# for `kauth`, which lives nowhere else. pinrun.py has this same ordering for
# the same reason.
import livebook                                                  # noqa: E402
import pinflat                                                   # noqa: E402
sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")

RESULTS = os.path.join(os.path.dirname(HERE), "results")

# series -> (tau_lo, tau_hi) the tape says is worth buying. GOLD dies at 16-30s
# (7.69% lost) so its window stops at 15; WTI is good at every horizon and is
# given the widest. SILVER is marginal and included ONLY to keep a losing arm
# in the sample -- if it prints worse than gold and WTI live, that is evidence
# the whole thing is real rather than a fluke of two series.
BANDS = {
    "KXGOLD15M":   (2, 15),
    "KXWTI15M":    (2, 30),
    "KXSILVER15M": (2, 5),
}
PRICE_LO = 0.90
PRICE_HI = 0.98
MAX_BOOK_AGE_MS = 2500
SIZE = 100.0                  # contracts per paper bet, fixed: this arm is
                              # about whether the edge exists, not sizing
MAX_PER_CLOSE = 1             # one paper bet per market per close


def decide(best, tau, band, price_lo=PRICE_LO, price_hi=PRICE_HI,
           max_age=MAX_BOOK_AGE_MS):
    """(want, price, size) to buy, or None.

    The rule: inside the series' time band, if either side's ASK sits in the
    price window, buy that side. At most one side can qualify, because the two
    asks sum to about 100c -- so there is never a choice to get wrong.
    """
    if not best or best.get("suspect"):
        return None
    age = best.get("age_ms")
    if age is None or age > max_age:
        return None
    if not (band[0] <= tau <= band[1]):
        return None
    for want in ("yes", "no"):
        px = best.get("%s_ask" % want)
        sz = best.get("%s_ask_size" % want)
        if px is None or sz is None or sz <= 0:
            continue
        if price_lo <= px <= price_hi:
            return want, float(px), float(sz)
    return None


def fee_per_contract(p):
    """Kalshi's taker fee, the same quadratic the crypto bot pays."""
    return 0.07 * p * (1.0 - p)


def score(bets, outcomes):
    """Attach settlement to each paper bet. `outcomes[ticker]` is 1.0 for YES."""
    out = []
    for b in bets:
        r = outcomes.get(b["ticker"])
        if r is None:
            continue
        won = (b["want"] == "yes" and r >= 0.5) or (b["want"] == "no" and r < 0.5)
        gross = (1.0 - b["price"]) if won else -b["price"]
        out.append(dict(b, won=won,
                        pnl=(gross - fee_per_contract(b["price"])) * b["n"]))
    return out


def summarise(scored):
    by = collections.defaultdict(lambda: {"n": 0, "lost": 0, "pnl": 0.0,
                                          "contracts": 0.0, "px": []})
    for s in scored:
        d = by[s["series"]]
        d["n"] += 1
        d["lost"] += (not s["won"])
        d["pnl"] += s["pnl"]
        d["contracts"] += s["n"]
        d["px"].append(s["price"])
    return by


def report(by, out=sys.stdout):
    p = lambda s: print(s, file=out)                              # noqa: E731
    p("  series       bets  lost   lost%   contracts        paper $   c/contract   mean price")
    tot = collections.Counter()
    for ser in sorted(by):
        d = by[ser]
        if not d["n"]:
            continue
        p("  %-11s %5d %5d %6.2f%% %11.0f %14.2f %12.2f %11.1fc" % (
            ser, d["n"], d["lost"], 100 * d["lost"] / d["n"], d["contracts"],
            d["pnl"], 100 * d["pnl"] / max(1e-9, d["contracts"]),
            100 * sum(d["px"]) / len(d["px"])))
        tot["n"] += d["n"]
        tot["lost"] += d["lost"]
    p("  PAPER FILLS ARE ASSUMED. This is availability and settlement, never")
    p("  our loss rate (rule 5): the offer that reaches us is the one somebody")
    p("  chose to sell, and on the crypto markets that gap was 31x.")


# ---------------------------------------------------------------------------
def open_markets(series):
    """Open markets closing within the next 15 minutes, via the same REST
    helper the rest of the project uses."""
    from kauth import get
    out = {}
    now = time.time()
    for s in series:
        try:
            st, d = get("/markets?series_ticker=%s&status=open&limit=200" % s)
        except Exception:                                         # noqa: BLE001
            continue
        if st != 200 or not isinstance(d, dict):
            continue
        for m in d.get("markets", []):
            tk = m.get("ticker")
            c = pinflat.close_epoch(tk) if tk else None
            if c and 0 < c - now <= 900:
                out[tk] = c
    return out


def settlements(tickers):
    from kauth import get
    out = {}
    for tk in tickers:
        try:
            st, d = get("/markets/%s" % tk)
        except Exception:                                         # noqa: BLE001
            continue
        if st != 200 or not isinstance(d, dict):
            continue
        m = d.get("market") or {}
        r = m.get("result")
        if isinstance(r, str) and r.strip().lower() in ("yes", "no"):
            out[tk] = 1.0 if r.strip().lower() == "yes" else 0.0
    return out


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("cmdarm selftest: FAILED -- " + msg)

    def book(yes_ask=None, no_ask=None, age=100, suspect=False, size=50.0):
        return {"yes_ask": yes_ask, "yes_ask_size": size if yes_ask else None,
                "no_ask": no_ask, "no_ask_size": size if no_ask else None,
                "age_ms": age, "suspect": suspect}

    band = (2, 15)
    ck(decide(book(yes_ask=0.95), 10, band) == ("yes", 0.95, 50.0),
       "a YES ask at 95c inside the band is the bet")
    ck(decide(book(no_ask=0.93), 10, band) == ("no", 0.93, 50.0),
       "so is a NO ask at 93c -- the side is whichever one is expensive")
    ck(decide(book(yes_ask=0.99), 10, band) is None,
       "NULL: 99c is above the window; the win no longer pays for the fee")
    ck(decide(book(yes_ask=0.80), 10, band) is None,
       "NULL: 80c is below the window -- not a near-certainty")
    ck(decide(book(yes_ask=0.95), 20, band) is None,
       "NULL: 20 s is outside GOLD's band, where the tape loses 7.69%")
    ck(decide(book(yes_ask=0.95), 1, band) is None,
       "NULL: 1 s left is inside nothing -- an order could land after the close")
    ck(decide(book(yes_ask=0.95), 20, (2, 30)) == ("yes", 0.95, 50.0),
       "...but 20 s IS inside WTI's band, which the tape says is its best")
    ck(decide(book(yes_ask=0.95, age=9000), 10, band) is None,
       "NULL: a stale book is refused, not traded on")
    ck(decide(book(yes_ask=0.95, suspect=True), 10, band) is None,
       "NULL: a book flagged suspect after a reconnect is refused")
    ck(decide(None, 10, band) is None and decide({}, 10, band) is None,
       "NULL: no book at all is not a signal")
    ck(decide(book(yes_ask=0.95, size=0.0), 10, band) is None,
       "NULL: a price with nothing behind it is not an offer")
    # both asks quoted: only one can be in the window, and it must be picked
    b = book(yes_ask=0.95); b["no_ask"] = 0.05; b["no_ask_size"] = 50.0
    ck(decide(b, 10, band) == ("yes", 0.95, 50.0),
       "with both sides quoted the expensive one is the near-certainty")

    ck(abs(fee_per_contract(0.95) - 0.07 * 0.95 * 0.05) < 1e-12,
       "the fee is Kalshi's quadratic, not a guess")

    bets = [{"ticker": "KXGOLD15M-26SEP170945-45", "series": "KXGOLD15M",
             "want": "yes", "price": 0.95, "n": 100.0, "tau": 10},
            {"ticker": "KXWTI15M-26SEP170945-45", "series": "KXWTI15M",
             "want": "no", "price": 0.96, "n": 100.0, "tau": 25}]
    sc = score(bets, {"KXGOLD15M-26SEP170945-45": 1.0,
                      "KXWTI15M-26SEP170945-45": 1.0})
    ck(len(sc) == 2 and sc[0]["won"] and not sc[1]["won"],
       "settlement YES: the YES bet won and the NO bet lost")
    ck(abs(sc[0]["pnl"] - (0.05 - fee_per_contract(0.95)) * 100) < 1e-9,
       "a win pays (1 - price) minus the fee, times the contracts")
    ck(abs(sc[1]["pnl"] - (-0.96 - fee_per_contract(0.96)) * 100) < 1e-9,
       "a loss costs the whole price, plus the fee")
    ck(score(bets, {}) == [], "NULL: no settlement on file scores nothing, "
                              "rather than assuming a win")
    by = summarise(sc)
    ck(by["KXGOLD15M"]["n"] == 1 and by["KXWTI15M"]["lost"] == 1,
       "the summary splits by series, which is the whole comparison")
    ck(not summarise([]), "NULL: nothing scored -> nothing reported")

    # the bands are the tape's, and GOLD's stops before the band it loses in
    ck(BANDS["KXGOLD15M"][1] == 15 and BANDS["KXWTI15M"][1] == 30,
       "GOLD's window stops at 15 s (16-30 s lost 7.69% on the tape); WTI's "
       "runs to 30 s (1.04% there, its best band)")
    ck(PRICE_HI == 0.98,
       "the price window tops out at the same 98c ceiling the live bot uses")
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.index("def selftest(")]
    for bad in ("pintake", "ordercli", "post_only", "/portfolio/orders"):
        ck(bad not in body,
           "PAPER ONLY: %r appears nowhere in the working code" % bad)
    ck(livebook.__file__.lower().startswith(HERE.lower()),
       "the REPO's livebook is loaded, not the scratch copy in kals-work that "
       "shadows it and runs an analysis on import (currently %s)" % livebook.__file__)
    ck(body.index("import livebook") < body.index('sys.path.append(r"C:\\Users'),
       "and the repo path is searched BEFORE kals-work is added, which is what "
       "keeps it that way")
    print("cmdarm selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=float, default=1440)
    ap.add_argument("--series", nargs="*", default=sorted(BANDS))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()

    log = a.out or os.path.join(
        RESULTS, "cmdarm-%s.jsonl" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    fh = open(log, "a", encoding="utf-8", buffering=1)

    def rec(kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fh.write(json.dumps(kw) + "\n")

    rec("start", series=a.series, bands={k: list(v) for k, v in BANDS.items()},
        price_lo=PRICE_LO, price_hi=PRICE_HI, size=SIZE, mode="paper")
    print("cmdarm PAPER -- %s | bands %s | %.0f-%.0fc | log %s"
          % (", ".join(a.series), {k: BANDS[k] for k in a.series},
             100 * PRICE_LO, 100 * PRICE_HI, os.path.basename(log)), flush=True)

    book = livebook.LiveBook().start()
    watching = {}
    bets = []
    per_close = collections.Counter()
    pending = {}
    looks = {}
    looked = set()
    end = time.time() + a.minutes * 60
    last_disc = 0.0
    while time.time() < end:
        now = time.time()
        if now - last_disc > 30:
            last_disc = now
            try:
                fresh = open_markets(a.series)
            except Exception as e:                                # noqa: BLE001
                rec("error", where="discover", err=str(e)[:200])
                fresh = {}
            new = [t for t in fresh if t not in watching]
            if new:
                book.subscribe(sorted(new))
                rec("watch", added=sorted(new), n=len(fresh))
            gone = [t for t in watching if t not in fresh]
            for t in gone:
                watching.pop(t, None)
                pending[t] = time.time()
                looks.pop(t, None)
                looked.discard(t)
            watching.update(fresh)

        for tk, close_s in list(watching.items()):
            tau = int(close_s - time.time())
            ser = tk.split("-")[0]
            try:
                best = book.best(tk)
            except Exception:                                     # noqa: BLE001
                continue
            # ---- WHAT THE BOOK SHOWED, whether or not we bet. One record per
            # market per close, written when the band closes: the cheapest ask
            # on each side seen INSIDE the band and the tau it was seen at. So
            # "why no bet on that close" is answerable from the log instead of
            # guessed -- three closes passed with one bet before this existed.
            lo, hi = BANDS.get(ser, (2, 15))
            lk = looks.setdefault(tk, {"ser": ser, "close": close_s, "yes": None, "no": None,
                                       "looks": 0, "fresh": 0})
            if best and lo <= tau <= hi:
                lk["looks"] += 1
                if best.get("age_ms") is not None and best["age_ms"] <= MAX_BOOK_AGE_MS:
                    lk["fresh"] += 1
                for want in ("yes", "no"):
                    px = best.get("%s_ask" % want)
                    sz = best.get("%s_ask_size" % want)
                    if px is not None and sz:
                        cur = lk[want]
                        if cur is None or px < cur[0]:
                            lk[want] = (float(px), float(sz), tau)
            if tau < lo and tk not in looked:
                looked.add(tk)
                rec("look", ticker=tk, series=ser, looks=lk["looks"], fresh=lk["fresh"],
                    yes_ask=lk["yes"], no_ask=lk["no"], bet=per_close[tk] > 0)
            if per_close[tk] >= MAX_PER_CLOSE:
                continue
            d = decide(best, tau, BANDS.get(ser, (2, 15)))
            if not d:
                continue
            want, px, sz = d
            n = min(SIZE, sz)
            per_close[tk] += 1
            bet = {"ticker": tk, "series": ser, "want": want, "price": px,
                   "n": n, "tau": tau, "offer": sz,
                   "age_ms": best.get("age_ms")}
            bets.append(bet)
            rec("bet", **bet)
            print("  BET %s tau=%2ds %s @%.4f  offer %.0f  taking %.0f"
                  % (tk, tau, want.upper(), px, sz, n), flush=True)

        # settle anything whose close passed at least 90 s ago
        due = [t for t, when in pending.items() if time.time() - when > 90]
        if due:
            try:
                got = settlements(due)
            except Exception as e:                                # noqa: BLE001
                got = {}
                rec("error", where="settle", err=str(e)[:200])
            for t in due:
                if t in got:
                    pending.pop(t, None)
                    mine = [b for b in bets if b["ticker"] == t and "won" not in b]
                    for s in score(mine, got):
                        for b in bets:
                            if b is mine[0] or b["ticker"] == t:
                                b.update(won=s["won"], pnl=s["pnl"])
                        rec("settled", ticker=t, result=got[t], won=s["won"],
                            pnl_c=round(100 * s["pnl"], 2))
                        print("  SETTLED %s %s -> %s  $%+.2f"
                              % (t, "yes" if got[t] >= 0.5 else "no",
                                 "WON" if s["won"] else "LOST", s["pnl"]), flush=True)
                elif time.time() - pending[t] > 1800:
                    pending.pop(t, None)
            done = [b for b in bets if "won" in b]
            if done:
                report(summarise(done))
        time.sleep(0.4)

    rec("end", bets=len(bets))
    done = [b for b in bets if "won" in b]
    if done:
        report(summarise(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
