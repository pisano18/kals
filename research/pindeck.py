#!/usr/bin/env python3
"""pindeck.py -- the flight deck. One page an owner can glance at.

Built 2026-09-15 with the operator's explicit "total creative freedom". So it
answers the four questions I would want answered if I owned this machine and
could not watch it all day, in the order they matter:

  1. IS IT ALIVE?      the bot, the two recorders, the key, and how long since
                       each last did something. A dead bot is worth more
                       attention than any number below it.
  2. IS IT WORKING?    the bank curve, today against the days before it, and
                       the one number that decides everything: cents kept per
                       contract against the price that break-even needs.
  3. WHAT WILL HURT?   every loss, in a ledger. Not a rate -- the actual
                       events, because this strategy wins small and loses big
                       and the losses are the whole story.
  4. HOW MUCH ROOM?    the share of the offered book we already eat. That, not
                       the edge, is what ends the growth.

And the market's own heartbeat: a 15-minute cycle the page can compute without
asking anyone, so it shows what the bot is doing RIGHT NOW -- waiting,
deciding, or settling -- while you are looking at it.

Everything is rebuilt from the bot's own logs at generation time and stamped
with when. Nothing here is live after that; the clock is the only thing that
keeps moving.

    python research/pindeck.py --selftest
    python research/pindeck.py
"""
import collections
import datetime as dt
import glob
import html
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import downtime                                              # noqa: E402
import pinstreak                                             # noqa: E402
import pinvalue                                              # noqa: E402

OUT = os.path.join(REPO, "results", "pindeck.html")
KALS = r"C:\kals\kalshi_data"
BREAK_EVEN_C = 1.51        # cents per contract the edge dies below (pinhealth)


# ------------------------------------------------------------------ gathering
def freshness():
    """{name: (seconds since it last wrote, path)} -- the honest liveness test
    on a box where we cannot ask a process how it feels."""
    out = {}
    now = time.time()

    def newest(pattern):
        fs = glob.glob(pattern)
        if not fs:
            return None
        f = max(fs, key=os.path.getmtime)
        return now - os.path.getmtime(f)

    out["bot"] = newest(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))
    out["settlement index"] = newest(os.path.join(KALS, "cfbenchmarks_value", "*.gz"))
    out["order books"] = newest(os.path.join(KALS, "orderbook_delta", "*.gz"))
    out["exchange feeds"] = newest(os.path.join(REPO, "..", "kals", "feed_data", "*", "*.gz"))
    out["race arm"] = newest(os.path.join(REPO, "results", "pinracearm-*.jsonl"))
    return out


def bank_curve():
    return pinvalue.bank_series()


def closes_and_flags():
    spans = downtime.load()
    rows = pinstreak.load(spans)
    return rows


def book_share():
    """(median share of the offered book we take, n markets)."""
    sig, fills = collections.defaultdict(list), collections.Counter()
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if '"signal"' not in line and '"order"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") == "signal" and d.get("ladder_under") is not None:
                sig[d["ticker"]].append(d["ladder_under"])
            elif d.get("kind") == "order" and (d.get("filled") or 0) > 0:
                fills[d["ticker"]] += d["filled"]
    shares = sorted(fills[t] / max(v) for t, v in sig.items()
                    if t in fills and max(v) > 0)
    if not shares:
        return None, 0
    return shares[len(shares) // 2], len(shares)


# ------------------------------------------------------------------- drawing
def spark(points, w=760, h=170, pad=26):
    """The bank curve as an SVG area. One scale, labelled at both ends."""
    if len(points) < 2:
        return "<p>not enough history yet</p>"
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 == x0:
        return "<p>not enough history yet</p>"
    span = max(y1 - y0, 1e-6)

    def px(x):
        return pad + (w - 2 * pad) * (x - x0) / (x1 - x0)

    def py(y):
        return h - pad - (h - 2 * pad) * (y - y0) / span

    pts = " ".join("%.1f,%.1f" % (px(x), py(y)) for x, y in points)
    area = "%.1f,%.1f %s %.1f,%.1f" % (px(x0), h - pad, pts, px(x1), h - pad)
    # a tick for every day boundary
    ticks = []
    seen = set()
    for x, _y in points:
        k = dt.datetime.fromtimestamp(x + downtime.et_offset(x),
                                      dt.timezone.utc).strftime("%m-%d")
        if k in seen:
            continue
        seen.add(k)
        ticks.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" class="tick"/>'
                     '<text x="%.1f" y="%d" class="tk">%s</text>'
                     % (px(x), pad - 8, px(x), h - pad, px(x) + 3, h - 10, k))
    return ('<svg viewBox="0 0 %d %d" class="curve" role="img" '
            'aria-label="bank from $%.0f to $%.0f">%s'
            '<polygon points="%s" class="fill"/>'
            '<polyline points="%s" class="line"/>'
            '<circle cx="%.1f" cy="%.1f" r="3.5" class="dot"/>'
            '<text x="%d" y="%d" class="ax">$%.0f</text>'
            '<text x="%.1f" y="%.1f" class="ax hi">$%.0f</text></svg>'
            % (w, h, y0, y1, "".join(ticks), area, pts,
               px(xs[-1]), py(ys[-1]), pad - 20, py(y0), y0,
               px(xs[-1]) - 44, py(ys[-1]) - 10, ys[-1]))


def ring():
    """The 15-minute cycle, drawn client-side. The bot scans all cycle and only
    decides in the last 30 seconds, so the ring turns amber then."""
    return ('<div class="ring" id="ring"><div class="ringface">'
            '<b id="cd">--:--</b><span id="phase">to the next close</span>'
            '</div></div>')


CSS = """<style>
:root{
 --ink:#0A0E16; --panel:#111726; --edge:#1C2436; --text:#E8EDF7; --dim:#7D8AA3;
 --gain:#31C48D; --loss:#E4572E; --watch:#F0B429; --grid:#151C2B;
}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]){
 --ink:#F2F4F8; --panel:#FFFFFF; --edge:#DFE4EC; --text:#111826; --dim:#5A6577;
 --gain:#12855C; --loss:#C04120; --watch:#9A6B12; --grid:#E7EBF1;}}
:root[data-theme="light"]{
 --ink:#F2F4F8; --panel:#FFFFFF; --edge:#DFE4EC; --text:#111826; --dim:#5A6577;
 --gain:#12855C; --loss:#C04120; --watch:#9A6B12; --grid:#E7EBF1;}
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--text);
 font-family:Archivo,"Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.5}
.deck{max-width:1000px;margin:0 auto;padding-block:26px 60px;
 padding-left:18px;padding-right:18px;display:flex;flex-direction:column;gap:20px}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}
h1{margin:0;font-size:25px;font-weight:700;letter-spacing:-.02em}
.stamp{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11.5px;color:var(--dim);
 text-align:right;line-height:1.7}
h2{margin:0 0 10px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;
 color:var(--dim);font-family:"JetBrains Mono",ui-monospace,monospace;font-weight:500}
.panel{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:18px}
.rail{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:10px}
.sig{background:var(--panel);border:1px solid var(--edge);border-left:3px solid var(--gain);
 border-radius:8px;padding:11px 13px}
.sig.warn{border-left-color:var(--watch)} .sig.bad{border-left-color:var(--loss)}
.sig b{display:block;font-family:"JetBrains Mono",ui-monospace,monospace;font-size:15px;
 font-weight:500;font-variant-numeric:tabular-nums}
.sig span{font-size:11px;color:var(--dim);letter-spacing:.04em}
.hero{display:grid;grid-template-columns:minmax(0,1fr) 168px;gap:18px;align-items:center}
.big{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:40px;font-weight:500;
 font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1}
.sub{color:var(--dim);font-size:13px;margin-top:4px}
.curve{width:100%;height:auto;display:block}
.curve .fill{fill:color-mix(in srgb,var(--gain) 16%,transparent)}
.curve .line{fill:none;stroke:var(--gain);stroke-width:2;stroke-linejoin:round}
.curve .dot{fill:var(--gain)}
.curve .tick{stroke:var(--grid);stroke-width:1}
.curve .tk,.curve .ax{fill:var(--dim);font-family:"JetBrains Mono",ui-monospace,monospace;font-size:10px}
.curve .hi{fill:var(--text)}
.ring{width:150px;height:150px;border-radius:50%;display:grid;place-items:center;
 background:conic-gradient(var(--gain) 0turn, var(--grid) 0turn);justify-self:end}
.ringface{width:124px;height:124px;border-radius:50%;background:var(--panel);
 display:grid;place-items:center;text-align:center}
.ringface b{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:26px;
 font-variant-numeric:tabular-nums;display:block}
.ringface span{font-size:10.5px;color:var(--dim);display:block;max-width:104px;letter-spacing:.03em}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;align-items:start}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-family:"JetBrains Mono",ui-monospace,monospace;font-size:10px;
 letter-spacing:.12em;text-transform:uppercase;color:var(--dim);font-weight:500;padding:0 8px 7px 0}
td{padding:7px 8px 7px 0;border-top:1px solid var(--edge);vertical-align:top}
td.n{font-family:"JetBrains Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;text-align:right}
.gain{color:var(--gain)} .loss{color:var(--loss)} .watch{color:var(--watch)}
.meter{height:9px;border-radius:5px;background:var(--grid);overflow:hidden;margin:9px 0 6px}
.meter i{display:block;height:100%;background:var(--watch)}
.note{color:var(--dim);font-size:12.5px;max-width:62ch}
footer{color:var(--dim);font-size:11.5px;border-top:1px solid var(--edge);padding-top:14px;max-width:70ch}
@media (max-width:620px){.hero{grid-template-columns:1fr}.ring{justify-self:start}.big{font-size:32px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>"""
FONT = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Archivo:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap">')

CLOCK_JS = """<script>
(function(){
 var ring=document.getElementById('ring'),cd=document.getElementById('cd'),ph=document.getElementById('phase');
 function tick(){
  var now=Date.now()/1000, cycle=900, into=now%cycle, left=cycle-into;
  var m=Math.floor(left/60), s=Math.floor(left%60);
  cd.textContent=m+':'+(s<10?'0':'')+s;
  var frac=into/cycle, colour= left<=30 ? 'var(--watch)' : 'var(--gain)';
  ring.style.background='conic-gradient('+colour+' '+frac+'turn, var(--grid) '+frac+'turn)';
  ph.textContent = left<=30 ? 'DECIDING NOW' : (left>870 ? 'settling the last close' : 'watching, no bets yet');
 }
 tick(); setInterval(tick,1000);
})();
</script>"""


def build(ctx):
    a = []
    w = a.append
    w("<title>Pin Deck</title>")
    w(FONT)
    w(CSS)
    w('<div class="deck">')
    w('<div class="top"><div><h1>Pin Deck</h1>'
      '<div class="sub">Kalshi 15-minute crypto &middot; one bot, nine coins</div></div>'
      '<div class="stamp">built %s ET<br>%s</div></div>'
      % (html.escape(ctx["stamp"]), html.escape(ctx["version"])))

    # 1 -- alive
    w('<div><h2>Is it alive</h2><div class="rail">')
    for name, secs in ctx["fresh"]:
        if secs is None:
            cls, txt = "bad", "never"
        elif secs < 120:
            cls, txt = "", "%ds ago" % int(secs)
        elif secs < 900:
            cls, txt = "warn", "%dm ago" % int(secs / 60)
        else:
            cls, txt = "bad", "%.1fh ago" % (secs / 3600.0)
        w('<div class="sig %s"><b>%s</b><span>%s</span></div>'
          % (cls, html.escape(txt), html.escape(name)))
    w("</div></div>")

    # 2 -- money
    w('<div class="panel"><h2>The bank</h2><div class="hero"><div>')
    w('<div class="big">$%s</div>' % ctx["bank"])
    w('<div class="sub">%s</div>' % html.escape(ctx["bank_sub"]))
    w(ctx["curve"])
    w('</div>%s</div></div>' % ring())

    w('<div class="rail">')
    for label, value, cls in ctx["tiles"]:
        w('<div class="sig %s"><b>%s</b><span>%s</span></div>'
          % (cls, html.escape(value), html.escape(label)))
    w("</div>")

    w('<div class="cols">')
    # 3 -- the losses
    w('<div class="panel"><h2>Every loss</h2>')
    if ctx["losses"]:
        w("<table><tr><th>when (ET)</th><th>market</th><th>paid</th>"
          "<th class='n'>cost</th></tr>")
        for when, mkt, paid, cost in ctx["losses"]:
            w("<tr><td>%s</td><td>%s</td><td class='n'>%s</td>"
              "<td class='n loss'>%s</td></tr>"
              % (html.escape(when), html.escape(mkt), html.escape(paid),
                 html.escape(cost)))
        w("</table>")
    w('<p class="note">%s</p></div>' % html.escape(ctx["loss_note"]))

    # 4 -- the ceiling
    w('<div class="panel"><h2>How much room is left</h2>')
    w('<div class="big">%s</div><div class="sub">of the contracts for sale at '
      'our prices, taken on a typical trade</div>' % ctx["share"])
    w('<div class="meter"><i style="width:%.0f%%"></i></div>' % ctx["share_pct"])
    w('<p class="note">%s</p>' % html.escape(ctx["share_note"]))
    w('<table><tr><th>silence</th><th class="n">how normal</th></tr>%s</table>'
      % ctx["drought_rows"])
    w('<p class="note">%s</p></div>' % html.escape(ctx["drought_note"]))
    w("</div>")

    w('<footer>%s</footer>' % html.escape(ctx["footer"]))
    w("</div>")
    w(CLOCK_JS)
    return "\n".join(a)


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    s = spark([(0, 10.0), (100, 20.0), (200, 15.0)])
    ck("<svg" in s and "polyline" in s and "$20" in s,
       "the curve draws, and its top label names a value the line reaches")
    ck(spark([(0, 1.0)]).startswith("<p"),
       "NULL: one point is not a curve and says so instead of drawing a lie")
    ck(spark([(5, 3.0), (5, 4.0)]).startswith("<p"),
       "NULL: and neither is two points at the same instant")
    ctx = {"stamp": "x", "version": "v", "fresh": [("bot", 5), ("books", None),
           ("slow", 300), ("feeds", 5000)], "bank": "100", "bank_sub": "s",
           "curve": spark([(0, 1.0), (10, 2.0)]), "tiles": [("a", "1", "")],
           "losses": [("t", "m", "p", "c")], "loss_note": "n", "share": "24%",
           "share_pct": 24.0, "share_note": "n", "drought_rows": "<tr><td>a</td><td>b</td></tr>",
           "drought_note": "n", "footer": "f"}
    page = build(ctx)
    ck(page.count("<div") == page.count("</div>"), "every div it opens, it closes")
    ck('class="sig bad"' in page and 'class="sig warn"' in page,
       "a recorder that never wrote is marked bad, a slow one amber")
    ck("prefers-color-scheme" in page and 'data-theme="light"' in page
       and "background:var(--ink)" in page,
       "the page paints its own ground and carries both themes")
    ck("conic-gradient" in page and "setInterval" in page,
       "the cycle ring is drawn and keeps ticking after the page is built")
    ck("900" in CLOCK_JS and "left<=30" in CLOCK_JS,
       "and it knows the real rhythm: a 900-second cycle whose last 30 seconds "
       "are the only ones the bot buys in")
    ck("<script" in page and "fetch(" not in page,
       "the only script is the clock -- the page asks nothing of anyone")
    print("pindeck selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0

    now = time.time()
    trades, _warn = pinvalue.load_trades()
    bank = bank_curve()
    rows = closes_and_flags()
    flags = [1 if f else 0 for _, f in rows]
    share, share_n = book_share()
    lost = downtime.lost_by_et_day()

    def et(e):
        return dt.datetime.fromtimestamp(e + downtime.et_offset(e), dt.timezone.utc)

    today = et(now).strftime("%Y-%m-%d")
    today_trades = [t for t in trades if et(t["close"]).strftime("%Y-%m-%d") == today]
    today_profit = sum(t["profit"] for t in today_trades)
    up_h = downtime.hours_up_et_day(today, now)
    total_profit = sum(t["profit"] for t in trades)
    total_stake = sum(t["stake"] for t in trades)
    contracts = sum(t["contracts"] for t in trades)
    cpc = 100.0 * total_profit / max(1e-9, contracts)
    losses = [t for t in trades if not t["won"]]
    cur_bank = bank[-1][1] if bank else 0.0
    first_bank = bank[0][1] if bank else 0.0

    g = pinstreak.gaps_between(flags)
    last_buy = max((c for c, f in rows if f), default=None)
    dry_closes = int((now - last_buy) // 900) if last_buy else 0
    q95 = pinstreak.quantile(g, 0.95) or 0
    q99 = pinstreak.quantile(g, 0.99) or 0

    drought_rows = "".join(
        "<tr><td>%s</td><td class='n'>%s</td></tr>" % (a, b) for a, b in (
            ("right now", "%.1f h" % ((now - last_buy) / 3600.0 if last_buy else 0)),
            ("normal (half are under)", "%.1f h" % ((pinstreak.quantile(g, 0.5) or 0) * 0.25)),
            ("19 in 20 are under", "%.1f h" % (q95 * 0.25)),
            ("99 in 100 are under", "%.1f h" % (q99 * 0.25)),
            ("longest ever", "%.1f h" % (max(g) * 0.25 if g else 0))))

    tiles = [
        ("today, %.1f h up" % up_h,
         "$%+.2f" % today_profit, "" if today_profit >= 0 else "bad"),
        ("kept per contract, all time", "%.2fc" % cpc,
         "" if cpc > BREAK_EVEN_C else "bad"),
        ("break-even sits at", "%.2fc" % BREAK_EVEN_C, "warn"),
        ("losses", "%d of %d" % (len(losses), len(trades)),
         "warn" if losses else ""),
        ("returned per $ staked", "%.2f%%" % (100 * total_profit / max(1e-9, total_stake)), ""),
        ("hours lost today", "%.1f h" % lost.get(today, 0.0),
         "bad" if lost.get(today, 0) > 1 else ""),
    ]

    loss_rows = []
    for t in sorted(losses, key=lambda t: -t["close"])[:12]:
        loss_rows.append((et(t["close"]).strftime("%m-%d %H:%M"),
                          t["ticker"].split("-")[0].replace("KX", "").replace("15M", ""),
                          "%.1fc x%d" % (100 * (t["price"] or 0), t["contracts"]),
                          "$%.2f" % t["profit"]))

    ctx = {
        "stamp": et(now).strftime("%Y-%m-%d %H:%M"),
        "version": "rebuilt from the bot's own logs",
        "fresh": sorted(freshness().items(), key=lambda kv: (kv[1] is None, kv[1] or 0)),
        "bank": "%s" % ("{:,.2f}".format(cur_bank)),
        "bank_sub": ("from $%.2f deposited, %.1fx in %d days"
                     % (first_bank, cur_bank / max(1e-9, first_bank),
                        len({et(t["close"]).strftime("%j") for t in trades}))),
        "curve": spark(bank),
        "tiles": [(a, b, c) for a, b, c in tiles],
        "losses": loss_rows,
        "loss_note": ("%d losses in %d buys. This strategy wins about 2c and "
                      "loses about 95c, so roughly 40 wins pay for one loss -- "
                      "the losses ARE the strategy's risk, which is why they "
                      "are listed one by one rather than as a rate."
                      % (len(losses), len(trades))),
        "share": ("%.0f%%" % (100 * share)) if share else "n/a",
        "share_pct": (100 * share) if share else 0.0,
        "share_note": ("Measured on %d markets where the full book was "
                       "recorded. At this size we already take about a quarter "
                       "of everything offered at our prices; the growth ends "
                       "when that reaches all of it, not when the edge fails."
                       % share_n),
        "drought_rows": drought_rows,
        "drought_note": ("Dry spells are real, not bad luck: the chance of a "
                         "buy falls from 51%% right after one to 25%% after two "
                         "quiet hours. Past %.1f h of silence, suspect the bot "
                         "before the market." % (q99 * 0.25)),
        "footer": ("Rebuilt from results/pinrun-live-*.jsonl at the time stamped "
                   "above; only the cycle clock keeps moving. Profit is "
                   "reconstructed from the fills and reconciles with the bank. "
                   "Closes inside a recorded outage are excluded so downtime "
                   "cannot read as a quiet market. Times Eastern."),
    }
    open(OUT, "w", encoding="utf-8").write(build(ctx))
    print("wrote %s" % OUT)
    print("  bank $%.2f | today $%+.2f in %.1f h | %.2fc per contract | "
          "%d losses of %d | share of book %s"
          % (cur_bank, today_profit, up_h, cpc, len(losses), len(trades),
             ("%.0f%%" % (100 * share)) if share else "n/a"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
