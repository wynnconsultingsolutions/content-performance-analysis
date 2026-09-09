-- content_kpis.sql
-- Analytical queries against data/content.db (table: content).
--
-- Run all:      sqlite3 data/content.db < sql/content_kpis.sql
-- Run one:      open the file, copy the query you want.
--
-- These are the aggregations behind the Tableau dashboard and the summary
-- tables in the README.

.headers on
.mode column


-- ============================================================
-- 1. Genre scorecard
-- ------------------------------------------------------------
-- Titles, median return multiple, hit rate, and audience reach by genre.
-- Median rather than mean because return multiple has a long right tail
-- that a handful of outliers would otherwise dominate.
-- SQLite has no MEDIAN(), so it is computed with a row-number CTE.
-- ============================================================

WITH ranked AS (
    SELECT
        genre,
        return_multiple,
        ROW_NUMBER() OVER (PARTITION BY genre ORDER BY return_multiple) AS rn,
        COUNT(*)    OVER (PARTITION BY genre)                           AS n
    FROM content
    WHERE return_multiple IS NOT NULL
      AND genre <> 'Unknown'
),
median_return AS (
    SELECT genre, AVG(return_multiple) AS median_return
    FROM ranked
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY genre
)
SELECT
    c.genre,
    COUNT(*)                                            AS titles,
    ROUND(m.median_return, 2)                           AS median_return_x,
    ROUND(100.0 * AVG(c.profitable), 1)                 AS pct_profitable,
    ROUND(AVG(c.production_budget) / 1e6, 1)            AS avg_budget_musd,
    ROUND(AVG(c.audience_volume), 0)                    AS avg_audience_volume,
    ROUND(AVG(c.critic_score), 1)                       AS avg_critic_score,
    ROUND(AVG(c.audience_score), 1)                     AS avg_audience_score
FROM content c
JOIN median_return m ON m.genre = c.genre
WHERE c.genre <> 'Unknown'
GROUP BY c.genre, m.median_return
HAVING COUNT(*) >= 20
ORDER BY median_return_x DESC;


-- ============================================================
-- 2. Budget tier performance
-- ------------------------------------------------------------
-- Does spending more return more? Buckets titles into budget tiers and
-- compares efficiency across them.
-- ============================================================

SELECT
    CASE
        WHEN production_budget <  5000000 THEN 'A. Under $5M'
        WHEN production_budget < 20000000 THEN 'B. $5-20M'
        WHEN production_budget < 50000000 THEN 'C. $20-50M'
        WHEN production_budget < 100000000 THEN 'D. $50-100M'
        ELSE                                   'E. $100M+'
    END                                                 AS budget_tier,
    COUNT(*)                                            AS titles,
    ROUND(AVG(return_multiple), 2)                      AS avg_return_x,
    ROUND(100.0 * AVG(profitable), 1)                   AS pct_profitable,
    ROUND(AVG(worldwide_revenue) / 1e6, 1)              AS avg_revenue_musd,
    ROUND(AVG(international_share) * 100, 1)            AS avg_intl_share_pct
FROM content
WHERE production_budget IS NOT NULL
  AND return_multiple  IS NOT NULL
GROUP BY budget_tier
ORDER BY budget_tier;


-- ============================================================
-- 3. Critic / audience divergence by genre
-- ------------------------------------------------------------
-- Where do critics and audiences disagree? Positive gap = critics score
-- higher. Relevant to programming: audience-favoured, critic-panned genres
-- are cheap to license and still perform.
-- ============================================================

SELECT
    genre,
    COUNT(*)                                            AS titles,
    ROUND(AVG(critic_score), 1)                         AS avg_critic,
    ROUND(AVG(audience_score), 1)                       AS avg_audience,
    ROUND(AVG(critic_audience_gap), 1)                  AS avg_gap
FROM content
WHERE critic_score   IS NOT NULL
  AND audience_score IS NOT NULL
  AND genre <> 'Unknown'
GROUP BY genre
HAVING COUNT(*) >= 20
ORDER BY avg_gap;


-- ============================================================
-- 4. Release timing
-- ------------------------------------------------------------
-- Seasonality in volume and performance by release quarter, split by era so
-- the secular growth in the catalogue does not mask the pattern.
-- ============================================================

SELECT
    release_era,
    release_quarter,
    COUNT(*)                                            AS titles,
    ROUND(AVG(worldwide_revenue) / 1e6, 1)              AS avg_revenue_musd,
    ROUND(AVG(return_multiple), 2)                      AS avg_return_x
FROM content
WHERE return_multiple IS NOT NULL
  AND release_era <> 'nan'
GROUP BY release_era, release_quarter
ORDER BY release_era, release_quarter;


-- ============================================================
-- 5. Year-over-year catalogue trend
-- ------------------------------------------------------------
-- Uses a window function to compute YoY change in title volume and average
-- revenue — the shape of a recurring monthly/quarterly report.
-- ============================================================

WITH yearly AS (
    SELECT
        release_year,
        COUNT(*)                        AS titles,
        AVG(worldwide_revenue)          AS avg_revenue,
        AVG(return_multiple)            AS avg_return
    FROM content
    WHERE release_year BETWEEN 1980 AND 2010
    GROUP BY release_year
)
SELECT
    release_year,
    titles,
    titles - LAG(titles) OVER (ORDER BY release_year)   AS titles_yoy,
    ROUND(avg_revenue / 1e6, 1)                         AS avg_revenue_musd,
    ROUND(
        100.0 * (avg_revenue - LAG(avg_revenue) OVER (ORDER BY release_year))
        / LAG(avg_revenue) OVER (ORDER BY release_year), 1
    )                                                   AS revenue_yoy_pct,
    ROUND(avg_return, 2)                                AS avg_return_x
FROM yearly
ORDER BY release_year;


-- ============================================================
-- 6. Top performers by genre
-- ------------------------------------------------------------
-- Ranks titles within each genre by return multiple and keeps the top 3.
-- ============================================================

WITH ranked AS (
    SELECT
        genre,
        title,
        release_year,
        ROUND(production_budget / 1e6, 1)               AS budget_musd,
        ROUND(worldwide_revenue / 1e6, 1)              AS revenue_musd,
        ROUND(return_multiple, 1)                      AS return_x,
        RANK() OVER (
            PARTITION BY genre ORDER BY return_multiple DESC
        )                                              AS rnk
    FROM content
    WHERE return_multiple IS NOT NULL
      AND production_budget >= 1000000   -- exclude micro-budget outliers
      AND genre <> 'Unknown'
)
SELECT genre, title, release_year, budget_musd, revenue_musd, return_x
FROM ranked
WHERE rnk <= 3
ORDER BY genre, rnk;


-- ============================================================
-- 7. Data quality check
-- ------------------------------------------------------------
-- Field-level completeness. Run this first on any refresh — the analysis
-- above is only valid on fields with adequate coverage.
-- ============================================================

SELECT
    'production_budget' AS field,
    COUNT(*)                                            AS total_rows,
    SUM(CASE WHEN production_budget IS NULL THEN 1 ELSE 0 END) AS nulls,
    ROUND(100.0 * SUM(CASE WHEN production_budget IS NOT NULL THEN 1 ELSE 0 END)
          / COUNT(*), 1)                                AS pct_complete
FROM content
UNION ALL
SELECT 'critic_score', COUNT(*),
       SUM(CASE WHEN critic_score IS NULL THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN critic_score IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 1)
FROM content
UNION ALL
SELECT 'audience_score', COUNT(*),
       SUM(CASE WHEN audience_score IS NULL THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN audience_score IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 1)
FROM content
UNION ALL
SELECT 'audience_volume', COUNT(*),
       SUM(CASE WHEN audience_volume IS NULL THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN audience_volume IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 1)
FROM content;
