"""Golden compare: one replay output (expected) against another (actual), case by case, world by world.
Never imported by production code.

    python research\\golden\\compare.py EXPECTED ACTUAL [--report FILE] [--lines 40]
    python research\\golden\\compare.py EXPECTED ACTUAL --accept "base/cmd//bots" --why "v-tg-active hides stopped bots"

A case is the same when its JSON file is byte-identical. A changed case is ACCEPTED when research/golden/CHANGES.md
holds a line for it with the same expected and actual digests (written by --accept, which needs --why). Charts: on a
different PNG both pictures and a PIL difference image are written next to the report. Exit 0 when every case is the
same or accepted, 1 otherwise.

--accept takes a world/case pattern (fnmatch: '*' matches across '/'; a pattern without a world matches every world),
and records every CURRENTLY DIFFERENT case it matches.
"""
import argparse
import datetime
import difflib
import fnmatch
import json
import os
import re
import shutil
import sys

GOLDEN = os.path.dirname(os.path.abspath(__file__))
CHANGES = os.path.join(GOLDEN, "CHANGES.md")
LINE_RX = re.compile(r"^- `(?P<world>[^`]+)` `(?P<case>[^`]+)` `(?P<exp>[0-9a-f]{12}|absent)` -> "
                     r"`(?P<act>[0-9a-f]{12}|absent)`: (?P<why>.*)$")


def sha12(path):
    import hashlib
    if path is None or not os.path.exists(path):
        return "absent"
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def worlds_of(d):
    return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x, "cases")))


def case_files(d, w):
    p = os.path.join(d, w, "cases")
    out = {}
    for f in os.listdir(p):
        if f.endswith(".json"):
            j = load(os.path.join(p, f))
            out[(j or {}).get("case") or f] = os.path.join(p, f)
    return out


def accepted():
    acc = {}
    if os.path.exists(CHANGES):
        with open(CHANGES, encoding="utf-8") as fh:
            for line in fh:
                m = LINE_RX.match(line.rstrip("\n"))
                if m:
                    acc[(m["world"], m["case"], m["exp"], m["act"])] = m["why"]
    return acc


def diff_lines(a, b, n, label):
    a = (a if isinstance(a, str) else json.dumps(a, indent=1, sort_keys=True, ensure_ascii=False)).splitlines()
    b = (b if isinstance(b, str) else json.dumps(b, indent=1, sort_keys=True, ensure_ascii=False)).splitlines()
    d = list(difflib.unified_diff(a, b, "expected " + label, "actual " + label, n=1, lineterm=""))
    if len(d) > n:
        d = d[:n] + ["... (%d more diff lines)" % (len(d) - n)]
    return d


def png_diff(exp_png, act_png, out_base):
    """Both PNGs + a PIL difference image (changed pixels red over a faded expected)."""
    made = []
    for src, tag in ((exp_png, "expected"), (act_png, "actual")):
        if src and os.path.exists(src):
            dst = "%s.%s.png" % (out_base, tag)
            shutil.copyfile(src, dst)
            made.append(os.path.basename(dst))
    try:
        from PIL import Image, ImageChops
        if exp_png and act_png and os.path.exists(exp_png) and os.path.exists(act_png):
            a = Image.open(exp_png).convert("RGB")
            b = Image.open(act_png).convert("RGB")
            w, h = max(a.width, b.width), max(a.height, b.height)
            a2 = Image.new("RGB", (w, h), "white")
            a2.paste(a)
            b2 = Image.new("RGB", (w, h), "white")
            b2.paste(b)
            d = ImageChops.difference(a2, b2).convert("L").point(lambda v: 255 if v > 16 else 0)
            faded = Image.blend(a2, Image.new("RGB", (w, h), "white"), 0.7)
            red = Image.new("RGB", (w, h), (220, 30, 30))
            faded.paste(red, mask=d)
            dst = "%s.diff.png" % out_base
            faded.save(dst)
            made.append(os.path.basename(dst))
            bbox = d.getbbox()
            made.append("changed area %s, sizes %sx%s vs %sx%s" % (bbox, a.width, a.height, b.width, b.height))
    except Exception as e:                                      # noqa: BLE001
        made.append("no PIL diff: %s" % e)
    return made


NOISE_MAX = 24          # a pixel channel may differ by this much ...
NOISE_PIXELS = 2000     # ... on at most this many pixels (of ~1.8 million) and still be the same picture


def render_noise(exp, act, w, de, da):
    """True when two chart cases differ ONLY in the PNG's bytes and the pictures differ by anti-aliasing noise.
    matplotlib 3.11 on this machine renders a long path's sub-pixel edge differently from one draw to the next, even
    in one process with identical data (measured 10-30: one /fx chart, max 6 levels on 263 pixels); a real change
    (a moved line, other text) differs by far more."""
    if de is None or da is None or not de.get("png") or not da.get("png"):
        return False
    keys = {k for k in set(de) | set(da) if de.get(k) != da.get(k)}
    if not keys or not keys <= {"sha256", "bytes"}:
        return False
    try:
        from PIL import Image, ImageChops
        a = Image.open(os.path.join(exp, w, "charts", de["png"])).convert("RGBA")
        b = Image.open(os.path.join(act, w, "charts", da["png"])).convert("RGBA")
        if a.size != b.size:
            return False
        d = ImageChops.difference(a, b)
        if max(hi for _lo, hi in d.getextrema()) > NOISE_MAX:
            return False
        mask = d.convert("RGB").convert("L").point(lambda v: 255 if v else 0)
        return mask.histogram()[255] <= NOISE_PIXELS
    except Exception:                                           # noqa: BLE001
        return False


def compare(exp, act, report_dir, nlines):
    acc = accepted()
    rows, details, pending = [], [], []
    ws = sorted(set(worlds_of(exp)) | set(worlds_of(act)))
    for w in ws:
        ef = case_files(exp, w) if os.path.isdir(os.path.join(exp, w, "cases")) else {}
        af = case_files(act, w) if os.path.isdir(os.path.join(act, w, "cases")) else {}
        n = {"same": 0, "changed": 0, "accepted": 0, "added": 0, "removed": 0, "noise": 0}
        for case in sorted(set(ef) | set(af)):
            pe, pa = ef.get(case), af.get(case)
            se, sa = sha12(pe), sha12(pa)
            if se == sa:
                n["same"] += 1
                continue
            if pe and pa and render_noise(exp, act, w, load(pe), load(pa)):
                n["noise"] += 1                     # only the PNG's bytes moved, by anti-aliasing noise: the same
                continue
            why = acc.get((w, case, se, sa))
            kind = "added" if pe is None else "removed" if pa is None else "changed"
            if why is not None:
                n["accepted"] += 1
                continue
            n[kind] += 1
            pending.append((w, case, se, sa))
            de, da = load(pe) if pe else None, load(pa) if pa else None
            lines = ["### `%s` `%s` -- %s (%s -> %s)" % (w, case, kind.upper(), se, sa)]
            if de is not None and da is not None:
                keys = sorted(k for k in set(de) | set(da) if de.get(k) != da.get(k))
                lines.append("fields that differ: %s" % ", ".join(keys))
                for k in keys:
                    if k in ("reply", "chunks") and "reply" in keys and k == "chunks":
                        if len(de.get("chunks") or []) != len(da.get("chunks") or []):
                            lines.append("chunks: %d -> %d messages" % (len(de.get("chunks") or []),
                                                                        len(da.get("chunks") or [])))
                        continue
                    lines += ["```diff"] + diff_lines(de.get(k), da.get(k), nlines, k) + ["```"]
                if (de.get("sha256") or da.get("sha256")) and de.get("sha256") != da.get("sha256"):
                    base = os.path.join(report_dir, re.sub(r"[^A-Za-z0-9_.-]", "_", "%s__%s" % (w, case)))
                    made = png_diff(os.path.join(exp, w, "charts", de["png"]) if de.get("png") else None,
                                    os.path.join(act, w, "charts", da["png"]) if da.get("png") else None, base)
                    lines.append("pictures: %s" % "; ".join(made))
            elif da is not None:
                lines.append("new case: status %s, type %s" % (da.get("status"), da.get("type")))
            details.append("\n".join(lines))
        fails = []
        for case, p in sorted(af.items()):
            j = load(p) or {}
            if j.get("status") == "FAIL":
                fails.append("%s (%s)" % (case, ", ".join(j.get("fail_why") or [])))
        rows.append((w, n, fails))
    return rows, details, pending


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("expected")
    ap.add_argument("actual")
    ap.add_argument("--report", default=None, help="markdown report (default ACTUAL/compare.md)")
    ap.add_argument("--lines", type=int, default=40, help="diff lines shown per field")
    ap.add_argument("--accept", default=None, help="world/case pattern to accept (needs --why)")
    ap.add_argument("--why", default=None)
    a = ap.parse_args()
    exp, act = os.path.abspath(a.expected), os.path.abspath(a.actual)
    report = os.path.abspath(a.report or os.path.join(act, "compare.md"))
    rdir = os.path.splitext(report)[0] + "_files"
    if os.path.exists(rdir):
        shutil.rmtree(rdir)
    os.makedirs(rdir)
    rows, details, pending = compare(exp, act, rdir, a.lines)

    if a.accept:
        if not a.why or not a.why.strip():
            print("--accept needs --why \"the reason\"")
            return 2
        first = a.accept.split("/")[0]
        known = set(worlds_of(exp)) | set(worlds_of(act))
        pat = a.accept if (first in known or any(c in first for c in "*?[")) else "*/" + a.accept
        hit = [p for p in pending if fnmatch.fnmatchcase("%s/%s" % (p[0], p[1]), pat)]
        if not hit:
            print("nothing pending matches %s" % pat)
            return 2
        new = not os.path.exists(CHANGES)
        with open(CHANGES, "a", encoding="utf-8", newline="\n") as fh:
            if new:
                fh.write("# Golden changes accepted\n\nEach line: world, case, expected digest -> actual digest (first 12 "
                         "hex of the case file's sha256), why. Written by `compare.py --accept`; compare.py treats a "
                         "case as unchanged when its pair of digests is listed here.\n\n")
            day = datetime.date.today().isoformat()
            for w, case, se, sa in hit:
                fh.write("- `%s` `%s` `%s` -> `%s`: %s (accepted %s)\n" % (w, case, se, sa, a.why.strip(), day))
        print("accepted %d case(s) into %s" % (len(hit), CHANGES))
        rows, details, pending = compare(exp, act, rdir, a.lines)

    out = ["# Golden compare", "", "expected: `%s`  " % exp, "actual: `%s`" % act, "",
           "| world | same | changed | added | removed | accepted | render noise | FAIL in actual |",
           "|---|---|---|---|---|---|---|---|"]
    for w, n, fails in rows:
        out.append("| %s | %d | %d | %d | %d | %d | %d | %d |" % (
            w, n["same"], n["changed"], n["added"], n["removed"], n["accepted"], n["noise"], len(fails)))
    for w, n, fails in rows:
        if fails:
            out.append("")
            out.append("FAIL cases in actual, %s: %s" % (w, "; ".join(fails)))
    out += ["", "## Differences (%d)" % len(details), ""] + details
    with open(report, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    for w, n, fails in rows:
        print("%-18s same %3d  changed %3d  added %3d  removed %3d  accepted %3d  noise %d  FAIL %d" % (
            w, n["same"], n["changed"], n["added"], n["removed"], n["accepted"], n["noise"], len(fails)))
    print("%d difference(s) pending -> %s" % (len(pending), report))
    if not os.listdir(rdir):
        os.rmdir(rdir)
    return 0 if not pending else 1


if __name__ == "__main__":
    sys.exit(main())
