"""unbound.py -- names a function reads but never binds, across the repo.

Why this exists: `maker.py` shipped with `hit, null = adverse_from_tape(...)`
in main() and `shuf[h]` three lines later. Every self-test passed. The stage
would have raised NameError on its first real run, at the exact point where it
prints the number the whole market-making question turns on.

No self-test in this project executes a `main()` -- they all need recorded
data that only exists on the collector's machine. So main() is the one place
where a typo survives every test until real data reaches it, which is the
worst possible moment to find out. This finds them without running anything.

It is deliberately conservative: it reports only names that are read inside a
function and bound NOWHERE -- not as a parameter, not by an assignment, not by
an import, not at module level, not as a builtin. A false positive here means
this file is wrong, so it errs toward silence.
"""

import argparse
import ast
import builtins
import os
import sys

ALWAYS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__spec__", "__package__",
    "__loader__", "__builtins__", "__debug__", "__class__",
}


def module_names(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add(a.asname or a.name.split(".")[0])
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For,
                            ast.With, ast.If, ast.Try)):
            for x in ast.walk(n):
                if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                    out.add(x.id)
    return out


def bound_in(fn):
    """Every name bound anywhere inside `fn`, nested functions included.

    Nested scopes are folded in rather than modelled properly. That
    over-counts -- a name bound only in an inner function is treated as
    available to the outer one -- which makes this MISS some real bugs. That
    is the correct direction to be wrong in: a checker that cries wolf gets
    switched off, and then catches nothing at all.
    """
    b = set()
    for x in ast.walk(fn):
        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
            b.add(x.id)
        elif isinstance(x, ast.arg):
            b.add(x.arg)
        elif isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            b.add(x.name)
        elif isinstance(x, ast.ExceptHandler) and x.name:
            b.add(x.name)
        elif isinstance(x, (ast.Import, ast.ImportFrom)):
            for a in x.names:
                b.add(a.asname or a.name.split(".")[0])
        elif isinstance(x, (ast.Global, ast.Nonlocal)):
            b.update(x.names)
    return b


NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def loads_here(fn):
    """Names READ in this function's own body, not in a nested one.

    Without this, a name genuinely unbound inside a nested function is
    reported twice -- once against the nested function, where it belongs, and
    once against the enclosing one, where it does not.

    Decorators, default arguments and base classes of a NESTED definition ARE
    evaluated in this scope, so they are still collected. This function's OWN
    defaults and decorators are not: they are evaluated in the scope that
    contains it, and are collected there.
    """
    out = set()

    def visit(node):
        if isinstance(node, NESTED):
            for d in getattr(node, "decorator_list", []):
                visit(d)
            args = getattr(node, "args", None)
            if args is not None:
                for d in list(getattr(args, "defaults", [])):
                    visit(d)
                for d in getattr(args, "kw_defaults", []):
                    if d is not None:
                        visit(d)
            for b in getattr(node, "bases", []):
                visit(b)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            out.add(node.id)
        for c in ast.iter_child_nodes(node):
            visit(c)

    for st in getattr(fn, "body", []):
        visit(st)
    return out


def free_names(fn, known):
    return sorted(loads_here(fn) - bound_in(fn) - known - ALWAYS)


def walk_scopes(node, known, out):
    """Recurse, handing every nested function the names its ENCLOSING scopes
    bind.

    The first version of this walked every FunctionDef in the tree against
    module-level names only, and reported 21 hits across the repo -- every one
    of them a closure reading an enclosing function's local, which is ordinary
    Python. A checker that reports 21 false positives is worse than no
    checker: it gets switched off, and the one real bug goes with it.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f = free_names(child, known)
            if f:
                out.append((f"{child.name}:{child.lineno}", f))
            walk_scopes(child, known | bound_in(child), out)
        elif isinstance(child, ast.ClassDef):
            walk_scopes(child, known | bound_in(child), out)
        else:
            walk_scopes(child, known, out)


def exported_by(path):
    """Top-level names a module defines: defs, classes, assignments, imports.

    Conservative on purpose. A name bound only inside an `if`/`try` at module
    level still counts, because it is reachable, and calling a real export
    missing would be a false alarm.
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError):
        return None
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
    return out


def bad_imports(path, search):
    """`from X import Y` where X is a module in this repo and Y is not in it.

    This is the bug the unbound-name check CANNOT see: the import statement
    binds Y, so every function using it looks perfectly correct. It cost two
    real runs -- `from replay import load_trades` (it is in edge.py) and
    `from engine import SERIES_TO_INDEX` (it is in replay.py). Both crashed at
    the first line of REAL DATA, after the self-tests had all passed, because
    a self-test never reaches that import.

    Only local modules are checked. A missing third-party package is a
    different problem with a different fix, and guessing at one would make
    this noisy enough to ignore.
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError):
        return []
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.ImportFrom) or n.level or not n.module:
            continue
        mod = n.module.split(".")[0]
        target = None
        for d in search:
            cand = os.path.join(d, mod + ".py")
            if os.path.isfile(cand) and os.path.abspath(cand) != \
                    os.path.abspath(path):
                target = cand
                break
        if target is None:
            continue                       # stdlib or third-party; not ours
        have = exported_by(target)
        if have is None:
            continue
        for a in n.names:
            if a.name == "*":
                continue
            if a.name not in have:
                near = sorted(x for x in have
                              if a.name.split("_")[-1] in x
                              or x.split("_")[-1] in a.name)[:3]
                out.append((f"import:{n.lineno}",
                            [f"{mod}.{a.name} does not exist"
                             + (f" (did you mean {near}?)" if near else "")]))
    return out


def scan(path):
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError) as e:
        return [("<file>", [f"{type(e).__name__}: {e}"])]
    out = []
    walk_scopes(tree, module_names(tree), out)
    out += bad_imports(path, [os.path.dirname(os.path.abspath(path)),
                              os.path.dirname(os.path.dirname(
                                  os.path.abspath(path)))])
    return out


def selftest():
    print("=" * 78)
    print("SELF-TEST -- the checker must see a real one and invent none")
    print("=" * 78)
    import shutil, tempfile
    fails = []
    CASES = [
        # `f` is defined at module level here on purpose: without it the
        # checker correctly flags `f` too, and the fixture would be asserting
        # that a genuinely undefined call is fine.
        ("the bug that shipped",
         "def f():\n    return (1, 2)\n"
         "def main():\n    hit, null = f()\n    return shuf[1]\n", ["shuf"]),
        ("parameter", "def g(a, b=2):\n    return a + b\n", []),
        ("module global",
         "X = 3\ndef g():\n    return X\n", []),
        ("import", "import os\ndef g():\n    return os.sep\n", []),
        ("from-import as",
         "from x import y as z\ndef g():\n    return z\n", []),
        ("builtin", "def g():\n    return len([])\n", []),
        ("comprehension target",
         "def g(xs):\n    return [i for i in xs]\n", []),
        ("except alias",
         "def g():\n    try:\n        pass\n    except OSError as e:\n"
         "        return e\n", []),
        ("nested function's name",
         "def g():\n    def h():\n        return 1\n    return h()\n", []),
        ("walrus", "def g(xs):\n    if (n := len(xs)):\n        return n\n",
         []),
        ("augmented assign at module level",
         "T = 0\ndef g():\n    return T\n", []),
        ("for target", "def g(xs):\n    for i in xs:\n        pass\n"
                       "    return i\n", []),
        ("global decl",
         "def g():\n    global Q\n    Q = 1\n    return Q\n", []),
        ("class attribute is not a free name",
         "class C:\n    z = 1\ndef g():\n    return C.z\n", []),
        # closures: the 21 false positives the first version produced
        ("closure over an enclosing local",
         "def g(xs):\n    m = {}\n    def h(k):\n        return m[k]\n"
         "    return h(xs)\n", []),
        ("closure over an enclosing parameter",
         "def g(a):\n    def h():\n        return a\n    return h()\n", []),
        ("closure two levels deep",
         "def g():\n    q = 1\n    def h():\n        def i():\n"
         "            return q\n        return i()\n    return h()\n", []),
        ("closure defined inside an if",
         "def g(a):\n    if a:\n        def h():\n            return a\n"
         "        return h()\n", []),
        ("a nested function CAN still be wrong",
         "def g(a):\n    def h():\n        return nope\n    return h()\n",
         ["nope"]),
        ("method reading a genuinely unbound name",
         "class C:\n    def m(self):\n        return missing\n", ["missing"]),
    ]
    print(f"  {'case':>36}{'expected':>12}{'got':>22}")
    for name, src, want in CASES:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                          encoding="utf-8")
        tmp.write(src)
        tmp.close()
        try:
            got = sorted(n for _f, names in scan(tmp.name) for n in names)
        finally:
            os.unlink(tmp.name)
        ok = got == want
        print(f"  {name:>36}{str(want):>12}{str(got):>22}"
              + ("" if ok else "   *** WRONG ***"))
        if not ok:
            fails.append(f"{name}: expected {want}, got {got}")

    # ---- cross-module imports: the bug the scope check cannot see --------
    print("\n  IMPORT RESOLUTION. `from X import Y` BINDS Y, so every use of")
    print("  it passes the scope check above. Two real runs crashed on this:")
    print("  `from replay import load_trades` (it is in edge.py) and")
    print("  `from engine import SERIES_TO_INDEX` (it is in replay.py). Both")
    print("  died at the first line of REAL DATA, long after the self-tests.")
    tmpd = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmpd, "lib.py"), "w", encoding="utf-8") as f:
            f.write("VALUE = 1\ndef real_fn():\n    return VALUE\n"
                    "class Thing:\n    pass\n")
        CASES2 = [
            ("existing function", "from lib import real_fn\n", 0),
            ("existing constant", "from lib import VALUE\n", 0),
            ("existing class", "from lib import Thing\n", 0),
            ("aliased", "from lib import real_fn as f\n", 0),
            ("several, all real",
             "from lib import VALUE, real_fn, Thing\n", 0),
            ("MISSING name", "from lib import nope\n", 1),
            ("one real one missing",
             "from lib import real_fn, nope\n", 1),
            ("stdlib is not ours", "from json import loads\n", 0),
            ("unknown third party", "from numpy import array\n", 0),
            ("star import is not checked", "from lib import *\n", 0),
            ("import inside a function",
             "def g():\n    from lib import nope\n    return nope\n", 1),
        ]
        print(f"\n  {'case':>28}{'expected':>10}{'found':>8}")
        for name, src, want in CASES2:
            fp = os.path.join(tmpd, "case.py")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(src)
            got = len([h for h in scan(fp) if h[0].startswith("import:")])
            print(f"  {name:>28}{want:>10}{got:>8}"
                  + ("" if got == want else "   *** WRONG ***"))
            if got != want:
                fails.append(f"import case '{name}': expected {want} hits, "
                             f"got {got}")
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- catches the bug that shipped and stays silent")
    print("on parameters, globals, imports, comprehensions, except aliases,")
    print("nested definitions, walrus targets, for targets and closures --")
    print("while still catching a nested function that IS wrong.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to report")

    roots = a.paths or ["."]
    files = []
    for r in roots:
        if os.path.isfile(r):
            files.append(r)
            continue
        for d, _sub, names in os.walk(r):
            if any(p in d for p in (".git", "__pycache__")):
                continue
            files += [os.path.join(d, n) for n in names if n.endswith(".py")]
    files.sort()
    print("=" * 78)
    print(f"UNBOUND NAMES across {len(files)} files")
    print("=" * 78)
    bad = 0
    for f in files:
        hits = scan(f)
        for where, names in hits:
            bad += 1
            print(f"  {f}:{where}  reads {names} but never binds them")
    if not bad:
        print("  clean -- no function reads a name it never binds.")
    print("\n  A hit here is a NameError waiting for the first run that")
    print("  reaches that line. main() is where they hide, because no")
    print("  self-test in this project executes one.")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
