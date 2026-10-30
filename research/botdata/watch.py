"""watch.py -- what the phone's monitor reads about each bot, through the registry's hooks (v-tg-rebuild step 12, lane Q,
2026-10-30). DATA only: no words, never imports the phone.

  watch_in(now)         the WatchIn a hook gets: RESULTS, the clock, the ET day, and the log readers (botdata.logs)
  gauges(name, now)     Bot.stop_gauges: where each of its stops stands now (the early warnings)
  gauge_level(g)        how many of a Gauge's warning levels it is through (len(warn_at) + 1 = tripped)
  books(name, upto)     Bot.books: each of its pots as its own log has it at Kalshi's read time `upto`
  compare(c, name, b, read_t)   one Book against botstats' cache (Kalshi's cash + open bets in that pot, from ONE read):
                        the gap, the money Kalshi's listings show moving in or out since the book's start, the markets
                        Kalshi settled that the book does not have, and whether the gap is past the tolerance

A hook that raises costs only that bot's check (the caller logs it); a bot without the hook has nothing to say.
"""
import bots as _bots
from botdata import clock as _clock
from botdata import logs as _logs
from botdata import money as _money
from botdata import paths as _paths
from botdata import pots as _pots
from bots.spec import WatchIn

# the balance check's tolerance: off by more than max($2, 1% of the pot) + 5c a market settled since the book's start
# (fees the bot books and fees Kalshi charges differ by a cent or two a market: FX measured ~2c on 10-30)
TOL_USD = 2.0
TOL_FRAC = 0.01
TOL_PER_MARKET = 0.05


def watch_in(now):
    """The readers a monitor hook gets, at clock `now`."""
    now = float(now)
    return WatchIn(results=_paths.RESULTS, now=now, today=_clock.et_day(now), last_record=_logs.last_record,
                   read_since=_logs.read_since, epoch=_clock.utc_epoch, et_day=_clock.et_day)


def gauges(name, now, wi=None):
    """[Gauge] of bot `name` now ([] when it has no stop_gauges hook)."""
    b = _bots.get(name)
    hook = getattr(b, "stop_gauges", None) if b is not None else None
    if hook is None:
        return []
    return list(hook(wi or watch_in(now)) or [])


def gauge_level(g):
    """0 = above every warning level; k = through the first k of g.warn_at; len(warn_at) + 1 = tripped (money at or
    under the line, or its own record says so)."""
    if g.tripped or g.money <= g.line + 1e-9:
        return len(g.warn_at) + 1
    return sum(1 for lv in g.warn_at if g.money <= lv + 1e-9)


def books(name, upto, now=None, wi=None):
    """[Book] of bot `name` at Kalshi's read time `upto` ([] when it has no books hook)."""
    b = _bots.get(name)
    hook = getattr(b, "books", None) if b is not None else None
    if hook is None:
        return []
    return list(hook(wi or watch_in(upto if now is None else now), float(upto)) or [])


def pool_only(name, sub):
    """True when bot `name`'s pot in subaccount `sub` is its own pool only (Pot.pool_only)."""
    b = _bots.get(name)
    return any(p.sub == sub and p.pool_only for p in (b.pots if b is not None else ()))


def compare(c, name, b, read_t):
    """Book `b` of bot `name` against botstats' cache `c` (read at `read_t`). {'why': reason} when Kalshi's side cannot
    be worked out from one read; else kalshi (cash + open bets now), books (value0 + settled), gap (kalshi - books),
    flows (money Kalshi lists moving in (+) or out (-) of the pot since b.t0), tol, off, kalshi_only ([market rows Kalshi
    settled after b.t0 that the book does not have, each with its $])."""
    sub = b.sub
    kalshi, why = _pots._pot_now(c, sub, own=pool_only(name, sub))
    if kalshi is None:
        return {"why": why}
    led = c.get("ledgers") or {}
    flows = _pots.flows(led, sub, b.t0, float(read_t) + 1.0) if led.get("fetched") else 0.0
    want = b.value0 + b.settled
    gap = kalshi - want
    tol = max(TOL_USD, TOL_FRAC * abs(kalshi)) + TOL_PER_MARKET * b.markets
    only = []
    rows = ((c.get("subs") or {}).get(sub) or {}).get("rows") or {}
    for s in rows.values():
        t = _clock.utc_epoch(s.get("settled_time"))
        tk = str(s.get("ticker") or "")
        if t is None or not (b.t0 < t <= float(read_t)) or tk in b.tickers or _bots.owner(tk, sub) != name:
            continue
        only.append(_money.market(s))
    only.sort(key=lambda m: m["t"] or 0)
    # v-tg-balmove (2026-10-30): money Kalshi lists moving in or out (a phone /move, a deposit into the pot) is EXPECTED,
    # not a mismatch -- before this, any /move into a bot's pot raised an urgent BALANCE alert until the bot restarted
    return {"why": None, "kalshi": round(kalshi, 2), "books": round(want, 2), "gap": round(gap, 2),
            "flows": round(flows, 2), "tol": round(tol, 2), "off": abs(gap - flows) > tol, "kalshi_only": only}


__all__ = ["watch_in", "gauges", "gauge_level", "books", "pool_only", "compare", "TOL_USD", "TOL_FRAC",
           "TOL_PER_MARKET"]
