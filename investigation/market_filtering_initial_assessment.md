# Earlier exploratory assessment — superseded by the revised market_filtering_assessment.md

Investigation date: 25 September 2026. Scope: market coverage, compression, and live-replicable selection—not research-method feasibility. No notebook was modified. No market filter has been applied to the archive.

## Recommendation

Start with a **category-balanced, liquidity-stratified panel**, retain both outcome assets, and reserve some capacity for randomly selected markets. Keep compact coverage/eligibility summaries across the observed universe. Use a byte budget in addition to a market-count budget.

For a genuinely small local dataset, target **30–60 GB** and accept limited, explicitly sampled recording episodes. If continuity and breadth matter more, **100–300 GB** is a much less restrictive research target and comfortably within the stated cloud-storage budget. These are proposed budgets, not measured outputs of an implemented filter.

The most important empirical finding: **a small number of active markets can generate almost all the rows. Removing many quiet markets is not the same as removing much data.** Keeping only the busiest markets can therefore sacrifice diversity without achieving the desired storage reduction.

## What I inspected—and what these samples cannot establish

- The complete manifest: **6,590 objects, 3,012,570,951,236 bytes** (3.013 decimal TB; 2.740 TiB).
- The primary dated raw-feed objects: **1,718 objects, 2,908,649,863,086 bytes**. The remaining manifest bytes include other data and metadata; they are not all interchangeable order-book input.
- **12 randomly selected hours**, one within each calendar stratum, using seed `20260925`. Selection did not prefer smaller files or more active markets. I downloaded only the first **8 MiB** of each object: **96 MiB total raw downloads**.
- **Four interior windows** from the existing August 16 files, using reproducible compressed-position fractions. No additional whole-hour raw file was downloaded.
- Up to 100,000 outer records per window: **1.6 million raw lines** in total. This includes 58 non-dictionary payloads; 1,599,942 records entered the timestamped analysis. Complete-payload deduplication identified **767,249 repeated payloads**.
- **25 daily indexes**: 24 newly downloaded and the existing August 16 index. Also small, cached official API requests: a uniform 16-market draw within each observed window, plus targeted checks of missing metadata.

The remote samples cover only **3.039–24.257 seconds per hour**, not full hours. The four interior samples cover **45.491–79.116 seconds** each. Prefixes are not uniform samples within an hour; interior compressed offsets are not uniform time draws either. Equal draws across calendar strata are not byte-weighted estimates of the archive. Quiet markets absent from a window cannot be counted from that window.

Consequently, the findings are substantially broader than the original August sample, but **not an archive-wide census or a calibrated forecast of production eligibility**. I have not established every market's continuous history, historical subscription rules, or full-day liquidity distributions.

### Hourly size and availability

An hourly object contains many markets and messages, not one snapshot. The manifest shows a major change in object size:

| Month represented | Primary objects | Total GB | Median object GB | Largest object GB |
|---|---:|---:|---:|---:|
| May 23–31 | 202 | 1,257.33 | 6.348 | 7.560 |
| June | 392 | 889.55 | 0.894 | 8.878 |
| July | 741 | 556.95 | 0.756 | 1.429 |
| August 1–16 | 383 | 204.82 | 0.510 | 0.989 |

There are dated primary files on **73 days** between May 23 and August 16, an 86-day inclusive span. **June 5–17 has no primary dated raw objects in this manifest.** Other partial-day gaps and tiny objects also exist; one July object is only 105 bytes. Do not interpret missing files, tiny files, or missing snapshots as market inactivity. Some hours have suffixed objects, so object count is not a count of complete hours.

## Which markets and categories are actually represented?

### Counts: three different universes

| Universe | Distinct markets | Interpretation |
|---|---:|---|
| Raw-feed markets observed in the 16 windows | **29,694** | Proven present in sampled feed messages; lower bound on archive coverage |
| Markets listed across the 25 inspected indexes | **210,980** | Metadata/catalogue union, not proof of captured book data |
| Entire raw archive | **Unknown** | The file manifest has no complete per-market coverage inventory |

For comparison, the May 28 daily index lists 41,379 markets; August 16 lists 10,656. Neither number is the archive's total. An index entry's listing/end dates do not establish that we recorded the whole interval.

**ID correction:** daily-index dictionary keys are **outcome-token/asset IDs**, not decimal encodings of raw condition IDs. Join raw `asset_id` to an index key. Use the API's `conditionId` to join raw `market_id`; keep the separate numeric Gamma market ID. A decimal-to-hex conversion of index keys does not make a market-condition map. Earlier conclusions based on that conversion—including an apparently absent BNB market—need to be discarded.

Across the raw-window union, **all 29,694 markets had exactly two observed asset IDs**, totaling 59,388 assets. All **256 API market draws** also returned two tokens. This supports retaining the pair as the unit of selection in this dataset; it is not a schema guarantee for every future product. An event can still contain many binary markets. Preserve `event_id` as a grouping dimension so dozens of sports propositions do not masquerade as unrelated research subjects.

### Category evidence

I queried current official metadata for 16 uniformly drawn observed markets per window. All 256 draws matched, querying both open and closed markets. These are **draws**, potentially including the same market in different windows, not 256 independent archive-uniform observations.

| Official-tag display category | May/early June: 48 draws | Later remote prefixes: 144 draws | Aug 16 interiors: 64 draws |
|---|---:|---:|---:|
| Sports / esports | 21 | 61 | 60 |
| Crypto | 4 | 32 | 4 |
| Weather | 4 | 36 | 0 |
| Politics | 14 | 4 | 0 |
| Economics / finance | 2 | 6 | 0 |
| Mentions | 0 | 1 | 0 |
| Other | 3 | 4 | 0 |

This is strong evidence against treating the August sample as representative of the earlier market mix. It is not enough to estimate a precise archive-wide category percentage. Tags are multi-label; the table uses a documented, fixed display priority and retains the original tag set.

Title heuristics applied to the larger index union label 150,878 sports/esports, 25,397 crypto, 7,250 weather, 6,823 politics, 1,382 mentions, 991 economics/finance, and 18,259 unclassified. **These are rough catalogue labels, not verified feed coverage or an official taxonomy.** For example, a generic “up or down” title can describe equities, not just crypto. Use official tags and event/series metadata for the actual classifier.

The same-day index is often incomplete for observed feed markets: zero joins in the June 22, July 30, and four August interior windows, versus 6,483 of 6,924 in the May 25 window. Even joining every cached index leaves 8,379 of the 29,694 observed markets unmapped. A targeted API audit resolved **107 of 108** additional draws; many missing-index markets were weather, crypto, or sports. **An unsuccessful index join is not a liquidity or data-quality filter.**

The API's `/tags/slug/mentions` returned 404; the mentions market actually carried **`mention-markets`**. Preserve the tag graph, not a guessed handful of slugs. Official discovery documentation describes tags and sports/series discovery; market queries expose condition/token identifiers and metadata. [Official discovery guide](https://docs.polymarket.com/market-data/discover-markets), [market API](https://docs.polymarket.com/api-reference/markets/list-markets).

### Horizon and age

Two different clocks matter: **listing-to-end lifetime** and **the event's measurement interval**. Neither equals recorded-history length.

| API panel | Median listing-to-end interval, valid dates only | Median age since creation when sampled |
|---|---:|---:|
| May / early June | 34.1 days (39 observations) | 13.7 days (46 observations) |
| Later prefixes | 2.29 days (138 observations) | 7.0 hours (136 observations) |
| Aug 16 interiors | 6.97 days (63 observations) | 3.36 hours (55 observations) |

The early panel includes markets created up to 227.5 days before observation. In the later remote panel, the maximum observed age among valid creation dates was under two days. Together with index turnover and object-size changes, this suggests a change in the captured universe or collection regime. It does **not** prove the collector's rule: short sampled windows and missing fields remain confounders. A later filter cannot undo pre-existing archive selection.

Real examples include five-minute SOL/XRP/BTC contracts, 15-minute BTC/ZCash contracts, and one-hour ETH contracts. A verified BNB market has `eventStartTime=2026-08-16 16:00Z`, `endDate=17:00Z`, but was listed the previous day. Do not classify that as a day-long event because `startDate` is a listing timestamp. Long-dated political and token-launch markets also occur in the early observations.

For selection, maintain separate fields for listing age, time to scheduled event start, time to scheduled end, and event duration where genuinely defined. Scheduled dates can change and are not necessarily resolution/closure dates. Historical continuous market coverage remains unmeasured.

## Liquidity: what is measurable now

The probes measure unique source payloads, token-level updates, trades, conditional quoted spread, and near-touch depth when a snapshot is present. A two-token price-change message can produce two rows; that is not two independent market-level activity events.

The distributions are very uneven:

- In the three early windows, the median across markets of each market's observed valid spread was approximately **2.8–3.0 cents**.
- Across later prefixes it ranged from **2.0 to 83 cents**. Across August interiors it was **91–94 cents**. Many newly listed markets have extremely wide books even though they produce some updates.
- **95.6–99.6%** of observed markets had no trade in their short window. This says little about their daily trade rate; do not require a trade in a seconds-long sample.
- Only **11–40 markets per window** had usable two-sided snapshot depth observations. Later-window median near-touch depth was typically tens to low hundreds of shares; the early windows contained some much larger observations. This coverage is insufficient to calibrate a universal depth cutoff.

Spread statistics exclude missing, crossed, endpoint, and nonpositive quotes and are observation-weighted—not time-weighted. Depth is the smaller bid/ask-side share depth within one cent of the respective best prices, not dollar liquidity. These are exploratory diagnostics, not validated live eligibility features.

For the real pipeline, compute trailing **time-weighted valid-book fraction, spread, near-touch share depth, standardized execution cost, unique market-message rate, and trade rate**, with separate dimensions for outcome price and event phase. Use rolling history available at the decision time. Do not rank markets by their full-history activity or current API `volume`/`liquidity`.

Ticks are not universally identical: sampled data contained **40 raw `tick_size_change` messages**, including duplicates, and prices at 0.001 precision. Retain tick-regime changes and compare spread in both price units and ticks. The official stream documents these lifecycle messages. [Realtime feed documentation](https://docs.polymarket.com/market-data/realtime-data).

### Measured short-window cut comparisons

For a temporally ordered sensitivity check, I set a fixed decision **one second after the first receive time in remote prefixes**, or **20 seconds in the local interior windows**. Threshold inputs use observations up to that cutoff; retained rows are measured strictly afterwards. Candidates are only markets already observed by the cutoff. The cutoff is not inferred from the window's future end or its eventual activity.

Each cell below is **median percentage of window markets selected / median percentage of subsequent fact rows retained**. The two medians are calculated independently across windows; they need not describe a single window. Rows combine token changes, trades, and snapshot levels—not encoded bytes. These very short horizons are concentration diagnostics, **not proposed production lookbacks or estimates of daily eligibility**.

| Information available at decision | Early windows, n=3 | Later prefixes, n=9 | Aug interiors, n=4 |
|---|---:|---:|---:|
| At least 2 token updates | 46.2% / 59.5% | 31.3% / 94.8% | 45.5% / 96.4% |
| At least 10 token updates | 8.4% / 34.7% | 12.1% / 93.1% | 9.2% / 95.3% |
| At least 50 token updates | 0.8% / 14.9% | 3.8% / 69.2% | 2.0% / 93.5% |
| At least 10 updates and observed median valid spread <=5 cents | 5.1% / 18.1% | 4.6% / 57.4% | 2.8% / 91.4% |
| Top 10% of already-observed markets by prior updates | 4.6% / 26.8% | 3.2% / 61.7% | 4.6% / 94.6% |
| Stable random 10% of already-observed markets | 4.4% / 5.5% | 3.8% / 4.2% | 5.4% / 5.2% |

The selected fractions can be below 10% because the denominator includes markets that first appear after the decision. The random allocation has large byte/row risk: across the four August interior windows its subsequent row share ranged from **1.0% to 58.2%**. The 50-update rule retained a median **93.5% of later rows while selecting only 2.0% of market names** there. This is why neither “keep the liquid ones” nor “sample 10% of names” is a storage guarantee.

These comparisons use the same observations explored during this investigation, not an untouched validation set. They motivate the proposals below; production thresholds still require longer forward, time-separated evaluation. Selection of rare categories and time-weighted depth cannot be calibrated from this test.

## Storage: corrected compact benchmark

The benchmark splits price changes, trades, snapshot headers, snapshot levels, asset dimensions, and market dimensions. It uses:

- Small integer surrogate keys in fact tables; reversible original token and condition IDs stored once in dimensions, as 32-byte binary values.
- Exact decimal price/size columns with observed scale, not `float32` or a hard-coded one-cent grid.
- Integer millisecond event and receive timestamps, plus source sequence for ordering/audit.
- Compact sides and binary hashes; snapshot hashes once per snapshot rather than repeated at every level.
- No per-change hash in retained rows. Both snapshot and transaction hashes remain.

Dimension tables are **included** in the measured sizes. Source shards must have stable namespaces or globally stable keys; never concatenate independent local integer maps as if they were global IDs. Likewise, snapshot sequence needs a source-file/partition identifier.

| Sample group | Parquet Zstd 3 / recompressed raw JSON | Parquet Zstd 9 / recompressed raw JSON | Additional saving from level 9 |
|---|---:|---:|---:|
| Early broad windows | 26.34% | 25.69% | 2.46% |
| Later prefixes | 22.14% | 20.97% | 5.29% |
| Aug 16 interiors | 24.44% | 22.89% | 6.33% |

**Denominator caveat:** raw means the same complete sampled outer messages reserialized and recompressed with Zstd 3. It is **not the original object's physical compressed byte count**. Original codec settings, larger partitions, ordering, and amortized dimensions can change the result. These exact-valued tables also omit unselected raw fields and rare lifecycle/metadata messages; they are not a lossless copy of the complete source archive. The production design must add the small metadata/lifecycle side tables.

Level 9 saved only a few additional percent while taking roughly 1.5–1.7 times the writer CPU time in these small benchmarks. Start with **Parquet Zstd 3**, shared dimensions, reasonable row groups, and incremental disk-backed output. Avoid thousands of tiny per-market files; use date/hour plus coarse hash buckets with market/time statistics. Keep snapshot headers separate, including empty snapshots. A compact on-disk dataset still needs bounded queries; loading it all into pandas is not safe.

An intentionally broad **planning scenario**, applying a 20–30% compact ratio to 2,908.65 GB of primary input, gives **582–873 GB** before market selection. This is not a measured archive forecast.

| Fraction of compact fact bytes retained | Illustrative fact-data size, before summaries/metadata/headroom |
|---|---:|
| 5% | 29–44 GB |
| 10% | 58–87 GB |
| 20% | 116–175 GB |
| 30% | 175–262 GB |
| 100% | 582–873 GB |

Market fractions and row fractions are **not** byte fractions. Use a pilot to measure actual written bytes before enforcing one of these budgets.

Cloudflare R2 Standard currently lists $0.015/GB-month, with 10 GB-month free: approximately **$1.35/month for 100 GB, $4.35 for 300 GB, or $7.35 for 500 GB** of storage. Requests, compute, backups, taxes, and any other service costs are separate. These figures are a storage-budget comparison, not a recommendation to deploy anything now. [Official pricing](https://developers.cloudflare.com/r2/pricing/).

## Live-replicable selection proposals

All numerical thresholds below are **candidate settings for a forward pilot**, not empirically optimized cutoffs. Log the configuration and freeze it before evaluating trading results. Keep rejected-market summaries so threshold decisions can be reviewed without pretending rejected full-depth data was retained.

### A. Broad quality floor: maximum flexibility

Keep all categories, admitting markets after a short observed warm-up if they have a valid two-sided book and minimal trailing activity. Explore a grid of 1/5/15-minute windows, 50/80/95% valid-book coverage, and 1/10/60 unique market messages per minute. Initially use depth and spread as strata, not hard exclusions. Exit only after persistent failure across several decision intervals; permit re-entry with a new snapshot.

This is the least restrictive proposal, but likely the weakest storage reducer: removing quiet names often leaves almost all active data. Suitable if hundreds of GB are acceptable or as the monitoring universe underlying another proposal. Do not promise that it reaches 30–60 GB.

### B. Stratified research panel: recommended starting point

Use **sports/esports, crypto, mentions, and weather** as deliberate research groups, with politics, economics, other, and unknown in a reserve. Weather deserves inclusion based on the later API samples; mentions deserves deliberate representation because a purely random draw rarely includes it. Retain an early-period political cohort if sufficient contiguous history is available.

Within each group, split eligible markets into low/medium/high trailing-liquidity bands. A concrete initial design is **four market slots per band per main category: 48 concurrent slots, plus 12 exploration/reserve slots**. These slot counts are experimental design targets, not storage estimates. Sparse strata may remain partly empty; never fill them with future knowledge.

Rank liquidity using trailing valid-book fraction, spread/depth, and unique-message activity; calculate band boundaries from the universe observed at that time. Choose within bands by a deterministic seeded hash, not eventual volume or profitability. Constrain concentration by event/series so a single match's many propositions cannot fill a whole group. Keep both assets.

Preserve a selected market's assigned cohort for a predeclared recording episode rather than re-ranking every minute. For recurring five-/15-minute contracts, select the family using known metadata and apply the same admission rule to newly arriving contracts; record each contract ID separately. An initial **30-second warm-up / 60-second trailing window** is a reasonable separate grid for very short contracts; a universal 15-minute minimum would exclude them. New listings and missing metadata stay eligible for the exploration allocation.

Use a **30–60 GB local budget** to set how many episodes can be admitted, measured against actual encoded bytes. If 60 concurrent slots are too expensive, shorten or reduce *future* sampled episodes or reduce slots by a predeclared schedule—not by hindsight about which completed episodes looked useful. This proposal best balances comparison and flexibility, but costs still need calibration.

### C. Broad panel plus active core: continuity-first

Keep B's stratified panel, add a liquidity-selected core within each category, and reserve **10–20% of the byte budget** for randomized exploration. Aim initially at **100–300 GB**. The core provides longer continuous, active series; the stratified portion prevents the project becoming exclusively the busiest crypto contracts.

The budget percentages describe storage allocations, not sampling probabilities. Log actual inclusion probabilities separately. A high-activity core can dominate bytes, so monitor its projected cost using past encoded bytes/second and stop admitting new core episodes before consuming the exploration reserve. Capacity decisions themselves must be timestamped and reproducible.

This is preferable to an unconditional “top 100 markets” filter: market count alone neither controls cost nor guarantees category balance.

### D. Randomized complete recording episodes: strongest size control

Select market-day blocks for long-lived markets, or entire scheduled contract intervals for short-lived ones, using an ex-ante stable random rule stratified by category and trailing liquidity. Include warm-up/base snapshots and every subsequent delta in the selected interval. Do **not** randomly retain individual price-change rows: that prevents faithful book reconstruction.

Target roughly a 5–10% *byte-retention scenario*, adjusted only through prospective pilot measurements. This offers broad cross-sectional diversity at 30–90-ish GB, but fewer continuous longitudinal histories. It is a good companion to a small continuous core when local space is the binding constraint. A fixed random percentage of market names is not a hard byte cap; the observed concentration makes realized costs highly variable.

## Causality, metadata, and coverage rules

1. **Decision clock:** evaluate at predeclared receive-time boundaries using only records received strictly before the decision. Store receive time/sequence in a compact acquisition ledger even if hidden from notebook tables. Exchange timestamps can arrive out of order; sorting the entire day by them does not reproduce what a live process knew.
2. **Metadata availability:** prefer timestamped embedded metadata, then archived index versions available at the decision, then prospectively fetched API versions. Store `available_at`, source timestamp, and version. A daily index generated at 00:02 is not available for a 00:00 decision. Later indexes and today's tags in this report are retrospective descriptions only.
3. **Useful discovery:** July 30's sample contains `token_index`, `market_metadata`, and `event_metadata` at approximately **21:00:00.703–.709Z**. The market object includes condition/token IDs, event times, tick size, and contemporaneous market fields. Preserve these sparse messages separately. The current table builder's feed-only check will reject them; silently converting their nested `market` object to a feed ID would also be wrong.
4. **No survivor-only discovery:** API lookups here explicitly queried both `closed=false` and `closed=true`. Do not build the historical universe from today's open markets, resolved winners, current volume ranks, or the set of contracts surviving to the end of the archive. Unmatched IDs remain unknown, not rejected.
5. **Episode integrity:** admission requires a usable base snapshot. If it is unavailable, mark “selected, awaiting snapshot”; do not fill it from a future snapshot or today's live API. Retain complete messages/snapshots at storage boundaries, both outcome books, and lifecycle/tick events. After a gap or re-entry, establish a fresh base and mark the discontinuity.
6. **Hysteresis:** use separate entry and exit conditions, minimum planned episode lengths, and consecutive failures to avoid rapid churn. A budget stop is an explicit censored episode with a reason—not a silently complete market history.
7. **Audit:** retain each decision's observed features, thresholds, candidate universe, category version, seed/hash, inclusion probability, reason, and effective start/end. Selection is intentionally nonuniform; live replicability eliminates look-ahead, not the need to account for selection in conclusions.
8. **Time coverage:** absence of messages is not evidence of zero activity unless feed coverage is known. Record available source hours, gaps, snapshot bootstrap status, and collector interruptions separately. Do not infer eligibility across June's missing interval.

The existing `raw_tables.py` remains a bounded notebook helper, not a production archive converter. Beyond the implemented hash change, production work will need metadata/lifecycle routing, exact archival types, receive-order audit, incremental state/deduplication across chunks, and event-atomic byte limits. This investigation does not claim those pieces are already implemented.

### Lightweight summaries also need a budget

For illustration, 5,000 active markets × 73 days × 1,440 one-minute intervals = **525.6 million rows**. At an assumed 32 compressed bytes/row that is **16.8 GB**; at five-minute intervals it is **3.36 GB**. Neither bytes/row nor a constant 5,000-market universe was measured here. Store sparse active/observed intervals and compact coverage spans, not dense zero rows for every catalogue market. Monitor a richer state in memory if necessary, while persisting coarser summaries. Summary granularity determines which later filter alternatives can actually be evaluated.

## Implementation, resource use, and reproduction

**Implemented now:** `raw_tables.py` drops `change_hash` from output while preserving full-payload deduplication, `book_hash`, and `transaction_hash`. Hash removal does not merge two different source payloads merely because their remaining displayed columns match. No existing local raw data was deleted and no notebook was edited.

The investigation cache is approximately **516 MB decimal / 492 MiB**, well below the authorized 5 GB. All newly downloaded content is in **`data/market_filter_investigation/`**, which can be removed as a unit when no longer needed; the scripts and compact results are outside it. Removing it loses cached API responses and may make replication dependent on renewed signed URLs. The shared URLs are due to expire September 28 at 05:17 UTC according to the supplied access notes.

Each raw prefix download is bounded at 8 MiB, each API response at 2 MiB, and scans at 100,000 records with a time limit. Drivers use two workers and a 58-second watchdog per child query/analysis. The cache has a cross-process storage reservation guard; interrupted reservations fail conservatively rather than silently exceeding the budget. Run the supplied drivers rather than launching multiple transfers of the same object yourself.

Observed initial individual download calls took **1.2–20.6 seconds**; official API calls **0.077–0.430 seconds**. In the final run, scanning, normalization, and compact benchmarking took **9.4–28.9 seconds per window**, including exact Parquet round-trip checks; the largest complete child command took 30.6 seconds. These are local exploratory Python timings, including deduplication and decimal conversion—not optimized production throughput or a trustworthy whole-archive ETA. Parquet writing itself was only a small portion; stronger compression alone does not address parsing cost.

Validation: **8 tests passed in 4.19 seconds**, using real raw data or saved real-source observations. All 16 compact probes verified exact Arrow-to-Parquet-to-Arrow equality at both compression levels. Evidence checks also confirm token ownership across windows, API token joins, bounded record counts, and the fixed decision offsets. These checks do not establish full-archive book continuity or eliminate the need for production replay validation.

**Filtering locally will reduce retained storage, not necessarily source bandwidth.** These objects combine markets inside sequential compressed streams. Without a server-side per-market index or seekable frames, processing the complete historical archive still requires reading/decompressing the relevant source objects. A bounded rolling download/process/delete pipeline avoids multi-TB temporary disk use; it does not make the transfer instantaneous. Random arbitrary compressed ranges cannot be assumed independently decodable. For future collection, a known-at-the-time subscription filter can reduce incoming data too.

Evidence and reproducible entry points, run from the project root:

```powershell
# Offline: rebuild statistics from saved observations and cached indexes.
python investigation/summarize.py

# Existing real-data tests; no synthetic fixtures.
python -m pytest -q tests

# Re-run a single bounded compression/selection probe using its saved plan.
python investigation/analyze.py 12
```

To reproduce sampling, `probe.py plan` deterministically creates the 12 remote choices and four existing-local-file supplements. `run_samples.py` runs remote probes; `run_enrichment.py 12 13 14 15` runs the local supplements. `run_enrichment.py 0 1 ... 11` performs optional next-day descriptive joins. `run_category_panel.py` performs the cached official-tag panel; `api_audit.py` performs the targeted missing-index audit. `inspect_embedded_metadata.py` verifies the embedded-metadata example. Do not pass a literal `...` to a command; it denotes the intervening sample numbers here.

`investigation/results/plan.json` records exact source objects and offsets; `sample_*.json` and `markets_*.json` contain per-window measurements; `category_panel_*.json` stores the official-metadata panel; `summary.json` rebuilds the tables. Signed download URLs are not copied into the report or result logs.

### Remaining uncertainty and next bounded experiment

The unanswered quantities are exact full-archive market count, continuous per-market history, time-weighted historical liquidity, production eligibility rates, and final bytes for each proposal. These cannot be honestly recovered from the manifest plus a few seconds per selected hour.

After choosing a proposal, the useful next step is a **small streaming pilot with longer contiguous intervals**, explicit runtime/byte limits, and time-separated calibration/evaluation periods spanning the early and late collection regimes. Measure actual written bytes, admission/exit behavior, snapshot availability, category balance, and runtime. Fix the candidate filter before assessing trading outcomes. This would calibrate the storage budget without committing to processing the entire archive.
