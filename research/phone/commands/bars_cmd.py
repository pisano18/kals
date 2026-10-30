"""/bars -- every running test against its pre-registered bar: research/bars.py's text, unchanged in words (one place
decides PASS / KILL / EXTEND / TOO EARLY; the phone quotes it), laid out by pinphone.bars_html.

v-tg-rebuild step 9 (2026-10-30): Phone.text_bars as a command module (load + render), byte-identical (golden
shadow). State written exactly as before: ctx.state._bars_d = None first, then bars.gather()'s dict, so /bars'
picture draws these very numbers. A planted ctx.bars_fn (the self-test) is quoted with no wall, as before; otherwise
any exception in bars.py or the layout -> logged, 'Could not build /bars: ...'.
"""
import traceback

from phone.command import Command, declare
from phone.log import log


def load(ctx):
    """('planted', text) | ('text', bars.py's words) | ('err', exception, already logged)."""
    if ctx.bars_fn is not None:
        return ("planted", ctx.bars_fn())
    ctx.state._bars_d = None
    try:
        import bars
        # bars.text() is render(gather()); gathered here so /bars' picture uses these very numbers
        d = bars.gather(ctx.ledger.results, ctx.now())
        ctx.state._bars_d = d
        return ("text", bars.render(d))
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        return ("err", e)


def failed(e):
    return ("Could not build /bars: %s\nEverything else still works -- /stats and /racestats "
            "carry the raw numbers." % str(e)[:200])


def render(data, ctx):
    kind, x = data
    if kind == "planted":
        return ctx.pp.bars_html(x)
    if kind == "err":
        return failed(x)
    try:
        return ctx.pp.bars_html(x)
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        return failed(e)


COMMAND = declare(Command(
    names=("/bars",), section="now", order=80,
    help_line="/bars — the September tests against their pre-registered bars (all finished; kept for the record)",
    chart="bars", load=load, render=render))
