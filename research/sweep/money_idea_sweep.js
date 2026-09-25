export const meta = {
  name: 'money-idea-sweep',
  description: 'Scout every Kalshi/Polymarket US market family (and anything else legal) for bot-tradeable money ideas, cross-breed, viability-check and refute each, update the idea ledger',
  whenToUse: 'When the operator asks for "the money sweep" / "find new ways to make money" / a broad hunt for new markets or strategies. Read research/sweep/README.md first.',
  phases: [
    { title: 'Scout', detail: 'one scout per market family, a free-roaming scout and a revisit scout' },
    { title: 'Combine', detail: 'combiners cross-breed scout ideas from different angles' },
    { title: 'Merge', detail: 'dedupe against this run AND the idea ledger, rank priors' },
    { title: 'Check', detail: 'quick measured viability check per idea' },
    { title: 'Refute', detail: 'independent skeptic tries to kill each surviving idea' },
    { title: 'Critic', detail: 'wrongful kills, missed families, new ideas (checked too)' },
    { title: 'Write', detail: 'dated report + json, and the idea ledger updated' },
  ],
}

// ---- arguments (Workflow args). Date.now() is unavailable in workflow scripts,
// so the caller passes the date. Everything else has a default.
//   { date: "2026-10-05",            REQUIRED, UTC date, used in file names
//     focus: ["weather", ...],       optional: run only scouts whose key contains one of these
//     maxCheck: 60, limit: 7,        optional: ideas checked; agents at once (RAM: ~7 on the laptop)
//     bank: "$900",                  optional: current Kalshi bank, for $/day maths
//     extra: "free text"             optional: anything the operator added this time }
const A = (typeof args === 'object' && args) ? args : {}
if (!A.date) throw new Error('pass args.date, e.g. {"date": "2026-10-05"}')
const DATE = A.date
const REPO = 'C:/kals-repo'
const SW = REPO + '/.sweep/run-' + DATE
const CAT = REPO + '/.sweep/catalogue'
const LEDGER = REPO + '/results/IDEA_LEDGER.md'
const LIMIT = A.limit || 7
const MAX_CHECK = A.maxCheck || 60
const BANK = A.bank || '$900'

async function pool(items, limit, fn) {
  const out = new Array(items.length)
  let i = 0
  async function worker() {
    while (i < items.length) {
      const k = i++
      try { out[k] = await fn(items[k], k) } catch (e) { out[k] = null }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()))
  return out
}

const PRE = `
You are one agent in a research sweep for the operator of a small real-money prediction-market bot. Goal: find ANY realistic, bot-runnable way to come out ahead, then do a quick honest viability check. It does not have to be small-consistent-wins like the existing bot; it just has to come out on top after fees and losses. Be creative, combine ideas across markets nobody would combine, pull threads in odd directions -- and be brutally critical of yourself. Accuracy beats enthusiasm: every large edge this project ever found was a measurement bug.

SCOPE -- the operator's words: "they can pull any information from anywhere and make money in any way possible." So:
- INFORMATION: any public source anywhere -- official data feeds and APIs, government releases, league/stat feeds, weather observations, exchange market data (crypto spot/futures/options books, CME/FedWatch, sportsbook odds, other prediction markets), social media, news wires, live streams/captions, satellite/sensor data, scraping of public pages, academic papers, GitHub repos of other bots, trader forums. Paid data is allowed as an idea if you price it in.
- WAYS TO MAKE MONEY: taking, making (resting quotes), cross-venue, hedging, incentive/reward programs, interest, capital efficiency, combinations, and any other venue a US retail account can legally use for event contracts (name it and what opening it would take). Primary venues: Kalshi (bank ${BANK}) and Polymarket US.
- LIMITS (the only ones): legal for a US retail account; no market manipulation, spoofing, wash trading or self-trading; no trading on non-public/insider information; no exploiting a venue bug in a way its terms forbid; no deceiving people.

THE IDEA LEDGER -- READ IT FIRST: ${LEDGER}. It lists every idea earlier sweeps and sessions checked, with status (live / testing / viable / needs-data / dead) and the reason, plus HOT AREAS and UNRESOLVED items. Do not re-propose a dead idea unless you have a genuinely new angle and say exactly what is new. Prefer hot areas and unresolved items; a needs-data idea whose data now exists is worth deciding.

HARD RULES (real money is running on this laptop):
- READ-ONLY. Never place, amend or cancel any order anywhere. Kalshi access only via Python: sys.path.insert(0, r"C:\\kals-repo\\research"); import kauth; status, body = kauth.get("/markets", {"series_ticker": "KXRAIN", "limit": "200"}) -- GET only, signed. Useful paths: /series, /series/{s}, /events?series_ticker=, /events/{e}, /markets?event_ticker=|series_ticker=|status=settled|min_close_ts=|mve_filter=exclude, /markets/{t}, /markets/{t}/orderbook, /markets/trades?ticker=&min_ts=&max_ts=&limit=1000 (cursor paging). Prices in *_dollars, sizes in *_fp. Sleep ~0.1 s between calls; you share a rate limit with a live bot (a few hundred GETs fine, tens of thousands not). research/rungtrades.py is a worked, self-tested example of trade-history analysis.
- Polymarket US read-only key: C:\\kals\\poly_us.py (research/poly/poly_ws_record.py shows the signed WebSocket). GET/WebSocket read only.
- Public web: load WebSearch / WebFetch with ToolSearch ("select:WebSearch,WebFetch").
- NEVER write under C:\\kals\\kalshi_data or C:\\kals\\feed_data (reading is allowed: gzip jsonl, one file per channel per UTC hour; stream one hour at a time). Do not touch, kill or restart any running process. Do not edit anything in C:\\kals-repo except files under your scratch folder (the Write-phase agent alone writes results/). No git commands.
- Memory: ~2 GB free with a live money bot on the box. Python you run must stay under ~200 MB, one script at a time, with a timeout.
- The Bash tool's heredoc HALVES backslashes: write scripts with the Write tool and run them by path.
- Your scratch folder: ${SW}/<your label>/ (create it).

CONTEXT:
- Live strategies: read C:\\kals-repo\\CURRENT_STATE.md and the top of C:\\kals-repo\\OPEN_WORK.md for what runs now (as of 2026-09-25: pinrun buys the near-certain side of Kalshi 15-minute crypto up/down in the last 45 s off the CF Benchmarks index feed; coin race at 5 contracts; hourly BTC ladder at 1 contract).
- Polymarket US (operator, 2026-09-25): offers him ONLY Bitcoin 15-minute and 1-hour up/down; account funded (~$60), eligible. Same CF Benchmarks BRTI 60-s average and same strike as Kalshi's KXBTC15M; book ~1/10-1/50 of Kalshi's. Re-check this: Polymarket may have added contracts since.
- Fees: Kalshi taker ~0.07*p*(1-p) per contract x the series fee_multiplier, rounded up per order; makers usually 0 (check the series). Polymarket US taker 0.0695*p*(1-p), makers PAID 0.0125*p*(1-p). Verify, they change.
- Catalogue: ${CAT}/INDEX.txt and ${CAT}/cat_<Category>.txt (one line per series: ticker | title | freq | 24h volume | open interest | open markets | closes in 7 days | two-sided | fee | settlement sources | sample ticker | sample rules). Built by research/sweep/sweep_catalogue.py; parlay/MVE markets excluded (there are millions).
- Lessons that cost real money or time: supply that OTHER people took is not supply WE would get (our fills are adversely selected); a tape/replay never gives OUR loss rate; cached feeds (Polymarket's public gateway is a ~30 s cache) produced fake arbitrage; "99c offers" were on the risky rung, not the safe one (check WHICH market the supply is on); cluster by event/close, never count correlated markets as independent; state the smallest effect your sample could detect; a progress count of files is not a count of hours.
${A.extra ? '- OPERATOR ADDED THIS RUN: ' + A.extra : ''}
`

const IDEA_PROPS = {
  name: { type: 'string', description: 'short memorable name' },
  family: { type: 'string' },
  markets: { type: 'array', items: { type: 'string' } },
  mechanism: { type: 'string', description: 'exactly how the bot makes money, step by step' },
  why_mispriced: { type: 'string', description: 'who is on the other side and why they lose' },
  must_be_true: { type: 'string', description: 'what would have to hold; what would make it an artefact' },
  evidence_so_far: { type: 'string', description: 'what you actually measured, or "none"' },
  rough_dollars_per_day: { type: 'string', description: 'order of magnitude at the current bank, with reasoning' },
  worst_case: { type: 'string' },
  data_needed: { type: 'string', description: 'cheapest measurement that would confirm or kill it' },
  novelty_vs_killed: { type: 'string', description: 'why this is not a re-proposal of a ledger idea' },
}
const IDEA = { type: 'object', properties: IDEA_PROPS, required: ['name', 'family', 'markets', 'mechanism', 'why_mispriced', 'must_be_true', 'rough_dollars_per_day', 'data_needed'] }
const SCOUT_SCHEMA = {
  type: 'object',
  properties: {
    ideas: { type: 'array', items: IDEA },
    abundant_markets: { type: 'array', items: { type: 'object', properties: { market: { type: 'string' }, why_more_ideas_likely: { type: 'string' } }, required: ['market', 'why_more_ideas_likely'] } },
    measurements: { type: 'string' },
    failures: { type: 'string' },
  },
  required: ['ideas', 'abundant_markets', 'measurements'],
}

const ALL_SCOUTS = [
  { key: 'sports-games', files: 'cat_Sports.txt (game winners, spreads, totals, tennis, cricket, soccer, UFC, F1)', brief: 'Game outcome markets: in-play vs free public score feeds (statsapi.mlb.com, api-web.nhle.com, NBA cdn, cricket/tennis feeds; ESPN returned 403 from this box in 2026-09); the final minutes of decided games; settlement rules (overtime, postponement, voids, stat corrections, settlement timer); obscure high-volume leagues (ITF/ATP challenger tennis); spreads/totals vs moneyline consistency; how long a decided market trades below 97c. Measure with trade history on settled games.' },
  { key: 'sports-props-parlays-futures', files: 'cat_Sports.txt (props, parlays/MVE, futures, awards)', brief: 'Props, multi-leg combination markets (use /markets?mve_filter=only sparingly -- millions exist) and futures: combos priced vs the product of their legs and leg correlation; exhaustive outcome sets (sum of YES asks < $1 or bids > $1 after fees); futures vs implied game paths; props vs free projections; props settling on box scores minutes after the game.' },
  { key: 'elections-politics', files: 'cat_Elections.txt, cat_Politics.txt', brief: 'Exhaustive sets; markets settled on continuously published official counts (roll calls, Federal Register, executive orders, nominations, post counts) where the answer is public before close; scheduled events; long-dated prices far from any plausible probability; cross-market inconsistency; foreign elections with fast official feeds.' },
  { key: 'econ-fin-commodities', files: 'cat_Economics.txt, cat_Financials.txt, cat_Commodities.txt', brief: 'Data releases (CPI, jobs, claims, GDP, PCE, Fed), rates, FX, indices, gas, oil, gold, and the commodity 15-minute series: what is public before settlement (AAA daily gas, nowcasts, FedWatch, futures as read-only fair value); ranges vs thresholds; trading after a release; settlement-source quirks; whether the late-pin logic transfers to commodity 15-minute markets.' },
  { key: 'crypto-other', files: 'cat_Crypto.txt', brief: 'Every crypto series except plain 15-minute up/down. At the top of each hour the 15-minute market, the hourly ladder and the hourly range/bracket markets settle on the SAME 60-second CF Benchmarks average: find inconsistencies and whether a set is ever buyable for < $1 after fees. Also daily/weekly/monthly max/min (one-touch) markets and their early-close rule, coin race variants, alt ladders, range sets. Index tape: C:\\kals\\kalshi_data\\cfbenchmarks_value (read only, stream).' },
  { key: 'weather-science', files: 'cat_Climate_and_Weather.txt, cat_Science_and_Technology.txt', brief: 'NWS/ASOS/METAR observations vs daily high/low markets (the high is often locked by late afternoon -- check every city and the final hours; an earlier kill was about supply); rain vs radar/observations; exact station and rounding; hurricane advisories; launches; quakes.' },
  { key: 'entertainment-mentions-companies', files: 'cat_Entertainment.txt, cat_Mentions.txt, cat_Companies.txt, cat_Social.txt, cat_AI.txt, cat_World.txt', brief: 'Rotten Tomatoes (live Tomatometer), box office (studio estimates before actuals), charts (Spotify daily before Billboard), streaming top-10s, app ranks, awards, "mentions" markets (live transcripts/captions during the event), earnings-call mentions. For each: settlement source, when the answer is public, whether it still trades after, supply at 90-98c.' },
  { key: 'cross-venue', files: 'INDEX.txt plus the open web', brief: 'Polymarket US BTC 15-min/1-h vs Kalshi: pin strategy on Polymarket\'s book (measure from a real-time recording, never the cached gateway); resting on Polymarket for the maker rebate and hedging fills on Kalshi; moments the books disagree by more than both fees; the 1-h contract vs Kalshi hourly markets at the same top-of-hour average. Sharp-sportsbook odds as fair value for Kalshi sports. Any other US-legal event-contract venue listing a contract Kalshi also lists.' },
  { key: 'exchange-mechanics', files: 'INDEX.txt (all)', brief: 'Kalshi incentive/market-maker programs and whether a small account qualifies; interest on cash and positions; per-order fee rounding; fee_multiplier differences (fee-free series?); collateral treatment for mutually exclusive events; settlement timers and early close; new listings (first minutes mispriced?); a generic "answer already public, certain side < 99c" scanner across ALL categories; settlement disputes.' },
  { key: 'calibration-bias', files: 'INDEX.txt (categories with many settled markets)', brief: 'Measure calibration across settled markets by category: for tradeable ASK prices (not last trade or midpoint) in each bucket at fixed times before close (24 h, 1 h, 10 min), how often YES won, net of the taker fee. Favorite-longshot bias, category and time-of-day effects. Cluster by event; state sample sizes and the smallest detectable effect.' },
  { key: 'anything-anywhere', files: 'INDEX.txt and the open web', brief: 'No assigned family. If a well-funded quant shop with our tools (1-second index feed, fast bot, Kalshi API, funded Polymarket US account, a laptop, $900-$5,000) wanted to make money from event contracts any legal way, what would they do first? Search how professional prediction-market traders, Kalshi market makers and arbitrage bots actually make money (interviews, blogs, GitHub, forums, Kalshi program pages, papers) and test the best against the catalogue: predictable flow, capital recycling, options-implied probabilities (Deribit/CME) vs Kalshi ranges, and whatever the family scouts would miss.' },
  { key: 'revisit', files: 'the idea ledger', brief: 'Take the ledger\'s NEEDS-DATA, UNCHECKED and "wrongly killed?" items and HOT AREAS. For each, decide whether the data now exists (new tape, new watchers, more days) and push it to a verdict or a sharper idea. Also re-check any "viable" or "testing" item against what has happened since.' },
]
const SCOUTS = A.focus && A.focus.length ? ALL_SCOUTS.filter(s => A.focus.some(f => s.key.indexOf(f) >= 0) || s.key === 'revisit') : ALL_SCOUTS

phase('Scout')
log('run ' + DATE + ': ' + SCOUTS.length + ' scouts, at most ' + LIMIT + ' agents at a time, scratch ' + SW)
const scouts = (await pool(SCOUTS, LIMIT, (s) => agent(
  PRE + `\nYOUR ROLE: scout "${s.key}". Scratch: ${SW}/${s.key}/. Catalogue files: ${s.files}.\n\n${s.brief}\n\nDo real, quick measurements to ground each idea. Aim for 8-15 concrete ideas, including at least three that combine this family with something else (another family, venue, public feed, our index feed, or the existing bots). Say who is on the other side and why they lose. List ABUNDANT markets where more ideas probably exist. Mark weak ideas weak rather than dropping them.`,
  { label: 'scout:' + s.key, phase: 'Scout', schema: SCOUT_SCHEMA }
).then(r => r ? Object.assign({ scout: s.key }, r) : null))).filter(Boolean)
const scoutIdeas = scouts.flatMap(s => s.ideas.map(i => Object.assign({ source: 'scout:' + s.scout }, i)))
log('scouts returned ' + scouts.length + '/' + SCOUTS.length + ', ideas ' + scoutIdeas.length)
const digest = JSON.stringify(scoutIdeas.map(i => ({ name: i.name, family: i.family, markets: i.markets, mechanism: i.mechanism, why_mispriced: i.why_mispriced, evidence_so_far: i.evidence_so_far, rough_dollars_per_day: i.rough_dollars_per_day })))
const measures = scouts.map(s => '## ' + s.scout + '\n' + s.measurements + (s.failures ? '\nFAILURES: ' + s.failures : '')).join('\n\n')

phase('Combine')
const COMBINERS = [
  { key: 'consistency-arbitrage', brief: 'The same fact priced in several places (legs vs combos, brackets vs thresholds, 15-min vs hourly vs daily, Kalshi vs Polymarket US, exhaustive sets): sets that pay >= $1 in every outcome for < $1 after fees, or nearly so with small bounded risk.' },
  { key: 'information-speed', brief: 'Public data that reveals the answer before the market prices it; one feed that settles many markets; one event moving several markets with different lags.' },
  { key: 'structure-incentives-hedging', brief: 'Incentive programs, fee quirks, interest, capital efficiency; and (the operator\'s #1 priority is LOSE LESS) cheap hedges for the existing crypto bot\'s rare big losses from other markets.' },
  { key: 'wild-card', brief: 'Contrarian and second-order ideas: who else runs bots here and what their patterns leave; timing (weekends, holidays, overnight, listings); human behaviour (fan bias, round numbers, recency); combinations of three or more ideas. Attack each of your own ideas once before submitting.' },
]
const combs = (await pool(COMBINERS, LIMIT, (c) => agent(
  PRE + `\nYOUR ROLE: combiner "${c.key}". Scratch: ${SW}/combine-${c.key}/.\n${c.brief}\n\nBuild NEW ideas by combining, inverting and extending the scouts' ideas below (do not repeat them). Measure where a number decides it. Aim for 6-12 ideas.\n\nSCOUT IDEAS: ${digest}\n\nSCOUT MEASUREMENTS:\n${measures}`,
  { label: 'combine:' + c.key, phase: 'Combine', schema: SCOUT_SCHEMA }
).then(r => r ? Object.assign({ scout: 'combine-' + c.key }, r) : null))).filter(Boolean)
const allIdeas = scoutIdeas.concat(combs.flatMap(c => c.ideas.map(i => Object.assign({ source: 'combine:' + c.scout }, i))))
const abundant = scouts.concat(combs).flatMap(s => (s.abundant_markets || []).map(a => Object.assign({ from: s.scout }, a)))

phase('Merge')
const MERGE_SCHEMA = {
  type: 'object',
  properties: {
    ideas: { type: 'array', items: { type: 'object', properties: Object.assign({}, IDEA_PROPS, { id: { type: 'string' }, merged_from: { type: 'array', items: { type: 'string' } }, prior: { type: 'integer' }, prior_reason: { type: 'string' } }), required: ['id', 'name', 'family', 'markets', 'mechanism', 'why_mispriced', 'must_be_true', 'rough_dollars_per_day', 'data_needed', 'prior', 'prior_reason'] } },
    dropped: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, reason: { type: 'string' } }, required: ['name', 'reason'] } },
  },
  required: ['ideas', 'dropped'],
}
const merged = await agent(
  PRE + `\nYOUR ROLE: merge. (1) Merge duplicates within these ${allIdeas.length} ideas, keeping all evidence. (2) Drop exact re-proposals of DEAD ledger ideas with no new angle (list each with the ledger line it repeats); weak ideas stay with prior 1-2. (3) Prior 1-5, judged critically. Ids ${DATE.replace(/-/g, '')}-01, -02, ... in descending prior.\n\nRAW IDEAS: ${JSON.stringify(allIdeas)}`,
  { label: 'merge', phase: 'Merge', schema: MERGE_SCHEMA }
)
const ideas = ((merged && merged.ideas) || []).slice().sort((a, b) => b.prior - a.prior)
const dropped = (merged && merged.dropped) || []
const toCheck = ideas.slice(0, MAX_CHECK)
const unchecked = ideas.slice(MAX_CHECK)
log('merged ' + ideas.length + ', dropped ' + dropped.length + ', checking ' + toCheck.length + (unchecked.length ? ', NOT checked (listed in report): ' + unchecked.length : ''))

const CHECK_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string' }, verdict: { type: 'string', enum: ['viable', 'plausible-needs-data', 'dead'] },
    measured: { type: 'string' }, realistic_dollars_per_day: { type: 'string' }, capital_needed: { type: 'string' },
    worst_case: { type: 'string' }, killer_risks: { type: 'string' }, next_test: { type: 'string' },
    confidence: { type: 'string', enum: ['low', 'medium', 'high'] },
  },
  required: ['id', 'verdict', 'measured', 'realistic_dollars_per_day', 'worst_case', 'killer_risks', 'next_test', 'confidence'],
}
const REFUTE_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string' }, refuted: { type: 'boolean' }, strongest_objection: { type: 'string' },
    independent_checks: { type: 'string' }, revised_verdict: { type: 'string', enum: ['viable', 'plausible-needs-data', 'dead'] },
    revised_dollars_per_day: { type: 'string' },
  },
  required: ['id', 'refuted', 'strongest_objection', 'independent_checks', 'revised_verdict', 'revised_dollars_per_day'],
}
const checkPrompt = (idea) => PRE + `\nYOUR ROLE: viability checker for ${idea.id}. Scratch: ${SW}/check-${idea.id}/.\nQUICK but REAL check (15-30 min): pull the books, trade history, settlement history or public data that decides it. Realistic $/day after fees at ${BANK} and at $5k, counting supply WE would get (not what others traded), adverse selection, capital lockup, the worst plausible event, correlation. Dead: say the number that kills it. Needs data you cannot get quickly: say what. Never report an unmeasured number as measured; say what would make a good number an artefact and check it.\n\nIDEA: ${JSON.stringify(idea)}`
const refutePrompt = (idea, chk) => PRE + `\nYOUR ROLE: independent skeptic for ${idea.id}. Scratch: ${SW}/refute-${idea.id}/.\nThe checker said "${chk.verdict}". REFUTE it: hidden fees, supply that will not be ours, adverse selection, settlement-rule gotchas, capital lockup, correlation, measurement bugs, cached/stale data, eligibility for a US retail account, rate limits, latency. Re-derive at least one decisive number with your own query. If you cannot refute it, say so and give your own verdict and $/day; unverifiable means plausible-needs-data, not a guess.\n\nIDEA: ${JSON.stringify(idea)}\n\nCHECKER: ${JSON.stringify(chk)}`
async function checkOne(idea) {
  const chk = await agent(checkPrompt(idea), { label: 'check:' + idea.id, phase: 'Check', schema: CHECK_SCHEMA })
  if (!chk) return { idea, chk: null, ref: null }
  if (chk.verdict === 'dead') return { idea, chk, ref: null }
  const ref = await agent(refutePrompt(idea, chk), { label: 'refute:' + idea.id, phase: 'Refute', schema: REFUTE_SCHEMA })
  return { idea, chk, ref }
}

phase('Check')
const results = (await pool(toCheck, LIMIT, checkOne)).filter(Boolean)

phase('Critic')
const CRITIC_SCHEMA = {
  type: 'object',
  properties: {
    wrongful_kills: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, why_the_kill_is_wrong: { type: 'string' }, what_to_measure: { type: 'string' } }, required: ['id', 'why_the_kill_is_wrong', 'what_to_measure'] } },
    weak_survivors: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, problem: { type: 'string' } }, required: ['id', 'problem'] } },
    missed_families: { type: 'array', items: { type: 'object', properties: { market: { type: 'string' }, why: { type: 'string' } }, required: ['market', 'why'] } },
    new_ideas: { type: 'array', items: IDEA },
  },
  required: ['wrongful_kills', 'weak_survivors', 'missed_families', 'new_ideas'],
}
const compact = results.map(r => ({ id: r.idea.id, name: r.idea.name, family: r.idea.family, mechanism: r.idea.mechanism, check: r.chk && { verdict: r.chk.verdict, measured: r.chk.measured, dpd: r.chk.realistic_dollars_per_day, risks: r.chk.killer_risks }, refute: r.ref && { refuted: r.ref.refuted, objection: r.ref.strongest_objection, revised: r.ref.revised_verdict, dpd: r.ref.revised_dollars_per_day } }))
const critic = await agent(
  PRE + `\nYOUR ROLE: completeness critic. Scratch: ${SW}/critic/.\n(1) Which kills are wrong or premature? (2) Which survivors are weak? (3) What families, venues or data sources did nobody examine (compare with ${CAT}/INDEX.txt and the ledger)? (4) Up to 8 NEW ideas, each grounded with a quick measurement.\n\nCHECKED: ${JSON.stringify(compact)}\n\nNOT CHECKED: ${JSON.stringify(unchecked.map(i => ({ id: i.id, name: i.name, prior: i.prior })))}\n\nDROPPED: ${JSON.stringify(dropped)}\n\nABUNDANT: ${JSON.stringify(abundant)}`,
  { label: 'critic', phase: 'Critic', schema: CRITIC_SCHEMA }
)
let round2 = []
if (critic && critic.new_ideas && critic.new_ideas.length) {
  const extra = critic.new_ideas.slice(0, 8).map((i, k) => Object.assign({ id: DATE.replace(/-/g, '') + '-N' + (k + 1), prior: 3, prior_reason: 'critic round' }, i))
  round2 = (await pool(extra, LIMIT, checkOne)).filter(Boolean)
}
const allResults = results.concat(round2)

phase('Write')
const payload = {
  date: DATE,
  counts: { scouts: scouts.length, combiners: combs.length, raw_ideas: allIdeas.length, merged: ideas.length, dropped: dropped.length, checked: results.length, round2: round2.length, unchecked: unchecked.length },
  results: allResults, unchecked, dropped, abundant, critic, scout_measurements: measures,
}
const writer = await agent(
  `You write the final outputs of a money-idea sweep run on ${DATE}. Follow C:\\kals-repo\\CLAUDE.md's reporting rules (plain language, numbers in dollars or times-out-of-100, reason first, failures as failures, ET times). Write THREE things, and nothing else:\n\n1. C:\\kals-repo\\results\\IDEA_SWEEP_${DATE}.md -- top: 3-6 sentences on what (if anything) makes money and how sure we are. Then "Worth testing next" (name | idea in one plain sentence | realistic $/day now | worst case | confidence | next test + pass bar; only ideas that survived check AND refutation or that the refuter itself rated plausible; where checker and refuter disagree show the LOWER $/day and say so), "Promising but needs data", "Wrongly killed? -- re-check list", "Dead, with the reason" (one line each), "Not checked", "Markets that probably hold more ideas", "How this was done" (counts, caps, failures; read-only, no orders).\n2. C:\\kals-repo\\results\\idea_sweep_${DATE}.json -- the DATA below verbatim, pretty-printed.\n3. UPDATE C:\\kals-repo\\results\\IDEA_LEDGER.md in place (read it first; keep its format and every existing row): add one row per NEW idea from this run (id | name | family | status | $/day | one-line reason | evidence file), change the status of existing rows this run decided (and say so in the row: "was X, ${DATE}: Y because Z"), refresh the HOT AREAS and UNRESOLVED sections from this run's survivors, needs-data items, critic re-check list and abundant markets. Never delete a row; a dead idea stays so nobody re-proposes it.\n\nDo NOT run git. DATA: ${JSON.stringify(payload)}`,
  { label: 'write', phase: 'Write' }
)
return {
  counts: payload.counts,
  survivors: allResults.filter(r => r.ref && !r.ref.refuted && r.ref.revised_verdict !== 'dead').map(r => ({ id: r.idea.id, name: r.idea.name, verdict: r.ref.revised_verdict, dpd: r.ref.revised_dollars_per_day, next: r.chk.next_test })),
  refuted: allResults.filter(r => r.ref && r.ref.refuted).map(r => ({ id: r.idea.id, name: r.idea.name, objection: r.ref.strongest_objection })),
  dead: allResults.filter(r => r.chk && r.chk.verdict === 'dead').map(r => ({ id: r.idea.id, name: r.idea.name })),
  wrongful_kills: (critic && critic.wrongful_kills) || [],
  writer: typeof writer === 'string' ? writer.slice(0, 2000) : writer,
}
