#!/usr/bin/env python3
# VERSION: 2026-09-11-tool1
"""pintool.py -- the local server behind the tool (Live / Builder / Profiles / Learn).

Design of record: TOOL_PLAN.md. Two nouns -- a PROFILE is the strategy, a
DECISION RECORD is what happened at one second -- and every endpoint here
returns a view of one of them or of the settlements they resolved against.

RULES THAT DO NOT BEND (TOOL_PLAN.md):
  * this process NEVER imports pintake -- the self-test asserts it
  * the sandbox never writes CONTROL.json; /api/control is the only writer
  * every rate carries n as markets AND closes and its exact interval
  * every replay result is labelled an upper bound and shows the 70%-fill pair
  * nothing deploys without the trader's own self-test (AMENDMENT 11, later)

Run:   python research/pintool.py            -> http://127.0.0.1:8765
       python research/pintool.py --lan      -> reachable from the phone
"""
import argparse
import glob
import json
import math
import os
import subprocess
import sys
import threading
import time
import calendar
import uuid
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrules                                              # noqa: E402
from pincross import cp_interval                              # noqa: E402
# NOT pinsim, and NOT pinrun: pinrun imports pintake (the order module), so
# importing the replay here would hand this process a path to the order API.
# The self-test caught exactly that on the first run. Sandbox jobs run
# pinsim.py as a SEPARATE process and read its JSON.

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
TOOL = os.path.join(REPO, "tool")
SANDBOX = os.path.join(RESULTS, "sandbox")
CONTROL = os.path.join(RESULTS, "CONTROL.json")
RUNS = os.path.join(SANDBOX, "runs.jsonl")
KAUTH = r"C:\Users\Joe\AppData\Local\Temp\kals-work"
BARS = {"fills_to_scale": 180, "dump_review": 40}     # pre-registered, SKIM.md
PYTHON = sys.executable
PINSIM = os.path.join(HERE, "pinsim.py")
DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
OBJECTIVES = {
    "pnl": "total P&L at the upper bound",
    "pnl_70": "total P&L at the 70% live fill rate",
    "ev_per_fill": "P&L per fill",
    "loss_rate": "losses / fills (lower is better)",
    "fills": "number of fills (more opportunities)",
    "mean_price": "average price paid (lower is better)",
}


def ts(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def fee(p, n=1.0):
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


# ------------------------------------------------------------------- live
_proc_cache = {"t": 0, "v": None}


def trader_process():
    """pid of the running trader, or None, or "unknown" when the CHECK failed.

    The first version cached a failed PowerShell call (cold start > 15 s) as
    None for 30 s, and the page said NOT RUNNING while the bot was fine. A
    failed check must never look like a dead bot: it is reported as unknown,
    not cached, and the page falls back to log freshness."""
    if time.time() - _proc_cache["t"] < 30:
        return _proc_cache["v"]
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object {$_.CommandLine -like '*research*pinrun*'} | "
             "Select-Object -First 1 -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=45).stdout.strip()
        v = int(out) if out else None
    except Exception:
        return "unknown"                                     # do not cache
    _proc_cache.update(t=time.time(), v=v)
    return v


_bank_cache = {"t": 0, "v": None}


def bank():
    if time.time() - _bank_cache["t"] < 60:
        return _bank_cache["v"]
    v = None
    try:
        if KAUTH not in sys.path:
            sys.path.insert(0, KAUTH)
        from kauth import get                                # read-only GET
        st, b = get("/portfolio/balance")
        if st == 200:
            v = float(b["balance_dollars"])
    except Exception:
        v = None
    _bank_cache.update(t=time.time(), v=v)
    return v


def newest_live_log():
    fs = sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")),
                key=os.path.getmtime)
    return fs[-1] if fs else None


def live_state():
    """Everything the Live tab shows, from the newest live log."""
    path = newest_live_log()
    out = {"log": os.path.basename(path) if path else None,
           "pid": trader_process(), "bank": bank(), "bars": BARS}
    if not path:
        out["error"] = "no live log found"
        return out
    recs = []
    for line in open(path, encoding="utf-8"):
        try:
            recs.append(json.loads(line))
        except Exception:
            continue
    start = next((r for r in recs if r.get("kind") == "start"), None)
    settled = [r for r in recs if r.get("kind") == "settled"]
    dumped = [r for r in recs if r.get("kind") == "dumped"]
    halts = [r for r in recs if r.get("kind") == "halt"]
    errors = [r for r in recs if r.get("kind") == "error"]
    closes = [r for r in recs if r.get("kind") == "close_summary"]
    out["start"] = start
    out["log_age_s"] = round(time.time() - os.path.getmtime(path), 1)
    # the trader writes a close summary every 15 minutes; a log younger than
    # ~20 minutes is alive whatever the process check said
    fresh = out["log_age_s"] < 1200
    if out["pid"] == "unknown":
        out["alive"] = fresh
        out["alive_basis"] = "log freshness (process check failed)"
    else:
        out["alive"] = out["pid"] is not None or fresh
        out["alive_basis"] = "process" if out["pid"] else "log freshness"
    # equity: cumulative realised, one point per settlement
    eq, cum = [], 0.0
    for r in settled:
        cum += r["pnl_c"] / 100.0
        eq.append({"t": r["t"], "ticker": r["ticker"], "want": r["want"],
                   "price": r["cost"], "pnl": round(r["pnl_c"] / 100, 4),
                   "cum": round(cum, 4)})
    out["equity"] = eq
    wins = [r for r in settled if r["pnl_c"] > 0]
    losses = [r for r in settled if r["pnl_c"] <= 0]
    n = len(settled)
    first = ts(start["t"]) if start else (ts(recs[0]["t"]) if recs else None)
    hours = (time.time() - first) / 3600 if first else 0
    m = {"fills": n, "wins": len(wins), "losses": len(losses),
         "realised": round(cum, 2), "hours": round(hours, 2)}
    if n:
        lo, hi = cp_interval(len(losses), n)
        m["loss_rate_fill"] = {"rate": round(100 * len(losses) / n, 2),
                               "ci": [round(100 * lo, 2), round(100 * hi, 2)],
                               "n": n}
        lc = len({r["ticker"] for r in losses})
        fc = len({r["ticker"] for r in settled})
        lo2, hi2 = cp_interval(lc, fc)
        m["loss_rate_close"] = {"rate": round(100 * lc / fc, 2),
                                "ci": [round(100 * lo2, 2), round(100 * hi2, 2)],
                                "n": fc}
        mp = sum(r["cost"] for r in settled) / n
        m["mean_price_c"] = round(100 * mp, 2)
        m["ev_per_fill"] = round(cum / n, 4)
        m["fills_per_day"] = round(24 * n / hours, 1) if hours > 0 else None
        m["break_even_loss_rate"] = round(100 * (1 - mp - fee(mp)), 2)
        size = float(start["size"]) if start else 20.0
        mean_loss = (sum(-r["pnl_c"] for r in losses) / len(losses) / 100
                     if losses else size * mp)
        m["mean_loss_size"] = round(mean_loss, 2)
        # THE NUMBER NEEDED TO SWAY THE AVERAGE: how many more losses of the
        # run's own mean loss size the realised P&L absorbs before it is
        # negative
        m["losses_absorbable"] = int(cum // mean_loss) if mean_loss > 0 else None
        m["wins_to_recover_one_loss"] = round(
            (mp + fee(mp)) / max(1e-9, (1 - mp) - fee(mp)), 1)
    out["metrics"] = m
    out["brakes"] = {"losing_closes": len({r["ticker"] for r in losses}),
                     "max_losses": 3,
                     "realised": round(cum, 2),
                     "loss_abort": float(start["loss_abort"]) if start else -60.0,
                     "halts": len(halts), "errors": len(errors)}
    out["progress"] = {"fills_to_scale": [n, BARS["fills_to_scale"]],
                       "dump_review": [len(dumped), BARS["dump_review"]]}
    out["recent"] = (settled[-30:])[::-1]
    out["dumped"] = dumped[-30:][::-1]
    out["closes_evaluated"] = len(closes)
    return out


# ---------------------------------------------------------------- sandbox
JOBS = {}


def _append_run(entry):
    os.makedirs(SANDBOX, exist_ok=True)
    with open(RUNS, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_history():
    n = 0
    rows = []
    if os.path.exists(RUNS):
        for line in open(RUNS, encoding="utf-8"):
            try:
                rows.append(json.loads(line))
                n += 1
            except Exception:
                pass
    return {"runs": n, "multiple_looks_threshold": round(0.05 / max(1, n), 5),
            "recent": rows[-20:][::-1]}


def _objective(summary, key):
    t = summary["traded"]["all"]
    if key == "pnl":
        return t["pnl"]
    if key == "pnl_70":
        return round(t["pnl"] * summary["live_fill_rate"], 2)
    if key == "ev_per_fill":
        return round(t["pnl"] / t["fills"], 4) if t["fills"] else None
    if key == "loss_rate":
        return t["loss_rate"]
    if key == "fills":
        return t["fills"]
    if key == "mean_price":
        return t["mean_price"]
    return None


def newest_settlement_iso():
    """Newest close with a settlement result, read straight from fulltape --
    no replay code imported."""
    ns = 0
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r.get("result") is not None:
                ns = max(ns, float(r["close"]))
    return ns


def sandbox_job(job):
    """Runs pinsim.py as a SEPARATE PROCESS (see the import note at the top)
    and reads its JSON. A sweep runs inside that one process so its tape
    cache serves every value."""
    try:
        prof = job["profile"]
        bad = pinrules.validate(prof)
        if bad:
            job.update(status="error", error="profile refused:\n" + "\n".join(bad))
            return
        os.makedirs(SANDBOX, exist_ok=True)
        pth = os.path.join(SANDBOX, f"{job['id']}.profile.json")
        with open(pth, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in prof.items() if not k.startswith("_")}, f)
        out = os.path.join(SANDBOX, f"{job['id']}.json")
        hours = int(min(48, max(1, job["hours"])))
        cmd = [PYTHON, PINSIM, "--profile", pth, "--hours", str(hours),
               "--json", out]
        if job.get("end"):
            cmd += ["--end", str(job["end"])]
        sweep = job.get("sweep")
        if sweep:
            cmd += ["--sweep", f"{sweep['param']}=" +
                    ",".join(str(v) for v in sweep["values"])]
        env = dict(os.environ, KALS_SELFTESTED="1")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env,
                                cwd=REPO)
        lines, done = [], 0
        for line in proc.stdout:
            lines.append(line.rstrip())
            if "bought" in line and line.strip()[:4] == "2026":
                done += 1
                job["progress"] = [done, hours * max(1, len(sweep["values"]) if sweep else 1)]
        proc.wait()
        job["log"] = lines[-40:]
        if proc.returncode != 0 or not os.path.exists(out):
            job.update(status="error",
                       error=f"pinsim exit {proc.returncode}; see log")
            return
        with open(out, encoding="utf-8") as f:
            res = json.load(f)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if sweep:
            job.update(status="done", results=res)
            for r in res:
                _append_run({"t": stamp, "profile": prof["name"],
                             "sweep": sweep["param"], "value": r.get("value"),
                             "hours": hours, "end": job.get("end")})
        else:
            job.update(status="done", summary=res)
            _append_run({"t": stamp, "profile": prof["name"],
                         "sha": pinrules.fingerprint(prof),
                         "hours": hours, "end": job.get("end")})
    except Exception as e:                                   # noqa: BLE001
        job.update(status="error", error=repr(e))


# ------------------------------------------------------------------ learn
CONCEPTS = {
    "the-settlement-window": (
        "Why the last 60 seconds decide everything",
        "Each market settles on the AVERAGE of 60 one-second prices, taken in "
        "the last minute before the close. With 20 seconds left, 40 of those 60 "
        "prices are already known. So the answer is mostly arithmetic, not "
        "prediction -- and that is the whole reason this works only in the "
        "final ~30 seconds and does not generalise to longer horizons."),
    "sigma-and-margin": (
        "Sigma and margin",
        "Sigma is how much the price wobbles per second, measured over the last "
        "5 minutes. Margin is how far the expected settlement sits from the "
        "strike, measured in sigmas. 2 sd is 'pretty sure', 4 sd is 'certain by "
        "the model'. The model is calibrated near 2-4 sd and worthless beyond it: "
        "live, 2 of 14 'certain' fills lost."),
    "price-beats-confidence": (
        "Why price matters more than confidence",
        "Break-even loss rate is roughly 1 minus the price. At 98c you may be "
        "wrong 2% of the time; at 60c, 40%. A cheap contract can afford to be "
        "wrong; a dear one cannot. One cent of average price is worth about 40% "
        "of income at the cap."),
    "wins-to-recover": (
        "Wins to recover, and break-even loss rate",
        "Wins to recover = (price + fee) / (profit - fee). At 98c, one loss "
        "needs ~49 wins to repay; at 95c, ~19. Break-even loss rate is the rate "
        "at which the strategy makes nothing: at 96c about 3.7%."),
    "fit-vs-holdout": (
        "Fit vs holdout, and curve fitting",
        "If you tune a setting by looking at all the data, it will look good on "
        "that data no matter what. So the tool splits history: the first 70% of "
        "closes (FIT) is where you tune, the last 30% (HOLDOUT) is the exam. A "
        "setting that wins on FIT and loses on HOLDOUT is a fit, not a finding. "
        "Every conditions gate tried this week did exactly that: +18.5% fit, "
        "-18.0% holdout. The more settings you try, the stricter the bar: the "
        "multiple-looks threshold is 0.05 divided by the number of runs."),
    "replay-is-an-upper-bound": (
        "Why a replay is an upper bound",
        "In a replay every resting offer is yours. Live, you win about 70% of "
        "the races for them, and you lose them most on the best prices. Every "
        "sandbox number is shown twice: as-if-every-offer-were-ours, and at "
        "the 70% live fill rate. Neither is a promise."),
    "the-brakes": (
        "What each brake does",
        "Loss abort: halt when the run's realised P&L falls below -$60. Loss "
        "count: halt after 3 losing closes (closes, because fills on one close "
        "are one event). Stake cap: never more than a fixed dollar amount at "
        "risk. Attempt cap: at most 8 orders per close. A halt means a human "
        "looks before more money moves."),
    "decision-record": (
        "What a decision record is",
        "Everything the bot knows at the second it decides: the model's fair "
        "value, the offer, the discount, tau, depth, the conditions on other "
        "coins. It is identical live and in replay. Rules and trackers can only "
        "see these fields, so nothing can peek at the future."),
    "schedules-and-trackers": (
        "Schedules and trackers",
        "A schedule makes a value depend on a field: 40 contracts under 90c, 20 "
        "above. A tracker is a rule whose action is 'log': it fires, records the "
        "moment, and lets the trade through -- so you can measure a hunch "
        "before acting on it. The crazy-deal guard is the same rule with action "
        "'refuse'."),
}


def learn():
    glossary = {k: {"meaning": v[4], "why": v[5], "type": v[0],
                    "range": [v[1], v[2]], "default": v[3]}
                for k, v in pinrules.PARAMS.items()}
    fields = dict(pinrules.FIELDS)
    return {"glossary": glossary, "fields": fields,
            "concepts": [{"id": k, "title": v[0], "text": v[1]}
                         for k, v in CONCEPTS.items()]}


def schema():
    return {"params": {k: {"type": v[0], "min": v[1], "max": v[2],
                           "default": v[3], "meaning": v[4], "why": v[5]}
                       for k, v in pinrules.PARAMS.items()},
            "fields": pinrules.FIELDS, "ops": list(pinrules.OPS),
            "actions": list(pinrules.ACTIONS), "objectives": OBJECTIVES,
            "bars": BARS}


# ---------------------------------------------------------------- control
def write_control(body):
    """The ONLY writer of CONTROL.json. Refuses anything unconfirmed."""
    allowed = {"run", "pause", "stop"}
    if "state" in body:
        if body["state"] not in allowed:
            return 400, {"error": f"state must be one of {sorted(allowed)}"}
        if body.get("confirm") != body["state"]:
            return 400, {"error": f"type the word '{body['state']}' to confirm"}
        payload = {"state": body["state"]}
    elif "profile" in body:
        try:
            p = pinrules.load(body["profile"])
        except Exception as e:                               # noqa: BLE001
            return 400, {"error": f"profile refused: {e}"}
        if body.get("confirm") != p["name"]:
            return 400, {"error": f"type the profile name '{p['name']}' to "
                                  f"confirm; worst case "
                                  f"{pinrules.worst_case(p['params'])}"}
        payload = {"profile": p["name"], "sha": p["_sha"],
                   "worst_case": pinrules.worst_case(p["params"])}
    else:
        return 400, {"error": "send {state, confirm} or {profile, confirm}"}
    payload["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["note"] = ("the trader honours this only once AMENDMENT 11 (the "
                       "control reader) is live; until then this file is a "
                       "request on record")
    with open(CONTROL, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return 200, payload


# ----------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                                # quiet
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                page = os.path.join(TOOL, "index.html")
                if os.path.exists(page):
                    body = open(page, "rb").read()
                else:
                    body = (b"<h1>pintool</h1><p>tool/index.html is not built "
                            b"yet. The API is up: /api/schema /api/live "
                            b"/api/profiles /api/learn</p>")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if u.path == "/api/schema":
                return self._json(200, schema())
            if u.path == "/api/live":
                return self._json(200, live_state())
            if u.path == "/api/learn":
                return self._json(200, learn())
            if u.path == "/api/profiles":
                names = sorted(os.path.basename(f)[:-5] for f in
                               glob.glob(os.path.join(pinrules.PROFILES, "*.json")))
                out = []
                for nm in names:
                    try:
                        p = pinrules.load(nm)
                        out.append({"name": nm, "sha": p["_sha"],
                                    "note": p.get("note", ""),
                                    "rules": len(p["rules"]),
                                    "worst_case": pinrules.worst_case(p["params"])})
                    except Exception as e:                   # noqa: BLE001
                        out.append({"name": nm, "error": str(e)})
                return self._json(200, {"profiles": out})
            if u.path.startswith("/api/profiles/"):
                nm = u.path.split("/", 3)[3]
                p = pinrules.load(nm)
                return self._json(200, p)
            if u.path.startswith("/api/sandbox/jobs/"):
                jid = u.path.rsplit("/", 1)[1]
                j = JOBS.get(jid)
                if not j:
                    return self._json(404, {"error": "no such job"})
                return self._json(200, {k: v for k, v in j.items()
                                        if k != "thread"})
            if u.path == "/api/sandbox/history":
                return self._json(200, run_history())
            if u.path == "/api/sandbox/newest":
                ns = newest_settlement_iso()
                nb = len(glob.glob(os.path.join(DATA, "orderbook_delta",
                                                "2026*.jsonl.gz")))
                return self._json(200, {
                    "newest_settlement": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(ns)),
                    "newest_hour": time.strftime("%Y%m%dT%H",
                                                 time.gmtime(ns - 3600)),
                    "book_hours": nb})
            return self._json(404, {"error": "unknown endpoint"})
        except Exception as e:                               # noqa: BLE001
            return self._json(500, {"error": repr(e)})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/profiles":
                bad = pinrules.validate(body)
                if bad:
                    return self._json(400, {"error": "profile refused",
                                            "problems": bad})
                path = pinrules.save(body)
                return self._json(200, {"saved": path,
                                        "sha": pinrules.fingerprint(body)})
            if u.path == "/api/sandbox/run":
                prof = body.get("profile")
                if isinstance(prof, str):
                    prof = {k: v for k, v in pinrules.load(prof).items()
                            if not k.startswith("_")}
                if not isinstance(prof, dict):
                    return self._json(400, {"error": "profile: a name or a "
                                                     "profile object"})
                jid = uuid.uuid4().hex[:10]
                job = {"id": jid, "status": "running", "progress": [0, 0],
                       "profile": prof, "hours": int(body.get("hours", 6)),
                       "end": body.get("end"), "sweep": body.get("sweep"),
                       "objective": body.get("objective", "pnl"),
                       "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                JOBS[jid] = job
                th = threading.Thread(target=sandbox_job, args=(job,),
                                      daemon=True)
                job["thread"] = th
                th.start()
                return self._json(200, {"job": jid})
            if u.path == "/api/control":
                code, out = write_control(body)
                return self._json(code, out)
            return self._json(404, {"error": "unknown endpoint"})
        except Exception as e:                               # noqa: BLE001
            return self._json(500, {"error": repr(e)})


def serve(host, port):
    srv = ThreadingHTTPServer((host, port), Handler)
    return srv


# --------------------------------------------------------------- self-test
def selftest():
    print("SELF-TEST -- pintool")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck("pintake" not in sys.modules,
       "pintake is NOT imported -- this process has no path to the order API")
    import urllib.request
    srv = serve("127.0.0.1", 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()

    def get(path):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=60) as r:
            return r.status, json.loads(r.read())

    def post(path, obj):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=json.dumps(obj).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    st, s = get("/api/schema")
    ck(st == 200 and set(s["params"]) == set(pinrules.PARAMS)
       and all(s["params"][k]["meaning"] for k in s["params"]),
       f"/api/schema serves every param with its meaning ({len(s['params'])})")
    st, l = get("/api/learn")
    ck(st == 200 and set(l["glossary"]) == set(pinrules.PARAMS) and l["concepts"],
       "/api/learn: a glossary entry for every param, plus concept pages")
    st, p = get("/api/profiles")
    ck(st == 200 and any(x["name"] == "default" for x in p["profiles"]),
       "/api/profiles lists default")
    st, d = get("/api/profiles/default")
    ck(st == 200 and d["params"]["PIN"] == 0.995, "/api/profiles/default loads")
    st, lv = get("/api/live")
    ck(st == 200 and "metrics" in lv and "bars" in lv,
       f"/api/live answers (fills {lv.get('metrics', {}).get('fills')}, "
       f"pid {lv.get('pid')})")
    st, c = post("/api/control", {"state": "pause", "confirm": "nope"})
    ck(st == 400, "/api/control refuses an unconfirmed request")
    st, c = post("/api/control", {"state": "bogus", "confirm": "bogus"})
    ck(st == 400, "and an unknown state")
    st, c = post("/api/profiles", {"name": "x", "params": {}, "rules": []})
    ck(st == 400 and c.get("problems"),
       "saving an invalid profile is refused with the problems listed")
    st, h = get("/api/sandbox/history")
    ck(st == 200 and "multiple_looks_threshold" in h,
       "/api/sandbox/history carries the multiple-looks threshold")
    srv.shutdown()
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--lan", action="store_true",
                    help="bind 0.0.0.0 so the phone can reach it")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = serve(host, a.port)
    print(f"\n  pintool on http://{host}:{a.port}   (page: tool/index.html)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
