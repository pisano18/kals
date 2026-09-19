# restart_bot.ps1 -- stop the live pin bot and start it again on current code.
#
# WHY THIS FILE EXISTS. The operator, 2026-09-13: "you push the bot live not
# me. I've never had to." The auto-mode classifier refuses an ad-hoc
# Stop-Process / Start-Process pair on a live money process, and it is right
# to -- but it can be allowed for ONE named, reviewable script. This is that
# script, and it is deliberately narrow: it kills nothing but `pinrun`, it
# starts nothing but `pinrun`, and it refuses outright if the bot is holding a
# position.
#
# IT NEVER TOUCHES THE COLLECTOR. kalshi_collector.py and crypto_feeds.py carry
# no "pinrun" in their command lines, and the tape is unreproducible.
#
# THE ARGUMENTS ARE THE DEPLOYED ONES from CURRENT_STATE.md. --size 20 is only
# a starting value; the bot re-reads the bank every 300 s and sizes itself.
#
# ADDED 2026-09-13 ~22:2xZ: --pick best (AMENDMENT 24). When two markets clear
# every gate in the same second the bot now buys the better one instead of
# whichever the loop happened to reach first. Measured +2.07c -> +2.76c per
# contract on IDENTICAL loss counts, and again out of sample (+1.63c ->
# +2.43c, six losses either way). The ordering comes from the edge measured on
# the previous 50 ms pass, so nothing is recomputed and no order waits. See
# results/PREREG_pin_live_AMENDMENT_23_24.md.
#
# ADDED 2026-09-14 BY OPERATOR DECISION: --max-per-market 2 (A23 + A29) and
# --min-fill-frac 0.10 (A28). Both were paper-only and both refusals are now
# lifted, in pinrun.py, with the reasoning written next to them.
#
# THE MEASUREMENT THAT DECIDED IT: over 234 live closes the bot spent only 58%
# of the contract budget it was ALREADY allowed, and the MEDIAN close spent
# exactly 50% -- one fill, never the second. The unspent half needs a second
# market to qualify and only 6.3% of scan seconds have one. So the cap was
# never the binding constraint; the inability to use it was.
#
# THE WORST CLOSE DOES NOT MOVE. It is MAX_PER_CLOSE x SIZE x ceiling either
# way. What changes is how often the budget is actually spent.
#
# --min-fill-frac 0.10 lowers the depth floor from half of SIZE to a tenth, so
# a thin book is taken rather than skipped. MIN_LEVEL (1 contract) is still the
# backstop. A smaller fill is the same bet at the same gate on fewer contracts.
#
# REVERTED 2026-09-13 ~18:1xZ: --sigma-ruler and --pin are GONE. The ruler cut
# live signals by 63% (4.21/hour -> 1.55/hour, measured on the day) against a
# benefit measured only on the index population, which rule 5 says may not
# transfer to us. Certain cost, unproven benefit. The sweep (AMENDMENT 18)
# stays -- it is separately evidenced and needs no flag.

$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"
$py = "C:\Python314\python.exe"

# --- 0. LEAVE A TRANSCRIPT. On 2026-09-13 the operator ran this and the bot
# did not change; nothing on disk said why, so the next session had to guess
# between "it refused because a position was open", "the execution policy
# blocked the script" and "it was run from the wrong directory". A restart that
# fails silently is worse than one that fails loudly.
$transcript = "$repo\results\restart_bot.last.log"
try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $transcript -Force | Out-Null
Write-Host "restart_bot.ps1 starting $(Get-Date -Format o)"

# --- 0b. BUILD AND CHECK THE ARGUMENT LIST *BEFORE* KILLING ANYTHING.
#
# 2026-09-19 00:02Z: a bare `,` on its own line between two flags is
# PowerShell's unary array operator. It wrapped the tail of the list in a
# nested array; this script killed the live bot, then Start-Process refused
# with "Cannot convert 'System.Object[]' to the type 'System.String'", and
# the bot stayed down. watch_bot.ps1 calls this same script, so every retry
# failed the same way. The operator had been told the new bot was live; it
# was not running at all.
#
# THE ORDER OF OPERATIONS IS THE WHOLE LESSON. This script's one dangerous
# act is stopping a money process before starting another, so anything that
# can make the START fail must be checked while the OLD bot is still
# running. Then the worst case is "nothing happened" rather than "nothing
# is running".
$botArgs = @(
    "-u", "$repo\research\pinrun.py",
    "--live", "--size", "20", "--minutes", "4320",
    "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "2",
    "--improve-scope", "market", "--pick", "best",
    "--max-per-market", "2", "--improve-max", "0.010",
    "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate",
    "--hedge-belief", "0.60",
    # AMENDMENT 46 REOPENED 2026-09-18 ~02:2xZ, at a THIRD and with a PRICE
    # FLOOR. The operator: "Can you re open 45 seconds with a cap at 90c, or
    # whatever number you like?"
    #
    # Why it is back: the pickoff tracker says the cheap offers are taken a
    # median of 41 s before the close while our window starts at 30 s, so the
    # 31-45 s band is where the trades we are missing actually live. Closing it
    # entirely gives up the only lever that addresses the real problem.
    #
    # Why a THIRD and not a full bet: its full-size life was 31 markets, 29
    # settled, 29 won, +$35.81, and then ONE fill took $27.87 back --
    # KXBTC15M-26SEP172115-15, ask seen 97.8c, FILLED AT 53.0c because the book
    # collapsed inside our 160 ms round trip. A limit is a MAXIMUM, so no price
    # rule can prevent that fill; only size bounds it. At a third it costs ~$9.
    #
    # Why the 90c floor (AMENDMENT 49): out at 31-45 s less of the settlement
    # average is locked, so `fair` leans harder on the sigma estimate. A cheap
    # ask there is the market disagreeing with us exactly where our model is
    # weakest. Inside 30 s the full leg is untouched.
    # A THIRD -> FULL, 2026-09-18 ~17:0xZ, on the operator's word: "If you're
    # ready, then yes increase to 45." The third was a precaution from a
    # mechanism story; the live record does not support it. 31-45 s on real
    # money: 57 markets, 1 model miss (hedged to +$4.36), +$64.79. The main
    # window: 475 markets, 11 misses. Same miss rate. And post-fix, 26 of 34
    # early legs got NO top-up because by 30 s nothing was left to buy -- at a
    # third that forgoes two thirds of the position on three markets in four.
    # Post-fix early legs at a third: 31 markets, 31 won, +$33.59.
    "--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90",
    # AMENDMENT 50, 2026-09-18. The operator asked what to do with the
    # 45-second leg in the meantime: "It's earning good it'd be a shame to
    # shut it off, but also a shame to lose money... It might mean smaller
    # gains but that's better than none."
    #
    # This is a REFUSAL, not a new way to buy, so its worst case is fewer
    # trades. Out at 31-45 s, our model being far ABOVE the market price is a
    # warning rather than a bargain, and the sign flips at 30 seconds:
    #
    #   31-45 s   under 3c  177 bets  3 lost  +0.06 $/bet
    #             3-6c       62 bets  5 lost  -0.57 $/bet
    #             6c+        11 bets  3 lost  -3.01 $/bet
    #   <=30 s    6c+       263 bets  1 lost  +1.44 $/bet   (live: +3.08)
    #
    # Because at 45 s only a quarter of the settlement average is locked, so
    # our confidence rests on a volatility estimate; at 15 s three quarters is
    # already recorded and the market is simply wrong. Refusals log as
    # `early_wide`. INSIDE 30 s NOTHING CHANGES -- a wide edge there is the
    # single most profitable thing the bot does.
    # 3.0 -> 10.0, 2026-09-19. THE CAP WAS A PRICE FLOOR IN DISGUISE AND
    # NOBODY INTENDED IT. Our model is usually ~100% sure, so edge is
    # (1 - price) - fee; a 3c cap therefore forbade ANY early buy under
    # about 96.5c, and the 90c floor below never got a chance to bind. That
    # is why every fill was 97-98c. The operator, shown the arithmetic:
    # "WOAH WHAT WE CANT BUY CHEAPER THAN 96.5??? ... please get rid of
    # whatever is blocking us from cheap trades."
    #
    # At 10.0 the 90c FLOOR is what binds (90c is worth 9.37c of edge), so
    # the early leg may now buy 90-98c instead of 96.5-98c. The gate stays
    # in place, still logs `early_wide`, and can be tightened again without
    # a code change.
    #
    # WHAT WE GIVE UP. A50 was built on the tape -- 6c+ edges at 31-45 s
    # lost 3 of 11 -- and rule 5 says the tape cannot price OUR losses. The
    # one live loss of that shape was 93c with 6.43c of edge, -$18.69, in
    # the uncapped paper arm. Both uncapped arms are ahead of live (+12% on
    # 27 markets, +41% on 28), but neither is old enough to be a result.
    # BAR: revert to 3.0 at TWO losing closes on early fills under 96c in
    # the first 40 such fills. The 90c floor is the adverse-selection guard
    # and it does not move tonight.
    "--early-max-edge", "10.0",
    # THE RISK SETTING, 2026-09-18, operator: "Sure divide by 8." One bet goes
    # from bank/5.88 to bank/8 -- at a $613 bank that is 104 contracts down to
    # 76, about $75 a bet. The worst a single close can cost falls from 33% of
    # the bank to 25%; the earning rate falls about a quarter. He was shown
    # both halves and chose it.
    # --price-ceiling 0.99 was passed here for about four minutes on
    # 2026-09-18 ~17:0x ET and the bot DID NOT COME BACK: pinrun runs its own
    # self-test at startup with the flag already applied, and four older checks
    # assert the 98c ceiling against the RUNNING value (worst_close_cost,
    # ladder_under, two A45 room checks). Those must be rewritten against the
    # declared default before the flag can be used live. Removed; see
    # results/VERSIONS.md v-ceiling99 for the full account.
    # (--bank-brake moved to the bottom of this list with AMENDMENT 56; a
    # duplicated flag makes argparse take the LAST one, so there must be
    # exactly one.)
    # v-bands, 2026-09-18 ~21:5xZ, three flags on the operator's word:
    # "Okay remove insurance. But keep hedging. We can remove 94-96. If it's
    # safe then yea you figure out a way to buy more beneath 94."
    #
    # --hedge-price 0.60 (A47): the hedge still fires when OUR belief drops
    # under 0.60, but only if the market agrees -- our side under 60c, so
    # the other side's ask over 40c. Every live hedge bought at 10-27c (the
    # market still 73-90% on us) hurt: 5 of 5, -$41.72. Both bought at 47c
    # and 74c helped: +$8.80. Same threshold as the belief, so the rule is
    # "model AND market both say under 60%".
    "--hedge-price", "0.60",
    # --skip-band 0.94 0.96 was staged here for about an hour on 2026-09-18
    # and REMOVED BEFORE IT RAN. The "+0.8% on 83 closes" figure was three
    # losses from the first-week bot (09-09, 09-10, 09-12); on the modern
    # bot (09-13 on) the band is 38 closes, 1 loss, +$51.82, 2.25% --
    # better than 96-97.5c. And no refusal under 94c has ever been for a
    # slot or a close budget, so "it frees a slot" had no evidence either.
    # The operator asked whether it was coincidence; it was. Paper arm
    # `arm-b-skip9496` tests the skip beside the control instead.
    # --band-mult 0.90 0.94 1.5 (A53): 64 live closes at 90-94c, no loss,
    # break-even 8%; the touch held a median 192 against the 97 we took on
    # 09-18. One order may reach 1.5x SIZE there, through the A45 drawdown
    # headroom, the book and the close budget. BAR: revert at the first
    # loss on a boosted fill in the first 20 boosted closes; at 20 clean,
    # 2.0. Fill quality at the larger size is the unproven part (rule 5).
    "--band-mult", "0.90", "0.94", "1.5",
    # AMENDMENT 48 + 55, 2026-09-18 ~23:5xZ. The operator: "Yes a48 live,
    # make sure it's got good confidence when buying in the last 10 seconds,
    # have it run at the full normal rate immediately, cut at first loss. If
    # it looks like it's going to a loss don't buy the extra, and obviously
    # if it's losing hedge if possible in those last seconds."
    #
    # A48 (--late-tau/--late-mult): inside the last 10 seconds one order may
    # reach 1.5x SIZE. Paper record, 49 markets over 29 hours, ZERO losses,
    # +15.1% against the live bot on the same markets. Our own live fills
    # say that window earns 5.35c a contract against 1.90c at 16-30 s.
    "--late-tau", "10", "--late-mult", "1.5",
    # A55, his three conditions, each enforced in code:
    #  * "good confidence": the EXTRA contracts need 99.75% where an
    #    ordinary bet needs 99.5%. Measured on 109 live signals inside 10 s:
    #    this allows 71% of them, and the ONE that lost sat at 99.612% --
    #    below the bar, so it would have been refused the extra.
    "--late-pin", "0.9975",
    #  * "if it looks like it's going to a loss don't buy the extra": a
    #    one-second move of 2 sigma against us skips the boost. It must be
    #    TIGHTER than --jump-gate's 3.0, which already refused the trade
    #    outright; at 4.0 it could never have fired and the bot now refuses
    #    to start on such a value.
    #  * "cut at first loss": one late-boosted loss sets LATE_MULT back to
    #    1.0 for the rest of the run (record `late_boost_off`). No flag; the
    #    bot enforces it. Hedging is unchanged and still fires at any tau,
    #    including inside the last seconds.
    #
    # THE COMMA GOES HERE, ON THE VALUE, NEVER ON ITS OWN LINE. A bare `,`
    # between elements is PowerShell's unary array operator: it wrapped the
    # rest of this list in a nested array, Start-Process refused
    # "Cannot convert 'System.Object[]' to the type 'System.String'", and on
    # 2026-09-19 00:02Z this script killed the live bot and then failed to
    # start it. THE BOT WAS DOWN AND NOTHING SAID SO -- watch_bot.ps1 calls
    # this same script, so it failed the same way every minute.
    "--late-jump", "2.0",
    # AMENDMENT 56, 2026-09-18. The operator: "if we've never lost multiple
    # coins at once, allow extra total size if it comes in the way of an
    # extra coin after two have been maxed out. I'm okay with that."
    #
    # His condition is MEASURED and holds: of 417 closes we have traded, 19
    # had a losing coin and NOT ONE had two -- in every case the other coins
    # at that close won. Twelve of those closes already held three coins.
    # And the budget really does bind: 326 markets were refused for
    # close_budget on a coin we were NOT holding, about 65 a day.
    #
    # A THIRD coin at a close may now spend one extra bet of budget. A coin
    # we ALREADY hold gets nothing extra -- the argument is about two COINS
    # never losing together, not about a second bet on the first coin.
    "--extra-coin", "1",
    # AMENDMENT 59 + 61, 2026-09-19. Inside --late-tau a close may spend one
    # extra bet whatever it already holds. That window is the best we have:
    # 94.8c median against 97.8c at 31-45 s, 5.4c a contract against 2.2c,
    # and no losing close in 68 fills -- and `close_budget` refused 126
    # markets in it.
    #
    # IT SHARES the --extra-coin allowance rather than adding a second, so
    # the worst close stays at THREE bets and the bet size does not move
    # (72 contracts at a $640 bank and a 3.00 brake, identical to before).
    # One extra bet, spendable by a new coin OR in the last seconds,
    # whichever arrives first.
    "--late-extra", "1",
    # AMENDMENT 64, 2026-09-19, operator: "Then increase to 15 seconds if it
    # means better cheaper buys." The extra BUDGET reaches 15 s while the
    # 1.5x BOOST stays at 10 -- they were sharing --late-tau and should not.
    # The boost is extra RISK on the bets with least time to recover and
    # wants a tight window; the extra budget is only permission to spend
    # what the close was already allowed, and wants a wide one.
    #
    # MEASURED, on the 97 closes where close_budget ran out: 75% of the
    # budget had gone at MORE than 15 s left, median 97.6c (worth ~2.2c a
    # contract), and 38% of the refusals landed inside 15 s where the median
    # is 96.0c and the last ten seconds return 5.4c a contract.
    "--late-extra-tau", "15",
    # THE PRICE, stated because it is the only change tonight that raises
    # the worst case. worst_close_cost grows from 2 bets to 3, and every
    # rail reads it, so at a fixed brake the bet size would fall. At a $640
    # bank:
    #     brake 4.08 + extra-coin 1 -> 53 contracts, worst close $156 (as now)
    #     brake 3.00 + extra-coin 1 -> 72 contracts, worst close $212
    #     brake 2.72 + extra-coin 1 -> 80 contracts, worst close $235
    # He asked for extra TOTAL size, not the same total spread thinner, so
    # the brake moves to 3.00: bets 80 -> 72, a third coin allowed, and the
    # worst close $157 -> $212 (the bank covers it 3.0x instead of 4.1x).
    # To keep 80-contract bets instead, set 2.72; to keep tonight's risk
    # exactly, set 4.08 and accept 53.
    # 3.00 -> 4.08 -> 3.00 AGAIN, 2026-09-19 ~03:3xZ. "Cap losses at 200, keep
    # bet size" was read as "hold the bet at 77 while the bank grows"; it meant
    # the opposite. The operator, one close later: "Wait why that seemed
    # perfectly fine I want the same size ratio just after $200 in losses
    # brake." THE RATIO IS THE BRAKE, so the brake does not move. At the $928
    # bank this is 105 contracts and a $309 worst close, covered 3.0x. Only
    # --loss-cap below is new. 4.08 was live for one close (03:30:58Z, size 77,
    # no fills) and is reverted.
    "--bank-brake", "3.00",
    # AMENDMENT 65, same instruction. The loss abort has always been DERIVED
    # (-2 x SIZE x MAX_PER_CLOSE) and therefore GREW with the bank -- it had
    # already reached -$420 at 105 contracts. This is a hard dollar cap: the
    # abort is the TIGHTER of the band and this number, re-applied on every
    # autosize so a moving bank cannot undo it.
    "--loss-cap", "200"
    # AMENDMENT 46, deployed 2026-09-17 ("As long as you have the 45 second is
    # built as safely as you described, deploy now"), first at half, then at a
    # THIRD, and from ~19:5xZ the same day at a FULL bet on his instruction:
    # "Bump 45 seconds up to normal price as well."
    #
    # So 31-45 s now buys a FULL bet, and the top-up leg becomes a no-op
    # (staged_take returns size - early_held = 0). One early leg per market is
    # still enforced by the "early_once" refusal, so this cannot double up.
    # In effect TAU_MAX is 45 for the first bet, which is exactly what the flat
    # tau-45 paper arm has been testing: 33 settled closes, 0 losses, +230% more
    # closes than its control.
    #
    # WHAT IT GIVES UP: at a third we got a foot in the door early and completed
    # at 30 s when the information was better. At full we commit at the earlier,
    # worse-information moment and cannot improve the price afterwards.
    # WHAT SUPPORTS IT: on the tape BY MARKETS, buyers of 95-98c at 31-45 s lost
    # 2.8% (606 markets) against 3.9% at 16-30 s (389) -- the earlier window is
    # not the worse one. Model error at 31-45 s is 0.058% of moments, ~1/200th
    # of our live loss rate, so the risk here is adverse selection, not
    # arithmetic, and only live fills can measure it.
    # Bar and revert UNCHANGED: results/PREREG_staged.md stage 2 -- revert at 3
    # losses on early-leg closes in the first 40, or 2 in the first 15.
    # REVERTED TO PAPER 2026-09-18 ~01:5xZ on the operator's instruction:
    # "Revert 45 seconds to just a paper". It ran live for ~12 hours at a third
    # and then a full bet. Record: 31 markets carried an early leg, 29 settled,
    # 29 won, +$35.81 -- but the two still open include KXBTC15M-26SEP172115-15,
    # where we saw an ask of 97.8c, filled at 53.0c because the book collapsed
    # inside our 160 ms round trip, and the hedge locked -$27.87. At the old
    # third-size that loss would have been about -$9. So the honest net is
    # roughly +$8 on 31 markets, and the one bad fill cost more than the other
    # thirty made.
    # The flags now live on a PAPER arm only (results/arm-early45.out).
)

$__bad = @($botArgs | Where-Object { $_ -isnot [string] })
if ($__bad.Count -gt 0 -or $botArgs.Count -lt 5) {
    Write-Host "ABORTING: the argument list is not a flat list of strings"
    Write-Host "  elements: $($botArgs.Count), non-string: $($__bad.Count)"
    Write-Host "  A bare comma on its own line makes a nested array."
    Write-Host "NOTHING WAS STOPPED -- the running bot is untouched."
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
Write-Host "argument list ok: $($botArgs.Count) flat strings"

# --- 1. REFUSE IF NOT FLAT. Restarting mid-position abandons a live bet: the
# new process does not know about it, so it never settles it, never hedges it
# and never counts it against the loss brake.
#
# 2026-09-17: THE CHECK IS research\pinflat.py, NOT A COUNT. The count
# ("filled orders > settled records") deadlocked when the bot DIED holding a
# bet: the settled record it would have written never arrives, so the count
# never balances and this script refused forever -- with the watchdog calling
# it every minute. pinflat knows whether the bot is alive (pid file) and reads
# each open fill's close time from its ticker: alive + open fill = wait; dead +
# market still ahead = wait (a new bot could buy that close twice); dead +
# market closed = flat, it settled on the exchange without us.
$flatOut = & $py "$repo\research\pinflat.py" 2>&1
$flatCode = $LASTEXITCODE
foreach ($l in $flatOut) { Write-Host "pinflat: $l" }
if ($flatCode -eq 1) {
    Write-Host "REFUSING: the bot is holding a position (see pinflat above)."
    Write-Host "Wait for the close to settle, then run this again."
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
if ($flatCode -ne 0) {
    # the helper itself failed: fall back to the old count, which errs on
    # the side of refusing.
    Write-Host "pinflat could not answer (exit $flatCode) -- falling back to the count"
    $log = Get-ChildItem "$repo\results\pinrun-live-*.jsonl" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) {
        $filled = 0
        $settled = 0
        foreach ($line in Get-Content $log.FullName) {
            if ($line -match '"kind":\s*"order"' -and $line -notmatch '"filled":\s*0(\.0+)?[,}]') { $filled++ }
            if ($line -match '"kind":\s*"settled"') { $settled++ }
        }
        Write-Host "newest log: $($log.Name) -- $filled filled orders, $settled settled"
        if ($settled -lt $filled) {
            Write-Host "REFUSING: the bot is holding a position ($filled filled, $settled settled)."
            try { Stop-Transcript | Out-Null } catch {}
            exit 1
        }
    }
}

# --- 2. STOP ONLY pinrun.
# ONLY THE LIVE ONE. On 2026-09-13 this matched '*pinrun*' and killed the
# WHAT-IF tracker too -- a paper pinrun the operator had asked to keep running.
# The live bot is the one carrying --live; nothing else may be stopped here.
#
# 2026-09-14: AND THE PID FILE IS THE PRIMARY SOURCE, NOT CommandLine.
# When the operator ran this himself, Win32_Process returned CommandLine EMPTY
# for the running bot -- Windows hides it from a caller that cannot open the
# process -- so this loop matched nothing, printed nothing, and the script went
# on to start a SECOND live bot. Two bots then traded the same account for 24
# minutes, each sizing off the same bank, each counting only its own fills
# against the loss abort, stake cap, position cap and losing-trade brake. Every
# rail was silently doubled.
$pidfile = "$repo\results\pinrun-live.pid"
$targets = @()
if (Test-Path $pidfile) {
    $wanted = (Get-Content $pidfile -Raw).Trim()
    if ($wanted -match '^\d+$') {
        $proc = Get-Process -Id ([int]$wanted) -ErrorAction SilentlyContinue
        if ($proc) { $targets += [int]$wanted }
    }
}
# belt and braces: the CommandLine sweep as well, in case the pid file is
# missing (a bot started before this amendment leaves none).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' -and $_.CommandLine -like '*--live*' } |
    ForEach-Object { if ($targets -notcontains $_.ProcessId) { $targets += $_.ProcessId } }

if ($targets.Count -eq 0) {
    Write-Host "no live pinrun found to stop (pid file: $(Test-Path $pidfile))"
} else {
    foreach ($id in $targets) {
        Write-Host "stopping live pinrun pid $id"
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 3

# --- 2b. PROVE IT IS GONE BEFORE STARTING ANYTHING.
# THIS IS THE RULE THAT MATTERS: a kill that failed must ABORT the restart,
# never fall through into a second start. Checked by PID, which needs no
# permission to read, rather than by CommandLine, which is what failed.
$stillAlive = @()
foreach ($id in $targets) {
    if (Get-Process -Id $id -ErrorAction SilentlyContinue) { $stillAlive += $id }
}
if ($stillAlive.Count -gt 0) {
    Write-Host "ABORTING: could not stop live pinrun pid(s) $($stillAlive -join ', ')."
    Write-Host "Starting a second one would put TWO bots on the same account."
    Write-Host "Stop it by hand, then run this again:"
    foreach ($id in $stillAlive) { Write-Host "    Stop-Process -Id $id -Force" }
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}

# --- 3. START IT AGAIN.
# CAPTURE STDERR. Until 2026-09-15 this started the bot with no redirect at
# all, so when trade_loop raised the traceback went to a hidden window and
# vanished. The bot died at 04:29:30Z on a TypeError in a logging line and
# nobody knew for sixteen minutes -- the only evidence was an `end` record
# with an empty state. Two files, appended, never rotated by this script.
$errLog = "$repo\results\pinrun-live.err"
$outLog = "$repo\results\pinrun-live.out"
Start-Process -FilePath $py -RedirectStandardError $errLog -RedirectStandardOutput $outLog -ArgumentList $botArgs -WorkingDirectory $repo -WindowStyle Hidden
Start-Sleep -Seconds 15

# --- 4. PROVE IT CAME BACK, and prove the collector survived.
$new = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' -and $_.CommandLine -like '*--live*' }
if (-not $new) {
    Write-Host "FAILED: pinrun did not come back. Check results\pinrun-live-*.jsonl"
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
Write-Host "pinrun running: pid $($new.ProcessId)"
# THE COLLECTOR CHECK IS BY FILE, NOT BY PROCESS LIST. The 2026-09-14 run
# reported "collector processes alive: 0" and raised a false alarm, for the
# same reason the kill failed: CommandLine came back empty. Both collectors
# were in fact running and had been since Sep 9. What actually proves a
# recorder is alive is that it is still WRITING, so that is what is checked.
# THE TWO RECORDERS WRITE DIFFERENTLY AND MUST BE CHECKED DIFFERENTLY.
# kalshi_collector flushes continuously, so its newest file is always seconds
# old. crypto_feeds gzips a whole hour in memory and writes it at the
# ROTATION: every one of its files has a LastWriteTime of exactly the top of
# the following hour, and the file for the hour in progress sits at 0 bytes
# until that hour ends. A naive "newest file is fresh" test therefore fails on
# a perfectly healthy feed recorder for 59 minutes out of every 60. Verified
# against six consecutive hours on 2026-09-14, each 280-690 KB, each written
# on the hour.
$fresh = 0

# BOTH recorders gzip a whole hour in memory and write it at the ROTATION.
# An in-progress file therefore sits at 0 bytes for up to 59 minutes, and a
# "newest write was N seconds ago" test alarms on a perfectly healthy recorder
# for most of every hour. The first version of this check applied that test to
# kalshi_data and duly cried wolf at 23:21 on 2026-09-14 with both collectors
# alive and burning CPU since Sep 9.
#
# The real proof of life: the PREVIOUS hour landed with bytes in it, and a
# file is open for the hour in progress.
$prevName = (Get-Date).ToUniversalTime().AddHours(-1).ToString("yyyyMMddTHH") + ".jsonl.gz"
$curName  = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHH") + ".jsonl.gz"
foreach ($d in @("C:\kals\kalshi_data", "C:\kals\feed_data")) {
    $prev = Get-ChildItem $d -Recurse -File -Filter $prevName -ErrorAction SilentlyContinue
    $cur  = Get-ChildItem $d -Recurse -File -Filter $curName  -ErrorAction SilentlyContinue
    $prevBytes = ($prev | Measure-Object -Property Length -Sum).Sum
    $name = Split-Path $d -Leaf
    Write-Host "$name -- last full hour $prevBytes bytes across $($prev.Count) channels; $($cur.Count) open now"
    if ($prevBytes -gt 0 -and $cur.Count -gt 0) { $fresh++ }
}

if ($fresh -lt 2) {
    Write-Host "WARNING: a recorder may have stopped. The tape is NOT"
    Write-Host "reproducible -- check run_all.ps1 before anything else."
} else {
    Write-Host "both recorders are writing"
}
Write-Host "flags now live: $($new.CommandLine)"
Write-Host "restart_bot.ps1 done $(Get-Date -Format o)"
try { Stop-Transcript | Out-Null } catch {}
