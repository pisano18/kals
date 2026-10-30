"""/server -- the machine, the time to Kalshi, every pot's money (botstats' cache, no Kalshi read) and the AWS bill;
`/server help` (or ?, aws, setup): the console steps that connect the AWS cost.

v-tg-rebuild step 9 (2026-10-30, lane D5): Phone.text_server as a command; its page code (SERVER_HELP, server_html and
its parts) MOVED VERBATIM out of research/pinphone.py, which re-exports every name here. The only edits: imports instead
of pinphone's globals (the number words from phone.commands.speed, dollars / _f from botdata.fmt, funds_short from
/funds' page, the AWS constants from aws.py).
"""
import time
import traceback

from botdata.fmt import _f, dollars
from phone.html import Html, esc, i_, pre, table
from phone.log import log
from phone.commands.funds.page import funds_short
from phone.commands.speed import (SERVER_SINCE_EPOCH, SPEED_HOME_DAYS, _et_at, _gb, _ms, _pct0, _span_words,
                                  _speed_win, pct1, pct_of, pin_speed_orders, ret, speed_stats)
from phone.commands.server.aws import (AWS_AZ, AWS_BILLED_FROM_EPOCH, AWS_BUDGET_USD, AWS_DISK_GB, AWS_EC2_HOURLY,
                                       AWS_ELASTIC_IP, AWS_INSTANCE_NAME, AWS_INSTANCE_TYPE, AWS_SERVICE_SHORT,
                                       aws_cost, aws_estimate)
from phone.commands.server.machine import KALSHI_HOST

SERVER_WARN_CPU, SERVER_WARN_MEM, SERVER_WARN_DISK_GB = 90.0, 90, 8.0


SERVER_HELP = Html("""🖥 <b>/server help: connect the AWS cost</b> (once, about 3 minutes, in the AWS console)

/server reads this month's spending from AWS itself, with no stored keys: the server gets a read-only role, and the phone link asks the server's own metadata service for short-lived keys. Until then it shows the price-list estimate.

<b>1. The policy</b>: IAM → Policies → Create policy → JSON, replace everything with:
<code>{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["budgets:ViewBudget","ce:GetCostAndUsage"],"Resource":"*"}]}</code>
→ Next → Policy name <code>kals-server-billing-read</code> → Create policy.
<b>2. The role</b>: IAM → Roles → Create role → Trusted entity type: AWS service, Use case: EC2 → Next → tick <code>kals-server-billing-read</code> → Next → Role name <code>kals-server-billing</code> → Create role.
<b>3. Give it to the server</b>: EC2 → Instances → tick <code>kals-bot</code> → Actions → Security → Modify IAM role → pick <code>kals-server-billing</code> → Update IAM role.

Within 5 minutes /server shows "This month so far" from AWS. Nothing restarts.
If it says access denied: sign in as the root user → your name (top right) → Account → "IAM user and role access to Billing information" → Edit → Activate. If Cost Explorer says it is not enabled: open Billing → Cost Explorer once (AWS turns it on; its numbers show within a day).

What the role can do: read the budget and the cost totals, nothing else. It cannot start, stop or change anything, and the server holds no AWS key on disk.
<i>budgets:ViewBudget is the permission behind AWS's DescribeBudgets call (there is no separate budgets:DescribeBudgets permission). DescribeBudgets is free and is read at most once an hour; Cost Explorer costs $0.01 a read, so it is read at most every 6 hours and only when /server is asked (at most about $1.20 a month).</i>""")


def _server_pots_lines(pots, now, active=None):
    """/server's funds: every pot from botstats' cache (cached_pots: the last read /bots, /funds or a chart made)."""
    if not isinstance(pots, dict) or pots.get("err") or not pots.get("pots"):
        return ["💰 <b>Funds</b>: botstats' cache could not be read%s. /funds reads every account."
                % ((" (%s)" % esc(pots.get("err"))) if isinstance(pots, dict) and pots.get("err") else "")], None
    ps = pots["pots"]
    total = pots.get("total")
    L = ["💰 <b>Funds: all pots %s</b> <i>(Kalshi, as of %s, %s ago: the last read /bots, /funds or a chart made; "
         "nothing is read here)</i>" % (esc(dollars(total)) if total is not None else "?", esc(_et_at(pots.get("t"))),
                                        esc(_span_words(now - pots["t"])) if pots.get("t") else "?")]
    rows = [("Pot", "Total", "Share", "Bets")]
    notes = []
    for sub in sorted(ps, key=lambda s: int(s) if str(s).isdigit() else 99):
        p = ps[sub]
        name = (funds_short(int(sub), active) or "pot %s" % sub) if str(sub).isdigit() else str(sub)
        v = p.get("value")
        if v is None:
            notes.append("%s: %s%s" % (name, p.get("why") or "not read",
                                       ("; its cash alone %s" % dollars(p["cash"])) if p.get("cash") is not None else ""))
        rows.append((name, "{:,.2f}".format(v) if v is not None else "?",
                     pct_of(v, total) if v is not None and total else "-",
                     "{:,.2f}".format(p["open"]) if p.get("open") else ("0" if p.get("open") == 0 else "?")))
    L.append(pre(table(rows)))
    for x in notes:
        L.append("⚠️ " + esc(x))
    L.append(i_("Total = cash in every pool + what the open bets cost; Share = of all pots. /funds reads them fresh, "
                "with each pool, bet sizes and the last 7 days."))
    return L, total


def _server_aws_lines(aws, est, total, now):
    L = ["☁️ <b>AWS cost</b>"]

    def of_pots(x):
        r = ret(x, total, 2) if total else ""
        return (" = %s of all pots" % r.lstrip("+")) if r else ""
    b = None
    if aws.get("connected") and aws.get("budget"):
        rows = aws["budget"]
        b = next((r for r in rows if r["type"] == "COST" and r["period"] == "MONTHLY"), rows[0])
    if not aws.get("connected"):
        L.append("AWS cost: <b>not connected yet</b> (needs the read-only billing role on the server, see "
                 "<code>/server help</code>)")
        if aws.get("why"):
            L.append(i_("(%s)" % aws["why"]))
    else:
        if b is not None:
            lim = b["limit"]
            L.append("This month so far: <b>%s</b>%s%s" % (
                esc(dollars(b["actual"])), (" of the %s budget (%s)" % (esc(dollars(lim)), pct_of(b["actual"], lim)))
                if lim and b["actual"] is not None else "", esc(of_pots(b["actual"])) if b["actual"] is not None else ""))
            L.append("AWS's forecast for %s: %s" % (
                esc(est["month_name"]), ("<b>%s</b>%s" % (esc(dollars(b["forecast"])), esc(of_pots(b["forecast"]))))
                if b["forecast"] is not None else "none yet (AWS needs some weeks of history first)"))
            L.append(i_("AWS Budgets, budget '%s'%s; AWS updates it a few times a day%s" % (
                b["name"] or "?", (", as of %s" % _et_at(b["updated"])) if b["updated"] else "",
                (" · %d budgets on the account" % len(aws["budget"])) if len(aws["budget"]) > 1 else "")))
        elif aws.get("budget") == []:
            L.append("AWS Budgets: no budget on the account yet.")
        if aws.get("budget_err"):
            L.append("⚠️ Budgets read: %s" % esc(aws["budget_err"]))
        ce = aws.get("ce")
        if ce:
            yday = time.strftime("%Y-%m-%d", time.gmtime(now - 86400))
            top = sorted(ce["services"].items(), key=lambda kv: -kv[1])
            L.append("Cost Explorer: this month <b>%s</b>%s · yesterday (UTC) %s%s" % (
                esc(dollars(ce["month"])), esc(of_pots(ce["month"])), esc(dollars(ce["days"].get(yday, 0.0))),
                " · AWS's figures are still estimated" if ce.get("estimated") else ""))
            if top:
                L.append("By service: %s" % esc(", ".join("%s %s" % (AWS_SERVICE_SHORT.get(k, k), dollars(v))
                                                         for k, v in top[:5] if abs(v) >= 0.005) or "nothing yet"))
            if aws.get("ce_t"):
                L.append(i_("Cost Explorer read %s ($0.01 a read: at most every 6 hours)" % _et_at(aws["ce_t"])))
        if aws.get("ce_err"):
            L.append("⚠️ Cost Explorer read: %s" % esc(aws["ce_err"]))
    L.append("Estimate from the price list: about <b>%s a month</b> (%s a day)%s: Windows %s %s an hour (%s), %d GB "
             "disk %s, public IPv4 %s; data out not counted (small; the first 100 GB a month are free)." % (
                 esc(dollars(est["month"])), esc(dollars(est["day"])), esc(of_pots(est["month"])), AWS_INSTANCE_TYPE,
                 esc(dollars(AWS_EC2_HOURLY)), esc(dollars(est["ec2_month"])), AWS_DISK_GB, esc(dollars(est["disk_month"])),
                 esc(dollars(est["ipv4_month"]))))
    L.append("%s so far, since %s: about %s · all of %s: about %s (estimates) · budget %s a month." % (
        esc(est["month_name"]), esc(_et_at(est["since"])) + (" (the server started)" if est["since"] == AWS_BILLED_FROM_EPOCH
                                                            else ""),
        esc(dollars(est["so_far"])), esc(est["month_name"]), esc(dollars(est["this_month"])),
        esc(dollars(b["limit"] if b is not None and b.get("limit") else AWS_BUDGET_USD))))
    return L


def server_html(m, ping, pots, aws, est, now, pin_home=None, pin_srv=None, active=None):
    """/server's screen: the machine (machine_read), the time to Kalshi (kalshi_ping), every pot's money (botstats'
    cache), the AWS bill (aws_cost, aws_estimate). Each part says what it could not read; none stops the others."""
    best = min(ping["ms"]) if ping and ping.get("ms") else None
    used = (m["mem_total"] - m["mem_avail"]) if m.get("mem_total") is not None and m.get("mem_avail") is not None else None
    head = ["CPU %s" % _pct0(m.get("cpu")), "memory %s used" % _pct0(m.get("mem_load")),
            "disk %s free" % _gb(m.get("disk_free")), "Kalshi %s" % (_ms(best) if best is not None else "?")]
    L = ["🖥 <b>SERVER: %s</b>" % esc(" · ".join(head)),
         i_("AWS EC2 in Ohio (%s) · %s: 2 vCPU, 4 GB, Windows Server 2022, %d GB disk · %s, %s · this machine: %s · %s"
            % (AWS_AZ, AWS_INSTANCE_TYPE, AWS_DISK_GB, AWS_INSTANCE_NAME, AWS_ELASTIC_IP, m.get("host") or "?",
               _et_at(now)))]
    warn = []
    if m.get("cpu") is not None and m["cpu"] >= SERVER_WARN_CPU:
        warn.append("CPU is busy: %s" % _pct0(m["cpu"]))
    if m.get("mem_load") is not None and m["mem_load"] >= SERVER_WARN_MEM:
        warn.append("memory nearly full: %d%% used" % m["mem_load"])
    if m.get("disk_free") is not None and m["disk_free"] / 1e9 < SERVER_WARN_DISK_GB:
        warn.append("disk under %d GB free" % SERVER_WARN_DISK_GB)
    if m.get("reboot"):
        warn.append("%s waits for a restart" % (m.get("reboot_why") or "Windows"))
    if ping and ping.get("err"):
        warn.append("Kalshi: %s" % ping["err"])
    for w in warn:
        L.append("⚠️ <b>%s</b>" % esc(w))
    L.append("")
    L.append("⚙️ <b>Machine</b>")
    rows = [("CPU now", "%s (%s cores, %.1f s)" % (_pct0(m.get("cpu")), m.get("ncpu") or "?", _f(m.get("sample_s")))),
            ("  python", "%s · %s" % (_pct0(m.get("py_cpu")), ("%d process%s" % (m["py_n"], "" if m["py_n"] == 1 else "es"))
                                      if m.get("py_n") is not None else "? processes")),
            ("Memory", "%s of %s (%s)" % (_gb(used), _gb(m.get("mem_total")), _pct0(m.get("mem_load")))),
            ("  free", _gb(m.get("mem_avail"))),
            ("  python", _gb(m.get("py_mem"))),
            ("Committed", "%s of %s" % (_gb(m.get("commit")), _gb(m.get("commit_limit")))),
            ("Disk C:", "%s free of %s" % (_gb(m.get("disk_free")), _gb(m.get("disk_total"), 0))),
            ("Up", _span_words(m["uptime_s"]) if m.get("uptime_s") is not None else "?")]
    L.append(pre(table(rows, "ll")))
    boot = (now - m["uptime_s"]) if m.get("uptime_s") is not None else None
    L.append("Last boot: %s · Windows Update: %s" % (
        esc(_et_at(boot)), "<b>a restart is waiting</b> (%s)" % esc(m.get("reboot_why") or "?") if m.get("reboot")
        else ("no restart waiting" if m.get("reboot") is False else "could not tell (%s)" % esc(m.get("reboot_why") or "?"))))
    if m.get("errs"):
        L.append(i_("Could not read: %s" % "; ".join(m["errs"])))
    L.append(i_("python = every python process (the bots, the recorders and this phone link): its share of the whole "
                "machine and the memory it holds."))
    L.append("")
    if ping and ping.get("ms"):
        L.append("⚡ <b>Kalshi: %s</b> to connect (best of %d: %s; name lookup %s), checked %s" % (
            esc(_ms(best)), len(ping["ms"]), esc(", ".join(_ms(x) for x in ping["ms"])), esc(_ms(ping.get("dns_ms"))),
            esc(_et_at(ping.get("t"), False))))
    else:
        L.append("⚡ <b>Kalshi: could not connect</b> (%s)" % esc((ping or {}).get("err") or "not checked"))
    if pin_srv and pin_srv.get("lat_n"):
        L.append("The pin bot's own orders here: median <b>%s</b> send to answer, %s got nothing%s · /speed" % (
            esc(_ms(pin_srv["med_ms"])), pct1(pin_srv["zero"], pin_srv["n"]),
            (" (home: %s, %s)" % (esc(_ms(pin_home["med_ms"])), pct1(pin_home["zero"], pin_home["n"])))
            if pin_home and pin_home.get("lat_n") else ""))
    L.append(i_("A bare TCP connect to %s:443 (no request is sent, so no Kalshi limit is used), at most once a minute."
                % KALSHI_HOST))
    L.append("")
    fl, total = _server_pots_lines(pots, now, active)
    L += fl
    L.append("")
    L += _server_aws_lines(aws or {}, est, total, now)
    L.append("")
    L.append(i_("/speed: the bots' orders, server against home · /funds: every account read fresh · /server help: "
                "connect the AWS cost"))
    return Html("\n".join(L))


# ---- the command (Phone.text_server) ------------------------------------------------------------------------------------
HELP_ARGS = ("help", "?", "aws", "setup")


def load(ctx):
    """Phone.text_server's reads, in its order: the clock, the machine, the ping, the pots (botstats' cache; a failure is
    logged and named on the page), the AWS bill, the pin bot's orders home and here, the active bots. `/server help`
    reads nothing. Returns None for the help page."""
    if ctx.arg.strip().lower() in HELP_ARGS:
        return None
    now = ctx.now()
    m = ctx.machine()
    ping = ctx.ping()
    try:
        pots = ctx.pots()
    except Exception as e:                              # noqa: BLE001
        log(traceback.format_exc())
        pots = {"err": str(e)[:120]}
    aws = aws_cost(now, http=ctx.aws_http)
    pins = pin_speed_orders(ctx.ledger.orders)
    est = aws_estimate(now)
    home = speed_stats(_speed_win(pins, SERVER_SINCE_EPOCH - SPEED_HOME_DAYS * 86400, SERVER_SINCE_EPOCH))
    srv = speed_stats(_speed_win(pins, SERVER_SINCE_EPOCH, now + 1))
    return {"m": m, "ping": ping, "pots": pots, "aws": aws, "est": est, "now": now, "home": home, "srv": srv,
            "active": ctx.active()}


def render(d):
    if d is None:
        return SERVER_HELP
    return server_html(d["m"], d["ping"], d["pots"], d["aws"], d["est"], d["now"], d["home"], d["srv"],
                       active=d["active"])


def fail(e):
    return ("Could not build /server: %s\nEverything else still works -- /funds has every account's money."
            % str(e)[:200])
