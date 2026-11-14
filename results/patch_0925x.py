"""Apply v-0925x (build 0925x) to a COPY of the live pin build (C:\\kals-live-0925w: research\\pinrun.py code_sha
05a01fbb5ed2; ordercli.py 467782077a23 is patched by results\\patch_0925x_ordercli.py; pintake.py b3c7bb48abb5 is NOT
touched). Patches pinrun.py in place, CRLF preserved; every anchor must occur exactly once; refuses an already-patched
tree, a tree that is not 0925w, and any result whose sha is not EXPECTED_PINRUN (nothing is written then). Every
refusal is an explicit exit, not an assert, so `python -O` cannot skip one.
usage: python patch_0925x.py <build_dir>      (build_dir holds research\\pinrun.py)
Run BOTH patches on the build (either order): pinrun's v-0925x connect checks read the mark the ordercli patch adds.

FOUR CONFIRMED REVIEW DEFECTS (2026-11-13), the smallest fix for each. No new flag, no trading rule, threshold, size,
gate or hedge trigger moves; every message of the new self-test checks starts "v-0925x <item>".

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
"""
import hashlib
import os
import sys

BASE_PINRUN = "05a01fbb5ed2"
EXPECTED_PINRUN = "4f798c3df9ea"   # the reviewed result (the patch refuses to write anything else)


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
if "v-0925x" in R.s or "_pre_bank" in R.s or "drain_cleared" in R.s or "[connect phase: not sent]" in R.s:
    refuse("already patched (v-0925x is in it); nothing written")
if "INDEX_5HZ" not in R.s or "hedge5_shadow" not in R.s or "book_shape_wrap" not in R.s:
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

_got = R.write(EXPECTED_PINRUN)
print("patched", PR, _got, "(checked: the reviewed %s)" % EXPECTED_PINRUN)
print("v-0925x: four review fixes, always on, no new flag (clock, prebank, drain, connect); run "
      "patch_0925x_ordercli.py on the same build for connect")
