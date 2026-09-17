#!/usr/bin/env python3
r"""pinpickoff.py -- the offers we would buy, and who gets them.

THE OPERATOR, 2026-09-17: "Track the things we'd buy and when they're getting
picked off. Hopefully we can track how that changes and other things for
insight and possibly act on it with strategy."

WHAT THIS MEASURES, AND WHY IT IS A LEGAL USE OF THE TAPE

`results/RESULTS_decay.md` showed the cheap offers vanishing: the best offer on
a quarter-hour drifted 95.7c -> 97.0c in nine days and the share sitting above
our 98c ceiling went 44% -> 52%. That told us the bargains are going. It did
NOT tell us WHO takes them or WHEN.

This file answers both from the trade tape. Every trade Kalshi prints carries
the taker's side, the price, the size and the millisecond. So for any market we
would have wanted, we can ask: did somebody buy the winning side cheap, how
many seconds before the close, and was it us?

RULE 5 (CLAUDE.md): the tape may NEVER be used for OUR loss rate. It IS valid
for "what the market did", and that is all this file claims. Nothing here is a
loss rate, a P&L, or a projection of either. It counts trades other people
made, and it separates ours from theirs so the two can be compared.

THE FOUR NUMBERS, per Eastern day

  bargains per close   how many times anyone bought the winning side inside
                       our own price band in the last 60 seconds. This is the
                       size of the pool we compete for.
  our share            how many of those were ours. Falling share against a
                       flat pool means we are being out-raced; a falling POOL
                       means the offers themselves are drying up. Those are
                       different problems with different answers, and until
                       now nothing separated them.
  median tau           how many seconds before the close the pool is taken. If
                       this creeps EARLIER, competitors are moving earlier and
                       the case for our own 31-45s window (AMENDMENT 46) gets
                       stronger. This is the number most likely to change
                       strategy.
  mean price           what the pool costs. Rising means the same thing
                       RESULTS_decay measured, seen per trade instead of per
                       quarter-hour.

WHAT "OURS" MEANS. A tape trade is ours when one of our own `order` records
names the same ticker within OWN_WINDOW_S seconds and the executed price is
within OWN_PRICE_C cents. The tape carries no account id, so this is a JOIN
and not a certainty; `--audit` prints the matched and unmatched counts so the
join can be checked rather than trusted. Our fills that find no tape trade are
reported too -- that gap is the join's error bar.

    python research/pinpickoff.py --selftest
    python research/pinpickoff.py                 # uses the cache, adds new hours
    python research/pinpickoff.py --rebuild       # re-walk every tape hour
    python research/pinpickoff.py --audit         # show the ours/theirs join
"""
import argparse
import calendar
import collections
import glob
import gzip
import json
import os
import statistics as st
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinflat                                                   # noqa: E402
from downtime import et_offset                                   # noqa: E402

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
TAPE = r"C:\kals\kalshi_data\trade"
SETTLE = r"C:\kals\fulltape\markets.json"
CACHE = os.path.join(RESULTS, "pinpickoff_cache.json")

# The band we would actually buy in: at or under the live ceiling, and not so
# cheap that it is a different animal (a 60c print is not our trade).
BAND_LO = 0.90
BAND_HI = 0.98
TAU_MAX = 60             # look back this far from the close
OWN_WINDOW_S = 6         # a tape trade this close in time to one of our fills
OWN_PRICE_C = 1.0        # ...and this close in price, is ours


def et_day(epoch):
    return time.strftime("%Y-%m-%d", time.gmtime(epoch + et_offset(epoch)))


def outcome_of(m):
    """1.0 if the market settled YES. Handles both spellings kalshi_fulltape
    has written: a float `result`, and the string 'yes'/'no'."""
    r = m.get("result")
    if isinstance(r, str):
        return 1.0 if r.strip().lower() in ("yes", "y", "1", "true") else 0.0
    try:
        return float(r)
    except (TypeError, ValueError):
        return None


def load_settlements(path=SETTLE):
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    for lst in data.values():
        for m in lst:
            o = outcome_of(m)
            if o is not None and m.get("ticker"):
                out[m["ticker"]] = o
    return out


def load_our_fills(results=RESULTS):
    """[(ticker, epoch, price)] for every live fill we made.

    THE TIME CONVERSION IS calendar.timegm AND NOTHING ELSE. The first version
    used `time.mktime(strptime(...)) - time.timezone`, which reads a UTC string
    as LOCAL time: mktime applies the DST offset in force (EDT, -4) while
    time.timezone is the STANDARD offset (EST, -5), so every fill came out
    exactly one hour early. The join window is six seconds, so not one of our
    463 fills could ever match a tape trade and the report read "our share 0%"
    -- a number that looked like a finding and was a bug.
    """
    out = []
    for f in sorted(glob.glob(os.path.join(results, "pinrun-live-*.jsonl"))):
        for line in open(f, encoding="utf-8", errors="replace"):
            if '"kind": "order"' not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            try:
                filled = float(r.get("filled") or 0)
            except (TypeError, ValueError):
                continue
            if filled <= 0:
                continue
            try:
                ep = calendar.timegm(time.strptime(str(r.get("t"))[:19], "%Y-%m-%dT%H:%M:%S"))
            except (TypeError, ValueError):
                continue
            px = r.get("exec_price")
            out.append((r.get("ticker"), ep, float(px) if px is not None else None))
    return out


def is_ours(tk, ts, paid, ours_index):
    """Does one of our fills match this tape trade?"""
    for ep, px in ours_index.get(tk, ()):
        if abs(ep - ts) <= OWN_WINDOW_S and (
                px is None or paid is None or abs(px - paid) <= OWN_PRICE_C / 100.0):
            return True
    return False


def scan_trade(msg, settled, ours_index, band=(BAND_LO, BAND_HI), tau_max=TAU_MAX):
    """One tape trade -> a bargain row, or None.

    A BARGAIN is a taker BUYING the side that went on to win, inside our price
    band, within tau_max seconds of the close. That is the trade we compete
    for, whoever made it.
    """
    tk = msg.get("market_ticker")
    if not tk or "15M-" not in tk:
        return None
    won_yes = settled.get(tk)
    if won_yes is None:
        return None
    close = pinflat.close_epoch(tk)
    if close is None:
        return None
    try:
        ts = int(msg["ts"])
        yes_px = float(msg["yes_price_dollars"])
        n = float(msg.get("count_fp") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    tau = close - ts
    if not (0 <= tau <= tau_max):
        return None
    side = msg.get("taker_side")
    if side not in ("yes", "no"):
        return None
    paid = yes_px if side == "yes" else 1.0 - yes_px
    if not (band[0] <= paid <= band[1]):
        return None
    took_winner = (side == "yes" and won_yes >= 0.5) or (side == "no" and won_yes < 0.5)
    if not took_winner:
        return None
    return {"ticker": tk, "close": close, "tau": tau, "paid": paid, "n": n,
            "ours": is_ours(tk, ts, paid, ours_index)}


def walk(files, settled, ours_index, verbose=False, on_progress=None, every=40):
    """Walk tape hours into bargain rows.

    `on_progress(done_files, rows, bad)` is called every `every` files so the
    caller can checkpoint. THIS EXISTS BECAUSE THE FIRST BACKFILL WAS KILLED:
    531 tape hours is ~25 minutes, the machine is shared, and a run that only
    saves at the end throws away everything it has done. A long job that cannot
    survive being interrupted is a job that will have to be run twice.
    """
    rows = []
    bad = 0
    done = []
    for f in files:
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "15M-" not in line:
                        continue
                    try:
                        msg = json.loads(line)["msg"]
                    except (ValueError, KeyError):
                        continue
                    r = scan_trade(msg, settled, ours_index)
                    if r:
                        rows.append(r)
        except (EOFError, zlib.error, OSError):
            bad += 1          # the hour still being written, or a torn file
        done.append(f)
        if verbose:
            print("  %s -> %d rows" % (os.path.basename(f), len(rows)), flush=True)
        if on_progress and len(done) % every == 0:
            on_progress(done, rows, bad)
    if on_progress and done:
        on_progress(done, rows, bad)
    return rows, bad


def mark_ours(rows, ours_index):
    """Re-decide 'ours' at REPORT time rather than at walk time.

    The walk over 531 tape hours takes ~25 minutes; our own fills change every
    day and the join logic had a bug in it. Deciding this here means a fix, or
    a new day of fills, costs a second instead of a re-walk. `ts` is recovered
    as close - tau, exactly the value the walk saw.
    """
    for r in rows:
        r["ours"] = is_ours(r["ticker"], r["close"] - r["tau"], r.get("paid"), ours_index)
    return rows


def summarise(rows):
    """Per ET day, and per close, the four numbers."""
    by = collections.defaultdict(lambda: {"n": 0, "ours": 0, "tau": [], "paid": [],
                                          "contracts": 0.0, "ours_contracts": 0.0,
                                          "closes": set(), "ours_closes": set()})
    for r in rows:
        d = by[et_day(r["close"])]
        d["n"] += 1
        d["ours"] += bool(r["ours"])
        d["tau"].append(r["tau"])
        d["paid"].append(100 * r["paid"])
        d["contracts"] += r["n"]
        d["closes"].add(r["close"])
        if r["ours"]:
            d["ours_contracts"] += r["n"]
            d["ours_closes"].add(r["close"])
    return by


def report(by, out=sys.stdout):
    p = lambda s: print(s, file=out)                              # noqa: E731
    p("THE OFFERS WE WOULD BUY, AND WHO GOT THEM")
    p("  A 'bargain' = any taker buying the WINNING side at %.0f-%.0fc within %ds of the close."
      % (100 * BAND_LO, 100 * BAND_HI, TAU_MAX))
    p("  TAPE POPULATION -- what the market did. Not our loss rate (rule 5).")
    p("")
    p("  day         closes  bargains  per close   ours   theirs  our share | median tau  mean price | contracts theirs")
    days = sorted(by)
    for d in days:
        v = by[d]
        if not v["n"]:
            continue
        p("  %s %7d %9d %10.1f %6d %8d %9.0f%% | %9.0fs %10.1fc | %13.0f"
          % (d, len(v["closes"]), v["n"], v["n"] / max(1, len(v["closes"])),
             v["ours"], v["n"] - v["ours"], 100 * v["ours"] / v["n"],
             st.median(v["tau"]), st.mean(v["paid"]), v["contracts"] - v["ours_contracts"]))
    if len(days) >= 6:
        f, l = days[:3], days[-3:]

        def pool(grp, k):
            return [x for d in grp for x in by[d][k]]

        def tot(grp, k):
            return sum(by[d][k] for d in grp)
        p("")
        p("  first 3 days vs last 3 days:")
        p("    bargains per close   %6.1f  ->  %6.1f" % (
            tot(f, "n") / max(1, sum(len(by[d]["closes"]) for d in f)),
            tot(l, "n") / max(1, sum(len(by[d]["closes"]) for d in l))))
        p("    our share            %5.0f%%  ->  %5.0f%%" % (
            100 * tot(f, "ours") / max(1, tot(f, "n")), 100 * tot(l, "ours") / max(1, tot(l, "n"))))
        p("    median tau taken     %5.0fs  ->  %5.0fs   (EARLIER means they are moving earlier)" % (
            st.median(pool(f, "tau")), st.median(pool(l, "tau"))))
        p("    mean price           %5.1fc  ->  %5.1fc" % (
            st.mean(pool(f, "paid")), st.mean(pool(l, "paid"))))
    p("")
    p("  HOW TO READ 'our share': one of our orders prints as MANY tape trades")
    p("  (it sweeps several resting orders), and the join accepts any print")
    p("  within 6 s and 1c of one of our fills. The share is an UPPER bound on")
    p("  the slice we take. Use the TREND and the pool size, not the level.")
    p("")
    p("  REVISIT THIS ONCE IT HAS TWO MORE WEEKS IN IT. Three things to act on:")
    p("    1. median tau falling  -> competitors are moving earlier; widen our own early")
    p("       window (AMENDMENT 46 is at 45s) or accept a thinner edge sooner.")
    p("    2. our share falling while bargains per close holds -> we are losing RACES,")
    p("       not opportunities; the answer is latency and the sweep, not the gates.")
    p("    3. bargains per close falling -> the pool itself is drying up; that is the")
    p("       one that argues for a second product rather than a better bot.")


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinpickoff selftest: FAILED -- " + msg)

    import calendar
    tk = "KXBTC15M-26SEP161000-00"          # closes 10:00 AM ET = 14:00Z
    close = calendar.timegm((2026, 9, 16, 14, 0, 0))
    ck(pinflat.close_epoch(tk) == close, "the close comes from the ticker, in ET")
    settled = {tk: 1.0, "KXETH15M-26SEP161000-00": 0.0}

    def trade(side, yes_px, tau, n=10.0, ticker=tk):
        return {"market_ticker": ticker, "ts": close - tau, "taker_side": side,
                "yes_price_dollars": yes_px, "count_fp": n}

    # the market settled YES, so buying YES at 95c is a bargain
    r = scan_trade(trade("yes", 0.95, 20), settled, {})
    ck(r and r["tau"] == 20 and abs(r["paid"] - 0.95) < 1e-9 and not r["ours"],
       "a taker buying the winning side at 95c, 20s out, is a bargain")
    ck(scan_trade(trade("no", 0.05, 20), settled, {}) is None,
       "NULL: the taker who bought the LOSING side at 95c is not our trade")
    # a NO taker on a market that settled NO, priced from the yes side
    r = scan_trade(trade("no", 0.04, 20, ticker="KXETH15M-26SEP161000-00"), settled, {})
    ck(r and abs(r["paid"] - 0.96) < 1e-9,
       "a NO taker pays 1 - yes_price; 0.04 yes = 96c for the NO that won")
    ck(scan_trade(trade("yes", 0.995, 20), settled, {}) is None,
       "NULL: 99.5c is above our band -- we would never buy it")
    ck(scan_trade(trade("yes", 0.50, 20), settled, {}) is None,
       "NULL: 50c is below our band -- a different animal")
    ck(scan_trade(trade("yes", 0.95, 90), settled, {}) is None,
       "NULL: 90 seconds out is outside the window")
    ck(scan_trade(trade("yes", 0.95, -5), settled, {}) is None,
       "NULL: a print after the close is not a bargain")
    ck(scan_trade(trade("yes", 0.95, 20, ticker="KXDOGE15M-26SEP161000-00"), settled, {}) is None,
       "NULL: a market with no settlement on file is skipped, not guessed")

    # ours vs theirs
    ours_index = {tk: [(close - 21, 0.95)]}
    ck(scan_trade(trade("yes", 0.95, 20), settled, ours_index)["ours"],
       "a tape trade 1s from our own fill at the same price is OURS")
    ck(not scan_trade(trade("yes", 0.95, 20), settled, {tk: [(close - 40, 0.95)]})["ours"],
       "...but 20s away is not")
    ck(not scan_trade(trade("yes", 0.95, 20), settled, {tk: [(close - 21, 0.90)]})["ours"],
       "...and 5c away is not")

    # the summary arithmetic, on planted rows
    rows = [{"ticker": tk, "close": close, "tau": 10, "paid": 0.95, "n": 5.0, "ours": True},
            {"ticker": tk, "close": close, "tau": 30, "paid": 0.97, "n": 7.0, "ours": False},
            {"ticker": tk, "close": close + 900, "tau": 20, "paid": 0.93, "n": 9.0, "ours": False}]
    by = summarise(rows)
    d = by[et_day(close)]
    ck(d["n"] == 3 and d["ours"] == 1 and len(d["closes"]) == 2,
       "three bargains over two closes, one of them ours")
    ck(abs(st.median(d["tau"]) - 20) < 1e-9 and abs(d["contracts"] - 21.0) < 1e-9,
       "median tau 20s and 21 contracts in total")
    ck(abs(d["contracts"] - d["ours_contracts"] - 16.0) < 1e-9,
       "16 of those contracts went to somebody else")
    ck(not summarise([]), "NULL: no bargains -> no rows, not a fabricated zero day")

    # THE BUG THAT READ AS A FINDING: a UTC timestamp converted with
    # mktime()-timezone lands an hour off under DST, so no fill can ever match.
    t_str = "2026-09-16T13:59:31Z"
    good = calendar.timegm(time.strptime(t_str[:19], "%Y-%m-%dT%H:%M:%S"))
    bad = time.mktime(time.strptime(t_str[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
    ck(good == calendar.timegm((2026, 9, 16, 13, 59, 31)),
       "our fill times are read as UTC with calendar.timegm")
    ck(abs(good - bad) >= 3600,
       "...and the old mktime()-timezone form is at least an hour out under "
       "DST, which is why the join found 0 of 583,424 and called it 0%% share")
    # and the report-time re-marking recovers ts from close - tau
    rr = [{"ticker": tk, "close": close, "tau": 20, "paid": 0.95, "n": 5.0, "ours": False}]
    mark_ours(rr, {tk: [(close - 20, 0.95)]})
    ck(rr[0]["ours"], "mark_ours recovers the trade time as close - tau and matches our fill")
    mark_ours(rr, {})
    ck(not rr[0]["ours"], "...and un-marks it when the fill is not ours, with no re-walk")

    # end to end over a written tape file, including a torn one
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "20260916T14.jsonl.gz")
        with gzip.open(good, "wt", encoding="utf-8") as fh:
            for t in (trade("yes", 0.95, 20), trade("yes", 0.99, 20), trade("no", 0.05, 20)):
                fh.write(json.dumps({"type": "trade", "msg": t}) + "\n")
        torn = os.path.join(td, "20260916T15.jsonl.gz")
        with open(torn, "wb") as fh:
            fh.write(gzip.compress(b'{"type":"trade"}\n')[:12])   # truncated
        seen = []
        rows, bad = walk([good, torn], settled, {},
                         on_progress=lambda d, r, b: seen.append((len(d), len(r))), every=1)
        ck(len(rows) == 1 and bad == 1,
           "end to end: one bargain found, and the torn hour is SKIPPED rather "
           "than crashing the run or silently reading as empty")
        ck(seen and seen[0] == (1, 1) and seen[-1][0] == 2,
           "and progress is reported as it goes, so a long walk can checkpoint "
           "instead of losing everything when it is killed")
    print("pinpickoff selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="re-walk every tape hour")
    ap.add_argument("--audit", action="store_true", help="show the ours/theirs join")
    ap.add_argument("--tape", default=TAPE)
    ap.add_argument("--out", default=os.path.join(RESULTS, "RESULTS_pickoff.md"))
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()

    settled = load_settlements()
    fills = load_our_fills()
    ours_index = collections.defaultdict(list)
    for tk, ep, px in fills:
        ours_index[tk].append((ep, px))
    print("settlements on file: %d markets | our live fills: %d" % (len(settled), len(fills)))

    cache = {"hours": {}, "rows": []}
    if not a.rebuild:
        try:
            with open(CACHE, encoding="utf-8") as fh:
                cache = json.load(fh)
        except (OSError, ValueError):
            pass
    files = sorted(glob.glob(os.path.join(a.tape, "*.jsonl.gz")))
    todo = [f for f in files if os.path.basename(f) not in cache["hours"]]
    print("tape hours: %d total, %d already cached, %d to walk" % (
        len(files), len(files) - len(todo), len(todo)))
    if todo:
        t0 = time.time()
        base_rows = list(cache["rows"])

        def checkpoint(done, rows, bad):
            """Save what has been walked so far. A kill then costs one chunk,
            not the whole run."""
            cache["rows"] = base_rows + rows
            for f in done:
                cache["hours"][os.path.basename(f)] = 1
            try:
                tmp = CACHE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(cache, fh)
                os.replace(tmp, CACHE)      # atomic: never a half-written cache
            except OSError:
                return
            print("  ... %d/%d hours, %d bargains, %.0f s elapsed"
                  % (len(done), len(todo), len(cache["rows"]), time.time() - t0), flush=True)

        rows, bad = walk(todo, settled, ours_index, on_progress=checkpoint)
        print("  walked %d hours in %.0f s (%d unreadable, skipped), %d bargains found"
              % (len(todo), time.time() - t0, bad, len(rows)))

    rows = cache["rows"]
    if not rows:
        print("loaded nothing -- no bargains on file yet")
        return 0
    mark_ours(rows, ours_index)          # decided here, so a fix needs no re-walk
    by = summarise(rows)
    report(by)
    if a.audit:
        n_ours = sum(1 for r in rows if r["ours"])
        tks = {r["ticker"] for r in rows if r["ours"]}
        print("\n  JOIN AUDIT: %d of %d tape bargains matched one of our %d fills, over %d markets."
              % (n_ours, len(rows), len(fills), len(tks)))
        print("  Our fills with no matching tape bargain: %d. That gap is this join's error bar."
              % max(0, len(fills) - n_ours))
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS -- the offers we would buy, and who gets them\n\n")
        fh.write("Rebuilt %s from `research/pinpickoff.py`. TAPE population (rule 5):\n"
                 "what the market did, never our loss rate.\n\n```\n" % time.strftime("%Y-%m-%d %H:%MZ", time.gmtime()))
        report(by, out=fh)
        fh.write("```\n")
    print("\nwrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
