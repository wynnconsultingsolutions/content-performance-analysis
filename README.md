# Content Performance Analysis

What content attributes actually drive audience reach and commercial return
across a 3,200-title catalogue — and which ones only look like they do.

SQL and Python end to end: extract and transform with SQL against SQLite,
analyse and model in pandas and statsmodels, and produce a Tableau dashboard
from the resulting analysis table.

---

## Findings

**1. Return multiple is U-shaped by budget; the middle is the weak position.**

Median return is 2.50x under $5M, falls to 1.51x in the $20-50M band, then climbs back to 2.51x above $100M. Mid-budget titles are the worst position in the catalogue: expensive enough to lose real money, not big enough to command the release that justifies the spend.

The two ends get there differently. Micro-budget titles hit 2.50x on a 65% hit rate — high variance, carried by a minority of breakouts. Tentpoles hit 2.51x on an 87% hit rate, the highest in the catalogue. Same efficiency, opposite risk profiles: one is a portfolio bet, the other is a reliable return on a large commitment.

Budget is still the strongest predictor of scale in both models — a one-log-unit increase is associated with roughly +55% audience volume and +122% worldwide revenue, holding genre, rating, era, and critic score constant. It just doesn't move efficiency monotonically.

**2. Horror is the standout acquisition category.**

At equal budget and critic score, horror titles show +77% audience volume and
+188% worldwide revenue relative to drama — the largest genre effect in either
model, significant at p < 0.001. It reaches that on an average budget of $18.5M
against $54.7M for action and $68.8M for adventure. It also carries the highest
profitability rate in the catalogue at 79.9%.

**3. Critic scores are a poor programming signal.**

Critics and audiences diverge systematically, and the divergence is genre-shaped
rather than random. Thriller/suspense (−16.9 points), horror (−15.6), and romantic
comedy (−15.1) all score far lower with critics than audiences. Documentary (+8.6)
and musical (+3.5) run the other way. Programming to critic score would
systematically under-weight exactly the genres that perform commercially.

**4. Mean return multiple is a misleading KPI.**

Documentary shows a 144x *average* return and a 2.2x *median*. A handful of
micro-budget titles with outsized returns pull the mean up by two orders of
magnitude. Horror shows the same pattern less severely: 69.6x mean, 2.63x median.
Any ranking built on average return in this catalogue is ranking outlier exposure,
not performance. The SQL in `sql/content_kpis.sql` uses median throughout for this
reason. The budget tiers show it too: micro-budget titles average 45.9x and return a median 2.50x. The mean is describing a handful of breakouts, not the tier.

**5. Attributes explain part of the picture, not most of it.**

The commercial model reaches R² = 0.49 on 1,790 titles; the reach model reaches
R² = 0.27. Content attributes are genuinely predictive, but half the variance in
revenue and three quarters of the variance in reach sit outside genre, budget,
rating, era, and critic score — in marketing spend, release competition, talent,
and distribution, none of which this dataset carries. The models are useful for
ranking categories, not for forecasting an individual title.

---

## Charts

| | |
|---|---|
| `output/genre_return.png` | Commercial efficiency by genre |
| `output/budget_tiers.png` | Return multiple and hit rate by budget tier |
| `output/critic_gap.png` | Critic vs audience score divergence |
| `output/diagnostics_reach.png` | Residual and Q-Q plots, reach model |
| `output/diagnostics_revenue.png` | Residual and Q-Q plots, revenue model |

---

## Method

### Data

3,201 theatrical titles with budget, revenue, genre, MPAA rating, creative type,
distributor, critic score, and audience score/volume. Source:
[vega-datasets](https://github.com/vega/vega-datasets) (`data/movies.json`),
originally compiled from public box-office and ratings sources.

### Cleaning (`src/01_clean.py`)

- Dropped three fields below 60% coverage: DVD sales (18%), running time (38%),
  director (58%).
- Dropped 8 rows missing title, release date, or revenue rather than imputing.
- Treated zero and negative production budgets as placeholders, set to null.
- De-duplicated on title + release date.
- Grouped distributors appearing fewer than 25 times into "Other"; collapsed
  "Open" and "NC-17" ratings into "Not Rated".

### Derived KPIs

| KPI | Definition |
|---|---|
| `return_multiple` | worldwide revenue ÷ production budget |
| `profitable` | return multiple ≥ 1 |
| `international_share` | (worldwide − domestic) ÷ worldwide |
| `audience_score` | IMDB rating × 10, to match the 0–100 critic scale |
| `critic_audience_gap` | critic score − audience score |
| `log_*` | natural log of budget, revenue, and audience volume |

### Modeling (`src/03_regression.py`)

Two OLS specifications, both on log outcomes because the raw distributions are
heavily right-skewed:

```
log(audience_volume)   ~ log(budget) + critic_score + genre + rating
                         + creative_type + release_era

log(worldwide_revenue) ~ log(budget) + critic_score + genre + rating
                         + creative_type + release_era
```

Reference levels are drama, R rating, and the 1990s, so every categorical
coefficient reads as a difference from those. Genres with fewer than 25
observations are excluded. Coefficients are reported both raw and as
`exp(coef) − 1`, the approximate percentage effect.

Diagnostics: variance inflation factors on the continuous predictors (both ≈ 1.01,
so no collinearity concern), plus residual-vs-fitted and normal Q-Q plots for each
model. Full statsmodels summaries are written to `output/model_summaries.txt`.

### Known limitations

- **Omitted variables.** No marketing spend, release-week competition, talent, or
  screen count. These plausibly drive much of the unexplained variance, and their
  absence means the budget coefficient is likely absorbing some marketing effect.
- **Audience volume is a proxy for reach**, not a measurement of it. IMDB vote
  counts correlate with reach but also with recency and online audience skew.
- **Survivorship.** The catalogue over-represents titles that got wide release and
  ratings coverage. Genre-level conclusions apply to that population, not to all
  produced content.
- **Cross-sectional, not causal.** These are associations. Nothing here supports a
  claim that changing an attribute would change an outcome.

---

## Running it

```bash
pip install -r requirements.txt

python src/01_clean.py       # builds data/content_performance.csv and content.db
python src/02_explore.py     # summary tables and charts
python src/03_regression.py  # models, diagnostics, output/model_summaries.txt
```

The SQL runs against the SQLite build:

```bash
sqlite3 data/content.db < sql/content_kpis.sql
```

If you do not have the `sqlite3` CLI installed, `python src/run_sql.py` executes
the same file and prints each result set.

## Layout

```
content-performance-analysis/
├── data/
│   ├── movies_raw.json            source data
│   ├── content_performance.csv    cleaned analysis table (Tableau source)
│   └── content.db                 SQLite build
├── sql/
│   └── content_kpis.sql           7 analytical queries
├── src/
│   ├── 01_clean.py
│   ├── 02_explore.py
│   ├── 03_regression.py
│   └── run_sql.py
├── output/                        charts and model summaries
├── TABLEAU.md                     dashboard build guide
└── requirements.txt
```
