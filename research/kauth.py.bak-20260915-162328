# kauth.py -- signed GETs against the Kalshi API. Imported by pinrun, livebook
# and pinracearm for KEY_ID and read-only calls.
#
# COPIED INTO THE REPO 2026-09-15 from the kals-work folder under the Windows
# TEMP directory, where it had lived since 2026-09-08 outside version control.
# Storage Sense and Disk Cleanup delete TEMP. The live bot loads that TEMP copy
# first (pinrun.py puts it at sys.path[0]); research/ is also on the path, so
# if Windows ever wipes TEMP this copy loads instead of an ImportError.
# The only change is KALSHI_KEY_FILE, for the Pi. THIS is the canonical copy;
# retire the TEMP one on the next versioned pinrun change.
"""Authenticated read-only Kalshi API helper.

Signs with the same RSA-PSS scheme kalshi_collector.make_signer uses. GET only
in this file -- no order endpoint is reachable from here by construction.
"""
import base64
import os
import json
import sys
import time
import urllib.request
import urllib.error

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

KEY_ID = "b48b406b-b498-4d14-b640-be989913526f"
# The key FILE is the secret and never enters git. On Windows it is C:\kals;
# on the Pi set KALSHI_KEY_FILE. Unset, this is exactly the old path.
KEY_FILE = os.environ.get("KALSHI_KEY_FILE", r"C:\kals\kalshi.pem")
BASE = "https://api.elections.kalshi.com"
PREFIX = "/trade-api/v2"

with open(KEY_FILE, "rb") as f:
    _PK = serialization.load_pem_private_key(f.read(), password=None)


def headers(method, path):
    ts = str(int(time.time() * 1000))
    msg = (ts + method + path).encode()
    sig = _PK.sign(msg,
                   padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                               salt_length=padding.PSS.DIGEST_LENGTH),
                   hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "Accept": "application/json"}


def get(path, params=None, auth=True):
    """GET only. Returns (status, parsed-or-text)."""
    q = ""
    if params:
        q = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    full = PREFIX + path
    req = urllib.request.Request(BASE + full + q, method="GET")
    if auth:
        for k, v in headers("GET", full).items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body[:400]
    except Exception as e:
        return -1, str(e)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        st, body = get(path)
        print(f"--- GET {path} -> {st}")
        print(json.dumps(body, indent=1)[:1800] if isinstance(body, (dict, list))
              else str(body)[:800])
