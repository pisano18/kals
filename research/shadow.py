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


def import_probe(pkg_dir, root, names):
    """With `pkg_dir` first on sys.path -- as every stage arranges -- import
    each name and check where it actually came from.

    Returns (failures, hijacked) where a failure is (name, exception text) and
    a hijack is (name, the repo file it resolved to).
    """
    root = os.path.abspath(root)
    failures, hijacked, absent = [], [], []
    saved_path = list(sys.path)
    saved_mods = dict(sys.modules)
    sys.path.insert(0, os.path.abspath(pkg_dir))
    try:
        for n in sorted(names):
            if n not in sys.stdlib_module_names and n not in FUTURE_STDLIB:
                continue                      # ours, or third party
            for k in [k for k in sys.modules if k == n or k.startswith(n + ".")]:
                del sys.modules[k]
            try:
                m = importlib.import_module(n)
            except ModuleNotFoundError as e:
                if e.name == n:
                    # The module itself is absent -- winreg on Linux, msvcrt
                    # on POSIX. That is a platform difference, not a shadow.
                    # A SHADOW reports a DIFFERENT name: the 3.14 bug raised
                    # "No module named 'compression._common'" while importing
                    # gzip, never "No module named 'compression'".
                    absent.append(n)
                    continue
                failures.append((n, f"{type(e).__name__}: {e}"))
                continue
            except Exception as e:
                failures.append((n, f"{type(e).__name__}: {e}"))
                continue
            f = getattr(m, "__file__", None)
            if f and os.path.abspath(f).startswith(root + os.sep):
                hijacked.append((n, os.path.abspath(f)))
    finally:
        sys.path[:] = saved_path
        sys.modules.clear()
        sys.modules.update(saved_mods)
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
