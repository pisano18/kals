#!/usr/bin/env python3
"""pinflat.py -- is the live bot holding a bet right now? One answer, one source.

WHY THIS EXISTS. restart_bot.ps1 refused to restart while "filled orders >
settled records" in the newest live log. That is the right refusal while the
bot is ALIVE -- a deliberate restart mid-bet abandons the hedge and the loss
brake. But when the bot has DIED holding a bet, the settled record it would
have written never arrives, the count never balances, and the refusal is
permanent: the watchdog calls restart_bot every minute, restart_bot refuses
every minute, and the account stops trading until a human deletes a file.
That is the deadlock this file removes, and it is the one a two-hour exchange
outage at 3 AM would have walked straight into.

THE RULE.
  bot alive  : ANY fill without a settled record is HOLDING. Wait.
  bot dead   : a fill whose market has not yet CLOSED (plus a short grace) is
               HOLDING -- a new bot could buy the same close again and double
               the exposure the per-close budget exists to cap. A fill whose
               close has passed has settled on the exchange whether or not we
               logged it; nothing a new process could do about it. FLAT.

The close time is read from the ticker itself (KXBNB15M-26SEP161000-00 closes
2026-09-16 10:00Z), not from any log field, so a log that died mid-line still
answers. Fills are matched to settlements PER TICKER, because a hedge leg is a
second filled order on the same ticker and writes its own settled record.

Exit 0 = FLAT, 1 = HOLDING, 2 = could not tell (the caller decides; restart_bot
falls back to its old count). --json prints one machine-readable line.

    python research/pinflat.py --selftest
    python research/pinflat.py [--json] [--grace 180]
"""
import argparse
import calendar
import glob
import json
import os
import re
import sys
import time

RESULTS = r"C:\kals-repo\results"
PIDFILE = os.path.join(RESULTS, "pinrun-live.pid")
GRACE_S = 180

_MON = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}
_TK = re.compile(r"^[A-Z0-9]+-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?:-|$)")


def close_epoch(ticker):
    """UTC epoch of a 15-minute market's close, from its ticker. None if the
    ticker is not shaped like one."""
    m = _TK.match(str(ticker or ""))
    if not m:
        return None
    yy, mon, dd, hh, mm = m.groups()
    mon_i = _MON.get(mon)
    if not mon_i:
        return None
    try:
        return calendar.timegm((2000 + int(yy), mon_i, int(dd), int(hh), int(mm), 0))
    except (ValueError, OverflowError):
        return None


def pid_alive(pid):
    """Same semantics as pinrun._pid_alive: never reads a command line, and
    answers YES when it cannot tell. Reimplemented rather than imported so a
    restart check never imports the bot (kauth, sockets, 6,700 lines)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE only
            if h:
                k32.CloseHandle(h)
                return True
            return k32.GetLastError() == 5                # exists, not ours
        except Exception:                                 # noqa: BLE001
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        import errno
        return getattr(e, "errno", None) == errno.EPERM


def live_pid(pidfile=PIDFILE):
    try:
        with open(pidfile, encoding="utf-8") as fh:
            return int((fh.read() or "0").strip() or 0) or None
    except (OSError, ValueError):
        return None


def newest_log(results=RESULTS):
    logs = glob.glob(os.path.join(results, "pinrun-live-*.jsonl"))
    if not logs:
        return None
    return max(logs, key=os.path.getmtime)


def _filled(rec):
    try:
        return float(rec.get("filled") or 0) > 0
    except (TypeError, ValueError):
        return False


def positions(rows):
    """{ticker: fills - settlements} for every ticker that is net open."""
    fills, done = {}, {}
    for r in rows:
        k = r.get("kind")
        tk = r.get("ticker")
        if not tk:
            continue
        if k == "order" and _filled(r):
            fills[tk] = fills.get(tk, 0) + 1
        elif k == "hedge":
            # a hedge record carries `n` (contracts) and `status`, not `filled`
            try:
                hedged = float(r.get("n") or 0) > 0 and str(r.get("status", "")) == "executed"
            except (TypeError, ValueError):
                hedged = False
            if hedged or _filled(r):
                fills[tk] = fills.get(tk, 0) + 1
        elif k == "settled":
            done[tk] = done.get(tk, 0) + 1
    out = {}
    for tk, n in fills.items():
        open_n = n - done.get(tk, 0)
        if open_n > 0:
            out[tk] = open_n
    return out


def read_rows(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue                  # a line cut off by a crash
    return rows


def verdict(rows, alive, now=None, grace=GRACE_S):
    """(status, detail). status in FLAT / HOLDING."""
    now = time.time() if now is None else now
    open_pos = positions(rows)
    if not open_pos:
        return "FLAT", {"open": {}, "alive": alive, "why": "every fill has settled"}
    if alive:
        return "HOLDING", {"open": open_pos, "alive": True,
                           "why": "bot is alive and holding %d open fill(s)"
                                  % sum(open_pos.values())}
    ahead = {}
    for tk, n in open_pos.items():
        c = close_epoch(tk)
        if c is None or c + grace > now:
            ahead[tk] = {"n": n, "closes_in_s": None if c is None else int(c - now)}
    if ahead:
        return "HOLDING", {"open": ahead, "alive": False,
                           "why": "bot is dead but %d market(s) have not closed yet; "
                                  "a new bot could buy the same close twice" % len(ahead)}
    return "FLAT", {"open": {}, "alive": False, "unlogged": open_pos,
                    "why": "bot is dead; %d fill(s) never logged a settlement but "
                           "their markets closed over %ds ago -- settled on the "
                           "exchange, nothing to double" % (sum(open_pos.values()), grace)}


def check(results=RESULTS, pidfile=PIDFILE, now=None, grace=GRACE_S):
    pid = live_pid(pidfile)
    alive = bool(pid) and pid_alive(pid)
    log = newest_log(results)
    if not log:
        return "FLAT", {"open": {}, "alive": alive, "pid": pid, "log": None,
                        "why": "no live log at all"}
    st, d = verdict(read_rows(log), alive, now=now, grace=grace)
    d.update(pid=pid, log=os.path.basename(log))
    return st, d


# --------------------------------------------------------------------------
def selftest():
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinflat selftest: FAILED -- " + msg)

    # ticker -> close
    ck(close_epoch("KXBNB15M-26SEP161000-00") == calendar.timegm((2026, 9, 16, 10, 0, 0)),
       "the close time is read from the ticker: 26SEP161000 is 2026-09-16 10:00Z")
    ck(close_epoch("KXXRP15M-26SEP170000-00") == calendar.timegm((2026, 9, 17, 0, 0, 0)),
       "and midnight parses (0000)")
    ck(close_epoch("garbage") is None and close_epoch(None) is None,
       "NULL: a non-ticker has no close")

    def order(tk, filled, kind="order"):
        return {"kind": kind, "ticker": tk, "filled": filled, "status": "executed"}

    def settled(tk):
        return {"kind": "settled", "ticker": tk, "pnl_c": 1.0}

    now = calendar.timegm((2026, 9, 16, 10, 5, 0))          # 10:05Z
    past = "KXBNB15M-26SEP161000-00"                        # closed 10:00Z
    ahead = "KXBTC15M-26SEP161015-15"                       # closes 10:15Z

    st, d = verdict([order(past, 85), settled(past)], alive=True, now=now)
    ck(st == "FLAT", "a fill with its settlement is flat")
    st, d = verdict([order(past, 85), order(ahead, 0)], alive=True, now=now)
    ck(st == "HOLDING" and d["open"] == {past: 1},
       "alive + an unsettled fill = HOLDING, and a zero-fill order is not a fill")
    st, d = verdict([order(past, 85)], alive=False, now=now)
    ck(st == "FLAT" and d.get("unlogged") == {past: 1},
       "THE DEADLOCK: dead bot, fill never logged a settlement, market closed 5 min "
       "ago -> FLAT (it settled on the exchange; refusing forever helps nobody)")
    st, d = verdict([order(past, 85)], alive=False, now=now, grace=600)
    ck(st == "HOLDING", "...but inside the grace window it still waits")
    st, d = verdict([order(ahead, 40)], alive=False, now=now)
    ck(st == "HOLDING" and d["open"][ahead]["closes_in_s"] == 600,
       "dead bot, market still 10 min from closing -> HOLDING (a new bot could "
       "buy that close again)")
    # hedge legs are fills on the same ticker and write their own settled record
    rows = [order(past, 85), {"kind": "hedge", "ticker": past, "n": 1.0,
                              "status": "executed"}, settled(past), settled(past)]
    ck(verdict(rows, alive=True, now=now)[0] == "FLAT",
       "a hedge leg is a second fill on the same ticker; two settlements clear it")
    rows = rows[:-1]
    ck(verdict(rows, alive=True, now=now)[0] == "HOLDING",
       "...and with only one settlement the pair is still open")
    # max-per-market 2: two fills, two settlements
    rows = [order(past, 40), order(past, 45), settled(past), settled(past)]
    ck(verdict(rows, alive=True, now=now)[0] == "FLAT", "two fills, two settlements")
    ck(verdict([], alive=True, now=now)[0] == "FLAT", "NULL: an empty log is flat")

    # end to end on a temp directory, with a dead pid
    with tempfile.TemporaryDirectory() as td:
        pf = os.path.join(td, "pinrun-live.pid")
        with open(pf, "w") as fh:
            fh.write("999999999")            # not a real pid on any box
        lp = os.path.join(td, "pinrun-live-20260916T100000Z.jsonl")
        with open(lp, "w") as fh:
            fh.write(json.dumps(order(past, 85)) + "\n")
            fh.write('{"kind": "close_summary", "trunc')     # a crash mid-line
        st, d = check(results=td, pidfile=pf, now=now)
        ck(st == "FLAT" and d["log"].startswith("pinrun-live-") and not d["alive"],
           "end to end: a truncated last line is skipped, the dead pid is seen as "
           "dead, the past close is flat")
        st, d = check(results=os.path.join(td, "nothing"), pidfile=pf, now=now)
        ck(st == "FLAT" and d["log"] is None, "NULL: no log at all is flat")
    ck(pid_alive(os.getpid()), "our own pid is alive")
    ck(not pid_alive(0) and not pid_alive("x"), "pid 0 / junk is not")
    print("pinflat selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--grace", type=int, default=GRACE_S)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    try:
        st, d = check(grace=a.grace)
    except Exception as e:                                # noqa: BLE001
        print(json.dumps({"status": "UNKNOWN", "err": str(e)[:200]}) if a.json
              else "pinflat: could not tell -- %s" % e)
        return 2
    if a.json:
        print(json.dumps({"status": st, **d}))
    else:
        print("%s -- %s (pid %s, %s)" % (st, d["why"], d.get("pid"), d.get("log")))
        for tk, v in (d.get("open") or {}).items():
            print("    open: %s %s" % (tk, v))
    return 0 if st == "FLAT" else 1


if __name__ == "__main__":
    sys.exit(main())
