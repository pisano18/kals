#!/usr/bin/env python3
# VERSION: 2026-09-13-vc1
"""versioncheck.py -- a live flag with no version entry is an error.

THE OPERATOR, 2026-09-13: "Can we start naming update versions so it's easier
to revert when something goes bad? are you able to keep a version history log?
Can you fill in the past versions and add something so future bots know to add
to the log?"

`results/VERSIONS.md` already existed and was good. It had also LAPSED: eight
live changes went out between 2026-09-11 and 2026-09-13 and none of them was
logged. Nobody noticed, because nothing checks.

This checks. It compares the arguments in `restart_bot.ps1` -- which is what
actually launches the money -- against the text of VERSIONS.md, and fails if
the bot is running a flag the log has never heard of. That is the narrow
version of the question, and the narrow version is the one that can be
enforced mechanically:

    A FLAG THAT CHANGES WHAT TRADES MUST APPEAR IN THE LOG.

It deliberately does NOT try to verify that entries are truthful, complete, or
current. A check that tried would be unmaintainable and would be switched off
inside a week. This one has a single failure mode and no false positives that
cannot be fixed by writing the entry that should have been written.

Run it in any session that touches the live bot:

    python research/versioncheck.py
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LAUNCHER = os.path.join(REPO, "restart_bot.ps1")
VERSIONS = os.path.join(REPO, "results", "VERSIONS.md")

# Flags that only affect logging, paths or run length change nothing about
# what trades, so they need no version entry.
BORING = {
    "--live", "--size", "--minutes", "--loss-abort", "--max-positions",
    "--max-losses", "-u",
}

FLAG = re.compile(r'"(--[a-z0-9-]+)"')


def launcher_flags(path=LAUNCHER):
    """Every --flag the launcher passes, minus the boring ones."""
    if not os.path.exists(path):
        return None, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    found = []
    for m in FLAG.finditer(src):
        f = m.group(1)
        if f not in BORING and f not in found:
            found.append(f)
    return src, found


def flag_values(src, flag):
    """The literal value passed after `flag`, if the launcher gives one."""
    m = re.search(re.escape('"%s"' % flag) + r'\s*,\s*"([^"]+)"', src)
    return m.group(1) if m else None


def check(launcher=LAUNCHER, versions=VERSIONS, say=print):
    """(ok, [problem, ...])."""
    problems = []
    src, flags = launcher_flags(launcher)
    if src is None:
        return False, ["%s does not exist -- nothing launches the bot" %
                       launcher]
    if not os.path.exists(versions):
        return False, ["%s does not exist" % versions]
    with open(versions, encoding="utf-8", errors="replace") as fh:
        log = fh.read()
    for f in flags:
        if f not in log:
            problems.append(
                "the launcher passes %s but %s never mentions it -- write the "
                "version entry before this runs again"
                % (f, os.path.basename(versions)))
            continue
        v = flag_values(src, f)
        if v and v not in log:
            problems.append(
                "the launcher passes %s %s but %s mentions %s without that "
                "value -- the log describes a DIFFERENT version from the one "
                "deployed" % (f, v, os.path.basename(versions), f))
    if say:
        if problems:
            say("versioncheck: %d PROBLEM(S)" % len(problems))
            for p in problems:
                say("  - " + p)
        else:
            say("versioncheck: clean -- every live flag (%s) appears in "
                "VERSIONS.md" % (", ".join(flags) if flags else "none"))
    return (not problems), problems


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="versioncheck-")
    try:
        lp = os.path.join(tmp, "launch.ps1")
        vp = os.path.join(tmp, "V.md")
        with open(lp, "w", encoding="utf-8") as fh:
            fh.write('Start-Process -ArgumentList @(\n'
                     '  "-u", "run.py",\n'
                     '  "--live", "--size", "20",\n'
                     '  "--sigma-ruler", "maxdown"\n)\n')
        with open(vp, "w", encoding="utf-8") as fh:
            fh.write("## v-a20b -- --sigma-ruler maxdown deployed\n")
        ok, probs = check(lp, vp, say=None)
        ck(ok, "a logged flag passes (%s)" % probs)

        with open(vp, "w", encoding="utf-8") as fh:
            fh.write("## v-old -- nothing here mentions the ruler\n")
        ok, probs = check(lp, vp, say=None)
        ck(not ok and "--sigma-ruler" in probs[0],
           "an UNLOGGED live flag fails, naming the flag")

        with open(vp, "w", encoding="utf-8") as fh:
            fh.write("## v-a20 -- --sigma-ruler max3600 deployed\n")
        ok, probs = check(lp, vp, say=None)
        ck(not ok and "maxdown" in probs[0],
           "and a flag logged with the WRONG VALUE fails too -- 'max3600' in "
           "the log while 'maxdown' is deployed is exactly the failure this "
           "exists to catch")

        with open(lp, "w", encoding="utf-8") as fh:
            fh.write('"-u", "--live", "--size", "20", "--minutes", "4320"\n')
        ok, probs = check(lp, vp, say=None)
        ck(ok, "flags that change nothing about what trades need no entry")

        ok, probs = check(os.path.join(tmp, "nope.ps1"), vp, say=None)
        ck(not ok, "a missing launcher is a failure, not a pass")

        # the REAL repo must be clean, or this file is pointless
        ok, probs = check(say=None)
        ck(ok, "and the live launcher is clean right now (%s)" % probs)
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    print("versioncheck selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    ok, _p = check()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
