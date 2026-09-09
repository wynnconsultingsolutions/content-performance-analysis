"""
01_clean.py — Build the analysis table.

Reads the raw catalog JSON, cleans it, derives the performance KPIs used
downstream, and writes two outputs:

  data/content_performance.csv  — flat table for Tableau
  data/content.db               — SQLite database for the SQL in sql/

Run:  python src/01_clean.py
"""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "movies_raw.json"
CSV_OUT = ROOT / "data" / "content_performance.csv"
DB_OUT = ROOT / "data" / "content.db"

# Columns dropped for coverage reasons — see README "Data quality notes".
LOW_COVERAGE = ["US DVD Sales", "Running Time min", "Director"]

RENAME = {
    "Title": "title",
    "US Gross": "domestic_revenue",
    "Worldwide Gross": "worldwide_revenue",
    "Production Budget": "production_budget",
    "Release Date": "release_date",
    "MPAA Rating": "content_rating",
    "Distributor": "distributor",
    "Source": "source_type",
    "Major Genre": "genre",
    "Creative Type": "creative_type",
    "Rotten Tomatoes Rating": "critic_score",
    "IMDB Rating": "audience_score_raw",
    "IMDB Votes": "audience_volume",
}


def load_raw() -> pd.DataFrame:
    with open(RAW) as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    print(f"Loaded {len(df):,} raw records")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in LOW_COVERAGE if c in df.columns])
    df = df.rename(columns=RENAME)

    # Parse dates. The source uses "Jun 12 1998"; a handful are malformed
    # and become NaT, which we drop rather than guess at.
    df["release_date"] = pd.to_datetime(
        df["release_date"], format="%b %d %Y", errors="coerce"
    )

    numeric = [
        "domestic_revenue",
        "worldwide_revenue",
        "production_budget",
        "critic_score",
        "audience_score_raw",
        "audience_volume",
    ]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Rows with no title, no date, or no revenue can't support the analysis.
    before = len(df)
    df = df.dropna(subset=["title", "release_date", "worldwide_revenue"])
    print(f"Dropped {before - len(df):,} rows missing title/date/revenue")

    # Zero or negative budgets are placeholders, not real values.
    df.loc[df["production_budget"] <= 0, "production_budget"] = np.nan

    df = df.drop_duplicates(subset=["title", "release_date"])
    return df


def derive_kpis(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["release_year"] = df["release_date"].dt.year
    df["release_month"] = df["release_date"].dt.month
    df["release_quarter"] = "Q" + df["release_date"].dt.quarter.astype(str)

    # Grouping release years into eras keeps the regression interpretable
    # and absorbs the secular growth in audience volume over time.
    df["release_era"] = pd.cut(
        df["release_year"],
        bins=[-np.inf, 1989, 1999, 2004, np.inf],
        labels=["pre-1990", "1990s", "2000-2004", "2005+"],
    )

    # --- Performance KPIs -------------------------------------------------
    # Return multiple: revenue per dollar of production spend. The core
    # commercial efficiency measure for acquisition decisions.
    df["return_multiple"] = df["worldwide_revenue"] / df["production_budget"]

    df["profitable"] = (df["return_multiple"] >= 1).astype("Int64")
    df.loc[df["return_multiple"].isna(), "profitable"] = pd.NA

    # Share of revenue earned outside the domestic market.
    df["international_share"] = (
        df["worldwide_revenue"] - df["domestic_revenue"]
    ) / df["worldwide_revenue"]
    df.loc[
        (df["worldwide_revenue"] <= 0) | (df["international_share"] < 0),
        "international_share",
    ] = np.nan

    # Put audience score on the same 0-100 scale as the critic score so the
    # two are directly comparable.
    df["audience_score"] = df["audience_score_raw"] * 10
    df["critic_audience_gap"] = df["critic_score"] - df["audience_score"]

    # Audience volume is the closest proxy this dataset has for reach. It is
    # heavily right-skewed, so the log is what the regression models.
    df["log_audience_volume"] = np.log(df["audience_volume"].where(
        df["audience_volume"] > 0))
    df["log_budget"] = np.log(df["production_budget"])
    df["log_worldwide_revenue"] = np.log(df["worldwide_revenue"].where(
        df["worldwide_revenue"] > 0))

    return df


def tidy_categories(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["genre", "creative_type", "content_rating", "source_type",
                "distributor"]:
        df[col] = df[col].fillna("Unknown").str.strip()

    # Collapse the long tail of distributors; anything under 25 titles has
    # too little data to say anything about.
    counts = df["distributor"].value_counts()
    small = counts[counts < 25].index
    df["distributor_grouped"] = df["distributor"].where(
        ~df["distributor"].isin(small), "Other"
    )

    # "Not Rated" and "Open" both mean unrated in this source.
    df["content_rating"] = df["content_rating"].replace(
        {"Open": "Not Rated", "NC-17": "Not Rated"}
    )
    return df


def main() -> None:
    df = load_raw()
    df = clean(df)
    df = derive_kpis(df)
    df = tidy_categories(df)

    cols = [
        "title", "release_date", "release_year", "release_month",
        "release_quarter", "release_era", "genre", "creative_type",
        "content_rating", "source_type", "distributor", "distributor_grouped",
        "production_budget", "domestic_revenue", "worldwide_revenue",
        "return_multiple", "profitable", "international_share",
        "critic_score", "audience_score", "critic_audience_gap",
        "audience_volume", "log_budget", "log_worldwide_revenue",
        "log_audience_volume",
    ]
    df = df[cols].sort_values("release_date").reset_index(drop=True)

    df.to_csv(CSV_OUT, index=False)
    print(f"Wrote {CSV_OUT.relative_to(ROOT)}  ({len(df):,} rows)")

    with sqlite3.connect(DB_OUT) as conn:
        df.assign(
            release_date=df["release_date"].dt.strftime("%Y-%m-%d"),
            release_era=df["release_era"].astype(str),
        ).to_sql("content", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX idx_genre ON content(genre)")
        conn.execute("CREATE INDEX idx_year ON content(release_year)")
    print(f"Wrote {DB_OUT.relative_to(ROOT)}  (table: content)")

    print("\nCoverage of key analysis fields:")
    for col in ["production_budget", "return_multiple", "critic_score",
                "audience_score", "audience_volume"]:
        pct = 100 * df[col].notna().mean()
        print(f"  {col:22} {df[col].notna().sum():>5,} / {len(df):,}  ({pct:.0f}%)")


if __name__ == "__main__":
    main()
