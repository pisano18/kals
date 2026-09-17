#!/usr/bin/env python3
r"""pindesk.py -- the desktop app. START / PAUSE / STOP, and what an owner needs to see.

THE OPERATOR, 2026-09-17: "it should be a proper tool on my desktop with a
dashboard and status viewer and controls. Make it so it's a program on my
desktop and I can click start pause and stop. Make it that simple so anyone can
do it."

WHAT THE THREE BUTTONS DO -- and, more important, what they never do.

  START   removes the stand-down flag (results\pinrun-live.stop), makes sure
          the watchdogs are running (boot_all.ps1), and if the bot is not
          alive starts it through restart_bot.ps1 -- THE ONLY script that may
          start the live bot, with all of its rails (refuses while a bet is
          held and the bot is alive, proves the old pid is gone, never starts
          a second live bot).
  PAUSE   writes the stand-down flag so the watchdog stops relaunching, waits
          for every open bet to SETTLE (research\pinflat.py decides), then
          stops the bot. Nothing is abandoned mid-bet. START resumes.
  STOP    writes the flag and stops the bot NOW. If a bet is open it asks
          first: the bet still settles on Kalshi by itself, but it will not
          be hedged.

Stopping is by pid from results\pinrun-live.pid, and ONLY after that process's
command line has been read and contains `pinrun.py` and `--live`. If Windows
returns the command line empty (it does, for a process the caller cannot open
-- the 2026-09-14 double-bot incident) the app REFUSES to kill and says so,
rather than guess. The collectors are never touched by anything here.

EVERY NUMBER ON THE SCREEN comes from results\pinrun-live-*.jsonl, the log the
live bot writes as it trades. Nothing is modelled. Days are EASTERN. Closes
are counted by close time (rule 4), so twelve coins settling on one quarter
hour are one close, won if the close made money and lost if it did not.

Runs under pythonw (no console); anything that would have been a traceback
goes to results\pindesk.err instead.

    python research/pindesk.py --selftest
    pythonw research/pindesk.py            # what the desktop shortcut runs
"""
import calendar
import ctypes
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from downtime import et_offset                                  # noqa: E402
import pinflat                                                  # noqa: E402

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
KALS = r"C:\kals"
PY = r"C:\Python314\python.exe"
STOP_FLAG = os.path.join(RESULTS, "pinrun-live.stop")
HEARTBEAT = os.path.join(RESULTS, "watch_bot.heartbeat")
ERR_FILE = os.path.join(RESULTS, "pindesk.err")
REFRESH_MS = 5000
STALE_MIN = 20
CREATE_NO_WINDOW = 0x08000000

C = {"bg": "#0F1420", "panel": "#171E2E", "panel2": "#1D2536", "text": "#E6EAF2",
     "muted": "#8A94A8", "gain": "#31C48D", "loss": "#E4572E", "watch": "#F0B429",
     "blue": "#4C8DFF", "grey": "#5B6478"}


# ===========================================================================
# time and tickers
# ===========================================================================
def parse_t(s):
    """'2026-09-16T13:59:31Z' -> epoch. None if it is not that shape."""
    try:
        return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def et_day(epoch):
    """ET calendar day of an epoch, as 'YYYY-MM-DD'."""
    e = epoch + et_offset(epoch)
    return time.strftime("%Y-%m-%d", time.gmtime(e))


def et_str(epoch, fmt="%I:%M %p"):
    e = epoch + et_offset(epoch)
    s = time.strftime(fmt, time.gmtime(e))
    return s.lstrip("0") if fmt.startswith("%I") else s


def et_now_str():
    return et_str(time.time(), "%a %b %d %I:%M:%S %p") + " ET"


def coin(ticker):
    m = re.match(r"^KX([A-Z0-9]+?)15M-", str(ticker or ""))
    return m.group(1) if m else str(ticker or "")[:8]


def close_et(ticker):
    c = pinflat.close_epoch(ticker)
    return et_str(c) if c else "?"


def money(x, sign=True):
    return ("%+.2f" if sign else "%.2f") % x


# ===========================================================================
# the ledger: everything the live logs say, kept current incrementally
# ===========================================================================
def _bank_from_why(why):
    m = re.search(r"bank \$([0-9][0-9,]*\.?[0-9]*)", str(why or ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


class Ledger:
    def __init__(self, results=RESULTS):
        self.results = results
        self.files = {}            # path -> bytes consumed
        self.settled = []          # dicts with epoch, tk, pnl ($), cost, want, result, file
        self.orders = []
        self.signals = []
        self.hedges = []
        self.autosize = []
        self.halts = []
        self.starts = []
        self.newest = None
        self.newest_rows = []      # every row of the newest file (for open positions)

    def refresh(self):
        paths = sorted(glob.glob(os.path.join(self.results, "pinrun-live-*.jsonl")))
        if not paths:
            return False
        changed = False
        newest = max(paths, key=os.path.getmtime)
        if newest != self.newest:
            self.newest = newest
            self.newest_rows = []
            self.files.pop(newest, None)
        for p in paths:
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            done = self.files.get(p, 0)
            if size <= done:
                continue
            with open(p, "rb") as fh:
                fh.seek(done)
                chunk = fh.read()
            # only consume whole lines; a partial line is read next time
            cut = chunk.rfind(b"\n")
            if cut < 0:
                continue
            for line in chunk[:cut + 1].splitlines():
                try:
                    r = json.loads(line.decode("utf-8", "replace"))
                except ValueError:
                    continue
                self._ingest(r, p)
                if p == newest:
                    self.newest_rows.append(r)
            self.files[p] = done + cut + 1
            changed = True
        return changed

    def _ingest(self, r, path):
        k = r.get("kind")
        t = parse_t(r.get("t"))
        f = os.path.basename(path)
        if k == "settled":
            try:
                pnl = float(r.get("pnl_c") or 0) / 100.0
            except (TypeError, ValueError):
                return
            tk = r.get("ticker")
            self.settled.append({"t": t, "tk": tk, "pnl": pnl, "cost": r.get("cost"),
                                 "want": r.get("want"), "result": r.get("result"),
                                 "close": pinflat.close_epoch(tk), "file": f})
        elif k == "order":
            try:
                filled = float(r.get("filled") or 0)
            except (TypeError, ValueError):
                filled = 0.0
            asked = None
            try:
                asked = float((r.get("body") or {}).get("count"))
            except (TypeError, ValueError, AttributeError):
                pass
            self.orders.append({"t": t, "tk": r.get("ticker"), "filled": filled,
                                "asked": asked, "price": r.get("exec_price"),
                                "status": r.get("status"), "swept": bool(r.get("swept")),
                                "file": f})
        elif k == "signal":
            self.signals.append({"t": t, "tk": r.get("ticker"), "want": r.get("want"),
                                 "price": r.get("price"), "edge_c": r.get("edge_c"),
                                 "size": r.get("size"), "take_n": r.get("take_n"),
                                 "tau": r.get("tau"), "file": f})
        elif k in ("hedge", "hedge_alarm"):
            self.hedges.append({"t": t, "kind": k, "tk": r.get("ticker"),
                                "belief": r.get("belief"), "n": r.get("n"),
                                "price": r.get("price"), "status": r.get("status"),
                                "tau": r.get("tau"), "file": f})
        elif k == "autosize":
            self.autosize.append({"t": t, "size": r.get("new"), "bank": _bank_from_why(r.get("why")),
                                  "file": f})
        elif k in ("halt", "end"):
            self.halts.append({"t": t, "kind": k, "why": r.get("why"), "file": f})
        elif k == "start":
            self.starts.append({"t": t, "file": f, "size": r.get("size"),
                                "hedge": r.get("hedge_belief"), "tau_max": r.get("tau_max")})

    # ---- aggregations ----
    @staticmethod
    def by_close(settled):
        """{close_epoch: net $} -- one entry per CLOSE (rule 4)."""
        out = {}
        for s in settled:
            key = s["close"] if s["close"] is not None else s["t"]
            out[key] = out.get(key, 0.0) + s["pnl"]
        return out

    @staticmethod
    def summary(settled):
        closes = Ledger.by_close(settled)
        won = sum(1 for v in closes.values() if v >= 0)
        lost = len(closes) - won
        net = sum(closes.values())
        worst = min(closes.values()) if closes else 0.0
        best = max(closes.values()) if closes else 0.0
        return {"closes": len(closes), "won": won, "lost": lost, "net": net,
                "worst": worst, "best": best, "markets": len(settled),
                "loss_rate": (100.0 * lost / len(closes)) if closes else None}

    def settled_on(self, day):
        return [s for s in self.settled if s["t"] and et_day(s["close"] or s["t"]) == day]

    def fills_on(self, day):
        return [o for o in self.orders if o["t"] and et_day(o["t"]) == day]

    @staticmethod
    def fill_stats(orders):
        f = [o for o in orders if o["filled"] > 0]
        zero = sum(1 for o in orders if o["filled"] <= 0)
        contracts = sum(o["filled"] for o in f)
        pcts = sorted(o["filled"] / o["asked"] for o in f if o["asked"])
        med = pcts[len(pcts) // 2] if pcts else None
        return {"orders": len(orders), "fills": len(f), "zero": zero,
                "contracts": contracts, "median_pct": med}

    def days(self):
        seen = {}
        for s in self.settled:
            if s["t"]:
                seen.setdefault(et_day(s["close"] or s["t"]), True)
        for o in self.orders:
            if o["t"]:
                seen.setdefault(et_day(o["t"]), True)
        return sorted(seen)

    def bank(self):
        for a in reversed(self.autosize):
            if a["bank"] is not None:
                return a
        return None

    def contracts_for(self, ticker):
        return sum(o["filled"] for o in self.orders if o["tk"] == ticker)

    def last_halt(self):
        return self.halts[-1] if self.halts else None

    def run_settled(self):
        f = os.path.basename(self.newest) if self.newest else None
        return [s for s in self.settled if s["file"] == f]

    def losing_closes(self):
        """Every losing close, all time, newest first: (close, net, coins)."""
        rows = {}
        for s in self.settled:
            key = s["close"] if s["close"] is not None else s["t"]
            d = rows.setdefault(key, {"net": 0.0, "legs": []})
            d["net"] += s["pnl"]
            d["legs"].append(s)
        out = [(k, v["net"], v["legs"]) for k, v in rows.items() if v["net"] < 0]
        out.sort(key=lambda x: -(x[0] or 0))
        return out


# ===========================================================================
# health
# ===========================================================================
def _file_age_s(path):
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _ram_free_gb():
    try:
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1e9
    except Exception:                                   # noqa: BLE001
        return None


def recorder_ok(root):
    """Same proof of life restart_bot.ps1 uses: the previous UTC hour landed
    with bytes, and a file is open for the hour in progress."""
    now = time.time()
    prev = time.strftime("%Y%m%dT%H", time.gmtime(now - 3600)) + ".jsonl.gz"
    cur = time.strftime("%Y%m%dT%H", time.gmtime(now)) + ".jsonl.gz"
    pb = 0
    cn = 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f == prev:
                try:
                    pb += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
            elif f == cur:
                cn += 1
    return pb > 0 and cn > 0, pb, cn


def read_flag():
    try:
        with open(STOP_FLAG, encoding="utf-8") as fh:
            return fh.read().strip() or "(no reason)"
    except OSError:
        return None


def health(ledger):
    h = {}
    pid = pinflat.live_pid()
    h["pid"] = pid
    h["alive"] = bool(pid) and pinflat.pid_alive(pid)
    h["flag"] = read_flag()
    ages = [a for a in (_file_age_s(ledger.newest) if ledger.newest else None,
                        _file_age_s(os.path.join(RESULTS, "pinrun-live.out"))) if a is not None]
    h["quiet_s"] = min(ages) if ages else None
    h["watchdog_s"] = _file_age_s(HEARTBEAT)
    try:
        with open(os.path.join(KALS, "logs", "run_all.pid")) as fh:
            h["run_all"] = pinflat.pid_alive(int(fh.read().strip()))
    except (OSError, ValueError):
        h["run_all"] = None
    h["kalshi_ok"], h["kalshi_prev"], _ = recorder_ok(os.path.join(KALS, "kalshi_data"))
    h["feeds_ok"], h["feeds_prev"], _ = recorder_ok(os.path.join(KALS, "feed_data"))
    try:
        h["disk_gb"] = shutil.disk_usage("C:\\").free / 1e9
    except OSError:
        h["disk_gb"] = None
    h["ram_gb"] = _ram_free_gb()
    try:
        st, d = pinflat.check()
        h["flat"] = st
        h["open"] = d.get("open") or {}
    except Exception as e:                              # noqa: BLE001
        h["flat"] = "UNKNOWN"
        h["open"] = {}
        h["flat_err"] = str(e)[:120]
    h["halt"] = ledger.last_halt()
    return h


def status_of(h, now=None):
    """(state, headline, detail, colour) for the banner."""
    now = time.time() if now is None else now
    n_open = sum(v if isinstance(v, (int, float)) else (v.get("n", 1) if isinstance(v, dict) else 1)
                 for v in (h.get("open") or {}).values())
    if h["alive"]:
        if h.get("flag"):
            if n_open:
                return ("PAUSING", "PAUSING -- finishing %d open bet%s first" % (n_open, "" if n_open == 1 else "s"),
                        "No new bets. It stops by itself when they settle.", C["watch"])
            return ("PAUSING", "STOPPING -- stand-down flag is set", "The bot will be stopped in a moment.", C["watch"])
        q = h.get("quiet_s")
        if q is not None and q > STALE_MIN * 60:
            return ("STALE", "RUNNING BUT QUIET for %d min" % int(q / 60),
                    "Nothing written to its log. The watchdog restarts it after %d min of silence." % 25, C["watch"])
        return ("TRADING", "TRADING  (pid %s)" % h["pid"],
                "%d open bet%s" % (n_open, "" if n_open == 1 else "s") if n_open else "No open bets right now.", C["gain"])
    if h.get("flag"):
        why = h["flag"]
        word = "PAUSED" if "PAUSE" in why.upper() else "STOPPED"
        return (word, "%s by you" % word, "Press START to trade again. (%s)" % why, C["grey"])
    halt = h.get("halt")
    if halt and halt.get("kind") == "halt" and halt.get("why") and \
            re.search(r"loss COUNT brake|loss abort|DRAWDOWN brake", halt["why"]):
        age = (now - halt["t"]) / 60 if halt.get("t") else None
        left = max(0, 15 - age) if age is not None else None
        return ("BRAKE", "STOPPED BY A SAFETY BRAKE",
                "%s%s" % (halt["why"][:110], (" -- watchdog restarts in ~%d min, or press START now." % left) if left is not None else ""),
                C["loss"])
    wd = h.get("watchdog_s")
    if wd is None or wd > 120:
        return ("DOWN", "NOT RUNNING -- and the watchdog is not running either",
                "Press START. It starts the watchdog and the bot.", C["loss"])
    return ("DOWN", "NOT RUNNING -- watchdog is bringing it back",
            "Last watchdog check %d s ago. If this lasts more than a few minutes, press START." % int(wd), C["loss"])


# ===========================================================================
# controls
# ===========================================================================
def _ps(script, *args, timeout=180):
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       creationflags=CREATE_NO_WINDOW, cwd=REPO)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _cmdline(pid):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % int(pid)],
                       capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
    return (r.stdout or "").strip()


def terminate_live_bot(log):
    """Stop the live bot by pid, only after proving what that pid is."""
    pid = pinflat.live_pid()
    if not pid or not pinflat.pid_alive(pid):
        log("bot is not running; nothing to stop")
        return True
    cl = _cmdline(pid)
    if "pinrun.py" not in cl or "--live" not in cl:
        log("REFUSING to stop pid %s: its command line reads %r -- cannot prove it is the live bot. "
            "Stop it from a terminal: Stop-Process -Id %s -Force" % (pid, cl[:80], pid))
        return False
    r = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True,
                       creationflags=CREATE_NO_WINDOW)
    time.sleep(2)
    if pinflat.pid_alive(pid):
        log("taskkill did not stop pid %s: %s" % (pid, (r.stdout + r.stderr).strip()[:120]))
        return False
    log("stopped live bot pid %s" % pid)
    return True


def write_flag(reason):
    with open(STOP_FLAG, "w", encoding="utf-8") as fh:
        fh.write("%s at %s" % (reason, et_now_str()))


def clear_flag():
    try:
        os.remove(STOP_FLAG)
    except OSError:
        pass


def do_start(log):
    clear_flag()
    log("stand-down flag cleared")
    code, out = _ps(os.path.join(REPO, "boot_all.ps1"), "-NoArms")
    for l in out.strip().splitlines()[-3:]:
        log("boot_all: " + l.strip())
    pid = pinflat.live_pid()
    if pid and pinflat.pid_alive(pid):
        log("bot already running, pid %s -- watchdog re-armed" % pid)
        return
    log("starting the bot through restart_bot.ps1 ...")
    code, out = _ps(os.path.join(REPO, "restart_bot.ps1"))
    for l in out.strip().splitlines():
        l = l.strip()
        if l and not l.startswith("*") and "transcript" not in l.lower():
            log("restart_bot: " + l)
    log("restart_bot exit code %d" % code)


def do_pause(log, set_status):
    write_flag("operator PAUSE")
    log("stand-down flag written; watchdog will not relaunch")
    while True:
        st, d = pinflat.check()
        if not d.get("alive"):
            log("bot is not running; paused")
            return
        if st == "FLAT":
            break
        opn = d.get("open") or {}
        soon = []
        for tk in opn:
            c = pinflat.close_epoch(tk)
            soon.append("%s closes %s" % (coin(tk), close_et(tk)) if c else coin(tk))
        set_status("PAUSING -- waiting for %d open bet(s): %s" % (len(opn), ", ".join(soon)[:80]))
        time.sleep(5)
    terminate_live_bot(log)


def do_stop(log):
    write_flag("operator STOP")
    log("stand-down flag written; watchdog will not relaunch")
    terminate_live_bot(log)


# ===========================================================================
# GUI
# ===========================================================================
def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    ledger = Ledger()
    ledger.refresh()

    root = tk.Tk()
    root.title("Pin Bot")
    root.configure(bg=C["bg"])
    root.geometry("1180x760")
    root.minsize(900, 600)

    def _tk_err(*a):
        with open(ERR_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s tk callback:\n%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), "".join(traceback.format_exception(*a))))
    root.report_callback_exception = _tk_err

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=C["bg"], foreground=C["text"], fieldbackground=C["panel"])
    st.configure("TFrame", background=C["bg"])
    st.configure("Panel.TFrame", background=C["panel"])
    st.configure("TLabel", background=C["bg"], foreground=C["text"], font=("Segoe UI", 10))
    st.configure("Panel.TLabel", background=C["panel"], foreground=C["text"], font=("Segoe UI", 10))
    st.configure("Muted.TLabel", background=C["panel"], foreground=C["muted"], font=("Segoe UI", 9))
    st.configure("Big.TLabel", background=C["panel"], foreground=C["text"], font=("Segoe UI", 20, "bold"))
    st.configure("TNotebook", background=C["bg"], borderwidth=0)
    st.configure("TNotebook.Tab", background=C["panel"], foreground=C["muted"], padding=(14, 6), font=("Segoe UI", 10, "bold"))
    st.map("TNotebook.Tab", background=[("selected", C["panel2"])], foreground=[("selected", C["text"])])
    st.configure("Treeview", background=C["panel"], fieldbackground=C["panel"], foreground=C["text"],
                 rowheight=24, font=("Consolas", 10), borderwidth=0)
    st.configure("Treeview.Heading", background=C["panel2"], foreground=C["muted"], font=("Segoe UI", 9, "bold"))
    st.map("Treeview", background=[("selected", C["blue"])])

    # ---- banner ----
    banner = tk.Frame(root, bg=C["grey"], height=96)
    banner.pack(fill="x", padx=12, pady=(12, 6))
    banner.pack_propagate(False)
    head = tk.Label(banner, text="...", bg=C["grey"], fg="white", font=("Segoe UI", 22, "bold"), anchor="w")
    head.pack(fill="x", padx=16, pady=(12, 0))
    sub = tk.Label(banner, text="", bg=C["grey"], fg="white", font=("Segoe UI", 11), anchor="w")
    sub.pack(fill="x", padx=16)

    btns = tk.Frame(root, bg=C["bg"])
    btns.pack(fill="x", padx=12, pady=(0, 6))

    def big_button(txt, colour, cmd):
        b = tk.Button(btns, text=txt, command=cmd, bg=colour, fg="white", activebackground=colour,
                      activeforeground="white", font=("Segoe UI", 14, "bold"), width=11, height=1,
                      relief="flat", cursor="hand2", bd=0)
        b.pack(side="left", padx=(0, 10))
        return b

    busy = {"on": False}

    def guarded(fn):
        def run():
            if busy["on"]:
                return
            busy["on"] = True
            for b in (b_start, b_pause, b_stop):
                b.configure(state="disabled")

            def worker():
                try:
                    fn()
                except Exception as e:                  # noqa: BLE001
                    console_log("ERROR: %s" % e)
                    with open(ERR_FILE, "a", encoding="utf-8") as fh:
                        fh.write(traceback.format_exc())
                finally:
                    busy["on"] = False
                    root.after(0, lambda: [b.configure(state="normal") for b in (b_start, b_pause, b_stop)])
                    root.after(500, tick)
            threading.Thread(target=worker, daemon=True).start()
        return run

    def on_start():
        do_start(console_log)

    def on_pause():
        do_pause(console_log, lambda s: root.after(0, lambda: sub.configure(text=s)))

    def on_stop():
        h = health(ledger)
        if h["alive"] and h.get("open"):
            n = len(h["open"])
            ok = messagebox.askyesno("Stop now?",
                                     "The bot is holding %d open bet%s. They still settle on Kalshi by "
                                     "themselves, but the bot will not be there to hedge them.\n\n"
                                     "PAUSE waits for them to settle first. Stop anyway?" % (n, "" if n == 1 else "s"))
            if not ok:
                console_log("stop cancelled")
                return
        do_stop(console_log)

    b_start = big_button("▶  START", C["gain"], guarded(on_start))
    b_pause = big_button("⏸  PAUSE", C["watch"], guarded(on_pause))
    b_stop = big_button("■  STOP", C["loss"], guarded(on_stop))
    tk.Button(btns, text="Open Deck (web view)", command=lambda: os.startfile(os.path.join(REPO, "open_deck.cmd")),
              bg=C["panel2"], fg=C["text"], font=("Segoe UI", 10), relief="flat", cursor="hand2", bd=0,
              padx=10).pack(side="left", padx=(20, 6))
    tk.Button(btns, text="Refresh", command=lambda: tick(force=True), bg=C["panel2"], fg=C["text"],
              font=("Segoe UI", 10), relief="flat", cursor="hand2", bd=0, padx=10).pack(side="left")
    clock = tk.Label(btns, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 10))
    clock.pack(side="right")

    # ---- health strip ----
    strip = tk.Frame(root, bg=C["bg"])
    strip.pack(fill="x", padx=12, pady=(0, 6))
    chips = {}

    def chip(key, title):
        f = tk.Frame(strip, bg=C["panel"], padx=10, pady=6)
        f.pack(side="left", padx=(0, 6), fill="x", expand=True)
        tk.Label(f, text=title, bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        v = tk.Label(f, text="...", bg=C["panel"], fg=C["text"], font=("Segoe UI", 11, "bold"))
        v.pack(anchor="w")
        chips[key] = v

    for key, title in (("bot", "BOT"), ("wd", "WATCHDOG"), ("rec", "RECORDERS"), ("disk", "DISK FREE"),
                       ("ram", "RAM FREE"), ("bank", "BANK"), ("size", "SIZE PER BET")):
        chip(key, title)

    # ---- tabs ----
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # NOW tab
    now_tab = ttk.Frame(nb)
    nb.add(now_tab, text="  Now  ")
    tiles = tk.Frame(now_tab, bg=C["bg"])
    tiles.pack(fill="x", pady=(8, 6))
    tile_vals = {}

    def tile(key, title):
        f = tk.Frame(tiles, bg=C["panel"], padx=12, pady=8)
        f.pack(side="left", padx=(0, 6), fill="x", expand=True)
        tk.Label(f, text=title, bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        v = tk.Label(f, text="...", bg=C["panel"], fg=C["text"], font=("Segoe UI", 18, "bold"))
        v.pack(anchor="w")
        s = tk.Label(f, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9))
        s.pack(anchor="w")
        tile_vals[key] = (v, s)

    for key, title in (("today", "TODAY (ET)"), ("yday", "YESTERDAY"), ("run", "THIS RUN"), ("all", "ALL TIME")):
        tile(key, title)

    lower = tk.Frame(now_tab, bg=C["bg"])
    lower.pack(fill="both", expand=True)

    def table(parent, cols, widths, height=8, title=None):
        f = tk.Frame(parent, bg=C["bg"])
        if title:
            tk.Label(f, text=title, bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        tv = ttk.Treeview(f, columns=cols, show="headings", height=height)
        for c_, w in zip(cols, widths):
            tv.heading(c_, text=c_)
            tv.column(c_, width=w, anchor="w", stretch=(w > 120))
        tv.pack(fill="both", expand=True)
        tv.tag_configure("gain", foreground=C["gain"])
        tv.tag_configure("loss", foreground=C["loss"])
        tv.tag_configure("watch", foreground=C["watch"])
        tv.tag_configure("muted", foreground=C["muted"])
        return f, tv

    left = tk.Frame(lower, bg=C["bg"])
    left.pack(side="left", fill="both", expand=True, padx=(0, 6))
    right = tk.Frame(lower, bg=C["bg"])
    right.pack(side="left", fill="both", expand=True)

    f_open, tv_open = table(left, ("Open bet", "Side", "Contracts", "Paid", "Closes at (ET)", "In"),
                            (110, 60, 80, 70, 110, 60), height=4, title="OPEN BETS")
    f_open.pack(fill="x")
    f_tr, tv_tr = table(left, ("Settled (ET)", "Coin", "Close", "Side", "Paid", "Contracts", "Result", "$"),
                        (110, 60, 80, 50, 60, 80, 60, 80), height=14, title="LAST SETTLED BETS")
    f_tr.pack(fill="both", expand=True)
    f_sig, tv_sig = table(right, ("Seen (ET)", "Coin", "Close", "Side", "Price", "Edge c", "Wanted", "Got"),
                          (110, 60, 80, 50, 60, 60, 70, 70), height=10, title="LAST SIGNALS (what it tried to buy)")
    f_sig.pack(fill="both", expand=True)
    f_hg, tv_hg = table(right, ("When (ET)", "Coin", "What", "Belief", "Contracts", "Price"),
                        (110, 60, 90, 70, 80, 70), height=5, title="HEDGES (insurance bought when a bet turned)")
    f_hg.pack(fill="x")

    # DAYS tab
    days_tab = ttk.Frame(nb)
    nb.add(days_tab, text="  Days  ")
    f_days, tv_days = table(days_tab, ("Day (ET)", "Closes", "Won", "Lost", "Net $", "$ / close", "Worst close $",
                                       "Orders", "Filled", "Zero-fills", "Contracts", "Median fill %"),
                            (100, 60, 60, 60, 80, 80, 100, 60, 60, 80, 90, 100), height=12, title="EACH DAY, NEWEST FIRST")
    f_days.pack(fill="x", padx=2, pady=(8, 4))
    tk.Label(days_tab, text="MONEY MADE, ADDED UP OVER TIME (every settled bet, all time)", bg=C["bg"], fg=C["muted"],
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
    chart = tk.Canvas(days_tab, bg=C["panel"], highlightthickness=0, height=220)
    chart.pack(fill="both", expand=True, padx=2, pady=(0, 6))

    # LOSSES tab
    loss_tab = ttk.Frame(nb)
    nb.add(loss_tab, text="  Losses  ")
    tk.Label(loss_tab, text="Every losing close, all time, newest first. A close is one quarter-hour; all coins settling "
                            "on it count as one bet.", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 2))
    f_loss, tv_loss = table(loss_tab, ("Close (ET)", "Day", "Net $", "Coins", "Legs", "Paid (avg)"),
                            (140, 100, 90, 200, 60, 90), height=24)
    f_loss.pack(fill="both", expand=True, padx=2)

    # LOG tab
    log_tab = ttk.Frame(nb)
    nb.add(log_tab, text="  Log  ")
    tk.Label(log_tab, text="WHAT THIS APP DID", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
    console = tk.Text(log_tab, height=8, bg=C["panel"], fg=C["text"], font=("Consolas", 10), relief="flat", wrap="word")
    console.pack(fill="x", padx=2)
    tk.Label(log_tab, text="THE BOT'S OWN CONSOLE (last lines) and THE WATCHDOG'S LOG", bg=C["bg"], fg=C["muted"],
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
    tails = tk.Text(log_tab, bg=C["panel"], fg=C["muted"], font=("Consolas", 9), relief="flat", wrap="none")
    tails.pack(fill="both", expand=True, padx=2, pady=(0, 6))

    def console_log(msg):
        line = "%s  %s\n" % (et_str(time.time(), "%I:%M:%S %p"), msg)

        def _w():
            console.insert("end", line)
            console.see("end")
        root.after(0, _w)
        with open(os.path.join(RESULTS, "pindesk.log"), "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%S") + "  " + msg + "\n")

    # ---- rendering ----
    def fill(tv, rows):
        tv.delete(*tv.get_children())
        for vals, tag in rows:
            tv.insert("", "end", values=vals, tags=(tag,) if tag else ())

    def draw_chart():
        chart.delete("all")
        pts = sorted((s["t"], s["pnl"]) for s in ledger.settled if s["t"])
        if len(pts) < 2:
            chart.create_text(20, 20, text="not enough settled bets yet", fill=C["muted"], anchor="w")
            return
        W = max(chart.winfo_width(), 200)
        H = max(chart.winfo_height(), 100)
        m = {"l": 60, "r": 16, "t": 14, "b": 24}
        cum = []
        tot = 0.0
        for t, p in pts:
            tot += p
            cum.append((t, tot))
        t0, t1 = cum[0][0], cum[-1][0]
        lo = min(0.0, min(v for _, v in cum))
        hi = max(0.0, max(v for _, v in cum))
        if hi - lo < 1e-9:
            hi = lo + 1
        def X(t):
            return m["l"] + (t - t0) / max(1, t1 - t0) * (W - m["l"] - m["r"])
        def Y(v):
            return m["t"] + (hi - v) / (hi - lo) * (H - m["t"] - m["b"])
        chart.create_line(m["l"], Y(0), W - m["r"], Y(0), fill=C["grey"], dash=(3, 3))
        for v in (lo, hi, 0.0):
            chart.create_text(m["l"] - 6, Y(v), text="$%.0f" % v, fill=C["muted"], anchor="e", font=("Segoe UI", 8))
        # day ticks
        d0 = et_day(t0)
        last = None
        for t, _ in cum:
            d = et_day(t)
            if d != last:
                x = X(t)
                chart.create_line(x, m["t"], x, H - m["b"], fill=C["panel2"])
                chart.create_text(x + 2, H - m["b"] + 10, text=d[5:], fill=C["muted"], anchor="w", font=("Segoe UI", 8))
                last = d
        coords = []
        for t, v in cum:
            coords += [X(t), Y(v)]
        chart.create_line(*coords, fill=C["gain"] if tot >= 0 else C["loss"], width=2)
        chart.create_text(W - m["r"], m["t"] + 4, text="$%+.2f" % tot, fill=C["text"], anchor="ne", font=("Segoe UI", 12, "bold"))
        _ = d0

    def render(h):
        state, hl, det, colour = status_of(h)
        banner.configure(bg=colour)
        head.configure(text=hl, bg=colour)
        sub.configure(text=det, bg=colour)
        clock.configure(text=et_now_str())

        # chips
        q = h.get("quiet_s")
        chips["bot"].configure(text=("alive, wrote %ds ago" % q) if h["alive"] and q is not None else ("alive" if h["alive"] else "not running"),
                               fg=C["gain"] if h["alive"] else C["loss"])
        wd = h.get("watchdog_s")
        chips["wd"].configure(text=("checked %ds ago" % wd) if wd is not None and wd < 120 else "NOT RUNNING",
                              fg=C["gain"] if wd is not None and wd < 120 else C["loss"])
        rec_ok = h["kalshi_ok"] and h["feeds_ok"]
        chips["rec"].configure(text="both writing" if rec_ok else ("kalshi %s, feeds %s" % ("ok" if h["kalshi_ok"] else "STOPPED?", "ok" if h["feeds_ok"] else "STOPPED?")),
                               fg=C["gain"] if rec_ok else C["loss"])
        dg = h.get("disk_gb")
        chips["disk"].configure(text=("%.1f GB" % dg) if dg is not None else "?",
                                fg=C["loss"] if dg is not None and dg < 6 else (C["watch"] if dg is not None and dg < 10 else C["text"]))
        rg = h.get("ram_gb")
        chips["ram"].configure(text=("%.1f GB" % rg) if rg is not None else "?",
                               fg=C["loss"] if rg is not None and rg < 1.5 else C["text"])
        b = ledger.bank()
        chips["bank"].configure(text=("$%.2f" % b["bank"]) if b else "?")
        chips["size"].configure(text=("%g contracts" % b["size"]) if b and b.get("size") else "?")

        # tiles
        today = et_day(time.time())
        yday = et_day(time.time() - 86400)
        for key, rows in (("today", ledger.settled_on(today)), ("yday", ledger.settled_on(yday)),
                          ("run", ledger.run_settled()), ("all", ledger.settled)):
            s = Ledger.summary(rows)
            v, sub_ = tile_vals[key]
            v.configure(text="$%+.2f" % s["net"], fg=C["gain"] if s["net"] >= 0 else C["loss"])
            extra = ""
            if key in ("today", "yday"):
                fs = Ledger.fill_stats(ledger.fills_on(today if key == "today" else yday))
                extra = "  |  %d fills, %g contracts" % (fs["fills"], fs["contracts"])
            if s["closes"]:
                sub_.configure(text="%d closes (%d bets): %d won, %d lost (%.1f%%)%s" % (
                    s["closes"], s["markets"], s["won"], s["lost"], s["loss_rate"], extra))
            else:
                sub_.configure(text="no settled bets" + extra)

        # open bets
        rows = []
        opn = pinflat.positions(ledger.newest_rows) if h["alive"] else {}
        for tk_, n in opn.items():
            c = pinflat.close_epoch(tk_)
            sig = next((s for s in reversed(ledger.signals) if s["tk"] == tk_), None)
            paid = next((o["price"] for o in reversed(ledger.orders) if o["tk"] == tk_ and o["filled"] > 0), None)
            left = ("%d s" % max(0, c - time.time())) if c else "?"
            rows.append(((coin(tk_) + "  " + tk_.split("-")[-1], (sig or {}).get("want", "?").upper(),
                          "%g" % ledger.contracts_for(tk_), ("%.1fc" % (100 * paid)) if paid else "?",
                          close_et(tk_), left), "watch"))
        fill(tv_open, rows or [(("none", "", "", "", "", ""), "muted")])

        # settled
        rows = []
        for s in list(reversed(ledger.settled))[:60]:
            won = s["pnl"] >= 0
            rows.append(((et_str(s["t"], "%m/%d %I:%M %p") if s["t"] else "?", coin(s["tk"]), close_et(s["tk"]),
                          str(s["want"]).upper(), ("%.1fc" % (100 * float(s["cost"]))) if s["cost"] is not None else "?",
                          "%g" % ledger.contracts_for(s["tk"]), "WON" if won else "LOST", money(s["pnl"])),
                         "gain" if won else "loss"))
        fill(tv_tr, rows)

        # signals -- each paired with ITS order: the first unclaimed order on
        # the same ticker at or after the signal (two signals on one ticker can
        # land in the same second, so "nearest in time" pairs them wrongly).
        rows = []
        recent_sig = list(reversed(ledger.signals))[:40]
        pool = [o for o in ledger.orders[-400:]]
        claimed = set()
        for s in reversed(recent_sig):
            s["_o"] = None
            for i, o in enumerate(pool):
                if i in claimed or o["tk"] != s["tk"] or not o["t"] or not s["t"] or o["t"] < s["t"] or o["t"] - s["t"] > 10:
                    continue
                claimed.add(i)
                s["_o"] = o
                break
        for s in recent_sig:
            o = s.get("_o")
            got = ("%g" % o["filled"]) if o else "-"
            tag = "gain" if (o and o["filled"] > 0) else ("muted" if o else "watch")
            rows.append(((et_str(s["t"], "%m/%d %I:%M:%S %p") if s["t"] else "?", coin(s["tk"]), close_et(s["tk"]),
                          str(s["want"]).upper(), "%.1fc" % (100 * float(s["price"] or 0)), "%+.2f" % float(s["edge_c"] or 0),
                          "%g" % float(s["take_n"] or s["size"] or 0), got), tag))
        fill(tv_sig, rows)

        # hedges
        rows = []
        for g in list(reversed(ledger.hedges))[:20]:
            rows.append(((et_str(g["t"], "%m/%d %I:%M %p") if g["t"] else "?", coin(g["tk"]),
                          "bought insurance" if g["kind"] == "hedge" else "alarm",
                          ("%.0f%%" % (100 * float(g["belief"]))) if g.get("belief") is not None else "?",
                          "%g" % float(g.get("n") or 0), ("%.0fc" % (100 * float(g["price"]))) if g.get("price") else "-"),
                         "watch" if g["kind"] == "hedge" else "muted"))
        fill(tv_hg, rows or [(("none yet", "", "", "", "", ""), "muted")])

        # days
        rows = []
        for d in reversed(ledger.days()):
            s = Ledger.summary(ledger.settled_on(d))
            fs = Ledger.fill_stats(ledger.fills_on(d))
            rows.append(((d, s["closes"], s["won"], s["lost"], money(s["net"]),
                          money(s["net"] / s["closes"]) if s["closes"] else "-", money(s["worst"]),
                          fs["orders"], fs["fills"], fs["zero"], "%g" % fs["contracts"],
                          ("%.0f%%" % (100 * fs["median_pct"])) if fs["median_pct"] is not None else "-"),
                         "gain" if s["net"] >= 0 else "loss"))
        fill(tv_days, rows)
        draw_chart()

        # losses
        rows = []
        for close, net, legs in ledger.losing_closes():
            coins = ", ".join(sorted({coin(l["tk"]) for l in legs}))
            paid = [float(l["cost"]) for l in legs if l["cost"] is not None]
            rows.append(((et_str(close, "%m/%d %I:%M %p") if close else "?", et_day(close) if close else "?",
                          money(net), coins, len(legs), ("%.1fc" % (100 * sum(paid) / len(paid))) if paid else "?"), "loss"))
        fill(tv_loss, rows or [(("no losing closes", "", "", "", "", ""), "muted")])

        # tails
        try:
            with open(os.path.join(RESULTS, "pinrun-live.out"), encoding="utf-8", errors="replace") as fh:
                bot_tail = fh.readlines()[-25:]
        except OSError:
            bot_tail = ["(no bot console yet)\n"]
        try:
            with open(os.path.join(RESULTS, "watch_bot.log"), encoding="utf-8", errors="replace") as fh:
                wd_tail = fh.readlines()[-8:]
        except OSError:
            wd_tail = ["(no watchdog log yet)\n"]
        tails.configure(state="normal")
        tails.delete("1.0", "end")
        tails.insert("end", "".join(bot_tail) + "\n---- watchdog ----\n" + "".join(wd_tail))
        tails.see("end")
        tails.configure(state="disabled")

    pending = {"h": None}

    def tick(force=False):
        def worker():
            try:
                ledger.refresh()
                pending["h"] = health(ledger)
            except Exception:                            # noqa: BLE001
                with open(ERR_FILE, "a", encoding="utf-8") as fh:
                    fh.write(traceback.format_exc())
            root.after(0, apply)

        def apply():
            if pending["h"] is not None:
                try:
                    render(pending["h"])
                except Exception:                        # noqa: BLE001
                    with open(ERR_FILE, "a", encoding="utf-8") as fh:
                        fh.write(traceback.format_exc())
        threading.Thread(target=worker, daemon=True).start()

    def loop():
        tick()
        root.after(REFRESH_MS, loop)

    console_log("Pin Bot opened")
    loop()
    root.mainloop()


# ===========================================================================
def selftest():
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pindesk selftest: FAILED -- " + msg)

    ck(parse_t("2026-09-16T13:59:31Z") == calendar.timegm((2026, 9, 16, 13, 59, 31)), "ISO time parses")
    ck(parse_t(None) is None and parse_t("junk") is None, "NULL: junk time is None")
    # 2026-09-17 03:00Z is 2026-09-16 11 PM ET -- the UTC day cut at 8 PM ET was mistake 3 in the handoff
    e = calendar.timegm((2026, 9, 17, 3, 0, 0))
    ck(et_day(e) == "2026-09-16", "03:00Z on the 17th is still the 16th in ET")
    ck(et_str(e) == "11:00 PM", "and reads 11:00 PM")
    ck(coin("KXBNB15M-26SEP161000-00") == "BNB" and coin("KXBTC15M-26SEP161000-00") == "BTC", "coin from ticker")
    ck(close_et("KXBNB15M-26SEP161000-00") == "6:00 AM", "close 10:00Z is 6:00 AM ET")
    ck(_bank_from_why("bank $500.67") == 500.67 and _bank_from_why("bank $1,234.50") == 1234.5, "bank parses from the autosize reason")
    ck(_bank_from_why("size cap") is None, "NULL: no bank in the reason")

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "pinrun-live-20260916T135734Z.jsonl")
        c1 = "KXBNB15M-26SEP161000-00"          # closes 10:00Z
        c2 = "KXBTC15M-26SEP161000-00"          # SAME close
        c3 = "KXSOL15M-26SEP161015-15"          # 10:15Z
        rows = [
            {"kind": "start", "t": "2026-09-16T09:00:00Z", "size": 20},
            {"kind": "autosize", "t": "2026-09-16T09:00:01Z", "old": 20, "new": 85, "why": "bank $500.67"},
            {"kind": "signal", "t": "2026-09-16T09:59:30Z", "ticker": c1, "want": "no", "price": 0.98, "edge_c": 1.5, "size": 85, "take_n": 85, "tau": 29},
            {"kind": "order", "t": "2026-09-16T09:59:31Z", "ticker": c1, "filled": 85.0, "exec_price": 0.979, "status": "executed", "body": {"count": "85.00"}},
            {"kind": "order", "t": "2026-09-16T09:59:35Z", "ticker": c2, "filled": 40.0, "exec_price": 0.97, "status": "executed", "body": {"count": "80.00"}},
            {"kind": "order", "t": "2026-09-16T10:14:35Z", "ticker": c3, "filled": 0.0, "status": "canceled", "body": {"count": "50.00"}},
            {"kind": "settled", "t": "2026-09-16T10:00:20Z", "ticker": c1, "want": "no", "result": "no", "cost": 0.979, "pnl_c": 166.26, "realised": 1.6626},
            {"kind": "settled", "t": "2026-09-16T10:00:21Z", "ticker": c2, "want": "no", "result": "yes", "cost": 0.97, "pnl_c": -3880.0, "realised": -37.1374},
            {"kind": "hedge_alarm", "t": "2026-09-16T10:14:40Z", "ticker": c3, "belief": 0.5, "n": 1.0, "tau": 20},
            {"kind": "halt", "t": "2026-09-16T10:30:00Z", "why": "loss COUNT brake: 2 losing trades this run >= 2"},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows[:-1]:
                fh.write(json.dumps(r) + "\n")
            fh.write('{"kind": "close_summary", "t": "2026-09-16T10:1')      # cut off mid-line
        L = Ledger(results=td)
        ck(L.refresh(), "first refresh reads the file")
        ck(len(L.settled) == 2 and len(L.orders) == 3 and len(L.signals) == 1 and len(L.hedges) == 1, "every kind was ingested")
        ck(L.halts == [], "the truncated tail line is not read, and nothing after it is")
        s = Ledger.summary(L.settled)
        ck(s["closes"] == 1 and s["lost"] == 1 and s["won"] == 0 and abs(s["net"] - (-37.1374)) < 1e-6,
           "RULE 4: two coins on one close are ONE close; it lost, net -$37.14")
        ck(s["markets"] == 2 and s["worst"] < 0, "two markets, worst close is negative")
        fs = Ledger.fill_stats(L.orders)
        ck(fs["orders"] == 3 and fs["fills"] == 2 and fs["zero"] == 1 and fs["contracts"] == 125.0, "fill stats count fills, zero-fills and contracts")
        ck(fs["median_pct"] == 1.0, "median fill share of (1.00, 0.50) is the upper middle, 1.00")
        ck(L.bank()["bank"] == 500.67 and L.bank()["size"] == 85, "bank and size from the last autosize")
        ck(L.days() == ["2026-09-16"], "one ET day")
        ck(L.contracts_for(c2) == 40.0, "contracts per ticker from orders")
        ck(len(L.losing_closes()) == 1 and L.losing_closes()[0][1] < 0, "the losses ledger holds the one losing close")
        # append the halt: only the new bytes are read
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\n" + json.dumps(rows[-1]) + "\n")
        ck(L.refresh() and len(L.halts) == 1 and len(L.settled) == 2,
           "an appended record is picked up incrementally without re-reading the rest")
        ck(not L.refresh(), "NULL: nothing new -> nothing read")

        # status derivation, planted
        base = {"pid": 1, "alive": True, "flag": None, "quiet_s": 30, "watchdog_s": 10, "open": {}, "halt": None}
        ck(status_of(dict(base))[0] == "TRADING", "alive, quiet 30 s, no flag -> TRADING")
        ck(status_of(dict(base, quiet_s=30 * 60))[0] == "STALE", "alive but silent 30 min -> STALE")
        ck(status_of(dict(base, flag="operator PAUSE", open={c3: 1}))[0] == "PAUSING", "alive + flag + open bet -> PAUSING")
        ck(status_of(dict(base, alive=False, flag="operator PAUSE at x"))[0] == "PAUSED", "dead + pause flag -> PAUSED")
        ck(status_of(dict(base, alive=False, flag="operator STOP at x"))[0] == "STOPPED", "dead + stop flag -> STOPPED")
        h = dict(base, alive=False, halt={"kind": "halt", "t": time.time() - 60, "why": rows[-1]["why"]})
        ck(status_of(h)[0] == "BRAKE" and "restarts in" in status_of(h)[2], "dead after a money brake -> BRAKE, with the countdown")
        ck(status_of(dict(base, alive=False))[0] == "DOWN" and "bringing it back" in status_of(dict(base, alive=False))[1],
           "dead, watchdog alive -> DOWN, watchdog restarting")
        ck("watchdog is not running" in status_of(dict(base, alive=False, watchdog_s=None))[1],
           "dead, no watchdog heartbeat -> says so")
    print("pindesk selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    try:
        run_gui()
    except Exception:                                    # noqa: BLE001
        with open(ERR_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s\n%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), traceback.format_exc()))
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
