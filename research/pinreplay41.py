#!/usr/bin/env python3
"""pinreplay41.py -- what would AMENDMENT 40 (the jump gate) and AMENDMENT 41
(post-jump widening) have done to the trades we ACTUALLY MADE on a given day?

THE OPERATOR'S QUESTION, 2026-09-14: "What would've happened if it ran today
vs what did happen?"

WHAT THIS IS. Decision reproduction through the bot's own functions --
`pinrun.fair`, `pinrun.IndexWS`, `pinrun.jump_against`, the live constants --
fed the settlement index as it stood at each second. Per CLAUDE.md
(2026-09-10) that is the one use of replay the repo certifies. It is NOT a
backtest of what the bot would have bought instead: both amendments only
REFUSE entries or fire the hedge EARLIER, so the full effect on our own fills
is (a) which fills would not have happened, with their real P&L, and (b) on
the fills that would, when the hedge would have fired.

WHAT IT CANNOT SAY. The hedge PRICE at an earlier second -- that needs the
order book at that second, which the live log does not hold. So "hedge fires
k seconds earlier" is reported as seconds, and the tape's measured ~17c per
tier is quoted as the expected value of a second, not asserted for the trade.

NO LOOKAHEAD, BY CONSTRUCTION. `fair()` reads the newest print in the index
object, so for every second t the index object is rebuilt holding only prints
<= t. A self-test plants a future print and proves it is invisible.

    python research/pinreplay41.py --selftest
    python research/pinreplay41.py --day 2026-09-14          # ET day
"""
import collections
import datetime as dt
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinrun                                                 # noqa: E402
import idxload                                                # noqa: E402
import replay                                                 # noqa: E402

PIN = pinrun.PIN
HEDGE_AT = pinrun.HEDGE_BELIEF
TAU_MIN = pinrun.TAU_MIN


def index_upto(iid, dense, lo, t):
    """A pinrun.IndexWS holding this index's prints in [lo, t] and nothing
    later -- what the bot could see at second t."""
    ix = pinrun.IndexWS([iid])
    for s in range(lo, t + 1):
        v = dense.get(s)
        if v is not None:
            ix.ticks[iid][s] = v
    return ix


def widen_at(ix, iid, sg):
    """The A41 multiplier at this second: 2.0 if any of the last 5 adjacent
    one-second moves is >= 3 sd in either direction."""
    for m in ix.recent_moves(iid, pinrun.JUMP_WIDEN_WINDOW):
        if abs(m) / sg >= pinrun.JUMP_SIGMA:
            return pinrun.JUMP_WIDEN
    return 1.0


def belief(ix, iid, close_s, t, strike, sg, digits, want):
    f = pinrun.fair(ix, iid, close_s, t, strike, sg, round_digits=digits)
    if f is None:
        return None
    return f if want == "yes" else 1.0 - f


def walk(iid, dense, close_s, t0, strike, sg, digits, want, factor_fn):
    """From the signal second to close-TAU_MIN: the first second belief falls
    under the hedge line, or None. `factor_fn(ix)` gives the sigma multiplier."""
    lo = close_s - 70
    for t in range(t0, close_s - TAU_MIN + 1):
        ix = index_upto(iid, dense, lo, t)
        b = belief(ix, iid, close_s, t, strike, sg * factor_fn(ix), digits, want)
        if b is not None and b < HEDGE_AT:
            return t
    return None


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # a dense index: flat, then the BTC-shaped jump, then a FUTURE print
    base = 3_000_000 - (3_000_000 % 900)
    close = base + 900
    D = idxload.Dense("T", close - 100, 200)
    K = 100.0
    for s in range(close - 100, close - 13):
        D.v[s - D.base] = K - 0.5
    D.v[(close - 13) - D.base] = K + 0.6          # the jump second
    D.v[(close - 12) - D.base] = K + 50.0         # the FUTURE, must be invisible at t=close-13
    sg = 0.1                                       # so +1.1 is an 11-sd jump
    ix = index_upto("T", D, close - 70, close - 13)
    ck(ix.spot("T")[0] == close - 13 and ix.spot("T")[1] == K + 0.6,
       "NO LOOKAHEAD: the index object at t holds t as its newest print, not "
       "the +50 planted one second later")
    ck(len(ix.recent_moves("T", 3)) == 3 and abs(ix.recent_moves("T", 3)[0] - 1.1) < 1e-9,
       "recent_moves sees the +1.1 jump as the newest move")
    ck(widen_at(ix, "T", sg) == pinrun.JUMP_WIDEN,
       "an 11-sd jump inside the window widens by %.1f" % pinrun.JUMP_WIDEN)
    b1 = belief(ix, "T", close, close - 13, K, sg, None, "no")
    b2 = belief(ix, "T", close, close - 13, K, sg * pinrun.JUMP_WIDEN, None, "no")
    ck(b1 is not None and b2 is not None and b2 < b1,
       "widened belief is lower on the jump shape (%.4f -> %.4f)" % (b1, b2))
    ck(pinrun.jump_against([1.1, 0.0, 0.0], sg, "no") >= pinrun.JUMP_SIGMA,
       "the gate would refuse a NO buy right after that up-jump")
    ck(pinrun.jump_against([1.1, 0.0, 0.0], sg, "yes") < pinrun.JUMP_SIGMA,
       "and would not refuse a YES buy -- the sign follows the side (the "
       "up-jump reads as -11 sd for YES; the other two moves are 0, so the "
       "max is 0, well under the 3 sd bar)")
    # a calm index: neither rule touches it, and the walk never fires
    D2 = idxload.Dense("C", close - 100, 200)
    for s in range(close - 100, close + 1):
        D2.v[s - D2.base] = K - 0.5 + (0.01 if s % 2 else 0.0)
    ix2 = index_upto("C", D2, close - 70, close - 20)
    ck(widen_at(ix2, "C", sg) == 1.0, "NULL: a calm index never widens")
    ck(walk("C", D2, close, close - 20, K, sg, None, "no", lambda ix: 1.0) is None
       and walk("C", D2, close, close - 20, K, sg, None, "no", lambda ix: widen_at(ix, "C", sg)) is None,
       "NULL: on a calm index neither model ever crosses the hedge line")
    print("pinreplay41 selftest:", "OK" if ok else "FAILED")
    return ok


def load_fills(day_et):
    """Today's live entry fills joined to their signal and settlement."""
    d0 = dt.datetime.strptime(day_et, "%Y-%m-%d")
    lo = (d0 + dt.timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")     # ET midnight = 04:00Z (EDT)
    hi = (d0 + dt.timedelta(hours=28)).strftime("%Y-%m-%dT%H:%M")
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "..", "results", "pinrun-live-*.jsonl"))):
        sig, res, orders = {}, {}, []
        for line in open(p, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            k = d.get("kind")
            if k == "signal":
                sig.setdefault(d["ticker"], d)
            elif k == "order" and (d.get("filled") or 0) > 0:
                orders.append(d)
            elif k == "settled":
                res[(d["ticker"], d.get("want"))] = d.get("result")
        for o in orders:
            s = sig.get(o["ticker"])
            if not s or not (lo <= s["t"] < hi):
                continue
            r = res.get((o["ticker"], s["want"]))
            if r is None:
                continue
            won = (r == s["want"])
            n, px, fee = o["filled"], o["exec_price"], o.get("fee_total") or 0
            out.append(dict(sig=s, n=n, px=px, won=won,
                            pnl=(n * (1 - px) - fee) if won else -(n * px + fee)))
    return out


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    day = sys.argv[sys.argv.index("--day") + 1] if "--day" in sys.argv else \
        dt.datetime.utcnow().strftime("%Y-%m-%d")
    fills = load_fills(day)
    if not fills:
        print("loaded nothing -- no live fills on", day)
        return 0
    idx = idxload.load(list(replay.SERIES_TO_INDEX.values()), verbose=False)

    rows = []
    for f in fills:
        s = f["sig"]
        iid = replay.SERIES_TO_INDEX.get(s["ticker"].split("-")[0])
        D = idx.get(iid)
        sg, strike, digits, want = s.get("sigma"), s.get("strike"), s.get("digits"), s["want"]
        if D is None or not sg or strike is None:
            continue
        t0 = int(dt.datetime.strptime(s["t"][:19], "%Y-%m-%dT%H:%M:%S")
                 .replace(tzinfo=dt.timezone.utc).timestamp())
        close_s = int(round((t0 + s["tau"]) / 900.0)) * 900
        ix = index_upto(iid, D, close_s - 70, t0)
        b_logged = (1 - s["fair"]) if want == "no" else s["fair"]
        b_base = belief(ix, iid, close_s, t0, strike, sg, digits, want)
        wf = widen_at(ix, iid, sg)
        b_wide = belief(ix, iid, close_s, t0, strike, sg * wf, digits, want)
        gate = pinrun.jump_against(ix.recent_moves(iid, pinrun.JUMP_LOOKBACK), sg, want)
        refused_gate = gate is not None and gate >= pinrun.JUMP_SIGMA
        refused_wide = b_wide is not None and b_wide < PIN
        h_base = walk(iid, D, close_s, t0 + 1, strike, sg, digits, want, lambda ix: 1.0)
        h_wide = walk(iid, D, close_s, t0 + 1, strike, sg, digits, want,
                      lambda ix, iid=iid, sg=sg: widen_at(ix, iid, sg))
        rows.append(dict(f=f, coin=s["ticker"].split("15M")[0][2:], t=s["t"][11:19],
                         tau=s["tau"], b_logged=b_logged, b_base=b_base, b_wide=b_wide,
                         wf=wf, gate=gate, rg=refused_gate, rw=refused_wide,
                         h_base=h_base, h_wide=h_wide, close_s=close_s))

    print("\n%s ET: %d live entry fills reproduced through pinrun.fair()\n" % (day, len(rows)))
    # certification: does the replayed belief match the logged one?
    diffs = [abs(r["b_base"] - r["b_logged"]) for r in rows if r["b_base"] is not None]
    print("  REPRODUCTION CHECK: replayed belief vs the belief the bot logged at the time")
    print("    max difference %.5f, median %.5f over %d fills  (the bot's own number, "
          "rebuilt from the index -- small means the replay is faithful)\n"
          % (max(diffs), sorted(diffs)[len(diffs) // 2], len(diffs)))

    tot = sum(r["f"]["pnl"] for r in rows)
    print("  WHAT HAPPENED: %d fills, net $%+.2f, %d losses\n"
          % (len(rows), tot, sum(1 for r in rows if not r["f"]["won"])))

    for name, key in (("A40 JUMP GATE", "rg"), ("A41 WIDENING", "rw")):
        ref = [r for r in rows if r[key]]
        print("  %s would have REFUSED %d of %d fills:" % (name, len(ref), len(rows)))
        for r in ref:
            print("    %-5s %s tau %2d  %s  $%+7.2f   %s"
                  % (r["coin"], r["t"], r["tau"], "LOST" if not r["f"]["won"] else "won ",
                     r["f"]["pnl"],
                     ("jump %+.1f sd against" % r["gate"]) if key == "rg"
                     else ("belief %.4f -> %.4f widened" % (r["b_base"], r["b_wide"]))))
        kept = tot - sum(r["f"]["pnl"] for r in ref)
        print("    -> net would have been $%+.2f instead of $%+.2f (%+.2f)\n"
              % (kept, tot, kept - tot))
    both = [r for r in rows if r["rg"] or r["rw"]]
    kept = tot - sum(r["f"]["pnl"] for r in both)
    print("  BOTH together refuse %d fills -> net $%+.2f instead of $%+.2f (%+.2f)\n"
          % (len(both), kept, tot, kept - tot))

    print("  THE HEDGE, on the fills that would still have been made:")
    print("    first second belief falls under %.2f -- baseline model vs widened model\n" % HEDGE_AT)
    print("    %-5s %-8s %-4s %8s %8s %8s   %s" % ("coin", "signal", "res", "baseline", "widened", "earlier", ""))
    new_false = []
    for r in rows:
        if r["rg"] or r["rw"]:
            continue
        hb, hw = r["h_base"], r["h_wide"]
        if hb is None and hw is None:
            continue
        lab = "LOST" if not r["f"]["won"] else "won"
        e = "" if (hb is None or hw is None) else "%+ds" % (hb - hw)
        flag = ""
        if r["f"]["won"] and hb is None and hw is not None:
            flag = "  <-- NEW false hedge the widened model would fire"
            new_false.append(r)
        if r["f"]["won"] and hb is not None and hw is not None:
            flag = "  (false alarm under both)"
        if not r["f"]["won"] and hw is not None and (hb is None or hw < hb):
            flag = "  <-- hedge fires EARLIER on a real loss"
        def sec(t):
            return "-" if t is None else ("%ds left" % (r["close_s"] - t))
        print("    %-5s %-8s %-4s %8s %8s %8s%s" % (r["coin"], r["t"], lab, sec(hb), sec(hw), e, flag))
    print("\n    new false hedges the widening would have added on today's winners: %d" % len(new_false))
    print("    (each costs roughly the hedge premium, ~20-40c a contract on the tape;")
    print("     each earlier real-loss hedge is worth ~17c a contract per second on the tape)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
