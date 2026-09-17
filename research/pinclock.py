"""pinclock.py -- is this machine's clock still telling the truth?

WHY THIS EXISTS. The 2026-09-17 fresh-eyes review found that nothing in the
stack watches the local clock, and rated it high: **every trading decision is
keyed on `tau`, and `tau` is `close_epoch - time.time()`.** The close time comes
from the exchange; `time.time()` comes from this PC. If the two drift apart,
every gate silently moves with it and nothing anywhere logs a complaint.

The damage is asymmetric, which is why a small drift matters:

- **Clock RUNS FAST** (local ahead of the exchange): tau reads SMALLER than it
  is. The bot thinks it is later than it is, so it stops trading early, misses
  the last seconds -- which the live record says are the most profitable
  (5.35c a contract inside 5 s against 1.90c at 16-30 s) -- and at the extreme
  refuses everything because tau drops under TAU_MIN.
- **Clock RUNS SLOW** (local behind): tau reads LARGER. The bot believes it has
  time it does not have, and sends orders that can land after the close. That
  is the dangerous direction: `pintake` refuses a market that has already
  closed by ITS OWN clock, which is the same wrong clock.

At `TAU_MIN = 3` the margin is three seconds, and the model is most sensitive
exactly there: with two prints still unknown a single mis-filled second moves
the mean by about 45% of the remaining standard deviation.

There is no fix in here and deliberately so -- this file only measures and
reports. Correcting a system clock is the operating system's job.
"""
import argparse
import email.utils
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.path.dirname(HERE), "results")

# The exchange we actually trade against. Its Date header is the authority we
# care about -- not a public NTP pool -- because it is the clock our close
# times are quoted in.
URL = "https://api.elections.kalshi.com/trade-api/v2/exchange/status"
WARN_S = 1.0             # report a warning past this
BAD_S = 2.0              # past this, tau is materially wrong
STATE = os.path.join(RESULTS, "pinclock.json")


def classify(drift, warn=WARN_S, bad=BAD_S):
    """('ok'|'watch'|'bad', one-line English). `drift` is local minus server."""
    a = abs(float(drift))
    if a < warn:
        return "ok", "clock is within %.1fs of the exchange" % a
    if a < bad:
        return "watch", ("clock is %.1fs %s the exchange -- approaching the "
                         "point where tau starts lying"
                         % (a, "ahead of" if drift > 0 else "behind"))
    if drift > 0:
        return "bad", ("clock is %.1fs AHEAD: tau reads too small, the bot "
                       "stops trading early and loses the last seconds, which "
                       "are its best" % a)
    return "bad", ("clock is %.1fs BEHIND: tau reads too large, so orders can "
                   "be sent into markets that have already closed" % a)


def measure(url=URL, opener=None, now=None):
    """(drift_seconds, round_trip_seconds) or None if the exchange is unreachable.

    Drift is local minus server, measured at the MIDPOINT of the request so the
    round trip does not count as drift -- a 92 ms round trip would otherwise
    look like 92 ms of error all by itself.
    """
    clock = time.time if now is None else now
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "kals-pinclock"})
        t0 = clock()
        op = opener or (lambda r: urllib.request.urlopen(r, timeout=10))
        with op(req) as resp:
            date = resp.headers.get("Date")
        t1 = clock()
    except Exception:                                             # noqa: BLE001
        return None
    if not date:
        return None
    try:
        server = email.utils.parsedate_to_datetime(date).timestamp()
    except (TypeError, ValueError):
        return None
    return ((t0 + t1) / 2.0 - server), (t1 - t0)


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinclock selftest: FAILED -- " + msg)

    ck(classify(0.0)[0] == "ok" and classify(0.9)[0] == "ok",
       "under a second is ok")
    ck(classify(1.5)[0] == "watch" and classify(-1.5)[0] == "watch",
       "1.5s either way is a warning, not yet a failure")
    ck(classify(2.5)[0] == "bad" and classify(-2.5)[0] == "bad",
       "past two seconds is bad in BOTH directions")
    ck("AHEAD" in classify(3.0)[1] and "stops trading early" in classify(3.0)[1],
       "a FAST clock is described by what it actually does: tau too small, the "
       "bot quits early and gives up the last seconds, which earn the most")
    ck("BEHIND" in classify(-3.0)[1] and "already closed" in classify(-3.0)[1],
       "a SLOW clock is the dangerous one: orders sent into closed markets")
    ck(classify(1.0)[0] == "watch" and classify(2.0)[0] == "bad",
       "the boundaries belong to the WORSE class -- a threshold that rounds in "
       "the kind direction is not a threshold")

    # THE ROUND TRIP MUST NOT BE MISTAKEN FOR DRIFT. Note the whole-second
    # timestamps: an HTTP Date header carries ONLY whole seconds, so the
    # measurement itself quantises to +/-0.5s. That is why WARN_S is 1.0 and not
    # something tighter -- a reading of "0.8s" could be anywhere in 0.3-1.3s,
    # and a threshold finer than the instrument is theatre. This self-test used
    # to plant a fractional server time and then assert the fraction away,
    # which tested the planting rather than the code.
    class _R:
        headers = {"Date": email.utils.formatdate(1000.0, usegmt=True)}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    clicks = iter([999.8, 1000.2])
    d, rt = measure(opener=lambda r: _R(), now=lambda: next(clicks))
    ck(abs(d) < 0.01 and abs(rt - 0.4) < 1e-9,
       "a 400ms round trip around a PERFECT clock reports ~0 drift, not 400ms "
       "-- drift is read at the MIDPOINT of the request")
    clicks2 = iter([1004.8, 1005.2])
    d2, _ = measure(opener=lambda r: _R(), now=lambda: next(clicks2))
    ck(abs(d2 - 5.0) < 0.01, "and a genuinely 5s-fast clock reports +5.0s")
    ck(WARN_S >= 1.0,
       "the warning threshold is not finer than the instrument: an HTTP Date "
       "header is whole seconds, so any reading carries +/-0.5s of quantisation")

    class _Bad:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    ck(measure(opener=lambda r: _Bad(), now=lambda: 0.0) is None,
       "NULL: a response with no Date header measures nothing rather than guessing")
    def _boom(r): raise OSError("down")
    ck(measure(opener=_boom) is None,
       "NULL: an unreachable exchange is not a clock problem and must not be "
       "reported as one")
    print("pinclock selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="print only when something is wrong (for a watchdog)")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    got = measure()
    if got is None:
        print("pinclock: could not reach the exchange -- NOT a clock verdict")
        return 3
    drift, rt = got
    state, msg = classify(drift)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "drift_s": round(drift, 3), "round_trip_ms": round(1000 * rt, 1),
           "state": state}
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
    except OSError:
        pass
    if state == "ok" and a.quiet:
        return 0
    print("pinclock: %s  (%+.2fs, round trip %.0f ms)" % (msg, drift, 1000 * rt))
    return 0 if state == "ok" else (1 if state == "watch" else 2)


if __name__ == "__main__":
    sys.exit(main())
