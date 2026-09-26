# Longer-horizon market survey

Updated 26 September 2026.

## Bottom line

Longer-lived contracts do exist in meaningful recurring themes, particularly politics/elections, geopolitics, macroeconomics, dated crypto, sports futures, mentions, and weather. The archive does **not yet demonstrate a broad, consistently liquid daily-trading universe** in any of them.

The best research candidates are:

1. **Politics/elections plus geopolitics**, selected each day by trailing spread, depth, and volume.
2. **Macro/economic releases and policy markets** as a smaller companion group.
3. **Major-league season futures** as a separately modelled comparison group, after adding a game calendar so observations during games are excluded.

Dated crypto and weather have more frequent rollover, but their observed trading falls sharply when the event buffer is widened. They look more like event/forecast contracts than a persistent stat-arb universe. Mentions cannot be evaluated safely from the supplied metadata because explicit event-start timestamps are generally absent.

Use a **24-hour event cutoff as the baseline**, 6 and 48 hours as robustness checks, and 1 hour only as an event-adjacent diagnostic. A fixed 48-hour rule is unnecessarily conservative for every category.

## Cutoff sensitivity

The table uses 20 exact, real-feed sample windows and historical metadata. Trade counts and notional are deduplicated and aligned to the same receive-time bounds used for spreads and updates. Contract count is unique across those windows; it is not the number simultaneously tradable.

Games and mentions receive no liquidity credit without an explicit event-start timestamp. For weather, the target day is treated as starting 24 hours before the listed end. Sports futures still require a separate schedule mask because games occur throughout a season.

| Theme | 1 hour: trades / notional | 6 hours | 24 hours | 48 hours | Median sampled spread at 24h | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| Politics/elections | 10 / $1,907 | 10 / $1,907 | 10 / $1,907 | 10 / $1,907 | 2c | Long horizon; cutoff has almost no effect |
| Geopolitics/security | 18 / $15,739 | 12 / $3,421 | 12 / $3,421 | 12 / $3,421 | 2c | Large last-hour event component; stable after 6h |
| Dated/threshold crypto | 15 / $620 | 6 / $166 | 6 / $166 | 4 / $26 | 2c | Much of the trading is close to resolution |
| Macro/economics | 2 / $201 | 2 / $201 | 2 / $201 | 2 / $201 | 4.9c | Suitable horizon, but very sparse observed trading |
| Weather | 5 / $65 | 3 / $25 | 0 / $0 | 0 / $0 | 4c | Observed trading is concentrated close to the target day |
| MLB season futures | 2 / $129 | 2 / $129 | 2 / $129 | 2 / $129 | 1c | Long-lived but sparse; schedule mask still required |
| Soccer futures | 1 / $42 | 1 / $42 | 1 / $42 | 1 / $42 | 3.6c | Long-lived but sparse |
| NBA futures | 0 / $0 | 0 / $0 | 0 / $0 | 0 / $0 | 1.1c | Quotes exist; sampled trades do not |

These are short-window observations, not daily volume estimates. Absolute binary-market spread is also incomplete without midpoint and executable depth: a one-cent spread can be enormous for a one-cent contract. The production liquidity rule must include spread relative to price, depth for a declared order size, and trailing traded notional.

### Activity is concentrated, not broad

The notional totals overstate category breadth:

- Two single politics trades contribute about **$1,817 of the $1,907** total.
- At the one-hour cutoff, one Iran-ceasefire market contributes about **$12,318** of geopolitics notional. It disappears at the six-hour cutoff.
- At six hours and beyond, roughly **$3,133** of geopolitics notional comes from one Strait of Hormuz contract.
- Weather has no sampled trades at least 24 hours before the target period.

Therefore, category membership alone is not a liquidity filter. A strategy would need a daily, causal top-N selection within each theme, and it must be allowed to hold fewer than N markets when the pool is weak.

## What exists by theme

### Politics and geopolitics

These provide the clearest economic match to a daily horizon. Contracts commonly remain open for months, and successive elections, leadership contests, legislation, conflicts, and diplomatic questions create rollover at the theme level. The 24-hour cohort contains 1,927 unique politics contracts and 197 geopolitical contracts across the sampled windows.

The drawback is extreme cross-sectional sparsity. Most contracts show no trade in a short observation window, while a few receive large isolated trades. Use them only with a trailing eligibility rule; do not retain every candidate as equally tradeable.

### Macro/economics

Rate decisions, inflation, employment, growth, commodities, and exchange-rate questions are structurally attractive. Their information horizon is compatible with daily signals and participant groups may recur across releases.

The archive evidence is thin: only two aligned sampled trades at any cutoff. Scheduled releases also need their own calendar mask, analogous to excluding an equity earnings window.

### Sports futures

Championship, award, draft, and season-winner markets last weeks or months and recur by league and season. That is a better daily research object than single-game outcomes.

They are not event-free merely because expiry is far away. A World Series or championship contract reprices during every relevant game. Exclude observations from a declared period before game start through a post-game cooling period, using an external historical schedule. The saved metadata alone cannot do this reliably.

### Dated crypto

Daily/weekly price ranges and longer threshold markets exist, but this remains binary-option-like. The cutoff sensitivity is unfavorable: sampled notional drops from $620 at one hour to $166 at 6/24 hours and $26 at 48 hours. These may be useful as a secondary comparison group, not the main daily-stat-arb universe.

### Weather

Weather markets recur by city and date, which is attractive for participant continuity. In these samples, however, all observed trades occur within 24 hours of the target period and the median spread worsens as the buffer widens. This is more naturally a forecast-specialist strategy unless a larger survey finds meaningful earlier liquidity.

### Mentions

Mentions and posting-count contracts exist and roll over by person, platform, or event. They are potentially attractive as a participant-theme panel. They are **not assigned liquidity statistics here**: the historical records usually lack an explicit event start, and time-to-end does not reveal whether a speech, posting window, or counting interval is already underway. Title/calendar parsing or improved event metadata is required first.

## Recording-universe problem

The longer-lived universe is heavily affected by the June recording change. At the 24-hour cutoff:

| Theme | Pre-change sampled windows / contracts / trades | Post-change sampled windows / contracts / trades |
|---|---:|---:|
| Politics/elections | 4 / 1,836 / 10 | 6 / 91 / 0 |
| Geopolitics/security | 4 / 173 / 12 | 5 / 24 / 0 |
| Dated crypto | 4 / 754 / 6 | 5 / 143 / 0 |
| Macro/economics | 4 / 293 / 2 | 1 / 6 / 0 |
| Weather | 4 / 339 / 0 | 3 / 28 / 0 |
| MLB futures | 4 / 331 / 2 | 1 / 1 / 0 |

The sample durations differ, so those counts are not direct rate comparisons. The collapse in represented contracts is nevertheless too large to ignore. The post-June collector appears to omit most of the long-lived catalogue that makes a daily strategy possible. Selecting the same themes does not repair absent subscriptions.

This means the existing archive may support an early-period exploratory study, but it does not presently support a clean full-period daily panel. Before committing to a strategy universe, verify whether the missing long-lived books can be recovered from another source or begin a new collector that explicitly subscribes to the selected daily universe.

## Proposed production eligibility rule

At each daily decision time, using only information then available:

1. Contract belongs to a predeclared theme and has at least seven days remaining.
2. It is outside the category-specific event mask; use 24 hours as the baseline buffer.
3. A valid two-sided book has been observed for at least 80% of the trailing day.
4. Median relative spread and executable cost for the target order size pass fixed thresholds.
5. Trailing non-event traded notional and near-touch depth pass fixed minima.
6. Rank eligible contracts on trailing information and retain up to N per theme; empty slots are allowed.
7. Require repeated failures before exit to reduce turnover, while event masks force immediate temporary exit.

The exact thresholds should be calibrated from longer non-event windows. The current short samples are sufficient to reject several naive universes, not to set reliable dollar cutoffs.

## Evidence and reproducibility

- 20 real raw-feed windows; no synthetic data.
- 29,784 historically identified market-window observations.
- Four cutoffs: 1, 6, 24, and 48 hours.
- All trade notionals deduplicated and measured within the exact corresponding activity-window bounds.
- Storage-calibration samples 2022 are deliberately excluded because their activity labels were copied from earlier windows and are not independent liquidity observations.

Run:

`python investigation/long_horizon_survey.py catalog`

`python investigation/long_horizon_survey.py notional --sample N`

`python investigation/long_horizon_survey.py summary`

Machine-readable results are in `investigation/results/long_horizon_catalog.json`, `long_horizon_notional_*.json`, and `long_horizon_summary.json`.
