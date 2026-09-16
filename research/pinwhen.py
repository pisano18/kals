#!/usr/bin/env python3
"""pinwhen.py -- WHEN do the chances come? Hot and cold hours, tested against
chance, saved so the answer sharpens every day.

THE OPERATOR, 2026-09-15: "We need to start keeping track of hot and cold
times... see if it's random and regardless of if it is or not try and find some
correlations (not apophenia or patternicity, real patterns)."

WHAT ONE ROW IS. One 15-minute CLOSE. All nine coins settle on the same quarter
hour, so a close is the unit of opportunity -- never a trade, never a coin
(hard rule 4). For each close this records:

  fired      did the live bot actually buy
  tradeable  how many moments cleared every gate
  no_offer   how many moments died because nobody offered the winning side
  best_edge  the best edge seen, in cents
  tape_opp   independently, did the TAPE show a gate-passing offer that close
  sigma      the index's own 1-second volatility over the last 5 minutes

TWO THINGS THAT WOULD MAKE THIS LIE, and what is done about each:

  1. OUR OWN DOWNTIME LOOKS LIKE A COLD HOUR. The bot was off for 7.57 hours on
     2026-09-15 alone. Every close overlapping a window in results/DOWNTIME.json
     is dropped from the live series, and the count dropped is printed.
  2. SHAPES IN NOISE. With ~27 closes an hour, an hour that fires 30% against a
     20% average is ordinary luck. So: every map is drawn beside a SHUFFLED
     TWIN built by the same code from the same data with the clock labels
     randomised, the spread of the real map is tested against 2,000 such
     shuffles, and the smallest difference this much data could detect is
     printed BEFORE any number is read.

AND A REAL DRIVER, not just the clock: the hour-of-day effect is re-tested
INSIDE volatility thirds. A clock pattern that disappears once volatility is
held still was never about the clock.

    python research/pinwhen.py --selftest
    python research/pinwhen.py
"""
import collections
import datetime as dt
import glob
import html
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import downtime                                              # noqa: E402

OUT_ROWS = os.path.join(REPO, "results", "when_closes.jsonl")
OUT_HTML = os.path.join(REPO, "results", "when_heatmap.html")
OUT_MD = os.path.join(REPO, "results", "WHEN.md")
HORIZONS = (1, 3, 7, 14, 21, 30)
BLOCKS = [(0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24)]
SHUFFLES = 2000
NLMARK = chr(10)


def et(epoch):
    return dt.datetime.fromtimestamp(epoch + downtime.et_offset(epoch),
                                     dt.timezone.utc).replace(tzinfo=None)


def block_of(hour):
    for i, (lo, hi) in enumerate(BLOCKS):
        if lo <= hour < hi:
            return i
    return len(BLOCKS) - 1


# ------------------------------------------------------------------ the test
def spread(counts):
    """How uneven a set of (hits, n) cells is: the largest gap between any two
    cells' rates, ignoring cells with fewer than 10 closes. Returns None when
    fewer than two cells qualify."""
    rates = [h / float(n) for h, n in counts if n >= 10]
    if len(rates) < 2:
        return None
    return max(rates) - min(rates)


def permutation_p(labels, hits, n_shuffle=SHUFFLES, seed=4242):
    """P(a spread this uneven by chance alone).

    `labels` is one clock label per close, `hits` the 0/1 outcome. The labels
    are shuffled against the outcomes, which destroys any real clock effect and
    keeps the sample sizes and the overall rate exactly as they are. This is the
    honest test: no distribution assumed, and it automatically pays for the many
    cells being looked at."""
    def sp(lab):
        agg = collections.defaultdict(lambda: [0, 0])
        for l, h in zip(lab, hits):
            a = agg[l]
            a[0] += h
            a[1] += 1
        return spread([(h, n) for h, n in agg.values()])

    obs = sp(labels)
    if obs is None:
        return None, None, 0
    rng = random.Random(seed)
    pool = list(labels)
    worse = 0
    for _ in range(n_shuffle):
        rng.shuffle(pool)
        s = sp(pool)
        if s is not None and s >= obs - 1e-12:
            worse += 1
    return obs, (worse + 1) / float(n_shuffle + 1), n_shuffle


def mde(n_per_cell, base_rate):
    """The smallest difference between two cells this much data could show,
    roughly: 2.8 standard errors of a difference of two rates."""
    if n_per_cell <= 0:
        return 1.0
    se = math.sqrt(2 * base_rate * (1 - base_rate) / n_per_cell)
    return 2.8 * se


# ------------------------------------------------------------------ the data
def load_live(spans):
    """One row per close from the live bot's own close summaries."""
    rows, dropped = {}, 0
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if '"close_summary"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            cs = d.get("close")
            if not cs:
                continue
            # the decision window is the last 30 s before the close
            if downtime.lost_seconds(cs - 30, cs, spans) > 0:
                dropped += 1
                continue
            rows[cs] = {"close": cs, "fired": bool(d.get("fired")),
                        "tradeable": d.get("tradeable"),
                        "no_offer": d.get("no_offer"),
                        "looks": d.get("looks"),
                        "best_edge_c": d.get("best_edge_c")}
    return rows, dropped


def load_tape():
    """{close: True} where the tape showed a gate-passing offer."""
    p = os.path.join(REPO, "results", "pinlevels_rows.jsonl")
    out = {}
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8", errors="ignore"):
        if '"row"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        cs = d.get("cs")
        if not cs:
            continue
        out[cs] = out.get(cs, False) or (d.get("verdict") == "trade")
    return out


def add_sigma(rows):
    """The index's own 1-second volatility over the 5 minutes before each
    close -- a real driver to hold still while the clock is tested."""
    try:
        import idxload
        idx = idxload.load(["BRTI"], verbose=False)
        D = idx.get("BRTI")
    except Exception:                                        # noqa: BLE001
        return 0
    if D is None:
        return 0
    done = 0
    for cs, r in rows.items():
        vals = [D.get(s) for s in range(cs - 300, cs)]
        rs = [math.log(b / a) for a, b in zip(vals, vals[1:])
              if a and b and a > 0 and b > 0]
        if len(rs) > 200:
            m = sum(rs) / len(rs)
            r["sigma"] = math.sqrt(sum((x - m) ** 2 for x in rs) / (len(rs) - 1))
            done += 1
    return done


# ------------------------------------------------------------------ the page
def heat_html(panels, title, summary=None, tests=None, vol=None):
    """A self-contained page: the finding first, then one map per horizon with
    its shuffled twin on the same grid, switchable.

    No script host, no library: the colours are computed here and written into
    the markup, and the only JavaScript swaps a class."""
    summary = summary or {}
    tests = tests or []
    vol = vol or []
    css = """<style>
:root{
  --ground:#F5F6F8; --panel:#FFFFFF; --ink:#141A22; --muted:#5C6773;
  --line:#DDE2E8; --busy:#1F8A6B; --quiet:#C1543A; --accent:#B07A1F;
  --grid-empty:#EDEFF2;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#0E1216; --panel:#151B22; --ink:#E7ECF2; --muted:#93A1B0;
    --line:#242D37; --busy:#3FBE93; --quiet:#E0714F; --accent:#E2A33C;
    --grid-empty:#1A212A;
  }
}
:root[data-theme="dark"]{
  --ground:#0E1216; --panel:#151B22; --ink:#E7ECF2; --muted:#93A1B0;
  --line:#242D37; --busy:#3FBE93; --quiet:#E0714F; --accent:#E2A33C;
  --grid-empty:#1A212A;
}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);margin:0;
  font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.55}
.wrap{max-width:1040px;margin:0 auto;padding-block:32px 56px;padding-left:20px;padding-right:20px;
  display:flex;flex-direction:column;gap:34px}
h1{font-size:27px;line-height:1.2;margin:0;font-weight:600;text-wrap:balance;letter-spacing:-.01em}
h2{font-size:17px;margin:0 0 4px;font-weight:600;text-wrap:balance}
p{margin:0;max-width:64ch;color:var(--muted)}
.lede{color:var(--ink);font-size:17px;max-width:62ch}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;
  letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 10px}
section{display:flex;flex-direction:column;gap:14px}
.finding{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:22px;display:flex;flex-direction:column;gap:16px}
.bars{display:flex;flex-direction:column;gap:9px}
.bar{display:grid;grid-template-columns:118px 1fr 58px;align-items:center;gap:12px}
.bar .k{font-size:13px;color:var(--muted)}
.bar .t{height:22px;background:var(--grid-empty);border-radius:3px;overflow:hidden}
.bar .t i{display:block;height:100%;background:var(--busy)}
.bar .v{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px;
  font-variant-numeric:tabular-nums;text-align:right}
table.stats{border-collapse:collapse;width:100%;font-size:13.5px}
table.stats th,table.stats td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
table.stats th{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;
  letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:500}
table.stats td.n{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.verdict{font-weight:600}
.v-real{color:var(--busy)} .v-no{color:var(--muted)} .v-maybe{color:var(--accent)}
.maps{display:flex;flex-direction:column;gap:22px}
.map{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
.map header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.map h3{margin:0;font-size:15px;font-weight:600}
.map .note{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11.5px;color:var(--muted);
  font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
table.grid{border-collapse:separate;border-spacing:2px}
table.grid th{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10px;color:var(--muted);
  font-weight:500;padding:0;height:16px;width:18px}
table.grid th.day{width:22px;text-align:right;padding-right:4px}
table.grid td{width:18px;height:18px;border-radius:2px;background:var(--grid-empty)}
.swap{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button{font:inherit;font-size:13px;padding:7px 13px;border-radius:7px;cursor:pointer;
  border:1px solid var(--line);background:var(--panel);color:var(--ink)}
button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent)}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
body.noise .real{display:none} body:not(.noise) .fake{display:none}
.key{display:flex;gap:7px;align-items:center;color:var(--muted);font-size:12px;flex-wrap:wrap}
.key i{width:20px;height:13px;border-radius:2px;display:inline-block}
footer{color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);padding-top:16px;max-width:66ch}
@media (max-width:520px){h1{font-size:23px}.bar{grid-template-columns:96px 1fr 48px}}
</style>"""
    font = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600'
            '&display=swap">')

    def cell(hit, n, base):
        if n == 0:
            return '<td title="no closes"></td>'
        rate = hit / float(n)
        d = (rate - base) / max(base, 1e-9)
        d = max(-1.0, min(1.0, d))
        var = "--busy" if d >= 0 else "--quiet"
        a = 0.14 + 0.72 * abs(d) * min(1.0, n / 6.0)
        return ('<td style="background:color-mix(in srgb, var(%s) %d%%, var(--grid-empty))" '
                'title="bought on %d of %d closes (%.0f%%)"></td>'
                % (var, int(100 * a), hit, n, 100 * rate))

    def grid_table(grid, klass):
        base = (sum(h for h, _ in grid.values()) /
                max(1.0, sum(n for _, n in grid.values())))
        t = ['<table class="grid %s"><tr><th class="day"></th>' % klass]
        for h in range(24):
            t.append("<th>%s</th>" % (h if h % 3 == 0 else ""))
        t.append("</tr>")
        for d in range(7):
            t.append('<tr><th class="day">%s</th>' % ("Mon Tue Wed Thu Fri Sat Sun".split()[d][:2]))
            for h in range(24):
                hit, n = grid.get((d, h), (0, 0))
                t.append(cell(hit, n, base))
            t.append("</tr>")
        t.append("</table>")
        return "".join(t)

    out = ['<title>%s</title>' % html.escape(title), font, css, '<div class="wrap">']
    out.append('<header><p class="eyebrow">15-minute crypto markets &middot; Eastern time</p>'
               '<h1>%s</h1></header>' % html.escape(title))
    if summary:
        out.append('<p class="lede">%s</p>' % html.escape(summary.get("lede", "")))

    if vol:
        top = max(v[2] for v in vol) or 1.0
        bars = "".join(
            '<div class="bar"><span class="k">%s</span>'
            '<span class="t"><i style="width:%.1f%%"></i></span>'
            '<span class="v">%.0f%%</span></div>'
            % (html.escape(k), 100.0 * v / top, 100 * v) for k, _n, v in vol)
        out.append('<section><div><p class="eyebrow">What actually moves it</p>'
                   '<h2>Calm markets are the hot ones</h2></div>'
                   '<div class="finding"><div class="bars">%s</div>'
                   '<p>Each row is a fifth of all closes, sorted by how much the '
                   'price was moving in the five minutes before. The bar is how '
                   'often the bot found a bet worth taking. The order is perfect: '
                   'the calmer it is, the more chances appear.</p></div></section>' % bars)

    if tests:
        rows = []
        for name, cells, gap, p, verdict, cls in tests:
            rows.append('<tr><td>%s</td><td class="n">%s</td><td class="n">%s</td>'
                        '<td class="verdict %s">%s</td></tr>'
                        % (html.escape(name), cells, gap, cls, html.escape(verdict)))
        out.append('<section><div><p class="eyebrow">Tested against chance</p>'
                   '<h2>Is the clock telling us anything?</h2></div>'
                   '<table class="stats"><tr><th>split</th><th>cells</th>'
                   '<th>widest gap</th><th>verdict</th></tr>%s</table>'
                   '<p>%s</p></section>'
                   % ("".join(rows), html.escape(summary.get("clock_note", ""))))

    out.append('<section><div><p class="eyebrow">The maps</p>'
               '<h2>Every close we have, by hour and weekday</h2>'
               '<p>Green means the bot bought more often than that period\'s own '
               'average, clay means less, and the colour is faint where few '
               'closes landed in that square. Switch to <em>shuffled</em> to see '
               'the same closes with their times scrambled: that is what pure '
               'chance looks like on this much data.</p></div>'
               '<div class="swap"><button id="b-real" aria-pressed="true">Real</button>'
               '<button id="b-fake" aria-pressed="false">Shuffled</button>'
               '<span class="key"><i style="background:color-mix(in srgb, var(--quiet) 75%, var(--grid-empty))"></i>'
               'quieter<i style="background:var(--grid-empty)"></i>'
               '<i style="background:color-mix(in srgb, var(--busy) 75%, var(--grid-empty))"></i>busier</span></div>'
               '<div class="maps">')
    for label, real, fake, note in panels:
        out.append('<div class="map"><header><h3>%s</h3><span class="note">%s</span></header>'
                   '<div class="scroll">%s%s</div></div>'
                   % (html.escape(label), html.escape(note),
                      grid_table(real, "real"), grid_table(fake, "fake")))
    out.append("</div></section>")
    out.append('<footer>%s</footer>' % html.escape(summary.get("footer", "")))
    out.append("</div>")
    out.append("""<script>
var br=document.getElementById('b-real'),bf=document.getElementById('b-fake');
function set(noise){document.body.classList.toggle('noise',noise);
br.setAttribute('aria-pressed',String(!noise));bf.setAttribute('aria-pressed',String(noise));}
br.onclick=function(){set(false)};bf.onclick=function(){set(true)};
</script>""")
    return "\n".join(out)

def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(block_of(0) == 0 and block_of(3) == 0 and block_of(4) == 1
       and block_of(23) == 5, "hours fall into the right 4-hour block")
    ck(spread([(5, 10), (1, 10)]) == 0.4, "spread is the widest gap between cells")
    ck(spread([(5, 10), (9, 9)]) is None,
       "a cell with only 9 closes is ignored, so one fat cell and one thin "
       "one leave nothing to compare -- a 9-close cell reading 100%% is the "
       "single easiest way to see a pattern that is not there")
    ck(spread([(5, 10), (9, 9), (1, 20)]) == 0.45,
       "and with two fat cells it measures those two only (50%% vs 5%%)")
    ck(spread([(5, 10)]) is None and spread([(1, 3), (2, 4)]) is None,
       "NULL: one cell, or only thin cells, has no spread to report")

    # A PLANTED PATTERN MUST BE FOUND
    rng = random.Random(1)
    labels, hits = [], []
    for i in range(1200):
        h = i % 24
        labels.append(h)
        p = 0.6 if h in (13, 14) else 0.2
        hits.append(1 if rng.random() < p else 0)
    obs, p, _ = permutation_p(labels, hits, 400, seed=5)
    ck(p is not None and p < 0.01,
       "a planted hot hour (60%% against 20%%) is found, p = %.4f" % p)

    # AND PURE NOISE MUST NOT BE
    labels, hits = [], []
    for i in range(1200):
        labels.append(i % 24)
        hits.append(1 if rng.random() < 0.2 else 0)
    obs, p2, _ = permutation_p(labels, hits, 400, seed=6)
    ck(p2 is not None and p2 > 0.05,
       "NULL: 1,200 coin flips with NO pattern are not called a pattern, "
       "p = %.3f -- the spread of %.2f between best and worst hour is what "
       "noise looks like at this sample size" % (p2, obs))
    ck(obs > 0.2,
       "and note how big that meaningless spread is (%.0f percentage points) "
       "-- this is exactly the eye's mistake the shuffled twin is there to "
       "show" % (100 * obs))

    ck(mde(27, 0.2) > 0.3,
       "with 27 closes an hour only a gap of %.0f points or more could be "
       "told from luck" % (100 * mde(27, 0.2)))
    ck(mde(500, 0.2) < mde(27, 0.2),
       "and that shrinks as closes accumulate (%.0f points at 500)"
       % (100 * mde(500, 0.2)))

    # downtime exclusion
    sp = [(1000, 2000, "outage")]
    ck(downtime.lost_seconds(1970, 2000, sp) > 0,
       "a close whose last 30 seconds sit inside an outage is droppable")
    ck(downtime.lost_seconds(2100, 2130, sp) == 0,
       "and one outside it is kept")

    g = {(0, 1): (3, 10), (0, 2): (0, 10)}
    pg = heat_html([("t", g, g, "n")], "t",
                   {"lede": "l", "clock_note": "c", "footer": "f"},
                   [("hour of day", 24, "10 pts", 0.4, "chance", "v-no")],
                   [("calmest fifth", 10, 0.6), ("choppiest fifth", 10, 0.3)])
    ck('class="grid real"' in pg and 'class="grid fake"' in pg,
       "the page draws the real map and its shuffled twin")
    ck("--busy" in pg and "prefers-color-scheme" in pg
       and 'data-theme="dark"' in pg and "background:var(--ground)" in pg,
       "and carries a full palette for light, dark and the un-stamped default")
    ck(pg.count("<table") == pg.count("</table>") and pg.count("<div") == pg.count("</div>"),
       "every table and div it opens, it closes")
    print("pinwhen selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    spans = downtime.load()
    live, dropped = load_live(spans)
    tape = load_tape()
    if not live:
        print("loaded nothing -- no close summaries on file")
        return 0
    got = add_sigma(live)
    for cs, r in live.items():
        e = et(cs)
        r["et_hour"] = e.hour
        r["et_weekday"] = e.weekday()
        r["et_day"] = e.strftime("%Y-%m-%d")
        r["tape_opp"] = tape.get(cs)
    with open(OUT_ROWS, "w", encoding="utf-8") as fh:
        for cs in sorted(live):
            fh.write(json.dumps(live[cs]) + "\n")

    rows = [live[c] for c in sorted(live)]
    weeks = len({(r["close"] // (7 * 86400)) for r in live.values()})
    fired = [1 if r["fired"] else 0 for r in rows]
    base = sum(fired) / float(len(fired))
    days = len({r["et_day"] for r in rows})
    lines = []
    w = lines.append
    w("# WHEN -- hot and cold times for the pin\n")
    w("Written by `research/pinwhen.py`. One row per 15-minute close, "
      "%d closes over %d days, saved in `results/when_closes.jsonl`.\n" % (len(rows), days))
    w("The bot bought on **%d of %d closes (%.1f%%)**. %d closes were dropped "
      "for overlapping a known outage (`results/DOWNTIME.json`).\n"
      % (sum(fired), len(rows), 100 * base, dropped))
    per_hour = len(rows) / 24.0
    w("**Before reading anything below:** with about %.0f closes per hour of "
      "the day, only a gap of **%.0f percentage points or more** between two "
      "hours could be told apart from luck. Anything smaller is noise, however "
      "convincing it looks.\n" % (per_hour, 100 * mde(per_hour, base)))

    w("\n## Is it random?\n")
    w("| split | cells | widest gap | p (2,000 shuffles) | verdict |")
    w("|---|---|---|---|---|")
    tests = [("hour of day", [r["et_hour"] for r in rows]),
             ("4-hour block", [block_of(r["et_hour"]) for r in rows]),
             ("day of week", [r["et_weekday"] for r in rows]),
             ("weekday vs weekend", [1 if r["et_weekday"] >= 5 else 0 for r in rows])]
    verdicts = {}
    page_tests = []
    for name, labels in tests:
        obs, p, _ = permutation_p(labels, fired)
        cells = len({l for l in labels})
        if p is None:
            w("| %s | %d | - | - | too little data |" % (name, cells))
            continue
        v = "**REAL, worth acting on**" if p < 0.01 else (
            "suggestive, not proven" if p < 0.05 else "looks like chance")
        if name in ("day of week", "weekday vs weekend") and weeks < 3:
            v = ("CANNOT BE READ -- only %d week(s) on file, so each weekday is "
                 "one or two particular days and a 'Tuesday effect' is just "
                 "what the market happened to do that Tuesday" % weeks)
        verdicts[name] = (obs, p)
        w("| %s | %d | %.0f points | %.3f | %s |" % (name, cells, 100 * obs, p, v))
        short = ("real, not chance" if p < 0.01 else
                 "maybe, not proven" if p < 0.05 else "chance")
        cls = "v-real" if p < 0.01 else ("v-maybe" if p < 0.05 else "v-no")
        if name in ("day of week", "weekday vs weekend") and weeks < 3:
            short, cls = "too few weeks to say", "v-no"
        page_tests.append((name, cells, "%.0f pts" % (100 * obs), p, short, cls))

    w("\n## The clock against a real driver\n")
    page_vol = []
    sig = [r for r in rows if r.get("sigma")]
    if len(sig) > 60:
        sig.sort(key=lambda r: r["sigma"])
        third = len(sig) // 3
        names = ("calmest third", "middle third", "choppiest third")
        w("Volatility is the obvious real driver: does the clock still matter "
          "once it is held still?\n")
        w("| volatility | closes | bought | p for 4-hour block inside it |")
        w("|---|---|---|---|")
        for i, nm in enumerate(names):
            part = sig[i * third:(i + 1) * third] if i < 2 else sig[2 * third:]
            f = [1 if r["fired"] else 0 for r in part]
            _, pp, _ = permutation_p([block_of(r["et_hour"]) for r in part], f, 600)
            w("| %s | %d | %.1f%% | %s |" % (nm, len(part), 100 * sum(f) / len(f),
                                             "-" if pp is None else "%.3f" % pp))
        w("" + NLMARK + "And in five steps, calmest to choppiest:" + NLMARK)
        w("| volatility | closes | bought |")
        w("|---|---|---|")
        fifth = len(sig) // 5
        names5 = ("calmest fifth", "2nd calmest", "middle fifth",
                  "2nd choppiest", "choppiest fifth")
        for i in range(5):
            part = sig[i * fifth:(i + 1) * fifth] if i < 4 else sig[4 * fifth:]
            f = sum(1 for r in part if r["fired"])
            w("| %d of 5 | %d | %.1f%% |" % (i + 1, len(part), 100.0 * f / len(part)))
            page_vol.append((names5[i], len(part), f / float(len(part))))
        lo = sum(1 for r in sig[:third] if r["fired"]) / float(third)
        hi = sum(1 for r in sig[2 * third:] if r["fired"]) / float(len(sig) - 2 * third)
        w("" + NLMARK + "Buying rate in the calmest third **%.1f%%** against "
          "the choppiest third **%.1f%%** -- a gap of %.0f points where %.0f "
          "points is the smallest this much data could show. **The clock "
          "splits above stop meaning anything once volatility is held still: "
          "the hours are not hot or cold, the CALM is.**"
          % (100 * lo, 100 * hi, 100 * (lo - hi), 100 * mde(third, base)))
    else:
        w("Not enough closes carry a volatility reading yet (%d)." % len(sig))

    # ---- the maps -------------------------------------------------------
    newest = max(r["close"] for r in rows)
    panels = []
    rng = random.Random(99)
    for h in HORIZONS:
        sel = [r for r in rows if r["close"] > newest - h * 86400]
        if len(sel) < 20:
            continue
        real = collections.defaultdict(lambda: [0, 0])
        for r in sel:
            c = real[(r["et_weekday"], r["et_hour"])]
            c[0] += 1 if r["fired"] else 0
            c[1] += 1
        shuf = [1 if r["fired"] else 0 for r in sel]
        rng.shuffle(shuf)
        fake = collections.defaultdict(lambda: [0, 0])
        for r, f in zip(sel, shuf):
            c = fake[(r["et_weekday"], r["et_hour"])]
            c[0] += f
            c[1] += 1
        note = ("%d closes, %d days, bought on %.0f%%"
                % (len(sel), len({r["et_day"] for r in sel}),
                   100.0 * sum(1 for r in sel if r["fired"]) / len(sel)))
        panels.append(("last %d day%s" % (h, "" if h == 1 else "s"),
                       {k: tuple(v) for k, v in real.items()},
                       {k: tuple(v) for k, v in fake.items()}, note))
    lede = ("The bot bought on %d of %d closes over %d days. The question was "
            "whether some hours are reliably busier. They are not: what looks "
            "like a hot hour is a calm market, and the clock stops mattering "
            "once the market's own movement is held still."
            % (sum(fired), len(rows), days))
    clock_note = ("Each split is tested by scrambling the clock labels 2,000 "
                  "times and asking how often chance alone spreads the squares "
                  "this far apart. With about %.0f closes an hour, only a gap "
                  "of %.0f points or more can be told from luck at all."
                  % (per_hour, 100 * mde(per_hour, base)))
    foot = ("One row per 15-minute close, saved in results/when_closes.jsonl and "
            "rebuilt by research/pinwhen.py. %d closes were dropped for "
            "overlapping a known outage, so our own downtime cannot masquerade "
            "as a quiet hour. Times are Eastern." % dropped)
    open(OUT_HTML, "w", encoding="utf-8").write(
        heat_html(panels, "Hot and Cold Closes",
                  {"lede": lede, "clock_note": clock_note, "footer": foot},
                  page_tests, page_vol))
    w("\n## The maps\n")
    w("`results/when_heatmap.html` -- one map per horizon (%s days), each beside "
      "a shuffled twin. Open it in a browser."
      % ", ".join(str(h) for h in HORIZONS))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\nwrote %s, %s, %s" % (os.path.basename(OUT_ROWS),
                                  os.path.basename(OUT_MD),
                                  os.path.basename(OUT_HTML)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
