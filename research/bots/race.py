"""The coin race: which coin gains most in 15 minutes, main account (subaccount 0). Every fact copied verbatim from
botstats.py / pinphone.py / tgcharts.py at 8a9c5e1 (v-tg-rebuild step 1, 2026-10-30). Paused since 10-27 22:02 ET by
its stop file (it keeps running and refuses every trade), so v-tg-active hides it; nothing here changes that."""
import re

from bots.spec import Bot, Feature, Logs, Pot, Records, Speed, VersionRule, live_flag, opt
from botdata.fmt import cents as _c, num as _num, usd


def _claims(series, ticker):
    """botstats.owner, subaccount 0 first: the race's series and every KXCRYPTOLEAD* one."""
    import pinday
    return series in pinday.RACE or series.startswith("KXCRYPTOLEAD")


def settings_race(start, cl):
    """(botstats.settings_race, verbatim)"""
    s = {}
    rails = (start or {}).get("live_rails") or {}
    src = cl or " ".join((start or {}).get("argv") or [])
    for flag, key in (("--max-contracts", "contracts_per_bet"), ("--max-stake", "max_in_play"),
                      ("--live-tau-max", "buys_within_s"), ("--live-min-price", "min_price"),
                      ("--live-max-legs", "max_bets_per_race"), ("--live-confirm", "confirm_s")):
        v = _num(opt(src, flag))
        if v is not None:
            s[key] = v
    s["stop_on_first_loss"] = bool(rails.get("stop_on_loss", (start or {}).get("stop_on_loss")))
    # v-race40 (2026-09-30): --live-max-losses N > 1 stops for the rest of the ET day after N losing races
    ml = _num(opt(src, "--live-max-losses"))
    if ml is not None and ml > 1:
        s["max_losses_per_day"] = ml
        s["stop_on_first_loss"] = False
    if start and start.get("version"):
        s["code_version"] = start["version"]
    bits = []
    if "contracts_per_bet" in s:
        bits.append("%g contracts a bet" % s["contracts_per_bet"])
    if "min_price" in s or "buys_within_s" in s:
        bits.append("buys at %s or more with %g s or less left" % (_c(s.get("min_price")), s.get("buys_within_s", 0)))
    if "max_in_play" in s:
        bits.append("at most %s in play" % usd(s["max_in_play"]).lstrip("+"))
    if "max_bets_per_race" in s:
        bits.append("up to %g bets a race" % s["max_bets_per_race"])
    if s.get("max_losses_per_day"):
        bits.append("stops for the rest of the ET day after %g losing races" % s["max_losses_per_day"])
    elif s["stop_on_first_loss"]:
        bits.append("stops after its first loss")
    return s, "; ".join(bits)


def settings(si):
    return settings_race(si.start, si.cmdline)


def activity(k, r, out, why, st):
    """botstats.activity's race branch (verbatim)."""
    import pinledger
    if k == "live_order":
        out["sent"] += 1
        f = pinledger.money(r, "filled")
        out["filled" if f > 0 else "not_filled"] += 1
        out["contracts_filled"] += f
    elif k == "live_refused":
        out["refused"] += 1
        w = r.get("why")
        # the race writes numbers and coins into its reasons; group them by their shape
        g = re.sub(r"\d+(\.\d+)?", "N", str((w[0] if isinstance(w, list) and w else w) or "?"))
        g = re.sub(r"(YES|NO) on [A-Z]+ ", r"\1 on COIN ", g)[:80]
        why[g] = why.get(g, 0) + 1


# v-tg-rebuild step 5 (2026-10-30): /funds' bet-size reader, moved verbatim from pinphone.funds_sizes (where it was a
# closure over its `when` and `results`; spec.SizeIn hands it those and the phone's readers).
def size_words(si):
    """/funds: the coin race's bet size now -- its start record's rails, or (v-race-snowball) its newest bank_size."""
    import os
    path = os.path.join(si.results, "pinracepenny-live.jsonl")
    r = si.last_record(path, ("start",))
    lr = (r or {}).get("live_rails") or {}
    if si.num(lr.get("max_contracts")) is None:
        return None
    # v-race-snowball (2026-10-11): a start record with bank_sizing takes its size from the bank; the
    # size in force is the newest bank_size record after that start, not the start-up live_rails.
    bsz = r.get("bank_sizing") or {}
    if si.num(bsz.get("contracts_per_bank")) and si.num(bsz.get("stake_per_bank")):
        sz = si.last_record(path, ("bank_size",))
        if sz and (si.epoch(sz.get("t")) or 0) >= (si.epoch(r.get("t")) or 0) \
                and si.num(sz.get("contracts")) is not None and si.num(sz.get("bank")):
            return "coin race %g contracts a leg, at most %s in play (%.2f%% of a %s bank; sized %s, grows " \
                   "with the bank)" % (si.num(sz["contracts"]), si.usd2(sz.get("stake")),
                                       100.0 * si.num(bsz["stake_per_bank"]), si.usd2(sz["bank"]), si.when(sz))
        return "coin race: bets grow with the bank (%.2f contracts per $100, %.2f%% of it in play); no size " \
               "read logged since its start %s" % (100.0 * si.num(bsz["contracts_per_bank"]),
                                                  100.0 * si.num(bsz["stake_per_bank"]), si.when(r))
    return "coin race %g contracts a bet%s (set at its start %s)" % (
        si.num(lr["max_contracts"]),
        (", at most %s in play" % si.usd2(lr["max_stake"]).replace(".00", "")) if si.num(lr.get("max_stake")) else "",
        si.when(r))


BOT = Bot(
    name="race", label="Coin race", short="Coin race", word="coin race",
    what="which coin gains most in 15 minutes",
    strategy=(
        "Bets on Kalshi's 15-minute coin race: which of BTC ETH SOL XRP and HYPE gains most in the quarter-hour.",
        "In the last 30 seconds it buys the leader's YES or a trailer's NO at 90c or more when its model, checked"
        " 5 times, says the lead is safe.",
        "It loses on a late overtake or a tie (a tie pays 50c).",
        "About 1.9 contracts per $100 of bank, at most 20 and $40 a bet; it halts after 2 losses.",
    ),
    help=("/race — the live coin race right now (real money; its bets grow with the bank), its last 10 races, and its "
          "money by window",
          "/racestats — the coin race record, and the paper arms on the same races"),
    command="/race", commands=("/race",), page="race", extra_commands=("/racestats",),
    pots=(Pot("0", 2, claims=_claims, priority=10, what="coin race", short="race"),),
    script="pinracearm.py", is_live=live_flag("--live", deny=("--paper-live",)), stop_file="pinracepenny.stop",
    logs=Logs(path="pinracepenny-live.jsonl", start_rule="live"),
    records=Records(fills=("live_order",), fill_qty="filled", halts=("live_halt",)),
    settings=settings,
    version=VersionRule(part=lambda n: n.startswith("v-race"),
                        text=lambda vname, low: vname.startswith("v-race") or bool(re.search(r"coin.?race", low))),
    colour="#ef7f1a",          # orange, yellower than the 7-day dashes' so it never reads as a loss
    order=2,
    # 2026-10-18: was None ("nothing restarts the live one"), stale since the 09-30 scale-up put the
    # live race in boot_all.ps1's keep-alive list (section 3e, 'coin race (LIVE, main account)').
    keepalive="boot_all.ps1 (every 10 min) restarts it unless the stop file is there",
    unit="leg",
    activity=activity,
    funds_size=size_words,
    ledger_book="coin race",        # pinday.book_of's name for its markets (/stats' lifetime by bot)
    speed=Speed(rank=3, field="kind", kind="live_order"),
    features=(
        Feature("pinracearm.py", "--live", None, "Coin race (LIVE, main account)",
                "Bets real money on which coin finishes a 15-minute race ahead, with the bet growing with the bank.",
                pos=1, hides=True),
        Feature("pinracearm.py", None, "--live", "Coin race paper arms",
                "Watch the same coin races on paper with other entry rules; no orders.", pos=8, hides=True),
    ),
)
