"""The jump band (research/cleanroom/jumpband_live.py --live --subaccount 3, ledger LS25): live stage 1 since 2026-10-30,
subaccount 3's POOL 2. Its paper arm runs the same script WITHOUT --live (log jumpband-paper.jsonl) and is never this
bot; --live --dry-run sends nothing and is not it either. Every fact copied verbatim from botstats.py / pinphone.py /
tgcharts.py at 8a9c5e1 (v-tg-rebuild step 1, 2026-10-30)."""
import re

from bots.spec import Bot, Feature, Logs, Pot, Records, Speed, VersionRule, live_flag
from botdata.fmt import cents as _c, fmt_g as _fmt_g, num as _num, plural as _n, usd

# the jump band's coins (jumpband_live.SLOW): in subaccount 3 a 15-minute coin market is the jump band's, a KXHIGH the weather's
JB_SERIES = frozenset(["KXBNB15M", "KXHYPE15M", "KXZEC15M", "KXNEAR15M"])


def _claims(series, ticker):
    """botstats.owner, subaccount 3 (2026-10-30): the number 3 is two pots' history -- the weather dip-seller's KXHIGH
    brackets (pool 0, 10-04..10-10) and the jump band's 15-minute coins (pool 2, from 10-30)."""
    import pinday
    return series in JB_SERIES or series in pinday.CRYPTO


def settings_jumpband(start):
    """The jump band's settings, all from its own start record (jumpband_live.py writes max_contracts, max_cost, k, lo, hi,
    tau, series, stop_line, day_stop): 'up to 5 contracts a buy, at most $20.00 an order; ...'.
    (botstats.settings_jumpband, verbatim)"""
    st = start or {}
    s = {k: st.get(k) for k in ("max_contracts", "max_cost", "k", "lo", "hi", "tau", "series", "stop_line", "day_stop",
                                "subaccount", "rule_override") if k in st}
    bits = []
    if s.get("max_contracts") is not None:
        bits.append("up to %s contracts a buy%s" % (_fmt_g(s["max_contracts"]), (", at most %s an order"
                                                    % usd(float(s["max_cost"])).lstrip("+")) if s.get("max_cost") else ""))
    if s.get("lo") is not None and s.get("hi") is not None:
        tau = s.get("tau") or []
        bits.append("buys the favourite at %s-%s when the price moves %s+ standard deviations in its last minute%s"
                    % (_c(s["lo"]), _c(s["hi"]), _fmt_g(s.get("k")),
                       (", %s-%s s before the close" % (_fmt_g(tau[0]), _fmt_g(tau[-1]))) if len(tau) == 2 else ""))
    if s.get("series"):
        bits.append("coins %s" % " ".join(re.sub(r"^KX|15M$", "", x) for x in s["series"]))
    if s.get("day_stop") is not None:
        bits.append("stops the day at %s settled" % usd(float(s["day_stop"])))
    if s.get("stop_line") is not None:
        bits.append("stands down for good at %s since it went live" % usd(float(s["stop_line"])))
    return s, "; ".join(bits)


def settings(si):
    return settings_jumpband(si.start)


def jb_why(r):
    """The jump band's day_stop / stop_line record in words ('settled -$15.20 today, its day stop -$15'), else ''.
    (botstats._jb_why, verbatim; botstats asks it of EVERY bot's halt records, so step 3 must keep that)"""
    k = r.get("kind")
    if k == "day_stop" and _num(r.get("day_money")) is not None:
        return "settled %s on %s, its day stop %s" % (usd(_num(r["day_money"])), r.get("day") or "the day",
                                                     usd(_num(r.get("day_stop")) or 0.0))
    if k == "stop_line" and _num(r.get("line_money")) is not None:
        return "settled %s since it went live, its stop line %s: stood down for good" % (
            usd(_num(r["line_money"])), usd(_num(r.get("stop_line")) or 0.0))
    return ""


def activity(k, r, out, why, st):
    """botstats.activity's jumpband branch (verbatim; `triggers` lives in st)."""
    import pinledger
    # jumpband_live.py (2026-10-30): 'trigger' = every qualifying jump it judged, 'order' = every IOC buy sent,
    # 'fill' = what one got ('qty' contracts), and the money refusals the order path logs by their own kind
    if k == "trigger":
        st["triggers"] += 1
    elif k == "order":
        out["sent"] += 1
        if pinledger.money(r, "filled") <= 0:
            out["not_filled"] += 1
    elif k == "fill":
        out["filled"] += 1
        out["contracts_filled"] += pinledger.money(r, "qty")
    elif k in ("no_cash", "max_cost", "refused", "order_skip", "body_refused"):
        out["refused"] += 1
        g = str(r.get("why") or k)
        why[g] = why.get(g, 0) + 1


def activity_note(out, st):
    triggers = st["triggers"]
    out["triggers"] = triggers
    out["note"] = ("%s judged today; it buys only one whose favourite asks 70-90c with 10-60 s left, once a market"
                   % _n(triggers, "price jump"))


BOT = Bot(
    name="jumpband", label="Jump band", short="Jump band", word="jump band",
    what="buys the 70-90c favourite on BNB/HYPE/ZEC/NEAR when the price jumps 2+ standard deviations in "
         "the last minute, 5 contracts, holds to the end",
    help=("/jb (or /jumpband) — the jump band: buys the 70-90c favourite on BNB/HYPE/ZEC/NEAR after a 2+ sd price "
          "jump, 5 contracts (subaccount 3), the same detail as /pin",),
    command="/jb", commands=("/jb", "/jumpband"),
    # v-tg-active (2026-10-30): subaccount 3 trades in POOL 2 now -- the jump band's $50 went into its pool 2 at ~05:35Z
    # (the weather dip-seller's pool 0 has held $0 since 10-15); its pool 2 and its coins are the jump band's own pot
    pots=(Pot("3", 2, claims=_claims, priority=10, pool_only=True,
              what="jump band: BNB/HYPE/ZEC/NEAR after a price jump (live stage 1, 2026-10-30)", short="jump band"),),
    script="jumpband_live.py", is_live=live_flag("--live", deny=("--dry-run",)), stop_file="jumpband-live.stop",
    logs=Logs(path="jumpband-live.jsonl"),
    records=Records(fills=("fill",), fill_qty="qty", halts=("halt", "day_stop", "stop_line"),
                    # 2026-10-30: the jump band's day stop names its ET day and lifts by itself the next day (no restart)
                    halt_lifts_next_day=("day_stop",),
                    # the jump band's (jumpband_live.plan_live, 2026-10-30)
                    refusal_words=((r"^max_cost$", "order over its $ cap"),
                                   (r"^under_one_contract$", "under one contract offered"),
                                   (r"^no_pool$", "market's cash pool unknown"))),
    settings=settings,
    # 2026-10-30: the jump band's entries name its script (jumpband_live) or start v-jb; never the pin bot's
    version=VersionRule(part=lambda n: "jumpband" in n or n.startswith("v-jb"),
                        text=lambda vname, low: "jumpband" in low or vname.startswith("v-jb"), override="v-jb"),
    colour="#c0399a",          # magenta (2026-10-30), 317 deg: off the red of a loss
    order=7,
    keepalive=None,            # started by hand on the server (results/jb_deploy.ps1); not in boot_all
    page_footer="Every bot: /bots · its pot (subaccount 3, crypto pool): /funds.",
    activity=activity, activity_note=activity_note, halt_why=jb_why,
    funds_size=True,
    # the jump band (2026-10-30) started on the server, so it has no home window to set its speed against
    speed=Speed(rank=1, skipped="skipped: it started on the server (10-30), so there is no home window to compare"),
    features=(
        Feature("jumpband_live.py", "--live", None, "Jump band (LIVE, subaccount 3)",
                "Buys the 70-90c favourite on BNB, HYPE, ZEC and NEAR when the price jumps 2+ standard deviations in "
                "the last minute, 10 to 60 seconds before the close, 5 contracts, and holds it to the end (live stage 1 "
                "since 10-30, $50).", pos=6, hides=True),
        Feature("jumpband_live.py", None, "--live", "Jump band paper arm",
                "The jump band's rule on paper at 100 contracts, beside the live one; no orders.", pos=7),
    ),
)
