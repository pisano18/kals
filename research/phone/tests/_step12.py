"""_step12.py -- the /help lines step 12's phone controls ADD (lane R), for the tests that hold /help to the frozen legacy
phone. Not a test file itself.

v-tg-step12 (2026-10-30, lane R): /resume (/pause <bot>), /approve and /move are new commands in /help's Controls
section. Every other byte of /help is the legacy one, so the tests that compared /help with the legacy phone now compare
it with the legacy text PLUS these lines in their places (with_step12): nothing else may change.
"""
import importlib

from phone.commands import help_cmd as H

MODULES = ("phone.commands.botctl", "phone.commands.approve", "phone.commands.move")


def rows():
    """[(section, order, help_line)] the step-12 modules declare (those present in this tree)."""
    from phone import command as CM
    out = []
    for m in MODULES:
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as e:
            if e.name != m:
                raise
            continue
        for c in CM.of_module(m):
            if c.section is not None and c.help_line:
                out.append((c.section, c.order, c.help_line))
    return out


def with_step12(text):
    """`text` (legacy /help, its template, or any reply that embeds it) with the step-12 lines put in their sections
    by order; text without /help's Controls block comes back unchanged."""
    s = str(text)
    new = rows()
    for sec in sorted({r[0] for r in new}):
        legacy = sorted((o, line) for se, o, line in H.HELP_ENTRIES if se == sec)
        if not legacy:
            continue
        old_block = "\n".join([H.HEADS[sec]] + [line for _o, line in legacy])
        if old_block not in s:
            continue
        merged = sorted(legacy + [(o, line) for se, o, line in new if se == sec])
        s = s.replace(old_block, "\n".join([H.HEADS[sec]] + [line for _o, line in merged]))
    return s
