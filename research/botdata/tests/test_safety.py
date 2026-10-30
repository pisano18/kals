"""test_safety.py -- botstats and botdata are READ ONLY by construction, and every text file they open names its encoding.

v-tg-rebuild step 7 (2026-10-30): the old self-test's section 0 (it scanned botstats.py alone; since step 4 also procs.py
and status.py), now over botstats.py and EVERY research/botdata/*.py (the tests excluded: they name the forbidden words
to look for them). Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_safety.py
"""
import ast
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import RESEARCH, ck, run                                   # noqa: E402

FILES = [os.path.join(RESEARCH, "botstats.py")] + sorted(glob.glob(os.path.join(RESEARCH, "botdata", "*.py")))


def _src():
    out = ""
    for f in FILES:
        with open(f, encoding="utf-8") as fh:
            out += fh.read() + "\n"
    return out


def test_no_order_transfer_or_process_control():
    """0. READ ONLY, BY CONSTRUCTION. The forbidden words are assembled from pieces so this check does not find
    itself; botstats.py and every botdata module are scanned."""
    src = _src()
    # 2026-10-02: the transfer HISTORY (GET .../transfers, plural) is read for the pot; the singular path
    # is the one that MOVES money, and it stays forbidden.
    bad = [p for p in (r"\b" + "PO" + r"ST\b", r"\b" + "DEL" + r"ETE\b", r"\b" + "PA" + r"TCH\b", r"\b" + "PU" + r"T\b",
                       "portfolio/" + "orders", "events/" + "orders", "subaccounts/" + r"transfer(?!s)", "order" + "cli",
                       "pin" + "take", "url" + "open", "urllib" + ".request", "Stop-" + "Process", "Start-" + "Process",
                       "task" + "kill", r"os\." + "kill", r"\." + r"terminate\(", "Invoke-" + "WebRequest",
                       "Terminate" + "Process", "Create" + "Process", "Write" + "ProcessMemory", "Shell" + "Execute")
           if re.search(p, src)]
    ck(not bad, "botstats + botdata contain no order, cancel, transfer or process-control call (found: %s)" % bad)
    ck(sorted(set(re.findall(r"/portfolio/subaccounts/\w+", src))) == ["/portfolio/subaccounts/balances",
                                                                     "/portfolio/subaccounts/transfers"],
       "the only subaccount paths named are the two GET listings (cash by pool, transfer history)")
    masks = re.findall(r"k32\." + r"OpenProcess\(\s*([^,]+),", src)
    ck(masks and all(m.strip() == "0x1000" for m in masks),
       "every process handle is opened with QUERY_LIMITED_INFORMATION (0x1000) only: %s" % masks)


def test_subprocess_only_in_procs():
    """DESIGN section 2: botdata/procs.py is the only botdata user of subprocess (the WMI fallback)."""
    users = []
    for f in FILES:
        with open(f, encoding="utf-8") as fh:
            if re.search(r"^\s*(import subprocess|from subprocess)", fh.read(), re.M):
                users.append(os.path.basename(f))
    ck(users == ["procs.py"], "only procs.py imports subprocess: %s" % users)


def test_every_text_open_names_its_encoding():
    """Every open() in text mode passes encoding= (the box's code page is cp1252; a log line with a non-ASCII
    character once broke a read)."""
    bad = []
    for f in FILES:
        with open(f, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"):
                continue
            mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
            binary = isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "b" in mode.value
            if not binary and not any(k.arg == "encoding" for k in n.keywords):
                bad.append("%s:%d" % (os.path.basename(f), n.lineno))
    ck(not bad, "every text open() in botstats + botdata names its encoding (missing: %s)" % bad)


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_safety"))
