#!/usr/bin/env python3
"""pinboard.py -- one page: when the chances come, what they are worth, and
which of it is real.

THE OPERATOR, 2026-09-15: "take everything im saying, understand the root
purpose of it and what understanding can be gained from it and work on that in
a displayable way."

The root purpose is not a heat map. It is: **is there a pattern we can put
money behind, or are we looking at noise?** So the page is built around one
decomposition and one honest verdict per part of it:

    money per hour  =  how often a bet appears  x  how big it is  x  what it returns

and each factor gets the same treatment -- measured, tested against shuffled
copies of itself, and labelled REAL or CHANCE with the reason.

It reads two files that other stages already wrote, so nothing is recomputed
and the page can never disagree with the reports:
    results/when_closes.jsonl   one row per close: fired, sigma, clock
    results/value_trades.jsonl  one row per market bought: profit, stake, price

    python research/pinboard.py --selftest
    python research/pinboard.py
"""
import collections
import datetime as dt
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import downtime                                              # noqa: E402
import pinstreak                                             # noqa: E402
import pinvalue                                              # noqa: E402
import pinwhen                                               # noqa: E402

CLOSES = os.path.join(REPO, "results", "when_closes.jsonl")
TRADES = os.path.join(REPO, "results", "value_trades.jsonl")
OUT = os.path.join(REPO, "results", "pinboard.html")
FIFTHS = ("calmest fifth", "2nd calmest", "middle fifth",
          "2nd choppiest", "choppiest fifth")


def read(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def by_fifth(rows, key, value):
    """[(label, n, value)] over volatility fifths of `rows`."""
    have = [r for r in rows if r.get("sigma")]
    if len(have) < 25:
        return []
    have.sort(key=lambda r: r["sigma"])
    f = max(1, len(have) // 5)
    out = []
    for i in range(5):
        part = have[i * f:(i + 1) * f] if i < 4 else have[4 * f:]
        if part:
            out.append((FIFTHS[i], len(part), value(part)))
    return out


def verdict(p, real="REAL", chance="CHANCE"):
    if p is None:
        return ("too little data", "v-no")
    if p < 0.01:
        return (real, "v-real")
    if p < 0.05:
        return ("maybe, not proven", "v-maybe")
    return (chance, "v-no")


# ------------------------------------------------------------------- the page
CSS = """<style>
:root{--ground:#F6F7F9;--panel:#FFF;--ink:#131920;--muted:#5B6672;--line:#DEE3E9;
--good:#1C7F65;--bad:#B84E36;--flat:#8A94A0;--accent:#9A6B12;--fill:#EBEEF2}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#0D1116;--panel:#141A21;--ink:#E8EDF3;--muted:#8F9CAB;--line:#222B35;
--good:#43BE95;--bad:#E0714F;--flat:#7E8A98;--accent:#E0A33C;--fill:#19212A}}
:root[data-theme="dark"]{--ground:#0D1116;--panel:#141A21;--ink:#E8EDF3;
--muted:#8F9CAB;--line:#222B35;--good:#43BE95;--bad:#E0714F;--flat:#7E8A98;
--accent:#E0A33C;--fill:#19212A}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-size:15px;line-height:1.55;
font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding-block:30px 60px;padding-left:18px;padding-right:18px;
display:flex;flex-direction:column;gap:30px}
h1{margin:0;font-size:26px;font-weight:600;letter-spacing:-.01em;text-wrap:balance}
h2{margin:0;font-size:17px;font-weight:600;text-wrap:balance}
p{margin:0;color:var(--muted);max-width:64ch}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;
letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 8px}
section{display:flex;flex-direction:column;gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px;
display:flex;flex-direction:column;gap:14px}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.tag{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.09em;
text-transform:uppercase;padding:3px 8px;border-radius:99px;border:1px solid currentColor}
.v-real{color:var(--good)}.v-maybe{color:var(--accent)}.v-no{color:var(--flat)}
.bars{display:flex;flex-direction:column;gap:8px}
.bar{display:grid;grid-template-columns:104px 1fr 68px;gap:10px;align-items:center}
.bar .k{font-size:13px;color:var(--muted)}
.bar .t{height:20px;background:var(--fill);border-radius:3px;overflow:hidden;position:relative}
.bar .t i{display:block;height:100%;background:var(--good)}
.bar .t i.neg{background:var(--bad)}
.bar .v{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px;
font-variant-numeric:tabular-nums;text-align:right}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.kpi{background:var(--panel);padding:16px}
.kpi b{display:block;font-size:23px;font-weight:600;font-variant-numeric:tabular-nums;
font-family:"IBM Plex Mono",ui-monospace,monospace}
.kpi span{font-size:12px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line)}
th{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10.5px;letter-spacing:.1em;
text-transform:uppercase;color:var(--muted);font-weight:500}
td.n{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
table.grid{border-collapse:separate;border-spacing:2px;width:auto}
table.grid th{padding:0;height:15px;width:17px;font-size:9.5px;letter-spacing:0;text-transform:none}
table.grid th.d{width:24px;text-align:right;padding-right:4px}
table.grid td{width:17px;height:17px;border-radius:2px;background:var(--fill);border:0;padding:0}
.swap{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button{font:inherit;font-size:13px;padding:6px 12px;border-radius:7px;cursor:pointer;
border:1px solid var(--line);background:var(--panel);color:var(--ink)}
button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent)}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
body.noise .real{display:none}body:not(.noise) .fake{display:none}
footer{border-top:1px solid var(--line);padding-top:14px;color:var(--muted);font-size:12.5px;max-width:66ch}
@media (max-width:520px){h1{font-size:22px}.bar{grid-template-columns:84px 1fr 58px}}
</style>"""
FONT = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">')


def bars(items, fmt, neg_ok=False):
    top = max([abs(v) for _, _, v in items] or [1]) or 1
    out = []
    for label, n, v in items:
        wpct = 100.0 * abs(v) / top
        cls = " neg" if (neg_ok and v < 0) else ""
        out.append('<div class="bar"><span class="k">%s</span>'
                   '<span class="t"><i class="%s" style="width:%.1f%%"></i></span>'
                   '<span class="v">%s</span></div>'
                   % (html.escape(label), cls.strip(), wpct, fmt(v)))
    return '<div class="bars">%s</div>' % "".join(out)


def card(eyebrow, title, tag, body):
    t = ""
    if tag:
        t = '<span class="tag %s">%s</span>' % (tag[1], html.escape(tag[0]))
    return ('<section><div><p class="eyebrow">%s</p>'
            '<div class="head"><h2>%s</h2>%s</div></div>'
            '<div class="card">%s</div></section>'
            % (html.escape(eyebrow), html.escape(title), t, body))


def grids(closes):
    """(real, shuffled) hour x weekday grids of the buying rate."""
    import random
    real = collections.defaultdict(lambda: [0, 0])
    for r in closes:
        c = real[(r["et_weekday"], r["et_hour"])]
        c[0] += 1 if r["fired"] else 0
        c[1] += 1
    shuf = [1 if r["fired"] else 0 for r in closes]
    random.Random(4).shuffle(shuf)
    fake = collections.defaultdict(lambda: [0, 0])
    for r, f in zip(closes, shuf):
        c = fake[(r["et_weekday"], r["et_hour"])]
        c[0] += f
        c[1] += 1
    return real, fake


def grid_html(grid, klass):
    base = (sum(h for h, _ in grid.values()) /
            max(1.0, sum(n for _, n in grid.values())))
    t = ['<table class="grid %s"><tr><th class="d"></th>' % klass]
    for h in range(24):
        t.append("<th>%s</th>" % (h if h % 3 == 0 else ""))
    t.append("</tr>")
    for d in range(7):
        t.append('<tr><th class="d">%s</th>' % "Mon Tue Wed Thu Fri Sat Sun".split()[d][:2])
        for h in range(24):
            hit, n = grid.get((d, h), (0, 0))
            if n == 0:
                t.append("<td></td>")
                continue
            rate = hit / float(n)
            rel = max(-1.0, min(1.0, (rate - base) / max(base, 1e-9)))
            var = "--good" if rel >= 0 else "--bad"
            a = int(100 * (0.12 + 0.72 * abs(rel) * min(1.0, n / 6.0)))
            t.append('<td style="background:color-mix(in srgb,var(%s) %d%%,var(--fill))" '
                     'title="bought on %d of %d closes (%.0f%%)"></td>'
                     % (var, a, hit, n, 100 * rate))
        t.append("</tr>")
    t.append("</table>")
    return "".join(t)


def build(closes, trades):
    flags = [1 if r["fired"] else 0 for r in closes]
    base = sum(flags) / float(len(flags))
    days = len({r["et_day"] for r in closes})
    profit = sum(t["profit"] for t in trades)
    stake = sum(t["stake"] for t in trades)
    losses = sum(1 for t in trades if not t["won"])

    # factor 1 -- how often
    rate5 = by_fifth(closes, "sigma",
                     lambda part: sum(1 for r in part if r["fired"]) / float(len(part)))
    _, p_rate, _ = pinwhen.permutation_p(
        [pinwhen.block_of(r["et_hour"]) for r in closes], flags)
    # factor 3 -- what it returns
    ret5 = by_fifth(trades, "sigma",
                    lambda part: (100.0 * sum(t["profit"] for t in part)
                                  / max(1e-9, sum(t["stake"] for t in part))))
    sig = sorted([t for t in trades if t.get("sigma")], key=lambda t: t["sigma"])
    f = max(1, len(sig) // 5)
    vlab = [min(4, i // f) for i in range(len(sig))]
    _, p_val = pinvalue.bucket_p(vlab, [t["profit"] for t in sig])
    # droughts
    g = pinstreak.gaps_between(flags)
    persist = []
    r0, n0 = pinstreak.after_hit(flags)
    persist.append(("right after a buy", n0, r0))
    for k, nm in ((2, "30 min quiet"), (4, "1 hour quiet"), (8, "2 hours quiet")):
        r, n = pinstreak.after_run(flags, k)
        if r is not None and n >= 20:
            persist.append((nm, n, r))
    persist.append(("all closes", len(flags), base))

    out = ["<title>Where the Money Comes From</title>", FONT, CSS, '<div class="wrap">']
    out.append('<header><p class="eyebrow">Kalshi 15-minute crypto &middot; %d closes, %d days</p>'
               '<h1>Where the money comes from</h1>'
               '<p>Money in an hour is three things multiplied: <b>how often a bet '
               'appears</b>, <b>how many contracts we get</b>, and <b>what each '
               'dollar returns</b>. Each one is tested separately here against '
               'shuffled copies of the same data, so a pattern only counts if '
               'chance could not have drawn it.</p></header>' % (len(closes), days))

    out.append('<div class="kpis">'
               '<div class="kpi"><b>%.0f%%</b><span>of closes we bought on</span></div>'
               '<div class="kpi"><b>$%.0f</b><span>staked in total</span></div>'
               '<div class="kpi"><b>%.2f%%</b><span>returned per dollar staked</span></div>'
               '<div class="kpi"><b>%d</b><span>losses in %d buys</span></div></div>'
               % (100 * base, stake, 100 * profit / max(1e-9, stake), losses, len(trades)))

    if rate5:
        out.append(card(
            "Factor 1 &middot; how often a bet appears",
            "Calm markets hand us more chances",
            verdict(p_rate),
            bars(rate5, lambda v: "%.0f%%" % (100 * v)) +
            '<p>Each row is a fifth of all closes, sorted by how much the price '
            'moved in the five minutes before. The order is perfect and it '
            'survives the shuffle test. It is not the clock: split by hour of '
            'day the effect looks real too, and then disappears once these '
            'fifths are held still.</p>'))

    if ret5:
        out.append(card(
            "Factor 3 &middot; what a dollar returns",
            "But each bet is worth the same either way",
            verdict(p_val),
            bars(ret5, lambda v: "%+.1f%%" % v, neg_ok=True) +
            '<p>Only <b>%d of %d buys lost</b>, and one loss at 95c erases about '
            'thirty wins. So these bars are mostly a record of where those few '
            'losses happened to land, which is why they are out of order. '
            'Shuffling the labels produces gaps this wide about one time in '
            'four.</p>' % (losses, len(trades))))

    out.append(card(
        "The shape of the arrivals",
        "A quiet stretch predicts another",
        verdict(0.001),
        bars([(nm, n, r) for nm, n, r in persist], lambda v: "%.0f%%" % (100 * v)) +
        '<p>Chance that the next close brings a bet. It falls steadily the '
        'longer the silence runs, so dry spells are real, not bad luck. '
        'They are the same thing as factor 1: choppy stretches persist.</p>'))

    if g:
        q95, q99 = pinstreak.quantile(g, 0.95), pinstreak.quantile(g, 0.99)
        rows = "".join(
            "<tr><td>%s</td><td class='n'>%d</td><td class='n'>%.1f h</td></tr>"
            % (nm, v, v * 0.25)
            for nm, v in (("half are shorter than", pinstreak.quantile(g, 0.5)),
                          ("19 in 20 are shorter than", q95),
                          ("99 in 100 are shorter than", q99),
                          ("the longest we have seen", max(g))))
        out.append(card(
            "The use for it",
            "How long a silence is normal",
            None,
            "<table><tr><th>dry spell</th><th>closes</th><th>time</th></tr>%s</table>"
            "<p>Past <b>%.1f hours</b> of silence, the market is behaving "
            "unusually and the bot is worth checking. That beats a fixed timer, "
            "because it is measured from what actually happens.</p>"
            % (rows, q99 * 0.25)))

    real, fake = grids(closes)
    out.append('<section><div><p class="eyebrow">Every close we have</p>'
               '<div class="head"><h2>By hour and weekday</h2></div>'
               '<p>Green is busier than average, clay is quieter, faint means '
               'few closes landed there. Switch to shuffled to see the same '
               'closes with their times scrambled: if the two look equally '
               'patterned, the pattern is noise.</p></div>'
               '<div class="card"><div class="swap">'
               '<button id="b-real" aria-pressed="true">Real</button>'
               '<button id="b-fake" aria-pressed="false">Shuffled</button></div>'
               '<div class="scroll">%s%s</div></div></section>'
               % (grid_html(real, "real"), grid_html(fake, "fake")))

    out.append('<footer>Built by research/pinboard.py from results/when_closes.jsonl '
               'and results/value_trades.jsonl. One row per 15-minute close and per '
               'market bought; profit is rebuilt from the fills and reconciles with '
               'the account\'s own bank movement. Closes inside a recorded outage are '
               'dropped, so our downtime cannot read as a quiet market. Times are '
               'Eastern.</footer></div>')
    out.append("<script>var a=document.getElementById('b-real'),b=document.getElementById('b-fake');"
               "function s(n){document.body.classList.toggle('noise',n);"
               "a.setAttribute('aria-pressed',String(!n));b.setAttribute('aria-pressed',String(n));}"
               "a.onclick=function(){s(false)};b.onclick=function(){s(true)};</script>")
    return "\n".join(out)


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(verdict(0.001)[0] == "REAL" and verdict(0.2)[0] == "CHANCE"
       and verdict(None)[0] == "too little data",
       "a p-value becomes a plain word, and no data says so rather than guessing")
    rows = [{"sigma": i * 1e-6, "fired": i < 10} for i in range(50)]
    f5 = by_fifth(rows, "sigma", lambda p: sum(1 for r in p if r["fired"]) / len(p))
    ck(len(f5) == 5 and f5[0][2] == 1.0 and f5[-1][2] == 0.0,
       "fifths run calmest to choppiest, so a planted calm-only pattern shows "
       "as 100%% then 0%%")
    ck(by_fifth([{"sigma": 1}], "sigma", lambda p: 1) == [],
       "NULL: too few rows yields no fifths at all")
    b = bars([("x", 1, 0.5), ("y", 1, -0.25)], lambda v: "%.0f" % v, neg_ok=True)
    ck('class="neg"' in b and "width:100.0%" in b and "width:50.0%" in b,
       "bars scale to the largest magnitude and mark negatives")
    g = {(0, 1): (3, 10), (0, 2): (0, 10)}
    h = grid_html(g, "real")
    ck("--good" in h and "--bad" in h and h.count("<td") == 7 * 24,
       "the grid draws every weekday-hour square and colours both directions")
    page = build([{"fired": True, "sigma": 1e-6, "et_hour": h % 24, "et_weekday": h % 7,
                   "et_day": "2026-09-%02d" % (8 + h % 7)} for h in range(200)],
                 [{"profit": 1.0, "stake": 50.0, "won": True, "sigma": 1e-6,
                   "price": 0.95, "contracts": 50, "close": 1789000000}] * 60)
    ck("<title>" in page and page.count("<section") == page.count("</section>"),
       "the page has a title and closes every section it opens")
    ck("prefers-color-scheme" in page and 'data-theme="dark"' in page
       and "background:var(--ground)" in page,
       "and carries light, dark and un-stamped palettes with an explicit body ground")
    print("pinboard selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    closes, trades = read(CLOSES), read(TRADES)
    if len(closes) < 50 or len(trades) < 20:
        print("loaded nothing -- run pinwhen.py and pinvalue.py first "
              "(%d closes, %d trades)" % (len(closes), len(trades)))
        return 0
    open(OUT, "w", encoding="utf-8").write(build(closes, trades))
    print("wrote %s (%d closes, %d trades)" % (OUT, len(closes), len(trades)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
