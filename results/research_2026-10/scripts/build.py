"""build.py -- one row per market the main bot traded with real money, joining Kalshi's ledger (money truth)
to the bot's own live logs (decisions) and the version that was running.

Read-only on the repo. Writes only live_markets.jsonl, live_versions.json, build_summary.json next to itself.
Money/day conventions are transcribed from research/pinledger.py (pnl, payout) and research/pinday.py
(et_day_of_ticker) and research/downtime.py (et_offset); the self-test below re-checks the exact values
those files' own self-tests check.
"""
import calendar
import collections
import datetime as dt
import glob
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
REPO = r"C:\kals-repo"
OUT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(REPO, "results", "kalshi_ledger.json")
LOGS = sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl")))
VERSIONS_MD = os.path.join(OUT, "versions_md.json")

CRYPTO = frozenset(["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXADA15M", "KXBCH15M",
                    "KXZEC15M", "KXHYPE15M", "KXNEAR15M", "KXTON15M"])
COMMODITY = frozenset(["KXGOLD15M", "KXWTI15M", "KXSILVER15M", "KXCOPPER15M", "KXNATGAS15M"])
RACE = frozenset(["KXCRYPTOLEAD15M", "KXCRYPTOCOMP15M"])
FIRST_LIVE_DAY = "2026-09-08"
_MONTHS = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
FLAG_PREFIXES = ("pin", "tau_", "size", "early_", "price_ceiling", "toxic_", "hedge_", "max_full_bets", "skip_", "loss_",
                 "bank_", "rebuy_", "late_", "dump_", "jump_", "min_level", "one_coin_", "sweep_", "edge_floor", "ev_",
                 "max_per_", "max_positions", "max_drawdown", "no_drawdown_halt", "band_", "depth_ladder", "honest_conf",
                 "series_", "minutes", "mode", "improve_", "pick", "measured_flip", "flip_mult", "doubt_", "sigma_",
                 "external_", "xfer_confirm", "ladder_", "extra_coin", "min_fill_frac", "max_book_age_ms", "max_index_age_s",
                 "max_hedge_attempts_per_close", "reconcile_fail_halt", "look_drop_c", "attempts_on_send")


# ------------------------------------------------------------------ transcribed conventions
def et_offset(epoch):
    """research/downtime.py: UTC-4 from the second Sunday of March to the first Sunday of November, else UTC-5."""
    t = dt.datetime(1970, 1, 1) + dt.timedelta(seconds=float(epoch))
    y = t.year
    mar = dt.datetime(y, 3, 8)
    dst_start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7, hours=7)
    nov = dt.datetime(y, 11, 1)
    dst_end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7, hours=6)
    return -4 * 3600 if dst_start <= t < dst_end else -5 * 3600


def money(s, *names):
    for n in names:
        if n in s:
            try:
                return float(s[n])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def payout(s):
    """research/pinledger.py payout(): value (cents) when sane, else the yes/no result; both sides pay the winner."""
    res = str(s.get("market_result") or "").strip().lower()
    val = s.get("value")
    if val is not None:
        try:
            v = float(val) / 100.0
        except (TypeError, ValueError):
            v = None
        if v is not None and 0.0 <= v <= 1.0:
            return money(s, "yes_count_fp") * v + money(s, "no_count_fp") * (1.0 - v)
    if res == "yes":
        return money(s, "yes_count_fp")
    if res == "no":
        return money(s, "no_count_fp")
    return 0.0


def pnl(s):
    cost = money(s, "yes_total_cost_dollars") + money(s, "no_total_cost_dollars")
    return payout(s) - cost - money(s, "fee_cost")


def pnl_task_formula(s):
    """The orchestrator's formula: revenue/100 + min(yes, no) - costs - fee. Kept as a cross-check."""
    return (money(s, "revenue") / 100.0 + min(money(s, "yes_count_fp"), money(s, "no_count_fp"))
            - money(s, "yes_total_cost_dollars") - money(s, "no_total_cost_dollars") - money(s, "fee_cost"))


def parse_ticker(ticker):
    """-> dict(series, stamp, local ET datetime, et_day, close_utc_epoch, hour_et, weekday) or None."""
    try:
        parts = str(ticker).split("-")
        series, stamp = parts[0], parts[1]
        yy, mon, dd = int(stamp[0:2]), _MONTHS[stamp[2:5].upper()], int(stamp[5:7])
        rest = stamp[7:]
        if len(rest) >= 4:
            hh, mm = int(rest[0:2]), int(rest[2:4])
        elif len(rest) == 2:
            hh, mm = int(rest), 0
        else:
            hh, mm = 0, 0
    except (AttributeError, IndexError, KeyError, ValueError):
        return None
    local = dt.datetime(2000 + yy, mon, dd, hh, mm)
    local_epoch = calendar.timegm(local.timetuple())
    off = et_offset(local_epoch)              # offset read at roughly the right instant (4-5 h error is harmless here)
    close_utc = local_epoch - off
    off2 = et_offset(close_utc)
    if off2 != off:
        close_utc = local_epoch - off2
    return {"series": series, "et_day": local.strftime("%Y-%m-%d"), "close_utc": close_utc,
            "close_utc_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(close_utc)),
            "close_et": local.strftime("%Y-%m-%d %H:%M ET"), "hour_et": hh, "weekday": local.strftime("%a")}


def epoch_of(t):
    try:
        return calendar.timegm(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def book_of(series):
    if series in CRYPTO:
        return "crypto"
    if series in COMMODITY:
        return "commodity"
    if series in RACE:
        return "coin race"
    return "other"


def selftest():
    s = {"ticker": "KXNEAR15M-26SEP172345-45", "market_result": "no", "no_count_fp": "4.00",
         "no_total_cost_dollars": "3.920000", "yes_total_cost_dollars": "0.000000", "revenue": 400,
         "fee_cost": "0.005500", "settled_time": "2026-09-18T03:45:04.700045Z"}
    assert abs(pnl(s) - (4.00 - 3.92 - 0.0055)) < 1e-9
    assert abs(pnl_task_formula(s) - pnl(s)) < 1e-9
    both = {"ticker": "KXBTC15M-26SEP172115-15", "market_result": "no", "yes_count_fp": "99.00",
            "yes_total_cost_dollars": "52.470000", "no_count_fp": "99.00", "no_total_cost_dollars": "71.280000",
            "revenue": 0, "fee_cost": "3.123400"}
    assert abs(pnl(both) - (-27.8734)) < 1e-4 and abs(pnl_task_formula(both) - pnl(both)) < 1e-9
    tie_y = {"market_result": "scalar", "value": 50, "revenue": 50, "yes_count_fp": "1.00",
             "yes_total_cost_dollars": "0.970000", "no_count_fp": "0.00", "no_total_cost_dollars": "0.000000",
             "fee_cost": "0.002100"}
    assert abs(pnl(tie_y) + 0.4721) < 1e-4
    p = parse_ticker("KXBTC15M-26SEP170000-00")
    assert p["et_day"] == "2026-09-17" and p["close_utc_iso"] == "2026-09-17T04:00:00Z" and p["hour_et"] == 0
    p = parse_ticker("KXGOLD15M-26SEP172345-15")
    assert p["et_day"] == "2026-09-17" and p["close_utc_iso"] == "2026-09-18T03:45:00Z"
    p = parse_ticker("KXBTCD-26OCT0710-T83199.99")
    assert p["et_day"] == "2026-10-07" and p["hour_et"] == 10 and p["close_utc_iso"] == "2026-10-07T14:00:00Z"
    assert et_offset(calendar.timegm((2026, 1, 15, 4, 30, 0))) == -5 * 3600
    assert et_offset(calendar.timegm((2026, 9, 17, 4, 0, 0))) == -4 * 3600
    print("build selftest: OK")


# ------------------------------------------------------------------ the ledger
def load_ledger():
    with open(LEDGER, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = d["settlements"]
    markets = {}
    for key, s in rows.items():
        tk = s.get("ticker") or ""
        pt = parse_ticker(tk)
        m = markets.setdefault(tk, {"ticker": tk, "rows": 0, "money": 0.0, "money_task_formula": 0.0, "yes_count": 0.0,
                                    "no_count": 0.0, "yes_cost": 0.0, "no_cost": 0.0, "fee": 0.0, "revenue_c": 0.0,
                                    "results": [], "values": [], "settled_times": [], "event_ticker": s.get("event_ticker"),
                                    "parsed": pt})
        m["rows"] += 1
        m["money"] += pnl(s)
        m["money_task_formula"] += pnl_task_formula(s)
        m["yes_count"] += money(s, "yes_count_fp")
        m["no_count"] += money(s, "no_count_fp")
        m["yes_cost"] += money(s, "yes_total_cost_dollars")
        m["no_cost"] += money(s, "no_total_cost_dollars")
        m["fee"] += money(s, "fee_cost")
        m["revenue_c"] += money(s, "revenue")
        m["results"].append(str(s.get("market_result")))
        m["values"].append(s.get("value"))
        m["settled_times"].append(s.get("settled_time"))
    return markets, d.get("written")


# ------------------------------------------------------------------ the logs
def flags_of(start):
    out = {}
    for k, v in start.items():
        if k in ("t", "kind"):
            continue
        if k.startswith(FLAG_PREFIXES):
            out[k] = v
    return out


def side_of_body(body):
    side = (body or {}).get("side")
    if side == "ask":
        return "no"
    if side == "bid":
        return "yes"
    return None


def our_price_from_body(body):
    try:
        p = float((body or {}).get("price"))
    except (TypeError, ValueError):
        return None
    side = (body or {}).get("side")
    return 1.0 - p if side == "ask" else p


SIGNAL_KEYS = ("fair", "edge_c", "sigma", "strike", "spot", "size", "take_n", "tau", "price", "ladder_under",
               "ladder_total", "ladder_levels", "cond_x", "cond_n", "cond_own", "widened", "early_held", "budget_left",
               "level_age_ms", "level_age_exact", "sell_share_3s", "taker_n_3s", "trade_age_s", "book_age_ms",
               "index_age_s", "digits", "series_size")
ORDER_KEYS = ("latency_ms", "book_age_ms", "index_age_s", "tau_at_send", "ask_seen", "limit_sent", "sweep_headroom_c",
              "swept", "sell_share_3s", "taker_n_3s", "trade_age_s", "level_age_ms", "status", "status_code", "filled",
              "fill_known", "remaining", "exec_price", "exec_yes_price", "fee", "fee_total", "error", "refused",
              "early_held", "order_id", "t_ms_decide", "t_ms_send")
HEDGE_KEYS = ("side", "price", "n", "asked", "ask", "ask_size", "limit_sent", "slip_c", "swept", "entry", "entry_tau",
              "tau", "belief", "locked_loss_c", "status", "edge_c", "flip_mult", "ladder_n", "past_halt", "order_id")
REFUSED_KEYS = ("gate", "tau", "price", "fair", "edge_c", "leg", "want", "wanted_side", "size", "take_n", "level_age_ms",
                "min_age_ms", "sell_share_3s", "min_share", "taker_n_3s", "trade_age_s", "age_ms", "age_s", "ceiling",
                "floor", "need_c", "need_edge_c", "cap", "cap_x", "have", "held", "jump_sd", "need_sd", "moves",
                "against_sigma", "sigma", "spot", "strike", "yes_ask", "no_ask", "first_ask", "paid", "disc_c", "budget",
                "budget_left", "spent", "tried", "fills", "reach", "offered", "min_conf", "prev_conf", "prev_age_s")


def scan_logs():
    files = []
    per_ticker = collections.defaultdict(lambda: {"orders": [], "settled": [], "hedges": [], "hedge_alarms": [],
                                                  "hedge_quotes": 0, "hedge_quote_min_belief": None,
                                                  "hedge_quote_first_t": None, "hedge_quote_last_t": None,
                                                  "hedge_prop": [], "hedge_panic": [], "hedge_other": [],
                                                  "refusal_gates": collections.Counter(), "refusals": [],
                                                  "late_boost": [], "late_refused": [], "taper": [], "sweep_depth": [],
                                                  "full_cap_trim": [], "scalein_cap": [], "band_boost": [],
                                                  "boost_off": [], "dumped": [], "scrap": [], "plant": [],
                                                  "errors": [], "files": set()})
    seen_settled_lines = set()
    for p in LOGS:
        base = os.path.basename(p)
        info = {"file": base, "start": None, "end": None, "start_epoch": None, "end_epoch": None, "code_sha": None,
                "flags": {}, "records": 0, "kinds": collections.Counter(), "autosize": [], "halts": [], "end_record": None,
                "orders": 0, "filled_orders": 0, "tickers_ordered": set(), "external": [], "unexplained": []}
        last_signal = {}
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict):
                    continue
                k = r.get("kind")
                t = r.get("t")
                info["records"] += 1
                info["kinds"][k] += 1
                if t:
                    if info["start"] is None:
                        info["start"] = t
                    info["end"] = t
                if k == "start":
                    info["flags"] = flags_of(r)
                    info["code_sha"] = r.get("code_sha")
                    info["start_full"] = {kk: vv for kk, vv in r.items() if kk not in ("t", "kind")}
                    continue
                if k == "autosize":
                    info["autosize"].append({"t": t, "old": r.get("old"), "new": r.get("new"), "why": r.get("why"),
                                             "loss_abort": r.get("loss_abort")})
                    continue
                if k == "halt":
                    info["halts"].append({"t": t, "why": r.get("why")})
                    continue
                if k == "end":
                    info["end_record"] = {"t": t, "state": r.get("state")}
                    continue
                if k in ("external", "unexplained"):
                    info[k].append({"t": t, "move": r.get("move"), "amount": r.get("amount"), "bank": r.get("bank")})
                    continue
                tk = r.get("ticker")
                if not tk:
                    continue
                pt = per_ticker[tk]
                if k == "signal":
                    last_signal[tk] = r
                elif k == "order":
                    body = r.get("body") or {}
                    sig = last_signal.get(tk)
                    sig_ok = sig is not None and (epoch_of(t) or 0) - (epoch_of(sig.get("t")) or 0) <= 5
                    o = {kk: r.get(kk) for kk in ORDER_KEYS}
                    o["t"] = t
                    o["file"] = base
                    o["leg_logged"] = r.get("leg")
                    o["want"] = r.get("want") or side_of_body(body)
                    o["asked"] = float(body.get("count")) if body.get("count") not in (None, "") else None
                    o["body_price_ours"] = our_price_from_body(body)
                    o["body_side"] = body.get("side")
                    if o["limit_sent"] is None:
                        o["limit_sent"] = o["body_price_ours"]
                    if o["tau_at_send"] is None and sig_ok:
                        o["tau_at_send"] = sig.get("tau")
                    if o["ask_seen"] is None and sig_ok:
                        o["ask_seen"] = sig.get("price")
                    for kk in ("sell_share_3s", "taker_n_3s", "trade_age_s", "level_age_ms", "book_age_ms"):
                        if o.get(kk) is None and sig_ok and sig.get(kk) is not None:
                            o[kk] = sig.get(kk)
                    if sig_ok:
                        sd = {kk: sig.get(kk) for kk in SIGNAL_KEYS}
                        lad = sig.get("ladder")
                        sd["ladder_touch"] = lad[0] if isinstance(lad, list) and lad else None
                        sd["ladder_n_levels_listed"] = len(lad) if isinstance(lad, list) else None
                        sd["leg"] = sig.get("leg")
                        sd["t"] = sig.get("t")
                        o["signal"] = sd
                    else:
                        o["signal"] = None
                    f = o.get("filled")
                    try:
                        o["filled"] = float(f) if f is not None else 0.0
                    except (TypeError, ValueError):
                        o["filled"] = 0.0
                    # leg label: logged, else by tau (the staged early leg only exists from 09-17)
                    lg = o["leg_logged"]
                    if lg is None:
                        tau = o.get("tau_at_send")
                        lg = "early" if (isinstance(tau, (int, float)) and tau > 30) else "full"
                        o["leg_source"] = "derived_from_tau"
                    else:
                        o["leg_source"] = "logged"
                    o["leg"] = lg
                    pt["orders"].append(o)
                    pt["files"].add(base)
                    info["orders"] += 1
                    info["tickers_ordered"].add(tk)
                    if o["filled"] > 0:
                        info["filled_orders"] += 1
                elif k == "settled":
                    key = line.strip()
                    if key in seen_settled_lines:
                        continue
                    seen_settled_lines.add(key)
                    pt["settled"].append({"t": t, "file": base, "want": r.get("want"), "result": r.get("result"),
                                          "cost": r.get("cost"), "pnl_c": r.get("pnl_c"), "boost": r.get("boost")})
                    pt["files"].add(base)
                elif k == "hedge":
                    h = {kk: r.get(kk) for kk in HEDGE_KEYS}
                    h["t"] = t
                    h["file"] = base
                    pt["hedges"].append(h)
                    pt["files"].add(base)
                elif k == "hedge_alarm":
                    pt["hedge_alarms"].append({"t": t, "belief": r.get("belief"), "tau": r.get("tau"), "entry": r.get("entry"),
                                               "n": r.get("n"), "threshold": r.get("threshold"), "trigger": r.get("trigger"),
                                               "jump_sd": r.get("jump_sd")})
                elif k == "hedge_quote":
                    pt["hedge_quotes"] += 1
                    b = r.get("belief")
                    if isinstance(b, (int, float)):
                        if pt["hedge_quote_min_belief"] is None or b < pt["hedge_quote_min_belief"]:
                            pt["hedge_quote_min_belief"] = b
                    if pt["hedge_quote_first_t"] is None:
                        pt["hedge_quote_first_t"] = t
                    pt["hedge_quote_last_t"] = t
                elif k == "hedge_prop":
                    pt["hedge_prop"].append({"t": t, "belief": r.get("belief"), "fraction": r.get("fraction"),
                                             "target": r.get("target"), "buy_now": r.get("buy_now"), "tau": r.get("tau")})
                elif k == "hedge_panic":
                    pt["hedge_panic"].append({"t": t, "belief": r.get("belief"), "ask": r.get("ask"), "tau": r.get("tau"),
                                              "n": r.get("n"), "entry": r.get("entry")})
                elif k in ("hedge_no_ask", "hedge_gave_up", "hedge_wait_price", "hedge_blind"):
                    pt["hedge_other"].append({"kind": k, "t": t, "belief": r.get("belief"), "tau": r.get("tau"),
                                              "ask": r.get("ask"), "why": r.get("why"), "tries": r.get("tries")})
                elif k == "refused":
                    g = str(r.get("gate"))
                    pt["refusal_gates"][g] += 1
                    if g != "no_offer" and len(pt["refusals"]) < 40:
                        d = {kk: r.get(kk) for kk in REFUSED_KEYS if r.get(kk) is not None}
                        d["t"] = t
                        pt["refusals"].append(d)
                elif k == "dumped":
                    pt["refusal_gates"]["dumped(A10)"] += 1
                    if len(pt["dumped"]) < 10:
                        pt["dumped"].append({"t": t, "price": r.get("price"), "fair": r.get("fair"), "tau": r.get("tau"),
                                             "disc_c": r.get("disc_c"), "want": r.get("want"), "refused": r.get("refused")})
                elif k == "late_boost":
                    pt["late_boost"].append({"t": t, "tau": r.get("tau"), "was": r.get("was"), "now": r.get("now"),
                                             "cap": r.get("cap"), "mult": r.get("mult"), "fair_ours": r.get("fair_ours"),
                                             "jump_sd": r.get("jump_sd")})
                elif k == "late_refused":
                    pt["late_refused"].append({"t": t, "tau": r.get("tau"), "fair_ours": r.get("fair_ours"),
                                               "jump_sd": r.get("jump_sd"), "need_pin": r.get("need_pin")})
                elif k == "taper":
                    pt["taper"].append({"t": t, "tau": r.get("tau"), "touch": r.get("touch"), "rungs": r.get("rungs"),
                                        "flat": r.get("flat"), "tapered": r.get("tapered"), "limit": r.get("limit")})
                elif k == "sweep_depth":
                    pt["sweep_depth"].append({"t": t, "touch": r.get("touch"), "ladder": r.get("ladder"), "was": r.get("was"),
                                              "now": r.get("now"), "limit": r.get("limit")})
                elif k == "full_cap_trim":
                    pt["full_cap_trim"].append({"t": t, "tau": r.get("tau"), "was": r.get("was"), "now": r.get("now"),
                                                "leg": r.get("leg"), "price": r.get("price")})
                elif k == "scalein_cap":
                    pt["scalein_cap"].append({"t": t, "tau": r.get("tau"), "ask": r.get("ask"), "limit_was": r.get("limit_was"),
                                              "limit": r.get("limit")})
                elif k == "band_boost":
                    pt["band_boost"].append({"t": t, "tau": r.get("tau"), "price": r.get("price"), "was": r.get("was"),
                                             "now": r.get("now"), "mult": r.get("mult")})
                elif k in ("band_boost_off", "late_boost_off"):
                    pt["boost_off"].append({"kind": k, "t": t, "pnl_c": r.get("pnl_c"), "cost": r.get("cost")})
                elif k == "scrap":
                    pt["scrap"].append({"t": t, "filled": r.get("filled"), "asked": r.get("asked"), "price": r.get("price"),
                                        "want": r.get("want")})
                elif k in ("plant", "plant_attempt"):
                    pt["plant"].append({"kind": k, "t": t, "side": r.get("side"), "price": r.get("price") or r.get("ask"),
                                        "filled": r.get("filled"), "status": r.get("status")})
                elif k == "error":
                    pt["errors"].append({"t": t, "where": r.get("where"), "err": str(r.get("err"))[:200]})
        info["start_epoch"] = epoch_of(info["start"])
        info["end_epoch"] = epoch_of(info["end"])
        info["tickers_ordered"] = sorted(info["tickers_ordered"])
        info["kinds"] = dict(info["kinds"])
        files.append(info)
    return files, per_ticker


# ------------------------------------------------------------------ versions
def load_versions_md():
    with open(VERSIONS_MD, encoding="utf-8") as fh:
        rows = json.load(fh)
    live = [r for r in rows if r["status"] in ("LIVE",) and r["main_bot"] and r["when"]]
    for r in live:
        r["epoch"] = epoch_of(r["when"])
    live.sort(key=lambda r: r["epoch"])
    return live, rows


def name_version(files, live_versions):
    """A log file's version = the latest LIVE main-bot VERSIONS.md header at or before its start (10 min slack for
    the '~hh:mx' headers); also the next header after its start, so an ambiguous match is visible."""
    for f in files:
        st = f["start_epoch"]
        if st is None:
            f["version_name"] = None
            continue
        cands = [v for v in live_versions if v["epoch"] <= st + (600 if v["approx"] else 0)]
        if cands:
            v = cands[-1]
            f["version_name"] = v["name"]
            f["version_when"] = v["when"]
            f["version_line"] = v["line"]
            f["version_header"] = v["header"][:160]
            f["version_matched_by_slack"] = v["epoch"] > st
        else:
            f["version_name"] = "pre-VERSIONS.md (no entry; first entry v-cond 2026-09-10 07:47Z)"
            f["version_when"] = None
            f["version_line"] = None
            f["version_header"] = None
            f["version_matched_by_slack"] = False
        nxt = [v for v in live_versions if v["epoch"] > st]
        f["next_version_after_start"] = (nxt[0]["name"] + " @ " + nxt[0]["when"]) if nxt else None


def main():
    selftest()
    t0 = time.time()
    ledger, written = load_ledger()
    print("ledger markets:", len(ledger), "written", written)
    files, per_ticker = scan_logs()
    print("log files:", len(files), "tickers with log records:", len(per_ticker), "(%.1fs)" % (time.time() - t0))
    live_versions, all_versions = load_versions_md()
    name_version(files, live_versions)

    # overlaps between live log files (two live processes at once?)
    overlaps = []
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            a, b = files[i], files[j]
            if a["end_epoch"] and b["start_epoch"] and b["start_epoch"] < a["end_epoch"] - 5:
                overlaps.append({"a": a["file"], "a_end": a["end"], "b": b["file"], "b_start": b["start"],
                                 "overlap_s": a["end_epoch"] - b["start_epoch"]})
    print("overlapping live log pairs:", len(overlaps))

    def file_for_epoch(e):
        """The live log whose [start, end] contains e; if several, the latest-started one."""
        best = None
        for f in files:
            if f["start_epoch"] is not None and f["end_epoch"] is not None and f["start_epoch"] <= e <= f["end_epoch"] + 1:
                if best is None or f["start_epoch"] > best["start_epoch"]:
                    best = f
        return best

    by_file = {f["file"]: f for f in files}
    rows_out = []
    # a market is in the dataset if Kalshi settled it for us OR the bot sent an order / booked a settlement / hedged it;
    # tickers that only ever appear in `refused` records were never traded and are left out
    universe = set(ledger) | {tk for tk, v in per_ticker.items() if v["orders"] or v["settled"] or v["hedges"]}
    for tk in sorted(universe):
        pt = parse_ticker(tk)
        led = ledger.get(tk)
        lg = per_ticker.get(tk)
        series = pt["series"] if pt else str(tk).split("-")[0]
        book = book_of(series)
        et_day = pt["et_day"] if pt else None
        orders = sorted(lg["orders"], key=lambda o: (o["t"] or "", o.get("t_ms_send") or 0)) if lg else []
        filled = [o for o in orders if o["filled"] > 0]
        # attribution: the log holding the first FILLED order (else the first order), else the log spanning the close
        attrib_file, attrib_how = None, None
        if filled:
            attrib_file, attrib_how = filled[0]["file"], "first_filled_order"
        elif orders:
            attrib_file, attrib_how = orders[0]["file"], "first_order_unfilled"
        elif pt:
            f = file_for_epoch(pt["close_utc"] - 60)
            if f:
                attrib_file, attrib_how = f["file"], "close_time_in_log_span"
        fi = by_file.get(attrib_file) if attrib_file else None
        # the bet side: the filled orders' side (majority by contracts), else the ledger's larger side
        want = None
        if filled:
            c = collections.Counter()
            for o in filled:
                c[o["want"]] += o["filled"]
            want = c.most_common(1)[0][0]
        elif led:
            want = "yes" if led["yes_count"] >= led["no_count"] else "no"
        hedged_ledger = bool(led and led["yes_count"] > 0 and led["no_count"] > 0)
        hedge_fills = [h for h in (lg["hedges"] if lg else []) if (h.get("n") or 0) > 0]
        # money
        m = led["money"] if led else None
        result = None
        if led:
            res = [r for r in led["results"] if r in ("yes", "no")]
            result = res[0] if res else (led["results"][0] if led["results"] else None)
        bet_count = bet_cost = hedge_count = hedge_cost = hedge_payout = None
        if led and want in ("yes", "no"):
            other = "no" if want == "yes" else "yes"
            bet_count, bet_cost = led[want + "_count"], led[want + "_cost"]
            hedge_count, hedge_cost = led[other + "_count"], led[other + "_cost"]
            # the other side's payout: value-aware like pinledger.payout
            v = None
            try:
                vv = led["values"][0]
                v = float(vv) / 100.0 if vv is not None else None
            except (TypeError, ValueError):
                v = None
            if v is not None and 0.0 <= v <= 1.0:
                hedge_payout = hedge_count * (v if other == "yes" else 1.0 - v)
                bet_payout = bet_count * (v if want == "yes" else 1.0 - v)
            else:
                hedge_payout = hedge_count if result == other else 0.0
                bet_payout = bet_count if result == want else 0.0
        if m is None:
            rclass = "no_ledger_row"
        elif m > 0:
            rclass = "hedged_win" if hedged_ledger else "win"
        elif m < 0:
            rclass = "hedged_loss" if hedged_ledger else "loss"
        else:
            rclass = "flat"
        bet_won = None
        if led and want in ("yes", "no") and result in ("yes", "no"):
            bet_won = (result == want)
        # loss type / leg mix
        legs_filled = [o["leg"] for o in filled]
        leg_mix = "+".join(sorted(set(legs_filled), key=["early", "full", "topup", "late_add"].index)) if legs_filled else None
        first = filled[0] if filled else None
        pnl_c_sum = sum(float(s.get("pnl_c") or 0.0) for s in lg["settled"]) / 100.0 if lg else None
        row = {
            "ticker": tk, "series": series, "coin": series.replace("KX", "").replace("15M", ""), "book": book,
            "in_main_table": (book == "crypto" and et_day is not None and et_day >= FIRST_LIVE_DAY
                              and (led is not None or bool(filled))),
            "traded": led is not None or bool(filled),
            "close_utc": pt["close_utc_iso"] if pt else None, "close_et": pt["close_et"] if pt else None,
            "et_day": et_day, "hour_et": pt["hour_et"] if pt else None, "weekday": pt["weekday"] if pt else None,
            "version": {"file": attrib_file, "how": attrib_how, "name": fi["version_name"] if fi else None,
                        "code_sha": fi["code_sha"] if fi else None, "file_start": fi["start"] if fi else None,
                        "file_end": fi["end"] if fi else None},
            "want": want, "result": result, "bet_won": bet_won, "result_class": rclass, "hedged_ledger": hedged_ledger,
            "hedge_filled_in_log": bool(hedge_fills),
            "money": m, "money_task_formula": led["money_task_formula"] if led else None,
            "bet_count": bet_count, "bet_cost": bet_cost, "bet_payout": bet_payout if led and want in ("yes", "no") else None,
            "hedge_count": hedge_count, "hedge_cost": hedge_cost, "hedge_payout": hedge_payout,
            "hedge_dollars_ledger": (hedge_payout - hedge_cost) if (hedge_cost is not None and hedge_count) else None,
            "cost_total": (led["yes_cost"] + led["no_cost"]) if led else None, "fee": led["fee"] if led else None,
            "ledger": ({"rows": led["rows"], "results": led["results"], "values": led["values"],
                        "settled_times": led["settled_times"], "yes_count": led["yes_count"], "no_count": led["no_count"],
                        "yes_cost": led["yes_cost"], "no_cost": led["no_cost"], "revenue_c": led["revenue_c"],
                        "event_ticker": led["event_ticker"]} if led else None),
            "n_orders": len(orders), "n_filled_orders": len(filled), "legs_filled": legs_filled, "leg_mix": leg_mix,
            "first_fill": ({"t": first["t"], "leg": first["leg"], "price": first.get("exec_price") or first.get("limit_sent"),
                            "limit_sent": first.get("limit_sent"), "ask_seen": first.get("ask_seen"),
                            "tau": first.get("tau_at_send"), "filled": first["filled"], "want": first["want"],
                            "swept": first.get("swept"), "sweep_headroom_c": first.get("sweep_headroom_c"),
                            "level_age_ms": first.get("level_age_ms"), "sell_share_3s": first.get("sell_share_3s"),
                            "taker_n_3s": first.get("taker_n_3s"), "trade_age_s": first.get("trade_age_s"),
                            "book_age_ms": first.get("book_age_ms"),
                            "fair": (first.get("signal") or {}).get("fair"), "edge_c": (first.get("signal") or {}).get("edge_c"),
                            "sigma": (first.get("signal") or {}).get("sigma")} if first else None),
            "legs": orders,
            "log_settled": lg["settled"] if lg else [], "pnl_c_sum_dollars": pnl_c_sum,
            "pnl_c_disagrees": (abs(pnl_c_sum - m) > 0.05) if (pnl_c_sum is not None and m is not None) else None,
            "hedge": ({"records": lg["hedges"], "alarms": lg["hedge_alarms"], "quotes_n": lg["hedge_quotes"],
                       "quotes_min_belief": lg["hedge_quote_min_belief"], "quotes_first_t": lg["hedge_quote_first_t"],
                       "quotes_last_t": lg["hedge_quote_last_t"], "prop": lg["hedge_prop"], "panic": lg["hedge_panic"],
                       "other": lg["hedge_other"]} if lg else None),
            "refusal_gates": dict(lg["refusal_gates"]) if lg else {}, "refusals": lg["refusals"] if lg else [],
            "extras": ({"late_boost": lg["late_boost"], "late_refused": lg["late_refused"], "taper": lg["taper"],
                        "sweep_depth": lg["sweep_depth"], "full_cap_trim": lg["full_cap_trim"],
                        "scalein_cap": lg["scalein_cap"], "band_boost": lg["band_boost"], "boost_off": lg["boost_off"],
                        "dumped": lg["dumped"], "scrap": lg["scrap"], "plant": lg["plant"], "errors": lg["errors"]}
                       if lg else None),
            "log_files": sorted(lg["files"]) if lg else [],
        }
        rows_out.append(row)

    with open(os.path.join(OUT, "live_markets.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows_out:
            fh.write(json.dumps(r, default=str) + "\n")
    vers = []
    for f in files:
        vers.append({"file": f["file"], "start_utc": f["start"], "end_utc": f["end"],
                     "hours": ((f["end_epoch"] or 0) - (f["start_epoch"] or 0)) / 3600.0,
                     "code_sha": f["code_sha"], "version_name": f["version_name"], "version_when": f.get("version_when"),
                     "version_header": f.get("version_header"), "version_matched_by_slack": f.get("version_matched_by_slack"),
                     "next_version_after_start": f.get("next_version_after_start"),
                     "flags": f["flags"], "records": f["records"], "kinds": f["kinds"], "orders": f["orders"],
                     "filled_orders": f["filled_orders"], "n_tickers_ordered": len(f["tickers_ordered"]),
                     "autosize": f["autosize"][:3] + ([{"...": len(f["autosize"]) - 3}] if len(f["autosize"]) > 3 else []),
                     "size_range": ([min(a["new"] for a in f["autosize"] if isinstance(a["new"], (int, float))),
                                     max(a["new"] for a in f["autosize"] if isinstance(a["new"], (int, float)))]
                                    if any(isinstance(a["new"], (int, float)) for a in f["autosize"]) else None),
                     "halts": f["halts"], "end_record": f["end_record"], "external": f["external"],
                     "unexplained": f["unexplained"]})
    with open(os.path.join(OUT, "live_versions.json"), "w", encoding="utf-8") as fh:
        json.dump({"files": vers, "overlapping_pairs": overlaps, "versions_md_live_main": [
            {"name": v["name"], "when": v["when"], "approx": v["approx"], "line": v["line"]} for v in live_versions]},
            fh, indent=1, default=str)
    main_rows = [r for r in rows_out if r["in_main_table"]]
    summ = {"ledger_written": written, "markets_total": len(rows_out), "main_table": len(main_rows),
            "main_with_ledger": sum(1 for r in main_rows if r["money"] is not None),
            "main_no_ledger": sum(1 for r in main_rows if r["money"] is None),
            "main_no_log_orders": sum(1 for r in main_rows if r["money"] is not None and r["n_orders"] == 0),
            "main_no_filled_orders": sum(1 for r in main_rows if r["money"] is not None and r["n_filled_orders"] == 0),
            "main_money": sum(r["money"] for r in main_rows if r["money"] is not None),
            "main_losses": sum(1 for r in main_rows if r["money"] is not None and r["money"] < 0),
            "pnl_c_disagree": sum(1 for r in main_rows if r["pnl_c_disagrees"]),
            "books": dict(collections.Counter(r["book"] for r in rows_out)),
            "version_names": dict(collections.Counter(r["version"]["name"] for r in main_rows)),
            "attrib_how": dict(collections.Counter(r["version"]["how"] for r in main_rows))}
    with open(os.path.join(OUT, "build_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summ, fh, indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str))
    print("done in %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
