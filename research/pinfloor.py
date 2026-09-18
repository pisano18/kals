"""pinfloor.py -- why the money fell: the depth floor moves with the bank.

THE MECHANISM, stated before the evidence so it can be checked against it.
`pinrun` refuses an offer that is too shallow to fill properly:

    _floor = max(MIN_LEVEL, MIN_FILL_FRAC * SIZE)      # = max(1, 0.5 * SIZE)

`SIZE` is not a constant. `autosize_tick` moves it with the bank, so as the
account grew from roughly $160 to $630 the bet went 20 -> 78 contracts and the
SMALLEST OFFER WE WILL TOUCH WENT FROM 10 CONTRACTS TO 39. Nobody deployed
that. It is a threshold that rides on another number, and it tightens every
time we win.

This measures it from the bot's OWN funnel, not from a replay. Every close
writes a `close_summary` holding `depth.kept` -- a histogram of how many
offers at that close held at least k contracts, built over every offer the
scan saw including the ones it then skipped. That histogram answers the
counterfactual directly, with no model and no re-simulation: at a floor of 10,
`kept["10"]` offers were available; at a floor of 39, about `kept["50"]`
were. The ratio is how much of the market our own growth has closed off.

WHAT THIS CANNOT SAY. It counts OFFERS, not fills, and an offer we could have
touched is not money we would have won -- hard rule 5 applies to any leap from
"this was in the book" to "we would have kept it". The money column here is
what actually settled, per day, from our own live fills; the offer counts are
the supply side, and the two are reported apart on purpose.
"""
import argparse
import collections
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

MIN_LEVEL = 1.0          # mirrors pinrun; asserted against it in selftest()
MIN_FILL_FRAC = 0.50


def floor_for(size):
    """The smallest offer `pinrun` will touch at this bet size."""
    return max(MIN_LEVEL, MIN_FILL_FRAC * float(size))


def kept_at(kept, floor):
    """Offers holding at least `floor` contracts, from a `kept` histogram.

    The histogram is sampled at fixed cut points (1, 5, 10, 15, 25, 50, ...),
    so an arbitrary floor falls between two of them. Take the NEXT CUT UP --
    the conservative side, which UNDERSTATES how many offers a lower floor
    would have reached. Interpolating would invent offers at sizes the
    histogram never counted, and this number exists to size a loss; it must
    not be allowed to flatter the argument it supports.
    """
    cuts = sorted(int(k) for k in kept)
    for c in cuts:
        if c >= floor:
            return kept[str(c)], c
    return 0, (cuts[-1] if cuts else 0)


def et_day_of(iso):
    """The Eastern day an ISO-8601 UTC stamp belongs to.

    Times shown to the operator are Eastern, always. Grouping by the UTC date
    would move the whole New York evening -- the busiest part of his day -- on
    to the next row, which is the ticker-clock trap that once turned a $23 day
    into a $47 one.
    """
    import calendar
    import time
    import pindesk
    try:
        t = calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None
    return pindesk.et_day(t)


def scan(paths=None):
    """Per Eastern day: the offer funnel, the bet size, and the money."""
    paths = paths or sorted(glob.glob(os.path.join(
        RESULTS, "pinrun-live-*.jsonl")))
    days = collections.defaultdict(lambda: {
        "closes": 0, "looks": 0, "tradeable": 0, "fired": 0,
        "offers": 0, "at10": 0, "at39": 0, "atfloor": 0,
        "depth_floor": 0, "sizes": [], "pnl": 0.0, "fills": 0,
        "costs": [], "wins": 0, "losses": 0, "run_end": {},
        "contracts": 0.0, "staked": 0.0})
    for p in paths:
        for line in io.open(p, encoding="utf-8", errors="replace"):
            if '"kind"' not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            day = et_day_of(r.get("t") or "")
            if day is None:
                continue
            d = days[day]
            if k == "close_summary":
                d["closes"] += 1
                d["looks"] += int(r.get("looks") or 0)
                d["tradeable"] += int(r.get("tradeable") or 0)
                d["fired"] += 1 if r.get("fired") else 0
                d["depth_floor"] += int((r.get("gates") or {})
                                        .get("depth_floor") or 0)
                kept = ((r.get("depth") or {}).get("kept") or {})
                if kept:
                    d["offers"] += int((r.get("depth") or {}).get("n") or 0)
                    d["at10"] += kept_at(kept, 10.0)[0]
                    d["at39"] += kept_at(kept, 39.0)[0]
                    # the floor that was ACTUALLY in force at this close
                    sk = r.get("shallow_skips") or {}
                    size = max([float(x) for x in sk] or [0.0]) or None
                    d["atfloor"] += (kept_at(kept, floor_for(size))[0]
                                     if size else kept_at(kept, 10.0)[0])
            elif k == "autosize":
                d["sizes"].append(float(r.get("new") or 0))
            elif k == "settled":
                # `pnl_c` IS THIS FILL, IN CENTS. `realised` IS A RUNNING
                # TOTAL FOR THE BOT RUN and resets to near zero on every
                # restart -- summing it turned 2026-09-18 into $768.58 when
                # the true figure is a fifteenth of that. This is the same
                # shape as the bug the operator caught with "you said we're
                # up 47, we're only up $22", and it is the reason this file
                # cross-checks the two below rather than trusting either.
                d["fills"] += 1
                d["pnl"] += float(r.get("pnl_c") or 0.0) / 100.0
                _won = r.get("result") == r.get("want")
                _n = contracts_of(r.get("pnl_c") or 0.0, r.get("cost") or 0.0,
                                  _won)
                if _n is not None:
                    d["contracts"] += _n
                    d["staked"] += _n * float(r["cost"])
                d["run_end"][p] = float(r.get("realised") or 0.0)
                if r.get("cost") is not None:
                    d["costs"].append(float(r["cost"]))
                res, want = r.get("result"), r.get("want")
                if res and want:
                    if res == want:
                        d["wins"] += 1
                    else:
                        d["losses"] += 1
    return days


def contracts_of(pnl_c, cost, won):
    """How many contracts a settled fill held, from its money and its price.

    THE SETTLED RECORD DOES NOT CARRY THE SIZE, and the size moved five times
    in the window being compared (20 -> 98), so "dollars per day" alone cannot
    say whether a good day was a good EDGE or just a big bet. Recovering the
    count is arithmetic on the fee rule, which is fixed and documented:

        win :  pnl = n * (1 - p) - 0.07 * p * (1 - p) * n
        loss:  pnl = -n * p                     (the fee is only paid on a win)

    Returns None rather than a guess when the arithmetic is degenerate -- at
    p = 1 a win pays nothing and the count is unrecoverable, and inventing one
    would put a fabricated number straight into the denominator of the return.
    """
    pnl = float(pnl_c) / 100.0
    p = float(cost)
    if not (0.0 < p < 1.0):
        return None
    if won:
        per = (1.0 - p) - 0.07 * p * (1.0 - p)
        return (pnl / per) if per > 1e-9 else None
    return (-pnl / p) if p > 1e-9 else None


def _med(xs):
    return None if not xs else sorted(xs)[len(xs) // 2]


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinfloor selftest: FAILED -- " + msg)

    # THE CONSTANTS MUST MATCH pinrun, or this whole file argues about a
    # threshold the bot does not have.
    src = io.open(os.path.join(HERE, "pinrun.py"), encoding="utf-8").read()
    ck("_DEFAULT_MIN_FILL_FRAC = 0.50" in src,
       "pinrun still declares the depth fraction as 0.50 -- if that line "
       "moves, every number below is measured against the wrong floor")
    ck("MIN_LEVEL = 1.0" in src, "and the absolute minimum level is still 1")
    ck("_floor = max(MIN_LEVEL, MIN_FILL_FRAC * float(SIZE))" in src,
       "and the floor is still MIN_FILL_FRAC times the RUNNING SIZE -- the "
       "whole claim of this file is that this one line ties the bar we "
       "refuse at to how much money we have")

    ck(abs(floor_for(20) - 10.0) < 1e-9 and abs(floor_for(78) - 39.0) < 1e-9,
       "a 20-contract bet refuses anything under 10; a 78-contract bet "
       "refuses anything under 39. Same code, four times the bar")
    ck(abs(floor_for(0.5) - 1.0) < 1e-9,
       "NULL: a tiny bet still has to find one whole contract, not half of one")

    # KEPT_AT takes the conservative cut, never the flattering one.
    kept = {"1": 100, "5": 80, "10": 60, "25": 40, "50": 20, "125": 5}
    ck(kept_at(kept, 39.0) == (20, 50),
       "a floor of 39 falls between the 25 and 50 cut points, and the answer "
       "is the 50 one -- 20 offers, not 40. Rounding the other way would "
       "overstate the loss this file exists to size")
    ck(kept_at(kept, 10.0) == (60, 10), "an exact cut point is used as it is")
    ck(kept_at(kept, 9999.0) == (0, 125),
       "NULL: a floor above every cut point keeps nothing, rather than "
       "falling through to the largest bucket")
    ck(kept_at({}, 10.0) == (0, 0), "NULL: no histogram, no answer")

    # ET DAY grouping, the trap that has bitten twice.
    ck(et_day_of("2026-09-18T23:30:00Z") == "2026-09-18",
       "23:30Z is 7:30pm in New York, so it belongs to the SAME Eastern day "
       "-- grouping by the UTC date is how an evening gets moved")
    ck(et_day_of("2026-09-19T02:30:00Z") == "2026-09-18",
       "and 02:30Z is 10:30pm the PREVIOUS Eastern evening, the busiest hour "
       "we trade")
    ck(et_day_of("") is None and et_day_of(None) is None,
       "NULL: an unparseable stamp is dropped, never bucketed into today")

    # THE MONEY COLUMN reads the per-fill field, never the running one.
    import tempfile
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8")
    for pnl, run in ((250.0, 2.50), (150.0, 4.00), (-400.0, 0.00)):
        fh.write(json.dumps({"kind": "settled", "t": "2026-09-18T12:00:00Z",
                             "ticker": "T", "want": "yes",
                             "result": "yes" if pnl > 0 else "no",
                             "cost": 0.97, "pnl_c": pnl,
                             "realised": run}) + chr(10))
    fh.close()
    got = scan([fh.name])["2026-09-18"]
    os.unlink(fh.name)
    ck(abs(got["pnl"] - 0.0) < 1e-9,
       "three fills of +$2.50, +$1.50 and -$4.00 net to ZERO. Summing the "
       "running `realised` column instead would have said $6.50, because "
       "that field is a cumulative total that also resets on restart -- the "
       "exact error that reported $768 on a day worth a fifteenth of it")
    ck(got["fills"] == 3 and got["wins"] == 2 and got["losses"] == 1,
       "and the win and loss counts follow the result, not the sign")

    # CONTRACTS recovered from the money must reproduce a known bet.
    n, p = 40.0, 0.95
    win_pnl = (n * (1 - p) - 0.07 * p * (1 - p) * n) * 100.0
    ck(abs(contracts_of(win_pnl, p, True) - n) < 1e-6,
       "forty contracts bought at 95c that win pay $1.87 after the fee, and "
       "the count comes back out of that exactly -- without it, a $115 day at "
       "a 47-contract bet and a $115 day at a 98-contract bet look identical "
       "when one is twice the risk for the same return")
    ck(abs(contracts_of(-n * p * 100.0, p, False) - n) < 1e-6,
       "and a loss pays no fee, so the count is simply the money over the price")
    ck(contracts_of(100.0, 1.0, True) is None
       and contracts_of(100.0, 0.0, False) is None,
       "NULL: a fill at 100c or 0c cannot yield a count, and returns nothing "
       "rather than a number that would silently enter the denominator")
    print("pinfloor selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    days = scan()
    print()
    print("  %-11s %6s %7s %8s %9s %8s %8s %8s %9s"
          % ("ET day", "closes", "bet", "offers", "ok@10", "ok@39", "skipped",
             "fills", "money"))
    for day in sorted(days):
        d = days[day]
        if not d["closes"] and not d["fills"]:
            continue
        size = _med(d["sizes"])
        print("  %-11s %6d %7s %8d %9d %8d %8d %8d %9s"
              % (day, d["closes"], ("%.0f" % size) if size else "-",
                 d["offers"], d["at10"], d["at39"], d["depth_floor"],
                 d["fills"], "$%.2f" % d["pnl"]))
    print()
    print("  ok@10 = offers big enough for a 20-contract bet")
    print("  ok@39 = the same offers, judged against a 78-contract bet")
    print()
    for day in sorted(days):
        d = days[day]
        if not d["offers"]:
            continue
        lost = d["at10"] - d["at39"]
        print("  %s: a 78-contract bet refuses %d of the %d offers a "
              "20-contract bet could take (%.0f%%)"
              % (day, lost, d["at10"],
                 100.0 * lost / d["at10"] if d["at10"] else 0.0))
    print()
    print("  THE NUMBER THAT MATTERS -- what each dollar we put at risk earned")
    print()
    print("  %-11s %6s %6s %7s %9s %11s %9s %8s"
          % ("ET day", "fills", "bet", "avg paid", "contracts", "staked",
             "money", "return"))
    for day in sorted(days):
        d = days[day]
        if not d["fills"]:
            continue
        cost = _med(d["costs"])
        ret = (100.0 * d["pnl"] / d["staked"]) if d["staked"] > 0 else None
        size = _med(d["sizes"])
        print("  %-11s %6d %6s %7s %9.0f %11s %9s %8s"
              % (day, d["fills"], ("%.0f" % size) if size else "-",
                 ("%.1fc" % (cost * 100)) if cost else "-",
                 d["contracts"], "$%.0f" % d["staked"],
                 "$%.2f" % d["pnl"],
                 ("%.2f%%" % ret) if ret is not None else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
