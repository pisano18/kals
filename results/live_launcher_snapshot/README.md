# Live launcher snapshot -- 2026-11-08

Byte-exact copies of the two files that start the live pin bot on the server, copied from the server on
2026-11-07 at 11:46 AM ET, with their sha256 in `SHA256SUMS.txt`.

| file here | is the server's | what runs it |
|---|---|---|
| `restart_bot_repo.ps1` | `C:\kals-repo\restart_bot.ps1` | the KEEP-ALIVE copy: `watch_bot.ps1` runs it when pin is down |
| `restart_bot_hand.ps1` | `C:\kals-live-0925n\restart_bot.ps1` | the HAND copy: every deploy script (`results\pin_<ver>.ps1`) and the phone's `/approve pinrestart` restart pin through it |

Both start code `C:\kals-live-0925v` (code sha `d51b131b55cf`, pintake sha `b3c7bb48abb5`) with the same flags; since 2026-11-08 the jump hedge runs as a SHADOW (`--hedge-jump-shadow 6`, v-jumpshadow: it records what it would have bought and sends nothing).

`LIVE_PATHS.txt` holds the same two rows in the form the watcher reads (`<file here>  <server path>`): both live files
are named `restart_bot.ps1`, so the name alone cannot say which one a snapshot copies. `research\botdata\tests\test_ops.py`
fails if it and `SHA256SUMS.txt` name different files, or if this table says other paths.

## Why this folder exists

- **The server copies are edited IN PLACE by the deploy scripts.** Each `results\pin_<ver>.ps1` rewrites the code
  path, the sha pins and the flag list inside both files on the server. Git's own `restart_bot.ps1` at the repo
  root is NOT what runs: on 11-07 it still named the `0925n` build and `--max-positions 3`, while pin ran `0925t`
  with `--max-positions 5`, `--band99-*` and `--ws-later-fall-c 10 --hedge-jump-max 8`.
- **This snapshot is what a watcher compares against.** The server's two files (found through `LIVE_PATHS.txt`) are
  hashed by `research\kalshi_watch.py` every 30 minutes and checked against `SHA256SUMS.txt`. A mismatch means a launcher changed since this snapshot: either a deploy (then this folder is
  refreshed in the same commit as that deploy script) or a change nobody made on purpose -- which is the alarm.
- **Byte-exact.** `.gitattributes` turns off line-ending conversion here, because `restart_bot_hand.ps1` mixes CRLF
  and LF line ends (14 CRLF, 899 LF) and a conversion would silently change its hash.

## Refreshing it (with every deploy that edits a launcher)

1. Copy both server files here under the names above, byte for byte (`scp`, never a text editor).
2. Rewrite `SHA256SUMS.txt` (LF line ends, `sha256sum` format: `<64 hex>  <file name>`), for example
   `(Get-FileHash -Algorithm SHA256 <file>).Hash.ToLower()` for each.
3. Check: `sha256sum -c SHA256SUMS.txt` from this folder says `OK` twice. A launcher added, renamed or moved also
   changes `LIVE_PATHS.txt` and the table above (test_ops checks all three agree).
4. Commit the folder in the same commit as the deploy script, and change the date and the build line above.
