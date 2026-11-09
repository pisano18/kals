r"""pinrules_watch.py -- what pin's two 2026-11-01 rules give up and save, scored on every fire, sent to the phone.

The rules (operator 11-01: "Push it live ... Heavily monitor what it gives up, what it saves, and what performance
would've been without it as accurately as possible. Give a report after the end of today, end of tomorrow, and end of
3 days, and end of 7 days ... Also alert if it saves, loses, or gives up anything major"):
  A  --ws-later-fall-c 10   a LATER buy in a 15-minute market (something already held on that side) is refused when the
                            index is across the strike from our side and our side's mid fell 10c or more in 5 s
                            (gate "ws_later_fall"); the rest of that side's buys in that close are refused too
                            ("ws_later_skip").
  B  --hedge-jump-max 8     the jump hedge (--hedge-jump 6) fires only for one-second jumps under 8 sd; a jump of 8 sd
                            or more with pin's odds still over the 0.40 line is logged "jump_capped" instead.
  C  --hedge-odds-mult M    (v-oddsmult, 11-02; operator: "Go. Push it yourself") when the belief line fires with 11+ s
                            left, pin also buys (M - 1) x the position of the hedge side as a second order right after
                            the covering hedge; each such leg is logged "hedge_extra". Scored on its OWN money: the
                            extra contracts at the result, fee included (+ = made, - = lost).

Run ONCE per tick (the scheduled task KalsPinRulesWatch, every 5 minutes, as SYSTEM). No orders, no Kalshi keys, no
network except Telegram. Reads pin's own logs in results\ (pinrun-live-*.jsonl: the rule records, settled, hedge and
order records); a market's result comes from pin's settled records (pin always holds something in a market either rule
touches); a market with no result 3 hours after its close is reported as unknown (the public API is never called from
the server's address).

SCORING (per event; "effect" = what the rule did to pin's money; + = SAVED, - = GAVE UP):
  A  the refused buy is filled by walking its logged ask ladder up to its limit for would_n contracts (what the order
     gets if nobody beats us), valued at the result with Kalshi's taker fee ceil(0.07*n*p*(1-p)*100)/100. If pin's
     market was hedged after the refusal, the hedge would have covered those contracts too: the extra hedge is priced
     on the real hedge orders' unused depth (ladder_n - asked at the price they filled) and then at the last hedge's
     limit. effect = -(buy + extra hedge). Several refusals in one market share the room: each takes what the earlier
     hypothetical buys left of its would_n.
  B  the skipped hedge is filled by walking the logged hedge-side ladder up to its limit for n. effect = (what pin's
     real later hedges on the same side made on those contracts) - (what the jump hedge would have made). Bet won: the
     rule saved the hedge's cost. Bet lost: it gave up the earlier, cheaper hedge's extra recovery.
  "usual fill": the same effect times pin's own fill ratio (contracts filled / asked) for that leg type (A) or for its
  hedges (B), from its order and hedge records -- the order may not have got everything on the ladder.
  Without the rules = pin's real settled money in the window - the rules' net effect.

ALERTS (urgent: sent even in the phone's quiet hours): one event's effect >= $10 either way; the running net past
-$25, -$50, -$75, ... (each level once). REPORTS (silent in quiet hours): 00:05 ET on Nov 2 (Nov 1, from the rules'
start), Nov 3 (Nov 2), Nov 4 (Nov 1-3), Nov 8 (Nov 1-7); each also written to results\pinrules_report_<n>.txt.
State (every scored event, the sent flags) in results\pinrules_watch.json; a late tick sends what is due, never twice.

v-fixes-alerts (2026-11-04, push 11-04; the operator: "track them thoroughly"): two more URGENT alerts from the same tick.
  * A BOOST RAIL TRIP: a band_boost_off / late_boost_off record in pin's CURRENT run (the 1.5x band boost or the
    last-10-s boost switched itself off for the rest of the run after a losing boosted leg). Said once per trip (state
    key "rail_trips"), in plain words: which boost, the market, the leg that tripped it and its $, and the remedy (a
    restart while flat: /approve pinrestart). A trip in an EARLIER run is never alerted: that restart put the boost back.
  * A $10+ ENGAGEMENT of the tracked changes D to J (botdata.fixes, the data behind the phone's /fixes page: boost rail,
    hedge tick, cheap jump skip, late-boost bypass fix, extra stake cap, max positions 5, extra on odds), once per
    engagement (state key "fix_alerted"). botdata.fixes is imported inside the tick, inside a try: a failure there is
    logged and never stops rules A/B/C.

  python research\pinrules_watch.py              one tick
  python research\pinrules_watch.py --dry        one tick, print instead of sending, state not saved
  python research\pinrules_watch.py --self-test [--log PATH]   the scorer on 11-01's HYPE and NEAR + a synthetic flip,
                                                 a synthetic band rail trip and a synthetic $12 engagement of change I
  python research\pinrules_watch.py --test-send  one message to the phone, labelled as a test
"""
import calendar
import glob
import json
import math
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from botdata import clock  # noqa: E402
import logfiles  # noqa: E402  (pin's logs archived by log_rotate.py after 60 days)

RESULTS = os.path.join(os.path.dirname(HERE), "results")
STATE = os.path.join(RESULTS, "pinrules_watch.json")
LOG = os.path.join(RESULTS, "pinrules_watch.log")
REPORT_TXT = os.path.join(RESULTS, "pinrules_report_%d.txt")
SIZE_JSON = os.path.join(RESULTS, "pinrun-live-size.json")
CFG_OVERRIDE = os.path.join(RESULTS, "pinrules_watch.cfg.json")   # optional {"start": "2026-11-01T20:40:00Z"}
TELEGRAM_CFG = r"C:\kals\telegram.json"

MAJOR_USD = 10.0
RUNNING_STEP = 25.0
UNKNOWN_AFTER_S = 3 * 3600
REPORTS = [   # (n, send on this ET day at 00:05, title, first day, last day)
    (1, "2026-11-02", "end of Sun Nov 1 (day 1)", "2026-11-01", "2026-11-01"),
    (2, "2026-11-03", "end of Mon Nov 2 (day 2)", "2026-11-02", "2026-11-02"),
    (3, "2026-11-04", "end of 3 days (Nov 1 to Nov 3)", "2026-11-01", "2026-11-03"),
    (4, "2026-11-08", "end of 7 days (Nov 1 to Nov 7)", "2026-11-01", "2026-11-07"),
]
REPORT_AT_S = 300
A_GATES = ("ws_later_fall", "ws_later_skip")
RULE_NAME = {"A": "later-buy check", "B": "jump cap", "C": "bigger hedge"}
RULE_WHAT = {"A": "skip a later buy when the index is across the line and our price fell 10c+ in 5 s",
             "B": "no jump hedge on a jump of 8 sd or more",
             "C": "extra contracts of the hedge side when pin's odds line fires with 11+ s left"}
# v-fixes-alerts: the two boost rails (pinrun: rec("band_boost_off" / "late_boost_off") in reconcile) and the remedy
RAIL_WORDS = {"band_boost_off": ("band", "the 1.5x band boost (buys priced 95.5c to 98.1c)"),
              "late_boost_off": ("late", "the 1.5x last-10-seconds boost")}
RESTART_REMEDY = "A restart while flat puts it back on: /approve pinrestart"
# the tracked changes D..M (botdata.fixes) and the verb each one's $ takes (+ / -); K (v-cheapwin, 11-07) is a skipped
# cheap morning buy: + = its shadow lost (saved), - = its shadow won (gave up); L (v-0925v JS, 11-08) is the jump hedge
# in shadow: + = the premium it would have paid stayed in the bank (kept), - = the save it would have made was missed;
# M (call B, 11-08) is a buy of pin's own the 2-bet budget held back: + = the bet lost, the held-back stake was saved,
# - = the bet won, the held-back gain was given up (M's true-3rd-bet list is not an event list and never alerts)
# N (v-hedgeline60, 11-08) is a hedge bought with belief between 0.40 and 0.60: + = it saved vs the 0.40 line (a flip
# caught cheaper or a save 0.40 would have missed), - = premium 0.40 would not have paid (the bet recovered)
FIX_POS = {"D": "MADE", "E": "MADE", "F": "SAVED", "G": "SAVED", "H": "SAVED", "I": "MADE", "J": "MADE", "K": "SAVED",
           "L": "KEPT", "M": "SAVED", "N": "SAVED"}
FIX_NEG = {"D": "LOST", "E": "COST", "F": "GAVE UP", "G": "GAVE UP", "H": "GAVE UP", "I": "LOST", "J": "LOST",
           "K": "GAVE UP", "L": "GAVE UP", "M": "GAVE UP", "N": "COST"}


# ---------------------------------------------------------------------------
def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg)
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def fee(n, p):
    if n <= 0 or p is None:
        return 0.0
    return math.ceil(round(0.07 * n * p * (1 - p) * 100, 6)) / 100.0


def epoch(t):
    return clock.utc_epoch(t)


def walk(ladder, n, limit=None, fallback=None):
    """[(got, price)] from an ascending ask ladder [[p, size], ...] up to `limit` for n contracts. With no usable
    ladder: `fallback` [(price, size)] levels the same way."""
    lv = []
    for x in (ladder or fallback or []):
        try:
            p, s = float(x[0]), float(x[1])
        except (TypeError, ValueError, IndexError):
            continue
        if p > 0 and s > 0:
            lv.append((p, s))
    lv.sort()
    out, left = [], float(n or 0)
    for p, s in lv:
        if left <= 1e-9 or (limit is not None and p > float(limit) + 1e-9) or p >= 1.0:
            break
        g = min(s, left)
        out.append((g, p))
        left -= g
    return out


def value(fills, wins):
    """Money of buying `fills` [(n, p)] on a side that wins (True) or loses, fee per level."""
    return sum(g * ((1.0 if wins else 0.0) - p) - fee(g, p) for g, p in fills)


def got(fills):
    return sum(g for g, _ in fills)


def avg_px(fills):
    n = got(fills)
    return sum(g * p for g, p in fills) / n if n else None


def coin_label(ticker):
    m = re.match(r"^KX([A-Z0-9]+?)15M-", str(ticker or ""))
    if m:
        return m.group(1)
    m = re.match(r"^KX([A-Z]+?)D-", str(ticker or ""))
    return (m.group(1) + " hourly") if m else str(ticker)


def market_label(ticker, close_s):
    c = clock.et_clock(close_s, with_day=False) if close_s else None
    return "%s %s market" % (coin_label(ticker), c.replace(" ET", "") if c else "")


def usd(x, sign=True):
    if x is None:
        return "?"
    s = "-" if x < -0.004 else ("+" if sign else "")
    return "%s$%.2f" % (s, abs(x))


def pct(x, bank):
    if not bank or x is None:
        return ""
    return " (%s%.2f%% of the bank)" % ("+" if x >= 0 else "-", abs(x) / bank * 100)


# ---------------------------------------------------------------------------
class Logs:
    """Everything one tick needs from pin's logs."""

    WANT = ('"start"', "ws_later_", '"jump_capped"', '"settled"', '"hedge"', '"hedge_extra"', '"order"',
            '"band_boost_off"', '"late_boost_off"')

    def __init__(self, paths):
        self.starts, self.events, self.settled, self.hedges, self.orders = [], [], {}, {}, []
        self.trips = []                       # v-fixes-alerts: band_boost_off / late_boost_off, each with its log's path
        seen = set()
        for path in paths:
            try:
                fh = logfiles.open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
                    if not any(w in line for w in self.WANT):
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    k = r.get("kind")
                    if k == "start":
                        self.starts.append((r.get("t"), r, path))
                        continue
                    tk = r.get("ticker")
                    t = r.get("t")
                    if not tk or not t:
                        continue
                    key = (k, tk, t, r.get("want"), r.get("side"), r.get("cost"), r.get("price"), r.get("n"),
                           r.get("client_order_id"), r.get("gate"))
                    if key in seen:
                        continue
                    seen.add(key)
                    if (k == "refused" and r.get("gate") in A_GATES) or k == "jump_capped":
                        self.events.append(r)
                    elif k == "hedge_extra" and r.get("status") == "executed" and (r.get("n") or 0) > 0:
                        self.events.append(r)          # rule C: an extra leg that filled
                    elif k == "settled":
                        self.settled.setdefault(tk, []).append(r)
                    elif k == "hedge" and r.get("status") == "executed" and (r.get("n") or 0) > 0:
                        self.hedges.setdefault(tk, []).append(r)
                    elif k == "order":
                        self.orders.append(r)
                    elif k in RAIL_WORDS:
                        r["_path"] = path
                        self.trips.append(r)
        self.events.sort(key=lambda r: r["t"])
        self.trips.sort(key=lambda r: r["t"])
        for v in self.hedges.values():
            v.sort(key=lambda r: r["t"])

    def result(self, tk):
        for r in self.settled.get(tk, []):
            if r.get("result") in ("yes", "no"):
                return r["result"]
        return None

    def fill_ratio(self, leg=None):
        """Contracts filled / contracts asked over pin's orders (leg type `leg`; None = every leg)."""
        a = f = 0.0
        for o in self.orders:
            if leg is not None and o.get("leg") != leg:
                continue
            try:
                ask = float((o.get("body") or {}).get("count") or 0)
            except (TypeError, ValueError):
                ask = 0.0
            if ask <= 0:
                continue
            a += ask
            f += min(float(o.get("filled") or 0), ask)
        return (f / a, a) if a else (None, 0)

    def hedge_fill_ratio(self):
        a = f = 0.0
        for hs in self.hedges.values():
            for h in hs:
                a += float(h.get("asked") or h.get("n") or 0)
                f += float(h.get("n") or 0)
        return (f / a) if a else None


def pin_paths(start_epoch):
    """pin's live logs that can hold anything from `start_epoch` on, plus the log before (fill ratios)."""
    ps = logfiles.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))     # plain + archived, in start order
    keep = [p for p in ps if logfiles.mtime(p, 0.0) >= (start_epoch or 0) - 86400]   # 0: archived since the listing
    i = ps.index(keep[0]) if keep else len(ps)
    return ps[max(0, i - 1):] if keep else ps[-2:]


def rules_start(starts):
    """t of the first start record with either new rule switched on (or the override file's)."""
    try:
        with open(CFG_OVERRIDE, encoding="utf-8") as fh:
            v = json.load(fh).get("start")
            if v:
                return v
    except (OSError, ValueError):
        pass
    for t, r, _ in sorted(starts, key=lambda x: x[0] or ""):
        for k, v in r.items():
            if re.search(r"later_fall|jump_max", k) and isinstance(v, (int, float)) and v > 0:
                return t
    return None


# ---------------------------------------------------------------------------
def score_events(L, now):
    """Every rule event scored (or pending). A market's A refusals share one room."""
    out = []
    room_used = {}
    capped_seen = set()
    hr = L.hedge_fill_ratio()
    for e in L.events:
        tk = e["ticker"]
        close_s = e.get("close_s")
        res = L.result(tk)
        if e.get("kind") == "hedge_extra":
            ev = score_C(e, res)
            ev["ratio"] = None
        elif e.get("kind") == "jump_capped":
            key = (tk, e.get("want"))
            if key in capped_seen:
                continue
            capped_seen.add(key)
            ev = score_B(L, e, res)
            ev["ratio"] = hr
        else:
            ev = score_A(L, e, res, room_used)
            ev["ratio"] = L.fill_ratio(e.get("leg"))[0] or L.fill_ratio()[0]
        want = e.get("want") or ev.get("want")
        ev.update(t=e["t"], ticker=tk, close_s=close_s, want=want, result=res,
                  id="%s|%s|%s|%s%s" % (ev["rule"], tk, want, e["t"],
                                        ("|" + str(e.get("order_id"))) if e.get("kind") == "hedge_extra" else ""))
        if res is None:
            ev["status"] = "unknown" if close_s and now > float(close_s) + UNKNOWN_AFTER_S else "pending"
            ev["effect"] = None
        else:
            ev["status"] = "scored"
        ev["effect_usual"] = None if ev["effect"] is None or ev["ratio"] is None else round(ev["effect"] * ev["ratio"], 2)
        out.append(ev)
    return out


def extra_hedge_fills(hedges, n):
    """n more contracts on the hedge side: first the unused depth of pin's real hedge orders (ladder_n - asked, at the
    price each filled), then the last hedge order's limit."""
    out, left = [], float(n)
    for h in hedges:
        if left <= 1e-9:
            break
        spare = max(0.0, float(h.get("ladder_n") or 0) - float(h.get("asked") or h.get("n") or 0))
        g = min(spare, left)
        if g > 0:
            out.append((g, float(h["price"])))
            left -= g
    if left > 1e-9 and hedges:
        h = hedges[-1]
        lim = h.get("limit_sent")
        p = float(lim) if lim is not None else min(float(h["price"]) + 0.10, 0.999)
        out.append((left, p))
    return out


def score_A(L, e, res, room_used):
    tk, want = e["ticker"], e.get("want")
    key = (tk, want)
    want_n = float(e.get("would_n") if e.get("would_n") is not None else (e.get("size") or 0))
    n = max(0.0, want_n - room_used.get(key, 0.0))
    lim = e.get("limit")
    fallback = [(e.get("price"), want_n)] if e.get("price") else None
    fills = walk(e.get("ladder"), n, lim, fallback) if n > 0 else []
    g = got(fills)
    room_used[key] = room_used.get(key, 0.0) + g
    ev = dict(rule="A", gate=e.get("gate"), leg=e.get("leg"), tau=e.get("tau"), n=round(g, 2), px=avg_px(fills),
              fall_c=e.get("fall_c"), extra_hedge_n=0.0, extra_hedge_px=None, buy=None, hedge=None, effect=None)
    if res is None or g <= 0:
        if g <= 0 and res is not None:
            ev.update(buy=0.0, hedge=0.0, effect=0.0)
        return ev
    buy = value(fills, res == want)
    hs = [h for h in L.hedges.get(tk, []) if h.get("side") != want and h["t"] >= e["t"]]
    hf = extra_hedge_fills(hs, g) if hs else []
    hv = value(hf, res != want) if hf else 0.0
    ev.update(buy=round(buy, 2), hedge=round(hv, 2), effect=round(-(buy + hv), 2),
              extra_hedge_n=round(got(hf), 2), extra_hedge_px=avg_px(hf))
    return ev


def score_B(L, e, res):
    tk, want = e["ticker"], e.get("want")
    side = e.get("side") or ("no" if want == "yes" else "yes")
    n = float(e.get("n") or 0)
    lim = e.get("limit")
    if lim is None and e.get("ask") is not None:
        lim = min(float(e["ask"]) + 0.10, 0.999)
    fb = [(e.get("ask"), e.get("ask_size") or n)] if e.get("ask") is not None else None
    fills = walk(e.get("ladder"), n, lim, fb)
    g = got(fills)
    ev = dict(rule="B", gate="jump_capped", jump_sd=e.get("jump_sd"), belief=e.get("belief"), tau=e.get("tau"),
              n=round(g, 2), px=avg_px(fills), side=side, jump_hedge=None, real_hedge=None, effect=None)
    if res is None:
        return ev
    jv = value(fills, res == side)
    left, real = g, []
    for h in L.hedges.get(tk, []):
        if h.get("side") != side or h["t"] < e["t"] or left <= 1e-9:
            continue
        take = min(float(h["n"]), left)
        real.append((take, float(h["price"])))
        left -= take
    rv = value(real, res == side)
    ev.update(jump_hedge=round(jv, 2), real_hedge=round(rv, 2), real_hedge_n=round(got(real), 2),
              effect=round(rv - jv, 2))
    return ev


def score_C(e, res):
    """Rule C: an extra leg that filled. effect = that leg's own money at the result (fee included)."""
    side = e.get("side")
    want = "no" if side == "yes" else "yes"
    n = float(e.get("n") or 0)
    px = e.get("price")
    ev = dict(rule="C", gate="hedge_extra", side=side, want=want, tau=e.get("tau"), n=round(n, 2),
              px=(float(px) if px is not None else None), mult=e.get("mult"), extra_of=e.get("extra_of"),
              base_n=e.get("base_n"), belief=e.get("belief"), effect=None)
    if res is None or n <= 0 or px is None:
        return ev
    ev["effect"] = round(value([(n, float(px))], res == side), 2)
    return ev


# ---------------------------------------------------------------------------
def pin_money(L, start_t, first_day, last_day):
    s = 0.0
    t0 = epoch(start_t) if start_t else 0
    for rs in L.settled.values():
        for r in rs:
            te = epoch(r.get("t"))
            if te is None or te < t0:
                continue
            d = clock.et_day(te)
            if first_day <= d <= last_day:
                s += (r.get("pnl_c") or 0) / 100.0
    return s


def describe(ev):
    """One line: what the rule skipped and what happened."""
    mk = market_label(ev["ticker"], ev.get("close_s"))
    if ev["rule"] == "A":
        what = "skipped a %s buy of %.0f %s at about %s" % (ev.get("leg") or "later", ev["n"] or 0,
                                                             (ev.get("want") or "").capitalize(),
                                                             ("%.1fc" % (ev["px"] * 100)) if ev.get("px") else "?")
        if ev.get("fall_c") is not None:
            what += " (our price had fallen %.0fc in 5 s)" % abs(float(ev["fall_c"]))
    elif ev["rule"] == "C":
        what = "bought %.0f EXTRA %s at about %s (%.2fx the position at the odds line)" % (
            ev["n"] or 0, (ev.get("side") or "").capitalize(), ("%.1fc" % (ev["px"] * 100)) if ev.get("px") else "?",
            float(ev.get("mult") or 0))
    else:
        what = "skipped a hedge of %.0f %s at about %s on a jump of %s sd" % (
            ev["n"] or 0, (ev.get("side") or "").capitalize(), ("%.1fc" % (ev["px"] * 100)) if ev.get("px") else "?",
            ("%.1f" % ev["jump_sd"]) if ev.get("jump_sd") is not None else "8+")
    if ev.get("tau") is not None:
        what += " with %s s left" % ev["tau"]
    return mk, what


def verdict(ev):
    if ev["status"] != "scored":
        return "not settled yet" if ev["status"] == "pending" else "result unknown"
    x = ev["effect"]
    if abs(x) < 0.005:
        return "no money either way"
    if ev["rule"] == "C":
        return ("MADE %s" % usd(x, False)) if x > 0 else ("LOST %s" % usd(-x, False))
    return ("SAVED %s" % usd(x, False)) if x > 0 else ("GAVE UP %s" % usd(-x, False))


def outcome_words(ev):
    if ev["status"] != "scored":
        return ""
    res = (ev.get("result") or "").capitalize()
    if ev["rule"] == "A":
        s = "The market settled %s, so that buy would have %s %s" % (
            res, "made" if ev["buy"] >= 0 else "lost", usd(abs(ev["buy"]), False))
        if ev.get("extra_hedge_n"):
            s += "; the bigger hedge that came with it would have %s %s" % (
                "made" if ev["hedge"] >= 0 else "cost", usd(abs(ev["hedge"]), False))
        return s + "."
    if ev["rule"] == "C":
        return "Our bet %s, so the %.0f extra contracts %s %s." % (
            "LOST (a flip)" if ev.get("result") == ev.get("side") else "won", ev["n"] or 0,
            "made" if ev["effect"] >= 0 else "lost", usd(abs(ev["effect"]), False))
    won = ev.get("result") == ev.get("want")
    s = "Our bet %s, so that hedge would have %s %s" % ("won" if won else "LOST (a flip)",
                                                      "made" if ev["jump_hedge"] >= 0 else "cost",
                                                      usd(abs(ev["jump_hedge"]), False))
    if ev.get("real_hedge_n"):
        s += "; pin's own later hedge on those contracts made %s" % usd(ev["real_hedge"])
    return s + "."


def totals(evs):
    sc = [e for e in evs if e["status"] == "scored"]
    saved = sum(e["effect"] for e in sc if e["effect"] > 0)
    gave = -sum(e["effect"] for e in sc if e["effect"] < 0)
    usual = sum(e["effect_usual"] for e in sc if e.get("effect_usual") is not None)
    return dict(fires=len(evs), scored=len(sc), open=len(evs) - len(sc), saved=saved, gave=gave, net=saved - gave,
                usual=usual)


def in_window(ev, first_day, last_day):
    return first_day <= clock.et_day(epoch(ev["t"])) <= last_day


def report_text(n, title, first_day, last_day, evs, L, start_t, bank):
    w = [e for e in evs if in_window(e, first_day, last_day)]
    T = totals(w)
    actual = pin_money(L, start_t, first_day, last_day)
    start_clock = clock.et_clock(epoch(start_t)) if start_t else "?"
    lines = ["📋 PIN RULES REPORT %d of 4 · %s" % (n, title),
             "Rules live since %s.%s" % (start_clock, " Day 1 counts from then." if first_day == "2026-11-01" else ""),
             "",
             "All rules: %d fires · saved or made %s · gave up or lost %s · net %s%s" % (
                 T["fires"], usd(T["saved"], False), usd(T["gave"], False), usd(T["net"]), pct(T["net"], bank)),
             "Pin real: %s · without the rules it would have been %s" % (usd(actual), usd(actual - T["net"])),
             "If the skipped orders had filled like pin's usually do: net %s" % usd(T["usual"])]
    if T["open"]:
        lines.append("%d fire%s not settled or unknown yet (not counted)." % (T["open"], "" if T["open"] == 1 else "s"))
    for r in ("A", "B", "C"):
        rw = [e for e in w if e["rule"] == r]
        R = totals(rw)
        ratio = next((e["ratio"] for e in reversed(rw) if e.get("ratio") is not None), None)
        w_pos, w_neg = ("made", "lost") if r == "C" else ("saved", "gave up")
        lines += ["", "%s (%s): %d fire%s · %s %s · %s %s · net %s" % (
            RULE_NAME[r].capitalize(), RULE_WHAT[r], R["fires"], "" if R["fires"] == 1 else "s", w_pos,
            usd(R["saved"], False), w_neg, usd(R["gave"], False), usd(R["net"])),
            "   usual-fill net %s%s" % (usd(R["usual"]), (" (pin fills %.0f%% of what it asks)" % (ratio * 100))
                                        if ratio is not None else "")]
        for e in rw:
            mk, what = describe(e)
            lines.append(" • %s · %s: %s: it %s" % (clock.et_clock(epoch(e["t"]), with_day=(first_day != last_day)),
                                                mk, verdict(e), what))
    if last_day > first_day:
        lines += ["", "By day:"]
        d = first_day
        while d <= last_day:
            dw = [e for e in w if in_window(e, d, d)]
            D = totals(dw)
            a = pin_money(L, start_t, d, d)
            lines.append(" • %s: %d fires, net %s · pin %s, without the rules %s" % (
                clock.day_label(d), D["fires"], usd(D["net"]), usd(a), usd(a - D["net"])))
            d = clock.shift_day(d, 1)
    if n == 2:
        A = totals(evs)
        a = pin_money(L, start_t, "2026-11-01", last_day)
        lines += ["", "Since the start: %d fires, net %s · pin %s, without the rules %s" % (
            A["fires"], usd(A["net"]), usd(a), usd(a - A["net"]))]
    return "\n".join(lines)


def alert_text(ev, run, bank):
    mk, what = describe(ev)
    if ev["rule"] == "C":
        head = ("💰 PIN BIGGER HEDGE MADE %s" % usd(ev["effect"], False)) if ev["effect"] > 0 else \
            ("💸 PIN BIGGER HEDGE LOST %s" % usd(-ev["effect"], False))
    else:
        head = ("🛡️ PIN RULE SAVED %s" % usd(ev["effect"], False)) if ev["effect"] > 0 else \
            ("💸 PIN RULE GAVE UP %s" % usd(-ev["effect"], False))
    return "\n".join([
        "%s%s · %s · %s" % (head, pct(ev["effect"], bank), RULE_NAME[ev["rule"]], mk),
        "It %s at %s." % (what, clock.et_clock(epoch(ev["t"]), with_day=False)),
        outcome_words(ev),
        "Rules so far: %d fires · saved %s · gave up %s · net %s" % (run["fires"], usd(run["saved"], False),
                                                                      usd(run["gave"], False), usd(run["net"]))])


def running_text(level, run, bank):
    return "\n".join([
        "⚠️ PIN RULES NET %s%s · the new pin rules have now given up or lost more than they saved or made" % (
            usd(run["net"]), pct(run["net"], bank)),
        "Past the %s line: %d fires · saved or made %s · gave up or lost %s." % (
            usd(-level), run["fires"], usd(run["saved"], False), usd(run["gave"], False)),
        "Turning a rule off = restart pin without its flag (--ws-later-fall-c / --hedge-jump-max / --hedge-odds-mult)."])


# ---------------------------------------------------------------------------
# v-fixes-alerts (2026-11-04): the boost rails and the tracked changes D..J
def trip_id(trip):
    return "%s|%s|%s" % (trip.get("kind"), trip.get("ticker"), trip.get("t"))


def trip_leg(L, trip):
    """The settled leg that tripped the rail: same ticker, same cost and pnl_c (the trip record copies both), nearest in
    time; None when that leg is not in the log."""
    best = None
    te = epoch(trip.get("t")) or 0.0
    for s in L.settled.get(trip.get("ticker"), []):
        try:
            if abs(float(s.get("cost")) - float(trip.get("cost"))) > 5e-5:
                continue
            if abs(float(s.get("pnl_c") or 0) - float(trip.get("pnl_c") or 0)) > 0.02:
                continue
        except (TypeError, ValueError):
            continue
        d = abs((epoch(s.get("t")) or 0.0) - te)
        if best is None or d < best[0]:
            best = (d, s)
    return best[1] if best else None


def new_trips(L, st):
    """band_boost_off / late_boost_off records of pin's CURRENT run (the newest start record's log) not yet alerted. A
    trip in an earlier run is never alerted: the restart that began the current run put the boost back on."""
    if not L.starts:
        return []
    cur = max(L.starts, key=lambda x: x[0] or "")[2]
    seen = set(st.get("rail_trips") or [])
    return [r for r in L.trips if r.get("_path") == cur and trip_id(r) not in seen]


def rail_text(trip, L, bank):
    which, boost = RAIL_WORDS[trip["kind"]]
    leg = trip_leg(L, trip)
    pnl = float(trip.get("pnl_c") or 0) / 100.0
    side = ("a %s leg" % (leg.get("want") or "").capitalize()) if leg and leg.get("want") else "a leg"
    at = ("bought at %.1fc" % (float(trip["cost"]) * 100)) if trip.get("cost") is not None else "bought"
    money = ("lost %s" % usd(-pnl, False)) if pnl < 0 else ("made %s" % usd(pnl, False))
    what = "%s %s %s%s on a market where the boost had been used" % (side, at, money, pct(pnl, bank))
    if leg and leg.get("market_net_c") is not None:
        what += " (the whole market net %s)" % usd(float(leg["market_net_c"]) / 100.0)
    return "\n".join([
        "🔕 PIN %s BOOST OFF · %s" % (which.upper(), market_label(trip["ticker"], trip.get("close_s"))),
        "%s is off for the rest of this pin run: at %s %s, and that trips the rail." % (
            boost[0].upper() + boost[1:], clock.et_clock(epoch(trip["t"]), with_day=False), what),
        "Until pin restarts, those buys are at 1x instead of 1.5x. %s" % RESTART_REMEDY])


def fix_id(c, ev):
    return "%s|%s|%s" % (c.get("id"), ev.get("coin"), ev.get("t"))


def new_fix_events(changes, st):
    """(change, event) pairs of the changes D..J whose settled $ is MAJOR_USD or more either way, not yet alerted."""
    seen = set(st.get("fix_alerted") or [])
    out = []
    for c in changes:
        if c.get("id") not in FIX_POS:
            continue
        for ev in c.get("events") or []:
            x = ev.get("usd")
            if x is None or abs(x) < MAJOR_USD or fix_id(c, ev) in seen:
                continue
            out.append((c, ev))
    return out


def fix_text(c, ev, tot, bank):
    x = ev["usd"]
    verb = (FIX_POS if x > 0 else FIX_NEG)[c["id"]]
    return "\n".join([
        "%s PIN CHANGE %s %s%s · %s %s · %s" % ("💰" if x > 0 else "💸", verb, usd(abs(x), False), pct(x, bank),
                                               c["id"], c.get("name"), ev.get("coin") or "?"),
        "%s: %s" % (ev.get("et") or "?", ev.get("words") or ""),
        "The change: %s." % c.get("what"),
        "All tracked changes so far: engaged %d times · net %s%s · /fixes lists every one" % (
            tot["engaged"], usd(tot["net_usd"]), pct(tot["net_usd"], bank))])


# ---------------------------------------------------------------------------
class Phone:
    """The phone path (also research\\kalshi_watch.py's, v-kwatch 11-07): urgent = sent with sound even in the quiet
    hours, the rest silent then. `log_fn` (default this file's log) is where its own failures are written."""

    def __init__(self, dry=False, log_fn=None):
        self.dry = dry
        self.log = log_fn or log
        self.cfg = {}
        try:
            with open(TELEGRAM_CFG, encoding="utf-8") as fh:
                self.cfg = json.load(fh)
        except (OSError, ValueError) as e:
            self.log("no phone config (%s)" % type(e).__name__)

    def quiet(self, now):
        try:
            from phone import quiet as Q
            return Q.is_quiet(self.cfg, now)
        except Exception:
            h = int(time.strftime("%H", time.gmtime(now + clock._et_off(now))))
            return h >= 23 or h < 7

    def send(self, text, urgent, now):
        if self.dry:
            print("---- %s message ----\n%s\n" % ("URGENT" if urgent else "quiet-ok", text))
            return True
        token, chat = self.cfg.get("token"), self.cfg.get("chat_id")
        if not token or not chat:
            self.log("not sent: the phone config has no token or chat_id")
            return False
        from phone.html import MAX_LEN, split_text
        from phone.transport import Telegram
        tg = Telegram(token)
        silent = (not urgent) and self.quiet(now)
        try:
            for chunk in split_text(text, MAX_LEN):
                d = tg._call("sendMessage", {"chat_id": chat, "text": chunk,
                                             "disable_notification": "true" if silent else None})
                if not d.get("ok"):
                    self.log("Telegram said not ok: %s" % str(d)[:200])
                    return False
            return True
        except Exception as e:
            self.log("send failed: %s" % type(e).__name__)
            return False


def load_state():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"events": {}, "alerted": [], "levels": [], "reports": {}, "rail_trips": [], "fix_alerted": []}


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1)
    os.replace(tmp, STATE)


def bank_now():
    try:
        with open(SIZE_JSON, encoding="utf-8") as fh:
            return float(json.load(fh).get("bank") or 0) or None
    except (OSError, ValueError, TypeError):
        return None


def tick(dry=False, now=None):
    now = time.time() if now is None else now
    st = load_state()
    probe = Logs(sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")))[-3:])
    start_t = st.get("start") or rules_start(probe.starts)
    if not start_t:
        log("waiting: no pin log has started with --ws-later-fall-c / --hedge-jump-max yet")
        return
    if not st.get("start"):
        st["start"] = start_t
        log("rules start found: %s" % start_t)
    paths = pin_paths(epoch(start_t))
    L = Logs(paths)
    evs = [e for e in score_events(L, now) if epoch(e["t"]) >= epoch(start_t) - 1]
    phone = Phone(dry)
    bank = bank_now()
    for e in evs:
        st["events"][e["id"]] = e
    run = totals(evs)
    # alerts: one event >= $10 either way, once
    for e in evs:
        if e["status"] == "scored" and abs(e["effect"]) >= MAJOR_USD and e["id"] not in st["alerted"]:
            if phone.send(alert_text(e, run, bank), True, now):
                st["alerted"].append(e["id"])
                log("alert sent: %s %s" % (e["id"], e["effect"]))
    # the running net past -$25, -$50, ...
    if run["net"] <= -RUNNING_STEP:
        level = RUNNING_STEP * math.floor(-run["net"] / RUNNING_STEP)
        if level not in st["levels"]:
            if phone.send(running_text(level, run, bank), True, now):
                st["levels"].append(level)
                log("running alert sent at -%s" % level)
    # v-fixes-alerts: a boost rail tripped in the current run (urgent, once per trip)
    st.setdefault("rail_trips", [])
    st.setdefault("fix_alerted", [])
    for trip in new_trips(L, st):
        if phone.send(rail_text(trip, L, bank), True, now):
            st["rail_trips"].append(trip_id(trip))
            log("rail alert sent: %s" % trip_id(trip))
    # ...and a $10+ engagement of the tracked changes D..J (botdata.fixes, imported here so a failure in it is logged
    # and never stops rules A/B/C above or the reports below)
    try:
        from botdata import fixes as _fixes
        changes = _fixes.report(paths=paths, now=now)
        tot = _fixes.totals(changes)
        for c, ev in new_fix_events(changes, st):
            if phone.send(fix_text(c, ev, tot, bank), True, now):
                st["fix_alerted"].append(fix_id(c, ev))
                log("change alert sent: %s %s" % (fix_id(c, ev), ev["usd"]))
    except Exception:
        log("changes D..J not scored this tick: " + traceback.format_exc().replace("\n", " | ")[-600:])
    # reports
    for n, due_day, title, d0, d1 in REPORTS:
        if st["reports"].get(str(n)):
            continue
        if now < clock.day_start(due_day) + REPORT_AT_S:
            continue
        txt = report_text(n, title, d0, d1, evs, L, start_t, bank)
        if not dry:
            with open(REPORT_TXT % n, "w", encoding="utf-8") as fh:
                fh.write(txt + "\n")
        if phone.send(txt, False, now):
            st["reports"][str(n)] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            log("report %d sent" % n)
    st["last_tick"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    st["running"] = run
    log("tick ok: %d fires (%d scored, %d open), net %s, logs %d" % (run["fires"], run["scored"], run["open"],
                                                                      usd(run["net"]), len(L.starts)))
    if not dry:
        save_state(st)


# ---------------------------------------------------------------------------
def self_test(log_path):
    """11-01's HYPE 9:15 AM and NEAR 9:30 AM replayed as if the rules had been on, plus a synthetic flip."""
    rows = [json.loads(l) for l in open(log_path, encoding="utf-8", errors="replace")
            if ("KXHYPE15M-26NOV010915-15" in l or "KXNEAR15M-26NOV010930-30" in l)]
    ok = True

    def check(name, got_, lo, hi):
        nonlocal ok
        good = got_ is not None and lo <= got_ <= hi
        ok = ok and good
        print("%s %-58s %s (expect %s..%s)" % ("PASS" if good else "FAIL", name, got_, lo, hi))

    # HYPE: drop the 41 topup, its settled leg, the 41-contract hedge and its leg; add the refusal at the topup signal
    hy = [r for r in rows if r.get("ticker") == "KXHYPE15M-26NOV010915-15"]
    sig = next(r for r in hy if r.get("kind") == "signal" and r.get("leg") == "topup")
    keep = []
    for r in hy:
        if r.get("kind") == "order" and r.get("leg") == "topup":
            continue
        if r.get("kind") == "settled" and abs((r.get("cost") or 0) - 0.9364) < 1e-4:
            continue
        if r.get("kind") == "hedge" and abs((r.get("price") or 0) - 0.988) < 1e-4:
            continue
        if r.get("kind") == "settled" and abs((r.get("cost") or 0) - 0.988) < 1e-4:
            continue
        keep.append(r)
    keep.append(dict(kind="refused", gate="ws_later_fall", ticker=sig["ticker"], close_s=1793542500, want="no",
                     leg="topup", tau=7, price=0.86, size=41.0, would_n=41.0, limit=0.98, ladder=sig["ladder"],
                     spot=sig["spot"], strike=sig["strike"], fall_c=24.0, held_n=4.0, t=sig["t"]))
    # NEAR: drop the 72-contract jump hedge and its leg; add the jump_capped record
    ne = [r for r in rows if r.get("ticker") == "KXNEAR15M-26NOV010930-30"]
    h = next(r for r in ne if r.get("kind") == "hedge" and r.get("status") == "executed")
    keep += [r for r in ne if not (r.get("kind") == "hedge" or
                                   (r.get("kind") == "settled" and r.get("want") == "yes"))]
    keep.append(dict(kind="jump_capped", ticker=h["ticker"], close_s=1793543400, want="no", n=72.12, jump_sd=8.32,
                     belief=0.81632, tau=33, side="yes", ask=h.get("ask"), ask_size=h.get("ask_size"),
                     ladder=[[h.get("ask"), h.get("ask_size")],
                             [round(h.get("ask") + 0.01, 3), max(0.0, (h.get("ladder_n") or 0) - (h.get("ask_size") or 0))]],
                     limit=round(h.get("ask") + 0.10, 3),
                     t=h["t"]))
    # synthetic flip: jump hedge at 10c x 50 skipped; pin's own belief hedge later at 60c x 50; bet lost
    keep += [dict(kind="settled", ticker="KXTEST15M-26NOV011000-00", want="no", result="yes", cost=0.97, pnl_c=-4985,
                  t="2026-11-01T15:00:20Z"),
             dict(kind="hedge", status="executed", ticker="KXTEST15M-26NOV011000-00", side="yes", price=0.60, n=50.0,
                  asked=50.0, ladder_n=50.0, limit_sent=0.70, t="2026-11-01T14:59:50Z"),
             dict(kind="settled", ticker="KXTEST15M-26NOV011000-00", want="yes", result="yes", cost=0.60, pnl_c=1916,
                  t="2026-11-01T15:00:35Z"),
             dict(kind="jump_capped", ticker="KXTEST15M-26NOV011000-00", close_s=1793545200, want="no", n=50.0,
                  jump_sd=9.0, belief=0.85, tau=25, side="yes", ask=0.10, ask_size=80.0, ladder=[[0.10, 80.0]],
                  limit=0.20, t="2026-11-01T14:59:35Z"),
             # synthetic bigger hedge (the 11-02 ZEC shape): bet No 297 @94.5c lost; the extra 297 Yes @14c won
             dict(kind="hedge_extra", status="executed", ticker="KXTESTX15M-26NOV011015-15", side="yes", price=0.14,
                  n=297.0, asked=297.0, extra_of=297.0, mult=2.0, base_n=297.0, tau=18, belief=0.342, trigger="belief",
                  order_id="x-1", live=True, t="2026-11-01T15:14:42Z"),
             dict(kind="settled", ticker="KXTESTX15M-26NOV011015-15", want="no", result="yes", cost=0.9446,
                  pnl_c=-28163, t="2026-11-01T15:15:20Z"),
             # v-fixes-alerts: this log is the current run (a start record), and the HYPE 10-31 7:30 AM rail trip shape:
             # the boosted Yes won, the 7.1c No hedge leg lost $1.59 and switched the band boost off ("any" rail)
             dict(kind="start", t="2026-11-01T14:00:00Z", code_sha="selftest0000", pid=0, live=True),
             dict(kind="settled", ticker="KXTESTR15M-26NOV011030-30", want="yes", result="yes", cost=0.98, pnl_c=39.08,
                  market_net_c=None, t="2026-11-01T15:30:20Z"),
             dict(kind="settled", ticker="KXTESTR15M-26NOV011030-30", want="no", result="yes", cost=0.071,
                  pnl_c=-158.65, market_net_c=-119.57, t="2026-11-01T15:30:35Z"),
             dict(kind="band_boost_off", ticker="KXTESTR15M-26NOV011030-30", close_s=calendar.timegm((2026, 11, 1, 15, 30, 0)),
                  cost=0.071, pnl_c=-158.65, was=None, t="2026-11-01T15:30:35Z")]
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "pinrun-live-test.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for r in keep:
            fh.write(json.dumps(r) + "\n")
    L = Logs([p])
    evs = {e["ticker"].split("-")[0]: e for e in score_events(L, time.time())}
    hy_e, ne_e, fl_e, cx_e = evs.get("KXHYPE15M"), evs.get("KXNEAR15M"), evs.get("KXTEST15M"), evs.get("KXTESTX15M")
    print("HYPE:", json.dumps({k: hy_e.get(k) for k in ("n", "px", "buy", "hedge", "extra_hedge_n", "extra_hedge_px",
                                                       "effect", "effect_usual", "ratio")}))
    print("NEAR:", json.dumps({k: ne_e.get(k) for k in ("n", "px", "jump_hedge", "real_hedge", "effect")}))
    print("FLIP:", json.dumps({k: fl_e.get(k) for k in ("n", "px", "jump_hedge", "real_hedge", "effect")}))
    print("EXTRA:", json.dumps({k: cx_e.get(k) for k in ("n", "px", "side", "want", "mult", "effect", "id")}))
    check("HYPE 9:15 AM later-buy refusal SAVED (buy ~-38.5, hedge back ~3)", hy_e["effect"], 33.0, 39.0)
    check("NEAR 9:30 AM jump cap SAVED the hedge cost", ne_e["effect"], 12.0, 12.5)
    check("synthetic flip: jump cap GAVE UP (60c hedge vs 10c)", fl_e["effect"], -25.6, -25.4)
    check("synthetic bigger hedge: 297 extra Yes at 14c on a flip MADE ~$252.9", cx_e["effect"], 252.5, 253.5)
    run = totals(list(evs.values()))
    tot4 = round(hy_e["effect"] + ne_e["effect"] + fl_e["effect"] + cx_e["effect"], 2)
    check("running net = sum of the four", round(run["net"], 2), tot4 - 0.001, tot4 + 0.001)
    # v-fixes-alerts (1): the band rail trip in the current run -> one urgent alert, said once
    st = {"rail_trips": []}
    trips = new_trips(L, st)
    check("rail: the band_boost_off in the current run is due once", len(trips), 1, 1)
    rt = rail_text(trips[0], L, 2628.63) if trips else ""
    print()
    print(rt)
    want_rt = ("PIN BAND BOOST OFF", "TESTR 10:30 AM market", "at 10:30 AM ET a No leg bought at 7.1c lost $1.59",
               "(-0.06% of the bank)", "the whole market net -$1.20", "1x instead of 1.5x", "/approve pinrestart")
    check("rail text: the boost, the market, the leg and its $, the remedy (%d phrases)" % len(want_rt),
          sum(1 for w in want_rt if w in rt), len(want_rt), len(want_rt))
    if trips:
        st["rail_trips"].append(trip_id(trips[0]))
    check("rail: alerted once, never twice", len(new_trips(L, st)), 0, 0)
    p3 = os.path.join(d, "pinrun-live-20261102T000000Z.jsonl")      # a NEWER run (its start record alone)
    with open(p3, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(kind="start", t="2026-11-02T00:00:00Z", code_sha="selftest0001", pid=0, live=True)) + "\n")
    check("rail: a trip in an EARLIER run is not alerted once a newer run has started",
          len(new_trips(Logs([p, p3]), {"rail_trips": []})), 0, 0)
    # v-fixes-alerts (2): a synthetic new-build log where change I (max positions 5) let two buys through: one made
    # $12.00 (alerted), one made $5.00 (under the $10 line)
    tkI, tkI2 = "KXTESTI15M-26NOV051000-00", "KXTESTI15M-26NOV051015-15"
    rows2 = [dict(kind="start", t="2026-11-05T13:40:00Z", code_sha="0925t0000000", pid=1, live=True, max_positions=5),
             dict(kind="open_cap_relaxed", ticker=tkI, close_s=calendar.timegm((2026, 11, 5, 15, 0, 0)), side="no",
                  open_positions=3, old_cap=3, leg="main", live=True, t="2026-11-05T14:59:40Z"),
             dict(kind="order", ticker=tkI, want="no", leg="main", filled=40.0, exec_price=0.70, limit_sent=0.72,
                  status="executed", t="2026-11-05T14:59:41Z"),
             dict(kind="settled", ticker=tkI, want="no", result="no", cost=0.70, pnl_c=1200.0, t="2026-11-05T15:00:20Z"),
             dict(kind="open_cap_relaxed", ticker=tkI2, close_s=calendar.timegm((2026, 11, 5, 15, 15, 0)), side="yes",
                  open_positions=4, old_cap=3, leg="main", live=True, t="2026-11-05T15:14:40Z"),
             dict(kind="order", ticker=tkI2, want="yes", leg="main", filled=20.0, exec_price=0.75, limit_sent=0.77,
                  status="executed", t="2026-11-05T15:14:41Z"),
             dict(kind="settled", ticker=tkI2, want="yes", result="yes", cost=0.75, pnl_c=500.0, t="2026-11-05T15:15:20Z")]
    p2 = os.path.join(d, "pinrun-live-20261105T134000Z.jsonl")
    with open(p2, "w", encoding="utf-8") as fh:
        for r in rows2:
            fh.write(json.dumps(r) + "\n")
    from botdata import fixes as FX
    ch = FX.report(paths=[p2], now=float(calendar.timegm((2026, 11, 5, 16, 0, 0))))
    chI = next(c for c in ch if c["id"] == "I")
    check("change I (max positions 5): engaged twice, net +$17.00", chI["net_usd"], 16.99, 17.01)
    st2 = {"fix_alerted": []}
    due = new_fix_events(ch, st2)
    check("one $10+ engagement is due (the $5.00 one is under the line)", len(due), 1, 1)
    ft = fix_text(due[0][0], due[0][1], FX.totals(ch), 2628.63) if due else ""
    print()
    print(ft)
    want_ft = ("PIN CHANGE MADE $12.00 (+0.46% of the bank)", "I max positions 5", "TESTI", "Nov 5 9:59 AM ET",
               "40 contracts filled at 70.0c", "the leg made $12.00", "up to 5 positions open at once (was 3)",
               "engaged 2 times", "net +$17.00", "/fixes")
    check("change text: verb and $, the change, the coin, the time, what happened, the total (%d phrases)" % len(want_ft),
          sum(1 for w in want_ft if w in ft), len(want_ft), len(want_ft))
    if due:
        st2["fix_alerted"].append(fix_id(*due[0]))
    check("change alert once, never twice", len(new_fix_events(ch, st2)), 0, 0)
    # v-cheapwin (3): change K (cheap morning skip): a skipped BNB 8:15 AM No buy whose shadow FLIPPED (the buy would
    # have lost $112.58 with its hedge) is a SAVED alert; a skip whose shadow won $1.08 is under the line
    tkK, tkK2 = "KXBNB15M-26NOV070815-15", "KXETH15M-26NOV070730-30"
    rowsK = [dict(kind="start", t="2026-11-07T12:00:00Z", code_sha="0925u0000000", pid=1, live=True,
                  cheap_window=[6.0, 10.0, 0.98]),
             dict(kind="refused", gate="cheap_window", ticker=tkK, close_s=calendar.timegm((2026, 11, 7, 13, 15, 0)),
                  want="no", leg="early", tau=45, price=0.97, n_ask=193.81, px=0.97287, t="2026-11-07T13:14:15Z"),
             dict(kind="cheap_window_settled", ticker=tkK, close_s=calendar.timegm((2026, 11, 7, 13, 15, 0)),
                  result="yes", won=False, want="no", n_ask=193.81, px=0.97287, hedge_px=0.70, hedge_mult=1.25,
                  t="2026-11-07T13:15:40Z"),
             dict(kind="refused", gate="cheap_window", ticker=tkK2, close_s=calendar.timegm((2026, 11, 7, 12, 30, 0)),
                  want="yes", leg="full", tau=20, price=0.975, n_ask=50.0, px=0.975, t="2026-11-07T12:29:40Z"),
             dict(kind="cheap_window_settled", ticker=tkK2, close_s=calendar.timegm((2026, 11, 7, 12, 30, 0)),
                  result="yes", won=True, want="yes", n_ask=50.0, px=0.975, hedge_px=None, t="2026-11-07T12:30:45Z")]
    pK = os.path.join(d, "pinrun-live-20261107T120000Z.jsonl")
    with open(pK, "w", encoding="utf-8") as fh:
        for r in rowsK:
            fh.write(json.dumps(r) + "\n")
    chK = FX.report(paths=[pK], now=float(calendar.timegm((2026, 11, 7, 19, 0, 0))))
    dueK = new_fix_events(chK, {"fix_alerted": []})
    check("change K: one $10+ engagement is due (the skip that flipped; the $1.08 one is under the line)", len(dueK), 1, 1)
    ftK = fix_text(dueK[0][0], dueK[0][1], FX.totals(chK), 3308.36) if dueK else ""
    print()
    print(ftK)
    want_ftK = ("PIN CHANGE SAVED $112.58", "K cheap morning skip", "BNB", "Nov 7 8:14 AM ET", "FLIPPED",
                "would have lost $112.58", "no first buy under 98.0c", "/fixes")
    check("change K text: SAVED and $, the change, the coin, the time, what happened (%d phrases)" % len(want_ftK),
          sum(1 for w in want_ftK if w in ftK), len(want_ftK), len(want_ftK))
    # call B (4): change M (3rd bet blocked): a full DOGE buy the 2-bet budget held to 50 where the old argv's third bet
    # had room for 100 more; the bet LOST, so the 100 x 97.8c + fee 0.16 not spent is a SAVED $97.96 alert; the true
    # 3rd bet under its net (c["third"]) never alerts
    tkM0, tkM = "KXBNB15M-26NOV081800-00", "KXDOGE15M-26NOV081800-00"
    csM = calendar.timegm((2026, 11, 8, 23, 0, 0))
    rowsM = [dict(kind="start", t="2026-11-08T21:00:00Z", code_sha="d51b131b55cf", pid=1, live=True, extra_coin=0.0,
                  late_extra=0.0, late_extra_tau=15, bank_brake=4.5, size=20.0, band_mults=[[0.955, 0.981, 1.5]]),
             dict(kind="autosize", t="2026-11-08T21:00:01Z", old=20.0, new=100.0),
             dict(kind="order", t="2026-11-08T22:59:40Z", ticker=tkM0, want="yes", leg="full", filled=150.0, exec_price=0.98,
                  limit_sent=0.98, tau_at_send=20, status="executed", body={"count": "150.00"}, client_order_id="pin-1"),
             dict(kind="signal", t="2026-11-08T22:59:52Z", live=True, ticker=tkM, want="yes", price=0.978, tau=8, size=500.0,
                  take_n=50.0, leg="full", budget_left=50.0, fair=0.9999, ladder=[[0.978, 500.0]]),
             dict(kind="order", t="2026-11-08T22:59:52Z", ticker=tkM, want="yes", leg="full", filled=50.0, exec_price=0.978,
                  limit_sent=0.98, tau_at_send=8, status="executed", body={"count": "50.00"}, client_order_id="pin-2"),
             dict(kind="refused", gate="close_budget", t="2026-11-08T22:59:53Z", ticker="KXETH15M-26NOV081800-00", close_s=csM,
                  size_now=100.0, spent=200.0, budget=200.0, base=200.0, extra_coin=0.0, tau=7, size=100.0, budget_left=0.0),
             dict(kind="settled", t="2026-11-08T23:00:20Z", ticker=tkM0, want="yes", result="yes", cost=0.98, pnl_c=300.0),
             dict(kind="settled", t="2026-11-08T23:00:20Z", ticker=tkM, want="yes", result="no", cost=0.978, pnl_c=-4890.0)]
    pM = os.path.join(d, "pinrun-live-20261108T210000Z.jsonl")
    with open(pM, "w", encoding="utf-8") as fh:
        for r in rowsM:
            fh.write(json.dumps(r) + "\n")
    chM = FX.report(paths=[pM], now=float(calendar.timegm((2026, 11, 9, 0, 40, 0))))
    cM = next(c for c in chM if c["id"] == "M")
    check("change M (3rd bet blocked): one held-back buy, net +$97.96, one refusal under it unpriced (no trajectory log)",
          cM["net_usd"] if (cM["engaged"] == 1 and cM["third"] == [] and "1 close hit the budget" in cM["extra"][1]) else -1,
          97.95, 97.97)
    dueM = new_fix_events(chM, {"fix_alerted": []})
    check("change M: one $10+ engagement is due", len(dueM), 1, 1)
    ftM = fix_text(dueM[0][0], dueM[0][1], FX.totals(chM), 2800.0) if dueM else ""
    print()
    print(ftM)
    want_ftM = ("PIN CHANGE SAVED $97.96", "M 3rd bet blocked", "DOGE", "Nov 8 5:59 PM ET", "held to the 2-bet budget",
                "the bet LOST, so holding them back saved $97.96", "a close spends 2 bets, never a 3rd", "/fixes")
    check("change M text: SAVED and $, the change, the coin, the time, what happened (%d phrases)" % len(want_ftM),
          sum(1 for w in want_ftM if w in ftM), len(want_ftM), len(want_ftM))
    rt = rt + ftK + ftM                              # the em-dash check below reads these alerts too
    check("no em dash in any alert text", (chr(0x2014) in rt) or (chr(0x2014) in ft), False, False)
    print()
    print(alert_text(hy_e, run, 2628.63))
    print()
    print(alert_text(fl_e, run, 2628.63))
    print()
    print(alert_text(cx_e, run, 2628.63))
    print()
    print(report_text(1, "end of Sun Nov 1 (day 1)", "2026-11-01", "2026-11-01", list(evs.values()), L,
                      "2026-11-01T14:00:00Z", 2628.63))
    print("\nSELF-TEST", "PASSED" if ok else "FAILED")
    return ok


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--self-test" in argv:
        i = argv.index("--log") if "--log" in argv else -1
        lp = argv[i + 1] if i >= 0 else os.path.join(RESULTS, "pinrun-live-20261031T101116Z.jsonl")
        return 0 if self_test(lp) else 1
    if "--test-send" in argv:
        ph = Phone()
        ok = ph.send("🧪 TEST from the pin rules watcher (pinrules_watch.py). Nothing happened in trading. From now on "
                     "it scores every fire of the two new pin rules, alerts on anything over $10, and sends 4 "
                     "reports: 12:05 AM ET on Nov 2, Nov 3, Nov 4 and Nov 8.", False, time.time())
        log("test message %s" % ("sent" if ok else "NOT sent"))
        return 0 if ok else 1
    try:
        tick(dry="--dry" in argv)
    except Exception:
        log("tick failed: " + traceback.format_exc().replace("\n", " | ")[-1500:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
