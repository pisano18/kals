"""bots -- THE REGISTRY: one file per bot (research/bots/<name>.py, each defining BOT = spec.Bot(...)).

v-tg-rebuild step 1 (2026-10-30). The phone knew each bot through ~30 parallel tables spread over botstats.py,
pinphone.py and tgcharts.py, synced by hand (DESIGN 1.6, tangle 1). This package holds every per-bot fact once and
DERIVES the old tables from it; bots/tests/test_registry.py proves each derived table equals the live one it will
replace. Nothing in production imports this yet: botstats switches in step 3, pinphone and tgcharts in step 5.

Adding a bot = one file here. Retiring one = retired=True. Pausing one = its stop file (no code change).

Nothing is imported at `import bots` time: the bot files are discovered (pkgutil) and validated on first use, and the
derived tables (BOTS, SUB_POOL, ...) are module attributes computed on first access (PEP 562 __getattr__), so a broken
bot file costs the first caller a clear error, never an import cycle.

owner(ticker, sub) keeps botstats.owner's precedence exactly: within a subaccount the pots that CLAIM tickers are asked
in priority order (subaccount 0: the race, then the pin bot; subaccount 3: the jump band; subaccount 4: the FX pairs),
then the sub's one catch-all pot (1 ladder, 2 forecaster, 3 weather, 5 fx), else 'other'. A sub with no pot at all
(None, '6', an int) reads as the main account -- botstats.owner's if-chain did the same.
"""
import importlib
import pkgutil
import re

from bots.spec import Bot, toks

EARLIER = "earlier"                 # botstats.EARLIER: every hidden bot's past money on one line
OTHER = "other"
# words / names / colours for the two lines that are not a bot (pinphone.BOT_WORD, tgcharts.BOT_SHORT / BOT_COLOUR)
NOT_BOT_WORD = {EARLIER: "earlier bots", OTHER: "not any bot's"}
NOT_BOT_SHORT = {EARLIER: "Earlier bots", OTHER: "Other"}
NOT_BOT_COLOUR = {EARLIER: "#bdb8aa",       # light warm grey: every paused or retired bot together (v-tg-active)
                  OTHER: "#8f8d86"}         # grey
# /funds' words for a pool no registry bot trades (pinphone.FUNDS_WHAT): {account: {pool: words}}
EXTRA_POOLS = {4: {2: "coin-race reward test (stopped)"}}

# The bots' refusal reasons in ordinary words (botstats.PLAIN): this shared part first, then each bot's own
# (Records.refusal_words) in bot order. The first pattern that matches wins.
PLAIN_BASE = [(r"^no_offer$", "nothing for sale"), (r"^edge_floor$", "edge too thin"),
              (r"^price_ceiling$", "price over the cap"), (r"^confidence$", "not sure enough"),
              (r"^depth_floor$", "too few for sale"), (r"^book_stale$", "order book too old"),
              (r"^index_stale$", "price feed too old"), (r"^toxic_fresh$", "sellers dumping"),
              (r"^jump_against$", "price jumped against us"), (r"^early_dear$", "early price too high"),
              (r"^early_once$", "early bet already taken"), (r"^max_per_market$", "market already full"),
              (r"^market_attempts$", "tried this market enough"), (r"^close_budget", "quarter-hour budget used"),
              (r"^tau N is past", "too early"), (r"already holding", "already holds that coin"),
              (r"^halted", "halted after a loss"), (r"confirmation", "still confirming"),
              (r"^price N is under", "price under its floor"), (r"under one contract", "bet under 1 contract"),
              (r"^in_flight$", "order already in flight"), (r"^late$", "too late to send"),
              (r"^stale$", "decision went stale"), (r"^cap$", "at its cap"), (r"^price$", "price out of range"),
              (r"^max_contracts$", "contract cap"), (r"^max_commit$", "money cap")]

# /features rows that are no bot's (pinphone.FEATURES), by their place in that list
EXTRA_FEATURES = (
    (11, ("bettor_paper.py", None, None, "Clean-room bettor (paper)",
          "The clean-room bettor's rule on paper; no orders.")),
    (13, ("rain_paper.py", None, None, "Rain tail NO desk (paper, SJ02)",
          "Sells the far tail of rain markets on paper; no orders.")),
    (14, ("pinledgerd.py", None, None, "Ledger refresher",
          "Fetches Kalshi's settlements and keeps results\\kalshi_ledger.json current; trades nothing.")),
    (15, ("cdc_record.py", None, None, "Crypto.com recorder",
          "Records Crypto.com prices to the tape (public data, no key, no orders).")),
    (16, ("pinphone.py", None, None, "Phone link", "This Telegram link: answers one paired chat, opens no port.")),
)

_R = {}                             # the loaded registry: {"all": (Bot, ...), "by_name": {...}, ...}


class RegistryError(Exception):
    pass


# ---- discovery + validation ---------------------------------------------------------------------------------------
def _discover():
    found = []
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_") or m.name in ("spec", "tests") or m.ispkg:
            continue
        mod = importlib.import_module("%s.%s" % (__name__, m.name))
        b = getattr(mod, "BOT", None)
        if not isinstance(b, Bot):
            raise RegistryError("bots/%s.py defines no BOT = spec.Bot(...)" % m.name)
        if b.name != m.name:
            raise RegistryError("bots/%s.py names its bot %r: the file and the name must match" % (m.name, b.name))
        found.append(b)
    return found


def validate(bots):
    """Raise RegistryError on: a repeated name, order or command; a bot with no pot; two catch-all pots (or two
    pool-only pots) in one subaccount; a sub-claims pot that is no callable."""
    seen_name, seen_order, seen_cmd = set(), set(), {}
    catch, pool_only = {}, {}
    for b in bots:
        if b.name in seen_name or b.name in (EARLIER, OTHER):
            raise RegistryError("bot name %r used twice (or reserved)" % b.name)
        seen_name.add(b.name)
        if b.order in seen_order:
            raise RegistryError("bot order %d used twice (%s)" % (b.order, b.name))
        seen_order.add(b.order)
        for c in tuple(b.commands) + tuple(b.extra_commands):
            if c in seen_cmd:
                raise RegistryError("command %s is both %s's and %s's" % (c, seen_cmd[c], b.name))
            seen_cmd[c] = b.name
        if b.command not in b.commands:
            raise RegistryError("%s: its command %s is not one of its commands" % (b.name, b.command))
        if not b.pots:
            raise RegistryError("%s has no pot" % b.name)
        for p in b.pots:
            if p.claims is None:
                if p.sub in catch:
                    raise RegistryError("subaccount %s has two catch-all pots (%s, %s)" % (p.sub, catch[p.sub], b.name))
                catch[p.sub] = b.name
            elif not callable(p.claims):
                raise RegistryError("%s: a pot's claims is not callable" % b.name)
            if p.pool_only:
                if p.sub in pool_only:
                    raise RegistryError("subaccount %s has two pool-only pots" % p.sub)
                pool_only[p.sub] = b.name
    return True


def _load():
    if _R:
        return _R
    bots = sorted(_discover(), key=lambda b: b.order)
    validate(bots)
    by_sub = {}
    for b in bots:
        for p in b.pots:
            by_sub.setdefault(p.sub, []).append((b, p))
    subs = tuple(sorted(by_sub, key=lambda s: (len(s), s)))
    claim = {s: sorted([(b, p) for b, p in by_sub[s] if p.claims is not None], key=lambda bp: (bp[1].priority, bp[0].order))
             for s in subs}
    catch = {s: next((b.name for b, p in by_sub[s] if p.claims is None), None) for s in subs}
    _R.update(all=tuple(bots), by_name={b.name: b for b in bots}, by_sub={s: tuple(by_sub[s]) for s in subs},
              subs=subs, claim=claim, catch=catch,
              by_cmd={c: b for b in bots for c in tuple(b.commands) + tuple(b.extra_commands)})
    return _R


def reload():
    """Forget the loaded registry (a test that adds a bot file)."""
    _R.clear()


# ---- lookups --------------------------------------------------------------------------------------------------------
def all_bots(retired=True):
    """Every Bot, in order (retired ones too unless retired=False)."""
    return tuple(b for b in _load()["all"] if retired or not b.retired)


def get(name):
    """The Bot called `name`, or None."""
    return _load()["by_name"].get(name)


def names(retired=True):
    return tuple(b.name for b in all_bots(retired))


def by_command(cmd):
    """The Bot a command ('/fc', '/racestats') belongs to, or None."""
    return _load()["by_cmd"].get(cmd)


def subs():
    """Every subaccount a bot trades from: '0', '1', ... (botstats.SUBS)."""
    return _load()["subs"]


def bots_on(sub):
    """The Bots with a pot in subaccount `sub`, in bot order."""
    out = []
    for b, _p in _load()["by_sub"].get(sub, ()):
        if b not in out:
            out.append(b)
    return tuple(out)


def owner(ticker, sub):
    """Which bot a settled market / position in subaccount `sub` is: a bot name or 'other'.  (botstats.owner)"""
    R = _load()
    series = str(ticker or "").split("-")[0]
    try:
        key = sub if sub in R["claim"] else "0"
    except TypeError:                                   # an unhashable sub: botstats' if-chain read it as main
        key = "0"
    for b, p in R["claim"][key]:
        if p.claims(series, ticker):
            return b.name
    return R["catch"][key] or OTHER


def bot_subs(name):
    """Every pot a bot trades from, its main one first (the FX taker: 5 then 4); ('0',) for a name no bot has."""
    b = get(name)
    if b is None:
        return ("0",)
    return tuple(p.sub for p in b.pots)


def cash_pool(sub):
    """The pool pot `sub` TRADES in, whose /portfolio/balance is read (botstats.SUB_POOL): its pool-only pot's pool
    when it has one (subaccount 3: the jump band's pool 2; 4: the FX pairs' pool 0), else its first bot's."""
    pots = _load()["by_sub"][sub]
    po = [p for _b, p in pots if p.pool_only]
    return (po[0] if po else pots[0][1]).pool


def fill_sub(name, ticker):
    """The pot one of a bot's fills is in (botstats.fill_sub): a pot that claims the ticker, else the bot's main pot."""
    b = get(name)
    series = str(ticker or "").split("-")[0]
    for p in b.pots:
        if p.claims is not None and p.sub != b.pots[0].sub and p.claims(series, ticker):
            return p.sub
    return b.pots[0].sub


def is_bot(name, cl):
    """Is this command line the LIVE copy of `name`? Paper arms of the same script are not.  (botstats.is_bot)"""
    t = toks(cl)
    b = get(name)
    if not any(re.search(r"(^|[\\/])" + re.escape(b.script) + "$", x) for x in t):
        return False
    return bool(b.is_live(t))


def version_claim(name, vname, rest):
    """botstats.version_of's ownership rule for one VERSIONS.md heading '# <vname> -- <rest>' (already past the
    INSTALLED / KILLED / infrastructure filters): the name to show for bot `name` (a combined heading's own parts
    joined with ' + ', else vname) or None when the heading is not this bot's."""
    bots = all_bots()
    low = (vname + " " + rest).lower()
    others = [b for b in bots if not b.version.default]
    defaults = [b for b in bots if b.version.default]
    # 2026-10-01: a heading that ships several bots at once names every bot; it belongs to each bot one of its names
    # is about
    parts = [n.strip() for n in vname.split("+")]
    if len(parts) > 1:
        own = {b.name: [n for n in parts if b.version.part(n)] for b in others}
        for d in defaults:
            if any(own.values()):
                own[d.name] = []
            elif not re.search(d.version.combined_not, low):
                own[d.name] = parts
            else:
                own[d.name] = []
        return " + ".join(own[name]) if own[name] else None
    flags = {b.name: bool(b.version.text(vname, low)) for b in others}
    for b in others:
        if b.version.override and vname.startswith(b.version.override):   # its own name wins over words about others
            flags = {k: (v if k == b.name else False) for k, v in flags.items()}
    if name in flags:
        return vname if flags[name] and not any(v for k, v in flags.items() if k != name) else None
    d = get(name)
    clean = bool(re.search(d.version.single_not, low))
    return vname if not (any(flags.values()) or clean) else None


def resolve(hook):
    """A hook given as 'module:function' (a lazy reference into a module that would make an import cycle), resolved
    on first use; a callable or None is returned as it is."""
    if hook is None or callable(hook):
        return hook
    mod, _, fn = str(hook).partition(":")
    return getattr(importlib.import_module(mod), fn)


# ---- the legacy tables, derived ------------------------------------------------------------------------------------
def legacy_spec():
    """botstats.SPEC."""
    out = {}
    for b in all_bots():
        d = {"label": b.label, "what": b.what, "sub": b.pots[0].sub}
        if len(b.pots) > 1:
            d["also"] = tuple(p.sub for p in b.pots[1:])
        d["script"], d["stop"] = b.script, b.stop_file
        if b.logs.glob:
            d["log_glob"] = b.logs.glob
        else:
            d["log"] = b.logs.path
        d["keepalive"] = b.keepalive
        out[b.name] = d
    return out


def _funds():
    what, who = {}, {}
    for s in subs():
        n = int(s)
        bypool = {}
        for b, p in _load()["by_sub"][s]:
            bypool.setdefault(p.pool, []).append((b, p))
        extra = EXTRA_POOLS.get(n, {})
        pools = sorted(set(bypool) | set(extra))
        if len(pools) > 1:
            what[n] = {ix: (" + ".join(p.what for _b, p in bypool[ix]) if ix in bypool else extra[ix]) for ix in pools}
            who[n] = {ix: tuple(b.name for b, _p in bypool.get(ix, ())) for ix in pools}
        else:
            what[n] = " + ".join(p.what for _b, p in bypool[pools[0]])
            who[n] = tuple(b.name for b, _p in bypool[pools[0]])
    return what, who


def _features():
    rows = [(f.pos, f.row()) for b in all_bots() for f in b.features] + list(EXTRA_FEATURES)
    rows.sort(key=lambda x: x[0])
    return tuple(r for _pos, r in rows)


def _feature_bot():
    live = [(b, f) for b in all_bots() for f in b.features if f.hides and f is b.features[0]]
    fam = [(b, f) for b in all_bots() for f in b.features if f.hides and f is not b.features[0]]
    return {(f.script, f.must): b.name for b, f in live + fam}


def _speed(skipped):
    sp = [b for b in all_bots() if b.speed is not None and bool(b.speed.skipped) == skipped]
    return sorted(sp, key=lambda b: b.speed.rank)


_TABLES = {
    # botstats
    "BOTS": lambda: names(),
    "SUBS": lambda: subs(),
    "SPEC": legacy_spec,
    "SUB_POOL": lambda: {s: cash_pool(s) for s in subs()},
    "POT_POOL_ONLY": lambda: {p.sub: p.pool for b in all_bots() for p in b.pots if p.pool_only},
    "POT_OWNER": lambda: {p.sub: b.name for b in all_bots() for p in b.pots if p.pool_only},
    "HALT_KINDS": lambda: {b.name: b.records.halts for b in all_bots()},
    "FILL_KINDS": lambda: {b.name: b.records.fills for b in all_bots()},
    "ALWAYS_SHOWN": lambda: tuple(b.name for b in all_bots() if b.always_shown),
    "PLAIN": lambda: list(PLAIN_BASE) + [w for b in all_bots() for w in b.records.refusal_words],
    "SUB_NAME": lambda: {s: ("main account" if s == "0" else "subaccount %s" % s) for s in subs()},
    # pinphone
    "BOT_CMDS": lambda: {c: b.name for b in all_bots() if b.page is None for c in b.commands},
    "BOT_CMD_OF": lambda: {b.name: b.command for b in all_bots()},
    "BOT_WORD": lambda: dict([(b.name, b.word) for b in all_bots()] + list(NOT_BOT_WORD.items())),
    "HELP_BOT_LINES": lambda: tuple((b.name, h) for b in all_bots() for h in b.help),
    "FUNDS_WHAT": lambda: _funds()[0],
    "FUNDS_BOTS": lambda: _funds()[1],
    "FUNDS_SIZE_BOTS": lambda: {int(s): tuple(b.name for b in bots_on(s) if b.funds_size) for s in subs()},
    "FUNDS_SHORT": lambda: {int(s): "+".join(p.short for _b, p in _load()["by_sub"][s] if p.short) for s in subs()},
    "FEATURES": _features,
    "FEATURE_BOT": _feature_bot,
    "SPEED_OTHERS": lambda: tuple((b.name, b.logs.path, b.speed.field, b.speed.kind) for b in _speed(False)),
    "SPEED_SKIPPED": lambda: tuple((b.name, b.speed.skipped) for b in _speed(True)),
    "SPEED_LABEL": lambda: {b.name: b.short for b in _speed(False) + _speed(True)},
    "PAGE_FOOTER": lambda: {b.name: b.page_footer for b in all_bots() if b.page_footer},
    "LADDER_GOAL_PCT": lambda: get("ladder").goal_pct,
    "UNIT": lambda: {b.name: b.unit for b in all_bots()},
    # tgcharts
    "BOT_SHORT": lambda: dict([(b.name, b.short) for b in all_bots()] + list(NOT_BOT_SHORT.items())),
    "BOT_COLOUR": lambda: dict([(b.name, b.colour) for b in all_bots()] + list(NOT_BOT_COLOUR.items())),
    "BOT_ORDER": lambda: names() + (EARLIER, OTHER),
    # the one-bot pages' commands first, then the bots with a page of their own (the race): tgcharts' order
    "CMD_KIND_BOTS": lambda: {c: "bot:" + b.name for b in sorted(all_bots(), key=lambda b: b.page is not None)
                              for c in tuple(b.commands) + tuple(b.extra_commands)},
    "ACCOUNT_NAME": lambda: {s: ("Main account" if s == "0" else "Subaccount %s" % s) for s in subs()},
    "POT_WHAT": lambda: dict(sorted((p.sub, p.part) for b in all_bots() for p in b.pots if p.part)),
}


def table(name):
    """A derived legacy table, freshly built (a new object every call)."""
    return _TABLES[name]()


def __getattr__(name):                  # PEP 562: bots.BOTS, bots.SUB_POOL, ... built on first access
    if name in _TABLES:
        return _TABLES[name]()
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
