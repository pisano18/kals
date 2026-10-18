#!/usr/bin/env python3
r"""bars.py -- every running test against the bar written for it BEFORE its data.

THE OPERATOR, 2026-09-24: one place that says, for each test in flight, what
the bar was, the numbers so far, how far into its window it is, and one word
-- PASS / KILL / EXTEND / TOO EARLY -- the bar exactly as it was written, never
a softened reading of it. `/bars` on the phone prints this same text.

WHAT IS READ, AND FROM WHERE (read-only, nothing here writes)
  money           Kalshi's own books, results/kalshi_ledger.json, one row per
                  market (a coin race tie is `value: 50`). Never a bot's
                  running total.
  arm vs live     the paper arms' and the live bot's own `settled.pnl_c`
                  records on the SAME markets over closes both were up for --
                  results/cf_2026-09-24/armh2h2.py's method, copied here: a
                  paper log is matched to its arm by how its start record
                  differs from live's start record of the same moment
                  (sync_arms.ps1), because the arm-*.out files only name the
                  CURRENT run. (armh2h2's close_of() cannot read an hourly
                  ticker; pinflat.close_epoch can, and is used instead.)
  fresh fills     the live bot's signal records (`level_age_ms`,
                  `level_age_exact`) and order records (`tau_at_send`,
                  `filled`): the FIRST fill per market, joined to the ledger.
  hourly BTC      live order records on KXBTCD tickers (asked vs filled,
                  price) and the ledger's KXBTCD rows; the paper arm-btcd's
                  KXBTCD signals and settled records.
  coin race       the ledger's KXCRYPTOLEAD15M rows since v-race5 and since
                  v-race30; the z3 arm's own log against its bar; the gap075
                  arm's photo-finish refusals against how those races settled.
  weather, quakes `wxwatch.py --report` and `quakewatch.py --report`, called
                  (never reimplemented); their PASS/FAIL-so-far lines quoted.

THE BARS, verbatim from where they were written. Edit the source file first,
then this copy, with the date:
  arm-fresh500  results/PREREG_fresh.md (2026-09-24 ~08:1xZ): read after >= 7
                days beside live. DEPLOY if live's fresh (<500 ms, >20 s) fills
                over the window are net <= +$25 AND contain >= 2 losers, and the
                arm shows no loser live did not also have. KILL if net >= +$100
                with <= 1 loser. Otherwise extend 7 more days.
  hourly BTC    results/IDEAS_2026-09-24.md item 2 (paper, 7 days): >= 30
                fired closes; 0 paper losses at <= 30 s; >= 660 paper-captured
                contracts. The LIVE 1-contract run (v-btcd1) has no pass/kill
                number -- OPEN_WORK A2 says "~30 fired closes, watching whether
                we get filled and at what price" -- so it is read only.
  z3            OPEN_WORK B3 / VERSIONS v-race5: 250 races with at most one
                loss (a tie is a loss); kill at 2 losses in the first 50.
  control arms  no bar. Read only.

    python research/bars.py                  # the text
    python research/bars.py --json           # the same numbers as JSON
    python research/bars.py --selftest
    python research/bars.py --results DIR --now 2026-10-01T12:00:00Z
"""
import calendar
import collections
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinphone                                                      # noqa: E402
import pinflat                                                       # noqa: E402
from pindesk import et_str, money                                    # noqa: E402

RESULTS = pinphone.RESULTS
DAY = 86400.0

# ---- arm-fresh500: results/PREREG_fresh.md --------------------------------
FRESH_ARM = "arm-fresh500"
FRESH_START_UTC = "2026-09-24T08:08:23Z"     # the arm's first start record
FRESH_WINDOW_DAYS = 7
FRESH_AGE_MS, FRESH_TAU_MIN = 500, 20
FRESH_DEPLOY_NET, FRESH_DEPLOY_LOSERS = 25.0, 2
FRESH_KILL_NET, FRESH_KILL_LOSERS = 100.0, 1
FRESH_BAR = ("DEPLOY if live's fresh (<500 ms, >20 s) fills over the window are net <= +$25 AND "
             "contain >= 2 losers, and the arm shows no loser live did not also have. KILL if net "
             ">= +$100 with <= 1 loser. Otherwise extend 7 more days.")

# ---- hourly BTC: results/IDEAS_2026-09-24.md item 2, VERSIONS v-btcd1 -----
BTCD_ARM = "arm-btcd"
BTCD_SERIES = "KXBTCD-"
BTCD_LIVE_UTC = "2026-09-24T16:48:35Z"       # v-btcd1: the live bot's start with --series KXBTCD
BTCD_PAPER_UTC = "2026-09-24T07:57:57Z"      # arm-btcd's first log
BTCD_WINDOW_DAYS = 7
BTCD_BAR_FIRED, BTCD_BAR_CONTRACTS, BTCD_LOSS_TAU = 30, 660, 30
BTCD_BAR = (">= 30 fired closes; 0 paper losses at <= 30 s; paper-captured contracts >= 660 "
            "(20% of the tape's capped 3,305 for the week).")

# ---- coin race: VERSIONS v-race5 / v-race30, OPEN_WORK B3 ------------------
RACE5_UTC = "2026-09-24T15:16:00Z"
RACE30_UTC = pinphone.RACE30_UTC
Z3_PASS, Z3_KILL = (250, 1), (2, 50)
Z3_BAR = "250 races with at most 1 loss (a tie is a loss); KILL at 2 losses in the first 50."
GAP075_LOG = "pinracearm-gap075.jsonl"
Z3_LOG = "pinracearm-z3.jsonl"

# ---- control arms: no bar --------------------------------------------------
CONTROL_ARMS = ("arm-edge2c", "arm-lateadd-off", "arm-afternoon", "arm-live-frozen", "arm-brake3")
H2H_SINCE_UTC = "2026-09-20T14:23:00Z"       # armh2h2's default: the first close every arm could hedge
NO_BAR = "no pre-registered bar; read only."

# start-record keys that differ between any two runs without meaning a
# different rule (armh2h2.NOISE, verbatim)
NOISE = {"t", "day_loss_at_start", "kind", "mode", "code_sha", "size", "minutes", "pid", "traj_file",
         "live", "paper", "log", "out", "arm_name", "attempts_on_send", "doubt_hist_tau_s",
         "doubt_mult", "traj_tau_max", "traj_every_s", "traj_near_tau_s", "hedge_belief_src"}

WATCHERS = (("WEATHER (the hourly temperature idea)", "wxwatch.py"),
            ("EARTHQUAKES (the biggest-quake idea)", "quakewatch.py"))
WATCH_LINE = re.compile(r"PASS so far|FAIL so far|^BAR \d|days so far|of the \d+ the bar asks for|^\S+ report:")


# ===========================================================================
# small helpers
# ===========================================================================
def ep(t):
    """UTC epoch from an ISO 'Z' stamp (fractions ignored); None if unreadable."""
    try:
        return calendar.timegm(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def et(epoch, fmt="%m/%d %I:%M %p"):
    return et_str(epoch, fmt) + " ET"


def _n(n, word):
    n = int(n)
    if n == 1:
        return "1 %s" % word
    if word.endswith("y"):
        return "%d %sies" % (n, word[:-1])
    return "%d %s%s" % (n, word, "es" if word.endswith("s") else "s")


def days_in(now, start_e):
    return max(0.0, (now - start_e) / DAY)


def _stamp_of(path):
    m = re.search(r"(\d{8}T\d{6})Z\.jsonl$", str(path).replace("\\", "/"))
    if not m:
        return None
    try:
        return calendar.timegm(time.strptime(m.group(1), "%Y%m%dT%H%M%S"))
    except ValueError:
        return None


def _tail_t(path, span=65536):
    """The `t` of the last readable record in a jsonl file, from its tail."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - span))
            chunk = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in reversed(chunk.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("t"):
            return ep(d["t"])
    return None


# ===========================================================================
# the bots' own logs
# ===========================================================================
def load_run(path, since_e=None, keep=(), count=None):
    """One pinrun log, read once, line by line, screened by substring before
    json.loads (a log is mostly refusals and universe lines).

    start    its first start record
    lo / hi  first and last record time
    settled  {ticker: money} = settled.pnl_c / 100 summed, for settles at or
             after `since_e` (armh2h2's rule: the market's own money, never
             the `realised` running total)
    kept     the records of `keep` kinds, in file order
    counts   {name: lines containing that substring} for `count`
    """
    needles = {k: '"kind": "%s"' % k for k in set(keep) | {"start", "settled"}}
    count = count or {}
    out = dict(path=path, start=None, lo=None, hi=None, settled={}, kept=[],
               counts={k: 0 for k in count})
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            if out["lo"] is None:
                try:
                    d0 = json.loads(line)
                except ValueError:
                    d0 = None
                if isinstance(d0, dict) and d0.get("t"):
                    out["lo"] = ep(d0["t"])
            for name, needle in count.items():
                if needle in line:
                    out["counts"][name] += 1
            if not any(n in line for n in needles.values()):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            k = d.get("kind")
            if k == "start":
                if out["start"] is None:
                    out["start"] = d
            elif k == "settled":
                tk = d.get("ticker")
                t = ep(d.get("t"))
                if tk and d.get("pnl_c") is not None and t is not None and (since_e is None or t >= since_e):
                    out["settled"][tk] = out["settled"].get(tk, 0.0) + _f(d["pnl_c"]) / 100.0
            if k in keep:
                out["kept"].append(d)
    out["hi"] = _tail_t(path)
    if out["lo"] is None and out["start"]:
        out["lo"] = ep(out["start"].get("t"))
    return out


def _recent(paths, since_e, slack_days=4):
    """Logs whose START stamp could still hold records after `since_e` (a run
    lives at most --minutes 4320 = 3 days)."""
    for p in sorted(paths):
        st = _stamp_of(p)
        if st is None or st >= since_e - slack_days * DAY:
            yield p


def live_runs(results, since_e, keep=()):
    runs = []
    for p in _recent(glob.glob(os.path.join(results, "pinrun-live-*.jsonl")), since_e):
        x = load_run(p, since_e, keep)
        if x and x["start"] and x["hi"] is not None and x["hi"] >= since_e:
            runs.append(x)
    return runs


def live_start_at(live, t):
    c = [x["start"] for x in live if x["lo"] is not None and t is not None and x["lo"] <= t + 120]
    if c:
        return c[-1]
    return live[0]["start"] if live else {}


def up(spans, c):
    """Was some run of this bot up from 50 s before the close through it?"""
    return any(lo is not None and hi is not None and lo <= c - 50 and hi >= c for lo, hi in spans)


def current_names(results):
    """{log stamp: arm name} from the arm-*.out files (they name only the CURRENT run)."""
    cur = {}
    for o in glob.glob(os.path.join(results, "arm-*.out")):
        nm = os.path.basename(o)[:-4]
        try:
            with open(o, encoding="utf-8", errors="replace") as fh:
                txt = fh.read(262144)
        except OSError:
            continue
        for s in re.findall(r"pinrun-paper-(\d{8}T\d{6}Z)\.jsonl", txt):
            cur[s] = nm
    return cur


def arm_groups(results, live, since_e, keep_for=None, count_for=None):
    """[{names, sig, logs}] -- paper logs grouped by how their start record
    differs from live's start record of the same moment (armh2h2's method).
    `keep_for` / `count_for`: {arm name: ...} extra reads for named arms
    (looked up by the .out name of the log)."""
    cur = current_names(results)
    keep_for = keep_for or {}
    count_for = count_for or {}
    groups = collections.OrderedDict()
    for p in _recent(glob.glob(os.path.join(results, "pinrun-paper-*.jsonl")), since_e):
        m = re.search(r"paper-(\d{8}T\d{6}Z)", p.replace("\\", "/"))
        nm = cur.get(m.group(1)) if m else None
        x = load_run(p, since_e, keep_for.get(nm, ()), count_for.get(nm))
        if not x or not x["start"] or x["lo"] is None:
            continue
        ls = live_start_at(live, x["lo"])
        diff = tuple(sorted((k, json.dumps(x["start"].get(k), sort_keys=True), json.dumps(ls.get(k), sort_keys=True))
                            for k in set(x["start"]) | set(ls)
                            if k not in NOISE and x["start"].get(k) != ls.get(k)))
        sig = tuple((k, a) for k, a, b in diff)
        x["name"] = nm
        g = groups.setdefault(sig, {"sig": sig, "names": set(), "logs": []})
        g["logs"].append(x)
        if nm:
            g["names"].add(nm)
    return list(groups.values())


def h2h(live, logs, ladder=None):
    """Arm vs live on the SAME markets over closes both were up for.

    `ladder`: does the arm trade the hourly BTC ladder? Detected from its start
    records when None. An arm without it never sees a KXBTCD rung, so those
    markets are left out of BOTH sides rather than booked as live-only money
    the arm "missed".

    same / arm / live / h2h: markets both settled, each bot's own money on them,
    arm minus live. arm_only / live_only: markets only one took, over closes
    both were up for, with that bot's money. edge = h2h + arm-only - live-only
    = what the arm would have made over live on those closes.
    arm_extra_losers: markets the arm lost that live did not lose."""
    if ladder is None:
        ladder = any("KXBTCD" in ((x["start"] or {}).get("ladder_series") or []) for x in logs)

    def keep(tk):
        return ladder or not str(tk).startswith(BTCD_SERIES)
    L = {}
    Lspans = []
    for x in live:
        L.update({tk: v for tk, v in x["settled"].items() if keep(tk)})
        Lspans.append((x["lo"], x["hi"]))
    A = {}
    spans = []
    for x in logs:
        A.update({tk: v for tk, v in x["settled"].items() if keep(tk)})
        spans.append((x["lo"], x["hi"]))

    def both(tk):
        c = pinflat.close_epoch(tk)
        return c is not None and up(spans, c) and up(Lspans, c)
    common = [tk for tk in A if tk in L and both(tk)]
    arm_only = [tk for tk in A if tk not in L and both(tk)]
    live_only = [tk for tk in L if tk not in A and both(tk)]
    a_sum = sum(A[t] for t in common)
    l_sum = sum(L[t] for t in common)
    ao = sum(A[t] for t in arm_only)
    lo_ = sum(L[t] for t in live_only)
    hours = sum((hi - lo) for lo, hi in spans if lo is not None and hi is not None) / 3600.0
    extra = sorted(tk for tk in common + arm_only if A[tk] < 0 and L.get(tk, 0.0) >= 0)
    return dict(logs=len(logs), hours=hours, same=len(common), arm=a_sum, live=l_sum, h2h=a_sum - l_sum,
                arm_only_n=len(arm_only), arm_only=ao, live_only_n=len(live_only), live_only=lo_,
                edge=(a_sum - l_sum) + ao - lo_, arm_extra_losers=extra)


def group_named(groups, name):
    for g in groups:
        if name in g["names"]:
            return g
    return None


def h2h_words(name, r, since_e):
    """The plain reading of one arm's head-to-head."""
    if r is None:
        return "%s: no paper log found for it since %s." % (name, et(since_e))
    if not r["same"] and not r["arm_only_n"] and not r["live_only_n"]:
        return "%s: %s Up %.0f h (%s), but no settled market yet on a close both bots were up for." % (
            name, NO_BAR, r["hours"], _n(r["logs"], "log"))
    L = ["%s: %s" % (name, NO_BAR)]
    if r["same"]:
        lead = "even" if abs(r["h2h"]) < 0.005 else ("arm ahead by %s" % money(abs(r["h2h"]), False) if r["h2h"] > 0
                                                       else "arm behind by %s" % money(abs(r["h2h"]), False))
        L.append("Same markets %d: arm %s, live %s -- head to head %s (%s)." % (
            r["same"], money(r["arm"]), money(r["live"]), money(r["h2h"]), lead))
    L.append("Arm-only markets %d (%s); live-only markets %d (%s)." % (
        r["arm_only_n"], money(r["arm_only"]), r["live_only_n"], money(r["live_only"])))
    verb = "more" if r["edge"] >= 0 else "less"
    L.append("Over these closes the arm would have made %s %s than live (%.0f h of overlap, %s)." % (
        money(abs(r["edge"]), False), verb, r["hours"], _n(r["logs"], "log")))
    if r["arm_extra_losers"]:
        L.append("The arm lost on %s live did not: %s." % (
            _n(len(r["arm_extra_losers"]), "market"), ", ".join(pinphone._leg_name(t) for t in r["arm_extra_losers"])))
    return "\n".join(L)


# ===========================================================================
# A1. the fresh offer test
# ===========================================================================
def fresh_fills(live, since_e, until_e, markets):
    """Live's FIRST filled order per market, with the fresh flag: the level it
    hit had an exact age under 500 ms and more than 20 s were left when the
    order went out. `markets` is the ledger (pinphone.markets_from) for the
    money and the result."""
    firsts = {}
    for x in live:
        last_sig = {}
        for d in x["kept"]:
            k = d.get("kind")
            tk = d.get("ticker")
            if not tk or tk.startswith(BTCD_SERIES):      # the hourly rungs are not in the arm's universe
                continue
            if k == "signal":
                last_sig[tk] = d
            elif k == "order":
                if tk in firsts or _f(d.get("filled")) <= 0:
                    continue
                s = last_sig.get(tk) or {}
                tau = d.get("tau_at_send", s.get("tau"))
                firsts[tk] = dict(tk=tk, t=ep(d.get("t")), tau=None if tau is None else _f(tau),
                                  age_ms=s.get("level_age_ms"), exact=bool(s.get("level_age_exact")),
                                  filled=_f(d.get("filled")), price=d.get("exec_price"))
    out = []
    for tk, f in firsts.items():
        if f["t"] is None or f["t"] < since_e or (until_e is not None and f["t"] > until_e):
            continue
        f["fresh"] = bool(f["exact"] and f["age_ms"] is not None and _f(f["age_ms"]) < FRESH_AGE_MS
                          and f["tau"] is not None and f["tau"] > FRESH_TAU_MIN)
        m = markets.get(tk)
        f["settled"] = m is not None
        f["pnl"] = m["pnl"] if m else None
        f["lost"] = (m["pnl"] < 0) if m else None
        out.append(f)
    out.sort(key=lambda f: f["t"])
    return out


def fresh_verdict(net, losers, arm_extra_losers, days):
    """(word, why) for the fresh test, the bar as written in PREREG_fresh.md."""
    if net <= FRESH_DEPLOY_NET and losers >= FRESH_DEPLOY_LOSERS and arm_extra_losers == 0:
        word = "PASS"
        why = ("deploy the rule: live's fresh fills are net %s with %s (bar: <= +$25 and >= 2 losers, "
               "no arm-only loser)" % (money(net), _n(losers, "loser")))
    elif net >= FRESH_KILL_NET and losers <= FRESH_KILL_LOSERS:
        word = "KILL"
        why = "live's fresh fills are net %s with %s (bar: >= +$100 with <= 1 loser)" % (money(net), _n(losers, "loser"))
    else:
        word = "EXTEND"
        why = "neither bar is met: net %s with %s" % (money(net), _n(losers, "loser"))
        if arm_extra_losers:
            why += " and the arm has %s live did not" % _n(arm_extra_losers, "loser")
        why += "; 7 more days"
    if days < FRESH_WINDOW_DAYS:
        return "TOO EARLY", "day %.1f of %d; read today it would say %s: %s" % (days, FRESH_WINDOW_DAYS, word, why)
    return word, why


def fresh_data(live, groups, markets, now):
    # 2026-09-25 (audit, verified): the window starts at the PRE-REGISTERED
    # time, never earlier. It used to widen to the oldest log in the arm's
    # group -- and that group also holds every live-identical paper log back
    # to 09-20, so /bars read the fresh test over the very losses that chose
    # the rule and would have printed "PASS -- deploy" on 09-27, 4 days early.
    start_e = ep(FRESH_START_UTC)
    g = group_named(groups, FRESH_ARM)
    end_e = start_e + FRESH_WINDOW_DAYS * DAY
    fills = fresh_fills(live, start_e, min(now, end_e), markets)
    fresh = [f for f in fills if f["fresh"]]
    settled = [f for f in fresh if f["settled"]]
    losers = [f for f in settled if f["lost"]]
    net = sum(f["pnl"] for f in settled)
    r = h2h(live, g["logs"]) if g else None
    refused = sum(x["counts"].get("fresh_level", 0) for x in g["logs"]) if g else 0
    days = days_in(now, start_e)
    word, why = fresh_verdict(net, len(losers), len(r["arm_extra_losers"]) if r else 0, days)
    return dict(arm=FRESH_ARM, start=start_e, end=end_e, days=round(days, 2), window_days=FRESH_WINDOW_DAYS,
                bar=FRESH_BAR, first_fills=len(fills), fresh=len(fresh), settled=len(settled),
                won=len(settled) - len(losers), losers=len(losers), unsettled=len(fresh) - len(settled),
                net=round(net, 2), loser_list=[dict(tk=f["tk"], t=f["t"], pnl=round(f["pnl"], 2)) for f in losers],
                arm_refused_fresh=refused, h2h=r, verdict=word, why=why, arm_running=bool(g))


def fresh_text(d):
    L = ["FRESH OFFER TEST (%s) -- day %.1f of %d (window %s to %s)." % (
        d["arm"], d["days"], d["window_days"], et(d["start"]), et(d["end"]))]
    L.append("The bar (PREREG_fresh.md): " + d["bar"])
    if not d["arm_running"]:
        L.append("No paper log for %s was found -- the arm is not running or its .out file does not name its log." % d["arm"])
    L.append("So far: live made %s in the window on the 15-minute markets; %d of them fresh (offer under half a "
             "second old, more than 20 s left): %d won, %d lost, %d not settled yet; net %s." % (
                 _n(d["first_fills"], "first fill"), d["fresh"], d["won"], d["losers"], d["unsettled"], money(d["net"])))
    if d["loser_list"]:
        L.append("Fresh losers: " + "; ".join("%s %s %s" % (pinphone._leg_name(x["tk"]), et(x["t"]), money(x["pnl"]))
                                             for x in d["loser_list"]) + ".")
    r = d["h2h"]
    if r:
        L.append("Arm vs live on the same closes: same markets %d, arm %s, live %s; live-only %d (%s); the arm "
                 "refused %s as fresh; arm-only losers: %d." % (
                     r["same"], money(r["arm"]), money(r["live"]), r["live_only_n"], money(r["live_only"]),
                     _n(d["arm_refused_fresh"], "entry"), len(r["arm_extra_losers"])))
    L.append("VERDICT: %s -- %s." % (d["verdict"], d["why"]))
    return "\n".join(L)


# ===========================================================================
# A2. hourly BTC: live at one contract, and the paper arm beside it
# ===========================================================================
def btcd_live_orders(live, since_e):
    """Every live order on an hourly BTC ticker since `since_e`: asked vs got."""
    out = []
    for x in live:
        for d in x["kept"]:
            if d.get("kind") != "order" or not str(d.get("ticker") or "").startswith(BTCD_SERIES):
                continue
            t = ep(d.get("t"))
            if t is None or t < since_e:
                continue
            asked = d.get("count_asked")
            if asked is None:
                asked = (d.get("body") or {}).get("count")
            out.append(dict(tk=d["ticker"], t=t, asked=_f(asked), filled=_f(d.get("filled")),
                            price=d.get("exec_price"), tau=d.get("tau_at_send")))
    out.sort(key=lambda o: o["t"])
    return out


def btcd_paper(logs, since_e):
    """The paper arm's hourly-BTC record: fired closes (distinct hours with a
    signal), contracts it would have taken (signal take_n), settles and losses,
    a loss at <= 30 s being the one the bar forbids."""
    first_tau = {}
    take = 0.0
    closes = set()
    for x in logs:
        for d in x["kept"]:
            if d.get("kind") != "signal" or not str(d.get("ticker") or "").startswith(BTCD_SERIES):
                continue
            t = ep(d.get("t"))
            if t is None or t < since_e:
                continue
            tk = d["ticker"]
            first_tau.setdefault(tk, _f(d.get("tau"), 999))
            take += _f(d.get("take_n"))
            c = pinflat.close_epoch(tk)
            closes.add(c if c is not None else tk)
    settled = {}
    for x in logs:
        for tk, v in x["settled"].items():
            if tk.startswith(BTCD_SERIES):
                settled[tk] = v
    lost = [tk for tk, v in settled.items() if v < 0]
    lost_le30 = [tk for tk in lost if first_tau.get(tk, 999) <= BTCD_LOSS_TAU]
    return dict(fired=len(closes), contracts=round(take, 2), settled=len(settled), won=len(settled) - len(lost),
                lost=len(lost), lost_le30=len(lost_le30), net=round(sum(settled.values()), 2))


def btcd_verdict(fired, lost_le30, contracts, days):
    """(word, why) for the paper bar, IDEAS_2026-09-24.md item 2."""
    have = "%s, %s inside 30 s, %.0f contracts" % (_n(fired, "fired close"), _n(lost_le30, "paper loss"), contracts)
    if lost_le30 > 0:
        return "KILL", "a paper loss inside 30 s; the bar allows 0 (%s)" % have
    if days < BTCD_WINDOW_DAYS:
        return "TOO EARLY", "day %.1f of %d; needs >= %d fired closes, 0 losses inside 30 s, >= %d contracts; has %s" % (
            days, BTCD_WINDOW_DAYS, BTCD_BAR_FIRED, BTCD_BAR_CONTRACTS, have)
    if fired >= BTCD_BAR_FIRED and contracts >= BTCD_BAR_CONTRACTS:
        return "PASS", "%s; bar >= %d closes, 0 losses inside 30 s, >= %d contracts" % (have, BTCD_BAR_FIRED, BTCD_BAR_CONTRACTS)
    return "KILL", "the week is up and the bar is not met: %s (needs >= %d closes and >= %d contracts)" % (
        have, BTCD_BAR_FIRED, BTCD_BAR_CONTRACTS)


def btcd_data(live, groups, markets, now):
    live_e = ep(BTCD_LIVE_UTC)
    orders = btcd_live_orders(live, live_e)
    filled = [o for o in orders if o["filled"] > 0]
    got = sum(o["filled"] for o in filled)
    asked = sum(o["asked"] for o in orders)
    avg = (sum(o["filled"] * _f(o["price"]) for o in filled) / got) if got else None
    ms = [m for m in markets.values() if m["tk"].startswith(BTCD_SERIES)
          and m["close"] is not None and m["close"] >= live_e]
    lost = [m for m in ms if not m["won"]]
    g = group_named(groups, BTCD_ARM)
    paper_e = ep(BTCD_PAPER_UTC)   # the pre-registered start, never widened (see fresh_data)
    pp = btcd_paper(g["logs"], paper_e) if g else None
    pdays = days_in(now, paper_e)
    if pp:
        word, why = btcd_verdict(pp["fired"], pp["lost_le30"], pp["contracts"], pdays)
    else:
        word, why = "TOO EARLY", "no paper log for %s was found" % BTCD_ARM
    return dict(live_since=live_e, live_days=round(days_in(now, live_e), 2),
                orders=len(orders), filled_orders=len(filled), asked=round(asked, 2), got=round(got, 2),
                avg_price=None if avg is None else round(avg, 4),
                ledger_markets=len(ms), ledger_won=len(ms) - len(lost), ledger_lost=len(lost),
                ledger_net=round(sum(m["pnl"] for m in ms), 2),
                paper_arm=BTCD_ARM, paper_since=paper_e, paper_days=round(pdays, 2), window_days=BTCD_WINDOW_DAYS,
                bar=BTCD_BAR, paper=pp, h2h=h2h(live, g["logs"]) if g else None, verdict=word, why=why)


def btcd_text(d):
    L = ["HOURLY BTC, LIVE at 1 contract a market (v-btcd1) -- day %.1f since %s." % (d["live_days"], et(d["live_since"]))]
    L.append("No pass/kill number was written for the live fills (OPEN_WORK A2: ~30 fired closes, watching "
             "whether we get filled and at what price); read only.")
    if d["orders"]:
        L.append("Orders: %d sent, %d filled; asked %g, got %g contracts%s." % (
            d["orders"], d["filled_orders"], d["asked"], d["got"],
            (", avg price %.1fc" % (100.0 * d["avg_price"])) if d["avg_price"] is not None else ""))
    else:
        L.append("Orders: none on the hourly BTC markets yet.")
    if d["ledger_markets"]:
        L.append("Kalshi's books: %s settled, %d won, %d lost, %s." % (
            _n(d["ledger_markets"], "market"), d["ledger_won"], d["ledger_lost"], money(d["ledger_net"])))
    else:
        L.append("Kalshi's books: nothing settled on the hourly BTC markets since then.")
    L.append("Paper %s beside it -- day %.1f of %d (since %s). The bar (IDEAS item 2): %s" % (
        d["paper_arm"], d["paper_days"], d["window_days"], et(d["paper_since"]), d["bar"]))
    p = d["paper"]
    if p:
        L.append("So far on paper: %s, %.0f contracts, %s (%d won, %d lost, %d lost inside 30 s), %s on its own log." % (
            _n(p["fired"], "fired close"), p["contracts"], _n(p["settled"], "settle"), p["won"], p["lost"],
            p["lost_le30"], money(p["net"])))
    else:
        L.append("No paper log for %s was found." % d["paper_arm"])
    L.append("VERDICT (paper bar): %s -- %s." % (d["verdict"], d["why"]))
    return "\n".join(L)


# ===========================================================================
# B. the coin race
# ===========================================================================
def z3_verdict(races, losses, first50_losses):
    """(word, why) for the z3 arm's bar."""
    if first50_losses >= Z3_KILL[0]:
        return "KILL", "%d losses in the first %d (bar kills at %d)" % (first50_losses, Z3_KILL[1], Z3_KILL[0])
    if races >= Z3_PASS[0] and losses <= Z3_PASS[1]:
        return "PASS", "%d races with %s (bar: %d with at most %d)" % (races, _n(losses, "loss"), Z3_PASS[0], Z3_PASS[1])
    if losses > Z3_PASS[1]:
        return "KILL", "%s in %d races; the bar allows at most %d in %d, so it can no longer pass" % (
            _n(losses, "loss"), races, Z3_PASS[1], Z3_PASS[0])
    return "TOO EARLY", "%d of %d races, %s so far (first 50: %d)" % (races, Z3_PASS[0], _n(losses, "loss"), first50_losses)


def photo_finishes(gap_log, races, arm_res):
    """The gap075 arm's photo-finish refusals (no_trade / small_gap), and how
    those races went on Kalshi's books (the penny bot's real legs) and in the
    arm's own log (did it still enter on another leg)."""
    recs = pinphone.log_records(gap_log, ("start", "no_trade"))
    start = next((r for r in recs if r.get("kind") == "start"), None)
    evts = collections.OrderedDict()
    for r in recs:
        if r.get("kind") == "no_trade" and r.get("why") == "small_gap" and r.get("event"):
            e = evts.setdefault(r["event"], {"event": r["event"], "gap_bp": None, "t": ep(r.get("t"))})
            g = abs(_f(r.get("gap_bp"), 999))
            e["gap_bp"] = g if e["gap_bp"] is None else min(e["gap_bp"], g)
    entered = [races[e] for e in evts if e in races]
    t = pinphone.race_tally(entered)
    anyway = sum(1 for e in evts if (arm_res.get(e) or {}).get("positions", 0) > 0)
    return dict(since=ep(start.get("t")) if start else None, refused=len(evts), penny_entered=len(entered),
                won=t["won"], tie=t["tie"], lost=t["lost"], net=round(t["net"], 2), arm_entered_anyway=anyway,
                races=[dict(event=r["event"], close=r["close"], tie=r["tie"], won=r["won"], pnl=round(r["pnl"], 2))
                       for r in sorted(entered, key=lambda r: r["close"] or 0)])


def race_data(results, markets, now):
    races = pinphone.races_from(markets)
    r5, r30 = ep(RACE5_UTC), ep(RACE30_UTC)
    since5 = [r for r in races.values() if r["close"] is not None and r["close"] >= r5]
    since30 = [r for r in races.values() if r["close"] is not None and r["close"] >= r30]
    z3p = os.path.join(results, Z3_LOG)
    z3res = pinphone.arm_results(z3p) if os.path.exists(z3p) else {}
    z = pinphone.z3_progress(z3res, races) if z3res else {"races": 0, "losses": 0, "first50_losses": 0}
    word, why = z3_verdict(z["races"], z["losses"], z["first50_losses"])
    gp = os.path.join(results, GAP075_LOG)
    gap_res = pinphone.arm_results(gp) if os.path.exists(gp) else {}
    gap = photo_finishes(gp, races, gap_res) if os.path.exists(gp) else None
    return dict(race5=r5, race30=r30, since5=pinphone.race_tally(since5), since30=pinphone.race_tally(since30),
                z3=dict(bar=Z3_BAR, log=bool(z3res), races=z["races"], losses=z["losses"],
                        first50_losses=z["first50_losses"], verdict=word, why=why),
                gap075=gap)


def race_text(d):
    L = ["COIN RACE (penny bot, real money; Kalshi's books; a tie pays 50c a leg and counts as a loss)."]
    L.append("Since v-race5 (5 contracts a leg, %s): %s" % (et(d["race5"]), pinphone.race_tally_line(d["since5"])))
    L.append("Since v-race30 (%s): %s" % (et(d["race30"]), pinphone.race_tally_line(d["since30"])))
    z = d["z3"]
    L.append("z3 (earlier entry, paper) -- the bar: %s" % z["bar"])
    if z["log"]:
        L.append("So far: %d races entered, %s (first 50: %d).  VERDICT: %s -- %s." % (
            z["races"], _n(z["losses"], "loss"), z["first50_losses"], z["verdict"], z["why"]))
    else:
        L.append("No z3 log on file.  VERDICT: %s -- %s." % (z["verdict"], z["why"]))
    g = d["gap075"]
    L.append("gap075 (photo finishes, paper) -- %s It refuses a race whose top two coins are within 0.75 bp." % NO_BAR)
    if g is None:
        L.append("No gap075 log on file.")
    else:
        L.append("Since %s it refused %s as photo finishes. The penny bot entered %d of them for real: %d won, "
                 "%d tie, %d lost, %s.%s" % (
                     et(g["since"]) if g["since"] else "?", _n(g["refused"], "race"), g["penny_entered"], g["won"],
                     g["tie"], g["lost"], money(g["net"]),
                     (" The arm still entered %d of them on another leg." % g["arm_entered_anyway"]) if g["arm_entered_anyway"] else ""))
        if g["races"]:
            L.append("Those races: " + "; ".join("%s %s %s" % (et(r["close"], "%m/%d %I:%M %p"), "TIE" if r["tie"] else ("WON" if r["won"] else "LOST"),
                                                                 money(r["pnl"])) for r in g["races"]) + ".")
    return "\n".join(L)


# ===========================================================================
# A5 / A6. the shadow watchers, called, their own lines quoted
# ===========================================================================
def watch_lines(script, output=None, timeout=120):
    """The PASS/FAIL-so-far lines of `python research/<script> --report`.
    `output` injects the report text (the self-test); otherwise the script is
    run. Returns (lines, error)."""
    if output is None:
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, script), "--report"], capture_output=True,
                               text=True, timeout=timeout, cwd=os.path.dirname(HERE),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError) as e:
            return [], "%s --report could not run: %s" % (script, e)
        if r.returncode != 0:
            return [], "%s --report failed (exit %d): %s" % (script, r.returncode, (r.stderr or r.stdout or "").strip()[-300:])
        output = r.stdout or ""
    lines = [ln.rstrip() for ln in output.splitlines() if WATCH_LINE.search(ln.strip())]
    if not lines:
        return [], "%s --report printed no PASS/FAIL line" % script
    return lines, None


def watch_data(outputs=None):
    outputs = outputs or {}
    out = []
    for title, script in WATCHERS:
        lines, err = watch_lines(script, outputs.get(script))
        out.append(dict(title=title, script=script, lines=lines, error=err))
    return out


def watch_text(ws):
    L = []
    for w in ws:
        L.append("%s -- %s --report says:" % (w["title"], w["script"]))
        if w["error"]:
            L.append("  " + w["error"])
        L += ["  " + re.sub(r"\s{2,}", "  ", ln.strip()) for ln in w["lines"]]
    return "\n".join(L)


# ===========================================================================
# everything
# ===========================================================================
def gather(results=RESULTS, now=None, watch_outputs=None):
    now = now or time.time()
    since_e = ep(H2H_SINCE_UTC)
    markets = pinphone.markets_from(pinphone.raw_ledger(os.path.join(results, pinphone.pinday.LEDGER_NAME)))
    live = live_runs(results, since_e, keep=("signal", "order"))
    groups = arm_groups(results, live, since_e,
                        keep_for={BTCD_ARM: ("signal",)},
                        count_for={FRESH_ARM: {"fresh_level": '"gate": "fresh_level"'}})
    controls = collections.OrderedDict()
    for name in CONTROL_ARMS:
        g = group_named(groups, name)
        controls[name] = h2h(live, g["logs"]) if g else None
    return dict(now=now, since=since_e, live_logs=len(live),
                fresh=fresh_data(live, groups, markets, now),
                btcd=btcd_data(live, groups, markets, now),
                controls=controls,
                race=race_data(results, markets, now),
                watchers=watch_data(watch_outputs))


def render(d):
    blocks = ["BARS  %s. Every running test against the bar written before its data. Money is Kalshi's; "
              "arm-vs-live is each bot's own log on the same markets (%s since %s)." % (
                  et(d["now"], "%a %m/%d %I:%M %p"), _n(d["live_logs"], "live log"), et(d["since"], "%m/%d"))]
    blocks.append(fresh_text(d["fresh"]))
    blocks.append(btcd_text(d["btcd"]))
    blocks.append("CONTROL ARMS -- " + NO_BAR + "\n" + "\n\n".join(
        h2h_words(name, r, d["since"]) for name, r in d["controls"].items()))
    blocks.append(race_text(d["race"]))
    blocks.append(watch_text(d["watchers"]))
    return "\n\n".join(blocks)


def text(results=RESULTS, now=None):
    return render(gather(results, now))


def _peak_rss_mb():
    """Peak working set of this process in MB (Windows), or None."""
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wt.HANDLE
        fn = k32.K32GetProcessMemoryInfo
        fn.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        fn.restype = wt.BOOL
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if not fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return None
        return pmc.PeakWorkingSetSize / 1e6
    except Exception:                                               # noqa: BLE001
        return None


# ===========================================================================
def selftest():
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("bars selftest: FAILED -- " + msg)

    def w(path, recs, mode="w"):
        with open(path, mode, encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")

    def row(tk, res, yes_n=0, yes_c=0, no_n=0, no_c=0, fee=0.0, value=None, st="2026-09-24T18:00:20Z"):
        r = {"ticker": tk, "market_result": res, "yes_count_fp": "%.2f" % yes_n,
             "yes_total_cost_dollars": "%.6f" % yes_c, "no_count_fp": "%.2f" % no_n,
             "no_total_cost_dollars": "%.6f" % no_c, "fee_cost": "%.6f" % fee, "revenue": 0, "settled_time": st}
        if value is not None:
            r["value"] = value
        return r

    # the pure verdicts first: exact words for every branch of every bar
    ck(fresh_verdict(-28.80, 2, 0, 0.58) == ("TOO EARLY", "day 0.6 of 7; read today it would say PASS: deploy the rule: "
       "live's fresh fills are net $-28.80 with 2 losers (bar: <= +$25 and >= 2 losers, no arm-only loser)"),
       "fresh: inside the 7 days it is TOO EARLY, and says what it would read today")
    ck(fresh_verdict(-28.80, 2, 0, 7.0)[0] == "PASS", "fresh: at 7 days, net under +$25 with 2 losers = PASS (deploy)")
    ck(fresh_verdict(24.99, 2, 0, 7.5)[0] == "PASS", "fresh: +$24.99 with 2 losers is still PASS")
    ck(fresh_verdict(24.99, 2, 1, 7.5) == ("EXTEND", "neither bar is met: net $+24.99 with 2 losers and the arm has "
       "1 loser live did not; 7 more days"), "fresh: the same numbers with an arm-only loser are EXTEND, not PASS")
    ck(fresh_verdict(150.0, 1, 0, 7.5) == ("KILL", "live's fresh fills are net $+150.00 with 1 loser (bar: >= +$100 with <= 1 loser)"),
       "fresh: +$150 with 1 loser = KILL")
    ck(fresh_verdict(150.0, 2, 0, 7.5)[0] == "EXTEND" and fresh_verdict(50.0, 1, 0, 7.5)[0] == "EXTEND"
       and fresh_verdict(-5.0, 1, 0, 7.5)[0] == "EXTEND",
       "fresh: +$150 with 2 losers, +$50 with 1, -$5 with 1 are all EXTEND -- neither bar, never softened to PASS")
    ck(btcd_verdict(2, 0, 57, 0.6) == ("TOO EARLY", "day 0.6 of 7; needs >= 30 fired closes, 0 losses inside 30 s, "
       ">= 660 contracts; has 2 fired closes, 0 paper losses inside 30 s, 57 contracts"), "btcd: TOO EARLY inside the week")
    ck(btcd_verdict(30, 1, 700, 2.0) == ("KILL", "a paper loss inside 30 s; the bar allows 0 (30 fired closes, 1 paper loss "
       "inside 30 s, 700 contracts)"), "btcd: one paper loss inside 30 s is KILL at once, whatever the day")
    ck(btcd_verdict(35, 0, 700, 7.2)[0] == "PASS", "btcd: 35 closes, 0 losses, 700 contracts after 7 days = PASS")
    ck(btcd_verdict(10, 0, 100, 7.5) == ("KILL", "the week is up and the bar is not met: 10 fired closes, 0 paper losses "
       "inside 30 s, 100 contracts (needs >= 30 closes and >= 660 contracts)"), "btcd: under the counts after the week = KILL")
    ck(btcd_verdict(35, 0, 600, 7.5)[0] == "KILL", "btcd: 35 closes but 600 contracts fails the 660 = KILL")
    ck(z3_verdict(3, 1, 1) == ("TOO EARLY", "3 of 250 races, 1 loss so far (first 50: 1)"), "z3: TOO EARLY with the tie counted")
    ck(z3_verdict(250, 1, 1)[0] == "PASS" and z3_verdict(249, 1, 1)[0] == "TOO EARLY", "z3: PASS at 250 with 1 loss, not at 249")
    ck(z3_verdict(40, 2, 2) == ("KILL", "2 losses in the first 50 (bar kills at 2)"), "z3: 2 losses in the first 50 = KILL")
    ck(z3_verdict(120, 2, 1) == ("KILL", "2 losses in 120 races; the bar allows at most 1 in 250, so it can no longer pass"),
       "z3: a second loss after the first 50 still means it can never pass = KILL")

    # a planted world
    with tempfile.TemporaryDirectory() as td:
        X1, X2, X3 = "KXXRP15M-26SEP241315-15", "KXSOL15M-26SEP241330-30", "KXBTC15M-26SEP241345-45"
        X4, X5, X6 = "KXETH15M-26SEP241400-00", "KXDOGE15M-26SEP241415-15", "KXBNB15M-26SEP241430-30"
        B1, B2 = "KXBTCD-26SEP2413-T83699.99", "KXBTCD-26SEP2414-T83799.99"
        R0B, R1X, R2S, R3H = ("KXCRYPTOLEAD15M-26SEP230800-BTC", "KXCRYPTOLEAD15M-26SEP241145-XRP",
                              "KXCRYPTOLEAD15M-26SEP241200-SOL", "KXCRYPTOLEAD15M-26SEP241215-HYPE")
        led = {"settlements": {
            "x1": row(X1, "yes", no_n=20, no_c=19.40, st="2026-09-24T17:15:20Z"),      # lost -19.40 (fresh)
            "x2": row(X2, "no", no_n=20, no_c=19.40, st="2026-09-24T17:30:20Z"),       # won +0.60 (fresh)
            "x3": row(X3, "yes", yes_n=10, yes_c=9.70, st="2026-09-24T17:45:20Z"),     # won +0.30 (resting level)
            "x4": row(X4, "no", no_n=20, no_c=19.80, st="2026-09-24T18:00:20Z"),       # won +0.20 (fresh but 12 s left)
            "x5": row(X5, "yes", no_n=10, no_c=10.00, st="2026-09-24T18:15:20Z"),      # lost -10.00 (fresh)
            "x6": row(X6, "no", no_n=5, no_c=4.50, st="2026-09-24T18:30:20Z"),         # arm-only +0.50
            "b1": row(B1, "yes", yes_n=1, yes_c=0.97, value=100, st="2026-09-24T17:02:40Z"),   # hourly BTC +0.03
            "r0": row(R0B, "yes", yes_n=1, yes_c=0.97, value=100, st="2026-09-23T12:00:38Z"),
            "r1": row(R1X, "yes", yes_n=5, yes_c=4.85, value=100, st="2026-09-24T15:45:38Z"),  # +0.15
            "r2": row(R2S, "scalar", yes_n=5, yes_c=4.90, value=50, st="2026-09-24T16:00:38Z"),  # tie -2.40
        }}
        with open(os.path.join(td, "kalshi_ledger.json"), "w", encoding="utf-8") as fh:
            json.dump(led, fh)
        live_start = {"kind": "start", "t": "2026-09-24T12:00:00Z", "mode": "live", "edge_floor": 0.003,
                      "ladder_series": [], "fresh_min_age_ms": None, "fresh_tau_min": None, "code_sha": "abc"}

        def sig(tk, t, age, exact, tau, take=20.0):
            return {"kind": "signal", "t": t, "ticker": tk, "want": "no", "price": 0.97, "level_age_ms": age,
                    "level_age_exact": exact, "tau": tau, "take_n": take}

        def order(tk, t, filled, tau, asked=None, px=0.97):
            return {"kind": "order", "t": t, "ticker": tk, "filled": filled, "exec_price": px, "tau_at_send": tau,
                    "body": {"count": "%.2f" % (asked if asked is not None else filled)}}

        def settled(tk, t, pnl_c):
            return {"kind": "settled", "t": t, "ticker": tk, "pnl_c": pnl_c, "realised": 99.0}
        w(os.path.join(td, "pinrun-live-20260924T120000Z.jsonl"), [
            live_start,
            {"kind": "refused", "t": "2026-09-24T12:00:05Z", "gate": "no_offer", "ticker": X1},
            sig(B1, "2026-09-24T16:59:20Z", 18, True, 40), order(B1, "2026-09-24T16:59:20Z", 1.0, 40, px=0.97),
            settled(B1, "2026-09-24T17:02:40Z", 3.0),
            sig(X1, "2026-09-24T17:14:15Z", 120, True, 45), order(X1, "2026-09-24T17:14:15Z", 20.0, 45),
            sig(X1, "2026-09-24T17:14:48Z", 9000, True, 12), order(X1, "2026-09-24T17:14:48Z", 5.0, 12),  # top-up: not a first fill
            settled(X1, "2026-09-24T17:15:20Z", -1940.0),
            sig(X2, "2026-09-24T17:29:30Z", 300, True, 30), order(X2, "2026-09-24T17:29:30Z", 20.0, 30),
            settled(X2, "2026-09-24T17:30:20Z", 60.0),
            sig(X3, "2026-09-24T17:44:20Z", 15000, True, 40), order(X3, "2026-09-24T17:44:20Z", 10.0, 40),
            settled(X3, "2026-09-24T17:45:20Z", 30.0),
            sig(X4, "2026-09-24T17:59:48Z", 50, True, 12), order(X4, "2026-09-24T17:59:48Z", 20.0, 12),
            settled(X4, "2026-09-24T18:00:20Z", 20.0),
            sig(X5, "2026-09-24T18:14:15Z", 90, True, 45), order(X5, "2026-09-24T18:14:15Z", 10.0, 45),
            order(X6, "2026-09-24T18:29:30Z", 0.0, 30),                                       # filled nothing
            settled(X5, "2026-09-24T18:15:20Z", -1000.0),
            {"kind": "loop", "t": "2026-09-24T18:30:30Z"},
        ])
        # the fresh arm: live's start plus the flag; it refused X1 and X5, took the rest
        w(os.path.join(td, "pinrun-paper-20260924T080823Z.jsonl"), [
            dict(live_start, t="2026-09-24T08:08:23Z", mode="paper", fresh_min_age_ms=500, fresh_tau_min=20),
            {"kind": "refused", "t": "2026-09-24T17:14:15Z", "gate": "fresh_level", "ticker": X1, "level_age_ms": 120},
            settled(X2, "2026-09-24T17:30:20Z", 60.0), settled(X3, "2026-09-24T17:45:20Z", 30.0),
            settled(X4, "2026-09-24T18:00:20Z", 20.0),
            {"kind": "refused", "t": "2026-09-24T18:14:15Z", "gate": "fresh_level", "ticker": X5, "level_age_ms": 90},
            {"kind": "loop", "t": "2026-09-24T18:30:30Z"},
        ])
        # the edge-floor arm: took X2, X3 and X6 (live took nothing on X6)
        w(os.path.join(td, "pinrun-paper-20260924T051727Z.jsonl"), [
            dict(live_start, t="2026-09-24T05:17:27Z", mode="paper", edge_floor=0.02),
            settled(X2, "2026-09-24T17:30:20Z", 60.0), settled(X3, "2026-09-24T17:45:20Z", 30.0),
            settled(X6, "2026-09-24T18:30:20Z", 50.0),
            {"kind": "loop", "t": "2026-09-24T18:30:30Z"},
        ])
        # the hourly ladder arm: two rungs, one lost at 40 s (allowed), plus the 15M markets
        w(os.path.join(td, "pinrun-paper-20260924T075757Z.jsonl"), [
            dict(live_start, t="2026-09-24T07:57:57Z", mode="paper", ladder_series=["KXBTCD"]),
            sig(B1, "2026-09-24T16:59:20Z", 18, True, 40, take=27.0), settled(B1, "2026-09-24T17:02:40Z", 50.24),
            sig(B2, "2026-09-24T17:59:20Z", 18, True, 40, take=30.0), settled(B2, "2026-09-24T18:02:40Z", -2940.0),
            settled(X2, "2026-09-24T17:30:20Z", 60.0),
            {"kind": "loop", "t": "2026-09-24T18:30:30Z"},
        ])
        for nm, stamp in (("arm-fresh500", "20260924T080823Z"), ("arm-edge2c", "20260924T051727Z"),
                          ("arm-btcd", "20260924T075757Z")):
            with open(os.path.join(td, nm + ".out"), "w", encoding="utf-8") as fh:
                fh.write("SELF-TEST -- pinrun\n  ok   x\nlog C:\\kals-repo\\results\\pinrun-paper-%s.jsonl\n" % stamp)
        # race arms: z3 entered 3 races (one Kalshi tied); gap075 refused R2 and R3 as photo finishes
        w(os.path.join(td, Z3_LOG), [
            {"kind": "start", "t": "2026-09-22T19:00:00Z", "paper_live": True},
            {"kind": "live_settled", "paper": True, "t": "2026-09-23T12:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP230800",
             "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-24T15:46:15Z", "event": "KXCRYPTOLEAD15M-26SEP241145",
             "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-24T16:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP241200",
             "positions": 1, "won": 1, "pnl": 0.0186},
        ])
        w(os.path.join(td, GAP075_LOG), [
            {"kind": "start", "t": "2026-09-24T04:27:00Z", "paper_live": True, "min_gap_bp": 0.75},
            {"kind": "no_trade", "t": "2026-09-24T15:59:30Z", "event": "KXCRYPTOLEAD15M-26SEP241200", "coin": "SOL",
             "why": "small_gap", "gap_bp": 0.31},
            {"kind": "no_trade", "t": "2026-09-24T15:59:40Z", "event": "KXCRYPTOLEAD15M-26SEP241200", "coin": "XRP",
             "why": "small_gap", "gap_bp": -0.31},
            {"kind": "no_trade", "t": "2026-09-24T16:14:30Z", "event": "KXCRYPTOLEAD15M-26SEP241215", "coin": "HYPE",
             "why": "small_gap", "gap_bp": 0.5},
            {"kind": "no_trade", "t": "2026-09-24T16:14:31Z", "event": "KXCRYPTOLEAD15M-26SEP241215", "coin": "BTC",
             "why": "below_min_price", "gap_bp": 9.0},
            {"kind": "live_settled", "paper": True, "t": "2026-09-24T16:16:15Z", "event": "KXCRYPTOLEAD15M-26SEP241215",
             "positions": 1, "won": 1, "pnl": 0.0186},
        ])
        wx = ("wxwatch report: 2026-09-24T07:54:32Z .. 2026-09-25T01:54:39Z UTC (0.75 days, 18629 lines, 1 files)\n\n"
              "BAR 1 -- index freshness: p90 age under 7 min (420 s) per city\n"
              "  miami      reads  1069  typical age 5.6 min  -> PASS so far\n"
              "BAR 2 -- supply: >= 50 offered index-side contracts per day per city\n"
              "  miami      2620 book polls; contracts/day 2026-09-24: 3105  -> FAIL so far (needs 50 every day)\n"
              "Shadow days so far: 0.75 of the 3-5 the bar asks for.\n")
        qk = ("quakewatch report: 2026-09-24T07:54:32Z .. 2026-09-25T01:54:15Z UTC (0.75 days of the 14 the bar asks for, 4607 lines)\n"
              "BAR 2 -- safety: zero false locks\n  locks called: 36; broken by a USGS revision: 0  -> PASS so far\n"
              "  quake-days 1, with >= $10: 0  -> FAIL so far\n")
        now = ep("2026-09-24T22:00:00Z")
        d = gather(td, now, {"wxwatch.py": wx, "quakewatch.py": qk})
        s = render(d)
        print(s)
        f = d["fresh"]
        ck(f["first_fills"] == 5 and f["fresh"] == 3 and f["losers"] == 2 and f["won"] == 1 and f["unsettled"] == 0
           and abs(f["net"] + 28.80) < 1e-9,
           "fresh: 5 first fills (the top-up and the zero fill are not fills); 3 fresh (X4 at 12 s is not); "
           "2 lost, 1 won, net -28.80 -- all from Kalshi's rows")
        ck(f["arm_refused_fresh"] == 2 and f["h2h"]["same"] == 3 and f["h2h"]["live_only_n"] == 2
           and abs(f["h2h"]["live_only"] + 29.40) < 1e-9 and f["h2h"]["arm_extra_losers"] == [],
           "fresh arm vs live: 3 same markets, live-only X1 and X5 (-29.40), the arm refused 2 as fresh, no arm-only loser")
        ck(abs(f["days"] - 0.58) < 0.01 and f["start"] == ep("2026-09-24T08:08:23Z"),
           "the window starts at the arm's first record and today is day 0.58")
        ck("VERDICT: TOO EARLY -- day 0.6 of 7; read today it would say PASS: deploy the rule: live's fresh fills are "
           "net $-28.80 with 2 losers (bar: <= +$25 and >= 2 losers, no arm-only loser)." in s,
           "the fresh block prints the verdict exactly")
        ck("Fresh losers: XRP 09/24 01:14 PM ET $-19.40; DOGE 09/24 02:14 PM ET $-10.00." in s,
           "...and names the fresh losers with their money")
        d7 = gather(td, now + 7 * DAY, {"wxwatch.py": wx, "quakewatch.py": qk})
        ck(d7["fresh"]["verdict"] == "PASS" and "VERDICT: PASS -- deploy the rule" in render(d7),
           "seven days on, the same world reads PASS")
        b = d["btcd"]
        ck(b["orders"] == 1 and b["filled_orders"] == 1 and b["asked"] == 1.0 and b["got"] == 1.0
           and abs(b["avg_price"] - 0.97) < 1e-9 and b["ledger_markets"] == 1 and b["ledger_won"] == 1
           and abs(b["ledger_net"] - 0.03) < 1e-9,
           "hourly BTC live: 1 order asked 1 got 1 at 97c; Kalshi's row +0.03")
        ck(b["paper"] == dict(fired=2, contracts=57.0, settled=2, won=1, lost=1, lost_le30=0, net=-28.90),
           "hourly BTC paper: 2 fired closes, 57 contracts, 1 won 1 lost, the loss at 40 s is not one inside 30 s")
        ck("VERDICT (paper bar): TOO EARLY -- day 0.6 of 7; needs >= 30 fired closes, 0 losses inside 30 s, >= 660 "
           "contracts; has 2 fired closes, 0 paper losses inside 30 s, 57 contracts." in s,
           "the hourly block prints the paper verdict exactly")
        ck("Orders: 1 sent, 1 filled; asked 1, got 1 contracts, avg price 97.0c." in s
           and "Kalshi's books: 1 market settled, 1 won, 0 lost, $+0.03." in s, "...and the live fills, asked vs got")
        c = d["controls"]["arm-edge2c"]
        ck(c["same"] == 2 and abs(c["arm"] - 0.90) < 1e-9 and abs(c["live"] - 0.90) < 1e-9 and c["arm_only_n"] == 1
           and abs(c["arm_only"] - 0.50) < 1e-9 and c["live_only_n"] == 3 and abs(c["live_only"] + 29.20) < 1e-9
           and abs(c["edge"] - 29.70) < 1e-9,
           "arm-edge2c vs live: 2 same (+0.90 each), arm-only X6 (+0.50), live-only X1 X4 X5 (-29.20): edge +29.70")
        ck("arm-edge2c: no pre-registered bar; read only.\nSame markets 2: arm $+0.90, live $+0.90 -- head to head $+0.00 "
           "(even).\nArm-only markets 1 ($+0.50); live-only markets 3 ($-29.20).\nOver these closes the arm would have "
           "made $29.70 more than live" in s, "the control block reads in plain words")
        ck(d["controls"]["arm-brake3"] is None and "arm-brake3: no paper log found for it since" in s,
           "an arm with no log says so instead of showing zeros")
        r = d["race"]
        ck(r["since5"]["races"] == 2 and r["since5"]["won"] == 1 and r["since5"]["tie"] == 1
           and abs(r["since5"]["net"] + 2.25) < 1e-9 and r["since30"]["races"] == 3,
           "coin race: 2 races since v-race5 (1 won, 1 tie, -2.25), 3 since v-race30")
        ck(r["z3"]["races"] == 3 and r["z3"]["losses"] == 1 and r["z3"]["verdict"] == "TOO EARLY"
           and "So far: 3 races entered, 1 loss (first 50: 1).  VERDICT: TOO EARLY -- 3 of 250 races, 1 loss so far (first 50: 1)." in s,
           "z3: Kalshi's tie on a race it entered is its one loss")
        g = r["gap075"]
        ck(g["refused"] == 2 and g["penny_entered"] == 1 and g["tie"] == 1 and g["won"] == 0 and g["lost"] == 0
           and abs(g["net"] + 2.40) < 1e-9 and g["arm_entered_anyway"] == 1,
           "gap075: 2 races refused as photo finishes; the penny bot entered 1 of them and it TIED (-2.40); "
           "the arm still entered the other on a wide leg")
        ck("it refused 2 races as photo finishes. The penny bot entered 1 of them for real: 0 won, 1 tie, 0 lost, $-2.40. "
           "The arm still entered 1 of them on another leg." in s, "...in words")
        ws = d["watchers"]
        _pre = ["wxwatch report:", "BAR 1", "miami", "BAR 2", "miami", "Shadow days so far"]
        ck(len(ws[0]["lines"]) == 6 and all(ln.strip().startswith(p_) for ln, p_ in zip(ws[0]["lines"], _pre))
           and ws[0]["error"] is None,
           "the weather report's header, BAR titles, PASS/FAIL lines and day count are quoted, nothing else")
        ck(len(ws[1]["lines"]) == 4 and "-> FAIL so far" in ws[1]["lines"][3] and "-> PASS so far" in ws[1]["lines"][2],
           "the quake report likewise")
        ck(watch_lines("wxwatch.py", "nothing here\n") == ([], "wxwatch.py --report printed no PASS/FAIL line"),
           "NULL: a report with no PASS/FAIL line is reported as such, never as a pass")
        js = json.dumps(d, default=str)
        ck('"verdict": "TOO EARLY"' in js and '"fresh"' in js and '"controls"' in js, "--json carries every verdict")
        ck(all(len(c) <= pinphone.MAX_LEN for c in pinphone.split_text(s)), "the text splits under Telegram's limit")
        # an empty world: nothing crashes, everything says so
        with tempfile.TemporaryDirectory() as td2:
            s0 = render(gather(td2, now, {"wxwatch.py": "", "quakewatch.py": ""}))
            ck("No paper log for arm-fresh500 was found" in s0 and "Orders: none on the hourly BTC markets yet." in s0
               and "No z3 log on file." in s0 and "No gap075 log on file." in s0
               and "printed no PASS/FAIL line" in s0, "NULL: an empty results directory reads as absence, not as numbers")
    print("bars selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    results = RESULTS
    now = None
    if "--results" in sys.argv:
        results = sys.argv[sys.argv.index("--results") + 1]
    if "--now" in sys.argv:
        now = ep(sys.argv[sys.argv.index("--now") + 1])
    d = gather(results, now)
    if "--json" in sys.argv:
        print(json.dumps(d, indent=1, default=str))
    else:
        print(render(d))
    if "--mem" in sys.argv:
        m = _peak_rss_mb()
        print("\n(peak working set %s)" % ("%.0f MB" % m if m is not None else "unknown"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
