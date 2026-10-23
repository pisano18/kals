"""ladder_shadow.py -- READ-ONLY scorecard: the live ladder's Option C vs the setup it replaced, from the paper ladder.

Operator 2026-10-22: "Okay option c but keep something running to know if we ever would have loss or won one on the
other option". The clean-room paper ladder (locked_average_ladder_re_paper.py, boot_all "ladder paper") keeps watching
ALL 9 coins and all 3 rungs at 100 contracts a rung, with queue-ahead charged (the 'pess' fill). This replays its fills
at the live sizes, the way .sweep/q-2026-10-22/ladder/opts.py did (one bid of S at a time, a refill after it is used up,
at most CAP bids a market):
    A  = the old setup: all 9 coins, S = pot / 14, 2 bids a market (live until 2026-10-22)
    C  = Option C (live from 2026-10-22): NEAR ZEC DOGE HYPE XRP, S = pot / 7.8, 1 bid a market
    C+ = C plus a 95c rung (level 1) on the same 5 coins at the same S (not live; a candidate)
and lists EVERY paper market where a ladder bid filled and LOST (any coin, any rung): the alarm the operator asked for.
Money truth for the live ladder is Kalshi (botstats / pinledger), never this file.

    python research/ladder_shadow.py            # report since Option C went live (and all-time)
    python research/ladder_shadow.py --json     # machine-readable (for Telegram)
The first run reads the whole paper log once (~300 MB); later runs read only what was appended (offset cache).
"""
import argparse
import collections
import json
import os
import sys
from datetime import datetime, timedelta, timezone

PAPER = r"C:\kals-repo\results\cleanroom-locked_average_ladder_re.jsonl"
ORDERS = r"C:\kals-repo\results\ladder-live-orders.jsonl"
CACHE = r"C:\kals-repo\results\ladder_shadow_cache.json"
OPTC_LIVE = "2026-10-22"                       # ET day Option C went live (updated at deploy)
TOP5 = ("KXNEAR15M", "KXZEC15M", "KXDOGE15M", "KXHYPE15M", "KXXRP15M")
KEEP = (b'"ev":"fill"', b'"ev":"settle"')
PX = {0: 0.98, 1: 0.95, 2: 0.85}


def et_day(close_s):
    return (datetime.fromtimestamp(close_s, timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d")


def load():
    c = {"offset": 0, "markets": {}}
    try:
        with open(CACHE) as f:
            c = json.load(f)
    except Exception:
        pass
    size = os.path.getsize(PAPER)
    if size < c["offset"]:                      # the log was rotated / replaced: start over
        c = {"offset": 0, "markets": {}}
    with open(PAPER, "rb") as f:
        f.seek(c["offset"])
        for line in f:
            if not line.endswith(b"\n"):
                break                          # a half-written last line: read it next time
            c["offset"] += len(line)
            if not any(k in line for k in KEEP):
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            m = c["markets"].setdefault(r.get("ticker"), {"f": {}, "px": {}, "res": None, "close_s": None})
            if r["ev"] == "fill":
                if r.get("kind") != "rest":
                    continue
                sz = float(r.get("size_pess") or 0)
                if sz > 0:
                    lv = str(r["level"])
                    m["f"].setdefault(lv, []).append([r["ts_ms"] / 1000.0, sz, r["side"]])
                    m["px"][lv] = float(r["my_price"])
            else:
                m["res"] = r.get("result")
                m["close_s"] = r.get("close_s")
    c["markets"] = {k: v for k, v in c["markets"].items() if v["f"] or v["res"] is None}
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(c, f)
    os.replace(tmp, CACHE)
    return c


def sim(fills, S, cap, refill=1.0):
    """opts.py's fill model: one bid of S, a refill bid 1 s after it is used up, at most `cap` bids. -> contracts."""
    got, bids, cur, t_av = 0.0, 1, 0.0, -1e18
    for ts, sz, _ in sorted(fills, key=lambda x: x[0]):
        if ts < t_av:
            continue
        take = min(sz, S - cur)
        cur += take
        got += take
        if cur >= S - 1e-9:
            if bids >= cap:
                break
            bids, cur, t_av = bids + 1, 0.0, ts + refill
    return got


def live_pot():
    """The live ladder's latest pot (its own 'rescale'/'start' records); 643.47 if none is readable."""
    pot = None
    try:
        with open(ORDERS, "rb") as f:
            f.seek(max(0, os.path.getsize(ORDERS) - 4_000_000))
            for line in f:
                if b'"pot"' in line and (b'"ev":"rescale"' in line or b'"ev":"start"' in line):
                    try:
                        p = json.loads(line).get("pot")
                        pot = float(p) if p else pot
                    except Exception:
                        pass
    except Exception:
        pass
    return pot or 643.47


def score(c, pot, since):
    S14, S78, S10 = int(pot // 14), int(pot // 7.8), int(pot // 10)
    # "fit" (10-22 study): pot/10 a bid so every rung of every coin rests at once under a 100% money rail (the live C+
    # at pot/7.8 + 70% defers most 95c bids). Unconstrained replay like the others; the rail-aware replay is in
    # .sweep/q-2026-10-22/ladfit/.
    opts = {"A": (None, S14, 2, (0,)), "C": (TOP5, S78, 1, (0,)), "C+": (TOP5, S78, 1, (0, 1)), "fit": (TOP5, S10, 1, (0, 1))}
    out = {k: collections.Counter() for k in opts}
    days, losers = set(), []
    for tk, m in c["markets"].items():
        if m["res"] not in ("yes", "no") or not m["close_s"]:
            continue
        d = et_day(m["close_s"])
        if d < since:
            continue
        days.add(d)
        coin = tk.split("-")[0]
        for lv, fl in m["f"].items():
            if any(side != m["res"] for _, _, side in fl):
                losers.append({"ticker": tk, "day": d, "level": int(lv), "result": m["res"],
                               "paper_contracts": sum(x[1] for x in fl)})
        for k, (coins, S, cap, lvls) in opts.items():
            if coins and coin not in coins:
                continue
            got_any = False
            for lv in lvls:
                fl = m["f"].get(str(lv))
                if not fl:
                    continue
                n = sim(fl, S, cap)
                if n <= 0:
                    continue
                got_any = True
                px = m["px"].get(str(lv), PX[lv])
                won = fl[0][2] == m["res"]
                out[k]["contracts"] += n
                out[k]["money"] += n * (1 - px) if won else -n * px
                out[k]["lost_markets"] += 0 if won else 1
            out[k]["filled_markets"] += got_any
    nd = max(1, len(days))
    res = {"since": since, "days": len(days), "pot": round(pot, 2), "sizes": {"A": S14, "C": S78, "C+": S78, "fit": S10},
           "losers": sorted(losers, key=lambda x: x["day"])}
    for k, o in out.items():
        res[k] = {"filled_markets": int(o["filled_markets"]), "lost_markets": int(o["lost_markets"]),
                  "contracts": round(o["contracts"]), "money": round(o["money"], 2),
                  "per_day": round(o["money"] / nd, 2), "pct_per_day": round(100 * o["money"] / nd / pot, 2)}
    return res


def selftest():
    fails = []
    fl = [[1.0, 30, "yes"], [1.5, 30, "yes"], [3.0, 100, "yes"]]
    if sim(fl, 50, 1) != 50:
        fails.append("one bid of 50 takes 50")
    if sim(fl, 50, 2) != 100:
        fails.append("two bids take 100 (got %s)" % sim(fl, 50, 2))
    if sim([[1.0, 10, "no"]], 50, 1) != 10:
        fails.append("a partial fill is partial")
    c = {"markets": {
        "KXNEAR15M-26OCT221200-00": {"f": {"0": [[1, 100, "yes"]]}, "px": {"0": 0.98}, "res": "yes", "close_s": 1792684800},
        "KXBTC15M-26OCT221200-00": {"f": {"0": [[1, 100, "no"]]}, "px": {"0": 0.98}, "res": "yes", "close_s": 1792684800}}}
    r = score(c, 643.47, "2026-10-01")
    if not (r["C"]["lost_markets"] == 0 and r["A"]["lost_markets"] == 1 and len(r["losers"]) == 1):
        fails.append("a BTC loss counts against A only and is listed (%s)" % r)
    if abs(r["C"]["money"] - 82 * 0.02) > 1e-6 or abs(r["A"]["money"] - (45 * 0.02 - 45 * 0.98)) > 1e-6:
        fails.append("money C %.4f A %.4f" % (r["C"]["money"], r["A"]["money"]))
    print("ladder_shadow self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--since", default=OPTC_LIVE)
    a = ap.parse_args()
    if a.selftest:
        return 0 if selftest() else 1
    c = load()
    pot = live_pot()
    rep = {"since_optc": score(c, pot, a.since), "all_time": score(c, pot, "2026-09-27")}
    if a.json:
        print(json.dumps(rep))
        return 0
    for name, r in (("SINCE OPTION C (%s)" % a.since, rep["since_optc"]), ("ALL TIME (paper since 09-27)", rep["all_time"])):
        print("== %s: %d days, pot $%.2f" % (name, r["days"], r["pot"]))
        for k, lab in (("C", "Option C"), ("A", "old setup, 9 coins"), ("C+", "C + 95c rung (live)"), ("fit", "fit: pot/10, 98+95")):
            o = r[k]
            print("  %-20s size %3d: %4d filled markets, %d lost, $%.2f (%.2f/day = %.2f%%/day)" % (
                lab, r["sizes"][k], o["filled_markets"], o["lost_markets"], o["money"], o["per_day"], o["pct_per_day"]))
        print("  paper markets where a ladder bid LOST: %s" % (r["losers"] or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
