"""test_ops.py -- the 11-07 ops fixes that no other test reads (the 11-07 tests review: the snapshot, the version pins
and the installer had no test, and nothing in the /update gate ran the three new self-tests):

  * logfiles.py --selftest, log_rotate.py --self-test and pinflat.py --selftest pass, each in its own `python -I`
    (the way the server runs them), pinflat with NOTHING on stderr -- so botstats --selftest, the phone's /update
    gate, now runs all three;
  * results/live_launcher_snapshot/: each file's sha256 is the one SHA256SUMS.txt names (LF, sha256sum format), the
    .gitattributes keeps them byte-exact, and both launchers still read pinflat by exit code (its contract);
    LIVE_PATHS.txt gives every snapshot name its live file (the README's table agrees), and kalshi_watch's launcher
    check on the committed list hashes those live files (planted: 2 of 2 match, one changed byte drifts) -- 11-08;
  * results/requirements-server.txt: exactly the six pins of 11-07, said to be a record, not an install list;
  * results/log_rotate_install.ps1: task KalsLogRotate as SYSTEM, `--apply` and the git it found in the action, the
    next 09:40 UTC, the self-test gate BEFORE the task is registered, the phone's marker, and (where PowerShell is
    on this machine) no parse error.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_ops.py   (botstats.py --selftest runs it too)
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import _kit                                                          # noqa: E402  (sys.path, KALS_TESTING=1)
from _kit import ck                                                  # noqa: E402

RESEARCH = _kit.RESEARCH
REPO = os.path.dirname(RESEARCH)
RESULTS = os.path.join(REPO, "results")
SNAP = os.path.join(RESULTS, "live_launcher_snapshot")


def _child(args, timeout=240):
    return subprocess.run([sys.executable, "-I"] + args, capture_output=True, timeout=timeout, cwd=REPO)


def _text(b):
    return b.decode("utf-8", "replace")


def test_the_three_ops_self_tests_pass_under_python_I():
    for script, flag, ok in (("logfiles.py", "--selftest", "logfiles selftest: OK"),
                             ("log_rotate.py", "--self-test", "log_rotate self-test: OK"),
                             ("pinflat.py", "--selftest", "pinflat selftest: OK")):
        r = _child([os.path.join(RESEARCH, script), flag])
        out = _text(r.stdout)
        fails = [x for x in out.splitlines() if x.startswith("  FAIL")]
        ck(r.returncode == 0 and out.rstrip().endswith(ok) and not fails,
           "%s %s under python -I: exit %s, last line %r, %d FAIL line(s) %s"
           % (script, flag, r.returncode, (out.strip().splitlines() or [""])[-1][:80], len(fails), fails[:1]))
        if script == "pinflat.py":
            ck(r.stderr == b"", "pinflat's self-test writes nothing to stderr (restart_bot reads it 2>&1 under Stop)")


def test_launcher_snapshot_is_byte_exact_and_still_reads_pinflat_by_exit_code():
    with open(os.path.join(SNAP, "SHA256SUMS.txt"), "rb") as fh:
        sums = fh.read()
    ck(b"\r" not in sums, "SHA256SUMS.txt has LF line ends (sha256sum -c reads it)")
    rows = [ln.split("  ", 1) for ln in sums.decode("ascii").splitlines() if ln.strip()]
    ck(sorted(n for _h, n in rows) == ["restart_bot_hand.ps1", "restart_bot_repo.ps1"]
       and all(re.fullmatch(r"[0-9a-f]{64}", h) for h, _n in rows), "SHA256SUMS.txt names the two launchers")
    for h, n in rows:
        with open(os.path.join(SNAP, n), "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        ck(got == h, "%s is byte-exact: sha256 %s... = SHA256SUMS.txt" % (n, got[:12]))
    with open(os.path.join(SNAP, ".gitattributes"), encoding="utf-8") as fh:
        attrs = [ln.split() for ln in fh if ln.strip() and not ln.startswith("#")]
    ck(["*.ps1", "-text"] in attrs and ["SHA256SUMS.txt", "-text"] in attrs,
       ".gitattributes keeps the launchers and the sums from any line-ending conversion")
    with open(os.path.join(SNAP, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    ck("edited IN PLACE by the deploy scripts" in readme and "what a watcher compares against" in readme,
       "README.md says the server copies are edited in place and this is what a watcher compares against")
    for n in ("restart_bot_repo.ps1", "restart_bot_hand.ps1"):
        with open(os.path.join(SNAP, n), encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        ck('& $py "$repo\\research\\pinflat.py" 2>&1' in src and "$flatCode = $LASTEXITCODE" in src
           and "if ($flatCode -eq 1) {" in src and "if ($flatCode -ne 0) {" in src,
           "%s runs pinflat with no arguments and reads only its exit code (1 = holding, not 0 = fall back to the "
           "count): pinflat's contract" % n)


def _snapshot_names():
    with open(os.path.join(SNAP, "SHA256SUMS.txt"), "rb") as fh:
        return [ln.split("  ", 1)[1] for ln in fh.read().decode("ascii").splitlines() if ln.strip()]


def test_every_snapshot_names_its_live_file_and_the_readme_agrees():
    """11-08 merge review: the watch looked the snapshot NAMES up under C:\\kals-repo (restart_bot_hand.ps1 is no file
    there), so it would have raised two false 'missing' alarms from its first scan and never hashed a live launcher.
    LIVE_PATHS.txt maps each name to its live file; here every name of SHA256SUMS.txt has one, and the README agrees."""
    import kalshi_watch as KW
    names = _snapshot_names()
    live = KW.read_live_paths(os.path.join(SNAP, "LIVE_PATHS.txt"))
    ck(live is not None, "results/live_launcher_snapshot/LIVE_PATHS.txt is there (kalshi_watch reads it: %s)" % KW.LIVE_REL)
    ck(sorted(live) == sorted(n.lower() for n in names),
       "LIVE_PATHS.txt names exactly the files SHA256SUMS.txt lists (%s vs %s)" % (sorted(live), sorted(names)))
    ck(all(re.fullmatch(r"[A-Za-z]:\\[^*?\"<>|]+\\restart_bot\.ps1", p) for p in live.values())
       and len({p.lower() for p in live.values()}) == len(live),
       "each is a full server path to a restart_bot.ps1, no two the same: %s" % sorted(live.values()))
    with open(os.path.join(SNAP, "README.md"), encoding="utf-8") as fh:
        table = dict((a.lower(), b) for a, b in re.findall(r"^\| `([^`]+\.ps1)` \| `([^`]+)` \|", fh.read(), re.M))
    ck(table == live, "the README's table says the same live paths (%s)" % table)


def test_the_watch_hashes_the_live_launchers_the_snapshot_names():
    """The cross-test the 11-08 tests review asked for: kalshi_watch.check_launchers on the COMMITTED SHA256SUMS.txt and
    LIVE_PATHS.txt, the live files planted (Env.remap puts each server path under a temp folder): nothing there -> both
    'missing' by their LIVE path; byte copies of the snapshots in place -> 2 of 2 match, no alarm; one byte changed in
    the hand copy -> exactly that one drifts."""
    import tempfile
    import kalshi_watch as KW
    td = tempfile.mkdtemp(prefix="test_ops_launchers_")
    try:
        res = os.path.join(td, "results")
        shutil.copytree(SNAP, os.path.join(res, "live_launcher_snapshot"))
        live = KW.read_live_paths(os.path.join(SNAP, "LIVE_PATHS.txt"))
        server = os.path.join(td, "server")

        def remap(p):
            return os.path.join(server, p.replace(":", "", 1).lstrip("\\/"))
        env = KW.Env(results=res, repo=os.path.join(td, "repo"), log_path="", remap=remap)
        r0 = KW.check_launchers(env, {}, 0)
        heads = sorted(o["head"] for o in r0.opens.values())
        ck("0 of 2 match" in r0.detail and heads == sorted("Live launcher %s is missing" % p for p in live.values()),
           "nothing at the live paths -> both missing, each named by its LIVE path: %s" % heads)
        for name in _snapshot_names():
            dst = remap(live[name.lower()])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(SNAP, name), dst)
        r1 = KW.check_launchers(env, {}, 0)
        ck(r1.opens == {} and r1.detail == "2 of 2 match the snapshot",
           "the live files = the snapshots -> '2 of 2 match the snapshot', no alarm (got %r, %s)" % (r1.detail,
                                                                                                 sorted(r1.opens)))
        with open(remap(live["restart_bot_hand.ps1"]), "ab") as fh:
            fh.write(b" ")
        r2 = KW.check_launchers(env, {}, 0)
        o = r2.opens.get("launcher|restart_bot_hand.ps1") or {}
        ck(set(r2.opens) == {"launcher|restart_bot_hand.ps1"} and "is not the snapshot" in o.get("head", "")
           and live["restart_bot_hand.ps1"] in o.get("head", "") and "1 of 2 match" in r2.detail,
           "one byte changed in the hand launcher -> that one drifts, named by its live path (%s)" % o.get("head"))
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_requirements_server_holds_exactly_the_six_pins():
    with open(os.path.join(RESULTS, "requirements-server.txt"), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    pins = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    ck(pins == ["certifi==2026.7.22", "cryptography==50.0.0", "numpy==2.5.4", "requests==2.34.2", "urllib3==2.7.0",
                "websockets==17.0.1"], "exactly the six pins of 11-07: %s" % pins)
    head = " ".join(ln for ln in lines if ln.startswith("#"))
    ck("drift alarms" in head and "NOT something to pip install blindly" in head,
       "the comment says it is a record for drift alarms, not an install list")


def test_rotation_installer_shape():
    p = os.path.join(RESULTS, "log_rotate_install.ps1")
    with open(p, encoding="utf-8") as fh:
        src = fh.read()
    ck("$task = 'KalsLogRotate'" in src and '-UserId "SYSTEM"' in src, "task KalsLogRotate, as SYSTEM")
    ck('$argLine = "-I -u $script --apply"' in src and '$argLine += " --git `"$git`""' in src
       and "-Argument $argLine" in src, "the action runs log_rotate.py --apply, with the git the installer found")
    ck("AddHours(9).AddMinutes(40)" in src and "if ($utc -le [datetime]::UtcNow) { $utc = $utc.AddDays(1) }" in src,
       "daily at 09:40 UTC, the first run the NEXT 09:40 (never at once by surprise)")
    gate, reg = src.find("--self-test 2>&1"), src.find("Register-ScheduledTask -TaskName")
    ck(0 < gate < src.find("exit 1", gate) < reg, "the self-test gate (refuse and exit 1) comes BEFORE the task is "
                                                  "registered")
    ck(src.find("if ($DryRunOnly)") < reg, "-DryRunOnly stops before anything is registered")
    ck("[IO.File]::WriteAllText($marker" in src and "log_rotate_installed.json" in src
       and "Remove-Item -LiteralPath $marker" in src, "it writes the phone's marker, and -Uninstall removes it")
    ck(src.find("[IO.File]::WriteAllText($phoneFlag") < src.find("if ($RunNow)") and "pinphone.update" in src
       and "if ($NoPhoneReload)" in src, "it asks the phone to reload (results\\pinphone.update) BEFORE any run can start, "
                                         "unless -NoPhoneReload")
    import log_rotate
    ck(log_rotate.INSTALLED_NAME == "log_rotate_installed.json", "the marker's name is the one log_rotate.health reads")
    # 11-08 merge review: the operator deploys from the phone only, so the installer is an /approve item; with no
    # arguments (how /approve runs it) it is the full install: self-test, dry run, register, marker, phone reload
    import json
    from phone.actions import approvals as AP
    with open(os.path.join(RESULTS, "approvals", "approvals.json"), encoding="utf-8") as fh:
        items = [it for it in json.load(fh)["items"] if it.get("script") == "log_rotate_install.ps1"]
    ck(len(items) == 1 and items[0]["id"] == "logrotate" and items[0]["log"] == "log_rotate_install.out"
       and items[0]["sha256"] == AP.text_sha(p) and not items[0].get("superseded_by"),
       "/approve lists the installer once ('logrotate'), at its current sha256 (an edited installer is not run until "
       "the list is updated)")
    ps = shutil.which("powershell")
    if not ps:
        print("  skip the PowerShell parse check: no powershell on this machine")
        return
    r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command",
                        "$e=$null; $t=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
                        "'%s', [ref]$t, [ref]$e); $e.Count" % p.replace("'", "''")],
                       capture_output=True, timeout=120)
    ck(r.returncode == 0 and _text(r.stdout).strip() == "0", "log_rotate_install.ps1 parses with no error (%s)"
       % _text(r.stdout + r.stderr).strip()[:120])


if __name__ == "__main__":
    sys.exit(_kit.run(dict(globals()), "test_ops"))
