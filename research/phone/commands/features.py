"""/features -- every bot's job and its settings as boot_all.ps1 has them now, plus the ladder's rails from
ladder_live.py and the rules block.

v-tg-rebuild step 9 (2026-10-30): Phone.text_features as a command module, byte-identical (golden shadow). The page is
pinphone.features_html (it reads boot_all.ps1 and ladder_live.py on each call, through pinphone's BOOT_ALL / LADDER_PY
globals the tests patch, so it stays ctx.pp.features_html until those move): one call that reads and lays out at once,
hence `handle`. No Kalshi read. The old wall: any exception -> logged, 'Could not build /features: ...' (`fail`).
"""
from phone.command import Command, declare


def handle(ctx):
    return ctx.pp.features_html(active=ctx.active(), procs=ctx.bs_procs)


COMMAND = declare(Command(
    names=("/features",), section="now", order=90,
    help_line="/features — what each bot does and the settings it runs with now (read from boot_all.ps1), and the "
              "rules they run under",
    chart=None, handle=handle,
    fail=lambda e: "Could not build /features: %s" % str(e)[:200]))
