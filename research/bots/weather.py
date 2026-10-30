"""The weather dip-seller: sells YES on a daily-high temperature bracket after a drop, subaccount 3's POOL 0 (2026-10-04;
its $50 back out 10-15, stopped). Every fact copied verbatim from botstats.py / pinphone.py / tgcharts.py at 8a9c5e1
(v-tg-rebuild step 1, 2026-10-30). Subaccount 3's pool 2 is the jump band's since 10-30 (bots/jumpband.py claims its
coins first); every other market in subaccount 3 is this bot's history."""
import re

from bots.spec import Bot, Feature, Logs, Pot, Records, VersionRule, live_flag
from botdata.fmt import fmt_g as _fmt_g, plural as _n, usd

# the weather dip-seller's VERSIONS.md entries (v-dipsell-live ...); pinphone._NOT_PIN_RE carries the same words
WX_VER = r"dipsell|dip.?sell"                       # botstats.WX_VER


def settings_weather(start, cl):
    """The weather dip-seller's rails, from its live start record (they are code constants there).
    (botstats.settings_weather, verbatim)"""
    st = start or {}
    r, tr = st.get("rails") or {}, st.get("trigger") or {}
    s = {"rails": r, "trigger": tr, "start_pot": st.get("start_pot"), "subaccount": st.get("subaccount"),
         "pool": r.get("pool")}
    bits = []
    if tr:
        hl = tr.get("hours_left") or ["?", "?"]
        bits.append("sells YES 1c over the ask after a %sc+ hourly drop with %s-%s h left"
                    % (_fmt_g(tr.get("drop_c")), _fmt_g(hl[0]), _fmt_g(hl[-1])))
    if r.get("contracts") is not None:
        bits.append("%s contracts an order, one order a market" % _fmt_g(r["contracts"]))
    if r.get("max_open") is not None:
        bits.append("at most %s open" % _fmt_g(r["max_open"]))
    if r.get("window_s"):
        bits.append("unfilled orders cancelled after %s h" % _fmt_g(float(r["window_s"]) / 3600.0))
    if r.get("day_stop_frac") is not None:
        pot = st.get("start_pot")
        bits.append("stops the day at -%s%% of its %s start" % (
            _fmt_g(100.0 * float(r["day_stop_frac"])), usd(float(pot)).lstrip("+") if pot is not None else "?"))
    if r.get("kill_after") is not None:
        bits.append("stops for good if behind after %s settled fills" % _fmt_g(r["kill_after"]))
    if r.get("max_fills") is not None or r.get("max_days") is not None:
        bits.append("ends at %s fills or %s days" % (_fmt_g(r.get("max_fills")), _fmt_g(r.get("max_days"))))
    return s, "; ".join(bits)


def settings(si):
    return settings_weather(si.start, si.cmdline)


def activity(k, r, out, why, st):
    """botstats.activity's weather branch (verbatim; `triggers` and `filled_tk` live in st)."""
    import pinledger
    # dipsell_live.py: one resting SELL-YES order a trigger, 3 h, then cancelled if unfilled
    if k == "trigger" and r.get("act"):
        st["triggers"] += 1
    elif k == "placed":
        out["sent"] += 1
    elif k == "fill":
        if r.get("ticker") not in st["filled_tk"]:
            st["filled_tk"].add(r.get("ticker"))
            out["filled"] += 1
        out["contracts_filled"] += pinledger.money(r, "delta")
    elif k == "cancel":
        out["cancelled"] += 1
    elif k in ("rail_refused", "rejected", "body_refused"):
        out["refused"] += 1
        g = str(r.get("why") or ("Kalshi refused it (HTTP %s)" % r.get("status") if k == "rejected" else k))
        why[g] = why.get(g, 0) + 1


def activity_note(out, st):
    triggers = st["triggers"]
    out["triggers"] = triggers
    out["note"] = ("%s seen today; each order rests up to 3 h and is cancelled if unfilled, by design"
                   % _n(triggers, "price-drop trigger"))


BOT = Bot(
    name="weather", label="Weather dip-seller", short="Weather", word="weather dip-seller",
    what="sells YES on a daily-high temperature bracket after a 10c+ hourly drop, 2 contracts",
    help=("/weather (or /wx) — the weather dip-seller (subaccount 3, weather cash pool), the same detail as /pin",),
    command="/weather", commands=("/weather", "/wx"),
    # the rest of subaccount 3 (its KXHIGH brackets, pool 0); no short /funds name since the jump band took the number
    pots=(Pot("3", 0, what="weather dip-seller"),),
    script="dipsell_live.py", is_live=live_flag("--live"), stop_file="dipsell-live.stop",
    logs=Logs(path="dipsell-live-orders.jsonl"),
    records=Records(fills=("fill",), fill_qty="delta", fixed_side="yes", act="sold",
                    halts=("day_stop", "kill", "done"),
                    # the weather dip-seller's rails (dipsell_live.rails_refusal)
                    refusal_words=((r"^one_per_market$", "already ordered in that market"), (r"^max_open$", "5 already open"),
                                   (r"^no_cash$", "not enough cash"), (r"^day_stop$", "day stop hit"),
                                   (r"^killed$", "stopped for good"), (r"^done$", "test finished"),
                                   (r"^stopped$", "stop file"), (r"^pool \S+ is not", "wrong cash pool"))),
    settings=settings,
    version=VersionRule(part=lambda n: bool(re.search(WX_VER, n)),
                        text=lambda vname, low: bool(re.search(WX_VER, low))),
    colour="#4b3fa0",          # indigo (stopped)
    order=5,
    keepalive="boot_all.ps1 (every 10 min) restarts it unless the stop file is there",
    page_footer="Every bot: /bots.",
    activity=activity, activity_note=activity_note,
    funds_size=False,          # /funds says no bet size for it
    features=(
        Feature("dipsell_live.py", None, None, "Weather dip-seller (LIVE, subaccount 3)",
                "Sells daily high-temperature markets (KXHIGH) into dips, in Kalshi's weather cash pool.",
                pos=4, hides=True),
    ),
)
