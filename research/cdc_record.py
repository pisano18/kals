#!/usr/bin/env python3
"""cdc_record.py -- record Crypto.com's DCM prediction market, read-only.

THE OPERATOR, 2026-09-16: "Do start recording and seeing if your strategy or a
strategy would work if you could bet."

CDNA (the old Nadex, now Crypto.com | Derivatives North America) lists binary
options on BTC, ETH, SOL, XRP, DOT, BCH, ADA, XLM that settle on a SIXTY-SECOND
TRIMMED AVERAGE of the underlying index -- the same collapse the Kalshi pin bot
lives on. Their whole market data surface is PUBLIC and unauthenticated.

What this writes, one gzip file per channel per hour, exactly like the Kalshi
collector so the analysis tools feel familiar:

  instruments  the live contract list, once a minute
  book         top 10 levels of every crypto binary, every few seconds
  trades       prints, so we can see what actually changed hands
  tickers      high/low/last/volume per contract

WHY IT MATTERS AND WHAT IT CANNOT DO. Their index feed is not exposed on any
endpoint I could find, so this cannot price fair value the way the pin does.
What it CAN do is answer the only question that matters first: does a
near-certain side ever get offered cheap here, or does the market maker hold a
13-cent spread all the way into expiry? A few days of tape settles that without
anyone placing a bet.

READ-ONLY. Every call is a public GET. No key, no orders, no account.

    python cdc_record.py --selftest
    python cdc_record.py --seconds 5
"""
import argparse
import gzip
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://api.crypto.com/dcm/v1/"
OUT = r"C:\kals\cdc_data"
# EVERY binary option, not a hand-picked coin list. Measured 2026-09-16:
# 522 live at once across 20 crypto names, four FX pairs and four stock
# indices, in 5, 15 and 20 minute windows. The first version filtered to eight
# coins and silently missed most of the venue.
NEAR_EXPIRY_S = 420      # only poll books for contracts closing within 7 min:
                         # that is where the settlement window is locking and
                         # the only place the edge can live. Polling all 522
                         # every few seconds would be ~300 requests a second.
UA = {"User-Agent": "kals-research/1.0 (read-only market data)"}


def get(path, timeout=20):
    req = urllib.request.Request(BASE + path, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_body": e.read()[:200].decode("utf-8", "replace")}
    except Exception as e:                                   # noqa: BLE001
        return {"_err": str(e)[:160]}


def near_expiry(row, now_ms, horizon_s=NEAR_EXPIRY_S):
    """Is this contract close enough to expiry to be worth watching?"""
    e = row.get("expiry_timestamp_ms")
    if not e:
        return False
    left = (int(e) - now_ms) / 1000.0
    return -30 <= left <= horizon_s


class Writer:
    """One gzip file per channel per hour, flushed every write.

    Flushing matters: a hard kill must not cost the hour. The Kalshi collector
    learned that the expensive way."""

    def __init__(self, root=OUT):
        self.root = root
        self.files = {}

    def write(self, channel, obj):
        hour = time.strftime("%Y%m%dT%H", time.gmtime())
        key = (channel, hour)
        if key not in self.files:
            for (c, h), fh in list(self.files.items()):
                if c == channel and h != hour:
                    fh.close()
                    del self.files[(c, h)]
            d = os.path.join(self.root, channel)
            os.makedirs(d, exist_ok=True)
            self.files[key] = gzip.open(os.path.join(d, hour + ".jsonl.gz"), "at",
                                        encoding="utf-8")
        obj["_rx_ms"] = int(time.time() * 1000)
        fh = self.files[key]
        fh.write(json.dumps(obj) + "\n")
        fh.flush()

    def close(self):
        for fh in self.files.values():
            try:
                fh.close()
            except Exception:                                # noqa: BLE001
                pass


def all_binaries():
    """Every live binary option. limit=1000 matters: the default page of 500
    returned 122 binaries when 522 existed."""
    d = get("public/get-instruments?limit=1000")
    rows = (d.get("result") or {}).get("data") or []
    return [r for r in rows if r.get("inst_type") == "BINARY_OPTION"]


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    now = 1_700_000_000_000
    ck(near_expiry({"expiry_timestamp_ms": now + 60_000}, now),
       "a contract expiring in a minute is watched")
    ck(near_expiry({"expiry_timestamp_ms": now - 10_000}, now),
       "and one that expired 10 s ago still is -- the settlement print lands "
       "after the close and tells us who won")
    ck(not near_expiry({"expiry_timestamp_ms": now + 3_600_000}, now),
       "NULL: one an hour out is not, because nothing is locked yet")
    ck(not near_expiry({}, now), "NULL: no expiry means not watched, never a crash")
    import tempfile
    tmp = tempfile.mkdtemp()
    w = Writer(tmp)
    w.write("book", {"a": 1})
    w.write("book", {"a": 2})
    w.close()
    hour = time.strftime("%Y%m%dT%H", time.gmtime())
    p = os.path.join(tmp, "book", hour + ".jsonl.gz")
    rows = [json.loads(l) for l in gzip.open(p, "rt", encoding="utf-8")]
    ck(len(rows) == 2 and rows[0]["a"] == 1 and "_rx_ms" in rows[0],
       "two writes land in one hourly file, each stamped with arrival time")
    ck(rows[0]["_rx_ms"] > 1_700_000_000_000,
       "and the stamp is a real millisecond clock, not a second one")
    d = get("public/get-instruments?limit=1000")
    live = (d.get("result") or {}).get("data")
    ck(isinstance(live, list) and len(live) > 10,
       "the public endpoint answers without a key (%s rows)"
       % (len(live) if isinstance(live, list) else d))
    bos = [r for r in (live or []) if r.get("inst_type") == "BINARY_OPTION"]
    ck(len(bos) > 100,
       "and %d of them are binary options -- the default page size showed 122 "
       "when 522 existed, so limit=1000 is not optional" % len(bos))
    print("cdc_record selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seconds", type=float, default=5.0,
                    help="book poll interval")
    ap.add_argument("--minutes", type=float, default=100000.0)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    w = Writer()
    t0 = time.time()
    insts = []
    last_inst = 0.0
    polls = 0
    print("recording to %s -- books every %.0fs, read-only" % (OUT, a.seconds))
    try:
        while time.time() - t0 < a.minutes * 60:
            now = time.time()
            if now - last_inst > 60:
                last_inst = now
                insts = all_binaries()
                w.write("instruments", {"n": len(insts), "rows": insts})
            now_ms = int(now * 1000)
            watch = [r for r in insts if near_expiry(r, now_ms)]
            for r in watch:
                s = r.get("symbol")
                if not s:
                    continue
                b = get("public/get-book?instrument_name=%s&depth=10" % s)
                w.write("book", {"symbol": s, "resp": b})
                tk = get("public/get-tickers?instrument_name=%s" % s)
                w.write("tickers", {"symbol": s, "resp": tk})
                tr = get("public/get-trades?instrument_name=%s" % s)
                w.write("trades", {"symbol": s, "resp": tr})
            polls += 1
            if polls % 20 == 0:
                print("  %s  %d passes, watching %d of %d live binaries"
                      % (time.strftime("%H:%M:%S"), polls, len(watch), len(insts)),
                      flush=True)
            time.sleep(a.seconds)
    finally:
        w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
