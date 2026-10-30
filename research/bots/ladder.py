"""The penny ladder: resting 98c bids on the decided side, subaccount 1. Every fact copied verbatim from botstats.py /
pinphone.py / tgcharts.py at 8a9c5e1 (v-tg-rebuild step 1, 2026-10-30)."""
import re

from bots.spec import Bot, Feature, Logs, Pot, Records, Speed, VersionRule, live_flag
from botdata.fmt import usd

LADDER_GOAL_PCT = 1.0       # operator 10-22: the ladder's target is 1% of its bank a day -- shown next to its %


def settings_ladder(start, cl):
    """botstats.settings_clean, its ladder (else) branch (verbatim; the forecaster's is in bots/forecaster.py)."""
    s = {}
    r = (start or {}).get("rails") or {}
    s["rails"] = r
    bits = []
    lv = r.get("live_levels")
    bits.append("%s-contract resting bids%s" % (r.get("size", 1), " on the top rung" if lv == [0] else ""))
    if r.get("max_live_per_close") is not None:
        bits.append("up to %s coins a quarter-hour" % r["max_live_per_close"])
    if r.get("max_contracts") is not None:
        bits.append("at most %s contracts / %s in play" % (r["max_contracts"], usd(float(r.get("max_commit") or 0)).lstrip("+")))
    if r.get("day_stop") is not None:
        bits.append("stops the day at %s" % usd(float(r["day_stop"])))
    return s, "; ".join(bits)


def settings(si):
    return settings_ladder(si.start, si.cmdline)


def activity(k, r, out, why, st):
    """botstats.activity's ladder branch (verbatim)."""
    import pinledger
    if k == "placed":
        out["sent"] += 1
    elif k == "cancelled":
        out["cancelled"] += 1
    elif k == "live_fill":
        out["filled"] += 1
        out["contracts_filled"] += pinledger.money(r, "delta")
    elif k == "rail_refused":
        out["refused"] += 1
        g = str(r.get("why") or k)
        why[g] = why.get(g, 0) + 1


def activity_note(out, st):
    out["note"] = "resting bids: most are cancelled unfilled at the close, by design"


# v-tg-rebuild step 5 (2026-10-30): /funds' bet-size reader, moved verbatim from pinphone.funds_sizes (where it was a
# closure over its `when` and `results`; spec.SizeIn hands it those and the phone's readers).
def size_words(si):
    """/funds: the ladder's bid size now -- its newest rescale or start record."""
    import os
    r = si.last_record(os.path.join(si.results, "ladder-live-orders.jsonl"), ("rescale", "start"))
    size = si.num(((r or {}).get("rails") or {}).get("size"))
    if size is None:
        size = si.num((r or {}).get("new"))
    if size is None:
        return None
    pot = si.num(r.get("pot") if r.get("pot") is not None else r.get("sub_balance"))
    return "ladder %g-contract bids (sized %s%s)" % (size, si.when(r), (" on a %s pot" % si.usd2(pot)) if pot else "")


BOT = Bot(
    name="ladder", label="Ladder", short="Ladder", word="ladder",
    what="resting 98c bids on the decided side of NEAR ZEC DOGE HYPE XRP (one rung since 10-23), sized so every bid "
         "fits its bank (goal 1%/day)",
    help=("/ladder — the penny ladder (subaccount 1), the same detail as /pin",),
    command="/ladder", commands=("/ladder",),
    pots=(Pot("1", 2, what="penny ladder", short="ladder"),),
    script="ladder_live.py", is_live=live_flag("--live"), stop_file="ladder-live.stop",
    logs=Logs(path="ladder-live-orders.jsonl"),
    records=Records(fills=("live_fill",), fill_qty="delta", halts=("day_stop",)),
    settings=settings,
    # An entry naming two clean-room bots (v-keepalive-cleanroom) is infrastructure, not either
    # bot's version; `v-ladder7` is pin's hourly ladder table, not the penny ladder.
    version=VersionRule(part=lambda n: bool(re.match(r"v-ladder-[a-z]", n)),
                        text=lambda vname, low: "ladder_live" in low or "penny ladder" in low),
    colour="#1aa3a3",          # teal
    order=4,
    keepalive="boot_all.ps1 (every 10 min) restarts it unless the stop file is there",
    goal_pct=LADDER_GOAL_PCT,
    page_footer="Every bot: /bots.",
    activity=activity, activity_note=activity_note,
    funds_size=size_words,
    speed=Speed(rank=2, skipped="skipped: its bids rest on the book until a seller hits them, so how fast it sends "
                                "does not decide what it gets, and its log keeps no send-to-answer time"),
    features=(
        Feature("ladder_live.py", None, None, "Penny ladder (LIVE, subaccount 1)",
                "Rests bids a few cents below fair on the already-decided side of 15-minute coin closes and collects the "
                "last cents when they fill.", pos=3, hides=True),
        Feature("locked_average_ladder_re_paper.py", None, None, "Ladder paper shadow",
                "The ladder's rule on paper across every coin, to compare with the live one; no orders.", pos=10),
    ),
)
