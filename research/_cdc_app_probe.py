"""cdc_probe.py -- what can the Crypto.com agent key actually reach?

READ-ONLY. Signs GET calls the way crypto-com/crypto-agent-trading does:

    BASE  https://wapi.crypto.com
    sig   base64( HMAC-SHA256( secret, timestamp + METHOD + path + body ) )
    hdrs  Cdc-Api-Key, Cdc-Api-Timestamp, Cdc-Api-Signature

The question is whether CDNA event/prediction contracts are reachable with it,
or whether it only reaches the consumer app's spot wallet.

Credentials: C:\\kals\\cdc_agent_key.json, outside the repo, never committed.
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request

CREDS = r"C:\kals\cdc_agent_key.json"
BASE = "https://wapi.crypto.com"

# what the published skill uses, plus guesses at a prediction surface
PATHS = [
    "/v1/api-keys/current",
    "/v1/portfolio",
    "/v1/crypto-account",
    # prediction / event contract guesses
    "/v1/prediction/markets",
    "/v1/predictions",
    "/v1/event-contracts",
    "/v1/predict/markets",
    "/v1/cdna/markets",
    "/v1/derivatives/markets",
]


def call(path, method="GET", body=None):
    c = json.load(open(CREDS, encoding="utf-8"))
    ts = str(int(time.time() * 1000))
    body_str = json.dumps(body) if body else ""
    sign_path = path.split("?")[0]
    payload = ts + method.upper() + sign_path + body_str
    sig = base64.b64encode(
        hmac.new(c["secret"].encode(), payload.encode(), hashlib.sha256).digest()
    ).decode()
    headers = {"User-Agent": "Python/3 windows-cdc-probe/1.0",
               "Cdc-Api-Key": c["api_key"],
               "Cdc-Api-Timestamp": ts,
               "Cdc-Api-Signature": sig}
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, method=method,
                                 data=body_str.encode() if body else None,
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()[:900]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400]
    except Exception as e:                                   # noqa: BLE001
        return -1, str(e)[:120].encode()


if __name__ == "__main__":
    for p in PATHS:
        st, b = call(p)
        try:
            txt = b.decode("utf-8", "replace")
        except Exception:                                    # noqa: BLE001
            txt = str(b)
        print("%-4s %-30s %s" % (st, p, " ".join(txt.split())[:190]))
