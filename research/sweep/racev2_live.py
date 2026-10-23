#!/usr/bin/env python3
"""racev2_live.py -- COIN RACE REWARD FILLER v2, THE 20-RACE LIVE TEST, SUBACCOUNT 4 ONLY.

THE OPERATOR, 2026-10-22 ~07:0xZ: "Build race v2." (the coin-race v2 reward live test: 20 races in subaccount 4, the most
it can lose about $45). Spec: .sweep/hunt-2026-10-15/spec-20261015-R1-C2-02/SPEC.md section 3 ("Part B"), bars 4.2.
The paper gate (spec 4.1, racev2_shadow.py code_sha 291531c22395) read RECOMMEND on 2026-10-20: 269 races, 2.13 placed
legs a race, x99 fill cost 28.6% of paid credit.

WHAT IT IS
  research/sweep/racereward_live.py (v1, code_sha c73979198066) IMPORTED, not copied: its Bot is subclassed and only the
  Part B changes are overridden, so every v1 rail (N1-N10) is the same code. The decisions are the shadow's: the same
  rr.leg_refusal, the same projection arithmetic, the same constants (the self-test compares them to racev2_shadow.py
  and replays planted legs through BOTH files). Both files are pinned by sha: a changed rr or shadow refuses to run.
  Part B (spec section 3):
    1  exit 115 s: the bot's own cancel is SENT at close-116 s; no new order from close-115 s; quiet zone from close-130.
    2  two floors: pay floor $1.00 (rr.floored), post floor $1.25 (floor_check).
    3  size min(1,100, target + 100); max collateral $40 (resting + held); start floor $40.
    4  server-side expiry: every body carries expiration_time = int(close - 115) and cancel_order_on_pause true, still
       good_till_canceled. DEMO PROBE 2026-10-22 07:05Z (.sweep/q-2026-10-22/racev2-live/demo_expiry_probe.json):
       accepted (201); Kalshi took it off the resting list within 0.38 s of expiration_time (last_update +0.03 s);
       the status string after expiry is "canceled" (not "expired").
    5  expiry is not an alarm: an order Kalshi reports final with no cancel from us, first seen at or after
       expiration_time - 1, is logged 'expired'; only an EARLIER unrequested cancel is N8 'exchange_cancelled'.
    6  starved cancel: YES side incl. our remaining < target for 5 consecutive seconds -> cancel 'starved'.
    7  race sampling --every N (default 3): only races whose close index ((close mod 1 day) / 15 min) % N == 0.
    8  logging: exchange-time fills (GET /portfolio/fills after each race), fills by window (360-240 / 240-180 /
       180-115 s), largest print, projected_at_place, the July-walk credit (shadow's snapshot_july, 99c NO removed)
       and its paid model (0.987 x, $0 under $1), and control legs (dead legs we did not post: 1c sales + 99c-NO adds).
    10 new paths; v1's stop/state files are never read or touched.
    11 the money lands in MAIN pool 0: the bot reads main pool 0 every 5 min (GET) and --report reads it again.
    12 payment tripwire: 4 h after the windows of the first 2 races with an order, if main pool 0 has not risen by >= 50%
       of their summed paid-model credit, the bot writes its stop file, logs 'payment_missing' and stops.
  NOT here (spec 13): the credit-aware budget is v3, after a PASS, with its own sign-off.

HARD RAILS (code, not flags; --selftest proves each one refuses)
  SUBACCOUNT 4 ONLY (args, start, every body, every DELETE/GET query); at most 20 races with an order, then cancel all and
  exit (also across restarts: state file); stake cap: 1,100 contracts x $0.01 = $11 an order, <= 5 resting, collateral
  resting + held <= $40, day budget/day stop -$30 (rail f), TEST STOP -$45 over the whole test (all days, unsettled
  fills counted lost; survives a restart), start only with $40..$50 in sub 4 pool 2; stop file results/racev2-live.stop
  (also results/racereward-v2-live.stop) cancels everything and exits, and refuses a start; post_only always; price is
  exactly 0.0100 (no price argument exists); every order body is checked twice -- by body_ok before the bot sends it
  and again by the guarded sender, which also refuses any POST that is not a create-order, any DELETE that is not an
  order cancel in subaccount 4, any PUT/PATCH, and any non-GET at all in --dry-run / --report; one process per mode.
  Backstops no code can break: expiration_time at close-115 s, and Kalshi cancels everything at the close.

LOGS (UTC 't', 'ev'): results/racereward-v2-live.jsonl (the name the shadow's 4.3 calibration reads), dry run
  results/racereward-v2-dry.jsonl. State results/racereward-v2-live.state.json. Lock results/racereward-v2-live.lock.

    python research/sweep/racev2_live.py --selftest [-v]
    python research/sweep/racev2_live.py --subaccount 4 --dry-run --races 2      (GET only; would_place / would_cancel)
    python research/sweep/racev2_live.py --subaccount 4 --live                   (operator only, after funding)
    python research/sweep/racev2_live.py --subaccount 4 --report                 (GET only: C, M, P and the 4.2 verdict)

THE BAR (spec 4.2, pre-registered 2026-10-16, unchanged): first 20 races with >= 1 v2 order. C = filled contracts x $0.01
  on test legs; M = sum of paid-model credit (July walk on the bot's per-second snapshots x 0.987, $0 under $1.00) over
  legs whose projection at placement was >= $1.25 (all of them, by the post floor); P = main pool 0 increase over the
  test. Read 2 h after the last race (provisional) and 48 h after it (final, with paid_out flags).
  PASS C <= 0.25 M AND P >= 0.90 M. KILL C > 0.50 M or P < 0.50 M at 48 h. Between: EXTEND by 20 races (a new sign-off).
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone


def _find_repo():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(d, "research", "sweep", "racereward_live.py")):
            return d
        d = os.path.dirname(d)
    return r"C:\kals-repo"


REPO = _find_repo()
RESEARCH = os.path.join(REPO, "research")
SWEEP = os.path.join(RESEARCH, "sweep")
for _p in (SWEEP, RESEARCH):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import racereward_live as rr      # noqa: E402  (v1: its Bot, rails, walk, books, InstanceLock)
import racev2_shadow as sh        # noqa: E402  (the paper shadow: its constants and July walk)

RR_SHA = "c73979198066"            # racereward_live.py the decisions were validated against
SH_SHA = "291531c22395"            # racev2_shadow.py whose gate read RECOMMEND (2026-10-20)
RESULTS = rr.RESULTS
SUB = 4                            # THE ONLY subaccount this file can use
POOL = rr.POOL                     # 2
PRICE = rr.PRICE                   # "0.0100"
SERIES = rr.SERIES
EXIT_S = 115.0                     # spec 3.1 (== sh.EXIT_S)
OWN_CANCEL_LEAD_S = 1.0            # our own exit cancel is SENT at close - 116 s, before the server expiry at close - 115
COUNT_CAP = 1100                   # spec 3.3 (== sh.COUNT_CAP)
CUSHION = 100
POST_FLOOR_USD = 1.25              # spec 3.2 (== sh.POST_FLOOR)
PAY_FLOOR_USD = rr.FLOOR_USD       # 1.00
PAID_FACTOR = 0.987                # the 10-11 paid / filing-walk ratio (== sh.PAID_FACTOR)
STARVE_N = 5                       # spec 3.6 (== sh.STARVE_N)
STARVE_GRACE_S = 2.0               # seconds after placement before the socket must show our own size
MAX_COLLATERAL = 40.00             # spec 3.3 (== sh.MAX_COLLATERAL_V2)
MAX_RESTING = rr.MAX_RESTING       # 5
DAY_STOP = rr.DAY_STOP             # -30
TEST_STOP = -45.00                 # the operator's "the most it can lose about $45", across the whole test
BAL_MIN, BAL_MAX = 40.00, 50.00    # sub 4 pool 2 cash at start
RACES_MAX = 20                     # hard: --races may be lower, never higher
EVERY_DEFAULT = 3                  # spec 3.7 / 4.2
EXPIRY_MIN_AHEAD_S = 30.0          # spec 3.4: expiration_time must be > now + 30 s ...
EXPIRY_MAX_AHEAD_S = rr.WINDOW_S + 5.0   # ... and (guard) never more than the 360 s window ahead
CID_PREFIX = "rv2-"
POOL0_EVERY_S = 300.0              # spec 3.11: main pool 0 read every 5 min
TRIP_RACES, TRIP_WAIT_S, TRIP_FRAC = 2, 4 * 3600.0, 0.50     # spec 3.12
PROVISIONAL_H, FINAL_H = 2.0, 48.0
FILL_WINDOWS = ((360, 240), (240, 180), (180, 115))
LIVE_LOG = os.path.join(RESULTS, "racereward-v2-live.jsonl")
DRY_LOG = os.path.join(RESULTS, "racereward-v2-dry.jsonl")
LIVE_STATE = os.path.join(RESULTS, "racereward-v2-live.state.json")
DRY_STATE = os.path.join(RESULTS, "racereward-v2-dry.state.json")
LIVE_LOCK = os.path.join(RESULTS, "racereward-v2-live.lock")
DRY_LOCK = os.path.join(RESULTS, "racereward-v2-dry.lock")
STOP_FILE = os.path.join(RESULTS, "racev2-live.stop")
STOP_ALIAS = os.path.join(RESULTS, "racereward-v2-live.stop")
REPORT_LOG = os.path.join(RESULTS, "racev2-live-report.jsonl")
ON_BOOK, CONFIRMABLE = rr.ON_BOOK, rr.CONFIRMABLE
f = rr.f
utc_iso, et_day, parse_ts = rr.utc_iso, rr.et_day, rr.parse_ts


def file_sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def code_sha():
    return file_sha(os.path.abspath(__file__))


def pins_ok():
    """The decisions are the ones validated on paper only while both imported files are byte-identical."""
    a, b = file_sha(rr.__file__), file_sha(sh.__file__)
    return (a == RR_SHA and b == SH_SHA), {"rr_sha": a, "shadow_sha": b}


# ------------------------------------------------------------------------------------------------ rules (pure)
def count_for(prog):
    """spec 3.3: min(1,100, round(target) + 100)."""
    return int(min(COUNT_CAP, max(1, round(prog["target"]) + CUSHION)))


def race_index(close):
    return int((int(round(close)) % 86400) // 900)


def sampled(close, every):
    """spec 3.7: place only in races whose close index (minutes since midnight UTC / 15) is divisible by N."""
    return race_index(close) % int(every) == 0


def expiry_for(close):
    return int(close - EXIT_S)


def order_body(ticker, count, cid, close):
    """Buy YES at exactly $0.01 in subaccount 4, expiring at close-115 s. There is no price or subaccount argument."""
    b = rr.order_body(ticker, count, SUB, cid)
    b["expiration_time"] = expiry_for(close)
    b["cancel_order_on_pause"] = True
    return b


BODY_KEYS = frozenset(("ticker", "side", "count", "price", "time_in_force", "self_trade_prevention_type", "post_only",
                       "client_order_id", "subaccount", "exchange_index", "expiration_time", "cancel_order_on_pause"))


def body_ok(b, now, close=None):
    """Every order body must pass this, or it is not sent. close=None (the guarded sender) checks the expiry window
    instead of the exact close-115 value."""
    if not isinstance(b, dict) or set(b) != BODY_KEYS:
        return False
    try:
        c = float(b.get("count"))
    except (TypeError, ValueError):
        return False
    exp = b.get("expiration_time")
    if not isinstance(exp, int) or isinstance(exp, bool):
        return False
    if close is not None and exp != expiry_for(close):
        return False
    if not (now + EXPIRY_MIN_AHEAD_S < exp <= now + EXPIRY_MAX_AHEAD_S):
        return False
    return (b.get("post_only") is True and b.get("subaccount") == SUB and type(b.get("subaccount")) is int
            and b.get("exchange_index") == POOL and b.get("price") == PRICE and b.get("side") == "bid"
            and 0 < c <= COUNT_CAP and b.get("self_trade_prevention_type") == "maker"
            and b.get("time_in_force") == "good_till_canceled" and b.get("cancel_order_on_pause") is True
            and str(b.get("client_order_id", "")).startswith(CID_PREFIX)
            and str(b.get("ticker", "")).startswith(SERIES + "-"))


ORDER_PATH = "/portfolio/events/orders"


def guard_refusal(method, path, body, query, now, writes_ok):
    """The guarded sender's check of EVERY request (None = may go out). writes_ok False = --dry-run / --report."""
    q = query or {}
    if "subaccount" in q and str(q["subaccount"]) != str(SUB):
        return "a query for subaccount %s (only %d)" % (q["subaccount"], SUB)
    if method == "GET":
        return None
    if not writes_ok:
        return "%s in a GET-only mode" % method
    if method == "POST":
        if path != ORDER_PATH:
            return "POST to %s (only %s)" % (path, ORDER_PATH)
        if not body_ok(body, now):
            return "order body failed body_ok: %s" % json.dumps(body, default=str)[:300]
        return None
    if method == "DELETE":
        if not (path.startswith(ORDER_PATH + "/") and "/" not in path[len(ORDER_PATH) + 1:]
                and len(path) > len(ORDER_PATH) + 1):
            return "DELETE of %s (only an order cancel)" % path
        if str(q.get("subaccount")) != str(SUB) or str(q.get("exchange_index")) != str(POOL):
            return "DELETE without subaccount %d / exchange_index %d" % (SUB, POOL)
        return None
    return "method %s refused" % method


def guarded(sender, writes_ok, clock=time.time):
    def s(method, path, body, query, timeout=None):
        why = guard_refusal(method, path, body, query, clock(), writes_ok)
        if why:
            raise RuntimeError("GUARD REFUSED: " + why)
        return sender(method, path, body, query, timeout=timeout)
    return s


def read_main_pool0(sender):
    """MAIN account cash in pool 0 (where Kalshi pays coin-race rewards), or None. `balance` (cents) and
    `balance_dollars` must both be present and agree (hard rule 5); pool 0 from balance_breakdown (lipwatch's read)."""
    st, b = sender("GET", "/portfolio/balance", None, None)
    try:
        d, c = float(b["balance_dollars"]), float(b["balance"])
        if st != 200 or abs(c / 100.0 - d) > 0.011:
            return None
        pools = {int(x["exchange_index"]): float(x["balance"]) for x in b.get("balance_breakdown") or []}
        return pools[0] if 0 in pools else None
    except Exception:
        return None


def start_refusal(sub, balance, state, races_max, now, stop_paths, day=(0.0, 0.0)):
    """Every reason the bot may NOT start live. None = ok."""
    if sub is None or int(sub) != SUB:
        return "subaccount %s refused: this test runs in subaccount %d only" % (sub, SUB)
    if not (1 <= int(races_max) <= RACES_MAX):
        return "--races %s outside 1..%d" % (races_max, RACES_MAX)
    if balance is None:
        return "subaccount %d balance (pool %d) is unreadable" % (SUB, POOL)
    if balance < BAL_MIN - 1e-9:
        return "subaccount %d holds $%.2f in pool %d, under the $%.0f floor" % (SUB, balance, POOL, BAL_MIN)
    if balance > BAL_MAX + 1e-9:
        return "subaccount %d holds $%.2f in pool %d, over the $%.0f ceiling" % (SUB, balance, POOL, BAL_MAX)
    if state.get("test_halted"):
        return "the -$%.0f test stop was hit (state file: %s)" % (-TEST_STOP, state.get("test_halted"))
    if state.get("halted_day") == et_day(now):
        return "day stop already hit on %s (state file)" % state["halted_day"]
    if state.get("payment_missing"):
        return "payment tripwire fired (state file: %s)" % state.get("payment_missing")
    if day is None:
        return "today's settled P&L / open positions in subaccount %d are unreadable" % SUB
    if day[1] > 0:
        return "subaccount %d holds $%.2f of open positions; start when it is flat" % (SUB, day[1])
    if day[0] <= DAY_STOP + 1e-9:
        return "today's settled P&L in subaccount %d is $%.2f <= the $%.0f day stop" % (SUB, day[0], DAY_STOP)
    if len(state.get("races") or []) >= races_max:
        return "%d races with an order already done (state file) >= %d" % (len(state["races"]), races_max)
    for p in stop_paths:
        if os.path.exists(p):
            return "stop file present: %s" % p
    return None


def window_of(left):
    for hi, lo in FILL_WINDOWS:
        if lo <= left < hi or (hi == 360 and left >= 360):
            return "%d-%d" % (hi, lo)
    return "other"


# ------------------------------------------------------------------------------------------------ the bot
class Bot(rr.Bot):
    def __init__(self, log, dry, sender, now, books, state_path, stop_path, races_max, every=EVERY_DEFAULT,
                 sleep=time.sleep, stop_alias=None):
        super().__init__(log, SUB, dry, sender, now, books, state_path, stop_path, min(int(races_max), RACES_MAX),
                         sleep=sleep, exit_s=EXIT_S)
        self.every = int(every)
        self.post_floor = POST_FLOOR_USD
        self.stop_alias = stop_alias
        for k, v in (("test_halted", None), ("pool0_base", None), ("race_paid", {}), ("payment_missing", None),
                     ("trip_done", False)):
            self.state.setdefault(k, v)
        self.last_pool0 = -1e18
        self.sampled_out = set()

    # ---------------- rails ----------------
    def test_realized(self):
        return sum(d.get("realized", 0.0) for d in self.state["days"].values())

    def rails_refusal(self, count, t, evt=None):
        if self.stopping:
            return "stopping:" + self.stopping
        if self.state.get("test_halted"):
            return "test_stop"
        if self.halted(t):
            return "day_stop"
        if evt not in self.state["races"] and len(self.state["races"]) >= self.races_max:
            return "races_done"
        if len(self.resting()) >= MAX_RESTING:
            return "max_resting"
        if count > COUNT_CAP:
            return "count_cap"
        if self.collateral() + 0.01 * count > MAX_COLLATERAL + 1e-9:
            return "max_collateral"
        at_risk = self.unsettled_cost() + self.resting_collateral() + 0.01 * count
        if self._day(t)["realized"] - at_risk < DAY_STOP - 1e-9:
            return "day_budget"
        if self.test_realized() - at_risk < TEST_STOP - 1e-9:
            return "test_budget"
        return None

    def check_day_stop(self, t):
        super().check_day_stop(t)
        worst = self.test_realized() - self.unsettled_cost()
        if worst <= TEST_STOP + 1e-9 and not self.state.get("test_halted"):
            self.state["test_halted"] = utc_iso(t)
            self.save()
            self.log.write("test_stop", realized=round(self.test_realized(), 4),
                           unsettled_cost=round(self.unsettled_cost(), 4), worst=round(worst, 4))
            self.stopping = self.stopping or "test_stop"

    @staticmethod
    def count_for(prog):
        return count_for(prog)

    def floor_check(self, r, tk, yes_lv, no_lv, prog, count, t):
        """rr.Bot.floor_check's arithmetic (== shadow.projection) against the $1.25 POST floor."""
        sn = rr.snapshot(yes_lv, no_lv, count, prog, r["linear"].get(tk, True))
        end = self.exit_t(r)
        if prog.get("end"):
            end = min(end, prog["end"])
        start = max(t, prog.get("start") or t)
        secs = max(0.0, end - start - rr.FLOOR_MARGIN_S)
        proj = rr.credit(prog["reward"], rr.period_of(prog), secs * sn["sh"])
        return proj >= self.post_floor - 1e-9, proj, sn["sh"]

    # ---------------- discovery: --every ----------------
    def discover(self, t):
        out = super().discover(t)
        keep = {}
        for evt, e in out.items():
            if sampled(e["close"], self.every):
                keep[evt] = e
            elif evt not in self.sampled_out and e["close"] - t <= rr.PREP_S:
                self.sampled_out.add(evt)
                self.log.write("sampled_out", evt=evt, close=utc_iso(e["close"]), index=race_index(e["close"]),
                               every=self.every)
        return keep

    def prepare(self, evt, e, t):
        super().prepare(evt, e, t)
        r = self.races[evt]
        r["ctl"], r["starve"] = {}, {}

    # ---------------- writes ----------------
    def place(self, r, tk, prog, nums, t):
        """rr.Bot.place with the v2 body (expiration_time, cancel_order_on_pause, 1,100, subaccount 4, rv2- ids)."""
        coin = r["coin_of"][tk]
        count = self.count_for(prog)
        if t >= self.exit_t(r) or self.quiet(t):
            self._once(r, tk, "past_exit", left=round(r["close"] - t, 1))
            return
        why = self.rails_refusal(count, t, r["evt"])
        if why:
            self._once(r, tk, "rail_" + why, left=round(r["close"] - t, 1), **nums)
            return
        legs = self.state.setdefault("legs", {})
        if coin in (legs.get(r["evt"]) or []):
            r["done"].add(tk)
            self._once(r, tk, "already_ordered", left=round(r["close"] - t, 1))
            return
        oid = self.next_id
        self.next_id += 1
        cid = "%s%d-%d" % (CID_PREFIX, int(time.time()), oid)
        b = order_body(tk, count, cid, r["close"])
        if not body_ok(b, self.now(), r["close"]):
            self.log.write("body_refused", body=b)
            r["done"].add(tk)
            return
        legs.setdefault(r["evt"], []).append(coin)
        for k in list(legs)[:-rr.LEGS_KEEP]:
            del legs[k]
        if r["evt"] not in self.state["races"]:
            self.state["races"].append(r["evt"])
        r["done"].add(tk)
        if not self.save():
            self.log.write("refused_state_unwritable", evt=r["evt"], coin=coin)
            return
        o = {"id": oid, "evt": r["evt"], "tk": tk, "coin": coin, "cid": cid, "kid": None, "count": float(count),
             "filled": 0.0, "cost": 0.0, "fees": 0.0, "status": "sending", "placed_t": t, "close": r["close"],
             "queue_ahead": nums.get("y1c", 0.0), "cancel_why": None, "tries": 0, "final": False, "unseen": 0,
             "cancel_try_t": None, "cancel_sent_t": None, "cancel_t": None, "exp": b["expiration_time"],
             "proj": nums.get("projected"), "prog_id": prog.get("id")}
        self.orders[oid] = o
        r["placed"][tk] = oid
        r["counted"] = True
        if self.dry:
            o["status"], o["kid"] = "resting", "dry-%d" % oid
            self.log.write("would_place", evt=r["evt"], coin=coin, left=round(r["close"] - t, 1), body=b, **nums)
            return
        self._throttle()
        self.writes += 1
        st, resp = self._call("POST", ORDER_PATH, b, None)
        rec = (resp.get("order") or resp) if isinstance(resp, dict) else {}
        if st in (200, 201) and isinstance(rec, dict) and rec.get("order_id"):
            o["kid"], o["status"] = rec.get("order_id"), "resting"
            self.log.write("placed", evt=r["evt"], coin=coin, left=round(r["close"] - t, 1), body=b,
                           order_id=o["kid"], resp=str(resp)[:300], **nums)
            got = f(rec.get("fill_count_fp"), f(rec.get("fill_count"), 0.0))
            if got:
                self.on_fill(o, got, t)
        elif st == -2:
            o["status"], o["final"] = "not_sent", True
            self.log.write("not_sent", evt=r["evt"], coin=coin, resp=str(resp)[:200])
        elif isinstance(st, int) and 400 <= st < 500 and st != 429:
            o["status"], o["final"] = "rejected", True
            self.log.write("rejected", evt=r["evt"], coin=coin, status=st, body=b, resp=str(resp)[:300])
        else:
            o["status"] = "unknown"
            self.log.write("place_unknown", evt=r["evt"], coin=coin, status=st, body=b, resp=str(resp)[:300])

    def own_exit_t(self, close):
        return close - self.exit_s - OWN_CANCEL_LEAD_S

    def cancel_due(self, t):
        """rr.Bot.cancel_due with the v2 exit: our own cancel is SENT from close-116 s (server expiry at close-115)."""
        for o in list(self.resting()):
            if o["status"] in ("resting", "unknown") and not o.get("cancel_why"):
                if self.stopping:
                    self.cancel(o, self.stopping, t)
                elif t >= self.own_exit_t(o["close"]):
                    self.cancel(o, "exit", t)
                continue
            gap = rr.CANCEL_RETRY_S if t < o["close"] else rr.CANCEL_RETRY_CLOSED_S
            if t - (o.get("cancel_try_t") or -1e18) >= gap:
                if o["status"] == "cancelling":
                    o["status"] = "cancel_failed"
                self.cancel(o, o.get("cancel_why") or "retry", t)
        for r in list(self.races.values()):
            if self.dry or r["swept"] or not (self.own_exit_t(r["close"]) <= t < r["close"]) or not r["placed"]:
                continue
            if t - r["sweep_t"] >= 1.0:
                r["sweep_t"] = t
                r["swept"] = self.sweep(t, "exit", set(r["legs"].values()))

    def quiet(self, t):
        return any(self.own_exit_t(o["close"]) - rr.QUIET_S <= t < o["close"] for o in self.resting())

    def timeout_for(self, t):
        to = rr.DEFAULT_TIMEOUT_S
        for r in self.races.values():
            if r["placed"] and t < r["close"] + 10.0:
                to = min(to, max(rr.SHORT_TIMEOUT_S, self.own_exit_t(r["close"]) - rr.QUIET_S - t))
        for o in self.resting():
            to = min(to, max(rr.SHORT_TIMEOUT_S, self.own_exit_t(o["close"]) - rr.QUIET_S - t))
        return to

    def sweep(self, t, why, tickers=None):
        """rr.Bot.sweep for this file's client-id prefix, in subaccount 4."""
        if self.dry:
            return True
        st, r = self._call("GET", "/portfolio/orders", None, {"subaccount": SUB, "status": "resting", "limit": 200},
                           cancel_path=True)
        if st != 200 or not isinstance(r, dict):
            self.log.write("sweep_unreadable", why=why, status=st)
            return False
        n, ok = 0, True
        for x in r.get("orders") or []:
            if not str(x.get("client_order_id", "")).startswith(CID_PREFIX):
                continue
            if tickers is not None and x.get("ticker") not in tickers:
                continue
            kid = x.get("order_id")
            mine = next((o for o in self.orders.values() if o.get("kid") == kid
                         or o["cid"] == x.get("client_order_id")), None)
            if mine is not None:
                mine["kid"] = kid
                if mine["status"] not in ON_BOOK:
                    mine["status"], mine["final"] = "cancel_failed", False
                self.cancel(mine, why, t)
                if mine["status"] in ON_BOOK:
                    ok = False
            else:
                self._throttle()
                self.writes += 1
                st2, _ = self._call("DELETE", "%s/%s" % (ORDER_PATH, kid), None,
                                    {"subaccount": SUB, "exchange_index": POOL}, cancel_path=True)
                self.log.write("sweep_cancel_stray", order_id=kid, cid=x.get("client_order_id"), status=st2)
                if st2 not in (200, 201):
                    ok = False
            n += 1
        if n:
            self.log.write("sweep", why=why, found=n, ok=ok)
        return ok

    def poll_orders(self, t):
        """rr.Bot.poll_orders + spec 3.5: an order Kalshi reports final ('canceled' -- the demo probe's string -- or
        'expired') with no cancel from us, first seen at or after expiration_time - 1, is 'expired' (final), not N8."""
        if self.dry:
            return True
        live = [o for o in self.orders.values() if not o.get("final") and o["status"] in CONFIRMABLE]
        if not live:
            return True
        mts = int(min(o["placed_t"] for o in live) - 120)
        st, r = self._call("GET", "/portfolio/orders", None, {"subaccount": SUB, "min_ts": mts, "limit": 200},
                           cancel_path=True)
        if st != 200 or not isinstance(r, dict):
            self.log.write("poll_unreadable", status=st)
            return False
        seen = set()
        for x in r.get("orders") or []:
            o = next((o for o in live if o.get("kid") == x.get("order_id") or o["cid"] == x.get("client_order_id")),
                     None)
            if o is None:
                continue
            seen.add(o["id"])
            if not o.get("kid") and x.get("order_id"):
                o["kid"] = x.get("order_id")
                self.log.write("reconciled", evt=o["evt"], coin=o["coin"], order_id=o["kid"], status=x.get("status"))
            self.on_fill(o, f(x.get("fill_count_fp"), f(x.get("fill_count"), 0.0)), t)
            o["fees"] = f(x.get("maker_fees_dollars"), 0.0) or 0.0
            s = x.get("status")
            if s == "resting":
                if o["status"] == "unknown":
                    o["status"] = "resting"
                elif o["status"] == "cancel_unconfirmed":
                    o["status"] = "cancel_failed"
                    self.log.write("cancel_404_still_resting", evt=o["evt"], coin=o["coin"], order_id=o["kid"],
                                   left=round(o["close"] - t, 2))
            elif s in ("executed", "canceled", "cancelled", "expired"):
                unasked = s != "executed" and o["tries"] == 0 and not o.get("cancel_why") \
                    and o["status"] in ("resting", "unknown")
                if unasked and t >= o["exp"] - 1.0:
                    o["cancel_why"] = "expired"
                    self.log.write("expired", evt=o["evt"], coin=o["coin"], order_id=o["kid"], kalshi_status=s,
                                   left=round(o["close"] - t, 2), sent_left=round(o["close"] - o["exp"], 2),
                                   filled=o["filled"])
                elif unasked:
                    self.log.write("exchange_cancelled", evt=o["evt"], coin=o["coin"], order_id=o["kid"],
                                   left=round(o["close"] - t, 2), after_close=t >= o["close"], filled=o["filled"],
                                   kalshi=str(x)[:300])
                if o["status"] in ON_BOOK:
                    if o["status"] in ("cancel_unconfirmed", "cancel_failed", "cancelling"):
                        self.log.write("cancel_confirmed", evt=o["evt"], coin=o["coin"], order_id=o["kid"],
                                       kalshi_status=s, left=round(o["close"] - t, 2))
                    o["status"] = "filled" if s == "executed" else "cancelled"
                if o.get("cancel_t") is None:
                    o["cancel_t"] = min(t, o["exp"]) if o.get("cancel_why") == "expired" else t
                o["final"] = True
        for o in live:
            if o["id"] in seen or o.get("kid"):
                continue
            o["unseen"] = o.get("unseen", 0) + 1
            if o["unseen"] >= rr.NEVER_CREATED_POLLS and t - o["placed_t"] >= 10.0:
                o["status"], o["final"] = "never_created", True
                self.log.write("never_created", evt=o["evt"], coin=o["coin"], cid=o["cid"], polls=o["unseen"])
        return True

    # ---------------- per-second scoring, starved cancel, controls ----------------
    def snapshots(self, t):
        slot = int(t)
        if slot == self.last_slot:
            return
        self.last_slot = slot
        for r in self.races.values():
            if t >= r["close"]:
                continue
            resting_here = False
            for tk, oid in r["placed"].items():
                o = self.orders[oid]
                if o["status"] not in ON_BOOK:
                    continue
                resting_here = True
                prog = r["prog"].get(tk)
                if prog is None:
                    continue
                got, src = self.book(tk, t)
                s = r["snaps"].setdefault(tk, {"slots": 0, "ok": 0, "share_s": 0.0, "first": slot, "last": slot,
                                               "alone": 0, "n99": 0.0, "cross99": 0.0, "ok_j": 0, "share_j": 0.0,
                                               "run": 0, "starved_s": 0})
                s["last"] = slot
                if got is None:
                    continue
                ours = max(0.0, o["count"] - o["filled"])
                lin = r["linear"].get(tk, True)
                yo = rr.others_of(got[0], 0 if self.dry else ours)
                asked = bool(o.get("cancel_why"))
                # spec 3.6, BEFORE crediting (the shadow's order): YES side incl. our remaining < target for 5 s.
                # Live: the socket's YES side already holds our true remaining (fills show there before the poll).
                incl = sum(got[0].values()) + (ours if self.dry else 0.0)
                if not asked and t - o["placed_t"] >= STARVE_GRACE_S:
                    if incl < prog["target"] - 1e-9:
                        s["run"] += 1
                        s["starved_s"] += 1
                        if s["run"] >= STARVE_N:
                            self.log.write("starved", evt=r["evt"], coin=o["coin"], left=round(r["close"] - t, 1),
                                           yes_incl=round(incl, 2), target=prog["target"], run=s["run"])
                            self.cancel(o, "starved", t)
                            asked = True
                    else:
                        s["run"] = 0
                if asked:
                    continue
                sn = rr.snapshot(yo, got[1], ours, prog, lin)
                no_sc = {p: v for p, v in got[1].items() if p < 0.99 - 1e-9}
                sj = sh.snapshot_july(yo, no_sc, ours, prog, lin)
                n99 = round(sum(v for p_, v in got[1].items() if p_ >= 0.99 - 1e-9), 2)
                s["cross99"] += max(0.0, n99 - s["n99"])
                s["n99"] = n99
                sn["bn"], sn["n99"], sn["shj"], sn["yin"] = rr.best(got[1]), n99, sj["sh"], round(incl, 2)
                s["slots"] += 1
                if sn["ok"]:
                    s["ok"] += 1
                    s["share_s"] += sn["sh"]
                    if sn["sh"] >= 0.999:
                        s["alone"] += 1
                if sj["ok"]:
                    s["ok_j"] += 1
                    s["share_j"] += sj["sh"]
                self.log.write("snap", evt=r["evt"], c=o["coin"], left=round(r["close"] - t, 1), src=src,
                               ours=ours, **sn)
            if not resting_here:
                continue
            for coin, tk in r["legs"].items():            # spec 3.8 controls: legs we did NOT post, socket only
                if tk in r["placed"]:
                    continue
                lv = self.books.levels(tk)
                if lv is None:
                    continue
                c = r["ctl"].setdefault(tk, {"s": 0, "n99": None, "add99": 0.0, "t0": t, "t1": t, "dead_s": 0})
                n99 = sum(v for p_, v in lv[1].items() if p_ >= 0.99 - 1e-9)
                if c["n99"] is not None:
                    c["add99"] += max(0.0, n99 - c["n99"])
                c["n99"], c["t1"] = n99, t
                c["s"] += 1
                if (rr.best(lv[0]) or 0.0) <= rr.DEAD_YES + 1e-9:
                    c["dead_s"] += 1

    # ---------------- race summary ----------------
    def exchange_fills(self, r):
        """spec 3.8: every fill of this race's orders with its EXCHANGE created_time (live only)."""
        mine = {o["kid"]: o for o in self.orders.values() if o["evt"] == r["evt"] and o.get("kid")}
        if self.dry or not mine:
            return [], True
        mts = int(min(o["placed_t"] for o in mine.values()) - 60)
        rows, ok = [], True
        cur = None
        for _ in range(5):
            q = {"subaccount": SUB, "min_ts": mts, "limit": 200}
            if cur:
                q["cursor"] = cur
            st, b = self._call("GET", "/portfolio/fills", None, q)
            if st != 200 or not isinstance(b, dict):
                ok = False
                break
            rows += [x for x in b.get("fills") or [] if x.get("order_id") in mine]
            cur = b.get("cursor")
            if not cur or not b.get("fills"):
                break
        out, cum = [], {}
        for x in sorted(rows, key=lambda x: str(x.get("created_time"))):
            o = mine[x["order_id"]]
            n = f(x.get("count_fp"), f(x.get("count"), 0.0)) or 0.0
            ts = parse_ts(x.get("created_time"))
            cum[o["kid"]] = cum.get(o["kid"], 0.0) + n
            left = round(o["close"] - ts, 2) if ts is not None else None
            row = {"evt": o["evt"], "coin": o["coin"], "order_id": o["kid"], "count": n, "filled": cum[o["kid"]],
                   "created_time": x.get("created_time"), "left": left, "window": window_of(left or 0.0),
                   "price": x.get("yes_price_dollars"), "trade_id": x.get("trade_id")}
            self.log.write("exchange_fill", **row)
            out.append(row)
        return out, ok

    def summarize(self, r, t, stopped=None):
        xf, xok = self.exchange_fills(r)
        legs, tot, tot_floor, paid_j, fills_n, fills_cost = {}, 0.0, 0.0, 0.0, 0.0, 0.0
        for tk, oid in r["placed"].items():
            o = self.orders[oid]
            prog = r["prog"].get(tk)
            if prog is None:
                continue
            period = rr.period_of(prog)
            s = r["snaps"].get(tk) or {"slots": 0, "ok": 0, "share_s": 0.0, "alone": 0, "share_j": 0.0, "ok_j": 0,
                                       "starved_s": 0, "cross99": 0.0}
            exp = rr.credit(prog["reward"], period, s["share_s"])
            cj = rr.credit(prog["reward"], period, s.get("share_j", 0.0))
            pj = rr.floored(PAID_FACTOR * cj)
            off = o.get("cancel_t") or o.get("cancel_sent_t") or r["close"]
            mine = [x for x in xf if x["order_id"] == o.get("kid")]
            by_w = {}
            for x in mine:
                by_w[x["window"]] = by_w.get(x["window"], 0.0) + x["count"]
            hyp = None
            if self.dry:
                sold = self.books.sells_1c(tk, int(o["placed_t"] * 1000))
                if sold is not None:
                    sold_in = sold - (self.books.sells_1c(tk, int(off * 1000)) or 0.0)
                    c99 = s.get("cross99", 0.0)
                    hyp = {"sold_into_1c": round(sold_in, 2), "queue_ahead": o["queue_ahead"],
                           "no_99c_would_cross": round(c99, 2),
                           "would_fill_low": round(min(o["count"], max(0.0, sold_in - o["queue_ahead"])), 2),
                           "would_fill_high": round(min(o["count"], sold_in + c99), 2)}
            legs[o["coin"]] = {"placed_left": round(r["close"] - o["placed_t"], 1), "cancel": o["cancel_why"],
                               "cancel_sent_left": (round(r["close"] - o["cancel_sent_t"], 2)
                                                    if o.get("cancel_sent_t") else None),
                               "status": o["status"], "on_book_s": round(max(0.0, off - o["placed_t"]), 1),
                               "snaps": s["slots"], "counted_s": s["ok"], "alone_s": s["alone"],
                               "share_s": round(s["share_s"], 3), "share_july_s": round(s.get("share_j", 0.0), 3),
                               "counted_july_s": s.get("ok_j", 0), "starved_s": s.get("starved_s", 0),
                               "reward": prog["reward"], "target": prog["target"], "period_s": period,
                               "program_id": prog.get("id"), "projected_at_place": o.get("proj"),
                               "count": o["count"], "expected": round(exp, 4), "expected_floored": round(rr.floored(exp), 4),
                               "credit_july": round(cj, 4), "paid_model": round(pj, 4), "filled": o["filled"],
                               "filled_exchange": round(sum(x["count"] for x in mine), 2) if not self.dry else None,
                               "fills_by_window": by_w, "largest_print": max([x["count"] for x in mine] or [0.0]),
                               "full_dump": o["filled"] >= 0.99 * o["count"],
                               "cost": round(o["cost"] + o["fees"], 4), "would_fill": hyp}
            tot += exp
            tot_floor += rr.floored(exp)
            paid_j += pj
            fills_n += o["filled"]
            fills_cost += o["cost"] + o["fees"]
        controls = {}
        for tk, c in (r.get("ctl") or {}).items():
            coin = r["coin_of"][tk]
            sold = None
            a = self.books.sells_1c(tk, int(c["t0"] * 1000))
            if a is not None:
                sold = round(a - (self.books.sells_1c(tk, int((c["t1"] + 1.0) * 1000)) or 0.0), 2)
            refused = sorted(w for k, w in r["seen"] if k == tk)
            controls[coin] = {"postable": any(w == "under_floor" or w.startswith("rail_") for w in refused),
                              "dead_s": c["dead_s"], "seconds": c["s"], "sold_1c": sold,
                              "add99": round(c["add99"], 2), "refusals": refused}
        self._day(r["close"])["credit_exp"] += tot_floor
        self.state.setdefault("race_paid", {})[r["evt"]] = {"close": r["close"], "paid_model": round(paid_j, 4)}
        self.save()
        self.log.write("race_summary", evt=r["evt"], close=utc_iso(r["close"]), mode="dry" if self.dry else "live",
                       exit_s=self.exit_s, every=self.every, stopped=stopped, legs=legs,
                       expected_credit=round(tot, 4), expected_credit_floored=round(tot_floor, 4),
                       paid_model=round(paid_j, 4), fills=fills_n, fills_cost=round(fills_cost, 4),
                       exchange_fills_read=xok, controls=controls, races_with_order=len(self.state["races"]),
                       unconfirmed=[o["coin"] for o in self.resting() if o["evt"] == r["evt"]],
                       refusals=sorted("%s:%s" % (r["coin_of"][tk], w) for tk, w in r["seen"]))
        r["summary"] = True

    # ---------------- money lands in MAIN pool 0 (spec 3.11 / 3.12) ----------------
    def pool0_step(self, t):
        if self.dry or self.quiet(t) or t - self.last_pool0 < POOL0_EVERY_S:
            return
        self.last_pool0 = t
        p0 = read_main_pool0(self._call_get)
        if p0 is None:
            self.log.write("pool0_unreadable")
            return
        base = self.state.get("pool0_base")
        if base is None:
            self.state["pool0_base"] = base = {"t": t, "pool0": p0}
            self.save()
        self.log.write("pool0", pool0=round(p0, 4), delta=round(p0 - base["pool0"], 4))
        self.tripwire(t, p0)

    def _call_get(self, method, path, body, query, timeout=None):
        return self._call(method, path, body, query)

    def tripwire(self, t, p0):
        if self.state.get("trip_done"):
            return
        rp = self.state.get("race_paid") or {}
        order_races = [e for e in self.state["races"] if e in rp]
        if len(order_races) < TRIP_RACES:
            return
        first = sorted(order_races, key=lambda e: rp[e]["close"])[:TRIP_RACES]
        due = max(rp[e]["close"] for e in first) + TRIP_WAIT_S
        if t < due:
            return
        need = TRIP_FRAC * sum(rp[e]["paid_model"] for e in first)
        rise = p0 - self.state["pool0_base"]["pool0"]
        self.state["trip_done"] = True
        if need > 0 and rise < need - 1e-9:
            self.state["payment_missing"] = utc_iso(t)
            self.save()
            try:
                with open(self.stop_path, "a", encoding="utf-8") as fh:
                    fh.write("payment_missing %s rise %.4f < %.4f\n" % (utc_iso(t), rise, need))
            except OSError:
                pass
            self.log.write("payment_missing", races=first, pool0_rise=round(rise, 4), needed=round(need, 4))
            self.stopping = self.stopping or "payment_missing"
        else:
            self.save()
            self.log.write("payment_ok", races=first, pool0_rise=round(rise, 4), needed=round(need, 4))

    def step(self):
        t = self.now()
        if not self.stopping and self.stop_alias and os.path.exists(self.stop_alias):
            self.stopping = "stop_file"
            self.log.write("stop_file", path=self.stop_alias)
        super().step()
        if not self.stopping:
            try:
                self.pool0_step(self.now())
            except Exception as e:
                self.log.write("pool0_error", err=repr(e)[:300])


# ------------------------------------------------------------------------------------------------ report (GET only)
def other_reward_logs(since, own=(LIVE_LOG, DRY_LOG), results=RESULTS):
    """spec 3.11: attribution is refused if another reward bot has an order log active in the window."""
    out = []
    try:
        names = os.listdir(results)
    except OSError:
        return out
    for n in names:
        p = os.path.join(results, n)
        if p in own or not (n == "lip_orders.jsonl" or ("reward" in n and n.endswith("-live.jsonl"))):
            continue
        try:
            if os.path.getmtime(p) >= since:
                out.append(n)
        except OSError:
            pass
    return out


def paid_out_ids(sender, ids, oldest, maxpages=20):
    """Which of these program ids Kalshi lists as paid_out (newest-first paging, stopped once a page ends before the
    oldest test window). None if unreadable."""
    want, seen, cur = set(i for i in ids if i), set(), None
    for _ in range(maxpages):
        q = {"status": "paid_out", "type": "liquidity", "limit": "5000"}
        if cur:
            q["cursor"] = cur
        st, b = sender("GET", "/incentive_programs", None, q)
        if st != 200 or not isinstance(b, dict):
            return None
        rows = b.get("incentive_programs") or []
        seen |= {p.get("id") for p in rows if p.get("id") in want}
        cur = b.get("cursor") or b.get("next_cursor")
        ends = [parse_ts(p.get("end_date")) for p in rows]
        if not cur or not rows or seen >= want or all(e is not None and e < oldest - 86400 for e in ends):
            break
    return seen


def report(sender, out=print, live_log=LIVE_LOG, state_path=LIVE_STATE, report_log=REPORT_LOG, now=None,
           results=RESULTS):
    t = time.time() if now is None else float(now)
    races, xfill = {}, {}
    try:
        with open(live_log, encoding="utf-8") as fh:
            for line in fh:
                if '"race_summary"' not in line and '"exchange_fill"' not in line:
                    continue
                x = json.loads(line)
                if x["ev"] == "race_summary" and x.get("mode") == "live" and x.get("legs"):
                    races[x["evt"]] = x
                elif x["ev"] == "exchange_fill":
                    xfill[(x["evt"], x["coin"])] = max(xfill.get((x["evt"], x["coin"]), 0.0), float(x["filled"]))
    except (OSError, ValueError):
        pass
    state = rr.load_state(state_path) if os.path.exists(state_path) else {}
    if not races:
        out("racev2 report: VERDICT NO_RACES -- no live race_summary with an order in %s" % live_log)
        return 0
    order = sorted(races.values(), key=lambda x: parse_ts(x["close"]))[:RACES_MAX]
    C = M = 0.0
    legs_n, dumps, ids, closes, b0004 = 0, 0, [], [], 0
    for x in order:
        c = parse_ts(x["close"])
        closes.append(c)
        h = (datetime.fromtimestamp(c, timezone.utc).hour + rr.et_offset_h(c)) % 24
        b0004 += 1 if 0 <= h < 4 or (h == 4 and datetime.fromtimestamp(c, timezone.utc).minute == 0) else 0
        for coin, lg in x["legs"].items():
            legs_n += 1
            filled = xfill.get((x["evt"], coin), lg.get("filled_exchange"))
            filled = max(float(filled or 0.0), float(lg.get("filled") or 0.0))
            C += 0.01 * filled
            M += float(lg.get("paid_model") or 0.0)
            dumps += 1 if filled >= 0.99 * float(lg.get("count") or COUNT_CAP) else 0
            ids.append(lg.get("program_id"))
    last, first = max(closes), min(closes)
    p0 = read_main_pool0(sender)
    base = (state.get("pool0_base") or {}).get("pool0")
    P = None if (p0 is None or base is None) else p0 - base
    others = other_reward_logs(first - 900, results=results)
    po = paid_out_ids(sender, ids, first) if t >= last + FINAL_H * 3600 else None
    rec = {"t": utc_iso(t), "races": len(order), "legs": legs_n, "C": round(C, 4), "M": round(M, 4),
           "P": None if P is None else round(P, 4), "pool0": p0, "pool0_base": base, "full_dumps": dumps,
           "races_00_04_et": b0004, "et_days": len({et_day(c) for c in closes}), "first_close": utc_iso(first),
           "last_close": utc_iso(last), "other_reward_logs": others,
           "paid_out": None if po is None else "%d/%d" % (len(po), len(set(i for i in ids if i)))}
    out("racev2 report %s: %d races with an order (bar sample = first %d), %d legs, %d ET days, %d closing 00-04 ET"
        % (rec["t"], len(order), RACES_MAX, legs_n, rec["et_days"], b0004))
    out("  C (fills x $0.01) $%.2f   M (paid-model credit) $%.2f   C/M %s   full 1,100 dumps %d"
        % (C, M, "%.3f" % (C / M) if M > 0 else "n/a", dumps))
    out("  P (main pool 0 now %s - at start %s) %s   P/M %s   paid_out flags %s"
        % (p0, base, "n/a" if P is None else "$%.2f" % P, "%.3f" % (P / M) if (P is not None and M > 0) else "n/a",
           rec["paid_out"] or "(read at 48 h)"))
    if others:
        out("  ATTRIBUTION REFUSED: other reward order logs active in the window: %s" % others)
    out("  BAR (spec 4.2): PASS C <= 0.25 M AND P >= 0.90 M; KILL C > 0.50 M or P < 0.50 M at 48 h; else EXTEND 20")
    if len(order) < RACES_MAX:
        v = "INCOMPLETE"
        why = "%d of %d races so far" % (len(order), RACES_MAX)
    elif t < last + PROVISIONAL_H * 3600:
        v, why = "TOO_EARLY", "read 2 h after the last race (%s)" % utc_iso(last + PROVISIONAL_H * 3600)
    elif M <= 0:
        v, why = "NO_CREDIT", "M = 0: no leg earned the paid model"
    elif C > 0.50 * M + 1e-9:
        v, why = "KILL", "C/M %.3f > 0.50" % (C / M)
    elif t < last + FINAL_H * 3600:
        v = "PROVISIONAL"
        why = "C/M %.3f; P/M %s; final read at %s" % (C / M, "n/a" if P is None else "%.3f" % (P / M),
                                                        utc_iso(last + FINAL_H * 3600))
    elif P is None or others:
        v, why = "UNREADABLE", "pool 0 unreadable or attribution refused"
    elif P < 0.50 * M - 1e-9:
        v, why = "KILL", "P/M %.3f < 0.50 at 48 h" % (P / M)
    elif C <= 0.25 * M + 1e-9 and P >= 0.90 * M - 1e-9:
        v, why = "PASS", "C/M %.3f <= 0.25 and P/M %.3f >= 0.90" % (C / M, P / M)
    else:
        v, why = "EXTEND", "C/M %.3f, P/M %.3f: between the lines -> 20 more races (operator sign-off)" % (C / M, P / M)
    rec["verdict"] = v
    out("  VERDICT: %s -- %s" % (v, why))
    try:
        with open(report_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    return 0


# ------------------------------------------------------------------------------------------------ self-test
class _FakeX(rr._FakeX):
    """rr's fake exchange + v2: expiration_time honoured (status 'canceled', as the demo probe saw), /portfolio/fills,
    the main balance with its breakdown, and the guard in front of it."""

    def __init__(self, clock, close):
        super().__init__(clock, close)
        self.fills = []
        self.pool0 = 100.0
        self.expire_status = "canceled"

    def __call__(self, method, path, body, query, timeout=None):
        for o in self.orders.values():
            if o["status"] == "resting" and o.get("exp") and self.clock[0] >= o["exp"]:
                o["status"], o["canceled_t"] = self.expire_status, o["exp"]
        if method == "POST":
            st, r = super().__call__(method, path, body, query, timeout)
            o = self.orders["K%d" % len(self.orders)]
            o["exp"] = body.get("expiration_time")
            return st, r
        if path == "/portfolio/fills":
            return 200, {"fills": list(self.fills), "cursor": ""}
        if path == "/portfolio/balance" and not query:
            d = self.pool0 + 1000.0
            return 200, {"balance": int(round(d * 100)), "balance_dollars": "%.4f" % d,
                         "balance_breakdown": [{"exchange_index": 0, "balance": "%.4f" % self.pool0},
                                               {"exchange_index": 2, "balance": "1000.0000"}]}
        return super().__call__(method, path, body, query, timeout)


class _FakeBooks(rr._FakeBooks):
    """The socket's view: everyone's book, INCLUDING our resting remaining at 1c when ours=True (live realism)."""

    def __init__(self, x, ours=True, **kw):
        super().__init__(x, **kw)
        self.ours = ours

    def levels(self, tk):
        lv = super().levels(tk)
        if lv is None or not self.ours:
            return lv
        y = dict(lv[0])
        for o in self.x.orders.values():
            if o["ticker"] == tk and o["status"] == "resting":
                y[0.01] = y.get(0.01, 0.0) + float(o["remaining_count_fp"]) - float(o["fill_count_fp"] or 0)
        return y, lv[1]


def selftest(verbose=False):
    fails, notes = [], []

    def ck(ok, m):
        (notes if ok else fails).append(m)

    def _rm(p):
        if os.path.exists(p):
            os.remove(p)

    ok_pins, shas = pins_ok()
    ck(ok_pins, "pins: racereward_live %s (want %s), racev2_shadow %s (want %s)"
       % (shas["rr_sha"], RR_SHA, shas["shadow_sha"], SH_SHA))

    # ---- 0. decisions identical to the shadow: constants, count, projection ----
    ck(EXIT_S == sh.EXIT_S and COUNT_CAP == sh.COUNT_CAP and CUSHION == sh.CUSHION and POST_FLOOR_USD == sh.POST_FLOOR
       and PAID_FACTOR == sh.PAID_FACTOR and STARVE_N == sh.STARVE_N and MAX_COLLATERAL == sh.MAX_COLLATERAL_V2
       and DAY_STOP == sh.DAY_STOP and MAX_RESTING == sh.MAX_RESTING and rr.WINDOW_S == sh.WINDOW,
       "constants == the shadow's (exit 115, 1,100, +100, $1.25, 0.987, starve 5, $40, -$30, 5 resting, 360 s)")
    P = {"reward": 20.0, "target": 1000.0, "df": 0.5, "start": None, "end": None}
    ck(all(count_for(dict(P, target=tg)) == sh.count_for_v2(dict(P, target=tg)) for tg in (1000, 1500, 500, 1, 1050))
       and count_for(P) == 1100 and count_for(dict(P, target=1500)) == 1100 and count_for(dict(P, target=500)) == 600,
       "count: target 1,000 -> 1,100; 1,500 -> 1,100 (cap); 500 -> 600; == shadow.count_for_v2")

    T0 = 1_791_700_000.0
    tmpd = os.path.join(RESULTS, ".racev2-live-selftest-%d" % os.getpid())
    os.makedirs(tmpd, exist_ok=True)
    stp, alias, spath = os.path.join(tmpd, "stop"), os.path.join(tmpd, "stop2"), os.path.join(tmpd, "state.json")

    def world(dry=False, every=1, books=None, races_max=20, fresh=True, day_realized=None, ours=True, reward_cc=200000,
              progs_all=False):
        if fresh:
            _rm(spath)
        clock = [T0]
        close = T0 + 420.0
        x = _FakeX(clock, close)
        x.reward_cc = reward_cc
        if progs_all:
            x.no_prog = set()
        tk = x.tks
        x.books = books(tk) if books else {tk["BTC"]: ({0.95: 300}, {0.04: 300}), tk["ETH"]: ({}, {0.97: 1500}),
                                            tk["SOL"]: ({0.01: 1200}, {0.98: 2000}),
                                            tk["XRP"]: ({0.01: 20}, {0.99: 30, 0.97: 2000}),
                                            tk["HYPE"]: ({}, {0.97: 2000})}
        sink = []
        bk = _FakeBooks(x, ours=ours and not dry)
        snd = guarded(x, writes_ok=not dry, clock=lambda: clock[0])
        bot = Bot(rr.Log(sink=sink), dry, snd, lambda: clock[0], bk, spath, stp, races_max, every=every,
                  sleep=lambda s: clock.__setitem__(0, clock[0] + s), stop_alias=alias)
        if day_realized is not None:
            bot.state["days"][et_day(T0)] = {"realized": float(day_realized), "fills_cost": 0.0, "credit_exp": 0.0}
        return clock, close, x, bot, sink, bk

    def run(clock, bot, until, dt=0.25):
        while clock[0] < until and not bot.exit_ready:
            bot.step()
            clock[0] += dt

    def decided(sink):
        return {(r.get("coin"), r.get("why")) for r in sink if r["ev"] == "decide"}

    # ---- 1. parity: planted legs through the shadow's simulate_race AND this bot (dry, every 1) ----
    def parity(book_at, label, coin="ETH"):
        close = T0 + 420.0
        leg = sh._mk_leg_by_L("%s-%s" % ("KXCRYPTOLEAD15M-26OCT100430", coin), close, book_at,
                              {"reward": 20.0, "target": 1000.0, "df": 0.5, "start": close - 900, "end": close})
        res, _ = sh.simulate_race([leg], "none")
        s_ = res[leg.tk]

        def books(tk):
            return {k: ({0.95: 300}, {0.04: 300}) for k in tk.values()}
        clock, close, x, bot, sink, bk = world(dry=True, books=books, progs_all=True)
        tkc = x.tks[coin]
        while clock[0] < close + 10:
            L = int(math.ceil(close - clock[0] - 1e-9))
            x.books[tkc] = book_at(min(max(L, 0), sh.REC_MAX))
            bot.step()
            clock[0] += 0.25
        wp = [r for r in sink if r["ev"] == "would_place" and r["coin"] == coin]
        sm = [r for r in sink if r["ev"] == "race_summary"]
        lg = (sm[0]["legs"].get(coin) if sm and sm[0].get("legs") else None) or {}
        live_L = wp[0]["left"] if wp else None
        ok = ((s_["placed_left"] is None and live_L is None) or
              (s_["placed_left"] is not None and live_L is not None and abs(live_L - s_["placed_left"]) <= 1.0))
        if s_["placed_left"] is not None and lg:
            ok = ok and (lg["cancel"] == s_["cancel"]) and abs(lg["share_july_s"] - s_["share_s"]) <= 2.5 \
                and abs(lg["paid_model"] - s_["paid"]) <= 0.06
        ck(ok, "parity %s: shadow placed L=%s cancel %s share_s %.2f paid $%.3f | bot placed %s cancel %s share_s %s "
               "paid %s" % (label, s_["placed_left"], s_["cancel"], s_["share_s"], s_["paid"], live_L,
                            lg.get("cancel"), lg.get("share_july_s"), lg.get("paid_model")))

    parity(lambda L: ({}, {0.95: 1500}), "A alone (L=360, $2.676 paid)")
    parity(lambda L: ({0.01: 20}, {0.95: 1500}), "B 20 ahead at 1c (share 1100/1120)")
    parity(lambda L: (({0.06: 10} if L <= 250 else {}), {0.95: 1500}), "D alive at L=250")
    parity(lambda L: ({}, ({0.95: 1500} if L <= 230 else {0.95: 500})), "floor: postable at L=230 -> placed")
    parity(lambda L: ({}, ({0.95: 1500} if L <= 220 else {0.95: 500})), "floor: postable at L=220 -> never placed")
    parity(lambda L: ({0.01: 1200}, {0.95: 1500}), "C incumbent 1,200 -> never placed")

    # ---- 2. post floor $1.25 vs $1.00, target 1,500 ----
    clock, close, x, bot, sink, bk = world()
    r_ = {"close": close, "linear": {}}
    t110 = close - EXIT_S - 2.0 - 99.0               # alone: 99 s x 20/1800 = $1.10
    ok1, pj1, _ = bot.floor_check(r_, "X", {}, {0.97: 2000}, P, 1100, t110)
    bot.post_floor = 1.00
    ok2, _, _ = bot.floor_check(r_, "X", {}, {0.97: 2000}, P, 1100, t110)
    bot.post_floor = POST_FLOOR_USD
    ck(not ok1 and ok2 and abs(pj1 - 1.10) < 1e-9, "post floor: a leg projecting $%.2f is refused at $1.25, placed at "
                                                   "$1.00" % pj1)
    P15 = dict(P, target=1500.0)
    ok3, pj3, sh3 = bot.floor_check(r_, "X", {}, {0.97: 2000}, P15, count_for(P15), close - 360)
    ck(count_for(P15) == 1100 and not ok3 and sh3 == 0.0, "target 1,500: count 1,100, share 0 -> under_floor")
    ck(abs(sh.projection(type("D", (), {"prog": dict(P, start=close - 900, end=close), "linear": True,
                                         "close": close})(), {0.01: 20}, {0.95: 1500}, 1100, close - 300, EXIT_S)
           - bot.floor_check(r_, "X", {0.01: 20}, {0.95: 1500}, dict(P, start=close - 900, end=close), 1100,
                             close - 300)[1]) < 1e-12, "projection == shadow.projection")

    # ---- 3. order bodies and the guard ----
    bd = order_body(SERIES + "-X-BTC", 1100, CID_PREFIX + "1", T0 + 420.0)
    ck(bd["price"] == "0.0100" and bd["count"] == "1100.00" and bd["subaccount"] == 4
       and bd["expiration_time"] == int(T0 + 420 - 115) and bd["cancel_order_on_pause"] is True
       and body_ok(bd, T0, T0 + 420.0), "the body: 1,100 YES at 0.0100, sub 4, pool 2, expires close-115, pause-cancel")
    bads = ((dict(bd, subaccount=5), "subaccount 5"), (dict(bd, subaccount=0), "subaccount 0"),
            (dict(bd, subaccount="4"), "subaccount as a string"), (dict(bd, price="0.0200"), "price 0.02"),
            (dict(bd, count="1101.00"), "count 1,101"), (dict(bd, count="0.00"), "count 0"),
            (dict(bd, post_only=False), "post_only False"), (dict(bd, exchange_index=0), "pool 0"),
            (dict(bd, side="ask"), "side ask"), (dict(bd, ticker="KXBTC15M-X"), "another series"),
            (dict(bd, client_order_id="rrw-1"), "v1's client id"), (dict(bd, time_in_force="immediate_or_cancel"),
                                                                     "IOC"),
            (dict(bd, self_trade_prevention_type="taker_at_cross"), "STP taker"),
            (dict(bd, cancel_order_on_pause=False), "cancel_order_on_pause False"),
            ({k: v for k, v in bd.items() if k != "expiration_time"}, "no expiration_time"),
            (dict(bd, expiration_ts=bd["expiration_time"]), "an expiration_ts key"),
            (dict(bd, expiration_time=float(bd["expiration_time"])), "expiration_time as a float"),
            (dict(bd, expiration_time=bd["expiration_time"] + 1), "expiration_time not close-115"),
            (dict(bd, reduce_only=True), "an extra key"))
    for b_, m in bads:
        ck(not body_ok(b_, T0, T0 + 420.0), "body_ok refuses %s" % m)
    ck(not body_ok(bd, T0 + 420 - 115 - 30, T0 + 420.0) and body_ok(bd, T0 + 420 - 115 - 31, T0 + 420.0),
       "body_ok refuses an expiry <= now + 30 s")
    late = order_body(SERIES + "-X-BTC", 1100, CID_PREFIX + "1", T0 + 2000.0)
    ck(not body_ok(late, T0) and body_ok(bd, T0), "guard body check: an expiry more than 365 s ahead is refused")
    try:
        sys.path.insert(0, os.path.join(RESEARCH, "cleanroom"))
        import importlib
        LL = importlib.import_module("ladder_live")
        lb = LL.order_body(SERIES + "-X-BTC", "yes", "0.01", 4, "lad-1")
        ck(set(bd) - set(lb) == {"expiration_time", "cancel_order_on_pause"} and set(lb) <= set(bd)
           and all(lb[k] == bd[k] for k in lb if k not in ("count", "client_order_id")),
           "the body differs from ladder_live.order_body only by expiration_time + cancel_order_on_pause")
    except Exception as e:
        ck(False, "ladder_live parity could not be checked: %r" % e)
    gcalls = []

    def raw(m, p, b, q, timeout=None):
        gcalls.append((m, p))
        return 200, {}
    g = guarded(raw, True, clock=lambda: T0)
    gd = guarded(raw, False, clock=lambda: T0)
    for args, m in ((("POST", ORDER_PATH, dict(bd, count="1101.00"), None), "a 1,101-lot POST"),
                    (("POST", ORDER_PATH, dict(bd, post_only=False), None), "a POST without post_only"),
                    (("POST", ORDER_PATH, dict(bd, subaccount=5), None), "a POST for subaccount 5"),
                    (("POST", "/portfolio/subaccounts/transfer", {"amount_cents": 1}, None), "a transfer POST"),
                    (("POST", "/portfolio/orders", bd, None), "a POST to another order path"),
                    (("PUT", ORDER_PATH + "/K1", {}, None), "a PUT (amend)"),
                    (("DELETE", ORDER_PATH + "/K1", None, {"subaccount": 5, "exchange_index": 2}), "a DELETE in sub 5"),
                    (("DELETE", ORDER_PATH + "/K1", None, None), "a DELETE without subaccount"),
                    (("DELETE", "/portfolio/subaccounts/4", None, {"subaccount": 4, "exchange_index": 2}),
                     "a DELETE of a non-order path"),
                    (("GET", "/portfolio/orders", None, {"subaccount": 1}), "a GET for subaccount 1")):
        try:
            g(*args)
            ck(False, "guard let through %s" % m)
        except RuntimeError:
            ck(True, "guard refuses %s" % m)
    try:
        gd("POST", ORDER_PATH, bd, None)
        ck(False, "dry-run guard let a POST through")
    except RuntimeError:
        ck(True, "guard refuses every POST/DELETE in --dry-run / --report (GET-only modes)")
    ok_ = g("POST", ORDER_PATH, bd, None)[0] == 200 and g("DELETE", ORDER_PATH + "/K1", None,
                                                           {"subaccount": 4, "exchange_index": 2})[0] == 200 \
        and g("GET", "/portfolio/balance", None, None)[0] == 200
    ck(ok_ and gcalls == [("POST", ORDER_PATH), ("DELETE", ORDER_PATH + "/K1"), ("GET", "/portfolio/balance")],
       "guard passes a good order, a sub-4 cancel and the main balance GET -- nothing refused reaches the sender")

    # ---- 4. start refusals ----
    st0 = {"races": [], "halted_day": None}
    for s_ in (None, 0, 1, 2, 3, 5, 63):
        ck(start_refusal(s_, 45, st0, 20, T0, [stp]) is not None, "start: subaccount %s refused" % s_)
    ck(start_refusal(4, 45, st0, 20, T0, [stp]) is None, "start: subaccount 4, $45, flat, no stop file -> ok")
    ck(start_refusal(4, 45, st0, 21, T0, [stp]) and start_refusal(4, 45, st0, 0, T0, [stp]),
       "start: --races 21 / 0 refused (max 20)")
    ck(start_refusal(4, 39.99, st0, 20, T0, [stp]) and start_refusal(4, 50.01, st0, 20, T0, [stp])
       and start_refusal(4, None, st0, 20, T0, [stp]) and start_refusal(4, 40.0, st0, 20, T0, [stp]) is None
       and start_refusal(4, 50.0, st0, 20, T0, [stp]) is None, "start: under $40 / over $50 / unreadable refused")
    ck(start_refusal(4, 45, {"races": ["e%d" % i for i in range(20)]}, 20, T0, [stp]),
       "start: 20 races already done (state) refused")
    ck(start_refusal(4, 45, dict(st0, test_halted="x"), 20, T0, [stp])
       and start_refusal(4, 45, dict(st0, payment_missing="x"), 20, T0, [stp])
       and start_refusal(4, 45, dict(st0, halted_day=et_day(T0)), 20, T0, [stp]),
       "start: test stop / payment tripwire / today's day stop in the state file refused")
    ck(start_refusal(4, 45, st0, 20, T0, [stp], None) and start_refusal(4, 45, st0, 20, T0, [stp], (0.0, 1.0))
       and start_refusal(4, 45, st0, 20, T0, [stp], (-30.0, 0.0)), "start: unreadable day / open positions / -$30 refused")
    open(alias, "w").close()
    ck(start_refusal(4, 45, st0, 20, T0, [stp, alias]) is not None, "start: a stop file present refuses the start")
    _rm(alias)

    # ---- 5. the planted race (live, every 1): one order, v2 exit, expiry, snapshots ----
    clock, close, x, bot, sink, bk = world()
    tk = x.tks
    run(clock, bot, close - 300)
    posts = x.writes("POST")
    ck(len(posts) == 1 and posts[0][2]["ticker"] == tk["ETH"] and posts[0][2]["count"] == "1100.00"
       and posts[0][2]["expiration_time"] == int(close - 115) and posts[0][2]["subaccount"] == 4,
       "planted race: one 1,100-lot on the dead ETH leg, expiring close-115, sub 4")
    ck(abs((close - posts[0][4]) - 360.0) <= 0.5 if posts else False, "placed at 360 s left (the shadow's L=360)")
    w = decided(sink)
    ck(("BTC", "not_dead") in w and ("SOL", "yes_side_full") in w and ("XRP", "would_cross") in w
       and ("HYPE", "no_program") in w, "the other legs refused for their planted reasons")
    run(clock, bot, close + 30)
    d_ = [c for c in x.calls if c[0] == "DELETE"]
    ck(len(d_) == 1 and close - 116.0 <= d_[0][4] <= close - 115.5 and d_[0][3] == {"subaccount": 4,
                                                                                     "exchange_index": 2},
       "EXIT: our own cancel SENT at close-116 s (%.2f s left), before the server expiry" % (close - d_[0][4]
                                                                                           if d_ else -1))
    ck(not any(c[4] >= close - EXIT_S for c in x.writes("POST")), "EXIT: no order sent from close-115 s")
    sm = [r for r in sink if r["ev"] == "race_summary"]
    lg = sm[0]["legs"]["ETH"] if sm else {}
    ck(sm and 240 <= lg.get("share_july_s", 0) <= 246 and abs(lg["paid_model"] - rr.floored(
        PAID_FACTOR * rr.credit(20.0, 900.0, lg["share_july_s"]))) < 1e-4 and lg.get("projected_at_place", 0) > 2.6
       and not any(r["ev"] in ("exchange_cancelled", "expired") for r in sink),
       "summary: ~244 share-seconds alone -> paid model $%.3f, projected_at_place %s; no N8, no expiry"
       % (lg.get("paid_model", -1), lg.get("projected_at_place")))

    # ---- 6. expiry is not an alarm (3.5); an earlier unrequested cancel still is (N8) ----
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 300)
    bot.own_exit_t = lambda c: c                    # our own exit cancel disabled: only the server expiry remains
    run(clock, bot, close + 20)
    ex_ = [r for r in sink if r["ev"] == "expired"]
    ck(len(ex_) == 1 and ex_[0]["kalshi_status"] == "canceled" and not any(r["ev"] == "exchange_cancelled" for r in sink)
       and bot.orders[1]["final"], "3.5: Kalshi's own expiry ('canceled' at close-115) is logged 'expired', not N8")
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 250)
    x.orders["K1"]["status"] = "canceled"
    run(clock, bot, close - 200)
    ck(len([r for r in sink if r["ev"] == "exchange_cancelled"]) == 1 and not any(r["ev"] == "expired" for r in sink),
       "3.5: an unrequested cancel at 250 s (before expiry-1) stays N8 'exchange_cancelled'")

    # ---- 7. starved (3.6): a 101 fill on a lone 1,100 bid -> cancel after 5 snapshots ----
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 300)
    x.orders["K1"]["fill_count_fp"] = "101.00"
    x.orders["K1"]["remaining_count_fp"] = "1100.00"     # _FakeBooks shows remaining - filled = 999 at 1c
    t_f = clock[0]
    run(clock, bot, close - 280)
    stv = [r for r in sink if r["ev"] == "starved"]
    dl = [c for c in x.calls if c[0] == "DELETE"]
    ck(len(stv) == 1 and bot.orders[1]["cancel_why"] == "starved" and dl and 4.0 <= dl[0][4] - t_f <= 6.5,
       "3.6: YES side 999 < 1,000 after a 101 fill -> 'starved' cancel %.2f s later (5 snapshots)"
       % ((dl[0][4] - t_f) if dl else -1))
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 200)
    ck(not any(r["ev"] == "starved" for r in sink), "3.6 null: a lone 1,100 (incl. ours) is never starved")

    # ---- 8. --every 3 (3.7): 12 consecutive races -> orders in exactly 4 ----
    base = 1_792_627_200.0                          # 2026-10-21T00:00Z
    ck(sum(sampled(base + 900 * i, 3) for i in range(1, 13)) == 4 and sampled(base, 3) and not sampled(base + 900, 3)
       and race_index(base + 2700) == 3 and sum(sampled(base + 900 * i, 1) for i in range(12)) == 12,
       "3.7: --every 3 keeps exactly 4 of 12 consecutive races (index % 3 == 0); --every 1 keeps all")
    clock, close, x, bot, sink, bk = world(every=96)
    run(clock, bot, close - 200)
    ck(not x.writes("POST") and any(r["ev"] == "sampled_out" for r in sink) and not bot.races,
       "3.7: a race outside the sample is never prepared and gets no order")

    # ---- 9. stake rails ----
    clock, close, x, bot, sink, bk = world(progs_all=True, books=lambda tk: {k: ({}, {0.97: 2000}) for k in tk.values()})
    run(clock, bot, close - 300)
    rb = {c_ for c_, w_ in decided(sink) if w_.startswith("rail_")}
    ck(len(x.writes("POST")) == 2 and len(rb) == 3,
       "rail (f): clean day, 5 dead legs: 2 orders ($22 worst case), 3 refused by the -$30 budget (%s)" % sorted(
           w_ for c_, w_ in decided(sink) if w_.startswith("rail_")))
    clock, close, x, bot, sink, bk = world(progs_all=True, day_realized=100.0,
                                           books=lambda tk: {k: ({}, {0.97: 2000}) for k in tk.values()})
    run(clock, bot, close - 300)
    ck(len(x.writes("POST")) == 3 and ("rail_max_collateral" in {w_ for c_, w_ in decided(sink)}),
       "max collateral $40: a +$100 day still holds at 3 orders ($33; a 4th = $44 > $40) -> 'max_collateral'")
    ck(bot.rails_refusal(1101, clock[0]) in ("count_cap", "max_collateral"), "count 1,101 refused by the rails")
    clock, close, x, bot, sink, bk = world(day_realized=0.0)
    bot.state["days"]["2026-01-01"] = {"realized": -35.0, "fills_cost": 0.0, "credit_exp": 0.0}
    ck(bot.rails_refusal(1100, clock[0]) == "test_budget",
       "TEST STOP budget: -$35 earlier in the test + a new $11 order = -$46 < -$45 -> 'test_budget'")
    bot.state["days"]["2026-01-01"]["realized"] = -34.0
    ck(bot.rails_refusal(1100, clock[0]) is None, "TEST STOP budget: -$34 + $11 = -$45 exactly -> allowed")
    bot.state["days"]["2026-01-01"]["realized"] = -45.0
    bot.check_day_stop(clock[0])
    ck(bot.state.get("test_halted") and bot.stopping == "test_stop"
       and start_refusal(4, 45, rr.load_state(spath), 20, clock[0], [stp]) is not None,
       "TEST STOP: -$45 realized over the test halts the bot, and the halt survives a restart")
    clock, close, x, bot, sink, bk = world(races_max=1)
    run(clock, bot, close + 200)
    ck(len(x.writes("POST")) == 1 and bot.stopping == "races_done", "--races 1: one race with an order, then stop")
    clock, close, x, bot, sink, bk = world(races_max=50)
    ck(bot.races_max == RACES_MAX, "races_max is capped at 20 inside the bot even if a caller asks 50")

    # ---- 10. stop files ----
    for path, m in ((stp, "results/racev2-live.stop"), (alias, "the alias racereward-v2-live.stop")):
        clock, close, x, bot, sink, bk = world()
        run(clock, bot, close - 200)
        open(path, "w").close()
        run(clock, bot, close - 190)
        ck(bot.stopping == "stop_file" and x.orders["K1"]["status"] == "canceled" and bot.exit_ready,
           "stop file (%s): every resting order cancelled, bot exits" % m)
        _rm(path)

    # ---- 11. payment tripwire (3.12) ----
    for rise, want in ((0.5, True), (3.0, False)):
        clock, close, x, bot, sink, bk = world()
        bot.state["races"] = ["E1", "E2"]
        bot.state["race_paid"] = {"E1": {"close": T0 - 5 * 3600, "paid_model": 2.0},
                                  "E2": {"close": T0 - 4.5 * 3600, "paid_model": 3.0}}
        bot.state["pool0_base"] = {"t": T0 - 6 * 3600, "pool0": 100.0}
        x.pool0 = 100.0 + rise
        bot.pool0_step(clock[0])
        hit = any(r["ev"] == "payment_missing" for r in sink)
        ck(hit == want and (os.path.exists(stp) == want) and (bot.stopping == "payment_missing") == want,
           "3.12: pool 0 +$%.2f vs 50%% of $5.00 paid model 4 h after 2 races -> %s"
           % (rise, "stop file + payment_missing" if want else "payment_ok"))
        _rm(stp)
    clock, close, x, bot, sink, bk = world()
    bot.state["races"] = ["E1", "E2"]
    bot.state["race_paid"] = {"E1": {"close": T0 - 3 * 3600, "paid_model": 2.0},
                              "E2": {"close": T0 - 2 * 3600, "paid_model": 3.0}}
    bot.state["pool0_base"] = {"t": T0 - 6 * 3600, "pool0": 100.0}
    bot.pool0_step(clock[0])
    ck(not any(r["ev"] in ("payment_missing", "payment_ok") for r in sink) and any(r["ev"] == "pool0" for r in sink),
       "3.12: before 4 h have passed only the pool-0 reading is logged")

    # ---- 12. exchange fills, windows, controls (3.8) and dry run ----
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 200)
    x.orders["K1"]["fill_count_fp"] = "30.00"
    x.fills = [{"order_id": "K1", "count_fp": "10.00", "created_time": utc_iso(close - 300), "trade_id": "a"},
               {"order_id": "K1", "count_fp": "20.00", "created_time": utc_iso(close - 150), "trade_id": "b"},
               {"order_id": "ZZ", "count_fp": "99.00", "created_time": utc_iso(close - 150), "trade_id": "c"}]
    run(clock, bot, close + 30)
    xf_ = [r for r in sink if r["ev"] == "exchange_fill"]
    sm = [r for r in sink if r["ev"] == "race_summary"]
    lg = sm[0]["legs"]["ETH"] if sm else {}
    ck(len(xf_) == 2 and xf_[-1]["filled"] == 30.0 and lg.get("fills_by_window") == {"360-240": 10.0, "180-115": 20.0}
       and lg.get("largest_print") == 20.0 and lg.get("filled_exchange") == 30.0,
       "3.8: exchange-time fills logged cumulatively, by window (360-240: 10, 180-115: 20), largest print 20")
    ctl = (sm[0].get("controls") or {}) if sm else {}
    ck(set(ctl) == {"BTC", "SOL", "XRP", "HYPE"} and all(v["seconds"] > 200 for v in ctl.values()),
       "3.8: the 4 legs we did not post are logged as controls while our order rested")
    clock, close, x, bot, sink, bk = world(dry=True)
    run(clock, bot, close + 30)
    ck(not x.writes() and any(r["ev"] == "would_place" for r in sink)
       and any(r["ev"] == "would_cancel" and r["why"] == "exit" and 115.5 <= r["left"] <= 116.0 for r in sink),
       "dry run: no POST/DELETE; would_place, and would_cancel at 116 s left")

    # ---- 13. --report: C, M, P and the 4.2 verdicts ----
    rl, rp_, rs = os.path.join(tmpd, "live.jsonl"), os.path.join(tmpd, "rep.jsonl"), os.path.join(tmpd, "st.json")

    def rep(fill_per_leg, pool0_rise, now_h, n=20, other=False):
        c1 = T0
        with open(rl, "w", encoding="utf-8") as fh:
            for i in range(n):
                fh.write(json.dumps({"ev": "race_summary", "evt": "E%d" % i, "close": utc_iso(c1 + 2700 * i),
                                     "mode": "live", "legs": {"ETH": {"filled": fill_per_leg, "paid_model": 2.0,
                                                                      "count": 1100, "program_id": "p%d" % i}}}) + "\n")
        rr.save_state(rs, {"races": [], "pool0_base": {"t": c1 - 600, "pool0": 100.0}})
        last = c1 + 2700 * (n - 1)

        def s(m, p, b, q, timeout=None):
            if p == "/portfolio/balance":
                d = 100.0 + pool0_rise
                return 200, {"balance": int(d * 100), "balance_dollars": "%.4f" % d,
                             "balance_breakdown": [{"exchange_index": 0, "balance": "%.4f" % d}]}
            if p == "/incentive_programs":
                return 200, {"incentive_programs": [{"id": "p%d" % i, "end_date": utc_iso(c1)} for i in range(n)],
                             "cursor": ""}
            return 404, "?"
        lines = []
        if other:
            open(os.path.join(tmpd, "lip_orders.jsonl"), "w").close()
        report(s, out=lines.append, live_log=rl, state_path=rs, report_log=rp_, now=last + now_h * 3600,
               results=tmpd)
        _rm(os.path.join(tmpd, "lip_orders.jsonl"))
        v = [ln for ln in lines if "VERDICT" in ln]
        return v[0].split("VERDICT:")[1].split()[0] if v else None
    # 20 races x 1 leg: M = $40. PASS needs C <= $10 (1,000 contracts = 50/leg) and P >= $36.
    ck(rep(40, 38.0, 49) == "PASS", "report: C $8 (20%), P $38 (95%) at 48 h -> PASS")
    ck(rep(110, 38.0, 49) == "KILL", "report: C $22 (55%) -> KILL")
    ck(rep(40, 15.0, 49) == "KILL", "report: P $15 (37.5%) at 48 h -> KILL")
    ck(rep(70, 38.0, 49) == "EXTEND", "report: C $14 (35%) -> EXTEND by 20")
    ck(rep(40, 38.0, 1) == "TOO_EARLY" and rep(40, 10.0, 10) == "PROVISIONAL" and rep(40, 38.0, 49, n=12)
       == "INCOMPLETE", "report: < 2 h TOO_EARLY; 2-48 h PROVISIONAL (P not judged); 12 races INCOMPLETE")
    ck(rep(110, 38.0, 10) == "KILL", "report: C > 0.5 M is a KILL already at the 2 h read")
    ck(rep(40, 38.0, 49, other=True) == "UNREADABLE",
       "report: another reward bot's order log active in the window -> attribution refused (no PASS)")

    # ---- 14. source: one POST call site, no money movement ----
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.index(chr(10) + "class _FakeX")]
    ck(body.count('self._call("POST"') == 1 and body.count('_call("DELETE"') == 1
       and "/portfolio/subaccounts/transfer" not in body and "intra_exchange" not in body
       and "/deposits" not in body and "/withdrawals" not in body and "ordercli.DEMO" not in body
       and "--prod" not in body,"source: one create-order call site, one stray-cancel DELETE (+ rr.Bot.cancel), no "
                                 "transfer/deposit/withdrawal endpoint")
    m_ = src[src.rindex(chr(10) + "def main():"):]
    ck("InstanceLock(" in m_ and m_.index("InstanceLock(") < m_.index("Bot(") and "guarded(" in m_
       and m_.index("guarded(") < m_.index("Bot("), "main(): instance lock and guarded sender before the bot")

    for p in (spath, stp, alias, rl, rp_, rs, os.path.join(tmpd, "lock")):
        _rm(p)
    try:
        os.rmdir(tmpd)
    except OSError:
        pass
    if verbose:
        for n in notes:
            print("  ok  ", n)
    for m in fails:
        print("  FAIL", m)
    print("racev2_live self-test %s (%d checks, %d failed)" % ("PASSED" if not fails else "FAILED",
                                                               len(notes) + len(fails), len(fails)))
    return not fails


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Coin Race reward filler v2: the 20-race live test, subaccount 4 only")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--subaccount", type=int)
    mx = ap.add_mutually_exclusive_group()
    mx.add_argument("--live", action="store_true")
    mx.add_argument("--dry-run", action="store_true")
    mx.add_argument("--report", action="store_true", help="GET only: C, M, P and the spec 4.2 verdict")
    ap.add_argument("--races", type=int, default=RACES_MAX, help="1..20 races with an order (default 20)")
    ap.add_argument("--every", type=int, default=EVERY_DEFAULT, help="race sampling (default 3; 1..12)")
    ap.add_argument("--minutes", type=float, default=2160.0)
    ap.add_argument("--rest-books", action="store_true")
    a = ap.parse_args()
    if not selftest(a.verbose):
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    ok, shas = pins_ok()
    if not ok:
        raise SystemExit("REFUSED: imported files changed since validation: %s (want rr %s, shadow %s)"
                         % (shas, RR_SHA, SH_SHA))
    if a.subaccount != SUB:
        raise SystemExit("--subaccount 4 is required; this test runs in subaccount 4 only")
    if not (a.live or a.dry_run or a.report):
        raise SystemExit("choose one of --live / --dry-run / --report")
    if not (1 <= a.races <= RACES_MAX):
        raise SystemExit("--races must be 1..%d" % RACES_MAX)
    if not (1 <= a.every <= 12):
        raise SystemExit("--every must be 1..12")
    import ordercli
    pk = ordercli.load_key(rr.KEY_FILE)

    def raw(method, path, body, query, timeout=None):
        return rr.http_send(ordercli.PROD, pk, rr.KEY_ID, method, path, body=body, query=query,
                            timeout=rr.DEFAULT_TIMEOUT_S if timeout is None else timeout)
    sender = guarded(raw, writes_ok=bool(a.live))
    if a.report:
        return report(sender)
    lock = rr.InstanceLock(LIVE_LOCK if a.live else DRY_LOCK)
    if not lock.acquire():
        raise SystemExit("REFUSED: another racev2 %s process holds %s (%s)"
                         % ("live" if a.live else "dry-run", lock.path, lock.holder()))
    try:
        log = rr.Log(LIVE_LOG if a.live else DRY_LOG)
        state_path = LIVE_STATE if a.live else DRY_STATE
        bal = None
        for _try in range(5):                        # 10-23: the start reads retry 429s (the first two live starts refused on one
            bal = rr.read_balance(sender, SUB)       # unreadable read under the recorder's 429 storm; the ladder/forecaster do the same)
            if bal is not None:
                break
            time.sleep(2.0)
        state = rr.load_state(state_path)
        for k in ("test_halted", "payment_missing"):
            state.setdefault(k, None)
        day = rr.kalshi_day(sender, SUB, time.time())
        why = start_refusal(a.subaccount, bal, state, a.races, time.time(), [STOP_FILE, STOP_ALIAS], day)
        if a.dry_run and why:
            log.write("would_refuse_live_start", why=why, note="dry run continues; --live would stop here")
            print("  NOTE (dry run continues): --live would refuse: " + why)
            if len(state.get("races") or []) >= a.races:
                state["races"] = []
                rr.save_state(state_path, state)
        elif why:
            raise SystemExit("REFUSED: " + why)
        pool0 = None
        for _try in range(5):
            pool0 = read_main_pool0(sender)
            if pool0 is not None:
                break
            time.sleep(2.0)
        if a.live and pool0 is None:
            raise SystemExit("REFUSED: main pool 0 is unreadable (the payment tripwire needs its baseline)")
        books = rr.RestBooks()
        if not a.rest_books:
            try:
                books = rr.WSBooks(rr.KEY_ID, rr.KEY_FILE)
            except Exception as e:
                print("  WebSocket books unavailable (%r); REST books" % e)
        bot = Bot(log, a.dry_run, sender, time.time, books, state_path, STOP_FILE, a.races, every=a.every,
                  stop_alias=STOP_ALIAS)
        if a.live and not any(bot.sweep(time.time(), "startup") for _ in range(3)):
            raise SystemExit("REFUSED: could not list / cancel resting orders in subaccount %d at startup" % SUB)
        if day is not None and not a.dry_run:
            dd = bot._day(time.time())
            dd["realized"] = min(dd["realized"], day[0])
        if a.live and bot.state.get("pool0_base") is None:
            bot.state["pool0_base"] = {"t": time.time(), "pool0": pool0}
            bot.save()
        log.write("start", pid=os.getpid(), argv=sys.argv, code_sha=code_sha(), rr_sha=shas["rr_sha"],
                  shadow_sha=shas["shadow_sha"], mode="live" if a.live else "dry", subaccount=SUB, balance_pool2=bal,
                  kalshi_day=day, main_pool0=pool0, pool0_base=bot.state.get("pool0_base"), races_max=bot.races_max,
                  races_done=len(bot.state["races"]), every=a.every, books=type(books).__name__,
                  rails={"price": PRICE, "count_cap": COUNT_CAP, "exit_s": EXIT_S, "own_cancel_left": EXIT_S
                         + OWN_CANCEL_LEAD_S, "expiration_time": "close-115", "cancel_order_on_pause": True,
                         "post_floor": POST_FLOOR_USD, "pay_floor": PAY_FLOOR_USD, "paid_factor": PAID_FACTOR,
                         "starve_n": STARVE_N, "max_resting": MAX_RESTING, "max_collateral": MAX_COLLATERAL,
                         "day_stop": DAY_STOP, "test_stop": TEST_STOP, "bal_min": BAL_MIN, "bal_max": BAL_MAX,
                         "races_max_hard": RACES_MAX, "stop_files": [STOP_FILE, STOP_ALIAS]})
        print("racev2 %s: subaccount %d, pool-2 balance %s, main pool 0 %s, races %d/%d, every %d, log %s"
              % ("LIVE" if a.live else "DRY RUN", SUB, bal, pool0, len(bot.state["races"]), bot.races_max, a.every,
                 log.path))
        t_end = time.time() + a.minutes * 60.0
        try:
            while not bot.exit_ready:
                if time.time() > t_end and not bot.stopping:
                    bot.stopping = "minutes"
                    log.write("minutes_up")
                bot.step()
                time.sleep(0.25 + random.random() * 0.05)
        except KeyboardInterrupt:
            log.write("interrupted")
        finally:
            try:
                bot.wind_down(bot.stopping or "exit")
            except Exception as e:
                log.write("exit_cancel_error", err=repr(e)[:300])
            log.write("exit", why=bot.stopping, races_done=len(bot.state["races"]), writes=bot.writes)
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
