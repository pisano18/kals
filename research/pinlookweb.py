"""pinlookweb.py -- turn a pinlook day into something a human can actually browse.

`pinlook.py` writes 14 MB of joined truth per day. That is the right thing to
keep and the wrong thing to read. This compacts a day to the few fields that
answer the operator's question -- *"what price it was at each second from 30 all
the way down, what the order book looked like ... and then something showing
your decision and why"* -- and emits one JSON per day for the browser page.

THREE NUMBERS PER SECOND, and the third is the one that matters:

  index       what the coin printed that second
  projection  where settlement lands IF THE PRICE FREEZES RIGHT NOW

Settlement is the mean of sixty one-second prints, so with `tau` seconds left,
`60 - tau` of them are already on disk and cannot move. The projection is
`(locked_sum + tau * spot) / 60`. It is not a forecast -- it is the arithmetic
the bot is doing, and it is why a market can sit at 3c with 43 seconds left and
still win: the locked half was already on the other side of the strike.

Both are written as a DISTANCE FROM THE STRIKE, because the absolute level of
Bitcoin is six digits of noise around the one digit that decides the contract.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")


def load_strikes(markets_json=r"C:\kals\fulltape\markets.json"):
    """{ticker: (strike, settle)} from EVERY settlement directory.

    Same discovery as `pinattrib.load_outcomes`, and for the same reason: the
    base `markets.json` stopped being refreshed on 09-12 and the fresh pulls
    land in sibling `fulltape_*` directories. Reading only the base file is how
    a tool silently reports nothing for the last six days.
    """
    out = {}
    paths = [markets_json] + sorted(
        glob.glob(os.path.join(os.path.dirname(markets_json) + "_*",
                               "markets.json")))
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for _ser, rows in (d or {}).items():
            for r in rows or []:
                tk, k = r.get("ticker"), r.get("strike")
                if tk and k is not None:
                    out[tk] = (float(k), r.get("settle"))
    return out


def projection(index, tau_max=60):
    """{tau: projected settlement} -- the mean if the price froze at `tau`.

    `index` is {tau: price}. The prints already recorded are the ones at taus
    ABOVE the current one, so at `tau` the locked set is 60-tau prints and the
    remaining `tau` seconds are assumed to print the current spot. That is the
    bot's own centre; `settlewin.partial()` is the same split.
    """
    out, locked, n = {}, 0.0, 0
    for tau in range(tau_max, -1, -1):
        spot = index.get(tau)
        if spot is None:
            continue
        # this second's print is one of the sixty
        locked += spot
        n += 1
        remaining = tau_max - n
        out[tau] = (locked + remaining * spot) / float(tau_max) if tau_max else spot
    return out


def flip_cost(index, strike, tau, tau_max=60):
    """How far the price must move, in percent, to flip the settlement.

    THIS IS THE ONLY MEASURE IN THE REPO THAT OWES NOTHING TO THE BOT. No fair
    value, no sigma, no gate, no threshold that was ever tuned -- just the
    settlement formula rearranged. With `tau` seconds left, `60 - tau` prints
    are locked at `locked`, and the remaining `tau` seconds must average

        spot' = (60 * strike - locked) / tau

    for the contract to land the other way. The answer is |spot' - spot| as a
    percentage of spot: a number the market has to deliver, in the seconds it
    has left, or the outcome is already written.

    It matters because every other way of asking "were there fewer bargains?"
    runs through something we built and have since changed. If this number
    says the cheap decided seconds are gone, they are gone from the MARKET.
    If it says they are still there, they are gone from US.

    Returns (percent_move_needed, side) where side is the winner if nothing
    moves, or None when the arithmetic cannot be formed.
    """
    spot = index.get(tau)
    if spot is None or not strike or tau <= 0:
        return None
    locked = 0.0
    n = 0
    for t in range(tau_max, tau - 1, -1):
        v = index.get(t)
        if v is None:
            return None                      # a hole makes `locked` a fiction
        locked += v
        n += 1
    remaining = tau_max - n
    if remaining <= 0:
        return None
    proj = (locked + remaining * spot) / float(tau_max)
    need = (tau_max * strike - locked) / float(remaining)
    return (abs(need - spot) / spot * 100.0, "yes" if proj > strike else "no")


def decided_bargains(rows, window=(3, 45), thresh=0.08, dear=0.95):
    """Seconds where the arithmetic had decided it and the book was still cheap.

    `thresh` is the percent move required to flip; `dear` the most we would
    call cheap. Counts CELLS and the MARKETS holding them -- rule 4 says a
    count of cells across twelve coins on one close is not twelve
    observations, so both are reported and the market count is the honest one.
    """
    cells = 0
    mkts = set()
    agreed = wrong = 0
    for r in rows:
        idx = {int(t): (r["k"] + d) for t, d, _p, _b, _a in r["x"]
               if d is not None and r["k"] is not None}
        for tau, _d, _p, bid, ask in r["x"]:
            if not (window[0] <= tau <= window[1]):
                continue
            fc = flip_cost(idx, r["k"], tau)
            if fc is None or fc[0] < thresh:
                continue
            side = fc[1]
            if r["r"] in ("yes", "no"):
                if side == r["r"]:
                    agreed += 1
                else:
                    wrong += 1
            px = ask if side == "yes" else ((1.0 - bid) if bid is not None else None)
            if px is not None and 0.0 < px <= dear:
                cells += 1
                mkts.add(r["t"])
    return {"cells": cells, "markets": len(mkts),
            "call_right": agreed, "call_wrong": wrong}


def fold_trades(trades):
    """One row per (second, taker side): [tau, vwap, side, contracts, prints].

    RAW PRINTS ARE 80% OF THE PAYLOAD AND ADD NOTHING. A busy market prints
    hundreds of times a second and they are all at one or two prices; shipping
    each one made the day file 10.4 MB, of which 8.5 MB was the tape repeating
    itself. Folding to a size-weighted average per second per side keeps the
    two questions a reader actually has -- what did it trade at, and how much
    went through -- and the print COUNT is kept so a single 400-lot is never
    mistaken for four hundred one-lots.
    """
    agg = {}
    for r in trades:
        key = (r.get("tau"), r.get("side"))
        px, n = r.get("yes_px"), float(r.get("n") or 0)
        if key[0] is None or px is None:
            continue
        a = agg.setdefault(key, [0.0, 0.0, 0])
        # weight by size, but a zero-size print still counts as a print and
        # must not vanish -- weight it 1 so the price is represented
        w = n if n > 0 else 1.0
        a[0] += float(px) * w
        a[1] += n
        a[2] += 1
    out = []
    for (tau, side), (num, size, prints) in agg.items():
        w = size if size > 0 else float(prints)
        out.append([tau, _r(num / w, 4), side, _r(size, 2), prints])
    out.sort(key=lambda r: (-r[0], r[2] or ""))
    return out


def _r(x, places):
    return None if x is None else round(float(x), places)


def compact(mk, strikes, tau_max=60):
    """The day, small enough to ship, with nothing a decision rested on cut."""
    import pinlook
    rows = []
    for tk, m in sorted(mk.items(), key=lambda kv: kv[1].get("close") or 0):
        strike, settle = strikes.get(tk, (None, None))
        idx = {int(k): float(v) for k, v in (m.get("index") or {}).items()}
        proj = projection(idx, tau_max)
        book = {int(k): v for k, v in (m.get("book") or {}).items()}
        secs = []
        for tau in sorted(set(idx) | set(book), reverse=True):
            bid, ask = book.get(tau, (None, None))
            secs.append([tau,
                         _r((idx[tau] - strike) if (tau in idx and strike) else None, 4),
                         _r((proj[tau] - strike) if (tau in proj and strike) else None, 4),
                         _r(bid, 4), _r(ask, 4)])
        bp = pinlook.best_price(m)
        cb = pinlook.confident_best(m)
        rows.append({
            "t": tk, "s": m.get("series"), "c": m.get("close"),
            "r": m.get("result"), "k": strike, "z": settle,
            "d": pinlook.decision(m),
            "x": secs,
            "v": fold_trades(m.get("trades") or []),
            "o": m.get("ours") or [],
            "bp": list(bp) if bp else None,
            "cb": [_r(cb[0], 4), cb[1], _r(cb[2], 5)] if cb else None,
        })
    return rows


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinlookweb selftest: FAILED -- " + msg)

    # PROJECTION is the settlement arithmetic, not a forecast.
    flat = {t: 100.0 for t in range(61)}
    p = projection(flat)
    ck(abs(p[60] - 100.0) < 1e-9 and abs(p[0] - 100.0) < 1e-9,
       "a price that never moves projects to itself at every second")

    # The planted case: half the window at 90, then a jump to 110.
    step = {t: (90.0 if t > 30 else 110.0) for t in range(61)}
    ps = projection(step)
    # at tau=0 all sixty prints are in: thirty at 90 (taus 60..31) and
    # thirty-one at 110 (taus 30..0) -- but only sixty are counted, so the
    # last print's own second closes the book.
    ck(abs(ps[0] - (30 * 90.0 + 30 * 110.0) / 60.0) < 0.5,
       "with the window full the projection IS the settlement -- a half at 90 "
       "and a half at 110 gives 100, so a market struck at 105 loses even "
       "though the price is 110 at the bell. That is the whole reason this "
       "column exists")
    ck(ps[30] > ps[31],
       "the projection jumps the instant the price does, because the "
       "remaining seconds are assumed to print the new spot")
    ck(abs(ps[31] - 90.0) < 1e-9,
       "and before the jump it is flat at 90 -- a projection that already "
       "knew about the jump would be a forecast, and this must never be one")

    # A GAP IN THE INDEX must not shift the count of locked prints.
    holey = {60: 100.0, 59: 100.0, 0: 100.0}
    ph = projection(holey)
    ck(set(ph) == {60, 59, 0},
       "NULL: seconds with no print are absent, not filled with the last "
       "value -- a forward-fill would invent locked prints that never existed")

    # FLIP COST is the settlement formula rearranged, and nothing else.
    half = {t: (100.0 if t > 30 else 100.0) for t in range(61)}
    fc = flip_cost(half, 100.0, 30)
    ck(fc and fc[0] < 1e-9,
       "a price sitting exactly on the strike needs no move at all to flip -- "
       "cost zero, which is what an undecided market looks like")
    up = {t: 101.0 for t in range(61)}
    fc2 = flip_cost(up, 100.0, 30)
    # 30 locked prints at 101 -> locked = 3131 (taus 60..30 is 31 prints)
    ck(fc2 and fc2[1] == "yes" and fc2[0] > 1.0,
       "a price a full percent above the strike for the whole locked half "
       "needs a move of more than a percent the OTHER way in thirty seconds "
       "-- decided, and on the yes side")
    ck(flip_cost({60: 100.0, 30: 100.0}, 100.0, 30) is None,
       "NULL: a hole in the locked prints makes the locked sum a fiction, so "
       "the answer is refused rather than computed from a partial window. "
       "Summing what happens to be present is how a thin tape reads as a "
       "decided market")
    ck(flip_cost(up, 100.0, 0) is None and flip_cost(up, None, 30) is None,
       "NULL: no strike and no time left both yield nothing")

    # DECIDED BARGAINS counts markets as well as cells.
    rows = [{"t": "A", "k": 100.0, "r": "yes",
             "x": [[t, 1.0, 1.0, 0.40, 0.42] for t in range(60, -1, -1)]}]
    db = decided_bargains(rows, thresh=0.5)
    ck(db["markets"] == 1 and db["cells"] > 10,
       "a market a percent clear of the strike, trading at 42c, is a decided "
       "bargain at every second in the window -- 40-odd cells but ONE market, "
       "and rule 4 says the market is the number that counts")
    ck(db["call_wrong"] == 0 and db["call_right"] > 10,
       "and the arithmetic called it right, which is the check that the "
       "threshold means anything at all")
    ck(decided_bargains(rows, thresh=0.5, dear=0.10)["cells"] == 0,
       "NULL: decided but not cheap is not a bargain")

    # FOLD TRADES keeps the price and the size, and loses only repetition.
    tr = [{"tau": 30, "yes_px": 0.90, "side": "yes", "n": 10.0},
          {"tau": 30, "yes_px": 0.98, "side": "yes", "n": 90.0},
          {"tau": 30, "yes_px": 0.50, "side": "no", "n": 5.0},
          {"tau": 12, "yes_px": 0.99, "side": "yes", "n": 0.0}]
    f = fold_trades(tr)
    y30 = [r for r in f if r[0] == 30 and r[2] == "yes"][0]
    ck(abs(y30[1] - 0.972) < 1e-9 and y30[3] == 100.0 and y30[4] == 2,
       "two yes prints in one second fold to ONE row at the size-weighted "
       "price -- 10 at 90c and 90 at 98c is 97.2c, not the 94c a plain mean "
       "would give, and the 100 contracts and 2 prints both survive")
    ck(len([r for r in f if r[0] == 30]) == 2,
       "the two taker sides stay apart -- folding them together would average "
       "a buy into a sell and report a price nobody traded at")
    z = [r for r in f if r[0] == 12][0]
    ck(abs(z[1] - 0.99) < 1e-9 and z[4] == 1,
       "NULL: a zero-size print keeps its price rather than dividing by zero")
    ck(fold_trades([]) == [], "NULL: no trades folds to nothing")

    # COMPACT keeps the strike distance, and survives a missing settlement.
    mk = {"A": {"ticker": "A", "series": "KXBTC15M", "close": 100.0,
                "result": "yes", "index": {60: 105.0, 0: 105.0},
                "book": {60: (0.5, 0.52)}, "trades": [], "ours": []}}
    rows = compact(mk, {"A": (100.0, 105.0)})
    ck(rows[0]["x"][0][1] == 5.0,
       "the index column is the DISTANCE from the strike, so a 105 print on a "
       "100 strike reads 5 -- six digits of Bitcoin around the one that counts")
    rows2 = compact(mk, {})
    ck(rows2[0]["k"] is None and rows2[0]["x"][0][1] is None,
       "NULL: an unsettled market with no strike yields empty columns rather "
       "than a distance measured from zero")
    print("pinlookweb selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--day", action="append", default=None)
    ap.add_argument("--outdir", default=None)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    strikes = load_strikes()
    outdir = a.outdir or RESULTS
    for day in (a.day or []):
        src = os.path.join(RESULTS, "pinlook_%s.json" % day)
        with open(src, encoding="utf-8") as fh:
            mk = json.load(fh)["markets"]
        rows = compact(mk, strikes)
        have = sum(1 for r in rows if r["k"] is not None)
        out = os.path.join(outdir, "look_%s.json" % day.replace("-", ""))
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"day": day, "m": rows}, fh, separators=(",", ":"))
        print("%s: %d markets, %d with a strike, %.1f MB -> %s"
              % (day, len(rows), have, os.path.getsize(out) / 1e6, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
