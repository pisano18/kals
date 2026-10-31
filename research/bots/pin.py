"""The pin bot: 15-minute coin markets + hourly Bitcoin, main account (subaccount 0). Every fact copied verbatim from
botstats.py / pinphone.py / tgcharts.py at 8a9c5e1 (v-tg-rebuild step 1, 2026-10-30)."""
from bots.spec import Book, Bot, Feature, Gauge, Logs, Pot, Records, VersionRule, live_flag, opt, toks
from botdata.clock import et_clock, utc_epoch
from botdata.fmt import cents as _c, num as _num, usd

# The hourly ladders pinrun knows (v-ladder7); only KXBTCD trades live today. A new series in
# subaccount 0 that is in neither list lands in `other`, loudly -- never folded into a bot.  (botstats.PIN_HOURLY)
PIN_HOURLY = frozenset(["KXBTCD", "KXETHD", "KXSOLD", "KXXRPD", "KXDOGED", "KXBNBD", "KXHYPED"])
WX_VER = r"dipsell|dip.?sell"                       # botstats.WX_VER (the pin bot's combined-heading exclusion uses it)


def _claims(series, ticker):
    """botstats.owner, subaccount 0 after the race: the 15-minute coins and the hourly ladders."""
    import pinday
    return series in pinday.CRYPTO or series in PIN_HOURLY


def settings_pin(start, cl, sizef):
    """(botstats.settings_pin, verbatim)"""
    s = {}
    if start:
        for k in ("size", "price_ceiling", "tau_max", "early_tau_max", "early_frac", "early_min_price",
                  "early_max_price", "hedge_belief", "loss_abort", "loss_cap", "max_positions",
                  "ladder_series", "late_tau", "late_mult", "bank_brake", "code_sha",
                  # v-tg-settings-now: what its newest autosize / loss_cap record laid over the start (resize_as_start)
                  "series_size", "max_run_stake", "bank_at_sizing"):
            if k in start:
                s[k] = start[k]
    if cl:
        for flag in ("--series-size", "--max-losses"):
            v = opt(cl, flag)
            if v is not None:
                s[flag[2:].replace("-", "_")] = _num(v)
        for flag in ("--one-full-bet", "--toxic-fresh", "--jump-gate", "--no-hedge-prop"):
            s[flag[2:].replace("-", "_")] = flag in toks(cl)
    if sizef:
        s["bet_now"] = sizef.get("size")
        s["bank_at_sizing"] = sizef.get("bank")
        s["sized_at_et"] = et_clock(_num(sizef.get("epoch")) or utc_epoch(sizef.get("at")))
    bits = []
    bet = s.get("bet_now") or s.get("size")
    if bet is not None:
        bits.append("bet %g contracts" % bet + (" (sized on a %s bank)" % usd(s["bank_at_sizing"]).lstrip("+")
                                                  if s.get("bank_at_sizing") else ""))
    if s.get("price_ceiling") is not None:
        bits.append("buys up to %s with %s s or less left" % (_c(s["price_ceiling"]), s.get("tau_max", "?")))
    if s.get("early_tau_max"):
        frac = s.get("early_frac")
        size = ("a third of a bet" if frac is not None and abs(float(frac) - 0.333) < 0.01
                else "%g of a bet" % frac if frac is not None else "?")
        bits.append("early bet from %s s left: %s, %s to %s" % (s["early_tau_max"], size, _c(s.get("early_min_price")),
                                                              _c(s.get("early_max_price") or s.get("price_ceiling"))))
    if s.get("hedge_belief") is not None:
        bits.append("hedges if our odds fall under %d%%" % round(100 * float(s["hedge_belief"])))
    stops = []
    if s.get("max_losses"):
        stops.append("%d losing bets" % s["max_losses"])
    if s.get("loss_cap"):
        stops.append("a %s run loss" % usd(float(s["loss_cap"])).lstrip("+"))
    if stops:
        bits.append("halts after " + " or ".join(stops))
    if s.get("ladder_series"):
        n_ = s.get("series_size") or 1
        bits.append("hourly %s: %g contract%s a market" % ("/".join(s["ladder_series"]), n_, "" if n_ == 1 else "s"))
    return s, "; ".join(bits)


def settings(si):
    """botstats.running's pin branch: its newest log's first record, with its newest autosize / loss_cap laid over it
    (botdata.logs.settings_now, before this hook) + results/pinrun-live-size.json."""
    return settings_pin(si.start, si.cmdline, si.read_json("pinrun-live-size.json"))


def resize_as_start(r):
    """v-tg-settings-now (2026-10-31): one of pinrun's self-change records as start-record fields. pinrun writes 'new'
    for the SIZE in an autosize record and for the LOSS CAP in a loss_cap record; both carry the loss abort."""
    import re
    if (r.get("kind") or r.get("ev")) == "autosize":
        m = re.search(r"bank \$([\d.]+)", str(r.get("why") or ""))
        return {"size": r.get("new"), "loss_abort": r.get("loss_abort"), "loss_cap": r.get("loss_cap"),
                "series_size": r.get("series_size"), "max_run_stake": r.get("max_run_stake"),
                "bank_at_sizing": float(m.group(1)) if m else r.get("loss_cap_base")}
    return {"loss_cap": r.get("new"), "loss_abort": r.get("loss_abort"), "size": r.get("size"),
            "bank_at_sizing": r.get("bank")}


def activity(k, r, out, why, st):
    """botstats.activity's pin branch (verbatim)."""
    import pinledger
    if k == "order":
        out["sent"] += 1
        f = pinledger.money(r, "filled")
        out["filled" if f > 0 else "not_filled"] += 1
        out["contracts_filled"] += f
    elif k == "hedge":
        out["hedges"] += 1
    elif k in ("refused", "late_refused"):
        out["refused"] += 1
        g = str(r.get("gate") or k)
        why[g] = why.get(g, 0) + 1


# v-tg-rebuild step 5 (2026-10-30): /funds' bet-size reader, moved verbatim from pinphone.funds_sizes (where it was a
# closure over its `when` and `results`; spec.SizeIn hands it those and the phone's readers).
def size_words(si):
    """/funds: the main bot's bet size now -- its newest autosize record, else results/pinrun-live-size.json."""
    import glob
    import os
    import re
    logs = sorted(glob.glob(os.path.join(si.results, "pinrun-live-*.jsonl")))
    r = si.last_record(logs[-1], ("autosize",)) if logs else None
    if r and si.num(r.get("new")) is not None:
        m = re.search(r"bank \$([\d.]+)", str(r.get("why") or ""))
        return "main bot %g contracts a bet (sized %s%s)" % (
            si.num(r["new"]), si.when(r), (" on a %s bank" % si.usd2(m.group(1))) if m else "")
    sz = si.read_json(os.path.join(si.results, "pinrun-live-size.json")) or {}
    if si.num(sz.get("size")) is None:
        return None
    return "main bot %g contracts a bet (sized %s%s)" % (
        si.num(sz["size"]), si.when({"t": sz.get("at")}),
        (" on a %s bank" % si.usd2(sz["bank"])) if si.num(sz.get("bank")) is not None else "")


# v-tg-rebuild step 12, lane Q (2026-10-30): the phone's early warning before the pin bot's loss abort trips
def stop_gauges(wi):
    """The pin bot's loss abort (pinrun.risk_abort): it halts when the run's settled money, or the ET day's, reaches
    loss_abort (its newest loss_cap / autosize record; the start record before any). One gauge: the worse of the two,
    warned at 60% and 80% of the line, once each per ET day and run."""
    import glob
    import os
    logs = sorted(glob.glob(os.path.join(wi.results, "pinrun-live-*.jsonl")))
    if not logs:
        return []
    path = logs[-1]
    lim = wi.last_record(path, ("loss_cap", "autosize", "start")) or {}         # the newest of the three
    line = _num(lim.get("loss_abort"))
    if line is None or line >= 0:
        return []
    s = wi.last_record(path, ("settled",)) or {}
    run = _num(s.get("realised")) or 0.0
    day = (_num(s.get("day_realised")) or 0.0) if s and wi.et_day(wi.epoch(s.get("t")) or 0) == wi.today else 0.0
    h = wi.last_record(path, ("halt",)) or {}
    hit = (str(h.get("why") or "").startswith(("DAY loss cap", "loss abort"))
           and wi.et_day(wi.epoch(h.get("t")) or 0) == wi.today)
    run_id = os.path.basename(path)[len("pinrun-live-"):-len(".jsonl")]
    money, counted = (day, "settled today") if day <= run else (run, "settled this run")
    return [Gauge(key="abort", what="its loss abort", money=round(money, 2), line=line,
                  warn_at=(round(0.6 * line, 2), round(0.8 * line, 2)), period="%s run %s" % (wi.today, run_id),
                  counted=counted, trips="it halts: no new bets until /start", tripped=hit)]


# v-tg-rebuild step 12, lane Q (2026-10-30): the phone's balance check -- the main account as the pin bot's log has it
def books(wi, upto):
    """The main account's money as the pin bot last read it (its newest autosize 'bank $X', or an external-move record's
    bank, both read while flat) at or before `upto`, plus every market it settled since (settled.pnl_c, fees in)."""
    import glob
    import os
    import re
    logs = sorted(glob.glob(os.path.join(wi.results, "pinrun-live-*.jsonl")))
    if not logs:
        return []
    path = logs[-1]

    def banked(r):
        t = wi.epoch(r.get("t"))
        return t is not None and t <= upto and (_num(r.get("bank")) is not None or re.search(r"bank \$([\d.]+)", str(
            r.get("why") or "")))
    r = wi.last_record(path, ("autosize", "external"), banked)
    if not r:
        return []
    m = re.search(r"bank \$([\d.]+)", str(r.get("why") or ""))
    value0 = _num(r.get("bank")) if r.get("kind") == "external" else (float(m.group(1)) if m else None)
    t0 = wi.epoch(r.get("t"))
    if value0 is None or t0 is None:
        return []
    settled, n, tickers, last = 0.0, 0, set(), None
    for x in wi.read_since(path, t0) or []:
        t = wi.epoch(x.get("t"))
        if t is None or t <= t0 or t > upto:
            continue
        k = x.get("kind")
        if k == "settled":
            settled += (_num(x.get("pnl_c")) or 0.0) / 100.0
            n += 1
            tickers.add(str(x.get("ticker")))
            last = t
        elif (k == "order" and (_num(x.get("filled")) or 0) > 0) or k == "hedge":
            last = t
    return [Book(sub="0", t0=t0, value0=value0, settled=round(settled, 4), markets=n, tickers=frozenset(tickers),
                 since="its last sizing" if r.get("kind") == "autosize" else "it saw money move", last_t=last)]


BOT = Bot(
    name="pin", label="Pin bot", short="Pin bot", word="pin bot",
    what="15-minute coin markets + hourly Bitcoin",
    help=("/pin — the pin bot: running or not and why, version, settings, money by window, worst, open bets, cash, "
          "last markets",),
    command="/pin", commands=("/pin",),
    pots=(Pot("0", 2, claims=_claims, priority=20, what="main bot (pin)", short="main"),),
    script="pinrun.py", is_live=live_flag("--live"), stop_file="pinrun-live.stop",
    logs=Logs(glob="pinrun-live-*.jsonl", start_rule="first_line"),
    records=Records(fills=("order", "hedge"), fill_qty="filled", fill_side="want", hedge="hedge",
                    halts=("halt", "entries_stopped", "pause"),
                    resize=("autosize", "loss_cap"), resize_as_start=resize_as_start),
    settings=settings,
    # botstats.version_of: the pin bot's is every heading no other bot claims -- except a combined one naming the
    # clean-room / penny / jump band / weather words, or a single one naming the clean-room bots
    version=VersionRule(default=True, combined_not=r"cleanroom|clean-room|bettor|penny|jumpband|" + WX_VER,
                        single_not=r"cleanroom|clean-room|bettor|forecaster|ladder_live|penny"),
    colour="#2a78d6",          # blue
    order=1,
    keepalive="watch_bot.ps1 restarts it unless the stop file is there",
    always_shown=True,         # /status, /pause and /start are about it (v-tg-active)
    page_footer="More on pin: /stats (win rate vs break-even), /fills (today's orders), /open, /losses, /hedges.",
    activity=activity,
    funds_size=size_words,
    stop_gauges=stop_gauges,     # step 12 (lane Q): the phone's early warnings
    books=books,                 # step 12 (lane Q): the phone's balance check
    ledger_book="crypto",           # pinday.book_of's name for its markets (/stats' lifetime by bot)
    speed=None,                # /speed's pin section is its own (speed_gather)
    features=(
        Feature("pinrun.py", "--live", None, "Pin bot (LIVE, main account)",
                "Buys the near-certain side of a 15-minute coin market in its last seconds, when the price has pinned.",
                pos=0, hides=True),
        Feature("pinrun.py", None, "--live", "Pin bot paper arms",
                "The pin rule under variant settings (bands, early leg, confidence), on paper; no orders.", pos=9),
    ),
)
