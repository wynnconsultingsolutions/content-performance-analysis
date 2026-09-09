"""
02_explore.py — Exploratory analysis and chart generation.

Pulls aggregates out of SQLite with SQL, shapes them in pandas, and writes
the charts used in the README.

Run:  python src/02_explore.py
"""

import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "content.db"
OUT = ROOT / "output"

plt.rcParams.update({
    "figure.dpi": 130,
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})

ACCENT = "#2B6CB0"
MUTED = "#A0AEC0"


def q(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)


def genre_scorecard(conn) -> pd.DataFrame:
    return q(conn, """
        SELECT genre,
               COUNT(*)                            AS titles,
               AVG(return_multiple)                AS avg_return,
               100.0 * AVG(profitable)             AS pct_profitable,
               AVG(production_budget) / 1e6        AS avg_budget_musd,
               AVG(audience_volume)                AS avg_audience_volume,
               AVG(critic_score)                   AS avg_critic,
               AVG(audience_score)                 AS avg_audience
        FROM content
        WHERE return_multiple IS NOT NULL AND genre <> 'Unknown'
        GROUP BY genre
        HAVING COUNT(*) >= 20
        ORDER BY avg_return DESC
    """)


def budget_tiers(conn) -> pd.DataFrame:
    """Median return by tier, not mean — see finding 4 in the README.

    The mean puts micro-budget titles at 45.9x on the strength of a handful
    of breakouts, which inverts the actual pattern.
    """
    return q(conn, """
        WITH tiered AS (
            SELECT CASE
                     WHEN production_budget <   5000000 THEN 'Under $5M'
                     WHEN production_budget <  20000000 THEN '$5-20M'
                     WHEN production_budget <  50000000 THEN '$20-50M'
                     WHEN production_budget < 100000000 THEN '$50-100M'
                     ELSE '$100M+'
                   END              AS tier,
                   return_multiple,
                   profitable
            FROM content
            WHERE return_multiple IS NOT NULL
        ),
        ranked AS (
            SELECT tier, return_multiple,
                   ROW_NUMBER() OVER (PARTITION BY tier
                                      ORDER BY return_multiple) AS rn,
                   COUNT(*)    OVER (PARTITION BY tier)          AS n
            FROM tiered
        ),
        med AS (
            SELECT tier, AVG(return_multiple) AS median_return
            FROM ranked
            WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
            GROUP BY tier
        )
        SELECT t.tier,
               COUNT(*)                        AS titles,
               m.median_return                 AS median_return,
               AVG(t.return_multiple)          AS mean_return,
               100.0 * AVG(t.profitable)       AS pct_profitable
        FROM tiered t
        JOIN med m ON m.tier = t.tier
        GROUP BY t.tier, m.median_return
    """)


def critic_gap(conn) -> pd.DataFrame:
    return q(conn, """
        SELECT genre,
               AVG(critic_score)         AS avg_critic,
               AVG(audience_score)       AS avg_audience,
               AVG(critic_audience_gap)  AS avg_gap,
               COUNT(*)                  AS titles
        FROM content
        WHERE critic_score IS NOT NULL AND audience_score IS NOT NULL
          AND genre <> 'Unknown'
        GROUP BY genre
        HAVING COUNT(*) >= 20
        ORDER BY avg_gap
    """)


def plot_genre_return(df: pd.DataFrame) -> None:
    d = df.sort_values("avg_return")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(d["genre"], d["avg_return"], color=ACCENT)
    ax.set_xlabel("Average return multiple (worldwide revenue ÷ budget)")
    ax.set_title("Commercial efficiency by genre", fontweight="bold", loc="left")
    for y, (v, n) in enumerate(zip(d["avg_return"], d["titles"])):
        ax.text(v + 0.05, y, f"{v:.1f}x  (n={n})", va="center", fontsize=7.5,
                color="#4A5568")
    ax.set_xlim(0, d["avg_return"].max() * 1.28)
    fig.tight_layout()
    fig.savefig(OUT / "genre_return.png")
    plt.close(fig)


def plot_budget_tiers(df: pd.DataFrame) -> None:
    order = ["Under $5M", "$5-20M", "$20-50M", "$50-100M", "$100M+"]
    d = df.set_index("tier").reindex(order).reset_index()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.4))
    a1.bar(d["tier"], d["median_return"], color=ACCENT)
    a1.set_title("Median return multiple", fontweight="bold", loc="left")
    a1.tick_params(axis="x", rotation=35)
    a1.set_ylim(0, d["median_return"].max() * 1.35)
    for x, (med, mean) in enumerate(zip(d["median_return"], d["mean_return"])):
        a1.text(x, med + 0.06, f"{med:.2f}x", ha="center", fontsize=7.5,
                color="#2D3748")
        a1.text(x, med + 0.26, f"mean {mean:.1f}x", ha="center", fontsize=6.5,
                color="#A0AEC0")
    a2.bar(d["tier"], d["pct_profitable"], color=MUTED)
    a2.set_title("% of titles profitable", fontweight="bold", loc="left")
    a2.tick_params(axis="x", rotation=35)
    a2.set_ylim(0, 100)
    fig.suptitle("Performance by production budget tier", fontweight="bold",
                 x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(OUT / "budget_tiers.png")
    plt.close(fig)


def plot_critic_gap(df: pd.DataFrame) -> None:
    d = df.sort_values("avg_gap")
    fig, ax = plt.subplots(figsize=(7, 4))
    y = range(len(d))
    ax.hlines(y, d["avg_audience"], d["avg_critic"], color="#CBD5E0", lw=2)
    ax.scatter(d["avg_audience"], y, color=ACCENT, s=38, label="Audience", zorder=3)
    ax.scatter(d["avg_critic"], y, color="#DD6B20", s=38, label="Critic", zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(d["genre"])
    ax.set_xlabel("Score (0-100)")
    ax.set_title("Critic vs audience score by genre", fontweight="bold", loc="left")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "critic_gap.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as conn:
        genres = genre_scorecard(conn)
        tiers = budget_tiers(conn)
        gaps = critic_gap(conn)

    print("\n=== Genre scorecard ===")
    print(genres.round(2).to_string(index=False))
    print("\n=== Budget tiers ===")
    print(tiers.round(2).to_string(index=False))
    print("\n=== Critic/audience gap ===")
    print(gaps.round(1).to_string(index=False))

    plot_genre_return(genres)
    plot_budget_tiers(tiers)
    plot_critic_gap(gaps)
    print(f"\nCharts written to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
