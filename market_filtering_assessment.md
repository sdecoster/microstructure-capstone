# Research portfolios: what to keep, what it costs, and the recording change

Updated 25 September 2026. This replaces the earlier broad category assessment.

## Recommendation

**Use BTC, ETH, SOL, and XRP rolling Up/Down contracts as the primary research universe. Start with 15-minute and hourly contracts: eight recurring series, approximately 59 GB for the available archive.** Adding four-hour contracts gets you twelve series for about **62 GB**. Reserve roughly **90–95 GB** including uncertainty and working headroom.

If the richer five-minute activity is worth storing, keep all four horizons: **16 recurring series, approximately 163 GB**, with a prudent 250 GB allocation. That is affordable within the cloud budget. These are four underlying assets at multiple horizons, however—not sixteen independent equities.

**Do not assume the full archive is one consistent collection regime.** Use June 18–August 16 as the primary development period, with explicit gap masks. Treat the earlier data separately until its rollover coverage is audited. The smaller files are not safely explained as a harmless compression improvement.

## Concrete portfolio choices

All crypto rows below use **BTC, ETH, SOL, XRP**, both outcome assets, full recorded depth changes, snapshots, and trades. A series continues into each successive contract; it is not one long-lived condition ID. Sizes are measured-sample extrapolations, not completed archive conversions. GB means decimal GB.

| Portfolio | Recurring series / slots | All available dates, estimated | June 18–Aug 16 only, estimated | Research trade-off |
|---|---:|---:|---:|---|
| Four coins × 15 minutes | 4 | **44 GB** | **37 GB** | Clean, active baseline; limited cross-asset breadth |
| Add the four hourly series | 8 | **59 GB** | **51 GB** | **Best starting point:** more horizon variation for about 15 GB extra |
| Add the four four-hour series | 12 | **62 GB** | **53 GB** | Cheap lower-activity comparison group; not all twelve are equally liquid |
| Add the four five-minute series too | 16 | **163 GB** | **138 GB** | Most active/richest option; five-minute data adds about **101 GB** |
| Up to 5 ranked sports match-winner books* | Up to 5 | **12 GB*** | **7 GB*** | Small exploratory comparison, not a continuous core |
| Up to 15 ranked sports match-winner books* | Up to 15 | **22 GB*** | **9 GB*** | Cheap, but the samples do **not** support fifteen consistently liquid books |
| Twelve slower crypto series + up to 5 sports books* | 12 + up to 5 | **74 GB*** | **60 GB*** | Practical cross-domain extension; sports remain a separately evaluated cohort |

The mixed estimate adds separately stored crypto and sports components. Suggested working allocations are 65 GB for the four-series baseline, 90–95 GB for eight/twelve crypto series, 110 GB for the mixed extension, or 250 GB for all sixteen crypto series. These reserves are planning choices, **not statistical confidence limits or guaranteed caps**.

\* Sports estimates are conditional on the short-window eligibility/ranking proxy described below. They **must not be interpreted as the cost of fifteen always-available, high-volume sports markets**. The pool frequently underfilled. A longer-lookback selection rule could admit more books and cost more.

For context, R2 Standard storage is $0.015/GB-month with a 10 GB allowance: about **$1.35/month for 100 GB** or **$3.60/month for 250 GB**, before operations, compute, backups, and taxes. Storage is not the main obstacle at these sizes. [Official pricing](https://developers.cloudflare.com/r2/pricing/).

## Why the hourly files shrink

### The large change is a break, not a steady decline

| Evidence | Before the gap | After the gap |
|---|---:|---:|
| Median ordinary hourly object | June 4: **8.36 GB** | June 18: **0.84 GB** |
| Daily index market count | June 4: **36,190** | June 18: **5,885** |
| Median indexed listing age | **13.3 days** | **0.33 days** |
| Indexed markets listed over two days earlier | **25,772** | **4** |

Of **8,158** June 4 index markets marked not closed and scheduled to end after August 16, **none** appears in the June 18 index. That is not explained by those contracts simply reaching their scheduled expiry. This proves a substantial catalogue/discovery change; the sampled raw feed also shifts toward recently listed contracts. It does not, by itself, prove every absent catalogue market was absent from every subsequent raw hour.

A format-only explanation fails the checks I could make:

- The sampled price-change schema is unchanged.
- Typical feed-message size does not collapse: median window averages are approximately **761 bytes before versus 785 bytes after**.
- Duplicate-payload rates remain close to **50%** in both regimes; the size reduction is not explained by suddenly removing duplicate messages.
- The inspected Zstd frames all use a **2 MiB window**, no dictionary ID, and no checksum. The compression level itself is not recoverable from those headers.

**Conclusion:** the evidence points to a change in market discovery/subscription coverage, not just more efficient storage. The exact collector rule—configuration change, pagination/discovery behavior, or a bug—cannot be recovered from this share. Collector code and runtime state are absent. I cannot truthfully name the exact software change.

The subsequent decrease from roughly 0.8–1.0 GB/hour to 0.4–0.6 GB/hour is less fully explained. The inspected daily catalogue actually grows again, so catalogue count alone is insufficient. Recorded activity/mix changes too, but without collector health logs or an independent historical feed I cannot distinguish all natural activity changes from missed subscriptions or dropped messages. **Do not interpret smaller files as proof of complete but quieter markets.**

### There is also a real rollover-coverage issue

I queried the exact current-interval contract IDs, then checked their raw messages—not just titles resembling a recurring family.

- **May 25, 08:00 UTC:** the new BTC five-minute contract first appears at **08:00:32.957**; new SOL and ETH contracts appear later, around 41–43 seconds. Earlier messages can belong to the just-expired contracts.
- **May 28, 16:00 UTC:** none of the eight new five-/15-minute contracts appears in the checked first **34.7 seconds**.
- **June 2, 15:00 UTC:** likewise none appears in the checked first **35.2 seconds**.
- **June 22, 22:00 UTC:** all eight current contracts appear within approximately **12 ms** of the hour boundary.

The later arrival alone does not identify whether subscription discovery was slow or another upstream mechanism delayed capture. It does establish different opening coverage. A later-window check finds ongoing early-period crypto activity, so this is **not evidence that the early archive contains no crypto**. I replaced the misleading early boundary windows with later windows for storage estimation.

**Research implication:** extra compression cannot repair missing opening data. Start each contract's usable episode only once an actual base snapshot is available; measure and retain its missing-opening interval. Do not backfill from a later snapshot. The approximate 59/62/163 GB figures describe recorded data, not a reconstructed complete history of missing messages.

## Which recurring themes to study

### What can actually span the recording break

No fixed set of individual contracts spans the break. The June 4 and June 18 daily catalogues have **zero condition-ID overlap and zero token-ID overlap**; the sampled raw data likewise has zero exact market IDs observed on both sides. For rolling crypto this is also structurally expected: each five-minute, 15-minute, hourly, or four-hour interval creates a new contract.

The stable unit is therefore the **recurring family**, not the condition ID. The recommended BTC/ETH/SOL/XRP 15-minute and hourly families occur on both sides of the break and in all 30 inspected daily indexes. All eight also have recorded book updates in the pre- and post-break samples. The four-hour families occur on both sides too, but are less consistently traded; sports do not provide an equally stable fixed panel.

For the longest defensible panel, retain all available dates for those eight families but apply the same causal rule to every contract: admit only its declared family; wait for an actual base snapshot; begin the usable episode no earlier than **60 seconds after scheduled start**; reject an episode if a valid base state is still unavailable; reset across source gaps; and never backfill the missing opening. The 60-second proposal exceeds the roughly 43-second worst opening delay observed in the targeted checks and should be confirmed in the conversion pilot. This neutralizes the known rollover difference without using eventual liquidity or outcomes. It does not prove that the two collector regimes are otherwise identical, so results should still include a post-June-18 robustness run and a recording-regime indicator or break test.

The all-date cost figures below and above already refer to this same recurring-family universe. Missing source periods contribute no bytes and no observations; they are not treated as quiet trading.

### Primary: the four-coin rolling family

The BTC/ETH/SOL/XRP 15-minute and hourly families are present in **all 30 inspected daily indexes**. Their feed activity is repeatedly observed across the calendar. This is much stronger continuity evidence than a single popular event, although not proof of every contract or minute being complete.

Keep fixed family definitions and record every successive captured contract. Do not retrospectively choose the individual contracts that eventually traded most. Preserve contract boundaries and time-to-expiry; do not concatenate prices as if the next contract were the same instrument.

For a local-first study, use eight series, with the four-hour group as an inexpensive secondary comparison. For maximum active-book richness, the sixteen-series option is better supported than trying to force fifteen sports books into every interval. BTC's five-minute family is the largest individual activity source in many sampled windows; the extra storage buys actual event density.

### Secondary: specific sports pools, not “sports” as one category

Start with **ATP match winners, MLB game winners, and Counter-Strike match winners**. Add WTA, Dota 2, or League of Legends only as separately reported groups if their observed coverage supports it. Do not mix moneylines, spreads, totals, map winners, and championship futures into one supposedly homogeneous series.

In the original twenty expanded windows—including four US-evening supplements—ATP, MLB, and Counter-Strike each had updates in **18/20** windows, but trades in only **9/20, 5/20, and 10/20**, respectively. WNBA updates appeared in only **4/20**. These are short-window observations, not daily trade-rate estimates; they do not justify WNBA or generic sports as a uniformly covered primary cohort.

The priced sports proxy is fully specified: among recognized match-winner candidates in MLB, WNBA, ATP, WTA, Counter-Strike, League of Legends, and Dota 2, require at least two token updates and a median observed valid spread no wider than five cents during the preceding **10 seconds**; rank by recorded traded notional, then update count, then condition ID; retain the next observed interval for the top N. Both assets are included. No future volume or current API liquidity is used in ranking.

That short lookback is a **cost probe, not my recommended production liquidity rule**. For research, evaluate every five minutes using the preceding **15 minutes**, require a valid two-sided book for at least 80% of observed time and median spread <=5 cents, then rank by traded notional with near-touch depth as a tie-breaker. Keep admitted books for a declared episode, require repeated failures before exit, and allow empty slots. Freeze this rule before testing signals. Its exact storage cost is not yet measured.

Why not recommend sports-only now? In the sixteen post-gap windows, the priced top-15 rule filled all fifteen slots in only **6**, and filled **0–8** in the four August interior windows. Low estimated storage partly reflects limited eligible coverage, not an inexpensive equivalent of fifteen continuously traded equities. The 15-minute rule needs a continuity/occupancy pilot before that claim can be made.

## Train/test design

Use a **calendar split shared across all families**, never random ticks or overlapping contracts. A concrete initial schedule is June 18–July 27 for training, July 28–August 4 for validation, and August 5–16 for testing. Purge contracts crossing split boundaries and embargo the maximum feature lookback plus prediction horizon. All correlated horizons for a coin belong to the same time split.

There are no primary dated raw files on **June 5–17**, plus shorter later interruptions, notably around July 16–17. Reset state and mask these intervals; do not fill them with zero activity. The proposed post-gap period spans 60 calendar days, **not 60 proven gap-free days**. Use the earlier May/June block for a separately reported robustness exercise only after its coverage passes checks.

Family selection is a research-design choice, not proof of an untouched, preregistered holdout: this investigation inspected coverage across dates. Per-contract admission must use information available then. Never require eventual survival or full-period activity for a contract to enter the historical universe. The fixed crypto families existed at the start; do not remove failed or illiquid episodes later because of their outcomes.

**My choice:** begin with the eight crypto series and a 90 GB working allocation; add four-hour data because its incremental cost is small. Keep sports as a limited comparison cohort. If five-minute signals become central, expand deliberately to the 250 GB allocation rather than cutting arbitrary market names.

---

## Appendix: evidence, costing, and limits

### Sampling and resources

The final compact benchmarks cover **23 windows and 8.18 million outer records**: twelve calendar-stratified hours, four existing August interior windows, four targeted 23:00 UTC sports-evening hours, and three later portions of early-period files to avoid the discovered rollover artifact. The windows total about **22.5 minutes**, spanning 19–156 seconds each. They cover different dates/collection regimes, but remain short and are not an exhaustive or formally archive-uniform census. In particular, most remote windows remain close to an hour boundary. The evening/interior checks improve coverage without eliminating that limitation.

I inspected 30 daily indexes and made bounded official API lookups for structural identities, including both open and closed markets. Present-day liquidity, eventual volume, and outcomes are not filter inputs. API identity/label lookup is retrospective; actual replay needs timestamped metadata versions or a documented structural mapping available at the time. [Official market API](https://docs.polymarket.com/api-reference/markets/list-markets).

The cleanable download cache is approximately **2.11 GB**, including the previous investigation, below the 5 GB authorization. It is entirely in `data/market_filter_investigation/`. No whole multi-GB hour was downloaded. New remote raw reads were 64 MiB prefixes; only three were extended to 128 MiB, reusing cached bytes. All final portfolio probes completed in about **17–35 seconds**. Three initial diagnostics hit the 58-second watchdog; repeated set construction was fixed and the scans tightened before successful reruns. No synthetic market data was used, and no notebook was edited.

### How costs were calculated

Each selected portfolio was actually encoded in memory as Parquet Zstd 3: separate changes, trades, snapshot headers and levels, plus reversible ID dimensions. Prices/sizes are exact scaled integers with six decimal places; the code rejects excess nonzero precision. Source receive/event times and sequence are retained; hashes follow the agreed policy. Every encoded table was checked by an exact Parquet round trip. This is a compact numeric/event archive, not preservation of every raw JSON field.

Accordingly, the **44/59/62/163 GB estimates are for the proposed compact representation, not for raw JSON**. Repeated change hashes are discarded; the snapshot book hash is stored once in its snapshot header and transaction hashes remain with trades. Long hexadecimal condition/token IDs are stored once as fixed 32-byte binary dimension values and fact tables use local integer keys. Redundant envelope fields and strings are omitted. The estimates include both outcome assets and all selected recorded changes, trades, snapshot headers, and book levels, but exclude operational headroom, temporary conversion space, replicas/backups, and the small production metadata/coverage tables.

For each of twelve calendar strata:

`estimated selected bytes = manifest raw bytes in stratum × selected sample Parquet bytes / compressed source bytes consumed during that sample's measured interval`.

Early-period costing uses the later windows, not the expired-contract bursts. The compressed-byte denominator is approximate because the streaming decoder reads ahead; intervals consume roughly 10–24 MB, so this is a small but nonzero source of error. Tiny sample partitions also repeat metadata/footers that a larger archive can amortize. Sparse lifecycle/catalogue tables, summaries, indexes, checkpoints, temporary space, and replicas need additional room.

The main table is a **point extrapolation of recorded bytes**, not a promise of complete capture or a confidence interval. For example, the post-gap eight-series 15-minute/hourly portfolio has sampled full-hour-equivalent costs ranging from approximately **13 to 56 MB/hour**. Short-window sports rankings and missing labels create more uncertainty: identified families cover a median **93%** of sampled token updates, with a minimum near **72%**. Unknown markets are not asserted to be illiquid, and the sports ranking is not an exhaustive API-wide liquidity ranking.

Full conversion still requires reading the relevant mixed-market source objects. Local filtering reduces retained bytes, not necessarily historical download/decompression volume. Use a bounded rolling staging area and incremental output; do not fetch the entire 2.9 TB primary archive onto the notebook machine at once.

### Reproduction and retained evidence

- `investigation/results/portfolio_summary.json`: portfolio estimates, family coverage, and regime comparisons.
- `investigation/results/portfolio_*.json`: exact sample costs, source-byte denominators, selected sports candidates, and verification results.
- `investigation/results/continuity_catalog.json`: daily object-size trends, index ages, and family counts.
- `investigation/results/rollover_check_*.json`: exact current-contract IDs and first observed messages.
- `investigation/results/plan.json`: source objects, offsets, and the three early calibration replacements.

Offline summary: `python investigation/portfolio_summary.py`. Tests: `python -m pytest -q tests` — **11 passed in 6.75 seconds**, using real sources and saved real-source observations. Reproducible scripts include `continuity_catalog.py`, `portfolio_probe.py`, `rollover_check.py`, and bounded download/query drivers. The earlier, longer report is retained as `investigation/market_filtering_initial_assessment.md`; its broad sampling-based recommendations are superseded by this document. No archive filter has been deployed.
