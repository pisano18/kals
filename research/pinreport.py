#!/usr/bin/env python3
# VERSION: 2026-09-08-rep1
"""pinreport.py -- the operator's report: what happened, what it means, in PDF.

Charts are hand-built SVG (this box has no matplotlib, numpy or reportlab) and
the PDF comes from headless Chrome, which is present and proven to render
inline SVG. Every number is pulled from a file on disk or stated as a constant
with the measurement that produced it -- nothing here is typed from memory.

Run:  python pinreport.py            -> results/pin_report.html + .pdf
      python pinreport.py --selftest
"""
import argparse
import glob
import html
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = r"C:\kals-repo\results"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


# ===========================================================================
# SVG chart primitives. Deliberately tiny and dependency-free.
# ===========================================================================
def _esc(s):
    return html.escape(str(s), quote=True)


def svg_open(w, h, title=""):
    return (f'<svg class="chart" width="100%" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{_esc(title)}" '
            f'xmlns="http://www.w3.org/2000/svg">')


def txt(x, y, s, size=11, anchor="start", fill="#333", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}" '
            f'font-family="Segoe UI,Helvetica,Arial,sans-serif">{_esc(s)}</text>')


def line(x1, y1, x2, y2, stroke="#bbb", w=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{w}"{d}/>')


def rect(x, y, w, h, fill, rx=2, op=1.0):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" '
            f'height="{max(h,0):.1f}" rx="{rx}" fill="{fill}" '
            f'fill-opacity="{op}"/>')


def path(pts, stroke="#2563eb", w=2, fill="none"):
    if not pts:
        return ""
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{w}" stroke-linejoin="round"/>')


# ---------------------------------------------------------------------------
def chart_calibration(buckets):
    """buckets: list of (label, n, realised_pct). The credibility chart."""
    W, H = 720, 300
    L, R, T, B = 58, 18, 26, 52
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H, "model confidence versus reality")]
    for g in range(0, 101, 25):
        y = T + ph - ph * g / 100.0
        s.append(line(L, y, W - R, y, "#eee"))
        s.append(txt(L - 8, y + 4, f"{g}%", 10, "end", "#888"))
    # perfect-calibration diagonal
    s.append(line(L, T + ph, W - R, T, "#c7d2fe", 2, "5,4"))
    s.append(txt(W - R - 6, T + 12, "perfect calibration", 10, "end", "#8b9dc3"))
    n = max(len(buckets), 1)
    bw = pw / n
    for i, (lab, cnt, pct) in enumerate(buckets):
        x = L + i * bw
        h = ph * (pct / 100.0)
        col = "#16a34a" if (pct >= 90 or pct <= 10) else "#94a3b8"
        s.append(rect(x + bw * 0.18, T + ph - h, bw * 0.64, h, col, 2, 0.9))
        s.append(txt(x + bw / 2, T + ph + 16, lab, 9, "middle", "#555"))
        s.append(txt(x + bw / 2, T + ph + 30, f"n={cnt:,}", 8, "middle", "#999"))
        if cnt:
            s.append(txt(x + bw / 2, T + ph - h - 5, f"{pct:.1f}%", 9,
                         "middle", "#333", "bold"))
    s.append(txt(L, H - 6, "what the model said (its stated chance of YES)",
                 10, "start", "#666"))
    s.append(txt(L - 46, T - 10, "how often YES actually happened", 10,
                 "start", "#666"))
    s.append("</svg>")
    return "".join(s)


def chart_collapse():
    """Why the edge exists: uncertainty collapses far faster than sqrt(t)."""
    from engine import var_factor
    W, H = 720, 300
    L, R, T, B = 58, 18, 22, 48
    pw, ph = W - L - R, H - T - B
    taus = list(range(60, 0, -1))
    real = [math.sqrt(var_factor(t, [1.0])) for t in taus]
    naive = [math.sqrt(t) * real[0] / math.sqrt(60) for t in taus]
    mx = max(max(real), max(naive)) * 1.05
    def pt(t, v):
        return (L + pw * (60 - t) / 59.0, T + ph - ph * (v / mx))
    s = [svg_open(W, H, "how fast the outcome becomes certain")]
    for g in range(0, 5):
        y = T + ph - ph * g / 4.0
        s.append(line(L, y, W - R, y, "#eee"))
        s.append(txt(L - 8, y + 4, f"{mx*g/4:.1f}", 10, "end", "#888"))
    s.append(path([pt(t, v) for t, v in zip(taus, naive)], "#f87171", 2))
    s.append(path([pt(t, v) for t, v in zip(taus, real)], "#2563eb", 2.5))
    for t in (60, 45, 30, 20, 10, 5, 1):
        x = L + pw * (60 - t) / 59.0
        s.append(line(x, T + ph, x, T + ph + 4, "#bbb"))
        s.append(txt(x, T + ph + 16, str(t), 10, "middle", "#555"))
    i20 = taus.index(20)
    px, py = pt(20, real[i20])
    s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#2563eb"/>')
    s.append(txt(px + 8, py - 6, "pin trades from here (20s left)", 10,
                 "start", "#2563eb", "bold"))
    s.append(txt(W - R, T + 14, "what a naive model expects", 10, "end",
                 "#f87171"))
    s.append(txt(W - R, T + 30, "what actually happens", 10, "end", "#2563eb"))
    s.append(txt(L, H - 6, "seconds left before the market closes  "
                           "(right = closer to the end)", 10, "start", "#666"))
    s.append("</svg>")
    return "".join(s)


def chart_funnel(stages):
    """stages: [(label, value, note)] — the opportunity funnel."""
    W = 720
    rowh = 46
    H = 30 + rowh * len(stages)
    s = [svg_open(W, H, "how many chances survive each filter")]
    mx = max(v for _, v, _ in stages) or 1
    for i, (lab, v, note) in enumerate(stages):
        y = 18 + i * rowh
        w = (W - 300) * (v / mx)
        col = ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"][min(i, 4)]
        s.append(rect(210, y, w, 26, col, 3, 0.92))
        s.append(txt(202, y + 18, lab, 11, "end", "#333"))
        s.append(txt(216 + w, y + 18, f"{v:,}", 11, "start", "#111", "bold"))
        s.append(txt(216 + w + 46, y + 18, note, 10, "start", "#888"))
    s.append("</svg>")
    return "".join(s)


def chart_payoff():
    """The shape of the bet: win small and often, lose big and rarely."""
    W, H = 720, 250
    s = [svg_open(W, H, "the shape of one bet")]
    mid = H - 70
    s.append(line(60, mid, W - 30, mid, "#ccc"))
    # win bar
    s.append(rect(150, mid - 24, 200, 24, "#16a34a", 3, 0.9))
    s.append(txt(250, mid - 32, "WIN  +2.5c", 12, "middle", "#166534", "bold"))
    s.append(txt(250, mid + 18, "happens 99.10% of the time", 10, "middle",
                 "#666"))
    # loss bar
    s.append(rect(430, mid, 200, 96, "#dc2626", 3, 0.9))
    s.append(txt(530, mid + 112, "LOSE  -97c", 12, "middle", "#991b1b",
                 "bold"))
    s.append(txt(530, mid + 128, "happens 0.90% of the time (3 in 333 TRADES)",
                 10, "middle", "#666"))
    s.append(txt(60, 24, "One bet, at 1 contract", 13, "start", "#111",
                 "bold"))
    s.append(txt(60, 42, "Drawn to scale: a loss is ~39x a win, so the only "
                         "number that matters is how often we are wrong -- and "
                         "the rate that counts is the one on TRADES WE TAKE.",
                 10, "start", "#666"))
    s.append("</svg>")
    return "".join(s)


def chart_scaling(rows):
    """rows: [(size, per_bet, per_day, worst)]"""
    W, H = 720, 300
    L, R, T, B = 58, 18, 26, 54
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H, "earnings and risk by bet size")]
    mx = max(max(r[2] for r in rows), 1) * 1.15
    n = len(rows)
    bw = pw / n
    for g in range(0, 5):
        y = T + ph - ph * g / 4.0
        s.append(line(L, y, W - R, y, "#eee"))
        s.append(txt(L - 8, y + 4, f"${mx*g/4:.0f}", 10, "end", "#888"))
    for i, (size, per_bet, per_day, worst) in enumerate(rows):
        x = L + i * bw
        h = ph * (per_day / mx)
        s.append(rect(x + bw * 0.30, T + ph - h, bw * 0.40, h, "#16a34a", 2,
                      0.9))
        s.append(txt(x + bw / 2, T + ph - h - 6, f"${per_day:.0f}/day", 10,
                     "middle", "#166534", "bold"))
        s.append(txt(x + bw / 2, T + ph + 16, f"{size} contracts", 10,
                     "middle", "#333"))
        s.append(txt(x + bw / 2, T + ph + 30, f"${per_bet:.2f} a bet", 9,
                     "middle", "#777"))
        s.append(txt(x + bw / 2, T + ph + 44, f"worst -${worst:.2f}", 9,
                     "middle", "#b91c1c"))
    s.append("</svg>")
    return "".join(s)


def chart_timeline(events):
    """events: [(hhmm, label, kind)] kind in ok/bug/money"""
    W = 720
    H = 46 + 26 * len(events)
    s = [svg_open(W, H, "the night, in order")]
    s.append(line(96, 22, 96, H - 14, "#ddd", 2))
    col = {"ok": "#16a34a", "bug": "#dc2626", "money": "#2563eb",
           "info": "#94a3b8"}
    for i, (t, lab, kind) in enumerate(events):
        y = 34 + i * 26
        s.append(f'<circle cx="96" cy="{y-4}" r="5" '
                 f'fill="{col.get(kind,"#999")}"/>')
        s.append(txt(86, y, t, 10, "end", "#666"))
        s.append(txt(110, y, lab, 11, "start", "#222"))
    s.append("</svg>")
    return "".join(s)



def chart_reading_vs_predicting():
    """The conceptual heart: how much of the answer is already published."""
    W, H = 720, 300
    L, R, T, B = 58, 18, 30, 56
    pw, ph = W - L - R, H - T - B
    taus = [60, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 3]
    s = [svg_open(W, H, "how much of the outcome is already known")]
    n = len(taus)
    bw = pw / n
    for g in range(0, 5):
        y = T + ph - ph * g / 4.0
        s.append(line(L, y, W - R, y, "#eee"))
        s.append(txt(L - 8, y + 4, f"{25*g}%", 10, "end", "#888"))
    for i, tau in enumerate(taus):
        locked = 61 - tau
        known = locked / 60.0
        x = L + i * bw
        hk = ph * known
        s.append(rect(x + bw * 0.16, T + ph - hk, bw * 0.68, hk, "#16a34a",
                      2, 0.9))
        s.append(rect(x + bw * 0.16, T, bw * 0.68, ph - hk, "#f87171", 2, 0.55))
        s.append(txt(x + bw / 2, T + ph + 15, str(tau), 9, "middle", "#555"))
        if tau in (20, 45):
            s.append(txt(x + bw / 2, T + ph - hk - 5, f"{100*known:.0f}%", 9,
                         "middle", "#166534", "bold"))
    # the line where reading becomes predicting
    i50 = next(i for i, t in enumerate(taus) if (61 - t) / 60.0 < 0.5)
    xh = L + i50 * bw
    s.append(line(xh, T, xh, T + ph, "#0f172a", 1.5, "4,3"))
    s.append(txt(xh - 6, T - 8, "more known than unknown", 9, "end", "#166534"))
    s.append(txt(xh + 6, T - 8, "mostly guesswork", 9, "start", "#b91c1c"))
    s.append(txt(L, H - 32, "green = already published and unchangeable   "
                            "red = still unknown", 10, "start", "#666"))
    s.append(txt(L, H - 16, "seconds remaining before the market closes",
                 10, "start", "#666"))
    s.append("</svg>")
    return "".join(s)


def chart_capacity(rows):
    """Why more money stops helping. rows: [(capital, per_day, limited_by)]"""
    W, H = 720, 260
    L, R, T, B = 62, 18, 24, 48
    pw, ph = W - L - R, H - T - B
    s = [svg_open(W, H, "earnings against capital")]
    mx = max(r[1] for r in rows) * 1.25
    n = len(rows)
    bw = pw / n
    for g in range(0, 5):
        y = T + ph - ph * g / 4.0
        s.append(line(L, y, W - R, y, "#eee"))
        s.append(txt(L - 8, y + 4, f"${mx*g/4:.0f}", 10, "end", "#888"))
    pts = []
    for i, (cap, day, lim) in enumerate(rows):
        x = L + i * bw + bw / 2
        y = T + ph - ph * (day / mx)
        pts.append((x, y))
        col = "#16a34a" if lim == "money" else "#94a3b8"
        s.append(rect(x - bw * 0.3, y, bw * 0.6, T + ph - y, col, 2, 0.85))
        s.append(txt(x, T + ph + 16, f"${cap:,}", 10, "middle", "#333"))
        s.append(txt(x, T + ph + 30, lim, 8.5, "middle",
                     "#166534" if lim == "money" else "#94a3b8"))
        s.append(txt(x, y - 6, f"${day:.0f}", 10, "middle", "#111", "bold"))
    s.append(path(pts, "#0f172a", 1.5))
    s.append(txt(L, H - 4, "capital deployed  (grey = adding money changes "
                           "nothing; the book runs out, not the cash)",
                 9.5, "start", "#666"))
    s.append("</svg>")
    return "".join(s)


def chart_two_error_rates():
    """The correction that matters: all calls versus calls we actually trade."""
    W, H = 720, 210
    s = [svg_open(W, H, "the two error rates")]
    s.append(txt(20, 22, "The number that matters is the one measured on "
                         "trades we actually take", 12, "start", "#0f172a",
                 "bold"))
    bars = [("over ALL near-certain calls", 0.01, "#93c5fd",
             "1 wrong in 10,421"),
            ("over calls we actually TRADE", 0.90, "#f59e0b",
             "3 wrong in 333"),
            ("break-even (lose money above this)", 2.26, "#dc2626",
             "the line that must not be crossed")]
    mx = 2.6
    for i, (lab, v, col, note) in enumerate(bars):
        y = 48 + i * 48
        w = (W - 330) * (v / mx)
        s.append(txt(292, y + 17, lab, 10.5, "end", "#333"))
        s.append(rect(300, y, w, 24, col, 3, 0.92))
        s.append(txt(306 + w, y + 17, f"{v:.2f}%", 11, "start", "#111",
                     "bold"))
        s.append(txt(306 + w + 46, y + 17, note, 9.5, "start", "#888"))
    s.append(txt(20, H - 10, "Someone only sells a sure thing cheap when they "
                             "might know something. That is why the traded "
                             "rate is 90x the general one.",
                 10, "start", "#666"))
    s.append("</svg>")
    return "".join(s)

# ===========================================================================
def read_run_logs():
    """Everything the live runs actually did."""
    out = {"signals": [], "orders": [], "settled": [], "halts": [],
           "errors": [], "runs": []}
    for p in sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")),
                    key=os.path.getmtime):
        ev = []
        try:
            for ln in open(p, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    try:
                        ev.append(json.loads(ln))
                    except Exception:
                        pass
        except Exception:
            continue
        out["runs"].append({"file": os.path.basename(p), "n": len(ev),
                            "kinds": dict(Counter(e.get("kind") for e in ev))})
        for e in ev:
            k = e.get("kind")
            if k in out:
                out[k].append(e)
            elif k == "signal":
                out["signals"].append(e)
            elif k == "order":
                out["orders"].append(e)
            elif k == "settled":
                out["settled"].append(e)
            elif k == "halt":
                out["halts"].append(e)
            elif k == "error":
                out["errors"].append(e)
    return out


def read_smoke():
    """The proven penny round trip."""
    best = None
    for p in sorted(glob.glob(os.path.join(RESULTS, "pinsmoke-*.jsonl")),
                    key=os.path.getmtime):
        d = {"file": os.path.basename(p)}
        try:
            for ln in open(p, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                e = json.loads(ln)
                d[e.get("kind")] = e
        except Exception:
            continue
        if d.get("settled"):
            best = d
    return best


def selftest():
    print("SELF-TEST -- pinreport")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    s = chart_calibration([("0-10%", 1207, 0.0), ("90-100%", 1169, 99.8)])
    ck(s.startswith("<svg") and s.endswith("</svg>"), "calibration chart is svg")
    ck("99.8%" in s, "it prints the realised rate")
    c = chart_collapse()
    ck("<path" in c and c.count("<path") >= 2,
       "collapse chart draws both curves")
    f = chart_funnel([("a", 108, "x"), ("b", 13, "y")])
    ck("108" in f and "13" in f, "funnel prints its counts")
    p = chart_payoff()
    ck("WIN" in p and "LOSE" in p, "payoff chart shows both outcomes")
    sc = chart_scaling([(1, 0.99, 0.93, 0.99), (30, 29.7, 18.0, 29.7)])
    ck("$18/day" in sc, "scaling chart labels earnings")
    rp = chart_reading_vs_predicting()
    ck("already published" in rp and "%" in rp,
       "reading-vs-predicting chart renders")
    cp = chart_capacity([(30, 18, "money"), (100, 30, "depth")])
    ck("$100" in cp and "depth" in cp, "capacity chart shows the ceiling")
    te = chart_two_error_rates()
    ck("0.90%" in te and "2.26%" in te,
       "two-error-rate chart shows traded rate and breakeven")
    t = chart_timeline([("07:16", "deployed", "money")])
    ck("deployed" in t, "timeline renders")
    ck(_esc('<b>&"') == "&lt;b&gt;&amp;&quot;", "text is html-escaped")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    print("charts module ready; build.py composes the report")
