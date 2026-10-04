#!/usr/bin/env python3
"""dipsell_live.py -- SJN1 "Dip Seller" on the daily-high temperature brackets, LIVE micro test, in a SUBACCOUNT.

Operator 2026-10-03: "Yes run the test" (the weather Dip Seller live micro test, IDEA_LEDGER U11 / SJN1).
Spec: results/IDEA_SWEEP_2026-10-02.md row "SJN1 Dip Seller (weather)", results/idea_sweep_2026-10-02.json
id 20261002-N1 (critic idea, checker, refuter), ledger row SJN1 in results/IDEA_LEDGER.md.

PRE-REGISTERED (verbatim from the sweep, written before the first order):
  "live micro test, pre-registered: 2 contracts a trigger (then 10), max 5 open, 14 days or 100 fills; pass =
   fills on 50%+ of triggers, net over +4c a contract with the low end of the range above zero, no day worse
   than -25%; kill if negative after 60 fills."
  The checker's wording of the same test: trigger = hourly candle mid of a KXHIGH bracket fell >= 10c with the
  new mid 15-85c and 6-12 h to close (18 cities); rest a YES ask at post-drop ask + 1c for 2 contracts for 3 h,
  cancel if unfilled, hold fills to settlement; cap 5 open; "low end of the range" = the 1-se lower bound.
  (The checker says "after 14 days or 100 fills, whichever is LATER"; the operator's brief says stop at 100
  fills or 14 days. This bot STOPS PLACING at whichever comes FIRST -- the operator's brief, the safer reading.)

WHAT IT DOES
  * Universe: the 18 KXHIGH city series the in-sample work used (CITIES below).
  * Trigger, Kalshi's own hourly candles (GET /markets/candlesticks, batch), exactly the critic's cell
    definition (.sweep/run-2026-10-02/check-20261002-N1/cands.py): for the candle that closed at the top of
    hour H and the candle before it, both quotes valid (ask > 0, bid present, spread <= 12c); the mid fell
    >= 10c; the new mid is 15-85c; the hour traded >= 50 contracts; 6 <= (close - H)/3600 < 12.
    All comparisons are integer tenths of a cent (no 0.0999999 float misses). Prices are read from the
    *_dollars fields only -- the unit is read, never inferred from a magnitude (hard rule 5).
    Evaluated once per hour, 60 s after the top of the hour, and only if the bot is no more than 15 min
    late (the in-sample first lift came a median 6 min after the candle close); a staler hour is evaluated
    for the log only ("diag") and places nothing.
  * Order: SELL YES (= buy NO) post_only at the candle's post-drop ask + 1c, 2 contracts, in the subaccount,
    in the market's own cash pool (KXHIGH = exchange_index 0; anything else is refused). Hold fills to
    settlement. Unfilled remainder cancelled 3 h after the candle close (the spec's window).
  * Records per fill what the checker asked for: trigger time, a, fill price, minutes to fill, the max ask
    and max last price seen in the 3 h window, settlement.

HARD RAILS (code, not flags)
  2 contracts an order (10 is the next step: a code change + a VERSIONS.md entry); at most 5 open (a market
  with a resting order or an unsettled holding); at most ONE order per market, ever; day stop at -25% of the
  starting pot (the ET day of the trigger: settled P&L + the open holdings marked at the current ask) -> no
  new order that ET day and every resting order cancelled; KILL once 60 fills have settled with net P&L < 0;
  STOP placing at 100 fills or 14 days after the first live start; post_only always; subaccount 0 (primary),
  1 (live ladder) and 2 (live forecaster) refused -- both bots size off their own pot, a weather holding in
  either would move it; a live start refuses unless the subaccount's pool-0 pot reads $50..$150 and the
  subaccount holds nothing but KXHIGH; stop file results/dipsell-live.stop cancels every resting order and
  exits; at most 3 order writes a second (this API key is shared with the live bots). Exit for any reason
  cancels whatever still rests (nobody else would enforce the 3 h window); holdings settle on their own and
  a restart books them (state is rebuilt from the live log, so a restart never re-orders a market).

LOGS (one JSON object a line, UTC `t`, `ev`):
  live    results/dipsell-live-orders.jsonl
  dry run results/dipsell-dry-orders.jsonl   (a dry run never writes to the live log)
  ev: start | hour_eval | trigger | rail_refused | placed | would_place | rejected | fill | cancel |
      window_end | settle | day_stop | kill | done | stop_file | exit | error
  `settle` carries pnl (dollars), pnl_c (cents a contract), the trigger's ET day, that day's settled total
  and its % of the starting pot, and the running net. `--report` reads the live log and prints the bar.

    python research/sweep/dipsell_live.py --selftest
    python research/sweep/dipsell_live.py --subaccount N --dry-run --minutes 10
    python -u research/sweep/dipsell_live.py --subaccount N --live --minutes 21600
    python research/sweep/dipsell_live.py --report
"""
import argparse
import calendar
import json
import math
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "research"))

LIVE_LOG = os.path.join(ROOT, "results", "dipsell-live-orders.jsonl")
DRY_LOG = os.path.join(ROOT, "results", "dipsell-dry-orders.jsonl")
STOP_FILE = os.path.join(ROOT, "results", "dipsell-live.stop")
KEY_FILE = r"C:\kals\kalshi.pem"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"

CITIES = ("KXHIGHNY KXHIGHCHI KXHIGHMIA KXHIGHLAX KXHIGHAUS KXHIGHDEN KXHIGHPHIL KXHIGHTSFO KXHIGHTSEA "
          "KXHIGHTBOS KXHIGHTDAL KXHIGHTATL KXHIGHTPHX KXHIGHTLV KXHIGHTOKC KXHIGHTHOU KXHIGHTMIN KXHIGHTDC").split()

# the trigger (tenths of a cent where it is a price)
DROP_T = 100                  # mid fell >= 10c
MID_LO_T, MID_HI_T = 150, 850  # new mid 15-85c
SPREAD_T = 120                # both candles' spread <= 12c
MIN_VOL = 50.0                # contracts traded in the drop hour
HL_LO, HL_HI = 6.0, 12.0      # hours from the candle close to the market close, [6, 12)
# the order and its rails
CONTRACTS = 2
MAX_OPEN = 5
WINDOW_S = 3 * 3600           # cancel the unfilled remainder 3 h after the candle close
DAY_STOP_FRAC = 0.25
KILL_AFTER = 60
MAX_FILLS = 100
MAX_DAYS = 14
POOL = 0                      # KXHIGH markets' exchange_index (read 2026-10-04 00:21Z); others are refused
RESERVED = {0: "the primary account", 1: "the live ladder's subaccount", 2: "the live forecaster's subaccount"}
POT_MIN, POT_MAX = 50.0, 150.0
NOMINAL_POT = 100.0           # a dry run with no funded subaccount sizes its rails off this
CID_PREFIX = "dip-"


def safe_cid(c):
    """2026-10-04: Kalshi answers 400 invalid_parameters to a client_order_id holding '.', which every bracket
    ticker has (KXHIGHTHOU-26OCT04-B81.5); keep only letters, digits, '-' and '_'."""
    return "".join(ch if (ch.isalnum() or ch in "-_") else "p" for ch in c)
WRITES_PER_S = 3.0
SCAN_S, POLL_S, EVAL_DELAY_S, STALE_S, SETTLE_S = 60.0, 15.0, 60.0, 15 * 60.0, 300.0
GET_GAP_S = 0.15
BAR = ("live micro test, pre-registered: 2 contracts a trigger (then 10), max 5 open, 14 days or 100 fills; pass = "
       "fills on 50%+ of triggers, net over +4c a contract with the low end of the range above zero, no day worse "
       "than -25%; kill if negative after 60 fills.")


def now_iso(t=None):
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ts(s):
    return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))


def _sunday(y, m, n):
    """Day of month of the n-th Sunday of (y, m)."""
    wd = datetime(y, m, 1).weekday()            # Monday 0 .. Sunday 6
    return 1 + (6 - wd) % 7 + 7 * (n - 1)


def et_day(t):
    """The ET calendar date of UTC second t: EDT (UTC-4) from the 2nd Sunday of March 07:00Z to the 1st Sunday of
    November 06:00Z, EST (UTC-5) otherwise. Presentation/day-bucketing only; every `t` in the log is UTC."""
    y = time.gmtime(t).tm_year
    a = calendar.timegm((y, 3, _sunday(y, 3, 2), 7, 0, 0))
    b = calendar.timegm((y, 11, _sunday(y, 11, 1), 6, 0, 0))
    off = 4 if a <= t < b else 5
    return time.strftime("%Y-%m-%d", time.gmtime(t - off * 3600))


def tc(x):
    """dollars -> integer tenths of a cent."""
    return int(round(float(x) * 1000))


class Logger:
    def __init__(self, path=None, sink=None):
        self.sink = sink
        self.fh = open(path, "a", encoding="utf-8") if path else None
        self.lock = threading.Lock()

    def write(self, ev, **kw):
        rec = {"t": now_iso(), "ev": ev}
        rec.update(kw)
        with self.lock:
            if self.sink is not None:
                self.sink.append(rec)
            if self.fh:
                self.fh.write(json.dumps(rec, default=str, separators=(",", ":")) + "\n")
                self.fh.flush()


# ------------------------------------------------------------------------------------------------ the trigger
def parse_candles(entry):
    """One market's candles from the API -> [{t, a, b, v}] sorted by t. a/b None when the field is absent."""
    out = []
    for c in (entry or {}).get("candlesticks") or []:
        try:
            t = int(c["end_period_ts"])
        except (KeyError, TypeError, ValueError):
            continue

        def px(side):
            try:
                return float(c[side]["close_dollars"])
            except (KeyError, TypeError, ValueError):
                return None
        try:
            v = float(c.get("volume_fp") or 0)
        except (TypeError, ValueError):
            v = 0.0
        out.append({"t": t, "a": px("yes_ask"), "b": px("yes_bid"), "v": v})
    out.sort(key=lambda x: x["t"])
    return out


def judge(prev, cur, close_ts):
    """(fires, why, info) for the candle `cur` (closed at cur['t']) against the candle before it.
    Exactly the critic's cell: valid quotes both hours, mid fell >= 10c, new mid 15-85c, hour volume >= 50,
    6 <= hours left < 12. `why` names the first test that failed ('' when it fires)."""
    info = {}
    if prev is None or cur is None:
        return False, "no_candle", info
    for c in (prev, cur):
        if c["a"] is None or c["b"] is None or c["a"] <= 0 or tc(c["a"]) - tc(c["b"]) > SPREAD_T:
            return False, "bad_quote", info
    m0 = tc(prev["a"]) + tc(prev["b"])          # twice the mid, tenths of a cent
    m1 = tc(cur["a"]) + tc(cur["b"])
    hl = (close_ts - cur["t"]) / 3600.0
    info = {"a": cur["a"], "b": cur["b"], "mid0": m0 / 2000.0, "mid": m1 / 2000.0, "drop_c": (m1 - m0) / 20.0,
            "v": cur["v"], "hl": round(hl, 3), "H": cur["t"]}
    if m1 - m0 > -2 * DROP_T:
        return False, "no_drop", info
    if not (2 * MID_LO_T <= m1 <= 2 * MID_HI_T):
        return False, "mid_range", info
    if cur["v"] < MIN_VOL:
        return False, "volume", info
    if not (HL_LO <= hl < HL_HI):
        return False, "hours_left", info
    return True, "", info


def evaluate_hour(H, snap, fetch, log, on_trigger, act):
    """Judge the candle that closed at H for every open bracket in `snap`. fetch(tickers, H) -> {ticker: candles}.
    on_trigger(trig) -> refusal reason or None. act=False logs only ('diag'). Returns the hour's counts."""
    tickers = sorted(snap)
    cands = fetch(tickers, H) if tickers else {}
    n = {"watched": len(tickers), "with_candle": 0, "drop10_any_window": 0, "triggers": 0, "acted": 0}
    for tk in tickers:
        cs = cands.get(tk) or []
        cur_i = next((i for i, c in enumerate(cs) if c["t"] == H), None)
        if cur_i is None or cur_i == 0:
            continue
        n["with_candle"] += 1
        fires, why, info = judge(cs[cur_i - 1], cs[cur_i], snap[tk]["close"])
        if fires or why == "hours_left":
            n["drop10_any_window"] += 1
        if not fires:
            continue
        n["triggers"] += 1
        m = snap[tk]
        trig = dict(info, ticker=tk, event=m.get("event"), series=m.get("series"), exi=m.get("exi"),
                    close=m["close"], ask_now=m.get("a"), bid_now=m.get("b"))
        log.write("trigger", act=act, **trig)
        if act:
            why2 = on_trigger(trig)
            if why2 is None:
                n["acted"] += 1
    log.write("hour_eval", H=H, H_iso=now_iso(H), act=act, **n)
    return n


# ------------------------------------------------------------------------------------------------ orders
def order_body(ticker, px, sub, cid, exi):
    """SELL YES at px (economically buy NO at 1 - px): side 'ask', price px, CONTRACTS, post_only."""
    return {"ticker": ticker, "side": "ask", "count": "%.2f" % CONTRACTS, "price": "%.4f" % px,
            "time_in_force": "good_till_canceled", "self_trade_prevention_type": "maker",
            "post_only": True, "client_order_id": cid, "subaccount": int(sub), "exchange_index": int(exi)}


def body_ok(b, sub):
    """Every order body must carry these, or it is not sent."""
    try:
        p = float(b["price"])
    except Exception:
        return False
    return (b.get("post_only") is True and b.get("side") == "ask" and b.get("subaccount") == int(sub)
            and int(sub) not in RESERVED and 1 <= int(sub) <= 63
            and b.get("exchange_index") == POOL and b.get("count") == "%.2f" % CONTRACTS
            and b.get("self_trade_prevention_type") == "maker" and b.get("time_in_force") == "good_till_canceled"
            and str(b.get("client_order_id", "")).startswith(CID_PREFIX)
            and str(b.get("ticker", "")).startswith("KXHIGH")
            and 0.16 <= p <= 0.95 and abs(p * 100 - round(p * 100)) < 1e-6)


def sub_refusal(sub):
    if sub is None or not (0 <= int(sub) <= 63):
        return "--subaccount N (3..63) is required"
    if int(sub) in RESERVED:
        return "subaccount %d is %s -- refused" % (int(sub), RESERVED[int(sub)])
    return None


def start_refusal(pot, cash, foreign, live):
    """The live start checks, as a function so the self-test drives them. The reason, or None."""
    if not live:
        return None
    if pot is None or cash is None:
        return "the subaccount's pool-0 pot is unreadable"
    if foreign:
        return "the subaccount holds non-KXHIGH positions %s; it must be this test's alone" % foreign[:5]
    if not (POT_MIN <= pot <= POT_MAX):
        return "pot $%.2f is outside $%.0f..$%.0f (a ~$100 micro test)" % (pot, POT_MIN, POT_MAX)
    return None


def read_pot(sender, sub):
    """(cash, pot, foreign tickers) for the subaccount's pool 0, or (None, None, None) if any read fails.
    cash = pool-0 balance (cents and dollars must both be present and agree -- the unit is read, hard rule 5);
    pot = cash + the cost of KXHIGH holdings; foreign = tickers held that are not KXHIGH."""
    st, bal = sender("GET", "/portfolio/balance", None, {"subaccount": int(sub), "exchange_index": POOL})
    try:
        cash = float(bal["balance_dollars"])
        cents = float(bal["balance"])
    except Exception:
        return None, None, None
    if st != 200 or abs(cents / 100.0 - cash) > 0.011:
        return None, None, None
    st2, pos = sender("GET", "/portfolio/positions", None,
                      {"subaccount": int(sub), "count_filter": "position", "settlement_status": "unsettled"})
    if st2 != 200 or not isinstance(pos, dict) or not isinstance(pos.get("market_positions"), list):
        return None, None, None
    held, foreign = 0.0, []
    for x in pos["market_positions"]:
        try:
            e = float(x["market_exposure_dollars"]) if x.get("market_exposure_dollars") is not None \
                else float(x["market_exposure"]) / 100.0
        except Exception:
            return None, None, None
        if str(x.get("ticker", "")).startswith("KXHIGH"):
            held += abs(e)
        else:
            foreign.append(x.get("ticker"))
    return round(cash, 4), round(cash + held, 4), foreign


class Dip:
    """The test's whole state: one record per market ordered (one order per market, ever)."""

    def __init__(self, log, sub, dry, sender, now, start_pot, t0=None):
        self.log, self.sub, self.dry, self.send, self.now = log, int(sub), dry, sender, now
        self.start_pot = float(start_pot)
        self.t0 = now() if t0 is None else t0
        self.orders = {}            # ticker -> order state
        self.used = set()           # every market an order was attempted in
        self.halt_day = None        # ET day under the day stop
        self.killed = self.done = self.stopped = False
        self.cash = None
        self.q = queue.Queue()
        self.lock = threading.RLock()
        self._w = []
        self.last_H = None
        self.start_pot_from_log = None

    # --- counts the rails and the bar read ---
    def open_count(self):
        t = self.now()
        return sum(1 for o in self.orders.values()
                   if o["status"] in ("sending", "resting", "cancelling")
                   or (o["status"] == "cancel_failed" and t < o.get("limbo_until", 0))
                   or (o["filled"] > 0 and not o.get("settled")))

    def fills(self):
        return [o for o in self.orders.values() if o["filled"] > 0]

    def settled(self):
        return [o for o in self.orders.values() if o.get("settled")]

    def rails_refusal(self, ticker, px, now):
        if self.stopped:
            return "stopped"
        if self.killed:
            return "killed"
        if self.done:
            return "done"
        if self.halt_day == et_day(now):
            return "day_stop"
        if ticker in self.used:
            return "one_per_market"
        if self.open_count() >= MAX_OPEN:
            return "max_open"
        if not self.dry and self.cash is not None and self.cash + 1e-9 < CONTRACTS * (1.0 - px):
            return "no_cash"
        return None

    def on_trigger(self, trig):
        now = self.now()
        px = round(float(trig["a"]) + 0.01, 2)
        with self.lock:
            why = self.rails_refusal(trig["ticker"], px, now)
            if why is None and trig.get("exi") != POOL:
                why = "pool %s is not %d" % (trig.get("exi"), POOL)
            if why:
                self.log.write("rail_refused", ticker=trig["ticker"], H=trig["H"], px=px, why=why,
                               open=self.open_count())
                return why
            self.used.add(trig["ticker"])
            self.orders[trig["ticker"]] = {
                "ticker": trig["ticker"], "event": trig.get("event"), "series": trig.get("series"),
                "exi": trig.get("exi"), "close": trig["close"], "H": trig["H"], "day": et_day(trig["H"]),
                "a": trig["a"], "px": px, "kid": None, "cid": None, "status": "sending", "filled": 0,
                "fees": 0.0, "max_ask": trig.get("ask_now"), "max_last": None, "first_fill_t": None,
                "window_logged": False, "settled": False}
            self.q.put(("place", trig["ticker"]))
        return None

    # --- the one writer ---
    def _throttle(self):
        t = time.time()
        self._w = [x for x in self._w if t - x < 1.0]
        if len(self._w) >= WRITES_PER_S:
            time.sleep(max(0.0, 1.0 - (t - self._w[0])))
        self._w.append(time.time())

    def work_once(self, item):
        kind, tk = item
        o = self.orders.get(tk)
        if o is None:
            return
        if kind == "place":
            cid = safe_cid("%s%d-%s" % (CID_PREFIX, int(o["H"]), tk[-24:]))
            b = order_body(tk, o["px"], self.sub, cid, o["exi"])
            if not body_ok(b, self.sub):
                with self.lock:
                    o["status"] = "refused"
                self.log.write("body_refused", body=b)
                return
            o["cid"] = cid
            if self.dry:
                with self.lock:
                    o["status"], o["kid"] = "resting", "dry-" + cid
                self.log.write("would_place", ticker=tk, body=b, H=o["H"], a=o["a"], px=o["px"])
                return
            self._throttle()
            st, r = self.send("POST", "/portfolio/events/orders", b, None)
            if st in (200, 201) and isinstance(r, dict):
                rec = r.get("order") or r
                with self.lock:
                    o["kid"], o["status"] = rec.get("order_id"), "resting"
                self.log.write("placed", ticker=tk, order_id=o["kid"], body=b, H=o["H"], a=o["a"], px=o["px"],
                               day=o["day"], resp=str(r)[:200])
                try:
                    f = float(rec.get("fill_count_fp") or rec.get("fill_count") or 0)
                    if f > 0:
                        self.on_fill(tk, f, 0.0)
                except Exception:
                    pass
            else:
                with self.lock:
                    o["status"] = "rejected"
                self.log.write("rejected", ticker=tk, body=b, H=o["H"], status=st, resp=str(r)[:300])
        elif kind == "cancel":
            if self.dry or not o.get("kid"):
                with self.lock:
                    o["status"] = "cancelled"
                self.log.write("cancel", ticker=tk, order_id=o.get("kid"), dry=self.dry, status=None,
                               filled=o["filled"], why=o.get("cancel_why"))
                return
            self._throttle()
            st, r = self.send("DELETE", "/portfolio/events/orders/%s" % o["kid"], None,
                              {"subaccount": self.sub, "exchange_index": POOL})
            with self.lock:
                o["status"] = "cancelled" if st in (200, 201) else "cancel_failed"
                if o["status"] == "cancel_failed":       # a 404 = already filled or gone: counted open 5 min while
                    o["limbo_until"] = self.now() + 300  # the poller books any fill, then it can never wedge the rails
            self.log.write("cancel", ticker=tk, order_id=o["kid"], status=st, filled=o["filled"],
                           why=o.get("cancel_why"), resp=str(r)[:200])

    def run_writer(self):
        while True:
            item = self.q.get()
            try:
                self.work_once(item)
            except Exception as e:
                self.log.write("error", where="writer", err=repr(e)[:300])
            finally:
                self.q.task_done()

    def cancel(self, tk, why):
        o = self.orders[tk]
        if o["status"] in ("resting", "sending"):
            o["status"], o["cancel_why"] = "cancelling", why
            self.q.put(("cancel", tk))

    def cancel_all(self, why):
        with self.lock:
            for tk in list(self.orders):
                self.cancel(tk, why)

    # --- fills ---
    def on_fill(self, tk, new_filled, fees):
        with self.lock:
            o = self.orders.get(tk)
            if o is None or new_filled <= o["filled"] + 1e-9:
                return
            delta = new_filled - o["filled"]
            o["filled"] = new_filled
            o["fees"] = float(fees or 0.0)
            t = self.now()
            if o["first_fill_t"] is None:
                o["first_fill_t"] = t
            self.log.write("fill", ticker=tk, order_id=o["kid"], px=o["px"], a=o["a"], delta=delta,
                           filled=new_filled, fees=o["fees"], min_to_fill=round((t - o["H"]) / 60.0, 1),
                           fills_total=len(self.fills()), day=o["day"])

    def poll_fills_once(self):
        st, r = self.send("GET", "/portfolio/orders", None,
                          {"subaccount": self.sub, "min_ts": int(self.now()) - 8 * 3600, "limit": 500})
        if st != 200 or not isinstance(r, dict):
            return False
        by_kid = {o["kid"]: tk for tk, o in self.orders.items() if o.get("kid")}
        for x in r.get("orders") or []:
            tk = by_kid.get(x.get("order_id"))
            if tk is None:
                continue
            fees = 0.0
            for k in ("maker_fees_dollars", "taker_fees_dollars"):
                try:
                    fees += float(x.get(k) or 0)
                except (TypeError, ValueError):
                    pass
            try:
                self.on_fill(tk, float(x.get("fill_count_fp") or x.get("fill_count") or 0), fees)
            except (TypeError, ValueError):
                pass
            if x.get("status") in ("executed", "canceled", "cancelled"):
                with self.lock:
                    o = self.orders[tk]
                    if o["status"] in ("resting", "cancelling", "cancel_failed"):
                        o["status"] = "closed"
        return True

    def run_poller(self):
        while True:
            try:
                if not self.dry and any(o["status"] in ("resting", "cancelling", "cancel_failed")
                                        for o in list(self.orders.values())):
                    self.poll_fills_once()
            except Exception as e:
                self.log.write("error", where="poller", err=repr(e)[:300])
            time.sleep(POLL_S)

    # --- settlement ---
    def on_result(self, tk, result):
        if result not in ("yes", "no"):
            return None          # not settled yet: an empty result books nothing
        with self.lock:
            o = self.orders.get(tk)
            if o is None or o["filled"] <= 0 or o.get("settled"):
                return None
            n, px = o["filled"], o["px"]
            pnl = (n * px if result == "no" else -n * (1.0 - px)) - o["fees"]
            o["settled"], o["result"], o["pnl"] = True, result, pnl
            day_pnl = sum(x["pnl"] for x in self.settled() if x["day"] == o["day"])
            net = sum(x["pnl"] for x in self.settled())
            self.log.write("settle", ticker=tk, result=result, n=n, px=px, a=o["a"], fees=o["fees"],
                           pnl=round(pnl, 4), pnl_c=round(100.0 * pnl / n, 3), day=o["day"],
                           day_pnl=round(day_pnl, 4), day_pct=round(100.0 * day_pnl / self.start_pot, 2),
                           net=round(net, 4), settled_fills=len(self.settled()), fills_total=len(self.fills()),
                           max_ask_3h=o.get("max_ask"), max_last_3h=o.get("max_last"),
                           min_to_fill=None if o["first_fill_t"] is None else round((o["first_fill_t"] - o["H"]) / 60.0, 1))
            return pnl

    def settle_check(self, getter):
        t = self.now()
        for tk, o in list(self.orders.items()):
            if o["filled"] > 0 and not o.get("settled") and t >= o["close"]:
                st, r = getter("/markets/%s" % tk)
                m = (r.get("market") or r) if isinstance(r, dict) else {}
                if st == 200:
                    self.on_result(tk, m.get("result"))

    # --- every scan ---
    def day_pnl(self, day, snap):
        """The trigger-day cohort: settled P&L + open holdings marked at the current ask (buy back = ask)."""
        tot = 0.0
        for o in self.orders.values():
            if o["day"] != day or o["filled"] <= 0:
                continue
            if o.get("settled"):
                tot += o["pnl"]
            else:
                ask = (snap.get(o["ticker"]) or {}).get("a")
                if ask is not None:
                    tot += o["filled"] * (o["px"] - float(ask)) - o["fees"]
        return tot

    def tick(self, snap, stop_file=None):
        t = self.now()
        with self.lock:
            if not self.stopped and os.path.exists(stop_file or STOP_FILE):
                self.stopped = True
                self.log.write("stop_file", path=stop_file or STOP_FILE)
                self.cancel_all("stop_file")
            for tk, o in self.orders.items():
                m = snap.get(tk) or {}
                if t < o["H"] + WINDOW_S:
                    for k, f in (("max_ask", "a"), ("max_last", "last")):
                        if m.get(f) is not None and (o[k] is None or float(m[f]) > float(o[k])):
                            o[k] = float(m[f])
                elif not o["window_logged"]:
                    o["window_logged"] = True
                    self.cancel(tk, "window")
                    self.log.write("window_end", ticker=tk, filled=o["filled"], px=o["px"], a=o["a"],
                                   max_ask_3h=o["max_ask"], max_last_3h=o["max_last"], status=o["status"])
            d = et_day(t)
            if self.halt_day != d:
                dp = self.day_pnl(d, snap)
                if dp <= -DAY_STOP_FRAC * self.start_pot:
                    self.halt_day = d
                    self.log.write("day_stop", day=d, day_pnl=round(dp, 4), limit=round(-DAY_STOP_FRAC * self.start_pot, 2))
                    self.cancel_all("day_stop")
            st = self.settled()
            if not self.killed and len(st) >= KILL_AFTER and sum(o["pnl"] for o in st) < 0:
                self.killed = True
                self.log.write("kill", settled_fills=len(st), net=round(sum(o["pnl"] for o in st), 4))
                self.cancel_all("kill")
            if not self.done and (len(self.fills()) >= MAX_FILLS or t - self.t0 >= MAX_DAYS * 86400):
                self.done = True
                self.log.write("done", fills=len(self.fills()), days=round((t - self.t0) / 86400.0, 2))
                self.cancel_all("done")

    def finished(self):
        """Nothing left to do: placing has ended and nothing rests or waits to settle."""
        busy = self.open_count() > 0 or not self.q.empty()
        return (self.stopped and not any(o["status"] in ("sending", "resting", "cancelling") for o in self.orders.values())
                and self.q.empty()) or ((self.killed or self.done) and not busy)


def rebuild(dip, records):
    """Restore a live run's state from its own log, so a restart never re-orders a market or forgets a holding."""
    trig_info = {}
    for r in records:
        ev, tk = r.get("ev"), r.get("ticker")
        if ev == "start" and r.get("live"):
            if r.get("t0") is not None:
                dip.t0 = min(dip.t0, float(r["t0"]))
            if r.get("start_pot") and dip.start_pot_from_log is None:
                dip.start_pot_from_log = float(r["start_pot"])
        elif ev == "trigger" and r.get("act") and tk:
            trig_info[tk] = r
        elif ev in ("placed", "rejected") and tk:
            dip.used.add(tk)
            b = r.get("body") or {}
            ti = trig_info.get(tk) or {}
            o = dip.orders.setdefault(tk, {
                "ticker": tk, "event": ti.get("event"), "series": ti.get("series"), "exi": b.get("exchange_index"),
                "close": ti.get("close") if ti.get("close") is not None else (r.get("H") or 0) + 12 * 3600,
                "H": r.get("H"), "day": et_day(r.get("H") or 0), "a": r.get("a"), "px": float(b.get("price") or 0),
                "kid": None, "cid": b.get("client_order_id"), "status": "rejected", "filled": 0, "fees": 0.0,
                "max_ask": None, "max_last": None, "first_fill_t": None, "window_logged": False, "settled": False})
            if ev == "placed":
                o["kid"], o["status"] = r.get("order_id"), "resting"
        elif ev == "fill" and tk in dip.orders:
            o = dip.orders[tk]
            o["filled"], o["fees"] = float(r.get("filled") or 0), float(r.get("fees") or 0)
            if o["first_fill_t"] is None:
                o["first_fill_t"] = iso_ts(r["t"])
        elif ev == "cancel" and tk in dip.orders:
            dip.orders[tk]["status"] = "cancelled" if r.get("status") in (200, 201, None) else "cancel_failed"
        elif ev == "window_end" and tk in dip.orders:
            dip.orders[tk]["window_logged"] = True
        elif ev == "settle" and tk in dip.orders:
            o = dip.orders[tk]
            o["settled"], o["result"], o["pnl"] = True, r.get("result"), float(r.get("pnl") or 0)
        elif ev == "day_stop":
            dip.halt_day = r.get("day")
        elif ev == "kill":
            dip.killed = True
        elif ev == "done":
            dip.done = True
        elif ev == "hour_eval" and r.get("act"):
            dip.last_H = max(dip.last_H or 0, int(r.get("H") or 0))
    return dip


# ------------------------------------------------------------------------------------------------ the bar
def report(records, start_pot=None):
    """The pre-registered bar, from a live log. Fill rate = orders with any fill / orders SENT (placed + rejected
    by Kalshi; a rail refusal is not a chance to fill). Net c a contract = settled P&L / settled contracts, its se
    clustered by the trigger's ET day; the low end = net - 1 se. Worst day = the lowest settled ET-day total as a
    % of the starting pot."""
    sent, filled, setl = {}, {}, {}
    trig = refused = 0
    pot = start_pot
    for r in records:
        ev = r.get("ev")
        if ev == "start" and r.get("live") and pot is None:
            pot = r.get("start_pot")
        elif ev == "trigger" and r.get("act"):
            trig += 1
        elif ev == "rail_refused":
            refused += 1
        elif ev in ("placed", "rejected"):
            sent[r["ticker"]] = ev
        elif ev == "fill":
            filled[r["ticker"]] = float(r.get("filled") or 0)
        elif ev == "settle":
            setl[r["ticker"]] = r
    pot = float(pot or NOMINAL_POT)
    n_sent, n_fill = len(sent), sum(1 for t in sent if filled.get(t, 0) > 0)
    days = {}
    for r in setl.values():
        d = days.setdefault(r["day"], [0.0, 0.0])
        d[0] += float(r["pnl"])
        d[1] += float(r["n"])
    P = sum(v[0] for v in days.values())
    N = sum(v[1] for v in days.values())
    out = {"triggers": trig, "rail_refused": refused, "sent": n_sent,
           "rejected": sum(1 for v in sent.values() if v == "rejected"), "filled_orders": n_fill,
           "fill_rate": (n_fill / n_sent) if n_sent else None, "settled": len(setl), "contracts": N,
           "net_usd": round(P, 4), "net_c": None, "se_c": None, "low_c": None, "worst_day_pct": None,
           "worst_day": None, "days": len(days), "start_pot": pot}
    if N > 0:
        r_ = P / N
        out["net_c"] = round(100 * r_, 3)
        D = len(days)
        if D >= 2:
            se = math.sqrt(D / (D - 1.0) * sum((v[0] - r_ * v[1]) ** 2 for v in days.values())) / N
            out["se_c"] = round(100 * se, 3)
            out["low_c"] = round(100 * (r_ - se), 3)
        wd = min(days.items(), key=lambda kv: kv[1][0])
        out["worst_day"], out["worst_day_pct"] = wd[0], round(100.0 * wd[1][0] / pot, 2)
    out["pass_fill"] = out["fill_rate"] is not None and out["fill_rate"] >= 0.5
    out["pass_net"] = out["net_c"] is not None and out["net_c"] > 4.0
    out["pass_low"] = out["low_c"] is not None and out["low_c"] > 0.0
    out["pass_day"] = out["worst_day_pct"] is not None and out["worst_day_pct"] > -25.0
    out["pass"] = all(out[k] for k in ("pass_fill", "pass_net", "pass_low", "pass_day"))
    return out


# ------------------------------------------------------------------------------------------------ live plumbing
def make_reader(sender):
    def get(path, q=None):
        for attempt in range(4):
            st, r = sender("GET", path, None, q)
            time.sleep(GET_GAP_S)
            if st == 429:
                time.sleep(1.0 + attempt)
                continue
            return st, r
        return st, r
    return get


def scan(get):
    """Every open bracket of the 18 city series -> {ticker: {a, b, last, vol, close, exi, event, series}}."""
    snap = {}
    for s in CITIES:
        st, r = get("/markets", {"series_ticker": s, "status": "open", "limit": 200})
        if st != 200 or not isinstance(r, dict):
            continue
        for m in r.get("markets") or []:
            try:
                close = iso_ts(m["close_time"])
            except Exception:
                continue

            def f(k):
                try:
                    return float(m[k]) if m.get(k) is not None else None
                except (TypeError, ValueError):
                    return None
            snap[m["ticker"]] = {"a": f("yes_ask_dollars"), "b": f("yes_bid_dollars"), "last": f("last_price_dollars"),
                                 "vol": f("volume_fp"), "close": close, "exi": m.get("exchange_index"),
                                 "event": m.get("event_ticker"), "series": s}
    return snap


def make_fetch(get, log):
    def fetch(tickers, H):
        out = {}
        for i in range(0, len(tickers), 40):
            chunk = tickers[i:i + 40]
            st, r = get("/markets/candlesticks", {"market_tickers": ",".join(chunk), "start_ts": H - 3 * 3600,
                                                  "end_ts": H + 60, "period_interval": 60})
            if st != 200 or not isinstance(r, dict):
                log.write("error", where="candles", status=st, resp=str(r)[:200])
                continue
            for e in r.get("markets") or []:
                out[e.get("market_ticker")] = parse_candles(e)
        return out
    return fetch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--subaccount", type=int)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--minutes", type=float, default=21600)
    a = ap.parse_args()
    if not selftest():
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    if a.report:
        recs = [json.loads(x) for x in open(LIVE_LOG, encoding="utf-8")] if os.path.exists(LIVE_LOG) else []
        print(json.dumps(report(recs), indent=1))
        return 0
    why = sub_refusal(a.subaccount)
    if why:
        raise SystemExit(why)
    if a.live == a.dry_run:
        raise SystemExit("choose exactly one of --live / --dry-run")
    if a.live and os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    import ordercli
    pk = ordercli.load_key(KEY_FILE)

    def sender(method, path, body, query):
        return ordercli.send(ordercli.PROD, pk, KEY_ID, method, path, body=body, query=query)
    get = make_reader(sender)
    cash, pot, foreign = read_pot(sender, a.subaccount)
    why = start_refusal(pot, cash, foreign, a.live)
    if why:
        raise SystemExit(why + " -- refusing")
    path = LIVE_LOG if a.live else DRY_LOG
    prior = [json.loads(x) for x in open(path, encoding="utf-8")] if (a.live and os.path.exists(path)) else []
    log = Logger(path)
    start_pot = pot if (pot is not None and pot >= POT_MIN) else NOMINAL_POT
    dip = Dip(log, a.subaccount, a.dry_run, sender, time.time, start_pot)
    if prior:
        rebuild(dip, prior)
        if dip.start_pot_from_log:
            dip.start_pot = dip.start_pot_from_log       # the bar's -25% is of the FIRST start's pot
    dip.cash = cash
    log.write("start", pid=os.getpid(), subaccount=a.subaccount, live=a.live, cash=cash, pot=pot,
              start_pot=dip.start_pot, nominal_pot=(pot is None or pot < POT_MIN), t0=dip.t0,
              rebuilt={"orders": len(dip.orders), "fills": len(dip.fills()), "settled": len(dip.settled())},
              rails={"contracts": CONTRACTS, "max_open": MAX_OPEN, "one_order_per_market": True,
                     "window_s": WINDOW_S, "day_stop_frac": DAY_STOP_FRAC, "kill_after": KILL_AFTER,
                     "max_fills": MAX_FILLS, "max_days": MAX_DAYS, "pool": POOL, "writes_per_s": WRITES_PER_S},
              trigger={"drop_c": DROP_T / 10, "mid_c": [MID_LO_T / 10, MID_HI_T / 10], "spread_c": SPREAD_T / 10,
                       "min_vol": MIN_VOL, "hours_left": [HL_LO, HL_HI], "price": "candle ask close + 1c"},
              cities=CITIES, bar=BAR)
    threading.Thread(target=dip.run_writer, daemon=True).start()
    threading.Thread(target=dip.run_poller, daemon=True).start()
    fetch = make_fetch(get, log)
    t_end = time.time() + a.minutes * 60
    last_settle = 0.0
    stats = {"scans": 0, "max_watched": 0, "hours": 0, "triggers": 0, "acted": 0, "drop10_any_window": 0}
    try:
        while time.time() < t_end:
            t_scan = time.time()
            snap = scan(get)
            stats["scans"] += 1
            stats["max_watched"] = max(stats["max_watched"], len(snap))
            dip.tick(snap)
            H = int(t_scan // 3600) * 3600
            if (dip.last_H is None or H > dip.last_H) and t_scan >= H + EVAL_DELAY_S:
                act = (t_scan - H) <= STALE_S
                n = evaluate_hour(H, snap, fetch, log, dip.on_trigger, act)
                if act:
                    dip.last_H = H
                elif dip.last_H is None:
                    dip.last_H = H                      # the stale start hour: logged as diag, never acted on
                stats["hours"] += 1
                for k in ("triggers", "acted", "drop10_any_window"):
                    stats[k] += n[k]
            if time.time() - last_settle >= SETTLE_S:
                last_settle = time.time()
                dip.settle_check(get)
                if not a.dry_run:
                    c2, _, _ = read_pot(sender, a.subaccount)
                    if c2 is not None:
                        dip.cash = c2
            if dip.finished():
                break
            while time.time() < t_scan + SCAN_S and time.time() < t_end:
                if os.path.exists(STOP_FILE) and not dip.stopped:
                    break
                time.sleep(1.0)
    finally:
        dip.cancel_all("exit")
        dip.q.join()
        log.write("exit", stats=stats, open=dip.open_count(), fills=len(dip.fills()), settled=len(dip.settled()),
                  resting=[tk for tk, o in dip.orders.items() if o["status"] in ("resting", "cancel_failed")])
        print(json.dumps({"exit": stats, "fills": len(dip.fills()), "orders": len(dip.orders)}))
    return 0


# ==== SELF-TEST BELOW: nothing under this line runs outside --selftest ====
def selftest():
    try:
        return _selftest()
    except Exception as e:                          # a crash inside the self-test is a failure, never a pass
        print("dipsell_live self-test FAILED: exception %r" % (e,))
        return False


def _selftest():
    fails, sink, nck = [], [], [0]

    def ck(ok, m):
        nck[0] += 1
        if not ok:
            fails.append(m)
    log = Logger(sink=sink)
    sent = []
    clk = [1_790_960_400.0]                          # 2026-10-02 17:00:00Z, a Friday afternoon ET

    def fake_send(method, path, body, query):
        sent.append((method, path, body, query))
        if method == "POST":
            return 201, {"order": {"order_id": "K%d" % len(sent), "fill_count_fp": "0.00"}}
        if method == "GET" and path == "/portfolio/orders":
            return 200, {"orders": fake_orders}
        return 200, {}
    fake_orders = []
    H = 1_790_960_400                                 # candle close at 17:00Z
    close = H + 12 * 3600 - 3600                      # 11 h left
    c = lambda t, a, b, v=200.0: {"t": t, "a": a, "b": b, "v": v}
    # 1. the trigger: planted fires; a 9c drop, 13 h / 5.9 h left, thin hour, wide spread, out-of-range mid do not
    f, why, info = judge(c(H - 3600, 0.51, 0.49), c(H, 0.39, 0.37), close)
    ck(f and info["drop_c"] == -12.0 and info["mid"] == 0.38, "a 12c drop at 11 h left fires (%s %s)" % (why, info))
    ck(judge(c(H - 3600, 0.46, 0.44), c(H, 0.36, 0.34), close)[0], "exactly 10c (0.45 -> 0.35) fires (no float miss)")
    ck(judge(c(H - 3600, 0.50, 0.48), c(H, 0.41, 0.39), close)[1] == "no_drop", "a 9c drop does not fire")
    ck(judge(c(H - 3600, 0.51, 0.49), c(H, 0.39, 0.37), H + 13 * 3600)[1] == "hours_left", "13 h left does not fire")
    ck(judge(c(H - 3600, 0.51, 0.49), c(H, 0.39, 0.37), H + 12 * 3600)[1] == "hours_left", "exactly 12 h left does not fire")
    ck(judge(c(H - 3600, 0.51, 0.49), c(H, 0.39, 0.37), H + 6 * 3600)[0], "exactly 6 h left fires")
    ck(judge(c(H - 3600, 0.51, 0.49), c(H, 0.39, 0.37), H + int(5.9 * 3600))[1] == "hours_left", "5.9 h left does not fire")
    ck(judge(c(H - 3600, 0.51, 0.49), c(H, 0.39, 0.37, 49.0), close)[1] == "volume", "49 contracts in the hour does not fire")
    ck(judge(c(H - 3600, 0.51, 0.49), c(H, 0.45, 0.32), close)[1] == "bad_quote", "a 13c spread does not fire")
    ck(judge(c(H - 3600, 0.30, 0.28), c(H, 0.15, 0.13), close)[1] == "mid_range", "a new mid of 14c does not fire")
    ck(judge(c(H - 3600, 0.51, None), c(H, 0.39, 0.37), close)[1] == "bad_quote", "a missing bid does not fire")
    ck(judge(None, c(H, 0.39, 0.37), close)[1] == "no_candle", "no previous candle does not fire")
    pc = parse_candles({"candlesticks": [{"end_period_ts": H, "volume_fp": "120.5",
                                          "yes_ask": {"close_dollars": "0.3900"}, "yes_bid": {"close_dollars": "0.3700"}},
                                         {"end_period_ts": H - 3600, "volume_fp": "3",
                                          "yes_ask": {"close_dollars": "0.5100"}, "yes_bid": {}}]})
    ck(pc == [{"t": H - 3600, "a": 0.51, "b": None, "v": 3.0}, {"t": H, "a": 0.39, "b": 0.37, "v": 120.5}],
       "candles parse from the *_dollars fields, sorted, a missing field is None (%s)" % pc)
    # 2. NULL worlds through evaluate_hour: flat prices and a <10c random walk -> zero triggers
    import random
    rnd = random.Random(7)
    snapN = {"KXHIGHNY-N%d" % i: {"a": 0.5, "b": 0.49, "close": H + 8 * 3600, "exi": 0, "event": "E", "series": "KXHIGHNY"}
             for i in range(200)}
    flat = lambda tks, h: {tk: [c(h - 3600, 0.50, 0.48), c(h, 0.50, 0.48)] for tk in tks}

    def walk(tks, h):
        out = {}
        for tk in tks:
            m = rnd.randint(200, 800)
            d = rnd.randint(-9, 9) * 10
            out[tk] = [c(h - 3600, (m + 10) / 1000, (m - 10) / 1000), c(h, (m + d + 10) / 1000, (m + d - 10) / 1000)]
        return out
    got = []
    nf = evaluate_hour(H, snapN, flat, log, lambda t: got.append(t), True)
    nw = evaluate_hour(H, snapN, walk, log, lambda t: got.append(t), True)
    ck(nf["triggers"] == 0 and nw["triggers"] == 0 and not got and nf["with_candle"] == 200,
       "NULL: flat prices and a 9c-max walk over 200 markets -> 0 triggers (%s %s)" % (nf, nw))
    planted = lambda tks, h: {tk: ([c(h - 3600, 0.51, 0.49), c(h, 0.39, 0.37)] if tk.endswith("N5") else
                                   [c(h - 3600, 0.50, 0.48), c(h, 0.50, 0.48)]) for tk in tks}
    np_ = evaluate_hour(H, snapN, planted, log, lambda t: got.append(t), True)
    ck(np_["triggers"] == 1 and len(got) == 1 and got[0]["ticker"] == "KXHIGHNY-N5" and got[0]["a"] == 0.39,
       "a planted drop in 1 of 200 markets -> exactly that trigger (%s)" % np_)
    nd = evaluate_hour(H, snapN, planted, log, lambda t: got.append(t), False)
    ck(nd["triggers"] == 1 and len(got) == 1, "act=False (a stale hour) logs the trigger and places nothing")
    # 3. order body: post_only SELL YES (side ask) at a + 1c, 2 contracts, the subaccount, pool 0
    ck(safe_cid("dip-1791140400-KXHIGHTHOU-26OCT04-B81.5") == "dip-1791140400-KXHIGHTHOU-26OCT04-B81p5"
       and safe_cid("dip-1-KXHIGHTATL-26OCT04-T79") == "dip-1-KXHIGHTATL-26OCT04-T79",
       "client_order_id: '.' replaced (Kalshi 400s on it), plain ids unchanged")
    b = order_body("KXHIGHNY-26OCT02-B70.5", 0.40, 3, "dip-1-x", 0)
    ck(b["side"] == "ask" and b["price"] == "0.4000" and b["count"] == "2.00" and b["post_only"] is True
       and b["subaccount"] == 3 and b["exchange_index"] == 0 and body_ok(b, 3), "the body is a 2-lot post_only ask at 40c in sub 3 (%s)" % b)
    for desc, mut in (("post_only stripped", {"post_only": False}), ("subaccount 0", {"subaccount": 0}),
                      ("count 10", {"count": "10.00"}), ("a bid", {"side": "bid"}), ("pool 2", {"exchange_index": 2}),
                      ("foreign prefix", {"client_order_id": "lad-1"}), ("off-grid price", {"price": "0.4050"}),
                      ("price 0.99", {"price": "0.9900"}), ("not KXHIGH", {"ticker": "KXBTC15M-X"}),
                      ("IOC", {"time_in_force": "immediate_or_cancel"})):
        ck(not body_ok(dict(b, **mut), 3), "body refused: %s" % desc)
    ck(not body_ok(order_body("KXHIGHNY-X", 0.40, 0, "dip-1", 0), 0) and not body_ok(order_body("KXHIGHNY-X", 0.40, 1, "dip-1", 0), 1)
       and not body_ok(order_body("KXHIGHNY-X", 0.40, 2, "dip-1", 0), 2), "bodies for subaccounts 0, 1, 2 are refused")
    ck(sub_refusal(0) and sub_refusal(1) and sub_refusal(2) and sub_refusal(None) and sub_refusal(64) and sub_refusal(3) is None,
       "the start refuses subaccounts 0 (primary), 1 (ladder), 2 (forecaster), none and 64; 3 is allowed")
    ck(start_refusal(None, None, [], True) and start_refusal(100.0, 100.0, ["KXBTC15M-X"], True)
       and start_refusal(49.0, 49.0, [], True) and start_refusal(151.0, 151.0, [], True)
       and start_refusal(100.0, 100.0, [], True) is None and start_refusal(None, None, None, False) is None,
       "live start: unreadable pot, a foreign holding, <$50 and >$150 refused; $100 starts; a dry run is never refused")

    def run(d):
        while not d.q.empty():
            d.work_once(d.q.get())

    def trig(tk, a=0.39, h=H, close_=None, exi=0):
        return {"ticker": tk, "event": tk.rsplit("-", 1)[0], "series": "KXHIGHNY", "exi": exi,
                "close": close_ or h + 11 * 3600, "H": h, "a": a, "b": a - 0.02, "ask_now": a, "mid": a - 0.01}
    # 4. rails: 5 placed, the 6th refused (max_open), a 2nd order in one market refused, pool 2 refused
    d = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0)
    for i in range(5):
        ck(d.on_trigger(trig("KXHIGHNY-26OCT02-B%d" % i)) is None, "trigger %d placed" % i)
    run(d)
    posts = [s for s in sent if s[0] == "POST"]
    ck(len(posts) == 5 and all(body_ok(p[2], 3) and p[2]["price"] == "0.4000" for p in posts),
       "5 orders sent, each a legal 40c ask in sub 3")
    ck(d.on_trigger(trig("KXHIGHNY-26OCT02-B9")) == "max_open" and sink[-1]["why"] == "max_open", "the 6th open position is refused")
    ck(d.on_trigger(trig("KXHIGHNY-26OCT02-B0")) == "one_per_market", "a 2nd order in the same market is refused")
    ck(str(Dip(log, 3, False, fake_send, lambda: clk[0], 100.0).on_trigger(trig("KXHIGHNY-26OCT02-P2", exi=2))).startswith("pool"),
       "a market outside pool 0 is refused")
    # 5. a fill is held; the window cancels the remainder in the subaccount; a filled market still counts open
    fake_orders[:] = [{"order_id": d.orders["KXHIGHNY-26OCT02-B0"]["kid"], "fill_count_fp": "1.00", "status": "resting"}]
    clk[0] = H + 600
    d.poll_fills_once()
    ck(d.orders["KXHIGHNY-26OCT02-B0"]["filled"] == 1.0 and sink[-1]["ev"] == "fill" and sink[-1]["min_to_fill"] == 10.0,
       "a partial fill (1 of 2) is booked with minutes-to-fill 10.0")
    snap = {tk: {"a": 0.45, "last": 0.47} for tk in d.orders}
    d.tick(snap, stop_file=STOP_FILE + ".never")
    ck(d.orders["KXHIGHNY-26OCT02-B0"]["max_ask"] == 0.45 and d.orders["KXHIGHNY-26OCT02-B0"]["max_last"] == 0.47,
       "max ask / max last in the 3 h window are tracked")
    n_del = len([s for s in sent if s[0] == "DELETE"])
    clk[0] = H + 3 * 3600 - 60                       # the spec's window is 3 h: nothing is cancelled a minute early
    d.tick({}, stop_file=STOP_FILE + ".never")
    run(d)
    ck(len([s for s in sent if s[0] == "DELETE"]) == n_del, "2 h 59 min after the candle nothing is cancelled")
    clk[0] = H + 3 * 3600
    d.tick({}, stop_file=STOP_FILE + ".never")
    run(d)
    dels = [s for s in sent if s[0] == "DELETE"][n_del:]
    ck(len(dels) == 5 and all(s[3]["subaccount"] == 3 and s[3]["exchange_index"] == 0 for s in dels)
       and any(r["ev"] == "window_end" for r in sink), "3 h after the candle every unfilled order is cancelled, in the subaccount")
    ck(d.open_count() == 1, "after the window only the filled market is open (%d)" % d.open_count())
    ck(d.on_trigger(trig("KXHIGHNY-26OCT02-B9", h=H + 3 * 3600)) is None, "with 1 open a new market is placed again")
    # 6. settlement booking: empty result books nothing; NO pays px a contract; YES costs 1 - px
    clk[0] = H + 11 * 3600 + 60
    ck(d.on_result("KXHIGHNY-26OCT02-B0", "") is None and not d.orders["KXHIGHNY-26OCT02-B0"]["settled"],
       "an empty result books nothing")
    p = d.on_result("KXHIGHNY-26OCT02-B0", "no")
    ck(abs(p - 0.40) < 1e-9 and sink[-1]["pnl_c"] == 40.0 and sink[-1]["day"] == "2026-10-02",
       "a NO settlement on 1 contract sold at 40c books +$0.40 (+40c a contract), day 2026-10-02 ET")
    d2 = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0)
    d2.on_trigger(trig("KXHIGHCHI-26OCT02-B1"))
    run(d2)
    d2.on_fill("KXHIGHCHI-26OCT02-B1", 2.0, 0.0)
    p = d2.on_result("KXHIGHCHI-26OCT02-B1", "yes")
    ck(abs(p + 1.20) < 1e-9 and sink[-1]["pnl_c"] == -60.0, "a YES settlement on 2 sold at 40c books -$1.20 (-60c a contract)")
    ck(d2.on_result("KXHIGHCHI-26OCT02-B1", "no") is None, "a market settles once")
    # 7. day stop: the ET day's cohort at -25% of the pot halts the day and cancels; the next ET day resumes
    d3 = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0)
    clk[0] = H + 600
    for i in range(3):
        d3.on_trigger(trig("KXHIGHNY-26OCT02-D%d" % i))
    run(d3)
    for tk in list(d3.orders)[:2]:
        d3.on_fill(tk, 2.0, 0.0)
    d3.tick({tk: {"a": 0.39} for tk in d3.orders}, stop_file=STOP_FILE + ".never")
    ck(d3.halt_day is None, "a flat day does not halt")
    for i, tk in enumerate(list(d3.orders)[:2]):
        d3.orders[tk]["filled"] = 20.0       # as if sized 10x: 2 x 20 short YES at 40c, ask now 99c -> -$23.60
    d3.tick({tk: {"a": 0.99} for tk in d3.orders}, stop_file=STOP_FILE + ".never")
    ck(d3.halt_day is None, "a marked day of -$23.60 on a $100 pot (-23.6%) does not halt")
    d3.orders[list(d3.orders)[0]]["fees"] = 1.50
    d3.tick({tk: {"a": 0.99} for tk in d3.orders}, stop_file=STOP_FILE + ".never")
    run(d3)
    ck(d3.halt_day == "2026-10-02" and any(r["ev"] == "day_stop" for r in sink)
       and d3.orders[list(d3.orders)[2]]["status"] == "cancelled",
       "-$25.10 (-25.1%) halts the ET day and cancels the resting order")
    ck(d3.on_trigger(trig("KXHIGHNY-26OCT02-D9")) == "day_stop", "no new order on the halted day")
    clk[0] = H + 86400
    ck(d3.on_trigger(trig("KXHIGHNY-26OCT03-D9", h=H + 86400 - 600)) is None, "the next ET day places again")
    # 8. the 60-fill kill: 60 settled with net < 0 kills; 59 negative or 60 positive does not
    for n_fills, pnl_each, want in ((59, -0.10, False), (60, -0.01, True), (60, +0.05, False)):
        d4 = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0)
        for i in range(n_fills):
            d4.orders["K%d" % i] = {"ticker": "K%d" % i, "day": "2026-10-02", "filled": 2.0, "settled": True,
                                    "pnl": pnl_each, "status": "closed", "H": H, "px": 0.4, "fees": 0.0,
                                    "max_ask": None, "max_last": None, "window_logged": True}
        d4.orders["R"] = {"ticker": "R", "day": "2026-10-04", "filled": 0, "settled": False, "status": "resting",
                          "H": clk[0], "px": 0.4, "fees": 0.0, "max_ask": None, "max_last": None, "window_logged": False,
                          "kid": "KR"}
        d4.tick({}, stop_file=STOP_FILE + ".never")
        ck(d4.killed == want, "%d settled fills at %+.2f each: killed=%s (want %s)" % (n_fills, pnl_each, d4.killed, want))
        if want:
            ck(d4.orders["R"]["status"] == "cancelling" and d4.on_trigger(trig("KXHIGHNY-Z")) == "killed",
               "the kill cancels the resting order and refuses new ones")
    # 9. stop at 100 fills or 14 days
    d5 = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0)
    for i in range(100):
        d5.orders["F%d" % i] = {"ticker": "F%d" % i, "day": "2026-10-02", "filled": 2.0, "settled": True, "pnl": 0.1,
                                "status": "closed", "H": H, "px": 0.4, "fees": 0.0, "max_ask": None, "max_last": None,
                                "window_logged": True}
    d5.tick({}, stop_file=STOP_FILE + ".never")
    ck(d5.done and d5.on_trigger(trig("KXHIGHNY-Y")) == "done" and d5.finished(), "100 fills: done, no new order, finished")
    d6 = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0, t0=clk[0] - 14 * 86400)
    d6.tick({}, stop_file=STOP_FILE + ".never")
    ck(d6.done and d6.on_trigger(trig("KXHIGHNY-Y")) == "done", "14 days after the first start: done")
    d6b = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0, t0=clk[0] - 13.9 * 86400)
    d6b.tick({}, stop_file=STOP_FILE + ".never")
    ck(not d6b.done, "13.9 days: not done")
    # 10. stop file cancels everything
    d7 = Dip(log, 3, False, fake_send, lambda: clk[0], 100.0)
    d7.on_trigger(trig("KXHIGHNY-S1"))
    run(d7)
    sf = STOP_FILE + ".selftest"
    open(sf, "w").close()
    try:
        d7.tick({}, stop_file=sf)
        run(d7)
    finally:
        os.remove(sf)
    ck(d7.stopped and d7.orders["KXHIGHNY-S1"]["status"] == "cancelled" and d7.finished(),
       "the stop file cancels the resting order and the bot is finished")
    # 10b. a cancel that 404s (already filled or gone) counts open for 5 min, then can never wedge the rails
    def send404(method, path, body, query):
        return (404, "not found") if method == "DELETE" else fake_send(method, path, body, query)
    d7b = Dip(log, 3, False, send404, lambda: clk[0], 100.0)
    d7b.on_trigger(trig("KXHIGHNY-L1"))
    run(d7b)
    d7b.cancel_all("window")
    run(d7b)
    ck(d7b.orders["KXHIGHNY-L1"]["status"] == "cancel_failed" and d7b.open_count() == 1, "a 404 cancel still counts open")
    clk[0] += 301
    ck(d7b.open_count() == 0, "after 5 min a 404 cancel with nothing filled no longer counts")
    clk[0] -= 301
    # 11. dry run sends nothing
    n0 = len(sent)
    d8 = Dip(log, 3, True, fake_send, lambda: clk[0], 100.0)
    d8.on_trigger(trig("KXHIGHNY-DRY"))
    run(d8)
    d8.cancel_all("exit")
    run(d8)
    ck(len(sent) == n0 and any(r["ev"] == "would_place" for r in sink), "dry run sends nothing (placed and cancelled on paper)")
    # 12. the bar from a planted log, reconciled by hand
    P = [
        {"ev": "start", "live": True, "start_pot": 100.0},
        {"ev": "trigger", "act": True}, {"ev": "trigger", "act": True}, {"ev": "trigger", "act": True},
        {"ev": "trigger", "act": True}, {"ev": "rail_refused"},
        {"ev": "placed", "ticker": "A"}, {"ev": "placed", "ticker": "B"}, {"ev": "placed", "ticker": "C"},
        {"ev": "rejected", "ticker": "D"},
        {"ev": "fill", "ticker": "A", "filled": 2}, {"ev": "fill", "ticker": "B", "filled": 2},
        {"ev": "settle", "ticker": "A", "pnl": 0.80, "n": 2, "day": "2026-10-05"},
        {"ev": "settle", "ticker": "B", "pnl": -1.20, "n": 2, "day": "2026-10-06"}]
    rp = report(P)
    ck(rp["sent"] == 4 and rp["filled_orders"] == 2 and rp["fill_rate"] == 0.5 and rp["triggers"] == 4
       and rp["rejected"] == 1 and rp["net_c"] == -10.0 and rp["worst_day_pct"] == -1.2 and rp["pass_fill"]
       and not rp["pass_net"] and not rp["pass"], "bar: 2 of 4 sent filled (50%%), net -10c a contract, worst day -1.2%% (%s)" % rp)
    # se by hand: r = -0.1; day residuals 0.8+0.2 = 1.0 and -1.2+0.2 = -1.0; sqrt(2/1 * 2) / 4 = 0.5 -> 50c
    ck(rp["se_c"] == 50.0 and rp["low_c"] == -60.0, "bar: day-clustered se 50c, low end -60c (%s %s)" % (rp["se_c"], rp["low_c"]))
    # 13. rebuild from a live log keeps one-per-market, the holding, the fill count and the first start
    recs = [{"ev": "start", "live": True, "t0": 1000.0, "start_pot": 98.5},
            {"ev": "trigger", "act": True, "ticker": "KXHIGHNY-R1", "close": H + 9 * 3600, "event": "E", "series": "KXHIGHNY"},
            {"ev": "placed", "ticker": "KXHIGHNY-R1", "order_id": "OID1", "H": H, "a": 0.39,
             "body": {"price": "0.4000", "exchange_index": 0, "client_order_id": "dip-x"}},
            {"ev": "fill", "ticker": "KXHIGHNY-R1", "filled": 2.0, "fees": 0.0, "t": "2026-10-02T17:05:00Z"},
            {"ev": "hour_eval", "act": True, "H": H}]
    d9 = rebuild(Dip(log, 3, False, fake_send, lambda: clk[0], 100.0), recs)
    o9 = d9.orders.get("KXHIGHNY-R1") or {}
    ck(d9.t0 == 1000.0 and d9.start_pot_from_log == 98.5 and "KXHIGHNY-R1" in d9.used and o9.get("kid") == "OID1"
       and o9.get("filled") == 2.0 and o9.get("close") == H + 9 * 3600 and d9.last_H == H and len(d9.fills()) == 1
       and d9.on_trigger(trig("KXHIGHNY-R1")) == "one_per_market", "rebuild: t0, pot, the order, its fill and close, last hour")
    # 14. ET day: EDT in October, EST after the November change
    ck(et_day(calendar.timegm((2026, 10, 3, 3, 59, 0))) == "2026-10-02" and et_day(calendar.timegm((2026, 10, 3, 4, 0, 0))) == "2026-10-03"
       and et_day(calendar.timegm((2026, 11, 3, 4, 30, 0))) == "2026-11-02", "ET day boundaries (EDT 04:00Z, EST 05:00Z)")
    # 15. the working code has exactly one POST (create order), one DELETE (cancel), and no money movement
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.index("# ==== SELF" + "-TEST BELOW")]
    ck(body.count('"POST"') == 1 and body.count('"DELETE"') == 1 and "/portfolio/subaccounts" not in body
       and "intra_exchange" not in body and "transfer" not in body.lower(),
       "the working code has one POST (create order), one DELETE (cancel), no subaccount/transfer endpoint")
    print("dipsell_live self-test " + ("PASSED (%d checks)" % nck[0] if not fails
                                       else "FAILED %d of %d: " % (len(fails), nck[0]) + "; ".join(fails)))
    return not fails


if __name__ == "__main__":
    sys.exit(main())
