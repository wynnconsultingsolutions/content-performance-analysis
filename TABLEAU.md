# Building the Tableau dashboard

Roughly an hour. The data is already shaped for it — `data/content_performance.csv`
is one row per title with every field the dashboard needs, so there is no
preparation left to do inside Tableau.

You need Tableau Public (free, tableau.com/products/public). It saves workbooks to
a public profile, which is what makes it usable as a portfolio link.

---

## Setup

1. Open Tableau Public → **Connect → Text file** → select
   `data/content_performance.csv`.
2. On the data source tab, check the field types. Tableau usually gets these
   right, but confirm:
   - `release_date` → Date
   - `release_year`, `release_month` → Number (whole), then right-click →
     **Convert to Dimension**
   - `profitable` → Number (whole)
   - everything else numeric → Measure, everything else text → Dimension
3. Rename the data source (bottom left) to `Content Catalogue`.

### Two calculated fields

Tableau aggregates with `AVG` by default, and finding #4 in the README is that
average return multiple is misleading here. Create these first.

**Median Return** — right-click in the Data pane → **Create Calculated Field**:

```
MEDIAN([Return Multiple])
```

**Hit Rate** — same again:

```
AVG([Profitable])
```

Set its default format to Percentage with 0 decimals (right-click the field →
Default Properties → Number Format).

---

## Sheet 1 — Genre scorecard

The anchor view.

- **Rows:** `Genre`
- **Columns:** `Median Return`
- **Sort:** descending by Median Return
- **Filter:** `Genre` → exclude `Unknown`. Then add `Number of Records` as a filter
  set to at least 20 — or simpler, exclude the low-count genres by hand
  (Concert/Performance, and anything else under 20 titles).
- **Marks:** Bar. Drag `Hit Rate` onto Color, `Number of Records` onto Tooltip.
- Colour: sequential blue, so darker = higher hit rate.

Title it **Commercial efficiency by genre**. Add a caption noting the median
choice — reviewers notice that kind of thing, and it is the most defensible
decision in the whole dashboard.

## Sheet 2 — Budget tier performance

- Create a calculated field **Budget Tier**:

```
IF [Production Budget] < 5000000 THEN "Under $5M"
ELSEIF [Production Budget] < 20000000 THEN "$5-20M"
ELSEIF [Production Budget] < 50000000 THEN "$20-50M"
ELSEIF [Production Budget] < 100000000 THEN "$50-100M"
ELSE "$100M+"
END
```

- **Columns:** `Budget Tier` (manually sort the tiers into ascending order —
  right-click → Sort → Manual)
- **Rows:** `Median Return`, then `Hit Rate` as a second row → creates a dual view
- **Marks:** Bar

Title it **Bigger budgets, smaller multiples**. That is the finding; say it in the
title rather than making the reader derive it.

## Sheet 3 — Critic vs audience divergence

The most visually interesting view, and a dumbbell chart is worth learning.

- **Rows:** `Genre`
- **Columns:** `AVG(Critic Score)`, then `AVG(Audience Score)` as a second
  continuous pill
- Right-click the second axis → **Dual Axis**, then right-click → **Synchronize
  Axis**
- Set both Marks cards to Circle, size ~120, different colours (blue for audience,
  orange for critic)
- To add the connecting line: duplicate one measure a third time as a Gantt or use
  a reference line. Simplest version — skip the line entirely, two dots per genre
  reads fine.
- **Sort:** by the gap. Create **Score Gap** = `AVG([Critic Score]) -
  AVG([Audience Score])` and sort rows by it ascending.

Title it **Where critics and audiences disagree**.

## Sheet 4 — Catalogue trend

- **Columns:** `release_year` (continuous)
- **Rows:** `Number of Records`
- **Marks:** Area or Line
- **Filter:** `release_year` between 1980 and 2010 — coverage before and after is
  thin enough to distort the shape
- Add `Genre` to Colour for a stacked view

Title it **Catalogue composition over time**.

---

## Assembling the dashboard

1. **New Dashboard**. Size: **Automatic**, or fixed at 1200×900 if you want
   predictable layout.
2. Layout: Sheet 1 top-left (largest), Sheet 3 top-right, Sheet 2 bottom-left,
   Sheet 4 bottom-right.
3. Add a **Text** object across the top with the dashboard title and a one-line
   subtitle: *What drives audience reach and commercial return across a
   3,200-title catalogue.*
4. **Filters:** drag `Release Era` and `Content Rating` in as filter controls.
   For each, use the dropdown → **Apply to Worksheets → All Using This Data
   Source**. Without that step the filters only affect one sheet, which is the most
   common thing to get wrong here.
5. **Interactivity:** select Sheet 1 → dropdown → **Use as Filter**. Clicking a
   genre now filters the rest of the dashboard. This is the single feature that
   makes it read as a dashboard rather than four charts.
6. Tidy up: remove redundant legends, set every sheet's tooltip to something
   readable, and hide axis titles that repeat the header.

## Publishing

**File → Save to Tableau Public As…** You will need a free account.

Once saved, open your profile, find the viz, and use the share link. Two things to
set on the published viz:

- Turn on **Show workbook in profile**.
- Under the viz settings, enable **Allow others to download this workbook** —
  reviewers sometimes want to see how it was built, and letting them is a point in
  your favour.

Put the link in the Projects section of your resume and in the Featured section of
your LinkedIn profile.

---

## Before you call it done

Open the dashboard cold and ask whether someone who has never seen the data could
say what it shows within about ten seconds. If not, the titles are doing too little
work. Chart titles that state the finding — "Bigger budgets, smaller multiples" —
beat titles that state the contents — "Return multiple by budget tier."

And be ready for the obvious interview question: *why median instead of mean?*
Finding #4 in the README is the answer, and it is a good one.
