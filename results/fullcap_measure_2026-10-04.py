"""Per-market full-bet cap counterfactual on OUR LIVE FILLS + Kalshi per-market money.
Never the tape, never pinsim.

PRE-STATED CHOICE RULE (written before any number was computed, 2026-10-04):
  pick 1.5x only if its net beats 1.0x by more than $20 over the whole window
  AND it does not let through any loser bigger than 10% of the account at the time;
  otherwise 1.0x.

Definitions:
  full bet in force at an order = SIZE (latest start/autosize record before it)
      x max(band_mult(ask_seen) from the run's start record band_mults,
            late_mult if tau_at_send <= late_tau else 1.0)
      -- the same target v-topup completes a position to (doubt mult is 1.0 live).
  bet side = side of the market's first filled entry order; entry orders on the other
      side (re-buys into a hedge) are exempt, as the gate exempts them; hedges are
      separate records and never counted.
  cap X: walk the bet-side fills in time order; kept_i = min(filled_i, max(0, X*full_i - kept_so_far)).
  money: Kalshi per market = revenue/100 + min(yes,no) - yes_cost - no_cost - fee.
    winner (bet side == result): given up = sum removed*(1 - exec - fee/contract)
        - hedge net loss x removed/actual (insurance sized in proportion; ASSUMPTION)
    loser: capped net = actual net x kept/actual (ASSUMPTION: insurance in proportion);
        saved = actual - capped.
"""
import json, glob, re, sys, collections
from datetime import datetime, timezone, timedelta

T0 = '2026-09-09T00:00:00Z'
ONEFULL = '2026-09-27T08:11:15Z'
REVERT = '2026-10-04T03:22:52Z'
CAPS = (1.0, 1.25, 1.5, 2.0)
SER = re.compile(r'^KX(BTC|ETH|SOL|XRP|DOGE|BNB|HYPE|NEAR|ZEC|ADA|BCH|TON)15M-')

led = json.load(open(r'C:\kals-repo\results\kalshi_ledger.json'))['settlements']
kal = {}
_dups = collections.Counter(s['ticker'] for s in led.values())
print('ledger tickers appearing more than once:', [t for t, c in _dups.items() if c > 1][:10])
for _key, s in led.items():
    tk = s['ticker']
    y, n = float(s['yes_count_fp']), float(s['no_count_fp'])
    kal[tk] = dict(result=s['market_result'], y=y, n=n,
                   ycost=float(s['yes_total_cost_dollars']), ncost=float(s['no_total_cost_dollars']),
                   fee=float(s['fee_cost']),
                   money=s['revenue'] / 100 + min(y, n) - float(s['yes_total_cost_dollars'])
                   - float(s['no_total_cost_dollars']) - float(s['fee_cost']))

fills = collections.defaultdict(list)
bank_t = []           # (t, bank)
files = sorted(glob.glob(r'C:\kals-repo\results\pinrun-live-*.jsonl'))
for f in files:
    stamp = f.split('-live-')[1][:16]
    size = None; lm, lt, bands = 1.0, 0, []
    for l in open(f, encoding='utf-8'):
        try:
            r = json.loads(l)
        except Exception:
            continue
        k = r.get('kind')
        if k == 'start':
            size = float(r.get('size') or 20)
            lm = float(r.get('late_mult') or 1.0); lt = int(r.get('late_tau') or 0)
            bands = r.get('band_mults') or []
            if r.get('mode') != 'live':
                print('NOTE non-live start in', f)
        elif k == 'autosize':
            size = float(r['new'])
            m = re.search(r'bank \$([0-9.]+)', r.get('why') or '')
            if m:
                bank_t.append((r['t'], float(m.group(1))))
        elif k == 'order':
            if r.get('t', '') < T0:
                continue
            fl = float(r.get('filled') or 0)
            if fl <= 0:
                continue
            tk = r['ticker']
            if not SER.match(tk):
                continue
            ask = float(r.get('ask_seen') or r.get('exec_price') or 0)
            tau = r.get('tau_at_send')
            bm = 1.0
            for lo, hi, mu in bands:
                if lo - 1e-9 <= ask < hi - 1e-9 or (lo - 1e-9 <= ask <= hi + 1e-9):
                    bm = max(bm, float(mu))
            mult = max(bm, lm if (tau is not None and lt and tau <= lt) else 1.0)
            fee = r.get('fee')
            fills[tk].append(dict(t=r['t'], tms=r.get('t_ms_send') or 0, want=(r.get('want') or ('yes' if (r.get('body') or {}).get('side') in ('bid', 'yes') else 'no')), leg=r.get('leg'),
                                  tau=tau, ask=ask, px=float(r.get('exec_price') or ask), n=fl,
                                  fee=float(fee) if fee is not None else 0.0, size=size, mult=mult,
                                  file=stamp))
bank_t.sort()

_settle_money = sorted((r['settled_time'], kal[r['ticker']]['money']) for r in led.values())

def bank_at(t):
    # before the first autosize record: that record's bank minus every main-account
    # settlement between t and it (no deposit fell in 09-09..09-13; pinxfer cache)
    if bank_t and t < bank_t[0][0]:
        return round(bank_t[0][1] - sum(m for st, m in _settle_money if t <= st <= bank_t[0][0]), 2)
    b = None
    for tt, bb in bank_t:
        if tt <= t:
            b = bb
        else:
            break
    return b if b is not None else (bank_t[0][1] if bank_t else None)

def window(t):
    if t < ONEFULL:
        return 'A 09-09..09-27 08:10Z (multi-bet builds)'
    if t < REVERT:
        return 'B 09-27 08:11Z..10-04 03:22Z (one-full-bet live)'
    return 'C 10-04 03:22Z.. (09-25 build again)'

mk = []
missing_k = []
mismatch = []
for tk, fl in fills.items():
    fl.sort(key=lambda x: (x['t'], x['tms']))
    if tk not in kal:
        missing_k.append(tk)
        continue
    k = kal[tk]
    side = fl[0]['want']
    bet = [x for x in fl if x['want'] == side]
    other = [x for x in fl if x['want'] != side]
    nlog = sum(x['n'] for x in bet)
    nk = k['y'] if side == 'yes' else k['n']
    if abs(nlog - nk) > 0.5:
        mismatch.append((tk, side, round(nlog, 2), nk))
    won = (k['result'] == side)
    # hedge / other-side net: Kalshi other-side holdings
    oth_n = k['n'] if side == 'yes' else k['y']
    oth_cost = k['ncost'] if side == 'yes' else k['ycost']
    oth_net = (oth_n if not won else 0.0) - oth_cost    # pays 1 if other side won
    full0 = bet[0]['size'] * bet[0]['mult']
    mk.append(dict(tk=tk, side=side, won=won, money=k['money'], nlog=nlog, nk=nk, bet=bet,
                   oth_n=oth_n, oth_net=oth_net, t=bet[0]['t'], win=window(bet[0]['t']),
                   bank=bank_at(bet[0]['t']), size=bet[0]['size'],
                   xbets=nlog / bet[0]['size']))

def capped(m, X):
    held = 0.0; rem = []
    for x in m['bet']:
        room = max(0.0, X * x['size'] * x['mult'] - held)
        keep = min(x['n'], room)
        held += keep
        if x['n'] - keep > 1e-9:
            rem.append((x, x['n'] - keep))
    return held, rem

print(__doc__.split('Definitions:')[0])
print('markets with live bet fills, 15-min coins, since 09-09:', len(mk),
      '| not in Kalshi ledger:', len(missing_k), '| log vs Kalshi count mismatch >0.5:', len(mismatch))
for t in mismatch[:40]:
    print('   mismatch', t)
print('autosize bank records:', len(bank_t), 'first', bank_t[0] if bank_t else None)
dist = collections.Counter()
for m in mk:
    dist[(m['win'][0], round(m['xbets'] * 4) / 4)] += 1
print('contracts held / SIZE at entry (quarter steps), by window:', sorted(dist.items()))

out = {}
for X in CAPS:
    rows = collections.defaultdict(lambda: dict(touched=0, w_n=0, w_up=0.0, l_n=0, l_saved=0.0, losers=[]))
    for m in mk:
        kept, rem = capped(m, X)
        if not rem:
            continue
        for wname in (m['win'], 'ALL'):
            R = rows[wname]
            R['touched'] += 1
            if m['won']:
                up = sum(n * (1.0 - x['px'] - x['fee']) for x, n in rem)
                frac = (m['nlog'] - kept) / m['nlog'] if m['nlog'] else 0
                up += frac * m['oth_net']          # hedge loss on removed share is saved (oth_net <= 0)
                R['w_n'] += 1; R['w_up'] += up
            else:
                after = m['money'] * kept / m['nlog']
                R['l_n'] += 1; R['l_saved'] += (after - m['money'])
                if wname == 'ALL':
                    R['losers'].append((m['tk'], m['t'], round(m['money'], 2), round(after, 2),
                                        round(m['nlog'], 1), round(kept, 1), m['bank'],
                                        round(-after / m['bank'] * 100, 1) if m['bank'] else None))
    out[X] = rows

for X in CAPS:
    print('\n=== cap %.2fx full bet ===' % X)
    for wname in sorted(out[X]):
        R = out[X][wname]
        print('  %-48s touched %3d | winners %3d give up $%8.2f | losers %2d save $%8.2f | net $%+8.2f'
              % (wname, R['touched'], R['w_n'], R['w_up'], R['l_n'], R['l_saved'], R['l_saved'] - R['w_up']))
    for lo in sorted(out[X]['ALL']['losers'], key=lambda z: z[1]):
        print('     loser', lo)

# Losers NOT touched by any cap but big (for the 10% rule)
print('\nAll losers (Kalshi money < 0) with held/SIZE, bank, loss % bank, and the loss at each cap:')
for m in sorted(mk, key=lambda z: z['t']):
    if m['money'] < 0 and not m['won']:
        caps = []
        for X in CAPS:
            kept, rem = capped(m, X)
            caps.append(round(m['money'] * kept / m['nlog'], 2))
        print('  %s %s money %8.2f held %6.1f size %5.1f (%.2fx) bank %s pct %.1f%% | at caps %s'
              % (m['tk'], m['t'], m['money'], m['nlog'], m['size'], m['xbets'], m['bank'],
                 (-m['money'] / m['bank'] * 100) if m['bank'] else float('nan'), caps))
json.dump({str(X): {w: {k: v for k, v in R.items()} for w, R in out[X].items()} for X in CAPS},
          open(r'C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\fc_measure.json', 'w'), indent=1)

print()
print('Touched markets in detail (cap: ticker, window, won, Kalshi $, held, size, removed contracts@price legs):')
for X in (1.0, 1.5):
    for m in sorted(mk, key=lambda z: z['t']):
        kept, rem = capped(m, X)
        if rem:
            print('  %.2fx %s %s won=%s money %.2f held %.1f size %.0f kept %.1f | removed %s | legs %s' % (
                X, m['tk'], m['t'], m['won'], m['money'], m['nlog'], m['size'], kept,
                [(round(n, 1), x['px'], x['leg'], x['tau']) for x, n in rem],
                [(round(x['n'], 1), x['px'], x['leg'], x['tau'], round(x['size'] * x['mult'], 1)) for x in m['bet']]))

print()
tot = collections.defaultdict(lambda: [0, 0.0, 0.0])
for m in mk:
    for w in (m['win'], 'ALL'):
        tot[w][0] += 1; tot[w][1] += m['money']
        tot[w][2] += sum(x['n'] * x['px'] for x in m['bet'])
for w in sorted(tot):
    print('context %-48s markets %4d  Kalshi money $%+9.2f  bet-side spend $%10.2f' % (w, tot[w][0], tot[w][1], tot[w][2]))
