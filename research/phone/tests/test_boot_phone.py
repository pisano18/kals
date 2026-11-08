"""test_boot_phone.py -- v-tg-hung (2026-11-07): boot_all.ps1's hung-phone keep-alive, RUN in every pinphone --selftest.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_boot_phone.py   (exit 0 = every test passed)
boot_all.ps1 restarts a phone whose heartbeat (results\\pinphone.heartbeat, written by phone/app.py) is over 5 minutes old.
Before this file only text matches covered it, so a change that never killed a hung phone, or killed a working one every
10 minutes, passed every suite (the 2026-11-07 tests review: mutations M6a / M6b / M6c lived).

THE KEEP-ALIVE SHIPS AS A PATCH, NOT AS A COMMITTED boot_all.ps1 (2026-11-08 merge review). The live boot_all.ps1 on the
server (and the laptop's) carries edits git never had -- the ladder's argv and 82% rail, the FX keep-alives, the retired
paper arms switched off -- so a committed copy built on git's HEAD would block every pull and, forced through, undo them.
results\\boot_phone_hung.ps1 (the /approve item 'phonehung') edits the live file in place, three anchored places only.
So the boot_all.ps1 these tests read is the repo's own once it carries the keep-alive (the server after /approve
phonehung), else a TEMP copy of it patched by that script -- which also proves, in the /update gate on the server, that
the script's three anchors are found in the server's own file. This test:
  - parses that boot_all.ps1 with PowerShell's own parser (0 errors), and NEVER RUNS IT: it lifts the three functions
    (PhoneHungVerdict, PhoneCands, PhoneKeepAlive) and the -PhoneTest block out of the parsed file into a temp script and
    runs only that (it starts and kills nothing: PhoneKeepAlive gets planted kill / alive blocks) -- the 5-minute bar,
    UTC times, which processes are judged (never a --selftest / --preview / --smoke run), one kill an hour, the blind
    rule, and a kill that did not end the phone starting no second one;
  - checks that section 3b acts through those functions (the heartbeat the phone writes, PhoneKeepAlive's keep / killed);
  - checks the heartbeat format the phone writes is the one PhoneHungVerdict reads;
  - runs the patch on planted "live" copies (CRLF and LF, edits beside every anchor): only its three places change,
    every planted edit, the BOM and the line ends survive, a second run changes nothing; a missing or doubled anchor is
    refused with the file untouched and no backup written;
  - checks /approve lists the patch with its current sha256.
The patch only ever gets temp paths here (and refuses C:\\kals-repo under KALS_TESTING=1). Skipped (said, exit 0) only
where there is no powershell.exe. KALS_TESTING=1; nothing under results\\ is written.
"""
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
BOOT = os.path.join(REPO, "boot_all.ps1")
PATCH = os.path.join(REPO, "results", "boot_phone_hung.ps1")
MANIFEST = os.path.join(REPO, "results", "approvals", "approvals.json")

import _dlane                                                        # noqa: E402,F401  (KALS_TESTING=1; the log to a temp file)
FUNCS = ("PhoneHungVerdict", "PhoneCands", "PhoneKeepAlive")
TD = tempfile.mkdtemp(prefix="test_boot_phone_")
_CACHE = {}

# The lifter: parse (never run) boot_all.ps1, write the named functions + the -PhoneTest block's body into a temp script,
# run that in a fresh powershell, and pass its exit code on. The block is found by its condition, exactly '$PhoneTest'.
LIFT = r"""
param([string]$Boot, [string]$Out)
$tokens = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Boot, [ref]$tokens, [ref]$errs)
Write-Output ("parse errors: {0}" -f $errs.Count)
foreach ($e in $errs) { Write-Output ("  {0} (line {1})" -f $e.Message, $e.Extent.StartLineNumber) }
if ($errs.Count -gt 0) { exit 3 }
$parts = @()
foreach ($name in @(%FUNCS%)) {
    $fn = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name }, $true))
    if ($fn.Count -ne 1) { Write-Output ("function {0}: found {1}, want 1" -f $name, $fn.Count); exit 4 }
    $parts += $fn[0].Extent.Text
}
$blk = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -eq '$PhoneTest' }, $true))
if ($blk.Count -ne 1) { Write-Output ("the -PhoneTest block: found {0}, want 1" -f $blk.Count); exit 4 }
$parts += (". " + $blk[0].Clauses[0].Item2.Extent.Text)
Set-Content -Path $Out -Value ($parts -join "`r`n`r`n") -Encoding UTF8
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Out
exit $LASTEXITCODE
"""

# the three places the patch changes (the old lines it replaces; every other line of the file stays)
OLD_PARAM = "param([switch]$Install, [switch]$NoArms, [switch]$DeafTest, [switch]$DeafDryRun)"
OLD_3B = ("    if (RunningPy '*pinphone.py*') {", "        # fine")
GROWS_BY = 184                                   # lines: 171 before PidFileAlive, 5 comment lines and 8 more in 3b


def _powershell():
    return shutil.which("powershell.exe") or shutil.which("powershell")


def _read_text(path):
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def _has_keepalive(text):
    return "function PhoneKeepAlive(" in text


def _patch(target):
    """Run results\\boot_phone_hung.ps1 on `target` (always a temp file), its log and backup beside it.
    (exit code, the log's text, the backup's path)."""
    d = os.path.dirname(target)
    log, backup = os.path.join(d, "patch.out"), os.path.join(d, "backup.ps1")
    assert os.path.abspath(target).startswith(os.path.abspath(TD)), target
    r = subprocess.run([_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PATCH, "-Target", target,
                        "-Log", log, "-Backup", backup], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=240)
    txt = ""
    if os.path.exists(log):
        with open(log, encoding="utf-8-sig", errors="replace") as fh:
            txt = fh.read()
    return r.returncode, txt + (r.stdout or "") + (r.stderr or ""), backup


def _case_dir(name):
    d = os.path.join(TD, name)
    os.makedirs(d, exist_ok=True)
    return d


def _tested_boot():
    """The boot_all.ps1 these tests read (see the docstring): the repo's own when it carries the keep-alive, else a temp
    copy patched by results\\boot_phone_hung.ps1. None (the caller says SKIPPED) when it must be patched and there is no
    powershell.exe."""
    if "boot" in _CACHE:
        return _CACHE["boot"]
    if _has_keepalive(_read_text(BOOT)):
        _CACHE["boot"] = BOOT
        return BOOT
    if _powershell() is None:
        _CACHE["boot"] = None
        return None
    tgt = os.path.join(_case_dir("repo_copy"), "boot_all.ps1")
    shutil.copyfile(BOOT, tgt)
    code, out, _bk = _patch(tgt)
    assert code == 0 and "PATCHED" in out, ("results\\boot_phone_hung.ps1 did not patch a copy of this repo's "
                                            "boot_all.ps1 (exit %s): %s" % (code, out))
    _CACHE["boot"] = tgt
    return tgt


def _src():
    p = _tested_boot()
    return None if p is None else _read_text(p)


def _section_3b(src):
    i = src.index("# --- 3b. the phone link")
    return src[i:src.index("# --- 4. the paper arms", i)]


def test_the_lifted_phone_self_test_passes():
    ps = _powershell()
    boot = _tested_boot()
    if ps is None or boot is None:
        print("  SKIPPED: no powershell.exe on this machine (boot_all.ps1 runs only on Windows)")
        return
    td = tempfile.mkdtemp(prefix="test_boot_phone_lift_")
    lift = os.path.join(td, "lift.ps1")
    with open(lift, "w", encoding="utf-8-sig") as fh:
        fh.write(LIFT.replace("%FUNCS%", ", ".join("'%s'" % f for f in FUNCS)))
    try:
        r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", lift, "-Boot", boot,
                            "-Out", os.path.join(td, "lifted.ps1")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=240)
        out = (r.stdout or "") + (r.stderr or "")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    assert "parse errors: 0" in out, out
    assert r.returncode == 0 and "boot_all phone self-test: OK" in out, out
    oks = [x for x in out.splitlines() if x.strip().startswith("ok ")]
    assert "FAIL" not in out and len(oks) >= 21, (len(oks), out)
    for want in ("-> HUNG, kill pid 4242", "5 min 10 s is over the 5-min bar -> HUNG",
                 "never a --selftest / --preview / --smoke run", "the start time is turned to UTC",
                 "NOT killed (one kill an hour)", "no second phone started beside it", "are blind -> not killed"):
        assert want in out, (want, out)


def test_section_3b_acts_through_the_tested_functions():
    src = _src()
    if src is None:
        print("  SKIPPED: no powershell.exe to patch a copy of boot_all.ps1")
        return
    s3b = _section_3b(src)
    assert '$phoneCands = @(PhoneCands $procs)' in s3b, s3b
    assert 'PhoneHungVerdict "$res\\pinphone.heartbeat" $phoneCands ([datetime]::UtcNow)' in s3b, s3b
    assert 'PhoneKeepAlive $pv $blind "$res\\phone_hung_kill.last" ([datetime]::UtcNow)' in s3b, s3b
    assert "Stop-Process -Id $p -Force" in s3b and "[bool](Get-Process -Id $p" in s3b, "the real kill, and its check"
    assert "if ($ka.keep -or $phoneUp) {" in s3b, "a phone that stays (held back, or not ended) gets no second one"
    assert "Stop-Process" not in s3b.replace("Stop-Process -Id $p -Force", ""), "3b kills only through PhoneKeepAlive"
    assert src.count("[double]$maxAgeS = 300") == 1 and "[double]$guardMin = 60" in src, "5 minutes; one kill an hour"
    for f in ("PhoneHungVerdict", "PhoneKeepAlive"):
        body = src[src.index("function %s(" % f):]
        body = body[:body.index("\n}\n")]                       # read in text mode: CRLF is "\n" here
        assert "LastWriteTime " not in body and "LastWriteTime)" not in body and "Get-Date" not in body, (
            "%s reads every time in UTC (a local-time subtraction is an hour off across a daylight-saving change)" % f)


def test_the_heartbeat_the_phone_writes_is_the_one_boot_all_reads():
    src = _src()
    if src is None:
        print("  SKIPPED: no powershell.exe to patch a copy of boot_all.ps1")
        return
    import phone.shared as S
    from phone import app as A
    td = tempfile.mkdtemp(prefix="test_boot_phone_hb_")
    saved = S.HEARTBEAT
    S.HEARTBEAT = os.path.join(td, "pinphone.heartbeat")
    try:
        ph = A.Phone.__new__(A.Phone)
        ph.heartbeat()
        with open(S.HEARTBEAT, encoding="utf-8") as fh:
            txt = fh.read()
    finally:
        S.HEARTBEAT = saved
        shutil.rmtree(td, ignore_errors=True)
    m = re.search(r"\$txt -match '([^']+)'", src)
    assert m and m.group(1) == r"pid (\d+)", "PhoneHungVerdict reads the pid with 'pid (\\d+)'"
    got = re.search(m.group(1), txt)
    assert got and int(got.group(1)) == os.getpid(), (txt, m.group(1))


def _planted(nl):
    """This repo's boot_all.ps1 (it must not carry the keep-alive yet) with a planted 'live edit' beside every anchor
    the patch uses and a few elsewhere, in line ends `nl`, its BOM as the repo's. (bytes, the marker lines)."""
    with open(BOOT, "rb") as fh:
        raw = fh.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    marks = ["# planted live edit %s" % c for c in "ABCDEF"]

    def once(t, old, new):
        assert t.count(old) == 1, (old, t.count(old))
        return t.replace(old, new)
    text = once(text, OLD_PARAM + "\n", OLD_PARAM + "\n" + marks[0] + "\n")
    text = once(text, "\nfunction PidFileAlive($path) {\n", "\n" + marks[1] + "\nfunction PidFileAlive($path) {\n")
    text = once(text, "\n# --- 3b. the phone link", "\n" + marks[2] + "\n# --- 3b. the phone link")
    text = once(text, "    } elseif ($blind -gt 0) {\n        Say \"pinphone.py not visible",
                "    } elseif ($blind -gt 0) {\n        " + marks[3] + "\n        Say \"pinphone.py not visible")
    text = once(text, "\n# --- 4. the paper arms", "\n" + marks[4] + "\n# --- 4. the paper arms")
    text = text + marks[5] + "\n"
    if '"--levels", "0,1"' in text:                            # the laptop's one-rung ladder edit, where git has it
        text = text.replace('"--levels", "0,1"', '"--levels", "0"')
    out = text.replace("\n", nl).encode("utf-8")
    return (b"\xef\xbb\xbf" + out if bom else out), marks


def test_the_patch_changes_only_its_three_places_and_keeps_every_live_edit():
    if _powershell() is None:
        print("  SKIPPED: no powershell.exe on this machine")
        return
    if _has_keepalive(_read_text(BOOT)):
        print("  SKIPPED: this repo's boot_all.ps1 already carries the keep-alive (patched); the tests above read it")
        return
    results = {}
    for name, nl in (("crlf", "\r\n"), ("lf", "\n")):
        planted, marks = _planted(nl)
        tgt = os.path.join(_case_dir("planted_" + name), "boot_all.ps1")
        with open(tgt, "wb") as fh:
            fh.write(planted)
        code, out, backup = _patch(tgt)
        assert code == 0 and "PATCHED" in out and ("its %s line ends" % name.upper()) in out, (name, code, out)
        with open(tgt, "rb") as fh:
            got = fh.read()
        with open(backup, "rb") as fh:
            assert fh.read() == planted, "the backup is the file as it was, byte for byte"
        assert got.startswith(b"\xef\xbb\xbf") == planted.startswith(b"\xef\xbb\xbf"), "the BOM is kept"
        if nl == "\n":
            assert b"\r" not in got, "an LF file stays LF"
        else:
            assert got.count(b"\r\n") == got.count(b"\n"), "a CRLF file stays CRLF"
        a = planted.decode("utf-8-sig").split(nl)
        b = got.decode("utf-8-sig").split(nl)
        for m in marks:
            assert b.count(m.strip()) + b.count("        " + m) == 1, ("a planted live edit survives once", m)
        changed = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            assert tag in ("equal", "insert", "replace"), (tag, a[i1:i2])
            if tag != "equal":
                changed += a[i1:i2]
        assert sorted(changed) == sorted([OLD_PARAM] + list(OLD_3B)), ("only the param line and 3b's two phone lines "
                                                                       "are replaced", changed)
        assert len(b) - len(a) == GROWS_BY, ("the patch adds exactly its own lines", len(b) - len(a))
        assert "param([switch]$Install, [switch]$NoArms, [switch]$DeafTest, [switch]$DeafDryRun, [switch]$PhoneTest)" in b
        results[name] = got
        code2, out2, _bk = _patch(tgt)
        with open(tgt, "rb") as fh:
            assert fh.read() == got, "a second run changes nothing"
        assert code2 == 0 and "already has the hung-phone keep-alive" in out2, (code2, out2)
    assert results["lf"] == results["crlf"].replace(b"\r\n", b"\n"), "the same edit whatever the line ends"


def test_the_patch_refuses_and_leaves_the_file_alone():
    if _powershell() is None:
        print("  SKIPPED: no powershell.exe on this machine")
        return
    if _has_keepalive(_read_text(BOOT)):
        print("  SKIPPED: this repo's boot_all.ps1 already carries the keep-alive (patched)")
        return
    planted, _marks = _planted("\r\n")
    cases = (("no3b", planted.replace(b"        # fine\r\n", b"        # fine, edited by hand\r\n", 1),
              "section 3b's phone lines found 0 times"),
             ("twice", planted.replace(b"\r\nfunction PidFileAlive($path) {\r\n",
                                       b"\r\nfunction PidFileAlive($path) {\r\n}\r\nfunction PidFileAlive($path) {\r\n", 1),
              "at a line start found 2 times"),
             ("mixed", planted.replace(b"\r\n", b"\n", 1), "mixes line ends"))
    for name, body, why in cases:
        assert body != planted, name
        tgt = os.path.join(_case_dir("refuse_" + name), "boot_all.ps1")
        with open(tgt, "wb") as fh:
            fh.write(body)
        code, out, backup = _patch(tgt)
        with open(tgt, "rb") as fh:
            assert fh.read() == body, ("%s: a refused patch leaves the file byte for byte" % name)
        assert code == 1 and "REFUSED" in out and why in out and "Nothing changed" in out.replace("nothing changed",
                                                                                                    "Nothing changed"), (
            name, code, out)
        assert not os.path.exists(backup), "%s: nothing is backed up when nothing is changed" % name


def test_approve_lists_the_patch_at_its_current_sha():
    from phone.actions import approvals as AP
    with open(MANIFEST, encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    it = [x for x in items if x.get("id") == "phonehung"]
    assert len(it) == 1, "results\\approvals\\approvals.json lists 'phonehung' once"
    it = it[0]
    assert it["script"] == "boot_phone_hung.ps1" and it["log"] == "boot_phone_hung.out", it
    assert it["sha256"] == AP.text_sha(PATCH), ("the listed sha256 is the script's (an edited script is not run until "
                                                "the list is updated)", it["sha256"], AP.text_sha(PATCH))
    assert not it.get("superseded_by")
    with open(PATCH, encoding="ascii") as fh:
        ps = fh.read()
    assert "param([string]$Target = 'C:\\kals-repo\\boot_all.ps1'" in ps, "with no arguments it edits the live file"
    assert "$env:KALS_TESTING -eq '1'" in ps and "-like 'C:\\kals-repo\\*'" in ps, "the test fence"


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = []
    try:
        for k, fn in tests:
            try:
                fn()
                print("  ok   %s" % k, flush=True)
            except Exception:                                   # noqa: BLE001
                failed.append(k)
                print("  FAIL %s\n%s" % (k, traceback.format_exc()), flush=True)
    finally:
        shutil.rmtree(TD, ignore_errors=True)
    print("test_boot_phone: %d passed, %d failed" % (len(tests) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
