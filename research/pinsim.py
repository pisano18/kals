#!/usr/bin/env python3
# VERSION: 2026-09-10-ps1
"""pinsim.py -- THE BACKTEST THE OPERATOR ASKED FOR, AND HE WAS RIGHT.

His words, 2026-09-10:

    "I don't get why the backtest is so hard for you to do right, you must be
     over complicating it or doing it in a dumb way. It literally just 'its
     3:14:30, do I buy or no?' Then run the program we have. Then at 3:15 see
     the price that actually happened"

HE IS RIGHT AND THIS FILE IS THE ADMISSION. Before this, the decision was
REIMPLEMENTED three separate times -- pincross.passes_live_gate,
pintail.window_state + its own fair, pinfirst.crossings -- none of which ran
the code the bot runs. Three copies of one decision is three chances to
diverge from live, and divergence is the exact thing the backtest exists to
rule out. It already bit once: pinrun computes sigma as an sd about the mean
with (n-1), the tape stages used a plain RMS. They happened to agree to 0.08%.
That was luck, not design.

SO THIS FILE REIMPLEMENTS NOTHING. It calls pinrun's own functions:

    pinrun.fair()            the model
    pinrun.net_edge()        the edge test
    pinrun.expected_value()  the EV test
    pinrun.billed_fee()      the fee
    pinrun.PIN, PRICE_CEILING, EDGE_FLOOR, EV_FLOOR, TAU_MIN, TAU_MAX,
    MIN_FILL_FRAC, MIN_LEVEL, MAX_BOOK_AGE_MS, SIGMA_STRESS

and it feeds them from the tape through pinrun's OWN IndexWS class. The only
override is `spot()`, whose age is measured against wall-clock `time.time()`
in live and must be measured against the simulated second here. One method,
two lines, and it is the only place a divergence can hide.

NO LOOKAHEAD BY CONSTRUCTION: ticks are inserted into the index only as the
simulated clock reaches them, exactly as they arrive live. `partial()` and
`sigma()` are then the untouched live code reading an untouched live
structure.

WHAT THIS STILL CANNOT TELL US, and no replay can: whether the offer would
have been OURS. Live we fill 70% of the attempts we make. Every number here
assumes we win every race, so it is an UPPER BOUND and says so in its output.
"""
import argparse
import glob
import gzip
import json
import os
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                # noqa: E402
import pindata                                               # noqa: E402
import pinrules                                              # noqa: E402
from statistics import NormalDist                            # noqa: E402
_ND = NormalDist()

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
LIVE_FILL_RATE = 0.70          # measured: 50 fills from 72 attempts


class TapeIndex(pinrun.IndexWS):
    """pinrun's OWN index, fed from the tape.

    `spot()` is the single method that reads the wall clock, so it is the
    single method overridden. `partial()` and `sigma()` -- the two that
    actually decide the trade -- are inherited untouched, which is the whole
    point of this class existing.
    """

    def __init__(self, ids):
        super().__init__(ids)
        self.now = 0

    def spot(self, iid):
        s, v, _ = super().spot(iid)
        return (s, v, (self.now - s)) if s is not None else (None, None, None)

    def feed_upto(self, series_ticks, upto):
        """Insert every tick at or before `upto` and no others."""
        for iid, pend in series_ticks.items():
            while pend and pend[0][0] <= upto:
                sec, val = pend.pop(0)
                self.on_frame({"type": "cfbenchmarks_value",
                               "msg": {"index_id": iid,
                                       "data": json.dumps(
                                           {"time": sec * 1000,
                                            "value": str(val)})}})


def book_view(bk, now_ms):
    """pindata's rebuilt book in the shape pinrun's livebook.best() returns."""
    yb, nb = bk.best()
    out = {"suspect": False,
           "age_ms": (now_ms - bk.last_ts) if bk.last_ts else None}
    out["yes_ask"] = round(1.0 - nb, 4) if nb is not None else None
    out["yes_ask_size"] = bk.no.get(nb, 0.0) if nb is not None else 0.0
    out["no_ask"] = round(1.0 - yb, 4) if yb is not None else None
    out["no_ask_size"] = bk.yes.get(yb, 0.0) if yb is not None else 0.0
    return out


def decide(idx, iid, close_s, now_s, strike, digits, b, size):
    """EXACTLY pinrun's decision, by calling pinrun. Nothing reimplemented.

    Returns (want, price, take_n, fair) or (None, reason, None, fair).
    """
    sg = idx.sigma(iid)
    if sg is None:
        return None, "no_sigma", None, None
    f = pinrun.fair(idx, iid, close_s, now_s, strike,
                    sg * pinrun.SIGMA_STRESS, round_digits=digits)
    if f is None:
        return None, "no_fair", None, None
    want = price = avail = None
    if f >= pinrun.PIN:
        ya, ys = b.get("yes_ask"), b.get("yes_ask_size")
        if ya and ys and ya < 1.0:
            want, price, avail = "yes", ya, ys
    elif f <= 1.0 - pinrun.PIN:
        na, ns = b.get("no_ask"), b.get("no_ask_size")
        if na and ns and na < 1.0:
            want, price, avail = "no", na, ns
    if want is None:
        return None, ("no_offer" if (f >= pinrun.PIN or f <= 1 - pinrun.PIN)
                      else "undecided"), None, f
    take_n = min(float(size), float(avail))
    if take_n < max(pinrun.MIN_LEVEL, pinrun.MIN_FILL_FRAC * float(size)):
        return None, "too_shallow", None, f
    if price > pinrun.PRICE_CEILING:
        return None, "over_ceiling", None, f
    if pinrun.net_edge(f, price, want) < pinrun.EDGE_FLOOR:
        return None, "no_edge", None, f
    if pinrun.expected_value(price) < pinrun.EV_FLOOR:
        return None, "neg_ev", None, f
    return want, price, take_n, f


def record(f, want, price, take_n, avail, tau, series, sec, sg, spot,
           book_age_ms, index_age_s, cond=(None, None, None)):
    """THE DECISION RECORD -- the contract between live and replay
    (pinrules.FIELDS). Everything a rule may see, all backward-looking."""
    conf = f if want == "yes" else 1.0 - f
    cc = min(max(conf, 1e-12), 1 - 1e-12)
    return {
        "fair": round(f, 6), "conf": round(conf, 6),
        "margin_sd": round(_ND.inv_cdf(cc), 3), "want": want,
        "price": round(price, 4),
        "discount_c": round(100.0 * (conf - price), 2),
        "edge_c": round(100.0 * pinrun.net_edge(f, price, want), 3),
        "ev_c": round(100.0 * pinrun.expected_value(price), 3),
        "tau": int(tau), "depth": float(avail), "take_n": float(take_n),
        "coin": series, "hour_utc": time.gmtime(sec).tm_hour,
        "sigma": sg, "spot": spot,
        "cond_x": cond[0], "cond_n": cond[1], "cond_own": cond[2],
        "book_age_ms": book_age_ms, "index_age_s": index_age_s,
    }


def apply_profile(profile):
    """Run pinrun's OWN decision code under a profile's params -- the
    constants are module attributes read at call time, so setting them is
    exactly what a restart with those values would do."""
    for k, v in profile["params"].items():
        if hasattr(pinrun, k):
            # a schedule is resolved per decision (see resolve_for); the
            # module gets the schedule's default so nothing reads a dict
            setattr(pinrun, k, v["default"] if pinrules.is_schedule(v) else v)


def resolve_for(profile, rec):
    """Set the schedulable params for THIS decision from the record so far.
    SIZE by price, PRICE_CEILING by margin, SIGMA_STRESS by conditions -- the
    live code reads them as module constants, so they are set right before
    the decision and mean exactly what a restart with those values would."""
    for k in ("SIZE", "PRICE_CEILING", "SIGMA_STRESS", "MAX_PER_CLOSE",
              "MIN_FILL_FRAC", "IMPROVE_BY", "EDGE_FLOOR", "EV_FLOOR",
              "MEASURED_FLIP", "PIN"):
        v = profile["params"].get(k)
        if pinrules.is_schedule(v):
            setattr(pinrun, k, pinrules.resolve(profile, k, rec))


# ------------------------------------------------------------------ self-test
def selftest():
    print("SELF-TEST -- pinsim")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(TapeIndex.partial is pinrun.IndexWS.partial,
       "partial() is pinrun's own code, not a copy")
    ck(TapeIndex.sigma is pinrun.IndexWS.sigma,
       "sigma() is pinrun's own code, not a copy")
    ck(TapeIndex.spot is not pinrun.IndexWS.spot,
       "spot() is the ONLY override -- it is the only wall-clock read")

    C = 1_000_000
    ix = TapeIndex(["T"])
    pend = {"T": [(s, 100.0) for s in range(C - 400, C)]}
    ix.now = C - 30
    ix.feed_upto(pend, C - 30)
    ck(max(ix.ticks["T"]) == C - 30,
       f"NO LOOKAHEAD: at now=close-30 the index holds nothing past it "
       f"(newest {max(ix.ticks['T']) - C})")
    _, _, age = ix.spot("T")
    ck(age == 0, f"spot age is measured against the simulated clock ({age})")
    ix.now = C - 25
    ck(ix.spot("T")[2] == 5, "and it advances with it")

    # the decision must be pinrun's: a certain market with a cheap offer buys
    ix2 = TapeIndex(["T"])
    p2 = {"T": [(s, 100.0) for s in range(C - 700, C)]}
    ix2.now = C - 10
    ix2.feed_upto(p2, C - 10)
    b = {"yes_ask": 0.97, "yes_ask_size": 500.0, "no_ask": 0.02,
         "no_ask_size": 500.0, "age_ms": 5, "suspect": False}
    w, px, n, f = decide(ix2, "T", C, C - 10, 50.0, 2, b, 20)
    ck(w == "yes" and px == 0.97,
       f"a certain YES with a 97c offer is bought (got {w} {px}, fair {f})")
    b2 = dict(b, yes_ask=0.99)
    w2, why, _, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b2, 20)
    ck(w2 is None and why == "over_ceiling",
       f"and the same market at 99c is refused by pinrun's OWN ceiling "
       f"({pinrun.PRICE_CEILING}) -> {why}")
    b3 = dict(b, yes_ask_size=3.0)
    w3, why3, _, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b3, 20)
    ck(w3 is None and why3 == "too_shallow",
       f"and refused when only 3 contracts rest against size 20 -> {why3}")
    ck(abs(pinrun.PIN - 0.995) < 1e-9,
       f"and it is reading the LIVE gate right now ({pinrun.PIN})")

    # --- profiles: the same decision code under DATA ------------------------
    prof = pinrules.default_profile()
    r_ = record(1.0, "yes", 0.82, 20.0, 500.0, 21, "KXXRP15M", C - 21,
                0.00008, 1.39075, 2, 0.18)
    ck(set(r_) == set(pinrules.FIELDS),
       "record() produces EXACTLY the fields a rule may see -- no more, no less")
    v_, fired_ = pinrules.decide(prof, r_)
    ck(v_ == "refuse" and fired_ == [("dump", "refuse")],
       "the XRP loss, rebuilt as a decision record, is refused by the "
       "default profile's rule")
    saved = pinrun.PIN
    p2 = json.loads(json.dumps(prof))
    p2["params"]["PIN"] = 0.98
    apply_profile(p2)
    ck(abs(pinrun.PIN - 0.98) < 1e-12,
       "apply_profile() changes the live constant the decision code reads")
    w4, why4, _, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b2, 20)
    apply_profile(prof)
    ck(abs(pinrun.PIN - saved) < 1e-12,
       "and applying the default puts it back exactly")
    # a SIZE schedule by price changes what the live code takes
    p3 = json.loads(json.dumps(prof))
    p3["params"]["SIZE"] = {"by": "price", "default": 20,
                            "bands": [[0.50, 0.90, 60], [0.90, 0.99, 10]]}
    apply_profile(p3)
    resolve_for(p3, {"price": 0.85})
    w5, px5, n5, _ = decide(ix2, "T", C, C - 10, 50.0, 2,
                            dict(b, yes_ask=0.85), pinrun.SIZE)
    resolve_for(p3, {"price": 0.97})
    w6, px6, n6, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b, pinrun.SIZE)
    apply_profile(prof)
    ck(w5 == "yes" and n5 == 60 and w6 == "yes" and n6 == 10,
       f"SIZE by price: 60 contracts at 85c, 10 at 97c, through the live "
       f"decision code (got {n5}, {n6})")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ------------------------------------------------------------------ real data
def load_ticks(lo, hi):
    lo_h = time.strftime("%Y%m%dT%H", time.gmtime(lo - 3700))
    hi_h = time.strftime("%Y%m%dT%H", time.gmtime(hi + 60))
    out = defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(DATA, "cfbenchmarks_value",
                                            "2026*.jsonl.gz"))):
        if not (lo_h <= os.path.basename(fp)[:11] <= hi_h):
            continue
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        dd = json.loads(m["data"])
                        s = int(dd["time"]) // 1000
                    except Exception:
                        continue
                    if lo - 3700 <= s <= hi + 60:
                        out[m["index_id"]].append((s, float(dd["value"])))
        except (EOFError, zlib.error, OSError):
            pass
    for k in out:
        out[k].sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--size", type=float, default=None,
                    help="override the profile's SIZE")
    ap.add_argument("--profile", default="default",
                    help="profile name in profiles/ or a path")
    ap.add_argument("--end", default=None,
                    help="last book hour to include, e.g. 20260910T05")
    ap.add_argument("--json", default=None,
                    help="also write the summary as JSON here (the tool reads it)")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    profile = pinrules.load(a.profile)
    apply_profile(profile)
    if a.size is not None:
        pinrun.SIZE = a.size
    a.size = pinrun.SIZE
    print(f"\n  profile {profile['name']} sha {profile['_sha']}: "
          f"{len(profile['rules'])} rules, worst case "
          f"{pinrules.worst_case(profile['params'])}")

    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in pindata.SERIES_TO_INDEX and \
                    r.get("result") is not None:
                mk[r["ticker"]] = r
    bfiles = sorted(glob.glob(os.path.join(
        DATA, "orderbook_delta", "2026*.jsonl.gz")))[:-1]
    if a.end:
        bfiles = [f for f in bfiles if os.path.basename(f)[:11] <= a.end]
    bfiles = bfiles[-a.hours:]
    newest_settle = max(float(r["close"]) for r in mk.values())
    print(f"  newest settlement on file: "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(newest_settle))} "
          f"-- book hours after it cannot resolve and count as nothing")
    snaps = {os.path.basename(f)[:11]: f for f in sorted(glob.glob(
        os.path.join(DATA, "orderbook_snapshot", "2026*.jsonl.gz")))}
    print(f"\n  {len(mk):,} settled markets, {len(bfiles)} book hours, "
          f"size {a.size:g}, gate {pinrun.PIN}, ceiling {pinrun.PRICE_CEILING}")

    bought = []
    refused = []                 # the rules said no; outcome still resolved
    rule_tally = {}              # rule id -> every moment it fired on
    skips = defaultdict(int)
    bad_deltas = 0               # a swallowed parse error is not "no trades"
    decided = set()              # markets already bought or refused
    for bf in bfiles:
        stamp = os.path.basename(bf)[:11]
        # UTC, explicitly. time.mktime() is LOCAL time and time.timezone is
        # the non-DST offset, so on this box the hour landed 3600 s off and
        # every decision second found its index prints an hour stale -- 6,813
        # moments skipped as no_fair with nothing else wrong.
        import calendar
        hstart = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H"))
        ticks = load_ticks(int(hstart) - 400, int(hstart) + 3700)
        if not ticks:
            continue
        idx = TapeIndex(sorted(ticks))
        pend = {k: list(v) for k, v in ticks.items()}
        books = {}
        sf = snaps.get(stamp)
        if sf:
            try:
                with gzip.open(sf, "rt") as f:
                    for line in f:
                        if '"orderbook_snapshot"' not in line:
                            continue
                        try:
                            d = json.loads(line)
                            m = d["msg"]
                        except Exception:
                            continue
                        tk = m.get("market_ticker")
                        if tk in mk:
                            books.setdefault(tk, pindata.Book()).snapshot(
                                m, d.get("ts_ms") or 0)
            except (EOFError, zlib.error, OSError):
                pass
        # walk the deltas in order, and at each second decide on every market
        last_sec = None
        try:
            with gzip.open(bf, "rt") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    ts = int(m.get("ts_ms") or 0)
                    if tk in mk and ts:
                        bk = books.setdefault(tk, pindata.Book())
                        # VERBATIM from pindata's replay, the reader that was
                        # fixed on 2026-09-10. The tape says `price_dollars`;
                        # a first version of this read `price_dollars_fp`,
                        # every delta raised, the except swallowed it, and six
                        # settled hours "bought 0" -- the exact shape of the
                        # bug that broke the old backtest for weeks.
                        try:
                            bk.delta(str(m.get("side", "")).lower(),
                                     m.get("price_dollars", m.get("price")),
                                     m.get("delta_fp", m.get("delta")) or 0.0,
                                     ts)
                        except Exception:
                            bad_deltas += 1
                    sec = ts // 1000
                    if sec == last_sec or not sec:
                        continue
                    last_sec = sec
                    idx.now = sec
                    idx.feed_upto(pend, sec)
                    for tkk, bkk in books.items():
                        r = mk[tkk]
                        cs = int(float(r["close"]))
                        tau = cs - sec
                        if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                            continue
                        # one decision per market: bought OR refused. A first
                        # version only excluded bought markets, so a refused
                        # one was re-refused every second and one market
                        # counted 16 times in a rule's tally.
                        if tkk in decided:
                            continue
                        iid = pindata.SERIES_TO_INDEX[r["series"]]
                        if iid not in idx.ticks:
                            continue
                        b = book_view(bkk, ts)
                        if b["age_ms"] is None or \
                                b["age_ms"] > pinrun.MAX_BOOK_AGE_MS:
                            skips["stale_book"] += 1
                            continue
                        # SCHEDULES resolve on what is known BEFORE deciding:
                        # the model's view and the offer in front of it.
                        sg0 = idx.sigma(iid)
                        f0 = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                                         (sg0 or 0) * pinrun.SIGMA_STRESS,
                                         round_digits=pindata.ROUND_DIGITS.get(
                                             r["series"])) if sg0 else None
                        if f0 is not None:
                            side0 = "yes" if f0 >= 0.5 else "no"
                            px0 = b.get(f"{side0}_ask")
                            _, spot0, iage0 = idx.spot(iid)
                            pre = record(f0, side0, px0 or 0.0, 0.0,
                                         b.get(f"{side0}_ask_size") or 0.0,
                                         tau, r["series"], sec, sg0, spot0,
                                         b["age_ms"], iage0)
                            resolve_for(profile, pre)
                        w, px, n, fv = decide(
                            idx, iid, cs, sec, float(r["strike"]),
                            pindata.ROUND_DIGITS.get(r["series"]), b,
                            pinrun.SIZE)
                        if w is None:
                            skips[px] += 1
                            continue
                        res = r["result"]
                        yes = (str(res).lower() == "yes") if \
                            isinstance(res, str) else float(res) >= 0.5
                        won = (yes == (w == "yes"))
                        # THE PROFILE'S RULES, on the same record live sees
                        sg_ = idx.sigma(iid)
                        _, spot_, iage_ = idx.spot(iid)
                        rc = record(fv, w, px, n, b.get(f"{w}_ask_size"),
                                    tau, r["series"], sec, sg_, spot_,
                                    b["age_ms"], iage_)
                        verdict, fired = pinrules.decide(profile, rc)
                        pnl = (n * (1 - px) if won else -n * px) - \
                            pinrun.billed_fee(px, n)
                        for rid, act in fired:
                            rt = rule_tally.setdefault(rid, [])
                            rt.append((cs, act, won, pnl, px))
                        decided.add(tkk)
                        if verdict == "refuse":
                            refused.append((tkk, w, px, n, tau, won, pnl, cs))
                            continue
                        bought.append((tkk, w, px, n, tau, won, pnl, cs))
        except (EOFError, zlib.error, OSError):
            pass
        print(f"    {stamp}  bought {len(bought):,}", flush=True)

    if bad_deltas:
        print(f"  *** {bad_deltas:,} DELTAS FAILED TO PARSE -- the book is "
              f"incomplete and every number below is suspect ***")
    if not bought and not refused:
        print(f"  loaded nothing -- skips: {dict(skips)}")
        return
    summary = report(bought, refused, rule_tally, skips, profile, a)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=1)
        print(f"  summary written to {a.json}")


def _stats(rows):
    """fills / closes / wins / losses / P&L / mean price / loss-rate CI."""
    from pincross import cp_interval
    if not rows:
        return {"fills": 0, "closes": 0, "wins": 0, "losses": 0, "pnl": 0.0,
                "mean_price": None, "loss_rate": None, "ci": None}
    L = [x for x in rows if not x[5]]
    lo, hi = cp_interval(len(L), len(rows))
    return {"fills": len(rows), "closes": len(set(x[7] for x in rows)),
            "wins": len(rows) - len(L), "losses": len(L),
            "pnl": round(sum(x[6] for x in rows), 2),
            "mean_price": round(100 * sum(x[2] for x in rows) / len(rows), 2),
            "loss_rate": round(100 * len(L) / len(rows), 2),
            "ci": [round(100 * lo, 2), round(100 * hi, 2)]}


def _line(tag, s):
    if not s["fills"]:
        return f"  {tag:<34}{'--':>8}"
    return (f"  {tag:<34}{s['fills']:>6} fills {s['closes']:>5} closes "
            f"{s['wins']:>5}W {s['losses']:>3}L  {s['loss_rate']:>6.2f}% "
            f"[{s['ci'][0]:.2f}, {s['ci'][1]:.2f}]  ${s['pnl']:>+9.2f}  "
            f"{s['mean_price']:>6.2f}c")


def report(bought, refused, rule_tally, skips, profile, a):
    """FIT and HOLDOUT side by side, always. n as markets AND closes. Every
    rate with its interval. The 70%-fill pair. Per rule, the would-be outcome
    of everything it fired on, so a tracker and a refusal read the same."""
    allrows = bought + refused
    closes = sorted(set(x[7] for x in allrows))
    cut = closes[int(0.70 * len(closes))] if closes else 0
    fit = [x for x in bought if x[7] < cut]
    hold = [x for x in bought if x[7] >= cut]
    S = {"profile": profile["name"], "sha": profile["_sha"],
         "size": a.size, "hours": a.hours, "split_close": cut,
         "traded": {"all": _stats(bought), "fit": _stats(fit),
                    "holdout": _stats(hold)},
         "refused": _stats(refused), "skips": dict(skips), "rules": {}}
    print(f"\n  {'='*100}")
    print(f"  PROFILE {profile['name']} (sha {profile['_sha']}), size "
          f"{a.size:g}, {a.hours} book hours -- UPPER BOUND: every offer "
          f"assumed ours; live we fill ~{100*LIVE_FILL_RATE:.0f}%")
    print(f"  {'='*100}")
    print(_line("TRADED, all", S["traded"]["all"]))
    print(_line("  fit (first 70% of closes)", S["traded"]["fit"]))
    print(_line("  HOLDOUT (last 30%)", S["traded"]["holdout"]))
    pa = S["traded"]["all"]["pnl"]
    print(f"  at the {100*LIVE_FILL_RATE:.0f}% live fill rate: "
          f"${pa*LIVE_FILL_RATE:+,.2f}")
    print(_line("REFUSED by rules (would-be)", S["refused"]))
    print(f"\n  PER RULE -- what it fired on, and what would have happened")
    for r in profile["rules"]:
        rows = rule_tally.get(r["id"], [])
        conv = [(None, None, px, None, None, won, pnl, cs)
                for cs, act, won, pnl, px in rows]
        f_ = [x for x in conv if x[7] < cut]
        h_ = [x for x in conv if x[7] >= cut]
        S["rules"][r["id"]] = {"name": r.get("name", r["id"]),
                               "action": r["action"],
                               "all": _stats(conv), "fit": _stats(f_),
                               "holdout": _stats(h_)}
        print(_line(f"{r['id']} [{r['action']}] all", S["rules"][r["id"]]["all"]))
        print(_line(f"    fit", S["rules"][r["id"]]["fit"]))
        print(_line(f"    HOLDOUT", S["rules"][r["id"]]["holdout"]))
    print(f"\n  why other moments did not fire: {dict(skips)}")
    L = [x for x in bought if not x[5]]
    for t, w, px, n, tau, won, pnl, cs in L[:20]:
        print(f"    LOSS {t[:28]:<29} {w:>3} {100*px:>5.1f}c tau {tau:>2} "
              f"${pnl:+.2f}")
    return S


if __name__ == "__main__":
    main()
