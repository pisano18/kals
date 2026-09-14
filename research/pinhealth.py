#!/usr/bin/env python3
# VERSION: 2026-09-14-h1
"""pinhealth.py -- the early warning: is the edge being competed away?

THE OPERATOR, 2026-09-14, after I explained why the edge might decay:
"And yes build it now."

WHAT DECAY WOULD LOOK LIKE, AND WHY IT NEEDS A DEDICATED TEST. The people
selling us a 100c contract for 96c lose on nearly every trade. At our current
size they apparently have not noticed. If they do -- or if anyone copies us --
they stop quoting under 98c in the final seconds and the edge is gone. The
measured shape of that is already visible: at 15 seconds out the side we want
has NOTHING under 98c on 94% of market-sides. We are feeding on the 6% who
have not adjusted.

THE SIGNATURE OF DECAY IS NOT A BAD WEEK. A bad week is fewer chances AND less
money. Decay is the opposite pairing:

    VOLUME UP, CENTS PER CONTRACT DOWN.

We trade more, and each contract earns less, because the counterparty is
pulling in and we are reaching further for what is left. That pairing is what
this file watches for, because either half alone is just weather.

THE KILL LINE IS ARITHMETIC, NOT A FEELING. Measured on our own fills, a
winning close pays +4.58c per contract and a losing one costs -35.8c. So at a
loss rate L the edge is  (1-L)*win - L*35.8 , and it reaches zero at

    win = L * 35.8 / (1 - L)

At our 4.15% loss rate that is 1.55c. Below roughly 1.5c per contract the
strategy is dead even though every individual trade still looks like a winner.
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
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_DASH_SELFTESTED", "1")
import pindash                                                 # noqa: E402

LOSS_COST_C = 35.8       # measured cents/contract on the ten real losing closes
WIN_C = 4.58             # measured cents/contract on winning closes
TREND_DAYS = 3           # consecutive days of the decay pairing before alarm


def kill_line(loss_rate):
    """Cents per contract at which the edge is exactly zero."""
    if loss_rate >= 1.0:
        return float("inf")
    return loss_rate * LOSS_COST_C / (1.0 - loss_rate)


def daily(trades):
    """{day: {contracts, net, legs, closes, losing_closes, mean_price}}"""
    out = defaultdict(lambda: {"contracts": 0.0, "net": 0.0, "legs": 0,
                               "px": 0.0, "closes": set(), "bad": set()})
    per_close = defaultdict(float)
    close_day = {}
    for t in trades:
        if t["pnl"] is None or not t.get("t"):
            continue
        e = pindash.to_epoch(t["t"])
        if e is None:
            continue
        d = time.strftime("%Y-%m-%d", time.localtime(e))
        a = out[d]
        a["contracts"] += t["filled"]
        a["net"] += t["pnl"]
        a["legs"] += 1
        if t["price"]:
            a["px"] += float(t["price"]) * t["filled"]
        k = pindash.close_key(t["ticker"])
        a["closes"].add(k)
        per_close[k] += t["pnl"]
        close_day[k] = d
    for k, v in per_close.items():
        if v < 0:
            out[close_day[k]]["bad"].add(k)
    return out


def assess(rows, days=TREND_DAYS):
    """(alarm, reason). `rows` is [(day, contracts, cents_per_contract)]."""
    if len(rows) < days + 1:
        return False, ("only %d days on record; the trend test needs %d"
                       % (len(rows), days + 1))
    tail = rows[-(days + 1):]
    vol_up = all(tail[i][1] < tail[i + 1][1] for i in range(len(tail) - 1))
    edge_dn = all(tail[i][2] > tail[i + 1][2] for i in range(len(tail) - 1))
    if vol_up and edge_dn:
        return True, ("%d straight days of MORE contracts and LESS per "
                      "contract -- the signature of the other side pulling "
                      "in, not of a quiet market" % days)
    if edge_dn:
        return False, ("%d days of falling cents per contract, but volume is "
                       "NOT rising -- that is a quiet market, not decay"
                       % days)
    return False, "no decay pattern"


def report(tr, loss_rate=None, say=print):
    d = daily(tr)
    if not d:
        return "pinhealth: loaded nothing -- no settled trade on file"
    days = sorted(d)
    rows = []
    for k in days:
        a = d[k]
        c = a["contracts"]
        rows.append((k, c, 100.0 * a["net"] / c if c else 0.0))
    tot_closes = sum(len(d[k]["closes"]) for k in days)
    tot_bad = sum(len(d[k]["bad"]) for k in days)
    lr = loss_rate if loss_rate is not None else (
        tot_bad / tot_closes if tot_closes else 0.0)
    kl = kill_line(lr)
    lines = []
    w = lines.append
    w("  THE ONE NUMBER: cents earned per contract.")
    w("")
    w("  day        | closes | contracts |     net | c/contract | mean price")
    w("  -----------|--------|-----------|---------|------------|-----------")
    for k in days:
        a = d[k]
        c = a["contracts"]
        w("  %-10s | %6d | %9.0f | %+7.2f | %+9.2fc | %9.1fc"
          % (k, len(a["closes"]), c, a["net"],
             100.0 * a["net"] / c if c else 0.0,
             100.0 * a["px"] / c if c else 0.0))
    w("")
    w("  loss rate so far        : %.2f%%  (%d losing of %d closes)"
      % (100 * lr, tot_bad, tot_closes))
    w("  the edge dies below     : %+.2fc per contract" % kl)
    last = rows[-1][2] if rows else 0.0
    w("  most recent day         : %+.2fc per contract" % last)
    if last > kl:
        w("  headroom                : %+.2fc  (%.1fx the kill line)"
          % (last - kl, last / kl if kl else float("inf")))
    else:
        w("  *** BELOW THE KILL LINE. At this rate the strategy loses money "
          "even though most trades still win. ***")
    alarm, why = assess(rows)
    w("")
    w("  DECAY TEST: %s" % ("*** ALARM *** " + why if alarm else why))
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

    ck(abs(kill_line(0.0415) - 1.55) < 0.02,
       "at our 4.15%% loss rate the edge dies at %.2fc per contract"
       % kill_line(0.0415))
    ck(kill_line(0.0) == 0.0, "with no losses any positive edge survives")
    ck(kill_line(0.10) > kill_line(0.04),
       "a higher loss rate needs a bigger edge to survive (%.2fc vs %.2fc)"
       % (kill_line(0.10), kill_line(0.04)))

    # THE PAIRING IS THE TEST. Either half alone must NOT alarm.
    decay = [("d1", 100, 5.0), ("d2", 200, 4.0), ("d3", 300, 3.0),
             ("d4", 400, 2.0)]
    a, why = assess(decay)
    ck(a, "volume up AND edge down for three days raises the alarm")

    quiet = [("d1", 400, 5.0), ("d2", 300, 4.0), ("d3", 200, 3.0),
             ("d4", 100, 2.0)]
    a2, why2 = assess(quiet)
    ck(not a2,
       "but a falling edge on FALLING volume does NOT -- that is a quiet "
       "market, and confusing the two would cry wolf every slow week (%s)"
       % why2)

    grow = [("d1", 100, 2.0), ("d2", 200, 3.0), ("d3", 300, 4.0),
            ("d4", 400, 5.0)]
    ck(not assess(grow)[0],
       "and growing on both counts is not an alarm either")
    ck(not assess([("d1", 100, 5.0), ("d2", 200, 4.0)])[0],
       "two days is not enough to call a trend")

    # the report must SAY it when the edge is under water
    class _T(dict):
        pass
    tr = [{"pnl": 0.01, "filled": 100.0, "price": 0.97,
           "ticker": "KXBTC15M-26SEP140100-00", "t": "2026-09-14T05:00:00Z"},
          {"pnl": -5.0, "filled": 100.0, "price": 0.97,
           "ticker": "KXETH15M-26SEP140115-15", "t": "2026-09-14T05:20:00Z"}]
    txt = report(tr, loss_rate=0.0415, say=None)
    ck("BELOW THE KILL LINE" in txt,
       "a day earning under the kill line is called out in words, not left "
       "for the reader to work out from a table")
    txt2 = report([{"pnl": 5.0, "filled": 100.0, "price": 0.93,
                    "ticker": "KXBTC15M-26SEP140100-00",
                    "t": "2026-09-14T05:00:00Z"}], loss_rate=0.0415, say=None)
    ck("headroom" in txt2, "and a healthy day reports its headroom")
    print("pinhealth selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--logs", default=os.path.join(REPO, "results",
                                                   "pinrun-live-*.jsonl"))
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "HEALTH.txt"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_HEALTH_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    ev = pindash.load(sorted(glob.glob(a.logs)))
    tr = pindash.build_trades(ev, pindash.load_outcomes(a.markets))
    txt = report(tr)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("EDGE HEALTH -- written %s ET%s%s"
                 % (time.strftime("%Y-%m-%d %H:%M"), nl, nl))
        fh.write(txt + nl)
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
