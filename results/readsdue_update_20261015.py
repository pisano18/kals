"""2026-10-15 ~06:3xZ READS_DUE update (session 828be284): the four overdue items read, the hunt relaunched."""
import json, io
P = r"C:\kals-repo\results\READS_DUE.json"
d = json.load(open(P, encoding="utf-8"))
by = {it["id"]: it for it in d["items"]}

def note(iid, text, due=None, status=None):
    it = by[iid]
    it.setdefault("read_log", []).append(text)
    it["read_note"] = text
    if due: it["due"] = due
    if status: it["status"] = status

note("strategy-hunt-1013",
     "10-15 06:3xZ: the 10-13 run (wf_fc310361-b2c) died with its chat at ~12:41Z 10-13 after Map + 12 of 15 hunter lanes "
     "(108 ideas; weather-model, revisit, pro-desk cut off; merge/test/critic never ran). RELAUNCHED as strategy-hunt-1015 "
     "(operator 10-15: 'Rerun hunt. Main priority put all resources into this') carrying all 12 lanes' output "
     "(.sweep/hunt-2026-10-15/r1_carry.json). See item strategy-hunt-1015.", status="read")
d["items"].append({
    "id": "strategy-hunt-1015",
    "due": "2026-10-16T12:00Z",
    "what": "Strategy hunt RESUMED 2026-10-15 06:25Z: Workflow wf_bc826eb0-aaf (task wp4z84rbs, session 828be284, script "
            "C:/Users/Joe/.claude/projects/C--kals-repo/828be284-0a9a-4233-9a4c-58fd0781cd83/workflows/scripts/strategy-hunt-1015-wf_bc826eb0-aaf.js). "
            "Round 1: 3 cut-off lanes (weather-model, revisit, pro-desk) + 5 new (structural-arb-scan, slow-source-settlement-lag, "
            "politics-entertainment-tech, new-listings-flows-timing, kalshi-mechanics-capital); 5 mergers (3 over the carried 108 ideas, 2 over "
            "the new) + ranker; up to 32 real-data tests, each survivor to 2 skeptics (+ tiebreak); critic; up to 3 rounds (no early stop); "
            "specs for the top 10; writer. Read-only, no orders. ~7 agents at a time. Scratch C:/kals-repo/.sweep/hunt-2026-10-15/.",
    "how": "Workflow result (task notification) + results/STRATEGY_HUNT_2026-10-15.md + results/strategy_hunt_2026-10-15.json + the SH rows "
           "in results/IDEA_LEDGER.md. Reconcile every strong survivor's $/day by hand before reporting. Journal: "
           "C:/Users/Joe/.claude/projects/C--kals-repo/828be284-0a9a-4233-9a4c-58fd0781cd83/subagents/workflows/wf_bc826eb0-aaf/journal.jsonl; "
           "every agent also saves RESULT.json in its scratch folder. If the chat dies: the journal + RESULT.json files hold whatever finished.",
    "bar": "'strong' = tester viable + both skeptics fail to refute (or tiebreak) + realistic >= $5/day at today's bank. Each strong or "
           "viable-small survivor -> a paper bot with a watcher and its own READS_DUE bar; nothing goes live without the operator's GO "
           "(new strategy family).",
    "status": "open"})
note("disk-guard",
     "10-15 04:4xZ: RESOLVED -- 130 GB free after the 10-14 outage (was 13-17 GB on 10-13); what freed it was not checked "
     "(the operator said he would get storage). Recorders alive. Daily watch no longer needed; the 6 GB guard rule stands.",
     status="read")
note("arm-5hz",
     "10-15 05:3xZ: CANNOT BE READ -- 3 of the 5 full ET days (10-10, 10-11, 10-12); the twin's 7-day run ended 10-13 18:59Z and was not "
     "relaunched; arm-5hz stopped at the 10-14 03:29Z shutdown and did not restart. 5 Hz feed DID reach spot(): 63 of 75 fast-coin signals "
     "index_age_s < 0.25 s (twin 65 of 116). Shared closes 437 (10-09 05:30Z..10-13 18:45Z): arm +$174.81 on $5,683 bet (137 mk, 3 lost "
     "-$67.62) vs twin +$178.83 on $5,871 (135 mk, 4 lost -$67.69); the loser gap is one market (BNB 10-10 08:00Z: twin 87 contracts hedged "
     "-$11.78, arm 4 contracts +$0.49). Live condition: 4 markets, live -$33.23 with 1 loser (ETH 10-10 09:15Z -$47.13) -> neither PROMOTE "
     "(needs >= 2 losers, <= -$40) nor KILL (>= $0). Paper half would pass. Verdict by the bar: run 5 more days -- needs BOTH arms relaunched "
     "(twin argv results/relaunch_twin_1006.cmd.txt; arm results/start_arm5hz.ps1; repo pinrun still 9afb6eca6a91 = the twin's code). "
     "Put to the operator 10-15 ('relaunch 5hz' / 'fresh 5 days'). Scripts: session scratchpad arm5hz/read5hz.py.",
     due="2026-10-18T12:00Z")
note("snowball-live",
     "10-15 05:2xZ interim: RUN-ON, plumbing all pass. 11 KXBTCD orders since 10-11 10:43Z, every one <= floor(SIZE x 0.12) at the time "
     "(cap 11 at SIZE 93-99; the 6-contract order came at SIZE 100, cap 12); no KXBTCD late boost; largest holding 11. All 23 autosize + "
     "49 loss_cap records = 0.187 x base to the cent (base = bank - min(0, day)). 110 settled records: no ticker counted twice, no counted "
     "market netted positive. Kalshi: 6 hourly markets, 0 lost, +$1.25 (logs $1.25). 6 of 40 -> ~2 more weeks.",
     due="2026-10-29T08:00Z")
note("fastconn-live",
     "10-15 05:2xZ: no revert trigger fired; KEEP quality tests all pass but n short -> RUN-ON. Window 10-12 11:15Z..10-15 05:04Z "
     "(40.2 bot-hours; 25.2 h outage 10-14 03:29Z..10-15 04:42Z): 89 orders (86 entries + 3 hedges), all warm, all 201, conn_result ok; "
     "warm entry latency median 43.2 ms (p90 65.8) vs 553 pre-deploy entries median 89.6 (p90 112) = 46.4 ms faster; 86/86 last-60-s entries "
     "warm; 3 hedges sent 2-4 ms after the alarm (conn 39-54 ms); 4 conn_events, all stale_replaced GETs at 19.6 s idle on 10-13 02-04Z, "
     "< 1 ms; conn_stats 76,513 requests, 0 failed/unknown/retried/lookups; no hedge_unknown; no duplicate client_order_id/order_id, "
     "contracts per side = Kalshi on all 51 markets; 1 halt = the 10-14 02:30:50Z 2-loss pause (not a connection event). Traceback check "
     "partial: pinrun-live.err of the 10-12..10-14 runs overwritten. 89 of 150 orders -> ~10-16 08Z.",
     due="2026-10-16T12:00Z")
note("hype-live-frac",
     "10-15 05:2xZ interim: no trigger. 7 HYPE orders on 5 markets (3 filled), coin_size = floor(SIZE x 0.15) on every signal (14; 15 at "
     "SIZE 100), largest order 14, largest position 14 YES; 22:30 ET 10-13 market held 4.66 YES + 9.32 NO after insurance (4 ms after the "
     "alarm, 4.66 NO at 55c); other coins' sizes unchanged. Kalshi: 3 HYPE markets, 1 lost -$2.45, net -$1.98 on $29.83 bet. That $2.45 "
     "loss was the 2nd loss of the run and paused the whole bot 15 min (loss count is per market, not per dollar).")
json.dump(d, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ok", len(d["items"]), "items")
