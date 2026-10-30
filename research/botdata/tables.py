"""tables.py -- the per-bot tables botstats always had, DERIVED from the registry (research/bots) once, and the rules
that read them: SPEC, BOTS, SUBS, SUB_POOL, POT_POOL_ONLY, POT_OWNER, SUB_NAME, HALT_KINDS, FILL_KINDS, PIN_HOURLY,
FX_PAIRS, JB_SERIES; bot_subs, sub_name, owner (which bot a settled market is), pot_groups (all_bots' cash pots).

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata). These
are the SAME objects botstats re-exports: tests change SUB_POOL / POT_POOL_ONLY in place (the 10-04 weather world) and
every reader in botdata reads them through this module at call time.
"""
import bots as _reg
from bots import fx as _b_fx, jumpband as _b_jb, pin as _b_pin


POOL = 2                        # Kalshi's crypto & commodities cash pool, where pots 0-2 trade
# v-tg-rebuild step 3 (2026-10-30): every per-bot table below is DERIVED from the registry (research/bots, one file a
# bot), no longer kept here by hand; bots/tests/test_registry.py proved each equal to the hand-kept table it replaces.
# Adding a bot = one file in research/bots. The facts and their history (why sub 3 is two pots, why sub 4's pool 0 only
# is the FX taker's, ...) are written next to them in those files. SUB_POOL / POT_POOL_ONLY are fresh dicts: tests
# change them in place (the 10-04 weather world) and every function here reads these same objects.
BOTS = _reg.names()                                      # ("pin", "race", "forecaster", "ladder", "weather", "fx", "jumpband")
SUBS = _reg.subs()                                       # ("0", "1", "2", "3", "4", "5")
# the pool each pot TRADES in, whose cash /portfolio/balance is asked for (bots.cash_pool: a pool-only pot's pool, else
# its first bot's): {"0": 2, "1": 2, "2": 2, "3": 2, "4": 0, "5": 2}
SUB_POOL = _reg.table("SUB_POOL")
FX_PAIRS = _b_fx.FX_PAIRS
# 2026-10-26: for a BOT's pot (its % of bank, its chart, the per-pot check) a pool-only pot is its POOL only -- sub 4 is
# the FX taker's pool 0, sub 3 the jump band's pool 2 -- and only its owner's bets: {"4": 0, "3": 2}, {"4": "fx", "3": "jumpband"}
POT_POOL_ONLY = _reg.table("POT_POOL_ONLY")
POT_OWNER = _reg.table("POT_OWNER")
JB_SERIES = _b_jb.JB_SERIES

PIN_HOURLY = _b_pin.PIN_HOURLY                  # the hourly ladders pinrun knows (bots/pin.py)
SPEC = _reg.legacy_spec()                       # {bot: label, what, sub, (also), script, stop, log | log_glob, keepalive}
SUB_NAME = _reg.table("SUB_NAME")


def bot_subs(name):
    """Every pot a bot trades from, its main one first (the FX taker: 5 then 4); ('0',) for a name no bot has."""
    return _reg.bot_subs(name)


def sub_name(sub):
    """'main account' / 'subaccount 5 + subaccount 4' / 'all pots' for one pot, a tuple of pots, or None."""
    if sub is None:
        return "all pots"
    if isinstance(sub, tuple):
        return " + ".join(SUB_NAME[s] for s in sub)
    return SUB_NAME[sub]

# what counts as stopped in each bot's own log (bots: Records.halts)
HALT_KINDS = _reg.table("HALT_KINDS")


# ---- which bot a settlement belongs to --------------------------------------
def owner(ticker, sub):
    """Which bot a settled market / position in subaccount `sub` is: a bot name or 'other'. v-tg-rebuild step 3
    (2026-10-30): the registry's rule (bots.owner) -- within a sub the pots that CLAIM tickers in priority order (sub 0:
    the race, then the pin bot; sub 3: the jump band; sub 4: the FX pairs), then the sub's catch-all pot, else 'other'."""
    return _reg.owner(ticker, sub)


# which records of each bot's own log are fills (botdata/activity.py: fill_of, fills_since)
FILL_KINDS = _reg.table("FILL_KINDS")          # bots: Records.fills (v-tg-rebuild step 3)


def pot_groups():
    """[(key, [bots])]: the cash pots all_bots names, one a subaccount that is some bot's MAIN pot -- 'main' for the main
    account, else its pool-only pot's owner (sub 3: the jump band), else its one bot -- with the bots whose main pot it
    is (the owner first, then bot order). A bot's second pot (the FX taker's sub 4) is in its main pot's group.
    v-tg-rebuild step 3 (2026-10-30): derived from the registry, was a hand-kept map. In subaccount order:
    main [pin, race], ladder, forecaster, jumpband [jumpband, weather], fx."""
    groups = {}
    for b in BOTS:
        groups.setdefault(SPEC[b]["sub"], []).append(b)
    out = []
    for sub in SUBS:
        if sub not in groups:
            continue
        names = groups[sub]
        key = "main" if sub == "0" else (POT_OWNER.get(sub) if POT_OWNER.get(sub) in names else names[0])
        out.append((key, ([key] if key in names else []) + [n for n in names if n != key]))
    return out
