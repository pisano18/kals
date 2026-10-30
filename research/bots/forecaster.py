"""The forecaster: buys the 15-minute coin side its own forecast calls decided, subaccount 2. Every fact copied verbatim
from botstats.py / pinphone.py / tgcharts.py at 8a9c5e1 (v-tg-rebuild step 1, 2026-10-30)."""
from bots.spec import Bot, Feature, Logs, Pot, Records, Speed, VersionRule, live_flag, opt
from botdata.fmt import cents as _c, usd


def settings_forecaster(start, cl):
    """botstats.settings_clean, its forecaster branch (verbatim; the ladder's branch is in bots/ladder.py)."""
    s = {}
    r = (start or {}).get("rails") or {}
    s["rails"] = r
    s["variant"] = (start or {}).get("variant") or opt(cl, "--variant")
    s["variant_params"] = (start or {}).get("variant_params")
    if cl and opt(cl, "--variant") and s["variant"] != opt(cl, "--variant"):
        s["variant_mismatch"] = "log says %s, command line says %s" % (s["variant"], opt(cl, "--variant"))
    bits = ["variant %s" % (s["variant"] or "none")]
    if r.get("scale") is not None:
        bits.append("%g%% of paper size" % (100 * float(r["scale"])))
    if r.get("per_side") is not None:
        bits.append("up to %s a side, %s a quarter-hour" % (r["per_side"], r.get("per_close", "?")))
    if r.get("max_commit") is not None:
        bits.append("at most %s in play" % usd(float(r["max_commit"])).lstrip("+"))
    if r.get("px"):
        bits.append("buys %s to %s" % (_c(r["px"][0]), _c(r["px"][1])))
    if r.get("day_stop") is not None:
        bits.append("stops the day at %s, the run at %s" % (usd(float(r["day_stop"])), usd(float(r.get("run_stop") or 0))))
    return s, "; ".join(bits)


def settings(si):
    return settings_forecaster(si.start, si.cmdline)


def activity(k, r, out, why, st):
    """botstats.activity's forecaster branch (verbatim)."""
    import pinledger
    if k == "placed":
        out["sent"] += 1
        if pinledger.money(r, "filled") <= 0:
            out["not_filled"] += 1
    elif k == "live_fill":
        out["filled"] += 1
        out["contracts_filled"] += pinledger.money(r, "n")
    elif k in ("refused", "dropped", "body_refused"):
        out["refused"] += 1
        g = str(r.get("why") or k)
        why[g] = why.get(g, 0) + 1


BOT = Bot(
    name="forecaster", label="Forecaster", short="Forecaster", word="forecaster",
    what="buys the 15-minute coin side its own forecast calls decided, sized from its bank",
    help=("/forecaster (or /fc) — the forecaster (subaccount 2), the same detail as /pin",),
    command="/fc", commands=("/forecaster", "/fc"),
    pots=(Pot("2", 2, what="forecaster", short="forecaster"),),
    script="forecaster_live.py", is_live=live_flag("--live"), stop_file="forecaster-live.stop",
    logs=Logs(path="forecaster-live-orders.jsonl"),
    records=Records(fills=("live_fill",), fill_qty="n", halts=("halt", "day_stop", "run_stop")),
    settings=settings,
    version=VersionRule(part=lambda n: "forecaster" in n or n == "v-crash-guard",
                        text=lambda vname, low: "forecaster" in low),
    colour="#a0479f",          # plum
    order=3,
    keepalive="boot_all.ps1 (every 10 min) restarts it unless the stop file is there",
    page_footer="Every bot: /bots.",
    activity=activity,
    funds_size=True,
    speed=Speed(rank=2, field="ev", kind="placed"),
    features=(
        Feature("forecaster_live.py", None, None, "Penny forecaster (LIVE, subaccount 2)",
                "Buys a 15-minute coin market at 98c when its own forecast says that side is as good as decided.",
                pos=2, hides=True),
        Feature("fc_variants_paper.py", None, None, "Forecaster variants (paper)",
                "The forecaster's variants side by side on paper (main, quiet and crash-guard runs); no orders.",
                pos=12, hides=True),
    ),
)
