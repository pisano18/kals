"""Prepend the v-oddsmult entry to results/VERSIONS.md and insert the LS38 row in results/IDEA_LEDGER.md (server repo).
Idempotent: refuses if either already mentions v-oddsmult / LS38. Preserves each file's line endings."""
import io, sys

VERS = r'C:\kals-repo\results\VERSIONS.md'
LEDG = r'C:\kals-repo\results\IDEA_LEDGER.md'

ENTRY = ('# v-oddsmult -- INSTALLED 2026-11-02 by results/pin_oddsmult.ps1 (operator 11-02: "Go. Push it yourself without '
         'me needing to do anything."); LIVE at its restart (C:\\kals-live-0925r, pinrun code_sha ca156bf45704 = 0925q '
         '0f49ba3ae221 + results/patch_oddsmult.py; ordercli/pintake unchanged). NEW FLAGS, both default off: '
         '--hedge-odds-mult 1.25 --hedge-odds-min-tau 11. When the hedge fires on the BELIEF line (pin\'s odds in our side '
         'under --hedge-belief 0.40; never the A52 jump trigger, never a K3 stale-index alarm) with at least 11 s left, '
         'pin ALSO buys (M - 1) x the position of the hedge side as a SECOND order sent right after the covering hedge, '
         'at the same limit (ask + --hedge-slip), sized from the same ladder less what the covering hedge took, once per '
         'position. The covering hedge is byte-for-byte the order it was (its size, limit, depth, "done" bookkeeping and '
         'attempt counting are untouched; asserted by source in the self-test). pintake sees an order larger than the '
         'held position is not a covering hedge and judges it with every dollar rail; a refusal costs the extra and '
         'nothing else (hedge_extra_refused). An extra whose outcome is unknown is looked up on Kalshi by its own id '
         '(v-safety2) with nothing counted covered, so the resolver books only what really filled and re-opens no hedge. '
         'Records: kind hedge_extra (side, price, n, asked, extra_of, mult, min_tau, base_n, orig_n, ask, ask_size, '
         'limit_sent, ladder_n, swept, entry, tau, belief, trigger, order_id, status, status_code, unknown, live, '
         'conn fields), hedge_extra_skipped (no depth past the covering hedge), hedge_extra_refused; the start record '
         'carries hedge_odds_mult / hedge_odds_min_tau; the leg settles as its own open_pos entry "hedge-extra-<parent>-'
         '<order_id>" (every reader tests startswith("hedge-")). EVIDENCE (11-02 deep dive, scratchpad extrahedge.py / '
         'hedgeprop.py / cross.py): the odds line is the one place pin beats the market -- the hedge side bought there '
         'at ~65c won 27 of 37 times 09-23..11-01 because pin\'s index runs ~1 s ahead of the book; at 299-contract bets '
         'the extra 1x at 2x is worth +$350..+$550 per 40 days over 1x, worst single market about -$440; by seconds left '
         'the extra lost only inside 10 s (8 fires, -$136), hence the 11 s floor. The live run already hedges the WHOLE '
         'position at the line (--no-hedge-prop), so "all at 0.40" was never a change. 11-02 ZEC 7:30 ET: No 297 @94.5c '
         'lost $281.63, the 1x hedge Yes 297 @14c made $253.07 (net -$28.56); at 2x the extra 297 Yes at 23-37c = +$180..'
         '+$225 more. 11-02 NEAR 6:30 ET (-$68 net): the hedge fired on the JUMP trigger at belief 0.64, so this rule '
         'does not touch it. Entry-side rules checked the same morning and DEAD: a longer spike lookback (5 s -$340, '
         '10 s -$934), random-walk distance skips (every bucket net positive), strike crossings, hour of day, weekday; '
         '"never near the strike in the last 60 s" is a zero-profit zone (-$64 after hedges), a watch item. STAGING: '
         '1.25 now (the operator\'s tiny-test rule), 1.5 then 2.0 after the fires pay. Monitor: research/pinrules_watch.py '
         'rule C scores every hedge_extra on its own money (+ made / - lost), alerts at $10+, and the 11-03 / 11-04 / '
         '11-08 reports carry it. Self-test: pure odds_extra() (floor, trigger, line, garbage, ships off), driven paper '
         'worlds (collapse at tau 26 -> 5 hedged + 5 extra; inside the floor / flag off / floor above the collapse -> no '
         'extra; the jump trigger -> no extra; the belief line through a capped 9 sd jump -> extra), the live order path '
         '(three orders: entry, covering hedge, extra; flag off -> one NO order as before), and by source. REVERT: delete '
         'the flag line pair from both launchers and $code/$codeSha back to C:\\kals-live-0925q / 0f49ba3ae221 (backups '
         '*.before-oddsmult-*), rerun restart_bot while flat.')

ROW = ('| LS38 | Pin bot: hedge SIZE at the odds line (11-02 deep dive, after the NEAR 6:30 and ZEC 7:30 ET losses; operator: '
       '"Go. Push it yourself without me needing to do anything.") | pin bot (main account) | 11-02 LIVE as v-oddsmult '
       '(results/pin_oddsmult.ps1, C:\\kals-live-0925r ca156bf45704): --hedge-odds-mult 1.25 --hedge-odds-min-tau 11 -- when '
       'the 0.40 belief line fires with 11+ s left pin also buys (M - 1) x the position of the hedge side as a second order '
       'right after the covering hedge (never on the jump trigger). The one place pin beats the market: the hedge side '
       'bought at the odds line (~65c) won 27 of 37 (09-23..11-01) because pin\'s index runs ~1 s ahead of the book. At '
       '299-contract bets the extra at 2x = +$350..+$550 per 40 days over 1x; worst market about -$440; inside 10 s the '
       'extra lost (-$136 on 8). ZEC 11-02 7:30 ET at 2x: -$28.56 -> about +$170. CORRECTION: the live run already hedges '
       'the whole position at the line (--no-hedge-prop; 25 of 38 odds-line hedges bought all at once), so the deep dive\'s '
       '"stage 1: all at 0.40" was a no-op and is withdrawn. DEAD the same morning: longer spike lookback (5 s -$340, 10 s '
       '-$934; fresh conviction is pin\'s BEST class, 0-1 s +$297 at 3.2c/contract), random-walk distance skips (every '
       'bucket net positive; margin 0.3c -> 5c/contract with distance = a sizing idea, not a skip), strike crossings, hour '
       'of day (all 4-h blocks positive), weekday (Mon -$138 = 7 losses in 6 Mondays), both_sides re-buy (1 refusal since '
       'Sep). Watch item: "never near the strike in the last 60 s" (424 mkts, 12 losses, -$241 main, -$64 after hedges). '
       'STAGE: 1.25 -> 1.5 -> 2.0 as the fires pay; read with the 11-10 trial | ~+$3/day at 1.25x, ~+$9..+$14/day at 2x '
       '(replay at today\'s size) | 37 fires in 40 days, 10 of them lose the extra (~-$190 each at 299); the 11 s floor is '
       'picked by looking at 8 fires | scratchpad extrahedge.py, hedgeprop.py, cross.py, hug.py, convage.py; '
       'results/patch_oddsmult.py; research/pinrules_watch.py rule C |')


def rw(path, fn):
    raw = open(path, 'rb').read()
    crlf = b'\r\n' in raw
    txt = raw.decode('utf-8')
    nl = '\r\n' if crlf else '\n'
    out = fn(txt, nl)
    open(path, 'wb').write(out.encode('utf-8'))


def do_versions(txt, nl):
    assert 'v-oddsmult' not in txt, 'VERSIONS.md already has v-oddsmult'
    bom = ''
    if txt.startswith('\ufeff'):
        bom, txt = '\ufeff', txt[1:]
    return bom + ENTRY + nl + txt      # entries are one line each, newest first, no blank line between


def do_ledger(txt, nl):
    assert '| LS38 |' not in txt, 'IDEA_LEDGER.md already has LS38'
    key = nl + '| LS37 |'
    assert txt.count(key) == 1, ('LS37 row not found once', txt.count(key))
    return txt.replace(key, nl + ROW + key)


rw(VERS, do_versions)
rw(LEDG, do_ledger)
print('docs updated: VERSIONS.md (entry at the top), IDEA_LEDGER.md (LS38 above LS37)')
