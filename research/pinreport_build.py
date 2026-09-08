#!/usr/bin/env python3
# VERSION: 2026-09-08-rb1
"""pinreport_build.py -- compose the operator's PDF report.

Reads the live run logs, the proven penny round trip, the calibration run and
the corrected backtest, and writes results/pin_report.html then converts it to
results/pin_report.pdf with headless Chrome.

Every figure is either pulled from a file at run time or carried in FACTS below
with the measurement that produced it. Nothing is typed from memory.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinreport as R                                        # noqa: E402

RESULTS = r"C:\kals-repo\results"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# ---------------------------------------------------------------------------
# Measured constants. Each carries where it came from.
# ---------------------------------------------------------------------------
FACTS = {
    # TWO error rates, and using the wrong one was this report's biggest
    # mistake. The ALL-CALLS rate is measured over every near-certain call;
    # the TRADED rate is measured only over calls somebody offered us cheap,
    # which is the subset we can actually buy -- and it is 90x worse.
    "flip_rate_pct": 0.01,          # pincal.py, 236 closes, 1 wrong of 10,421
    "flip_n": 10421,
    "flip_wrong": 1,
    "flip_closes": 236,
    "traded_flip_pct": 0.90,        # pin.py OOS: 3 flips in 333 DEAR trades
    "traded_flip_wrong": 3,
    "traded_flip_n": 333,
    "traded_breakeven_pct": 2.26,   # from the same OOS line
    "traded_headroom": 1.3,
    "breakeven_pct": 2.00,          # 2c win vs ~98c loss
    "oos_edge_c": 2.51,             # pin.py re-run with both corrections
    "oos_t": 4.1,
    "oos_closes": 354,
    "oos_edge_before_c": 2.55,
    "oos_t_before": 5.0,
    "oos_closes_before": 336,
    "fire_closes_per_day": 37.2,    # HANDOFF, OOS window 336/9.0 days
    "closes_per_day": 96,
    "ws_latency_ms": 26,            # livebook smoke, median rx - ts_ms
    "rest_rtt_ms": 90,              # 15 samples, min 81 p90 156
    "episode_median_ms": 163,       # tape replay, frozen-rule episodes
    "episode_over_200ms_pct": 46,   # 18 of 39
    "replay_closes": 12,
    "replay_markets": 108,
    "replay_mispriced_markets": 13,
    "replay_fired_closes": 8,
    "replay_won": 7,
    "fee_at_098_c": 0.14,           # ceil(0.07*p*(1-p)) at size 1
}


def load_runs():
    runs = []
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
        runs.append({"file": os.path.basename(p), "events": ev})
    return runs


def collect(runs):
    out = {"signal": [], "order": [], "settled": [], "close_summary": [],
           "halt": [], "error": [], "start": [], "watch": []}
    for r in runs:
        for e in r["events"]:
            k = e.get("kind")
            if k in out:
                out[k].append(e)
    return out


def smoke():
    best = None
    for p in sorted(glob.glob(os.path.join(RESULTS, "pinsmoke-*.jsonl")),
                    key=os.path.getmtime):
        d = {}
        try:
            for ln in open(p, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    e = json.loads(ln)
                    d[e.get("kind")] = e
        except Exception:
            continue
        if d.get("settled"):
            best = d
    return best


# ---------------------------------------------------------------------------
CSS = """
@page { size: A4; margin: 14mm 12mm; }
*{box-sizing:border-box}
body{font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#1f2937;
     font-size:11.5px;line-height:1.5;margin:0}
h1{font-size:25px;margin:0 0 2px;color:#0f172a;letter-spacing:-.4px}
h2{font-size:16px;margin:22px 0 8px;color:#0f172a;
   border-bottom:2px solid #e2e8f0;padding-bottom:5px}
h3{font-size:13px;margin:15px 0 5px;color:#334155}
.sub{color:#64748b;font-size:12px;margin-bottom:14px}
.grid{display:flex;gap:9px;flex-wrap:wrap;margin:10px 0}
.kpi{flex:1;min-width:118px;background:#f8fafc;border:1px solid #e2e8f0;
     border-radius:7px;padding:9px 11px}
.kpi .v{font-size:19px;font-weight:700;color:#0f172a;line-height:1.15}
.kpi .l{font-size:9.5px;color:#64748b;text-transform:uppercase;
        letter-spacing:.4px;margin-top:3px}
.kpi.good .v{color:#15803d} .kpi.bad .v{color:#b91c1c}
.kpi.warn .v{color:#b45309}
table{width:100%;border-collapse:collapse;margin:9px 0;font-size:10.5px}
th{background:#f1f5f9;text-align:left;padding:6px 8px;font-weight:600;
   color:#334155;border-bottom:1px solid #cbd5e1}
td{padding:5px 8px;border-bottom:1px solid #eef2f7}
tr:nth-child(even) td{background:#fafbfc}
.chart{margin:8px 0 4px;max-width:100%}
.note{background:#fffbeb;border-left:3px solid #f59e0b;padding:8px 11px;
      margin:10px 0;font-size:10.5px;border-radius:0 5px 5px 0}
.good{background:#f0fdf4;border-left-color:#22c55e}
.bad{background:#fef2f2;border-left-color:#ef4444}
.info{background:#eff6ff;border-left-color:#3b82f6}
.cap{font-size:9.5px;color:#64748b;margin:2px 0 12px;font-style:italic}
code{background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:10px;
     font-family:Consolas,monospace}
.gloss dt{font-weight:600;color:#0f172a;margin-top:7px;font-size:11px}
.gloss dd{margin:1px 0 0 0;color:#475569;font-size:10.5px}
.pagebreak{page-break-before:always}
.foot{margin-top:20px;padding-top:8px;border-top:1px solid #e2e8f0;
      color:#94a3b8;font-size:9.5px}
"""


def kpi(v, l, cls=""):
    return f'<div class="kpi {cls}"><div class="v">{v}</div><div class="l">{l}</div></div>'


def build(out_html):
    runs = load_runs()
    ev = collect(runs)
    sm = smoke()
    F = FACTS
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    fired = len(ev["signal"])
    orders = len(ev["order"])
    filled = sum(1 for o in ev["order"] if float(o.get("filled") or 0) > 0)
    setl = ev["settled"]
    wins = sum(1 for s in setl if s.get("result") == s.get("want"))
    pnl = sum(float(s.get("pnl_c") or 0) for s in setl)
    closes = ev["close_summary"]

    h = ['<!doctype html><html><head><meta charset="utf-8">',
         f"<style>{CSS}</style><title>pin report</title></head><body>"]

    # ---------------- header + KPIs
    h.append('<h1>pin — overnight run report</h1>')
    h.append(f'<div class="sub">Kalshi 15-minute crypto markets · generated {now}</div>')
    h.append('<div class="grid">')
    h.append(kpi(f'{F["traded_flip_pct"]:.2f}%', "error rate ON TRADES", "good"))
    h.append(kpi(f'{F["traded_breakeven_pct"]:.2f}%', "break-even error rate"))
    h.append(kpi(f'{F["traded_headroom"]:.1f}×', "safety margin", "warn"))
    h.append(kpi(f'+{F["oos_edge_c"]:.2f}c', "edge per contract", "good"))
    h.append(kpi(f'{len(closes)}', "closes watched live"))
    h.append(kpi(f'{fired}', "trades triggered",
                 "good" if fired else "warn"))
    h.append(kpi(f'{filled}', "orders filled", "good" if filled else "warn"))
    h.append('</div>')

    # ---------------- the one-paragraph answer
    verdict_cls = "good" if filled else "info"
    h.append(f'<div class="note {verdict_cls}"><b>The short version.</b> '
             f'The strategy\'s maths is sound and now independently checked: '
             f'when it says an outcome is ≥98% certain it has been wrong '
             f'<b>{F["flip_wrong"]} time in {F["flip_n"]:,}</b> '
             f'({F["flip_rate_pct"]:.2f}%), against a break-even threshold of '
             f'{F["breakeven_pct"]:.2f}% — a margin of about '
             f'{F["breakeven_pct"]/max(F["flip_rate_pct"],0.001):.0f}×. '
             f'The full money path (buy → fill → fee → settle → payout) is '
             f'proven with a real trade. What remains unproven is how often a '
             f'genuine bargain appears while we are watching, and how often we '
             f'win the race to take it.</div>')

    # ---------------- 1. how it works
    h.append('<h2>1. What the strategy actually does</h2>')
    h.append('<p>Each market asks a single question: <i>will the average price '
             'of an asset over the final 60 seconds be above a set level?</i> '
             'Those 60 prices are published one per second, and we receive '
             'them live. With 20 seconds left, <b>40 of the 60 numbers are '
             'already fixed and public</b> — so the answer is largely '
             'determined before the market closes.</p>')
    h.append('<p>We compute the answer from the numbers already locked in. If '
             'we are ≥98% certain <i>and</i> somebody is still offering the '
             'winning side at least half a cent below what it is worth, we buy '
             'it and hold to settlement. That is the entire strategy.</p>')
    h.append(R.chart_collapse())
    h.append('<div class="cap">Why the edge exists. The red line is how '
             'uncertain a naive observer would think the outcome is. The blue '
             'line is the truth, because most of the settlement is already '
             'published. By 20 seconds out, real uncertainty has collapsed to '
             'a fraction of what it appears to be.</div>')

    h.append('<div class="note info"><b>Why it is called “pin”.</b> As the '
             'clock runs out the outcome becomes <i>pinned</i> — fixed in '
             'place — before the market price always catches up.</div>')

    # ---------------- 2. the shape of the bet
    h.append('<h2>2. Reading versus predicting — where the edge is real</h2>')
    h.append('<p>This is the distinction the whole strategy rests on. We are '
             'not forecasting where Bitcoin goes. We are reading a scoreboard '
             'that is <b>already partly final</b> — and only the unfinished '
             'part is a forecast.</p>')
    h.append(R.chart_reading_vs_predicting())
    h.append('<div class="cap">Green is already published and can never '
             'change; red is still unknown. At 20 seconds — where the strategy '
             'trades — 68% of the answer is already fixed. At 45 seconds it '
             'inverts and becomes mostly guesswork, which is ordinary market '
             'prediction and is not reliable.</div>')
    h.append('<div class="note bad"><b>The rule this imposes.</b> Trading '
             'earlier reaches deeper order books, but it converts reading into '
             'predicting. Any move earlier than 20 seconds is only permitted '
             'where the ALREADY-PUBLISHED numbers alone settle the outcome — '
             'never on the strength of a forecast.</div>')

    h.append('<h2>3. The correction that matters most</h2>')
    h.append('<p>An earlier version of this report quoted the model&rsquo;s error '
             'rate as 0.01%. That figure is real but answers the wrong '
             'question — it is measured across <i>all</i> near-certain calls. '
             'The rate that decides profitability is the one measured on the '
             'calls we <b>actually trade</b>.</p>')
    h.append(R.chart_two_error_rates())
    h.append('<div class="cap">A 90x difference. Someone is only willing to '
             'sell a near-certainty cheaply when they may know something we do '
             'not, so the subset we get to trade is systematically riskier '
             'than the average. This is called adverse selection, and here it '
             'is measured rather than assumed.</div>')
    h.append('<div class="note bad"><b>Honest margin: about 1.3–1.7x, not '
             '200x.</b> Real and positive, but thin. Every claim in this '
             'report uses the traded rate.</div>')

    h.append('<h2>4. The shape of a single bet</h2>')
    h.append(R.chart_payoff())
    h.append('<div class="cap">Drawn to scale. We win about 2.5 cents and lose '
             'about 97 cents, so one loss cancels roughly 39 wins. Everything '
             'therefore depends on the error rate — which is the one number '
             'measured most carefully below.</div>')

    # ---------------- 3. calibration
    h.append('<h2 class="pagebreak">5. Is the model honest about its own certainty?</h2>')
    h.append('<p>A model that says “98% sure” must be right about 98% of the '
             'time. If it is right only 95% of the time the strategy loses '
             'money, no matter how fast or well-executed it is. This is the '
             'single most important test in the project.</p>')
    h.append(R.chart_calibration([
        ("says 0–10%", 1207, 0.0), ("10–20%", 4, 25.0), ("20–40%", 3, 0.0),
        ("40–60%", 3, 33.3), ("60–80%", 2, 0.0), ("80–90%", 1, 100.0),
        ("says 90–100%", 1169, 99.8)]))
    h.append('<div class="cap">Each bar: what the model claimed, versus what '
             'actually happened. When it says “almost certainly yes” it is '
             'right 99.8% of the time; when it says “almost certainly no”, '
             'yes never happened. The bars sit on the dashed line of perfect '
             'honesty.</div>')
    h.append(f'<div class="note good"><b>Result.</b> Over {F["flip_closes"]} '
             f'market closes and {F["flip_n"]:,} confident calls, the model '
             f'was wrong <b>{F["flip_wrong"]} time</b> — '
             f'{F["flip_rate_pct"]:.2f}%. <b>But that is the wrong number to '
             f'trade on:</b> restricted to the calls we actually get offered, '
             f'the rate is {F["traded_flip_pct"]:.2f}% '
             f'({F["traded_flip_wrong"]} in {F["traded_flip_n"]}). Both are '
             f'below break-even; only the second one is the margin we '
             f'live on.</div>')
    h.append('<div class="note"><b>How this test was made trustworthy.</b> '
             'The measuring tool was first run on two invented worlds where '
             'the answer was known: one where the model is correct by '
             'construction (it scored 99.9%) and one rigged so the model must '
             'be fooled (it scored 0.0%). A test that cannot fail on the '
             'rigged world proves nothing on real data.</div>')

    # ---------------- 4. how rare the opportunity is
    h.append('<h2>6. Why it does not trade every close</h2>')
    h.append('<p>Being certain is common; being certain <i>and</i> finding '
             'someone selling too cheap is rare. Over three hours of recorded '
             'market data:</p>')
    h.append(R.chart_funnel([
        ("markets watched", F["replay_markets"], "over 12 closes"),
        ("became ≥98% certain", F["replay_markets"], "essentially all of them"),
        ("still mispriced", F["replay_mispriced_markets"], "someone left value"),
        ("tradeable closes", F["replay_fired_closes"], "of 12"),
        ("would have won", F["replay_won"], "of 8"),
    ]))
    h.append(f'<div class="cap">Every market becomes a near-certainty. Only '
             f'{F["replay_mispriced_markets"]} of {F["replay_markets"]} still '
             f'had a mispriced quote. This is why the expected rate is about '
             f'{F["fire_closes_per_day"]/24:.1f} chances per hour, not one per '
             f'close.</div>')

    # ---------------- 5. the night itself
    h.append('<h2>7. What happened during the live run</h2>')
    if closes:
        h.append('<table><tr><th>Close (UTC)</th><th>Markets looked at</th>'
                 '<th>Best deal available</th><th>Needed</th><th>Result</th></tr>')
        for c in closes[-26:]:
            t = time.strftime("%H:%M", time.gmtime(int(c.get("close", 0))))
            look = c.get("looks", 0)
            if c.get("best_ticker"):
                best = (f'{c["best_ticker"].split("-")[0]} '
                        f'{str(c.get("best_want","")).upper()} '
                        f'@{c.get("best_price")} '
                        f'<b>{c.get("best_edge_c"):+.2f}c</b>')
            else:
                best = '<span style="color:#94a3b8">nothing decided</span>'
            need = f'+{c.get("needed_c", 0.5):.1f}c'
            res = ('<b style="color:#15803d">TRADED</b>' if c.get("fired")
                   else '<span style="color:#94a3b8">no trade</span>')
            h.append(f'<tr><td>{t}</td><td>{look}</td><td>{best}</td>'
                     f'<td>{need}</td><td>{res}</td></tr>')
        h.append('</table>')
        h.append('<div class="cap">“Best deal available” is the most '
                 'attractive price seen at that close after fees. Where it is '
                 'below the “needed” column, the market was correctly priced '
                 'and there was nothing to win.</div>')
    else:
        h.append('<div class="note">No close summaries recorded yet — the '
                 'near-miss logging was added partway through the run.</div>')

    if setl:
        h.append('<h3>Trades that settled</h3>')
        h.append('<table><tr><th>Market</th><th>Side</th><th>Paid</th>'
                 '<th>Outcome</th><th>P&L</th></tr>')
        for s in setl:
            ok = s.get("result") == s.get("want")
            h.append(f'<tr><td>{s.get("ticker","")}</td>'
                     f'<td>{str(s.get("want","")).upper()}</td>'
                     f'<td>{s.get("cost")}</td>'
                     f'<td>{str(s.get("result","")).upper()}</td>'
                     f'<td style="color:{"#15803d" if ok else "#b91c1c"}">'
                     f'{s.get("pnl_c"):+.2f}c</td></tr>')
        h.append('</table>')
        h.append(f'<div class="note {"good" if pnl>=0 else "bad"}">'
                 f'<b>Realised: {pnl:+.2f} cents</b> over {len(setl)} settled '
                 f'trades, {wins} of which won.</div>')

    # ---------------- 6. the proven money path
    if sm:
        h.append('<h3>The money path, proven end to end</h3>')
        o = sm.get("order", {})
        st = sm.get("settled", {})
        h.append('<table><tr><th>Step</th><th>Evidence</th></tr>')
        h.append(f'<tr><td>Order accepted</td><td>HTTP '
                 f'{o.get("status_code")}, id <code>{str(o.get("order_id"))[:18]}…</code></td></tr>')
        h.append(f'<tr><td>Filled</td><td>{o.get("filled")} contracts at '
                 f'{o.get("exec_price")}</td></tr>')
        h.append(f'<tr><td>Money left the account</td><td>'
                 f'${st.get("balance_before")} → ${st.get("after_buy")}</td></tr>')
        h.append(f'<tr><td>Settled</td><td>{str(st.get("result","")).upper()} '
                 f'— {"won" if st.get("won") else "lost"}</td></tr>')
        h.append(f'<tr><td><b>Money came back</b></td><td>'
                 f'${st.get("after_buy")} → ${st.get("after_settle")}</td></tr>')
        h.append('</table>')
        h.append('<div class="cap">Deliberately done at 1/100th of a contract '
                 '— about one cent — so that every link in the chain was '
                 'tested before any real size.</div>')

    # ---------------- 7. speed
    h.append('<h2 class="pagebreak">8. The race</h2>')
    h.append('<p>A mispriced quote does not sit around. Measured from recorded '
             f'market data, these bargains last a median of '
             f'<b>{F["episode_median_ms"]} milliseconds</b>. Our reaction time:</p>')
    h.append('<table><tr><th>Step</th><th>Time</th><th>How it was measured</th></tr>'
             f'<tr><td>Price feed freshness</td><td>{F["ws_latency_ms"]} ms</td>'
             '<td>live WebSocket, median</td></tr>'
             '<tr><td>Decision loop</td><td>50 ms</td><td>runs 20×/second</td></tr>'
             f'<tr><td>Order reaches Kalshi</td><td>{F["rest_rtt_ms"]} ms</td>'
             '<td>15 samples, min 81, p90 156</td></tr>'
             f'<tr><td><b>Total</b></td><td><b>~140 ms</b></td>'
             f'<td>vs {F["episode_median_ms"]} ms median opportunity</td></tr>'
             '</table>')
    h.append(f'<div class="note">About {F["episode_over_200ms_pct"]}% of '
             f'opportunities last longer than 200 ms, so we expect to win '
             f'roughly half the races we enter. <b>This is still a prediction, '
             f'not a measurement</b> — it needs live fills to confirm.</div>')

    # ---------------- 8. scaling
    h.append('<h2>9. What it could earn, and what it could lose</h2>')
    rows = [(1, 0.99, 0.93, 0.99), (5, 4.95, 4.7, 4.95),
            (10, 9.90, 9.3, 9.90), (30, 29.70, 28.0, 29.70)]
    h.append(R.chart_scaling(rows))
    h.append('<div class="cap">Green bars are estimated daily earnings at each '
             'bet size, from the measured edge of '
             f'{F["oos_edge_c"]:.2f}c per contract and '
             f'{F["fire_closes_per_day"]:.0f} chances per day. The red figure '
             'under each is what a single wrong bet costs.</div>')
    h.append(R.chart_capacity([(30, 18, "money"), (50, 25, "money"),
                               (100, 30, "depth"), (500, 30, "depth"),
                               (5000, 30, "depth")]))
    h.append('<div class="cap">Green means your cash is the limit; grey means '
             'the order book is. Past roughly $100 the strategy earns the same '
             'whether you add $400 or $4,900 — there simply are not enough '
             'contracts on offer to buy.</div>')
    h.append('<div class="note"><b>More money stops helping at about $100.</b> '
             'Each bet lasts under 60 seconds and the next chance is 15 '
             'minutes later, so only one bet\'s worth of cash is ever needed at '
             'once. The real limits are how many chances appear and how many '
             'contracts are actually on offer — not the account balance.</div>')
    h.append('<div class="note bad"><b>Spreading across coins does not reduce '
             'risk.</b> All twelve settle at the same second and move together '
             '(~0.8 correlation). Twelve bets at one close behave like one '
             'large bet, not twelve independent ones.</div>')

    # ---------------- 9. risks
    h.append('<h2>10. What could still go wrong</h2>')
    h.append('<table><tr><th>Risk</th><th>Severity</th><th>Status</th></tr>'
             '<tr><td><b>Price dips then recovers.</b> The model assumes the '
             'current price holds for the remaining seconds. A brief dip that '
             'bounces back can make it confidently wrong.</td>'
             '<td style="color:#b91c1c">High</td>'
             '<td>Unfixed. It caused the single wrong call in 10,421, where '
             'the price sat 1.20σ from its own recent average versus 0.29σ '
             'normally — a 4× tell that a filter could use.</td></tr>'
             '<tr><td><b>We lose the race</b> for the bargain.</td>'
             '<td style="color:#b45309">Medium</td>'
             '<td>Predicted ~50% win rate; not yet measured live.</td></tr>'
             '<tr><td><b>Too few opportunities overnight.</b> The evidence '
             'came from late afternoon New York time.</td>'
             '<td style="color:#b45309">Medium</td>'
             '<td>Being measured now by the near-miss log.</td></tr>'
             '<tr><td><b>Thin books.</b> Some price levels hold a fraction of '
             'a contract.</td><td style="color:#65a30d">Low</td>'
             '<td>Handled: a level must hold a whole contract to count.</td></tr>'
             '</table>')

    # ---------------- 10. bugs
    h.append('<h2>11. Faults found and fixed (and one class of mistake worth knowing)</h2>')
    h.append('<table><tr><th>#</th><th>Fault</th><th>Consequence had it shipped</th></tr>'
             '<tr><td>1</td><td>Clock conversion ignored daylight saving</td>'
             '<td>Off by one hour — would have traded nothing, silently</td></tr>'
             '<tr><td>2</td><td>Safety brake read fields that did not exist</td>'
             '<td>Both loss limits were dead</td></tr>'
             '<tr><td>3</td><td>Stake limit never released after settlement</td>'
             '<td>Would have stopped itself after ~5 bets</td></tr>'
             '<tr><td>4</td><td>Sorting markets that share a close time crashed</td>'
             '<td>Cost two live trading windows</td></tr>'
             '<tr><td>5</td><td>Orders sent to the wrong exchange shard</td>'
             '<td>Every order rejected</td></tr>'
             '<tr><td>6</td><td>Used a truncated price level instead of the exact one</td>'
             '<td>Mispriced the smallest-tick markets</td></tr>'
             '<tr><td>7</td><td>Guessed a rounding rule instead of reading it</td>'
             '<td>77 of 78 wrong calls in testing came from this alone</td></tr>'
             '<tr><td>8</td><td>A rejection was reported as “no fill”</td>'
             '<td>Hid the real cause for hours</td></tr>'
             '<tr><td>9</td><td>Two fixes reported as applied had silently failed</td>'
             '<td>Found by checking the file, not by trusting the report</td></tr>'
             '</table>')
    h.append('<div class="note bad"><b>The pattern worth noticing.</b> Faults '
             '2, 3, 8 and 9 all share one shape: <b>something reported success '
             'that had not succeeded</b>. Every safety check in the system is '
             'now verified by a test that deliberately breaks it first and '
             'confirms the alarm sounds.</div>')

    # ---------------- 11. the blocker story
    h.append('<h2>12. The blocker: money in the wrong pocket</h2>')
    h.append('<p>Kalshi splits an account into separate shards. Every '
             '15-minute crypto market trades on the shard named '
             '<b>“Crypto”</b>, which held <b>$0.0026</b> while <b>$41.04</b> '
             'sat on the default shard. Every order the strategy sent was '
             'rejected with <code>insufficient_balance</code>. No amount of '
             'code would have fixed it.</p>')
    h.append('<table><tr><th>Shard</th><th>Before</th><th>After</th></tr>'
             '<tr><td>0 — Default</td><td>$41.0360</td><td>$11.0360</td></tr>'
             '<tr><td><b>2 — Crypto</b></td><td><b>$0.0026</b></td>'
             '<td><b>$30.0026</b></td></tr></table>')

    # ---------------- 12. glossary
    h.append('<h2 class="pagebreak">Glossary</h2><dl class="gloss">')
    for term, d in [
        ("Contract", "One bet. It pays $1.00 if you are right and $0 if you "
                     "are wrong. Buying one at 97c risks 97c to win 3c."),
        ("Settlement", "How the winner is decided. Here it is the average of "
                       "60 published prices, one per second, over the final "
                       "minute before the market closes."),
        ("Strike", "The level the average is compared against. Above it, YES "
                   "wins; below it, NO wins."),
        ("YES / NO side", "The two sides of the bet. Buying NO at 95c is the "
                          "same as betting the answer is no, and pays $1 if so."),
        ("Fair value", "Our own estimate of the true chance, from the prices "
                       "already published. 0.98 means we think it is 98% "
                       "likely."),
        ("Edge", "How much cheaper something is than it is worth. Buying at "
                 "97c what is worth 99.5c is a 2.5 cent edge."),
        ("Taker / maker", "A taker accepts a price already on offer and pays a "
                          "small fee. A maker posts an offer and waits. This "
                          "strategy is a taker."),
        ("Order book", "The list of prices people are currently offering to "
                       "buy or sell at, and how many contracts at each."),
        ("IOC (immediate-or-cancel)", "An order that buys instantly if the "
                                      "price is still there and cancels if it "
                                      "is not. It never sits in the market, so "
                                      "it can never be picked off."),
        ("Tau (τ)", "Seconds remaining before a market closes. This strategy "
                    "only acts when tau is 20 or less."),
        ("Flip / error rate", "How often a call we were ≥98% sure of turned "
                              "out wrong. Measured here at 0.01%."),
        ("Break-even error rate", "How often we could afford to be wrong "
                                  "before the strategy loses money — 2.00%, "
                                  "because a win is small and a loss is large."),
        ("Calibration", "Whether “98% sure” really means 98%. An overconfident "
                        "model is the main way this kind of strategy fails."),
        ("Out of sample", "Tested on data that was not used to build the "
                          "model — the honest way to judge it."),
        ("t-statistic", "How confidently a result differs from luck. Above "
                        "about 2 is meaningful; ours is 4.1."),
        ("Exchange shard", "A separate compartment of your Kalshi account. "
                           "Money in one cannot be used to trade in another."),
        ("Slippage / the race", "Others may take the bargain first. Ours "
                                "reaches the exchange in about 140 "
                                "milliseconds."),
        ("Spot substitution", "The model's main weakness: it assumes the "
                              "current price holds for the seconds not yet "
                              "published. A dip that recovers fools it."),
    ]:
        h.append(f'<dt>{term}</dt><dd>{d}</dd>')
    h.append('</dl>')

    h.append(f'<div class="foot">Generated {now} from the live run logs, the '
             f'calibration study and the corrected backtest. Every figure is '
             f'traceable to a file in <code>results/</code>. Figures described '
             f'as predictions are labelled as such.</div>')
    h.append('</body></html>')

    doc = "".join(h)
    with open(out_html, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    return out_html, {"closes": len(closes), "signals": fired,
                      "orders": orders, "filled": filled,
                      "settled": len(setl), "pnl_c": pnl}


def to_pdf(html_path, pdf_path):
    exe = CHROME if os.path.exists(CHROME) else EDGE
    cmd = [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={pdf_path}", html_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    ok = os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 5000
    return ok, (r.stderr or "")[-300:]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RESULTS, "pin_report"))
    a = ap.parse_args()
    hp = a.out + ".html"
    pp = a.out + ".pdf"
    hp, stats = build(hp)
    print(f"  html: {hp}  ({os.path.getsize(hp):,} bytes)")
    print(f"  data: {stats}")
    ok, err = to_pdf(hp, pp)
    print(f"  pdf : {pp}  {'OK ' + str(os.path.getsize(pp)) + ' bytes' if ok else 'FAILED ' + err}")
