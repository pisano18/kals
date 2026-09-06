#!/usr/bin/env python3
# VERSION: 2026-09-06-d1
"""deploycheck.py -- the deployed copies must match the repo.

WHY THIS EXISTS, AND IT IS NOT HYPOTHETICAL.

`CLAUDE.md` documents the deployment process as: add a series to `CRYPTO_15M`
in `kalshi_collector.py`, copy the file to `C:\\kals`, done. On 2026-09-06 that
process was followed exactly -- five commodity 15-minute series added, file
copied, verified byte-identical -- and the collector came back running the OLD
fourteen series.

The reason was in a DIFFERENT file. `C:\\kals\\run_all.ps1` carried an explicit

    --series KXBTC15M KXETH15M ... KXCRYPTOCOMP15M

that the repo's copy does not, and an explicit `--series` overrides the
`CRYPTO_15M` default. So the documented process could never work, and had been
unable to work for an unknown length of time. `CRYPTO_15M`'s own comment even
records a previous instance of this exact trap ("everything.py once patched
run_all.ps1 to add them via --series and it never took effect") -- and the trap
was still live, one file over.

Silent drift between repo and deployment is worse than a crash, because
everything keeps running and only the DATA is wrong. This makes it loud.

Line endings are ignored: the repo is checked out with CRLF on Windows and a
copy may normalise them. Nothing else is ignored.

    python deploycheck.py            # check, exit 1 on drift
    python deploycheck.py --selftest
"""
import argparse
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
DEPLOY = r"C:\kals"

# (repo-relative path, deployed path). Only files whose CONTENT drives
# collection belong here -- a stale analysis file is caught by git.
WATCHED = [
    ("kalshi_collector.py", "kalshi_collector.py"),
    ("run_all.ps1", "run_all.ps1"),
    ("crypto_feeds.py", "crypto_feeds.py"),
]


def norm(path):
    """Bytes with line endings normalised, or None if unreadable."""
    try:
        with open(path, "rb") as f:
            return f.read().replace(b"\r\n", b"\n")
    except OSError:
        return None


def check(repo=REPO, deploy=DEPLOY, verbose=True):
    problems = []
    for rel, dep in WATCHED:
        rp = os.path.join(repo, rel)
        dp = os.path.join(deploy, dep)
        a, b = norm(rp), norm(dp)
        if a is None:
            problems.append(f"{rel}: MISSING FROM THE REPO at {rp}")
            continue
        if b is None:
            # Not deployed at all is only a problem if the deploy dir exists;
            # on a container with no C:\kals this check must not fire.
            if os.path.isdir(deploy):
                problems.append(f"{rel}: NOT DEPLOYED to {dp}")
            continue
        if a != b:
            ha, hb = hashlib.sha256(a).hexdigest()[:12], \
                hashlib.sha256(b).hexdigest()[:12]
            la, lb = a.decode("utf-8", "replace").splitlines(), \
                b.decode("utf-8", "replace").splitlines()
            first = next((i + 1 for i, (x, y) in enumerate(zip(la, lb))
                          if x != y), min(len(la), len(lb)) + 1)
            problems.append(
                f"{rel}: DRIFT  repo {ha} != deployed {hb}  "
                f"first difference at line {first}")
            if verbose and first <= len(la) and first <= len(lb):
                problems.append(f"      repo     : {la[first-1][:96]}")
                problems.append(f"      deployed : {lb[first-1][:96]}")
    if verbose:
        print("=" * 78)
        print("DEPLOY CHECK -- repo vs C:\\kals, line endings ignored")
        print("=" * 78)
        if not os.path.isdir(deploy):
            print(f"  {deploy} does not exist -- not the operator's box, "
                  f"nothing to check.")
            return []
        for rel, _ in WATCHED:
            print(f"  watching {rel}")
        if problems:
            print()
            for p in problems:
                print("  " + p)
            print("\n  A deployed file that differs from the repo means the")
            print("  documented deployment process is a lie and the collector")
            print("  may be recording something other than what the repo says.")
            print("  Fix by copying the repo file over, then RESTART the")
            print("  watchdog -- PowerShell parses run_all.ps1 at launch, so")
            print("  editing it does not affect a running instance.")
        else:
            print("\n  clean -- every watched file matches the repo.")
    return problems


def selftest():
    import tempfile
    import shutil
    print("=" * 78)
    print("SELF-TEST -- deploycheck must SEE drift and must IGNORE line endings")
    print("=" * 78)
    fails = []
    d = tempfile.mkdtemp()
    try:
        repo = os.path.join(d, "repo")
        dep = os.path.join(d, "dep")
        os.makedirs(repo)
        os.makedirs(dep)
        for rel, _ in WATCHED:
            with open(os.path.join(repo, rel), "wb") as f:
                f.write(b"line one\nline two\nline three\n")

        # 1. identical -> clean
        for rel, _ in WATCHED:
            shutil.copy(os.path.join(repo, rel), os.path.join(dep, rel))
        p = check(repo, dep, verbose=False)
        print(f"  identical files            -> {len(p)} problems")
        if p:
            fails.append("identical trees reported drift")

        # 2. CRLF only -> still clean
        for rel, _ in WATCHED:
            with open(os.path.join(dep, rel), "wb") as f:
                f.write(b"line one\r\nline two\r\nline three\r\n")
        p = check(repo, dep, verbose=False)
        print(f"  line endings differ only   -> {len(p)} problems")
        if p:
            fails.append("CRLF-vs-LF alone was reported as drift")

        # 3. a real change -> caught. This is the run_all.ps1 --series case.
        with open(os.path.join(dep, "run_all.ps1"), "wb") as f:
            f.write(b"line one\nline two --series KXBTC15M\nline three\n")
        p = check(repo, dep, verbose=False)
        print(f"  one line differs           -> {len(p)} problems")
        if not any("run_all.ps1" in x and "DRIFT" in x for x in p):
            fails.append("a real content difference was NOT caught")

        # 4. missing from deployment -> caught
        os.remove(os.path.join(dep, "crypto_feeds.py"))
        p = check(repo, dep, verbose=False)
        print(f"  file missing from deploy   -> {len(p)} problems")
        if not any("NOT DEPLOYED" in x for x in p):
            fails.append("a file missing from the deployment was NOT caught")

        # 5. a deploy dir that does not exist must be silent, not a failure
        p = check(repo, os.path.join(d, "nope"), verbose=False)
        print(f"  no deploy dir at all       -> {len(p)} problems")
        if p:
            fails.append("a missing deploy dir was reported as drift -- this "
                         "would fail every run on a container")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print()
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        return False
    print("SELF-TEST PASSED -- sees a one-line change, ignores line endings,")
    print("catches a file missing from the deployment, and stays silent where")
    print("there is no deployment to check.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--deploy", default=DEPLOY)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    raise SystemExit(1 if check(deploy=a.deploy) else 0)


if __name__ == "__main__":
    main()
