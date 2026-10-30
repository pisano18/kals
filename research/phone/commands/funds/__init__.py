"""/funds (/bank /accounts) -- the money in every Kalshi account and subaccount: cash by pool, open bets, the total, what
runs there, each bot's bet size now and each account's last 7 ET days; the grand total first.

v-tg-rebuild step 9 (2026-10-30, lane D4): Phone.text_funds as a command package -- read.py reads (Kalshi through the
GET-only getter, the bots' logs, botstats' settlement rows), page.py words it. Byte-identical to the old method (golden
shadow, every world).
"""
from phone.command import Command, declare
from phone.commands.funds.read import load
from phone.commands.funds.page import fail, render

COMMAND = declare(Command(
    names=("/funds", "/bank", "/accounts"), section="money", order=40,
    # pinphone.HELP_TEXT's line verbatim; {funds_split} is filled by help_text(active) (" (main bot and race apart)" while
    # the main account is shared) -- the router's /help does the same (step 10)
    help_line="/funds (or /bank, /accounts) — the money in every account and subaccount: cash, open bets, total, what "
              "runs there, bet size now, each account's last 7 days{funds_split}, and the grand total",
    chart="funds", load=load, render=render, fail=fail))
