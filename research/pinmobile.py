"""pinmobile.py -- the desktop tool, as one page you can open on a phone.

WHY THIS EXISTS. The operator, 2026-09-18: *"Can this run on iPad? Is it
possible to make that a thing?"* and then, when he was handed a page that
answered his questions instead: *"No I wanted a mobile version for the desktop
tool, not my questions."*

So this is `pindesk` -- the same tabs, the same numbers, the same wording --
rendered as a single self-contained page. It is a SNAPSHOT, not a live app: it
reads the ledger once, embeds what it found, and writes the file. Re-run it to
refresh.

**EVERY NUMBER COMES FROM `pindesk` ITSELF.** Not from a re-implementation of
it. `Ledger`, `health()`, `status_of()`, `summary()`, `fill_stats()` and the
story functions are imported and called, because a phone view that computes
its own totals is a second set of numbers to keep honest, and this project has
already shipped that bug more than once -- the desktop tool and the Telegram
bot disagreed about the same day for three days running.

What it deliberately does NOT do: start, pause or stop the bot. A snapshot
cannot honestly offer a control, and a button that silently does nothing on a
page the operator trusts is worse than no button.
"""
import argparse
import html
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
os.environ.setdefault("KALS_DASH_SELFTESTED", "1")

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
OUT = os.path.join(RESULTS, "pinmobile.html")


def _money(v):
    return None if v is None else round(float(v), 2)


def collect(ledger=None, results=None):
    """Everything the page shows, as plain JSON-able data.

    Separated from rendering so the self-test can build a page from a known
    ledger and check the numbers survive the trip.
    """
    import pindesk
    if ledger is None:
        ledger = pindesk.Ledger(results=results or RESULTS)
        ledger.refresh()
    h = pindesk.health(ledger)
    state, headline, detail, _c = pindesk.status_of(h)
    b = ledger.bank() or {}
    dep = ledger.deposited()
    now = time.time()
    today = pindesk.et_day(now)
    yday = pindesk.et_day(now - 86400)

    def tile(rows, base=None):
        if rows is None:
            return None
        s = pindesk.Ledger.summary(rows)
        s = {k: (_money(v) if isinstance(v, float) else v) for k, v in s.items()}
        s["pct"] = (round(100.0 * s["net"] / base, 2)
                    if base else None)
        return s

    run_rows = ledger.run_settled()
    st = ledger.last_start()
    d = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "built_et": pindesk.et_str(now, "%b %d, %I:%M %p"),
        "state": state, "headline": headline, "detail": detail,
        "bank": _money(b.get("bank")), "size": b.get("size"),
        "deposited": _money(dep),
        "tiles": {
            "today": tile(ledger.settled_on(today),
                          ledger.bank_at(pindesk.et_day_start(today))),
            "yday": tile(ledger.settled_on(yday),
                         ledger.bank_at(pindesk.et_day_start(yday))),
            "run": tile(run_rows,
                        ledger.bank_at(st["t"]) if st and st.get("t") else None),
            "all": tile(ledger.settled, dep),
        },
        "run_since": (pindesk.et_str(st["t"]) if st and st.get("t") else None),
        "open": h.get("open") or {},
        "supply": h.get("supply_lines") or [],
        "supply_age_d": h.get("supply_age_d"),
        "sys": {
            "disk_gb": round(h.get("disk_gb") or 0, 1),
            "ram_gb": round(h.get("ram_gb") or 0, 1),
            "kalshi_ok": bool(h.get("kalshi_ok")),
            "feeds_ok": bool(h.get("feeds_ok")),
            "kalshi_chans": len(h.get("kalshi_chans") or []),
            "feeds_chans": len(h.get("feeds_chans") or []),
            "paper_arms": h.get("paper_arms"),
            "flat": h.get("flat"),
            "watchdog_s": h.get("watchdog_s"),
            "phone_s": h.get("phone_s"),
        },
    }

    # settled, newest first
    rows = []
    for s in sorted(ledger.settled, key=lambda x: -(x.get("t") or 0))[:40]:
        rows.append({
            "when": pindesk.et_str(s.get("t")),
            "coin": pindesk.coin(s.get("tk") or ""),
            "close": pindesk.et_str(s.get("close")) if s.get("close") else "",
            "want": (s.get("want") or "").upper(),
            "cost": s.get("cost"),
            "result": s.get("result"),
            "pnl": _money(s.get("pnl")),
            "hedged": bool(s.get("hedged")),
        })
    d["settled"] = rows

    # losing closes
    d["losses"] = [{
        "close": pindesk.et_str(c, "%b %d, %I:%M %p") if c else "?",
        "net": _money(net),
        "coins": sorted({pindesk.coin(l["tk"]) for l in legs if l.get("tk")}),
        "legs": len(legs),
    } for c, net, legs in ledger.losing_closes()[:30]]

    # per ET day
    days = {}
    for s in ledger.settled:
        if not s.get("t"):
            continue
        days.setdefault(pindesk.et_day(s["t"]), []).append(s)
    drows = []
    for k in sorted(days, reverse=True)[:30]:
        b0 = ledger.bank_at(pindesk.et_day_start(k))
        t = tile(days[k], b0)
        t["day"] = k
        t["bank_start"] = _money(b0)
        drows.append(t)
    d["days"] = drows

    # last quarter-hours seen
    d["closes"] = [{
        "close": pindesk.et_str(c.get("close")) if c.get("close") else "?",
        "share": pindesk.Ledger.offer_share(c),
        "why": ledger.reason(c),
        "fired": bool(c.get("fired")),
    } for c in list(reversed(ledger.closes))[:25]]
    act = ledger.activity()
    d["sellers"] = {"level": act.get("level"),
                    "recent": act.get("recent"),
                    "median": act.get("median")}
    fs = pindesk.Ledger.fill_stats(ledger.fills_on(today))
    d["fills_today"] = fs

    # the lab
    try:
        import pinlab
        prog = pinlab.live_progress(cmdlines=_cmdlines())
        bym = {e.get("match"): e for e in pinlab.EXPERIMENTS}
        exps = []
        for e in pinlab.EXPERIMENTS:
            p = prog.get(e.get("match") or "", {})
            exps.append({
                "name": e["name"], "status": e["status"],
                "what": e.get("what"), "why": e.get("why"),
                "good": e.get("good"), "bad": e.get("bad"),
                "watch": e.get("watch"), "outcome": e.get("outcome"),
                "attribution": e.get("attribution"), "since": e.get("since"),
                "running": bool(p.get("running")),
                "settled": p.get("settled"), "won": p.get("won"),
                "lost": p.get("lost"), "net": _money(p.get("net")),
            })
        d["lab"] = exps
        d["lab_counts"] = dict(pinlab.counts())
    except Exception as e:                                     # noqa: BLE001
        d["lab"] = []
        d["lab_counts"] = {}
        d["lab_error"] = str(e)[:200]
    return d


def _cmdlines():
    """Running python command lines, or [] -- never a crash on the phone path."""
    import subprocess
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return [l for l in (out.stdout or "").splitlines() if l.strip()]
    except Exception:                                          # noqa: BLE001
        return []


PAGE = """<title>Pin Bot Mobile</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
:root{
  --ground:#F4F6F9;--surface:#FFFFFF;--sunk:#E9EDF3;--ink:#161C24;--muted:#5D6A7C;
  --rule:#D8DEE7;--gain:#17795A;--loss:#B4491F;--watch:#8A6410;--blue:#2B5FBF;
  --gain-wash:#E2F2EC;--loss-wash:#FAE8E1;--watch-wash:#F7EEDC;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#0F1420;--surface:#171E2E;--sunk:#1D2536;--ink:#E6EAF2;--muted:#8A94A8;
  --rule:#2A3442;--gain:#31C48D;--loss:#E4572E;--watch:#F0B429;--blue:#4C8DFF;
  --gain-wash:#14302A;--loss-wash:#331F18;--watch-wash:#302716;}}
:root[data-theme="dark"]{
  --ground:#0F1420;--surface:#171E2E;--sunk:#1D2536;--ink:#E6EAF2;--muted:#8A94A8;
  --rule:#2A3442;--gain:#31C48D;--loss:#E4572E;--watch:#F0B429;--blue:#4C8DFF;
  --gain-wash:#14302A;--loss-wash:#331F18;--watch-wash:#302716;}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);
  line-height:1.45;padding:0;-webkit-text-size-adjust:100%}
.app{max-width:720px;margin-inline:auto;padding-inline:14px;
  padding-block:14px calc(76px + env(safe-area-inset-bottom,0px))}
.num,.n{font-family:var(--mono);font-variant-numeric:tabular-nums}
.gain{color:var(--gain)}.loss{color:var(--loss)}.watch{color:var(--watch)}
.muted{color:var(--muted)}
h2{font-size:.68rem;font-weight:600;margin:0 0 10px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.11em}
section{margin-bottom:26px}
p{margin:0 0 .6em;max-width:60ch;font-size:.9rem}p:last-child{margin-bottom:0}

/* status */
.status{border-radius:10px;padding:14px 16px;margin-bottom:18px;
  background:var(--surface);border:1px solid var(--rule);border-left-width:4px}
.status .hl{font-weight:600;font-size:1.05rem;letter-spacing:-.01em}
.status .dt{font-size:.8rem;color:var(--muted);margin-top:4px;white-space:pre-line}

/* tiles */
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:2px;background:var(--rule);
  border:1px solid var(--rule);border-radius:10px;overflow:hidden}
.tile{background:var(--surface);padding:13px 14px;display:flex;flex-direction:column;gap:2px}
.tile .k{font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.tile .v{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:1.2rem;
  font-weight:500;letter-spacing:-.02em}
.tile .s{font-size:.72rem;color:var(--muted)}

/* tables */
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{text-align:left;font-weight:500;font-size:.62rem;text-transform:uppercase;
  letter-spacing:.08em;color:var(--muted);padding:0 10px 7px 0;
  border-bottom:1px solid var(--rule);white-space:nowrap}
td{padding:8px 10px 8px 0;border-bottom:1px solid var(--rule);vertical-align:baseline}
td:last-child,th:last-child{padding-right:0}
td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
tr:last-child td{border-bottom:none}

/* lab cards */
.exp{background:var(--surface);border:1px solid var(--rule);border-radius:10px;
  padding:14px;margin-bottom:10px}
.exp h3{margin:0 0 8px;font-size:.95rem;font-weight:600;letter-spacing:-.01em;
  text-wrap:balance}
.pill{display:inline-block;font-size:.6rem;font-weight:600;letter-spacing:.08em;
  text-transform:uppercase;padding:3px 8px;border-radius:999px;margin-left:6px;
  vertical-align:2px}
.RUNNING{background:var(--gain-wash);color:var(--gain)}
.SHIPPED{background:var(--gain-wash);color:var(--gain)}
.KILLED{background:var(--loss-wash);color:var(--loss)}
.IDEA{background:var(--watch-wash);color:var(--watch)}
.PAUSED{background:var(--sunk);color:var(--muted)}
.exp .row{font-size:.82rem;margin-top:7px}
.exp .lbl{font-size:.6rem;font-weight:600;letter-spacing:.09em;color:var(--muted);
  text-transform:uppercase;display:block;margin-bottom:1px}
.prog{font-family:var(--mono);font-size:.8rem;color:var(--blue);margin-bottom:6px}

ul{margin:0;padding-left:1.05em;display:flex;flex-direction:column;gap:6px}
li{font-size:.86rem;max-width:58ch}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{font-size:.7rem;padding:4px 10px;border-radius:999px;background:var(--sunk);
  color:var(--muted);border:1px solid var(--rule);white-space:nowrap}
.chip.ok{background:var(--gain-wash);color:var(--gain);border-color:transparent}
.chip.bad{background:var(--loss-wash);color:var(--loss);border-color:transparent}
.note{font-size:.76rem;color:var(--muted);max-width:58ch}

/* tab bar */
nav{position:fixed;left:0;right:0;bottom:0;z-index:20;background:var(--surface);
  border-top:1px solid var(--rule);display:flex;
  padding-bottom:env(safe-area-inset-bottom,0px)}
nav button{flex:1;appearance:none;background:none;border:0;cursor:pointer;
  font-family:var(--sans);font-size:.66rem;font-weight:600;letter-spacing:.05em;
  text-transform:uppercase;color:var(--muted);padding:13px 2px;
  border-top:2px solid transparent;margin-top:-1px}
nav button[aria-selected="true"]{color:var(--blue);border-top-color:var(--blue)}
nav button:focus-visible{outline:2px solid var(--blue);outline-offset:-2px}
[hidden]{display:none!important}
@media (prefers-reduced-motion:no-preference){
  .pane{animation:fade .14s ease-out}
  @keyframes fade{from{opacity:.4}to{opacity:1}}}
</style>

<div class="app">
  <div class="status" id="status">
    <div class="hl" id="hl">&hellip;</div>
    <div class="dt" id="dt"></div>
  </div>
  <div id="panes"></div>
  <p class="note" style="margin-top:26px" id="stamp"></p>
</div>
<nav id="tabs" role="tablist"></nav>

<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
  var D = JSON.parse(document.getElementById('data').textContent);
  var esc = function(s){ var d=document.createElement('div'); d.textContent=(s==null?'':String(s)); return d.innerHTML; };
  var money = function(v){ if(v==null) return '-'; return (v<0?'-$':'+$')+Math.abs(v).toFixed(2); };
  var cls = function(v){ return v==null?'':(v>=0?'gain':'loss'); };
  var pct = function(v){ return v==null?'':(v>=0?'+':'')+v.toFixed(2)+'%'; };

  function tiles(){
    var t=D.tiles, out='<div class="tiles">';
    [['today','Today'],['yday','Yesterday'],['run','This run'],['all','All time']].forEach(function(p){
      var s=t[p[0]];
      out += '<div class="tile"><span class="k">'+p[1]+'</span>';
      if(!s){ out += '<span class="v muted">?</span><span class="s">cannot tell when this run started</span></div>'; return; }
      out += '<span class="v '+cls(s.net)+'">'+money(s.net)+'</span>';
      var sub = s.closes ? (s.closes+' quarter-hour'+(s.closes==1?'':'s')+', '+s.won+' won, '+s.lost+' lost') : 'nothing settled yet';
      if(s.pct!=null) sub = pct(s.pct)+' &middot; '+sub;
      out += '<span class="s">'+sub+'</span></div>';
    });
    return out+'</div>';
  }

  function table(cols, rows){
    if(!rows.length) return '<p class="note">Nothing here yet.</p>';
    var h='<div class="scroll"><table><thead><tr>';
    cols.forEach(function(c){ h+='<th'+(c[2]?' style="text-align:right"':'')+'>'+esc(c[0])+'</th>'; });
    h+='</tr></thead><tbody>';
    rows.forEach(function(r){
      h+='<tr>';
      cols.forEach(function(c){ h+='<td'+(c[2]?' class="n"':'')+'>'+c[1](r)+'</td>'; });
      h+='</tr>';
    });
    return h+'</tbody></table></div>';
  }

  var PANES = {
    now: function(){
      var openN = 0; for(var k in D.open){ var v=D.open[k]; openN += (typeof v==='number')?v:(v&&v.n?v.n:1); }
      var h = '<section>'+tiles()+'</section>';
      h += '<section><h2>The account</h2><div class="chips">'
        + '<span class="chip">Bank <b class="num">$'+(D.bank==null?'?':D.bank.toFixed(2))+'</b></span>'
        + '<span class="chip">Put in <b class="num">$'+(D.deposited==null?'?':D.deposited.toFixed(2))+'</b></span>'
        + '<span class="chip">Bet size <b class="num">'+(D.size||'?')+'</b> contracts</span>'
        + '<span class="chip">Open bets <b class="num">'+openN+'</b></span>'
        + (D.run_since?'<span class="chip">Running since '+esc(D.run_since)+'</span>':'')
        + '</div></section>';
      h += '<section><h2>Last settled bets</h2>'+table([
        ['When', function(r){return esc(r.when)}],
        ['Coin', function(r){return esc(r.coin)}],
        ['Side', function(r){return esc(r.want)}],
        ['Result', function(r){return esc(r.result||'')+(r.hedged?' <span class="muted">(insured)</span>':'')}],
        ['$', function(r){return '<span class="'+cls(r.pnl)+'">'+money(r.pnl)+'</span>'}, 1]
      ], D.settled)+'</section>';
      return h;
    },
    market: function(){
      var s=D.sellers, f=D.fills_today;
      var h='<section><h2>How active sellers are</h2>';
      h+='<p><b>'+esc(s.level||'?')+'</b>';
      if(s.recent!=null) h+=' &mdash; someone selling the winning side on <span class="num">'+(100*s.recent).toFixed(0)+'%</span> of the last few looks, against a usual <span class="num">'+(100*(s.median||0)).toFixed(0)+'%</span>.';
      h+='</p></section>';
      if(D.supply.length){
        h+='<section><h2>Is the opportunity going away?</h2><ul>';
        D.supply.forEach(function(l){ h+='<li>'+esc(l)+'</li>'; });
        h+='</ul>';
        if(D.supply_age_d!=null) h+='<p class="note" style="margin-top:10px">Measured up to '+D.supply_age_d.toFixed(1)+' days ago.</p>';
        h+='</section>';
      }
      h+='<section><h2>Today\\u2019s orders</h2><div class="chips">'
        +'<span class="chip">Sent <b class="num">'+f.orders+'</b></span>'
        +'<span class="chip">Filled <b class="num">'+f.fills+'</b></span>'
        +'<span class="chip">Lost the race <b class="num">'+f.zero+'</b></span>'
        +'<span class="chip">Asked <b class="num">'+f.asked+'</b> got <b class="num">'+f.contracts+'</b></span>'
        +'</div></section>';
      h+='<section><h2>The last quarter-hours</h2>'+table([
        ['Close', function(r){return esc(r.close)}],
        ['Sellers', function(r){return r.share==null?'-':(100*r.share).toFixed(0)+'%'}, 1],
        ['What happened', function(r){return esc(r.why)}]
      ], D.closes)+'</section>';
      return h;
    },
    days: function(){
      return '<section><h2>One row per day, newest first</h2>'+table([
        ['Day', function(r){return esc(r.day)}],
        ['$', function(r){return '<span class="'+cls(r.net)+'">'+money(r.net)+'</span>'}, 1],
        ['%', function(r){return r.pct==null?'-':'<span class="'+cls(r.pct)+'">'+pct(r.pct)+'</span>'}, 1],
        ['Won', function(r){return r.won}, 1],
        ['Lost', function(r){return r.lost}, 1]
      ], D.days)+'<p class="note" style="margin-top:12px">The percentage is that day\\u2019s money over the bank at the start of that day.</p></section>';
    },
    losses: function(){
      return '<section><h2>Every losing quarter-hour</h2>'+table([
        ['When', function(r){return esc(r.close)}],
        ['Coins', function(r){return esc(r.coins.join(', '))}],
        ['$', function(r){return '<span class="loss">'+money(r.net)+'</span>'}, 1]
      ], D.losses)+'</section>';
    },
    lab: function(){
      var c=D.lab_counts||{};
      var h='<section><h2>The drawing board</h2><div class="chips" style="margin-bottom:14px">'
        +'<span class="chip ok">'+(c.RUNNING||0)+' running</span>'
        +'<span class="chip ok">'+(c.SHIPPED||0)+' shipped</span>'
        +'<span class="chip bad">'+(c.KILLED||0)+' killed</span>'
        +'<span class="chip">'+(c.IDEA||0)+' ideas</span></div>';
      var order={RUNNING:0,IDEA:1,SHIPPED:2,KILLED:3,PAUSED:4};
      D.lab.slice().sort(function(a,b){return (order[a.status]||9)-(order[b.status]||9)}).forEach(function(e){
        h+='<div class="exp"><h3>'+esc(e.name)+'<span class="pill '+e.status+'">'+e.status+'</span></h3>';
        if(e.settled) h+='<div class="prog">So far: '+e.settled+' settled, '+e.won+' won, '+e.lost+' lost, '
          +money(e.net)+(e.running?'':' (not running now)')+'</div>';
        else if(e.status==='RUNNING') h+='<div class="prog">'+(e.running?'running, nothing settled yet':'NOT RUNNING')+'</div>';
        [['What it does','what'],['Why','why'],['Good looks like','good'],['Bad looks like','bad'],
         ['What to watch','watch'],['What happened','outcome'],['What it was worth','attribution']].forEach(function(p){
          if(e[p[1]]) h+='<div class="row"><span class="lbl">'+p[0]+'</span>'+esc(e[p[1]])+'</div>';
        });
        h+='</div>';
      });
      return h+'</section>';
    },
    system: function(){
      var s=D.sys;
      var h='<section><h2>The machines</h2><div class="chips">'
        +'<span class="chip '+(s.kalshi_ok?'ok':'bad')+'">Kalshi recorder '+(s.kalshi_ok?'alive':'DOWN')+' &middot; '+s.kalshi_chans+' channels</span>'
        +'<span class="chip '+(s.feeds_ok?'ok':'bad')+'">Exchange feeds '+(s.feeds_ok?'alive':'DOWN')+' &middot; '+s.feeds_chans+' channels</span>'
        +'<span class="chip '+(s.disk_gb<6?'bad':'')+'">Disk free '+s.disk_gb+' GB</span>'
        +'<span class="chip '+(s.ram_gb<1.5?'bad':'')+'">Memory free '+s.ram_gb+' GB</span>'
        +'<span class="chip">Paper tests running '+(s.paper_arms||0)+'</span>'
        +'<span class="chip">Positions: '+esc(s.flat||'?')+'</span>'
        +'</div>';
      h+='<p class="note" style="margin-top:14px">The tape stops for good below 5 GB free, so the disk chip turns red at 6. '
        +'Money comes from Kalshi\\u2019s own settlement record, not from our logs.</p></section>';
      h+='<section><h2>What this page is not</h2><p class="note">A snapshot, not the live app. '
        +'It cannot start, pause or stop the bot &mdash; a button that silently does nothing would be worse than no button. '
        +'Use the desktop app or the Telegram bot for that.</p></section>';
      return h;
    }
  };

  var TABS=[['now','Now'],['market','Market'],['days','Days'],['losses','Losses'],['lab','Lab'],['system','System']];
  var nav=document.getElementById('tabs'), panes=document.getElementById('panes');
  TABS.forEach(function(t,i){
    var b=document.createElement('button');
    b.id='tab-'+t[0]; b.type='button'; b.textContent=t[1];
    b.setAttribute('role','tab'); b.setAttribute('aria-selected', i===0?'true':'false');
    b.onclick=function(){ show(t[0]); };
    nav.appendChild(b);
    var p=document.createElement('div');
    p.className='pane'; p.id='pane-'+t[0]; p.hidden = i!==0;
    panes.appendChild(p);
  });
  function show(key){
    TABS.forEach(function(t){
      var sel = t[0]===key;
      document.getElementById('tab-'+t[0]).setAttribute('aria-selected', sel?'true':'false');
      var p=document.getElementById('pane-'+t[0]);
      p.hidden=!sel;
      if(sel && !p.dataset.done){ p.innerHTML=PANES[t[0]](); p.dataset.done='1'; }
    });
    try{ localStorage.setItem('pinmobile.tab', key); }catch(e){}
    window.scrollTo(0,0);
  }
  var hl=document.getElementById('hl'), dt=document.getElementById('dt'), st=document.getElementById('status');
  hl.textContent=D.headline; dt.textContent=D.detail;
  var col = D.state==='TRADING' ? 'var(--gain)' : (D.state==='DOWN'||D.state==='BRAKE' ? 'var(--loss)' : 'var(--watch)');
  st.style.borderLeftColor=col; hl.style.color=col;
  document.getElementById('stamp').textContent='Snapshot taken '+D.built_et+' ET. This page does not update on its own.';
  var start='now';
  try{ var s=localStorage.getItem('pinmobile.tab'); if(s && PANES[s]) start=s; }catch(e){}
  show(start);
})();
</script>
"""


def render(d):
    return PAGE.replace("__DATA__", json.dumps(d).replace("</", "<\\/"))


def write(d=None, out=None, results=None):
    d = collect(results=results) if d is None else d
    out = out or OUT
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render(d))
    return out, d


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinmobile selftest: FAILED -- " + msg)

    import tempfile
    import pindesk
    import pinledger
    td = tempfile.mkdtemp()
    _sv = pinledger.LEDGER
    pinledger.LEDGER = os.path.join(td, "ledger.json")
    log = os.path.join(td, "pinrun-live-20260918T000000Z.jsonl")
    recs = [
        {"kind": "start", "mode": "live", "t": "2026-09-18T00:00:00Z"},
        {"kind": "autosize", "new": 77, "why": "bank $622.57",
         "t": "2026-09-18T00:00:01Z"},
        {"kind": "order", "ticker": "KXBTC15M-26SEP180100-00", "filled": 77,
         "asked": 77, "price": 0.96, "status": "executed",
         "t": "2026-09-18T00:59:00Z"},
    ]
    with open(log, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    # MONEY COMES FROM KALSHI, NOT FROM THE LOG. `refresh()` replaces its
    # settlements wholesale from the ledger file, so a fixture that writes
    # `settled` records into the log measures nothing at all -- which is the
    # whole point of that change, and a test that did not know it would have
    # been testing a code path the real app never takes.
    def _s(tk, res, n, cost, when, fee="0.05"):
        won_yes = res == "yes"
        return {"ticker": tk, "market_result": res,
                "yes_count_fp": ("%.2f" % n) if won_yes else "0.00",
                "no_count_fp": "0.00" if won_yes else ("%.2f" % n),
                "yes_total_cost_dollars": ("%.2f" % cost) if won_yes else "0.00",
                "no_total_cost_dollars": "0.00" if won_yes else ("%.2f" % cost),
                "fee_cost": fee, "settled_time": when}
    # KEYED BY (ticker, settled_time), not a list -- `load_cache` returns the
    # dict and `_load_kalshi` walks `.values()`, so a list fixture crashes.
    rows = {}
    for r in (
            # bought 77 YES at 96c and YES won: pays $77, cost $73.92
            _s("KXBTC15M-26SEP180100-00", "yes", 77, 73.92,
               "2026-09-18T01:00:20Z"),
            # bought 77 NO at 95c and YES won: pays nothing, cost $73.15
            {"ticker": "KXETH15M-26SEP180115-15", "market_result": "yes",
             "yes_count_fp": "0.00", "no_count_fp": "77.00",
             "yes_total_cost_dollars": "0.00",
             "no_total_cost_dollars": "73.15", "fee_cost": "0.05",
             "settled_time": "2026-09-18T01:15:20Z"}):
        rows[r["ticker"] + "|" + r["settled_time"]] = r
    with open(pinledger.LEDGER, "w", encoding="utf-8") as fh:
        json.dump({"settlements": rows}, fh)
    # ISOLATED FROM THE REAL ACCOUNT ABOVE: `Ledger.refresh()` reads
    # `pinledger.LEDGER`, an ABSOLUTE default path, so `results=td` alone
    # would hand this test a temp log plus every real settlement on the
    # machine.
    try:
        L = pindesk.Ledger(results=td)
        L.refresh()
        d = collect(ledger=L)
    finally:
        pinledger.LEDGER = _sv

    # THE POINT OF THIS FILE: the phone shows pindesk's numbers, not its own.
    want = pindesk.Ledger.summary(L.settled)
    ck(abs(d["tiles"]["all"]["net"] - round(want["net"], 2)) < 1e-9,
       "the all-time figure is pindesk's own summary, not a total this file "
       "added up again -- the desktop app and the phone bot once disagreed "
       "about the same day for three days running")
    ck(d["tiles"]["all"]["won"] == want["won"]
       and d["tiles"]["all"]["lost"] == want["lost"],
       "...and so are won and lost")
    ck(d["tiles"]["run"] is not None and d["tiles"]["run"]["closes"] == 2,
       "THIS RUN counts what settled since the start record, which is the bug "
       "that pinned the desktop tile to $0.00")
    ck(len(d["losses"]) == 1 and d["losses"][0]["net"] < 0,
       "the losing quarter-hour is listed, and only the losing one")
    ck(d["settled"] and d["settled"][0]["when"],
       "settled bets carry an EASTERN time string, never a raw timestamp")
    ck("T" not in (d["settled"][0]["when"] or ""),
       "...not an ISO stamp, which is what the operator asked never to be "
       "handed")

    page = render(d)
    ck("__DATA__" not in page, "the data placeholder is actually replaced")
    ck(page.count("<title>") == 1 and "Pin Bot Mobile" in page,
       "the page names itself once")
    for tab in ("now", "market", "days", "losses", "lab", "system"):
        ck("'" + tab + "'" in page, "the %s tab exists" % tab)
    ck("</script>" not in json.dumps(d).replace("</", "<\\/"),
       "NULL: a '</script>' inside the data cannot close the script tag early "
       "-- that is how an embedded-JSON page silently renders half a document")
    ck("prefers-color-scheme" in page and 'data-theme="dark"' in page,
       "both themes are defined, including the un-stamped system default")
    ck("--ground" in page.split("@media")[0],
       "every colour token is declared on bare :root before any media block, "
       "so no colour exists only inside one theme")
    ck("start, pause or stop" in page,
       "the page says plainly that it cannot control the bot, rather than "
       "showing a button that does nothing")
    out, _ = write(d=d, out=os.path.join(td, "m.html"))
    ck(os.path.getsize(out) > 4000, "and it writes a real file")
    print("pinmobile selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--results", default=RESULTS)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    out, d = write(out=a.out, results=a.results)
    print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))
    print("  %s -- bank $%s, %d settled on file"
          % (d["headline"], d["bank"], len(d["settled"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
