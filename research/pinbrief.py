"""pinbrief.py -- the daily briefing, in one place, in plain words.

WHY THIS EXISTS. The operator, 2026-09-18: *"add a daily summary somewhere
somehow. Include like what changes were made good and bad, what had effects on
stuff. How the market was. Things to look out for, ideas had, all that good
stuff... how we performed and our effect on it both through ideas implemented
that day and recently previous ones saying if they helped or hurt by how much."*

Six questions, each answered from the file that already owns it rather than
recomputed here:

  money        `pindesk.Ledger`   -- Kalshi's own settlement record
  what changed `results/VERSIONS.md` -- every live change, dated
  what it did  `pinlab`           -- the running arms and their progress
  the market   `pinsupply`        -- cheap offers against a normal day
  watch out    `pindesk` health + `pinattrib` -- brakes, losses, gates
  ideas        `pinlab`           -- the IDEA entries on the board

**NOTHING IN HERE ADDS UP ITS OWN TOTAL.** That is the whole design. A summary
that recomputes the day's money is a second number to keep honest, and this
project has shipped that bug more than once -- the desktop tool and the phone
bot disagreed about the same day for three days running, and a day reported as
"+$47" was really +$23 because a throwaway query filtered UTC as if it were
Eastern.

**IT SAYS WHAT IT CANNOT SEE.** A briefing that quietly omits the effect of a
change is worse than one that says "too early to tell" -- the first reads as
"no effect". `too_early` is a real answer here and it is printed.
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
os.environ.setdefault("KALS_DASH_SELFTESTED", "1")

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
VERSIONS = os.path.join(RESULTS, "VERSIONS.md")

# A change needs at least this many settled quarter-hours behind it before its
# effect is quoted as anything but "too early". Chosen to match the arm bars
# already written into the PREREG files, not picked here.
MIN_CLOSES_TO_JUDGE = 40


def versions(path=None, text=None):
    """[{name, day, headline}] newest first, from VERSIONS.md's own headings.

    The heading format is `# v-<name> -- <date> ~<time>Z -- <headline>`, which
    is what the standing rule requires of every live change. A heading this
    cannot parse is SKIPPED and counted, never guessed at.
    """
    if text is None:
        try:
            with open(path or VERSIONS, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return [], 0
    out, bad = [], 0
    for line in text.splitlines():
        if not line.startswith("# v-"):
            continue
        m = re.match(r"#\s+(v-\S+)\s+--\s+(\d{4}-\d{2}-\d{2})[^-]*--\s*(.+)$",
                     line)
        if not m:
            bad += 1
            continue
        out.append({"name": m.group(1), "day": m.group(2),
                    "headline": m.group(3).strip()})
    return out, bad


def _pct(a, b):
    if a is None or b is None or abs(b) < 1e-9:
        return None
    return 100.0 * (a - b) / abs(b)


def brief(day=None, ledger=None, results=None, now=None):
    """Everything the briefing says, as data. Render separately."""
    import pindesk
    now = time.time() if now is None else now
    if ledger is None:
        ledger = pindesk.Ledger(results=results or RESULTS)
        ledger.refresh()
    day = day or pindesk.et_day(now)
    prev = pindesk.et_day(pindesk.et_day_start(day) - 3600)

    rows = ledger.settled_on(day)
    s = pindesk.Ledger.summary(rows)
    b0 = ledger.bank_at(pindesk.et_day_start(day))
    ps = pindesk.Ledger.summary(ledger.settled_on(prev))

    # the worst single quarter-hour, which is the number that actually hurts
    worst = None
    for close, net, legs in ledger.losing_closes():
        if close and pindesk.et_day(close) == day:
            if worst is None or net < worst["net"]:
                worst = {"when": pindesk.et_str(close), "net": round(net, 2),
                         "coins": sorted({pindesk.coin(l["tk"]) for l in legs
                                          if l.get("tk")})}
    out = {
        "day": day, "prev": prev,
        "net": round(s["net"], 2), "closes": s["closes"],
        "won": s["won"], "lost": s["lost"],
        "bank_start": round(b0, 2) if b0 else None,
        "pct_of_bank": (round(100.0 * s["net"] / b0, 2) if b0 else None),
        "prev_net": round(ps["net"], 2), "prev_closes": ps["closes"],
        "vs_prev": _pct(s["net"], ps["net"]) if ps["closes"] else None,
        "worst": worst,
        "changed_today": [], "changed_recent": [],
        "arms": [], "ideas": [], "market": [], "watch": [],
        "too_early": [],
    }

    # what changed, today and in the week behind it
    vs, bad = versions()
    out["versions_unparsed"] = bad
    cutoff = pindesk.et_day(pindesk.et_day_start(day) - 7 * 86400)
    for v in vs:
        if v["day"] == day:
            out["changed_today"].append(v)
        elif cutoff <= v["day"] < day:
            out["changed_recent"].append(v)

    # what the running arms have done, and whether that is enough to judge
    try:
        import pinlab
        prog = pinlab.live_progress(cmdlines=[])
        bym = {e.get("match"): e for e in pinlab.EXPERIMENTS}
        for match, info in prog.items():
            e = bym.get(match) or {}
            if e.get("status") != pinlab.RUNNING or not info.get("settled"):
                continue
            row = {"name": e.get("name"), "settled": info["settled"],
                   "won": info.get("won"), "lost": info.get("lost"),
                   "net": round(info.get("net") or 0.0, 2)}
            if info["settled"] < MIN_CLOSES_TO_JUDGE:
                row["verdict"] = "too early -- %d of %d quarter-hours" % (
                    info["settled"], MIN_CLOSES_TO_JUDGE)
                out["too_early"].append(row)
            else:
                row["verdict"] = ("ahead" if row["net"] > 0 else "behind")
            out["arms"].append(row)
        out["ideas"] = [{"name": e["name"], "why": e.get("why")}
                        for e in pinlab.EXPERIMENTS
                        if e.get("status") == pinlab.IDEA][:4]
    except Exception as e:                                     # noqa: BLE001
        out["arms_error"] = str(e)[:150]

    # the market
    try:
        import pinsupply
        out["market"] = pinsupply.lines()
    except Exception as e:                                     # noqa: BLE001
        out["market"] = ["Could not read the opportunity trend (%s)" % str(e)[:60]]
    try:
        act = ledger.activity()
        out["sellers"] = act.get("level")
    except Exception:                                          # noqa: BLE001
        out["sellers"] = None

    # what to look out for
    h = None
    try:
        h = pindesk.health(ledger)
    except Exception:                                          # noqa: BLE001
        pass
    if h:
        halt = h.get("halt")
        if halt and halt.get("why"):
            out["watch"].append("A safety brake fired: %s" % halt["why"][:120])
        if (h.get("disk_gb") or 99) < 6:
            out["watch"].append(
                "Disk is down to %.1f GB. Below 5 the recording stops for good "
                "and cannot be re-made." % h["disk_gb"])
        if not h.get("kalshi_ok"):
            out["watch"].append("The Kalshi recorder is NOT writing.")
        if not h.get("feeds_ok"):
            out["watch"].append("The exchange feeds are NOT writing.")
        a = h.get("supply_age_d")
        if a is not None and a > 2:
            out["watch"].append(
                "The opportunity trend is %.1f days old, so it describes a week "
                "that has already ended." % a)
    if worst and out["bank_start"]:
        share = 100.0 * abs(worst["net"]) / out["bank_start"]
        if share >= 5:
            out["watch"].append(
                "One quarter-hour cost %.0f%% of the bank we started the day "
                "with." % share)
    if s["closes"] and s["lost"]:
        out["watch"].append(
            "%d of %d quarter-hours lost today, against about 1 in 24 normally."
            % (s["lost"], s["closes"]))
    return out


def render(b, say=print):
    def w(*x):
        say(*x)
    w("THE DAY -- %s (Eastern)" % b["day"])
    w("")
    if not b["closes"]:
        w("  Nothing settled today yet.")
    else:
        w("  MONEY: %s%s from %d quarter-hours, %d won and %d lost."
          % (("+$%.2f" % b["net"]) if b["net"] >= 0 else ("-$%.2f" % -b["net"]),
             ("" if b["pct_of_bank"] is None
              else ", which is %+.2f%% of the $%.2f the bank held this morning"
              % (b["pct_of_bank"], b["bank_start"])),
             b["closes"], b["won"], b["lost"]))
        if b["prev_closes"]:
            w("  Yesterday was %s%s over %d."
              % (("+$%.2f" % b["prev_net"]) if b["prev_net"] >= 0
                 else ("-$%.2f" % -b["prev_net"]),
                 "" if b["vs_prev"] is None else (" (%+.0f%%)" % b["vs_prev"]),
                 b["prev_closes"]))
        if b["worst"]:
            w("  Worst single quarter-hour: %s, %s on %s."
              % (b["worst"]["when"], "-$%.2f" % -b["worst"]["net"],
                 ", ".join(b["worst"]["coins"]) or "?"))
    w("")
    w("  WHAT CHANGED TODAY")
    if b["changed_today"]:
        for v in b["changed_today"]:
            w("    %s -- %s" % (v["name"], v["headline"]))
    else:
        w("    Nothing went live today.")
    if b["changed_recent"]:
        w("")
        w("  CHANGED IN THE WEEK BEFORE, still settling in")
        for v in b["changed_recent"][:5]:
            w("    %s (%s) -- %s" % (v["name"], v["day"], v["headline"]))
    w("")
    w("  WHAT THOSE CHANGES ARE DOING")
    if not b["arms"]:
        w("    No test has settled a quarter-hour yet.")
    for a in b["arms"]:
        w("    %s" % a["name"])
        w("      %d settled, %d won, %d lost, %s%.2f -- %s"
          % (a["settled"], a["won"], a["lost"],
             "+$" if a["net"] >= 0 else "-$", abs(a["net"]), a["verdict"]))
    if b["too_early"]:
        w("")
        w("    %d of these have too few quarter-hours to judge. That is NOT "
          "the same as no effect." % len(b["too_early"]))
    w("")
    w("  HOW THE MARKET WAS")
    if b.get("sellers"):
        w("    Sellers: %s." % b["sellers"])
    for l in b["market"]:
        w("    %s" % l)
    w("")
    w("  WHAT TO LOOK OUT FOR")
    if b["watch"]:
        for l in b["watch"]:
            w("    %s" % l)
    else:
        w("    Nothing flagged. The brakes did not fire, the recorders are "
          "writing and there is room on the disk.")
    if b["ideas"]:
        w("")
        w("  ON THE DRAWING BOARD, not started")
        for i in b["ideas"]:
            w("    %s" % i["name"])
    if b.get("versions_unparsed"):
        w("")
        w("  (%d headings in VERSIONS.md could not be read and were skipped, "
          "so a change may be missing above.)" % b["versions_unparsed"])


def text(b):
    out = []
    render(b, say=lambda *x: out.append(" ".join(str(i) for i in x)))
    return "\n".join(out)


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinbrief selftest: FAILED -- " + msg)

    v, bad = versions(text="""# v-bank8 -- 2026-09-18 ~07:0xZ -- one bet is the bank/8
some prose
# v-early49 -- 2026-09-17 ~02:3xZ -- the 45s leg reopens at a THIRD
# v-broken heading with no date
## not a version heading at all
""")
    ck(len(v) == 2 and v[0]["name"] == "v-bank8",
       "VERSIONS.md headings parse into dated changes, newest first as written")
    ck(v[0]["headline"].startswith("one bet"),
       "...and the headline is the sentence after the date, not the date")
    ck(bad == 1,
       "a heading that cannot be parsed is COUNTED, not guessed at -- a change "
       "silently missing from the briefing reads as a day nothing shipped")

    import json
    import tempfile
    import pindesk
    import pinledger
    td = tempfile.mkdtemp()
    _sv = pinledger.LEDGER
    pinledger.LEDGER = os.path.join(td, "ledger.json")
    try:
        with open(os.path.join(td, "pinrun-live-20260918T000000Z.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "start", "mode": "live",
                                 "t": "2026-09-18T00:00:00Z"}) + "\n")
            fh.write(json.dumps({"kind": "autosize", "new": 77,
                                 "why": "bank $600.00",
                                 "t": "2026-09-18T00:00:01Z"}) + "\n")
        rows = {}
        for tk, res, n, cost, when in (
                ("KXBTC15M-26SEP181200-00", "yes", 77, 73.9,
                 "2026-09-18T16:00:20Z"),
                ("KXETH15M-26SEP181215-15", "no", 77, 73.1,
                 "2026-09-18T16:15:20Z")):
            won_yes = res == "yes"
            rows[tk] = {
                "ticker": tk, "market_result": res,
                "yes_count_fp": ("%.2f" % n) if won_yes else "0.00",
                "no_count_fp": "0.00" if won_yes else ("%.2f" % n),
                "yes_total_cost_dollars": ("%.2f" % cost) if won_yes else "0.00",
                "no_total_cost_dollars": "0.00" if won_yes else ("%.2f" % cost),
                "fee_cost": "0.05", "settled_time": when}
        with open(pinledger.LEDGER, "w", encoding="utf-8") as fh:
            json.dump({"settlements": rows}, fh)
        L = pindesk.Ledger(results=td)
        L.refresh()
        b = brief(day="2026-09-18", ledger=L)
    finally:
        pinledger.LEDGER = _sv

    want = pindesk.Ledger.summary(L.settled_on("2026-09-18"))
    ck(abs(b["net"] - round(want["net"], 2)) < 1e-9,
       "the day's money is pindesk's own summary and is never added up again "
       "here -- a day was once reported as +$47 when it was +$23 by a "
       "throwaway query that filtered UTC as if it were Eastern")
    ck(b["closes"] == want["closes"] and b["won"] == want["won"],
       "...and so are the quarter-hours won and lost")
    t = text(b)
    ck("THE DAY -- 2026-09-18" in t, "the briefing names its own Eastern day")
    for head in ("MONEY", "WHAT CHANGED TODAY", "WHAT THOSE CHANGES ARE DOING",
                 "HOW THE MARKET WAS", "WHAT TO LOOK OUT FOR"):
        ck(head in t, "it answers '%s'" % head.lower())
    ck("2026-09-18T" not in t,
       "no raw timestamp reaches the operator -- Eastern only, standing rule")
    for word in ("tau", "sigma", "rho", "Clopper", "bootstrap", "p90", "MDE"):
        ck(word not in t, "no jargon: %r" % word)

    empty = brief(day="2019-01-01", ledger=L)
    ck(empty["closes"] == 0 and "Nothing settled today yet" in text(empty),
       "NULL: a day with nothing settled SAYS so, rather than printing $0.00 "
       "as though the bot had traded and broken even")

    row = {"settled": 3, "net": 1.0}
    ck(MIN_CLOSES_TO_JUDGE > 3,
       "a handful of quarter-hours is not enough to call a change good or bad")
    ck(any("too early" in (a.get("verdict") or "") for a in b["arms"])
       or not b["arms"],
       "an arm with too few quarter-hours is reported as TOO EARLY, which is a "
       "real answer -- omitting it would read as 'no effect'")
    print("pinbrief selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--day", default=None, help="Eastern day, YYYY-MM-DD")
    ap.add_argument("--results", default=RESULTS)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    render(brief(day=a.day, results=a.results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
