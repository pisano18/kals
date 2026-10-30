"""/server -- the server's CPU, memory, disk, uptime and Windows restarts, the time to Kalshi, every pot's money and the
AWS bill this month; `/server help` (? aws setup): connect the AWS cost.

v-tg-rebuild step 9 (2026-10-30, lane D5): Phone.text_server as a command package -- machine.py (Windows readings, the
Kalshi ping), aws.py (IMDSv2 + SigV4: Budgets and Cost Explorer; the only command file with urllib), page.py (the
reads in Phone.text_server's order, and the page). Byte-identical to the old method (golden shadow, every world).
"""
from phone.command import Command, declare
from phone.commands.server.page import fail, load, render

COMMAND = declare(Command(
    names=("/server",), section="server", order=20,
    help_line="/server: the server's CPU, memory, disk, uptime and Windows restarts, the time to Kalshi, every pot's "
              "money, and the AWS bill this month (<code>/server help</code>: connect the AWS cost)",
    chart=None, load=load, render=render, fail=fail,
    examples=("/server help", "/server ?", "/server aws", "/server setup")))
