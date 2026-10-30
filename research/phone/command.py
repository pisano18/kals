"""command.py -- the Command a phone command module declares, and the tiny registry the modules declare into.

v-tg-rebuild step 9 (2026-10-30). Each research/phone/commands/<x>.py says what it is with ONE module-level declaration:

    COMMAND = declare(Command(
        names=("/hedges",), section="now", order=60,
        help_line="/hedges — the pin bot's insurance, whether it was needed, % of the bank",
        chart="hedges", load=load, render=render))

and nothing here dispatches: the router (phone/router.py, step 10) is the only caller of Command.run. Until then the
golden shadow (research/golden/shadow.py) runs Command.run beside the old Phone.text_* method and wants the same bytes.

A Command is either load + render (preferred: load(ctx) reads -- files, Kalshi, the ledger, botstats -- and returns
plain data; render(data) or render(data, ctx) builds the reply from that data only) or one handle(ctx) (a command that
starts a worker, changes state, or cannot be split without changing its bytes). `fail` is the old method's
`except Exception as e: log(traceback.format_exc()); return "Could not build /x: ..."` wall: run() catches, logs the
traceback the same way and returns fail(e). No fail = an exception propagates (the router's per-command wall, step 10).
"""
import importlib
import inspect
import pkgutil
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Tuple, Union

from phone.log import log

SECTIONS = ("money", "one_bot", "now", "server", "controls")   # /help's sections, in order (HELP_TEXT's emoji headings)


@dataclass(frozen=True)
class Command:
    """One phone command (its names share one handler; ctx.cmd says which name was typed).

    names           every name, the main one first: ('/fills', '/bets'). Lower-case, with the slash, no '@bot'.
    section         /help's section (SECTIONS) or None (not listed in /help, e.g. aliases-only or hidden commands).
    help_line       the /help line exactly as HELP_TEXT has it today (None: not listed, or listed by the registry's
                    Bot.help -- the one-bot pages).
    order           position in its section (lower first); the router sorts by it (step 10).
    chart           the picture after the words: None (words only), a kind for every name ('hedges'), or
                    {name: kind or None} -- must equal tgcharts.kind_of(name) for each name (shadow.py checks).
    load, render    load(ctx) -> data; render(data) or render(data, ctx) -> Html / str / None.
    handle          handle(ctx) -> reply, instead of load + render.
    fail            fail(exception) -> reply: the old method's 'Could not build ...' answer (see the module note).
    needs_ledger    the router refreshes ctx.ledger before running it (every command does today: Phone.handle).
    runs_in_worker  it starts a background worker that later calls ctx.say (controls, /update).
    examples        extra message texts the shadow / tests run besides the bare names: ('/server help', '/stop yes').
    """
    names: Tuple[str, ...]
    section: Optional[str] = None
    help_line: Optional[str] = None
    order: int = 0
    chart: Union[None, str, Mapping[str, Optional[str]]] = None
    load: Optional[Callable[[Any], Any]] = None
    render: Optional[Callable[..., Any]] = None
    handle: Optional[Callable[[Any], Any]] = None
    fail: Optional[Callable[[BaseException], Any]] = None
    needs_ledger: bool = True
    runs_in_worker: bool = False
    examples: Tuple[str, ...] = ()
    module: str = field(default="", compare=False)

    def __post_init__(self):
        names = tuple(self.names) if not isinstance(self.names, str) else (self.names,)
        object.__setattr__(self, "names", names)
        object.__setattr__(self, "examples", tuple(self.examples))
        if not names:
            raise ValueError("Command: no names")
        for n in names:
            if not (isinstance(n, str) and n.startswith("/") and n == n.lower() and "@" not in n and " " not in n):
                raise ValueError("Command: a name is '/lower-case' with no '@' or space: %r" % (n,))
        if self.section is not None and self.section not in SECTIONS:
            raise ValueError("Command %s: section %r is not one of %s" % (names[0], self.section, SECTIONS))
        if (self.handle is None) == (self.load is None or self.render is None):
            raise ValueError("Command %s: give load + render, or handle (not both)" % names[0])
        if isinstance(self.chart, Mapping):
            extra = sorted(set(self.chart) - set(names))
            if extra:
                raise ValueError("Command %s: chart names %s are not its names" % (names[0], extra))
        if self.render is not None:
            try:
                n = len([p for p in inspect.signature(self.render).parameters.values()
                         if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
            except (TypeError, ValueError):
                n = 1
            if n not in (1, 2):
                raise ValueError("Command %s: render takes (data) or (data, ctx)" % names[0])
            object.__setattr__(self, "_render_ctx", n == 2)

    @property
    def name(self):
        return self.names[0]

    def kind_of(self, name=None):
        """The chart kind after `name` (default the main name), or None."""
        name = name or self.names[0]
        if isinstance(self.chart, Mapping):
            return self.chart.get(name)
        return self.chart if name in self.names else None

    def run(self, ctx):
        """The reply for ctx's message: handle(ctx), or render(load(ctx)); `fail` turns an exception into its words."""
        try:
            if self.handle is not None:
                return self.handle(ctx)
            data = self.load(ctx)
            if getattr(self, "_render_ctx", False):
                return self.render(data, ctx)
            return self.render(data)
        except Exception as e:                                  # noqa: BLE001
            if self.fail is None:
                raise
            log(traceback.format_exc())
            return self.fail(e)


# ---- the registry (declaration only: the router, step 10, dispatches) -------------------------------------------------
_BY_NAME = {}                   # '/name' -> Command
_BY_MODULE = {}                 # module name -> [Command]


def declare(*cmds):
    """Register the module's Command(s); returns the one Command (or the tuple of them) for COMMAND = declare(...).
    A name already declared by ANOTHER module is an error; the same module declaring again (a re-import) replaces."""
    mod = sys._getframe(1).f_globals.get("__name__", "")
    out = []
    for c in cmds:
        if not isinstance(c, Command):
            raise TypeError("declare: not a Command: %r" % (c,))
        if not c.module:
            object.__setattr__(c, "module", mod)
        for n in c.names:
            old = _BY_NAME.get(n)
            if old is not None and old.module != c.module:
                raise ValueError("command %s is declared by %s and %s" % (n, old.module, c.module))
        out.append(c)
    for old in _BY_MODULE.get(mod, []):
        for n in old.names:
            if _BY_NAME.get(n) is old:
                del _BY_NAME[n]
    _BY_MODULE[mod] = out
    for c in out:
        for n in c.names:
            _BY_NAME[n] = c
    return out[0] if len(out) == 1 else tuple(out)


def by_name(name):
    """The Command declared for '/name' (lower-case, no '@'), or None. Only modules already imported are known."""
    return _BY_NAME.get(name)


def commands():
    """Every declared Command, once each, in declaration order."""
    seen, out = set(), []
    for cs in _BY_MODULE.values():
        for c in cs:
            if id(c) not in seen:
                seen.add(id(c))
                out.append(c)
    return out


def of_module(module):
    """The Command(s) a module declared (its COMMAND / COMMANDS), as a list."""
    m = importlib.import_module(module) if isinstance(module, str) else module
    got = getattr(m, "COMMANDS", None)
    if got is None:
        got = getattr(m, "COMMAND", None)
    if got is None:
        return []
    return list(got) if isinstance(got, (list, tuple)) else [got]


def discover(package="phone.commands"):
    """Import every module of the commands package; {module name: exception} for those that failed to import (the
    router answers 'this command failed to load', step 10). The rest are declared."""
    pkg = importlib.import_module(package)
    failed = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_") or info.name == "tests":
            continue
        name = "%s.%s" % (package, info.name)
        try:
            importlib.import_module(name)
        except Exception as e:                                  # noqa: BLE001
            failed[name] = e
    return failed
