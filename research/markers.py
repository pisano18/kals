#!/usr/bin/env python3
"""markers.py -- a stage must not SAY it loaded nothing unless it did.

    python research/markers.py --selftest
    python research/markers.py ..

WHY

go.py decides whether a stage loaded real data by scanning its output for
EMPTY_MARKERS -- phrases like "no quotes" that a loader prints when it comes
back with nothing. That is a crude protocol and go.py's own comment says so,
along with the reason it matters:

    "A false EMPTY is worse than no flag at all: it buries a real result
     under the one label that says 'do not read this'."

It happened anyway, on the 2026-08-28 23:00 run. endgame.py printed

    Read the quote-seconds column first. An edge in a bucket with
    no quotes is not an edge.

as ordinary prose under a table of 89,757 quote-seconds and a full settlement
P&L, and go.py flagged the whole stage EMPTY. The result was real, and the
label told the reader to discard it.

THE RULE, AND WHY IT IS CHECKABLE

Every genuine use of these phrases has the same shape: a loader came back
empty, the stage says so, and the stage STOPS. Every false use is prose in the
middle of a report that carries on afterwards. So:

    a print() containing an EMPTY_MARKER must be on a path that ends --
    a return, a raise, or a SystemExit -- in the same block.

That is decidable from the syntax tree, needs no allowlist to maintain, and
fails loudly the next time someone writes the phrase into an explanation.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import ast
import os
import re
import sys

TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def markers_from(go_path):
    """The live EMPTY_MARKERS list, read from go.py rather than copied.

    Copying it would let the two drift, and a checker that guards a stale copy
    of the rule guards nothing.
    """
    src = open(go_path, encoding="utf-8").read()
    a = src.index("EMPTY_MARKERS = (")
    b = src.index(")", src.index("\n", a))
    return re.findall(r'r?"((?:[^"\\]|\\.)*)"', src[a:b])


def _ends_here(block, idx):
    """Does this one block terminate at or after index `idx`?

    A loader that reports and stops may print two or three explanatory lines
    first, but it must not go on to compute anything. Any statement that is
    not a bare print() disqualifies it.
    """
    for st in block[idx:]:
        if isinstance(st, TERMINATORS):
            return True
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
            fn = st.value.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name in ("print", "log", "Say"):
                continue
            return False
        if isinstance(st, ast.Pass):
            continue
        return False
    return False              # ran off the end of this block


def _ends(chain):
    """Does the path terminate, looking outward through enclosing blocks?

    The common genuine shape puts the print one level in from the return:

        if not seen:
            if verbose:
                print("  quotes: no ticker messages on disk")
            return {}

    Checking only the `if verbose:` body finds no terminator and calls a
    correct loader wrong -- which is the same class of mistake as the one this
    file exists to catch, so it is not enough to check the innermost block.
    `chain` is [(block, index), ...] innermost first.
    """
    for i, (block, idx) in enumerate(chain):
        if _ends_here(block, idx if i == 0 else idx + 1):
            return True
    return False


def offenders(root, go_path):
    pats = [(m, re.compile(m, re.I)) for m in markers_from(go_path)]
    out = []
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", "results",
                                    "kalshi_data", "feed_data", "fulltape"}]
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            if os.path.abspath(path) == os.path.abspath(go_path):
                continue                     # go.py DEFINES the markers
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except (OSError, SyntaxError):
                continue
            def walk(node, chain):
                for field in ("body", "orelse", "finalbody"):
                    body = getattr(node, field, None)
                    if not isinstance(body, list):
                        continue
                    for i, st in enumerate(body):
                        here = [(body, i)] + chain
                        if (isinstance(st, ast.Expr)
                                and isinstance(st.value, ast.Call)
                                and getattr(st.value.func, "id", None)
                                == "print"):
                            text = " ".join(
                                a.value for a in ast.walk(st.value)
                                if isinstance(a, ast.Constant)
                                and isinstance(a.value, str))
                            hit = next((m for m, p in pats
                                        if p.search(text)), None)
                            if hit and not _ends(here):
                                out.append((os.path.relpath(path, root),
                                            st.lineno, hit,
                                            text.strip()[:70]))
                        walk(st, here)
                for h in getattr(node, "handlers", []) or []:
                    walk(h, chain)

            walk(tree, [])
    return out


def report(root, go_path):
    bad = offenders(root, go_path)
    print("=" * 78)
    print("EMPTY-MARKER PROSE")
    print("=" * 78)
    print(f"  markers: {', '.join(markers_from(go_path))}\n")
    for path, line, marker, text in bad:
        print(f"  *** {path}:{line} prints /{marker}/ and then CARRIES ON.")
        print(f"      {text!r}")
        print("      go.py will flag this stage EMPTY and tell the reader to")
        print("      discard a result that is real. Reword it.")
    if not bad:
        print("  clean -- every stage that says it loaded nothing then stops.")
    return not bad


# ===========================================================================
def selftest():
    import tempfile
    import textwrap
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []
    here = os.path.dirname(os.path.abspath(__file__))
    go = os.path.join(here, "go.py")

    ms = markers_from(go)
    print(f"\n  read {len(ms)} markers live from go.py: {ms}")
    if "\\bno quotes\\b" not in ms:
        fails.append("did not read the no-quotes marker out of go.py -- the "
                     "list is parsed from go.py on purpose so the two cannot "
                     "drift, and that parse just failed")

    d = tempfile.mkdtemp(prefix="markers_")

    def write(name, body):
        p = os.path.join(d, name)
        open(p, "w", encoding="utf-8").write(textwrap.dedent(body))
        return p

    # the GENUINE shape: report and stop
    write("good.py", '''
        def main():
            q = load()
            if not q:
                print("  no quotes -- nothing to measure. Run doctor.py.")
                return
            print(q)
        ''')
    # the shape that shipped: prose, then the report carries on
    write("bad.py", '''
        def main():
            print("  Read the quote-seconds column first. An edge in a")
            print("  bucket with no quotes is not an edge.")
            table = compute()
            print(table)
        ''')
    # report-and-raise counts as stopping
    write("raises.py", '''
        def main():
            if not load():
                print("no ticker messages on disk")
                raise SystemExit(1)
            print("ok")
        ''')
    bad = offenders(d, go)
    names = sorted(b[0] for b in bad)
    print(f"\n  {'fixture':>12}   flagged?")
    for n in ("good.py", "bad.py", "raises.py"):
        print(f"  {n:>12}   {'YES' if n in names else 'no'}")
    if "bad.py" not in names:
        fails.append("the exact shape that shipped -- prose containing a "
                     "marker, followed by a table -- was NOT flagged")
    if "good.py" in names:
        fails.append("a genuine report-and-return loader message was flagged")
    if "raises.py" in names:
        fails.append("report-and-raise was flagged; raising is stopping")

    import shutil
    shutil.rmtree(d, ignore_errors=True)

    print("\n" + "-" * 78)
    ok = report(os.path.dirname(here), go)
    if not ok:
        fails.append("this repository currently has a stage whose prose will "
                     "be read as an empty loader")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- flags prose that carries on, allows a loader")
    print("that reports and stops, and reads the marker list live from go.py.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="..")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    raise SystemExit(0 if report(os.path.abspath(a.root),
                                 os.path.join(here, "go.py")) else 1)


if __name__ == "__main__":
    main()
