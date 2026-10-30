"""/speed -- did the move to the AWS server win orders the laptop used to lose? The pin bot's orders home against
server, what speed added in $ (an estimate), and a line for each other bot whose log allows it. No Kalshi read.

v-tg-rebuild step 9 (2026-10-30, lane D5): Phone.text_speed as a command module, its code MOVED VERBATIM out of
research/pinphone.py (the /speed half of the "/speed and /server" section, the short number words /server shares, and
tail_rows), which re-exports every name here. The only edits: imports instead of pinphone's globals (usd, dollars, _f,
_cnt, _nof, _fnum from botdata.fmt; the HTML helpers from phone.html). Rebuild step 12: the five tiny formatters it had
copied (dot, pct_of, pct1, ret, _of100) are botdata.fmt's now (the same code), imported here under the same names.
"""
import calendar
import json
import os
import time

import bots as _bots
import pindesk
import pinday
from botdata.fmt import _f, cnt as _cnt, dollars, nof as _nof, num as _fnum, usd
from botdata.fmt import dot, of100 as _of100, pct1, pct_of, ret              # noqa: F401  (step 12: merged into botdata.fmt)
from phone.command import Command, declare
from phone.html import Html, details, elines, esc, i_, pre, table


# ===========================================================================
# /speed and /server (2026-10-27): the bots moved from the home laptop to an AWS server in Ohio.
#
# THE OPERATOR, 2026-10-27: "Yes add speed" (to: a /speed screen "that shows this, server against home, with the
# dollars") and "Yes add server command. If possible add server funds and cost and spending too to that".
#
# /speed splits the bots' OWN order logs at SERVER_SINCE: home = the SPEED_HOME_DAYS days before it (the laptop),
# server = since. The pin bot's orders are the Ledger's (every pinrun-live log, already in this process: read once,
# then only the new bytes); its money per filled contract comes from the `settled` rows of the pin logs written
# since the move; the FX taker, forecaster and coin race from their own logs, read once whole and then only what was
# added (tail_rows). No Kalshi read anywhere, so it answers in well under a second.
#
# /server reads the machine through Windows itself (ctypes: kernel32; winreg for a waiting restart; psutil is not
# installed and none is added), times a bare TCP connect to Kalshi (the handshake only: no request is sent, so no
# Kalshi rate limit is touched), shows every pot's money from botstats' cache (the last read /bots, /funds or a chart
# made: no read of its own) and the AWS bill from AWS's own Budgets and Cost Explorer APIs, signed here (SigV4 with
# hashlib and hmac) with the short-lived keys of the instance's IAM role from the EC2 metadata service: no stored
# keys, no boto3. Every reading is cached, has a short timeout, and none raises into the screen.
# ===========================================================================
# THE MOVE: the first live bot started on the server at this instant (00:20:52 ET, 10-27). Before it every bot and
# this phone link ran on the operator's home laptop; from it on, on the EC2 server. /speed's "server" is at or after
# it, "home" the SPEED_HOME_DAYS days before it.
SERVER_SINCE = "2026-10-27T04:20:52Z"
SERVER_SINCE_EPOCH = calendar.timegm(time.strptime(SERVER_SINCE, "%Y-%m-%dT%H:%M:%SZ"))
SPEED_HOME_DAYS = 14
SPEED_MIN_ORDERS = 50           # fewer pin orders than this on the server: "too early to tell"
SPEED_MIN_OTHER = 20            # ... and for another bot's line
# the other bots whose own logs say, per order, what was asked and what was got: (bot, log, the field that names a
# record, the order record's name). Only orders Kalshi took count (a refusal, e.g. 'market not found', is no race).
# v-tg-rebuild step 5 (2026-10-30): from the registry (each bot's Bot.speed: its order record, or why it is skipped;
# its log is its Logs.path; its name on the page its Bot.short)
SPEED_OTHERS = _bots.SPEED_OTHERS
SPEED_SKIPPED = _bots.SPEED_SKIPPED
SPEED_LABEL = _bots.SPEED_LABEL


def _et_at(epoch, with_day=True):
    """'Oct 27 12:20 AM ET' (or '12:20 AM ET') -- botstats.et_clock's style, kept here so a broken botstats costs only
    the pages that need it."""
    if epoch is None:
        return "?"
    tm = time.gmtime(float(epoch) + pinday.et_offset(float(epoch)))
    hm_ = "%d:%02d %s" % (tm.tm_hour % 12 or 12, tm.tm_min, "AM" if tm.tm_hour < 12 else "PM")
    return ("%s %d %s ET" % (time.strftime("%b", tm), tm.tm_mday, hm_)) if with_day else hm_ + " ET"


def _span_words(s):
    """'3 days 4 h' / '1 h 42 min' / '12 min' / '40 s'."""
    s = max(0.0, _f(s))
    if s < 60:
        return "%d s" % s
    if s < 3600:
        return "%d min" % (s // 60)
    if s < 86400:
        return "%d h %d min" % (s // 3600, (s % 3600) // 60)
    d = int(s // 86400)
    return "%d day%s %d h" % (d, "" if d == 1 else "s", (s % 86400) // 3600)


def _gb(x, digits=1):
    return "?" if x is None else ("%." + str(digits) + "f GB") % (x / 1e9)


def _ms(x):
    return "?" if x is None else ("%.0f ms" % x if x >= 10 else "%.1f ms" % x)


def _usd4(x):
    """A small amount to the hundredth of a cent, signed: +$0.0167 a contract."""
    if x is None:
        return "?"
    return ("+$" if x > 0 else ("-$" if x < 0 else "$")) + "%.4f" % abs(x)


def _pct0(x):
    return "-" if x is None else "%.0f%%" % x


# ---- an append-only log, read once and then only what was added ----------------------------------------------------
_TAILS = {}


def tail_rows(path, field, value):
    """Every record of an append-only jsonl log whose `field` is `value`, read ONCE whole and after that only the bytes
    added since the last call (a file that shrank was replaced: it is read again from the start). Lines are screened
    by substring before json.loads, and a cut last line waits for its end. [] when the file cannot be read."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    key = (path, field, value)
    hit = _TAILS.get(key)
    if hit is None or size < hit["off"]:
        hit = _TAILS[key] = {"off": 0, "rows": []}
    if size > hit["off"]:
        try:
            with open(path, "rb") as fh:
                fh.seek(hit["off"])
                chunk = fh.read(size - hit["off"])
        except OSError:
            return hit["rows"]
        cut = chunk.rfind(b"\n")
        if cut >= 0:
            needle = ('"%s"' % value).encode("utf-8")
            for line in chunk[:cut + 1].split(b"\n"):
                if needle not in line:
                    continue
                try:
                    r = json.loads(line.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get(field) == value:
                    hit["rows"].append(r)
            hit["off"] += cut + 1
    return hit["rows"]


# ---- /speed --------------------------------------------------------------------------------------------------------
def _median(xs):
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _rank(xs, q):
    """The nearest-rank q-th quantile of a sorted list (q=0.9: the 90th percentile), None when empty."""
    if not xs:
        return None
    k = int(q * len(xs))
    k = k if k == q * len(xs) else k + 1
    return xs[max(0, k - 1)]


def _speed_win(rows, t0, t1):
    return [o for o in rows if o.get("t") is not None and t0 <= o["t"] < t1]


def pin_speed_orders(orders):
    """The Ledger's order rows (pindesk) of the pin bot's own logs, as /speed counts them: t, ticker, got, asked, ms."""
    return [{"t": o.get("t"), "tk": o.get("tk"), "got": _f(o.get("filled")), "asked": _fnum(o.get("asked")),
             "ms": o.get("latency_ms")}
            for o in orders if str(o.get("file") or "").startswith("pinrun-live-")]


def speed_stats(rows):
    """One window's orders, worked out: n, zero (orders that got nothing) and its share, contracts got and asked, got
    of asked (over the orders whose ask is known), and the send-to-answer time: how many have one, median, p90."""
    lat = sorted(float(o["ms"]) for o in rows if isinstance(o.get("ms"), (int, float)) and o["ms"] >= 0)
    known = [o for o in rows if o.get("asked")]
    n = len(rows)
    zero = sum(1 for o in rows if _f(o.get("got")) <= 0)
    asked = sum(_f(o["asked"]) for o in known)
    return {"n": n, "zero": zero, "zero_share": (float(zero) / n) if n else None,
            "got": sum(_f(o.get("got")) for o in rows), "asked": asked,
            "got_share": (sum(_f(o.get("got")) for o in known) / asked) if asked > 0 else None,
            "lat_n": len(lat), "med_ms": _median(lat), "p90_ms": _rank(lat, 0.9)}


def _other_order(bot, r):
    """One other bot's order record as /speed counts it, or None when Kalshi did not take it."""
    t = pindesk.parse_t(r.get("t"))
    if bot == "race":
        code = r.get("status_code")
        took = code in (200, 201) if code is not None else r.get("status") in (
            "executed", "canceled", "partially_filled_then_canceled")
        return {"t": t, "tk": r.get("ticker"), "got": _f(r.get("filled")), "asked": _fnum(r.get("count_asked")),
                "ms": None} if took else None
    if r.get("status") not in (200, 201):
        return None
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    rtt = _fnum(r.get("rtt"))
    return {"t": t, "tk": body.get("ticker"), "got": _f(r.get("filled")), "asked": _fnum(body.get("count")),
            "ms": rtt * 1000.0 if rtt is not None else None}


def speed_pin_money(results, server_rows, since):
    """What the pin bot made on the server, per filled contract: the `settled` rows' pnl_c (each leg, a hedge's
    included, fees in) of the pin logs written since `since`, on the markets it got contracts in on the server, over those
    contracts. Markets not settled yet are left out (their contracts are `open_contracts`)."""
    import glob
    got = {}
    for o in server_rows:
        if o.get("tk") and _f(o.get("got")) > 0:
            got[o["tk"]] = got.get(o["tk"], 0.0) + _f(o["got"])
    made = {}
    for p in sorted(glob.glob(os.path.join(results, "pinrun-live-*.jsonl"))):
        try:
            if os.path.getmtime(p) < since:
                continue
        except OSError:
            continue
        for r in tail_rows(p, "kind", "settled"):
            t, tk = pindesk.parse_t(r.get("t")), r.get("ticker")
            if t is None or t < since or tk not in got:
                continue
            v = _fnum(r.get("pnl_c"))              # this leg's money in cents; `realised` is the RUN's running total
            if v is not None:
                made[tk] = made.get(tk, 0.0) + v / 100.0
    contracts = sum(got[tk] for tk in made)
    usd_ = sum(made.values())
    return {"usd": usd_, "contracts": contracts, "markets": len(made),
            "per": (usd_ / contracts) if contracts > 0 else None,
            "open_contracts": sum(v for tk, v in got.items() if tk not in made)}


def speed_estimate(home, srv, money, span_s):
    """What speed added, an ESTIMATE: (server got/asked - home got/asked) x contracts asked on the server = the extra
    contracts; x the $ the server's filled contracts made each. None-valued with `why` when a part is missing."""
    out = {"d_share": None, "extra": None, "usd": None, "per_day": None, "days": span_s / 86400.0, "why": None}
    if home["got_share"] is None:
        out["why"] = "no pin orders at home to compare with"
    elif srv["got_share"] is None:
        out["why"] = "no pin orders on the server yet"
    elif money["per"] is None:
        out["why"] = "none of the server's filled pin markets has settled yet"
    else:
        out["d_share"] = srv["got_share"] - home["got_share"]
        out["extra"] = out["d_share"] * srv["asked"]
        out["usd"] = out["extra"] * money["per"]
        if out["days"] >= 1.0:
            out["per_day"] = out["usd"] / out["days"]
    return out


def speed_gather(results, orders, now, since=None, home_days=None, active=None):
    """Everything /speed shows, worked from the logs (see the section's head). `orders` = the Ledger's order rows.
    `active` (v-tg-active): the other bots' lines for those bots only (None = every bot)."""
    since = SERVER_SINCE_EPOCH if since is None else since
    h0 = since - (SPEED_HOME_DAYS if home_days is None else home_days) * 86400
    pins = pin_speed_orders(orders)
    home, srv = _speed_win(pins, h0, since), _speed_win(pins, since, now + 1)
    d = {"since": since, "home_from": h0, "now": now, "others": [],
         "skipped": [x for x in SPEED_SKIPPED if active is None or x[0] in active],
         "pin": {"home": speed_stats(home), "server": speed_stats(srv)}}
    d["pin"]["money"] = speed_pin_money(results, srv, since)
    d["pin"]["est"] = speed_estimate(d["pin"]["home"], d["pin"]["server"], d["pin"]["money"], now - since)
    for bot, name, field, value in SPEED_OTHERS:
        if active is not None and bot not in active:
            continue
        p = os.path.join(results, name)
        if not os.path.exists(p):
            d["others"].append({"bot": bot, "missing": name})
            continue
        rows = [x for x in (_other_order(bot, r) for r in tail_rows(p, field, value)) if x and x["t"] is not None]
        d["others"].append({"bot": bot, "home": speed_stats(_speed_win(rows, h0, since)),
                            "server": speed_stats(_speed_win(rows, since, now + 1)),
                            "has_ms": any(x["ms"] is not None for x in rows)})
    return d


def _speed_other_line(x, min_other):
    name = SPEED_LABEL.get(x["bot"], x["bot"])
    if x.get("missing"):
        return "<b>%s</b>: skipped: no log here (%s)" % (esc(name), esc(x["missing"]))
    h, s = x["home"], x["server"]

    def part(st, where):
        if not st["n"]:
            return "%s: no orders" % where
        got = 100.0 * (1.0 - st["zero_share"])
        return "%s %s got something (%s of %s%s)" % (
            where, _pct0(got), _cnt(st["n"] - st["zero"]), _nof(st["n"], "order"),
            (", %s" % _ms(st["med_ms"])) if st["med_ms"] is not None else "")
    tail = []
    if s["n"] and s["n"] < min_other:
        tail.append("too few on the server to tell")
    if not x.get("has_ms"):
        tail.append("its log keeps no send time")
    return "<b>%s</b>: %s · %s%s" % (esc(name), esc(part(h, "home")), esc(part(s, "server")),
                                     (" · " + esc("; ".join(tail))) if tail else "")


def speed_html(d, bank=None, min_orders=None, min_other=None):
    """/speed's screen from speed_gather's numbers. `bank` = the main account's bank (the pin bot's), for the %."""
    min_orders = SPEED_MIN_ORDERS if min_orders is None else min_orders
    min_other = SPEED_MIN_OTHER if min_other is None else min_other
    pin = d["pin"]
    h, s, mo, est = pin["home"], pin["server"], pin["money"], pin["est"]
    early = s["n"] < min_orders
    bank_pct = (" (%s of the main account's %s bank)" % (ret(est["usd"], bank, 2), dollars(bank))
                if est["usd"] is not None and bank and ret(est["usd"], bank, 2) else "")
    L = []
    if not s["n"]:
        L.append("⏳ <b>SPEED: too early to tell, no pin orders on the server yet</b>")
    elif early:
        L.append("⏳ <b>SPEED: too early to tell, %s so far</b> on the server (the bar is %d)"
                 % (esc(_nof(s["n"], "order")), min_orders))
    else:
        L.append("⚡ <b>SPEED: %s on the server, was %s at home</b> (median, send to answer)"
                 % (esc(_ms(s["med_ms"])), esc(_ms(h["med_ms"]))))
    if s["n"]:
        L.append("Pin orders that got nothing: <b>%s</b> on the server, %s at home · contracts got of those asked: "
                 "<b>%s</b>, was %s" % (pct1(s["zero"], s["n"]), pct1(h["zero"], h["n"]),
                                        _of100(s["got_share"]) + "%" if s["got_share"] is not None else "-",
                                        _of100(h["got_share"]) + "%" if h["got_share"] is not None else "-"))
    if est["usd"] is not None:
        L.append("%s What speed added: about <b>%s</b>%s since the move%s · an estimate, not a proof" % (
            dot(est["usd"]), esc(usd(est["usd"])), esc(bank_pct),
            (" (too early: %s)" % esc(_nof(s["n"], "order"))) if early else ""))
    L.append(i_("Pin bot · home = %s to %s (%d days, the laptop) · server = since %s (%s so far, AWS Ohio)" % (
        _et_at(d["home_from"]), _et_at(d["since"]), round((d["since"] - d["home_from"]) / 86400.0),
        _et_at(d["since"]), _span_words(d["now"] - d["since"]))))
    L.append("")
    rows = [("Pin bot", "Home", "Server"),
            ("Orders", _cnt(h["n"]), _cnt(s["n"])),
            ("Median", _ms(h["med_ms"]) if h["lat_n"] else "-", _ms(s["med_ms"]) if s["lat_n"] else "-"),
            ("90% under", _ms(h["p90_ms"]) if h["lat_n"] else "-", _ms(s["p90_ms"]) if s["lat_n"] else "-"),
            ("Got nothing", pct1(h["zero"], h["n"]), pct1(s["zero"], s["n"])),
            ("Got / asked", (_of100(h["got_share"]) + "%") if h["got_share"] is not None else "-",
             (_of100(s["got_share"]) + "%") if s["got_share"] is not None else "-"),
            ("Contracts got", _cnt(h["got"]), _cnt(s["got"])),
            ("  asked", _cnt(h["asked"]), _cnt(s["asked"]))]
    L.append(pre(table(rows)))
    L.append("")
    L.append("💵 <b>What speed added (an estimate, not a proof)</b>")
    L.append(i_("extra contracts = (server got/asked - home got/asked) x contracts asked on the server; "
                "$ = extra contracts x the $ made per filled contract on the server"))
    if est["d_share"] is not None:
        L.append("(%s%% - %s%%) x %s asked on the server = <b>%s%s extra contracts</b>" % (
            _of100(s["got_share"]), _of100(h["got_share"]), _cnt(s["asked"]), "+" if est["extra"] > 0 else "",
            esc(_cnt(est["extra"]) if est["extra"] >= 0 else "-" + _cnt(-est["extra"]))))
        L.append("x %s a filled contract (%s on %s contracts in %s settled on the server) = <b>%s</b>%s" % (
            esc(_usd4(mo["per"])), esc(usd(mo["usd"])), esc(_cnt(mo["contracts"])), esc(_nof(mo["markets"], "market")),
            esc(usd(est["usd"])), esc(bank_pct)))
        if est["per_day"] is not None:
            L.append("About <b>%s a day</b> at this pace%s." % (
                esc(usd(est["per_day"])), (" (%s of the bank a day)" % esc(ret(est["per_day"], bank, 2)))
                if bank and ret(est["per_day"], bank, 2) else ""))
        if early:
            L.append("⏳ Too early to tell: %s so far (the bar is %d); a few orders swing this a lot."
                     % (esc(_nof(s["n"], "order")), min_orders))
    else:
        L.append("Not yet: %s." % esc(est["why"]))
    L.append("")
    L.append("🤖 <b>Other bots</b> (orders Kalshi took: how many got something, median send to answer)")
    for x in d["others"]:
        L.append(_speed_other_line(x, min_other))
    for bot, why in d["skipped"]:
        L.append("<b>%s</b>: %s" % (esc(SPEED_LABEL.get(bot, bot)), esc(why)))
    L.append(details(elines([
        "Send to answer = the pin bot's own latency_ms on each order: from sending it to Kalshi's reply. 90% under = "
        "the time 90% of the orders beat.",
        "Got nothing = an order Kalshi answered with no contracts: someone faster took them, or the price moved first.",
        "Got / asked = contracts filled over contracts asked, every order in the window.",
        "$ per filled contract = what the pin bot's markets settled on the server made (its own settled rows: both "
        "legs, a hedge's included, fees in), over the contracts it got in them. Markets still open are left out "
        "(%s contracts now)." % _cnt(mo["open_contracts"]),
        "Why only an estimate: it assumes the extra contracts made what the server's filled ones made, and that the "
        "markets of the two windows were alike. Neither is proven; the gap in got/asked is the measured part.",
        "Other bots: only orders Kalshi took count (a refusal such as 'market not found' is no race); their time is the "
        "bot's own send-to-answer time (rtt).%s" % (" The coin race keeps none." if any(x.get("bot") == "race"
                                                                                       for x in d["others"]) else ""),
        "Home = the %d days before the move (SERVER_SINCE = %s, a constant in research/phone/commands/speed.py); server = since. Read from "
        "the bots' own logs; nothing is asked of Kalshi." % (SPEED_HOME_DAYS, SERVER_SINCE)]),
        "🔎 How each figure is worked (tap)"))
    L.append(i_("/server: the machine, the time to Kalshi, the funds and the AWS bill"))
    return Html("\n".join(L))


# ---- the command (Phone.text_speed) -------------------------------------------------------------------------------------
def load(ctx):
    """speed_gather over the Ledger's orders, then the main account's bank -- Phone.text_speed's reads, in its order."""
    d = speed_gather(ctx.ledger.results, ctx.ledger.orders, ctx.now(), active=ctx.active())
    return d, (ctx.ledger.bank() or {}).get("bank")


def render(data):
    d, bank = data
    return speed_html(d, bank)


def fail(e):
    return ("Could not build /speed: %s\nEverything else still works -- /fills has today's pin orders."
            % str(e)[:200])


COMMAND = declare(Command(
    names=("/speed",), section="server", order=10,
    help_line="/speed: did the move win orders the laptop lost: the pin bot's order times and empty orders, home against "
              "server, and what speed added in $ (an estimate); a line for the other bots",
    chart=None, load=load, render=render, fail=fail))
