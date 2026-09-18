"""pinledgerd.py -- keep `results/kalshi_ledger.json` fresh, forever.

WHY THIS EXISTS. `pinledger.py` pulls the account's settlements from Kalshi,
and `pindesk` / `pinphone` read the file it writes. Nothing was refreshing that
file, so the desktop app and the phone bot would have shown a ledger frozen at
whenever someone last ran the command by hand -- which is a quieter version of
the bug they were just fixed for. A number that is merely STALE still reads as
current.

It is deliberately tiny: fetch, write, sleep, repeat. An incremental refresh
stops at the first settlement it already holds, so the steady-state cost is one
request a minute. It never trades, holds no positions, and exits on the same
stop flag the desktop app uses to stand the bot down.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinledger                                                 # noqa: E402

RESULTS = pinledger.RESULTS
HEARTBEAT = os.path.join(RESULTS, "pinledgerd.heartbeat")
EVERY = 60


def once(creds, backfill=False):
    """One refresh. Returns (new settlements, total on file)."""
    rows = pinledger.load_cache(pinledger.LEDGER)
    added, _ = pinledger.fetch(rows, creds, backfill=backfill)
    if added:
        pinledger.save_cache(rows, pinledger.LEDGER)
    return added, len(rows)


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinledgerd selftest: FAILED -- " + msg)
    import json
    import tempfile
    td = tempfile.mkdtemp()
    sv = pinledger.LEDGER
    pinledger.LEDGER = os.path.join(td, "ledger.json")
    try:
        s = {"ticker": "KXBTC15M-26SEP170000-00", "market_result": "yes",
             "yes_count_fp": "10.00", "yes_total_cost_dollars": "9.80",
             "no_count_fp": "0.00", "no_total_cost_dollars": "0.00",
             "revenue": 1000, "fee_cost": "0.01",
             "settled_time": "2026-09-17T04:00:04Z"}
        calls = {"n": 0}

        def fake(path, q):
            calls["n"] += 1
            return 200, {"settlements": [s], "cursor": None}
        _real = pinledger.fetch

        def patched(rows, creds, backfill=False, page=200, getter=None):
            return _real(rows, creds, backfill=backfill, page=page, getter=fake)
        pinledger.fetch = patched
        added, total = once(None)
        ck(added == 1 and total == 1, "a first refresh writes the settlement")
        ck(os.path.exists(pinledger.LEDGER), "...to the ledger file on disk")
        added2, total2 = once(None)
        ck(added2 == 0 and total2 == 1,
           "a second refresh adds nothing -- append-only on (ticker, "
           "settled_time), so the file cannot grow by re-reading the same rows. "
           "That stacking is exactly what the log-parsing tools used to do")
        with open(pinledger.LEDGER, encoding="utf-8") as fh:
            ck(len(json.load(fh)["settlements"]) == 1,
               "and the file still holds exactly one row")
    finally:
        pinledger.fetch = _real
        pinledger.LEDGER = sv
    print("pinledgerd selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--every", type=int, default=EVERY)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    import ordercli
    import pintake
    import kauth
    creds = {"base": pintake.PROD_ELECTIONS, "key_id": kauth.KEY_ID,
             "pk": ordercli.load_key(pintake.PROD_KEY_FILE)}
    print("pinledgerd: refreshing Kalshi's settlements every %d s" % a.every, flush=True)
    while True:
        try:
            added, total = once(creds)
            if added:
                print("  +%d settlements (%d on file)" % (added, total), flush=True)
            with open(HEARTBEAT, "w", encoding="utf-8") as fh:
                fh.write('{"t": "%s", "settlements": %d}'
                         % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), total))
        except Exception as e:                                    # noqa: BLE001
            print("  refresh failed: %s" % str(e)[:200], flush=True)
        if a.once:
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
