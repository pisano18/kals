# Golden changes accepted

Each line: world, case, expected digest -> actual digest (first 12 hex of the case file's sha256), why. Written by `compare.py --accept`; compare.py treats a case as unchanged when its pair of digests is listed here.

- `jumpband-live` `data/all_bots` `de5fdde902bc` -> `a4bf995b54e2`: harness normalisation, not code: the world's planted jumpband_live.py command line names C:\kals-repo\research, which reads <REPO>\research when the baseline is replayed from the C:\kals-golden-base worktree and <CODE> when the tree under test is C:\kals-repo itself (B0 8a9c5e1 vs the unchanged tree) (accepted 2026-10-30)
