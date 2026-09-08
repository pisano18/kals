#!/bin/sh
for d in "$@"; do
  KALS_SELFTESTED=1 python /c/kals-repo/results/opp/oppcount.py --day $d > /c/kals-repo/results/opp/log_$d.txt 2>&1
  echo "done $d"
done
