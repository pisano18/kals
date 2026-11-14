"""Apply v-0925x (build 0925x) to a COPY of the live pin build (C:\\kals-live-0925w: research\\pinrun.py code_sha
05a01fbb5ed2; ordercli.py 467782077a23 is patched by results\\patch_0925x_ordercli.py; pintake.py b3c7bb48abb5 is NOT
touched). Patches pinrun.py in place, CRLF preserved; every anchor must occur exactly once; refuses an already-patched
tree, a tree that is not 0925w, and any result whose sha is not EXPECTED_PINRUN (nothing is written then). Every
refusal is an explicit exit, not an assert, so `python -O` cannot skip one.
usage: python patch_0925x.py <build_dir>      (build_dir holds research\\pinrun.py)
Run BOTH patches on the build (either order): pinrun's v-0925x connect checks read the mark the ordercli patch adds.

FOUR CONFIRMED REVIEW DEFECTS (2026-11-13), the smallest fix for each (always on, no flag; no trading rule,
threshold, size, gate or hedge trigger moves), and ONE NEW FLAG (2026-11-14, band99late below; off when omitted = the
0925w band exactly). Every message of the new self-test checks starts "v-0925x <item>".

  clock    book_shape_wrap knows Kalshi's "clock" key (added to orderbook frames 2026-10-29). An EMPTY book's snapshot
           ({market_ticker, market_id, clock}) recorded api_shape absent_with_other_keys keys=clock and, the record
           being once per process per key, used up the alarm for a real rename of the level arrays ~10 min after
           every start. A rename (a new array name) is still an unknown key and still records, once. Recording only.
  prebank  risk_abort: with --loss-cap-frac the day stop is F x the bank and exists only once a balance read (or the
           size mirror's saved bank) sets LOSS_CAP. Until then a.loss_abort is the argv's placeholder (-$60), and one
           failed balance read at a restart ended for good any day already below -$60 (the real stop: ~0.187 x the
           bank). The DAY comparison now waits while ALL hold: the flag on, LOSS_CAP unset, no bank in state, and the
           startup_bank entry block in force (so no entry can be made; hedges, settlement, the run abort and every
           other brake run as before). The first read sets the stop and the same pass compares the day with it --
           and halts then if the day really is past it. Flag off, --no-auto-size (no startup_bank block), a bank in
           hand or a stop already set: exactly as before.
  drain    trade_loop: a terminal halt while holding starts a drain (halt_pending, DRAIN_MAX_S 600 s). When that halt
           CLEARED before the run went flat (a booked win lifts the day back over the DAY cap, reconcile reads again,
           an error streak ends) trading resumed but `draining` / `draining_since` were never cleared, so the NEXT
           terminal halt while holding wrote no halt_pending and -- 600 s after the FIRST halt -- timed out at once:
           an exit holding a bet nothing hedges. A pass with NO stop now ends that drain (one drain_cleared record),
           so the next halt starts its own. A pause still `continue`s above it, so a terminal halt masked by a
           transient one (risk_abort returns the first reason) keeps its clock: the drain stays bounded.
  connect  hedge_never_sent: a hedge whose request failed in the CONNECT phase (TCP connect or TLS handshake, nothing
           written) was read as never sent only for 7 fixed texts (refused, DNS, unreachable, the handshake timeout).
           A reset or a timeout during the handshake ("<urlopen error [WinError 10054] ...>", "<urlopen error timed
           out>") was UNKNOWN: counted covered, the position naked for 3+ s (KTRUTH_SETTLE_S) until ktruth reopened
           it. ordercli (patch_0925x_ordercli.py) now marks a connect-phase failure " [connect phase: not sent]" and
           this marker joins _NEVER_SENT_MARKERS; the "<urlopen error" prefix rule (v-keepconn texts stay UNKNOWN) is
           unchanged. pintake's halt on that -1 is unchanged (intended; the drain keeps hedging).

  band99late  --band99-max-tau SECONDS (new flag; default None = no limit, today's band). The band99 leg (--band99-
           ceiling 0.99 --band99-frac 0.10: a tenth of the coin's bet at up to 99c in a market pin holds nothing in)
           splits by WHEN it lands (11-14, three independent reads of the live band): legs at 31-45 s held all 12 band
           losses and, being the market's early leg, took pin's own early slot (pin's early leg was then refused
           early_once) -- all-in about -$7/day; legs at <= 30 s lost 0 of 396 markets, all-in about +$6/day. With the
           flag a band leg is placed only when tau (seconds to the close) <= SECONDS. A band leg that is too early is
           refused band99_early (beside band99_over / band99_held, once a close) and written ONCE a market as a
           band99_shadow record: ticker, side, the ask and its size, tau, the contracts it would have bought (n: the
           band's tenth cut to the book under the limit, the early leg's share and the coin cap -- an estimate of the
           send path), the limit the band order would have sent and the ladder up to it, fair, edge, EV, strike, spot,
           sigma, book and index age, drop_seen, budget_left. The skip sits where the band is decided -- above the EV
           skip, the signal counter, the attempt counters and the early leg -- so it spends NOTHING: no early leg
           (early_once stays free), no fill (max_per_market), no attempt, no signal; pin's own early leg can still buy
           that market, and a band leg can still come at <= SECONDS if the market is still unheld and the offer still
           in the band. Needs --band99-ceiling; SECONDS in [3, 60]. The start record names it (band99_max_tau).
"""
import hashlib
import os
import sys

BASE_PINRUN = "05a01fbb5ed2"
EXPECTED_PINRUN = "3a19b0019e9c"   # the reviewed result (the patch refuses to write anything else)
# (2026-11-13 the four fixes alone made 4f798c3df9ea; with band99late (2026-11-14) the build is the value above)


def refuse(msg):
    sys.stderr.write("REFUSED: " + msg + "\n")
    sys.exit(2)


if len(sys.argv) != 2:
    sys.stderr.write("usage: python patch_0925x.py <build_dir>   (build_dir holds research\\pinrun.py)\n")
    sys.exit(2)
B = sys.argv[1]
PR = os.path.join(B, "research", "pinrun.py")
if not os.path.isfile(PR):
    refuse("%s does not exist" % PR)


def sha12(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


class Src:
    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read().decode("utf-8")
        if "\r\n" not in raw:
            refuse(path + ": not CRLF")
        self.s = raw.replace("\r\n", "\n")
        if "\r" in self.s:
            refuse(path + ": stray CR")

    def once(self, anchor):
        n = self.s.count(anchor)
        if n != 1:
            refuse("%s: anchor found %d times (need exactly 1), nothing written: %r"
                   % (self.path, n, anchor[:90]))

    def after(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, anchor + text)

    def before(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, text + anchor)

    def replace(self, old, new):
        self.once(old)
        self.s = self.s.replace(old, new)

    def write(self, expected=None):
        data = self.s.replace("\n", "\r\n").encode("utf-8")
        got = hashlib.sha256(data).hexdigest()[:12]
        if expected is not None and got != expected:
            refuse("%s: the patched file would be %s, not the reviewed %s; nothing written"
                   % (self.path, got, expected))
        open(self.path, "wb").write(data)
        return got


if sha12(PR) != BASE_PINRUN:
    refuse("research/pinrun.py is not 0925w (%s, want %s); nothing written" % (sha12(PR), BASE_PINRUN))
R = Src(PR)
if ("v-0925x" in R.s or "_pre_bank" in R.s or "drain_cleared" in R.s or "[connect phase: not sent]" in R.s
        or "BAND99_MAX_TAU" in R.s or "band99_shadow" in R.s or "band99_early" in R.s):
    refuse("already patched (v-0925x is in it); nothing written")
if ("INDEX_5HZ" not in R.s or "hedge5_shadow" not in R.s or "book_shape_wrap" not in R.s
        or "def band99_why(" not in R.s or "_band99_now = True" not in R.s):
    refuse("not the 0925w build (no v-hedge5 / apishape code); nothing written")

# ============================================================================ 1. clock: a known orderbook key
R.replace('''    _known = ("market_ticker", "market_id", "yes_dollars_fp", "no_dollars_fp")
''', '''    # v-0925x clock (2026-11-13): Kalshi added "clock" to orderbook frames
    # (2026-10-29). An EMPTY book's snapshot is {market_ticker, market_id,
    # clock}: it read as a rename (keys=clock) and, once per process, used up
    # the alarm meant for a real rename of the level arrays ~10 min after
    # every start. Known now; a renamed array is still an unknown key.
    _known = ("market_ticker", "market_id", "clock", "yes_dollars_fp", "no_dollars_fp")
''')

# ============================================================================ 2. prebank: the DAY comparison waits for a bank
R.replace('''    _dl = mk_view(_dl, state, "day")
    if _dl is not None and _dl <= a.loss_abort:
''', '''    _dl = mk_view(_dl, state, "day")
    # v-0925x prebank (2026-11-13): WITH --loss-cap-frac THERE IS NO DAY STOP
    # UNTIL A BANK IS READ. The stop is F x the bank and exists once a balance
    # read (or the size mirror's saved bank) sets LOSS_CAP; until then
    # a.loss_abort is the argv's placeholder (-$60), and ONE failed read at a
    # restart ended for good any day already below it -- a day the real stop
    # (~$700 at a $3,700 bank) allows. While the startup_bank block is in force
    # no entry can be made (hedges, settlement and every brake below run as
    # before), so the DAY comparison waits for the read; the pass that reads
    # the bank compares the day with the real stop and halts if it is past it.
    # Flag off, no startup_bank block (--no-auto-size), a bank in hand or a
    # stop already set: exactly as before.
    _pre_bank = (LOSS_CAP_FRAC is not None and LOSS_CAP is None
                 and state.get("bank") is None
                 and "startup_bank" in (state.get("entry_blocks") or {}))
    if _dl is not None and not _pre_bank and _dl <= a.loss_abort:
''')

# ============================================================================ 3. drain: a stop that cleared ends its drain
R.replace('''        if state.get("paused_on"):
            rec("resume", after=state.pop("paused_on"))
            print("  --- RESUMED")
        if stop:
''', '''        if state.get("paused_on"):
            rec("resume", after=state.pop("paused_on"))
            print("  --- RESUMED")
        if not stop and state.get("draining"):
            # v-0925x drain (2026-11-13): THE HALT THAT BEGAN A DRAIN CLEARED
            # BEFORE THE RUN WENT FLAT (a booked win lifts the day back over
            # the DAY cap, reconcile reads again, an error streak ends), so
            # trading resumed -- and the drain was never forgotten: the NEXT
            # terminal halt while holding wrote no halt_pending and, DRAIN_MAX_S
            # after the FIRST halt, timed out at once, exiting holding a bet
            # nothing hedges. That drain is over; the next halt starts its own.
            # Only on a pass with NO stop: a pause `continue`s above, so a
            # terminal halt masked by a transient one keeps its clock.
            _dr_was = state.pop("draining", None)
            _dr_since = state.pop("draining_since", None)
            try:
                rec("drain_cleared", was=_dr_was,
                    waited_s=(None if _dr_since is None
                              else round(now - float(_dr_since), 1)))
                print(f"  --- the stop that began the drain cleared: {_dr_was}")
            except Exception:                            # noqa: BLE001
                pass
        if stop:
''')

# ============================================================================ 4. connect: ordercli's connect-phase mark
R.replace('''    "nodename nor servname provided",
    "The handshake operation timed out")                    # TLS, pre-send
''', '''    "nodename nor servname provided",
    "The handshake operation timed out",                    # TLS, pre-send
    # v-0925x connect (2026-11-13): ordercli.CONNECT_NOT_SENT, which the
    # kept-connection path appends to a CONNECT-phase failure (the TCP connect
    # or the TLS handshake: nothing written) -- so a reset or a timeout DURING
    # the handshake, texts with no marker of their own, is known never sent.
    # Never on a write- or read-phase failure, never on a v-keepconn text.
    "[connect phase: not sent]")
''')

# ============================================================================ 5. self-test: clock, beside the apishape block
R.replace('''       % (len(_v_qk2), _v_lbt2.get("yes_bid"), _v_lbt2.get("no_bid")))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
''', '''       % (len(_v_qk2), _v_lbt2.get("yes_bid"), _v_lbt2.get("no_bid")))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    # v-0925x clock (2026-11-13): an EMPTY book's snapshot -- market_ticker,
    # market_id and Kalshi's clock, no level array -- is not a rename and
    # records nothing, so it cannot use up the rename alarm; a renamed level
    # array beside a clock still records ONCE, naming only the unknown key.
    _x_lb = livebook.LiveBook(key_id="selftest", key_file="none")
    _x_lbw = book_shape_wrap(_x_lb)
    _x_lb.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 8, "seq": 1, "msg": {
        "market_ticker": "TX1", "market_id": "m", "clock": 1762990000123}}), 1000)
    _x_lq0 = list(_API_SHAPE_Q)
    _x_lb.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 8, "seq": 2, "msg": {
        "market_ticker": "TX2", "market_id": "m", "clock": 1762990000456,
        "yes_levels": [["0.5000", "3.00"]]}}), 1001)
    _x_lq1 = list(_API_SHAPE_Q)
    ck(_x_lbw is True and not _x_lq0 and len(_x_lq1) == 1
       and (_x_lq1[0]["endpoint"], _x_lq1[0]["field"], _x_lq1[0]["what"])
       == ("ws orderbook_snapshot", "yes_dollars_fp/no_dollars_fp", "absent_with_other_keys")
       and _x_lq1[0].get("keys") == "yes_levels",
       "v-0925x clock: an empty book's snapshot (market_ticker, market_id, clock) "
       "records nothing (%d records), so it cannot use up the rename alarm; a "
       "renamed level array beside a clock still records once, keys %r"
       % (len(_x_lq0), (_x_lq1[0].get("keys") if _x_lq1 else None)))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
''')

# ============================================================================ 6. self-test: prebank, drain, connect
R.before('''    # ---- B: the 3rd bet out, the brake moved, SIZE and every order the same
''', '''    # ---- v-0925x (2026-11-13): prebank, drain, connect ---------------------
    # (clock is beside the apishape block.) Each fix: a DRIVEN world through
    # the REAL trade_loop where its condition happens, and NULL worlds where
    # the old behaviour must hold. Every message starts "v-0925x <item>".
    # prebank, unit: risk_abort's DAY comparison waits only while --loss-cap-
    # frac is on, LOSS_CAP unset, no bank in state AND the startup_bank block
    # is in force; any one of those not so, the -$100 day halts at -$60
    _x_dlr = globals()["day_loss"]
    _x_lsv = (LOSS_CAP, LOSS_CAP_FRAC, __import__("copy").deepcopy(pintake.LEDGER))

    class _XPA(object):
        loss_abort = -60.0
        max_positions = 3
        max_losses = 0
        live = True

    def _x_pra(lc, lcf, **kw):
        _st = {"halted": False, "errors": 0, "open_cost": 0.0,
               "entry_blocks": {"startup_bank": {"since": 0.0, "kind": "entries_blocked"}}}
        _st.update(kw)
        globals()["LOSS_CAP"], globals()["LOSS_CAP_FRAC"] = lc, lcf
        return risk_abort(_st, _XPA())
    try:
        globals()["day_loss"] = (lambda *_a, **_k: -100.0)
        pintake.LEDGER.clear()
        pintake.LEDGER.update({"halt": None, "realised": 0.0, "committed": 0.0,
                               "positions": {}, "losses": 0})
        _x_pu = [_x_pra(None, 0.187),
                 _x_pra(None, 0.187, bank=3300.0),
                 _x_pra(205.7, 0.187),
                 _x_pra(None, 0.187, entry_blocks={}),
                 _x_pra(None, None)]
    finally:
        globals()["day_loss"] = _x_dlr
        globals()["LOSS_CAP"], globals()["LOSS_CAP_FRAC"] = _x_lsv[0], _x_lsv[1]
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_x_lsv[2])
    ck(_x_pu[0] is None
       and all(str(_u or "").startswith("DAY loss cap") for _u in _x_pu[1:]),
       "v-0925x prebank: a -$100 day under the argv's -$60 placeholder WAITS "
       "only before the first bank (flag on, no stop, no bank, startup_bank "
       "blocking entries: %r); a bank in state, a stop already set, no "
       "startup_bank block (--no-auto-size) or the flag off each halt as "
       "before (%r)" % (_x_pu[0], [str(_u or "")[:13] for _u in _x_pu[1:]]))
    # A's market with a 500-lot book: the $1,000 read sizes the bet to 125,
    # which A's own 50-lot book would refuse (depth_floor) -- nothing to do
    # with the stop
    _x_pA = dict(_k1_A(collapse_at=None), book=(lambda t: _ob(0.94, 0.05, size=500.0)))
    _x_pbk = (lambda t: None if t < 5.0 else 1000.0)
    _x_p1 = _offline_trade_loop([_x_pA], live=True, run_s=25.0,
                                day0=-100.0, loss_abort=-60.0, bank=_x_pbk,
                                flags={"LOSS_CAP_FRAC": 0.187})
    _x_p1b = _kinds(_x_p1, "startup_bank")
    _x_p1p = _v_posts(_x_p1, _kA, "bid")
    ck(_x_p1["raised"] is None and not _kinds(_x_p1, "halt")
       and not _kinds(_x_p1, "halt_pending")
       and len(_x_p1b) == 1 and _x_p1b[0].get("source") == "api"
       and _x_p1b[0]["t"] >= 5.0
       and abs(float(_x_p1b[0].get("loss_cap") or 0) - round(0.187 * 1100.0, 2)) < 1e-6
       and float(_x_p1b[0].get("loss_abort") or 0) < -100.0
       and _x_p1p and min(p["_t"] for p in _x_p1p) >= 5.0,
       "v-0925x prebank DRIVEN: a restart on a -$100 day whose balance read "
       "fails until t 5 (argv stop -$60) does NOT halt: entries wait for the "
       "read (startup_bank at t %s), which sets the real stop ($%s, run/day "
       "stop %s) and trading starts (first post t %s)"
       % ((_x_p1b[0]["t"] if _x_p1b else None),
          (_x_p1b[0].get("loss_cap") if _x_p1b else None),
          (_x_p1b[0].get("loss_abort") if _x_p1b else None),
          (min(p["_t"] for p in _x_p1p) if _x_p1p else None)))
    _x_p2 = _offline_trade_loop([_x_pA], live=True, run_s=25.0,
                                day0=-400.0, loss_abort=-60.0, bank=_x_pbk,
                                flags={"LOSS_CAP_FRAC": 0.187})
    _x_p3 = _offline_trade_loop([_x_pA], live=True, run_s=25.0,
                                day0=-100.0, loss_abort=-60.0, bank=_x_pbk)
    _x_p4 = _offline_trade_loop([_x_pA], live=True, run_s=25.0,
                                day0=-100.0, loss_abort=-60.0,
                                flags={"LOSS_CAP_FRAC": 0.187})
    _x_ph = [_kinds(_w, "halt") for _w in (_x_p2, _x_p3, _x_p4)]
    ck(all(_w["raised"] is None for _w in (_x_p2, _x_p3, _x_p4))
       and all(len(_h) == 1 and str(_h[0].get("why")).startswith("DAY loss cap")
               for _h in _x_ph)
       and _x_ph[0][0]["t"] >= 5.0 and _x_ph[1][0]["t"] < 1.0 and _x_ph[2][0]["t"] < 1.0
       and not any(_v_posts(_w, _kA, "bid") for _w in (_x_p2, _x_p3, _x_p4)),
       "v-0925x prebank NULL: a day past the REAL stop halts on the read (t "
       "%s, -$400 vs 0.187 x $1,400); the flag off (t %s) and --no-auto-size "
       "(no startup_bank block, t %s) halt at once on the argv's -$60 as "
       "before; nothing is bought in any of them"
       % tuple((_h[0]["t"] if _h else None) for _h in _x_ph))
    # drain: a planted terminal halt (not in TRANSIENT_HALTS) over a held A;
    # DRAIN_MAX_S 4 s so a stale clock shows inside the world
    _x_t0 = 1_800_000_000 - 30 + 0.1           # the offline worlds' start (tau0 30)
    _x_rar = globals()["risk_abort"]
    _x_plan = {"halt": (), "pause": ()}

    def _x_ra(state_, a_):
        _t = time.time() - _x_t0
        if any(_a0 <= _t < _a1 for _a0, _a1 in _x_plan["halt"]):
            return "planted: 2 errors on the ORDER path"
        if any(_a0 <= _t < _a1 for _a0, _a1 in _x_plan["pause"]):
            return "open cap: planted"
        return _x_rar(state_, a_)
    try:
        globals()["risk_abort"] = _x_ra
        _x_plan.update(halt=((1.0, 2.0), (6.0, 99.0)), pause=())
        _x_d1 = _offline_trade_loop([_k1_A(collapse_at=7)], live=True, run_s=12.0,
                                    flags={"DRAIN_MAX_S": 4.0})
        _x_plan.update(halt=((1.0, 2.0), (4.0, 99.0)), pause=((2.0, 4.0),))
        _x_d2 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=12.0,
                                    flags={"DRAIN_MAX_S": 4.0})
        _x_plan.update(halt=((1.0, 99.0),), pause=())
        _x_d3 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=12.0,
                                    flags={"DRAIN_MAX_S": 4.0})
    finally:
        globals()["risk_abort"] = _x_rar
    _x_d1p = _kinds(_x_d1, "halt_pending")
    _x_d1c = _kinds(_x_d1, "drain_cleared")
    _x_d1t = _kinds(_x_d1, "drain_timeout")
    ck(_x_d1["raised"] is None and len(_x_d1p) == 2
       and 1.0 <= _x_d1p[0]["t"] < 1.2 and 6.0 <= _x_d1p[1]["t"] < 6.2
       and len(_x_d1c) == 1 and 2.0 <= _x_d1c[0]["t"] < 2.2
       and str(_x_d1c[0].get("was", "")).startswith("planted:")
       and len(_x_d1t) == 1 and _x_d1t[0]["t"] >= 9.9
       and _hedged(_x_d1, _kA) >= 5.0 - 1e-9,
       "v-0925x drain DRIVEN: a halt while holding (t 1) that clears (t 2) ends "
       "its drain (drain_cleared at t %s); the NEXT halt while holding (t 6) "
       "starts its own drain (halt_pending at t %s, not drain_timeout at once), "
       "so A's collapse at t 7 is still hedged (%g) and that drain times out on "
       "its own clock (t %s)"
       % ((_x_d1c[0]["t"] if _x_d1c else None),
          ([r["t"] for r in _x_d1p][1:2]), _hedged(_x_d1, _kA),
          (_x_d1t[0]["t"] if _x_d1t else None)))
    _x_d2t = _kinds(_x_d2, "drain_timeout")
    _x_d3t = _kinds(_x_d3, "drain_timeout")
    ck(_x_d2["raised"] is None and len(_kinds(_x_d2, "halt_pending")) == 1
       and not _kinds(_x_d2, "drain_cleared")
       and len(_x_d2t) == 1 and 5.0 <= _x_d2t[0]["t"] < 5.2
       and _x_d3["raised"] is None and len(_kinds(_x_d3, "halt_pending")) == 1
       and not _kinds(_x_d3, "drain_cleared")
       and len(_x_d3t) == 1 and 5.0 <= _x_d3t[0]["t"] < 5.2
       and not _kinds(_x_p1, "drain_cleared"),
       "v-0925x drain NULL: a PAUSE inside a drain (the halt masked by a "
       "transient reason) does not end it -- the drain keeps its clock and "
       "times out at t %s, bounded as before; a halt that never clears drains "
       "once and times out at t %s; no halt, no drain_cleared"
       % ((_x_d2t[0]["t"] if _x_d2t else None), (_x_d3t[0]["t"] if _x_d3t else None)))
    _x_tl = inspect.getsource(trade_loop)
    ck(_x_tl.count('        if not stop and state.get("draining"):') == 1
       and _x_tl.index("            stop = risk_abort(state, a)")
       < _x_tl.index("        if stop and halt_is_transient(stop):")
       < _x_tl.index('        if not stop and state.get("draining"):')
       < _x_tl.index("            if _openn74 and DRAIN_ON_HALT:"),
       "v-0925x drain by source: the drain is forgotten only on a pass whose "
       "risk check returned NO stop -- after the pause's `continue`, before the "
       "terminal-halt branch")
    # connect: the text ordercli itself writes for a failure in each phase
    _x_oc = pintake.ordercli
    _x_rst = ConnectionResetError(10054, "An existing connection was forcibly "
                                         "closed by the remote host")
    _x_cn = _x_oc._Fail("connect", False, _x_rst, None).text()
    _x_ct = _x_oc._Fail("connect", False, TimeoutError("timed out"), None).text()
    _x_wr = _x_oc._Fail("write", False, _x_rst, None).text()
    _x_rd = _x_oc._Fail("read", False, TimeoutError("timed out"), None).text()
    _x_ns = getattr(_x_oc, "CONNECT_NOT_SENT", None)
    ck(isinstance(_x_ns, str) and _x_ns.strip() in _NEVER_SENT_MARKERS
       and hedge_never_sent({"status_code": -1, "raw": _x_cn})
       and hedge_never_sent({"status_code": -1, "raw": _x_ct})
       and not hedge_never_sent({"status_code": -1, "raw": _x_wr})
       and not hedge_never_sent({"status_code": -1, "raw": _x_rd})
       and not hedge_never_sent({"status_code": 503, "raw": _x_cn})
       and not any(hedge_never_sent({"status_code": -1, "raw": _t + str(_x_ns)})
                   for _t in _fc_vk),
       "v-0925x connect: ordercli's own text for a reset or a timeout in the "
       "CONNECT phase (TCP / TLS handshake, nothing written) is read as never "
       "sent (%r); the same reset in the WRITE phase and a read timeout stay "
       "UNKNOWN, as does a v-keepconn text even with the mark on its end"
       % (str(_x_cn)[-60:],))
    _x_k2 = _offline_trade_loop([_k1_A()], live=True, reply=_k2n_reply(_x_cn))
    _x_k2w = _offline_trade_loop([_k1_A()], live=True, reply=_k2n_reply(_x_wr))
    ck(_x_k2["raised"] is None and len(_k2_posts(_x_k2, _kA, "ask")) == 2
       and abs(_hedged(_x_k2, _kA) - 5.0) < 1e-9
       and _kinds(_x_k2, "hedge_not_sent", _kA)
       and not _kinds(_x_k2, "hedge_unknown", _kA)
       and _x_k2w["raised"] is None and len(_k2_posts(_x_k2w, _kA, "ask")) == 1
       and _kinds(_x_k2w, "hedge_unknown", _kA)
       and not _kinds(_x_k2w, "hedge_not_sent", _kA),
       "v-0925x connect DRIVEN: a hedge whose TLS handshake was reset is sent "
       "again next second and fills in full (%d hedge POSTs, hedged %g); the "
       "same reset after the connection was up (write phase) is still counted "
       "covered and NOT resent (%d hedge POSTs)"
       % (len(_k2_posts(_x_k2, _kA, "ask")), _hedged(_x_k2, _kA),
          len(_k2_posts(_x_k2w, _kA, "ask"))))

''')

# ============================================================================ 7. band99late: the flag's constant
R.after('''BAND99_FRAC = 0.10           # --band99-frac: the band buy's share of the coin's bet
_DEFAULT_BAND99_FRAC = 0.10
''', '''# v-0925x band99late (2026-11-14): THE BAND LEG ONLY INSIDE --band99-max-tau
# SECONDS. Three independent reads of the live band (11-14) split it by when
# it lands: legs at 31-45 s held all 12 band losses AND, being the market's
# early leg, took pin's own early slot (pin's early leg was then refused
# early_once) -- all-in about -$7/day; legs at <= 30 s lost 0 of 396 markets,
# all-in about +$6/day. With the flag a band leg too early is not bought: it
# is refused band99_early and written ONCE a market as band99_shadow (what it
# would have bought, priced like the band order), and it spends nothing -- no
# signal, no attempt, no early leg, no fill count -- so pin's own early leg
# may still buy that market. None = no limit (the shipped value, = 0925w).
BAND99_MAX_TAU = None        # --band99-max-tau SECONDS; None = off
_DEFAULT_BAND99_MAX_TAU = None
''')

# ============================================================================ 8. band99late: the wait rule and the shadow's fields
R.before('''def drop_note(hist, key, t, price, tau):''', '''def band99_too_early(tau):
    """v-0925x band99late: True when --band99-max-tau is set and a band leg at
    `tau` seconds to the close must wait (tau over the flag). Off: always
    False, exactly as before. A tau it cannot read waits: the leg is placed
    only when tau is KNOWN to be inside."""
    if BAND99_MAX_TAU is None:
        return False
    try:
        return not (float(tau) <= float(BAND99_MAX_TAU) + 1e-9)
    except (TypeError, ValueError):
        return True


def band99_shadow_fields(book, tk, want, price, f, ask_size, full, bet=None,
                         ssz=None, csz=None, tau=None):
    """v-0925x band99late: the fields of a band99_shadow record -- the band leg
    pin WOULD have sent at this look had --band99-max-tau not held it back,
    priced the way the band order is: its leg (early past TAU_MAX with the
    early leg on, as staged_take names it), the limit the send path uses
    (sweep_limit up to BAND99_CEILING with the EV floor off, then the early
    leg's own price cap), our side's ask ladder up to that limit and the depth
    under it, and the contracts n: what the book holds up to the limit (at
    least the touch, at most `bet`), cut by the early leg's share, the series
    and coin caps and last by the band's own share of the coin's bet
    (n_band). An ESTIMATE of the send path, as v-wsfall10's would_n is (the
    close's budget is the record's budget_left). Reads the book; sends
    nothing. Never raises: a field it cannot work out stays None."""
    out = {"leg": None, "n": None, "n_band": None, "limit": None,
           "sweep_headroom_c": None, "ladder": None, "buyable": None,
           "band99_ev_c": None}
    try:
        out["n_band"] = band99_size(full)
        out["leg"] = ("early" if (EARLY_TAU_MAX > TAU_MAX
                                  and float(tau) > TAU_MAX) else "full")
    except Exception:                                    # noqa: BLE001
        pass
    try:
        out["band99_ev_c"] = round(100.0 * float(expected_value(float(price))), 3)
    except Exception:                                    # noqa: BLE001
        pass
    try:
        _lm = float(sweep_limit(f, float(price), want,
                                ceiling=float(BAND99_CEILING), ev_floor=-1.0))
        if out["leg"] == "early" and EARLY_MAX_PRICE < 1.0:
            _lm = min(_lm, float(EARLY_MAX_PRICE))
        out["limit"] = round(_lm, 4)
        out["sweep_headroom_c"] = round(100.0 * (_lm - float(price)), 3)
    except Exception:                                    # noqa: BLE001
        return out
    try:
        out["ladder"] = [[round(float(_p), 4), round(float(_z), 2)]
                         for _p, _z in list(book.rungs(tk, want, _lm) or [])[:12]]
    except Exception:                                    # noqa: BLE001
        pass
    try:
        _bet = float(SIZE if bet is None else bet)
        _dp = (float(book.buyable(tk, want, _lm))
               if (SWEEP_DEPTH and _lm > float(price) + 1e-9) else 0.0)
        out["buyable"] = round(_dp, 2)
        _n = max(min(_bet, float(ask_size)), min(_bet, _dp))
        if out["leg"] == "early":
            _n = min(_n, float(EARLY_FRAC) * float(full))
        for _c in (ssz, csz):
            if _c is not None:
                _n = min(_n, float(_c))
        _n = min(_n, float(band99_size(full)))
        out["n"] = round(max(0.0, _n), 2)
    except Exception:                                    # noqa: BLE001
        pass
    return out


''')

# ============================================================================ 9. band99late: the decision, where the band is decided
R.replace('''                    _b99 = band99_why(price, _lad is not None,
                                      band99_held(prev, open_pos, tk))
                    if _b99 is None:
                        _band99_now = True
''', '''                    _b99 = band99_why(price, _lad is not None,
                                      band99_held(prev, open_pos, tk))
                    if _b99 is None and band99_too_early(tau):
                        # v-0925x band99late (2026-11-14): A BAND LEG TOO EARLY
                        # FOR --band99-max-tau IS NOT BOUGHT. Refused below
                        # with the band's other refusals (band99_early, once a
                        # close) and shadowed ONCE a market here -- what it
                        # would have bought, priced like the band order. HERE,
                        # above the EV skip, the signal counter, the attempt
                        # counters and the early leg, so the skip spends
                        # NOTHING: no early leg (early_once stays free), no
                        # fill (max_per_market), no attempt -- pin's own early
                        # leg may still buy the market, and the band may still
                        # buy it inside the flag while it stays unheld.
                        # Off (None): never true, exactly as before.
                        _b99 = "band99_early"
                        if (close_s, tk, _b99) not in gate_seen:
                            try:
                                # (ssz None: a ladder rung is never a band leg)
                                _b9s = band99_shadow_fields(
                                    book, tk, want, price, f, size, _fsz,
                                    bet=float(SIZE), ssz=None, csz=_csz,
                                    tau=tau)
                                rec("band99_shadow", ticker=tk, close_s=close_s,
                                    want=want, side=want,
                                    ask=round(float(price), 4),
                                    ask_seen=round(float(price), 4),
                                    ask_size=size, tau=tau,
                                    max_tau=BAND99_MAX_TAU, fair=round(f, 5),
                                    edge_c=round(100 * e, 3), strike=strike,
                                    digits=digits, spot=spot,
                                    sigma=round(sg, 6),
                                    book_age_ms=b.get("age_ms"),
                                    index_age_s=round(iage, 2),
                                    exchange_index=exi, full=_fsz,
                                    coin_size=_csz, early_held=_held46,
                                    drop_seen=drop_seen(drop_hist, (close_s, tk, want), now),
                                    budget_left=_budget_left(close_s, tk, tau),
                                    band99=True,
                                    band99_ceiling=BAND99_CEILING,
                                    band99_frac=BAND99_FRAC,
                                    live=bool(live), sent=False, **_b9s)
                                print(f"  BAND99 SHADOW {tk} tau={tau}s "
                                      f"{want.upper()} @{price:.4f}: the band "
                                      f"waits for tau<={BAND99_MAX_TAU}s; it "
                                      f"would buy {_b9s.get('n')} at up to "
                                      f"{_b9s.get('limit')}; nothing sent")
                            except Exception:            # noqa: BLE001
                                pass
                    if _b99 is None:
                        _band99_now = True
''')

# ============================================================================ 10. band99late: pinned offline, watched by the give-back guard
R.replace('''    "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW", "INDEX_5HZ")


def _offline_trade_loop(''', '''    "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW", "INDEX_5HZ", "BAND99_MAX_TAU")


def _offline_trade_loop(''')
R.replace('''                 "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW", "INDEX_5HZ")


def _selftest_body():''', '''                 "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW", "INDEX_5HZ",
                 "BAND99_MAX_TAU")


def _selftest_body():''')

# ============================================================================ 11. band99late: the flag, its checks, the start record
R.after('''    ap.add_argument("--band99-frac", type=float, default=None, metavar="F",
                    help="v-band99: the band buy's share of the coin's full bet "
                         "(default %.2f; 0.01..0.25)" % _DEFAULT_BAND99_FRAC)
''', '''    ap.add_argument("--band99-max-tau", type=int, default=None, metavar="SECONDS",
                    help="v-0925x band99late: place a band leg only at or under "
                         "SECONDS to the close (3..60). A band leg that is too "
                         "early is refused band99_early and written once a market "
                         "as band99_shadow (what it would have bought); it spends "
                         "no early leg, fill or attempt, so pin's own early leg "
                         "may still buy the market. Needs --band99-ceiling; off "
                         "by default (no limit)")
''')
R.after('''        globals()["BAND99_FRAC"] = float(a.band99_frac)
''', '''    if a.band99_max_tau is not None:                       # v-0925x band99late
        if a.band99_ceiling is None:
            raise SystemExit("--band99-max-tau needs --band99-ceiling")
        if not (TAU_MIN <= int(a.band99_max_tau) <= 60):
            raise SystemExit("--band99-max-tau must be in [%d, 60], got %r"
                             % (TAU_MIN, a.band99_max_tau))
        globals()["BAND99_MAX_TAU"] = int(a.band99_max_tau)
''')
R.after('''        band99_ceiling=BAND99_CEILING, band99_frac=BAND99_FRAC,
''', '''        band99_max_tau=BAND99_MAX_TAU,                      # v-0925x band99late
''')

# ============================================================================ 12. band99late: the band's own by-source check
# counts the shadow's one read of drop_hist (a record, never a decision); every other count is as it was
R.replace('''    ck(_b99_src.count("drop_hist") == 3
       and _b99_src.count("drop_note(drop_hist") == 1
       and _b99_src.count("drop_seen(drop_hist") == 1
       and _b99_src.count('drop_seen=sig.get("drop_seen")') == 1
       and _b99_src.count("_band99_now = True") == 1
       and _b99_src.count("if _band99_now:") == 4
       and _b99_src.count("not _band99_now") == 2,
       "v-band99 by source: drop_hist is written once (every look) and read "
       "once (into the signal), never by a decision; the band is set at ONE "
       "place and read by the size (signal, live, paper), the limit, the EV "
       "skip and the old ceiling refusal only")
''', '''    # (v-0925x band99late, 2026-11-14: drop_hist is read once more, into the
    # band99_shadow record a too-early band leg writes -- a record, never a
    # decision; every other count is unchanged)
    _b99_shr = "drop_seen=drop_seen(drop_hist, (close_s, tk, want), now),"
    ck(_b99_src.count("drop_hist") == 4
       and _b99_src.count("drop_note(drop_hist") == 1
       and _b99_src.count("drop_seen(drop_hist") == 2
       and _b99_src.count(_b99_shr) == 1
       and _b99_src.count('rec("band99_shadow"') == 1
       and _b99_src.index('rec("band99_shadow"') < _b99_src.index(_b99_shr)
       < _b99_src.index("_band99_now = True")
       and _b99_src.count('drop_seen=sig.get("drop_seen")') == 1
       and _b99_src.count("_band99_now = True") == 1
       and _b99_src.count("if _band99_now:") == 4
       and _b99_src.count("not _band99_now") == 2,
       "v-band99 by source: drop_hist is written once (every look) and read "
       "twice -- into the signal and into the band99late shadow record -- "
       "never by a decision; the band is set at ONE place and read by the "
       "size (signal, live, paper), the limit, the EV skip and the old "
       "ceiling refusal only")
''')

# ============================================================================ 13. band99late: the self-test, beside the band's own
R.after('''       "v-band99 add-on: an ordinary buy's signal and order carry drop_seen "
       "too, and band99 False")
''', '''    # ---- v-0925x band99late (2026-11-14): --band99-max-tau -----------------
    # PURE: the wait rule, and the shadow's fields on a planted book (every
    # flag those read is pinned here, so the running argv cannot move them).
    # DRIVEN: the REAL trade_loop, live path, a 99c band offer at tau 25, 33
    # and 40, with the flag at 30 and off. Every message starts "v-0925x".
    _x9_g = {"BAND99_MAX_TAU": None, "BAND99_CEILING": 0.99, "BAND99_FRAC": 0.10,
             "SWEEP_ENABLED": True, "SWEEP_DEPTH": True, "EARLY_TAU_MAX": 45,
             "TAU_MAX": 30, "EARLY_FRAC": 0.333, "EARLY_MAX_PRICE": 1.0,
             "SKIP_BANDS": (), "EDGE_FLOOR": _DEFAULT_EDGE_FLOOR}
    _x9_was = {_k: globals()[_k] for _k in _x9_g}

    class _X9Book(object):
        def rungs(self, tk, side, lim):
            return [(0.985, 3.0), (0.99, 40.0)][:(2 if lim >= 0.99 - 1e-9 else 1)]

        def buyable(self, tk, side, lim):
            return 43.0 if lim >= 0.99 - 1e-9 else 3.0

    class _X9Thin(_X9Book):
        def buyable(self, tk, side, lim):
            return 3.0

    class _X9Bad(object):
        def rungs(self, *_a):
            raise RuntimeError("planted")

        def buyable(self, *_a):
            raise RuntimeError("planted")
    try:
        globals().update(_x9_g)
        _x9_off = [band99_too_early(_t) for _t in (45, 40, 31, 30, 25, None, "x")]
        globals()["BAND99_MAX_TAU"] = 30
        _x9_on = [band99_too_early(_t) for _t in (45, 40, 31, 30, 25, 3, None, "x")]
        _x9_fA = band99_shadow_fields(_X9Book(), "T", "yes", 0.985, 0.999, 3.0,
                                      50.0, bet=50.0, tau=40)
        _x9_fB = band99_shadow_fields(_X9Book(), "T", "yes", 0.985, 0.999, 3.0,
                                      50.0, bet=50.0, tau=25, csz=2.0)
        _x9_fC = band99_shadow_fields(_X9Thin(), "T", "yes", 0.985, 0.999, 3.0,
                                      50.0, bet=50.0, tau=40)
        _x9_fD = band99_shadow_fields(_X9Bad(), "T", "yes", 0.985, 0.999, 3.0,
                                      50.0, bet=50.0, tau=40)
        _x9_fE = band99_shadow_fields(_X9Book(), "T", "yes", "x", 0.999, 3.0,
                                      50.0, bet=50.0, tau=40)
    finally:
        globals().update(_x9_was)
    ck(_DEFAULT_BAND99_MAX_TAU is None and _x9_off == [False] * 7
       and _x9_on == [True, True, True, False, False, False, True, True],
       "v-0925x band99late PURE: ships OFF (no band leg ever waits: %r); at 30 a "
       "band leg at tau 31 or more waits and one at 30 or under goes, and a tau "
       "it cannot read waits (%r)" % (_x9_off, _x9_on))
    ck(_x9_fA.get("leg") == "early" and _x9_fA.get("n_band") == 5.0
       and _x9_fA.get("n") == 5.0 and _x9_fA.get("buyable") == 43.0
       and 0.985 <= float(_x9_fA.get("limit") or 0) <= 0.99 + 1e-9
       and _x9_fA.get("ladder") == [[0.985, 3.0], [0.99, 40.0]][
           :(2 if float(_x9_fA.get("limit") or 0) >= 0.99 - 1e-9 else 1)]
       and _x9_fA.get("band99_ev_c") == round(100.0 * expected_value(0.985), 3)
       and _x9_fB.get("leg") == "full" and _x9_fB.get("n") == 2.0
       and _x9_fC.get("n") == 3.0
       and _x9_fD.get("limit") is not None and _x9_fD.get("ladder") is None
       and _x9_fD.get("buyable") is None and _x9_fD.get("n") is None
       and _x9_fD.get("n_band") == 5.0
       and _x9_fE.get("limit") is None and _x9_fE.get("n") is None
       and _x9_fE.get("band99_ev_c") is None and _x9_fE.get("n_band") == 5.0,
       "v-0925x band99late PURE: the shadow's contracts are the band's tenth of "
       "the coin's 50 (5) out of 43 under its limit %s at tau 40 (an early "
       "leg); 2 under a coin cap of 2 at tau 25 (a full leg); 3 when the book "
       "holds 3; a book that raises leaves the ladder, depth and n None, a "
       "garbage ask the limit too, and neither raises (%r)"
       % (_x9_fA.get("limit"), _x9_fA))
    _x9_f = {"BAND99_CEILING": 0.99, "BAND99_FRAC": 0.10, "EARLY_TAU_MAX": 45,
             "EARLY_FRAC": 0.333, "EARLY_MIN_PRICE": 0.90, "EARLY_MAX_EDGE": 10.0,
             "MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"}
    _x9_30 = dict(_x9_f, BAND99_MAX_TAU=30)

    def _x9_m(n, book_of):
        return {"tk": "KXBLT%d15M-B9L" % n, "series": "KXBLT%d15M" % n,
                "iid": "B9L%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.999), "book": book_of}
    _x9_99 = lambda t: _ob(0.94, 0.01)                         # YES at 99c throughout
    _x9_gone = lambda t: _ob(0.94, 0.01) if t < 2.0 else _ob(0.94, None)   # 99c, then no YES offer
    _x9_97 = lambda t: _ob(0.94, 0.01) if t < 2.0 else _ob(0.94, 0.03)     # 99c, then 97c

    def _x9_w(n, book_of, tau0, flags):
        _wt, _wc = _k1_take(False)
        _wr = _offline_trade_loop([_x9_m(n, book_of)], live=True, take=_wt,
                                  run_s=6.0, size=50.0, tau0=tau0, flags=flags)
        return _wr, _wc
    _x9_1, _x9_1c = _x9_w(1, _x9_99, 25, _x9_30)
    _x9_1n, _x9_1nc = _x9_w(2, _x9_99, 25, _x9_f)
    _x9_1o = _kinds(_x9_1, "order")
    _x9_1no = _kinds(_x9_1n, "order")
    ck(_x9_1["raised"] is None and _x9_1n["raised"] is None
       and [_c[2] for _c in _x9_1c] == [5.0] and [_c[2] for _c in _x9_1nc] == [5.0]
       and len(_x9_1o) == 1 and _x9_1o[0].get("band99") is True
       and _x9_1o[0].get("leg") == "full" and _x9_1o[0].get("tau_at_send") == 25
       and len(_x9_1no) == 1 and _x9_1no[0].get("band99") is True
       and _x9_1no[0].get("tau_at_send") == 25
       and not _kinds(_x9_1, "band99_shadow") and not _kinds(_x9_1n, "band99_shadow")
       and not _refusals(_x9_1, "band99_early") and not _refusals(_x9_1n, "band99_early"),
       "v-0925x band99late DRIVEN: with --band99-max-tau 30 a 99c band offer at "
       "tau 25 is bought exactly as with the flag off -- ONE band order for 5 "
       "(a tenth of 50) at tau 25 both ways (%r / %r), no shadow, no band99_early"
       % (_x9_1c, _x9_1nc))
    _x9_2, _x9_2c = _x9_w(3, _x9_gone, 40, _x9_30)
    _x9_2s = _kinds(_x9_2, "band99_shadow")
    ck(_x9_2["raised"] is None and not _x9_2c and not _kinds(_x9_2, "order")
       and not _kinds(_x9_2, "signal")
       and len(_x9_2s) == 1 and _x9_2s[0].get("tau") == 40
       and _x9_2s[0].get("ticker") == _x9_m(3, None)["tk"]
       and _x9_2s[0].get("want") == "yes" and _x9_2s[0].get("side") == "yes"
       and _x9_2s[0].get("ask") == 0.99 and _x9_2s[0].get("ask_size") == 50.0
       and _x9_2s[0].get("n") == 5.0 and _x9_2s[0].get("n_band") == 5.0
       and _x9_2s[0].get("leg") == "early" and _x9_2s[0].get("max_tau") == 30
       and _x9_2s[0].get("sent") is False and _x9_2s[0].get("live") is True
       and float(_x9_2s[0].get("limit") or 9) <= 0.99 + 1e-9
       and (_x9_2s[0].get("drop_seen") or [None])[0] == 0.99
       and "fair" in _x9_2s[0] and "budget_left" in _x9_2s[0]
       and len(_refusals(_x9_2, "band99_early")) == 1
       and not _refusals(_x9_2, "early_once"),
       "v-0925x band99late DRIVEN: at 30 a 99c band offer at tau 40 is NOT "
       "bought (orders %r): ONE band99_shadow (tau 40, YES 5 of 50 at 99c, an "
       "early leg, nothing sent) and one band99_early refusal however many "
       "looks it gets (%d shadows)" % (_x9_2c, len(_x9_2s)))
    _x9_3, _x9_3c = _x9_w(4, _x9_97, 40, _x9_30)
    _x9_3n, _x9_3nc = _x9_w(5, _x9_97, 40, _x9_f)
    _x9_3o = _kinds(_x9_3, "order")
    _x9_3no = _kinds(_x9_3n, "order")
    ck(_x9_3["raised"] is None and len(_kinds(_x9_3, "band99_shadow")) == 1
       and _kinds(_x9_3, "band99_shadow")[0].get("tau") == 40
       and len(_x9_3c) == 1 and abs(_x9_3c[0][2] - 0.333 * 50.0) < 0.02
       and len(_x9_3o) == 1 and _x9_3o[0].get("leg") == "early"
       and _x9_3o[0].get("band99") is False and _x9_3o[0].get("tau_at_send") == 38
       and abs(float(_x9_3o[0].get("ask_seen") or 0) - 0.97) < 1e-9
       and all(_r["t"] > _x9_3o[0]["t"] for _r in _refusals(_x9_3, "early_once")),
       "v-0925x band99late DRIVEN: the skip LEAVES THE EARLY SLOT FREE -- 99c at "
       "tau 40 is shadowed, and when the ask falls to 97c at tau 38 pin's own "
       "early leg buys the market (%r, leg early, not a band buy); early_once "
       "refuses only AFTER that leg (at t %r, order at t %r)"
       % (_x9_3c, [_r["t"] for _r in _refusals(_x9_3, "early_once")],
          [_o["t"] for _o in _x9_3o]))
    ck(_x9_3n["raised"] is None and not _kinds(_x9_3n, "band99_shadow")
       and not _refusals(_x9_3n, "band99_early")
       and [_c[2] for _c in _x9_3nc] == [5.0]
       and len(_x9_3no) == 1 and _x9_3no[0].get("band99") is True
       and _x9_3no[0].get("leg") == "early" and _x9_3no[0].get("tau_at_send") == 40
       and len(_refusals(_x9_3n, "early_once")) == 1,
       "v-0925x band99late NULL: the flag off (the default) is today's band "
       "unchanged -- the same world buys the band at tau 40 as the market's "
       "early leg (%r, the only order) and every later early look is refused "
       "early_once, so the 97c ask at tau 38 is never bought (the slot the flag "
       "frees)" % (_x9_3nc,))
    _x9_4, _x9_4c = _x9_w(6, _x9_99, 33, _x9_30)
    _x9_4o = _kinds(_x9_4, "order")
    _x9_4s = _kinds(_x9_4, "band99_shadow")
    ck(_x9_4["raised"] is None and len(_x9_4s) == 1 and _x9_4s[0].get("tau") == 33
       and [_c[2] for _c in _x9_4c] == [5.0]
       and len(_x9_4o) == 1 and _x9_4o[0].get("band99") is True
       and _x9_4o[0].get("tau_at_send") == 30 and _x9_4o[0].get("leg") == "full"
       and len(_refusals(_x9_4, "band99_early")) == 1,
       "v-0925x band99late DRIVEN: a 99c offer from tau 33 waits (one shadow at "
       "tau 33) and is bought as the band at tau 30 -- the boundary is inside "
       "(orders %r at tau %r)"
       % (_x9_4c, [_o.get("tau_at_send") for _o in _x9_4o]))
    _x9_src = inspect.getsource(trade_loop)
    _x9_mn = inspect.getsource(main)
    ck(_x9_src.count("band99_too_early(") == 1
       and _x9_src.count('rec("band99_shadow"') == 1
       and _x9_src.index("_b99 = band99_why(price,") < _x9_src.index("band99_too_early(tau)")
       < _x9_src.index('rec("band99_shadow"') < _x9_src.index("_band99_now = True")
       < _x9_src.index('state["signals"] += 1')
       < _x9_src.index("attempts_tk[(close_s, tk)] = ")
       < _x9_src.index("take_n, _leg46 = staged_take(")
       and "BAND99_MAX_TAU" in _OFFLINE_PINNED_FLAGS and "BAND99_MAX_TAU" in _FLAG_GLOBALS
       and 'globals()["BAND99_MAX_TAU"] = int(a.band99_max_tau)' in _x9_mn
       and "--band99-max-tau needs --band99-ceiling" in _x9_mn
       and "band99_max_tau=BAND99_MAX_TAU," in _x9_mn,
       "v-0925x band99late by source: the wait is read once, where the band is "
       "decided -- after band99_why, above the signal counter, the attempt "
       "counters and the early leg's sizing -- the shadow is written there "
       "once; the flag ships off, is pinned in every offline world, watched by "
       "the give-back guard, needs the band and is named in the start record")
''')

_got = R.write(EXPECTED_PINRUN)
print("patched", PR, _got, "(checked: the reviewed %s)" % EXPECTED_PINRUN)
print("v-0925x: four review fixes, always on, no flag (clock, prebank, drain, connect), and one new flag, off when "
      "omitted: --band99-max-tau SECONDS (band99late; the deploy passes 30); run patch_0925x_ordercli.py on the same "
      "build for connect")
