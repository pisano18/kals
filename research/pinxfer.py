"""pinxfer.py -- every dollar that entered or left the account, FROM KALSHI.

WHY THIS EXISTS, and it is not a nice-to-have.

Until 2026-09-20 nothing in this repo knew what had been deposited. Two things
guessed, and both guessed wrong:

  1. `results/DEPOSITED.txt` held a single hand-typed number ($160). The
     desktop app divided by it, so a $378 deposit on 09-19 read as profit and
     the app reported a total return over 100%.

  2. `pinrun.classify_bank_move()` infers transfers from the BANK BALANCE:
     anything the balance did that `realised` does not explain is called a
     deposit or a withdrawal. **`realised` RESETS TO ZERO ON RESTART**
     (CURRENT_STATE trap 7), so every trading gain or loss that straddles a
     restart is misread as money moving in or out.

     That is not theoretical. It invented a **$58.37 WITHDRAWAL** at
     2026-09-17T20:16:58Z. Kalshi's own books say there has NEVER been a
     withdrawal on this account -- `/portfolio/withdrawals` returns zero
     records. The operator: *"I never took out 58.37."*

     Worse, `shift_hwm()` moved the drawdown brake's high-water mark by those
     invented amounts. The mark ended at $1046.43, a level the balance never
     reached, and on 2026-09-20 the brake halted the live bot on a drawdown
     that was partly fictional -- and could not clear, because a halted bot
     cannot earn the balance back.

THE FIX IS TO STOP GUESSING. `/portfolio/deposits` and
`/portfolio/withdrawals` are the exchange's own records: amount, fee, status
and timestamp. This module reads them, caches them, and answers one question
exactly -- how much money has the operator put in, and taken out, as of any
instant.

**FEES COME OFF.** A $378.00 deposit with a $7.56 fee credits $370.44. The
$370.44 is what the balance moved by and therefore what "put in" means here;
the $378.00 is what left his bank account. Both are reported, because the
difference is real money and he is entitled to see it.

Only settled/applied transfers count. A pending deposit has not moved the
balance and must not be subtracted from performance.

    python research/pinxfer.py              # the table, and the reconciliation
    python research/pinxfer.py --selftest
"""
import argparse
import datetime
import json
import os
import sys

ET = datetime.timezone(datetime.timedelta(hours=-4))
RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "results")
CACHE = os.path.join(RESULTS, "kalshi_transfers.json")

# Kalshi marks a finished transfer with one of these. Anything else is in
# flight and has NOT moved the balance, so counting it would overstate what
# was put in and understate what we made.
DONE = ("applied", "settled", "succeeded", "complete", "completed")


def is_done(rec):
    return str(rec.get("status", "")).lower() in DONE


def _num(rec, key):
    """A cents field as a float, or 0.0. EVERY read of these records goes
    through here: the first version guarded net_cents() and not the gross and
    fee sums, and one unparseable amount raised out of totals()."""
    try:
        return float(rec.get(key) or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def net_cents(rec):
    """What the BALANCE moved by: amount minus the fee Kalshi charged."""
    return _num(rec, "amount_cents") - _num(rec, "fee_cents")


def when(rec):
    for k in ("finalized_ts", "created_ts", "updated_ts"):
        v = rec.get(k)
        if v:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return None


def totals(deposits, withdrawals, as_of=None):
    """(in_net, out_net, in_gross, fees) in DOLLARS, counting only finished
    transfers at or before `as_of` (epoch seconds; None = everything)."""
    din = dgross = dfees = dout = 0.0
    for r in deposits or ():
        if not is_done(r):
            continue
        t = when(r)
        if as_of is not None and (t is None or t > as_of):
            continue
        din += net_cents(r) / 100.0
        dgross += _num(r, "amount_cents") / 100.0
        dfees += _num(r, "fee_cents") / 100.0
    for r in withdrawals or ():
        if not is_done(r):
            continue
        t = when(r)
        if as_of is not None and (t is None or t > as_of):
            continue
        dout += abs(net_cents(r)) / 100.0
    return din, dout, dgross, dfees


def load_cache(path=None):
    try:
        with open(path or CACHE, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {"deposits": [], "withdrawals": [], "fetched": None}
    d.setdefault("deposits", [])
    d.setdefault("withdrawals", [])
    return d


def refresh(path=None):
    """Pull both endpoints and cache them. Returns the cache dict.

    On any failure the EXISTING cache is left untouched and returned -- a
    stale-but-real number beats a confident wrong one, which is the mistake
    this whole file exists to undo.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kauth
    out = {"deposits": [], "withdrawals": [],
           "fetched": datetime.datetime.now(datetime.timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%SZ")}
    for path_, key in (("/portfolio/deposits", "deposits"),
                       ("/portfolio/withdrawals", "withdrawals")):
        cursor, seen = None, []
        for _ in range(50):                       # bounded; never a live loop
            q = {"limit": "200"}
            if cursor:
                q["cursor"] = cursor
            st, b = kauth.get(path_, q)
            if st != 200 or not isinstance(b, dict):
                return load_cache(path)           # leave the cache alone
            got = b.get(key) or []
            seen.extend(got)
            cursor = b.get("cursor")
            if not cursor or not got:
                break
        out[key] = seen
    try:
        os.makedirs(os.path.dirname(path or CACHE), exist_ok=True)
        with open(path or CACHE, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    except OSError:
        pass
    return out


def selftest():
    ok = True

    def ck(cond, msg):
        nonlocal ok
        print("  %-4s %s" % ("ok" if cond else "FAIL", msg))
        if not cond:
            ok = False

    # THE REAL RECORD that broke everything, verbatim from Kalshi.
    real = {"amount_cents": 37800, "fee_cents": 756, "status": "applied",
            "created_ts": 1789801739, "finalized_ts": 1789801739,
            "type": "debit"}
    ck(abs(net_cents(real) / 100.0 - 370.44) < 1e-9,
       "PLANTED: the real 09-19 deposit is $378.00 gross, $7.56 fee, and the "
       "BALANCE moved by $370.44 -- the fee is real money and comes off")
    ck(is_done(real), "...and it is applied, so it counts")

    pend = dict(real, status="pending")
    ck(not is_done(pend),
       "NULL: a PENDING deposit has not moved the balance and must not be "
       "subtracted from what we made")

    din, dout, gross, fees = totals([real], [])
    ck(abs(din - 370.44) < 1e-9 and abs(gross - 378.0) < 1e-9
       and abs(fees - 7.56) < 1e-9,
       "totals report net, gross and fees separately (%.2f / %.2f / %.2f)"
       % (din, gross, fees))
    ck(dout == 0.0,
       "and ZERO withdrawals is zero -- Kalshi returns no withdrawal records "
       "for this account, and the $58.37 'withdrawal' pinrun inferred on "
       "2026-09-17 never happened")

    # as_of: performance on any past day needs the deposits of THAT day only
    ck(totals([real], [], as_of=1789801738)[0] == 0.0,
       "as_of EXCLUDES a deposit that had not landed yet -- otherwise a later "
       "deposit makes an earlier day look worse than it was")
    ck(abs(totals([real], [], as_of=1789801739)[0] - 370.44) < 1e-9,
       "...and includes it at the exact second it landed")

    # NULLs: nothing here may raise or invent a number
    for bad in (None, [], [{}], [{"amount_cents": "x", "status": "applied"}],
                [{"status": "applied"}]):
        try:
            v = totals(bad, bad)[0]
        except Exception as e:                     # noqa: BLE001
            v = "RAISED %s" % e
        ck(v == 0.0, "NULL: %r totals to 0.0, never a guess (%r)" % (bad, v))
    ck(when({}) is None and when({"created_ts": None}) is None,
       "NULL: a record with no usable timestamp reports None, not epoch 0 -- "
       "epoch 0 would sort before every as_of and always count")
    ck(when({"created_ts": 5, "finalized_ts": 9}) == 9,
       "the FINALIZED time wins: that is when the balance actually moved")

    # the cache must never be wiped by a failed pull
    d = load_cache(os.path.join(RESULTS, "__nope__.json"))
    ck(d["deposits"] == [] and d["withdrawals"] == [],
       "NULL: a missing cache reads as empty rather than raising")

    print("pinxfer selftest: OK" if ok else "pinxfer selftest: FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-refresh", action="store_true",
                    help="use the cache, do not call Kalshi")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not os.environ.get("KALS_SELFTESTED") and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")
    d = load_cache() if a.no_refresh else refresh()
    dep, wdr = d["deposits"], d["withdrawals"]
    din, dout, gross, fees = totals(dep, wdr)
    print("\n  EVERY TRANSFER, from Kalshi's own records")
    rows = sorted([(when(r), "deposit", r) for r in dep if is_done(r)] +
                  [(when(r), "withdrawal", r) for r in wdr if is_done(r)],
                  key=lambda x: x[0] or 0)
    for t, kind, r in rows:
        ts = (datetime.datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d %H:%M ET")
              if t else "?")
        print("    %s  %-11s $%8.2f  fee $%5.2f  net $%8.2f  %s"
              % (ts, kind, _num(r, "amount_cents") / 100.0,
                 _num(r, "fee_cents") / 100.0, net_cents(r) / 100.0,
                 r.get("type", "")))
    print("    " + "-" * 62)
    print("    put in   $%.2f gross, $%.2f in fees, $%.2f NET credited"
          % (gross, fees, din))
    print("    taken out $%.2f" % dout)

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import kauth
        st, b = kauth.get("/portfolio/balance", None)
        bank = float(b["balance"]) / 100.0
        held = float(b.get("portfolio_value") or 0) / 100.0
        print("\n  RECONCILIATION")
        print("    bank now                 $%.2f" % bank)
        print("    open positions           $%.2f" % held)
        print("    net put in - taken out   $%.2f" % (din - dout))
        print("    SO MONEY MADE            $%+.2f" % (bank + held - (din - dout)))
        if din:
            print("    return on money put in   %+.1f%%"
                  % (100.0 * (bank + held - (din - dout)) / din))
    except Exception as e:                         # noqa: BLE001
        print("\n  (balance unavailable: %s)" % str(e)[:90])


if __name__ == "__main__":
    main()
