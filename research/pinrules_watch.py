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

v-undo-alerts (2026-11-14; the operator, the day pin's undo v-undo1114 went live: "make sure each is being tracked and
what reverting gives up. I want to know if a loss ever comes that would've been prevented by any of these rules, I also
want to know how much more each rules being reverted earns me"). The undo switched off M (the 3rd-bet block), K (the
6-10 AM cheap-buy skip) and WS (the wrong-side skip) and dropped B's cap (the jump hedge only shadows: no money).
botdata.fixes scores each undo against KEEPING its rule (row["undo"]: its events, + = the undo made money; M a 3rd
bet's own contracts, K and WS a whole market). Two more messages from the same tick:
  * A LOSS A REVERTED RULE WOULD HAVE STOPPED: every (rule, market) whose undo events have all settled with money under
    $0, of ANY size: ONE message (state key "undo_alerted", kept across ticks and restarts), the market, its $, the
    rule in plain words, what happened, and the rule's net since the undo vs keeping it. It is said only once its
    money reads the SAME on two ticks in a row (state key "undo_pending": {id: $ at the last tick}): pinrun books a
    market's legs (buy, hedge, extra) up to ~45 s apart, and a tick between them would say a part of the money (an
    -$281 that ends -$28, or a 'loss' that ends up), once and never corrected. A market is its coin and its
    close (an undo event's order time rounded up to the quarter hour, or the hour for an hourly market): M's several
    orders past the budget in one market are one message. More than UNDO_BURST new ones in one tick (a late start, an
    outage): one message listing them.
  * THE DAILY LINE: the first tick after 9 PM ET (UNDO_DAILY_AT_S, wall clock: undo_daily_at), once per ET day (state key "undo_daily"; a late
    tick sends the last day due, never an older one, never twice): each reverted rule's running total since the undo
    vs keeping it (bets or markets, won / lost / open, $, the day's part) and the sum, "how much more reverting earned
    (or cost)". A day with nothing new still sends it ($0 / no bets): the operator sees the watch is alive.
  A Telegram failure stops the tick's undo sends (each is tried again next tick): the task kills a run at 4 minutes,
  and a run killed after a send but before the state is saved would send that message twice.
  QUIET HOURS (the phone's rule, phone/quiet.py, read from the same telegram.json "quiet_hours", default 11 PM to 7
  AM ET, "off" = none): while quiet only an URGENT message goes (a loss of $50+ or 3%+ of the bank: quiet.loss_is_urgent,
  the phone's own line for a single loss), with sound. Any other new message is HELD in the state file (state key
  "held", so a restart in the night loses nothing) and goes as ONE message at the first tick after quiet hours end; a
  held message is already counted as said, so it is never repeated. MUTE: the phone's /mute is a flag in the phone
  process's memory, never written anywhere this process could read: the watcher has never followed it (nor do its other
  alerts) and cannot.

  python research\pinrules_watch.py              one tick
  python research\pinrules_watch.py --dry        one tick, print instead of sending, state not saved
  python research\pinrules_watch.py --self-test [--log PATH]   the scorer on 11-01's HYPE and NEAR + a synthetic flip,
                                                 a synthetic band rail trip and a synthetic $12 engagement of change I,
                                                 and v-undo-alerts on a planted undo log (a loss alerts once, a win
                                                 never, the daily line once an ET day, quiet hours hold and release)
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
# v-undo-alerts: the rules the 11-14 undo reverted (botdata.fixes rows with row["undo"]), in plain words
UNDO_IDS = ("M", "K", "WS")
UNDO_NAME = {"M": "3rd-bet block", "K": "6-10 AM cheap-buy skip", "WS": "wrong-side skip"}
UNDO_STOP = {"M": "would have kept that bet out", "K": "would have skipped that market",
             "WS": "would have skipped that market"}
UNDO_UNIT = {"M": "bet", "K": "market", "WS": "market"}    # what one undo event is (fixes.undo_counted's words)
UNDO_ON = {"M": "_m_on", "K": "_k_on", "WS": "_ws_on"}     # fixes' test of a start record: is the rule on there?
UNDO_DAILY_AT_S = 21 * 3600               # the daily line: the first tick from 9 PM ET on, once per ET day
UNDO_BURST = 4                            # more new losses than this in one tick: one message listing them
LOSS_URGENT_USD = 50.0                    # phone/quiet.py's line for a single loss (used only if it cannot be imported)
LOSS_URGENT_FRAC = 0.03


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
# v-undo-alerts (2026-11-14): the reverted rules M, K, WS against KEEPING them (botdata.fixes row["undo"])
def undo_rows(changes):
    """{id: row} of the undone rules (M, K, WS rows whose undo is scored), in UNDO_IDS order."""
    by = {c.get("id"): c for c in (changes or [])}
    return {k: by[k] for k in UNDO_IDS if by.get(k) and by[k].get("undo")}


def undo_close(ev):
    """The close epoch of the market an undo event is in: its order's time rounded up to the next quarter hour (a
    15-minute coin) or the next hour (an hourly market, coin '<X> hourly'). pin buys only before a close, and the
    order's time alone fixes it, so the same market gets the same close at every tick. None when the event has no
    time."""
    e = ev.get("epoch")
    if e is None:
        e = epoch(ev.get("t"))
    if e is None:
        return None
    step = 3600 if str(ev.get("coin") or "").endswith(" hourly") else 900
    return (int(e) // step + 1) * step


def undo_loss_id(cid, coin, close):
    return "undo|%s|%s|%d" % (cid, coin, close)


def undo_markets(row):
    """[(close, coin, [events])] of an undone row's undo events, one entry a market, in close order."""
    g = {}
    for ev in (row.get("undo") or {}).get("events") or []:
        cl = undo_close(ev)
        if cl is not None:
            g.setdefault((cl, ev.get("coin") or "?"), []).append(ev)
    return [(cl, coin, evs) for (cl, coin), evs in sorted(g.items())]


def undo_settled_usd(evs):
    """The money of a market's undo events once EVERY one has settled (None while any is open)."""
    if not evs or any(e.get("open") or e.get("usd") is None for e in evs):
        return None
    return round(sum(e["usd"] for e in evs), 2)


def undo_losses(changes):
    """Every (rule, market) of the undos settled with money under $0 (any size: a loss the rule would have stopped):
    [{row, id, close, coin, usd, events}] in close order."""
    out = []
    for cid, c in undo_rows(changes).items():
        for cl, coin, evs in undo_markets(c):
            x = undo_settled_usd(evs)
            if x is not None and x <= -0.005:
                out.append(dict(row=c, id=undo_loss_id(cid, coin, cl), close=cl, coin=coin, usd=x, events=evs))
    out.sort(key=lambda x: (x["close"], x["id"]))
    return out


def new_undo_losses(changes, st):
    """undo_losses not yet said (sent, or held by quiet hours: state key "undo_alerted") whose money reads the same as
    at the last tick (state key "undo_pending", {id: $}, updated here): a market read between its legs' bookings is
    held back one tick, and one whose money ends at $0 or up drops out unsaid."""
    seen = set(st.get("undo_alerted") or [])
    cand = [x for x in undo_losses(changes) if x["id"] not in seen]
    last = st.get("undo_pending") or {}
    st["undo_pending"] = {x["id"]: x["usd"] for x in cand}
    return [x for x in cand if last.get(x["id"]) is not None and abs(float(last[x["id"]]) - x["usd"]) < 0.005]


def loss_urgent(x, bank):
    """The phone's line for a single loss (phone/quiet.py loss_is_urgent: $50+ or 3%+ of the bank): rings in the quiet
    hours; any smaller loss waits for their end."""
    try:
        from phone import quiet as Q
        return bool(Q.loss_is_urgent(x, bank))
    except Exception:
        loss = -float(x or 0.0)
        return loss >= LOSS_URGENT_USD or (bool(bank) and loss >= LOSS_URGENT_FRAC * float(bank))


def undo_total(rows):
    return round(sum(float(c["undo"].get("net_usd") or 0.0) for c in rows.values()), 2)


def undo_market_words(coin, close, now):
    """'ETH 3:15 PM' (its day too when it closed on another ET day than now)."""
    other_day = clock.et_day(close) != clock.et_day(now)
    return "%s %s" % (coin, clock.et_clock(close, with_day=other_day).replace(" ET", ""))


def undo_event_words(ev):
    """An undo event's words without fixes' 'since the undo (vs keeping it): ' lead."""
    w = str(ev.get("words") or "")
    i = w.find("): ")
    return w[i + 3:] if w.startswith("since the undo") and i >= 0 else w


def undo_net_line(c, bank):
    """'Since the undo (Nov 14 4:54 PM ET), M's net vs keeping the rule: +$18.40 (+0.46% of the bank) on 6 bets.'"""
    from botdata import fixes as _fixes
    u = c["undo"]
    x = float(u.get("net_usd") or 0.0)
    return "Since the undo (%s), %s's net vs keeping the rule: %s%s %s." % (
        u.get("since") or "?", c["id"], usd(x), pct(x, bank), _fixes.undo_counted(c))


def undo_sum_line(rows, bank):
    x = undo_total(rows)
    return "All %d reverted rules vs keeping them: %s%s · /fixes lists every one" % (len(rows), usd(x), pct(x, bank))


def undo_loss_text(x, changes, bank, now):
    """ONE loss a reverted rule would have stopped, in plain words."""
    c = x["row"]
    cid = c["id"]
    evs = sorted(x["events"], key=lambda e: e.get("epoch") or 0)
    t0 = evs[0].get("epoch") or x["close"]
    return "\n".join([
        "⚠️ Loss a reverted rule would have stopped: %s %s%s -- the %s (%s) %s." % (
            undo_market_words(x["coin"], x["close"], now), usd(x["usd"]), pct(x["usd"], bank), UNDO_NAME[cid], cid,
            UNDO_STOP[cid]),
        "What happened (%s): %s." % (clock.et_clock(t0, with_day=clock.et_day(t0) != clock.et_day(now)),
                                     "; then ".join(undo_event_words(e) for e in evs)),
        undo_net_line(c, bank),
        undo_sum_line(undo_rows(changes), bank)])


def undo_burst_text(new, changes, bank, now):
    """More than UNDO_BURST new losses in one tick (a late start, an outage): ONE message listing them."""
    rows = undo_rows(changes)
    tot = round(sum(x["usd"] for x in new), 2)
    lines = ["⚠️ %d losses reverted rules would have stopped, found at once: %s%s" % (
        len(new), usd(tot), pct(tot, bank))]
    for x in new:
        cid = x["row"]["id"]
        lines.append(" • %s %s -- the %s (%s) %s" % (undo_market_words(x["coin"], x["close"], now), usd(x["usd"]),
                                                     UNDO_NAME[cid], cid, UNDO_STOP[cid]))
    lines += [undo_net_line(rows[cid], bank) for cid in rows if any(x["row"]["id"] == cid for x in new)]
    lines.append(undo_sum_line(rows, bank))
    return "\n".join(lines)


def undo_daily_at(d):
    """9 PM ET on day `d` by the wall clock: the next ET midnight less 3 h (the clocks change at 2 AM, never between
    9 PM and midnight, so this is 9 PM on the two change days too, where midnight + 21 h is 8 or 10 PM)."""
    return clock.day_start(clock.shift_day(d, 1)) - (24 * 3600 - UNDO_DAILY_AT_S)


def undo_daily_due(st, now, since_t):
    """The ET day whose daily line is due (the last day whose 9 PM has passed, from the undo's day on), or None when
    it has gone (or been held) already."""
    if since_t is None:
        return None
    d = clock.et_day(now)
    if now < undo_daily_at(d):
        d = clock.shift_day(d, -1)
    if d < clock.et_day(since_t) or d in (st.get("undo_daily") or {}):
        return None
    return d


def undo_rule_on(cid, start):
    """True when pin's latest start record has rule `cid` back on (fixes' own test of a start record)."""
    try:
        from botdata import fixes as _fixes
        fn = getattr(_fixes, UNDO_ON[cid], None)
        return bool(start) and bool(fn and fn(start))
    except Exception:
        return False


def undo_daily_text(changes, day, bank, now, start=None):
    """The daily line: each reverted rule's running total since the undo vs keeping it, the day's part, the sum."""
    rows = undo_rows(changes)
    start = start or {}
    since_t = min(float(c["undo"].get("since_t") or now) for c in rows.values())
    n_day = clock.days_between(clock.et_day(since_t), day)            # inclusive: 1 on the undo's own day
    late = now >= clock.day_start(clock.shift_day(day, 1))
    lines = ["📊 REVERTED PIN RULES · end of %s (day %d since the undo)%s" % (
                 clock.day_label(day), n_day, (" · sent late, %s" % clock.et_clock(now)) if late else ""),
             "Each against KEEPING the rule, since the undo (%s); + = reverting earned more:" % clock.et_clock(since_t)]
    n_all = open_all = 0
    for cid, c in rows.items():
        u = c["undo"]
        evs = u.get("events") or []
        unit = UNDO_UNIT[cid]
        x = float(u.get("net_usd") or 0.0)
        won = sum(1 for e in evs if e.get("usd") is not None and e["usd"] > 0.004)
        lost = sum(1 for e in evs if e.get("usd") is not None and e["usd"] < -0.004)
        opn = sum(1 for e in evs if e.get("open"))
        even = len(evs) - won - lost - opn
        n_all += len(evs)
        open_all += opn
        if not evs:
            body = "no %ss yet · $0.00" % unit
        else:
            body = "%d %s%s · %d won, %d lost%s%s · %s%s" % (
                len(evs), unit, "" if len(evs) == 1 else "s", won, lost, (", %d even" % even) if even else "",
                (", %d open" % opn) if opn else "", usd(x), pct(x, bank))
            today = [e for e in evs if e.get("usd") is not None and undo_close(e) is not None
                     and clock.et_day(undo_close(e)) == day]
            body += (" · that day %s on %d" % (usd(round(sum(e["usd"] for e in today), 2)), len(today))) if today \
                else " · nothing new that day"
        back = " (BACK ON at pin's latest start: its total no longer moves)" if undo_rule_on(cid, start) else ""
        lines.append(" • %s (%s)%s: %s" % (UNDO_NAME[cid][:1].upper() + UNDO_NAME[cid][1:], cid, back, body))
    tot = undo_total(rows)
    on = ("on %d bet%s and market%s%s" % (n_all, "" if n_all == 1 else "s", "" if n_all == 1 else "s",
                                           (" · %d open" % open_all) if open_all else "")) if n_all \
        else "nothing has come up for any of them yet"
    if tot > 0.004:
        lines.append("All %d: reverting has EARNED %s%s more than keeping them would have, %s." % (
            len(rows), usd(tot), pct(tot, bank), on))
    elif tot < -0.004:
        lines.append("All %d: reverting has COST %s%s against keeping them, %s." % (
            len(rows), usd(-tot, False), pct(tot, bank), on))
    else:
        lines.append("All %d: reverting has made no difference yet ($0.00), %s." % (len(rows), on))
    ls = undo_losses(changes)
    if ls:
        lt = round(sum(x["usd"] for x in ls), 2)
        lines.append("Losses a reverted rule would have stopped since the undo: %d, %s%s, each sent when it settled." % (
            len(ls), usd(lt), pct(lt, bank)))
    else:
        lines.append("No loss yet that a reverted rule would have stopped.")
    b = next((c for c in changes if c.get("id") == "B"), None)
    if b and b.get("dropped"):
        if start.get("hedge_jump") in (None, 0, 0.0) and start.get("hedge_jump_shadow"):
            lines.append("The jump cap (B) was dropped too (%s): the jump hedge only shadows (it sends nothing), so the "
                         "cap moves no money." % b["dropped"])
        else:
            lines.append("The jump cap (B) was dropped (%s) and the jump hedge is LIVE: what the missing cap does is not "
                         "priced here." % b["dropped"])
    lines.append("/fixes lists every one")
    return "\n".join(lines)


def undo_send(phone, st, key, text, urgent, now, say=None):
    """Send now, or HOLD while the phone's quiet hours run and the message is not urgent (phone/quiet.py: only urgent
    alerts overnight, the rest when they end; held in the state file, so a restart in the night loses nothing). True:
    sent or held (said; never again). False: Telegram did not take it -- tried again at the next tick."""
    say = say or log
    if not urgent and phone.quiet(now):
        st.setdefault("held", []).append({"t": now, "id": key, "text": text})
        if getattr(phone, "dry", False):
            print("---- HELD by quiet hours (goes at the first tick after them) ----\n%s\n" % text)
        say("held by quiet hours: %s" % key)
        return True
    return bool(phone.send(text, urgent, now))


def held_text(held, phone):
    """What quiet hours held, as ONE message: each as it would have gone, under the time it was held."""
    try:
        from phone import quiet as Q
        span = Q.words(phone.cfg)
    except Exception:
        span = "11 PM to 7 AM ET"
    out = ["🌅 Quiet hours are over (%s): %d message%s held for you (only urgent ones ring then)" % (
        span, len(held), "" if len(held) == 1 else "s")]
    for h in held:
        out += ["", "-- held at %s --" % clock.et_clock(h.get("t")), str(h.get("text") or "")]
    return "\n".join(out)


def flush_held(st, phone, now, say=None):
    """Quiet hours are over (or off): everything held goes as one message. Returns how many went, or None when
    Telegram did not take it (kept for the next tick)."""
    say = say or log
    held = list(st.get("held") or [])
    if not held or phone.quiet(now):
        return 0
    if phone.send(held_text(held, phone), False, now):
        st["held"] = []
        say("held messages sent: %d (%s)" % (len(held), ", ".join(str(h.get("id")) for h in held)[:300]))
        return len(held)
    return None


def undo_watch(changes, st, phone, bank, now, start=None, say=None, failed=None):
    """The tick's v-undo-alerts part. What quiet hours held goes first (even when fixes failed this tick); then each
    new loss a reverted rule would have stopped (once per rule and market) and the daily line (once per ET day).
    `changes`: fixes.report's rows, or None when it failed (`failed`: the error's name) -- then only the held messages,
    and from 10 PM a daily that says it could not score, so a quiet phone never hides a broken watch. The first send
    Telegram does not take ends the tick's undo sends (all are tried again next tick)."""
    say = say or log
    st.setdefault("undo_alerted", [])
    st.setdefault("undo_daily", {})
    st.setdefault("held", [])
    if flush_held(st, phone, now, say) is None:
        say("undo: Telegram did not take the held messages; the undo sends wait for the next tick")
        return
    if changes is None:
        d = undo_daily_due(st, now, st.get("undo_since"))
        if d and now >= undo_daily_at(d) + 3600:
            txt = ("📊 REVERTED PIN RULES · end of %s: NOT SCORED -- the scorer (botdata.fixes) failed (%s); "
                   "results\\pinrules_watch.log has it. The loss alerts come as soon as it scores again." % (
                       clock.day_label(d), failed or "error"))
            if undo_send(phone, st, "daily|" + d, txt, False, now, say):
                st["undo_daily"][d] = "not scored " + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        return
    rows = undo_rows(changes)
    if not rows:
        return
    st["undo_since"] = min(float(c["undo"].get("since_t") or now) for c in rows.values())
    new = new_undo_losses(changes, st)
    if len(new) > UNDO_BURST:
        if not undo_send(phone, st, "burst|%s" % new[0]["id"], undo_burst_text(new, changes, bank, now),
                         any(loss_urgent(x["usd"], bank) for x in new), now, say):
            return
        st["undo_alerted"] += [x["id"] for x in new]
        for x in new:
            st["undo_pending"].pop(x["id"], None)
        say("undo losses sent as one: %d" % len(new))
    else:
        for x in new:
            if not undo_send(phone, st, x["id"], undo_loss_text(x, changes, bank, now), loss_urgent(x["usd"], bank),
                             now, say):
                return
            st["undo_alerted"].append(x["id"])
            st["undo_pending"].pop(x["id"], None)
            say("undo loss said: %s %s" % (x["id"], x["usd"]))
    d = undo_daily_due(st, now, st["undo_since"])
    if d:
        if undo_send(phone, st, "daily|" + d, undo_daily_text(changes, d, bank, now, start), False, now, say):
            st["undo_daily"][d] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            say("undo daily said: %s" % d)


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
        return {"events": {}, "alerted": [], "levels": [], "reports": {}, "rail_trips": [], "fix_alerted": [],
                "undo_alerted": [], "undo_daily": {}, "held": []}


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
    changes, failed = None, None
    try:
        from botdata import fixes as _fixes
        # the tracker's own pin logs (from WS's 10-28 run on, not the rules' window): the alert's total is /fixes's
        changes = _fixes.report(paths=_fixes.pin_paths(), now=now)
        tot = _fixes.totals(changes)
        for c, ev in new_fix_events(changes, st):
            if phone.send(fix_text(c, ev, tot, bank), True, now):
                st["fix_alerted"].append(fix_id(c, ev))
                log("change alert sent: %s %s" % (fix_id(c, ev), ev["usd"]))
    except Exception as e:
        failed = failed or type(e).__name__
        log("changes D..J not scored this tick: " + traceback.format_exc().replace("\n", " | ")[-600:])
    # v-undo-alerts: the reverted rules (M, K, WS) against keeping them -- what quiet hours held, each loss one of them
    # would have stopped (once per rule and market), the daily line after 9 PM ET (its own try: never stops the rest)
    try:
        latest = max(L.starts, key=lambda x: x[0] or "")[1] if L.starts else {}
        undo_watch(changes, st, phone, bank, now, latest, failed=failed)
    except Exception:
        log("reverted rules not watched this tick: " + traceback.format_exc().replace("\n", " | ")[-600:])
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
    # the total is /fixes's: I's +$17.00 and the rows measured once by the 11-14 retro (the ladder's 4 changes, the stops)
    want_ft = ("PIN CHANGE MADE $12.00 (+0.46% of the bank)", "I max positions 5", "TESTI", "Nov 5 9:59 AM ET",
               "40 contracts filled at 70.0c", "the leg made $12.00", "up to 5 positions open at once (was 3)",
               "engaged 2 times", "net %s" % usd(17.0 + sum(p[-1] for p in FX.LAD_PARTS + FX.STOP_PARTS)), "/fixes")
    check("change text: verb and $, the change, the coin, the time, what happened, the total (%d phrases)" % len(want_ft),
          sum(1 for w in want_ft if w in ft), len(want_ft), len(want_ft))
    if due:
        st2["fix_alerted"].append(fix_id(*due[0]))
    check("change alert once, never twice", len(new_fix_events(ch, st2)), 0, 0)
    # v-cheapwin (3): change K (cheap morning skip): a skipped BNB 8:15 AM No buy whose shadow FLIPPED (the buy would
    # have lost $108.18 with its hedge: 193.81 x 0.903 at 97.287c lost, its 1.25x Yes hedge at 70c won; the 11-14 retro's
    # prices) is a SAVED alert; a skip whose shadow won $1.14 (0.909 x 50 x 2.5c) is under the line
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
    want_ftK = ("PIN CHANGE SAVED $108.18", "K cheap morning skip", "BNB", "Nov 7 8:14 AM ET", "FLIPPED",
                "would have lost $108.18", "no first buy under 98.0c", "/fixes")
    check("change K text: SAVED and $, the change, the coin, the time, what happened (%d phrases)" % len(want_ftK),
          sum(1 for w in want_ftK if w in ftK), len(want_ftK), len(want_ftK))
    # call B (4): change M (3rd bet blocked): a full DOGE buy the 2-bet budget held to 50 where the old argv's third bet
    # had room for 100 more (the band boost's one-coin room off the bank pin's band_boost record carries: 1.5 x 100); the
    # bet LOST, so the 100 x 97.8c + fee 0.16 not spent is a SAVED $97.96 alert; the true 3rd bet under its net
    # (c["third"]) never alerts
    tkM0, tkM = "KXBNB15M-26NOV081800-00", "KXDOGE15M-26NOV081800-00"
    csM = calendar.timegm((2026, 11, 8, 23, 0, 0))
    rowsM = [dict(kind="start", t="2026-11-08T21:00:00Z", code_sha="d51b131b55cf", pid=1, live=True, extra_coin=0.0,
                  late_extra=0.0, late_extra_tau=15, bank_brake=4.5, size=20.0, band_mults=[[0.955, 0.981, 1.5]]),
             dict(kind="autosize", t="2026-11-08T21:00:01Z", old=20.0, new=100.0),
             dict(kind="band_boost", t="2026-11-08T22:30:00Z", ticker="KXSOL15M-26NOV081830-30", want="yes", tau=20,
                  price=0.97, mult=1.5, was=100.0, now=150.0, size=100.0, bank=1000.0, hwm=1000.0),
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
    self_test_undo(FX, d, check)                     # v-undo-alerts (its checks count in this self-test's verdict)
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


def self_test_undo(FX, d, check):
    """v-undo-alerts on a planted log of the 11-14 undo (test_fixes.run_u's markets, worked by hand there, plus a losing
    3rd bet and two late-night losses), through undo_watch tick by tick, the state through its JSON file's round trip
    between ticks (a fresh process each tick), a phone that records what it sends, quiet hours 11 PM to 7 AM ET, a
    $6,000 bank (3% = $180, so only $50+ is urgent):
      K   ETH 7:30 AM close, first buy at 97c (under the old window's 98c): the market made +$2.00 -- no alert
      WS  SOL 8:00 AM close, wrong side, mid up 0.2c (K's window too: WS's, the earlier gate): LOST -$50.00 (urgent);
          DOGE 2 PM, wrong side, mid down 1c: +$1.50 -- no alert
      M   XRP 11 AM: 50 past the 2-bet budget (10 at 96c + 40 at 97c), won: +$1.48 -- no alert; XRP 3 PM the same
          shape, LOST: -(9.60 + fee 0.03) - (38.80 + fee 0.09) = -$48.52 (not urgent)
      planted before the 11:30 PM tick: WS DOT 11:15 PM, 10 at 97c, LOST -$9.70 (HELD by quiet hours) and WS LINK
          11:15 PM, 100 at 97c, LOST -$97.00 (urgent: goes at once, with sound)."""
    def R(kind, t, **kw):
        kw.update(kind=kind, t=t)
        return kw

    def usig(t, tk, want, price, tau, wrong=False, rise=None, ladder=None, bl=200.0):
        return R("signal", t, live=True, ticker=tk, want=want, price=price, tau=tau, size=100.0, take_n=100.0,
                 leg="full", budget_left=bl, fair=(0.999 if want == "yes" else 0.001), spot_wrong=wrong,
                 mid_rise_c=rise, ladder=ladder or [[price, 500.0]])

    def uord(t, tk, want, n, px, tau):
        return R("order", t, ticker=tk, want=want, leg="full", tau_at_send=tau, ask_seen=px, filled=n, exec_price=px,
                 limit_sent=0.99, status="executed", body={"count": "%.2f" % n, "ticker": tk})

    def uset(t, tk, want, res, pnl, cost=0.97):
        return R("settled", t, ticker=tk, want=want, result=res, cost=cost, pnl_c=pnl)
    on = dict(code_sha="0925x0000000", extra_coin=0.0, late_extra=0.0, bank_brake=4.5, late_extra_tau=15,
              cheap_window=[6.0, 10.0, 0.98], wrongside_rise_c=1.0, hedge_jump_max=8.0, hedge_jump_shadow=6.0,
              hedge_jump=None, size=100.0)
    off = dict(on, extra_coin=1.0, late_extra=1.0, bank_brake=3.0, cheap_window=None, wrongside_rise_c=0.0,
               hedge_jump_max=None)
    eth, sol, doge = "KXETH15M-26NOV150730-30", "KXSOL15M-26NOV150800-00", "KXDOGE15M-26NOV151400-00"
    btc11, xrp11, btc15, xrp15 = ("KXBTC15M-26NOV151100-00", "KXXRP15M-26NOV151100-00", "KXBTC15M-26NOV151500-00",
                                  "KXXRP15M-26NOV151500-00")
    dot, link = "KXDOT15M-26NOV152315-15", "KXLINK15M-26NOV152315-15"
    lad = [[0.96, 60.0], [0.97, 200.0]]
    rows = [R("start", "2026-11-15T10:00:00Z", **on), R("start", "2026-11-15T11:00:00Z", **off),
            usig("2026-11-15T12:29:40Z", eth, "yes", 0.97, 20), uord("2026-11-15T12:29:40Z", eth, "yes", 100.0, 0.97, 20),
            uset("2026-11-15T12:30:20Z", eth, "yes", "yes", 200.0),
            usig("2026-11-15T12:59:40Z", sol, "yes", 0.97, 20, wrong=True, rise=0.2),
            uord("2026-11-15T12:59:40Z", sol, "yes", 250.0, 0.97, 20),
            uset("2026-11-15T13:00:20Z", sol, "yes", "no", -5000.0),
            uord("2026-11-15T15:59:30Z", btc11, "yes", 150.0, 0.99, 30),
            usig("2026-11-15T15:59:40Z", xrp11, "yes", 0.985, 20, ladder=lad, bl=50.0),
            uord("2026-11-15T15:59:40Z", xrp11, "yes", 100.0, 0.968, 20),
            uset("2026-11-15T16:00:20Z", btc11, "yes", "yes", 150.0),
            uset("2026-11-15T16:00:21Z", xrp11, "yes", "yes", 290.0),
            usig("2026-11-15T18:59:40Z", doge, "no", 0.985, 20, wrong=True, rise=-1.0),
            uord("2026-11-15T18:59:40Z", doge, "no", 50.0, 0.985, 20),
            uset("2026-11-15T19:00:20Z", doge, "no", "no", 150.0),
            uord("2026-11-15T19:59:30Z", btc15, "yes", 150.0, 0.99, 30),
            usig("2026-11-15T19:59:40Z", xrp15, "yes", 0.985, 20, ladder=lad, bl=50.0),
            uord("2026-11-15T19:59:40Z", xrp15, "yes", 100.0, 0.968, 20),
            uset("2026-11-15T20:00:20Z", btc15, "yes", "yes", 150.0),
            uset("2026-11-15T20:00:21Z", xrp15, "yes", "no", -9680.0)]
    late = [usig("2026-11-16T04:14:40Z", dot, "yes", 0.97, 20, wrong=True, rise=0.3),
            uord("2026-11-16T04:14:40Z", dot, "yes", 10.0, 0.97, 20),
            usig("2026-11-16T04:14:41Z", link, "yes", 0.97, 20, wrong=True, rise=0.1),
            uord("2026-11-16T04:14:41Z", link, "yes", 100.0, 0.97, 20),
            uset("2026-11-16T04:15:20Z", dot, "yes", "no", -970.0),
            uset("2026-11-16T04:15:21Z", link, "yes", "no", -9700.0)]
    pU = os.path.join(d, "pinrun-live-20261115T100000Z.jsonl")

    def write(rs):
        with open(pU, "w", encoding="utf-8") as fh:
            for r in rs:
                fh.write(json.dumps(r) + "\n")
    write(rows)

    class TPhone(Phone):
        """The phone path with Telegram replaced: what it would send, and whether it rang (urgent)."""

        def __init__(self):
            self.dry, self.log, self.cfg, self.sent, self.up = False, (lambda m: None), {"quiet_hours": [23, 7]}, [], True

        def send(self, text, urgent, now):
            if not self.up:
                return False
            self.sent.append((text, bool(urgent), now))
            return True
    ph, said, box = TPhone(), [], {"st": {}}

    def utick(mo, dd, hh, mi):
        """One tick at 2026-mo-dd hh:mi UTC."""
        now = float(calendar.timegm((2026, mo, dd, hh, mi, 0)))
        ch = FX.report(paths=[pU], now=now)
        n0 = len(ph.sent)
        undo_watch(ch, box["st"], ph, 6000.0, now, off, say=said.append)
        box["st"] = json.loads(json.dumps(box["st"]))        # the state file's round trip: a fresh process each tick
        return ph.sent[n0:], ch

    def head(m):
        return m[0].split("\n")[0]
    sA, _ch = utick(11, 15, 20, 50)                       # 3:50 PM ET: both losses first seen
    check("undo: a new loss waits one tick (its money must read the same twice): nothing sent, 2 pending",
          len(sA) + 10 * (len(box["st"].get("undo_pending") or {}) != 2), 0, 0)
    ph.up = False                                            # 3:55 PM ET: Telegram down -- nothing counted as said
    s0, _ch = utick(11, 15, 20, 55)
    check("undo: Telegram down: no loss marked as said (tried again next tick)", len(box["st"]["undo_alerted"]), 0, 0)
    ph.up = True
    s1, ch1 = utick(11, 15, 21, 0)                        # 4:00 PM ET
    U = undo_rows(ch1)
    check("undo: M, K and WS scored vs keeping them: M -47.04, K +2.00, WS -48.50 (1 = right)",
          1 if (set(U) == {"M", "K", "WS"} and U["M"]["undo"]["net_usd"] == -47.04 and U["K"]["undo"]["net_usd"] == 2.0
                and U["WS"]["undo"]["net_usd"] == -48.5) else 0, 1, 1)
    losses = [m for m in s1 if m[0].startswith("⚠️")]
    print()
    for m in s1:
        print(("[URGENT] " if m[1] else "[normal] ") + m[0])
        print()
    check("undo: 4 PM: the 2 losing markets alert, one message each (SOL WS, XRP 3 PM M)", len(losses), 2, 2)
    sol_m = next((m for m in losses if "SOL 8:00 AM" in head(m)), None)
    xrp_m = next((m for m in losses if "XRP 3:00 PM" in head(m)), None)
    want_x = ("Loss a reverted rule would have stopped: XRP 3:00 PM -$48.52 (-0.81% of the bank)",
              "the 3rd-bet block (M) would have kept that bet out", "filled 50 past the 2-bet budget", "the bet LOST",
              "Since the undo (Nov 15 6:00 AM ET), M's net vs keeping the rule: -$47.04 (-0.78% of the bank) on 2 bets",
              "All 3 reverted rules vs keeping them: -$93.54", "/fixes")
    check("undo: the M loss in plain words (%d phrases)" % len(want_x),
          sum(1 for w in want_x if xrp_m and w in xrp_m[0]), len(want_x), len(want_x))
    want_s = ("SOL 8:00 AM -$50.00", "the wrong-side skip (WS) would have skipped that market",
              "WS's net vs keeping the rule: -$48.50", "on 2 markets")
    check("undo: the WS loss in plain words (%d phrases)" % len(want_s),
          sum(1 for w in want_s if sol_m and w in sol_m[0]), len(want_s), len(want_s))
    check("undo: $50+ rings (urgent), the $48.52 one does not (1 = right)",
          1 if (sol_m and sol_m[1] and xrp_m and not xrp_m[1]) else 0, 1, 1)
    check("undo: a WINNING undo market never alerts (ETH +2.00, XRP 11 AM +1.48, DOGE +1.50)",
          sum(1 for m in losses if any(w in head(m) for w in ("ETH", "DOGE", "XRP 11:00 AM"))), 0, 0)
    s2, _ch = utick(11, 15, 21, 5)                        # 4:05 PM ET, a fresh process
    check("undo: the next tick (after a restart) repeats nothing", len(s2), 0, 0)
    s3, _ch = utick(11, 16, 2, 5)                         # 9:05 PM ET Nov 15: the daily line
    print("[normal] " + (s3[0][0] if s3 else "(no daily)"))
    print()
    dl = s3[0][0] if s3 else ""
    want_d = ("REVERTED PIN RULES · end of Nov 15 (day 1 since the undo)",
              "3rd-bet block (M): 2 bets · 1 won, 1 lost · -$47.04 (-0.78% of the bank) · that day -$47.04 on 2",
              "6-10 AM cheap-buy skip (K): 1 market · 1 won, 0 lost · +$2.00",
              "Wrong-side skip (WS): 2 markets · 1 won, 1 lost · -$48.50",
              "reverting has COST $93.54 (-1.56% of the bank) against keeping them, on 5 bets and markets",
              "Losses a reverted rule would have stopped since the undo: 2, -$98.52 (-1.64% of the bank)",
              "The jump cap (B) was dropped too", "/fixes")
    check("undo: 9:05 PM: ONE daily line, each rule's total, won/lost, the sum (%d phrases)" % len(want_d),
          sum(1 for w in want_d if w in dl) if len(s3) == 1 and not s3[0][1] else -1, len(want_d), len(want_d))
    s4, _ch = utick(11, 16, 2, 10)                        # 9:10 PM ET
    check("undo: the daily line once per ET day (9:10 PM: nothing)", len(s4), 0, 0)
    write(rows + late)                                       # the log grows: DOT and LINK settle 11:15 PM ET
    s5a, _ch = utick(11, 16, 4, 30)                       # 11:30 PM ET: first seen, waits a tick
    check("undo: 11:30 PM: DOT and LINK first seen, nothing yet", len(s5a), 0, 0)
    s5, _ch = utick(11, 16, 4, 35)                        # 11:35 PM ET: quiet hours
    check("undo: quiet hours: the $97 LINK loss goes at once, urgent; the $9.70 DOT loss is HELD (1 = right)",
          1 if (len(s5) == 1 and s5[0][1] and "LINK" in head(s5[0]) and "-$97.00" in head(s5[0])
                and [h["id"] for h in box["st"]["held"]] == ["undo|WS|DOT|%d" % calendar.timegm((2026, 11, 16, 4, 15, 0))])
          else 0, 1, 1)
    check("undo: nothing left pending once said", len(box["st"].get("undo_pending") or {}), 0, 0)
    s6, _ch = utick(11, 16, 11, 55)                       # 6:55 AM ET: still quiet
    check("undo: 6:55 AM: still quiet, still held, nothing sent", len(s6) + 10 * (len(box["st"]["held"]) != 1), 0, 0)
    s7, _ch = utick(11, 16, 12, 0)                        # 7:00 AM ET: quiet hours over
    print("[normal] " + (s7[0][0] if s7 else "(nothing flushed)"))
    print()
    check("undo: 7:00 AM: the held DOT loss goes, once, as the held message (1 = right)",
          1 if (len(s7) == 1 and not s7[0][1] and "Quiet hours are over (11 PM to 7 AM ET)" in s7[0][0]
                and "DOT 11:15 PM" in s7[0][0] and "-$9.70" in s7[0][0] and not box["st"]["held"]) else 0, 1, 1)
    s8, _ch = utick(11, 16, 12, 5)                        # 7:05 AM ET
    check("undo: a held message is never sent twice", len(s8), 0, 0)
    s9, _ch = utick(11, 17, 2, 5)                         # 9:05 PM ET Nov 16: a day with nothing new
    dl9 = s9[0][0] if s9 else ""
    check("undo: a quiet day still sends its daily line (Nov 16, nothing new, totals -$200.24, 4 losses)",
          sum(1 for w in ("end of Nov 16 (day 2 since the undo)", "nothing new that day", "COST $200.24",
                          "stopped since the undo: 4, -$205.22") if w in dl9) if len(s9) == 1 else -1, 4, 4)
    s10, _ch = utick(11, 18, 4, 40)                       # 11:40 PM ET Nov 17: the first tick of that evening
    check("undo: a daily due in quiet hours is HELD, not lost", len(s10) + 10 * (len(box["st"]["held"]) != 1), 0, 0)
    s11, _ch = utick(11, 18, 12, 0)                       # 7:00 AM ET Nov 18
    check("undo: ...and goes at 7:00 AM, once (Nov 17's)",
          1 if (len(s11) == 1 and "end of Nov 17" in s11[0][0] and not box["st"]["held"]) else 0, 1, 1)
    al = box["st"]["undo_alerted"]
    check("undo: each (rule, market) said once over every tick: SOL, XRP 3 PM, LINK, DOT",
          len(al) if len(set(al)) == len(al) else -1, 4, 4)
    # a late start / an outage: more than UNDO_BURST new losses in one tick go as ONE message
    saved = globals()["UNDO_BURST"]
    globals()["UNDO_BURST"] = 3
    try:
        php, stb = TPhone(), {"undo_daily": {"2026-11-15": "x"}}
        for mi in (0, 5):
            nb = float(calendar.timegm((2026, 11, 16, 15, mi, 0)))
            undo_watch(FX.report(paths=[pU], now=nb), stb, php, 6000.0, nb, off, say=said.append)
    finally:
        globals()["UNDO_BURST"] = saved
    check("undo: 4 new losses over a burst line of 3: ONE message listing them (urgent: $50+ among them)",
          1 if (len(php.sent) == 1 and php.sent[0][1] and php.sent[0][0].count(" • ") == 4) else 0, 1, 1)
    # fixes failing: the held messages still go; from 10 PM a daily that says it could not score
    phf = TPhone()
    stf = {"undo_since": float(calendar.timegm((2026, 11, 15, 11, 0, 0))), "undo_daily": {},
           "held": [{"t": 1.0, "id": "x", "text": "planted held"}]}
    undo_watch(None, stf, phf, 6000.0, float(calendar.timegm((2026, 11, 16, 2, 5, 0))), off, say=said.append,
               failed="ValueError")
    undo_watch(None, stf, phf, 6000.0, float(calendar.timegm((2026, 11, 16, 3, 5, 0))), off, say=said.append,
               failed="ValueError")
    check("undo: fixes failing: the held message goes at 9:05 PM; at 10:05 PM one 'NOT SCORED' daily (1 = right)",
          1 if (len(phf.sent) == 2 and "planted held" in phf.sent[0][0] and "NOT SCORED" in phf.sent[1][0]
                and "ValueError" in phf.sent[1][0]) else 0, 1, 1)
    # Telegram down mid-tick: the first failed send ends the tick's undo sends (no daily after it); the next tick
    # sends what is left, once
    class FPhone(TPhone):
        def send(self, text, urgent, now):
            self.tries = getattr(self, "tries", 0) + 1
            return False if self.tries == 1 else TPhone.send(self, text, urgent, now)
    write(rows)                                              # Nov 15's 2 losses only (no DOT / LINK yet)
    phd, std, tries = FPhone(), {}, []
    for hh, mi in ((1, 55), (2, 0), (2, 5), (2, 10)):        # 8:55 (first seen), 9:00, 9:05, 9:10 PM ET Nov 15
        nd = float(calendar.timegm((2026, 11, 16, hh, mi, 0)))
        undo_watch(FX.report(paths=[pU], now=nd), std, phd, 6000.0, nd, off, say=said.append)
        tries.append(getattr(phd, "tries", 0))
    check("undo: a failed send ends the tick (9 PM: 1 try, no 2nd loss, no daily); 9:05 sends both + the daily once"
          " (tries %s)" % tries,
          1 if (tries == [0, 1, 4, 4] and len(phd.sent) == 3
                and sum(1 for m in phd.sent if "REVERTED PIN RULES" in m[0]) == 1) else 0, 1, 1)
    # a market read between its legs' bookings (pinrun books each leg up to ~45 s apart): never said on a part
    avx, ada = "KXAVAX15M-26NOV201300-00", "KXADA15M-26NOV201400-00"
    pX = os.path.join(d, "pinrun-live-20261120T100000Z.jsonl")
    xrows = [R("start", "2026-11-20T10:00:00Z", **on), R("start", "2026-11-20T11:00:00Z", **off)]
    for tk, hh, nh in ((avx, 17, 200.0), (ada, 18, 100.0)):
        xrows += [usig("2026-11-20T%02d:59:40Z" % hh, tk, "yes", 0.97, 20, wrong=True, rise=0.2),
                  uord("2026-11-20T%02d:59:40Z" % hh, tk, "yes", 100.0, 0.97, 20),
                  R("hedge", "2026-11-20T%02d:59:50Z" % hh, status="executed", ticker=tk, side="no", price=0.30, n=nh,
                    asked=nh)]
    phx, stx = TPhone(), {"undo_daily": {"2026-11-20": "x"}}

    def xtick(hh, mi, more):
        xrows.extend(more)
        with open(pX, "w", encoding="utf-8") as fh:
            for r in xrows:
                fh.write(json.dumps(r) + "\n")
        nx = float(calendar.timegm((2026, 11, 20, hh, mi, 0)))
        n0 = len(phx.sent)
        undo_watch(FX.report(paths=[pX], now=nx), stx, phx, 6000.0, nx, off, say=said.append)
        return phx.sent[n0:]
    x1 = xtick(18, 2, [uset("2026-11-20T18:00:20Z", avx, "yes", "no", -9700.0)])            # AVAX: the lost buy only
    x2 = xtick(18, 7, [uset("2026-11-20T18:00:35Z", avx, "no", "no", 14000.0, cost=0.30)])  # its hedge: +$43 in all
    x3 = xtick(18, 12, [])
    check("undo: a 'loss' read before the hedge leg was booked (AVAX -$97, ends +$43) is never said",
          len(x1) + len(x2) + len(x3) + 10 * len(stx.get("undo_pending") or {}), 0, 0)
    y1 = xtick(19, 2, [uset("2026-11-20T19:00:20Z", ada, "yes", "no", -9700.0)])            # ADA: -$97 so far
    y2 = xtick(19, 7, [uset("2026-11-20T19:00:35Z", ada, "no", "no", 7000.0, cost=0.30)])   # ends -$27
    y3 = xtick(19, 12, [])
    check("undo: a loss whose money moved between ticks is said once, at its FINAL $ (-$27.00, never -$97.00)",
          1 if (not y1 and not y2 and len(y3) == 1 and "ADA 2:00 PM -$27.00" in head(y3[0])
                and "-$97.00" not in y3[0][0]) else 0, 1, 1)
    # the daily at 9 PM ET by the wall clock on the two clock-change days (midnight + 21 h is 10 PM / 8 PM there)
    check("undo: daily at 9 PM ET on the clock-change days (Mar 14 2027 01:00Z+1d, Nov 7 2027 02:00Z+1d) (1 = right)",
          1 if (undo_daily_at("2027-03-14") == calendar.timegm((2027, 3, 15, 1, 0, 0))
                and undo_daily_at("2027-11-07") == calendar.timegm((2027, 11, 8, 2, 0, 0))
                and undo_daily_at("2026-11-15") == calendar.timegm((2026, 11, 16, 2, 0, 0))) else 0, 1, 1)
    alltxt = "\n".join(m[0] for m in ph.sent + php.sent + phf.sent + phd.sent + phx.sent)
    check("undo: no em dash in any of these messages", chr(0x2014) in alltxt, False, False)
    print(php.sent[0][0] if php.sent else "")
    print()


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
