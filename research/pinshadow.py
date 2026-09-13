#!/usr/bin/env python3
# VERSION: 2026-09-13-sh1
"""pinshadow.py -- what the OLD confidence gate would have done, exactly.

THE OPERATOR, 2026-09-13, after AMENDMENT 21 moved PIN 0.995 -> 0.990: "can you
run something on the side that'll track what would happen if .995 was still
running so we can compare?"

WHY THIS NEEDS NO SIMULATION, AND WHY THAT MATTERS HERE. 0.995 is STRICTLY
STRICTER than 0.990: every trade the old gate would have taken, the new gate
also takes. So the old gate's history is not something to model -- it is a
SUBSET of our real fills, the ones whose stated confidence reached 0.995. Real
prices, real fills, real settlements, real hedges. Nothing is replayed and
nothing is assumed.

That matters because this project's whole problem is that replayed populations
do not match live ones (rule 5), and because the index population just produced
a 70x error on exactly this question. A comparison that avoids both is worth
more than a cleverer one that does not.

THE ONE WAY IT IS NOT EXACT, stated plainly and measured rather than waved at.
A close carries a CONTRACT BUDGET (MAX_PER_CLOSE x SIZE). If a marginal trade
at 0.990 consumes that budget, the old gate -- which would have skipped it --
would still have had the budget available for a LATER, possibly better signal
in the same close. So the subset is a LOWER BOUND on what 0.995 would have
done. `--report` prints how often a close held more than one fill, which is how
often that caveat can bite at all. MEASURED ON ALL HISTORY IT IS 61 OF 216
CLOSES -- 28%, not near zero -- so the bound is real but not tight, and the old
gate's arm below is an UNDERSTATEMENT of what it would have done by an unknown
amount. Said here rather than in a footnote because the first draft of this
file called the count "near zero" before anyone had counted it.

WHAT IT DOES NOT AND CANNOT SHOW. Whether the trades the old gate skipped would
have been available at all under different market conditions, and anything at
all about closes where we took nothing. It compares two gates over the SAME
moments, which is the only comparison the data supports.
"""
import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIVE = os.path.join(REPO, "results", "pinrun-live-*.jsonl")
OLD_PIN = 0.995
NEW_PIN = 0.990


def close_key(ticker):
    """The CLOSE, which is a TIME and not a market.

    `KXBTC15M-26SEP131230-30` -> `26SEP131230`. Twelve series settle on the
    same second at rho ~0.8 (hard rule 4), so keying on series+time treats one
    event as twelve and every count built on it is wrong. The first version of
    this file used `rsplit("-", 1)[0]`, which keeps the series -- caught by the
    self-test, which is why the fixture uses real-shaped tickers.
    """
    parts = str(ticker).split("-")
    return parts[1] if len(parts) >= 2 else str(ticker)


def load(glob_pat=LIVE, since=None):
    """[(close, ticker, conf, pnl_dollars, is_hedge, t, ruler, pin)].

    A fill is joined to the signal that produced it BY TICKER, which is exact
    because AMENDMENT 13 allows one fill per market. The signal carries `fair`;
    confidence is `fair` for a YES buy and `1 - fair` for a NO buy.
    """
    out = []
    for path in sorted(glob.glob(glob_pat), key=os.path.getmtime):
        conf_of = {}
        ruler, pin = "live(300s)", None
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            k = d.get("kind")
            if k == "start":
                ruler = d.get("sigma_ruler") or "live(300s)"
                pin = d.get("pin")
            elif k == "signal":
                fy = d.get("fair")
                if fy is None:
                    continue
                c = fy if d.get("want") == "yes" else 1.0 - fy
                conf_of[d.get("ticker")] = c
            elif k == "settled":
                tk = d.get("ticker")
                c = conf_of.get(tk)
                if c is None:
                    continue
                t = d.get("t") or ""
                if since and t < since:
                    continue
                out.append((close_key(tk), tk, c,
                            (d.get("pnl_c") or 0.0) / 100.0,
                            (d.get("cost") or 0.0) < 0.5, t, ruler, pin))
    return out


def split(rows, old_pin=OLD_PIN):
    """(what BOTH gates take, what ONLY the new gate takes)."""
    both, only_new = [], []
    for r in rows:
        (both if r[2] >= old_pin else only_new).append(r)
    return both, only_new


def tally(rows):
    """(entry fills, losses, dollars) -- hedges counted into the dollars but
    never into the fill or loss counts, because a hedge is not a bet."""
    ent = [r for r in rows if not r[4]]
    return (len(ent), sum(1 for r in ent if r[3] < 0),
            sum(r[3] for r in rows))


def multi_fill_closes(rows):
    """How many closes held more than one entry fill -- the only situation in
    which the contract budget could make this comparison inexact."""
    per = defaultdict(int)
    for r in rows:
        if not r[4]:
            per[r[0]] += 1
    return sum(1 for v in per.values() if v > 1), len(per)




# ---------------------------------------------------------------------------
# ERAS AND BANDS, added 2026-09-13 after I quoted a band across an era boundary
#
# THE MISTAKE. `--all` was used to report "the 0.990-0.995 band is worth
# +$13.13 on 37 fills". Every one of those 37 fills is dated 2026-09-08 to
# 2026-09-10, when the gate was **0.98**, the ruler was the 300-second one and
# the sweep did not exist. They are not what loosening the gate adds today;
# they are a different strategy in a different market. Forward evidence on the
# 0.990-0.995 band began at 17:51Z on 2026-09-13 and was, at the time of
# writing, zero fills.
#
# So: nothing in this file may pool fills across a configuration change without
# saying so, and `bands()` carries the era of every row it counts.
# ---------------------------------------------------------------------------
def eras(glob_pat=LIVE):
    """[(started, pin, ruler, sweep)] -- the configuration in force, in order.

    Read from each run's `start` record, which has logged `pin` since before
    it was a flag, so the gate is known for every fill ever taken.
    """
    out = []
    for path in sorted(glob.glob(glob_pat), key=os.path.getmtime):
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") != "start":
                continue
            cfg = (d.get("pin"), d.get("sigma_ruler") or "live(300s)",
                   bool(d.get("sweep_enabled")))
            if not out or out[-1][1:] != cfg:
                out.append((d.get("t"), ) + cfg)
            break
    return out


def era_of(t, ers):
    """The configuration in force at time `t`."""
    cur = None
    for e in ers:
        if e[0] and t >= e[0]:
            cur = e
        else:
            break
    return cur


MIN_FILLS_FOR_RATE = 30      # below this, a $/hour figure is noise wearing a
                             # decimal point and is refused rather than printed


def era_table(rows, ers, say=print):
    """Measured results per configuration. The ONLY honest answer to 'was the
    old setup better' -- and it is confounded by the market changing at the
    same time, which is stated rather than hidden."""
    import calendar
    import datetime
    per = defaultdict(lambda: [0, 0, 0.0, None, None])
    for r in rows:
        e = era_of(r[5], ers)
        if e is None:
            continue
        key = (e[1], e[2], e[3])
        a = per[key]
        if not r[4]:
            a[0] += 1
            a[1] += 1 if r[3] < 0 else 0
        a[2] += r[3]
        ts = calendar.timegm(datetime.datetime.strptime(
            r[5], "%Y-%m-%dT%H:%M:%SZ").timetuple())
        a[3] = ts if a[3] is None else min(a[3], ts)
        a[4] = ts if a[4] is None else max(a[4], ts)
    # the %% is not a typo: the two literals concatenate BEFORE the % applies,
    # so a bare "loss%" reads as a format specifier and raises
    lines = ["  gate | ruler      | sweep | hours | fills | losses | loss%% | "
             "net $ | $/hour (needs n>=%d)" % MIN_FILLS_FOR_RATE,
             "  -----|------------|-------|-------|-------|--------|-------|"
             "-------|-------"]
    for (pin, ruler, sw), (f, L, d, t0, t1) in sorted(
            per.items(), key=lambda kv: kv[1][3] or 0):
        h = max((t1 - t0) / 3600.0, 0.01)
        # A RATE FROM FOUR FILLS IS NOT A RATE. The first version of this
        # table printed "+$17.37/hour" off 4 fills in 48 minutes and
        # "+$563.09/hour" off 2 fills in two minutes, and the operator quite
        # reasonably asked for more of the second one. Both were noise wearing
        # a decimal point. Anything under MIN_FILLS_FOR_RATE now prints the
        # sample size instead of a number nobody should act on.
        rate = ("%+.2f" % (d / h)) if f >= MIN_FILLS_FOR_RATE else (
            "n=%d, too few" % f)
        lines.append("  %-5s| %-11s| %-6s| %5.1f | %5d | %6d | %5s | %+6.2f "
                     "| %s"
                     % (pin, ruler, sw, h, f, L,
                        ("%.1f%%" % (100.0 * L / f)) if f else "-", d, rate))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


BANDS = (0.95, 0.97, 0.98, 0.985, 0.99, 0.995, 0.998, 0.999, 0.9999, 1.01)


def bands(rows, ers, say=print):
    """Fills, losses and dollars by CONFIDENCE BAND, with the gate that was in
    force -- because a band below the gate of its era cannot have been produced
    by that gate and is evidence about a different strategy."""
    per = defaultdict(lambda: [0, 0, 0.0, set()])
    for r in rows:
        if r[4]:
            continue
        c = r[2]
        lo = BANDS[0]
        for i in range(len(BANDS) - 1):
            if BANDS[i] <= c < BANDS[i + 1]:
                lo = BANDS[i]
                break
        else:
            lo = BANDS[-2]
        a = per[lo]
        a[0] += 1
        a[1] += 1 if r[3] < 0 else 0
        a[2] += r[3]
        e = era_of(r[5], ers)
        if e:
            a[3].add(str(e[1]))
    lines = ["  confidence band | fills | losses | loss% | net $ | $/fill | "
             "gate(s) in force then",
             "  ----------------|-------|--------|-------|-------|--------|"
             "----------------------"]
    for i in range(len(BANDS) - 1):
        lo, hi = BANDS[i], BANDS[i + 1]
        if lo not in per:
            continue
        f, L, d, gates = per[lo]
        lines.append("  %.4f-%.4f | %5d | %6d | %5s | %+6.2f | %+6.3f | %s"
                     % (lo, min(hi, 1.0), f, L,
                        ("%.1f%%" % (100.0 * L / f)) if f else "-", d,
                        d / f if f else float("nan"),
                        ",".join(sorted(gates))))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="pinshadow-")
    try:
        fp = os.path.join(tmp, "pinrun-live-x.jsonl")
        with open(fp, "w", encoding="utf-8") as fh:
            w = lambda d: fh.write(json.dumps(d) + "\n")      # noqa: E731
            w({"kind": "start", "sigma_ruler": "maxdown", "pin": 0.99})
            # clears BOTH gates, wins
            w({"kind": "signal", "ticker": "KXBTC15M-26SEP131230-00", "want": "yes",
               "fair": 0.9990})
            w({"kind": "settled", "ticker": "KXBTC15M-26SEP131230-00", "cost": 0.96,
               "pnl_c": 400.0, "t": "2026-09-13T18:00:00Z"})
            # clears ONLY the new gate, loses
            w({"kind": "signal", "ticker": "KXETH15M-26SEP131230-00", "want": "yes",
               "fair": 0.9920})
            w({"kind": "settled", "ticker": "KXETH15M-26SEP131230-00", "cost": 0.95,
               "pnl_c": -9500.0, "t": "2026-09-13T18:00:05Z"})
            # a NO buy: confidence is 1 - fair, and this one clears both
            w({"kind": "signal", "ticker": "KXSOL15M-26SEP131230-00", "want": "no",
               "fair": 0.0002})
            w({"kind": "settled", "ticker": "KXSOL15M-26SEP131230-00", "cost": 0.97,
               "pnl_c": 300.0, "t": "2026-09-13T18:00:10Z"})
            # a hedge leg on B: cost under 0.5, must not count as a fill
            w({"kind": "settled", "ticker": "KXETH15M-26SEP131230-00", "cost": 0.10,
               "pnl_c": -340.0, "t": "2026-09-13T18:00:12Z"})
        rows = load(os.path.join(tmp, "pinrun-live-*.jsonl"))
        ck(len(rows) == 4, "every settled record with a signal is loaded (%d)"
           % len(rows))
        both, only_new = split(rows)
        ck([r[1] for r in both] == ["KXBTC15M-26SEP131230-00", "KXSOL15M-26SEP131230-00"],
           "the old gate keeps exactly the two that reached 0.995 (%s)"
           % [r[1] for r in both])
        ck(len(only_new) == 2 and all(r[1] == "KXETH15M-26SEP131230-00" for r in only_new),
           "and the loser that only reached 0.992 -- WITH ITS HEDGE LEG -- is "
           "attributed to the new gate alone, because the old gate would never "
           "have opened the position the hedge protects")
        e, L, d = tally(both)
        ck((e, L) == (2, 0) and abs(d - 7.0) < 1e-9,
           "the old gate's arm: %d fills, %d losses, $%+.2f" % (e, L, d))
        e2, L2, d2 = tally(only_new)
        ck((e2, L2) == (1, 1) and abs(d2 - (-98.40)) < 1e-9,
           "the new gate's extra arm: %d fills, %d losses, $%+.2f"
           % (e2, L2, d2))
        ck(abs((d + d2) - sum(r[3] for r in rows)) < 1e-9,
           "and the two arms sum to the real total, so nothing is "
           "double-counted or dropped")

        # a NO buy at fair 0.006 has confidence 0.994 -- under 0.995, not over
        with open(fp, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "signal", "ticker": "KXXRP15M-26SEP131245-00",
                                 "want": "no", "fair": 0.006}) + "\n")
            fh.write(json.dumps({"kind": "settled", "ticker": "KXXRP15M-26SEP131245-00",
                                 "cost": 0.98, "pnl_c": 100.0,
                                 "t": "2026-09-13T18:00:20Z"}) + "\n")
        rows2 = load(os.path.join(tmp, "pinrun-live-*.jsonl"))
        b2, n2 = split(rows2)
        ck(any(r[1] == "KXXRP15M-26SEP131245-00" for r in n2),
           "a NO buy is judged on 1-fair, not fair -- 0.006 is 99.4% "
           "confident and does NOT clear 0.995")

        mf, tot = multi_fill_closes(rows2)
        ck(tot == 2,
           "closes are keyed by TIME, so three coins settling at 12:30 are ONE "
           "close and the 12:45 one is another -- %d closes, not 4" % tot)
        ck(mf == 1,
           "and the budget caveat is measured: %d of %d closes held more than "
           "one fill" % (mf, tot))
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    print("pinshadow selftest: %d checks OK" % n[0])
    return 0


def report(rows, say=print, old_pin=OLD_PIN, new_pin=NEW_PIN):
    both, only_new = split(rows, old_pin)
    e1, l1, d1 = tally(both)
    e2, l2, d2 = tally(only_new)
    mf, tot = multi_fill_closes(rows)
    lines = []
    w = lines.append
    w("SHADOW: what PIN %.3f would have done, against what PIN %.3f actually "
      "did" % (old_pin, new_pin))
    w("  (not a simulation -- %.3f is strictly stricter, so its history is the "
      "subset" % old_pin)
    w("   of our REAL fills that reached it: real prices, fills, settlements, "
      "hedges)")
    w("")
    w("  gate            | fills | losses | loss rate | net $")
    w("  ----------------|-------|--------|-----------|--------")
    w("  %.3f (old)      | %5d | %6d | %8s | %+7.2f"
      % (old_pin, e1, l1, ("%.1f%%" % (100.0 * l1 / e1)) if e1 else "-", d1))
    w("  extra at %.3f   | %5d | %6d | %8s | %+7.2f"
      % (new_pin, e2, l2, ("%.1f%%" % (100.0 * l2 / e2)) if e2 else "-", d2))
    w("  ----------------|-------|--------|-----------|--------")
    w("  ACTUAL (%.3f)   | %5d | %6d | %8s | %+7.2f"
      % (new_pin, e1 + e2, l1 + l2,
         ("%.1f%%" % (100.0 * (l1 + l2) / (e1 + e2))) if (e1 + e2) else "-",
         d1 + d2))
    w("")
    if e2 == 0:
        w("  The looser gate has not yet taken a trade the old one would have "
          "refused.")
    else:
        w("  VERDICT SO FAR: the %d extra trades are worth $%+.2f. Loosening "
          "the gate" % (e2, d2))
        w("  is %s on this evidence."
          % ("PAYING" if d2 > 0 else "COSTING money"))
    w("")
    w("  budget caveat: %d of %d closes held more than one fill, the only "
      "case where" % (mf, tot))
    w("  the old gate could have used the freed budget on a later signal. "
      "This is a")
    w("  LOWER BOUND on the old gate, and at %d of %d it is NOT a tight one."
      % (mf, tot))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--since", default="2026-09-13T17:51:00Z",
                    help="ISO UTC; default is the AMENDMENT 21 deploy")
    ap.add_argument("--all", action="store_true",
                    help="every fill ever, not just since the deploy")
    ap.add_argument("--bands", action="store_true",
                    help="fills, losses and dollars by confidence band")
    ap.add_argument("--eras", action="store_true",
                    help="measured results per configuration")
    ap.add_argument("--watch", action="store_true",
                    help="emit one line each time a trade lands that the old "
                         "gate would have refused")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    since = None if a.all else a.since
    if a.bands or a.eras:
        rows = load(since=None)
        ers = eras()
        if not rows:
            print("pinshadow: no settled fill carries a signal yet -- nothing "
                  "to analyse")
            return 0
        _ent = [r for r in rows if not r[4]]
        print("ACCOUNT TOTAL, ALL TIME: $%+.2f  (%d entry fills, %d losses)"
              % (sum(r[3] for r in rows), len(_ent),
                 sum(1 for r in _ent if r[3] < 0)))
        print("  Every row below is ONE SLICE of that total, not the total. "
              "The slices sum to it.")
        print("")
        print("CONFIGURATIONS, in order:")
        for t, pin, ruler, sw in ers:
            print("  from %s | gate %-6s | ruler %-11s | sweep %s"
                  % (t, pin, ruler, sw))
        print("")
        if a.eras:
            print("MEASURED RESULTS PER CONFIGURATION")
            print("  (the market changed at the same time as every one of "
                  "these, so this")
            print("   is a record of what happened, NOT an experiment)")
            era_table(rows, ers)
            print("")
        if a.bands:
            print("BY CONFIDENCE BAND -- every fill ever")
            print("  (a band BELOW the gate of its era could not have been "
                  "produced by that")
            print("   gate; it is evidence about a different strategy, and "
                  "the last column")
            print("   says which)")
            bands(rows, ers)
        return 0
    if not a.watch:
        rows = load(since=since)
        if not rows:
            print("pinshadow: no settled fill carries a signal yet -- nothing "
                  "to analyse")
            return 0
        report(rows)
        return 0
    seen = set()
    for r in load(since=since):
        seen.add((r[1], r[5]))
    while True:
        for r in load(since=since):
            key = (r[1], r[5])
            if key in seen or r[4]:
                seen.add(key)
                continue
            seen.add(key)
            if r[2] < OLD_PIN:
                print("GATE DIFFERENCE %s | confidence %.4f (under the old "
                      "%.3f) | %+.2f dollars | the old gate would have SKIPPED "
                      "this" % (r[1], r[2], OLD_PIN, r[3]))
        sys.stdout.flush()
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
