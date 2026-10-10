#!/usr/bin/env python3
"""racereward_live.py -- COIN RACE REWARD TEST: a 1c YES "filler" bid on DEAD coin-race legs, in a SUBACCOUNT.

THE OPERATOR, 2026-10-10: "Yes to coin race test." (the 20-race live probe in results/LADDER_UPSIDE_2026-10-10.md
section 7, the 09-25 sweep's SI05 / I05.)

WHY THIS COULD PAY
  Kalshi's Liquidity Incentive Program pays $20.00 per Coin Race leg per 15-minute window (period_reward 200000 is in
  CENTI-CENTS; the repo's 10-02 "$0.20" was a 100x unit error). A second counts only when BOTH sides of the leg's book
  hold the program target (1,000). In the last minutes of a race the four losing legs usually have NO YES bids at all
  -- every second is excluded and pays nobody. One 1,000-contract YES bid at 1c fills that side alone, makes those
  seconds count and takes the whole YES side's credit: $20 x seconds / 1,800 (the filing's arithmetic: each side's
  normalised scores sum to 1 per second; payout = reward x our share of all scores x counted / total seconds).
  It has NEVER been paid to this account; that is what the 20 races test (results/LADDER_UPSIDE_2026-10-10.md s.6).

WHAT IT DOES (Coin Race series KXCRYPTOLEAD15M: one event per 15 minutes, one market -- a "leg" -- per coin)
  In the last 360 s before each close, for each leg where
    (a) the best YES bid is <= $0.03                        (a dead leg),
    (b) the YES side's resting size is below the program target (1,000; read from GET /incentive_programs),
    (c) the best NO bid is <= $0.98                         (a 1c YES bid cannot cross it; re-read over REST first),
    (d) the NO side reaches the program target              (N4: otherwise none of the leg's seconds can count),
    (e) it can still earn the filing's $1 floor before the exit (N3): (exit - now - 2 s) x our share now x reward /
        (2 x period) >= $1.00 -- alone, 92 s or more of resting time before the exit,
    (f) the day budget holds (N2): today's realized - unsettled cost of held contracts - resting collateral - this
        order's $10 >= -$30 (so on a clean day at most 3 orders rest at once),
  it rests ONE post_only good-till-canceled order: buy <= 1,000 YES at exactly $0.01, self_trade_prevention_type
  'maker', in the given subaccount, on exchange_index 2. One order per coin per race, never re-placed -- also across a
  restart (N7: the coin is written to the state file BEFORE the order is sent).

  EXIT AT close-60 s (--exit-s; the 2026-10-10 money sweep, item 1): in the last minute sellers dump into 1c bids (87
  of 100 big 1c piles still up in the last 60 s got sold into). Pulling at 60 s cuts the expected fill cost from
  ~$7.50-15 to ~$2.80-5.10 a race for ~$2 less reward. Every order is cancelled starting at close-exit_s, and no new
  order is placed after close-exit_s. It is also cancelled as soon as the leg's best YES bid rises above $0.05 (the
  leg came alive), and on the stop file.

  CANCELS ARE GUARANTEED IN TIME (N1): from exit-15 s every call except a cancel and the cancel-confirm poll is
  refused locally (one gate, in Bot._call); no call can block into that window (its timeout is clamped to the time
  left before it, floor 2 s) and every call inside it carries a 2 s timeout. A cancel Kalshi has not confirmed is
  re-sent (every 0.5 s before the close, every 5 s after) and polled until Kalshi reports the order final (N5); it is
  never assumed gone or marked expired. A 404 on cancel is confirmed with a GET before the order is treated as gone
  (N6). A program list that cannot be read refuses the race (N10; no assumed $20/1,000).

PATTERNS REUSED (cited, not imported, so this process stays ~40 MB):
  discovery  pinracearm.discover(): GET /markets?series_ticker=KXCRYPTOLEAD15M&status=open, ticker.rpartition('-'),
             coin from custom_strike.Cryptocurrency, close_time, exactly 5 legs.
  orders     cleanroom/ladder_live.py: order_body / body_ok shape, POST /portfolio/events/orders, DELETE
             /portfolio/events/orders/{id} with subaccount + exchange_index as QUERY, ordercli's signing (path signed,
             not the query -- http_send below is ordercli.send with a caller-set timeout), the <=3 writes/s throttle
             (the key is shared with the live bot), the GET /portfolio/orders fill poller, the subaccount-0 refusal and
             the balance unit read from BOTH balance fields (hard rule 5). The self-test compares this file's body to
             ladder_live.order_body key by key.
  books      livebook.LiveBook (WebSocket orderbook_delta + trade): per-second book reads with no REST load; REST
             GET /markets/{t}/orderbook only as the last look before a send and as a fallback when the socket is down.

HARD RAILS (code, not flags)
  subaccount 0 refused; an unreadable balance refused; start refused under $45 or over $100 (pool 2); price exactly
  0.0100 (no caller passes a price); count <= 1,000; <= 5 orders resting; collateral resting + held <= $55; the day
  budget (f) on every new order; day stop once realized loss -- counting every unsettled fill as already lost --
  reaches $30 (ET day; survives a restart via results/racereward-live.state.json); the run ends after --races N
  (default 20) races with at least one order, ALSO across restarts (the count is in the state file), then cancels
  everything and exits; the stop file results/racereward-live.stop cancels everything and exits; <= 3 writes a second;
  one process per mode (results/racereward-live.lock, an OS lock the OS drops when the holder dies).
  Backstop no code can break: every leg closes at the race close and Kalshi cancels whatever still rests there.

LOGS
  results/racereward-live.jsonl (dry run: results/racereward-dry.jsonl, so a would-be order can never be read as a
  real one): start (argv, code sha), every decision with the book numbers, order / cancel (with its SEND time) / fill
  / reply, 'exchange_cancelled' when Kalshi shows an order canceled that we never asked to cancel (N8: a possible
  self-trade), a compact snapshot once a second per scored leg (YES walk size incl. ours, NO walk size, counted, our
  share), and a race summary with the expected credit by the filing's rules, fills and their cost -- also when the
  bot stops mid-race (N10).

    python research/sweep/racereward_live.py --selftest
    python research/sweep/racereward_live.py --subaccount N --dry-run --races 1
    python research/sweep/racereward_live.py --subaccount N --live --races 20
    python research/sweep/racereward_live.py --subaccount N --report        (GET only; leftover cash by ET day + bar)

THE BAR (N8, restated 2026-10-10 because the per-race bar could not be measured: a credit has no API line item)
  Read --report 48 h after the last race. PASS = leftover >= 50% of the SUM of expected_credit_floored over the live
  races, with fill cost <= 50% of that sum. FAIL = leftover < $1 in total. --report prints both per ET day and the
  verdict.

WHAT IT CANNOT TELL US
  Whether Kalshi pays this account (only the --report leftover 16-48 h later can); what OUR fills cost (the dry run
  bounds it from the public trade prints at 1c: low = after the queue that was ahead of us, high = as if first).
"""
import argparse
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(RESEARCH)
RESULTS = os.path.join(REPO, "results")
sys.path.insert(0, RESEARCH)

SERIES = "KXCRYPTOLEAD15M"
COINS = ("BTC", "ETH", "SOL", "XRP", "HYPE")
POOL = 2                          # Coin Race lives on exchange_index 2 (pinracearm.RACE_EXCHANGE_INDEX)
PRICE = "0.0100"                  # the ONLY price this file can send
COUNT_MAX = 1000
WINDOW_S = 360.0                  # act only in the last 360 s
EXIT_S_DEFAULT = 60.0             # every order is cancelled from close-60 s; nothing new after it (--exit-s)
EXIT_S_MIN, EXIT_S_MAX = 10.0, 240.0
QUIET_S = 15.0                    # N1: from exit-15 s only cancels and the cancel-confirm poll may call Kalshi
SHORT_TIMEOUT_S = 2.0             # N1: the timeout of every call inside that window
DEFAULT_TIMEOUT_S = 20.0          # ordercli.send's fixed timeout, used when nothing rests near its exit
CANCEL_RETRY_S = 0.5              # N5: an unconfirmed cancel is re-sent at most this often before the close ...
CANCEL_RETRY_CLOSED_S = 5.0       # ... and this often after it, until Kalshi reports the order final
FLOOR_USD = 1.00                  # N3: the filing pays a market-period result only when it is >= $1.00
FLOOR_MARGIN_S = 2.0              # N3: seconds of the projected window not counted (send latency, the snapshot grid)
DEAD_YES = 0.03                   # (a) best YES bid at or under this = a dead leg
ALIVE_YES = 0.05                  # best YES bid above this = the leg came alive -> cancel
NO_MAX = 0.98                     # (c) best NO bid at or under this; 0.99 would cross a 1c YES bid
MAX_RESTING = 5
MAX_COLLATERAL = 55.00
DAY_STOP = -30.00
BAL_MIN, BAL_MAX = 45.00, 100.00
WRITES_PER_S = 3
RACES_DEFAULT = 20
CID_PREFIX = "rrw-"
PREP_S = 450.0                    # read programs / subscribe books this long before a close
DISCOVER_EVERY_S = 30.0
PROGRAM_RETRY_S = 30.0            # N10: an unreadable program list is re-read this often (the race is refused till then)
POLL_FILLS_S = 2.0
FRESH_RETRY_S = 2.0               # a leg refused on the REST last look is re-checked at most this often
SETTLE_AFTER_S = 75.0
SETTLE_GIVEUP_S = 1800.0
SUMMARY_WAIT_S = 120.0            # a race summary waits this long after the close for unconfirmed orders, then is written
NEVER_CREATED_POLLS = 3           # a lost-reply order absent from this many order listings (>= 10 s) was never created
REST_BOOK_EVERY_S = 1.0           # fallback REST book read per leg (socket down)
LEGS_KEEP = 64                    # N7: per-coin-per-race records kept in the state file
BAR_WAIT_H = 48.0                 # N8: the bar is read this long after the last race
LIVE_LOG = os.path.join(RESULTS, "racereward-live.jsonl")
DRY_LOG = os.path.join(RESULTS, "racereward-dry.jsonl")
LIVE_STATE = os.path.join(RESULTS, "racereward-live.state.json")
DRY_STATE = os.path.join(RESULTS, "racereward-dry.state.json")
LIVE_LOCK = os.path.join(RESULTS, "racereward-live.lock")
DRY_LOCK = os.path.join(RESULTS, "racereward-dry.lock")
STOP_FILE = os.path.join(RESULTS, "racereward-live.stop")
REPORT_LOG = os.path.join(RESULTS, "racereward-report.jsonl")
KEY_FILE = r"C:\kals\kalshi.pem"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"
ON_BOOK = ("resting", "unknown", "cancelling", "cancel_failed", "cancel_unconfirmed")   # may still be live on Kalshi
CONFIRMABLE = ON_BOOK + ("cancelled",)          # off the book or not, Kalshi has not yet reported these final
IN_USE = {1: "the maker ladder", 2: "the forecaster", 3: "the weather dip-seller"}   # never share their subaccounts


# ------------------------------------------------------------------------------------------------ time and logging
def utc_iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _nth_sunday(y, month, n):
    d = datetime(y, month, 1, tzinfo=timezone.utc)
    return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))


def et_offset_h(t):
    """-4 (EDT) from the 2nd Sunday of March 07:00Z to the 1st Sunday of November 06:00Z, else -5 (EST)."""
    dt = datetime.fromtimestamp(t, timezone.utc)
    a = _nth_sunday(dt.year, 3, 2) + timedelta(hours=7)
    b = _nth_sunday(dt.year, 11, 1) + timedelta(hours=6)
    return -4 if a <= dt < b else -5


def et_day(t):
    return (datetime.fromtimestamp(t, timezone.utc) + timedelta(hours=et_offset_h(t))).strftime("%Y-%m-%d")


def parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class Log:
    def __init__(self, path=None, sink=None, clock=time.time):
        self.path, self.sink, self.clock = path, sink, clock
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def write(self, ev, **kw):
        r = {"t": utc_iso(time.time()), "ev": ev}
        r.update(kw)
        if self.sink is not None:
            self.sink.append(r)
        if self.fh is not None:
            try:
                self.fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
                self.fh.flush()
            except Exception:
                pass
        return r


# ------------------------------------------------------------------------------------------------ books and scoring
def f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def levels_from_rest(ob):
    """GET /markets/{t}/orderbook body -> ({px: size} YES bids, {px: size} NO bids), or None if unreadable.
    Units come from the field names (`*_dollars`, sizes `_fp` contracts), never from magnitudes (hard rule 5)."""
    if not isinstance(ob, dict) or not isinstance(ob.get("orderbook_fp"), dict):
        return None
    o = ob["orderbook_fp"]
    out = []
    for k in ("yes_dollars", "no_dollars"):
        d = {}
        for lv in o.get(k) or []:
            try:
                p, s = round(float(lv[0]), 4), float(lv[1])
            except (TypeError, ValueError, IndexError):
                return None
            if s > 0:
                d[p] = d.get(p, 0.0) + s
        out.append(d)
    return out[0], out[1]


def best(lv):
    return max(lv) if lv else None


def ticks_between(hi, lo, linear=True):
    """Ticks from lo up to hi (0 when lo >= hi). Coin Race is linear_cent; the tapered grid is kept for safety."""
    if hi <= lo + 1e-9:
        return 0
    if linear:
        return int(round((hi - lo) * 100))
    n, p = 0, lo
    while p < hi - 1e-9 and n < 5000:
        p = round(p + (0.001 if (p < 0.10 - 1e-9 or p >= 0.90 - 1e-9) else 0.01), 4)
        n += 1
    return n


def walk(levels, target, df, ours=0.0, our_px=0.01, linear=True):
    """The filing's walk (CFTC 2026-07-15) for ONE side. `levels` = everyone ELSE's bids {px: size}; `ours` = our size
    at our_px. The highest bid must be under the highest possible price; walk best-first adding whole price levels;
    Reference = the first level where the running size reaches target/5; stop at the level where it reaches target;
    no qualifying bids if it never does. Score = df ** ticks below the reference x size (full credit at or above it).
    Returns {q, ref, tot (size walked), share (our normalised score, 0 when not qualifying)}."""
    top = 0.99 if linear else 0.999
    lv = {p: s for p, s in levels.items() if s > 0}
    if ours > 0:
        lv[round(our_px, 4)] = lv.get(round(our_px, 4), 0.0) + ours
    pxs = sorted(lv, reverse=True)
    if not pxs or pxs[0] >= top - 1e-9:
        return {"q": False, "ref": None, "tot": 0.0, "share": 0.0}
    tot, ref, used, reached = 0.0, None, [], False
    for p in pxs:
        tot += lv[p]
        used.append(p)
        if ref is None and tot >= target / 5.0 - 1e-9:
            ref = p
        if tot >= target - 1e-9:
            reached = True
            break
    if not reached:
        return {"q": False, "ref": ref, "tot": tot, "share": 0.0}
    s_all = sum(df ** ticks_between(ref, p, linear) * lv[p] for p in used)
    s_us = 0.0
    if ours > 0 and any(abs(p - our_px) < 1e-9 for p in used):
        s_us = df ** ticks_between(ref, our_px, linear) * ours
    return {"q": True, "ref": ref, "tot": tot, "share": (s_us / s_all) if s_all > 0 else 0.0}


def others_of(yes_lv, ours_on_book):
    """Remove our own resting size from the 1c YES level of a book that INCLUDES it (live mode)."""
    lv = dict(yes_lv)
    if ours_on_book > 0 and 0.01 in lv:
        lv[0.01] = max(0.0, lv[0.01] - min(ours_on_book, lv[0.01]))
        if lv[0.01] <= 0:
            del lv[0.01]
    return lv


def snapshot(yes_others, no_lv, ours, prog, linear=True):
    """One second scored by the filing: our YES share, counted only if BOTH sides reach the target."""
    y = walk(yes_others, prog["target"], prog["df"], ours=ours, linear=linear)
    n = walk(no_lv, prog["target"], prog["df"], linear=linear)
    ok = bool(y["q"] and n["q"])
    return {"yq": round(y["tot"], 2), "yref": y["ref"], "nq": round(n["tot"], 2), "nref": n["ref"], "ok": ok,
            "sh": round(y["share"], 5) if ok else 0.0}


def credit(reward, period_s, share_seconds):
    """Dollars = reward x (sum over counted seconds of our yes + no share) / (2 x seconds in the period)."""
    if not period_s or period_s <= 0:
        return 0.0
    return reward * share_seconds / (2.0 * period_s)


def floored(x):
    """The filing pays a market-period result only when it is >= $1.00."""
    return x if x >= FLOOR_USD - 1e-9 else 0.0


def period_of(prog):
    return (prog["end"] - prog["start"]) if prog.get("end") and prog.get("start") else 900.0


def leg_refusal(yes_lv, no_lv, target, linear=True):
    """None if a leg is a dead leg we may fill, else the reason. Books are everyone else's bids (ours excluded)."""
    by, bn = best(yes_lv), best(no_lv)
    if by is not None and by > DEAD_YES + 1e-9:
        return "not_dead"
    if sum(yes_lv.values()) >= target - 1e-9:
        return "yes_side_full"
    if bn is not None and bn > NO_MAX + 1e-9:
        return "would_cross"
    if not walk(no_lv, target, 0.5, linear=linear)["q"]:
        return "no_side_short"          # N4: the NO side under the target -> none of the leg's seconds count
    return None


def book_numbers(yes_lv, no_lv):
    return {"by": best(yes_lv), "bn": best(no_lv), "ytot": round(sum(yes_lv.values()), 2),
            "ntot": round(sum(no_lv.values()), 2), "y1c": round(yes_lv.get(0.01, 0.0), 2),
            "ylv": sorted(yes_lv.items(), reverse=True)[:4], "nlv": sorted(no_lv.items(), reverse=True)[:4]}


# ------------------------------------------------------------------------------------------------ orders
def order_body(ticker, count, sub, cid):
    """Buy YES at exactly $0.01 (a bid). There is no price argument: 0.0100 is the only price this file can build."""
    return {"ticker": ticker, "side": "bid", "count": "%.2f" % float(count), "price": PRICE,
            "time_in_force": "good_till_canceled", "self_trade_prevention_type": "maker",
            "post_only": True, "client_order_id": cid, "subaccount": int(sub), "exchange_index": POOL}


def body_ok(b, sub):
    """Every order body must carry these, or it is not sent."""
    try:
        c = float(b.get("count"))
    except (TypeError, ValueError):
        return False
    return (b.get("post_only") is True and int(sub) >= 1 and b.get("subaccount") == int(sub)
            and b.get("exchange_index") == POOL and b.get("price") == PRICE and b.get("side") == "bid"
            and 0 < c <= COUNT_MAX and b.get("self_trade_prevention_type") == "maker"
            and b.get("time_in_force") == "good_till_canceled"
            and str(b.get("client_order_id", "")).startswith(CID_PREFIX)
            and str(b.get("ticker", "")).startswith(SERIES + "-"))


def http_send(base, pk, key_id, method, path, body=None, query=None, timeout=DEFAULT_TIMEOUT_S):
    """ordercli.send with a caller-set timeout (N1: 2 s near the exit; ordercli's is a fixed 20 s). Signs the PATH only
    with ordercli.sign_headers and appends the query unsigned, exactly as ordercli.send does. The timeout is urllib's
    (per socket operation)."""
    import urllib.error
    import urllib.request
    import ordercli
    q = "" if not query else "?" + "&".join("%s=%s" % (k, v) for k, v in query.items())
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path + q, data=data, method=method)
    for k, v in ordercli.sign_headers(pk, key_id, method, "/trade-api/v2" + path).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:
        return -1, str(e)


def read_balance(sender, sub, pool=POOL):
    """Cash in one pool of one subaccount, or None. Both `balance` (cents) and `balance_dollars` must be present and
    agree to a cent: the unit is read, never inferred (hard rule 5; ladder_live.read_pot)."""
    st, b = sender("GET", "/portfolio/balance", None, {"subaccount": int(sub), "exchange_index": int(pool)})
    try:
        d, c = float(b["balance_dollars"]), float(b["balance"])
    except Exception:
        return None
    if st != 200 or abs(c / 100.0 - d) > 0.011:
        return None
    return d


def kalshi_day(sender, sub, now):
    """(realized P&L of today's ET day, cost of open positions) for the subaccount, from Kalshi itself -- so the day
    stop survives a restart even if the state file missed a settlement. None if either read is unreadable."""
    import pinledger
    rows, ok = _pages(sender, "/portfolio/settlements", "settlements", {"subaccount": int(sub)}, maxpages=20)
    pos, ok2 = _pages(sender, "/portfolio/positions", "market_positions",
                      {"subaccount": int(sub), "count_filter": "position", "settlement_status": "unsettled"})
    if not (ok and ok2):
        return None
    d = et_day(now)
    real = sum(pinledger.pnl(s) for s in rows if et_day(parse_ts(s.get("settled_time")) or 0) == d)
    held = sum(abs(f(x.get("market_exposure_dollars"), 0.0)) for x in pos)
    return round(real, 4), round(held, 4)


def start_refusal(sub, balance, state, races_max, now, stop_path, day=(0.0, 0.0)):
    """Every reason the bot may NOT start (live). None = ok. `day` = kalshi_day() (None = unreadable)."""
    if sub is None or int(sub) < 1:
        return "subaccount %s: the primary account (0) is refused; a subaccount 1..63 is required" % sub
    if int(sub) in IN_USE:
        return "subaccount %d belongs to %s; this test needs its own NEW subaccount" % (int(sub), IN_USE[int(sub)])
    if balance is None:
        return "subaccount %s balance (pool %d) is unreadable" % (sub, POOL)
    if balance < BAL_MIN - 1e-9:
        return "subaccount %s holds $%.2f in pool %d, under the $%.0f floor" % (sub, balance, POOL, BAL_MIN)
    if balance > BAL_MAX + 1e-9:
        return "subaccount %s holds $%.2f in pool %d, over the $%.0f ceiling" % (sub, balance, POOL, BAL_MAX)
    if state.get("halted_day") == et_day(now):
        return "day stop already hit on %s (state file)" % state["halted_day"]
    if day is None:
        return "today's settled P&L / open positions in subaccount %s are unreadable" % sub
    if day[1] > 0:
        return ("subaccount %s holds $%.2f of open positions; start when it is flat (they settle ~1 min after close)"
                % (sub, day[1]))
    if day[0] <= DAY_STOP + 1e-9:
        return "today's settled P&L in subaccount %s is $%.2f <= the $%.0f day stop" % (sub, day[0], DAY_STOP)
    if len(state.get("races") or []) >= races_max:
        return "%d races with an order already done (state file) >= --races %d" % (len(state["races"]), races_max)
    if os.path.exists(stop_path):
        return "stop file present: %s" % stop_path
    return None


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            s = json.load(fh)
        if isinstance(s, dict):
            s.setdefault("races", [])
            s.setdefault("days", {})
            s.setdefault("settled", {})
            s.setdefault("halted_day", None)
            s.setdefault("legs", {})
            return s
    except (OSError, ValueError):
        pass
    return {"races": [], "days": {}, "settled": {}, "halted_day": None, "legs": {}}


def save_state(path, s):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1)
    os.replace(tmp, path)


class InstanceLock:
    """N7: one process per mode. An OS byte-range lock (msvcrt on Windows, flock elsewhere) on a byte past the pid
    line; the OS drops it when the holder dies, so a crash never leaves a stale lock and no pid test is needed
    (os.kill(pid, 0) TERMINATES the process on Windows -- never use it as a liveness probe)."""
    OFFSET = 4096

    def __init__(self, path):
        self.path, self.fd = path, None

    def acquire(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, self.OFFSET, 0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self.fd = fd
        try:
            os.lseek(fd, 0, 0)
            os.write(fd, ("pid %d since %s" % (os.getpid(), utc_iso(time.time()))).ljust(80).encode() + b"\n")
        except OSError:
            pass
        return True

    def holder(self):
        try:
            with open(self.path, encoding="utf-8", errors="replace") as fh:
                return fh.readline().strip()
        except OSError:
            return "?"

    def release(self):
        if self.fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(self.fd, self.OFFSET, 0)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None


# ------------------------------------------------------------------------------------------------ book providers
class RestBooks:
    """No socket: levels() is always None, so the bot reads REST books itself -- through its own call gate (N1 timeouts
    and quiet zone) and at most once a second per leg."""

    def levels(self, tk):
        return None

    def subscribe(self, tks):
        pass

    def drop(self, tks):
        pass

    def sells_1c(self, tk, since_ms):
        return None

    def connected(self):
        return False


class WSBooks:
    """livebook.LiveBook, plus a count of taker prints that SOLD YES at 1c (taker bought NO at 99c) per watched leg --
    the public flow that hits 1c YES bids, for the dry run's would-fill bound."""

    def __init__(self, key_id, key_file):
        import livebook

        class _LB(livebook.LiveBook):
            def __init__(s, *a, **k):
                super().__init__(*a, **k)
                s.hits = {}

            def _on_trade(s, msg, rx_ms):
                super()._on_trade(msg, rx_ms)
                try:
                    tk = msg.get("market_ticker")
                    if tk in s.wanted and msg.get("taker_side") == "no" \
                            and float(msg.get("yes_price_dollars")) <= 0.0100 + 1e-9:
                        n = float(msg.get("count_fp") if msg.get("count_fp") is not None else msg.get("count"))
                        ts = int(msg.get("ts_ms") or rx_ms)
                        s.hits.setdefault(tk, []).append((ts, n))
                except Exception:
                    pass
        self.lb = _LB(key_id=key_id, key_file=key_file)
        self.started = False

    def connected(self):
        return self.lb.connected.is_set()

    def subscribe(self, tks):
        if not self.started:
            self.lb.start(list(tks))
            self.started = True
        else:
            self.lb.subscribe(list(tks))

    def drop(self, tks):
        self.lb.drop(list(tks))
        for tk in tks:
            self.lb.hits.pop(tk, None)

    def levels(self, tk):
        if not self.lb.connected.is_set():
            return None
        with self.lb.lock:
            b, m = self.lb.books.get(tk), self.lb.meta.get(tk)
            if b is None or m is None or m.get("suspect") or m.get("await_snapshot"):
                return None
            return dict(b["yes"]), dict(b["no"])

    def sells_1c(self, tk, since_ms):
        rows = self.lb.hits.get(tk)
        if rows is None:
            return 0.0 if self.connected() else None
        return sum(n for ts, n in list(rows) if ts >= since_ms)


# ------------------------------------------------------------------------------------------------ the bot
class Bot:
    def __init__(self, log, sub, dry, sender, now, books, state_path, stop_path, races_max,
                 sleep=time.sleep, exit_s=EXIT_S_DEFAULT):
        self.log, self.sub, self.dry, self.send, self.now = log, int(sub), bool(dry), sender, now
        self.books = books
        self.state_path, self.stop_path, self.races_max, self.sleep = state_path, stop_path, races_max, sleep
        self.exit_s = float(exit_s)
        self.state = load_state(state_path)
        self.races = {}               # evt -> race dict
        self.orders = {}              # local id -> order dict
        self.next_id = 1
        self.stopping = None          # reason string once the bot is winding down
        self.exit_ready = False
        self._w = []                  # write timestamps (throttle)
        self.last_discover = -1e18
        self.last_poll = -1e18
        self.last_stop_sweep = -1e18
        self.last_slot = None
        self.rest_seen = {}           # tk -> (t, levels) fallback cache
        self.writes = 0
        self.quiet_refused = 0

    # ---------------- state ----------------
    def _day(self, t):
        d = et_day(t)
        return self.state["days"].setdefault(d, {"realized": 0.0, "fills_cost": 0.0, "credit_exp": 0.0})

    def save(self):
        try:
            save_state(self.state_path, self.state)
            return True
        except Exception as e:
            self.log.write("state_error", err=repr(e)[:200])
            return False

    def unsettled_cost(self):
        return sum(o["cost"] + o["fees"] for o in self.orders.values() if o["filled"] > 0 and not o.get("settled"))

    def resting(self):
        return [o for o in self.orders.values() if o["status"] in ON_BOOK]

    def resting_collateral(self):
        # B1 (re-review 2026-10-10): an order whose cancel was ACKNOWLEDGED but which Kalshi has not yet reported
        # final may carry a fill the poller has not seen yet; it keeps counting at (count - filled) until the poll
        # marks it final, so the day budget can never be spent twice inside the ~2 s poll gap.
        return sum(0.01 * max(0.0, o["count"] - o["filled"]) for o in self.orders.values()
                   if o["status"] in ON_BOOK or (o["status"] == "cancelled" and not o.get("final")))

    def collateral(self):
        return self.resting_collateral() + self.unsettled_cost()

    def halted(self, t):
        return self.state.get("halted_day") == et_day(t)

    def rails_refusal(self, count, t, evt=None):
        if self.stopping:
            return "stopping:" + self.stopping
        if self.halted(t):
            return "day_stop"
        if evt not in self.state["races"] and len(self.state["races"]) >= self.races_max:
            return "races_done"
        if len(self.resting()) >= MAX_RESTING:
            return "max_resting"
        if self.collateral() + 0.01 * count > MAX_COLLATERAL + 1e-9:
            return "max_collateral"
        # N2: the day stop as a BUDGET -- every held contract and every resting order counted as already lost, plus
        # this order's full cost. A new order may take the worst case to -$30, never past it.
        worst = self._day(t)["realized"] - self.unsettled_cost() - self.resting_collateral() - 0.01 * count
        if worst < DAY_STOP - 1e-9:
            return "day_budget"
        return None

    def check_day_stop(self, t):
        d = self._day(t)
        worst = d["realized"] - self.unsettled_cost()
        if worst <= DAY_STOP + 1e-9 and not self.halted(t):
            self.state["halted_day"] = et_day(t)
            self.save()
            self.log.write("day_stop", day=et_day(t), realized=round(d["realized"], 4),
                           unsettled_cost=round(self.unsettled_cost(), 4), worst=round(worst, 4))
            self.stopping = self.stopping or "day_stop"

    # ---------------- every call to Kalshi goes through here (N1) ----------------
    def exit_t(self, r):
        return r["close"] - self.exit_s

    def quiet(self, t):
        """N1: True from exit-QUIET_S until the close while any order of ours may still rest in that race."""
        return any(o["close"] - self.exit_s - QUIET_S <= t < o["close"] for o in self.resting())

    def timeout_for(self, t):
        """N1: no call may block into a quiet zone -- its timeout is the time left before the zone (floor 2 s), and
        2 s inside it until 10 s after the close of any race we had an order in (and after that while an order is
        unconfirmed). 20 s when no order of ours is near its exit."""
        to = DEFAULT_TIMEOUT_S
        for r in self.races.values():
            if r["placed"] and t < r["close"] + 10.0:
                to = min(to, max(SHORT_TIMEOUT_S, r["close"] - self.exit_s - QUIET_S - t))
        for o in self.resting():
            to = min(to, max(SHORT_TIMEOUT_S, o["close"] - self.exit_s - QUIET_S - t))
        return to

    def _call(self, method, path, body=None, query=None, cancel_path=False):
        """The one gate to Kalshi. In a quiet zone only cancels and the cancel-confirm poll (cancel_path=True) are
        sent; anything else is refused HERE, without a network call, as status -2."""
        now = self.now()
        if not cancel_path and self.quiet(now):
            self.quiet_refused += 1
            return -2, "quiet zone: only cancels and the cancel-confirm poll (N1)"
        try:
            return self.send(method, path, body, query, timeout=self.timeout_for(now))
        except Exception as e:
            return -1, repr(e)[:200]

    def _throttle(self):
        t = self.now()
        self._w = [x for x in self._w if t - x < 1.0]
        if len(self._w) >= WRITES_PER_S:
            self.sleep(max(0.0, 1.0 - (t - self._w[0])) + 0.001)
            t = self.now()
            self._w = [x for x in self._w if t - x < 1.0]
        self._w.append(self.now())

    # ---------------- the $1 floor (N3) ----------------
    @staticmethod
    def count_for(prog):
        return int(min(COUNT_MAX, max(1, round(prog["target"]))))

    def floor_check(self, r, tk, yes_lv, no_lv, prog, count, t):
        """N3: (exit - now - margin) x our share now x reward / (2 x period) >= $1, else the order can never be paid.
        Returns (ok, projected dollars, share)."""
        sn = snapshot(yes_lv, no_lv, count, prog, r["linear"].get(tk, True))
        end = self.exit_t(r)
        if prog.get("end"):
            end = min(end, prog["end"])
        start = max(t, prog.get("start") or t)
        secs = max(0.0, end - start - FLOOR_MARGIN_S)
        proj = credit(prog["reward"], period_of(prog), secs * sn["sh"])
        return proj >= FLOOR_USD - 1e-9, proj, sn["sh"]

    # ---------------- writes ----------------
    def place(self, r, tk, prog, nums, t):
        coin = r["coin_of"][tk]
        count = self.count_for(prog)
        if t >= self.exit_t(r) or self.quiet(t):          # EXIT: nothing new from close-exit_s (N1: nor in a quiet zone)
            self._once(r, tk, "past_exit", left=round(r["close"] - t, 1))
            return
        why = self.rails_refusal(count, t, r["evt"])
        if why:
            self._once(r, tk, "rail_" + why, left=round(r["close"] - t, 1), **nums)
            return
        legs = self.state.setdefault("legs", {})
        if coin in (legs.get(r["evt"]) or []):            # N7: this coin already had its order in this race
            r["done"].add(tk)
            self._once(r, tk, "already_ordered", left=round(r["close"] - t, 1))
            return
        oid = self.next_id
        self.next_id += 1
        cid = "%s%d-%d" % (CID_PREFIX, int(time.time()), oid)
        b = order_body(tk, count, self.sub, cid)
        if not body_ok(b, self.sub):
            self.log.write("body_refused", body=b)
            r["done"].add(tk)
            return
        # N7: the coin is recorded and SAVED before anything is sent, so a restart can never send a second order
        legs.setdefault(r["evt"], []).append(coin)
        for k in list(legs)[:-LEGS_KEEP]:
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
             "cancel_try_t": None, "cancel_sent_t": None, "cancel_t": None}
        self.orders[oid] = o
        r["placed"][tk] = oid
        r["counted"] = True
        if self.dry:
            o["status"], o["kid"] = "resting", "dry-%d" % oid
            self.log.write("would_place", evt=r["evt"], coin=coin, left=round(r["close"] - t, 1), body=b, **nums)
            return
        self._throttle()
        self.writes += 1
        st, resp = self._call("POST", "/portfolio/events/orders", b, None)
        rec = (resp.get("order") or resp) if isinstance(resp, dict) else {}
        if st in (200, 201) and isinstance(rec, dict) and rec.get("order_id"):
            o["kid"], o["status"] = rec.get("order_id"), "resting"
            self.log.write("placed", evt=r["evt"], coin=coin, left=round(r["close"] - t, 1), body=b,
                           order_id=o["kid"], resp=str(resp)[:300], **nums)
            got = f(rec.get("fill_count_fp"), f(rec.get("fill_count"), 0.0))
            if got:
                self.on_fill(o, got, t)
        elif st == -2:
            o["status"], o["final"] = "not_sent", True     # refused by the gate: nothing went out
            self.log.write("not_sent", evt=r["evt"], coin=coin, resp=str(resp)[:200])
        elif isinstance(st, int) and 400 <= st < 500 and st != 429:
            o["status"], o["final"] = "rejected", True
            self.log.write("rejected", evt=r["evt"], coin=coin, status=st, body=b, resp=str(resp)[:300])
        else:
            # a lost reply (-1, 429, 5xx): the order may exist. Counted as on the book until the poller finds it by
            # client_order_id (or finds it never existed); the exit sweep cancels anything of ours still resting.
            o["status"] = "unknown"
            self.log.write("place_unknown", evt=r["evt"], coin=coin, status=st, body=b, resp=str(resp)[:300])

    def cancel(self, o, why, t):
        if o["status"] not in ON_BOOK:
            return
        o["cancel_why"] = o["cancel_why"] or why
        o["cancel_try_t"] = t
        if self.dry:
            ts = self.now()
            o["status"], o["cancel_t"], o["cancel_sent_t"], o["final"] = "cancelled", ts, ts, True
            self.log.write("would_cancel", evt=o["evt"], coin=o["coin"], why=why, left=round(o["close"] - ts, 2))
            return
        if not o.get("kid"):
            o["status"] = "cancel_failed"          # unknown order id: the sweep / poller (by client_order_id) find it
            return
        o["status"] = "cancelling"
        o["tries"] += 1
        self._throttle()
        self.writes += 1
        o["cancel_sent_t"] = ts = self.now()      # N1: the SEND time (after the throttle), not the step's start
        st, resp = self._call("DELETE", "/portfolio/events/orders/%s" % o["kid"], None,
                              {"subaccount": self.sub, "exchange_index": POOL}, cancel_path=True)
        if st in (200, 201):
            o["status"], o["cancel_t"] = "cancelled", ts
            rec = (resp.get("order") or resp) if isinstance(resp, dict) else {}
            got = f(rec.get("fill_count_fp"), None) if isinstance(rec, dict) else None
            if got:
                self.on_fill(o, got, t)
        elif st == 404:
            o["status"] = "cancel_unconfirmed"     # N6: maybe filled, maybe not -- a GET decides, never an assumption
        else:
            o["status"] = "cancel_failed"
        self.log.write("cancelled" if st in (200, 201) else "cancel_reply", evt=o["evt"], coin=o["coin"], why=why,
                       order_id=o["kid"], status=st, tries=o["tries"], left=round(o["close"] - ts, 2),
                       sent_left=round(o["close"] - ts, 3), resp=str(resp)[:200])
        if st == 404:
            self.poll_orders(self.now())           # N6: confirmed by GET before it is treated as gone

    def sweep(self, t, why, tickers=None):
        """Cancel every RESTING order of ours (client_order_id prefix) in the subaccount, found by GET -- the net under
        a lost reply or a lost order id. Live only. True only when the listing was read AND every stray cancel was
        accepted (a 404 or failure is re-checked by the next listing)."""
        if self.dry:
            return True
        st, r = self._call("GET", "/portfolio/orders", None, {"subaccount": self.sub, "status": "resting",
                                                              "limit": 200}, cancel_path=True)
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
                st2, _ = self._call("DELETE", "/portfolio/events/orders/%s" % kid, None,
                                    {"subaccount": self.sub, "exchange_index": POOL}, cancel_path=True)
                self.log.write("sweep_cancel_stray", order_id=kid, cid=x.get("client_order_id"), status=st2)
                if st2 not in (200, 201):
                    ok = False
            n += 1
        if n:
            self.log.write("sweep", why=why, found=n, ok=ok)
        return ok

    # ---------------- fills and settlement ----------------
    def on_fill(self, o, total, t):
        if total is None or total <= o["filled"] + 1e-9:
            return
        d = total - o["filled"]
        o["filled"] = total
        o["cost"] += d * 0.01
        self._day(t)["fills_cost"] += d * 0.01
        self.log.write("fill", evt=o["evt"], coin=o["coin"], order_id=o["kid"], delta=d, filled=total,
                       cost=round(o["cost"], 4), left=round(o["close"] - t, 2))
        self.check_day_stop(t)

    def needs_confirm(self):
        return any(not o.get("final") and o["status"] in CONFIRMABLE and o["status"] != "resting"
                   for o in self.orders.values())

    def poll_orders(self, t):
        """GET /portfolio/orders: fills, lost-reply reconciliation, cancel confirmation (N5/N6), and orders Kalshi
        cancelled that we never asked to cancel (N8). True when the listing was read."""
        if self.dry:
            return True
        live = [o for o in self.orders.values() if not o.get("final") and o["status"] in CONFIRMABLE]
        if not live:
            return True
        mts = int(min(o["placed_t"] for o in live) - 120)
        st, r = self._call("GET", "/portfolio/orders", None, {"subaccount": self.sub, "min_ts": mts, "limit": 200},
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
                    o["status"] = "cancel_failed"          # N6: the 404 was wrong -- it rests; cancel_due re-sends
                    self.log.write("cancel_404_still_resting", evt=o["evt"], coin=o["coin"], order_id=o["kid"],
                                   left=round(o["close"] - t, 2))
            elif s in ("executed", "canceled", "cancelled"):
                if s != "executed" and o["tries"] == 0 and not o.get("cancel_why") \
                        and o["status"] in ("resting", "unknown"):
                    # N8: Kalshi cancelled an order we never asked to cancel. Our orders are maker-STP, so a
                    # self-trade cancels OURS: this is how a possible self-match shows up (or the market closing).
                    self.log.write("exchange_cancelled", evt=o["evt"], coin=o["coin"], order_id=o["kid"],
                                   left=round(o["close"] - t, 2), after_close=t >= o["close"], filled=o["filled"],
                                   kalshi=str(x)[:300])
                if o["status"] in ON_BOOK:
                    if o["status"] in ("cancel_unconfirmed", "cancel_failed", "cancelling"):
                        self.log.write("cancel_confirmed", evt=o["evt"], coin=o["coin"], order_id=o["kid"],
                                       kalshi_status=s, left=round(o["close"] - t, 2))
                    o["status"] = "filled" if s == "executed" else "cancelled"
                if o.get("cancel_t") is None:
                    o["cancel_t"] = t
                o["final"] = True
        for o in live:
            if o["id"] in seen or o.get("kid"):
                continue
            o["unseen"] = o.get("unseen", 0) + 1         # a lost reply whose order Kalshi has never listed
            if o["unseen"] >= NEVER_CREATED_POLLS and t - o["placed_t"] >= 10.0:
                o["status"], o["final"] = "never_created", True
                self.log.write("never_created", evt=o["evt"], coin=o["coin"], cid=o["cid"], polls=o["unseen"])
        return True

    def settle(self, t):
        for o in self.orders.values():
            if o["filled"] <= 0 or o.get("settled") or t < o["close"] + SETTLE_AFTER_S:
                continue
            if t - o.get("settle_try", -1e18) < 30:
                continue
            o["settle_try"] = t
            st, m = self._call("GET", "/markets/%s" % o["tk"])
            res = ((m or {}).get("market") or {}).get("result") if st == 200 and isinstance(m, dict) else None
            if res not in ("yes", "no"):
                if t > o["close"] + SETTLE_GIVEUP_S:
                    self.log.write("settle_unknown", evt=o["evt"], coin=o["coin"], status=st)
                    o["settled"] = True     # stays counted as lost in the day's worst case (conservative): see below
                    self._day(o["close"])["realized"] -= o["cost"] + o["fees"]
                continue
            pnl = (o["filled"] if res == "yes" else 0.0) - o["cost"] - o["fees"]
            o["settled"], o["result"], o["pnl"] = True, res, pnl
            self._day(o["close"])["realized"] += pnl
            self.state["settled"][o["tk"]] = round(pnl, 4)
            self.save()
            self.log.write("settle", evt=o["evt"], coin=o["coin"], result=res, filled=o["filled"],
                           cost=round(o["cost"], 4), fees=round(o["fees"], 4), pnl=round(pnl, 4),
                           day_realized=round(self._day(o["close"])["realized"], 4))
            self.check_day_stop(t)

    # ---------------- discovery and race preparation ----------------
    def discover(self, t):
        """pinracearm.discover(), through this file's sender: open Coin Race events with exactly five legs."""
        st, b = self._call("GET", "/markets", None, {"series_ticker": SERIES, "status": "open", "limit": "200"})
        if st != 200 or not isinstance(b, dict):
            self.log.write("discover_unreadable", status=st)
            return {}
        out = {}
        for m in b.get("markets") or []:
            tk = m.get("ticker") or ""
            evt, _, leg = tk.rpartition("-")
            coin = (m.get("custom_strike") or {}).get("Cryptocurrency") or leg
            cs = parse_ts(m.get("close_time"))
            if coin not in COINS or cs is None:
                continue
            e = out.setdefault(evt, {"close": cs, "legs": {}, "grid": {}})
            e["legs"][coin] = tk
            e["grid"][tk] = m.get("price_level_structure")
        return {k: v for k, v in out.items() if len(v["legs"]) == 5}

    def programs(self, tickers):
        """{ticker: program} from GET /incentive_programs (status=active, type=liquidity), paged. The endpoint ignores
        series/market filters (probed 10-10), so the list is read and filtered here. None if unreadable."""
        out, cur = {}, None
        for _ in range(10):
            q = {"status": "active", "type": "liquidity", "limit": "5000"}
            if cur:
                q["cursor"] = cur
            st, b = self._call("GET", "/incentive_programs", None, q)
            if st != 200 or not isinstance(b, dict):
                return None
            for p in b.get("incentive_programs") or []:
                tk = p.get("market_ticker")
                if tk in tickers:
                    rw, tg, df = f(p.get("period_reward")), f(p.get("target_size_fp")), f(p.get("discount_factor_bps"))
                    if rw is None or tg is None or df is None:
                        continue
                    out[tk] = {"reward": rw / 10000.0, "target": tg, "df": df / 10000.0,
                               "start": parse_ts(p.get("start_date")), "end": parse_ts(p.get("end_date")),
                               "id": p.get("id")}       # period_reward is CENTI-CENTS
            cur = b.get("cursor") or b.get("next_cursor")
            if not cur or not b.get("incentive_programs"):
                break
        return out

    def load_programs(self, r, t):
        """N10: an unreadable list REFUSES the race's legs (no assumed $20/1,000) and is re-read every 30 s."""
        r["prog_t"] = t
        progs = self.programs(set(r["legs"].values()))
        if progs is None:
            self.log.write("program_list_unreadable", evt=r["evt"],
                           action="every leg refused until it reads; re-read every %d s" % PROGRAM_RETRY_S)
            return False
        r["prog"] = {tk: progs[tk] for tk in r["legs"].values() if tk in progs}
        r["prog_ok"] = True
        return True

    def prepare(self, evt, e, t):
        tks = list(e["legs"].values())
        r = {"evt": evt, "close": e["close"], "legs": e["legs"], "coin_of": {v: k for k, v in e["legs"].items()},
             "linear": {tk: (e["grid"].get(tk) in (None, "linear_cent")) for tk in tks}, "prog": {},
             "prog_ok": False, "prog_t": -1e18, "placed": {}, "done": set(), "seen": set(), "fresh_t": {},
             "snaps": {}, "counted": False, "summary": False, "swept": False, "sweep_t": -1e18}
        self.races[evt] = r
        self.load_programs(r, t)
        self.books.subscribe(tks)
        self.log.write("race", evt=evt, close=utc_iso(e["close"]), legs=e["legs"], grid=e["grid"], exit_s=self.exit_s,
                       programs={r["coin_of"][tk]: {k: v for k, v in p.items() if k != "id"}
                                 for tk, p in r["prog"].items()},
                       programs_read=r["prog_ok"], missing=[r["coin_of"][tk] for tk in tks if tk not in r["prog"]])
        for coin in (self.state.get("legs") or {}).get(evt) or []:      # N7: ordered before a restart
            tk = e["legs"].get(coin)
            if tk:
                r["done"].add(tk)
                self._once(r, tk, "already_ordered", left=round(e["close"] - t, 1), note="state file (restart)")

    # ---------------- per-step logic ----------------
    def _once(self, r, tk, why, **kw):
        k = (tk, why)
        if k in r["seen"]:
            return
        r["seen"].add(k)
        self.log.write("decide", evt=r["evt"], coin=r["coin_of"][tk], why=why, **kw)

    def book(self, tk, t):
        lv = self.books.levels(tk)
        if lv is not None:
            return lv, "ws"
        c = self.rest_seen.get(tk)
        if c is not None and t - c[0] < REST_BOOK_EVERY_S:
            return c[1], "rest"
        st, ob = self._call("GET", "/markets/%s/orderbook" % tk)     # refused (-2) inside a quiet zone
        lv = levels_from_rest(ob) if st == 200 else None
        if lv is not None:
            self.rest_seen[tk] = (t, lv)
        return lv, ("rest" if st != -2 else "quiet")

    def cancel_due(self, t):
        """FIRST thing every step, in its own try (EXIT / N1 / N5). From close-exit_s every order of ours is cancelled
        (on the stop path, at once). A cancel Kalshi has not confirmed is re-sent -- every 0.5 s before the close,
        every 5 s after -- for as long as it takes; never assumed gone, never marked expired. At the exit the
        subaccount is also swept by client-id prefix (the net under a lost order id)."""
        for o in list(self.resting()):
            if o["status"] in ("resting", "unknown") and not o.get("cancel_why"):
                if self.stopping:
                    self.cancel(o, self.stopping, t)
                elif t >= o["close"] - self.exit_s:
                    self.cancel(o, "exit", t)
                continue
            gap = CANCEL_RETRY_S if t < o["close"] else CANCEL_RETRY_CLOSED_S
            if t - (o.get("cancel_try_t") or -1e18) >= gap:
                if o["status"] == "cancelling":
                    o["status"] = "cancel_failed"
                self.cancel(o, o.get("cancel_why") or "retry", t)
        for r in list(self.races.values()):
            if self.dry or r["swept"] or not (self.exit_t(r) <= t < r["close"]) or not r["placed"]:
                continue
            if t - r["sweep_t"] >= 1.0:
                r["sweep_t"] = t
                r["swept"] = self.sweep(t, "exit", set(r["legs"].values()))

    def race_step(self, r, t):
        left = r["close"] - t
        if left > WINDOW_S or t >= r["close"]:
            return
        ex = self.exit_t(r)
        quiet = self.quiet(t)
        for coin, tk in r["legs"].items():
            oid = r["placed"].get(tk)
            if oid is not None:
                o = self.orders[oid]
                if o["status"] in ("resting", "unknown") and not o.get("cancel_why") and t < ex:
                    got, src = self.book(tk, t)
                    if got is not None:
                        yo = others_of(got[0], 0 if self.dry else max(0.0, o["count"] - o["filled"]))
                        if (best(yo) or 0) > ALIVE_YES + 1e-9:
                            self.log.write("alive", evt=r["evt"], coin=coin, left=round(left, 1), src=src,
                                           **book_numbers(yo, got[1]))
                            self.cancel(o, "alive", t)
                continue
            if t >= ex or quiet or tk in r["done"]:       # EXIT: no new order from close-exit_s
                continue
            if tk not in r["prog"]:
                self._once(r, tk, "no_program", left=round(left, 1), programs_read=r["prog_ok"])
                continue
            got, src = self.book(tk, t)
            if got is None:
                self._once(r, tk, "book_unreadable", left=round(left, 1))
                continue
            prog = r["prog"][tk]
            lin = r["linear"].get(tk, True)
            why = leg_refusal(got[0], got[1], prog["target"], lin)
            nums = book_numbers(got[0], got[1])
            if why:
                self._once(r, tk, why, left=round(left, 1), src=src, **nums)
                continue
            count = self.count_for(prog)
            ok, proj, sh = self.floor_check(r, tk, got[0], got[1], prog, count, t)
            if not ok:                                    # N3: it could never reach the $1 floor before the exit
                self._once(r, tk, "under_floor", left=round(left, 1), projected=round(proj, 4), share=sh, src=src,
                           **nums)
                continue
            if t - r["fresh_t"].get(tk, -1e18) < FRESH_RETRY_S:
                continue
            r["fresh_t"][tk] = t
            # LAST LOOK over REST: the crossing guard, the NO side and the floor re-checked on the exchange's own reply
            st, ob = self._call("GET", "/markets/%s/orderbook" % tk)
            fr = levels_from_rest(ob) if st == 200 else None
            if fr is None:
                self._once(r, tk, "fresh_unreadable", left=round(left, 1), status=st)
                continue
            tn = self.now()
            fwhy = leg_refusal(fr[0], fr[1], prog["target"], lin)
            if not fwhy:
                ok, proj, sh = self.floor_check(r, tk, fr[0], fr[1], prog, count, tn)
                if not ok:
                    fwhy = "under_floor"
            if fwhy:
                self.log.write("fresh_refused", evt=r["evt"], coin=coin, why=fwhy, left=round(r["close"] - tn, 1),
                               ws=nums, rest=book_numbers(fr[0], fr[1]))
                continue
            nums = dict(book_numbers(fr[0], fr[1]), src="rest_last_look", ws_by=nums["by"], ws_bn=nums["bn"],
                        projected=round(proj, 4), share=sh)
            self.place(r, tk, prog, nums, tn)

    def snapshots(self, t):
        """Once a second per leg with an order on the book (or would-be order in the dry run): score the second."""
        slot = int(t)
        if slot == self.last_slot:
            return
        self.last_slot = slot
        for r in self.races.values():
            for tk, oid in r["placed"].items():
                o = self.orders[oid]
                if o["status"] not in ON_BOOK or t >= r["close"]:
                    continue
                prog = r["prog"].get(tk)
                if prog is None:
                    continue
                got, src = self.book(tk, t)
                s = r["snaps"].setdefault(tk, {"slots": 0, "ok": 0, "share_s": 0.0, "first": slot, "last": slot,
                                               "alone": 0, "n99": 0.0, "cross99": 0.0})
                s["last"] = slot
                if got is None:
                    continue
                ours = max(0.0, o["count"] - o["filled"])
                yo = others_of(got[0], 0 if self.dry else ours)
                sn = snapshot(yo, got[1], ours, prog, r["linear"].get(tk, True))
                # A NO bid resting at 99c can only exist while nobody else bids YES at 1c, so with our bid really there
                # it would have traded INTO it: new 99c NO size is would-be fill volume (dry run's upper bound).
                n99 = round(sum(v for p_, v in got[1].items() if p_ >= 0.99 - 1e-9), 2)
                s["cross99"] += max(0.0, n99 - s["n99"])
                s["n99"] = n99
                sn["bn"], sn["n99"] = best(got[1]), n99
                s["slots"] += 1
                if sn["ok"]:
                    s["ok"] += 1
                    s["share_s"] += sn["sh"]
                    if sn["sh"] >= 0.999:
                        s["alone"] += 1
                self.log.write("snap", evt=r["evt"], c=o["coin"], left=round(r["close"] - t, 1), src=src,
                               ours=ours, **sn)

    def summarize(self, r, t, stopped=None):
        legs, tot, tot_floor, fills_n, fills_cost = {}, 0.0, 0.0, 0.0, 0.0
        for tk, oid in r["placed"].items():
            o = self.orders[oid]
            prog = r["prog"].get(tk)
            if prog is None:
                continue
            period = period_of(prog)
            s = r["snaps"].get(tk) or {"slots": 0, "ok": 0, "share_s": 0.0, "alone": 0}
            exp = credit(prog["reward"], period, s["share_s"])
            off = o.get("cancel_t") or o.get("cancel_sent_t") or r["close"]
            on_s = max(0.0, off - o["placed_t"])
            hyp = None
            if self.dry:
                sold = self.books.sells_1c(tk, int(o["placed_t"] * 1000))
                if sold is not None:
                    sold_on = self.books.sells_1c(tk, int(off * 1000))
                    sold_in = sold - (sold_on or 0.0)
                    c99 = (r["snaps"].get(tk) or {}).get("cross99", 0.0)
                    hyp = {"sold_into_1c": round(sold_in, 2), "queue_ahead": o["queue_ahead"],
                           "no_99c_would_cross": round(c99, 2),
                           "would_fill_low": round(min(o["count"], max(0.0, sold_in - o["queue_ahead"])), 2),
                           "would_fill_high": round(min(o["count"], sold_in + c99), 2)}
            legs[o["coin"]] = {"placed_left": round(r["close"] - o["placed_t"], 1), "cancel": o["cancel_why"],
                               "cancel_sent_left": (round(r["close"] - o["cancel_sent_t"], 2)
                                                    if o.get("cancel_sent_t") else None),
                               "status": o["status"], "on_book_s": round(on_s, 1), "snaps": s["slots"],
                               "counted_s": s["ok"], "alone_s": s["alone"], "share_s": round(s["share_s"], 3),
                               "reward": prog["reward"], "period_s": period, "expected": round(exp, 4),
                               "expected_floored": round(floored(exp), 4), "filled": o["filled"],
                               "cost": round(o["cost"] + o["fees"], 4), "would_fill": hyp}
            tot += exp
            tot_floor += floored(exp)
            fills_n += o["filled"]
            fills_cost += o["cost"] + o["fees"]
        self._day(r["close"])["credit_exp"] += tot_floor
        self.save()
        self.log.write("race_summary", evt=r["evt"], close=utc_iso(r["close"]), mode="dry" if self.dry else "live",
                       exit_s=self.exit_s, stopped=stopped, legs=legs, expected_credit=round(tot, 4),
                       expected_credit_floored=round(tot_floor, 4), fills=fills_n, fills_cost=round(fills_cost, 4),
                       races_with_order=len(self.state["races"]),
                       unconfirmed=[o["coin"] for o in self.resting() if o["evt"] == r["evt"]],
                       refusals=sorted("%s:%s" % (r["coin_of"][tk], w) for tk, w in r["seen"]))
        r["summary"] = True

    def stop_summaries(self, t):
        """N10: a stop in mid-race still writes that race's summary (its expected credit is in the report)."""
        for r in list(self.races.values()):
            if r["placed"] and not r["summary"]:
                try:
                    self.summarize(r, t, stopped=self.stopping or "exit")
                except Exception as e:
                    self.log.write("summary_error", evt=r["evt"], err=repr(e)[:300])

    def cancel_all(self, why, t=None):
        t = self.now() if t is None else t
        self.stopping = self.stopping or why
        self.cancel_due(t)                 # every resting order cancelled at once; failures re-sent, spaced
        if not self.dry and t - self.last_stop_sweep >= 1.0:
            self.last_stop_sweep = t
            self.sweep(t, why)

    def _stop_step(self, t):
        try:
            self.cancel_all(self.stopping, t)
        except Exception as e:
            self.log.write("cancel_all_error", err=repr(e)[:300])
        if not self.resting():
            if not self.dry:
                try:
                    self.poll_orders(self.now())
                except Exception:
                    pass
            self.stop_summaries(self.now())
            self.exit_ready = True
        elif not self.dry and t - self.last_poll >= POLL_FILLS_S:
            self.last_poll = t
            try:
                self.poll_orders(t)
            except Exception as e:
                self.log.write("poll_error", err=repr(e)[:300])

    def wind_down(self, why, budget_s=15.0):
        """The exit path (KeyboardInterrupt, --minutes, an error): keep cancelling and confirming for up to budget_s,
        then write the summaries of any race still open."""
        self.stopping = self.stopping or why
        t0 = self.now()
        while not self.exit_ready and self.now() - t0 < budget_s:
            self.step()
            if not self.exit_ready:
                self.sleep(0.25)
        if not self.exit_ready:
            self.stop_summaries(self.now())
            self.log.write("wind_down_incomplete", still_on_book=[(o["coin"], o["kid"], o["status"])
                                                                  for o in self.resting()])

    def step(self):
        t = self.now()
        if not self.stopping and os.path.exists(self.stop_path):
            self.stopping = "stop_file"
            self.log.write("stop_file", path=self.stop_path)
        try:
            self.cancel_due(t)
        except Exception as e:
            self.log.write("deadline_error", err=repr(e)[:300])
        if self.stopping:
            self._stop_step(t)
            return
        if not self.quiet(self.now()) and t - self.last_discover >= DISCOVER_EVERY_S:
            self.last_discover = t
            try:
                for evt, e in self.discover(t).items():
                    if evt not in self.races and e["close"] - t <= PREP_S and e["close"] - t > self.exit_s + QUIET_S:
                        if len(self.state["races"]) < self.races_max:
                            self.prepare(evt, e, t)
            except Exception as ex:
                self.log.write("discover_error", err=repr(ex)[:300])
        for r in list(self.races.values()):
            if not r["prog_ok"] and t - r["prog_t"] >= PROGRAM_RETRY_S and t < self.exit_t(r) - 60.0 \
                    and not self.quiet(self.now()):
                try:
                    if self.load_programs(r, t):
                        self.log.write("programs_read", evt=r["evt"], coins=sorted(r["coin_of"][k] for k in r["prog"]))
                except Exception as e:
                    self.log.write("program_error", evt=r["evt"], err=repr(e)[:300])
        for r in list(self.races.values()):
            try:
                self.race_step(r, t)
            except Exception as e:
                self.log.write("race_error", evt=r["evt"], err=repr(e)[:300])
        try:
            self.snapshots(t)
        except Exception as e:
            self.log.write("snap_error", err=repr(e)[:300])
        if not self.dry and t - self.last_poll >= POLL_FILLS_S \
                and (not self.quiet(self.now()) or self.needs_confirm()):
            self.last_poll = t
            try:
                self.poll_orders(t)
            except Exception as e:
                self.log.write("poll_error", err=repr(e)[:300])
        if not self.quiet(self.now()):
            try:
                self.settle(t)
            except Exception as e:
                self.log.write("settle_error", err=repr(e)[:300])
        for evt, r in list(self.races.items()):
            if not r["summary"] and t >= r["close"] + 5:
                if r["placed"]:
                    pending = [o for o in self.resting() if o["evt"] == evt]
                    if not pending or t >= r["close"] + SUMMARY_WAIT_S:
                        if not self.dry:
                            try:
                                self.poll_orders(t)
                            except Exception:
                                pass
                        self.summarize(r, t)
                else:
                    r["summary"] = True
                    self.log.write("race_summary", evt=evt, close=utc_iso(r["close"]), placed=0,
                                   refusals=sorted("%s:%s" % (r["coin_of"][tk], w) for tk, w in r["seen"]))
            if r["summary"] and t >= r["close"] + 120:
                try:
                    self.books.drop(list(r["legs"].values()))
                except Exception:
                    pass
                if all(o.get("settled") or o["filled"] <= 0 for o in self.orders.values() if o["evt"] == evt):
                    del self.races[evt]
        if len(self.state["races"]) >= self.races_max and not self.races and not self.resting():
            pend = [o for o in self.orders.values() if o["filled"] > 0 and not o.get("settled")]
            if not pend:
                self.stopping = "races_done"
                self.log.write("races_done", races=len(self.state["races"]), races_max=self.races_max)


# ------------------------------------------------------------------------------------------------ report (GET only)
def _pages(sender, path, key, q0, maxpages=100):
    out, cur = [], None
    for _ in range(maxpages):
        q = dict(q0)
        q.setdefault("limit", 200)
        if cur:
            q["cursor"] = cur
        st, d = sender("GET", path, None, q)
        if st != 200 or not isinstance(d, dict):
            return out, False
        got = d.get(key) or []
        out += got
        cur = d.get("cursor") or d.get("next_cursor")
        if not got or not cur:
            return out, True
    return out, False


def report(sender, sub, out=print, live_log=LIVE_LOG, report_log=REPORT_LOG, now=None):
    """leftover = cash (pools 0-3) + cost of open positions - net transfers in - settled P&L. A Kalshi reward has no
    API line item; it shows up ONLY as leftover cash. Every reading is appended to results/racereward-report.jsonl and
    the readings are printed one per ET day NEXT TO the sum of that day's live races' expected_credit_floored, so a
    credit 16-48 h after a race appears as a step between days. Then the N8 bar and its verdict."""
    import pinledger
    if int(sub) < 1:
        out("REFUSED: --report needs a subaccount 1..63")
        return 2
    t = time.time() if now is None else float(now)
    cash, pools = 0.0, {}
    for pool in (0, 1, 2, 3):
        v = read_balance(sender, sub, pool)
        if v is None:
            out("FAILED: subaccount %d pool %d balance unreadable; no leftover computed" % (sub, pool))
            return 1
        pools[pool] = v
        cash += v
    pos, ok1 = _pages(sender, "/portfolio/positions", "market_positions",
                      {"subaccount": sub, "count_filter": "position", "settlement_status": "unsettled"})
    rest, ok2 = _pages(sender, "/portfolio/orders", "orders", {"subaccount": sub, "status": "resting"})
    xf, ok3 = _pages(sender, "/portfolio/subaccounts/transfers", "transfers", {"limit": 100})
    st_rows, ok4 = _pages(sender, "/portfolio/settlements", "settlements", {"subaccount": sub})
    if not (ok1 and ok2 and ok3 and ok4):
        out("FAILED: a listing was unreadable (positions %s orders %s transfers %s settlements %s)" % (ok1, ok2, ok3, ok4))
        return 1
    held = sum(abs(f(x.get("market_exposure_dollars"), 0.0)) for x in pos)
    resv = 0.0
    for o in rest:
        p = f(o.get("yes_price_dollars"), None) if o.get("side") in ("yes", "bid") else f(o.get("no_price_dollars"))
        resv += (p or 0.0) * f(o.get("remaining_count_fp"), 0.0)
    by_day = {}
    net_in = 0.0
    for x in xf:
        a = f(x.get("amount_cents"), 0.0) / 100.0
        d = et_day(f(x.get("created_ts"), t))
        if int(x.get("to_subaccount", -1)) == int(sub):
            net_in += a
            by_day.setdefault(d, {"xfer": 0.0, "pnl": 0.0, "n": 0})["xfer"] += a
        if int(x.get("from_subaccount", -1)) == int(sub):
            net_in -= a
            by_day.setdefault(d, {"xfer": 0.0, "pnl": 0.0, "n": 0})["xfer"] -= a
    pnl = 0.0
    for s in st_rows:
        v = pinledger.pnl(s)
        pnl += v
        d = et_day(parse_ts(s.get("settled_time")) or t)
        e = by_day.setdefault(d, {"xfer": 0.0, "pnl": 0.0, "n": 0})
        e["pnl"] += v
        e["n"] += 1
    left = cash + held - net_in - pnl
    rec = {"t": utc_iso(t), "et_day": et_day(t), "sub": sub, "cash": round(cash, 4), "pools": pools,
           "held": round(held, 4), "resting_reserve": round(resv, 4), "net_transfers_in": round(net_in, 4),
           "settled_pnl": round(pnl, 4), "settled_n": len(st_rows), "leftover": round(left, 4)}
    try:
        with open(report_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    races = {}                                         # evt -> the last live race_summary (a re-summary replaces it)
    try:
        with open(live_log, encoding="utf-8") as fh:
            for line in fh:
                if '"race_summary"' not in line:
                    continue
                r = json.loads(line)
                if r.get("mode") == "live" and parse_ts(r.get("close")) is not None:
                    races[r.get("evt")] = r
    except (OSError, ValueError):
        pass
    race_day = {}
    for r in races.values():
        e = race_day.setdefault(et_day(parse_ts(r["close"])), {"n": 0, "exp": 0.0, "fills": 0.0})
        e["n"] += 1
        e["exp"] += float(r.get("expected_credit_floored") or 0.0)
        e["fills"] += float(r.get("fills_cost") or 0.0)
    readings = {}
    try:
        with open(report_log, encoding="utf-8") as fh:
            for line in fh:
                x = json.loads(line)
                if int(x.get("sub", -1)) == int(sub):
                    readings[x["et_day"]] = x          # the last reading of each ET day
    except (OSError, ValueError):
        readings[rec["et_day"]] = rec
    out("subaccount %d at %s: cash $%.4f (pools %s) + open positions $%.4f - net transfers in $%.4f - settled P&L "
        "$%.4f (%d markets) = LEFTOVER $%.4f   [resting orders reserve $%.4f; balance is gross of it]"
        % (sub, rec["t"], cash, {k: round(v, 4) for k, v in pools.items()}, held, net_in, pnl, len(st_rows), left, resv))
    out("ET day      leftover(last reading)   change  settled P&L  transfers  markets  races  "
        "SUM expected_credit_floored  fill cost")
    prev = None
    for d in sorted(set(readings) | set(by_day) | set(race_day)):
        x = readings.get(d)
        lv = x["leftover"] if x else None
        ch = (lv - prev) if (lv is not None and prev is not None) else None
        b = by_day.get(d, {"xfer": 0.0, "pnl": 0.0, "n": 0})
        rd = race_day.get(d)
        out("%s  %22s  %7s  %11.4f  %9.2f  %7d  %5s  %27s  %9s" % (
            d, "" if lv is None else "$%.4f" % lv, "" if ch is None else "%+.4f" % ch, b["pnl"], b["xfer"], b["n"],
            "" if rd is None else "%d" % rd["n"], "" if rd is None else "$%.2f" % rd["exp"],
            "" if rd is None else "$%.2f" % rd["fills"]))
        if lv is not None:
            prev = lv
    out("A credit is any leftover above ~$0.00 that nothing else explains. Interest (3.5%/yr, paid monthly) is the "
        "only known other source. A credit paid to the PRIMARY account instead would not show here (results "
        "recon: main leftover was +$1.46 lifetime on 10-10).")
    # ---- the N8 bar ----
    exp_total = sum(e["exp"] for e in race_day.values())
    fills_log = sum(e["fills"] for e in race_day.values())
    net_loss = max(0.0, -pnl)
    fill_cost = max(fills_log, net_loss)
    out("BAR (N8, 2026-10-10): read %.0f h after the last live race. PASS = leftover >= 50%% of the SUM of "
        "expected_credit_floored AND fill cost <= 50%% of it. FAIL = leftover < $1.00." % BAR_WAIT_H)
    if not races:
        out("  VERDICT: NO_RACES -- no live race_summary in %s" % live_log)
        return 0
    last_close = max(parse_ts(r["close"]) for r in races.values())
    due = last_close + BAR_WAIT_H * 3600.0
    half = 0.5 * exp_total
    out("  %d live races; the last closed %s; the bar is read at or after %s" % (len(races), utc_iso(last_close),
                                                                                 utc_iso(due)))
    out("  SUM expected_credit_floored $%.2f -> PASS needs leftover >= $%.2f and fill cost <= $%.2f" % (exp_total, half,
                                                                                                        half))
    out("  leftover now $%.4f; fill cost $%.2f (the larger of the race log's $%.2f and Kalshi's settled loss $%.2f)"
        % (left, fill_cost, fills_log, net_loss))
    if t < due:
        out("  VERDICT: TOO_EARLY -- %.1f h to go; a credit lands 16-48 h after a race" % ((due - t) / 3600.0))
    elif left < 1.0 - 1e-9:
        out("  VERDICT: FAIL -- leftover $%.2f < $1.00 %.0f h after the last race: Kalshi has not paid this account"
            % (left, BAR_WAIT_H))
    elif exp_total > 0 and left >= half - 1e-9 and fill_cost <= half + 1e-9:
        out("  VERDICT: PASS -- leftover $%.2f >= $%.2f and fill cost $%.2f <= $%.2f" % (left, half, fill_cost, half))
    else:
        out("  VERDICT: NEITHER -- leftover $%.2f (>= $1) but %s" % (
            left, "under half the expected credit" if left < half - 1e-9 else
            "fill cost $%.2f is over half the expected credit" % fill_cost))
    return 0


# ------------------------------------------------------------------------------------------------ self-test
class _FakeX:
    """A fake exchange: orders, books, programs, balance. Records every call as
    (method, path, body, query, SEND time on the fake clock, timeout)."""

    def __init__(self, clock, close):
        self.clock, self.close = clock, close
        self.books = {}            # tk -> (yes {px: n}, no {px: n})
        self.orders = {}
        self.calls = []
        self.results = {}
        self.raise_delete = 0
        self.fail_delete = 0
        self.lose_post = 0         # the order IS created, the reply is lost
        self.drop_post = 0         # the request is lost: no order
        self.programs_ok = True
        self.reward_cc = 200000
        self.no_prog = {"HYPE"}
        self.hang = None           # (t_from, t_to, seconds, methods): those calls take `seconds` (or time out)
        self.fail_delete_win = None
        self.fail_list_win = None
        self.del404 = {}           # order id -> how many DELETEs answer 404 while it still rests
        self.bal = {"balance": 5000, "balance_dollars": "50.0000"}
        self.evt = "KXCRYPTOLEAD15M-26OCT100430"
        self.tks = {c: "%s-%s" % (self.evt, c) for c in COINS}

    def __call__(self, method, path, body, query, timeout=None):
        t0 = self.clock[0]
        to = DEFAULT_TIMEOUT_S if timeout is None else float(timeout)
        self.calls.append((method, path, body, dict(query or {}), t0, to))
        if self.hang and self.hang[0] <= t0 < self.hang[1] and method in self.hang[3]:
            if self.hang[2] > to:
                self.clock[0] += to
                return -1, "timed out after %.1f s" % to
            self.clock[0] += self.hang[2]
        if method == "POST":
            if self.drop_post:
                self.drop_post -= 1
                return -1, "timed out"
            oid = "K%d" % (len(self.orders) + 1)
            self.orders[oid] = {"order_id": oid, "client_order_id": body["client_order_id"], "ticker": body["ticker"],
                                "status": "resting", "fill_count_fp": "0.00", "remaining_count_fp": body["count"]}
            if self.lose_post:
                self.lose_post -= 1
                return -1, "timed out"
            return 201, {"order": {"order_id": oid, "fill_count_fp": "0.00"}}
        if method == "DELETE":
            if self.raise_delete:
                self.raise_delete -= 1
                raise ConnectionError("socket died mid-cancel")
            if self.fail_delete:
                self.fail_delete -= 1
                return 500, "internal"
            if self.fail_delete_win and self.fail_delete_win[0] <= t0 < self.fail_delete_win[1]:
                return 500, "internal"
            kid = path.rsplit("/", 1)[1]
            if self.del404.get(kid):
                self.del404[kid] -= 1
                return 404, "not_found"
            o = self.orders.get(kid)
            if not o or o["status"] != "resting":
                return 404, "not_found"
            o["status"], o["canceled_t"] = "canceled", self.clock[0]
            return 200, {"order_id": kid, "reduced_by": o["remaining_count_fp"], "ts_ms": int(t0 * 1000)}
        if path == "/portfolio/orders":
            if self.fail_list_win and self.fail_list_win[0] <= t0 < self.fail_list_win[1]:
                return 503, "down"
            rows = [dict(o) for o in self.orders.values()
                    if (query or {}).get("status") in (None, o["status"])]
            return 200, {"orders": rows}
        if path == "/portfolio/balance":
            return 200, dict(self.bal)
        if path == "/incentive_programs":
            if not self.programs_ok:
                return 503, "down"
            return 200, {"incentive_programs": [
                {"market_ticker": tk, "period_reward": self.reward_cc, "target_size_fp": "1000.00",
                 "discount_factor_bps": 5000, "start_date": utc_iso(self.close - 900).replace(".000000", ""),
                 "end_date": utc_iso(self.close).replace(".000000", ""), "id": "p-" + c}
                for c, tk in self.tks.items() if c not in self.no_prog] + [
                {"market_ticker": "KXOTHER-X", "period_reward": 1000000, "target_size_fp": "300.00",
                 "discount_factor_bps": 5000}], "cursor": ""}
        if path == "/markets":
            return 200, {"markets": [{"ticker": tk, "custom_strike": {"Cryptocurrency": c},
                                      "close_time": datetime.fromtimestamp(self.close, timezone.utc)
                                      .strftime("%Y-%m-%dT%H:%M:%SZ"), "price_level_structure": "linear_cent"}
                                     for c, tk in self.tks.items()]}
        if path.startswith("/markets/") and path.endswith("/orderbook"):
            tk = path.split("/")[2]
            y, n = self.books.get(tk, ({}, {}))
            return 200, {"orderbook_fp": {"yes_dollars": [["%.4f" % p, "%.2f" % s] for p, s in sorted(y.items())],
                                          "no_dollars": [["%.4f" % p, "%.2f" % s] for p, s in sorted(n.items())]}}
        if path.startswith("/markets/"):
            return 200, {"market": {"result": self.results.get(path.split("/")[2], "")}}
        return 404, "?"

    def writes(self, m=None):
        return [c for c in self.calls if c[0] in ((m,) if m else ("POST", "DELETE"))]


class _FakeBooks:
    """The bot's book provider, reading the fake exchange's books (what the socket would show). down=True: no socket."""

    def __init__(self, x, raise_on=None, down=False):
        self.x, self.raise_on, self.down = x, raise_on, down
        self.subs = set()
        self.sold = {}

    def levels(self, tk):
        if self.raise_on and tk in self.raise_on:
            raise RuntimeError("book provider exploded")
        if self.down:
            return None
        y, n = self.x.books.get(tk, ({}, {}))
        return dict(y), dict(n)

    def subscribe(self, tks):
        self.subs |= set(tks)

    def drop(self, tks):
        pass

    def sells_1c(self, tk, since_ms):
        return sum(n for ts, n in self.sold.get(tk, []) if ts >= since_ms)

    def connected(self):
        return not self.down


def selftest(verbose=False):
    fails, notes = [], []

    def ck(ok, m):
        (notes if ok else fails).append(m)

    def _rm(path):
        if os.path.exists(path):
            os.remove(path)

    # ---- 1. the filing's walk, against hand arithmetic ----
    P = {"reward": 20.0, "target": 1000.0, "df": 0.5, "start": None, "end": None}
    a = snapshot({}, {0.95: 600, 0.94: 600}, 1000, P)
    ck(a["ok"] and abs(a["sh"] - 1.0) < 1e-12, "alone at 1c with NO 1,200 deep: counted, share 1.0 (%s)" % a)
    b = snapshot({0.02: 300}, {0.95: 1200}, 1000, P)
    ck(b["ok"] and abs(b["sh"] - 500.0 / 800.0) < 1e-9 and b["yref"] == 0.02,
       "others 300 @2c: ref 2c, ours 1000 x 0.5 = 500 of 800 -> 0.625 (%s)" % b)
    c = snapshot({0.01: 5440}, {0.95: 1200}, 1000, P)
    ck(c["ok"] and abs(c["sh"] - 1000.0 / 6440.0) < 1e-5, "5,440 others at 1c: share 1000/6440 = 15.5% (the 10-09 XRP leg)")
    d = snapshot({}, {0.95: 800}, 1000, P)
    ck(not d["ok"] and d["sh"] == 0.0, "NO side 800 < target: second excluded, pays nobody")
    e = snapshot({}, {0.99: 5000}, 1000, P)
    ck(not e["ok"], "best NO bid 99c (the highest possible price): NO side has no qualifying bids -> excluded")
    g = snapshot({0.03: 1200}, {0.95: 1200}, 1000, P)
    ck(g["ok"] and g["sh"] == 0.0, "others fill the target above 1c: our 1c bid is past the cutoff -> share 0")
    h = walk({0.05: 150, 0.04: 100}, 1000, 0.5, ours=1000)
    ck(h["q"] and h["ref"] == 0.04 and abs(h["share"] - (1000 * 0.5 ** 3) / (150 + 100 + 125)) < 1e-9,
       "ref = first level reaching target/5 (4c); above-ref full credit, ours 3 ticks below x 0.125")
    ck(abs(credit(20.0, 900, 360) - 4.0) < 1e-9 and abs(credit(20.0, 900, 80) - 0.8889) < 1e-4
       and floored(credit(20.0, 900, 80)) == 0.0 and floored(4.0) == 4.0,
       "credit: 360 s alone = $4.00 ($20 x 360 / 1800); 80 s = $0.89 -> $0 under the $1 floor")
    ck(others_of({0.01: 1500, 0.02: 5}, 1000) == {0.01: 500, 0.02: 5} and others_of({0.01: 900}, 1000) == {},
       "live: our own resting size is taken out of the 1c level before the walk")

    # ---- 2. leg selection (incl. N4) ----
    ck(leg_refusal({}, {0.97: 2000}, 1000) is None, "empty YES side, NO 97c x 2,000: a dead leg qualifies")
    ck(leg_refusal({0.03: 10}, {0.97: 2000}, 1000) is None, "best YES 3c qualifies (<= 3c)")
    ck(leg_refusal({0.04: 10}, {0.95: 2000}, 1000) == "not_dead", "best YES 4c is not dead")
    ck(leg_refusal({0.95: 500}, {0.04: 500}, 1000) == "not_dead", "the leader leg is refused")
    ck(leg_refusal({0.01: 1000}, {0.97: 2000}, 1000) == "yes_side_full", "YES side already at the target: refused")
    ck(leg_refusal({0.01: 999}, {0.97: 2000}, 1000) is None, "YES side 999 < 1000 qualifies")
    ck(leg_refusal({}, {0.99: 50, 0.97: 2000}, 1000) == "would_cross", "best NO bid 99c: a 1c YES bid would cross")
    ck(leg_refusal({}, {0.985: 50, 0.97: 2000}, 1000) == "would_cross", "best NO bid 98.5c also refused (> 98c)")
    ck(leg_refusal({}, {0.98: 1500}, 1000) is None, "best NO bid exactly 98c (NO side 1,500 deep) is allowed")
    ck(leg_refusal({}, {0.97: 999}, 1000) == "no_side_short"
       and leg_refusal({}, {0.97: 600, 0.90: 399}, 1000) == "no_side_short"
       and leg_refusal({}, {0.97: 600, 0.90: 400}, 1000) is None,
       "N4: a NO side under the 1,000 target (999; 600+399) is refused -- its seconds cannot count; 600+400 qualifies")

    # ---- 3. order bodies ----
    bd = order_body(SERIES + "-X-BTC", 1000, 4, CID_PREFIX + "1")
    ck(bd["price"] == "0.0100" and bd["side"] == "bid" and bd["count"] == "1000.00" and body_ok(bd, 4),
       "the body: buy 1,000 YES at 0.0100, post_only, maker STP, GTC, pool 2, subaccount 4")
    for bad, m in ((dict(bd, subaccount=0), "subaccount 0"), (dict(bd, price="0.0200"), "price 0.02"),
                   (dict(bd, price="0.01"), "price spelled 0.01 (not the canonical 0.0100)"),
                   (dict(bd, count="1001.00"), "count 1,001"), (dict(bd, count="0.00"), "count 0"),
                   (dict(bd, post_only=False), "post_only False"), (dict(bd, exchange_index=0), "pool 0"),
                   (dict(bd, self_trade_prevention_type="taker_at_cross"), "STP taker_at_cross"),
                   (dict(bd, side="ask"), "side ask (= buy NO)"), (dict(bd, ticker="KXBTC15M-X"), "another series"),
                   (dict(bd, client_order_id="pin-1"), "a foreign client_order_id"),
                   (dict(bd, time_in_force="immediate_or_cancel"), "IOC")):
        ck(not body_ok(bad, bad.get("subaccount", 4)), "body_ok refuses %s" % m)
    ck(not body_ok(order_body(SERIES + "-X-BTC", 1000, 0, CID_PREFIX + "1"), 0), "body_ok refuses the primary account")
    try:
        import importlib
        sys.path.insert(0, os.path.join(RESEARCH, "cleanroom"))
        LL = importlib.import_module("ladder_live")
        lb = LL.order_body(SERIES + "-X-BTC", "yes", "0.01", 4, "lad-1")
        ck(set(lb) == set(bd) and all(lb[k] == bd[k] for k in bd if k not in ("count", "client_order_id")),
           "the body matches ladder_live.order_body key for key (except count and client id)")
    except Exception as ex:
        ck(False, "ladder_live.order_body parity could not be checked: %r" % ex)

    # ---- 4. start refusals ----
    tmpd = os.path.join(RESULTS, ".racereward-selftest")
    os.makedirs(tmpd, exist_ok=True)
    stp = os.path.join(tmpd, "stop")
    spath = os.path.join(tmpd, "state.json")
    for p in (stp, spath):
        _rm(p)
    T0 = 1_791_700_000.0
    st0 = {"races": [], "halted_day": None}
    ck(start_refusal(0, 50, st0, 20, T0, stp) and start_refusal(None, 50, st0, 20, T0, stp),
       "start: subaccount 0 / none refused")
    ck(all(start_refusal(s_, 50, st0, 20, T0, stp) for s_ in (1, 2, 3)),
       "start: subaccounts 1-3 (ladder, forecaster, dip-seller) refused")
    ck(start_refusal(4, 50, st0, 20, T0, stp, None) and start_refusal(4, 50, st0, 20, T0, stp, (0.0, 4.9))
       and start_refusal(4, 50, st0, 20, T0, stp, (-30.0, 0.0))
       and start_refusal(4, 50, st0, 20, T0, stp, (-29.9, 0.0)) is None,
       "start: unreadable Kalshi day / open positions / today's settled -$30 refused; -$29.90 and flat starts")
    ck(start_refusal(4, None, st0, 20, T0, stp), "start: unreadable balance refused")
    ck(start_refusal(4, 44.99, st0, 20, T0, stp) and start_refusal(4, 100.01, st0, 20, T0, stp)
       and start_refusal(4, 45.0, st0, 20, T0, stp) is None and start_refusal(4, 100.0, st0, 20, T0, stp) is None,
       "start: under $45 / over $100 refused, $45 and $100 accepted")
    ck(start_refusal(4, 50, {"races": ["e%d" % i for i in range(20)]}, 20, T0, stp),
       "start: 20 races already done (state) refused")
    ck(start_refusal(4, 50, {"races": [], "halted_day": et_day(T0)}, 20, T0, stp)
       and start_refusal(4, 50, {"races": [], "halted_day": et_day(T0 - 86400)}, 20, T0, stp) is None,
       "start: today's day stop refused; yesterday's is not")
    ck(read_balance(lambda m, p, b, q: (200, {"balance": 5000, "balance_dollars": "50.0000"}), 4) == 50.0
       and read_balance(lambda m, p, b, q: (200, {"balance": 500000, "balance_dollars": "50.0000"}), 4) is None
       and read_balance(lambda m, p, b, q: (200, {"balance_dollars": "50.0000"}), 4) is None
       and read_balance(lambda m, p, b, q: (500, {"balance": 5000, "balance_dollars": "50.0000"}), 4) is None,
       "balance: both fields must be present and agree, and the read must be a 200")
    ck(et_day(datetime(2026, 10, 10, 3, 59, tzinfo=timezone.utc).timestamp()) == "2026-10-09"
       and et_day(datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc).timestamp()) == "2026-10-10"
       and et_day(datetime(2026, 12, 10, 4, 30, tzinfo=timezone.utc).timestamp()) == "2026-12-09",
       "ET day: EDT midnight is 04:00Z in October, EST midnight 05:00Z in December")

    # ---- 5. worlds on a fake exchange (close = T0+420; exit = close-60 = T0+360; window opens close-360) ----
    def world(dry=False, books_raise=None, down=False, progs_all=False, reward_cc=200000, exit_s=EXIT_S_DEFAULT,
              day_realized=None, keep_state=False):
        if not keep_state:
            _rm(spath)
        clock = [T0]
        close = T0 + 420.0
        x = _FakeX(clock, close)
        x.reward_cc = reward_cc
        if progs_all:
            x.no_prog = set()
        tk = x.tks
        x.books = {tk["BTC"]: ({0.95: 300}, {0.04: 300}),               # leader: not dead
                   tk["ETH"]: ({}, {0.97: 1500}),                        # dead, empty YES -> place
                   tk["SOL"]: ({0.01: 1200}, {0.98: 2000}),              # YES side already full -> refuse
                   tk["XRP"]: ({0.01: 20}, {0.99: 30, 0.97: 2000}),      # NO bid 99c -> would cross
                   tk["HYPE"]: ({}, {0.97: 2000})}                       # dead, but NO PROGRAM listed -> refuse
        sink = []
        bk = _FakeBooks(x, books_raise, down)
        bot = Bot(Log(sink=sink), 4, dry, x, lambda: clock[0], bk, spath, stp, 20,
                  sleep=lambda s: clock.__setitem__(0, clock[0] + s), exit_s=exit_s)
        if day_realized is not None:
            bot.state["days"][et_day(T0)] = {"realized": float(day_realized), "fills_cost": 0.0, "credit_exp": 0.0}
        return clock, close, x, bot, sink, bk

    def run(clock, bot, until, dt=0.25):
        while clock[0] < until and not bot.exit_ready:
            bot.step()
            clock[0] += dt

    def dels(x, kid=None):
        return [c for c in x.calls if c[0] == "DELETE" and (kid is None or c[1].endswith("/" + kid))]

    def decided(sink):
        return {(r.get("coin"), r.get("why")) for r in sink if r["ev"] == "decide"}

    # 5a. the planted race: leg choice, alive cancel, N4, N3, the EXIT cancel by its SEND time
    clock, close, x, bot, sink, bk = world()
    tk = x.tks
    ex = close - EXIT_S_DEFAULT
    run(clock, bot, close - 300)
    posts = x.writes("POST")
    ck(len(posts) == 1 and posts[0][2]["ticker"] == tk["ETH"] and body_ok(posts[0][2], 4),
       "planted race: exactly one order, on the dead ETH leg (%s)" % [p[2]["ticker"][-4:] for p in posts])
    why = decided(sink)
    ck(("BTC", "not_dead") in why and ("SOL", "yes_side_full") in why and ("XRP", "would_cross") in why
       and ("HYPE", "no_program") in why, "every other leg refused, each for its planted reason (%s)" % sorted(why))
    ck(not any(r["ev"] == "decide" for r in sink if r.get("left", 999) > WINDOW_S), "nothing decided before close-360")
    ck(all(c[2]["price"] == PRICE for c in x.writes("POST")) and all(c[2]["subaccount"] == 4 for c in x.writes("POST")),
       "never a price other than 0.0100, never another subaccount")
    snaps = [r for r in sink if r["ev"] == "snap"]
    ck(len(snaps) >= 55 and all(s["ok"] and s["sh"] == 1.0 for s in snaps),
       "one snapshot a second while resting; alone on a counted side -> share 1.0 (%d snaps)" % len(snaps))
    x.books[tk["ETH"]] = ({0.06: 50}, {0.93: 1500})
    t_alive = clock[0]
    run(clock, bot, clock[0] + 2)
    d_ = dels(x)
    ck(len(d_) == 1 and d_[0][3] == {"subaccount": 4, "exchange_index": POOL} and 0 <= d_[0][4] - t_alive <= 0.5,
       "alive (best YES 6c > 5c): cancel SENT within 0.5 s, subaccount + pool as query")
    x.books[tk["ETH"]] = ({}, {0.97: 1500})
    run(clock, bot, close - 250)
    ck(len(x.writes("POST")) == 1, "one order per leg per race: the leg dying again is NOT re-placed")
    x.books[tk["BTC"]] = ({}, {0.96: 3000})
    x.books[tk["SOL"]] = ({}, {0.96: 800})
    run(clock, bot, close - 145)
    ck(len(x.writes("POST")) == 2 and x.writes("POST")[-1][2]["ticker"] == tk["BTC"],
       "a leg that dies at close-250 (188 s of credit before the exit, $2.09) is placed")
    ck(("SOL", "no_side_short") in decided(sink) and not any(c[2]["ticker"] == tk["SOL"] for c in x.writes("POST")),
       "N4: a dead leg whose NO side is 800 < 1,000 is refused 'no_side_short'")
    x.books[tk["XRP"]] = ({}, {0.96: 3000})
    run(clock, bot, close - 100)
    ck(("XRP", "under_floor") in decided(sink) and not any(c[2]["ticker"] == tk["XRP"] for c in x.writes("POST")),
       "N3: a leg that dies at close-145 (83 s before the exit = $0.92 alone) is refused 'under_floor'")
    run(clock, bot, close + 30)
    btc = [o for o in bot.orders.values() if o["coin"] == "BTC"][0]
    bdl = dels(x, btc["kid"])
    ck(len(bdl) == 1 and ex <= bdl[0][4] <= ex + 1.0 and btc["cancel_why"] == "exit"
       and x.orders[btc["kid"]]["status"] == "canceled",
       "EXIT: the resting order's cancel is SENT at close-60 s, not before (sent %.2f s before the close)"
       % (close - bdl[0][4] if bdl else -1))
    ck(not any(c[4] >= ex for c in x.writes("POST")), "EXIT: no order sent at or after close-60 s")
    ck(not any(r["ev"] == "exchange_cancelled" for r in sink),
       "N8 null: orders WE cancelled (alive, exit) are never logged as exchange_cancelled")
    summ = [r for r in sink if r["ev"] == "race_summary"]
    ck(len(summ) == 1 and summ[0]["legs"]["BTC"]["expected"] > 0 and summ[0]["races_with_order"] == 1,
       "a race summary with an expected credit")
    if summ:
        b_ = summ[0]["legs"]["BTC"]
        ck(abs(b_["expected"] - credit(20.0, 900.0, b_["share_s"])) < 1e-4 and 186 <= b_["share_s"] <= 192
           and b_["expected_floored"] == b_["expected"],
           "BTC rested ~190 s alone until the exit: expected = $20 x share-seconds / 1800 = $%.2f (over the floor)"
           % b_["expected"])
        e_ = summ[0]["legs"]["ETH"]
        ck(55 <= e_["share_s"] <= 62 and e_["expected_floored"] == 0.0 and e_["cancel"] == "alive",
           "ETH rested ~60 s then came alive: $%.2f, under the $1 floor -> $0" % e_["expected"])
    st_ = load_state(spath)
    ck(st_["races"] == [x.evt] and (st_.get("legs") or {}).get(x.evt) == ["ETH", "BTC"],
       "N7: the race and each coin ordered in it are in the state file (%s)" % (st_.get("legs") or {}).get(x.evt))

    # 5b. EXIT is the exit, not the floor: with $200,000 a window the floor needs 0.01 s, and still nothing after it
    clock, close, x, bot, sink, bk = world(reward_cc=2_000_000_000)
    tk = x.tks
    run(clock, bot, close - 58)
    x.books[tk["BTC"]] = ({}, {0.96: 3000})
    run(clock, bot, close + 10)
    ps = x.writes("POST")
    ed = dels(x)
    ck(len(ps) == 1 and ps[0][2]["ticker"] == tk["ETH"] and not any(c[4] >= ex for c in ps),
       "EXIT: a leg that dies at close-58 gets NO order even when the floor would allow it")
    ck(len(ed) == 1 and ex <= ed[0][4] <= ex + 1.0, "EXIT: the resting order's cancel is sent at close-60 s")
    clock, close, x, bot, sink, bk = world(exit_s=90.0)
    run(clock, bot, close + 10)
    ed = dels(x)
    ck(len(ed) == 1 and close - 90.0 <= ed[0][4] <= close - 89.0,
       "--exit-s 90: the cancel is sent at close-90 s (%.2f s before)" % (close - ed[0][4] if ed else -1))

    # 5c. N1: socket down + every GET hanging 30 s around the exit -- cancels still SENT on time
    clock, close, x, bot, sink, bk = world(down=True)
    tk = x.tks
    q0 = ex - QUIET_S
    x.books[tk["BTC"]] = ({}, {0.96: 3000})
    x.hang = (ex - 20.0, ex + 20.0, 30.0, ("GET",))
    run(clock, bot, close + 30)
    ps, ed = x.writes("POST"), dels(x)
    last_d = max(c[4] for c in ed) if ed else None
    ck(len(ps) == 2 and len(ed) >= 2 and all(ex <= c[4] <= ex + 2.5 for c in ed)
       and all(x.orders[k]["status"] == "canceled" and x.orders[k]["canceled_t"] <= ex + 2.5 for k in ("K1", "K2")),
       "N1: socket down, every GET hanging 30 s from exit-20 s: both cancels SENT within 2.5 s of the exit (%s)"
       % [round(c[4] - ex, 2) for c in ed])
    win = [c for c in x.calls if last_d is not None and q0 <= c[4] <= last_d]
    ck(win and all(c[0] == "DELETE" or (c[0] == "GET" and c[1] == "/portfolio/orders") for c in win),
       "N1: from exit-15 s to the last cancel only cancels and the cancel-confirm poll go out (%s)"
       % sorted({(c[0], c[1][:20]) for c in win}))
    ck(win and all(c[5] <= SHORT_TIMEOUT_S + 1e-9 for c in win), "N1: every call from exit-15 s carries a 2 s timeout")
    pre = [c for c in x.calls if ps and ps[0][4] < c[4] < q0]
    ck(pre and all(c[5] <= max(SHORT_TIMEOUT_S, q0 - c[4]) + 1e-6 for c in pre),
       "N1: while an order rests, no earlier call can block into the quiet zone (timeout <= time left, floor 2 s)")
    ck(bot.quiet_refused > 0, "N1: calls refused locally in the quiet zone: %d" % bot.quiet_refused)

    # 5d. N5: cancels AND the poll fail through the close; the order fills at close-1 -- kept cancelling and polling
    clock, close, x, bot, sink, bk = world()
    tk = x.tks
    run(clock, bot, close - 200)
    x.fail_delete_win = (ex - 1.0, close + 20.0)
    x.fail_list_win = (ex - 1.0, close + 20.0)
    run(clock, bot, close - 1)
    x.orders["K1"]["fill_count_fp"], x.orders["K1"]["status"] = "1000.00", "executed"
    run(clock, bot, close + 40)
    eth = bot.orders[1]
    after = [c for c in dels(x, "K1") if c[4] >= close]
    ck(not any(r["ev"] == "expired_at_close" for r in sink) and len(after) >= 2 and eth["filled"] == 1000
       and eth["status"] == "filled" and eth.get("final"),
       "N5: an unconfirmed cancel is re-sent past the close (%d after it) and polled until Kalshi reports the fill"
       % len(after))
    x.results[tk["ETH"]] = "no"
    run(clock, bot, close + SETTLE_AFTER_S + 40)
    ck(eth.get("settled") and abs(eth.get("pnl", 0) + 10.0) < 1e-9 and abs(bot._day(close)["realized"] + 10.0) < 1e-9,
       "N5: that late fill is booked and settled: -$10.00 in the day (not $0.00)")
    summ = [r for r in sink if r["ev"] == "race_summary"]
    ck(len(summ) == 1 and summ[0]["fills"] == 1000, "N5: the race summary carries the 1,000 filled")

    # 5e. N6: a 404 while the order still rests is confirmed by GET and the order re-cancelled
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 200)
    x.del404 = {"K1": 2}
    run(clock, bot, close + 10)
    k1 = [i for i, c in enumerate(x.calls) if c[0] == "DELETE" and c[1].endswith("/K1")]
    between = len(k1) >= 2 and any(c[0] == "GET" and c[1] == "/portfolio/orders" for c in x.calls[k1[0] + 1:k1[1]])
    ck(x.orders["K1"]["status"] == "canceled" and x.orders["K1"]["canceled_t"] <= ex + 5 and len(k1) >= 3
       and between and bot.orders[1]["status"] == "cancelled",
       "N6: two 404s on a still-resting order -> GET-confirmed, re-cancelled, off %.2f s after the exit (%d DELETEs)"
       % (x.orders["K1"].get("canceled_t", 1e18) - ex, len(k1)))

    # 5f. N7: a restart mid-race never sends a second order on the same coin; one process per mode
    clock, close, x, bot, sink, bk = world()
    tk = x.tks
    run(clock, bot, close - 300)
    sink2 = []
    bot2 = Bot(Log(sink=sink2), 4, False, x, lambda: clock[0], bk, spath, stp, 20,
               sleep=lambda s: clock.__setitem__(0, clock[0] + s))
    ok_sw = bot2.sweep(clock[0], "startup")
    run(clock, bot2, close + 30)
    ck(ok_sw and x.orders["K1"]["status"] == "canceled" and len(x.writes("POST")) == 1
       and ("ETH", "already_ordered") in decided(sink2),
       "N7: after a restart (startup sweep cancels the old order) the same coin is NOT ordered again this race")
    lp = os.path.join(tmpd, "lock")
    try:
        la, lb2 = InstanceLock(lp), InstanceLock(lp)
        o1, o2 = la.acquire(), lb2.acquire()
        la.release()
        o3 = lb2.acquire()
        lb2.release()
        ck(o1 and not o2 and o3, "N7: a second instance cannot take the lock; it can once the first lets go")
    except Exception as ex_:
        ck(False, "N7: the instance lock could not be exercised: %r" % ex_)
    _rm(lp)
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    m_ = src[src.rindex(chr(10) + "def main():"):]
    ck("InstanceLock(" in m_ and ".acquire()" in m_ and m_.index("InstanceLock(") < m_.index("Bot("),
       "N7: main() takes the instance lock before it builds the bot")

    # 5g. N2: the day budget
    clock, close, x, bot, sink, bk = world(progs_all=True)
    for c_ in COINS:
        x.books[x.tks[c_]] = ({}, {0.97: 2000})
    run(clock, bot, close - 300)
    rb = {c_ for c_, w in decided(sink) if w == "rail_day_budget"}
    ck(len(x.writes("POST")) == 3 and len(rb) == 2,
       "N2: clean day, 5 dead legs: 3 orders ($30 worst case) and 2 refused 'day_budget' (%s)" % sorted(rb))
    clock, close, x, bot, sink, bk = world(day_realized=-21.0)
    run(clock, bot, close - 300)
    ck(not x.writes("POST") and ("ETH", "rail_day_budget") in decided(sink),
       "N2: today -$21 realized: a $10 order (worst -$31) is refused")
    clock, close, x, bot, sink, bk = world(day_realized=-20.0)
    run(clock, bot, close - 300)
    ck(len(x.writes("POST")) == 1, "N2: today -$20: one $10 order (worst exactly -$30) is allowed")
    # B1: a cancel acknowledged but not yet final still counts toward the day budget (its fill may be unseen)
    clock, close, x, bot, sink, bk = world(day_realized=-20.0)
    bot.orders[999] = {"status": "cancelled", "final": False, "count": 1000.0, "filled": 0.0, "cost": 0.0,
                       "fees": 0.0, "coin": "BTC", "evt": "B1"}
    ck(abs(bot.resting_collateral() - 10.0) < 1e-9 and bot.rails_refusal(1000, clock[0]) == "day_budget",
       "B1: an acknowledged-but-not-final cancel keeps its $10 in the day budget, so a new $10 order is refused at -$20")
    bot.orders[999]["final"] = True
    ck(abs(bot.resting_collateral()) < 1e-9, "B1: once Kalshi reports it final, its collateral is released")
    del bot.orders[999]

    # 5h. N3 arithmetic: alone, 92 s before the exit is the least that pays
    r_ = {"close": T0 + 420.0, "linear": {}}
    exa = T0 + 360.0
    fc = bot.floor_check
    ck(fc(r_, "X", {}, {0.97: 2000}, P, 1000, exa - 92.0)[0] and not fc(r_, "X", {}, {0.97: 2000}, P, 1000, exa - 91.0)[0]
       and not fc(r_, "X", {0.01: 1000}, {0.97: 2000}, P, 1000, exa - 150.0)[0]
       and fc(r_, "X", {0.01: 1000}, {0.97: 2000}, P, 1000, exa - 190.0)[0]
       and not fc(r_, "X", {}, {0.97: 800}, P, 1000, exa - 300.0)[0],
       "N3: alone 92 s before the exit pays $1.00 (91 s: $0.99, refused); half share needs ~182 s; NO side short: 0")

    # 5i. N10: an unreadable program list refuses the race (no assumed $20/1,000), then is re-read
    clock, close, x, bot, sink, bk = world(progs_all=True)
    for c_ in COINS:
        x.books[x.tks[c_]] = ({}, {0.97: 2000})
    x.programs_ok = False
    run(clock, bot, close - 300)
    ck(not x.writes("POST") and any(r["ev"] == "program_list_unreadable" for r in sink)
       and ("ETH", "no_program") in decided(sink),
       "N10: program list unreadable -> every leg refused, no order")
    x.programs_ok = True
    run(clock, bot, close - 200)
    ck(len(x.writes("POST")) == 3 and any(r["ev"] == "programs_read" for r in sink),
       "N10: re-read 30 s later; once it reads, orders go out (3: the day budget)")

    # 5j. N8: Kalshi cancels an order we never asked to cancel -> 'exchange_cancelled'
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 250)
    x.orders["K1"]["status"] = "canceled"
    run(clock, bot, close + 10)
    xc = [r for r in sink if r["ev"] == "exchange_cancelled"]
    ck(len(xc) == 1 and xc[0]["coin"] == "ETH" and bot.orders[1]["status"] == "cancelled"
       and len(x.writes("POST")) == 1 and not dels(x, "K1"),
       "N8: an order Kalshi cancelled on its own is logged 'exchange_cancelled' once, and not re-placed")

    # ---- 6. writer errors can never leave an order up; a lost POST reply is swept ----
    clock, close, x, bot, sink, bk = world()
    x.lose_post = 1                                 # the order IS created but the reply is lost
    run(clock, bot, close - 200)
    eth = [o for o in bot.orders.values() if o["coin"] == "ETH"][0]
    ck(eth["status"] in ("unknown", "resting"), "a lost POST reply leaves the order 'unknown', counted as on the book")
    ck(eth["kid"] == "K1", "the fill poller reconciles it by client_order_id (order id %s)" % eth["kid"])
    x.raise_delete, x.fail_delete = 2, 2            # two exceptions, then two 500s, then it works
    run(clock, bot, close + 30)
    ck(x.orders["K1"]["status"] == "canceled" and x.orders["K1"]["canceled_t"] <= ex + 3.0,
       "two raised exceptions + two 500s on DELETE: re-sent every 0.5 s, off the book %.2f s after the exit"
       % (x.orders["K1"].get("canceled_t", 1e18) - ex))
    ck(not any(o["status"] == "resting" for o in x.orders.values()), "nothing of ours rests at the close")
    clock, close, x, bot, sink, bk = world()
    x.lose_post = 1
    real_poll = bot.poll_orders
    bot.poll_orders = lambda t: None                # the poller is down too
    run(clock, bot, close - 150)
    ck([o["status"] for o in bot.orders.values()] == ["unknown"], "lost reply, blind poller: the order is 'unknown'")
    run(clock, bot, close + 30)
    ck(x.orders["K1"]["status"] == "canceled" and any(r["ev"] == "sweep" for r in sink),
       "the exit sweep (GET resting by client-id prefix) cancels it anyway")
    bot.poll_orders = real_poll
    clock, close, x, bot, sink, bk = world()
    x.drop_post = 1                                 # the request never arrived: no order exists
    run(clock, bot, close - 200)
    ck(bot.orders[1]["status"] == "never_created" and bot.orders[1].get("final"),
       "a lost POST that Kalshi never listed is 'never_created' after 3 listings (no livelock waiting for it)")
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 100)
    bk.raise_on = {x.tks["ETH"]}
    run(clock, bot, close + 20)
    ck(x.orders["K1"]["status"] == "canceled" and any(r["ev"] == "race_error" for r in sink),
       "a decision/book exception every step still ends with the order cancelled at the exit")

    # ---- 7. rails ----
    clock, close, x, bot, sink, bk = world(progs_all=True, day_realized=100.0)
    for c_ in COINS:
        x.books[x.tks[c_]] = ({}, {0.97: 2000})
    run(clock, bot, close - 300)
    ck(len(x.writes("POST")) == 5, "a +$100 day: 5 dead legs -> 5 orders ($50 collateral)")
    ck(bot.rails_refusal(1000, clock[0]) == "max_resting", "a 6th order: refused, max_resting")
    bot.orders[1]["status"], bot.orders[1]["filled"], bot.orders[1]["cost"] = "filled", 1000.0, 10.0
    ck(bot.rails_refusal(1000, clock[0]) == "max_collateral",
       "4 resting ($40) + 1,000 held ($10) + a new $10 = $60 > $55: refused, max_collateral")
    bot.state["days"][et_day(clock[0])] = {"realized": -21.0, "fills_cost": 0.0, "credit_exp": 0.0}
    bot.check_day_stop(clock[0])
    ck(bot.halted(clock[0]) and bot.stopping == "day_stop",
       "day stop: -$21 realized - $10 held unsettled = -$31 <= -$30 -> halted")
    run(clock, bot, clock[0] + 3)
    ck(all(o["status"] in ("cancelled", "filled") for o in bot.orders.values()) and bot.exit_ready,
       "after the day stop everything is cancelled and the bot is ready to exit")
    ck(start_refusal(4, 50, load_state(spath), 20, clock[0], stp) is not None,
       "the day stop survives a restart (state file refuses the start)")
    clock, close, x, bot, sink, bk = world()
    bot.races_max = 1
    run(clock, bot, close + 200)
    ck(len(x.writes("POST")) == 1 and bot.stopping == "races_done",
       "--races 1: after one race with an order the bot cancels all and stops")
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 200)
    open(stp, "w").close()
    run(clock, bot, close - 190)
    sm = [r for r in sink if r["ev"] == "race_summary"]
    ck(bot.stopping == "stop_file" and x.orders["K1"]["status"] == "canceled" and bot.exit_ready,
       "the stop file cancels every resting order and exits")
    ck(len(sm) == 1 and sm[0].get("stopped") == "stop_file" and sm[0]["legs"]["ETH"]["share_s"] > 100,
       "N10: a stop in mid-race still writes the race summary (stopped=stop_file)")
    os.remove(stp)
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 200)
    bot.wind_down("exit")
    sm = [r for r in sink if r["ev"] == "race_summary"]
    ck(x.orders["K1"]["status"] == "canceled" and len(sm) == 1 and sm[0].get("stopped") == "exit",
       "the exit path (wind_down) cancels, confirms and writes the summary")
    clock, close, x, bot, sink, bk = world()
    run(clock, bot, close - 200)
    x.orders["K1"]["fill_count_fp"], x.orders["K1"]["status"] = "1000.00", "executed"
    run(clock, bot, close - 190)
    o1 = bot.orders[1]
    ck(o1["filled"] == 1000 and abs(o1["cost"] - 10.0) < 1e-9 and o1["status"] == "filled",
       "a full fill of 1,000 is booked: held, $10.00 at risk")
    x.results[x.tks["ETH"]] = "no"
    run(clock, bot, close + SETTLE_AFTER_S + 5)
    ck(o1.get("settled") and abs(o1["pnl"] + 10.0) < 1e-9, "the leg loses: -$10.00 realized")
    ck(not bot.halted(clock[0]), "-$10 does not trip the -$30 day stop")
    clock, close, x, bot, sink, bk = world()
    for c_ in COINS:
        x.books[x.tks[c_]] = ({0.01: 1500}, {0.97: 2000})
    run(clock, bot, close + 10)
    ck(not x.writes("POST"), "NULL: no dead leg with room -> no order at all")

    # ---- 8. dry run sends nothing and logs would_place / would_cancel ----
    clock, close, x, bot, sink, bk = world(dry=True)
    bk.sold[x.tks["ETH"]] = [(int((close - 100) * 1000), 300.0)]
    run(clock, bot, close - 150)
    x.books[x.tks["ETH"]] = ({}, {0.99: 50.0, 0.97: 1500})
    run(clock, bot, close - 147)
    x.books[x.tks["ETH"]] = ({}, {0.97: 1500})
    run(clock, bot, close + 10)
    wc = [r for r in sink if r["ev"] == "would_cancel"]
    ck(not x.writes() and any(r["ev"] == "would_place" for r in sink) and len(wc) == 1 and wc[0]["why"] == "exit"
       and 59.0 <= wc[0]["left"] <= 60.0, "dry run: no POST, no DELETE; would_place, and would_cancel at the exit")
    sm = [r for r in sink if r["ev"] == "race_summary"]
    wf = (sm[0]["legs"].get("ETH") or {}).get("would_fill") if sm else None
    ck(wf is not None and wf["would_fill_low"] == 300.0 and wf["no_99c_would_cross"] == 50.0
       and wf["would_fill_high"] == 350.0,
       "dry run: 300 sold into 1c (queue ahead 0) + a 50-lot NO bid resting at 99c for 3 s -> would-fill 300..350 (%s)"
       % wf)
    n99s = [r_ for r_ in sink if r_["ev"] == "snap" and r_.get("n99")]
    ck(len(n99s) == 3 and all(not r_["ok"] and r_["bn"] == 0.99 for r_ in n99s),
       "the 3 seconds with a 99c NO bid are logged (bn 0.99, n99 50) and NOT counted (the filing excludes them)")

    # ---- 9. N8: --report prints leftover next to the SUM of expected_credit_floored, and the verdict ----
    rl, rpl = os.path.join(tmpd, "live.jsonl"), os.path.join(tmpd, "report.jsonl")
    c1 = datetime(2026, 10, 11, 1, 0, tzinfo=timezone.utc).timestamp()        # 9:00 PM ET on 2026-10-10
    c2 = c1 + 900.0
    with open(rl, "w", encoding="utf-8") as fh:
        for evt, cl, ec, fcst, mode in (("E1", c1, 3.0, 1.0, "live"), ("E2", c2, 2.0, 0.5, "live"),
                                        ("E0", c1, 50.0, 0.0, "dry")):
            fh.write(json.dumps({"ev": "race_summary", "evt": evt, "close": utc_iso(cl), "mode": mode,
                                 "expected_credit_floored": ec, "fills_cost": fcst}) + "\n")

    def rsender(credit_usd):
        cash2 = 50.0 - 1.50 + credit_usd

        def s(method, path, body, query, timeout=None):
            if method != "GET":
                return 405, "GET only"
            if path == "/portfolio/balance":
                d_ = cash2 if int(query["exchange_index"]) == 2 else 0.0
                return 200, {"balance": int(round(d_ * 100)), "balance_dollars": "%.4f" % d_}
            if path == "/portfolio/positions":
                return 200, {"market_positions": []}
            if path == "/portfolio/orders":
                return 200, {"orders": []}
            if path == "/portfolio/subaccounts/transfers":
                return 200, {"transfers": [{"to_subaccount": 4, "from_subaccount": 0, "amount_cents": 5000,
                                            "created_ts": int(c1 - 3600)}]}
            if path == "/portfolio/settlements":
                return 200, {"settlements": [{"ticker": "KXCRYPTOLEAD15M-X-ETH", "settled_time": utc_iso(c2 + 90),
                                              "market_result": "no", "value": 0, "yes_count_fp": "150.00",
                                              "no_count_fp": "0", "yes_total_cost_dollars": "1.5000",
                                              "no_total_cost_dollars": "0", "fee_cost": "0"}]}
            return 404, "?"
        return s

    def rep(credit_usd, now):
        lines = []
        _rm(rpl)
        report(rsender(credit_usd), 4, out=lines.append, live_log=rl, report_log=rpl, now=now)
        v = [ln for ln in lines if ln.strip().startswith("VERDICT:")]
        row = [ln for ln in lines if ln.startswith("2026-10-10")]
        return (v[0].split()[1] if v else None), (row[0] if row else ""), lines

    late = c2 + 49 * 3600.0
    v1, row1, ln1 = rep(3.0, late)
    ck(v1 == "PASS" and "$5.00" in row1 and "$1.50" in row1 and " 2 " in row1,
       "N8 report: the 2026-10-10 row shows 2 live races, SUM expected_credit_floored $5.00, fill cost $1.50 (dry "
       "race excluded); leftover $3.00 >= $2.50 and fill cost $1.50 <= $2.50 -> PASS (%s)" % row1.strip())
    ck(rep(0.40, late)[0] == "FAIL", "N8 report: leftover $0.40 < $1.00 48 h after the last race -> FAIL")
    ck(rep(3.0, c2 + 10 * 3600.0)[0] == "TOO_EARLY", "N8 report: 10 h after the last race -> TOO_EARLY")
    ck(rep(2.0, late)[0] == "NEITHER", "N8 report: leftover $2.00 (>= $1, < half of $5.00) -> NEITHER")
    for p in (rl, rpl):
        _rm(p)

    # ---- 10. the working code: one POST, two DELETE call sites, no money movement ----
    body = src[:src.rindex(chr(10) + "class _FakeX")]
    ck(body.count('"POST"') == 1 and body.count('"DELETE"') == 2,
       "the working code has exactly one POST (create order) and two DELETE (cancel, sweep-cancel) call sites")
    ck("/portfolio/subaccounts/transfer\"" not in body and "intra_exchange" not in body
       and '"/portfolio/subaccounts"' not in body and "/deposits" not in body and "/withdrawals" not in body,
       "no transfer, subaccount creation, deposit or withdrawal endpoint anywhere in the working code")
    for p in (spath, stp):
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
    print("racereward_live self-test %s (%d checks, %d failed)" % ("PASSED" if not fails else "FAILED",
                                                                    len(notes) + len(fails), len(fails)))
    return not fails


# ------------------------------------------------------------------------------------------------ main
def code_sha():
    with open(os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser(description="Coin Race reward test: 1c YES filler bids on dead legs, subaccount only")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--subaccount", type=int)
    mx = ap.add_mutually_exclusive_group()
    mx.add_argument("--live", action="store_true")
    mx.add_argument("--dry-run", action="store_true")
    mx.add_argument("--report", action="store_true", help="GET only: the subaccount's leftover cash by ET day + bar")
    ap.add_argument("--races", type=int, default=RACES_DEFAULT,
                    help="end after this many races with at least one order (counted across restarts in live)")
    ap.add_argument("--exit-s", type=float, default=EXIT_S_DEFAULT,
                    help="cancel every order from this many seconds before the close; no new order after it "
                         "(default 60: sellers dump into 1c bids in the last minute)")
    ap.add_argument("--minutes", type=float, default=720.0)
    ap.add_argument("--rest-books", action="store_true", help="no WebSocket: REST books (5 GET/s in the window)")
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    if not selftest(a.verbose):
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    if a.subaccount is None or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account (0) is refused")
    if not (a.live or a.dry_run or a.report):
        raise SystemExit("choose one of --live / --dry-run / --report")
    if not (EXIT_S_MIN <= a.exit_s <= EXIT_S_MAX):
        raise SystemExit("--exit-s must be %.0f..%.0f s" % (EXIT_S_MIN, EXIT_S_MAX))
    import ordercli
    pk = ordercli.load_key(KEY_FILE)

    def sender(method, path, body, query, timeout=None):
        if (a.report or a.dry_run) and method != "GET":
            raise RuntimeError("dry run / report: a %s was attempted and refused" % method)
        return http_send(ordercli.PROD, pk, KEY_ID, method, path, body=body, query=query,
                         timeout=DEFAULT_TIMEOUT_S if timeout is None else timeout)
    if a.report:
        return report(sender, a.subaccount)
    lock = InstanceLock(LIVE_LOCK if a.live else DRY_LOCK)
    if not lock.acquire():
        raise SystemExit("REFUSED: another racereward %s process holds %s (%s)"
                         % ("live" if a.live else "dry-run", lock.path, lock.holder()))
    try:
        log_path = a.log or (LIVE_LOG if a.live else DRY_LOG)
        state_path = LIVE_STATE if a.live else DRY_STATE
        log = Log(log_path)
        bal = read_balance(sender, a.subaccount)
        state = load_state(state_path)
        day = kalshi_day(sender, a.subaccount, time.time())
        why = start_refusal(a.subaccount, bal, state, a.races, time.time(), STOP_FILE, day)
        if a.dry_run and why and a.subaccount >= 1:
            log.write("would_refuse_live_start", why=why, note="dry run continues; --live would stop here")
            print("  NOTE (dry run continues): --live would refuse: " + why)
            if len(state.get("races") or []) >= a.races:
                state["races"] = []
                save_state(state_path, state)
        elif why:
            raise SystemExit("REFUSED: " + why)
        books = RestBooks()
        if not a.rest_books:
            try:
                books = WSBooks(KEY_ID, KEY_FILE)
            except Exception as e:
                print("  WebSocket books unavailable (%r); REST books" % e)
        bot = Bot(log, a.subaccount, a.dry_run, sender, time.time, books, state_path, STOP_FILE, a.races,
                  exit_s=a.exit_s)
        if a.live and not any(bot.sweep(time.time(), "startup") for _ in range(3)):
            raise SystemExit("REFUSED: could not list / cancel resting orders in subaccount %d at startup"
                             % a.subaccount)
        if day is not None and not a.dry_run:
            dd = bot._day(time.time())
            dd["realized"] = min(dd["realized"], day[0])      # Kalshi's settled P&L today, if worse than the state's
        log.write("start", pid=os.getpid(), argv=sys.argv, code_sha=code_sha(), mode="live" if a.live else "dry",
                  subaccount=a.subaccount, balance_pool2=bal, kalshi_day=day, races_max=a.races,
                  races_done=len(bot.state["races"]), books=type(books).__name__,
                  rails={"price": PRICE, "count_max": COUNT_MAX, "window_s": WINDOW_S, "exit_s": a.exit_s,
                         "quiet_s": QUIET_S, "short_timeout_s": SHORT_TIMEOUT_S, "floor_usd": FLOOR_USD,
                         "floor_margin_s": FLOOR_MARGIN_S, "dead_yes": DEAD_YES, "alive_yes": ALIVE_YES,
                         "no_max": NO_MAX, "max_resting": MAX_RESTING, "max_collateral": MAX_COLLATERAL,
                         "day_stop": DAY_STOP, "bal_min": BAL_MIN, "bal_max": BAL_MAX, "writes_per_s": WRITES_PER_S})
        print("racereward %s: subaccount %d, pool-2 balance %s, races %d/%d, exit %.0f s, log %s"
              % ("LIVE" if a.live else "DRY RUN", a.subaccount, bal, len(bot.state["races"]), a.races, a.exit_s,
                 log_path))
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
