import gzip, json, time, zlib
H="20260907T12"
t0=time.time(); n=0; keep=0
try:
    with gzip.open(f"C:/kals/feed_data/bitstamp/{H}.jsonl.gz","rt") as f:
        for l in f:
            n+=1
            if '"order_book_btcusd"' in l or '"order_book_ethusd"' in l:
                keep+=1
except (EOFError,OSError,zlib.error) as e: print("trunc",type(e).__name__)
print(f"bitstamp lines={n} btc/eth={keep} in {time.time()-t0:.1f}s")
for ch in ("coinbase","kraken","gemini"):
    t0=time.time(); n=0
    try:
        with gzip.open(f"C:/kals/feed_data/{ch}/{H}.jsonl.gz","rt") as f:
            for l in f: n+=1
    except (EOFError,OSError,zlib.error) as e: print("trunc",type(e).__name__)
    print(f"{ch} lines={n} in {time.time()-t0:.1f}s")
