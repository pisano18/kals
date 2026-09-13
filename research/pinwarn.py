#!/usr/bin/env python3
# VERSION: 2026-09-13-wn1
"""pinwarn.py -- does the model's OWN CONFIDENCE warn us before a flip?

THE OPERATOR'S CLAIM, 2026-09-13: "you can buy the same coin again if all the
metrics line up and it's something you'd usually buy and it's under the
contract threshold, because if it's really going to flip then the confidence
should be dropping. Can you check and see if this is really the case."

It is exactly the right question, because it decides whether the GATE is its
own protection against buying more of a position that is turning against us.

WHY THE OBVIOUS MEASUREMENT IS WORTHLESS HERE, and this file exists because I
made it first. `pinlevels_rows.jsonl` holds every candidate the gate passed --
and only those. Its minimum confidence across 16,683 rows is 0.995002, because
a row is not written unless the model was ALREADY certain. Asking that file
"did confidence ever fall below 0.995" returns "never, 0 of 16,683", which is a
statement about the file and not about the world. CENSORED DATA, and it would
have confirmed the claim beautifully.

WHAT THIS DOES INSTEAD. It recomputes the model's confidence from the INDEX at
every second of the final window, for every close, whether or not anything was
ever offered and whether or not the gate would have passed it. Nothing is
filtered, so a fall below the gate is visible when it happens.

  strike  = the previous window's settlement. CLAUDE.md's settlement model:
            strike(N+1) == settle(N), exactly.
  fair    = pinrun's own arithmetic, mu = (locked + tau*spot)/60 over
            sd = sigma*sqrt(var_factor(tau)).
  outcome = settle vs strike, from the index.

THE QUESTION IN ONE LINE: among closes the model's side LOST, how often had its
confidence already fallen below the gate, and with how many seconds to spare?
If the answer is "almost always, with time to spare", the gate protects a
second buy and the operator is right. If it is "rarely, or far too late", the
gate is blind and a second buy loads money into exactly the closes that fail.
"""
import argparse
import glob
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pincalib                                                # noqa: E402
import gzsalvage                                               # noqa: E402
from engine import var_factor, N_AVG                           # noqa: E402

PIN = 0.995
TAUS = (30, 25, 20, 15, 10, 7, 5, 3)
WINDOW = 60


def load_one_index(data_dir, index_id):
    """{second: value} for ONE index id -- one coin at a time, because
    loading twelve got an earlier job killed for memory."""
    out = {}
    key = '"%s"' % index_id
    for path in sorted(glob.glob(os.path.join(data_dir, "cfbenchmarks_value",
                                              "*.jsonl.gz"))):
        for line in gzsalvage.iter_lines(path):
            if key not in line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            d = m.get("msg") or {}
            if d.get("index_id") != index_id:
                continue
            inner = d.get("data")
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except ValueError:
                    continue
            if not isinstance(inner, dict):
                continue
            try:
                out[int(round(float(inner["time"]) / 1000.0))] = float(
                    inner["value"])
            except (KeyError, TypeError, ValueError):
                continue
    return out


def confidence(ser, close_s, tau, strike):
    """The model's confidence in ITS OWN CALLED SIDE at `tau` seconds out.

    Uncensored: computed whether or not anything was offered and whether or
    not it clears any gate.
    """
    now = close_s - tau
    spot = ser.get(now - 1)
    if spot is None:
        return None
    locked = 0.0
    for s in range(close_s - WINDOW, close_s - tau):
        v = ser.get(s)
        if v is None:
            return None
        locked += v
    sg = pincalib.sigma_at(ser, now - 1)
    if not sg:
        return None
    sd = sg * math.sqrt(var_factor(int(tau), [1.0]))
    if sd <= 0:
        return None
    z = (locked + tau * spot) / float(N_AVG) - strike
    # P(settle >= strike). NOT max(p, 1-p): that is confidence in whatever the
    # model believes RIGHT NOW, which stays near 1.0 while the model quietly
    # flips to the opposite side -- and the flip is the entire thing being
    # measured. The caller converts this to confidence in the side ALREADY
    # BOUGHT, which is the only side money is on.
    return pincalib.norm_cdf(z / sd)


def walk(ser, taus=TAUS):
    """One record per complete close, with UNCENSORED confidence at every tau.

    [{close, settle, strike, conf: {tau: P(settle >= strike)}}]
    """
    out = []
    if not ser:
        return out
    lo, hi = min(ser), max(ser)
    c = lo - (lo % 900) + 900
    prev_settle = None
    while c <= hi:
        settle = pincalib.settle_of(ser, c)
        if settle is None or prev_settle is None:
            if settle is not None:
                prev_settle = settle
            c += 900
            continue
        strike = prev_settle
        conf = {}
        for tau in taus:
            r = confidence(ser, c, tau, strike)
            if r is not None:
                conf[tau] = r                       # P(up), not confidence
        if conf:
            out.append({"close": c, "settle": settle, "strike": strike,
                        "conf": conf})
        prev_settle = settle
        c += 900
    return out


def entries(rows, pin=PIN, taus=TAUS):
    """The closes the bot would actually have BOUGHT, and what happened next.

    `t_in` is the EARLIEST tau at which confidence clears the gate -- the
    first moment a buy could occur. The called side is fixed there, because
    that is the side money is now on; a later reading is a warning about that
    position, not a fresh opinion.

    Returns [{t_in, up, won, conf}].
    """
    out = []
    for r in rows:
        t_in = None
        for tau in sorted(r["conf"], reverse=True):       # 30, 25, 20, ...
            p = r["conf"][tau]
            if max(p, 1.0 - p) >= pin:
                t_in = tau
                break
        if t_in is None:
            continue
        up = r["conf"][t_in] >= 0.5
        won = (r["settle"] >= r["strike"]) if up else (r["settle"] < r["strike"])
        # confidence in the side WE BOUGHT, at every second, including before
        # entry; it is allowed to go all the way to zero.
        held = dict((t, (p if up else 1.0 - p))
                    for t, p in r["conf"].items())
        out.append({"t_in": t_in, "up": up, "won": won, "conf": held,
                    "close": r["close"]})
    return out


def summarise(rows, pin=PIN, taus=TAUS, say=print):
    """Answer the operator's question: after we buy, does confidence FALL
    before a flip, in time to block a second buy?"""
    ent = entries(rows, pin=pin, taus=taus)
    lost = [e for e in ent if not e["won"]]
    won = [e for e in ent if e["won"]]
    lines = []
    w = lines.append
    w("  complete closes on the index          : %d" % len(rows))
    w("  closes the %.3f gate would have BOUGHT : %d" % (pin, len(ent)))
    w("  of those, the bought side LOST         : %d (%.2f%%)"
      % (len(lost), 100.0 * len(lost) / max(1, len(ent))))
    w("")
    w("  AFTER THE FIRST BUY, DID CONFIDENCE DROP BACK UNDER THE GATE?")
    w("  (a second buy is only blocked if it did, at that later second)")
    w("")
    w("  tau | on closes that LOST   | on closes that WON")
    w("  ----|-----------------------|----------------------")
    for tau in taus:
        lh = [e for e in lost if tau in e["conf"] and tau < e["t_in"]]
        wh = [e for e in won if tau in e["conf"] and tau < e["t_in"]]
        ld = sum(1 for e in lh if e["conf"][tau] < pin)
        wd = sum(1 for e in wh if e["conf"][tau] < pin)
        w("  %3ds | %5d of %-5d %6.1f%% | %5d of %-6d %6.2f%%"
          % (tau, ld, len(lh), 100.0 * ld / max(1, len(lh)),
             wd, len(wh), 100.0 * wd / max(1, len(wh))))
    w("")
    # EVER dropping, at any second after entry -- the most generous reading
    def ever(sel):
        n = 0
        for e in sel:
            if any(e["conf"][t] < pin for t in e["conf"] if t < e["t_in"]):
                n += 1
        return n
    le, we = ever(lost), ever(won)
    w("  EVER drops below the gate at any point after entry:")
    w("    losing closes : %5d of %-5d  %6.1f%%   <- the protection"
      % (le, len(lost), 100.0 * le / max(1, len(lost))))
    w("    winning closes: %5d of %-5d  %6.1f%%   <- the cost (blocks a good "
      "second buy)" % (we, len(won), 100.0 * we / max(1, len(won))))
    w("")
    blind = len(lost) - le
    w("  SO: %d of %d losing closes (%.1f%%) NEVER warned -- a second buy "
      "there is unprotected." % (blind, len(lost),
                                 100.0 * blind / max(1, len(lost))))
    w("")
    w("  THE NUMBER THAT DECIDES IT -- RISK OF A *SECOND* BUY, GIVEN THE GATE")
    w("  STILL PASSES AT THAT SECOND. Compare the two loss rates on each row:")
    w("  the left is every close still live at that tau, the right is only")
    w("  those whose confidence is STILL above the gate right then.")
    w("")
    w("  tau | all still-live closes | gate STILL passing    | loss odds")
    w("  ----|-----------------------|-----------------------|----------")
    for tau in taus:
        live_ = [e for e in ent if tau in e["conf"] and tau < e["t_in"]]
        if not live_:
            continue
        still = [e for e in live_ if e["conf"][tau] >= pin]
        lb = sum(1 for e in live_ if not e["won"])
        ls = sum(1 for e in still if not e["won"])
        rb = lb / float(len(live_))
        rs = (ls / float(len(still))) if still else float("nan")
        rat = (rs / rb) if rb > 0 else float("nan")
        w("  %3ds | %5d lose of %-6d %6.3f%% | %5d lose of %-6d %6.3f%% | %6.2fx"
          % (tau, lb, len(live_), 100.0 * rb, ls, len(still), 100.0 * rs, rat))
    w("")
    w("  A ratio under 1.00 means a second buy that still clears the gate is")
    w("  SAFER per contract than the first buy was. Above 1.00 means the gate")
    w("  has stopped protecting and a second buy is loading the bad closes.")
    txt = chr(10).join(lines)
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

    def world(n_closes, seed, flip_at=None, shock=0.0, sd=0.5):
        """A pure random walk -- which is exactly what the settlement model
        assumes, so the model's own sd is honest here and any warning it
        produces is earned rather than a modelling artefact.

        A consequence worth stating plainly: over the 900s between closes the
        index travels ~30 sigma, so nearly every close is already decided by
        tau=30 and the walk alone produces almost no losses. That is the real
        shape of this market, and it is why losses are PLANTED as jumps.

        The jump is TRANSIENT -- applied to the last `flip_at` seconds of each
        window and removed afterwards. A permanent jump would ride into the
        next window's strike and decide that close too, which quietly destroys
        the thing being tested.
        """
        import random
        r2 = random.Random(seed)
        ser = {}
        v = 1000.0
        t0 = 1788700000 - (1788700000 % 900)
        lo, hi = t0 - 3700, t0 + 900 * n_closes + 900
        for s2 in range(lo, hi):
            v += r2.gauss(0.0, sd)
            ser[s2] = v
        if flip_at:
            c = lo - (lo % 900) + 900
            while c <= hi:
                g = shock * (1 if r2.random() < 0.5 else -1)
                for s2 in range(c - flip_at, c):
                    if s2 in ser:
                        ser[s2] += g
                c += 900
        return ser

    rows = walk(world(600, 11))
    ck(len(rows) > 300, "the walk produces %d complete closes" % len(rows))
    ck(all(0.0 <= p <= 1.0 for r in rows for p in r["conf"].values()),
       "every stored value is a probability that settle lands at or above "
       "the strike")

    # THE POINT OF THIS FILE: unlike pinlevels_rows.jsonl, whose 16,683 rows
    # bottom out at 0.995002 because a row is only written once the model is
    # already certain, this must produce readings under the gate.
    below = sum(1 for r in rows for p in r["conf"].values()
                if max(p, 1.0 - p) < PIN)
    ck(below > 0,
       "%d readings fall BELOW the 0.995 gate -- UNCENSORED, which the "
       "candidate file provably is not" % below)

    # entries() drives every number below, so it is tested on handcrafted
    # records rather than inferred from a simulation.
    hand = [
        # never certain -> never bought
        {"close": 900, "settle": 1.0, "strike": 0.0,
         "conf": {30: 0.90, 15: 0.99, 5: 0.994}},
        # certain from tau=30 -> entry at 30, called UP, settle above -> won
        {"close": 1800, "settle": 1.0, "strike": 0.0,
         "conf": {30: 0.999, 15: 0.60, 5: 0.9999}},
        # only certain late -> entry at 5, called DOWN, settle above -> LOST
        {"close": 2700, "settle": 1.0, "strike": 0.0,
         "conf": {30: 0.20, 15: 0.10, 5: 0.0001}},
    ]
    he = entries(hand)
    ck(len(he) == 2, "the gate refuses the never-certain close and buys 2 of 3")
    ck(he[0]["t_in"] == 30 and he[0]["won"],
       "entry is taken at the EARLIEST certain second (30s), and an UP call "
       "that settles above is scored a win")
    ck(he[1]["t_in"] == 5 and not he[1]["won"],
       "a DOWN call that settles above is scored a LOSS -- if this reads "
       "backwards every rate in the report inverts")

    def warned(ent_rows, lo=0):
        """entries whose confidence fell under the gate after entry, counting
        only readings strictly later than `lo` seconds to close."""
        out = 0
        for e in ent_rows:
            if any(e["conf"][t] < PIN
                   for t in e["conf"] if lo < t < e["t_in"]):
                out += 1
        return out

    # PLANT 1 -- A WARNING THE MODEL CAN SEE. The jump lands 20s before the
    # close: AFTER entry, but inside the settlement window, so by tau=15 five
    # of its prints are locked and spot has moved with it. Confidence in the
    # side already bought must fall.
    p1 = entries(walk(world(600, 13, flip_at=20, shock=150.0)))
    l1 = [e for e in p1 if not e["won"] and e["t_in"] > 15]
    ck(len(l1) >= 10, "plant 1 produced %d losing closes to test" % len(l1))
    ck(warned(l1) >= 0.85 * len(l1),
       "a jump the model CAN see warns on %d of %d losing closes -- the "
       "detector fires when it should" % (warned(l1), len(l1)))

    # PLANT 2 -- THE NULL, and the one that matters most. The jump lands in
    # the FINAL SECOND, touching one print of sixty and appearing in no
    # `spot` the model ever reads. The outcome flips and the model cannot
    # possibly know. An estimator that reports warnings here is reading the
    # future, which is the single failure mode that would make this entire
    # answer wrong.
    p2 = entries(walk(world(600, 17, flip_at=1, shock=1500.0)))
    l2 = [e for e in p2 if not e["won"] and e["t_in"] > 3]
    ck(len(l2) >= 10, "plant 2 produced %d losing closes to test" % len(l2))
    ck(warned(l2, lo=2) <= 0.20 * len(l2),
       "an invisible jump warns on only %d of %d losing closes -- the "
       "estimator is NOT peeking at the outcome" % (warned(l2, lo=2), len(l2)))

    txt = summarise(rows, say=None)
    ck("NEVER warned" in txt, "the summary reports the unwarned share")
    print("pinwarn selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "RESULTS_warn.md"))
    ap.add_argument("--cache", default=os.path.join(REPO, "results",
                                                    "pinwarn_rows.json"),
                    help="walk() output, so re-analysis costs seconds rather "
                         "than another full pass over the index")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the cache and re-read the index")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    allrows = None
    if a.cache and not a.refresh and os.path.exists(a.cache):
        with open(a.cache, encoding="utf-8") as fh:
            allrows = [{"close": r[0], "settle": r[1], "strike": r[2],
                        "conf": dict((int(k), v) for k, v in r[3].items())}
                       for r in json.load(fh)]
        print("  %d closes from cache %s" % (len(allrows), a.cache))
    if allrows is None:
        allrows = _read_index(a.data)
        if a.cache:
            with open(a.cache, "w", encoding="utf-8") as fh:
                json.dump([[r["close"], r["settle"], r["strike"], r["conf"]]
                           for r in allrows], fh)
            print("  cached %d closes to %s" % (len(allrows), a.cache))
    if not allrows:
        print("pinwarn: no complete close on the index -- nothing to analyse")
        return 0
    txt = summarise(allrows)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_warn -- does confidence warn before a "
                 "flip?" + nl + nl)
        fh.write("```" + nl + txt + nl + "```" + nl)
    print("  wrote %s" % a.out)
    return 0


def _read_index(data_dir):
    """Every complete close on the tape, one index at a time.

    ONE COIN AT A TIME AND THEN DROPPED, deliberately: loading all twelve
    index series at once is ~2.5 GB and got an earlier job OOM-killed while
    the collector was writing. The collector outranks this.
    """
    import replay                                              # noqa: E402
    ids = sorted(set(replay.SERIES_TO_INDEX.values()))
    allrows = []
    for iid in ids:
        ser = load_one_index(data_dir, iid)
        if not ser:
            continue
        rs = walk(ser)
        print("  %-14s %d closes" % (iid, len(rs)))
        allrows += rs
        ser.clear()
        del ser
    return allrows


if __name__ == "__main__":
    raise SystemExit(main())
