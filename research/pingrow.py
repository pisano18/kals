#!/usr/bin/env python3
"""pingrow.py -- every day from funding to three days past the 250 cap.

Actuals from our own live logs; the projection from the CURRENT version's
measured rate only, because the version changed almost daily and the early
days do not describe what is running now.

    python research/pingrow.py --selftest
    python research/pingrow.py
"""
import json, glob, collections, datetime, sys


def project(bank, cpc, eff, cps=58, brake=5.88, cap=250, days=60):
    """Day-by-day (bank, size, contracts, earned). Size is bank/brake capped
    at `cap`; the per-contract rate is scaled toward `eff` as size approaches
    the cap, because a bigger order pays a worse average price."""
    out = []
    b = bank
    for _ in range(days):
        size = min(cap, b / brake)
        scale = 1.0 - (1.0 - eff) * (size / cap)
        c = cps * size
        earn = c * (cpc / 100.0) * scale
        out.append((b, size, c, earn))
        b += earn
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    r = project(1000.0, 2.4, 1.0, cps=58, brake=5.88, cap=250)
    ck(abs(r[0][1] - 1000.0 / 5.88) < 1e-9, "size is bank / 5.88 before the cap")
    ck(all(x[1] <= 250 + 1e-9 for x in r), "size NEVER exceeds the 250 cap")
    big = project(100000.0, 2.4, 1.0)
    ck(abs(big[0][1] - 250.0) < 1e-9, "a huge bank is capped at 250, not scaled")
    ck(abs(big[0][3] - big[1][3]) < 1e-9,
       "and past the cap the daily amount is FLAT -- growth stops being "
       "exponential, which is the whole point of the table")
    # the null: a zero edge earns nothing and the bank never moves
    z = project(1000.0, 0.0, 1.0)
    ck(all(abs(x[3]) < 1e-12 for x in z) and abs(z[-1][0] - 1000.0) < 1e-9,
       "NULL: at zero cents per contract nothing is earned and the bank is flat")
    # the haircut only bites as size approaches the cap
    a = project(250 * 5.88, 2.4, 0.9)[0]
    b = project(10 * 5.88, 2.4, 0.9)[0]
    ck(a[3] / a[2] < b[3] / b[2],
       "the depth haircut lowers cents per contract at the cap (%.3fc) vs a "
       "small size (%.3fc)" % (100 * a[3] / a[2], 100 * b[3] / b[2]))
    ck(project(1000.0, 2.4, 1.0)[0][3] > project(1000.0, 2.4, 0.85)[0][3],
       "a worse depth efficiency always earns less")
    print("pingrow selftest:", "OK" if ok else "FAILED")
    return ok


if "--selftest" in sys.argv:
    sys.exit(0 if selftest() else 1)
if not selftest():
    sys.exit(1)

def et(t): return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S") - datetime.timedelta(hours=4)

net = collections.defaultdict(float); con = collections.Counter()
fills = collections.Counter(); sizes = collections.defaultdict(list)
losses = collections.Counter(); banks = []
for p in sorted(glob.glob('results/pinrun-live-*.jsonl')):
    sig = {}
    for line in open(p, encoding='utf-8'):
        try: d = json.loads(line)
        except: continue
        t = d.get('t')
        if not t: continue
        k = d.get('kind'); day = et(t).strftime('%Y-%m-%d')
        if k == 'signal': sig.setdefault(d['ticker'], d.get('want'))
        if k == 'settled':
            net[day] += d.get('pnl_c', 0) / 100.0
            if sig.get(d['ticker']) == d.get('want') and d.get('result') != d.get('want'):
                losses[day] += 1
        if k == 'order' and (d.get('filled') or 0) > 0:
            con[day] += d['filled']; fills[day] += 1
        if k == 'autosize' and (d.get('why') or '').startswith('bank $'):
            sizes[day].append(d.get('new')); banks.append((t, float(d['why'].split('$')[1])))
banks.sort()

VER = {
 '2026-09-08': 'v0-v14  first live day, size 1->20, EV gate, tau 30',
 '2026-09-09': 'v14     size 20 fixed; first big loss (NEAR, -$52.60)',
 '2026-09-10': 'v15-v17 dump guard (A10) went live 09-11',
 '2026-09-11': 'v17     15c dump guard live 08:29 ET',
 '2026-09-12': 'v18-v22 AUTO-SIZING BEGINS; hedge 0.80',
 '2026-09-13': 'v-pick  best-market-first (A24) 20:35 ET',
 '2026-09-14': 'v-ladder 02:1 ET | v-spend | v-brake20 | v-nofloor 10:53 ET | v-jump 21:39 ET',
}
days = sorted(set(list(net) + list(con)))
# bank at the START of each day: measured where we have a read, else inferred
first_read = {}
for t, b in banks:
    first_read.setdefault(et(t).strftime('%Y-%m-%d'), b)
START = {}
anchor_day = '2026-09-12'; START[anchor_day] = 193.76
for d in reversed([x for x in days if x < anchor_day]):
    nxt = days[days.index(d) + 1]
    START[d] = START[nxt] - net[d]
for d in [x for x in days if x > anchor_day]:
    prv = days[days.index(d) - 1]
    START[d] = first_read.get(d, START[prv] + net[prv])

print("=" * 108)
print("PART 1 -- WHAT ACTUALLY HAPPENED".center(108))
print("=" * 108)
print(f"\n  {'day':12} {'bank start':>10} {'size':>5} {'max/close':>9} {'fills':>6} {'contracts':>9} "
      f"{'c/contract':>10} {'net$':>9} {'loss':>4} {'return':>7}")
print("  " + "-" * 104)
cum = 0.0
for d in days:
    ss = sizes.get(d) or []
    med = sorted(ss)[len(ss) // 2] if ss else 20
    b = START[d]; n = net[d]; cum += n
    print(f"  {d:12} {b:10.2f} {med:5.0f} {2*med:9.0f} {fills[d]:6} {con[d]:9.0f} "
          f"{100*n/max(1,con[d]):+10.2f} {n:+9.2f} {losses[d]:4} {100*n/b:+6.1f}%")
print("  " + "-" * 104)
print(f"  {'TOTALS':12} {'':10} {'':5} {'':9} {sum(fills.values()):6} {sum(con.values()):9.0f} "
      f"{100*cum/sum(con.values()):+10.2f} {cum:+9.2f} {sum(losses.values()):4}")
print(f"\n  funding: started $38.83 on 09-08, deposited $150 (only $113.04 reached the crypto")
print(f"  shard -- the rest landed where it could not trade). No deposit since; 09-13 and")
print(f"  09-14 bank changes match P&L to within 4 cents, so all growth after that is traded.")
print(f"  Bank now ${banks[-1][1]:.2f}. Grew from $151.87 of usable capital to ${banks[-1][1]:.2f} in 7 days.")

# ---------------- projection ----------------
CAP, BRAKE = 250, 5.88
CPS = 58            # contracts per unit of size per day -- current version, measured
SCEN = (("LOW",      1.50, 0.85),
        ("EXPECTED", 2.40, 0.90),
        ("HIGH",     3.50, 0.95))
print("\n" + "=" * 108)
print("PART 2 -- PROJECTION".center(108))
print("=" * 108)
print(f"""
  Built from the CURRENT version only (since the depth floor came off, 10:53 ET on 09-14):
    contracts per unit of size per day   58   measured over 12.2 h / 21 closes
    cents per contract                 2.74c  measured in that window -- which had NO losses
  So the projection does NOT use 2.74c. The three cases use:
    LOW 1.5c   EXPECTED 2.4c (the all-time live average, losses included)   HIGH 3.5c
  and a depth haircut as size grows, from research/pincap.py: a 250-lot fills 86% of the
  time and pays 0.21c more than a 50-lot, so the per-contract rate is scaled toward 0.85-0.95
  at the cap. Size = bank / 5.88, hard cap {CAP} contracts (bank ${CAP*BRAKE:,.0f}).
""")
start_bank = banks[-1][1]
d0 = datetime.date(2026, 9, 15)
for name, cpc, eff in SCEN:
    b = start_bank; cap_day = None; rows = []
    for i in range(0, 60):
        size = min(CAP, b / BRAKE)
        scale = 1.0 - (1.0 - eff) * (size / CAP)
        c = CPS * size
        earn = c * (cpc / 100.0) * scale
        rows.append((d0 + datetime.timedelta(days=i), b, size, 2 * size, c, earn, 100 * earn / b))
        if size >= CAP - 0.5 and cap_day is None:
            cap_day = i
        if cap_day is not None and i >= cap_day + 3:
            break
        b += earn
    print(f"  {name} -- {cpc:.1f}c per contract, depth efficiency {eff:.2f} at the cap")
    print(f"  {'date':12} {'bank start':>10} {'size':>5} {'max/close':>9} {'contracts':>9} {'net$':>9} {'return':>7}")
    print("  " + "-" * 70)
    for dt_, b_, s_, m_, c_, e_, r_ in rows:
        mark = ""
        if cap_day is not None and rows.index((dt_, b_, s_, m_, c_, e_, r_)) == cap_day:
            mark = "  <== 250 CAP REACHED"
        print(f"  {dt_.strftime('%a %d %b'):12} {b_:10.2f} {s_:5.0f} {m_:9.0f} {c_:9.0f} {e_:+9.2f} {r_:+6.1f}%{mark}")
    print(f"  -> cap reached day {cap_day} ({(d0+datetime.timedelta(days=cap_day)).strftime('%a %d %b')}), "
          f"steady state ${rows[-1][5]:,.0f}/day, bank ${rows[-1][1]:,.0f} three days later\n")
