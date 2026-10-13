#!/usr/bin/env python3
"""watchlive.py -- the operator's "resume watcher": a live-bot watch a Claude session runs under its Monitor tool.

Operator 2026-10-13: "Can you make something so I can just say resume watcher and it will?" Before this, every
session re-typed a long tail|grep pipeline, and that pipeline kept tailing the OLD log after a bot restart.

    python -u research/watchlive.py             # watch: print ONLY lines that need attention, as they happen
    python research/watchlive.py --status       # one-shot hourly check: money, connection counts, processes, disk, RAM
    python research/watchlive.py --selftest

Watched: the NEWEST results/pinrun-live-*.jsonl (re-checked every 30 s; a new log -- a restart -- is announced and
read from its first line, so a bad start record is caught), plus the side bots' results/forecaster-live.jsonl,
results/ladder-live.jsonl and results/pinracepenny-live.jsonl. Existing lines are skipped at start (no replay).

Alert = halts / aborts / pauses / errors / stops, every insurance (hedge*) record, every conn_event (v-fastconn),
a negative pnl_c (a loss), a Traceback, outcome UNKNOWN, conn_result unknown/failed/recovered, a retried send,
status_code -1, keep_conn false, hook_errors > 0, ktruth unknown/unresolved. Routine and skipped: stale_idle
connection refreshes, and stale_replaced on GETs (a data read finding a dead kept connection and replacing it
before sending -- measured harmless 10-13). A stale_replaced on an ORDER or HEDGE is still an alert.

Read-only: reads results/, never writes; the --status process query filters Name='python.exe' (never kills).
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDE = ("forecaster-live.jsonl", "ladder-live.jsonl", "pinracepenny-live.jsonl")
ALERT = re.compile(
    r'"kind": ?"(halt|abort|pause|error|exit|stop|hedge|hedge_alarm|hedge_blind|hedge_no_ask|hedge_unknown|'
    r'hedge_not_sent|hedge_refused|hedge_panic|conn_event)"|"pnl_c": ?-|Traceback|"error": ?"|outcome UNKNOWN|'
    r'"conn_result": ?"(unknown|failed|recovered)"|"conn": ?"retried"|"status_code": ?-1|"keep_conn": ?false|'
    r'"hook_errors": ?[1-9]|"what": ?"(unknown|unresolved)"')
SKIP = re.compile(r'stale_idle|"event": ?"stale_replaced", ?"method": ?"GET"')
WIDTH = 400


def newest_main(root):
    logs = glob.glob(os.path.join(root, "results", "pinrun-live-*.jsonl"))
    return max(logs, key=lambda p: (os.path.getmtime(p), p)) if logs else None


class Tail:
    """Follows one file: new complete lines only; survives the file appearing late, being truncated or replaced."""

    def __init__(self, path, from_start=False):
        self.path, self.pos, self.buf = path, None, b""
        if not from_start and os.path.exists(path):
            self.pos = os.path.getsize(path)
        elif from_start:
            self.pos = 0

    def lines(self):
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []
        if self.pos is None or size < self.pos:          # appeared after start, or truncated/replaced: read it all
            self.pos, self.buf = 0, b""
        if size == self.pos:
            return []
        with open(self.path, "rb") as fh:
            fh.seek(self.pos)
            data = fh.read(size - self.pos)
        self.pos += len(data)
        parts = (self.buf + data).split(b"\n")
        self.buf = parts.pop()                            # an unfinished last line waits for its newline
        return [p.decode("utf-8", "replace").rstrip("\r") for p in parts if p.strip()]


def wanted(line):
    return bool(ALERT.search(line)) and not SKIP.search(line)


def watch(root, out=print, stop=None, poll_s=1.0, rescan_s=30.0):
    main = newest_main(root)
    tails = {p: Tail(p) for p in [main] if p}
    for name in SIDE:
        p = os.path.join(root, "results", name)
        tails[p] = Tail(p)
    last_scan = time.monotonic()
    while not (stop and stop.is_set()):
        if time.monotonic() - last_scan >= rescan_s:
            last_scan = time.monotonic()
            now_main = newest_main(root)
            if now_main and now_main != main:
                if main:
                    tails.pop(main, None)
                main = now_main
                tails[main] = Tail(main, from_start=True)
                out("WATCHER: the main bot started a new log (a restart): %s" % os.path.basename(main))
        for p, t in list(tails.items()):
            for line in t.lines():
                if wanted(line):
                    out(("%s | " % os.path.basename(p) if p != main else "") + line[:WIDTH])
        if stop:
            stop.wait(poll_s)
        else:
            time.sleep(poll_s)


def status(root, out=print):
    main = newest_main(root)
    if not main:
        out("no live main-bot log found")
        return 1
    c, pn, cs, start, last = {}, [], None, None, None
    with open(main, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind") or "loop"
            c[k] = c.get(k, 0) + 1
            last = r.get("t") or last
            if k == "start" and start is None:
                start = r
            elif k == "conn_stats":
                cs = r
            elif k == "settled":
                pn.append(r.get("pnl_c") or 0)
    out("log %s  start %s  code_sha %s  keep_conn %s  last record %s" % (
        os.path.basename(main), (start or {}).get("t"), (start or {}).get("code_sha"),
        (start or {}).get("keep_conn"), last))
    out("orders %d  hedges %d  settled %d  money $%.2f  losing settled records %d  conn_event %d  error %d  halt %d" % (
        c.get("order", 0), c.get("hedge", 0), len(pn), sum(pn) / 100.0, sum(1 for x in pn if x < 0),
        c.get("conn_event", 0), c.get("error", 0), c.get("halt", 0)))
    if cs:
        out("conn counts %s  conn %s" % (cs.get("counts"), {k: v for k, v in (cs.get("conn") or {}).items() if v}))
    ps = ("$n=@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { $_.CommandLine });"
          "foreach ($w in 'pinrun.py --live','pinracearm.py --live','kalshi_collector','crypto_feeds','pinphone') {"
          " '{0}: {1}' -f $w, @($n | Where-Object { $_ -like ('*' + $w + '*') }).Count };"
          "$o=Get-CimInstance Win32_OperatingSystem;"
          "'free disk {0:N1} GB, free RAM {1:N1} GB, commit free {2:N1} GB' -f ((Get-PSDrive C).Free/1GB),"
          " ($o.FreePhysicalMemory/1MB), ($o.FreeVirtualMemory/1MB)")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
        for l in (r.stdout or "").splitlines():
            if l.strip():
                out(l.strip())
    except (OSError, subprocess.SubprocessError) as e:
        out("process/disk check FAILED: %s" % e)
    return 0


def selftest():
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    td = tempfile.mkdtemp(prefix="watchlive_")
    try:
        res = os.path.join(td, "results")
        os.makedirs(res)
        a = os.path.join(res, "pinrun-live-20260101T000000Z.jsonl")
        side = os.path.join(res, "ladder-live.jsonl")
        with open(a, "w") as fh:
            fh.write('{"kind": "halt", "why": "OLD line, before the watcher started"}\n')
        with open(side, "w") as fh:
            fh.write('{"kind": "error", "msg": "old side line"}\n')
        got, stop = [], threading.Event()
        th = threading.Thread(target=watch, args=(td,), kwargs=dict(out=got.append, stop=stop, poll_s=0.05,
                                                                    rescan_s=0.2), daemon=True)
        th.start()
        time.sleep(0.3)

        def add(path, text):
            with open(path, "a") as fh:
                fh.write(text)
            time.sleep(0.25)
        add(a, '{"t": "x", "tau": 30}\n')                                                     # routine loop
        add(a, '{"kind": "conn_event", "event": "stale_replaced", "why": "stale_idle"}\n')    # routine
        add(a, '{"event": "stale_replaced", "method": "GET", "what": "get", "kind": "conn_event"}\n')  # routine
        add(a, '{"event": "stale_replaced", "method": "POST", "what": "hedge", "kind": "conn_event"}\n')
        add(a, '{"kind": "hedge", "ticker": "KXBTC15M-X"}\n')
        add(a, '{"kind": "settled", "pnl_c": -1234.5}\n')
        add(a, '{"kind": "settled", "pnl_c": 260.69}\n')                                       # a win: silent
        add(a, '{"kind": "order", "conn_resu')                                                 # half a line ...
        add(a, 'lt": "unknown"}\n')                                                            # ... completed
        add(side, '{"kind": "error", "msg": "side bot"}\n')
        b = os.path.join(res, "pinrun-live-20260102T000000Z.jsonl")
        time.sleep(0.05)
        add(b, '{"kind": "start", "keep_conn": false}\n')
        time.sleep(0.6)
        stop.set()
        th.join(2)
        text = "\n".join(got)
        print("    --- watcher output ---\n    " + text.replace("\n", "\n    "))
        ck("OLD line" not in text and "old side line" not in text, "lines already in a log at start are not replayed")
        ck("stale_idle" not in text and '"method": "GET"' not in text,
           "routine: stale_idle and GET stale_replaced are skipped")
        ck('"method": "POST", "what": "hedge"' in text, "a stale_replaced on a HEDGE order still alerts")
        ck('"kind": "hedge"' in text and "-1234.5" in text and "260.69" not in text,
           "every insurance record and a loss alert; a win is silent")
        ck(text.count('"conn_result": "unknown"') == 1, "a line written in two pieces alerts once, when complete")
        ck("ladder-live.jsonl | " in text and "side bot" in text, "side-bot logs are watched and named")
        ck("WATCHER: the main bot started a new log" in text and '"keep_conn": false' in text,
           "a restart's new log is announced and read from its first line (a bad start record alerts)")
        ck(len(got) == 7, "exactly the 7 expected lines, nothing else (%d)" % len(got))
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("watchlive selftest: %s" % ("OK" if not fails else "FAILED -- " + fails[0]))
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default=ROOT)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.status:
        return status(a.root)
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):                 # quiet: every printed line is a Monitor event
        bad = selftest()
    if bad:
        print("WATCHER NOT STARTED: " + buf.getvalue().strip().splitlines()[-1], flush=True)
        return 1
    print("WATCHER: self-test OK; watching %s + side bots" % os.path.basename(newest_main(a.root) or "(no main log yet)"),
          flush=True)
    watch(a.root, out=lambda s: print(s, flush=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
