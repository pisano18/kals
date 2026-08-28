#!/usr/bin/env python3
"""shadow.py -- does any file in this repo shadow a standard-library module?

    python research/shadow.py --selftest
    python research/shadow.py ..

WHY THIS EXISTS

On 2026-08-28 a full run died in every stage that reads compressed data:

    File "research/replay.py", line 47, in <module>
        import gzip
    File "C:\\Python314\\Lib\\gzip.py", line 16, in <module>
        from compression._common import _streams
    ModuleNotFoundError: No module named 'compression._common';
    'compression' is not a package

Python 3.14 added a standard-library PACKAGE called `compression`. This repo had
a `research/compression.py`, and every stage puts `research/` first on sys.path,
so `import gzip` found OUR file. gzip has imported that name since 3.14; before
that it imported `_compression`, with an underscore.

The part that makes this worth a permanent check rather than a one-line fix:

  * It was invisible on the machine the code was written on. That container
    runs 3.11. `compression` is not in its `sys.stdlib_module_names`, `gzip`
    does not import it, and every self-test passed.
  * It was fatal on the machine that runs the data, on 3.14.6.
  * Nothing in the project could see it. The self-tests import their own
    modules; only a stage that loads real data imports gzip, and those stages
    are exactly the ones that get skipped when there is no data to load.

So a name check against the RUNNING interpreter's stdlib list is not enough --
that is the check that would have passed. This file does two things instead.

  1. THE IMPORT PROBE. Put the package directory first on sys.path, exactly as
     every stage does, then import every stdlib module the repo actually names
     in an import statement, and check each one resolves to a file OUTSIDE the
     repo. This reproduces the failure directly and needs no list of stdlib
     names at all, so it catches versions of this bug nobody has thought of --
     including transitive ones like gzip -> compression, where the shadowed
     name is never mentioned in our own source.

  2. THE FORWARD-COMPATIBILITY NAME SCAN. The probe can only catch what breaks
     on the interpreter running it. A repo file named after a module that a
     NEWER Python will add is invisible to it, which is precisely what
     happened. So there is also a small, explicit list of stdlib names that
     exist in Pythons newer than the one running, and a file matching one is
     reported as a future break rather than a current one.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import ast
import importlib
import os
import sys

# Top-level stdlib names that exist in some Python but may not be in the
# `sys.stdlib_module_names` of the interpreter running this check. Add to this
# when a new Python lands; it is the only part of this file that has to be
# maintained by hand, and it is the part that would have caught the bug.
FUTURE_STDLIB = {
    "compression",      # 3.14: package; gzip/bz2/lzma import compression._common
    "annotationlib",    # 3.14
}

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".idea",
             ".pytest_cache", "kalshi_data", "feed_data", "fulltape",
             "results"}


def repo_files(root):
    """Every .py in the tree, as (module name, absolute path)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py") and fn != "__init__.py":
                out.append((fn[:-3], os.path.abspath(os.path.join(dirpath, fn))))
    return out


def imported_names(paths):
    """Top-level module names this repo imports, from its own source.

    Parsed rather than executed: importing the repo to find out what it imports
    is exactly the thing that fails when something is shadowed.
    """
    names = set()
    for p in paths:
        try:
            tree = ast.parse(open(p, encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for al in node.names:
                    names.add(al.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    names.add(node.module.split(".")[0])
    return names


def name_collisions(root):
    """Repo files whose name matches a stdlib module -- now or in a newer
    Python. Returns (name, path, "current" | "future")."""
    std = set(sys.stdlib_module_names)
    hits = []
    for name, path in repo_files(root):
        if name in std:
            hits.append((name, path, "current"))
        elif name in FUTURE_STDLIB:
            hits.append((name, path, "future"))
    return sorted(hits)


# The probe runs in a CHILD interpreter, and that is not a detail.
#
# The first version did it in-process: delete the name from sys.modules,
# re-import, look at __file__. The list of names to probe is "every stdlib
# module this repo imports", and this repo imports `sys` -- so the probe
# deleted `sys` from sys.modules and re-imported it, producing a module object
# with no `stderr`. Every name probed alphabetically after it then died with
# `AttributeError: module 'sys' has no attribute 'stderr'`. On Linux 3.11 it
# survived by luck and reported clean; on Windows 3.14 it failed, and the
# preflight built to stop a broken run became the thing that stopped it.
#
# That is the SAME failure as the bug this file exists to catch: behaviour that
# differs between the machine the code is written on and the machine that runs
# it, where the writing machine says fine. A checker must not be able to do
# that, so it no longer mutates the interpreter it runs in at all.
#
# The child uses ONLY `sys` and builtins. Built-in modules are resolved by
# BuiltinImporter before any path entry is consulted, so a research/sys.py
# could not shadow them -- which means the child's own machinery cannot be
# fooled by the thing it is looking for. Importing json or importlib up front
# to do the reporting WOULD be fooled: it would load the real one before the
# repo path went on, then report the name clean.
_CHILD = r"""
import sys
sys.path.insert(0, sys.argv[1])
for n in sys.argv[2:]:
    try:
        m = __import__(n)
    except BaseException as e:
        nm = getattr(e, "name", None) or ""
        print("\t".join(["ERR", n, type(e).__name__ + ": " + str(e), str(nm)]))
        continue
    f = getattr(m, "__file__", None) or ""
    print("\t".join(["OK", n, f, ""]))
"""


def import_probe(pkg_dir, root, names):
    """Import each name in a FRESH interpreter with `pkg_dir` first on
    sys.path, exactly as a stage is launched, and report where each came from.

    Returns (failures, hijacked, absent).
    """
    import subprocess
    root = os.path.abspath(root)
    probe = [n for n in sorted(names)
             if n in sys.stdlib_module_names or n in FUTURE_STDLIB]
    if not probe:
        return [], [], []
    try:
        p = subprocess.run(
            [sys.executable, "-c", _CHILD, os.path.abspath(pkg_dir)] + probe,
            capture_output=True, text=True, timeout=180)
    except Exception as e:
        return [("<probe>", f"could not launch the child interpreter: "
                            f"{type(e).__name__}: {e}")], [], []
    failures, hijacked, absent, seen = [], [], [], set()
    for line in (p.stdout or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        kind, name, detail, errname = parts
        seen.add(name)
        if kind == "OK":
            if detail and os.path.abspath(detail).startswith(root + os.sep):
                hijacked.append((name, os.path.abspath(detail)))
        else:
            if errname == name and detail.startswith("ModuleNotFoundError"):
                # The module itself is absent -- winreg on Linux, msvcrt on
                # POSIX. A platform difference, not a shadow. A real shadow
                # reports a DIFFERENT name: the 3.14 bug raised "No module
                # named 'compression._common'" while importing gzip.
                absent.append(name)
            else:
                failures.append((name, detail))
    missed = [n for n in probe if n not in seen]
    if missed:
        # The child died partway. Whatever it was importing when it stopped is
        # worth knowing about, so report it rather than silently passing.
        failures.append(("<probe>", f"the child interpreter stopped after "
                                    f"{len(seen)} of {len(probe)} imports "
                                    f"(exit {p.returncode}); not reached: "
                                    + ", ".join(missed[:8])
                                    + (" ..." if len(missed) > 8 else "")
                                    + ((" | stderr: " + p.stderr.strip()[-300:])
                                       if p.stderr.strip() else "")))
    return failures, hijacked, absent


def check(root, pkg_dir=None):
    root = os.path.abspath(root)
    pkg_dir = os.path.abspath(pkg_dir or os.path.join(root, "research"))
    if not os.path.isdir(pkg_dir):
        pkg_dir = root
    files = repo_files(root)
    names = imported_names([p for _, p in files])
    coll = name_collisions(root)
    failures, hijacked, absent = import_probe(pkg_dir, root, names)
    return {"root": root, "pkg_dir": pkg_dir, "files": len(files),
            "probed": len([n for n in names
                           if n in sys.stdlib_module_names or n in FUTURE_STDLIB]),
            "collisions": coll, "failures": failures,
            "hijacked": hijacked, "absent": sorted(absent)}


def report(res):
    print("=" * 78)
    print("STDLIB SHADOWING")
    print("=" * 78)
    print(f"  {res['files']} python files under {res['root']}")
    print(f"  probing {res['probed']} stdlib modules with {res['pkg_dir']}")
    print("  first on sys.path, the way every stage arranges it\n")
    bad = False
    for name, path, when in res["collisions"]:
        bad = True
        if when == "current":
            print(f"  *** {os.path.relpath(path, res['root'])} shadows the "
                  f"stdlib module `{name}` on THIS Python ({sys.version_info.major}."
                  f"{sys.version_info.minor}).")
        else:
            print(f"  *** {os.path.relpath(path, res['root'])} shadows `{name}`,"
                  " which is stdlib in a NEWER Python than this one.")
            print("      It will not break here. It will break on the machine")
            print("      that has that Python, and only there.")
    for name, err in res["failures"]:
        bad = True
        print(f"  *** `import {name}` FAILED with the repo on sys.path: {err}")
    for name, path in res["hijacked"]:
        bad = True
        print(f"  *** `import {name}` resolved to "
              f"{os.path.relpath(path, res['root'])}, not the stdlib.")
    if res.get("absent"):
        print("  (absent on this platform, so not probed: "
              + ", ".join(res["absent"]) + ")")
    if not bad:
        print("  clean -- nothing in this repo shadows a stdlib module, on this")
        print("  Python or on any newer one this file knows about.")
    return not bad


# ===========================================================================
def selftest():
    import tempfile
    import textwrap
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    def world(files):
        d = tempfile.mkdtemp(prefix="shadow_")
        os.makedirs(os.path.join(d, "research"), exist_ok=True)
        for name, body in files.items():
            with open(os.path.join(d, "research", name), "w",
                      encoding="utf-8") as f:
                f.write(textwrap.dedent(body))
        return d

    # --- 1. a clean tree must be clean ------------------------------------
    d = world({"thing.py": "import gzip\nimport json\n"})
    r = check(d)
    print(f"\n  clean tree: {len(r['collisions'])} collisions, "
          f"{len(r['failures'])} import failures, "
          f"{len(r['hijacked'])} hijacks")
    if r["collisions"] or r["failures"] or r["hijacked"]:
        fails.append("a tree with no shadowing was reported as shadowed")

    # --- 2. THE ACTUAL BUG, on an interpreter that cannot feel it ---------
    # This is the case that shipped. On 3.14 the import probe catches it; on
    # 3.11 nothing does, unless the forward-compatibility list is consulted.
    d = world({"thing.py": "import gzip\n",
               "compression.py": "X = 1\n"})
    r = check(d)
    fut = [c for c in r["collisions"] if c[0] == "compression"]
    probe_caught = bool(r["failures"] or r["hijacked"])
    print(f"\n  a research/compression.py, on Python "
          f"{sys.version_info.major}.{sys.version_info.minor}:")
    print(f"    name scan flags it: {'YES' if fut else 'NO'}")
    print(f"    import probe flags it: {'YES' if probe_caught else 'NO'}"
          + ("  (this Python's gzip does not import it)" if not probe_caught
             else ""))
    if not fut:
        fails.append("research/compression.py was NOT flagged -- this is the "
                     "exact file that broke every data stage on 3.14, and the "
                     "check that is supposed to catch it did not")

    # --- 3. a shadow this interpreter CAN feel ----------------------------
    d = world({"thing.py": "import gzip\n", "gzip.py": "X = 1\n"})
    r = check(d)
    caught = any(n == "gzip" for n, _, _ in r["collisions"]) or \
        any(n == "gzip" for n, _ in r["hijacked"]) or \
        any(n == "gzip" for n, _ in r["failures"])
    print(f"\n  a research/gzip.py: flagged = {'YES' if caught else 'NO'}")
    if not caught:
        fails.append("a file literally named gzip.py was not flagged")

    # --- 4. the probe must actually LOAD, not just name-match -------------
    # A module that shadows by name AND imports cleanly must still be caught
    # by __file__, not silently accepted.
    d = world({"thing.py": "import json\n",
               "json.py": "def loads(s):\n    return None\n"})
    r = check(d)
    hij = [n for n, _ in r["hijacked"]]
    print(f"  a research/json.py that imports fine: hijack detected = "
          f"{'YES' if 'json' in hij or any(n == 'json' for n, _, _ in r['collisions']) else 'NO'}")
    if "json" not in hij and not any(n == "json" for n, _, _ in r["collisions"]):
        fails.append("a working-but-shadowing json.py was accepted")

    # --- 3b. A TRANSITIVE SHADOW, which is the shape that actually shipped -
    # The bug was never that we imported `compression`. Nothing in this repo
    # mentions that name. It was that `gzip` imports it, so the shadow was
    # reached through a module we DO import. A name scan alone cannot see that
    # shape, which is why the probe exists.
    #
    # It can be reproduced exactly on Pythons before 3.14, where gzip imports
    # `_compression` with an underscore for the same purpose. Same mechanism,
    # different name, and this interpreter can actually run it.
    if "_compression" in sys.stdlib_module_names:
        d = world({"thing.py": "import gzip\n", "_compression.py": "X = 1\n"})
        r = check(d)
        got = [n for n, _ in r["failures"]]
        print("\n  A transitive shadow (research/_compression.py, reached only")
        print("  through `import gzip` -- the same shape as the 3.14 bug):")
        for n, e in r["failures"]:
            print(f"    {n}: {e}")
        if "gzip" not in got:
            fails.append("a shadow reached THROUGH gzip was not detected -- "
                         "this is the exact shape that broke fourteen stages, "
                         "and a name scan alone cannot see it")
    else:
        print("\n  (the transitive-shadow reproduction needs a Python whose")
        print("   gzip imports _compression; this one does not, so it is")
        print("   skipped rather than silently passed)")

    # --- 4b. THE CHECKER MUST NOT DAMAGE THE INTERPRETER IT RUNS IN -------
    # The first version of import_probe deleted names from sys.modules and
    # re-imported them. `sys` is on the probe list, because this repo imports
    # sys everywhere, so it deleted and rebuilt `sys` -- and every name probed
    # alphabetically after it died with "module 'sys' has no attribute
    # 'stderr'". It survived on Linux 3.11 and killed the run on Windows 3.14.
    # A checker that can do that is worse than no checker.
    print("\n  The probe must not touch the interpreter running it. Probing")
    print("  the most dangerous names there are -- sys, builtins, io,")
    print("  importlib -- and checking this process is unharmed afterwards.")
    before = {
        "stderr": getattr(sys, "stderr", None),
        "stdout": getattr(sys, "stdout", None),
        "sys_is_sys": sys.modules.get("sys") is sys,
        "path": list(sys.path),
        "nmods": len(sys.modules),
    }
    d = world({"thing.py": "import sys\nimport io\nimport builtins\n"
                           "import importlib\nimport threading\nimport zipfile\n"})
    r = check(d)
    after_ok = (getattr(sys, "stderr", None) is before["stderr"]
                and getattr(sys, "stdout", None) is before["stdout"]
                and sys.modules.get("sys") is sys
                and list(sys.path) == before["path"])
    print(f"    sys.stderr intact:            {getattr(sys, 'stderr', None) is before['stderr']}")
    print(f"    sys.stdout intact:            {getattr(sys, 'stdout', None) is before['stdout']}")
    print(f"    sys.modules['sys'] is sys:    {sys.modules.get('sys') is sys}")
    print(f"    sys.path unchanged:           {list(sys.path) == before['path']}")
    print(f"    probe reported {len(r['failures'])} failures on a clean tree")
    if not after_ok:
        fails.append("import_probe damaged the interpreter it was running in "
                     "-- this is the exact defect that killed the 19:48 run")
    if r["failures"]:
        fails.append(f"probing sys/io/builtins/importlib on a CLEAN tree "
                     f"reported failures: {r['failures']}")

    # --- 5. the real repo, which is the point -----------------------------
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    print("\n" + "-" * 78)
    ok = report(check(repo, here))
    if not ok:
        fails.append("this repository currently shadows a stdlib module")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- catches a shadow this Python can feel, catches")
    print("the 3.14 `compression` shadow on a Python that cannot, and reports")
    print("this repository clean.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="..")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    here = os.path.dirname(os.path.abspath(__file__))
    raise SystemExit(0 if report(check(a.root, here)) else 1)


if __name__ == "__main__":
    main()
