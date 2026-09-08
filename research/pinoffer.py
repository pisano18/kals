#!/usr/bin/env python3
# VERSION: 2026-09-08-po1
"""pinoffer.py -- is the losing side of a decided market actually EMPTY?

THE QUESTION. The live runner reports most refusals as `no_offer`: the model
reached its 98% gate but nobody was offering the winning side. That is either a
market fact (a CAPACITY limit that no parameter change can fix) or a bug in how
we read the book (in which case we are blind and every no_offer is wrong).

THE CONTROL IS THE WHOLE POINT. "The losing side is empty" is only meaningful if
the replay populated the WINNING side in the same moment. If BOTH sides come
back empty, the Book never filled and the reading proves nothing. So this file
measures three numbers, not one, and the middle one is the control.

MEASURED 2026-09-08 over 33,431 decided moments on eight closes:
    winning side has bids   33,431   100.00%   (median 84 price levels)
    LOSING side has bids          4     0.01%   (all at 99.90c)
    both sides empty              0     0.00%   <- the control, clean
So it is a market fact. To buy the winner somebody must hold the loser, and
once an outcome is obvious nobody will at any price.
"""
import argparse
import glob, gzip, json, math, os, sys, time, zlib
sys.path.insert(0, r"C:\kals-repo\research")
from pindata import Book, load_index, idx_feats, partial, eff_strike, \
    SERIES_TO_INDEX, ROUND_DIGITS
from engine import var_factor, N_AVG
from statistics import NormalDist
ND = NormalDist(); DATA = r"C:\kals\kalshi_data"

def main():
    mk = json.load(open(r"C:\kals-repo\results\_tmp_closes.json", encoding="utf-8"))
    TARGETS = sorted({v["close"] for v in mk.values()})
    idx, _ = load_index(300)
    snaps = {os.path.basename(f)[:11]: f for f in
             glob.glob(os.path.join(DATA, "orderbook_snapshot", "2026*.jsonl.gz"))}
    hours = sorted({time.strftime("%Y%m%dT%H", time.gmtime(c)) for c in TARGETS})
    S = {"dec":0, "win_empty":0, "lose_empty":0, "both_empty":0, "win_lv":[], "lose_px":[]}
    for h in hours:
        cands = glob.glob(os.path.join(DATA, "orderbook_delta", h + "*.jsonl.gz"))
        if not cands: continue
        books = {}
        sf = snaps.get(h)
        if sf:
            try:
                with gzip.open(sf, "rt") as fh:
                    for line in fh:
                        if '"orderbook_snapshot"' not in line: continue
                        try: m = json.loads(line)["msg"]
                        except Exception: continue
                        if m.get("market_ticker") in mk:
                            books.setdefault(m["market_ticker"], Book()).snapshot(m, int(m.get("ts_ms") or 0))
            except (EOFError, zlib.error, OSError): pass
        try:
            with gzip.open(cands[0], "rt") as fh:
                for line in fh:
                    if '"orderbook_delta"' not in line: continue
                    try: m = json.loads(line)["msg"]
                    except Exception: continue
                    tk = m.get("market_ticker"); rec = mk.get(tk)
                    if rec is None: continue
                    ts = int(m.get("ts_ms") or 0)
                    bk = books.setdefault(tk, Book())
                    try:
                        bk.delta(str(m.get("side","")).lower(),
                                 m.get("price_dollars", m.get("price")),
                                 m.get("delta_fp", m.get("delta")) or 0.0, ts)
                    except Exception: continue
                    sec = ts//1000; close_s = rec["close"]; tau = close_s-sec
                    if not (3 <= tau <= 30): continue
                    iid = SERIES_TO_INDEX[rec["series"]]
                    if iid not in idx: continue
                    base, arr = idx[iid]
                    pa = partial(base, arr, close_s, sec)
                    if pa is None: continue
                    locked, rr, _ = pa
                    if rr < 1: continue
                    fe = idx_feats(base, arr, sec)
                    if fe is None or not fe["sigma"]: continue
                    mu=(locked+rr*fe["spot"])/N_AVG
                    rd=rec.get("round_digits")
                    K=eff_strike(rec["strike"], int(rd) if rd is not None else ROUND_DIGITS.get(rec["series"]))
                    req=(60.0/rr)*(K-mu)
                    sd=fe["sigma"]*math.sqrt(var_factor(int(rr),[1.0]))*(60.0/rr)
                    if sd<=0: continue
                    pf=(1-ND.cdf(req/sd)) if req>0 else ND.cdf(req/sd)
                    if pf>0.02: continue
                    S["dec"]+=1
                    side_yes = req<=0
                    win  = bk.yes if side_yes else bk.no   # BIDS for the winner
                    lose = bk.no  if side_yes else bk.yes  # BIDS for the loser = our ask
                    we, le = (not win), (not lose)
                    S["win_empty"]+=we; S["lose_empty"]+=le; S["both_empty"]+= (we and le)
                    if win:  S["win_lv"].append(len(win))
                    if lose: S["lose_px"].append(round(1-max(lose.keys()),4))
        except (EOFError, zlib.error, OSError): pass
        books.clear()

    d=S["dec"] or 1
    print(f"\n  {S['dec']:,} decided moments reconstructed from the tape\n")
    print(f"  {'winning side has bids':<38}{d-S['win_empty']:>9,}  {100*(d-S['win_empty'])/d:>6.2f}%")
    print(f"  {'LOSING side has bids (= we can buy)':<38}{d-S['lose_empty']:>9,}  {100*(d-S['lose_empty'])/d:>6.2f}%")
    print(f"  {'BOTH sides empty (replay artefact)':<38}{S['both_empty']:>9,}  {100*S['both_empty']/d:>6.2f}%")
    if S["win_lv"]:
        w=sorted(S["win_lv"]); print(f"\n  median price levels on the winning side: {w[len(w)//2]}")
    if S["lose_px"]:
        p=sorted(S["lose_px"]); print(f"  the {len(p)} buyable moments priced: min {100*p[0]:.2f}c  median {100*p[len(p)//2]:.2f}c")
    print()
    if S["both_empty"] > 0.5*d:
        print("  *** ARTEFACT *** both sides empty most of the time -- my replay never")
        print("  populated the book, so the no_offer reading proves nothing.")
    elif (d-S["win_empty"]) > 0.5*d and (d-S["lose_empty"]) < 0.05*d:
        print("  CONFIRMED, and it is a MARKET fact, not a replay artefact: the winning")
        print("  side is quoted while the LOSING side's book is empty. In a decided")
        print("  market nobody will take the losing side, so there is nothing to buy.")
    else:
        print("  INCONCLUSIVE -- neither pattern is clean. Reporting that, not a verdict.")


def selftest():
    """Plant three worlds where the answer is known and refuse real data unless
    all three are recovered. The NULL world is the important one: a replay that
    reads nothing must NOT be reported as an empty market."""
    print("SELF-TEST -- pinoffer")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    def classify(win, lose):
        """The exact three-way split main() uses."""
        we, le = (not win), (not lose)
        return {"win_empty": we, "lose_empty": le, "both_empty": we and le}

    # WORLD 1 -- a decided market: winner richly quoted, loser empty.
    d = classify({0.99: 50.0, 0.98: 120.0}, {})
    ck(not d["win_empty"] and d["lose_empty"] and not d["both_empty"],
       "a decided market reads as 'winner quoted, loser empty' -- the real finding")

    # WORLD 2 -- THE NULL. A broken replay, where nothing was ever populated.
    d = classify({}, {})
    ck(d["both_empty"],
       "a BROKEN REPLAY reads as both-empty and must NOT be reported as an "
       "empty market -- this is the control that makes the result mean anything")

    # WORLD 3 -- a two-sided market, which must NOT look like the finding.
    d = classify({0.99: 50.0}, {0.02: 30.0})
    ck(not d["win_empty"] and not d["lose_empty"] and not d["both_empty"],
       "a healthy two-sided market plants NOTHING and the estimator finds "
       "nothing -- no false positive")

    # the price conversion: our ask = 1 - the best bid on the losing side
    lose = {0.005: 10.0, 0.02: 30.0, 0.01: 5.0}
    ck(round(1 - max(lose.keys()), 4) == 0.98,
       "our purchase price is 1 minus the HIGHEST bid on the losing side "
       f"(got {round(1 - max(lose.keys()), 4)})")

    # a guard that discards everything must be visible, per the repo rule
    ck(classify({}, {0.02: 1.0})["win_empty"],
       "a moment with a loser bid but NO winner quote is counted as "
       "win_empty, so a one-sided replay failure cannot masquerade as a finding")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


if __name__ == "__main__":
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--selftest", action="store_true")
    _a, _rest = _ap.parse_known_args()
    if _a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    main()
