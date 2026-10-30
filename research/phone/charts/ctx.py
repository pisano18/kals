"""ctx.py -- ChartCtx: everything a picture reads, fixed right after the command's words were built.

v-tg-rebuild step 8 (2026-10-30). tgcharts took a dict whose "pp" was the pinphone MODULE itself and reached into it
(pp._bs(), pp.Phone._sides with a fake self, pp.markets_from, pp.raw_ledger, pp.window_stats, pp.FIRST_LIVE_DAY,
pp.main_words): a pinphone <-> tgcharts cycle (DESIGN 1.6, tangle 2). ChartCtx names each thing the charts use instead:

  now           the clock the words used (epoch)
  ledger        a private copy of pindesk.Ledger's lists (the LEDGER_KINDS only; None otherwise)
  bs_getter, bs_procs   botstats' Kalshi getter and process table, as the words use them
  funds_what    {account: words} (pinphone.funds_what for every FUNDS_WHAT account) -- /funds names stopped pots
  active        the active bots (botstats.active_bots) -- 'pin bot' vs 'pin bot + coin race'
  bars          /bars' gathered numbers (bars.gather), the 'bars' kind only
  botstats      () -> the botstats module (default: import it). It may RAISE: a broken botstats costs the botstats
                pictures, which then draw the main account's own picture instead
  markets       (ledger) -> {ticker: market}: the main account's markets (pinphone.markets_from over raw_ledger, with
                Phone._sides), /stats' fallback picture and /hedges
  window_stats  (markets, taus) -> stats (pinphone.window_stats), /stats' fallback picture
  first_live_day  'YYYY-MM-DD' (pinphone.FIRST_LIVE_DAY), /stats' fallback picture
  main_words    (active) -> 'pin bot + coin race' / 'pin bot' (pinphone.main_words); None = 'pin bot + coin race'

build() still takes the OLD dict (pinphone builds it today: Phone._chart_ctx) and adapts it with as_ctx(); every pp
access stays lazy, at the moment the old code made it, so a planted or broken pp fails in the same place as before.
"""
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from botdata import clock


def _import_botstats():
    import botstats
    return botstats


@dataclass
class ChartCtx:
    now: float
    ledger: Any = None
    bs_getter: Any = None
    bs_procs: Any = None
    funds_what: Optional[dict] = None
    active: Any = None
    bars: Any = None
    botstats: Callable[[], Any] = _import_botstats
    markets: Optional[Callable[[Any], dict]] = None
    window_stats: Optional[Callable] = None
    first_live_day: Optional[str] = None
    main_words: Optional[Callable[[Any], str]] = None

    def bs(self):
        """The botstats module (raises when it cannot be had)."""
        return self.botstats()

    def bs_load(self):
        """(bs, cache, process rows, process table read?) -- botstats._load as the words use it."""
        bs = self.bs()
        c, prows, ok = bs._load(self.now, self.bs_getter, self.bs_procs)
        return bs, c, prows, ok

    def bs_args(self):
        """(bs, now, getter, procs): the first arguments of botdata.series' all_* functions."""
        return self.bs(), self.now, self.bs_getter, self.bs_procs

    def main_account_markets(self):
        """/stats' (fallback) and /hedges' markets: pinphone.markets_from(raw_ledger) with Phone._sides, on the
        snapshot."""
        if self.markets is None:
            raise RuntimeError("no main-account markets for this picture (ChartCtx.markets is not set)")
        return self.markets(self.ledger)

    def words_main(self):
        """'pin bot + coin race' or 'pin bot' -- the main account's bots the phone names now (pinphone.main_words)."""
        try:
            return self.main_words(self.active) if self.main_words is not None else "pin bot + coin race"
        except Exception:                               # noqa: BLE001
            return "pin bot + coin race"

    day_minus = staticmethod(clock.day_minus)           # pinphone.day_minus, the same code (botdata.clock)


def _no_pp():
    raise KeyError("pp")                                # the old ctx["pp"] with no "pp": the same failure, same place


def phone_markets(pp, led):
    """pinphone's main-account markets for the ledger snapshot `led`: markets_from(raw_ledger(the Kalshi ledger file),
    Phone._sides over `led`) -- tgcharts.markets_of, verbatim. A helpers module that names it (pinphone's chart_markets
    since v-tg-rebuild step 10, when Phone._sides went into the command modules) is asked for it directly."""
    cm = getattr(pp, "chart_markets", None)
    if cm is not None:
        return cm(led)

    class _S:
        ledger = led
    sides = pp.Phone._sides(_S())
    return pp.markets_from(pp.raw_ledger(os.path.join(led.results, pp.pinday.LEDGER_NAME)), sides)


def as_ctx(ctx):
    """A ChartCtx as it is, or the old dict ({"now", "pp", "ledger", "bs_getter", "bs_procs", "funds_what", "active",
    "bars"}) adapted. Nothing is read from pp here: each field reaches pp only when a picture asks for it."""
    if isinstance(ctx, ChartCtx):
        return ctx
    pp = ctx.get("pp")
    kw = dict(now=ctx.get("now"), ledger=ctx.get("ledger"), bs_getter=ctx.get("bs_getter"), bs_procs=ctx.get("bs_procs"),
              funds_what=ctx.get("funds_what"), active=ctx.get("active"), bars=ctx.get("bars"))
    if pp is None:
        return ChartCtx(botstats=_no_pp, **kw)
    return ChartCtx(botstats=lambda: pp._bs(), markets=lambda led: phone_markets(pp, led),
                    window_stats=lambda ms, taus: pp.window_stats(ms, taus),
                    first_live_day=getattr(pp, "FIRST_LIVE_DAY", None),
                    main_words=(lambda active: pp.main_words(active)) if hasattr(pp, "main_words") else None, **kw)
