"""Put back what Claude Code's 'Teleport auto-stash' (2026-10-15 04:39:42Z) took out of results/.

stash@{0} holds the worktree as it was. For each path in it that differs from the stash's base commit:
  MISSING now                      -> write the stash bytes (checkout form: autocrlf=true -> CRLF; pinrun-live
                                      logs raw LF, which is what pinrun writes).
  untracked, recreated since       -> stash bytes + what the new process wrote since.
  tracked, reverted to HEAD (C==H) -> stash bytes.
  tracked, HEAD + appended         -> stash bytes + the appended part.
A .jsonl a running bot holds open (os.replace refused) is merged IN PLACE: every writer here opens its log with
Python "a" (O_APPEND: each write goes to the then-current end), so the file is first extended to its final length --
later bot lines land after it -- then old+new is written at the front and re-verified. Console logs (.log/.out/.err:
not append handles) and anything rewritten since go to results/stash_20261015/ untouched.
Never deletes; the stash is left in place. --go to write, default is a dry run.
"""
import os, subprocess, sys, time

REPO = r"C:\kals-repo"
S = "stash@{0}"
SIDE = os.path.join(REPO, "results", "stash_20261015")
GO = "--go" in sys.argv


def git_bytes(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, check=True).stdout


def tree(ref):
    out = {}
    for line in git_bytes("ls-tree", "-r", ref).decode("utf-8", "replace").splitlines():
        meta, path = line.split("\t", 1)
        out[path] = meta.split()[2]
    return out


def blob(rev, path, raw=False):
    if raw:
        return git_bytes("cat-file", "blob", rev + ":" + path)
    return git_bytes("cat-file", "--filters", rev + ":" + path)


def read(fp):
    with open(fp, "rb") as fh:
        return fh.read()


def nl(a):
    return a if (not a or a.endswith(b"\n")) else a + b"\n"


def sidecar(path, data):
    dst = os.path.join(SIDE, path.replace("results/", "", 1))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return "sidecar exists"
    with open(dst, "wb") as fh:
        fh.write(data)
    return "sidecar"


def replace_with(fp, build):
    tmp = fp + ".restore-tmp"
    cur = read(fp)
    new = build(cur)
    with open(tmp, "wb") as fh:
        fh.write(new)
    cur2 = read(fp)
    if cur2 != cur:
        new = build(cur2)
        with open(tmp, "wb") as fh:
            fh.write(new)
    try:
        os.replace(tmp, fp)
        return True, len(new)
    except PermissionError:
        os.remove(tmp)
        return False, 0


def inplace_prepend(fp, pre, skip):
    """File now = X; make it pre + X[skip:] + (whatever the O_APPEND writer adds meanwhile)."""
    pre = nl(pre)
    with open(fp, "r+b") as fh:
        for _ in range(200):
            c0 = os.fstat(fh.fileno()).st_size
            fh.seek(0)
            X = fh.read(c0)
            if len(X) != c0 or (X and not X.endswith(b"\n")):
                time.sleep(0.02); continue                     # mid-write: wait for a whole line
            body = pre + X[skip:]
            new_len = len(body)
            if new_len < c0 or os.fstat(fh.fileno()).st_size != c0:
                time.sleep(0.02); continue
            fh.truncate(new_len)                               # writer's next line lands at >= new_len
            fh.seek(0)
            fh.write(body)
            fh.flush(); os.fsync(fh.fileno())
            for _v in range(3):                                # a write that raced the extension lands inside
                fh.seek(0)
                if fh.read(new_len) == body:
                    return new_len, os.fstat(fh.fileno()).st_size
                fh.seek(0); fh.write(body); fh.flush(); os.fsync(fh.fileno())
            raise RuntimeError("verify failed " + fp)
    raise RuntimeError("never quiet " + fp)


base, work = tree(S + "^1"), tree(S)
todo = [(p, base.get(p)) for p, sha in work.items() if base.get(p) != sha]
log = []
for p, hsha in sorted(todo):
    fp = os.path.join(REPO, p.replace("/", os.sep))
    raw = os.path.basename(p).startswith("pinrun-live-")
    sb = blob(S, p, raw)
    if not os.path.exists(fp):
        if GO:
            with open(fp, "xb") as fh:                         # x: never overwrite something that appeared
                fh.write(sb)
        log.append(("restore (missing)" + (" raw LF" if raw else ""), p, len(sb), len(sb)))
        continue
    cur = read(fp)
    if hsha is None:
        if cur == sb:
            log.append(("same already", p, len(sb), len(cur))); continue
        act, skip = "merge stash+new", 0
    else:
        hb = blob(S + "^1", p)
        if cur == hb:
            act, skip = "restore (reverted to HEAD)", None
        elif cur.startswith(hb):
            act, skip = "merge stash+appended", len(hb)
        else:
            act, skip = "rewritten since", -1
    is_jsonl = p.endswith(".jsonl")
    if skip == -1 or not (is_jsonl or p.endswith(".json")):
        log.append(((sidecar(p, sb) if GO else "sidecar") + " (" + act + ")", p, len(sb), len(cur))); continue
    if not GO:
        log.append((act, p, len(sb), len(cur))); continue
    build = (lambda c, sb=sb: sb) if skip is None else (lambda c, sb=sb, k=skip: nl(sb) + c[k:])
    ok, n = replace_with(fp, build)
    if ok:
        log.append((act + " DONE (replace)", p, len(sb), n)); continue
    if is_jsonl and skip is not None:
        n, now = inplace_prepend(fp, sb, skip)
        log.append((act + " DONE (in place; %d bytes since)" % (now - n), p, len(sb), now)); continue
    log.append((sidecar(p, sb) + " (held open; " + act + ")", p, len(sb), len(cur)))

for act, p, a, b in log:
    print(f"{act:62} {a:>11} {b:>11}  {p}")
print(len(log), "paths;", "WROTE" if GO else "DRY RUN")
