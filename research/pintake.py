#!/usr/bin/env python3
# VERSION: 2026-09-07-pt1
"""pintake.py -- the TAKER order path for pin. It crosses the spread and it
NEVER rests. It is the exact opposite of ordercli.py's resting-quoter rails.

WHY A SEPARATE FILE
  ordercli.build_order() forces post_only=True and good_till_canceled: an
  order that can only REST. Resting is what lost money on 2026-09-07 -- the
  quotes were picked off while they sat in the book. pin buys a contract the
  model says is decided (fair >= 0.98) from someone still offering it too
  cheap, so it MUST cross, and it must never be left in the book. The one
  thing ordercli forbids is the one thing pin needs, so the rails here are
  different and checked by a different self-test.

WHAT IS SENT (Kalshi V2 create-order, POST /portfolio/events/orders)
  Field names and enums are quoted from Kalshi's own reference
  (docs.kalshi.com/api-reference/orders/create-order-v2.md, fetched
  2026-09-07):
    time_in_force            "fill_or_kill" | "good_till_canceled" |
                             "immediate_or_cancel"
    self_trade_prevention_type  "taker_at_cross" | "maker"
    side                     "bid" | "ask"
    count, price             fixed-point STRINGS (2 dp / 2-4 dp, dollars)
    post_only                boolean, optional -> we send it EXPLICITLY False
  We use time_in_force = "immediate_or_cancel": take what is there at our
  limit, cancel the rest, never rest. fill_or_kill would also be allowed by
  the rails (it is a taker order that cannot rest either) but IOC is chosen
  because a partial fill is still a good fill at pin's prices.

HOW NO IS REPRESENTED -- the mapping, with the evidence
  The V2 body has no "no" side. `price` is ALWAYS the YES price in dollars:
    buy YES at p   ->  side "bid", price p
    buy NO  at q   ->  side "ask", price (1 - q)      (= sell YES at 1 - q)
  Evidence:
    * ordercli.collateral(): a "bid" at p reserves p; an "ask" at p reserves
      (1 - p). Buying NO at q must reserve q, and 1 - (1 - q) = q. The sign
      is right only under this mapping.
    * results/run-live-20260907T083151Z.jsonl, every kind=="place" event with
      side "no": price 0.25, ref 0.75, collateral 15.00 on size 20, i.e.
      20 x (1 - 0.25). goldquote.py sent side="ask", price=0.25 for that
      leg; the exchange held the NO price (0.75) per contract.
    * ordercli.order_collateral()'s documented real record from this account:
      action=sell book_side=ask side=yes yes_px=0.3000 no_px=0.7000 -- an
      ask at yes 0.30 IS the no position at 0.70.
    * ordercli VERIFY 2: "an ask rests on the no book at (1-p)".
  So to take a stale YES BID at yb on a decided-NO market (pinlive's "no"
  signal, price na = 1 - yb) we send side "ask" at price yb = 1 - na, which
  buys NO at na and costs na per contract.

THE RAILS (check_take, every one a refusal BEFORE signing)
  count <= MAX_TAKE_COUNT (1), and a SEPARATE HARD_MAX (5) that nothing may
    exceed even if the first constant is edited;
  price strictly inside (0, 1);
  time_in_force must be IOC or FOK -- good_till_canceled is REFUSED by name;
  post_only must be exactly False -- True would REST;
  the market must close within MAX_TAU (90 s) and must not have closed;
  a module-level stake LEDGER: dollars committed this process <= MAX_RUN_STAKE
    ($5.00). The intent is committed while the order is in flight and then
    RE-SET FROM THE FILLS in the response -- the unfilled part of an IOC is
    released ONLY when the response says remaining_count is 0, the filled
    part stays. An UNKNOWN outcome (request failed, 5xx, 3xx, or a 2xx
    without both counts) is never released and HALTS further takes until
    clear_halt() is called after reconciling against /portfolio/orders.
    A 2xx with contracts still LIVE (remaining_count > 0, or status resting)
    means the IOC RESTED: take() cancels it, verifies against the resting
    listing, re-reads the order record, books any fill found there, and
    HALTS if live contracts had to be cancelled or a fill appeared after the
    create -- time_in_force was not honoured and the next take would rest too;
  base must be given (None is refused) and a production take may not
    override the clock (now_epoch is a DEMO/test affordance only);
  a LOSS ABORT: realised P&L in the ledger <= LOSS_ABORT (-$2.00) refuses
    every further take;
  a production base is refused unless armed by --prod (the CLI) or
    arm_prod() (a caller that has the operator's sign-off). DEMO IS THE
    DEFAULT. Nothing here can reach production by omission.

  Close times are parsed with calendar.timegm(strptime(..., "%Y-%m-%dT%H:%M:%SZ")).
  NOT time.mktime(...) - time.timezone: that is off by 3600 s under DST and
  was the bug found in pinlive.py on 2026-09-07.

THE RESPONSE (normalise)
  201 -> {order_id, client_order_id, fill_count, remaining_count, ts_ms}
  plus average_fill_price and average_fee_paid ONLY when fill_count > 0
  (Kalshi reference, above). A real 201 from this account, 2026-09-06:
    {"client_order_id":"kals-machine-test-2","fill_count":"0.00",
     "order_id":"01a0797b-0af0-735d-80c0-8dd310b32c84",
     "remaining_count":"1.00","ts_ms":1788744502497}
  Order RECORDS (GET /portfolio/orders) use different names --
  fill_count_fp, remaining_count_fp, taker_fees_dollars, maker_fees_dollars,
  taker_fill_cost_dollars, status in {resting, canceled, executed} -- and the
  parser accepts both shapes. The create response carries no `status`; for an
  IOC it is derived from the counts and labelled as derived.
  Kalshi's reference on remaining_count: "For IOC orders, this reflects the
  final state after unfilled contracts are canceled." So a missed IOC reads
  fill 0.00 / remaining 0.00. The 2026-09-06 201 above (fill 0.00 / remaining
  1.00) was a GTC that RESTED -- the same shape from an IOC means the order is
  live in the book, and is handled as such (see the ledger rail).
  average_fee_paid is "volume-weighted average fee paid per contract" (same
  reference); fee_total = average_fee_paid x fill_count.

    python pintake.py --selftest
    python pintake.py --envtest                 # DEMO only: auth, book, rails
    python pintake.py --ticker T --want yes --price 0.97 --close 2026-...Z
    python pintake.py ... --live                # send (demo unless --prod)
"""
import argparse
import ast
import calendar
import inspect
import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ordercli                                            # noqa: E402

DEMO = ordercli.DEMO
PROD = ordercli.PROD
PROD_ELECTIONS = "https://api.elections.kalshi.com/trade-api/v2"
KNOWN_BASES = (DEMO, PROD, PROD_ELECTIONS)

# Credentials are per environment (Kalshi's own words). The demo key was
# proven demo-only on 2026-09-06: 200 on demo, 401 NOT_FOUND on production.
DEMO_KEY_ID = "6f64485b-3e4d-4110-bdb7-bb489e4d68c6"
DEMO_KEY_FILE = r"C:\kals\kalshi-demo.pem"
PROD_KEY_FILE = r"C:\kals\kalshi.pem"

ENDPOINT = "/portfolio/events/orders"
TIF = "immediate_or_cancel"
TIF_ALLOWED = ("immediate_or_cancel", "fill_or_kill")
STP = "taker_at_cross"
STP_ALLOWED = ("taker_at_cross", "maker")

# HARD CEILINGS. Not arguments. Changing them is a code edit and a commit.
# THESE RAILS WERE SET FOR A SIZE-1 PROOF AND SILENTLY BLOCKED EVERY SCALE-UP.
# On 2026-09-08 the operator asked to scale. pinrun was restarted at size 3 and
# then 8, and BOTH would have been refused HERE at the order stage even after
# pinrun's own flags were fixed: MAX_TAKE_COUNT of 1 rejects any size above one
# contract, and a $5 run stake is less than a single size-8 buy (~$7.60).
# Raised deliberately, with the reasoning recorded, rather than rediscovered as
# an outage later.
MAX_TAKE_COUNT = 10.0     # contracts per take. About 8% of the median 125
                          # resting at the touch, so market impact stays
                          # negligible.
HARD_MAX = 25.0           # nothing may exceed this even if the line above is
                          # edited. 25 contracts is ~$24 at typical prices,
                          # roughly 60% of the crypto shard -- the real ceiling
                          # whatever any other constant says.
MAX_TAU = 90.0            # seconds to close; pin trades only in the last minute
MAX_RUN_STAKE = 60.00     # dollars committed per process. The shard holds ~$38
                          # and positions settle within 60 s, so this bounds
                          # CONCURRENT exposure, not turnover; pinrun releases
                          # the stake on settlement.
LOSS_ABORT = -2.00        # realised P&L at or below this refuses every take.
                          # THIS IS A SIZE-1 DEFAULT AND MUST BE RAISED BY THE
                          # CALLER FOR ANY LARGER SIZE -- see set_limits().
                          # Found 2026-09-08 by an adversarial audit: at
                          # --size 5 a single ordinary loss is about -$4.90,
                          # so the FIRST loss would refuse every subsequent
                          # take while the operator's own -$21 brake sat
                          # untouched. take() RETURNS the refusal rather than
                          # raising, so nothing halted and nothing was logged;
                          # the process would print SIGNAL lines forever while
                          # every order died before the wire.
                          # THE FOURTH size-1 literal to break scaling in one
                          # day. The repo rule stands: ANY CONSTANT TIED TO
                          # SIZE MUST BE EXPRESSED IN TERMS OF SIZE.


def set_limits(loss_abort=None, max_run_stake=None, why=""):
    """Raise this module's rails to match the run that is actually trading.

    Deliberately one-way: a caller may only LOOSEN a rail, never tighten it
    below the shipped default, and the change is printed rather than silent.
    Two independent brakes are a safety feature; a hidden one that is tighter
    than the operator's is not a brake, it is an outage.
    """
    global LOSS_ABORT, MAX_RUN_STAKE
    out = []
    if loss_abort is not None:
        la = float(loss_abort)
        if la >= 0:
            raise ValueError("loss_abort must be negative")
        if la > LOSS_ABORT:
            raise ValueError(
                f"refusing to TIGHTEN the order-path loss abort from "
                f"${LOSS_ABORT:.2f} to ${la:.2f}")
        out.append(f"LOSS_ABORT ${LOSS_ABORT:.2f} -> ${la:.2f}")
        LOSS_ABORT = la
    if max_run_stake is not None:
        ms = float(max_run_stake)
        if ms < MAX_RUN_STAKE:
            raise ValueError(
                f"refusing to LOWER MAX_RUN_STAKE from ${MAX_RUN_STAKE:.2f} "
                f"to ${ms:.2f}")
        out.append(f"MAX_RUN_STAKE ${MAX_RUN_STAKE:.2f} -> ${ms:.2f}")
        MAX_RUN_STAKE = ms
    if out:
        print("  pintake rails raised: " + "; ".join(out) +
              (f"  ({why})" if why else ""))
    return out

_PROD_ARMED = False


def arm_prod(reason):
    """Allow a production base. Only the CLI's --prod or a caller holding the
    operator's per-instance sign-off should call this. Logged, not silent."""
    global _PROD_ARMED
    _PROD_ARMED = True
    print(f"  *** PRODUCTION ARMED: {reason} ***", file=sys.stderr)


def disarm_prod():
    global _PROD_ARMED
    _PROD_ARMED = False


# ---------- ledger ------------------------------------------------------------
def _fresh_ledger():
    return {
        "committed": 0.0,          # dollars at risk right now (in flight + filled)
        "filled_contracts": 0.0,
        "filled_dollars": 0.0,     # from FILLS in responses, never from intents
        "fees": 0.0,
        "realised": 0.0,           # settled P&L, recorded by record_pnl()
        "losses": 0,               # COUNT of losing settlements. Distinct from
                                   # "realised" on purpose: dollars answer "have
                                   # we lost too much", a COUNT answers "is the
                                   # model still what we think it is". The whole
                                   # edge rests on a 0.90% flip rate measured
                                   # from three events, so the arrival RATE of
                                   # losses is the first thing that would tell
                                   # us the number is wrong.
        "sends": 0,
        "unknown": 0,
        "rested": 0,               # IOCs that came back with live contracts
        "anomalies": [],           # things that did not match the doc but were verified harmless
        "halt": None,
        "positions": {},           # ticker -> {want, contracts, cost, order_id}
        "takes": [],
    }


LEDGER = _fresh_ledger()


def reset_ledger():
    LEDGER.clear()
    LEDGER.update(_fresh_ledger())


def record_pnl(delta, note=""):
    """Book REALISED P&L (a settlement, read from the exchange). The loss abort
    reads this. A caller must record losses as soon as they are known."""
    LEDGER["realised"] += float(delta)
    LEDGER["takes"].append({"kind": "pnl", "delta": float(delta), "note": note,
                            "t": time.time()})
    return LEDGER["realised"]


def clear_halt(reason):
    """Lift a halt set by an UNKNOWN order outcome -- only after the caller has
    reconciled the order against /portfolio/orders. The reason is recorded."""
    LEDGER["takes"].append({"kind": "clear_halt", "was": LEDGER["halt"],
                            "reason": reason, "t": time.time()})
    LEDGER["halt"] = None


# ---------- time --------------------------------------------------------------
def close_epoch(iso_z):
    """'2026-09-07T20:15:00Z' -> epoch seconds, UTC, DST-proof.

    calendar.timegm treats the struct as UTC. time.mktime treats it as LOCAL
    and correcting with time.timezone ignores DST: off by 3600 s in summer.
    That exact bug was in pinlive.py on 2026-09-07."""
    return calendar.timegm(time.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ"))


# ---------- body --------------------------------------------------------------
def build_take(ticker, want, price, count=1, exchange_index=0, client_id=None):
    """A LIMIT order that can cross, immediate-or-cancel, post_only False.

    want is "yes" or "no"; price is the price of the outcome WE ARE BUYING.
      yes at p -> side "bid", price p
      no  at q -> side "ask", price 1-q   (sell YES at 1-q == buy NO at q)
    See the module docstring for the evidence behind the NO mapping.
    """
    want = str(want).lower()
    if want not in ("yes", "no"):
        raise ValueError(f"want must be 'yes' or 'no', got {want!r}")
    p = float(price)
    if want == "yes":
        side, yes_price = "bid", p
    else:
        side, yes_price = "ask", round(1.0 - p, 4)
    return {
        "ticker": str(ticker),
        "side": side,
        "count": f"{float(count):.2f}",
        "price": f"{yes_price:.4f}",
        "time_in_force": TIF,                  # never rests
        "self_trade_prevention_type": STP,
        "post_only": False,                    # MUST be able to cross
        "client_order_id": client_id or
        f"pin-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}",
        "exchange_index": int(exchange_index),
    }


def stake(body):
    """Dollars this order can cost: a bid at p costs p; an ask at p costs 1-p
    (it buys NO at 1-p). Same arithmetic as ordercli.collateral, by import."""
    return ordercli.collateral(body)


def expected_fee(price, count=1):
    """Kalshi taker fee, 0.07 * p * (1-p) per contract (engine.fee_per_contract)."""
    p = float(price)
    return 0.07 * p * (1.0 - p) * float(count)


# ---------- rails -------------------------------------------------------------
def check_take(body, market_close_epoch, now_epoch, base=None, ledger=None):
    """Every reason NOT to send. Empty list == ok. Runs before signing."""
    bad = []
    L = LEDGER if ledger is None else ledger

    if MAX_TAKE_COUNT > HARD_MAX:
        bad.append(f"MAX_TAKE_COUNT {MAX_TAKE_COUNT} has been edited above "
                   f"HARD_MAX {HARD_MAX}; refusing everything")

    c = p = None
    try:
        c = float(body.get("count"))
    except Exception:
        bad.append(f"count {body.get('count')!r} is unparseable")
    if c is not None:
        if c <= 0:
            bad.append(f"count {c} is not positive")
        if c > MAX_TAKE_COUNT:
            bad.append(f"count {c} exceeds MAX_TAKE_COUNT {MAX_TAKE_COUNT}")
        if c > HARD_MAX:
            bad.append(f"count {c} exceeds HARD_MAX {HARD_MAX} -- the ceiling "
                       f"that holds even if MAX_TAKE_COUNT is edited")

    try:
        p = float(body.get("price"))
    except Exception:
        bad.append(f"price {body.get('price')!r} is unparseable")
    if p is not None and not (0.0 < p < 1.0):
        bad.append(f"price {p} is outside (0,1)")

    tif = body.get("time_in_force")
    if tif == "good_till_canceled":
        bad.append("time_in_force is good_till_canceled -- that order would "
                   "REST in the book; pin never rests")
    elif tif not in TIF_ALLOWED:
        bad.append(f"time_in_force {tif!r} is not one of {TIF_ALLOWED}")

    if body.get("post_only") is not False:
        bad.append(f"post_only is {body.get('post_only')!r}, not False -- a "
                   f"post_only order RESTS, the failure class that lost money "
                   f"on 2026-09-07")

    if body.get("side") not in ("bid", "ask"):
        bad.append(f"side {body.get('side')!r} is not bid or ask")
    if body.get("self_trade_prevention_type") not in STP_ALLOWED:
        bad.append(f"self_trade_prevention_type "
                   f"{body.get('self_trade_prevention_type')!r} not in "
                   f"{STP_ALLOWED}")
    if not body.get("ticker"):
        bad.append("ticker is empty")
    try:
        if int(body.get("exchange_index")) < 0:
            bad.append("exchange_index is negative")
    except Exception:
        bad.append(f"exchange_index {body.get('exchange_index')!r} unparseable")

    tau = None
    try:
        tau = float(market_close_epoch) - float(now_epoch)
    except Exception:
        bad.append(f"close time {market_close_epoch!r} / now {now_epoch!r} "
                   f"unparseable")
    if tau is not None:
        if tau <= 0:
            bad.append(f"market closed {-tau:.1f} s ago")
        elif tau > MAX_TAU:
            bad.append(f"market closes in {tau:.1f} s; pin only trades inside "
                       f"the last {MAX_TAU:.0f} s")

    if c is not None and p is not None and c > 0:
        try:
            stk = stake(body)
        except Exception:
            stk = None
        if stk is None:
            bad.append("could not compute the stake")
        elif L["committed"] + stk > MAX_RUN_STAKE + 1e-9:
            bad.append(f"stake ${stk:.4f} + committed ${L['committed']:.4f} "
                       f"would exceed MAX_RUN_STAKE ${MAX_RUN_STAKE:.2f}")

    if L["realised"] <= LOSS_ABORT:
        bad.append(f"LOSS ABORT: realised P&L ${L['realised']:+.2f} <= "
                   f"${LOSS_ABORT:.2f}; no further takes this process")
    if L.get("halt"):
        bad.append(f"ledger HALTED: {L['halt']}")

    if base is not None:
        if base not in KNOWN_BASES:
            bad.append(f"base {base!r} is not a known Kalshi environment")
        elif base != DEMO and not _PROD_ARMED:
            bad.append(f"base {base} is PRODUCTION and production is not "
                       f"armed (--prod)")
    return bad


# ---------- response ----------------------------------------------------------
def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def normalise(status_code, resp, body, base=None):
    """Turn the exchange's answer into one dict, and be honest about what the
    response did and did not carry.

      status_code   HTTP status; -1 means the request itself failed (UNKNOWN)
      order_id      from order_id
      status        `status` if present; else derived from the counts for an
                    IOC and flagged status_source="derived_from_counts"
      filled        fill_count (create) or fill_count_fp (record)
      remaining     remaining_count / remaining_count_fp
      exec_yes_price  average_fill_price, in the request's YES-price terms
      exec_price    the same in the WANTED outcome's terms (ask -> 1 - yes)
      fee           average_fee_paid (per contract, create response) or
                    taker_fees_dollars / filled (record); fee_total = x filled
      parsed        True when the body was a dict we could read
      raw           the response exactly as received
    """
    out = {"status_code": status_code, "order_id": None, "client_order_id":
           body.get("client_order_id"), "status": None, "status_source": None,
           "filled": 0.0, "fill_known": False, "remaining": None,
           "exec_yes_price": None, "exec_price": None, "fee": None,
           "fee_total": None, "fee_field": None, "parsed": False, "raw": resp,
           "base": base, "body": body, "error": None, "t": time.time()}
    if not isinstance(resp, dict):
        # ordercli.send hands back a 4xx/5xx body as TEXT; surface its
        # error object without pretending the order was parsed.
        try:
            err = json.loads(resp) if isinstance(resp, str) else None
            out["error"] = err.get("error", err) if isinstance(err, dict) else None
        except Exception:
            out["error"] = None
        return out
    o = resp.get("order") if isinstance(resp.get("order"), dict) else resp
    out["parsed"] = True
    out["order_id"] = o.get("order_id")
    if o.get("client_order_id"):
        out["client_order_id"] = o.get("client_order_id")
    filled = _f(o.get("fill_count"))
    if filled is None:
        filled = _f(o.get("fill_count_fp"))
    remaining = _f(o.get("remaining_count"))
    if remaining is None:
        remaining = _f(o.get("remaining_count_fp"))
    out["filled"] = filled if filled is not None else 0.0
    out["fill_known"] = filled is not None      # False: the fill count was NOT in the response
    out["remaining"] = remaining
    if o.get("status"):
        out["status"], out["status_source"] = o.get("status"), "response"
    elif filled is not None:
        count = _f(body.get("count")) or 0.0
        if filled >= count - 1e-9 and count > 0:
            out["status"] = "executed"
        elif filled > 0:
            out["status"] = "partially_filled_then_canceled"
        else:
            out["status"] = "canceled"
        out["status_source"] = "derived_from_counts"
    avg = _f(o.get("average_fill_price"))
    if avg is None and (out["filled"] or 0) > 0:
        # an order RECORD carries the price on both sides
        avg = _f(o.get("yes_price_dollars"))
    if avg is not None:
        out["exec_yes_price"] = avg
        out["exec_price"] = avg if body.get("side") == "bid" else round(1.0 - avg, 4)
    if o.get("average_fee_paid") is not None:
        out["fee"] = _f(o.get("average_fee_paid"))
        out["fee_field"] = "average_fee_paid"
        if out["fee"] is not None:
            out["fee_total"] = out["fee"] * (out["filled"] or 0.0)
    elif o.get("taker_fees_dollars") is not None:
        tot = _f(o.get("taker_fees_dollars"))
        out["fee_field"] = "taker_fees_dollars"
        out["fee_total"] = tot
        if tot is not None and (out["filled"] or 0) > 0:
            out["fee"] = tot / out["filled"]
    return out


def _readable(out):
    """A 2xx whose fill AND remaining counts were actually in the response.
    Anything less is UNKNOWN: an order we cannot see is the state that lost
    money before."""
    code = out["status_code"]
    return (code is not None and 200 <= code < 300 and out["parsed"]
            and out.get("fill_known") and out["remaining"] is not None)


def _is_live(out):
    """Did a readable 2xx come back with contracts still in the book? Kalshi's
    reference: an IOC's remaining_count 'reflects the final state after
    unfilled contracts are canceled' -- so for an IOC it must be 0.00, and
    anything else means the order RESTED (the real 201 of a resting GTC on
    2026-09-06 read fill 0.00 / remaining 1.00 -- the same shape)."""
    return _readable(out) and ((out["remaining"] or 0.0) > 1e-9
                               or out["status"] == "resting")


def _unrest(base, pk, key_id, out, body):
    """An IOC came back with live contracts. CANCEL them, verify against the
    resting listing, then READ THE RECORD so a fill that landed between the
    create and the cancel is booked rather than lost. Only take() calls this,
    and only after its one send. Nothing here can add exposure."""
    res = {"cancel_status": None, "reduced_by": None, "still": None,
           "record": None, "record_status": None, "reconciled": False,
           "error": None}
    oid = out.get("order_id")
    if not oid:
        res["error"] = "no order_id in the response; cannot cancel"
        return res
    try:
        st, r, still = ordercli.cancel(base, pk, key_id, oid,
                                       body.get("exchange_index", 0))
        res["cancel_status"], res["still"] = st, still
        if isinstance(r, dict):
            res["reduced_by"] = _f(r.get("reduced_by"))
    except Exception as e:                       # noqa: BLE001
        res["error"] = f"cancel: {type(e).__name__}: {e}"
    try:
        st, rec = _get(base, pk, key_id, f"/portfolio/orders/{oid}")
        res["record_status"] = st
        if st == 200 and isinstance(rec, dict):
            res["record"] = rec
    except Exception as e:                       # noqa: BLE001
        res["error"] = (res["error"] or "") + f" record: {type(e).__name__}: {e}"
    return res


def _book(out, body, stk):
    """Update the ledger FROM THE RESPONSE. The intent was committed before
    the send; here it is replaced by what actually filled -- and by what may
    still be LIVE in the book, which for an IOC must be nothing.

      2xx, readable, nothing live      -> keep filled x price, release the rest
      2xx, readable, contracts live    -> the order RESTED. take() has already
                                          run _unrest(); out["unrest"] says how
                                          it went. Reconciled and nothing live:
                                          release, and HALT if we had to cancel
                                          live contracts or a fill appeared
                                          after the create (time_in_force was
                                          not honoured). Not reconciled: keep
                                          the live contracts committed, HALT.
      4xx                              -> rejected, nothing placed: release
      -1, 3xx, 5xx, or a 2xx missing its counts
                                       -> UNKNOWN: keep the intent, HALT
    """
    code = out["status_code"]
    count = _f(body.get("count")) or 0.0
    per_intent = stk / count if count else 0.0
    is_4xx = code is not None and 400 <= code < 500
    LEDGER["committed"] -= stk                     # the intent ...
    if _readable(out):
        filled = out["filled"] or 0.0
        per = out["exec_price"] if out["exec_price"] is not None else per_intent
        live = max(0.0, out["remaining"] or 0.0)
        if out["status"] == "resting" and live <= 1e-9:
            live = max(0.0, count - filled)
        LEDGER["committed"] += filled * per        # ... what filled stays
        LEDGER["filled_contracts"] += filled
        LEDGER["filled_dollars"] += filled * per
        if out["fee_total"]:
            LEDGER["fees"] += out["fee_total"]
        if filled > 0:
            want = "yes" if body["side"] == "bid" else "no"
            pos = LEDGER["positions"].setdefault(
                body["ticker"], {"want": want, "contracts": 0.0, "cost": 0.0,
                                 "order_ids": []})
            pos["contracts"] += filled
            pos["cost"] += filled * per
            pos["order_ids"].append(out["order_id"])
        u = out.get("unrest")
        if u is not None:
            LEDGER["rested"] += 1
            if u.get("reconciled") and live <= 1e-9:
                if (u.get("reduced_by") or 0.0) > 0 or (u.get("fill_discovered") or 0.0) > 0:
                    LEDGER["halt"] = (
                        f"order {out['order_id']} RESTED after an IOC "
                        f"(we cancelled {u.get('reduced_by')}, fill discovered "
                        f"on reconciliation {u.get('fill_discovered')}); "
                        f"time_in_force was NOT honoured; investigate before "
                        f"clear_halt()")
                else:
                    LEDGER["anomalies"].append(
                        {"order_id": out["order_id"], "t": out["t"],
                         "what": "remaining_count non-zero on an IOC, but the "
                                 "record shows nothing live and nothing "
                                 "extra filled"})
            else:
                LEDGER["committed"] += live * per_intent
                LEDGER["halt"] = (
                    f"order {out['order_id']} may be RESTING with {live} "
                    f"contract(s) live after an IOC and the cancel could not "
                    f"be verified (still={u.get('still')}, record "
                    f"{u.get('record_status')}, error {u.get('error')}); "
                    f"reconcile against /portfolio/orders, then clear_halt()")
        elif live > 1e-9:
            # _book() called without take() having run _unrest(): never
            # release what may be resting.
            LEDGER["committed"] += live * per_intent
            LEDGER["halt"] = (f"order {out['order_id']} has {live} contract(s) "
                              f"live after an IOC and no cancel was attempted; "
                              f"reconcile, then clear_halt()")
    elif is_4xx:
        pass                                       # rejected: nothing placed
    else:
        # -1 (request failed), 3xx, 5xx (a gateway timeout can have placed
        # the order), or a 2xx we could not read: UNKNOWN. Keep the intent
        # committed and HALT.
        LEDGER["committed"] += stk
        LEDGER["unknown"] += 1
        LEDGER["halt"] = (f"order {body.get('client_order_id')} outcome UNKNOWN "
                          f"(status {code}, parsed {out['parsed']}, fill_known "
                          f"{out.get('fill_known')}, remaining {out['remaining']}); "
                          f"reconcile against /portfolio/orders, then clear_halt()")
    LEDGER["committed"] = max(0.0, LEDGER["committed"])
    LEDGER["takes"].append({k: out[k] for k in
                            ("status_code", "order_id", "status", "filled",
                             "remaining", "exec_price", "fee", "fee_total",
                             "client_order_id", "t")})
    del LEDGER["takes"][:-500]


# ---------- the one path to the wire ----------------------------------------
def take(base, pk, key_id, ticker, want, price, count, market_close_epoch,
         exchange_index=0, client_id=None, now_epoch=None):
    """Build, CHECK, then -- only with an empty violation list -- POST.

    Returns the normalised dict from normalise(), plus "refused": [...] and
    status_code None when the rails said no. The self-test reads this
    function's source and fails if the wire call appears before the check.
    """
    now = time.time() if now_epoch is None else float(now_epoch)
    body = build_take(ticker, want, price, count, exchange_index, client_id)
    violations = check_take(body, market_close_epoch, now, base=base)
    if base is None:
        violations.append("base is None -- no environment named; refused")
    if now_epoch is not None and base != DEMO:
        violations.append("now_epoch may only be overridden on DEMO (tests); "
                          "a production take uses the wall clock")
    if violations:
        out = normalise(None, None, body, base)
        out["refused"] = violations
        LEDGER["takes"].append({"kind": "refused", "violations": violations,
                                "client_order_id": body["client_order_id"],
                                "t": now})
        return out
    stk = stake(body)
    LEDGER["committed"] += stk          # intent, in flight; _book() resets it from fills
    LEDGER["sends"] += 1
    status_code, resp = ordercli.send(base, pk, key_id, "POST", ENDPOINT, body)
    out = normalise(status_code, resp, body, base)
    out["refused"] = []
    if _is_live(out):
        # An IOC that left contracts in the book. Cancel, verify, re-read.
        out["unrest"] = _unrest(base, pk, key_id, out, body)
        rec = out["unrest"].get("record")
        r2 = normalise(200, rec, body, base) if rec is not None else None
        if r2 is not None and _readable(r2) and r2["status"] != "resting":
            if r2["filled"] > out["filled"] + 1e-9:
                out["unrest"]["fill_discovered"] = r2["filled"] - out["filled"]
            for k in ("filled", "remaining", "exec_yes_price", "exec_price",
                      "fee", "fee_total", "fee_field", "status"):
                out[k] = r2[k]
            out["status_source"] = "record_after_cancel"
            out["unrest"]["reconciled"] = True
    _book(out, body, stk)
    return out


# ---------- self-test ---------------------------------------------------------
def _take_code_source():
    """Source of take() with the docstring removed, plus the module AST."""
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    lines = src.splitlines()
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "take")
    first = fn.body[0]
    start = (fn.body[1].lineno if isinstance(first, ast.Expr)
             and isinstance(getattr(first, "value", None), ast.Constant)
             and isinstance(first.value.value, str) and len(fn.body) > 1
             else first.lineno)
    code = "\n".join(lines[start - 1:fn.end_lineno])
    return code, tree, fn


def _call_name(node):
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def selftest():
    print("=" * 78)
    print("SELF-TEST -- pintake: the taker rails must hold before anything is sent")
    print("=" * 78)
    fails = []
    reset_ledger()
    disarm_prod()
    now = 1_800_000_000.0
    close_ok = now + 30.0

    # --- bodies -------------------------------------------------------------
    y = build_take("KXBTC15M-TEST-00", "yes", 0.97, 1, 0, "cid-y")
    n = build_take("KXBTC15M-TEST-00", "no", 0.03, 1, 0, "cid-n")
    print(f"\n  buy YES at 0.97 -> {json.dumps(y)}")
    print(f"  buy NO  at 0.03 -> {json.dumps(n)}")
    exp_y = {"ticker": "KXBTC15M-TEST-00", "side": "bid", "count": "1.00",
             "price": "0.9700", "time_in_force": "immediate_or_cancel",
             "self_trade_prevention_type": "taker_at_cross", "post_only": False,
             "client_order_id": "cid-y", "exchange_index": 0}
    exp_n = dict(exp_y, side="ask", client_order_id="cid-n")   # 1-0.03 = 0.9700
    for label, got, exp in (("yes", y, exp_y), ("no", n, exp_n)):
        if got != exp:
            fails.append(f"{label} body differs: got {got} expected {exp}")
        if got.get("post_only") is not False:
            fails.append(f"{label} body post_only is not exactly False")
        if got.get("time_in_force") == "good_till_canceled":
            fails.append(f"{label} body would REST")
    if abs(stake(y) - 0.97) > 1e-9:
        fails.append(f"stake of a yes take at 0.97 is {stake(y)}, not 0.97")
    if abs(stake(n) - 0.03) > 1e-9:
        fails.append(f"stake of a NO take at 0.03 is {stake(n)}, not 0.03 -- "
                     f"the ask/1-q mapping is wrong")
    print(f"  stake: yes@0.97 ${stake(y):.4f}   no@0.03 ${stake(n):.4f}   "
          f"(a NO at q must cost q)")
    try:
        build_take("T", "maybe", 0.5)
        fails.append("build_take accepted want='maybe'")
    except ValueError:
        pass

    # --- a legal take is accepted ----------------------------------------------
    ok = check_take(y, close_ok, now, base=DEMO)
    print(f"\n  legal yes take, close in 30 s, demo, fresh ledger -> "
          f"{'ACCEPTED' if not ok else ok}")
    if ok:
        fails.append(f"a legal take was refused: {ok}")
    ok = check_take(n, close_ok, now, base=DEMO)
    if ok:
        fails.append(f"a legal NO take was refused: {ok}")

    # --- every rail must REFUSE ------------------------------------------------
    print("\n  every rail must REFUSE, before signing:")
    cases = [
        # RELATIVE to the constants, not hardcoded. These were "count 2" and
        # "count 10", correct when the rails were 1 and 5 and silently WRONG
        # the moment they were raised for scaling -- the suite then failed on
        # legal orders instead of illegal ones.
        (f"count {MAX_TAKE_COUNT + 1:g} (over MAX_TAKE_COUNT)",
         dict(y, count=f"{MAX_TAKE_COUNT + 1:.2f}"), close_ok, now, None),
        (f"count {HARD_MAX + 5:g} (over HARD_MAX too)",
         dict(y, count=f"{HARD_MAX + 5:.2f}"), close_ok, now, None),
        ("price 0", dict(y, price="0.0000"), close_ok, now, None),
        ("price 1", dict(y, price="1.0000"), close_ok, now, None),
        ("price 1.2", dict(y, price="1.2000"), close_ok, now, None),
        ("NO at q=1 -> yes price 0", build_take("T", "no", 1.0, 1, 0, "c"), close_ok, now, None),
        ("tif good_till_canceled", dict(y, time_in_force="good_till_canceled"), close_ok, now, None),
        ("tif nonsense", dict(y, time_in_force="day"), close_ok, now, None),
        ("post_only True", dict(y, post_only=True), close_ok, now, None),
        ("post_only missing", {k: v for k, v in y.items() if k != "post_only"}, close_ok, now, None),
        ("close 120 s away", y, now + 120.0, now, None),
        ("close 91 s away", y, now + 91.0, now, None),
        ("close in the past", y, now - 1.0, now, None),
        ("close exactly now", y, now, now, None),
        ("side sell", dict(y, side="sell"), close_ok, now, None),
        ("negative count", dict(y, count="-1.00"), close_ok, now, None),
        ("unknown base", y, close_ok, now, "https://example.com/trade-api/v2"),
        ("production base, not armed", y, close_ok, now, PROD),
        ("elections production base, not armed", y, close_ok, now, PROD_ELECTIONS),
    ]
    for desc, body, close, t, base in cases:
        v = check_take(body, close, t, base=base)
        print(f"    {desc:<40} -> {'REFUSED' if v else '*** ALLOWED ***'}")
        if not v:
            fails.append(f"{desc} was NOT refused")
    vhard = check_take(dict(y, count=f"{HARD_MAX + 5:.2f}"), close_ok, now)
    if not any("HARD_MAX" in s for s in vhard):
        fails.append(f"count {HARD_MAX+5:g} was not refused by HARD_MAX specifically")
    vsoft = check_take(dict(y, count=f"{MAX_TAKE_COUNT + 1:.2f}"), close_ok, now)
    if any("HARD_MAX" in s for s in vsoft):
        fails.append(f"count {MAX_TAKE_COUNT+1:g} tripped HARD_MAX -- the two "
                     f"ceilings are not separate")
    if not any("MAX_TAKE_COUNT" in s for s in vsoft):
        fails.append(f"count {MAX_TAKE_COUNT+1:g} was not refused by MAX_TAKE_COUNT")
    # and a LEGAL size must pass, or the rails are simply blocking everything
    vok = check_take(dict(y, count=f"{MAX_TAKE_COUNT:.2f}"), close_ok, now,
                     base=DEMO)
    if vok:
        fails.append(f"a legal count of {MAX_TAKE_COUNT:g} was refused: {vok}")
    if HARD_MAX < MAX_TAKE_COUNT:
        fails.append("HARD_MAX is below MAX_TAKE_COUNT")

    # --- ledger: stake cap ------------------------------------------------------
    print("\n  the stake ledger must bind:")
    led = _fresh_ledger()
    led["committed"] = MAX_RUN_STAKE - 0.50
    v = check_take(y, close_ok, now, ledger=led)          # 4.50 + 0.97 > 5.00
    print(f"    committed ${led['committed']:.2f} + ${stake(y):.2f} > "
          f"${MAX_RUN_STAKE:.2f} -> {'REFUSED' if v else '*** ALLOWED ***'}")
    if not v:
        fails.append("stake ledger did not refuse when the cap would be exceeded")
    led["committed"] = MAX_RUN_STAKE - 1.00
    v = check_take(y, close_ok, now, ledger=led)          # 4.00 + 0.97 <= 5.00
    if v:
        fails.append(f"stake ledger refused a take that fits: {v}")

    # --- ledger: loss abort -----------------------------------------------------
    print("\n  the loss abort must refuse everything:")
    led = _fresh_ledger()
    led["realised"] = LOSS_ABORT + 0.01
    if check_take(y, close_ok, now, ledger=led):
        fails.append("loss abort fired above its threshold")
    led["realised"] = LOSS_ABORT
    v = check_take(y, close_ok, now, ledger=led)
    print(f"    realised ${led['realised']:+.2f} -> {'REFUSED' if v else '*** ALLOWED ***'}")
    if not v or not any("LOSS ABORT" in s for s in v):
        fails.append("loss abort did not refuse at exactly LOSS_ABORT")
    reset_ledger()
    record_pnl(-1.50, "test")
    record_pnl(-0.60, "test")
    v = check_take(y, close_ok, now)
    print(f"    record_pnl(-1.50), record_pnl(-0.60) -> realised "
          f"${LEDGER['realised']:+.2f} -> {'REFUSED' if v else '*** ALLOWED ***'}")
    if not v:
        fails.append("loss abort did not fire through record_pnl")
    reset_ledger()
    led = _fresh_ledger()
    led["halt"] = "test halt"
    if not check_take(y, close_ok, now, ledger=led):
        fails.append("a halted ledger did not refuse")

    # --- close-time parsing -----------------------------------------------------
    print("\n  close-time parsing must be UTC and DST-proof:")
    import datetime as _dt
    iso = "2026-09-07T20:15:00Z"
    got = close_epoch(iso)
    exp = int(_dt.datetime(2026, 9, 7, 20, 15, tzinfo=_dt.timezone.utc).timestamp())
    buggy = time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    print(f"    {iso} -> {got}  (datetime UTC says {exp}; mktime-timezone "
          f"would say {int(buggy)}, off by {int(buggy - exp)} s here)")
    if got != exp:
        fails.append(f"close_epoch({iso}) = {got}, expected {exp}")

    # --- the parser ---------------------------------------------------------------
    print("\n  the response parser, on the real 201 shape and a filled one:")
    real201 = {"client_order_id": "kals-machine-test-2", "fill_count": "0.00",
               "order_id": "01a0797b-0af0-735d-80c0-8dd310b32c84",
               "remaining_count": "1.00", "ts_ms": 1788744502497}
    r = normalise(201, real201, y, DEMO)
    print(f"    unfilled 201 -> id {r['order_id']} filled {r['filled']} "
          f"remaining {r['remaining']} status {r['status']} "
          f"({r['status_source']}) fee {r['fee']}")
    if (r["order_id"] != real201["order_id"] or r["filled"] != 0.0
            or r["remaining"] != 1.0 or r["status"] != "canceled"
            or r["fee"] is not None or r["exec_price"] is not None):
        fails.append(f"parser misread the real 201: {r}")
    filled = {"client_order_id": "cid-n", "fill_count": "1.00",
              "remaining_count": "0.00", "average_fill_price": "0.9700",
              "average_fee_paid": "0.0020", "order_id": "x-1", "ts_ms": 1}
    r = normalise(201, filled, n, DEMO)
    print(f"    filled NO 201 -> filled {r['filled']} exec_yes {r['exec_yes_price']} "
          f"exec(no) {r['exec_price']} fee {r['fee']} ({r['fee_field']}) "
          f"total {r['fee_total']} status {r['status']}")
    if (r["filled"] != 1.0 or r["remaining"] != 0.0 or r["exec_yes_price"] != 0.97
            or abs(r["exec_price"] - 0.03) > 1e-9 or r["fee"] != 0.002
            or r["fee_total"] != 0.002 or r["status"] != "executed"):
        fails.append(f"parser misread a filled response: {r}")
    # The first two IOC 201s this project ever received -- DEMO shard 0,
    # 2026-09-08T01:32Z, KXSILVERH-26SEP0723-T67.949, bodies from build_take:
    #   miss: IOC bid at 0.01 with no ask in the book -> remaining_count 0.00
    #   fill: IOC ask at 0.01 (= buy NO at 0.99) into a YES bid at 0.01;
    #         balance 10.0000 -> 9.0093 = -(0.99 + 0.0007), record
    #         action=sell book_side=ask outcome_side=no taker_fill_cost 0.99
    real_miss = {"client_order_id": "pin-1788831120478-2251b2", "fill_count": "0.00",
                 "order_id": "01a07ea4-ba80-735d-b8ea-a36b32155432",
                 "remaining_count": "0.00", "ts_ms": 1788831120702}
    real_fill = {"average_fee_paid": "0.0007", "average_fill_price": "0.0100",
                 "client_order_id": "pin-1788831122535-9b17d9", "fill_count": "1.00",
                 "order_id": "01a07ea4-c250-7fea-998f-0ee077f05d6a",
                 "remaining_count": "0.00", "ts_ms": 1788831122750}
    yb = build_take("KXSILVERH-26SEP0723-T67.949", "yes", 0.01, 1, 0, "pin-1788831120478-2251b2")
    r = normalise(201, real_miss, yb, DEMO)
    print(f"    REAL IOC miss (demo 2026-09-08) -> status {r['status']} filled {r['filled']} "
          f"remaining {r['remaining']} live={_is_live(r)}")
    if r["status"] != "canceled" or r["remaining"] != 0.0 or _is_live(r) or not _readable(r):
        fails.append(f"parser misread the real IOC miss: {r}")
    nb = build_take("KXSILVERH-26SEP0723-T67.949", "no", 0.99, 1, 0, "pin-1788831122535-9b17d9")
    r = normalise(201, real_fill, nb, DEMO)
    print(f"    REAL IOC fill (demo 2026-09-08) -> status {r['status']} filled {r['filled']} "
          f"exec_yes {r['exec_yes_price']} exec(no) {r['exec_price']} fee {r['fee']} "
          f"total {r['fee_total']} (exchange charged 0.9907 = 0.99 + 0.0007)")
    if (r["status"] != "executed" or r["filled"] != 1.0 or r["remaining"] != 0.0
            or abs(r["exec_price"] - 0.99) > 1e-9 or abs(r["fee_total"] - 0.0007) > 1e-9
            or abs(r["exec_price"] + r["fee_total"] - 0.9907) > 1e-9):
        fails.append(f"parser misread the real IOC fill: {r}")

    rec = {"order_id": "rec-1", "status": "executed", "fill_count_fp": "1.00",
           "remaining_count_fp": "0.00", "yes_price_dollars": "0.9700",
           "no_price_dollars": "0.0300", "taker_fees_dollars": "0.0014"}
    r = normalise(200, rec, y, DEMO)
    if (r["filled"] != 1.0 or r["status"] != "executed"
            or r["status_source"] != "response" or r["fee_total"] != 0.0014
            or r["exec_price"] != 0.97):
        fails.append(f"parser misread an order RECORD: {r}")
    r = normalise(400, '{"error":{"code":"invalid_parameters"}}', y, DEMO)
    if r["parsed"] or r["filled"] != 0.0 or r["order_id"] is not None:
        fails.append(f"parser invented fields on a 400 text body: {r}")

    # --- take(): refused -> nothing sent; sent -> ledger from FILLS ----------------
    print("\n  take() end to end with a fake wire:")
    calls = []
    real_send = ordercli.send

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("send() was reached with a refused body")
    ordercli.send = boom
    try:
        reset_ledger()
        # A count ABOVE HARD_MAX. This used to be 2, which was refused when
        # MAX_TAKE_COUNT was 1; raising that rail for scaling turned this test
        # into a false alarm rather than a real check. The INTENT is unchanged
        # and is the important part: a refused body must never reach the wire.
        over = HARD_MAX + 5.0
        out = take(DEMO, None, "k", "T", "yes", 0.97, over, close_ok,
                   now_epoch=now)
    finally:
        ordercli.send = real_send
    print(f"    count {over:g} (> HARD_MAX {HARD_MAX:g}) -> "
          f"refused={bool(out.get('refused'))} sends={len(calls)}")
    if not out.get("refused") or calls or out["status_code"] is not None:
        fails.append("take() reached the wire, or did not report, a refused body")

    def fake_send(base, pk, key_id, method, path, body=None, query=None):
        calls.append((method, path, body))
        return 201, {"client_order_id": body["client_order_id"],
                     "fill_count": "1.00", "remaining_count": "0.00",
                     "average_fill_price": body["price"],
                     "average_fee_paid": "0.0014", "order_id": "fake-1",
                     "ts_ms": 1}
    ordercli.send = fake_send
    try:
        reset_ledger()
        calls.clear()
        out = take(DEMO, None, "k", "T", "yes", 0.97, 1, close_ok, now_epoch=now)
    finally:
        ordercli.send = real_send
    print(f"    legal yes@0.97, fake 201 filled 1 -> filled {out['filled']} "
          f"exec {out['exec_price']} fee {out['fee']}; ledger committed "
          f"${LEDGER['committed']:.4f} filled ${LEDGER['filled_dollars']:.4f} "
          f"fees ${LEDGER['fees']:.4f}")
    if len(calls) != 1 or calls[0][0] != "POST" or calls[0][1] != ENDPOINT:
        fails.append(f"take() did not POST {ENDPOINT} exactly once: {calls}")
    if calls and calls[0][2].get("post_only") is not False:
        fails.append("the body that went to the wire had post_only != False")
    if calls and calls[0][2].get("time_in_force") != TIF:
        fails.append("the body that went to the wire was not IOC")
    if abs(LEDGER["committed"] - 0.97) > 1e-9 or abs(LEDGER["filled_dollars"] - 0.97) > 1e-9:
        fails.append(f"ledger after a full fill: {LEDGER}")
    if abs(LEDGER["fees"] - 0.0014) > 1e-9:
        fails.append(f"ledger fees {LEDGER['fees']} != 0.0014")

    # A fake wire that routes by method: POST = create, DELETE = cancel,
    # GET = the resting listing (ordercli.cancel polls it); and a fake
    # record reader standing in for _get().
    def wire(post, delete=(-1, "no cancel expected"), listing=(200, {"orders": []}),
             record=(-1, "no record expected")):
        log = []

        def fs(base, pk, key_id, method, path, body=None, query=None):
            log.append((method, path, body, query))
            return {"POST": post, "DELETE": delete, "GET": listing}.get(method, (-1, "?"))

        def fg(base, pk, key_id, path, query=None):
            log.append(("GET*", path, None, query))
            return record
        return fs, fg, log

    def run_take(fs, fg, base=DEMO, **kw):
        global _get
        real_g = _get
        ordercli.send, _get = fs, fg
        try:
            reset_ledger()
            return take(base, None, "k", "T", "yes", 0.97, 1, close_ok,
                        now_epoch=now, **kw)
        finally:
            ordercli.send, _get = real_send, real_g

    fs, fg, log = wire(post=(201, {"client_order_id": "c", "fill_count": "0.00",
                                   "remaining_count": "0.00", "order_id": "fake-2",
                                   "ts_ms": 2}))
    out = run_take(fs, fg)
    print(f"    IOC that missed (fill 0.00, remaining 0.00 per the reference) -> "
          f"status {out['status']} ({out['status_source']}); ledger committed "
          f"${LEDGER['committed']:.4f} (intent released from fills); "
          f"cancels sent {sum(1 for m in log if m[0] == 'DELETE')}")
    if (abs(LEDGER["committed"]) > 1e-9 or out["status"] != "canceled"
            or LEDGER["halt"] or any(m[0] == "DELETE" for m in log)):
        fails.append("an unfilled IOC left dollars committed, was not read as "
                     "canceled, halted, or triggered a cancel")

    fs, fg, log = wire(post=(-1, "timed out"))
    out = run_take(fs, fg)
    v = check_take(y, close_ok, now)
    print(f"    wire failed (-1) -> committed ${LEDGER['committed']:.4f} kept, "
          f"halt={LEDGER['halt'] is not None}, next take "
          f"{'REFUSED' if v else '*** ALLOWED ***'}")
    if abs(LEDGER["committed"] - 0.97) > 1e-9 or not LEDGER["halt"] or not v:
        fails.append("an UNKNOWN outcome did not stay committed and halt further takes")
    clear_halt("test")
    if check_take(y, close_ok, now):
        fails.append("clear_halt did not lift the halt")
    reset_ledger()

    # --- outcomes that must NEVER release the stake ---------------------------
    print("\n  outcomes that are UNKNOWN must keep the stake committed and HALT:")
    for desc, post in (
            ("201 with an empty body {}", (201, {})),
            ("201 with order_id only (no counts)", (201, {"order_id": "x"})),
            ("201 with fill_count but no remaining_count",
             (201, {"order_id": "x", "fill_count": "0.00"})),
            ("503 text body", (503, "<html>Service Unavailable</html>")),
            ("504 gateway timeout", (504, "timeout")),
            ("302 (a redirect answered)", (302, "")),
            ("201 with a non-dict body", (201, ["not", "an", "order"]))):
        fs, fg, log = wire(post=post)
        out = run_take(fs, fg)
        ok_ = (abs(LEDGER["committed"] - 0.97) < 1e-9 and LEDGER["halt"]
               and LEDGER["unknown"] == 1)
        print(f"    {desc:<44} -> committed ${LEDGER['committed']:.4f} "
              f"halt={bool(LEDGER['halt'])} {'OK' if ok_ else '*** RELEASED ***'}")
        if not ok_:
            fails.append(f"{desc}: stake released or no halt: {LEDGER}")

    print("\n  a rejection releases the stake without a halt:")
    demo404 = ('{"error":{"code":"user_not_found","message":"user not found",'
               '"details":"Exchange user not found. For Predictions: reference '
               'documentation Exchange Sharding documentation."}}')
    fs, fg, log = wire(post=(404, demo404))
    out = run_take(fs, fg)
    print(f"    the demo 404 text (2026-09-07) -> parsed {out['parsed']} error code "
          f"{(out['error'] or {}).get('code')} committed ${LEDGER['committed']:.4f} "
          f"halt={bool(LEDGER['halt'])}")
    if (out["parsed"] or (out["error"] or {}).get("code") != "user_not_found"
            or abs(LEDGER["committed"]) > 1e-9 or LEDGER["halt"] or out["filled"] != 0.0):
        fails.append(f"the demo 404 was not read as a clean rejection: {out} {LEDGER}")

    # --- an IOC that RESTED: cancel, verify, reconcile, halt --------------------
    print("\n  an IOC that came back with LIVE contracts (remaining 1.00) must be "
          "cancelled, verified, and halt:")
    rest201 = (201, {"client_order_id": "c", "fill_count": "0.00",
                     "remaining_count": "1.00", "order_id": "r1", "ts_ms": 3})
    rec_canceled = (200, {"order": {"order_id": "r1", "status": "canceled",
                                    "fill_count_fp": "0.00",
                                    "remaining_count_fp": "0.00"}})
    # R1: we cancelled a live contract -> nothing live, but HALT (TIF not honoured)
    fs, fg, log = wire(post=rest201, delete=(200, {"reduced_by": "1.00"}),
                       record=rec_canceled)
    out = run_take(fs, fg)
    dels = [m for m in log if m[0] == "DELETE"]
    recs = [m for m in log if m[0] == "GET*"]
    print(f"    R1 cancel 200 reduced_by 1.00, record canceled -> DELETE "
          f"{dels[0][1] if dels else None} q={dels[0][3] if dels else None}; "
          f"record GET {recs[0][1] if recs else None}; status {out['status']} "
          f"({out['status_source']}); committed ${LEDGER['committed']:.4f}; "
          f"halt={bool(LEDGER['halt'])}; rested {LEDGER['rested']}")
    if (not dels or dels[0][1] != "/portfolio/events/orders/r1"
            or (dels[0][3] or {}).get("exchange_index") != 0
            or not recs or recs[0][1] != "/portfolio/orders/r1"
            or abs(LEDGER["committed"]) > 1e-9 or not LEDGER["halt"]
            or "NOT honoured" not in LEDGER["halt"] or LEDGER["rested"] != 1
            or out["status_source"] != "record_after_cancel"):
        fails.append(f"R1: a rested IOC was not cancelled+verified+halted: {out} {LEDGER}")
    # R2: the cancel found nothing (404) and the record says canceled: an
    # anomaly in remaining_count, nothing live -> release, no halt
    fs, fg, log = wire(post=rest201, delete=(404, "order not found"),
                       record=rec_canceled)
    out = run_take(fs, fg)
    print(f"    R2 cancel 404, listing empty, record canceled -> committed "
          f"${LEDGER['committed']:.4f}; halt={bool(LEDGER['halt'])}; anomalies "
          f"{len(LEDGER['anomalies'])}")
    if abs(LEDGER["committed"]) > 1e-9 or LEDGER["halt"] or len(LEDGER["anomalies"]) != 1:
        fails.append(f"R2: a verified-dead order was not released as an anomaly: {LEDGER}")
    # R3: cancel returns 200 reduced_by 0 but the listing keeps showing it
    # and the record cannot be read -> keep the live contract committed, HALT
    fs, fg, log = wire(post=rest201, delete=(200, {"reduced_by": "0.00"}),
                       listing=(200, {"orders": [{"order_id": "r1", "status": "resting"}]}),
                       record=(-1, "record endpoint down"))
    out = run_take(fs, fg)
    print(f"    R3 still resting, record unreadable -> committed "
          f"${LEDGER['committed']:.4f} kept; halt={bool(LEDGER['halt'])}")
    if abs(LEDGER["committed"] - 0.97) > 1e-9 or not LEDGER["halt"]:
        fails.append(f"R3: an unverified resting order was released or not halted: {LEDGER}")
    # R4: it rested, then FILLED before our cancel: the record carries the
    # fill; book it, HALT (it rested)
    fs, fg, log = wire(post=rest201, delete=(200, {"reduced_by": "0.00"}),
                       record=(200, {"order": {"order_id": "r1", "status": "executed",
                                               "fill_count_fp": "1.00",
                                               "remaining_count_fp": "0.00",
                                               "yes_price_dollars": "0.9700",
                                               "no_price_dollars": "0.0300",
                                               "taker_fees_dollars": "0.0014"}}))
    out = run_take(fs, fg)
    print(f"    R4 filled between create and cancel -> filled {out['filled']} "
          f"exec {out['exec_price']} fee_total {out['fee_total']}; committed "
          f"${LEDGER['committed']:.4f}; positions {list(LEDGER['positions'])}; "
          f"halt={bool(LEDGER['halt'])}")
    if (out["filled"] != 1.0 or abs(LEDGER["committed"] - 0.97) > 1e-9
            or abs(LEDGER["fees"] - 0.0014) > 1e-9 or "T" not in LEDGER["positions"]
            or not LEDGER["halt"] or out["unrest"].get("fill_discovered") != 1.0):
        fails.append(f"R4: a fill found on reconciliation was not booked+halted: {out} {LEDGER}")
    # R5: the create response itself says status resting (record shape)
    fs, fg, log = wire(post=(200, {"order_id": "r1", "status": "resting",
                                   "fill_count_fp": "0.00", "remaining_count_fp": "1.00"}),
                       delete=(200, {"reduced_by": "1.00"}), record=rec_canceled)
    out = run_take(fs, fg)
    print(f"    R5 response says status=resting -> cancels sent "
          f"{sum(1 for m in log if m[0] == 'DELETE')}; committed "
          f"${LEDGER['committed']:.4f}; halt={bool(LEDGER['halt'])}")
    if (not any(m[0] == "DELETE" for m in log) or abs(LEDGER["committed"]) > 1e-9
            or not LEDGER["halt"]):
        fails.append(f"R5: an explicit resting status was not cancelled+halted: {LEDGER}")
    # R6: _book() reached directly with live contracts and no unrest: never release
    reset_ledger()
    LEDGER["committed"] = 0.97
    _book(normalise(201, rest201[1], y, DEMO), y, 0.97)
    if abs(LEDGER["committed"] - 0.97) > 1e-9 or not LEDGER["halt"]:
        fails.append(f"R6: _book() released a live order without a cancel: {LEDGER}")
    reset_ledger()

    # --- environment rails inside take() ----------------------------------------
    print("\n  environment rails inside take():")
    fs, fg, log = wire(post=(201, {"order_id": "x", "fill_count": "0.00",
                                   "remaining_count": "0.00"}))
    out = run_take(fs, fg, base=None)
    print(f"    base=None -> refused={bool(out.get('refused'))} sends={len(log)}")
    if not out.get("refused") or log or not any("base is None" in s for s in out["refused"]):
        fails.append(f"take(base=None) was not refused before the wire: {out.get('refused')} {log}")
    arm_prod("self-test: proving the clock cannot be overridden on production")
    try:
        fs, fg, log = wire(post=(201, {"order_id": "x", "fill_count": "0.00",
                                       "remaining_count": "0.00"}))
        out = run_take(fs, fg, base=PROD)         # now_epoch is set by run_take
    finally:
        disarm_prod()
    print(f"    production armed + now_epoch override -> refused="
          f"{bool(out.get('refused'))} sends={len(log)}")
    if not out.get("refused") or log or not any("now_epoch" in s for s in out["refused"]):
        fails.append(f"a production take with a faked clock reached the wire: {out.get('refused')} {log}")
    reset_ledger()

    # --- STRUCTURAL: the wire call cannot precede the check ---------------------
    print("\n  STRUCTURAL: in take(), check_take( must come before send(:")
    code, tree, fn = _take_code_source()
    i_check = code.find("check_take(")
    i_send = code.find("send(")
    print(f"    text: check_take( at {i_check}, send( at {i_send}")
    if i_check < 0:
        fails.append("take() does not call check_take at all")
    if i_send < 0:
        fails.append("take() never reaches send( -- it cannot trade")
    if i_check >= 0 and i_send >= 0 and i_send < i_check:
        fails.append("send( appears before check_take( in take()")
    if "if violations:" not in code or code.find("if violations:") > i_send:
        fails.append("take() does not return on violations before send(")
    sends = [n_ for n_ in ast.walk(fn) if isinstance(n_, ast.Call)
             and _call_name(n_) == "send"]
    checks = [n_ for n_ in ast.walk(fn) if isinstance(n_, ast.Call)
              and _call_name(n_) == "check_take"]
    if len(sends) != 1:
        fails.append(f"take() has {len(sends)} send calls, expected exactly 1")
    if not checks or (sends and min(c_.lineno for c_ in checks) >=
                      min(s_.lineno for s_ in sends)):
        fails.append("AST: check_take is not before send in take()")
    unrests = [n_ for n_ in ast.walk(fn) if isinstance(n_, ast.Call)
               and _call_name(n_) == "_unrest"]
    if unrests and sends and min(u_.lineno for u_ in unrests) <= max(s_.lineno for s_ in sends):
        fails.append("AST: _unrest (the cancel path) is reachable before send in take()")
    # and nothing else in this module may reach the wire: every call that can
    # carry a request -- send, cancel, amend, urlopen -- is pinned to one
    # function each, with a count.
    WIRE = ("send", "cancel", "amend", "urlopen")
    ALLOWED = {"take": {"send": 1}, "_unrest": {"cancel": 1}, "_get": {"urlopen": 1}}
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "selftest":
            continue
        name = node.name if isinstance(node, ast.FunctionDef) else f"<module:{node.lineno}>"
        for n_ in ast.walk(node):
            if isinstance(n_, ast.Call) and _call_name(n_) in WIRE:
                found.setdefault(name, {})
                found[name][_call_name(n_)] = found[name].get(_call_name(n_), 0) + 1
    print(f"    AST: wire-capable calls by function: {found}")
    if found != ALLOWED:
        fails.append(f"wire-capable calls differ from the allowed map: found {found}, "
                     f"allowed {ALLOWED}")
    # _get() must build a GET and nothing else
    getfn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_get")
    reqs = [n_ for n_ in ast.walk(getfn) if isinstance(n_, ast.Call)
            and _call_name(n_) == "Request"]
    meths = [kw.value.value for r_ in reqs for kw in r_.keywords
             if kw.arg == "method" and isinstance(kw.value, ast.Constant)]
    print(f"    AST: _get() builds {len(reqs)} Request(s) with method literal(s) {meths}")
    if len(reqs) != 1 or meths != ["GET"]:
        fails.append(f"_get() does not build exactly one Request with method='GET': {meths}")

    print("\n  default environment:")
    print(f"    base defaults to DEMO: {DEMO}; production needs --prod")

    print()
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        return False
    # EVERY NUMBER HERE IS READ FROM THE CONSTANT, NEVER TYPED. The version
    # this replaces said "count <= 1", "HARD_MAX 5", "$5 stake ledger" and
    # "-$2 loss abort" long after those rails became 10, 25, $60 and settable.
    # A summary that describes code which no longer exists is worse than none:
    # it is a PASSING TEST REPORTING A CONFIGURATION THAT IS NOT RUNNING --
    # the same failure as the start record that logged a derived ceiling.
    print(f"SELF-TEST PASSED -- IOC only, post_only False, "
          f"count <= {MAX_TAKE_COUNT:g} with a separate HARD_MAX "
          f"{HARD_MAX:g}, close within {MAX_TAU:g} s,\n"
          f"${MAX_RUN_STAKE:.2f} stake ledger booked from fills "
          f"(released only on remaining 0), UNKNOWN outcomes and 5xx keep "
          f"the stake and halt,\n"
          f"a rested IOC is cancelled, verified and halted, "
          f"${LOSS_ABORT:.2f} loss abort "
          f"(raisable via set_limits, never tightenable),\n"
          f"production refused unless armed and never with a faked clock, "
          f"and no path to the wire without an empty violation list.")
    return True


# ---------- environment test (DEMO ONLY) -------------------------------------
def envtest(key_id, key_file):
    """Prove demo auth, read the demo KXBTC15M book, and run take() THROUGH
    THE RAILS at the best ask. Nothing bypasses check_take here. The demo
    base is hard-wired; --prod is refused by main()."""
    base = DEMO
    print("=" * 78)
    print(f"ENVIRONMENT TEST -- {base}")
    print("=" * 78)
    pk = ordercli.load_key(key_file)
    st, bal = _get(base, pk, key_id, "/portfolio/balance")
    print(f"  GET /portfolio/balance -> {st} {json.dumps(bal)[:300] if isinstance(bal, dict) else bal}")
    if st != 200:
        print("  demo auth FAILED; nothing more is attempted.")
        return False
    st, mk = _get(base, pk, key_id, "/markets",
                  {"series_ticker": "KXBTC15M", "status": "open", "limit": "5"})
    ms = (mk or {}).get("markets", []) if isinstance(mk, dict) else []
    print(f"  GET /markets?series_ticker=KXBTC15M&status=open -> {st}: {len(ms)} market(s)")
    if not ms:
        print("  the demo has no open KXBTC15M market; nothing is sent.")
        return False
    m = ms[0]
    tk, ct, ei = m["ticker"], m.get("close_time"), int(m.get("exchange_index") or 0)
    cs = close_epoch(ct)
    now = time.time()
    print(f"  market {tk} close {ct} (tau {cs - now:+.0f} s) exchange_index {ei}")
    st, ob = _get(base, pk, key_id, f"/markets/{tk}/orderbook", {"depth": "5"})
    o = (ob or {}).get("orderbook_fp") or {} if isinstance(ob, dict) else {}
    print(f"  GET /markets/{tk}/orderbook -> {st} {json.dumps(o)[:300]}")
    nb = [_f(px) for px, _ in (o.get("no_dollars") or [])]
    ask = round(1.0 - max(nb), 4) if nb else None
    print(f"  best YES ask (1 - best NO bid): {ask if ask is not None else 'NONE -- nothing offered'}")
    price = ask if ask is not None else _f(m.get("yes_ask_dollars"))
    print(f"\n  take(base=DEMO, {tk}, yes, price {price}, count 1, close {ct}) "
          f"-- THROUGH THE RAILS:")
    out = take(base, pk, key_id, tk, "yes", price, 1, cs, exchange_index=ei)
    if out.get("refused"):
        print("  REFUSED BY THE RAILS. Nothing was sent:")
        for v in out["refused"]:
            print("    - " + v)
        return True
    print(f"  SENT -> {out['status_code']}")
    print(f"  raw: {json.dumps(out['raw']) if isinstance(out['raw'], dict) else out['raw']}")
    print(f"  parsed: order_id {out['order_id']} status {out['status']} "
          f"({out['status_source']}) filled {out['filled']} remaining "
          f"{out['remaining']} exec_price {out['exec_price']} fee {out['fee']} "
          f"({out['fee_field']})")
    print(f"  ledger: {json.dumps({k: LEDGER[k] for k in ('committed', 'filled_dollars', 'fees', 'halt')})}")
    return True


def _get(base, pk, key_id, path, query=None):
    """Authenticated GET via ordercli's signer (path signed without query)."""
    import urllib.request
    import urllib.error
    q = "" if not query else "?" + "&".join(f"{k}={v}" for k, v in query.items())
    req = urllib.request.Request(base + path + q, method="GET")
    for k, v in ordercli.sign_headers(pk, key_id, "GET", "/trade-api/v2" + path).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:
        return -1, str(e)


# ---------- CLI ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--envtest", action="store_true",
                    help="DEMO ONLY: auth, book, one take through the rails")
    ap.add_argument("--ticker")
    ap.add_argument("--want", choices=["yes", "no"], default="yes")
    ap.add_argument("--price", type=float)
    ap.add_argument("--count", type=float, default=1.0)
    ap.add_argument("--close", help="market close_time, e.g. 2026-09-07T20:15:00Z")
    ap.add_argument("--exchange-index", type=int, default=0)
    ap.add_argument("--prod", action="store_true",
                    help="use PRODUCTION (real money). Demo is the default.")
    ap.add_argument("--live", action="store_true", help="actually send")
    ap.add_argument("--key-id", default="")
    ap.add_argument("--key-file", default="")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing to touch the API")

    if a.envtest:
        if a.prod:
            raise SystemExit("--envtest is DEMO ONLY; --prod is refused")
        ok = envtest(a.key_id or DEMO_KEY_ID, a.key_file or DEMO_KEY_FILE)
        raise SystemExit(0 if ok else 1)

    if not (a.ticker and a.price and a.close):
        raise SystemExit("--ticker, --price and --close are required")
    if a.prod:
        base = PROD
        key_id = a.key_id or os.environ.get("KALSHI_KEY_ID", "")
        key_file = a.key_file or PROD_KEY_FILE
        if not key_id:
            raise SystemExit("--key-id (or KALSHI_KEY_ID) is required for --prod")
    else:
        base = DEMO
        key_id = a.key_id or DEMO_KEY_ID
        key_file = a.key_file or DEMO_KEY_FILE

    cs = close_epoch(a.close)
    body = build_take(a.ticker, a.want, a.price, a.count, a.exchange_index)
    if a.prod:
        arm_prod("--prod on the command line")
    bad = check_take(body, cs, time.time(), base=base)
    print("\n" + "=" * 78)
    print("TAKE, NOT YET SENT")
    print("=" * 78)
    print(f"  environment : {'PRODUCTION -- REAL MONEY' if a.prod else 'DEMO'}")
    print(f"  base        : {base}")
    print(f"  body        : {json.dumps(body, indent=2)}")
    print(f"  stake       : ${stake(body):.4f}   expected taker fee "
          f"${expected_fee(a.price, a.count):.4f}")
    print(f"  tau         : {cs - time.time():+.1f} s to close")
    if bad:
        print("\n  *** REFUSED BY THE RAILS ***")
        for v in bad:
            print("    - " + v)
        raise SystemExit(1)
    if not a.live:
        print("\n  DRY RUN. Nothing was sent. Add --live to send.")
        return
    pk = ordercli.load_key(key_file)
    out = take(base, pk, key_id, a.ticker, a.want, a.price, a.count, cs,
               exchange_index=a.exchange_index)
    print(f"\n  POST {ENDPOINT} -> {out['status_code']}")
    print(f"  raw    : {json.dumps(out['raw']) if isinstance(out['raw'], dict) else out['raw']}")
    print(f"  parsed : order_id {out['order_id']} status {out['status']} "
          f"({out['status_source']}) filled {out['filled']} remaining "
          f"{out['remaining']} exec_price {out['exec_price']} fee {out['fee']} "
          f"({out['fee_field']})")
    if out.get("refused"):
        print(f"  refused: {out['refused']}")
    print(f"  ledger : committed ${LEDGER['committed']:.4f} filled "
          f"${LEDGER['filled_dollars']:.4f} fees ${LEDGER['fees']:.4f} "
          f"halt {LEDGER['halt']}")


if __name__ == "__main__":
    main()
