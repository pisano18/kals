"""pinday.py -- what we made, by EASTERN day. The one place that answers it.

WHY THIS FILE EXISTS. On 2026-09-17 the operator was told the day was "+$47".
It was **+$23**. The query behind the $47 filtered the live log on
`t.startswith("2026-09-17")`, and `t` is UTC, so it swept in every settlement
from 20:00-23:59 ET the PREVIOUS evening. That is the same ticker-clock trap
that was found and fixed inside `pinflat` a day earlier, repeated in a
throwaway one-liner because there was nothing to call.

So: **no session writes another ad-hoc day total.** Call `by_et_day()` or run
this file. It uses `downtime.et_offset`, the same source the desktop app uses,
so the CLI, the app and the phone bot cannot disagree.

A settlement belongs to the ET day of its CLOSE, taken from the ticker
(`KXBTC15M-26SEP170000-00` closes at midnight ET), falling back to the log's
`t` converted to ET when a ticker cannot be parsed. Those two agree on every
record in the live logs today; the ticker is preferred because it is the
exchange's own clock and survives a log being written late.

**THE MONEY NOW COMES FROM KALSHI, NOT FROM OUR LOGS (2026-09-22).** The bots
write a `settled` line only for a market they were ALIVE to see settle. A run
that dies holding a position never writes one, so every log-derived total
silently drops exactly the markets a crash left behind -- and those are the
expensive ones, because a crash mid-hedge is how they happen. 2026-09-19 read
**-$161.14** from the logs; Kalshi's own books say **-$223.46**. Two markets,
-$62.28, simply were not there.

So the money column is `results/kalshi_ledger.json` (written by
`research/pinledger.py` from `/portfolio/settlements`), one row per MARKET:
a market we hedged is ONE row with both sides netted, exactly as the exchange
settled it. Crypto, the commodity (oil) bot and the coin race are separate
lines -- a total that silently merges or omits a bot has already cost us once.

The log-derived counts are kept, beside it, as a CROSS-CHECK only. Every
market Kalshi settled that no log ever recorded is printed on its own loud
line; so is every market the two disagree on by 50c or more, and every market
a log settled that Kalshi has no record of.

With no ledger file the report says so in capitals, falls back to the logs,
and flags every money figure `LOGS` -- a log number must never be mistaken for
the books.
"""
import argparse
import calendar
import collections
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from downtime import et_offset                                   # noqa: E402

RESULTS = os.path.join(os.path.dirname(HERE), "results")
LIVE_GLOB = os.path.join(RESULTS, "pinrun-live-*.jsonl")
# The COMMODITY bot writes here and nothing used to read it, so every "today"
# figure was crypto-only. On 2026-09-17 that reported +$88 on a day that was
# +$88 crypto and -$58 commodity, and the operator caught the gap himself.
CMD_GLOB = os.path.join(RESULTS, "cmdlive-*.jsonl")

# The file names, so `--results` can point every source at one directory.
LIVE_PAT = "pinrun-live-*.jsonl"
CMD_PAT = "cmdlive-*.jsonl"
# The coin race's REAL bets (`pinracearm.py --live`). Only `live_settled`
# records are money; the same file's `settled` records score paper positions.
RACE_PAT = "pinrace*-live*.jsonl"
LEDGER_NAME = "kalshi_ledger.json"

# Which book a series belongs to. Commodity matches `pindesk._load_kalshi` and
# the keys of `cmdarm.BANDS`; crypto is `CRYPTO_15M` minus the coin race.
# Anything NOT listed is its own "other" line -- a new series must show up
# loudly, never be folded into a bot it does not belong to.
CRYPTO = frozenset(["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
                    "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
                    "KXNEAR15M", "KXTON15M"])
COMMODITY = frozenset(["KXGOLD15M", "KXWTI15M", "KXSILVER15M", "KXCOPPER15M",
                       "KXNATGAS15M"])
RACE = frozenset(["KXCRYPTOLEAD15M", "KXCRYPTOCOMP15M"])
BOOKS = ("crypto", "commodity", "coin race", "other")

# A market both sources hold but price differently by at least this is
# printed. Kalshi rounds fees to the hundredth of a cent and the bots compute
# their own, so a few cents of difference is bookkeeping, not a missing leg.
DISAGREE = 0.50
# A market a log settled that the ledger lacks is "not refreshed yet" when the
# log saw it settle this close to, or after, the ledger's last write.
PENDING_GRACE_S = 600

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def et_day_of_epoch(epoch):
    """'YYYY-MM-DD' in Eastern, from a UTC epoch."""
    e = float(epoch) + et_offset(float(epoch))
    return time.strftime("%Y-%m-%d", time.gmtime(e))


def et_day_of_ticker(ticker):
    """'YYYY-MM-DD' from the ET clock encoded in a ticker, or None.

    `KXBTC15M-26SEP170000-00` -> 2026-09-17. No timezone arithmetic: the
    ticker is already Eastern, which is exactly why reading it as UTC moved
    four hours of settlements into the wrong day.
    """
    try:
        stamp = str(ticker).split("-")[1]
        yy, mon, dd = int(stamp[0:2]), _MONTHS[stamp[2:5].upper()], int(stamp[5:7])
    except (AttributeError, IndexError, KeyError, ValueError):
        return None
    return "%04d-%02d-%02d" % (2000 + yy, mon, dd)


def et_day_of_record(r):
    """The ET day a record belongs to: its ticker's, else its timestamp's."""
    d = et_day_of_ticker(r.get("ticker", ""))
    if d:
        return d
    t = r.get("t")
    if not t:
        return None
    try:
        return et_day_of_epoch(calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%SZ")))
    except (TypeError, ValueError):
        return None


def load(paths):
    """Settled records from the live logs, de-duplicated on (ticker, t) --
    the logs overlap whenever the bot restarts mid-day, and a restart is the
    normal case now that it heals itself."""
    seen, out = set(), []
    for p in paths:
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"settled"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("kind") != "settled":
                    continue
                # DE-DUPLICATE ON THE WHOLE LINE, NOT ON (ticker, t).
                # Two legs of the SAME market settle in the same second with
                # the same ticker, and keying on (ticker, t) silently threw the
                # second one away -- it reported the commodity day as -$23.14
                # when the records summed to -$51.94, because most losing
                # markets carried two legs. The thing we actually need to guard
                # against is a whole line repeated when logs overlap after a
                # restart, and the full line catches exactly that and nothing
                # else.
                k = line.strip()
                if k in seen:
                    continue
                seen.add(k)
                out.append(r)
    return out


def by_et_day(records):
    """{'YYYY-MM-DD': {'n', 'dollars', 'losses', 'lost_dollars'}}"""
    out = collections.defaultdict(
        lambda: {"n": 0, "dollars": 0.0, "losses": 0, "lost_dollars": 0.0})
    for r in records:
        d = et_day_of_record(r)
        if d is None:
            continue
        c = float(r.get("pnl_c") or 0.0) / 100.0
        out[d]["n"] += 1
        out[d]["dollars"] += c
        if c < 0:
            out[d]["losses"] += 1
            out[d]["lost_dollars"] += c
    return dict(out)


# --------------------------------------------------------------------------
# KALSHI'S BOOKS, AND THE LOGS AS A CROSS-CHECK
# --------------------------------------------------------------------------

def book_of(ticker):
    """'crypto' | 'commodity' | 'coin race' | 'other', from the series."""
    s = str(ticker or "").split("-")[0].upper()
    if s in CRYPTO:
        return "crypto"
    if s in COMMODITY:
        return "commodity"
    if s in RACE:
        return "coin race"
    return "other"


def load_race(paths):
    """The coin race's REAL settled legs, as `settled`-shaped records.

    `pinracearm.py --live` writes one `live_settled` line per race with a
    `legs` list; each leg carries its own ticker and `pnl` in DOLLARS (size x
    price, less the fee -- decided from the writer, not from the magnitude).
    Its `settled` lines score PAPER positions and are ignored here.
    Returned records carry `pnl_c` in cents so every log source is one shape.

    A record (or a leg) carrying `paper` is SKIPPED. `pinracearm.py
    --paper-live` runs the whole live decision path with the order call
    replaced, and writes the same `live_settled` shape with the same
    real-looking per-leg dollars -- the `paper` flag is the only thing that
    tells them apart, and this is the only place that has to read it. Without
    this, one paper arm logged as `pinracearm-*-live.jsonl` would put
    invented dollars straight into the operator's DAY TOTAL. pinracearm
    refuses such a name as well; two rails, because this number is what the
    bank balance is reconciled against.
    """
    seen, out = set(), []
    for p in paths:
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"live_settled"' not in line:
                    continue
                k = line.strip()
                if k in seen:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict) or r.get("kind") != "live_settled":
                    continue
                if r.get("paper"):
                    continue          # --paper-live: same shape, no money
                seen.add(k)
                for lg in r.get("legs") or []:
                    if not isinstance(lg, dict) or not lg.get("ticker"):
                        continue
                    if lg.get("paper"):
                        continue
                    try:
                        pc = float(lg.get("pnl") or 0.0) * 100.0
                    except (TypeError, ValueError):
                        pc = 0.0
                    out.append({"kind": "settled", "ticker": lg["ticker"],
                                "pnl_c": pc, "t": r.get("t")})
    return out


def load_ledger(path):
    """(ledger, why). ledger = {'rows', 'written'}; None with a reason when
    there is nothing usable -- a missing file and an unreadable one are
    reported differently, because they are fixed differently."""
    if not os.path.exists(path):
        return None, "no file at %s" % path
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except OSError as e:
        return None, "cannot open %s (%s)" % (path, e)
    except ValueError:
        return None, "%s is not readable JSON" % path
    rows = d.get("settlements") if isinstance(d, dict) else None
    if not isinstance(rows, dict) or not rows:
        return None, "%s holds no settlements" % path
    return {"rows": rows, "written": d.get("written")}, None


def _epoch_of(stamp):
    """UTC epoch from '2026-09-22T10:16:35Z' / '...35.123Z', or None."""
    try:
        return calendar.timegm(time.strptime(str(stamp)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def ledger_markets(rows):
    """({ticker: market}, skipped). ONE entry per market, from Kalshi.

    market = {'day', 'book', 'dollars', 'hedged', 'rows'}. Money is
    `pinledger.pnl` -- payout minus both sides' cost minus fees, as Kalshi
    settled it -- so a hedged market is already one netted row. Should the
    exchange ever list one ticker twice, the two are summed into the one
    market; nothing is dropped. `skipped` counts rows with no ticker or no
    day, so a guard that discards data says how much it discarded.
    """
    import pinledger          # here, not at the top: pinledger imports pinday
    out, skipped = {}, 0
    for s in rows.values():
        if not isinstance(s, dict):
            skipped += 1
            continue
        tk = s.get("ticker") or ""
        d = et_day_of_ticker(tk)
        if d is None:
            e = _epoch_of(s.get("settled_time"))
            d = et_day_of_epoch(e) if e is not None else None
        if not tk or d is None:
            skipped += 1
            continue
        m = out.setdefault(tk, {"day": d, "book": book_of(tk), "dollars": 0.0,
                                "hedged": False, "rows": 0})
        m["dollars"] += pinledger.pnl(s)
        m["hedged"] = m["hedged"] or (pinledger.money(s, "yes_count_fp") > 0
                                      and pinledger.money(s, "no_count_fp") > 0)
        m["rows"] += 1
    return out, skipped


def log_markets(records):
    """({ticker: market}, skipped). The logs' legs NETTED per market.

    The bots write one `settled` line per LEG, so a hedged market is two or
    more lines. Netting them here is what makes the cross-check comparable to
    the ledger's one row per market. market = {'day', 'book', 'dollars',
    'legs', 'last_t'}.
    """
    out, skipped = {}, 0
    for r in records:
        tk = r.get("ticker") or ""
        d = et_day_of_record(r)
        if not tk or d is None:
            skipped += 1
            continue
        try:
            c = float(r.get("pnl_c") or 0.0) / 100.0
        except (TypeError, ValueError):
            c = 0.0
        m = out.setdefault(tk, {"day": d, "book": book_of(tk), "dollars": 0.0,
                                "legs": 0, "last_t": ""})
        m["dollars"] += c
        m["legs"] += 1
        m["last_t"] = max(m["last_t"], str(r.get("t") or ""))
    return out, skipped


def _cell():
    return {"n": 0, "dollars": 0.0, "losses": 0, "hedged": 0,
            "log_n": 0, "log_dollars": 0.0, "log_losses": 0,
            "missing": 0, "missing_dollars": 0.0}


def reconcile(led, logm):
    """Kalshi's money per (ET day, book), the logs beside it, and every
    market the two do not agree on.

    Returns (table, missing, disagree, log_only):
      table    {(day, book): cell}  -- `n/dollars/losses` are KALSHI's,
               `log_*` are the logs', `missing*` the ledger markets no log has
      missing  [(day, book, ticker, kalshi $, hedged)]  -- never in any log
      disagree [(day, book, ticker, kalshi $, logs $)]  -- |gap| >= DISAGREE
      log_only [(day, book, ticker, logs $, log t)]     -- Kalshi has no row
    A loss is a MARKET whose net is below zero, on both sides.
    """
    table = collections.defaultdict(_cell)
    missing, disagree, log_only = [], [], []
    for tk, m in led.items():
        c = table[(m["day"], m["book"])]
        c["n"] += 1
        c["dollars"] += m["dollars"]
        c["losses"] += m["dollars"] < 0
        c["hedged"] += bool(m.get("hedged"))
        g = logm.get(tk)
        if g is None:
            c["missing"] += 1
            c["missing_dollars"] += m["dollars"]
            missing.append((m["day"], m["book"], tk, m["dollars"], bool(m.get("hedged"))))
        elif abs(g["dollars"] - m["dollars"]) >= DISAGREE:
            disagree.append((m["day"], m["book"], tk, m["dollars"], g["dollars"]))
    for tk, g in logm.items():
        c = table[(g["day"], g["book"])]
        c["log_n"] += 1
        c["log_dollars"] += g["dollars"]
        c["log_losses"] += g["dollars"] < 0
        if tk not in led:
            log_only.append((g["day"], g["book"], tk, g["dollars"], g["last_t"]))
    return dict(table), sorted(missing), sorted(disagree), sorted(log_only)


def _et_clock(epoch):
    e = float(epoch) + et_offset(float(epoch))
    return time.strftime("%Y-%m-%d %H:%M ET", time.gmtime(e))


def report(results=RESULTS, days=7, crypto_glob=None, now=None, out=print):
    """Print the day table and return what it printed, for the self-test.

    Reads only: the ledger and the live logs under `results`. Writes nothing.
    `crypto_glob` set means the caller named ONE set of logs; it is honoured
    as before -- that set alone, logs only, flagged -- rather than handed a
    second set or compared against books it may not belong to.
    """
    now = time.time() if now is None else now
    today = et_day_of_epoch(now)
    explicit = crypto_glob is not None
    paths = sorted(glob.glob(crypto_glob if explicit
                             else os.path.join(results, LIVE_PAT)))
    recs = load(paths)
    if not explicit:
        recs += load(sorted(glob.glob(os.path.join(results, CMD_PAT))))
        recs += load_race(sorted(glob.glob(os.path.join(results, RACE_PAT))))
    logm, log_skipped = log_markets(recs)

    ledger_path = os.path.join(results, LEDGER_NAME)
    if explicit:
        ledger, why = None, "an explicit --glob names one set of logs, not the account"
    else:
        ledger, why = load_ledger(ledger_path)
    led, led_skipped = ledger_markets(ledger["rows"]) if ledger else ({}, 0)
    mode = "ledger" if ledger else "logs"
    res = {"mode": mode, "why": why, "led": led, "logm": logm, "lines": []}

    def say(s=""):
        res["lines"].append(s)
        out(s)

    if mode == "logs" and not logm:
        say("  !!! NO KALSHI LEDGER -- %s" % why)
        say("loaded nothing")
        return res

    if mode == "ledger":
        table, missing, disagree, log_only = reconcile(led, logm)
    else:
        # LOGS ONLY: the logs' markets stand in for the money, and every
        # figure below is flagged so it can never be read as the books.
        table, _m, _d, _o = reconcile(logm, logm)
        missing, disagree, log_only = [], [], []
    res.update(table=table, missing=missing, disagree=disagree, log_only=log_only)

    w_epoch = _epoch_of(ledger["written"]) if ledger else None
    say()
    if mode == "ledger":
        say("  MONEY BY EASTERN DAY -- from KALSHI'S OWN BOOKS")
        say("  ledger %s: %d markets, last refreshed %s"
            % (ledger_path, len(led),
               _et_clock(w_epoch) if w_epoch is not None else "at an UNKNOWN time"))
        say("  one row per market, a hedged market is ONE row with both sides "
            "netted. 'logs' = what the bots' own logs recorded -- a cross-check only.")
        flag = ""
    else:
        say(("  !!! NOT KALSHI'S BOOKS -- %s" if explicit
             else "  !!! NO KALSHI LEDGER -- %s") % why)
        say("  !!! MONEY BELOW IS FROM THE BOTS' OWN LOGS, flagged LOGS. The logs "
            "miss every market held when a run died")
        say("  !!! (2026-09-19: logs -161.14, Kalshi -223.46). Refresh the books: "
            "python research/pinledger.py")
        flag = "  LOGS"
    if led_skipped or log_skipped:
        say("  (unplaceable rows set aside: %d ledger, %d log -- no ticker or no day)"
            % (led_skipped, log_skipped))
    say()
    say("  %-10s %-9s | %7s %9s %6s | %9s %9s %6s %8s"
        % ("ET day", "book", "markets", "made", "losses",
           "logs:mkts", "made", "losses", "gap"))

    all_days = sorted({d for d, _b in table})
    for d in all_days[-days:]:
        rows = [(b, table[(d, b)]) for b in BOOKS if (d, b) in table]
        for i, (b, c) in enumerate(rows):
            note = ""
            if c["missing"]:
                note = "  <-- %d NOT IN LOGS (%+.2f)" % (c["missing"], c["missing_dollars"])
            say("  %-10s %-9s | %7d %+9.2f %6d | %9d %+9.2f %6d %+8.2f%s%s"
                % (d if i == 0 else "", b, c["n"], c["dollars"], c["losses"],
                   c["log_n"], c["log_dollars"], c["log_losses"],
                   c["dollars"] - c["log_dollars"], flag, note))
        if len(rows) > 1:
            t = {k: sum(c[k] for _b, c in rows) for k in _cell()}
            say("  %-10s %-9s | %7d %+9.2f %6d | %9d %+9.2f %6d %+8.2f%s"
                % ("", "DAY TOTAL", t["n"], t["dollars"], t["losses"], t["log_n"],
                   t["log_dollars"], t["log_losses"], t["dollars"] - t["log_dollars"],
                   flag))

    say()
    grand = _cell()
    for b in BOOKS:
        cs = [c for (d, bb), c in table.items() if bb == b]
        if not cs:
            continue
        t = {k: sum(c[k] for c in cs) for k in _cell()}
        for k in grand:
            grand[k] += t[k]
        say("  %-10s %-9s | %7d %+9.2f %6d | %9d %+9.2f %6d %+8.2f%s"
            % ("ALL TIME", b, t["n"], t["dollars"], t["losses"], t["log_n"],
               t["log_dollars"], t["log_losses"], t["dollars"] - t["log_dollars"], flag))
    say("  %-10s %-9s | %7d %+9.2f %6d | %9d %+9.2f %6d %+8.2f%s"
        % ("ALL TIME", "TOTAL", grand["n"], grand["dollars"], grand["losses"],
           grand["log_n"], grand["log_dollars"], grand["log_losses"],
           grand["dollars"] - grand["log_dollars"], flag))
    res["grand"] = grand

    first_log = min((g["day"] for g in logm.values()), default=None)
    if mode == "ledger" and first_log:
        k_since = sum(c["dollars"] for (d, _b), c in table.items() if d >= first_log)
        l_since = sum(c["log_dollars"] for (d, _b), c in table.items() if d >= first_log)
        res["since_first_log"] = (first_log, k_since, l_since)
        say("  since the first live log (%s): Kalshi %+.2f, logs %+.2f -- the logs "
            "are off by %+.2f" % (first_log, k_since, l_since, l_since - k_since))

    tv = {b: table.get((today, b)) for b in BOOKS}
    parts = ["%s %+.2f (%d mkts, %d lost)" % (b, c["dollars"], c["n"], c["losses"])
             for b, c in tv.items() if c and c["n"]]
    tot = sum(c["dollars"] for c in tv.values() if c)
    say()
    say("  TODAY (%s ET), %s: %s" % (
        today, "Kalshi's books" if mode == "ledger" else "LOGS, NOT KALSHI",
        "nothing settled yet" if not parts else "  ".join(parts) + "  =  %+.2f" % tot))

    if mode != "ledger":
        return res

    # ---- the markets the two sources do not agree on, every one of them ----
    pending, orphan = [], []
    for row in log_only:
        e = _epoch_of(row[4])
        if w_epoch is None or e is None or e >= w_epoch - PENDING_GRACE_S:
            pending.append(row)
        else:
            orphan.append(row)
    res.update(pending=pending, orphan=orphan)
    if pending:
        say("  + %d market(s) the logs settled after Kalshi's books were last "
            "refreshed (%+.2f by the logs) -- NOT in the money above yet"
            % (len(pending), sum(r[3] for r in pending)))
    if missing:
        say()
        say("  !!! %d MARKET(S) KALSHI SETTLED THAT THE BOTS' LOGS NEVER DID -- "
            "%+.2f on Kalshi's books, absent from every log-derived total"
            % (len(missing), sum(r[3] for r in missing)))
        for d, b, tk, v, hedged in missing:
            tags = []
            if hedged:
                tags.append("hedged: both sides held")
            if first_log is None or d < first_log:
                tags.append("before any live log existed")
            say("  !!! NOT IN LOGS  %s  %-9s  %-34s %+9.2f  %s"
                % (d, b, tk, v, ", ".join(tags)))
    if disagree:
        say()
        say("  !!! %d MARKET(S) WHERE THE LOGS AND KALSHI DIFFER BY %.2f OR MORE"
            % (len(disagree), DISAGREE))
        for d, b, tk, v, g in disagree:
            say("  !!! DISAGREE     %s  %-9s  %-34s kalshi %+9.2f  logs %+9.2f"
                % (d, b, tk, v, g))
    if orphan:
        say()
        say("  !!! %d MARKET(S) A LOG SETTLED THAT KALSHI HAS NO RECORD OF "
            "(settled well before the last refresh)" % len(orphan))
        for d, b, tk, g, t in orphan:
            say("  !!! LOG ONLY     %s  %-9s  %-34s logs %+9.2f" % (d, b, tk, g))
    return res


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinday selftest: FAILED -- " + msg)

    ck(et_day_of_ticker("KXBTC15M-26SEP170000-00") == "2026-09-17",
       "a ticker closing at midnight ET belongs to that ET day, not the UTC one")
    ck(et_day_of_ticker("KXGOLD15M-26SEP172345-15") == "2026-09-17",
       "and so does one closing at 23:45 ET -- which is 03:45Z the NEXT day")
    ck(et_day_of_ticker("KXBTC15M-26JAN012215-00") == "2026-01-01"
       and et_day_of_ticker("KXBTC15M-26DEC312215-00") == "2026-12-31",
       "January and December parse; the month is read from its name, not a number")
    ck(et_day_of_ticker("junk") is None and et_day_of_ticker(None) is None
       and et_day_of_ticker("KXBTC15M-26XXX170000-00") is None,
       "NULL: an unparseable ticker returns None rather than a wrong day")

    # THE BUG THIS FILE EXISTS FOR: 01:30Z on the 17th is 21:30 ET on the 16th.
    e = calendar.timegm((2026, 9, 17, 1, 30, 0))
    ck(et_day_of_epoch(e) == "2026-09-16",
       "01:30Z on the 17th is 21:30 ET on the 16TH -- the four hours that "
       "turned $23 into $47")
    ck(et_day_of_epoch(calendar.timegm((2026, 9, 17, 4, 0, 0))) == "2026-09-17",
       "04:00Z IS midnight ET, the first moment of the new ET day (EDT)")
    ck(et_day_of_epoch(calendar.timegm((2026, 9, 17, 3, 59, 59))) == "2026-09-16",
       "...and one second earlier is still the old one")
    ck(et_day_of_epoch(calendar.timegm((2026, 1, 15, 4, 30, 0))) == "2026-01-14",
       "in JANUARY the offset is five hours, so 04:30Z is still the 14th -- a "
       "hard-coded -4 would be wrong for half the year")

    rs = [{"kind": "settled", "ticker": "KXBTC15M-26SEP170000-00", "pnl_c": 150.0,
           "t": "2026-09-17T04:00:20Z"},
          {"kind": "settled", "ticker": "KXETH15M-26SEP162300-00", "pnl_c": -80.0,
           "t": "2026-09-17T03:00:20Z"},
          {"kind": "settled", "ticker": "KXSOL15M-26SEP171100-00", "pnl_c": 50.0,
           "t": "2026-09-17T15:00:20Z"}]
    d = by_et_day(rs)
    ck(abs(d["2026-09-17"]["dollars"] - 2.00) < 1e-9 and d["2026-09-17"]["n"] == 2,
       "two of the three land on the 17th and pay $2.00")
    ck(d["2026-09-16"]["n"] == 1 and d["2026-09-16"]["losses"] == 1
       and abs(d["2026-09-16"]["lost_dollars"] + 0.80) < 1e-9,
       "the 23:00 ET market is the 16th's loss, though its log line says 17th")
    ck(len(load([])) == 0 and by_et_day([]) == {},
       "NULL: no files, no records, no invented days")
    # TWO LEGS OF ONE MARKET ARE TWO SETTLEMENTS, NOT A DUPLICATE.
    import tempfile as _tf
    _d = _tf.mkdtemp()
    _f = os.path.join(_d, "cmdlive-x.jsonl")
    _same = {"kind": "settled", "ticker": "KXWTI15M-26SEP171615-15",
             "t": "2026-09-17T20:30:20Z"}
    with open(_f, "w", encoding="utf-8") as _fh:
        _fh.write(json.dumps(dict(_same, pnl_c=-2926.0)) + chr(10))
        _fh.write(json.dumps(dict(_same, pnl_c=-2958.0)) + chr(10))
        _fh.write(json.dumps(dict(_same, pnl_c=-2926.0)) + chr(10))   # a true repeat
    _got = load([_f])
    ck(len(_got) == 2 and abs(sum(float(x["pnl_c"]) for x in _got) + 5884.0) < 1e-9,
       "two DIFFERENT legs on one ticker at one second both count (-$58.84); an "
       "identical line repeated after a restart does not. Keying on (ticker, t) "
       "reported that market as -$29.26 and hid half the loss")
    rec = {"kind": "settled", "ticker": "", "pnl_c": 10.0, "t": "2026-09-17T15:00:20Z"}
    ck(et_day_of_record(rec) == "2026-09-17",
       "with no usable ticker it falls back to the timestamp, converted to ET")

    selftest_ledger(ck)
    print("pinday selftest: OK")


def selftest_ledger(ck):
    """MONEY FROM KALSHI'S BOOKS. Every world is built in a temp directory;
    nothing here reads or writes the real results folder."""
    import shutil
    import tempfile

    ck(book_of("KXBTC15M-26SEP190000-00") == "crypto"
       and book_of("KXWTI15M-26SEP191215-15") == "commodity"
       and book_of("KXCRYPTOLEAD15M-26SEP210500-XRP") == "coin race"
       and book_of("KXBTCD-26AUG1501-T63099.99") == "other"
       and book_of(None) == "other",
       "crypto, the commodity bot and the coin race are separate books; an "
       "unknown series is 'other', never folded into a bot it is not")

    def row(tk, result, yes_n=0.0, yes_cost=0.0, no_n=0.0, no_cost=0.0, fee=0.0,
            st="2026-09-19T12:00:04.1Z"):
        return {"ticker": tk, "market_result": result,
                "yes_count_fp": "%.2f" % yes_n, "yes_total_cost_dollars": "%.6f" % yes_cost,
                "no_count_fp": "%.2f" % no_n, "no_total_cost_dollars": "%.6f" % no_cost,
                "fee_cost": "%.6f" % fee, "revenue": 0, "settled_time": st}

    def leg(tk, pnl_c, t="2026-09-19T12:00:20Z"):
        return {"ticker": tk, "pnl_c": pnl_c, "t": t, "kind": "settled"}

    def world(ledger_rows, crypto=(), oil=(), race=(), written="2026-09-19T23:00:00Z",
              ledger_text=None):
        root = tempfile.mkdtemp(prefix="pinday-st-")
        if ledger_rows is not None or ledger_text is not None:
            with open(os.path.join(root, LEDGER_NAME), "w", encoding="utf-8") as fh:
                if ledger_text is not None:
                    fh.write(ledger_text)
                else:
                    json.dump({"settlements": {"%s|%s" % (r["ticker"], r["settled_time"]): r
                                               for r in ledger_rows},
                               "written": written}, fh)
        for name, recs in (("pinrun-live-20260919T000000Z.jsonl", crypto),
                           ("cmdlive-20260919T000000Z.jsonl", oil),
                           ("pinracepenny-live.jsonl", race)):
            if recs:
                with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
                    for r in recs:
                        fh.write(json.dumps(r) + chr(10))
        return root

    NOW = calendar.timegm((2026, 9, 20, 3, 0, 0))     # 23:00 ET on the 19th
    DAY = "2026-09-19"
    WIN = "KXSOL15M-26SEP190800-00"
    GONE = "KXBTC15M-26SEP191415-15"
    HEDGE = "KXBTC15M-26SEP172115-15"
    roots = []
    try:
        # 1. A MARKET ONLY THE LEDGER HAS IS COUNTED, AND SAID OUT LOUD.
        #    The run died holding GONE: Kalshi settled it, no log ever did.
        r1 = world([row(WIN, "no", no_n=10, no_cost=9.0, fee=0.0),        # +1.00
                    row(GONE, "yes", no_n=31, no_cost=30.0, fee=0.0)],    # -30.00
                   crypto=[leg(WIN, 100.0)])
        roots.append(r1)
        a = report(r1, days=7, now=NOW, out=lambda s: None)
        c = a["table"][(DAY, "crypto")]
        ck(a["mode"] == "ledger" and c["n"] == 2 and abs(c["dollars"] + 29.0) < 1e-9
           and c["losses"] == 1,
           "the market no log settled IS in the day's money: Kalshi says 2 "
           "markets, -29.00 -- the logs alone would have said 1 market, +1.00")
        ck(c["log_n"] == 1 and abs(c["log_dollars"] - 1.0) < 1e-9
           and c["missing"] == 1 and abs(c["missing_dollars"] + 30.0) < 1e-9,
           "the logs' own count is kept beside it as the cross-check, and the "
           "gap is exactly the missing market's -30.00")
        ck([m[2] for m in a["missing"]] == [GONE]
           and any(s.startswith("  !!! NOT IN LOGS") and GONE in s for s in a["lines"]),
           "and that market gets its own loud NOT IN LOGS line, by name")

        # 2. A HEDGED MARKET IS ONE ROW. Kalshi's real 09-17 settlement: 99 YES
        #    and 99 NO, settled NO -> -27.8734. The log wrote it as two legs.
        hedged = dict(row(HEDGE, "no", yes_n=99, yes_cost=52.47, no_n=99,
                          no_cost=71.28, fee=3.1234, st="2026-09-18T01:15:04.588332Z"))
        r2 = world([hedged], crypto=[leg(HEDGE, -5351.04, "2026-09-18T01:15:20Z"),
                                     leg(HEDGE, 2563.70, "2026-09-18T01:15:35Z")],
                   written="2026-09-18T02:00:00Z")
        roots.append(r2)
        b = report(r2, days=7, now=NOW, out=lambda s: None)
        hc = b["table"][("2026-09-17", "crypto")]
        ck(len(b["led"]) == 1 and b["led"][HEDGE]["hedged"]
           and abs(b["led"][HEDGE]["dollars"] + 27.8734) < 1e-4,
           "a hedged market is ONE ledger market, both sides netted: -27.87")
        ck(hc["n"] == 1 and hc["losses"] == 1 and hc["log_n"] == 1
           and b["logm"][HEDGE]["legs"] == 2 and hc["log_losses"] == 1,
           "and the log's two legs net to ONE market on the cross-check side "
           "too -- one market, one loss, on both sides of the table")
        ck(not b["missing"] and not b["disagree"] and not b["log_only"],
           "the two legs sum to Kalshi's figure, so nothing is flagged")

        # 3. NULL: NO LEDGER FILE -> SAYS SO, FALLS BACK TO THE LOGS, FLAGGED.
        r3 = world(None, crypto=[leg(WIN, 100.0), leg(GONE, -250.0)])
        roots.append(r3)
        n = report(r3, days=7, now=NOW, out=lambda s: None)
        nc = n["table"][(DAY, "crypto")]
        ck(n["mode"] == "logs" and "no file" in n["why"]
           and any("NO KALSHI LEDGER" in s for s in n["lines"]),
           "NULL: with no ledger file it SAYS there is no Kalshi ledger")
        ck(nc["n"] == 2 and abs(nc["dollars"] + 1.5) < 1e-9,
           "and falls back to the logs' money (-1.50), rather than printing nothing")
        money_rows = [s for s in n["lines"]
                      if " | " in s and not s.startswith("  ET day")]
        ck(money_rows and all(s.rstrip().endswith("LOGS") for s in money_rows)
           and any("LOGS, NOT KALSHI" in s for s in n["lines"]),
           "and EVERY money row, plus today's line, is flagged LOGS")
        ck(not n["missing"] and not any(s.startswith("  !!! NOT IN LOGS")
                                        for s in n["lines"]),
           "NULL: with no ledger there is nothing to call missing, so it calls "
           "nothing missing")

        # 3b. NULL: an unreadable ledger is not silently treated as empty books.
        r3b = world(None, crypto=[leg(WIN, 100.0)], ledger_text="{not json")
        roots.append(r3b)
        nb = report(r3b, days=7, now=NOW, out=lambda s: None)
        ck(nb["mode"] == "logs" and "not readable" in nb["why"],
           "NULL: a corrupt ledger falls back the same way and names the reason")

        # 3c. NULL: neither ledger nor logs -> 'loaded nothing', no invented days
        r3c = world(None)
        roots.append(r3c)
        nc0 = report(r3c, days=7, now=NOW, out=lambda s: None)
        ck(nc0["mode"] == "logs" and "loaded nothing" in nc0["lines"]
           and "table" not in nc0,
           "NULL: no ledger and no logs says loaded nothing and stops")

        # 4. NULL: THE TWO SOURCES AGREE -> NOT ONE WARNING.
        r4 = world([row(WIN, "no", no_n=10, no_cost=9.0)], crypto=[leg(WIN, 100.0)])
        roots.append(r4)
        q = report(r4, days=7, now=NOW, out=lambda s: None)
        ck(not q["missing"] and not q["disagree"] and not q["log_only"]
           and not any("!!!" in s for s in q["lines"]),
           "NULL: when the logs match the books line for line, nothing is flagged")

        # 5. THE THREE BOOKS ARE SEPARATE LINES; the race log's REAL legs count.
        OIL = "KXWTI15M-26SEP191215-15"
        RC = "KXCRYPTOLEAD15M-26SEP190500-XRP"
        r5 = world([row(WIN, "no", no_n=10, no_cost=9.0),
                    row(OIL, "yes", no_n=31, no_cost=30.0),               # -30.00
                    row(RC, "yes", yes_n=1, yes_cost=0.97, fee=0.0021)],  # +0.0279
                   crypto=[leg(WIN, 100.0)], oil=[leg(OIL, -3000.0)],
                   race=[{"event": "KXCRYPTOLEAD15M-26SEP190500", "kind": "live_settled",
                          "t": "2026-09-19T09:01:15Z", "pnl": 0.0279,
                          "legs": [{"ticker": RC, "pnl": 0.0279}]},
                         {"event": "KXCRYPTOLEAD15M-26SEP190500", "kind": "settled",
                          "t": "2026-09-19T09:01:15Z", "pnl": 55.0, "positions": 3},
                         # --paper-live: the SAME shape, the same real-looking
                         # dollars, flagged `paper`. It must not be money.
                         {"event": "KXCRYPTOLEAD15M-26SEP190500",
                          "kind": "live_settled", "paper": True,
                          "t": "2026-09-19T09:01:15Z", "pnl": -9.99,
                          "legs": [{"ticker": RC, "pnl": -9.99}]}])
        roots.append(r5)
        f = report(r5, days=7, now=NOW, out=lambda s: None)
        t5 = f["table"]
        ck((DAY, "crypto") in t5 and (DAY, "commodity") in t5 and (DAY, "coin race") in t5
           and abs(t5[(DAY, "commodity")]["dollars"] + 30.0) < 1e-9
           and abs(t5[(DAY, "coin race")]["dollars"] - 0.0279) < 1e-9,
           "crypto, commodity and coin race are three separate lines on the day")
        ck(abs(t5[(DAY, "coin race")]["log_dollars"] - 0.0279) < 1e-9
           and not f["missing"],
           "the coin race cross-check reads the REAL bet (live_settled), not the "
           "paper `settled` line's 55.00 in the same file")
        ck([x["pnl_c"] for x in load_race(
               sorted(glob.glob(os.path.join(r5, RACE_PAT))))] == [2.79]
           and load_race([]) == [],
           "and NOT the --paper-live line's -9.99 in that same file: the same "
           "`live_settled` shape with the same real-looking dollars and only "
           "a `paper` flag to tell it apart. It is dropped at the source, not "
           "netted out later, so a paper arm logged under the money glob "
           "cannot land in the operator's DAY TOTAL (and nothing in, nothing "
           "out)")
        ck(any("DAY TOTAL" in s and "-28.97" in s for s in f["lines"]),
           "and a DAY TOTAL row sums the three books (1.00 - 30.00 + 0.03)")

        # 6. A MARKET ONLY A LOG HAS: 'not refreshed yet' vs 'Kalshi has no record'
        LATE = "KXETH15M-26SEP192245-45"
        OLD = "KXXRP15M-26SEP190100-00"
        r6 = world([row(WIN, "no", no_n=10, no_cost=9.0)],
                   crypto=[leg(WIN, 100.0), leg(LATE, 50.0, "2026-09-20T02:45:20Z"),
                           leg(OLD, 40.0, "2026-09-19T05:00:20Z")],
                   written="2026-09-20T01:00:00Z")
        roots.append(r6)
        g = report(r6, days=7, now=NOW, out=lambda s: None)
        ck([x[2] for x in g["pending"]] == [LATE] and [x[2] for x in g["orphan"]] == [OLD],
           "a log settlement AFTER the last ledger refresh is 'not in the books "
           "yet'; one from long BEFORE it is a loud LOG ONLY line")
        ck(abs(g["table"][(DAY, "crypto")]["dollars"] - 1.0) < 1e-9,
           "and neither is added to Kalshi's money -- the books are the books")

        # 7. A DISAGREEMENT of 50c or more is printed; a cent of fee rounding is not
        r7 = world([row(WIN, "no", no_n=10, no_cost=9.0),
                    row(OIL, "yes", no_n=31, no_cost=30.0)],
                   crypto=[leg(WIN, 99.0)], oil=[leg(OIL, -2900.0)])
        roots.append(r7)
        h = report(r7, days=7, now=NOW, out=lambda s: None)
        ck([x[2] for x in h["disagree"]] == [OIL],
           "a 1.00 gap on one market is flagged DISAGREE; a 1c gap is not")
    finally:
        for r in roots:
            shutil.rmtree(r, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--glob", default=None,
                    help="read ONLY these logs, logs-only, no ledger (flagged LOGS)")
    ap.add_argument("--results", default=RESULTS,
                    help="the folder holding kalshi_ledger.json and the live logs "
                         "(read only)")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    # `--glob` equal to the old default is the default, not an explicit choice.
    g = a.glob
    if g is not None and os.path.abspath(g) == os.path.abspath(
            os.path.join(a.results, LIVE_PAT)):
        g = None
    report(a.results, days=a.days, crypto_glob=g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
