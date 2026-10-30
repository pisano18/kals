"""Shared helpers for the golden-output harness (step 0 of the phone rebuild). Never imported by production code.

Plain standard library only: this file is imported BEFORE the fence is installed and before any code under test.
"""
import hashlib
import json
import os
import re

CHAT = 4242                      # the fake paired chat
OTHER_CHAT = 999                 # a chat that is not ours
SECRET = "golden-secret"         # the fake pairing secret (never the real one)
TOKEN = "0:golden-fake-token"    # the fake bot token (never the real one)
FAKE_TELEGRAM_JSON = {"token": TOKEN, "chat_id": CHAT, "secret": SECRET, "charts": True}

HERE = os.path.dirname(os.path.abspath(__file__))


# ---- a JSON codec that keeps tuples and sets (health / machine / procs carry tuples) ----------------------------
def enc(x):
    if isinstance(x, tuple):
        return {"__tuple__": [enc(v) for v in x]}
    if isinstance(x, (set, frozenset)):
        return {"__set__": sorted((enc(v) for v in x), key=repr)}
    if isinstance(x, list):
        return [enc(v) for v in x]
    if isinstance(x, dict):
        if all(isinstance(k, str) for k in x):
            return {k: enc(v) for k, v in x.items()}
        return {"__dict__": [[enc(k), enc(v)] for k, v in x.items()]}
    if isinstance(x, bytes):
        return {"__bytes__": x.decode("latin-1")}
    if x is None or isinstance(x, (str, int, float, bool)):
        return x
    return {"__repr__": repr(x)}


def dec(x):
    if isinstance(x, list):
        return [dec(v) for v in x]
    if isinstance(x, dict):
        if len(x) == 1:
            k = next(iter(x))
            if k == "__tuple__":
                return tuple(dec(v) for v in x[k])
            if k == "__set__":
                return set(dec(v) for v in x[k])
            if k == "__dict__":
                return {_hashable(dec(a)): dec(b) for a, b in x[k]}
            if k == "__bytes__":
                return x[k].encode("latin-1")
            if k == "__repr__":
                return x[k]
        return {k: dec(v) for k, v in x.items()}
    return x


def _hashable(v):
    return tuple(_hashable(x) for x in v) if isinstance(v, list) else v


def dump_json(path, obj, codec=True):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(enc(obj) if codec else obj, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def load_json(path, codec=True):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return dec(d) if codec else d


def canon(obj):
    """Canonical JSON text of a case result: sorted keys, no float noise beyond repr, tuples as lists."""
    return json.dumps(_plain(obj), sort_keys=True, ensure_ascii=False, indent=1, default=repr)


def _plain(x):
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted((_plain(v) for v in x), key=repr)
    if isinstance(x, float) and (x != x or x in (float("inf"), float("-inf"))):
        return repr(x)
    return x


def sha(b):
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def case_file(case_id):
    """A case id ('cmd//stop yes') as a safe file name."""
    s = re.sub(r"[^a-z0-9._-]+", lambda m: "~%s~" % "".join("%02x" % ord(c) for c in m.group(0)), case_id)
    return s[:150] + ".json"


# ---- Kalshi request keys -----------------------------------------------------------------------------------------
def kalshi_key(path, params):
    q = "&".join("%s=%s" % (k, (params or {})[k]) for k in sorted(params or {}))
    return str(path) + ("?" + q if q else "")


# ---- output normalisation ----------------------------------------------------------------------------------------
_HEX = re.compile(r"0x[0-9a-fA-F]{6,}")


class Normaliser:
    """Replaces machine- and tree-specific strings (the code tree, the scratch folder) with fixed tokens so the same
    behaviour gives the same bytes on any tree."""

    def __init__(self, pairs):
        # longest first, each in its raw and its JSON-escaped (doubled backslash) form, case-insensitively
        self.subs = []
        for real, token in sorted(pairs, key=lambda p: -len(p[0])):
            if not real:
                continue
            for form in {real, real.replace("\\", "\\\\"), real.replace("\\", "/")}:
                self.subs.append((re.compile(re.escape(form), re.I), token))

    def s(self, text):
        if not isinstance(text, str):
            return text
        for rx, token in self.subs:
            text = rx.sub(token.replace("\\", "\\\\"), text)
        return _HEX.sub("0xADDR", text)

    def deep(self, x):
        if isinstance(x, str):
            return type(x)(self.s(x)) if type(x) is str else self.s(str(x))
        if isinstance(x, dict):
            return {self.s(k) if isinstance(k, str) else k: self.deep(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [self.deep(v) for v in x]
        return x
