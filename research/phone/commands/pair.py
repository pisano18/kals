"""/pair <secret> -- make this chat the one that controls the bot (telegram.json's chat_id), then show /help.

v-tg-rebuild step 9 (2026-10-30): the /pair branch of Phone.handle as a command module, byte-identical (golden shadow:
research/golden/shadow.py with --case "/pair <secret>=phone.commands.pair"; research/golden/shadow_more.py runs the
golden pair/* cases -- right, right with @bot, wrong, empty -- on an UNPAIRED phone).

THE ROUTER (step 10) must run /pair BEFORE its paired-chat check (it is the one command an unpaired or other chat may
send) and WITHOUT the ledger refresh (Phone.handle answered /pair before refreshing): needs_ledger=False says the second.
A wrong or empty secret answers nothing (None) and logs the refusal, exactly as before.
"""
import json

from botdata import paths as _paths
from phone.command import Command, declare
from phone.commands.help_cmd import help_html
from phone.html import Html
from phone.log import log


def save_cfg(cfg, cfg_path):                    # from pinphone.Phone.save_cfg (only /pair saves the config)
    """telegram.json, rewritten (indent 2). A failure is logged, never raised."""
    try:
        _paths.check_write(cfg_path)        # v-tg-rebuild step 2: never C:\kals under KALS_TESTING=1
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except OSError as e:
        log("could not save config: %s" % e)


def handle(ctx):
    arg = ctx.arg
    if arg.strip() and arg.strip() == str(ctx.cfg.get("secret", "")).strip():
        ctx.cfg["chat_id"] = ctx.chat_id
        save_cfg(ctx.cfg, ctx.cfg_path)
        log("paired with chat %s" % ctx.chat_id)
        return Html("<b>Paired.</b> This chat now controls the bot.\n\n" + help_html(ctx.active(), ctx.pp))
    log("refused pairing from chat %s" % ctx.chat_id)
    return None


COMMAND = declare(Command(
    names=("/pair",), section=None, chart=None, handle=handle, needs_ledger=False,
    examples=("/pair not-the-secret",)))
