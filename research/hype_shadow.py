#!/usr/bin/env python3
"""hype_shadow.py -- what the live bot WOULD have made on HYPE since it stopped trading it.

v-skiphype went live 2026-10-05T14:24:02Z: the live main bot no longer buys KXHYPE15M.
The operator, 2026-10-06: "Track what we'd have if we still traded hype wins and losses."

THERE IS NO LIVE HYPE DATA ANY MORE, so this reads the PAPER copies that still trade it:
  - arm-0925b (main view): the SAME 09-25 code live runs (results/arms_1003_manifest.json;
    code_sha f9548c5571ff; live is that build + v-fullcap + v-skiphype). Its flags differ
    from live in two ways: --early-min-price 0.95 (live 0.90) and no --max-full-bets 1.0.
  - arm-live-twin (second view): live's code and argv as of 2026-09-29 (pid 4228512,
    results/pinrun-paper-20260929T185918Z.jsonl), also still trading HYPE. Its 7-day run
    ended 2026-10-06 18:59Z; the identical relaunch (pid 1675248, on that day's repo pinrun,
    results/pinrun-paper-20261006T185948Z.jsonl) is reported as its own section.

For every KXHYPE15M market an arm SETTLED since the window start, per-market money is the
sum of its settled records' pnl_c / 100 (an entry leg and a hedge leg are separate records;
memory paper-log-money-fields: `settled.realised` is a running total, never per market).
That is SCALED to live's bet size at the time: x (live size / arm size), both read from
their own `autosize` records (an arm mirrors live's size, so the factor is ~1 except while
a mirror read lags). Money bet = signal take_n x price + hedge n x price, scaled the same.

THIS IS PAPER AND THE LOSS SIDE IS OPTIMISTIC. A paper arm books what the book showed; live
is sold to by people who know more. NEAR on 10-03: live filled 94 contracts on a loser where
paper booked 4. Paper also cannot see live's fills at all on a fast collapse. So a paper
"HYPE would have made +$X" is an upper bound on what live would have made, not an estimate.

    python research/hype_shadow.py                 # per ET day + cumulative, both arms
    python research/hype_shadow.py --since 2026-10-05T14:24:02Z
    python research/hype_shadow.py --selftest

Read-only: reads results/*.jsonl and the arm manifests; writes nothing.
"""
import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")
SERIES = "KXHYPE15M-"
SINCE = "2026-10-05T14:24:02Z"          # v-skiphype live start record
TWIN_START = "2026-09-29T18:59:18Z"     # arm-live-twin (results/arms_0928_manifest.json)
TWIN2_START = "2026-10-06T18:59:48Z"    # its identical relaunch (results/relaunch_twin_1006.ps1, pid 1675248)


def ts(s):
    """'2026-10-05T14:24:02Z' -> aware UTC datetime, or None."""
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def et_offset(dt):
    """EDT (UTC-4) from the 2nd Sunday of March 07:00Z to the 1st Sunday of November
    06:00Z, EST (UTC-5) otherwise -- the readsdue.py rule."""
    y = dt.year
    mar = datetime(y, 3, 8, 7, tzinfo=timezone.utc)
    mar += timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, 6, tzinfo=timezone.utc)
    nov += timedelta(days=(6 - nov.weekday()) % 7)
    return -4 if mar <= dt < nov else -5


def et_day(dt):
    return (dt + timedelta(hours=et_offset(dt))).strftime("%Y-%m-%d")


def et_str(dt):
    return (dt + timedelta(hours=et_offset(dt))).strftime("%m-%d %I:%M %p ET")


def size_at(timeline, t, default):
    """The size in force at `t`: the newest (t, size) at or before it, else `default`."""
    best = None
    for tt, s in timeline:
        if tt <= t and (best is None or tt >= best[0]):
            best = (tt, s)
    return best[1] if best else default


def live_sizes(results=None):
    """[(t, size)] from every live log: each run's start (its --size, until the first
    autosize) and every autosize `new`. Only lines naming those kinds are parsed."""
    out = []
    for f in sorted(glob.glob(os.path.join(results or RESULTS, "pinrun-live-*.jsonl"))):
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"kind": "autosize"' not in line and '"kind": "start"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = ts(r.get("t"))
                if t is None:
                    continue
                if r.get("kind") == "autosize" and r.get("new") is not None:
                    out.append((t, float(r["new"])))
                elif r.get("kind") == "start" and r.get("size") is not None:
                    out.append((t, float(r["size"])))
    return sorted(out)


def read_arm(path, since, until=None):
    """One arm log -> (meta, sizes, markets). markets: {ticker: {pnl_c, spent, t_settle,
    t_first, legs, lost}} for HYPE tickers with a settled record in [since, until)."""
    meta = {"start": None, "code_sha": None, "last_t": None, "bad_lines": 0}
    sizes, mk, spent, first = [], {}, {}, {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            hyp = SERIES in line
            if not hyp and '"kind": "autosize"' not in line and '"kind": "start"' not in line:
                if '"kind": "loop"' in line and line.rstrip().endswith("}"):
                    k = line.rfind('"t": "')
                    if k >= 0:
                        meta["last_t"] = line[k + 6:k + 26]
                continue
            try:
                r = json.loads(line)
            except ValueError:
                meta["bad_lines"] += 1
                continue
            kind, t = r.get("kind"), ts(r.get("t"))
            if t is None:
                continue
            meta["last_t"] = r.get("t")
            if kind == "start":
                meta["start"], meta["code_sha"] = r.get("t"), r.get("code_sha")
                if r.get("size") is not None:
                    sizes.append((t, float(r["size"])))
                continue
            if kind == "autosize":
                if r.get("new") is not None:
                    sizes.append((t, float(r["new"])))
                continue
            tk = str(r.get("ticker") or "")
            if not tk.startswith(SERIES):
                continue
            if kind == "signal" and not r.get("live"):
                try:
                    spent[tk] = spent.get(tk, 0.0) + float(r.get("take_n") or 0) * float(r.get("price") or 0)
                except (TypeError, ValueError):
                    pass
                first.setdefault(tk, t)
            elif kind == "hedge" and not r.get("live"):
                try:
                    spent[tk] = spent.get(tk, 0.0) + float(r.get("n") or 0) * float(r.get("price") or 0)
                except (TypeError, ValueError):
                    pass
            elif kind == "settled":
                if t < since or (until is not None and t >= until):
                    continue
                m = mk.setdefault(tk, {"pnl_c": 0.0, "legs": 0, "t_settle": t})
                m["pnl_c"] += float(r.get("pnl_c") or 0.0)
                m["legs"] += 1
                m["t_settle"] = max(m["t_settle"], t)
    for tk, m in mk.items():
        m["spent"] = spent.get(tk, 0.0)
        m["t_first"] = first.get(tk, m["t_settle"] - timedelta(seconds=60))
    return meta, sorted(sizes), mk


def shadow(markets, arm_sizes, live_tl, arm_default=20.0):
    """Scale each market to live's size at its entry; returns rows sorted by settle time."""
    rows = []
    for tk, m in markets.items():
        a = size_at(arm_sizes, m["t_first"], arm_default)
        lv = size_at(live_tl, m["t_first"], None)
        f = (lv / a) if (lv and a) else 1.0
        rows.append({"ticker": tk, "t": m["t_settle"], "day": et_day(m["t_settle"]),
                     "arm_usd": m["pnl_c"] / 100.0, "arm_spent": m["spent"],
                     "arm_size": a, "live_size": lv, "factor": f,
                     "usd": m["pnl_c"] / 100.0 * f, "spent": m["spent"] * f,
                     "legs": m["legs"]})
    return sorted(rows, key=lambda r: r["t"])


def summarise(rows):
    """{day: agg} plus 'ALL'. agg: markets, won, lost, net, spent, arm_net, losers."""
    out = {}
    for r in rows:
        for key in (r["day"], "ALL"):
            a = out.setdefault(key, {"markets": 0, "won": 0, "lost": 0, "net": 0.0,
                                     "spent": 0.0, "arm_net": 0.0, "losers": []})
            a["markets"] += 1
            a["won"] += r["usd"] > 0
            a["lost"] += r["usd"] < 0
            a["net"] += r["usd"]
            a["spent"] += r["spent"]
            a["arm_net"] += r["arm_usd"]
            if r["usd"] < 0:
                a["losers"].append(r)
    return out


def fmt(agg):
    pct = (100.0 * agg["net"] / agg["spent"]) if agg["spent"] > 0 else 0.0
    return ("%3d markets, %3d won, %2d lost, net %+9.2f on $%9.2f bet (%+.2f%%)"
            % (agg["markets"], agg["won"], agg["lost"], agg["net"], agg["spent"], pct))


def find_twin_log(results, start=TWIN_START):
    """The paper log whose name is within 30 s of `start`, else None."""
    want = ts(start)
    best = None
    for f in glob.glob(os.path.join(results, "pinrun-paper-*.jsonl")):
        n = os.path.basename(f)[len("pinrun-paper-"):-len(".jsonl")]
        try:
            t = datetime.strptime(n, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        d = abs((t - want).total_seconds())
        if d <= 30 and (best is None or d < best[0]):
            best = (d, f)
    return best[1] if best else None


def arm_0925b_log(results):
    try:
        man = json.load(open(os.path.join(results, "arms_1003_manifest.json"), encoding="utf-8"))
        for a in man:
            if a.get("arm") == "arm-0925b":
                return os.path.join(results, "..", a["log"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def report(name, path, since, live_tl, until=None, out=print):
    if not path or not os.path.exists(path):
        out("%s: LOG NOT FOUND (%s) -- no numbers" % (name, path))
        return None
    meta, sizes, mk = read_arm(path, since, until)
    rows = shadow(mk, sizes, live_tl)
    agg = summarise(rows)
    out("%s  (%s; start %s, code_sha %s; last record %s)"
        % (name, os.path.basename(path), meta["start"], meta["code_sha"], meta["last_t"]))
    if not rows:
        out("   no HYPE market settled since %s" % et_str(since))
        return agg
    for day in sorted(k for k in agg if k != "ALL"):
        out("   ET %s  %s" % (day, fmt(agg[day])))
    out("   TOTAL       %s" % fmt(agg["ALL"]))
    fs = sorted(set(round(r["factor"], 3) for r in rows))
    out("   size factor live/arm per market: %s (arm unscaled net %+.2f)" % (fs, agg["ALL"]["arm_net"]))
    for r in agg["ALL"]["losers"]:
        out("   lost: %-28s %s  %+8.2f (paper %+.2f; arm size %g, live size %s)"
            % (r["ticker"], et_str(r["t"]), r["usd"], r["arm_usd"], r["arm_size"], r["live_size"]))
    return agg


# ---------------------------------------------------------------------------
def selftest():
    fails = []

    def ck(c, msg):
        print(("  ok   " if c else "  FAIL ") + msg)
        if not c:
            fails.append(msg)
    d = tempfile.mkdtemp(prefix="hypeshadow-")
    try:
        J = lambda **k: json.dumps(k) + "\n"
        # live: starts at size 20, sizes to 88 at 14:25, to 90 on 10-06 02:00Z
        with open(os.path.join(d, "pinrun-live-20261005T142402Z.jsonl"), "w") as fh:
            fh.write(J(kind="start", size=20.0, t="2026-10-05T14:24:02Z", code_sha="x"))
            fh.write(J(kind="autosize", old=20.0, new=88.0, t="2026-10-05T14:25:00Z"))
            fh.write(J(kind="order", ticker="KXBTC15M-A", t="2026-10-05T15:00:00Z"))
            fh.write(J(kind="autosize", old=88.0, new=90.0, t="2026-10-06T02:00:00Z"))
        arm = os.path.join(d, "pinrun-paper-20261004T003604Z.jsonl")
        with open(arm, "w") as fh:
            fh.write(J(kind="start", size=20.0, t="2026-10-04T00:36:04Z", code_sha="f9548c5571ff"))
            fh.write(J(kind="autosize", old=20.0, new=44.0, t="2026-10-05T00:00:00Z"))
            # BEFORE the window: must not count
            fh.write(J(kind="signal", live=False, ticker="KXHYPE15M-OLD", take_n=44, price=0.97, t="2026-10-05T14:00:00Z"))
            fh.write(J(kind="settled", ticker="KXHYPE15M-OLD", pnl_c=-4000.0, t="2026-10-05T14:15:20Z"))
            # a win at arm size 44, live 88 -> x2
            fh.write(J(kind="signal", live=False, ticker="KXHYPE15M-W1", take_n=44, price=0.97, t="2026-10-05T15:14:40Z"))
            fh.write(J(kind="settled", ticker="KXHYPE15M-W1", pnl_c=110.0, realised=1.1, t="2026-10-05T15:15:20Z"))
            # a BTC market: not HYPE, never counted
            fh.write(J(kind="signal", live=False, ticker="KXBTC15M-B1", take_n=44, price=0.97, t="2026-10-05T15:14:40Z"))
            fh.write(J(kind="settled", ticker="KXBTC15M-B1", pnl_c=-5000.0, t="2026-10-05T15:15:20Z"))
            # a hedged LOSER: entry leg -42.68, hedge leg +8.0 -> one market, -34.68 x2
            fh.write(J(kind="signal", live=False, ticker="KXHYPE15M-L1", take_n=44, price=0.97, t="2026-10-06T03:59:30Z"))
            fh.write(J(kind="hedge", live=False, ticker="KXHYPE15M-L1", n=44, price=0.80, t="2026-10-06T03:59:45Z"))
            fh.write(J(kind="settled", ticker="KXHYPE15M-L1", pnl_c=-4268.0, t="2026-10-06T03:59:58Z"))
            fh.write(J(kind="settled", ticker="KXHYPE15M-L1", pnl_c=800.0, t="2026-10-06T03:59:59Z"))
            # the arm catches up to live (90) and a win settles on 10-06 ET
            fh.write(J(kind="autosize", old=44.0, new=90.0, t="2026-10-06T04:10:00Z"))
            fh.write(J(kind="signal", live=False, ticker="KXHYPE15M-W2", take_n=90, price=0.98, t="2026-10-06T04:14:40Z"))
            fh.write(J(kind="settled", ticker="KXHYPE15M-W2", pnl_c=150.0, t="2026-10-06T04:15:20Z"))
            fh.write('{"ticker": "KXHYPE15M-TORN", "pnl\n')
            fh.write(J(kind="loop", t="2026-10-06T05:00:00Z"))
        lt = live_sizes(d)
        ck(lt == [(ts("2026-10-05T14:24:02Z"), 20.0), (ts("2026-10-05T14:25:00Z"), 88.0),
                  (ts("2026-10-06T02:00:00Z"), 90.0)],
           "live size timeline from start + autosize records only (%d points)" % len(lt))
        meta, sz, mk = read_arm(arm, ts(SINCE))
        ck(sorted(mk) == ["KXHYPE15M-L1", "KXHYPE15M-W1", "KXHYPE15M-W2"],
           "only HYPE markets settled AFTER the window start (BTC and the 14:15Z one are out): %s" % sorted(mk))
        ck(mk["KXHYPE15M-L1"]["legs"] == 2 and abs(mk["KXHYPE15M-L1"]["pnl_c"] + 3468.0) < 1e-9,
           "entry and hedge legs are ONE market: -42.68 + 8.00 = -34.68")
        ck(meta["bad_lines"] == 1 and meta["code_sha"] == "f9548c5571ff" and meta["last_t"] == "2026-10-06T05:00:00Z",
           "a torn line is counted, not fatal; start code_sha and last record read")
        rows = shadow(mk, sz, lt)
        by = dict((r["ticker"], r) for r in rows)
        ck(abs(by["KXHYPE15M-W1"]["factor"] - 2.0) < 1e-9 and abs(by["KXHYPE15M-W1"]["usd"] - 2.2) < 1e-9,
           "scaled to LIVE's size at entry: arm 44, live 88 -> x2, +$1.10 -> +$2.20")
        ck(abs(by["KXHYPE15M-L1"]["factor"] - 90.0 / 44.0) < 1e-9
           and abs(by["KXHYPE15M-L1"]["usd"] + 34.68 * 90.0 / 44.0) < 1e-9
           and abs(by["KXHYPE15M-L1"]["spent"] - (44 * 0.97 + 44 * 0.80) * 90.0 / 44.0) < 1e-9,
           "the loser scales at live 90 / arm 44 and its money bet counts entry + hedge")
        ck(abs(by["KXHYPE15M-W2"]["factor"] - 1.0) < 1e-9, "arm and live at the same size -> x1")
        ck(by["KXHYPE15M-L1"]["day"] == "2026-10-05" and by["KXHYPE15M-W2"]["day"] == "2026-10-06",
           "ET day: 03:59Z on 10-06 is still 10-05 ET (EDT); 04:15Z is 10-06")
        agg = summarise(rows)
        ck(agg["ALL"]["markets"] == 3 and agg["ALL"]["won"] == 2 and agg["ALL"]["lost"] == 1
           and abs(agg["ALL"]["net"] - (2.2 - 34.68 * 90 / 44 + 1.5)) < 1e-9
           and agg["2026-10-05"]["markets"] == 2 and agg["2026-10-06"]["markets"] == 1,
           "per-day and total counts and net (%+.2f)" % agg["ALL"]["net"])
        _, _, none = read_arm(arm, ts("2026-10-07T00:00:00Z"))
        ck(summarise(shadow(none, sz, lt)) == {}, "NULL: a window with nothing settled gives nothing, not zeros invented")
        _, _, half = read_arm(arm, ts(SINCE), until=ts("2026-10-06T00:00:00Z"))
        ck(sorted(half) == ["KXHYPE15M-W1"], "an `until` bound excludes later settlements")
        ck(size_at([], ts(SINCE), 20.0) == 20.0 and shadow({"KXHYPE15M-X": {"pnl_c": 100.0, "legs": 1,
           "t_settle": ts(SINCE), "t_first": ts(SINCE), "spent": 1.0}}, [], [])[0]["factor"] == 1.0,
           "no live size known -> factor 1 (the arm's own money), never a guess")
        ck(et_day(ts("2026-12-01T04:30:00Z")) == "2026-11-30", "EST in December (UTC-5)")
        for n in ("20260929T185918Z", "20261006T185948Z", "20261006T190030Z"):
            open(os.path.join(d, "pinrun-paper-%s.jsonl" % n), "w").close()
        ck(os.path.basename(find_twin_log(d)) == "pinrun-paper-20260929T185918Z.jsonl"
           and os.path.basename(find_twin_log(d, TWIN2_START)) == "pinrun-paper-20261006T185948Z.jsonl"
           and find_twin_log(d, "2026-10-08T00:00:00Z") is None,
           "each twin log found by its own start (nearest within 30 s); no log near a start -> None")
        lines = []
        report("arm", arm, ts(SINCE), lt, out=lines.append)
        ck(any("TOTAL" in x for x in lines) and any(x.strip().startswith("lost: KXHYPE15M-L1") for x in lines),
           "the report prints a total and names the loser")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("SELF-TEST %s (%d failed)" % ("PASSED" if not fails else "*** FAILED ***", len(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", default=SINCE)
    ap.add_argument("--until", default=None)
    ap.add_argument("--results", default=RESULTS)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            ok = selftest()
        if not ok:
            print("hype_shadow: SELF-TEST FAILED -- not reading real data (run --selftest)")
            sys.exit(1)
    since, until = ts(a.since), (ts(a.until) if a.until else None)
    lt = live_sizes(a.results)
    print("HYPE SHADOW -- what live would have made on KXHYPE15M since %s (v-skiphype), PAPER."
          % et_str(since))
    print("Paper books what the book showed; live gets sold to on losers (NEAR 10-03: live 94"
          " contracts vs paper 4), so the LOSS side here is optimistic -- an upper bound.")
    print("Live size now %s (last autosize %s)." % (
        lt[-1][1] if lt else "unknown", et_str(lt[-1][0]) if lt else "-"))
    report("arm-0925b (09-25 code = live's base; early-min-price 0.95, no full-bet cap)",
           arm_0925b_log(a.results), since, lt, until)
    report("arm-live-twin (live code+argv as of 09-29)", find_twin_log(a.results), since, lt, until)
    # the 7-day twin ended 10-06 18:59Z and was relaunched identically, but on the repo's
    # pinrun of that day (code_sha printed) -- reported separately so each window names its code
    report("arm-live-twin relaunch (same argv, 10-06 repo code)",
           find_twin_log(a.results, TWIN2_START), since, lt, until)


if __name__ == "__main__":
    main()
